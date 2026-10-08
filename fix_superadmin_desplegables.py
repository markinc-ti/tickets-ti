# -*- coding: utf-8 -*-
"""
Panel de Superadmin: convierte los botones sueltos en menus
desplegables (<details>) para que se vean ordenados en celular.

Que toca (todo en frontend/index.html):
  - CSS nuevo para .menu-desplegable (junto a .header-actions)
  - CSS: empresa-card/empresa-acciones ahora envuelven en varias lineas
  - HTML: header del superadmin -- Mi cuenta/Consumo/Uso de BD/Cotizador
    ahora viven dentro de un desplegable "Herramientas"
  - JS: renderEmpresas() -- los botones de cada empresa (Cambiar logo,
    Modulos, Cotizacion, WhatsApp, Respaldo, Clonar, Desactivar/Eliminar)
    ahora viven dentro de un desplegable "Acciones" por empresa

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    python fix_superadmin_desplegables.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['frontend/index.html'] = [
    [
        "  .header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }\n  .whoami { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); text-align: right; }\n  .whoami b { color: var(--text); }",
        "  .header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }\n  .whoami { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); text-align: right; }\n  .whoami b { color: var(--text); }\n\n  /* Menu desplegable (usado en el header del superadmin y en las acciones de cada empresa) */\n  details.menu-desplegable > summary {\n    list-style: none; cursor: pointer; user-select: none;\n    background: transparent; color: var(--text);\n    border: 1px solid var(--muted); font-family: 'JetBrains Mono', monospace;\n    font-size: 12px; padding: 9px 14px; display: inline-flex; align-items: center; gap: 6px;\n  }\n  details.menu-desplegable > summary::-webkit-details-marker { display: none; }\n  details.menu-desplegable > summary::marker { content: ''; }\n  details.menu-desplegable > summary::before { content: '▸'; font-size: 10px; }\n  details.menu-desplegable[open] > summary::before { content: '▾'; }\n  details.menu-desplegable[open] > summary { border-color: var(--copper); color: var(--copper); }\n  details.menu-desplegable .menu-opciones { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }",
    ],
    [
        "  .empresa-card {\n    display: flex; align-items: center; gap: 16px;\n    background: var(--panel-2); border: 1px solid rgba(198,142,63,0.2);\n    padding: 14px 16px; margin-bottom: 12px;\n  }\n  .empresa-card.inactivo { opacity: 0.45; }\n  .empresa-logo-chico { width: 48px; height: 48px; object-fit: contain; background: #fff; border-radius: 4px; padding: 4px; }\n  .empresa-logo-vacio { display:flex; align-items:center; justify-content:center; color: var(--muted); font-family:'JetBrains Mono',monospace; border: 1px dashed rgba(155,157,159,0.4); }\n  .empresa-info { flex: 1; }\n  .empresa-nombre { font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; }\n  .empresa-fecha { font-size: 11px; color: var(--muted); }\n  .empresa-acciones { display: flex; gap: 8px; align-items: center; }\n  .btn-file { cursor: pointer; display: inline-block; }",
        "  .empresa-card {\n    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;\n    background: var(--panel-2); border: 1px solid rgba(198,142,63,0.2);\n    padding: 14px 16px; margin-bottom: 12px;\n  }\n  .empresa-card.inactivo { opacity: 0.45; }\n  .empresa-logo-chico { width: 48px; height: 48px; object-fit: contain; background: #fff; border-radius: 4px; padding: 4px; }\n  .empresa-logo-vacio { display:flex; align-items:center; justify-content:center; color: var(--muted); font-family:'JetBrains Mono',monospace; border: 1px dashed rgba(155,157,159,0.4); }\n  .empresa-info { flex: 1; min-width: 140px; }\n  .empresa-nombre { font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 700; }\n  .empresa-fecha { font-size: 11px; color: var(--muted); }\n  .empresa-card > details.menu-desplegable { width: 100%; }\n  .empresa-acciones { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; width: 100%; }\n  .btn-file { cursor: pointer; display: inline-block; }",
    ],
    [
        '    <div class="header-actions">\n      <div class="whoami" id="whoamiSuper"></div>\n      <button class="secondary" onclick="abrirMiCuenta()">Mi cuenta</button>\n      <button class="secondary" onclick="abrirConsumoSuperadmin()">💰 Consumo</button>\n      <button class="secondary" onclick="abrirUsoDBSuperadmin()">📊 Uso de BD</button>\n      <button class="secondary" onclick="abrirCotizadorSuperadmin()">🧾 Cotizador</button>\n      <button class="primary" onclick="abrirCrearEmpresa()">+ NUEVA EMPRESA</button>\n      <button class="secondary" onclick="cerrarSesionConConfirmacion()">Salir</button>\n    </div>',
        '    <div class="header-actions">\n      <div class="whoami" id="whoamiSuper"></div>\n      <details class="menu-desplegable">\n        <summary>Herramientas</summary>\n        <div class="menu-opciones">\n          <button class="secondary" onclick="abrirMiCuenta()">Mi cuenta</button>\n          <button class="secondary" onclick="abrirConsumoSuperadmin()">💰 Consumo</button>\n          <button class="secondary" onclick="abrirUsoDBSuperadmin()">📊 Uso de BD</button>\n          <button class="secondary" onclick="abrirCotizadorSuperadmin()">🧾 Cotizador</button>\n        </div>\n      </details>\n      <button class="primary" onclick="abrirCrearEmpresa()">+ NUEVA EMPRESA</button>\n      <button class="secondary" onclick="cerrarSesionConConfirmacion()">Salir</button>\n    </div>',
    ],
    [
        'function renderEmpresas(empresas) {\n  document.getElementById(\'listaEmpresas\').innerHTML = empresas.map(e => `\n    <div class="empresa-card ${e.activo ? \'\' : \'inactivo\'}">\n      ${e.logo_base64 ? `<img src="${e.logo_base64}" class="empresa-logo-chico" />` : \'<div class="empresa-logo-chico empresa-logo-vacio">?</div>\'}\n      <div class="empresa-info">\n        <div class="empresa-nombre">${escapeHtml(e.nombre)}</div>\n        <div class="empresa-fecha">Creada ${e.creado_en.slice(0,10)}</div>\n      </div>\n      <div class="empresa-acciones">\n        <label class="secondary btn-file">\n          Cambiar logo\n          <input type="file" accept="image/*" style="display:none;" onchange="subirLogoEmpresa(${e.id}, this)" />\n        </label>\n        <button class="secondary" onclick="abrirModulosEmpresa(${e.id})">Módulos</button>\n        <button class="secondary" onclick="abrirCostosEmpresa(${e.id})">🧾 Cotización</button>\n        <button class="secondary" onclick="abrirConfigWhatsappEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">WhatsApp</button>\n        <button class="secondary" onclick="descargarRespaldoEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Respaldo</button>\n        <button class="secondary" onclick="abrirClonarEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Clonar</button>\n        ${e.activo\n          ? `<button class="danger" onclick="cambiarEstadoEmpresa(${e.id}, false)">Desactivar</button>`\n          : `<button class="secondary" onclick="cambiarEstadoEmpresa(${e.id}, true)">Reactivar</button>`}\n        <button class="danger" onclick="abrirEliminarEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Eliminar</button>\n      </div>\n    </div>\n  `).join(\'\') || \'<div class="empty-col">— aún no hay empresas, crea la primera —</div>\';\n}',
        'function renderEmpresas(empresas) {\n  document.getElementById(\'listaEmpresas\').innerHTML = empresas.map(e => `\n    <div class="empresa-card ${e.activo ? \'\' : \'inactivo\'}">\n      ${e.logo_base64 ? `<img src="${e.logo_base64}" class="empresa-logo-chico" />` : \'<div class="empresa-logo-chico empresa-logo-vacio">?</div>\'}\n      <div class="empresa-info">\n        <div class="empresa-nombre">${escapeHtml(e.nombre)}</div>\n        <div class="empresa-fecha">Creada ${e.creado_en.slice(0,10)}</div>\n      </div>\n      <details class="menu-desplegable">\n        <summary>⋮ Acciones</summary>\n        <div class="empresa-acciones">\n        <label class="secondary btn-file">\n          Cambiar logo\n          <input type="file" accept="image/*" style="display:none;" onchange="subirLogoEmpresa(${e.id}, this)" />\n        </label>\n        <button class="secondary" onclick="abrirModulosEmpresa(${e.id})">Módulos</button>\n        <button class="secondary" onclick="abrirCostosEmpresa(${e.id})">🧾 Cotización</button>\n        <button class="secondary" onclick="abrirConfigWhatsappEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">WhatsApp</button>\n        <button class="secondary" onclick="descargarRespaldoEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Respaldo</button>\n        <button class="secondary" onclick="abrirClonarEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Clonar</button>\n        ${e.activo\n          ? `<button class="danger" onclick="cambiarEstadoEmpresa(${e.id}, false)">Desactivar</button>`\n          : `<button class="secondary" onclick="cambiarEstadoEmpresa(${e.id}, true)">Reactivar</button>`}\n        <button class="danger" onclick="abrirEliminarEmpresa(${e.id}, \'${escapeHtml(e.nombre).replace(/\'/g,"\\\\\'")}\')">Eliminar</button>\n      </div>\n      </details>\n    </div>\n  `).join(\'\') || \'<div class="empty-col">— aún no hay empresas, crea la primera —</div>\';\n}',
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
    print('   git commit -m "Superadmin: menus desplegables para que se vea ordenado en celular"')
    print("   git push")


if __name__ == "__main__":
    main()
