# -*- coding: utf-8 -*-
"""
CONCURSO: BORRAR VOTOS (ADMINISTRADOR)
En el concurso, pestana "Resultados en vivo" -> tabla "Quien voto y por cual":
el administrador ve un boton "Borrar voto" en cada renglon (esa persona puede
volver a votar) y "Borrar todos los votos" para quitar las pruebas antes de
empezar (pide escribir BORRAR). Los jueces no ven esos botones.
Toca: backend/db.py, backend/app.py, frontend/concurso.html
Se puede correr varias veces.  Correr con:  py -3 fix_concurso_borrar_votos.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    cur.close(); conn.close()\n\n\ndef resultados_concurso(concurso_id, empresa_id):\n    \"\"\"Votos por ofrenda, participación total y por equipo, y los últimos votos (sin decir quién votó por quién).\"\"\"\n    conn = get_connection()\n",
   "    cur.close(); conn.close()\n\n\ndef borrar_votos_concurso(concurso_id, usuario_id=None):\n    \"\"\"Borra el voto de una persona (usuario_id) o, sin usuario_id, todos los votos del concurso.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    if usuario_id:\n        cur.execute(\"DELETE FROM concurso_votos WHERE concurso_id = %s AND usuario_id = %s\", (concurso_id, usuario_id))\n    else:\n        cur.execute(\"DELETE FROM concurso_votos WHERE concurso_id = %s\", (concurso_id,))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef resultados_concurso(concurso_id, empresa_id):\n    \"\"\"Votos por ofrenda, participación total y por equipo, y los últimos votos (sin decir quién votó por quién).\"\"\"\n    conn = get_connection()\n"
  ],
  [
   "                   WHERE v.concurso_id = %s ORDER BY v.votado_en DESC LIMIT 15\"\"\", (concurso_id,))\n    ultimos = [dict(x) for x in cur.fetchall()]\n    # Para los jueces: quién votó, de qué equipo es y por cuál ofrenda.\n    cur.execute(\"\"\"SELECT u.nombre_completo AS votante, eq.nombre AS equipo, o.nombre AS ofrenda, v.votado_en\n                   FROM concurso_votos v\n                   JOIN users u ON u.id = v.usuario_id\n                   JOIN concurso_ofrendas o ON o.id = v.ofrenda_id\n",
   "                   WHERE v.concurso_id = %s ORDER BY v.votado_en DESC LIMIT 15\"\"\", (concurso_id,))\n    ultimos = [dict(x) for x in cur.fetchall()]\n    # Para los jueces: quién votó, de qué equipo es y por cuál ofrenda.\n    cur.execute(\"\"\"SELECT v.usuario_id, u.nombre_completo AS votante, eq.nombre AS equipo, o.nombre AS ofrenda, v.votado_en\n                   FROM concurso_votos v\n                   JOIN users u ON u.id = v.usuario_id\n                   JOIN concurso_ofrendas o ON o.id = v.ofrenda_id\n"
  ]
 ],
 "backend/app.py": [
  [
   "        raise HTTPException(status_code=403, detail=\"Solo los jueces pueden ver los resultados\")\n    # Los jueces y el admin ven quién votó y por cuál ofrenda.\n    return {**db.resultados_concurso(concurso_id, c[\"empresa_id\"]), \"abierto\": c[\"abierto\"], \"termina_en\": c.get(\"termina_en\")}\n\n\n@app.delete(\"/api/concursos/{concurso_id}\")\n",
   "        raise HTTPException(status_code=403, detail=\"Solo los jueces pueden ver los resultados\")\n    # Los jueces y el admin ven quién votó y por cuál ofrenda.\n    return {**db.resultados_concurso(concurso_id, c[\"empresa_id\"]), \"abierto\": c[\"abierto\"], \"termina_en\": c.get(\"termina_en\")}\n\n\n@app.delete(\"/api/concursos/{concurso_id}/votos/{votante_id}\")\ndef api_borrar_voto_concurso(concurso_id: int, votante_id: int, usuario: dict = Depends(requiere_admin)):\n    \"\"\"El admin borra el voto de una persona (ej. una prueba); esa persona puede volver a votar.\"\"\"\n    _concurso_de_mi_empresa(concurso_id, usuario)\n    if not db.borrar_votos_concurso(concurso_id, votante_id):\n        raise HTTPException(status_code=404, detail=\"Esa persona no tiene voto en este concurso\")\n    return {\"ok\": True}\n\n\n@app.delete(\"/api/concursos/{concurso_id}/votos\")\ndef api_borrar_todos_votos_concurso(concurso_id: int, usuario: dict = Depends(requiere_admin)):\n    \"\"\"El admin borra TODOS los votos (para empezar de cero después de probar).\"\"\"\n    _concurso_de_mi_empresa(concurso_id, usuario)\n    return {\"ok\": True, \"borrados\": db.borrar_votos_concurso(concurso_id)}\n\n\n@app.delete(\"/api/concursos/{concurso_id}\")\n"
  ]
 ],
 "frontend/concurso.html": [
  [
   "    let r;\n    const enfocado = document.activeElement && document.activeElement.id === 'rs_f';\n    try { r = await api('/api/concursos/' + CID + '/resultados'); } catch(e){ $('vista').innerHTML = `<div class=\"card\">${esc(e.message)}</div>`; return; }\n    const max = Math.max(1, ...r.ofrendas.map(o => o.votos));\n    const pct = r.elegibles ? Math.round(r.total_votos / r.elegibles * 100) : 0;\n    $('vista').innerHTML = `\n",
   "    let r;\n    const enfocado = document.activeElement && document.activeElement.id === 'rs_f';\n    try { r = await api('/api/concursos/' + CID + '/resultados'); } catch(e){ $('vista').innerHTML = `<div class=\"card\">${esc(e.message)}</div>`; return; }\n    const esAdm = !!(ESTADO && ESTADO.es_admin);\n    const max = Math.max(1, ...r.ofrendas.map(o => o.votos));\n    const pct = r.elegibles ? Math.round(r.total_votos / r.elegibles * 100) : 0;\n    $('vista').innerHTML = `\n"
  ],
  [
   "      </div>\n      <div class=\"card\" style=\"margin-top:14px\">\n        <div style=\"display:flex;gap:8px;align-items:center;flex-wrap:wrap\"><b style=\"flex:1\">🗳️ Quién votó y por cuál (${r.detalle.length})</b>\n          <input id=\"rs_f\" placeholder=\"Buscar nombre, equipo u ofrenda…\" style=\"max-width:300px\" value=\"${esc(FILTRO_VOTOS)}\"></div>\n        <div style=\"max-height:420px;overflow:auto;margin-top:8px\"><table><thead><tr><th>Votante</th><th>Su equipo</th><th>Votó por</th><th>Hora</th></tr></thead>\n          <tbody id=\"rs_tb\">${r.detalle.map(x => `<tr data-b=\"${esc((x.votante + ' ' + (x.equipo || '') + ' ' + x.ofrenda).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase())}\">\n            <td>${esc(x.votante)}</td><td class=\"mini\">${esc(x.equipo || '— sin equipo —')}</td><td><b>${esc(x.ofrenda)}</b></td>\n            <td class=\"mini\">${esc(String(x.votado_en).slice(5,16).replace('T',' '))}</td></tr>`).join('') || '<tr><td class=\"mini\" colspan=\"4\">Aún no hay votos</td></tr>'}</tbody></table></div>\n      </div>\n      ${r.faltan_equipos.length ? `<details class=\"card\" style=\"margin-top:14px\"><summary style=\"cursor:pointer\"><b>⏳ Integrantes de equipos que aún no votan (${r.faltan_equipos.length})</b></summary>\n        <table style=\"margin-top:8px\"><tbody>${r.faltan_equipos.map(x => `<tr><td>${esc(x.nombre)}</td><td class=\"mini\">${esc(x.equipo)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;\n",
   "      </div>\n      <div class=\"card\" style=\"margin-top:14px\">\n        <div style=\"display:flex;gap:8px;align-items:center;flex-wrap:wrap\"><b style=\"flex:1\">🗳️ Quién votó y por cuál (${r.detalle.length})</b>\n          <input id=\"rs_f\" placeholder=\"Buscar nombre, equipo u ofrenda…\" style=\"max-width:300px\" value=\"${esc(FILTRO_VOTOS)}\">\n          ${esAdm && r.detalle.length ? '<button class=\"btn\" id=\"rs_borrar_todos\" style=\"color:var(--peligro)\">🗑️ Borrar todos los votos</button>' : ''}</div>\n        <div style=\"max-height:420px;overflow:auto;margin-top:8px\"><table><thead><tr><th>Votante</th><th>Su equipo</th><th>Votó por</th><th>Hora</th>${esAdm ? '<th></th>' : ''}</tr></thead>\n          <tbody id=\"rs_tb\">${r.detalle.map(x => `<tr data-b=\"${esc((x.votante + ' ' + (x.equipo || '') + ' ' + x.ofrenda).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase())}\">\n            <td>${esc(x.votante)}</td><td class=\"mini\">${esc(x.equipo || '— sin equipo —')}</td><td><b>${esc(x.ofrenda)}</b></td>\n            <td class=\"mini\">${esc(String(x.votado_en).slice(5,16).replace('T',' '))}</td>\n            ${esAdm ? `<td><button class=\"btn\" style=\"padding:4px 10px;font-size:12px;color:var(--peligro)\" data-borrarvoto=\"${x.usuario_id}\" data-nom=\"${esc(x.votante)}\" title=\"Borrar este voto (la persona puede volver a votar)\">🗑️ Borrar voto</button></td>` : ''}</tr>`).join('') || '<tr><td class=\"mini\" colspan=\"5\">Aún no hay votos</td></tr>'}</tbody></table></div>\n      </div>\n      ${r.faltan_equipos.length ? `<details class=\"card\" style=\"margin-top:14px\"><summary style=\"cursor:pointer\"><b>⏳ Integrantes de equipos que aún no votan (${r.faltan_equipos.length})</b></summary>\n        <table style=\"margin-top:8px\"><tbody>${r.faltan_equipos.map(x => `<tr><td>${esc(x.nombre)}</td><td class=\"mini\">${esc(x.equipo)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;\n"
  ],
  [
   "    const filtrar = () => { const f = inp.value.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim(); FILTRO_VOTOS = inp.value;\n      $('rs_tb').querySelectorAll('tr[data-b]').forEach(tr => tr.style.display = !f || tr.dataset.b.includes(f) ? '' : 'none'); };\n    inp.oninput = filtrar; filtrar();\n    if (enfocado) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }\n  };\n  $('vista').innerHTML = '<div class=\"card\">Cargando resultados…</div>';\n",
   "    const filtrar = () => { const f = inp.value.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim(); FILTRO_VOTOS = inp.value;\n      $('rs_tb').querySelectorAll('tr[data-b]').forEach(tr => tr.style.display = !f || tr.dataset.b.includes(f) ? '' : 'none'); };\n    inp.oninput = filtrar; filtrar();\n    $('vista').querySelectorAll('[data-borrarvoto]').forEach(b => b.onclick = async () => {\n      if (!confirm(`¿Borrar el voto de ${b.dataset.nom}?\\nPodrá volver a votar.`)) return;\n      b.disabled = true;\n      try { await api('/api/concursos/' + CID + '/votos/' + b.dataset.borrarvoto, { method:'DELETE' }); toast('Voto borrado'); await pintar(); }\n      catch(e){ toast(e.message); b.disabled = false; }\n    });\n    if ($('rs_borrar_todos')) $('rs_borrar_todos').onclick = async () => {\n      if (!confirm(`¿Borrar TODOS los votos (${r.detalle.length}) de este concurso?\\nÚsalo solo para quitar las pruebas antes de empezar. No se puede deshacer.`)) return;\n      if (prompt('Para confirmar escribe BORRAR') !== 'BORRAR') return toast('No se borró nada');\n      try { const x = await api('/api/concursos/' + CID + '/votos', { method:'DELETE' }); toast(`Se borraron ${x.borrados} votos`); await pintar(); }\n      catch(e){ toast(e.message); }\n    };\n    if (enfocado) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }\n  };\n  $('vista').innerHTML = '<div class=\"card\">Cargando resultados…</div>';\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_concurso_borrar_votos.py")
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
