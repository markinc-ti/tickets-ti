# -*- coding: utf-8 -*-
"""
CONCURSO: BORRAR CONCURSO Y VOTOS CON NOMBRE PARA LOS JUECES
- En Administrar: boton "Borrar concurso" (pide confirmar y escribir BORRAR);
  borra ofrendas, equipos, jueces y votos.
- En Resultados en vivo (jueces y admin): tabla "Quien voto y por cual" con el
  nombre del votante, su equipo, la ofrenda por la que voto y la hora, con
  buscador; y la lista de integrantes de equipos que aun no votan.
REQUIERE haber corrido antes fix_concurso_calaverita.py.
Toca: backend/db.py, backend/app.py, frontend/concurso.html
Se puede correr varias veces.  Correr con:  py -3 fix_concurso_borrar_y_votantes.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    cur.execute(\"\"\"SELECT v.votado_en, o.nombre AS ofrenda FROM concurso_votos v JOIN concurso_ofrendas o ON o.id = v.ofrenda_id\n                   WHERE v.concurso_id = %s ORDER BY v.votado_en DESC LIMIT 15\"\"\", (concurso_id,))\n    ultimos = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return {\"ofrendas\": ofrendas, \"total_votos\": total, \"elegibles\": elegibles, \"por_equipo\": por_equipo, \"ultimos\": ultimos}\n\n\ndef eliminar_cotizacion_costos(cotizacion_id):\n",
   "    cur.execute(\"\"\"SELECT v.votado_en, o.nombre AS ofrenda FROM concurso_votos v JOIN concurso_ofrendas o ON o.id = v.ofrenda_id\n                   WHERE v.concurso_id = %s ORDER BY v.votado_en DESC LIMIT 15\"\"\", (concurso_id,))\n    ultimos = [dict(x) for x in cur.fetchall()]\n    # Para los jueces: quién votó, de qué equipo es y por cuál ofrenda.\n    cur.execute(\"\"\"SELECT u.nombre_completo AS votante, eq.nombre AS equipo, o.nombre AS ofrenda, v.votado_en\n                   FROM concurso_votos v\n                   JOIN users u ON u.id = v.usuario_id\n                   JOIN concurso_ofrendas o ON o.id = v.ofrenda_id\n                   LEFT JOIN concurso_integrantes i ON i.concurso_id = v.concurso_id AND i.usuario_id = v.usuario_id\n                   LEFT JOIN concurso_ofrendas eq ON eq.id = i.ofrenda_id\n                   WHERE v.concurso_id = %s ORDER BY v.votado_en DESC\"\"\", (concurso_id,))\n    detalle = [dict(x) for x in cur.fetchall()]\n    # Integrantes de equipos que todavía no votan.\n    cur.execute(\"\"\"SELECT u.nombre_completo AS nombre, o.nombre AS equipo FROM concurso_integrantes i\n                   JOIN users u ON u.id = i.usuario_id JOIN concurso_ofrendas o ON o.id = i.ofrenda_id\n                   WHERE i.concurso_id = %s AND NOT EXISTS (SELECT 1 FROM concurso_votos v WHERE v.concurso_id = i.concurso_id AND v.usuario_id = i.usuario_id)\n                   ORDER BY o.orden, o.id, u.nombre_completo\"\"\", (concurso_id,))\n    faltan = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return {\"ofrendas\": ofrendas, \"total_votos\": total, \"elegibles\": elegibles, \"por_equipo\": por_equipo, \"ultimos\": ultimos,\n            \"detalle\": detalle, \"faltan_equipos\": faltan}\n\n\ndef eliminar_concurso(concurso_id, empresa_id):\n    \"\"\"Borra el concurso con sus ofrendas, equipos, jueces y votos (los videos se quedan en R2).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM concursos WHERE id = %s AND empresa_id = %s\", (concurso_id, empresa_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef eliminar_cotizacion_costos(cotizacion_id):\n"
  ]
 ],
 "backend/app.py": [
  [
   "    c = _concurso_de_mi_empresa(concurso_id, usuario)\n    if usuario[\"rol\"] != \"admin\" and not db.estado_votante_concurso(concurso_id, usuario[\"id\"])[\"es_juez\"]:\n        raise HTTPException(status_code=403, detail=\"Solo los jueces pueden ver los resultados\")\n    return {**db.resultados_concurso(concurso_id, c[\"empresa_id\"]), \"abierto\": c[\"abierto\"], \"termina_en\": c.get(\"termina_en\")}\n\n\n# ---- Administración del concurso (admin de la empresa) ----\n",
   "    c = _concurso_de_mi_empresa(concurso_id, usuario)\n    if usuario[\"rol\"] != \"admin\" and not db.estado_votante_concurso(concurso_id, usuario[\"id\"])[\"es_juez\"]:\n        raise HTTPException(status_code=403, detail=\"Solo los jueces pueden ver los resultados\")\n    # Los jueces y el admin ven quién votó y por cuál ofrenda.\n    return {**db.resultados_concurso(concurso_id, c[\"empresa_id\"]), \"abierto\": c[\"abierto\"], \"termina_en\": c.get(\"termina_en\")}\n\n\n@app.delete(\"/api/concursos/{concurso_id}\")\ndef api_eliminar_concurso(concurso_id: int, usuario: dict = Depends(requiere_admin)):\n    \"\"\"Borra el concurso completo (ofrendas, equipos, jueces y votos).\"\"\"\n    _concurso_de_mi_empresa(concurso_id, usuario)\n    db.eliminar_concurso(concurso_id, usuario[\"empresa_id\"])\n    return {\"ok\": True}\n\n\n# ---- Administración del concurso (admin de la empresa) ----\n"
  ]
 ],
 "frontend/concurso.html": [
  [
   "(function(){\nconst P = new URLSearchParams(location.search);\nlet CID = Number(P.get('c')) || null;\nlet CONCURSO = null, ESTADO = null, TAB = 'votar', ADMIN = null, TIMER = null;\n\nconst $ = id => document.getElementById(id);\nconst esc = t => String(t == null ? '' : t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n",
   "(function(){\nconst P = new URLSearchParams(location.search);\nlet CID = Number(P.get('c')) || null;\nlet CONCURSO = null, ESTADO = null, TAB = 'votar', ADMIN = null, TIMER = null, FILTRO_VOTOS = '';\n\nconst $ = id => document.getElementById(id);\nconst esc = t => String(t == null ? '' : t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
  ],
  [
   "async function vistaResultados(){\n  const pintar = async () => {\n    let r;\n    try { r = await api('/api/concursos/' + CID + '/resultados'); } catch(e){ $('vista').innerHTML = `<div class=\"card\">${esc(e.message)}</div>`; return; }\n    const max = Math.max(1, ...r.ofrendas.map(o => o.votos));\n    const pct = r.elegibles ? Math.round(r.total_votos / r.elegibles * 100) : 0;\n",
   "async function vistaResultados(){\n  const pintar = async () => {\n    let r;\n    const enfocado = document.activeElement && document.activeElement.id === 'rs_f';\n    try { r = await api('/api/concursos/' + CID + '/resultados'); } catch(e){ $('vista').innerHTML = `<div class=\"card\">${esc(e.message)}</div>`; return; }\n    const max = Math.max(1, ...r.ofrendas.map(o => o.votos));\n    const pct = r.elegibles ? Math.round(r.total_votos / r.elegibles * 100) : 0;\n"
  ],
  [
   "          <tbody>${r.por_equipo.map(x => `<tr><td>${esc(x.nombre)}</td><td>${x.integrantes}</td><td>${x.ya_votaron}</td></tr>`).join('')}</tbody></table></div>\n        <div class=\"card\"><b>Últimos votos</b>\n          <table style=\"margin-top:8px\"><tbody>${r.ultimos.map(x => `<tr><td class=\"mini\">${esc(String(x.votado_en).slice(5,16).replace('T',' '))}</td><td>${esc(x.ofrenda)}</td></tr>`).join('') || '<tr><td class=\"mini\">Aún no hay votos</td></tr>'}</tbody></table>\n          <div class=\"mini\" style=\"margin-top:6px\">No se muestra quién votó por quién: el voto es secreto.</div></div>\n      </div>`;\n  };\n  $('vista').innerHTML = '<div class=\"card\">Cargando resultados…</div>';\n  await pintar();\n",
   "          <tbody>${r.por_equipo.map(x => `<tr><td>${esc(x.nombre)}</td><td>${x.integrantes}</td><td>${x.ya_votaron}</td></tr>`).join('')}</tbody></table></div>\n        <div class=\"card\"><b>Últimos votos</b>\n          <table style=\"margin-top:8px\"><tbody>${r.ultimos.map(x => `<tr><td class=\"mini\">${esc(String(x.votado_en).slice(5,16).replace('T',' '))}</td><td>${esc(x.ofrenda)}</td></tr>`).join('') || '<tr><td class=\"mini\">Aún no hay votos</td></tr>'}</tbody></table>\n          </div>\n      </div>\n      <div class=\"card\" style=\"margin-top:14px\">\n        <div style=\"display:flex;gap:8px;align-items:center;flex-wrap:wrap\"><b style=\"flex:1\">🗳️ Quién votó y por cuál (${r.detalle.length})</b>\n          <input id=\"rs_f\" placeholder=\"Buscar nombre, equipo u ofrenda…\" style=\"max-width:300px\" value=\"${esc(FILTRO_VOTOS)}\"></div>\n        <div style=\"max-height:420px;overflow:auto;margin-top:8px\"><table><thead><tr><th>Votante</th><th>Su equipo</th><th>Votó por</th><th>Hora</th></tr></thead>\n          <tbody id=\"rs_tb\">${r.detalle.map(x => `<tr data-b=\"${esc((x.votante + ' ' + (x.equipo || '') + ' ' + x.ofrenda).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase())}\">\n            <td>${esc(x.votante)}</td><td class=\"mini\">${esc(x.equipo || '— sin equipo —')}</td><td><b>${esc(x.ofrenda)}</b></td>\n            <td class=\"mini\">${esc(String(x.votado_en).slice(5,16).replace('T',' '))}</td></tr>`).join('') || '<tr><td class=\"mini\" colspan=\"4\">Aún no hay votos</td></tr>'}</tbody></table></div>\n      </div>\n      ${r.faltan_equipos.length ? `<details class=\"card\" style=\"margin-top:14px\"><summary style=\"cursor:pointer\"><b>⏳ Integrantes de equipos que aún no votan (${r.faltan_equipos.length})</b></summary>\n        <table style=\"margin-top:8px\"><tbody>${r.faltan_equipos.map(x => `<tr><td>${esc(x.nombre)}</td><td class=\"mini\">${esc(x.equipo)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;\n    const inp = $('rs_f');\n    const filtrar = () => { const f = inp.value.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim(); FILTRO_VOTOS = inp.value;\n      $('rs_tb').querySelectorAll('tr[data-b]').forEach(tr => tr.style.display = !f || tr.dataset.b.includes(f) ? '' : 'none'); };\n    inp.oninput = filtrar; filtrar();\n    if (enfocado) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }\n  };\n  $('vista').innerHTML = '<div class=\"card\">Cargando resultados…</div>';\n  await pintar();\n"
  ],
  [
   "      </div>\n      <label style=\"display:flex;gap:8px;align-items:center;margin-top:12px;font-size:14px\"><input type=\"checkbox\" id=\"ad_res\" style=\"width:auto\" ${c && c.mostrar_resultados ? 'checked' : ''}> Al cerrar, mostrar el ganador a todos en la página</label>\n      <label style=\"display:flex;gap:8px;align-items:center;margin-top:6px;font-size:14px\"><input type=\"checkbox\" id=\"ad_act\" style=\"width:auto\" ${!c || c.activo ? 'checked' : ''}> Concurso visible (apágalo al terminar la semana para quitarlo)</label>\n      <button class=\"btn pri\" style=\"margin-top:12px\" id=\"ad_guardar\">${c ? 'Guardar cambios' : 'Crear concurso'}</button>\n    </div>\n    ${c ? `\n    <div class=\"card\" style=\"margin-bottom:14px\">\n",
   "      </div>\n      <label style=\"display:flex;gap:8px;align-items:center;margin-top:12px;font-size:14px\"><input type=\"checkbox\" id=\"ad_res\" style=\"width:auto\" ${c && c.mostrar_resultados ? 'checked' : ''}> Al cerrar, mostrar el ganador a todos en la página</label>\n      <label style=\"display:flex;gap:8px;align-items:center;margin-top:6px;font-size:14px\"><input type=\"checkbox\" id=\"ad_act\" style=\"width:auto\" ${!c || c.activo ? 'checked' : ''}> Concurso visible (apágalo al terminar la semana para quitarlo)</label>\n      <div style=\"display:flex;gap:8px;flex-wrap:wrap;margin-top:12px\">\n        <button class=\"btn pri\" id=\"ad_guardar\">${c ? 'Guardar cambios' : 'Crear concurso'}</button>\n        ${c ? '<span style=\"flex:1\"></span><button class=\"btn\" id=\"ad_borrar\" style=\"color:var(--peligro)\">🗑️ Borrar concurso</button>' : ''}\n      </div>\n    </div>\n    ${c ? `\n    <div class=\"card\" style=\"margin-bottom:14px\">\n"
  ],
  [
   "    } catch(e){ toast(e.message); }\n  };\n  if (!c) return;\n  try { new QRCode($('ad_qr'), { text: liga, width: 132, height: 132 }); } catch(e){ $('ad_qr').style.display = 'none'; }\n  $('ad_copiar').onclick = () => { navigator.clipboard.writeText(liga).then(() => toast('Liga copiada')); };\n  $('ad_nueva').onclick = async () => {\n",
   "    } catch(e){ toast(e.message); }\n  };\n  if (!c) return;\n  $('ad_borrar').onclick = async () => {\n    if (!confirm(`¿Borrar el concurso \"${c.nombre}\"?\\n\\nSe borran sus ofrendas, equipos, jueces y TODOS los votos. No se puede deshacer.`)) return;\n    if ((prompt('Para confirmar escribe BORRAR') || '').trim().toUpperCase() !== 'BORRAR') { toast('No se borró'); return; }\n    try {\n      await api('/api/concursos/' + CID, { method:'DELETE' });\n      toast('Concurso borrado'); CID = null; CONCURSO = null; history.replaceState(null, '', location.pathname);\n      await cargar(); TAB = 'admin'; pintarTabs(); vistaAdmin();\n    } catch(e){ toast(e.message); }\n  };\n  try { new QRCode($('ad_qr'), { text: liga, width: 132, height: 132 }); } catch(e){ $('ad_qr').style.display = 'none'; }\n  $('ad_copiar').onclick = () => { navigator.clipboard.writeText(liga).then(() => toast('Liga copiada')); };\n  $('ad_nueva').onclick = async () => {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_concurso_borrar_y_votantes.py")
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
