# -*- coding: utf-8 -*-
"""Unidental: el administrador puede entrar a la app aunque la tienda todavia no este activada
(antes salia "Tienda no encontrada" y no habia forma de activarla).
Correr en la carpeta tickets-ti:  py -3 fix_unidental_activar.py
"""
import os, sys

ARCHIVOS = {
 "backend/tienda.py": [
  [
   "    \"\"\"Entra el doctor (o el administrador de la tienda) — solo cuentas de ESTA tienda.\"\"\"\n    t = tienda_por_codigo(codigo)\n",
   "    \"\"\"Entra el doctor (o el administrador de la tienda) — solo cuentas de ESTA tienda.\n    Mientras la tienda no está activada, puede entrar un administrador para activarla.\"\"\"\n    t = _q(\"SELECT * FROM tienda_config WHERE codigo = %s\", (codigo.strip().lower(),), uno=True)\n"
  ],
  [
   "        raise HTTPException(status_code=401, detail=\"Correo o contraseña incorrectos.\")\n    if u.get(\"empresa_id\") != t[\"empresa_id\"] or u[\"rol\"] not in (\"doctor\", \"admin\"):\n",
   "        raise HTTPException(status_code=401, detail=\"Correo o contraseña incorrectos.\")\n    if t is None:\n        if u[\"rol\"] == \"admin\" and u.get(\"empresa_id\"):\n            return _token_respuesta(u)\n        raise HTTPException(status_code=404, detail=\"La tienda todavía no está activada. Entra con el administrador para activarla.\")\n    if u.get(\"empresa_id\") != t[\"empresa_id\"] or u[\"rol\"] not in (\"doctor\", \"admin\"):\n"
  ]
 ]
}

NUEVOS = {}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_unidental_activar.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto and viejo not in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
