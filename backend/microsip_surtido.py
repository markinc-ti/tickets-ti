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
import gc
import math
import re
from array import array
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


_LUNES = {}


def _lunes(n):
    n = int(n)
    f = _LUNES.get(n)
    if f is None:
        f = _LUNES[n] = LUNES_BASE + timedelta(days=n * 7)
    return f


def por_semana(v):
    """[(lunes, unidades)] ordenado, de una venta compacta (ver _compactar)."""
    if not v or not v.get("sem"):
        return []
    return [(_lunes(i), u) for i, u in zip(v["sem"], v["uds"])]


def _compactar(v):
    """La venta de un año son cientos de miles de semanas: guardarlas en dicts/sets con fechas usaba ~170 MB y tumbaba el
    servidor (Render, 512 MB). Se guardan en arreglos (array) de semanas y unidades: ~10 bytes por semana."""
    for k, x in list(v.items()):
        items = sorted(x["por_dia"].items())
        v[k] = {"u": x["u"], "u30": x["u30"], "n_dias": len(x["dias"]),
                "sem": array("i", [(f - LUNES_BASE).days // 7 for f, _ in items]), "uds": array("d", [u for _, u in items])}
    return v


def liberar_memoria():
    """Después de un reporte grande: recoger basura y devolver al sistema la memoria libre (glibc no la regresa sola)."""
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


try:  # Menos 'arenas' de malloc por hilo: cada petición corre en otro hilo y cada arena se queda con memoria.
    import ctypes as _ct
    _ct.CDLL("libc.so.6").mallopt(-8, 2)   # M_ARENA_MAX = 2
except Exception:
    pass


def _ventas(cur, desde, hasta, corte_reciente, diag, detalle_pv=False):
    """{(almacen, articulo): {"u", "u30", "n_dias", "sem": array de semanas, "uds": array de unidades}} (ver _compactar).
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
    return _compactar(v), abiertos


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


def _datos_compra(cur, ids, hasta):
    """Para las órdenes de compra: marca y proveedor (clasificadores MARCA / PROVEEDOR del artículo), la última compra
    (proveedor, costo unitario sin IVA y fecha; compras y recepciones sin cancelar de los últimos 2 años) y lo que ya
    está pedido en órdenes de compra pendientes de recibir (de los últimos 6 meses). Si algo falla, regresa lo que pudo."""
    ids = set(ids)
    out = {"marca": {}, "prov_clasif": {}, "ultima": {}, "pedido": {}, "proveedores": {}, "errores": {}}
    try:
        cur.execute("SELECT CLASIFICADOR_ID, NOMBRE FROM CLASIFICADORES_CAT WHERE TIPO_OBJETO = 'A'")
        cl = {cid: (_t(n) or "").upper() for cid, n in cur.fetchall()}
        c_marca = next((c for c, n in cl.items() if n == "MARCA"), None) or next((c for c, n in cl.items() if "MARCA" in n), None)
        c_prov = next((c for c, n in cl.items() if n == "PROVEEDOR"), None)
        for cid, clave in ((c_marca, "marca"), (c_prov, "prov_clasif")):
            if not cid:
                continue
            cur.execute("""SELECT e.ELEMENTO_ID, v.VALOR FROM ELEMENTOS_CAT_CLASIF e
                           JOIN CLASIFICADORES_CAT_VALORES v ON v.VALOR_CLASIF_ID = e.VALOR_CLASIF_ID
                           WHERE v.CLASIFICADOR_ID = ?""", (cid,))
            for a, v in cur.fetchall():
                if a in ids and _t(v):
                    out[clave][a] = _t(v)
    except Exception as e:
        out["errores"]["clasificadores"] = str(e)[-200:]
    try:
        cur.execute("""SELECT d.ARTICULO_ID, c.FECHA, c.DOCTO_CM_ID, c.PROVEEDOR_ID, d.PRECIO_UNITARIO, d.PCTJE_DSCTO, d.CONTENIDO_UMED,
                              c.TIPO_CAMBIO, c.FOLIO
                       FROM DOCTOS_CM c JOIN DOCTOS_CM_DET d ON d.DOCTO_CM_ID = c.DOCTO_CM_ID
                       WHERE c.TIPO_DOCTO IN ('C', 'R') AND c.ESTATUS <> 'C' AND c.FECHA >= ?""", (hasta - timedelta(days=730),))
        for a, f, did, prov, pu, dsc, cont, tc, folio in cur.fetchall():
            if a not in ids or not pu:
                continue
            u = out["ultima"].get(a)
            if u and (u["fecha"], u["_id"]) >= (f, did):
                continue
            costo = float(pu) * (1 - float(dsc or 0) / 100.0) * float(tc or 1)
            if cont and float(cont) > 1:
                costo /= float(cont)
            out["ultima"][a] = {"fecha": f, "_id": did, "proveedor_id": prov, "costo": round(costo, 4), "folio": _t(folio)}
    except Exception as e:
        out["errores"]["ultima_compra"] = str(e)[-200:]
    try:
        cur.execute("""SELECT d.ARTICULO_ID, c.FOLIO, d.UNIDADES - COALESCE(d.UNIDADES_REC_DEV, 0)
                       FROM DOCTOS_CM c JOIN DOCTOS_CM_DET d ON d.DOCTO_CM_ID = c.DOCTO_CM_ID
                       WHERE c.TIPO_DOCTO = 'O' AND c.ESTATUS IN ('N', 'P') AND c.FECHA >= ?""", (hasta - timedelta(days=180),))
        for a, folio, pend in cur.fetchall():
            if a not in ids or not pend or float(pend) <= 0:
                continue
            x = out["pedido"].setdefault(a, {"u": 0.0, "folios": []})
            x["u"] += float(pend)
            if _t(folio) and _t(folio) not in x["folios"]:
                x["folios"].append(_t(folio))
    except Exception as e:
        out["errores"]["ordenes_pendientes"] = str(e)[-200:]
    try:
        pids = {u["proveedor_id"] for u in out["ultima"].values() if u["proveedor_id"]}
        cols = _cols(cur, "PROVEEDORES")
        sel = ", ".join(c if c in cols else "NULL" for c in ("NOMBRE", "CONTACTO1", "TELEFONO1", "EMAIL", "ORDEN_MINIMA"))
        for lote in _lotes(pids):
            cur.execute(f"SELECT PROVEEDOR_ID, {sel} FROM PROVEEDORES WHERE PROVEEDOR_ID IN ({','.join('?' * len(lote))})", tuple(lote))
            for pid, nom, cont, tel, mail, minimo in cur.fetchall():
                out["proveedores"][pid] = {"nombre": _t(nom) or f"Proveedor {pid}", "contacto": _t(cont) or "", "telefono": _t(tel) or "",
                                           "email": _t(mail) or "", "orden_minima": float(minimo or 0)}
    except Exception as e:
        out["errores"]["proveedores"] = str(e)[-200:]
    return out


def agregar_datos_compra(comprar, dc):
    """Pone a cada artículo a comprar su marca, proveedor, costo e importe, y le resta lo que ya está pedido en
    órdenes de compra pendientes de recibir (para no pedirlo dos veces)."""
    for x in comprar:
        a = x["articulo_id"]
        u = dc["ultima"].get(a) or {}
        prov = dc["proveedores"].get(u.get("proveedor_id")) or {}
        ped = dc["pedido"].get(a) or {"u": 0.0, "folios": []}
        sugerido = x["comprar"]
        ya = int(math.floor(ped["u"] + 1e-9))
        x["sugerido"] = sugerido
        x["ya_pedido"] = ya
        x["oc_pendientes"] = ", ".join(ped["folios"])
        x["comprar"] = max(0, sugerido - ya)
        x["marca"] = dc["marca"].get(a) or "SIN MARCA"
        x["proveedor"] = prov.get("nombre") or dc["prov_clasif"].get(a) or "SIN PROVEEDOR"
        x["proveedor_id"] = u.get("proveedor_id") if prov else None
        x["costo"] = u.get("costo")
        x["ultima_compra"] = u["fecha"].isoformat() if u.get("fecha") else ""
        x["importe"] = round(x["comprar"] * x["costo"], 2) if x["costo"] is not None else None
        if ya:
            x["motivo"] += (f" Ya hay {ya} pedido(s) en OC pendiente ({x['oc_pendientes']}): se restan." if x["comprar"]
                            else f" Ya está pedido en OC pendiente ({x['oc_pendientes']}): no comprar más.")
    comprar.sort(key=lambda x: (x["comprar"] <= 0, -x["vd_red"]))
    return comprar


IVA = 0.16


def ordenes_por_marca(r, marca=None):
    """Una orden de compra sugerida por marca con lo que hay que comprar (cantidad > 0)."""
    grupos = {}
    for x in r.get("comprar") or []:
        if x.get("comprar", 0) <= 0:
            continue
        if marca and x.get("marca") != marca:
            continue
        grupos.setdefault(x.get("marca") or "SIN MARCA", []).append(x)
    provs = r.get("_proveedores") or {}
    ordenes = []
    for m, lineas in grupos.items():
        peso = {}
        for x in lineas:
            k = x.get("proveedor") or "SIN PROVEEDOR"
            peso[k] = peso.get(k, 0) + (x.get("importe") or 0) + 0.001
        reales = {k: v for k, v in peso.items() if k != "SIN PROVEEDOR"}
        prov = max(reales or peso, key=(reales or peso).get)
        pid = next((x.get("proveedor_id") for x in lineas if x.get("proveedor") == prov and x.get("proveedor_id")), None)
        subtotal = round(sum(x.get("importe") or 0 for x in lineas), 2)
        lineas = sorted(lineas, key=lambda x: x["articulo"])
        ordenes.append({"marca": m, "proveedor": prov, "proveedor_info": provs.get(pid) or provs.get(str(pid)) or {},
                        "otros_proveedores": sorted(k for k in peso if k not in (prov, "SIN PROVEEDOR")),
                        "lineas": [{"clave": x["clave"], "articulo": x["articulo"], "cantidad": x["comprar"], "costo": x.get("costo"),
                                    "importe": x.get("importe"), "proveedor": x.get("proveedor"), "ultima_compra": x.get("ultima_compra"),
                                    "ya_pedido": x.get("ya_pedido", 0)} for x in lineas],
                        "articulos": len(lineas), "piezas": sum(x["comprar"] for x in lineas), "sin_costo": sum(1 for x in lineas if x.get("costo") is None),
                        "subtotal": subtotal, "iva": round(subtotal * IVA, 2), "total": round(subtotal * (1 + IVA), 2)})
    ordenes.sort(key=lambda o: (o["marca"] == "SIN MARCA", -o["subtotal"], o["marca"]))
    fecha = (r.get("hasta") or date.today().isoformat()).replace("-", "")
    for n, o in enumerate(ordenes, 1):
        o["folio"] = f"SUG-{fecha}-{n:03d}"
    return ordenes


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
    return "1 semana" if abs(s - 1) < 0.05 else f"{s:.1f} semanas".replace(".0 ", " ")


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
    semanas = por_semana(v)
    dias_pos = sorted(u for _, u in semanas if u > 0)
    if len(dias_pos) < MIN_DIAS_VENTA:
        recortes = [(f, u, TOPE_ESPORADICA, 0) for f, u in semanas if u > TOPE_ESPORADICA]
        ajustado = sum(min(u, TOPE_ESPORADICA) for u in dias_pos)
        return ajustado, bool(recortes), recortes
    n = len(dias_pos)
    mediana = dias_pos[n // 2] if n % 2 else (dias_pos[n // 2 - 1] + dias_pos[n // 2]) / 2
    tope = max(FACTOR_ATIPICO * mediana, mediana + MARGEN_ATIPICO)
    ajustado, atipicos = 0.0, []
    for f, u in semanas:
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
            v = ventas.get((t, a), {"u": 0.0, "n_dias": 0, "u30": 0.0})
            u_real = max(0.0, v["u"])
            u, esporadica, atip = ajustar_venta(v, ignorar_atipicas)
            for fch, pzs, tope, med in atip:
                atipicas.append({"articulo_id": a, "clave": i["clave"], "articulo": i["nombre"], "sucursal": nom(t),
                                 "fecha": fch.isoformat() if hasattr(fch, "isoformat") else str(fch), "piezas": pzs,
                                 "se_tomaron": round(tope, 1),
                                 "motivo": (f"Solo vendió en {v['n_dias']} semana(s) del periodo (venta esporádica): de esa semana se tomaron {tope:,.0f} pzas."
                                            if esporadica else f"Esa semana vendió {pzs:,.0f} y en una semana normal vende {med:,.0f}: solo se tomaron {tope:,.0f}.")})
            vd = u / habiles[t]                     # venta por día hábil
            cob_t = semanas * abre[t]                # días hábiles a cubrir en esta sucursal
            e = max(0.0, existencias.get((t, a), 0.0))
            obj = _redondo(vd * cob_t) if u > 0 else 0
            cob = (e / vd) if vd > 0 else (999 if e > 0 else None)
            filas[t] = {"cob_t": cob_t, "habiles": habiles[t], "abre": abre[t], "vendido": u, "vendido_real": u_real, "esporadica": esporadica, "vd": vd, "dias_con_venta": v["n_dias"],
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
        compra = _datos_compra(cur, ids, hasta)
    finally:
        con.close()
    datos = {"crudos": crudos, "ventas": ventas, "abiertos": abiertos_sets, "existencias": existencias, "traspasos": traspasos, "info": info, "diag": diag,
             "compra": compra}
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
    dc = datos.get("compra") or {"marca": {}, "prov_clasif": {}, "ultima": {}, "pedido": {}, "proveedores": {}, "errores": {}}
    agregar_datos_compra(res["comprar"], dc)
    res["_proveedores"] = dc["proveedores"]
    if dc.get("errores"):
        diag["datos_compra"] = dc["errores"]
    abiertos = dias_abiertos(datos["abiertos"])
    por_sem = habiles_por_semana(datos["abiertos"], hasta)
    res.update({
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": dias, "semanas": semanas, "cobertura": round(semanas * 7),
        "dias_habiles": [{"sucursal": nombres.get(t, str(t)), "dias_que_abrio": abiertos.get(t, 0),
                          "por_semana": round(por_sem.get(t, 0), 1)} for t in tiendas],
        "tiendas": [{"id": t, "nombre": nombres.get(t, str(t))} for t in tiendas], "cedis": {"id": cedis, "nombre": nombres.get(cedis, "")} if cedis else None,
        "texto": texto or "", "diagnostico": diag, "ignorar_atipicas": ignorar_atipicas,
        "resumen": {"comprar": sum(1 for x in res["comprar"] if x["comprar"] > 0), "piezas_comprar": sum(x["comprar"] for x in res["comprar"]),
                    "importe_comprar": round(sum(x.get("importe") or 0 for x in res["comprar"]), 2),
                    "ya_pedido": sum(1 for x in res["comprar"] if x.get("ya_pedido")),
                    "de_cedis": len(res["de_cedis"]), "piezas_de_cedis": sum(x["cantidad"] for x in res["de_cedis"]),
                    "entre_sucursales": len(res["entre_sucursales"]), "piezas_entre": sum(x["cantidad"] for x in res["entre_sucursales"]),
                    "traspaso_frecuente": len(res["traspaso_frecuente"]), "traspaso_no_vende": len(res["traspaso_no_vende"]),
                    "parado": len(res["parado"]), "atipicas": len(res["atipicas"]), "articulos": len(res["detalle"])},
    })
    ords = ordenes_por_marca(res)
    res["ordenes"] = [{k: o[k] for k in ("folio", "marca", "proveedor", "articulos", "piezas", "subtotal", "total", "sin_costo")} for o in ords]
    res["resumen"]["ordenes"] = len(ords)
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
     [("Artículo", "articulo", 0.19), ("Clave", "clave", 0.07), ("Marca", "marca", 0.07), ("Venta por semana (todas)", "vd_red", 0.055),
      ("Hay en total", "existencia_red", 0.05), ("Para sucursales", "para_sucursales", 0.055), ("Para CEDIS", "para_cedis", 0.05),
      ("Ya pedido (OC)", "ya_pedido", 0.05), ("Comprar", "comprar", 0.05), ("Costo", "costo", 0.055), ("Importe", "importe", 0.06),
      ("Por qué", "motivo", 0.245)]),
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


# ---------------------------------------------------------------------------------------------
# Órdenes de compra por marca
# ---------------------------------------------------------------------------------------------
def _dinero(v):
    return "—" if v is None else f"${v:,.2f}"


def ordenes_pdf(r, empresa_nombre="", marca=None):
    """Una orden de compra sugerida por marca, cada una en su(s) hoja(s). Con todas las marcas, la primera hoja es el índice."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ords = ordenes_por_marca(r, marca)
    ROJO = colors.HexColor("#D8192F"); GRIS = colors.HexColor("#5F6368"); LINEA = colors.HexColor("#DDDDDD"); SUAVE = colors.HexColor("#F5F5F5")
    p = ParagraphStyle("p", fontName="Helvetica", fontSize=8, leading=9.8)
    pd = ParagraphStyle("pd", parent=p, alignment=2)
    b = ParagraphStyle("b", parent=p, fontName="Helvetica-Bold")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=19)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5, leading=11, textColor=GRIS)
    W = letter[0] - 0.9 * inch
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.45 * inch, rightMargin=0.45 * inch, topMargin=0.45 * inch,
                            bottomMargin=0.5 * inch, title="Órdenes de compra sugeridas por marca")
    hoy = r.get("hasta") or date.today().isoformat()
    base = (f"Sugerencia de compra: ventas del {r.get('desde')} al {r.get('hasta')}, surtir para {_fmt_sem(r.get('semanas') or 1)} de días hábiles. "
            "Ya se restó lo que está pedido en órdenes de compra pendientes de recibir. Costo = última compra en Microsip, sin IVA: confirmar con el proveedor.")

    def tabla(datos, anchos, encabezado=True, zebra=True):
        t = Table(datos, colWidths=anchos, repeatRows=1 if encabezado else 0)
        st = [("GRID", (0, 0), (-1, -1), 0.4, LINEA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        if encabezado:
            st.append(("BACKGROUND", (0, 0), (-1, 0), ROJO))
        if zebra:
            st.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SUAVE]))
        t.setStyle(TableStyle(st))
        return t

    def cab(*cols):
        return [Paragraph(f"<font color='white'><b>{escape(c)}</b></font>", p) for c in cols]

    story = []
    if not ords:
        story = [Paragraph("Órdenes de compra sugeridas", h1), Spacer(1, 8), Paragraph("No hay nada que comprar con estos filtros.", p)]
    elif not marca and len(ords) > 1:
        tot = sum(o["subtotal"] for o in ords)
        story += [Paragraph(f"Órdenes de compra sugeridas por marca{' · ' + escape(empresa_nombre) if empresa_nombre else ''}", h1),
                  Paragraph(escape(f"{len(ords)} órdenes · {sum(o['piezas'] for o in ords):,} piezas · subtotal {_dinero(tot)} + IVA · {hoy}"), sub),
                  Paragraph(escape(base), sub), Spacer(1, 6)]
        datos = [cab("Folio", "Marca", "Proveedor sugerido", "Arts.", "Piezas", "Subtotal", "Total c/IVA")]
        for o in ords:
            datos.append([Paragraph(o["folio"], p), Paragraph(f"<b>{escape(o['marca'])}</b>", p), Paragraph(escape(o["proveedor"]), p),
                          Paragraph(f"{o['articulos']:,}", pd), Paragraph(f"{o['piezas']:,}", pd), Paragraph(_dinero(o["subtotal"]), pd),
                          Paragraph(_dinero(o["total"]), pd)])
        datos.append([Paragraph("", p), Paragraph("<b>TOTAL</b>", p), Paragraph("", p), Paragraph(f"<b>{sum(o['articulos'] for o in ords):,}</b>", pd),
                      Paragraph(f"<b>{sum(o['piezas'] for o in ords):,}</b>", pd), Paragraph(f"<b>{_dinero(tot)}</b>", pd),
                      Paragraph(f"<b>{_dinero(round(tot * (1 + IVA), 2))}</b>", pd)])
        story.append(tabla(datos, [W * a for a in (0.17, 0.17, 0.30, 0.06, 0.08, 0.11, 0.11)]))
        story.append(PageBreak())
    for k, o in enumerate(ords):
        pi = o["proveedor_info"] or {}
        contacto = " · ".join(x for x in (pi.get("contacto"), pi.get("telefono"), pi.get("email")) if x)
        izq = (f"<b>Proveedor sugerido:</b> {escape(o['proveedor'])}" + (f"<br/>{escape(contacto)}" if contacto else "")
               + (f"<br/><font color='#5F6368'>Otros proveedores de esta marca: {escape(', '.join(o['otros_proveedores']))}</font>" if o["otros_proveedores"] else ""))
        der = (f"<b>Folio:</b> {o['folio']}<br/><b>Fecha:</b> {hoy}<br/><b>Marca:</b> {escape(o['marca'])}"
               f"<br/><b>Entregar en:</b> {escape((r.get('cedis') or {}).get('nombre') or 'CEDIS')}")
        story += [Paragraph(f"ORDEN DE COMPRA (SUGERIDA){' · ' + escape(empresa_nombre) if empresa_nombre else ''}", h1), Spacer(1, 4)]
        enc = Table([[Paragraph(izq, p), Paragraph(der, p)]], colWidths=[W * 0.62, W * 0.38])
        enc.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINEA), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINEA), ("BACKGROUND", (0, 0), (-1, -1), SUAVE),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [enc, Spacer(1, 6)]
        datos = [cab("#", "Clave", "Artículo", "Cantidad", "Costo unit.", "Importe")]
        for n, x in enumerate(o["lineas"], 1):
            nota = []
            if x["proveedor"] and x["proveedor"] not in (o["proveedor"], "SIN PROVEEDOR"):
                nota.append(f"última compra a {x['proveedor']}")
            if x["ya_pedido"]:
                nota.append(f"ya pedidas {x['ya_pedido']} en OC pendiente")
            if x["costo"] is None:
                nota.append("sin compra registrada: pedir precio")
            art = escape(x["articulo"]) + (f"<br/><font size='6.5' color='#5F6368'>{escape('; '.join(nota))}</font>" if nota else "")
            datos.append([Paragraph(str(n), p), Paragraph(escape(x["clave"] or ""), p), Paragraph(art, p), Paragraph(f"<b>{x['cantidad']:,}</b>", pd),
                          Paragraph(_dinero(x["costo"]), pd), Paragraph(_dinero(x["importe"]), pd)])
        story.append(tabla(datos, [W * a for a in (0.05, 0.14, 0.47, 0.09, 0.12, 0.13)]))
        tot = [[Paragraph("Piezas", p), Paragraph(f"{o['piezas']:,}", pd)], [Paragraph("Subtotal", p), Paragraph(_dinero(o["subtotal"]), pd)],
               [Paragraph(f"IVA {IVA * 100:.0f}% (estimado)", p), Paragraph(_dinero(o["iva"]), pd)],
               [Paragraph("<b>Total</b>", b), Paragraph(f"<b>{_dinero(o['total'])}</b>", pd)]]
        tt = Table(tot, colWidths=[W * 0.2, W * 0.15], hAlign="RIGHT")
        tt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINEA), ("LINEABOVE", (0, 3), (-1, 3), 0.8, colors.black),
                                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        notas = [base]
        if o["sin_costo"]:
            notas.append(f"{o['sin_costo']} artículo(s) sin compra registrada: el total no los incluye.")
        minimo = pi.get("orden_minima") or 0
        if minimo and o["subtotal"] < minimo:
            notas.append(f"Ojo: el proveedor tiene orden mínima de {_dinero(minimo)} y esta orden suma {_dinero(o['subtotal'])}.")
        firmas = Table([[Paragraph("<br/><br/>_____________________________<br/>Elaboró (Compras)", p),
                         Paragraph("<br/><br/>_____________________________<br/>Autorizó (Dirección)", p)]], colWidths=[W / 2, W / 2])
        story += [Spacer(1, 4), KeepTogether([tt, Spacer(1, 6), Paragraph(escape(" ".join(notas)), sub), Spacer(1, 10), firmas])]
        if k < len(ords) - 1:
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()


def ordenes_excel(r, empresa_nombre="", marca=None):
    """Hoja 'Órdenes' (resumen), 'Todas las líneas' (filtrable) y una hoja por marca lista para mandar al proveedor.
    Importe, subtotal, IVA y total son fórmulas: si cambian una cantidad o un costo, se recalcula."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    ords = ordenes_por_marca(r, marca)
    wb = Workbook(write_only=True)
    A = "Arial"
    ROJO = PatternFill("solid", fgColor="D8192F")
    F_T = Font(name=A, size=13, bold=True); F_S = Font(name=A, size=9, color="595959"); F_C = Font(name=A, bold=True, color="FFFFFF")
    F_N = Font(name=A, size=9); F_B = Font(name=A, size=9, bold=True); F_IN = Font(name=A, size=9, color="0000FF")
    AL = Alignment(wrap_text=True, vertical="top"); AC = Alignment(horizontal="center", wrap_text=True)
    MON = '"$"#,##0.00'; ENT = "#,##0"

    def c(ws, v, f=F_N, fill=None, al=None, fmt=None):
        x = WriteOnlyCell(ws, value=v)
        x.font = f
        if fill is not None:
            x.fill = fill
        if al is not None:
            x.alignment = al
        if fmt:
            x.number_format = fmt
        return x

    def anchos(ws, lst):
        for i, a in enumerate(lst, 1):
            ws.column_dimensions[get_column_letter(i)].width = a

    nota = ("Costo = última compra en Microsip, sin IVA (en azul: se puede cambiar). Ya se restó lo pedido en órdenes de compra pendientes. "
            f"Ventas del {r.get('desde')} al {r.get('hasta')}, surtir para {_fmt_sem(r.get('semanas') or 1)} de días hábiles.")
    # Índice
    ws = wb.create_sheet("Órdenes")
    anchos(ws, [16, 22, 44, 9, 10, 15, 15, 15, 28])
    ws.freeze_panes = "A5"
    ws.append([c(ws, f"Órdenes de compra sugeridas por marca{' · ' + empresa_nombre if empresa_nombre else ''}", F_T)])
    ws.append([c(ws, nota, F_S)])
    ws.append([])
    ws.append([c(ws, h, F_C, ROJO, AC) for h in ("Folio", "Marca", "Proveedor sugerido", "Artículos", "Piezas", "Subtotal", "IVA", "Total", "Hoja")])
    hojas, usados = [], set()
    for o in ords:
        base = "".join(ch for ch in o["marca"] if ch not in '[]:*?/\\')[:28] or "Marca"
        nombre, n = base, 2
        while nombre.upper() in usados or nombre.upper() in ("ÓRDENES", "TODAS LAS LÍNEAS"):
            nombre = f"{base[:25]} {n}"; n += 1
        usados.add(nombre.upper()); hojas.append(nombre)
    fila = 5
    for o, h in zip(ords, hojas):
        ult = 7 + o["articulos"]
        ref = "'" + h.replace("'", "''") + "'"
        ws.append([c(ws, o["folio"]), c(ws, o["marca"], F_B), c(ws, o["proveedor"]), c(ws, o["articulos"], fmt=ENT),
                   c(ws, f"=SUM({ref}!D8:D{ult})", fmt=ENT), c(ws, f"={ref}!F{ult + 1}", fmt=MON), c(ws, f"={ref}!F{ult + 2}", fmt=MON),
                   c(ws, f"={ref}!F{ult + 3}", fmt=MON), c(ws, h)])
        fila += 1
    if ords:
        ws.append([c(ws, "TOTAL", F_B), c(ws, ""), c(ws, ""), c(ws, f"=SUM(D5:D{fila - 1})", F_B, fmt=ENT), c(ws, f"=SUM(E5:E{fila - 1})", F_B, fmt=ENT),
                   c(ws, f"=SUM(F5:F{fila - 1})", F_B, fmt=MON), c(ws, f"=SUM(G5:G{fila - 1})", F_B, fmt=MON), c(ws, f"=SUM(H5:H{fila - 1})", F_B, fmt=MON)])
    else:
        ws.append([c(ws, "No hay nada que comprar con estos filtros.")])
    # Todas las líneas
    ws = wb.create_sheet("Todas las líneas")
    anchos(ws, [16, 20, 36, 16, 48, 10, 12, 14, 10, 12, 36])
    ws.freeze_panes = "A5"
    n_lin = sum(o["articulos"] for o in ords)
    ws.auto_filter.ref = f"A4:K{4 + max(n_lin, 1)}"
    ws.append([c(ws, "Todas las líneas de las órdenes", F_T)])
    ws.append([c(ws, "Usa los filtros para ver por marca o por proveedor.", F_S)])
    ws.append([])
    ws.append([c(ws, h, F_C, ROJO, AC) for h in ("Folio", "Marca", "Proveedor sugerido", "Clave", "Artículo", "Cantidad", "Costo unit.", "Importe",
                                                    "Ya pedido (OC)", "Última compra", "Último proveedor")])
    i = 5
    for o in ords:
        for x in o["lineas"]:
            ws.append([c(ws, o["folio"]), c(ws, o["marca"]), c(ws, o["proveedor"]), c(ws, x["clave"]), c(ws, x["articulo"]),
                       c(ws, x["cantidad"], fmt=ENT), c(ws, x["costo"], F_IN, fmt=MON), c(ws, f"=IF(G{i}=\"\",\"\",F{i}*G{i})", fmt=MON),
                       c(ws, x["ya_pedido"] or None, fmt=ENT), c(ws, x["ultima_compra"] or None), c(ws, x["proveedor"])])
            i += 1
    # Una hoja por marca
    for o, h in zip(ords, hojas):
        ws = wb.create_sheet(h)
        anchos(ws, [6, 18, 56, 11, 14, 15])
        ws.freeze_panes = "A8"
        pi = o["proveedor_info"] or {}
        ws.append([c(ws, f"ORDEN DE COMPRA (SUGERIDA) {o['folio']}", F_T)])
        ws.append([c(ws, "Marca:", F_B), c(ws, o["marca"], F_B), c(ws, ""), c(ws, "Fecha:", F_B), c(ws, r.get("hasta") or "")])
        ws.append([c(ws, "Proveedor:", F_B), c(ws, o["proveedor"]), c(ws, ""), c(ws, "Entregar en:", F_B), c(ws, (r.get("cedis") or {}).get("nombre") or "CEDIS")])
        ws.append([c(ws, "Contacto:", F_B), c(ws, " · ".join(x for x in (pi.get("contacto"), pi.get("telefono"), pi.get("email")) if x))])
        ws.append([c(ws, nota, F_S)])
        ws.append([])
        ws.append([c(ws, hh, F_C, ROJO, AC) for hh in ("#", "Clave", "Artículo", "Cantidad", "Costo unit.", "Importe")])
        j = 8
        for n, x in enumerate(o["lineas"], 1):
            ws.append([c(ws, n), c(ws, x["clave"]), c(ws, x["articulo"], al=AL), c(ws, x["cantidad"], fmt=ENT), c(ws, x["costo"], F_IN, fmt=MON),
                       c(ws, f"=IF(E{j}=\"\",0,D{j}*E{j})", fmt=MON)])
            j += 1
        u = j - 1
        ws.append([c(ws, ""), c(ws, ""), c(ws, ""), c(ws, ""), c(ws, "Subtotal", F_B), c(ws, f"=SUM(F8:F{u})", F_B, fmt=MON)])
        ws.append([c(ws, ""), c(ws, ""), c(ws, ""), c(ws, ""), c(ws, f"IVA {IVA * 100:.0f}%", F_B), c(ws, f"=F{u + 1}*{IVA}", fmt=MON)])
        ws.append([c(ws, ""), c(ws, ""), c(ws, ""), c(ws, ""), c(ws, "Total", F_B), c(ws, f"=F{u + 1}+F{u + 2}", F_B, fmt=MON)])
        if o["sin_costo"]:
            ws.append([c(ws, f"{o['sin_costo']} artículo(s) sin compra registrada (costo vacío): pedir precio.", F_S)])
    try:
        from openpyxl.workbook.properties import CalcProperties
        wb.calculation = CalcProperties(fullCalcOnLoad=True)
    except Exception:
        pass
    out = BytesIO(); wb.save(out)
    return out.getvalue()
