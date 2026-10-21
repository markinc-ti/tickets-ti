# -*- coding: utf-8 -*-
"""
RH: "HORAS QUE DEBE TU GENTE" VACIO PARA LA ENCARGADA + SE QUITA "EMBARAZO"
- La encargada que tambien tiene "Datos RH" (y el admin) recibia la lista de
  adeudos vacia en la app; ahora recibe la de todos, con su sucursal.
- "Embarazo" ya no se puede elegir en incidencias nuevas (web y app). Las que
  ya existen lo conservan y se pueden editar.
REQUIERE haber corrido antes fix_horas_permisos_adeudo.py.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_adeudos_encargada.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    \"colegio\", \"comercializadora\", \"hospital\", \"estudiante\", \"estancia_gobierno\", \"otro\",\n]\n\nTIPOS_INCIDENCIA_RH = [\"dia_libre_sin_goce\", \"enfermedad\", \"lesion\", \"embarazo\", \"accidente\", \"otro\"]\nESTADOS_INCIDENCIA_RH = [\"propuesta_empleado\", \"pendiente_encargado\", \"pendiente\", \"aprobada\", \"rechazada\", \"pagada\"]\nESTADOS_VACACION_AJUSTE = [\"pendiente\", \"aprobada\", \"rechazada\"]\nTIPOS_MOVIMIENTO_HORAS_RH = [\"debe\", \"pago\"]\n",
   "    \"colegio\", \"comercializadora\", \"hospital\", \"estudiante\", \"estancia_gobierno\", \"otro\",\n]\n\n# \"embarazo\" se quitó (David, 19 oct 2026): ya no se puede elegir en incidencias\n# nuevas, pero las que ya existen lo conservan y se siguen mostrando.\nTIPOS_INCIDENCIA_RH = [\"dia_libre_sin_goce\", \"enfermedad\", \"lesion\", \"accidente\", \"otro\"]\nTIPOS_INCIDENCIA_RH_RETIRADOS = [\"embarazo\"]\nESTADOS_INCIDENCIA_RH = [\"propuesta_empleado\", \"pendiente_encargado\", \"pendiente\", \"aprobada\", \"rechazada\", \"pagada\"]\nESTADOS_VACACION_AJUSTE = [\"pendiente\", \"aprobada\", \"rechazada\"]\nTIPOS_MOVIMIENTO_HORAS_RH = [\"debe\", \"pago\"]\n"
  ],
  [
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT u.id AS usuario_id, u.nombre_completo, u.puesto,\n               COALESCE(SUM(CASE WHEN m.tipo = 'debe' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS debe_total,\n               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        WHERE u.empresa_id = %s\n        GROUP BY u.id, u.nombre_completo, u.puesto\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id,))\n    rows = [dict(r) for r in cur.fetchall()]\n",
   "    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        SELECT u.id AS usuario_id, u.nombre_completo, u.puesto, s.nombre AS sucursal_nombre,\n               COALESCE(SUM(CASE WHEN m.tipo = 'debe' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS debe_total,\n               COALESCE(SUM(CASE WHEN m.tipo = 'pago' AND m.estado = 'aprobado' THEN m.horas ELSE 0 END), 0) AS pagado_total\n        FROM users u\n        JOIN horas_rh_movimientos m ON m.usuario_id = u.id\n        LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n        WHERE u.empresa_id = %s\n        GROUP BY u.id, u.nombre_completo, u.puesto, s.nombre\n        ORDER BY u.nombre_completo\n    \"\"\", (empresa_id,))\n    rows = [dict(r) for r in cur.fetchall()]\n"
  ]
 ],
 "backend/app.py": [
  [
   "            raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n        if incidencia[\"estado\"] != \"pendiente_encargado\":\n            raise HTTPException(status_code=400, detail=\"Ya no se puede editar — esta incidencia ya pasó a Recursos Humanos\")\n    if payload.tipo and payload.tipo not in db.TIPOS_INCIDENCIA_RH:\n        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    return db.editar_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, payload.tipo, payload.fecha_inicio,\n                                    payload.fecha_fin, payload.motivo, payload.horas)\n",
   "            raise HTTPException(status_code=403, detail=\"Esta incidencia no es de tu sucursal\")\n        if incidencia[\"estado\"] != \"pendiente_encargado\":\n            raise HTTPException(status_code=400, detail=\"Ya no se puede editar — esta incidencia ya pasó a Recursos Humanos\")\n    if payload.tipo and payload.tipo not in db.TIPOS_INCIDENCIA_RH and payload.tipo != incidencia[\"tipo\"]:\n        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    return db.editar_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, payload.tipo, payload.fecha_inicio,\n                                    payload.fecha_fin, payload.motivo, payload.horas)\n"
  ],
  [
   "        incidencias = [i for i in db.listar_incidencias_rh(usuario[\"empresa_id\"])\n                       if i[\"estado\"] in (\"pendiente\", \"pendiente_encargado\") and i[\"usuario_id\"] != yo]\n        horas = [m for m in db.listar_pagos_horas_pendientes_todos(usuario[\"empresa_id\"]) if m[\"usuario_id\"] != yo]\n        saldos = []\n    else:\n        suc = db.obtener_sucursal_id_usuario(yo)\n        incidencias = [i for i in (db.listar_incidencias_pendientes_encargado(usuario[\"empresa_id\"], suc) if suc else [])\n",
   "        incidencias = [i for i in db.listar_incidencias_rh(usuario[\"empresa_id\"])\n                       if i[\"estado\"] in (\"pendiente\", \"pendiente_encargado\") and i[\"usuario_id\"] != yo]\n        horas = [m for m in db.listar_pagos_horas_pendientes_todos(usuario[\"empresa_id\"]) if m[\"usuario_id\"] != yo]\n        # Antes iba vacío: una encargada con \"Datos RH\" (o el admin) veía en la\n        # app \"Nadie de tu sucursal debe horas\" aunque sí le debían.\n        saldos = [s for s in db.listar_saldos_horas_todos(usuario[\"empresa_id\"]) if s[\"usuario_id\"] != yo]\n    else:\n        suc = db.obtener_sucursal_id_usuario(yo)\n        incidencias = [i for i in (db.listar_incidencias_pendientes_encargado(usuario[\"empresa_id\"], suc) if suc else [])\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <h2>Corregir incidencia</h2>\n      <p style=\"font-size:12px; color:var(--muted); margin-bottom:10px;\">De ${escapeHtml(i.usuario_nombre)} — corrige lo que se haya capturado mal antes de firmarla.</p>\n      <div class=\"field\"><label>Tipo</label>\n        <select id=\"ei_tipo\">${META.tipos_incidencia_rh.map(t => `<option value=\"${t}\" ${t===i.tipo?'selected':''}>${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n      </div>\n      <div class=\"row-2\">\n        <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"ei_fecha_inicio\" value=\"${i.fecha_inicio.slice(0,10)}\" /></div>\n",
   "      <h2>Corregir incidencia</h2>\n      <p style=\"font-size:12px; color:var(--muted); margin-bottom:10px;\">De ${escapeHtml(i.usuario_nombre)} — corrige lo que se haya capturado mal antes de firmarla.</p>\n      <div class=\"field\"><label>Tipo</label>\n        <select id=\"ei_tipo\">${(META.tipos_incidencia_rh.includes(i.tipo) ? META.tipos_incidencia_rh : [i.tipo, ...META.tipos_incidencia_rh]).map(t => `<option value=\"${t}\" ${t===i.tipo?'selected':''}>${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n      </div>\n      <div class=\"row-2\">\n        <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"ei_fecha_inicio\" value=\"${i.fecha_inicio.slice(0,10)}\" /></div>\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_adeudos_encargada.py")
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
