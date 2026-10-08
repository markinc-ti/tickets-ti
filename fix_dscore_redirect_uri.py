# -*- coding: utf-8 -*-
"""
Ajusta la URL de regreso (Redirect URL) que usa tickets-ti para el login de
DS Core, para que coincida EXACTO con la que quedo registrada -- y ya
aprobada -- en el portal de desarrolladores (open.dscore.com):

  Antes (lo que ya tenia el codigo):
    https://tickets-ti-n4wn.onrender.com/api/laboratorio/dscore/oauth/callback
  Ahora (lo que de verdad quedo registrado y aprobado, App ID 7196):
    https://tickets-ti-n4wn.onrender.com/api/laboratorio/dscore/callback

OAuth2 exige que la Redirect URL que manda la app y la que tiene registrada
el proveedor sean identicas -- si no coinciden, DS Core rechaza el login.
Como esa app ya esta aprobada con la URL corta (sin "oauth/"), es mas
rapido ajustar el codigo de tickets-ti que pedirle a Dentsply Sirona que
apruebe de nuevo una URL distinta.

Que cambia, con nombres exactos:
  - backend/app.py: la ruta del callback (@app.get(...)) y las dos veces
    que se arma el redirect_uri para mandarlo a DS Core.
  - frontend/index.html: el texto de ayuda en Administrar -> DS Core que
    le muestra al admin la URL a copiar en el portal (solo informativo,
    para que si algun dia se vuelve a registrar coincida).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_dscore_redirect_uri.py
"""
import os
import sys

ARCHIVOS = {
    "backend/app.py": [
        [
            'redirect_uri = f"{base_url}/api/laboratorio/dscore/oauth/callback"\n'
            '    url = dscore.armar_url_login(creds["base_host"], creds["client_id"], redirect_uri, code_challenge, state)',
            'redirect_uri = f"{base_url}/api/laboratorio/dscore/callback"\n'
            '    url = dscore.armar_url_login(creds["base_host"], creds["client_id"], redirect_uri, code_challenge, state)',
        ],
        [
            '@app.get("/api/laboratorio/dscore/oauth/callback")',
            '@app.get("/api/laboratorio/dscore/callback")',
        ],
        [
            'base_url = os.getenv("APP_BASE_URL", "https://tickets-ti-n4wn.onrender.com")\n'
            '    redirect_uri = f"{base_url}/api/laboratorio/dscore/oauth/callback"\n'
            '    try:\n'
            '        access_token, refresh_token, expires_in = dscore.intercambiar_code_por_tokens(',
            'base_url = os.getenv("APP_BASE_URL", "https://tickets-ti-n4wn.onrender.com")\n'
            '    redirect_uri = f"{base_url}/api/laboratorio/dscore/callback"\n'
            '    try:\n'
            '        access_token, refresh_token, expires_in = dscore.intercambiar_code_por_tokens(',
        ],
    ],
    "frontend/index.html": [
        [
            '<br /><code style="font-size:11px; word-break:break-all;">${location.origin}/api/laboratorio/dscore/oauth/callback</code>',
            '<br /><code style="font-size:11px; word-break:break-all;">${location.origin}/api/laboratorio/dscore/callback</code>',
        ],
    ],
}


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
    ok = aplicar_reemplazos("frontend/index.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py frontend/index.html")
    print('   git commit -m "DS Core: ajusta la Redirect URL para que coincida con la ya aprobada en el portal"')
    print("   git push")


if __name__ == "__main__":
    main()
