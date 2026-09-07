"""Generación de imágenes de promoción con la API de Gemini (Google) —
a diferencia de ia.py (que usa Claude para LEER imágenes/documentos),
este módulo CREA imágenes desde cero a partir de una descripción y,
si se le dan, fotos de referencia reales de los productos.

Requiere la variable de entorno GEMINI_API_KEY (se consigue gratis/con
saldo en aistudio.google.com — es una cuenta y costo APARTE de la de
Anthropic). Sin ella, lanza RuntimeError con un mensaje claro.

Importante: los modelos de generación de imágenes NO son confiables
para texto exacto (precios, teléfonos) — esto es una limitación del
estado del arte, no un bug de esta integración. Los precios/nombres se
mandan en el prompt para que el modelo los use, pero SIEMPRE hay que
revisar la imagen final a mano antes de publicarla.
"""
import base64
import os

import requests

import db

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
MODELO_IMAGEN = "gemini-2.5-flash-image"


def _api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno GEMINI_API_KEY. Configúrala en Render "
            "(Environment) con tu API key de aistudio.google.com para poder generar "
            "imágenes de promoción."
        )
    return key


def _decodificar_base64(datos_base64: str, media_type_por_defecto: str = "image/jpeg"):
    media_type = media_type_por_defecto
    if datos_base64.startswith("data:"):
        try:
            media_type = datos_base64.split(";")[0].split(":")[1]
            datos_base64 = datos_base64.split(",", 1)[1]
        except (IndexError, ValueError):
            pass
    return base64.b64decode(datos_base64), media_type


def _construir_prompt(nombre_promocion, items, descripcion_usuario, marca):
    lineas_items = "\n".join(
        f"- {it['nombre']} (cantidad {it.get('cantidad', 1)}): ${it['precio_promocional']:,.2f} MXN"
        for it in items
    )
    return f"""Diseña una imagen publicitaria de redes sociales (formato cuadrado o vertical, \
estilo flyer/post de Instagram-Facebook) para una promoción de la empresa "{marca}" \
(productos/equipo dental).

Nombre de la promoción: {nombre_promocion}

Artículos incluidos y su precio de promoción:
{lineas_items}

Instrucciones de diseño del usuario:
{descripcion_usuario or "Usa un diseño profesional, llamativo, colores acordes a una marca de equipo dental."}

Muestra el/los producto(s) de forma prominente. Incluye el nombre de la promoción y \
los precios de forma clara y legible. El diseño debe verse profesional, listo para \
publicarse en redes sociales."""


def _generar_una_imagen(prompt_texto, fotos_referencia_base64):
    api_key = _api_key()
    partes = [{"text": prompt_texto}]
    for foto in (fotos_referencia_base64 or [])[:3]:  # máximo 3 referencias, para no disparar el tamaño del request
        try:
            datos_bytes, media_type = _decodificar_base64(foto)
        except Exception:
            continue
        partes.append({"inline_data": {"mime_type": media_type, "data": base64.b64encode(datos_bytes).decode()}})

    body = {
        "contents": [{"parts": partes}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    try:
        r = requests.post(
            GEMINI_API_URL.format(modelo=MODELO_IMAGEN),
            headers={"x-goog-api-key": api_key, "content-type": "application/json"},
            json=body,
            timeout=90,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"No se pudo conectar con la API de Gemini: {e}")

    if r.status_code == 401 or r.status_code == 403:
        raise RuntimeError("La API key de Gemini no es válida (revisa GEMINI_API_KEY en Render).")
    if r.status_code == 429:
        raise RuntimeError("Se alcanzó el límite de uso de la API de Gemini por ahora — intenta en un momento.")
    if not r.ok:
        raise RuntimeError(f"La API de Gemini respondió con error ({r.status_code}): {r.text[:300]}")

    data = r.json()
    candidatos = data.get("candidates", [])
    if not candidatos:
        raise RuntimeError("Gemini no regresó ninguna imagen (puede que el prompt haya sido bloqueado por sus filtros de seguridad).")

    partes_respuesta = candidatos[0].get("content", {}).get("parts", [])
    for parte in partes_respuesta:
        # La API acepta inline_data en la petición pero puede regresar
        # inlineData (camelCase) en la respuesta — checamos ambas formas.
        inline = parte.get("inlineData") or parte.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return f"data:{mime};base64,{inline['data']}"

    raise RuntimeError("Gemini respondió pero no incluyó ninguna imagen.")


def generar_imagenes_promocion(nombre_promocion, items, descripcion_usuario, fotos_referencia_base64, marca="Mark·Inc", n=3, empresa_id=None):
    """Genera n variantes (por default 3) de la imagen de promoción.
    Regresa una lista de data URLs (base64). Si alguna variante falla,
    sigue con las demás — solo lanza error si NINGUNA se pudo generar."""
    prompt = _construir_prompt(nombre_promocion, items, descripcion_usuario, marca)
    resultados = []
    errores = []
    for _ in range(n):
        try:
            resultados.append(_generar_una_imagen(prompt, fotos_referencia_base64))
        except RuntimeError as e:
            errores.append(str(e))
    try:
        # Costo aproximado publicado de Gemini 2.5 Flash Image — no exacto,
        # para tener idea del gasto (revisa Google AI Studio para el real).
        db.registrar_consumo(empresa_id, "generar_imagen_promocion", len(resultados), "imagen", round(len(resultados) * 0.039, 6))
    except Exception:
        pass
    if not resultados:
        raise RuntimeError(errores[0] if errores else "No se pudo generar ninguna imagen.")
    return resultados
