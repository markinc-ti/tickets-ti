# -*- coding: utf-8 -*-
"""
Login (tickets-ti y portal de estudiantes) — ya no se autocompleta la
contraseña guardada al elegir un usuario de la lista del navegador.

Qué hace:
En una computadora compartida (ej. una sucursal), cuando dos o más
personas ya iniciaron sesión ahí antes, el navegador ofrece una lista
de usuarios ya usados al dar clic en el campo "Usuario". Hasta ahora,
al elegir uno de esa lista, el navegador también rellenaba solo la
contraseña que tenía guardada de esa persona — y con eso ya se podía
entrar sin teclear nada, sin importar quién estuviera frente a la
pantalla.

Con este cambio: la lista de usuarios ya escritos sigue apareciendo
igual que antes (eso el navegador lo sigue recordando y no se toca),
pero ya NO se rellena sola la contraseña guardada al elegir un usuario
— toca escribirla a mano cada vez. Si después de escribirla el
navegador pregunta si quiere guardarla para la próxima vez, eso sigue
funcionando normal.

Aplica el mismo cambio en dos pantallas de login: la principal de
tickets-ti y la del portal de estudiantes de laboratorio.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_login_password_sin_autocompletar.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# frontend/index.html — login principal (superadmin / usuarios de empresa)
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        '<input id="login_pass" type="password" autocapitalize="off" autocomplete="current-password" style="padding-right:44px; text-transform:none;" />',
        '<input id="login_pass" type="password" autocapitalize="off" autocomplete="new-password" style="padding-right:44px; text-transform:none;" />',
    ],
]

# ---------------------------------------------------------------------------
# frontend/laboratorio_estudiantes.html — login del portal de estudiantes
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/laboratorio_estudiantes.html'] = [
    [
        '<div class="field"><label>Contraseña</label><input id="li_password" type="password" autocomplete="current-password" /></div>',
        '<div class="field"><label>Contraseña</label><input id="li_password" type="password" autocomplete="new-password" /></div>',
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
            print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
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
                print(f"[{ruta}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html frontend/laboratorio_estudiantes.html")
    print('   git commit -m "Login: no autocompletar contraseña guardada al elegir un usuario de la lista"')
    print("   git push")


if __name__ == "__main__":
    main()
