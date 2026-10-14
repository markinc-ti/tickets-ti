"""
Usuarios de Microsip y sus derechos (solo lectura).

Microsip guarda los usuarios, roles y derechos en la base del sistema
(carpeta de datos → System\\Config.fdb), no en la base de la empresa. Como
la estructura exacta de esa base no está documentada, aquí se lee de forma
genérica:

- la tabla USUARIOS (sin contraseñas ni tokens);
- EMPRESAS (para mostrar nombres);
- todas las tablas que apuntan a USUARIOS por llave foránea o que tienen una
  columna USUARIO_ID / ROL_ID (ahí viven los derechos y el acceso a empresas);
- los catálogos a los que apuntan esas tablas (para mostrar nombres en lugar
  de números).

También se leen los permisos de Firebird (GRANT) de la base de la empresa.
Nunca escribe nada.
"""
import ntpath
import re

import fdb

import microsip

SENSIBLES = re.compile(r"PASS|CONTRAS|TOKEN|HASH|SALT|SECRET|PWD|CLAVE_ACCESO|LLAVE", re.I)
MAX_FILAS = 20000


def _conectar(cfg, ruta):
    microsip._asegurar_cargado()
    usuario = cfg.get("microsip_escritura_usuario") or cfg["microsip_usuario"]
    password = cfg.get("microsip_escritura_password") if cfg.get("microsip_escritura_usuario") else cfg["microsip_password"]
    host = cfg["microsip_host"]
    puerto = cfg.get("microsip_puerto") or 3050
    return fdb.connect(dsn=f"{host}/{puerto}:{ruta}", user=usuario, password=password or "", charset="ISO8859_1")


def rutas_candidatas(ruta_empresa, ruta_manual=None):
    """C:\\Microsip datos\\EMPRESA.FDB → C:\\Microsip datos\\System\\Config.fdb (y variantes)."""
    if ruta_manual:
        return [ruta_manual.strip()]
    r = (ruta_empresa or "").strip()
    win = "\\" in r or re.match(r"^[A-Za-z]:", r)
    sep = "\\" if win else "/"
    carpeta = ntpath.dirname(r) if win else r.rsplit("/", 1)[0]
    padre = ntpath.dirname(carpeta) if win else carpeta.rsplit("/", 1)[0]
    salida = []
    for base in (carpeta, padre):
        if not base:
            continue
        for sub in ("System", "SYSTEM", "Sistema"):
            for nom in ("Config.fdb", "CONFIG.FDB"):
                p = f"{base}{sep}{sub}{sep}{nom}"
                if p not in salida:
                    salida.append(p)
    return salida


def _valor(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    if isinstance(v, (bytes, bytearray)):
        try:
            t = bytes(v).decode("latin-1")
            return t if t.isprintable() else f"[binario {len(v)} bytes]"
        except Exception:
            return f"[binario {len(v)} bytes]"
    if hasattr(v, "read"):  # BlobReader
        try:
            return _valor(v.read())
        except Exception:
            return "[blob]"
    return str(v)


def _tablas(cur):
    cur.execute("""SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
                   WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0 AND RDB$VIEW_BLR IS NULL ORDER BY 1""")
    return [r[0] for r in cur.fetchall()]


def _columnas(cur, tabla):
    cur.execute("""SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS
                   WHERE RDB$RELATION_NAME = ? ORDER BY RDB$FIELD_POSITION""", (tabla,))
    return [r[0] for r in cur.fetchall()]


def _llaves_foraneas(cur):
    """[(tabla, columna, tabla_ref, columna_ref)]"""
    cur.execute("""
        SELECT TRIM(RC.RDB$RELATION_NAME), TRIM(S.RDB$FIELD_NAME), TRIM(RC2.RDB$RELATION_NAME), TRIM(S2.RDB$FIELD_NAME)
        FROM RDB$RELATION_CONSTRAINTS RC
        JOIN RDB$REF_CONSTRAINTS REF ON REF.RDB$CONSTRAINT_NAME = RC.RDB$CONSTRAINT_NAME
        JOIN RDB$RELATION_CONSTRAINTS RC2 ON RC2.RDB$CONSTRAINT_NAME = REF.RDB$CONST_NAME_UQ
        JOIN RDB$INDEX_SEGMENTS S ON S.RDB$INDEX_NAME = RC.RDB$INDEX_NAME
        JOIN RDB$INDEX_SEGMENTS S2 ON S2.RDB$INDEX_NAME = RC2.RDB$INDEX_NAME AND S2.RDB$FIELD_POSITION = S.RDB$FIELD_POSITION
        WHERE RC.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'""")
    return [tuple(r) for r in cur.fetchall()]


def _llave_primaria(cur, tabla):
    cur.execute("""SELECT TRIM(S.RDB$FIELD_NAME) FROM RDB$RELATION_CONSTRAINTS RC
                   JOIN RDB$INDEX_SEGMENTS S ON S.RDB$INDEX_NAME = RC.RDB$INDEX_NAME
                   WHERE RC.RDB$RELATION_NAME = ? AND RC.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
                   ORDER BY S.RDB$FIELD_POSITION""", (tabla,))
    return [r[0] for r in cur.fetchall()]


def _leer(cur, tabla, limite=MAX_FILAS):
    cols = [c for c in _columnas(cur, tabla) if not SENSIBLES.search(c)]
    if not cols:
        return [], []
    cur.execute(f'SELECT FIRST {int(limite)} ' + ", ".join(f'"{c}"' for c in cols) + f' FROM "{tabla}"')
    return cols, [dict(zip(cols, (_valor(v) for v in fila))) for fila in cur.fetchall()]


def _columna_nombre(cols):
    for c in ("NOMBRE", "DESCRIPCION", "NOMBRE_CORTO", "DESCRIP", "CLAVE", "NOMBRE_EMPRESA"):
        if c in cols:
            return c
    otras = [c for c in cols if "NOMBRE" in c or "DESCRIP" in c]
    return otras[0] if otras else None


def _contar(cur, tabla):
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{tabla}"')
        return cur.fetchone()[0]
    except Exception:
        return None


def leer_config(cfg, ruta_manual=None):
    """Lee usuarios, roles, empresas y derechos de la base del sistema de Microsip."""
    errores = []
    con = ruta = None
    for r in rutas_candidatas(cfg.get("microsip_ruta_db"), ruta_manual):
        try:
            con = _conectar(cfg, r)
            ruta = r
            break
        except Exception as e:
            errores.append(f"{r}: {str(e).splitlines()[-1] if str(e) else e}")
    if con is None:
        raise RuntimeError("No se pudo abrir la base del sistema de Microsip (Config.fdb). Probé: " + " | ".join(errores)
                           + ". Escribe la ruta exacta (en el servidor de Microsip: carpeta de datos → System → Config.fdb).")
    try:
        cur = con.cursor()
        tablas = _tablas(cur)
        catalogo = [{"tabla": t, "columnas": _columnas(cur, t), "filas": _contar(cur, t)} for t in tablas]
        if "USUARIOS" not in tablas:
            return {"ruta": ruta, "catalogo": catalogo, "usuarios": [], "relacionadas": [],
                    "aviso": "Esa base no tiene tabla USUARIOS; revisa la ruta."}
        fks = _llaves_foraneas(cur)
        cols_u, usuarios = _leer(cur, "USUARIOS")
        pk_u = (_llave_primaria(cur, "USUARIOS") or ["USUARIO_ID"])[0]

        # Tablas ligadas a usuarios: por llave foránea o por nombre de columna.
        ligadas = {}
        for t, c, tr, cr in fks:
            if tr == "USUARIOS" and t != "USUARIOS":
                ligadas.setdefault(t, set()).add(c)
        for info in catalogo:
            t = info["tabla"]
            if t == "USUARIOS":
                continue
            for c in info["columnas"]:
                if c in ("USUARIO_ID", "ROL_ID") or (c.endswith("_USUARIO_ID")):
                    ligadas.setdefault(t, set()).add(c)

        # Catálogos para traducir *_ID a nombre.
        cache_cat = {}

        def traductor(tabla_ref, col_ref):
            clave = (tabla_ref, col_ref)
            if clave not in cache_cat:
                try:
                    cols, filas = _leer(cur, tabla_ref)
                    nom = _columna_nombre(cols)
                    mod = next((c for c in cols if c in ("SISTEMA", "MODULO", "APLICACION", "GRUPO")), None)
                    cache_cat[clave] = {f.get(col_ref): (f"{f.get(mod)} · {f.get(nom)}" if mod and f.get(mod) else f.get(nom))
                                        for f in filas} if nom else {}
                except Exception:
                    cache_cat[clave] = {}
            return cache_cat[clave]

        fk_por_tabla = {}
        for t, c, tr, cr in fks:
            fk_por_tabla.setdefault(t, []).append((c, tr, cr))

        relacionadas = []
        for t, cols_lig in sorted(ligadas.items()):
            try:
                cols, filas = _leer(cur, t)
            except Exception as e:
                relacionadas.append({"tabla": t, "error": str(e)})
                continue
            traducciones = {}
            for c, tr, cr in fk_por_tabla.get(t, []):
                if tr != "USUARIOS":
                    traducciones[c] = traductor(tr, cr)
            for f in filas:
                for c, mapa in traducciones.items():
                    if f.get(c) in mapa and mapa[f.get(c)] is not None:
                        f[c + "__NOMBRE"] = mapa[f.get(c)]
            relacionadas.append({"tabla": t, "columnas_usuario": sorted(cols_lig), "columnas": cols,
                                 "traducidas": sorted(traducciones), "filas": filas})

        empresas = []
        if "EMPRESAS" in tablas:
            cols_e, empresas = _leer(cur, "EMPRESAS")
        return {"ruta": ruta, "llave_usuario": pk_u, "columnas_usuarios": cols_u, "usuarios": usuarios,
                "empresas": empresas, "relacionadas": relacionadas, "catalogo": catalogo,
                "llaves_foraneas": [list(x) for x in fks]}
    finally:
        con.close()


def permisos_firebird(cfg):
    """GRANTs de la base de la empresa, agrupados por usuario/rol y privilegio."""
    con = _conectar(cfg, cfg["microsip_ruta_db"])
    try:
        cur = con.cursor()
        cur.execute("""SELECT TRIM(RDB$USER), TRIM(RDB$PRIVILEGE), COUNT(DISTINCT RDB$RELATION_NAME)
                       FROM RDB$USER_PRIVILEGES
                       WHERE RDB$USER NOT IN ('SYSDBA', 'PUBLIC') AND RDB$USER_TYPE IN (8, 13)
                       GROUP BY 1, 2 ORDER BY 1, 2""")
        grants = {}
        for u, p, n in cur.fetchall():
            grants.setdefault(u, {})[p] = n
        roles = []
        try:
            cur.execute("SELECT TRIM(RDB$ROLE_NAME), TRIM(RDB$OWNER_NAME) FROM RDB$ROLES WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0")
            roles = [{"rol": r, "dueno": o} for r, o in cur.fetchall()]
        except Exception:
            pass
        usuarios_servidor = None
        try:
            cur.execute("SELECT TRIM(SEC$USER_NAME), SEC$ACTIVE, TRIM(SEC$FIRST_NAME), TRIM(SEC$LAST_NAME) FROM SEC$USERS")
            usuarios_servidor = [{"usuario": u, "activo": a, "nombre": " ".join(x for x in (n, ap) if x)} for u, a, n, ap in cur.fetchall()]
        except Exception:
            pass  # Firebird 2.5 no tiene SEC$USERS
        return {"grants": grants, "roles": roles, "usuarios_servidor": usuarios_servidor}
    finally:
        con.close()
