# -*- coding: utf-8 -*-
"""
Arregla que en "modo claro" se pierdan letras/texto en paneles de la
app (por ejemplo en "Tus tareas de proyecto pendientes"), mientras que
en "modo oscuro" se ve bien.

Que estaba pasando: estas pantallas (panel de administracion, kiosko,
pantalla de TV, seguimiento de entregas) SIEMPRE usan un tema oscuro
fijo -- no tienen ni han tenido nunca un modo claro propio. El
problema es que nunca le avisabamos eso al navegador. Entonces, cuando
el celular o la compu del usuario esta en modo claro, algunos
navegadores (sobre todo en Android) intentan "ayudar" ajustando
automaticamente colores de fondo/texto en ciertos controles para que
combinen con el modo claro del sistema -- pero como esta app ya trae
sus propios colores oscuros a proposito, ese ajuste automatico
choca con ellos y el texto pierde contraste (letras claras sobre
fondo claro, casi invisibles). En modo oscuro no pasaba porque el
navegador no tenia nada que "corregir".

Que se arregla: se le dice explicitamente al navegador, con
color-scheme, que esta app SIEMPRE es oscura -- para que deje de
intentar recolorear nada por su cuenta sin importar si el celular/compu
del usuario esta en modo claro u oscuro.

Que toca:
  - frontend/index.html -- panel de administracion.
  - frontend/kiosko_turnos.html -- kiosko de tomar turno.
  - frontend/pantalla_turnos.html -- pantalla de TV de la sala de
    espera.
  - frontend/seguimiento.html -- seguimiento de entregas.

(No toca frontend/cotizador_costos.html ni frontend/gantt.html porque
esos ya manejan su propio tema claro/oscuro aparte.)

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_modo_claro_letras.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["frontend/index.html"] = [
    [
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n<title>Tickets TI</title>",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n<meta name=\"color-scheme\" content=\"dark\" />\n<title>Tickets TI</title>",
    ],
    [
        "  :root {\n    --substrate: #1A1B1D;",
        "  :root {\n    /* La app siempre usa este tema oscuro (no hay modo claro) -- se lo\n       decimos al navegador explicitamente con color-scheme para que NO\n       intente \"ayudar\" recoloreando u oscureciendo/aclarando controles\n       por su cuenta cuando el celular/compu está en modo claro. Sin\n       esto, algunos navegadores (sobre todo en Android) podían\n       perder el contraste del texto en ciertos paneles. */\n    color-scheme: dark;\n    --substrate: #1A1B1D;",
    ],
]

ARCHIVOS["frontend/kiosko_turnos.html"] = [
    [
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\" />\n<title>Tomar turno</title>\n<style>\n  * { box-sizing: border-box; }",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\" />\n<meta name=\"color-scheme\" content=\"dark\" />\n<title>Tomar turno</title>\n<style>\n  * { box-sizing: border-box; color-scheme: dark; }",
    ],
]

ARCHIVOS["frontend/pantalla_turnos.html"] = [
    [
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0\" />\n<title>Turnos — Pantalla</title>\n<style>\n  * { box-sizing: border-box; }",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0\" />\n<meta name=\"color-scheme\" content=\"dark\" />\n<title>Turnos — Pantalla</title>\n<style>\n  * { box-sizing: border-box; color-scheme: dark; }",
    ],
]

ARCHIVOS["frontend/seguimiento.html"] = [
    [
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0\" />\n<title>Seguimiento de tu entrega</title>\n<link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css\" />\n<style>",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0\" />\n<meta name=\"color-scheme\" content=\"dark\" />\n<title>Seguimiento de tu entrega</title>\n<link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css\" />\n<style>\n  :root { color-scheme: dark; }",
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
    print('   git commit -m "Arregla que se pierdan letras en modo claro -- le decimos al navegador que la app siempre es oscura"')
    print("   git push")


if __name__ == "__main__":
    main()
