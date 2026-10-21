# -*- coding: utf-8 -*-
"""
TRES ERRORES ENCONTRADOS AL GRABAR LOS VIDEOS WEB
- RH: "Registrar incidencia de un empleado" (retroactiva) daba error 500.
  Lo mismo la vista previa del PDF de cotizacion.
- RH: la encargada con "Datos RH" (sin ser admin) veia la lista de incidencias
  pero al abrir una salia "No puedes ver la incidencia de alguien mas".
- Reparaciones: Logistica no podia llenar la firma de entrega al chofer.
REQUIERE haber corrido antes fix_apps_separadas.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_reparaciones_videos.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "        if not mi_sucursal_id or objetivo.get(\"sucursal_id\") != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Solo puedes registrar incidencias de gente de tu sucursal\")\n\n    nota_origen = f\"[Registrada directamente por {usuario['nombre_completo']} — {'RH' if es_rh else 'encargado de sucursal'}, incidencia retroactiva]\"\n    motivo_final = f\"{nota_origen} {payload.motivo}\" if payload.motivo else nota_origen\n    incidencia_id = db.crear_incidencia_rh_directa(\n        usuario[\"empresa_id\"], payload.usuario_id, payload.tipo, payload.fecha_inicio,\n",
   "        if not mi_sucursal_id or objetivo.get(\"sucursal_id\") != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Solo puedes registrar incidencias de gente de tu sucursal\")\n\n    nota_origen = f\"[Registrada directamente por {usuario.get('nombre') or usuario.get('nombre_completo') or usuario.get('username')} — {'RH' if es_rh else 'encargado de sucursal'}, incidencia retroactiva]\"\n    motivo_final = f\"{nota_origen} {payload.motivo}\" if payload.motivo else nota_origen\n    incidencia_id = db.crear_incidencia_rh_directa(\n        usuario[\"empresa_id\"], payload.usuario_id, payload.tipo, payload.fecha_inicio,\n"
  ],
  [
   "    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if usuario[\"rol\"] == \"admin\" or incidencia[\"usuario_id\"] == usuario[\"id\"]:\n        return incidencia\n    if usuario[\"rol\"] == \"encargado_sucursal\":\n        # También puede ver (para revisarla antes de firmar) cualquier\n",
   "    if not incidencia:\n        raise HTTPException(status_code=404, detail=\"Incidencia no encontrada\")\n    if usuario[\"rol\"] == \"admin\" or incidencia[\"usuario_id\"] == usuario[\"id\"]:\n        return incidencia\n    # La encargada de RH (\"Datos RH\") ve la lista de todas, así que también\n    # tiene que poder abrir el detalle para aprobar o rechazar.\n    if _con_permisos(usuario).get(\"acceso_datos_empleado_rh\", False):\n        return incidencia\n    if usuario[\"rol\"] == \"encargado_sucursal\":\n        # También puede ver (para revisarla antes de firmar) cualquier\n"
  ],
  [
   "            ],\n            \"notas\": \"Estas son notas de ejemplo para la vista previa.\",\n            \"vigencia_hasta\": None, \"meses_msi\": 6,\n            \"creado_por_nombre\": usuario[\"nombre_completo\"], \"creador_telefono\": None,\n            \"creador_sucursal_nombre\": None, \"creador_sucursal_telefonos\": None,\n        }\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, payload.config)\n",
   "            ],\n            \"notas\": \"Estas son notas de ejemplo para la vista previa.\",\n            \"vigencia_hasta\": None, \"meses_msi\": 6,\n            \"creado_por_nombre\": usuario.get(\"nombre\") or usuario.get(\"nombre_completo\"), \"creador_telefono\": None,\n            \"creador_sucursal_nombre\": None, \"creador_sucursal_telefonos\": None,\n        }\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, payload.config)\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    `;\n  }\n  if (soloLectura && !(tab === 'entrega' && (puedeEntregar || puedeFirmarIngreso))) bloquearFormularioSoloLectura('repDetalleContenido');\n}\n\nasync function refrescarDetalleRep(id, tab) {\n",
   "    `;\n  }\n  if (soloLectura && !(tab === 'entrega' && (puedeEntregar || puedeFirmarIngreso))) bloquearFormularioSoloLectura('repDetalleContenido');\n  if (soloLectura && tab === 'entrega' && puedeFirmarChofer) {\n    // Logística (solo lectura en lo demás) sí firma la entrega al chofer: se reactiva SOLO ese bloque.\n    const bloqueChofer = document.getElementById('ed_chofer_nombre') && document.getElementById('ed_chofer_nombre').closest('.comentarios');\n    if (bloqueChofer) {\n      bloqueChofer.querySelectorAll('input, textarea, select').forEach(el => el.disabled = false);\n      bloqueChofer.querySelectorAll('button').forEach(el => el.style.display = '');\n    }\n  }\n}\n\nasync function refrescarDetalleRep(id, tab) {\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_reparaciones_videos.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "db.app_movil_empresa(" not in f.read():
            print("Primero corre fix_apps_separadas.py (y los anteriores), y luego este.")
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
