# -*- coding: utf-8 -*-
"""
Dashboard: nueva tarjeta "Valor del inventario" (a costo de compra) por
sucursal, con desglose completo mostrando el top 50 de articulos con mas
valor por sucursal (boton por sucursal + paginacion de 10 en 10).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_valor_inventario.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['    resultado = microsip.obtener_bitacora_ventas_pv(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = etiqueta\n    return resultado', '    resultado = microsip.obtener_bitacora_ventas_pv(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = etiqueta\n    return resultado\n\n\n@app.get("/api/dashboard/valor-inventario")\ndef api_dashboard_valor_inventario(usuario: dict = Depends(requiere_dashboard)):\n    """Valor del inventario (a costo de compra) por sucursal, y los 50\n    artículos que más valor representan en cada una."""\n    config = _config_microsip_o_error(usuario)\n    try:\n        resultado = microsip.obtener_valor_inventario_por_almacen(config)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario): {e}")\n    return resultado']], 'frontend/index.html': [['    let resumenVentasPv = null;\n    if (puedeVerFlotilla) {\n      try {\n        resumenVentasPv = await api(`/api/dashboard/ventas-pv?fecha=${new Date().toISOString().slice(0, 10)}`);\n      } catch (e) {\n        resumenVentasPv = null; // si Microsip no está configurado o falla, simplemente no se muestra la tarjeta\n      }\n    }', "    let resumenVentasPv = null;\n    if (puedeVerFlotilla) {\n      try {\n        resumenVentasPv = await api(`/api/dashboard/ventas-pv?fecha=${new Date().toISOString().slice(0, 10)}`);\n      } catch (e) {\n        resumenVentasPv = null; // si Microsip no está configurado o falla, simplemente no se muestra la tarjeta\n      }\n    }\n    let resumenValorInventario = null;\n    if (puedeVerFlotilla) {\n      try {\n        resumenValorInventario = await api('/api/dashboard/valor-inventario');\n      } catch (e) {\n        resumenValorInventario = null;\n      }\n    }"], ['${puedeVerFlotilla && resumenVentasPv ? `\n          <div class="dash-tarjeta">\n            <div id="dashResumenVentasPvCard">${contenidoTarjetaResumenVentasPv(resumenVentasPv)}</div>\n            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>\n          </div>\n        ` : \'\'}\n        ${tarjetaModuloDashboard(\'Recursos Humanos\', \'🩺\', d.rh.total, d.rh.por_estado, \'#E85D9E\', \'/api/dashboard/rh\')}', '${puedeVerFlotilla && resumenVentasPv ? `\n          <div class="dash-tarjeta">\n            <div id="dashResumenVentasPvCard">${contenidoTarjetaResumenVentasPv(resumenVentasPv)}</div>\n            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>\n          </div>\n        ` : \'\'}\n        ${puedeVerFlotilla && resumenValorInventario ? `\n          <div class="dash-tarjeta">\n            <div class="dash-tarjeta-header">\n              <span class="dash-icono">📦</span>\n              <div>\n                <div class="dash-titulo">Valor del inventario</div>\n                <div class="dash-total">$${resumenValorInventario.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n              </div>\n            </div>\n            <div style="margin-top:10px;">\n              ${resumenValorInventario.por_sucursal.length ? resumenValorInventario.por_sucursal.map(s => `\n                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n                  <span>${escapeHtml(s.sucursal)}</span>\n                  <span style="color:var(--text);">$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n                </div>\n              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con capas de costo activas.</p>`}\n            </div>\n            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioDashboard()">🔎 Ver desglose completo</button>\n          </div>\n        ` : \'\'}\n        ${tarjetaModuloDashboard(\'Recursos Humanos\', \'🩺\', d.rh.total, d.rh.por_estado, \'#E85D9E\', \'/api/dashboard/rh\')}'], ['function abrirDesgloseVentasPvDashboard() {', 'let INVENTARIO_ALMACEN_SELECCIONADO = null;\nlet INVENTARIO_PAGINA = 0; // 0-indexado, de 10 en 10\nlet INVENTARIO_DATOS_ACTUALES = null;\n\nfunction abrirDesgloseInventarioDashboard() {\n  document.getElementById(\'modalContent\').innerHTML = `\n    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n    <h2>📦 Valor del inventario por sucursal</h2>\n    <div id="dashInventarioContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n  `;\n  abrirModal(\'admin\');\n  renderInventarioDashboard();\n}\n\nasync function renderInventarioDashboard() {\n  const cont = document.getElementById(\'dashInventarioContenido\');\n  if (!cont) return;\n  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n  try {\n    const d = await api(\'/api/dashboard/valor-inventario\');\n    if (!d.por_sucursal.length) {\n      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">No hay inventario con capas de costo activas.</p>\';\n      return;\n    }\n    if (INVENTARIO_ALMACEN_SELECCIONADO === null || !d.por_sucursal.some(s => s.almacen_id === INVENTARIO_ALMACEN_SELECCIONADO)) {\n      INVENTARIO_ALMACEN_SELECCIONADO = d.por_sucursal[0].almacen_id;\n      INVENTARIO_PAGINA = 0;\n    }\n    INVENTARIO_DATOS_ACTUALES = d;\n    cont.innerHTML = `\n      <div style="overflow-x:auto; margin-bottom:20px;">\n        <table class="users">\n          <thead><tr><th>Sucursal</th><th>Unidades</th><th>Valor en inventario</th></tr></thead>\n          <tbody>\n            ${d.por_sucursal.map(s => `\n              <tr>\n                <td>${escapeHtml(s.sucursal)}</td>\n                <td>${s.unidades_totales.toLocaleString(\'es-MX\')}</td>\n                <td>$${s.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n              </tr>\n            `).join(\'\')}\n          </tbody>\n          <tfoot><tr><td><b>Total general</b></td><td></td><td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n        </table>\n      </div>\n\n      <h3 style="margin:0 0 8px; font-size:15px;">🏆 Top 50 artículos con más valor en inventario</h3>\n      <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;" id="dashInventarioSucursalBotones">\n        ${d.por_sucursal.map(s => `\n          <button class="secondary" style="padding:5px 12px; font-size:12px; ${s.almacen_id === INVENTARIO_ALMACEN_SELECCIONADO ? \'background:var(--copper); color:#fff;\' : \'\'}" onclick="cambiarSucursalInventario(${s.almacen_id})">${escapeHtml(s.sucursal)}</button>\n        `).join(\'\')}\n      </div>\n      <div id="dashInventarioTopArticulos"></div>\n    `;\n    renderTopArticulosInventario();\n  } catch (e) {\n    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n  }\n}\n\nfunction cambiarSucursalInventario(almacenId) {\n  INVENTARIO_ALMACEN_SELECCIONADO = almacenId;\n  INVENTARIO_PAGINA = 0;\n  const botones = document.getElementById(\'dashInventarioSucursalBotones\');\n  if (botones) {\n    [...botones.children].forEach(btn => {\n      const esEste = btn.getAttribute(\'onclick\') === `cambiarSucursalInventario(${almacenId})`;\n      btn.style.background = esEste ? \'var(--copper)\' : \'\';\n      btn.style.color = esEste ? \'#fff\' : \'\';\n    });\n  }\n  renderTopArticulosInventario();\n}\n\nfunction renderTopArticulosInventario() {\n  const cont = document.getElementById(\'dashInventarioTopArticulos\');\n  if (!cont || !INVENTARIO_DATOS_ACTUALES) return;\n  const sucursal = INVENTARIO_DATOS_ACTUALES.por_sucursal.find(s => s.almacen_id === INVENTARIO_ALMACEN_SELECCIONADO);\n  const articulos = sucursal ? sucursal.top_articulos : [];\n  const porPagina = 10;\n  const totalPaginas = Math.max(1, Math.ceil(articulos.length / porPagina));\n  if (INVENTARIO_PAGINA >= totalPaginas) INVENTARIO_PAGINA = totalPaginas - 1;\n  const inicio = INVENTARIO_PAGINA * porPagina;\n  const pagina = articulos.slice(inicio, inicio + porPagina);\n  cont.innerHTML = `\n    <div style="overflow-x:auto;">\n      <table class="users">\n        <thead><tr><th>#</th><th>Artículo</th><th>Clave</th><th>Cantidad</th><th>Costo unit.</th><th>Valor en inventario</th></tr></thead>\n        <tbody>\n          ${pagina.length ? pagina.map((a, i) => `\n            <tr>\n              <td>${inicio + i + 1}</td>\n              <td>${escapeHtml(a.nombre)}</td>\n              <td>${escapeHtml(a.clave || \'—\')}</td>\n              <td>${a.cantidad.toLocaleString(\'es-MX\')}</td>\n              <td>$${a.costo_unitario.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n              <td>$${a.valor_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n            </tr>\n          `).join(\'\') : `<tr><td colspan="6" class="empty-col">— sin artículos con inventario en esta sucursal —</td></tr>`}\n        </tbody>\n      </table>\n    </div>\n    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">\n      <button class="secondary" style="padding:5px 14px;" ${INVENTARIO_PAGINA === 0 ? \'disabled\' : \'\'} onclick="cambiarPaginaInventario(-1)">← Anteriores 10</button>\n      <span style="font-size:12px; color:var(--muted);">Página ${INVENTARIO_PAGINA + 1} de ${totalPaginas} (${articulos.length} artículo(s) en total)</span>\n      <button class="secondary" style="padding:5px 14px;" ${INVENTARIO_PAGINA >= totalPaginas - 1 ? \'disabled\' : \'\'} onclick="cambiarPaginaInventario(1)">Siguientes 10 →</button>\n    </div>\n  `;\n}\n\nfunction cambiarPaginaInventario(delta) {\n  INVENTARIO_PAGINA += delta;\n  renderTopArticulosInventario();\n}\n\nfunction abrirDesgloseVentasPvDashboard() {']]}

MICROSIP_APPEND = '\n\n# =============================================================================\n# DASHBOARD: valor del inventario por sucursal (almacén) — usa la misma\n# lógica de capas de costo (CAPAS_COSTOS) ya probada en el Checador de\n# precio, pero agregada por almacén completo en vez de artículo por\n# artículo. VALOR_TOTAL de una capa no agotada es literalmente el dinero\n# que sigue invertido en esas piezas — sumarlo da el valor real del\n# inventario a costo de compra.\n# =============================================================================\n\ndef obtener_valor_inventario_por_almacen(config: dict):\n    """Valor total del inventario (a costo de compra) por sucursal/almacén,\n    y los 50 artículos que más valor representan en cada uno."""\n    con = _conectar(config)\n    cur = con.cursor()\n\n    cur.execute("""\n        SELECT cc.ALMACEN_ID, COALESCE(a.NOMBRE, \'Sin nombre\'), SUM(cc.VALOR_TOTAL), SUM(cc.EXISTENCIA)\n        FROM CAPAS_COSTOS cc\n        LEFT JOIN ALMACENES a ON a.ALMACEN_ID = cc.ALMACEN_ID\n        WHERE cc.CAPA_AGOTADA = \'N\'\n        GROUP BY cc.ALMACEN_ID, a.NOMBRE\n    """)\n    totales = {}\n    for almacen_id, nombre, valor, existencia in cur.fetchall():\n        totales[almacen_id] = {\n            "almacen_id": almacen_id,\n            "sucursal": (nombre or "Sin nombre").strip(),\n            "valor_total": float(valor or 0),\n            "unidades_totales": float(existencia or 0),\n        }\n\n    cur.execute("""\n        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA), SUM(cc.VALOR_TOTAL)\n        FROM CAPAS_COSTOS cc\n        WHERE cc.CAPA_AGOTADA = \'N\'\n        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID\n    """)\n    filas_articulos = cur.fetchall()\n\n    articulo_ids = sorted({r[1] for r in filas_articulos})\n    nombres, claves = {}, {}\n    LOTE = 400\n    for i in range(0, len(articulo_ids), LOTE):\n        lote = articulo_ids[i:i + LOTE]\n        placeholders = ",".join("?" for _ in lote)\n        cur.execute(f"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n        for aid, nombre in cur.fetchall():\n            nombres[aid] = (nombre or "").strip()\n        cur.execute(f"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n        for aid, clave in cur.fetchall():\n            if aid not in claves and clave:\n                claves[aid] = clave\n\n    por_almacen_articulos = {}\n    for almacen_id, articulo_id, existencia, valor in filas_articulos:\n        existencia = float(existencia or 0)\n        valor = float(valor or 0)\n        if existencia <= 0:\n            continue\n        por_almacen_articulos.setdefault(almacen_id, []).append({\n            "articulo_id": articulo_id,\n            "nombre": nombres.get(articulo_id, "(sin nombre)"),\n            "clave": claves.get(articulo_id),\n            "cantidad": existencia,\n            "costo_unitario": valor / existencia if existencia else 0,\n            "valor_total": valor,\n        })\n\n    con.close()\n\n    for almacen_id in por_almacen_articulos:\n        por_almacen_articulos[almacen_id].sort(key=lambda a: -a["valor_total"])\n        por_almacen_articulos[almacen_id] = por_almacen_articulos[almacen_id][:50]\n\n    resultado = []\n    for almacen_id, datos in sorted(totales.items(), key=lambda kv: -kv[1]["valor_total"]):\n        datos = dict(datos)\n        datos["top_articulos"] = por_almacen_articulos.get(almacen_id, [])\n        resultado.append(datos)\n\n    total_general = sum(d["valor_total"] for d in resultado)\n    return {"por_sucursal": resultado, "total_general": total_general}\n'


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    reemplazos = ARCHIVOS[ruta]
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in reemplazos:
        if nuevo in contenido:
            continue
        if viejo not in contenido:
            print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
            hubo_error = True
            continue
        contenido = contenido.replace(viejo, nuevo, 1)
        cambios += 1
    escribir(ruta, contenido)
    print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")
    return not hubo_error


def aplicar_microsip():
    ruta = "backend/microsip.py"
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    if MICROSIP_APPEND.strip() in contenido:
        print(f"[{ruta}] Ya estaba aplicado. No hace falta nada.")
        return True
    contenido = contenido + MICROSIP_APPEND
    escribir(ruta, contenido)
    print(f"[{ruta}] Funcion agregada al final del archivo.")
    return True


def main():
    ok = True
    ok = aplicar_microsip() and ok
    ok = aplicar_reemplazos("backend/app.py") and ok
    ok = aplicar_reemplazos("frontend/index.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py backend/microsip.py frontend/index.html")
    print('   git commit -m "Dashboard: valor del inventario por sucursal + top 50 articulos"')
    print("   git push")


if __name__ == "__main__":
    main()
