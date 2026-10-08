# -*- coding: utf-8 -*-
"""
Panel de Administrador: agrupa las 16 pestanas en categorias
desplegables (<details>) para que se vean ordenadas en celular,
igual que se hizo antes en el panel de Superadmin.

Categorias:
  - Organizacion: Usuarios, Departamentos, Categorias, Sucursales, Accesos
  - Configuracion: Politicas, Apariencia, Terminologia
  - Integraciones: Microsip, Explorador Microsip, Shopify, Geotab,
    Geocodificacion, Importar reparaciones
  - Reportes: Reportador, Monitoreo
  - Zona de riesgo: Borrar datos

La categoria que contiene la pestana activa se abre sola; las demas
quedan cerradas. No cambia ninguna logica, solo como se agrupan
visualmente los mismos botones de siempre.

Que toca (todo en frontend/index.html):
  - CSS: estilos para agrupar las categorias
  - JS: renderAdmin() -- arma las pestanas por categoria

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    python fix_admin_desplegables.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['frontend/index.html'] = [
    [
        "  .admin-tabs { display: flex; gap: 2px; margin-bottom: 22px; border-bottom: 1px solid rgba(155,157,159,0.2); flex-wrap: wrap; }\n  .admin-tab {\n    background: none; border: none; color: var(--muted); font-family: 'JetBrains Mono', monospace;\n    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 14px;\n    cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap;\n  }\n  .admin-tab.active { color: var(--copper); border-bottom-color: var(--copper); }",
        "  .admin-tabs { display: flex; gap: 2px; margin-bottom: 22px; border-bottom: 1px solid rgba(155,157,159,0.2); flex-wrap: wrap; }\n  .admin-tab {\n    background: none; border: none; color: var(--muted); font-family: 'JetBrains Mono', monospace;\n    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 14px;\n    cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap;\n  }\n  .admin-tab.active { color: var(--copper); border-bottom-color: var(--copper); }\n  .admin-tabs-categorias { display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }\n  .admin-tabs-categorias details.menu-desplegable { border: 1px solid rgba(155,157,159,0.2); }\n  .admin-tabs-categorias details.menu-desplegable > summary { width: 100%; box-sizing: border-box; border: none; }\n  .admin-tabs-categorias details.menu-desplegable[open] > summary { border-bottom: 1px solid rgba(155,157,159,0.2); }\n  .admin-tabs-categorias .admin-tabs { margin: 10px 12px 12px; border-bottom: none; }",
    ],
    [
        '  const tabs = `\n    <div class="admin-tabs">\n      <button class="admin-tab ${ADMIN_TAB===\'usuarios\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'usuarios\')">Usuarios</button>\n      <button class="admin-tab ${ADMIN_TAB===\'departamentos\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'departamentos\')">Departamentos</button>\n      <button class="admin-tab ${ADMIN_TAB===\'categorias\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'categorias\')">Categorías</button>\n      <button class="admin-tab ${ADMIN_TAB===\'sucursales\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'sucursales\')">Sucursales</button>\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'accesos\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'accesos\')">Accesos</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'politicas\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'politicas\')">Políticas</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'apariencia\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'apariencia\')">Apariencia</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'reportador\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'reportador\')">🧾 Reportador</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'explorador_microsip\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'explorador_microsip\')">🔍 Explorador Microsip</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'terminologia\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'terminologia\')">Terminología</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'microsip\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'microsip\')">Microsip</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'shopify\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'shopify\')">🛍️ Shopify</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'geotab\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'geotab\')">📍 Geotab (GPS)</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'locationiq\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'locationiq\')">🗺️ Geocodificación</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'importar-reparaciones\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'importar-reparaciones\')">Importar reparaciones</button>` : \'\'}\n      ${puedeVerMonitoreo ? `<button class="admin-tab ${ADMIN_TAB===\'monitoreo\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'monitoreo\')">🕵️ Monitoreo</button>` : \'\'}\n      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'borrado\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'borrado\')" style="color:var(--urgente);">Borrar datos</button>` : \'\'}\n    </div>\n  `;',
        '  const grupoOrganizacion = [\'usuarios\',\'departamentos\',\'categorias\',\'sucursales\',\'accesos\'].includes(ADMIN_TAB);\n  const grupoConfiguracion = [\'politicas\',\'apariencia\',\'terminologia\'].includes(ADMIN_TAB);\n  const grupoIntegraciones = [\'microsip\',\'explorador_microsip\',\'shopify\',\'geotab\',\'locationiq\',\'importar-reparaciones\'].includes(ADMIN_TAB);\n  const grupoReportes = [\'reportador\',\'monitoreo\'].includes(ADMIN_TAB);\n  const grupoRiesgo = [\'borrado\'].includes(ADMIN_TAB);\n  const tabs = `\n    <div class="admin-tabs-categorias">\n      <details class="menu-desplegable" ${grupoOrganizacion ? \'open\' : \'\'}>\n        <summary>Organización</summary>\n        <div class="admin-tabs">\n          <button class="admin-tab ${ADMIN_TAB===\'usuarios\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'usuarios\')">Usuarios</button>\n          <button class="admin-tab ${ADMIN_TAB===\'departamentos\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'departamentos\')">Departamentos</button>\n          <button class="admin-tab ${ADMIN_TAB===\'categorias\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'categorias\')">Categorías</button>\n          <button class="admin-tab ${ADMIN_TAB===\'sucursales\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'sucursales\')">Sucursales</button>\n          ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'accesos\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'accesos\')">Accesos</button>` : \'\'}\n        </div>\n      </details>\n      ${esAdmin ? `\n      <details class="menu-desplegable" ${grupoConfiguracion ? \'open\' : \'\'}>\n        <summary>Configuración</summary>\n        <div class="admin-tabs">\n          <button class="admin-tab ${ADMIN_TAB===\'politicas\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'politicas\')">Políticas</button>\n          <button class="admin-tab ${ADMIN_TAB===\'apariencia\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'apariencia\')">Apariencia</button>\n          <button class="admin-tab ${ADMIN_TAB===\'terminologia\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'terminologia\')">Terminología</button>\n        </div>\n      </details>\n      <details class="menu-desplegable" ${grupoIntegraciones ? \'open\' : \'\'}>\n        <summary>Integraciones</summary>\n        <div class="admin-tabs">\n          <button class="admin-tab ${ADMIN_TAB===\'microsip\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'microsip\')">Microsip</button>\n          <button class="admin-tab ${ADMIN_TAB===\'explorador_microsip\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'explorador_microsip\')">🔍 Explorador Microsip</button>\n          <button class="admin-tab ${ADMIN_TAB===\'shopify\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'shopify\')">🛍️ Shopify</button>\n          <button class="admin-tab ${ADMIN_TAB===\'geotab\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'geotab\')">📍 Geotab (GPS)</button>\n          <button class="admin-tab ${ADMIN_TAB===\'locationiq\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'locationiq\')">🗺️ Geocodificación</button>\n          <button class="admin-tab ${ADMIN_TAB===\'importar-reparaciones\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'importar-reparaciones\')">Importar reparaciones</button>\n        </div>\n      </details>` : \'\'}\n      ${(esAdmin || puedeVerMonitoreo) ? `\n      <details class="menu-desplegable" ${grupoReportes ? \'open\' : \'\'}>\n        <summary>Reportes</summary>\n        <div class="admin-tabs">\n          ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'reportador\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'reportador\')">🧾 Reportador</button>` : \'\'}\n          ${puedeVerMonitoreo ? `<button class="admin-tab ${ADMIN_TAB===\'monitoreo\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'monitoreo\')">🕵️ Monitoreo</button>` : \'\'}\n        </div>\n      </details>` : \'\'}\n      ${esAdmin ? `\n      <details class="menu-desplegable" ${grupoRiesgo ? \'open\' : \'\'}>\n        <summary style="color:var(--urgente);">Zona de riesgo</summary>\n        <div class="admin-tabs">\n          <button class="admin-tab ${ADMIN_TAB===\'borrado\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'borrado\')" style="color:var(--urgente);">Borrar datos</button>\n        </div>\n      </details>` : \'\'}\n    </div>\n  `;',
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False

    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print("[" + ruta + "] " + str(cambios) + "/" + str(len(cambios_lista)) + " cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Administrador: agrupar pestanas en categorias desplegables para celular"')
    print("   git push")


if __name__ == "__main__":
    main()
