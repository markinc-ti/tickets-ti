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
from datetime import datetime

import psycopg2
import psycopg2.extras

import auth

DATABASE_URL = os.getenv("DATABASE_URL", "")

ESTADOS = ["abierto", "en_progreso", "resuelto", "cerrado"]
PRIORIDADES = ["baja", "media", "alta", "urgente"]
ROLES = ["superadmin", "admin", "tecnico", "usuario"]

TIPOS_EQUIPO = ["computadora", "laptop", "impresora", "monitor", "servidor", "red", "otro"]
ESTADOS_EQUIPO = ["activo", "en_reparacion", "baja"]
TIPOS_MANTENIMIENTO = ["preventivo", "correctivo"]
FRECUENCIAS_MANTENIMIENTO = ["unica", "mensual", "trimestral", "semestral", "anual"]

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
            creado_en TEXT NOT NULL
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
            creado_en TEXT NOT NULL
        );
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'")
    if cur.fetchone()["n"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
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
    now = datetime.now().isoformat(timespec="seconds")
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
        "SELECT id, username, nombre_completo, rol, telefono_whatsapp, activo, creado_en FROM users WHERE empresa_id = %s ORDER BY nombre_completo",
        (empresa_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


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


def crear_usuario(empresa_id, username, password, nombre_completo, rol, telefono_whatsapp=None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, telefono_whatsapp, creado_en) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (empresa_id, username, auth.hash_password(password), nombre_completo, rol, telefono_whatsapp, now),
    )
    user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return user_id


def actualizar_usuario(usuario_id, nombre_completo=None, rol=None, telefono_whatsapp=None, activo=None, password=None):
    conn = get_connection()
    cur = conn.cursor()
    campos, valores = [], []
    if nombre_completo is not None:
        campos.append("nombre_completo = %s"); valores.append(nombre_completo)
    if rol is not None:
        campos.append("rol = %s"); valores.append(rol)
    if telefono_whatsapp is not None:
        campos.append("telefono_whatsapp = %s"); valores.append(telefono_whatsapp)
    if activo is not None:
        campos.append("activo = %s"); valores.append(activo)
    if password:
        campos.append("password_hash = %s"); valores.append(auth.hash_password(password))
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
    query = "SELECT * FROM categorias WHERE empresa_id = %s"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = TRUE"
    query += " ORDER BY nombre"
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
                    departamento=None, fecha_desde=None, fecha_hasta=None):
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
        SELECT c.id, c.texto, c.creado_en, u.nombre_completo AS autor_nombre
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
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO tickets
           (empresa_id, folio, departamento, descripcion, categoria, prioridad, estado, solicitante_id, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, 'abierto', %s, %s, %s) RETURNING id""",
        (empresa_id, folio, departamento, descripcion, categoria, prioridad, usuario_id, now, now),
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
    now = datetime.now().isoformat(timespec="seconds")
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


def agregar_comentario(ticket_id, usuario_id, texto):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tickets WHERE id = %s", (ticket_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO comentarios (ticket_id, autor_id, texto, creado_en) VALUES (%s, %s, %s, %s)",
        (ticket_id, usuario_id, texto, now),
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
    now = datetime.now().isoformat(timespec="seconds")
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


def estadisticas(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT estado, COUNT(*) AS n FROM tickets WHERE empresa_id = %s GROUP BY estado", (empresa_id,))
    por_estado = {r["estado"]: r["n"] for r in cur.fetchall()}

    cur.execute(
        "SELECT COUNT(*) AS n FROM tickets WHERE empresa_id = %s AND prioridad = 'urgente' AND estado NOT IN ('resuelto','cerrado')",
        (empresa_id,),
    )
    urgentes_abiertos = cur.fetchone()["n"]

    cur.execute(
        "SELECT creado_en, resuelto_en FROM tickets WHERE empresa_id = %s AND resuelto_en IS NOT NULL", (empresa_id,)
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
    query = "SELECT * FROM equipos WHERE empresa_id = %s"
    params = [empresa_id]
    if tipo:
        query += " AND tipo = %s"; params.append(tipo)
    if estado:
        query += " AND estado = %s"; params.append(estado)
    else:
        query += " AND estado != 'baja'"
    query += " ORDER BY nombre"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


def obtener_equipo(empresa_id, equipo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM equipos WHERE id = %s AND empresa_id = %s", (equipo_id, empresa_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def crear_equipo(empresa_id, tipo, nombre, marca=None, modelo=None, numero_serie=None,
                  departamento=None, responsable=None, fecha_adquisicion=None, notas=None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO equipos
           (empresa_id, tipo, nombre, marca, modelo, numero_serie, departamento, responsable,
            estado, fecha_adquisicion, notas, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'activo', %s, %s, %s, %s) RETURNING id""",
        (empresa_id, tipo, nombre, marca, modelo, numero_serie, departamento, responsable,
         fecha_adquisicion, notas, now, now),
    )
    equipo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return obtener_equipo(empresa_id, equipo_id)


def actualizar_equipo(empresa_id, equipo_id, **campos_nuevos):
    conn = get_connection()
    cur = conn.cursor()
    permitidos = ["tipo", "nombre", "marca", "modelo", "numero_serie", "departamento",
                  "responsable", "estado", "fecha_adquisicion", "notas"]
    campos, valores = [], []
    for k in permitidos:
        if k in campos_nuevos and campos_nuevos[k] is not None:
            campos.append(f"{k} = %s"); valores.append(campos_nuevos[k])
    if campos:
        campos.append("actualizado_en = %s"); valores.append(datetime.now().isoformat(timespec="seconds"))
        valores += [equipo_id, empresa_id]
        cur.execute(f"UPDATE equipos SET {', '.join(campos)} WHERE id = %s AND empresa_id = %s", valores)
        conn.commit()
    cur.close(); conn.close()
    return obtener_equipo(empresa_id, equipo_id)


def dar_de_baja_equipo(empresa_id, equipo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE equipos SET estado = 'baja', actualizado_en = %s WHERE id = %s AND empresa_id = %s",
                (datetime.now().isoformat(timespec="seconds"), equipo_id, empresa_id))
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
        SELECT m.*, e.nombre AS equipo_nombre, e.tipo AS equipo_tipo
        FROM mantenimientos m JOIN equipos e ON e.id = m.equipo_id
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

    hoy = datetime.now().date().isoformat()
    for r in rows:
        if r["estado"] == "pendiente" and r["fecha_programada"][:10] < hoy:
            r["estado"] = "vencido"
    return rows


def crear_mantenimiento(empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia="unica", notas=None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO mantenimientos
           (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia, estado, notas, creado_en)
           VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, %s) RETURNING id""",
        (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia, notas, now),
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
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE mantenimientos SET estado = 'realizado', realizado_en = %s, realizado_por = %s, notas = %s WHERE id = %s",
        (now, realizado_por, notas or mant.get("notas"), mantenimiento_id),
    )
    conn.commit()

    siguiente_id = None
    siguiente_fecha = _siguiente_fecha(mant["fecha_programada"], mant["frecuencia"])
    if siguiente_fecha:
        cur.execute(
            """INSERT INTO mantenimientos
               (empresa_id, equipo_id, tipo, descripcion, fecha_programada, frecuencia, estado, creado_en)
               VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s) RETURNING id""",
            (empresa_id, mant["equipo_id"], mant["tipo"], mant["descripcion"], siguiente_fecha, mant["frecuencia"], now),
        )
        siguiente_id = cur.fetchone()["id"]
        conn.commit()

    cur.close(); conn.close()
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
