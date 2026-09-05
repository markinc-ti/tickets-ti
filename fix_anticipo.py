# -*- coding: utf-8 -*-
"""
Descuenta el artículo "ANTICIPO" del total de ventas por sucursal en el
Dashboard (Punto de Venta), y lo muestra aparte en rojo.

Backend (microsip.py): además de la consulta ya existente de ventas por
forma de cobro, se agrega una segunda consulta que suma el importe de las
líneas de venta (DOCTOS_PV_DET) cuyo artículo es "ANTICIPO" (join a
ARTICULOS por NOMBRE, no por ID fijo, para que siga funcionando aunque el
ID cambie o se use con otra empresa/Microsip). Ese monto se resta del
total de cada sucursal y del total general, y se regresa aparte como
"anticipo" (por sucursal) y "total_anticipo" (general).

Frontend (index.html): tanto la tarjeta chica del Dashboard principal como
la tabla completa del modal de "Ventas Punto de Venta" muestran una línea
en rojo con el anticipo descontado, cuando aplica.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_anticipo.py
"""
import sys

ARCHIVOS = {
    'backend/microsip.py': [
        [
            'def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):\n'
            '    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n'
            '    (excluida), en formato \'YYYY-MM-DD\', agrupadas por sucursal y forma de\n'
            '    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por\n'
            '    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se\n'
            '    encontró la tabla real donde esa forma de cobro vive para CxC — se\n'
            '    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se\n'
            '    encuentra esa conexión, se puede volver a ampliar.) Si los nombres de\n'
            '    tabla/columna no coinciden con esta empresa, el error de Firebird se\n'
            '    deja tal cual para poder ajustarlo rápido."""\n'
            '    con = _conectar(config)\n'
            '    cur = con.cursor()\n'
            '    cur.execute("""\n'
            '        SELECT COALESCE(s.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n'
            '        FROM DOCTOS_PV p\n'
            '        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\'\n'
            '        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n'
            '        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n'
            '        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\'\n'
            '        GROUP BY 1, 2\n'
            '        ORDER BY 1, 2\n'
            '    """, (fecha_inicio, fecha_fin))\n'
            '    filas = cur.fetchall()\n'
            '    con.close()\n'
            '\n'
            '    por_sucursal = {}\n'
            '    total_general = 0.0\n'
            '    for sucursal, forma_cobro, importe in filas:\n'
            '        importe = float(importe or 0)\n'
            '        sucursal = (sucursal or "Sin sucursal").strip()\n'
            '        forma_cobro = (forma_cobro or "Sin especificar").strip()\n'
            '        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0})\n'
            '        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe\n'
            '        entrada["total"] += importe\n'
            '        total_general += importe\n'
            '\n'
            '    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])\n'
            '    return {"por_sucursal": resultado, "total_general": total_general}\n',

            'def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):\n'
            '    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n'
            '    (excluida), en formato \'YYYY-MM-DD\', agrupadas por sucursal y forma de\n'
            '    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por\n'
            '    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se\n'
            '    encontró la tabla real donde esa forma de cobro vive para CxC — se\n'
            '    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se\n'
            '    encuentra esa conexión, se puede volver a ampliar.) El artículo\n'
            '    "ANTICIPO" se descuenta del total de cada sucursal (y se reporta\n'
            '    aparte como "anticipo"/"total_anticipo") porque es un cobro\n'
            '    adelantado, no una venta real — se identifica por NOMBRE del\n'
            '    artículo, no por ID fijo, para que siga funcionando si cambia de\n'
            '    empresa/base. Si los nombres de tabla/columna no coinciden con esta\n'
            '    empresa, el error de Firebird se deja tal cual para poder ajustarlo\n'
            '    rápido."""\n'
            '    con = _conectar(config)\n'
            '    cur = con.cursor()\n'
            '    cur.execute("""\n'
            '        SELECT COALESCE(s.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n'
            '        FROM DOCTOS_PV p\n'
            '        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\'\n'
            '        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n'
            '        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n'
            '        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\'\n'
            '        GROUP BY 1, 2\n'
            '        ORDER BY 1, 2\n'
            '    """, (fecha_inicio, fecha_fin))\n'
            '    filas = cur.fetchall()\n'
            '\n'
            '    cur.execute("""\n'
            '        SELECT COALESCE(s.NOMBRE, \'Sin sucursal\'), SUM(d.PRECIO_TOTAL_NETO)\n'
            '        FROM DOCTOS_PV p\n'
            '        JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID\n'
            '        JOIN ARTICULOS a ON a.ARTICULO_ID = d.ARTICULO_ID\n'
            '        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n'
            '        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\' AND a.NOMBRE = \'ANTICIPO\'\n'
            '        GROUP BY 1\n'
            '    """, (fecha_inicio, fecha_fin))\n'
            '    filas_anticipo = cur.fetchall()\n'
            '    con.close()\n'
            '\n'
            '    anticipos_por_sucursal = {}\n'
            '    for sucursal, importe in filas_anticipo:\n'
            '        sucursal = (sucursal or "Sin sucursal").strip()\n'
            '        anticipos_por_sucursal[sucursal] = anticipos_por_sucursal.get(sucursal, 0.0) + float(importe or 0)\n'
            '\n'
            '    por_sucursal = {}\n'
            '    total_general = 0.0\n'
            '    for sucursal, forma_cobro, importe in filas:\n'
            '        importe = float(importe or 0)\n'
            '        sucursal = (sucursal or "Sin sucursal").strip()\n'
            '        forma_cobro = (forma_cobro or "Sin especificar").strip()\n'
            '        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})\n'
            '        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe\n'
            '        entrada["total"] += importe\n'
            '        total_general += importe\n'
            '\n'
            '    total_anticipo_general = 0.0\n'
            '    for sucursal, anticipo in anticipos_por_sucursal.items():\n'
            '        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})\n'
            '        entrada["anticipo"] = anticipo\n'
            '        entrada["total"] -= anticipo\n'
            '        total_general -= anticipo\n'
            '        total_anticipo_general += anticipo\n'
            '\n'
            '    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])\n'
            '    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}\n'
        ],
    ],
    'frontend/index.html': [
        [
            'function contenidoTarjetaResumenVentasPv(resumen) {\n'
            '  return `\n'
            '    <div class="dash-tarjeta-header">\n'
            '      <span class="dash-icono">💵</span>\n'
            '      <div>\n'
            '        <div class="dash-titulo">Ventas (Punto de Venta)</div>\n'
            '        <div class="dash-total">Hoy — $${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
            '      </div>\n'
            '    </div>\n'
            '    <div style="margin-top:10px;">\n'
            '      ${resumen.por_sucursal.length ? resumen.por_sucursal.map(s => `\n'
            '        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
            '          <span>${escapeHtml(s.sucursal)}</span>\n'
            '          <span style="color:var(--text);">$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
            '        </div>\n'
            '      `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin ventas registradas hoy.</p>`}\n'
            '      <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">\n'
            '        <span>Total general</span>\n'
            '        <span>$${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
            '      </div>\n'
            '    </div>\n'
            '  `;\n'
            '}\n',

            'function contenidoTarjetaResumenVentasPv(resumen) {\n'
            '  return `\n'
            '    <div class="dash-tarjeta-header">\n'
            '      <span class="dash-icono">💵</span>\n'
            '      <div>\n'
            '        <div class="dash-titulo">Ventas (Punto de Venta)</div>\n'
            '        <div class="dash-total">Hoy — $${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</div>\n'
            '      </div>\n'
            '    </div>\n'
            '    <div style="margin-top:10px;">\n'
            '      ${resumen.por_sucursal.length ? resumen.por_sucursal.map(s => `\n'
            '        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">\n'
            '          <span>${escapeHtml(s.sucursal)}</span>\n'
            '          <span style="color:var(--text);">$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
            '        </div>\n'
            '        ${s.anticipo > 0 ? `\n'
            '        <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px; color:var(--copper);">\n'
            '          <span>&nbsp;&nbsp;Anticipo</span>\n'
            '          <span>-$${s.anticipo.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
            '        </div>\n'
            '        ` : \'\'}\n'
            '      `).join(\'\') : `<p style="font-size:12px; color:var(--muted);">Sin ventas registradas hoy.</p>`}\n'
            '      <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">\n'
            '        <span>Total general</span>\n'
            '        <span>$${resumen.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</span>\n'
            '      </div>\n'
            '    </div>\n'
            '  `;\n'
            '}\n'
        ],
        [
            'async function renderVentasPvDashboard() {\n'
            '  const cont = document.getElementById(\'dashVentasPvContenido\');\n'
            '  if (!cont) return;\n'
            '  const query = PERIODO_VENTAS_PV === \'dia\'\n'
            '    ? `fecha=${document.getElementById(\'dashVentasPvFecha\').value}`\n'
            '    : `mes=${document.getElementById(\'dashVentasPvMes\').value}`;\n'
            '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
            '  try {\n'
            '    const d = await api(`/api/dashboard/ventas-pv?${query}`);\n'
            '    if (!d.por_sucursal.length) {\n'
            '      cont.innerHTML = `<p style="font-size:12px; color:var(--muted);">No hay ventas de Punto de Venta registradas ${PERIODO_VENTAS_PV === \'dia\' ? \'ese día\' : \'ese mes\'}.</p>`;\n'
            '      return;\n'
            '    }\n'
            '\n'
            '    // Unión de todas las formas de cobro que aparecen (para columnas parejas en todas las sucursales)\n'
            '    const formasCobro = [...new Set(d.por_sucursal.flatMap(s => Object.keys(s.formas_cobro)))].sort();\n'
            '    cont.innerHTML = `\n'
            '      <table class="users">\n'
            '        <thead><tr><th>Sucursal</th>${formasCobro.map(f => `<th>${escapeHtml(f)}</th>`).join(\'\')}<th>Total</th></tr></thead>\n'
            '        <tbody>\n'
            '          ${d.por_sucursal.map(s => `\n'
            '            <tr>\n'
            '              <td>${escapeHtml(s.sucursal)}</td>\n'
            '              ${formasCobro.map(f => `<td>${s.formas_cobro[f] != null ? \'$\' + s.formas_cobro[f].toLocaleString(\'es-MX\', {minimumFractionDigits:2}) : \'—\'}</td>`).join(\'\')}\n'
            '              <td><b>$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td>\n'
            '            </tr>\n'
            '          `).join(\'\')}\n'
            '        </tbody>\n'
            '        <tfoot><tr><td><b>Total general</b></td>${formasCobro.map(() => \'<td></td>\').join(\'\')}<td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n'
            '      </table>\n'
            '    `;\n'
            '  } catch (e) {\n'
            '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
            '  }\n'
            '}\n',

            'async function renderVentasPvDashboard() {\n'
            '  const cont = document.getElementById(\'dashVentasPvContenido\');\n'
            '  if (!cont) return;\n'
            '  const query = PERIODO_VENTAS_PV === \'dia\'\n'
            '    ? `fecha=${document.getElementById(\'dashVentasPvFecha\').value}`\n'
            '    : `mes=${document.getElementById(\'dashVentasPvMes\').value}`;\n'
            '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
            '  try {\n'
            '    const d = await api(`/api/dashboard/ventas-pv?${query}`);\n'
            '    if (!d.por_sucursal.length) {\n'
            '      cont.innerHTML = `<p style="font-size:12px; color:var(--muted);">No hay ventas de Punto de Venta registradas ${PERIODO_VENTAS_PV === \'dia\' ? \'ese día\' : \'ese mes\'}.</p>`;\n'
            '      return;\n'
            '    }\n'
            '\n'
            '    // Unión de todas las formas de cobro que aparecen (para columnas parejas en todas las sucursales)\n'
            '    const formasCobro = [...new Set(d.por_sucursal.flatMap(s => Object.keys(s.formas_cobro)))].sort();\n'
            '    const hayAnticipos = d.por_sucursal.some(s => s.anticipo > 0);\n'
            '    cont.innerHTML = `\n'
            '      <table class="users">\n'
            '        <thead><tr><th>Sucursal</th>${formasCobro.map(f => `<th>${escapeHtml(f)}</th>`).join(\'\')}${hayAnticipos ? \'<th style="color:var(--copper);">Anticipo</th>\' : \'\'}<th>Total</th></tr></thead>\n'
            '        <tbody>\n'
            '          ${d.por_sucursal.map(s => `\n'
            '            <tr>\n'
            '              <td>${escapeHtml(s.sucursal)}</td>\n'
            '              ${formasCobro.map(f => `<td>${s.formas_cobro[f] != null ? \'$\' + s.formas_cobro[f].toLocaleString(\'es-MX\', {minimumFractionDigits:2}) : \'—\'}</td>`).join(\'\')}\n'
            '              ${hayAnticipos ? `<td style="color:var(--copper);">${s.anticipo > 0 ? \'-$\' + s.anticipo.toLocaleString(\'es-MX\', {minimumFractionDigits:2}) : \'—\'}</td>` : \'\'}\n'
            '              <td><b>$${s.total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td>\n'
            '            </tr>\n'
            '          `).join(\'\')}\n'
            '        </tbody>\n'
            '        <tfoot><tr><td><b>Total general</b></td>${formasCobro.map(() => \'<td></td>\').join(\'\')}${hayAnticipos ? `<td style="color:var(--copper);"><b>-$${d.total_anticipo.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td>` : \'\'}<td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n'
            '      </table>\n'
            '    `;\n'
            '  } catch (e) {\n'
            '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
            '  }\n'
            '}\n'
        ],
    ],
}


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
                # Ya se había aplicado antes (script corrido dos veces) — no es error.
                cambios += 1
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
    print("   git add backend/microsip.py frontend/index.html")
    print("   git commit -m \"Descontar anticipo del total de ventas por sucursal en Dashboard\"")
    print("   git push")


if __name__ == "__main__":
    main()
