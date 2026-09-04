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


def calcular_msi(cotizacion):
    """Meses sin intereses: a 6 meses se cobra el costo íntegro SIN los
    descuentos por artículo (el descuento no aplica si se difiere a meses);
    por cada mes arriba de 6 se suma 1% de recargo sobre ese mismo costo
    íntegro (ej. a 9 meses = 3% de recargo, por los 3 meses arriba del 6º)."""
    meses = cotizacion.get("meses_msi")
    if not meses or meses <= 0:
        return None
    total_bruto = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])
    recargo_pct = max(0, meses - 6) * 1
    total_msi = total_bruto * (1 + recargo_pct / 100)
    return {
        "meses": meses,
        "total_bruto": total_bruto,
        "recargo_pct": recargo_pct,
        "total_msi": total_msi,
        "mensualidad": total_msi / meses,
    }


TITULOS_TIPO_CLIENTE = {
    "publico": "COTIZACIÓN PÚBLICO EN GENERAL",
    "mayoreo": "COTIZACIÓN MAYOREO",
    "distribuidor": "COTIZACIÓN DISTRIBUIDOR",
}


def generar_cotizacion_pdf(cotizacion, empresa):
    styles = _styles()
    elementos = []
    titulo = TITULOS_TIPO_CLIENTE.get(cotizacion.get("tipo_cliente"), "COTIZACIÓN")
    _encabezado_membretado(
        elementos, styles, titulo,
        folio=cotizacion["folio"],
        fecha=f"Fecha: {_formatear_fecha(cotizacion.get('creado_en'))}",
        etiqueta_folio="Folio",
    )

    elementos.append(Paragraph("Cliente", styles["Seccion"]))
    elementos.append(Paragraph(f"<b>Nombre:</b> {cotizacion.get('cliente_nombre') or '—'}", styles["Cuerpo"]))
    # Teléfono y Dirección se combinan en un solo renglón (si ambos existen)
    # para no gastar una línea completa por cada uno.
    contacto_cliente = []
    if cotizacion.get("cliente_telefono"):
        contacto_cliente.append(f"<b>Teléfono:</b> {cotizacion['cliente_telefono']}")
    if cotizacion.get("cliente_direccion"):
        contacto_cliente.append(f"<b>Dirección:</b> {cotizacion['cliente_direccion']}")
    if contacto_cliente:
        elementos.append(Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(contacto_cliente), styles["Cuerpo"]))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("Artículos cotizados", styles["Seccion"]))

    estilo_celda = ParagraphStyle("CeldaTabla", parent=styles["Normal"], fontSize=9, leading=12)
    estilo_celda_num = ParagraphStyle("CeldaTablaNum", parent=estilo_celda, alignment=2)
    estilo_nota = ParagraphStyle("NotaItem", parent=estilo_celda, fontSize=7.5, textColor=GRIS, leftIndent=2)
    hay_descuentos = any(float(item.get("descuento_pct") or 0) > 0 for item in cotizacion["items"])
    encabezado = [
        Paragraph("<b>Artículo</b>", estilo_celda),
        Paragraph("<b>Cant.</b>", estilo_celda_num),
        Paragraph("<b>Precio unit.</b>", estilo_celda_num),
    ]
    if hay_descuentos:
        encabezado.append(Paragraph("<b>Desc.</b>", estilo_celda_num))
    encabezado.append(Paragraph("<b>Subtotal</b>", estilo_celda_num))
    filas = [encabezado]
    total = 0.0
    for item in cotizacion["items"]:
        cantidad = float(item["cantidad"])
        precio = float(item["precio_unitario"])
        descuento_pct = float(item.get("descuento_pct") or 0)
        subtotal = cantidad * precio * (1 - descuento_pct / 100)
        total += subtotal
        nombre = item["nombre"] + (f" <font size=7 color='#74767A'>(clave: {item['clave']})</font>" if item.get("clave") else "")
        if item.get("nota"):
            nombre_parrafo = [Paragraph(nombre, estilo_celda), Paragraph(f"Nota: {item['nota']}", estilo_nota)]
        else:
            nombre_parrafo = Paragraph(nombre, estilo_celda)
        fila = [
            nombre_parrafo,
            Paragraph(f"{cantidad:g}", estilo_celda_num),
            Paragraph(_fmt_dinero(precio), estilo_celda_num),
        ]
        if hay_descuentos:
            fila.append(Paragraph(f"{descuento_pct:g}%" if descuento_pct else "—", estilo_celda_num))
        fila.append(Paragraph(_fmt_dinero(subtotal), estilo_celda_num))
        filas.append(fila)

    if hay_descuentos:
        colWidths = [7.2 * cm, 1.6 * cm, 2.4 * cm, 1.7 * cm, 2.6 * cm]
    else:
        colWidths = [8.8 * cm, 1.8 * cm, 2.7 * cm, 2.7 * cm]
    tabla = Table(filas, colWidths=colWidths, repeatRows=1)
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
    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)
    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)
    tabla_total = Table([[
        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),
        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),
    ]], colWidths=[13.3 * cm, 2.7 * cm])
    tabla_total.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_total)

    if hay_descuentos:
        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])
        estilo_sin_desc = ParagraphStyle("SinDesc", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)
        elementos.append(Spacer(1, 14))
        elementos.append(Paragraph(
            f"Precio de contado (sin descuento): {_fmt_dinero(total_sin_descuento)}",
            estilo_sin_desc,
        ))

    msi = calcular_msi(cotizacion)
    if msi:
        elementos.append(Spacer(1, 14))
        elementos.append(Paragraph("Meses sin intereses", styles["Seccion"]))
        texto_recargo = f" (incluye recargo de {msi['recargo_pct']:g}% por ser más de 6 meses)" if msi["recargo_pct"] else ""
        elementos.append(Paragraph(
            f"A <b>{msi['meses']} meses sin intereses</b>{texto_recargo}: total de "
            f"<b>{_fmt_dinero(msi['total_msi'])}</b> — {msi['meses']} pagos de "
            f"<b>{_fmt_dinero(msi['mensualidad'])}</b> cada uno.",
            styles["Cuerpo"],
        ))

    if cotizacion.get("notas"):
        elementos.append(Spacer(1, 14))
        elementos.append(Paragraph("Notas", styles["Seccion"]))
        elementos.append(Paragraph(cotizacion["notas"], styles["Cuerpo"]))

    contacto_partes = []
    if cotizacion.get("creado_por_nombre"):
        tel_creador = f" — Tel. {cotizacion['creador_telefono']}" if cotizacion.get("creador_telefono") else ""
        contacto_partes.append(f"Atendido por: {cotizacion['creado_por_nombre']}{tel_creador}")
    if cotizacion.get("creador_sucursal_nombre") and cotizacion.get("creador_sucursal_telefonos"):
        contacto_partes.append(f"Sucursal {cotizacion['creador_sucursal_nombre']}: {cotizacion['creador_sucursal_telefonos']}")
    if contacto_partes:
        elementos.append(Spacer(1, 14))
        elementos.append(Paragraph("Contacto", styles["Seccion"]))
        for parte in contacto_partes:
            elementos.append(Paragraph(parte, styles["Cuerpo"]))

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


def _escapar_html(texto):
    return (
        (texto or "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_cant(n):
    n = float(n or 0)
    return f"{n:g}"


def generar_html_recibo_termico(cotizacion):
    """Recibo angosto (58mm) para la impresora térmica Star SM-L200, servido
    en la ruta pública que la app Star PassPRNT consulta directamente (no
    lleva sesión ni token de la app — por eso nunca incluye datos sensibles
    de más, solo lo mismo que ya trae la cotización). Se evitan caracteres
    tipográficos poco comunes (guion en vez de punto medio, etc.) por si la
    fuente de la impresora no los trae."""
    filas = ""
    total = 0.0
    for item in cotizacion["items"]:
        cantidad = float(item["cantidad"])
        precio = float(item["precio_unitario"])
        descuento_pct = float(item.get("descuento_pct") or 0)
        subtotal = cantidad * precio * (1 - descuento_pct / 100)
        total += subtotal
        clave = f" ({_escapar_html(item['clave'])})" if item.get("clave") else ""
        desc = f" (-{descuento_pct:g}%)" if descuento_pct else ""
        filas += f"""
          <tr>
            <td style="text-align:left; padding:3px 0;">{_escapar_html(item['nombre'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}{desc}</td>
            <td style="text-align:right; white-space:nowrap; padding:3px 0;">{_fmt_dinero(subtotal)}</td>
          </tr>
        """
    telefono = f"<br>Tel: {_escapar_html(cotizacion['cliente_telefono'])}" if cotizacion.get("cliente_telefono") else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Cotizacion {_escapar_html(cotizacion['folio'])}</title><style>
  body {{ width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }}
  h1 {{ font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }}
  .centro {{ text-align:center; margin:2px 0; }}
  .linea {{ border-top:1px dashed #000; margin:8px 0; }}
  table {{ width:100%; border-collapse:collapse; }}
  .total td {{ font-size:15px; font-weight:bold; padding-top:6px; }}
</style></head><body>
  <h1>MARK - INC</h1>
  <p class="centro">Cotizacion {_escapar_html(cotizacion['folio'])}</p>
  <div class="linea"></div>
  <p><b>Cliente:</b> {_escapar_html(cotizacion['cliente_nombre'])}{telefono}</p>
  <div class="linea"></div>
  <table>{filas}</table>
  <div class="linea"></div>
  <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">{_fmt_dinero(total)}</td></tr></table>
  <div class="linea"></div>
  <p class="centro" style="font-size:10px;">Cotizacion informativa, sujeta a cambios.<br>Vigencia 15 dias.</p>
</body></html>"""
