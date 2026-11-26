"""Sugerencia de surtido: qué comprar y qué traspasar entre sucursales (solo lectura de Microsip).

Cruza, por artículo y por almacén de cada sucursal:
- la venta del periodo (Punto de Venta + Facturas/Remisiones de Ventas) → venta diaria;
- la existencia de hoy (CAPAS_COSTOS con capa sin agotar, igual que el Checador de precio);
- los traspasos que RECIBIÓ cada sucursal (concepto TRASPASO; el envío va al almacén puente
  "Mercancía en tránsito" y la recepción sale de ahí hacia la sucursal destino).

Con eso arma, en este orden de preferencia, para cada sucursal a la que le falta:
  1) pasarle de otra sucursal que lo tiene parado (no lo vende o le sobra mucho);
  2) mandárselo de CEDIS;
  3) si no alcanza, comprarlo.
Además señala qué sucursales piden traspaso seguido y sí venden (para dejarles un mínimo fijo y que
lo mande CEDIS) y cuáles piden traspaso pero no lo venden (no mandarles más y regresar lo que tienen).
Nunca escribe nada en Microsip.
"""
import math
import re
from datetime import date, timedelta

import microsip

ALMACEN_TRANSITO_ID = 645           # "Traspaso sucursal - Mercancía en tránsito"
CONCEPTO_TRASPASO_ID = 36           # "TRASPASO (SALIDA)" confirmado a mano; también se buscan por nombre
NO_TIENDA = re.compile(r"TRANSITO|TRÁNSITO|CUARENTENA|REPARACION|LABORATORIO|PREPARACION|LICITACION|EXPO", re.I)
# DEPOSITO CORPO sí cuenta como sucursal: vende poco, pero su existencia se puede pasar a otras.
ES_CEDIS = re.compile(r"GENERAL|CEDIS", re.I)
# Artículos que no son mercancía (cobros, servicios): no se surten ni se compran.
NO_MERCANCIA = re.compile(r"^(ANTICIPO|FLETE|SERVICIO|ENVIO|ENVÍO|MANO DE OBRA|INSTALACION|INSTALACIÓN|DESCUENTO|REDONDEO)\b", re.I)


def _t(v):
    return (v or "").strip() if isinstance(v, str) else v


def _cols(cur, tabla):
    cur.execute("SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = ?", (tabla,))
    return {r[0] for r in cur.fetchall()}


def _lotes(ids, n=900):
    ids = list(ids)
    for i in range(0, len(ids), n):
        yield ids[i:i + n]


def nombre_corto(nombre):
    n = _t(nombre) or ""
    n = re.sub(r"^ALMAC[EÉ�]N\s+", "", n, flags=re.I).strip()
    return n or _t(nombre)


def _conectar(config):
    """Igual que microsip._conectar pero con el juego de caracteres de Microsip (para que salgan bien los acentos)."""
    import fdb
    microsip._asegurar_cargado()
    try:
        return fdb.connect(dsn=microsip._dsn(config), user=config["microsip_usuario"], password=config["microsip_password"],
                           charset="ISO8859_1")
    except Exception:
        return microsip._conectar(config)


def opciones(config):
    """Almacenes con su sugerencia: cuáles son sucursales de venta y cuál es CEDIS."""
    con = _conectar(config)
    try:
        cur = con.cursor()
        cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")
        alms = [{"id": i, "nombre": _t(n) or str(i)} for i, n in cur.fetchall() if i != ALMACEN_TRANSITO_ID]
        alms.sort(key=lambda a: a["nombre"])
        cedis = next((a["id"] for a in alms if ES_CEDIS.search(a["nombre"])), None)
        for a in alms:
            a["es_cedis"] = a["id"] == cedis
            a["tienda_sugerida"] = a["id"] != cedis and not NO_TIENDA.search(a["nombre"])
        cur.execute("SELECT LINEA_ARTICULO_ID, NOMBRE FROM LINEAS_ARTICULOS ORDER BY NOMBRE")
        lineas = [{"id": i, "nombre": _t(n)} for i, n in cur.fetchall()]
        return {"almacenes": alms, "cedis_sugerido": cedis, "lineas": lineas}
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------------------------
# Tipos de documento de Punto de venta que son venta real. Visto en la base real (nov 2026): "O" = orden del mostrador
# que se convierte en ticket "V" (liga O->V); "T" = pendiente que pasa a "O"; las facturas "F" salen de tickets (V->F)
# y no traen almacén. Por eso solo cuentan V (y F que no venga de un ticket); D resta.
TIPOS_PV_VENTA = ("V",)   # las F de Punto de venta salen de tickets y no traen almacén


def _diag_pv(cur, desde, hasta, cancel, diag):
    """Para revisar qué es cada TIPO_DOCTO de Punto de venta: folios de ejemplo, piezas, ligas y estatus."""
    d = {}
    cur.execute(f"""SELECT p.TIPO_DOCTO, COALESCE(p.ESTATUS, '?'), COUNT(*) FROM DOCTOS_PV p
                    WHERE p.FECHA >= ? AND p.FECHA <= ?{cancel} GROUP BY 1, 2""", (desde, hasta))
    for t, e, n in cur.fetchall():
        d.setdefault(_t(t) or "?", {}).setdefault("estatus", {})[_t(e)] = n
    cur.execute(f"""SELECT p.TIPO_DOCTO, SUM(d.UNIDADES), COUNT(DISTINCT p.DOCTO_PV_ID) FROM DOCTOS_PV p
                    JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID WHERE p.FECHA >= ? AND p.FECHA <= ?{cancel} GROUP BY 1""", (desde, hasta))
    for t, u, n in cur.fetchall():
        d.setdefault(_t(t) or "?", {}).update({"piezas": float(u or 0), "docs_con_renglones": n})
    for t in list(d):
        cur.execute(f"""SELECT FIRST 4 p.FOLIO, p.ALMACEN_ID FROM DOCTOS_PV p WHERE p.TIPO_DOCTO = ? AND p.FECHA >= ? AND p.FECHA <= ?{cancel}
                        ORDER BY p.FECHA DESC""", (t, desde, hasta))
        d[t]["folios"] = [f"{_t(a)}@{b}" for a, b in cur.fetchall()]
    if _cols(cur, "DOCTOS_PV_LIGAS") >= {"DOCTO_PV_FTE_ID", "DOCTO_PV_DEST_ID"}:
        cur.execute(f"""SELECT f.TIPO_DOCTO, t.TIPO_DOCTO, COUNT(*) FROM DOCTOS_PV_LIGAS l
                        JOIN DOCTOS_PV f ON f.DOCTO_PV_ID = l.DOCTO_PV_FTE_ID JOIN DOCTOS_PV t ON t.DOCTO_PV_ID = l.DOCTO_PV_DEST_ID
                        WHERE t.FECHA >= ? AND t.FECHA <= ? GROUP BY 1, 2""", (desde, hasta))
        diag["ligas_pv"] = [f"{_t(a)}->{_t(b)}: {n}" for a, b, n in cur.fetchall()]
    diag["detalle_pv"] = d


LUNES_BASE = date(2000, 1, 3)   # lunes: las semanas se cuentan desde aquí


def _lunes(n):
    return LUNES_BASE + timedelta(days=int(n) * 7)


def _ventas(cur, desde, hasta, corte_reciente, diag, detalle_pv=False):
    """{(almacen, articulo): {"u": unidades, "dias": set(semanas), "u30": unidades recientes, "por_dia": {lunes: u}}}
    Para que un año completo sea rápido, la venta se trae SUMADA POR SEMANA (lunes a domingo) y no por día.
    Aparte se leen los días que abrió cada almacén (para los días hábiles)."""
    v = {}
    abiertos = {}

    def sumar(alm, art, fecha, u):
        if not alm or not art:
            return
        x = v.setdefault((alm, art), {"u": 0.0, "dias": set(), "u30": 0.0, "por_dia": {}})
        x["u"] += u
        x["por_dia"][fecha] = x["por_dia"].get(fecha, 0.0) + u
        if u > 0:
            x["dias"].add(fecha)
        if fecha >= corte_reciente:
            x["u30"] += u

    # Punto de venta
    cols_pv = _cols(cur, "DOCTOS_PV")
    if cols_pv:
        cancel = " AND p.FECHA_HORA_CANCELACION IS NULL" if "FECHA_HORA_CANCELACION" in cols_pv else ""
        if "ESTATUS" in cols_pv:
            cancel += " AND COALESCE(p.ESTATUS, '') <> 'C'"
        cur.execute(f"SELECT p.TIPO_DOCTO, COUNT(*) FROM DOCTOS_PV p WHERE p.FECHA >= ? AND p.FECHA <= ?{cancel} GROUP BY p.TIPO_DOCTO",
                    (desde, hasta))
        diag["tipos_pv"] = {(_t(a) or "?"): b for a, b in cur.fetchall()}
        if detalle_pv:
            try:
                _diag_pv(cur, desde, hasta, cancel, diag)
            except Exception as e:
                diag["detalle_pv_error"] = str(e)[:300]
        # Facturas de tickets: si la factura viene de tickets (DOCTOS_PV_LIGAS), sus renglones repiten lo
        # del ticket; solo cuentan las facturas que no salen de un ticket.
        excluir = ""
        if _cols(cur, "DOCTOS_PV_LIGAS") >= {"DOCTO_PV_FTE_ID", "DOCTO_PV_DEST_ID"}:
            # Solo la FACTURA que viene de tickets se descarta (los tickets V también son destino de una liga:
            # vienen de la orden "O" del mostrador, y esos sí son la venta).
            excluir = " AND NOT (p.TIPO_DOCTO = 'F' AND EXISTS (SELECT 1 FROM DOCTOS_PV_LIGAS l WHERE l.DOCTO_PV_DEST_ID = p.DOCTO_PV_ID))"
            diag["pv_ligas"] = True
        tipos = ",".join(f"'{x}'" for x in TIPOS_PV_VENTA)
        if "F" not in TIPOS_PV_VENTA:
            excluir = ""
        cur.execute(f"""SELECT p.ALMACEN_ID, d.ARTICULO_ID, DATEDIFF(DAY FROM DATE '{LUNES_BASE.isoformat()}' TO p.FECHA) / 7,
                               SUM(CASE WHEN p.TIPO_DOCTO = 'D' THEN -ABS(d.UNIDADES) ELSE d.UNIDADES END)
                        FROM DOCTOS_PV p JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID
                        WHERE p.TIPO_DOCTO IN ({tipos}, 'D') AND p.FECHA >= ? AND p.FECHA <= ?{cancel}{excluir}
                        GROUP BY 1, 2, 3""", (desde, hasta))
        for alm, art, sem, u in cur.fetchall():
            sumar(alm, art, _lunes(sem), float(u or 0))
        cur.execute(f"""SELECT p.ALMACEN_ID, p.FECHA FROM DOCTOS_PV p
                        WHERE p.TIPO_DOCTO IN ({tipos}) AND p.FECHA >= ? AND p.FECHA <= ?{cancel} GROUP BY 1, 2""", (desde, hasta))
        for alm, f in cur.fetchall():
            abiertos.setdefault(alm, set()).add(f)

    # Ventas: facturas y remisiones (sin contar dos veces la factura que sale de una remisión)
    cols_ve = _cols(cur, "DOCTOS_VE")
    if cols_ve and "ALMACEN_ID" in cols_ve:
        cancel = " AND p.FECHA_HORA_CANCELACION IS NULL" if "FECHA_HORA_CANCELACION" in cols_ve else ""
        cancel += " AND COALESCE(p.ESTATUS, '') <> 'C'"
        excluir = ""
        if _cols(cur, "DOCTOS_VE_LIGAS") >= {"DOCTO_VE_FTE_ID", "DOCTO_VE_DEST_ID"}:
            excluir = (" AND NOT (p.TIPO_DOCTO = 'F' AND EXISTS (SELECT 1 FROM DOCTOS_VE_LIGAS l JOIN DOCTOS_VE r"
                       " ON r.DOCTO_VE_ID = l.DOCTO_VE_FTE_ID WHERE l.DOCTO_VE_DEST_ID = p.DOCTO_VE_ID AND r.TIPO_DOCTO = 'R'))")
        cur.execute(f"""SELECT p.ALMACEN_ID, d.ARTICULO_ID, DATEDIFF(DAY FROM DATE '{LUNES_BASE.isoformat()}' TO p.FECHA) / 7, SUM(d.UNIDADES)
                        FROM DOCTOS_VE p JOIN DOCTOS_VE_DET d ON d.DOCTO_VE_ID = p.DOCTO_VE_ID
                        WHERE p.TIPO_DOCTO IN ('F', 'R') AND p.FECHA >= ? AND p.FECHA <= ?{cancel}{excluir}
                        GROUP BY 1, 2, 3""", (desde, hasta))
        n = 0
        for alm, art, sem, u in cur.fetchall():
            sumar(alm, art, _lunes(sem), float(u or 0)); n += 1
        diag["renglones_ventas_ve"] = n
        cur.execute(f"""SELECT p.ALMACEN_ID, p.FECHA FROM DOCTOS_VE p
                        WHERE p.TIPO_DOCTO IN ('F', 'R') AND p.FECHA >= ? AND p.FECHA <= ?{cancel} GROUP BY 1, 2""", (desde, hasta))
        for alm, f in cur.fetchall():
            abiertos.setdefault(alm, set()).add(f)
    return v, abiertos


def _existencias(cur):
    cur.execute("""SELECT ALMACEN_ID, ARTICULO_ID, SUM(EXISTENCIA) FROM CAPAS_COSTOS
                   WHERE CAPA_AGOTADA = 'N' GROUP BY ALMACEN_ID, ARTICULO_ID""")
    return {(a, b): float(e or 0) for a, b, e in cur.fetchall()}


def _folio_traspaso(desc):
    if not desc or ":" not in desc:
        return None
    return desc.rsplit(":", 1)[-1].strip().upper() or None


def _traspasos(cur, desde, hasta, diag):
    """Lista de recepciones: {destino, origen, articulo, unidades, fecha, folio}."""
    conceptos = {CONCEPTO_TRASPASO_ID}
    try:
        cur.execute("SELECT CONCEPTO_IN_ID, NOMBRE FROM CONCEPTOS_IN")
        for cid, nom in cur.fetchall():
            if "TRASPASO" in (_t(nom) or "").upper():
                conceptos.add(cid)
    except Exception:
        pass
    diag["conceptos_traspaso"] = sorted(conceptos)
    ph = ",".join("?" * len(conceptos))
    cols_in = _cols(cur, "DOCTOS_IN")
    c_dest = "ALMACEN_DESTINO_ID" if "ALMACEN_DESTINO_ID" in cols_in else "NULL"
    # Los envíos se buscan desde un poco antes para emparejar recepciones del inicio del periodo.
    cur.execute(f"""SELECT DOCTO_IN_ID, ALMACEN_ID, {c_dest}, FECHA, DESCRIPCION, FOLIO FROM DOCTOS_IN
                    WHERE CONCEPTO_IN_ID IN ({ph}) AND COALESCE(CANCELADO, 'N') = 'N' AND FECHA >= ? AND FECHA <= ?""",
                (*conceptos, desde - timedelta(days=45), hasta))
    docs = cur.fetchall()
    origen_por_folio = {}
    recepciones, directos = [], []
    for did, alm, dest, fecha, desc, folio in docs:
        if dest == ALMACEN_TRANSITO_ID and alm != ALMACEN_TRANSITO_ID:
            f = _folio_traspaso(_t(desc))
            if f:
                origen_por_folio[f] = alm
        elif alm == ALMACEN_TRANSITO_ID and dest:
            if fecha >= desde:
                recepciones.append((did, dest, fecha, _folio_traspaso(_t(desc)) or _t(folio)))
        elif dest and alm and fecha >= desde:
            directos.append((did, dest, fecha, _t(folio), alm))
    diag["traspasos_recibidos"] = len(recepciones)
    diag["traspasos_directos"] = len(directos)
    salida = []
    todos = [(d, dest, f, fol, origen_por_folio.get(fol)) for d, dest, f, fol in recepciones] + directos
    por_doc = {d: (dest, f, fol, ori) for d, dest, f, fol, ori in todos}
    if not por_doc:
        return salida
    cols_det = _cols(cur, "DOCTOS_IN_DET")
    c_tipo = "TIPO_MOVTO" if "TIPO_MOVTO" in cols_det else "NULL"
    c_alm = "ALMACEN_ID" if "ALMACEN_ID" in cols_det else "NULL"
    filas = []
    for lote in _lotes(por_doc):
        cur.execute(f"""SELECT DOCTO_IN_ID, ARTICULO_ID, {c_tipo}, {c_alm}, SUM(UNIDADES) FROM DOCTOS_IN_DET
                        WHERE DOCTO_IN_ID IN ({','.join('?' * len(lote))}) GROUP BY DOCTO_IN_ID, ARTICULO_ID, {c_tipo}, {c_alm}""",
                    tuple(lote))
        filas.extend(cur.fetchall())
    # Si el documento trae renglones de entrada (E), solo esos (si no, se contaría la salida y la entrada).
    con_entrada = {d for d, _, tipo, _, _ in filas if _t(tipo) == "E"}
    agg = {}
    for d, art, tipo, alm_det, u in filas:
        if d in con_entrada and _t(tipo) != "E":
            continue
        dest, fecha, fol, ori = por_doc[d]
        k = (d, art)
        agg[k] = agg.get(k, 0.0) + abs(float(u or 0))
    for (d, art), u in agg.items():
        dest, fecha, fol, ori = por_doc[d]
        salida.append({"destino": dest, "origen": ori, "articulo": art, "unidades": u, "fecha": fecha, "folio": fol})
    return salida


def _articulos(cur, ids, lineas=None):
    info = {}
    cols = _cols(cur, "ARTICULOS")
    c_lin = "LINEA_ARTICULO_ID" if "LINEA_ARTICULO_ID" in cols else "NULL"
    c_est = "ESTATUS" if "ESTATUS" in cols else "NULL"
    for lote in _lotes(ids):
        cur.execute(f"SELECT ARTICULO_ID, NOMBRE, {c_lin}, {c_est} FROM ARTICULOS WHERE ARTICULO_ID IN ({','.join('?' * len(lote))})", tuple(lote))
        for aid, nom, lin, est in cur.fetchall():
            info[aid] = {"nombre": _t(nom) or f"Artículo {aid}", "linea_id": lin, "estatus": _t(est), "clave": ""}
        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({','.join('?' * len(lote))})", tuple(lote))
        for aid, clave in cur.fetchall():
            if aid in info and not info[aid]["clave"] and clave:
                info[aid]["clave"] = _t(clave)
    return info


# ---------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------
def _redondo(x):
    return int(math.ceil(x - 1e-9)) if x > 0 else 0


def _fmt_dias(d, unidad="días hábiles"):
    if d is None:
        return "—"
    if d >= 999:
        return "más de 1 año"
    return f"{d:.0f} {unidad}" if d >= 1 else "menos de 1 día"


def _fmt_sem(s):
    if s is None:
        return "—"
    if s >= 52:
        return "más de 1 año"
    if s < 1:
        return f"{s * 7:.0f} días" if s * 7 >= 1 else "menos de 1 día"
    return f"{s:.1f} semanas".replace(".0 ", " ")


def dias_abiertos(abiertos):
    """Días que abrió cada almacén en el periodo = días con al menos un ticket, factura o remisión.
    Así no cuentan domingos, festivos, vacaciones ni días que la sucursal estuvo cerrada."""
    return {a: len(d) for a, d in (abiertos or {}).items()}


def habiles_por_semana(abiertos, hasta):
    """Días hábiles por semana de cada almacén, contados desde su primer día con venta en el periodo
    (una sucursal nueva no se castiga por las semanas en que todavía no existía)."""
    dias = abiertos or {}
    salida = {}
    for a, d in dias.items():
        primero = min(d)
        semanas = max(1.0, ((hasta - primero).days + 1) / 7.0) if hasattr(primero, "year") else None
        salida[a] = min(7.0, len(d) / semanas) if semanas else 6.0
    return salida


MIN_DIAS_VENTA = 3      # con menos de 3 SEMANAS con venta en el periodo es venta esporádica
TOPE_ESPORADICA = 2     # en venta esporádica cada semana cuenta como máximo 2 piezas (venta normal de mostrador)
FACTOR_ATIPICO = 4      # una semana que vende más de 4 veces lo normal (mediana) y al menos 10 piezas más se recorta
MARGEN_ATIPICO = 10     # (con 3x/+3 se recortaban 11 mil semanas normales de productos que venden 1-3 por semana)


def ajustar_venta(v, ignorar_atipicas=True):
    """Venta del periodo sin las ventas atípicas.
    - Esporádica: vendió en menos de MIN_DIAS_VENTA días distintos. Cada uno de esos días cuenta como máximo
      TOPE_ESPORADICA piezas: un producto lento (1 o 2 piezas de vez en cuando) se sigue surtiendo, pero una sola
      venta grande (ej. 2,500 motores en un depósito) no hace que se compre de más.
    - Semana atípica: la que vendió mucho más que su semana normal se recorta al tope max(4×mediana, mediana+10).
    Regresa (unidades_ajustadas, esporadica, atipicos=[(fecha, piezas_del_dia, tope, mediana)])."""
    if not v:
        return 0.0, False, []
    total = max(0.0, v["u"])
    if not ignorar_atipicas or total <= 0:
        return total, False, []
    dias_pos = sorted(u for u in v.get("por_dia", {}).values() if u > 0)
    if len(dias_pos) < MIN_DIAS_VENTA:
        recortes = [(f, u, TOPE_ESPORADICA, 0) for f, u in sorted(v.get("por_dia", {}).items()) if u > TOPE_ESPORADICA]
        ajustado = sum(min(u, TOPE_ESPORADICA) for u in dias_pos)
        return ajustado, bool(recortes), recortes
    n = len(dias_pos)
    mediana = dias_pos[n // 2] if n % 2 else (dias_pos[n // 2 - 1] + dias_pos[n // 2]) / 2
    tope = max(FACTOR_ATIPICO * mediana, mediana + MARGEN_ATIPICO)
    ajustado, atipicos = 0.0, []
    for f, u in sorted(v.get("por_dia", {}).items()):
        if u > tope:
            atipicos.append((f, u, tope, mediana))
            ajustado += tope
        else:
            ajustado += u
    return max(0.0, ajustado), False, atipicos


def calcular(ventas, existencias, traspasos, info, nombres_alm, tiendas, cedis, dias, semanas, dias_recientes, texto=None,
             lineas=None, min_traspasos=3, ignorar_atipicas=True, hasta=None, abiertos_sets=None):
    """semanas = para cuántas semanas surtir. Todo se mide en DÍAS HÁBILES de cada sucursal (los días que abrió)."""
    tiendas = [t for t in tiendas if t != cedis]
    abiertos = dias_abiertos(abiertos_sets)
    por_sem = habiles_por_semana(abiertos_sets, hasta or date.today())
    abre = {t: por_sem.get(t, 6.0) for t in list(tiendas) + ([cedis] if cedis else [])}   # días hábiles por semana
    habiles = {t: max(1, abiertos.get(t, 0)) for t in abre}
    arts = set()
    for (alm, art), v in ventas.items():
        if alm in tiendas or alm == cedis:
            arts.add(art)
    for t in traspasos:
        if t["destino"] in tiendas and not (cedis and t["origen"] == cedis):
            arts.add(t["articulo"])
    txt = (texto or "").strip().upper()
    lineas = set(lineas or [])

    def incluir(a):
        i = info.get(a)
        if not i:
            return False
        if NO_MERCANCIA.search(i["nombre"]):
            return False
        if txt and txt not in i["nombre"].upper() and txt not in (i["clave"] or "").upper():
            return False
        if lineas and i["linea_id"] not in lineas:
            return False
        return True

    arts = {a for a in arts if incluir(a)}
    rec_por = {}
    for t in traspasos:
        # Lo que manda CEDIS es el resurtido normal, no un traspaso que pidió la sucursal: no cuenta.
        if cedis and t["origen"] == cedis:
            continue
        if t["articulo"] in arts and t["destino"] in tiendas:
            x = rec_por.setdefault((t["destino"], t["articulo"]), {"n": 0, "u": 0.0, "origenes": {}, "folios": set()})
            x["u"] += t["unidades"]
            x["folios"].add(t["folio"] or id(t))
            o = t["origen"]
            x["origenes"][o] = x["origenes"].get(o, 0.0) + t["unidades"]
    for x in rec_por.values():
        x["n"] = len(x["folios"])

    nom = lambda a: nombres_alm.get(a, str(a))
    comprar, de_cedis, entre, frecuentes, no_vende, parados, detalle, atipicas = [], [], [], [], [], [], [], []
    for a in sorted(arts, key=lambda x: info[x]["nombre"]):
        i = info[a]
        filas = {}
        for t in tiendas:
            v = ventas.get((t, a), {"u": 0.0, "dias": set(), "u30": 0.0, "por_dia": {}})
            u_real = max(0.0, v["u"])
            u, esporadica, atip = ajustar_venta(v, ignorar_atipicas)
            for fch, pzs, tope, med in atip:
                atipicas.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "sucursal": nom(t),
                                 "fecha": fch.isoformat() if hasattr(fch, "isoformat") else str(fch), "piezas": pzs,
                                 "se_tomaron": round(tope, 1),
                                 "motivo": (f"Solo vendió en {len(v['dias'])} semana(s) del periodo (venta esporádica): de esa semana se tomaron {tope:,.0f} pzas."
                                            if esporadica else f"Esa semana vendió {pzs:,.0f} y en una semana normal vende {med:,.0f}: solo se tomaron {tope:,.0f}.")})
            vd = u / habiles[t]                     # venta por día hábil
            cob_t = semanas * abre[t]                # días hábiles a cubrir en esta sucursal
            e = max(0.0, existencias.get((t, a), 0.0))
            obj = _redondo(vd * cob_t) if u > 0 else 0
            cob = (e / vd) if vd > 0 else (999 if e > 0 else None)
            filas[t] = {"cob_t": cob_t, "habiles": habiles[t], "abre": abre[t], "vendido": u, "vendido_real": u_real, "esporadica": esporadica, "vd": vd, "dias_con_venta": len(v["dias"]),
                        "reciente": max(0.0, v["u30"]),
                        "existencia": e, "objetivo": obj, "cobertura": cob,
                        "recibido": rec_por.get((t, a), {}).get("u", 0.0), "traspasos": rec_por.get((t, a), {}).get("n", 0)}
        vc_aj = ajustar_venta(ventas.get((cedis, a)), ignorar_atipicas)[0] if cedis else 0.0
        e_cedis = max(0.0, existencias.get((cedis, a), 0.0)) if cedis else 0.0
        reserva_cedis = _redondo(vc_aj / habiles[cedis] * semanas * abre[cedis]) if cedis else 0
        cedis_disp = max(0.0, e_cedis - reserva_cedis)
        vd_red = sum(f["vd"] * f["abre"] for f in filas.values())   # venta por SEMANA de toda la red
        if vd_red <= 0 and not any(f["recibido"] for f in filas.values()):
            continue

        # Faltantes: se pide cuando le alcanza menos de la mitad de la cobertura objetivo
        faltas = []
        for t, f in filas.items():
            if f["vd"] > 0 and f["existencia"] < f["objetivo"] and (f["cobertura"] or 0) < f["cob_t"] / 2:
                faltas.append([t, f["objetivo"] - _redondo(f["existencia"]) if f["existencia"] else f["objetivo"]])
        # Sobrantes: sucursal que no lo vende (lo tiene parado) o que tiene más de 3 veces la cobertura
        sobra = {}
        for t, f in filas.items():
            e = int(math.floor(f["existencia"]))
            if e <= 0:
                continue
            if f["vendido"] <= 0:
                sobra[t] = {"cant": e, "motivo": (f"casi no lo vende (solo en {f['dias_con_venta']} semana(s) del periodo)" if f["vendido_real"] > 0
                                                  else f"no vendió ninguna en {dias} días")}
            elif f["cobertura"] and f["cobertura"] > f["cob_t"] * 3:
                extra = e - 2 * f["objetivo"]
                if extra > 0:
                    sobra[t] = {"cant": extra, "motivo": f"le alcanza para {_fmt_dias(f['cobertura'])}"}
        faltas.sort(key=lambda x: -filas[x[0]]["vd"])
        cedis_queda = cedis_disp
        sin_cubrir = 0
        for t, falta in faltas:
            f = filas[t]
            porque = (f"vende {f['vd']:.1f} por día hábil ({f['vendido']:,.0f} en {f['habiles']} días que abrió"
                      + (f", sin contar ventas atípicas: en total vendió {f['vendido_real']:,.0f}" if f["vendido_real"] - f["vendido"] >= 1 else "")
                      + f") y tiene {f['existencia']:,.0f}: le alcanza {_fmt_dias(f['cobertura'])}")
            if f["traspasos"]:
                porque += f"; pidió {f['traspasos']} traspaso(s) a otras sucursales ({f['recibido']:,.0f} pzas)"
            for o in sorted(sobra, key=lambda x: (filas[x]["vendido"] > 0, filas[x]["vd"])):
                if falta <= 0:
                    break
                q = min(falta, sobra[o]["cant"])
                if q <= 0:
                    continue
                entre.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "origen": nom(o), "destino": nom(t),
                              "cantidad": q, "motivo_origen": f"En {nom(o)} {sobra[o]['motivo']} (tiene {filas[o]['existencia']:,.0f}).",
                              "motivo_destino": f"En {nom(t)} {porque}.", "vd_destino": f["vd"]})
                sobra[o]["cant"] -= q
                falta -= q
            if falta > 0 and cedis_queda >= 1:
                q = int(min(falta, math.floor(cedis_queda)))
                if q > 0:
                    de_cedis.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "destino": nom(t), "cantidad": q,
                                     "cedis_tiene": e_cedis, "motivo": f"En {nom(t)} {porque}.", "vd_destino": f["vd"],
                                     "completo": q >= falta})
                    cedis_queda -= q
                    falta -= q
            if falta > 0:
                sin_cubrir += falta

        # Compra: lo que no se pudo cubrir + dejar a CEDIS con cobertura para la red
        meta_cedis = _redondo(vd_red * semanas)
        resurtir_cedis = max(0, meta_cedis - int(math.floor(cedis_queda))) if cedis else 0
        existencia_red = sum(f["existencia"] for f in filas.values()) + e_cedis
        cob_red = existencia_red / vd_red if vd_red > 0 else None          # en semanas
        if (sin_cubrir > 0 or (cob_red is not None and cob_red < semanas / 2)) and vd_red > 0:
            total = sin_cubrir + resurtir_cedis
            if total > 0:
                quien = ", ".join(f"{nom(t)} {filas[t]['vd'] * filas[t]['abre']:.1f}/semana" for t in sorted(filas, key=lambda x: -filas[x]["vd"] * filas[x]["abre"]) if filas[t]["vd"] > 0)
                comprar.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "vd_red": vd_red,
                                "existencia_red": existencia_red, "cedis": e_cedis, "cobertura_red": cob_red,
                                "para_sucursales": sin_cubrir, "para_cedis": resurtir_cedis, "comprar": total,
                                "motivo": (f"Entre todas venden {vd_red:.1f} por semana; hay {existencia_red:,.0f} en total "
                                           f"(CEDIS {e_cedis:,.0f}), alcanza {_fmt_sem(cob_red)}. "
                                           + (f"A las sucursales les faltan {sin_cubrir} que ni CEDIS ni otra sucursal pueden cubrir. " if sin_cubrir else "")
                                           + f"Quién lo vende: {quien}.")})

        # Traspasos: piden seguido y sí venden / piden y no venden
        for t, f in filas.items():
            r = rec_por.get((t, a))
            if not r:
                continue
            origenes = ", ".join(f"{nom(o) if o else 'otro almacén'} {u:,.0f}" for o, u in sorted(r["origenes"].items(), key=lambda kv: -kv[1]))
            de_sucursal = r["u"]
            if r["n"] >= min_traspasos and f["vendido_real"] >= 0.6 * r["u"] and not f["esporadica"]:
                rec = f"Dejarle un mínimo de {max(f['objetivo'], 1)} pzas para que no tenga que pedir"
                if e_cedis > 0:
                    rec += f"; se lo están pasando otras sucursales ({de_sucursal:,.0f}) y CEDIS tiene {e_cedis:,.0f}: que lo mande CEDIS"
                elif e_cedis <= 0:
                    rec += "; CEDIS no tiene: incluirlo en la compra"
                frecuentes.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "sucursal": nom(t), "traspasos": r["n"],
                                   "recibido": r["u"], "vendido": f["vendido_real"], "existencia": f["existencia"], "de_donde": origenes,
                                   "recomendacion": rec + "."})
            elif r["u"] >= 2 and f["vendido_real"] < 0.3 * r["u"]:
                mejor = max((x for x in filas if x != t), key=lambda x: filas[x]["vd"], default=None)
                # Solo se sugiere pasarlo a otra sucursal si ahí de verdad se vende (al menos 5 en la cobertura).
                destino_reg = (f"pasar lo que tiene a {nom(mejor)} (vende {filas[mejor]['vd'] * filas[mejor]['abre']:.1f} por semana)"
                               if mejor and filas[mejor]["vd"] * filas[mejor]["cob_t"] >= 5 else "regresarlo a CEDIS")
                no_vende.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "sucursal": nom(t), "traspasos": r["n"],
                                 "recibido": r["u"], "vendido": f["vendido_real"], "existencia": f["existencia"], "de_donde": origenes,
                                 "recomendacion": f"No mandarle más. Le llegaron {r['u']:,.0f} en {r['n']} traspaso(s) y vendió {f['vendido_real']:,.0f}"
                                                  + (f"; tiene {f['existencia']:,.0f}: {destino_reg}." if f["existencia"] >= 1 else ".")})

        detalle.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "vd_red": vd_red, "cedis": e_cedis,
                        "sucursales": {nom(t): {k: (round(v, 2) if isinstance(v, float) else v) for k, v in f.items()} for t, f in filas.items()}})

    # Parado: existencia en la sucursal sin ninguna venta en el periodo y que tampoco se vende en otra
    for (alm, a), e in existencias.items():
        if alm in tiendas and e >= 1 and a in info and incluir(a):
            v = ventas.get((alm, a))
            if v and v["u"] > 0:
                continue
            red = sum(max(0.0, ventas.get((t, a), {"u": 0})["u"]) for t in tiendas)
            if red <= 0:
                parados.append({"articulo_id": a, "clave": info[a]["clave"], "articulo": info[a]["nombre"], "sucursal": nom(alm), "existencia": e,
                                "recomendacion": f"No se vendió en ninguna sucursal en {dias} días: no comprar; valorar promoción o regresarlo a CEDIS."})

    comprar.sort(key=lambda x: -x["vd_red"])
    de_cedis.sort(key=lambda x: (x["destino"], -x["vd_destino"]))
    entre.sort(key=lambda x: (x["destino"], -x["vd_destino"]))
    frecuentes.sort(key=lambda x: -x["traspasos"])
    no_vende.sort(key=lambda x: -x["recibido"])
    parados.sort(key=lambda x: (x["sucursal"], -x["existencia"]))
    atipicas.sort(key=lambda x: (x["sucursal"], -x["piezas"]))
    return {"comprar": comprar, "de_cedis": de_cedis, "entre_sucursales": entre, "traspaso_frecuente": frecuentes,
            "traspaso_no_vende": no_vende, "parado": parados, "atipicas": atipicas, "detalle": detalle}


_CACHE = {}
_CACHE_MIN = 20


def _leer_microsip(config, desde, hasta, diagnostico):
    """Lo pesado (ventas de hasta 1 año, existencias, traspasos, artículos) se guarda 20 min: cambiar las semanas,
    las sucursales o bajar el PDF/Excel ya no vuelve a leer Microsip."""
    import time
    clave = (config.get("microsip_host"), config.get("microsip_ruta_db"), desde, hasta, bool(diagnostico))
    hit = _CACHE.get(clave)
    if hit and time.time() - hit[0] < _CACHE_MIN * 60:
        return hit[1]
    for k in [k for k, v in _CACHE.items() if time.time() - v[0] >= _CACHE_MIN * 60]:
        _CACHE.pop(k, None)
    diag = {}
    con = _conectar(config)
    try:
        cur = con.cursor()
        cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")
        crudos = {i: (_t(n) or "") for i, n in cur.fetchall()}
        ventas, abiertos_sets = _ventas(cur, desde, hasta, hasta - timedelta(days=29), diag, diagnostico)
        existencias = _existencias(cur)
        traspasos = _traspasos(cur, desde, hasta, diag)
        ids = {a for (_, a) in ventas} | {t["articulo"] for t in traspasos} | {a for (_, a) in existencias}
        info = _articulos(cur, ids)
    finally:
        con.close()
    datos = {"crudos": crudos, "ventas": ventas, "abiertos": abiertos_sets, "existencias": existencias, "traspasos": traspasos, "info": info, "diag": diag}
    _CACHE[clave] = (time.time(), datos)
    return datos


def reporte(config, dias=365, cobertura=None, tiendas=None, cedis=None, texto=None, lineas=None, hasta=None, min_traspasos=3,
            diagnostico=False, ignorar_atipicas=True, semanas=None):
    """dias = días de venta a analizar (hasta 1 año). semanas = para cuántas semanas (de días hábiles) surtir;
    si no viene, se usa cobertura (días naturales) / 7."""
    dias = max(7, min(int(dias or 365), 366))
    if semanas is None:
        semanas = (int(cobertura) / 7.0) if cobertura else 1.0
    semanas = max(0.5, min(float(semanas), 26.0))
    hasta = hasta or date.today()
    desde = hasta - timedelta(days=dias - 1)
    datos = _leer_microsip(config, desde, hasta, diagnostico)
    crudos, ventas, existencias, traspasos, info, diag = (datos[k] for k in ("crudos", "ventas", "existencias", "traspasos", "info", "diag"))
    nombres = {i: nombre_corto(n) for i, n in crudos.items()}
    if cedis is None:
        cedis = next((i for i, n in crudos.items() if ES_CEDIS.search(n)), None)
    if cedis:
        nombres[cedis] = "CEDIS" if "CEDIS" in crudos.get(cedis, "").upper() else f"CEDIS ({crudos.get(cedis) or cedis})"
    if not tiendas:
        con_venta = {alm for (alm, _), v in ventas.items() if v["u"] > 0}
        tiendas = sorted(a for a in con_venta if a != cedis and a != ALMACEN_TRANSITO_ID and not NO_TIENDA.search(crudos.get(a, "")))
    res = calcular(ventas, existencias, traspasos, info, nombres, tiendas, cedis, dias, semanas, 30, texto, lineas, min_traspasos,
                   ignorar_atipicas, hasta, datos["abiertos"])
    abiertos = dias_abiertos(datos["abiertos"])
    por_sem = habiles_por_semana(datos["abiertos"], hasta)
    res.update({
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": dias, "semanas": semanas, "cobertura": round(semanas * 7),
        "dias_habiles": [{"sucursal": nombres.get(t, str(t)), "dias_que_abrio": abiertos.get(t, 0),
                          "por_semana": round(por_sem.get(t, 0), 1)} for t in tiendas],
        "tiendas": [{"id": t, "nombre": nombres.get(t, str(t))} for t in tiendas], "cedis": {"id": cedis, "nombre": nombres.get(cedis, "")} if cedis else None,
        "texto": texto or "", "diagnostico": diag, "ignorar_atipicas": ignorar_atipicas,
        "resumen": {"comprar": len(res["comprar"]), "piezas_comprar": sum(x["comprar"] for x in res["comprar"]),
                    "de_cedis": len(res["de_cedis"]), "piezas_de_cedis": sum(x["cantidad"] for x in res["de_cedis"]),
                    "entre_sucursales": len(res["entre_sucursales"]), "piezas_entre": sum(x["cantidad"] for x in res["entre_sucursales"]),
                    "traspaso_frecuente": len(res["traspaso_frecuente"]), "traspaso_no_vende": len(res["traspaso_no_vende"]),
                    "parado": len(res["parado"]), "atipicas": len(res["atipicas"]), "articulos": len(res["detalle"])},
    })
    return res


# ---------------------------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------------------------
SECCIONES = [
    ("entre_sucursales", "1. Pasar de una sucursal a otra",
     "Primero se aprovecha lo que está parado: la sucursal que no lo vende (o le sobra mucho) se lo pasa a la que sí lo vende y le falta.",
     [("Artículo", "articulo", 0.25), ("Clave", "clave", 0.09), ("De", "origen", 0.09), ("A", "destino", 0.09), ("Cant.", "cantidad", 0.05),
      ("Por qué", "_porque", 0.43)]),
    ("de_cedis", "2. Que CEDIS mande",
     "Lo que falta en cada sucursal y ninguna otra sucursal tiene de sobra, pero CEDIS sí tiene.",
     [("Sucursal", "destino", 0.09), ("Artículo", "articulo", 0.27), ("Clave", "clave", 0.09), ("Mandar", "cantidad", 0.06),
      ("CEDIS tiene", "cedis_tiene", 0.07), ("Por qué", "motivo", 0.42)]),
    ("comprar", "3. Comprar",
     "Lo que ni CEDIS ni otra sucursal pueden cubrir, más lo necesario para que CEDIS quede con la cobertura de toda la red.",
     [("Artículo", "articulo", 0.22), ("Clave", "clave", 0.08), ("Venta por semana (todas)", "vd_red", 0.075), ("Hay en total", "existencia_red", 0.07),
      ("Para sucursales", "para_sucursales", 0.08), ("Para CEDIS", "para_cedis", 0.07), ("Comprar", "comprar", 0.075), ("Por qué", "motivo", 0.33)]),
    ("traspaso_frecuente", "4. Piden traspaso seguido y sí lo venden",
     "Traspasos entre sucursales (lo que manda CEDIS no cuenta). Conviene dejarles un mínimo fijo y que lo mande CEDIS en vez de otra sucursal.",
     [("Sucursal", "sucursal", 0.09), ("Artículo", "articulo", 0.25), ("Traspasos", "traspasos", 0.06), ("Recibió", "recibido", 0.06),
      ("Vendió", "vendido", 0.06), ("Tiene", "existencia", 0.05), ("De dónde vino", "de_donde", 0.13), ("Recomendación", "recomendacion", 0.30)]),
    ("traspaso_no_vende", "5. Piden traspaso pero NO lo venden",
     "Les llega mercancía por traspaso de otras sucursales (lo que manda CEDIS no cuenta) y casi no la venden: no pedir más y mover lo que tienen a donde sí se vende.",
     [("Sucursal", "sucursal", 0.09), ("Artículo", "articulo", 0.25), ("Traspasos", "traspasos", 0.06), ("Recibió", "recibido", 0.06),
      ("Vendió", "vendido", 0.06), ("Tiene", "existencia", 0.05), ("De dónde vino", "de_donde", 0.13), ("Recomendación", "recomendacion", 0.30)]),
    ("parado", "6. Mercancía parada (no se vende en ninguna sucursal)",
     "Tiene existencia y no se vendió en ninguna sucursal en todo el periodo: no comprar.",
     [("Sucursal", "sucursal", 0.12), ("Artículo", "articulo", 0.40), ("Clave", "clave", 0.12), ("Existencia", "existencia", 0.08),
      ("Recomendación", "recomendacion", 0.28)]),
    ("atipicas", "7. Ventas atípicas que no se tomaron en cuenta",
     "Ventas esporádicas (vendió en menos de 3 semanas del periodo, ej. una sola venta grande) o semanas que vendió mucho más de lo normal. "
     "No se usan para calcular la venta diaria, para no surtir ni comprar de más.",
     [("Sucursal", "sucursal", 0.10), ("Artículo", "articulo", 0.30), ("Clave", "clave", 0.09), ("Semana del", "fecha", 0.08),
      ("Piezas esa semana", "piezas", 0.08), ("Se tomaron", "se_tomaron", 0.07), ("Por qué", "motivo", 0.28)]),
]


def _porque(x):
    return f"{x['motivo_origen']} {x['motivo_destino']}"


def _encabezado(r):
    tiendas = ", ".join(t["nombre"] for t in r["tiendas"])
    sem = r.get("semanas") or (r.get("cobertura", 7) / 7)
    return (f"Ventas del {r['desde']} al {r['hasta']} ({r['dias']} días) · Surtir para: {_fmt_sem(sem)} de días hábiles · "
            f"Sucursales: {tiendas} · CEDIS: {(r.get('cedis') or {}).get('nombre') or 'sin CEDIS'}"
            + (f" · Artículos con: {r['texto']}" if r.get("texto") else ""))


def _num(v):
    if isinstance(v, float):
        return f"{v:,.1f}" if not float(v).is_integer() else f"{v:,.0f}"
    return f"{v:,}" if isinstance(v, int) else (v or "")


def pdf(r, empresa_nombre="", max_filas=400):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    from io import BytesIO
    from xml.sax.saxutils import escape

    ROJO = colors.HexColor("#D8192F"); GRIS = colors.HexColor("#5F6368"); LINEA = colors.HexColor("#DDDDDD"); SUAVE = colors.HexColor("#F5F5F5")
    p = ParagraphStyle("p", fontName="Helvetica", fontSize=7.6, leading=9.4)
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=ROJO, spaceBefore=8, spaceAfter=3)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.8, leading=11, textColor=GRIS)
    W = landscape(letter)[0] - 0.9 * inch
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=0.45 * inch, rightMargin=0.45 * inch,
                            topMargin=0.45 * inch, bottomMargin=0.45 * inch, title="Sugerencia de compras y traspasos")
    s = r["resumen"]
    story = [Paragraph(f"Sugerencia de compras y traspasos{' · ' + escape(empresa_nombre) if empresa_nombre else ''}", h1),
             Paragraph(escape(_encabezado(r)), sub), Spacer(1, 6)]
    tarjetas = [("Pasar entre sucursales", f"{s['entre_sucursales']} movimientos · {s['piezas_entre']:,} pzas"),
                ("Que mande CEDIS", f"{s['de_cedis']} movimientos · {s['piezas_de_cedis']:,} pzas"),
                ("Comprar", f"{s['comprar']} artículos · {s['piezas_comprar']:,} pzas"),
                ("Piden y sí venden", f"{s['traspaso_frecuente']}"), ("Piden y NO venden", f"{s['traspaso_no_vende']}"),
                ("Parado", f"{s['parado']}")]
    t = Table([[Paragraph(f"<font color='#5F6368' size='7.5'>{a}</font><br/><b>{b}</b>", p) for a, b in tarjetas]],
              colWidths=[W / len(tarjetas)] * len(tarjetas))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINEA), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINEA),
                           ("BACKGROUND", (0, 0), (-1, -1), SUAVE), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [t, Spacer(1, 4),
              Paragraph("Cómo se calcula: venta diaria = piezas vendidas (Punto de venta + facturas y remisiones) ÷ días del periodo. "
                        "Todo se mide en días hábiles: los días que cada sucursal abrió (tuvo ventas); domingos, festivos y vacaciones no cuentan. "
                        "A una sucursal le falta cuando su existencia le alcanza para menos de la mitad de lo que se quiere surtir; se le "
                        "pide hasta completarlo. Orden: 1) de otra sucursal que lo tiene parado, 2) de CEDIS, 3) compra.", sub)]
    for clave, titulo, explica, cols in SECCIONES:
        filas = r.get(clave) or []
        story += [Paragraph(f"{titulo} ({len(filas)})", h2), Paragraph(escape(explica), sub), Spacer(1, 3)]
        if not filas:
            story.append(Paragraph("— Nada que sugerir —", p)); continue
        datos = [[Paragraph(f"<font color='white'><b>{escape(c)}</b></font>", p) for c, _, _ in cols]]
        for f in filas[:max_filas]:
            fila = []
            for _, k, _ in cols:
                v = _porque(f) if k == "_porque" else f.get(k)
                fila.append(Paragraph(escape(str(_num(v))), p))
            datos.append(fila)
        tb = Table(datos, colWidths=[W * a for _, _, a in cols], repeatRows=1)
        tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ROJO), ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SUAVE]),
                                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(tb)
        if len(filas) > max_filas:
            story.append(Paragraph(f"… y {len(filas) - max_filas} más (vienen completas en el Excel).", sub))
    doc.build(story)
    return buf.getvalue()


def excel(r, empresa_nombre=""):
    """Excel en modo 'write_only' (se escribe fila por fila): con un año de ventas el modo normal llegaba a ~270 MB de RAM
    y tumbaba el servidor; así usa una fracción y es más rápido."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(write_only=True)
    A = "Arial"
    cab = PatternFill("solid", fgColor="D8192F")
    F_TIT = Font(name=A, size=13, bold=True); F_SUB = Font(name=A, size=9, color="595959"); F_EXP = Font(name=A, size=9, italic=True)
    F_CAB = Font(name=A, bold=True, color="FFFFFF"); F_N = Font(name=A, size=9)
    AL_CAB = Alignment(horizontal="center", wrap_text=True); AL_N = Alignment(wrap_text=True, vertical="top")

    def celda(ws, v, font, fill=None, al=None):
        c = WriteOnlyCell(ws, value=v)
        c.font = font
        if fill is not None:
            c.fill = fill
        if al is not None:
            c.alignment = al
        return c

    for clave, titulo, explica, cols in SECCIONES:
        ws = wb.create_sheet(titulo.split(". ", 1)[-1][:31])
        for i, (_, _, ancho) in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(9, int(ancho * 170))
        ws.freeze_panes = "A6"
        ws.append([celda(ws, titulo, F_TIT)])
        ws.append([celda(ws, f"{empresa_nombre} · {_encabezado(r)}", F_SUB)])
        ws.append([celda(ws, explica, F_EXP)])
        ws.append([])
        ws.append([celda(ws, c, F_CAB, cab, AL_CAB) for c, _, _ in cols])
        for f in r.get(clave) or []:
            fila = []
            for _, k, _ in cols:
                v = _porque(f) if k == "_porque" else f.get(k)
                if isinstance(v, float):
                    v = round(v, 2)
                fila.append(celda(ws, v, F_N, al=AL_N))
            ws.append(fila)
    # Detalle por artículo y sucursal
    ws = wb.create_sheet("Detalle por sucursal")
    hdr = ["Artículo", "Clave", "Sucursal", "Vendió (sin atípicas)", "Venta por día hábil", "Semanas con venta", "Últimos 30 días", "Existencia",
           "Le alcanza (días hábiles)",
           "Objetivo", "Traspasos recibidos", "Pzas recibidas", "CEDIS tiene", "Vendió (todo)"]
    for i in range(1, len(hdr) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 40 if i == 1 else 13
    ws.freeze_panes = "A5"
    n = sum(len(d["sucursales"]) for d in r.get("detalle") or [])
    ws.auto_filter.ref = f"A4:N{max(4 + n, 4)}"
    ws.append([celda(ws, "Detalle por artículo y sucursal", F_TIT)])
    ws.append([celda(ws, _encabezado(r), F_SUB)])
    ws.append([])
    ws.append([celda(ws, c, F_CAB, cab, AL_CAB) for c in hdr])
    for d in r.get("detalle") or []:
        for suc, f in d["sucursales"].items():
            ws.append([d["articulo"], d["clave"], suc, f["vendido"], round(f["vd"], 2), f["dias_con_venta"], f["reciente"], f["existencia"],
                       (None if f["cobertura"] is None else round(min(f["cobertura"], 999), 1)), f["objetivo"], f["traspasos"], f["recibido"],
                       d["cedis"], f.get("vendido_real")])
    out = BytesIO(); wb.save(out)
    return out.getvalue()
