# -*- coding: utf-8 -*-
"""Checador de precio: almacenes "reservados" (ej. Almacen General / CEDIS) que NO muestran
la cantidad, solo "Hay disponible, consulta con CEDIS" (o "Sin disponible por ahora").
La cantidad solo la ven el administrador y los departamentos marcados (ej. Abastecimiento).
Se configura en la web: Administrar -> Microsip -> Checador de precio. Aplica en web y app
(el servidor ya no manda la cantidad, aunque la app sea vieja).
Correr en la carpeta tickets-ti:  py -3 fix_checador_cedis.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return config\n\n\ndef _filtrar_almacenes_checador(usuario, resultado):\n    \"\"\"Solo los almacenes que el administrador marcó como visibles (el admin ve todos).\"\"\"\n    if not resultado or usuario.get(\"rol\") == \"admin\":\n        return resultado\n    visibles = db.almacenes_visibles_checador(usuario[\"empresa_id\"])\n    if visibles is None:\n        return resultado\n    vis = set(visibles)\n    almacenes = [a for a in (resultado.get(\"almacenes\") or []) if a.get(\"almacen_id\") in vis]\n    resultado[\"almacenes\"] = almacenes\n    if \"existencia_total\" in resultado:\n        resultado[\"existencia_total\"] = sum(float(a.get(\"existencia\") or 0) for a in almacenes)\n    if \"comprometido_total\" in resultado:\n        resultado[\"comprometido_total\"] = sum(float(a.get(\"comprometido\") or 0) for a in almacenes)\n    if \"disponible_total\" in resultado:\n        resultado[\"disponible_total\"] = sum(float(a.get(\"disponible\") or 0) for a in almacenes)\n    if resultado.get(\"capas_detalle\"):\n        resultado[\"capas_detalle\"] = [c for c in resultado[\"capas_detalle\"] if c.get(\"almacen_id\") in vis]\n    return resultado\n\n\nclass AlmacenesChecadorIn(BaseModel):\n    todos: bool = True\n    almacen_ids: List[int] = []\n\n\n@app.get(\"/api/checador-precio/almacenes-config\")\n",
   "    return config\n\n\ndef _sin_acentos(texto):\n    return unicodedata.normalize(\"NFKD\", str(texto or \"\")).encode(\"ascii\", \"ignore\").decode().strip().lower()\n\n\ndef _ve_cantidad_reservados(usuario, reservados):\n    \"\"\"El administrador y los departamentos marcados (ej. Abastecimiento / CEDIS) sí ven la cantidad.\"\"\"\n    if usuario.get(\"rol\") == \"admin\":\n        return True\n    deptos = {_sin_acentos(d) for d in reservados.get(\"departamentos\") or []}\n    if not deptos:\n        return False\n    mio = usuario.get(\"departamento\") or db.obtener_departamento_usuario(usuario[\"id\"])\n    return _sin_acentos(mio) in deptos\n\n\ndef _filtrar_almacenes_checador(usuario, resultado):\n    \"\"\"Solo los almacenes que el administrador marcó como visibles (el admin ve todos), y en los\n    almacenes \"reservados\" (ej. Almacén General / CEDIS) solo se dice si hay disponible, sin la\n    cantidad, salvo al administrador y a los departamentos que la pueden ver.\"\"\"\n    if not resultado:\n        return resultado\n    almacenes = list(resultado.get(\"almacenes\") or [])\n    vis = None\n    if usuario.get(\"rol\") != \"admin\":\n        visibles = db.almacenes_visibles_checador(usuario[\"empresa_id\"])\n        if visibles is not None:\n            vis = set(visibles)\n            almacenes = [a for a in almacenes if a.get(\"almacen_id\") in vis]\n    reservados = db.almacenes_reservados_checador(usuario[\"empresa_id\"])\n    ocultar = set(reservados[\"almacenes\"]) if reservados[\"almacenes\"] and not _ve_cantidad_reservados(usuario, reservados) else set()\n    if vis is None and not ocultar:\n        return resultado\n    con_cantidad = [a for a in almacenes if a.get(\"almacen_id\") not in ocultar]\n    final = []\n    for a in almacenes:\n        if a.get(\"almacen_id\") in ocultar:\n            hay = float(a.get(\"disponible\") or 0) > 0\n            final.append({\"almacen_id\": a.get(\"almacen_id\"), \"almacen_nombre\": a.get(\"almacen_nombre\"),\n                          \"existencia\": None, \"comprometido\": None, \"disponible\": None, \"ultimo_movimiento\": None,\n                          \"solo_disponibilidad\": True, \"hay_disponible\": hay,\n                          \"mensaje\": reservados[\"mensaje\"] if hay else \"Sin disponible por ahora\"})\n        else:\n            final.append(a)\n    resultado[\"almacenes\"] = final\n    if \"existencia_total\" in resultado:\n        resultado[\"existencia_total\"] = sum(float(a.get(\"existencia\") or 0) for a in con_cantidad)\n    if \"comprometido_total\" in resultado:\n        resultado[\"comprometido_total\"] = sum(float(a.get(\"comprometido\") or 0) for a in con_cantidad)\n    if \"disponible_total\" in resultado:\n        resultado[\"disponible_total\"] = sum(float(a.get(\"disponible\") or 0) for a in con_cantidad)\n    if ocultar:\n        resultado[\"totales_sin_reservados\"] = True\n    if resultado.get(\"capas_detalle\"):\n        resultado[\"capas_detalle\"] = [c for c in resultado[\"capas_detalle\"]\n                                      if (vis is None or c.get(\"almacen_id\") in vis) and c.get(\"almacen_id\") not in ocultar]\n    return resultado\n\n\nclass AlmacenesChecadorIn(BaseModel):\n    todos: bool = True\n    almacen_ids: List[int] = []\n    # Almacenes que solo dicen \"hay disponible, consulta con CEDIS\" (sin cantidad)\n    # y los departamentos que sí ven la cantidad. None = no cambiar.\n    reservados: Optional[List[int]] = None\n    departamentos_ven_cantidad: Optional[List[str]] = None\n    mensaje_reservados: Optional[str] = Field(default=None, max_length=120)\n\n\n@app.get(\"/api/checador-precio/almacenes-config\")\n"
  ],
  [
   "        todos = microsip.listar_almacenes(config)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (almacenes): {e}\")\n    return {\"almacenes\": todos, \"visibles\": db.almacenes_visibles_checador(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/checador-precio/almacenes-config\")\n",
   "        todos = microsip.listar_almacenes(config)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (almacenes): {e}\")\n    return {\"almacenes\": todos, \"visibles\": db.almacenes_visibles_checador(usuario[\"empresa_id\"]),\n            \"reservados\": db.almacenes_reservados_checador(usuario[\"empresa_id\"]),\n            \"departamentos\": [d[\"nombre\"] for d in db.listar_departamentos(usuario[\"empresa_id\"])]}\n\n\n@app.post(\"/api/checador-precio/almacenes-config\")\n"
  ],
  [
   "    if not payload.todos and not payload.almacen_ids:\n        raise HTTPException(status_code=400, detail=\"Marca al menos un almacén (o deja 'Todos')\")\n    db.guardar_almacenes_visibles_checador(usuario[\"empresa_id\"], None if payload.todos else payload.almacen_ids)\n    return {\"ok\": True}\n\n\n",
   "    if not payload.todos and not payload.almacen_ids:\n        raise HTTPException(status_code=400, detail=\"Marca al menos un almacén (o deja 'Todos')\")\n    db.guardar_almacenes_visibles_checador(usuario[\"empresa_id\"], None if payload.todos else payload.almacen_ids)\n    if payload.reservados is not None:\n        actual = db.almacenes_reservados_checador(usuario[\"empresa_id\"])\n        db.guardar_almacenes_reservados_checador(\n            usuario[\"empresa_id\"], payload.reservados,\n            actual[\"departamentos\"] if payload.departamentos_ven_cantidad is None else payload.departamentos_ven_cantidad,\n            actual[\"mensaje\"] if payload.mensaje_reservados is None else payload.mensaje_reservados)\n    return {\"ok\": True}\n\n\n"
  ]
 ],
 "backend/db.py": [
  [
   "        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS checador_almacenes_json TEXT;\n    \"\"\")\n",
   "        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS checador_almacenes_json TEXT;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS checador_reservados_json TEXT;\n    \"\"\")\n"
  ],
  [
   "def guardar_almacenes_visibles_checador(empresa_id, ids):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET checador_almacenes_json = %s WHERE id = %s\",\n                (None if ids is None else json.dumps([int(x) for x in ids]), empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef obtener_microsip_pruebas(empresa_id):\n",
   "def guardar_almacenes_visibles_checador(empresa_id, ids):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET checador_almacenes_json = %s WHERE id = %s\",\n                (None if ids is None else json.dumps([int(x) for x in ids]), empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\nRESERVADOS_CHECADOR_VACIO = {\"almacenes\": [], \"departamentos\": [], \"mensaje\": \"Hay disponible, consulta con CEDIS\"}\n\n\ndef almacenes_reservados_checador(empresa_id):\n    \"\"\"Almacenes del checador de precio que NO muestran cantidad (ej. Almacén General / CEDIS):\n    solo dicen si hay disponible. `departamentos` = los que sí ven la cantidad (ej. Abastecimiento).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT checador_reservados_json FROM empresas WHERE id = %s\", (empresa_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    try:\n        v = json.loads((row or {}).get(\"checador_reservados_json\") or \"null\")\n    except (TypeError, ValueError):\n        v = None\n    r = dict(RESERVADOS_CHECADOR_VACIO)\n    if isinstance(v, dict):\n        r[\"almacenes\"] = [int(x) for x in (v.get(\"almacenes\") or [])]\n        r[\"departamentos\"] = [str(x) for x in (v.get(\"departamentos\") or []) if str(x).strip()]\n        r[\"mensaje\"] = (v.get(\"mensaje\") or \"\").strip() or r[\"mensaje\"]\n    return r\n\n\ndef guardar_almacenes_reservados_checador(empresa_id, almacenes, departamentos, mensaje):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET checador_reservados_json = %s WHERE id = %s\",\n                (json.dumps({\"almacenes\": [int(x) for x in almacenes], \"departamentos\": [str(x).strip() for x in departamentos if str(x).strip()],\n                             \"mensaje\": (mensaje or \"\").strip()}, ensure_ascii=False), empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef obtener_microsip_pruebas(empresa_id):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style=\"color:var(--trace);\">${fmt(datos.disponible_total)} disponibles</b>\n",
   "        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style=\"color:var(--trace);\">${fmt(datos.disponible_total)} disponibles</b>${datos.totales_sin_reservados ? ' <span style=\"font-size:11px;\">(sin contar CEDIS)</span>' : ''}\n"
  ],
  [
   "          ${datos.almacenes.map(a => `\n",
   "          ${datos.almacenes.map(a => a.solo_disponibilidad ? `\n            <tr>\n              <td>${escapeHtml(a.almacen_nombre)}</td>\n              <td colspan=\"4\"><b style=\"color:${a.hay_disponible ? 'var(--trace)' : 'var(--copper)'};\">${a.hay_disponible ? '✅' : '—'} ${escapeHtml(a.mensaje || '')}</b></td>\n            </tr>\n          ` : `\n"
  ],
  [
   "      `<tr><td>${escapeHtml(a.almacen_nombre)}</td><td style=\"text-align:right;\">${a.disponible}</td></tr>`\n",
   "      `<tr><td>${escapeHtml(a.almacen_nombre)}</td><td style=\"text-align:right;\">${a.solo_disponibilidad ? escapeHtml(a.mensaje || '') : a.disponible}</td></tr>`\n"
  ],
  [
   "        <input type=\"checkbox\" class=\"msc_alm\" value=\"${a.almacen_id}\" ${todos || vis.has(a.almacen_id) ? 'checked' : ''} ${todos ? 'disabled' : ''} style=\"width:auto;\" /> ${escapeHtml(a.nombre)}</label>`).join('') || '<p class=\"empty-col\">— sin almacenes —</p>'}\n    </div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"ms_guardarChecador(this)\">Guardar</button>\n    <div id=\"msc_error\" class=\"error-msg\"></div>\n",
   "        <input type=\"checkbox\" class=\"msc_alm\" value=\"${a.almacen_id}\" ${todos || vis.has(a.almacen_id) ? 'checked' : ''} ${todos ? 'disabled' : ''} style=\"width:auto;\" /> ${escapeHtml(a.nombre)}</label>`).join('') || '<p class=\"empty-col\">— sin almacenes —</p>'}\n    </div>\n    <h4 style=\"margin:14px 0 6px;\">🔒 Almacenes que solo dicen si hay (sin cantidad)</h4>\n    <p style=\"font-size:12px; color:var(--muted); margin-bottom:8px;\">Ej. <b>Almacén General / CEDIS</b>: en vez de la cantidad aparece el mensaje de abajo (o \"Sin disponible por ahora\"). La cantidad solo la ven el <b>administrador</b> y los departamentos que marques.</p>\n    <div style=\"columns:2; column-gap:18px; margin-bottom:10px;\">\n      ${(d.almacenes || []).map(a => `<label style=\"display:flex; gap:8px; align-items:center; padding:4px 0; break-inside:avoid;\">\n        <input type=\"checkbox\" class=\"msc_res\" value=\"${a.almacen_id}\" ${(d.reservados?.almacenes || []).includes(a.almacen_id) ? 'checked' : ''} style=\"width:auto;\" /> ${escapeHtml(a.nombre)}</label>`).join('')}\n    </div>\n    <div class=\"field\"><label>Mensaje cuando sí hay</label>\n      <input id=\"msc_mensaje\" maxlength=\"120\" value=\"${escapeHtml(d.reservados?.mensaje || 'Hay disponible, consulta con CEDIS')}\" /></div>\n    <div style=\"font-size:12px; font-weight:700; margin:6px 0;\">Departamentos que SÍ ven la cantidad</div>\n    <div style=\"columns:2; column-gap:18px; margin-bottom:12px;\">\n      ${(d.departamentos || []).map(n => `<label style=\"display:flex; gap:8px; align-items:center; padding:4px 0; break-inside:avoid;\">\n        <input type=\"checkbox\" class=\"msc_dep\" value=\"${escapeHtml(n)}\" ${(d.reservados?.departamentos || []).includes(n) ? 'checked' : ''} style=\"width:auto;\" /> ${escapeHtml(n)}</label>`).join('') || '<p class=\"empty-col\">— no hay departamentos dados de alta (Administrar → Organización → Departamentos) —</p>'}\n    </div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"ms_guardarChecador(this)\">Guardar</button>\n    <div id=\"msc_error\" class=\"error-msg\"></div>\n"
  ],
  [
   "    try { await api('/api/checador-precio/almacenes-config', { method: 'POST', body: JSON.stringify({ todos, almacen_ids: ids }) });\n          mostrarExito(todos ? 'Se muestran todos los almacenes' : `Se muestran ${ids.length} almacén(es) en el checador`); }\n",
   "    const reservados = [...document.querySelectorAll('.msc_res:checked')].map(c => Number(c.value));\n    const departamentos_ven_cantidad = [...document.querySelectorAll('.msc_dep:checked')].map(c => c.value);\n    const mensaje_reservados = document.getElementById('msc_mensaje').value.trim();\n    try { await api('/api/checador-precio/almacenes-config', { method: 'POST', body: JSON.stringify({ todos, almacen_ids: ids, reservados, departamentos_ven_cantidad, mensaje_reservados }) });\n          mostrarExito((todos ? 'Se muestran todos los almacenes' : `Se muestran ${ids.length} almacén(es) en el checador`) + (reservados.length ? ` · ${reservados.length} sin cantidad` : '')); }\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_cedis.py")
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
