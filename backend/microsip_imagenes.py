"""Productos con imagen (solo lectura).

Junta dos fuentes:
- Microsip: IMAGENES_ARTICULOS (IMAGEN es un BLOB; ROLES_IMAGENES_ARTICULOS dice cuál es la "Imagen principal").
- La app: la foto que se toma en Inventarios si el producto no tenía (tabla articulos_imagenes de tickets-ti).
Las imágenes se mandan como miniaturas (JPEG chico) en lotes, para que la pantalla cargue rápido y no se gaste memoria.
"""
import base64
from collections import OrderedDict

import microsip_surtido as ms

_CACHE_MINI = OrderedDict()   # (fuente, id, ancho) -> data URI
_MAX_CACHE = 600


def _mime(b):
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:2] == b"BM":
        return "image/bmp"
    if b[:4] in (b"GIF8",):
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def miniatura(datos, ancho=260):
    """bytes de imagen -> data URI JPEG de `ancho` px (o la original si no se puede reducir). ancho=0 -> original."""
    if not datos:
        return None
    if ancho:
        try:
            import cv2
            import numpy as np
            img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                if w > ancho:
                    img = cv2.resize(img, (ancho, max(1, int(h * ancho / w))), interpolation=cv2.INTER_AREA)
                ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    return "data:image/jpeg;base64," + base64.b64encode(enc.tobytes()).decode()
        except Exception:
            pass
    return f"data:{_mime(datos)};base64," + base64.b64encode(datos).decode()


def _guardar(clave, valor):
    _CACHE_MINI[clave] = valor
    _CACHE_MINI.move_to_end(clave)
    while len(_CACHE_MINI) > _MAX_CACHE:
        _CACHE_MINI.popitem(last=False)


def listar(config):
    """Artículos que tienen al menos una imagen en Microsip, sin las imágenes (solo ids y tamaños)."""
    con = ms._conectar(config)
    try:
        cur = con.cursor()
        principales = set()
        try:
            cur.execute("SELECT ROL_IMAGEN_ART_ID, NOMBRE, ES_PPAL FROM ROLES_IMAGENES_ARTICULOS")
            roles = {}
            for rid, nom, ppal in cur.fetchall():
                roles[rid] = ms._t(nom) or ""
                if ms._t(ppal) == "S":
                    principales.add(rid)
        except Exception:
            roles = {}
        # Sin OCTET_LENGTH(IMAGEN): medir cada BLOB obliga a Firebird a leer todas las imágenes.
        cur.execute("""SELECT IMAGEN_ARTICULO_ID, ARTICULO_ID, ROL_IMAGEN_ART_ID
                       FROM IMAGENES_ARTICULOS WHERE IMAGEN IS NOT NULL""")
        fotos = {}
        for iid, art, rol in cur.fetchall():
            fotos.setdefault(art, []).append({"id": iid, "rol": roles.get(rol, ""), "principal": rol in principales})
        for lst in fotos.values():
            lst.sort(key=lambda x: (not x["principal"], x["id"]))
        _fechas_estimadas(cur, fotos)
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN COALESCE(ESTATUS, 'A') = 'A' THEN 1 ELSE 0 END) FROM ARTICULOS")
        total, activos = cur.fetchone()
        return {"fotos": fotos, "total_articulos": int(total or 0), "activos": int(activos or 0)}
    finally:
        con.close()


def _fechas_estimadas(cur, fotos):
    """Microsip no guarda la fecha de cada imagen. Dos datos ayudan a saberla:
    - al subir la imagen se modifica el artículo (FECHA_HORA_ULT_MODIF / USUARIO_ULT_MODIF), pero si después se vuelve
      a modificar, esa fecha se recorre;
    - IMAGEN_ARTICULO_ID es consecutivo: una imagen con id más alto se subió después.
    Fecha estimada = la menor FECHA_HORA_ULT_MODIF entre los artículos de esa imagen y de todas las que se subieron
    después (nunca puede ser posterior a esa). Con eso cada imagen queda en el día de la sesión en que se subió.
    tickets-ti guarda la fecha la primera vez que ve cada imagen (ver api), así que después ya no cambia."""
    arts = set(fotos)
    mod = {}
    try:
        for lote in ms._lotes(arts):
            cur.execute(f"SELECT ARTICULO_ID, FECHA_HORA_ULT_MODIF, USUARIO_ULT_MODIF FROM ARTICULOS WHERE ARTICULO_ID IN ({','.join('?' * len(lote))})",
                        tuple(lote))
            for a, f, u in cur.fetchall():
                mod[a] = (f, ms._t(u) or "")
    except Exception:
        return
    todas = sorted(((x["id"], a, x) for a, lst in fotos.items() for x in lst), key=lambda t: -t[0])
    minimo = None
    for _, a, x in todas:
        f, u = mod.get(a, (None, ""))
        if f is not None and (minimo is None or f <= minimo[0]):
            minimo = (f, u)
        if minimo:
            x["fecha"] = minimo[0].isoformat(timespec="minutes") if hasattr(minimo[0], "isoformat") else str(minimo[0])[:16]
            x["usuario"] = minimo[1]


def datos_articulos(config, ids):
    """Nombre, clave, estatus, línea y marca de esos artículos."""
    ids = set(ids)
    if not ids:
        return {}
    con = ms._conectar(config)
    try:
        cur = con.cursor()
        info = ms._articulos(cur, ids)
        lineas = {}
        try:
            cur.execute("SELECT LINEA_ARTICULO_ID, NOMBRE FROM LINEAS_ARTICULOS")
            lineas = {i: ms._t(n) for i, n in cur.fetchall()}
        except Exception:
            pass
        marca = {}
        try:
            cur.execute("SELECT CLASIFICADOR_ID, NOMBRE FROM CLASIFICADORES_CAT WHERE TIPO_OBJETO = 'A'")
            cid = next((c for c, n in cur.fetchall() if (ms._t(n) or "").upper() == "MARCA"), None)
            if cid:
                cur.execute("""SELECT e.ELEMENTO_ID, v.VALOR FROM ELEMENTOS_CAT_CLASIF e
                               JOIN CLASIFICADORES_CAT_VALORES v ON v.VALOR_CLASIF_ID = e.VALOR_CLASIF_ID WHERE v.CLASIFICADOR_ID = ?""", (cid,))
                marca = {a: ms._t(v) for a, v in cur.fetchall() if a in ids}
        except Exception:
            pass
        for a, i in info.items():
            i["linea"] = lineas.get(i.get("linea_id")) or ""
            i["marca"] = marca.get(a) or ""
        return info
    finally:
        con.close()


def miniaturas(config, ids, ancho=260):
    """{IMAGEN_ARTICULO_ID: data URI} de Microsip, de un lote de ids (una sola conexión)."""
    ids = [int(i) for i in ids][:60]
    ancho = max(0, min(int(ancho or 0), 1600))
    out, faltan = {}, []
    for i in ids:
        v = _CACHE_MINI.get(("ms", i, ancho))
        if v:
            out[i] = v
        else:
            faltan.append(i)
    if faltan:
        con = ms._conectar(config)
        try:
            cur = con.cursor()
            cur.execute(f"SELECT IMAGEN_ARTICULO_ID, IMAGEN FROM IMAGENES_ARTICULOS WHERE IMAGEN_ARTICULO_ID IN ({','.join('?' * len(faltan))})",
                        tuple(faltan))
            for iid, blob in cur.fetchall():
                if hasattr(blob, "read"):          # las imágenes grandes llegan como BlobReader
                    try:
                        datos = blob.read()
                    finally:
                        try:
                            blob.close()
                        except Exception:
                            pass
                else:
                    datos = blob
                if isinstance(datos, str):
                    datos = datos.encode("latin-1")
                uri = miniatura(datos, ancho)
                if uri:
                    out[iid] = uri
                    if ancho and ancho <= 400:
                        _guardar(("ms", iid, ancho), uri)
        finally:
            con.close()
    return out


def miniatura_app(articulo_id, data_uri, ancho=260):
    """La foto de la app viene como data URI; se reduce igual que las de Microsip."""
    if not data_uri:
        return None
    clave = ("app", int(articulo_id), int(ancho or 0), len(data_uri))
    v = _CACHE_MINI.get(clave)
    if v:
        return v
    try:
        datos = base64.b64decode(data_uri.split(",", 1)[1])
    except Exception:
        return data_uri
    v = miniatura(datos, ancho)
    if ancho and ancho <= 400:
        _guardar(clave, v)
    return v
