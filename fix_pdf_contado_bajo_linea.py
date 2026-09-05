"""Script de aplicación: mueve la leyenda 'Precio de contado (sin
descuento)' para que quede DEBAJO de la línea roja, con el importe
alineado justo bajo la columna 'Precio unit.' en vez de pegado al
margen derecho. Corre esto desde la raíz del repo (misma carpeta
donde está la carpeta backend/): py fix_pdf_contado_bajo_linea.py
"""
import pathlib

RUTA = pathlib.Path("backend/pdfs_cotizaciones.py")

VIEJO = '''    elementos.append(Spacer(1, 6))
    if hay_descuentos:
        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])
        estilo_sin_desc = ParagraphStyle("SinDesc", parent=styles["Normal"], fontSize=9.5, alignment=2, textColor=GRIS)
        elementos.append(Spacer(1, 6))
        elementos.append(Paragraph(
            f"Precio de contado (sin descuento): {_fmt_dinero(total_sin_descuento)}",
            estilo_sin_desc,
        ))

    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)
    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)
    tabla_total = Table([[
        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),
        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),
    ]], colWidths=[12.7 * cm, 3.3 * cm])
    tabla_total.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_total)'''

NUEVO = '''    elementos.append(Spacer(1, 6))
    if hay_descuentos:
        # Línea roja primero, y la leyenda "Precio de contado (sin
        # descuento)" queda debajo de ella, con el importe alineado
        # justo bajo la columna "Precio unit." (misma anchura de
        # columnas que la tabla de artículos) — sirve de referencia
        # visual de que esa es la suma de precios unitarios sin
        # descuentos aplicados.
        elementos.append(HRFlowable(width="100%", thickness=1.2, color=ROJO, spaceBefore=2, spaceAfter=4))
        total_sin_descuento = sum(float(i["cantidad"]) * float(i["precio_unitario"]) for i in cotizacion["items"])
        estilo_sin_desc_etiqueta = ParagraphStyle("SinDescEtiqueta", parent=styles["Normal"], fontSize=8, textColor=GRIS)
        estilo_sin_desc_valor = ParagraphStyle("SinDescValor", parent=styles["Normal"], fontSize=9, alignment=2, textColor=GRIS)
        fila_contado = [""] * len(colWidths)
        fila_contado[0] = Paragraph("Precio de contado (sin descuento)", estilo_sin_desc_etiqueta)
        fila_contado[2] = Paragraph(_fmt_dinero(total_sin_descuento), estilo_sin_desc_valor)  # col. "Precio unit."
        tabla_contado = Table([fila_contado], colWidths=colWidths)
        tabla_contado.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elementos.append(tabla_contado)

    estilo_total_etiqueta = ParagraphStyle("TotalEtiqueta", parent=styles["Normal"], fontSize=12, textColor=NEGRO)
    estilo_total_valor = ParagraphStyle("TotalValor", parent=styles["Normal"], fontSize=12, alignment=2, textColor=ROJO)
    tabla_total = Table([[
        Paragraph("<b>TOTAL</b>", estilo_total_etiqueta),
        Paragraph(f"<b>{_fmt_dinero(total)}</b>", estilo_total_valor),
    ]], colWidths=[12.7 * cm, 3.3 * cm])
    estilo_tabla_total = [
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if not hay_descuentos:
        # Sin descuentos no hay leyenda "Precio de contado" ni línea roja
        # aparte, así que el TOTAL lleva su propia línea arriba.
        estilo_tabla_total.append(("LINEABOVE", (0, 0), (-1, 0), 1.2, ROJO))
    tabla_total.setStyle(TableStyle(estilo_tabla_total))
    elementos.append(tabla_total)'''


def main():
    if not RUTA.exists():
        print(f"ERROR: no encuentro {RUTA}. Corre este script desde la raíz del repo (donde está la carpeta backend/).")
        return
    contenido = RUTA.read_text(encoding="utf-8")
    if NUEVO in contenido:
        print("Ya estaba aplicado, no hice nada.")
        return
    if VIEJO not in contenido:
        print("ERROR: no encontré el bloque esperado en pdfs_cotizaciones.py. Puede que ya lo hayas modificado a mano. Revisa manualmente.")
        return
    contenido = contenido.replace(VIEJO, NUEVO)
    RUTA.write_text(contenido, encoding="utf-8")
    print(f"Listo: {RUTA} actualizado.")


if __name__ == "__main__":
    main()
