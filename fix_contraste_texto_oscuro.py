# -*- coding: utf-8 -*-
"""
Arregla el contraste de las letras "apagadas" (gris secundario) en TODA la
app -- en las zonas oscuras casi no se distinguian porque el gris que se
usaba (#9B9D9F, y su variante mas oscura #6F7173/#74767A) queda muy cerca
del fondo oscuro (contraste real: 3.5:1 a 6.3:1 segun el caso, por debajo
de lo recomendado para texto normal). Se aclararon esos grises sin tocar
nada del resto de la paleta (rojo de marca, colores de prioridad alta/baja,
etc.) ni el modo claro (ahi el gris oscuro sobre fondo blanco ya se lee
bien, no se toco).

Que cambia, con nombres exactos:
  - frontend/index.html: las variables CSS --trace y --muted (texto
    secundario/informativo, usadas cientos de veces en toda la app) y
    --media (texto de la etiqueta de prioridad "media") -- tanto en el
    :root de arriba como en el objeto TEMA_OSCURO que la pantalla de
    Administrar -> Apariencia aplica de verdad en tiempo real. El modo
    claro (TEMA_CLARO) no se toca.
  - frontend/laboratorio_estudiantes.html, pantalla_turnos.html,
    seguimiento.html, kiosko_turnos.html, cotizador_costos.html: estas
    pantallas tienen su propio CSS aparte (no comparten variables con
    index.html) y usaban el mismo gris #9B9D9F/#6F7173 escrito directo --
    se reemplaza en TODAS sus apariciones dentro de cada archivo (por eso
    esta parte no sigue el patron de "un solo cambio, una sola vez": aqui
    SI se busca y reemplaza cada aparicion del color, a propósito).

Antes -> despues:
  #9B9D9F (gris secundario) -> #C4C6C9
  #6F7173 / #74767A (gris mas oscuro, texto de prioridad media / estados vacios) -> #9FA1A4 / #8B8D90

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_contraste_texto_oscuro.py
"""
import os
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        '    --trace: #9B9D9F;\n    --text: #F2F1F0;\n    --muted: #9B9D9F;\n    --urgente: #D8192F;\n    --alta: #E8823D;\n    --media: #74767A;\n    --baja: #B9BABC;',
        '    --trace: #C4C6C9;\n    --text: #F2F1F0;\n    --muted: #C4C6C9;\n    --urgente: #D8192F;\n    --alta: #E8823D;\n    --media: #8B8D90;\n    --baja: #B9BABC;',
    ],
    [
        "  '--copper': '#D8192F', '--trace': '#9B9D9F', '--text': '#F2F1F0', '--muted': '#9B9D9F',\n  '--urgente': '#D8192F', '--alta': '#E8823D', '--media': '#74767A', '--baja': '#B9BABC',",
        "  '--copper': '#D8192F', '--trace': '#C4C6C9', '--text': '#F2F1F0', '--muted': '#C4C6C9',\n  '--urgente': '#D8192F', '--alta': '#E8823D', '--media': '#8B8D90', '--baja': '#B9BABC',",
    ],
    [
        "const colorMuted = (estilos.getPropertyValue('--trace') || '#9B9D9F').trim();",
        "const colorMuted = (estilos.getPropertyValue('--trace') || '#C4C6C9').trim();",
    ]
]

# ---------------------------------------------------------------------------
# Archivos con el mismo gris escrito directo (sin variable CSS) -- aqui se
# reemplaza CADA aparicion dentro de cada archivo, no solo una.
# ---------------------------------------------------------------------------
ARCHIVOS_REEMPLAZO_GLOBAL = {
    'frontend/laboratorio_estudiantes.html': [('#9B9D9F', '#C4C6C9'), ('#6F7173', '#9FA1A4')],
    'frontend/pantalla_turnos.html': [('#9B9D9F', '#C4C6C9'), ('#6F7173', '#9FA1A4')],
    'frontend/seguimiento.html': [('#9B9D9F', '#C4C6C9'), ('#6F7173', '#9FA1A4')],
    'frontend/kiosko_turnos.html': [('#9B9D9F', '#C4C6C9')],
    'frontend/cotizador_costos.html': [('#9B9D9F', '#C4C6C9')],
}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    reemplazos = ARCHIVOS[ruta]
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in reemplazos:
        if nuevo in contenido:
            continue
        if viejo not in contenido:
            print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
            hubo_error = True
            continue
        contenido = contenido.replace(viejo, nuevo, 1)
        cambios += 1
    escribir(ruta, contenido)
    print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")
    return not hubo_error


def aplicar_reemplazo_global(ruta):
    """A diferencia de aplicar_reemplazos, aqui SI se reemplazan TODAS las
    apariciones del color viejo en el archivo (son puros valores de color
    repetidos en distintas reglas CSS, no bloques de contexto unico)."""
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    cambios_totales = 0
    for viejo, nuevo in ARCHIVOS_REEMPLAZO_GLOBAL[ruta]:
        veces = contenido.count(viejo)
        if veces == 0:
            continue  # ya aplicado antes (o nunca existio) -- no es error
        contenido = contenido.replace(viejo, nuevo)
        cambios_totales += veces
    escribir(ruta, contenido)
    print(f"[{ruta}] {cambios_totales} aparicion(es) de color aclarada(s).")
    return True


def main():
    ok = True
    ok = aplicar_reemplazos("frontend/index.html") and ok
    for ruta in ARCHIVOS_REEMPLAZO_GLOBAL:
        ok = aplicar_reemplazo_global(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html frontend/laboratorio_estudiantes.html frontend/pantalla_turnos.html frontend/seguimiento.html frontend/kiosko_turnos.html frontend/cotizador_costos.html")
    print('   git commit -m "Aclara el gris de texto secundario para que se lea bien en las zonas oscuras de toda la app"')
    print("   git push")


if __name__ == "__main__":
    main()
