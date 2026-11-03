# -*- coding: utf-8 -*-
"""
MICROSIP PRUEBAS: BLOQUEAR A LOS DEMAS PARA QUE NO GUARDEN EN LA BASE REAL
Administrar -> Microsip -> Base de pruebas: junto a cada modulo, nueva casilla
"Bloquear a los demas". Mientras este marcada, nadie (fuera de quien esta en
pruebas en ese modulo) puede GUARDAR en el Microsip real desde ese modulo:
altas de clientes, cotizaciones, facturas, vacaciones, niveles... Si lo
intentan, el sistema les dice "Microsip esta en pruebas... avisa a Sistemas".
Las CONSULTAS siguen funcionando normal. "Todo a la real" quita los bloqueos.
Correr DESPUES de fix_microsip_base_pruebas.py
Toca: backend/db.py, backend/app.py, backend/microsip_escritura.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_microsip_bloquear_real.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    return c\n\n\ndef _aplicar_microsip_pruebas(empresa_id, cfg):\n    ctx = MICROSIP_CTX.get()\n    if not ctx or not cfg:\n        return cfg\n    usuario_id, modulo = ctx\n    if not modulo or modulo not in modulos_pruebas_de_usuario(empresa_id, usuario_id):\n        return cfg\n    return config_microsip_pruebas(empresa_id, cfg) or cfg\n\n\ndef obtener_config_microsip(empresa_id, real=False):\n",
   "    return c\n\n\nTEXTO_MICROSIP_BLOQUEADO = (\"Microsip está en pruebas: por ahora este módulo NO guarda nada en Microsip \"\n                            \"(las consultas sí funcionan). Avisa a Sistemas.\")\n\n\ndef _aplicar_microsip_pruebas(empresa_id, cfg):\n    ctx = MICROSIP_CTX.get()\n    if not ctx or not cfg:\n        return cfg\n    usuario_id, modulo = ctx\n    if not modulo:\n        return cfg\n    if modulo in modulos_pruebas_de_usuario(empresa_id, usuario_id):\n        return config_microsip_pruebas(empresa_id, cfg) or cfg\n    # Quien NO está en pruebas: si ese módulo está bloqueado, puede consultar la real pero no guardar en ella.\n    if modulo in (obtener_microsip_pruebas(empresa_id).get(\"bloquear\") or []):\n        cfg = dict(cfg)\n        cfg[\"_escritura_bloqueada\"] = TEXTO_MICROSIP_BLOQUEADO\n    return cfg\n\n\ndef obtener_config_microsip(empresa_id, real=False):\n"
  ]
 ],
 "backend/app.py": [
  [
   "    usuario: Optional[str] = Field(default=None, max_length=100)\n    password: Optional[str] = None  # None = no cambiarla; \"\" = borrarla\n    mis_modulos: List[str] = []      # módulos donde YO uso la base de pruebas\n\n\n@app.get(\"/api/microsip/pruebas\")\n",
   "    usuario: Optional[str] = Field(default=None, max_length=100)\n    password: Optional[str] = None  # None = no cambiarla; \"\" = borrarla\n    mis_modulos: List[str] = []      # módulos donde YO uso la base de pruebas\n    bloquear: Optional[List[str]] = None  # módulos donde los demás NO pueden guardar en la real\n\n\n@app.get(\"/api/microsip/pruebas\")\n"
  ],
  [
   "        \"usuario\": d.get(\"usuario\") or \"\", \"tiene_password\": bool(d.get(\"password\")),\n        \"modulos\": [{\"clave\": m, \"nombre\": n,\n                     \"yo\": int(usuario[\"id\"]) in [int(x) for x in (d[\"modulos\"].get(m) or [])],\n                     \"otros\": [nombres.get(int(x), f\"#{x}\") for x in (d[\"modulos\"].get(m) or []) if int(x) != int(usuario[\"id\"])]}\n                    for m, n in db.MODULOS_MICROSIP_PRUEBAS.items()],\n    }\n\n",
   "        \"usuario\": d.get(\"usuario\") or \"\", \"tiene_password\": bool(d.get(\"password\")),\n        \"modulos\": [{\"clave\": m, \"nombre\": n,\n                     \"yo\": int(usuario[\"id\"]) in [int(x) for x in (d[\"modulos\"].get(m) or [])],\n                     \"otros\": [nombres.get(int(x), f\"#{x}\") for x in (d[\"modulos\"].get(m) or []) if int(x) != int(usuario[\"id\"])],\n                     \"bloqueado\": m in (d.get(\"bloquear\") or [])}\n                    for m, n in db.MODULOS_MICROSIP_PRUEBAS.items()],\n    }\n\n"
  ],
  [
   "        if m in payload.mis_modulos:\n            ids.append(yo)\n        d[\"modulos\"][m] = ids\n    if payload.mis_modulos and not d[\"ruta_db\"]:\n        raise HTTPException(status_code=400, detail=\"Primero escribe la ruta de la base de PRUEBAS\")\n    db.guardar_microsip_pruebas(usuario[\"empresa_id\"], d)\n",
   "        if m in payload.mis_modulos:\n            ids.append(yo)\n        d[\"modulos\"][m] = ids\n    if payload.bloquear is not None:\n        d[\"bloquear\"] = [m for m in payload.bloquear if m in db.MODULOS_MICROSIP_PRUEBAS]\n    if payload.mis_modulos and not d[\"ruta_db\"]:\n        raise HTTPException(status_code=400, detail=\"Primero escribe la ruta de la base de PRUEBAS\")\n    db.guardar_microsip_pruebas(usuario[\"empresa_id\"], d)\n"
  ]
 ],
 "backend/microsip_escritura.py": [
  [
   "# ---------------------------------------------------------------- conexión\n\ndef _conectar(config):\n    microsip._asegurar_cargado()\n    usuario = config.get(\"microsip_escritura_usuario\") or config[\"microsip_usuario\"]\n    password = config.get(\"microsip_escritura_password\") if config.get(\"microsip_escritura_usuario\") else config[\"microsip_password\"]\n",
   "# ---------------------------------------------------------------- conexión\n\ndef _conectar(config):\n    if config.get(\"_escritura_bloqueada\"):\n        # El módulo está en pruebas y bloqueado: nadie (fuera de quien prueba) guarda en la base real.\n        raise ErrorMicrosip(\"Bloqueado\", config[\"_escritura_bloqueada\"])\n    microsip._asegurar_cargado()\n    usuario = config.get(\"microsip_escritura_usuario\") or config[\"microsip_usuario\"]\n    password = config.get(\"microsip_escritura_password\") if config.get(\"microsip_escritura_usuario\") else config[\"microsip_password\"]\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    </details>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase;\">¿En qué módulos uso YO la base de pruebas?</label>\n    <div style=\"margin:6px 0 12px;\">\n      ${d.modulos.map(m => `\n        <label style=\"display:flex; gap:8px; align-items:flex-start; padding:7px 4px; border-bottom:1px solid var(--line); cursor:pointer;\">\n          <input type=\"checkbox\" class=\"msp_mod\" value=\"${m.clave}\" ${m.yo ? 'checked' : ''} style=\"width:auto; margin-top:3px;\" />\n          <span>${escapeHtml(m.nombre)}${m.otros.length ? `<br><span style=\"font-size:11px; color:var(--muted);\">También en pruebas: ${m.otros.map(escapeHtml).join(', ')}</span>` : ''}</span>\n        </label>`).join('')}\n    </div>\n    <div style=\"display:flex; gap:8px;\">\n      <button class=\"primary\" style=\"flex:1;\" onclick=\"ms_guardarPruebas(this)\">Guardar</button>\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"ms_probarPruebas(this)\">Probar conexión a pruebas</button>\n      <button class=\"secondary\" onclick=\"document.querySelectorAll('.msp_mod').forEach(c => c.checked = false); ms_guardarPruebas(this)\" title=\"Desmarca todos tus módulos: vuelves a la base real en todo\">↩️ Todo a la real</button>\n    </div>\n    <div id=\"msp_error\" class=\"error-msg\"></div><div id=\"msp_ok\"></div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:12px;\">⚠️ Lo que hagas en pruebas puede guardar en el sistema folios o IDs de la copia (ej. el cliente de Microsip de un estudiante o el folio de una cotización). Usa estudiantes, clientes y trabajos <b>de prueba</b>.</p>`;\n",
   "    </details>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase;\">¿En qué módulos uso YO la base de pruebas?</label>\n    <div style=\"margin:6px 0 12px;\">\n      <div style=\"display:flex; gap:8px; font-size:11px; color:var(--muted); padding:0 4px 4px; text-transform:uppercase;\">\n        <span style=\"width:62px;\">Yo en pruebas</span><span style=\"width:70px;\">🔒 Bloquear a los demás</span><span>Módulo</span></div>\n      ${d.modulos.map(m => `\n        <div style=\"display:flex; gap:8px; align-items:flex-start; padding:7px 4px; border-bottom:1px solid var(--line);\">\n          <span style=\"width:62px; text-align:center;\"><input type=\"checkbox\" class=\"msp_mod\" value=\"${m.clave}\" ${m.yo ? 'checked' : ''} style=\"width:auto;\" title=\"Yo uso la base de pruebas en este módulo\" /></span>\n          <span style=\"width:70px; text-align:center;\"><input type=\"checkbox\" class=\"msp_blq\" value=\"${m.clave}\" ${m.bloqueado ? 'checked' : ''} style=\"width:auto;\" title=\"Los demás pueden consultar Microsip real, pero NO guardar nada (altas de clientes, cotizaciones, facturas, vacaciones…)\" /></span>\n          <span>${escapeHtml(m.nombre)}${m.otros.length ? `<br><span style=\"font-size:11px; color:var(--muted);\">También en pruebas: ${m.otros.map(escapeHtml).join(', ')}</span>` : ''}${m.bloqueado ? '<br><span style=\"font-size:11px; color:var(--copper);\">🔒 Los demás no pueden guardar en Microsip desde aquí</span>' : ''}</span>\n        </div>`).join('')}\n      <p style=\"font-size:11px; color:var(--muted); margin:6px 4px 0;\">🔒 <b>Bloquear a los demás</b>: mientras pruebas, nadie más puede guardar en el Microsip REAL desde ese módulo (dar de alta clientes, cotizaciones, facturas, vacaciones, niveles…). Sí pueden seguir consultando. Si lo intentan, el sistema les dice que Microsip está en pruebas. Lo que no se mandó (ej. la cotización de un trabajo de laboratorio) se puede mandar después con \"Mandar a Microsip\".</p>\n    </div>\n    <div style=\"display:flex; gap:8px;\">\n      <button class=\"primary\" style=\"flex:1;\" onclick=\"ms_guardarPruebas(this)\">Guardar</button>\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"ms_probarPruebas(this)\">Probar conexión a pruebas</button>\n      <button class=\"secondary\" onclick=\"document.querySelectorAll('.msp_mod, .msp_blq').forEach(c => c.checked = false); ms_guardarPruebas(this)\" title=\"Desmarca todo: tú vuelves a la base real y se quitan los bloqueos\">↩️ Todo a la real</button>\n    </div>\n    <div id=\"msp_error\" class=\"error-msg\"></div><div id=\"msp_ok\"></div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:12px;\">⚠️ Lo que hagas en pruebas puede guardar en el sistema folios o IDs de la copia (ej. el cliente de Microsip de un estudiante o el folio de una cotización). Usa estudiantes, clientes y trabajos <b>de prueba</b>.</p>`;\n"
  ],
  [
   "    usuario: document.getElementById('msp_usuario').value.trim(),\n    password: pw ? pw : null,\n    mis_modulos: [...document.querySelectorAll('.msp_mod:checked')].map(c => c.value),\n  };\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n",
   "    usuario: document.getElementById('msp_usuario').value.trim(),\n    password: pw ? pw : null,\n    mis_modulos: [...document.querySelectorAll('.msp_mod:checked')].map(c => c.value),\n    bloquear: [...document.querySelectorAll('.msp_blq:checked')].map(c => c.value),\n  };\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_microsip_bloquear_real.py")
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
