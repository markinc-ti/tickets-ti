# -*- coding: utf-8 -*-
"""PDFs del módulo de Soporte técnico (Peymar): orden de servicio (con la firma
del cliente) y diagnóstico / resolución para el cliente. Llevan el logo de la
empresa (Superadmin → logo). Nunca incluyen el apartado interno ni costos."""
import base64
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from minuta_ia import _fecha_corta, _fecha_larga, _fuentes

TIPOS = {"mantenimiento": "Mantenimiento", "garantia": "Garantía"}
AZUL = colors.HexColor("#0E4C92")      # acento por default si la empresa no tiene color
TINTA = colors.HexColor("#1B1B1D")
GRIS = colors.HexColor("#5B5D62")
LINEA = colors.HexColor("#D9D4CF")
CLARO = colors.HexColor("#F4F6FA")
ANCHO = letter[0] - 3.6 * cm


def _logo_de(empresa):
    """Solo el logo de ESTA empresa (Superadmin → logo); sin logo, va su nombre en texto."""
    datos = (empresa or {}).get("logo_base64") if isinstance(empresa, dict) else None
    if not datos:
        return None
    try:
        return base64.b64decode(datos.split(",", 1)[1] if "," in datos else datos)
    except Exception:
        return None


def folio_txt(r):
    return f"SOP-{int(r['folio']):06d}"


def _acento(empresa):
    c = (empresa or {}).get("color_acento") if isinstance(empresa, dict) else None
    try:
        return colors.HexColor(c) if c and c.startswith("#") and len(c) in (4, 7) else AZUL
    except Exception:
        return AZUL


def _estilos(acento):
    F, FB, _ = _fuentes()
    st = getSampleStyleSheet()
    base = ParagraphStyle("b", parent=st["BodyText"], fontName=F, fontSize=9.6, leading=13.4, textColor=TINTA)
    return {
        "base": base,
        "chico": ParagraphStyle("c", parent=base, fontSize=8, leading=10.5, textColor=GRIS),
        "et": ParagraphStyle("e", parent=base, fontName=FB, fontSize=7.4, leading=9, textColor=GRIS),
        "val": ParagraphStyle("v", parent=base, fontName=FB, fontSize=9.6, leading=12),
        "celda": ParagraphStyle("ce", parent=base, fontSize=8.8, leading=11.4),
        "encab": ParagraphStyle("en", parent=base, fontName=FB, fontSize=8.2, leading=10.5, textColor=colors.white),
        "titulo": ParagraphStyle("t", parent=base, fontName=FB, fontSize=16, leading=19),
        "sub": ParagraphStyle("s", parent=base, fontName=FB, fontSize=9, leading=11, textColor=acento),
        "sec": ParagraphStyle("se", parent=base, fontName=FB, fontSize=9.6, leading=12),
        "F": F, "FB": FB,
    }


def _e(t):
    return escape(str(t if t is not None else ""))


def _imagen(datos_b64, max_w, max_h):
    try:
        raw = base64.b64decode(datos_b64.split(",", 1)[1] if "," in datos_b64 else datos_b64)
        iw, ih = ImageReader(BytesIO(raw)).getSize()
        k = min(max_w / iw, max_h / ih, 1e9)
        return Image(BytesIO(raw), width=iw * k, height=ih * k)
    except Exception:
        return None


class _Doc:
    """Encabezado (logo | título | folio), secciones numeradas y pie con 'Página X de Y'."""

    def __init__(self, empresa, titulo, r):
        self.empresa = empresa or {}
        self.acento = _acento(self.empresa)
        self.s = _estilos(self.acento)
        self.titulo = titulo
        self.r = r
        self.h = []
        self.n = 0
        self.nombre_empresa = (self.empresa.get("nombre") if isinstance(self.empresa, dict) else str(self.empresa)) or ""

    def encabezado(self, fecha):
        s = self.s
        logo = _logo_de(self.empresa)
        celda_logo = Paragraph(_e(self.nombre_empresa), ParagraphStyle("ln", parent=s["titulo"], fontSize=13, leading=15))
        if logo:
            try:
                iw, ih = ImageReader(BytesIO(logo)).getSize()
                w = 4.3 * cm
                hh = w * ih / iw
                if hh > 1.9 * cm:
                    hh = 1.9 * cm
                    w = hh * iw / ih
                celda_logo = Image(BytesIO(logo), width=w, height=hh)
            except Exception:
                pass
        blanco = lambda st, **k: ParagraphStyle("x", parent=st, textColor=colors.white, alignment=TA_CENTER, **k)
        caja = Table([[Paragraph("FOLIO", blanco(s["et"]))],
                      [Paragraph(_e(folio_txt(self.r)), blanco(s["val"], fontSize=11))],
                      [Paragraph(_e(_fecha_corta(fecha)), blanco(s["chico"]))]], colWidths=[3.4 * cm])
        caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), self.acento), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        cab = Table([[celda_logo, [Paragraph(_e(self.titulo), s["titulo"]), Spacer(1, 2),
                                   Paragraph(_e(self.nombre_empresa).upper() + " · SOPORTE TÉCNICO", s["sub"])], caja]],
                    colWidths=[4.8 * cm, ANCHO - 4.8 * cm - 3.6 * cm, 3.6 * cm])
        cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("LINEBELOW", (0, 0), (-1, 0), 2, self.acento),
                                 ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]))
        self.h += [cab, Spacer(1, 10)]

    def seccion(self, texto, devolver=False):
        self.n += 1
        t = Table([[Paragraph(f"{self.n}.&nbsp;&nbsp;{_e(texto.upper())}", self.s["sec"])]], colWidths=[ANCHO])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CLARO), ("LINEBEFORE", (0, 0), (0, -1), 3.2, self.acento),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        if devolver:
            return [Spacer(1, 10), t, Spacer(1, 5)]
        self.h += [Spacer(1, 10), t, Spacer(1, 5)]

    def datos(self, pares):
        """pares: [(etiqueta, valor), ...] en 2 columnas."""
        s = self.s
        filas = []
        for i in range(0, len(pares), 2):
            fila = []
            for et, val in pares[i:i + 2]:
                fila += [Paragraph(_e(et).upper(), s["et"]), Paragraph(_e(val) if val not in (None, "") else "—", s["val"])]
            while len(fila) < 4:
                fila.append("")
            filas.append(fila)
        t = Table(filas, colWidths=[3.1 * cm, ANCHO / 2 - 3.1 * cm, 3.1 * cm, ANCHO / 2 - 3.1 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, LINEA),
                               ("INNERGRID", (0, 0), (-1, -1), 0.4, LINEA),
                               ("BACKGROUND", (0, 0), (0, -1), CLARO), ("BACKGROUND", (2, 0), (2, -1), CLARO),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        self.h.append(t)

    def texto(self, t):
        for parrafo in str(t or "—").split("\n"):
            self.h.append(Paragraph(_e(parrafo) or "&nbsp;", self.s["base"]))

    def tabla(self, filas, anchos):
        t = Table(filas, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TINTA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA), ("BOX", (0, 0), (-1, -1), 0.5, LINEA),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        self.h.append(t)

    def fotos(self, evidencias, max_fotos=6, titulo=None):
        """evidencias: [{archivo_base64, tipo, descripcion}] — solo imágenes, 3 por renglón."""
        imgs = []
        for ev in evidencias:
            if len(imgs) >= max_fotos:
                break
            if (ev.get("tipo") or "").startswith("image") and ev.get("archivo_base64"):
                im = _imagen(ev["archivo_base64"], ANCHO / 3 - 0.4 * cm, 4.6 * cm)
                if im:
                    imgs.append([im, Paragraph(_e(ev.get("descripcion") or ""), self.s["chico"])])
        if not imgs:
            return False
        filas = []
        for i in range(0, len(imgs), 3):
            grupo = imgs[i:i + 3]
            filas.append([g[0] for g in grupo] + [""] * (3 - len(grupo)))
            filas.append([g[1] for g in grupo] + [""] * (3 - len(grupo)))
        t = Table(filas, colWidths=[ANCHO / 3] * 3)
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        self.h.append(KeepTogether((self.seccion(titulo, devolver=True) if titulo else []) + [t]))
        return True

    def construir(self, pie):
        acento = self.acento
        F = self.s["F"]

        class _Lienzo(rl_canvas.Canvas):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self._paginas = []

            def showPage(self):
                self._paginas.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._paginas)
                for estado in self._paginas:
                    self.__dict__.update(estado)
                    self.setStrokeColor(acento)
                    self.setLineWidth(0.8)
                    self.line(1.8 * cm, 1.35 * cm, letter[0] - 1.8 * cm, 1.35 * cm)
                    self.setFont(F, 7.5)
                    self.setFillColor(GRIS)
                    self.drawString(1.8 * cm, 0.95 * cm, pie)
                    self.drawRightString(letter[0] - 1.8 * cm, 0.95 * cm, f"Página {self._pageNumber} de {total}")
                    super().showPage()
                super().save()

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm,
                                bottomMargin=1.9 * cm, title=f"{self.titulo} {folio_txt(self.r)}", author=self.nombre_empresa)
        doc.build(self.h, canvasmaker=_Lienzo)
        return buf.getvalue()


def _datos_equipo(d, r):
    d.datos([("Tipo de unidad dental", r.get("tipo_unidad")), ("Modelo", r.get("modelo")),
             ("Número de serie", r.get("numero_serie")), ("Tipo de servicio", TIPOS.get(r.get("tipo_servicio"), r.get("tipo_servicio")))])


def _datos_cliente(d, r):
    d.datos([("Cliente", r.get("cliente_nombre")), ("Teléfono", r.get("cliente_telefono")),
             ("Correo", r.get("cliente_email")), ("Ciudad", r.get("cliente_ciudad")),
             ("Dirección", r.get("cliente_direccion"))])


def orden_servicio_pdf(r, empresa, evidencias, liga=None):
    """r: reporte (con firma si ya firmó). evidencias: las de la etapa 'reporte' con archivo_base64."""
    d = _Doc(empresa, "ORDEN DE SERVICIO", r)
    fecha = r.get("creado_en") or ""
    d.encabezado(fecha)
    d.datos([("Fecha", _fecha_larga(fecha)), ("Hora", fecha[11:16] if len(fecha) >= 16 else ""),
             ("Tipo de servicio", TIPOS.get(r.get("tipo_servicio"), r.get("tipo_servicio"))), ("Atendió", r.get("creado_por_nombre"))])
    d.seccion("Datos del cliente")
    _datos_cliente(d, r)
    d.seccion("Equipo")
    _datos_equipo(d, r)
    d.seccion("Problema reportado")
    d.texto(r.get("problema"))
    if evidencias:
        if not d.fotos(evidencias, titulo="Evidencia enviada por el cliente"):
            d.seccion("Evidencia enviada por el cliente")
            d.texto(f"{len(evidencias)} archivo(s) de evidencia (videos o documentos) en el expediente.")
        else:
            otros = sum(1 for e in evidencias if not (e.get("tipo") or "").startswith("image"))
            if otros:
                d.h.append(Paragraph(f"Además, {otros} video(s)/documento(s) en el expediente.", d.s["chico"]))
    condiciones = d.seccion("Condiciones del servicio", devolver=True) + [Paragraph(
        "El cliente autoriza a " + _e(d.nombre_empresa or "la empresa") + " a revisar y diagnosticar el equipo descrito. "
        "El diagnóstico determinará la causa de la falla y la solución. "
        + ("En servicios de garantía, la cobertura queda sujeta al dictamen técnico (no cubre mal uso, golpes, "
           "instalación inadecuada ni piezas de desgaste). " if r.get("tipo_servicio") == "garantia" else
           "Cualquier costo se informa por separado antes de realizar trabajos adicionales. ")
        + "Con su firma, el cliente confirma que los datos y el problema reportado son correctos.", d.s["chico"])]
    # Firma
    s = d.s
    if r.get("firma_base64"):
        im = _imagen(r["firma_base64"], 6.5 * cm, 2.6 * cm)
        origen = "en persona" if r.get("firma_origen") == "presencial" else "electrónicamente desde la liga enviada al cliente"
        bloque = [im or Spacer(1, 30),
                  Table([[""]], colWidths=[7 * cm], style=[("LINEABOVE", (0, 0), (-1, -1), 0.8, TINTA)]),
                  Paragraph(f"<b>{_e(r.get('firma_nombre'))}</b>", ParagraphStyle("fn", parent=s["celda"], alignment=TA_CENTER)),
                  Paragraph(f"Firmó {origen} el {_e(_fecha_larga(r.get('firma_en')))} a las {_e((r.get('firma_en') or '')[11:16])}"
                            + (f" · IP {_e(r.get('firma_ip'))}" if r.get("firma_ip") and r.get("firma_origen") != "presencial" else ""),
                            ParagraphStyle("fo", parent=s["chico"], alignment=TA_CENTER))]
    else:
        bloque = [Spacer(1, 40), Table([[""]], colWidths=[7 * cm], style=[("LINEABOVE", (0, 0), (-1, -1), 0.8, TINTA)]),
                  Paragraph("Nombre y firma de conformidad del cliente", ParagraphStyle("fn", parent=s["chico"], alignment=TA_CENTER))]
        if liga:
            bloque.append(Paragraph(f"Firma desde tu celular: {_e(liga)}", ParagraphStyle("fl", parent=s["chico"], alignment=TA_CENTER)))
    t = Table([[bloque]], colWidths=[ANCHO])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    d.h += [KeepTogether(condiciones + [Spacer(1, 14), t])]
    return d.construir(f"{d.nombre_empresa} · Orden de servicio {folio_txt(r)}")


def resolucion_pdf(r, empresa, evidencias, liga_encuesta=None):
    """Diagnóstico y resolución para el cliente. SIN costos ni apartado interno."""
    d = _Doc(empresa, "DIAGNÓSTICO Y RESOLUCIÓN", r)
    fecha = r.get("resolucion_enviada_en") or r.get("actualizado_en") or r.get("creado_en") or ""
    d.encabezado(fecha)
    d.datos([("Fecha", _fecha_larga(fecha)), ("Orden de servicio", f"{folio_txt(r)} del {_fecha_corta(r.get('creado_en'))}"),
             ("Cliente", r.get("cliente_nombre")), ("Teléfono", r.get("cliente_telefono"))])
    d.seccion("Equipo")
    _datos_equipo(d, r)
    d.seccion("Problema reportado")
    d.texto(r.get("problema"))
    d.seccion("Diagnóstico")
    d.texto(r.get("diagnostico"))
    refacciones = [x for x in (r.get("refacciones") or []) if (x.get("descripcion") or "").strip()]
    if refacciones:
        d.seccion("Refacciones")
        s = d.s
        filas = [[Paragraph(x, s["encab"]) for x in ("#", "Cantidad", "Descripción", "No. de parte")]]
        for i, x in enumerate(refacciones, 1):
            filas.append([Paragraph(str(i), s["celda"]), Paragraph(_e(x.get("cantidad") or 1), s["celda"]),
                          Paragraph(_e(x.get("descripcion")), s["celda"]), Paragraph(_e(x.get("numero_parte") or "—"), s["celda"])])
        d.tabla(filas, [0.8 * cm, 2 * cm, ANCHO - 0.8 * cm - 2 * cm - 4 * cm, 4 * cm])
    d.seccion("Qué se va a hacer")
    d.texto(r.get("resolucion"))
    d.seccion("Envío")
    ocurre = r.get("ocurre")
    d.datos([("Paquetería", r.get("paqueteria")),
             ("Entrega en ocurre", "Sí — se recoge en la sucursal de la paquetería" if ocurre else ("No — entrega a domicilio" if ocurre is False else "")),
             ("Dirección", r.get("cliente_direccion")), ("Ciudad", r.get("cliente_ciudad"))])
    if evidencias:
        d.fotos(evidencias, titulo="Evidencia del diagnóstico")
    if liga_encuesta:
        s = d.s
        caja = Table([[Paragraph("<b>¿Cómo te fue con tu equipo y con nuestro servicio?</b><br/>"
                                 f"Ayúdanos contestando una encuesta de 1 minuto: {_e(liga_encuesta)}", s["base"])]],
                     colWidths=[ANCHO])
        caja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, d.acento), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
        d.h += [Spacer(1, 14), caja]
    return d.construir(f"{d.nombre_empresa} · Diagnóstico y resolución {folio_txt(r)}")
