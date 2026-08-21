# -*- coding: utf-8 -*-
"""Generador de PDFs del módulo de Recursos Humanos — por ahora, la constancia
de finalización de curso. Sigue el mismo estilo visual que pdfs_reparaciones.py
(logo de la empresa, acento rojo, tipografía limpia)."""
import base64
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable

ROJO = colors.HexColor("#D8192F")
GRIS = colors.HexColor("#74767A")
NEGRO = colors.HexColor("#1C1E1B")
GRIS_CLARO = colors.HexColor("#F2F2F2")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _logo_bytes(empresa):
    logo_base64 = (empresa or {}).get("logo_base64")
    if not logo_base64:
        return None
    try:
        datos = logo_base64.split(",", 1)[1] if "," in logo_base64 else logo_base64
        return base64.b64decode(datos)
    except Exception:
        return None


def _firma_bytes(firma_base64):
    if not firma_base64:
        return None
    try:
        datos = firma_base64.split(",", 1)[1] if "," in firma_base64 else firma_base64
        return base64.b64decode(datos)
    except Exception:
        return None


def generar_constancia_curso(curso, participante, empresa):
    """curso: dict de cursos_rh (nombre, descripcion, puesto_objetivo).
    participante: dict con nombre_completo, puesto, completado_en, firma_base64."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=2.5*cm, bottomMargin=2.5*cm,
                             leftMargin=2.2*cm, rightMargin=2.2*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TituloConstancia", parent=styles["Title"], fontSize=26, textColor=NEGRO,
                               alignment=1, spaceBefore=18, spaceAfter=6))
    styles.add(ParagraphStyle("SubConstancia", parent=styles["Normal"], fontSize=11, textColor=GRIS,
                               alignment=1, spaceAfter=28))
    styles.add(ParagraphStyle("CuerpoConstancia", parent=styles["Normal"], fontSize=12.5, leading=20,
                               alignment=1, spaceAfter=18))
    styles.add(ParagraphStyle("NombreParticipante", parent=styles["Normal"], fontSize=19, leading=24,
                               alignment=1, textColor=ROJO, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=6))
    styles.add(ParagraphStyle("PiePagina", parent=styles["Normal"], fontSize=8, textColor=GRIS))

    elementos = []

    logo_datos = _logo_bytes(empresa)
    if logo_datos:
        iw, ih = ImageReader(BytesIO(logo_datos)).getSize()
        ancho = 6*cm
        elementos.append(Table([[Image(BytesIO(logo_datos), width=ancho, height=ancho*ih/iw)]], colWidths=[17*cm],
                                style=TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")])))
    elementos.append(Spacer(1, 6))
    elementos.append(HRFlowable(width="60%", thickness=1.3, color=ROJO, spaceBefore=6, spaceAfter=6, hAlign="CENTER"))

    elementos.append(Paragraph("CONSTANCIA DE CAPACITACIÓN", styles["TituloConstancia"]))
    elementos.append(Paragraph((empresa or {}).get("nombre", "").upper(), styles["SubConstancia"]))

    elementos.append(Paragraph("Se otorga la presente constancia a:", styles["CuerpoConstancia"]))
    elementos.append(Paragraph(participante.get("nombre_completo", ""), styles["NombreParticipante"]))
    if participante.get("puesto"):
        elementos.append(Paragraph(f"Puesto: {participante['puesto']}",
                                    ParagraphStyle("Puesto", parent=styles["Normal"], fontSize=10.5,
                                                    textColor=GRIS, alignment=1, spaceAfter=18)))

    elementos.append(Paragraph(
        f"Por haber completado satisfactoriamente el curso de capacitación:",
        styles["CuerpoConstancia"],
    ))
    elementos.append(Paragraph(
        f"«{curso.get('nombre', '')}»",
        ParagraphStyle("NombreCurso", parent=styles["Normal"], fontSize=15, leading=20, alignment=1,
                        fontName="Helvetica-Bold", textColor=NEGRO, spaceAfter=18),
    ))
    if curso.get("descripcion"):
        elementos.append(Paragraph(curso["descripcion"],
                                    ParagraphStyle("DescCurso", parent=styles["Normal"], fontSize=10, leading=15,
                                                    textColor=GRIS, alignment=1, spaceAfter=22)))

    completado_en = participante.get("completado_en") or ""
    fecha_legible = completado_en
    try:
        dt = datetime.fromisoformat(completado_en)
        fecha_legible = f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"
    except Exception:
        pass
    elementos.append(Paragraph(f"Fecha de finalización: {fecha_legible}",
                                ParagraphStyle("Fecha", parent=styles["Normal"], fontSize=10.5, alignment=1,
                                                textColor=NEGRO, spaceAfter=36)))

    firma_datos = _firma_bytes(participante.get("firma_base64"))
    if firma_datos:
        iw, ih = ImageReader(BytesIO(firma_datos)).getSize()
        ancho_firma = 6*cm
        elementos.append(Table([[Image(BytesIO(firma_datos), width=ancho_firma, height=ancho_firma*ih/iw)]], colWidths=[17*cm],
                                style=TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")])))
    elementos.append(HRFlowable(width="35%", thickness=0.8, color=GRIS, spaceBefore=2, spaceAfter=4, hAlign="CENTER"))
    elementos.append(Paragraph("Firma del participante",
                                ParagraphStyle("FirmaLabel", parent=styles["Normal"], fontSize=9, alignment=1,
                                                textColor=GRIS)))

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        ahora_tz = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%d/%m/%Y %H:%M")
        canvas.drawCentredString(letter[0]/2, 1.3*cm, f"Constancia generada automáticamente el {ahora_tz}")
        canvas.restoreState()

    doc.build(elementos, onFirstPage=pie, onLaterPages=pie)
    buffer.seek(0)
    return buffer.read()
