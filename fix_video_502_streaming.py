# -*- coding: utf-8 -*-
"""
Turnos / Videos: arregla el error "servidor (502)" que sigue saliendo
al subir un video AUNQUE pese menos de 500 MB.

Que estaba pasando: el arreglo anterior (fix_video_502_500mb.py) ya
evitaba el problema en archivos de MAS de 500 MB, pero para cualquier
archivo dentro del limite (por ejemplo uno de 300-450 MB), el servidor
segui­a cargando el video COMPLETO en su memoria (RAM) antes de
mandarlo a Cloudflare R2. El plan gratis de Render solo tiene 512 MB
de RAM en total para toda la aplicacion -- entonces un video de varios
cientos de MB podia hacer que el servidor se quedara sin memoria y el
proceso se cayera a la mitad de la subida, sin alcanzar a mandar
ningun mensaje de error propio. Eso se ve, del lado del navegador,
exactamente como lo que reportaste: "PROCESANDO..." y despues un
"Error del servidor (502)" en seco, sin ningun detalle -- porque ese
502 no lo genera la aplicacion (que si manda un mensaje claro), sino
el servidor de Render dandose cuenta de que el proceso se cayo.

Que se arregla:
  1. El servidor YA NO carga el video completo a su memoria. En vez de
     eso, mide su tamano y lo transmite hacia Cloudflare R2 en pedazos
     chicos, usando el archivo temporal que ya queda guardado en disco
     mientras se sube (esto es normal y automatico, no algo nuevo).
     Esto baja muchisimo el uso de memoria del servidor sin importar
     que tan grande sea el video (siempre que este dentro del limite
     de 500 MB).
  2. Si de todos modos algo sale mal al subir a Cloudflare R2 (por
     ejemplo un problema de red o de credenciales), ahora queda un
     registro con el motivo exacto en los logs de Render -- para poder
     ver la causa real en vez de solo un "502" si vuelve a pasar.

Que toca:
  - backend/r2.py -- la funcion que sube el video a Cloudflare R2.
  - backend/app.py -- el endpoint de subir video.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_video_502_streaming.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["backend/r2.py"] = [
    [
        "def subir_video(empresa_id, nombre_archivo, contenido_bytes, content_type=None):\n    \"\"\"Sube el archivo bajo una carpeta por empresa (empresa_{id}/...) con\n    un nombre único, para que dos archivos con el mismo nombre no se\n    pisen entre sí ni entre empresas. Regresa (key, url_publica).\"\"\"\n    nombre_limpio = (nombre_archivo or \"video.mp4\").replace(\"/\", \"_\").replace(\"\\\\\", \"_\")\n    key = f\"empresa_{empresa_id}/{uuid.uuid4().hex}_{nombre_limpio}\"\n    cliente = _cliente()\n    cliente.put_object(\n        Bucket=R2_BUCKET_NAME, Key=key, Body=contenido_bytes,\n        ContentType=content_type or \"video/mp4\",\n    )\n    url = f\"{R2_PUBLIC_URL_BASE}/{key}\"\n    return key, url",
        "def subir_video(empresa_id, nombre_archivo, archivo_file, content_type=None):\n    \"\"\"Sube el archivo bajo una carpeta por empresa (empresa_{id}/...) con\n    un nombre único, para que dos archivos con el mismo nombre no se\n    pisen entre sí ni entre empresas. Regresa (key, url_publica).\n\n    `archivo_file` es un objeto tipo archivo (no los bytes ya leídos a\n    memoria) -- con upload_fileobj(), boto3 transmite el archivo hacia\n    Cloudflare R2 en pedazos, en vez de necesitar tenerlo completo junto\n    en la memoria del servidor antes de empezar a subirlo. Esto es clave\n    en archivos grandes: el plan gratis de Render solo tiene 512 MB de\n    RAM, y cargar un video de 300-500 MB completo en memoria (encima de\n    lo que ya usa la aplicación) podía tronar el proceso sin ningún\n    mensaje de error claro -- se veía como un \"502\" genérico del\n    servidor.\n    \"\"\"\n    nombre_limpio = (nombre_archivo or \"video.mp4\").replace(\"/\", \"_\").replace(\"\\\\\", \"_\")\n    key = f\"empresa_{empresa_id}/{uuid.uuid4().hex}_{nombre_limpio}\"\n    cliente = _cliente()\n    cliente.upload_fileobj(\n        archivo_file, R2_BUCKET_NAME, key,\n        ExtraArgs={\"ContentType\": content_type or \"video/mp4\"},\n    )\n    url = f\"{R2_PUBLIC_URL_BASE}/{key}\"\n    return key, url",
    ],
]

ARCHIVOS["backend/app.py"] = [
    [
        "import secrets\nimport urllib.parse",
        "import secrets\nimport sys\nimport urllib.parse",
    ],
    [
        "    content_length_header = request.headers.get(\"content-length\")\n    if content_length_header and content_length_header.isdigit():\n        if int(content_length_header) > MAX_VIDEO_BYTES_UNA_SUBIDA + (5 * 1024 * 1024):\n            raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    contenido = await archivo.read()\n    tamano = len(contenido)\n    if tamano == 0:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"])\n    limite_bytes = (empresa.get(\"limite_almacenamiento_videos_mb\") or 2048) * 1024 * 1024\n    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario[\"empresa_id\"])\n    if usado_bytes + tamano > limite_bytes:\n        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)\n        raise HTTPException(\n            status_code=400,\n            detail=f\"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.\",\n        )\n    try:\n        # run_in_threadpool: la subida a R2 es una llamada bloqueante\n        # (boto3), y sin esto se congelaría TODA la aplicación (para\n        # todos los usuarios) mientras dura la subida de un video grande.\n        key, url = await run_in_threadpool(r2.subir_video, usuario[\"empresa_id\"], archivo.filename, contenido, archivo.content_type)\n    except Exception as e:\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir el video a Cloudflare R2: {e}\")",
        "    content_length_header = request.headers.get(\"content-length\")\n    if content_length_header and content_length_header.isdigit():\n        if int(content_length_header) > MAX_VIDEO_BYTES_UNA_SUBIDA + (5 * 1024 * 1024):\n            raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    # IMPORTANTE: ya NO se carga el archivo completo a la memoria del\n    # servidor con \"archivo.read()\". FastAPI ya guarda el archivo que se\n    # está subiendo en un archivo temporal en disco -- aquí solo se mide\n    # su tamaño (moviendo el cursor al final y regresándolo al inicio) y\n    # más abajo se manda ese mismo archivo temporal directo a Cloudflare\n    # R2, en pedazos. Antes, un video de 300-500 MB se cargaba COMPLETO\n    # en memoria (en un servidor con solo 512 MB de RAM en el plan\n    # gratis de Render) y eso podía tronar el proceso sin ningún mensaje\n    # de error claro -- se veía como un \"502\" genérico del servidor,\n    # incluso en archivos que sí pesaban menos de 500 MB.\n    archivo.file.seek(0, 2)\n    tamano = archivo.file.tell()\n    archivo.file.seek(0)\n    if tamano == 0:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"])\n    limite_bytes = (empresa.get(\"limite_almacenamiento_videos_mb\") or 2048) * 1024 * 1024\n    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario[\"empresa_id\"])\n    if usado_bytes + tamano > limite_bytes:\n        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)\n        raise HTTPException(\n            status_code=400,\n            detail=f\"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.\",\n        )\n    try:\n        # run_in_threadpool: la subida a R2 es una llamada bloqueante\n        # (boto3), y sin esto se congelaría TODA la aplicación (para\n        # todos los usuarios) mientras dura la subida de un video\n        # grande. Se manda el archivo (archivo.file) en vez de los\n        # bytes ya leídos, para que boto3 lo transmita en pedazos sin\n        # necesitar tenerlo todo junto en memoria.\n        key, url = await run_in_threadpool(r2.subir_video, usuario[\"empresa_id\"], archivo.filename, archivo.file, archivo.content_type)\n    except Exception as e:\n        # Se deja un registro en los logs de Render con el error real de\n        # R2 (por ejemplo credenciales, red, o el nombre del bucket) --\n        # así, si vuelve a pasar, se puede ver la causa exacta en vez de\n        # solo un \"502\" genérico.\n        print(f\"[videos] error subiendo a Cloudflare R2 (empresa {usuario['empresa_id']}, archivo {archivo.filename!r}, {tamano} bytes): {e}\", file=sys.stderr)\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir el video a Cloudflare R2: {e}\")",
    ],
]



def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in ARCHIVOS[ruta]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
            hubo_error = True
    escribir(ruta, contenido)
    print("[" + ruta + "] " + str(cambios) + "/" + str(len(ARCHIVOS[ruta])) + " cambio(s) aplicado(s).")
    return not hubo_error


def main():
    ok = True
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Videos: ya no carga el archivo completo en memoria -- lo transmite en pedazos a R2, arregla 502 en archivos dentro del limite"')
    print("   git push")


if __name__ == "__main__":
    main()
