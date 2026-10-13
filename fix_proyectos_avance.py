# -*- coding: utf-8 -*-
"""
Proyectos: avance con semáforo y "Terminé".
  - Solo el administrador o quien creó el proyecto cambia el estatus de las
    tareas (también desde el Gantt). Quien tiene la tarea avisa con
    "✅ Terminé" (nota y foto opcionales): queda "por revisar" y se le avisa
    al creador.
  - Barra de avance en la lista y el detalle: % de tareas completadas y color
    por tiempos (rojo = hay vencidas, amarillo = por vencer en 2 días o
    entregadas tarde, verde = todo en tiempo). Cada tarea muestra su semáforo.
  - Nuevas columnas en proyecto_tareas: completada_en, terminada_reportada_*.
  - /api/meta trae es_logistica (para la app de Reparaciones).
REQUIERE haber corrido antes fix_notificaciones_push.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "        },\n        \"mi_departamento\": db.obtener_departamento_usuario(usuario[\"id\"]) if usuario[\"rol\"] != \"master\" else None,\n        \"mi_sucursal_id\": db.obtener_sucursal_id_usuario(usuario[\"id\"]) if usuario[\"rol\"] != \"master\" else None,\n        \"mi_ventanilla_turnos\": usuario.get(\"ventanilla_turnos\"),\n        \"terminos\": db.obtener_terminos(usuario[\"empresa_id\"]) if usuario[\"rol\"] != \"master\" else {},\n    }\n",
   "        },\n        \"mi_departamento\": db.obtener_departamento_usuario(usuario[\"id\"]) if usuario[\"rol\"] != \"master\" else None,\n        \"mi_sucursal_id\": db.obtener_sucursal_id_usuario(usuario[\"id\"]) if usuario[\"rol\"] != \"master\" else None,\n        # Para la app: Logística ve todas las reparaciones y registra la entrega al chofer.\n        \"es_logistica\": _es_departamento_logistica(usuario[\"id\"]) if usuario[\"rol\"] != \"master\" else False,\n        \"mi_ventanilla_turnos\": usuario.get(\"ventanilla_turnos\"),\n        \"terminos\": db.obtener_terminos(usuario[\"empresa_id\"]) if usuario[\"rol\"] != \"master\" else {},\n    }\n"
  ],
  [
   "    avisos.avisar_seguro(ids, titulo, cuerpo, modulo=\"proyectos\", ref=proyecto.get(\"id\"), excluir=[usuario[\"id\"]])\n\n\ndef _puede_ver_proyecto(usuario, proyecto):\n    if usuario[\"rol\"] == \"admin\":\n        return True\n",
   "    avisos.avisar_seguro(ids, titulo, cuerpo, modulo=\"proyectos\", ref=proyecto.get(\"id\"), excluir=[usuario[\"id\"]])\n\n\ndef _puede_mover_tareas(usuario, proyecto):\n    return usuario.get(\"rol\") == \"admin\" or usuario[\"id\"] == proyecto.get(\"creado_por_id\")\n\n\ndef _puede_ver_proyecto(usuario, proyecto):\n    if usuario[\"rol\"] == \"admin\":\n        return True\n"
  ],
  [
   "        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    if payload.estado not in db.ESTADOS_TAREA_PROYECTO:\n        raise HTTPException(status_code=400, detail=\"Estado inválido\")\n    # Solo quien tiene la tarea asignada, o el staff, puede cambiar su estado\n    if usuario[\"rol\"] not in (\"admin\", \"tecnico\") and usuario[\"id\"] != tarea[\"usuario_id\"]:\n        raise HTTPException(status_code=403, detail=\"Esta tarea no te pertenece\")\n    db.cambiar_estado_tarea_proyecto(tarea_id, payload.estado)\n    if payload.estado != tarea.get(\"estado\"):\n        _avisar_proyecto(usuario, proyecto, f\"📋 {proyecto.get('nombre', '')}\",\n                         f\"{usuario.get('nombre', '')} cambió la tarea \\\"{(tarea.get('descripcion') or '')[:80]}\\\" a {payload.estado.replace('_', ' ')}.\",\n                         solo=[proyecto.get(\"creado_por_id\"), tarea.get(\"usuario_id\")])\n    return db.obtener_proyecto(usuario[\"empresa_id\"], proyecto_id)\n\n\n",
   "        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    if payload.estado not in db.ESTADOS_TAREA_PROYECTO:\n        raise HTTPException(status_code=400, detail=\"Estado inválido\")\n    # Solo el administrador o quien creó el proyecto cambia el estatus; quien\n    # tiene la tarea avisa con \"Terminé\" (ver api_reportar_tarea_terminada).\n    if not _puede_mover_tareas(usuario, proyecto):\n        raise HTTPException(status_code=403, detail=\"Solo el administrador o quien creó el proyecto cambia el estatus. \"\n                                                    \"Si ya terminaste, usa \\\"Terminé\\\".\")\n    db.cambiar_estado_tarea_proyecto(tarea_id, payload.estado)\n    if payload.estado != tarea.get(\"estado\"):\n        _avisar_proyecto(usuario, proyecto, f\"📋 {proyecto.get('nombre', '')}\",\n                         f\"{usuario.get('nombre', '')} cambió la tarea \\\"{(tarea.get('descripcion') or '')[:80]}\\\" a {payload.estado.replace('_', ' ')}.\",\n                         solo=[proyecto.get(\"creado_por_id\")] + [u[\"id\"] for t in proyecto.get(\"tareas\") or []\n                                                                  if t[\"id\"] == tarea_id for u in t.get(\"usuarios\") or []])\n    return db.obtener_proyecto(usuario[\"empresa_id\"], proyecto_id)\n\n\nclass TareaTerminadaIn(BaseModel):\n    nota: Optional[str] = Field(default=None, max_length=1000)\n    archivo_base64: Optional[str] = None\n    archivo_nombre: Optional[str] = None\n    archivo_tipo: Optional[str] = None\n\n\n@app.post(\"/api/proyectos/{proyecto_id}/tareas/{tarea_id}/termine\")\ndef api_reportar_tarea_terminada(proyecto_id: int, tarea_id: int, payload: TareaTerminadaIn, usuario: dict = Depends(requiere_empresa)):\n    \"\"\"Quien tiene la tarea avisa que ya terminó (con nota y/o foto). Queda\n    \"por revisar\" hasta que el administrador o quien creó el proyecto la\n    marque completada.\"\"\"\n    proyecto = db.obtener_proyecto(usuario[\"empresa_id\"], proyecto_id)\n    if not proyecto:\n        raise HTTPException(status_code=404, detail=\"Proyecto no encontrado\")\n    tarea = db.obtener_tarea_proyecto(tarea_id)\n    if not tarea or tarea[\"proyecto_id\"] != proyecto_id:\n        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    if not db.usuario_asignado_a_tarea(tarea_id, usuario[\"id\"]) and not _puede_mover_tareas(usuario, proyecto):\n        raise HTTPException(status_code=403, detail=\"Esta tarea no está asignada a ti\")\n    if tarea[\"estado\"] == \"completada\":\n        raise HTTPException(status_code=400, detail=\"Esta tarea ya está completada\")\n    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa demasiado (máximo 5MB)\")\n    nota = _limpio(payload.nota)\n    db.reportar_tarea_terminada(tarea_id, usuario[\"id\"], nota)\n    db.agregar_actualizacion_proyecto(\n        proyecto_id, usuario[\"id\"],\n        f\"✅ Terminé la tarea \\\"{(tarea.get('descripcion') or '')[:120]}\\\"\" + (f\" — {nota}\" if nota else \"\") + \". Falta que la revisen.\",\n        payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)\n    _avisar_proyecto(usuario, proyecto, f\"✅ Tarea terminada · {proyecto.get('nombre', '')}\",\n                     f\"{usuario.get('nombre', '')} terminó \\\"{(tarea.get('descripcion') or '')[:80]}\\\". Revísala y márcala completada.\",\n                     solo=[proyecto.get(\"creado_por_id\")])\n    return db.obtener_proyecto(usuario[\"empresa_id\"], proyecto_id)\n\n\n"
  ],
  [
   "    tarea = db.obtener_tarea_proyecto(tarea_id)\n    if not tarea or tarea[\"proyecto_id\"] != proyecto_id:\n        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    db.actualizar_completado_tarea_gantt(tarea_id, payload.completed)\n    return {\"ok\": True}\n\n",
   "    tarea = db.obtener_tarea_proyecto(tarea_id)\n    if not tarea or tarea[\"proyecto_id\"] != proyecto_id:\n        raise HTTPException(status_code=404, detail=\"Tarea no encontrada\")\n    if not _puede_mover_tareas(usuario, proyecto):\n        raise HTTPException(status_code=403, detail=\"Solo el administrador o quien creó el proyecto marca tareas como completadas.\")\n    db.actualizar_completado_tarea_gantt(tarea_id, payload.completed)\n    return {\"ok\": True}\n\n"
  ]
 ],
 "backend/db.py": [
  [
   "import os\nimport secrets\nimport json\nfrom datetime import datetime, timedelta\nfrom zoneinfo import ZoneInfo\n\nimport psycopg2\n",
   "import os\nimport secrets\nimport json\nfrom datetime import date, datetime, timedelta\nfrom zoneinfo import ZoneInfo\n\nimport psycopg2\n"
  ],
  [
   "        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_plan_fin TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_ejec_inicio TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_ejec_fin TEXT;\n\n        CREATE TABLE IF NOT EXISTS proyecto_tarea_dependencias (\n            id SERIAL PRIMARY KEY,\n",
   "        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_plan_fin TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_ejec_inicio TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS gantt_ejec_fin TEXT;\n        -- Avance del proyecto: cuándo se completó cada tarea (para saber si\n        -- fue a tiempo) y el aviso de \"Terminé\" de quien la tiene asignada\n        -- (solo el admin o quien creó el proyecto la marca completada).\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS completada_en TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS terminada_reportada_en TEXT;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS terminada_reportada_por INTEGER REFERENCES users(id) ON DELETE SET NULL;\n        ALTER TABLE proyecto_tareas ADD COLUMN IF NOT EXISTS terminada_nota TEXT;\n\n        CREATE TABLE IF NOT EXISTS proyecto_tarea_dependencias (\n            id SERIAL PRIMARY KEY,\n"
  ],
  [
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT t.id, t.descripcion, t.estado, t.fecha_limite, t.proyecto_id, p.nombre AS proyecto_nombre\n        FROM proyecto_tareas t\n        JOIN proyectos p ON p.id = t.proyecto_id\n        JOIN proyecto_tarea_usuarios tu ON tu.tarea_id = t.id\n",
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT t.id, t.descripcion, t.estado, t.fecha_limite, t.proyecto_id, p.nombre AS proyecto_nombre,\n               t.terminada_reportada_en, t.terminada_nota, t.completada_en, p.creado_por_id\n        FROM proyecto_tareas t\n        JOIN proyectos p ON p.id = t.proyecto_id\n        JOIN proyecto_tarea_usuarios tu ON tu.tarea_id = t.id\n"
  ],
  [
   "        ORDER BY t.fecha_limite IS NULL, t.fecha_limite ASC\n    \"\"\", (empresa_id, usuario_id))\n    rows = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    return rows\n\n\ndef dar_de_baja_equipo(empresa_id, equipo_id):\n",
   "        ORDER BY t.fecha_limite IS NULL, t.fecha_limite ASC\n    \"\"\", (empresa_id, usuario_id))\n    rows = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    calcular_avance_tareas(rows)  # deja \"semaforo\" en cada una\n    return rows\n\n\ndef dar_de_baja_equipo(empresa_id, equipo_id):\n"
  ],
  [
   "    \"\"\"\n\n\ndef _enriquecer_proyecto(cur, proyecto):\n    \"\"\"Agrega participantes (personas y departamentos), su estado de firma, y calcula el tiempo transcurrido.\"\"\"\n    cur.execute(\"\"\"\n",
   "    \"\"\"\n\n\ndef _fecha_corta(v):\n    try:\n        return date.fromisoformat(str(v)[:10]) if v else None\n    except ValueError:\n        return None\n\n\ndef calcular_avance_tareas(tareas, hoy=None):\n    \"\"\"Barra de avance del proyecto: % = completadas / total, y el color\n    según los tiempos de entrega:\n      rojo     hay tareas vencidas sin terminar\n      amarillo alguna vence en 2 días o menos, o se completó tarde\n      verde    todo en tiempo\n      gris     todavía no hay tareas\n    A cada tarea le deja \"semaforo\": completada | tarde | vencida | por_vencer | en_tiempo | sin_fecha.\"\"\"\n    hoy = hoy or ahora().date()\n    total = len(tareas)\n    completadas = vencidas = por_vencer = tarde = por_revisar = 0\n    for t in tareas:\n        limite = _fecha_corta(t.get(\"fecha_limite\"))\n        if t.get(\"estado\") == \"completada\":\n            completadas += 1\n            hecho = _fecha_corta(t.get(\"completada_en\"))\n            if limite and hecho and hecho > limite:\n                tarde += 1\n                t[\"semaforo\"] = \"tarde\"\n            else:\n                t[\"semaforo\"] = \"completada\"\n            continue\n        if t.get(\"terminada_reportada_en\"):\n            por_revisar += 1\n        if not limite:\n            t[\"semaforo\"] = \"sin_fecha\"\n        elif limite < hoy:\n            vencidas += 1\n            t[\"semaforo\"] = \"vencida\"\n            t[\"dias_vencida\"] = (hoy - limite).days\n        elif (limite - hoy).days <= 2:\n            por_vencer += 1\n            t[\"semaforo\"] = \"por_vencer\"\n        else:\n            t[\"semaforo\"] = \"en_tiempo\"\n    if not total:\n        color, texto = \"gris\", \"Sin tareas todavía\"\n    elif vencidas:\n        color, texto = \"rojo\", f\"{vencidas} tarea(s) vencida(s)\"\n    elif por_vencer or tarde:\n        partes = []\n        if por_vencer:\n            partes.append(f\"{por_vencer} por vencer\")\n        if tarde:\n            partes.append(f\"{tarde} entregada(s) tarde\")\n        color, texto = \"amarillo\", \", \".join(partes)\n    else:\n        color, texto = \"verde\", \"Todo en tiempo\" if completadas < total else \"Terminado en tiempo\"\n    return {\"total\": total, \"completadas\": completadas, \"porcentaje\": round(completadas * 100 / total) if total else 0,\n            \"vencidas\": vencidas, \"por_vencer\": por_vencer, \"tarde\": tarde, \"por_revisar\": por_revisar,\n            \"color\": color, \"texto\": texto}\n\n\ndef _enriquecer_proyecto(cur, proyecto):\n    \"\"\"Agrega participantes (personas y departamentos), su estado de firma, y calcula el tiempo transcurrido.\"\"\"\n    cur.execute(\"\"\"\n"
  ],
  [
   "            # frontend todavía lo usa — pero lo normal ya es leer la lista \"usuarios\".\n            t[\"usuario_nombre\"] = t[\"usuarios\"][0][\"nombre_completo\"] if t[\"usuarios\"] else None\n    proyecto[\"tareas\"] = tareas\n\n    if proyecto.get(\"fecha_inicio\"):\n        inicio = datetime.fromisoformat(proyecto[\"fecha_inicio\"])\n",
   "            # frontend todavía lo usa — pero lo normal ya es leer la lista \"usuarios\".\n            t[\"usuario_nombre\"] = t[\"usuarios\"][0][\"nombre_completo\"] if t[\"usuarios\"] else None\n    proyecto[\"tareas\"] = tareas\n    proyecto[\"avance\"] = calcular_avance_tareas(tareas)\n\n    if proyecto.get(\"fecha_inicio\"):\n        inicio = datetime.fromisoformat(proyecto[\"fecha_inicio\"])\n"
  ],
  [
   "\n\ndef cambiar_estado_tarea_proyecto(tarea_id, estado):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    cur.execute(\"UPDATE proyecto_tareas SET estado = %s, actualizado_en = %s WHERE id = %s\", (estado, now, tarea_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef eliminar_tarea_proyecto(tarea_id):\n",
   "\n\ndef cambiar_estado_tarea_proyecto(tarea_id, estado):\n    \"\"\"Al completarla se guarda cuándo (para saber si fue a tiempo). Si se\n    regresa a pendiente/en progreso, se borra el \"Terminé\" (se le pidió más).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    if estado == \"completada\":\n        cur.execute(\"\"\"UPDATE proyecto_tareas SET estado = %s, actualizado_en = %s,\n                              completada_en = COALESCE(completada_en, %s) WHERE id = %s\"\"\", (estado, now, now, tarea_id))\n    else:\n        cur.execute(\"\"\"UPDATE proyecto_tareas SET estado = %s, actualizado_en = %s, completada_en = NULL,\n                              terminada_reportada_en = NULL, terminada_reportada_por = NULL, terminada_nota = NULL\n                       WHERE id = %s\"\"\", (estado, now, tarea_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef reportar_tarea_terminada(tarea_id, usuario_id, nota=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    cur.execute(\"\"\"UPDATE proyecto_tareas SET terminada_reportada_en = %s, terminada_reportada_por = %s,\n                          terminada_nota = %s, actualizado_en = %s WHERE id = %s\"\"\",\n                (now, usuario_id, nota, now, tarea_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef usuario_asignado_a_tarea(tarea_id, usuario_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT 1 AS x FROM proyecto_tarea_usuarios WHERE tarea_id = %s AND usuario_id = %s\", (tarea_id, usuario_id))\n    ok = cur.fetchone() is not None\n    cur.close(); conn.close()\n    return ok\n\n\ndef eliminar_tarea_proyecto(tarea_id):\n"
  ],
  [
   "\n\ndef actualizar_completado_tarea_gantt(tarea_id, completado):\n    conn = get_connection()\n    cur = conn.cursor()\n    now = ahora().isoformat(timespec=\"seconds\")\n    cur.execute(\n        \"UPDATE proyecto_tareas SET estado = %s, actualizado_en = %s WHERE id = %s\",\n        (\"completada\" if completado else \"pendiente\", now, tarea_id),\n    )\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef eliminar_tarea_gantt(tarea_id):\n",
   "\n\ndef actualizar_completado_tarea_gantt(tarea_id, completado):\n    cambiar_estado_tarea_proyecto(tarea_id, \"completada\" if completado else \"pendiente\")\n\n\ndef eliminar_tarea_gantt(tarea_id):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  }).join('');\n}\n\nfunction cardProyectoHtml(p) {\n  const chipsPersonas = p.participantes_usuarios.map(u => `<span class=\"chip persona\">${escapeHtml(u.nombre_completo)}</span>`).join('');\n  const chipsDeptos = p.participantes_departamentos.map(d => `<span class=\"chip depto\">${escapeHtml(d)}</span>`).join('');\n",
   "  }).join('');\n}\n\n// Barra de avance del proyecto (la calcula el servidor: % de tareas\n// completadas; color por tiempos: rojo = hay vencidas, amarillo = por\n// vencer o entregadas tarde, verde = todo en tiempo).\nconst COLOR_AVANCE = { verde: '#2E9E5B', amarillo: '#E0A326', rojo: '#D8192F', gris: '#9B9D9F' };\nconst SEMAFORO_TAREA = {\n  vencida: ['#D8192F', 'Vencida'], por_vencer: ['#E0A326', 'Por vencer'], en_tiempo: ['#2E9E5B', 'En tiempo'],\n  sin_fecha: ['#9B9D9F', 'Sin fecha'], completada: ['#2E9E5B', 'A tiempo'], tarde: ['#E0A326', 'Tarde'],\n};\nfunction barraAvanceProyectoHtml(a, grande) {\n  if (!a) return '';\n  const color = COLOR_AVANCE[a.color] || COLOR_AVANCE.gris;\n  const alto = grande ? 12 : 7;\n  return `\n    <div class=\"avance-proyecto\" style=\"margin:${grande ? '6px 0 12px' : '8px 0 2px'};\">\n      <div style=\"display:flex; justify-content:space-between; font-size:${grande ? 13 : 11}px; margin-bottom:3px;\">\n        <span><b style=\"color:${color};\">${a.porcentaje}%</b> · ${a.completadas} de ${a.total} tarea(s)</span>\n        <span style=\"color:${color}; font-weight:700;\">${escapeHtml(a.texto)}</span>\n      </div>\n      <div style=\"height:${alto}px; background:rgba(155,157,159,0.25); border-radius:${alto}px; overflow:hidden;\">\n        <div style=\"height:100%; width:${Math.max(a.porcentaje, a.total ? 3 : 0)}%; background:${color}; border-radius:${alto}px; transition:width .3s;\"></div>\n      </div>\n      ${grande && a.por_revisar ? `<div style=\"font-size:12px; color:#E0A326; margin-top:4px;\">🔔 ${a.por_revisar} tarea(s) marcada(s) como terminada(s), esperan tu revisión.</div>` : ''}\n    </div>`;\n}\n\nfunction cardProyectoHtml(p) {\n  const chipsPersonas = p.participantes_usuarios.map(u => `<span class=\"chip persona\">${escapeHtml(u.nombre_completo)}</span>`).join('');\n  const chipsDeptos = p.participantes_departamentos.map(d => `<span class=\"chip depto\">${escapeHtml(d)}</span>`).join('');\n"
  ],
  [
   "      ${p.descripcion ? `<div style=\"font-size:12px; color:var(--muted);\">${escapeHtml(p.descripcion.slice(0,100))}</div>` : ''}\n      ${p.fecha_estimada ? `<div class=\"fecha-estimada\">🎯 Estimado: ${p.fecha_estimada.slice(0,10)}</div>` : ''}\n      ${tiempo ? `<div class=\"tiempo\">${tiempo}</div>` : ''}\n      <div class=\"chips\">${chipsPersonas}${chipsDeptos}</div>\n    </div>\n  `;\n",
   "      ${p.descripcion ? `<div style=\"font-size:12px; color:var(--muted);\">${escapeHtml(p.descripcion.slice(0,100))}</div>` : ''}\n      ${p.fecha_estimada ? `<div class=\"fecha-estimada\">🎯 Estimado: ${p.fecha_estimada.slice(0,10)}</div>` : ''}\n      ${tiempo ? `<div class=\"tiempo\">${tiempo}</div>` : ''}\n      ${p.avance && p.avance.total ? barraAvanceProyectoHtml(p.avance, false) : ''}\n      <div class=\"chips\">${chipsPersonas}${chipsDeptos}</div>\n    </div>\n  `;\n"
  ],
  [
   "  `;\n  const tituloParticipantes = `Participantes y firma de compromiso ${p.todos_resolvieron_firma ? '<span class=\"badge baja\" style=\"margin-left:6px;\">✅ Todos resolvieron</span>' : '<span class=\"badge media\" style=\"margin-left:6px;\">⏳ Falta alguien</span>'}`;\n\n  const tareasVisibles = p.tareas.filter(t => t.estado !== 'completada');\n  const tareasCompletadas = p.tareas.length - tareasVisibles.length;\n  const seccionTareas = `\n",
   "  `;\n  const tituloParticipantes = `Participantes y firma de compromiso ${p.todos_resolvieron_firma ? '<span class=\"badge baja\" style=\"margin-left:6px;\">✅ Todos resolvieron</span>' : '<span class=\"badge media\" style=\"margin-left:6px;\">⏳ Falta alguien</span>'}`;\n\n  // Solo el administrador o quien creó el proyecto cambia el estatus de las\n  // tareas; quien la tiene asignada avisa con \"Terminé\".\n  const puedeMover = SESION.usuario.rol === 'admin' || p.creado_por_id === SESION.usuario.id;\n  const tareasVisibles = p.tareas.filter(t => t.estado !== 'completada');\n  const tareasCompletadas = p.tareas.length - tareasVisibles.length;\n  const seccionTareas = `\n"
  ],
  [
   "              ${esStaff ? `<span class=\"editar\" style=\"margin-left:6px;\" onclick=\"abrirReasignarTareaProyecto(${p.id}, ${t.id}, this)\" title=\"Cambiar a quién está asignada\">✎</span>` : ''}\n            </td>\n            <td>${escapeHtml(t.descripcion)}</td>\n            <td>${t.fecha_limite ? t.fecha_limite.slice(0,10) : '—'}</td>\n            <td>\n              ${(esStaff || meToca) ? `\n                <select onchange=\"pintarSelectPorColor(this, COLOR_ESTADO_TAREA[this.value]); cambiarEstadoTareaProyectoUI(${p.id}, ${t.id}, this.value)\" style=\"font-size:12px; padding:5px 8px; min-width:120px; font-weight:bold; background:transparent; color:${COLORES_ESTADO_HEX[COLOR_ESTADO_TAREA[t.estado]]}; border:1px solid ${COLORES_ESTADO_HEX[COLOR_ESTADO_TAREA[t.estado]]};\">\n                  ${META.estados_tarea_proyecto.map(e => `<option value=\"${e}\" ${e===t.estado?'selected':''}>${NOMBRES_ESTADO_TAREA[e]}</option>`).join('')}\n                </select>\n              ` : `<span class=\"badge ${COLOR_ESTADO_TAREA[t.estado]}\">${NOMBRES_ESTADO_TAREA[t.estado]}</span>`}\n            </td>\n            ${esStaff ? `<td><span class=\"quitar\" onclick=\"quitarTareaProyectoUI(${p.id}, ${t.id})\">✕</span></td>` : ''}\n          </tr>\n",
   "              ${esStaff ? `<span class=\"editar\" style=\"margin-left:6px;\" onclick=\"abrirReasignarTareaProyecto(${p.id}, ${t.id}, this)\" title=\"Cambiar a quién está asignada\">✎</span>` : ''}\n            </td>\n            <td>${escapeHtml(t.descripcion)}</td>\n            <td>${t.fecha_limite ? t.fecha_limite.slice(0,10) : '—'}\n              ${SEMAFORO_TAREA[t.semaforo] && t.fecha_limite ? `<div style=\"font-size:11px; font-weight:700; color:${SEMAFORO_TAREA[t.semaforo][0]};\">● ${SEMAFORO_TAREA[t.semaforo][1]}${t.dias_vencida ? ` (${t.dias_vencida} día(s))` : ''}</div>` : ''}\n            </td>\n            <td>\n              ${t.terminada_reportada_en ? `<div style=\"font-size:11px; color:#E0A326; font-weight:700; margin-bottom:4px;\">🔔 Reportó que terminó ${escapeHtml(t.terminada_reportada_en.slice(0,10))}${t.terminada_nota ? `<br><span style=\"font-weight:400; color:var(--muted);\">${escapeHtml(t.terminada_nota)}</span>` : ''}</div>` : ''}\n              ${puedeMover ? `\n                <select onchange=\"pintarSelectPorColor(this, COLOR_ESTADO_TAREA[this.value]); cambiarEstadoTareaProyectoUI(${p.id}, ${t.id}, this.value)\" style=\"font-size:12px; padding:5px 8px; min-width:120px; font-weight:bold; background:transparent; color:${COLORES_ESTADO_HEX[COLOR_ESTADO_TAREA[t.estado]]}; border:1px solid ${COLORES_ESTADO_HEX[COLOR_ESTADO_TAREA[t.estado]]};\">\n                  ${META.estados_tarea_proyecto.map(e => `<option value=\"${e}\" ${e===t.estado?'selected':''}>${NOMBRES_ESTADO_TAREA[e]}</option>`).join('')}\n                </select>\n              ` : `<span class=\"badge ${COLOR_ESTADO_TAREA[t.estado]}\">${NOMBRES_ESTADO_TAREA[t.estado]}</span>\n                   ${meToca && !t.terminada_reportada_en ? `<button class=\"secondary\" style=\"margin-top:4px; padding:3px 10px; font-size:12px;\" onclick=\"tareaTerminadaUI(${p.id}, ${t.id})\">✅ Terminé</button>` : ''}`}\n            </td>\n            ${esStaff ? `<td><span class=\"quitar\" onclick=\"quitarTareaProyectoUI(${p.id}, ${t.id})\">✕</span></td>` : ''}\n          </tr>\n"
  ],
  [
   "    </div>\n    <p style=\"font-size:12px; color:var(--muted);\">Creado por <b style=\"color:var(--text)\">${escapeHtml(p.creado_por_nombre)}</b></p>\n    <p class=\"tiempo\" style=\"margin-bottom:10px;\">${tiempoTexto}</p>\n\n    ${controlesEstado}\n\n",
   "    </div>\n    <p style=\"font-size:12px; color:var(--muted);\">Creado por <b style=\"color:var(--text)\">${escapeHtml(p.creado_por_nombre)}</b></p>\n    <p class=\"tiempo\" style=\"margin-bottom:10px;\">${tiempoTexto}</p>\n    ${barraAvanceProyectoHtml(p.avance, true)}\n\n    ${controlesEstado}\n\n"
  ],
  [
   "  const usuarioIds = Array.from(document.querySelectorAll('.py_reasignar_tarea_cb:checked')).map(cb => parseInt(cb.value, 10));\n  try {\n    await api(`/api/proyectos/tareas/${tareaId}/asignados`, { method: 'PATCH', body: JSON.stringify({ usuario_ids: usuarioIds }) });\n    await abrirDetalleProyecto(proyectoId);\n  } catch (e) {\n    document.getElementById('proyectoDetalleError').textContent = e.message;\n",
   "  const usuarioIds = Array.from(document.querySelectorAll('.py_reasignar_tarea_cb:checked')).map(cb => parseInt(cb.value, 10));\n  try {\n    await api(`/api/proyectos/tareas/${tareaId}/asignados`, { method: 'PATCH', body: JSON.stringify({ usuario_ids: usuarioIds }) });\n    await abrirDetalleProyecto(proyectoId);\n  } catch (e) {\n    document.getElementById('proyectoDetalleError').textContent = e.message;\n  }\n}\n\nasync function tareaTerminadaUI(proyectoId, tareaId) {\n  const nota = prompt('¿Algo que comentar de lo que hiciste? (opcional)\\nAvisaremos a quien creó el proyecto para que la revise.');\n  if (nota === null) return;\n  try {\n    await api(`/api/proyectos/${proyectoId}/tareas/${tareaId}/termine`, { method: 'POST', body: JSON.stringify({ nota }) });\n    await abrirDetalleProyecto(proyectoId);\n  } catch (e) {\n    document.getElementById('proyectoDetalleError').textContent = e.message;\n"
  ],
  [
   "          <tr>\n            <td>${escapeHtml(t.descripcion)}</td>\n            <td style=\"color:var(--muted); font-size:12px;\">${escapeHtml(t.proyecto_nombre)}</td>\n            <td>${t.fecha_limite ? t.fecha_limite.slice(0,10) : '—'}</td>\n            <td><span class=\"badge ${COLOR_ESTADO_TAREA[t.estado]}\">${NOMBRES_ESTADO_TAREA[t.estado]}</span></td>\n            <td><button class=\"secondary\" style=\"padding:6px 12px; font-size:12px;\" onclick=\"cerrarModal(); abrirDetalleProyecto(${t.proyecto_id})\">Ver proyecto</button></td>\n          </tr>\n        `).join('')}\n",
   "          <tr>\n            <td>${escapeHtml(t.descripcion)}</td>\n            <td style=\"color:var(--muted); font-size:12px;\">${escapeHtml(t.proyecto_nombre)}</td>\n            <td>${t.fecha_limite ? t.fecha_limite.slice(0,10) : '—'}\n              ${SEMAFORO_TAREA[t.semaforo] && t.fecha_limite ? `<div style=\"font-size:11px; font-weight:700; color:${SEMAFORO_TAREA[t.semaforo][0]};\">● ${SEMAFORO_TAREA[t.semaforo][1]}</div>` : ''}</td>\n            <td>${t.terminada_reportada_en ? '<span class=\"badge media\">🔔 Por revisar</span>' : `<span class=\"badge ${COLOR_ESTADO_TAREA[t.estado]}\">${NOMBRES_ESTADO_TAREA[t.estado]}</span>`}</td>\n            <td><button class=\"secondary\" style=\"padding:6px 12px; font-size:12px;\" onclick=\"cerrarModal(); abrirDetalleProyecto(${t.proyecto_id})\">Ver proyecto</button></td>\n          </tr>\n        `).join('')}\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "def tokens_push_de_usuarios" not in f.read():
            print("Primero corre fix_notificaciones_push.py (y los anteriores), y luego este.")
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
