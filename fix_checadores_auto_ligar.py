# -*- coding: utf-8 -*-
"""
CHECADORES: LIGAR SOLOS POR NUMERO Y NOMBRE + CHECADOR COMPARTIDO POR VARIAS NAVES
- Boton "Ligar solos (numero y nombre)" en Personas de los checadores y en el
  aviso de Asistencia: liga a quien su numero del checador = No. de empleado y
  su nombre coincide, o cuyo nombre coincide con UNA sola persona. Muestra antes
  la lista y lo que queda por revisar a mano (con el motivo).
- Al leer la gente de un checador se liga solo a quien coincide numero Y nombre.
- "Nave 4-5" (o 4 – 5, 4/5, 4 y 5) cuando existen Nave 4 y Nave 5: se reconoce
  como checador compartido; cada quien conserva su nave. Y "NAVE 3" = "Nave 3".
REQUIERE haber corrido antes fix_rh_apartar_gente_checador.py.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_checadores_auto_ligar.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "\n\ndef _clave_nave(t):\n    return \" \".join(str(t or \"\").strip().lower().split())\n\n\ndef naves_de_checadores(empresa_id):\n",
   "\n\ndef _clave_nave(t):\n    \"\"\"'NAVE 4 – 5', 'nave 4-5', 'Nave  4/5' -> 'nave 4-5' (sin mayúsculas, espacios ni tipos de guion).\"\"\"\n    t = str(t or \"\").strip().lower()\n    t = re.sub(r\"\\s*[-–—/·,y]\\s*(?=\\d)\", \"-\", t)   # 4 – 5 / 4/5 / 4 y 5 -> 4-5\n    return \" \".join(t.split())\n\n\ndef _naves_en_texto(texto, sucursales):\n    \"\"\"'Nave 4-5' cuando existen 'Nave 4' y 'Nave 5' -> esas dos (checador compartido).\"\"\"\n    m = re.match(r\"^(.*?)(\\d+(?:-\\d+)+)$\", _clave_nave(texto))\n    if not m:\n        return []\n    base = m.group(1).strip()\n    por_nombre = {_clave_nave(x[\"nombre\"]): x for x in sucursales}\n    halladas = [por_nombre.get(f\"{base} {n}\".strip()) for n in m.group(2).split(\"-\")]\n    return [x for x in halladas if x] if all(halladas) else []\n\n\ndef naves_de_checadores(empresa_id):\n"
  ],
  [
   "        suc = por_nombre.get(_clave_nave(k.get(\"sucursal\")))\n        k[\"sucursal_id\"] = suc[\"id\"] if suc else None\n        k[\"sucursal_nombre\"] = suc[\"nombre\"] if suc else None\n    return {\"sucursales\": sucursales, \"checadores\": checadores}\n\n\n",
   "        suc = por_nombre.get(_clave_nave(k.get(\"sucursal\")))\n        k[\"sucursal_id\"] = suc[\"id\"] if suc else None\n        k[\"sucursal_nombre\"] = suc[\"nombre\"] if suc else None\n        # Checador compartido por varias naves (ej. \"Nave 4-5\"): no cambia la nave de su gente.\n        k[\"naves_compartidas\"] = [x[\"nombre\"] for x in _naves_en_texto(k.get(\"sucursal\"), sucursales)] if not suc else []\n    return {\"sucursales\": sucursales, \"checadores\": checadores}\n\n\n"
  ]
 ],
 "backend/app.py": [
  [
   "    if tabla != \"ATTLOG\":\n        if chk and chk.get(\"empresa_id\") and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\", \"USERPIC\", \"BIOPHOTO\", \"BIODATA\"):\n            if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)) and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\"):\n                # Al jalar la gente del checador: cada persona ya ligada queda en la nave de ese checador.\n                _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n",
   "    if tabla != \"ATTLOG\":\n        if chk and chk.get(\"empresa_id\") and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\", \"USERPIC\", \"BIOPHOTO\", \"BIODATA\"):\n            if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)) and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\"):\n                # Al jalar la gente del checador: se liga sola a quien es clarísimo (mismo número y nombre)\n                # y cada persona ligada queda en la nave de ese checador.\n                try:\n                    _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n                except Exception as e:  # noqa: BLE001\n                    print(f\"[auto-ligar] {e}\")\n                _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n"
  ],
  [
   "            return _texto_plano(\"OK\")\n        cuerpo = crudo.decode(\"utf-8\", \"replace\")\n        if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)):\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n    return _texto_plano(\"OK\")\n\n",
   "            return _texto_plano(\"OK\")\n        cuerpo = crudo.decode(\"utf-8\", \"replace\")\n        if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)):\n            try:\n                _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n            except Exception as e:  # noqa: BLE001\n                print(f\"[auto-ligar] {e}\")\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n    return _texto_plano(\"OK\")\n\n"
  ],
  [
   "@app.get(\"/api/rh/checadores\")\ndef api_checadores_adms(usuario: dict = Depends(requiere_datos_empleado_rh)):\n    return db.listar_checadores_adms(usuario[\"empresa_id\"])\n\n\ndef _asignar_naves(empresa_id, **kw):\n",
   "@app.get(\"/api/rh/checadores\")\ndef api_checadores_adms(usuario: dict = Depends(requiere_datos_empleado_rh)):\n    return db.listar_checadores_adms(usuario[\"empresa_id\"])\n\n\ndef _auto_ligar_gente(empresa_id, sns=None, solo_nombre=False, aplicar=True):\n    \"\"\"Liga sola a la gente del checador que todavía no está ligada cuando es clarísimo de quién es:\n    su número en el checador = No. de empleado de UNA persona y el nombre del checador coincide con el\n    de esa persona (o el checador no trae nombre). solo_nombre=True también liga cuando el nombre\n    coincide con UNA sola persona aunque el número sea otro (solo con el botón, mostrando antes la lista).\n    No toca a los apartados (🔒), dados de baja ni a quien ya está ligado.\"\"\"\n    import importar_personal as ip\n    checadores, gente, _ = db.datos_red_checadores(empresa_id)\n    nombres_chk = {k[\"sn\"]: k.get(\"nombre\") or k[\"sn\"] for k in checadores}\n    usuarios = db.usuarios_ligables_checador(empresa_id)\n    por_numero = {}\n    for u in usuarios:\n        n = asistencia.normalizar_codigo(u.get(\"numero_empleado\"))\n        if n:\n            por_numero.setdefault(n, []).append(u)\n    toks = {u[\"id\"]: ip.tokens(u[\"nombre\"]) for u in usuarios}\n    ligados_en = {}\n    for g in gente:\n        if g.get(\"usuario_id\") and not g.get(\"baja_en\"):\n            ligados_en.setdefault(g[\"sn\"], set()).add(g[\"usuario_id\"])\n    sns = {x.upper() for x in sns} if sns else None\n    hechos, dudas = [], []\n    for g in gente:\n        if g.get(\"usuario_id\") or g.get(\"baja_en\") or g.get(\"apartado_en\") or g[\"sn\"] not in nombres_chk:\n            continue\n        if sns and g[\"sn\"] not in sns:\n            continue\n        nombre = (g.get(\"nombre\") or g.get(\"nombre_checador\") or \"\").strip()\n        cands = por_numero.get(asistencia.normalizar_codigo(g[\"codigo\"]), [])\n        elegido, motivo = None, None\n        if len(cands) == 1:\n            u = cands[0]\n            # Sin nombre en el checador solo se liga con el botón (con la lista a la vista), nunca en automático.\n            if (not nombre and solo_nombre) or (nombre and ip._coincide_checador(nombre, toks[u[\"id\"]])):\n                elegido, motivo = u, \"mismo número y nombre\" if nombre else \"mismo número (el checador no trae nombre)\"\n        if not elegido and solo_nombre and len(ip.tokens(nombre)) >= 2:\n            por_nom = [u for u in usuarios if ip._coincide_checador(nombre, toks[u[\"id\"]])]\n            if len(por_nom) == 1:\n                elegido, motivo = por_nom[0], \"el nombre coincide (el número es distinto)\"\n            elif len(por_nom) > 1:\n                dudas.append({\"checador\": nombres_chk[g[\"sn\"]], \"codigo\": g[\"codigo\"], \"nombre\": nombre,\n                              \"motivo\": \"El nombre coincide con varias personas: \" + \", \".join(u[\"nombre\"] for u in por_nom[:4])})\n        if not elegido:\n            if not solo_nombre:\n                continue\n            if not any(d[\"codigo\"] == g[\"codigo\"] and d[\"checador\"] == nombres_chk[g[\"sn\"]] for d in dudas):\n                dudas.append({\"checador\": nombres_chk[g[\"sn\"]], \"codigo\": g[\"codigo\"], \"nombre\": nombre or \"—\",\n                              \"motivo\": (\"Su número es de \" + cands[0][\"nombre\"] + \" pero el nombre no coincide\") if len(cands) == 1\n                              else \"No encontré a nadie con ese número ni con ese nombre\"})\n            continue\n        if elegido[\"id\"] in ligados_en.get(g[\"sn\"], set()):\n            dudas.append({\"checador\": nombres_chk[g[\"sn\"]], \"codigo\": g[\"codigo\"], \"nombre\": nombre,\n                          \"motivo\": f\"{elegido['nombre']} ya está ligado a otro número en este checador\"})\n            continue\n        hechos.append({\"gente_id\": g[\"id\"], \"checador\": nombres_chk[g[\"sn\"]], \"codigo\": g[\"codigo\"], \"nombre_checador\": nombre,\n                       \"usuario_id\": elegido[\"id\"], \"persona\": elegido[\"nombre\"], \"numero_empleado\": elegido.get(\"numero_empleado\"),\n                       \"motivo\": motivo})\n        ligados_en.setdefault(g[\"sn\"], set()).add(elegido[\"id\"])\n    if aplicar and hechos:\n        for h in hechos:\n            db.actualizar_gente_checador(empresa_id, h[\"gente_id\"], h[\"usuario_id\"], h[\"persona\"], None)\n        _asignar_naves(empresa_id, usuario_ids=[h[\"usuario_id\"] for h in hechos])\n    return {\"ligados\": hechos, \"dudas\": dudas}\n\n\n@app.post(\"/api/rh/checadores/auto-ligar\")\ndef api_auto_ligar_gente(simular: bool = True, por_nombre: bool = True, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Liga a la gente sin ligar cuando el número y el nombre coinciden con una persona (y, con\n    por_nombre, cuando el nombre coincide con una sola). simular=true solo muestra qué haría.\"\"\"\n    return _auto_ligar_gente(usuario[\"empresa_id\"], solo_nombre=por_nombre, aplicar=not simular)\n\n\ndef _asignar_naves(empresa_id, **kw):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <div class=\"cv-aviso\" style=\"margin-bottom:10px; font-size:12px;\">⚠️ Hay checadas de <b>${d.codigos_sin_empleado.length}</b> número(s) del checador que no corresponden a ningún usuario.\n        Cada checador tiene su propia numeración: elige a qué persona pertenece cada número <b>de ese checador</b> y toca <b>Ligar</b>\n        (⭐ = sugerido por el nombre). También puedes hacerlo en 👥 Personas de los checadores.\n        <div id=\"asis_ligar\" style=\"margin-top:8px;\"></div></div>` : ''}\n    ${(d.codigos_ligados || []).length ? `<details style=\"font-size:12px; margin-bottom:10px;\"><summary>🔗 Números del checador ligados a otra persona (${d.codigos_ligados.length})</summary>\n        ${d.codigos_ligados.map(x => `<div style=\"margin:3px 0;\">Checador <b>${escapeHtml(x.codigo)}</b> → ${escapeHtml(x.nombre)} (No. ${escapeHtml(x.numero_empleado || '—')})\n",
   "      <div class=\"cv-aviso\" style=\"margin-bottom:10px; font-size:12px;\">⚠️ Hay checadas de <b>${d.codigos_sin_empleado.length}</b> número(s) del checador que no corresponden a ningún usuario.\n        Cada checador tiene su propia numeración: elige a qué persona pertenece cada número <b>de ese checador</b> y toca <b>Ligar</b>\n        (⭐ = sugerido por el nombre). También puedes hacerlo en 👥 Personas de los checadores.\n        <div style=\"margin-top:6px;\"><button class=\"primary\" style=\"font-size:12px;\" onclick=\"asis_autoLigar(true, this, 'asis_autolig_res')\">🔗 Ligar automáticamente (número y nombre)</button></div>\n        <div id=\"asis_autolig_res\" style=\"margin-top:6px;\"></div>\n        <div id=\"asis_ligar\" style=\"margin-top:8px;\"></div></div>` : ''}\n    ${(d.codigos_ligados || []).length ? `<details style=\"font-size:12px; margin-bottom:10px;\"><summary>🔗 Números del checador ligados a otra persona (${d.codigos_ligados.length})</summary>\n        ${d.codigos_ligados.map(x => `<div style=\"margin:3px 0;\">Checador <b>${escapeHtml(x.codigo)}</b> → ${escapeHtml(x.nombre)} (No. ${escapeHtml(x.numero_empleado || '—')})\n"
  ],
  [
   "      </ol>\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n        <button class=\"secondary\" onclick=\"asis_leerTodos(this)\">1️⃣ Leer personas, huellas y caras de todos</button>\n        <button class=\"secondary\" onclick=\"asis_ligarSugeridas(this)\">⭐ Ligar todas las sugeridas</button>\n        <button class=\"secondary\" onclick=\"asis_asignarNaves(true, this)\">🏭 Asignar nave por checador</button>\n        <button class=\"secondary\" onclick=\"asis_red(true, null, this)\">2️⃣ Ver qué falta</button>\n",
   "      </ol>\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n        <button class=\"secondary\" onclick=\"asis_leerTodos(this)\">1️⃣ Leer personas, huellas y caras de todos</button>\n        <button class=\"secondary\" onclick=\"asis_autoLigar(true, this, 'asis_red_res')\">🔗 Ligar solos (número y nombre)</button>\n        <button class=\"secondary\" onclick=\"asis_ligarSugeridas(this)\">⭐ Ligar todas las sugeridas</button>\n        <button class=\"secondary\" onclick=\"asis_asignarNaves(true, this)\">🏭 Asignar nave por checador</button>\n        <button class=\"secondary\" onclick=\"asis_red(true, null, this)\">2️⃣ Ver qué falta</button>\n"
  ],
  [
   "    } catch (e) { document.getElementById('alta_res').innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\n// Liga de una vez a todas las personas sin ligar que tienen una sugerencia ⭐ (o una persona elegida en su lista).\nasync function asis_ligarSugeridas(btn) {\n  const pendientes = ASIS_GENTE.gente.filter(g => !g.usuario_id && !g.apartado_en && !g.baja_en).map(g => {\n",
   "    } catch (e) { document.getElementById('alta_res').innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\n// 🔗 Ligar solos: número del checador = No. de empleado y el nombre coincide (o el nombre coincide con\n// una sola persona). Primero muestra la lista; luego liga.\nasync function asis_autoLigar(simular, btn, idCaja) {\n  const caja = document.getElementById(idCaja);\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      const r = await api(`/api/rh/checadores/auto-ligar?simular=${simular ? 'true' : 'false'}&por_nombre=true`, { method: 'POST' });\n      if (!caja) return;\n      caja.innerHTML = `\n        ${r.ligados.length ? `<p style=\"font-size:12px; margin:4px 0;\"><b>${r.ligados.length}</b> persona(s) ${simular ? 'se ligarían' : '<span style=\"color:#4caf50;\">quedaron ligadas ✔</span>'}:</p>\n          <div style=\"max-height:240px; overflow:auto;\"><table class=\"users\" style=\"font-size:11px;\"><thead><tr><th>Checador</th><th>No.</th><th>Nombre en el checador</th><th>Es…</th><th>Por qué</th></tr></thead>\n          <tbody>${r.ligados.map(x => `<tr><td>${escapeHtml(x.checador)}</td><td>${escapeHtml(x.codigo)}</td><td>${escapeHtml(x.nombre_checador || '—')}</td>\n            <td><b>${escapeHtml(x.persona)}</b>${x.numero_empleado ? ` <span style=\"color:var(--muted);\">No. ${escapeHtml(x.numero_empleado)}</span>` : ''}</td><td style=\"color:var(--muted);\">${escapeHtml(x.motivo)}</td></tr>`).join('')}</tbody></table></div>\n          ${simular ? `<button class=\"primary\" style=\"margin-top:6px; font-size:12px;\" onclick=\"asis_autoLigar(false, this, '${idCaja}')\">✔ Ligar estas ${r.ligados.length}</button>` : ''}`\n        : '<p style=\"font-size:12px;\">No encontré a nadie que se pueda ligar solo con seguridad.</p>'}\n        ${r.dudas.length ? `<details style=\"font-size:12px; margin-top:6px;\"><summary><b>Quedan por revisar a mano (${r.dudas.length})</b></summary>\n          <table class=\"users\" style=\"font-size:11px;\"><tbody>${r.dudas.map(x => `<tr><td>${escapeHtml(x.checador)}</td><td>No. ${escapeHtml(x.codigo)}</td><td>${escapeHtml(x.nombre || '—')}</td><td style=\"color:var(--muted);\">${escapeHtml(x.motivo)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;\n      if (!simular) {\n        try { if (typeof ASIS_GENTE !== 'undefined' && ASIS_GENTE && document.getElementById('asis_red_res')) { ASIS_GENTE = Object.assign(await api('/api/rh/checadores/gente'), { comandos: ASIS_GENTE.comandos, conBajas: ASIS_GENTE.conBajas }); const html = caja.innerHTML; asis_pintarGente(); const c2 = document.getElementById(idCaja); if (c2) c2.innerHTML = html; } } catch (e) {}\n        if (idCaja === 'asis_autolig_res' && ASIS.vista) { const html = caja.innerHTML; await renderAsistenciaRH(); const c2 = document.getElementById(idCaja); if (c2) c2.innerHTML = html; }\n      }\n    } catch (e) { if (caja) caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\n\n// Liga de una vez a todas las personas sin ligar que tienen una sugerencia ⭐ (o una persona elegida en su lista).\nasync function asis_ligarSugeridas(btn) {\n  const pendientes = ASIS_GENTE.gente.filter(g => !g.usuario_id && !g.apartado_en && !g.baja_en).map(g => {\n"
  ],
  [
   "  let naves = { sucursales: [], checadores: [] };\n  try { naves = await api('/api/rh/checadores/naves'); } catch (e) {}\n  const naveDeSn = Object.fromEntries(naves.checadores.map(k => [k.sn, k.sucursal_nombre]));\n  const host = location.host;\n  const mios = lista.filter(x => x.empresa_id), sinVincular = lista.filter(x => !x.empresa_id);\n  const fila = x => `<tr>\n",
   "  let naves = { sucursales: [], checadores: [] };\n  try { naves = await api('/api/rh/checadores/naves'); } catch (e) {}\n  const naveDeSn = Object.fromEntries(naves.checadores.map(k => [k.sn, k.sucursal_nombre]));\n  const compartidas = Object.fromEntries(naves.checadores.map(k => [k.sn, k.naves_compartidas || []]));\n  const host = location.host;\n  const mios = lista.filter(x => x.empresa_id), sinVincular = lista.filter(x => !x.empresa_id);\n  const fila = x => `<tr>\n"
  ],
  [
   "      <td><input id=\"adms_nom_${x.id}\" value=\"${escapeHtml(x.nombre || '')}\" placeholder=\"ej. Checador Dentigo\" style=\"font-size:12px;\" /></td>\n      <td><input id=\"adms_suc_${x.id}\" value=\"${escapeHtml(x.sucursal || '')}\" placeholder=\"Nave / sucursal\" list=\"adms_naves_dl\" style=\"font-size:12px;\" />\n        ${x.empresa_id ? (naveDeSn[x.sn] ? `<div style=\"font-size:11px; color:#4caf50;\">✔ Nave: ${escapeHtml(naveDeSn[x.sn])}</div>`\n          : `<div style=\"font-size:11px; color:#e8a33d;\">⚠️ No coincide con ninguna nave: su gente no se asigna</div>`) : ''}</td>\n      <td style=\"font-size:12px;\">${x.ultima_conexion ? asis_hace(x.ultima_conexion) : '<span style=\"color:var(--muted);\">nunca</span>'}</td>\n      <td style=\"font-size:12px;\">${x.ultima_checada ? escapeHtml(x.ultima_checada.replace('T', ' ').slice(0, 16)) : '—'} <span style=\"color:var(--muted);\">(${x.total_checadas || 0})</span></td>\n      <td style=\"white-space:nowrap;\">\n",
   "      <td><input id=\"adms_nom_${x.id}\" value=\"${escapeHtml(x.nombre || '')}\" placeholder=\"ej. Checador Dentigo\" style=\"font-size:12px;\" /></td>\n      <td><input id=\"adms_suc_${x.id}\" value=\"${escapeHtml(x.sucursal || '')}\" placeholder=\"Nave / sucursal\" list=\"adms_naves_dl\" style=\"font-size:12px;\" />\n        ${x.empresa_id ? (naveDeSn[x.sn] ? `<div style=\"font-size:11px; color:#4caf50;\">✔ Nave: ${escapeHtml(naveDeSn[x.sn])}</div>`\n          : (compartidas[x.sn] || []).length ? `<div style=\"font-size:11px; color:#5B9BD5;\">🔀 Compartido: ${escapeHtml(compartidas[x.sn].join(' y '))}. Cada quien conserva su nave (asígnala en 👥 Personal).</div>`\n          : `<div style=\"font-size:11px; color:#e8a33d;\">⚠️ No coincide con ninguna nave (${escapeHtml(naves.sucursales.map(z => z.nombre).join(', ') || 'no hay naves')}): su gente no cambia de nave. Sus checadas sí cuentan.</div>`) : ''}</td>\n      <td style=\"font-size:12px;\">${x.ultima_conexion ? asis_hace(x.ultima_conexion) : '<span style=\"color:var(--muted);\">nunca</span>'}</td>\n      <td style=\"font-size:12px;\">${x.ultima_checada ? escapeHtml(x.ultima_checada.replace('T', ' ').slice(0, 16)) : '—'} <span style=\"color:var(--muted);\">(${x.total_checadas || 0})</span></td>\n      <td style=\"white-space:nowrap;\">\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checadores_auto_ligar.py")
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
