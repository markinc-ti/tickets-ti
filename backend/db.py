"""
Capa de datos — ahora multiempresa (multi-tenant).

Cada empresa tiene sus propios usuarios, departamentos, categorías y
tickets, completamente aislados de las demás. Por encima de todas las
empresas existe un usuario "superadmin" (empresa_id = NULL) que solo
puede crear/editar/activar empresas y ponerles su logo — no ve tickets
de ninguna empresa.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import auth

DB_PATH = Path(__file__).parent / "tickets.db"

ESTADOS = ["abierto", "en_progreso", "resuelto", "cerrado"]
PRIORIDADES = ["baja", "media", "alta", "urgente"]
ROLES = ["superadmin", "admin", "tecnico", "usuario"]

_DEPARTAMENTOS_INICIALES = [
    "Ventas", "Producción", "Almacén", "Contabilidad",
    "Recursos Humanos", "Dirección", "Sistemas", "Otro",
]
_CATEGORIAS_INICIALES = ["hardware", "software", "red", "accesos", "otro"]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()

    # Si la base es de la versión anterior (una sola empresa, sin la
    # tabla "empresas" o sin la columna empresa_id en users), no hay
    # forma segura de migrar automáticamente la estructura de varias
    # tablas a la vez (SQLite no permite cambiar UNIQUE constraints con
    # ALTER TABLE). Se reinicia limpio, igual que en el salto anterior.
    cols_users = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    esquema_viejo = cols_users and "empresa_id" not in cols_users
    if esquema_viejo:
        conn.executescript("""
            DROP TABLE IF EXISTS comentarios;
            DROP TABLE IF EXISTS tickets;
            DROP TABLE IF EXISTS departamentos;
            DROP TABLE IF EXISTS categorias;
            DROP TABLE IF EXISTS users;
        """)
        conn.commit()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            logo_base64 TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER REFERENCES empresas(id),
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'usuario',
            telefono_whatsapp TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            UNIQUE(empresa_id, nombre)
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            UNIQUE(empresa_id, nombre)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            autor_id INTEGER NOT NULL REFERENCES users(id),
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL
        );
    """)
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM users WHERE rol = 'superadmin'").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, creado_en) VALUES (NULL, ?, ?, ?, 'superadmin', ?)",
            ("superadmin", auth.hash_password("cambiar123"), "Super Administrador", now),
        )
        conn.commit()
    conn.close()


# ---- Empresas (superadmin) ----

def listar_empresas():
    conn = get_connection()
    rows = conn.execute("SELECT id, nombre, logo_base64, activo, creado_en FROM empresas ORDER BY nombre").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_empresa(empresa_id):
    conn = get_connection()
    row = conn.execute("SELECT id, nombre, logo_base64, activo, creado_en FROM empresas WHERE id = ?", (empresa_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def crear_empresa(nombre, admin_username, admin_password, admin_nombre):
    """Crea la empresa y de una vez su primer usuario administrador."""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        cur = conn.execute("INSERT INTO empresas (nombre, creado_en) VALUES (?, ?)", (nombre, now))
        empresa_id = cur.lastrowid

        conn.execute(
            "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, creado_en) VALUES (?, ?, ?, ?, 'admin', ?)",
            (empresa_id, admin_username, auth.hash_password(admin_password), admin_nombre, now),
        )

        conn.executemany(
            "INSERT INTO departamentos (empresa_id, nombre) VALUES (?, ?)",
            [(empresa_id, d) for d in _DEPARTAMENTOS_INICIALES],
        )
        conn.executemany(
            "INSERT INTO categorias (empresa_id, nombre) VALUES (?, ?)",
            [(empresa_id, c) for c in _CATEGORIAS_INICIALES],
        )
        conn.commit()
    finally:
        conn.close()
    return empresa_id


def actualizar_empresa(empresa_id, nombre=None, activo=None):
    conn = get_connection()
    campos, valores = [], []
    if nombre is not None:
        campos.append("nombre = ?"); valores.append(nombre)
    if activo is not None:
        campos.append("activo = ?"); valores.append(1 if activo else 0)
    if campos:
        valores.append(empresa_id)
        conn.execute(f"UPDATE empresas SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
    conn.close()


def actualizar_logo_empresa(empresa_id, logo_base64):
    conn = get_connection()
    conn.execute("UPDATE empresas SET logo_base64 = ? WHERE id = ?", (logo_base64, empresa_id))
    conn.commit()
    conn.close()


# ---- Usuarios (dentro de una empresa) ----

def obtener_usuario_por_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_usuarios(empresa_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, nombre_completo, rol, telefono_whatsapp, activo, creado_en FROM users WHERE empresa_id = ? ORDER BY nombre_completo",
        (empresa_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_tecnicos_activos(empresa_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, nombre_completo, telefono_whatsapp FROM users WHERE empresa_id = ? AND rol IN ('tecnico','admin') AND activo = 1 ORDER BY nombre_completo",
        (empresa_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_usuario(empresa_id, username, password, nombre_completo, rol, telefono_whatsapp=None):
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO users (empresa_id, username, password_hash, nombre_completo, rol, telefono_whatsapp, creado_en) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (empresa_id, username, auth.hash_password(password), nombre_completo, rol, telefono_whatsapp, now),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def actualizar_usuario(usuario_id, nombre_completo=None, rol=None, telefono_whatsapp=None, activo=None, password=None):
    conn = get_connection()
    campos, valores = [], []
    if nombre_completo is not None:
        campos.append("nombre_completo = ?"); valores.append(nombre_completo)
    if rol is not None:
        campos.append("rol = ?"); valores.append(rol)
    if telefono_whatsapp is not None:
        campos.append("telefono_whatsapp = ?"); valores.append(telefono_whatsapp)
    if activo is not None:
        campos.append("activo = ?"); valores.append(1 if activo else 0)
    if password:
        campos.append("password_hash = ?"); valores.append(auth.hash_password(password))
    if campos:
        valores.append(usuario_id)
        conn.execute(f"UPDATE users SET {', '.join(campos)} WHERE id = ?", valores)
        conn.commit()
    conn.close()


def eliminar_usuario(usuario_id):
    conn = get_connection()
    conn.execute("UPDATE users SET activo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()


# ---- Departamentos ----

def listar_departamentos(empresa_id, solo_activos=True):
    conn = get_connection()
    query = "SELECT * FROM departamentos WHERE empresa_id = ?"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = 1"
    query += " ORDER BY nombre"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_departamento(empresa_id, nombre):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO departamentos (empresa_id, nombre) VALUES (?, ?)", (empresa_id, nombre))
        conn.commit()
    finally:
        conn.close()


def cambiar_estado_departamento(empresa_id, depto_id, activo):
    conn = get_connection()
    conn.execute("UPDATE departamentos SET activo = ? WHERE id = ? AND empresa_id = ?", (1 if activo else 0, depto_id, empresa_id))
    conn.commit()
    conn.close()


# ---- Categorías ----

def listar_categorias(empresa_id, solo_activos=True):
    conn = get_connection()
    query = "SELECT * FROM categorias WHERE empresa_id = ?"
    params = [empresa_id]
    if solo_activos:
        query += " AND activo = 1"
    query += " ORDER BY nombre"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_categoria(empresa_id, nombre):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO categorias (empresa_id, nombre) VALUES (?, ?)", (empresa_id, nombre))
        conn.commit()
    finally:
        conn.close()


def cambiar_estado_categoria(empresa_id, cat_id, activo):
    conn = get_connection()
    conn.execute("UPDATE categorias SET activo = ? WHERE id = ? AND empresa_id = ?", (1 if activo else 0, cat_id, empresa_id))
    conn.commit()
    conn.close()


# ---- Tickets (siempre acotados a una empresa) ----

def _ticket_query_base():
    return """
        SELECT t.*, s.nombre_completo AS solicitante_nombre,
               a.nombre_completo AS asignado_a_nombre
        FROM tickets t
        JOIN users s ON s.id = t.solicitante_id
        LEFT JOIN users a ON a.id = t.asignado_a_id
    """


def _next_folio(conn, empresa_id):
    row = conn.execute("SELECT COUNT(*) FROM tickets WHERE empresa_id = ?", (empresa_id,)).fetchone()
    return f"TI-{row[0] + 1:04d}"


def listar_tickets(empresa_id, estado=None, prioridad=None, categoria=None, solicitante_id=None):
    conn = get_connection()
    query = _ticket_query_base() + " WHERE t.empresa_id = ?"
    params = [empresa_id]
    if estado:
        query += " AND t.estado = ?"; params.append(estado)
    if prioridad:
        query += " AND t.prioridad = ?"; params.append(prioridad)
    if categoria:
        query += " AND t.categoria = ?"; params.append(categoria)
    if solicitante_id:
        query += " AND t.solicitante_id = ?"; params.append(solicitante_id)
    query += " ORDER BY CASE t.prioridad WHEN 'urgente' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, t.creado_en DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_ticket(ticket_id, empresa_id=None):
    """Si se pasa empresa_id, solo devuelve el ticket si pertenece a esa empresa (aislamiento entre empresas)."""
    conn = get_connection()
    query = _ticket_query_base() + " WHERE t.id = ?"
    params = [ticket_id]
    if empresa_id is not None:
        query += " AND t.empresa_id = ?"; params.append(empresa_id)
    row = conn.execute(query, params).fetchone()
    if not row:
        conn.close()
        return None
    ticket = dict(row)
    comentarios = conn.execute("""
        SELECT c.id, c.texto, c.creado_en, u.nombre_completo AS autor_nombre
        FROM comentarios c JOIN users u ON u.id = c.autor_id
        WHERE c.ticket_id = ? ORDER BY c.creado_en ASC
    """, (ticket_id,)).fetchall()
    ticket["comentarios"] = [dict(c) for c in comentarios]
    conn.close()
    return ticket


def crear_ticket(empresa_id, departamento, descripcion, categoria, prioridad, usuario_id):
    conn = get_connection()
    folio = _next_folio(conn, empresa_id)
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO tickets
           (empresa_id, folio, departamento, descripcion, categoria, prioridad, estado, solicitante_id, creado_en, actualizado_en)
           VALUES (?, ?, ?, ?, ?, ?, 'abierto', ?, ?, ?)""",
        (empresa_id, folio, departamento, descripcion, categoria, prioridad, usuario_id, now, now),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()
    return obtener_ticket(ticket_id)


def actualizar_ticket(ticket_id, estado=None, prioridad=None, asignado_a_id=None):
    conn = get_connection()
    existente = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existente:
        conn.close()
        return None
    now = datetime.now().isoformat(timespec="seconds")
    campos, valores = [], []
    if estado is not None:
        campos.append("estado = ?"); valores.append(estado)
        campos.append("resuelto_en = ?")
        valores.append(now if estado in ("resuelto", "cerrado") else None)
    if prioridad is not None:
        campos.append("prioridad = ?"); valores.append(prioridad)
    if asignado_a_id is not None:
        campos.append("asignado_a_id = ?"); valores.append(asignado_a_id)
    campos.append("actualizado_en = ?"); valores.append(now)
    valores.append(ticket_id)
    conn.execute(f"UPDATE tickets SET {', '.join(campos)} WHERE id = ?", valores)
    conn.commit()
    conn.close()
    return obtener_ticket(ticket_id)


def agregar_comentario(ticket_id, usuario_id, texto):
    conn = get_connection()
    existente = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existente:
        conn.close()
        return None
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO comentarios (ticket_id, autor_id, texto, creado_en) VALUES (?, ?, ?, ?)",
        (ticket_id, usuario_id, texto, now),
    )
    conn.execute("UPDATE tickets SET actualizado_en = ? WHERE id = ?", (now, ticket_id))
    conn.commit()
    conn.close()
    return obtener_ticket(ticket_id)


def firmar_ticket(ticket_id, firma_base64, firmado_por):
    conn = get_connection()
    existente = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existente:
        conn.close()
        return None
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """UPDATE tickets
           SET estado = 'cerrado', resuelto_en = ?, actualizado_en = ?,
               firma = ?, firmado_por = ?, firmado_en = ?
           WHERE id = ?""",
        (now, now, firma_base64, firmado_por, now, ticket_id),
    )
    conn.commit()
    conn.close()
    return obtener_ticket(ticket_id)


def estadisticas(empresa_id):
    conn = get_connection()
    por_estado = {r["estado"]: r["n"] for r in conn.execute(
        "SELECT estado, COUNT(*) n FROM tickets WHERE empresa_id = ? GROUP BY estado", (empresa_id,)
    ).fetchall()}
    urgentes_abiertos = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE empresa_id = ? AND prioridad = 'urgente' AND estado NOT IN ('resuelto','cerrado')",
        (empresa_id,),
    ).fetchone()[0]
    tiempos = conn.execute(
        "SELECT creado_en, resuelto_en FROM tickets WHERE empresa_id = ? AND resuelto_en IS NOT NULL", (empresa_id,)
    ).fetchall()
    conn.close()

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
