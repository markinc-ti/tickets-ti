# -*- coding: utf-8 -*-
"""
RH: la encargada de sucursal tambien ve las horas que debe el personal de
ALMACEN de su sucursal (antes la lista los dejaba fuera).
Toca: backend/db.py
Se puede correr varias veces.  Correr con:  py -3 fix_rh_adeudos_almacen.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        LEFT JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        WHERE u.empresa_id = %s AND u.sucursal_id = %s AND u.activo = TRUE AND u.rol NOT IN ('encargado_sucursal', 'almacen', 'master', 'estudiante')\n        GROUP BY u.id, u.nombre_completo, u.puesto\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id, sucursal_id))\n",
   "               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        LEFT JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        -- El de almacén SÍ cuenta (sus permisos también los firma la encargada).\n        WHERE u.empresa_id = %s AND u.sucursal_id = %s AND u.activo = TRUE AND u.rol NOT IN ('encargado_sucursal', 'master', 'estudiante')\n        GROUP BY u.id, u.nombre_completo, u.puesto\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id, sucursal_id))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_adeudos_almacen.py")
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
