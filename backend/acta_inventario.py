# -*- coding: utf-8 -*-
"""
Acta de entrega de inventario físico (PDF membretado con el logo de la empresa).
Se descarga desde Dashboard -> Reportes Microsip -> Acta de entrega de inventario.
Cada acta lleva un folio automático (AEI-0001, AEI-0002... por empresa).
Usa solo fuentes estándar de PDF (Helvetica) para no depender de nada instalado.
"""
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

ROJO = colors.HexColor('#D8192F')
GRIS = colors.HexColor('#6D6E71')
TINTA = colors.HexColor('#1F2124')
LINEA = colors.HexColor('#D9D9DC')
FONDO = colors.HexColor('#F5F5F6')
W, H = letter
M = 2.0 * cm
N, B, I = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'

ST = {
    'titulo': ParagraphStyle('t', fontName=B, fontSize=19, leading=24, textColor=TINTA, spaceAfter=2),
    'sub': ParagraphStyle('s', fontName=N, fontSize=10, leading=14, textColor=GRIS),
    'h': ParagraphStyle('h', fontName=B, fontSize=12, leading=16, textColor=TINTA, spaceBefore=14, spaceAfter=6),
    'p': ParagraphStyle('p', fontName=N, fontSize=10, leading=14, textColor=TINTA, alignment=TA_JUSTIFY, spaceAfter=6),
    'li': ParagraphStyle('li', fontName=N, fontSize=10, leading=14, textColor=TINTA, leftIndent=16, spaceAfter=3),
    'cel': ParagraphStyle('c', fontName=N, fontSize=9, leading=11.5, textColor=TINTA),
    'celB': ParagraphStyle('cb', fontName=B, fontSize=9, leading=11.5, textColor=TINTA),
    'celH': ParagraphStyle('ch', fontName=B, fontSize=8.5, leading=10.5, textColor=colors.white),
    'nota': ParagraphStyle('n', fontName=I, fontSize=8.5, leading=11.5, textColor=GRIS, spaceAfter=4),
    'firma': ParagraphStyle('f', fontName=N, fontSize=9, leading=12, textColor=TINTA, alignment=TA_CENTER),
    'firmaB': ParagraphStyle('fb', fontName=B, fontSize=9, leading=12, textColor=TINTA, alignment=TA_CENTER),
}


def _esc(t):
    return str(t if t is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _p(t, s='p'):
    return Paragraph(t, ST[s])


def _num(v):
    try:
        if v is None or str(v).strip() == '':
            return None
        return float(str(v).replace(',', '').replace('$', '').replace('%', '').strip())
    except ValueError:
        return None


def _fmt_num(v):
    return f'{v:,.0f}' if v is not None else ''


def _fmt_mon(v):
    return f'${v:,.2f}' if v is not None else ''


def _fmt_pct(v):
    if v is None:
        return ''
    return f'{v:.1f}%'.replace('.0%', '%')


def _fecha_larga(iso):
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
             'noviembre', 'diciembre']
    try:
        a, m, d = str(iso)[:10].split('-')
        return f'{int(d)} de {meses[int(m) - 1]} de {a}'
    except Exception:
        return _esc(iso or '')


def calcular(datos):
    """Completa los números que se pueden calcular (con diferencia, exactitud)."""
    d = dict(datos or {})
    contados, sin_dif = _num(d.get('contados')), _num(d.get('sin_diferencia'))
    con_dif = _num(d.get('con_diferencia'))
    if contados is not None and sin_dif is not None and con_dif is None:
        con_dif = max(contados - sin_dif, 0)
    exact = _num(d.get('exactitud'))
    if contados and sin_dif is not None:
        exact = round(sin_dif / contados * 100, 1)
    if exact is None:
        exact = 95.0
    valor, valor_dif = _num(d.get('valor_sistema')), _num(d.get('valor_diferencias'))
    exact_valor = _num(d.get('exactitud_valor'))
    if valor and valor_dif is not None:
        exact_valor = round(max(0.0, (1 - abs(valor_dif) / valor) * 100), 1)
    meta = _num(d.get('meta')) or 95.0
    d.update(contados=contados, sin_diferencia=sin_dif, con_diferencia=con_dif, exactitud=exact,
             valor_sistema=valor, valor_diferencias=valor_dif, exactitud_valor=exact_valor, meta=meta)
    return d


def _tabla(filas, anchos, encabezado=True, alto=None, col0=False):
    datos = []
    for i, f in enumerate(filas):
        datos.append([_p(c, 'celH' if (encabezado and i == 0) else ('celB' if (col0 and j == 0) else 'cel'))
                      for j, c in enumerate(f)])
    alturas = [None if (encabezado and i == 0) else alto for i in range(len(datos))] if alto else None
    t = Table(datos, colWidths=anchos, rowHeights=alturas, repeatRows=1 if encabezado else 0)
    est = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINEA),
           ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
           ('TOPPADDING', (0, 0), (-1, -1), 4.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
           ('BOX', (0, 0), (-1, -1), 0.6, LINEA)]
    if encabezado:
        est.append(('BACKGROUND', (0, 0), (-1, 0), TINTA))
    if col0:
        est += [('BACKGROUND', (0, 1 if encabezado else 0), (0, -1), FONDO), ('LINEAFTER', (0, 0), (0, -1), 0.5, LINEA)]
    else:
        est.append(('INNERGRID', (0, 1 if encabezado else 0), (-1, -1), 0.4, LINEA))
    t.setStyle(TableStyle(est))
    return t


class _Indicador(Flowable):
    def __init__(self, ancho, pct, meta):
        super().__init__()
        self.ancho, self.alto, self.pct, self.meta = ancho, 2.5 * cm, pct, meta

    def wrap(self, *a):
        return self.ancho, self.alto

    def draw(self):
        c = self.canv
        c.setFillColor(FONDO); c.setStrokeColor(LINEA); c.setLineWidth(0.6)
        c.roundRect(0, 0, self.ancho, self.alto, 6, stroke=1, fill=1)
        c.setFillColor(ROJO); c.rect(0, 0, 5, self.alto, stroke=0, fill=1)
        c.setFont(B, 32); c.drawString(0.8 * cm, 0.75 * cm, _fmt_pct(self.pct))
        c.setFont(B, 11); c.setFillColor(TINTA)
        c.drawString(4.6 * cm, 1.45 * cm, 'Exactitud del inventario físico')
        c.setFont(N, 9.5); c.setFillColor(GRIS)
        c.drawString(4.6 * cm, 0.95 * cm, 'Artículos cuya existencia física coincide con lo registrado en el sistema.')
        c.drawString(4.6 * cm, 0.52 * cm, f'Meta comprometida en los siguientes inventarios: {_fmt_pct(self.meta)} o más.')


def generar_pdf(datos, empresa_nombre, logo_bytes=None):
    """datos: folio, sucursal, fecha_conteo, fecha_entrega, entrega_nombre, recibe_nombre, recibe_puesto,
    contados, sin_diferencia, con_diferencia, exactitud, valor_sistema, valor_diferencias, exactitud_valor,
    folio_ajuste, sistema, meta. Lo que no venga se deja en blanco para llenarlo a mano."""
    d = calcular(datos)
    empresa = _esc(empresa_nombre or 'la empresa')
    folio = _esc(d.get('folio') or '')
    # "Microsip" (u otro nombre) o vacío: sin nombre se dice "el sistema" a secas.
    sistema_nombre = _esc(d.get('sistema') or '')
    sistema = sistema_nombre or 'el sistema'
    sistema_largo = f'el sistema {sistema_nombre}' if sistema_nombre else 'el sistema de inventarios'
    logo = None
    if logo_bytes:
        try:
            logo = ImageReader(io.BytesIO(logo_bytes))
        except Exception:
            logo = None

    def membrete(c, doc):
        c.saveState()
        if logo:
            iw, ih = logo.getSize()
            lh = 1.15 * cm
            lw = min(5.0 * cm, lh * iw / ih)
            lh = lw * ih / iw
            c.drawImage(logo, M, H - 1.25 * cm - lh, width=lw, height=lh, mask='auto')
        else:
            c.setFont(B, 16); c.setFillColor(ROJO)
            c.drawString(M, H - 2.0 * cm, empresa_nombre or '')
        c.setFont(B, 8.5); c.setFillColor(TINTA)
        c.drawRightString(W - M, H - 1.55 * cm, 'ACTA DE ENTREGA DE INVENTARIO FÍSICO')
        c.setFont(N, 8.5); c.setFillColor(GRIS)
        c.drawRightString(W - M, H - 1.98 * cm, f'Folio: {d.get("folio") or ""}')
        c.setStrokeColor(ROJO); c.setLineWidth(1.4)
        c.line(M, H - 2.55 * cm, W - M, H - 2.55 * cm)
        c.setStrokeColor(LINEA); c.setLineWidth(0.6)
        c.line(M, 1.55 * cm, W - M, 1.55 * cm)
        c.setFont(N, 7.5); c.setFillColor(GRIS)
        c.drawString(M, 1.1 * cm, empresa_nombre or '')
        c.drawCentredString(W / 2, 1.1 * cm, f'Documento de control interno  ·  {d.get("folio") or ""}')
        c.restoreState()

    class _Canvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._paginas = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for e in self._paginas:
                self.__dict__.update(e)
                self.setFont(N, 7.5); self.setFillColor(GRIS)
                self.drawRightString(W - M, 1.1 * cm, f'Página {self._pageNumber} de {total}')
                super().showPage()
            super().save()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=letter, leftMargin=M, rightMargin=M, topMargin=3.2 * cm, bottomMargin=2.2 * cm,
                          title=f'Acta de entrega de inventario físico {d.get("folio") or ""}', author=empresa_nombre or '')
    doc.addPageTemplates([PageTemplate(id='p', onPage=membrete, frames=[
        Frame(M, 2.2 * cm, W - 2 * M, H - 5.4 * cm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])
    AN = W - 2 * M
    v = lambda k: _esc(d.get(k) or '')
    s = []

    def sec(n, t):
        s.append(Paragraph(f'<font color="#D8192F">{n}.</font>&nbsp;&nbsp;{t}', ST['h']))

    pct, meta = d['exactitud'], d['meta']
    s.append(_p('Acta de entrega de inventario físico', 'titulo'))
    s.append(_p(f'Folio {folio}  ·  Entrega del almacén al encargado con {_fmt_pct(pct)} de exactitud y compromiso de mantenerla', 'sub'))
    s.append(Spacer(1, 12))
    s.append(_p(f'En la fecha indicada, el Encargado de Inventarios de <b>{empresa}</b> entrega al encargado del almacén el '
                f'inventario físico, conciliado contra {sistema_largo}, con una exactitud del <b>{_fmt_pct(pct)}</b>. '
                'Con su firma, el encargado recibe el inventario en estas condiciones y se compromete a mantenerlo así, con '
                'inventarios físicos periódicos que lo verifiquen.'))
    s.append(Spacer(1, 4))
    s.append(_Indicador(AN, pct, meta))

    sec(1, 'Datos generales')
    s.append(_tabla([
        ['Folio', folio],
        ['Empresa', empresa],
        ['Sucursal / almacén', v('sucursal')],
        ['Fecha del conteo físico', _fecha_larga(d.get('fecha_conteo')) if d.get('fecha_conteo') else ''],
        ['Fecha de entrega', _fecha_larga(d.get('fecha_entrega')) if d.get('fecha_entrega') else ''],
        ['Entrega', 'Encargado de Inventarios. Nombre: ' + v('entrega_nombre')],
        ['Recibe (encargado)', 'Nombre: ' + v('recibe_nombre')],
        ['Puesto del encargado', v('recibe_puesto')],
        ['Sistema de inventario', sistema_nombre or 'Sistema de inventarios'],
    ], [5.4 * cm, AN - 5.4 * cm], encabezado=False, alto=0.7 * cm, col0=True))

    sec(2, 'Resultado del inventario')
    s.append(_p(f'El conteo físico coincide con lo registrado en {sistema} en un <b>{_fmt_pct(pct)}</b> de los artículos '
                'contados. Las diferencias quedaron identificadas y ajustadas, como se detalla en la sección 3.'))
    s.append(_tabla([
        ['Indicador', 'Resultado'],
        ['Artículos (claves) contados', _fmt_num(d['contados'])],
        ['Artículos sin diferencia', _fmt_num(d['sin_diferencia'])],
        ['Artículos con diferencia', _fmt_num(d['con_diferencia'])],
        ['Exactitud por artículo', f'<b>{_fmt_pct(pct)}</b>'],
        ['Valor del inventario en sistema', _fmt_mon(d['valor_sistema'])],
        ['Valor de las diferencias', _fmt_mon(d['valor_diferencias'])],
        ['Exactitud por valor', _fmt_pct(d['exactitud_valor'])],
    ], [AN * 0.55, AN * 0.45], alto=0.66 * cm))
    s.append(Spacer(1, 4))
    s.append(_p('Exactitud por artículo = artículos sin diferencia ÷ artículos contados × 100. Un artículo cuenta como '
                f'correcto cuando su cantidad física es igual a la registrada en {sistema}.', 'nota'))

    sec(3, 'Ajustes y diferencias')
    s.append(_p(f'Las diferencias encontradas se revisaron con el encargado y se ajustaron en {sistema}, por lo que el '
                'inventario se entrega con el sistema igual a lo físico. Se anexa el reporte de diferencias del conteo.'))
    cols = [2.2 * cm, 5.0 * cm, 1.9 * cm, 1.9 * cm, 1.8 * cm]
    cols.append(AN - sum(cols))
    s.append(_tabla([['Clave', 'Artículo', 'En sistema', 'Conteo físico', 'Diferencia', 'Causa / comentario']]
                    + [[''] * 6 for _ in range(6)], cols, alto=0.64 * cm))
    s.append(Spacer(1, 6))
    s.append(_p(f'Folio del ajuste de inventario en {sistema}: ' + (v('folio_ajuste') or '______________________')))

    sec(4, 'Compromisos del encargado')
    s.append(_p(f'El encargado recibe el inventario con {_fmt_pct(pct)} de exactitud y se compromete a mantenerlo en '
                f'<b>{_fmt_pct(meta)} o más</b> en cada inventario físico. Para lograrlo se compromete a:'))
    for i, t in enumerate([
        f'Registrar en {sistema} toda entrada y salida de mercancía el mismo día en que ocurre.',
        'No entregar ni recibir mercancía sin su documento (factura, remisión, traspaso o vale).',
        'Registrar los traspasos entre almacenes y sucursales antes de mover la mercancía.',
        'Reportar de inmediato a su jefe y al Encargado de Inventarios cualquier faltante, sobrante, merma o producto dañado.',
        'Mantener el almacén ordenado: cada artículo en su lugar, identificado y con su clave visible.',
        'Permitir el acceso al almacén solo al personal autorizado.',
        'Dar las facilidades y el tiempo necesarios para los inventarios físicos programados y sorpresa.',
    ], 1):
        s.append(Paragraph(f'<font name="{B}" color="#D8192F">{i}.</font>&nbsp;&nbsp;{t}', ST['li']))

    sec(5, 'Inventarios físicos periódicos')
    s.append(_p(f'A partir de esta entrega se harán inventarios físicos periódicos para verificar que la exactitud se '
                f'mantenga en {_fmt_pct(meta)} o más. Cada resultado se registra en el seguimiento.'))
    s.append(_tabla([
        ['Tipo de inventario', 'Frecuencia', 'Alcance'],
        ['Conteo cíclico', 'Mensual', 'Una parte de los artículos cada vez (por línea o ubicación), empezando por los de mayor valor y movimiento.'],
        ['Inventario sorpresa', 'Sin aviso previo', 'Una muestra de artículos elegida por el Encargado de Inventarios o Dirección.'],
        ['Inventario general', 'Cada 6 meses', 'Todo el almacén.'],
    ], [3.8 * cm, 3.0 * cm, AN - 6.8 * cm]))
    s.append(Spacer(1, 6))
    s.append(_p(f'Si un inventario resulta por debajo del {_fmt_pct(meta)}, el encargado del almacén y el Encargado de Inventarios revisan las causas, se '
                f'ajusta {sistema} y se repite el conteo de esos artículos en un plazo máximo de 15 días.'))
    s.append(KeepTogether([
        _p('<b>Seguimiento de inventarios</b>'),
        _tabla([['Fecha', 'Tipo', 'Artículos contados', 'Exactitud', 'Firma del encargado']] + [[''] * 5 for _ in range(5)],
               [2.6 * cm, 3.4 * cm, 3.4 * cm, 2.4 * cm, AN - 11.8 * cm], alto=0.75 * cm),
    ]))

    nombres = {'Entrega': d.get('entrega_nombre'), 'Recibe': d.get('recibe_nombre'), 'Visto bueno': None}
    firmas = []
    for rol, puesto in [('Entrega', 'Encargado de Inventarios'), ('Recibe', d.get('recibe_puesto') or 'Encargado del almacén'),
                        ('Visto bueno', 'Dirección')]:
        nom = nombres[rol]
        firmas.append([Spacer(1, 1.7 * cm), _p('_______________________________', 'firma'), _p(rol, 'firmaB'),
                       _p(_esc(puesto), 'firma'), Spacer(1, 4),
                       _p(_esc(nom) if nom else 'Nombre: ______________________', 'firma'),
                       _p('Fecha: _______________________', 'firma')])
    tf = Table([firmas], colWidths=[AN / 3] * 3)
    tf.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 2),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 2)]))
    s.append(KeepTogether([Paragraph('<font color="#D8192F">6.</font>&nbsp;&nbsp;Firmas', ST['h']),
                           _p('Las partes firman de conformidad con el resultado del inventario y con los compromisos de esta acta.'),
                           tf]))
    doc.build(s, canvasmaker=_Canvas)
    return buf.getvalue()
