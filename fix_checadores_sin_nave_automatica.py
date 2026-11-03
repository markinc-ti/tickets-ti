# -*- coding: utf-8 -*-
"""
CHECADORES: APAGA DEL TODO LA SUCURSAL AUTOMATICA
La sucursal (nave) por checador fue solo para la carga inicial. El personal se
da de alta desde la app con su sucursal, asi que ya NADA la cambia solo
(checador, ligar solo, cambiar vinculo, liberar, importar). Solo queda el
boton de RH "Asignar nave por checador" (con vista previa) por si un dia se usa.
Correr DESPUES de fix_checadores_no_pisar_sucursal.py
Toca: backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_checadores_sin_nave_automatica.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return _auto_ligar_gente(usuario[\"empresa_id\"], solo_nombre=por_nombre, aplicar=not simular)\n\n\ndef _asignar_naves(empresa_id, **kw):\n    \"\"\"Pone a cada persona en la nave de su checador (ver db.asignar_naves_por_checador).\n    Nunca tumba la operación que lo llamó.\"\"\"\n    try:\n        return db.asignar_naves_por_checador(empresa_id, **kw)\n    except Exception as e:  # noqa: BLE001\n",
   "    return _auto_ligar_gente(usuario[\"empresa_id\"], solo_nombre=por_nombre, aplicar=not simular)\n\n\n# La sucursal (nave) por checador fue solo para la carga inicial: el personal se da de\n# alta desde la app con su sucursal. Ya nada la cambia en automático (checador, ligar,\n# cambiar vínculo, importar); solo el botón de RH \"Asignar naves\" (con vista previa).\nASIGNAR_NAVES_AUTOMATICO = False\n\n\ndef _asignar_naves(empresa_id, **kw):\n    \"\"\"Pone a cada persona en la nave de su checador (ver db.asignar_naves_por_checador).\n    Apagado (ASIGNAR_NAVES_AUTOMATICO). Nunca tumba la operación que lo llamó.\"\"\"\n    if not ASIGNAR_NAVES_AUTOMATICO:\n        return None\n    try:\n        return db.asignar_naves_por_checador(empresa_id, **kw)\n    except Exception as e:  # noqa: BLE001\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checadores_sin_nave_automatica.py")
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
