# -*- coding: utf-8 -*-
"""
Subir videos desde la propia app a Cloudflare R2 (sin necesitar abrir
una cuenta/consola de Cloudflare cada vez), con limite de espacio por
empresa -- y un panel en Superadmin para ver cuanto lleva usado cada
una y ajustar su limite.

Por ahora se usa desde Turnos (video de la pantalla); mas adelante se
puede reusar igual en Capacitacion.

IMPORTANTE -- antes de correr este script, en Render (Environment)
necesitas agregar estas variables con los datos de tu bucket de R2:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME
  R2_PUBLIC_URL_BASE   (ej. https://pub-xxxxxxxx.r2.dev -- SIN / al final)

Si faltan, la app sigue funcionando normal -- solo el boton de "Subir
video" avisa que todavia no esta configurado, en vez de tronar.

Que toca:
  - backend/requirements.txt -- agrega boto3
  - backend/r2.py -- ARCHIVO NUEVO, conexion a Cloudflare R2
  - backend/db.py -- tabla de videos subidos + limite por empresa
  - backend/app.py -- endpoints de subir/listar/borrar video, y de
    Superadmin para ver/ajustar el limite de cada empresa
  - frontend/index.html -- boton para subir el video directo desde
    Turnos, y panel nuevo en Superadmin ("Videos")

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_videos_subida_r2.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS["backend/requirements.txt"] = [
    [
        "requests==2.32.3\nAPScheduler==3.10.4",
        "requests==2.32.3\nboto3==1.35.99\nAPScheduler==3.10.4",
    ],
]

ARCHIVOS["backend/db.py"] = [
    [
        "CREATE INDEX IF NOT EXISTS idx_turnos_sucursal_fecha_estado ON turnos(sucursal_id, fecha, estado);\n    \"\"\")\n    conn.commit()\n\n    cur.execute(\"SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'\")",
        "CREATE INDEX IF NOT EXISTS idx_turnos_sucursal_fecha_estado ON turnos(sucursal_id, fecha, estado);\n\n        -- Videos subidos desde la app (Cloudflare R2) -- Turnos por ahora,\n        -- Capacitación más adelante reusa lo mismo. Cada empresa tiene un\n        -- límite de espacio (limite_almacenamiento_videos_mb, 2 GB por\n        -- default) para que no se dispare el costo de guardado.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS limite_almacenamiento_videos_mb INTEGER NOT NULL DEFAULT 2048;\n\n        CREATE TABLE IF NOT EXISTS videos_subidos (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            r2_key TEXT NOT NULL UNIQUE,\n            nombre_archivo TEXT NOT NULL,\n            tamano_bytes BIGINT NOT NULL,\n            url_publica TEXT NOT NULL,\n            subido_por_id INTEGER REFERENCES users(id),\n            creado_en TEXT NOT NULL\n        );\n        CREATE INDEX IF NOT EXISTS idx_videos_subidos_empresa ON videos_subidos(empresa_id);\n    \"\"\")\n    conn.commit()\n\n    cur.execute(\"SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'\")",
    ],
    [
        "def obtener_empresa(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"\"\"SELECT id, nombre, logo_base64, activo, creado_en, politicas_texto,\n                  tema, color_acento, fondo_color, fondo_base64\n           FROM empresas WHERE id = %s\"\"\",\n        (empresa_id,),\n    )\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef obtener_plantilla_pdf(empresa_id, tipo_documento):",
        "def obtener_empresa(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"\"\"SELECT id, nombre, logo_base64, activo, creado_en, politicas_texto,\n                  tema, color_acento, fondo_color, fondo_base64,\n                  limite_almacenamiento_videos_mb\n           FROM empresas WHERE id = %s\"\"\",\n        (empresa_id,),\n    )\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef obtener_plantilla_pdf(empresa_id, tipo_documento):",
    ],
    [
        "def actualizar_videos_turnos_sucursal(empresa_id, sucursal_id, videos):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE sucursales_reparacion SET turnos_videos = %s WHERE id = %s AND empresa_id = %s\",\n                (json.dumps(videos), sucursal_id, empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef _fecha_hoy_turnos():",
        "def actualizar_videos_turnos_sucursal(empresa_id, sucursal_id, videos):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE sucursales_reparacion SET turnos_videos = %s WHERE id = %s AND empresa_id = %s\",\n                (json.dumps(videos), sucursal_id, empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\n# ---- Videos subidos (Cloudflare R2) ----\n\ndef crear_video_subido(empresa_id, r2_key, nombre_archivo, tamano_bytes, url_publica, subido_por_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"\"\"INSERT INTO videos_subidos (empresa_id, r2_key, nombre_archivo, tamano_bytes, url_publica, subido_por_id, creado_en)\n           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *\"\"\",\n        (empresa_id, r2_key, nombre_archivo, tamano_bytes, url_publica, subido_por_id, ahora().isoformat()),\n    )\n    row = cur.fetchone()\n    conn.commit()\n    cur.close(); conn.close()\n    return dict(row)\n\n\ndef listar_videos_subidos(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT * FROM videos_subidos WHERE empresa_id = %s ORDER BY creado_en DESC\", (empresa_id,))\n    filas = cur.fetchall()\n    cur.close(); conn.close()\n    return [dict(r) for r in filas]\n\n\ndef obtener_video_subido(video_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT * FROM videos_subidos WHERE id = %s\", (video_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef eliminar_video_subido(video_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM videos_subidos WHERE id = %s\", (video_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef sumar_almacenamiento_videos_empresa(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT COALESCE(SUM(tamano_bytes), 0) AS total FROM videos_subidos WHERE empresa_id = %s\", (empresa_id,))\n    total = cur.fetchone()[\"total\"] or 0\n    cur.close(); conn.close()\n    return total\n\n\ndef actualizar_limite_videos_empresa(empresa_id, limite_mb):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET limite_almacenamiento_videos_mb = %s WHERE id = %s\", (limite_mb, empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef resumen_almacenamiento_videos_por_empresa():\n    \"\"\"Para el panel de Superadmin: cuánto espacio de Cloudflare R2 lleva\n    usado cada empresa en videos subidos desde la app, contra el límite\n    que tenga configurado.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT e.id AS empresa_id, e.nombre AS empresa_nombre,\n               e.limite_almacenamiento_videos_mb AS limite_mb,\n               COALESCE(SUM(v.tamano_bytes), 0) AS usado_bytes,\n               COUNT(v.id) AS total_videos\n        FROM empresas e\n        LEFT JOIN videos_subidos v ON v.empresa_id = e.id\n        GROUP BY e.id, e.nombre, e.limite_almacenamiento_videos_mb\n        ORDER BY e.nombre\n    \"\"\")\n    filas = cur.fetchall()\n    cur.close(); conn.close()\n    resultado = []\n    for r in filas:\n        usado_mb = round((r[\"usado_bytes\"] or 0) / (1024 * 1024), 1)\n        limite_mb = r[\"limite_mb\"] or 0\n        porcentaje = round((usado_mb / limite_mb) * 100, 1) if limite_mb else 0.0\n        resultado.append({\n            \"empresa_id\": r[\"empresa_id\"],\n            \"empresa_nombre\": r[\"empresa_nombre\"],\n            \"usado_mb\": usado_mb,\n            \"limite_mb\": limite_mb,\n            \"porcentaje\": porcentaje,\n            \"total_videos\": r[\"total_videos\"],\n        })\n    return resultado\n\n\ndef _fecha_hoy_turnos():",
    ],
]

ARCHIVOS["backend/app.py"] = [
    [
        "import shopify_api\ntry:\n    import microsip",
        "import shopify_api\nimport r2\ntry:\n    import microsip",
    ],
    [
        "@app.put(\"/api/reparaciones/sucursales/{sucursal_id}/turnos/videos\")\ndef api_guardar_videos_turnos(sucursal_id: int, payload: VideosTurnosSucursal, usuario: dict = Depends(requiere_admin_completo)):\n    if not db.obtener_sucursal_reparacion(usuario[\"empresa_id\"], sucursal_id):\n        raise HTTPException(status_code=404, detail=\"Sucursal no encontrada\")\n    videos = [v.strip() for v in payload.videos if v.strip()]\n    db.actualizar_videos_turnos_sucursal(usuario[\"empresa_id\"], sucursal_id, videos)\n    return {\"ok\": True}\n\n\n@app.get(\"/api/turnos/esperando\")",
        "@app.put(\"/api/reparaciones/sucursales/{sucursal_id}/turnos/videos\")\ndef api_guardar_videos_turnos(sucursal_id: int, payload: VideosTurnosSucursal, usuario: dict = Depends(requiere_admin_completo)):\n    if not db.obtener_sucursal_reparacion(usuario[\"empresa_id\"], sucursal_id):\n        raise HTTPException(status_code=404, detail=\"Sucursal no encontrada\")\n    videos = [v.strip() for v in payload.videos if v.strip()]\n    db.actualizar_videos_turnos_sucursal(usuario[\"empresa_id\"], sucursal_id, videos)\n    return {\"ok\": True}\n\n\n# ---- Videos subidos desde la app (Cloudflare R2) ----\n\nMAX_VIDEO_BYTES_UNA_SUBIDA = 500 * 1024 * 1024  # 500 MB por archivo -- si pesa más, mejor comprimirlo\n\n\n@app.post(\"/api/admin/videos/subir\")\nasync def api_subir_video(archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_completo)):\n    if not r2.configurado():\n        raise HTTPException(\n            status_code=503,\n            detail=\"La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.\",\n        )\n    contenido = await archivo.read()\n    tamano = len(contenido)\n    if tamano == 0:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"])\n    limite_bytes = (empresa.get(\"limite_almacenamiento_videos_mb\") or 2048) * 1024 * 1024\n    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario[\"empresa_id\"])\n    if usado_bytes + tamano > limite_bytes:\n        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)\n        raise HTTPException(\n            status_code=400,\n            detail=f\"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.\",\n        )\n    try:\n        key, url = r2.subir_video(usuario[\"empresa_id\"], archivo.filename, contenido, archivo.content_type)\n    except Exception as e:\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir el video a Cloudflare R2: {e}\")\n    video = db.crear_video_subido(usuario[\"empresa_id\"], key, archivo.filename, tamano, url, usuario[\"id\"])\n    return video\n\n\n@app.get(\"/api/admin/videos\")\ndef api_listar_videos_subidos(usuario: dict = Depends(requiere_admin_completo)):\n    return db.listar_videos_subidos(usuario[\"empresa_id\"])\n\n\n@app.delete(\"/api/admin/videos/{video_id}\")\ndef api_eliminar_video_subido(video_id: int, usuario: dict = Depends(requiere_admin_completo)):\n    video = db.obtener_video_subido(video_id)\n    if not video or video[\"empresa_id\"] != usuario[\"empresa_id\"]:\n        raise HTTPException(status_code=404, detail=\"Video no encontrado\")\n    try:\n        r2.eliminar_video(video[\"r2_key\"])\n    except Exception:\n        pass  # si ya no existe en R2 o algo falla, igual lo quitamos de la lista de la app\n    db.eliminar_video_subido(video_id)\n    return {\"ok\": True}\n\n\n@app.get(\"/api/superadmin/almacenamiento-videos\")\ndef api_almacenamiento_videos_superadmin(_: dict = Depends(requiere_superadmin)):\n    return db.resumen_almacenamiento_videos_por_empresa()\n\n\nclass LimiteVideosIn(BaseModel):\n    limite_mb: int\n\n\n@app.put(\"/api/superadmin/empresas/{empresa_id}/limite-videos\")\ndef api_actualizar_limite_videos(empresa_id: int, payload: LimiteVideosIn, _: dict = Depends(requiere_superadmin)):\n    if not db.obtener_empresa(empresa_id):\n        raise HTTPException(status_code=404, detail=\"Empresa no encontrada\")\n    if payload.limite_mb < 0:\n        raise HTTPException(status_code=400, detail=\"El límite no puede ser negativo\")\n    db.actualizar_limite_videos_empresa(empresa_id, payload.limite_mb)\n    return {\"ok\": True}\n\n\n@app.get(\"/api/turnos/esperando\")",
    ],
]

ARCHIVOS["frontend/index.html"] = [
    [
        "onclick=\"abrirUsoDBSuperadmin()\">📊 Uso de BD</button>\n          <button class=\"secondary\" onclick=\"abrirCotizadorSuperadmin()\">🧾 Cotizador</button>",
        "onclick=\"abrirUsoDBSuperadmin()\">📊 Uso de BD</button>\n          <button class=\"secondary\" onclick=\"abrirAlmacenamientoVideosSuperadmin()\">🎥 Videos</button>\n          <button class=\"secondary\" onclick=\"abrirCotizadorSuperadmin()\">🧾 Cotizador</button>",
    ],
    [
        "function toggleDetalleUsoDB(i) {\n  const fila = document.getElementById(`detalleUsoDB_${i}`);\n  fila.style.display = fila.style.display === 'none' ? '' : 'none';\n}\n\n// ==================================================================\n// ---- Cotizador interno de costos por empresa (Superadmin) ----",
        "function toggleDetalleUsoDB(i) {\n  const fila = document.getElementById(`detalleUsoDB_${i}`);\n  fila.style.display = fila.style.display === 'none' ? '' : 'none';\n}\n\nasync function abrirAlmacenamientoVideosSuperadmin() {\n  document.getElementById('modalContent').innerHTML = `<button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button><h2>🎥 Almacenamiento de videos por empresa</h2><p style=\"color:var(--muted);\">Cargando…</p>`;\n  abrirModal(true);\n  await renderAlmacenamientoVideosSuperadmin();\n}\n\nasync function renderAlmacenamientoVideosSuperadmin() {\n  const datos = await api('/api/superadmin/almacenamiento-videos');\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>🎥 Almacenamiento de videos por empresa</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">\n      Videos subidos desde la app (Turnos, Capacitación) a Cloudflare R2. Cada empresa tiene un límite de espacio -- ajústalo aquí si alguna necesita más.\n    </p>\n    <table class=\"users\" style=\"margin-top:8px;\">\n      <thead><tr><th>Empresa</th><th>Videos</th><th>Usado</th><th>Límite</th><th>%</th><th>Nuevo límite (MB)</th><th></th></tr></thead>\n      <tbody>\n        ${datos.map(e => `\n          <tr>\n            <td>${escapeHtml(e.empresa_nombre)}</td>\n            <td>${e.total_videos}</td>\n            <td>${e.usado_mb.toLocaleString('es-MX')} MB</td>\n            <td>${e.limite_mb.toLocaleString('es-MX')} MB</td>\n            <td style=\"color:${e.porcentaje >= 90 ? 'var(--copper)' : 'inherit'};\">${e.porcentaje}%</td>\n            <td><input type=\"number\" min=\"0\" step=\"1\" id=\"limiteVideos_${e.empresa_id}\" value=\"${e.limite_mb}\" style=\"width:90px;\" /></td>\n            <td><button class=\"secondary\" style=\"padding:2px 8px; font-size:11px;\" onclick=\"guardarLimiteVideosUI(${e.empresa_id}, this)\">Guardar</button></td>\n          </tr>\n        `).join('')}\n      </tbody>\n    </table>\n  `;\n}\n\nasync function guardarLimiteVideosUI(empresaId, boton) {\n  const input = document.getElementById(`limiteVideos_${empresaId}`);\n  const limite_mb = parseInt(input.value, 10);\n  if (isNaN(limite_mb) || limite_mb < 0) { alert('Pon un número válido de MB.'); return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api(`/api/superadmin/empresas/${empresaId}/limite-videos`, { method: 'PUT', body: JSON.stringify({ limite_mb }) });\n      mostrarExito('Límite actualizado');\n      await renderAlmacenamientoVideosSuperadmin();\n    } catch (e) {\n      alert(e.message);\n    }\n  });\n}\n\n// ==================================================================\n// ---- Cotizador interno de costos por empresa (Superadmin) ----",
    ],
    [
        "function abrirConfigTurnosSucursal(id) {\n  const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);\n  if (!s) return;\n  let videos = [];\n  try { videos = s.turnos_videos ? JSON.parse(s.turnos_videos) : []; } catch (e) { videos = []; }\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>🛎️ Turnos — ${escapeHtml(s.nombre)}</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">\n      Genera las dos ligas de esta sucursal: la <b>Pantalla</b> (se deja abierta en la smart TV de la sala de espera, con el video en loop y el número llamado) y el <b>Kiosko</b> (se deja abierto en la tablet/PC de entrada para que el cliente tome su turno). Ninguna de las dos pide iniciar sesión.\n    </p>\n    <div id=\"turnosLigasBox\">${s.codigo_turnos ? _htmlLigasTurnos(id, s.codigo_turnos) : `<button class=\"primary\" style=\"width:100%;\" onclick=\"generarLigasTurnosUI(${id})\">Generar ligas</button>`}</div>\n    <div class=\"field\" style=\"margin-top:16px;\"><label>Video(s) para la pantalla (un link por línea — recomendado: link directo a un archivo .mp4, por ejemplo de Cloudflare R2. También acepta un link de \"Insertar/Embed\" de YouTube/Drive/Vimeo/OneDrive)</label>\n      <textarea id=\"ct_videos\" rows=\"4\" placeholder=\"https://…\">${videos.map(v => escapeHtml(v)).join('\\n')}</textarea>\n    </div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"guardarVideosTurnosUI(${id}, this)\">Guardar video(s)</button>\n    <div id=\"turnosConfigError\" class=\"error-msg\"></div>\n  `;\n  abrirModal();\n}\n\n",
        "function abrirConfigTurnosSucursal(id) {\n  const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);\n  if (!s) return;\n  let videos = [];\n  try { videos = s.turnos_videos ? JSON.parse(s.turnos_videos) : []; } catch (e) { videos = []; }\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>🛎️ Turnos — ${escapeHtml(s.nombre)}</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">\n      Genera las dos ligas de esta sucursal: la <b>Pantalla</b> (se deja abierta en la smart TV de la sala de espera, con el video en loop y el número llamado) y el <b>Kiosko</b> (se deja abierto en la tablet/PC de entrada para que el cliente tome su turno). Ninguna de las dos pide iniciar sesión.\n    </p>\n    <div id=\"turnosLigasBox\">${s.codigo_turnos ? _htmlLigasTurnos(id, s.codigo_turnos) : `<button class=\"primary\" style=\"width:100%;\" onclick=\"generarLigasTurnosUI(${id})\">Generar ligas</button>`}</div>\n\n    <div class=\"field\" style=\"margin-top:16px;\"><label>Subir un video (se guarda en tu espacio de Cloudflare R2, sin necesitar una cuenta aparte)</label>\n      <input type=\"file\" id=\"ct_archivo_video\" accept=\"video/mp4,video/webm,video/quicktime,video/ogg\" />\n      <button class=\"secondary\" style=\"width:100%; margin-top:6px;\" onclick=\"subirVideoTurnosUI(${id}, this)\">Subir video</button>\n    </div>\n    <div id=\"ct_lista_videos_subidos\" style=\"font-size:12px; color:var(--muted); margin-bottom:8px;\">Cargando tus videos subidos…</div>\n\n    <div class=\"field\" style=\"margin-top:8px;\"><label>Video(s) para la pantalla (un link por línea — recomendado: link directo a un archivo .mp4, por ejemplo de Cloudflare R2. También acepta un link de \"Insertar/Embed\" de YouTube/Drive/Vimeo/OneDrive)</label>\n      <textarea id=\"ct_videos\" rows=\"4\" placeholder=\"https://…\">${videos.map(v => escapeHtml(v)).join('\\n')}</textarea>\n    </div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"guardarVideosTurnosUI(${id}, this)\">Guardar video(s)</button>\n    <div id=\"turnosConfigError\" class=\"error-msg\"></div>\n  `;\n  abrirModal();\n  renderListaVideosSubidosTurnosUI();\n}\n\nasync function renderListaVideosSubidosTurnosUI() {\n  const cont = document.getElementById('ct_lista_videos_subidos');\n  if (!cont) return;\n  try {\n    const videos = await api('/api/admin/videos');\n    if (!videos.length) { cont.innerHTML = 'Todavía no has subido ningún video.'; return; }\n    cont.innerHTML = 'Tus videos subidos (dale clic a uno para copiar su link, o a 🗑 para borrarlo y liberar espacio):<br>' + videos.map(v => `\n      <div style=\"display:flex; align-items:center; gap:6px; margin-top:4px;\">\n        <span style=\"flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; cursor:pointer;\" title=\"Clic para copiar el link\" onclick=\"navigator.clipboard.writeText('${escapeHtml(v.url_publica)}'); mostrarExito('Link copiado');\">${escapeHtml(v.nombre_archivo)} (${(v.tamano_bytes / (1024 * 1024)).toFixed(1)} MB)</span>\n        <button class=\"secondary\" style=\"padding:2px 8px; font-size:11px;\" onclick=\"eliminarVideoSubidoUI(${v.id})\">🗑</button>\n      </div>\n    `).join('');\n  } catch (e) {\n    cont.innerHTML = `<span style=\"color:var(--copper);\">${escapeHtml(e.message)}</span>`;\n  }\n}\n\nasync function subirVideoTurnosUI(sucursalId, boton) {\n  const input = document.getElementById('ct_archivo_video');\n  const archivo = input.files[0];\n  if (!archivo) { alert('Elige un archivo de video primero.'); return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const formData = new FormData();\n      formData.append('archivo', archivo);\n      const r = await fetch(`${API}/api/admin/videos/subir`, {\n        method: 'POST',\n        headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo\n        body: formData,\n      });\n      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (${r.status})`); }\n      const video = await r.json();\n      const textarea = document.getElementById('ct_videos');\n      textarea.value = textarea.value.trim() ? textarea.value.trim() + '\\n' + video.url_publica : video.url_publica;\n      input.value = '';\n      mostrarExito('Video subido -- ya se agregó abajo, dale a \"Guardar video(s)\" para dejarlo activo en la pantalla');\n      await renderListaVideosSubidosTurnosUI();\n    } catch (e) {\n      alert(e.message);\n    }\n  });\n}\n\nasync function eliminarVideoSubidoUI(videoId) {\n  if (!confirm('¿Borrar este video? Si está pegado en el campo de abajo o ya guardado en alguna pantalla, dejará de reproducirse ahí.')) return;\n  try {\n    await api(`/api/admin/videos/${videoId}`, { method: 'DELETE' });\n    await renderListaVideosSubidosTurnosUI();\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\n",
    ],
]

R2_PY_CONTENIDO = "\"\"\"Subida de videos a Cloudflare R2 (almacenamiento de archivos, sin costo\nde entrega/egress) -- usado por Turnos (video en loop de la pantalla) y,\nmás adelante, por Capacitación.\n\nNecesita estas variables de entorno configuradas en Render (Environment):\n  R2_ACCOUNT_ID        -- el \"Account ID\" de tu cuenta de Cloudflare\n  R2_ACCESS_KEY_ID      -- del token de API de R2 (Manage R2 API Tokens)\n  R2_SECRET_ACCESS_KEY  -- idem\n  R2_BUCKET_NAME         -- el nombre del bucket, ej. \"tickets-ti-videos\"\n  R2_PUBLIC_URL_BASE     -- el dominio público del bucket, ej.\n                            \"https://pub-xxxxxxxx.r2.dev\" (SIN \"/\" al final)\n\nSi falta alguna, `configurado()` regresa False y el endpoint de subida\navisa con un mensaje claro en vez de tronar feo.\n\"\"\"\nimport os\nimport uuid\n\nR2_ACCOUNT_ID = os.environ.get(\"R2_ACCOUNT_ID\")\nR2_ACCESS_KEY_ID = os.environ.get(\"R2_ACCESS_KEY_ID\")\nR2_SECRET_ACCESS_KEY = os.environ.get(\"R2_SECRET_ACCESS_KEY\")\nR2_BUCKET_NAME = os.environ.get(\"R2_BUCKET_NAME\")\nR2_PUBLIC_URL_BASE = (os.environ.get(\"R2_PUBLIC_URL_BASE\") or \"\").rstrip(\"/\")\n\n\ndef configurado():\n    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_PUBLIC_URL_BASE)\n\n\ndef _cliente():\n    import boto3\n    return boto3.client(\n        \"s3\",\n        endpoint_url=f\"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com\",\n        aws_access_key_id=R2_ACCESS_KEY_ID,\n        aws_secret_access_key=R2_SECRET_ACCESS_KEY,\n        region_name=\"auto\",\n    )\n\n\ndef subir_video(empresa_id, nombre_archivo, contenido_bytes, content_type=None):\n    \"\"\"Sube el archivo bajo una carpeta por empresa (empresa_{id}/...) con\n    un nombre único, para que dos archivos con el mismo nombre no se\n    pisen entre sí ni entre empresas. Regresa (key, url_publica).\"\"\"\n    nombre_limpio = (nombre_archivo or \"video.mp4\").replace(\"/\", \"_\").replace(\"\\\\\", \"_\")\n    key = f\"empresa_{empresa_id}/{uuid.uuid4().hex}_{nombre_limpio}\"\n    cliente = _cliente()\n    cliente.put_object(\n        Bucket=R2_BUCKET_NAME, Key=key, Body=contenido_bytes,\n        ContentType=content_type or \"video/mp4\",\n    )\n    url = f\"{R2_PUBLIC_URL_BASE}/{key}\"\n    return key, url\n\n\ndef eliminar_video(key):\n    cliente = _cliente()\n    cliente.delete_object(Bucket=R2_BUCKET_NAME, Key=key)\n"


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


def crear_r2_py():
    ruta = 'backend/r2.py'
    if os.path.exists(ruta):
        actual = leer(ruta)
        if actual.strip() == R2_PY_CONTENIDO.strip():
            print("[" + ruta + "] Ya existe y esta correcto. No hace falta nada.")
            return True
    escribir(ruta, R2_PY_CONTENIDO)
    print("[" + ruta + "] Archivo creado.")
    return True


def main():
    ok = True
    ok = crear_r2_py() and ok
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = ['backend/r2.py'] + list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Subir videos desde la app a Cloudflare R2, con limite por empresa y panel en Superadmin"')
    print("   git push")
    print()
    print("Recuerda: en Render (Environment) necesitas tener configuradas")
    print("R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME")
    print("y R2_PUBLIC_URL_BASE -- si no, el boton de subir video avisa que falta eso.")


if __name__ == "__main__":
    main()
