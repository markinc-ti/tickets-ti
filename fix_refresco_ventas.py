# -*- coding: utf-8 -*-
"""
Ventas por sucursal: la tarjeta chica del Dashboard principal, el desglose
completo, y la bitacora del modal ahora se actualizan solas cada 30
segundos (cumple "al menos cada minuto", lo mas cercano a tiempo real que
tiene sentido sin dejar de ser respetuoso con Microsip/Render).

Uso: colocalo en la carpeta del repo (junto a frontend/) y corre:
    py fix_refresco_ventas.py
"""
import sys

ARCHIVOS = {'frontend/index.html': [['        ${puedeVerFlotilla && resumenVentasPv ? `\n          <div class="dash-tarjeta">\n            <div class="dash-tarjeta-header">\n              <span class="dash-icono">💵</span>\n              <div>\n                <div class="dash-titulo">Ventas (Punto de Venta)</div>\n                <div class="dash-total">Hoy — $${resumenVentasPv.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n              </div>\n            </div>\n            <div style="margin-top:10px;">\n              ${resumenVentasPv.por_sucursal.length ? resumenVentasPv.por_sucursal.map(s => `\n                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n                  <span>${escapeHtml(s.sucursal)}</span>\n                  <span style="color:var(--text);">$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n                </div>\n              `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin ventas registradas hoy.</p>`}\n              <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">\n                <span>Total general</span>\n                <span>$${resumenVentasPv.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n              </div>\n            </div>\n            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>\n          </div>\n        ` : \'\'}', '${puedeVerFlotilla && resumenVentasPv ? `\n          <div class="dash-tarjeta">\n            <div id="dashResumenVentasPvCard">${contenidoTarjetaResumenVentasPv(resumenVentasPv)}</div>\n            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>\n          </div>\n        ` : \'\'}'], ['function abrirDesgloseVentasPvDashboard() {', 'function contenidoTarjetaResumenVentasPv(resumen) {\n  return `\n    <div class="dash-tarjeta-header">\n      <span class="dash-icono">💵</span>\n      <div>\n        <div class="dash-titulo">Ventas (Punto de Venta)</div>\n        <div class="dash-total">Hoy — $${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n      </div>\n    </div>\n    <div style="margin-top:10px;">\n      ${resumen.por_sucursal.length ? resumen.por_sucursal.map(s => `\n        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n          <span>${escapeHtml(s.sucursal)}</span>\n          <span style="color:var(--text);">$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n        </div>\n      `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin ventas registradas hoy.</p>`}\n      <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">\n        <span>Total general</span>\n        <span>$${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n      </div>\n    </div>\n  `;\n}\n\nlet resumenVentasPvAutoRefreshTimer = null;\n\n// La tarjeta chica del Dashboard principal también se actualiza sola cada\n// 30 segundos (no solo el desglose completo dentro del modal), para que\n// nunca se quede viendo un número de hace rato sin que el usuario haga nada.\nfunction iniciarAutoRefrescoResumenVentasPv() {\n  if (resumenVentasPvAutoRefreshTimer) return;\n  resumenVentasPvAutoRefreshTimer = setInterval(async () => {\n    const tarjeta = document.getElementById(\'dashResumenVentasPvCard\');\n    const dash = document.getElementById(\'dashboardScreen\');\n    if (!tarjeta || !dash || dash.style.display === \'none\') return;\n    try {\n      const resumen = await api(`/api/dashboard/ventas-pv?fecha=${new Date().toISOString().slice(0, 10)}`);\n      tarjeta.innerHTML = contenidoTarjetaResumenVentasPv(resumen);\n    } catch (e) {\n      // Si falla un refresco (ej. Microsip tarda en responder) se deja el\n      // último dato bueno en pantalla — se reintenta solo en 30 segundos.\n    }\n  }, 30 * 1000);\n}\n\nfunction abrirDesgloseVentasPvDashboard() {'], ['    if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n  } catch (e) {', '    if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n    if (puedeVerFlotilla && resumenVentasPv) iniciarAutoRefrescoResumenVentasPv();\n  } catch (e) {'], ['  if (ventasPvAutoRefreshTimer) clearInterval(ventasPvAutoRefreshTimer);', '  if (ventasPvAutoRefreshTimer) clearInterval(ventasPvAutoRefreshTimer);\n  if (resumenVentasPvAutoRefreshTimer) clearInterval(resumenVentasPvAutoRefreshTimer);'], ["function iniciarAutoRefrescoVentasPv() {\n  if (ventasPvAutoRefreshTimer) return;\n  ventasPvAutoRefreshTimer = setInterval(() => {\n    const overlay = document.getElementById('overlay');\n    if (overlay && overlay.classList.contains('open') && document.getElementById('dashVentasPvContenido')) {\n      renderVentasPvDashboard();\n    }\n  }, 30 * 1000);\n}", "function iniciarAutoRefrescoVentasPv() {\n  if (ventasPvAutoRefreshTimer) return;\n  ventasPvAutoRefreshTimer = setInterval(() => {\n    const overlay = document.getElementById('overlay');\n    if (overlay && overlay.classList.contains('open') && document.getElementById('dashVentasPvContenido')) {\n      renderVentasPvDashboard();\n      if (PERIODO_VENTAS_PV === 'dia') renderBitacoraVentasPvDashboard();\n    }\n  }, 30 * 1000);\n}"]]}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    hubo_error = False
    for ruta, reemplazos in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
            hubo_error = True
            continue
        cambios = 0
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

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print('   git commit -m "Ventas por sucursal se actualiza sola cada 30 segundos"')
    print("   git push")


if __name__ == "__main__":
    main()
