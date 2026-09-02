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


def consultar_muestra(config: dict, tabla: str, limite: int = 20, columna_filtro: str = None, valor_filtro: str = None,
                       mas_recientes: bool = False, columna_fecha: str = None, fecha_desde: str = None, fecha_hasta: str = None):
    con = _conectar(config)
    cur = con.cursor()
    # El nombre de tabla/columna no viene parametrizable en SQL — se limita a
    # identificadores válidos para evitar inyección.
    if not re.match(r"^[A-Za-z0-9_$]+$", tabla):
        raise ValueError("Nombre de tabla inválido")

    condiciones = []
    parametros = []
    if columna_filtro and valor_filtro:
        if not re.match(r"^[A-Za-z0-9_$]+$", columna_filtro):
            raise ValueError("Nombre de columna inválido")
        # CONTAINING busca la coincidencia sin importar mayúsculas/minúsculas
        # ni si el valor está en medio del texto — funciona tanto para
        # folios exactos como para nombres parciales.
        condiciones.append(f"{columna_filtro} CONTAINING ?")
        parametros.append(valor_filtro)
    if columna_fecha and (fecha_desde or fecha_hasta):
        if not re.match(r"^[A-Za-z0-9_$]+$", columna_fecha):
            raise ValueError("Nombre de columna de fecha inválido")
        if fecha_desde:
            condiciones.append(f"{columna_fecha} >= ?")
            parametros.append(fecha_desde)
        if fecha_hasta:
            condiciones.append(f"{columna_fecha} < ?")
            parametros.append(fecha_hasta)

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    # Ordenar por la primera columna (normalmente el ID autoincremental)
    # descendente es una forma genérica de traer "lo más reciente" sin
    # tener que adivinar si la tabla tiene una columna FECHA y cómo se
    # llama exactamente.
    orden = " ORDER BY 1 DESC" if mas_recientes else ""
    cur.execute(f"SELECT FIRST {int(limite)} * FROM {tabla}{where}{orden}", tuple(parametros))
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
        SELECT FOLIO, DOCTO_VE_ID, CLIENTE_ID, TIPO_DOCTO, DESCRIPCION
        FROM DOCTOS_VE
        WHERE FOLIO STARTING WITH ?
    """, (prefijo,))

    coincidencias = []
    for folio_db, docto_id, cli_id, tipo, descripcion_docto in cur.fetchall():
        resto = folio_db[len(prefijo):].lstrip("0") or "0"
        if resto == numero_norm:
            coincidencias.append((folio_db, docto_id, cli_id, tipo, descripcion_docto))

    if not coincidencias:
        # Autodiagnóstico: en vez de solo decir "no encontrado", mostramos
        # qué SÍ hay con ese prefijo — así se ve de inmediato si el problema
        # es el prefijo, el número, o que de plano no existe ese folio.
        cur.execute("SELECT FIRST 8 FOLIO FROM DOCTOS_VE WHERE FOLIO STARTING WITH ?", (prefijo,))
        ejemplos = [r[0] for r in cur.fetchall()]
        con.close()
        if ejemplos:
            raise ValueError(
                f"No hay ningún folio '{prefijo}' que numéricamente coincida con '{numero}'. "
                f"Folios que sí existen con el prefijo '{prefijo}': {', '.join(ejemplos)}"
            )
        raise ValueError(f"No existe ningún folio en Microsip que empiece con '{prefijo}' (se interpretó tu búsqueda '{folio}' como prefijo='{prefijo}' + número='{numero}').")

    mejor = None
    mejor_num_items = -1
    for folio_db, docto_id, cli_id, tipo, descripcion_docto in coincidencias:
        cur.execute("SELECT COUNT(*) FROM DOCTOS_VE_DET WHERE DOCTO_VE_ID = ?", (docto_id,))
        num_items = cur.fetchone()[0]
        if num_items > mejor_num_items or (num_items == mejor_num_items and (mejor is None or docto_id > mejor[1])):
            mejor_num_items = num_items
            mejor = (folio_db, docto_id, cli_id, tipo, descripcion_docto)

    folio_db, docto_pv_id, cliente_id, tipo_docto, descripcion_docto = mejor

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
               P.UNIDADES, P.UNIDADES_SURT_DEV, P.UNIDADES_A_SURTIR
        FROM DOCTOS_VE_DET P
        LEFT JOIN ARTICULOS A ON A.ARTICULO_ID = P.ARTICULO_ID
        WHERE P.DOCTO_VE_ID = ?
    """, (docto_pv_id,))
    partidas = cur.fetchall()
    con.close()

    piezas_descripcion = []
    checklist_items = []
    pendiente_de_surtir = False
    total_articulos = 0
    total_piezas_a_entregar = 0
    for i, (desc, unidades, surtido, por_surtir) in enumerate(partidas):
        unidades = unidades or 0
        surtido = surtido or 0
        por_surtir = por_surtir if por_surtir is not None else (unidades - surtido)
        nombre = (desc or "").strip()
        total_articulos += 1

        if por_surtir and por_surtir > 0:
            # Lo que realmente se va a entregar HOY es lo pendiente, no el
            # total del pedido — el checklist se arma con esa cantidad.
            texto_item = f"{por_surtir:g} x {nombre} (pendiente"
            if surtido > 0:
                texto_item += f" — ya se entregaron {surtido:g} de {unidades:g} antes"
            texto_item += ")"
            etiqueta = f"{por_surtir:g} x {nombre} (faltan {por_surtir:g} por surtir de {unidades:g})"
            pendiente_de_surtir = True
            total_piezas_a_entregar += por_surtir
        else:
            texto_item = f"{unidades:g} x {nombre} (completo)"
            etiqueta = f"{unidades:g} x {nombre}"
            total_piezas_a_entregar += unidades

        piezas_descripcion.append(etiqueta)
        checklist_items.append({"texto": texto_item, "orden": i, "obligatorio": True})

    resumen_cantidad = (
        f"{total_articulos:g} artículo{'s' if total_articulos != 1 else ''}, "
        f"{total_piezas_a_entregar:g} pieza{'s' if total_piezas_a_entregar != 1 else ''} en total a entregar. "
    )
    equipo_descripcion = resumen_cantidad + ("; ".join(piezas_descripcion) or "(sin partidas)")
    if pendiente_de_surtir:
        equipo_descripcion += "  ⚠️ Este pedido tiene artículos pendientes de surtir."

    return {
        "folio_encontrado": folio_db,
        "cliente_nombre": (cliente_nombre or "").strip(),
        "cliente_direccion": direccion,
        "cliente_telefono": telefono,
        "equipo_descripcion": equipo_descripcion,
        "checklist_items": checklist_items,
        "descripcion_pedido": (descripcion_docto or "").strip() or None,
    }


def buscar_clientes(config: dict, texto: str, campo: str = "nombre", limite: int = 20):
    """Busca clientes de Microsip por nombre o por teléfono (búsqueda
    parcial, insensible a mayúsculas) — usado por el buscador de clientes
    (F4 / botón) al crear una reparación."""
    texto = (texto or "").strip()
    if not texto:
        return []
    con = _conectar(config)
    cur = con.cursor()

    if campo == "telefono":
        # Traemos varios de más y quitamos duplicados en Python (un
        # cliente puede tener más de una dirección/teléfono registrado).
        cur.execute(f"""
            SELECT FIRST {int(limite) * 3} D.CLIENTE_ID, C.NOMBRE
            FROM DIRS_CLIENTES D
            JOIN CLIENTES C ON C.CLIENTE_ID = D.CLIENTE_ID
            WHERE D.TELEFONO1 CONTAINING ?
            ORDER BY C.NOMBRE
        """, (texto,))
        vistos = set()
        filas = []
        for cliente_id, nombre in cur.fetchall():
            if cliente_id not in vistos:
                vistos.add(cliente_id)
                filas.append((cliente_id, nombre))
            if len(filas) >= limite:
                break
    else:
        cur.execute(
            f"SELECT FIRST {int(limite)} CLIENTE_ID, NOMBRE FROM CLIENTES WHERE NOMBRE CONTAINING ? ORDER BY NOMBRE",
            (texto,),
        )
        filas = cur.fetchall()

    resultados = []
    for cliente_id, nombre in filas:
        cur.execute("""
            SELECT NOMBRE_CALLE, NUM_EXTERIOR, COLONIA, POBLACION, TELEFONO1
            FROM DIRS_CLIENTES
            WHERE CLIENTE_ID = ?
            ORDER BY ES_DIR_PPAL DESC
        """, (cliente_id,))
        dir_row = cur.fetchone()
        if dir_row:
            calle, num_ext, colonia, poblacion, telefono = dir_row
            partes = [
                f"{(calle or '').strip()} {(num_ext or '').strip()}".strip(),
                (colonia or "").strip() or None,
                (poblacion or "").strip() or None,
            ]
            direccion = ", ".join(p for p in partes if p)
            telefono = (telefono or "").strip()
        else:
            direccion, telefono = "", ""
        resultados.append({
            "cliente_id": cliente_id,
            "nombre": (nombre or "").strip(),
            "direccion": direccion,
            "telefono": telefono,
        })
    con.close()
    return resultados


# =============================================================================
# CHECADOR DE PRECIO (costo + existencia real por almacén, disponible vs
# comprometido) — usa CLAVES_ARTICULOS (clave/código de barras -> artículo),
# ARTICULOS (nombre), CAPAS_COSTOS (existencia y costo por almacén, método
# de capas de Microsip) y COMPROM_ARTICULOS (piezas comprometidas por almacén).
# =============================================================================

def _consultar_producto_por_articulo_id(cur, articulo_id):
    cur.execute("SELECT NOMBRE FROM ARTICULOS WHERE ARTICULO_ID = ?", (articulo_id,))
    row = cur.fetchone()
    if not row:
        return None
    nombre = (row[0] or "").strip()

    cur.execute(
        "SELECT CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID = ? ORDER BY CLAVE_ARTICULO_ID",
        (articulo_id,),
    )
    claves = [r[0] for r in cur.fetchall() if r[0]]

    # Precio de lista (lo que se le cobra al cliente). PRECIOS_ARTICULOS
    # guarda el precio SIN impuesto — se le agrega el 16% de IVA estándar
    # para mostrar el precio final, igual que Microsip lo muestra en la
    # pantalla del artículo ("Precio con impuesto").
    cur.execute("SELECT FIRST 1 PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID = ?", (articulo_id,))
    fila_precio = cur.fetchone()
    precio_sin_impuesto = float(fila_precio[0]) if fila_precio and fila_precio[0] is not None else None
    precio_con_impuesto = round(precio_sin_impuesto * 1.16, 2) if precio_sin_impuesto is not None else None

    # Solo las capas de costo NO agotadas cuentan como existencia real.
    # Un artículo puede tener varias capas (compras en distintas fechas a
    # distinto precio) — para "el costo" usamos la MÁS RECIENTE (mayor
    # CAPA_ID), no el promedio de todas: promediar con capas viejas y
    # baratas que aún tienen unidades pendientes da un costo irreal, muy
    # por debajo del precio de reposición actual.
    cur.execute("""
        SELECT CAPA_ID, ALMACEN_ID, EXISTENCIA, VALOR_TOTAL
        FROM CAPAS_COSTOS
        WHERE ARTICULO_ID = ? AND CAPA_AGOTADA = 'N'
        ORDER BY CAPA_ID
    """, (articulo_id,))
    capas_por_almacen = {}
    capas_detalle = []  # para poder ver "las tripas" desde la app y detectar capas raras
    total_existencia = 0.0
    capa_id_mas_reciente = -1
    costo_mas_reciente = 0.0
    for capa_id, almacen_id, existencia, valor in cur.fetchall():
        existencia = float(existencia or 0)
        valor = float(valor or 0)
        acumulado = capas_por_almacen.setdefault(almacen_id, {"existencia": 0.0, "costo": 0.0, "capa_id": -1})
        acumulado["existencia"] += existencia
        total_existencia += existencia
        capas_detalle.append({
            "capa_id": capa_id, "almacen_id": almacen_id,
            "existencia": existencia, "valor_total": valor,
            "costo_unitario": (valor / existencia) if existencia > 0 else None,
        })
        # Nos quedamos con el costo unitario de la capa más reciente DE ESE
        # ALMACÉN (no se promedia, y no se mezcla el costo de un almacén con
        # el de otro).
        if existencia > 0 and capa_id > acumulado["capa_id"]:
            acumulado["capa_id"] = capa_id
            acumulado["costo"] = valor / existencia
        if existencia > 0 and capa_id > capa_id_mas_reciente:
            capa_id_mas_reciente = capa_id
            costo_mas_reciente = valor / existencia

    costo_promedio = costo_mas_reciente

    cur.execute(
        "SELECT ALMACEN_ID, UNIDADES_COMPROM FROM COMPROM_ARTICULOS WHERE ARTICULO_ID = ?",
        (articulo_id,),
    )
    comprometido_por_almacen = {}
    for almacen_id, comprom in cur.fetchall():
        comprometido_por_almacen[almacen_id] = float(comprom or 0)

    almacen_ids = set(capas_por_almacen) | set(comprometido_por_almacen)
    nombres_almacen = {}
    if almacen_ids:
        placeholders = ",".join("?" for _ in almacen_ids)
        cur.execute(
            f"SELECT ALMACEN_ID, NOMBRE FROM ALMACENES WHERE ALMACEN_ID IN ({placeholders})",
            tuple(almacen_ids),
        )
        nombres_almacen = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}

    # Fecha del último movimiento (última vez que se vendió este
    # artículo por Punto de Venta) POR ALMACÉN — DOCTOS_PV_DET no trae
    # ALMACEN_ID propio, pero el encabezado DOCTOS_PV sí lo tiene (cada
    # venta completa sale de un solo almacén). Sin importar el estatus
    # del documento.
    cur.execute("""
        SELECT p.ALMACEN_ID, MAX(p.FECHA)
        FROM DOCTOS_PV_DET d
        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
        WHERE d.ARTICULO_ID = ?
        GROUP BY p.ALMACEN_ID
    """, (articulo_id,))
    ultimo_movimiento_por_almacen = {aid: str(fecha) for aid, fecha in cur.fetchall() if fecha}
    ultimo_movimiento = max(ultimo_movimiento_por_almacen.values()) if ultimo_movimiento_por_almacen else None

    almacenes = []
    for almacen_id in almacen_ids:
        existencia = capas_por_almacen.get(almacen_id, {}).get("existencia", 0.0)
        comprometido = comprometido_por_almacen.get(almacen_id, 0.0)
        # No mostramos almacenes donde no hay ni existencia ni comprometido
        # (evita llenar la lista con decenas de almacenes internos vacíos).
        if existencia == 0 and comprometido == 0:
            continue
        almacenes.append({
            "almacen_id": almacen_id,
            "almacen_nombre": nombres_almacen.get(almacen_id, f"Almacén {almacen_id}"),
            "existencia": existencia,
            "comprometido": comprometido,
            "disponible": existencia - comprometido,
            "ultimo_movimiento": ultimo_movimiento_por_almacen.get(almacen_id),
        })
    almacenes.sort(key=lambda a: a["almacen_nombre"])

    for capa in capas_detalle:
        capa["almacen_nombre"] = nombres_almacen.get(capa["almacen_id"], f"Almacén {capa['almacen_id']}")

    return {
        "articulo_id": articulo_id,
        "nombre": nombre,
        "claves": claves,
        "precio_sin_impuesto": precio_sin_impuesto,
        "precio_con_impuesto": precio_con_impuesto,
        "existencia_total": total_existencia,
        "comprometido_total": sum(comprometido_por_almacen.values()),
        "disponible_total": total_existencia - sum(comprometido_por_almacen.values()),
        "ultimo_movimiento": ultimo_movimiento,
        "almacenes": almacenes,
        "capas_detalle": sorted(capas_detalle, key=lambda c: -c["capa_id"]),
    }


def buscar_producto_por_clave(config: dict, clave: str):
    """Busca un producto por su clave/código de barras exacto (tabla
    CLAVES_ARTICULOS) y regresa costo + existencia real por almacén."""
    clave = (clave or "").strip()
    if not clave:
        return None
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("SELECT ARTICULO_ID FROM CLAVES_ARTICULOS WHERE CLAVE_ARTICULO = ?", (clave,))
    row = cur.fetchone()
    if not row:
        con.close()
        return None
    resultado = _consultar_producto_por_articulo_id(cur, row[0])
    con.close()
    return resultado


def buscar_producto_por_articulo_id(config: dict, articulo_id: int):
    """Igual que buscar_producto_por_clave, pero cuando ya se conoce el
    ARTICULO_ID (ej. tras elegirlo del buscador por nombre)."""
    con = _conectar(config)
    cur = con.cursor()
    resultado = _consultar_producto_por_articulo_id(cur, articulo_id)
    con.close()
    return resultado


def buscar_productos_por_nombre(config: dict, texto: str, limite: int = 20):
    """Busca artículos activos cuyo nombre contenga el texto dado —
    para el botón de lupa cuando la clave no se encuentra."""
    texto = (texto or "").strip()
    if not texto:
        return []
    con = _conectar(config)
    cur = con.cursor()
    cur.execute(f"""
        SELECT FIRST {int(limite)} ARTICULO_ID, NOMBRE
        FROM ARTICULOS
        WHERE NOMBRE CONTAINING ? AND ESTATUS = 'A'
        ORDER BY NOMBRE
    """, (texto,))
    filas = cur.fetchall()

    resultados = []
    for articulo_id, nombre in filas:
        cur.execute(
            "SELECT FIRST 1 CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID = ? ORDER BY CLAVE_ARTICULO_ID",
            (articulo_id,),
        )
        clave_row = cur.fetchone()
        resultados.append({
            "articulo_id": articulo_id,
            "nombre": (nombre or "").strip(),
            "clave": (clave_row[0] if clave_row else "") or "",
        })
    con.close()
    return resultados


def buscar_pedidos_por_cliente(config: dict, cliente_id: int, limite: int = 200):
    """Busca todos los pedidos/documentos de venta de un cliente en
    Microsip, con su sucursal, si ya está facturado, y si le quedan
    piezas pendientes de surtir — para importar una entrega eligiendo
    primero al cliente, en vez de tener que saber el folio de memoria."""
    con = _conectar(config)
    cur = con.cursor()

    cur.execute(f"""
        SELECT FIRST {int(limite)} DOCTO_VE_ID, FOLIO, TIPO_DOCTO, SUCURSAL_ID, FECHA, ESTATUS
        FROM DOCTOS_VE
        WHERE CLIENTE_ID = ?
        ORDER BY FECHA DESC
    """, (cliente_id,))
    filas = cur.fetchall()

    # Nombres de sucursal — se traen todos de una vez para no repetir consultas.
    sucursal_ids = {f[3] for f in filas if f[3] is not None}
    nombres_sucursal = {}
    if sucursal_ids:
        placeholders = ",".join("?" for _ in sucursal_ids)
        cur.execute(f"SELECT ALMACEN_ID, NOMBRE FROM ALMACENES WHERE ALMACEN_ID IN ({placeholders})", tuple(sucursal_ids))
        nombres_sucursal = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}

    resultados = []
    for docto_id, folio, tipo_docto, sucursal_id, fecha, estatus in filas:
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN UNIDADES_A_SURTIR IS NOT NULL THEN UNIDADES_A_SURTIR
                     ELSE (UNIDADES - COALESCE(UNIDADES_SURT_DEV, 0)) END
            ), 0)
            FROM DOCTOS_VE_DET
            WHERE DOCTO_VE_ID = ?
        """, (docto_id,))
        piezas_pendientes = float(cur.fetchone()[0] or 0)

        tipo_docto = (tipo_docto or "").strip().upper()
        resultados.append({
            "folio": folio,
            # Código real de Microsip, tal cual — cada empresa puede tener
            # sus propios códigos, así que se manda también el crudo para
            # poder ajustar la interpretación si hace falta.
            "tipo_docto": tipo_docto,
            "es_factura": tipo_docto == "F",
            "sucursal_nombre": nombres_sucursal.get(sucursal_id, f"Sucursal {sucursal_id}" if sucursal_id else "—"),
            "fecha": str(fecha) if fecha else None,
            "estatus": (estatus or "").strip(),
            "pendiente_de_surtir": piezas_pendientes > 0,
            "piezas_pendientes": piezas_pendientes,
        })

    con.close()
    return resultados


def buscar_pedidos_pendientes(config: dict, prefijo: str, limite: int = 30):
    """Busca pedidos de venta cuyo folio empiece con el prefijo dado
    (ej. 'AMI') y que todavía tengan piezas pendientes de surtir —
    para el botón 'ver pendientes' al importar una entrega desde folio."""
    prefijo = (prefijo or "").strip().upper()
    if not prefijo:
        return []
    con = _conectar(config)
    cur = con.cursor()
    cur.execute(f"""
        SELECT FIRST {int(limite) * 3} P.FOLIO, P.DOCTO_VE_ID, C.NOMBRE
        FROM DOCTOS_VE P
        LEFT JOIN CLIENTES C ON C.CLIENTE_ID = P.CLIENTE_ID
        WHERE P.FOLIO STARTING WITH ?
        ORDER BY P.FOLIO
    """, (prefijo,))
    filas = cur.fetchall()

    resultados = []
    for folio, docto_id, cliente_nombre in filas:
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN UNIDADES_A_SURTIR IS NOT NULL THEN UNIDADES_A_SURTIR
                     ELSE (UNIDADES - COALESCE(UNIDADES_SURT_DEV, 0)) END
            ), 0)
            FROM DOCTOS_VE_DET
            WHERE DOCTO_VE_ID = ?
        """, (docto_id,))
        pendiente = cur.fetchone()[0] or 0
        if pendiente > 0:
            resultados.append({
                "folio": folio,
                "cliente_nombre": (cliente_nombre or "").strip(),
                "piezas_pendientes": float(pendiente),
            })
        if len(resultados) >= limite:
            break

    con.close()
    return resultados


# =============================================================================
# COTIZADOR: jala un documento de Microsip (cotización, pedido, o venta —
# igual que buscar_pedido, sin filtrar por tipo porque el código de
# TIPO_DOCTO varía por empresa) con precio de lista por artículo, para
# poder editarlo dentro de la app sin tocar Microsip.
# =============================================================================

def buscar_cotizacion_microsip(config: dict, folio: str):
    """Busca un documento en Microsip por folio (cotización, pedido, o
    venta — se acepta cualquiera, igual que buscar_pedido) y regresa
    cliente + artículos CON PRECIO DE LISTA (reutilizando la misma lógica
    ya probada del Checador de precio), para armar una cotización editable."""
    con = _conectar(config)
    cur = con.cursor()

    m = re.match(r"^([A-Za-z]*)0*(\d+)$", folio.strip())
    prefijo, numero = (m.group(1).upper(), m.group(2)) if m else ("", folio.strip())
    numero_norm = numero.lstrip("0") or "0"

    cur.execute("""
        SELECT FOLIO, DOCTO_VE_ID, CLIENTE_ID, TIPO_DOCTO
        FROM DOCTOS_VE
        WHERE FOLIO STARTING WITH ?
    """, (prefijo,))

    coincidencias = []
    for folio_db, docto_id, cli_id, tipo in cur.fetchall():
        resto = folio_db[len(prefijo):].lstrip("0") or "0"
        if resto == numero_norm:
            coincidencias.append((folio_db, docto_id, cli_id, tipo))

    if not coincidencias:
        cur.execute("SELECT FIRST 8 FOLIO FROM DOCTOS_VE WHERE FOLIO STARTING WITH ?", (prefijo,))
        ejemplos = [r[0] for r in cur.fetchall()]
        con.close()
        if ejemplos:
            raise ValueError(
                f"No hay ningún folio '{prefijo}' que numéricamente coincida con '{numero}'. "
                f"Folios que sí existen con el prefijo '{prefijo}': {', '.join(ejemplos)}"
            )
        raise ValueError(f"No existe ningún folio en Microsip que empiece con '{prefijo}'.")

    mejor = None
    mejor_num_items = -1
    for folio_db, docto_id, cli_id, tipo in coincidencias:
        cur.execute("SELECT COUNT(*) FROM DOCTOS_VE_DET WHERE DOCTO_VE_ID = ?", (docto_id,))
        num_items = cur.fetchone()[0]
        if num_items > mejor_num_items or (num_items == mejor_num_items and (mejor is None or docto_id > mejor[1])):
            mejor_num_items = num_items
            mejor = (folio_db, docto_id, cli_id, tipo)

    folio_db, docto_id, cliente_id, tipo_docto = mejor

    cur.execute("SELECT NOMBRE FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
    cliente_row = cur.fetchone()
    cliente_nombre = (cliente_row[0] if cliente_row else "") or ""

    cur.execute("""
        SELECT NOMBRE_CALLE, NUM_EXTERIOR, NUM_INTERIOR, COLONIA, POBLACION, TELEFONO1
        FROM DIRS_CLIENTES WHERE CLIENTE_ID = ? ORDER BY ES_DIR_PPAL DESC
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
        direccion, telefono = "", ""

    cur.execute("""
        SELECT ARTICULO_ID, UNIDADES
        FROM DOCTOS_VE_DET
        WHERE DOCTO_VE_ID = ?
    """, (docto_id,))
    partidas = cur.fetchall()

    items = []
    for articulo_id, unidades in partidas:
        cantidad = float(unidades or 0)
        if articulo_id:
            # Se usa la MISMA función ya probada del Checador de precio para
            # el precio de lista — no se inventa una columna nueva de precio,
            # se reutiliza lo que ya se confirmó correcto en producción.
            info = _consultar_producto_por_articulo_id(cur, articulo_id)
        else:
            info = None
        if info:
            items.append({
                "articulo_id": articulo_id,
                "clave": info["claves"][0] if info["claves"] else None,
                "nombre": info["nombre"],
                "cantidad": cantidad,
                "precio_unitario": info["precio_con_impuesto"] or 0,
            })
        else:
            items.append({
                "articulo_id": None,
                "clave": None,
                "nombre": "(artículo sin nombre en Microsip)",
                "cantidad": cantidad,
                "precio_unitario": 0,
            })

    con.close()
    return {
        "folio_encontrado": folio_db,
        "tipo_docto": (tipo_docto or "").strip(),
        "cliente_nombre": cliente_nombre.strip(),
        "cliente_direccion": direccion,
        "cliente_telefono": telefono,
        "items": items,
    }


# =============================================================================
# DASHBOARD: ventas del módulo de Punto de Venta (caja), por sucursal y
# desglosadas por forma de cobro (efectivo, tarjeta de crédito/débito,
# transferencia, etc.) — usa FORMAS_COBRO_DOCTOS (el desglose real de cómo
# se cobró cada ticket, puede ser mixto) en vez de DOCTOS_PV.TOTAL_DOCTO.
# =============================================================================

def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):
    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin
    (excluida), en formato 'YYYY-MM-DD', agrupadas por sucursal y forma de
    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por
    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se
    encontró la tabla real donde esa forma de cobro vive para CxC — se
    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se
    encuentra esa conexión, se puede volver a ampliar.) El artículo
    "ANTICIPO" se descuenta del total de cada sucursal (y se reporta
    aparte como "anticipo"/"total_anticipo") porque es un cobro
    adelantado, no una venta real — se identifica por NOMBRE del
    artículo, no por ID fijo, para que siga funcionando si cambia de
    empresa/base. Se usa un cursor separado para esta segunda consulta
    (reusar el mismo cursor para dos SELECT seguidos dejaba vacía la
    primera consulta con este driver de Firebird), y va envuelta en
    try/except: si llegara a fallar, no tumba el desglose principal de
    ventas, simplemente no se descuenta ningún anticipo ese rato. Si los
    nombres de tabla/columna no coinciden con esta empresa, el error de
    Firebird de la consulta principal se deja tal cual para poder
    ajustarlo rápido."""
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), fc.NOMBRE, SUM(fcd.IMPORTE)
        FROM DOCTOS_PV p
        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV'
        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, (fecha_inicio, fecha_fin))
    filas = cur.fetchall()
    cur.close()

    filas_anticipo = []
    try:
        cur2 = con.cursor()
        cur2.execute("""
            SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), SUM(d.PRECIO_TOTAL_NETO)
            FROM DOCTOS_PV p
            JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID
            JOIN ARTICULOS a ON a.ARTICULO_ID = d.ARTICULO_ID
            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
            WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S' AND a.NOMBRE = 'ANTICIPO'
            GROUP BY 1
        """, (fecha_inicio, fecha_fin))
        filas_anticipo = cur2.fetchall()
        cur2.close()
    except Exception:
        filas_anticipo = []
    con.close()

    anticipos_por_sucursal = {}
    for sucursal, importe in filas_anticipo:
        sucursal = (sucursal or "Sin sucursal").strip()
        anticipos_por_sucursal[sucursal] = anticipos_por_sucursal.get(sucursal, 0.0) + float(importe or 0)

    por_sucursal = {}
    total_general = 0.0
    for sucursal, forma_cobro, importe in filas:
        importe = float(importe or 0)
        sucursal = (sucursal or "Sin sucursal").strip()
        forma_cobro = (forma_cobro or "Sin especificar").strip()
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe
        entrada["total"] += importe
        total_general += importe

    total_anticipo_general = 0.0
    for sucursal, anticipo in anticipos_por_sucursal.items():
        entrada = por_sucursal.get(sucursal)
        if entrada is None:
            # No hay ventas cobradas (forma de cobro) en esta sucursal ese
            # periodo — no se fabrica una fila solo con el anticipo, para
            # no mostrar un total negativo sin ventas reales detrás.
            continue
        entrada["anticipo"] = anticipo
        entrada["total"] = max(0.0, entrada["total"] - anticipo)
        total_anticipo_general += anticipo

    total_general = sum(e["total"] for e in por_sucursal.values())

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}


def obtener_bitacora_ventas_pv(config: dict, fecha_inicio: str, fecha_fin: str):
    """Primeras y últimas 10 ventas del día (con su hora y sucursal), más el
    rango de 12:00pm a 2:00pm — para revisar la actividad de Punto de Venta
    a lo largo del día. fecha_inicio/fecha_fin en formato 'YYYY-MM-DD'
    (el rango de UN día se arma como [fecha, fecha + 1 día))."""
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT p.FOLIO, p.HORA, COALESCE(s.NOMBRE, 'Sin sucursal'), p.IMPORTE_NETO
        FROM DOCTOS_PV p
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'
        ORDER BY p.HORA
    """, (fecha_inicio, fecha_fin))
    filas = cur.fetchall()
    con.close()

    ventas = []
    for folio, hora, sucursal, importe in filas:
        ventas.append({
            "folio": folio,
            # Se convierte a texto "HH:MM:SS" para comparar y mostrar sin
            # depender del tipo exacto que regrese el driver de Firebird.
            "hora": str(hora)[:8] if hora is not None else None,
            "sucursal": (sucursal or "Sin sucursal").strip(),
            "total": float(importe or 0),
        })

    rango_comida = [v for v in ventas if v["hora"] and "12:00:00" <= v["hora"] < "14:00:00"]

    return {
        "total_ventas": len(ventas),
        "primeras": ventas[:10],
        "ultimas": ventas[-10:],
        "rango_12_14": rango_comida,
    }


# =============================================================================
# DASHBOARD: valor del inventario por sucursal (almacén) — usa la misma
# lógica de capas de costo (CAPAS_COSTOS) ya probada en el Checador de
# precio, pero agregada por almacén completo en vez de artículo por
# artículo. VALOR_TOTAL de una capa no agotada es literalmente el dinero
# que sigue invertido en esas piezas — sumarlo da el valor real del
# inventario a costo de compra.
# =============================================================================

def obtener_valor_inventario_por_almacen(config: dict):
    """Valor total del inventario (a costo de compra) por sucursal/almacén,
    y los 50 artículos que más valor representan en cada uno."""
    con = _conectar(config)
    cur = con.cursor()

    cur.execute("""
        SELECT cc.ALMACEN_ID, COALESCE(a.NOMBRE, 'Sin nombre'), SUM(cc.VALOR_TOTAL), SUM(cc.EXISTENCIA)
        FROM CAPAS_COSTOS cc
        LEFT JOIN ALMACENES a ON a.ALMACEN_ID = cc.ALMACEN_ID
        WHERE cc.CAPA_AGOTADA = 'N'
        GROUP BY cc.ALMACEN_ID, a.NOMBRE
    """)
    totales = {}
    for almacen_id, nombre, valor, existencia in cur.fetchall():
        totales[almacen_id] = {
            "almacen_id": almacen_id,
            "sucursal": (nombre or "Sin nombre").strip(),
            "valor_total": float(valor or 0),
            "unidades_totales": float(existencia or 0),
        }

    cur.execute("""
        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA), SUM(cc.VALOR_TOTAL)
        FROM CAPAS_COSTOS cc
        WHERE cc.CAPA_AGOTADA = 'N'
        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID
    """)
    filas_articulos = cur.fetchall()

    articulo_ids = sorted({r[1] for r in filas_articulos})
    nombres, claves = {}, {}
    LOTE = 400
    for i in range(0, len(articulo_ids), LOTE):
        lote = articulo_ids[i:i + LOTE]
        placeholders = ",".join("?" for _ in lote)
        cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, nombre in cur.fetchall():
            nombres[aid] = (nombre or "").strip()
        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, clave in cur.fetchall():
            if aid not in claves and clave:
                claves[aid] = clave

    por_almacen_articulos = {}
    for almacen_id, articulo_id, existencia, valor in filas_articulos:
        existencia = float(existencia or 0)
        valor = float(valor or 0)
        if existencia <= 0:
            continue
        por_almacen_articulos.setdefault(almacen_id, []).append({
            "articulo_id": articulo_id,
            "nombre": nombres.get(articulo_id, "(sin nombre)"),
            "clave": claves.get(articulo_id),
            "cantidad": existencia,
            "costo_unitario": valor / existencia if existencia else 0,
            "valor_total": valor,
        })

    con.close()

    for almacen_id in por_almacen_articulos:
        por_almacen_articulos[almacen_id].sort(key=lambda a: -a["valor_total"])
        por_almacen_articulos[almacen_id] = por_almacen_articulos[almacen_id][:50]

    resultado = []
    for almacen_id, datos in sorted(totales.items(), key=lambda kv: -kv[1]["valor_total"]):
        datos = dict(datos)
        datos["top_articulos"] = por_almacen_articulos.get(almacen_id, [])
        resultado.append(datos)

    total_general = sum(d["valor_total"] for d in resultado)
    return {"por_sucursal": resultado, "total_general": total_general}


def obtener_articulos_sin_movimiento_por_almacen(config: dict, fecha_inicio: str = None, fecha_fin: str = None):
    """Artículos con existencia > 0 en cada almacén que JAMÁS se han
    vendido por Punto de Venta, en ninguna sucursal, en todo el historial
    de Microsip. Valuados a PRECIO DE VENTA (PRECIOS_ARTICULOS x 1.16
    IVA — mismo precio de lista que usa el Checador de precio), no a
    costo. Si se dan fecha_inicio/fecha_fin ('YYYY-MM-DD', fecha_fin
    excluida), solo se incluyen artículos que tuvieron una ENTRADA de
    inventario (DOCTOS_IN/DOCTOS_IN_DET, cruzado con
    CONCEPTOS_IN.NATURALEZA='E' — compras, recepción de mercancía, etc.,
    nunca salidas) en ese rango; sin fechas se muestran todos, sin
    importar cuándo entraron. Se devuelven TODOS los artículos (no solo
    un top 50) — el frontend pagina de 50 en 50. Ordenados por precio
    unitario, de mayor a menor."""
    con = _conectar(config)
    cur = con.cursor()

    cur.execute("""
        SELECT DISTINCT d.ARTICULO_ID
        FROM DOCTOS_PV_DET d
        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
        WHERE p.ESTATUS = 'S'
    """)
    vendidos_alguna_vez = {fila[0] for fila in cur.fetchall()}

    entradas_permitidas = None
    if fecha_inicio and fecha_fin:
        cur.execute("""
            SELECT DISTINCT d.ALMACEN_ID, d.ARTICULO_ID
            FROM DOCTOS_IN_DET d
            JOIN DOCTOS_IN p ON p.DOCTO_IN_ID = d.DOCTO_IN_ID
            JOIN CONCEPTOS_IN c ON c.CONCEPTO_IN_ID = d.CONCEPTO_IN_ID
            WHERE c.NATURALEZA = 'E' AND p.CANCELADO = 'N' AND d.CANCELADO = 'N'
              AND p.FECHA >= ? AND p.FECHA < ?
        """, (fecha_inicio, fecha_fin))
        entradas_permitidas = {(almacen_id, articulo_id) for almacen_id, articulo_id in cur.fetchall()}

    cur.execute("""
        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA)
        FROM CAPAS_COSTOS cc
        WHERE cc.CAPA_AGOTADA = 'N'
        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID
    """)
    filas_articulos = [
        (almacen_id, articulo_id, existencia)
        for almacen_id, articulo_id, existencia in cur.fetchall()
        if articulo_id not in vendidos_alguna_vez
        and (entradas_permitidas is None or (almacen_id, articulo_id) in entradas_permitidas)
    ]

    cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")
    nombres_almacen = {aid: (nombre or "Sin nombre").strip() for aid, nombre in cur.fetchall()}

    articulo_ids = sorted({fila[1] for fila in filas_articulos})
    nombres, claves, precios = {}, {}, {}
    LOTE = 400
    for i in range(0, len(articulo_ids), LOTE):
        lote = articulo_ids[i:i + LOTE]
        placeholders = ",".join("?" for _ in lote)
        cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, nombre in cur.fetchall():
            nombres[aid] = (nombre or "").strip()
        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, clave in cur.fetchall():
            if aid not in claves and clave:
                claves[aid] = clave
        # Precio de lista: PRECIOS_ARTICULOS guarda el precio SIN
        # impuesto, igual que en el Checador de precio se le agrega 16%
        # de IVA.
        cur.execute(f"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, precio in cur.fetchall():
            if aid not in precios and precio is not None:
                precios[aid] = round(float(precio) * 1.16, 2)

    con.close()

    por_almacen = {}
    for almacen_id, articulo_id, existencia in filas_articulos:
        existencia = float(existencia or 0)
        if existencia <= 0:
            continue
        precio_unitario = precios.get(articulo_id)
        if precio_unitario is None:
            continue  # sin precio de lista capturado en Microsip, no se puede valuar
        valor = precio_unitario * existencia
        entrada = por_almacen.setdefault(almacen_id, {
            "almacen_id": almacen_id,
            "sucursal": nombres_almacen.get(almacen_id, "Sin nombre"),
            "valor_total": 0.0,
            "cantidad_articulos": 0,
            "articulos": [],
        })
        entrada["valor_total"] += valor
        entrada["cantidad_articulos"] += 1
        entrada["articulos"].append({
            "articulo_id": articulo_id,
            "nombre": nombres.get(articulo_id, "(sin nombre)"),
            "clave": claves.get(articulo_id),
            "cantidad": existencia,
            "precio_unitario": precio_unitario,
            "valor_total": valor,
        })

    for datos in por_almacen.values():
        datos["articulos"].sort(key=lambda a: -a["precio_unitario"])

    resultado = sorted(por_almacen.values(), key=lambda d: -d["valor_total"])
    total_general = sum(d["valor_total"] for d in resultado)
    return {"por_sucursal": resultado, "total_general": total_general}


def obtener_valor_inventario_precio_venta_por_almacen(config: dict):
    """Igual que obtener_valor_inventario_por_almacen, pero valuando cada
    artículo a su PRECIO DE VENTA (PRECIOS_ARTICULOS x 1.16 IVA — mismo
    precio de lista que usa el Checador de precio) en vez del costo de
    compra. Sirve para saber cuánto valdría el inventario si se vendiera
    todo a precio de lista."""
    con = _conectar(config)
    cur = con.cursor()

    cur.execute("""
        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA)
        FROM CAPAS_COSTOS cc
        WHERE cc.CAPA_AGOTADA = 'N'
        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID
    """)
    filas_existencia = cur.fetchall()

    cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")
    nombres_almacen = {aid: (nombre or "Sin nombre").strip() for aid, nombre in cur.fetchall()}

    articulo_ids = sorted({fila[1] for fila in filas_existencia})
    nombres, claves, precios = {}, {}, {}
    LOTE = 400
    for i in range(0, len(articulo_ids), LOTE):
        lote = articulo_ids[i:i + LOTE]
        placeholders = ",".join("?" for _ in lote)
        cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, nombre in cur.fetchall():
            nombres[aid] = (nombre or "").strip()
        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, clave in cur.fetchall():
            if aid not in claves and clave:
                claves[aid] = clave
        # Precio de lista: PRECIOS_ARTICULOS guarda el precio SIN
        # impuesto, igual que en el Checador de precio se le agrega 16% de
        # IVA. Si un artículo tuviera más de un precio capturado, se usa
        # el primero que aparezca (mismo criterio de "FIRST 1" que usa el
        # Checador).
        cur.execute(f"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))
        for aid, precio in cur.fetchall():
            if aid not in precios and precio is not None:
                precios[aid] = round(float(precio) * 1.16, 2)

    con.close()

    por_almacen_totales = {}
    por_almacen_articulos = {}
    for almacen_id, articulo_id, existencia in filas_existencia:
        existencia = float(existencia or 0)
        if existencia <= 0:
            continue
        precio_unitario = precios.get(articulo_id)
        if precio_unitario is None:
            continue  # sin precio de lista capturado en Microsip, no se puede valuar
        valor_total = precio_unitario * existencia

        totales = por_almacen_totales.setdefault(almacen_id, {
            "almacen_id": almacen_id,
            "sucursal": nombres_almacen.get(almacen_id, "Sin nombre"),
            "valor_total": 0.0,
            "unidades_totales": 0.0,
        })
        totales["valor_total"] += valor_total
        totales["unidades_totales"] += existencia

        por_almacen_articulos.setdefault(almacen_id, []).append({
            "articulo_id": articulo_id,
            "nombre": nombres.get(articulo_id, "(sin nombre)"),
            "clave": claves.get(articulo_id),
            "cantidad": existencia,
            "precio_unitario": precio_unitario,
            "valor_total": valor_total,
        })

    for almacen_id in por_almacen_articulos:
        por_almacen_articulos[almacen_id].sort(key=lambda a: -a["valor_total"])
        por_almacen_articulos[almacen_id] = por_almacen_articulos[almacen_id][:50]

    resultado = []
    for almacen_id, datos in sorted(por_almacen_totales.items(), key=lambda kv: -kv[1]["valor_total"]):
        datos = dict(datos)
        datos["top_articulos"] = por_almacen_articulos.get(almacen_id, [])
        resultado.append(datos)

    total_general = sum(d["valor_total"] for d in resultado)
    return {"por_sucursal": resultado, "total_general": total_general}


# =============================================================================
# DASHBOARD: descuentos otorgados en Punto de Venta — usa DOCTOS_PV_DET
# (DSCTO_ART + DSCTO_EXTRA, confirmados con datos reales como los campos que
# sí traen el descuento en PESOS; PCTJE_DSCTO se confirmó vacío/0 siempre en
# este Microsip) por sucursal y con el cliente de cada ticket.
# =============================================================================

def obtener_descuentos_pv(config: dict, fecha_inicio: str, fecha_fin: str):
    """Descuento total (en dinero) por sucursal entre fecha_inicio (incluida)
    y fecha_fin (excluida), y los 50 descuentos más altos otorgados en cada
    una, con el cliente y el monto del ticket."""
    con = _conectar(config)
    cur = con.cursor()

    cur.execute("""
        SELECT p.SUCURSAL_ID, COALESCE(s.NOMBRE, 'Sin sucursal'), SUM(d.DSCTO_ART + d.DSCTO_EXTRA), SUM(d.PRECIO_TOTAL_NETO)
        FROM DOCTOS_PV_DET d
        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'
        GROUP BY p.SUCURSAL_ID, s.NOMBRE
    """, (fecha_inicio, fecha_fin))
    totales = {}
    for sucursal_id, nombre, descuento, venta_total in cur.fetchall():
        totales[sucursal_id] = {
            "sucursal_id": sucursal_id,
            "sucursal": (nombre or "Sin sucursal").strip(),
            "descuento_total": float(descuento or 0),
            "venta_total": float(venta_total or 0),
        }

    cur.execute("""
        SELECT p.SUCURSAL_ID, COALESCE(c.NOMBRE, 'Público en general'),
               p.FOLIO, p.FECHA, p.HORA, (d.DSCTO_ART + d.DSCTO_EXTRA), d.PRECIO_TOTAL_NETO, p.DSCTO_PCTJE
        FROM DOCTOS_PV_DET d
        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID
        LEFT JOIN CLIENTES c ON c.CLIENTE_ID = p.CLIENTE_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S' AND (d.DSCTO_ART + d.DSCTO_EXTRA) > 0
        ORDER BY (d.DSCTO_ART + d.DSCTO_EXTRA) DESC
    """, (fecha_inicio, fecha_fin))
    filas = cur.fetchall()
    con.close()

    # Como la consulta ya viene ordenada de mayor a menor descuento, ir
    # repartiendo cada fila en su sucursal y cortar en 50 mantiene el orden
    # correcto dentro de cada sucursal sin tener que reordenar después.
    por_sucursal_desc = {}
    for sucursal_id, cliente, folio, fecha, hora, descuento, monto, pctje_docto in filas:
        lista = por_sucursal_desc.setdefault(sucursal_id, [])
        if len(lista) >= 50:
            continue
        lista.append({
            "cliente": (cliente or "Público en general").strip(),
            "folio": folio,
            "fecha": str(fecha)[:10] if fecha else None,
            "hora": str(hora)[:8] if hora else None,
            "descuento": float(descuento or 0),
            "monto": float(monto or 0),
            # Porcentaje real del documento en Microsip (no uno calculado
            # por nosotros) — es el mismo % para todas las líneas de un
            # mismo ticket, porque el descuento se aplica a nivel documento.
            "porcentaje": float(pctje_docto or 0),
        })

    resultado = []
    for sucursal_id, datos in sorted(totales.items(), key=lambda kv: -kv[1]["descuento_total"]):
        datos = dict(datos)
        datos["top_descuentos"] = por_sucursal_desc.get(sucursal_id, [])
        resultado.append(datos)

    total_general = sum(d["descuento_total"] for d in resultado)
    return {"por_sucursal": resultado, "total_general": total_general}
