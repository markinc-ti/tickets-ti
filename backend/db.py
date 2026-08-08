"""
Capa de datos para el sistema de tickets de TI.
Usuarios con login (contraseñas con hash vía auth.hash_password),
departamentos como lista fija, tickets y comentarios ligados a
usuarios reales (no texto libre).
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import auth

DB_PATH = Path(__file__).parent / "tickets.db"

ESTADOS = ["abierto", "en_progreso", "resuelto", "cerrado"]
PRIORIDADES = ["baja", "media", "alta", "urgente"]
CATEGORIAS = ["hardware", "software", "red", "accesos", "otro"]
ROLES = ["admin", "tecnico", "usuario"]
DEPARTAMENTOS = [
    "Ventas", "Producción", "Almacén", "Contabilidad",
    "Recursos Humanos", "Dirección", "Sistemas", "Otro",
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'usuario',
            telefono_whatsapp TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            departamento TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'otro',
            prioridad TEXT NOT NULL DEFAULT 'media',
            estado TEXT NOT NULL DEFAULT 'abierto',
            solicitante_id INTEGER NOT NULL REFERENCES users(id),
            asignado_a_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL,
            resuelto_en TEXT
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

    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO users (username, password_hash, nombre_completo, rol, creado_en) VALUES (?, ?, ?, 'admin', ?)",
            ("admin", auth.hash_password("cambiar123"), "Administrador", now),
        )
        conn.commit()
    conn.close()


# ---- Usuarios ----

def obtener_usuario_por_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_usuarios():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, nombre_completo, rol, telefono_whatsapp, activo, creado_en FROM users ORDER BY nombre_completo"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_tecnicos_activos():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, nombre_completo, telefono_whatsapp FROM users WHERE rol IN ('tecnico','admin') AND activo = 1 ORDER BY nombre_completo"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_usuario(username, password, nombre_completo, rol, telefono_whatsapp=None):
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, nombre_completo, rol, telefono_whatsapp, creado_en) VALUES (?, ?, ?, ?, ?, ?)",
        (username, auth.hash_password(password), nombre_completo, rol, telefono_whatsapp, now),
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
    """Desactiva al usuario (no se borra de verdad, para no romper tickets/comentarios existentes)."""
    conn = get_connection()
    conn.execute("UPDATE users SET activo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()


# ---- Tickets ----

def _ticket_query_base():
    return """
        SELECT t.*, s.nombre_completo AS solicitante_nombre,
               a.nombre_completo AS asignado_a_nombre
        FROM tickets t
        JOIN users s ON s.id = t.solicitante_id
        LEFT JOIN users a ON a.id = t.asignado_a_id
    """


def _next_folio(conn):
    row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
    return f"TI-{row[0] + 1:04d}"


def listar_tickets(estado=None, prioridad=None, categoria=None, solicitante_id=None):
    conn = get_connection()
    query = _ticket_query_base() + " WHERE 1=1"
    params = []
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


def obtener_ticket(ticket_id):
    conn = get_connection()
    row = conn.execute(_ticket_query_base() + " WHERE t.id = ?", (ticket_id,)).fetchone()
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


def crear_ticket(departamento, descripcion, categoria, prioridad, usuario_id):
    conn = get_connection()
    folio = _next_folio(conn)
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO tickets
           (folio, departamento, descripcion, categoria, prioridad, estado, solicitante_id, creado_en, actualizado_en)
           VALUES (?, ?, ?, ?, ?, 'abierto', ?, ?, ?)""",
        (folio, departamento, descripcion, categoria, prioridad, usuario_id, now, now),
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


def estadisticas():
    conn = get_connection()
    por_estado = {r["estado"]: r["n"] for r in conn.execute(
        "SELECT estado, COUNT(*) n FROM tickets GROUP BY estado"
    ).fetchall()}
    urgentes_abiertos = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE prioridad = 'urgente' AND estado NOT IN ('resuelto','cerrado')"
    ).fetchone()[0]
    tiempos = conn.execute("SELECT creado_en, resuelto_en FROM tickets WHERE resuelto_en IS NOT NULL").fetchall()
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
