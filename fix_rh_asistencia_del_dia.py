# -*- coding: utf-8 -*-
"""
RH: ASISTENCIA DEL DIA PARA LA APP (servidor)
- GET /api/rh/asistencia/del-dia?dia=hoy|ayer : lo mismo que ve el director
  (retardos, quien no ha checado, faltas, sin conexion). Solo con "Datos RH".
REQUIERE haber corrido antes fix_checadores_sin_conexion.py.
Toca: backend/app.py, backend/direccion.py
Se puede correr varias veces.  Correr con:  py -3 fix_rh_asistencia_del_dia.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "            raise HTTPException(status_code=400, detail=\"Día inválido, usa hoy, ayer o AAAA-MM-DD\")\n    modulos = db.obtener_modulos_empresa(usuario[\"empresa_id\"])\n    return direccion.resumen(usuario[\"empresa_id\"], modulos, d, _reporte_asistencia)\n\n\ndef _microsip_direccion(usuario: dict):\n",
   "            raise HTTPException(status_code=400, detail=\"Día inválido, usa hoy, ayer o AAAA-MM-DD\")\n    modulos = db.obtener_modulos_empresa(usuario[\"empresa_id\"])\n    return direccion.resumen(usuario[\"empresa_id\"], modulos, d, _reporte_asistencia)\n\n\n@app.get(\"/api/rh/asistencia/del-dia\")\ndef api_asistencia_del_dia_rh(dia: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Para RH en la app: lo mismo que ve el director en Dirección → Asistencia\n    (quién llegó tarde, quién no ha checado, faltas con y sin permiso,\n    checadores sin conexión). dia: 'hoy' (default), 'ayer' o AAAA-MM-DD.\"\"\"\n    hoy = db.ahora().date()\n    if not dia or dia == \"hoy\":\n        d = hoy\n    elif dia == \"ayer\":\n        d = hoy - timedelta(days=1)\n    else:\n        try:\n            d = date.fromisoformat(dia)\n        except ValueError:\n            raise HTTPException(status_code=400, detail=\"Día inválido, usa hoy, ayer o AAAA-MM-DD\")\n    return {\"fecha\": d.isoformat(), \"generado\": db.ahora().strftime(\"%Y-%m-%d %H:%M\"),\n            \"rh\": direccion.bloque_asistencia(usuario[\"empresa_id\"], d, _reporte_asistencia)}\n\n\ndef _microsip_direccion(usuario: dict):\n"
  ]
 ],
 "backend/direccion.py": [
  [
   "                       for k in rep.get(\"conexion_checadores\") or []],\n        \"permisos\": permisos, \"avisos\": rep.get(\"avisos\") or [],\n    }\n\n\ndef _paso_reparacion(estado):\n",
   "                       for k in rep.get(\"conexion_checadores\") or []],\n        \"permisos\": permisos, \"avisos\": rep.get(\"avisos\") or [],\n    }\n\n\ndef bloque_asistencia(empresa_id, dia: date, reporte_asistencia) -> dict:\n    \"\"\"El bloque de asistencia del día solo (RH lo ve en su app).\"\"\"\n    return _bloque_rh(empresa_id, dia, db.ahora().date(), reporte_asistencia)\n\n\ndef _paso_reparacion(estado):\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_asistencia_del_dia.py")
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
            if nuevo in texto:
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
