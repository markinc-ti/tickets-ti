"""
Artículos que en Microsip piden lote o serie (seguimiento por lotes/series)
pero cuya existencia no tiene lote o serie asignado, por almacén.

Solo lectura. Existencia del almacén = CAPAS_COSTOS activas (mismo criterio
que Valor del inventario). Existencia con lote/serie = EXIS_DISCRETOS unido
con ARTICULOS_DISCRETOS. Lo que falta = existencia − con lote/serie.

Los nombres de columnas se leen del catálogo de Firebird, para no depender de
la versión de Microsip.
"""
import microsip

SIN_SEGUIMIENTO = {"", "N", "NINGUNO", "0"}
NOMBRE_SEGUIMIENTO = {"L": "Lote", "S": "Serie"}


def _columnas(cur, tabla):
    cur.execute("""SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS
                   WHERE RDB$RELATION_NAME = ? ORDER BY RDB$FIELD_POSITION""", (tabla,))
    return [r[0] for r in cur.fetchall()]


def _por_lotes(cur, sql, ids):
    salida = []
    for i in range(0, len(ids), 400):
        lote = ids[i:i + 400]
        cur.execute(sql.format(",".join("?" for _ in lote)), tuple(lote))
        salida.extend(cur.fetchall())
    return salida


def articulos_sin_lote_serie(config):
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        cols_art = _columnas(cur, "ARTICULOS")
        col_seg = "SEGUIMIENTO" if "SEGUIMIENTO" in cols_art else next((c for c in cols_art if "SEGUIM" in c), None)
        if not col_seg:
            pistas = [c for c in cols_art if "LOTE" in c or "SERIE" in c or "DISCRET" in c]
            raise RuntimeError("No encontré la columna de seguimiento en ARTICULOS. Columnas parecidas: " + (", ".join(pistas) or "ninguna"))

        cur.execute(f'SELECT TRIM("{col_seg}"), COUNT(*) FROM ARTICULOS GROUP BY 1')
        valores = {(v or ""): n for v, n in cur.fetchall()}
        cur.execute(f'SELECT ARTICULO_ID, TRIM("{col_seg}") FROM ARTICULOS')
        seguimiento = {aid: (v or "").upper() for aid, v in cur.fetchall() if (v or "").strip().upper() not in SIN_SEGUIMIENTO}

        cur.execute("""SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA) FROM CAPAS_COSTOS cc
                       WHERE cc.CAPA_AGOTADA = 'N' GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID""")
        existencia = {(a, art): float(e or 0) for a, art, e in cur.fetchall() if art in seguimiento}

        # Existencia que sí tiene lote/serie.
        con_discreto = {}
        aviso = None
        cur.execute("""SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
                       WHERE RDB$RELATION_NAME IN ('ARTICULOS_DISCRETOS', 'EXIS_DISCRETOS')""")
        tablas = {r[0] for r in cur.fetchall()}
        if tablas == {"ARTICULOS_DISCRETOS", "EXIS_DISCRETOS"}:
            ca, ce = _columnas(cur, "ARTICULOS_DISCRETOS"), _columnas(cur, "EXIS_DISCRETOS")
            llave = next((c for c in ce if c.endswith("DISCRETO_ID") and c in ca), None)
            col_exis = "EXISTENCIA" if "EXISTENCIA" in ce else next((c for c in ce if "EXIS" in c and not c.endswith("_ID")), None)
            if llave and col_exis and "ALMACEN_ID" in ce and "ARTICULO_ID" in ca:
                cur.execute(f'''SELECT e.ALMACEN_ID, d.ARTICULO_ID, SUM(e."{col_exis}")
                                FROM EXIS_DISCRETOS e JOIN ARTICULOS_DISCRETOS d ON d."{llave}" = e."{llave}"
                                GROUP BY e.ALMACEN_ID, d.ARTICULO_ID''')
                con_discreto = {(a, art): float(e or 0) for a, art, e in cur.fetchall()}
            else:
                aviso = f"No pude unir EXIS_DISCRETOS ({', '.join(ce)}) con ARTICULOS_DISCRETOS ({', '.join(ca)})."
        else:
            aviso = "Esta base no tiene las tablas ARTICULOS_DISCRETOS / EXIS_DISCRETOS; se toma toda la existencia como sin lote/serie."

        filas = []
        for (alm, art), exis in existencia.items():
            con_ls = con_discreto.get((alm, art), 0.0)
            falta = round(exis - con_ls, 4)
            if exis > 0.0001 and falta > 0.0001:
                filas.append({"almacen_id": alm, "articulo_id": art, "existencia": round(exis, 4),
                              "con_lote_serie": round(con_ls, 4), "sin_lote_serie": falta,
                              "seguimiento": NOMBRE_SEGUIMIENTO.get(seguimiento[art], seguimiento[art])})

        ids = sorted({f["articulo_id"] for f in filas})
        nombres = {a: (n or "").strip() for a, n in _por_lotes(cur, "SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({})", ids)}
        claves = {}
        for a, c in _por_lotes(cur, "SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({})", ids):
            if a not in claves and c:
                claves[a] = c.strip()
        cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")
        almacenes = {a: (n or "").strip() for a, n in cur.fetchall()}
        for f in filas:
            f["clave"] = claves.get(f["articulo_id"], "")
            f["nombre"] = nombres.get(f["articulo_id"], "")
            f["sucursal"] = almacenes.get(f["almacen_id"], f"Almacén {f['almacen_id']}")
            f["estado"] = "Sin ningún lote/serie" if f["con_lote_serie"] <= 0.0001 else "Le faltan"
        filas.sort(key=lambda f: (f["sucursal"], f["nombre"]))
        return {"columna_seguimiento": col_seg, "valores_seguimiento": valores,
                "articulos_con_seguimiento": len(seguimiento), "aviso": aviso, "filas": filas}
    finally:
        con.close()
