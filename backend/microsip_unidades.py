"""Reporte de unidades dentales vendidas (Microsip, solo lectura).

Cuenta las unidades que vienen en los PEDIDOS (DOCTOS_VE tipo 'P') que no están
cancelados (ESTATUS <> 'C'), y las desglosa por marca, modelo, sucursal, estado
de destino, mes y cliente. También trae todo lo demás que venía en esos pedidos.

¿Qué es una "unidad dental"? Los artículos de las líneas de Microsip que se elijan
(por defecto, las líneas cuyo nombre lleva "UNIDAD") y/o los artículos cuyo nombre
empiezan con un texto (por defecto "UNIDAD DENTAL").

Marca: el clasificador de artículos de Microsip cuyo nombre lleva "MARCA"
(CLASIFICADORES_CAT → CLASIFICADORES_CAT_VALORES → ELEMENTOS_CAT_CLASIF).
Estado de destino: la dirección de consignación del pedido (DIR_CONSIG_ID); si no
tiene, la dirección del cliente. DIRS_CLIENTES.ESTADO_ID o, si viene vacío, el
estado de su ciudad (CIUDADES.ESTADO_ID) → ESTADOS.NOMBRE.
"""
import io
from collections import defaultdict
from datetime import date

import microsip

# Marca según el nombre del artículo (va primero; si ninguna aplica se usa el clasificador MARCA
# de Microsip). Se buscan como palabras completas dentro del nombre.
MARCAS_POR_NOMBRE = [
    ("LUXOR", "PEYMAR"), ("CF", "PEYMAR"), ("JOY", "PEYMAR"),
    ("JAMEC", "JAMEC"),
    ("CINGOL", "CINGOL"),
]
TEXTO_DEFECTO = "UNIDAD DENTAL"  # por defecto: artículos cuyo nombre EMPIEZA con esto
ESTATUS_PEDIDO = {"P": "Pendiente", "F": "Facturado", "R": "Remisionado", "S": "Surtido", "C": "Cancelado"}

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _cols(cur, tabla):
    cur.execute("SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = ?", (tabla,))
    return {r[0] for r in cur.fetchall()}


def _t(v):
    return (v or "").strip() if isinstance(v, str) else (v or "")


def _lotes(ids, n=900):
    ids = list(ids)
    for i in range(0, len(ids), n):
        yield ids[i:i + n]


def _norm(v):
    """Mayúsculas, sin acentos y con un solo espacio (para comparar nombres)."""
    import unicodedata
    v = unicodedata.normalize("NFD", str(v or "").upper())
    v = "".join(c for c in v if unicodedata.category(c) != "Mn")
    return " ".join(v.split())


def folio_corto(folio):
    """AMC000180 -> AMC180: quita los ceros de en medio (entre las letras y el número)."""
    import re
    f = _t(folio)
    m = re.match(r"^(\D*?)0*(\d+)$", f)
    return f"{m.group(1)}{m.group(2)}" if m else f


def _marca_por_nombre(nombre):
    import re
    palabras = set(re.findall(r"[A-Z0-9]+", _norm(nombre)))
    for clave, marca in MARCAS_POR_NOMBRE:
        if set(clave.split()) <= palabras:
            return marca
    return None


def _fecha(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v or "")[:10]


def opciones(config):
    """Líneas de artículos (con cuántos artículos tiene cada una) y cuáles se
    sugieren por defecto (las que llevan UNIDAD en el nombre)."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        sucs, alms = _sucursales_almacenes(cur)
        if "LINEA_ARTICULO_ID" not in _cols(cur, "ARTICULOS") or not _cols(cur, "LINEAS_ARTICULOS"):
            return {"lineas": [], "sugeridas": [], "marca": _clasificador_marca(cur)[1], "sucursales": sucs, "almacenes": alms}
        cur.execute("""SELECT l.LINEA_ARTICULO_ID, l.NOMBRE, COUNT(a.ARTICULO_ID)
                       FROM LINEAS_ARTICULOS l LEFT JOIN ARTICULOS a ON a.LINEA_ARTICULO_ID = l.LINEA_ARTICULO_ID
                       GROUP BY l.LINEA_ARTICULO_ID, l.NOMBRE ORDER BY l.NOMBRE""")
        lineas = [{"id": i, "nombre": _t(n), "articulos": c} for i, n, c in cur.fetchall()]
        marca = _clasificador_marca(cur)[1]
    finally:
        con.close()
    sugeridas = []  # por defecto se usa el nombre (TEXTO_DEFECTO), no líneas
    return {"lineas": lineas, "sugeridas": sugeridas, "marca": marca, "sucursales": sucs, "almacenes": alms}


def _catalogo(cur, tabla, col_id):
    """{id: nombre} de SUCURSALES o ALMACENES, si la tabla existe."""
    if not {col_id, "NOMBRE"} <= _cols(cur, tabla):
        return {}
    cur.execute(f"SELECT {col_id}, NOMBRE FROM {tabla}")
    return {i: _t(n) for i, n in cur.fetchall()}


def _sucursales_almacenes(cur):
    """Sucursales y almacenes para los filtros (solo si los pedidos traen esa columna)."""
    cols_doc = _cols(cur, "DOCTOS_VE")
    orden = lambda d: [{"id": i, "nombre": n} for i, n in sorted(d.items(), key=lambda kv: kv[1])]
    sucs = orden(_catalogo(cur, "SUCURSALES", "SUCURSAL_ID")) if "SUCURSAL_ID" in cols_doc else []
    alms = orden(_catalogo(cur, "ALMACENES", "ALMACEN_ID")) if "ALMACEN_ID" in cols_doc else []
    return sucs, alms


def _clasificador_marca(cur):
    try:
        cur.execute("SELECT CLASIFICADOR_ID, NOMBRE FROM CLASIFICADORES_CAT WHERE TIPO_OBJETO = 'A' ORDER BY NOMBRE")
    except Exception:
        return None, None
    for cid, nom in cur.fetchall():
        if "MARCA" in _t(nom).upper():
            return cid, _t(nom)
    return None, None


def reporte(config, desde=None, hasta=None, lineas=None, texto=None, sucursales=None, almacenes=None, estatus=None):
    """desde / hasta: 'AAAA-MM-DD' (hasta es exclusivo) o None para todo.
    lineas: lista de LINEA_ARTICULO_ID; texto: el nombre del artículo debe EMPEZAR con él.
    sucursales / almacenes: listas de SUCURSAL_ID / ALMACEN_ID del pedido (vacío = todas).
    estatus: None = todos los pedidos sin cancelar; 'surtidos' = ya facturados/remisionados
    (no pendientes); 'pendientes' = solo pendientes.
    Si no se dan líneas ni texto, se usa TEXTO_DEFECTO ('UNIDAD DENTAL')."""
    texto = _norm(texto) or None
    estatus = estatus if estatus in ("surtidos", "pendientes") else None
    lineas = [int(x) for x in (lineas or [])]
    sucursales = [int(x) for x in (sucursales or [])]
    almacenes = [int(x) for x in (almacenes or [])]
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        cols_art = _cols(cur, "ARTICULOS")
        tiene_lineas = "LINEA_ARTICULO_ID" in cols_art and bool(_cols(cur, "LINEAS_ARTICULOS"))
        nombres_linea = {}
        if tiene_lineas:
            cur.execute("SELECT LINEA_ARTICULO_ID, NOMBRE FROM LINEAS_ARTICULOS")
            nombres_linea = {i: _t(n) for i, n in cur.fetchall()}
        if not lineas and not texto:
            texto = TEXTO_DEFECTO

        # 1) Artículos que cuentan como unidad dental
        sel_linea = ", LINEA_ARTICULO_ID" if tiene_lineas else ", NULL"
        cur.execute(f"SELECT ARTICULO_ID, NOMBRE{sel_linea} FROM ARTICULOS")
        articulos = {}
        for aid, nombre, linea in cur.fetchall():
            n = _t(nombre)
            if (linea in lineas) or (texto and _norm(n).startswith(texto)):
                articulos[aid] = {"nombre": n, "linea": nombres_linea.get(linea, "")}
        cols_doc = _cols(cur, "DOCTOS_VE")
        sucursales_cat = _catalogo(cur, "SUCURSALES", "SUCURSAL_ID") if "SUCURSAL_ID" in cols_doc else {}
        almacenes_cat = _catalogo(cur, "ALMACENES", "ALMACEN_ID") if "ALMACEN_ID" in cols_doc else {}
        criterio = {"lineas": [nombres_linea.get(i, str(i)) for i in lineas], "texto": texto, "articulos": len(articulos), "estatus": estatus,
                    "lista_articulos": sorted(a["nombre"] for a in articulos.values()),
                    "sucursales": [sucursales_cat.get(i, str(i)) for i in sucursales],
                    "almacenes": [almacenes_cat.get(i, str(i)) for i in almacenes]}
        vacio = _vacio(criterio, desde, hasta)
        if not articulos:
            return vacio

        claves = {}
        for lote in _lotes(articulos):
            cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({','.join('?' * len(lote))}) "
                        "ORDER BY CLAVE_ARTICULO_ID", tuple(lote))
            for aid, clave in cur.fetchall():
                if clave and aid not in claves:
                    claves[aid] = _t(clave)

        cid_marca, nombre_marca = _clasificador_marca(cur)
        marcas = {}
        if cid_marca:
            for lote in _lotes(articulos):
                cur.execute(f"""SELECT e.ELEMENTO_ID, v.VALOR FROM ELEMENTOS_CAT_CLASIF e
                                JOIN CLASIFICADORES_CAT_VALORES v ON v.VALOR_CLASIF_ID = e.VALOR_CLASIF_ID
                                WHERE v.CLASIFICADOR_ID = ? AND e.ELEMENTO_ID IN ({','.join('?' * len(lote))})""",
                            (cid_marca, *lote))
                for aid, valor in cur.fetchall():
                    if _t(valor):
                        marcas[aid] = _t(valor)
        for aid, a in articulos.items():
            m = _marca_por_nombre(a["nombre"])
            if m:
                marcas[aid] = m

        # 2) Pedidos vigentes que traen alguna unidad
        cols_det = _cols(cur, "DOCTOS_VE_DET")
        c_suc = "p.SUCURSAL_ID" if "SUCURSAL_ID" in cols_doc else "NULL"
        c_alm = "p.ALMACEN_ID" if "ALMACEN_ID" in cols_doc else "NULL"
        c_dir = "p.DIR_CONSIG_ID" if "DIR_CONSIG_ID" in cols_doc else "NULL"
        c_imp = "d.PRECIO_TOTAL_NETO" if "PRECIO_TOTAL_NETO" in cols_det else "0"
        cond = ["p.TIPO_DOCTO = 'P'", "COALESCE(p.ESTATUS, '') <> 'C'"]
        if estatus == "surtidos":
            cond.append("COALESCE(p.ESTATUS, '') <> 'P'")
        elif estatus == "pendientes":
            cond.append("p.ESTATUS = 'P'")
        params = []
        if desde:
            cond.append("p.FECHA >= ?"); params.append(desde)
        if hasta:
            cond.append("p.FECHA < ?"); params.append(hasta)
        for ids, col in ((sucursales, c_suc), (almacenes, c_alm)):
            if ids:
                if col == "NULL":
                    return vacio  # Microsip no guarda esa columna en los pedidos
                cond.append(f"{col} IN ({','.join('?' * len(ids))})"); params.extend(ids)
        pedidos = {}
        for lote in _lotes(articulos):
            cur.execute(f"""SELECT DISTINCT p.DOCTO_VE_ID, p.FOLIO, p.FECHA, p.CLIENTE_ID, {c_suc}, {c_dir}, {c_alm}, p.ESTATUS
                            FROM DOCTOS_VE p JOIN DOCTOS_VE_DET d ON d.DOCTO_VE_ID = p.DOCTO_VE_ID
                            WHERE {' AND '.join(cond)} AND d.ARTICULO_ID IN ({','.join('?' * len(lote))})""",
                        (*params, *lote))
            for did, folio, fecha, cli, suc, dir_id, alm, est in cur.fetchall():
                pedidos[did] = {"id": did, "estatus": ESTATUS_PEDIDO.get(_t(est), _t(est) or "Sin estatus"), "folio": folio_corto(folio), "fecha": _fecha(fecha), "cliente_id": cli,
                                "sucursal_id": suc, "almacen_id": alm, "dir_id": dir_id, "partidas": []}
        if not pedidos:
            return vacio

        # 3) Todas las partidas de esos pedidos (unidades y lo demás)
        otros_ids = set()
        for lote in _lotes(pedidos):
            cur.execute(f"""SELECT d.DOCTO_VE_ID, d.ARTICULO_ID, d.CLAVE_ARTICULO, d.UNIDADES, {c_imp}
                            FROM DOCTOS_VE_DET d WHERE d.DOCTO_VE_ID IN ({','.join('?' * len(lote))})""", tuple(lote))
            for did, aid, clave, unidades, importe in cur.fetchall():
                pedidos[did]["partidas"].append({"articulo_id": aid, "clave": _t(clave) or claves.get(aid, ""),
                                                 "unidades": float(unidades or 0), "importe": float(importe or 0),
                                                 "es_unidad": aid in articulos})
                if aid not in articulos:
                    otros_ids.add(aid)
        nombres_otros = {}
        for lote in _lotes([x for x in otros_ids if x]):
            cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({','.join('?' * len(lote))})", tuple(lote))
            nombres_otros.update({aid: _t(n) for aid, n in cur.fetchall()})

        # 4) Catálogos: clientes, sucursales, direcciones → estado
        clientes = {}
        for lote in _lotes({p["cliente_id"] for p in pedidos.values() if p["cliente_id"]}):
            cur.execute(f"SELECT CLIENTE_ID, NOMBRE FROM CLIENTES WHERE CLIENTE_ID IN ({','.join('?' * len(lote))})", tuple(lote))
            clientes.update({c: _t(n) for c, n in cur.fetchall()})
        estados, ciudades = {}, {}
        if _cols(cur, "ESTADOS"):
            cur.execute("SELECT ESTADO_ID, NOMBRE FROM ESTADOS")
            estados = {e: _t(n) for e, n in cur.fetchall()}
        if _cols(cur, "CIUDADES"):
            cur.execute("SELECT CIUDAD_ID, NOMBRE, ESTADO_ID FROM CIUDADES")
            ciudades = {c: (_t(n), e) for c, n, e in cur.fetchall()}
        cols_dir = _cols(cur, "DIRS_CLIENTES")
        c_est = "ESTADO_ID" if "ESTADO_ID" in cols_dir else "NULL"
        c_ciu = "CIUDAD_ID" if "CIUDAD_ID" in cols_dir else "NULL"
        c_ppal = "ES_DIR_PPAL" if "ES_DIR_PPAL" in cols_dir else "'N'"
        c_tels = [c for c in ("TELEFONO1", "TELEFONO2") if c in cols_dir] or ["NULL"]
        telefonos = {}  # CLIENTE_ID -> teléfono(s) de su dirección principal (o de la que tenga)
        dirs, dir_ppal = {}, {}
        ids_dir = {p["dir_id"] for p in pedidos.values() if p["dir_id"]}
        for lote in _lotes(ids_dir):
            cur.execute(f"SELECT DIR_CLI_ID, {c_est}, {c_ciu} FROM DIRS_CLIENTES WHERE DIR_CLI_ID IN ({','.join('?' * len(lote))})", tuple(lote))
            dirs.update({d: (e, c) for d, e, c in cur.fetchall()})
        for lote in _lotes({p["cliente_id"] for p in pedidos.values() if p["cliente_id"]}):
            cur.execute(f"SELECT CLIENTE_ID, {c_est}, {c_ciu}, {c_ppal}, {', '.join(c_tels)} FROM DIRS_CLIENTES "
                        f"WHERE CLIENTE_ID IN ({','.join('?' * len(lote))})", tuple(lote))
            for cli, e, c, ppal, *tels in cur.fetchall():
                if cli not in dir_ppal or _t(ppal) == "S":
                    dir_ppal[cli] = (e, c)
                tel = " / ".join(dict.fromkeys(_t(x) for x in tels if _t(x)))
                if tel and (cli not in telefonos or _t(ppal) == "S"):
                    telefonos[cli] = tel
    finally:
        con.close()

    def lugar(p):
        e, c = dirs.get(p["dir_id"]) or dir_ppal.get(p["cliente_id"]) or (None, None)
        ciudad, e_ciudad = ciudades.get(c, ("", None))
        return estados.get(e) or estados.get(e_ciudad) or "Sin estado", ciudad

    # 5) Armar el reporte
    por_marca, por_modelo = defaultdict(lambda: [0.0, 0.0, set()]), {}
    por_suc, suc_modelo = defaultdict(lambda: [0.0, 0.0, set()]), defaultdict(float)
    por_est, est_modelo = defaultdict(lambda: [0.0, 0.0, set()]), defaultdict(float)
    por_alm, alm_modelo = defaultdict(lambda: [0.0, 0.0, set()]), defaultdict(float)
    por_estatus = defaultdict(lambda: [0.0, 0.0, set()])
    por_mes = defaultdict(lambda: [0.0, 0.0])
    por_cli = defaultdict(lambda: {"unidades": 0.0, "importe": 0.0, "pedidos": set(), "modelos": defaultdict(float), "ultima": "", "estado": "",
                                   "telefono": ""})
    detalle = []
    tot_u = tot_imp = 0.0
    for p in sorted(pedidos.values(), key=lambda x: (x["fecha"], x["folio"])):
        estado, ciudad = lugar(p)
        suc = sucursales_cat.get(p["sucursal_id"], "Sin sucursal")
        alm = almacenes_cat.get(p["almacen_id"], "Sin almacén")
        cli = clientes.get(p["cliente_id"], "Sin cliente")
        u_ped = imp_ped_u = imp_ped = 0.0
        partidas = []
        for d in p["partidas"]:
            imp_ped += d["importe"]
            if d["es_unidad"]:
                a = articulos[d["articulo_id"]]
                marca = marcas.get(d["articulo_id"]) or "Sin marca"
                modelo = a["nombre"]
                u, imp = d["unidades"], d["importe"]
                u_ped += u; imp_ped_u += imp
                por_marca[marca][0] += u; por_marca[marca][1] += imp; por_marca[marca][2].add(p["id"])
                m = por_modelo.setdefault(d["articulo_id"], {"marca": marca, "modelo": modelo, "clave": d["clave"] or claves.get(d["articulo_id"], ""),
                                                             "linea": a["linea"], "unidades": 0.0, "importe": 0.0, "pedidos": set(),
                                                             "por_folio": {}})
                m["unidades"] += u; m["importe"] += imp; m["pedidos"].add(p["id"])
                m["por_folio"][p["folio"]] = m["por_folio"].get(p["folio"], 0.0) + u
                por_suc[suc][0] += u; por_suc[suc][1] += imp; por_suc[suc][2].add(p["id"])
                suc_modelo[(suc, marca, modelo)] += u
                por_alm[alm][0] += u; por_alm[alm][1] += imp; por_alm[alm][2].add(p["id"])
                alm_modelo[(alm, marca, modelo)] += u
                por_estatus[p["estatus"]][0] += u; por_estatus[p["estatus"]][1] += imp; por_estatus[p["estatus"]][2].add(p["id"])
                por_est[estado][0] += u; por_est[estado][1] += imp; por_est[estado][2].add(p["id"])
                est_modelo[(estado, marca, modelo)] += u
                por_mes[p["fecha"][:7]][0] += u; por_mes[p["fecha"][:7]][1] += imp
                c = por_cli[cli]
                c["unidades"] += u; c["importe"] += imp; c["pedidos"].add(p["id"]); c["modelos"][modelo] += u
                c["ultima"] = max(c["ultima"], p["fecha"]); c["estado"] = estado
                c["telefono"] = c["telefono"] or telefonos.get(p["cliente_id"], "")
                partidas.append({"tipo": "Unidad", "marca": marca, "articulo": modelo, "clave": d["clave"], "unidades": u, "importe": round(imp, 2)})
            else:
                partidas.append({"tipo": "Otro", "marca": "", "articulo": nombres_otros.get(d["articulo_id"], ""), "clave": d["clave"],
                                 "unidades": d["unidades"], "importe": round(d["importe"], 2)})
        tot_u += u_ped; tot_imp += imp_ped_u
        detalle.append({"folio": p["folio"], "fecha": p["fecha"], "sucursal": suc, "almacen": alm, "estatus": p["estatus"], "cliente": cli, "estado": estado, "ciudad": ciudad,
                        "unidades": u_ped, "importe_unidades": round(imp_ped_u, 2), "importe_pedido": round(imp_ped, 2),
                        "partidas": partidas})

    def lista(dic, nombre):
        return sorted([{nombre: k, "unidades": v[0], "importe": round(v[1], 2), "pedidos": len(v[2])} for k, v in dic.items()],
                      key=lambda x: (-x["unidades"], -x["importe"]))

    meses = sorted(por_mes)
    serie = []
    if meses:
        y, m = int(meses[0][:4]), int(meses[0][5:7])
        y2, m2 = int(meses[-1][:4]), int(meses[-1][5:7])
        while (y, m) <= (y2, m2):
            k = f"{y:04d}-{m:02d}"
            serie.append({"mes": k, "etiqueta": f"{MESES[m - 1]} {y}", "unidades": por_mes[k][0] if k in por_mes else 0.0,
                          "importe": round(por_mes[k][1], 2) if k in por_mes else 0.0})
            m += 1
            if m == 13:
                y, m = y + 1, 1
    por_anio = defaultdict(lambda: [0.0] * 12)
    for s in serie:
        por_anio[s["mes"][:4]][int(s["mes"][5:7]) - 1] += s["unidades"]
    anios = sorted(por_anio)
    comparativo = {"anios": anios, "meses": MESES, "series": {a: por_anio[a] for a in anios},
                   "totales": {a: sum(por_anio[a]) for a in anios}}
    mejor_mes = max(serie, key=lambda s: s["unidades"]) if serie else None

    clientes_rank = sorted([{"cliente": k, "unidades": v["unidades"], "importe": round(v["importe"], 2), "pedidos": len(v["pedidos"]),
                             "ultima_compra": v["ultima"], "estado": v["estado"], "telefono": v["telefono"],
                             "modelos": ", ".join(f"{mod} ({u:g})" for mod, u in sorted(v["modelos"].items(), key=lambda kv: -kv[1]))}
                            for k, v in por_cli.items()], key=lambda x: (-x["unidades"], -x["importe"]))
    for i, c in enumerate(clientes_rank, 1):
        c["lugar"] = i

    return {
        "criterio": criterio, "desde": desde, "hasta": hasta, "marca_clasificador": nombre_marca,
        "resumen": {"unidades": tot_u, "pedidos": len(pedidos), "clientes": len(por_cli), "importe": round(tot_imp, 2),
                    "mejor_cliente": clientes_rank[0] if clientes_rank else None, "mejor_mes": mejor_mes},
        "por_marca": lista(por_marca, "marca"),
        "por_modelo": sorted([{**{k: v for k, v in m.items() if k not in ("pedidos", "por_folio")}, "importe": round(m["importe"], 2),
                               "pedidos": len(m["pedidos"]),
                               # En qué pedidos van: "AMC180, AMC181 (2)" (el número entre paréntesis = unidades si son más de 1)
                               "folios": ", ".join(f"{f} ({u:g})" if u != 1 else f for f, u in m["por_folio"].items())}
                              for m in por_modelo.values()], key=lambda x: (-x["unidades"], x["modelo"])),
        "por_sucursal": lista(por_suc, "sucursal"),
        "sucursal_modelo": sorted([{"sucursal": s, "marca": ma, "modelo": mo, "unidades": u} for (s, ma, mo), u in suc_modelo.items()],
                                  key=lambda x: (x["sucursal"], -x["unidades"])),
        "por_almacen": lista(por_alm, "almacen"),
        "por_estatus": lista(por_estatus, "estatus"),
        "almacen_modelo": sorted([{"almacen": a, "marca": ma, "modelo": mo, "unidades": u} for (a, ma, mo), u in alm_modelo.items()],
                                 key=lambda x: (x["almacen"], -x["unidades"])),
        "por_estado": lista(por_est, "estado"),
        "estado_modelo": sorted([{"estado": e, "marca": ma, "modelo": mo, "unidades": u} for (e, ma, mo), u in est_modelo.items()],
                                key=lambda x: (x["estado"], -x["unidades"])),
        "por_mes": serie, "comparativo": comparativo,
        "clientes": clientes_rank,
        "pedidos": detalle,
    }


def _vacio(criterio, desde, hasta):
    return {"criterio": criterio, "desde": desde, "hasta": hasta, "marca_clasificador": None,
            "resumen": {"unidades": 0, "pedidos": 0, "clientes": 0, "importe": 0, "mejor_cliente": None, "mejor_mes": None},
            "por_marca": [], "por_modelo": [], "por_sucursal": [], "sucursal_modelo": [], "por_almacen": [], "almacen_modelo": [], "por_estatus": [], "por_estado": [], "estado_modelo": [],
            "por_mes": [], "comparativo": {"anios": [], "meses": MESES, "series": {}, "totales": {}}, "clientes": [], "pedidos": []}


# =============================================================================
# Excel y PDF
# =============================================================================

def _periodo_txt(r):
    d, h = r.get("desde"), r.get("hasta")
    if not d and not h:
        return "Todo el historial"
    fmt = lambda s: f"{s[8:10]}/{s[5:7]}/{s[:4]}"
    if d and h:
        from datetime import timedelta
        fin = (date.fromisoformat(h) - timedelta(days=1)).isoformat()
        return f"{fmt(d)} al {fmt(fin)}"
    return f"Desde {fmt(d)}" if d else f"Hasta {fmt(h)}"


def _criterio_txt(r):
    c = r.get("criterio") or {}
    partes = []
    if c.get("lineas"):
        partes.append("líneas " + ", ".join(c["lineas"]))
    if c.get("texto"):
        partes.append(f"artículos cuyo nombre empieza con “{c['texto']}”")
    return " y ".join(partes) or "—"


def _filtro_txt(r):
    """'Sucursal X · Almacén Y' según los filtros, o '' si son todas."""
    c = r.get("criterio") or {}
    partes = []
    if c.get("sucursales"):
        partes.append(("Sucursal " if len(c["sucursales"]) == 1 else "Sucursales ") + ", ".join(c["sucursales"]))
    if c.get("almacenes"):
        partes.append(("Almacén " if len(c["almacenes"]) == 1 else "Almacenes ") + ", ".join(c["almacenes"]))
    if c.get("estatus") == "surtidos":
        partes.append("Solo pedidos ya facturados/remisionados")
    elif c.get("estatus") == "pendientes":
        partes.append("Solo pedidos pendientes")
    return " · ".join(partes)


def _encabezado_txt(r):
    return " · ".join(x for x in (_periodo_txt(r), _filtro_txt(r)) if x)


def excel(r, empresa_nombre=""):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    A = "Arial"
    cab = PatternFill("solid", fgColor="D8192F")

    def hoja(ws, titulo, columnas, filas, anchos):
        ws["A1"] = titulo; ws["A1"].font = Font(name=A, size=14, bold=True)
        ws["A2"] = f"{empresa_nombre} · {_encabezado_txt(r)} · Pedidos sin cancelar"; ws["A2"].font = Font(name=A, size=9, color="595959")
        for i, (t, _) in enumerate(columnas, 1):
            c = ws.cell(row=4, column=i, value=t)
            c.font = Font(name=A, bold=True, color="FFFFFF"); c.fill = cab; c.alignment = Alignment(horizontal="center", wrap_text=True)
        for j, f in enumerate(filas, 5):
            for i, (_, k) in enumerate(columnas, 1):
                v = f.get(k) if isinstance(f, dict) else f[i - 1]
                c = ws.cell(row=j, column=i, value=v); c.font = Font(name=A)
                if k in ("importe", "importe_unidades", "importe_pedido"):
                    c.number_format = '$#,##0.00'
                elif k in ("unidades", "pedidos", "lugar"):
                    c.number_format = '#,##0.##'
        for i, w in enumerate(anchos, 1):
            ws.column_dimensions[chr(64 + i)].width = w
        ws.freeze_panes = "A5"
        return 5, 4 + len(filas)

    ws = wb.active; ws.title = "Resumen"
    res = r["resumen"]
    ws["A1"] = "Unidades dentales vendidas"; ws["A1"].font = Font(name=A, size=16, bold=True)
    filas = [("Periodo", _periodo_txt(r)), ("Sucursal", ", ".join(r["criterio"].get("sucursales") or []) or "Todas"),
             ("Almacén", ", ".join(r["criterio"].get("almacenes") or []) or "Todos"),
             ("Estatus de pedidos", {"surtidos": "Solo ya facturados/remisionados", "pendientes": "Solo pendientes"}.get(r["criterio"].get("estatus"), "Todos los no cancelados")),
             ("Qué se contó", _criterio_txt(r)),
             ("Solo pedidos", "Pedidos de Microsip sin cancelar"),
             ("Unidades vendidas", res["unidades"]), ("Pedidos", res["pedidos"]), ("Clientes", res["clientes"]),
             ("Importe de las unidades (sin IVA)", res["importe"])]
    mc = res.get("mejor_cliente")
    if mc:
        filas.append(("Mejor comprador", f"{mc['cliente']} — {mc['unidades']:g} unidades en {mc['pedidos']} pedido(s)"))
    mm = res.get("mejor_mes")
    if mm:
        filas.append(("Mes con más ventas", f"{mm['etiqueta']} — {mm['unidades']:g} unidades"))
    for i, (k, v) in enumerate(filas, 3):
        ws.cell(row=i, column=1, value=k).font = Font(name=A, bold=True)
        c = ws.cell(row=i, column=2, value=v); c.font = Font(name=A)
        if k.startswith("Importe"):
            c.number_format = '$#,##0.00'
    ws.column_dimensions["A"].width = 34; ws.column_dimensions["B"].width = 80

    hoja(wb.create_sheet("Por marca"), "Por marca", [("Marca", "marca"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                      ("Importe sin IVA", "importe")], r["por_marca"], [30, 12, 10, 18])
    hoja(wb.create_sheet("Por modelo"), "Por modelo", [("Marca", "marca"), ("Modelo (artículo)", "modelo"), ("Clave", "clave"),
                                                        ("Línea", "linea"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                        ("Importe sin IVA", "importe"), ("En qué pedidos van (folio)", "folios")],
         r["por_modelo"], [20, 46, 14, 20, 11, 10, 16, 70])
    ws_m = wb["Por modelo"]
    for fila in ws_m.iter_rows(min_row=5, min_col=8, max_col=8):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    hoja(wb.create_sheet("Por sucursal"), "Por sucursal", [("Sucursal", "sucursal"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                            ("Importe sin IVA", "importe")], r["por_sucursal"], [30, 12, 10, 18])
    hoja(wb.create_sheet("Sucursal y modelo"), "Por sucursal y modelo", [("Sucursal", "sucursal"), ("Marca", "marca"), ("Modelo", "modelo"),
                                                                         ("Unidades", "unidades")], r["sucursal_modelo"], [28, 20, 46, 11])
    hoja(wb.create_sheet("Por estatus"), "Por estatus del pedido", [("Estatus", "estatus"), ("Unidades", "unidades"),
                                                                   ("Pedidos", "pedidos"), ("Importe sin IVA", "importe")],
         r["por_estatus"], [24, 12, 10, 18])
    hoja(wb.create_sheet("Por almacén"), "Por almacén", [("Almacén", "almacen"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                          ("Importe sin IVA", "importe")], r["por_almacen"], [30, 12, 10, 18])
    hoja(wb.create_sheet("Almacén y modelo"), "Por almacén y modelo", [("Almacén", "almacen"), ("Marca", "marca"), ("Modelo", "modelo"),
                                                                       ("Unidades", "unidades")], r["almacen_modelo"], [28, 20, 46, 11])
    hoja(wb.create_sheet("Por estado"), "Por estado de destino", [("Estado", "estado"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                                  ("Importe sin IVA", "importe")], r["por_estado"], [28, 12, 10, 18])
    hoja(wb.create_sheet("Estado y modelo"), "Por estado y modelo", [("Estado", "estado"), ("Marca", "marca"), ("Modelo", "modelo"),
                                                                     ("Unidades", "unidades")], r["estado_modelo"], [24, 20, 46, 11])
    hoja(wb.create_sheet("Mejores clientes"), "Mejores compradores", [("Lugar", "lugar"), ("Cliente", "cliente"), ("Teléfono", "telefono"),
                                                                       ("Unidades", "unidades"),
                                                                       ("Pedidos", "pedidos"), ("Importe sin IVA", "importe"),
                                                                       ("Última compra", "ultima_compra"), ("Estado", "estado"),
                                                                       ("Modelos", "modelos")], r["clientes"], [7, 38, 18, 10, 9, 16, 13, 18, 60])

    ws = wb.create_sheet("Por mes")
    ini, fin = hoja(ws, "Unidades vendidas por mes", [("Mes", "etiqueta"), ("Unidades", "unidades"), ("Importe sin IVA", "importe")],
                    r["por_mes"], [14, 12, 18])
    if r["por_mes"]:
        g = BarChart(); g.type = "col"; g.title = "Unidades por mes"; g.y_axis.title = "Unidades"
        g.add_data(Reference(ws, min_col=2, min_row=4, max_row=fin), titles_from_data=True)
        g.set_categories(Reference(ws, min_col=1, min_row=5, max_row=fin))
        g.height, g.width = 9, 26; g.legend = None
        g.roundedCorners = False; g.x_axis.delete = False; g.y_axis.delete = False
        ws.add_chart(g, "E4")

    comp = r["comparativo"]
    ws = wb.create_sheet("Comparativo por año")
    cols = [("Mes", 0)] + [(a, i + 1) for i, a in enumerate(comp["anios"])]
    filas = [[m] + [comp["series"][a][i] for a in comp["anios"]] for i, m in enumerate(comp["meses"])]
    filas.append(["Total"] + [comp["totales"][a] for a in comp["anios"]])
    ws["A1"] = "Comparativo de unidades por mes y año"; ws["A1"].font = Font(name=A, size=14, bold=True)
    for i, (t, _) in enumerate(cols, 1):
        c = ws.cell(row=4, column=i, value=str(t)); c.font = Font(name=A, bold=True, color="FFFFFF"); c.fill = cab
    for j, f in enumerate(filas, 5):
        for i, v in enumerate(f, 1):
            c = ws.cell(row=j, column=i, value=v); c.font = Font(name=A, bold=(f[0] == "Total"))
    if comp["anios"]:
        g = BarChart(); g.type = "col"; g.title = "Comparativo por año"; g.y_axis.title = "Unidades"
        g.add_data(Reference(ws, min_col=2, max_col=1 + len(comp["anios"]), min_row=4, max_row=16), titles_from_data=True)
        g.set_categories(Reference(ws, min_col=1, min_row=5, max_row=16))
        g.height, g.width = 9, 26; g.roundedCorners = False; g.x_axis.delete = False; g.y_axis.delete = False
        g.legend.overlay = False
        ws.add_chart(g, f"{chr(67 + len(comp['anios']))}4")

    hoja(wb.create_sheet("Artículos contados"), "Artículos que se contaron como unidad dental", [("Artículo", "articulo")],
         [{"articulo": x} for x in r["criterio"].get("lista_articulos") or []], [70])

    ws = wb.create_sheet("Pedidos (detalle)")
    cols = [("Folio", "folio"), ("Fecha", "fecha"), ("Sucursal", "sucursal"), ("Almacén", "almacen"), ("Estatus", "estatus"), ("Cliente", "cliente"), ("Estado", "estado"),
            ("Ciudad", "ciudad"), ("Tipo", "tipo"), ("Marca", "marca"), ("Artículo", "articulo"), ("Clave", "clave"),
            ("Unidades", "unidades"), ("Importe sin IVA", "importe")]
    filas = []
    for p in r["pedidos"]:
        for d in p["partidas"]:
            filas.append({**{k: p[k] for k in ("folio", "fecha", "sucursal", "almacen", "estatus", "cliente", "estado", "ciudad")}, **d})
    hoja(ws, "Todo lo que traen los pedidos", cols, filas, [12, 11, 20, 20, 13, 32, 18, 18, 8, 16, 44, 14, 10, 15])
    ws.auto_filter.ref = f"A4:N{4 + len(filas)}"

    out = io.BytesIO(); wb.save(out)
    return out.getvalue()


def pdf(r, empresa_nombre=""):
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ROJO = colors.HexColor("#D8192F"); GRIS = colors.HexColor("#5F6368"); LINEA = colors.HexColor("#DDDDDD"); SUAVE = colors.HexColor("#F5F5F5")
    PALETA = [colors.HexColor(x) for x in ("#D8192F", "#2F4B7C", "#2E9E5B", "#E0A100", "#7A4FBF", "#1E88E5", "#8D6E63")]
    p = ParagraphStyle("p", fontName="Helvetica", fontSize=8.5, leading=10.5)
    pb = ParagraphStyle("pb", parent=p, fontName="Helvetica-Bold")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, leading=22)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=ROJO, spaceBefore=10, spaceAfter=5)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, leading=12, textColor=GRIS)
    W = landscape(letter)[0] - 1.2 * inch
    dinero = lambda v: f"${v:,.2f}"
    num = lambda v: f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"

    def tabla(columnas, filas, anchos, max_filas=None):
        datos = [[Paragraph(f"<font color='white'><b>{c}</b></font>", p) for c, _ in columnas]]
        for f in filas[:max_filas] if max_filas else filas:
            fila = []
            for _, k in columnas:
                v = f.get(k)
                if k in ("importe", "importe_unidades", "importe_pedido"):
                    v = dinero(v or 0)
                elif k in ("unidades", "pedidos"):
                    v = num(v or 0)
                fila.append(Paragraph(str(v if v is not None else ""), p))
            datos.append(fila)
        t = Table(datos, colWidths=[W * a for a in anchos], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ROJO), ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SUAVE]),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    def grafica(etiquetas, series, nombres, alto=2.6 * inch):
        d = Drawing(W, alto)
        if not etiquetas:
            return d
        g = VerticalBarChart()
        g.x, g.y, g.width, g.height = 40, 38, W - 60 - (90 if len(series) > 1 else 0), alto - 55
        g.data = series
        g.categoryAxis.categoryNames = etiquetas
        g.categoryAxis.labels.fontSize = 6.5 if len(etiquetas) > 18 else 8
        g.categoryAxis.labels.angle = 45 if len(etiquetas) > 12 else 0
        g.categoryAxis.labels.boxAnchor = "ne" if len(etiquetas) > 12 else "n"
        g.valueAxis.valueMin = 0
        g.valueAxis.labels.fontSize = 8
        g.categoryAxis.labels.fontName = g.valueAxis.labels.fontName = "Helvetica"
        g.groupSpacing = 4 if len(series) > 1 else 2
        for i in range(len(series)):
            g.bars[i].fillColor = PALETA[i % len(PALETA)]; g.bars[i].strokeColor = None
        d.add(g)
        if len(series) > 1:
            for i, n in enumerate(nombres):
                y = alto - 25 - i * 14
                from reportlab.graphics.shapes import Rect
                d.add(Rect(W - 80, y, 9, 9, fillColor=PALETA[i % len(PALETA)], strokeColor=None))
                d.add(String(W - 66, y + 1, str(n), fontSize=8, fontName="Helvetica"))
        return d

    res = r["resumen"]
    s = [Paragraph("Unidades dentales vendidas", h1),
         Paragraph(f"{empresa_nombre} · {_encabezado_txt(r)} · Pedidos de Microsip sin cancelar · {_criterio_txt(r)}", sub), Spacer(1, 10)]
    kpis = [("Unidades vendidas", num(res["unidades"])), ("Pedidos", num(res["pedidos"])), ("Clientes", num(res["clientes"])),
            ("Importe de unidades (sin IVA)", dinero(res["importe"]))]
    kt = Table([[Paragraph(f"<font size=8 color='#5F6368'>{a}</font><br/><font size=16><b>{b}</b></font>", ParagraphStyle('k', leading=20))
                 for a, b in kpis]], colWidths=[W / 4] * 4)
    kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINEA), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINEA),
                            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    s.append(kt)
    mc, mm = res.get("mejor_cliente"), res.get("mejor_mes")
    destacados = []
    if mc:
        destacados.append(f"🏆 <b>Mejor comprador:</b> {mc['cliente']} — {num(mc['unidades'])} unidades en {mc['pedidos']} pedido(s), {dinero(mc['importe'])}.")
    if mm:
        destacados.append(f"📈 <b>Mes con más ventas:</b> {mm['etiqueta']} — {num(mm['unidades'])} unidades.")
    if r["por_modelo"]:
        t = r["por_modelo"][0]
        destacados.append(f"⭐ <b>Modelo más vendido:</b> {t['modelo']} ({t['marca']}) — {num(t['unidades'])} unidades.")
    for x in destacados:
        s += [Spacer(1, 4), Paragraph(x.replace("🏆 ", "").replace("📈 ", "").replace("⭐ ", ""), ParagraphStyle("d", fontName="Helvetica", fontSize=10, leading=13))]

    if r["por_mes"]:
        s.append(KeepTogether([Paragraph("¿Cuándo se vendió más? (unidades por mes)", h2),
                               grafica([x["etiqueta"] for x in r["por_mes"]], [[x["unidades"] for x in r["por_mes"]]], ["Unidades"])]))
    comp = r["comparativo"]
    if len(comp["anios"]) > 1:
        s.append(KeepTogether([Paragraph("Comparativo por año (unidades por mes)", h2),
                               grafica(comp["meses"], [comp["series"][a] for a in comp["anios"]], comp["anios"]),
                               Paragraph("Total por año: " + " · ".join(f"<b>{a}</b>: {num(comp['totales'][a])}" for a in comp["anios"]), p)]))

    s += [PageBreak(), Paragraph("Mejores compradores", h2),
          tabla([("#", "lugar"), ("Cliente", "cliente"), ("Teléfono", "telefono"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                 ("Importe", "importe"), ("Última compra", "ultima_compra"), ("Estado", "estado"), ("Modelos", "modelos")],
                r["clientes"], [.03, .17, .1, .075, .07, .11, .085, .09, .27], 25)]
    s += [Paragraph("Por marca", h2), tabla([("Marca", "marca"), ("Unidades", "unidades"), ("Pedidos", "pedidos"), ("Importe", "importe")],
                                            r["por_marca"], [.4, .2, .2, .2])]
    s += [KeepTogether([Paragraph("Por modelo", h2),
                        tabla([("Marca", "marca"), ("Modelo", "modelo"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                               ("Importe", "importe"), ("En qué pedidos van", "folios")], r["por_modelo"],
                              [.1, .28, .08, .08, .11, .35])])]
    s += [Paragraph("Por sucursal", h2), tabla([("Sucursal", "sucursal"), ("Unidades", "unidades"), ("Pedidos", "pedidos"), ("Importe", "importe")],
                                               r["por_sucursal"], [.4, .2, .2, .2]),
          Spacer(1, 6), tabla([("Sucursal", "sucursal"), ("Marca", "marca"), ("Modelo", "modelo"), ("Unidades", "unidades")],
                              r["sucursal_modelo"], [.25, .2, .45, .1])]
    s += [Paragraph("Por estatus del pedido", h2), tabla([("Estatus", "estatus"), ("Unidades", "unidades"), ("Pedidos", "pedidos"),
                                                          ("Importe", "importe")], r["por_estatus"], [.4, .2, .2, .2])]
    s += [Paragraph("Por almacén", h2), tabla([("Almacén", "almacen"), ("Unidades", "unidades"), ("Pedidos", "pedidos"), ("Importe", "importe")],
                                              r["por_almacen"], [.4, .2, .2, .2]),
          Spacer(1, 6), tabla([("Almacén", "almacen"), ("Marca", "marca"), ("Modelo", "modelo"), ("Unidades", "unidades")],
                              r["almacen_modelo"], [.25, .2, .45, .1])]
    s += [Paragraph("Por estado de destino", h2), tabla([("Estado", "estado"), ("Unidades", "unidades"), ("Pedidos", "pedidos"), ("Importe", "importe")],
                                                        r["por_estado"], [.4, .2, .2, .2]),
          Spacer(1, 6), tabla([("Estado", "estado"), ("Marca", "marca"), ("Modelo", "modelo"), ("Unidades", "unidades")],
                              r["estado_modelo"], [.25, .2, .45, .1])]
    s += [PageBreak(), Paragraph("Detalle de los pedidos (todo lo que traen)", h2)]
    for ped in r["pedidos"]:
        cab = Paragraph(f"<b>{ped['folio']}</b> · {ped['fecha']} · {ped['sucursal']} · {ped['almacen']} · {ped['estatus']} · <b>{ped['cliente']}</b> · {ped['estado']}"
                        f"{(' (' + ped['ciudad'] + ')') if ped['ciudad'] else ''} · Total del pedido {dinero(ped['importe_pedido'])}", p)
        t = tabla([("Tipo", "tipo"), ("Marca", "marca"), ("Artículo", "articulo"), ("Clave", "clave"), ("Unidades", "unidades"), ("Importe", "importe")],
                  ped["partidas"], [.08, .14, .48, .12, .08, .1])
        s.append(KeepTogether([cab, Spacer(1, 2), t, Spacer(1, 8)]))

    def pie(c, doc):
        c.setFont("Helvetica", 7.5); c.setFillColor(GRIS)
        c.drawString(0.6 * inch, 0.4 * inch, f"Unidades dentales vendidas · {empresa_nombre} · Fuente: Microsip (pedidos sin cancelar)")
        c.drawRightString(landscape(letter)[0] - 0.6 * inch, 0.4 * inch, f"Página {doc.page}")

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(letter), leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.55 * inch,
                            bottomMargin=0.65 * inch, title="Unidades dentales vendidas")
    doc.build(s, onFirstPage=pie, onLaterPages=pie)
    return out.getvalue()
