"""Minuta de reunión con IA (Proyectos → 🎙️ Proyecto desde una reunión).

Se graba (o se sube) el audio de la reunión y Gemini lo escucha y regresa:
título y descripción del proyecto, resumen, puntos clave, acuerdos,
conclusión y tareas con su responsable. Con eso se arma un PDF de minuta y
el proyecto con sus tareas. El audio NO se guarda: se procesa en memoria,
se sube temporalmente a Gemini y se borra de allá al terminar.

Usa la misma GEMINI_API_KEY que las imágenes de promociones.
"""
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import date

import requests

API = "https://generativelanguage.googleapis.com"
# Google va retirando modelos ("no longer available to new users"). Se prueba en orden:
# el de la variable GEMINI_MODELO_MINUTA (si existe), luego estos; si Gemini responde 404
# y sugiere otro modelo en el mensaje, se usa ese. El que funcione se recuerda.
MODELOS = [m for m in [os.getenv("GEMINI_MODELO_MINUTA", "").strip(),
                       "gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash"] if m]
_modelo_bueno = None


class ErrorMinuta(Exception):
    pass


def _api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ErrorMinuta("Falta la variable GEMINI_API_KEY en Render (la misma de las imágenes de promociones).")
    return key


def a_mp3(audio: bytes, nombre: str = "") -> tuple[bytes, str]:
    """Convierte cualquier audio (webm del navegador, m4a del iPhone, wav…) a mp3
    mono 16 kHz 32 kbps: 1 hora ≈ 14 MB. Si no hay ffmpeg, se manda tal cual."""
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return audio, _mime_por_nombre(nombre)
    sufijo = os.path.splitext(nombre or "")[1] or ".bin"
    with tempfile.TemporaryDirectory() as tmp:
        entrada = os.path.join(tmp, "entrada" + sufijo)
        salida = os.path.join(tmp, "salida.mp3")
        with open(entrada, "wb") as f:
            f.write(audio)
        r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", entrada, "-vn", "-ac", "1",
                            "-ar", "16000", "-b:a", "32k", "-f", "mp3", salida], capture_output=True, timeout=600)
        if r.returncode != 0 or not os.path.exists(salida) or os.path.getsize(salida) < 1000:
            raise ErrorMinuta("No se pudo leer el audio (¿el archivo está completo?). "
                              + (r.stderr.decode(errors="ignore")[:200] if r.stderr else ""))
        with open(salida, "rb") as f:
            return f.read(), "audio/mp3"


def _mime_por_nombre(nombre):
    ext = os.path.splitext(nombre or "")[1].lower()
    return {".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg", ".flac": "audio/flac",
            ".aac": "audio/aac", ".m4a": "audio/aac"}.get(ext, "audio/mp3")


def _subir(audio: bytes, mime: str, key: str) -> dict:
    """Files API de Gemini (subida resumible). El archivo se borra al terminar."""
    ini = requests.post(f"{API}/upload/v1beta/files", headers={
        "x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(audio)), "X-Goog-Upload-Header-Content-Type": mime,
        "Content-Type": "application/json"}, json={"file": {"display_name": "reunion"}}, timeout=60)
    _revisar(ini)
    url = ini.headers.get("x-goog-upload-url") or ini.headers.get("X-Goog-Upload-URL")
    if not url:
        raise ErrorMinuta("Gemini no dio dónde subir el audio.")
    r = requests.post(url, headers={"Content-Length": str(len(audio)), "X-Goog-Upload-Offset": "0",
                                    "X-Goog-Upload-Command": "upload, finalize"}, data=audio, timeout=600)
    _revisar(r)
    archivo = r.json().get("file") or {}
    # Esperar a que Gemini termine de procesarlo
    for _ in range(90):
        if archivo.get("state") in (None, "ACTIVE"):
            break
        if archivo.get("state") == "FAILED":
            raise ErrorMinuta("Gemini no pudo procesar el audio.")
        time.sleep(2)
        g = requests.get(f"{API}/v1beta/{archivo['name']}", headers={"x-goog-api-key": key}, timeout=30)
        _revisar(g)
        archivo = g.json()
    return archivo


def _borrar(archivo: dict, key: str):
    try:
        if archivo.get("name"):
            requests.delete(f"{API}/v1beta/{archivo['name']}", headers={"x-goog-api-key": key}, timeout=30)
    except Exception:
        pass


def _revisar(r):
    if r.status_code in (401, 403):
        raise ErrorMinuta("La API key de Gemini no es válida (revisa GEMINI_API_KEY en Render).")
    if r.status_code == 429:
        raise ErrorMinuta("Se alcanzó el límite de uso de Gemini. Espera un minuto e intenta de nuevo "
                          "(o activa facturación en aistudio.google.com para subir el límite).")
    if r.status_code == 413:
        raise ErrorMinuta("El audio es demasiado grande para Gemini.")
    if not r.ok:
        raise ErrorMinuta(f"Gemini respondió con error ({r.status_code}): {r.text[:300]}")


def _generar(cuerpo, key):
    """generateContent probando modelos hasta dar con uno vigente."""
    global _modelo_bueno
    pendientes = ([_modelo_bueno] if _modelo_bueno else []) + [m for m in MODELOS if m != _modelo_bueno]
    probados = []
    r = None
    while pendientes:
        modelo = pendientes.pop(0)
        if modelo in probados:
            continue
        probados.append(modelo)
        r = requests.post(f"{API}/v1beta/models/{modelo}:generateContent",
                          headers={"x-goog-api-key": key, "content-type": "application/json"},
                          json=cuerpo, timeout=900)
        if r.status_code == 404 or (r.status_code == 400 and "model" in r.text.lower() and "not" in r.text.lower()):
            # "This model ... is no longer available ... use models/gemini-X-flash"
            sugerido = re.findall(r"models/([A-Za-z0-9.\-]+)", r.text)
            for m in reversed([x for x in sugerido if x != modelo]):
                if m not in probados:
                    pendientes.insert(0, m)
            print(f"[minuta] modelo {modelo} no disponible ({r.status_code}); probando otro")
            continue
        _revisar(r)
        _modelo_bueno = modelo
        return r
    raise ErrorMinuta("Ningún modelo de Gemini respondió (" + ", ".join(probados) + "). "
                      "Pon el nombre de un modelo vigente en la variable GEMINI_MODELO_MINUTA de Render. "
                      + (r.text[:200] if r is not None else ""))


def _prompt(participantes, contexto, hoy):
    lista = "\n".join(f"- {p['nombre']}" + (f" ({p['puesto']})" if p.get("puesto") else "") for p in participantes) or "- (no se indicaron)"
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    return f"""Eres el secretario que levanta la MINUTA OFICIAL de una reunión de trabajo de una empresa mexicana
(Productos Dentales Mark Inc). Es un documento de la empresa: debe ser específico, con NOMBRES de las personas,
FECHAS exactas, cantidades, lugares y compromisos tal como se dijeron. Escucha TODO el audio y regresa SOLO un JSON
(sin texto antes ni después) así:

{{
  "titulo_proyecto": "nombre corto y claro del proyecto que salió de la reunión (máx. 80 caracteres)",
  "descripcion_proyecto": "objetivo del proyecto: qué se va a hacer, dónde, para qué y con qué alcance, en 2 a 4 oraciones",
  "resumen": "resumen ejecutivo de la reunión en 5 a 10 oraciones, mencionando quién propuso o decidió cada cosa",
  "temas": [
    {{"tema": "título corto del tema tratado", "detalle": "qué se dijo, quién lo dijo, cifras, fechas y lo que se decidió sobre ese tema (2 a 5 oraciones)"}}
  ],
  "puntos_clave": ["datos más importantes (montos, fechas, cantidades, proveedores, lugares), máximo 10"],
  "acuerdos": ["cada acuerdo como oración completa: QUIÉN se compromete a QUÉ y para CUÁNDO (con fecha), máximo 12"],
  "tareas": [
    {{"descripcion": "tarea concreta empezando con verbo, con el detalle necesario para hacerla",
      "responsables": ["nombre exacto de la lista"],
      "fecha_limite": "AAAA-MM-DD o null",
      "prioridad": "alta | media | baja",
      "entregable": "qué se debe entregar o cómo se sabe que quedó (corto) o null"}}
  ],
  "riesgos": ["pendientes, dudas sin resolver, riesgos o bloqueos mencionados; vacío si no hubo"],
  "conclusion": "conclusión de la reunión en 2 a 4 oraciones, con los siguientes pasos",
  "proxima_reunion": "fecha (AAAA-MM-DD), hora y tema de la siguiente reunión si se acordó, si no null",
  "fecha_entrega_proyecto": "AAAA-MM-DD o null",
  "duracion_min": número aproximado de minutos del audio
}}

Reglas:
- Escribe en español de México, formal, claro y profesional (es un documento oficial de la empresa).
- Usa los nombres completos de los participantes cuando se refieran a ellos (aunque en el audio digan solo el nombre de pila).
- Hoy es {hoy.isoformat()} ({dias[hoy.weekday()]}). Convierte TODA fecha relativa ("el viernes", "mañana", "en dos semanas",
  "a fin de mes") a fecha exacta AAAA-MM-DD. Si no se dijo fecha, pon null; no la inventes.
- En "responsables" usa SOLO nombres de esta lista de participantes, escritos exactamente igual. Si no queda claro quién, deja la lista vacía:
{lista}
- La prioridad es "alta" si se dijo que es urgente o bloquea otras cosas, "baja" si se dijo que puede esperar; si no, "media".
- No inventes tareas, acuerdos, cifras ni nombres que no se dijeron. Si el audio no tiene una reunión entendible,
  regresa los campos vacíos y en "resumen" explica por qué.
{('- Contexto que dio quien grabó: ' + contexto) if contexto else ''}"""


def _json(texto):
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    try:
        return json.loads(texto)
    except Exception:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            return json.loads(m.group(0))
        raise ErrorMinuta("Gemini no regresó la minuta en el formato esperado. Intenta de nuevo.")


def _normaliza(nombre):
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", str(nombre or "")) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().lower()


def _ligar_responsables(tareas, participantes):
    por_nombre = {_normaliza(p["nombre"]): p["id"] for p in participantes}
    salida = []
    for t in tareas or []:
        ids = []
        for n in t.get("responsables") or []:
            k = _normaliza(n)
            uid = por_nombre.get(k)
            if uid is None:   # por si solo dijo el nombre de pila o un apellido
                candidatos = [pid for pn, pid in por_nombre.items() if k and (k in pn or pn.split(" ")[0] == k.split(" ")[0])]
                uid = candidatos[0] if len(candidatos) == 1 else None
            if uid is not None and uid not in ids:
                ids.append(uid)
        fecha = t.get("fecha_limite")
        if not (isinstance(fecha, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha)):
            fecha = None
        if (t.get("descripcion") or "").strip():
            prioridad = str(t.get("prioridad") or "media").strip().lower()
            salida.append({"descripcion": t["descripcion"].strip()[:500], "usuario_ids": ids,
                           "responsables_dichos": t.get("responsables") or [], "fecha_limite": fecha,
                           "prioridad": prioridad if prioridad in ("alta", "media", "baja") else "media",
                           "entregable": (str(t.get("entregable") or "").strip() or None)})
    return salida


def analizar_reunion(audio: bytes, nombre_archivo: str, participantes: list[dict], contexto: str = "", hoy: date | None = None):
    """participantes: [{id, nombre, puesto}]. Regresa la minuta lista para revisar."""
    key = _api_key()
    mp3, mime = a_mp3(audio, nombre_archivo)
    archivo = _subir(mp3, mime, key)
    try:
        cuerpo = {
            "contents": [{"parts": [
                {"file_data": {"mime_type": archivo.get("mimeType") or mime, "file_uri": archivo["uri"]}},
                {"text": _prompt(participantes, (contexto or "").strip()[:500], hoy or date.today())},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        r = _generar(cuerpo, key)
        cands = r.json().get("candidates") or []
        if not cands:
            raise ErrorMinuta("Gemini no regresó respuesta (puede que el audio haya sido bloqueado por sus filtros).")
        texto = "".join(p.get("text", "") for p in (cands[0].get("content") or {}).get("parts", []))
        datos = _json(texto)
    finally:
        _borrar(archivo, key)
    lista = lambda v: [str(x).strip() for x in (v or []) if str(x).strip()]
    fecha = datos.get("fecha_entrega_proyecto")
    return {
        "titulo_proyecto": (datos.get("titulo_proyecto") or "Proyecto de la reunión").strip()[:160],
        "descripcion_proyecto": (datos.get("descripcion_proyecto") or "").strip(),
        "resumen": (datos.get("resumen") or "").strip(),
        "puntos_clave": lista(datos.get("puntos_clave")),
        "acuerdos": lista(datos.get("acuerdos")),
        "temas": [{"tema": str(t.get("tema") or "").strip(), "detalle": str(t.get("detalle") or "").strip()}
                  for t in (datos.get("temas") or []) if isinstance(t, dict) and (t.get("tema") or t.get("detalle"))],
        "riesgos": lista(datos.get("riesgos")),
        "proxima_reunion": (str(datos.get("proxima_reunion") or "").strip() or None)
                           if str(datos.get("proxima_reunion") or "").strip().lower() not in ("null", "none") else None,
        "conclusion": (datos.get("conclusion") or "").strip(),
        "tareas": _ligar_responsables(datos.get("tareas"), participantes),
        "fecha_entrega_proyecto": fecha if isinstance(fecha, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) else None,
        "duracion_min": datos.get("duracion_min"),
    }


_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _fecha_larga(iso):
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month - 1]} de {d.year}"
    except Exception:
        return str(iso or "")


def _fecha_corta(iso):
    try:
        d = date.fromisoformat(str(iso)[:10])
        return f"{_DIAS_CORTOS[d.weekday()]} {d.day:02d}/{d.month:02d}/{d.year}"
    except Exception:
        return str(iso or "") or "—"


def _logo_empresa(empresa):
    """Logo de la empresa (configurado en el sistema) o el de Mark Inc por defecto."""
    import base64
    datos = (empresa or {}).get("logo_base64") if isinstance(empresa, dict) else None
    if datos:
        try:
            return base64.b64decode(datos.split(",", 1)[1] if "," in datos else datos)
        except Exception:
            pass
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_mark_inc.png")
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except Exception:
        return None


_FUENTES = None


def _fuentes():
    """(normal, negrita, itálica). Bitstream Vera viene dentro de reportlab y trae todos los acentos y ²."""
    global _FUENTES
    if _FUENTES:
        return _FUENTES
    try:
        import reportlab
        from reportlab.lib.fonts import addMapping
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        d = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        for nombre, arch in (("MinVera", "Vera.ttf"), ("MinVera-Bold", "VeraBd.ttf"),
                             ("MinVera-Italic", "VeraIt.ttf"), ("MinVera-BoldItalic", "VeraBI.ttf")):
            pdfmetrics.registerFont(TTFont(nombre, os.path.join(d, arch)))
        addMapping("MinVera", 0, 0, "MinVera"); addMapping("MinVera", 1, 0, "MinVera-Bold")
        addMapping("MinVera", 0, 1, "MinVera-Italic"); addMapping("MinVera", 1, 1, "MinVera-BoldItalic")
        _FUENTES = ("MinVera", "MinVera-Bold", "MinVera-Italic")
    except Exception as ex:
        print(f"[minuta] sin fuente Vera ({ex}); uso Helvetica")
        _FUENTES = ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique")
    return _FUENTES


def pdf_minuta(m: dict, empresa, participantes: list[dict], fecha_reunion: str, autor: str,
               folio: str | None = None, hora: str | None = None, proyecto_folio: str | None = None) -> bytes:
    """Minuta oficial con el diseño de la empresa.
    empresa: dict de la empresa (nombre, logo_base64) o solo el nombre.
    participantes: [{id, nombre, puesto}]."""
    from io import BytesIO
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    F, FB, FI = _fuentes()
    ROJO = colors.HexColor("#D8192F")
    TINTA = colors.HexColor("#1B1B1D")
    GRIS = colors.HexColor("#5B5D62")
    LINEA = colors.HexColor("#D9D4CF")
    CREMA = colors.HexColor("#FAF6F2")
    ANCHO = letter[0] - 3.6 * cm

    nombre_empresa = (empresa.get("nombre") if isinstance(empresa, dict) else empresa) or "Mark Inc"
    folio = folio or "—"
    e = lambda t: escape(str(t if t is not None else ""))
    nombres = {p["id"]: p["nombre"] for p in participantes}

    st = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=st["BodyText"], fontName=F, fontSize=9.6, leading=13.4, textColor=TINTA)
    chico = ParagraphStyle("chico", parent=base, fontSize=8, leading=10.5, textColor=GRIS)
    etiqueta = ParagraphStyle("et", parent=base, fontName=FB, fontSize=7.4, leading=9, textColor=GRIS)
    valor = ParagraphStyle("val", parent=base, fontName=FB, fontSize=9.6, leading=12)
    celda = ParagraphStyle("celda", parent=base, fontSize=8.8, leading=11.4)
    celda_b = ParagraphStyle("celdab", parent=celda, fontName=FB)
    encab = ParagraphStyle("enc", parent=celda, fontName=FB, textColor=colors.white, fontSize=8.2)
    titulo = ParagraphStyle("tit", parent=base, fontName=FB, fontSize=17, leading=20, textColor=TINTA)
    sub = ParagraphStyle("sub", parent=base, fontSize=9, leading=11, textColor=ROJO, fontName=FB)
    tema_t = ParagraphStyle("tt", parent=base, fontName=FB, fontSize=9.8, spaceBefore=4)

    secciones = [0]

    def seccion(texto):
        secciones[0] += 1
        t = Table([[Paragraph(f"{secciones[0]}.&nbsp;&nbsp;{e(texto.upper())}",
                              ParagraphStyle("sec", parent=base, fontName=FB, fontSize=9.6,
                                             textColor=TINTA, leading=12))]],
                  colWidths=[ANCHO])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CREMA), ("LINEBEFORE", (0, 0), (0, -1), 3.2, ROJO),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        return [Spacer(1, 10), t, Spacer(1, 5)]

    def tabla(filas, anchos, estilo_extra=()):
        t = Table(filas, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TINTA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA), ("BOX", (0, 0), (-1, -1), 0.5, LINEA),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREMA]),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            *estilo_extra]))
        return t

    h = []
    # ---- Encabezado: logo | título | folio ----
    logo = _logo_empresa(empresa)
    celda_logo = ""
    if logo:
        try:
            iw, ih = ImageReader(BytesIO(logo)).getSize()
            w = 4.3 * cm
            hh = w * ih / iw
            if hh > 1.9 * cm:
                hh = 1.9 * cm
                w = hh * iw / ih
            celda_logo = Image(BytesIO(logo), width=w, height=hh)
        except Exception:
            celda_logo = ""
    caja_folio = Table([[Paragraph("FOLIO", ParagraphStyle("f1", parent=etiqueta, textColor=colors.white, alignment=TA_CENTER))],
                        [Paragraph(e(folio), ParagraphStyle("f2", parent=valor, textColor=colors.white, alignment=TA_CENTER, fontSize=11))],
                        [Paragraph(e(_fecha_corta(fecha_reunion)), ParagraphStyle("f3", parent=chico, textColor=colors.white, alignment=TA_CENTER))]],
                       colWidths=[3.4 * cm])
    caja_folio.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ROJO), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    cab = Table([[celda_logo,
                  [Paragraph("MINUTA DE REUNIÓN", titulo), Spacer(1, 2), Paragraph(e(nombre_empresa).upper(), sub)],
                  caja_folio]],
                colWidths=[4.8 * cm, ANCHO - 4.8 * cm - 3.6 * cm, 3.6 * cm])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                             ("LINEBELOW", (0, 0), (-1, 0), 2, ROJO), ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]))
    h += [cab, Spacer(1, 10)]

    # ---- Datos generales ----
    def dato(et, val):
        return [Paragraph(e(et).upper(), etiqueta), Paragraph(e(val) if val else "—", valor)]
    duracion = f"{m.get('duracion_min')} min aprox." if m.get("duracion_min") else None
    datos = [
        dato("Proyecto", m.get("titulo_proyecto")) + dato("Folio de proyecto", proyecto_folio or "Por crear"),
        dato("Fecha de la reunión", _fecha_larga(fecha_reunion)) + dato("Hora", hora),
        dato("Elaboró", autor) + dato("Duración", duracion),
        dato("Participantes", f"{len(participantes)} persona(s)") +
        dato("Entrega estimada", _fecha_larga(m["fecha_entrega_proyecto"]) if m.get("fecha_entrega_proyecto") else None),
    ]
    tdat = Table(datos, colWidths=[3.1 * cm, ANCHO / 2 - 3.1 * cm, 3.1 * cm, ANCHO / 2 - 3.1 * cm])
    tdat.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, LINEA),
                              ("INNERGRID", (0, 0), (-1, -1), 0.4, LINEA),
                              ("BACKGROUND", (0, 0), (0, -1), CREMA), ("BACKGROUND", (2, 0), (2, -1), CREMA),
                              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    h.append(tdat)

    if m.get("descripcion_proyecto"):
        h += seccion("Objetivo del proyecto") + [Paragraph(e(m["descripcion_proyecto"]), base)]

    if participantes:
        filas = [[Paragraph("#", encab), Paragraph("Nombre", encab), Paragraph("Puesto", encab), Paragraph("Firma", encab)]]
        for i, p in enumerate(participantes, 1):
            filas.append([Paragraph(str(i), celda), Paragraph(e(p["nombre"]), celda_b), Paragraph(e(p.get("puesto") or "—"), celda), Spacer(1, 16)])
        h += seccion("Participantes") + [tabla(filas, [0.8 * cm, 6.6 * cm, 5.2 * cm, ANCHO - 12.6 * cm])]

    if m.get("resumen"):
        h += seccion("Resumen ejecutivo") + [Paragraph(e(m["resumen"]), base)]

    temas = [t for t in (m.get("temas") or []) if isinstance(t, dict)]
    if temas:
        h += seccion("Temas tratados")
        n = secciones[0]
        for i, t in enumerate(temas, 1):
            h.append(KeepTogether([Paragraph(f"{n}.{i}&nbsp;&nbsp;{e(t.get('tema'))}", tema_t),
                                   Paragraph(e(t.get("detalle")), base), Spacer(1, 3)]))

    if m.get("puntos_clave"):
        h += seccion("Puntos clave")
        h += [Paragraph(f"<font color='#D8192F'><b>•</b></font>&nbsp;&nbsp;{e(x)}", base) for x in m["puntos_clave"]]

    if m.get("acuerdos"):
        filas = [[Paragraph("#", encab), Paragraph("Acuerdo", encab)]]
        filas += [[Paragraph(str(i), celda_b), Paragraph(e(x), celda)] for i, x in enumerate(m["acuerdos"], 1)]
        h += seccion("Acuerdos") + [tabla(filas, [0.8 * cm, ANCHO - 0.8 * cm])]

    tareas = m.get("tareas") or []
    if tareas:
        colores = {"alta": "#C0141F", "media": "#B8650F", "baja": "#2E7D4F"}
        filas = [[Paragraph(x, encab) for x in ("#", "Actividad", "Responsable(s)", "Fecha compromiso", "Prioridad")]]
        for i, t in enumerate(tareas, 1):
            resp = ", ".join(nombres.get(u, "") for u in t.get("usuario_ids") or [] if nombres.get(u)) \
                or ", ".join(t.get("responsables_dichos") or []) or "Sin asignar"
            act = e(t.get("descripcion"))
            if t.get("entregable"):
                act += f"<br/><font size='7.6' color='#5B5D62'><i>Entregable: {e(t['entregable'])}</i></font>"
            pr = str(t.get("prioridad") or "media").lower()
            filas.append([Paragraph(str(i), celda_b), Paragraph(act, celda), Paragraph(e(resp), celda_b),
                          Paragraph(e(_fecha_corta(t.get("fecha_limite")) if t.get("fecha_limite") else "Por definir"), celda),
                          Paragraph(f"<font color='{colores.get(pr, '#B8650F')}'><b>{e(pr.capitalize())}</b></font>", celda)])
        h += seccion("Plan de trabajo y responsables") + [
            tabla(filas, [0.8 * cm, ANCHO - 0.8 * cm - 4.0 * cm - 2.8 * cm - 2.1 * cm, 4.0 * cm, 2.8 * cm, 2.1 * cm])]

    if m.get("riesgos"):
        h += seccion("Pendientes y riesgos")
        h += [Paragraph(f"<font color='#D8192F'><b>!</b></font>&nbsp;&nbsp;{e(x)}", base) for x in m["riesgos"]]

    if m.get("conclusion"):
        h += seccion("Conclusión") + [Paragraph(e(m["conclusion"]), base)]

    if m.get("proxima_reunion"):
        caja = Table([[Paragraph("PRÓXIMA REUNIÓN", ParagraphStyle("pr", parent=etiqueta, textColor=ROJO)),
                       Paragraph(e(re.sub(r"\d{4}-\d{2}-\d{2}", lambda x: _fecha_larga(x.group(0)), m["proxima_reunion"])), valor)]], colWidths=[3.6 * cm, ANCHO - 3.6 * cm])
        caja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, ROJO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        h += [Spacer(1, 12), caja]

    # ---- Firmas ----
    def linea_firma(quien, rol):
        return [Spacer(1, 34), Table([[""]], colWidths=[6.2 * cm], style=[("LINEABOVE", (0, 0), (-1, -1), 0.8, TINTA)]),
                Paragraph(f"<b>{e(quien)}</b>", ParagraphStyle("fq", parent=celda, alignment=TA_CENTER)),
                Paragraph(e(rol), ParagraphStyle("fr", parent=chico, alignment=TA_CENTER))]
    firmas = Table([[linea_firma(autor or "", "Elaboró"), linea_firma("\u00a0", "Vo. Bo. (nombre y firma)")]], colWidths=[ANCHO / 2, ANCHO / 2])
    firmas.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    h += [KeepTogether([Spacer(1, 8), firmas])]
    h += [Spacer(1, 14), Paragraph(
        "Minuta generada con inteligencia artificial a partir del audio de la reunión y revisada por quien la elaboró. "
        "El audio no se conserva. Los acuerdos y tareas aquí descritos quedan registrados en el proyecto correspondiente.", chico)]

    pie_izq = f"{nombre_empresa} · Minuta {folio} · Documento interno"

    class _Lienzo(rl_canvas.Canvas):
        """Pie con 'Página X de Y'."""
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for estado in self._paginas:
                self.__dict__.update(estado)
                self.setStrokeColor(ROJO)
                self.setLineWidth(0.8)
                self.line(1.8 * cm, 1.35 * cm, letter[0] - 1.8 * cm, 1.35 * cm)
                self.setFont(F, 7.5)
                self.setFillColor(GRIS)
                self.drawString(1.8 * cm, 0.95 * cm, pie_izq)
                self.drawRightString(letter[0] - 1.8 * cm, 0.95 * cm, f"Página {self._pageNumber} de {total}")
                super().showPage()
            super().save()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.9 * cm, title=f"Minuta {folio} — {m.get('titulo_proyecto') or ''}",
                            author=autor or nombre_empresa, subject="Minuta de reunión")
    doc.build(h, canvasmaker=_Lienzo)
    return buf.getvalue()
