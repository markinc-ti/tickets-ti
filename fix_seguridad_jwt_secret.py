#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seguridad: JWT_SECRET ya NO tiene un valor de respaldo fijo/conocido.

Por qué: backend/auth.py usaba
    JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esta-clave-en-produccion")
Si la variable de entorno JWT_SECRET nunca se llegó a configurar en Render
(quedó a medias la última vez que se revisó), el servidor estaba firmando
TODAS las sesiones -- de cualquier usuario, incluido administrador -- con
ese texto fijo, que cualquiera que vea este repositorio puede leer. Con
esa clave, alguien podría forjar un token válido de administrador sin
necesitar contraseña de nadie.

Qué cambia: si JWT_SECRET no está configurado en el entorno, en vez de
usar ese texto conocido, el servidor genera una clave aleatoria nueva
CADA VEZ que arranca (nadie puede adivinarla de antemano) y deja un
aviso bien visible en los logs de Render explicando que hace falta
configurarla. Mientras no se configure, las sesiones de todos se cierran
en cada reinicio/deploy del servidor -- una molestia, pero segura. En
cuanto JWT_SECRET quede configurado como variable de entorno fija en
Render, vuelve a comportarse exactamente igual que antes (una sola clave
estable, sesiones de hasta 7 días) -- este cambio NO afecta nada si
JWT_SECRET ya estaba bien configurado.

IMPORTANTE -- esto no reemplaza confirmar en Render:
1. Entra a Render -> tu servicio (tickets-ti) -> Environment.
2. Busca si ya existe la variable JWT_SECRET.
   - Si SÍ existe con un valor propio: no hay que hacer nada más ahí,
     este parche es solo un refuerzo por si acaso.
   - Si NO existe (o dice justo "cambia-esta-clave-en-produccion"):
     agrégala con un valor largo y aleatorio (ej. generado con
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
     y guarda. ADVERTENCIA: esto cierra la sesión de TODOS los usuarios
     de golpe (tendrán que volver a iniciar sesión) -- hazlo en un
     momento de poco uso.
"""
import sys

ARCHIVOS = {
    'backend/auth.py': [
        [
            'import os\nfrom datetime import datetime, timedelta, timezone\n\nimport bcrypt\nimport jwt\nfrom fastapi import Header, HTTPException\n',
            'import os\nimport secrets\nfrom datetime import datetime, timedelta, timezone\n\nimport bcrypt\nimport jwt\nfrom fastapi import Header, HTTPException\n',
        ],
        [
            'JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esta-clave-en-produccion")\nJWT_ALGORITHM = "HS256"\nJWT_EXPIRA_DIAS = 7\n',
            'JWT_SECRET = os.getenv("JWT_SECRET")\nif not JWT_SECRET:\n    # Nunca usar un valor fijo conocido de respaldo -- cualquiera que vea\n    # este código (o el repositorio en GitHub) podría forjar tokens\n    # válidos, incluso de administrador, si supiera cuál es el valor de\n    # respaldo. Si JWT_SECRET no está configurado en el entorno (Render ->\n    # Environment -> JWT_SECRET), se genera una clave aleatoria SOLO para\n    # este arranque del servidor -- las sesiones existentes se cierran en\n    # cada reinicio/deploy mientras falte configurarlo, pero nunca queda\n    # un secreto adivinable de antemano.\n    JWT_SECRET = secrets.token_urlsafe(48)\n    print(\n        "ADVERTENCIA: la variable de entorno JWT_SECRET no está configurada -- "\n        "se generó una clave aleatoria SOLO para este arranque del servidor "\n        "(las sesiones se cerrarán en el próximo reinicio/deploy). "\n        "Configúrala en Render -> Environment -> JWT_SECRET con un valor fijo "\n        "y secreto para que las sesiones sobrevivan reinicios."\n    )\nJWT_ALGORITHM = "HS256"\nJWT_EXPIRA_DIAS = 7\n',
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
    print("    git add backend/auth.py")
    print('    git commit -m "Seguridad: quitar el respaldo fijo de JWT_SECRET"')
    print("    git push")
    print()
    print("Y NO OLVIDES revisar en Render -> Environment que JWT_SECRET esté")
    print("configurado con un valor propio (ver el encabezado de este archivo).")


if __name__ == "__main__":
    main()
