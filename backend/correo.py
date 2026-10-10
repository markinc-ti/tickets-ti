"""
Envío de correos por SMTP (para avisos a estudiantes, por ejemplo que su
vigencia está por vencer).

Variables de entorno (Render → Environment):
  SMTP_HOST      ej. smtp.gmail.com
  SMTP_PORT      587 (STARTTLS) o 465 (SSL). Default 587.
  SMTP_USER      la cuenta, ej. laboratorio@markinc.com.mx
  SMTP_PASSWORD  con Gmail/Google Workspace: una "contraseña de aplicación"
  SMTP_FROM      opcional, ej. "Markinc Lab <laboratorio@markinc.com.mx>"

Si no están, configurado() es False y enviar() no hace nada (nunca truena
el flujo que lo llama).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr


def configurado():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def enviar(destinatario, asunto, texto):
    """True si se mandó; False si no hay SMTP o falló (se registra en consola)."""
    if not configurado() or not destinatario or "@" not in destinatario:
        return False
    host = os.getenv("SMTP_HOST")
    puerto = int(os.getenv("SMTP_PORT") or 587)
    usuario = os.getenv("SMTP_USER")
    remitente = os.getenv("SMTP_FROM") or usuario
    nombre, direccion = parseaddr(remitente)
    msg = EmailMessage()
    msg["From"] = formataddr((nombre, direccion or usuario)) if nombre else (direccion or usuario)
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(texto)
    try:
        contexto = ssl.create_default_context()
        if puerto == 465:
            with smtplib.SMTP_SSL(host, puerto, context=contexto, timeout=20) as s:
                s.login(usuario, os.getenv("SMTP_PASSWORD"))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, puerto, timeout=20) as s:
                s.starttls(context=contexto)
                s.login(usuario, os.getenv("SMTP_PASSWORD"))
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"[correo] no se pudo mandar a {destinatario}: {e}")
        return False
