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
    """TODO el dinero cobrado entre fecha_inicio (incluida) y fecha_fin
    (excluida), en formato 'YYYY-MM-DD', agrupado por sucursal y forma de
    cobro — igual que el "Reporte de cobros" nativo de Microsip: junta lo
    cobrado en Punto de Venta (tickets de caja) CON lo cobrado en Cuentas
    por Cobrar (pagos de crédito, condonaciones, etc.), ya que ambos usan
    la misma tabla de formas de cobro (FORMAS_COBRO_DOCTOS es compartida,
    distinguida por NOM_TABLA_DOCTOS). Si los nombres de tabla/columna no
    coinciden con esta empresa, el error de Firebird se deja tal cual."""
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT sucursal, forma_cobro, SUM(importe)
        FROM (
            SELECT s.NOMBRE AS sucursal, fc.NOMBRE AS forma_cobro, fcd.IMPORTE AS importe
            FROM FORMAS_COBRO_DOCTOS fcd
            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID
            JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = fcd.DOCTO_ID
            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
            WHERE fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV' AND p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> 'C'

            UNION ALL

            SELECT s.NOMBRE, fc.NOMBRE, fcd.IMPORTE
            FROM FORMAS_COBRO_DOCTOS fcd
            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID
            JOIN DOCTOS_CC cc ON cc.DOCTO_CC_ID = fcd.DOCTO_ID
            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = cc.SUCURSAL_ID
            WHERE fcd.NOM_TABLA_DOCTOS = 'DOCTOS_CC' AND cc.FECHA >= ? AND cc.FECHA < ? AND cc.ESTATUS <> 'C'
        ) t
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, (fecha_inicio, fecha_fin, fecha_inicio, fecha_fin))
    filas = cur.fetchall()
    con.close()

    por_sucursal = {}
    total_general = 0.0
    for sucursal, forma_cobro, importe in filas:
        importe = float(importe or 0)
        sucursal = (sucursal or "Sin sucursal").strip()
        forma_cobro = (forma_cobro or "Sin especificar").strip()
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0})
        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe
        entrada["total"] += importe
        total_general += importe

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general}
