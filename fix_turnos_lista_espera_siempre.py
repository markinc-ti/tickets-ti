# -*- coding: utf-8 -*-
"""
Turnos: la lista de "a quien llamar" (del cambio anterior,
fix_turnos_llamar_elegir.py) solo aparecia cuando habia MAS DE UNA
persona esperando -- si solo habia una (o ninguna) en fila, no se veia
nada distinto y parecia que el cambio no habia hecho nada. Ahora la
lista aparece en cuanto hay AL MENOS UNA persona esperando.

IMPORTANTE: este script es una continuacion de fix_turnos_llamar_elegir.py
(que a su vez va despues de fix_turnos_categorias_reporte.py). Corre
este DESPUES de esos dos.

Que toca:
  - frontend/index.html -- la pantalla de Turnos del mostrador.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_turnos_lista_espera_siempre.py

Si despues de correrlo y hacer push la pantalla SIGUE viendose igual,
casi seguro es el navegador mostrando una version guardada en cache:
en la pantalla de Turnos del mostrador, refresca forzado (Ctrl+F5 en
Windows/Linux, Cmd+Shift+R en Mac) o cierra y abre la pestana de nuevo.
"""
import sys

ARCHIVOS = {}

ARCHIVOS["frontend/index.html"] = [
    [
        "    ${esperando.length > 1 ? `",
        "    ${esperando.length > 0 ? `",
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
            print("[" + ruta + "] No se encontro un bloque esperado. Corriste primero fix_turnos_llamar_elegir.py? El archivo pudo haber cambiado desde la ultima vez.")
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
    print('   git commit -m "Turnos: la lista de a quien llamar aparece siempre que haya al menos uno esperando"')
    print("   git push")


if __name__ == "__main__":
    main()
