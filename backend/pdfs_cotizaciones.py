"""Generación del PDF de una cotización (módulo Cotizador, dentro de
Checador de precio) — mismo estilo membretado que los documentos de
Reparaciones."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable

from pdfs_reparaciones import (
    ROJO, GRIS, GRIS_CLARO, NEGRO, _styles, _encabezado_membretado, _pie_pagina,
    _formatear_fecha, _doc_template,
)


def _fmt_dinero(n):
    n = float(n or 0)
    return f"${n:,.2f}"


def generar_cotizacion_pdf(cotizacion, empresa):
    styles = _styles()
    elementos = []
    _encabezado_membretado(
        elementos, styles, "COTIZACIÓN",
        folio=cotizacion["folio"],
        fecha=f"Fecha: {_formatear_fecha(cotizacion.get('creado_en'))}",
        etiqueta_folio="Folio",
    )

    elementos.append(Paragraph("Cliente", styles["Seccion"]))
    datos_cliente = [("Nombre", cotizacion.get("cliente_nombre"))]
    if cotizacion.get("cliente_telefono"):
        datos_cliente.append(("Teléfono", cotizacion["cliente_telefono"]))
    if cotizacion.get("cliente_direccion"):
        datos_cliente.append(("Dirección", cotizacion["cliente_direccion"]))
    for etiqueta, valor in datos_cliente:
        elementos.append(Paragraph(f"<b>{etiqueta}:</b> {valor or '—'}", styles["Cuerpo"]))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("Artículos cotizados", styles["Seccion"]))

    estilo_celda = ParagraphStyle("CeldaTabla", parent=styles["Normal"], fontSize=9, leading=12)
    estilo_celda_num = ParagraphStyle("CeldaTablaNum", parent=estilo_celda, alignment=2)
    filas = [[
        Paragraph("<b>Artículo</b>", estilo_celda),
        Paragraph("<b>Cant.</b>", estilo_celda_num),
        Paragraph("<b>Precio unit.</b>", estilo_celda_num),
        Paragraph("<b>Subtotal</b>", estilo_celda_num),
    ]]
    total = 0.0
    for item in cotizacion["items"]:
        cantidad = float(item["cantidad"])
        precio = float(item["precio_unitario"])
        subtotal = cantidad * precio
        total += subtotal
        nombre = item["nombre"] + (f" <font size=7 color='#74767A'>(clave: {item['clave']})</font>" if item.get("clave") else "")
        filas.append([
            Paragraph(nombre, estilo_celda),
            Paragraph(f"{cantidad:g}", estilo_celda_num),
            Paragraph(_fmt_dinero(precio), estilo_celda_num),
            Paragraph(_fmt_dinero(subtotal), estilo_celda_num),
        ])

    tabla = Table(filas, colWidths=[8.8 * cm, 1.8 * cm, 2.7 * cm, 2.7 * cm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROJO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS),
    ]))
    elementos.append(tabla)

    elementos.append(Spacer(1, 6))
    tabla_total = Table([[
        Paragraph("<b>TOTAL</b>", ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)),
        Paragraph(f"<b>{_fmt_dinero(total)}</b>", ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)),
    ]], colWidths=[13.3 * cm, 2.7 * cm])
    tabla_total.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabla_total)

    if cotizacion.get("notas"):
        elementos.append(Spacer(1, 14))
        elementos.append(Paragraph("Notas", styles["Seccion"]))
        elementos.append(Paragraph(cotizacion["notas"], styles["Cuerpo"]))

    elementos.append(Spacer(1, 20))
    elementos.append(HRFlowable(width="100%", thickness=0.8, color=GRIS, spaceBefore=4, spaceAfter=8))
    elementos.append(Paragraph(
        "Esta cotización es informativa y no representa una factura. Precios sujetos a cambio sin previo aviso; "
        "vigencia de 15 días naturales salvo que se indique lo contrario.",
        ParagraphStyle("Vigencia", parent=styles["Normal"], fontSize=7.5, textColor=GRIS),
    ))

    buffer = BytesIO()
    documento = _doc_template(buffer)
    documento.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buffer.seek(0)
    return buffer.read()
