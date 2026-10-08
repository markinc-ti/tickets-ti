# -*- coding: utf-8 -*-
"""
Corrige que el portal de estudiantes de Laboratorio (registro, login, e
importar desde DS Core) muestre "[object Object]" en vez del error real
cuando el servidor rechaza algo (por ejemplo, una contrasena de menos de
6 caracteres, o un telefono que no tiene 10 digitos).

Por que pasaba: cuando FastAPI rechaza datos invalidos (error 422), manda
el detalle como una LISTA de objetos, no como texto. El codigo de esta
pantalla hacia "new Error(err.detail || ...)" y le pasaba esa lista
directo -- JavaScript la convierte en el inutil "[object Object]" en vez
de mostrar el mensaje real. Este mismo bug ya se habia corregido antes en
la pantalla principal de administrador, pero se le paso aplicar aqui, en
la pantalla aparte que usan los estudiantes.

Que cambia, con nombres exactos:
  - frontend/laboratorio_estudiantes.html: la funcion api() de esta
    pantalla ahora arma un mensaje legible tanto si el error viene como
    texto normal, como si viene como la lista de FastAPI, o como
    cualquier otro objeto -- igual que ya funciona en la pantalla
    principal.

Uso: coloca este script en la carpeta del repo (junto a backend/ y
frontend/) y corre:
    py fix_error_legible_portal_estudiantes.py
"""
import os
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
ARCHIVOS['frontend/laboratorio_estudiantes.html'] = [
    [
        "  async function api(ruta, opciones = {}) {\n    const headers = { 'Content-Type': 'application/json' };\n    if (TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`;\n    const resp = await fetch(ruta, { ...opciones, headers: { ...headers, ...(opciones.headers || {}) } });\n    if (!resp.ok) {\n      const err = await resp.json().catch(() => ({}));\n      throw new Error(err.detail || 'Ocurrió un error, intenta de nuevo.');\n    }\n    return resp.status === 204 ? null : resp.json();\n  }",
        '  async function api(ruta, opciones = {}) {\n    const headers = { \'Content-Type\': \'application/json\' };\n    if (TOKEN) headers[\'Authorization\'] = `Bearer ${TOKEN}`;\n    const resp = await fetch(ruta, { ...opciones, headers: { ...headers, ...(opciones.headers || {}) } });\n    if (!resp.ok) {\n      const err = await resp.json().catch(() => ({}));\n      let mensaje = err.detail;\n      // err.detail puede venir como texto (caso normal), como lista de errores de\n      // validación de FastAPI (422), o como algún otro objeto -- nunca lo pasamos\n      // crudo a new Error(), porque JS lo convertiría en el inútil texto "[object Object]".\n      if (Array.isArray(mensaje)) {\n        mensaje = mensaje.map(m => (m && typeof m === \'object\') ? (m.msg || JSON.stringify(m)) : m).join(\'; \');\n      } else if (mensaje && typeof mensaje === \'object\') {\n        mensaje = mensaje.msg || JSON.stringify(mensaje);\n      }\n      throw new Error(mensaje || \'Ocurrió un error, intenta de nuevo.\');\n    }\n    return resp.status === 204 ? null : resp.json();\n  }',
    ]
]

# ---------------------------------------------------------------------------


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
    ok = aplicar_reemplazos("frontend/laboratorio_estudiantes.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/laboratorio_estudiantes.html")
    print('   git commit -m "Portal de estudiantes: muestra el error real en vez de [object Object]"')
    print("   git push")


if __name__ == "__main__":
    main()
