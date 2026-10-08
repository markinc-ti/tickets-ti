# -*- coding: utf-8 -*-
"""
Turnos / Videos: arregla el error "servidor (502)" que salia al subir
un video de mas de 500 MB (y de paso deja subidas grandes mas rapidas
y estables en general).

Que estaba pasando: aunque ya existia el limite de 500 MB, el servidor
primero CARGABA TODO el archivo a su memoria (aunque fuera de 1 GB o
mas) y apenas DESPUES revisaba si pesaba de mas -- eso tardaba un buen
rato y en Render podia agotar la memoria del servidor o el tiempo de
espera, lo que se veia como un error "502" feo en vez de un mensaje
claro.

Que se arregla:
  1. El navegador ahora revisa el tamano del video ANTES de empezar a
     subirlo -- si pesa mas de 500 MB, avisa al instante sin gastar
     tiempo ni datos.
  2. Por si acaso (por ejemplo si se sube desde otro lado que no sea
     esta pantalla), el servidor tambien revisa el tamano ANTES de
     cargar el archivo completo a memoria, usando el tamano que manda
     el navegador -- si ya se ve que pesa de mas, lo rechaza de una
     vez.
  3. La subida del video a Cloudflare R2 ya no bloquea el resto de la
     aplicacion mientras dura -- antes, mientras un video grande se
     subia, TODOS los demas usuarios podian quedarse esperando sin que
     el servidor les respondiera nada.

Que toca:
  - backend/app.py -- el endpoint de subir video.
  - frontend/index.html -- las dos pantallas donde se sube un video
    (Administrar -> Turnos, y Marketing -> Videos de Turnos).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_video_502_500mb.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["backend/app.py"] = [
    [
        "from fastapi.staticfiles import StaticFiles\nfrom pydantic import BaseModel, Field",
        "from fastapi.staticfiles import StaticFiles\nfrom starlette.concurrency import run_in_threadpool\nfrom pydantic import BaseModel, Field",
    ],
    [
        "@app.post(\"/api/admin/videos/subir\")\nasync def api_subir_video(archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_completo_o_marketing)):\n    if not r2.configurado():\n        raise HTTPException(\n            status_code=503,\n            detail=\"La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.\",\n        )\n    contenido = await archivo.read()\n    tamano = len(contenido)\n    if tamano == 0:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"])\n    limite_bytes = (empresa.get(\"limite_almacenamiento_videos_mb\") or 2048) * 1024 * 1024\n    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario[\"empresa_id\"])\n    if usado_bytes + tamano > limite_bytes:\n        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)\n        raise HTTPException(\n            status_code=400,\n            detail=f\"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.\",\n        )\n    try:\n        key, url = r2.subir_video(usuario[\"empresa_id\"], archivo.filename, contenido, archivo.content_type)\n    except Exception as e:\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir el video a Cloudflare R2: {e}\")\n    video = db.crear_video_subido(usuario[\"empresa_id\"], key, archivo.filename, tamano, url, usuario[\"id\"])\n    return video\n\n\n@app.get(\"/api/admin/videos\")",
        "@app.post(\"/api/admin/videos/subir\")\nasync def api_subir_video(request: Request, archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_completo_o_marketing)):\n    if not r2.configurado():\n        raise HTTPException(\n            status_code=503,\n            detail=\"La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.\",\n        )\n    # Se revisa el tamaño ANTES de leer el archivo completo -- si ya viene\n    # marcado como demasiado grande en el header Content-Length, se rechaza\n    # de una vez sin gastar memoria ni tiempo del servidor cargándolo\n    # completo (eso era lo que causaba que un video de más de 500 MB\n    # tardara un buen rato y terminara en un error 502 en vez de un\n    # mensaje claro).\n    content_length_header = request.headers.get(\"content-length\")\n    if content_length_header and content_length_header.isdigit():\n        if int(content_length_header) > MAX_VIDEO_BYTES_UNA_SUBIDA + (5 * 1024 * 1024):\n            raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    contenido = await archivo.read()\n    tamano = len(contenido)\n    if tamano == 0:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"])\n    limite_bytes = (empresa.get(\"limite_almacenamiento_videos_mb\") or 2048) * 1024 * 1024\n    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario[\"empresa_id\"])\n    if usado_bytes + tamano > limite_bytes:\n        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)\n        raise HTTPException(\n            status_code=400,\n            detail=f\"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.\",\n        )\n    try:\n        # run_in_threadpool: la subida a R2 es una llamada bloqueante\n        # (boto3), y sin esto se congelaría TODA la aplicación (para\n        # todos los usuarios) mientras dura la subida de un video grande.\n        key, url = await run_in_threadpool(r2.subir_video, usuario[\"empresa_id\"], archivo.filename, contenido, archivo.content_type)\n    except Exception as e:\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir el video a Cloudflare R2: {e}\")\n    video = db.crear_video_subido(usuario[\"empresa_id\"], key, archivo.filename, tamano, url, usuario[\"id\"])\n    return video\n\n\n@app.get(\"/api/admin/videos\")",
    ],
]

ARCHIVOS["frontend/index.html"] = [
    [
        "async function subirVideoMarketingUI(boton) {\n  const input = document.getElementById('mktVideoArchivo');\n  const archivo = input.files[0];\n  if (!archivo) { alert('Elige un archivo de video primero.'); return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const formData = new FormData();\n      formData.append('archivo', archivo);\n      const r = await fetch(`${API}/api/admin/videos/subir`, {\n        method: 'POST',\n        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo\n        body: formData,\n      });\n      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }\n      const video = await r.json();\n      await api(`/api/reparaciones/sucursales/${MKT_SUCURSAL_ELEGIDA}/turnos/videos/agregar`, { method: 'POST', body: JSON.stringify({ url: video.url_publica }) });\n      input.value = '';\n      mostrarExito('Video subido y agregado a la sucursal');\n      await renderVideosTurnosMarketing();\n    } catch (e) {\n      document.getElementById('mktVideosError').textContent = e.message;\n    }\n  });\n}\n\nasync function agregarVideoExistenteMarketingUI() {",
        "async function subirVideoMarketingUI(boton) {\n  const input = document.getElementById('mktVideoArchivo');\n  const archivo = input.files[0];\n  if (!archivo) { alert('Elige un archivo de video primero.'); return; }\n  if (archivo.size > 500 * 1024 * 1024) {\n    document.getElementById('mktVideosError').textContent = 'Ese video pesa más de 500 MB -- comprímelo o súbelo en partes más chicas antes de subirlo (si lo intentas de todos modos, el servidor tarda mucho y termina en un error).';\n    return;\n  }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const formData = new FormData();\n      formData.append('archivo', archivo);\n      const r = await fetch(`${API}/api/admin/videos/subir`, {\n        method: 'POST',\n        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo\n        body: formData,\n      });\n      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }\n      const video = await r.json();\n      await api(`/api/reparaciones/sucursales/${MKT_SUCURSAL_ELEGIDA}/turnos/videos/agregar`, { method: 'POST', body: JSON.stringify({ url: video.url_publica }) });\n      input.value = '';\n      mostrarExito('Video subido y agregado a la sucursal');\n      await renderVideosTurnosMarketing();\n    } catch (e) {\n      document.getElementById('mktVideosError').textContent = e.message;\n    }\n  });\n}\n\nasync function agregarVideoExistenteMarketingUI() {",
    ],
    [
        "async function subirVideoTurnosUI(sucursalId, boton) {\n  const input = document.getElementById('ct_archivo_video');\n  const archivo = input.files[0];\n  if (!archivo) { alert('Elige un archivo de video primero.'); return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const formData = new FormData();\n      formData.append('archivo', archivo);\n      const r = await fetch(`${API}/api/admin/videos/subir`, {\n        method: 'POST',\n        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo\n        body: formData,\n      });\n      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }\n      const video = await r.json();\n      const textarea = document.getElementById('ct_videos');\n      textarea.value = textarea.value.trim() ? textarea.value.trim() + '\\n' + video.url_publica : video.url_publica;\n      input.value = '';\n      mostrarExito('Video subido -- ya se agregó abajo, dale a \"Guardar video(s)\" para dejarlo activo en la pantalla');\n      await renderListaVideosSubidosTurnosUI();\n    } catch (e) {\n      alert(e.message);\n    }\n  });\n}\n\nasync function eliminarVideoSubidoUI(videoId) {",
        "async function subirVideoTurnosUI(sucursalId, boton) {\n  const input = document.getElementById('ct_archivo_video');\n  const archivo = input.files[0];\n  if (!archivo) { alert('Elige un archivo de video primero.'); return; }\n  if (archivo.size > 500 * 1024 * 1024) {\n    alert('Ese video pesa más de 500 MB -- comprímelo o súbelo en partes más chicas antes de subirlo (si lo intentas de todos modos, el servidor tarda mucho y termina en un error).');\n    return;\n  }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const formData = new FormData();\n      formData.append('archivo', archivo);\n      const r = await fetch(`${API}/api/admin/videos/subir`, {\n        method: 'POST',\n        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo\n        body: formData,\n      });\n      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }\n      const video = await r.json();\n      const textarea = document.getElementById('ct_videos');\n      textarea.value = textarea.value.trim() ? textarea.value.trim() + '\\n' + video.url_publica : video.url_publica;\n      input.value = '';\n      mostrarExito('Video subido -- ya se agregó abajo, dale a \"Guardar video(s)\" para dejarlo activo en la pantalla');\n      await renderListaVideosSubidosTurnosUI();\n    } catch (e) {\n      alert(e.message);\n    }\n  });\n}\n\nasync function eliminarVideoSubidoUI(videoId) {",
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
    print('   git commit -m "Videos: arregla error 502 al subir video de mas de 500 MB y evita que bloquee la app"')
    print("   git push")


if __name__ == "__main__":
    main()
