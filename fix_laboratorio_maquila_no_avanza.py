#!/usr/bin/env python3
"""
Laboratorio: el trabajo se queda atorado en "Maquila (fresado)" y ya no deja
cambiarle el estado -- el flujo real de estados de laboratorio es:

    recibido -> en_laboratorio -> modelado -> aprobar_diseno -> maquila
    -> maquillado -> control_calidad -> envio_sucursal -> listo_entrega -> entregado

Cuando el estudiante aprueba el diseño desde la app/portal, el trabajo pasa
automáticamente a "maquila" (ver api_aprobar_diseno_laboratorio). El
problema: el endpoint "PATCH /api/laboratorio/{id}/estado" (el selector
"Mover estado" del panel) solo permite mover un trabajo que YA esté en
alguno de estos estados: "en_laboratorio", o los de ESTADOS_LABORATORIO_LIBRES
("modelado", "maquillado", "control_calidad", "envio_sucursal", "cancelado")
-- "maquila" nunca se agregó a esa lista de estados de partida válidos, así
que en cuanto un trabajo llega a "maquila" (automáticamente, al aprobar el
diseño), CUALQUIER intento de moverlo más allá (a "maquillado", etc.) se
rechaza con "Este trabajo todavía no ha entrado al laboratorio, o ya se
envió de vuelta a la sucursal" -- un mensaje que además no aplica nada al
caso real. Esto deja el trabajo atorado ahí para siempre desde el panel del
laboratorio.

Fix: agregar "maquila" a la lista de estados de partida válidos en ese
checkeo. No cambia nada más del flujo (el checkeo de diseño aprobado, unas
líneas abajo, ya no bloquea nada al venir de "maquila" -- solo bloquea
viniendo de "modelado"/"aprobar_diseno", que es la parte correcta).
"""

ARCHIVOS = {
    "backend/app.py": [
        [
            '''        if trabajo["estado"] not in ("en_laboratorio", *ESTADOS_LABORATORIO_LIBRES) or trabajo["estado"] == "envio_sucursal":
            raise HTTPException(status_code=400, detail="Este trabajo todavía no ha entrado al laboratorio, o ya se envió de vuelta a la sucursal")''',
            '''        if trabajo["estado"] not in ("en_laboratorio", "maquila", *ESTADOS_LABORATORIO_LIBRES) or trabajo["estado"] == "envio_sucursal":
            raise HTTPException(status_code=400, detail="Este trabajo todavía no ha entrado al laboratorio, o ya se envió de vuelta a la sucursal")''',
        ],
    ],
}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    for ruta, cambios in ARCHIVOS.items():
        contenido = leer(ruta)
        original = contenido
        for viejo, nuevo in cambios:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                raise SystemExit(f"[ERROR] No se encontró el texto esperado en {ruta} -- puede que ya haya cambiado. Aborta sin tocar nada.")
            contenido = contenido.replace(viejo, nuevo, 1)
        if contenido != original:
            escribir(ruta, contenido)
            print(f"[OK] Actualizado: {ruta}")
        else:
            print(f"[OK] Ya estaba aplicado: {ruta}")

    print()
    print("Listo. Ahora corre:")
    print("  git add backend/app.py")
    print('  git commit -m "Laboratorio: corrige trabajo atorado en Maquila que no dejaba cambiar de estado"')
    print("  git push")


if __name__ == "__main__":
    main()
