#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RH — Incidencias: ahora la ENCARGADA DE SUCURSAL decide (aceptar o
rechazar), y Recursos Humanos solo lo ve informativamente. También se
quita la oferta automática de convertir horas acumuladas en un día sin
goce de sueldo.

Pedido de David (textual): "el empleado crea una incidencia -- no importa
el motivo ni el tipo -- cuando el empleado genera una incidencia la
encargada de sucursal que le corresponda según su sucursal ella debe
autorizar y le debe aparecer si la acepta o no y motivo por qué no. Una
vez aceptada o rechazada le debe aparecer a RH, la cual RH debe solo
tener informativo la información."

Antes: la encargada de sucursal solo podía FIRMAR PARA ACEPTAR una
incidencia -- eso la pasaba a la bandeja de RH, y RH era quien de verdad
decidía (aprobar/rechazar/marcar como pagada). No existía forma de que
la encargada rechazara.

Ahora: cuando la incidencia SÍ tiene una encargada de sucursal asignada,
su decisión (aceptar con firma, o rechazar con motivo) es LA DECISIÓN
FINAL -- la incidencia nunca vuelve a pasar a 'pendiente' para que RH la
apruebe de nuevo. RH la ve en su lista con el estado final, quién la
resolvió y el motivo, pero SIN botones de aprobar/rechazar/pagar (esos
botones, en el código que ya existía, solo aparecían cuando el estado
era 'pendiente' -- por eso no hizo falta tocar la pantalla de RH: con
este cambio esas incidencias ya nunca llegan a ese estado).

Cuando la sucursal del empleado NO tiene ninguna encargada asignada
(esto ya existía así, confirmado con David que se queda igual), la
incidencia sigue naciendo directo en 'pendiente' y ahí SÍ la resuelve RH
como hasta ahora -- para que nunca se quede atorada sin que nadie la
pueda mover.

Aparte, confirmado con David: se quita la oferta automática de "ya se te
juntaron 8 horas, ¿las quieres convertir en un día sin goce de sueldo?"
-- las horas ahora solo se van acumulando, sin generar ninguna
propuesta. (El mecanismo para responder una propuesta YA existente se
deja tal cual, por si algún empleado todavía tiene una pendiente de
antes de este cambio -- nada más se apaga la generación de nuevas.)

Qué toca:
1. backend/db.py:
   - aceptar_incidencia_encargado(): ahora pone estado='aprobada'
     directo (antes ponía 'pendiente') y aplica los mismos efectos que
     ya existían al aprobar (movimiento de horas si es día sin goce).
   - rechazar_incidencia_encargado() [NUEVO]: mismo mecanismo pero
     estado='rechazada', con motivo, sin pedir firma.
   - _aplicar_efectos_incidencia_aprobada() [NUEVO]: el bloque de
     efectos que antes vivía dentro de resolver_incidencia_rh, ahora
     factorizado para poder llamarlo también desde el aceptar de la
     encargada.
   - resolver_incidencia_rh(): sigue igual para RH (solo aplica de
     verdad cuando la incidencia está en 'pendiente', que ahora
     únicamente pasa cuando no hay encargada asignada).
   - registrar_movimiento_horas_rh(): ya no llama a
     _ofrecer_conversion_dia_sin_goce() -- se quita la oferta
     automática.
2. backend/app.py:
   - api_aceptar_incidencia_encargado(): ahora también manda la
     notificación de WhatsApp (antes solo lo hacía cuando RH resolvía),
     porque su aceptación ya es la decisión final.
   - api_rechazar_incidencia_encargado() [NUEVO]: POST
     /api/rh/incidencias/{id}/rechazar-encargado, mismo permiso que
     aceptar (requiere_encargado_sucursal), pide {"motivo": "..."}.
3. frontend/index.html:
   - El modal de la encargada ("Aceptar incidencia") ahora se llama
     "Revisar incidencia", explica que su decisión es final, y agrega
     un botón "No aceptar -- rechazar con motivo" que abre un campo de
     texto y un botón de confirmar (sin firma).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_incidencias_decide_encargada.py
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        # 1) aceptar_incidencia_encargado ahora es decisión final +
        #    rechazar_incidencia_encargado nuevo.
        [
            '''def aceptar_incidencia_encargado(empresa_id, incidencia_id, encargado_id, firma_base64):
    """El encargado de sucursal firma para aceptar la incidencia — pasa a
    'pendiente' para que ahora sí la vea RH. Regresa False si no estaba en el
    estado correcto (ya se adelantaron, o ya la resolvió alguien más)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE incidencias_rh SET estado = 'pendiente', firma_encargado_base64 = %s,
                                      firma_encargado_en = %s, firma_encargado_por_id = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente_encargado'""",
        (firma_base64, now, encargado_id, incidencia_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


''',
            '''def aceptar_incidencia_encargado(empresa_id, incidencia_id, encargado_id, firma_base64):
    """La encargada de sucursal firma para ACEPTAR la incidencia de alguien de
    su sucursal -- esta es la decisión FINAL (ya no pasa por RH para que la
    apruebe de nuevo; RH solo la ve informativamente después). Regresa False
    si no estaba en el estado correcto (ya se adelantaron, o ya se resolvió)."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE incidencias_rh SET estado = 'aprobada', firma_encargado_base64 = %s,
                                      firma_encargado_en = %s, firma_encargado_por_id = %s,
                                      resuelto_por_id = %s, resuelto_en = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente_encargado'""",
        (firma_base64, now, encargado_id, encargado_id, now, incidencia_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    if filas > 0:
        _aplicar_efectos_incidencia_aprobada(empresa_id, incidencia_id, encargado_id)
    return filas > 0


def rechazar_incidencia_encargado(empresa_id, incidencia_id, encargado_id, motivo):
    """La encargada de sucursal RECHAZA la incidencia de alguien de su
    sucursal, con el motivo -- también es decisión FINAL, no pasa por RH.
    A diferencia de aceptar, no pide firma."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute(
        """UPDATE incidencias_rh SET estado = 'rechazada', respuesta_admin = %s,
                                      resuelto_por_id = %s, resuelto_en = %s
           WHERE id = %s AND empresa_id = %s AND estado = 'pendiente_encargado'""",
        (motivo, encargado_id, now, incidencia_id, empresa_id),
    )
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    return filas > 0


''',
        ],
        # 2) resolver_incidencia_rh: se factoriza el bloque de efectos a
        #    _aplicar_efectos_incidencia_aprobada() para reusarlo desde el
        #    aceptar de la encargada.
        [
            '''def resolver_incidencia_rh(empresa_id, incidencia_id, admin_id, estado, respuesta_admin=None):
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE incidencias_rh
        SET estado = %s, respuesta_admin = %s, resuelto_por_id = %s, resuelto_en = %s
        WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'
    """, (estado, respuesta_admin, admin_id, now, incidencia_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()

    if filas > 0 and estado == "aprobada":
        incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)
        es_conversion_automatica = incidencia and incidencia.get("motivo") and incidencia["motivo"].startswith("Generado automáticamente")
        if incidencia and incidencia["tipo"] == "dia_libre_sin_goce" and incidencia.get("horas"):
            if es_conversion_automatica:
                # Este NO es un permiso pedido de más — es la conversión de horas
                # que YA debía, que el propio empleado aceptó y la encargada ya
                # autorizó. Aquí se registra como PAGO (para que baje su adeudo),
                # nunca como un adeudo nuevo — si no, se le duplicaría la deuda.
                registrar_movimiento_horas_rh(
                    empresa_id, incidencia["usuario_id"], "pago", incidencia["horas"],
                    notas=f"Día sin goce de sueldo #{incidencia_id} — aceptado por el empleado y autorizado por su encargada.",
                    incidencia_id=incidencia_id, registrado_por_id=admin_id,
                )
            else:
                # Un permiso SIN GOCE DE SUELDO normal, pedido por la persona — si
                # se pidió por horas, genera el adeudo correspondiente.
                registrar_movimiento_horas_rh(
                    empresa_id, incidencia["usuario_id"], "debe", incidencia["horas"],
                    notas=f"Generado automáticamente al aprobar la incidencia #{incidencia_id}",
                    incidencia_id=incidencia_id, registrado_por_id=admin_id,
                )
    return filas > 0''',
            '''def _aplicar_efectos_incidencia_aprobada(empresa_id, incidencia_id, resuelto_por_id):
    """Efectos que ya existían al APROBAR una incidencia tipo
    dia_libre_sin_goce (mueve horas) -- factorizado aparte para poder
    llamarlo tanto desde resolver_incidencia_rh (RH, cuando la persona no
    tiene encargada de sucursal asignada) como desde
    aceptar_incidencia_encargado (la encargada, que ahora decide directo
    sin pasar por RH)."""
    incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)
    es_conversion_automatica = incidencia and incidencia.get("motivo") and incidencia["motivo"].startswith("Generado automáticamente")
    if incidencia and incidencia["tipo"] == "dia_libre_sin_goce" and incidencia.get("horas"):
        if es_conversion_automatica:
            # Este NO es un permiso pedido de más — es la conversión de horas
            # que YA debía, que el propio empleado aceptó. Aquí se registra
            # como PAGO (para que baje su adeudo), nunca como un adeudo
            # nuevo — si no, se le duplicaría la deuda.
            registrar_movimiento_horas_rh(
                empresa_id, incidencia["usuario_id"], "pago", incidencia["horas"],
                notas=f"Día sin goce de sueldo #{incidencia_id} — aceptado por el empleado y autorizado.",
                incidencia_id=incidencia_id, registrado_por_id=resuelto_por_id,
            )
        else:
            # Un permiso SIN GOCE DE SUELDO normal, pedido por la persona — si
            # se pidió por horas, genera el adeudo correspondiente.
            registrar_movimiento_horas_rh(
                empresa_id, incidencia["usuario_id"], "debe", incidencia["horas"],
                notas=f"Generado automáticamente al aprobar la incidencia #{incidencia_id}",
                incidencia_id=incidencia_id, registrado_por_id=resuelto_por_id,
            )


def resolver_incidencia_rh(empresa_id, incidencia_id, admin_id, estado, respuesta_admin=None):
    """Esto lo usa RH -- con el cambio de que ahora decide la encargada de
    sucursal, en la práctica esto solo aplica de verdad cuando la persona NO
    tiene una encargada asignada (ahí la incidencia nace directo en
    'pendiente'). Si ya la decidió una encargada, esta incidencia nunca
    llega a 'pendiente', así que este UPDATE no encuentra nada que
    actualizar (filas = 0) y no pasa nada -- no hace falta bloquear nada
    aparte."""
    conn = get_connection()
    cur = conn.cursor()
    now = ahora().isoformat(timespec="seconds")
    cur.execute("""
        UPDATE incidencias_rh
        SET estado = %s, respuesta_admin = %s, resuelto_por_id = %s, resuelto_en = %s
        WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'
    """, (estado, respuesta_admin, admin_id, now, incidencia_id, empresa_id))
    filas = cur.rowcount
    conn.commit()
    cur.close(); conn.close()

    if filas > 0 and estado == "aprobada":
        _aplicar_efectos_incidencia_aprobada(empresa_id, incidencia_id, admin_id)
    return filas > 0''',
        ],
        # 3) Se quita la oferta automática de convertir horas acumuladas en
        #    un día sin goce de sueldo.
        [
            '''    movimiento_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    if tipo == "debe" and estado == "aprobado":
        # Cada vez que se agrega (o se aprueba) un adeudo, revisamos si ya se
        # juntaron 8 horas o más sin pagar — si es así, se le OFRECE al
        # empleado convertirlo en un día sin goce (ver la función de abajo;
        # ya no se hace solo, necesita que el empleado acepte primero).
        _ofrecer_conversion_dia_sin_goce(empresa_id, usuario_id)
    return movimiento_id''',
            '''    movimiento_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    # Antes, cada vez que se juntaban 8+ horas a deber sin pagar, se le
    # OFRECÍA al empleado convertirlas en un día sin goce de sueldo. David
    # pidió quitar esa oferta automática -- las horas ahora solo se
    # acumulan, sin generar ninguna propuesta.
    return movimiento_id''',
        ],
    ],
    'backend/app.py': [
        [
            '''@app.post("/api/rh/incidencias/{incidencia_id}/aceptar-encargado")
def api_aceptar_incidencia_encargado(incidencia_id: int, payload: FirmaAceptacionEncargado, usuario: dict = Depends(requiere_encargado_sucursal)):
    """El encargado de sucursal firma para aceptar la incidencia de alguien de
    SU sucursal — recién ahí pasa a la bandeja de Recursos Humanos."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
        raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if not db.aceptar_incidencia_encargado(usuario["empresa_id"], incidencia_id, usuario["id"], payload.firma_base64):
        raise HTTPException(status_code=400, detail="Esta incidencia ya no está esperando tu firma (puede que ya se haya aceptado)")
    return {"ok": True}
''',
            '''@app.post("/api/rh/incidencias/{incidencia_id}/aceptar-encargado")
def api_aceptar_incidencia_encargado(incidencia_id: int, payload: FirmaAceptacionEncargado, usuario: dict = Depends(requiere_encargado_sucursal)):
    """La encargada de sucursal firma para ACEPTAR (aprobar) la incidencia de
    alguien de SU sucursal — esta es la decisión final, ya no pasa por RH
    para que la vuelva a aprobar (RH solo la ve informativamente después)."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
        raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if not db.aceptar_incidencia_encargado(usuario["empresa_id"], incidencia_id, usuario["id"], payload.firma_base64):
        raise HTTPException(status_code=400, detail="Esta incidencia ya no está esperando tu firma (puede que ya se haya resuelto)")
    incidencia_resuelta = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    notifications.notificar_incidencia_rh_resuelta(
        usuario["empresa_id"], {"telefono_whatsapp": incidencia_resuelta.get("usuario_telefono")}, incidencia_resuelta,
    )
    return {"ok": True}


class RechazoIncidenciaEncargado(BaseModel):
    motivo: str = Field(min_length=1)


@app.post("/api/rh/incidencias/{incidencia_id}/rechazar-encargado")
def api_rechazar_incidencia_encargado(incidencia_id: int, payload: RechazoIncidenciaEncargado, usuario: dict = Depends(requiere_encargado_sucursal)):
    """La encargada de sucursal RECHAZA la incidencia de alguien de SU
    sucursal, con el motivo — también es decisión final, no pasa por RH.
    A diferencia de aceptar, no pide firma."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
        raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
    if not db.rechazar_incidencia_encargado(usuario["empresa_id"], incidencia_id, usuario["id"], payload.motivo.strip()):
        raise HTTPException(status_code=400, detail="Esta incidencia ya no está esperando tu respuesta (puede que ya se haya resuelto)")
    incidencia_resuelta = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    notifications.notificar_incidencia_rh_resuelta(
        usuario["empresa_id"], {"telefono_whatsapp": incidencia_resuelta.get("usuario_telefono")}, incidencia_resuelta,
    )
    return {"ok": True}
''',
        ],
    ],
    'frontend/index.html': [
        [
            '''function abrirAceptarIncidenciaEncargado(incidenciaId) {
  document.getElementById('modalContent').innerHTML = '<p style="color:var(--muted); font-size:13px;">Cargando…</p>';
  abrirModal();
  api(`/api/rh/incidencias/${incidenciaId}`).then(i => {
    document.getElementById('modalContent').innerHTML = `
      <button class="close-btn" onclick="cerrarModal()">cerrar</button>
      <h2>Aceptar incidencia</h2>
      <table class="users" style="margin-bottom:14px;">
        <tr><td><b>Persona</b></td><td>${escapeHtml(i.usuario_nombre)}${i.usuario_puesto ? ` — ${escapeHtml(i.usuario_puesto)}` : ''}</td></tr>
        <tr><td><b>Tipo</b></td><td>${NOMBRES_TIPO_INCIDENCIA_RH[i.tipo] || i.tipo}</td></tr>
        <tr><td><b>Fecha(s)</b></td><td>${i.fecha_inicio.slice(0,10)}${i.fecha_fin && i.fecha_fin.slice(0,10) !== i.fecha_inicio.slice(0,10) ? ' al ' + i.fecha_fin.slice(0,10) : ''}</td></tr>
        ${i.horas ? `<tr><td><b>Horas</b></td><td>${formatearHoras(i.horas)}</td></tr>` : ''}
        <tr><td><b>Motivo</b></td><td>${i.motivo ? escapeHtml(i.motivo) : '—'}</td></tr>
      </table>
      ${i.foto_base64 ? `<img src="${i.foto_base64}" style="max-width:100%; border-radius:4px; margin-bottom:14px;" />` : ''}
      <p style="font-size:12px; color:var(--muted); margin-bottom:10px;">
        Al firmar, confirmas que ya revisaste esta incidencia de tu sucursal — pasa a Recursos Humanos para la decisión final (aprobar o rechazar).
      </p>
      <label style="font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;">Tu firma</label>
      <canvas id="firma_encargado_canvas" width="500" height="140" style="width:100%; height:140px; background:var(--substrate); border:1px solid rgba(155,157,159,0.3); touch-action:none; cursor:crosshair;"></canvas>
      <div style="display:flex; gap:8px; margin: 8px 0 14px;">
        <button class="secondary" style="flex:1;" onclick="limpiarFirmaCanvas('firma_encargado_canvas')">Limpiar firma</button>
      </div>
      <button class="primary" style="width:100%;" onclick="aceptarIncidenciaEncargadoUI(${i.id}, this)">Firmar y aceptar</button>
      <div id="encargadoError" class="error-msg"></div>
    `;
    firmaEncargadoVacia = true;
    inicializarFirmaCanvas('firma_encargado_canvas', () => { firmaEncargadoVacia = false; });
  }).catch(e => {
    document.getElementById('modalContent').innerHTML = `
      <button class="close-btn" onclick="cerrarModal()">cerrar</button>
      <h2>Aceptar incidencia</h2>
      <p style="color:var(--urgente); font-size:13px;">${escapeHtml(e.message)}</p>
    `;
  });
}

async function aceptarIncidenciaEncargadoUI(incidenciaId, boton) {
  if (firmaEncargadoVacia) { document.getElementById('encargadoError').textContent = 'Falta la firma'; return; }
  const payload = { firma_base64: document.getElementById('firma_encargado_canvas').toDataURL('image/png') };
  await conBloqueoDeBoton(boton, async () => {
    try {
      await api(`/api/rh/incidencias/${incidenciaId}/aceptar-encargado`, { method: 'POST', body: JSON.stringify(payload) });
      cerrarModal();
      await renderIncidenciasPendientesEncargado();
      mostrarExito('Incidencia aceptada y enviada a Recursos Humanos');
    } catch (e) {
      document.getElementById('encargadoError').textContent = e.message;
    }
  });
}
''',
            '''function abrirAceptarIncidenciaEncargado(incidenciaId) {
  document.getElementById('modalContent').innerHTML = '<p style="color:var(--muted); font-size:13px;">Cargando…</p>';
  abrirModal();
  api(`/api/rh/incidencias/${incidenciaId}`).then(i => {
    document.getElementById('modalContent').innerHTML = `
      <button class="close-btn" onclick="cerrarModal()">cerrar</button>
      <h2>Revisar incidencia</h2>
      <table class="users" style="margin-bottom:14px;">
        <tr><td><b>Persona</b></td><td>${escapeHtml(i.usuario_nombre)}${i.usuario_puesto ? ` — ${escapeHtml(i.usuario_puesto)}` : ''}</td></tr>
        <tr><td><b>Tipo</b></td><td>${NOMBRES_TIPO_INCIDENCIA_RH[i.tipo] || i.tipo}</td></tr>
        <tr><td><b>Fecha(s)</b></td><td>${i.fecha_inicio.slice(0,10)}${i.fecha_fin && i.fecha_fin.slice(0,10) !== i.fecha_inicio.slice(0,10) ? ' al ' + i.fecha_fin.slice(0,10) : ''}</td></tr>
        ${i.horas ? `<tr><td><b>Horas</b></td><td>${formatearHoras(i.horas)}</td></tr>` : ''}
        <tr><td><b>Motivo</b></td><td>${i.motivo ? escapeHtml(i.motivo) : '—'}</td></tr>
      </table>
      ${i.foto_base64 ? `<img src="${i.foto_base64}" style="max-width:100%; border-radius:4px; margin-bottom:14px;" />` : ''}
      <p style="font-size:12px; color:var(--muted); margin-bottom:10px;">
        Tu decisión es final -- una vez que aceptes o rechaces, Recursos Humanos solo la ve como información (ya no la vuelve a aprobar).
      </p>
      <div id="encargadoAceptarBloque">
        <label style="font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;">Tu firma (para aceptar)</label>
        <canvas id="firma_encargado_canvas" width="500" height="140" style="width:100%; height:140px; background:var(--substrate); border:1px solid rgba(155,157,159,0.3); touch-action:none; cursor:crosshair;"></canvas>
        <div style="display:flex; gap:8px; margin: 8px 0 14px;">
          <button class="secondary" style="flex:1;" onclick="limpiarFirmaCanvas('firma_encargado_canvas')">Limpiar firma</button>
        </div>
        <button class="primary" style="width:100%;" onclick="aceptarIncidenciaEncargadoUI(${i.id}, this)">Firmar y aceptar</button>
      </div>
      <div id="encargadoRechazarBloque" style="display:none; margin-top:14px; border-top:1px solid rgba(155,157,159,0.3); padding-top:14px;">
        <div class="field"><label>Motivo del rechazo</label><textarea id="rechazo_encargado_motivo" rows="3" placeholder="Explica por qué no se acepta esta incidencia"></textarea></div>
        <button class="danger" style="width:100%;" onclick="rechazarIncidenciaEncargadoUI(${i.id}, this)">Confirmar rechazo</button>
      </div>
      <div style="margin-top:14px; text-align:center;">
        <button class="secondary" id="btnMostrarRechazoEncargado" onclick="document.getElementById('encargadoAceptarBloque').style.display='none'; document.getElementById('encargadoRechazarBloque').style.display='block'; this.style.display='none';">No aceptar — rechazar con motivo</button>
      </div>
      <div id="encargadoError" class="error-msg"></div>
    `;
    firmaEncargadoVacia = true;
    inicializarFirmaCanvas('firma_encargado_canvas', () => { firmaEncargadoVacia = false; });
  }).catch(e => {
    document.getElementById('modalContent').innerHTML = `
      <button class="close-btn" onclick="cerrarModal()">cerrar</button>
      <h2>Revisar incidencia</h2>
      <p style="color:var(--urgente); font-size:13px;">${escapeHtml(e.message)}</p>
    `;
  });
}

async function aceptarIncidenciaEncargadoUI(incidenciaId, boton) {
  if (firmaEncargadoVacia) { document.getElementById('encargadoError').textContent = 'Falta la firma'; return; }
  const payload = { firma_base64: document.getElementById('firma_encargado_canvas').toDataURL('image/png') };
  await conBloqueoDeBoton(boton, async () => {
    try {
      await api(`/api/rh/incidencias/${incidenciaId}/aceptar-encargado`, { method: 'POST', body: JSON.stringify(payload) });
      cerrarModal();
      await renderIncidenciasPendientesEncargado();
      mostrarExito('Incidencia aceptada');
    } catch (e) {
      document.getElementById('encargadoError').textContent = e.message;
    }
  });
}

async function rechazarIncidenciaEncargadoUI(incidenciaId, boton) {
  const motivo = document.getElementById('rechazo_encargado_motivo').value.trim();
  if (!motivo) { document.getElementById('encargadoError').textContent = 'Escribe el motivo del rechazo'; return; }
  await conBloqueoDeBoton(boton, async () => {
    try {
      await api(`/api/rh/incidencias/${incidenciaId}/rechazar-encargado`, { method: 'POST', body: JSON.stringify({ motivo }) });
      cerrarModal();
      await renderIncidenciasPendientesEncargado();
      mostrarExito('Incidencia rechazada');
    } catch (e) {
      document.getElementById('encargadoError').textContent = e.message;
    }
  });
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
    print("    git add backend/db.py backend/app.py frontend/index.html")
    print('    git commit -m "RH Incidencias: decide la encargada de sucursal, RH solo informativo; quita oferta automatica de dia sin goce"')
    print("    git push")


if __name__ == "__main__":
    main()
