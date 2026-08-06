"""
Capa de datos para el sistema de tickets de TI.
Usa SQLite (un solo archivo, sin servidor de base de datos que instalar).
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "tickets.db"

ESTADOS = ["abierto", "en_progreso", "resuelto", "cerrado"]
PRIORIDADES = ["baja", "media", "alta", "urgente"]
CATEGORIAS = ["hardware", "software", "red", "accesos", "otro"]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            titulo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'otro',
            prioridad TEXT NOT NULL DEFAULT 'media',
            estado TEXT NOT NULL DEFAULT 'abierto',
            solicitante TEXT NOT NULL,
            asignado_a TEXT,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL,
            resuelto_en TEXT
        );

        CREATE TABLE IF NOT EXISTS comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            autor TEXT NOT NULL,
            texto TEXT NOT NULL,
            creado_en TEXT NOT NULL
        );
    """)
    conn.commit()

    # Sembrar datos de ejemplo solo la primera vez
    count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    if count == 0:
        _seed(conn)
    conn.close()


def _next_folio(conn):
    row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
    return f"TI-{row[0] + 1:04d}"


def _seed(conn):
    ejemplos = [
        ("No enciende mi computadora", "La torre no prende desde esta mañana, revisé el cable de poder.", "hardware", "urgente", "abierto", "Ana López", None),
        ("Solicito acceso a carpeta de Finanzas", "Necesito acceso de lectura a \\\\servidor\\finanzas para el cierre de mes.", "accesos", "media", "en_progreso", "Carlos Ruiz", "Mario (TI)"),
        ("VPN se desconecta cada 10 minutos", "Trabajando desde casa, la VPN se cae constantemente desde ayer.", "red", "alta", "abierto", "Sofía Martínez", None),
        ("Instalar Office en equipo nuevo", "Llegó laptop nueva, falta activar el paquete Office.", "software", "baja", "resuelto", "Diego Torres", "Mario (TI)"),
        ("Impresora del 2do piso sin tóner", "La impresora HP del área de ventas marca tóner bajo.", "hardware", "baja", "cerrado", "Recepción", "Laura (TI)"),
    ]
    now = datetime.now().isoformat(timespec="seconds")
    for titulo, desc, cat, pri, estado, solicitante, asignado in ejemplos:
        conn.execute(
            """INSERT INTO tickets
               (folio, titulo, descripcion, categoria, prioridad, estado, solicitante, asignado_a, creado_en, actualizado_en, resuelto_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_next_folio(conn), titulo, desc, cat, pri, estado, solicitante, asignado, now, now,
             now if estado in ("resuelto", "cerrado") else None),
        )
    conn.commit()


# ---- Operaciones ----

def listar_tickets(estado=None, prioridad=None, categoria=None):
    conn = get_connection()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if estado:
        query += " AND estado = ?"
        params.append(estado)
    if prioridad:
        query += " AND prioridad = ?"
        params.append(prioridad)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    query += " ORDER BY CASE prioridad WHEN 'urgente' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, creado_en DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_ticket(ticket_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        conn.close()
        return None
    ticket = dict(row)
    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE ticket_id = ? ORDER BY creado_en ASC", (ticket_id,)
    ).fetchall()
    ticket["comentarios"] = [dict(c) for c in comentarios]
    conn.close()
    return ticket


def crear_ticket(titulo, descripcion, categoria, prioridad, solicitante):
    conn = get_connection()
    folio = _next_folio(conn)
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO tickets
           (folio, titulo, descripcion, categoria, prioridad, estado, solicitante, creado_en, actualizado_en)
           VALUES (?, ?, ?, ?, ?, 'abierto', ?, ?, ?)""",
        (folio, titulo, descripcion, categoria, prioridad, solicitante, now, now),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()
    return obtener_ticket(ticket_id)


def actualizar_ticket(ticket_id, estado=None, prioridad=None, asignado_a=None):
    conn = get_connection()
    existente = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existente:
        conn.close()
        return None

    now = datetime.now().isoformat(timespec="seconds")
    campos, valores = [], []

    if estado is not None:
        campos.append("estado = ?"); valores.append(estado)
        if estado in ("resuelto", "cerrado"):
            campos.append("resuelto_en = ?"); valores.append(now)
        else:
            campos.append("resuelto_en = NULL")
    if prioridad is not None:
        campos.append("prioridad = ?"); valores.append(prioridad)
    if asignado_a is not None:
        campos.append("asignado_a = ?"); valores.append(asignado_a)

    campos.append("actualizado_en = ?"); valores.append(now)
    valores.append(ticket_id)

    conn.execute(f"UPDATE tickets SET {', '.join(campos)} WHERE id = ?", valores)
    conn.commit()
    conn.close()
    return obtener_ticket(ticket_id)


def agregar_comentario(ticket_id, autor, texto):
    conn = get_connection()
    existente = conn.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not existente:
        conn.close()
        return None
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO comentarios (ticket_id, autor, texto, creado_en) VALUES (?, ?, ?, ?)",
        (ticket_id, autor, texto, now),
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
    tiempos = conn.execute(
        """SELECT creado_en, resuelto_en FROM tickets
           WHERE resuelto_en IS NOT NULL"""
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
