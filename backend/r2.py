"""Subida de videos a Cloudflare R2 (almacenamiento de archivos, sin costo
de entrega/egress) -- usado por Turnos (video en loop de la pantalla) y,
más adelante, por Capacitación.

Necesita estas variables de entorno configuradas en Render (Environment):
  R2_ACCOUNT_ID        -- el "Account ID" de tu cuenta de Cloudflare
  R2_ACCESS_KEY_ID      -- del token de API de R2 (Manage R2 API Tokens)
  R2_SECRET_ACCESS_KEY  -- idem
  R2_BUCKET_NAME         -- el nombre del bucket, ej. "tickets-ti-videos"
  R2_PUBLIC_URL_BASE     -- el dominio público del bucket, ej.
                            "https://pub-xxxxxxxx.r2.dev" (SIN "/" al final)

Si falta alguna, `configurado()` regresa False y el endpoint de subida
avisa con un mensaje claro en vez de tronar feo.
"""
import os
import uuid

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_PUBLIC_URL_BASE = (os.environ.get("R2_PUBLIC_URL_BASE") or "").rstrip("/")


def configurado():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL_BASE)


def _cliente():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def subir_video(empresa_id, nombre_archivo, contenido_bytes, content_type=None):
    """Sube el archivo bajo una carpeta por empresa (empresa_{id}/...) con
    un nombre único, para que dos archivos con el mismo nombre no se
    pisen entre sí ni entre empresas. Regresa (key, url_publica)."""
    nombre_limpio = (nombre_archivo or "video.mp4").replace("/", "_").replace("\\", "_")
    key = f"empresa_{empresa_id}/{uuid.uuid4().hex}_{nombre_limpio}"
    cliente = _cliente()
    cliente.put_object(
        Bucket=R2_BUCKET_NAME, Key=key, Body=contenido_bytes,
        ContentType=content_type or "video/mp4",
    )
    url = f"{R2_PUBLIC_URL_BASE}/{key}"
    return key, url


def eliminar_video(key):
    cliente = _cliente()
    cliente.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
