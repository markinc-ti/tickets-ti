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
    _pie_pagina_personalizado, _formatear_fecha, _doc_template,
)


# ==================== Reportador: diseño configurable ====================
# Bloques que el administrador puede reordenar, ocultar, y a los que se les
# puede cambiar el tamaño de letra desde el Reportador (Administrar → Diseño
# de PDFs). El encabezado (logo + título + folio) no es parte de la lista
# porque es la identidad del documento — siempre va primero y siempre visible.

ORDEN_BLOQUES_DEFAULT = [
    "cliente", "tabla_articulos", "precio_contado", "total",
    "meses_msi", "notas", "contacto", "vigencia",
]

NOMBRES_BLOQUES_COTIZACION = {
    "cliente": "Datos del cliente",
    "tabla_articulos": "Tabla de artículos",
    "precio_contado": "Precio de contado (solo si hay descuentos)",
    "total": "Total",
    "meses_msi": "Meses sin intereses (solo si se cotizaron)",
    "notas": "Notas",
    "contacto": "Contacto (atendido por / sucursal)",
    "vigencia": "Vigencia y aviso legal",
}

FACTOR_TAMANO_FUENTE = {"chico": 0.85, "normal": 1.0, "grande": 1.15}

# Espaciado (en puntos) ANTES de cada bloque — el mismo que ya traía el
# diseño original. Editable por bloque desde el Reportador para poder
# apretar el documento y aprovechar mejor la hoja.
ESPACIADO_DEFAULT_BLOQUES = {
    "cliente": 0, "tabla_articulos": 10, "precio_contado": 0, "total": 0,
    "meses_msi": 14, "notas": 14, "contacto": 14, "vigencia": 20,
}


def diseno_default_cotizacion():
    """El diseño de fábrica — usarlo produce EXACTAMENTE el mismo PDF que
    antes de que existiera el Reportador."""
    return {
        "tamano_fuente": "normal",
        "padding_filas_tabla": 6,
        "pie_pagina": {"linea1_izq": None, "linea2_izq": None, "linea1_der": None, "linea2_der": None},
        "bloques": [{"id": b, "visible": True, "espaciado": ESPACIADO_DEFAULT_BLOQUES[b]} for b in ORDEN_BLOQUES_DEFAULT],
    }


def _normalizar_diseno(diseno):
    """Completa cualquier diseño guardado con los defaults que le falten
    (por si se agregan bloques o propiedades nuevas después) y descarta
    ids de bloques que ya no existan."""
    base = diseno_default_cotizacion()
    if not diseno:
        return base
    resultado = {**base, **diseno}
    resultado["tamano_fuente"] = diseno.get("tamano_fuente") or base["tamano_fuente"]
    resultado["padding_filas_tabla"] = diseno.get("padding_filas_tabla") or base["padding_filas_tabla"]
    resultado["pie_pagina"] = {**base["pie_pagina"], **(diseno.get("pie_pagina") or {})}
    bloques_guardados = diseno.get("bloques") or []
    ids_guardados = {b["id"] for b in bloques_guardados if b.get("id") in NOMBRES_BLOQUES_COTIZACION}
    bloques = []
    for b in bloques_guardados:
        if b.get("id") not in NOMBRES_BLOQUES_COTIZACION:
            continue
        # diseños guardados antes de que existiera "espaciado" no lo traen
        if "espaciado" not in b or b["espaciado"] is None:
            b = {**b, "espaciado": ESPACIADO_DEFAULT_BLOQUES.get(b["id"], 0)}
        bloques.append(b)
    for b_id in ORDEN_BLOQUES_DEFAULT:  # agrega al final cualquier bloque nuevo que el diseño guardado no conociera
        if b_id not in ids_guardados:
            bloques.append({"id": b_id, "visible": True, "espaciado": ESPACIADO_DEFAULT_BLOQUES[b_id]})
    resultado["bloques"] = bloques
    return resultado


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


def _bloque_cliente(elementos, styles, cot, ctx):
    elementos.append(Paragraph("Cliente", styles["Seccion"]))
    elementos.append(Paragraph(f"<b>Nombre:</b> {cot.get('cliente_nombre') or '—'}", styles["Cuerpo"]))
    contacto_cliente = []
    if cot.get("cliente_telefono"):
        contacto_cliente.append(f"<b>Teléfono:</b> {cot['cliente_telefono']}")
    if cot.get("cliente_direccion"):
        contacto_cliente.append(f"<b>Dirección:</b> {cot['cliente_direccion']}")
    if contacto_cliente:
        elementos.append(Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(contacto_cliente), styles["Cuerpo"]))
    return True


def _bloque_tabla_articulos(elementos, styles, cot, ctx):
    elementos.append(Paragraph("Artículos cotizados", styles["Seccion"]))
    factor = ctx["factor"]
    estilo_celda = ParagraphStyle("CeldaTabla", parent=styles["Normal"], fontSize=9 * factor, leading=12 * factor)
    estilo_celda_num = ParagraphStyle("CeldaTablaNum", parent=estilo_celda, alignment=2)
    estilo_nota = ParagraphStyle("NotaItem", parent=estilo_celda, fontSize=7.5 * factor, textColor=GRIS, leftIndent=2)
    hay_descuentos = ctx["hay_descuentos"]
    encabezado = [
        Paragraph("<b>Artículo</b>", estilo_celda),
        Paragraph("<b>Cant.</b>", estilo_celda_num),
        Paragraph("<b>Precio unit.</b>", estilo_celda_num),
    ]
    if hay_descuentos:
        encabezado.append(Paragraph("<b>Desc.</b>", estilo_celda_num))
    encabezado.append(Paragraph("<b>Subtotal</b>", estilo_celda_num))
    filas = [encabezado]
    for item in cot["items"]:
        cantidad = float(item["cantidad"])
        precio = float(item["precio_unitario"])
        descuento_pct = float(item.get("descuento_pct") or 0)
        subtotal = cantidad * precio * (1 - descuento_pct / 100)
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

    tabla = Table(filas, colWidths=ctx["colWidths"], repeatRows=1)
    pad = ctx["padding_filas_tabla"]
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROJO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS),
    ]))
    elementos.append(tabla)
    return True


def _bloque_precio_contado(elementos, styles, cot, ctx):
    if not ctx["hay_descuentos"]:
        return False  # esta leyenda solo aplica cuando hay descuentos que restar
    factor = ctx["factor"]
    elementos.append(HRFlowable(width="100%", thickness=1.2, color=ROJO, spaceBefore=2, spaceAfter=4))
    total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cot["items"])
    estilo_sin_desc_etiqueta = ParagraphStyle("SinDescEtiqueta", parent=styles["Normal"], fontSize=8 * factor, textColor=GRIS)
    estilo_sin_desc_valor = ParagraphStyle("SinDescValor", parent=styles["Normal"], fontSize=9 * factor, alignment=2, textColor=GRIS)
    fila_contado = [""] * len(ctx["colWidths"])
    fila_contado[0] = Paragraph("Precio de contado (sin descuento)", estilo_sin_desc_etiqueta)
    fila_contado[2] = Paragraph(_fmt_dinero(total_sin_descuento), estilo_sin_desc_valor)
    tabla_contado = Table([fila_contado], colWidths=ctx["colWidths"])
    tabla_contado.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elementos.append(tabla_contado)
    return True


def _bloque_total(elementos, styles, cot, ctx):
    factor = ctx["factor"]
    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12 * factor, textColor=NEGRO)
    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12 * factor, alignment=2, textColor=ROJO)
    tabla_total = Table([[
        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),
        Paragraph(f"<b>{_fmt_dinero(ctx['total'])}</b>", estilo_total_valor),
    ]], colWidths=[12.7 * cm, 3.3 * cm])
    estilo_tabla_total = [
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if not ctx["hay_descuentos"]:
        estilo_tabla_total.append(("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO))
    tabla_total.setStyle(TableStyle(estilo_tabla_total))
    elementos.append(tabla_total)
    return True


def _bloque_meses_msi(elementos, styles, cot, ctx):
    msi = ctx["msi"]
    if not msi:
        return False
    elementos.append(Paragraph("Meses sin intereses", styles["Seccion"]))
    texto_recargo = f" (incluye recargo de {msi['recargo_pct']:g}% por ser más de 6 meses)" if msi["recargo_pct"] else ""
    elementos.append(Paragraph(
        f"A <b>{msi['meses']} meses sin intereses</b>{texto_recargo}: total de "
        f"<b>{_fmt_dinero(msi['total_msi'])}</b> — {msi['meses']} pagos de "
        f"<b>{_fmt_dinero(msi['mensualidad'])}</b> cada uno.",
        styles["Cuerpo"],
    ))
    return True


def _bloque_notas(elementos, styles, cot, ctx):
    if not cot.get("notas"):
        return False
    elementos.append(Paragraph("Notas", styles["Seccion"]))
    elementos.append(Paragraph(cot["notas"], styles["Cuerpo"]))
    return True


def _bloque_contacto(elementos, styles, cot, ctx):
    contacto_partes = []
    if cot.get("creado_por_nombre"):
        tel_creador = f" — Tel. {cot['creador_telefono']}" if cot.get("creador_telefono") else ""
        contacto_partes.append(f"Atendido por: {cot['creado_por_nombre']}{tel_creador}")
    if cot.get("creador_sucursal_nombre") and cot.get("creador_sucursal_telefonos"):
        contacto_partes.append(f"Sucursal {cot['creador_sucursal_nombre']}: {cot['creador_sucursal_telefonos']}")
    if not contacto_partes:
        return False
    elementos.append(Paragraph("Contacto", styles["Seccion"]))
    for parte in contacto_partes:
        elementos.append(Paragraph(parte, styles["Cuerpo"]))
    return True


def _bloque_vigencia(elementos, styles, cot, ctx):
    factor = ctx["factor"]
    elementos.append(HRFlowable(width="100%", thickness=0.8, color=GRIS, spaceBefore=4, spaceAfter=8))
    texto_vigencia = "Esta cotización es informativa y no representa una factura. Precios sujetos a cambio sin previo aviso."
    if cot.get("vigencia_hasta"):
        texto_vigencia += f" Vigente hasta el {_formatear_fecha(str(cot['vigencia_hasta']))} (5 días hábiles)."
    elementos.append(Paragraph(
        texto_vigencia,
        ParagraphStyle("Vigencia", parent=styles["Normal"], fontSize=7.5 * factor, textColor=GRIS),
    ))
    return True


_FUNCIONES_BLOQUES = {
    "cliente": _bloque_cliente,
    "tabla_articulos": _bloque_tabla_articulos,
    "precio_contado": _bloque_precio_contado,
    "total": _bloque_total,
    "meses_msi": _bloque_meses_msi,
    "notas": _bloque_notas,
    "contacto": _bloque_contacto,
    "vigencia": _bloque_vigencia,
}


def generar_cotizacion_pdf(cotizacion, empresa, diseno=None):
    diseno = _normalizar_diseno(diseno)
    factor = FACTOR_TAMANO_FUENTE.get(diseno["tamano_fuente"], 1.0)
    styles = _styles(factor)
    elementos = []
    titulo = TITULOS_TIPO_CLIENTE.get(cotizacion.get("tipo_cliente"), "COTIZACIÓN")
    _encabezado_membretado(
        elementos, styles, titulo,
        folio=cotizacion["folio"],
        fecha=f"Fecha: {_formatear_fecha(cotizacion.get('creado_en'))}",
        etiqueta_folio="Folio",
    )

    hay_descuentos = any(float(item.get("descuento_pct") or 0) > 0 for item in cotizacion["items"])
    total = sum(
        float(item["cantidad"]) * float(item["precio_unitario"]) * (1 - float(item.get("descuento_pct") or 0) / 100)
        for item in cotizacion["items"]
    )
    if hay_descuentos:
        colWidths = [7.2 * cm, 1.6 * cm, 2.4 * cm, 1.7 * cm, 2.6 * cm]
    else:
        colWidths = [8.8 * cm, 1.8 * cm, 2.7 * cm, 2.7 * cm]
    ctx = {
        "factor": factor,
        "hay_descuentos": hay_descuentos,
        "total": total,
        "colWidths": colWidths,
        "msi": calcular_msi(cotizacion),
        "padding_filas_tabla": diseno["padding_filas_tabla"],
    }

    for bloque in diseno["bloques"]:
        if not bloque.get("visible", True):
            continue
        funcion = _FUNCIONES_BLOQUES.get(bloque["id"])
        if not funcion:
            continue
        espaciado = bloque.get("espaciado") or 0
        marca_antes = len(elementos)
        if espaciado and elementos:  # sin espacio antes del primer bloque visible
            elementos.append(Spacer(1, espaciado))
        agregado = funcion(elementos, styles, cotizacion, ctx)
        if agregado is False:
            # el bloque no aplicó (ej. "precio de contado" sin descuentos) —
            # se quita también el espacio que se le había puesto antes, para
            # no dejar un hueco donde no hay nada.
            del elementos[marca_antes:]

    buffer = BytesIO()
    documento = _doc_template(buffer)
    pie = _pie_pagina_personalizado(diseno.get("pie_pagina"))
    documento.build(elementos, onFirstPage=pie, onLaterPages=pie)
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
        subtotal = cantidad * precio
        total += subtotal
        clave = f" ({_escapar_html(item['clave'])})" if item.get("clave") else ""
        filas += f"""
          <tr>
            <td style="text-align:left; padding:3px 0;">{_escapar_html(item['nombre'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}</td>
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
