"""
Conexión de solo lectura a Microsip (Firebird), por empresa.

Usa el paquete 'fdb' con una librería cliente (fbclient.so) empaquetada
en backend/lib/, para no depender de que el sistema donde corre el
servidor (Render) tenga Firebird instalado — cosa que no se puede en
el plan gratis.

La configuración (host, puerto, ruta de la base, usuario, password) se
guarda por empresa en la tabla `empresas` (ver db.obtener_config_microsip).
Típicamente el host/puerto apuntan a un túnel de ngrok que expone el
puerto 3050 de Firebird desde la computadora donde vive Microsip.
"""
import os
import re

import fdb

_LIB_DIR = os.path.join(os.path.dirname(__file__), "lib")
_FBCLIENT_PATH = os.path.join(_LIB_DIR, "libfbclient.so")

# fdb necesita que fbclient.so pueda resolver libtommath.so.1 — como no
# está instalado en el sistema, lo empaquetamos junto y lo agregamos al
# LD_LIBRARY_PATH del proceso antes de cargar la librería.
os.environ["LD_LIBRARY_PATH"] = _LIB_DIR + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")

_cargado = False


def _asegurar_cargado():
    global _cargado
    if not _cargado:
        fdb.load_api(_FBCLIENT_PATH)
        _cargado = True


def _dsn(config: dict) -> str:
    host = config["microsip_host"]
    puerto = config.get("microsip_puerto") or 3050
    ruta = config["microsip_ruta_db"]
    return f"{host}/{puerto}:{ruta}"


def _conectar(config: dict):
    _asegurar_cargado()
    return fdb.connect(dsn=_dsn(config), user=config["microsip_usuario"], password=config["microsip_password"])


def probar_conexion(config: dict):
    try:
        con = _conectar(config)
        con.close()
        return True, "Conexión exitosa."
    except Exception as e:
        return False, str(e)


def listar_tablas(config: dict):
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
        WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL
        ORDER BY 1
    """)
    tablas = [r[0] for r in cur.fetchall()]
    con.close()
    return tablas


def listar_columnas(config: dict, tabla: str):
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT TRIM(RF.RDB$FIELD_NAME), TRIM(F.RDB$FIELD_TYPE)
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
        WHERE RF.RDB$RELATION_NAME = ?
        ORDER BY RF.RDB$FIELD_POSITION
    """, (tabla.upper(),))
    columnas = [{"nombre": r[0], "tipo": r[1]} for r in cur.fetchall()]
    con.close()
    return columnas


def consultar_muestra(config: dict, tabla: str, limite: int = 20):
    con = _conectar(config)
    cur = con.cursor()
    # El nombre de tabla no viene parametrizable en SQL — se limita a
    # identificadores válidos para evitar inyección.
    if not re.match(r"^[A-Za-z0-9_$]+$", tabla):
        raise ValueError("Nombre de tabla inválido")
    cur.execute(f"SELECT FIRST {int(limite)} * FROM {tabla}")
    columnas = [d[0] for d in cur.description]
    filas = [dict(zip(columnas, row)) for row in cur.fetchall()]
    con.close()
    return filas


def buscar_pedido(config: dict, folio: str):
    """Busca un pedido de Microsip por folio y regresa cliente, dirección,
    teléfono y artículos — mismo criterio ya probado en importar_pedido.py:
    puede haber varios documentos con el mismo texto de folio (distinto
    TIPO_DOCTO); se prefiere el que sí tenga artículos capturados."""
    con = _conectar(config)
    cur = con.cursor()

    m = re.match(r"^([A-Za-z]*)0*(\d+)$", folio.strip())
    prefijo, numero = (m.group(1).upper(), m.group(2)) if m else ("", folio.strip())
    numero_norm = numero.lstrip("0") or "0"

    cur.execute("""
        SELECT FOLIO, DOCTO_PV_ID, CLIENTE_ID, TIPO_DOCTO
        FROM DOCTOS_PV
        WHERE FOLIO STARTING WITH ?
    """, (prefijo,))

    coincidencias = []
    for folio_db, docto_id, cli_id, tipo in cur.fetchall():
        resto = folio_db[len(prefijo):].lstrip("0") or "0"
        if resto == numero_norm:
            coincidencias.append((folio_db, docto_id, cli_id, tipo))

    if not coincidencias:
        con.close()
        return None

    mejor = None
    mejor_num_items = -1
    for folio_db, docto_id, cli_id, tipo in coincidencias:
        cur.execute("SELECT COUNT(*) FROM DOCTOS_PV_DET WHERE DOCTO_PV_ID = ?", (docto_id,))
        num_items = cur.fetchone()[0]
        if num_items > mejor_num_items or (num_items == mejor_num_items and (mejor is None or docto_id > mejor[1])):
            mejor_num_items = num_items
            mejor = (folio_db, docto_id, cli_id, tipo)

    folio_db, docto_pv_id, cliente_id, tipo_docto = mejor

    cur.execute("SELECT NOMBRE FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
    cliente_row = cur.fetchone()
    cliente_nombre = cliente_row[0] if cliente_row else ""

    cur.execute("""
        SELECT NOMBRE_CALLE, NUM_EXTERIOR, NUM_INTERIOR, COLONIA, POBLACION, TELEFONO1
        FROM DIRS_CLIENTES
        WHERE CLIENTE_ID = ?
        ORDER BY ES_DIR_PPAL DESC
    """, (cliente_id,))
    dir_row = cur.fetchone()

    if dir_row:
        calle, num_ext, num_int, colonia, poblacion, telefono = dir_row
        partes = [
            f"{(calle or '').strip()} {(num_ext or '').strip()}".strip(),
            (f"Int. {num_int.strip()}" if num_int else None),
            (colonia or "").strip() or None,
            (poblacion or "").strip() or None,
        ]
        direccion = ", ".join(p for p in partes if p)
        telefono = (telefono or "").strip()
    else:
        direccion = ""
        telefono = ""

    cur.execute("""
        SELECT COALESCE(A.NOMBRE, P.CLAVE_ARTICULO, '(sin descripción)'),
               P.UNIDADES, P.UNIDADES_SURT, P.UNIDADES_A_SURTIR
        FROM DOCTOS_PV_DET P
        LEFT JOIN ARTICULOS A ON A.ARTICULO_ID = P.ARTICULO_ID
        WHERE P.DOCTO_PV_ID = ?
    """, (docto_pv_id,))
    partidas = cur.fetchall()
    con.close()

    piezas_descripcion = []
    checklist_items = []
    pendiente_de_surtir = False
    for i, (desc, unidades, surtido, por_surtir) in enumerate(partidas):
        unidades = unidades or 0
        surtido = surtido or 0
        por_surtir = por_surtir if por_surtir is not None else (unidades - surtido)
        nombre = (desc or "").strip()

        if por_surtir and por_surtir > 0:
            # Lo que realmente se va a entregar HOY es lo pendiente, no el
            # total del pedido — el checklist se arma con esa cantidad.
            texto_item = f"{por_surtir:g} x {nombre} (pendiente"
            if surtido > 0:
                texto_item += f" — ya se entregaron {surtido:g} de {unidades:g} antes"
            texto_item += ")"
            etiqueta = f"{por_surtir:g} x {nombre} (faltan {por_surtir:g} por surtir de {unidades:g})"
            pendiente_de_surtir = True
        else:
            texto_item = f"{unidades:g} x {nombre} (completo)"
            etiqueta = f"{unidades:g} x {nombre}"

        piezas_descripcion.append(etiqueta)
        checklist_items.append({"texto": texto_item, "orden": i, "obligatorio": True})

    equipo_descripcion = "; ".join(piezas_descripcion) or "(sin partidas)"
    if pendiente_de_surtir:
        equipo_descripcion += "  ⚠️ Este pedido tiene artículos pendientes de surtir."

    return {
        "folio_encontrado": folio_db,
        "cliente_nombre": (cliente_nombre or "").strip(),
        "cliente_direccion": direccion,
        "cliente_telefono": telefono,
        "equipo_descripcion": equipo_descripcion,
        "checklist_items": checklist_items,
    }
