"""Integración con la API de Claude (Anthropic) para leer fotos/imágenes
Y AHORA TAMBIÉN documentos (PDF, Word, Excel, CSV) con listas de
artículos, extraer nombre + cantidad de cada uno, para después
buscarlos en Microsip y armar una cotización.

Requiere la variable de entorno ANTHROPIC_API_KEY. Si no está
configurada, las funciones de este módulo lanzan RuntimeError con un
mensaje claro (la app sigue funcionando normal para todo lo demás).
"""
import base64
import io
import json
import os
import re

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# Sonnet da mejor lectura de letra manuscrita/fotos de empaque y de
# documentos largos que un modelo más chico — el costo por archivo
# sigue siendo unos centavos.
MODELO_LECTURA_IMAGEN = "claude-sonnet-5"

PROMPT_LECTURA_LISTA = """Este archivo puede ser: una lista escrita a mano, una lista impresa o \
captura de pantalla, fotos de productos físicos (empaques/etiquetas), o un documento \
(PDF/Word/Excel) con una lista o tabla de artículos/pedido/cotización. \
Identifica cada artículo/producto que aparezca y su cantidad.

Reglas:
- Si no hay cantidad especificada para un artículo, usa 1.
- Si es una foto de un producto físico, usa el nombre/marca/modelo que \
alcances a leer en el empaque o etiqueta como el nombre del artículo.
- Si es una tabla (Excel o tabla dentro de un Word/PDF), identifica cuál columna es \
el nombre/descripción del artículo y cuál es la cantidad — ignora columnas de precio, \
importe, IVA, etc.
- Ignora encabezados, totales, subtotales, precios, fechas, o cualquier texto que no \
sea un artículo en sí.
- Si de verdad no hay ningún artículo identificable, regresa una lista vacía.

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después, con \
esta forma exacta:
{"items": [{"nombre": "texto tal cual lo leíste", "cantidad": 1}]}"""

# Extensiones que tratamos como "documento de oficina" (se les extrae el
# texto/tabla en Python y se le manda a Claude como texto, no como imagen).
EXTENSIONES_DOCX = (".docx",)
EXTENSIONES_XLSX = (".xlsx", ".xlsm", ".xls")
EXTENSIONES_CSV = (".csv",)


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno ANTHROPIC_API_KEY. Configúrala en Render "
            "(Environment) con tu API key de console.anthropic.com para poder usar "
            "la lectura de imágenes/documentos."
        )
    return key


def _extraer_json(texto: str):
    """Claude normalmente responde solo el JSON, pero por si acaso viene
    con ```json ... ``` alrededor o algo de texto extra, lo limpiamos
    antes de parsear."""
    texto = texto.strip()
    texto = re.sub(r"^```json\s*|^```\s*|\s*```$", "", texto.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        texto = match.group(0)
    return json.loads(texto)


def _decodificar_base64(datos_base64: str, media_type_por_defecto: str):
    """Acepta tanto un data URL completo (data:...;base64,....) como puro
    base64. Regresa (bytes_crudos, media_type)."""
    media_type = media_type_por_defecto
    if datos_base64.startswith("data:"):
        try:
            media_type = datos_base64.split(";")[0].split(":")[1]
            datos_base64 = datos_base64.split(",", 1)[1]
        except (IndexError, ValueError):
            pass
    return base64.b64decode(datos_base64), media_type


def _texto_desde_docx(datos_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(datos_bytes))
    partes = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabla in doc.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells]
            if any(celdas):
                partes.append(" | ".join(celdas))
    return "\n".join(partes)


def _texto_desde_xlsx(datos_bytes: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(datos_bytes), data_only=True)
    partes = []
    for hoja in wb.worksheets:
        for fila in hoja.iter_rows(values_only=True):
            valores = [str(v) for v in fila if v is not None and str(v).strip()]
            if valores:
                partes.append(" | ".join(valores))
    return "\n".join(partes)


def _texto_desde_csv(datos_bytes: bytes) -> str:
    for codificacion in ("utf-8", "latin-1"):
        try:
            return datos_bytes.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos_bytes.decode("utf-8", errors="ignore")


def _llamar_claude(bloques_contenido):
    api_key = _api_key()
    body = {
        "model": MODELO_LECTURA_IMAGEN,
        "max_tokens": 2000,
        "messages": [
            {"role": "user", "content": bloques_contenido},
            # "Prefill": forzamos a que la respuesta empiece exactamente con "{" —
            # así Claude no puede anteponer explicaciones ni texto antes del JSON,
            # sin importar qué tan complejo o visualmente cargado sea el PDF/imagen.
            {"role": "assistant", "content": "{"},
        ],
    }
    try:
        r = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=body,
            timeout=90,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"No se pudo conectar con la API de Claude: {e}")

    if r.status_code == 401:
        raise RuntimeError("La API key de Anthropic no es válida (revisa ANTHROPIC_API_KEY en Render).")
    if r.status_code == 429:
        raise RuntimeError("Se alcanzó el límite de uso de la API de Claude por ahora — intenta en un momento.")
    if not r.ok:
        detalle = r.text[:300]
        raise RuntimeError(f"La API de Claude respondió con error ({r.status_code}): {detalle}")

    data = r.json()
    bloques_texto = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    # Claude continúa desde donde dejamos el prefill ("{"), así que se lo
    # volvemos a pegar al principio antes de parsear.
    texto_completo = "{" + "\n".join(bloques_texto)
    if texto_completo.strip() == "{":
        raise RuntimeError("Claude no regresó contenido en la respuesta.")

    try:
        parseado = _extraer_json(texto_completo)
    except (json.JSONDecodeError, ValueError):
        fragmento = texto_completo.strip().replace("\n", " ")[:200]
        raise RuntimeError(
            "No se pudo leer la respuesta de Claude como lista de artículos. "
            f"Esto fue lo que respondió: \"{fragmento}\""
        )

    items = parseado.get("items", []) if isinstance(parseado, dict) else []
    if not isinstance(items, list):
        items = []
    resultado = []
    for it in items:
        if not isinstance(it, dict):
            continue
        nombre = (it.get("nombre") or "").strip()
        if not nombre:
            continue
        try:
            cantidad = float(it.get("cantidad") or 1)
        except (TypeError, ValueError):
            cantidad = 1
        resultado.append({"nombre": nombre, "cantidad": cantidad})
    return resultado


def leer_lista_de_imagen(imagen_base64: str, media_type: str = "image/jpeg"):
    """Compatibilidad con el nombre anterior — sigue funcionando igual
    que antes para imágenes."""
    return leer_lista_de_archivo(imagen_base64, nombre_archivo="imagen.jpg", media_type=media_type)


def leer_lista_de_archivo(datos_base64: str, nombre_archivo: str = "", media_type: str = "application/octet-stream"):
    """Punto de entrada único: detecta si es imagen, PDF, Word, Excel o
    CSV, y arma el mensaje correcto para Claude en cada caso. Regresa
    una lista de dicts {"nombre": str, "cantidad": float}."""
    datos_bytes, media_type = _decodificar_base64(datos_base64, media_type)
    nombre_lower = (nombre_archivo or "").lower()

    if media_type.startswith("image/"):
        bloques = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(datos_bytes).decode()}},
            {"type": "text", "text": PROMPT_LECTURA_LISTA},
        ]
        return _llamar_claude(bloques)

    if media_type == "application/pdf" or nombre_lower.endswith(".pdf"):
        bloques = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(datos_bytes).decode()}},
            {"type": "text", "text": PROMPT_LECTURA_LISTA},
        ]
        return _llamar_claude(bloques)

    if nombre_lower.endswith(EXTENSIONES_DOCX) or "wordprocessingml" in media_type:
        try:
            texto = _texto_desde_docx(datos_bytes)
        except Exception as e:
            raise RuntimeError(f"No se pudo leer el archivo Word: {e}")
        return _llamar_claude_con_texto(texto)

    if nombre_lower.endswith(EXTENSIONES_XLSX) or "spreadsheetml" in media_type or media_type == "application/vnd.ms-excel":
        try:
            texto = _texto_desde_xlsx(datos_bytes)
        except Exception as e:
            raise RuntimeError(f"No se pudo leer el archivo Excel: {e}")
        return _llamar_claude_con_texto(texto)

    if nombre_lower.endswith(EXTENSIONES_CSV) or media_type == "text/csv":
        texto = _texto_desde_csv(datos_bytes)
        return _llamar_claude_con_texto(texto)

    raise RuntimeError(
        "Ese tipo de archivo no lo puedo leer todavía. Sube una imagen (foto), PDF, Word (.docx) o Excel (.xlsx/.csv)."
    )


def _llamar_claude_con_texto(texto_extraido: str):
    if not texto_extraido.strip():
        return []
    # Si el documento es enorme, lo recortamos para no disparar el costo/tiempo
    # de una sola llamada — para listas de artículos esto es más que suficiente.
    texto_extraido = texto_extraido[:40000]
    bloques = [
        {"type": "text", "text": f"Contenido del documento:\n\n{texto_extraido}\n\n{PROMPT_LECTURA_LISTA}"},
    ]
    return _llamar_claude(bloques)
