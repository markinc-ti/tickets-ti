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
MODELO = os.getenv("GEMINI_MODELO_MINUTA", "gemini-2.5-flash")


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


def _prompt(participantes, contexto, hoy):
    lista = "\n".join(f"- {p['nombre']}" + (f" ({p['puesto']})" if p.get("puesto") else "") for p in participantes) or "- (no se indicaron)"
    return f"""Eres el asistente que levanta la minuta de una reunión de trabajo de una empresa mexicana
(Productos Dentales Mark Inc). Escucha TODO el audio y regresa SOLO un JSON (sin texto antes ni después) así:

{{
  "titulo_proyecto": "nombre corto del proyecto que salió de la reunión (máx. 80 caracteres)",
  "descripcion_proyecto": "qué se va a hacer y para qué, en 2 a 4 oraciones",
  "resumen": "resumen de la reunión en un párrafo de 4 a 8 oraciones",
  "puntos_clave": ["los mejores puntos tratados, uno por renglón, máximo 10"],
  "acuerdos": ["decisiones o acuerdos tomados, máximo 10"],
  "conclusion": "conclusión de la reunión en 2 a 4 oraciones",
  "tareas": [
    {{"descripcion": "tarea concreta, empezando con verbo", "responsables": ["nombre exacto de la lista"], "fecha_limite": "AAAA-MM-DD o null"}}
  ],
  "fecha_entrega_proyecto": "AAAA-MM-DD o null",
  "duracion_min": número aproximado de minutos del audio
}}

Reglas:
- Escribe en español de México, claro y profesional.
- Hoy es {hoy.isoformat()} ({['lunes','martes','miércoles','jueves','viernes','sábado','domingo'][hoy.weekday()]}). Si dicen "el viernes" o "en dos semanas", conviértelo a fecha. Si no se dijo fecha, pon null.
- En "responsables" usa SOLO nombres de esta lista de participantes, escritos exactamente igual. Si no queda claro quién, deja la lista vacía:
{lista}
- No inventes tareas ni acuerdos que no se dijeron. Si el audio no tiene una reunión entendible, regresa los campos vacíos y en "resumen" explica por qué.
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
            salida.append({"descripcion": t["descripcion"].strip()[:500], "usuario_ids": ids,
                           "responsables_dichos": t.get("responsables") or [], "fecha_limite": fecha})
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
        r = requests.post(f"{API}/v1beta/models/{MODELO}:generateContent", headers={"x-goog-api-key": key,
                          "content-type": "application/json"}, json=cuerpo, timeout=900)
        _revisar(r)
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
        "conclusion": (datos.get("conclusion") or "").strip(),
        "tareas": _ligar_responsables(datos.get("tareas"), participantes),
        "fecha_entrega_proyecto": fecha if isinstance(fecha, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) else None,
        "duracion_min": datos.get("duracion_min"),
    }


def pdf_minuta(m: dict, empresa: str, participantes: list[dict], fecha_reunion: str, autor: str) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    rojo = colors.HexColor("#D8192F")
    st = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=st["Title"], fontSize=18, textColor=colors.HexColor("#221512"), alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=st["Heading2"], fontSize=12.5, textColor=rojo, spaceBefore=10, spaceAfter=4)
    tx = ParagraphStyle("tx", parent=st["BodyText"], fontSize=10, leading=14)
    pe = ParagraphStyle("pe", parent=tx, fontSize=8.5, textColor=colors.HexColor("#555555"))
    e = lambda t: escape(str(t or ""))
    nombres = {p["id"]: p["nombre"] for p in participantes}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title=f"Minuta — {m.get('titulo_proyecto') or ''}")
    h = [Paragraph(e(empresa).upper(), ParagraphStyle("em", parent=tx, textColor=rojo, fontSize=9)),
         Paragraph(f"Minuta de reunión: {e(m.get('titulo_proyecto'))}", h1),
         Paragraph(f"Fecha: {e(fecha_reunion)} · Levantó: {e(autor)}"
                   + (f" · Duración aprox.: {e(m.get('duracion_min'))} min" if m.get("duracion_min") else ""), pe),
         HRFlowable(width="100%", color=rojo, thickness=1.2, spaceBefore=6, spaceAfter=6)]
    if participantes:
        h += [Paragraph("Participantes", h2), Paragraph(e(", ".join(p["nombre"] for p in participantes)), tx)]
    if m.get("descripcion_proyecto"):
        h += [Paragraph("Proyecto", h2), Paragraph(e(m["descripcion_proyecto"]), tx)]
    if m.get("resumen"):
        h += [Paragraph("Resumen", h2), Paragraph(e(m["resumen"]), tx)]
    for titulo, clave in (("Puntos clave", "puntos_clave"), ("Acuerdos", "acuerdos")):
        if m.get(clave):
            h.append(Paragraph(titulo, h2))
            h += [Paragraph(f"• {e(x)}", tx) for x in m[clave]]
    if m.get("tareas"):
        h.append(Paragraph("Tareas asignadas", h2))
        filas = [["#", "Tarea", "Responsable(s)", "Fecha límite"]]
        for i, t in enumerate(m["tareas"], 1):
            resp = ", ".join(nombres.get(u, "") for u in t.get("usuario_ids") or []) or ", ".join(t.get("responsables_dichos") or []) or "Sin asignar"
            filas.append([str(i), Paragraph(e(t.get("descripcion")), tx), Paragraph(e(resp), tx), e(t.get("fecha_limite") or "—")])
        tabla = Table(filas, colWidths=[0.8 * cm, 9.2 * cm, 4.5 * cm, 2.6 * cm], repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rojo), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF6F2")]),
        ]))
        h.append(tabla)
    if m.get("conclusion"):
        h += [Paragraph("Conclusión", h2), Paragraph(e(m["conclusion"]), tx)]
    h += [Spacer(1, 14), Paragraph("Minuta generada con IA a partir del audio de la reunión (el audio no se guarda). "
                                   "Revisada por quien la levantó antes de crear el proyecto.", pe)]
    doc.build(h)
    return buf.getvalue()
