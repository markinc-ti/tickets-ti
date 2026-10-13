# -*- coding: utf-8 -*-
"""
Devolución de trabajos de laboratorio + tickets solo para sistemas.
  - Laboratorio: el estudiante (app) o el personal (web) puede DEVOLVER un
    trabajo listo o entregado que quedó mal (motivo + foto). Queda en
    "Devolución (por revisar)", se avisa al laboratorio y a la sucursal.
    El laboratorio la acepta (vuelve a "En laboratorio" y se rehace paso por
    paso) o dice que no procede (regresa a "Entregado" con la respuesta).
    El estudiante recibe aviso de lo que se decidió.
    Columnas nuevas: devolucion_motivo, devolucion_en, devolucion_respuesta,
    devoluciones en trabajos_laboratorio.
  - Tickets: solo admin y técnicos ven tickets de otros; cualquier otro rol
    (encargadas, instaladores, etc.) ve únicamente los que él levantó.
REQUIERE haber corrido antes fix_incidencias_rh_visibles.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    \"aprobar_diseno\": \"Aprobar diseño\", \"maquila\": \"Maquila (fresado)\",\n    \"maquillado\": \"Maquillado / acabado\", \"control_calidad\": \"Control de calidad\",\n    \"envio_sucursal\": \"Envío a sucursal\", \"listo_entrega\": \"Listo para entrega\",\n    \"entregado\": \"Entregado\", \"cancelado\": \"Cancelado\",\n}\nNOMBRES_METODO_PAGO_LABORATORIO = {\n    \"efectivo\": \"Efectivo\", \"tarjeta_debito\": \"Tarjeta de débito\", \"tarjeta_credito\": \"Tarjeta de crédito\",\n",
   "    \"aprobar_diseno\": \"Aprobar diseño\", \"maquila\": \"Maquila (fresado)\",\n    \"maquillado\": \"Maquillado / acabado\", \"control_calidad\": \"Control de calidad\",\n    \"envio_sucursal\": \"Envío a sucursal\", \"listo_entrega\": \"Listo para entrega\",\n    \"entregado\": \"Entregado\", \"cancelado\": \"Cancelado\", \"devolucion\": \"Devolución (por revisar)\",\n}\nNOMBRES_METODO_PAGO_LABORATORIO = {\n    \"efectivo\": \"Efectivo\", \"tarjeta_debito\": \"Tarjeta de débito\", \"tarjeta_credito\": \"Tarjeta de crédito\",\n"
  ],
  [
   "        if restriccion:\n            return ticket[\"categoria\"] == restriccion\n        return True\n    return True\n\n\n@app.get(\"/api/tickets\")\ndef api_listar_tickets(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,\n                        departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,\n                        tecnico_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_tickets)):\n    solicitante_id = usuario[\"id\"] if usuario[\"rol\"] == \"usuario\" else None\n    asignado_a_id = usuario[\"id\"] if usuario[\"rol\"] == \"tecnico\" else tecnico_id\n    if usuario[\"rol\"] == \"admin\" and usuario.get(\"restriccion_categoria\"):\n        categoria = usuario[\"restriccion_categoria\"]  # se impone, ignora lo que haya mandado el cliente\n",
   "        if restriccion:\n            return ticket[\"categoria\"] == restriccion\n        return True\n    if usuario[\"rol\"] == \"superadmin\":\n        return True\n    return ticket[\"solicitante_id\"] == usuario[\"id\"]\n\n\n@app.get(\"/api/tickets\")\ndef api_listar_tickets(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,\n                        departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,\n                        tecnico_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_tickets)):\n    # Solo sistemas (admin y técnicos) ve tickets de otros; cualquier otro rol\n    # (encargadas, instaladores, etc.) ve únicamente los que él levantó.\n    solicitante_id = usuario[\"id\"] if usuario[\"rol\"] not in (\"admin\", \"tecnico\", \"superadmin\") else None\n    asignado_a_id = usuario[\"id\"] if usuario[\"rol\"] == \"tecnico\" else tecnico_id\n    if usuario[\"rol\"] == \"admin\" and usuario.get(\"restriccion_categoria\"):\n        categoria = usuario[\"restriccion_categoria\"]  # se impone, ignora lo que haya mandado el cliente\n"
  ],
  [
   "    return db.listar_trabajos_laboratorio_de_usuario(usuario[\"empresa_id\"], usuario[\"id\"])\n\n\n@app.get(\"/api/laboratorio/mios/{trabajo_id}\")\ndef api_obtener_mi_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n",
   "    return db.listar_trabajos_laboratorio_de_usuario(usuario[\"empresa_id\"], usuario[\"id\"])\n\n\nclass DevolucionLaboratorioIn(BaseModel):\n    motivo: str = Field(min_length=3, max_length=2000)\n    foto_base64: Optional[str] = None\n\n\n@app.post(\"/api/laboratorio/mios/{trabajo_id}/devolver\")\ndef api_devolver_trabajo_laboratorio(trabajo_id: int, payload: DevolucionLaboratorioIn, usuario: dict = Depends(requiere_ver_laboratorio)):\n    \"\"\"El estudiante (o el personal, a su nombre) regresa un trabajo que\n    quedó mal: queda en \"Devolución\" para que el laboratorio la revise.\"\"\"\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if trabajo[\"estado\"] not in (\"entregado\", \"listo_entrega\"):\n        raise HTTPException(status_code=400, detail=\"Solo se puede devolver un trabajo ya terminado (listo o entregado)\")\n    if payload.foto_base64 and len(payload.foto_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"La foto pesa demasiado (máximo 5MB)\")\n    motivo = payload.motivo.strip()\n    db.registrar_devolucion_laboratorio(usuario[\"empresa_id\"], trabajo_id, motivo)\n    if payload.foto_base64:\n        db.agregar_evidencia_laboratorio(trabajo_id, _como_data_url(payload.foto_base64), \"devolucion.jpg\",\n                                         f\"Devolución: {motivo[:200]}\", usuario[\"id\"])\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"], f\"Devolvió el trabajo. Motivo: {motivo}\")\n    # Para que el aviso al estudiante al resolverla parta de \"devolución\".\n    try:\n        db.marcar_push_trabajo_laboratorio(trabajo_id, _firma_push_lab(db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)))\n    except Exception as e:\n        print(f\"[avisos] devolución {trabajo_id}: {e}\")\n    destinatarios = db.ids_usuarios_laboratorio(usuario[\"empresa_id\"])\n    if trabajo.get(\"entrega_sucursal_id\"):\n        destinatarios += db.ids_encargados_sucursal(usuario[\"empresa_id\"], trabajo[\"entrega_sucursal_id\"])\n    avisos.avisar_seguro(destinatarios, f\"↩️ Devolución · {trabajo.get('folio', '')}\",\n                         f\"{trabajo.get('solicitante_nombre', '')}: {motivo[:200]}\", modulo=\"laboratorio\", ref=trabajo_id,\n                         excluir=[usuario[\"id\"]])\n    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\nclass ResolverDevolucionIn(BaseModel):\n    acepta: bool\n    respuesta: Optional[str] = Field(default=None, max_length=2000)\n\n\n@app.post(\"/api/laboratorio/{trabajo_id}/devolucion\")\ndef api_resolver_devolucion_laboratorio(trabajo_id: int, payload: ResolverDevolucionIn, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    \"\"\"El laboratorio revisa la devolución: la acepta (vuelve a \"En\n    laboratorio\" para rehacerlo, otra vez paso por paso) o no procede\n    (regresa a \"Entregado\" con su respuesta).\"\"\"\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    if not _es_usuario_laboratorio(usuario):\n        raise HTTPException(status_code=403, detail=\"Solo el laboratorio revisa las devoluciones\")\n    if trabajo[\"estado\"] != \"devolucion\":\n        raise HTTPException(status_code=400, detail=\"Este trabajo no tiene una devolución pendiente\")\n    respuesta = _limpio(payload.respuesta)\n    if not payload.acepta and not respuesta:\n        raise HTTPException(status_code=400, detail=\"Escribe por qué no procede la devolución (se le avisa al estudiante)\")\n    db.resolver_devolucion_laboratorio(usuario[\"empresa_id\"], trabajo_id, payload.acepta, respuesta, usuario[\"id\"])\n    db.agregar_actualizacion_laboratorio(\n        trabajo_id, usuario[\"id\"],\n        (\"Aceptó la devolución — el trabajo vuelve al laboratorio para rehacerse.\" if payload.acepta\n         else \"La devolución no procede\") + (f\" ({respuesta})\" if respuesta else \"\"),\n    )\n    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\n@app.get(\"/api/laboratorio/mios/{trabajo_id}\")\ndef api_obtener_mi_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n"
  ],
  [
   "    \"listo_entrega\": \"¡Tu trabajo está listo para recoger!\",\n    \"entregado\": \"Tu trabajo fue entregado. ¡Gracias!\",\n    \"cancelado\": \"Tu trabajo fue cancelado.\",\n}\n\n\n",
   "    \"listo_entrega\": \"¡Tu trabajo está listo para recoger!\",\n    \"entregado\": \"Tu trabajo fue entregado. ¡Gracias!\",\n    \"cancelado\": \"Tu trabajo fue cancelado.\",\n    \"devolucion\": \"Recibimos tu devolución; el laboratorio la va a revisar.\",\n}\n\n\n"
  ],
  [
   "                     else f\"¡Tu trabajo está terminado! Va en camino a {destino}.\")\n        elif estado == \"listo_entrega\":\n            texto = f\"¡Tu trabajo ya está en {destino}! Pasa a recogerlo.\"\n        else:\n            texto = _TEXTO_ESTADO_LAB.get(estado, f\"Ahora está: {str(estado).replace('_', ' ')}.\")\n        avisos.avisar([estudiante_id], f\"🦷 {trabajo.get('folio', '')}\" + (f\" · {trabajo['paciente_nombre']}\" if trabajo.get(\"paciente_nombre\") else \"\"),\n",
   "                     else f\"¡Tu trabajo está terminado! Va en camino a {destino}.\")\n        elif estado == \"listo_entrega\":\n            texto = f\"¡Tu trabajo ya está en {destino}! Pasa a recogerlo.\"\n        elif estado_antes == \"devolucion\" and estado == \"en_laboratorio\":\n            texto = \"Aceptamos tu devolución: volvemos a trabajar tu pieza.\"\n        elif estado_antes == \"devolucion\" and estado == \"entregado\":\n            texto = \"Revisamos tu devolución y no procede\" + (f\": {trabajo['devolucion_respuesta']}\" if trabajo.get(\"devolucion_respuesta\") else \".\")\n        else:\n            texto = _TEXTO_ESTADO_LAB.get(estado, f\"Ahora está: {str(estado).replace('_', ' ')}.\")\n        avisos.avisar([estudiante_id], f\"🦷 {trabajo.get('folio', '')}\" + (f\" · {trabajo['paciente_nombre']}\" if trabajo.get(\"paciente_nombre\") else \"\"),\n"
  ]
 ],
 "backend/db.py": [
  [
   "    \"estado_laboratorio.listo_entrega\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Listo para entrega\"},\n    \"estado_laboratorio.entregado\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Entregado\"},\n    \"estado_laboratorio.cancelado\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Cancelado\"},\n}\n\n\n",
   "    \"estado_laboratorio.listo_entrega\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Listo para entrega\"},\n    \"estado_laboratorio.entregado\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Entregado\"},\n    \"estado_laboratorio.cancelado\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Cancelado\"},\n    \"estado_laboratorio.devolucion\": {\"grupo\": \"Estados de laboratorio\", \"default\": \"Devolución (por revisar)\"},\n}\n\n\n"
  ],
  [
   "]\nESTADOS_LABORATORIO = [\n    \"recibido\", \"en_laboratorio\", \"modelado\", \"aprobar_diseno\", \"maquila\", \"maquillado\", \"control_calidad\",\n    \"envio_sucursal\", \"listo_entrega\", \"entregado\", \"cancelado\",\n]\nTIPOS_SOLICITANTE_LABORATORIO = [\"estudiante\", \"doctor\"]\nTIPOS_TRABAJO_LABORATORIO = [\"corona\", \"implante\", \"puente\", \"carilla\", \"incrustacion\", \"otro\"]\n",
   "]\nESTADOS_LABORATORIO = [\n    \"recibido\", \"en_laboratorio\", \"modelado\", \"aprobar_diseno\", \"maquila\", \"maquillado\", \"control_calidad\",\n    \"envio_sucursal\", \"listo_entrega\", \"entregado\", \"cancelado\", \"devolucion\",\n]\nTIPOS_SOLICITANTE_LABORATORIO = [\"estudiante\", \"doctor\"]\nTIPOS_TRABAJO_LABORATORIO = [\"corona\", \"implante\", \"puente\", \"carilla\", \"incrustacion\", \"otro\"]\n"
  ],
  [
   "           AND NOT EXISTS (SELECT 1 FROM users e JOIN users u ON u.id = i.usuario_id\n                            WHERE e.empresa_id = i.empresa_id AND e.rol = 'encargado_sucursal' AND e.activo = TRUE\n                              AND e.sucursal_id = u.sucursal_id AND u.sucursal_id IS NOT NULL AND e.id <> u.id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_tipo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_sucursal_id INTEGER;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n",
   "           AND NOT EXISTS (SELECT 1 FROM users e JOIN users u ON u.id = i.usuario_id\n                            WHERE e.empresa_id = i.empresa_id AND e.rol = 'encargado_sucursal' AND e.activo = TRUE\n                              AND e.sucursal_id = u.sucursal_id AND u.sucursal_id IS NOT NULL AND e.id <> u.id);\n        -- Devolución: el estudiante regresa un trabajo que quedó mal.\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS devolucion_motivo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS devolucion_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS devolucion_respuesta TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS devoluciones INTEGER NOT NULL DEFAULT 0;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_tipo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_sucursal_id INTEGER;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n"
  ],
  [
   "    cur.close(); conn.close()\n\n\ndef ids_encargados_sucursal(empresa_id, sucursal_id):\n    \"\"\"Quién recibe y entrega en esa sucursal: sus encargados y quien tenga\n    el privilegio de entrega de laboratorio ahí. Si no hay nadie así, todo el\n",
   "    cur.close(); conn.close()\n\n\ndef registrar_devolucion_laboratorio(empresa_id, trabajo_id, motivo):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    cur.execute(\"\"\"UPDATE trabajos_laboratorio SET estado = 'devolucion', devolucion_motivo = %s, devolucion_en = %s,\n                          devolucion_respuesta = NULL, devoluciones = devoluciones + 1, actualizado_en = %s\n                   WHERE id = %s AND empresa_id = %s\"\"\", (motivo, now, now, trabajo_id, empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef resolver_devolucion_laboratorio(empresa_id, trabajo_id, acepta, respuesta, usuario_id):\n    \"\"\"Acepta → vuelve a 'en_laboratorio' para rehacerlo (diseño otra vez).\n    Rechaza → regresa a 'entregado' con la respuesta del laboratorio.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    if acepta:\n        cur.execute(\"\"\"UPDATE trabajos_laboratorio SET estado = 'en_laboratorio', devolucion_respuesta = %s,\n                              omite_aprobacion_diseno = FALSE, entro_laboratorio_en = %s, entro_laboratorio_por_id = %s,\n                              actualizado_en = %s\n                       WHERE id = %s AND empresa_id = %s AND estado = 'devolucion'\"\"\",\n                    (respuesta, now, usuario_id, now, trabajo_id, empresa_id))\n    else:\n        cur.execute(\"\"\"UPDATE trabajos_laboratorio SET estado = 'entregado', devolucion_respuesta = %s, actualizado_en = %s\n                       WHERE id = %s AND empresa_id = %s AND estado = 'devolucion'\"\"\",\n                    (respuesta, now, trabajo_id, empresa_id))\n    ok = cur.rowcount > 0\n    conn.commit()\n    cur.close(); conn.close()\n    return ok\n\n\ndef ids_encargados_sucursal(empresa_id, sucursal_id):\n    \"\"\"Quién recibe y entrega en esa sucursal: sus encargados y quien tenga\n    el privilegio de entrega de laboratorio ahí. Si no hay nadie así, todo el\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  recibido: 'Recibido en sucursal', en_laboratorio: 'Entró a laboratorio', modelado: 'Modelado / diseño',\n  aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)',\n  maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad', envio_sucursal: 'Envío a sucursal',\n  listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n};\nconst COLOR_ESTADO_LABORATORIO = {\n  recibido: 'urgente', en_laboratorio: 'alta', modelado: 'alta', maquila: 'alta', maquillado: 'media', control_calidad: 'media',\n  envio_sucursal: 'media', listo_entrega: 'baja', entregado: 'baja', cancelado: 'baja',\n};\nconst NOMBRES_TIPO_SOLICITANTE_LAB = { estudiante: 'Estudiante', doctor: 'Doctor' };\n\n",
   "  recibido: 'Recibido en sucursal', en_laboratorio: 'Entró a laboratorio', modelado: 'Modelado / diseño',\n  aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)',\n  maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad', envio_sucursal: 'Envío a sucursal',\n  listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado', devolucion: '↩️ Devolución (por revisar)',\n};\nconst COLOR_ESTADO_LABORATORIO = {\n  recibido: 'urgente', en_laboratorio: 'alta', modelado: 'alta', maquila: 'alta', maquillado: 'media', control_calidad: 'media',\n  envio_sucursal: 'media', listo_entrega: 'baja', entregado: 'baja', cancelado: 'baja', devolucion: 'urgente',\n};\nconst NOMBRES_TIPO_SOLICITANTE_LAB = { estudiante: 'Estudiante', doctor: 'Doctor' };\n\n"
  ],
  [
   "      </div>\n    `) : ''}\n\n    ${w.estado === 'envio_sucursal' ? `\n      <p style=\"font-size:13px; margin-top:12px;\">🚚 ${w.destino_tipo === 'escuela' ? 'Se llevará a la escuela — se entrega ahí con la firma del estudiante.' : `En camino a <b>${escapeHtml(w.destino_texto || 'la sucursal')}</b> — la encargada confirma cuando llegue y lo entrega con la firma del estudiante.`}</p>\n      ${w.soy_laboratorio ? `\n",
   "      </div>\n    `) : ''}\n\n    ${w.estado === 'devolucion' ? `\n      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;\">\n        <p style=\"font-size:13px; margin:0 0 6px;\">↩️ <b>El estudiante devolvió este trabajo</b>${w.devolucion_en ? ` el ${escapeHtml(w.devolucion_en.slice(0,10))}` : ''}${w.devoluciones > 1 ? ` (devolución #${w.devoluciones})` : ''}.</p>\n        <p style=\"font-size:13px; margin:0 0 8px;\"><b>Motivo:</b> ${escapeHtml(w.devolucion_motivo || '—')}</p>\n        <p style=\"font-size:11px; color:var(--muted); margin:0 0 8px;\">Si mandó foto, está en \"Evidencia fotográfica\".</p>\n        ${w.soy_laboratorio ? `\n          <div class=\"field\"><label>Respuesta (obligatoria si no procede)</label><input id=\"lab_devol_resp\" placeholder=\"ej. Se rehace la corona con el color correcto\" /></div>\n          <div style=\"display:flex; gap:8px;\">\n            <button class=\"secondary\" style=\"flex:1;\" onclick=\"resolverDevolucionLaboratorioUI(${w.id}, false, this)\">No procede</button>\n            <button class=\"primary\" style=\"flex:2;\" onclick=\"resolverDevolucionLaboratorioUI(${w.id}, true, this)\">Aceptar y rehacer (vuelve a laboratorio)</button>\n          </div>\n        ` : `<p style=\"font-size:12px; color:var(--muted); margin:0;\">El laboratorio la está revisando.</p>`}\n      </div>\n    ` : ''}\n    ${(w.estado === 'entregado' || w.estado === 'listo_entrega') && w.devolucion_respuesta ? `<p style=\"font-size:12px; color:var(--muted); margin-top:10px;\">↩️ Última devolución: ${escapeHtml(w.devolucion_motivo || '')} — respuesta: ${escapeHtml(w.devolucion_respuesta)}</p>` : ''}\n    ${['entregado', 'listo_entrega'].includes(w.estado) ? `<button class=\"secondary\" style=\"margin-top:10px; font-size:12px;\" onclick=\"abrirDevolverTrabajoLaboratorio(${w.id})\">↩️ Registrar devolución (quedó mal)</button>` : ''}\n    ${w.estado === 'envio_sucursal' ? `\n      <p style=\"font-size:13px; margin-top:12px;\">🚚 ${w.destino_tipo === 'escuela' ? 'Se llevará a la escuela — se entrega ahí con la firma del estudiante.' : `En camino a <b>${escapeHtml(w.destino_texto || 'la sucursal')}</b> — la encargada confirma cuando llegue y lo entrega con la firma del estudiante.`}</p>\n      ${w.soy_laboratorio ? `\n"
  ],
  [
   "      await renderListaLaboratorio();\n    } catch (e) {\n      document.getElementById('labDetalleError').textContent = e.message;\n    }\n  });\n}\n\nfunction lab_selectDestino(idSel, w) {\n",
   "      await renderListaLaboratorio();\n    } catch (e) {\n      document.getElementById('labDetalleError').textContent = e.message;\n    }\n  });\n}\n\nasync function resolverDevolucionLaboratorioUI(id, acepta, boton) {\n  const respuesta = (document.getElementById('lab_devol_resp').value || '').trim() || null;\n  if (!acepta && !respuesta) { document.getElementById('labDetalleError').textContent = 'Escribe por qué no procede (se le avisa al estudiante)'; return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api(`/api/laboratorio/${id}/devolucion`, { method: 'POST', body: JSON.stringify({ acepta, respuesta }) });\n      mostrarExito(acepta ? 'Devolución aceptada — el trabajo regresó a laboratorio' : 'Registrado: la devolución no procede');\n      await abrirDetalleLaboratorio(id);\n      await renderListaLaboratorio();\n    } catch (e) { document.getElementById('labDetalleError').textContent = e.message; }\n  });\n}\n\nfunction abrirDevolverTrabajoLaboratorio(id) {\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"abrirDetalleLaboratorio(${id})\">cerrar</button>\n    <h2>↩️ Devolución</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">Para cuando el estudiante regresa el trabajo porque quedó mal. El laboratorio lo revisa y decide si se rehace.</p>\n    <div class=\"field\"><label>¿Qué quedó mal? *</label><textarea id=\"lab_devol_motivo\" rows=\"3\"></textarea></div>\n    <div class=\"field\"><label>Foto (opcional)</label><input type=\"file\" id=\"lab_devol_foto\" accept=\"image/*\" /></div>\n    <div id=\"labDevolError\" class=\"error-msg\"></div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"registrarDevolucionLaboratorioUI(${id}, this)\">Registrar devolución</button>\n  `;\n  abrirModal(true);\n}\n\nasync function registrarDevolucionLaboratorioUI(id, boton) {\n  const motivo = document.getElementById('lab_devol_motivo').value.trim();\n  if (motivo.length < 3) { document.getElementById('labDevolError').textContent = 'Escribe qué quedó mal'; return; }\n  const archivo = document.getElementById('lab_devol_foto').files[0];\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const cuerpo = { motivo };\n      if (archivo) cuerpo.foto_base64 = await leerArchivoComoBase64(archivo);\n      await api(`/api/laboratorio/mios/${id}/devolver`, { method: 'POST', body: JSON.stringify(cuerpo) });\n      mostrarExito('Devolución registrada — se avisó al laboratorio');\n      await abrirDetalleLaboratorio(id);\n      await renderListaLaboratorio();\n    } catch (e) { document.getElementById('labDevolError').textContent = e.message; }\n  });\n}\n\nfunction lab_selectDestino(idSel, w) {\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "estado IN ('pendiente', 'pendiente_encargado')" not in f.read():
            print("Primero corre fix_incidencias_rh_visibles.py (y los anteriores), y luego este.")
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
