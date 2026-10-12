# -*- coding: utf-8 -*-
"""
Laboratorio:
  - Pedidos creados desde la app: primer estatus "Registro pedido en app".
  - Comprobante de pago: ya se ve (la app lo mandaba sin "data:"); al pasar
    el mouse se amplia y con clic se ve completo.
  - Confirmar pago reportado: muestra total del trabajo, ya pagado y lo que se
    debe; avisa si lo capturado no cubre o sobra.
  - SOLO el usuario del laboratorio (sucursal marcada como laboratorio) o el
    admin confirma/rechaza pagos reportados y cambia/cancela el estatus.

REQUIERE haber corrido antes fix_laboratorio_estudiantes_v2.py.
Toca: backend/app.py, backend/db.py, frontend/index.html, frontend/laboratorio_estudiantes.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    if usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\":\n        return usuario\n    raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n\n\ndef requiere_no_ser_estudiante_laboratorio(usuario: dict = Depends(requiere_ver_laboratorio)) -> dict:\n",
   "    if usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\":\n        return usuario\n    raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n\n\ndef _es_usuario_laboratorio(usuario: dict) -> bool:\n    \"\"\"El usuario del LABORATORIO (dado de alta en la sucursal marcada como\n    laboratorio) — es el único que confirma pagos reportados y mueve los\n    estatus. El administrador también puede.\"\"\"\n    if usuario.get(\"rol\") in (\"admin\", \"superadmin\"):\n        return True\n    sucursal_lab = db.obtener_sucursal_laboratorio(usuario[\"empresa_id\"])\n    return bool(sucursal_lab) and db.obtener_sucursal_id_usuario(usuario[\"id\"]) == sucursal_lab[\"id\"]\n\n\ndef _como_data_url(b64):\n    \"\"\"Las apps mandan el comprobante como base64 \"pelón\" (sin data:...) — se\n    guarda como data URL para que el navegador lo pueda mostrar.\"\"\"\n    if not b64 or b64.startswith(\"data:\"):\n        return b64\n    tipo = \"image/png\" if b64.startswith(\"iVBOR\") else \"application/pdf\" if b64.startswith(\"JVBER\") \\\n        else \"image/webp\" if b64.startswith(\"UklGR\") else \"image/heic\" if b64[4:12] == \"ZnR5cGhl\" else \"image/jpeg\"\n    return f\"data:{tipo};base64,{b64}\"\n\n\ndef requiere_no_ser_estudiante_laboratorio(usuario: dict = Depends(requiere_ver_laboratorio)) -> dict:\n"
  ],
  [
   "            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n            if not sucursal_lab or mi_sucursal_id != sucursal_lab[\"id\"]:\n                raise HTTPException(status_code=403, detail=\"Solo el laboratorio puede mover estos estados\")\n    db.cambiar_estado_laboratorio(usuario[\"empresa_id\"], trabajo_id, payload.estado)\n    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"], f\"Cambió el estado a: {nombre_estado}\")\n",
   "            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n            if not sucursal_lab or mi_sucursal_id != sucursal_lab[\"id\"]:\n                raise HTTPException(status_code=403, detail=\"Solo el laboratorio puede mover estos estados\")\n    if payload.estado == \"cancelado\" and not _es_usuario_laboratorio(usuario):\n        raise HTTPException(status_code=403, detail=\"Solo el laboratorio puede cambiar el estatus\")\n    db.cambiar_estado_laboratorio(usuario[\"empresa_id\"], trabajo_id, payload.estado)\n    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"], f\"Cambió el estado a: {nombre_estado}\")\n"
  ],
  [
   "        payload.notas, None, usuario[\"id\"],\n        (payload.folio_escaneo or \"\").strip() or None, payload.requiere_factura, piezas,\n    )\n    db.agregar_actualizacion_laboratorio(\n        trabajo[\"id\"], usuario[\"id\"],\n        f\"{registro['nombre_completo']} creó su propio trabajo desde el portal de estudiantes. Falta registrar el pago.\",\n    )\n    return trabajo\n\n",
   "        payload.notas, None, usuario[\"id\"],\n        (payload.folio_escaneo or \"\").strip() or None, payload.requiere_factura, piezas,\n    )\n    db.marcar_origen_app_laboratorio(trabajo[\"id\"])\n    trabajo[\"origen\"] = \"app\"\n    db.agregar_actualizacion_laboratorio(\n        trabajo[\"id\"], usuario[\"id\"],\n        f\"Registro pedido en app — {registro['nombre_completo']} creó su pedido desde la app. Falta registrar el pago.\",\n    )\n    return trabajo\n\n"
  ],
  [
   "            raise HTTPException(status_code=400, detail=\"Este trabajo ya está cubierto — no hace falta reportar otro pago\")\n    if len(payload.comprobante_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"La foto del comprobante pesa demasiado (máximo 5MB)\")\n    datos_ia = ia.leer_comprobante_transferencia_laboratorio(payload.comprobante_base64, empresa_id=usuario[\"empresa_id\"])\n    reporte = db.reportar_pago_transferencia_laboratorio(\n        trabajo_id, usuario[\"id\"], payload.comprobante_base64,\n",
   "            raise HTTPException(status_code=400, detail=\"Este trabajo ya está cubierto — no hace falta reportar otro pago\")\n    if len(payload.comprobante_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"La foto del comprobante pesa demasiado (máximo 5MB)\")\n    payload.comprobante_base64 = _como_data_url(payload.comprobante_base64)\n    datos_ia = ia.leer_comprobante_transferencia_laboratorio(payload.comprobante_base64, empresa_id=usuario[\"empresa_id\"])\n    reporte = db.reportar_pago_transferencia_laboratorio(\n        trabajo_id, usuario[\"id\"], payload.comprobante_base64,\n"
  ],
  [
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], reporte[\"trabajo_id\"])\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    if usuario[\"rol\"] != \"admin\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n    return reporte, trabajo\n\n\n",
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], reporte[\"trabajo_id\"])\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    if not _es_usuario_laboratorio(usuario):\n        raise HTTPException(status_code=403, detail=\"Solo el usuario del laboratorio puede confirmar o rechazar pagos reportados\")\n    return reporte, trabajo\n\n\n"
  ],
  [
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    return trabajo\n\n\n@app.get(\"/api/laboratorio/dscore/config\")\n",
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if usuario[\"rol\"] != \"estudiante\":\n        trabajo[\"soy_laboratorio\"] = _es_usuario_laboratorio(usuario)\n    return trabajo\n\n\n@app.get(\"/api/laboratorio/dscore/config\")\n"
  ]
 ],
 "backend/db.py": [
  [
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entro_laboratorio_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS envio_sucursal_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n",
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entro_laboratorio_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS envio_sucursal_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_en TEXT;\n        -- 'sucursal' (alta en mostrador) o 'app' (el estudiante lo creó desde la app/portal):\n        -- los de la app empiezan como \"Registro pedido en app\".\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'sucursal';\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n"
  ],
  [
   "    return dict(row) if row else None\n\n\ndef reportar_pago_transferencia_laboratorio(trabajo_id, reportado_por_id, comprobante_base64, monto_detectado, fecha_detectada, referencia_detectada, banco_detectado):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return dict(row) if row else None\n\n\ndef marcar_origen_app_laboratorio(trabajo_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE trabajos_laboratorio SET origen = 'app' WHERE id = %s\", (trabajo_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef reportar_pago_transferencia_laboratorio(trabajo_id, reportado_por_id, comprobante_base64, monto_detectado, fecha_detectada, referencia_detectada, banco_detectado):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  envio_sucursal: 'media', listo_entrega: 'baja', entregado: 'baja', cancelado: 'baja',\n};\nconst NOMBRES_TIPO_SOLICITANTE_LAB = { estudiante: 'Estudiante', doctor: 'Doctor' };\nconst NOMBRES_METODO_PAGO_LAB = {\n  efectivo: 'Efectivo', tarjeta_debito: 'Tarjeta de débito', tarjeta_credito: 'Tarjeta de crédito',\n  transferencia: 'Transferencia', otro: 'Otro',\n",
   "  envio_sucursal: 'media', listo_entrega: 'baja', entregado: 'baja', cancelado: 'baja',\n};\nconst NOMBRES_TIPO_SOLICITANTE_LAB = { estudiante: 'Estudiante', doctor: 'Doctor' };\n\n// Los pedidos que el estudiante crea desde la app empiezan como \"Registro\n// pedido en app\" (internamente siguen en 'recibido' hasta que entran al laboratorio).\nfunction lab_nombreEstado(w) {\n  if (w && w.estado === 'recibido' && w.origen === 'app') return 'Registro pedido en app';\n  return NOMBRES_ESTADO_LABORATORIO[w && w.estado] || (w && w.estado) || '';\n}\n\n// Comprobantes: las apps los mandaban como base64 sin \"data:...\" — se arma la URL para poder verlos.\nfunction lab_srcImagen(b64) {\n  if (!b64) return '';\n  if (b64.startsWith('data:')) return b64;\n  const tipo = b64.startsWith('iVBOR') ? 'image/png' : b64.startsWith('JVBER') ? 'application/pdf' : b64.startsWith('UklGR') ? 'image/webp' : 'image/jpeg';\n  return `data:${tipo};base64,${b64}`;\n}\n\n// Ver un comprobante en grande (los navegadores ya no dejan abrir data URLs en otra pestaña).\nfunction lab_verComprobante(src) {\n  const capa = document.createElement('div');\n  capa.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,.85); z-index:99999; display:flex; align-items:center; justify-content:center; cursor:zoom-out; padding:20px;';\n  capa.innerHTML = src.startsWith('data:application/pdf')\n    ? `<iframe src=\"${src}\" style=\"width:90vw; height:90vh; border:0; background:#fff;\"></iframe>`\n    : `<img src=\"${src}\" style=\"max-width:95vw; max-height:92vh; object-fit:contain; border-radius:8px; box-shadow:0 10px 40px rgba(0,0,0,.6);\" />`;\n  capa.onclick = () => capa.remove();\n  document.body.appendChild(capa);\n}\n\nfunction lab_htmlComprobante(b64, tam, titulo) {\n  const src = lab_srcImagen(b64);\n  if (!src) return '';\n  return `<div class=\"lab-comprobante\" style=\"width:${tam}px; height:${tam}px;\" title=\"${escapeHtml(titulo)} — pasa el mouse para ampliar, clic para verlo completo\">\n    <img src=\"${src}\" alt=\"${escapeHtml(titulo)}\" onclick=\"event.stopPropagation(); lab_verComprobante(this.src)\" />\n  </div>`;\n}\n\n(function () {\n  if (document.getElementById('lab_estilos_comprobante')) return;\n  const st = document.createElement('style');\n  st.id = 'lab_estilos_comprobante';\n  st.textContent = `\n    .lab-comprobante { position:relative; flex-shrink:0; }\n    .lab-comprobante img { width:100%; height:100%; object-fit:cover; border-radius:6px; cursor:zoom-in; background:#fff;\n      transition:transform .18s ease, box-shadow .18s ease; transform-origin:left top; position:relative; z-index:1; }\n    .lab-comprobante:hover img { transform:scale(4.2); object-fit:contain; z-index:50; box-shadow:0 12px 40px rgba(0,0,0,.55); }\n  `;\n  document.head.appendChild(st);\n})();\nconst NOMBRES_METODO_PAGO_LAB = {\n  efectivo: 'Efectivo', tarjeta_debito: 'Tarjeta de débito', tarjeta_credito: 'Tarjeta de crédito',\n  transferencia: 'Transferencia', otro: 'Otro',\n"
  ],
  [
   "            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n            <td><span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${NOMBRES_ESTADO_LABORATORIO[w.estado]}</span>${(w.pagos_reportados||[]).some(r=>r.estado==='pendiente') ? ' <span title=\"Pago por transferencia reportado -- pendiente de confirmar\" style=\"cursor:default;\">📋</span>' : ''}</td>\n            <td>${w.dias_transcurridos !== null ? `${w.dias_transcurridos}d` : '—'}</td>\n            <td><button class=\"secondary\" style=\"padding:5px 10px; font-size:11px;\" onclick=\"abrirDetalleLaboratorio(${w.id})\">Ver</button></td>\n          </tr>\n",
   "            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n            <td><span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${lab_nombreEstado(w)}</span>${(w.pagos_reportados||[]).some(r=>r.estado==='pendiente') ? ' <span title=\"Pago por transferencia reportado -- pendiente de confirmar\" style=\"cursor:default;\">📋</span>' : ''}</td>\n            <td>${w.dias_transcurridos !== null ? `${w.dias_transcurridos}d` : '—'}</td>\n            <td><button class=\"secondary\" style=\"padding:5px 10px; font-size:11px;\" onclick=\"abrirDetalleLaboratorio(${w.id})\">Ver</button></td>\n          </tr>\n"
  ],
  [
   "  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    ${esAdmin ? `<button class=\"danger\" style=\"margin-bottom:10px;\" onclick=\"eliminarTrabajoLaboratorioUI(${w.id})\">Eliminar trabajo (por error al crearlo)</button>` : ''}\n    <h2>${escapeHtml(w.folio)} <span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${NOMBRES_ESTADO_LABORATORIO[w.estado]}</span></h2>\n    <p style=\"font-size:12px; color:var(--muted);\">\n      ${escapeHtml(w.solicitante_nombre)} (${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo]||w.solicitante_tipo})\n      ${w.universidad_clinica ? ` · ${escapeHtml(w.universidad_clinica)}` : ''}\n",
   "  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    ${esAdmin ? `<button class=\"danger\" style=\"margin-bottom:10px;\" onclick=\"eliminarTrabajoLaboratorioUI(${w.id})\">Eliminar trabajo (por error al crearlo)</button>` : ''}\n    <h2>${escapeHtml(w.folio)} <span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${lab_nombreEstado(w)}</span></h2>\n    <p style=\"font-size:12px; color:var(--muted);\">\n      ${escapeHtml(w.solicitante_nombre)} (${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo]||w.solicitante_tipo})\n      ${w.universidad_clinica ? ` · ${escapeHtml(w.universidad_clinica)}` : ''}\n"
  ],
  [
   "      <br><button class=\"secondary\" style=\"margin-bottom:10px;\" onclick=\"descargarPdfLaboratorio(${w.id}, 'orden_trabajo_${w.folio}')\">📄 Descargar orden de trabajo (PDF)</button>\n    ` : ''}\n\n    ${ESTADOS_LABORATORIO_LIBRES_JS.includes(w.estado) || w.estado === 'en_laboratorio' ? `\n      <div class=\"row-2\" style=\"align-items:end; margin-top:12px;\">\n        <div class=\"field\"><label>Mover estado dentro del laboratorio</label>\n          <select id=\"lab_estado_sel\">${ESTADOS_LABORATORIO_LIBRES_JS.map(e => `<option value=\"${e}\" ${e===w.estado?'selected':''}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join('')}</select>\n",
   "      <br><button class=\"secondary\" style=\"margin-bottom:10px;\" onclick=\"descargarPdfLaboratorio(${w.id}, 'orden_trabajo_${w.folio}')\">📄 Descargar orden de trabajo (PDF)</button>\n    ` : ''}\n\n    ${(ESTADOS_LABORATORIO_LIBRES_JS.includes(w.estado) || w.estado === 'en_laboratorio') && w.soy_laboratorio ? `\n      <div class=\"row-2\" style=\"align-items:end; margin-top:12px;\">\n        <div class=\"field\"><label>Mover estado dentro del laboratorio</label>\n          <select id=\"lab_estado_sel\">${ESTADOS_LABORATORIO_LIBRES_JS.map(e => `<option value=\"${e}\" ${e===w.estado?'selected':''}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join('')}</select>\n"
  ],
  [
   "    ${yaPagado ? `\n      <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Pago registrado — total pagado ${_fmtC(w.pago_monto_total)}</label>\n      <p style=\"font-size:12px; margin:4px 0;\">${w.pago_metodos.map(m => `${NOMBRES_METODO_PAGO_LAB[m.metodo]||m.metodo}: ${_fmtC(m.monto)}`).join(' · ')}</p>\n      ${w.pago_comprobante_base64 ? `<img src=\"${w.pago_comprobante_base64}\" style=\"width:90px; height:90px; object-fit:cover; border-radius:6px; cursor:pointer;\" onclick=\"window.open('${w.pago_comprobante_base64}','_blank')\" title=\"Comprobante de pago\" />` : ''}\n      ${saldo > 0 ? `<p style=\"font-size:13px; color:var(--trace); margin-top:6px;\">💰 Sobrante: ${_fmtC(saldo)}</p>` : ''}\n      ${saldo < 0 && w.estado === 'recibido' ? `\n        <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;\">\n",
   "    ${yaPagado ? `\n      <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Pago registrado — total pagado ${_fmtC(w.pago_monto_total)}</label>\n      <p style=\"font-size:12px; margin:4px 0;\">${w.pago_metodos.map(m => `${NOMBRES_METODO_PAGO_LAB[m.metodo]||m.metodo}: ${_fmtC(m.monto)}`).join(' · ')}</p>\n      ${w.pago_comprobante_base64 ? lab_htmlComprobante(w.pago_comprobante_base64, 90, 'Comprobante de pago') : ''}\n      ${saldo > 0 ? `<p style=\"font-size:13px; color:var(--trace); margin-top:6px;\">💰 Sobrante: ${_fmtC(saldo)}</p>` : ''}\n      ${saldo < 0 && w.estado === 'recibido' ? `\n        <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;\">\n"
  ],
  [
   "      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;\">\n        <p style=\"font-size:13px; margin:0 0 8px;\">📋 El estudiante reportó un pago por transferencia — revísalo contra el banco antes de confirmar.</p>\n        <div style=\"display:flex; gap:10px; align-items:flex-start;\">\n          <img src=\"${r.comprobante_base64}\" style=\"width:80px; height:80px; object-fit:cover; border-radius:6px; cursor:pointer; flex-shrink:0;\" onclick=\"window.open('${r.comprobante_base64}','_blank')\" title=\"Comprobante\" />\n          <div style=\"font-size:12px; color:var(--muted);\">\n            IA sugiere: ${r.monto_detectado != null ? _fmtC(r.monto_detectado) : '—'} · ${r.fecha_detectada ? escapeHtml(r.fecha_detectada) : 'fecha —'}<br>\n            Ref: ${r.referencia_detectada ? escapeHtml(r.referencia_detectada) : '—'} · Banco: ${r.banco_detectado ? escapeHtml(r.banco_detectado) : '—'}<br>\n            <span style=\"font-size:11px;\">Esto es solo lo que alcanzó a leer la IA — confírmalo tú contra el banco.</span>\n          </div>\n        </div>\n        <div style=\"display:flex; gap:8px; margin-top:10px;\">\n          <button class=\"secondary\" style=\"flex:1;\" onclick=\"rechazarPagoReportadoLaboratorioUI(${r.id}, ${w.id})\">Rechazar</button>\n          <button class=\"primary\" style=\"flex:2;\" onclick=\"abrirConfirmarPagoReportadoLaboratorio(${r.id}, ${w.id}, ${r.monto_detectado != null ? r.monto_detectado : 'null'})\">Confirmar pago</button>\n        </div>\n      </div>\n    `).join('') : ''}\n\n",
   "      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;\">\n        <p style=\"font-size:13px; margin:0 0 8px;\">📋 El estudiante reportó un pago por transferencia — revísalo contra el banco antes de confirmar.</p>\n        <div style=\"display:flex; gap:10px; align-items:flex-start;\">\n          ${lab_htmlComprobante(r.comprobante_base64, 110, 'Comprobante')}\n          <div style=\"font-size:12px; color:var(--muted);\">\n            IA sugiere: ${r.monto_detectado != null ? _fmtC(r.monto_detectado) : '—'} · ${r.fecha_detectada ? escapeHtml(r.fecha_detectada) : 'fecha —'}<br>\n            Ref: ${r.referencia_detectada ? escapeHtml(r.referencia_detectada) : '—'} · Banco: ${r.banco_detectado ? escapeHtml(r.banco_detectado) : '—'}<br>\n            <span style=\"font-size:11px;\">Esto es solo lo que alcanzó a leer la IA — confírmalo tú contra el banco.</span>\n          </div>\n        </div>\n        ${w.soy_laboratorio ? `\n        <div style=\"display:flex; gap:8px; margin-top:10px;\">\n          <button class=\"secondary\" style=\"flex:1;\" onclick=\"rechazarPagoReportadoLaboratorioUI(${r.id}, ${w.id})\">Rechazar</button>\n          <button class=\"primary\" style=\"flex:2;\" onclick=\"abrirConfirmarPagoReportadoLaboratorio(${r.id}, ${w.id}, ${r.monto_detectado != null ? r.monto_detectado : 'null'}, ${Number(w.costo_total) || 0}, ${Number(w.pago_monto_total) || 0})\">Confirmar pago</button>\n        </div>` : `<p style=\"font-size:12px; color:var(--muted); margin:10px 0 0;\">🔒 Solo el usuario del laboratorio puede confirmar o rechazar este pago.</p>`}\n      </div>\n    `).join('') : ''}\n\n"
  ],
  [
   "// ---- Pago por transferencia reportado por un estudiante (Fase 2, sin\n// Mercado Pago todavia) -- la IA solo sugirio los datos al leer la foto, el\n// laboratorio siempre confirma a mano contra el banco antes de que cuente. ----\nfunction abrirConfirmarPagoReportadoLaboratorio(reporteId, trabajoId, montoSugerido) {\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Confirmar pago reportado</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">Verifica en el banco que el pago sí llegó y captura cómo quedó cubierto — puedes dividirlo entre varios métodos.</p>\n    <div id=\"lpr_metodos\">\n      ${(META.tipos_metodo_pago_laboratorio || ['efectivo','tarjeta_debito','tarjeta_credito','transferencia','otro']).map(m => `\n",
   "// ---- Pago por transferencia reportado por un estudiante (Fase 2, sin\n// Mercado Pago todavia) -- la IA solo sugirio los datos al leer la foto, el\n// laboratorio siempre confirma a mano contra el banco antes de que cuente. ----\nfunction abrirConfirmarPagoReportadoLaboratorio(reporteId, trabajoId, montoSugerido, costoTotal, yaPagado) {\n  const falta = Math.max(0, Math.round(((Number(costoTotal) || 0) - (Number(yaPagado) || 0)) * 100) / 100);\n  window._lprFalta = costoTotal != null ? falta : null;\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Confirmar pago reportado</h2>\n    ${costoTotal != null ? `\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 10px;\">\n        <div style=\"flex:1; min-width:120px; border:1px solid rgba(155,157,159,.4); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">TOTAL DEL TRABAJO</div><b style=\"font-size:18px;\">${_fmtC(costoTotal)}</b></div>\n        <div style=\"flex:1; min-width:120px; border:1px solid rgba(155,157,159,.4); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">YA PAGADO</div><b style=\"font-size:18px;\">${_fmtC(yaPagado || 0)}</b></div>\n        <div style=\"flex:1; min-width:120px; border:1px solid var(--copper); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">SE DEBE</div><b style=\"font-size:18px; color:var(--copper);\">${_fmtC(falta)}</b></div>\n      </div>` : ''}\n    <p style=\"font-size:12px; color:var(--muted);\">Verifica en el banco que el pago sí llegó y captura cómo quedó cubierto — puedes dividirlo entre varios métodos.</p>\n    <div id=\"lpr_metodos\">\n      ${(META.tipos_metodo_pago_laboratorio || ['efectivo','tarjeta_debito','tarjeta_credito','transferencia','otro']).map(m => `\n"
  ],
  [
   "        </div>\n      `).join('')}\n    </div>\n    <p style=\"font-size:13px; margin:8px 0;\">Total: <b id=\"lpr_total\">$0.00</b></p>\n    <button class=\"primary\" style=\"width:100%; margin-top:10px;\" onclick=\"confirmarPagoReportadoLaboratorioUI(${reporteId}, ${trabajoId}, this)\">Confirmar pago</button>\n    <div id=\"lprError\" class=\"error-msg\"></div>\n  `;\n",
   "        </div>\n      `).join('')}\n    </div>\n    <p style=\"font-size:13px; margin:8px 0;\">Total capturado: <b id=\"lpr_total\">$0.00</b> <span id=\"lpr_dif\" style=\"font-size:12px;\"></span></p>\n    <button class=\"primary\" style=\"width:100%; margin-top:10px;\" onclick=\"confirmarPagoReportadoLaboratorioUI(${reporteId}, ${trabajoId}, this)\">Confirmar pago</button>\n    <div id=\"lprError\" class=\"error-msg\"></div>\n  `;\n"
  ],
  [
   "  let total = 0;\n  document.querySelectorAll('.lpr_metodo_monto').forEach(inp => { if (!inp.disabled) total += parseFloat(inp.value) || 0; });\n  document.getElementById('lpr_total').textContent = _fmtC(total);\n}\n\nasync function confirmarPagoReportadoLaboratorioUI(reporteId, trabajoId, boton) {\n",
   "  let total = 0;\n  document.querySelectorAll('.lpr_metodo_monto').forEach(inp => { if (!inp.disabled) total += parseFloat(inp.value) || 0; });\n  document.getElementById('lpr_total').textContent = _fmtC(total);\n  const dif = document.getElementById('lpr_dif');\n  if (dif && window._lprFalta != null) {\n    const resta = Math.round((window._lprFalta - total) * 100) / 100;\n    dif.innerHTML = resta > 0 ? `<span style=\"color:var(--copper);\">· faltaría ${_fmtC(resta)}</span>`\n      : resta < 0 ? `<span style=\"color:#e6a23c;\">· ${_fmtC(-resta)} de más</span>` : '<span style=\"color:#4caf50;\">· queda cubierto ✔</span>';\n  }\n}\n\nasync function confirmarPagoReportadoLaboratorioUI(reporteId, trabajoId, boton) {\n"
  ],
  [
   "      return `\n        <div class=\"card\" style=\"margin-bottom:10px;\">\n          <b>${escapeHtml(w.solicitante_nombre)}</b>${w.matricula ? ` · ${escapeHtml(w.matricula)}` : ''}<br>\n          <span class=\"trabajo-folio\">${escapeHtml(w.folio)}</span> <span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${NOMBRES_ESTADO_LABORATORIO[w.estado]}</span><br>\n          ${w.es_mi_sucursal ? `\n            <p style=\"font-size:12px; margin:6px 0;\">${yaPagado ? '✅ Pagado' : '⚠️ Falta pago'} — ${listoParaEntregar ? 'Listo para entregar aquí' : 'Todavía no está listo para entregar'}</p>\n            ${listoParaEntregar && yaPagado ? `<button class=\"primary\" style=\"width:100%;\" onclick=\"cerrarModal(); abrirFirmarEntregaLaboratorio(${w.id});\">Entregar aquí</button>` : ''}\n",
   "      return `\n        <div class=\"card\" style=\"margin-bottom:10px;\">\n          <b>${escapeHtml(w.solicitante_nombre)}</b>${w.matricula ? ` · ${escapeHtml(w.matricula)}` : ''}<br>\n          <span class=\"trabajo-folio\">${escapeHtml(w.folio)}</span> <span class=\"badge ${COLOR_ESTADO_LABORATORIO[w.estado]}\">${lab_nombreEstado(w)}</span><br>\n          ${w.es_mi_sucursal ? `\n            <p style=\"font-size:12px; margin:6px 0;\">${yaPagado ? '✅ Pagado' : '⚠️ Falta pago'} — ${listoParaEntregar ? 'Listo para entregar aquí' : 'Todavía no está listo para entregar'}</p>\n            ${listoParaEntregar && yaPagado ? `<button class=\"primary\" style=\"width:100%;\" onclick=\"cerrarModal(); abrirFirmarEntregaLaboratorio(${w.id});\">Entregar aquí</button>` : ''}\n"
  ]
 ],
 "frontend/laboratorio_estudiantes.html": [
  [
   "  const NOMBRES_TIPO = { corona: 'Corona', implante: 'Implante', puente: 'Puente', carilla: 'Carilla', incrustacion: 'Incrustación', otro: 'Otro' };\n  const NOMBRES_MATERIAL = { zirconia: 'Zirconia', disilicato: 'Disilicato' };\n  const NOMBRES_ESTADO = {\n    recibido: 'Recibido — falta pago y firma', en_laboratorio: 'En laboratorio', modelado: 'Modelado / diseño',\n    aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)', maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad',\n    envio_sucursal: 'En camino a sucursal', listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n  };\n",
   "  const NOMBRES_TIPO = { corona: 'Corona', implante: 'Implante', puente: 'Puente', carilla: 'Carilla', incrustacion: 'Incrustación', otro: 'Otro' };\n  const NOMBRES_MATERIAL = { zirconia: 'Zirconia', disilicato: 'Disilicato' };\n  const NOMBRES_ESTADO = {\n    recibido: 'Registro pedido en app — falta pago', en_laboratorio: 'En laboratorio', modelado: 'Modelado / diseño',\n    aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)', maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad',\n    envio_sucursal: 'En camino a sucursal', listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n  };\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    if not os.path.exists("backend/correo.py"):
        print("Primero corre fix_laboratorio_estudiantes_v2.py (y luego este).")
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
