# -*- coding: utf-8 -*-
"""
FOTOS DE LAS CHECADAS: TAMBIEN LAS CHECADAS SIN FOTO Y PEDIR FOTOS AL CHECADOR
- En "Fotos de las checadas" ahora salen tambien las checadas del dia que no
  trajeron foto (antes decia "no hay checadas").
- Aviso de si ese checador manda fotos y cuando llego la ultima.
- Boton "Pedir al checador las fotos de este dia" (las que todavia tenga).
REQUIERE haber corrido antes fix_rh_fotos_checadas.py.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_fotos_checadas_2.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    return filas\n\n\ndef foto_de_checada(empresa_id, foto_id, referencia=False):\n    \"\"\"La foto de la checada, o (referencia=True) la foto con la que se compara: la que se le\n    registró en la app y, si no tiene, la de su ficha en el checador.\"\"\"\n",
   "    return filas\n\n\ndef checadas_sin_foto(empresa_id, dia, sn=None):\n    \"\"\"Checadas de checador directo de ese día que NO trajeron foto (para que se vean igual).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT c.equipo AS sn, c.codigo_empleado AS codigo, c.fecha_hora, k.nombre AS checador,\n               COALESCE(g.nombre, g.nombre_checador, c.nombre_checador) AS nombre_checador, u.nombre_completo AS usuario_nombre,\n               u.numero_empleado\n        FROM rh_checadas c\n        LEFT JOIN rh_checadores k ON k.sn = c.equipo\n        LEFT JOIN rh_checador_gente g ON g.empresa_id = c.empresa_id AND g.sn = c.equipo AND g.codigo = c.codigo_empleado\n        LEFT JOIN users u ON u.id = g.usuario_id\n        WHERE c.empresa_id = %s AND c.origen = 'adms' AND c.fecha_hora >= %s AND c.fecha_hora < %s\n          AND (%s::text IS NULL OR c.equipo = %s)\n          AND NOT EXISTS (SELECT 1 FROM rh_checada_fotos f WHERE f.empresa_id = c.empresa_id AND f.sn = c.equipo\n                          AND f.codigo = c.codigo_empleado AND f.fecha_hora = c.fecha_hora)\n        ORDER BY c.fecha_hora DESC\"\"\", (empresa_id, dia, dia + timedelta(days=1), sn, sn))\n    filas = []\n    for r in cur.fetchall():\n        d = dict(r)\n        d[\"fecha_hora\"] = d[\"fecha_hora\"].isoformat(timespec=\"minutes\")\n        filas.append(d)\n    cur.close(); conn.close()\n    return filas\n\n\ndef ultimas_fotos_por_checador(empresa_id):\n    \"\"\"{sn: fecha de la última foto de checada recibida} — para saber si el checador sí manda fotos.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT sn, MAX(creado_en) AS ultima FROM rh_checada_fotos WHERE empresa_id = %s GROUP BY sn\"\"\", (empresa_id,))\n    r = {x[\"sn\"]: x[\"ultima\"] for x in cur.fetchall()}\n    cur.execute(\"\"\"SELECT sn, MAX(foto_en) AS ultima FROM rh_checador_gente\n                   WHERE empresa_id = %s AND foto_origen = 'checada' GROUP BY sn\"\"\", (empresa_id,))\n    for x in cur.fetchall():\n        if x[\"ultima\"] and (not r.get(x[\"sn\"]) or x[\"ultima\"] > r[x[\"sn\"]]):\n            r[x[\"sn\"]] = x[\"ultima\"]\n    cur.close(); conn.close()\n    return r\n\n\ndef foto_de_checada(empresa_id, foto_id, referencia=False):\n    \"\"\"La foto de la checada, o (referencia=True) la foto con la que se compara: la que se le\n    registró en la app y, si no tiene, la de su ficha en el checador.\"\"\"\n"
  ]
 ],
 "backend/app.py": [
  [
   "    sn = (request.query_params.get(\"SN\") or \"\").strip().upper()\n    chk = db.checador_adms(sn) if sn else None\n    if chk and chk.get(\"empresa_id\"):\n        cuerpo = (await request.body()).decode(\"utf-8\", \"replace\")\n        if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)):\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n    return _texto_plano(\"OK\")\n",
   "    sn = (request.query_params.get(\"SN\") or \"\").strip().upper()\n    chk = db.checador_adms(sn) if sn else None\n    if chk and chk.get(\"empresa_id\"):\n        crudo = await request.body()\n        tabla_q = (request.query_params.get(\"tablename\") or request.query_params.get(\"table\") or \"\").upper()\n        foto = asistencia.leer_foto_checada(crudo) if (tabla_q == \"ATTPHOTO\" or b\"uploadphoto\" in crudo[:400].lower()) else None\n        if foto:\n            # Respuesta a \"Pedir fotos de este día\": la foto de una checada.\n            db.foto_checada_gente(chk[\"empresa_id\"], sn, foto[0], foto[1])\n            db.guardar_foto_checada(chk[\"empresa_id\"], sn, foto[0], asistencia.fecha_foto_checada(crudo), foto[1])\n            return _texto_plano(\"OK\")\n        cuerpo = crudo.decode(\"utf-8\", \"replace\")\n        if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)):\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n    return _texto_plano(\"OK\")\n"
  ],
  [
   "        dia = date.fromisoformat(fecha) if fecha else db.ahora().date()\n    except ValueError:\n        raise HTTPException(status_code=400, detail=\"Fecha inválida, usa AAAA-MM-DD\")\n    return {\"fecha\": dia.isoformat(), \"dias_guardadas\": db.DIAS_FOTOS_CHECADA,\n            \"fotos\": db.listar_fotos_checadas(usuario[\"empresa_id\"], dia, (sn or \"\").strip().upper() or None)}\n\n\n@app.get(\"/api/rh/checadores/fotos-checadas/{foto_id}\")\n",
   "        dia = date.fromisoformat(fecha) if fecha else db.ahora().date()\n    except ValueError:\n        raise HTTPException(status_code=400, detail=\"Fecha inválida, usa AAAA-MM-DD\")\n    sn = (sn or \"\").strip().upper() or None\n    return {\"fecha\": dia.isoformat(), \"dias_guardadas\": db.DIAS_FOTOS_CHECADA,\n            \"fotos\": db.listar_fotos_checadas(usuario[\"empresa_id\"], dia, sn),\n            \"sin_foto\": db.checadas_sin_foto(usuario[\"empresa_id\"], dia, sn),\n            \"ultima_foto_por_checador\": db.ultimas_fotos_por_checador(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/rh/checadores/{sn}/pedir-fotos\")\ndef api_pedir_fotos_checadas(sn: str, fecha: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Le pide al checador que vuelva a mandar las fotos de las checadas de un día (las que tenga guardadas).\n    Llegan en su siguiente conexión; no todos los modelos lo aceptan.\"\"\"\n    chk = db.checador_adms(sn)\n    if not chk or chk.get(\"empresa_id\") != usuario[\"empresa_id\"]:\n        raise HTTPException(status_code=404, detail=\"Checador no encontrado\")\n    try:\n        dia = date.fromisoformat(fecha) if fecha else db.ahora().date()\n    except ValueError:\n        raise HTTPException(status_code=400, detail=\"Fecha inválida, usa AAAA-MM-DD\")\n    db.encolar_comando_checador(chk[\"sn\"], f\"DATA QUERY ATTPHOTO StartTime={dia.isoformat()} 00:00:00\\tEndTime={dia.isoformat()} 23:59:59\")\n    return {\"ok\": True}\n\n\n@app.get(\"/api/rh/checadores/fotos-checadas/{foto_id}\")\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  const d = ASIS_FCH.datos;\n  if (!caja || !d) return;\n  const todas = d.fotos;\n  const f = ASIS_FCH.filtro;\n  const lista = todas.filter(x => f === 'todas' || (f === 'pendientes' && !x.revision) || (f === 'no_coincide' && x.revision === 'no_coincide') || (f === 'sin_ref' && !x.tiene_referencia));\n  const n = { pend: todas.filter(x => !x.revision).length, mal: todas.filter(x => x.revision === 'no_coincide').length };\n  if (!todas.length) {\n    caja.innerHTML = `<div class=\"cv-caja\" style=\"font-size:12px;\">No hay fotos de checadas este día.<br>\n      Para que lleguen, el checador debe tener activado <b>tomar foto al verificar</b> (en el checador: Menú → Sistema/Asistencia →\n      <i>Foto de verificación</i> o <i>Guardar foto al checar</i>) y estar conectado directo (📡 Conexión directa). Se guardan ${d.dias_guardadas} días.</div>`;\n    return;\n  }\n  const nombre = x => x.usuario_nombre || x.nombre_checador || `No. ${x.codigo} (sin ligar)`;\n  caja.innerHTML = `\n    <p style=\"font-size:12px; margin:0 0 8px;\"><b>${todas.length}</b> checada(s) con foto · <b style=\"color:${n.pend ? '#e8a33d' : '#4caf50'};\">${n.pend} sin revisar</b>\n      ${n.mal ? ` · <b style=\"color:var(--copper);\">⚠️ ${n.mal} no coinciden</b>` : ''} · se guardan ${d.dias_guardadas} días</p>\n    ${n.pend ? `<button class=\"secondary\" style=\"font-size:11px; margin-bottom:8px;\" onclick=\"asis_todasOkFotos(this)\">✔ Marcar todas las sin revisar como correctas</button>` : ''}\n    <div style=\"display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:10px;\">\n",
   "  const d = ASIS_FCH.datos;\n  if (!caja || !d) return;\n  const todas = d.fotos;\n  const sinFoto = (d.sin_foto || []);\n  const f = ASIS_FCH.filtro;\n  const lista = todas.filter(x => f === 'todas' || (f === 'pendientes' && !x.revision) || (f === 'no_coincide' && x.revision === 'no_coincide') || (f === 'sin_ref' && !x.tiene_referencia));\n  const n = { pend: todas.filter(x => !x.revision).length, mal: todas.filter(x => x.revision === 'no_coincide').length };\n  const ultimas = d.ultima_foto_por_checador || {};\n  const avisoFotos = `<div class=\"cv-caja\" style=\"font-size:12px; margin-bottom:10px; border-color:#E6A014;\">\n      ${ASIS_FCH.sn ? (ultimas[ASIS_FCH.sn] ? `Este checador sí manda fotos (la última llegó ${escapeHtml(String(ultimas[ASIS_FCH.sn]).replace('T', ' ').slice(0, 16))}).`\n        : '<b>De este checador nunca ha llegado una foto.</b>') : ''}\n      Las fotos de cada checada se guardan <b>desde que se activó esta función</b>; las de días anteriores no se guardaron.\n      Puedes pedírselas al checador (si todavía las tiene y tu modelo lo acepta llegan en 1–2 min).\n      Si nunca llegan, activa en el checador <b>tomar/guardar foto al verificar</b> (Menú → Sistema o Asistencia → <i>Foto de verificación</i>).\n      ${ASIS_FCH.sn ? `<div style=\"margin-top:6px;\"><button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_pedirFotosDia(this)\">📥 Pedir al checador las fotos de este día</button></div>` : '<div style=\"margin-top:4px; color:var(--muted);\">Elige un checador para pedirle las fotos.</div>'}\n    </div>`;\n  const tarjetasSinFoto = (f === 'todas' ? sinFoto : []).map(x => `<div class=\"cv-caja\" style=\"padding:8px; opacity:.75;\">\n      <div style=\"height:120px; display:flex; align-items:center; justify-content:center; background:#0002; border-radius:8px; font-size:11px; color:var(--muted);\">📷 sin foto de esta checada</div>\n      <div style=\"margin-top:6px; font-size:12px;\"><b>${escapeHtml(x.usuario_nombre || x.nombre_checador || `No. ${x.codigo} (sin ligar)`)}</b>${x.numero_empleado ? ` <span style=\"color:var(--muted);\">No. ${escapeHtml(x.numero_empleado)}</span>` : ''}</div>\n      <div style=\"font-size:11px; color:var(--muted);\">🕘 ${escapeHtml(x.fecha_hora.slice(11, 16))} · ${escapeHtml(x.checador || x.sn)} · No. en checador ${escapeHtml(x.codigo)}</div>\n    </div>`).join('');\n  if (!todas.length) {\n    caja.innerHTML = avisoFotos + `<p style=\"font-size:12px; margin:0 0 8px;\">Sin fotos este día${sinFoto.length ? ` · <b>${sinFoto.length}</b> checada(s) sin foto` : ' y sin checadas'}.</p>\n      ${sinFoto.length ? `<div style=\"display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:10px;\">${tarjetasSinFoto}</div>` : ''}`;\n    return;\n  }\n  const nombre = x => x.usuario_nombre || x.nombre_checador || `No. ${x.codigo} (sin ligar)`;\n  caja.innerHTML = `\n    ${sinFoto.length ? avisoFotos : ''}\n    <p style=\"font-size:12px; margin:0 0 8px;\"><b>${todas.length}</b> checada(s) con foto${sinFoto.length ? ` · ${sinFoto.length} sin foto` : ''} · <b style=\"color:${n.pend ? '#e8a33d' : '#4caf50'};\">${n.pend} sin revisar</b>\n      ${n.mal ? ` · <b style=\"color:var(--copper);\">⚠️ ${n.mal} no coinciden</b>` : ''} · se guardan ${d.dias_guardadas} días</p>\n    ${n.pend ? `<button class=\"secondary\" style=\"font-size:11px; margin-bottom:8px;\" onclick=\"asis_todasOkFotos(this)\">✔ Marcar todas las sin revisar como correctas</button>` : ''}\n    <div style=\"display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:10px;\">\n"
  ],
  [
   "          ${x.revision !== 'no_coincide' ? `<button class=\"secondary\" style=\"font-size:11px; padding:3px 8px;\" onclick=\"asis_revisarFoto(${x.id}, 'no_coincide', this)\">⚠️ No es</button>` : ''}\n          ${x.revision ? `<button class=\"secondary\" style=\"font-size:11px; padding:3px 8px;\" onclick=\"asis_revisarFoto(${x.id}, null, this)\">↺ Quitar revisión</button>` : ''}\n        </div>\n      </div>`).join('') || '<p style=\"font-size:12px; color:var(--muted);\">Nada con ese filtro.</p>'}\n    </div>`;\n  asis_cargarImgsFotosChecadas(lista);\n}\n",
   "          ${x.revision !== 'no_coincide' ? `<button class=\"secondary\" style=\"font-size:11px; padding:3px 8px;\" onclick=\"asis_revisarFoto(${x.id}, 'no_coincide', this)\">⚠️ No es</button>` : ''}\n          ${x.revision ? `<button class=\"secondary\" style=\"font-size:11px; padding:3px 8px;\" onclick=\"asis_revisarFoto(${x.id}, null, this)\">↺ Quitar revisión</button>` : ''}\n        </div>\n      </div>`).join('') || (tarjetasSinFoto ? '' : '<p style=\"font-size:12px; color:var(--muted);\">Nada con ese filtro.</p>')}\n      ${tarjetasSinFoto}\n    </div>`;\n  asis_cargarImgsFotosChecadas(lista);\n}\n"
  ],
  [
   "    </div><div style=\"color:#fff; font-size:14px;\">${escapeHtml(x.usuario_nombre || x.nombre_checador || '')} · ${escapeHtml(x.checador || x.sn || '')}</div>`;\n  v.onclick = () => v.remove();\n  document.body.appendChild(v);\n}\nasync function asis_revisarFoto(id, revision, btn) {\n  let nota = null;\n",
   "    </div><div style=\"color:#fff; font-size:14px;\">${escapeHtml(x.usuario_nombre || x.nombre_checador || '')} · ${escapeHtml(x.checador || x.sn || '')}</div>`;\n  v.onclick = () => v.remove();\n  document.body.appendChild(v);\n}\nasync function asis_pedirFotosDia(btn) {\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      await api(`/api/rh/checadores/${encodeURIComponent(ASIS_FCH.sn)}/pedir-fotos?fecha=${ASIS_FCH.fecha}`, { method: 'POST' });\n      alert('Listo. El checador manda las fotos que todavía tenga de ese día en su siguiente conexión (1–2 min). Luego toca ⟳.\\nSi no llegan, tu modelo no las guarda o no acepta este pedido.');\n    } catch (e) { alert(e.message); }\n  });\n}\nasync function asis_revisarFoto(id, revision, btn) {\n  let nota = null;\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_fotos_checadas_2.py")
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
