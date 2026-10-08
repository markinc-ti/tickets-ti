#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Endpoint TEMPORAL de diagnostico para DS Core: agrega
GET /api/laboratorio/dscore/debug-orders (solo administrador) que regresa
tal cual la respuesta real de DS Core en /v1beta/orders.

Por que: ya se resolvio el bloqueo de "laboratorio preferido" (viene de
Dentsply, no de tickets-ti) y ya se curso un pedido de prueba real
(2ABK0N0P), pero al intentar importarlo desde el portal de estudiantes
salio "No encontramos ningun pedido con ese codigo en DS Core". El codigo
de busqueda (buscar_order_por_codigo en backend/dscore.py) se escribio
ANTES de tener acceso real al sandbox, basado solo en la documentacion --
nunca se pudo probar contra un pedido real hasta ahora. Lo mas probable es
que el campo que trae el codigo legible del pedido no se llame
"readableId" como se asumio, o que el filtro que se manda no sea el que
espera la API real.

Este endpoint no cambia nada de lo que ya funciona -- solo agrega una
forma de ver la respuesta real de DS Core para poder corregir
buscar_order_por_codigo() con datos reales en vez de seguir adivinando.
Una vez resuelto esto se puede quitar (avisenme y los saco).

Como usarlo: con la sesion de administrador iniciada en el navegador,
entra a esta direccion (ajusta el dominio si no es el de producción):

    https://tickets-ti-n4wn.onrender.com/api/laboratorio/dscore/debug-orders

Te va a salir un JSON en la pantalla -- mandame una captura o copia y pega
el texto completo.

Que cambia:
- backend/dscore.py: nueva funcion obtener_orders_crudo() (no toca nada existente)
- backend/app.py: nuevo endpoint GET /api/laboratorio/dscore/debug-orders
"""
import sys

ARCHIVOS = {
    'backend/dscore.py': [
        [
            'def probar_conexion(base_host, access_token):\n    try:\n        _get(base_host, access_token, "/v1beta/orders", params={"pageSize": 1})\n    except DSCoreError as e:\n        return False, str(e)\n    return True, "Conectado correctamente con DS Core."\n',
            'def probar_conexion(base_host, access_token):\n    try:\n        _get(base_host, access_token, "/v1beta/orders", params={"pageSize": 1})\n    except DSCoreError as e:\n        return False, str(e)\n    return True, "Conectado correctamente con DS Core."\n\n\ndef obtener_orders_crudo(base_host, access_token, page_size=5):\n    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,\n    sin interpretar nada, para poder ver con datos reales (no documentacion)\n    como se llama de verdad el campo del codigo legible del pedido y que\n    forma tiene cada order. Se usa una sola vez desde el endpoint de debug\n    para ajustar buscar_order_por_codigo() con la forma real de los datos."""\n    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})\n',
        ],
    ],
    'backend/app.py': [
        [
            '@app.post("/api/laboratorio/dscore/probar-conexion")\ndef api_probar_conexion_dscore(usuario: dict = Depends(requiere_admin_completo)):\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    ok, mensaje = dscore.probar_conexion(tokens["base_host"], access_token)\n    if not ok:\n        raise HTTPException(status_code=400, detail=mensaje)\n    return {"ok": True, "mensaje": mensaje}\n',
            '@app.post("/api/laboratorio/dscore/probar-conexion")\ndef api_probar_conexion_dscore(usuario: dict = Depends(requiere_admin_completo)):\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    ok, mensaje = dscore.probar_conexion(tokens["base_host"], access_token)\n    if not ok:\n        raise HTTPException(status_code=400, detail=mensaje)\n    return {"ok": True, "mensaje": mensaje}\n\n\n@app.get("/api/laboratorio/dscore/debug-orders")\ndef api_debug_orders_dscore(usuario: dict = Depends(requiere_admin_completo)):\n    """SOLO PARA DIAGNOSTICO (temporal) -- regresa tal cual lo que contesta\n    DS Core en /v1beta/orders, para poder ver con un pedido real cómo se\n    llama de verdad el campo del código legible y ajustar la búsqueda por\n    código en consecuencia. Se puede quitar una vez resuelto."""\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale \'Conectar con DS Core\' primero).")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    try:\n        return dscore.obtener_orders_crudo(tokens["base_host"], access_token, page_size=5)\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")\n',
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
    print('    git commit -m "DS Core: endpoint temporal de diagnostico para ver la respuesta real de /v1beta/orders"')
    print("    git push")


if __name__ == "__main__":
    main()
