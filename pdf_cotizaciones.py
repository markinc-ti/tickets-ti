# -*- coding: utf-8 -*-
"""
En el PDF de cotizacion: se invierte el orden otra vez -- ahora
"Precio de contado (sin descuento)" va justo debajo de la tabla de
articulos (pegado, sin tanto espacio), y el TOTAL aparece despues.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_pdf_contado_arriba.py
"""
import sys

RUTA = 'backend/pdfs_cotizaciones.py'

VIEJO = '    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)\n    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)\n    tabla_total = Table([[\n        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),\n        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),\n    ]], colWidths=[12.7 * cm, 3.3 * cm])\n    tabla_total.setStyle(TableStyle([\n        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n        ("TOPPADDING", (0, 0), (-1, -1), 4),\n        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),\n    ]))\n    elementos.append(tabla_total)\n\n    if hay_descuentos:\n        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])\n        estilo_sin_desc = ParagraphStyle("SinDesc", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)\n        elementos.append(Spacer(1, 14))\n        elementos.append(Paragraph(\n            f"Precio de contado (sin descuento): {_fmt_dinero(total_sin_descuento)}",\n            estilo_sin_desc,\n        ))\n'

NUEVO = '    if hay_descuentos:\n        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])\n        estilo_sin_desc = ParagraphStyle("SinDesc", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)\n        elementos.append(Spacer(1, 6))\n        elementos.append(Paragraph(\n            f"Precio de contado (sin descuento): {_fmt_dinero(total_sin_descuento)}",\n            estilo_sin_desc,\n        ))\n\n    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)\n    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)\n    tabla_total = Table([[\n        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),\n        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),\n    ]], colWidths=[12.7 * cm, 3.3 * cm])\n    tabla_total.setStyle(TableStyle([\n        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n        ("TOPPADDING", (0, 0), (-1, -1), 4),\n        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),\n    ]))\n    elementos.append(tabla_total)\n'


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if VIEJO in contenido:
        contenido = contenido.replace(VIEJO, NUEVO, 1)
    elif NUEVO in contenido:
        print(f"[{RUTA}] Ya estaba aplicado, no se hizo nada.")
        sys.exit(0)
    else:
        print(f"[{RUTA}] No se encontro el bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
        print("Avisale a Claude sin correr git add/commit todavia.")
        sys.exit(1)

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] Corregido.")
    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/pdfs_cotizaciones.py")
    print('   git commit -m "PDF cotizacion: precio de contado arriba del total, justo debajo de la tabla"')
    print("   git push")


if __name__ == "__main__":
    main()
