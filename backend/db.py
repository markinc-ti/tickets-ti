"""
Capa de datos — multiempresa, sobre PostgreSQL (antes era SQLite).

Se cambió de SQLite a Postgres porque el disco local de Render (plan
gratis) es efímero: se borra cada vez que la app se duerme por
inactividad y vuelve a despertar. Postgres vive en un servidor aparte
(Neon/Supabase) y no depende del disco de Render, así que los datos
ya no se pierden.

Requiere la variable de entorno DATABASE_URL (cadena de conexión de
Postgres, la da Neon/Supabase al crear la base).
"""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras

import auth

ZONA_MX = ZoneInfo("America/Mexico_City")  # Puebla y CDMX usan esta misma zona


def ahora():
    """Fecha y hora actual en Puebla/CDMX (UTC-6), como datetime "naive" para no
    romper el formato que ya se guarda en toda la base de datos (el servidor
    normalmente corre en UTC, así que no reemplazar esto volvería a guardar
    la hora equivocada en tickets, reparaciones, etc.)."""
    return datetime.now(ZONA_MX).replace(tzinfo=None)

DATABASE_URL = os.getenv("DATABASE_URL", "")

ESTADOS = ["abierto", "en_progreso", "resuelto", "cerrado"]
PRIORIDADES = ["baja", "media", "alta", "urgente"]
ROLES = ["superadmin", "admin", "tecnico", "usuario"]

TIPOS_EQUIPO = ["computadora", "laptop", "impresora", "monitor", "servidor", "red", "otro"]
ESTADOS_EQUIPO = ["activo", "en_reparacion", "baja"]
TIPOS_MANTENIMIENTO = ["preventivo", "correctivo"]
FRECUENCIAS_MANTENIMIENTO = ["unica", "mensual", "trimestral", "semestral", "anual"]
ESTADOS_PROYECTO = ["planificacion", "en_progreso", "pausado", "completado", "cancelado"]
ESTADOS_TAREA_PROYECTO = ["pendiente", "en_progreso", "completada"]
FRECUENCIAS_COMPRA = ["unica", "semanal", "quincenal", "mensual"]
ESTADOS_CICLO_COMPRA = ["pendiente", "abierto", "cerrado"]
ESTADOS_REPARACION = [
    "en_diagnostico", "esperando_autorizacion", "en_reparacion", "con_proveedor",
    "esperando_refaccion", "control_calidad", "envio_sucursal", "listo_entrega", "entregado", "cancelado",
]

TABLAS_BORRADO_MASIVO = {
    "tickets": {"tabla": "tickets", "campo_fecha": "creado_en", "etiqueta": "Tickets"},
    "reparaciones": {"tabla": "reparaciones", "campo_fecha": "creado_en", "etiqueta": "Reparaciones"},
    "proyectos": {"tabla": "proyectos", "campo_fecha": "creado_en", "etiqueta": "Proyectos"},
    "mantenimientos": {"tabla": "mantenimientos", "campo_fecha": "creado_en", "etiqueta": "Mantenimientos"},
    "ciclos_compra": {"tabla": "ciclos_compra", "campo_fecha": "creado_en", "etiqueta": "Ciclos de compra"},
}

_DEPARTAMENTOS_INICIALES = [
    "Ventas", "Producción", "Almacén", "Contabilidad",
    "Recursos Humanos", "Dirección", "Sistemas", "Otro",
]
_CATEGORIAS_INICIALES = ["hardware", "software", "red", "accesos", "otro"]


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL (la cadena de conexión de tu base "
            "Postgres en Neon/Supabase). La app no puede guardar nada sin ella."
        )
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            logo_base64 TEXT,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER REFERENCES empresas(id),
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'usuario',
            telefono_whatsapp TEXT,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS departamentos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE(empresa_id, nombre)
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE(empresa_id, nombre)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            folio TEXT NOT NULL,
            departamento TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'otro',
            prioridad TEXT NOT NULL DEFAULT 'media',
            estado TEXT NOT NULL DEFAULT 'abierto',
            solicitante_id INTEGER NOT NULL REFERENCES users(id),
            asignado_a_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL,
            resuelto_en TEXT,
            firma TEXT,
            firmado_por TEXT,
            firmado_en TEXT,
            UNIQUE(empresa_id, folio)
        );

        CREATE TABLE IF NOT EXISTS comentarios (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            autor_id INTEGER NOT NULL REFERENCES users(id),
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL,
            archivo_base64 TEXT,
            archivo_nombre TEXT,
            archivo_tipo TEXT
        );

        CREATE TABLE IF NOT EXISTS equipos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            tipo TEXT NOT NULL DEFAULT 'computadora',
            nombre TEXT NOT NULL,
            marca TEXT,
            modelo TEXT,
            numero_serie TEXT,
            departamento TEXT,
            responsable TEXT,
            estado TEXT NOT NULL DEFAULT 'activo',
            fecha_adquisicion TEXT,
            notas TEXT,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mantenimientos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            equipo_id INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL DEFAULT 'preventivo',
            descripcion TEXT NOT NULL,
            fecha_programada TEXT NOT NULL,
            frecuencia TEXT NOT NULL DEFAULT 'unica',
            estado TEXT NOT NULL DEFAULT 'pendiente',
            realizado_en TEXT,
            realizado_por TEXT,
            notas TEXT,
            creado_en TEXT NOT NULL,
            ticket_id INTEGER REFERENCES tickets(id),
            tecnico_asignado_id INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS proyectos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            descripcion TEXT,
            estado TEXT NOT NULL DEFAULT 'planificacion',
            fecha_inicio TEXT,
            fecha_estimada TEXT,
            fecha_completado TEXT,
            creado_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proyecto_participantes_usuarios (
            id SERIAL PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            UNIQUE(proyecto_id, usuario_id)
        );

        CREATE TABLE IF NOT EXISTS proyecto_participantes_departamentos (
            id SERIAL PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            departamento TEXT NOT NULL,
            UNIQUE(proyecto_id, departamento)
        );

        CREATE TABLE IF NOT EXISTS proyecto_firmas (
            id SERIAL PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            estado TEXT NOT NULL,
            firma_base64 TEXT,
            motivo_no_conforme TEXT,
            actualizado_en TEXT NOT NULL,
            UNIQUE(proyecto_id, usuario_id)
        );

        CREATE TABLE IF NOT EXISTS proyecto_tareas (
            id SERIAL PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            descripcion TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            fecha_limite TEXT,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proyecto_actualizaciones (
            id SERIAL PRIMARY KEY,
            proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
            autor_id INTEGER NOT NULL REFERENCES users(id),
            texto TEXT NOT NULL,
            archivo_base64 TEXT,
            archivo_nombre TEXT,
            archivo_tipo TEXT,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS articulos_compra (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            proveedor TEXT,
            marca TEXT,
            foto_base64 TEXT,
            notas TEXT,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ciclos_compra (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            frecuencia TEXT NOT NULL DEFAULT 'unica',
            fecha_programada TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            creado_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL,
            abierto_en TEXT,
            cerrado_en TEXT
        );

        CREATE TABLE IF NOT EXISTS pedidos_compra (
            id SERIAL PRIMARY KEY,
            ciclo_id INTEGER NOT NULL REFERENCES ciclos_compra(id) ON DELETE CASCADE,
            articulo_id INTEGER NOT NULL REFERENCES articulos_compra(id),
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            cantidad INTEGER NOT NULL DEFAULT 1,
            notas TEXT,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reparaciones (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            folio TEXT NOT NULL,
            folio_microsip TEXT,
            cliente_nombre TEXT NOT NULL,
            cliente_direccion TEXT,
            cliente_telefono TEXT,
            cliente_email TEXT,
            equipo TEXT,
            ticket_id INTEGER REFERENCES tickets(id),
            creado_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL,
            UNIQUE(empresa_id, folio)
        );

        CREATE TABLE IF NOT EXISTS sucursales_reparacion (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            prefijo TEXT NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE(empresa_id, prefijo)
        );

        CREATE TABLE IF NOT EXISTS reparacion_items_costo (
            id SERIAL PRIMARY KEY,
            reparacion_id INTEGER NOT NULL REFERENCES reparaciones(id) ON DELETE CASCADE,
            articulo TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 1,
            codigo TEXT,
            costo REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reparacion_evidencias (
            id SERIAL PRIMARY KEY,
            reparacion_id INTEGER NOT NULL REFERENCES reparaciones(id) ON DELETE CASCADE,
            etapa TEXT NOT NULL DEFAULT 'ingreso',
            archivo_base64 TEXT NOT NULL,
            archivo_nombre TEXT,
            subido_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reparacion_actualizaciones (
            id SERIAL PRIMARY KEY,
            reparacion_id INTEGER NOT NULL REFERENCES reparaciones(id) ON DELETE CASCADE,
            autor_id INTEGER NOT NULL REFERENCES users(id),
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL
        );
    """)
    conn.commit()

    # Migración no destructiva: agrega las columnas de adjunto si la tabla
    # comentarios ya existía de antes (Postgres soporta IF NOT EXISTS aquí).
    cur.execute("""
        ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS archivo_base64 TEXT;
        ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS archivo_nombre TEXT;
        ALTER TABLE comentarios ADD COLUMN IF NOT EXISTS archivo_tipo TEXT;
        ALTER TABLE mantenimientos ADD COLUMN IF NOT EXISTS ticket_id INTEGER REFERENCES tickets(id);
        ALTER TABLE mantenimientos ADD COLUMN IF NOT EXISTS tecnico_asignado_id INTEGER REFERENCES users(id);
        ALTER TABLE mantenimientos ADD COLUMN IF NOT EXISTS creado_por_id INTEGER REFERENCES users(id);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS puesto TEXT;
        ALTER TABLE categorias ADD COLUMN IF NOT EXISTS tecnico_predeterminado_id INTEGER REFERENCES users(id);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS restriccion_categoria TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_equipos BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_administracion BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE pedidos_compra ADD COLUMN IF NOT EXISTS departamento TEXT;
        ALTER TABLE pedidos_compra ADD COLUMN IF NOT EXISTS listo BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE pedidos_compra ADD COLUMN IF NOT EXISTS listo_en TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_compras BOOLEAN NOT NULL DEFAULT TRUE;

        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS asesor_recibe TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS marca TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS modelo TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS numero_serie TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_folio_adquisicion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS garantia BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS falla_reportada TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS estado_fisico TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS accesorios_entregados TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_recepcion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS estado TEXT NOT NULL DEFAULT 'en_diagnostico';
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_recepcion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS diagnostico TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS autorizacion_precio BOOLEAN;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS autorizacion_medio TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_autorizacion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS folio_solicitud_traspaso TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS costo_paqueteria REAL NOT NULL DEFAULT 0;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS conclusion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS recomendaciones TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS responsable_diagnostico_id INTEGER REFERENCES users(id);
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_envio_proveedor TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_entrega TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS observaciones_entrega TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_entrega TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS departamento TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES users(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS usuario_microsip TEXT;
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS password_microsip TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS telefonos TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS notas TEXT;
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'")
    if cur.fetchone()["n"] == 0:
        now = ahora().isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, creado_en) VALUES (NULL, %s, %s, %s, 'superadmin', %s)",
            ("superadmin", auth.hash_password("cambiar123"), "Super Administrador", now),
        )
        conn.commit()
    cur.close()
    conn.close()


# ---- Empresas (superadmin) ----

def listar_empresas():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, logo_base64, activo, creado_en FROM empresas ORDER BY nombre")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_empresa(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, logo_base64, activo, creado_en FROM empresas WHERE id = %s", (empresa_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def crear_empresa(nombre, admin_username, admin_password, admin_nombre):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    try:
        cur.execute("INSERT INTO empresas (nombre, creado_en) VALUES (%s, %s) RETURNING id", (nombre, now))
        empresa_id = cur.fetchone()["id"]

        cur.execute(
            "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, creado_en) VALUES (%s, %s, %s, %s, 'admin', %s)",
            (empresa_id, admin_username, auth.hash_password(admin_password), admin_nombre, now),
        )

        cur.executemany(
            "INSERT INTO departamentos (empresa_id, nombre) VALUES (%s, %s)",
            [(empresa_id, d) for d in _DEPARTAMENTOS_INICIALES],
        )
        cur.executemany(
            "INSERT INTO categorias (empresa_id, nombre) VALUES (%s, %s)",
            [(empresa_id, c) for c in _CATEGORIAS_INICIALES],
        )
        conn.commit()
    finally:
        cur.close(); conn.close()
    return empresa_id


def actualizar_empresa(empresa_id, nombre=None, activo=None):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre = %s"); valores.append(nombre)
    if activo is not None:
        campos.append("activo = %s"); valores.append(activo)
    if campos:
        valores.append(empresa_id)
        cur.execute(f"UPDATE empresas SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def actualizar_logo_empresa(empresa_id, logo_base64):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE empresas SET logo_base64 = %s WHERE id = %s", (logo_base64, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Usuarios (dentro de una empresa) ----

def obtener_usuario_por_username(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def listar_usuarios(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT u.id, u.username, u.nombre_completo, u.rol, u.puesto, u.telefono_whatsapp, u.activo, u.creado_en,
                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,
                  u.sucursal_id, s.nombre AS sucursal_nombre
           FROM users u
           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id
           WHERE u.empresa_id = %s ORDER BY u.nombre_completo""",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_permisos_usuario(usuario_id):
    """Permisos vigentes de un usuario, leídos frescos de la base (no del JWT, para que
    un cambio de permisos aplique de inmediato sin esperar a que vuelva a iniciar sesión)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras FROM users WHERE id = %s",
        (usuario_id,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else {}


def obtener_departamento_usuario(usuario_id):
    """El departamento del usuario, heredado de su sucursal (si tiene una asignada
    y esa sucursal tiene un departamento vinculado). None si no aplica."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.departamento
        FROM users u LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id
        WHERE u.id = %s
    """, (usuario_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row["departamento"] if row else None


def obtener_sucursal_id_usuario(usuario_id):
    """La sucursal directamente asignada al usuario (None si no tiene)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT sucursal_id FROM users WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row["sucursal_id"] if row else None


def obtener_sucursal_id_usuario(usuario_id):
    """El id de sucursal asignado directamente al usuario (None si no tiene)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT sucursal_id FROM users WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row["sucursal_id"] if row else None


def listar_tecnicos_activos(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre_completo, telefono_whatsapp FROM users WHERE empresa_id = %s AND rol IN ('tecnico','admin') AND activo = TRUE ORDER BY nombre_completo",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_usuarios_activos(empresa_id):
    """Todos los usuarios activos de la empresa, cualquier rol — para elegir participantes de un proyecto."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre_completo, rol, puesto FROM users WHERE empresa_id = %s AND activo = TRUE ORDER BY nombre_completo",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_usuario(empresa_id, username, password, nombre_completo, rol, telefono_whatsapp=None, puesto=None, sucursal_id=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, telefono_whatsapp, puesto, sucursal_id, creado_en) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (empresa_id, username, auth.hash_password(password), nombre_completo, rol, telefono_whatsapp, puesto, sucursal_id, now),
    )
    user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return user_id


def actualizar_usuario(usuario_id, nombre_completo=None, rol=None, telefono_whatsapp=None, activo=None, password=None,
                        puesto=None, restriccion_categoria="__sin_cambio__", acceso_equipos=None,
                        acceso_administracion=None, acceso_compras=None, sucursal_id="__sin_cambio__"):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if nombre_completo is not None:
        campos.append("nombre_completo = %s"); valores.append(nombre_completo)
    if rol is not None:
        campos.append("rol = %s"); valores.append(rol)
    if telefono_whatsapp is not None:
        campos.append("telefono_whatsapp = %s"); valores.append(telefono_whatsapp)
    if puesto is not None:
        campos.append("puesto = %s"); valores.append(puesto)
    if activo is not None:
        campos.append("activo = %s"); valores.append(activo)
    if password:
        campos.append("password_hash = %s"); valores.append(auth.hash_password(password))
    if restriccion_categoria != "__sin_cambio__":  # permite mandar None explícito para quitar la restricción
        campos.append("restriccion_categoria = %s"); valores.append(restriccion_categoria)
    if acceso_equipos is not None:
        campos.append("acceso_equipos = %s"); valores.append(acceso_equipos)
    if acceso_administracion is not None:
        campos.append("acceso_administracion = %s"); valores.append(acceso_administracion)
    if acceso_compras is not None:
        campos.append("acceso_compras = %s"); valores.append(acceso_compras)
    if sucursal_id != "__sin_cambio__":  # permite mandar None explícito para quitar la sucursal
        campos.append("sucursal_id = %s"); valores.append(sucursal_id)
    if campos:
        valores.append(usuario_id)
        cur.execute(f"UPDATE users SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def eliminar_usuario(usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET activo = FALSE WHERE id = %s", (usuario_id,))
    conn.commit()
    cur.close(); conn.close()


# ---- Departamentos ----

def listar_departamentos(empresa_id, solo_activos=True):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM departamentos WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = TRUE"
    query += " ORDER BY nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_departamento(empresa_id, nombre):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO departamentos (empresa_id, nombre) VALUES (%s, %s)", (empresa_id, nombre))
        conn.commit()
    finally:
        cur.close(); conn.close()


def cambiar_estado_departamento(empresa_id, depto_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE departamentos SET activo = %s WHERE id = %s AND empresa_id = %s", (activo, depto_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Categorías ----

def listar_categorias(empresa_id, solo_activos=True):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT c.*, u.nombre_completo AS tecnico_predeterminado_nombre
        FROM categorias c
        LEFT JOIN users u ON u.id = c.tecnico_predeterminado_id
        WHERE c.empresa_id = %s
    """
    params = [empresa_id]
    if solo_activos:
        query += " AND c.activo = TRUE"
    query += " ORDER BY c.nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_categoria(empresa_id, nombre):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categorias (empresa_id, nombre) VALUES (%s, %s)", (empresa_id, nombre))
        conn.commit()
    finally:
        cur.close(); conn.close()


def cambiar_estado_categoria(empresa_id, cat_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE categorias SET activo = %s WHERE id = %s AND empresa_id = %s", (activo, cat_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def asignar_tecnico_categoria(empresa_id, cat_id, tecnico_id):
    """tecnico_id puede ser None para quitar la auto-asignación de esa categoría."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE categorias SET tecnico_predeterminado_id = %s WHERE id = %s AND empresa_id = %s",
                (tecnico_id, cat_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Tickets ----

def _ticket_query_base():
    return """
        SELECT t.*, s.nombre_completo AS solicitante_nombre,
               a.nombre_completo AS asignado_a_nombre
        FROM tickets t
        JOIN users s ON s.id = t.solicitante_id
        LEFT JOIN users a ON a.id = t.asignado_a_id
    """


def _next_folio(cur, empresa_id):
    cur.execute("SELECT COUNT(*) AS n FROM tickets WHERE empresa_id = %s", (empresa_id,))
    return f"TI-{cur.fetchone()['n'] + 1:04d}"


def listar_tickets(empresa_id, estado=None, prioridad=None, categoria=None, solicitante_id=None,
                    departamento=None, fecha_desde=None, fecha_hasta=None, asignado_a_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = _ticket_query_base() + " WHERE t.empresa_id = %s"
    params = [empresa_id]
    if estado:
        query += " AND t.estado = %s"; params.append(estado)
    if prioridad:
        query += " AND t.prioridad = %s"; params.append(prioridad)
    if categoria:
        query += " AND t.categoria = %s"; params.append(categoria)
    if solicitante_id:
        query += " AND t.solicitante_id = %s"; params.append(solicitante_id)
    if asignado_a_id:
        query += " AND t.asignado_a_id = %s"; params.append(asignado_a_id)
    if departamento:
        query += " AND t.departamento = %s"; params.append(departamento)
    if fecha_desde:
        query += " AND t.creado_en >= %s"; params.append(f"{fecha_desde}T00:00:00")
    if fecha_hasta:
        query += " AND t.creado_en <= %s"; params.append(f"{fecha_hasta}T23:59:59")
    query += " ORDER BY CASE t.prioridad WHEN 'urgente' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, t.creado_en DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_ticket(ticket_id, empresa_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = _ticket_query_base() + " WHERE t.id = %s"
    params = [ticket_id]
    if empresa_id is not None:
        query += " AND t.empresa_id = %s"; params.append(empresa_id)
    cur.execute(query, params)
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    ticket = dict(row)
    cur.execute("""
        SELECT c.id, c.texto, c.creado_en, u.nombre_completo AS autor_nombre,
               c.archivo_base64, c.archivo_nombre, c.archivo_tipo
        FROM comentarios c JOIN users u ON u.id = c.autor_id
        WHERE c.ticket_id = %s ORDER BY c.creado_en ASC
    """, (ticket_id,))
    ticket["comentarios"] = [dict(c) for c in cur.fetchall()]
    cur.close(); conn.close()
    return ticket


def crear_ticket(empresa_id, departamento, descripcion, categoria, prioridad, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    folio = _next_folio(cur, empresa_id)
    now = ahora().isoformat(timespec="seconds")

    cur.execute(
        "SELECT tecnico_predeterminado_id FROM categorias WHERE empresa_id = %s AND nombre = %s AND activo = TRUE",
        (empresa_id, categoria),
    )
    fila_categoria = cur.fetchone()
    tecnico_predeterminado_id = fila_categoria["tecnico_predeterminado_id"] if fila_categoria else None

    cur.execute(
        """INSERT INTO tickets
           (empresa_id, folio, departamento, descripcion, categoria, prioridad, estado, solicitante_id,
            asignado_a_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, 'abierto', %s, %s, %s, %s) RETURNING id""",
        (empresa_id, folio, departamento, descripcion, categoria, prioridad, usuario_id,
         tecnico_predeterminado_id, now, now),
    )
    ticket_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return obtener_ticket(ticket_id)


def actualizar_ticket(ticket_id, estado=None, prioridad=None, asignado_a_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tickets WHERE id = %s", (ticket_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    now = ahora().isoformat(timespec="seconds")
    campos, valores = [], []
    if estado is not None:
        campos.append("estado = %s"); valores.append(estado)
        campos.append("resuelto_en = %s")
        valores.append(now if estado in ("resuelto", "cerrado") else None)
    if prioridad is not None:
        campos.append("prioridad = %s"); valores.append(prioridad)
    if asignado_a_id is not None:
        campos.append("asignado_a_id = %s"); valores.append(asignado_a_id)
    campos.append("actualizado_en = %s"); valores.append(now)
    valores.append(ticket_id)
    cur.execute(f"UPDATE tickets SET {', '.join(campos)} WHERE id = %s", valores)
    conn.commit()
    cur.close(); conn.close()
    return obtener_ticket(ticket_id)


def agregar_comentario(ticket_id, usuario_id, texto, archivo_base64=None, archivo_nombre=None, archivo_tipo=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tickets WHERE id = %s", (ticket_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO comentarios (ticket_id, autor_id, texto, creado_en, archivo_base64, archivo_nombre, archivo_tipo)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (ticket_id, usuario_id, texto, now, archivo_base64, archivo_nombre, archivo_tipo),
    )
    cur.execute("UPDATE tickets SET actualizado_en = %s WHERE id = %s", (now, ticket_id))
    conn.commit()
    cur.close(); conn.close()
    return obtener_ticket(ticket_id)


def firmar_ticket(ticket_id, firma_base64, firmado_por):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tickets WHERE id = %s", (ticket_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE tickets
           SET estado = 'cerrado', resuelto_en = %s, actualizado_en = %s,
               firma = %s, firmado_por = %s, firmado_en = %s
           WHERE id = %s""",
        (now, now, firma_base64, firmado_por, now, ticket_id),
    )
    conn.commit()
    cur.close(); conn.close()
    return obtener_ticket(ticket_id)


def detalle_dashboard(empresa_id):
    """Igual que estadisticas_dashboard, pero con los desgloses adicionales que
    necesita el PDF del Dashboard: tickets por departamento/categoría, reparaciones
    por sucursal y por cliente (doctor), equipos por tipo."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT estado, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    tickets_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("SELECT departamento, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY departamento ORDER BY n DESC",
                (empresa_id,))
    tickets_departamento = [(r["departamento"], r["n"]) for r in cur.fetchall()]
    cur.execute("SELECT categoria, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY categoria ORDER BY n DESC",
                (empresa_id,))
    tickets_categoria = [(r["categoria"], r["n"]) for r in cur.fetchall()]

    cur.execute("SELECT estado, COUNT(*) AS n FROM reparaciones WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    reparaciones_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("""
        SELECT COALESCE(s.nombre, 'Sin sucursal') AS sucursal, COUNT(*) AS n
        FROM reparaciones r LEFT JOIN sucursales_reparacion s ON s.id = r.sucursal_id
        WHERE r.empresa_id = %s GROUP BY s.nombre ORDER BY n DESC
    """, (empresa_id,))
    reparaciones_sucursal = [(r["sucursal"], r["n"]) for r in cur.fetchall()]
    cur.execute("""
        SELECT cliente_nombre, COUNT(*) AS n FROM reparaciones
        WHERE empresa_id = %s GROUP BY cliente_nombre ORDER BY n DESC
    """, (empresa_id,))
    reparaciones_cliente = [(r["cliente_nombre"], r["n"]) for r in cur.fetchall()]

    cur.execute("SELECT estado, COUNT(*) AS n FROM proyectos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    proyectos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM equipos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    equipos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("SELECT tipo, COUNT(*) AS n FROM equipos WHERE empresa_id = %s GROUP BY tipo ORDER BY n DESC", (empresa_id,))
    equipos_tipo = [(r["tipo"], r["n"]) for r in cur.fetchall()]

    cur.execute("SELECT estado, COUNT(*) AS n FROM ciclos_compra WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    ciclos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("""
        SELECT COUNT(*) AS n FROM pedidos_compra p JOIN ciclos_compra c ON c.id = p.ciclo_id
        WHERE c.empresa_id = %s
    """, (empresa_id,))
    pedidos_total = cur.fetchone()["n"]

    cur.close(); conn.close()

    return {
        "tickets": {
            "por_estado": {e: tickets_estado.get(e, 0) for e in ESTADOS}, "total": sum(tickets_estado.values()),
            "por_departamento": tickets_departamento, "por_categoria": tickets_categoria,
        },
        "reparaciones": {
            "por_estado": {e: reparaciones_estado.get(e, 0) for e in ESTADOS_REPARACION}, "total": sum(reparaciones_estado.values()),
            "por_sucursal": reparaciones_sucursal, "por_cliente": reparaciones_cliente,
        },
        "proyectos": {
            "por_estado": {e: proyectos_estado.get(e, 0) for e in ESTADOS_PROYECTO}, "total": sum(proyectos_estado.values()),
        },
        "equipos": {
            "por_estado": {e: equipos_estado.get(e, 0) for e in ESTADOS_EQUIPO}, "total": sum(equipos_estado.values()),
            "por_tipo": equipos_tipo,
        },
        "compras": {
            "ciclos_por_estado": {e: ciclos_estado.get(e, 0) for e in ESTADOS_CICLO_COMPRA}, "ciclos_total": sum(ciclos_estado.values()),
            "pedidos_total": pedidos_total,
        },
    }


def estadisticas_dashboard(empresa_id):
    """Resumen de todos los módulos para el Dashboard general (usuario master / admin)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT estado, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    tickets_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM reparaciones WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    reparaciones_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM proyectos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    proyectos_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM equipos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    equipos_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM ciclos_compra WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    ciclos_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("""
        SELECT COUNT(*) AS n FROM pedidos_compra p JOIN ciclos_compra c ON c.id = p.ciclo_id
        WHERE c.empresa_id = %s AND c.estado = 'abierto'
    """, (empresa_id,))
    pedidos_pendientes = cur.fetchone()["n"]

    cur.close(); conn.close()

    return {
        "tickets": {
            "por_estado": {e: tickets_por_estado.get(e, 0) for e in ESTADOS},
            "total": sum(tickets_por_estado.values()),
        },
        "reparaciones": {
            "por_estado": {e: reparaciones_por_estado.get(e, 0) for e in ESTADOS_REPARACION},
            "total": sum(reparaciones_por_estado.values()),
        },
        "proyectos": {
            "por_estado": {e: proyectos_por_estado.get(e, 0) for e in ESTADOS_PROYECTO},
            "total": sum(proyectos_por_estado.values()),
        },
        "equipos": {
            "por_estado": {e: equipos_por_estado.get(e, 0) for e in ESTADOS_EQUIPO},
            "total": sum(equipos_por_estado.values()),
        },
        "compras": {
            "ciclos_por_estado": {e: ciclos_por_estado.get(e, 0) for e in ESTADOS_CICLO_COMPRA},
            "ciclos_total": sum(ciclos_por_estado.values()),
            "pedidos_pendientes": pedidos_pendientes,
        },
    }


def estadisticas(empresa_id, asignado_a_id=None, categoria=None):
    conn = get_connection()
    cur = conn.cursor()
    filtro_extra = ""
    params_extra = []
    if asignado_a_id:
        filtro_extra += " AND asignado_a_id = %s"; params_extra.append(asignado_a_id)
    if categoria:
        filtro_extra += " AND categoria = %s"; params_extra.append(categoria)

    cur.execute(f"SELECT estado, COUNT(*) AS n FROM tickets WHERE empresa_id = %s{filtro_extra} GROUP BY estado",
                [empresa_id] + params_extra)
    por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute(
        f"SELECT COUNT(*) AS n FROM tickets WHERE empresa_id = %s AND prioridad = 'urgente' AND estado NOT IN ('resuelto','cerrado'){filtro_extra}",
        [empresa_id] + params_extra,
    )
    urgentes_abiertos = cur.fetchone()["n"]

    cur.execute(
        f"SELECT creado_en, resuelto_en FROM tickets WHERE empresa_id = %s AND resuelto_en IS NOT NULL{filtro_extra}",
        [empresa_id] + params_extra,
    )
    tiempos = cur.fetchall()
    cur.close(); conn.close()

    horas = []
    for t in tiempos:
        creado = datetime.fromisoformat(t["creado_en"])
        resuelto = datetime.fromisoformat(t["resuelto_en"])
        horas.append((resuelto - creado).total_seconds() / 3600)
    promedio_horas = round(sum(horas) / len(horas), 1) if horas else 0

    return {
        "por_estado": {e: por_estado.get(e, 0) for e in ESTADOS},
        "urgentes_abiertos": urgentes_abiertos,
        "tiempo_promedio_resolucion_horas": promedio_horas,
        "total": sum(por_estado.values()),
    }


# ---- Equipos (inventario de cómputo/impresoras) ----

def listar_equipos(empresa_id, tipo=None, estado=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT e.*, s.nombre AS sucursal_nombre, u.nombre_completo AS usuario_nombre
        FROM equipos e
        LEFT JOIN sucursales_reparacion s ON s.id = e.sucursal_id
        LEFT JOIN users u ON u.id = e.usuario_id
        WHERE e.empresa_id = %s
    """
    params = [empresa_id]
    if tipo:
        query += " AND e.tipo = %s"; params.append(tipo)
    if estado:
        query += " AND e.estado = %s"; params.append(estado)
    else:
        query += " AND e.estado != 'baja'"
    query += " ORDER BY e.nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_equipo(empresa_id, equipo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.*, s.nombre AS sucursal_nombre, u.nombre_completo AS usuario_nombre
        FROM equipos e
        LEFT JOIN sucursales_reparacion s ON s.id = e.sucursal_id
        LEFT JOIN users u ON u.id = e.usuario_id
        WHERE e.id = %s AND e.empresa_id = %s
    """, (equipo_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def crear_equipo(empresa_id, tipo, nombre, marca=None, modelo=None, numero_serie=None,
                  departamento=None, responsable=None, fecha_adquisicion=None, notas=None, sucursal_id=None,
                  usuario_id=None, usuario_microsip=None, password_microsip=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO equipos
           (empresa_id, tipo, nombre, marca, modelo, numero_serie, departamento, responsable,
            estado, fecha_adquisicion, notas, sucursal_id, usuario_id, usuario_microsip, password_microsip,
            creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'activo', %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, tipo, nombre, marca, modelo, numero_serie, departamento, responsable,
         fecha_adquisicion, notas, sucursal_id, usuario_id, usuario_microsip, password_microsip, now, now),
    )
    equipo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return obtener_equipo(empresa_id, equipo_id)


def actualizar_equipo(empresa_id, equipo_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = ["tipo", "nombre", "marca", "modelo", "numero_serie", "departamento",
                  "responsable", "estado", "fecha_adquisicion", "notas", "sucursal_id",
                  "usuario_id", "usuario_microsip", "password_microsip"]
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        campos.append("actualizado_en = %s"); valores.append(ahora().isoformat(timespec="seconds"))
        valores += [equipo_id, empresa_id]
        cur.execute(f"UPDATE equipos SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()
    return obtener_equipo(empresa_id, equipo_id)


def dar_de_baja_equipo(empresa_id, equipo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE equipos SET estado = 'baja', actualizado_en = %s WHERE id = %s AND empresa_id = %s",
                (ahora().isoformat(timespec="seconds"), equipo_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Mantenimientos programados ----

def _siguiente_fecha(fecha_str, frecuencia):
    fecha = datetime.fromisoformat(fecha_str)
    meses_por_frecuencia = {"mensual": 1, "trimestral": 3, "semestral": 6, "anual": 12}
    meses = meses_por_frecuencia.get(frecuencia)
    if not meses:
        return None
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, 28)  # evita errores con meses cortos (simple y suficiente aquí)
    return fecha.replace(year=anio, month=mes, day=dia).isoformat()


def listar_mantenimientos(empresa_id, estado=None, equipo_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT m.*, e.nombre AS equipo_nombre, e.tipo AS equipo_tipo, e.departamento AS equipo_departamento,
               t.folio AS ticket_folio, t.estado AS ticket_estado,
               u.nombre_completo AS tecnico_nombre
        FROM mantenimientos m
        JOIN equipos e ON e.id = m.equipo_id
        LEFT JOIN tickets t ON t.id = m.ticket_id
        LEFT JOIN users u ON u.id = m.tecnico_asignado_id
        WHERE m.empresa_id = %s
    """
    params = [empresa_id]
    if estado:
        query += " AND m.estado = %s"; params.append(estado)
    if equipo_id:
        query += " AND m.equipo_id = %s"; params.append(equipo_id)
    query += " ORDER BY m.fecha_programada ASC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()

    hoy = ahora().date().isoformat()
    for r in rows:
        if r["estado"] == "pendiente" and r["fecha_programada"][:10] < hoy:
            r["estado"] = "vencido"
    return rows


_NOMBRES_TIPO_MANT = {"preventivo": "Preventivo", "correctivo": "Correctivo"}


def crear_mantenimiento(empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia="unica",
                         notas=None, tecnico_asignado_id=None, creado_por_id=None):
    equipo = obtener_equipo(empresa_id, equipo_id)
    if not equipo:
        return None

    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")

    ticket_id = None
    if creado_por_id:
        ticket = crear_ticket(
            empresa_id,
            departamento=equipo.get("departamento") or "Sistemas",
            descripcion=f"Mantenimiento {_NOMBRES_TIPO_MANT.get(tipo, tipo)} programado — Equipo: {equipo['nombre']}. {descripcion}",
            categoria="hardware",
            prioridad="media",
            usuario_id=creado_por_id,
        )
        ticket_id = ticket["id"]
        if tecnico_asignado_id:
            actualizar_ticket(ticket_id, asignado_a_id=tecnico_asignado_id)

    cur.execute(
        """INSERT INTO mantenimientos
           (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia, estado, notas, creado_en,
            ticket_id, tecnico_asignado_id, creado_por_id)
           VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia, notas, now,
         ticket_id, tecnico_asignado_id, creado_por_id),
    )
    mant_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return mant_id


def marcar_mantenimiento_realizado(empresa_id, mantenimiento_id, realizado_por, notas=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mantenimientos WHERE id = %s AND empresa_id = %s", (mantenimiento_id, empresa_id))
    mant = cur.fetchone()
    if not mant:
        cur.close(); conn.close()
        return None
    mant = dict(mant)
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE mantenimientos SET estado = 'realizado', realizado_en = %s, realizado_por = %s, notas = %s WHERE id = %s",
        (now, realizado_por, notas or mant.get("notas"), mantenimiento_id),
    )
    conn.commit()
    cur.close(); conn.close()

    # Si el mantenimiento tiene un ticket vinculado, se marca como resuelto también
    if mant.get("ticket_id"):
        actualizar_ticket(mant["ticket_id"], estado="resuelto")

    # Si es recurrente, se programa solo el siguiente (con su propio ticket y el mismo técnico)
    siguiente_id = None
    siguiente_fecha = _siguiente_fecha(mant["fecha_programada"], mant["frecuencia"])
    if siguiente_fecha:
        siguiente_id = crear_mantenimiento(
            empresa_id, mant["equipo_id"], mant["tipo"], mant["descripcion"], siguiente_fecha, mant["frecuencia"],
            tecnico_asignado_id=mant.get("tecnico_asignado_id"),
            creado_por_id=mant.get("creado_por_id"),
        )

    return {"realizado_id": mantenimiento_id, "siguiente_id": siguiente_id}


def reprogramar_mantenimiento(empresa_id, mantenimiento_id, fecha_programada=None, descripcion=None, frecuencia=None):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if fecha_programada:
        campos.append("fecha_programada = %s"); valores.append(fecha_programada)
    if descripcion:
        campos.append("descripcion = %s"); valores.append(descripcion)
    if frecuencia:
        campos.append("frecuencia = %s"); valores.append(frecuencia)
    if campos:
        valores += [mantenimiento_id, empresa_id]
        cur.execute(f"UPDATE mantenimientos SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def eliminar_mantenimiento(empresa_id, mantenimiento_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mantenimientos WHERE id = %s AND empresa_id = %s", (mantenimiento_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Respaldo y clonación de empresas (superadmin) ----

def exportar_empresa(empresa_id):
    """Exporta todos los datos de una empresa como respaldo descargable.
    No incluye password_hash de los usuarios por seguridad (este archivo
    es solo para respaldo/consulta, no para restaurar logins)."""
    empresa = obtener_empresa(empresa_id)
    if not empresa:
        return None

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, nombre_completo, rol, telefono_whatsapp, activo, creado_en FROM users WHERE empresa_id = %s", (empresa_id,))
    usuarios = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT nombre, activo FROM departamentos WHERE empresa_id = %s", (empresa_id,))
    departamentos = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT nombre, activo FROM categorias WHERE empresa_id = %s", (empresa_id,))
    categorias = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM equipos WHERE empresa_id = %s", (empresa_id,))
    equipos = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM mantenimientos WHERE empresa_id = %s", (empresa_id,))
    mantenimientos = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM tickets WHERE empresa_id = %s", (empresa_id,))
    tickets = [dict(r) for r in cur.fetchall()]

    ticket_ids = [t["id"] for t in tickets]
    comentarios = []
    if ticket_ids:
        marcador = ",".join(["%s"] * len(ticket_ids))
        cur.execute(f"SELECT * FROM comentarios WHERE ticket_id IN ({marcador})", ticket_ids)
        comentarios = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()

    return {
        "empresa": empresa,
        "usuarios": usuarios,
        "departamentos": departamentos,
        "categorias": categorias,
        "equipos": equipos,
        "mantenimientos": mantenimientos,
        "tickets": tickets,
        "comentarios": comentarios,
        "exportado_en": ahora().isoformat(timespec="seconds"),
    }


def _username_disponible(cur, username):
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    return cur.fetchone() is None


def clonar_empresa(origen_empresa_id, nombre_nueva_empresa, sufijo_usuarios):
    """Copia una empresa completa (usuarios, departamentos, categorías,
    equipos, mantenimientos, tickets y comentarios) hacia una empresa nueva.
    Los usuarios se copian con el mismo password (mismo hash) pero un
    username distinto, ya que el username es único en todo el sistema.
    """
    origen = obtener_empresa(origen_empresa_id)
    if not origen:
        return None

    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")

    # 1. Nueva empresa (copia también el logo)
    cur.execute(
        "INSERT INTO empresas (nombre, logo_base64, creado_en) VALUES (%s, %s, %s) RETURNING id",
        (nombre_nueva_empresa, origen.get("logo_base64"), now),
    )
    nueva_empresa_id = cur.fetchone()["id"]
    conn.commit()

    # 2. Usuarios (mismo hash de contraseña, username con sufijo para no chocar)
    cur.execute("SELECT * FROM users WHERE empresa_id = %s", (origen_empresa_id,))
    usuarios_origen = [dict(r) for r in cur.fetchall()]
    mapa_usuarios = {}
    usuarios_nuevos = []
    for u in usuarios_origen:
        nuevo_username = f"{u['username']}_{sufijo_usuarios}"
        intento = 1
        base = nuevo_username
        while not _username_disponible(cur, nuevo_username):
            intento += 1
            nuevo_username = f"{base}{intento}"
        cur.execute(
            """INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, telefono_whatsapp, activo, creado_en)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (nueva_empresa_id, nuevo_username, u["password_hash"], u["nombre_completo"], u["rol"],
             u["telefono_whatsapp"], u["activo"], now),
        )
        mapa_usuarios[u["id"]] = cur.fetchone()["id"]
        usuarios_nuevos.append({"original": u["username"], "nuevo": nuevo_username})
    conn.commit()

    # 3. Departamentos y categorías
    cur.execute("SELECT nombre, activo FROM departamentos WHERE empresa_id = %s", (origen_empresa_id,))
    for d in cur.fetchall():
        cur.execute("INSERT INTO departamentos (empresa_id, nombre, activo) VALUES (%s, %s, %s)",
                     (nueva_empresa_id, d["nombre"], d["activo"]))
    cur.execute("SELECT nombre, activo FROM categorias WHERE empresa_id = %s", (origen_empresa_id,))
    for c in cur.fetchall():
        cur.execute("INSERT INTO categorias (empresa_id, nombre, activo) VALUES (%s, %s, %s)",
                     (nueva_empresa_id, c["nombre"], c["activo"]))
    conn.commit()

    # 4. Equipos
    cur.execute("SELECT * FROM equipos WHERE empresa_id = %s", (origen_empresa_id,))
    equipos_origen = [dict(r) for r in cur.fetchall()]
    mapa_equipos = {}
    for e in equipos_origen:
        cur.execute(
            """INSERT INTO equipos (empresa_id, tipo, nombre, marca, modelo, numero_serie, departamento,
                                     responsable, estado, fecha_adquisicion, notas, creado_en, actualizado_en)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (nueva_empresa_id, e["tipo"], e["nombre"], e["marca"], e["modelo"], e["numero_serie"], e["departamento"],
             e["responsable"], e["estado"], e["fecha_adquisicion"], e["notas"], e["creado_en"], e["actualizado_en"]),
        )
        mapa_equipos[e["id"]] = cur.fetchone()["id"]
    conn.commit()

    # 5. Tickets (con folios repetidos, es válido: UNIQUE es por empresa)
    cur.execute("SELECT * FROM tickets WHERE empresa_id = %s", (origen_empresa_id,))
    tickets_origen = [dict(r) for r in cur.fetchall()]
    mapa_tickets = {}
    for t in tickets_origen:
        nuevo_solicitante = mapa_usuarios.get(t["solicitante_id"])
        nuevo_asignado = mapa_usuarios.get(t["asignado_a_id"]) if t["asignado_a_id"] else None
        cur.execute(
            """INSERT INTO tickets (empresa_id, folio, departamento, descripcion, categoria, prioridad, estado,
                                     solicitante_id, asignado_a_id, creado_en, actualizado_en, resuelto_en,
                                     firma, firmado_por, firmado_en)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (nueva_empresa_id, t["folio"], t["departamento"], t["descripcion"], t["categoria"], t["prioridad"],
             t["estado"], nuevo_solicitante, nuevo_asignado, t["creado_en"], t["actualizado_en"], t["resuelto_en"],
             t["firma"], t["firmado_por"], t["firmado_en"]),
        )
        mapa_tickets[t["id"]] = cur.fetchone()["id"]
    conn.commit()

    # 6. Comentarios (de todos los tickets copiados)
    if tickets_origen:
        ids_origen = [t["id"] for t in tickets_origen]
        marcador = ",".join(["%s"] * len(ids_origen))
        cur.execute(f"SELECT * FROM comentarios WHERE ticket_id IN ({marcador})", ids_origen)
        for c in cur.fetchall():
            c = dict(c)
            nuevo_ticket_id = mapa_tickets.get(c["ticket_id"])
            nuevo_autor_id = mapa_usuarios.get(c["autor_id"])
            if nuevo_ticket_id and nuevo_autor_id:
                cur.execute(
                    """INSERT INTO comentarios (ticket_id, autor_id, texto, creado_en, archivo_base64, archivo_nombre, archivo_tipo)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (nuevo_ticket_id, nuevo_autor_id, c["texto"], c["creado_en"],
                     c.get("archivo_base64"), c.get("archivo_nombre"), c.get("archivo_tipo")),
                )
        conn.commit()

    # 7. Mantenimientos (mapeando equipo, ticket vinculado, técnico y creador)
    cur.execute("SELECT * FROM mantenimientos WHERE empresa_id = %s", (origen_empresa_id,))
    for m in cur.fetchall():
        m = dict(m)
        nuevo_equipo_id = mapa_equipos.get(m["equipo_id"])
        if not nuevo_equipo_id:
            continue
        nuevo_ticket_id = mapa_tickets.get(m["ticket_id"]) if m.get("ticket_id") else None
        nuevo_tecnico_id = mapa_usuarios.get(m["tecnico_asignado_id"]) if m.get("tecnico_asignado_id") else None
        nuevo_creador_id = mapa_usuarios.get(m["creado_por_id"]) if m.get("creado_por_id") else None
        cur.execute(
            """INSERT INTO mantenimientos (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia,
                                            estado, realizado_en, realizado_por, notas, creado_en,
                                            ticket_id, tecnico_asignado_id, creado_por_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (nueva_empresa_id, nuevo_equipo_id, m["tipo"], m["descripcion"], m["fecha_programada"], m["frecuencia"],
             m["estado"], m["realizado_en"], m["realizado_por"], m["notas"], m["creado_en"],
             nuevo_ticket_id, nuevo_tecnico_id, nuevo_creador_id),
        )
    conn.commit()

    cur.close(); conn.close()
    return {
        "empresa_id": nueva_empresa_id,
        "usuarios_copiados": len(mapa_usuarios),
        "tickets_copiados": len(mapa_tickets),
        "equipos_copiados": len(mapa_equipos),
        "usuarios_nuevos": usuarios_nuevos,
    }


# ---- Proyectos ----

def _proyecto_query_base():
    return """
        SELECT p.*, c.nombre_completo AS creado_por_nombre
        FROM proyectos p
        JOIN users c ON c.id = p.creado_por_id
    """


def _enriquecer_proyecto(cur, proyecto):
    """Agrega participantes (personas y departamentos), su estado de firma, y calcula el tiempo transcurrido."""
    cur.execute("""
        SELECT u.id, u.nombre_completo,
               COALESCE(pf.estado, 'pendiente') AS firma_estado,
               pf.motivo_no_conforme, pf.actualizado_en AS firma_actualizado_en
        FROM proyecto_participantes_usuarios pu
        JOIN users u ON u.id = pu.usuario_id
        LEFT JOIN proyecto_firmas pf ON pf.proyecto_id = pu.proyecto_id AND pf.usuario_id = pu.usuario_id
        WHERE pu.proyecto_id = %s ORDER BY u.nombre_completo
    """, (proyecto["id"],))
    proyecto["participantes_usuarios"] = [dict(r) for r in cur.fetchall()]
    proyecto["todos_resolvieron_firma"] = all(
        p["firma_estado"] != "pendiente" for p in proyecto["participantes_usuarios"]
    )

    cur.execute("""
        SELECT departamento FROM proyecto_participantes_departamentos
        WHERE proyecto_id = %s ORDER BY departamento
    """, (proyecto["id"],))
    proyecto["participantes_departamentos"] = [r["departamento"] for r in cur.fetchall()]

    cur.execute("""
        SELECT t.*, u.nombre_completo AS usuario_nombre
        FROM proyecto_tareas t JOIN users u ON u.id = t.usuario_id
        WHERE t.proyecto_id = %s ORDER BY t.creado_en ASC
    """, (proyecto["id"],))
    proyecto["tareas"] = [dict(r) for r in cur.fetchall()]

    if proyecto.get("fecha_inicio"):
        inicio = datetime.fromisoformat(proyecto["fecha_inicio"])
        fin = datetime.fromisoformat(proyecto["fecha_completado"]) if proyecto.get("fecha_completado") else ahora()
        proyecto["dias_transcurridos"] = round((fin - inicio).total_seconds() / 86400, 1)
    else:
        proyecto["dias_transcurridos"] = None

    return proyecto


def listar_proyectos(empresa_id, participante_usuario_id=None, estado=None):
    conn = get_connection()
    cur = conn.cursor()
    query = _proyecto_query_base() + " WHERE p.empresa_id = %s"
    params = [empresa_id]
    if participante_usuario_id:
        query += " AND p.id IN (SELECT proyecto_id FROM proyecto_participantes_usuarios WHERE usuario_id = %s)"
        params.append(participante_usuario_id)
    if estado:
        query += " AND p.estado = %s"; params.append(estado)
    query += " ORDER BY p.creado_en DESC"
    cur.execute(query, params)
    proyectos = [dict(r) for r in cur.fetchall()]
    for p in proyectos:
        _enriquecer_proyecto(cur, p)
    cur.close(); conn.close()
    return proyectos


def obtener_proyecto(empresa_id, proyecto_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(_proyecto_query_base() + " WHERE p.id = %s AND p.empresa_id = %s", (proyecto_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    proyecto = dict(row)
    _enriquecer_proyecto(cur, proyecto)

    cur.execute("""
        SELECT a.id, a.texto, a.creado_en, a.archivo_base64, a.archivo_nombre, a.archivo_tipo,
               u.nombre_completo AS autor_nombre
        FROM proyecto_actualizaciones a JOIN users u ON u.id = a.autor_id
        WHERE a.proyecto_id = %s ORDER BY a.creado_en ASC
    """, (proyecto_id,))
    proyecto["actualizaciones"] = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()
    return proyecto


def es_participante_proyecto(proyecto_id, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM proyecto_participantes_usuarios WHERE proyecto_id = %s AND usuario_id = %s",
                (proyecto_id, usuario_id))
    resultado = cur.fetchone() is not None
    cur.close(); conn.close()
    return resultado


def crear_proyecto(empresa_id, nombre, descripcion, fecha_estimada, creado_por_id,
                    participantes_usuarios=None, participantes_departamentos=None, tareas=None):
    """tareas: lista opcional de {"usuario_id": int, "descripcion": str, "fecha_limite": str|None} —
    cada persona agregada al proyecto puede traer ya su tarea específica asignada."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO proyectos (empresa_id, nombre, descripcion, estado, fecha_estimada, creado_por_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, 'planificacion', %s, %s, %s, %s) RETURNING id""",
        (empresa_id, nombre, descripcion, fecha_estimada, creado_por_id, now, now),
    )
    proyecto_id = cur.fetchone()["id"]

    for uid in (participantes_usuarios or []):
        cur.execute(
            "INSERT INTO proyecto_participantes_usuarios (proyecto_id, usuario_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (proyecto_id, uid),
        )
    for depto in (participantes_departamentos or []):
        cur.execute(
            "INSERT INTO proyecto_participantes_departamentos (proyecto_id, departamento) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (proyecto_id, depto),
        )
    for t in (tareas or []):
        if t.get("usuario_id") and t.get("descripcion"):
            cur.execute(
                """INSERT INTO proyecto_tareas (proyecto_id, usuario_id, descripcion, estado, fecha_limite, creado_en, actualizado_en)
                   VALUES (%s, %s, %s, 'pendiente', %s, %s, %s)""",
                (proyecto_id, t["usuario_id"], t["descripcion"].strip(), t.get("fecha_limite"), now, now),
            )
    conn.commit()
    cur.close(); conn.close()
    return proyecto_id


def crear_tarea_proyecto(proyecto_id, usuario_id, descripcion, fecha_limite=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO proyecto_tareas (proyecto_id, usuario_id, descripcion, estado, fecha_limite, creado_en, actualizado_en)
           VALUES (%s, %s, %s, 'pendiente', %s, %s, %s) RETURNING id""",
        (proyecto_id, usuario_id, descripcion.strip(), fecha_limite, now, now),
    )
    tarea_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return tarea_id


def cambiar_estado_tarea_proyecto(tarea_id, estado):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("UPDATE proyecto_tareas SET estado = %s, actualizado_en = %s WHERE id = %s", (estado, now, tarea_id))
    conn.commit()
    cur.close(); conn.close()


def eliminar_tarea_proyecto(tarea_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM proyecto_tareas WHERE id = %s", (tarea_id,))
    conn.commit()
    cur.close(); conn.close()


def obtener_tarea_proyecto(tarea_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM proyecto_tareas WHERE id = %s", (tarea_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def actualizar_proyecto(empresa_id, proyecto_id, nombre=None, descripcion=None, fecha_estimada=None):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre = %s"); valores.append(nombre)
    if descripcion is not None:
        campos.append("descripcion = %s"); valores.append(descripcion)
    if fecha_estimada is not None:
        campos.append("fecha_estimada = %s"); valores.append(fecha_estimada)
    if campos:
        campos.append("actualizado_en = %s"); valores.append(ahora().isoformat(timespec="seconds"))
        valores += [proyecto_id, empresa_id]
        cur.execute(f"UPDATE proyectos SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def firmar_participante_proyecto(proyecto_id, usuario_id, firma_base64):
    """El participante firma su compromiso con el proyecto — desbloquea el inicio
    si con esto ya no queda nadie pendiente. Si antes había dicho que no estaba
    conforme, esto lo reemplaza (ya cambió de opinión y sí firmó)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        INSERT INTO proyecto_firmas (proyecto_id, usuario_id, estado, firma_base64, motivo_no_conforme, actualizado_en)
        VALUES (%s, %s, 'firmado', %s, NULL, %s)
        ON CONFLICT (proyecto_id, usuario_id) DO UPDATE SET
            estado = 'firmado', firma_base64 = %s, motivo_no_conforme = NULL, actualizado_en = %s
    """, (proyecto_id, usuario_id, firma_base64, now, firma_base64, now))
    conn.commit()
    cur.close(); conn.close()


def marcar_no_conforme_proyecto(proyecto_id, usuario_id, motivo):
    """El participante no está de acuerdo, pero deja por escrito el motivo — esto
    SÍ cuenta como 'resuelto' para poder iniciar el proyecto (no bloquea), a
    diferencia de quedarse sin responder nada."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        INSERT INTO proyecto_firmas (proyecto_id, usuario_id, estado, firma_base64, motivo_no_conforme, actualizado_en)
        VALUES (%s, %s, 'no_conforme', NULL, %s, %s)
        ON CONFLICT (proyecto_id, usuario_id) DO UPDATE SET
            estado = 'no_conforme', motivo_no_conforme = %s, actualizado_en = %s
    """, (proyecto_id, usuario_id, motivo, now, motivo, now))
    conn.commit()
    cur.close(); conn.close()


def participantes_pendientes_de_firma(proyecto_id):
    """Participantes que todavía no firmaron NI dijeron por qué no están conformes."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.nombre_completo
        FROM proyecto_participantes_usuarios pu
        JOIN users u ON u.id = pu.usuario_id
        LEFT JOIN proyecto_firmas pf ON pf.proyecto_id = pu.proyecto_id AND pf.usuario_id = pu.usuario_id
        WHERE pu.proyecto_id = %s AND pf.estado IS NULL
        ORDER BY u.nombre_completo
    """, (proyecto_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def iniciar_proyecto(empresa_id, proyecto_id):
    """Marca el inicio real del proyecto: arranca el conteo de tiempo transcurrido.
    Solo si NINGÚN participante quedó sin responder (deben haber firmado, o al
    menos dicho por qué no están conformes)."""
    pendientes = participantes_pendientes_de_firma(proyecto_id)
    if pendientes:
        return {"ok": False, "pendientes": pendientes}

    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE proyectos SET estado = 'en_progreso', fecha_inicio = %s, actualizado_en = %s WHERE id = %s AND empresa_id = %s AND fecha_inicio IS NULL",
        (now, now, proyecto_id, empresa_id),
    )
    conn.commit()
    cur.close(); conn.close()
    return {"ok": True, "pendientes": []}


def cambiar_estado_proyecto(empresa_id, proyecto_id, estado):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    campos = ["estado = %s", "actualizado_en = %s"]
    valores = [estado, now]
    if estado == "completado":
        campos.append("fecha_completado = %s"); valores.append(now)
    valores += [proyecto_id, empresa_id]
    cur.execute(f"UPDATE proyectos SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
    conn.commit()
    cur.close(); conn.close()


def agregar_participante_usuario(proyecto_id, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO proyecto_participantes_usuarios (proyecto_id, usuario_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (proyecto_id, usuario_id),
    )
    conn.commit()
    cur.close(); conn.close()


def quitar_participante_usuario(proyecto_id, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM proyecto_participantes_usuarios WHERE proyecto_id = %s AND usuario_id = %s",
                (proyecto_id, usuario_id))
    conn.commit()
    cur.close(); conn.close()


def agregar_participante_departamento(proyecto_id, departamento):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO proyecto_participantes_departamentos (proyecto_id, departamento) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (proyecto_id, departamento),
    )
    conn.commit()
    cur.close(); conn.close()


def quitar_participante_departamento(proyecto_id, departamento):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM proyecto_participantes_departamentos WHERE proyecto_id = %s AND departamento = %s",
                (proyecto_id, departamento))
    conn.commit()
    cur.close(); conn.close()


def agregar_actualizacion_proyecto(proyecto_id, autor_id, texto, archivo_base64=None, archivo_nombre=None, archivo_tipo=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM proyectos WHERE id = %s", (proyecto_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO proyecto_actualizaciones (proyecto_id, autor_id, texto, archivo_base64, archivo_nombre, archivo_tipo, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (proyecto_id, autor_id, texto, archivo_base64, archivo_nombre, archivo_tipo, now),
    )
    cur.execute("UPDATE proyectos SET actualizado_en = %s WHERE id = %s", (now, proyecto_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Compras: catálogo de artículos ----

def listar_articulos_compra(empresa_id, solo_activos=True):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM articulos_compra WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = TRUE"
    query += " ORDER BY nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_articulo_compra(empresa_id, articulo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM articulos_compra WHERE id = %s AND empresa_id = %s", (articulo_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def crear_articulo_compra(empresa_id, nombre, proveedor=None, marca=None, foto_base64=None, notas=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO articulos_compra (empresa_id, nombre, proveedor, marca, foto_base64, notas, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, nombre, proveedor, marca, foto_base64, notas, now),
    )
    articulo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return articulo_id


def actualizar_articulo_compra(empresa_id, articulo_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = ["nombre", "proveedor", "marca", "foto_base64", "notas", "activo"]
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [articulo_id, empresa_id]
        cur.execute(f"UPDATE articulos_compra SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def dar_de_baja_articulo_compra(empresa_id, articulo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE articulos_compra SET activo = FALSE WHERE id = %s AND empresa_id = %s", (articulo_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Compras: ciclos y pedidos ----

def _siguiente_fecha_compra(fecha_str, frecuencia):
    fecha = datetime.fromisoformat(fecha_str)
    if frecuencia == "semanal":
        return (fecha + timedelta(days=7)).isoformat()
    if frecuencia == "quincenal":
        return (fecha + timedelta(days=15)).isoformat()
    if frecuencia == "mensual":
        mes_total = fecha.month - 1 + 1
        anio = fecha.year + mes_total // 12
        mes = mes_total % 12 + 1
        dia = min(fecha.day, 28)
        return fecha.replace(year=anio, month=mes, day=dia).isoformat()
    return None  # 'unica' no se repite


def listar_ciclos_compra(empresa_id, estado=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT c.*, u.nombre_completo AS creado_por_nombre
        FROM ciclos_compra c JOIN users u ON u.id = c.creado_por_id
        WHERE c.empresa_id = %s
    """
    params = [empresa_id]
    if estado:
        query += " AND c.estado = %s"; params.append(estado)
    query += " ORDER BY c.fecha_programada DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_pedidos_compra_todos(empresa_id):
    """Todos los pedidos de todos los ciclos de la empresa, con su info completa —
    para el reporte de Compras (uno por línea de pedido)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.cantidad, p.departamento, p.notas, p.creado_en,
               c.nombre AS ciclo_nombre, c.estado AS ciclo_estado, c.fecha_programada,
               a.nombre AS articulo_nombre, a.proveedor, a.marca,
               u.nombre_completo AS usuario_nombre
        FROM pedidos_compra p
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        JOIN articulos_compra a ON a.id = p.articulo_id
        JOIN users u ON u.id = p.usuario_id
        WHERE c.empresa_id = %s
        ORDER BY c.fecha_programada DESC, p.creado_en ASC
    """, (empresa_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_ciclo_compra(empresa_id, ciclo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.nombre_completo AS creado_por_nombre
        FROM ciclos_compra c JOIN users u ON u.id = c.creado_por_id
        WHERE c.id = %s AND c.empresa_id = %s
    """, (ciclo_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    ciclo = dict(row)
    cur.execute("""
        SELECT p.*, a.nombre AS articulo_nombre, a.proveedor, a.marca, a.foto_base64,
               u.nombre_completo AS usuario_nombre, u.telefono_whatsapp AS usuario_telefono
        FROM pedidos_compra p
        JOIN articulos_compra a ON a.id = p.articulo_id
        JOIN users u ON u.id = p.usuario_id
        WHERE p.ciclo_id = %s ORDER BY p.creado_en ASC
    """, (ciclo_id,))
    ciclo["pedidos"] = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return ciclo


def crear_ciclo_compra(empresa_id, nombre, frecuencia, fecha_programada, creado_por_id):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO ciclos_compra (empresa_id, nombre, frecuencia, fecha_programada, estado, creado_por_id, creado_en)
           VALUES (%s, %s, %s, %s, 'pendiente', %s, %s) RETURNING id""",
        (empresa_id, nombre, frecuencia, fecha_programada, creado_por_id, now),
    )
    ciclo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return ciclo_id


def abrir_ciclo_compra(empresa_id, ciclo_id):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("UPDATE ciclos_compra SET estado = 'abierto', abierto_en = %s WHERE id = %s AND empresa_id = %s",
                (now, ciclo_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def cerrar_ciclo_compra(empresa_id, ciclo_id):
    """Cierra el ciclo (marca como surtido) y, si es recurrente, programa el siguiente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ciclos_compra WHERE id = %s AND empresa_id = %s", (ciclo_id, empresa_id))
    ciclo = cur.fetchone()
    if not ciclo:
        cur.close(); conn.close()
        return None
    ciclo = dict(ciclo)
    now = ahora().isoformat(timespec="seconds")
    cur.execute("UPDATE ciclos_compra SET estado = 'cerrado', cerrado_en = %s WHERE id = %s",
                (now, ciclo_id))
    conn.commit()
    cur.close(); conn.close()

    siguiente_id = None
    siguiente_fecha = _siguiente_fecha_compra(ciclo["fecha_programada"], ciclo["frecuencia"])
    if siguiente_fecha:
        siguiente_id = crear_ciclo_compra(empresa_id, ciclo["nombre"], ciclo["frecuencia"], siguiente_fecha, ciclo["creado_por_id"])
    return {"cerrado_id": ciclo_id, "siguiente_id": siguiente_id}


def agregar_pedido_compra(ciclo_id, articulo_id, usuario_id, cantidad, departamento, notas=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO pedidos_compra (ciclo_id, articulo_id, usuario_id, cantidad, departamento, notas, creado_en) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (ciclo_id, articulo_id, usuario_id, cantidad, departamento, notas, now),
    )
    conn.commit()
    cur.close(); conn.close()


def eliminar_pedido_compra(pedido_id, usuario_id, es_staff):
    """Un empleado solo puede borrar su propio pedido; staff puede borrar cualquiera."""
    conn = get_connection()
    cur = conn.cursor()
    if es_staff:
        cur.execute("DELETE FROM pedidos_compra WHERE id = %s", (pedido_id,))
    else:
        cur.execute("DELETE FROM pedidos_compra WHERE id = %s AND usuario_id = %s", (pedido_id, usuario_id))
    conn.commit()
    cur.close(); conn.close()


def obtener_pedido_compra(empresa_id, pedido_id):
    """Un pedido individual, con los datos necesarios para poder avisarle a quien lo pidió."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, a.nombre AS articulo_nombre, c.empresa_id,
               u.nombre_completo AS usuario_nombre, u.telefono_whatsapp AS usuario_telefono
        FROM pedidos_compra p
        JOIN articulos_compra a ON a.id = p.articulo_id
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        JOIN users u ON u.id = p.usuario_id
        WHERE p.id = %s AND c.empresa_id = %s
    """, (pedido_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def marcar_pedido_listo(pedido_id):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("UPDATE pedidos_compra SET listo = TRUE, listo_en = %s WHERE id = %s", (now, pedido_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Sucursales de reparación (definen el prefijo de folio, ej. SPD, PPD, DSG, CPM) ----

def listar_sucursales_reparacion(empresa_id, solo_activas=True):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM sucursales_reparacion WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activas:
        query += " AND activo = TRUE"
    query += " ORDER BY nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_sucursal_reparacion(empresa_id, sucursal_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sucursales_reparacion WHERE id = %s AND empresa_id = %s", (sucursal_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def crear_sucursal_reparacion(empresa_id, nombre, prefijo, departamento=None, telefonos=None, notas=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sucursales_reparacion (empresa_id, nombre, prefijo, departamento, telefonos, notas) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (empresa_id, nombre, prefijo.upper(), departamento, telefonos, notas),
    )
    sucursal_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return sucursal_id


def cambiar_estado_sucursal_reparacion(empresa_id, sucursal_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sucursales_reparacion SET activo = %s WHERE id = %s AND empresa_id = %s",
                (activo, sucursal_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def actualizar_sucursal_reparacion(empresa_id, sucursal_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = ["nombre", "prefijo", "departamento", "activo", "telefonos", "notas"]
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [sucursal_id, empresa_id]
        cur.execute(f"UPDATE sucursales_reparacion SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()
    return obtener_sucursal_reparacion(empresa_id, sucursal_id)


# ---- Reparaciones ----

def _next_folio_reparacion(cur, empresa_id, sucursal):
    cur.execute("SELECT COUNT(*) AS n FROM reparaciones WHERE empresa_id = %s AND sucursal_id = %s",
                (empresa_id, sucursal["id"]))
    n = cur.fetchone()["n"] + 1
    return f"{sucursal['prefijo']}{n}"


def _reparacion_query_base():
    return """
        SELECT r.*, t.estado AS ticket_estado, t.prioridad AS ticket_prioridad,
               t.asignado_a_id, ua.nombre_completo AS tecnico_nombre,
               uc.nombre_completo AS creado_por_nombre,
               s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,
               ur.nombre_completo AS responsable_diagnostico_nombre, ur.puesto AS responsable_diagnostico_puesto
        FROM reparaciones r
        LEFT JOIN tickets t ON t.id = r.ticket_id
        LEFT JOIN users ua ON ua.id = t.asignado_a_id
        LEFT JOIN sucursales_reparacion s ON s.id = r.sucursal_id
        LEFT JOIN users ur ON ur.id = r.responsable_diagnostico_id
        JOIN users uc ON uc.id = r.creado_por_id
    """


def _enriquecer_reparacion(cur, rep):
    cur.execute("SELECT * FROM reparacion_items_costo WHERE reparacion_id = %s ORDER BY id", (rep["id"],))
    items = [dict(r) for r in cur.fetchall()]
    rep["items_costo"] = items
    rep["costo_refacciones_servicio"] = sum(i["cantidad"] * i["costo"] for i in items)
    rep["costo_total"] = round(rep["costo_refacciones_servicio"] + (rep.get("costo_paqueteria") or 0), 2)

    if rep.get("fecha_recepcion") and rep["estado"] not in ("entregado", "cancelado"):
        dias = (ahora() - datetime.fromisoformat(rep["fecha_recepcion"])).days
        rep["dias_transcurridos"] = dias
    else:
        rep["dias_transcurridos"] = None

    rep["alerta_reparacion_interna"] = (
        rep["estado"] in ("en_reparacion", "control_calidad")
        and rep.get("fecha_autorizacion") is not None
        and (ahora() - datetime.fromisoformat(rep["fecha_autorizacion"])).days > 7
    )
    rep["alerta_proveedor"] = (
        rep["estado"] == "con_proveedor"
        and rep.get("fecha_envio_proveedor") is not None
        and (ahora() - datetime.fromisoformat(rep["fecha_envio_proveedor"])).days > 20
    )
    return rep


def listar_reparaciones(empresa_id, estado=None, sucursal_id=None, creado_por_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = _reparacion_query_base() + " WHERE r.empresa_id = %s"
    params = [empresa_id]
    if estado:
        query += " AND r.estado = %s"; params.append(estado)
    if sucursal_id:
        query += " AND r.sucursal_id = %s"; params.append(sucursal_id)
    if creado_por_id:
        query += " AND r.creado_por_id = %s"; params.append(creado_por_id)
    query += " ORDER BY r.creado_en DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        _enriquecer_reparacion(cur, r)
    cur.close(); conn.close()
    return rows


def obtener_reparacion(empresa_id, reparacion_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(_reparacion_query_base() + " WHERE r.id = %s AND r.empresa_id = %s", (reparacion_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    rep = dict(row)
    _enriquecer_reparacion(cur, rep)

    cur.execute("""
        SELECT e.*, u.nombre_completo AS subido_por_nombre
        FROM reparacion_evidencias e JOIN users u ON u.id = e.subido_por_id
        WHERE e.reparacion_id = %s ORDER BY e.creado_en ASC
    """, (reparacion_id,))
    rep["evidencias"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT a.*, u.nombre_completo AS autor_nombre
        FROM reparacion_actualizaciones a JOIN users u ON u.id = a.autor_id
        WHERE a.reparacion_id = %s ORDER BY a.creado_en ASC
    """, (reparacion_id,))
    rep["actualizaciones"] = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()
    return rep


def crear_reparacion(empresa_id, sucursal_id, cliente_nombre, cliente_telefono, asesor_recibe,
                      equipo, marca, modelo, numero_serie, fecha_folio_adquisicion, garantia,
                      falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
                      departamento, categoria, prioridad, creado_por_id, foto_estado_base64=None,
                      foto_estado_nombre=None):
    """Crea la Orden de Servicio (reparación) Y su ticket vinculado en el tablero principal."""
    sucursal = obtener_sucursal_reparacion(empresa_id, sucursal_id)
    if not sucursal:
        return None

    descripcion_ticket = f"[Reparación {sucursal['prefijo']}] {equipo or 'Equipo'} — {cliente_nombre}. Falla: {falla_reportada or 'sin especificar'}"
    ticket = crear_ticket(empresa_id, departamento, descripcion_ticket, categoria, prioridad, creado_por_id)

    conn = get_connection()
    cur = conn.cursor()
    folio = _next_folio_reparacion(cur, empresa_id, sucursal)
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO reparaciones
           (empresa_id, folio, sucursal_id, cliente_nombre, cliente_telefono, asesor_recibe,
            equipo, marca, modelo, numero_serie, fecha_folio_adquisicion, garantia,
            falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
            estado, fecha_recepcion, ticket_id, creado_por_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   'en_diagnostico', %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, folio, sucursal_id, cliente_nombre, cliente_telefono, asesor_recibe,
         equipo, marca, modelo, numero_serie, fecha_folio_adquisicion, garantia,
         falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
         now, ticket["id"], creado_por_id, now, now),
    )
    reparacion_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()

    if foto_estado_base64:
        agregar_evidencia_reparacion(reparacion_id, "ingreso", foto_estado_base64, foto_estado_nombre, creado_por_id)

    return obtener_reparacion(empresa_id, reparacion_id)


_CAMPOS_EDITABLES_REPARACION = [
    "folio_microsip", "cliente_nombre", "cliente_telefono", "asesor_recibe", "equipo", "marca", "modelo",
    "numero_serie", "fecha_folio_adquisicion", "garantia", "falla_reportada", "estado_fisico",
    "accesorios_entregados", "diagnostico", "autorizacion_precio", "autorizacion_medio", "fecha_autorizacion",
    "folio_solicitud_traspaso", "costo_paqueteria", "conclusion", "recomendaciones",
    "responsable_diagnostico_id", "fecha_envio_proveedor", "fecha_entrega", "observaciones_entrega",
    "firma_entrega",
]


def actualizar_reparacion(empresa_id, reparacion_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in _CAMPOS_EDITABLES_REPARACION:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        campos.append("actualizado_en = %s"); valores.append(ahora().isoformat(timespec="seconds"))
        valores += [reparacion_id, empresa_id]
        cur.execute(f"UPDATE reparaciones SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def cambiar_estado_reparacion(empresa_id, reparacion_id, estado):
    """Cambia el estado de la reparación y, si corresponde, sincroniza el ticket vinculado."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    campos = ["estado = %s", "actualizado_en = %s"]
    valores = [estado, now]
    if estado == "con_proveedor":
        campos.append("fecha_envio_proveedor = %s"); valores.append(now)
    if estado == "entregado":
        campos.append("fecha_entrega = %s"); valores.append(now)
    valores += [reparacion_id, empresa_id]
    cur.execute(f"UPDATE reparaciones SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
    cur.execute("SELECT ticket_id FROM reparaciones WHERE id = %s", (reparacion_id,))
    fila = cur.fetchone()
    conn.commit()
    cur.close(); conn.close()

    if fila and fila["ticket_id"]:
        mapa_ticket = {
            "en_diagnostico": "abierto", "esperando_autorizacion": "abierto",
            "en_reparacion": "en_progreso", "con_proveedor": "en_progreso", "esperando_refaccion": "en_progreso",
            "control_calidad": "en_progreso", "envio_sucursal": "en_progreso", "listo_entrega": "resuelto",
            "entregado": "cerrado", "cancelado": "cerrado",
        }
        if estado in mapa_ticket:
            actualizar_ticket(fila["ticket_id"], estado=mapa_ticket[estado])


def agregar_item_costo(reparacion_id, articulo, cantidad, codigo, costo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reparacion_items_costo (reparacion_id, articulo, cantidad, codigo, costo) VALUES (%s, %s, %s, %s, %s)",
        (reparacion_id, articulo, cantidad, codigo, costo),
    )
    conn.commit()
    cur.close(); conn.close()


def eliminar_item_costo(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reparacion_items_costo WHERE id = %s", (item_id,))
    conn.commit()
    cur.close(); conn.close()


def agregar_evidencia_reparacion(reparacion_id, etapa, archivo_base64, archivo_nombre, subido_por_id):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO reparacion_evidencias (reparacion_id, etapa, archivo_base64, archivo_nombre, subido_por_id, creado_en) VALUES (%s, %s, %s, %s, %s, %s)",
        (reparacion_id, etapa, archivo_base64, archivo_nombre, subido_por_id, now),
    )
    conn.commit()
    cur.close(); conn.close()


def agregar_actualizacion_reparacion(reparacion_id, autor_id, texto):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO reparacion_actualizaciones (reparacion_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (reparacion_id, autor_id, texto, now),
    )
    cur.execute("UPDATE reparaciones SET actualizado_en = %s WHERE id = %s", (now, reparacion_id))
    conn.commit()
    cur.close(); conn.close()



# ---- Borrado masivo (Administrar → Borrar datos) ----

def contar_registros_borrado_masivo(empresa_id, tabla_key, fecha_desde, fecha_hasta):
    info = TABLAS_BORRADO_MASIVO[tabla_key]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT COUNT(*) AS n FROM {info['tabla']} WHERE empresa_id = %s AND {info['campo_fecha']} >= %s AND {info['campo_fecha']} <= %s",
        (empresa_id, f"{fecha_desde}T00:00:00", f"{fecha_hasta}T23:59:59"),
    )
    n = cur.fetchone()["n"]
    cur.close(); conn.close()
    return n


def borrar_masivo(empresa_id, tabla_key, fecha_desde, fecha_hasta):
    """Borra por lote los registros de una tabla dentro de un rango de fechas.
    Antes de borrar tickets, desvincula (no borra) las reparaciones/mantenimientos
    que apuntaban a ellos, para no dejar nada roto. Al borrar reparaciones o
    mantenimientos, sí borra su ticket vinculado (se creó solo para eso)."""
    info = TABLAS_BORRADO_MASIVO[tabla_key]
    desde, hasta = f"{fecha_desde}T00:00:00", f"{fecha_hasta}T23:59:59"

    conn = get_connection()
    cur = conn.cursor()

    eliminados = None

    if tabla_key == "tickets":
        cur.execute(
            """UPDATE reparaciones SET ticket_id = NULL WHERE empresa_id = %s AND ticket_id IN
               (SELECT id FROM tickets WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s)""",
            (empresa_id, empresa_id, desde, hasta),
        )
        cur.execute(
            """UPDATE mantenimientos SET ticket_id = NULL WHERE empresa_id = %s AND ticket_id IN
               (SELECT id FROM tickets WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s)""",
            (empresa_id, empresa_id, desde, hasta),
        )
        cur.execute("DELETE FROM tickets WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s", (empresa_id, desde, hasta))
        eliminados = cur.rowcount
    elif tabla_key == "reparaciones":
        # Hay que capturar los ticket_id ANTES de borrar las reparaciones (si no, ya no
        # se podrían consultar), y borrar esos tickets DESPUÉS de borrar las reparaciones
        # que los referencian — si no, la base rechaza el borrado por integridad referencial.
        cur.execute(
            "SELECT ticket_id FROM reparaciones WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s AND ticket_id IS NOT NULL",
            (empresa_id, desde, hasta),
        )
        ticket_ids = [r["ticket_id"] for r in cur.fetchall()]
        cur.execute("DELETE FROM reparaciones WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s", (empresa_id, desde, hasta))
        eliminados = cur.rowcount  # se guarda ANTES de borrar los tickets, para reportar reparaciones, no tickets
        if ticket_ids:
            marcador = ",".join(["%s"] * len(ticket_ids))
            cur.execute(f"DELETE FROM tickets WHERE empresa_id = %s AND id IN ({marcador})", [empresa_id] + ticket_ids)
    elif tabla_key == "mantenimientos":
        cur.execute(
            "SELECT ticket_id FROM mantenimientos WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s AND ticket_id IS NOT NULL",
            (empresa_id, desde, hasta),
        )
        ticket_ids = [r["ticket_id"] for r in cur.fetchall()]
        cur.execute("DELETE FROM mantenimientos WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s", (empresa_id, desde, hasta))
        eliminados = cur.rowcount
        if ticket_ids:
            marcador = ",".join(["%s"] * len(ticket_ids))
            cur.execute(f"DELETE FROM tickets WHERE empresa_id = %s AND id IN ({marcador})", [empresa_id] + ticket_ids)
    else:
        cur.execute(
            f"DELETE FROM {info['tabla']} WHERE empresa_id = %s AND {info['campo_fecha']} >= %s AND {info['campo_fecha']} <= %s",
            (empresa_id, desde, hasta),
        )
        eliminados = cur.rowcount

    conn.commit()
    cur.close(); conn.close()
    return eliminados


# ---- Eliminar un ticket o una reparación individual (por error al crearlos) ----

def eliminar_ticket(empresa_id, ticket_id):
    conn = get_connection()
    cur = conn.cursor()
    # Antes de borrar, desvincular (no borrar) cualquier reparación/mantenimiento
    # que lo tuviera como su ticket vinculado.
    cur.execute("UPDATE reparaciones SET ticket_id = NULL WHERE empresa_id = %s AND ticket_id = %s", (empresa_id, ticket_id))
    cur.execute("UPDATE mantenimientos SET ticket_id = NULL WHERE empresa_id = %s AND ticket_id = %s", (empresa_id, ticket_id))
    cur.execute("DELETE FROM tickets WHERE id = %s AND empresa_id = %s", (ticket_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado


def eliminar_reparacion(empresa_id, reparacion_id):
    """Borra la reparación y, si tenía uno, también su ticket vinculado (se creó solo para eso)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticket_id FROM reparaciones WHERE id = %s AND empresa_id = %s", (reparacion_id, empresa_id))
    fila = cur.fetchone()
    if not fila:
        cur.close(); conn.close()
        return False
    ticket_id = fila["ticket_id"]
    cur.execute("DELETE FROM reparaciones WHERE id = %s AND empresa_id = %s", (reparacion_id, empresa_id))
    if ticket_id:
        cur.execute("DELETE FROM tickets WHERE id = %s AND empresa_id = %s", (ticket_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    return True
