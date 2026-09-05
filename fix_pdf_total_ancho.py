# -*- coding: utf-8 -*-
"""
La columna donde va el número del TOTAL en el PDF de cotización estaba
muy justa (2.7cm) para el texto en negritas, así que en totales grandes
se cortaba el último "0" y se caía a la siguiente línea. Se ensancha a
3.3cm (y se recorta la columna de la etiqueta "TOTAL" a 12.7cm para que
sigan sumando lo mismo).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_pdf_total_ancho.py
"""
import sys

RUTA = 'backend/pdfs_cotizaciones.py'

VIEJO = (
    '    ]], colWidths=[13.3 * cm, 2.7 * cm])'
)

NUEVO = (
    '    ]], colWidths=[12.7 * cm, 3.3 * cm])'
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
    print('   git commit -m "PDF cotizacion: ensanchar columna del total"')
    print("   git push")


if __name__ == "__main__":
    main()
