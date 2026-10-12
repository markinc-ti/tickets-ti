"""
Notificaciones push a las apps Mark·Inc y Mark·Inc Lab (Firebase Cloud
Messaging, Android e iPhone). Para avisar a usuarios usa avisos.avisar(). Requiere la variable FIREBASE_SERVICE_ACCOUNT_JSON en Render con
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
    """True si Firebase aceptó el mensaje; "invalido" si ese token ya no
    sirve (app desinstalada o sesión de otro proyecto) para borrarlo."""
    if not configurado() or not token:
        return False
    try:
        from firebase_admin import messaging
        mensaje = messaging.Message(
            token=token,
            notification=messaging.Notification(title=titulo, body=cuerpo),
            data={k: str(v) for k, v in (datos or {}).items() if v is not None},
            android=messaging.AndroidConfig(priority="high",
                                            notification=messaging.AndroidNotification(sound="default")),
            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))),
        )
        messaging.send(mensaje, app=_iniciar())
        return True
    except Exception as e:
        nombre = type(e).__name__
        if nombre in ("UnregisteredError", "SenderIdMismatchError") or "registration-token-not-registered" in str(e) \
                or "not a valid FCM registration token" in str(e):
            return "invalido"
        print(f"[push] no se pudo mandar: {e}")
        return False
