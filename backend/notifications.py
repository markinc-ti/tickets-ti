"""
Envío de notificaciones por WhatsApp usando Twilio.

Variables de entorno necesarias:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM     -- ej. "whatsapp:+14155238886" (tu número de Twilio)
  TWILIO_TEMPLATE_SID      -- opcional, ver nota abajo

Si no están configuradas, las funciones simplemente no hacen nada (no
rompen la creación de tickets). Si Twilio devuelve un error, también
se ignora silenciosamente (solo se registra en consola) — un problema
de WhatsApp nunca debe impedir crear o actualizar un ticket.

NOTA sobre cómo funciona WhatsApp en la práctica:
- Con el "Sandbox" gratis de Twilio (para pruebas), cada técnico debe
  primero mandarle un mensaje al número del sandbox (algo como "join
  palabra-clave") desde su propio WhatsApp para autorizar que le
  lleguen mensajes. Esa autorización expira cada 72 horas de inactividad.
- Con un número de WhatsApp Business API ya aprobado por Meta, para
  mensajes que tú inicias (como estas notificaciones) casi siempre se
  requiere una "plantilla" pre-aprobada, no texto libre. Si ese es tu
  caso, define TWILIO_TEMPLATE_SID (empieza con "HX...").
"""
import os

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
TWILIO_TEMPLATE_SID = os.getenv("TWILIO_TEMPLATE_SID", "")

_habilitado = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)

if _habilitado:
    from twilio.rest import Client
    _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    _client = None


def _enviar(telefono_whatsapp: str, texto: str, variables_plantilla: dict | None = None):
    if not _client or not telefono_whatsapp:
        return
    destino = telefono_whatsapp if telefono_whatsapp.startswith("whatsapp:") else f"whatsapp:{telefono_whatsapp}"
    try:
        kwargs = dict(from_=TWILIO_WHATSAPP_FROM, to=destino)
        if TWILIO_TEMPLATE_SID and variables_plantilla:
            kwargs["content_sid"] = TWILIO_TEMPLATE_SID
            kwargs["content_variables"] = str(variables_plantilla).replace("'", '"')
        else:
            kwargs["body"] = texto
        _client.messages.create(**kwargs)
    except Exception as e:
        print(f"[whatsapp] Error enviando a {destino}: {e}")


def notificar_nuevo_ticket(tecnicos: list, ticket: dict):
    if not _habilitado:
        print("[whatsapp] Twilio no configurado — se omite la notificación de ticket nuevo.")
        return
    texto = (
        f"🎫 Nuevo ticket {ticket['folio']}\n"
        f"Departamento: {ticket['departamento']}\n"
        f"Prioridad: {ticket['prioridad'].upper()}\n"
        f"Solicita: {ticket.get('solicitante_nombre', '')}\n"
        f"Detalle: {ticket['descripcion'][:200]}"
    )
    variables = {"1": ticket["folio"], "2": ticket["departamento"], "3": ticket["prioridad"], "4": ticket.get("solicitante_nombre", "")}
    for tec in tecnicos:
        if tec.get("telefono_whatsapp"):
            _enviar(tec["telefono_whatsapp"], texto, variables)


def notificar_asignacion(tecnico: dict, ticket: dict):
    if not _habilitado or not tecnico or not tecnico.get("telefono_whatsapp"):
        return
    texto = (
        f"📌 Te asignaron el ticket {ticket['folio']}\n"
        f"Departamento: {ticket['departamento']}\n"
        f"Prioridad: {ticket['prioridad'].upper()}"
    )
    _enviar(tecnico["telefono_whatsapp"], texto)


def notificar_pedido_listo(usuario: dict, articulo_nombre: str, cantidad: int):
    if not _habilitado or not usuario or not usuario.get("telefono_whatsapp"):
        return
    texto = (
        f"✅ Ya está listo tu pedido: {articulo_nombre} (x{cantidad}).\n"
        f"Puedes pasar por él cuando gustes."
    )
    _enviar(usuario["telefono_whatsapp"], texto)


def notificar_ciclo_pendiente_autorizacion(usuarios_master: list, ciclo: dict, total: float):
    if not _habilitado:
        print("[whatsapp] Twilio no configurado — se omite la notificación de autorización de compra.")
        return
    texto = (
        f"🧾 El ciclo de compra \"{ciclo['nombre']}\" ya se cerró y está listo para autorizar.\n"
        f"Total a pagar: ${total:,.2f}"
    )
    for m in usuarios_master:
        if m.get("telefono_whatsapp"):
            _enviar(m["telefono_whatsapp"], texto)
