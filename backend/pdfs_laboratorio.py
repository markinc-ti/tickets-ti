# -*- coding: utf-8 -*-
"""Genera el PDF de "Orden de trabajo" del módulo de Laboratorio: datos del
solicitante, el odontograma dibujado con los dientes marcados y numerados,
el desglose de piezas/costos, el pago, y la firma de recepción.

No depende de matplotlib ni de ninguna librería nueva — se dibuja directo
sobre el canvas de reportlab (la misma librería que ya usan los demás PDFs
de la app), así que no hace falta agregar nada al requirements.txt.
"""
import base64
import io
import math

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.lib.utils import ImageReader

COPPER = colors.HexColor("#D8192F")
COPPER_DARK = colors.HexColor("#A81124")
INK = colors.HexColor("#201F1E")
MUTED = colors.HexColor("#6B6D70")
LINE = colors.HexColor("#DDD9D3")
PANEL_BG = colors.HexColor("#F6F4F1")
GRIS_DIENTE = colors.HexColor("#C9C7C4")

NOMBRES_TIPO_SOLICITANTE = {"estudiante": "Estudiante", "doctor": "Doctor"}
NOMBRES_TIPO_TRABAJO = {
    "corona": "Corona", "implante": "Implante", "puente": "Puente",
    "carilla": "Carilla", "incrustacion": "Incrustación", "otro": "Otro",
}
NOMBRES_MATERIAL = {"zirconia": "Zirconia", "disilicato": "Disilicato"}
NOMBRES_METODO_PAGO = {
    "efectivo": "Efectivo", "tarjeta_debito": "Tarjeta de débito", "tarjeta_credito": "Tarjeta de crédito",
    "transferencia": "Transferencia", "otro": "Otro",
}

PAGE_W, PAGE_H = letter
MARGIN = 1.8 * cm


def _fmt_moneda(n):
    try:
        return f"${float(n):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _imagen_desde_base64(data_uri):
    """Regresa un ImageReader (o None) a partir de un data-URI base64
    (data:image/png;base64,...) tal como los guarda la app."""
    if not data_uri:
        return None
    try:
        if "," in data_uri:
            data_uri = data_uri.split(",", 1)[1]
        raw = base64.b64decode(data_uri)
        return ImageReader(io.BytesIO(raw))
    except Exception:
        return None


# ---------------------------------------------------------------- odontograma
def _posiciones_odontograma(cx, cy_top, escala=1.0):
    """Mismo cálculo geométrico que usa el odontograma de la app (arcos tipo
    Maxila/Mandíbula), adaptado a coordenadas de reportlab (Y hacia arriba)."""
    R = 90 * escala
    apex_sup, ancho_sup = 38 * escala, 82 * escala
    apex_inf, ancho_inf = 255 * escala, 82 * escala

    def posicion(p):
        ang = (p - 0.5) / 8 * (math.pi * 0.53)
        return R * math.sin(ang), 1 - math.cos(ang)

    puntos = {}

    def agregar(nums, lado, arco):
        for i, num in enumerate(nums):
            p = i + 1
            dx, sube = posicion(p)
            x = cx + (-dx if lado == "izq" else dx)
            y_offset = apex_sup + ancho_sup * sube if arco == "sup" else apex_inf - ancho_inf * sube
            y = cy_top - y_offset
            puntos[str(num)] = (x, y)

    agregar([11, 12, 13, 14, 15, 16, 17, 18], "izq", "sup")
    agregar([21, 22, 23, 24, 25, 26, 27, 28], "der", "sup")
    agregar([41, 42, 43, 44, 45, 46, 47, 48], "izq", "inf")
    agregar([31, 32, 33, 34, 35, 36, 37, 38], "der", "inf")
    return puntos


def _dibujar_odontograma(c, x0, y0, ancho, piezas):
    """Dibuja el odontograma completo dentro del rectángulo que empieza en
    (x0, y0) [esquina superior izquierda] con el ancho dado. Los dientes que
    tienen pieza salen numerados (1, 2, 3…) en el mismo orden que la tabla
    de abajo — así el número en el diente ES la referencia a su renglón."""
    cx = x0 + ancho / 2
    puntos = _posiciones_odontograma(cx, y0, escala=ancho / 260.0)
    r_diente = 8.2 * (ancho / 260.0)

    por_diente = {p["diente"]: i + 1 for i, p in enumerate(piezas)}

    c.setFont("Helvetica-Bold", 8)
    for diente, (x, y) in puntos.items():
        indice = por_diente.get(diente)
        if indice:
            c.setFillColor(COPPER)
            c.setStrokeColor(COPPER_DARK)
        else:
            c.setFillColor(colors.white)
            c.setStrokeColor(GRIS_DIENTE)
        c.setLineWidth(1)
        c.circle(x, y, r_diente, stroke=1, fill=1)
        c.setFillColor(colors.white if indice else MUTED)
        c.setFont("Helvetica-Bold", 6.4)
        c.drawCentredString(x, y - 2.2, diente)
        if indice:
            # Numerito de referencia, arriba a la derecha del círculo
            bx, by = x + r_diente * 0.78, y + r_diente * 0.78
            c.setFillColor(COPPER_DARK)
            c.circle(bx, by, 5, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 6.6)
            c.drawCentredString(bx, by - 2.1, str(indice))

    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(cx, y0 - 305 * (ancho / 260.0), "Numeración FDI — el número en rojo indica el renglón de la tabla")


# ---------------------------------------------------------------- documento
def generar_orden_trabajo(trabajo: dict, empresa: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=letter)
    y = PAGE_H - MARGIN

    nombre_empresa = (empresa or {}).get("nombre") or "Mark·Inc"

    # ---- encabezado ----
    c.setFillColor(INK)
    c.rect(0, PAGE_H - 2.3 * cm, PAGE_W, 2.3 * cm, fill=1, stroke=0)
    c.setFillColor(COPPER)
    c.rect(0, PAGE_H - 2.3 * cm, PAGE_W, 0.1 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, PAGE_H - 1.05 * cm, nombre_empresa)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, PAGE_H - 1.55 * cm, "Orden de trabajo — Laboratorio dental")
    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.15 * cm, trabajo.get("folio", ""))
    c.setFont("Helvetica", 8.5)
    fecha_recepcion = (trabajo.get("fecha_recepcion") or "")[:16].replace("T", " ")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.6 * cm, f"Recibido: {fecha_recepcion}")

    y = PAGE_H - 2.9 * cm

    # ---- datos del solicitante ----
    def campo(label, valor, x, yy, ancho_col=8.6 * cm):
        c.setFont("Helvetica-Bold", 7.2)
        c.setFillColor(MUTED)
        c.drawString(x, yy, label.upper())
        c.setFont("Helvetica", 9.5)
        c.setFillColor(INK)
        c.drawString(x, yy - 12, str(valor) if valor not in (None, "") else "—")

    col1, col2 = MARGIN, MARGIN + 9 * cm
    campo("Solicitante", f"{trabajo.get('solicitante_nombre','—')} ({NOMBRES_TIPO_SOLICITANTE.get(trabajo.get('solicitante_tipo'), '')})", col1, y)
    campo("Universidad / Clínica", trabajo.get("universidad_clinica"), col2, y)
    y -= 30
    campo("Teléfono", trabajo.get("telefono"), col1, y)
    campo("Paciente", trabajo.get("paciente_nombre"), col2, y)
    y -= 30
    campo("Sucursal", trabajo.get("sucursal_nombre"), col1, y)
    campo("Fecha compromiso", trabajo.get("fecha_compromiso"), col2, y)
    y -= 30
    campo("Folio de escaneo", trabajo.get("folio_escaneo"), col1, y)
    campo("¿Requiere factura?", "Sí" if trabajo.get("requiere_factura") else "No", col2, y)
    y -= 26

    if trabajo.get("notas"):
        c.setFont("Helvetica-Bold", 7.2)
        c.setFillColor(MUTED)
        c.drawString(col1, y, "NOTAS")
        c.setFont("Helvetica", 9)
        c.setFillColor(INK)
        c.drawString(col1, y - 12, str(trabajo["notas"])[:120])
        y -= 26

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 18

    # ---- odontograma + tabla de piezas, lado a lado ----
    piezas = trabajo.get("piezas") or []
    odonto_ancho = 7.6 * cm
    odonto_top = y
    _dibujar_odontograma(c, MARGIN, odonto_top, odonto_ancho, piezas)

    tabla_x = MARGIN + odonto_ancho + 0.7 * cm
    tabla_ancho = PAGE_W - MARGIN - tabla_x
    ty = y
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(COPPER_DARK)
    c.drawString(tabla_x, ty, f"Piezas del odontograma ({len(piezas)})")
    ty -= 16

    encabezados = ["#", "Diente", "Trabajo", "Material", "Color", "Costo"]
    anchos = [0.32, 0.62, 1.55, 1.15, 0.78, 1.0]
    anchos = [a / sum(anchos) * tabla_ancho for a in anchos]
    c.setFillColor(COPPER_DARK)
    c.rect(tabla_x, ty - 14, tabla_ancho, 14, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.3)
    cx = tabla_x
    for h, a in zip(encabezados, anchos):
        c.drawString(cx + 3, ty - 10, h)
        cx += a
    ty -= 14

    for i, p in enumerate(piezas):
        fila_h = 15
        if i % 2 == 1:
            c.setFillColor(PANEL_BG)
            c.rect(tabla_x, ty - fila_h, tabla_ancho, fila_h, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica", 7.6)
        valores = [
            str(i + 1), p.get("diente", ""), NOMBRES_TIPO_TRABAJO.get(p.get("tipo_trabajo"), p.get("tipo_trabajo", "")),
            NOMBRES_MATERIAL.get(p.get("material"), p.get("material") or "—"),
            p.get("color") or "—", _fmt_moneda(p.get("costo", 0)),
        ]
        cx = tabla_x
        for v, a in zip(valores, anchos):
            c.drawString(cx + 3, ty - fila_h + 4, str(v)[:22])
            cx += a
        ty -= fila_h
        if ty < 8 * cm:
            break  # se corta razonable; el odontograma ya trae la numeración completa

    ty -= 6
    c.setStrokeColor(LINE)
    c.line(tabla_x, ty, tabla_x + tabla_ancho, ty)
    ty -= 14
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(COPPER_DARK)
    c.drawString(tabla_x, ty, f"Costo total: {_fmt_moneda(trabajo.get('costo_total', 0))}")

    y = min(odonto_top - 320, ty) - 20

    # ---- pago ----
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 16
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(COPPER_DARK)
    c.drawString(MARGIN, y, "Pago")
    y -= 14
    metodos = trabajo.get("pago_metodos") or []
    c.setFont("Helvetica", 9)
    c.setFillColor(INK)
    if metodos:
        texto_pago = "  ·  ".join(f"{NOMBRES_METODO_PAGO.get(m['metodo'], m['metodo'])}: {_fmt_moneda(m['monto'])}" for m in metodos)
        c.drawString(MARGIN, y, texto_pago)
    else:
        c.drawString(MARGIN, y, "— sin pago registrado —")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(PAGE_W - MARGIN, y, f"Total pagado: {_fmt_moneda(trabajo.get('pago_monto_total', 0))}")
    y -= 30

    # ---- firma ----
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 16
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(COPPER_DARK)
    c.drawString(MARGIN, y, "Firma de recepción")
    y -= 4
    firma_img = _imagen_desde_base64(trabajo.get("firma_recepcion"))
    if firma_img:
        alto_firma = 2.6 * cm
        c.drawImage(firma_img, MARGIN, y - alto_firma - 6, width=6.5 * cm, height=alto_firma,
                    preserveAspectRatio=True, anchor="sw", mask="auto")
        y -= (alto_firma + 14)
    else:
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, y - 16, "— sin firma registrada —")
        y -= 26
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, y, f"{trabajo.get('solicitante_nombre','')} — {NOMBRES_TIPO_SOLICITANTE.get(trabajo.get('solicitante_tipo'), '')}")

    # ---- pie ----
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, 1.1 * cm, f"{nombre_empresa} · Orden de trabajo generada por Tickets-TI · Folio {trabajo.get('folio','')}")

    c.showPage()
    c.save()
    return buf.getvalue()
