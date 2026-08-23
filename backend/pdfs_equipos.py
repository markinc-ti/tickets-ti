# -*- coding: utf-8 -*-
"""Generador de la Carta Responsiva para equipos asignados — sigue el
formato de la plantilla real de la empresa (RESPONSIVA_CEDI.docx):
título "CARTA RESPONSIVA" con líneas a los lados, fecha en español,
tabla gris con los datos del equipo, párrafos de compromiso, y firma."""
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
GRIS_CLARO = colors.HexColor("#EDEDED")
NEGRO = colors.HexColor("#1C1E1B")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

NOMBRES_TIPO_EQUIPO_CARTA = {
    "computadora": "COMPUTADORA", "laptop": "LAPTOP", "monitor": "MONITOR", "impresora": "IMPRESORA",
    "escaner": "ESCÁNER", "servidor": "SERVIDOR",
    "mouse": "MOUSE", "mouse_inalambrico": "MOUSE INALÁMBRICO", "teclado": "TECLADO",
    "teclado_inalambrico": "TECLADO INALÁMBRICO",
    "router": "ROUTER", "switch": "SWITCH", "modem": "MÓDEM", "punto_acceso": "PUNTO DE ACCESO (WIFI)",
    "dvr": "DVR", "camara_seguridad": "CÁMARA DE SEGURIDAD", "no_break": "NO-BREAK (UPS)",
    "regulador": "REGULADOR DE VOLTAJE",
    "telefono": "TELÉFONO", "telefono_ip": "TELÉFONO IP", "proyector": "PROYECTOR",
    "bocinas": "BOCINAS", "microfono": "MICRÓFONO",
    "tablet": "TABLET", "lector_codigo_barras": "LECTOR DE CÓDIGO DE BARRAS",
    "disco_duro_externo": "DISCO DURO EXTERNO", "red": "EQUIPO DE RED", "otro": "EQUIPO",
}


def _logo_bytes(empresa):
    logo_base64 = (empresa or {}).get("logo_base64")
    if not logo_base64:
        return None
    try:
        datos = logo_base64.split(",", 1)[1] if "," in logo_base64 else logo_base64
        return base64.b64decode(datos)
    except Exception:
        return None


def generar_carta_responsiva(equipo, empresa):
    """equipo: dict de la tabla equipos (nombre, tipo, marca, modelo, numero_serie,
    departamento, responsable, notas). empresa: dict con nombre y logo_base64."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.8*cm, bottomMargin=1.8*cm,
                             leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TituloCarta", parent=styles["Heading1"], fontSize=15, textColor=NEGRO,
                               alignment=1, spaceAfter=4))
    styles.add(ParagraphStyle("FechaCarta", parent=styles["Normal"], fontSize=10, textColor=NEGRO,
                               alignment=1, fontName="Helvetica-Bold", spaceAfter=14))
    styles.add(ParagraphStyle("CeldaHeader", parent=styles["Normal"], fontSize=9, textColor=NEGRO,
                               fontName="Helvetica-Bold", leading=12))
    styles.add(ParagraphStyle("Celda", parent=styles["Normal"], fontSize=9.5, leading=12.5))
    styles.add(ParagraphStyle("Cuerpo", parent=styles["Normal"], fontSize=10, leading=15.5, spaceAfter=10,
                               alignment=4))  # justificado
    styles.add(ParagraphStyle("FirmaNombre", parent=styles["Normal"], fontSize=10, alignment=1,
                               fontName="Helvetica-Bold", spaceBefore=2))
    styles.add(ParagraphStyle("FirmaPuesto2", parent=styles["Normal"], fontSize=9.5, alignment=1, textColor=GRIS))
    styles.add(ParagraphStyle("PiePagina", parent=styles["Normal"], fontSize=7.5, textColor=GRIS))

    elementos = []

    logo_datos = _logo_bytes(empresa)
    if logo_datos:
        iw, ih = ImageReader(BytesIO(logo_datos)).getSize()
        ancho = 4.5*cm
        elementos.append(Table([[Image(BytesIO(logo_datos), width=ancho, height=ancho*ih/iw)]], colWidths=[17*cm],
                                style=TableStyle([("ALIGN", (0,0), (-1,-1), "LEFT")])))
        elementos.append(Spacer(1, 4))

    # Título con línea a cada lado, como en la plantilla original
    fila_titulo = Table(
        [[HRFlowable(width="100%", thickness=1, color=NEGRO), Paragraph("CARTA RESPONSIVA", styles["TituloCarta"]),
          HRFlowable(width="100%", thickness=1, color=NEGRO)]],
        colWidths=[4.3*cm, 8.4*cm, 4.3*cm],
    )
    fila_titulo.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    elementos.append(fila_titulo)
    elementos.append(Spacer(1, 6))

    ahora = datetime.now(ZoneInfo("America/Mexico_City"))
    fecha_legible = f"San Andrés Cholula, San Bernardino Tlaxcalancingo a {ahora.day:02d} de {MESES[ahora.month - 1].capitalize()} del {ahora.year}."
    elementos.append(Paragraph(fecha_legible, styles["FechaCarta"]))

    def celda(texto):
        return Paragraph(texto or "—", styles["Celda"])
    def celda_h(texto):
        return Paragraph(texto, styles["CeldaHeader"])

    tipo_legible = NOMBRES_TIPO_EQUIPO_CARTA.get(equipo.get("tipo"), (equipo.get("tipo") or "EQUIPO").upper())
    responsable_nombre = equipo.get("usuario_nombre") or equipo.get("responsable") or ""
    marca_modelo = " / ".join(x for x in [equipo.get("marca"), equipo.get("modelo")] if x) or "—"
    equipo_legible = tipo_legible + (f" — {equipo['nombre'].upper()}" if equipo.get("nombre") else "")

    filas_tabla = [
        [celda_h("NOMBRE:"), celda(responsable_nombre.upper() if responsable_nombre else None),
         celda_h("DEPTO:"), celda((equipo.get("departamento") or "").upper() or None)],
        [celda_h("EQUIPO:"), celda(equipo_legible),
         celda_h("No. Serie:"), celda(equipo.get("numero_serie"))],
        [celda_h("Marca/Modelo:"), Table([[celda(marca_modelo.upper())]], colWidths=[10.5*cm],
                                          style=TableStyle([("SPAN", (0,0), (-1,-1))]))],
    ]
    if equipo.get("notas"):
        filas_tabla.append([celda_h("Notas / accesorios:"), Table([[celda(equipo["notas"])]], colWidths=[10.5*cm],
                                                                    style=TableStyle([("SPAN", (0,0), (-1,-1))]))])

    tabla_datos = Table(filas_tabla, colWidths=[2.9*cm, 5.4*cm, 2.9*cm, 5.4*cm])
    tabla_datos.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.6, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), GRIS_CLARO), ("BACKGROUND", (2,0), (2,1), GRIS_CLARO),
        ("SPAN", (1,2), (3,2)),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ] + ([("SPAN", (1,3), (3,3))] if equipo.get("notas") else [])))
    elementos.append(tabla_datos)
    elementos.append(Spacer(1, 16))

    empresa_nombre = ((empresa or {}).get("nombre") or "LA EMPRESA").upper()
    texto1 = (
        f"Recibí {tipo_legible.lower() if tipo_legible != 'EQUIPO' else 'el equipo'}, el cuál me fue asignado como "
        f"herramienta de trabajo para el desempeño de mis funciones, me comprometo a su buen manejo, aplicando y "
        f"cumpliendo las políticas de uso, toda la información que se derive en el mismo es estrictamente "
        f"confidencial y propiedad de <b>{empresa_nombre}</b>."
    )
    texto2 = (
        "El tiempo que tenga a mi resguardo el equipo lo conservaré en buenas condiciones y lo usaré únicamente "
        "para las actividades relacionadas con mi puesto, me comprometo a <b>NO DESCARGAR</b> aplicaciones que no "
        "sean de carácter laboral. El mal uso del equipo y el no acatar esta disposición será mi responsabilidad "
        "y acataré la sanción correspondiente."
    )
    texto3 = (
        f"En caso de promoción de puesto y/o terminación de la relación laboral con <b>{empresa_nombre}</b>, soy "
        f"responsable de regresar el equipo a Gerencia y/o a mi supervisor directo para la cancelación de este "
        f"documento. En caso contrario de no entregarlo en buenas condiciones y/o funcionando, <b>ACEPTO</b> se me "
        f"descuente el costo de reposición vigente del mercado; en caso de robo o extravío es mi responsabilidad "
        f"levantar una denuncia ante el Ministerio Público y entregar una copia del trámite que se realice, y en "
        f"todo momento deberé informar por escrito a mi superior inmediato."
    )
    texto4 = (
        "Asimismo, reconozco que el equipo asignado podrá ser solicitado en cualquier momento por mi jefe "
        "inmediato o por Dirección, comprometiéndome a realizar su entrega de manera oportuna y sin objeción "
        "alguna, cuando así me sea requerido por motivos laborales o administrativos."
    )
    for t in (texto1, texto2, texto3):
        elementos.append(Paragraph(t, styles["Cuerpo"]))

    elementos.append(Spacer(1, 30))
    bloque_firma = Table([
        [Paragraph("PERSONAL RESPONSABLE", ParagraphStyle("FirmaTitulo", parent=styles["Normal"], fontSize=10,
                                                            alignment=1, fontName="Helvetica-Bold"))],
        [Spacer(1, 26)],
        [HRFlowable(width="70%", thickness=0.8, color=NEGRO, hAlign="CENTER")],
        [Paragraph(responsable_nombre.upper() if responsable_nombre else "&nbsp;", styles["FirmaNombre"])],
    ], colWidths=[10*cm])
    bloque_firma.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
    elementos.append(Table([[bloque_firma]], colWidths=[17*cm], style=TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")])))
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(texto4, styles["Cuerpo"]))

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawCentredString(letter[0]/2, 1.2*cm,
                                  f"{(empresa or {}).get('nombre', '')} — Carta responsiva generada el {ahora.strftime('%d/%m/%Y %H:%M')}")
        canvas.restoreState()

    doc.build(elementos, onFirstPage=pie, onLaterPages=pie)
    buffer.seek(0)
    return buffer.read()
