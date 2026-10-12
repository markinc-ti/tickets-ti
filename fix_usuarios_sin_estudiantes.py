# -*- coding: utf-8 -*-
"""
Usuarios del sistema sin los estudiantes del laboratorio:
  - Administrar → Usuarios ya no muestra a los estudiantes registrados desde
    la app Mark·Inc Lab (rol estudiante). Ellos se ven y administran solo en
    Administrar → Portal de estudiantes.
  - Tampoco salen al elegir participantes de proyectos, en el estatus de
    capacitación ni en el saldo de horas por sucursal.
Toca: backend/db.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n           FROM users u\n           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n           WHERE u.empresa_id = %s ORDER BY u.nombre_completo\"\"\",\n        (empresa_id,),\n    )\n    rows = [dict(r) for r in cur.fetchall()]\n",
   "                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n           FROM users u\n           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n           WHERE u.empresa_id = %s AND u.rol IS DISTINCT FROM 'estudiante'\n           ORDER BY u.nombre_completo\"\"\",\n        (empresa_id,),\n    )\n    rows = [dict(r) for r in cur.fetchall()]\n"
  ],
  [
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"SELECT id, nombre_completo, rol, puesto, numero_empleado, sucursal_id FROM users WHERE empresa_id = %s AND activo = TRUE ORDER BY nombre_completo\",\n        (empresa_id,),\n    )\n    rows = [dict(r) for r in cur.fetchall()]\n",
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"SELECT id, nombre_completo, rol, puesto, numero_empleado, sucursal_id FROM users \"\n        \"WHERE empresa_id = %s AND activo = TRUE AND rol IS DISTINCT FROM 'estudiante' ORDER BY nombre_completo\",\n        (empresa_id,),\n    )\n    rows = [dict(r) for r in cur.fetchall()]\n"
  ],
  [
   "    cur.execute(\n        \"\"\"SELECT u.id, u.nombre_completo, u.rol, u.sucursal_id, s.departamento\n           FROM users u LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n           WHERE u.empresa_id = %s AND u.activo = TRUE ORDER BY u.nombre_completo\"\"\",\n        (empresa_id,),\n    )\n    usuarios = [dict(r) for r in cur.fetchall()]\n",
   "    cur.execute(\n        \"\"\"SELECT u.id, u.nombre_completo, u.rol, u.sucursal_id, s.departamento\n           FROM users u LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n           WHERE u.empresa_id = %s AND u.activo = TRUE AND u.rol IS DISTINCT FROM 'estudiante'\n           ORDER BY u.nombre_completo\"\"\",\n        (empresa_id,),\n    )\n    usuarios = [dict(r) for r in cur.fetchall()]\n"
  ],
  [
   "               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        LEFT JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        WHERE u.empresa_id = %s AND u.sucursal_id = %s AND u.activo = TRUE AND u.rol NOT IN ('encargado_sucursal', 'almacen', 'master')\n        GROUP BY u.id, u.nombre_completo, u.puesto\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id, sucursal_id))\n",
   "               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        LEFT JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        WHERE u.empresa_id = %s AND u.sucursal_id = %s AND u.activo = TRUE AND u.rol NOT IN ('encargado_sucursal', 'almacen', 'master', 'estudiante')\n        GROUP BY u.id, u.nombre_completo, u.puesto\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id, sucursal_id))\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
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
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
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
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
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
