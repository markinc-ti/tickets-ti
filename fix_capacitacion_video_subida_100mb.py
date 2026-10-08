#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capacitación (RH): subir un archivo de video directo (hasta 100 MB), sin
depender de pegar un link externo.

Antes, un material de Capacitación tipo "Video" solo aceptaba un link
externo (YouTube, Drive, Vimeo, OneDrive) -- no había forma de subir un
archivo de video propio. Este parche reutiliza la MISMA infraestructura
que ya existe para los videos de Turnos/Marketing (Cloudflare R2, ver
r2.py -- su propio docstring ya decía "usado por Turnos y, más adelante,
por Capacitación"): un endpoint nuevo sube el archivo a R2 y regresa su
URL pública, que se guarda como el video_url normal del material.

Por qué un endpoint aparte en vez de reusar /api/admin/videos/subir:
- Ese endpoint es para Marketing/Turnos y permite hasta 500 MB -- David
  pidió específicamente 100 MB para Capacitación (RH), así que baja el
  tope sin tocar el límite de Turnos.
- Lo puede usar cualquiera con acceso a RH (requiere_admin_rh), no solo
  quien tenga acceso a Marketing.
- Comparte la MISMA tabla videos_subidos y el mismo cupo de almacenamiento
  por empresa que ya existía (no hace falta ninguna tabla ni migración
  nueva).

Qué toca:
1. backend/app.py:
   - Nuevo endpoint POST /api/rh/capacitacion/videos/subir (requiere_admin_rh,
     tope 100 MB, mismas validaciones de tamaño/cupo/errores claros que ya
     usa el de Turnos).
   - El mensaje de error cuando falta el video ahora menciona que se puede
     subir un archivo, no solo pegar un link.
2. frontend/index.html:
   - Nuevo helper _campoVideoMaterialCapacitacion() con un botón "Subir
     video" (además del campo de link de siempre) -- se usa tanto al crear
     como al editar un material de tipo Video.
   - Nueva función subirVideoCapacitacionUI() que sube el archivo elegido
     y llena solo el campo de link con la URL que regresa el servidor.
   - verVideoCapacitacionIncrustado() ahora usa un <video> nativo (en vez
     de <iframe>) cuando el link es un archivo subido directo (.mp4/.webm/
     etc.) -- los links de YouTube/Drive/Vimeo/OneDrive siguen usando el
     iframe de "insertar/embed" de siempre.

IMPORTANTE: en Render hay que tener configuradas las variables de entorno
de Cloudflare R2 (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
R2_BUCKET_NAME, R2_PUBLIC_URL_BASE) -- si ya subes videos en Turnos/
Marketing, ya están puestas y esto funciona sin nada más que hacer.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_capacitacion_video_subida_100mb.py
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        # 1) Mensaje de error más claro: ahora se puede subir un archivo,
        #    no solo pegar un link.
        [
            '''    elif payload.tipo == "video":
        if not payload.video_url or not payload.video_url.strip().lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Falta un link de video válido (YouTube, Drive, Vimeo o OneDrive)")
''',
            '''    elif payload.tipo == "video":
        if not payload.video_url or not payload.video_url.strip().lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Falta un video (sube un archivo o pega un link de YouTube, Drive, Vimeo u OneDrive)")
''',
        ],
        # 2) Endpoint nuevo para subir el archivo de video a Cloudflare R2.
        [
            '''    return {"archivo_base64": material["archivo_base64"], "archivo_nombre": material["archivo_nombre"]}


@app.get("/api/rh/capacitacion/estatus")
''',
            '''    return {"archivo_base64": material["archivo_base64"], "archivo_nombre": material["archivo_nombre"]}


# ---- Subir un video de Capacitación directo a Cloudflare R2 ----
# Misma infraestructura que ya usan los videos de Turnos/Marketing (ver
# r2.py y /api/admin/videos/subir), pero con su propio tope de tamaño y
# su propio permiso (RH, no Marketing).
MAX_VIDEO_BYTES_CAPACITACION = 100 * 1024 * 1024  # 100 MB -- un video de RH no necesita pesar tanto como los de Turnos (500MB)


@app.post("/api/rh/capacitacion/videos/subir")
async def api_subir_video_capacitacion(request: Request, archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_rh)):
    """Sube el video elegido a Cloudflare R2 y regresa su URL pública, para
    usarla como video_url de un material de Capacitación (tipo="video").
    Reusa la misma tabla videos_subidos y el mismo cupo de almacenamiento
    por empresa que ya usan los videos de Turnos/Marketing."""
    if not r2.configurado():
        raise HTTPException(
            status_code=503,
            detail="La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.",
        )
    # Igual que en /api/admin/videos/subir: se revisa el tamaño ANTES de
    # leer el archivo completo, para rechazar de una vez un archivo
    # demasiado grande sin gastar memoria ni tiempo del servidor.
    content_length_header = request.headers.get("content-length")
    if content_length_header and content_length_header.isdigit():
        if int(content_length_header) > MAX_VIDEO_BYTES_CAPACITACION + (5 * 1024 * 1024):
            raise HTTPException(status_code=400, detail="El archivo pesa más de 100 MB -- comprime el video o sube uno más chico")
    archivo.file.seek(0, 2)
    tamano = archivo.file.tell()
    archivo.file.seek(0)
    if tamano == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if tamano > MAX_VIDEO_BYTES_CAPACITACION:
        raise HTTPException(status_code=400, detail="El archivo pesa más de 100 MB -- comprime el video o sube uno más chico")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    limite_bytes = (empresa.get("limite_almacenamiento_videos_mb") or 2048) * 1024 * 1024
    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario["empresa_id"])
    if usado_bytes + tamano > limite_bytes:
        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.",
        )
    try:
        key, url = await run_in_threadpool(r2.subir_video, usuario["empresa_id"], archivo.filename, archivo.file, archivo.content_type)
    except Exception as e:
        print(f"[videos-capacitacion] error subiendo a Cloudflare R2 (empresa {usuario['empresa_id']}, archivo {archivo.filename!r}, {tamano} bytes): {e}", file=sys.stderr)
        raise HTTPException(status_code=502, detail=f"No se pudo subir el video a Cloudflare R2: {e}")
    video = db.crear_video_subido(usuario["empresa_id"], key, archivo.filename, tamano, url, usuario["id"])
    return video


@app.get("/api/rh/capacitacion/estatus")
''',
        ],
    ],
    'frontend/index.html': [
        # 1) Helper nuevo con el botón "Subir video" + campo de link, y su
        #    función de subida -- se agrega justo antes de
        #    abrirFormMaterialCapacitacion().
        [
            '''    </div>
  `;
}

async function abrirFormMaterialCapacitacion(materialId = null) {
''',
            '''    </div>
  `;
}

function _campoVideoMaterialCapacitacion(valorActual) {
  return `
    <div class="field">
      <label>Subir archivo de video (máximo 100 MB)</label>
      <input type="file" id="capMatVideoArchivo" accept="video/*" />
      <button class="secondary" type="button" style="margin-top:6px;" onclick="subirVideoCapacitacionUI(this)">Subir video</button>
      <p style="font-size:11px; color:var(--muted); margin:4px 0 0;">Al terminar de subirlo, el link de abajo se llena solo -- nada más falta darle Guardar.</p>
    </div>
    <div class="field">
      <label>...o pega un link del video</label>
      <input id="capMatVideoUrl" value="${escapeHtml(valorActual || '')}" placeholder="https://…" />
      <p style="font-size:11px; color:var(--muted); margin:4px 0 0;">Puedes subir el archivo arriba, o pegar aquí un link de YouTube, Drive, Vimeo u OneDrive (para OneDrive usa el link de "Insertar/Embed" al compartirlo -- no el de "Copiar vínculo", que normalmente no se deja incrustar).</p>
    </div>
    <div id="capMatVideoError" class="error-msg"></div>
  `;
}

async function subirVideoCapacitacionUI(boton) {
  const input = document.getElementById('capMatVideoArchivo');
  const archivo = input.files[0];
  if (!archivo) { alert('Elige un archivo de video primero.'); return; }
  if (archivo.size > 100 * 1024 * 1024) {
    document.getElementById('capMatVideoError').textContent = 'Ese video pesa más de 100 MB -- comprímelo o sube uno más chico (si lo intentas de todos modos, el servidor lo va a rechazar igual).';
    return;
  }
  await conBloqueoDeBoton(boton, async () => {
    try {
      document.getElementById('capMatVideoError').textContent = '';
      const formData = new FormData();
      formData.append('archivo', archivo);
      const r = await fetch(`${API}/api/rh/capacitacion/videos/subir`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo
        body: formData,
      });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }
      const video = await r.json();
      document.getElementById('capMatVideoUrl').value = video.url_publica;
      input.value = '';
      mostrarExito('Video subido -- ya puedes darle Guardar');
    } catch (e) {
      document.getElementById('capMatVideoError').textContent = e.message;
    }
  });
}

async function abrirFormMaterialCapacitacion(materialId = null) {
''',
        ],
        # 2) Campo de video al EDITAR un material -- usa el helper nuevo.
        [
            '''      ${material.tipo === 'video' ? `<div class="field"><label>Link del video</label><input id="capMatVideoUrl" value="${escapeHtml(material.video_url || '')}" /><p style="font-size:11px; color:var(--muted); margin:4px 0 0;">El video se ve incrustado dentro de la app. Si es de OneDrive, usa el link de "Insertar" (Insert/Embed) al compartirlo — no el de "Copiar vínculo", que normalmente no se deja incrustar.</p></div>` : `<div class="field"><label>Reemplazar PDF (opcional — déjalo vacío para conservar el actual)</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>`}
''',
            '''      ${material.tipo === 'video' ? _campoVideoMaterialCapacitacion(material.video_url) : `<div class="field"><label>Reemplazar PDF (opcional — déjalo vacío para conservar el actual)</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>`}
''',
        ],
        # 3) Texto de la opción del tipo "Video" en el selector.
        [
            '''          <option value="video">Video (link de YouTube, Drive, Vimeo o OneDrive)</option>
''',
            '''          <option value="video">Video (sube un archivo o pega un link)</option>
''',
        ],
        # 4) Campo de video al CREAR un material -- usa el helper nuevo.
        [
            '''      <div class="field" id="capMatCampoVideo" style="display:none;">
        <label>Link del video</label>
        <input id="capMatVideoUrl" placeholder="https://…" />
        <p style="font-size:11px; color:var(--muted); margin:4px 0 0;">El video se ve incrustado dentro de la app. Si es de OneDrive, usa el link de "Insertar" (Insert/Embed) al compartirlo — no el de "Copiar vínculo", que normalmente no se deja incrustar.</p>
      </div>
''',
            '''      <div class="field" id="capMatCampoVideo" style="display:none;">
        ${_campoVideoMaterialCapacitacion('')}
      </div>
''',
        ],
        # 5) Mensaje de error al guardar sin video.
        [
            '''      document.getElementById('capMatError').textContent = 'Falta el link del video';
''',
            '''      document.getElementById('capMatError').textContent = 'Falta subir un video o pegar un link';
''',
        ],
        # 6) El reproductor del estudiante/empleado: usa <video> nativo
        #    para un archivo subido directo, e <iframe> para links de
        #    YouTube/Drive/Vimeo/OneDrive (como ya era).
        [
            '''function verVideoCapacitacionIncrustado(material) {
  // Se ve incrustado (iframe) dentro del mismo panel — si el link no es
  // un link de "insertar/embed" (por ejemplo, un link normal de "copiar
  // vínculo" de OneDrive), el propio proveedor puede negarse a cargar
  // dentro de un iframe; por eso siempre dejamos también el link para
  // abrirlo aparte, como respaldo.
  const cont = document.getElementById('miCapacitacionLista');
  if (!cont) { window.open(material.video_url, '_blank'); return; }
  cont.innerHTML = `
    <button class="secondary" style="margin-bottom:10px;" onclick="renderMiCapacitacionLista()">← Volver a la lista</button>
    <div style="font-weight:600; font-size:13px; margin-bottom:8px;">🎥 ${escapeHtml(material.titulo)}</div>
    <div style="position:relative; width:100%; padding-top:56.25%; background:#000; border-radius:6px; overflow:hidden;">
      <iframe src="${escapeHtml(material.video_url)}" allow="autoplay; fullscreen" allowfullscreen
              style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;"></iframe>
    </div>
    <p style="font-size:11px; color:var(--muted); margin-top:8px;">
      ¿No carga el video aquí? <a href="${escapeHtml(material.video_url)}" target="_blank" rel="noopener">Ábrelo en OneDrive</a>.
    </p>
  `;
}
''',
            '''function _esArchivoDeVideoDirecto(url) {
  // Un video SUBIDO por la app (Cloudflare R2) es un archivo real
  // (.mp4/.webm/...) -- se reproduce mejor con un <video> nativo que con
  // un iframe. Un link de YouTube/Drive/Vimeo/OneDrive es una página, no
  // un archivo, así que esos siguen usando el iframe de "insertar/embed"
  // de siempre.
  return /\\.(mp4|webm|mov|m4v|ogg)(\\?|$)/i.test(url || '');
}

function verVideoCapacitacionIncrustado(material) {
  // Se ve incrustado dentro del mismo panel -- si el link no es un link
  // de "insertar/embed" (por ejemplo, un link normal de "copiar vínculo"
  // de OneDrive), el propio proveedor puede negarse a cargar dentro de
  // un iframe; por eso siempre dejamos también el link para abrirlo
  // aparte, como respaldo.
  const cont = document.getElementById('miCapacitacionLista');
  if (!cont) { window.open(material.video_url, '_blank'); return; }
  const reproductor = _esArchivoDeVideoDirecto(material.video_url)
    ? `<video src="${escapeHtml(material.video_url)}" controls playsinline
             style="position:absolute; top:0; left:0; width:100%; height:100%; background:#000;"></video>`
    : `<iframe src="${escapeHtml(material.video_url)}" allow="autoplay; fullscreen" allowfullscreen
              style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;"></iframe>`;
  cont.innerHTML = `
    <button class="secondary" style="margin-bottom:10px;" onclick="renderMiCapacitacionLista()">← Volver a la lista</button>
    <div style="font-weight:600; font-size:13px; margin-bottom:8px;">🎥 ${escapeHtml(material.titulo)}</div>
    <div style="position:relative; width:100%; padding-top:56.25%; background:#000; border-radius:6px; overflow:hidden;">
      ${reproductor}
    </div>
    <p style="font-size:11px; color:var(--muted); margin-top:8px;">
      ¿No carga el video aquí? <a href="${escapeHtml(material.video_url)}" target="_blank" rel="noopener">Ábrelo en otra pestaña</a>.
    </p>
  `;
}
''',
        ],
    ],
}


def main():
    cambios_totales = 0
    for ruta, hunks in ARCHIVOS.items():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
        except FileNotFoundError:
            print(f"ERROR: no se encontro {ruta} -- corre este script desde la raiz del repo tickets-ti.")
            sys.exit(1)

        original = contenido
        cambios_archivo = 0
        for viejo, nuevo in hunks:
            if nuevo in contenido:
                continue  # ya aplicado antes -- idempotente
            if viejo not in contenido:
                print(f"ERROR: no se encontro el texto esperado en {ruta}.")
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
                print("--- fragmento esperado ---")
                print(viejo[:300])
                sys.exit(1)
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios_archivo += 1

        if contenido != original:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: {ruta} -- {cambios_archivo} cambio(s) aplicado(s).")
            cambios_totales += cambios_archivo
        else:
            print(f"(sin cambios) {ruta} -- ya estaba aplicado.")

    if cambios_totales == 0:
        print()
        print("No habia nada nuevo que aplicar (el parche ya estaba puesto).")
    else:
        print()
        print(f"{cambios_totales} cambio(s) aplicado(s) en total.")

    print()
    print("Ahora corre esto para subirlo:")
    print()
    print("    git add backend/app.py frontend/index.html")
    print('    git commit -m "Capacitacion RH: subir video directo (hasta 100MB) ademas de pegar un link"')
    print("    git push")


if __name__ == "__main__":
    main()
