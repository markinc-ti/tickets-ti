# -*- coding: utf-8 -*-
"""
LABORATORIO: CANCELAR CON MOTIVO + CANCELACION AUTOMATICA A LOS 20 DIAS
1) Boton "Cancelar trabajo" en el detalle: pide el motivo (obligatorio) y
   cancela. Queda registrado quien, cuando, el motivo y en que estado estaba;
   en la bitacora y en el detalle ("Trabajo cancelado - Motivo..."). Al
   estudiante le llega el aviso con el motivo y el telefono de ayuda.
   El Laboratorio (y el admin) cancela en cualquier estado abierto; las
   sucursales, solo lo suyo mientras sigue en recepcion.
2) Automatico: los trabajos que siguen en recepcion SIN pago (ni transferencia
   por confirmar) con mas de 20 dias se cancelan solos (revisa cada hora, de 9
   a 20 h), con motivo, en la bitacora ("Sistema") y aviso al estudiante.
Correr DESPUES de los 3 de laboratorio anteriores (matricula, telefono, pago).
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_laboratorio_cancelar.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'sucursal';\n        -- Aviso automático al estudiante si a 1 día de pedir en la app no ha pagado (una sola vez).\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS aviso_sin_pago_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n",
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'sucursal';\n        -- Aviso automático al estudiante si a 1 día de pedir en la app no ha pagado (una sola vez).\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS aviso_sin_pago_en TEXT;\n        -- Cancelación con motivo (a mano) o automática (pedido de más de 20 días sin pago).\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS cancelado_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS cancelado_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS cancelado_motivo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS cancelado_automatico BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS estado_antes_cancelar TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n"
  ],
  [
   "        SELECT l.*, s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,\n               uc.nombre_completo AS creado_por_nombre, uc.username AS matricula, uc.rol AS creado_por_rol,\n               uc.telefono_whatsapp AS creado_por_telefono,\n               uel.nombre_completo AS entro_laboratorio_por_nombre,\n               urs.nombre_completo AS recibido_sucursal_por_nombre,\n               uent.nombre_completo AS entregado_por_nombre,\n",
   "        SELECT l.*, s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,\n               uc.nombre_completo AS creado_por_nombre, uc.username AS matricula, uc.rol AS creado_por_rol,\n               uc.telefono_whatsapp AS creado_por_telefono,\n               ucan.nombre_completo AS cancelado_por_nombre,\n               uel.nombre_completo AS entro_laboratorio_por_nombre,\n               urs.nombre_completo AS recibido_sucursal_por_nombre,\n               uent.nombre_completo AS entregado_por_nombre,\n"
  ],
  [
   "        LEFT JOIN users uel ON uel.id = l.entro_laboratorio_por_id\n        LEFT JOIN users urs ON urs.id = l.recibido_sucursal_por_id\n        LEFT JOIN users uent ON uent.id = l.entregado_por_id\n        JOIN users uc ON uc.id = l.creado_por_id\n    \"\"\"\n\n",
   "        LEFT JOIN users uel ON uel.id = l.entro_laboratorio_por_id\n        LEFT JOIN users urs ON urs.id = l.recibido_sucursal_por_id\n        LEFT JOIN users uent ON uent.id = l.entregado_por_id\n        LEFT JOIN users ucan ON ucan.id = l.cancelado_por_id\n        JOIN users uc ON uc.id = l.creado_por_id\n    \"\"\"\n\n"
  ],
  [
   "        elif f[\"vigencia_hasta\"] == hoy and f.get(\"vigencia_aviso_0\") != hoy:\n            resultado.append((f, 0))\n    return resultado\n\n\ndef pedidos_lab_sin_pago_para_aviso():\n",
   "        elif f[\"vigencia_hasta\"] == hoy and f.get(\"vigencia_aviso_0\") != hoy:\n            resultado.append((f, 0))\n    return resultado\n\n\ndef cancelar_trabajo_laboratorio(empresa_id, trabajo_id, motivo, usuario_id=None, automatico=False):\n    \"\"\"Cancela el trabajo guardando quién, cuándo, el motivo y en qué estado estaba.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    cur.execute(\"\"\"UPDATE trabajos_laboratorio SET estado_antes_cancelar = estado, estado = 'cancelado', actualizado_en = %s,\n                          cancelado_en = %s, cancelado_por_id = %s, cancelado_motivo = %s, cancelado_automatico = %s\n                   WHERE id = %s AND empresa_id = %s AND estado NOT IN ('entregado', 'cancelado')\"\"\",\n                (now, now, usuario_id, motivo, bool(automatico), trabajo_id, empresa_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef pedidos_lab_para_cancelar_automatico():\n    \"\"\"Trabajos que siguen en recepción (sin pago registrado ni transferencia por confirmar):\n    el llamador decide por antigüedad (creado_en).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT l.id, l.empresa_id, l.folio, l.creado_en, l.creado_por_id, l.paciente_nombre, u.rol AS creado_por_rol,\n                          u.nombre_completo, u.email\n                   FROM trabajos_laboratorio l JOIN users u ON u.id = l.creado_por_id\n                   WHERE l.estado = 'recibido' AND l.pago_registrado_en IS NULL\n                     AND NOT EXISTS (SELECT 1 FROM laboratorio_pagos_reportados r\n                                     WHERE r.trabajo_id = l.id AND r.estado = 'pendiente')\n                   ORDER BY l.id\"\"\")\n    filas = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return filas\n\n\ndef usuario_sistema_empresa(empresa_id):\n    \"\"\"Un administrador de la empresa, para firmar lo que hace el sistema solo (bitácora).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT id FROM users WHERE empresa_id = %s AND rol = 'admin' AND activo ORDER BY id LIMIT 1\", (empresa_id,))\n    r = cur.fetchone()\n    cur.close(); conn.close()\n    return r[\"id\"] if r else None\n\n\ndef pedidos_lab_sin_pago_para_aviso():\n"
  ]
 ],
 "backend/app.py": [
  [
   "\nclass CambioEstadoLaboratorio(BaseModel):\n    estado: str\n    # Solo al pasar a \"envio_sucursal\": a qué sucursal va, o \"escuela\".\n    destino_tipo: Optional[Literal[\"sucursal\", \"escuela\"]] = None\n    destino_sucursal_id: Optional[int] = None\n",
   "\nclass CambioEstadoLaboratorio(BaseModel):\n    estado: str\n    motivo: Optional[str] = Field(default=None, max_length=500)  # obligatorio al cancelar\n    # Solo al pasar a \"envio_sucursal\": a qué sucursal va, o \"escuela\".\n    destino_tipo: Optional[Literal[\"sucursal\", \"escuela\"]] = None\n    destino_sucursal_id: Optional[int] = None\n"
  ],
  [
   "    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\n@app.patch(\"/api/laboratorio/{trabajo_id}/estado\")\ndef api_cambiar_estado_laboratorio(trabajo_id: int, payload: CambioEstadoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    \"\"\"Mover el trabajo entre los pasos internos de fabricación — desde que\n",
   "    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\nclass CancelarLaboratorioIn(BaseModel):\n    motivo: str = Field(min_length=3, max_length=500)\n\n\ndef _cancelar_trabajo_lab(usuario, trabajo, motivo):\n    \"\"\"El Laboratorio (y el admin) cancela en cualquier estado abierto; las sucursales solo\n    lo que es de su sucursal y sigue en recepción (antes de entrar al laboratorio).\"\"\"\n    motivo = (motivo or \"\").strip()\n    if len(motivo) < 3:\n        raise HTTPException(status_code=400, detail=\"Escribe el motivo de la cancelación\")\n    if trabajo[\"estado\"] in (\"entregado\", \"cancelado\"):\n        raise HTTPException(status_code=400, detail=\"Este trabajo ya está cerrado\")\n    if not _es_usuario_laboratorio(usuario):\n        if trabajo[\"estado\"] != \"recibido\":\n            raise HTTPException(status_code=403, detail=\"Este trabajo ya entró al laboratorio: solo el Laboratorio lo puede cancelar\")\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n    db.cancelar_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo[\"id\"], motivo, usuario[\"id\"])\n    db.agregar_actualizacion_laboratorio(trabajo[\"id\"], usuario[\"id\"], f\"❌ Canceló el trabajo. Motivo: {motivo}\")\n    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo[\"id\"])\n\n\n@app.post(\"/api/laboratorio/{trabajo_id}/cancelar\")\ndef api_cancelar_trabajo_laboratorio(trabajo_id: int, payload: CancelarLaboratorioIn,\n                                     usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    return _cancelar_trabajo_lab(usuario, trabajo, payload.motivo)\n\n\n@app.patch(\"/api/laboratorio/{trabajo_id}/estado\")\ndef api_cambiar_estado_laboratorio(trabajo_id: int, payload: CambioEstadoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    \"\"\"Mover el trabajo entre los pasos internos de fabricación — desde que\n"
  ],
  [
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    destino = None\n    if payload.estado != \"cancelado\":\n        if trabajo[\"estado\"] not in (\"en_laboratorio\", \"maquila\", *ESTADOS_LABORATORIO_LIBRES) or trabajo[\"estado\"] == \"envio_sucursal\":\n",
   "    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    if payload.estado == \"cancelado\":\n        # Cancelar siempre pide motivo y queda registrado (mismo camino que /cancelar).\n        return _cancelar_trabajo_lab(usuario, trabajo, payload.motivo)\n    destino = None\n    if payload.estado != \"cancelado\":\n        if trabajo[\"estado\"] not in (\"en_laboratorio\", \"maquila\", *ESTADOS_LABORATORIO_LIBRES) or trabajo[\"estado\"] == \"envio_sucursal\":\n"
  ],
  [
   "        print(f\"[pago-lab] error revisando pedidos sin pago: {e}\")\n\n\n@app.on_event(\"startup\")\ndef iniciar_scheduler_vigencias():\n    if not APSCHEDULER_DISPONIBLE:\n",
   "        print(f\"[pago-lab] error revisando pedidos sin pago: {e}\")\n\n\nDIAS_CANCELAR_PEDIDO_LAB = 20\n\n\ndef _cancelar_pedidos_lab_viejos():\n    \"\"\"Cada hora (de 9 a 20 h): los trabajos que siguen en recepción sin pago (ni\n    transferencia por confirmar) y tienen más de 20 días se cancelan solos, con motivo,\n    en la bitácora y con aviso al estudiante.\"\"\"\n    from datetime import datetime as dt\n    try:\n        ahora = db.ahora()\n        if not (9 <= ahora.hour < 20):\n            return\n        for p in db.pedidos_lab_para_cancelar_automatico():\n            try:\n                creado = dt.fromisoformat(str(p[\"creado_en\"]))\n                if creado.tzinfo is None:\n                    creado = creado.replace(tzinfo=ahora.tzinfo)\n            except (TypeError, ValueError):\n                continue\n            if ahora - creado < timedelta(days=DIAS_CANCELAR_PEDIDO_LAB):\n                continue\n            motivo = (f\"Cancelado automáticamente: el pedido tenía más de {DIAS_CANCELAR_PEDIDO_LAB} días \"\n                      \"sin pago y no entró al laboratorio.\")\n            sistema = db.usuario_sistema_empresa(p[\"empresa_id\"]) or p[\"creado_por_id\"]\n            if not db.cancelar_trabajo_laboratorio(p[\"empresa_id\"], p[\"id\"], motivo, None, automatico=True):\n                continue\n            db.agregar_actualizacion_laboratorio(p[\"id\"], sistema, f\"🤖 {motivo}\")\n            if p.get(\"creado_por_rol\") == \"estudiante\":\n                titulo = f\"Tu pedido {p['folio']} fue cancelado\"\n                texto = (f\"Su pedido {p['folio']}\" + (f\" ({p['paciente_nombre']})\" if p.get(\"paciente_nombre\") else \"\")\n                         + f\" se canceló porque pasaron más de {DIAS_CANCELAR_PEDIDO_LAB} días sin pago. \"\n                         + \"Si todavía lo necesita, puede volver a pedirlo en la app. \" + TEXTO_AYUDA_PAGO_LAB)\n                t_act = db.obtener_trabajo_laboratorio(p[\"empresa_id\"], p[\"id\"])\n                if t_act:  # que el aviso de cambio de estado no se repita después\n                    db.marcar_push_trabajo_laboratorio(p[\"id\"], _firma_push_lab(t_act))\n                avisos.avisar_seguro([p[\"creado_por_id\"]], titulo, texto, modulo=\"laboratorio\", ref=p[\"id\"])\n                try:\n                    correo.enviar(p.get(\"email\"), titulo, texto + \"\\n\\nMarkinc Lab\")\n                except Exception as e:  # noqa: BLE001\n                    print(f\"[cancelar-lab] correo {p['folio']}: {e}\")\n            print(f\"[cancelar-lab] cancelado automático {p['folio']}\")\n    except Exception as e:\n        print(f\"[cancelar-lab] error: {e}\")\n\n\n@app.on_event(\"startup\")\ndef iniciar_scheduler_vigencias():\n    if not APSCHEDULER_DISPONIBLE:\n"
  ],
  [
   "                  run_date=db.ahora() + timedelta(minutes=2), id=\"vigencias_estudiantes_arranque\")\n    sched.add_job(_revisar_pedidos_lab_sin_pago, \"interval\", minutes=30, id=\"pedidos_lab_sin_pago\",\n                  next_run_time=db.ahora() + timedelta(minutes=3))\n    sched.start()\n\n\n",
   "                  run_date=db.ahora() + timedelta(minutes=2), id=\"vigencias_estudiantes_arranque\")\n    sched.add_job(_revisar_pedidos_lab_sin_pago, \"interval\", minutes=30, id=\"pedidos_lab_sin_pago\",\n                  next_run_time=db.ahora() + timedelta(minutes=3))\n    sched.add_job(_cancelar_pedidos_lab_viejos, \"interval\", minutes=60, id=\"cancelar_pedidos_lab_viejos\",\n                  next_run_time=db.ahora() + timedelta(minutes=5))\n    sched.start()\n\n\n"
  ],
  [
   "            texto = \"Aceptamos tu devolución: volvemos a trabajar tu pieza.\"\n        elif estado_antes == \"devolucion\" and estado == \"entregado\":\n            texto = \"Revisamos tu devolución y no procede\" + (f\": {trabajo['devolucion_respuesta']}\" if trabajo.get(\"devolucion_respuesta\") else \".\")\n        else:\n            texto = _TEXTO_ESTADO_LAB.get(estado, f\"Ahora está: {str(estado).replace('_', ' ')}.\")\n        avisos.avisar([estudiante_id], f\"🦷 {trabajo.get('folio', '')}\" + (f\" · {trabajo['paciente_nombre']}\" if trabajo.get(\"paciente_nombre\") else \"\"),\n",
   "            texto = \"Aceptamos tu devolución: volvemos a trabajar tu pieza.\"\n        elif estado_antes == \"devolucion\" and estado == \"entregado\":\n            texto = \"Revisamos tu devolución y no procede\" + (f\": {trabajo['devolucion_respuesta']}\" if trabajo.get(\"devolucion_respuesta\") else \".\")\n        elif estado == \"cancelado\":\n            texto = \"Tu trabajo fue cancelado\" + (f\". Motivo: {trabajo['cancelado_motivo']}\" if trabajo.get(\"cancelado_motivo\") else \".\")\n            texto += \" \" + TEXTO_AYUDA_PAGO_LAB\n        else:\n            texto = _TEXTO_ESTADO_LAB.get(estado, f\"Ahora está: {str(estado).replace('_', ' ')}.\")\n        avisos.avisar([estudiante_id], f\"🦷 {trabajo.get('folio', '')}\" + (f\" · {trabajo['paciente_nombre']}\" if trabajo.get(\"paciente_nombre\") else \"\"),\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      ${w.notas ? `<br>Notas: ${escapeHtml(w.notas)}` : ''}\n      ${!puedeEditarPiezas ? `<br><span style=\"color:var(--muted);\">Los datos de recepción ya quedaron bloqueados${esAdmin ? '' : ' (solo el administrador los puede corregir)'}.</span>` : ''}\n    </p>\n    ${lab_cajaFacturaMicrosip(w, esAdmin)}\n    ${w.firma_recepcion ? `\n      ${w.firma_recepcion === 'AUTO_FIRMA_PAGO_APP' ? `\n",
   "      ${w.notas ? `<br>Notas: ${escapeHtml(w.notas)}` : ''}\n      ${!puedeEditarPiezas ? `<br><span style=\"color:var(--muted);\">Los datos de recepción ya quedaron bloqueados${esAdmin ? '' : ' (solo el administrador los puede corregir)'}.</span>` : ''}\n    </p>\n    ${w.estado === 'cancelado' ? `\n      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:10px 12px; margin:8px 0 12px; background:rgba(216,25,47,.06);\">\n        <b>❌ Trabajo cancelado</b>${w.cancelado_automatico ? ' <span style=\"font-size:11px; color:var(--muted);\">(automático)</span>' : ''}<br>\n        <span style=\"font-size:13px;\">Motivo: ${escapeHtml(w.cancelado_motivo || '—')}</span><br>\n        <span style=\"font-size:12px; color:var(--muted);\">${w.cancelado_en ? escapeHtml(String(w.cancelado_en).replace('T', ' ').slice(0, 16)) : ''}${w.cancelado_por_nombre ? ' · ' + escapeHtml(w.cancelado_por_nombre) : (w.cancelado_automatico ? ' · Sistema' : '')}</span>\n      </div>` : ''}\n    ${lab_cajaFacturaMicrosip(w, esAdmin)}\n    ${w.firma_recepcion ? `\n      ${w.firma_recepcion === 'AUTO_FIRMA_PAGO_APP' ? `\n"
  ],
  [
   "        <button class=\"primary\" style=\"width:100%;\" onclick=\"cambiarEstadoLaboratorioUI(${w.id}, this, '${SIGUIENTE_ESTADO_LAB_JS[w.estado]}')\">➡️ Avanzar a: ${NOMBRES_ESTADO_LABORATORIO[SIGUIENTE_ESTADO_LAB_JS[w.estado]]}</button>`}\n      </div>\n    ` : ''}\n    ${['en_laboratorio','modelado','aprobar_diseno','maquila','maquillado','control_calidad'].includes(w.estado) && w.soy_laboratorio ? `\n      <button class=\"secondary\" style=\"margin-top:8px; font-size:12px;\" onclick=\"cambiarEstadoLaboratorioUI(${w.id}, this, 'cancelado')\">Cancelar trabajo</button>\n    ` : ''}\n\n    ${(w.estado === 'modelado' || w.estado === 'aprobar_diseno') ? (disenoActual && disenoActual.estado === 'pendiente' ? `\n",
   "        <button class=\"primary\" style=\"width:100%;\" onclick=\"cambiarEstadoLaboratorioUI(${w.id}, this, '${SIGUIENTE_ESTADO_LAB_JS[w.estado]}')\">➡️ Avanzar a: ${NOMBRES_ESTADO_LABORATORIO[SIGUIENTE_ESTADO_LAB_JS[w.estado]]}</button>`}\n      </div>\n    ` : ''}\n    ${!['entregado', 'cancelado'].includes(w.estado) && (w.soy_laboratorio || esAdmin || w.estado === 'recibido') ? `\n      <button class=\"secondary\" style=\"margin-top:8px; font-size:12px; color:var(--copper);\" onclick=\"abrirCancelarTrabajoLaboratorio(${w.id}, '${escapeHtml(w.folio)}')\">❌ Cancelar trabajo</button>\n    ` : ''}\n\n    ${(w.estado === 'modelado' || w.estado === 'aprobar_diseno') ? (disenoActual && disenoActual.estado === 'pendiente' ? `\n"
  ],
  [
   "  });\n}\n\nasync function cambiarEstadoLaboratorioUI(id, boton, estado) {\n  if (estado === 'cancelado' && !confirm('¿Cancelar este trabajo?')) return;\n  const cuerpo = { estado };\n  if (estado === 'envio_sucursal') Object.assign(cuerpo, lab_leerDestino('lab_destino_sel'));\n  await conBloqueoDeBoton(boton, async () => {\n",
   "  });\n}\n\nfunction abrirCancelarTrabajoLaboratorio(id, folio) {\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"abrirDetalleLaboratorio(${id})\">cerrar</button>\n    <h2>❌ Cancelar trabajo ${escapeHtml(folio)}</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">Queda registrado quién lo canceló, cuándo y el motivo. Al estudiante le llega el aviso con el motivo.</p>\n    <div class=\"field\"><label>Motivo de la cancelación *</label>\n      <textarea id=\"lab_cancel_motivo\" rows=\"3\" maxlength=\"500\" placeholder=\"ej. El estudiante ya no lo necesita / se duplicó el pedido\"></textarea></div>\n    <div style=\"display:flex; gap:8px;\">\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"abrirDetalleLaboratorio(${id})\">No, regresar</button>\n      <button class=\"danger\" style=\"flex:1;\" onclick=\"cancelarTrabajoLaboratorioUI(${id}, this)\">Cancelar trabajo</button>\n    </div>\n    <div id=\"labCancelError\" class=\"error-msg\"></div>`;\n  abrirModal();\n  setTimeout(() => { const t = document.getElementById('lab_cancel_motivo'); if (t) t.focus(); }, 50);\n}\n\nasync function cancelarTrabajoLaboratorioUI(id, boton) {\n  const motivo = (document.getElementById('lab_cancel_motivo').value || '').trim();\n  const err = document.getElementById('labCancelError');\n  if (motivo.length < 3) { err.textContent = 'Escribe el motivo de la cancelación'; return; }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api(`/api/laboratorio/${id}/cancelar`, { method: 'POST', body: JSON.stringify({ motivo }) });\n      mostrarExito('Trabajo cancelado');\n      await abrirDetalleLaboratorio(id);\n      await renderListaLaboratorio();\n    } catch (e) { err.textContent = e.message; }\n  });\n}\n\nasync function cambiarEstadoLaboratorioUI(id, boton, estado) {\n  if (estado === 'cancelado') return abrirCancelarTrabajoLaboratorio(id, '');\n  const cuerpo = { estado };\n  if (estado === 'envio_sucursal') Object.assign(cuerpo, lab_leerDestino('lab_destino_sel'));\n  await conBloqueoDeBoton(boton, async () => {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_laboratorio_cancelar.py")
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
