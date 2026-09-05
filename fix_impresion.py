# -*- coding: utf-8 -*-
"""
Agrega la impresion de cotizaciones en 2 formas:
1. PDF con logo (boton "Descargar PDF").
2. Bluetooth a tu impresora Star SM-L200, via la app oficial gratuita
   "Star PassPRNT" (App Store / Play Store) -- boton "Imprimir en Star".
   IMPORTANTE: la SM-L200 no habla ESC/POS, solo su protocolo propio
   StarPRNT, por eso se usa PassPRNT en vez de mandarle un PDF directo.
   Necesitas: 1) instalar la app "Star PassPRNT" en el celular/tableta que
   use la app, 2) emparejar la impresora por Bluetooth en los ajustes del
   sistema (una sola vez). Despues, el boton "Imprimir en Star" abre
   PassPRNT solo, listo para imprimir.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_impresion.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['import pdfs_reparaciones\nimport pdfs_rh\nimport pdfs_equipos', 'import pdfs_reparaciones\nimport pdfs_rh\nimport pdfs_equipos\nimport pdfs_cotizaciones'], ['@app.get("/api/cotizaciones/{cotizacion_id}")\ndef api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return cotizacion', '@app.get("/api/cotizaciones/{cotizacion_id}")\ndef api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return cotizacion\n\n\n@app.get("/api/cotizaciones/{cotizacion_id}/pdf")\ndef api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    empresa = db.obtener_empresa(usuario["empresa_id"])\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa)\n    return Response(content=pdf_bytes, media_type="application/pdf",\n                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion[\'folio\']}.pdf"})']], 'backend/pdfs_reparaciones.py': [['def _encabezado_membretado(elementos, styles, titulo, folio=None, fecha=None):', 'def _encabezado_membretado(elementos, styles, titulo, folio=None, fecha=None, etiqueta_folio="Orden de servicio"):'], ['        elementos.append(Paragraph(f"Orden de servicio: <b>{folio}</b>", styles["FolioRojo"]))', '        elementos.append(Paragraph(f"{etiqueta_folio}: <b>{folio}</b>", styles["FolioRojo"]))']], 'frontend/index.html': [['function renderCotizadorForm() {\n  const c = COT_ACTUAL;\n  document.getElementById(\'checadorPrecioContenido\').innerHTML = `\n    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">\n      <h3 style="margin:0;">${c.id ? `Editando ${escapeHtml(c.folio)}` : \'Nueva cotización\'}</h3>\n      ${c.id ? \'<button class="secondary" onclick="renderCotizadorNueva()">+ Nueva cotización</button>\' : \'\'}\n    </div>\n', 'function renderCotizadorForm() {\n  const c = COT_ACTUAL;\n  document.getElementById(\'checadorPrecioContenido\').innerHTML = `\n    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">\n      <h3 style="margin:0;">${c.id ? `Editando ${escapeHtml(c.folio)}` : \'Nueva cotización\'}</h3>\n      ${c.id ? \'<button class="secondary" onclick="renderCotizadorNueva()">+ Nueva cotización</button>\' : \'\'}\n    </div>\n    ${c.id ? `\n      <div style="display:flex; gap:8px; margin-bottom:16px;">\n        <button class="secondary" style="flex:1;" onclick="cot_descargarPdfActual()">📄 Descargar PDF</button>\n        <button class="secondary" style="flex:1;" onclick="cot_imprimirBluetoothActual()">🖨️ Imprimir en Star (Bluetooth)</button>\n      </div>\n    ` : \'\'}\n\n'], ['            <td style="white-space:nowrap;">\n              <button class="secondary" style="padding:4px 8px;" onclick="cot_editarCotizacion(${c.id})">Ver / editar</button>\n              <button class="secondary" style="padding:4px 8px; color:var(--copper); border-color:var(--copper);" onclick="cot_eliminarCotizacionUI(${c.id}, this)">Eliminar</button>\n            </td>', '            <td style="white-space:nowrap;">\n              <button class="secondary" style="padding:4px 8px;" onclick="cot_editarCotizacion(${c.id})">Ver / editar</button>\n              <button class="secondary" style="padding:4px 8px;" onclick="cot_descargarPdfLista(${c.id}, \'${escapeHtml(c.folio)}\')">📄 PDF</button>\n              <button class="secondary" style="padding:4px 8px;" onclick="cot_imprimirBluetoothLista(${c.id})">🖨️ Star</button>\n              <button class="secondary" style="padding:4px 8px; color:var(--copper); border-color:var(--copper);" onclick="cot_eliminarCotizacionUI(${c.id}, this)">Eliminar</button>\n            </td>'], ['// ---- Cotizaciones realizadas ----\n', '// ---- Imprimir cotización: PDF con logo, o Bluetooth (Star SM-L200 vía PassPRNT) ----\n//\n// El SM-L200 NO habla ESC/POS, solo su protocolo propio StarPRNT — por eso no\n// se le puede mandar un PDF directo. Se usa la app gratuita oficial "Star\n// PassPRNT" (App Store / Play Store), que cualquier navegador puede invocar\n// con una liga especial (starpassprnt://) mandándole el recibo ya armado en\n// HTML; PassPRNT se encarga de la parte de Bluetooth con la impresora, ya\n// emparejada de antemano en los ajustes del teléfono/tableta.\n\nasync function cot_descargarPdfLista(id, folio) {\n  try {\n    const r = await fetch(`/api/cotizaciones/${id}/pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error(\'No se pudo generar el PDF\');\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement(\'a\');\n    a.href = url;\n    a.download = `cotizacion_${folio}.pdf`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nfunction cot_descargarPdfActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  cot_descargarPdfLista(COT_ACTUAL.id, COT_ACTUAL.folio);\n}\n\nfunction cot_construirHtmlRecibo(c) {\n  const total = c.items.reduce((s, it) => s + (Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0), 0);\n  const filas = c.items.map(it => `\n    <tr>\n      <td style="text-align:left; padding:3px 0;">${escapeHtml(it.nombre)}${it.clave ? ` (${escapeHtml(it.clave)})` : \'\'}<br>${it.cantidad} x $${cot_fmt(it.precio_unitario)}</td>\n      <td style="text-align:right; white-space:nowrap; padding:3px 0;">$${cot_fmt((Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0))}</td>\n    </tr>\n  `).join(\'\');\n  return `<html><head><meta charset="utf-8"><style>\n    body { width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }\n    h1 { font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }\n    .centro { text-align:center; margin:2px 0; }\n    .linea { border-top:1px dashed #000; margin:8px 0; }\n    table { width:100%; border-collapse:collapse; }\n    .total td { font-size:15px; font-weight:bold; padding-top:6px; }\n  </style></head><body>\n    <h1>MARK · INC</h1>\n    <p class="centro">Cotización ${escapeHtml(c.folio)}</p>\n    <div class="linea"></div>\n    <p><b>Cliente:</b> ${escapeHtml(c.cliente_nombre)}${c.cliente_telefono ? `<br>Tel: ${escapeHtml(c.cliente_telefono)}` : \'\'}</p>\n    <div class="linea"></div>\n    <table>${filas}</table>\n    <div class="linea"></div>\n    <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">$${cot_fmt(total)}</td></tr></table>\n    <div class="linea"></div>\n    <p class="centro" style="font-size:10px;">Cotización informativa, sujeta a cambios.<br>Vigencia 15 días.</p>\n  </body></html>`;\n}\n\nfunction cot_abrirPassPRNT(c) {\n  const html = cot_construirHtmlRecibo(c);\n  const uri = `starpassprnt://v1/print/nopreview?back=${encodeURIComponent(window.location.href)}&html=${encodeURIComponent(html)}`;\n  window.location.href = uri;\n}\n\nasync function cot_imprimirBluetoothLista(id) {\n  try {\n    const c = await api(`/api/cotizaciones/${id}`);\n    cot_abrirPassPRNT(c);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nfunction cot_imprimirBluetoothActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  cot_sincronizarDesdeInputs();\n  cot_abrirPassPRNT(COT_ACTUAL);\n}\n\n// ---- Cotizaciones realizadas ----\n']]}

PDFS_COTIZACIONES_CONTENIDO = '"""Generación del PDF de una cotización (módulo Cotizador, dentro de\nChecador de precio) — mismo estilo membretado que los documentos de\nReparaciones."""\nfrom io import BytesIO\n\nfrom reportlab.lib import colors\nfrom reportlab.lib.pagesizes import letter\nfrom reportlab.lib.styles import ParagraphStyle\nfrom reportlab.lib.units import cm\nfrom reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable\n\nfrom pdfs_reparaciones import (\n    ROJO, GRIS, GRIS_CLARO, NEGRO, _styles, _encabezado_membretado, _pie_pagina,\n    _formatear_fecha, _doc_template,\n)\n\n\ndef _fmt_dinero(n):\n    n = float(n or 0)\n    return f"${n:,.2f}"\n\n\ndef generar_cotizacion_pdf(cotizacion, empresa):\n    styles = _styles()\n    elementos = []\n    _encabezado_membretado(\n        elementos, styles, "COTIZACIÓN",\n        folio=cotizacion["folio"],\n        fecha=f"Fecha: {_formatear_fecha(cotizacion.get(\'creado_en\'))}",\n        etiqueta_folio="Folio",\n    )\n\n    elementos.append(Paragraph("Cliente", styles["Seccion"]))\n    datos_cliente = [("Nombre", cotizacion.get("cliente_nombre"))]\n    if cotizacion.get("cliente_telefono"):\n        datos_cliente.append(("Teléfono", cotizacion["cliente_telefono"]))\n    if cotizacion.get("cliente_direccion"):\n        datos_cliente.append(("Dirección", cotizacion["cliente_direccion"]))\n    for etiqueta, valor in datos_cliente:\n        elementos.append(Paragraph(f"<b>{etiqueta}:</b> {valor or \'—\'}", styles["Cuerpo"]))\n\n    elementos.append(Spacer(1, 10))\n    elementos.append(Paragraph("Artículos cotizados", styles["Seccion"]))\n\n    estilo_celda = ParagraphStyle("CeldaTabla", parent=styles["Normal"], fontSize=9, leading=12)\n    estilo_celda_num = ParagraphStyle("CeldaTablaNum", parent=estilo_celda, alignment=2)\n    filas = [[\n        Paragraph("<b>Artículo</b>", estilo_celda),\n        Paragraph("<b>Cant.</b>", estilo_celda_num),\n        Paragraph("<b>Precio unit.</b>", estilo_celda_num),\n        Paragraph("<b>Subtotal</b>", estilo_celda_num),\n    ]]\n    total = 0.0\n    for item in cotizacion["items"]:\n        cantidad = float(item["cantidad"])\n        precio = float(item["precio_unitario"])\n        subtotal = cantidad * precio\n        total += subtotal\n        nombre = item["nombre"] + (f" <font size=7 color=\'#74767A\'>(clave: {item[\'clave\']})</font>" if item.get("clave") else "")\n        filas.append([\n            Paragraph(nombre, estilo_celda),\n            Paragraph(f"{cantidad:g}", estilo_celda_num),\n            Paragraph(_fmt_dinero(precio), estilo_celda_num),\n            Paragraph(_fmt_dinero(subtotal), estilo_celda_num),\n        ])\n\n    tabla = Table(filas, colWidths=[8.8 * cm, 1.8 * cm, 2.7 * cm, 2.7 * cm], repeatRows=1)\n    tabla.setStyle(TableStyle([\n        ("BACKGROUND", (0, 0), (-1, 0), ROJO),\n        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),\n        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),\n        ("TOPPADDING", (0, 0), (-1, -1), 6),\n        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),\n        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),\n        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS),\n    ]))\n    elementos.append(tabla)\n\n    elementos.append(Spacer(1, 6))\n    tabla_total = Table([[\n        Paragraph("<b>TOTAL</b>", ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)),\n        Paragraph(f"<b>{_fmt_dinero(total)}</b>", ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)),\n    ]], colWidths=[13.3 * cm, 2.7 * cm])\n    tabla_total.setStyle(TableStyle([\n        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n        ("TOPPADDING", (0, 0), (-1, -1), 8),\n    ]))\n    elementos.append(tabla_total)\n\n    if cotizacion.get("notas"):\n        elementos.append(Spacer(1, 14))\n        elementos.append(Paragraph("Notas", styles["Seccion"]))\n        elementos.append(Paragraph(cotizacion["notas"], styles["Cuerpo"]))\n\n    elementos.append(Spacer(1, 20))\n    elementos.append(HRFlowable(width="100%", thickness=0.8, color=GRIS, spaceBefore=4, spaceAfter=8))\n    elementos.append(Paragraph(\n        "Esta cotización es informativa y no representa una factura. Precios sujetos a cambio sin previo aviso; "\n        "vigencia de 15 días naturales salvo que se indique lo contrario.",\n        ParagraphStyle("Vigencia", parent=styles["Normal"], fontSize=7.5, textColor=GRIS),\n    ))\n\n    buffer = BytesIO()\n    documento = _doc_template(buffer)\n    documento.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)\n    buffer.seek(0)\n    return buffer.read()\n'


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


def crear_pdfs_cotizaciones():
    ruta = "backend/pdfs_cotizaciones.py"
    import os
    if os.path.exists(ruta):
        actual = leer(ruta)
        if actual.strip() == PDFS_COTIZACIONES_CONTENIDO.strip():
            print(f"[{ruta}] Ya existe y esta correcto. No hace falta nada.")
            return True
    escribir(ruta, PDFS_COTIZACIONES_CONTENIDO)
    print(f"[{ruta}] Archivo creado.")
    return True


def main():
    ok = True
    ok = crear_pdfs_cotizaciones() and ok
    ok = aplicar_reemplazos("backend/app.py") and ok
    ok = aplicar_reemplazos("backend/pdfs_reparaciones.py") and ok
    ok = aplicar_reemplazos("frontend/index.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py backend/pdfs_reparaciones.py backend/pdfs_cotizaciones.py frontend/index.html")
    print('   git commit -m "Imprimir cotizacion: PDF con logo, y Bluetooth a impresora Star via PassPRNT"')
    print("   git push")


if __name__ == "__main__":
    main()
