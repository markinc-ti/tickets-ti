# -*- coding: utf-8 -*-
"""
SOPORTE (Peymar) -- las evidencias que se suben desde la app (iOS/Android)
llegan sin tipo de archivo: ahora el servidor lo deduce del nombre (foto.jpg ->
imagen), para que se vean las miniaturas y salgan en los PDFs.
REQUIERE haber corrido antes fix_reparaciones_alta_encargada.py.
Toca: backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_soporte_evidencia_app.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    if len(datos) > MAX_EVIDENCIA_SOPORTE:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 20 MB. Mándalo más corto o comprimido.\")\n    tipo = archivo.content_type or \"application/octet-stream\"\n    url, b64 = None, None\n    import r2\n    if not tipo.startswith(\"image\") and len(datos) > 3 * 1024 * 1024 and r2.configurado():\n",
   "    if len(datos) > MAX_EVIDENCIA_SOPORTE:\n        raise HTTPException(status_code=400, detail=\"El archivo pesa más de 20 MB. Mándalo más corto o comprimido.\")\n    tipo = archivo.content_type or \"application/octet-stream\"\n    if tipo == \"application/octet-stream\":\n        # Las apps suben sin tipo: se deduce del nombre (foto.jpg → image/jpeg).\n        import mimetypes\n        tipo = mimetypes.guess_type(archivo.filename or \"\")[0] or tipo\n    url, b64 = None, None\n    import r2\n    if not tipo.startswith(\"image\") and len(datos) > 3 * 1024 * 1024 and r2.configurado():\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_soporte_evidencia_app.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "La encargada da de alta en SU sucursal" not in f.read():
            print("Primero corre fix_reparaciones_alta_encargada.py (y los anteriores), y luego este.")
            sys.exit(1)
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    bin_cambios = {}
    for ruta, b64 in NUEVOS_BIN.items():
        datos = base64.b64decode(b64)
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                if f.read() == datos:
                    continue
        bin_cambios[ruta] = datos
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append("No encontre {} -- corre el script desde la carpeta del repo.".format(ruta))
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        # Windows: el archivo puede tener saltos CRLF, LF o una mezcla.
        # Se trabaja todo en LF y al guardar se deja como estaba (CRLF si tenia).
        crlf = "\r\n" in original
        texto = original.replace("\r\n", "\n")
        inicial = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue  # ya aplicado
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo, 1)
        if texto != inicial:
            cambios[ruta] = texto.replace("\n", "\r\n") if crlf else texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, datos in bin_cambios.items():
        with open(ruta, "wb") as f:
            f.write(datos)
        print("Actualizado:", ruta)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios and not bin_cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
