#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DS Core: endpoint temporal de diagnostico para ver como expone DS Core el
contenido de un archivo de un pedido (digitalImpressions/documents), antes
de programar la descarga real de los escaneos STL originales.

Contexto: David aclaro que lo que necesita AHORA es que el laboratorio
pueda descargar el escaneo STL ORIGINAL del pedido (el que se hizo en
Sirona), una vez que el pago esta confirmado -- no el archivo de diseno
que el laboratorio sube despues (eso ya esta hecho, es "Aprobar diseno").

Con el endpoint de diagnostico que ya existe (/debug-orders) se confirmo
que cada order trae un campo "files" con entradas como:

    {"uri": "digitalImpressions/dxd-...", "label": "DI_SCAN"}

Ese "uri" es el mismo tipo de referencia que "patient.uri" (que se
resuelve pidiendo /v1beta/{uri}) -- pero todavia no se sabe si al pedir
/v1beta/digitalImpressions/{id} DS Core regresa el archivo binario
directo, un JSON con metadatos/link de descarga, o algo mas. Este parche
agrega el endpoint para verlo con un archivo real, siguiendo la misma
practica de este proyecto de no adivinar la forma de la respuesta.

Que cambia:
- backend/dscore.py: nueva funcion obtener_archivo_crudo_diagnostico() --
  hace GET a /v1beta/{uri} SIN forzar que la respuesta sea JSON (a
  diferencia de _get(), que si lo fuerza) y regresa metadatos de la
  respuesta cruda: status, Content-Type, tamano, si hubo redireccion, y
  o el JSON completo (si el Content-Type es JSON) o los primeros bytes en
  base64 (si es binario), para poder ver la forma real sin arriesgarse a
  regresar un archivo completo de varios MB en la respuesta de diagnostico.
- backend/app.py: nuevo endpoint GET /api/laboratorio/dscore/debug-file
  (solo admin, temporal, se puede quitar despues) -- recibe ?uri=... y
  llama a la funcion de arriba.
"""
import sys

ARCHIVOS = {
    'backend/dscore.py': [
        [
            'def obtener_orders_crudo(base_host, access_token, page_size=5):\n    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,\n    sin interpretar nada, para poder ver con datos reales (no documentacion)\n    como se llama de verdad el campo del codigo legible del pedido y que\n    forma tiene cada order. Se usa una sola vez desde el endpoint de debug\n    para ajustar buscar_order_por_codigo() con la forma real de los datos."""\n    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})',
            'def obtener_orders_crudo(base_host, access_token, page_size=5):\n    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,\n    sin interpretar nada, para poder ver con datos reales (no documentacion)\n    como se llama de verdad el campo del codigo legible del pedido y que\n    forma tiene cada order. Se usa una sola vez desde el endpoint de debug\n    para ajustar buscar_order_por_codigo() con la forma real de los datos."""\n    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})\n\n\ndef obtener_archivo_crudo_diagnostico(base_host, access_token, uri):\n    """SOLO PARA DIAGNOSTICO -- pide directamente la \'uri\' de un archivo\n    del pedido (el campo \'files[].uri\' de un order, ej.\n    \'digitalImpressions/dxd-...\') siguiendo el mismo patron que ya\n    funciona para resolver patient.uri (GET /v1beta/{uri}), pero SIN\n    forzar que la respuesta sea JSON -- para poder ver si DS Core regresa\n    el archivo binario directo, un JSON con metadatos/link de descarga, o\n    algo mas, antes de programar la descarga real de los escaneos STL\n    originales del pedido."""\n    try:\n        r = requests.get(\n            f"{base_host.rstrip(\'/\')}/v1beta/{uri.lstrip(\'/\')}",\n            headers={"Authorization": f"Bearer {access_token}"},\n            timeout=TIMEOUT,\n        )\n    except requests.RequestException as e:\n        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")\n    content_type = r.headers.get("Content-Type", "")\n    resultado = {\n        "status_code": r.status_code,\n        "content_type": content_type,\n        "content_length_header": r.headers.get("Content-Length"),\n        "bytes_recibidos": len(r.content),\n        "hubo_redireccion": bool(r.history),\n        "url_final": r.url,\n        "headers_respuesta": dict(r.headers),\n    }\n    if "json" in content_type.lower():\n        try:\n            resultado["json"] = r.json()\n        except ValueError:\n            resultado["texto_preview"] = r.text[:2000]\n    else:\n        resultado["primeros_bytes_base64"] = base64.b64encode(r.content[:800]).decode("ascii")\n    return resultado',
        ],
    ],
    'backend/app.py': [
        [
            '@app.get("/api/laboratorio/dscore/debug-orders")\ndef api_debug_orders_dscore(usuario: dict = Depends(requiere_admin_completo)):\n    """SOLO PARA DIAGNOSTICO (temporal) -- regresa tal cual lo que contesta\n    DS Core en /v1beta/orders, para poder ver con un pedido real cómo se\n    llama de verdad el campo del código legible y ajustar la búsqueda por\n    código en consecuencia. Se puede quitar una vez resuelto."""\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    try:\n        return dscore.obtener_orders_crudo(tokens["base_host"], access_token, page_size=5)\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")',
            '@app.get("/api/laboratorio/dscore/debug-orders")\ndef api_debug_orders_dscore(usuario: dict = Depends(requiere_admin_completo)):\n    """SOLO PARA DIAGNOSTICO (temporal) -- regresa tal cual lo que contesta\n    DS Core en /v1beta/orders, para poder ver con un pedido real cómo se\n    llama de verdad el campo del código legible y ajustar la búsqueda por\n    código en consecuencia. Se puede quitar una vez resuelto."""\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    try:\n        return dscore.obtener_orders_crudo(tokens["base_host"], access_token, page_size=5)\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")\n\n\n@app.get("/api/laboratorio/dscore/debug-file")\ndef api_debug_file_dscore(uri: str, usuario: dict = Depends(requiere_admin_completo)):\n    """SOLO PARA DIAGNOSTICO (temporal) -- pide directamente el \'uri\' de un\n    archivo de un pedido (tomado del campo \'files\' que ya vimos en\n    /debug-orders, ej. \'digitalImpressions/dxd-...\') para ver cómo lo\n    expone DS Core de verdad (binario directo, JSON con link de descarga,\n    etc.) antes de programar la descarga real de los escaneos STL\n    originales del pedido. Se puede quitar una vez resuelto."""\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    try:\n        return dscore.obtener_archivo_crudo_diagnostico(tokens["base_host"], access_token, uri)\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")',
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
    print("    git add backend/dscore.py backend/app.py")
    print('    git commit -m "DS Core: endpoint temporal de diagnostico para ver como se descarga un archivo del pedido"')
    print("    git push")


if __name__ == "__main__":
    main()
