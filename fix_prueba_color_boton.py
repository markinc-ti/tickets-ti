# -*- coding: utf-8 -*-
"""
PRUEBA: este script NO arregla ni agrega nada -- solo cambia el color
del boton de "Tomar turno" del kiosko, de rojo (#D8192F) a un rojo un
poco mas oscuro (#B01426). Es un cambio puramente de CSS, en un solo
archivo de frontend, sin tocar Python ni la base de datos.

Se hizo para probar algo muy concreto: si esto TAMBIEN se queda
colgado 15 minutos igual que los deploys anteriores, entonces el
problema definitivamente es de Render (su plan gratis aprovisionando
la instancia) y no de ningun cambio de codigo -- porque un cambio de
color no puede colgar el arranque de la app.

Que toca:
  - frontend/kiosko_turnos.html -- SOLO el color del boton.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_prueba_color_boton.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["frontend/kiosko_turnos.html"] = [
    [
        "#btnTomar { width:100%; padding:28px; font-size:22px; font-weight:700; border-radius:14px; border:none; background:#D8192F; color:#fff; cursor:pointer; }",
        "#btnTomar { width:100%; padding:28px; font-size:22px; font-weight:700; border-radius:14px; border:none; background:#B01426; color:#fff; cursor:pointer; }",
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in ARCHIVOS[ruta]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
            hubo_error = True
    escribir(ruta, contenido)
    print("[" + ruta + "] " + str(cambios) + "/" + str(len(ARCHIVOS[ruta])) + " cambio(s) aplicado(s).")
    return not hubo_error


def main():
    ok = True
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Prueba: solo cambia el color del boton del kiosko (sin tocar backend)"')
    print("   git push")


if __name__ == "__main__":
    main()
