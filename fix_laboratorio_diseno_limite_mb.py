#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio: sube el limite de tamano para el archivo de diseno (STL) que
sube el laboratorio en el paso "Aprobar diseno".

Antes usaba el mismo limite que una foto o una firma (MAX_ADJUNTO_BASE64,
~5MB de archivo real) -- un diseno STL de un diente o una corona pesa mucho
mas que eso normalmente, asi que al intentar subirlo salia el error "El
archivo pesa demasiado (maximo 5MB)" aunque el archivo fuera un STL de
laboratorio totalmente normal.

Por que: David lo encontro al probar el visor STL recien entregado -- pudo
llegar al boton de subir diseno, pero el archivo que intento subir se
rechazo por pesar mas de 5MB.

Que cambia:
- backend/app.py: nueva constante MAX_DISENO_STL_BASE64 (~30MB de archivo
  real) SOLO para el endpoint POST /api/laboratorio/{id}/subir-diseno --
  no toca el limite de 5MB que se usa en todos los demas adjuntos de la
  app (fotos, firmas, comprobantes, etc.), esos se quedan igual.
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            'MAX_ADJUNTO_BASE64 = 7_000_000  # ~5MB de archivo real (base64 pesa ~33% más)',
            'MAX_ADJUNTO_BASE64 = 7_000_000  # ~5MB de archivo real (base64 pesa ~33% más)\nMAX_DISENO_STL_BASE64 = 40_000_000  # ~30MB de archivo real -- un diseño STL de laboratorio pesa mucho más que una foto/firma/comprobante',
        ],
        [
            '    if len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")\n    estado_anterior = trabajo["estado"]\n    db.subir_diseno_laboratorio(trabajo_id, payload.archivo_base64, payload.archivo_nombre, usuario["id"])',
            '    if len(payload.archivo_base64) > MAX_DISENO_STL_BASE64:\n        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~30MB) -- comprímelo o expórtalo con menos resolución")\n    estado_anterior = trabajo["estado"]\n    db.subir_diseno_laboratorio(trabajo_id, payload.archivo_base64, payload.archivo_nombre, usuario["id"])',
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
    print("    git add backend/app.py")
    print('    git commit -m "Laboratorio: sube el limite de tamano del STL de diseno a ~30MB"')
    print("    git push")


if __name__ == "__main__":
    main()
