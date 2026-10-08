#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador: desglose Subtotal / IVA (16%) / Total a pagar en cada cotizacion
(PDF y recibo termico), y datos de pago (cuenta bancaria) configurables POR
EMPRESA desde el panel de superadmin (Administrar -> Empresas -> boton
"Datos de pago"), para que el cliente sepa como pagarte si acepta la
cotizacion.

Que cambia:

1. backend/db.py
   - Nueva columna empresas.datos_pago_cotizacion (texto libre).
   - listar_empresas() ahora la incluye (la necesita el panel de Empresas).
   - actualizar_empresa() ahora la puede guardar.

2. backend/app.py
   - PATCH /api/empresas/{id} (el mismo que ya existia) ahora tambien
     acepta datos_pago_cotizacion.
   - La ruta publica del recibo termico manda esos datos (si los hay) al
     generarlo.

3. backend/pdfs_cotizaciones.py
   - El bloque "Total" del PDF ahora muestra 3 lineas: Subtotal, IVA (16%)
     y TOTAL A PAGAR. El total que paga el cliente NO cambia -- los precios
     ya incluian el IVA (igual que en el resto de la app), solo se desglosa.
   - Nuevo bloque opcional "datos_pago" (justo despues del Total): sale
     solo si el superadmin configuro algo para esa empresa.
   - De paso corrige un bug real que ya existia: la funcion del recibo
     termico (58mm, Star PassPRNT) estaba duplicada en el archivo -- la
     copia que de verdad se usaba (la segunda, por como Python resuelve
     definiciones repetidas) ignoraba el descuento por articulo al calcular
     el total impreso. Se dejo una sola version, con el descuento aplicado
     correctamente y el mismo desglose Subtotal/IVA/Total que el PDF.

4. frontend/index.html
   - Administrar -> Empresas: nuevo boton "Datos de pago" por empresa
     (junto a "Modulos"), con un cuadro de texto libre.
   - Al armar una cotizacion nueva, debajo del total ya se ve en vivo el
     desglose Subtotal / IVA (16%), igual que va a salir en el PDF.
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS limite_almacenamiento_videos_mb INTEGER NOT NULL DEFAULT 2048;\n\n        CREATE TABLE IF NOT EXISTS videos_subidos (',
            '        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS limite_almacenamiento_videos_mb INTEGER NOT NULL DEFAULT 2048;\n\n        -- Datos de pago (cuenta bancaria, CLABE, etc.) que el superadmin\n        -- configura por empresa desde Administrar -> Empresas -> Datos de\n        -- pago. Si se llenan, salen como una sección aparte en el PDF de\n        -- cada cotización (justo después del total) para que el cliente\n        -- sepa cómo pagar si la acepta.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS datos_pago_cotizacion TEXT;\n\n        CREATE TABLE IF NOT EXISTS videos_subidos (',
        ],
        [
            'def listar_empresas():\n    conn = get_connection()\n    cur = conn.cursor()\n    columnas_modulos = ", ".join(MODULOS_EMPRESA.keys())\n    cur.execute(f"SELECT id, nombre, logo_base64, activo, creado_en, {columnas_modulos} FROM empresas ORDER BY nombre")',
            'def listar_empresas():\n    conn = get_connection()\n    cur = conn.cursor()\n    columnas_modulos = ", ".join(MODULOS_EMPRESA.keys())\n    cur.execute(f"SELECT id, nombre, logo_base64, activo, creado_en, datos_pago_cotizacion, {columnas_modulos} FROM empresas ORDER BY nombre")',
        ],
        [
            'def actualizar_empresa(empresa_id, nombre=None, activo=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    campos, valores = [], []\n    if nombre is not None:\n        campos.append("nombre = %s"); valores.append(nombre)\n    if activo is not None:\n        campos.append("activo = %s"); valores.append(activo)\n    if campos:',
            'def actualizar_empresa(empresa_id, nombre=None, activo=None, datos_pago_cotizacion=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    campos, valores = [], []\n    if nombre is not None:\n        campos.append("nombre = %s"); valores.append(nombre)\n    if activo is not None:\n        campos.append("activo = %s"); valores.append(activo)\n    if datos_pago_cotizacion is not None:\n        campos.append("datos_pago_cotizacion = %s"); valores.append(datos_pago_cotizacion)\n    if campos:',
        ],
    ],
    'backend/app.py': [
        [
            'class ActualizacionEmpresa(BaseModel):\n    nombre: Optional[str] = None\n    activo: Optional[bool] = None',
            'class ActualizacionEmpresa(BaseModel):\n    nombre: Optional[str] = None\n    activo: Optional[bool] = None\n    datos_pago_cotizacion: Optional[str] = None',
        ],
        [
            'def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):\n    if not db.obtener_empresa(empresa_id):\n        raise HTTPException(status_code=404, detail="Empresa no encontrada")\n    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo)\n    return db.obtener_empresa(empresa_id)',
            'def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):\n    if not db.obtener_empresa(empresa_id):\n        raise HTTPException(status_code=404, detail="Empresa no encontrada")\n    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo, payload.datos_pago_cotizacion)\n    return db.obtener_empresa(empresa_id)',
        ],
        [
            '    html = pdfs_cotizaciones.generar_html_recibo_termico(cotizacion)\n    return Response(content=html, media_type="text/html; charset=utf-8")',
            '    empresa = db.obtener_empresa(cotizacion["empresa_id"])\n    datos_pago = (empresa or {}).get("datos_pago_cotizacion")\n    html = pdfs_cotizaciones.generar_html_recibo_termico(cotizacion, datos_pago)\n    return Response(content=html, media_type="text/html; charset=utf-8")',
        ],
    ],
    'backend/pdfs_cotizaciones.py': [
        [
            'ORDEN_BLOQUES_DEFAULT = [\n    "cliente", "tabla_articulos", "precio_contado", "total",\n    "meses_msi", "notas", "contacto", "vigencia",\n]',
            'ORDEN_BLOQUES_DEFAULT = [\n    "cliente", "tabla_articulos", "precio_contado", "total", "datos_pago",\n    "meses_msi", "notas", "contacto", "vigencia",\n]',
        ],
        [
            'NOMBRES_BLOQUES_COTIZACION = {\n    "cliente": "Datos del cliente",\n    "tabla_articulos": "Tabla de artículos",\n    "precio_contado": "Precio de contado (solo si hay descuentos)",\n    "total": "Total",\n    "meses_msi": "Meses sin intereses (solo si se cotizaron)",\n    "notas": "Notas",\n    "contacto": "Contacto (atendido por / sucursal)",\n    "vigencia": "Vigencia y aviso legal",\n}',
            'NOMBRES_BLOQUES_COTIZACION = {\n    "cliente": "Datos del cliente",\n    "tabla_articulos": "Tabla de artículos",\n    "precio_contado": "Precio de contado (solo si hay descuentos)",\n    "total": "Subtotal, IVA y total a pagar",\n    "datos_pago": "Datos para pago (cuenta bancaria — se configura en Administrar -> Empresas)",\n    "meses_msi": "Meses sin intereses (solo si se cotizaron)",\n    "notas": "Notas",\n    "contacto": "Contacto (atendido por / sucursal)",\n    "vigencia": "Vigencia y aviso legal",\n}',
        ],
        [
            'ESPACIADO_DEFAULT_BLOQUES = {\n    "cliente": 0, "tabla_articulos": 10, "precio_contado": 0, "total": 0,\n    "meses_msi": 14, "notas": 14, "contacto": 14, "vigencia": 20,\n}',
            'ESPACIADO_DEFAULT_BLOQUES = {\n    "cliente": 0, "tabla_articulos": 10, "precio_contado": 0, "total": 0, "datos_pago": 14,\n    "meses_msi": 14, "notas": 14, "contacto": 14, "vigencia": 20,\n}',
        ],
        [
            'def _bloque_total(elementos, styles, cot, ctx):\n    factor = ctx["factor"]\n    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12 * factor, textColor=NEGRO)\n    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12 * factor, alignment=2, textColor=ROJO)\n    tabla_total = Table([[\n        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),\n        Paragraph(f"<b>{_fmt_dinero(ctx[\'total\'])}</b>", estilo_total_valor),\n    ]], colWidths=[12.7 * cm, 3.3 * cm])\n    estilo_tabla_total = [\n        ("TOPPADDING", (0, 0), (-1, -1), 4),\n        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),\n    ]\n    if not ctx["hay_descuentos"]:\n        estilo_tabla_total.append(("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO))\n    tabla_total.setStyle(TableStyle(estilo_tabla_total))\n    elementos.append(tabla_total)\n    return True',
            'def _bloque_total(elementos, styles, cot, ctx):\n    # Los precios de los artículos ya incluyen el 16% de IVA (mismo precio de\n    # lista que usa el Checador de precio, ver microsip.py) — aquí solo se\n    # DESGLOSA ese total ya conocido en Subtotal + IVA, no se le suma nada\n    # encima. El total que paga el cliente no cambia.\n    factor = ctx["factor"]\n    total = ctx["total"]\n    subtotal = total / 1.16\n    iva = total - subtotal\n    estilo_desglose_etiqueta = ParagraphStyle("DesgloseEtiqueta", parent=styles["Normal"], fontSize=9.5 * factor, textColor=GRIS, alignment=2)\n    estilo_desglose_valor = ParagraphStyle("DesgloseValor", parent=styles["Normal"], fontSize=9.5 * factor, alignment=2, textColor=GRIS)\n    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12 * factor, textColor=NEGRO)\n    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12 * factor, alignment=2, textColor=ROJO)\n    filas = [\n        [Paragraph("Subtotal", estilo_desglose_etiqueta), Paragraph(_fmt_dinero(subtotal), estilo_desglose_valor)],\n        [Paragraph("IVA (16%)", estilo_desglose_etiqueta), Paragraph(_fmt_dinero(iva), estilo_desglose_valor)],\n        [Paragraph("<b>TOTAL A PAGAR</b>", estilo_total_etiqueta), Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor)],\n    ]\n    tabla_total = Table(filas, colWidths=[12.7 * cm, 3.3 * cm])\n    tabla_total.setStyle(TableStyle([\n        ("TOPPADDING", (0, 0), (-1, 0), 2), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),\n        ("TOPPADDING", (0, 1), (-1, 1), 1), ("BOTTOMPADDING", (0, 1), (-1, 1), 4),\n        ("TOPPADDING", (0, 2), (-1, 2), 4), ("BOTTOMPADDING", (0, 2), (-1, 2), 4),\n        ("LINEABOVE", (0, 2), (-1, 2), 1.2, ROJO),\n    ]))\n    elementos.append(tabla_total)\n    return True\n\n\ndef _bloque_datos_pago(elementos, styles, cot, ctx):\n    """Datos de pago (ej. cuenta bancaria) configurados por el superadmin\n    desde Administrar -> Empresas -> Datos de pago (uno por empresa) — solo\n    se dibuja si se llenaron, para no dejar un hueco vacío en empresas que\n    no los hayan configurado."""\n    texto = ctx.get("datos_pago")\n    if not texto:\n        return False\n    elementos.append(Paragraph("Cómo pagar", styles["Seccion"]))\n    texto_html = (\n        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\\n", "<br/>")\n    )\n    elementos.append(Paragraph(texto_html, styles["Cuerpo"]))\n    return True',
        ],
        [
            '_FUNCIONES_BLOQUES = {\n    "cliente": _bloque_cliente,\n    "tabla_articulos": _bloque_tabla_articulos,\n    "precio_contado": _bloque_precio_contado,\n    "total": _bloque_total,\n    "meses_msi": _bloque_meses_msi,\n    "notas": _bloque_notas,\n    "contacto": _bloque_contacto,\n    "vigencia": _bloque_vigencia,\n}',
            '_FUNCIONES_BLOQUES = {\n    "cliente": _bloque_cliente,\n    "tabla_articulos": _bloque_tabla_articulos,\n    "precio_contado": _bloque_precio_contado,\n    "total": _bloque_total,\n    "datos_pago": _bloque_datos_pago,\n    "meses_msi": _bloque_meses_msi,\n    "notas": _bloque_notas,\n    "contacto": _bloque_contacto,\n    "vigencia": _bloque_vigencia,\n}',
        ],
        [
            '        "msi": calcular_msi(cotizacion),\n        "padding_filas_tabla": diseno["padding_filas_tabla"],\n    }',
            '        "msi": calcular_msi(cotizacion),\n        "padding_filas_tabla": diseno["padding_filas_tabla"],\n        "datos_pago": (empresa or {}).get("datos_pago_cotizacion"),\n    }',
        ],
        [
            'def _escapar_html(texto):\n    return (\n        (texto or "")\n        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")\n        .replace(\'"\', "&quot;")\n    )\n\n\ndef _fmt_cant(n):\n    n = float(n or 0)\n    return f"{n:g}"\n\n\ndef generar_html_recibo_termico(cotizacion):\n    """Recibo angosto (58mm) para la impresora térmica Star SM-L200, servido\n    en la ruta pública que la app Star PassPRNT consulta directamente (no\n    lleva sesión ni token de la app — por eso nunca incluye datos sensibles\n    de más, solo lo mismo que ya trae la cotización). Se evitan caracteres\n    tipográficos poco comunes (guion en vez de punto medio, etc.) por si la\n    fuente de la impresora no los trae."""\n    filas = ""\n    total = 0.0\n    for item in cotizacion["items"]:\n        cantidad = float(item["cantidad"])\n        precio = float(item["precio_unitario"])\n        descuento_pct = float(item.get("descuento_pct") or 0)\n        subtotal = cantidad * precio * (1 - descuento_pct / 100)\n        total += subtotal\n        clave = f" ({_escapar_html(item[\'clave\'])})" if item.get("clave") else ""\n        desc = f" (-{descuento_pct:g}%)" if descuento_pct else ""\n        filas += f"""\n          <tr>\n            <td style="text-align:left; padding:3px 0;">{_escapar_html(item[\'nombre\'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}{desc}</td>\n            <td style="text-align:right; white-space:nowrap; padding:3px 0;">{_fmt_dinero(subtotal)}</td>\n          </tr>\n        """\n    telefono = f"<br>Tel: {_escapar_html(cotizacion[\'cliente_telefono\'])}" if cotizacion.get("cliente_telefono") else ""\n    return f"""<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Cotizacion {_escapar_html(cotizacion[\'folio\'])}</title><style>\n  body {{ width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }}\n  h1 {{ font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }}\n  .centro {{ text-align:center; margin:2px 0; }}\n  .linea {{ border-top:1px dashed #000; margin:8px 0; }}\n  table {{ width:100%; border-collapse:collapse; }}\n  .total td {{ font-size:15px; font-weight:bold; padding-top:6px; }}\n</style></head><body>\n  <h1>MARK - INC</h1>\n  <p class="centro">Cotizacion {_escapar_html(cotizacion[\'folio\'])}</p>\n  <div class="linea"></div>\n  <p><b>Cliente:</b> {_escapar_html(cotizacion[\'cliente_nombre\'])}{telefono}</p>\n  <div class="linea"></div>\n  <table>{filas}</table>\n  <div class="linea"></div>\n  <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">{_fmt_dinero(total)}</td></tr></table>\n  <div class="linea"></div>\n  <p class="centro" style="font-size:10px;">Cotizacion informativa, sujeta a cambios.<br>Vigencia 15 dias.</p>\n</body></html>"""\n\n\ndef _escapar_html(texto):\n    return (\n        (texto or "")\n        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")\n        .replace(\'"\', "&quot;")\n    )\n\n\ndef _fmt_cant(n):\n    n = float(n or 0)\n    return f"{n:g}"\n\n\ndef generar_html_recibo_termico(cotizacion):\n    """Recibo angosto (58mm) para la impresora térmica Star SM-L200, servido\n    en la ruta pública que la app Star PassPRNT consulta directamente (no\n    lleva sesión ni token de la app — por eso nunca incluye datos sensibles\n    de más, solo lo mismo que ya trae la cotización). Se evitan caracteres\n    tipográficos poco comunes (guion en vez de punto medio, etc.) por si la\n    fuente de la impresora no los trae."""\n    filas = ""\n    total = 0.0\n    for item in cotizacion["items"]:\n        cantidad = float(item["cantidad"])\n        precio = float(item["precio_unitario"])\n        subtotal = cantidad * precio\n        total += subtotal\n        clave = f" ({_escapar_html(item[\'clave\'])})" if item.get("clave") else ""\n        filas += f"""\n          <tr>\n            <td style="text-align:left; padding:3px 0;">{_escapar_html(item[\'nombre\'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}</td>\n            <td style="text-align:right; white-space:nowrap; padding:3px 0;">{_fmt_dinero(subtotal)}</td>\n          </tr>\n        """\n    telefono = f"<br>Tel: {_escapar_html(cotizacion[\'cliente_telefono\'])}" if cotizacion.get("cliente_telefono") else ""\n    return f"""<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Cotizacion {_escapar_html(cotizacion[\'folio\'])}</title><style>\n  body {{ width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }}\n  h1 {{ font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }}\n  .centro {{ text-align:center; margin:2px 0; }}\n  .linea {{ border-top:1px dashed #000; margin:8px 0; }}\n  table {{ width:100%; border-collapse:collapse; }}\n  .total td {{ font-size:15px; font-weight:bold; padding-top:6px; }}\n</style></head><body>\n  <h1>MARK - INC</h1>\n  <p class="centro">Cotizacion {_escapar_html(cotizacion[\'folio\'])}</p>\n  <div class="linea"></div>\n  <p><b>Cliente:</b> {_escapar_html(cotizacion[\'cliente_nombre\'])}{telefono}</p>\n  <div class="linea"></div>\n  <table>{filas}</table>\n  <div class="linea"></div>\n  <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">{_fmt_dinero(total)}</td></tr></table>\n  <div class="linea"></div>\n  <p class="centro" style="font-size:10px;">Cotizacion informativa, sujeta a cambios.<br>Vigencia 15 dias.</p>\n</body></html>"""\n',
            'def _escapar_html(texto):\n    return (\n        (texto or "")\n        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")\n        .replace(\'"\', "&quot;")\n    )\n\n\ndef _fmt_cant(n):\n    n = float(n or 0)\n    return f"{n:g}"\n\n\ndef generar_html_recibo_termico(cotizacion, datos_pago=None):\n    """Recibo angosto (58mm) para la impresora térmica Star SM-L200, servido\n    en la ruta pública que la app Star PassPRNT consulta directamente (no\n    lleva sesión ni token de la app — por eso nunca incluye datos sensibles\n    de más, solo lo mismo que ya trae la cotización). Se evitan caracteres\n    tipográficos poco comunes (guion en vez de punto medio, etc.) por si la\n    fuente de la impresora no los trae."""\n    filas = ""\n    total = 0.0\n    for item in cotizacion["items"]:\n        cantidad = float(item["cantidad"])\n        precio = float(item["precio_unitario"])\n        descuento_pct = float(item.get("descuento_pct") or 0)\n        subtotal = cantidad * precio * (1 - descuento_pct / 100)\n        total += subtotal\n        clave = f" ({_escapar_html(item[\'clave\'])})" if item.get("clave") else ""\n        desc = f" (-{descuento_pct:g}%)" if descuento_pct else ""\n        filas += f"""\n          <tr>\n            <td style="text-align:left; padding:3px 0;">{_escapar_html(item[\'nombre\'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}{desc}</td>\n            <td style="text-align:right; white-space:nowrap; padding:3px 0;">{_fmt_dinero(subtotal)}</td>\n          </tr>\n        """\n    # Igual que en el PDF: el precio de los artículos ya incluye el 16% de\n    # IVA, así que aquí solo se desglosa el total ya conocido — no se le\n    # suma nada encima.\n    subtotal_sin_iva = total / 1.16\n    iva = total - subtotal_sin_iva\n    telefono = f"<br>Tel: {_escapar_html(cotizacion[\'cliente_telefono\'])}" if cotizacion.get("cliente_telefono") else ""\n    pago_html = ""\n    if datos_pago:\n        datos_pago_html = _escapar_html(datos_pago).replace(chr(10), "<br>")\n        pago_html = f"""\n  <div class="linea"></div>\n  <p style="font-size:11px;"><b>Como pagar:</b><br>{datos_pago_html}</p>\n        """\n    return f"""<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Cotizacion {_escapar_html(cotizacion[\'folio\'])}</title><style>\n  body {{ width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }}\n  h1 {{ font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }}\n  .centro {{ text-align:center; margin:2px 0; }}\n  .linea {{ border-top:1px dashed #000; margin:8px 0; }}\n  table {{ width:100%; border-collapse:collapse; }}\n  .total td {{ font-size:15px; font-weight:bold; padding-top:6px; }}\n</style></head><body>\n  <h1>MARK - INC</h1>\n  <p class="centro">Cotizacion {_escapar_html(cotizacion[\'folio\'])}</p>\n  <div class="linea"></div>\n  <p><b>Cliente:</b> {_escapar_html(cotizacion[\'cliente_nombre\'])}{telefono}</p>\n  <div class="linea"></div>\n  <table>{filas}</table>\n  <div class="linea"></div>\n  <table>\n    <tr><td>Subtotal</td><td style="text-align:right;">{_fmt_dinero(subtotal_sin_iva)}</td></tr>\n    <tr><td>IVA (16%)</td><td style="text-align:right;">{_fmt_dinero(iva)}</td></tr>\n    <tr class="total"><td>TOTAL</td><td style="text-align:right;">{_fmt_dinero(total)}</td></tr>\n  </table>\n  {pago_html}\n  <div class="linea"></div>\n  <p class="centro" style="font-size:10px;">Cotizacion informativa, sujeta a cambios.<br>Vigencia 15 dias.</p>\n</body></html>"""\n',
        ],
    ],
    'frontend/index.html': [
        [
            '        <button class="secondary" onclick="abrirModulosEmpresa(${e.id})">Módulos</button>\n        <button class="secondary" onclick="abrirCostosEmpresa(${e.id})">🧾 Cotización</button>',
            '        <button class="secondary" onclick="abrirModulosEmpresa(${e.id})">Módulos</button>\n        <button class="secondary" onclick="abrirDatosPagoEmpresa(${e.id})">💳 Datos de pago</button>\n        <button class="secondary" onclick="abrirCostosEmpresa(${e.id})">🧾 Cotización</button>',
        ],
        [
            "async function guardarModulosEmpresa(id) {\n  const payload = {};\n  MODULOS_EMPRESA_CONFIG.filter(m => !m.siempre).forEach(m => {\n    payload[m.clave] = document.getElementById(`mod_${m.clave}`).checked;\n  });\n  try {\n    await api(`/api/empresas/${id}/modulos`, { method: 'PATCH', body: JSON.stringify(payload) });\n    cerrarModal();\n    await cargarEmpresas();\n  } catch (e) {\n    document.getElementById('modulosEmpresaError').textContent = e.message;\n  }\n}",
            'async function guardarModulosEmpresa(id) {\n  const payload = {};\n  MODULOS_EMPRESA_CONFIG.filter(m => !m.siempre).forEach(m => {\n    payload[m.clave] = document.getElementById(`mod_${m.clave}`).checked;\n  });\n  try {\n    await api(`/api/empresas/${id}/modulos`, { method: \'PATCH\', body: JSON.stringify(payload) });\n    cerrarModal();\n    await cargarEmpresas();\n  } catch (e) {\n    document.getElementById(\'modulosEmpresaError\').textContent = e.message;\n  }\n}\n\nfunction abrirDatosPagoEmpresa(id) {\n  const empresa = EMPRESAS_CACHE.find(e => e.id === id);\n  if (!empresa) return;\n  document.getElementById(\'modalContent\').innerHTML = `\n    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n    <h2>Datos de pago de ${escapeHtml(empresa.nombre)}</h2>\n    <p style="font-size:12px; color:var(--muted);">\n      Si los llenas, aparecen como una sección aparte ("Cómo pagar") en el PDF de cada cotización de esta empresa,\n      justo después del total — ej. banco, número de cuenta, CLABE. Déjalo vacío para no mostrar nada.\n    </p>\n    <div class="field">\n      <textarea id="datos_pago_empresa" rows="5" placeholder="Ej. BBVA, cuenta 0123456789, CLABE 012345678901234567, a nombre de Mark Inc">${empresa.datos_pago_cotizacion ? escapeHtml(empresa.datos_pago_cotizacion) : \'\'}</textarea>\n    </div>\n    <button class="primary" style="width:100%; margin-top:10px;" onclick="conBloqueoDeBoton(this, () => guardarDatosPagoEmpresa(${id}))">Guardar</button>\n    <div id="datosPagoEmpresaError" class="error-msg"></div>\n  `;\n  abrirModal();\n}\n\nasync function guardarDatosPagoEmpresa(id) {\n  const texto = document.getElementById(\'datos_pago_empresa\').value.trim();\n  try {\n    await api(`/api/empresas/${id}`, { method: \'PATCH\', body: JSON.stringify({ datos_pago_cotizacion: texto }) });\n    cerrarModal();\n    await cargarEmpresas();\n  } catch (e) {\n    document.getElementById(\'datosPagoEmpresaError\').textContent = e.message;\n  }\n}',
        ],
        [
            '      <div style="text-align:right; margin-top:8px;">\n        <p style="font-size:12px; color:var(--muted); margin:0;">Precio sin descuento: <span id="cot_total_sin_descuento">$${cot_fmt(cot_totalSinDescuento())}</span></p>\n        <p style="font-size:16px; margin:2px 0 0;"><b>Precio con descuento: <span id="cot_total">$${cot_fmt(cot_total())}</span></b></p>\n      </div>',
            '      <div style="text-align:right; margin-top:8px;">\n        <p style="font-size:12px; color:var(--muted); margin:0;">Precio sin descuento: <span id="cot_total_sin_descuento">$${cot_fmt(cot_totalSinDescuento())}</span></p>\n        <p style="font-size:16px; margin:2px 0 0;"><b>Precio con descuento: <span id="cot_total">$${cot_fmt(cot_total())}</span></b></p>\n        <p style="font-size:11px; color:var(--muted); margin:6px 0 0;">Subtotal: <span id="cot_subtotal_sin_iva">$${cot_fmt(cot_total() / 1.16)}</span> &nbsp;+&nbsp; IVA (16%): <span id="cot_iva">$${cot_fmt(cot_total() - cot_total() / 1.16)}</span></p>\n      </div>',
        ],
        [
            "  const totalEl = document.getElementById('cot_total');\n  if (totalEl) totalEl.textContent = '$' + cot_fmt(cot_total());\n  const totalSinDescEl = document.getElementById('cot_total_sin_descuento');\n  if (totalSinDescEl) totalSinDescEl.textContent = '$' + cot_fmt(cot_totalSinDescuento());\n}",
            "  const totalEl = document.getElementById('cot_total');\n  if (totalEl) totalEl.textContent = '$' + cot_fmt(cot_total());\n  const totalSinDescEl = document.getElementById('cot_total_sin_descuento');\n  if (totalSinDescEl) totalSinDescEl.textContent = '$' + cot_fmt(cot_totalSinDescuento());\n  const subtotalSinIvaEl = document.getElementById('cot_subtotal_sin_iva');\n  const ivaEl = document.getElementById('cot_iva');\n  if (subtotalSinIvaEl && ivaEl) {\n    const totalConIva = cot_total();\n    const subtotalSinIva = totalConIva / 1.16;\n    subtotalSinIvaEl.textContent = '$' + cot_fmt(subtotalSinIva);\n    ivaEl.textContent = '$' + cot_fmt(totalConIva - subtotalSinIva);\n  }\n}",
        ],
    ],
}


def main():
    cambios_totales = 0
    for ruta, hunks in ARCHIVOS.items():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
        except FileNotFoundError:
            print(f"ERROR: no se encontro {ruta} -- corre este script desde la raiz del repo tickets-ti.")
            sys.exit(1)

        original = contenido
        cambios_archivo = 0
        for viejo, nuevo in hunks:
            if nuevo in contenido:
                continue  # ya aplicado antes -- idempotente
            if viejo not in contenido:
                print(f"ERROR: no se encontro el texto esperado en {ruta}.")
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
                print("--- fragmento esperado ---")
                print(viejo[:300])
                sys.exit(1)
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios_archivo += 1

        if contenido != original:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: {ruta} -- {cambios_archivo} cambio(s) aplicado(s).")
            cambios_totales += cambios_archivo
        else:
            print(f"(sin cambios) {ruta} -- ya estaba aplicado.")

    if cambios_totales == 0:
        print()
        print("No habia nada nuevo que aplicar (el parche ya estaba puesto).")
    else:
        print()
        print(f"{cambios_totales} cambio(s) aplicado(s) en total.")

    print()
    print("Ahora corre esto para subirlo:")
    print()
    print("    git add backend/db.py backend/app.py backend/pdfs_cotizaciones.py frontend/index.html")
    print('    git commit -m "Cotizador: desglose Subtotal/IVA/Total y datos de pago por empresa desde superadmin"')
    print("    git push")


if __name__ == "__main__":
    main()
