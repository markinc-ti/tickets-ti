# -*- coding: utf-8 -*-
"""
Nueva tarjeta de Dashboard: "Artículos sin movimiento" — mismo dominio que
"Valor del inventario" (CAPAS_COSTOS/ALMACENES, a costo), pero mostrando
SOLO los artículos que JAMÁS se han vendido por Punto de Venta en ninguna
sucursal, en todo el historial de Microsip (no un rango de fechas).
Ordenados por costo unitario (de mayor a menor), TODOS (no solo top 50),
paginados de 50 en 50 en el frontend. El total por sucursal es el valor en
dinero (costo × existencia) de esos artículos sin movimiento.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_articulos_sin_movimiento.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/microsip.py — nueva función, insertada justo después de
# obtener_valor_inventario_por_almacen (mismo bloque de tablas/patrón).
# ---------------------------------------------------------------------------
ARCHIVOS['backend/microsip.py'] = [
    [
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        '# =============================================================================\n'
        '# DASHBOARD: descuentos otorgados en Punto de Venta — usa DOCTOS_PV_DET\n',

        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        'def obtener_articulos_sin_movimiento_por_almacen(config: dict):\n'
        '    """Artículos con existencia > 0 en cada almacén que JAMÁS se han\n'
        '    vendido por Punto de Venta, en ninguna sucursal, en todo el historial\n'
        '    de Microsip (no un rango de fechas). Mismo criterio de\n'
        '    existencia/costo que \'Valor del inventario\' (CAPAS_COSTOS por\n'
        '    ALMACEN_ID), cruzado contra el histórico completo de\n'
        '    DOCTOS_PV_DET/DOCTOS_PV para excluir los que sí se han vendido\n'
        '    alguna vez. Se devuelven TODOS los artículos (no solo un top 50) —\n'
        '    el frontend pagina de 50 en 50. Ordenados por costo unitario, de\n'
        '    mayor a menor."""\n'
        '    con = _conectar(config)\n'
        '    cur = con.cursor()\n'
        '\n'
        '    cur.execute("""\n'
        '        SELECT DISTINCT d.ARTICULO_ID\n'
        '        FROM DOCTOS_PV_DET d\n'
        '        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n'
        '        WHERE p.ESTATUS = \'S\'\n'
        '    """)\n'
        '    vendidos_alguna_vez = {fila[0] for fila in cur.fetchall()}\n'
        '\n'
        '    cur.execute("""\n'
        '        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA), SUM(cc.VALOR_TOTAL)\n'
        '        FROM CAPAS_COSTOS cc\n'
        '        WHERE cc.CAPA_AGOTADA = \'N\'\n'
        '        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID\n'
        '    """)\n'
        '    filas_articulos = [\n'
        '        (almacen_id, articulo_id, existencia, valor)\n'
        '        for almacen_id, articulo_id, existencia, valor in cur.fetchall()\n'
        '        if articulo_id not in vendidos_alguna_vez\n'
        '    ]\n'
        '\n'
        '    cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")\n'
        '    nombres_almacen = {aid: (nombre or "Sin nombre").strip() for aid, nombre in cur.fetchall()}\n'
        '\n'
        '    articulo_ids = sorted({fila[1] for fila in filas_articulos})\n'
        '    nombres, claves = {}, {}\n'
        '    LOTE = 400\n'
        '    for i in range(0, len(articulo_ids), LOTE):\n'
        '        lote = articulo_ids[i:i + LOTE]\n'
        '        placeholders = ",".join("?" for _ in lote)\n'
        '        cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n'
        '        for aid, nombre in cur.fetchall():\n'
        '            nombres[aid] = (nombre or "").strip()\n'
        '        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n'
        '        for aid, clave in cur.fetchall():\n'
        '            if aid not in claves and clave:\n'
        '                claves[aid] = clave\n'
        '\n'
        '    con.close()\n'
        '\n'
        '    por_almacen = {}\n'
        '    for almacen_id, articulo_id, existencia, valor in filas_articulos:\n'
        '        existencia = float(existencia or 0)\n'
        '        valor = float(valor or 0)\n'
        '        if existencia <= 0:\n'
        '            continue\n'
        '        entrada = por_almacen.setdefault(almacen_id, {\n'
        '            "almacen_id": almacen_id,\n'
        '            "sucursal": nombres_almacen.get(almacen_id, "Sin nombre"),\n'
        '            "valor_total": 0.0,\n'
        '            "cantidad_articulos": 0,\n'
        '            "articulos": [],\n'
        '        })\n'
        '        entrada["valor_total"] += valor\n'
        '        entrada["cantidad_articulos"] += 1\n'
        '        entrada["articulos"].append({\n'
        '            "articulo_id": articulo_id,\n'
        '            "nombre": nombres.get(articulo_id, "(sin nombre)"),\n'
        '            "clave": claves.get(articulo_id),\n'
        '            "cantidad": existencia,\n'
        '            "costo_unitario": valor / existencia if existencia else 0,\n'
        '            "valor_total": valor,\n'
        '        })\n'
        '\n'
        '    for datos in por_almacen.values():\n'
        '        datos["articulos"].sort(key=lambda a: -a["costo_unitario"])\n'
        '\n'
        '    resultado = sorted(por_almacen.values(), key=lambda d: -d["valor_total"])\n'
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        '# =============================================================================\n'
        '# DASHBOARD: descuentos otorgados en Punto de Venta — usa DOCTOS_PV_DET\n',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py — nuevo endpoint, insertado justo después del de
# valor-inventario.
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    [
        '@app.get("/api/dashboard/valor-inventario")\n'
        'def api_dashboard_valor_inventario(usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Valor del inventario (a costo de compra) por sucursal, y los 50\n'
        '    artículos que más valor representan en cada una."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_valor_inventario_por_almacen(config)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario): {e}")\n'
        '    return resultado\n',

        '@app.get("/api/dashboard/valor-inventario")\n'
        'def api_dashboard_valor_inventario(usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Valor del inventario (a costo de compra) por sucursal, y los 50\n'
        '    artículos que más valor representan en cada una."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_valor_inventario_por_almacen(config)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario): {e}")\n'
        '    return resultado\n'
        '\n'
        '\n'
        '@app.get("/api/dashboard/sin-movimiento")\n'
        'def api_dashboard_sin_movimiento(usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Artículos que nunca se han vendido por Punto de Venta (en ninguna\n'
        '    sucursal, en todo el historial), con existencia > 0, por almacén."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_articulos_sin_movimiento_por_almacen(config)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (sin movimiento): {e}")\n'
        '    return resultado\n',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # 1) Cargar el resumen junto con el de valor de inventario.
    [
        '    let resumenValorInventario = null;\n'
        '    if (puedeVerFlotilla) {\n'
        '      try {\n'
        "        resumenValorInventario = await api('/api/dashboard/valor-inventario');\n"
        '      } catch (e) {\n'
        '        resumenValorInventario = null;\n'
        '      }\n'
        '    }\n',

        '    let resumenValorInventario = null;\n'
        '    if (puedeVerFlotilla) {\n'
        '      try {\n'
        "        resumenValorInventario = await api('/api/dashboard/valor-inventario');\n"
        '      } catch (e) {\n'
        '        resumenValorInventario = null;\n'
        '      }\n'
        '    }\n'
        '    let resumenSinMovimiento = null;\n'
        '    if (puedeVerFlotilla) {\n'
        '      try {\n'
        "        resumenSinMovimiento = await api('/api/dashboard/sin-movimiento');\n"
        '      } catch (e) {\n'
        '        resumenSinMovimiento = null;\n'
        '      }\n'
        '    }\n',
    ],
    # 2) Tarjeta en el Dashboard, justo después de la de Valor del inventario.
    [
        '        ${puedeVerFlotilla && resumenValorInventario ? `\n'
        '          <div class="dash-tarjeta">\n'
        '            <div class="dash-tarjeta-header">\n'
        '              <span class="dash-icono">📦</span>\n'
        '              <div>\n'
        '                <div class="dash-titulo">Valor del inventario</div>\n'
        '                <div class="dash-total">$${resumenValorInventario.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div style="margin-top:10px;">\n'
        '              ${resumenValorInventario.por_sucursal.length ? resumenValorInventario.por_sucursal.map(s => `\n'
        '                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
        '                  <span>${escapeHtml(s.sucursal)}</span>\n'
        '                  <span style="color:var(--text);">$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
        '                </div>\n'
        '              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con capas de costo activas.</p>`}\n'
        '            </div>\n'
        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n',

        '        ${puedeVerFlotilla && resumenValorInventario ? `\n'
        '          <div class="dash-tarjeta">\n'
        '            <div class="dash-tarjeta-header">\n'
        '              <span class="dash-icono">📦</span>\n'
        '              <div>\n'
        '                <div class="dash-titulo">Valor del inventario</div>\n'
        '                <div class="dash-total">$${resumenValorInventario.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div style="margin-top:10px;">\n'
        '              ${resumenValorInventario.por_sucursal.length ? resumenValorInventario.por_sucursal.map(s => `\n'
        '                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
        '                  <span>${escapeHtml(s.sucursal)}</span>\n'
        '                  <span style="color:var(--text);">$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
        '                </div>\n'
        '              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con capas de costo activas.</p>`}\n'
        '            </div>\n'
        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n'
        '        ${puedeVerFlotilla && resumenSinMovimiento ? `\n'
        '          <div class="dash-tarjeta">\n'
        '            <div class="dash-tarjeta-header">\n'
        '              <span class="dash-icono">🐌</span>\n'
        '              <div>\n'
        '                <div class="dash-titulo">Artículos sin movimiento</div>\n'
        '                <div class="dash-total">$${resumenSinMovimiento.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div style="margin-top:10px;">\n'
        '              ${resumenSinMovimiento.por_sucursal.length ? resumenSinMovimiento.por_sucursal.map(s => `\n'
        '                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
        '                  <span>${escapeHtml(s.sucursal)}</span>\n'
        '                  <span style="color:var(--text);">$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
        '                </div>\n'
        '              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin artículos detectados sin movimiento.</p>`}\n'
        '            </div>\n'
        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseSinMovimientoDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n',
    ],
    # 3) Modal + funciones, reutilizando el mismo patrón que Valor del inventario
    #    (mismas variables/funciones pero con paginación de 50 y sin límite de
    #    artículos).
    [
        'function cambiarPaginaInventario(delta) {\n'
        '  INVENTARIO_PAGINA += delta;\n'
        '  renderTopArticulosInventario();\n'
        '}\n',

        'function cambiarPaginaInventario(delta) {\n'
        '  INVENTARIO_PAGINA += delta;\n'
        '  renderTopArticulosInventario();\n'
        '}\n'
        '\n'
        'let SIN_MOVIMIENTO_ALMACEN_SELECCIONADO = null;\n'
        'let SIN_MOVIMIENTO_PAGINA = 0; // 0-indexado, de 50 en 50\n'
        'let SIN_MOVIMIENTO_DATOS_ACTUALES = null;\n'
        '\n'
        'function abrirDesgloseSinMovimientoDashboard() {\n'
        "  document.getElementById('modalContent').innerHTML = `\n"
        '    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n'
        '    <h2>🐌 Artículos sin movimiento por sucursal</h2>\n'
        '    <p style="font-size:12px; color:var(--muted); margin-top:-8px;">Nunca se han vendido por Punto de Venta, en ninguna sucursal, en todo el historial.</p>\n'
        '    <div id="dashSinMovimientoContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n'
        '  `;\n'
        "  abrirModal('admin');\n"
        '  renderSinMovimientoDashboard();\n'
        '}\n'
        '\n'
        'async function renderSinMovimientoDashboard() {\n'
        "  const cont = document.getElementById('dashSinMovimientoContenido');\n"
        '  if (!cont) return;\n'
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
        '  try {\n'
        "    const d = await api('/api/dashboard/sin-movimiento');\n"
        '    if (!d.por_sucursal.length) {\n'
        '      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">No se detectaron artículos sin movimiento.</p>\';\n'
        '      return;\n'
        '    }\n'
        '    if (SIN_MOVIMIENTO_ALMACEN_SELECCIONADO === null || !d.por_sucursal.some(s => s.almacen_id === SIN_MOVIMIENTO_ALMACEN_SELECCIONADO)) {\n'
        '      SIN_MOVIMIENTO_ALMACEN_SELECCIONADO = d.por_sucursal[0].almacen_id;\n'
        '      SIN_MOVIMIENTO_PAGINA = 0;\n'
        '    }\n'
        '    SIN_MOVIMIENTO_DATOS_ACTUALES = d;\n'
        '    cont.innerHTML = `\n'
        '      <div style="overflow-x:auto; margin-bottom:20px;">\n'
        '        <table class="users">\n'
        '          <thead><tr><th>Sucursal</th><th>Artículos sin movimiento</th><th>Valor en inventario</th></tr></thead>\n'
        '          <tbody>\n'
        '            ${d.por_sucursal.map(s => `\n'
        '              <tr>\n'
        '                <td>${escapeHtml(s.sucursal)}</td>\n'
        "                <td>${s.cantidad_articulos.toLocaleString('es-MX')}</td>\n"
        "                <td>$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        '              </tr>\n'
        "            `).join('')}\n"
        '          </tbody>\n'
        "          <tfoot><tr><td><b>Total general</b></td><td></td><td><b>$${d.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n"
        '        </table>\n'
        '      </div>\n'
        '\n'
        '      <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;" id="dashSinMovimientoSucursalBotones">\n'
        '        ${d.por_sucursal.map(s => `\n'
        '          <button class="secondary" style="padding:5px 12px; font-size:12px; ${s.almacen_id === SIN_MOVIMIENTO_ALMACEN_SELECCIONADO ? \'background:var(--copper); color:#fff;\' : \'\'}" onclick="cambiarAlmacenSinMovimiento(${s.almacen_id})">${escapeHtml(s.sucursal)}</button>\n'
        "        `).join('')}\n"
        '      </div>\n'
        '      <div id="dashSinMovimientoArticulos"></div>\n'
        '    `;\n'
        '    renderArticulosSinMovimiento();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}\n'
        '\n'
        'function cambiarAlmacenSinMovimiento(almacenId) {\n'
        '  SIN_MOVIMIENTO_ALMACEN_SELECCIONADO = almacenId;\n'
        '  SIN_MOVIMIENTO_PAGINA = 0;\n'
        "  const botones = document.getElementById('dashSinMovimientoSucursalBotones');\n"
        '  if (botones) {\n'
        '    [...botones.children].forEach(btn => {\n'
        '      const esEste = btn.getAttribute(\'onclick\') === `cambiarAlmacenSinMovimiento(${almacenId})`;\n'
        "      btn.style.background = esEste ? 'var(--copper)' : '';\n"
        "      btn.style.color = esEste ? '#fff' : '';\n"
        '    });\n'
        '  }\n'
        '  renderArticulosSinMovimiento();\n'
        '}\n'
        '\n'
        'function renderArticulosSinMovimiento() {\n'
        "  const cont = document.getElementById('dashSinMovimientoArticulos');\n"
        '  if (!cont || !SIN_MOVIMIENTO_DATOS_ACTUALES) return;\n'
        '  const sucursal = SIN_MOVIMIENTO_DATOS_ACTUALES.por_sucursal.find(s => s.almacen_id === SIN_MOVIMIENTO_ALMACEN_SELECCIONADO);\n'
        '  const articulos = sucursal ? sucursal.articulos : [];\n'
        '  const porPagina = 50;\n'
        '  const totalPaginas = Math.max(1, Math.ceil(articulos.length / porPagina));\n'
        '  if (SIN_MOVIMIENTO_PAGINA >= totalPaginas) SIN_MOVIMIENTO_PAGINA = totalPaginas - 1;\n'
        '  const inicio = SIN_MOVIMIENTO_PAGINA * porPagina;\n'
        '  const pagina = articulos.slice(inicio, inicio + porPagina);\n'
        '  cont.innerHTML = `\n'
        '    <div style="overflow-x:auto;">\n'
        '      <table class="users">\n'
        '        <thead><tr><th>#</th><th>Artículo</th><th>Clave</th><th>Cantidad</th><th>Costo unit.</th><th>Valor en inventario</th></tr></thead>\n'
        '        <tbody>\n'
        '          ${pagina.length ? pagina.map((a, i) => `\n'
        '            <tr>\n'
        '              <td>${inicio + i + 1}</td>\n'
        '              <td>${escapeHtml(a.nombre)}</td>\n'
        "              <td>${escapeHtml(a.clave || '—')}</td>\n"
        "              <td>${a.cantidad.toLocaleString('es-MX')}</td>\n"
        "              <td>$${a.costo_unitario.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        "              <td>$${a.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        '            </tr>\n'
        "          `).join('') : `<tr><td colspan=\"6\" class=\"empty-col\">— sin artículos sin movimiento en esta sucursal —</td></tr>`}\n"
        '        </tbody>\n'
        '      </table>\n'
        '    </div>\n'
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">\n'
        '      <button class="secondary" style="padding:5px 14px;" ${SIN_MOVIMIENTO_PAGINA === 0 ? \'disabled\' : \'\'} onclick="cambiarPaginaSinMovimiento(-1)">← Anteriores 50</button>\n'
        '      <span style="font-size:12px; color:var(--muted);">Página ${SIN_MOVIMIENTO_PAGINA + 1} de ${totalPaginas} (${articulos.length} artículo(s) en total)</span>\n'
        '      <button class="secondary" style="padding:5px 14px;" ${SIN_MOVIMIENTO_PAGINA >= totalPaginas - 1 ? \'disabled\' : \'\'} onclick="cambiarPaginaSinMovimiento(1)">Siguientes 50 →</button>\n'
        '    </div>\n'
        '  `;\n'
        '}\n'
        '\n'
        'function cambiarPaginaSinMovimiento(delta) {\n'
        '  SIN_MOVIMIENTO_PAGINA += delta;\n'
        '  renderArticulosSinMovimiento();\n'
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
                print(f"[{ruta}] No se encontró el bloque esperado para uno de los cambios. El archivo pudo haber cambiado desde la última vez.")
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
    print("   git add backend/microsip.py backend/app.py frontend/index.html")
    print("   git commit -m \"Dashboard: artículos sin movimiento por sucursal\"")
    print("   git push")


if __name__ == "__main__":
    main()
