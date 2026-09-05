# -*- coding: utf-8 -*-
"""
En el PDF de cotización (backend/pdfs_cotizaciones.py):

1. La sección "Cliente" ocupaba hasta 3 renglones (Nombre, Teléfono,
   Dirección, cada uno en su propia línea). Ahora el Nombre queda en su
   propio renglón, y Teléfono + Dirección se combinan en un solo renglón
   (si ambos existen) — máximo 2 renglones en vez de 3.

2. Se agrega "Precio sin descuento" justo arriba del TOTAL, solo cuando
   algún artículo tiene descuento (si nadie tiene descuento, sería el
   mismo número repetido sin sentido).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_pdf_cotizacion_cliente_totales.py
"""
import sys

RUTA = 'backend/pdfs_cotizaciones.py'

VIEJO_CLIENTE = (
    '    elementos.append(Paragraph("Cliente", styles["Seccion"]))\n'
    '    datos_cliente = [("Nombre", cotizacion.get("cliente_nombre"))]\n'
    '    if cotizacion.get("cliente_telefono"):\n'
    '        datos_cliente.append(("Teléfono", cotizacion["cliente_telefono"]))\n'
    '    if cotizacion.get("cliente_direccion"):\n'
    '        datos_cliente.append(("Dirección", cotizacion["cliente_direccion"]))\n'
    '    for etiqueta, valor in datos_cliente:\n'
    '        elementos.append(Paragraph(f"<b>{etiqueta}:</b> {valor or \'—\'}", styles["Cuerpo"]))\n'
)

NUEVO_CLIENTE = (
    '    elementos.append(Paragraph("Cliente", styles["Seccion"]))\n'
    '    elementos.append(Paragraph(f"<b>Nombre:</b> {cotizacion.get(\'cliente_nombre\') or \'—\'}", styles["Cuerpo"]))\n'
    '    # Teléfono y Dirección se combinan en un solo renglón (si ambos existen)\n'
    '    # para no gastar una línea completa por cada uno.\n'
    '    contacto_cliente = []\n'
    '    if cotizacion.get("cliente_telefono"):\n'
    '        contacto_cliente.append(f"<b>Teléfono:</b> {cotizacion[\'cliente_telefono\']}")\n'
    '    if cotizacion.get("cliente_direccion"):\n'
    '        contacto_cliente.append(f"<b>Dirección:</b> {cotizacion[\'cliente_direccion\']}")\n'
    '    if contacto_cliente:\n'
    '        elementos.append(Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(contacto_cliente), styles["Cuerpo"]))\n'
)

VIEJO_TOTAL = (
    '    elementos.append(Spacer(1, 6))\n'
    '    tabla_total = Table([[\n'
    '        Paragraph("<b>TOTAL</b>", ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)),\n'
    '        Paragraph(f"<b>{_fmt_dinero(total)}</b>", ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)),\n'
    '    ]], colWidths=[13.3 * cm, 2.7 * cm])\n'
    '    tabla_total.setStyle(TableStyle([\n'
    '        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),\n'
    '        ("TOPPADDING", (0, 0), (-1, -1), 8),\n'
    '    ]))\n'
    '    elementos.append(tabla_total)\n'
)

NUEVO_TOTAL = (
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


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    cambios = 0
    hubo_error = False
    for viejo, nuevo in [(VIEJO_CLIENTE, NUEVO_CLIENTE), (VIEJO_TOTAL, NUEVO_TOTAL)]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print(f"[{RUTA}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
            hubo_error = True

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] {cambios}/2 cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/pdfs_cotizaciones.py")
    print("   git commit -m \"PDF cotizacion: cliente compacto + precio sin descuento\"")
    print("   git push")


if __name__ == "__main__":
    main()
