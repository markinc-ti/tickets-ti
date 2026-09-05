# -*- coding: utf-8 -*-
"""
Agrega al Dashboard:
1. Ventas de HOY del modulo de Punto de Venta (caja) de Microsip, por
   sucursal y desglosadas por forma de cobro (efectivo, tarjeta credito/
   debito, etc.), justo debajo del mapa de flotilla.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_dashboard_ventas.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['@app.get("/api/dashboard")\ndef api_dashboard(usuario: dict = Depends(requiere_dashboard)):\n    return db.estadisticas_dashboard(usuario["empresa_id"])', '@app.get("/api/dashboard")\ndef api_dashboard(usuario: dict = Depends(requiere_dashboard)):\n    return db.estadisticas_dashboard(usuario["empresa_id"])\n\n\n@app.get("/api/dashboard/ventas-pv")\ndef api_dashboard_ventas_pv(fecha: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):\n    """Ventas de HOY (o del día que se pida) del módulo de Punto de Venta de\n    Microsip, por sucursal y desglosadas por forma de cobro."""\n    config = _config_microsip_o_error(usuario)\n    from datetime import date, datetime, timedelta\n    if fecha:\n        try:\n            dia = datetime.strptime(fecha, "%Y-%m-%d").date()\n        except ValueError:\n            raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")\n    else:\n        dia = date.today()\n    fecha_inicio = dia.isoformat()\n    fecha_fin = (dia + timedelta(days=1)).isoformat()\n    try:\n        resultado = microsip.obtener_ventas_pv_por_sucursal(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = fecha_inicio\n    return resultado']], 'frontend/index.html': [['      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <h3 style="margin:0 0 8px;">📍 Flotilla en vivo</h3>\n          <div id="dashFlotillaMsg" style="font-size:12px; color:var(--muted); margin-bottom:8px;">Cargando posiciones…</div>\n          <div id="dashFlotillaMapa" style="width:100%; height:340px; border:1px solid rgba(155,157,159,0.3); border-radius:6px;"></div>\n        </div>\n      ` : \'\'}\n      ${puedeAutorizar ? \'<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>\' : \'\'}\n      <div class="dash-grid">', '      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <h3 style="margin:0 0 8px;">📍 Flotilla en vivo</h3>\n          <div id="dashFlotillaMsg" style="font-size:12px; color:var(--muted); margin-bottom:8px;">Cargando posiciones…</div>\n          <div id="dashFlotillaMapa" style="width:100%; height:340px; border:1px solid rgba(155,157,159,0.3); border-radius:6px;"></div>\n        </div>\n      ` : \'\'}\n      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">\n            <h3 style="margin:0;">💵 Ventas por sucursal (Punto de Venta)</h3>\n            <input id="dashVentasPvFecha" type="date" style="width:auto;" onchange="renderVentasPvDashboard()" />\n          </div>\n          <div id="dashVentasPvContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n        </div>\n      ` : \'\'}\n      ${puedeAutorizar ? \'<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>\' : \'\'}\n      <div class="dash-grid">'], ['if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}\n\nasync function renderMapaFlotillaDashboard() {\n  const msg = document.getElementById(\'dashFlotillaMsg\');\n  if (!msg) return;\n  try {\n    const posiciones = await api(\'/api/entregas/mapa-flotilla\');\n    if (!posiciones.length) {\n      msg.textContent = \'Ningún vehículo con unidad Geotab vinculada tiene posición disponible todavía.\';\n      return;\n    }\n    msg.textContent = `${posiciones.length} vehículo(s) con ubicación en vivo:`;\n    const mapa = L.map(\'dashFlotillaMapa\');\n    L.tileLayer(\'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png\', { attribution: \'© OpenStreetMap\', maxZoom: 19 }).addTo(mapa);\n    const puntos = [];\n    posiciones.forEach(p => {\n      const marcador = L.marker([p.lat, p.lng]).addTo(mapa);\n      marcador.bindPopup(`<b>${escapeHtml(p.nombre)}</b><br>${p.velocidad_kmh != null ? Math.round(p.velocidad_kmh) + \' km/h\' : \'\'}`);\n      puntos.push([p.lat, p.lng]);\n    });\n    mapa.fitBounds(puntos, { padding: [30, 30] });\n  } catch (e) {\n    msg.innerHTML = `<span style="color:var(--copper);">${escapeHtml(e.message)}</span>`;\n  }\n}\n', 'if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n    if (puedeVerFlotilla) {\n      document.getElementById(\'dashVentasPvFecha\').value = new Date().toISOString().slice(0, 10);\n      await renderVentasPvDashboard();\n    }\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}\n\nasync function renderVentasPvDashboard() {\n  const cont = document.getElementById(\'dashVentasPvContenido\');\n  if (!cont) return;\n  const fecha = document.getElementById(\'dashVentasPvFecha\').value;\n  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n  try {\n    const d = await api(`/api/dashboard/ventas-pv?fecha=${fecha}`);\n    if (!d.por_sucursal.length) {\n      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">No hay ventas de Punto de Venta registradas ese día.</p>\';\n      return;\n    }\n    // Unión de todas las formas de cobro que aparecen (para columnas parejas en todas las sucursales)\n    const formasCobro = [...new Set(d.por_sucursal.flatMap(s => Object.keys(s.formas_cobro)))].sort();\n    cont.innerHTML = `\n      <table class="users">\n        <thead><tr><th>Sucursal</th>${formasCobro.map(f => `<th>${escapeHtml(f)}</th>`).join(\'\')}<th>Total</th></tr></thead>\n        <tbody>\n          ${d.por_sucursal.map(s => `\n            <tr>\n              <td>${escapeHtml(s.sucursal)}</td>\n              ${formasCobro.map(f => `<td>${s.formas_cobro[f] != null ? \'$\' + s.formas_cobro[f].toLocaleString(\'es-MX\', {minimumFractionDigits:2}) : \'—\'}</td>`).join(\'\')}\n              <td><b>$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td>\n            </tr>\n          `).join(\'\')}\n        </tbody>\n        <tfoot><tr><td><b>Total general</b></td>${formasCobro.map(() => \'<td></td>\').join(\'\')}<td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n      </table>\n    `;\n  } catch (e) {\n    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n  }\n}\n\nasync function renderMapaFlotillaDashboard() {\n  const msg = document.getElementById(\'dashFlotillaMsg\');\n  if (!msg) return;\n  try {\n    const posiciones = await api(\'/api/entregas/mapa-flotilla\');\n    if (!posiciones.length) {\n      msg.textContent = \'Ningún vehículo con unidad Geotab vinculada tiene posición disponible todavía.\';\n      return;\n    }\n    msg.textContent = `${posiciones.length} vehículo(s) con ubicación en vivo:`;\n    const mapa = L.map(\'dashFlotillaMapa\');\n    L.tileLayer(\'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png\', { attribution: \'© OpenStreetMap\', maxZoom: 19 }).addTo(mapa);\n    const puntos = [];\n    posiciones.forEach(p => {\n      const marcador = L.marker([p.lat, p.lng]).addTo(mapa);\n      marcador.bindPopup(`<b>${escapeHtml(p.nombre)}</b><br>${p.velocidad_kmh != null ? Math.round(p.velocidad_kmh) + \' km/h\' : \'\'}`);\n      puntos.push([p.lat, p.lng]);\n    });\n    mapa.fitBounds(puntos, { padding: [30, 30] });\n  } catch (e) {\n    msg.innerHTML = `<span style="color:var(--copper);">${escapeHtml(e.message)}</span>`;\n  }\n}\n']]}

MICROSIP_APPEND = '\n\n# =============================================================================\n# DASHBOARD: ventas del módulo de Punto de Venta (caja), por sucursal y\n# desglosadas por forma de cobro (efectivo, tarjeta de crédito/débito,\n# transferencia, etc.) — usa FORMAS_COBRO_DOCTOS (el desglose real de cómo\n# se cobró cada ticket, puede ser mixto) en vez de DOCTOS_PV.TOTAL_DOCTO.\n# =============================================================================\n\ndef obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):\n    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n    (excluida), en formato \'YYYY-MM-DD\', agrupadas por sucursal y forma de\n    cobro. Si los nombres de tabla/columna no coinciden con esta empresa,\n    el error de Firebird se deja tal cual para poder ajustarlo rápido."""\n    con = _conectar(config)\n    cur = con.cursor()\n    cur.execute("""\n        SELECT COALESCE(a.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n        FROM DOCTOS_PV p\n        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_PV_ID = p.DOCTO_PV_ID\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN ALMACENES a ON a.ALMACEN_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    por_sucursal = {}\n    total_general = 0.0\n    for sucursal, forma_cobro, importe in filas:\n        importe = float(importe or 0)\n        sucursal = (sucursal or "Sin sucursal").strip()\n        forma_cobro = (forma_cobro or "Sin especificar").strip()\n        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0})\n        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe\n        entrada["total"] += importe\n        total_general += importe\n\n    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])\n    return {"por_sucursal": resultado, "total_general": total_general}\n'


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
    print('   git commit -m "Dashboard: ventas por sucursal y forma de cobro (Punto de Venta)"')
    print("   git push")


if __name__ == "__main__":
    main()
