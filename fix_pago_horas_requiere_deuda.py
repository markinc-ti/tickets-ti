#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RH — Horas: un empleado ya no puede "registrar que pagó horas" si no
debe nada (o por más de lo que debe).

Bug reportado por David con capturas: Yuladi Perez Ramirez registró dos
pagos de horas (15 min y 45 min) sin tener ninguna deuda -- se quedaron
atorados en "Horas pagadas por autorizar" de su encargada, sin poder
autorizarse nunca (el backend ya bloqueaba la AUTORIZACIÓN si la persona
no debía tanto, pero no bloqueaba que el empleado los registrara en
primer lugar). Eso hacía parecer que "se perdió" su movimiento: no
aparecía en "Quién te debe horas" (esa tabla solo lista a quien debe) ni
en ningún lado más, porque un movimiento "pendiente" no cuenta en el
saldo de nadie todavía.

Pedido de David: "SE SUPONE QUE NADIEN PUEDE PAGAR SI NO TIENE DEUDA, SI
NO TUBIERA DEUNDA POR QUE PERMITE EL PAGO".

Qué toca:
- backend/app.py: en POST /api/rh/horas/solicitar-pago, antes de
  registrar el pago se valida que la persona sí tenga saldo pendiente
  (saldo > 0) y que no esté registrando más de lo que debe -- exactamente
  la misma regla que ya existía para cuando RH registra un movimiento
  manual, y para cuando la encargada autoriza un pago ya registrado.
  El frontend no necesita cambios: el formulario de "Registrar horas
  pagadas" ya muestra cualquier error que regrese el servidor.

No toca los dos movimientos de Yuladi que ya quedaron atorados -- esos
hay que rechazarlos a mano (botón "Rechazar" en "Horas pagadas por
autorizar", en la pantalla de la encargada) ya que, con esta regla,
nunca se hubieran podido autorizar.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_pago_horas_requiere_deuda.py
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            '''@app.post("/api/rh/horas/solicitar-pago")
def api_solicitar_pago_horas(payload: SolicitudPagoHoras, usuario: dict = Depends(requiere_empresa)):
    """Cualquier persona puede registrar que 'pagó' horas (se quedó tiempo
    extra, trabajó parte de su comida, etc.) — queda pendiente de que el
    encargado de su sucursal lo autorice antes de que cuente en su saldo."""
    movimiento_id = db.solicitar_pago_horas_empleado(usuario["empresa_id"], usuario["id"], payload.fecha,
                                                       payload.horas, payload.motivo)
    return {"id": movimiento_id}''',
            '''@app.post("/api/rh/horas/solicitar-pago")
def api_solicitar_pago_horas(payload: SolicitudPagoHoras, usuario: dict = Depends(requiere_empresa)):
    """Cualquier persona puede registrar que 'pagó' horas (se quedó tiempo
    extra, trabajó parte de su comida, etc.) — queda pendiente de que el
    encargado de su sucursal lo autorice antes de que cuente en su saldo.
    Solo se puede registrar un pago si esa persona SÍ debe horas, y hasta
    por el monto que debe -- si no, la solicitud se queda atorada
    esperando una firma que nunca va a poder darse (la autorización ya
    bloqueaba esto del otro lado, pero es mejor avisar de una vez)."""
    saldo_actual = db.saldo_horas_usuario(usuario["empresa_id"], usuario["id"])["saldo"]
    if saldo_actual <= 0:
        raise HTTPException(status_code=400, detail="No tienes horas pendientes por pagar — estás al corriente.")
    if payload.horas > saldo_actual:
        raise HTTPException(
            status_code=400,
            detail=f"No puedes registrar más de lo que debes (debes {formatear_horas_legible(saldo_actual)}, intentas registrar {formatear_horas_legible(payload.horas)})",
        )
    movimiento_id = db.solicitar_pago_horas_empleado(usuario["empresa_id"], usuario["id"], payload.fecha,
                                                       payload.horas, payload.motivo)
    return {"id": movimiento_id}''',
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
    print("    git add backend/app.py")
    print('    git commit -m "Horas: no dejar registrar un pago si la persona no debe (o por mas de lo que debe)"')
    print("    git push")


if __name__ == "__main__":
    main()
