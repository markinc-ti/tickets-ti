# -*- coding: utf-8 -*-
"""
Fase 3 de "Monitoreo de empleados": pantalla en Administrar para ver la
bitácora de eventos (web / programas / documentos) por persona y por
computadora.

Qué hace:
1. Nuevo endpoint GET /api/monitoreo/computadoras (admin) — lista las
   computadoras que ya han mandado algo, para el filtro.
2. Nueva pestaña "Monitoreo" en Administrar, con 3 filtros (persona,
   computadora, tipo) y una tabla con fecha/hora, persona, computadora,
   tipo (con color) y detalle. Se actualiza sola al cambiar cualquier
   filtro, sin recargar toda la pantalla.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_monitoreo_fase3.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS['backend/app.py'] = [
    [
        '@app.get("/api/monitoreo/eventos")\n'
        'def api_listar_eventos_monitoreo(usuario_id: Optional[int] = None, computadora: Optional[str] = None,\n'
        '                                  tipo: Optional[str] = None, admin: dict = Depends(requiere_admin)):\n'
        '    """Base para la bitácora (Fase 3 — la pantalla en el frontend viene\n'
        '    después). Por ahora ya se puede consultar directo por la URL."""\n'
        '    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo)\n',

        '@app.get("/api/monitoreo/eventos")\n'
        'def api_listar_eventos_monitoreo(usuario_id: Optional[int] = None, computadora: Optional[str] = None,\n'
        '                                  tipo: Optional[str] = None, admin: dict = Depends(requiere_admin)):\n'
        '    """Bitácora de monitoreo — filtrable por persona/computadora/tipo."""\n'
        '    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo)\n'
        '\n'
        '\n'
        '@app.get("/api/monitoreo/computadoras")\n'
        'def api_listar_computadoras_monitoreo(admin: dict = Depends(requiere_admin)):\n'
        '    """Nombres de computadoras que ya han mandado algún evento, para el\n'
        '    filtro de la bitácora."""\n'
        '    return db.listar_computadoras_monitoreo(admin["empresa_id"])\n',
    ],
]

ARCHIVOS['frontend/index.html'] = [
    # 1) Botón de la pestaña nueva.
    [
        '      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'borrado\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'borrado\')" style="color:var(--urgente);">Borrar datos</button>` : \'\'}\n'
        '    </div>\n'
        '  `;\n',

        '      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'monitoreo\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'monitoreo\')">🕵️ Monitoreo</button>` : \'\'}\n'
        '      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB===\'borrado\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'borrado\')" style="color:var(--urgente);">Borrar datos</button>` : \'\'}\n'
        '    </div>\n'
        '  `;\n',
    ],
    # 2) Rama en renderAdmin() para la pestaña nueva.
    [
        "  } else if (ADMIN_TAB === 'borrado' && esAdmin) {\n"
        '    renderBorradoMasivo(tabs);\n'
        '  }\n'
        '}\n',

        "  } else if (ADMIN_TAB === 'monitoreo' && esAdmin) {\n"
        '    await renderMonitoreoAdmin(tabs);\n'
        "  } else if (ADMIN_TAB === 'borrado' && esAdmin) {\n"
        '    renderBorradoMasivo(tabs);\n'
        '  }\n'
        '}\n'
        '\n'
        'const NOMBRES_TIPO_MONITOREO = { web: \'🌐 Web\', programa: \'🖥️ Programa\', documento: \'📄 Documento\' };\n'
        'const COLORES_TIPO_MONITOREO = { web: \'#5B9BD5\', programa: \'#9B59B6\', documento: \'#FFC000\' };\n'
        '\n'
        'async function renderMonitoreoAdmin(tabsHtml) {\n'
        "  const [usuarios, computadoras] = await Promise.all([\n"
        "    api('/api/usuarios'),\n"
        "    api('/api/monitoreo/computadoras'),\n"
        '  ]);\n'
        '  const monitoreados = usuarios.filter(u => u.monitoreo_activo);\n'
        "  document.getElementById('modalContent').innerHTML = `\n"
        '    ${tabsHtml}\n'
        '    <h2>🕵️ Bitácora de monitoreo</h2>\n'
        '    <p style="font-size:12px; color:var(--muted); margin-top:-8px;">Actividad reportada por el agente de Windows en las computadoras de las personas monitoreadas. Muestra las últimas 300 entradas según el filtro.</p>\n'
        '    <div style="display:flex; gap:8px; flex-wrap:wrap; margin:14px 0;">\n'
        '      <select id="monFiltroUsuario" onchange="filtrarMonitoreoAdmin()">\n'
        '        <option value="">Todas las personas</option>\n'
        "        ${monitoreados.map(u => `<option value=\"${u.id}\">${escapeHtml(u.nombre_completo)}</option>`).join('')}\n"
        '      </select>\n'
        '      <select id="monFiltroComputadora" onchange="filtrarMonitoreoAdmin()">\n'
        '        <option value="">Todas las computadoras</option>\n'
        "        ${computadoras.map(c => `<option value=\"${escapeHtml(c)}\">${escapeHtml(c)}</option>`).join('')}\n"
        '      </select>\n'
        '      <select id="monFiltroTipo" onchange="filtrarMonitoreoAdmin()">\n'
        '        <option value="">Todos los tipos</option>\n'
        '        <option value="web">🌐 Web</option>\n'
        '        <option value="programa">🖥️ Programa</option>\n'
        '        <option value="documento">📄 Documento</option>\n'
        '      </select>\n'
        '    </div>\n'
        '    <div id="monitoreoTablaContenedor"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n'
        '  `;\n'
        "  abrirModal('admin');\n"
        '  await filtrarMonitoreoAdmin();\n'
        '}\n'
        '\n'
        'async function filtrarMonitoreoAdmin() {\n'
        "  const cont = document.getElementById('monitoreoTablaContenedor');\n"
        '  if (!cont) return;\n'
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
        '  try {\n'
        "    const usuarioId = document.getElementById('monFiltroUsuario').value;\n"
        "    const computadora = document.getElementById('monFiltroComputadora').value;\n"
        "    const tipo = document.getElementById('monFiltroTipo').value;\n"
        '    const params = new URLSearchParams();\n'
        "    if (usuarioId) params.set('usuario_id', usuarioId);\n"
        "    if (computadora) params.set('computadora', computadora);\n"
        "    if (tipo) params.set('tipo', tipo);\n"
        '    const eventos = await api(`/api/monitoreo/eventos?${params.toString()}`);\n'
        '    if (!eventos.length) {\n'
        '      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Sin eventos con ese filtro.</p>\';\n'
        '      return;\n'
        '    }\n'
        '    cont.innerHTML = `\n'
        '      <div style="overflow-x:auto;">\n'
        '        <table class="users">\n'
        '          <thead><tr><th>Fecha/hora</th><th>Persona</th><th>Computadora</th><th>Tipo</th><th>Detalle</th></tr></thead>\n'
        '          <tbody>\n'
        '            ${eventos.map(e => `\n'
        '              <tr>\n'
        "                <td style=\"white-space:nowrap;\">${new Date(e.fecha_hora).toLocaleString('es-MX')}</td>\n"
        '                <td>${escapeHtml(e.nombre_completo)}</td>\n'
        "                <td>${escapeHtml(e.computadora || '—')}</td>\n"
        '                <td><span style="color:${COLORES_TIPO_MONITOREO[e.tipo] || \'var(--text)\'};">${NOMBRES_TIPO_MONITOREO[e.tipo] || escapeHtml(e.tipo)}</span></td>\n'
        '                <td style="max-width:420px; word-break:break-word;">${escapeHtml(e.detalle)}</td>\n'
        '              </tr>\n'
        "            `).join('')}\n"
        '          </tbody>\n'
        '        </table>\n'
        '      </div>\n'
        '    `;\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}\n',
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
            print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
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
                print(f"[{ruta}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py frontend/index.html")
    print('   git commit -m "Monitoreo Fase 3: pantalla de bitacora en Administrar"')
    print("   git push")


if __name__ == "__main__":
    main()
