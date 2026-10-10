"""
Notificaciones push a la app Android de estudiantes (Firebase Cloud
Messaging). Requiere la variable FIREBASE_SERVICE_ACCOUNT_JSON en Render con
el contenido completo de la clave de cuenta de servicio (Firebase Console →
Configuración del proyecto → Cuentas de servicio → Generar nueva clave).
Si falta, configurado() es False y enviar() no hace nada.
"""
import json
import os

_app = None


def configurado():
    return bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))


def _iniciar():
    global _app
    if _app is None:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")))
        _app = firebase_admin.initialize_app(cred, name="markinc-lab")
    return _app


def enviar(token, titulo, cuerpo, datos=None):
    """True si Firebase aceptó el mensaje."""
    if not configurado() or not token:
        return False
    try:
        from firebase_admin import messaging
        mensaje = messaging.Message(
            token=token,
            notification=messaging.Notification(title=titulo, body=cuerpo),
            data={k: str(v) for k, v in (datos or {}).items()},
        )
        messaging.send(mensaje, app=_iniciar())
        return True
    except Exception as e:
        print(f"[push] no se pudo mandar: {e}")
        return False
