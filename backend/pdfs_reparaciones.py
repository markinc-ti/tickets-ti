"""Generación de los 3 documentos PDF del proceso de Reparaciones, calcados de los
formatos reales que usa Mark·Inc: Orden de Servicio, Diagnóstico Técnico y
Conformidad de Entrega.
"""
import base64
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image, ListFlowable, ListItem,
)

ZONA_MX = ZoneInfo("America/Mexico_City")  # Puebla y CDMX

ROJO = colors.HexColor("#D8192F")
GRIS = colors.HexColor("#74767A")
GRIS_CLARO = colors.HexColor("#F2F2F2")
NEGRO = colors.HexColor("#1C1E1B")

CONTACTO = {
    "web": "www.markinc.com.mx",
    "tel1": "2211536428",
    "tel2": "2211536428",
    "correo": "reparaciones.markinc@gmail.com",
    "direccion": "13 Sur 3103 Col. Volcanes C.P 72410 Puebla, Pue.",
    "razon_social": "PRODUCTOS DENTALES MARK INC S DE RL DE CV",
    "rfc": "PDM111209DP1",
}

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_larga_es(dt):
    return f"{dt.day} de {_MESES_ES[dt.month - 1]} de {dt.year}"

_LOGO_B64 = None  # se carga perezosamente desde assets/logo_mark_inc.png


def _logo_reader():
    global _LOGO_B64
    if _LOGO_B64 is None:
        import os
        ruta = os.path.join(os.path.dirname(__file__), "assets", "logo_mark_inc.png")
        with open(ruta, "rb") as f:
            _LOGO_B64 = f.read()
    return ImageReader(BytesIO(_LOGO_B64))


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TituloDoc", parent=styles["Title"], fontSize=15, textColor=NEGRO, spaceAfter=10, alignment=1))
    styles.add(ParagraphStyle("Seccion", parent=styles["Heading2"], fontSize=11.5, textColor=ROJO, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle("Etiqueta", parent=styles["Normal"], fontSize=9.5, leading=14))
    styles.add(ParagraphStyle("Cuerpo", parent=styles["Normal"], fontSize=9.5, leading=14, spaceAfter=6))
    styles.add(ParagraphStyle("FolioRojo", parent=styles["Normal"], fontSize=10.5, textColor=ROJO))
    return styles


def _pie_pagina(canvas, doc):
    canvas.saveState()
    ancho, alto = letter
    barra_alto = 1.3 * cm
    canvas.setFillColor(GRIS)
    canvas.rect(0, 0, ancho, barra_alto, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(1.5 * cm, barra_alto - 0.45 * cm, CONTACTO["web"])
    canvas.drawString(1.5 * cm, barra_alto - 0.85 * cm, f"{CONTACTO['tel1']}  ·  {CONTACTO['tel2']}")
    canvas.drawRightString(ancho - 1.5 * cm, barra_alto - 0.45 * cm, CONTACTO["correo"])
    canvas.drawRightString(ancho - 1.5 * cm, barra_alto - 0.85 * cm, CONTACTO["direccion"])
    canvas.restoreState()


def _encabezado_membretado(elementos, styles, titulo, folio=None, fecha=None):
    logo = _logo_reader()
    iw, ih = logo.getSize()
    ancho_logo = 4.5 * cm
    alto_logo = ancho_logo * ih / iw

    tabla_encabezado = Table(
        [[
            Image(BytesIO(_LOGO_B64), width=ancho_logo, height=alto_logo),
            Paragraph(f"<b>{CONTACTO['razon_social']}</b><br/>{CONTACTO['rfc']}", styles["Etiqueta"]),
        ]],
        colWidths=[6.5 * cm, 10.5 * cm],
    )
    tabla_encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 4))
    if fecha:
        elementos.append(Paragraph(fecha, ParagraphStyle("Fecha", parent=styles["Normal"], fontSize=9, alignment=2, textColor=GRIS)))
    elementos.append(HRFlowable(width="100%", thickness=1.2, color=ROJO, spaceBefore=6, spaceAfter=10))
    elementos.append(Paragraph(titulo, styles["TituloDoc"]))
    if folio:
        elementos.append(Paragraph(f"Orden de servicio: <b>{folio}</b>", styles["FolioRojo"]))
        elementos.append(Spacer(1, 8))


def _tabla_datos(pares, col_widths=(4.2 * cm, 4.5 * cm, 4.2 * cm, 4.5 * cm)):
    """Arma una tabla de 2 columnas de pares etiqueta/valor, 2 pares por fila."""
    styles = _styles()
    filas = []
    for i in range(0, len(pares), 2):
        izquierda = pares[i]
        derecha = pares[i + 1] if i + 1 < len(pares) else ("", "")
        filas.append([
            Paragraph(f"<b>{izquierda[0]}:</b>", styles["Etiqueta"]), Paragraph(str(izquierda[1] or "—"), styles["Etiqueta"]),
            Paragraph(f"<b>{derecha[0]}:</b>" if derecha[0] else "", styles["Etiqueta"]), Paragraph(str(derecha[1] or "") if derecha[0] else "", styles["Etiqueta"]),
        ])
    tabla = Table(filas, colWidths=list(col_widths))
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


def _formatear_fecha(iso_str, con_hora=False):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M") if con_hora else dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso_str)


def _pdf_a_bytes(doc, elementos):
    buffer = BytesIO()
    documento = doc(buffer)
    documento.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    buffer.seek(0)
    return buffer.read()


def _doc_template(buffer):
    return SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=2.2 * cm,
                              leftMargin=1.8 * cm, rightMargin=1.8 * cm)


# ==================== 1. ORDEN DE SERVICIO ====================

def generar_orden_servicio(rep, empresa):
    styles = _styles()
    elementos = []
    _encabezado_membretado(elementos, styles, "ORDEN DE SERVICIO",
                            fecha=f"Fecha: {_formatear_fecha(rep.get('creado_en'))}")

    elementos.append(Paragraph("1. Información del Cliente", styles["Seccion"]))
    elementos.append(_tabla_datos([
        ("Folio", rep["folio"]), ("Sucursal", rep.get("sucursal_nombre")),
        ("Nombre del Cliente", rep["cliente_nombre"]), ("Teléfono del Cliente", rep.get("cliente_telefono")),
        ("Asesor que recibe", rep.get("asesor_recibe")), ("", ""),
    ]))

    elementos.append(Paragraph("2. Información del Equipo", styles["Seccion"]))
    elementos.append(_tabla_datos([
        ("Tipo de Equipo", rep.get("equipo")), ("Marca", rep.get("marca")),
        ("Modelo", rep.get("modelo")), ("Número de serie", rep.get("numero_serie")),
        ("Fecha y Folio de Adquisición", rep.get("fecha_folio_adquisicion") or "No aplica"),
        ("Cuenta con garantía", "Sí" if rep.get("garantia") else "No"),
    ]))
    elementos.append(Paragraph(f"<b>Falla Reportada:</b><br/>{rep.get('falla_reportada') or '—'}", styles["Cuerpo"]))
    elementos.append(Paragraph(f"<b>Estado Físico:</b><br/>{rep.get('estado_fisico') or '—'}", styles["Cuerpo"]))
    elementos.append(Paragraph(f"<b>Accesorios entregados:</b><br/>{rep.get('accesorios_entregados') or '—'}", styles["Cuerpo"]))

    elementos.append(Spacer(1, 40))
    if rep.get("firma_recepcion"):
        try:
            firma_bytes = base64.b64decode(rep["firma_recepcion"].split(",")[-1])
            elementos.append(Image(BytesIO(firma_bytes), width=7 * cm, height=2.5 * cm))
        except Exception:
            pass
    elementos.append(HRFlowable(width=7 * cm, thickness=0.8, color=NEGRO, spaceBefore=2))
    elementos.append(Paragraph("Firma del Cliente", ParagraphStyle("FirmaLabel", parent=styles["Normal"], fontSize=9, alignment=1)))

    return _pdf_a_bytes(_doc_template, elementos)


# ==================== 2. DIAGNÓSTICO TÉCNICO ====================

def generar_diagnostico(rep, empresa):
    styles = _styles()
    elementos = []
    fecha_documento = datetime.fromisoformat(rep["creado_en"]) if rep.get("creado_en") else datetime.now(ZONA_MX).replace(tzinfo=None)
    fecha_hoy = _fecha_larga_es(fecha_documento)
    _encabezado_membretado(elementos, styles, "DIAGNÓSTICO TÉCNICO", folio=rep["folio"],
                            fecha=f"Tlaxcalancingo, Pue., a {fecha_hoy}")

    elementos.append(Paragraph("Datos del cliente:", styles["Seccion"]))
    elementos.append(_tabla_datos([
        ("Nombre", rep["cliente_nombre"]), ("Sucursal", rep.get("sucursal_nombre")),
    ]))

    elementos.append(Paragraph("Información del equipo:", styles["Seccion"]))
    filas_equipo = [
        ["Equipo:", rep.get("equipo") or "—", "No. Serie:", rep.get("numero_serie") or "—"],
        ["Marca:", rep.get("marca") or "—", "Fecha / Folio compra:", rep.get("fecha_folio_adquisicion") or "—"],
        ["Modelo:", rep.get("modelo") or "—", "Garantía:", "Sí aplica" if rep.get("garantia") else "NO APLICA"],
    ]
    tabla_equipo = Table(filas_equipo, colWidths=[2.6 * cm, 6 * cm, 3.6 * cm, 4.2 * cm])
    tabla_equipo.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BACKGROUND", (2, 2), (3, 2), GRIS_CLARO if not rep.get("garantia") else colors.white),
        ("TEXTCOLOR", (3, 2), (3, 2), ROJO if not rep.get("garantia") else NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_equipo)
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("Diagnóstico:", styles["Seccion"]))
    elementos.append(Paragraph(rep.get("diagnostico") or "Pendiente de registrar.", styles["Cuerpo"]))

    elementos.append(Paragraph("Costo de Reparación", styles["Seccion"]))
    filas_costo = [["ARTICULO", "CANTIDAD", "CODIGO", "COSTO"]]
    for item in rep.get("items_costo", []):
        filas_costo.append([item["articulo"], str(item["cantidad"]), item.get("codigo") or "—", f"${item['costo']:,.2f}"])
    if not rep.get("items_costo"):
        filas_costo.append(["—", "—", "—", "$0.00"])
    filas_costo.append(["COSTO TOTAL", "", "", f"${rep.get('costo_total', 0):,.2f}"])
    tabla_costo = Table(filas_costo, colWidths=[6.5 * cm, 2.8 * cm, 2.8 * cm, 3.9 * cm])
    tabla_costo.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), ROJO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("SPAN", (0, -1), (2, -1)),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, -1), (0, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_costo)
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("Conclusión:", styles["Seccion"]))
    elementos.append(Paragraph(rep.get("conclusion") or "—", styles["Cuerpo"]))

    if rep.get("recomendaciones"):
        elementos.append(Paragraph("Recomendaciones:", styles["Seccion"]))
        lineas = [l.strip("-• ").strip() for l in rep["recomendaciones"].split("\n") if l.strip()]
        if len(lineas) > 1:
            items = [ListItem(Paragraph(l, styles["Cuerpo"]), leftIndent=14, bulletColor=ROJO) for l in lineas]
            elementos.append(ListFlowable(items, bulletType="bullet", start="•"))
        else:
            elementos.append(Paragraph(rep["recomendaciones"], styles["Cuerpo"]))

    elementos.append(Spacer(1, 30))
    elementos.append(Paragraph("Atentamente", styles["Cuerpo"]))
    elementos.append(Spacer(1, 20))
    nombre_resp = rep.get("responsable_diagnostico_nombre") or "—"
    puesto_resp = rep.get("responsable_diagnostico_puesto") or "Responsable de Reparaciones"
    elementos.append(Paragraph(f"<b>{nombre_resp}</b>", styles["Cuerpo"]))
    elementos.append(Paragraph(puesto_resp, ParagraphStyle("Puesto", parent=styles["Normal"], fontSize=8.5, textColor=GRIS)))

    return _pdf_a_bytes(_doc_template, elementos)


# ==================== 3. CONFORMIDAD DE ENTREGA ====================

def generar_conformidad_entrega(rep, empresa):
    styles = _styles()
    elementos = []

    logo = _logo_reader()
    iw, ih = logo.getSize()
    ancho_logo = 6 * cm
    alto_logo = ancho_logo * ih / iw
    elementos.append(Image(BytesIO(_LOGO_B64), width=ancho_logo, height=alto_logo))
    elementos.append(Spacer(1, 14))

    elementos.append(Paragraph("Conformidad de Entrega", ParagraphStyle("TituloConf", parent=styles["Heading1"], fontSize=13, textColor=NEGRO)))
    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph(
        "Declaro haber recibido mi equipo y los accesorios descritos en esta Orden de Servicio.",
        styles["Cuerpo"],
    ))
    elementos.append(Paragraph(
        "Confirmo que recibí mi equipo en buen estado físico, que su funcionamiento fue probado en mi "
        "presencia y que opera correctamente. Asimismo, recibí la explicación del servicio realizado y, "
        "en su caso, de la garantía correspondiente.",
        styles["Cuerpo"],
    ))
    elementos.append(Spacer(1, 10))

    campo = ParagraphStyle("Campo", parent=styles["Normal"], fontSize=10.5, leading=20)
    elementos.append(Paragraph(f"<b>Nombre del Cliente:</b> {rep['cliente_nombre']}", campo))
    elementos.append(Paragraph(f"<b>Fecha de entrega:</b> {_formatear_fecha(rep.get('fecha_entrega'))}", campo))
    elementos.append(Paragraph(f"<b>Folio:</b> {rep['folio']}", campo))
    elementos.append(Spacer(1, 24))

    if rep.get("firma_entrega"):
        try:
            firma_bytes = base64.b64decode(rep["firma_entrega"].split(",")[-1])
            elementos.append(Image(BytesIO(firma_bytes), width=7 * cm, height=2.5 * cm))
        except Exception:
            pass
    elementos.append(HRFlowable(width=8 * cm, thickness=0.8, color=NEGRO, spaceBefore=2))
    elementos.append(Paragraph("Firma del Cliente", campo))
    elementos.append(Spacer(1, 14))

    elementos.append(Paragraph("<b>Observaciones de la entrega:</b>", campo))
    elementos.append(Paragraph(rep.get("observaciones_entrega") or "—", styles["Cuerpo"]))
    elementos.append(Spacer(1, 10))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

    return _pdf_a_bytes(_doc_template, elementos)
