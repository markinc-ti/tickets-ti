# -*- coding: utf-8 -*-
"""
Mejora la pantalla de "Monitoreo" en Administrar:

1. Arriba de la tabla, un panel con cada persona monitoreada, un punto de
   color (verde = actividad en los últimos 10 minutos = "en línea";
   gris = sin actividad reciente) y cuándo fue su último evento.
2. La tabla ahora pagina de 50 en 50 (con Anteriores/Siguientes), igual
   que "Artículos sin movimiento" en el Dashboard.
3. Al abrir la pantalla, por default solo muestra los eventos de HOY.
   Arriba hay un filtro "Desde / Hasta" para consultar otros días,
   mismo patrón que ya usamos en otras partes de la app.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_monitoreo_fase3_mejoras.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/db.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    [
        'def listar_eventos_monitoreo(empresa_id, usuario_id=None, computadora=None, tipo=None, limite=300):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    query = """SELECT e.id, e.usuario_id, u.nombre_completo, e.computadora, e.tipo, e.detalle, e.fecha_hora\n'
        '               FROM monitoreo_eventos e JOIN users u ON u.id = e.usuario_id\n'
        '               WHERE e.empresa_id = %s"""\n'
        '    params = [empresa_id]\n'
        '    if usuario_id:\n'
        '        query += " AND e.usuario_id = %s"; params.append(usuario_id)\n'
        '    if computadora:\n'
        '        query += " AND e.computadora = %s"; params.append(computadora)\n'
        '    if tipo:\n'
        '        query += " AND e.tipo = %s"; params.append(tipo)\n'
        '    query += " ORDER BY e.fecha_hora DESC LIMIT %s"; params.append(limite)\n'
        '    cur.execute(query, params)\n'
        '    rows = [dict(r) for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return rows\n',

        'def listar_eventos_monitoreo(empresa_id, usuario_id=None, computadora=None, tipo=None,\n'
        '                              fecha_inicio=None, fecha_fin=None, limite=5000):\n'
        '    """fecha_inicio/fecha_fin: \'YYYY-MM-DD\', fecha_fin excluida. Se\n'
        '    interpretan en hora de Ciudad de México, no UTC, para que "hoy"\n'
        '    coincida con el día real de la persona que consulta."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    query = """SELECT e.id, e.usuario_id, u.nombre_completo, e.computadora, e.tipo, e.detalle, e.fecha_hora\n'
        '               FROM monitoreo_eventos e JOIN users u ON u.id = e.usuario_id\n'
        '               WHERE e.empresa_id = %s"""\n'
        '    params = [empresa_id]\n'
        '    if usuario_id:\n'
        '        query += " AND e.usuario_id = %s"; params.append(usuario_id)\n'
        '    if computadora:\n'
        '        query += " AND e.computadora = %s"; params.append(computadora)\n'
        '    if tipo:\n'
        '        query += " AND e.tipo = %s"; params.append(tipo)\n'
        '    if fecha_inicio:\n'
        '        query += " AND e.fecha_hora >= (%s::date AT TIME ZONE \'America/Mexico_City\')"; params.append(fecha_inicio)\n'
        '    if fecha_fin:\n'
        '        query += " AND e.fecha_hora < (%s::date AT TIME ZONE \'America/Mexico_City\')"; params.append(fecha_fin)\n'
        '    query += " ORDER BY e.fecha_hora DESC LIMIT %s"; params.append(limite)\n'
        '    cur.execute(query, params)\n'
        '    rows = [dict(r) for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return rows\n'
        '\n'
        '\n'
        'def listar_estado_monitoreo(empresa_id):\n'
        '    """Por cada persona monitoreada: su última actividad reportada y si\n'
        '    cuenta como "en línea" (algo en los últimos 10 minutos). Se calcula\n'
        '    todo en SQL para no mezclar la hora "naive" que usa el resto de la\n'
        '    app con la hora real (con zona) que trae esta tabla."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("""\n'
        '        SELECT u.id, u.nombre_completo,\n'
        '               MAX(e.fecha_hora) AS ultima_actividad,\n'
        '               STRING_AGG(DISTINCT e.computadora, \', \') AS computadoras,\n'
        '               (MAX(e.fecha_hora) > NOW() - INTERVAL \'10 minutes\') AS en_linea\n'
        '        FROM users u\n'
        '        LEFT JOIN monitoreo_eventos e ON e.usuario_id = u.id\n'
        '        WHERE u.empresa_id = %s AND u.monitoreo_activo = TRUE\n'
        '        GROUP BY u.id, u.nombre_completo\n'
        '        ORDER BY u.nombre_completo\n'
        '    """, (empresa_id,))\n'
        '    rows = [dict(r) for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return rows\n',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    [
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

        '@app.get("/api/monitoreo/eventos")\n'
        'def api_listar_eventos_monitoreo(usuario_id: Optional[int] = None, computadora: Optional[str] = None,\n'
        '                                  tipo: Optional[str] = None, fecha_inicio: Optional[str] = None,\n'
        '                                  fecha_fin: Optional[str] = None, admin: dict = Depends(requiere_admin)):\n'
        '    """Bitácora de monitoreo — filtrable por persona/computadora/tipo/fecha."""\n'
        '    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo, fecha_inicio, fecha_fin)\n'
        '\n'
        '\n'
        '@app.get("/api/monitoreo/computadoras")\n'
        'def api_listar_computadoras_monitoreo(admin: dict = Depends(requiere_admin)):\n'
        '    """Nombres de computadoras que ya han mandado algún evento, para el\n'
        '    filtro de la bitácora."""\n'
        '    return db.listar_computadoras_monitoreo(admin["empresa_id"])\n'
        '\n'
        '\n'
        '@app.get("/api/monitoreo/estado")\n'
        'def api_estado_monitoreo(admin: dict = Depends(requiere_admin)):\n'
        '    """Última actividad y si está "en línea" (últimos 10 min), por cada\n'
        '    persona monitoreada."""\n'
        '    return db.listar_estado_monitoreo(admin["empresa_id"])\n',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        "const NOMBRES_TIPO_MONITOREO = { web: '🌐 Web', programa: '🖥️ Programa', documento: '📄 Documento' };\n"
        "const COLORES_TIPO_MONITOREO = { web: '#5B9BD5', programa: '#9B59B6', documento: '#FFC000' };\n"
        '\n'
        'async function renderMonitoreoAdmin(tabsHtml) {\n'
        '  const [usuarios, computadoras] = await Promise.all([\n'
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

        "const NOMBRES_TIPO_MONITOREO = { web: '🌐 Web', programa: '🖥️ Programa', documento: '📄 Documento' };\n"
        "const COLORES_TIPO_MONITOREO = { web: '#5B9BD5', programa: '#9B59B6', documento: '#FFC000' };\n"
        'let MONITOREO_EVENTOS_ACTUALES = [];\n'
        'let MONITOREO_PAGINA = 0; // 0-indexado, de 50 en 50\n'
        '\n'
        'function _monFechaHoyISO() {\n'
        "  return new Date().toLocaleDateString('sv-SE'); // YYYY-MM-DD, hora local del navegador\n"
        '}\n'
        '\n'
        'function _monFormatoRelativo(fechaISO) {\n'
        '  if (!fechaISO) return \'sin actividad\';\n'
        '  const ms = Date.now() - new Date(fechaISO).getTime();\n'
        '  const min = Math.floor(ms / 60000);\n'
        "  if (min < 1) return 'justo ahora';\n"
        "  if (min < 60) return `hace ${min} min`;\n"
        '  const horas = Math.floor(min / 60);\n'
        "  if (horas < 24) return `hace ${horas} h`;\n"
        "  return new Date(fechaISO).toLocaleDateString('es-MX');\n"
        '}\n'
        '\n'
        'async function renderMonitoreoAdmin(tabsHtml) {\n'
        '  const [usuarios, computadoras, estado] = await Promise.all([\n'
        "    api('/api/usuarios'),\n"
        "    api('/api/monitoreo/computadoras'),\n"
        "    api('/api/monitoreo/estado'),\n"
        '  ]);\n'
        '  const monitoreados = usuarios.filter(u => u.monitoreo_activo);\n'
        '  const hoy = _monFechaHoyISO();\n'
        "  document.getElementById('modalContent').innerHTML = `\n"
        '    ${tabsHtml}\n'
        '    <h2>🕵️ Bitácora de monitoreo</h2>\n'
        '    <p style="font-size:12px; color:var(--muted); margin-top:-8px;">Actividad reportada por el agente de Windows en las computadoras de las personas monitoreadas.</p>\n'
        '    <div style="display:flex; flex-wrap:wrap; gap:10px; margin:14px 0;">\n'
        '      ${estado.length ? estado.map(p => `\n'
        '        <div style="display:flex; align-items:center; gap:6px; padding:6px 10px; border:1px solid rgba(155,157,159,0.3); border-radius:6px; font-size:12px;">\n'
        "          <span style=\"display:inline-block; width:8px; height:8px; border-radius:50%; background:${p.en_linea ? 'var(--trace)' : 'var(--muted)'};\"></span>\n"
        '          <span><b>${escapeHtml(p.nombre_completo)}</b> — ${p.en_linea ? \'en línea\' : _monFormatoRelativo(p.ultima_actividad)}</span>\n'
        '        </div>\n'
        "      `).join('') : '<p style=\"font-size:12px; color:var(--muted);\">Nadie tiene monitoreo activo todavía.</p>'}\n"
        '    </div>\n'
        '    <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:14px 0;">\n'
        '      <label style="font-size:12px; color:var(--muted);">Desde</label>\n'
        '      <input type="date" id="monFiltroDesde" value="${hoy}" onchange="filtrarMonitoreoAdmin()" style="width:auto;" />\n'
        '      <label style="font-size:12px; color:var(--muted);">Hasta</label>\n'
        '      <input type="date" id="monFiltroHasta" value="${hoy}" onchange="filtrarMonitoreoAdmin()" style="width:auto;" />\n'
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
        '  MONITOREO_PAGINA = 0;\n'
        '  try {\n'
        "    const usuarioId = document.getElementById('monFiltroUsuario').value;\n"
        "    const computadora = document.getElementById('monFiltroComputadora').value;\n"
        "    const tipo = document.getElementById('monFiltroTipo').value;\n"
        "    const desde = document.getElementById('monFiltroDesde').value;\n"
        "    const hasta = document.getElementById('monFiltroHasta').value;\n"
        '    const params = new URLSearchParams();\n'
        "    if (usuarioId) params.set('usuario_id', usuarioId);\n"
        "    if (computadora) params.set('computadora', computadora);\n"
        "    if (tipo) params.set('tipo', tipo);\n"
        '    if (desde) {\n'
        "      params.set('fecha_inicio', desde);\n"
        '      // \"Hasta\" es inclusivo en el input — el backend espera fecha_fin\n'
        '      // EXCLUSIVA, así que se le suma 1 día.\n'
        "      const hastaExclusiva = new Date((hasta || desde) + 'T00:00:00');\n"
        '      hastaExclusiva.setDate(hastaExclusiva.getDate() + 1);\n'
        "      params.set('fecha_fin', hastaExclusiva.toISOString().slice(0, 10));\n"
        '    }\n'
        '    const eventos = await api(`/api/monitoreo/eventos?${params.toString()}`);\n'
        '    MONITOREO_EVENTOS_ACTUALES = eventos;\n'
        '    renderTablaMonitoreo();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}\n'
        '\n'
        'function renderTablaMonitoreo() {\n'
        "  const cont = document.getElementById('monitoreoTablaContenedor');\n"
        '  if (!cont) return;\n'
        '  const eventos = MONITOREO_EVENTOS_ACTUALES;\n'
        '  if (!eventos.length) {\n'
        '    cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Sin eventos con ese filtro.</p>\';\n'
        '    return;\n'
        '  }\n'
        '  const porPagina = 50;\n'
        '  const totalPaginas = Math.max(1, Math.ceil(eventos.length / porPagina));\n'
        '  if (MONITOREO_PAGINA >= totalPaginas) MONITOREO_PAGINA = totalPaginas - 1;\n'
        '  const inicio = MONITOREO_PAGINA * porPagina;\n'
        '  const pagina = eventos.slice(inicio, inicio + porPagina);\n'
        '  cont.innerHTML = `\n'
        '    <div style="overflow-x:auto;">\n'
        '      <table class="users">\n'
        '        <thead><tr><th>Fecha/hora</th><th>Persona</th><th>Computadora</th><th>Tipo</th><th>Detalle</th></tr></thead>\n'
        '        <tbody>\n'
        '          ${pagina.map(e => `\n'
        '            <tr>\n'
        "              <td style=\"white-space:nowrap;\">${new Date(e.fecha_hora).toLocaleString('es-MX')}</td>\n"
        '              <td>${escapeHtml(e.nombre_completo)}</td>\n'
        "              <td>${escapeHtml(e.computadora || '—')}</td>\n"
        '              <td><span style="color:${COLORES_TIPO_MONITOREO[e.tipo] || \'var(--text)\'};">${NOMBRES_TIPO_MONITOREO[e.tipo] || escapeHtml(e.tipo)}</span></td>\n'
        '              <td style="max-width:420px; word-break:break-word;">${escapeHtml(e.detalle)}</td>\n'
        '            </tr>\n'
        "          `).join('')}\n"
        '        </tbody>\n'
        '      </table>\n'
        '    </div>\n'
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">\n'
        '      <button class="secondary" style="padding:5px 14px;" ${MONITOREO_PAGINA === 0 ? \'disabled\' : \'\'} onclick="cambiarPaginaMonitoreo(-1)">← Anteriores 50</button>\n'
        '      <span style="font-size:12px; color:var(--muted);">Página ${MONITOREO_PAGINA + 1} de ${totalPaginas} (${eventos.length} evento(s) en total)</span>\n'
        '      <button class="secondary" style="padding:5px 14px;" ${MONITOREO_PAGINA >= totalPaginas - 1 ? \'disabled\' : \'\'} onclick="cambiarPaginaMonitoreo(1)">Siguientes 50 →</button>\n'
        '    </div>\n'
        '  `;\n'
        '}\n'
        '\n'
        'function cambiarPaginaMonitoreo(delta) {\n'
        '  MONITOREO_PAGINA += delta;\n'
        '  renderTablaMonitoreo();\n'
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
    print("   git add backend/db.py backend/app.py frontend/index.html")
    print('   git commit -m "Monitoreo: estado en linea, paginacion de 50, filtro de fecha (default hoy)"')
    print("   git push")


if __name__ == "__main__":
    main()
