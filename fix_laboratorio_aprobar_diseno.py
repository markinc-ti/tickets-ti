#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio: nuevo estatus "Aprobar diseño" entre "Modelado" y "Maquila".

El laboratorio sube el archivo de diseño (STL) desde su panel -- eso mueve
el trabajo a "Aprobar diseño" y ya no se puede mandar a fresar sin que el
estudiante le dé el visto bueno. El estudiante lo descarga desde su portal
(celular o computadora), lo revisa, y le da clic a "Todo está bien" (el
trabajo pasa a Maquila) o pide una corrección (se queda en "Aprobar diseño"
hasta que el laboratorio suba el archivo corregido).

Este parche es independiente de los otros tres parches de Laboratorio/DS
Core entregados junto con este (firma automática por pago, búsqueda por
folio, validación de material) -- no importa el orden en que se apliquen
entre sí.

Por qué: siguiendo con lo que pidió David sobre el flujo de laboratorio,
quiere un paso donde el estudiante apruebe el diseño antes de que se
fabrique, en vez de enterarse hasta que ya está hecho.

Que cambia:
- backend/db.py: nueva tabla laboratorio_disenos (un archivo STL por
  intento, con su propio estado pendiente/aprobado/rechazado); nuevo
  estado 'aprobar_diseno' en ESTADOS_LABORATORIO; obtener_trabajo_laboratorio
  ahora también trae la lista de diseños; funciones nuevas para subir,
  consultar, aprobar y rechazar un diseño.
- backend/app.py: 'maquila' ya no se puede mover a mano desde el estado
  libre (solo se llega ahí aprobando el diseño); tres endpoints nuevos --
  POST /api/laboratorio/{id}/subir-diseno (laboratorio),
  POST /api/laboratorio/{id}/disenos/{diseno_id}/aprobar (estudiante) y
  POST /api/laboratorio/{id}/disenos/{diseno_id}/rechazar (estudiante).
- frontend/index.html (panel del laboratorio/administrador): en el detalle
  de un trabajo en 'modelado' o 'aprobar_diseno', botón para subir el STL
  (o volver a subirlo si el estudiante pidió corrección).
- frontend/laboratorio_estudiantes.html (portal del estudiante): en el
  detalle de un trabajo en 'aprobar_diseno', tarjeta para descargar el
  diseño y aprobarlo o pedir corrección (con nota opcional de qué corregir).
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            'ESTADOS_LABORATORIO = [\n    "recibido", "en_laboratorio", "modelado", "maquila", "maquillado", "control_calidad",\n    "envio_sucursal", "listo_entrega", "entregado", "cancelado",\n]',
            'ESTADOS_LABORATORIO = [\n    "recibido", "en_laboratorio", "modelado", "aprobar_diseno", "maquila", "maquillado", "control_calidad",\n    "envio_sucursal", "listo_entrega", "entregado", "cancelado",\n]',
        ],
        [
            '        CREATE TABLE IF NOT EXISTS laboratorio_pagos_reportados (\n            id SERIAL PRIMARY KEY,\n            trabajo_id INTEGER NOT NULL REFERENCES trabajos_laboratorio(id) ON DELETE CASCADE,\n            reportado_por_id INTEGER NOT NULL REFERENCES users(id),\n            comprobante_base64 TEXT NOT NULL,\n            monto_detectado NUMERIC,\n            fecha_detectada TEXT,\n            referencia_detectada TEXT,\n            banco_detectado TEXT,\n            estado TEXT NOT NULL DEFAULT \'pendiente\',\n            creado_en TEXT NOT NULL,\n            revisado_por_id INTEGER REFERENCES users(id),\n            revisado_en TEXT,\n            motivo_rechazo TEXT\n        );\n    """)\n    conn.commit()',
            '        CREATE TABLE IF NOT EXISTS laboratorio_pagos_reportados (\n            id SERIAL PRIMARY KEY,\n            trabajo_id INTEGER NOT NULL REFERENCES trabajos_laboratorio(id) ON DELETE CASCADE,\n            reportado_por_id INTEGER NOT NULL REFERENCES users(id),\n            comprobante_base64 TEXT NOT NULL,\n            monto_detectado NUMERIC,\n            fecha_detectada TEXT,\n            referencia_detectada TEXT,\n            banco_detectado TEXT,\n            estado TEXT NOT NULL DEFAULT \'pendiente\',\n            creado_en TEXT NOT NULL,\n            revisado_por_id INTEGER REFERENCES users(id),\n            revisado_en TEXT,\n            motivo_rechazo TEXT\n        );\n\n        -- El archivo de diseño (STL) que sube el laboratorio para que el\n        -- estudiante lo apruebe antes de mandarlo a fresar. Cada intento\n        -- (incluidas las correcciones después de un rechazo) es una fila\n        -- nueva -- así queda el historial completo de idas y vueltas; la\n        -- más reciente es la que se le muestra al estudiante para revisar.\n        CREATE TABLE IF NOT EXISTS laboratorio_disenos (\n            id SERIAL PRIMARY KEY,\n            trabajo_id INTEGER NOT NULL REFERENCES trabajos_laboratorio(id) ON DELETE CASCADE,\n            archivo_base64 TEXT NOT NULL,\n            archivo_nombre TEXT,\n            subido_por_id INTEGER NOT NULL REFERENCES users(id),\n            creado_en TEXT NOT NULL,\n            estado TEXT NOT NULL DEFAULT \'pendiente\',\n            revisado_por_id INTEGER REFERENCES users(id),\n            revisado_en TEXT,\n            motivo_rechazo TEXT\n        );\n    """)\n    conn.commit()',
        ],
        [
            '    cur.execute("""\n        SELECT e.*, u.nombre_completo AS subido_por_nombre\n        FROM laboratorio_evidencias e JOIN users u ON u.id = e.subido_por_id\n        WHERE e.trabajo_id = %s ORDER BY e.creado_en ASC\n    """, (trabajo_id,))\n    trabajo["evidencias"] = [dict(r) for r in cur.fetchall()]\n\n    cur.execute("""\n        SELECT a.*, u.nombre_completo AS autor_nombre\n        FROM laboratorio_actualizaciones a JOIN users u ON u.id = a.autor_id\n        WHERE a.trabajo_id = %s ORDER BY a.creado_en ASC\n    """, (trabajo_id,))\n    trabajo["actualizaciones"] = [dict(r) for r in cur.fetchall()]\n\n    cur.close(); conn.close()\n    return trabajo',
            '    cur.execute("""\n        SELECT e.*, u.nombre_completo AS subido_por_nombre\n        FROM laboratorio_evidencias e JOIN users u ON u.id = e.subido_por_id\n        WHERE e.trabajo_id = %s ORDER BY e.creado_en ASC\n    """, (trabajo_id,))\n    trabajo["evidencias"] = [dict(r) for r in cur.fetchall()]\n\n    cur.execute("""\n        SELECT d.*, u.nombre_completo AS subido_por_nombre\n        FROM laboratorio_disenos d JOIN users u ON u.id = d.subido_por_id\n        WHERE d.trabajo_id = %s ORDER BY d.creado_en ASC\n    """, (trabajo_id,))\n    trabajo["disenos"] = [dict(r) for r in cur.fetchall()]\n\n    cur.execute("""\n        SELECT a.*, u.nombre_completo AS autor_nombre\n        FROM laboratorio_actualizaciones a JOIN users u ON u.id = a.autor_id\n        WHERE a.trabajo_id = %s ORDER BY a.creado_en ASC\n    """, (trabajo_id,))\n    trabajo["actualizaciones"] = [dict(r) for r in cur.fetchall()]\n\n    cur.close(); conn.close()\n    return trabajo',
        ],
        [
            'def firmar_recepcion_laboratorio(empresa_id, trabajo_id, firma_recepcion):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec="seconds")\n    cur.execute(\n        "UPDATE trabajos_laboratorio SET firma_recepcion = %s, actualizado_en = %s WHERE id = %s AND empresa_id = %s",\n        (firma_recepcion, now, trabajo_id, empresa_id),\n    )\n    conn.commit()\n    cur.close(); conn.close()',
            'def firmar_recepcion_laboratorio(empresa_id, trabajo_id, firma_recepcion):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec="seconds")\n    cur.execute(\n        "UPDATE trabajos_laboratorio SET firma_recepcion = %s, actualizado_en = %s WHERE id = %s AND empresa_id = %s",\n        (firma_recepcion, now, trabajo_id, empresa_id),\n    )\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef subir_diseno_laboratorio(trabajo_id, archivo_base64, archivo_nombre, subido_por_id):\n    """Cada subida (la primera o una corrección después de un rechazo) es\n    una fila nueva en laboratorio_disenos -- la más reciente es la que se le\n    muestra al estudiante para revisar."""\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec="seconds")\n    cur.execute(\n        """INSERT INTO laboratorio_disenos (trabajo_id, archivo_base64, archivo_nombre, subido_por_id, creado_en, estado)\n           VALUES (%s, %s, %s, %s, %s, \'pendiente\') RETURNING id""",\n        (trabajo_id, archivo_base64, archivo_nombre, subido_por_id, now),\n    )\n    diseno_id = cur.fetchone()["id"]\n    conn.commit()\n    cur.close(); conn.close()\n    return diseno_id\n\n\ndef obtener_diseno_laboratorio(diseno_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("SELECT * FROM laboratorio_disenos WHERE id = %s", (diseno_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef aprobar_diseno_laboratorio(diseno_id, usuario_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec="seconds")\n    cur.execute(\n        "UPDATE laboratorio_disenos SET estado = \'aprobado\', revisado_por_id = %s, revisado_en = %s WHERE id = %s",\n        (usuario_id, now, diseno_id),\n    )\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef rechazar_diseno_laboratorio(diseno_id, usuario_id, motivo):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec="seconds")\n    cur.execute(\n        "UPDATE laboratorio_disenos SET estado = \'rechazado\', revisado_por_id = %s, revisado_en = %s, motivo_rechazo = %s WHERE id = %s",\n        (usuario_id, now, motivo, diseno_id),\n    )\n    conn.commit()\n    cur.close(); conn.close()',
        ],
    ],
    'backend/app.py': [
        [
            '# Estados que el laboratorio mueve libremente una vez que el trabajo ya\n# está ahí — \'recibido\' (alta en sucursal), \'en_laboratorio\' (llegada al\n# laboratorio) y \'listo_entrega\' (recepción de vuelta en sucursal) tienen\n# cada uno su propio endpoint dedicado, con su firma/validación — por\n# eso NO están en esta lista.\nESTADOS_LABORATORIO_LIBRES = ["modelado", "maquila", "maquillado", "control_calidad", "envio_sucursal", "cancelado"]',
            '# Estados que el laboratorio mueve libremente una vez que el trabajo ya\n# está ahí — \'recibido\' (alta en sucursal), \'en_laboratorio\' (llegada al\n# laboratorio), \'aprobar_diseno\' (subir el STL y esperar a que el\n# estudiante lo apruebe) y \'listo_entrega\' (recepción de vuelta en\n# sucursal) tienen cada uno su propio endpoint dedicado, con su\n# firma/validación — por eso NO están en esta lista. \'maquila\' tampoco:\n# solo se llega ahí cuando el estudiante aprueba el diseño (endpoint\n# /disenos/{id}/aprobar) -- nunca se manda a fresar sin ese visto bueno.\nESTADOS_LABORATORIO_LIBRES = ["modelado", "maquillado", "control_calidad", "envio_sucursal", "cancelado"]',
        ],
        [
            'NOMBRES_ESTADO_LABORATORIO_BITACORA = {\n    "recibido": "Recibido en sucursal", "en_laboratorio": "Entró a laboratorio", "modelado": "Modelado / diseño", "maquila": "Maquila (fresado)",\n    "maquillado": "Maquillado / acabado", "control_calidad": "Control de calidad",\n    "envio_sucursal": "Envío a sucursal", "listo_entrega": "Listo para entrega",\n    "entregado": "Entregado", "cancelado": "Cancelado",\n}',
            'NOMBRES_ESTADO_LABORATORIO_BITACORA = {\n    "recibido": "Recibido en sucursal", "en_laboratorio": "Entró a laboratorio", "modelado": "Modelado / diseño",\n    "aprobar_diseno": "Aprobar diseño", "maquila": "Maquila (fresado)",\n    "maquillado": "Maquillado / acabado", "control_calidad": "Control de calidad",\n    "envio_sucursal": "Envío a sucursal", "listo_entrega": "Listo para entrega",\n    "entregado": "Entregado", "cancelado": "Cancelado",\n}',
        ],
        [
            'class NuevaEvidenciaLaboratorio(BaseModel):\n    archivo_base64: str\n    archivo_nombre: Optional[str] = None\n    descripcion: Optional[str] = None',
            'class NuevaEvidenciaLaboratorio(BaseModel):\n    archivo_base64: str\n    archivo_nombre: Optional[str] = None\n    descripcion: Optional[str] = None\n\n\nclass SubirDisenoLaboratorio(BaseModel):\n    archivo_base64: str = Field(min_length=100)\n    archivo_nombre: Optional[str] = None\n\n\nclass RechazarDisenoLaboratorio(BaseModel):\n    motivo: Optional[str] = None',
        ],
        [
            '    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, payload.estado)\n    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.post("/api/laboratorio/{trabajo_id}/recibir-sucursal")',
            '    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, payload.estado)\n    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")\ndef api_subir_diseno_laboratorio(trabajo_id: int, payload: SubirDisenoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    """El laboratorio sube el archivo de diseño (STL) para que el estudiante\n    lo revise antes de mandarlo a fresar -- la primera vez mueve el trabajo\n    de \'modelado\' a \'aprobar_diseno\'; si el estudiante ya lo había\n    rechazado, esto sube la corrección y se queda en \'aprobar_diseno\'."""\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):\n        raise HTTPException(status_code=400, detail="Este trabajo no está en modelado ni esperando aprobación de diseño")\n    if usuario["rol"] != "admin":\n        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:\n            raise HTTPException(status_code=403, detail="Solo el laboratorio puede subir el diseño")\n    if len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")\n    estado_anterior = trabajo["estado"]\n    db.subir_diseno_laboratorio(trabajo_id, payload.archivo_base64, payload.archivo_nombre, usuario["id"])\n    if estado_anterior == "modelado":\n        db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "aprobar_diseno")\n    db.agregar_actualizacion_laboratorio(\n        trabajo_id, usuario["id"],\n        f"Subió el diseño ({payload.archivo_nombre or \'archivo\'}) para que el estudiante lo apruebe.",\n    )\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/aprobar")\ndef api_aprobar_diseno_laboratorio(trabajo_id: int, diseno_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):\n    """El estudiante (o el laboratorio/admin, por si necesita ayudarlo)\n    aprueba el diseño que se subió -- con eso el trabajo pasa a maquila.\n    Nunca se manda a fresar sin este visto bueno."""\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if trabajo["estado"] != "aprobar_diseno":\n        raise HTTPException(status_code=400, detail="Este trabajo no está esperando aprobación de diseño")\n    diseno = db.obtener_diseno_laboratorio(diseno_id)\n    if not diseno or diseno["trabajo_id"] != trabajo_id:\n        raise HTTPException(status_code=404, detail="Diseño no encontrado")\n    if diseno["estado"] != "pendiente":\n        raise HTTPException(status_code=400, detail="Este diseño ya fue revisado")\n    db.aprobar_diseno_laboratorio(diseno_id, usuario["id"])\n    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "maquila")\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"{trabajo[\'solicitante_nombre\']} aprobó el diseño -- pasa a maquila.")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/rechazar")\ndef api_rechazar_diseno_laboratorio(trabajo_id: int, diseno_id: int, payload: RechazarDisenoLaboratorio, usuario: dict = Depends(requiere_ver_laboratorio)):\n    """El estudiante pide que se corrija el diseño -- el trabajo se queda en\n    \'aprobar_diseno\' hasta que el laboratorio suba una corrección."""\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if trabajo["estado"] != "aprobar_diseno":\n        raise HTTPException(status_code=400, detail="Este trabajo no está esperando aprobación de diseño")\n    diseno = db.obtener_diseno_laboratorio(diseno_id)\n    if not diseno or diseno["trabajo_id"] != trabajo_id:\n        raise HTTPException(status_code=404, detail="Diseño no encontrado")\n    if diseno["estado"] != "pendiente":\n        raise HTTPException(status_code=400, detail="Este diseño ya fue revisado")\n    motivo = (payload.motivo or "").strip() or None\n    db.rechazar_diseno_laboratorio(diseno_id, usuario["id"], motivo)\n    db.agregar_actualizacion_laboratorio(\n        trabajo_id, usuario["id"],\n        f"{trabajo[\'solicitante_nombre\']} pidió corregir el diseño" + (f": {motivo}" if motivo else "") + ".",\n    )\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.post("/api/laboratorio/{trabajo_id}/recibir-sucursal")',
        ],
    ],
    'frontend/index.html': [
        [
            "const NOMBRES_ESTADO_LABORATORIO = {\n  recibido: 'Recibido en sucursal', en_laboratorio: 'Entró a laboratorio', modelado: 'Modelado / diseño', maquila: 'Maquila (fresado)',\n  maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad', envio_sucursal: 'Envío a sucursal',\n  listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n};",
            "const NOMBRES_ESTADO_LABORATORIO = {\n  recibido: 'Recibido en sucursal', en_laboratorio: 'Entró a laboratorio', modelado: 'Modelado / diseño',\n  aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)',\n  maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad', envio_sucursal: 'Envío a sucursal',\n  listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n};",
        ],
        [
            "const ESTADOS_LABORATORIO_LIBRES_JS = ['modelado', 'maquila', 'maquillado', 'control_calidad', 'envio_sucursal'];",
            "const ESTADOS_LABORATORIO_LIBRES_JS = ['modelado', 'maquillado', 'control_calidad', 'envio_sucursal'];",
        ],
        [
            '  const saldo = round2(w.pago_monto_total - w.costo_total);\n  function round2(n) { return Math.round(n * 100) / 100; }',
            '  const saldo = round2(w.pago_monto_total - w.costo_total);\n  function round2(n) { return Math.round(n * 100) / 100; }\n  const disenoActual = (w.disenos && w.disenos.length) ? w.disenos[w.disenos.length - 1] : null;',
        ],
        [
            '    ${ESTADOS_LABORATORIO_LIBRES_JS.includes(w.estado) || w.estado === \'en_laboratorio\' ? `\n      <div class="row-2" style="align-items:end; margin-top:12px;">\n        <div class="field"><label>Mover estado dentro del laboratorio</label>\n          <select id="lab_estado_sel">${ESTADOS_LABORATORIO_LIBRES_JS.map(e => `<option value="${e}" ${e===w.estado?\'selected\':\'\'}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join(\'\')}</select>\n        </div>\n        <button class="primary" onclick="cambiarEstadoLaboratorioUI(${w.id}, this)">Guardar estado</button>\n      </div>\n    ` : \'\'}\n\n    ${w.estado === \'envio_sucursal\' ? `',
            '    ${ESTADOS_LABORATORIO_LIBRES_JS.includes(w.estado) || w.estado === \'en_laboratorio\' ? `\n      <div class="row-2" style="align-items:end; margin-top:12px;">\n        <div class="field"><label>Mover estado dentro del laboratorio</label>\n          <select id="lab_estado_sel">${ESTADOS_LABORATORIO_LIBRES_JS.map(e => `<option value="${e}" ${e===w.estado?\'selected\':\'\'}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join(\'\')}</select>\n        </div>\n        <button class="primary" onclick="cambiarEstadoLaboratorioUI(${w.id}, this)">Guardar estado</button>\n      </div>\n    ` : \'\'}\n\n    ${(w.estado === \'modelado\' || w.estado === \'aprobar_diseno\') ? (disenoActual && disenoActual.estado === \'pendiente\' ? `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0;">🦷 Diseño subido (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — esperando que el estudiante lo apruebe.</p>\n      </div>\n    ` : `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0 0 8px;">🦷 ${disenoActual && disenoActual.estado === \'rechazado\' ? `El estudiante pidió corregir el diseño${disenoActual.motivo_rechazo ? \': \' + escapeHtml(disenoActual.motivo_rechazo) : \'\'} — sube el archivo corregido.` : \'Sube el archivo de diseño (STL) para que el estudiante lo apruebe.\'}</p>\n        <label class="secondary btn-file" style="display:inline-block;">\n          📎 Subir diseño (STL)\n          <input type="file" accept=".stl,.ply,.obj" style="display:none;" onchange="subirDisenoLaboratorioUI(${w.id}, this)" />\n        </label>\n      </div>\n    `) : \'\'}\n\n    ${w.estado === \'envio_sucursal\' ? `',
        ],
        [
            "async function subirEvidenciaLaboratorioUI(trabajoId, input) {\n  const archivo = input.files[0];\n  if (!archivo) return;\n  const base64 = await new Promise((res, rej) => {\n    const r = new FileReader();\n    r.onload = () => res(r.result);\n    r.onerror = rej;\n    r.readAsDataURL(archivo);\n  });\n  try {\n    await api(`/api/laboratorio/${trabajoId}/evidencias`, { method: 'POST', body: JSON.stringify({ archivo_base64: base64, archivo_nombre: archivo.name }) });\n    await abrirDetalleLaboratorio(trabajoId);\n  } catch (e) {\n    alert(e.message);\n  }\n}",
            "async function subirEvidenciaLaboratorioUI(trabajoId, input) {\n  const archivo = input.files[0];\n  if (!archivo) return;\n  const base64 = await new Promise((res, rej) => {\n    const r = new FileReader();\n    r.onload = () => res(r.result);\n    r.onerror = rej;\n    r.readAsDataURL(archivo);\n  });\n  try {\n    await api(`/api/laboratorio/${trabajoId}/evidencias`, { method: 'POST', body: JSON.stringify({ archivo_base64: base64, archivo_nombre: archivo.name }) });\n    await abrirDetalleLaboratorio(trabajoId);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nasync function subirDisenoLaboratorioUI(trabajoId, input) {\n  const archivo = input.files[0];\n  if (!archivo) return;\n  const base64 = await new Promise((res, rej) => {\n    const r = new FileReader();\n    r.onload = () => res(r.result);\n    r.onerror = rej;\n    r.readAsDataURL(archivo);\n  });\n  try {\n    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: 'POST', body: JSON.stringify({ archivo_base64: base64, archivo_nombre: archivo.name }) });\n    await abrirDetalleLaboratorio(trabajoId);\n  } catch (e) {\n    alert(e.message);\n  }\n}",
        ],
    ],
    'frontend/laboratorio_estudiantes.html': [
        [
            "  const NOMBRES_ESTADO = {\n    recibido: 'Recibido — falta pago y firma', en_laboratorio: 'En laboratorio', modelado: 'Modelado / diseño',\n    maquila: 'Maquila (fresado)', maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad',\n    envio_sucursal: 'En camino a sucursal', listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n  };",
            "  const NOMBRES_ESTADO = {\n    recibido: 'Recibido — falta pago y firma', en_laboratorio: 'En laboratorio', modelado: 'Modelado / diseño',\n    aprobar_diseno: 'Aprobar diseño', maquila: 'Maquila (fresado)', maquillado: 'Maquillado / acabado', control_calidad: 'Control de calidad',\n    envio_sucursal: 'En camino a sucursal', listo_entrega: 'Listo para entrega', entregado: 'Entregado', cancelado: 'Cancelado',\n  };",
        ],
        [
            '    if (cubierto && !w.firma_recepcion) {\n      html += `\n        <div class="card destacada">\n          <h2 style="margin-top:0;">Firma de recepción</h2>\n          <p class="sub" style="margin-bottom:10px;">Tu pago ya está confirmado — firma aquí para que el laboratorio empiece a fabricar tu trabajo.</p>\n          <canvas id="firmaCanvas" width="500" height="120"></canvas>\n          <div class="fila" style="margin-top:10px;">\n            <button class="secondary" onclick="limpiarFirma()">Limpiar</button>\n            <button class="primary" onclick="firmarRecepcion(${w.id})">Firmar y confirmar recepción</button>\n          </div>\n          <div class="error" id="firmaError"></div>\n        </div>\n      `;\n    }\n\n    return html;\n  }\n\n  async function verDetalle(id) {',
            '    if (cubierto && !w.firma_recepcion) {\n      html += `\n        <div class="card destacada">\n          <h2 style="margin-top:0;">Firma de recepción</h2>\n          <p class="sub" style="margin-bottom:10px;">Tu pago ya está confirmado — firma aquí para que el laboratorio empiece a fabricar tu trabajo.</p>\n          <canvas id="firmaCanvas" width="500" height="120"></canvas>\n          <div class="fila" style="margin-top:10px;">\n            <button class="secondary" onclick="limpiarFirma()">Limpiar</button>\n            <button class="primary" onclick="firmarRecepcion(${w.id})">Firmar y confirmar recepción</button>\n          </div>\n          <div class="error" id="firmaError"></div>\n        </div>\n      `;\n    }\n\n    return html;\n  }\n\n  function _seccionAprobarDiseno(w) {\n    if (w.estado !== \'aprobar_diseno\') return \'\';\n    const disenos = w.disenos || [];\n    const disenoActual = disenos.length ? disenos[disenos.length - 1] : null;\n    if (!disenoActual || disenoActual.estado !== \'pendiente\') {\n      return `\n        <div class="card destacada">\n          <h2 style="margin-top:0;">Diseño</h2>\n          <p class="sub">El laboratorio todavía no sube el diseño para que lo revises.</p>\n        </div>\n      `;\n    }\n    return `\n      <div class="card destacada">\n        <h2 style="margin-top:0;">Revisa tu diseño</h2>\n        <p class="sub" style="margin-bottom:10px;">El laboratorio subió el diseño de tu trabajo (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — descárgalo y revísalo antes de que se mande a fresar.</p>\n        <a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${disenoActual.archivo_base64}" download="${escapeHtml(disenoActual.archivo_nombre || \'diseno.stl\')}">⬇️ Descargar diseño (STL)</a>\n        <button class="primary" style="width:100%; margin-bottom:10px;" onclick="aprobarDisenoUI(${w.id}, ${disenoActual.id})">✅ Todo está bien</button>\n        <p class="sub" style="margin-bottom:4px;">¿Algo no está bien? Cuéntanos qué (opcional):</p>\n        <textarea id="diseno_motivo_rechazo" placeholder="ej. falta ajustar el contacto con el diente 16"></textarea>\n        <button class="secondary" style="width:100%; margin-top:8px;" onclick="rechazarDisenoUI(${w.id}, ${disenoActual.id})">No está bien — pedir corrección</button>\n        <div class="error" id="disenoError"></div>\n      </div>\n    `;\n  }\n\n  async function verDetalle(id) {',
        ],
        [
            "        </div>\n        ${_seccionPagoYFirma(w)}\n      `;\n      const canvas = document.getElementById('firmaCanvas');",
            "        </div>\n        ${_seccionPagoYFirma(w)}\n        ${_seccionAprobarDiseno(w)}\n      `;\n      const canvas = document.getElementById('firmaCanvas');",
        ],
        [
            "  async function firmarRecepcion(id) {\n    const err = document.getElementById('firmaError');\n    if (FIRMA_VACIA) { err.textContent = 'Falta tu firma.'; return; }\n    const firma_recepcion = document.getElementById('firmaCanvas').toDataURL('image/png');\n    try {\n      await api(`/api/laboratorio/${id}/firmar-recepcion`, { method: 'POST', body: JSON.stringify({ firma_recepcion }) });\n      await verDetalle(id);\n    } catch (e) {\n      err.textContent = e.message;\n    }\n  }\n\n  async function iniciar() {",
            "  async function firmarRecepcion(id) {\n    const err = document.getElementById('firmaError');\n    if (FIRMA_VACIA) { err.textContent = 'Falta tu firma.'; return; }\n    const firma_recepcion = document.getElementById('firmaCanvas').toDataURL('image/png');\n    try {\n      await api(`/api/laboratorio/${id}/firmar-recepcion`, { method: 'POST', body: JSON.stringify({ firma_recepcion }) });\n      await verDetalle(id);\n    } catch (e) {\n      err.textContent = e.message;\n    }\n  }\n\n  async function aprobarDisenoUI(trabajoId, disenoId) {\n    const err = document.getElementById('disenoError');\n    try {\n      await api(`/api/laboratorio/${trabajoId}/disenos/${disenoId}/aprobar`, { method: 'POST' });\n      await verDetalle(trabajoId);\n    } catch (e) {\n      if (err) err.textContent = e.message;\n    }\n  }\n\n  async function rechazarDisenoUI(trabajoId, disenoId) {\n    const err = document.getElementById('disenoError');\n    const campoMotivo = document.getElementById('diseno_motivo_rechazo');\n    const motivo = campoMotivo ? campoMotivo.value.trim() : '';\n    try {\n      await api(`/api/laboratorio/${trabajoId}/disenos/${disenoId}/rechazar`, { method: 'POST', body: JSON.stringify({ motivo: motivo || null }) });\n      await verDetalle(trabajoId);\n    } catch (e) {\n      if (err) err.textContent = e.message;\n    }\n  }\n\n  async function iniciar() {",
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
    print("    git add backend/db.py backend/app.py frontend/index.html frontend/laboratorio_estudiantes.html")
    print('    git commit -m "Laboratorio: nuevo estatus Aprobar diseno con subida/descarga/aprobacion de STL"')
    print("    git push")


if __name__ == "__main__":
    main()
