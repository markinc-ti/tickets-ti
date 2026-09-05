"""Integración con la API de Claude (Anthropic) para leer fotos/imágenes
de listas de artículos (a mano, impresas, capturas de pantalla, o fotos
de producto) y extraer nombre + cantidad de cada uno, para después
buscarlos en Microsip y armar una cotización.

Requiere la variable de entorno ANTHROPIC_API_KEY. Si no está
configurada, las funciones de este módulo lanzan RuntimeError con un
mensaje claro (la app sigue funcionando normal para todo lo demás).
"""
import base64
import json
import os
import re

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# Sonnet da mejor lectura de letra manuscrita/fotos de empaque que un
# modelo más chico — el costo por imagen sigue siendo unos centavos.
MODELO_LECTURA_IMAGEN = "claude-sonnet-5"

PROMPT_LECTURA_LISTA = """Esta imagen puede ser: una lista escrita a mano, una lista impresa o \
captura de pantalla, o fotos de productos físicos (empaques/etiquetas). \
Identifica cada artículo/producto que aparezca y su cantidad.

Reglas:
- Si no hay cantidad especificada para un artículo, usa 1.
- Si es una foto de un producto físico, usa el nombre/marca/modelo que \
alcances a leer en el empaque o etiqueta como el nombre del artículo.
- Ignora encabezados, totales, precios, fechas o cualquier texto que no \
sea un artículo en sí.
- Si de verdad no hay ningún artículo identificable en la imagen, regresa \
una lista vacía.

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después, con \
esta forma exacta:
{"items": [{"nombre": "texto tal cual lo leíste", "cantidad": 1}]}"""


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno ANTHROPIC_API_KEY. Configúrala en Render "
            "(Environment) con tu API key de console.anthropic.com para poder usar "
            "la lectura de imágenes."
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


def leer_lista_de_imagen(imagen_base64: str, media_type: str = "image/jpeg"):
    """Manda la imagen a Claude y regresa una lista de dicts
    {"nombre": str, "cantidad": float}. Lanza RuntimeError con un
    mensaje claro si algo sale mal (falta la key, la API responde con
    error, o la respuesta no es JSON válido)."""
    api_key = _api_key()

    # Por si el front manda el data URL completo (data:image/jpeg;base64,....)
    if imagen_base64.startswith("data:"):
        try:
            media_type = imagen_base64.split(";")[0].split(":")[1]
            imagen_base64 = imagen_base64.split(",", 1)[1]
        except (IndexError, ValueError):
            pass

    body = {
        "model": MODELO_LECTURA_IMAGEN,
        "max_tokens": 2000,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": imagen_base64}},
                {"type": "text", "text": PROMPT_LECTURA_LISTA},
            ],
        }],
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
            timeout=60,
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
    texto_completo = "\n".join(bloques_texto)
    if not texto_completo.strip():
        raise RuntimeError("Claude no regresó texto en la respuesta.")

    try:
        parseado = _extraer_json(texto_completo)
    except (json.JSONDecodeError, ValueError):
        raise RuntimeError("No se pudo leer la respuesta de Claude como lista de artículos. Intenta con otra foto, más clara.")

    items = parseado.get("items", []) if isinstance(parseado, dict) else []
    resultado = []
    for it in items:
        nombre = (it.get("nombre") or "").strip()
        if not nombre:
            continue
        try:
            cantidad = float(it.get("cantidad") or 1)
        except (TypeError, ValueError):
            cantidad = 1
        resultado.append({"nombre": nombre, "cantidad": cantidad})
    return resultado
