# -*- coding: utf-8 -*-
"""
En el PDF de cotización: el TOTAL ahora va primero (como siempre), y el
"Precio de contado (sin descuento)" se movió a unos renglones ABAJO del
TOTAL, en vez de arriba.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_pdf_precio_contado_abajo.py
"""
import sys

RUTA = 'backend/pdfs_cotizaciones.py'

VIEJO = (
    '    elementos.append(Spacer(1, 6))\n'
    '    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)\n'
    '    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)\n'
    '    filas_total = []\n'
    '    if hay_descuentos:\n'
    '        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])\n'
    '        estilo_sin_desc_etiqueta = ParagraphStyle("SinDescEtiqueta", parent=styles["Normal"], fontSize=9.5, textColor=GRIS)\n'
    '        estilo_sin_desc_valor = ParagraphStyle("SinDescValor", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)\n'
    '        filas_total.append([\n'
    '            Paragraph("Precio sin descuento", estilo_sin_desc_etiqueta),\n'
    '            Paragraph(_fmt_dinero(total_sin_descuento), estilo_sin_desc_valor),\n'
    '        ])\n'
    '    filas_total.append([\n'
    '        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),\n'
    '        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),\n'
    '    ])\n'
    '    tabla_total = Table(filas_total, colWidths=[13.3 * cm, 2.7 * cm])\n'
    '    estilo_tabla_total = [\n'
    '        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n'
    '        ("TOPPADDING", (0, 0), (-1, -1), 4),\n'
    '        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),\n'
    '    ]\n'
    '    if hay_descuentos:\n'
    '        estilo_tabla_total.append(("TOPPADDING", (0, -1), (-1, -1), 8))\n'
    '    tabla_total.setStyle(TableStyle(estilo_tabla_total))\n'
    '    elementos.append(tabla_total)\n'
)

NUEVO = (
    '    elementos.append(Spacer(1, 6))\n'
    '    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)\n'
    '    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)\n'
    '    tabla_total = Table([[\n'
    '        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),\n'
    '        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),\n'
    '    ]], colWidths=[12.7 * cm, 3.3 * cm])\n'
    '    tabla_total.setStyle(TableStyle([\n'
    '        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n'
    '        ("TOPPADDING", (0, 0), (-1, -1), 4),\n'
    '        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),\n'
    '    ]))\n'
    '    elementos.append(tabla_total)\n'
    '\n'
    '    if hay_descuentos:\n'
    '        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])\n'
    '        estilo_sin_desc = ParagraphStyle("SinDesc", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)\n'
    '        elementos.append(Spacer(1, 14))\n'
    '        elementos.append(Paragraph(\n'
    '            f"Precio de contado (sin descuento): {_fmt_dinero(total_sin_descuento)}",\n'
    '            estilo_sin_desc,\n'
    '        ))\n'
)


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if VIEJO in contenido:
        contenido = contenido.replace(VIEJO, NUEVO, 1)
    elif NUEVO in contenido:
        print(f"[{RUTA}] Ya estaba aplicado, no se hizo nada.")
        sys.exit(0)
    else:
        print(f"[{RUTA}] No se encontró el bloque esperado. El archivo pudo haber cambiado desde la última vez.")
        print("Avísale a Claude sin correr git add/commit todavía.")
        sys.exit(1)

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] Corregido.")
    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/pdfs_cotizaciones.py")
    print('   git commit -m "PDF cotizacion: precio de contado abajo del total"')
    print("   git push")


if __name__ == "__main__":
    main()
