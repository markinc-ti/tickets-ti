# -*- coding: utf-8 -*-
"""
RH (Mark Inc y todas) -- "Por autorizar" en la app.
- Nuevo GET /api/rh/por-autorizar: la encargada de sucursal ve los permisos y pagos
  de horas de su gente; RH / administrador ve los de todos (tambien los de las
  encargadas y de quien no tiene encargada).
- Autorizar / rechazar pagos de horas ahora lo puede hacer tambien RH / admin
  (antes solo la encargada de la sucursal).
- Nadie se autoriza a si misma (lo suyo lo autoriza RH).
REQUIERE haber corrido antes fix_soporte_tecnico_peymar.py.
Toca: backend/app.py, backend/db.py
Se puede correr varias veces.  Correr con:  py -3 fix_rh_autorizar_app.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    para que la vuelva a aprobar (RH solo la ve informativamente después).\"\"\"\n    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n",
   "    para que la vuelva a aprobar (RH solo la ve informativamente después).\"\"\"\n    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if incidencia[\"usuario_id\"] == usuario[\"id\"]:\n        raise HTTPException(status_code=403, detail=\"No puedes autorizarte a ti misma: lo autoriza RH.\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n"
  ],
  [
   "    A diferencia de aceptar, no pide firma.\"\"\"\n    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n",
   "    A diferencia de aceptar, no pide firma.\"\"\"\n    incidencia = db.obtener_incidencia_rh(usuario[\"empresa_id\"], incidencia_id)\n    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if incidencia[\"usuario_id\"] == usuario[\"id\"]:\n        raise HTTPException(status_code=403, detail=\"No puedes autorizarte a ti misma: lo autoriza RH.\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n"
  ],
  [
   "    return {\"id\": movimiento_id}\n\n\nclass FirmaAprobacionHoras(BaseModel):\n    firma_base64: str = Field(min_length=100)\n\n\n@app.post(\"/api/rh/horas/movimientos/{movimiento_id}/aprobar\")\ndef api_aprobar_pago_horas(movimiento_id: int, payload: FirmaAprobacionHoras, usuario: dict = Depends(requiere_encargado_sucursal)):\n    movimiento = db.obtener_movimiento_horas_rh(usuario[\"empresa_id\"], movimiento_id)\n    if not movimiento:\n        raise HTTPException(status_code=404, detail=\"Movimiento no encontrado\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(movimiento[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta persona no es de tu sucursal\")\n    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"La firma pesa demasiado\")\n    if movimiento[\"tipo\"] == \"pago\":\n",
   "    return {\"id\": movimiento_id}\n\n\ndef _tipo_autorizador_rh(usuario):\n    \"\"\"'rh' = administrador con RH o quien tiene \"Datos RH\" (autoriza a todos);\n    'encargado' = encargada de sucursal (autoriza a su gente); None = nadie.\"\"\"\n    u = _con_permisos(usuario)\n    if (u[\"rol\"] == \"admin\" and u.get(\"acceso_rh\", True)) or u.get(\"acceso_datos_empleado_rh\", False):\n        return \"rh\"\n    if u[\"rol\"] == \"encargado_sucursal\":\n        return \"encargado\"\n    return None\n\n\ndef _puede_autorizar_de(usuario, usuario_id_persona):\n    if usuario_id_persona == usuario[\"id\"] and usuario[\"rol\"] != \"admin\":\n        raise HTTPException(status_code=403, detail=\"No puedes autorizarte a ti misma: lo autoriza RH.\")\n    tipo = _tipo_autorizador_rh(usuario)\n    if tipo == \"rh\":\n        return\n    if tipo == \"encargado\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if mi_sucursal_id and db.obtener_sucursal_id_usuario(usuario_id_persona) == mi_sucursal_id:\n            return\n        raise HTTPException(status_code=403, detail=\"Esta persona no es de tu sucursal\")\n    raise HTTPException(status_code=403, detail=\"No tienes permiso para autorizar esto\")\n\n\n@app.get(\"/api/rh/por-autorizar\")\ndef api_rh_por_autorizar(usuario: dict = Depends(requiere_empresa)):\n    \"\"\"Para la app: permisos (incidencias) y pagos de horas que esta persona puede\n    autorizar. Encargada: los de su sucursal. RH / administrador: todos.\"\"\"\n    tipo = _tipo_autorizador_rh(usuario)\n    if not tipo:\n        return {\"rol\": None, \"incidencias\": [], \"horas\": [], \"saldos\": []}\n    yo = usuario[\"id\"]\n    if tipo == \"rh\":\n        incidencias = [i for i in db.listar_incidencias_rh(usuario[\"empresa_id\"])\n                       if i[\"estado\"] in (\"pendiente\", \"pendiente_encargado\") and i[\"usuario_id\"] != yo]\n        horas = [m for m in db.listar_pagos_horas_pendientes_todos(usuario[\"empresa_id\"]) if m[\"usuario_id\"] != yo]\n        saldos = []\n    else:\n        suc = db.obtener_sucursal_id_usuario(yo)\n        incidencias = [i for i in (db.listar_incidencias_pendientes_encargado(usuario[\"empresa_id\"], suc) if suc else [])\n                       if i[\"usuario_id\"] != yo]\n        horas = [m for m in (db.listar_pagos_horas_pendientes_encargado(usuario[\"empresa_id\"], suc) if suc else [])\n                 if m[\"usuario_id\"] != yo]\n        saldos = db.listar_saldos_horas_sucursal(usuario[\"empresa_id\"], suc) if suc else []\n    for m in horas:\n        m.pop(\"firma_aprobacion_base64\", None)\n        try:\n            m[\"saldo_actual\"] = db.saldo_horas_usuario(usuario[\"empresa_id\"], m[\"usuario_id\"])[\"saldo\"]\n        except Exception:\n            m[\"saldo_actual\"] = None\n    return {\"rol\": tipo, \"incidencias\": incidencias, \"horas\": horas, \"saldos\": saldos}\n\n\nclass FirmaAprobacionHoras(BaseModel):\n    firma_base64: str = Field(min_length=100)\n\n\n@app.post(\"/api/rh/horas/movimientos/{movimiento_id}/aprobar\")\ndef api_aprobar_pago_horas(movimiento_id: int, payload: FirmaAprobacionHoras, usuario: dict = Depends(requiere_empresa)):\n    movimiento = db.obtener_movimiento_horas_rh(usuario[\"empresa_id\"], movimiento_id)\n    if not movimiento:\n        raise HTTPException(status_code=404, detail=\"Movimiento no encontrado\")\n    _puede_autorizar_de(usuario, movimiento[\"usuario_id\"])\n    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:\n        raise HTTPException(status_code=400, detail=\"La firma pesa demasiado\")\n    if movimiento[\"tipo\"] == \"pago\":\n"
  ],
  [
   "\n\n@app.post(\"/api/rh/horas/movimientos/{movimiento_id}/rechazar\")\ndef api_rechazar_pago_horas(movimiento_id: int, payload: RechazoPagoHoras, usuario: dict = Depends(requiere_encargado_sucursal)):\n    movimiento = db.obtener_movimiento_horas_rh(usuario[\"empresa_id\"], movimiento_id)\n    if not movimiento:\n        raise HTTPException(status_code=404, detail=\"Movimiento no encontrado\")\n    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(movimiento[\"usuario_id\"])\n    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:\n        raise HTTPException(status_code=403, detail=\"Esta persona no es de tu sucursal\")\n    if not db.rechazar_pago_horas(usuario[\"empresa_id\"], movimiento_id, usuario[\"id\"], payload.motivo):\n        raise HTTPException(status_code=400, detail=\"Este pago ya no está pendiente de tu firma\")\n    avisos.avisar_seguro([movimiento[\"usuario_id\"]], \"❌ Tus horas fueron RECHAZADAS\",\n",
   "\n\n@app.post(\"/api/rh/horas/movimientos/{movimiento_id}/rechazar\")\ndef api_rechazar_pago_horas(movimiento_id: int, payload: RechazoPagoHoras, usuario: dict = Depends(requiere_empresa)):\n    movimiento = db.obtener_movimiento_horas_rh(usuario[\"empresa_id\"], movimiento_id)\n    if not movimiento:\n        raise HTTPException(status_code=404, detail=\"Movimiento no encontrado\")\n    _puede_autorizar_de(usuario, movimiento[\"usuario_id\"])\n    if not db.rechazar_pago_horas(usuario[\"empresa_id\"], movimiento_id, usuario[\"id\"], payload.motivo):\n        raise HTTPException(status_code=400, detail=\"Este pago ya no está pendiente de tu firma\")\n    avisos.avisar_seguro([movimiento[\"usuario_id\"]], \"❌ Tus horas fueron RECHAZADAS\",\n"
  ]
 ],
 "backend/db.py": [
  [
   "    return rows\n\n\ndef aprobar_pago_horas(empresa_id, movimiento_id, encargado_id, firma_base64):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return rows\n\n\ndef listar_pagos_horas_pendientes_todos(empresa_id):\n    \"\"\"Para RH / el administrador: todos los pagos de horas esperando autorización\n    (también los de las propias encargadas y de quien no tiene encargada).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT m.*, u.nombre_completo AS usuario_nombre, u.puesto AS usuario_puesto, s.nombre AS sucursal_nombre\n        FROM horas_rh_movimientos m\n        JOIN users u ON u.id = m.usuario_id\n        LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n        WHERE m.empresa_id = %s AND m.estado = 'pendiente' AND m.tipo = 'pago'\n        ORDER BY m.creado_en ASC\n    \"\"\", (empresa_id,))\n    rows = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    return rows\n\n\ndef aprobar_pago_horas(empresa_id, movimiento_id, encargado_id, firma_base64):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_autorizar_app.py")
        sys.exit(1)
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "soporte_reportes" not in f.read():
            print("Primero corre fix_soporte_tecnico_peymar.py (y los anteriores), y luego este.")
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
