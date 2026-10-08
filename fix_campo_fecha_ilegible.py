#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Campos de fecha (type="date") con texto ilegible en Android.

David reportó con capturas: en "Nueva incidencia" (y en cualquier otro
campo de fecha de la app), el celular pinta la casilla clara/blanca con
"DD/MM/AAAA" en gris muy tenue -- casi no se lee.

La app ya intenta forzar el tema oscuro en todos los controles con
"color-scheme: dark" (ver el comentario que ya existe en el CSS), pero
en los campos de fecha específicamente, algunos navegadores de Android
los dibujan con su propio widget nativo que no siempre respeta eso --
el resultado es una caja clara con texto que casi no contrasta.

En vez de seguir peleando por que el navegador pinte esa caja oscura
(que en la práctica no es consistente), este parche hace lo contrario:
fuerza a que el campo de fecha SIEMPRE se vea claro (fondo claro, texto
oscuro), para que sea legible sin importar el dispositivo. Se ve un
poco distinto al resto de los campos (que siguen oscuros), pero
legible en todos lados es más importante que la consistencia visual
aquí. Esto NO toca el resto de los inputs (texto, select, etc.), que
siguen con el tema oscuro normal de la app.

Qué toca:
- frontend/index.html: nueva regla CSS para input[type="date"].

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_campo_fecha_ilegible.py
"""
import sys

ARCHIVOS = {
    'frontend/index.html': [
        [
            '''  input:focus, textarea:focus, select:focus {
    outline: none; border-color: var(--copper);
    box-shadow: var(--shadow-inset), 0 0 0 3px rgba(216,25,47,0.18);
  }
  textarea { min-height: 70px; resize: vertical; }''',
            '''  input:focus, textarea:focus, select:focus {
    outline: none; border-color: var(--copper);
    box-shadow: var(--shadow-inset), 0 0 0 3px rgba(216,25,47,0.18);
  }
  /* Los campos de fecha (type="date") a veces los pinta el propio
     sistema operativo (sobre todo en Android) sin respetar el tema
     oscuro de la app -- se ve una caja clara con "DD/MM/AAAA" en gris
     casi invisible. En vez de pelear contra eso, se fuerza a que ESTE
     campo en particular se vea siempre claro con texto oscuro, para
     que se lea bien sin importar el dispositivo (los demás campos
     siguen con el tema oscuro normal). */
  input[type="date"] {
    color-scheme: light;
    background: #F2F1F0;
    color: #1A1B1D;
  }
  textarea { min-height: 70px; resize: vertical; }''',
        ],
    ],
}


def main():
    cambios_totales = 0
    for ruta, hunks in ARCHIVOS.items():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
        except FileNotFoundError:
            print(f"ERROR: no se encontro {ruta} -- corre este script desde la raiz del repo tickets-ti.")
            sys.exit(1)

        original = contenido
        cambios_archivo = 0
        for viejo, nuevo in hunks:
            if nuevo in contenido:
                continue  # ya aplicado antes -- idempotente
            if viejo not in contenido:
                print(f"ERROR: no se encontro el texto esperado en {ruta}.")
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
                print("--- fragmento esperado ---")
                print(viejo[:300])
                sys.exit(1)
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios_archivo += 1

        if contenido != original:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: {ruta} -- {cambios_archivo} cambio(s) aplicado(s).")
            cambios_totales += cambios_archivo
        else:
            print(f"(sin cambios) {ruta} -- ya estaba aplicado.")

    if cambios_totales == 0:
        print()
        print("No habia nada nuevo que aplicar (el parche ya estaba puesto).")
    else:
        print()
        print(f"{cambios_totales} cambio(s) aplicado(s) en total.")

    print()
    print("Ahora corre esto para subirlo:")
    print()
    print("    git add frontend/index.html")
    print('    git commit -m "UI: campos de fecha siempre legibles (fondo claro/texto oscuro) en Android"')
    print("    git push")


if __name__ == "__main__":
    main()
