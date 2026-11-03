# -*- coding: utf-8 -*-
"""
RH CHECADORES: CAMBIAR EL VINCULO SI TE EQUIVOCASTE
En "Personas de los checadores", cada numero ya ligado muestra a quien esta
ligado y un boton "Cambiar": eliges a la persona correcta (o "De quien es?"
para desligarlo) y Guardar. Pide confirmacion, avisa si esa persona ya tenia
otro numero en el mismo checador, cambia el nombre corregido, recalcula la
nave de los dos y avisa si hay que corregir el numero en el checador (Paso 0).
REQUIERE haber corrido antes fix_rh_nave_por_checador.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_cambiar_vinculo_checador.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\n@app.patch(\"/api/rh/checadores/gente/{gente_id}\")\ndef api_actualizar_gente_checador(gente_id: int, payload: GenteChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    try:\n        n = db.actualizar_gente_checador(usuario[\"empresa_id\"], gente_id, payload.usuario_id, _limpio(payload.nombre), usuario[\"id\"])\n    except ValueError as e:\n",
   "\n@app.patch(\"/api/rh/checadores/gente/{gente_id}\")\ndef api_actualizar_gente_checador(gente_id: int, payload: GenteChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    antes = db.obtener_gente_checador(usuario[\"empresa_id\"], gente_id) or {}\n    try:\n        n = db.actualizar_gente_checador(usuario[\"empresa_id\"], gente_id, payload.usuario_id, _limpio(payload.nombre), usuario[\"id\"])\n    except ValueError as e:\n"
  ],
  [
   "    if not n:\n        raise HTTPException(status_code=404, detail=\"No encontrado\")\n    nave = _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[payload.usuario_id]) if payload.usuario_id else None\n    return {\"ok\": True, \"nave\": (nave or {}).get(\"cambios\", [None])[0] if (nave or {}).get(\"cambios\") else None}\n\n\nclass PedirChecadorIn(BaseModel):\n",
   "    if not n:\n        raise HTTPException(status_code=404, detail=\"No encontrado\")\n    nave = _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[payload.usuario_id]) if payload.usuario_id else None\n    anterior = antes.get(\"usuario_id\")\n    if anterior and anterior != payload.usuario_id:\n        # Se cambió el vínculo: a quien tenía antes se le recalcula su nave con los checadores que le quedan.\n        _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[anterior])\n    return {\"ok\": True, \"nave\": (nave or {}).get(\"cambios\", [None])[0] if (nave or {}).get(\"cambios\") else None,\n            \"cambio_vinculo\": bool(anterior and anterior != payload.usuario_id)}\n\n\nclass PedirChecadorIn(BaseModel):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "              ? `<div style=\"font-size:10px; color:#e8a33d; font-weight:700;\">${rhSinMicrosip() ? 'No. emp.' : 'Microsip'}: ${escapeHtml(asis_normNum(g.usuario_numero))}</div>` : ''}</td>\n            <td>${escapeHtml(g.nombre_checador || '—')}</td>\n            <td><input id=\"gnom_${g.id}\" value=\"${escapeHtml(g.nombre || '')}\" placeholder=\"${escapeHtml(g.nombre_checador || 'Nombre completo')}\" style=\"font-size:12px; min-width:160px;\" /></td>\n            <td><select id=\"gusr_${g.id}\" style=\"font-size:12px; min-width:200px; max-width:280px;\">${asis_opcionesUsuarios(usuarios, g.usuario_id, g.nombre || g.nombre_checador)}</select>\n              ${g.usuario_id ? '' : '<div style=\"font-size:10px; color:#e8a33d;\">sin ligar</div>'}</td>\n            <td style=\"white-space:nowrap;\">${g.huellas ? `🖐️ ${g.huellas}` : ''} ${g.caras ? `🙂 ${g.caras}` : ''}${!g.huellas && !g.caras ? '<span style=\"color:var(--muted);\">—</span>' : ''}\n              ${g.creado_por_red ? '<div style=\"font-size:10px; color:#5B9BD5;\">🌐 por la red</div>' : ''}</td>\n",
   "              ? `<div style=\"font-size:10px; color:#e8a33d; font-weight:700;\">${rhSinMicrosip() ? 'No. emp.' : 'Microsip'}: ${escapeHtml(asis_normNum(g.usuario_numero))}</div>` : ''}</td>\n            <td>${escapeHtml(g.nombre_checador || '—')}</td>\n            <td><input id=\"gnom_${g.id}\" value=\"${escapeHtml(g.nombre || '')}\" placeholder=\"${escapeHtml(g.nombre_checador || 'Nombre completo')}\" style=\"font-size:12px; min-width:160px;\" /></td>\n            <td>${g.usuario_id ? `<div id=\"gvin_${g.id}\" style=\"display:flex; gap:6px; align-items:center;\">\n                  <span>🔗 <b>${escapeHtml(g.usuario_nombre || (usuarios.find(u => u.id === g.usuario_id) || {}).nombre || 'Ligado')}</b></span>\n                  <button class=\"secondary\" style=\"font-size:11px; padding:2px 8px;\" title=\"Me equivoqué: ligar este número a otra persona o desligarlo\" onclick=\"asis_cambiarVinculo(${g.id})\">✏️ Cambiar</button></div>` : ''}\n              <select id=\"gusr_${g.id}\" style=\"font-size:12px; min-width:200px; max-width:280px; ${g.usuario_id ? 'display:none;' : ''}\">${asis_opcionesUsuarios(usuarios, g.usuario_id, g.nombre || g.nombre_checador)}</select>\n              ${g.usuario_id ? '' : '<div style=\"font-size:10px; color:#e8a33d;\">sin ligar</div>'}</td>\n            <td style=\"white-space:nowrap;\">${g.huellas ? `🖐️ ${g.huellas}` : ''} ${g.caras ? `🙂 ${g.caras}` : ''}${!g.huellas && !g.caras ? '<span style=\"color:var(--muted);\">—</span>' : ''}\n              ${g.creado_por_red ? '<div style=\"font-size:10px; color:#5B9BD5;\">🌐 por la red</div>' : ''}</td>\n"
  ],
  [
   "    } catch (e) { caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\nasync function asis_guardarGente(id, btn) {\n  const uid = Number(document.getElementById(`gusr_${id}`).value || 0) || null;\n  const nombre = document.getElementById(`gnom_${id}`).value.trim() || null;\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      await api(`/api/rh/checadores/gente/${id}`, { method: 'PATCH', body: JSON.stringify({ usuario_id: uid, nombre }) });\n      const g = ASIS_GENTE.gente.find(x => x.id === id);\n      Object.assign(g, { usuario_id: uid, nombre });\n      btn.textContent = '✔ Guardado';\n    } catch (e) { alert(e.message); }\n  });\n",
   "    } catch (e) { caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\n// \"✏️ Cambiar\": muestra la lista para ligar ese número a otra persona (o desligarlo).\nfunction asis_cambiarVinculo(id) {\n  const vin = document.getElementById(`gvin_${id}`);\n  const sel = document.getElementById(`gusr_${id}`);\n  if (vin) vin.style.display = 'none';\n  if (sel) { sel.style.display = ''; sel.focus(); }\n}\n\nasync function asis_guardarGente(id, btn) {\n  const uid = Number(document.getElementById(`gusr_${id}`).value || 0) || null;\n  let nombre = document.getElementById(`gnom_${id}`).value.trim() || null;\n  const g = ASIS_GENTE.gente.find(x => x.id === id);\n  const nombreDe = u => ((ASIS_GENTE.usuarios || []).find(x => x.id === u) || {}).nombre || 'otra persona';\n  // Si cambia el vínculo y no tocaron el \"Nombre corregido\", ese nombre era del anterior: se pone el de la nueva persona.\n  if (g && g.usuario_id && g.usuario_id !== uid && nombre === (g.nombre || null)) nombre = uid ? nombreDe(uid) : null;\n  if (g && g.usuario_id && g.usuario_id !== uid) {\n    const otro = uid && ASIS_GENTE.gente.find(x => x.id !== id && x.sn === g.sn && x.usuario_id === uid && !x.baja_en);\n    const msg = uid\n      ? `¿Cambiar el No. ${g.codigo} de este checador de ${g.usuario_nombre || nombreDe(g.usuario_id)} a ${nombreDe(uid)}?\\n\\nSus checadas en este checador pasan a ${nombreDe(uid)} y a cada uno se le recalcula su nave.`\n        + (otro ? `\\n\\n⚠️ ${nombreDe(uid)} ya está ligado al No. ${otro.codigo} en este mismo checador: revisa cuál número es el bueno.` : '')\n      : `¿Desligar el No. ${g.codigo} de ${g.usuario_nombre || nombreDe(g.usuario_id)}? Sus checadas en este checador dejan de contarle.`;\n    if (!confirm(msg)) return;\n  }\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      const r = await api(`/api/rh/checadores/gente/${id}`, { method: 'PATCH', body: JSON.stringify({ usuario_id: uid, nombre }) });\n      Object.assign(g, { usuario_id: uid, nombre, usuario_nombre: uid ? nombreDe(uid) : null,\n                         usuario_numero: uid ? ((ASIS_GENTE.usuarios || []).find(x => x.id === uid) || {}).numero_empleado : null });\n      if (r && r.cambio_vinculo) {\n        const filtro = (document.querySelector('#modalContent input[placeholder^=\"Buscar\"]') || {}).value || '';\n        asis_pintarGente(filtro);\n        const numMal = uid && g.usuario_numero && asis_normNum(g.usuario_numero) !== asis_normNum(g.codigo);\n        alert('✔ Vínculo cambiado.' + (r.nave ? `\\n🏭 ${r.nave.nombre} quedó en ${r.nave.a}.` : '')\n          + (numMal ? `\\n\\nOjo: en el checador tiene el No. ${g.codigo} y su No. de empleado es ${asis_normNum(g.usuario_numero)}. Usa «Ver qué cambia» / «Poner el No. de empleado» (Paso 0) para corregirlo en el checador.` : ''));\n        return;\n      }\n      btn.textContent = '✔ Guardado';\n    } catch (e) { alert(e.message); }\n  });\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_cambiar_vinculo_checador.py")
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
