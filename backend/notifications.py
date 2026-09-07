"""Envío de notificaciones por WhatsApp usando Twilio — AHORA POR EMPRESA:
cada empresa puede tener su propia cuenta de Twilio (Account SID, Auth
Token, número de WhatsApp), configurable en Administrar → WhatsApp (o
desde el panel de Superadmin). Si una empresa no configuró la suya,
se usan las variables de entorno globales de respaldo (así no se rompe
nada de lo que ya funcionaba antes de este cambio):

  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM     -- ej. "whatsapp:+14155238886"
  TWILIO_TEMPLATE_SID      -- opcional, ver nota abajo

Si ninguna de las dos (ni la de la empresa ni la global) está
configurada, las funciones simplemente no hacen nada (no rompen la
creación de tickets). Si Twilio devuelve un error, también se ignora
silenciosamente en las notificaciones internas (solo se registra en
consola) — un problema de WhatsApp nunca debe impedir crear o
actualizar un ticket. Las difusiones del CRM sí reportan éxito/error
por destinatario (ver enviar_difusion_individual).

NOTA sobre cómo funciona WhatsApp en la práctica:
- Con el "Sandbox" gratis de Twilio (para pruebas), cada técnico debe
  primero mandarle un mensaje al número del sandbox (algo como "join
  palabra-clave") desde su propio WhatsApp para autorizar que le
  lleguen mensajes. Esa autorización expira cada 72 horas de inactividad.
- Con un número de WhatsApp Business API ya aprobado por Meta, para
  mensajes que tú inicias (como estas notificaciones) casi siempre se
  requiere una "plantilla" pre-aprobada, no texto libre. Si ese es tu
  caso, define una plantilla (TWILIO_TEMPLATE_SID o su equivalente por
  empresa, empieza con "HX...").
"""
import os

import db

_TWILIO_ACCOUNT_SID_GLOBAL = os.getenv("TWILIO_ACCOUNT_SID", "")
_TWILIO_AUTH_TOKEN_GLOBAL = os.getenv("TWILIO_AUTH_TOKEN", "")
_TWILIO_WHATSAPP_FROM_GLOBAL = os.getenv("TWILIO_WHATSAPP_FROM", "")
_TWILIO_TEMPLATE_SID_GLOBAL = os.getenv("TWILIO_TEMPLATE_SID", "")

_clientes_por_empresa = {}  # cache: empresa_id -> twilio.rest.Client, para no reconectar en cada mensaje


def _config_para_empresa(empresa_id):
    """Regresa (account_sid, auth_token, whatsapp_from, template_sid) —
    primero intenta la config propia de la empresa; si no tiene,
    respalda con las variables de entorno globales."""
    propia = db.obtener_config_whatsapp(empresa_id) if empresa_id else None
    if propia and propia.get("account_sid") and propia.get("auth_token") and propia.get("whatsapp_from"):
        return propia["account_sid"], propia["auth_token"], propia["whatsapp_from"], propia.get("template_sid") or ""
    return _TWILIO_ACCOUNT_SID_GLOBAL, _TWILIO_AUTH_TOKEN_GLOBAL, _TWILIO_WHATSAPP_FROM_GLOBAL, _TWILIO_TEMPLATE_SID_GLOBAL


def _cliente_para_empresa(empresa_id, account_sid, auth_token):
    clave = empresa_id or "__global__"
    if clave not in _clientes_por_empresa:
        from twilio.rest import Client
        _clientes_por_empresa[clave] = Client(account_sid, auth_token)
    return _clientes_por_empresa[clave]


def esta_habilitado(empresa_id=None):
    account_sid, auth_token, whatsapp_from, _ = _config_para_empresa(empresa_id)
    return bool(account_sid and auth_token and whatsapp_from)


def _enviar(empresa_id, telefono_whatsapp: str, texto: str, variables_plantilla: dict | None = None):
    if not telefono_whatsapp or not esta_habilitado(empresa_id):
        return
    account_sid, auth_token, whatsapp_from, template_sid = _config_para_empresa(empresa_id)
    destino = telefono_whatsapp if telefono_whatsapp.startswith("whatsapp:") else f"whatsapp:{telefono_whatsapp}"
    try:
        cliente = _cliente_para_empresa(empresa_id, account_sid, auth_token)
        kwargs = dict(from_=whatsapp_from, to=destino)
        if template_sid and variables_plantilla:
            kwargs["content_sid"] = template_sid
            kwargs["content_variables"] = str(variables_plantilla).replace("'", '"')
        else:
            kwargs["body"] = texto
        cliente.messages.create(**kwargs)
        db.registrar_consumo(empresa_id, "whatsapp_notificacion", 1, "mensaje")
    except Exception as e:
        print(f"[whatsapp] Error enviando a {destino}: {e}")


def enviar_difusion_individual(empresa_id, telefono_whatsapp: str, texto: str):
    """Como _enviar, pero SÍ reporta éxito/error — para el registro de
    difusiones del CRM, donde cada destinatario necesita su propio
    estatus (a diferencia de las notificaciones internas, que se
    ignoran silenciosamente si fallan).

    IMPORTANTE: esto manda TEXTO LIBRE, no una plantilla. Con un número
    de WhatsApp Business API ya aprobado por Meta, el texto libre solo
    se puede mandar dentro de una conversación activa de 24h (el
    cliente te escribió primero) — fuera de esa ventana, Meta exige una
    plantilla pre-aprobada con redacción fija, que no admite mensajes
    de difusión con contenido libre como este. Con el Sandbox de
    prueba, solo llega a números que ya se unieron al sandbox."""
    if not esta_habilitado(empresa_id):
        return False, "WhatsApp no está configurado para esta empresa (ni tiene una propia, ni hay una global de respaldo)."
    if not telefono_whatsapp:
        return False, "Este cliente no tiene teléfono registrado."
    account_sid, auth_token, whatsapp_from, _ = _config_para_empresa(empresa_id)
    destino = telefono_whatsapp if telefono_whatsapp.startswith("whatsapp:") else f"whatsapp:{telefono_whatsapp}"
    try:
        cliente = _cliente_para_empresa(empresa_id, account_sid, auth_token)
        cliente.messages.create(from_=whatsapp_from, to=destino, body=texto)
        db.registrar_consumo(empresa_id, "whatsapp_difusion", 1, "mensaje")
        return True, None
    except Exception as e:
        return False, str(e)


def notificar_nuevo_ticket(empresa_id, tecnicos: list, ticket: dict):
    if not esta_habilitado(empresa_id):
        print("[whatsapp] No configurado para esta empresa — se omite la notificación de ticket nuevo.")
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
            _enviar(empresa_id, tec["telefono_whatsapp"], texto, variables)


def notificar_asignacion(empresa_id, tecnico: dict, ticket: dict):
    if not tecnico or not tecnico.get("telefono_whatsapp"):
        return
    texto = (
        f"📌 Te asignaron el ticket {ticket['folio']}\n"
        f"Departamento: {ticket['departamento']}\n"
        f"Prioridad: {ticket['prioridad'].upper()}"
    )
    _enviar(empresa_id, tecnico["telefono_whatsapp"], texto)


def notificar_pedido_listo(empresa_id, usuario: dict, articulo_nombre: str, cantidad: int):
    if not usuario or not usuario.get("telefono_whatsapp"):
        return
    texto = (
        f"✅ Ya está listo tu pedido: {articulo_nombre} (x{cantidad}).\n"
        f"Puedes pasar por él cuando gustes."
    )
    _enviar(empresa_id, usuario["telefono_whatsapp"], texto)


def notificar_ciclo_pendiente_autorizacion(empresa_id, usuarios_master: list, ciclo: dict, total: float):
    if not esta_habilitado(empresa_id):
        print("[whatsapp] No configurado para esta empresa — se omite la notificación de autorización de compra.")
        return
    texto = (
        f"🧾 El ciclo de compra \"{ciclo['nombre']}\" ya se cerró y está listo para autorizar.\n"
        f"Total a pagar: ${total:,.2f}"
    )
    for m in usuarios_master:
        if m.get("telefono_whatsapp"):
            _enviar(empresa_id, m["telefono_whatsapp"], texto)


def notificar_incidencia_rh_resuelta(empresa_id, usuario: dict, incidencia: dict):
    if not usuario or not usuario.get("telefono_whatsapp"):
        return
    if incidencia["estado"] == "aprobada":
        texto = f"✅ Tu incidencia de RH ({incidencia['tipo']}) fue APROBADA."
    else:
        texto = f"❌ Tu incidencia de RH ({incidencia['tipo']}) fue RECHAZADA."
    if incidencia.get("respuesta_admin"):
        texto += f"\nComentario: {incidencia['respuesta_admin']}"
    _enviar(empresa_id, usuario["telefono_whatsapp"], texto)
