# -*- coding: utf-8 -*-
"""
Notificaciones push como WhatsApp en Android: se mandan al canal
"avisos_markinc" (importancia alta: salen arriba en pantalla, con sonido y
vibración, aun con la app cerrada). Las apps crean ese canal (AvisosApp.kt,
Mark·Inc 1.0.6+8 y Lab 1.0.6+14).
REQUIERE haber corrido antes fix_lab_devolucion_tickets_sistemas.py.
Toca: backend/push_notifications.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/push_notifications.py": [
  [
   "import os\n\n_app = None\n\n\ndef configurado():\n",
   "import os\n\n_app = None\n# Canal de importancia alta que crean las apps (AvisosApp.kt): el aviso sale\n# arriba en pantalla con sonido, aun con la app cerrada.\nCANAL_ANDROID = \"avisos_markinc\"\n\n\ndef configurado():\n"
  ],
  [
   "            token=token,\n            notification=messaging.Notification(title=titulo, body=cuerpo),\n            data={k: str(v) for k, v in (datos or {}).items() if v is not None},\n            android=messaging.AndroidConfig(priority=\"high\", notification=messaging.AndroidNotification(sound=\"default\")),\n            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound=\"default\"))),\n        ), app=_iniciar())\n        return \"ok\", \"\"\n",
   "            token=token,\n            notification=messaging.Notification(title=titulo, body=cuerpo),\n            data={k: str(v) for k, v in (datos or {}).items() if v is not None},\n            android=messaging.AndroidConfig(priority=\"high\", notification=messaging.AndroidNotification(\n                sound=\"default\", channel_id=CANAL_ANDROID, priority=\"high\", default_vibrate_timings=True)),\n            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound=\"default\"))),\n        ), app=_iniciar())\n        return \"ok\", \"\"\n"
  ],
  [
   "            notification=messaging.Notification(title=titulo, body=cuerpo),\n            data={k: str(v) for k, v in (datos or {}).items() if v is not None},\n            android=messaging.AndroidConfig(priority=\"high\",\n                                            notification=messaging.AndroidNotification(sound=\"default\")),\n            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound=\"default\"))),\n        )\n        messaging.send(mensaje, app=_iniciar())\n",
   "            notification=messaging.Notification(title=titulo, body=cuerpo),\n            data={k: str(v) for k, v in (datos or {}).items() if v is not None},\n            android=messaging.AndroidConfig(priority=\"high\",\n                                            notification=messaging.AndroidNotification(\n                sound=\"default\", channel_id=CANAL_ANDROID, priority=\"high\", default_vibrate_timings=True)),\n            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound=\"default\"))),\n        )\n        messaging.send(mensaje, app=_iniciar())\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "devolucion_motivo" not in f.read():
            print("Primero corre fix_lab_devolucion_tickets_sistemas.py (y los anteriores), y luego este.")
            sys.exit(1)
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    bin_cambios = {}
    for ruta, b64 in NUEVOS_BIN.items():
        datos = base64.b64decode(b64)
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                if f.read() == datos:
                    continue
        bin_cambios[ruta] = datos
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        # Windows: el archivo puede tener saltos CRLF, LF o una mezcla.
        # Se trabaja todo en LF y al guardar se deja como estaba (CRLF si tenia).
        crlf = "\r\n" in original
        texto = original.replace("\r\n", "\n")
        inicial = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue  # ya aplicado
            n = texto.count(viejo)
            if n != 1:
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
                continue
            texto = texto.replace(viejo, nuevo, 1)
        if texto != inicial:
            cambios[ruta] = texto.replace("\n", "\r\n") if crlf else texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, datos in bin_cambios.items():
        with open(ruta, "wb") as f:
            f.write(datos)
        print("Actualizado:", ruta)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios and not bin_cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
