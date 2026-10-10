"""
Escritura a Microsip (Firebird): dar de alta / completar clientes y crear
cotizaciones (DOCTOS_VE tipo 'C') cuando el cliente acepta una cotización
en la app.

Cómo se hace sin romper Microsip:
- Todo va en UNA transacción: si algo falla, no queda nada a medias.
- No se adivinan las columnas: se leen del catálogo de Firebird. Las
  columnas obligatorias que la app no conoce se llenan copiando el último
  registro del mismo tipo (la última cotización, el último cliente) solo
  para catálogos (moneda, condición de pago, almacén, sucursal…) y banderas
  de una letra; los importes desconocidos van en 0 y las fechas con hoy.
- IDs con los generadores de Microsip (ID_DOCTOS / ID_CATALOGOS); si no
  existen, se manda -1 y el trigger de Microsip lo asigna.
- Folio con FOLIOS_VENTAS (serie + consecutivo), saltando los ya usados.
- Totales con el procedimiento de Microsip CALC_TOTALES_DOCTO_VE; si no
  existe, se calculan aquí con el IVA de cada artículo.
- probar=True hace exactamente lo mismo y al final deshace todo (ROLLBACK):
  así se ve si Microsip lo acepta sin dejar nada guardado.
"""
import datetime
import difflib
import re
import unicodedata

import fdb

import microsip

# Tipos de RDB$FIELDS.RDB$FIELD_TYPE
_NUMERICOS = {7, 8, 16, 10, 27, 9, 11}
_FECHAS = {12, 13, 35}
_TEXTO = {14, 37, 40}
_BLOB = {261}

RFC_GENERICOS = {"XAXX010101000", "XEXX010101000"}
USUARIO_APP = "TICKETS-TI"

_PALABRAS_VACIAS = {"SA", "DE", "CV", "S", "A", "C", "V", "SAPI", "RL", "SC", "SRL", "SPR", "AC", "SAS",
                    "Y", "LA", "EL", "LOS", "LAS", "DEL", "MI", "SOCIEDAD", "ANONIMA", "CAPITAL", "VARIABLE"}


class ErrorMicrosip(Exception):
    """Error con el paso donde ocurrió, para mostrarlo claro en pantalla."""
    def __init__(self, paso, detalle):
        self.paso = paso
        self.detalle = detalle
        super().__init__(f"{paso}: {detalle}")


# ---------------------------------------------------------------- conexión

def _conectar(config):
    microsip._asegurar_cargado()
    usuario = config.get("microsip_escritura_usuario") or config["microsip_usuario"]
    password = config.get("microsip_escritura_password") if config.get("microsip_escritura_usuario") else config["microsip_password"]
    return fdb.connect(dsn=microsip._dsn(config), user=usuario, password=password or "", charset="ISO8859_1")


def _txt(v, largo=None):
    """Texto apto para Microsip (Latin-1, sin espacios de más, recortado)."""
    if v is None:
        return None
    v = " ".join(str(v).split())
    v = v.encode("latin-1", "ignore").decode("latin-1")
    if largo:
        v = v[:largo]
    return v or None


def _solo_digitos(v):
    return "".join(ch for ch in str(v or "") if ch.isdigit())


def _norm_nombre(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return [t for t in s.split() if t not in _PALABRAS_VACIAS]


def parecido_nombres(a, b):
    ta, tb = _norm_nombre(a), _norm_nombre(b)
    if not ta or not tb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    sa, sb = set(ta), set(tb)
    cubre = len(sa & sb) / min(len(sa), len(sb))
    jacc = len(sa & sb) / len(sa | sb)
    # "JUAN PEREZ" vs "JUAN PEREZ LOPEZ": todas las palabras del corto están
    # en el largo → muy parecido, aunque sobren apellidos.
    # El parecido de letras solo cuenta si es muy alto (errores de dedo); si
    # no, se requiere que compartan palabras ("ANA PRUEBA LOPEZ" no es
    # parecido a "JUAN PEREZ LOPEZ" solo por el apellido).
    return round(max(ratio if ratio >= 0.85 else 0, jacc, cubre * 0.92 if len(sa & sb) >= 2 or min(len(sa), len(sb)) == 1 else 0), 3)


# ------------------------------------------------------- catálogo Firebird

class _Esquema:
    def __init__(self, cur):
        self.cur = cur
        self._cols = {}

    def columnas(self, tabla):
        if tabla not in self._cols:
            self.cur.execute("""
                SELECT TRIM(RF.RDB$FIELD_NAME), F.RDB$FIELD_TYPE, COALESCE(F.RDB$CHARACTER_LENGTH, F.RDB$FIELD_LENGTH),
                       COALESCE(RF.RDB$NULL_FLAG, F.RDB$NULL_FLAG, 0),
                       IIF(RF.RDB$DEFAULT_SOURCE IS NULL AND F.RDB$DEFAULT_SOURCE IS NULL, 0, 1),
                       IIF(F.RDB$COMPUTED_BLR IS NULL, 0, 1)
                FROM RDB$RELATION_FIELDS RF JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
                WHERE RF.RDB$RELATION_NAME = ? ORDER BY RF.RDB$FIELD_POSITION
            """, (tabla,))
            self._cols[tabla] = {
                r[0]: {"tipo": r[1], "largo": r[2], "obligatoria": bool(r[3]), "default": bool(r[4]), "calculada": bool(r[5])}
                for r in self.cur.fetchall()
            }
        return self._cols[tabla]

    def existe(self, tabla):
        return bool(self.columnas(tabla))

    def generador(self, nombre):
        self.cur.execute("SELECT 1 FROM RDB$GENERATORS WHERE RDB$GENERATOR_NAME = ?", (nombre,))
        return bool(self.cur.fetchone())

    def procedimiento(self, nombre):
        self.cur.execute("""SELECT TRIM(RDB$PARAMETER_NAME), RDB$PARAMETER_TYPE FROM RDB$PROCEDURE_PARAMETERS
                            WHERE RDB$PROCEDURE_NAME = ? ORDER BY RDB$PARAMETER_TYPE, RDB$PARAMETER_NUMBER""", (nombre,))
        filas = self.cur.fetchall()
        self.cur.execute("SELECT 1 FROM RDB$PROCEDURES WHERE RDB$PROCEDURE_NAME = ?", (nombre,))
        if not self.cur.fetchone():
            return None
        return {"entradas": [f[0] for f in filas if f[1] == 0], "salidas": [f[0] for f in filas if f[1] == 1]}

    def fila(self, sql, params=()):
        self.cur.execute(sql, params)
        r = self.cur.fetchonemap()
        return {k: r[k] for k in r.keys()} if r else None

    def columnas_texto(self, tabla, contiene):
        return [c for c, d in self.columnas(tabla).items()
                if contiene in c and d["tipo"] in _TEXTO and not d["calculada"]]


def _ahora():
    return datetime.datetime.now().replace(microsecond=0)


def _insertar(esq, tabla, valores, plantilla=None, copiar=(), id_col=None, generador=None):
    """INSERT usando solo columnas que existen; las obligatorias que falten se
    llenan con la plantilla (catálogos y banderas), 0 (importes) u hoy (fechas).
    Regresa el ID asignado."""
    cols = esq.columnas(tabla)
    if not cols:
        raise ErrorMicrosip(f"Tabla {tabla}", "no existe en esta base de Microsip")
    plantilla = plantilla or {}
    final = {}
    for nombre, d in cols.items():
        if d["calculada"] or nombre == id_col:
            continue
        if nombre in valores:
            v = valores[nombre]
        elif nombre in copiar or any(nombre.startswith(p[:-1]) for p in copiar if p.endswith("*")):
            v = plantilla.get(nombre)
        else:
            v = None
        if v is None and d["obligatoria"] and not d["default"]:
            pv = plantilla.get(nombre)
            if d["tipo"] in _FECHAS:
                v = _ahora().date() if d["tipo"] == 12 else (_ahora().time() if d["tipo"] == 13 else _ahora())
            elif d["tipo"] in _NUMERICOS:
                v = pv if (nombre.endswith("_ID") and pv is not None) else 0
            elif pv is not None:
                v = pv
            else:
                v = "N" if (d["largo"] or 0) == 1 else ""
        if v is None:
            if nombre in valores and d["obligatoria"] and not d["default"]:
                raise ErrorMicrosip(f"Tabla {tabla}", f"falta el dato obligatorio {nombre}")
            continue
        if isinstance(v, str) and d["tipo"] in _TEXTO and d["largo"]:
            v = v[: d["largo"]]
        final[nombre] = v
    nuevo_id = None
    if id_col:
        if generador and esq.generador(generador):
            esq.cur.execute(f"SELECT GEN_ID({generador}, 1) FROM RDB$DATABASE")
            nuevo_id = esq.cur.fetchone()[0]
        else:
            nuevo_id = -1
        final = {id_col: nuevo_id, **final}
    nombres = list(final)
    sql = f"INSERT INTO {tabla} ({', '.join(nombres)}) VALUES ({', '.join('?' for _ in nombres)})"
    if id_col:
        sql += f" RETURNING {id_col}"
    esq.cur.execute(sql, [final[n] for n in nombres])
    if id_col:
        r = esq.cur.fetchone()
        asignado = r[0] if r else nuevo_id
        if not asignado or asignado < 0:
            raise ErrorMicrosip(f"Tabla {tabla}", "Microsip no asignó un ID al registro nuevo")
        return asignado
    return None


def _actualizar(esq, tabla, id_col, id_valor, valores):
    cols = esq.columnas(tabla)
    valores = {k: v for k, v in valores.items() if k in cols and not cols[k]["calculada"]}
    if not valores:
        return
    for k, v in list(valores.items()):
        if isinstance(v, str) and cols[k]["largo"] and cols[k]["tipo"] in _TEXTO:
            valores[k] = v[: cols[k]["largo"]]
    esq.cur.execute(f"UPDATE {tabla} SET {', '.join(f'{k} = ?' for k in valores)} WHERE {id_col} = ?",
                    list(valores.values()) + [id_valor])


# ---------------------------------------------------------------- clientes

def _dir_principal(esq, cliente_id):
    orden = " ORDER BY ES_DIR_PPAL DESC" if "ES_DIR_PPAL" in esq.columnas("DIRS_CLIENTES") else ""
    return esq.fila(f"SELECT FIRST 1 * FROM DIRS_CLIENTES WHERE CLIENTE_ID = ?{orden}", (cliente_id,))


def _clave_cliente(esq, cliente_id):
    if not esq.existe("CLAVES_CLIENTES"):
        return None
    f = esq.fila("SELECT FIRST 1 CLAVE_CLIENTE FROM CLAVES_CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
    return (f["CLAVE_CLIENTE"] or "").strip() or None if f else None


def _resumen_cliente(esq, cliente_id):
    c = esq.fila("SELECT CLIENTE_ID, NOMBRE FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
    if not c:
        return None
    d = _dir_principal(esq, cliente_id) or {}
    partes = [" ".join(filter(None, [(d.get("NOMBRE_CALLE") or "").strip(), (d.get("NUM_EXTERIOR") or "").strip()])),
              (d.get("COLONIA") or "").strip(), (d.get("POBLACION") or "").strip()]
    return {
        "cliente_id": c["CLIENTE_ID"],
        "nombre": (c["NOMBRE"] or "").strip(),
        "clave": _clave_cliente(esq, cliente_id),
        "rfc": (d.get("RFC_CURP") or "").strip() or None,
        "telefono": (d.get("TELEFONO1") or "").strip() or None,
        "codigo_postal": (d.get("CODIGO_POSTAL") or "").strip() or None,
        "direccion": ", ".join(p for p in partes if p) or None,
    }


def _similares(esq, nombre, rfc=None, telefono=None, limite=8):
    encontrados = {}

    def agregar(cid, motivo, puntaje):
        e = encontrados.setdefault(cid, {"motivos": [], "puntaje": 0})
        if motivo not in e["motivos"]:
            e["motivos"].append(motivo)
        e["puntaje"] = max(e["puntaje"], puntaje)

    rfc = (rfc or "").upper().replace(" ", "").replace("-", "")
    if rfc and rfc not in RFC_GENERICOS and "RFC_CURP" in esq.columnas("DIRS_CLIENTES"):
        esq.cur.execute("SELECT DISTINCT CLIENTE_ID FROM DIRS_CLIENTES WHERE UPPER(TRIM(RFC_CURP)) = ?", (rfc,))
        for (cid,) in esq.cur.fetchall():
            agregar(cid, "Mismo RFC", 1.0)

    tel = _solo_digitos(telefono)[-10:]
    if len(tel) >= 8:
        cols_tel = [c for c in ("TELEFONO1", "TELEFONO2") if c in esq.columnas("DIRS_CLIENTES")]
        for col in cols_tel:
            esq.cur.execute(f"SELECT FIRST 400 CLIENTE_ID, {col} FROM DIRS_CLIENTES WHERE {col} CONTAINING ?", (tel[-4:],))
            for cid, valor in esq.cur.fetchall():
                if _solo_digitos(valor)[-8:] == tel[-8:]:
                    agregar(cid, "Mismo teléfono", 0.95)

    palabras = sorted({t for t in _norm_nombre(nombre) if len(t) >= 3}, key=len, reverse=True)[:3]
    vistos = set()
    for p in palabras:
        esq.cur.execute("SELECT FIRST 200 CLIENTE_ID, NOMBRE FROM CLIENTES WHERE NOMBRE CONTAINING ?", (p,))
        for cid, nom in esq.cur.fetchall():
            if cid in vistos:
                continue
            vistos.add(cid)
            puntos = parecido_nombres(nombre, nom)
            if puntos >= 0.6:
                agregar(cid, f"Nombre parecido ({round(puntos * 100)}%)", puntos * 0.9)

    resultado = []
    for cid, e in sorted(encontrados.items(), key=lambda kv: -kv[1]["puntaje"])[:limite]:
        r = _resumen_cliente(esq, cid)
        if r:
            r.update(motivos=e["motivos"], puntaje=round(e["puntaje"], 3))
            resultado.append(r)
    return resultado


def _ubicacion(esq, municipio, estado, plantilla_dir):
    """CIUDAD_ID / ESTADO_ID / PAIS_ID buscando el municipio en el catálogo de
    Microsip; si no aparece, los de la plantilla."""
    res = {k: plantilla_dir.get(k) for k in ("CIUDAD_ID", "ESTADO_ID", "PAIS_ID") if plantilla_dir.get(k) is not None}
    if not municipio or not esq.existe("CIUDADES"):
        return res, False
    objetivo = " ".join(_norm_nombre(municipio))
    est_obj = " ".join(_norm_nombre(estado)) if estado else None
    esq.cur.execute("SELECT CIUDAD_ID, NOMBRE, ESTADO_ID FROM CIUDADES WHERE NOMBRE CONTAINING ?", (_norm_nombre(municipio)[0] if _norm_nombre(municipio) else municipio,))
    candidatos = esq.cur.fetchall()
    nombres_estado = {}
    if est_obj and esq.existe("ESTADOS"):
        esq.cur.execute("SELECT ESTADO_ID, NOMBRE FROM ESTADOS")
        nombres_estado = {r[0]: " ".join(_norm_nombre(r[1])) for r in esq.cur.fetchall()}
    mejor = None
    for cid, nom, eid in candidatos:
        if " ".join(_norm_nombre(nom)) != objetivo:
            continue
        if est_obj and nombres_estado and nombres_estado.get(eid) and nombres_estado[eid] != est_obj:
            continue
        mejor = (cid, eid)
        break
    if not mejor:
        return res, False
    res["CIUDAD_ID"], res["ESTADO_ID"] = mejor
    if esq.existe("ESTADOS") and "PAIS_ID" in esq.columnas("ESTADOS"):
        f = esq.fila("SELECT PAIS_ID FROM ESTADOS WHERE ESTADO_ID = ?", (mejor[1],))
        if f and f.get("PAIS_ID") is not None:
            res["PAIS_ID"] = f["PAIS_ID"]
    return res, True


def _separar_domicilio(domicilio):
    """'AV VALLARTA #100 int. 3 col. AMERICANA' → calle, número, colonia."""
    d = domicilio or ""
    colonia = None
    m = re.search(r"\b(?:col\.?|colonia)\s+(.+)$", d, re.I)
    if m:
        colonia = m.group(1).strip()
        d = d[: m.start()].strip()
    num_ext = None
    m = re.search(r"#\s*([\w-]+)", d)
    if m:
        num_ext = m.group(1)
        d = (d[: m.start()] + d[m.end():]).strip()
    num_int = None
    m = re.search(r"\bint\.?\s*([\w-]+)", d, re.I)
    if m:
        num_int = m.group(1)
        d = (d[: m.start()] + d[m.end():]).strip()
    return _txt(d), _txt(num_ext), _txt(num_int), _txt(colonia)


def _siguiente_clave(esq, rol_id):
    if rol_id is not None and "ROL_CLAVE_CLI_ID" in esq.columnas("CLAVES_CLIENTES"):
        esq.cur.execute("SELECT CLAVE_CLIENTE FROM CLAVES_CLIENTES WHERE ROL_CLAVE_CLI_ID = ?", (rol_id,))
    else:
        esq.cur.execute("SELECT CLAVE_CLIENTE FROM CLAVES_CLIENTES")
    numericas = [c.strip() for (c,) in esq.cur.fetchall() if c and c.strip().isdigit()]
    if not numericas:
        return None
    mayor = max(numericas, key=int)
    siguiente = str(int(mayor) + 1).zfill(len(mayor))
    esq.cur.execute("SELECT 1 FROM CLAVES_CLIENTES WHERE CLAVE_CLIENTE = ?", (siguiente,))
    return None if esq.cur.fetchone() else siguiente


def _datos_dir(esq, datos):
    calle, num_ext, num_int, colonia = _separar_domicilio(datos.get("domicilio"))
    rfc = (datos.get("rfc") or "").upper() or None
    valores = {
        "NOMBRE_CALLE": calle, "NUM_EXTERIOR": num_ext, "NUM_INTERIOR": num_int,
        "COLONIA": colonia or _txt(datos.get("colonia")), "POBLACION": _txt(datos.get("municipio")),
        "CODIGO_POSTAL": _txt(datos.get("codigo_postal")), "TELEFONO1": _txt(datos.get("telefono")),
        "EMAIL": _txt(datos.get("email")), "RFC_CURP": rfc,
    }
    for col in esq.columnas_texto("DIRS_CLIENTES", "REGIMEN"):
        valores[col] = datos.get("regimen_fiscal")
    for col in esq.columnas_texto("DIRS_CLIENTES", "USO_CFDI"):
        valores[col] = datos.get("uso_cfdi")
    return valores


def _crear_cliente(esq, datos, avisos):
    plantilla = esq.fila("SELECT FIRST 1 * FROM CLIENTES ORDER BY CLIENTE_ID DESC")
    if not plantilla:
        raise ErrorMicrosip("Alta de cliente", "no hay ningún cliente en Microsip para tomar de modelo")
    nombre = _txt((datos.get("razon_social") or datos.get("nombre") or "").upper(), 100)
    if not nombre:
        raise ErrorMicrosip("Alta de cliente", "falta el nombre del cliente")
    esq.cur.execute("SELECT FIRST 1 CLIENTE_ID FROM CLIENTES WHERE UPPER(TRIM(NOMBRE)) = ?", (nombre.upper(),))
    if esq.cur.fetchone():
        raise ErrorMicrosip("Alta de cliente", f"ya existe un cliente llamado '{nombre}' en Microsip (Microsip no permite nombres repetidos). "
                            "Si es él, elígelo de la lista; si es otra persona, cambia el nombre en la cotización (ej. con su segundo apellido) y vuelve a enviar")
    ahora = _ahora()
    valores = {"NOMBRE": nombre, "ESTATUS": "A", "LIMITE_CREDITO": 0, "CONTACTO1": None,
               "USUARIO_CREADOR": USUARIO_APP, "FECHA_HORA_CREACION": ahora,
               "USUARIO_ULT_MODIF": USUARIO_APP, "FECHA_HORA_ULT_MODIF": ahora}
    for col in esq.columnas_texto("CLIENTES", "REGIMEN"):
        valores[col] = datos.get("regimen_fiscal")
    for col in esq.columnas_texto("CLIENTES", "USO_CFDI"):
        valores[col] = datos.get("uso_cfdi")
    copiar = ("MONEDA_ID", "COND_PAGO_ID", "TIPO_CLIENTE_ID", "ZONA_CLIENTE_ID", "CUENTA_*",
              "COBRAR_IMPUESTOS", "RETIENE_IMPUESTOS", "SUJETO_IEPS", "GENERAR_INTERESES", "EMITIR_EDOCTA")
    try:
        cliente_id = _insertar(esq, "CLIENTES", valores, plantilla, copiar, "CLIENTE_ID", "ID_CATALOGOS")
    except fdb.DatabaseError as e:
        raise ErrorMicrosip("Alta de cliente (CLIENTES)", _error_fb(e))

    clave = None
    if esq.existe("CLAVES_CLIENTES"):
        pl_clave = esq.fila("SELECT FIRST 1 * FROM CLAVES_CLIENTES ORDER BY CLAVE_CLIENTE_ID DESC")
        if pl_clave:
            clave = _siguiente_clave(esq, pl_clave.get("ROL_CLAVE_CLI_ID"))
            if clave:
                try:
                    _insertar(esq, "CLAVES_CLIENTES", {"CLAVE_CLIENTE": clave, "CLIENTE_ID": cliente_id},
                              pl_clave, ("ROL_CLAVE_CLI_ID",), "CLAVE_CLIENTE_ID", "ID_CATALOGOS")
                except fdb.DatabaseError as e:
                    raise ErrorMicrosip("Alta de cliente (clave)", _error_fb(e))
            else:
                avisos.append("No se pudo calcular la siguiente clave de cliente; quedó sin clave — ponla en Microsip si la usan.")

    pl_dir = esq.fila("SELECT FIRST 1 * FROM DIRS_CLIENTES ORDER BY DIR_CLI_ID DESC") or {}
    valores_dir = _datos_dir(esq, datos)
    if not valores_dir.get("RFC_CURP"):
        valores_dir["RFC_CURP"] = "XAXX010101000"
    ubic, encontrada = _ubicacion(esq, datos.get("municipio"), datos.get("estado"), pl_dir)
    if datos.get("municipio") and not encontrada:
        avisos.append(f"No encontré el municipio '{datos.get('municipio')}' en las ciudades de Microsip; quedó la ciudad del último cliente — corrígela en Microsip.")
    valores_dir.update(ubic)
    valores_dir.update({"CLIENTE_ID": cliente_id, "ES_DIR_PPAL": "S",
                        "NOMBRE_CONSIG": pl_dir.get("NOMBRE_CONSIG") if pl_dir.get("NOMBRE_CONSIG") else "Dirección principal"})
    try:
        dir_id = _insertar(esq, "DIRS_CLIENTES", valores_dir, pl_dir, ("CIUDAD_ID", "ESTADO_ID", "PAIS_ID"), "DIR_CLI_ID", "ID_CATALOGOS")
    except fdb.DatabaseError as e:
        raise ErrorMicrosip("Alta de cliente (dirección)", _error_fb(e))
    return cliente_id, dir_id, clave, nombre


def _completar_cliente(esq, cliente_id, datos, avisos):
    """Solo escribe lo que en Microsip está vacío. Nunca sobreescribe."""
    c = esq.fila("SELECT CLIENTE_ID, NOMBRE FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
    if not c:
        raise ErrorMicrosip("Cliente de Microsip", f"no existe el cliente #{cliente_id}")
    completados = []
    nuevos = _datos_dir(esq, datos)
    d = _dir_principal(esq, cliente_id)
    if not d:
        pl_dir = esq.fila("SELECT FIRST 1 * FROM DIRS_CLIENTES ORDER BY DIR_CLI_ID DESC") or {}
        ubic, _ = _ubicacion(esq, datos.get("municipio"), datos.get("estado"), pl_dir)
        nuevos.update(ubic)
        if not nuevos.get("RFC_CURP"):
            nuevos["RFC_CURP"] = "XAXX010101000"
        nuevos.update({"CLIENTE_ID": cliente_id, "ES_DIR_PPAL": "S", "NOMBRE_CONSIG": "Dirección principal"})
        dir_id = _insertar(esq, "DIRS_CLIENTES", nuevos, pl_dir, ("CIUDAD_ID", "ESTADO_ID", "PAIS_ID"), "DIR_CLI_ID", "ID_CATALOGOS")
        completados.append("dirección")
    else:
        dir_id = d["DIR_CLI_ID"]
        cambios = {}
        etiquetas = {"RFC_CURP": "RFC", "TELEFONO1": "teléfono", "EMAIL": "correo", "CODIGO_POSTAL": "código postal",
                     "NOMBRE_CALLE": "calle", "NUM_EXTERIOR": "número", "COLONIA": "colonia", "POBLACION": "población"}
        for col, v in nuevos.items():
            if not v or col not in d:
                continue
            actual = (str(d.get(col) or "")).strip()
            if col == "RFC_CURP" and actual.upper() in RFC_GENERICOS:
                actual = ""
            if not actual:
                cambios[col] = v
                completados.append(etiquetas.get(col, col.lower()))
        if cambios:
            _actualizar(esq, "DIRS_CLIENTES", "DIR_CLI_ID", dir_id, cambios)
    reg_cols = esq.columnas_texto("CLIENTES", "REGIMEN") + esq.columnas_texto("CLIENTES", "USO_CFDI")
    if reg_cols:
        actual = esq.fila(f"SELECT {', '.join(reg_cols)} FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
        cambios = {}
        for col in reg_cols:
            v = datos.get("regimen_fiscal") if "REGIMEN" in col else datos.get("uso_cfdi")
            if v and not (str(actual.get(col) or "")).strip():
                cambios[col] = v
                completados.append("régimen fiscal" if "REGIMEN" in col else "uso de CFDI")
        _actualizar(esq, "CLIENTES", "CLIENTE_ID", cliente_id, cambios)
    return dir_id, _clave_cliente(esq, cliente_id), (c["NOMBRE"] or "").strip(), completados


# ------------------------------------------------------------- cotización

def _precios(esq, articulo_ids):
    info = {}
    for aid in articulo_ids:
        a = esq.fila("SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID = ?", (aid,))
        if not a:
            info[aid] = None
            continue
        p = esq.fila("SELECT FIRST 1 PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID = ?", (aid,))
        cl = esq.fila("SELECT FIRST 1 CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID = ? ORDER BY CLAVE_ARTICULO_ID", (aid,))
        info[aid] = {"nombre": (a["NOMBRE"] or "").strip(),
                     "precio": float(p["PRECIO"]) if p and p.get("PRECIO") is not None else None,
                     "clave": (cl["CLAVE_ARTICULO"] or "").strip() if cl else None}
    return info


def _plantilla_cotizacion(esq):
    pl = esq.fila("SELECT FIRST 1 * FROM DOCTOS_VE WHERE TIPO_DOCTO = 'C' ORDER BY DOCTO_VE_ID DESC")
    if not pl:
        pl = esq.fila("SELECT FIRST 1 * FROM DOCTOS_VE WHERE TIPO_DOCTO IN ('P', 'R', 'F') ORDER BY DOCTO_VE_ID DESC")
    return pl


def _folio(esq, tipo, plantilla, reservar=True):
    """Siguiente folio libre. FOLIOS_VENTAS manda (serie + consecutivo); si no
    existe, se sigue el último folio del mismo tipo."""
    largo = len((plantilla or {}).get("FOLIO") or "") or 9
    if largo < 4:
        largo = 9
    fila_folios = None
    cols = esq.columnas("FOLIOS_VENTAS")
    if cols and "TIPO_DOCTO" in cols and "CONSECUTIVO" in cols:
        id_col = next(iter(cols))
        filas = []
        esq.cur.execute(f"SELECT * FROM FOLIOS_VENTAS WHERE TIPO_DOCTO = ?", (tipo,))
        nombres = [d[0] for d in esq.cur.description]
        filas = [dict(zip(nombres, r)) for r in esq.cur.fetchall()]
        suc = (plantilla or {}).get("SUCURSAL_ID")
        if "SUCURSAL_ID" in cols and filas:
            fila_folios = next((f for f in filas if f.get("SUCURSAL_ID") == suc), None) or \
                          next((f for f in filas if f.get("SUCURSAL_ID") is None), None)
        if not fila_folios and filas:
            serie_pl = re.match(r"^([A-Za-z]*)", (plantilla or {}).get("FOLIO") or "").group(1)
            fila_folios = next((f for f in filas if (f.get("SERIE") or "").strip() == serie_pl), filas[0])
    if fila_folios:
        serie = (fila_folios.get("SERIE") or "").strip()
        if serie == "@":
            serie = ""
        consecutivo = int(fila_folios.get("CONSECUTIVO") or 1)
    else:
        m = re.match(r"^([A-Za-z]*)(\d+)$", ((plantilla or {}).get("FOLIO") or "").strip())
        serie, consecutivo = (m.group(1), int(m.group(2)) + 1) if m else ("", 1)
    for _ in range(500):
        folio = serie + str(consecutivo).zfill(max(1, largo - len(serie)))
        esq.cur.execute("SELECT 1 FROM DOCTOS_VE WHERE TIPO_DOCTO = ? AND FOLIO = ?", (tipo, folio))
        if not esq.cur.fetchone():
            break
        consecutivo += 1
    else:
        raise ErrorMicrosip("Folio", "no encontré un folio libre para la cotización")
    if fila_folios and reservar:
        _actualizar(esq, "FOLIOS_VENTAS", id_col, fila_folios[id_col], {"CONSECUTIVO": consecutivo + 1})
    return folio


def _crear_cotizacion(esq, cliente_id, dir_id, clave_cliente, partidas, descripcion, datos, avisos):
    pl = _plantilla_cotizacion(esq)
    if not pl:
        raise ErrorMicrosip("Cotización", "no hay ninguna cotización, pedido o factura en Microsip para tomar de modelo")
    folio = _folio(esq, "C", pl)
    ahora = _ahora()
    valores = {
        "TIPO_DOCTO": "C", "FOLIO": folio, "FECHA": ahora.date(), "HORA": ahora.time(),
        "CLAVE_CLIENTE": clave_cliente, "CLIENTE_ID": cliente_id, "DIR_CLI_ID": dir_id, "DIR_CONSIG_ID": dir_id,
        "ESTATUS": "P", "APLICADO": "N", "DESCRIPCION": _txt(descripcion, 200),
        "DSCTO_PCTJE": 0, "DSCTO_IMPORTE": 0, "IMPORTE_NETO": 0, "TOTAL_IMPUESTOS": 0, "FLETES": 0, "OTROS_CARGOS": 0,
        "FORMA_EMITIDA": "N", "CONTABILIZADO": "N", "CANCELADO": "N", "SISTEMA_ORIGEN": "VE",
        "USUARIO_CREADOR": USUARIO_APP, "FECHA_HORA_CREACION": ahora,
        "USUARIO_ULT_MODIF": USUARIO_APP, "FECHA_HORA_ULT_MODIF": ahora,
    }
    for col in esq.columnas_texto("DOCTOS_VE", "USO_CFDI"):
        if datos.get("uso_cfdi"):
            valores[col] = datos["uso_cfdi"]
    copiar = ("SUBTIPO_DOCTO", "SUCURSAL_ID", "ALMACEN_ID", "LUGAR_EXPEDICION_ID", "MONEDA_ID", "TIPO_CAMBIO",
              "COND_PAGO_ID", "TIPO_DSCTO")
    try:
        docto_id = _insertar(esq, "DOCTOS_VE", valores, pl, copiar, "DOCTO_VE_ID", "ID_DOCTOS")
    except fdb.DatabaseError as e:
        raise ErrorMicrosip("Cotización (encabezado)", _error_fb(e))

    pl_det = esq.fila("SELECT FIRST 1 * FROM DOCTOS_VE_DET WHERE DOCTO_VE_ID = ?", (pl["DOCTO_VE_ID"],)) or {}
    importe = 0.0
    for i, p in enumerate(partidas, start=1):
        neto = round(p["cantidad"] * p["precio"], 2)
        importe += neto
        det = {"DOCTO_VE_ID": docto_id, "CLAVE_ARTICULO": p.get("clave"), "ARTICULO_ID": p["articulo_id"],
               "UNIDADES": p["cantidad"], "UNIDADES_COMPROM": 0, "UNIDADES_SURT_DEV": 0, "UNIDADES_A_SURTIR": 0,
               "PRECIO_UNITARIO": p["precio"], "PCTJE_DSCTO": 0, "DSCTO_ART": 0, "DSCTO_EXTRA": 0,
               "PRECIO_TOTAL_NETO": neto, "POSICION": i, "NOTAS": _txt(p.get("nota"))}
        try:
            _insertar(esq, "DOCTOS_VE_DET", det, pl_det, ("ROL",), "DOCTO_VE_DET_ID", "ID_DOCTOS")
        except fdb.DatabaseError as e:
            raise ErrorMicrosip(f"Cotización (partida {i}: {p.get('nombre')})", _error_fb(e))

    totales = _calcular_totales(esq, docto_id, partidas, importe, avisos)
    if (pl.get("APLICADO") or "S").strip() == "S":
        try:
            _actualizar(esq, "DOCTOS_VE", "DOCTO_VE_ID", docto_id, {"APLICADO": "S"})
        except fdb.DatabaseError as e:
            raise ErrorMicrosip("Cotización (aplicar)", _error_fb(e))
    return docto_id, folio, totales


def _calcular_totales(esq, docto_id, partidas, importe, avisos):
    cols = esq.columnas("DOCTOS_VE")
    proc = esq.procedimiento("CALC_TOTALES_DOCTO_VE")
    if proc and len(proc["entradas"]) in (1, 2) and proc["salidas"]:
        args = (docto_id, "S")[: len(proc["entradas"])]
        try:
            esq.cur.execute(f"SELECT * FROM CALC_TOTALES_DOCTO_VE({', '.join('?' for _ in args)})", args)
            r = esq.cur.fetchonemap()
            if r:
                r = {k: r[k] for k in r.keys()}
                cambios = {k: v for k, v in r.items() if k in cols and v is not None and k in ("IMPORTE_NETO", "TOTAL_IMPUESTOS", "TOTAL_RETENCIONES", "DSCTO_IMPORTE")}
                if cambios:
                    _actualizar(esq, "DOCTOS_VE", "DOCTO_VE_ID", docto_id, cambios)
                    return {"importe_neto": float(cambios.get("IMPORTE_NETO", importe)),
                            "total_impuestos": float(cambios.get("TOTAL_IMPUESTOS") or 0)}
        except fdb.DatabaseError as e:
            avisos.append(f"El cálculo de totales de Microsip falló ({_error_fb(e)}); se calcularon aquí.")
    impuestos = 0.0
    if esq.existe("IMPUESTOS_ARTICULOS") and esq.existe("IMPUESTOS"):
        for p in partidas:
            f = esq.fila("""SELECT MAX(I.PCTJE_IMPUESTO) AS PCT FROM IMPUESTOS_ARTICULOS IA
                            JOIN IMPUESTOS I ON I.IMPUESTO_ID = IA.IMPUESTO_ID WHERE IA.ARTICULO_ID = ?""", (p["articulo_id"],))
            pct = float(f["PCT"]) if f and f.get("PCT") is not None else 16.0
            impuestos += round(p["cantidad"] * p["precio"] * pct / 100, 2)
    else:
        impuestos = round(importe * 0.16, 2)
    _actualizar(esq, "DOCTOS_VE", "DOCTO_VE_ID", docto_id, {"IMPORTE_NETO": round(importe, 2), "TOTAL_IMPUESTOS": round(impuestos, 2)})
    return {"importe_neto": round(importe, 2), "total_impuestos": round(impuestos, 2)}


def _error_fb(e):
    texto = e.args[0] if getattr(e, "args", None) and isinstance(e.args[0], str) else str(e)
    partes = [l.strip(" -") for l in texto.splitlines() if l.strip(" -") and "SQLCODE" not in l and "Error while" not in l]
    detalle = "; ".join(partes[:4]) or texto
    if "no permission" in texto.lower() or "permission" in texto.lower():
        detalle += (" — ese usuario de Firebird no tiene permisos sobre las tablas de Microsip. Lo más sencillo: usa el mismo "
                    "usuario con el que entra Microsip (normalmente SYSDBA) en 'Usuario de Firebird con escritura'.")
    if "violation of PRIMARY or UNIQUE" in texto or "unique" in texto.lower():
        detalle += " — ya existe un registro igual en Microsip."
    return detalle


# ------------------------------------------------------------- públicos

def buscar_similares(config, nombre, rfc=None, telefono=None):
    con = _conectar(config)
    try:
        return _similares(_Esquema(con.cursor()), nombre, rfc, telefono)
    finally:
        con.close()


def leer_cliente(config, cliente_id):
    con = _conectar(config)
    try:
        return _resumen_cliente(_Esquema(con.cursor()), cliente_id)
    finally:
        con.close()


def enviar_cotizacion(config, *, datos_cliente, partidas, descripcion, cliente_id=None, probar=False):
    """datos_cliente: nombre, razon_social, rfc, telefono, email, domicilio,
    municipio, estado, codigo_postal, regimen_fiscal, uso_cfdi.
    partidas: [{articulo_id, cantidad, nombre, nota}] — precio de lista de Microsip.
    cliente_id: el de Microsip si ya se eligió/ligó; None = dar de alta."""
    avisos = []
    con = _conectar(config)
    try:
        esq = _Esquema(con.cursor())
        info = _precios(esq, sorted({p["articulo_id"] for p in partidas}))
        sin = [p["nombre"] for p in partidas if not info.get(p["articulo_id"])]
        if sin:
            raise ErrorMicrosip("Artículos", "no existen en Microsip: " + ", ".join(sin))
        sin_precio = [info[p["articulo_id"]]["nombre"] for p in partidas if not info[p["articulo_id"]]["precio"]]
        if sin_precio:
            raise ErrorMicrosip("Artículos", "no tienen precio de lista en Microsip: " + ", ".join(sin_precio))
        partidas_ms = [{**p, "precio": round(info[p["articulo_id"]]["precio"], 6), "clave": info[p["articulo_id"]]["clave"],
                        "nombre_microsip": info[p["articulo_id"]]["nombre"]} for p in partidas]

        creado = False
        completados = []
        if cliente_id:
            dir_id, clave, nombre_ms, completados = _completar_cliente(esq, cliente_id, datos_cliente, avisos)
        else:
            cliente_id, dir_id, clave, nombre_ms = _crear_cliente(esq, datos_cliente, avisos)
            creado = True
        docto_id, folio, totales = _crear_cotizacion(esq, cliente_id, dir_id, clave, partidas_ms, descripcion, datos_cliente, avisos)
        if probar:
            con.rollback()
        else:
            con.commit()
    except fdb.DatabaseError as e:
        con.rollback()
        raise ErrorMicrosip("Microsip", _error_fb(e))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {
        "probado": probar, "folio": folio, "docto_ve_id": None if probar else docto_id,
        "cliente_id": None if (probar and creado) else cliente_id, "cliente_nombre": nombre_ms, "cliente_clave": clave,
        "cliente_creado": creado, "campos_completados": completados,
        "importe_neto": totales["importe_neto"], "total_impuestos": totales["total_impuestos"],
        "total": round(totales["importe_neto"] + totales["total_impuestos"], 2),
        "partidas": [{"clave": p["clave"], "nombre": p["nombre_microsip"], "cantidad": p["cantidad"], "precio": p["precio"]} for p in partidas_ms],
        "avisos": avisos,
    }


def alta_cliente(config, *, datos_cliente, cliente_id=None):
    """Solo el cliente (sin cotización): da de alta en Microsip o, si ya se
    eligió uno, le llena los datos que tenga vacíos. Se usa, por ejemplo,
    para dar de alta a los estudiantes del laboratorio."""
    avisos = []
    con = _conectar(config)
    try:
        esq = _Esquema(con.cursor())
        if cliente_id:
            _, clave, nombre, completados = _completar_cliente(esq, cliente_id, datos_cliente, avisos)
            creado = False
        else:
            cliente_id, _, clave, nombre = _crear_cliente(esq, datos_cliente, avisos)
            completados, creado = [], True
        con.commit()
    except fdb.DatabaseError as e:
        con.rollback()
        raise ErrorMicrosip("Microsip", _error_fb(e))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"cliente_id": cliente_id, "cliente_nombre": nombre, "cliente_clave": clave, "cliente_creado": creado,
            "campos_completados": completados, "avisos": avisos}


def diagnostico(config, articulo_prueba_id=None):
    """Revisa lo que hace falta para escribir y hace una prueba completa que
    se deshace al final (cliente + cotización de prueba)."""
    r = {"pasos": [], "ok": False}

    def paso(nombre, ok, detalle=""):
        r["pasos"].append({"paso": nombre, "ok": ok, "detalle": detalle})
        return ok

    try:
        con = _conectar(config)
    except Exception as e:
        paso("Conectar con el usuario de escritura", False, _error_fb(e) if isinstance(e, fdb.DatabaseError) else str(e))
        return r
    usuario = config.get("microsip_escritura_usuario") or config.get("microsip_usuario")
    paso("Conectar con el usuario de escritura", True, usuario)
    try:
        esq = _Esquema(con.cursor())
        faltan = [t for t in ("CLIENTES", "DIRS_CLIENTES", "DOCTOS_VE", "DOCTOS_VE_DET", "ARTICULOS", "PRECIOS_ARTICULOS") if not esq.existe(t)]
        paso("Tablas de Microsip", not faltan, "Faltan: " + ", ".join(faltan) if faltan else "Completas")
        gens = [g for g in ("ID_DOCTOS", "ID_CATALOGOS") if esq.generador(g)]
        paso("Generadores de IDs", True, ", ".join(gens) if gens else "No hay; se usará el trigger (-1)")
        proc = esq.procedimiento("CALC_TOTALES_DOCTO_VE")
        paso("Cálculo de totales de Microsip", True, f"CALC_TOTALES_DOCTO_VE ({', '.join(proc['salidas'])})" if proc else "No existe; se calcularán aquí")
        pl = _plantilla_cotizacion(esq)
        if not paso("Cotización de modelo", bool(pl), f"{pl['FOLIO'].strip()} del {pl['FECHA']}" if pl else "No hay cotizaciones/pedidos en Microsip"):
            return r
        paso("Siguiente folio de cotización", True, _folio(esq, "C", pl, reservar=False))
        if faltan:
            return r
        aid = articulo_prueba_id
        if not aid:
            f = esq.fila("SELECT FIRST 1 A.ARTICULO_ID FROM ARTICULOS A WHERE A.ESTATUS = 'A' AND EXISTS (SELECT 1 FROM PRECIOS_ARTICULOS P WHERE P.ARTICULO_ID = A.ARTICULO_ID AND P.PRECIO > 0)")
            aid = f["ARTICULO_ID"] if f else None
        if not paso("Artículo para la prueba", bool(aid), str(aid or "No hay artículos con precio")):
            return r
    except fdb.DatabaseError as e:
        paso("Leer Microsip con ese usuario", False, _error_fb(e))
        return r
    except Exception as e:
        paso("Leer Microsip con ese usuario", False, str(e))
        return r
    finally:
        con.close()
    try:
        prueba = enviar_cotizacion(config, probar=True, descripcion="PRUEBA TICKETS-TI (se deshace)",
                                   partidas=[{"articulo_id": aid, "cantidad": 1, "nombre": "prueba", "nota": None}],
                                   datos_cliente={"nombre": f"PRUEBA TICKETS-TI {_ahora():%Y%m%d%H%M%S}", "telefono": "0000000000",
                                                  "municipio": None})
        paso("Prueba completa (alta de cliente + cotización, deshecha al final)", True,
             f"Microsip aceptó la cotización {prueba['folio']} por ${prueba['total']:,.2f}; no se guardó nada."
             + (" Avisos: " + " ".join(prueba["avisos"]) if prueba["avisos"] else ""))
        r["ok"] = True
    except ErrorMicrosip as e:
        paso("Prueba completa (alta de cliente + cotización, deshecha al final)", False, str(e))
    except Exception as e:
        paso("Prueba completa (alta de cliente + cotización, deshecha al final)", False, str(e))
    return r
