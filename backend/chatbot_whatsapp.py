"""Chatbot de WhatsApp para CLIENTES — distinto de Mouse (que es el
asistente interno para empleados). Responde preguntas de productos,
precio y existencia, confirma dudas generales, y si detecta interés
real de compra dirige al cliente hacia el equipo de ventas humano.

Usa la misma ANTHROPIC_API_KEY que Mouse e ia.py — no necesita otra.
"""
import json
import os

import requests

import db

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODELO_CHATBOT = "claude-sonnet-5"
MAX_VUELTAS_HERRAMIENTAS = 4

SYSTEM_PROMPT_BASE = """Eres el chatbot de atención por WhatsApp de "{marca}", una empresa de \
equipo/productos dentales. Le hablas directo a un CLIENTE o posible cliente por WhatsApp — \
NUNCA a un empleado interno.

Tu trabajo:
1. Responder preguntas sobre productos, precios y existencia usando la herramienta de \
consulta a Microsip — nunca inventes precios ni disponibilidad.
2. Resolver dudas generales sobre la empresa de forma amable y breve (mensajes de WhatsApp \
cortos, no correos largos).
3. Si el cliente muestra intención real de compra (quiere cotización formal, quiere que le \
llamen, pregunta por financiamiento, quiere agendar algo), usa la herramienta \
marcar_cliente_interesado para avisarle al equipo de ventas, y dile al cliente que en breve \
alguien del equipo le va a contactar.
4. Si no sabes algo o el cliente pide hablar con una persona, dile amablemente que ahora \
mismo le avisas al equipo para que le contacten (y usa marcar_cliente_interesado también en \
ese caso).

Nunca reveles que eres una IA a menos que te pregunten directamente. Sé cordial, profesional, \
breve — como un buen mensaje de WhatsApp, no un ensayo."""

HERRAMIENTAS = [
    {
        "name": "consultar_precio_existencia_microsip",
        "description": "Busca un artículo por nombre en Microsip y regresa su precio de lista y existencia disponible.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre": {"type": "string", "description": "Nombre o parte del nombre del artículo"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "marcar_cliente_interesado",
        "description": "Registra que este cliente mostró intención real de compra o pidió hablar con una persona, para que el equipo de ventas le dé seguimiento.",
        "input_schema": {
            "type": "object",
            "properties": {"resumen": {"type": "string", "description": "Resumen breve de qué quiere el cliente, para que ventas lo lea rápido"}},
            "required": ["resumen"],
        },
    },
]


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Falta ANTHROPIC_API_KEY.")
    return key


def _system_prompt(empresa_id, marca):
    base = SYSTEM_PROMPT_BASE.format(marca=marca)
    notas = db.listar_conocimiento_asistente(empresa_id)
    if notas:
        lista = "\n".join(f"- {n['texto']}" for n in notas)
        base += f"\n\nInformación específica de esta empresa que debes usar cuando aplique:\n{lista}"
    return base


def _ejecutar_herramienta(nombre, entrada, empresa_id, cliente_id):
    try:
        if nombre == "consultar_precio_existencia_microsip":
            import microsip
            config = db.obtener_config_microsip(empresa_id)
            if not config or not config.get("microsip_host"):
                return {"error": "No se pudo consultar el inventario en este momento."}
            texto = (entrada.get("nombre") or "").strip()
            if not texto:
                return {"error": "Falta el nombre del artículo."}
            candidatos = microsip.buscar_productos_por_nombre(config, texto, limite=5)
            if not candidatos:
                return {"resultado": "No se encontró ningún artículo con ese nombre."}
            resultados = []
            for c in candidatos:
                detalle = microsip.buscar_producto_por_articulo_id(config, c["articulo_id"]) or {}
                resultados.append({
                    "nombre": c["nombre"],
                    "precio_con_impuesto": detalle.get("precio_con_impuesto"),
                    "disponible_total": detalle.get("disponible_total"),
                })
            return {"articulos_encontrados": resultados}

        if nombre == "marcar_cliente_interesado":
            resumen = (entrada.get("resumen") or "Mostró interés en el chat de WhatsApp").strip()
            if cliente_id:
                db.crear_tarea_crm(
                    empresa_id, cliente_id, None, "Dar seguimiento — interés detectado en WhatsApp",
                    resumen, None, None, None,
                )
            return {"ok": True}

        return {"error": f"Herramienta desconocida: {nombre}"}
    except Exception as e:
        return {"error": f"No se pudo completar esa acción: {e}"}


_PRECIO_INPUT_POR_MTOK_USD = 3.0
_PRECIO_OUTPUT_POR_MTOK_USD = 15.0


def _registrar_uso_claude(empresa_id, data, tipo):
    try:
        uso = data.get("usage", {})
        tokens_in = uso.get("input_tokens", 0) or 0
        tokens_out = uso.get("output_tokens", 0) or 0
        costo = (tokens_in / 1_000_000 * _PRECIO_INPUT_POR_MTOK_USD) + (tokens_out / 1_000_000 * _PRECIO_OUTPUT_POR_MTOK_USD)
        db.registrar_consumo(empresa_id, tipo, tokens_in + tokens_out, "tokens", round(costo, 6))
    except Exception:
        pass


def responder_mensaje_cliente(empresa_id, cliente_id, mensaje, marca="la empresa"):
    """Manda el mensaje del cliente a Claude (con las herramientas de
    arriba) y regresa el texto de la respuesta final. Lanza RuntimeError
    si algo falla con la API."""
    api_key = _api_key()
    mensajes = [{"role": "user", "content": mensaje}]

    for _ in range(MAX_VUELTAS_HERRAMIENTAS):
        r = requests.post(
            ANTHROPIC_API_URL,
            headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"},
            json={
                "model": MODELO_CHATBOT,
                "max_tokens": 1024,
                "system": _system_prompt(empresa_id, marca),
                "tools": HERRAMIENTAS,
                "messages": mensajes,
            },
            timeout=45,
        )
        if not r.ok:
            raise RuntimeError(f"Error de la API de Claude ({r.status_code}): {r.text[:200]}")

        data = r.json()
        _registrar_uso_claude(empresa_id, data, "chatbot_whatsapp_mensaje")
        contenido = data.get("content", [])
        mensajes.append({"role": "assistant", "content": contenido})

        bloques_tool_use = [b for b in contenido if b.get("type") == "tool_use"]
        if not bloques_tool_use:
            textos = [b["text"] for b in contenido if b.get("type") == "text"]
            return "\n".join(textos).strip() or "Gracias por tu mensaje, en breve te atendemos."

        resultados = []
        for bloque in bloques_tool_use:
            resultado = _ejecutar_herramienta(bloque["name"], bloque.get("input", {}), empresa_id, cliente_id)
            resultados.append({"type": "tool_result", "tool_use_id": bloque["id"], "content": json.dumps(resultado, ensure_ascii=False, default=str)})
        mensajes.append({"role": "user", "content": resultados})

    return "Gracias por tu mensaje, en breve te atiende alguien de nuestro equipo."
