#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DS Core: hace mas seguro el endpoint temporal de diagnostico de archivos
(el de fix_dscore_debug_archivo.py) antes de usarlo contra el contenido
real del escaneo.

IMPORTANTE -- este parche depende de que YA este aplicado
fix_dscore_debug_archivo.py. Si ese parche todavia no se ha corrido, corre
PRIMERO fix_dscore_debug_archivo.py y DESPUES este.

Por que: al pedir los metadatos de un escaneo real (digitalImpressions/...)
salio que el archivo STL puede pesar ~25MB, el PLY ~38MB y el DXD
~107MB (campo estimatedContentSizesBytes). La version anterior del
diagnostico descargaba la respuesta COMPLETA a memoria nada mas para
enseñar los primeros bytes -- en el plan gratis de Render (poca RAM) eso
es arriesgado si el siguiente paso es pedir el contenido real del archivo
(.../content), no solo sus metadatos.

Que cambia:
- backend/dscore.py: obtener_archivo_crudo_diagnostico() ahora pide la
  respuesta con stream=True y solo lee un pedazo chico (800 bytes) para
  el preview -- nunca descarga el archivo completo. También agrega
  Content-Disposition a lo que regresa (por si el nombre/extensión real
  del archivo viene ahí).
"""
import sys

ARCHIVOS = {
    'backend/dscore.py': [
        [
            'def obtener_archivo_crudo_diagnostico(base_host, access_token, uri):\n    """SOLO PARA DIAGNOSTICO -- pide directamente la \'uri\' de un archivo\n    del pedido (el campo \'files[].uri\' de un order, ej.\n    \'digitalImpressions/dxd-...\') siguiendo el mismo patron que ya\n    funciona para resolver patient.uri (GET /v1beta/{uri}), pero SIN\n    forzar que la respuesta sea JSON -- para poder ver si DS Core regresa\n    el archivo binario directo, un JSON con metadatos/link de descarga, o\n    algo mas, antes de programar la descarga real de los escaneos STL\n    originales del pedido."""\n    try:\n        r = requests.get(\n            f"{base_host.rstrip(\'/\')}/v1beta/{uri.lstrip(\'/\')}",\n            headers={"Authorization": f"Bearer {access_token}"},\n            timeout=TIMEOUT,\n        )\n    except requests.RequestException as e:\n        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")\n    content_type = r.headers.get("Content-Type", "")\n    resultado = {\n        "status_code": r.status_code,\n        "content_type": content_type,\n        "content_length_header": r.headers.get("Content-Length"),\n        "bytes_recibidos": len(r.content),\n        "hubo_redireccion": bool(r.history),\n        "url_final": r.url,\n        "headers_respuesta": dict(r.headers),\n    }\n    if "json" in content_type.lower():\n        try:\n            resultado["json"] = r.json()\n        except ValueError:\n            resultado["texto_preview"] = r.text[:2000]\n    else:\n        resultado["primeros_bytes_base64"] = base64.b64encode(r.content[:800]).decode("ascii")\n    return resultado',
            'def obtener_archivo_crudo_diagnostico(base_host, access_token, uri):\n    """SOLO PARA DIAGNOSTICO -- pide directamente la \'uri\' de un archivo\n    del pedido (el campo \'files[].uri\' de un order, ej.\n    \'digitalImpressions/dxd-...\') siguiendo el mismo patron que ya\n    funciona para resolver patient.uri (GET /v1beta/{uri}), pero SIN\n    forzar que la respuesta sea JSON -- para poder ver si DS Core regresa\n    el archivo binario directo, un JSON con metadatos/link de descarga, o\n    algo mas, antes de programar la descarga real de los escaneos STL\n    originales del pedido.\n\n    Usa stream=True y solo lee los primeros bytes para el preview -- ya\n    vimos que un escaneo real puede pesar 25-100+ MB (estimatedContentSizesBytes),\n    y este servidor corre con poca RAM (plan gratis de Render), asi que NO\n    conviene descargar el archivo completo nada mas para diagnostico."""\n    try:\n        r = requests.get(\n            f"{base_host.rstrip(\'/\')}/v1beta/{uri.lstrip(\'/\')}",\n            headers={"Authorization": f"Bearer {access_token}"},\n            timeout=TIMEOUT,\n            stream=True,\n        )\n    except requests.RequestException as e:\n        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")\n    content_type = r.headers.get("Content-Type", "")\n    resultado = {\n        "status_code": r.status_code,\n        "content_type": content_type,\n        "content_length_header": r.headers.get("Content-Length"),\n        "content_disposition": r.headers.get("Content-Disposition"),\n        "hubo_redireccion": bool(r.history),\n        "url_final": r.url,\n        "headers_respuesta": dict(r.headers),\n    }\n    if "json" in content_type.lower():\n        try:\n            resultado["json"] = r.json()\n        except ValueError:\n            resultado["texto_preview"] = r.text[:2000]\n    else:\n        preview = b""\n        try:\n            preview = next(r.iter_content(chunk_size=800), b"")\n        except requests.RequestException:\n            pass\n        resultado["primeros_bytes_base64"] = base64.b64encode(preview).decode("ascii")\n        resultado["bytes_leidos_para_preview"] = len(preview)\n    r.close()\n    return resultado',
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
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche,")
                print("o que todavia falte aplicar fix_dscore_debug_archivo.py primero.")
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
    print("    git add backend/dscore.py")
    print('    git commit -m "DS Core: hace mas seguro (streaming) el diagnostico de archivos grandes"')
    print("    git push")


if __name__ == "__main__":
    main()
