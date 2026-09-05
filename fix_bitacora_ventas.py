# -*- coding: utf-8 -*-
"""
Dashboard: arregla el modal de "Ventas por sucursal" que salia cortado
(ahora usa el ancho completo tipo Administrar, mas scroll horizontal como
respaldo), y agrega una bitacora de ventas del dia: primeras 10, ultimas 10,
y el rango de 12:00pm a 2:00pm.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_bitacora_ventas.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['    resultado["fecha"] = etiqueta\n    return resultado', '    resultado["fecha"] = etiqueta\n    return resultado\n\n\n@app.get("/api/dashboard/bitacora-ventas-pv")\ndef api_dashboard_bitacora_ventas_pv(fecha: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):\n    """Primeras/últimas 10 ventas del día y el rango de 12pm a 2pm, para\n    revisar la actividad de Punto de Venta a lo largo del día."""\n    config = _config_microsip_o_error(usuario)\n    from datetime import date, datetime, timedelta\n    if fecha:\n        try:\n            dia = datetime.strptime(fecha, "%Y-%m-%d").date()\n        except ValueError:\n            raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")\n    else:\n        dia = date.today()\n    fecha_inicio = dia.isoformat()\n    fecha_fin = (dia + timedelta(days=1)).isoformat()\n    try:\n        resultado = microsip.obtener_bitacora_ventas_pv(config, fecha_inicio, fecha_fin)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")\n    resultado["fecha"] = fecha_inicio\n    return resultado']], 'frontend/index.html': [['      <input id="dashVentasPvFecha" type="date" style="width:auto;" onchange="renderVentasPvDashboard()" />\n      <input id="dashVentasPvMes" type="month" style="width:auto; display:none;" onchange="renderVentasPvDashboard()" />\n    </div>\n    <div id="dashVentasPvContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n  `;\n  abrirModal(true);\n  document.getElementById(\'dashVentasPvFecha\').value = new Date().toISOString().slice(0, 10);\n  document.getElementById(\'dashVentasPvMes\').value = new Date().toISOString().slice(0, 7);\n  cambiarPeriodoVentasPv(PERIODO_VENTAS_PV);', '      <input id="dashVentasPvFecha" type="date" style="width:auto;" onchange="renderVentasPvDashboard(); renderBitacoraVentasPvDashboard();" />\n      <input id="dashVentasPvMes" type="month" style="width:auto; display:none;" onchange="renderVentasPvDashboard()" />\n    </div>\n    <div id="dashVentasPvContenido" style="overflow-x:auto;"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n    <div id="dashBitacoraVentasPv" style="margin-top:24px;"></div>\n  `;\n  abrirModal(\'admin\');\n  document.getElementById(\'dashVentasPvFecha\').value = new Date().toISOString().slice(0, 10);\n  document.getElementById(\'dashVentasPvMes\').value = new Date().toISOString().slice(0, 7);\n  cambiarPeriodoVentasPv(PERIODO_VENTAS_PV);'], ["  btnMes.style.color = !esDia ? '#fff' : '';\n  renderVentasPvDashboard();\n}", '  btnMes.style.color = !esDia ? \'#fff\' : \'\';\n  renderVentasPvDashboard();\n  const bitacora = document.getElementById(\'dashBitacoraVentasPv\');\n  if (esDia) {\n    renderBitacoraVentasPvDashboard();\n  } else if (bitacora) {\n    bitacora.innerHTML = \'\'; // la bitácora (primeras/últimas ventas, rango 12-2pm) solo aplica a un día específico\n  }\n}\n\nasync function renderBitacoraVentasPvDashboard() {\n  const cont = document.getElementById(\'dashBitacoraVentasPv\');\n  if (!cont) return;\n  const fecha = document.getElementById(\'dashVentasPvFecha\').value;\n  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando bitácora…</p>\';\n  try {\n    const b = await api(`/api/dashboard/bitacora-ventas-pv?fecha=${fecha}`);\n    const filaVenta = (v) => `\n      <tr>\n        <td>${escapeHtml(v.hora || \'—\')}</td>\n        <td>${escapeHtml(v.folio || \'—\')}</td>\n        <td>${escapeHtml(v.sucursal)}</td>\n        <td>$${v.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n      </tr>\n    `;\n    const tablaVentas = (filas, vacioTexto) => `\n      <div style="overflow-x:auto;">\n        <table class="users">\n          <thead><tr><th>Hora</th><th>Folio</th><th>Sucursal</th><th>Total</th></tr></thead>\n          <tbody>${filas.length ? filas.map(filaVenta).join(\'\') : `<tr><td colspan="4" class="empty-col">${vacioTexto}</td></tr>`}</tbody>\n        </table>\n      </div>\n    `;\n    const totalRango = b.rango_12_14.reduce((s, v) => s + v.total, 0);\n    cont.innerHTML = `\n      <h3 style="margin:0 0 4px; font-size:15px;">📋 Bitácora de ventas del día</h3>\n      <p style="font-size:12px; color:var(--muted); margin-bottom:14px;">${b.total_ventas} ticket(s) en total ese día.</p>\n\n      <h4 style="margin:0 0 6px; font-size:13px;">🌅 Primeras 10 ventas</h4>\n      ${tablaVentas(b.primeras, \'— sin ventas ese día —\')}\n\n      <h4 style="margin:18px 0 6px; font-size:13px;">🌙 Últimas 10 ventas</h4>\n      ${tablaVentas(b.ultimas, \'— sin ventas ese día —\')}\n\n      <h4 style="margin:18px 0 4px; font-size:13px;">🍽️ Ventas de 12:00 pm a 2:00 pm</h4>\n      <p style="font-size:12px; color:var(--muted); margin-bottom:6px;">${b.rango_12_14.length} ticket(s) — $${totalRango.toLocaleString(\'es-MX\', {minimumFractionDigits:2})} en total</p>\n      ${tablaVentas(b.rango_12_14, \'— sin ventas en ese rango —\')}\n    `;\n  } catch (e) {\n    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n  }\n}']]}

MICROSIP_APPEND = '\n\ndef obtener_bitacora_ventas_pv(config: dict, fecha_inicio: str, fecha_fin: str):\n    """Primeras y últimas 10 ventas del día (con su hora y sucursal), más el\n    rango de 12:00pm a 2:00pm — para revisar la actividad de Punto de Venta\n    a lo largo del día. fecha_inicio/fecha_fin en formato \'YYYY-MM-DD\'\n    (el rango de UN día se arma como [fecha, fecha + 1 día))."""\n    con = _conectar(config)\n    cur = con.cursor()\n    cur.execute("""\n        SELECT p.FOLIO, p.HORA, COALESCE(s.NOMBRE, \'Sin sucursal\'), p.IMPORTE_NETO\n        FROM DOCTOS_PV p\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        ORDER BY p.HORA\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    ventas = []\n    for folio, hora, sucursal, importe in filas:\n        ventas.append({\n            "folio": folio,\n            # Se convierte a texto "HH:MM:SS" para comparar y mostrar sin\n            # depender del tipo exacto que regrese el driver de Firebird.\n            "hora": str(hora)[:8] if hora is not None else None,\n            "sucursal": (sucursal or "Sin sucursal").strip(),\n            "total": float(importe or 0),\n        })\n\n    rango_comida = [v for v in ventas if v["hora"] and "12:00:00" <= v["hora"] < "14:00:00"]\n\n    return {\n        "total_ventas": len(ventas),\n        "primeras": ventas[:10],\n        "ultimas": ventas[-10:],\n        "rango_12_14": rango_comida,\n    }\n'


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
    print('   git commit -m "Dashboard: modal completo + bitacora de ventas"')
    print("   git push")


if __name__ == "__main__":
    main()
