"""
Avisos (notificaciones push) a las apps Mark·Inc y Mark·Inc Lab.

    avisos.avisar([usuario_id, ...], "Título", "Texto", modulo="tickets", ref=123)

- Se manda en segundo plano (un hilo): nunca retrasa ni tumba la petición.
- Llega a TODOS los celulares/tablets donde ese usuario tenga sesión abierta
  (tabla dispositivos_push + el token viejo users.fcm_token de la app Lab).
- `excluir`: ids que no deben recibirlo (normalmente quien hizo la acción).
- `modulo` / `ref` viajan en los datos del aviso para que la app abra la
  pantalla correcta al tocarlo (tickets, proyectos, rh, capacitacion,
  compras, laboratorio...).
- Si Firebase dice que un token ya no sirve, se borra.
- Sin FIREBASE_SERVICE_ACCOUNT_JSON en Render no hace nada.
"""
import json
import os
import threading

import db
import push_notifications

# Para pruebas: si es una lista, en vez de mandar a Firebase se agregan aquí
# los avisos (usuario_ids, titulo, cuerpo, datos).
REGISTRO_PRUEBAS = None


def _ids(usuario_ids, excluir):
    fuera = {int(i) for i in (excluir or []) if i}
    ids = []
    for i in usuario_ids or []:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i and i not in fuera and i not in ids:
            ids.append(i)
    return ids


def avisar(usuario_ids, titulo, cuerpo, modulo=None, ref=None, excluir=None, extra=None):
    ids = _ids(usuario_ids, excluir)
    if not ids:
        return
    datos = {"modulo": modulo or "", "ref": "" if ref is None else str(ref)}
    datos.update({k: str(v) for k, v in (extra or {}).items() if v is not None})
    titulo = (titulo or "")[:120]
    cuerpo = (cuerpo or "")[:400]
    if REGISTRO_PRUEBAS is not None:
        REGISTRO_PRUEBAS.append((ids, titulo, cuerpo, datos))
        return
    if os.getenv("AVISOS_REGISTRO_ARCHIVO"):  # solo pruebas locales
        with open(os.getenv("AVISOS_REGISTRO_ARCHIVO"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ids": ids, "titulo": titulo, "cuerpo": cuerpo, "datos": datos}, ensure_ascii=False) + "\n")
        return
    if not push_notifications.configurado():
        return
    threading.Thread(target=_mandar, args=(ids, titulo, cuerpo, datos), daemon=True).start()


def _mandar(ids, titulo, cuerpo, datos):
    try:
        for token in db.tokens_push_de_usuarios(ids):
            if push_notifications.enviar(token, titulo, cuerpo, datos) == "invalido":
                db.quitar_token_push(token)
    except Exception as e:  # nunca debe tumbar nada
        print(f"[avisos] {e}")


def avisar_seguro(*args, **kwargs):
    """Igual que avisar(), pero si algo falla al armar el aviso (un dato que
    no venía, etc.) se ignora: un aviso nunca debe romper la acción."""
    try:
        avisar(*args, **kwargs)
    except Exception as e:
        print(f"[avisos] no se armó el aviso: {e}")
