# -*- coding: utf-8 -*-
"""Formato PDF media carta de una solicitud de vacaciones o de permiso.

Se comparte en grupos de trabajo, así que NUNCA imprime el motivo, el
comentario ni el tipo de incidencia que lo revela (enfermedad, lesión,
accidente…): en su lugar dice que los motivos los conocen el jefe directo y
Recursos Humanos.
"""
import base64
import io
import math
from datetime import date, datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import calendario_laboral

MEDIA_CARTA = (5.5 * inch, 8.5 * inch)
ROJO = colors.HexColor("#B3121F")
GRIS = colors.HexColor("#5F6368")
GRIS_CLARO = colors.HexColor("#E6E7E9")
FONDO = colors.HexColor("#F6F6F7")
TINTA = colors.HexColor("#1F2328")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Lo que se imprime como "tipo": nada que revele la causa.
TIPO_IMPRESO = {
    "permiso_horas": "Permiso por horas",
    "dia_libre_sin_goce": "Día sin goce de sueldo",
}
TIPO_GENERICO = "Permiso de ausencia"

ESTADOS = {
    "pendiente": ("PENDIENTE DE AUTORIZAR", colors.HexColor("#B7791F")),
    "pendiente_encargado": ("PENDIENTE DE AUTORIZAR", colors.HexColor("#B7791F")),
    "propuesta_empleado": ("PENDIENTE DE AUTORIZAR", colors.HexColor("#B7791F")),
    "aprobada": ("AUTORIZADA", colors.HexColor("#1A7F37")),
    "pagada": ("AUTORIZADA", colors.HexColor("#1A7F37")),
    "rechazada": ("NO AUTORIZADA", ROJO),
    "cancelada": ("CANCELADA", GRIS),
}

NOTA_MOTIVO = ("Confidencial. Los motivos de esta ausencia los conocen únicamente "
               "el jefe directo y Recursos Humanos.")


def _fecha(v):
    if not v:
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) and not isinstance(v, datetime) else v.date()
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def fecha_larga(v, con_dia=True):
    d = _fecha(v)
    if not d:
        return "—"
    txt = f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    return f"{DIAS[d.weekday()].capitalize()} {txt}" if con_dia else txt


def _num(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return "0"
    return f"{f:g}"


def _horas_txt(h):
    try:
        h = float(h or 0)
    except (TypeError, ValueError):
        return ""
    total = round(h * 60)
    hh, mm_ = divmod(total, 60)
    partes = []
    if hh:
        partes.append(f"{hh} hora{'s' if hh != 1 else ''}")
    if mm_:
        partes.append(f"{mm_} minutos")
    return " y ".join(partes) or "0 horas"


def rango_vacaciones(fecha_inicio, dias):
    """Último día y día de regreso contando solo días laborables: no cuentan
    los domingos ni los festivos oficiales (ver calendario_laboral)."""
    d = _fecha(fecha_inicio)
    if not d:
        return None, None
    _, fin, regreso, _ = calendario_laboral.rango_laboral(d, dias)
    return fin, regreso


def _logo(logo_base64):
    if not logo_base64:
        return None
    try:
        crudo = logo_base64.split(",", 1)[1] if "," in logo_base64 else logo_base64
        return ImageReader(io.BytesIO(base64.b64decode(crudo)))
    except Exception:
        return None


def _firma(firma_base64):
    return _logo(firma_base64)


def _texto_ajustado(c, texto, x, y, ancho, fuente="Helvetica", tam=8, interlinea=10.5, color=TINTA):
    """Escribe un párrafo partido en líneas; regresa la y final."""
    c.setFont(fuente, tam)
    c.setFillColor(color)
    palabras, linea = texto.split(), ""
    for p in palabras:
        prueba = (linea + " " + p).strip()
        if c.stringWidth(prueba, fuente, tam) > ancho and linea:
            c.drawString(x, y, linea)
            y -= interlinea
            linea = p
        else:
            linea = prueba
    if linea:
        c.drawString(x, y, linea)
        y -= interlinea
    return y


def generar(d):
    """d: {
        empresa, logo_base64, titulo ('SOLICITUD DE VACACIONES' / 'SOLICITUD DE PERMISO'),
        folio, solicitada_en, persona: {nombre, puesto, departamento, sucursal, numero_empleado, jefe_directo},
        detalle: [(etiqueta, valor), ...], estado, resuelto_por, resuelto_en,
        firma_jefe_base64, firma_jefe_nombre
    } -> bytes del PDF."""
    buf = io.BytesIO()
    W, H = MEDIA_CARTA
    c = canvas.Canvas(buf, pagesize=MEDIA_CARTA)
    c.setTitle(f"{d.get('titulo', 'Solicitud')} {d.get('folio', '')}".strip())
    c.setAuthor(d.get("empresa") or "")
    m = 14 * mm
    ancho = W - 2 * m

    # Encabezado
    c.setFillColor(ROJO)
    c.rect(0, H - 6, W, 6, stroke=0, fill=1)
    y = H - 18 * mm
    logo = _logo(d.get("logo_base64"))
    x_txt = m
    if logo:
        try:
            iw, ih = logo.getSize()
            alto = 12 * mm
            an = min(alto * iw / ih, 30 * mm)
            c.drawImage(logo, m, y - 3 * mm, width=an, height=alto, mask="auto", preserveAspectRatio=True, anchor="w")
            x_txt = m + an + 4 * mm
        except Exception:
            pass
    c.setFillColor(TINTA)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x_txt, y + 4 * mm, (d.get("empresa") or "")[:48])
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GRIS)
    c.drawString(x_txt, y, "Recursos Humanos")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(ROJO)
    c.drawRightString(W - m, y + 4 * mm, d.get("folio") or "")
    c.setFont("Helvetica", 7)
    c.setFillColor(GRIS)
    c.drawRightString(W - m, y, f"Solicitada: {fecha_larga(d.get('solicitada_en'), con_dia=False)}")

    y -= 8 * mm
    c.setStrokeColor(GRIS_CLARO)
    c.setLineWidth(0.8)
    c.line(m, y, W - m, y)
    y -= 9 * mm
    c.setFillColor(TINTA)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, y, d.get("titulo") or "SOLICITUD")

    # Estatus
    etiqueta, color = ESTADOS.get(d.get("estado") or "pendiente", ESTADOS["pendiente"])
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 7.5)
    aw = c.stringWidth(etiqueta, "Helvetica-Bold", 7.5) + 8 * mm
    c.setFillColor(color)
    c.roundRect(W / 2 - aw / 2, y - 1.6 * mm, aw, 5.4 * mm, 2.6 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.drawCentredString(W / 2, y, etiqueta)

    def seccion(titulo, filas, y):
        y -= 8 * mm
        c.setFillColor(ROJO)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(m, y, titulo.upper())
        y -= 2.2 * mm
        alto_fila = 6.4 * mm
        caja = alto_fila * len(filas) + 1.5 * mm
        c.setFillColor(FONDO)
        c.setStrokeColor(GRIS_CLARO)
        c.roundRect(m, y - caja, ancho, caja, 2 * mm, stroke=1, fill=1)
        y -= 1 * mm
        for i, (k, v) in enumerate(filas):
            yy = y - alto_fila * i - 4.3 * mm
            c.setFont("Helvetica", 7)
            c.setFillColor(GRIS)
            c.drawString(m + 3 * mm, yy, k)
            c.setFont("Helvetica-Bold", 8.2)
            c.setFillColor(TINTA)
            v = str(v or "—")
            while c.stringWidth(v, "Helvetica-Bold", 8.2) > ancho - 36 * mm and len(v) > 4:
                v = v[:-2]
            c.drawString(m + 33 * mm, yy, v)
            if i < len(filas) - 1:
                c.setStrokeColor(GRIS_CLARO)
                c.line(m + 3 * mm, yy - 2.1 * mm, W - m - 3 * mm, yy - 2.1 * mm)
        return y - caja

    p = d.get("persona") or {}
    filas_p = [("Nombre", p.get("nombre")), ("Puesto", p.get("puesto"))]
    if p.get("departamento"):
        filas_p.append(("Departamento", p.get("departamento")))
    if p.get("sucursal"):
        filas_p.append(("Sucursal", p.get("sucursal")))
    if p.get("numero_empleado"):
        filas_p.append(("No. de empleado", p.get("numero_empleado")))
    if p.get("jefe_directo"):
        filas_p.append(("Jefe directo", p.get("jefe_directo")))
    y = seccion("Datos del colaborador", filas_p, y)
    y = seccion("Detalle de la solicitud", list(d.get("detalle") or []), y)

    # Motivo (nunca se imprime)
    y -= 8 * mm
    c.setFillColor(ROJO)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(m, y, "MOTIVO")
    y -= 2.2 * mm
    caja = 11 * mm
    c.setFillColor(colors.white)
    c.setStrokeColor(GRIS_CLARO)
    c.setDash(2, 2)
    c.roundRect(m, y - caja, ancho, caja, 2 * mm, stroke=1, fill=1)
    c.setDash()
    c.setFont("Helvetica-Oblique", 7.6)
    _texto_ajustado(c, NOTA_MOTIVO, m + 3 * mm, y - 4.4 * mm, ancho - 6 * mm,
                    fuente="Helvetica-Oblique", tam=7.6, interlinea=9.5, color=GRIS)
    y -= caja

    # Autorización
    if d.get("resuelto_por") and d.get("estado") in ("aprobada", "pagada", "rechazada", "cancelada"):
        y -= 5.5 * mm
        verbo = {"rechazada": "No autorizada", "cancelada": "Cancelada"}.get(d.get("estado"), "Autorizada")
        c.setFont("Helvetica", 7)
        c.setFillColor(GRIS)
        c.drawString(m, y, f"{verbo} por {d['resuelto_por']}"
                           + (f" el {fecha_larga(d.get('resuelto_en'), con_dia=False)}" if d.get("resuelto_en") else ""))

    # Firmas
    firmas = [("Colaborador", p.get("nombre")),
              ("Jefe directo", d.get("firma_jefe_nombre") or p.get("jefe_directo")),
              ("Recursos Humanos", None)]
    yf = 24 * mm
    col = ancho / 3
    img = _firma(d.get("firma_jefe_base64"))
    for i, (rol, nombre) in enumerate(firmas):
        x0 = m + col * i + 2.5 * mm
        x1 = m + col * (i + 1) - 2.5 * mm
        if i == 1 and img:
            try:
                c.drawImage(img, x0, yf + 0.8 * mm, width=x1 - x0, height=11 * mm, mask="auto", preserveAspectRatio=True)
            except Exception:
                pass
        c.setStrokeColor(TINTA)
        c.setLineWidth(0.6)
        c.line(x0, yf, x1, yf)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(TINTA)
        c.drawCentredString((x0 + x1) / 2, yf - 3.6 * mm, rol)
        if nombre:
            c.setFont("Helvetica", 6.3)
            c.setFillColor(GRIS)
            n = str(nombre)
            while c.stringWidth(n, "Helvetica", 6.3) > x1 - x0 and len(n) > 4:
                n = n[:-2]
            c.drawCentredString((x0 + x1) / 2, yf - 6.6 * mm, n)

    # Pie
    c.setStrokeColor(GRIS_CLARO)
    c.line(m, 11 * mm, W - m, 11 * mm)
    c.setFont("Helvetica", 6)
    c.setFillColor(GRIS)
    c.drawString(m, 7.5 * mm, f"Generado el {fecha_larga(d.get('generado_en') or date.today(), con_dia=False)}")
    c.drawRightString(W - m, 7.5 * mm, d.get("empresa") or "")
    c.setFillColor(ROJO)
    c.rect(0, 0, W, 2.5, stroke=0, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------- Armar los datos de cada tipo de solicitud ----------

def detalle_vacaciones(fecha_inicio, dias):
    fin, regreso = rango_vacaciones(fecha_inicio, dias)
    d0 = _fecha(fecha_inicio)
    brincados = calendario_laboral.rango_laboral(d0, dias)[3] if d0 else []
    festivos_txt = ", ".join(f"{f.day} {MESES[f.month - 1][:3]}" for f, n in brincados if n != "Domingo")
    dias_f = float(dias or 0)
    filas = [("Tipo", "Vacaciones"),
             ("Días solicitados", f"{_num(dias_f)} día{'s' if dias_f != 1 else ''}" + (" (incluye medio día)" if dias_f != int(dias_f) else "")),
             ("Desde", fecha_larga(fecha_inicio))]
    if fin:
        filas.append(("Último día", fecha_larga(fin)))
        filas.append(("Regresa a laborar", fecha_larga(regreso)))
        filas.append(("No se cuentan", "Domingos y festivos" + (f" ({festivos_txt})" if festivos_txt else "")))
    return filas


def detalle_incidencia(inc):
    tipo = inc.get("tipo")
    filas = [("Tipo", TIPO_IMPRESO.get(tipo, TIPO_GENERICO))]
    ini, fin = inc.get("fecha_inicio"), inc.get("fecha_fin")
    horas = inc.get("horas")
    if horas and float(horas) > 0:
        filas.append(("Fecha", fecha_larga(ini)))
        filas.append(("Duración", _horas_txt(horas)))
    elif fin and str(fin)[:10] != str(ini)[:10]:
        a, b = _fecha(ini), _fecha(fin)
        filas.append(("Desde", fecha_larga(ini)))
        filas.append(("Hasta", fecha_larga(fin)))
        if a and b:
            n = (b - a).days + 1
            filas.append(("Duración", f"{n} día{'s' if n != 1 else ''} naturales"))
    else:
        filas.append(("Fecha", fecha_larga(ini)))
        filas.append(("Duración", "Día completo"))
    return filas
