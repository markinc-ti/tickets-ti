# -*- coding: utf-8 -*-
"""
COTIZADOR (SUPERADMIN): ARREGLA EL BOTON "+ AGREGAR ITEM LIBRE"
El boton no hacia nada (la funcion no se encontraba desde el HTML).
Funciona con o sin fix_cotizador_nota_venta_folios.py aplicado.
Toca: frontend/cotizador_costos.html
Se puede correr varias veces.  Correr con:  py -3 fix_cotizador_agregar_item.py
"""
import os
import sys

ARCHIVOS = {
 "frontend/cotizador_costos.html": [
  [
   "\n    <h2 class=\"section-title\"><span class=\"n\">03</span>Módulos a incluir</h2>\n    <div id=\"modules-list\"></div>\n    <button class=\"add-resource\" style=\"width:100%; text-align:center; padding:8px; margin-top:4px;\" onclick=\"agregarItemPersonalizado()\">+ Agregar ítem libre (lo que no esté en la lista)</button>\n\n    <h2 class=\"section-title\"><span class=\"n\">04</span>Qué más se puede ofrecer a futuro</h2>\n    <p style=\"font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;\">Módulos no incluidos hoy que puedes mostrar como camino de crecimiento en la cotización.</p>\n",
   "\n    <h2 class=\"section-title\"><span class=\"n\">03</span>Módulos a incluir</h2>\n    <div id=\"modules-list\"></div>\n    <button class=\"add-resource\" style=\"width:100%; text-align:center; padding:8px; margin-top:4px;\" id=\"btn-agregar-item\">+ Agregar ítem libre (lo que no esté en la lista)</button>\n\n    <h2 class=\"section-title\"><span class=\"n\">04</span>Qué más se puede ofrecer a futuro</h2>\n    <p style=\"font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;\">Módulos no incluidos hoy que puedes mostrar como camino de crecimiento en la cotización.</p>\n"
  ],
  [
   "  mods().push({ id:'custom_'+Date.now(), name:'Nuevo ítem', desc:'', on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] });\n  renderAll();\n}\n\n// ---------- render: crecimiento (módulos apagados, para marcar como \"a futuro\") ----------\nfunction renderGrowth(){\n",
   "  mods().push({ id:'custom_'+Date.now(), name:'Nuevo ítem', desc:'', on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] });\n  renderAll();\n}\n// El script vive dentro de (function(){...}), así que un onclick=\"...\" en el\n// HTML no encuentra la función: se conecta aquí con addEventListener.\ndocument.getElementById('btn-agregar-item').addEventListener('click', agregarItemPersonalizado);\n\n// ---------- render: crecimiento (módulos apagados, para marcar como \"a futuro\") ----------\nfunction renderGrowth(){\n"
  ]
 ]
}

NUEVOS = {}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_cotizador_agregar_item.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto and viejo not in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
