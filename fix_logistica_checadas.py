# -*- coding: utf-8 -*-
"""
LOGISTICA: CHECADAS DE CHOFERES (CHECADOR APP)
- Quien es de Logistica (acceso "Logistica Rep." o su sucursal con departamento
  Logistica) ve y revisa las checadas del Checador app (selfie, mapa, "Es la
  persona" / "No coincide"): boton "Checadas de choferes" en el menu y pestana
  "Checadas" en Entregas.
- Registrar la foto de la cara sigue siendo solo de RH. RH queda igual.
REQUIERE haber corrido antes fix_rh_importar_personal.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_logistica_checadas.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    es_encargada_rh = usuario.get(\"acceso_datos_empleado_rh\", False)\n    if not (es_admin_con_rh or es_encargada_rh):\n        raise HTTPException(status_code=403, detail=\"No tienes acceso a administrar Recursos Humanos\")\n    return usuario\n\n\n",
   "    es_encargada_rh = usuario.get(\"acceso_datos_empleado_rh\", False)\n    if not (es_admin_con_rh or es_encargada_rh):\n        raise HTTPException(status_code=403, detail=\"No tienes acceso a administrar Recursos Humanos\")\n    return usuario\n\n\ndef requiere_rh_o_logistica(usuario: dict = Depends(requiere_empresa)) -> dict:\n    \"\"\"Ver y revisar las checadas del Checador app (selfie + ubicación): RH como\n    siempre, y también Logística, que revisa si checaron los choferes (David, 21 oct 2026).\n    Registrar la foto de la cara sigue siendo solo de RH.\"\"\"\n    usuario = _con_permisos(usuario)\n    es_rh = (usuario[\"rol\"] == \"admin\" and usuario.get(\"acceso_rh\", True)) or usuario.get(\"acceso_datos_empleado_rh\", False)\n    if not (es_rh or (usuario[\"rol\"] != \"master\" and _es_departamento_logistica(usuario[\"id\"]))):\n        raise HTTPException(status_code=403, detail=\"No tienes acceso a las checadas del Checador app\")\n    return usuario\n\n\n"
  ],
  [
   "\n@app.get(\"/api/rh/checador\")\ndef api_rh_checadas_app(desde: Optional[str] = None, hasta: Optional[str] = None, usuario_id: Optional[int] = None,\n                        usuario: dict = Depends(requiere_admin_rh)):\n    try:\n        d = date.fromisoformat(desde) if desde else db.ahora().date()\n        h = date.fromisoformat(hasta) if hasta else d\n",
   "\n@app.get(\"/api/rh/checador\")\ndef api_rh_checadas_app(desde: Optional[str] = None, hasta: Optional[str] = None, usuario_id: Optional[int] = None,\n                        usuario: dict = Depends(requiere_rh_o_logistica)):\n    try:\n        d = date.fromisoformat(desde) if desde else db.ahora().date()\n        h = date.fromisoformat(hasta) if hasta else d\n"
  ],
  [
   "\n\n@app.get(\"/api/rh/checador/{checada_id}\")\ndef api_rh_detalle_checada(checada_id: int, usuario: dict = Depends(requiere_admin_rh)):\n    c = db.obtener_checada_app(usuario[\"empresa_id\"], checada_id)\n    if not c:\n        raise HTTPException(status_code=404, detail=\"Checada no encontrada\")\n",
   "\n\n@app.get(\"/api/rh/checador/{checada_id}\")\ndef api_rh_detalle_checada(checada_id: int, usuario: dict = Depends(requiere_rh_o_logistica)):\n    c = db.obtener_checada_app(usuario[\"empresa_id\"], checada_id)\n    if not c:\n        raise HTTPException(status_code=404, detail=\"Checada no encontrada\")\n"
  ],
  [
   "\n\n@app.patch(\"/api/rh/checador/{checada_id}/revision\")\ndef api_rh_revisar_checada(checada_id: int, payload: RevisionChecadaIn, usuario: dict = Depends(requiere_admin_rh)):\n    if not db.obtener_checada_app(usuario[\"empresa_id\"], checada_id):\n        raise HTTPException(status_code=404, detail=\"Checada no encontrada\")\n    db.revisar_checada_app(usuario[\"empresa_id\"], checada_id, payload.revision, (payload.nota or \"\").strip() or None, usuario[\"id\"])\n",
   "\n\n@app.patch(\"/api/rh/checador/{checada_id}/revision\")\ndef api_rh_revisar_checada(checada_id: int, payload: RevisionChecadaIn, usuario: dict = Depends(requiere_rh_o_logistica)):\n    if not db.obtener_checada_app(usuario[\"empresa_id\"], checada_id):\n        raise HTTPException(status_code=404, detail=\"Checada no encontrada\")\n    db.revisar_checada_app(usuario[\"empresa_id\"], checada_id, payload.revision, (payload.nota or \"\").strip() or None, usuario[\"id\"])\n"
  ]
 ],
 "frontend/index.html": [
  [
   "          <button class=\"menu-boton\" id=\"btnReparaciones\" onclick=\"abrirReparaciones()\" style=\"display:none;\"><span class=\"menu-icono\">🔧</span>Reparaciones</button>\n          <button class=\"menu-boton\" id=\"btnEquipos\" onclick=\"abrirEquipos()\" style=\"display:none;\"><span class=\"menu-icono\">💻</span>Equipos</button>\n          <button class=\"menu-boton\" id=\"btnEntregas\" onclick=\"abrirEntregas()\" style=\"display:none;\"><span class=\"menu-icono\">🚚</span>Entregas</button>\n          <button class=\"menu-boton\" id=\"btnLaboratorio\" onclick=\"abrirLaboratorio()\" style=\"display:none;\"><span class=\"menu-icono\">🦷</span>Laboratorio</button>\n          <button class=\"menu-boton\" id=\"btnSoporte\" onclick=\"abrirSoporte()\" style=\"display:none;\"><span class=\"menu-icono\">🛠️</span>Soporte técnico</button>\n        </div>\n",
   "          <button class=\"menu-boton\" id=\"btnReparaciones\" onclick=\"abrirReparaciones()\" style=\"display:none;\"><span class=\"menu-icono\">🔧</span>Reparaciones</button>\n          <button class=\"menu-boton\" id=\"btnEquipos\" onclick=\"abrirEquipos()\" style=\"display:none;\"><span class=\"menu-icono\">💻</span>Equipos</button>\n          <button class=\"menu-boton\" id=\"btnEntregas\" onclick=\"abrirEntregas()\" style=\"display:none;\"><span class=\"menu-icono\">🚚</span>Entregas</button>\n          <button class=\"menu-boton\" id=\"btnChecadasLogistica\" onclick=\"abrirChecadasLogistica()\" style=\"display:none;\"><span class=\"menu-icono\">📱</span>Checadas de choferes</button>\n          <button class=\"menu-boton\" id=\"btnLaboratorio\" onclick=\"abrirLaboratorio()\" style=\"display:none;\"><span class=\"menu-icono\">🦷</span>Laboratorio</button>\n          <button class=\"menu-boton\" id=\"btnSoporte\" onclick=\"abrirSoporte()\" style=\"display:none;\"><span class=\"menu-icono\">🛠️</span>Soporte técnico</button>\n        </div>\n"
  ],
  [
   "      <button class=\"admin-tab\" id=\"tabEntregasAgenda\" onclick=\"cambiarEntregasTab('agenda')\">📅 Agenda</button>\n      <button class=\"admin-tab\" id=\"tabEntregasVehiculos\" onclick=\"cambiarEntregasTab('vehiculos')\" style=\"display:none;\">🚚 Vehículos</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecklist\" onclick=\"cambiarEntregasTab('checklist')\" style=\"display:none;\">☑️ Checklist</button>\n    </div>\n    <div id=\"entregasContenido\" style=\"max-width:1200px; margin:0 auto;\"></div>\n  </main>\n",
   "      <button class=\"admin-tab\" id=\"tabEntregasAgenda\" onclick=\"cambiarEntregasTab('agenda')\">📅 Agenda</button>\n      <button class=\"admin-tab\" id=\"tabEntregasVehiculos\" onclick=\"cambiarEntregasTab('vehiculos')\" style=\"display:none;\">🚚 Vehículos</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecklist\" onclick=\"cambiarEntregasTab('checklist')\" style=\"display:none;\">☑️ Checklist</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecadas\" onclick=\"cambiarEntregasTab('checadas')\" style=\"display:none;\">📱 Checadas</button>\n    </div>\n    <div id=\"entregasContenido\" style=\"max-width:1200px; margin:0 auto;\"></div>\n  </main>\n"
  ],
  [
   "  if (document.getElementById('btnProyectos')) document.getElementById('btnProyectos').style.display = META.mis_permisos.acceso_proyectos === false ? 'none' : 'flex';\n  document.getElementById('btnLaboratorio').style.display = META.mis_permisos.acceso_laboratorio ? 'flex' : 'none';\n  document.getElementById('btnEntregas').style.display = META.mis_permisos.acceso_entregas ? 'flex' : 'none';\n  document.getElementById('btnChecadorPrecio').style.display = META.mis_permisos.acceso_checador_precio ? 'flex' : 'none';\n  document.getElementById('btnRH').style.display = META.mis_permisos.acceso_rh ? 'flex' : 'none';\n  document.getElementById('btnCompras').style.display = META.mis_permisos.acceso_compras ? 'flex' : 'none';\n",
   "  if (document.getElementById('btnProyectos')) document.getElementById('btnProyectos').style.display = META.mis_permisos.acceso_proyectos === false ? 'none' : 'flex';\n  document.getElementById('btnLaboratorio').style.display = META.mis_permisos.acceso_laboratorio ? 'flex' : 'none';\n  document.getElementById('btnEntregas').style.display = META.mis_permisos.acceso_entregas ? 'flex' : 'none';\n  // Logística revisa si checaron los choferes (Checador app). RH lo sigue viendo en su módulo.\n  document.getElementById('btnChecadasLogistica').style.display = META.es_logistica ? 'flex' : 'none';\n  document.getElementById('btnChecadorPrecio').style.display = META.mis_permisos.acceso_checador_precio ? 'flex' : 'none';\n  document.getElementById('btnRH').style.display = META.mis_permisos.acceso_rh ? 'flex' : 'none';\n  document.getElementById('btnCompras').style.display = META.mis_permisos.acceso_compras ? 'flex' : 'none';\n"
  ],
  [
   "// cada checada (foto del momento junto a la registrada, y el mapa).\n\nasync function renderChecadorAppRH() {\n  const cont = document.getElementById('rhContenido');\n  const hoy = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);\n  const desde = (window.CHK_APP_DESDE || hoy), hasta = (window.CHK_APP_HASTA || hoy);\n",
   "// cada checada (foto del momento junto a la registrada, y el mapa).\n\nasync function renderChecadorAppRH() {\n  window.CHK_APP_RECARGAR = null;\n  const cont = document.getElementById('rhContenido');\n  const hoy = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);\n  const desde = (window.CHK_APP_DESDE || hoy), hasta = (window.CHK_APP_HASTA || hoy);\n"
  ],
  [
   "    try {\n      await api(`/api/rh/checador/${id}/revision`, { method: 'PATCH', body: JSON.stringify({ revision, nota: document.getElementById('chkNota').value }) });\n      cerrarModal();\n      await renderChecadorAppRH();\n    } catch (e) { alert(e.message); }\n  });\n}\n",
   "    try {\n      await api(`/api/rh/checador/${id}/revision`, { method: 'PATCH', body: JSON.stringify({ revision, nota: document.getElementById('chkNota').value }) });\n      cerrarModal();\n      await (window.CHK_APP_RECARGAR || renderChecadorAppRH)();\n    } catch (e) { alert(e.message); }\n  });\n}\n"
  ],
  [
   "  }\n  document.getElementById('tabEntregasChecklist').style.display = SESION.usuario.rol === 'admin' ? 'inline-block' : 'none';\n  document.getElementById('tabEntregasVehiculos').style.display = esInstalador ? 'none' : 'inline-block';\n  await cambiarEntregasTab(ENTREGAS_TAB);\n}\n\nlet ENTREGAS_TAB = 'lista';\n",
   "  }\n  document.getElementById('tabEntregasChecklist').style.display = SESION.usuario.rol === 'admin' ? 'inline-block' : 'none';\n  document.getElementById('tabEntregasVehiculos').style.display = esInstalador ? 'none' : 'inline-block';\n  // Checadas del Checador app: Logística (y quien no tenga Entregas solo ve esa pestaña).\n  const conEntregas = !!(META.mis_permisos && META.mis_permisos.acceso_entregas) || SESION.usuario.rol === 'admin';\n  document.getElementById('tabEntregasChecadas').style.display = META.es_logistica ? 'inline-block' : 'none';\n  if (!conEntregas) {\n    ['tabEntregasLista', 'tabEntregasAgenda', 'tabEntregasVehiculos', 'tabEntregasChecklist'].forEach(i => document.getElementById(i).style.display = 'none');\n    document.getElementById('btnNuevaEntrega').style.display = 'none';\n    document.getElementById('btnImportarMicrosip').style.display = 'none';\n    ENTREGAS_TAB = 'checadas';\n  } else if (ENTREGAS_TAB === 'checadas' && !META.es_logistica) {\n    ENTREGAS_TAB = 'lista';\n  }\n  await cambiarEntregasTab(ENTREGAS_TAB);\n}\n\nfunction abrirChecadasLogistica() {\n  ENTREGAS_TAB = 'checadas';\n  abrirEntregas();\n}\n\n// ---- Logística → 📱 Checadas: las del Checador app (selfie + ubicación), para\n// revisar si checaron los choferes. Es la misma lista que RH → Checador app,\n// sin registrar fotos (eso sigue siendo de RH).\nasync function renderChecadasLogistica() {\n  const cont = document.getElementById('entregasContenido');\n  const hoy = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);\n  const desde = (window.CHK_LOG_DESDE || hoy), hasta = (window.CHK_LOG_HASTA || hoy);\n  window.CHK_APP_RECARGAR = renderChecadasLogistica;\n  cont.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Cargando…</p>';\n  try {\n    const checadas = await api(`/api/rh/checador?desde=${desde}&hasta=${hasta}`);\n    const tipoColor = { entrada: '#2e9e5b', salida_comida: '#e0a326', regreso_comida: '#e0a326', salida: '#b23a3a' };\n    const personas = new Set(checadas.map(c => c.nombre_completo));\n    cont.innerHTML = `\n      <p style=\"font-size:12px; color:var(--muted); margin:0 0 10px;\">Checadas hechas desde la app (entrada, comida y salida) con selfie y ubicación.\n        Revisa la foto y el mapa de cada una; si la persona no coincide, márcala. Las fotos de la cara las registra Recursos Humanos.</p>\n      <div style=\"display:flex; gap:8px; align-items:end; flex-wrap:wrap; margin-bottom:8px;\">\n        <div class=\"field\" style=\"margin:0;\"><label>Desde</label><input type=\"date\" id=\"chkLogDesde\" value=\"${desde}\" /></div>\n        <div class=\"field\" style=\"margin:0;\"><label>Hasta</label><input type=\"date\" id=\"chkLogHasta\" value=\"${hasta}\" /></div>\n        <button class=\"secondary\" onclick=\"window.CHK_LOG_DESDE=document.getElementById('chkLogDesde').value; window.CHK_LOG_HASTA=document.getElementById('chkLogHasta').value; renderChecadasLogistica();\">Ver</button>\n        <span style=\"font-size:12px; color:var(--muted); margin-left:auto;\">${checadas.length} checada(s) de ${personas.size} persona(s)</span>\n      </div>\n      ${barraBusquedaDiscreta('busq_chk_log', 'tbody_chk_log', 'nombre, sucursal, tipo…')}\n      <table class=\"users\">\n        <thead><tr><th>Fecha y hora</th><th>Persona</th><th>Tipo</th><th>Ubicación</th><th>Cara</th><th>Revisión</th><th></th></tr></thead>\n        <tbody id=\"tbody_chk_log\">${checadas.map(c => `\n          <tr>\n            <td>${escapeHtml(String(c.fecha_hora).replace('T', ' ').slice(0, 16))}</td>\n            <td>${escapeHtml(c.nombre_completo)}${c.sucursal ? `<div style=\"font-size:11px; color:var(--muted);\">${escapeHtml(c.sucursal)}</div>` : ''}</td>\n            <td><span style=\"font-weight:700; color:${tipoColor[c.tipo] || 'inherit'};\">${escapeHtml(c.etiqueta)}</span></td>\n            <td>${c.lat != null ? `<a href=\"https://www.google.com/maps?q=${c.lat},${c.lng}\" target=\"_blank\" rel=\"noopener\">📍 Ver mapa</a>${c.precision_m ? `<div style=\"font-size:11px; color:var(--muted);\">±${Math.round(c.precision_m)} m</div>` : ''}` : '—'}</td>\n            <td>${c.cara_detectada === true ? '🙂 Sí' : c.cara_detectada === false ? '❌ No' : '—'}</td>\n            <td>${c.revision === 'ok' ? '✅ Coincide' : c.revision === 'no_coincide' ? '❌ No coincide' : '<span style=\"color:var(--muted);\">Sin revisar</span>'}</td>\n            <td><button class=\"secondary\" style=\"font-size:12px;\" onclick=\"verChecadaAppRH(${c.id})\">Ver foto</button></td>\n          </tr>`).join('') || '<tr><td colspan=\"7\" class=\"empty-col\">— sin checadas en esas fechas —</td></tr>'}</tbody>\n      </table>`;\n  } catch (e) {\n    cont.innerHTML = `<p style=\"color:var(--copper);\">${escapeHtml(e.message)}</p>`;\n  }\n}\n\nlet ENTREGAS_TAB = 'lista';\n"
  ],
  [
   "  document.getElementById('tabEntregasAgenda').classList.toggle('active', tab === 'agenda');\n  document.getElementById('tabEntregasVehiculos').classList.toggle('active', tab === 'vehiculos');\n  document.getElementById('tabEntregasChecklist').classList.toggle('active', tab === 'checklist');\n  if (tab === 'lista') {\n    await renderListaEntregas();\n  } else if (tab === 'checklist') {\n    await renderChecklistPlantillaEntregas();\n",
   "  document.getElementById('tabEntregasAgenda').classList.toggle('active', tab === 'agenda');\n  document.getElementById('tabEntregasVehiculos').classList.toggle('active', tab === 'vehiculos');\n  document.getElementById('tabEntregasChecklist').classList.toggle('active', tab === 'checklist');\n  document.getElementById('tabEntregasChecadas').classList.toggle('active', tab === 'checadas');\n  if (tab === 'checadas') {\n    await renderChecadasLogistica();\n  } else if (tab === 'lista') {\n    await renderListaEntregas();\n  } else if (tab === 'checklist') {\n    await renderChecklistPlantillaEntregas();\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_logistica_checadas.py")
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
            if nuevo in texto:
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
