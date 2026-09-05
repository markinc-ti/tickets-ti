# -*- coding: utf-8 -*-
"""
Agrega la opcion de ver "Ventas por sucursal (Punto de Venta)" del Dashboard
por MES ademas de por dia (botones Dia/Mes arriba de la tabla).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_ventas_pv_periodo.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['def api_dashboard_ventas_pv(fecha: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):\n    """Ventas de HOY (o del día que se pida) del módulo de Punto de Venta de\n    Microsip, por sucursal y desglosadas por forma de cobro."""\n    config = _config_microsip_o_error(usuario)\n    from datetime import date, datetime, timedelta\n    if fecha:\n        try:\n            dia = datetime.strptime(fecha, "%Y-%m-%d").date()\n        except ValueError:\n            raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")\n    else:\n        dia = date.today()\n    fecha_inicio = dia.isoformat()\n    fecha_fin = (dia + timedelta(days=1)).isoformat()\n    try:\n        resultado = microsip.obtener_ventas_pv_por_sucursal(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = fecha_inicio\n    return resultado', 'def api_dashboard_ventas_pv(fecha: Optional[str] = None, mes: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):\n    """Ventas de HOY (o del día/mes que se pida) del módulo de Punto de Venta\n    de Microsip, por sucursal y desglosadas por forma de cobro."""\n    config = _config_microsip_o_error(usuario)\n    from datetime import date, datetime, timedelta\n    if mes:\n        try:\n            primer_dia = datetime.strptime(mes, "%Y-%m").date()\n        except ValueError:\n            raise HTTPException(status_code=400, detail="Mes inválido, usa el formato AAAA-MM")\n        fecha_inicio = primer_dia.isoformat()\n        fecha_fin_dt = date(primer_dia.year + 1, 1, 1) if primer_dia.month == 12 else date(primer_dia.year, primer_dia.month + 1, 1)\n        fecha_fin = fecha_fin_dt.isoformat()\n        etiqueta = mes\n    else:\n        if fecha:\n            try:\n                dia = datetime.strptime(fecha, "%Y-%m-%d").date()\n            except ValueError:\n                raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")\n        else:\n            dia = date.today()\n        fecha_inicio = dia.isoformat()\n        fecha_fin = (dia + timedelta(days=1)).isoformat()\n        etiqueta = fecha_inicio\n    try:\n        resultado = microsip.obtener_ventas_pv_por_sucursal(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = etiqueta\n    return resultado']], 'frontend/index.html': [['      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">\n            <h3 style="margin:0;">💵 Ventas por sucursal (Punto de Venta)</h3>\n            <input id="dashVentasPvFecha" type="date" style="width:auto;" onchange="renderVentasPvDashboard()" />\n          </div>\n          <div id="dashVentasPvContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n        </div>\n      ` : \'\'}', '      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">\n            <h3 style="margin:0;">💵 Ventas por sucursal (Punto de Venta)</h3>\n            <div style="display:flex; gap:6px; align-items:center;">\n              <button id="dashVentasPvTabDia" class="secondary" style="padding:4px 10px;" onclick="cambiarPeriodoVentasPv(\'dia\')">Día</button>\n              <button id="dashVentasPvTabMes" class="secondary" style="padding:4px 10px;" onclick="cambiarPeriodoVentasPv(\'mes\')">Mes</button>\n              <input id="dashVentasPvFecha" type="date" style="width:auto;" onchange="renderVentasPvDashboard()" />\n              <input id="dashVentasPvMes" type="month" style="width:auto; display:none;" onchange="renderVentasPvDashboard()" />\n            </div>\n          </div>\n          <div id="dashVentasPvContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n        </div>\n      ` : \'\'}'], ['    if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n    if (puedeVerFlotilla) {\n      document.getElementById(\'dashVentasPvFecha\').value = new Date().toISOString().slice(0, 10);\n      await renderVentasPvDashboard();\n    }\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}\n\nasync function renderVentasPvDashboard() {\n  const cont = document.getElementById(\'dashVentasPvContenido\');\n  if (!cont) return;\n  const fecha = document.getElementById(\'dashVentasPvFecha\').value;\n  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n  try {\n    const d = await api(`/api/dashboard/ventas-pv?fecha=${fecha}`);\n    if (!d.por_sucursal.length) {\n      cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">No hay ventas de Punto de Venta registradas ese día.</p>\';\n      return;\n    }', '    if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n    if (puedeVerFlotilla) {\n      document.getElementById(\'dashVentasPvFecha\').value = new Date().toISOString().slice(0, 10);\n      document.getElementById(\'dashVentasPvMes\').value = new Date().toISOString().slice(0, 7);\n      cambiarPeriodoVentasPv(PERIODO_VENTAS_PV);\n    }\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}\n\nlet PERIODO_VENTAS_PV = \'dia\';\n\nfunction cambiarPeriodoVentasPv(periodo) {\n  PERIODO_VENTAS_PV = periodo;\n  const esDia = periodo === \'dia\';\n  document.getElementById(\'dashVentasPvFecha\').style.display = esDia ? \'\' : \'none\';\n  document.getElementById(\'dashVentasPvMes\').style.display = esDia ? \'none\' : \'\';\n  const btnDia = document.getElementById(\'dashVentasPvTabDia\');\n  const btnMes = document.getElementById(\'dashVentasPvTabMes\');\n  btnDia.style.background = esDia ? \'var(--copper)\' : \'\';\n  btnDia.style.color = esDia ? \'#fff\' : \'\';\n  btnMes.style.background = !esDia ? \'var(--copper)\' : \'\';\n  btnMes.style.color = !esDia ? \'#fff\' : \'\';\n  renderVentasPvDashboard();\n}\n\nasync function renderVentasPvDashboard() {\n  const cont = document.getElementById(\'dashVentasPvContenido\');\n  if (!cont) return;\n  const query = PERIODO_VENTAS_PV === \'dia\'\n    ? `fecha=${document.getElementById(\'dashVentasPvFecha\').value}`\n    : `mes=${document.getElementById(\'dashVentasPvMes\').value}`;\n  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n  try {\n    const d = await api(`/api/dashboard/ventas-pv?${query}`);\n    if (!d.por_sucursal.length) {\n      cont.innerHTML = `<p style="font-size:12px; color:var(--muted);">No hay ventas de Punto de Venta registradas ${PERIODO_VENTAS_PV === \'dia\' ? \'ese día\' : \'ese mes\'}.</p>`;\n      return;\n    }\n']]}


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
    print("   git add backend/app.py frontend/index.html")
    print('   git commit -m "Ventas PV por mes ademas de por dia"')
    print("   git push")


if __name__ == "__main__":
    main()
