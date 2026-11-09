# -*- coding: utf-8 -*-
"""PDFs de Dirección → Consultas → Pedidos pendientes (app Mark·Inc):
- un pedido (sus artículos pendientes de surtir),
- varios pedidos en un solo archivo (uno por hoja),
- todos los productos de los pedidos elegidos, sumados (para surtir / comprar).
Mismo estilo que los demás PDFs (logo de la empresa, acento rojo)."""
import base64
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROJO = colors.HexColor("#D8192F")
GRIS = colors.HexColor("#74767A")
NEGRO = colors.HexColor("#1C1E1B")
GRIS_CLARO = colors.HexColor("#F2F2F2")
ANCHO = letter[0] - 3 * cm


def _logo(empresa):
    b64 = (empresa or {}).get("logo_base64")
    if not b64:
        return None
    try:
        datos = base64.b64decode(b64.split(",", 1)[1] if "," in b64 else b64)
        iw, ih = ImageReader(BytesIO(datos)).getSize()
        alto = 1.4 * cm
        return Image(BytesIO(datos), width=alto * iw / ih, height=alto)
    except Exception:
        return None


def _estilos():
    s = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("t", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NEGRO),
        "sub": ParagraphStyle("s", parent=s["Normal"], fontSize=9, leading=12, textColor=GRIS),
        "celda": ParagraphStyle("c", parent=s["Normal"], fontSize=8.5, leading=10.5, textColor=NEGRO),
        "celda_b": ParagraphStyle("cb", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=NEGRO),
        "enc": ParagraphStyle("e", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white),
        "dato": ParagraphStyle("d", parent=s["Normal"], fontSize=9.5, leading=13, textColor=NEGRO),
    }


def _num(v):
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    return f"{n:,.0f}" if abs(n - round(n)) < 0.005 else f"{n:,.2f}"


def _dinero(v):
    if v is None:
        return "—"
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _fecha(v):
    t = str(v or "")
    return f"{t[8:10]}/{t[5:7]}/{t[0:4]}" if len(t) >= 10 else t


def _encabezado(el, est, empresa, titulo, sub):
    logo = _logo(empresa)
    textos = [Paragraph(escape(titulo), est["titulo"]), Paragraph(sub, est["sub"])]
    if logo:
        t = Table([[textos, logo]], colWidths=[ANCHO - 5 * cm, 5 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        el.append(t)
    else:
        el.extend(textos)
    el.append(Spacer(1, 4))
    linea = Table([[""]], colWidths=[ANCHO], rowHeights=[2])
    linea.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ROJO)]))
    el.append(linea)
    el.append(Spacer(1, 10))


def _tabla(est, encabezados, filas, anchos, derecha=(), total=None):
    def p(texto, estilo, col):
        if col in derecha:
            estilo = ParagraphStyle(estilo.name + "_d", parent=estilo, alignment=2)
        return Paragraph(escape(str(texto)), estilo)
    datos = [[p(h, est["enc"], i) for i, h in enumerate(encabezados)]]
    for f in filas:
        datos.append([p(c, est["celda"], i) for i, c in enumerate(f)])
    if total:
        datos.append([p(c, est["celda_b"], i) for i, c in enumerate(total)])
    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for i in range(1, len(datos)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    if total:
        estilo += [("BACKGROUND", (0, len(datos) - 1), (-1, len(datos) - 1), colors.HexColor("#FDE8EA")),
                   ("LINEABOVE", (0, len(datos) - 1), (-1, len(datos) - 1), 1, ROJO)]
    t.setStyle(TableStyle(estilo))
    return t


def _pie(texto):
    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        ahora = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%d/%m/%Y %H:%M")
        canvas.drawString(1.5 * cm, 1.1 * cm, f"{texto} · generado el {ahora}")
        canvas.drawRightString(letter[0] - 1.5 * cm, 1.1 * cm, f"Hoja {doc_.page}")
        canvas.restoreState()
    return pie


def _documento(buffer):
    return SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.4 * cm, bottomMargin=1.7 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)


def _bloque_pedido(el, est, empresa, pedido, sucursal, rango):
    _encabezado(el, est, empresa, f"Pedido {pedido.get('folio') or ''}",
                f"Pendiente de surtir · {escape(sucursal)}")
    datos = [
        ["Cliente:", pedido.get("cliente_nombre") or "—", "Fecha:", _fecha(pedido.get("fecha"))],
        ["Capturó:", pedido.get("capturado_por") or "—", "Periodo:", rango],
    ]
    t = Table([[Paragraph(f"<b>{escape(str(a))}</b>", est["dato"]) if i % 2 == 0 else Paragraph(escape(str(a)), est["dato"])
                for i, a in enumerate(f)] for f in datos], colWidths=[2.2 * cm, ANCHO / 2 - 2.2 * cm, 2 * cm, ANCHO / 2 - 2 * cm])
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    el.append(t)
    el.append(Spacer(1, 10))
    items = pedido.get("items") or []
    filas = [[i.get("clave") or "", i.get("nombre") or "", _num(i.get("cantidad_pendiente")),
              _dinero(i.get("precio_unitario_con_iva")), _dinero(i.get("total_con_iva"))] for i in items]
    total = ["", f"{len(items)} artículo(s)", _num(pedido.get("total_piezas_pendientes")), "",
             _dinero(pedido.get("total_pedido_con_iva"))]
    el.append(_tabla(est, ["Clave", "Artículo", "Piezas", "Precio c/IVA", "Importe c/IVA"], filas,
                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total))


def pdf_pedidos(empresa, pedidos, sucursal, rango):
    """Un PDF con uno o varios pedidos, cada uno en su hoja."""
    buffer = BytesIO()
    doc = _documento(buffer)
    est = _estilos()
    el = []
    for i, p in enumerate(pedidos):
        if i:
            el.append(PageBreak())
        _bloque_pedido(el, est, empresa, p, sucursal, rango)
    if not el:
        el.append(Paragraph("No hay pedidos pendientes con esos datos.", est["dato"]))
    texto = f"Pedido {pedidos[0].get('folio')}" if len(pedidos) == 1 else f"{len(pedidos)} pedidos pendientes · {sucursal}"
    doc.build(el, onFirstPage=_pie(texto), onLaterPages=_pie(texto))
    return buffer.getvalue()


def pdf_productos(empresa, pedidos, sucursal, rango):
    """Todos los artículos de los pedidos, sumados (cuántas piezas y en cuántos pedidos)."""
    suma = {}
    for p in pedidos:
        for it in p.get("items") or []:
            k = it.get("articulo_id") or f"{it.get('clave')}|{it.get('nombre')}"
            s = suma.setdefault(k, {"clave": it.get("clave") or "", "nombre": it.get("nombre") or "", "piezas": 0.0,
                                    "pedidos": set(), "importe": 0.0})
            s["piezas"] += float(it.get("cantidad_pendiente") or 0)
            s["pedidos"].add(p.get("folio"))
            s["importe"] += float(it.get("total_con_iva") or 0)
    filas = sorted(suma.values(), key=lambda s: (-s["piezas"], s["nombre"]))
    buffer = BytesIO()
    doc = _documento(buffer)
    est = _estilos()
    el = []
    folios = ", ".join(str(p.get("folio")) for p in pedidos[:40]) + (f" y {len(pedidos) - 40} más" if len(pedidos) > 40 else "")
    _encabezado(el, est, empresa, "Productos de pedidos pendientes",
                f"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}")
    tabla = [[s["clave"], s["nombre"], _num(s["piezas"]), str(len(s["pedidos"])), _dinero(s["importe"])] for s in filas]
    total = ["", f"{len(filas)} artículo(s)", _num(sum(s["piezas"] for s in filas)), str(len(pedidos)),
             _dinero(sum(s["importe"] for s in filas))]
    el.append(_tabla(est, ["Clave", "Artículo", "Piezas", "Pedidos", "Importe c/IVA"], tabla,
                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total))
    doc.build(el, onFirstPage=_pie("Productos de pedidos pendientes"), onLaterPages=_pie("Productos de pedidos pendientes"))
    return buffer.getvalue()
