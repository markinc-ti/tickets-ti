# -*- coding: utf-8 -*-
"""
RH: NUEVO TIPO DE INCIDENCIA "PERMISO POR HORAS" (y es el que sale por defecto)
- Es el primero de la lista, asi que sale elegido al crear una incidencia
  (web y app) y deja marcada la casilla "por horas". Pide las horas/minutos.
- Al elegir otro tipo, la casilla de horas se quita sola.
Toca: backend/db.py, backend/app.py, backend/direccion.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_permiso_horas.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "\n# \"embarazo\" se quitó (David, 19 oct 2026): ya no se puede elegir en incidencias\n# nuevas, pero las que ya existen lo conservan y se siguen mostrando.\nTIPOS_INCIDENCIA_RH = [\"dia_libre_sin_goce\", \"enfermedad\", \"lesion\", \"accidente\", \"otro\"]\nTIPOS_INCIDENCIA_RH_RETIRADOS = [\"embarazo\"]\nESTADOS_INCIDENCIA_RH = [\"propuesta_empleado\", \"pendiente_encargado\", \"pendiente\", \"aprobada\", \"rechazada\", \"pagada\"]\nESTADOS_VACACION_AJUSTE = [\"pendiente\", \"aprobada\", \"rechazada\"]\n",
   "\n# \"embarazo\" se quitó (David, 19 oct 2026): ya no se puede elegir en incidencias\n# nuevas, pero las que ya existen lo conservan y se siguen mostrando.\n# \"permiso_horas\" (David, 21 oct 2026) va primero: es el que sale elegido por defecto.\nTIPOS_INCIDENCIA_RH = [\"permiso_horas\", \"dia_libre_sin_goce\", \"enfermedad\", \"lesion\", \"accidente\", \"otro\"]\nTIPOS_INCIDENCIA_RH_RETIRADOS = [\"embarazo\"]\nESTADOS_INCIDENCIA_RH = [\"propuesta_empleado\", \"pendiente_encargado\", \"pendiente\", \"aprobada\", \"rechazada\", \"pagada\"]\nESTADOS_VACACION_AJUSTE = [\"pendiente\", \"aprobada\", \"rechazada\"]\n"
  ]
 ],
 "backend/app.py": [
  [
   "        raise HTTPException(status_code=400, detail=\"La foto pesa demasiado (máximo 5MB)\")\n    if payload.horas is not None and payload.horas <= 0:\n        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n",
   "        raise HTTPException(status_code=400, detail=\"La foto pesa demasiado (máximo 5MB)\")\n    if payload.horas is not None and payload.horas <= 0:\n        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n"
  ],
  [
   "        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    if payload.horas is not None and payload.horas <= 0:\n        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n\n    objetivo = next((u for u in db.listar_usuarios(usuario[\"empresa_id\"]) if u[\"id\"] == payload.usuario_id), None)\n    if not objetivo:\n",
   "        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    if payload.horas is not None and payload.horas <= 0:\n        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n\n    objetivo = next((u for u in db.listar_usuarios(usuario[\"empresa_id\"]) if u[\"id\"] == payload.usuario_id), None)\n    if not objetivo:\n"
  ],
  [
   "\n\nNOMBRES_TIPO_INCIDENCIA_RH_PDF = {\n    \"dia_libre_sin_goce\": \"Día libre sin goce de sueldo\", \"enfermedad\": \"Falta por enfermedad\",\n    \"lesion\": \"Lesión\", \"embarazo\": \"Embarazo\", \"accidente\": \"Accidente\", \"otro\": \"Otro\",\n}\nNOMBRES_ESTADO_INCIDENCIA_RH_PDF = {\"pendiente\": \"Pendiente\", \"aprobada\": \"Aprobada\", \"rechazada\": \"Rechazada\"}\n",
   "\n\nNOMBRES_TIPO_INCIDENCIA_RH_PDF = {\n    \"permiso_horas\": \"Permiso por horas\", \"dia_libre_sin_goce\": \"Día libre sin goce de sueldo\", \"enfermedad\": \"Falta por enfermedad\",\n    \"lesion\": \"Lesión\", \"embarazo\": \"Embarazo\", \"accidente\": \"Accidente\", \"otro\": \"Otro\",\n}\nNOMBRES_ESTADO_INCIDENCIA_RH_PDF = {\"pendiente\": \"Pendiente\", \"aprobada\": \"Aprobada\", \"rechazada\": \"Rechazada\"}\n"
  ]
 ],
 "backend/direccion.py": [
  [
   "}\nNOMBRES_SOPORTE = {\"orden_pendiente_firma\": \"Falta firma del cliente\", \"diagnostico\": \"En diagnóstico\",\n                   \"resolucion_enviada\": \"Resolución enviada\", \"enviado\": \"Enviado al cliente\"}\nNOMBRES_INCIDENCIA = {\"dia_libre_sin_goce\": \"Día libre sin goce\", \"enfermedad\": \"Enfermedad\", \"lesion\": \"Lesión\",\n                      \"embarazo\": \"Embarazo\", \"accidente\": \"Accidente\", \"otro\": \"Permiso\"}\nNOMBRES_ESTADO_INCIDENCIA = {\"propuesta_empleado\": \"Por confirmar\", \"pendiente_encargado\": \"Con la encargada\",\n                             \"pendiente\": \"Por aprobar\", \"aprobada\": \"Aprobada\", \"pagada\": \"Pagada\"}\n",
   "}\nNOMBRES_SOPORTE = {\"orden_pendiente_firma\": \"Falta firma del cliente\", \"diagnostico\": \"En diagnóstico\",\n                   \"resolucion_enviada\": \"Resolución enviada\", \"enviado\": \"Enviado al cliente\"}\nNOMBRES_INCIDENCIA = {\"permiso_horas\": \"Permiso por horas\", \"dia_libre_sin_goce\": \"Día libre sin goce\", \"enfermedad\": \"Enfermedad\", \"lesion\": \"Lesión\",\n                      \"embarazo\": \"Embarazo\", \"accidente\": \"Accidente\", \"otro\": \"Permiso\"}\nNOMBRES_ESTADO_INCIDENCIA = {\"propuesta_empleado\": \"Por confirmar\", \"pendiente_encargado\": \"Con la encargada\",\n                             \"pendiente\": \"Por aprobar\", \"aprobada\": \"Aprobada\", \"pagada\": \"Pagada\"}\n"
  ]
 ],
 "frontend/index.html": [
  [
   "// ---- Recursos Humanos (incidencias) ----\n\nconst NOMBRES_TIPO_INCIDENCIA_RH = {\n  dia_libre_sin_goce: 'Día libre sin goce de sueldo', enfermedad: 'Falta por enfermedad',\n  lesion: 'Lesión', embarazo: 'Embarazo', accidente: 'Accidente', otro: 'Otro',\n};\nconst NOMBRES_ESTADO_INCIDENCIA_RH = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada', pagada: 'Pagada' };\n",
   "// ---- Recursos Humanos (incidencias) ----\n\nconst NOMBRES_TIPO_INCIDENCIA_RH = {\n  permiso_horas: 'Permiso por horas', dia_libre_sin_goce: 'Día libre sin goce de sueldo', enfermedad: 'Falta por enfermedad',\n  lesion: 'Lesión', embarazo: 'Embarazo', accidente: 'Accidente', otro: 'Otro',\n};\nconst NOMBRES_ESTADO_INCIDENCIA_RH = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada', pagada: 'Pagada' };\n"
  ],
  [
   "    </p>\n    <div class=\"field\"><label>Empleado</label><select id=\"rhd_usuario\">${opcionesEmpleados}</select></div>\n    <div class=\"field\"><label>Tipo</label>\n      <select id=\"rhd_tipo\">${META.tipos_incidencia_rh.map(t => `<option value=\"${t}\">${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"rhd_fecha_inicio\" /></div>\n      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rhd_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rhd_es_por_horas\" onchange=\"document.getElementById('rhd_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rhd_horas_wrap\" style=\"display:none;\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n        <div class=\"field\" style=\"margin-bottom:0;\"><label style=\"font-size:10px;\">Horas</label><input type=\"number\" id=\"rhd_horas\" min=\"0\" step=\"1\" placeholder=\"0\" value=\"0\" /></div>\n",
   "    </p>\n    <div class=\"field\"><label>Empleado</label><select id=\"rhd_usuario\">${opcionesEmpleados}</select></div>\n    <div class=\"field\"><label>Tipo</label>\n      <select id=\"rhd_tipo\" onchange=\"tipoIncidenciaPorHoras('rhd')\">${META.tipos_incidencia_rh.map(t => `<option value=\"${t}\">${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"rhd_fecha_inicio\" /></div>\n      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rhd_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rhd_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked' : ''} onchange=\"document.getElementById('rhd_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rhd_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n        <div class=\"field\" style=\"margin-bottom:0;\"><label style=\"font-size:10px;\">Horas</label><input type=\"number\" id=\"rhd_horas\" min=\"0\" step=\"1\" placeholder=\"0\" value=\"0\" /></div>\n"
  ],
  [
   "  });\n}\n\nfunction abrirCrearIncidenciaRH() {  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Nueva incidencia</h2>\n    <div class=\"field\"><label>Tipo</label>\n      <select id=\"rh_tipo\">${META.tipos_incidencia_rh.map(t => `<option value=\"${t}\">${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"rh_fecha_inicio\" /></div>\n      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rh_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rh_es_por_horas\" onchange=\"document.getElementById('rh_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rh_horas_wrap\" style=\"display:none;\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n        <div class=\"field\" style=\"margin-bottom:0;\"><label style=\"font-size:10px;\">Horas</label><input type=\"number\" id=\"rh_horas\" min=\"0\" step=\"1\" placeholder=\"0\" value=\"0\" /></div>\n",
   "  });\n}\n\n// \"Permiso por horas\" deja marcada la casilla de horas; los demás tipos la quitan.\nfunction tipoIncidenciaPorHoras(p) {\n  const porHoras = document.getElementById(p + '_tipo').value === 'permiso_horas';\n  const caja = document.getElementById(p + '_es_por_horas');\n  if (!caja) return;\n  caja.checked = porHoras;\n  document.getElementById(p + '_horas_wrap').style.display = porHoras ? 'block' : 'none';\n}\n\nfunction abrirCrearIncidenciaRH() {  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Nueva incidencia</h2>\n    <div class=\"field\"><label>Tipo</label>\n      <select id=\"rh_tipo\" onchange=\"tipoIncidenciaPorHoras('rh')\">${META.tipos_incidencia_rh.map(t => `<option value=\"${t}\">${NOMBRES_TIPO_INCIDENCIA_RH[t]}</option>`).join('')}</select>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Fecha de inicio</label><input type=\"date\" id=\"rh_fecha_inicio\" /></div>\n      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rh_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rh_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked' : ''} onchange=\"document.getElementById('rh_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rh_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n        <div class=\"field\" style=\"margin-bottom:0;\"><label style=\"font-size:10px;\">Horas</label><input type=\"number\" id=\"rh_horas\" min=\"0\" step=\"1\" placeholder=\"0\" value=\"0\" /></div>\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_permiso_horas.py")
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
