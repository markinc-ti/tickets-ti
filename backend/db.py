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
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras

import auth
import geo

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
ROLES = ["superadmin", "admin", "tecnico", "usuario", "instalador"]

# Registro de "términos editables" — cada empresa puede sobreescribir el
# valor por default (ej. cambiar "Encargado de Sucursal" por "Encargado de
# Nave"). La CLAVE nunca cambia (así el resto del código y la base de datos
# no se rompen); solo cambia el TEXTO que se le muestra al usuario.
TERMINOS_EDITABLES = {
    # Nombres de roles
    "rol.admin": {"grupo": "Roles", "default": "Administrador"},
    "rol.tecnico": {"grupo": "Roles", "default": "Técnico"},
    "rol.usuario": {"grupo": "Roles", "default": "Empleado"},
    "rol.master": {"grupo": "Roles", "default": "Usuario Master"},
    "rol.almacen": {"grupo": "Roles", "default": "Encargado de Almacén"},
    "rol.encargado_sucursal": {"grupo": "Roles", "default": "Encargado de Sucursal"},
    "rol.instalador": {"grupo": "Roles", "default": "Instalador"},
    # Nombres de módulos (menú principal)
    "modulo.tickets": {"grupo": "Módulos", "default": "Tickets"},
    "modulo.reparaciones": {"grupo": "Módulos", "default": "Reparaciones"},
    "modulo.entregas": {"grupo": "Módulos", "default": "Entregas"},
    "modulo.checador_precio": {"grupo": "Módulos", "default": "Checador de precio"},
    "modulo.equipos": {"grupo": "Módulos", "default": "Equipos"},
    "modulo.proyectos": {"grupo": "Módulos", "default": "Proyectos"},
    "modulo.compras": {"grupo": "Módulos", "default": "Compras"},
    "modulo.rh": {"grupo": "Módulos", "default": "Recursos Humanos"},
    # Campos comunes
    "campo.sucursal": {"grupo": "Campos", "default": "Sucursal"},
}


def obtener_terminos(empresa_id):
    """Regresa {clave: valor} solo con las claves que la empresa SÍ
    personalizó — el frontend combina esto con los valores por default."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT clave, valor FROM terminos_personalizados WHERE empresa_id = %s", (empresa_id,))
    terminos = {r["clave"]: r["valor"] for r in cur.fetchall()}
    cur.close(); conn.close()
    return terminos


def guardar_termino(empresa_id, clave, valor):
    if clave not in TERMINOS_EDITABLES:
        raise ValueError(f"'{clave}' no es un término editable reconocido")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO terminos_personalizados (empresa_id, clave, valor) VALUES (%s, %s, %s)
           ON CONFLICT (empresa_id, clave) DO UPDATE SET valor = EXCLUDED.valor""",
        (empresa_id, clave, valor),
    )
    conn.commit()
    cur.close(); conn.close()


def restaurar_termino(empresa_id, clave):
    """Borra la personalización — vuelve a usar el valor por default."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM terminos_personalizados WHERE empresa_id = %s AND clave = %s", (empresa_id, clave))
    conn.commit()
    cur.close(); conn.close()

TIPOS_EQUIPO = [
    "computadora", "laptop", "monitor", "impresora", "escaner", "servidor",
    "mouse", "mouse_inalambrico", "teclado", "teclado_inalambrico",
    "router", "switch", "modem", "punto_acceso",
    "dvr", "camara_seguridad", "no_break", "regulador",
    "telefono", "telefono_ip", "proyector", "bocinas", "microfono",
    "tablet", "lector_codigo_barras", "disco_duro_externo",
    "red", "otro",
]
ESTADOS_EQUIPO = ["nuevo", "buen_estado", "sugerencia_cambio", "en_proceso_cambio", "cambio_urgente", "baja"]
TIPOS_MANTENIMIENTO = ["preventivo", "correctivo"]
FRECUENCIAS_MANTENIMIENTO = ["unica", "mensual", "trimestral", "semestral", "anual"]
ESTADOS_PROYECTO = ["planificacion", "en_progreso", "pausado", "completado", "cancelado"]
ESTADOS_TAREA_PROYECTO = ["pendiente", "en_progreso", "completada"]
FRECUENCIAS_COMPRA = ["unica", "semanal", "quincenal", "mensual"]
ESTADOS_CICLO_COMPRA = ["pendiente", "abierto", "esperando_autorizacion", "cerrado"]

TIPOS_INCIDENCIA_RH = ["dia_libre_sin_goce", "enfermedad", "lesion", "embarazo", "accidente", "otro"]
ESTADOS_INCIDENCIA_RH = ["propuesta_empleado", "pendiente_encargado", "pendiente", "aprobada", "rechazada", "pagada"]
TIPOS_MOVIMIENTO_HORAS_RH = ["debe", "pago"]
ESTADOS_REPARACION = [
    "nueva", "en_diagnostico", "esperando_autorizacion", "en_reparacion", "con_proveedor",
    "esperando_refaccion", "control_calidad", "envio_sucursal", "en_traslado", "listo_entrega", "entregado", "cancelado",
]

TABLAS_BORRADO_MASIVO = {
    "tickets": {"tabla": "tickets", "campo_fecha": "creado_en", "etiqueta": "Tickets"},
    "reparaciones": {"tabla": "reparaciones", "campo_fecha": "creado_en", "etiqueta": "Reparaciones"},
    "proyectos": {"tabla": "proyectos", "campo_fecha": "creado_en", "etiqueta": "Proyectos"},
    "mantenimientos": {"tabla": "mantenimientos", "campo_fecha": "creado_en", "etiqueta": "Mantenimientos"},
    "ciclos_compra": {"tabla": "ciclos_compra", "campo_fecha": "creado_en", "etiqueta": "Ciclos de compra"},
    "articulos_compra": {"tabla": "articulos_compra", "campo_fecha": "creado_en", "etiqueta": "Catálogo de compras"},
    "incidencias_rh": {"tabla": "incidencias_rh", "campo_fecha": "creado_en", "etiqueta": "Incidencias de RH"},
    "horas_rh_movimientos": {"tabla": "horas_rh_movimientos", "campo_fecha": "creado_en", "etiqueta": "Movimientos de horas (RH)"},
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
            articulo_id INTEGER REFERENCES articulos_compra(id),
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
        ALTER TABLE articulos_compra ADD COLUMN IF NOT EXISTS categoria TEXT;
        ALTER TABLE ciclos_compra ADD COLUMN IF NOT EXISTS categoria TEXT;
        ALTER TABLE pedidos_compra ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE pedidos_compra ADD COLUMN IF NOT EXISTS articulo_libre TEXT;
        ALTER TABLE pedidos_compra ALTER COLUMN articulo_id DROP NOT NULL;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_compras BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE articulos_compra ADD COLUMN IF NOT EXISTS precio_unitario REAL;
        ALTER TABLE articulos_compra ADD COLUMN IF NOT EXISTS stock_actual INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE articulos_compra ADD COLUMN IF NOT EXISTS stock_minimo INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE ciclos_compra ADD COLUMN IF NOT EXISTS autorizado BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE ciclos_compra ADD COLUMN IF NOT EXISTS autorizado_por_id INTEGER REFERENCES users(id);
        ALTER TABLE ciclos_compra ADD COLUMN IF NOT EXISTS autorizado_en TEXT;
        ALTER TABLE ciclos_compra ADD COLUMN IF NOT EXISTS firma_autorizacion TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_rh BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_tickets BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_reparaciones BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS calendario_token TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_dashboard BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS numero_empleado TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_entregas BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_checador_precio BOOLEAN NOT NULL DEFAULT TRUE;

        CREATE TABLE IF NOT EXISTS vehiculos_entrega (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE(empresa_id, nombre)
        );

        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS horario TEXT;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS vehiculo_id INTEGER REFERENCES vehiculos_entrega(id);
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS liga_mapa TEXT;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS comentarios TEXT;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS estatus_pago TEXT;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS confirmado BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS destino_lat DOUBLE PRECISION;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS destino_lng DOUBLE PRECISION;

        CREATE TABLE IF NOT EXISTS entrega_configuracion (
            empresa_id INTEGER PRIMARY KEY REFERENCES empresas(id),
            cedis_direccion TEXT,
            cedis_lat DOUBLE PRECISION,
            cedis_lng DOUBLE PRECISION
        );

        CREATE TABLE IF NOT EXISTS terminos_personalizados (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            clave TEXT NOT NULL,
            valor TEXT NOT NULL,
            UNIQUE(empresa_id, clave)
        );

        CREATE TABLE IF NOT EXISTS entregas (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            folio TEXT NOT NULL,
            folio_pedido_microsip TEXT,
            cliente_nombre TEXT NOT NULL,
            cliente_direccion TEXT,
            cliente_telefono TEXT,
            equipo_descripcion TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            fecha_programada TEXT,
            motivo_rechazo TEXT,
            motivo_reagenda TEXT,
            receptor_nombre TEXT,
            receptor_puesto TEXT,
            firma_base64 TEXT,
            firmado_en TEXT,
            latitud TEXT,
            longitud TEXT,
            creado_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL,
            UNIQUE(empresa_id, folio)
        );

        CREATE TABLE IF NOT EXISTS entrega_checklist_items (
            id SERIAL PRIMARY KEY,
            entrega_id INTEGER NOT NULL REFERENCES entregas(id) ON DELETE CASCADE,
            texto TEXT NOT NULL,
            orden INTEGER NOT NULL DEFAULT 0,
            obligatorio BOOLEAN NOT NULL DEFAULT TRUE,
            completado BOOLEAN NOT NULL DEFAULT FALSE,
            completado_por_id INTEGER REFERENCES users(id),
            completado_en TEXT,
            agregado_en_sitio BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS entrega_instaladores (
            id SERIAL PRIMARY KEY,
            entrega_id INTEGER NOT NULL REFERENCES entregas(id) ON DELETE CASCADE,
            instalador_id INTEGER NOT NULL REFERENCES users(id),
            asignado_en TEXT NOT NULL,
            UNIQUE(entrega_id, instalador_id)
        );

        CREATE TABLE IF NOT EXISTS entrega_historial (
            id SERIAL PRIMARY KEY,
            entrega_id INTEGER NOT NULL REFERENCES entregas(id) ON DELETE CASCADE,
            estatus_anterior TEXT,
            estatus_nuevo TEXT NOT NULL,
            comentario TEXT,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entrega_actualizaciones (
            id SERIAL PRIMARY KEY,
            entrega_id INTEGER NOT NULL REFERENCES entregas(id) ON DELETE CASCADE,
            autor_id INTEGER NOT NULL REFERENCES users(id),
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entrega_checklist_plantilla (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            texto TEXT NOT NULL,
            automatico BOOLEAN NOT NULL DEFAULT FALSE,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            orden INTEGER NOT NULL DEFAULT 0,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incidencias_rh (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            tipo TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT,
            motivo TEXT,
            foto_base64 TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            respuesta_admin TEXT,
            resuelto_por_id INTEGER REFERENCES users(id),
            resuelto_en TEXT,
            creado_en TEXT NOT NULL
        );

        ALTER TABLE incidencias_rh ADD COLUMN IF NOT EXISTS horas REAL;
        ALTER TABLE incidencias_rh ADD COLUMN IF NOT EXISTS firma_encargado_base64 TEXT;
        ALTER TABLE incidencias_rh ADD COLUMN IF NOT EXISTS firma_encargado_en TEXT;
        ALTER TABLE incidencias_rh ADD COLUMN IF NOT EXISTS firma_encargado_por_id INTEGER REFERENCES users(id);

        CREATE TABLE IF NOT EXISTS horas_rh_movimientos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            incidencia_id INTEGER REFERENCES incidencias_rh(id),
            tipo TEXT NOT NULL,
            horas REAL NOT NULL,
            notas TEXT,
            registrado_por_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL
        );
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS estado TEXT NOT NULL DEFAULT 'aprobado';
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS fecha TEXT;
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS firma_aprobacion_base64 TEXT;
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS aprobado_por_id INTEGER REFERENCES users(id);
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS aprobado_en TEXT;
        ALTER TABLE horas_rh_movimientos ADD COLUMN IF NOT EXISTS motivo_rechazo TEXT;

        CREATE TABLE IF NOT EXISTS cursos_rh (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            descripcion TEXT,
            puesto_objetivo TEXT,
            creado_por_id INTEGER NOT NULL REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        );
        ALTER TABLE cursos_rh ADD COLUMN IF NOT EXISTS dias_duracion INTEGER;
        ALTER TABLE cursos_rh ADD COLUMN IF NOT EXISTS fecha_limite TEXT;

        CREATE TABLE IF NOT EXISTS curso_bitacora (
            id SERIAL PRIMARY KEY,
            curso_id INTEGER NOT NULL REFERENCES cursos_rh(id) ON DELETE CASCADE,
            autor_id INTEGER REFERENCES users(id),
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS curso_participantes (
            id SERIAL PRIMARY KEY,
            curso_id INTEGER NOT NULL REFERENCES cursos_rh(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            agregado_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            agregado_en TEXT NOT NULL,
            UNIQUE(curso_id, usuario_id)
        );

        CREATE TABLE IF NOT EXISTS curso_firmas (
            id SERIAL PRIMARY KEY,
            curso_id INTEGER NOT NULL REFERENCES cursos_rh(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            firma_base64 TEXT NOT NULL,
            completado_en TEXT NOT NULL,
            UNIQUE(curso_id, usuario_id)
        );
        ALTER TABLE curso_firmas ADD COLUMN IF NOT EXISTS evidencia_base64 TEXT;
        ALTER TABLE curso_firmas ADD COLUMN IF NOT EXISTS evidencia_nombre TEXT;

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
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_salida TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_salida_por_id INTEGER REFERENCES users(id);
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_salida_en TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_ingreso_sucursal TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_ingreso_por_id INTEGER REFERENCES users(id);
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_ingreso_en TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS fecha_adquisicion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS folio_adquisicion TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS chofer_nombre TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_chofer TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_chofer_por_id INTEGER REFERENCES users(id);
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS firma_chofer_en TEXT;
        ALTER TABLE reparaciones ADD COLUMN IF NOT EXISTS diagnostico_bloqueado BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS politicas_texto TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS tema TEXT NOT NULL DEFAULT 'oscuro';
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS color_acento TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS fondo_color TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS fondo_base64 TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_host TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_puerto INTEGER DEFAULT 3050;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_ruta_db TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_usuario TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_password TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS departamento TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS sucursal_id INTEGER REFERENCES sucursales_reparacion(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES users(id);
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS usuario_microsip TEXT;
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS password_microsip TEXT;
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS firma_responsiva_base64 TEXT;
        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS firma_responsiva_en TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS telefonos TEXT;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS notas TEXT;

        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS numero_serie TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS marca TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS modelo TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS anio INTEGER;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS placa TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS kilometraje INTEGER;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS notas TEXT;

        CREATE TABLE IF NOT EXISTS mantenimientos_vehiculo (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            vehiculo_id INTEGER NOT NULL REFERENCES vehiculos_entrega(id) ON DELETE CASCADE,
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
            responsable_id INTEGER REFERENCES users(id),
            creado_por_id INTEGER REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS proyecto_tarea_usuarios (
            tarea_id INTEGER NOT NULL REFERENCES proyecto_tareas(id) ON DELETE CASCADE,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            PRIMARY KEY (tarea_id, usuario_id)
        );

        ALTER TABLE proyecto_tareas ALTER COLUMN usuario_id DROP NOT NULL;

        -- Datos fiscales/documentales del vehículo (seguro, factura, tarjeta
        -- de circulación, verificación) — tomados del formato que ya llevaba
        -- la empresa en Excel para su flotilla.
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS razon_social TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS combustible TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS numero_factura TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS aseguradora TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS numero_poliza TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS vigencia_poliza TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS numero_tarjeta_circulacion TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS aplica_verificacion BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS periodo_verificacion_1 TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS periodo_verificacion_2 TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS chofer_habitual_id INTEGER REFERENCES users(id);

        -- Datos del chofer (persona) — se guardan en el propio usuario, para
        -- reutilizar el sistema de usuarios que ya existe (un instalador YA
        -- es un usuario) en vez de duplicar personas en otra tabla.
        ALTER TABLE users ADD COLUMN IF NOT EXISTS rfc TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS curp TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS numero_licencia TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS tipo_licencia TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS vigencia_licencia TEXT;

        -- Kilometraje específico de cada servicio realizado, y a qué
        -- kilometraje toca el siguiente — para dar seguimiento real
        -- (ej. "cambio de aceite cada 10,000 km"), no solo por fecha.
        ALTER TABLE mantenimientos_vehiculo ADD COLUMN IF NOT EXISTS kilometraje_en_servicio INTEGER;
        ALTER TABLE mantenimientos_vehiculo ADD COLUMN IF NOT EXISTS kilometraje_proximo_servicio INTEGER;

        -- Rastreo GPS en vivo (Geotab / A&T): credenciales por empresa,
        -- qué dispositivo Geotab corresponde a cada vehículo, y la liga
        -- pública de seguimiento por entrega (como las apps de comida).
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS geotab_database TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS geotab_usuario TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS geotab_password TEXT;
        ALTER TABLE vehiculos_entrega ADD COLUMN IF NOT EXISTS geotab_device_id TEXT;
        ALTER TABLE entregas ADD COLUMN IF NOT EXISTS token_seguimiento TEXT UNIQUE;

        -- Geocodificación (dirección de texto -> lat/lng) con LocationIQ:
        -- llave propia por empresa, para no depender del Nominatim público
        -- compartido (que en Render se bloquea seguido por IP compartida).
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS locationiq_api_key TEXT;
    """)
    conn.commit()

    # Migración no destructiva: las tareas de proyecto que ya existían solo
    # tenían UN asignado (columna usuario_id) — se copian a la tabla nueva de
    # muchos-a-muchos para no perder esas asignaciones ya hechas. Ya no se
    # vuelve a tocar después de la primera vez (ON CONFLICT DO NOTHING).
    cur.execute("""
        INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id)
        SELECT id, usuario_id FROM proyecto_tareas WHERE usuario_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)
    conn.commit()

    # ---- Módulo de Marketing: campañas, redes sociales, presupuesto y métricas ----
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_marketing BOOLEAN NOT NULL DEFAULT TRUE;

        CREATE TABLE IF NOT EXISTS redes_sociales_marketing (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            plataforma TEXT NOT NULL,
            nombre_cuenta TEXT NOT NULL,
            url TEXT,
            activa BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS campanas_marketing (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            descripcion TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            estado TEXT NOT NULL DEFAULT 'planificacion',
            presupuesto_asignado REAL,
            responsable_id INTEGER REFERENCES users(id),
            creado_por_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campana_redes_marketing (
            id SERIAL PRIMARY KEY,
            campana_id INTEGER NOT NULL REFERENCES campanas_marketing(id) ON DELETE CASCADE,
            red_social_id INTEGER NOT NULL REFERENCES redes_sociales_marketing(id),
            presupuesto_asignado REAL,
            UNIQUE(campana_id, red_social_id)
        );

        CREATE TABLE IF NOT EXISTS gastos_marketing (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            campana_id INTEGER REFERENCES campanas_marketing(id) ON DELETE CASCADE,
            red_social_id INTEGER REFERENCES redes_sociales_marketing(id),
            persona_id INTEGER REFERENCES users(id),
            concepto TEXT NOT NULL,
            monto REAL NOT NULL,
            fecha TEXT NOT NULL,
            creado_por_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metricas_marketing (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            red_social_id INTEGER NOT NULL REFERENCES redes_sociales_marketing(id),
            campana_id INTEGER REFERENCES campanas_marketing(id) ON DELETE CASCADE,
            fecha TEXT NOT NULL,
            nombre_metrica TEXT NOT NULL,
            valor REAL NOT NULL,
            registrado_por_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL
        );
    """)
    conn.commit()

    # Migración no destructiva: los equipos que ya existían usaban los estados
    # viejos (activo/en_reparacion) — se traducen a los nuevos para que no se
    # queden con un valor que ya no aparece en el desplegable. "baja" se
    # conserva igual, ese concepto no cambió.
    cur.execute("""
        UPDATE equipos SET estado = 'buen_estado' WHERE estado = 'activo';
        UPDATE equipos SET estado = 'sugerencia_cambio' WHERE estado = 'en_reparacion';
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


def obtener_config_microsip(empresa_id):
    """Trae TODO, incluida la contraseña — solo para uso interno (conectar de
    verdad a Firebird). Nunca se manda esto tal cual al frontend."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT microsip_host, microsip_puerto, microsip_ruta_db, microsip_usuario, microsip_password
           FROM empresas WHERE id = %s""",
        (empresa_id,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def obtener_config_microsip_publica(empresa_id):
    """Igual que obtener_config_microsip, pero SIN la contraseña — para
    mostrar en la pantalla de Administrar (solo dice si ya hay una guardada)."""
    config = obtener_config_microsip(empresa_id)
    if not config:
        return None
    return {
        "microsip_host": config["microsip_host"],
        "microsip_puerto": config["microsip_puerto"],
        "microsip_ruta_db": config["microsip_ruta_db"],
        "microsip_usuario": config["microsip_usuario"],
        "tiene_password": bool(config["microsip_password"]),
    }


def actualizar_config_microsip(empresa_id, host, puerto, ruta_db, usuario, password=None):
    """password=None -> no la toca (para no borrarla si el admin solo edita el
    host, por ejemplo); password='' explícito si algún día se quiere quitar."""
    conn = get_connection()
    cur = conn.cursor()
    campos = ["microsip_host = %s", "microsip_puerto = %s", "microsip_ruta_db = %s", "microsip_usuario = %s"]
    valores = [host, puerto, ruta_db, usuario]
    if password is not None:
        campos.append("microsip_password = %s"); valores.append(password)
    valores.append(empresa_id)
    cur.execute(f"UPDATE empresas SET {', '.join(campos)} WHERE id = %s", valores)
    conn.commit()
    cur.close(); conn.close()


# ---- Rastreo GPS en vivo (Geotab / A&T) ----

def obtener_config_geotab(empresa_id):
    """Trae TODO, incluida la contraseña — solo para uso interno (conectar de
    verdad a la API de Geotab). Nunca se manda esto tal cual al frontend."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT geotab_database, geotab_usuario, geotab_password FROM empresas WHERE id = %s",
        (empresa_id,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def obtener_config_geotab_publica(empresa_id):
    """Igual que obtener_config_geotab, pero sin la contraseña — para la
    pantalla de Administrar (solo dice si ya hay una guardada)."""
    config = obtener_config_geotab(empresa_id)
    if not config:
        return None
    return {
        "geotab_database": config["geotab_database"],
        "geotab_usuario": config["geotab_usuario"],
        "tiene_password": bool(config["geotab_password"]),
    }


def actualizar_config_geotab(empresa_id, database, usuario, password=None):
    conn = get_connection()
    cur = conn.cursor()
    campos = ["geotab_database = %s", "geotab_usuario = %s"]
    valores = [database, usuario]
    if password is not None:
        campos.append("geotab_password = %s"); valores.append(password)
    valores.append(empresa_id)
    cur.execute(f"UPDATE empresas SET {', '.join(campos)} WHERE id = %s", valores)
    conn.commit()
    cur.close(); conn.close()


# ---- Geocodificación (LocationIQ) ----

def obtener_config_locationiq(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT locationiq_api_key FROM empresas WHERE id = %s", (empresa_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row["locationiq_api_key"] if row else None


def actualizar_config_locationiq(empresa_id, api_key):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE empresas SET locationiq_api_key = %s WHERE id = %s", (api_key, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def generar_token_seguimiento_entrega(empresa_id, entrega_id):
    """Crea (o regresa el que ya existía) un token único e imposible de
    adivinar para la liga pública de seguimiento en vivo de esta entrega —
    quien tenga la liga puede ver dónde va el vehículo, sin necesitar cuenta
    ni contraseña, igual que el link de una app de comida a domicilio."""
    import secrets
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT token_seguimiento FROM entregas WHERE id = %s AND empresa_id = %s", (entrega_id, empresa_id))
    fila = cur.fetchone()
    if not fila:
        cur.close(); conn.close()
        return None
    if fila["token_seguimiento"]:
        cur.close(); conn.close()
        return fila["token_seguimiento"]
    token = secrets.token_urlsafe(24)
    cur.execute("UPDATE entregas SET token_seguimiento = %s WHERE id = %s", (token, entrega_id))
    conn.commit()
    cur.close(); conn.close()
    return token


def obtener_entrega_por_token_seguimiento(token):
    """Para la página pública de seguimiento — solo lo mínimo necesario para
    mostrarle al cliente su entrega y el vehículo asignado, SIN exponer
    nada sensible (ni empresa completa, ni otros datos internos)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.empresa_id, e.folio, e.cliente_nombre, e.equipo_descripcion, e.estado,
               e.destino_lat, e.destino_lng, v.id AS vehiculo_id, v.geotab_device_id, v.nombre AS vehiculo_nombre,
               emp.nombre AS empresa_nombre
        FROM entregas e
        LEFT JOIN vehiculos_entrega v ON v.id = e.vehiculo_id
        LEFT JOIN empresas emp ON emp.id = e.empresa_id
        WHERE e.token_seguimiento = %s
    """, (token,))
    fila = cur.fetchone()
    cur.close(); conn.close()
    return dict(fila) if fila else None


def obtener_empresa(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, nombre, logo_base64, activo, creado_en, politicas_texto,
                  tema, color_acento, fondo_color, fondo_base64
           FROM empresas WHERE id = %s""",
        (empresa_id,),
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def actualizar_politicas_empresa(empresa_id, texto):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE empresas SET politicas_texto = %s WHERE id = %s", (texto, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def actualizar_apariencia_empresa(empresa_id, tema=None, color_acento="__sin_cambio__",
                                   fondo_color="__sin_cambio__", fondo_base64="__sin_cambio__"):
    """Cada campo de color/fondo puede mandarse como None explícito para quitarlo
    (volver al valor por defecto) — por eso usan un centinela para distinguir
    'no lo toques' de 'ponlo en null'."""
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if tema is not None:
        campos.append("tema = %s"); valores.append(tema)
    if color_acento != "__sin_cambio__":
        campos.append("color_acento = %s"); valores.append(color_acento)
    if fondo_color != "__sin_cambio__":
        campos.append("fondo_color = %s"); valores.append(fondo_color)
    if fondo_base64 != "__sin_cambio__":
        campos.append("fondo_base64 = %s"); valores.append(fondo_base64)
    if campos:
        valores.append(empresa_id)
        cur.execute(f"UPDATE empresas SET {', '.join(campos)} WHERE id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


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
                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_entregas,
                  u.acceso_checador_precio, u.acceso_marketing,
                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,
                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia
           FROM users u
           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id
           WHERE u.empresa_id = %s ORDER BY u.nombre_completo""",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_usuarios_master(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre_completo, telefono_whatsapp FROM users WHERE empresa_id = %s AND rol = 'master' AND activo = TRUE",
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
        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,
                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_entregas, acceso_checador_precio,
                  acceso_marketing
           FROM users WHERE id = %s""",
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


def listar_instaladores_activos(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre_completo, telefono_whatsapp FROM users WHERE empresa_id = %s AND rol = 'instalador' AND activo = TRUE ORDER BY nombre_completo",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_usuario(empresa_id, username, password, nombre_completo, rol, telefono_whatsapp=None, puesto=None,
                   sucursal_id=None, numero_empleado=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, telefono_whatsapp, puesto,
                               sucursal_id, numero_empleado, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, username, auth.hash_password(password), nombre_completo, rol, telefono_whatsapp, puesto,
         sucursal_id, numero_empleado, now),
    )
    user_id = cur.fetchone()["id"]
    if rol == "almacen":
        # Por default, un encargado de almacén nuevo arranca sin los demás
        # módulos — el administrador puede darle más después desde
        # Administrar → Accesos.
        cur.execute(
            """UPDATE users SET acceso_tickets = FALSE, acceso_equipos = FALSE,
                                 acceso_compras = FALSE, acceso_rh = FALSE WHERE id = %s""",
            (user_id,),
        )
    elif rol == "instalador":
        # Un instalador nuevo arranca solo con acceso a Entregas — el
        # administrador puede darle más después desde Administrar → Accesos.
        cur.execute(
            """UPDATE users SET acceso_tickets = FALSE, acceso_equipos = FALSE,
                                 acceso_compras = FALSE, acceso_rh = FALSE WHERE id = %s""",
            (user_id,),
        )
    elif rol == "encargado_sucursal":
        # El encargado de sucursal SÍ necesita ver RH por default — es
        # justo su función (aceptar incidencias de su gente) — pero no
        # necesita los demás módulos salvo que el administrador se los dé.
        cur.execute(
            """UPDATE users SET acceso_tickets = FALSE, acceso_equipos = FALSE,
                                 acceso_compras = FALSE WHERE id = %s""",
            (user_id,),
        )
    conn.commit()
    cur.close(); conn.close()
    return user_id


def actualizar_usuario(usuario_id, nombre_completo=None, rol=None, telefono_whatsapp=None, activo=None, password=None,
                        puesto=None, restriccion_categoria="__sin_cambio__", acceso_equipos=None,
                        acceso_administracion=None, acceso_compras=None, acceso_rh=None, acceso_dashboard=None,
                        acceso_tickets=None, acceso_reparaciones=None, acceso_entregas=None,
                        acceso_checador_precio=None, acceso_marketing=None,
                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",
                        rfc="__sin_cambio__", curp="__sin_cambio__", numero_licencia="__sin_cambio__",
                        tipo_licencia="__sin_cambio__", vigencia_licencia="__sin_cambio__"):
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
    if acceso_rh is not None:
        campos.append("acceso_rh = %s"); valores.append(acceso_rh)
    if acceso_dashboard is not None:
        campos.append("acceso_dashboard = %s"); valores.append(acceso_dashboard)
    if acceso_tickets is not None:
        campos.append("acceso_tickets = %s"); valores.append(acceso_tickets)
    if acceso_reparaciones is not None:
        campos.append("acceso_reparaciones = %s"); valores.append(acceso_reparaciones)
    if acceso_entregas is not None:
        campos.append("acceso_entregas = %s"); valores.append(acceso_entregas)
    if acceso_checador_precio is not None:
        campos.append("acceso_checador_precio = %s"); valores.append(acceso_checador_precio)
    if acceso_marketing is not None:
        campos.append("acceso_marketing = %s"); valores.append(acceso_marketing)
    if sucursal_id != "__sin_cambio__":  # permite mandar None explícito para quitar la sucursal
        campos.append("sucursal_id = %s"); valores.append(sucursal_id)
    if numero_empleado != "__sin_cambio__":  # permite mandar None explícito para quitarlo
        campos.append("numero_empleado = %s"); valores.append(numero_empleado)
    if rfc != "__sin_cambio__":
        campos.append("rfc = %s"); valores.append(rfc)
    if curp != "__sin_cambio__":
        campos.append("curp = %s"); valores.append(curp)
    if numero_licencia != "__sin_cambio__":
        campos.append("numero_licencia = %s"); valores.append(numero_licencia)
    if tipo_licencia != "__sin_cambio__":
        campos.append("tipo_licencia = %s"); valores.append(tipo_licencia)
    if vigencia_licencia != "__sin_cambio__":
        campos.append("vigencia_licencia = %s"); valores.append(vigencia_licencia)
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
    """Usa el folio MÁS ALTO que ya existe (no un conteo) para que nunca se repita
    uno, aunque se hayan borrado tickets anteriores (con 'Borrar datos', por
    ejemplo) — contar cuántos quedan no sirve porque el número baja pero los
    folios ya usados siguen existiendo."""
    cur.execute("SELECT folio FROM tickets WHERE empresa_id = %s", (empresa_id,))
    maximo = 0
    for row in cur.fetchall():
        try:
            numero = int(row["folio"].split("-")[-1])
            maximo = max(maximo, numero)
        except (ValueError, AttributeError, IndexError, TypeError):
            continue
    return f"TI-{maximo + 1:04d}"


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


def estadisticas_dashboard(empresa_id):
    """Resumen para la pantalla EN VIVO del Dashboard (más ligero que
    detalle_dashboard, que es para el PDF: ese trae además los desgloses por
    departamento/categoría/cliente/tipo/persona)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT estado, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    tickets_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM reparaciones WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    reparaciones_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM proyectos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    proyectos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM equipos WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    equipos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT estado, COUNT(*) AS n FROM ciclos_compra WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    ciclos_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("""
        SELECT COUNT(*) AS n FROM pedidos_compra p JOIN ciclos_compra c ON c.id = p.ciclo_id
        WHERE c.empresa_id = %s AND c.estado = 'abierto'
    """, (empresa_id,))
    pedidos_pendientes = cur.fetchone()["n"]

    cur.execute("""
        SELECT COALESCE(s.nombre, 'Sin sucursal') AS sucursal, COUNT(*) AS n_pedidos,
               COALESCE(SUM(p.cantidad * a.precio_unitario), 0) AS total
        FROM pedidos_compra p
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        LEFT JOIN sucursales_reparacion s ON s.id = p.sucursal_id
        LEFT JOIN articulos_compra a ON a.id = p.articulo_id
        WHERE c.empresa_id = %s
        GROUP BY s.nombre ORDER BY total DESC
    """, (empresa_id,))
    compras_por_sucursal = [{"sucursal": r["sucursal"], "pedidos": r["n_pedidos"], "total": round(r["total"], 2)} for r in cur.fetchall()]
    precio_general_compras = round(sum(s["total"] for s in compras_por_sucursal), 2)

    cur.execute("SELECT estado, COUNT(*) AS n FROM incidencias_rh WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    rh_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.close(); conn.close()

    return {
        "tickets": {
            "por_estado": {e: tickets_estado.get(e, 0) for e in ESTADOS}, "total": sum(tickets_estado.values()),
        },
        "reparaciones": {
            "por_estado": {e: reparaciones_estado.get(e, 0) for e in ESTADOS_REPARACION}, "total": sum(reparaciones_estado.values()),
        },
        "proyectos": {
            "por_estado": {e: proyectos_estado.get(e, 0) for e in ESTADOS_PROYECTO}, "total": sum(proyectos_estado.values()),
        },
        "equipos": {
            "por_estado": {e: equipos_estado.get(e, 0) for e in ESTADOS_EQUIPO}, "total": sum(equipos_estado.values()),
        },
        "compras": {
            "ciclos_por_estado": {e: ciclos_estado.get(e, 0) for e in ESTADOS_CICLO_COMPRA}, "ciclos_total": sum(ciclos_estado.values()),
            "pedidos_pendientes": pedidos_pendientes,
            "por_sucursal": compras_por_sucursal, "precio_general": precio_general_compras,
        },
        "rh": {
            "por_estado": {e: rh_estado.get(e, 0) for e in ESTADOS_INCIDENCIA_RH}, "total": sum(rh_estado.values()),
        },
    }


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

    cur.execute("""
        SELECT COALESCE(s.nombre, 'Sin sucursal') AS sucursal, COUNT(*) AS n_pedidos,
               COALESCE(SUM(p.cantidad * a.precio_unitario), 0) AS total
        FROM pedidos_compra p
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        LEFT JOIN sucursales_reparacion s ON s.id = p.sucursal_id
        LEFT JOIN articulos_compra a ON a.id = p.articulo_id
        WHERE c.empresa_id = %s
        GROUP BY s.nombre ORDER BY total DESC
    """, (empresa_id,))
    compras_por_sucursal = [{"sucursal": r["sucursal"], "pedidos": r["n_pedidos"], "total": round(r["total"], 2)} for r in cur.fetchall()]
    precio_general = round(sum(s["total"] for s in compras_por_sucursal), 2)

    cur.execute("SELECT estado, COUNT(*) AS n FROM incidencias_rh WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    rh_estado = {r["estado"]: r["n"] for r in cur.fetchall()}
    cur.execute("SELECT tipo, COUNT(*) AS n FROM incidencias_rh WHERE empresa_id = %s GROUP BY tipo ORDER BY n DESC", (empresa_id,))
    rh_tipo = [(r["tipo"], r["n"]) for r in cur.fetchall()]
    cur.execute("""
        SELECT u.nombre_completo AS persona, COUNT(*) AS n
        FROM incidencias_rh i JOIN users u ON u.id = i.usuario_id
        WHERE i.empresa_id = %s GROUP BY u.nombre_completo ORDER BY n DESC
    """, (empresa_id,))
    rh_persona = [(r["persona"], r["n"]) for r in cur.fetchall()]

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
            "por_sucursal": compras_por_sucursal, "precio_general": precio_general,
        },
        "rh": {
            "por_estado": {e: rh_estado.get(e, 0) for e in ESTADOS_INCIDENCIA_RH}, "total": sum(rh_estado.values()),
            "por_tipo": rh_tipo, "por_persona": rh_persona,
        },
    }


def obtener_notificaciones_usuario(empresa_id, usuario_id, rol):
    """Pendientes que le conviene saber a la persona apenas entra: tickets, tareas
    de proyecto, y ciclos de compra abiertos donde puede pedir. Se calcula al vuelo
    cada vez (no se guarda un historial ni un estado de 'ya lo vi')."""
    conn = get_connection()
    cur = conn.cursor()
    notificaciones = []

    if rol == "tecnico":
        cur.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE empresa_id = %s AND asignado_a_id = %s AND estado IN ('abierto','en_progreso')",
            (empresa_id, usuario_id),
        )
        n = cur.fetchone()["n"]
        if n > 0:
            notificaciones.append({
                "tipo": "ticket", "modulo": "tickets",
                "texto": f"Tienes {n} ticket(s) asignado(s) sin resolver" if n > 1 else "Tienes 1 ticket asignado sin resolver",
            })
    elif rol == "usuario":
        cur.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE empresa_id = %s AND solicitante_id = %s AND estado IN ('resuelto')",
            (empresa_id, usuario_id),
        )
        n = cur.fetchone()["n"]
        if n > 0:
            notificaciones.append({
                "tipo": "ticket", "modulo": "tickets",
                "texto": f"Tienes {n} ticket(s) resuelto(s) esperando que confirmes" if n > 1 else "Tienes 1 ticket resuelto esperando que confirmes",
            })

    cur.execute("""
        SELECT COUNT(*) AS n FROM proyecto_tareas t
        JOIN proyectos p ON p.id = t.proyecto_id
        JOIN proyecto_tarea_usuarios tu ON tu.tarea_id = t.id
        WHERE p.empresa_id = %s AND tu.usuario_id = %s AND t.estado != 'completada'
    """, (empresa_id, usuario_id))
    n = cur.fetchone()["n"]
    if n > 0:
        notificaciones.append({
            "tipo": "proyecto", "modulo": "proyectos",
            "texto": f"Tienes {n} tarea(s) de proyecto pendiente(s)" if n > 1 else "Tienes 1 tarea de proyecto pendiente",
        })

    cur.execute(
        "SELECT COUNT(*) AS n FROM ciclos_compra WHERE empresa_id = %s AND estado IN ('pendiente','abierto')",
        (empresa_id,),
    )
    n = cur.fetchone()["n"]
    if n > 0:
        notificaciones.append({
            "tipo": "compras", "modulo": "compras",
            "texto": f"Hay {n} ciclo(s) de compra abierto(s), puedes pedir del catálogo" if n > 1 else "Hay un ciclo de compra abierto, puedes pedir del catálogo",
        })

    if rol == "usuario":
        cur.execute(
            "SELECT COUNT(*) AS n FROM reparaciones WHERE empresa_id = %s AND creado_por_id = %s AND estado = 'listo_entrega'",
            (empresa_id, usuario_id),
        )
        n = cur.fetchone()["n"]
        if n > 0:
            notificaciones.append({
                "tipo": "reparacion", "modulo": "reparaciones",
                "texto": f"Tienes {n} reparación(es) lista(s) para entregar" if n > 1 else "Tienes 1 reparación lista para entregar",
            })

    cur.close(); conn.close()
    return notificaciones



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

    cur.execute("""
        SELECT COALESCE(s.nombre, 'Sin sucursal') AS sucursal, COUNT(*) AS n_pedidos,
               COALESCE(SUM(p.cantidad * a.precio_unitario), 0) AS total
        FROM pedidos_compra p
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        LEFT JOIN sucursales_reparacion s ON s.id = p.sucursal_id
        LEFT JOIN articulos_compra a ON a.id = p.articulo_id
        WHERE c.empresa_id = %s
        GROUP BY s.nombre ORDER BY total DESC
    """, (empresa_id,))
    compras_por_sucursal = [{"sucursal": r["sucursal"], "pedidos": r["n_pedidos"], "total": round(r["total"], 2)} for r in cur.fetchall()]
    precio_general_compras = round(sum(s["total"] for s in compras_por_sucursal), 2)

    cur.execute("SELECT estado, COUNT(*) AS n FROM incidencias_rh WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    rh_por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

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
            "por_sucursal": compras_por_sucursal, "precio_general": precio_general_compras,
        },
        "rh": {
            "por_estado": {e: rh_por_estado.get(e, 0) for e in ESTADOS_INCIDENCIA_RH},
            "total": sum(rh_por_estado.values()),
        },
    }


def obtener_notificaciones(empresa_id, usuario_id, rol, acceso_compras=True, acceso_rh=True, acceso_reparaciones=True, acceso_equipos=True):
    """Resumen EN VIVO de pendientes que le tocan a esta persona — no es un historial
    de eventos, así que no necesita marcarse como 'leído': en cuanto atienden el
    pendiente (cierran el ticket, firman el proyecto, etc.) deja de aparecer solo.
    Cada notificación es de UN elemento puntual (no un conteo agrupado), con su id,
    para que al hacer clic se pueda ir directo a ese elemento exacto."""
    conn = get_connection()
    cur = conn.cursor()
    notificaciones = []

    if rol == "tecnico":
        cur.execute(
            "SELECT id, folio, descripcion FROM tickets WHERE empresa_id = %s AND asignado_a_id = %s AND estado IN ('abierto','en_progreso') ORDER BY creado_en DESC LIMIT 20",
            (empresa_id, usuario_id),
        )
        for t in cur.fetchall():
            notificaciones.append({"tipo": "ticket", "icono": "🎫", "modulo": "tickets", "id": t["id"],
                                    "texto": f"Ticket {t['folio']} asignado a ti — {t['descripcion'][:60]}"})

    if rol == "usuario":
        cur.execute(
            "SELECT id, folio, descripcion FROM tickets WHERE empresa_id = %s AND creado_por_id = %s AND estado = 'resuelto' ORDER BY creado_en DESC LIMIT 20",
            (empresa_id, usuario_id),
        )
        for t in cur.fetchall():
            notificaciones.append({"tipo": "ticket", "icono": "🎫", "modulo": "tickets", "id": t["id"],
                                    "texto": f"Ticket {t['folio']} resuelto — revísalo: {t['descripcion'][:50]}"})

        cur.execute(
            "SELECT id, folio FROM reparaciones WHERE empresa_id = %s AND creado_por_id = %s AND estado = 'listo_entrega' ORDER BY creado_en DESC LIMIT 20",
            (empresa_id, usuario_id),
        )
        for r in cur.fetchall():
            notificaciones.append({"tipo": "reparacion", "icono": "🔧", "modulo": "reparaciones", "id": r["id"],
                                    "texto": f"Reparación {r['folio']} lista para entregar"})

    if rol in ("admin", "tecnico", "usuario"):
        cur.execute("""
            SELECT DISTINCT p.id, p.nombre
            FROM proyectos p
            JOIN proyecto_participantes_usuarios pu ON pu.proyecto_id = p.id
            LEFT JOIN proyecto_firmas pf ON pf.proyecto_id = p.id AND pf.usuario_id = %s
            WHERE p.empresa_id = %s AND pu.usuario_id = %s AND pf.estado IS NULL AND p.fecha_inicio IS NULL
            LIMIT 20
        """, (usuario_id, empresa_id, usuario_id))
        for p in cur.fetchall():
            notificaciones.append({"tipo": "proyecto", "icono": "📋", "modulo": "proyectos", "id": p["id"],
                                    "texto": f"Proyecto \"{p['nombre']}\" esperando tu firma de compromiso"})

    if acceso_equipos:
        cur.execute(
            "SELECT id, nombre FROM equipos WHERE empresa_id = %s AND usuario_id = %s AND firma_responsiva_base64 IS NULL AND estado != 'baja'",
            (empresa_id, usuario_id),
        )
        for e in cur.fetchall():
            notificaciones.append({"tipo": "equipo", "icono": "💻", "modulo": "equipos", "id": e["id"],
                                    "texto": f"Firma tu carta responsiva del equipo \"{e['nombre']}\""})

    if rol in ("admin", "tecnico", "usuario") and acceso_compras:
        cur.execute(
            "SELECT id, nombre FROM ciclos_compra WHERE empresa_id = %s AND estado IN ('pendiente','abierto') ORDER BY fecha_programada DESC LIMIT 20",
            (empresa_id,),
        )
        for c in cur.fetchall():
            notificaciones.append({"tipo": "compras", "icono": "🛒", "modulo": "compras", "id": c["id"],
                                    "texto": f"Ciclo de compra abierto: \"{c['nombre']}\" — puedes hacer tu pedido"})

    if rol == "admin" and acceso_rh:
        cur.execute(
            "SELECT id, usuario_id FROM incidencias_rh WHERE empresa_id = %s AND estado = 'pendiente' ORDER BY creado_en DESC LIMIT 20",
            (empresa_id,),
        )
        for i in cur.fetchall():
            notificaciones.append({"tipo": "rh", "icono": "🩺", "modulo": "rh", "id": i["id"],
                                    "texto": "Incidencia de RH pendiente de aprobar"})

    if rol == "almacen" or acceso_reparaciones:
        if rol == "almacen":
            cur.execute(
                "SELECT id, folio FROM reparaciones WHERE empresa_id = %s AND estado = 'en_traslado' AND sucursal_id = %s ORDER BY creado_en DESC LIMIT 20",
                (empresa_id, obtener_sucursal_id_usuario(usuario_id)),
            )
            for r in cur.fetchall():
                notificaciones.append({"tipo": "reparacion", "icono": "🔧", "modulo": "reparaciones", "id": r["id"],
                                        "texto": f"Reparación {r['folio']} en camino a tu sucursal"})

    if rol == "encargado_sucursal":
        mi_sucursal_id = obtener_sucursal_id_usuario(usuario_id)
        if mi_sucursal_id:
            cur.execute("""
                SELECT m.id, m.horas, u.nombre_completo AS usuario_nombre
                FROM horas_rh_movimientos m JOIN users u ON u.id = m.usuario_id
                WHERE m.empresa_id = %s AND m.estado = 'pendiente' AND m.tipo = 'pago' AND u.sucursal_id = %s
                ORDER BY m.creado_en ASC LIMIT 20
            """, (empresa_id, mi_sucursal_id))
            for h in cur.fetchall():
                notificaciones.append({"tipo": "horas", "icono": "🕒", "modulo": "rh", "id": h["id"],
                                        "texto": f"{h['usuario_nombre']} registró {h['horas']} hrs pagadas — falta tu autorización"})

    cur.execute("""
        SELECT id, horas FROM incidencias_rh
        WHERE empresa_id = %s AND usuario_id = %s AND tipo = 'dia_libre_sin_goce'
              AND motivo LIKE 'Generado automáticamente%%' AND estado = 'propuesta_empleado'
        ORDER BY creado_en DESC LIMIT 20
    """, (empresa_id, usuario_id))
    for c in cur.fetchall():
        notificaciones.append({"tipo": "rh", "icono": "⚠️", "modulo": "rh", "id": c["id"],
                                "texto": f"Ya acumulaste 8 horas a deber — responde si aceptas que se conviertan en un día sin goce de sueldo"})

    cur.close(); conn.close()
    return notificaciones


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
    if "usuario_id" in campos_nuevos and campos_nuevos["usuario_id"] is not None:
        # Si se reasigna a otra persona, la firma de responsiva anterior ya no
        # aplica — que la vuelva a firmar quien lo tenga ahora.
        actual = obtener_equipo(empresa_id, equipo_id)
        if actual and actual.get("usuario_id") != campos_nuevos["usuario_id"]:
            campos.append("firma_responsiva_base64 = NULL"); campos.append("firma_responsiva_en = NULL")
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


def firmar_responsiva_equipo(empresa_id, equipo_id, firma_base64):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE equipos SET firma_responsiva_base64 = %s, firma_responsiva_en = %s WHERE id = %s AND empresa_id = %s",
        (firma_base64, now, equipo_id, empresa_id),
    )
    conn.commit()
    cur.close(); conn.close()
    return obtener_equipo(empresa_id, equipo_id)


def listar_equipos_pendientes_firma(empresa_id, usuario_id):
    """Equipos asignados a esta persona que todavía no tienen su firma de
    responsiva — para el apartado de 'Mis tareas'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, nombre, tipo, marca, modelo FROM equipos
           WHERE empresa_id = %s AND usuario_id = %s AND firma_responsiva_base64 IS NULL AND estado != 'baja'""",
        (empresa_id, usuario_id),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_proyectos_pendientes_firma_usuario(empresa_id, usuario_id):
    """Proyectos donde esta persona es participante y todavía no firmó su
    compromiso (ni tampoco marcó que no está conforme) — para 'Mis tareas'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT p.id, p.nombre
        FROM proyectos p
        JOIN proyecto_participantes_usuarios pu ON pu.proyecto_id = p.id
        LEFT JOIN proyecto_firmas pf ON pf.proyecto_id = p.id AND pf.usuario_id = %s
        WHERE p.empresa_id = %s AND pu.usuario_id = %s AND pf.estado IS NULL AND p.fecha_inicio IS NULL
    """, (usuario_id, empresa_id, usuario_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_tareas_proyecto_usuario(empresa_id, usuario_id):
    """Tareas de proyecto asignadas a esta persona que todavía no ha
    terminado — para 'Mis tareas'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.descripcion, t.estado, t.fecha_limite, t.proyecto_id, p.nombre AS proyecto_nombre
        FROM proyecto_tareas t
        JOIN proyectos p ON p.id = t.proyecto_id
        JOIN proyecto_tarea_usuarios tu ON tu.tarea_id = t.id
        WHERE p.empresa_id = %s AND tu.usuario_id = %s AND t.estado != 'completada'
        ORDER BY t.fecha_limite IS NULL, t.fecha_limite ASC
    """, (empresa_id, usuario_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


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


def eliminar_empresa_completa(empresa_id):
    """Borra una empresa y TODOS sus datos, sin dejar nada huérfano —
    tickets, reparaciones, entregas, equipos, proyectos, compras, RH,
    sucursales, vehículos, términos personalizados y usuarios. No se
    puede deshacer. Las tablas 'hijas' (comentarios de ticket, checklist
    de entrega, items de costo de reparación, evidencias, historial,
    mantenimientos, etc.) ya tienen ON DELETE CASCADE en su llave foránea,
    así que se van solas al borrar la tabla 'padre' correspondiente."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Tablas de dominio, en cualquier orden entre ellas — ninguna
        # depende de otra (solo dependen de empresas y de users, y a
        # users lo dejamos hasta el final).
        for tabla in [
            "tickets", "equipos", "proyectos", "articulos_compra", "ciclos_compra",
            "reparaciones", "entregas", "incidencias_rh", "horas_rh_movimientos",
            "cursos_rh", "sucursales_reparacion", "vehiculos_entrega",
            "terminos_personalizados", "departamentos", "categorias",
        ]:
            cur.execute(f"DELETE FROM {tabla} WHERE empresa_id = %s", (empresa_id,))
        # Los usuarios al final — muchas de las tablas de arriba los
        # referenciaban (creado_por_id, tecnico_id, etc.) y ya se fueron.
        cur.execute("DELETE FROM users WHERE empresa_id = %s", (empresa_id,))
        # La empresa misma, al final de todo.
        cur.execute("DELETE FROM empresas WHERE id = %s", (empresa_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"No se pudo borrar la empresa por completo: {e}") from e
    finally:
        cur.close(); conn.close()


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
        SELECT t.*
        FROM proyecto_tareas t
        WHERE t.proyecto_id = %s ORDER BY t.creado_en ASC
    """, (proyecto["id"],))
    tareas = [dict(r) for r in cur.fetchall()]
    if tareas:
        cur.execute("""
            SELECT tu.tarea_id, u.id, u.nombre_completo
            FROM proyecto_tarea_usuarios tu JOIN users u ON u.id = tu.usuario_id
            WHERE tu.tarea_id IN %s ORDER BY u.nombre_completo
        """, (tuple(t["id"] for t in tareas),))
        asignados_por_tarea = {}
        for tarea_id, usuario_id, nombre in cur.fetchall():
            asignados_por_tarea.setdefault(tarea_id, []).append({"id": usuario_id, "nombre_completo": nombre})
        for t in tareas:
            t["usuarios"] = asignados_por_tarea.get(t["id"], [])
            # Se conserva "usuario_nombre" (el primer asignado) por si algo viejo del
            # frontend todavía lo usa — pero lo normal ya es leer la lista "usuarios".
            t["usuario_nombre"] = t["usuarios"][0]["nombre_completo"] if t["usuarios"] else None
    proyecto["tareas"] = tareas

    if proyecto.get("fecha_inicio"):
        inicio = datetime.fromisoformat(proyecto["fecha_inicio"])
        fin = datetime.fromisoformat(proyecto["fecha_completado"]) if proyecto.get("fecha_completado") else ahora()
        proyecto["dias_transcurridos"] = round((fin - inicio).total_seconds() / 86400, 1)
    else:
        proyecto["dias_transcurridos"] = None

    return proyecto


def obtener_o_crear_token_calendario(usuario_id):
    """Cada persona tiene un enlace de calendario propio y secreto — se genera
    la primera vez que lo pide, y de ahí siempre es el mismo (para que no se
    le rompa la suscripción ya hecha en su celular)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT calendario_token FROM users WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    if row and row["calendario_token"]:
        cur.close(); conn.close()
        return row["calendario_token"]
    token = secrets.token_urlsafe(24)
    cur.execute("UPDATE users SET calendario_token = %s WHERE id = %s", (token, usuario_id))
    conn.commit()
    cur.close(); conn.close()
    return token


def regenerar_token_calendario(usuario_id):
    """Por si alguien quiere invalidar el enlace viejo (ej. lo compartió sin querer)."""
    token = secrets.token_urlsafe(24)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET calendario_token = %s WHERE id = %s", (token, usuario_id))
    conn.commit()
    cur.close(); conn.close()
    return token


def obtener_usuario_por_token_calendario(token):
    """El enlace .ics no pasa por el login normal — el propio token, imposible
    de adivinar, funciona como su credencial. Así es como Google Calendar,
    Notion, Trello, etc. hacen sus calendarios 'de suscripción' también."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, empresa_id, rol, nombre_completo FROM users WHERE calendario_token = %s AND activo = TRUE", (token,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def listar_eventos_calendario_usuario(empresa_id, usuario_id, rol):
    """Junta los proyectos y mantenimientos que le tocan a esta persona, con
    fecha, para armar su calendario de suscripción — cada quien ve lo suyo:
    proyectos donde participa, y mantenimientos si tiene que ver con Equipos."""
    conn = get_connection()
    cur = conn.cursor()
    eventos = []

    if rol == "admin":
        cur.execute("""
            SELECT id, nombre, descripcion, fecha_inicio, fecha_estimada
            FROM proyectos WHERE empresa_id = %s AND fecha_estimada IS NOT NULL AND estado NOT IN ('completado','cancelado')
        """, (empresa_id,))
    else:
        cur.execute("""
            SELECT DISTINCT p.id, p.nombre, p.descripcion, p.fecha_inicio, p.fecha_estimada
            FROM proyectos p
            JOIN proyecto_participantes_usuarios pu ON pu.proyecto_id = p.id
            WHERE p.empresa_id = %s AND pu.usuario_id = %s AND p.fecha_estimada IS NOT NULL
                  AND p.estado NOT IN ('completado', 'cancelado')
        """, (empresa_id, usuario_id))
    for p in cur.fetchall():
        eventos.append({
            "tipo": "proyecto", "id": p["id"], "titulo": f"Proyecto: {p['nombre']}",
            "descripcion": p.get("descripcion") or "", "fecha": p["fecha_estimada"],
        })

    if rol in ("admin", "tecnico"):
        cur.execute("""
            SELECT m.id, m.descripcion, m.fecha_programada, e.nombre AS equipo_nombre
            FROM mantenimientos m JOIN equipos e ON e.id = m.equipo_id
            WHERE m.empresa_id = %s AND m.estado = 'pendiente'
                  AND (%s = 'admin' OR m.tecnico_asignado_id = %s OR m.tecnico_asignado_id IS NULL)
        """, (empresa_id, rol, usuario_id))
        for m in cur.fetchall():
            eventos.append({
                "tipo": "mantenimiento", "id": m["id"], "titulo": f"Mantenimiento: {m['equipo_nombre']}",
                "descripcion": m.get("descripcion") or "", "fecha": m["fecha_programada"],
            })

    cur.close(); conn.close()
    return eventos


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
        uids = t.get("usuario_ids") or ([t["usuario_id"]] if t.get("usuario_id") else [])
        if uids and t.get("descripcion"):
            cur.execute(
                """INSERT INTO proyecto_tareas (proyecto_id, usuario_id, descripcion, estado, fecha_limite, creado_en, actualizado_en)
                   VALUES (%s, %s, %s, 'pendiente', %s, %s, %s) RETURNING id""",
                (proyecto_id, uids[0], t["descripcion"].strip(), t.get("fecha_limite"), now, now),
            )
            tarea_id = cur.fetchone()["id"]
            for uid in uids:
                cur.execute(
                    "INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (tarea_id, uid),
                )
    conn.commit()
    cur.close(); conn.close()
    return proyecto_id


def crear_tarea_proyecto(proyecto_id, usuario_ids, descripcion, fecha_limite=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    usuario_ids = [u for u in (usuario_ids or []) if u]
    cur.execute(
        """INSERT INTO proyecto_tareas (proyecto_id, usuario_id, descripcion, estado, fecha_limite, creado_en, actualizado_en)
           VALUES (%s, %s, %s, 'pendiente', %s, %s, %s) RETURNING id""",
        # usuario_id se sigue llenando con el primero de la lista, nada más
        # por compatibilidad con datos/reportes viejos — la fuente real de
        # quién está asignado ya es proyecto_tarea_usuarios.
        (proyecto_id, usuario_ids[0] if usuario_ids else None, descripcion.strip(), fecha_limite, now, now),
    )
    tarea_id = cur.fetchone()["id"]
    for uid in usuario_ids:
        cur.execute(
            "INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (tarea_id, uid),
        )
    conn.commit()
    cur.close(); conn.close()
    return tarea_id


def asignar_usuarios_tarea_proyecto(tarea_id, usuario_ids):
    """Reemplaza por completo a quién está asignada la tarea."""
    conn = get_connection()
    cur = conn.cursor()
    usuario_ids = [u for u in (usuario_ids or []) if u]
    cur.execute("DELETE FROM proyecto_tarea_usuarios WHERE tarea_id = %s", (tarea_id,))
    for uid in usuario_ids:
        cur.execute(
            "INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (tarea_id, uid),
        )
    cur.execute("UPDATE proyecto_tareas SET usuario_id = %s WHERE id = %s",
                (usuario_ids[0] if usuario_ids else None, tarea_id))
    conn.commit()
    cur.close(); conn.close()


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


def crear_articulo_compra(empresa_id, nombre, proveedor=None, marca=None, foto_base64=None, notas=None, categoria=None,
                           precio_unitario=None, stock_actual=0, stock_minimo=0):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO articulos_compra (empresa_id, nombre, proveedor, marca, foto_base64, notas, categoria,
                                          precio_unitario, stock_actual, stock_minimo, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, nombre, proveedor, marca, foto_base64, notas, categoria,
         precio_unitario, stock_actual or 0, stock_minimo or 0, now),
    )
    articulo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return articulo_id


def _icono_categoria_compra(color, emoji):
    """Genera un ícono simple (SVG propio, sin derechos de autor de terceros) para
    representar visualmente cada categoría del catálogo, ya que no se pueden usar
    fotos reales de productos de tiendas por temas de derechos de autor."""
    import base64 as _b64
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">'
        f'<rect width="300" height="300" fill="{color}"/>'
        f'<text x="150" y="200" font-size="150" text-anchor="middle" font-family="sans-serif">{emoji}</text>'
        f'</svg>'
    )
    return "data:image/svg+xml;base64," + _b64.b64encode(svg.encode("utf-8")).decode("ascii")


_ICONOS_CATEGORIA_COMPRA = {
    "Papelería": _icono_categoria_compra("#5B9BD5", "📎"),
    "Limpieza": _icono_categoria_compra("#70AD47", "🧴"),
    "Ferretería": _icono_categoria_compra("#E8823D", "🔧"),
    "Equipo de cómputo": _icono_categoria_compra("#9B59B6", "💻"),
    "Cafetería": _icono_categoria_compra("#8B5A2B", "☕"),
    "Equipo de oficina": _icono_categoria_compra("#D8192F", "🗄️"),
}


CATALOGO_INICIAL_COMPRAS = [
    # ---- Papelería ---- (precios de referencia, ajústalos según tu proveedor real)
    {"nombre": "Papel bond carta (paquete 500 hojas)", "categoria": "Papelería", "precio_unitario": 135.00},
    {"nombre": "Papel bond oficio (paquete 500 hojas)", "categoria": "Papelería", "precio_unitario": 150.00},
    {"nombre": "Bolígrafos punto mediano negro (caja 12)", "categoria": "Papelería", "precio_unitario": 60.00},
    {"nombre": "Bolígrafos punto mediano azul (caja 12)", "categoria": "Papelería", "precio_unitario": 60.00},
    {"nombre": "Lápices del núm. 2 (caja 12)", "categoria": "Papelería", "precio_unitario": 35.00},
    {"nombre": "Marcadores permanentes (paquete 4)", "categoria": "Papelería", "precio_unitario": 85.00},
    {"nombre": "Resaltadores / marcatextos (paquete 4)", "categoria": "Papelería", "precio_unitario": 70.00},
    {"nombre": "Corrector líquido", "categoria": "Papelería", "precio_unitario": 25.00},
    {"nombre": "Clips estándar (caja 100)", "categoria": "Papelería", "precio_unitario": 20.00},
    {"nombre": "Grapas estándar (caja 5000)", "categoria": "Papelería", "precio_unitario": 35.00},
    {"nombre": "Engrapadora", "categoria": "Papelería", "precio_unitario": 95.00},
    {"nombre": "Perforadora de 2 orificios", "categoria": "Papelería", "precio_unitario": 150.00},
    {"nombre": "Cinta adhesiva transparente", "categoria": "Papelería", "precio_unitario": 18.00},
    {"nombre": "Notas adhesivas Post-it (paquete)", "categoria": "Papelería", "precio_unitario": 55.00},
    {"nombre": "Folders tamaño carta (paquete 100)", "categoria": "Papelería", "precio_unitario": 180.00},
    {"nombre": "Sobres carta (paquete 50)", "categoria": "Papelería", "precio_unitario": 90.00},
    {"nombre": "Libretas profesionales (paquete 3)", "categoria": "Papelería", "precio_unitario": 120.00},
    {"nombre": "Tijeras de oficina", "categoria": "Papelería", "precio_unitario": 45.00},
    {"nombre": "Cutter / cortador", "categoria": "Papelería", "precio_unitario": 30.00},
    {"nombre": "Tóner genérico para impresora láser", "categoria": "Papelería", "precio_unitario": 450.00},

    # ---- Limpieza ----
    {"nombre": "Cloro (garrafa 3.8L)", "categoria": "Limpieza", "precio_unitario": 45.00},
    {"nombre": "Jabón líquido para manos (galón)", "categoria": "Limpieza", "precio_unitario": 110.00},
    {"nombre": "Papel higiénico industrial (paquete 12 rollos)", "categoria": "Limpieza", "precio_unitario": 180.00},
    {"nombre": "Toallas de papel / secamanos (paquete)", "categoria": "Limpieza", "precio_unitario": 150.00},
    {"nombre": "Franela multiusos (paquete)", "categoria": "Limpieza", "precio_unitario": 60.00},
    {"nombre": "Fibra para trastes (paquete 10)", "categoria": "Limpieza", "precio_unitario": 35.00},
    {"nombre": "Bolsas de basura grandes (paquete 20)", "categoria": "Limpieza", "precio_unitario": 65.00},
    {"nombre": "Escoba", "categoria": "Limpieza", "precio_unitario": 80.00},
    {"nombre": "Trapeador", "categoria": "Limpieza", "precio_unitario": 95.00},
    {"nombre": "Cubeta", "categoria": "Limpieza", "precio_unitario": 70.00},
    {"nombre": "Desinfectante multiusos (litro)", "categoria": "Limpieza", "precio_unitario": 55.00},
    {"nombre": "Limpiador de vidrios (litro)", "categoria": "Limpieza", "precio_unitario": 50.00},
    {"nombre": "Guantes de látex (caja 100)", "categoria": "Limpieza", "precio_unitario": 95.00},
    {"nombre": "Aromatizante ambiental", "categoria": "Limpieza", "precio_unitario": 60.00},
    {"nombre": "Detergente en polvo (kg)", "categoria": "Limpieza", "precio_unitario": 50.00},

    # ---- Ferretería ----
    {"nombre": "Cinta métrica 5m", "categoria": "Ferretería", "precio_unitario": 75.00},
    {"nombre": "Desarmador plano", "categoria": "Ferretería", "precio_unitario": 45.00},
    {"nombre": "Desarmador de cruz", "categoria": "Ferretería", "precio_unitario": 45.00},
    {"nombre": "Juego de desarmadores", "categoria": "Ferretería", "precio_unitario": 250.00},
    {"nombre": "Pinzas de electricista", "categoria": "Ferretería", "precio_unitario": 110.00},
    {"nombre": "Martillo", "categoria": "Ferretería", "precio_unitario": 150.00},
    {"nombre": "Taladro / rotomartillo básico", "categoria": "Ferretería", "precio_unitario": 850.00},
    {"nombre": "Extensión eléctrica 5m", "categoria": "Ferretería", "precio_unitario": 180.00},
    {"nombre": "Multicontacto / regleta eléctrica", "categoria": "Ferretería", "precio_unitario": 120.00},
    {"nombre": "Cinta aislante", "categoria": "Ferretería", "precio_unitario": 25.00},
    {"nombre": "Pistola de silicón", "categoria": "Ferretería", "precio_unitario": 130.00},
    {"nombre": "Tornillos surtidos (caja)", "categoria": "Ferretería", "precio_unitario": 60.00},
    {"nombre": "Focos LED (paquete 4)", "categoria": "Ferretería", "precio_unitario": 150.00},
    {"nombre": "Candado", "categoria": "Ferretería", "precio_unitario": 95.00},
    {"nombre": "Cable eléctrico (metro)", "categoria": "Ferretería", "precio_unitario": 12.00},

    # ---- Equipo de cómputo ----
    {"nombre": "Mouse óptico USB", "categoria": "Equipo de cómputo", "precio_unitario": 180.00},
    {"nombre": "Teclado USB estándar", "categoria": "Equipo de cómputo", "precio_unitario": 220.00},
    {"nombre": "Mouse pad", "categoria": "Equipo de cómputo", "precio_unitario": 60.00},
    {"nombre": "Cable HDMI 1.5m", "categoria": "Equipo de cómputo", "precio_unitario": 120.00},
    {"nombre": "Cable USB", "categoria": "Equipo de cómputo", "precio_unitario": 80.00},
    {"nombre": "Memoria USB 32GB", "categoria": "Equipo de cómputo", "precio_unitario": 150.00},
    {"nombre": "Disco duro externo 1TB", "categoria": "Equipo de cómputo", "precio_unitario": 950.00},
    {"nombre": "Audífonos con micrófono", "categoria": "Equipo de cómputo", "precio_unitario": 250.00},
    {"nombre": "Webcam USB", "categoria": "Equipo de cómputo", "precio_unitario": 450.00},
    {"nombre": "No-break / regulador de voltaje", "categoria": "Equipo de cómputo", "precio_unitario": 600.00},
    {"nombre": "Base para laptop", "categoria": "Equipo de cómputo", "precio_unitario": 280.00},

    # ---- Cafetería / Consumibles ----
    {"nombre": "Café soluble (frasco 200g)", "categoria": "Cafetería", "precio_unitario": 95.00},
    {"nombre": "Azúcar (kg)", "categoria": "Cafetería", "precio_unitario": 28.00},
    {"nombre": "Vasos desechables (paquete 50)", "categoria": "Cafetería", "precio_unitario": 45.00},
    {"nombre": "Servilletas (paquete)", "categoria": "Cafetería", "precio_unitario": 30.00},
    {"nombre": "Agua embotellada (garrafón 20L)", "categoria": "Cafetería", "precio_unitario": 45.00},
    {"nombre": "Té (caja 25 sobres)", "categoria": "Cafetería", "precio_unitario": 40.00},
    {"nombre": "Cucharas desechables (paquete 50)", "categoria": "Cafetería", "precio_unitario": 35.00},
    {"nombre": "Filtros de café (paquete)", "categoria": "Cafetería", "precio_unitario": 25.00},

    # ---- Equipo de oficina ----
    {"nombre": "Calculadora básica", "categoria": "Equipo de oficina", "precio_unitario": 120.00},
    {"nombre": "Organizador de escritorio", "categoria": "Equipo de oficina", "precio_unitario": 150.00},
    {"nombre": "Charola de documentos", "categoria": "Equipo de oficina", "precio_unitario": 90.00},
    {"nombre": "Pizarrón blanco pequeño", "categoria": "Equipo de oficina", "precio_unitario": 350.00},
    {"nombre": "Plumones para pizarrón (paquete 4)", "categoria": "Equipo de oficina", "precio_unitario": 90.00},
    {"nombre": "Extintor pequeño", "categoria": "Equipo de oficina", "precio_unitario": 450.00},
]

for _item in CATALOGO_INICIAL_COMPRAS:
    _item["foto_base64"] = _ICONOS_CATEGORIA_COMPRA[_item["categoria"]]


def sembrar_catalogo_compras(empresa_id):
    """Carga el catálogo inicial de productos comunes (papelería, limpieza,
    ferretería, equipo de cómputo, etc.) con precios de referencia y un ícono
    por categoría. No duplica artículos que ya existan (comparando por nombre,
    sin importar mayúsculas)."""
    existentes = {a["nombre"].strip().lower() for a in listar_articulos_compra(empresa_id, solo_activos=False)}
    agregados = 0
    for item in CATALOGO_INICIAL_COMPRAS:
        if item["nombre"].strip().lower() in existentes:
            continue
        crear_articulo_compra(empresa_id, item["nombre"], categoria=item["categoria"],
                               precio_unitario=item["precio_unitario"], foto_base64=item["foto_base64"])
        agregados += 1
    return agregados


def listar_categorias_compra(empresa_id):
    """Categorías ya usadas en el catálogo (para armar el selector al crear un ciclo)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT categoria FROM articulos_compra WHERE empresa_id = %s AND categoria IS NOT NULL AND categoria != '' ORDER BY categoria",
        (empresa_id,),
    )
    rows = [r["categoria"] for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def actualizar_articulo_compra(empresa_id, articulo_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = ["nombre", "proveedor", "marca", "foto_base64", "notas", "activo", "categoria",
                  "precio_unitario", "stock_actual", "stock_minimo"]
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [articulo_id, empresa_id]
        cur.execute(f"UPDATE articulos_compra SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def ajustar_stock_articulo(empresa_id, articulo_id, delta):
    """Suma (o resta, si delta es negativo) al stock actual del artículo — nunca
    lo deja bajar de cero. Devuelve el stock resultante, o None si no existe."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT stock_actual FROM articulos_compra WHERE id = %s AND empresa_id = %s", (articulo_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    nuevo = max(row["stock_actual"] + delta, 0)
    cur.execute("UPDATE articulos_compra SET stock_actual = %s WHERE id = %s AND empresa_id = %s",
                (nuevo, articulo_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    return nuevo


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
        SELECT p.cantidad, p.notas, p.creado_en,
               c.nombre AS ciclo_nombre, c.estado AS ciclo_estado, c.fecha_programada, c.categoria,
               COALESCE(a.nombre, p.articulo_libre) AS articulo_nombre, a.proveedor, a.marca,
               u.nombre_completo AS usuario_nombre, s.nombre AS sucursal_nombre
        FROM pedidos_compra p
        JOIN ciclos_compra c ON c.id = p.ciclo_id
        LEFT JOIN articulos_compra a ON a.id = p.articulo_id
        LEFT JOIN sucursales_reparacion s ON s.id = p.sucursal_id
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
        SELECT c.*, u.nombre_completo AS creado_por_nombre, au.nombre_completo AS autorizado_por_nombre
        FROM ciclos_compra c
        JOIN users u ON u.id = c.creado_por_id
        LEFT JOIN users au ON au.id = c.autorizado_por_id
        WHERE c.id = %s AND c.empresa_id = %s
    """, (ciclo_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    ciclo = dict(row)
    cur.execute("""
        SELECT p.*,
               COALESCE(a.nombre, p.articulo_libre) AS articulo_nombre,
               a.proveedor, a.marca, a.foto_base64, a.precio_unitario,
               u.nombre_completo AS usuario_nombre, u.telefono_whatsapp AS usuario_telefono,
               s.id AS sucursal_id, s.nombre AS sucursal_nombre
        FROM pedidos_compra p
        LEFT JOIN articulos_compra a ON a.id = p.articulo_id
        LEFT JOIN sucursales_reparacion s ON s.id = p.sucursal_id
        JOIN users u ON u.id = p.usuario_id
        WHERE p.ciclo_id = %s ORDER BY p.creado_en ASC
    """, (ciclo_id,))
    pedidos = [dict(r) for r in cur.fetchall()]
    for p in pedidos:
        precio = p.get("precio_unitario")
        p["subtotal"] = round(precio * p["cantidad"], 2) if precio is not None else None
    ciclo["pedidos"] = pedidos

    # Desglose por sucursal: cuántos pedidos y cuánto suman, para el Dashboard y la autorización.
    por_sucursal = {}
    total_general = 0.0
    hay_precio_faltante = False
    for p in pedidos:
        clave = p.get("sucursal_nombre") or "Sin sucursal"
        if clave not in por_sucursal:
            por_sucursal[clave] = {"sucursal": clave, "pedidos": 0, "total": 0.0}
        por_sucursal[clave]["pedidos"] += 1
        if p["subtotal"] is not None:
            por_sucursal[clave]["total"] += p["subtotal"]
            total_general += p["subtotal"]
        else:
            hay_precio_faltante = True
    ciclo["desglose_sucursales"] = list(por_sucursal.values())
    ciclo["total_general"] = round(total_general, 2)
    ciclo["hay_precio_faltante"] = hay_precio_faltante

    cur.close(); conn.close()
    return ciclo


def crear_ciclo_compra(empresa_id, nombre, frecuencia, fecha_programada, creado_por_id, categoria=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO ciclos_compra (empresa_id, nombre, frecuencia, fecha_programada, estado, creado_por_id, creado_en, categoria)
           VALUES (%s, %s, %s, %s, 'pendiente', %s, %s, %s) RETURNING id""",
        (empresa_id, nombre, frecuencia, fecha_programada, creado_por_id, now, categoria),
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
    """Marca el ciclo como surtido (comprado) y, si es recurrente, programa el
    siguiente. OJO: esto todavía NO lo deja en 'cerrado' — pasa a
    'esperando_autorizacion' y solo llega a 'cerrado' cuando el usuario master
    lo autoriza con su firma."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ciclos_compra WHERE id = %s AND empresa_id = %s", (ciclo_id, empresa_id))
    ciclo = cur.fetchone()
    if not ciclo:
        cur.close(); conn.close()
        return None
    ciclo = dict(ciclo)
    now = ahora().isoformat(timespec="seconds")
    cur.execute("UPDATE ciclos_compra SET estado = 'esperando_autorizacion', cerrado_en = %s WHERE id = %s",
                (now, ciclo_id))
    conn.commit()
    cur.close(); conn.close()

    siguiente_id = None
    siguiente_fecha = _siguiente_fecha_compra(ciclo["fecha_programada"], ciclo["frecuencia"])
    if siguiente_fecha:
        siguiente_id = crear_ciclo_compra(empresa_id, ciclo["nombre"], ciclo["frecuencia"], siguiente_fecha,
                                           ciclo["creado_por_id"], ciclo.get("categoria"))
    return {"cerrado_id": ciclo_id, "siguiente_id": siguiente_id}


def listar_ciclos_pendientes_autorizacion(empresa_id):
    """Ciclos ya marcados como surtidos pero que el usuario master todavía no
    autoriza con su firma — con el total a pagar ya calculado."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM ciclos_compra
        WHERE empresa_id = %s AND estado = 'esperando_autorizacion'
        ORDER BY cerrado_en ASC
    """, (empresa_id,))
    ids = [r["id"] for r in cur.fetchall()]
    cur.close(); conn.close()
    return [obtener_ciclo_compra(empresa_id, cid) for cid in ids]


def autorizar_ciclo_compra(empresa_id, ciclo_id, usuario_id, firma_base64):
    """La firma del master es lo que finalmente deja el ciclo en 'cerrado'."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE ciclos_compra
        SET estado = 'cerrado', autorizado = TRUE, autorizado_por_id = %s, autorizado_en = %s, firma_autorizacion = %s
        WHERE id = %s AND empresa_id = %s AND estado = 'esperando_autorizacion'
    """, (usuario_id, now, firma_base64, ciclo_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def agregar_pedido_compra(ciclo_id, articulo_id, usuario_id, cantidad, sucursal_id, notas=None, articulo_libre=None):
    """Si el mismo usuario ya había pedido este mismo producto en este ciclo, se
    suma la cantidad al pedido existente en vez de crear una línea duplicada."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")

    if articulo_id:
        cur.execute(
            "SELECT id, cantidad FROM pedidos_compra WHERE ciclo_id = %s AND usuario_id = %s AND articulo_id = %s",
            (ciclo_id, usuario_id, articulo_id),
        )
    else:
        cur.execute(
            "SELECT id, cantidad FROM pedidos_compra WHERE ciclo_id = %s AND usuario_id = %s AND articulo_libre = %s",
            (ciclo_id, usuario_id, articulo_libre),
        )
    existente = cur.fetchone()

    if existente:
        cur.execute("UPDATE pedidos_compra SET cantidad = %s WHERE id = %s",
                     (existente["cantidad"] + cantidad, existente["id"]))
    else:
        cur.execute(
            """INSERT INTO pedidos_compra (ciclo_id, articulo_id, usuario_id, cantidad, sucursal_id, notas, articulo_libre, creado_en)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (ciclo_id, articulo_id, usuario_id, cantidad, sucursal_id, notas, articulo_libre, now),
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
    """Igual que _next_folio: usa el número MÁS ALTO ya usado en esa sucursal,
    no un conteo — para que no se repita un folio si se borró alguna reparación."""
    prefijo = sucursal["prefijo"]
    cur.execute("SELECT folio FROM reparaciones WHERE empresa_id = %s AND sucursal_id = %s",
                (empresa_id, sucursal["id"]))
    maximo = 0
    for row in cur.fetchall():
        folio = row["folio"] or ""
        if folio.startswith(prefijo):
            try:
                maximo = max(maximo, int(folio[len(prefijo):]))
            except (ValueError, TypeError):
                continue
    return f"{prefijo}{maximo + 1}"


def _reparacion_query_base():
    return """
        SELECT r.*, t.estado AS ticket_estado, t.prioridad AS ticket_prioridad,
               t.asignado_a_id, ua.nombre_completo AS tecnico_nombre,
               uc.nombre_completo AS creado_por_nombre,
               s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,
               ur.nombre_completo AS responsable_diagnostico_nombre, ur.puesto AS responsable_diagnostico_puesto,
               usal.nombre_completo AS firma_salida_por_nombre, uing.nombre_completo AS firma_ingreso_por_nombre,
               ucho.nombre_completo AS firma_chofer_por_nombre
        FROM reparaciones r
        LEFT JOIN tickets t ON t.id = r.ticket_id
        LEFT JOIN users ua ON ua.id = t.asignado_a_id
        LEFT JOIN sucursales_reparacion s ON s.id = r.sucursal_id
        LEFT JOIN users ur ON ur.id = r.responsable_diagnostico_id
        LEFT JOIN users usal ON usal.id = r.firma_salida_por_id
        LEFT JOIN users uing ON uing.id = r.firma_ingreso_por_id
        LEFT JOIN users ucho ON ucho.id = r.firma_chofer_por_id
        JOIN users uc ON uc.id = r.creado_por_id
    """


def _enriquecer_reparacion(cur, rep):
    cur.execute("SELECT * FROM reparacion_items_costo WHERE reparacion_id = %s ORDER BY id", (rep["id"],))
    items = [dict(r) for r in cur.fetchall()]
    rep["items_costo"] = items
    rep["costo_refacciones_servicio"] = sum(i["cantidad"] * i["costo"] for i in items)
    rep["costo_total"] = round(rep["costo_refacciones_servicio"] + (rep.get("costo_paqueteria") or 0), 2)

    if rep.get("fecha_recepcion") and rep["estado"] not in ("entregado", "cancelado"):
        try:
            dias = (ahora() - datetime.fromisoformat(rep["fecha_recepcion"])).days
            rep["dias_transcurridos"] = dias
        except (ValueError, TypeError):
            # Una fecha mal formada (ej. de una importación vieja desde Excel)
            # no debe tronar el listado COMPLETO de reparaciones — solo se
            # omite el cálculo de días para esta fila en particular.
            rep["dias_transcurridos"] = None
    else:
        rep["dias_transcurridos"] = None

    try:
        rep["alerta_reparacion_interna"] = (
            rep["estado"] in ("en_reparacion", "control_calidad")
            and rep.get("fecha_autorizacion") is not None
            and (ahora() - datetime.fromisoformat(rep["fecha_autorizacion"])).days > 7
        )
    except (ValueError, TypeError):
        rep["alerta_reparacion_interna"] = False
    try:
        rep["alerta_proveedor"] = (
            rep["estado"] == "con_proveedor"
            and rep.get("fecha_envio_proveedor") is not None
            and (ahora() - datetime.fromisoformat(rep["fecha_envio_proveedor"])).days > 20
        )
    except (ValueError, TypeError):
        rep["alerta_proveedor"] = False
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
                      equipo, marca, modelo, numero_serie, fecha_adquisicion, folio_adquisicion, garantia,
                      falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
                      departamento, categoria, creado_por_id, foto_estado_base64=None,
                      foto_estado_nombre=None, prioridad="media"):
    """Crea la Orden de Servicio (reparación) Y su ticket vinculado en el tablero principal."""
    sucursal = obtener_sucursal_reparacion(empresa_id, sucursal_id)
    if not sucursal:
        return None

    descripcion_ticket = f"[Reparación {sucursal['prefijo']}] {equipo or 'Equipo'} — {cliente_nombre}. Falla: {falla_reportada or 'sin especificar'}"
    ticket = crear_ticket(empresa_id, departamento, descripcion_ticket, categoria, prioridad or "media", creado_por_id)

    conn = get_connection()
    cur = conn.cursor()
    folio = _next_folio_reparacion(cur, empresa_id, sucursal)
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO reparaciones
           (empresa_id, folio, sucursal_id, cliente_nombre, cliente_telefono, asesor_recibe,
            equipo, marca, modelo, numero_serie, fecha_adquisicion, folio_adquisicion, garantia,
            falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
            estado, fecha_recepcion, ticket_id, creado_por_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   'nueva', %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, folio, sucursal_id, cliente_nombre, cliente_telefono, asesor_recibe,
         equipo, marca, modelo, numero_serie, fecha_adquisicion, folio_adquisicion, garantia,
         falla_reportada, estado_fisico, accesorios_entregados, firma_recepcion,
         now, ticket["id"], creado_por_id, now, now),
    )
    reparacion_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()

    if foto_estado_base64:
        agregar_evidencia_reparacion(reparacion_id, "ingreso", foto_estado_base64, foto_estado_nombre, creado_por_id)

    return obtener_reparacion(empresa_id, reparacion_id)


_CAMPOS_RECEPCION_REPARACION = [
    # Datos que la sucursal captura al crear la orden — el técnico NO puede tocarlos,
    # solo el administrador (ej. si hubo un error de captura real).
    "folio_microsip", "cliente_nombre", "cliente_telefono", "asesor_recibe", "equipo", "marca", "modelo",
    "numero_serie", "fecha_adquisicion", "folio_adquisicion", "garantia", "falla_reportada", "estado_fisico",
    "accesorios_entregados",
]
_CAMPOS_TECNICO_REPARACION = [
    # Todo lo relacionado con el trabajo de reparación en sí — esto sí lo llena el técnico.
    "diagnostico", "autorizacion_precio", "autorizacion_medio", "fecha_autorizacion",
    "folio_solicitud_traspaso", "costo_paqueteria", "conclusion", "recomendaciones",
    "responsable_diagnostico_id", "fecha_envio_proveedor", "fecha_entrega", "observaciones_entrega",
    "firma_entrega",
]
_CAMPOS_EDITABLES_REPARACION = _CAMPOS_RECEPCION_REPARACION + _CAMPOS_TECNICO_REPARACION


def actualizar_reparacion(empresa_id, reparacion_id, campos_permitidos=None, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = campos_permitidos if campos_permitidos is not None else _CAMPOS_EDITABLES_REPARACION
    campos, valores = [], []
    for k in permitidos:
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


def firmar_salida_reparacion(empresa_id, reparacion_id, usuario_id, firma_base64):
    """Firma de quien envía el equipo de vuelta a la sucursal (el técnico o quien
    cierra el trabajo) — deja constancia y avanza el estado a 'envio_sucursal'."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE reparaciones
        SET firma_salida = %s, firma_salida_por_id = %s, firma_salida_en = %s
        WHERE id = %s AND empresa_id = %s
    """, (firma_base64, usuario_id, now, reparacion_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    cambiar_estado_reparacion(empresa_id, reparacion_id, "envio_sucursal")


def firmar_chofer_reparacion(empresa_id, reparacion_id, usuario_id, chofer_nombre, firma_base64):
    """Firma del CHOFER que recoge el equipo para llevarlo a la sucursal — deja
    constancia de quién se lo llevó y avanza el estado a 'en_traslado'. Solo
    aplica después de la firma de salida (el equipo ya tiene que estar listo
    para que alguien pase por él)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE reparaciones
        SET chofer_nombre = %s, firma_chofer = %s, firma_chofer_por_id = %s, firma_chofer_en = %s
        WHERE id = %s AND empresa_id = %s
    """, (chofer_nombre, firma_base64, usuario_id, now, reparacion_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    cambiar_estado_reparacion(empresa_id, reparacion_id, "en_traslado")


def firmar_ingreso_reparacion(empresa_id, reparacion_id, usuario_id, firma_base64):
    """Firma del encargado de almacén que RECIBE el equipo en su sucursal — avanza el
    estado a 'listo_entrega'. La validación de que el usuario pertenezca a la sucursal
    correcta (mismo folio), y de que ya esté 'en_traslado', se hace en la capa de la
    API, antes de llamar esta función."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE reparaciones
        SET firma_ingreso_sucursal = %s, firma_ingreso_por_id = %s, firma_ingreso_en = %s
        WHERE id = %s AND empresa_id = %s
    """, (firma_base64, usuario_id, now, reparacion_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    cambiar_estado_reparacion(empresa_id, reparacion_id, "listo_entrega")


def agregar_item_costo(reparacion_id, articulo, cantidad, codigo, costo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reparacion_items_costo (reparacion_id, articulo, cantidad, codigo, costo) VALUES (%s, %s, %s, %s, %s)",
        (reparacion_id, articulo, cantidad, codigo, costo),
    )
    conn.commit()
    cur.close(); conn.close()


def obtener_reparacion_id_de_item_costo(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT reparacion_id FROM reparacion_items_costo WHERE id = %s", (item_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row["reparacion_id"] if row else None


def eliminar_item_costo(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reparacion_items_costo WHERE id = %s", (item_id,))
    conn.commit()
    cur.close(); conn.close()


def folios_reparacion_existentes(empresa_id):
    """Set de todos los folios ya usados en esta empresa — para detectar
    duplicados antes de importar un lote desde Excel."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT folio FROM reparaciones WHERE empresa_id = %s", (empresa_id,))
    folios = {r["folio"] for r in cur.fetchall()}
    cur.close(); conn.close()
    return folios


def importar_reparaciones_lote(empresa_id, filas, creado_por_id):
    """Inserta un lote de reparaciones históricas (ej. desde un Excel viejo)
    directo a la tabla, SIN crear ticket ni pedir firma — a diferencia de
    crear_reparacion(), pensada para reparaciones nuevas del día a día.
    Cada fila en `filas` es un dict con: folio, sucursal_id, cliente_nombre,
    cliente_telefono, equipo, marca, modelo, numero_serie, garantia,
    falla_reportada, diagnostico, folio_solicitud_traspaso, costo_paqueteria,
    autorizacion_precio, estado, fecha_recepcion, fecha_entrega,
    items_costo (lista de {articulo, costo}).
    Regresa (importadas, omitidas_duplicadas) — folios ya existentes se
    omiten en vez de tronar toda la importación."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    importadas = 0
    omitidas = []

    try:
        for fila in filas:
            cur.execute(
                "SELECT 1 FROM reparaciones WHERE empresa_id = %s AND folio = %s",
                (empresa_id, fila["folio"]),
            )
            if cur.fetchone():
                omitidas.append(fila["folio"])
                continue

            cur.execute(
                """INSERT INTO reparaciones
                   (empresa_id, folio, sucursal_id, cliente_nombre, cliente_telefono, equipo,
                    marca, modelo, numero_serie, garantia, falla_reportada, diagnostico,
                    folio_solicitud_traspaso, costo_paqueteria, autorizacion_precio,
                    estado, fecha_recepcion, fecha_entrega, creado_por_id, creado_en, actualizado_en)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (empresa_id, fila["folio"], fila.get("sucursal_id"), fila["cliente_nombre"],
                 fila.get("cliente_telefono"), fila.get("equipo"), fila.get("marca"), fila.get("modelo"),
                 fila.get("numero_serie"), bool(fila.get("garantia")), fila.get("falla_reportada"),
                 fila.get("diagnostico"), fila.get("folio_solicitud_traspaso"),
                 fila.get("costo_paqueteria", 0), fila.get("autorizacion_precio"),
                 fila.get("estado", "entregado"), fila.get("fecha_recepcion"), fila.get("fecha_entrega"),
                 creado_por_id, fila.get("fecha_recepcion") or now, now),
            )
            reparacion_id = cur.fetchone()["id"]

            for item in fila.get("items_costo", []):
                if item.get("costo"):
                    cur.execute(
                        "INSERT INTO reparacion_items_costo (reparacion_id, articulo, cantidad, costo) VALUES (%s, %s, 1, %s)",
                        (reparacion_id, item["articulo"], item["costo"]),
                    )
            importadas += 1

        conn.commit()
        return importadas, omitidas
    except Exception as e:
        conn.rollback()
        raise Exception(f"falló en el folio '{fila.get('folio', '?')}': {e}") from e
    finally:
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


def agregar_actualizacion_entrega(entrega_id, autor_id, texto):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO entrega_actualizaciones (entrega_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (entrega_id, autor_id, texto, now),
    )
    cur.execute("UPDATE entregas SET actualizado_en = %s WHERE id = %s", (now, entrega_id))
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


# ==================== RECURSOS HUMANOS (incidencias) ====================

def crear_incidencia_rh(empresa_id, usuario_id, tipo, fecha_inicio, fecha_fin=None, motivo=None, foto_base64=None, horas=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    # Si la persona tiene una sucursal asignada Y esa sucursal tiene a alguien
    # con el rol "encargado_sucursal", la incidencia primero espera SU firma de
    # aceptación. Si no hay nadie así (sucursal sin encargado, o la persona no
    # tiene sucursal), pasa directo a RH como antes — para que nunca se quede
    # atorada sin nadie que la pueda mover.
    cur.execute("SELECT sucursal_id FROM users WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    mi_sucursal_id = row["sucursal_id"] if row else None
    estado_inicial = "pendiente"
    if mi_sucursal_id:
        cur.execute(
            "SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE LIMIT 1",
            (empresa_id, mi_sucursal_id),
        )
        if cur.fetchone():
            estado_inicial = "pendiente_encargado"
    cur.execute(
        """INSERT INTO incidencias_rh (empresa_id, usuario_id, tipo, fecha_inicio, fecha_fin, motivo, foto_base64,
                                        horas, estado, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, usuario_id, tipo, fecha_inicio, fecha_fin, motivo, foto_base64, horas, estado_inicial, now),
    )
    incidencia_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return incidencia_id


def aceptar_incidencia_encargado(empresa_id, incidencia_id, encargado_id, firma_base64):
    """El encargado de sucursal firma para aceptar la incidencia — pasa a
    'pendiente' para que ahora sí la vea RH. Regresa False si no estaba en el
    estado correcto (ya se adelantaron, o ya la resolvió alguien más)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE incidencias_rh SET estado = 'pendiente', firma_encargado_base64 = %s,
                                      firma_encargado_en = %s, firma_encargado_por_id = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente_encargado'""",
        (firma_base64, now, encargado_id, incidencia_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def listar_incidencias_pendientes_encargado(empresa_id, sucursal_id):
    """Incidencias de la sucursal de este encargado, esperando su firma."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.*, u.nombre_completo AS usuario_nombre, u.puesto AS usuario_puesto
        FROM incidencias_rh i
        JOIN users u ON u.id = i.usuario_id
        WHERE i.empresa_id = %s AND i.estado = 'pendiente_encargado' AND u.sucursal_id = %s
        ORDER BY i.creado_en ASC
    """, (empresa_id, sucursal_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def listar_incidencias_rh(empresa_id, usuario_id=None, estado=None):
    """usuario_id=None -> las ve todas (vista de administrador); si se manda, solo las de esa persona."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT i.*, u.nombre_completo AS usuario_nombre, u.puesto AS usuario_puesto,
               r.nombre_completo AS resuelto_por_nombre
        FROM incidencias_rh i
        JOIN users u ON u.id = i.usuario_id
        LEFT JOIN users r ON r.id = i.resuelto_por_id
        WHERE i.empresa_id = %s
    """
    params = [empresa_id]
    if usuario_id:
        query += " AND i.usuario_id = %s"; params.append(usuario_id)
    if estado:
        query += " AND i.estado = %s"; params.append(estado)
    query += " ORDER BY i.creado_en DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_incidencia_rh(empresa_id, incidencia_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.*, u.nombre_completo AS usuario_nombre, u.puesto AS usuario_puesto, u.telefono_whatsapp AS usuario_telefono,
               r.nombre_completo AS resuelto_por_nombre
        FROM incidencias_rh i
        JOIN users u ON u.id = i.usuario_id
        LEFT JOIN users r ON r.id = i.resuelto_por_id
        WHERE i.id = %s AND i.empresa_id = %s
    """, (incidencia_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def resolver_incidencia_rh(empresa_id, incidencia_id, admin_id, estado, respuesta_admin=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE incidencias_rh
        SET estado = %s, respuesta_admin = %s, resuelto_por_id = %s, resuelto_en = %s
        WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'
    """, (estado, respuesta_admin, admin_id, now, incidencia_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()

    if filas > 0 and estado == "aprobada":
        incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)
        es_conversion_automatica = incidencia and incidencia.get("motivo") and incidencia["motivo"].startswith("Generado automáticamente")
        if incidencia and incidencia["tipo"] == "dia_libre_sin_goce" and incidencia.get("horas"):
            if es_conversion_automatica:
                # Este NO es un permiso pedido de más — es la conversión de horas
                # que YA debía, que el propio empleado aceptó y la encargada ya
                # autorizó. Aquí se registra como PAGO (para que baje su adeudo),
                # nunca como un adeudo nuevo — si no, se le duplicaría la deuda.
                registrar_movimiento_horas_rh(
                    empresa_id, incidencia["usuario_id"], "pago", incidencia["horas"],
                    notas=f"Día sin goce de sueldo #{incidencia_id} — aceptado por el empleado y autorizado por su encargada.",
                    incidencia_id=incidencia_id, registrado_por_id=admin_id,
                )
            else:
                # Un permiso SIN GOCE DE SUELDO normal, pedido por la persona — si
                # se pidió por horas, genera el adeudo correspondiente.
                registrar_movimiento_horas_rh(
                    empresa_id, incidencia["usuario_id"], "debe", incidencia["horas"],
                    notas=f"Generado automáticamente al aprobar la incidencia #{incidencia_id}",
                    incidencia_id=incidencia_id, registrado_por_id=admin_id,
                )
    return filas > 0


def registrar_movimiento_horas_rh(empresa_id, usuario_id, tipo, horas, notas=None, incidencia_id=None,
                                   registrado_por_id=None, estado="aprobado", fecha=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO horas_rh_movimientos (empresa_id, usuario_id, incidencia_id, tipo, horas, notas,
                                               registrado_por_id, creado_en, estado, fecha)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, usuario_id, incidencia_id, tipo, horas, notas, registrado_por_id, now, estado,
         fecha or now[:10]),
    )
    movimiento_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    if tipo == "debe" and estado == "aprobado":
        # Cada vez que se agrega (o se aprueba) un adeudo, revisamos si ya se
        # juntaron 8 horas o más sin pagar — si es así, se le OFRECE al
        # empleado convertirlo en un día sin goce (ver la función de abajo;
        # ya no se hace solo, necesita que el empleado acepte primero).
        _ofrecer_conversion_dia_sin_goce(empresa_id, usuario_id)
    return movimiento_id


def _ofrecer_conversion_dia_sin_goce(empresa_id, usuario_id):
    """Si el saldo de horas a deber de esta persona llega a 8 o más, se le
    OFRECE convertirlo en un día sin goce de sueldo — queda en estado
    'propuesta_empleado' hasta que la persona responda que sí o que no.
    Si ya tiene una propuesta sin resolver, no se le manda otra encima."""
    saldo = saldo_horas_usuario(empresa_id, usuario_id)
    if saldo["saldo"] < 8:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 AS x FROM incidencias_rh
        WHERE empresa_id = %s AND usuario_id = %s AND tipo = 'dia_libre_sin_goce'
              AND motivo LIKE 'Generado automáticamente%%'
              AND estado IN ('propuesta_empleado', 'pendiente_encargado', 'pendiente')
        LIMIT 1
    """, (empresa_id, usuario_id))
    ya_tiene_propuesta = cur.fetchone() is not None
    if ya_tiene_propuesta:
        cur.close(); conn.close()
        return
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO incidencias_rh (empresa_id, usuario_id, tipo, fecha_inicio, motivo, horas, estado, creado_en)
           VALUES (%s, %s, 'dia_libre_sin_goce', %s, %s, 8, 'propuesta_empleado', %s)""",
        (empresa_id, usuario_id, now[:10],
         "Generado automáticamente: se acumularon 8 horas a deber sin pagar.", now),
    )
    conn.commit()
    cur.close(); conn.close()


def responder_propuesta_dia_sin_goce(empresa_id, incidencia_id, usuario_id, acepta):
    """El empleado responde si acepta o no que sus 8 horas acumuladas se
    conviertan en un día sin goce de sueldo. Si acepta, pasa a que la
    encargada de su sucursal lo autorice (o directo a RH si no tiene
    encargada asignada) — si no acepta, queda rechazada y su deuda sigue
    tal cual, sin convertirse en nada."""
    incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)
    if not incidencia or incidencia["usuario_id"] != usuario_id or incidencia["estado"] != "propuesta_empleado":
        return False
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    if not acepta:
        cur.execute(
            "UPDATE incidencias_rh SET estado = 'rechazada', respuesta_admin = %s, resuelto_en = %s WHERE id = %s",
            ("El empleado no aceptó convertir sus horas acumuladas en un día sin goce.", now, incidencia_id),
        )
        conn.commit()
        cur.close(); conn.close()
        return True
    cur.execute("SELECT sucursal_id FROM users WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    mi_sucursal_id = row["sucursal_id"] if row else None
    tiene_encargado = False
    if mi_sucursal_id:
        cur.execute(
            "SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE LIMIT 1",
            (empresa_id, mi_sucursal_id),
        )
        tiene_encargado = cur.fetchone() is not None
    nuevo_estado = "pendiente_encargado" if tiene_encargado else "pendiente"
    cur.execute("UPDATE incidencias_rh SET estado = %s WHERE id = %s", (nuevo_estado, incidencia_id))
    conn.commit()
    cur.close(); conn.close()
    return True


def listar_propuestas_dia_sin_goce_pendientes(empresa_id, usuario_id):
    """Propuestas de conversión de horas que le tocan responder a esta
    persona (sí/no) — para mostrárselo en 'Mis incidencias' o 'Mis tareas'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, horas, motivo, creado_en FROM incidencias_rh
        WHERE empresa_id = %s AND usuario_id = %s AND tipo = 'dia_libre_sin_goce'
              AND estado = 'propuesta_empleado'
        ORDER BY creado_en DESC
    """, (empresa_id, usuario_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def solicitar_pago_horas_empleado(empresa_id, usuario_id, fecha, horas, motivo):
    """El empleado registra que 'pagó' horas (ej. se quedó tiempo extra, o
    trabajó parte de su comida) — queda PENDIENTE hasta que el encargado de
    su sucursal lo autorice; no cuenta en su saldo todavía."""
    return registrar_movimiento_horas_rh(empresa_id, usuario_id, "pago", horas, notas=motivo,
                                          estado="pendiente", fecha=fecha)


def listar_pagos_horas_pendientes_encargado(empresa_id, sucursal_id):
    """Pagos de horas de la gente de esta sucursal, esperando la firma del
    encargado antes de que cuenten en el saldo de nadie."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, u.nombre_completo AS usuario_nombre, u.puesto AS usuario_puesto
        FROM horas_rh_movimientos m
        JOIN users u ON u.id = m.usuario_id
        WHERE m.empresa_id = %s AND m.estado = 'pendiente' AND m.tipo = 'pago' AND u.sucursal_id = %s
        ORDER BY m.creado_en ASC
    """, (empresa_id, sucursal_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def aprobar_pago_horas(empresa_id, movimiento_id, encargado_id, firma_base64):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE horas_rh_movimientos SET estado = 'aprobado', firma_aprobacion_base64 = %s,
                                             aprobado_por_id = %s, aprobado_en = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'""",
        (firma_base64, encargado_id, now, movimiento_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def rechazar_pago_horas(empresa_id, movimiento_id, encargado_id, motivo=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE horas_rh_movimientos SET estado = 'rechazado', motivo_rechazo = %s,
                                             aprobado_por_id = %s, aprobado_en = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'""",
        (motivo, encargado_id, now, movimiento_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def listar_movimientos_horas_rh(empresa_id, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, r.nombre_completo AS registrado_por_nombre, a.nombre_completo AS aprobado_por_nombre
        FROM horas_rh_movimientos m
        LEFT JOIN users r ON r.id = m.registrado_por_id
        LEFT JOIN users a ON a.id = m.aprobado_por_id
        WHERE m.empresa_id = %s AND m.usuario_id = %s
        ORDER BY m.creado_en DESC
    """, (empresa_id, usuario_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def eliminar_movimiento_horas_rh(empresa_id, movimiento_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM horas_rh_movimientos WHERE id = %s AND empresa_id = %s", (movimiento_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def obtener_movimiento_horas_rh(empresa_id, movimiento_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM horas_rh_movimientos WHERE id = %s AND empresa_id = %s", (movimiento_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def listar_saldos_horas_sucursal(empresa_id, sucursal_id):
    """Igual que listar_saldos_horas_todos, pero solo de la gente de una
    sucursal — para que el encargado sepa quién le debe horas."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id AS usuario_id, u.nombre_completo, u.puesto,
               COALESCE(SUM(CASE WHEN m.tipo = 'debe' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS debe_total,
               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total
        FROM users u
        LEFT JOIN horas_rh_movimientos m ON m.usuario_id = u.id
        WHERE u.empresa_id = %s AND u.sucursal_id = %s AND u.activo = TRUE AND u.rol NOT IN ('encargado_sucursal', 'almacen', 'master')
        GROUP BY u.id, u.nombre_completo, u.puesto
        ORDER BY u.nombre_completo
    """, (empresa_id, sucursal_id))
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["saldo"] = round(r["debe_total"] - r["pagado_total"], 2)
    cur.close(); conn.close()
    return rows


def saldo_horas_usuario(empresa_id, usuario_id):
    """Cuántas horas debe (o ya pagó) un empleado en total — solo cuenta lo
    ya APROBADO; lo que sigue pendiente de firma del encargado no cuenta
    todavía en el saldo."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(horas), 0) AS total FROM horas_rh_movimientos WHERE empresa_id = %s AND usuario_id = %s AND tipo = 'debe' AND estado = 'aprobado'",
        (empresa_id, usuario_id),
    )
    debe_total = cur.fetchone()["total"]
    cur.execute(
        "SELECT COALESCE(SUM(horas), 0) AS total FROM horas_rh_movimientos WHERE empresa_id = %s AND usuario_id = %s AND tipo = 'pago' AND estado = 'aprobado'",
        (empresa_id, usuario_id),
    )
    pagado_total = cur.fetchone()["total"]
    cur.close(); conn.close()
    return {"debe_total": debe_total, "pagado_total": pagado_total, "saldo": round(debe_total - pagado_total, 2)}


def listar_saldos_horas_todos(empresa_id):
    """Resumen del saldo de horas de todos los empleados que tengan al menos un
    movimiento APROBADO — para la vista general del administrador."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id AS usuario_id, u.nombre_completo, u.puesto,
               COALESCE(SUM(CASE WHEN m.tipo = 'debe' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS debe_total,
               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total
        FROM users u
        JOIN horas_rh_movimientos m ON m.usuario_id = u.id
        WHERE u.empresa_id = %s
        GROUP BY u.id, u.nombre_completo, u.puesto
        ORDER BY u.nombre_completo
    """, (empresa_id,))
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["saldo"] = round(r["debe_total"] - r["pagado_total"], 2)
    cur.close(); conn.close()
    return rows


def eliminar_incidencia_rh(empresa_id, incidencia_id, usuario_id, es_admin, es_encargado_de_esa_persona=False):
    """Un empleado solo puede borrar su propia incidencia mientras siga
    pendiente; el admin puede borrar cualquiera; y la encargada de sucursal
    puede borrar (por si se equivocaron) cualquiera de su gente MIENTRAS
    siga esperando su firma — una vez que ya pasó a RH, ya no es su decisión."""
    conn = get_connection()
    cur = conn.cursor()
    if es_admin:
        cur.execute("DELETE FROM incidencias_rh WHERE id = %s AND empresa_id = %s", (incidencia_id, empresa_id))
    elif es_encargado_de_esa_persona:
        cur.execute(
            "DELETE FROM incidencias_rh WHERE id = %s AND empresa_id = %s AND estado = 'pendiente_encargado'",
            (incidencia_id, empresa_id),
        )
    else:
        cur.execute(
            "DELETE FROM incidencias_rh WHERE id = %s AND empresa_id = %s AND usuario_id = %s AND estado = 'pendiente'",
            (incidencia_id, empresa_id, usuario_id),
        )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


def editar_incidencia_rh(empresa_id, incidencia_id, tipo=None, fecha_inicio=None, fecha_fin=None, motivo=None, horas=None):
    """Para que la encargada (o el administrador) puedan corregir una
    incidencia que se capturó mal — solo mientras siga esperando su firma
    (o, para el admin, en cualquier momento). El endpoint de arriba decide
    quién tiene permiso; esta función solo aplica el cambio."""
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if tipo is not None:
        campos.append("tipo = %s"); valores.append(tipo)
    if fecha_inicio is not None:
        campos.append("fecha_inicio = %s"); valores.append(fecha_inicio)
    if fecha_fin is not None:
        campos.append("fecha_fin = %s"); valores.append(fecha_fin if fecha_fin else None)
    if motivo is not None:
        campos.append("motivo = %s"); valores.append(motivo)
    if horas is not None:
        campos.append("horas = %s"); valores.append(horas if horas > 0 else None)
    if not campos:
        cur.close(); conn.close()
        return obtener_incidencia_rh(empresa_id, incidencia_id)
    valores += [incidencia_id, empresa_id]
    cur.execute(f"UPDATE incidencias_rh SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
    conn.commit()
    cur.close(); conn.close()
    return obtener_incidencia_rh(empresa_id, incidencia_id)


def agregar_actualizacion_curso(curso_id, autor_id, texto):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (curso_id, autor_id, texto, now),
    )
    conn.commit()
    cur.close(); conn.close()


def crear_curso_rh(empresa_id, nombre, descripcion, puesto_objetivo, dias_duracion, fecha_limite, creado_por_id):
    """Crea el curso y, si se indicó un puesto_objetivo, agrega automáticamente
    como participantes a todas las personas ACTIVAS que ya tengan ese mismo
    puesto capturado en su perfil (Administrar → Usuarios)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    puesto_limpio = (puesto_objetivo or "").strip() or None
    cur.execute(
        """INSERT INTO cursos_rh (empresa_id, nombre, descripcion, puesto_objetivo, dias_duracion, fecha_limite,
                                   creado_por_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, nombre.strip(), (descripcion or "").strip() or None, puesto_limpio, dias_duracion,
         fecha_limite, creado_por_id, now, now),
    )
    curso_id = cur.fetchone()["id"]

    cur.execute(
        "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (curso_id, creado_por_id, "Se creó el curso.", now),
    )

    if puesto_limpio:
        cur.execute(
            "SELECT id, nombre_completo FROM users WHERE empresa_id = %s AND activo = TRUE AND TRIM(LOWER(puesto)) = TRIM(LOWER(%s))",
            (empresa_id, puesto_limpio),
        )
        agregados = cur.fetchall()
        for row in agregados:
            cur.execute(
                """INSERT INTO curso_participantes (curso_id, usuario_id, agregado_automaticamente, agregado_en)
                   VALUES (%s, %s, TRUE, %s) ON CONFLICT DO NOTHING""",
                (curso_id, row["id"], now),
            )
        if agregados:
            nombres = ", ".join(r["nombre_completo"] for r in agregados)
            cur.execute(
                "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
                (curso_id, creado_por_id, f"Se asignó automáticamente por el puesto '{puesto_limpio}' a: {nombres}.", now),
            )
    conn.commit()
    cur.close(); conn.close()
    return curso_id


def listar_cursos_rh(empresa_id):
    """Para el administrador: todos los cursos de la empresa, con el conteo
    de participantes y cuántos ya lo completaron."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.nombre, c.descripcion, c.puesto_objetivo, c.dias_duracion, c.fecha_limite, c.creado_en,
               uc.nombre_completo AS creado_por_nombre,
               COUNT(DISTINCT cp.usuario_id) AS total_participantes,
               COUNT(DISTINCT cf.usuario_id) AS total_completados
        FROM cursos_rh c
        JOIN users uc ON uc.id = c.creado_por_id
        LEFT JOIN curso_participantes cp ON cp.curso_id = c.id
        LEFT JOIN curso_firmas cf ON cf.curso_id = c.id AND cf.usuario_id = cp.usuario_id
        WHERE c.empresa_id = %s
        GROUP BY c.id, uc.nombre_completo
        ORDER BY c.creado_en DESC
    """, (empresa_id,))
    return [dict(r) for r in cur.fetchall()]


def obtener_curso_rh(empresa_id, curso_id):
    """Detalle completo de un curso: datos generales + la lista de
    participantes con su estatus de firma (completado o pendiente) + su
    bitácora completa de movimientos."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, uc.nombre_completo AS creado_por_nombre
        FROM cursos_rh c JOIN users uc ON uc.id = c.creado_por_id
        WHERE c.id = %s AND c.empresa_id = %s
    """, (curso_id, empresa_id))
    curso = cur.fetchone()
    if not curso:
        cur.close(); conn.close()
        return None
    curso = dict(curso)

    cur.execute("""
        SELECT u.id AS usuario_id, u.nombre_completo, u.puesto, cp.agregado_automaticamente, cp.agregado_en,
               cf.completado_en, cf.firma_base64, cf.evidencia_base64, cf.evidencia_nombre
        FROM curso_participantes cp
        JOIN users u ON u.id = cp.usuario_id
        LEFT JOIN curso_firmas cf ON cf.curso_id = cp.curso_id AND cf.usuario_id = cp.usuario_id
        WHERE cp.curso_id = %s
        ORDER BY u.nombre_completo
    """, (curso_id,))
    curso["participantes"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT cb.texto, cb.creado_en, ua.nombre_completo AS autor_nombre
        FROM curso_bitacora cb
        LEFT JOIN users ua ON ua.id = cb.autor_id
        WHERE cb.curso_id = %s
        ORDER BY cb.creado_en ASC
    """, (curso_id,))
    curso["bitacora"] = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()
    return curso


def agregar_participante_curso(curso_id, usuario_id, autor_id=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO curso_participantes (curso_id, usuario_id, agregado_automaticamente, agregado_en)
           VALUES (%s, %s, FALSE, %s) ON CONFLICT DO NOTHING""",
        (curso_id, usuario_id, now),
    )
    cur.execute("SELECT nombre_completo FROM users WHERE id = %s", (usuario_id,))
    persona = cur.fetchone()
    nombre_persona = persona["nombre_completo"] if persona else "alguien"
    cur.execute(
        "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (curso_id, autor_id, f"Se agregó a {nombre_persona} al curso.", now),
    )
    conn.commit()
    cur.close(); conn.close()


def quitar_participante_curso(curso_id, usuario_id, autor_id=None):
    """No deja quitar a alguien que YA completó el curso — eso es historial,
    no se borra. Regresa False en ese caso para que la API avise por qué."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 AS x FROM curso_firmas WHERE curso_id = %s AND usuario_id = %s", (curso_id, usuario_id))
    if cur.fetchone():
        cur.close(); conn.close()
        return False
    cur.execute("SELECT nombre_completo FROM users WHERE id = %s", (usuario_id,))
    persona = cur.fetchone()
    nombre_persona = persona["nombre_completo"] if persona else "alguien"
    cur.execute("DELETE FROM curso_participantes WHERE curso_id = %s AND usuario_id = %s", (curso_id, usuario_id))
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (curso_id, autor_id, f"Se quitó a {nombre_persona} del curso.", now),
    )
    conn.commit()
    cur.close(); conn.close()
    return True


def firmar_curso_rh(curso_id, usuario_id, firma_base64, evidencia_base64, evidencia_nombre):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("SELECT 1 AS x FROM curso_firmas WHERE curso_id = %s AND usuario_id = %s", (curso_id, usuario_id))
    ya_existia = bool(cur.fetchone())
    cur.execute(
        """INSERT INTO curso_firmas (curso_id, usuario_id, firma_base64, completado_en, evidencia_base64, evidencia_nombre)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (curso_id, usuario_id) DO UPDATE
           SET firma_base64 = %s, completado_en = %s, evidencia_base64 = %s, evidencia_nombre = %s""",
        (curso_id, usuario_id, firma_base64, now, evidencia_base64, evidencia_nombre,
         firma_base64, now, evidencia_base64, evidencia_nombre),
    )
    cur.execute("SELECT nombre_completo FROM users WHERE id = %s", (usuario_id,))
    persona = cur.fetchone()
    nombre_persona = persona["nombre_completo"] if persona else "alguien"
    texto = f"{nombre_persona} corrigió su firma/evidencia del curso." if ya_existia else f"{nombre_persona} completó el curso y adjuntó su evidencia."
    cur.execute(
        "INSERT INTO curso_bitacora (curso_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (curso_id, usuario_id, texto, now),
    )
    conn.commit()
    cur.close(); conn.close()


def es_participante_curso(curso_id, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 AS x FROM curso_participantes WHERE curso_id = %s AND usuario_id = %s", (curso_id, usuario_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return bool(row)


def listar_cursos_usuario(empresa_id, usuario_id):
    """Para 'Mis cursos': los cursos asignados a esta persona, con su propio
    estatus (completado o pendiente) — es lo mismo que se usa para el
    historial que revisa RH, nada más que aquí se filtra a un solo usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id AS curso_id, c.nombre, c.descripcion, c.puesto_objetivo, c.creado_en,
               cf.completado_en, cf.firma_base64
        FROM curso_participantes cp
        JOIN cursos_rh c ON c.id = cp.curso_id
        LEFT JOIN curso_firmas cf ON cf.curso_id = cp.curso_id AND cf.usuario_id = cp.usuario_id
        WHERE c.empresa_id = %s AND cp.usuario_id = %s
        ORDER BY (cf.completado_en IS NOT NULL), c.creado_en DESC
    """, (empresa_id, usuario_id))
    return [dict(r) for r in cur.fetchall()]


def eliminar_curso_rh(empresa_id, curso_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cursos_rh WHERE id = %s AND empresa_id = %s", (curso_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


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
    elif tabla_key == "articulos_compra":
        # Los pedidos históricos que apuntaban a estos artículos se quedan (no se
        # borran), solo se desvinculan — si no, la base rechazaría el borrado por
        # integridad referencial. El pedido conserva su cantidad/notas, solo pierde
        # el nombre del artículo (ya no se puede reconstruir si el catálogo se borró).
        cur.execute(
            """UPDATE pedidos_compra SET articulo_id = NULL WHERE articulo_id IN
               (SELECT id FROM articulos_compra WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s)""",
            (empresa_id, desde, hasta),
        )
        cur.execute("DELETE FROM articulos_compra WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s", (empresa_id, desde, hasta))
        eliminados = cur.rowcount
    elif tabla_key == "incidencias_rh":
        # Las incidencias que ya se aprobaron pueden tener un movimiento en el
        # libro de horas apuntando a ellas (ej. un día libre sin goce ya
        # autorizado) — hay que desvincular ese movimiento primero (sin
        # borrarlo, es el registro de horas de la persona) o la base rechaza
        # el borrado por integridad referencial.
        cur.execute(
            """UPDATE horas_rh_movimientos SET incidencia_id = NULL WHERE incidencia_id IN
               (SELECT id FROM incidencias_rh WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s)""",
            (empresa_id, desde, hasta),
        )
        cur.execute("DELETE FROM incidencias_rh WHERE empresa_id = %s AND creado_en >= %s AND creado_en <= %s", (empresa_id, desde, hasta))
        eliminados = cur.rowcount
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


# =============================================================================
# ENTREGAS (módulo de Logística fusionado — entrega de equipos e instalaciones)
# =============================================================================

TRANSICIONES_VALIDAS_ENTREGA = {
    "pendiente": {"asignada", "cancelada"},
    "asignada": {"en_camino", "reagendada", "cancelada"},
    "en_camino": {"en_proceso", "rechazada", "reagendada"},
    "en_proceso": {"entregada", "rechazada", "reagendada"},
    "rechazada": {"reagendada", "cancelada"},
    "reagendada": {"asignada", "en_camino"},
    "entregada": set(),
    "cancelada": set(),
}


def _next_folio_entrega(cur, empresa_id):
    cur.execute("SELECT folio FROM entregas WHERE empresa_id = %s", (empresa_id,))
    maximo = 0
    for row in cur.fetchall():
        try:
            numero = int(row["folio"].split("-")[-1])
            maximo = max(maximo, numero)
        except (ValueError, AttributeError, IndexError, TypeError):
            continue
    return f"ENT-{maximo + 1:04d}"


def _entrega_query_base():
    return """
        SELECT e.*, c.nombre_completo AS creado_por_nombre, v.nombre AS vehiculo_nombre
        FROM entregas e
        JOIN users c ON c.id = e.creado_por_id
        LEFT JOIN vehiculos_entrega v ON v.id = e.vehiculo_id
    """


def _enriquecer_entrega(cur, entrega):
    cur.execute(
        "SELECT * FROM entrega_checklist_items WHERE entrega_id = %s ORDER BY orden",
        (entrega["id"],),
    )
    entrega["checklist_items"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT ei.instalador_id, u.nombre_completo, u.telefono_whatsapp
        FROM entrega_instaladores ei JOIN users u ON u.id = ei.instalador_id
        WHERE ei.entrega_id = %s
    """, (entrega["id"],))
    entrega["instaladores"] = [dict(r) for r in cur.fetchall()]


def listar_entregas(empresa_id, estado=None, instalador_id=None, fecha_desde=None, fecha_hasta=None):
    conn = get_connection()
    cur = conn.cursor()
    query = _entrega_query_base() + " WHERE e.empresa_id = %s"
    params = [empresa_id]
    if estado:
        query += " AND e.estado = %s"; params.append(estado)
    if instalador_id:
        query += " AND EXISTS (SELECT 1 FROM entrega_instaladores ei WHERE ei.entrega_id = e.id AND ei.instalador_id = %s)"
        params.append(instalador_id)
    if fecha_desde:
        query += " AND e.fecha_programada >= %s"; params.append(fecha_desde)
    if fecha_hasta:
        query += " AND e.fecha_programada <= %s"; params.append(fecha_hasta)
    query += " ORDER BY e.fecha_programada NULLS LAST, e.horario NULLS LAST, e.creado_en DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        _enriquecer_entrega(cur, r)
    cur.close(); conn.close()
    return rows


def obtener_entrega(empresa_id, entrega_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(_entrega_query_base() + " WHERE e.id = %s AND e.empresa_id = %s", (entrega_id, empresa_id))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    entrega = dict(row)
    _enriquecer_entrega(cur, entrega)

    cur.execute("""
        SELECT h.*, u.nombre_completo AS usuario_nombre
        FROM entrega_historial h JOIN users u ON u.id = h.usuario_id
        WHERE h.entrega_id = %s ORDER BY h.creado_en ASC
    """, (entrega_id,))
    entrega["historial"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT a.*, u.nombre_completo AS autor_nombre
        FROM entrega_actualizaciones a JOIN users u ON u.id = a.autor_id
        WHERE a.entrega_id = %s ORDER BY a.creado_en ASC
    """, (entrega_id,))
    entrega["bitacora"] = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()
    return entrega


def crear_entrega(empresa_id, cliente_nombre, cliente_direccion, cliente_telefono, equipo_descripcion,
                   creado_por_id, checklist_items=None, folio_pedido_microsip=None, fecha_programada=None,
                   horario=None, vehiculo_id=None, liga_mapa=None, comentarios=None, estatus_pago=None,
                   destino_lat=None, destino_lng=None):
    conn = get_connection()
    cur = conn.cursor()
    folio = _next_folio_entrega(cur, empresa_id)
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO entregas
           (empresa_id, folio, folio_pedido_microsip, cliente_nombre, cliente_direccion, cliente_telefono,
            equipo_descripcion, estado, fecha_programada, horario, vehiculo_id, liga_mapa, comentarios,
            estatus_pago, destino_lat, destino_lng, creado_por_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, folio, folio_pedido_microsip, cliente_nombre, cliente_direccion, cliente_telefono,
         equipo_descripcion, fecha_programada, horario, vehiculo_id, liga_mapa, comentarios, estatus_pago,
         destino_lat, destino_lng, creado_por_id, now, now),
    )
    entrega_id = cur.fetchone()["id"]

    for i, item in enumerate(checklist_items or []):
        cur.execute(
            """INSERT INTO entrega_checklist_items (entrega_id, texto, orden, obligatorio)
               VALUES (%s, %s, %s, %s)""",
            (entrega_id, item["texto"], item.get("orden", i), item.get("obligatorio", True)),
        )

    # Puntos que el administrador marcó como "automático" en la plantilla de
    # checklist (Administrar → Checklist entregas) — se agregan solos a toda
    # entrega nueva, además de los artículos del pedido.
    orden_base = len(checklist_items or [])
    cur.execute(
        "SELECT texto FROM entrega_checklist_plantilla WHERE empresa_id = %s AND automatico = TRUE AND activo = TRUE ORDER BY orden, id",
        (empresa_id,),
    )
    for j, fila in enumerate(cur.fetchall()):
        cur.execute(
            """INSERT INTO entrega_checklist_items (entrega_id, texto, orden, obligatorio)
               VALUES (%s, %s, %s, %s)""",
            (entrega_id, fila["texto"], orden_base + j, True),
        )

    cur.execute(
        """INSERT INTO entrega_historial (entrega_id, estatus_anterior, estatus_nuevo, usuario_id, creado_en)
           VALUES (%s, NULL, 'pendiente', %s, %s)""",
        (entrega_id, creado_por_id, now),
    )
    conn.commit()
    cur.close(); conn.close()
    return obtener_entrega(empresa_id, entrega_id)


def actualizar_entrega(empresa_id, entrega_id, **campos_nuevos):
    permitidos = ["cliente_nombre", "cliente_direccion", "cliente_telefono", "equipo_descripcion", "fecha_programada",
                  "horario", "vehiculo_id", "liga_mapa", "comentarios", "estatus_pago", "confirmado",
                  "destino_lat", "destino_lng"]
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        campos.append("actualizado_en = %s"); valores.append(ahora().isoformat(timespec="seconds"))
        valores += [entrega_id, empresa_id]
        cur.execute(f"UPDATE entregas SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


# ---- Vehículos de entrega (para la agenda) ----

def listar_vehiculos_entrega(empresa_id, solo_activos=True):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT v.*, u.nombre_completo AS chofer_habitual_nombre
        FROM vehiculos_entrega v
        LEFT JOIN users u ON u.id = v.chofer_habitual_id
        WHERE v.empresa_id = %s
    """
    params = [empresa_id]
    if solo_activos:
        query += " AND v.activo = TRUE"
    query += " ORDER BY v.nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()

    # La vigencia de la póliza solo sirve de algo si alguien se entera ANTES
    # de que venza — se marca aquí para que el frontend pueda resaltarla,
    # en vez de que el dato quede enterrado hasta que ya sea demasiado tarde.
    hoy = ahora().date()
    for v in rows:
        v["poliza_vencida"] = False
        v["poliza_por_vencer"] = False
        if v.get("vigencia_poliza"):
            try:
                dias = (datetime.fromisoformat(v["vigencia_poliza"][:10]).date() - hoy).days
                v["poliza_vencida"] = dias < 0
                v["poliza_por_vencer"] = 0 <= dias <= 30
            except ValueError:
                pass
    return rows


_CAMPOS_VEHICULO = [
    "nombre", "numero_serie", "marca", "modelo", "anio", "placa", "kilometraje", "notas",
    "razon_social", "combustible", "numero_factura", "aseguradora", "numero_poliza", "vigencia_poliza",
    "numero_tarjeta_circulacion", "aplica_verificacion", "periodo_verificacion_1", "periodo_verificacion_2",
    "chofer_habitual_id", "geotab_device_id",
]


def crear_vehiculo_entrega(empresa_id, nombre, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    columnas, marcadores, valores = ["empresa_id", "nombre"], ["%s", "%s"], [empresa_id, nombre]
    for k in _CAMPOS_VEHICULO:
        if k == "nombre":
            continue
        if k in campos_nuevos and campos_nuevos[k] is not None:
            columnas.append(k); marcadores.append("%s"); valores.append(campos_nuevos[k])
    cur.execute(
        f"INSERT INTO vehiculos_entrega ({', '.join(columnas)}) VALUES ({', '.join(marcadores)}) RETURNING id",
        valores,
    )
    vehiculo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return vehiculo_id


def actualizar_vehiculo_entrega(empresa_id, vehiculo_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in _CAMPOS_VEHICULO:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [vehiculo_id, empresa_id]
        cur.execute(f"UPDATE vehiculos_entrega SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def cambiar_estado_vehiculo_entrega(empresa_id, vehiculo_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE vehiculos_entrega SET activo = %s WHERE id = %s AND empresa_id = %s",
                (activo, vehiculo_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


# ---- Mantenimientos de vehículo (verificación, servicio, reparaciones) ----

_NOMBRES_TIPO_MANT_VEH = {"preventivo": "Preventivo", "correctivo": "Correctivo", "verificacion": "Verificación"}


def listar_mantenimientos_vehiculo(empresa_id, estado=None, vehiculo_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT m.*, v.nombre AS vehiculo_nombre, v.placa AS vehiculo_placa,
               t.folio AS ticket_folio, t.estado AS ticket_estado,
               u.nombre_completo AS responsable_nombre
        FROM mantenimientos_vehiculo m
        JOIN vehiculos_entrega v ON v.id = m.vehiculo_id
        LEFT JOIN tickets t ON t.id = m.ticket_id
        LEFT JOIN users u ON u.id = m.responsable_id
        WHERE m.empresa_id = %s
    """
    params = [empresa_id]
    if estado:
        query += " AND m.estado = %s"; params.append(estado)
    if vehiculo_id:
        query += " AND m.vehiculo_id = %s"; params.append(vehiculo_id)
    query += " ORDER BY m.fecha_programada ASC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()

    hoy = ahora().date().isoformat()
    for r in rows:
        if r["estado"] == "pendiente" and r["fecha_programada"][:10] < hoy:
            r["estado"] = "vencido"
    return rows


def crear_mantenimiento_vehiculo(empresa_id, vehiculo_id, tipo, descripcion, fecha_programada, frecuencia="unica",
                                  notas=None, responsable_id=None, creado_por_id=None,
                                  kilometraje_en_servicio=None, kilometraje_proximo_servicio=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nombre FROM vehiculos_entrega WHERE id = %s AND empresa_id = %s", (vehiculo_id, empresa_id))
    fila_vehiculo = cur.fetchone()
    if not fila_vehiculo:
        cur.close(); conn.close()
        return None
    nombre_vehiculo = fila_vehiculo["nombre"]
    now = ahora().isoformat(timespec="seconds")

    # Igual que con los mantenimientos de equipos: se crea un ticket vinculado
    # y asignado al responsable, así le llega notificación por WhatsApp (si
    # tiene teléfono configurado) y lo ve en el tablero de Tickets, además de
    # aparecer en "Mis tareas".
    ticket_id = None
    if creado_por_id:
        ticket = crear_ticket(
            empresa_id,
            departamento="Almacén",
            descripcion=f"Mantenimiento {_NOMBRES_TIPO_MANT_VEH.get(tipo, tipo)} programado — Vehículo: {nombre_vehiculo}. {descripcion}",
            categoria="vehiculo",
            prioridad="media",
            usuario_id=creado_por_id,
        )
        ticket_id = ticket["id"]
        if responsable_id:
            actualizar_ticket(ticket_id, asignado_a_id=responsable_id)

    cur.execute(
        """INSERT INTO mantenimientos_vehiculo
           (empresa_id, vehiculo_id, tipo, descripcion, fecha_programada, frecuencia, estado, notas, creado_en,
            ticket_id, responsable_id, creado_por_id, kilometraje_en_servicio, kilometraje_proximo_servicio)
           VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, vehiculo_id, tipo, descripcion, fecha_programada, frecuencia, notas, now,
         ticket_id, responsable_id, creado_por_id, kilometraje_en_servicio, kilometraje_proximo_servicio),
    )
    mant_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return mant_id


def marcar_mantenimiento_vehiculo_realizado(empresa_id, mantenimiento_id, realizado_por, notas=None,
                                             kilometraje_en_servicio=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mantenimientos_vehiculo WHERE id = %s AND empresa_id = %s", (mantenimiento_id, empresa_id))
    mant = cur.fetchone()
    if not mant:
        cur.close(); conn.close()
        return None
    mant = dict(mant)
    now = ahora().isoformat(timespec="seconds")
    km_final = kilometraje_en_servicio if kilometraje_en_servicio is not None else mant.get("kilometraje_en_servicio")
    cur.execute(
        """UPDATE mantenimientos_vehiculo
           SET estado = 'realizado', realizado_en = %s, realizado_por = %s, notas = %s, kilometraje_en_servicio = %s
           WHERE id = %s""",
        (now, realizado_por, notas or mant.get("notas"), km_final, mantenimiento_id),
    )
    # El kilometraje capturado al cerrar el servicio se refleja también como
    # el kilometraje ACTUAL del vehículo — así el odómetro registrado en el
    # vehículo no se queda desactualizado con cada servicio.
    if km_final is not None:
        cur.execute("UPDATE vehiculos_entrega SET kilometraje = %s WHERE id = %s AND empresa_id = %s",
                    (km_final, mant["vehiculo_id"], empresa_id))
    conn.commit()

    # Si es recurrente, se programa el siguiente automáticamente — mismo
    # comportamiento que ya existe para mantenimientos de equipos.
    siguiente_id = None
    siguiente_fecha = _siguiente_fecha(mant["fecha_programada"], mant["frecuencia"])
    if siguiente_fecha:
        cur.execute(
            """INSERT INTO mantenimientos_vehiculo
               (empresa_id, vehiculo_id, tipo, descripcion, fecha_programada, frecuencia, estado, notas, creado_en,
                responsable_id, creado_por_id, kilometraje_proximo_servicio)
               VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s, %s) RETURNING id""",
            (empresa_id, mant["vehiculo_id"], mant["tipo"], mant["descripcion"], siguiente_fecha, mant["frecuencia"],
             mant.get("notas"), now, mant.get("responsable_id"), mant.get("creado_por_id"),
             mant.get("kilometraje_proximo_servicio")),
        )
        siguiente_id = cur.fetchone()["id"]
        conn.commit()

    cur.close(); conn.close()
    return {"mantenimiento_id": mantenimiento_id, "siguiente_id": siguiente_id}


def listar_mantenimientos_vehiculo_pendientes_usuario(empresa_id, usuario_id):
    """Mantenimientos de vehículo asignados a esta persona y todavía sin
    realizar — para 'Mis tareas'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.tipo, m.descripcion, m.fecha_programada, m.vehiculo_id,
               v.nombre AS vehiculo_nombre
        FROM mantenimientos_vehiculo m
        JOIN vehiculos_entrega v ON v.id = m.vehiculo_id
        WHERE m.empresa_id = %s AND m.responsable_id = %s AND m.estado = 'pendiente'
        ORDER BY m.fecha_programada ASC
    """, (empresa_id, usuario_id))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def cambiar_estado_entrega(empresa_id, entrega_id, estado_nuevo, usuario_id, comentario=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM entregas WHERE id = %s AND empresa_id = %s", (entrega_id, empresa_id))
    fila = cur.fetchone()
    if not fila:
        cur.close(); conn.close()
        return False, "Entrega no encontrada"
    estado_actual = fila["estado"]
    if estado_nuevo not in TRANSICIONES_VALIDAS_ENTREGA.get(estado_actual, set()):
        cur.close(); conn.close()
        return False, f"No se puede pasar de '{estado_actual}' a '{estado_nuevo}'"

    now = ahora().isoformat(timespec="seconds")
    campos = ["estado = %s", "actualizado_en = %s"]
    valores = [estado_nuevo, now]
    if estado_nuevo == "rechazada" and comentario:
        campos.append("motivo_rechazo = %s"); valores.append(comentario)
    if estado_nuevo == "reagendada" and comentario:
        campos.append("motivo_reagenda = %s"); valores.append(comentario)
    valores += [entrega_id, empresa_id]
    cur.execute(f"UPDATE entregas SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)

    cur.execute(
        """INSERT INTO entrega_historial (entrega_id, estatus_anterior, estatus_nuevo, comentario, usuario_id, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (entrega_id, estado_actual, estado_nuevo, comentario, usuario_id, now),
    )
    conn.commit()
    cur.close(); conn.close()
    return True, None


def asignar_instaladores_entrega(empresa_id, entrega_id, instalador_ids):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM entregas WHERE id = %s AND empresa_id = %s", (entrega_id, empresa_id))
    if not cur.fetchone():
        cur.close(); conn.close()
        return False
    now = ahora().isoformat(timespec="seconds")
    cur.execute("DELETE FROM entrega_instaladores WHERE entrega_id = %s", (entrega_id,))
    for instalador_id in instalador_ids:
        cur.execute(
            "INSERT INTO entrega_instaladores (entrega_id, instalador_id, asignado_en) VALUES (%s, %s, %s)",
            (entrega_id, instalador_id, now),
        )
    conn.commit()
    cur.close(); conn.close()
    return True


# ---- Plantilla de checklist de entregas (puntos que arma el administrador) ----

def listar_plantilla_checklist_entrega(empresa_id, solo_activos=False):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM entrega_checklist_plantilla WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = TRUE"
    query += " ORDER BY orden, id"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_item_plantilla_checklist_entrega(empresa_id, texto, automatico=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(orden), -1) + 1 AS siguiente FROM entrega_checklist_plantilla WHERE empresa_id = %s", (empresa_id,))
    orden = cur.fetchone()["siguiente"]
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO entrega_checklist_plantilla (empresa_id, texto, automatico, orden, creado_en)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, texto, automatico, orden, now),
    )
    item_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return item_id


def actualizar_item_plantilla_checklist_entrega(empresa_id, item_id, **campos_nuevos):
    permitidos = ["texto", "automatico", "activo"]
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [item_id, empresa_id]
        cur.execute(f"UPDATE entrega_checklist_plantilla SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def eliminar_item_plantilla_checklist_entrega(empresa_id, item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entrega_checklist_plantilla WHERE id = %s AND empresa_id = %s", (item_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado


# ---- Ubicación del CEDIS y estimados de viaje (sin API de pago) ----

def obtener_config_cedis(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM entrega_configuracion WHERE empresa_id = %s", (empresa_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def guardar_config_cedis(empresa_id, cedis_direccion, cedis_lat, cedis_lng):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO entrega_configuracion (empresa_id, cedis_direccion, cedis_lat, cedis_lng)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (empresa_id) DO UPDATE SET
               cedis_direccion = EXCLUDED.cedis_direccion,
               cedis_lat = EXCLUDED.cedis_lat,
               cedis_lng = EXCLUDED.cedis_lng""",
        (empresa_id, cedis_direccion, cedis_lat, cedis_lng),
    )
    conn.commit()
    cur.close(); conn.close()


def listar_entregas_cercanas(empresa_id, entrega_id, fecha_programada, lat, lng, radio_km=5):
    """Otras entregas programadas para el MISMO día, dentro de un radio (en
    línea recta) de la ubicación dada — para sugerir asignar el mismo
    instalador y ahorrar viajes."""
    if lat is None or lng is None or not fecha_programada:
        return []
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, folio, cliente_nombre, destino_lat, destino_lng
           FROM entregas
           WHERE empresa_id = %s AND id != %s AND fecha_programada = %s
                 AND destino_lat IS NOT NULL AND destino_lng IS NOT NULL
                 AND estado NOT IN ('entregada', 'cancelada')""",
        (empresa_id, entrega_id, fecha_programada),
    )
    candidatas = [dict(r) for r in cur.fetchall()]
    resultado = []
    for c in candidatas:
        distancia = geo.haversine_km(lat, lng, c["destino_lat"], c["destino_lng"])
        if distancia <= radio_km:
            cur.execute(
                """SELECT ei.instalador_id, u.nombre_completo
                   FROM entrega_instaladores ei JOIN users u ON u.id = ei.instalador_id
                   WHERE ei.entrega_id = %s""",
                (c["id"],),
            )
            resultado.append({
                "id": c["id"], "folio": c["folio"], "cliente_nombre": c["cliente_nombre"],
                "distancia_km": round(distancia, 1),
                "instaladores": [dict(r) for r in cur.fetchall()],
            })
    cur.close(); conn.close()
    resultado.sort(key=lambda x: x["distancia_km"])
    return resultado


def agregar_item_checklist_entrega(entrega_id, texto, obligatorio=True, agregado_en_sitio=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(orden), -1) + 1 AS siguiente FROM entrega_checklist_items WHERE entrega_id = %s", (entrega_id,))
    orden = cur.fetchone()["siguiente"]
    cur.execute(
        """INSERT INTO entrega_checklist_items (entrega_id, texto, orden, obligatorio, agregado_en_sitio)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (entrega_id, texto, orden, obligatorio, agregado_en_sitio),
    )
    item_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return item_id


def marcar_item_checklist_entrega(item_id, usuario_id, completado):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    if completado:
        cur.execute(
            "UPDATE entrega_checklist_items SET completado = TRUE, completado_por_id = %s, completado_en = %s WHERE id = %s",
            (usuario_id, now, item_id),
        )
    else:
        cur.execute(
            "UPDATE entrega_checklist_items SET completado = FALSE, completado_por_id = NULL, completado_en = NULL WHERE id = %s",
            (item_id,),
        )
    conn.commit()
    cur.close(); conn.close()


def eliminar_item_checklist_entrega(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entrega_checklist_items WHERE id = %s", (item_id,))
    conn.commit()
    cur.close(); conn.close()


def firmar_entrega(empresa_id, entrega_id, receptor_nombre, receptor_puesto, firma_base64, usuario_id,
                    latitud=None, longitud=None):
    """Guarda la firma de conformidad del receptor y avanza la entrega a 'entregada'."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE entregas
           SET receptor_nombre = %s, receptor_puesto = %s, firma_base64 = %s, firmado_en = %s,
               latitud = %s, longitud = %s, actualizado_en = %s
           WHERE id = %s AND empresa_id = %s""",
        (receptor_nombre, receptor_puesto, firma_base64, now, latitud, longitud, now, entrega_id, empresa_id),
    )
    conn.commit()
    cur.close(); conn.close()
    return cambiar_estado_entrega(empresa_id, entrega_id, "entregada", usuario_id, comentario="Firmado de conformidad")


def eliminar_entrega(empresa_id, entrega_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM entregas WHERE id = %s AND empresa_id = %s", (entrega_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado


# ================== MARKETING ==================
# Campañas, redes sociales, presupuesto (por campaña / red / persona) y
# métricas — cada red social puede tener sus propias métricas (texto libre
# en nombre_metrica) en vez de una lista fija, porque cada plataforma mide
# cosas distintas y eso cambia con el tiempo.

_NOMBRES_PLATAFORMA = {
    "facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok",
    "youtube": "YouTube", "linkedin": "LinkedIn", "x": "X (Twitter)",
    "google_ads": "Google Ads", "otro": "Otra",
}


# ---- Redes sociales (catálogo de cuentas) ----

def listar_redes_sociales_marketing(empresa_id, solo_activas=True):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM redes_sociales_marketing WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activas:
        query += " AND activa = TRUE"
    query += " ORDER BY plataforma, nombre_cuenta"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def crear_red_social_marketing(empresa_id, plataforma, nombre_cuenta, url=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO redes_sociales_marketing (empresa_id, plataforma, nombre_cuenta, url) VALUES (%s, %s, %s, %s) RETURNING id",
        (empresa_id, plataforma, nombre_cuenta.strip(), url),
    )
    red_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return red_id


def actualizar_red_social_marketing(empresa_id, red_id, **campos_nuevos):
    permitidos = ["plataforma", "nombre_cuenta", "url", "activa"]
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [red_id, empresa_id]
        cur.execute(f"UPDATE redes_sociales_marketing SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


# ---- Campañas ----

def listar_campanas_marketing(empresa_id, estado=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT c.*, u.nombre_completo AS responsable_nombre,
               COALESCE((SELECT SUM(g.monto) FROM gastos_marketing g WHERE g.campana_id = c.id), 0) AS gastado
        FROM campanas_marketing c
        LEFT JOIN users u ON u.id = c.responsable_id
        WHERE c.empresa_id = %s
    """
    params = [empresa_id]
    if estado:
        query += " AND c.estado = %s"; params.append(estado)
    query += " ORDER BY c.fecha_inicio IS NULL, c.fecha_inicio DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_campana_marketing(empresa_id, campana_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.nombre_completo AS responsable_nombre
        FROM campanas_marketing c
        LEFT JOIN users u ON u.id = c.responsable_id
        WHERE c.id = %s AND c.empresa_id = %s
    """, (campana_id, empresa_id))
    fila = cur.fetchone()
    if not fila:
        cur.close(); conn.close()
        return None
    campana = dict(fila)

    cur.execute("""
        SELECT cr.id, cr.red_social_id, cr.presupuesto_asignado, r.plataforma, r.nombre_cuenta
        FROM campana_redes_marketing cr JOIN redes_sociales_marketing r ON r.id = cr.red_social_id
        WHERE cr.campana_id = %s
    """, (campana_id,))
    campana["redes"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT g.*, r.nombre_cuenta AS red_social_nombre, u.nombre_completo AS persona_nombre
        FROM gastos_marketing g
        LEFT JOIN redes_sociales_marketing r ON r.id = g.red_social_id
        LEFT JOIN users u ON u.id = g.persona_id
        WHERE g.campana_id = %s ORDER BY g.fecha DESC
    """, (campana_id,))
    campana["gastos"] = [dict(r) for r in cur.fetchall()]
    campana["gastado"] = sum(g["monto"] for g in campana["gastos"])

    cur.close(); conn.close()
    return campana


def crear_campana_marketing(empresa_id, nombre, descripcion, fecha_inicio, fecha_fin, presupuesto_asignado,
                             responsable_id, creado_por_id, redes=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO campanas_marketing
           (empresa_id, nombre, descripcion, fecha_inicio, fecha_fin, estado, presupuesto_asignado,
            responsable_id, creado_por_id, creado_en)
           VALUES (%s, %s, %s, %s, %s, 'planificacion', %s, %s, %s, %s) RETURNING id""",
        (empresa_id, nombre.strip(), descripcion, fecha_inicio, fecha_fin, presupuesto_asignado,
         responsable_id, creado_por_id, now),
    )
    campana_id = cur.fetchone()["id"]
    for r in (redes or []):
        if r.get("red_social_id"):
            cur.execute(
                "INSERT INTO campana_redes_marketing (campana_id, red_social_id, presupuesto_asignado) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (campana_id, r["red_social_id"], r.get("presupuesto_asignado")),
            )
    conn.commit()
    cur.close(); conn.close()
    return campana_id


def actualizar_campana_marketing(empresa_id, campana_id, **campos_nuevos):
    permitidos = ["nombre", "descripcion", "fecha_inicio", "fecha_fin", "estado", "presupuesto_asignado", "responsable_id"]
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        valores += [campana_id, empresa_id]
        cur.execute(f"UPDATE campanas_marketing SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()


def asignar_redes_campana_marketing(campana_id, redes):
    """Reemplaza por completo qué redes están asignadas a la campaña y con
    qué presupuesto cada una."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM campana_redes_marketing WHERE campana_id = %s", (campana_id,))
    for r in (redes or []):
        if r.get("red_social_id"):
            cur.execute(
                "INSERT INTO campana_redes_marketing (campana_id, red_social_id, presupuesto_asignado) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (campana_id, r["red_social_id"], r.get("presupuesto_asignado")),
            )
    conn.commit()
    cur.close(); conn.close()


def eliminar_campana_marketing(empresa_id, campana_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM campanas_marketing WHERE id = %s AND empresa_id = %s", (campana_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado


# ---- Gastos / presupuesto ejecutado ----

def crear_gasto_marketing(empresa_id, concepto, monto, fecha, campana_id=None, red_social_id=None,
                           persona_id=None, creado_por_id=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO gastos_marketing
           (empresa_id, campana_id, red_social_id, persona_id, concepto, monto, fecha, creado_por_id, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, campana_id, red_social_id, persona_id, concepto.strip(), monto, fecha, creado_por_id, now),
    )
    gasto_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return gasto_id


def listar_gastos_marketing(empresa_id, campana_id=None, red_social_id=None, persona_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT g.*, c.nombre AS campana_nombre, r.nombre_cuenta AS red_social_nombre, u.nombre_completo AS persona_nombre
        FROM gastos_marketing g
        LEFT JOIN campanas_marketing c ON c.id = g.campana_id
        LEFT JOIN redes_sociales_marketing r ON r.id = g.red_social_id
        LEFT JOIN users u ON u.id = g.persona_id
        WHERE g.empresa_id = %s
    """
    params = [empresa_id]
    if campana_id:
        query += " AND g.campana_id = %s"; params.append(campana_id)
    if red_social_id:
        query += " AND g.red_social_id = %s"; params.append(red_social_id)
    if persona_id:
        query += " AND g.persona_id = %s"; params.append(persona_id)
    query += " ORDER BY g.fecha DESC, g.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def eliminar_gasto_marketing(empresa_id, gasto_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gastos_marketing WHERE id = %s AND empresa_id = %s", (gasto_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado


def resumen_presupuesto_marketing(empresa_id):
    """Total gastado agrupado 3 formas — por campaña, por red social y por
    persona — para la vista de presupuesto."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.nombre, c.presupuesto_asignado, COALESCE(SUM(g.monto), 0) AS gastado
        FROM campanas_marketing c LEFT JOIN gastos_marketing g ON g.campana_id = c.id
        WHERE c.empresa_id = %s GROUP BY c.id, c.nombre, c.presupuesto_asignado ORDER BY gastado DESC
    """, (empresa_id,))
    por_campana = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT r.id, r.plataforma, r.nombre_cuenta, COALESCE(SUM(g.monto), 0) AS gastado
        FROM redes_sociales_marketing r LEFT JOIN gastos_marketing g ON g.red_social_id = r.id
        WHERE r.empresa_id = %s GROUP BY r.id, r.plataforma, r.nombre_cuenta ORDER BY gastado DESC
    """, (empresa_id,))
    por_red = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT u.id, u.nombre_completo, COALESCE(SUM(g.monto), 0) AS gastado
        FROM gastos_marketing g JOIN users u ON u.id = g.persona_id
        WHERE g.empresa_id = %s GROUP BY u.id, u.nombre_completo ORDER BY gastado DESC
    """, (empresa_id,))
    por_persona = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()
    return {"por_campana": por_campana, "por_red": por_red, "por_persona": por_persona}


# ---- Métricas por red social ----

def crear_metrica_marketing(empresa_id, red_social_id, fecha, nombre_metrica, valor, campana_id=None,
                             registrado_por_id=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO metricas_marketing
           (empresa_id, red_social_id, campana_id, fecha, nombre_metrica, valor, registrado_por_id, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (empresa_id, red_social_id, campana_id, fecha, nombre_metrica.strip(), valor, registrado_por_id, now),
    )
    metrica_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return metrica_id


def listar_metricas_marketing(empresa_id, red_social_id=None, campana_id=None):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT m.*, r.plataforma, r.nombre_cuenta AS red_social_nombre, c.nombre AS campana_nombre
        FROM metricas_marketing m
        JOIN redes_sociales_marketing r ON r.id = m.red_social_id
        LEFT JOIN campanas_marketing c ON c.id = m.campana_id
        WHERE m.empresa_id = %s
    """
    params = [empresa_id]
    if red_social_id:
        query += " AND m.red_social_id = %s"; params.append(red_social_id)
    if campana_id:
        query += " AND m.campana_id = %s"; params.append(campana_id)
    query += " ORDER BY m.fecha DESC, m.id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def eliminar_metrica_marketing(empresa_id, metrica_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM metricas_marketing WHERE id = %s AND empresa_id = %s", (metrica_id, empresa_id))
    eliminado = cur.rowcount > 0
    conn.commit()
    cur.close(); conn.close()
    return eliminado
