# -*- coding: utf-8 -*-
"""
CONCURSO DE OFRENDAS: CALAVERITA LITERARIA JUNTO AL VIDEO
- En Administrar, cada ofrenda tiene "Subir calaverita (PDF)" (tambien acepta
  imagen JPG/PNG, hasta 15 MB), con ver / quitar.
- En la pagina de votar, cada ofrenda con calaverita muestra el boton
  "Leer su calaverita literaria" (en computadora se abre ahi mismo; en el
  celular se abre en el visor de PDF del telefono).
REQUIERE haber corrido antes fix_concurso_ofrendas.py.
Toca: backend/db.py, backend/app.py, frontend/concurso.html
Se puede correr varias veces.  Correr con:  py -3 fix_concurso_calaverita.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "            video_url TEXT,\n            orden INTEGER NOT NULL DEFAULT 0\n        );\n        CREATE TABLE IF NOT EXISTS concurso_integrantes (\n            concurso_id INTEGER NOT NULL REFERENCES concursos(id) ON DELETE CASCADE,\n            usuario_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n",
   "            video_url TEXT,\n            orden INTEGER NOT NULL DEFAULT 0\n        );\n        ALTER TABLE concurso_ofrendas ADD COLUMN IF NOT EXISTS calaverita_url TEXT;\n        CREATE TABLE IF NOT EXISTS concurso_integrantes (\n            concurso_id INTEGER NOT NULL REFERENCES concursos(id) ON DELETE CASCADE,\n            usuario_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n"
  ],
  [
   "    cur.execute(\"UPDATE concurso_ofrendas SET video_url = %s WHERE id = %s AND concurso_id = %s\", (video_url, ofrenda_id, concurso_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef eliminar_ofrenda(concurso_id, ofrenda_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM concurso_ofrendas WHERE id = %s AND concurso_id = %s\", (ofrenda_id, concurso_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n",
   "    cur.execute(\"UPDATE concurso_ofrendas SET video_url = %s WHERE id = %s AND concurso_id = %s\", (video_url, ofrenda_id, concurso_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef calaverita_ofrenda(concurso_id, ofrenda_id, url):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE concurso_ofrendas SET calaverita_url = %s WHERE id = %s AND concurso_id = %s\", (url, ofrenda_id, concurso_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef eliminar_ofrenda(concurso_id, ofrenda_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM concurso_ofrendas WHERE id = %s AND concurso_id = %s\", (ofrenda_id, concurso_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n"
  ]
 ],
 "backend/app.py": [
  [
   "            \"inicia_en\": c.get(\"inicia_en\"), \"termina_en\": c.get(\"termina_en\"), \"abierto\": c[\"abierto\"], \"activo\": c[\"activo\"],\n            \"mostrar_resultados\": c[\"mostrar_resultados\"],\n            \"ofrendas\": [{\"id\": o[\"id\"], \"nombre\": o[\"nombre\"], \"descripcion\": o.get(\"descripcion\"), \"video_url\": o.get(\"video_url\"),\n                          **({\"integrantes\": o[\"integrantes\"]} if ver_integrantes else {\"num_integrantes\": len(o[\"integrantes\"])})}\n                         for o in c[\"ofrendas\"]]}\n\n",
   "            \"inicia_en\": c.get(\"inicia_en\"), \"termina_en\": c.get(\"termina_en\"), \"abierto\": c[\"abierto\"], \"activo\": c[\"activo\"],\n            \"mostrar_resultados\": c[\"mostrar_resultados\"],\n            \"ofrendas\": [{\"id\": o[\"id\"], \"nombre\": o[\"nombre\"], \"descripcion\": o.get(\"descripcion\"), \"video_url\": o.get(\"video_url\"),\n                          \"calaverita_url\": o.get(\"calaverita_url\"),\n                          **({\"integrantes\": o[\"integrantes\"]} if ver_integrantes else {\"num_integrantes\": len(o[\"integrantes\"])})}\n                         for o in c[\"ofrendas\"]]}\n\n"
  ],
  [
   "    db.crear_video_subido(usuario[\"empresa_id\"], key, archivo.filename, tamano, url, usuario[\"id\"])\n    db.video_ofrenda(concurso_id, ofrenda_id, url)\n    return {\"ok\": True, \"video_url\": url}\n\n\n@app.get(\"/cotizador-costos.html\")\n",
   "    db.crear_video_subido(usuario[\"empresa_id\"], key, archivo.filename, tamano, url, usuario[\"id\"])\n    db.video_ofrenda(concurso_id, ofrenda_id, url)\n    return {\"ok\": True, \"video_url\": url}\n\n\nMAX_BYTES_CALAVERITA = 15 * 1024 * 1024\n\n\n@app.post(\"/api/concursos/{concurso_id}/ofrendas/{ofrenda_id}/calaverita\")\nasync def api_calaverita_ofrenda(concurso_id: int, ofrenda_id: int, archivo: UploadFile = File(...),\n                                 usuario: dict = Depends(requiere_admin)):\n    \"\"\"La calaverita literaria de la ofrenda (PDF o imagen), junto al video.\"\"\"\n    c = _concurso_de_mi_empresa(concurso_id, usuario)\n    if ofrenda_id not in {o[\"id\"] for o in c[\"ofrendas\"]}:\n        raise HTTPException(status_code=404, detail=\"Ofrenda no encontrada\")\n    if not r2.configurado():\n        raise HTTPException(status_code=503, detail=\"La subida de archivos no está configurada en el servidor (faltan las credenciales de Cloudflare R2).\")\n    tipo = (archivo.content_type or \"\").lower()\n    nombre = (archivo.filename or \"calaverita.pdf\")\n    if not (tipo == \"application/pdf\" or tipo.startswith(\"image/\") or nombre.lower().endswith(\".pdf\")):\n        raise HTTPException(status_code=400, detail=\"La calaverita debe ser un PDF o una imagen (JPG/PNG)\")\n    archivo.file.seek(0, 2)\n    tamano = archivo.file.tell()\n    archivo.file.seek(0)\n    if not tamano:\n        raise HTTPException(status_code=400, detail=\"El archivo está vacío\")\n    if tamano > MAX_BYTES_CALAVERITA:\n        raise HTTPException(status_code=400, detail=\"La calaverita pesa más de 15 MB\")\n    if nombre.lower().endswith(\".pdf\"):\n        tipo = \"application/pdf\"\n    try:\n        key, url = await run_in_threadpool(r2.subir_video, usuario[\"empresa_id\"], nombre, archivo.file, tipo or \"application/pdf\")\n    except Exception as e:  # noqa: BLE001\n        print(f\"[concurso] error subiendo calaverita a R2: {e}\", file=sys.stderr)\n        raise HTTPException(status_code=502, detail=f\"No se pudo subir la calaverita: {e}\")\n    db.crear_video_subido(usuario[\"empresa_id\"], key, nombre, tamano, url, usuario[\"id\"])\n    db.calaverita_ofrenda(concurso_id, ofrenda_id, url)\n    return {\"ok\": True, \"calaverita_url\": url}\n\n\n@app.delete(\"/api/concursos/{concurso_id}/ofrendas/{ofrenda_id}/calaverita\")\ndef api_quitar_calaverita(concurso_id: int, ofrenda_id: int, usuario: dict = Depends(requiere_admin)):\n    _concurso_de_mi_empresa(concurso_id, usuario)\n    db.calaverita_ofrenda(concurso_id, ofrenda_id, None)\n    return {\"ok\": True}\n\n\n@app.get(\"/cotizador-costos.html\")\n"
  ]
 ],
 "frontend/concurso.html": [
  [
   "        <div class=\"cuerpo\">\n          <h3>${esc(o.nombre)}</h3>\n          ${o.descripcion ? `<p>${esc(o.descripcion)}</p>` : ''}\n          <div class=\"acc\">\n            ${mia ? '<span class=\"tag\">Tu equipo</span>' : ''}\n            ${votada ? '<span class=\"tag v\">✔ Tu voto</span>' : ''}\n",
   "        <div class=\"cuerpo\">\n          <h3>${esc(o.nombre)}</h3>\n          ${o.descripcion ? `<p>${esc(o.descripcion)}</p>` : ''}\n          ${o.calaverita_url ? `<button class=\"btn\" style=\"align-self:flex-start\" data-cala=\"${o.id}\">📜 Leer su calaverita literaria</button>` : ''}\n          <div class=\"acc\">\n            ${mia ? '<span class=\"tag\">Tu equipo</span>' : ''}\n            ${votada ? '<span class=\"tag v\">✔ Tu voto</span>' : ''}\n"
  ],
  [
   "        </div></article>`; }).join('') || '<div class=\"card\">Todavía no hay ofrendas.</div>'}\n    </div>\n    ${!sesion() ? '<div class=\"aviso\">Para votar, entra con tu usuario arriba ☝️</div>' : ''}`;\n  $('vista').querySelectorAll('[data-votar]').forEach(b => b.onclick = async () => {\n    const o = c.ofrendas.find(x => x.id === Number(b.dataset.votar));\n    if (!confirm(`¿Votar por \"${o.nombre}\"?` + (e.mi_voto_ofrenda_id ? '\\nSe cambia tu voto anterior.' : ''))) return;\n",
   "        </div></article>`; }).join('') || '<div class=\"card\">Todavía no hay ofrendas.</div>'}\n    </div>\n    ${!sesion() ? '<div class=\"aviso\">Para votar, entra con tu usuario arriba ☝️</div>' : ''}`;\n  $('vista').querySelectorAll('[data-cala]').forEach(b => b.onclick = () => verCalaverita(c.ofrendas.find(x => x.id === Number(b.dataset.cala))));\n  $('vista').querySelectorAll('[data-votar]').forEach(b => b.onclick = async () => {\n    const o = c.ofrendas.find(x => x.id === Number(b.dataset.votar));\n    if (!confirm(`¿Votar por \"${o.nombre}\"?` + (e.mi_voto_ofrenda_id ? '\\nSe cambia tu voto anterior.' : ''))) return;\n"
  ],
  [
   "        </div>\n        <div class=\"fila\" style=\"margin-top:8px;align-items:center\">\n          <div class=\"mini\">${o.video_url ? `✔ Video cargado · <a href=\"${esc(o.video_url)}\" target=\"_blank\">ver</a>` : '⚠️ Falta el video'}\n            <div class=\"progreso\" id=\"of_p_${o.id}\" style=\"display:none\"><i></i></div></div>\n          <div style=\"display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end\">\n            <label class=\"btn\" style=\"cursor:pointer\">🎥 ${o.video_url ? 'Cambiar video' : 'Subir video'}<input type=\"file\" accept=\"video/*\" data-video=\"${o.id}\" style=\"display:none\"></label>\n            <button class=\"btn\" data-integ=\"${o.id}\">👥 Integrantes (${o.integrantes.length})</button>\n            <button class=\"btn\" data-guardar=\"${o.id}\">Guardar</button>\n            <button class=\"btn\" data-borrar=\"${o.id}\" style=\"color:var(--peligro)\">Borrar</button>\n",
   "        </div>\n        <div class=\"fila\" style=\"margin-top:8px;align-items:center\">\n          <div class=\"mini\">${o.video_url ? `✔ Video cargado · <a href=\"${esc(o.video_url)}\" target=\"_blank\">ver</a>` : '⚠️ Falta el video'}\n            <br>${o.calaverita_url ? `✔ Calaverita cargada · <a href=\"${esc(o.calaverita_url)}\" target=\"_blank\">ver</a> · <a href=\"#\" data-quitarcala=\"${o.id}\">quitar</a>` : '📜 Sin calaverita'}\n            <div class=\"progreso\" id=\"of_p_${o.id}\" style=\"display:none\"><i></i></div></div>\n          <div style=\"display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end\">\n            <label class=\"btn\" style=\"cursor:pointer\">🎥 ${o.video_url ? 'Cambiar video' : 'Subir video'}<input type=\"file\" accept=\"video/*\" data-video=\"${o.id}\" style=\"display:none\"></label>\n            <label class=\"btn\" style=\"cursor:pointer\">📜 ${o.calaverita_url ? 'Cambiar calaverita' : 'Subir calaverita (PDF)'}<input type=\"file\" accept=\"application/pdf,.pdf,image/*\" data-calaverita=\"${o.id}\" style=\"display:none\"></label>\n            <button class=\"btn\" data-integ=\"${o.id}\">👥 Integrantes (${o.integrantes.length})</button>\n            <button class=\"btn\" data-guardar=\"${o.id}\">Guardar</button>\n            <button class=\"btn\" data-borrar=\"${o.id}\" style=\"color:var(--peligro)\">Borrar</button>\n"
  ],
  [
   "    try { await api(`/api/concursos/${CID}/ofrendas/${b.dataset.borrar}`, { method:'DELETE' }); await recargarAdmin(); } catch(e){ toast(e.message); }\n  });\n  $('vista').querySelectorAll('[data-video]').forEach(inp => inp.onchange = () => subirVideo(inp.dataset.video, inp.files[0]));\n  $('vista').querySelectorAll('[data-integ]').forEach(b => b.onclick = () => {\n    const o = c.ofrendas.find(x => x.id === Number(b.dataset.integ));\n    const enOtro = {}; c.ofrendas.forEach(x => { if (x.id !== o.id) x.integrantes.forEach(i => enOtro[i.usuario_id] = x.nombre); });\n",
   "    try { await api(`/api/concursos/${CID}/ofrendas/${b.dataset.borrar}`, { method:'DELETE' }); await recargarAdmin(); } catch(e){ toast(e.message); }\n  });\n  $('vista').querySelectorAll('[data-video]').forEach(inp => inp.onchange = () => subirVideo(inp.dataset.video, inp.files[0]));\n  $('vista').querySelectorAll('[data-calaverita]').forEach(inp => inp.onchange = () => subirVideo(inp.dataset.calaverita, inp.files[0], 'calaverita'));\n  $('vista').querySelectorAll('[data-quitarcala]').forEach(a => a.onclick = async ev => {\n    ev.preventDefault();\n    if (!confirm('¿Quitar la calaverita de esta ofrenda?')) return;\n    try { await api(`/api/concursos/${CID}/ofrendas/${a.dataset.quitarcala}/calaverita`, { method:'DELETE' }); await recargarAdmin(); } catch(e){ toast(e.message); }\n  });\n  $('vista').querySelectorAll('[data-integ]').forEach(b => b.onclick = () => {\n    const o = c.ofrendas.find(x => x.id === Number(b.dataset.integ));\n    const enOtro = {}; c.ofrendas.forEach(x => { if (x.id !== o.id) x.integrantes.forEach(i => enOtro[i.usuario_id] = x.nombre); });\n"
  ],
  [
   "  $('pk_ok').onclick = async () => { try { await guardar([...sel]); toast('Guardado'); caja.innerHTML = ''; await recargarAdmin(); } catch(e){ toast(e.message); } };\n}\n\nfunction subirVideo(id, archivo){\n  if (!archivo) return;\n  if (archivo.size > 150 * 1024 * 1024) { toast('El video pesa más de 150 MB: mándalo en menor calidad'); return; }\n  const barra = $('of_p_' + id); barra.style.display = 'block';\n  const fd = new FormData(); fd.append('archivo', archivo);\n  const x = new XMLHttpRequest();\n  x.open('POST', `/api/concursos/${CID}/ofrendas/${id}/video`);\n  const s = sesion(); if (s && s.token) x.setRequestHeader('Authorization', 'Bearer ' + s.token);\n  x.upload.onprogress = e => { if (e.lengthComputable) barra.firstElementChild.style.width = (e.loaded / e.total * 100) + '%'; };\n  x.onload = async () => {\n    if (x.status >= 200 && x.status < 300) { toast('🎥 Video subido'); await recargarAdmin(); }\n    else { let m = 'No se pudo subir el video'; try { m = JSON.parse(x.responseText).detail || m; } catch(e){} toast(m); barra.style.display = 'none'; }\n  };\n  x.onerror = () => { toast('Se cortó la conexión al subir el video'); barra.style.display = 'none'; };\n  x.send(fd);\n}\n\n",
   "  $('pk_ok').onclick = async () => { try { await guardar([...sel]); toast('Guardado'); caja.innerHTML = ''; await recargarAdmin(); } catch(e){ toast(e.message); } };\n}\n\n// Calaverita: en computadora se ve aquí mismo; en celular se abre (el visor de PDF del teléfono se ve mejor).\nfunction verCalaverita(o){\n  if (!o || !o.calaverita_url) return;\n  const esPdf = /\\.pdf(\\?|$)/i.test(o.calaverita_url);\n  if (window.innerWidth < 700 && esPdf) { window.open(o.calaverita_url, '_blank'); return; }\n  const v = document.createElement('div');\n  v.style.cssText = 'position:fixed;inset:0;background:#000d;z-index:60;display:flex;flex-direction:column;padding:14px;gap:10px';\n  v.innerHTML = `<div style=\"display:flex;gap:8px;align-items:center\"><b style=\"flex:1;font-family:Fraunces,serif;font-size:20px\">📜 ${esc(o.nombre)}</b>\n      <a class=\"btn\" href=\"${esc(o.calaverita_url)}\" target=\"_blank\" style=\"text-decoration:none\">Abrir aparte</a><button class=\"btn pri\" id=\"cala_x\">Cerrar</button></div>\n    ${esPdf ? `<iframe src=\"${esc(o.calaverita_url)}\" style=\"flex:1;width:100%;border:0;border-radius:12px;background:#fff\"></iframe>`\n            : `<div style=\"flex:1;overflow:auto;text-align:center\"><img src=\"${esc(o.calaverita_url)}\" style=\"max-width:100%;border-radius:12px\"></div>`}`;\n  document.body.appendChild(v);\n  v.querySelector('#cala_x').onclick = () => v.remove();\n}\n\nfunction subirVideo(id, archivo, que = 'video'){\n  if (!archivo) return;\n  if (que === 'calaverita' && archivo.size > 15 * 1024 * 1024) { toast('La calaverita pesa más de 15 MB'); return; }\n  if (que === 'video' && archivo.size > 150 * 1024 * 1024) { toast('El video pesa más de 150 MB: mándalo en menor calidad'); return; }\n  const barra = $('of_p_' + id); barra.style.display = 'block';\n  const fd = new FormData(); fd.append('archivo', archivo);\n  const x = new XMLHttpRequest();\n  x.open('POST', `/api/concursos/${CID}/ofrendas/${id}/${que}`);\n  const s = sesion(); if (s && s.token) x.setRequestHeader('Authorization', 'Bearer ' + s.token);\n  x.upload.onprogress = e => { if (e.lengthComputable) barra.firstElementChild.style.width = (e.loaded / e.total * 100) + '%'; };\n  x.onload = async () => {\n    if (x.status >= 200 && x.status < 300) { toast(que === 'video' ? '🎥 Video subido' : '📜 Calaverita subida'); await recargarAdmin(); }\n    else { let m = 'No se pudo subir el archivo'; try { m = JSON.parse(x.responseText).detail || m; } catch(e){} toast(m); barra.style.display = 'none'; }\n  };\n  x.onerror = () => { toast('Se cortó la conexión al subir el archivo'); barra.style.display = 'none'; };\n  x.send(fd);\n}\n\n"
  ]
 ]
}

NUEVOS = {}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_concurso_calaverita.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto and viejo not in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
