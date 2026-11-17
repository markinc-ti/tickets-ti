"""Portal de bienvenida para clientes (doctores): base de datos.

Los clientes que compraron una unidad dental entran a /bienvenida, escriben el folio
de su pedido, factura o remisión de Microsip y ven SOLO los manuales y videos de los
equipos que compraron. Logística administra los equipos, sus manuales/videos y las
reglas que ligan cada equipo con los artículos de Microsip.

Las tablas se crean solas la primera vez que se usan (asegurar_tablas), para no
tocar db.init_db.
"""
import re
import secrets
import threading
import unicodedata

from db import get_connection

_LISTO = False
_CANDADO = threading.Lock()


def asegurar_tablas():
    global _LISTO
    if _LISTO:
        return
    with _CANDADO:
        if _LISTO:
            return
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manuales_config (
                empresa_id INTEGER PRIMARY KEY REFERENCES empresas(id),
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                codigo TEXT UNIQUE NOT NULL,
                titulo TEXT,
                mensaje TEXT,
                whatsapp TEXT,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS manuales_equipos (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES empresas(id),
                nombre TEXT NOT NULL,
                descripcion TEXT,
                categoria TEXT,
                para_todos BOOLEAN NOT NULL DEFAULT FALSE,
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                orden INTEGER NOT NULL DEFAULT 0,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS manuales_reglas (
                id SERIAL PRIMARY KEY,
                equipo_id INTEGER NOT NULL REFERENCES manuales_equipos(id) ON DELETE CASCADE,
                tipo TEXT NOT NULL CHECK (tipo IN ('articulo', 'clave', 'texto')),
                valor TEXT NOT NULL,
                articulo_id BIGINT,
                etiqueta TEXT
            );
            CREATE TABLE IF NOT EXISTS manuales_recursos (
                id SERIAL PRIMARY KEY,
                equipo_id INTEGER NOT NULL REFERENCES manuales_equipos(id) ON DELETE CASCADE,
                tipo TEXT NOT NULL CHECK (tipo IN ('pdf', 'video', 'link')),
                titulo TEXT NOT NULL,
                url TEXT,
                r2_key TEXT,
                archivo_base64 TEXT,
                archivo_nombre TEXT,
                tamano BIGINT,
                orden INTEGER NOT NULL DEFAULT 0,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS manuales_ligas (
                token TEXT PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES empresas(id),
                folio TEXT NOT NULL,
                cliente_nombre TEXT,
                telefono TEXT,
                creado_por INTEGER,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                visitas INTEGER NOT NULL DEFAULT 0,
                ultima_visita TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS manuales_consultas (
                id BIGSERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES empresas(id),
                folio TEXT,
                origen TEXT,
                encontrado BOOLEAN,
                equipos TEXT,
                ip TEXT,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_manuales_equipos_emp ON manuales_equipos (empresa_id);
            CREATE INDEX IF NOT EXISTS idx_manuales_reglas_eq ON manuales_reglas (equipo_id);
            CREATE INDEX IF NOT EXISTS idx_manuales_recursos_eq ON manuales_recursos (equipo_id);
            CREATE INDEX IF NOT EXISTS idx_manuales_consultas_emp ON manuales_consultas (empresa_id, creado_en DESC);
        """)
        conn.commit()
        cur.close(); conn.close()
        _LISTO = True


def _slug(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "clientes"


def _codigo_valido(codigo):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", codigo or ""))


# ---------------------------------------------------------------- configuración

def obtener_config(empresa_id, crear=True):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM manuales_config WHERE empresa_id = %s", (empresa_id,))
    r = cur.fetchone()
    if not r and crear:
        cur.execute("SELECT nombre FROM empresas WHERE id = %s", (empresa_id,))
        e = cur.fetchone()
        base = _slug(e["nombre"] if e else "")
        codigo = base
        cur.execute("SELECT 1 FROM manuales_config WHERE codigo = %s", (codigo,))
        if cur.fetchone():
            codigo = f"{base}-{empresa_id}"
        cur.execute("""INSERT INTO manuales_config (empresa_id, codigo, titulo, mensaje)
                       VALUES (%s, %s, %s, %s) ON CONFLICT (empresa_id) DO NOTHING""",
                    (empresa_id, codigo, "¡Bienvenido a la familia!",
                     "Gracias por confiar en nosotros. Aquí encontrarás los manuales y videos de los equipos que "
                     "compraste. Escribe el folio de tu pedido, factura o remisión para verlos."))
        conn.commit()
        cur.execute("SELECT * FROM manuales_config WHERE empresa_id = %s", (empresa_id,))
        r = cur.fetchone()
    cur.close(); conn.close()
    return dict(r) if r else None


def guardar_config(empresa_id, activo, codigo, titulo, mensaje, whatsapp):
    obtener_config(empresa_id)
    codigo = (codigo or "").strip().lower()
    if not _codigo_valido(codigo):
        raise ValueError("El código de la liga solo puede llevar letras minúsculas, números y guiones (2 a 41 caracteres).")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT empresa_id FROM manuales_config WHERE codigo = %s AND empresa_id <> %s", (codigo, empresa_id))
    if cur.fetchone():
        cur.close(); conn.close()
        raise ValueError("Ese código ya lo usa otra empresa. Elige otro.")
    cur.execute("""UPDATE manuales_config SET activo = %s, codigo = %s, titulo = %s, mensaje = %s, whatsapp = %s
                   WHERE empresa_id = %s""", (activo, codigo, titulo, mensaje, whatsapp, empresa_id))
    conn.commit()
    cur.close(); conn.close()
    return obtener_config(empresa_id)


def config_publica(codigo=None):
    """Busca el portal por su código. Sin código: el primer portal activo (el de la
    empresa que lo activó primero) — así la liga corta /bienvenida sirve para el QR."""
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    if codigo:
        cur.execute("""SELECT c.*, e.nombre AS empresa_nombre, e.color_acento FROM manuales_config c
                       JOIN empresas e ON e.id = c.empresa_id WHERE c.codigo = %s AND c.activo AND e.activo""",
                    ((codigo or "").strip().lower(),))
    else:
        cur.execute("""SELECT c.*, e.nombre AS empresa_nombre, e.color_acento FROM manuales_config c
                       JOIN empresas e ON e.id = c.empresa_id WHERE c.activo AND e.activo
                       ORDER BY c.creado_en, c.empresa_id LIMIT 1""")
    r = cur.fetchone()
    cur.close(); conn.close()
    return dict(r) if r else None


def logo_empresa(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT logo_base64 FROM empresas WHERE id = %s", (empresa_id,))
    r = cur.fetchone()
    cur.close(); conn.close()
    return r["logo_base64"] if r else None


# ---------------------------------------------------------------- equipos, reglas y recursos

def listar_equipos(empresa_id, solo_activos=False):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""SELECT * FROM manuales_equipos WHERE empresa_id = %s {"AND activo" if solo_activos else ""}
                    ORDER BY orden, nombre""", (empresa_id,))
    equipos = [dict(x) for x in cur.fetchall()]
    ids = [e["id"] for e in equipos]
    reglas, recursos = {}, {}
    if ids:
        cur.execute("SELECT * FROM manuales_reglas WHERE equipo_id = ANY(%s) ORDER BY id", (ids,))
        for x in cur.fetchall():
            reglas.setdefault(x["equipo_id"], []).append(dict(x))
        cur.execute("""SELECT id, equipo_id, tipo, titulo, url, r2_key, archivo_nombre, tamano, orden,
                              (archivo_base64 IS NOT NULL) AS en_base
                       FROM manuales_recursos WHERE equipo_id = ANY(%s) ORDER BY orden, id""", (ids,))
        for x in cur.fetchall():
            recursos.setdefault(x["equipo_id"], []).append(dict(x))
    cur.close(); conn.close()
    for e in equipos:
        e["reglas"] = reglas.get(e["id"], [])
        e["recursos"] = recursos.get(e["id"], [])
    return equipos


def obtener_equipo(empresa_id, equipo_id):
    for e in listar_equipos(empresa_id):
        if e["id"] == equipo_id:
            return e
    return None


def _guardar_reglas(cur, equipo_id, reglas):
    cur.execute("DELETE FROM manuales_reglas WHERE equipo_id = %s", (equipo_id,))
    for r in reglas or []:
        valor = (r.get("valor") or "").strip()
        if not valor:
            continue
        cur.execute("""INSERT INTO manuales_reglas (equipo_id, tipo, valor, articulo_id, etiqueta)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (equipo_id, r["tipo"], valor, r.get("articulo_id"), (r.get("etiqueta") or "").strip() or None))


def crear_equipo(empresa_id, datos):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO manuales_equipos (empresa_id, nombre, descripcion, categoria, para_todos, activo, orden)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (empresa_id, datos["nombre"], datos.get("descripcion"), datos.get("categoria"),
                 datos.get("para_todos", False), datos.get("activo", True), datos.get("orden", 0)))
    nuevo = cur.fetchone()["id"]
    _guardar_reglas(cur, nuevo, datos.get("reglas"))
    conn.commit()
    cur.close(); conn.close()
    return nuevo


def editar_equipo(empresa_id, equipo_id, datos):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""UPDATE manuales_equipos SET nombre = %s, descripcion = %s, categoria = %s, para_todos = %s,
                          activo = %s, orden = %s
                   WHERE id = %s AND empresa_id = %s""",
                (datos["nombre"], datos.get("descripcion"), datos.get("categoria"), datos.get("para_todos", False),
                 datos.get("activo", True), datos.get("orden", 0), equipo_id, empresa_id))
    ok = cur.rowcount == 1
    if ok:
        _guardar_reglas(cur, equipo_id, datos.get("reglas"))
    conn.commit()
    cur.close(); conn.close()
    return ok


def eliminar_equipo(empresa_id, equipo_id):
    """Regresa las llaves de R2 de sus archivos, para borrarlos también de R2."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT r.r2_key FROM manuales_recursos r JOIN manuales_equipos e ON e.id = r.equipo_id
                   WHERE e.id = %s AND e.empresa_id = %s AND r.r2_key IS NOT NULL""", (equipo_id, empresa_id))
    llaves = [x["r2_key"] for x in cur.fetchall()]
    cur.execute("DELETE FROM manuales_equipos WHERE id = %s AND empresa_id = %s", (equipo_id, empresa_id))
    ok = cur.rowcount == 1
    conn.commit()
    cur.close(); conn.close()
    return ok, llaves


def agregar_recurso(empresa_id, equipo_id, tipo, titulo, url=None, r2_key=None, archivo_base64=None,
                    archivo_nombre=None, tamano=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM manuales_equipos WHERE id = %s AND empresa_id = %s", (equipo_id, empresa_id))
    if not cur.fetchone():
        cur.close(); conn.close()
        return None
    cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 AS siguiente FROM manuales_recursos WHERE equipo_id = %s", (equipo_id,))
    orden = cur.fetchone()["siguiente"]
    cur.execute("""INSERT INTO manuales_recursos (equipo_id, tipo, titulo, url, r2_key, archivo_base64, archivo_nombre,
                                                  tamano, orden)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (equipo_id, tipo, titulo, url, r2_key, archivo_base64, archivo_nombre, tamano, orden))
    nuevo = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return nuevo


def _recurso_de_empresa(cur, empresa_id, recurso_id):
    cur.execute("""SELECT r.* FROM manuales_recursos r JOIN manuales_equipos e ON e.id = r.equipo_id
                   WHERE r.id = %s AND e.empresa_id = %s""", (recurso_id, empresa_id))
    r = cur.fetchone()
    return dict(r) if r else None


def editar_recurso(empresa_id, recurso_id, titulo, orden, url=None):
    conn = get_connection()
    cur = conn.cursor()
    rec = _recurso_de_empresa(cur, empresa_id, recurso_id)
    if not rec:
        cur.close(); conn.close()
        return False
    nueva_url = url if (url and rec["tipo"] in ("video", "link")) else rec["url"]
    cur.execute("UPDATE manuales_recursos SET titulo = %s, orden = %s, url = %s WHERE id = %s",
                (titulo, orden, nueva_url, recurso_id))
    conn.commit()
    cur.close(); conn.close()
    return True


def eliminar_recurso(empresa_id, recurso_id):
    conn = get_connection()
    cur = conn.cursor()
    rec = _recurso_de_empresa(cur, empresa_id, recurso_id)
    if not rec:
        cur.close(); conn.close()
        return False, None
    cur.execute("DELETE FROM manuales_recursos WHERE id = %s", (recurso_id,))
    conn.commit()
    cur.close(); conn.close()
    return True, rec.get("r2_key")


def archivo_recurso(recurso_id):
    """Para la descarga pública firmada (PDF guardado en la base, sin R2)."""
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT archivo_base64, archivo_nombre, url FROM manuales_recursos WHERE id = %s AND tipo = 'pdf'",
                (recurso_id,))
    r = cur.fetchone()
    cur.close(); conn.close()
    return dict(r) if r else None


# ---------------------------------------------------------------- ligas personales (WhatsApp) y bitácora

def crear_liga(empresa_id, folio, cliente_nombre, telefono, usuario_id):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT token FROM manuales_ligas WHERE empresa_id = %s AND folio = %s
                   ORDER BY creado_en DESC LIMIT 1""", (empresa_id, folio))
    r = cur.fetchone()
    if r:
        token = r["token"]
        cur.execute("UPDATE manuales_ligas SET cliente_nombre = %s, telefono = %s WHERE token = %s",
                    (cliente_nombre, telefono, token))
    else:
        token = secrets.token_urlsafe(9)
        cur.execute("""INSERT INTO manuales_ligas (token, empresa_id, folio, cliente_nombre, telefono, creado_por)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (token, empresa_id, folio, cliente_nombre, telefono, usuario_id))
    conn.commit()
    cur.close(); conn.close()
    return token


def obtener_liga(token):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM manuales_ligas WHERE token = %s", (token,))
    r = cur.fetchone()
    if r:
        cur.execute("UPDATE manuales_ligas SET visitas = visitas + 1, ultima_visita = NOW() WHERE token = %s", (token,))
        conn.commit()
    cur.close(); conn.close()
    return dict(r) if r else None


def listar_ligas(empresa_id, limite=100):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT l.token, l.folio, l.cliente_nombre, l.telefono, l.creado_en, l.visitas, l.ultima_visita,
                          u.nombre_completo AS creado_por_nombre
                   FROM manuales_ligas l LEFT JOIN users u ON u.id = l.creado_por
                   WHERE l.empresa_id = %s ORDER BY l.creado_en DESC LIMIT %s""", (empresa_id, int(limite)))
    r = [dict(x) for x in cur.fetchall()]
    cur.close(); conn.close()
    return r


def registrar_consulta(empresa_id, folio, origen, encontrado, equipos, ip):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""INSERT INTO manuales_consultas (empresa_id, folio, origen, encontrado, equipos, ip)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (empresa_id, (folio or "")[:40], origen, encontrado, (equipos or "")[:500], (ip or "")[:60]))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print(f"[manuales] no se pudo registrar la consulta: {e}")


def listar_consultas(empresa_id, limite=200):
    asegurar_tablas()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""SELECT folio, origen, encontrado, equipos, creado_en FROM manuales_consultas
                   WHERE empresa_id = %s ORDER BY creado_en DESC LIMIT %s""", (empresa_id, int(limite)))
    r = [dict(x) for x in cur.fetchall()]
    cur.close(); conn.close()
    return r
