"""
Inventarios a puerta abierta: lo que se lee (y lo poco que se escribe) en
Microsip para contar sin cerrar la sucursal.

Lectura (nunca mueve existencias):
- Producto por clave / código de barras: nombre, claves, seguimiento
  (lote / serie / ninguno), existencia en el almacén (CAPAS_COSTOS activas,
  mismo criterio que el resto del sistema), lotes o series con su caducidad
  y su existencia en ese almacén (ARTICULOS_DISCRETOS + EXIS_DISCRETOS).
- Ubicación, máximo, mínimo y punto de reorden (NIVELES_ARTICULOS).
- Última venta en ese almacén (Punto de Venta: DOCTOS_PV con su hora).
- Rotación: unidades vendidas en los últimos 90 días en ese almacén
  (Punto de Venta + Facturas/Remisiones de Ventas).

Escritura (lo único que toca Microsip): ubicación / máximo / mínimo /
reorden en NIVELES_ARTICULOS, cuando el usuario los captura al contar.
El ajuste de existencias NO se hace aquí: el inventario se revisa y se
aplica a mano en Microsip (Inventario físico).

Las columnas se leen del catálogo de Firebird, para no depender de la
versión de Microsip.
"""
import datetime

import microsip
import microsip_escritura as esc

SIN_SEGUIMIENTO = {"", "N", "NINGUNO", "0"}
NOMBRE_SEGUIMIENTO = {"L": "lote", "S": "serie"}
DIAS_ROTACION = 90


def _columnas(cur, tabla):
    cur.execute("""SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS
                   WHERE RDB$RELATION_NAME = ? ORDER BY RDB$FIELD_POSITION""", (tabla,))
    return [r[0] for r in cur.fetchall()]


def _primera(cols, *opciones, contiene=None):
    for o in opciones:
        if o in cols:
            return o
    if contiene:
        for c in cols:
            if contiene in c:
                return c
    return None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _fecha_iso(v):
    if v is None:
        return None
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10]
    t = str(v).strip()
    return t[:10] if t else None


# ------------------------------------------------------------------ lectura

def _articulo_id_por_clave(cur, clave):
    cur.execute("SELECT ARTICULO_ID FROM CLAVES_ARTICULOS WHERE CLAVE_ARTICULO = ?", (clave,))
    r = cur.fetchone()
    if r:
        return r[0]
    # A veces escanean con minúsculas o espacios.
    cur.execute("SELECT FIRST 1 ARTICULO_ID FROM CLAVES_ARTICULOS WHERE UPPER(TRIM(CLAVE_ARTICULO)) = ?", (clave.strip().upper(),))
    r = cur.fetchone()
    return r[0] if r else None


def _seguimiento(cur, articulo_id):
    cols = _columnas(cur, "ARTICULOS")
    col = _primera(cols, "SEGUIMIENTO", contiene="SEGUIM")
    if not col:
        return None
    cur.execute(f'SELECT TRIM("{col}") FROM ARTICULOS WHERE ARTICULO_ID = ?', (articulo_id,))
    r = cur.fetchone()
    v = ((r[0] if r else "") or "").strip().upper()
    return None if v in SIN_SEGUIMIENTO else v


def _lotes(cur, articulo_id, almacen_id):
    """[{lote, tipo, caducidad, existencia}] del artículo; existencia en ese almacén."""
    cur.execute("""SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
                   WHERE RDB$RELATION_NAME IN ('ARTICULOS_DISCRETOS', 'EXIS_DISCRETOS')""")
    if {r[0] for r in cur.fetchall()} != {"ARTICULOS_DISCRETOS", "EXIS_DISCRETOS"}:
        return []
    ca, ce = _columnas(cur, "ARTICULOS_DISCRETOS"), _columnas(cur, "EXIS_DISCRETOS")
    llave = next((c for c in ce if c.endswith("DISCRETO_ID") and c in ca), None)
    col_clave = _primera(ca, "CLAVE", contiene="CLAVE")
    col_cad = _primera(ca, "FECHA_CADUCIDAD", "CADUCIDAD", "FECHA", contiene="CADUC")
    col_tipo = _primera(ca, "TIPO")
    col_exis = _primera(ce, "EXISTENCIA", contiene="EXIS")
    if not (llave and col_clave):
        return []
    sel_cad = f'd."{col_cad}"' if col_cad else "NULL"
    sel_tipo = f'd."{col_tipo}"' if col_tipo else "NULL"
    sel_exis = f'COALESCE(e."{col_exis}", 0)' if col_exis else "0"
    cur.execute(f'''SELECT TRIM(d."{col_clave}"), {sel_tipo}, {sel_cad}, {sel_exis}
                    FROM ARTICULOS_DISCRETOS d
                    LEFT JOIN EXIS_DISCRETOS e ON e."{llave}" = d."{llave}" AND e.ALMACEN_ID = ?
                    WHERE d.ARTICULO_ID = ?''', (almacen_id, articulo_id))
    salida = {}
    for clave, tipo, cad, exis in cur.fetchall():
        if not clave:
            continue
        x = salida.setdefault(clave, {"lote": clave, "tipo": (tipo or "").strip() or None,
                                      "caducidad": _fecha_iso(cad), "existencia": 0.0})
        x["existencia"] += float(exis or 0)
    return sorted(salida.values(), key=lambda x: (x["existencia"] <= 0, x["caducidad"] or "9999", x["lote"]))


def _existencia_almacen(cur, articulo_id, almacen_id):
    cur.execute("""SELECT SUM(EXISTENCIA) FROM CAPAS_COSTOS
                   WHERE ARTICULO_ID = ? AND ALMACEN_ID = ? AND CAPA_AGOTADA = 'N'""", (articulo_id, almacen_id))
    r = cur.fetchone()
    return float(r[0] or 0) if r else 0.0


def _niveles(cur, articulo_id, almacen_id):
    cur.execute("SELECT 1 FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = 'NIVELES_ARTICULOS'")
    if not cur.fetchone():
        return None
    cols = _columnas(cur, "NIVELES_ARTICULOS")
    m = {
        "ubicacion": _primera(cols, "LOCALIZACION", "UBICACION", contiene="LOCALIZ"),
        "maximo": _primera(cols, "INVENTARIO_MAXIMO", "MAXIMO", contiene="MAXIMO"),
        "minimo": _primera(cols, "INVENTARIO_MINIMO", "MINIMO", contiene="MINIMO"),
        "reorden": _primera(cols, "PUNTO_REORDEN", "REORDEN", contiene="REORDEN"),
    }
    usadas = {k: v for k, v in m.items() if v}
    if not usadas or "ARTICULO_ID" not in cols or "ALMACEN_ID" not in cols:
        return None
    cur.execute(f'''SELECT {", ".join(f'"{c}"' for c in usadas.values())} FROM NIVELES_ARTICULOS
                    WHERE ARTICULO_ID = ? AND ALMACEN_ID = ?''', (articulo_id, almacen_id))
    r = cur.fetchone()
    salida = {k: None for k in m}
    if r:
        for (k, _c), v in zip(usadas.items(), r):
            if k == "ubicacion":
                salida[k] = (v or "").strip() or None
            else:
                salida[k] = _num(v)
    # Microsip guarda 0 cuando no se ha capturado: para la app eso es "no tiene".
    for k in ("maximo", "minimo", "reorden"):
        if salida[k] == 0:
            salida[k] = None
    salida["existe_registro"] = bool(r)
    return salida


def _ultima_venta(cur, articulo_id, almacen_id):
    cur.execute("""SELECT FIRST 1 p.FECHA, p.HORA, p.FOLIO FROM DOCTOS_PV_DET d
                   JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
                   WHERE d.ARTICULO_ID = ? AND p.ALMACEN_ID = ? AND p.FECHA_HORA_CANCELACION IS NULL
                   ORDER BY p.FECHA DESC, p.HORA DESC""", (articulo_id, almacen_id))
    r = cur.fetchone()
    if not r or not r[0]:
        return None
    fecha, hora, folio = r
    hhmm = hora.strftime("%H:%M") if hasattr(hora, "strftime") else (str(hora)[:5] if hora else None)
    return {"fecha": _fecha_iso(fecha), "hora": hhmm, "folio": (folio or "").strip() or None}


def _vendido(cur, articulo_id, almacen_id, desde):
    """Unidades vendidas desde 'desde' (date) en ese almacén: PV + Facturas/Remisiones."""
    total = 0.0
    cur.execute("""SELECT SUM(d.UNIDADES) FROM DOCTOS_PV_DET d JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
                   WHERE d.ARTICULO_ID = ? AND p.ALMACEN_ID = ? AND p.FECHA >= ? AND p.FECHA_HORA_CANCELACION IS NULL""",
                (articulo_id, almacen_id, desde))
    r = cur.fetchone()
    total += float(r[0] or 0) if r else 0
    try:
        if "ALMACEN_ID" in _columnas(cur, "DOCTOS_VE"):
            cur.execute("""SELECT SUM(d.UNIDADES) FROM DOCTOS_VE_DET d JOIN DOCTOS_VE p ON p.DOCTO_VE_ID = d.DOCTO_VE_ID
                           WHERE d.ARTICULO_ID = ? AND p.ALMACEN_ID = ? AND p.TIPO_DOCTO IN ('F', 'R')
                             AND p.FECHA >= ? AND p.FECHA_HORA_CANCELACION IS NULL""", (articulo_id, almacen_id, desde))
            r = cur.fetchone()
            total += float(r[0] or 0) if r else 0
    except Exception:  # noqa: BLE001 — sin módulo de Ventas o columnas distintas: solo cuenta PV
        pass
    return total


def rotacion(existencia, vendidas_90, niveles=None):
    """Semáforo para decidir si dejarle o quitarle producto a la sucursal."""
    diaria = (vendidas_90 or 0) / DIAS_ROTACION
    dias = round(existencia / diaria) if diaria > 0 and existencia > 0 else None
    reorden = (niveles or {}).get("reorden") or (niveles or {}).get("minimo")
    if existencia > 0 and not vendidas_90:
        return {"nivel": "sin_rotacion", "color": "#D8192F", "etiqueta": "Sin ventas en 90 días",
                "consejo": "Quítale producto o pásalo a otra sucursal", "dias_inventario": None}
    if reorden and existencia <= reorden and vendidas_90:
        return {"nivel": "surtir", "color": "#2563EB", "etiqueta": "Por debajo del reorden",
                "consejo": "Surtir: se vende y ya está bajo", "dias_inventario": dias}
    if dias is not None and dias > 180:
        return {"nivel": "baja", "color": "#EA580C", "etiqueta": f"Baja rotación (~{dias} días de inventario)",
                "consejo": "Tiene de más: reduce o no le surtas", "dias_inventario": dias}
    if dias is not None and dias > 90:
        return {"nivel": "lenta", "color": "#F59E0B", "etiqueta": f"Rotación lenta (~{dias} días)",
                "consejo": "Vigila; no le surtas de más", "dias_inventario": dias}
    if vendidas_90:
        return {"nivel": "buena", "color": "#16A34A", "etiqueta": f"Buena rotación{f' (~{dias} días)' if dias else ''}",
                "consejo": "Déjale producto", "dias_inventario": dias}
    return {"nivel": "sin_datos", "color": "#6B7280", "etiqueta": "Sin existencia ni ventas",
            "consejo": "", "dias_inventario": None}


def producto(config, almacen_id, clave=None, articulo_id=None):
    """Todo lo que la app necesita al escanear un producto en ese almacén."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        if articulo_id is None:
            articulo_id = _articulo_id_por_clave(cur, (clave or "").strip())
            if articulo_id is None:
                return None
        cur.execute("SELECT NOMBRE FROM ARTICULOS WHERE ARTICULO_ID = ?", (articulo_id,))
        r = cur.fetchone()
        if not r:
            return None
        cur.execute("SELECT CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID = ? ORDER BY CLAVE_ARTICULO_ID", (articulo_id,))
        claves = [x[0].strip() for x in cur.fetchall() if x[0]]
        seg = _seguimiento(cur, articulo_id)
        exis = _existencia_almacen(cur, articulo_id, almacen_id)
        niveles = _niveles(cur, articulo_id, almacen_id)
        desde = (datetime.date.today() - datetime.timedelta(days=DIAS_ROTACION)).isoformat()
        vendidas = _vendido(cur, articulo_id, almacen_id, desde)
        return {
            "articulo_id": articulo_id, "nombre": (r[0] or "").strip(), "claves": claves,
            "clave": (clave or "").strip() or (claves[0] if claves else None),
            "seguimiento": NOMBRE_SEGUIMIENTO.get(seg, seg.lower() if seg else None),
            "existencia_almacen": exis,
            "lotes": _lotes(cur, articulo_id, almacen_id) if seg else [],
            "niveles": niveles, "niveles_disponibles": niveles is not None,
            "ultima_venta": _ultima_venta(cur, articulo_id, almacen_id),
            "vendidas_90": vendidas, "rotacion": rotacion(exis, vendidas, niveles),
        }
    finally:
        con.close()


def buscar(config, texto, limite=25):
    """Buscador por nombre o clave (para cuando no hay código de barras)."""
    t = (texto or "").strip().upper()
    if len(t) < 2:
        return []
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        cur.execute(f"""SELECT FIRST {int(limite)} a.ARTICULO_ID, a.NOMBRE,
                               (SELECT FIRST 1 c.CLAVE_ARTICULO FROM CLAVES_ARTICULOS c WHERE c.ARTICULO_ID = a.ARTICULO_ID)
                        FROM ARTICULOS a
                        WHERE UPPER(a.NOMBRE) CONTAINING ? OR EXISTS (SELECT 1 FROM CLAVES_ARTICULOS c
                              WHERE c.ARTICULO_ID = a.ARTICULO_ID AND UPPER(c.CLAVE_ARTICULO) STARTING WITH ?)
                        ORDER BY a.NOMBRE""", (t, t))
        return [{"articulo_id": a, "nombre": (n or "").strip(), "clave": (c or "").strip() or None} for a, n, c in cur.fetchall()]
    finally:
        con.close()


def existencias_actuales(config, almacen_id, pares):
    """Para revisar al cerrar: {(articulo_id, lote|None): existencia actual},
    última venta por artículo y todos los lotes de cada artículo (para ver los
    que nadie contó). pares: [(articulo_id, lote|None)]."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        salida, ventas, todos = {}, {}, {}
        for art in {a for a, _ in pares}:
            todos[art] = _lotes(cur, art, almacen_id)
            lotes = {x["lote"]: x["existencia"] for x in todos[art]}
            for a, lote in pares:
                if a != art:
                    continue
                salida[(a, lote)] = lotes.get(lote, 0.0) if lote else _existencia_almacen(cur, art, almacen_id)
            ventas[art] = _ultima_venta(cur, art, almacen_id)
        return salida, ventas, todos
    finally:
        con.close()


def con_existencia_en_almacen(config, almacen_id):
    """{articulo_id: {"nombre", "clave", "existencia"}} de todo lo que Microsip
    dice que hay en ese almacén (para la lista de "faltan por contar")."""
    con = microsip._conectar(config)
    try:
        cur = con.cursor()
        cur.execute("""SELECT ARTICULO_ID, SUM(EXISTENCIA) FROM CAPAS_COSTOS
                       WHERE ALMACEN_ID = ? AND CAPA_AGOTADA = 'N' GROUP BY ARTICULO_ID HAVING SUM(EXISTENCIA) > 0""", (almacen_id,))
        exis = {a: float(e or 0) for a, e in cur.fetchall()}
        ids = sorted(exis)
        salida = {a: {"articulo_id": a, "nombre": None, "clave": None, "existencia": exis[a]} for a in ids}
        for i in range(0, len(ids), 400):
            lote = ids[i:i + 400]
            ph = ",".join("?" for _ in lote)
            cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({ph})", tuple(lote))
            for a, n in cur.fetchall():
                salida[a]["nombre"] = (n or "").strip()
            cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({ph}) ORDER BY CLAVE_ARTICULO_ID", tuple(lote))
            for a, c in cur.fetchall():
                if c and not salida[a]["clave"]:
                    salida[a]["clave"] = c.strip()
        return salida
    finally:
        con.close()


def almacenes(config):
    return microsip.listar_almacenes(config)


# ------------------------------------------------------------------ escritura

def guardar_niveles(config, articulo_id, almacen_id, datos, usuario=None):
    """Guarda en Microsip la ubicación / máximo / mínimo / reorden del artículo
    en ese almacén. Solo cambia lo que viene en datos (None = no tocar)."""
    con = esc._conectar(config)
    try:
        cur = con.cursor()
        esq = esc._Esquema(cur, usuario)
        cols = esq.columnas("NIVELES_ARTICULOS")
        if not cols:
            raise esc.ErrorMicrosip("Niveles", "Esta base de Microsip no tiene la tabla NIVELES_ARTICULOS")
        nombres = list(cols)
        m = {
            "ubicacion": _primera(nombres, "LOCALIZACION", "UBICACION", contiene="LOCALIZ"),
            "maximo": _primera(nombres, "INVENTARIO_MAXIMO", "MAXIMO", contiene="MAXIMO"),
            "minimo": _primera(nombres, "INVENTARIO_MINIMO", "MINIMO", contiene="MINIMO"),
            "reorden": _primera(nombres, "PUNTO_REORDEN", "REORDEN", contiene="REORDEN"),
        }
        valores = {m[k]: v for k, v in datos.items() if k in m and m[k] and v is not None}
        if not valores:
            return False
        cur.execute("SELECT COUNT(*) FROM NIVELES_ARTICULOS WHERE ARTICULO_ID = ? AND ALMACEN_ID = ?", (articulo_id, almacen_id))
        if cur.fetchone()[0]:
            sets = ", ".join(f'"{c}" = ?' for c in valores)
            cur.execute(f"UPDATE NIVELES_ARTICULOS SET {sets} WHERE ARTICULO_ID = ? AND ALMACEN_ID = ?",
                        list(valores.values()) + [articulo_id, almacen_id])
        else:
            id_col = next((c for c in nombres if c.endswith("_ID") and c not in ("ARTICULO_ID", "ALMACEN_ID")), None)
            plantilla = esq.fila("SELECT FIRST 1 * FROM NIVELES_ARTICULOS") or {}
            esc._insertar(esq, "NIVELES_ARTICULOS", {"ARTICULO_ID": articulo_id, "ALMACEN_ID": almacen_id, **valores},
                          plantilla=plantilla, id_col=id_col, generador="ID_CATALOGOS" if id_col else None)
        con.commit()
        return True
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
