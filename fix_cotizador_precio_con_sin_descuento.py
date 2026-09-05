# -*- coding: utf-8 -*-
"""
En el Checador de precio, al final de la lista de artículos de una
cotización, ahora se muestra tanto el precio SIN descuento (suma de
cantidad × precio unitario, sin aplicar ningún % de descuento) como el
precio CON descuento (el total real, como ya se mostraba).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_cotizador_precio_con_sin_descuento.py
"""
import sys

RUTA = 'frontend/index.html'

VIEJO_FUNCIONES = (
    'function cot_total() {\n'
    '  return COT_ACTUAL.items.reduce((suma, it) => suma + cot_subtotalItem(it), 0);\n'
    '}\n'
)

NUEVO_FUNCIONES = (
    'function cot_total() {\n'
    '  return COT_ACTUAL.items.reduce((suma, it) => suma + cot_subtotalItem(it), 0);\n'
    '}\n'
    '\n'
    'function cot_totalSinDescuento() {\n'
    '  return COT_ACTUAL.items.reduce((suma, it) => suma + (Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0), 0);\n'
    '}\n'
)

VIEJO_ACTUALIZAR = (
    '  const totalEl = document.getElementById(\'cot_total\');\n'
    '  if (totalEl) totalEl.textContent = \'$\' + cot_fmt(cot_total());\n'
    '}\n'
)

NUEVO_ACTUALIZAR = (
    '  const totalEl = document.getElementById(\'cot_total\');\n'
    '  if (totalEl) totalEl.textContent = \'$\' + cot_fmt(cot_total());\n'
    '  const totalSinDescEl = document.getElementById(\'cot_total_sin_descuento\');\n'
    '  if (totalSinDescEl) totalSinDescEl.textContent = \'$\' + cot_fmt(cot_totalSinDescuento());\n'
    '}\n'
)

VIEJO_HTML = (
    '      <p style="text-align:right; font-size:16px; margin-top:8px;"><b>Total: <span id="cot_total">$${cot_fmt(cot_total())}</span></b></p>'
)

NUEVO_HTML = (
    '      <div style="text-align:right; margin-top:8px;">\n'
    '        <p style="font-size:12px; color:var(--muted); margin:0;">Precio sin descuento: <span id="cot_total_sin_descuento">$${cot_fmt(cot_totalSinDescuento())}</span></p>\n'
    '        <p style="font-size:16px; margin:2px 0 0;"><b>Precio con descuento: <span id="cot_total">$${cot_fmt(cot_total())}</span></b></p>\n'
    '      </div>'
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
    for viejo, nuevo in [(VIEJO_FUNCIONES, NUEVO_FUNCIONES), (VIEJO_ACTUALIZAR, NUEVO_ACTUALIZAR), (VIEJO_HTML, NUEVO_HTML)]:
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

    print(f"[{RUTA}] {cambios}/3 cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print("   git commit -m \"Cotizador: mostrar precio con y sin descuento\"")
    print("   git push")


if __name__ == "__main__":
    main()
