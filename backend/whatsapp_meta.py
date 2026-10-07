"""WhatsApp Business — API oficial de Meta (Cloud API), directo, sin Twilio.

Se usa para los mensajes AUTOMÁTICOS a clientes desde ventas (app de iPad
"Markinc Ventas" y el Checador de precio):
  - bienvenida al dar de alta un cliente
  - bienvenida + PDF de la cotización al crearla

Por reglas de Meta, un mensaje que inicia la EMPRESA (el cliente no nos
escribió en las últimas 24 h) solo puede ir como PLANTILLA aprobada en
WhatsApp Manager. Por eso aquí todo se manda como plantilla.

Variables de entorno (en Render):
  WHATSAPP_META_TOKEN               token permanente del "usuario del sistema"
  WHATSAPP_META_PHONE_NUMBER_ID     ID del número (no es el teléfono, es el ID que da Meta)
  WHATSAPP_META_PLANTILLA_BIENVENIDA  nombre de la plantilla (default: bienvenida_cliente)
  WHATSAPP_META_PLANTILLA_COTIZACION  nombre de la plantilla (default: cotizacion_cliente)
  WHATSAPP_META_IDIOMA              código de idioma de las plantillas (default: es_MX)
  WHATSAPP_META_VERIFY_TOKEN        texto que tú inventas, para validar el webhook
  WHATSAPP_META_APP_SECRET          opcional: "Clave secreta de la app" para validar
                                    que los avisos del webhook sí vienen de Meta

Plantillas (crearlas así en WhatsApp Manager, idioma Español (MEX)):
  bienvenida_cliente  (Marketing)
    Cuerpo: Hola {{1}}, gracias por tu interés en {{2}}. Soy {{3}} y quedo a
            tus órdenes. Por este medio te enviaremos tus cotizaciones y la
            información de tus equipos.
  cotizacion_cliente  (Utilidad) — Encabezado: Documento
    Cuerpo: Hola {{1}}, gracias por tu interés en {{2}}. Te compartimos tu
            cotización {{3}} por un total de {{4}} (IVA incluido). Cualquier
            duda, responde a este mensaje; te atiende {{5}}.
"""
import hashlib
import hmac
import os
import re

import requests

GRAPH_URL = os.getenv("WHATSAPP_META_GRAPH_URL", "https://graph.facebook.com/v23.0").rstrip("/")
TIMEOUT = 25


class ErrorWhatsApp(Exception):
    """Error con mensaje entendible para el vendedor."""


def _cfg():
    return {
        "token": os.getenv("WHATSAPP_META_TOKEN", "").strip(),
        "phone_id": os.getenv("WHATSAPP_META_PHONE_NUMBER_ID", "").strip(),
        "pl_bienvenida": os.getenv("WHATSAPP_META_PLANTILLA_BIENVENIDA", "").strip() or "bienvenida_cliente",
        "pl_cotizacion": os.getenv("WHATSAPP_META_PLANTILLA_COTIZACION", "").strip() or "cotizacion_cliente",
        "idioma": os.getenv("WHATSAPP_META_IDIOMA", "").strip() or "es_MX",
    }


def configurado() -> bool:
    c = _cfg()
    return bool(c["token"] and c["phone_id"])


def normalizar_telefono(telefono) -> str | None:
    """Deja el número como lo pide Meta: solo dígitos con lada de país.
    10 dígitos → México (52). Quita el '1' viejo de celulares mexicanos
    (521XXXXXXXXXX → 52XXXXXXXXXX)."""
    d = re.sub(r"\D", "", str(telefono or ""))
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 10:
        return "52" + d
    if len(d) == 13 and d.startswith("521"):
        return "52" + d[3:]
    if len(d) == 12 and d.startswith("52"):
        return d
    if 11 <= len(d) <= 15 and not d.startswith("52"):
        return d
    return None


def ultimos_10(telefono) -> str:
    d = re.sub(r"\D", "", str(telefono or ""))
    return d[-10:]


def _texto_param(valor, maximo=200) -> str:
    """Meta rechaza parámetros con saltos de línea, tabs o 4+ espacios seguidos."""
    t = re.sub(r"[\r\n\t]+", " ", str(valor if valor is not None else "")).strip()
    t = re.sub(r" {2,}", " ", t)
    return (t or "-")[:maximo]


_ERRORES_CONOCIDOS = {
    131026: "Ese número no tiene WhatsApp o no puede recibir mensajes.",
    131030: "Ese número no está en la lista de prueba de Meta (en modo prueba solo llega a números agregados).",
    132000: "La plantilla no tiene los datos que espera — revisa que tenga las variables {{1}}…{{n}} correctas.",
    132001: "La plantilla no existe o todavía no está aprobada en ese idioma.",
    132005: "Algún dato de la plantilla es demasiado largo.",
    132012: "Los datos no coinciden con el formato de la plantilla (por ejemplo, falta el encabezado de Documento).",
    131047: "Ya pasaron más de 24 h desde que el cliente escribió — solo se puede mandar con plantilla.",
    131056: "Se mandaron demasiados mensajes a ese número en poco tiempo; intenta en unos minutos.",
    130429: "Se alcanzó el límite de envíos de Meta; intenta en unos minutos.",
    131031: "La cuenta de WhatsApp Business está bloqueada o restringida por Meta.",
    190: "El token de Meta venció o es inválido — genera uno permanente del usuario del sistema.",
    100: "Meta rechazó la solicitud (revisa el ID del número y la configuración).",
}


def _error_de_respuesta(resp) -> ErrorWhatsApp:
    try:
        err = (resp.json() or {}).get("error") or {}
    except Exception:
        err = {}
    codigo = err.get("code")
    detalle = ((err.get("error_data") or {}).get("details") or err.get("message") or resp.text or "")[:300]
    amigable = _ERRORES_CONOCIDOS.get(codigo)
    if amigable:
        return ErrorWhatsApp(f"{amigable} (Meta {codigo})")
    return ErrorWhatsApp(f"Meta respondió {resp.status_code}: {detalle}")


def _headers():
    return {"Authorization": f"Bearer {_cfg()['token']}"}


def subir_pdf(pdf_bytes: bytes, nombre_archivo: str) -> str:
    """Sube el PDF a Meta y regresa el media_id (dura 30 días en Meta)."""
    c = _cfg()
    try:
        resp = requests.post(
            f"{GRAPH_URL}/{c['phone_id']}/media",
            headers=_headers(),
            data={"messaging_product": "whatsapp", "type": "application/pdf"},
            files={"file": (nombre_archivo, pdf_bytes, "application/pdf")},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise ErrorWhatsApp(f"No se pudo conectar con WhatsApp (Meta): {e}")
    if resp.status_code >= 400:
        raise _error_de_respuesta(resp)
    media_id = (resp.json() or {}).get("id")
    if not media_id:
        raise ErrorWhatsApp("Meta no regresó el ID del PDF subido.")
    return media_id


def enviar_plantilla(telefono: str, plantilla: str, parametros_cuerpo: list, documento: dict | None = None) -> str:
    """Manda una plantilla. Regresa el wamid (ID del mensaje en Meta)."""
    if not configurado():
        raise ErrorWhatsApp("WhatsApp Business (Meta) no está configurado en el servidor.")
    numero = normalizar_telefono(telefono)
    if not numero:
        raise ErrorWhatsApp("El teléfono no es válido — captura los 10 dígitos.")
    c = _cfg()
    componentes = []
    if documento:
        componentes.append({"type": "header", "parameters": [{"type": "document", "document": documento}]})
    if parametros_cuerpo:
        componentes.append({"type": "body", "parameters": [{"type": "text", "text": _texto_param(p)} for p in parametros_cuerpo]})
    cuerpo = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {"name": plantilla, "language": {"code": c["idioma"]}, "components": componentes},
    }
    try:
        resp = requests.post(f"{GRAPH_URL}/{c['phone_id']}/messages", headers=_headers(), json=cuerpo, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ErrorWhatsApp(f"No se pudo conectar con WhatsApp (Meta): {e}")
    if resp.status_code >= 400:
        raise _error_de_respuesta(resp)
    mensajes = (resp.json() or {}).get("messages") or []
    return (mensajes[0] or {}).get("id") if mensajes else None


def enviar_bienvenida(telefono, nombre_cliente, nombre_empresa, nombre_vendedor) -> str:
    return enviar_plantilla(telefono, _cfg()["pl_bienvenida"], [nombre_cliente, nombre_empresa, nombre_vendedor])


def enviar_cotizacion(telefono, nombre_cliente, nombre_empresa, folio, total_texto, nombre_vendedor,
                      pdf_bytes: bytes, nombre_archivo: str) -> str:
    media_id = subir_pdf(pdf_bytes, nombre_archivo)
    return enviar_plantilla(
        telefono, _cfg()["pl_cotizacion"],
        [nombre_cliente, nombre_empresa, folio, total_texto, nombre_vendedor],
        documento={"id": media_id, "filename": nombre_archivo},
    )


# ---- Webhook ----

def verificar_suscripcion(modo, token, reto):
    """GET del webhook: Meta pregunta con hub.verify_token; si coincide, se
    regresa hub.challenge tal cual."""
    esperado = os.getenv("WHATSAPP_META_VERIFY_TOKEN", "").strip()
    if modo == "subscribe" and esperado and token == esperado:
        return reto
    return None


def firma_valida(cuerpo: bytes, firma_header: str | None) -> bool:
    secreto = os.getenv("WHATSAPP_META_APP_SECRET", "").strip()
    if not secreto:
        return True  # sin secreto configurado no se valida (igual se aceptan los avisos)
    if not firma_header or not firma_header.startswith("sha256="):
        return False
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma_header.split("=", 1)[1])


def extraer_eventos(payload: dict):
    """Del aviso de Meta saca (estatus, mensajes entrantes).
    estatus: [{wamid, estatus, error}]   mensajes: [{telefono, nombre, texto}]"""
    estatus, mensajes = [], []
    for entry in (payload or {}).get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for s in value.get("statuses") or []:
                errores = s.get("errors") or []
                error = None
                if errores:
                    e = errores[0]
                    error = _ERRORES_CONOCIDOS.get(e.get("code")) or ((e.get("error_data") or {}).get("details") or e.get("title") or e.get("message"))
                estatus.append({"wamid": s.get("id"), "estatus": s.get("status"), "error": error})
            nombres = {c.get("wa_id"): ((c.get("profile") or {}).get("name")) for c in value.get("contacts") or []}
            for m in value.get("messages") or []:
                tipo = m.get("type")
                if tipo == "text":
                    texto = (m.get("text") or {}).get("body") or ""
                elif tipo == "button":
                    texto = (m.get("button") or {}).get("text") or ""
                else:
                    texto = f"[{tipo}]"
                mensajes.append({"telefono": m.get("from"), "nombre": nombres.get(m.get("from")), "texto": texto})
    return estatus, mensajes
