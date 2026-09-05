# -*- coding: utf-8 -*-
"""
Amplía "Artículos sin movimiento":
1. Filtro opcional por fecha de ENTRADA de inventario (ej. "todo lo que
   entró en enero y sigue sin venderse"), usando DOCTOS_IN/DOCTOS_IN_DET
   cruzado con CONCEPTOS_IN.NATURALEZA='E' (compras, recepción de
   mercancía, etc. — no salidas). Sin fechas, se muestran todos como
   antes.
2. Se cambia de COSTO a PRECIO DE VENTA (PRECIOS_ARTICULOS x 1.16 IVA —
   mismo precio de lista que usa el Checador de precio) para esta
   consulta específica.

(Filtro por marca/clasificador: pendiente, no encontramos todavía la
tabla de unión artículo↔clasificador — se investiga después.)

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_sin_movimiento_fecha_venta.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/microsip.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/microsip.py'] = [
    [
        'def obtener_articulos_sin_movimiento_por_almacen(config: dict):\n'
        '    """Artículos con existencia > 0 en cada almacén que JAMÁS se han\n'
        '    vendido por Punto de Venta, en ninguna sucursal, en todo el historial\n'
        '    de Microsip (no un rango de fechas). Mismo criterio de\n'
        "    existencia/costo que 'Valor del inventario' (CAPAS_COSTOS por\n"
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
        '    return {"por_sucursal": resultado, "total_general": total_general}\n',

        'def obtener_articulos_sin_movimiento_por_almacen(config: dict, fecha_inicio: str = None, fecha_fin: str = None):\n'
        '    """Artículos con existencia > 0 en cada almacén que JAMÁS se han\n'
        '    vendido por Punto de Venta, en ninguna sucursal, en todo el historial\n'
        '    de Microsip. Valuados a PRECIO DE VENTA (PRECIOS_ARTICULOS x 1.16\n'
        '    IVA — mismo precio de lista que usa el Checador de precio), no a\n'
        '    costo. Si se dan fecha_inicio/fecha_fin (\'YYYY-MM-DD\', fecha_fin\n'
        '    excluida), solo se incluyen artículos que tuvieron una ENTRADA de\n'
        '    inventario (DOCTOS_IN/DOCTOS_IN_DET, cruzado con\n'
        "    CONCEPTOS_IN.NATURALEZA='E' — compras, recepción de mercancía, etc.,\n"
        '    nunca salidas) en ese rango; sin fechas se muestran todos, sin\n'
        '    importar cuándo entraron. Se devuelven TODOS los artículos (no solo\n'
        '    un top 50) — el frontend pagina de 50 en 50. Ordenados por precio\n'
        '    unitario, de mayor a menor."""\n'
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
        '    entradas_permitidas = None\n'
        '    if fecha_inicio and fecha_fin:\n'
        '        cur.execute("""\n'
        '            SELECT DISTINCT d.ALMACEN_ID, d.ARTICULO_ID\n'
        '            FROM DOCTOS_IN_DET d\n'
        '            JOIN DOCTOS_IN p ON p.DOCTO_IN_ID = d.DOCTO_IN_ID\n'
        '            JOIN CONCEPTOS_IN c ON c.CONCEPTO_IN_ID = d.CONCEPTO_IN_ID\n'
        '            WHERE c.NATURALEZA = \'E\' AND p.CANCELADO = \'N\' AND d.CANCELADO = \'N\'\n'
        '              AND p.FECHA >= ? AND p.FECHA < ?\n'
        '        """, (fecha_inicio, fecha_fin))\n'
        '        entradas_permitidas = {(almacen_id, articulo_id) for almacen_id, articulo_id in cur.fetchall()}\n'
        '\n'
        '    cur.execute("""\n'
        '        SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA)\n'
        '        FROM CAPAS_COSTOS cc\n'
        '        WHERE cc.CAPA_AGOTADA = \'N\'\n'
        '        GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID\n'
        '    """)\n'
        '    filas_articulos = [\n'
        '        (almacen_id, articulo_id, existencia)\n'
        '        for almacen_id, articulo_id, existencia in cur.fetchall()\n'
        '        if articulo_id not in vendidos_alguna_vez\n'
        '        and (entradas_permitidas is None or (almacen_id, articulo_id) in entradas_permitidas)\n'
        '    ]\n'
        '\n'
        '    cur.execute("SELECT ALMACEN_ID, NOMBRE FROM ALMACENES")\n'
        '    nombres_almacen = {aid: (nombre or "Sin nombre").strip() for aid, nombre in cur.fetchall()}\n'
        '\n'
        '    articulo_ids = sorted({fila[1] for fila in filas_articulos})\n'
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
        '        # impuesto, igual que en el Checador de precio se le agrega 16%\n'
        '        # de IVA.\n'
        '        cur.execute(f"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})", tuple(lote))\n'
        '        for aid, precio in cur.fetchall():\n'
        '            if aid not in precios and precio is not None:\n'
        '                precios[aid] = round(float(precio) * 1.16, 2)\n'
        '\n'
        '    con.close()\n'
        '\n'
        '    por_almacen = {}\n'
        '    for almacen_id, articulo_id, existencia in filas_articulos:\n'
        '        existencia = float(existencia or 0)\n'
        '        if existencia <= 0:\n'
        '            continue\n'
        '        precio_unitario = precios.get(articulo_id)\n'
        '        if precio_unitario is None:\n'
        '            continue  # sin precio de lista capturado en Microsip, no se puede valuar\n'
        '        valor = precio_unitario * existencia\n'
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
        '            "precio_unitario": precio_unitario,\n'
        '            "valor_total": valor,\n'
        '        })\n'
        '\n'
        '    for datos in por_almacen.values():\n'
        '        datos["articulos"].sort(key=lambda a: -a["precio_unitario"])\n'
        '\n'
        '    resultado = sorted(por_almacen.values(), key=lambda d: -d["valor_total"])\n'
        '    total_general = sum(d["valor_total"] for d in resultado)\n'
        '    return {"por_sucursal": resultado, "total_general": total_general}\n',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py
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
        'def api_dashboard_sin_movimiento(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):\n'
        '    """Artículos que nunca se han vendido por Punto de Venta (en ninguna\n'
        '    sucursal, en todo el historial), con existencia > 0, por almacén,\n'
        '    valuados a precio de venta. Si se dan fecha_inicio/fecha_fin\n'
        '    (AAAA-MM-DD, fecha_fin excluida), solo incluye los que tuvieron una\n'
        '    entrada de inventario en ese rango."""\n'
        '    config = _config_microsip_o_error(usuario)\n'
        '    try:\n'
        '        resultado = microsip.obtener_articulos_sin_movimiento_por_almacen(config, fecha_inicio, fecha_fin)\n'
        '    except Exception as e:\n'
        '        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (sin movimiento): {e}")\n'
        '    return resultado\n',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        "function abrirDesgloseSinMovimientoDashboard() {\n"
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
        "    const d = await api('/api/dashboard/sin-movimiento');\n",

        "function abrirDesgloseSinMovimientoDashboard() {\n"
        "  document.getElementById('modalContent').innerHTML = `\n"
        '    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n'
        '    <h2>🐌 Artículos sin movimiento por sucursal</h2>\n'
        '    <p style="font-size:12px; color:var(--muted); margin-top:-8px;">Nunca se han vendido por Punto de Venta, en ninguna sucursal, en todo el historial. Valuados a precio de venta.</p>\n'
        '    <div style="display:flex; justify-content:flex-end; align-items:center; margin:12px 0; flex-wrap:wrap; gap:8px;">\n'
        '      <label style="font-size:12px; color:var(--muted);">Entró entre:</label>\n'
        '      <input id="dashSinMovimientoDesde" type="date" style="width:auto;" />\n'
        '      <span style="font-size:12px; color:var(--muted);">y</span>\n'
        '      <input id="dashSinMovimientoHasta" type="date" style="width:auto;" />\n'
        '      <button class="secondary" style="padding:4px 10px;" onclick="renderSinMovimientoDashboard()">Filtrar</button>\n'
        '      <button class="secondary" style="padding:4px 10px;" onclick="limpiarFiltroFechaSinMovimiento()">Quitar filtro</button>\n'
        '    </div>\n'
        '    <div id="dashSinMovimientoContenido"><p style="font-size:12px; color:var(--muted);">Cargando…</p></div>\n'
        '  `;\n'
        "  abrirModal('admin');\n"
        '  renderSinMovimientoDashboard();\n'
        '}\n'
        '\n'
        'function limpiarFiltroFechaSinMovimiento() {\n'
        "  const desde = document.getElementById('dashSinMovimientoDesde');\n"
        "  const hasta = document.getElementById('dashSinMovimientoHasta');\n"
        "  if (desde) desde.value = '';\n"
        "  if (hasta) hasta.value = '';\n"
        '  renderSinMovimientoDashboard();\n'
        '}\n'
        '\n'
        'async function renderSinMovimientoDashboard() {\n'
        "  const cont = document.getElementById('dashSinMovimientoContenido');\n"
        '  if (!cont) return;\n'
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando…</p>\';\n'
        '  try {\n'
        "    const desde = document.getElementById('dashSinMovimientoDesde')?.value;\n"
        "    const hasta = document.getElementById('dashSinMovimientoHasta')?.value;\n"
        "    let query = '';\n"
        '    if (desde && hasta) {\n'
        '      // El input "hasta" es inclusivo (el día elegido) — el backend\n'
        '      // espera fecha_fin EXCLUSIVA, así que se le suma 1 día.\n'
        "      const hastaExclusiva = new Date(hasta + 'T00:00:00');\n"
        '      hastaExclusiva.setDate(hastaExclusiva.getDate() + 1);\n'
        "      query = `?fecha_inicio=${desde}&fecha_fin=${hastaExclusiva.toISOString().slice(0,10)}`;\n"
        '    }\n'
        '    const d = await api(`/api/dashboard/sin-movimiento${query}`);\n',
    ],
    [
        '          <thead><tr><th>Sucursal</th><th>Artículos sin movimiento</th><th>Valor en inventario</th></tr></thead>\n',

        '          <thead><tr><th>Sucursal</th><th>Artículos sin movimiento</th><th>Valor a precio de venta</th></tr></thead>\n',
    ],
    [
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
        "          `).join('') : `<tr><td colspan=\"6\" class=\"empty-col\">— sin artículos sin movimiento en esta sucursal —</td></tr>`}\n",

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
        "          `).join('') : `<tr><td colspan=\"6\" class=\"empty-col\">— sin artículos sin movimiento en esta sucursal —</td></tr>`}\n",
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
    print("   git commit -m \"Sin movimiento: filtro por fecha de entrada + precio de venta\"")
    print("   git push")


if __name__ == "__main__":
    main()
