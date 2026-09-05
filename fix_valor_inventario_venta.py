# -*- coding: utf-8 -*-
"""
Nueva tarjeta de Dashboard: "Valor del inventario (precio de venta)" —
misma estructura que "Valor del inventario" ya existente (CAPAS_COSTOS por
ALMACEN_ID, top 50 por sucursal), pero valuando cada artículo a su PRECIO
DE VENTA (PRECIOS_ARTICULOS x 1.16 IVA — el mismo precio de lista que ya
usa el Checador de precio) en vez de a costo de compra. La tarjeta de
costo que ya existe NO se toca, esta es una tarjeta adicional aparte.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_valor_inventario_venta.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/microsip.py — nueva función, insertada justo después de
# obtener_articulos_sin_movimiento_por_almacen.
# ---------------------------------------------------------------------------
ARCHIVOS['backend/microsip.py'] = [
    [
        'resultado = sorted(por_almacen.values(), key=lambda d: -d["valor_total"])\n'
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        '# =============================================================================\n'
        '# DASHBOARD: descuentos otorgados',

        'resultado = sorted(por_almacen.values(), key=lambda d: -d["valor_total"])\n'
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        'def obtener_valor_inventario_precio_venta_por_almacen(config: dict):\n'
        '    """Igual que obtener_valor_inventario_por_almacen, pero valuando cada\n'
        '    artículo a su PRECIO DE VENTA (PRECIOS_ARTICULOS x 1.16 IVA — mismo\n'
        '    precio de lista que usa el Checador de precio) en vez del costo de\n'
        '    compra. Sirve para saber cuánto valdría el inventario si se vendiera\n'
        '    todo a precio de lista."""\n'
        '    con = _conectar(config)\n'
        '    cur = con.cursor()\n'
        '\n'
        '    cur.execute("""\n'
        '        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA)\n'
        '        FROM CAPAS_COSTOS cc\n'
        '        WHERE cc.CAPA_AGOTADA = \'N\'\n'
        '        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID\n'
        '    """)\n'
        '    filas_existencia = cur.fetchall()\n'
        '\n'
        '    cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")\n'
        '    nombres_almacen = {aid: (nombre or "Sin nombre").strip() for aid, nombre in cur.fetchall()}\n'
        '\n'
        '    articulo_ids = sorted({fila[1] for fila in filas_existencia})\n'
        '    nombres, claves, precios = {}, {}, {}\n'
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
        '        # Precio de lista: PRECIOS_ARTICULOS guarda el precio SIN\n'
        '        # impuesto, igual que en el Checador de precio se le agrega 16% de\n'
        '        # IVA. Si un artículo tuviera más de un precio capturado, se usa\n'
        '        # el primero que aparezca (mismo criterio de "FIRST 1" que usa el\n'
        '        # Checador).\n'
        '        cur.execute(f"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n'
        '        for aid, precio in cur.fetchall():\n'
        '            if aid not in precios and precio is not None:\n'
        '                precios[aid] = round(float(precio) * 1.16, 2)\n'
        '\n'
        '    con.close()\n'
        '\n'
        '    por_almacen_totales = {}\n'
        '    por_almacen_articulos = {}\n'
        '    for almacen_id, articulo_id, existencia in filas_existencia:\n'
        '        existencia = float(existencia or 0)\n'
        '        if existencia <= 0:\n'
        '            continue\n'
        '        precio_unitario = precios.get(articulo_id)\n'
        '        if precio_unitario is None:\n'
        '            continue  # sin precio de lista capturado en Microsip, no se puede valuar\n'
        '        valor_total = precio_unitario * existencia\n'
        '\n'
        '        totales = por_almacen_totales.setdefault(almacen_id, {\n'
        '            "almacen_id": almacen_id,\n'
        '            "sucursal": nombres_almacen.get(almacen_id, "Sin nombre"),\n'
        '            "valor_total": 0.0,\n'
        '            "unidades_totales": 0.0,\n'
        '        })\n'
        '        totales["valor_total"] += valor_total\n'
        '        totales["unidades_totales"] += existencia\n'
        '\n'
        '        por_almacen_articulos.setdefault(almacen_id, []).append({\n'
        '            "articulo_id": articulo_id,\n'
        '            "nombre": nombres.get(articulo_id, "(sin nombre)"),\n'
        '            "clave": claves.get(articulo_id),\n'
        '            "cantidad": existencia,\n'
        '            "precio_unitario": precio_unitario,\n'
        '            "valor_total": valor_total,\n'
        '        })\n'
        '\n'
        '    for almacen_id in por_almacen_articulos:\n'
        '        por_almacen_articulos[almacen_id].sort(key=lambda a: -a["valor_total"])\n'
        '        por_almacen_articulos[almacen_id] = por_almacen_articulos[almacen_id][:50]\n'
        '\n'
        '    resultado = []\n'
        '    for almacen_id, datos in sorted(por_almacen_totales.items(), key=lambda kv: -kv[1]["valor_total"]):\n'
        '        datos = dict(datos)\n'
        '        datos["top_articulos"] = por_almacen_articulos.get(almacen_id, [])\n'
        '        resultado.append(datos)\n'
        '\n'
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n'
        '\n'
        '\n'
        '# =============================================================================\n'
        '# DASHBOARD: descuentos otorgados',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py — nuevo endpoint, insertado justo después del de
# sin-movimiento.
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    [
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

        '@app.get("/api/dashboard/sin-movimiento")\n'
        'def api_dashboard_sin_movimiento(usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Artículos que nunca se han vendido por Punto de Venta (en ninguna\n'
        '    sucursal, en todo el historial), con existencia > 0, por almacén."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_articulos_sin_movimiento_por_almacen(config)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (sin movimiento): {e}")\n'
        '    return resultado\n'
        '\n'
        '\n'
        '@app.get("/api/dashboard/valor-inventario-venta")\n'
        'def api_dashboard_valor_inventario_venta(usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Valor del inventario a PRECIO DE VENTA (lista, no costo) por\n'
        '    sucursal, y los 50 artículos que más valor representan en cada una."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_valor_inventario_precio_venta_por_almacen(config)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario a precio de venta): {e}")\n'
        '    return resultado\n',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # 1) Cargar el resumen junto con el de sin-movimiento.
    [
        "        resumenSinMovimiento = await api('/api/dashboard/sin-movimiento');\n"
        '      } catch (e) {\n'
        '        resumenSinMovimiento = null;\n'
        '      }\n'
        '    }\n',

        "        resumenSinMovimiento = await api('/api/dashboard/sin-movimiento');\n"
        '      } catch (e) {\n'
        '        resumenSinMovimiento = null;\n'
        '      }\n'
        '    }\n'
        '    let resumenValorInventarioVenta = null;\n'
        '    if (puedeVerFlotilla) {\n'
        '      try {\n'
        "        resumenValorInventarioVenta = await api('/api/dashboard/valor-inventario-venta');\n"
        '      } catch (e) {\n'
        '        resumenValorInventarioVenta = null;\n'
        '      }\n'
        '    }\n',
    ],
    # 2) Tarjeta en el Dashboard, justo después de la de "Artículos sin
    #    movimiento" (que a su vez está después de "Valor del inventario").
    [
        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseSinMovimientoDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n',

        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseSinMovimientoDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n'
        '        ${puedeVerFlotilla && resumenValorInventarioVenta ? `\n'
        '          <div class="dash-tarjeta">\n'
        '            <div class="dash-tarjeta-header">\n'
        '              <span class="dash-icono">💲</span>\n'
        '              <div>\n'
        '                <div class="dash-titulo">Valor del inventario (precio de venta)</div>\n'
        '                <div class="dash-total">$${resumenValorInventarioVenta.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div style="margin-top:10px;">\n'
        '              ${resumenValorInventarioVenta.por_sucursal.length ? resumenValorInventarioVenta.por_sucursal.map(s => `\n'
        '                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
        '                  <span>${escapeHtml(s.sucursal)}</span>\n'
        '                  <span style="color:var(--text);">$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
        '                </div>\n'
        '              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con precio de lista capturado.</p>`}\n'
        '            </div>\n'
        '<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioVentaDashboard()">🔎 Ver desglose completo</button>\n'
        '          </div>\n'
        '        ` : \'\'}\n',
    ],
    # 3) Modal + funciones, mismo patrón que Valor del inventario (top 50,
    #    paginado de 10 en 10).
    [
        'function cambiarPaginaSinMovimiento(delta) {\n'
        '  SIN_MOVIMIENTO_PAGINA += delta;\n'
        '  renderArticulosSinMovimiento();\n'
        '}\n',

        'function cambiarPaginaSinMovimiento(delta) {\n'
        '  SIN_MOVIMIENTO_PAGINA += delta;\n'
        '  renderArticulosSinMovimiento();\n'
        '}\n'
        '\n'
        'let VENTA_INV_ALMACEN_SELECCIONADO = null;\n'
        'let VENTA_INV_PAGINA = 0; // 0-indexado, de 10 en 10\n'
        'let VENTA_INV_DATOS_ACTUALES = null;\n'
        '\n'
        'function abrirDesgloseInventarioVentaDashboard() {\n'
        "  document.getElementById('modalContent').innerHTML = `\n"
        '    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n'
        '    <h2>💲 Valor del inventario a precio de venta, por sucursal</h2>\n'
        '    <div id="dashInventarioVentaContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n'
        '  `;\n'
        "  abrirModal('admin');\n"
        '  renderInventarioVentaDashboard();\n'
        '}\n'
        '\n'
        'async function renderInventarioVentaDashboard() {\n'
        "  const cont = document.getElementById('dashInventarioVentaContenido');\n"
        '  if (!cont) return;\n'
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
        '  try {\n'
        "    const d = await api('/api/dashboard/valor-inventario-venta');\n"
        '    if (!d.por_sucursal.length) {\n'
        '      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">No hay inventario con precio de lista capturado.</p>\';\n'
        '      return;\n'
        '    }\n'
        '    if (VENTA_INV_ALMACEN_SELECCIONADO === null || !d.por_sucursal.some(s => s.almacen_id === VENTA_INV_ALMACEN_SELECCIONADO)) {\n'
        '      VENTA_INV_ALMACEN_SELECCIONADO = d.por_sucursal[0].almacen_id;\n'
        '      VENTA_INV_PAGINA = 0;\n'
        '    }\n'
        '    VENTA_INV_DATOS_ACTUALES = d;\n'
        '    cont.innerHTML = `\n'
        '      <div style="overflow-x:auto; margin-bottom:20px;">\n'
        '        <table class="users">\n'
        '          <thead><tr><th>Sucursal</th><th>Unidades</th><th>Valor a precio de venta</th></tr></thead>\n'
        '          <tbody>\n'
        '            ${d.por_sucursal.map(s => `\n'
        '              <tr>\n'
        '                <td>${escapeHtml(s.sucursal)}</td>\n'
        "                <td>${s.unidades_totales.toLocaleString('es-MX')}</td>\n"
        "                <td>$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        '              </tr>\n'
        "            `).join('')}\n"
        '          </tbody>\n'
        "          <tfoot><tr><td><b>Total general</b></td><td></td><td><b>$${d.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n"
        '        </table>\n'
        '      </div>\n'
        '\n'
        '      <h3 style="margin:0 0 8px; font-size:15px;">🏆 Top 50 artículos con más valor (precio de venta)</h3>\n'
        '      <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;" id="dashInventarioVentaSucursalBotones">\n'
        '        ${d.por_sucursal.map(s => `\n'
        '          <button class="secondary" style="padding:5px 12px; font-size:12px; ${s.almacen_id === VENTA_INV_ALMACEN_SELECCIONADO ? \'background:var(--copper); color:#fff;\' : \'\'}" onclick="cambiarSucursalInventarioVenta(${s.almacen_id})">${escapeHtml(s.sucursal)}</button>\n'
        "        `).join('')}\n"
        '      </div>\n'
        '      <div id="dashInventarioVentaTopArticulos"></div>\n'
        '    `;\n'
        '    renderTopArticulosInventarioVenta();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}\n'
        '\n'
        'function cambiarSucursalInventarioVenta(almacenId) {\n'
        '  VENTA_INV_ALMACEN_SELECCIONADO = almacenId;\n'
        '  VENTA_INV_PAGINA = 0;\n'
        "  const botones = document.getElementById('dashInventarioVentaSucursalBotones');\n"
        '  if (botones) {\n'
        '    [...botones.children].forEach(btn => {\n'
        '      const esEste = btn.getAttribute(\'onclick\') === `cambiarSucursalInventarioVenta(${almacenId})`;\n'
        "      btn.style.background = esEste ? 'var(--copper)' : '';\n"
        "      btn.style.color = esEste ? '#fff' : '';\n"
        '    });\n'
        '  }\n'
        '  renderTopArticulosInventarioVenta();\n'
        '}\n'
        '\n'
        'function renderTopArticulosInventarioVenta() {\n'
        "  const cont = document.getElementById('dashInventarioVentaTopArticulos');\n"
        '  if (!cont || !VENTA_INV_DATOS_ACTUALES) return;\n'
        '  const sucursal = VENTA_INV_DATOS_ACTUALES.por_sucursal.find(s => s.almacen_id === VENTA_INV_ALMACEN_SELECCIONADO);\n'
        '  const articulos = sucursal ? sucursal.top_articulos : [];\n'
        '  const porPagina = 10;\n'
        '  const totalPaginas = Math.max(1, Math.ceil(articulos.length / porPagina));\n'
        '  if (VENTA_INV_PAGINA >= totalPaginas) VENTA_INV_PAGINA = totalPaginas - 1;\n'
        '  const inicio = VENTA_INV_PAGINA * porPagina;\n'
        '  const pagina = articulos.slice(inicio, inicio + porPagina);\n'
        '  cont.innerHTML = `\n'
        '    <div style="overflow-x:auto;">\n'
        '      <table class="users">\n'
        '        <thead><tr><th>#</th><th>Artículo</th><th>Clave</th><th>Cantidad</th><th>Precio venta</th><th>Valor a precio de venta</th></tr></thead>\n'
        '        <tbody>\n'
        '          ${pagina.length ? pagina.map((a, i) => `\n'
        '            <tr>\n'
        '              <td>${inicio + i + 1}</td>\n'
        '              <td>${escapeHtml(a.nombre)}</td>\n'
        "              <td>${escapeHtml(a.clave || '—')}</td>\n"
        "              <td>${a.cantidad.toLocaleString('es-MX')}</td>\n"
        "              <td>$${a.precio_unitario.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        "              <td>$${a.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</td>\n"
        '            </tr>\n'
        "          `).join('') : `<tr><td colspan=\"6\" class=\"empty-col\">— sin artículos con inventario en esta sucursal —</td></tr>`}\n"
        '        </tbody>\n'
        '      </table>\n'
        '    </div>\n'
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">\n'
        '      <button class="secondary" style="padding:5px 14px;" ${VENTA_INV_PAGINA === 0 ? \'disabled\' : \'\'} onclick="cambiarPaginaInventarioVenta(-1)">← Anteriores 10</button>\n'
        '      <span style="font-size:12px; color:var(--muted);">Página ${VENTA_INV_PAGINA + 1} de ${totalPaginas} (${articulos.length} artículo(s) en total)</span>\n'
        '      <button class="secondary" style="padding:5px 14px;" ${VENTA_INV_PAGINA >= totalPaginas - 1 ? \'disabled\' : \'\'} onclick="cambiarPaginaInventarioVenta(1)">Siguientes 10 →</button>\n'
        '    </div>\n'
        '  `;\n'
        '}\n'
        '\n'
        'function cambiarPaginaInventarioVenta(delta) {\n'
        '  VENTA_INV_PAGINA += delta;\n'
        '  renderTopArticulosInventarioVenta();\n'
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
    print("   git commit -m \"Dashboard: valor del inventario a precio de venta\"")
    print("   git push")


if __name__ == "__main__":
    main()
