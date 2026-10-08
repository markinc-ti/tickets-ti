# -*- coding: utf-8 -*-
"""
Arreglo: "Llamar siguiente" en Turnos daba error 500

Bug real (mio, no tuyo): en el endpoint que llama al siguiente turno,
cuando un usuario del mostrador NO tiene una ventanilla/caja fija
asignada (el caso normal, por default), el codigo intentaba leer
usuario["nombre_completo"] -- pero esa llave no existe ahi (tu sesion
guarda el nombre como "nombre", no "nombre_completo"), asi que tronaba
con un error 500 cada vez que alguien sin ventanilla asignada le daba
clic a "Llamar siguiente". Si el usuario SI tenia una ventanilla
asignada (ej. "Caja 5"), no se notaba porque ese caso ni siquiera
llegaba a leer esa llave.

Ya lo probe con los dos casos (con y sin ventanilla asignada) antes de
mandarte esto.

Que toca:
  - backend/app.py -- una sola linea en el endpoint POST
    /api/turnos/{turno_id}/llamar.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    python fix_turnos_llamar_bug.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['backend/app.py'] = [
    [
        '    ventanilla = usuario.get("ventanilla_turnos") or usuario["nombre_completo"]\n    db.llamar_turno(turno_id, ventanilla, usuario["id"])',
        '    ventanilla = usuario.get("ventanilla_turnos") or usuario["nombre"]\n    db.llamar_turno(turno_id, ventanilla, usuario["id"])',
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False

    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print("[" + ruta + "] " + str(cambios) + "/" + str(len(cambios_lista)) + " cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Arreglar error 500 al llamar turno sin ventanilla asignada"')
    print("   git push")


if __name__ == "__main__":
    main()
