# -*- coding: utf-8 -*-
"""
MARK INC: SOPORTE TECNICO DENTRO DE LOGISTICA (ENTREGAS)
En Mark Inc el modulo de Soporte tecnico (el mismo de Peymar) aparece como
pestana "Soporte tecnico" dentro de Entregas / Logistica, con Analisis y
Nuevo reporte. En Mark Inc ya no sale como boton aparte en el menu (a quien
tenga Entregas). Peymar se queda igual.
Toca: frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_soporte_en_logistica.py
"""
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "      <button class=\"admin-tab\" id=\"tabEntregasVehiculos\" onclick=\"cambiarEntregasTab('vehiculos')\" style=\"display:none;\">🚚 Vehículos</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecklist\" onclick=\"cambiarEntregasTab('checklist')\" style=\"display:none;\">☑️ Checklist</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecadas\" onclick=\"cambiarEntregasTab('checadas')\" style=\"display:none;\">📱 Checadas</button>\n    </div>\n    <div id=\"entregasContenido\" style=\"max-width:1200px; margin:0 auto;\"></div>\n  </main>\n",
   "      <button class=\"admin-tab\" id=\"tabEntregasVehiculos\" onclick=\"cambiarEntregasTab('vehiculos')\" style=\"display:none;\">🚚 Vehículos</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecklist\" onclick=\"cambiarEntregasTab('checklist')\" style=\"display:none;\">☑️ Checklist</button>\n      <button class=\"admin-tab\" id=\"tabEntregasChecadas\" onclick=\"cambiarEntregasTab('checadas')\" style=\"display:none;\">📱 Checadas</button>\n      <button class=\"admin-tab\" id=\"tabEntregasSoporte\" onclick=\"cambiarEntregasTab('soporte')\" style=\"display:none;\">🛠️ Soporte técnico</button>\n    </div>\n    <div id=\"entregasContenido\" style=\"max-width:1200px; margin:0 auto;\"></div>\n  </main>\n"
  ],
  [
   "  tabsEntregas: [\n    { titulo: '🚚 Operación', ids: ['tabEntregasLista', 'tabEntregasAgenda'] },\n    { titulo: '⚙️ Configuración', ids: ['tabEntregasVehiculos', 'tabEntregasChecklist'] },\n  ],\n};\n\n",
   "  tabsEntregas: [\n    { titulo: '🚚 Operación', ids: ['tabEntregasLista', 'tabEntregasAgenda'] },\n    { titulo: '⚙️ Configuración', ids: ['tabEntregasVehiculos', 'tabEntregasChecklist'] },\n    { titulo: '🛠️ Soporte técnico', ids: ['tabEntregasSoporte'] },\n  ],\n};\n\n"
  ],
  [
   "  document.getElementById('btnCRM').style.display = META.mis_permisos.acceso_crm ? 'flex' : 'none';\n  document.getElementById('btnShopify').style.display = META.mis_permisos.acceso_shopify ? 'flex' : 'none';\n  document.getElementById('btnTurnos').style.display = META.mis_permisos.acceso_turnos ? 'flex' : 'none';\n  document.getElementById('btnSoporte').style.display = META.mis_permisos.acceso_soporte ? 'flex' : 'none';\n\n  // El menú principal es la primera pantalla tras iniciar sesión — desde ahí\n  // se entra a cada módulo según los permisos que ya se acaban de calcular arriba.\n",
   "  document.getElementById('btnCRM').style.display = META.mis_permisos.acceso_crm ? 'flex' : 'none';\n  document.getElementById('btnShopify').style.display = META.mis_permisos.acceso_shopify ? 'flex' : 'none';\n  document.getElementById('btnTurnos').style.display = META.mis_permisos.acceso_turnos ? 'flex' : 'none';\n  // Mark·Inc: Soporte técnico vive dentro de Logística (Entregas → 🛠️ Soporte técnico).\n  document.getElementById('btnSoporte').style.display = (META.mis_permisos.acceso_soporte && !_soporteEnLogistica()) ? 'flex' : 'none';\n\n  // El menú principal es la primera pantalla tras iniciar sesión — desde ahí\n  // se entra a cada módulo según los permisos que ya se acaban de calcular arriba.\n"
  ],
  [
   "  document.getElementById('entregasScreen').style.display = 'block';\n  document.getElementById('whoamiEntregas').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;\n  const esInstalador = SESION.usuario.rol === 'instalador';\n  document.getElementById('btnNuevaEntrega').style.display = esInstalador ? 'none' : 'inline-block';\n  document.getElementById('btnImportarMicrosip').style.display = esInstalador ? 'none' : 'inline-block';\n  document.getElementById('btnVolverDesdeEntregas').style.display = esInstalador ? 'none' : 'inline-block';\n",
   "  document.getElementById('entregasScreen').style.display = 'block';\n  document.getElementById('whoamiEntregas').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;\n  const esInstalador = SESION.usuario.rol === 'instalador';\n  ['btnNuevaEntrega', 'btnImportarMicrosip'].forEach(i => delete document.getElementById(i).dataset.ocultoSoporte);\n  document.getElementById('btnNuevaEntrega').style.display = esInstalador ? 'none' : 'inline-block';\n  document.getElementById('btnImportarMicrosip').style.display = esInstalador ? 'none' : 'inline-block';\n  document.getElementById('btnVolverDesdeEntregas').style.display = esInstalador ? 'none' : 'inline-block';\n"
  ],
  [
   "  } else if (ENTREGAS_TAB === 'checadas' && !META.es_logistica) {\n    ENTREGAS_TAB = 'lista';\n  }\n  await cambiarEntregasTab(ENTREGAS_TAB);\n}\n\n",
   "  } else if (ENTREGAS_TAB === 'checadas' && !META.es_logistica) {\n    ENTREGAS_TAB = 'lista';\n  }\n  document.getElementById('tabEntregasSoporte').style.display = _soporteEnLogistica() ? 'inline-block' : 'none';\n  if (ENTREGAS_TAB === 'soporte' && !_soporteEnLogistica()) ENTREGAS_TAB = 'lista';\n  await cambiarEntregasTab(ENTREGAS_TAB);\n}\n\n"
  ],
  [
   "  document.getElementById('tabEntregasVehiculos').classList.toggle('active', tab === 'vehiculos');\n  document.getElementById('tabEntregasChecklist').classList.toggle('active', tab === 'checklist');\n  document.getElementById('tabEntregasChecadas').classList.toggle('active', tab === 'checadas');\n  if (tab === 'checadas') {\n    await renderChecadasLogistica();\n  } else if (tab === 'lista') {\n    await renderListaEntregas();\n",
   "  document.getElementById('tabEntregasVehiculos').classList.toggle('active', tab === 'vehiculos');\n  document.getElementById('tabEntregasChecklist').classList.toggle('active', tab === 'checklist');\n  document.getElementById('tabEntregasChecadas').classList.toggle('active', tab === 'checadas');\n  document.getElementById('tabEntregasSoporte').classList.toggle('active', tab === 'soporte');\n  const btnNuevaEnt = document.getElementById('btnNuevaEntrega'), btnImpMs = document.getElementById('btnImportarMicrosip');\n  if (tab === 'soporte') {\n    if (btnNuevaEnt.style.display !== 'none') { btnNuevaEnt.dataset.ocultoSoporte = '1'; btnNuevaEnt.style.display = 'none'; }\n    if (btnImpMs.style.display !== 'none') { btnImpMs.dataset.ocultoSoporte = '1'; btnImpMs.style.display = 'none'; }\n  } else {\n    [btnNuevaEnt, btnImpMs].forEach(b => { if (b.dataset.ocultoSoporte) { delete b.dataset.ocultoSoporte; b.style.display = 'inline-block'; } });\n  }\n  _devolverSoporteASuPantalla();\n  if (tab === 'soporte') {\n    await renderSoporteEnLogistica();\n  } else if (tab === 'checadas') {\n    await renderChecadasLogistica();\n  } else if (tab === 'lista') {\n    await renderListaEntregas();\n"
  ],
  [
   "   'crmScreen', 'shopifyScreen', 'turnosScreen'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });\n}\n\nasync function abrirSoporte() {\n  _ocultarPantallasParaSoporte();\n  document.getElementById('soporteScreen').style.display = 'block';\n  document.getElementById('whoamiSoporte').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;\n",
   "   'crmScreen', 'shopifyScreen', 'turnosScreen'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });\n}\n\n// Mark·Inc: el módulo de Soporte técnico se usa dentro de Logística (Entregas).\n// Peymar lo sigue teniendo como botón propio en el menú principal.\nfunction _soporteEnLogistica() {\n  const p = (META && META.mis_permisos) || {};\n  return Number(SESION.usuario.empresa_id) === 1 && !!p.acceso_soporte && !!p.acceso_entregas;\n}\n\n// El contenido de Soporte (#soporteContenido) se \"presta\" a Logística: se mueve\n// dentro de la pestaña y regresa a su pantalla antes de pintar otra cosa.\nfunction _devolverSoporteASuPantalla() {\n  const cont = document.getElementById('soporteContenido');\n  const casa = document.querySelector('#soporteScreen main');\n  if (cont && casa && cont.parentElement !== casa) casa.appendChild(cont);\n}\n\nasync function renderSoporteEnLogistica() {\n  const ent = document.getElementById('entregasContenido');\n  ent.innerHTML = `\n    <div style=\"display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;\">\n      <div><b>🛠️ Soporte técnico</b> <span style=\"color:var(--muted); font-size:12px;\">mantenimiento y garantías</span></div>\n      <div style=\"display:flex; gap:8px;\">\n        <button class=\"secondary\" onclick=\"abrirAnalisisSoporte()\">📊 Análisis</button>\n        <button class=\"primary\" onclick=\"abrirNuevoSoporte()\">+ Nuevo reporte</button>\n      </div>\n    </div>\n    <div id=\"soporteEnLogistica\"></div>`;\n  const cont = document.getElementById('soporteContenido');\n  document.getElementById('soporteEnLogistica').appendChild(cont);\n  await cargarSoporte();\n}\n\nasync function abrirSoporte() {\n  if (_soporteEnLogistica()) { ENTREGAS_TAB = 'soporte'; return abrirEntregas(); }\n  _devolverSoporteASuPantalla();\n  _ocultarPantallasParaSoporte();\n  document.getElementById('soporteScreen').style.display = 'block';\n  document.getElementById('whoamiSoporte').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_soporte_en_logistica.py")
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
