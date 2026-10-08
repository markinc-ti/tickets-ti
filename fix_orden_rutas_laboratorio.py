# -*- coding: utf-8 -*-
"""
Laboratorio -- Arregla un bug real (ya existía desde antes de DS Core) en
el orden de las rutas de la API: "GET /api/laboratorio/{trabajo_id}" estaba
registrada ANTES que varias rutas mas especificas que tambien son GET de un
solo segmento bajo /api/laboratorio/ -- y FastAPI/Starlette hace match por
orden de registro, asi que cualquier llamada a esas rutas mas especificas
caia primero en "{trabajo_id}" (que intenta convertir el texto a numero) y
tronaba con un error 422 "Input should be a valid integer" en vez de
ejecutar la ruta correcta.

Esto rompia TRES cosas que ya estaban en produccion (nada de esto lo toque
yo al agregar DS Core, ya estaba asi desde que se agrego el portal de
estudiantes de Laboratorio):

  - GET /api/laboratorio/mios            -> "Mis trabajos" del estudiante
  - GET /api/laboratorio/buscar-entrega  -> buscar por matricula/nombre en ventanilla
  - GET /api/laboratorio/pagos-reportados -> lista de pagos por confirmar

Lo descubri armando el demo simulado de DS Core (al probar "Mis trabajos"
contra un backend real me marco justo este error). Ya lo confirme contra
una copia limpia bajada directo de GitHub -- no es nada de mi entorno de
prueba, esta en el repo real ahorita mismo.

El arreglo: mover la ruta "GET /api/laboratorio/{trabajo_id}" hasta el
final del bloque de rutas de Laboratorio (justo antes de donde empiezan las
de DS Core), sin tocar nada de su contenido -- asi las rutas especificas de
arriba se evaluan primero y ya no las tapa.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_orden_rutas_laboratorio.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['backend/app.py'] = [
    [
        '    db.firmar_recepcion_laboratorio(usuario["empresa_id"], trabajo_id, payload.firma_recepcion)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"{trabajo[\'solicitante_nombre\']} firmó de recepción.")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.get("/api/laboratorio/{trabajo_id}")\ndef api_obtener_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    return trabajo\n\n\n@app.patch("/api/laboratorio/{trabajo_id}")',
        '    db.firmar_recepcion_laboratorio(usuario["empresa_id"], trabajo_id, payload.firma_recepcion)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"{trabajo[\'solicitante_nombre\']} firmó de recepción.")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n\n\n@app.patch("/api/laboratorio/{trabajo_id}")',
    ],
    [
        '@app.get("/api/laboratorio/dscore/config")',
        '@app.get("/api/laboratorio/{trabajo_id}")\ndef api_obtener_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    return trabajo\n\n\n@app.get("/api/laboratorio/dscore/config")',
    ],
]


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


def main():
    ok = True
    ok = aplicar_reemplazos("backend/app.py") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py")
    print('   git commit -m "Laboratorio: arregla que GET /mios, /buscar-entrega y /pagos-reportados tronaban por el orden de las rutas"')
    print("   git push")


if __name__ == "__main__":
    main()
