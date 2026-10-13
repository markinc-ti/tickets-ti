# -*- coding: utf-8 -*-
"""
Incidencias: que RH siempre las vea.
  - La incidencia de una encargada ya no espera a "la encargada" (ella
    misma): pasa directo a RH. Las que estaban atoradas así pasan a RH solas
    al arrancar el servidor.
  - RH → "Todas (administrar)" también muestra las que esperan a la
    encargada de la sucursal ("Esperando a su encargada") y RH las puede
    aprobar o rechazar directamente.
  - Aviso (push) a RH cuando una incidencia le llega directo.
REQUIERE haber corrido antes fix_laboratorio_envio_entrega.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    # de lo suyo, aunque siga esperando al encargado de su sucursal). Cuando\n    # se piden \"todas\" sin filtro, no se mezclan las que ni siquiera ha visto\n    # el encargado todavía — esas están en la bandeja del encargado, no aquí.\n    puede_ver_todas = usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_datos_empleado_rh\", False)\n    usuario_id_filtro = None if puede_ver_todas else usuario[\"id\"]\n    resultado = db.listar_incidencias_rh(usuario[\"empresa_id\"], usuario_id_filtro, estado)\n    if puede_ver_todas and estado is None:\n        resultado = [i for i in resultado if i[\"estado\"] != \"pendiente_encargado\"]\n    return resultado\n\n\ndef _saldo_vacaciones_ajustado(persona: dict, dias_consumidos_microsip: float) -> Optional[dict]:\n",
   "    # de lo suyo, aunque siga esperando al encargado de su sucursal). Cuando\n    # se piden \"todas\" sin filtro, no se mezclan las que ni siquiera ha visto\n    # el encargado todavía — esas están en la bandeja del encargado, no aquí.\n    # RH también ve las que esperan a la encargada (marcadas así) y las puede\n    # decidir directamente si hace falta.\n    puede_ver_todas = usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_datos_empleado_rh\", False)\n    usuario_id_filtro = None if puede_ver_todas else usuario[\"id\"]\n    return db.listar_incidencias_rh(usuario[\"empresa_id\"], usuario_id_filtro, estado)\n\n\ndef _saldo_vacaciones_ajustado(persona: dict, dias_consumidos_microsip: float) -> Optional[dict]:\n"
  ],
  [
   "    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n    avisos.avisar_seguro(db.ids_encargados_de_usuario(usuario[\"empresa_id\"], usuario[\"id\"]),\n                         \"🩺 Incidencia por revisar\", f\"{usuario.get('nombre', '')}: {payload.tipo.replace('_', ' ')} desde el {payload.fecha_inicio[:10]}.\",\n                         modulo=\"rh\", ref=incidencia_id, excluir=[usuario[\"id\"]])\n    return {\"id\": incidencia_id}\n",
   "    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n    nueva = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id) or {}\n    # Va a la encargada de su sucursal; si no tiene (o es ella misma), a RH.\n    destinatarios = (db.ids_encargados_de_usuario(usuario[\"empresa_id\"], usuario[\"id\"])\n                     if nueva.get(\"estado\") == \"pendiente_encargado\"\n                     else db.ids_usuarios_con_permiso(usuario[\"empresa_id\"], \"acceso_datos_empleado_rh\"))\n    avisos.avisar_seguro(destinatarios,\n                         \"🩺 Incidencia por revisar\", f\"{usuario.get('nombre', '')}: {payload.tipo.replace('_', ' ')} desde el {payload.fecha_inicio[:10]}.\",\n                         modulo=\"rh\", ref=incidencia_id, excluir=[usuario[\"id\"]])\n    return {\"id\": incidencia_id}\n"
  ],
  [
   "    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if incidencia[\"estado\"] != \"pendiente\":\n        raise HTTPException(status_code=400, detail=\"Esta incidencia ya fue resuelta\")\n    db.resolver_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, usuario[\"id\"], payload.estado, payload.respuesta_admin)\n    incidencia_resuelta = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n",
   "    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if incidencia[\"estado\"] not in (\"pendiente\", \"pendiente_encargado\"):\n        raise HTTPException(status_code=400, detail=\"Esta incidencia ya fue resuelta\")\n    db.resolver_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, usuario[\"id\"], payload.estado, payload.respuesta_admin)\n    incidencia_resuelta = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n"
  ]
 ],
 "backend/db.py": [
  [
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_factura_pendiente BOOLEAN NOT NULL DEFAULT FALSE;\n        -- A dónde se manda al salir del laboratorio: a una sucursal (la que\n        -- se elija, no siempre la de origen) o a la escuela del estudiante.\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_tipo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_sucursal_id INTEGER;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n",
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_factura_pendiente BOOLEAN NOT NULL DEFAULT FALSE;\n        -- A dónde se manda al salir del laboratorio: a una sucursal (la que\n        -- se elija, no siempre la de origen) o a la escuela del estudiante.\n        -- Incidencias atoradas: esperando \"a la encargada\" cuando la única\n        -- encargada de esa sucursal es la misma persona -> pasan a RH.\n        UPDATE incidencias_rh i SET estado = 'pendiente'\n         WHERE i.estado = 'pendiente_encargado'\n           AND NOT EXISTS (SELECT 1 FROM users e JOIN users u ON u.id = i.usuario_id\n                            WHERE e.empresa_id = i.empresa_id AND e.rol = 'encargado_sucursal' AND e.activo = TRUE\n                              AND e.sucursal_id = u.sucursal_id AND u.sucursal_id IS NOT NULL AND e.id <> u.id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_tipo TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS destino_sucursal_id INTEGER;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n"
  ],
  [
   "    estado_inicial = \"pendiente\"\n    if mi_sucursal_id:\n        cur.execute(\n            \"SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE LIMIT 1\",\n            (empresa_id, mi_sucursal_id),\n        )\n        if cur.fetchone():\n            estado_inicial = \"pendiente_encargado\"\n",
   "    estado_inicial = \"pendiente\"\n    if mi_sucursal_id:\n        cur.execute(\n            # Otra encargada, no la misma persona: lo de una encargada va a RH.\n            \"SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE AND id <> %s LIMIT 1\",\n            (empresa_id, mi_sucursal_id, usuario_id),\n        )\n        if cur.fetchone():\n            estado_inicial = \"pendiente_encargado\"\n"
  ],
  [
   "    cur.execute(\"\"\"\n        UPDATE incidencias_rh\n        SET estado = %s, respuesta_admin = %s, resuelto_por_id = %s, resuelto_en = %s\n        WHERE id = %s AND empresa_id = %s AND estado = 'pendiente'\n    \"\"\", (estado, respuesta_admin, admin_id, now, incidencia_id, empresa_id))\n    filas = cur.rowcount\n    conn.commit()\n",
   "    cur.execute(\"\"\"\n        UPDATE incidencias_rh\n        SET estado = %s, respuesta_admin = %s, resuelto_por_id = %s, resuelto_en = %s\n        WHERE id = %s AND empresa_id = %s AND estado IN ('pendiente', 'pendiente_encargado')\n    \"\"\", (estado, respuesta_admin, admin_id, now, incidencia_id, empresa_id))\n    filas = cur.rowcount\n    conn.commit()\n"
  ],
  [
   "    tiene_encargado = False\n    if mi_sucursal_id:\n        cur.execute(\n            \"SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE LIMIT 1\",\n            (empresa_id, mi_sucursal_id),\n        )\n        tiene_encargado = cur.fetchone() is not None\n    nuevo_estado = \"pendiente_encargado\" if tiene_encargado else \"pendiente\"\n",
   "    tiene_encargado = False\n    if mi_sucursal_id:\n        cur.execute(\n            # Otra encargada, no la misma persona: lo de una encargada va a RH.\n            \"SELECT 1 AS x FROM users WHERE empresa_id = %s AND rol = 'encargado_sucursal' AND sucursal_id = %s AND activo = TRUE AND id <> %s LIMIT 1\",\n            (empresa_id, mi_sucursal_id, usuario_id),\n        )\n        tiene_encargado = cur.fetchone() is not None\n    nuevo_estado = \"pendiente_encargado\" if tiene_encargado else \"pendiente\"\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  const cont = document.getElementById('rhContenido');\n  const BADGE_ESTADO = {\n    propuesta_empleado: '<span class=\"badge alta\">❓ Esperando tu respuesta</span>',\n    pendiente_encargado: '<span class=\"rol-tag\">⏳ Esperando al encargado de tu sucursal</span>',\n    pendiente: '<span class=\"rol-tag\">⏳ Pendiente</span>',\n    aprobada: '<span class=\"badge baja\">✅ Aprobada</span>',\n    pagada: '<span class=\"badge baja\">💰 Pagada</span>',\n",
   "  const cont = document.getElementById('rhContenido');\n  const BADGE_ESTADO = {\n    propuesta_empleado: '<span class=\"badge alta\">❓ Esperando tu respuesta</span>',\n    pendiente_encargado: (puedeVerTodas && !soloMias) ? '<span class=\"rol-tag\">⏳ Esperando a su encargada (RH también puede decidir)</span>' : '<span class=\"rol-tag\">⏳ Esperando al encargado de tu sucursal</span>',\n    pendiente: '<span class=\"rol-tag\">⏳ Pendiente</span>',\n    aprobada: '<span class=\"badge baja\">✅ Aprobada</span>',\n    pagada: '<span class=\"badge baja\">💰 Pagada</span>',\n"
  ],
  [
   "    ${i.horas ? `<p style=\"font-size:13px;\"><b>Horas solicitadas:</b> ${formatearHoras(i.horas)}${i.tipo === 'dia_libre_sin_goce' ? ' <span style=\"color:var(--muted); font-size:12px;\">(al aprobarse, se suman a su saldo por pagar)</span>' : ''}</p>` : ''}\n    ${i.motivo ? `<p style=\"font-size:13px;\"><b>Motivo:</b> ${escapeHtml(i.motivo)}</p>` : ''}\n    ${i.foto_base64 ? `<img src=\"${i.foto_base64}\" style=\"width:100%; max-height:320px; object-fit:contain; background:var(--substrate); margin:10px 0; border-radius:4px;\" />` : ''}\n    ${i.estado !== 'pendiente' ? `\n      <p style=\"font-size:12px; color:var(--muted); margin-top:10px;\">\n        Resuelta por <b style=\"color:var(--text);\">${escapeHtml(i.resuelto_por_nombre || '')}</b> el ${i.resuelto_en ? i.resuelto_en.slice(0,10) : ''}\n      </p>\n      ${i.respuesta_admin ? `<p style=\"font-size:13px;\"><b>Comentario:</b> ${escapeHtml(i.respuesta_admin)}</p>` : ''}\n    ` : ''}\n\n    ${puedeResolver && i.estado === 'pendiente' ? `\n      <div class=\"comentarios\">\n        <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;\">Resolver</label>\n        <div class=\"field\"><label>Comentario (opcional)</label><textarea id=\"rh_respuesta\"></textarea></div>\n",
   "    ${i.horas ? `<p style=\"font-size:13px;\"><b>Horas solicitadas:</b> ${formatearHoras(i.horas)}${i.tipo === 'dia_libre_sin_goce' ? ' <span style=\"color:var(--muted); font-size:12px;\">(al aprobarse, se suman a su saldo por pagar)</span>' : ''}</p>` : ''}\n    ${i.motivo ? `<p style=\"font-size:13px;\"><b>Motivo:</b> ${escapeHtml(i.motivo)}</p>` : ''}\n    ${i.foto_base64 ? `<img src=\"${i.foto_base64}\" style=\"width:100%; max-height:320px; object-fit:contain; background:var(--substrate); margin:10px 0; border-radius:4px;\" />` : ''}\n    ${puedeResolver && i.estado === 'pendiente_encargado' ? `<p style=\"font-size:12px; color:var(--muted);\">Está esperando a la encargada de su sucursal, pero RH la puede aprobar o rechazar desde aquí.</p>` : ''}\n    ${!['pendiente', 'pendiente_encargado', 'propuesta_empleado'].includes(i.estado) ? `\n      <p style=\"font-size:12px; color:var(--muted); margin-top:10px;\">\n        Resuelta por <b style=\"color:var(--text);\">${escapeHtml(i.resuelto_por_nombre || '')}</b> el ${i.resuelto_en ? i.resuelto_en.slice(0,10) : ''}\n      </p>\n      ${i.respuesta_admin ? `<p style=\"font-size:13px;\"><b>Comentario:</b> ${escapeHtml(i.respuesta_admin)}</p>` : ''}\n    ` : ''}\n\n    ${puedeResolver && (i.estado === 'pendiente' || i.estado === 'pendiente_encargado') ? `\n      <div class=\"comentarios\">\n        <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;\">Resolver</label>\n        <div class=\"field\"><label>Comentario (opcional)</label><textarea id=\"rh_respuesta\"></textarea></div>\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "def fijar_destino_laboratorio" not in f.read():
            print("Primero corre fix_laboratorio_envio_entrega.py (y los anteriores), y luego este.")
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
