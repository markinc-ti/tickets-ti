# -*- coding: utf-8 -*-
"""Checador de precio / CEDIS (2): el almacen que "solo dice si hay" (Almacen General) ahora
SIEMPRE sale con su mensaje, aunque no este marcado en "almacenes visibles". Antes, si no estaba
marcado, se ocultaba completo y solo salia la nota "Los totales no incluyen CEDIS".
REQUIERE fix_checador_cedis.py.
Correr en la carpeta tickets-ti:  py -3 fix_checador_cedis_v2.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    almacenes = list(resultado.get(\"almacenes\") or [])\n    vis = None\n",
   "    almacenes = list(resultado.get(\"almacenes\") or [])\n    reservados = db.almacenes_reservados_checador(usuario[\"empresa_id\"])\n    ocultar = set(reservados[\"almacenes\"]) if reservados[\"almacenes\"] and not _ve_cantidad_reservados(usuario, reservados) else set()\n    vis = None\n"
  ],
  [
   "            almacenes = [a for a in almacenes if a.get(\"almacen_id\") in vis]\n    reservados = db.almacenes_reservados_checador(usuario[\"empresa_id\"])\n    ocultar = set(reservados[\"almacenes\"]) if reservados[\"almacenes\"] and not _ve_cantidad_reservados(usuario, reservados) else set()\n",
   "            # Un almacén \"solo dice si hay\" (CEDIS) siempre sale con su mensaje, aunque\n            # no esté marcado en la lista de almacenes visibles.\n            almacenes = [a for a in almacenes if a.get(\"almacen_id\") in vis or a.get(\"almacen_id\") in ocultar]\n"
  ],
  [
   "    if ocultar:\n",
   "    if any(a.get(\"solo_disponibilidad\") for a in final):\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_cedis_v2.py")
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
