"""
Historial de cambios de Microsip: quién creó un documento o artículo y TODAS
las modificaciones, no solo la última.

Microsip solo guarda USUARIO_CREADOR y USUARIO_ULT_MODIF (el último que lo
tocó). Para tener el historial completo, tickets-ti revisa Microsip cada pocos
minutos (solo lectura): cada registro cuya FECHA_HORA_ULT_MODIF cambió se
compara con la foto anterior guardada en Postgres y se anota quién lo cambió,
cuándo y qué cambió (encabezado y partidas).

Limitaciones:
- Empieza a registrar desde que se instala; lo anterior Microsip no lo guarda.
- Si alguien modifica el mismo documento dos veces entre una revisión y otra,
  o mientras no hay conexión con Microsip, solo se ve el último de esos cambios.

Los nombres de columnas se leen del catálogo de Firebird para no depender de la
versión de Microsip.
"""
import microsip

# Fuentes que se vigilan. 'tipo' es la columna que dice qué documento es.
FUENTES = {
    "ve": {"nombre": "Ventas", "tabla": "DOCTOS_VE", "id": "DOCTO_VE_ID", "det": "DOCTOS_VE_DET",
           "tipo": "TIPO_DOCTO", "tercero": ("CLIENTE_ID", "CLIENTES", "CLIENTE_ID", "Cliente"),
           "tipos": {"C": "Cotización", "P": "Pedido", "R": "Remisión", "F": "Factura", "D": "Devolución", "V": "Devolución"}},
    "cm": {"nombre": "Compras", "tabla": "DOCTOS_CM", "id": "DOCTO_CM_ID", "det": "DOCTOS_CM_DET",
           "tipo": "TIPO_DOCTO", "tercero": ("PROVEEDOR_ID", "PROVEEDORES", "PROVEEDOR_ID", "Proveedor"),
           "tipos": {"O": "Orden de compra", "R": "Recepción de mercancía", "C": "Compra", "D": "Devolución de compra"}},
    "in": {"nombre": "Inventarios", "tabla": "DOCTOS_IN", "id": "DOCTO_IN_ID", "det": "DOCTOS_IN_DET",
           "tipo": "NATURALEZA_CONCEPTO", "tercero": ("ALMACEN_ID", "ALMACENES", "ALMACEN_ID", "Almacén"),
           "tipos": {"E": "Entrada de inventario", "S": "Salida de inventario"}},
    "art": {"nombre": "Artículos", "tabla": "ARTICULOS", "id": "ARTICULO_ID", "det": None, "tipo": None, "tercero": None,
            "tipos": {}},
    "cli": {"nombre": "Clientes", "tabla": "CLIENTES", "id": "CLIENTE_ID", "det": None, "tipo": None, "tercero": None,
            "tipos": {}},
}

# Catálogos para traducir *_ID a su nombre al mostrar un cambio.
CATALOGOS = {
    "CLIENTE_ID": ("CLIENTES", "CLIENTE_ID"), "PROVEEDOR_ID": ("PROVEEDORES", "PROVEEDOR_ID"),
    "ALMACEN_ID": ("ALMACENES", "ALMACEN_ID"), "ALMACEN_DESTINO_ID": ("ALMACENES", "ALMACEN_ID"),
    "VENDEDOR_ID": ("VENDEDORES", "VENDEDOR_ID"), "SUCURSAL_ID": ("SUCURSALES", "SUCURSAL_ID"),
    "COND_PAGO_ID": ("CONDICIONES_PAGO", "COND_PAGO_ID"), "LINEA_ARTICULO_ID": ("LINEAS_ARTICULOS", "LINEA_ARTICULO_ID"),
    "ZONA_CLIENTE_ID": ("ZONAS_CLIENTES", "ZONA_CLIENTE_ID"), "TIPO_CLIENTE_ID": ("TIPOS_CLIENTES", "TIPO_CLIENTE_ID"),
    "MONEDA_ID": ("MONEDAS", "MONEDA_ID"), "CONCEPTO_IN_ID": ("CONCEPTOS_IN", "CONCEPTO_IN_ID"),
}

ETIQUETAS = {
    "FOLIO": "Folio", "FECHA": "Fecha", "ESTATUS": "Estatus", "DESCRIPCION": "Descripción", "IMPORTE_NETO": "Importe neto",
    "TOTAL_IMPUESTOS": "Impuestos", "CLIENTE_ID": "Cliente", "PROVEEDOR_ID": "Proveedor", "ALMACEN_ID": "Almacén",
    "ALMACEN_DESTINO_ID": "Almacén destino", "VENDEDOR_ID": "Vendedor", "SUCURSAL_ID": "Sucursal", "COND_PAGO_ID": "Condición de pago",
    "NOMBRE": "Nombre", "UNIDADES": "Unidades", "PRECIO_UNITARIO": "Precio unitario", "PCTJE_DSCTO": "% descuento",
    "PRECIO_TOTAL_NETO": "Importe", "COSTO_UNITARIO": "Costo unitario", "COSTO_TOTAL": "Costo total", "NOTAS": "Notas",
    "UNIDAD_VENTA": "Unidad de venta", "UNIDAD_COMPRA": "Unidad de compra", "LINEA_ARTICULO_ID": "Línea",
    "LIMITE_CREDITO": "Límite de crédito", "MONEDA_ID": "Moneda", "CONCEPTO_IN_ID": "Concepto", "TIPO_DOCTO": "Tipo",
}

LIMITE_POR_REVISION = 3000


def etiqueta(col):
    return ETIQUETAS.get(col) or col.replace("_", " ").capitalize()


def _columnas(cur, tabla):
    """Columnas que no son BLOB (los BLOB pueden pesar mucho y casi nunca importan aquí)."""
    cur.execute("""SELECT TRIM(rf.RDB$FIELD_NAME), f.RDB$FIELD_TYPE FROM RDB$RELATION_FIELDS rf
                   JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
                   WHERE rf.RDB$RELATION_NAME = ? ORDER BY rf.RDB$FIELD_POSITION""", (tabla,))
    return [c for c, t in cur.fetchall() if t != 261]


def _txt(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ")[:19] if hasattr(v, "hour") else v.isoformat()
    if isinstance(v, float) or type(v).__name__ == "Decimal":
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:.4f}".rstrip("0").rstrip(".")
    return str(v).strip()


def _por_lotes(cur, sql, ids, tam=400):
    salida = []
    ids = list(ids)
    for i in range(0, len(ids), tam):
        lote = ids[i:i + tam]
        cur.execute(sql.format(",".join("?" for _ in lote)), tuple(lote))
        salida.extend(cur.fetchall())
    return salida


class _Esquema:
    """Columnas reales de cada fuente en ESTA base de Microsip."""

    def __init__(self, cur, fuente):
        f = FUENTES[fuente]
        self.f = f
        self.cols = _columnas(cur, f["tabla"])
        need = {f["id"], "USUARIO_ULT_MODIF", "FECHA_HORA_ULT_MODIF"}
        self.ok = need.issubset(self.cols)
        self.tiene = lambda c: c in self.cols
        self.det_cols = []
        if f["det"]:
            dc = _columnas(cur, f["det"])
            if f["id"] in dc:
                self.det_cols = dc
        self.det_id = next((c for c in self.det_cols if c.endswith("_DET_ID")), None)


def _excluir(col, f):
    return col.startswith("USUARIO_") or col.startswith("FECHA_HORA_") or col == f["id"]


def _ahora_microsip(cur):
    cur.execute("SELECT CURRENT_TIMESTAMP FROM RDB$DATABASE")
    return cur.fetchone()[0]


def _fotos(cur, esq, filas):
    """Arma la foto (encabezado + partidas) de cada fila leída de la tabla."""
    f = esq.f
    fotos = {}
    for fila in filas:
        r = dict(zip(esq.cols, fila))
        fotos[r[f["id"]]] = {
            "h": {c: _txt(v) for c, v in r.items() if not _excluir(c, f)},
            "d": [],
            "creador": _txt(r.get("USUARIO_CREADOR")), "creado": _txt(r.get("FECHA_HORA_CREACION")),
            "ult_usuario": _txt(r.get("USUARIO_ULT_MODIF")), "ult": _txt(r.get("FECHA_HORA_ULT_MODIF")),
            "cancelado": _txt(r.get("FECHA_HORA_CANCELACION")), "cancelo": _txt(r.get("USUARIO_CANCELACION")),
            "_ult_raw": r.get("FECHA_HORA_ULT_MODIF"),
        }
    if esq.det_cols and fotos:
        lista = ", ".join(f'"{c}"' for c in esq.det_cols)
        orden = f' ORDER BY "{esq.det_id}"' if esq.det_id else ""
        for fila in _por_lotes(cur, f'SELECT {lista} FROM {f["det"]} WHERE "{f["id"]}" IN ({{}}){orden}', fotos.keys()):
            r = dict(zip(esq.det_cols, fila))
            d = {c: _txt(v) for c, v in r.items() if c not in (f["id"], esq.det_id) and not c.startswith("USUARIO_")}
            fotos[r[f["id"]]]["d"].append(d)
    return fotos


def leer_cambios(config, fuente, desde):
    """Registros de la fuente modificados (o cancelados) desde 'desde'.
    Regresa (fotos, nuevo_desde, ahora_microsip). Si 'desde' es None, revisa el último día."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        esq = _Esquema(cur, fuente)
        if not esq.ok:
            return {}, desde, None
        ahora = _ahora_microsip(cur)
        if desde is None:
            from datetime import timedelta
            desde = ahora - timedelta(days=1)
        f = esq.f
        lista = ", ".join(f'"{c}"' for c in esq.cols)
        cond = "FECHA_HORA_ULT_MODIF >= ?"
        params = [desde]
        if esq.tiene("FECHA_HORA_CANCELACION"):
            cond = f"({cond} OR FECHA_HORA_CANCELACION >= ?)"
            params.append(desde)
        cur.execute(f"SELECT FIRST {LIMITE_POR_REVISION} {lista} FROM {f['tabla']} WHERE {cond} ORDER BY FECHA_HORA_ULT_MODIF",
                    tuple(params))
        filas = cur.fetchall()
        fotos = _fotos(cur, esq, filas)
        marcas = [x["_ult_raw"] for x in fotos.values() if x["_ult_raw"] is not None]
        nuevo = max(marcas) if marcas else desde
        if len(filas) >= LIMITE_POR_REVISION and marcas and min(marcas) == nuevo:
            # Miles de registros con la misma hora (cambio masivo): se avanza un poco para no atorarse.
            from datetime import timedelta
            nuevo = nuevo + timedelta(milliseconds=1)
        if nuevo > ahora:
            nuevo = ahora
        for x in fotos.values():
            x.pop("_ult_raw", None)
        return fotos, nuevo, ahora
    finally:
        con.close()


def comparar(antes, despues):
    """Lista de cambios legibles entre dos fotos (sin traducir IDs todavía)."""
    cambios = []
    for c in sorted(set(antes["h"]) | set(despues["h"])):
        a, b = antes["h"].get(c), despues["h"].get(c)
        if a != b:
            cambios.append({"campo": c, "antes": a, "despues": b})

    def llave(d, i):
        return (d.get("ARTICULO_ID") or d.get("CLAVE_ARTICULO") or "?", d.get("POSICION") or "")

    def agrupar(lineas):
        g = {}
        for d in lineas:
            k = llave(d, 0)
            g.setdefault(k, []).append(d)
        return g

    ga, gb = agrupar(antes.get("d") or []), agrupar(despues.get("d") or [])
    for k in list(ga.keys()) + [k for k in gb if k not in ga]:
        la, lb = ga.get(k, []), gb.get(k, [])
        for i in range(max(len(la), len(lb))):
            da = la[i] if i < len(la) else None
            db_ = lb[i] if i < len(lb) else None
            art = (db_ or da).get("ARTICULO_ID")
            if da is None:
                cambios.append({"partida": art, "tipo": "agregada", "despues": _resumen_linea(db_)})
            elif db_ is None:
                cambios.append({"partida": art, "tipo": "quitada", "antes": _resumen_linea(da)})
            elif da != db_:
                difs = [f"{etiqueta(c)}: {da.get(c) if da.get(c) is not None else '—'} → {db_.get(c) if db_.get(c) is not None else '—'}"
                        for c in sorted(set(da) | set(db_)) if da.get(c) != db_.get(c)]
                cambios.append({"partida": art, "tipo": "modificada", "detalle": "; ".join(difs)})
    return cambios


def _resumen_linea(d):
    partes = []
    for c in ("UNIDADES", "PRECIO_UNITARIO", "PCTJE_DSCTO", "PRECIO_TOTAL_NETO", "COSTO_UNITARIO"):
        if d.get(c) not in (None, "", "0"):
            partes.append(f"{etiqueta(c)} {d[c]}")
    return ", ".join(partes)


def traducir(config, cambios_por_evento):
    """Pone nombre a los IDs (cliente, almacén, artículo de la partida…) de una lista de cambios."""
    ids_cat = {}
    arts = set()
    for cambios in cambios_por_evento:
        for c in cambios or []:
            if c.get("campo") in CATALOGOS:
                for v in (c.get("antes"), c.get("despues")):
                    if v and str(v).isdigit():
                        ids_cat.setdefault(c["campo"], set()).add(int(v))
            if c.get("partida") and str(c["partida"]).isdigit():
                arts.add(int(c["partida"]))
    nombres = {}
    art_nom = {}
    if not ids_cat and not arts:
        return nombres, art_nom
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        for campo, ids in ids_cat.items():
            tabla, llave = CATALOGOS[campo]
            try:
                for i, n in _por_lotes(cur, f'SELECT "{llave}", NOMBRE FROM {tabla} WHERE "{llave}" IN ({{}})', ids):
                    nombres[(campo, str(i))] = (n or "").strip()
            except Exception:
                pass
        if arts:
            for i, n in _por_lotes(cur, "SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({})", arts):
                art_nom[str(i)] = {"nombre": (n or "").strip(), "clave": ""}
            try:
                for i, c in _por_lotes(cur, "SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({})", arts):
                    if str(i) in art_nom and not art_nom[str(i)]["clave"] and c:
                        art_nom[str(i)]["clave"] = c.strip()
            except Exception:
                pass
    finally:
        con.close()
    return nombres, art_nom


# ------------------------------------------------------------------ búsqueda en vivo

def _fila_actual(cur, esq, fuente, r):
    f = esq.f
    tipo = r.get(f["tipo"]) if f["tipo"] else None
    tipo = (tipo or "").strip() if isinstance(tipo, str) else tipo
    return {
        "fuente": fuente, "fuente_nombre": f["nombre"], "registro_id": r[f["id"]],
        "folio": _txt(r.get("FOLIO")) or "", "nombre": _txt(r.get("NOMBRE")) or "",
        "tipo": tipo, "tipo_nombre": f["tipos"].get(tipo, f"Tipo {tipo}" if tipo else f["nombre"][:-1] if fuente in ("art", "cli") else ""),
        "fecha": _txt(r.get("FECHA")),
        "estatus": _txt(r.get("ESTATUS")),
        "creador": _txt(r.get("USUARIO_CREADOR")), "creado": _txt(r.get("FECHA_HORA_CREACION")),
        "ult_usuario": _txt(r.get("USUARIO_ULT_MODIF")), "ult": _txt(r.get("FECHA_HORA_ULT_MODIF")),
        "cancelo": _txt(r.get("USUARIO_CANCELACION")), "cancelado": _txt(r.get("FECHA_HORA_CANCELACION")),
        "tercero_id": r.get(f["tercero"][0]) if f["tercero"] else None,
    }


def _con_terceros(cur, fuente, filas):
    f = FUENTES[fuente]
    if not f["tercero"] or not filas:
        return filas
    _, tabla, llave, titulo = f["tercero"]
    ids = {x["tercero_id"] for x in filas if x["tercero_id"]}
    try:
        nombres = {i: (n or "").strip() for i, n in _por_lotes(cur, f'SELECT "{llave}", NOMBRE FROM {tabla} WHERE "{llave}" IN ({{}})', ids)}
    except Exception:
        nombres = {}
    for x in filas:
        x["tercero_titulo"] = titulo
        x["tercero"] = nombres.get(x["tercero_id"], "")
    return filas


def buscar(config, fuente, texto, tipo=None, limite=40):
    """Busca en Microsip (en vivo) por folio (documentos), clave/nombre (artículos) o nombre (clientes)."""
    if fuente not in FUENTES:
        raise ValueError("Fuente inválida")
    texto = (texto or "").strip()
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        esq = _Esquema(cur, fuente)
        f = esq.f
        lista = ", ".join(f'"{c}"' for c in esq.cols)
        cond, params = [], []
        if fuente == "art":
            ids = []
            if texto:
                cur.execute("SELECT FIRST 200 ARTICULO_ID FROM CLAVES_ARTICULOS WHERE CLAVE_ARTICULO CONTAINING ?", (texto,))
                ids = [r[0] for r in cur.fetchall()]
            cond.append("(NOMBRE CONTAINING ?" + (f" OR ARTICULO_ID IN ({','.join('?' for _ in ids)})" if ids else "") + ")")
            params += [texto] + ids
        elif fuente == "cli":
            cond.append("NOMBRE CONTAINING ?")
            params.append(texto)
        else:
            if texto:
                cond.append("FOLIO CONTAINING ?")
                params.append(texto)
            if tipo and f["tipo"] and esq.tiene(f["tipo"]):
                cond.append(f'"{f["tipo"]}" = ?')
                params.append(tipo)
        where = (" WHERE " + " AND ".join(cond)) if cond else ""
        orden = "FECHA DESC" if esq.tiene("FECHA") else f'"{f["id"]}" DESC'
        cur.execute(f"SELECT FIRST {int(limite)} {lista} FROM {f['tabla']}{where} ORDER BY {orden}", tuple(params))
        filas = [_fila_actual(cur, esq, fuente, dict(zip(esq.cols, r))) for r in cur.fetchall()]
        if fuente == "art" and filas:
            claves = {}
            for i, c in _por_lotes(cur, "SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({})",
                                   [x["registro_id"] for x in filas]):
                claves.setdefault(i, (c or "").strip())
            for x in filas:
                x["folio"] = claves.get(x["registro_id"], "")
        return _con_terceros(cur, fuente, filas)
    finally:
        con.close()


def actual(config, fuente, registro_id):
    """El registro tal como está hoy en Microsip (creador, último que lo modificó, partidas)."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        esq = _Esquema(cur, fuente)
        f = esq.f
        lista = ", ".join(f'"{c}"' for c in esq.cols)
        cur.execute(f'SELECT {lista} FROM {f["tabla"]} WHERE "{f["id"]}" = ?', (registro_id,))
        fila = cur.fetchone()
        if not fila:
            return None
        r = dict(zip(esq.cols, fila))
        x = _con_terceros(cur, fuente, [_fila_actual(cur, esq, fuente, r)])[0]
        if fuente == "art":
            cur.execute("SELECT FIRST 1 CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID = ?", (registro_id,))
            c = cur.fetchone()
            x["folio"] = (c[0] or "").strip() if c else ""
        x["foto"] = _fotos(cur, esq, [fila])[registro_id]
        x["foto"].pop("_ult_raw", None)
        return x
    finally:
        con.close()
