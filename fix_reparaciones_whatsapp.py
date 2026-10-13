# -*- coding: utf-8 -*-
"""
Reparaciones por WhatsApp Business (Meta), con el PDF adjunto, igual que las
cotizaciones: POST /api/reparaciones/{id}/whatsapp {"tipo": "orden" |
"diagnostico"}. Usa las plantillas de Meta "orden_servicio_cliente" y
"diagnostico_cliente" (encabezado Documento) o las que digan las variables
WHATSAPP_META_PLANTILLA_ORDEN / WHATSAPP_META_PLANTILLA_DIAGNOSTICO.
REQUIERE haber corrido antes fix_reparaciones_flujo_areas.py.
Toca: backend/app.py, backend/whatsapp_meta.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "                     headers={\"Content-Disposition\": f\"attachment; filename=orden_servicio_{reparacion['folio']}.pdf\"})\n\n\n@app.get(\"/api/reparaciones/{reparacion_id}/diagnostico.pdf\")\ndef api_pdf_diagnostico(reparacion_id: int, usuario: dict = Depends(requiere_empresa)):\n    reparacion = db.obtener_reparacion(usuario[\"empresa_id\"], reparacion_id)\n",
   "                     headers={\"Content-Disposition\": f\"attachment; filename=orden_servicio_{reparacion['folio']}.pdf\"})\n\n\nclass WhatsappReparacionIn(BaseModel):\n    tipo: Literal[\"orden\", \"diagnostico\"] = \"orden\"\n\n\n@app.post(\"/api/reparaciones/{reparacion_id}/whatsapp\")\ndef api_reparacion_whatsapp(reparacion_id: int, payload: WhatsappReparacionIn, usuario: dict = Depends(requiere_ver_reparaciones)):\n    \"\"\"Le manda al cliente, por WhatsApp Business (Meta), la orden de servicio\n    o el diagnóstico con el PDF adjunto (igual que las cotizaciones).\"\"\"\n    empresa_id = usuario[\"empresa_id\"]\n    reparacion = db.obtener_reparacion(empresa_id, reparacion_id)\n    if not reparacion:\n        raise HTTPException(status_code=404, detail=\"Reparación no encontrada\")\n    if usuario[\"rol\"] == \"usuario\" and reparacion[\"creado_por_id\"] != usuario[\"id\"] and not _es_departamento_logistica(usuario[\"id\"]):\n        raise HTTPException(status_code=403, detail=\"No puedes ver esta reparación\")\n    if not whatsapp_meta.configurado():\n        raise HTTPException(status_code=400, detail=\"WhatsApp Business (Meta) todavía no está configurado en el servidor.\")\n    telefono = (reparacion.get(\"cliente_telefono\") or \"\").strip()\n    if not whatsapp_meta.normalizar_telefono(telefono):\n        raise HTTPException(status_code=400, detail=\"La reparación no tiene un teléfono válido del cliente (10 dígitos).\")\n    if payload.tipo == \"diagnostico\" and not (reparacion.get(\"diagnostico\") or \"\").strip():\n        raise HTTPException(status_code=400, detail=\"Todavía no hay diagnóstico.\")\n    empresa = db.obtener_empresa(empresa_id) or {}\n    equipo = \" \".join(x for x in [reparacion.get(\"equipo\"), reparacion.get(\"marca\"), reparacion.get(\"modelo\")] if x) or \"equipo\"\n    if payload.tipo == \"diagnostico\":\n        pdf_bytes = pdfs_reparaciones.generar_diagnostico(reparacion, empresa)\n        nombre = f\"Diagnostico_{reparacion['folio']}.pdf\"\n        params = [reparacion[\"cliente_nombre\"], equipo, reparacion[\"folio\"], f\"${float(reparacion.get('costo_total') or 0):,.2f}\"]\n    else:\n        pdf_bytes = pdfs_reparaciones.generar_orden_servicio(reparacion, empresa)\n        nombre = f\"Orden_servicio_{reparacion['folio']}.pdf\"\n        params = [reparacion[\"cliente_nombre\"], equipo, reparacion[\"folio\"]]\n    try:\n        wamid = whatsapp_meta.enviar_documento_reparacion(payload.tipo, telefono, params, pdf_bytes, nombre)\n    except whatsapp_meta.ErrorWhatsApp as e:\n        db.registrar_envio_whatsapp(empresa_id, f\"reparacion_{payload.tipo}\", telefono, \"error\", usuario[\"id\"], error=str(e))\n        return {\"ok\": False, \"error\": str(e)}\n    db.registrar_envio_whatsapp(empresa_id, f\"reparacion_{payload.tipo}\", telefono, \"sent\", usuario[\"id\"], wamid=wamid)\n    db.agregar_actualizacion_reparacion(\n        reparacion_id, usuario[\"id\"],\n        f\"Se le mandó al cliente por WhatsApp {'el diagnóstico' if payload.tipo == 'diagnostico' else 'la orden de servicio'} (PDF).\",\n    )\n    return {\"ok\": True, \"error\": None}\n\n\n@app.get(\"/api/reparaciones/{reparacion_id}/diagnostico.pdf\")\ndef api_pdf_diagnostico(reparacion_id: int, usuario: dict = Depends(requiere_empresa)):\n    reparacion = db.obtener_reparacion(usuario[\"empresa_id\"], reparacion_id)\n"
  ]
 ],
 "backend/whatsapp_meta.py": [
  [
   "        \"phone_id\": os.getenv(\"WHATSAPP_META_PHONE_NUMBER_ID\", \"\").strip(),\n        \"pl_bienvenida\": os.getenv(\"WHATSAPP_META_PLANTILLA_BIENVENIDA\", \"\").strip() or \"bienvenida_cliente\",\n        \"pl_cotizacion\": os.getenv(\"WHATSAPP_META_PLANTILLA_COTIZACION\", \"\").strip() or \"cotizacion_cliente\",\n        \"idioma\": os.getenv(\"WHATSAPP_META_IDIOMA\", \"\").strip() or \"es_MX\",\n    }\n\n",
   "        \"phone_id\": os.getenv(\"WHATSAPP_META_PHONE_NUMBER_ID\", \"\").strip(),\n        \"pl_bienvenida\": os.getenv(\"WHATSAPP_META_PLANTILLA_BIENVENIDA\", \"\").strip() or \"bienvenida_cliente\",\n        \"pl_cotizacion\": os.getenv(\"WHATSAPP_META_PLANTILLA_COTIZACION\", \"\").strip() or \"cotizacion_cliente\",\n        # Reparaciones: orden de servicio y diagnóstico, con el PDF adjunto.\n        \"pl_orden\": os.getenv(\"WHATSAPP_META_PLANTILLA_ORDEN\", \"\").strip() or \"orden_servicio_cliente\",\n        \"pl_diagnostico\": os.getenv(\"WHATSAPP_META_PLANTILLA_DIAGNOSTICO\", \"\").strip() or \"diagnostico_cliente\",\n        \"idioma\": os.getenv(\"WHATSAPP_META_IDIOMA\", \"\").strip() or \"es_MX\",\n    }\n\n"
  ],
  [
   "    )\n\n\n# ---- Webhook ----\n\ndef verificar_suscripcion(modo, token, reto):\n",
   "    )\n\n\ndef enviar_documento_reparacion(tipo, telefono, parametros, pdf_bytes: bytes, nombre_archivo: str) -> str:\n    \"\"\"tipo: 'orden' o 'diagnostico'. Plantillas (encabezado Documento):\n    orden_servicio_cliente: {{1}} cliente, {{2}} equipo, {{3}} folio.\n    diagnostico_cliente: {{1}} cliente, {{2}} equipo, {{3}} folio, {{4}} costo.\"\"\"\n    media_id = subir_pdf(pdf_bytes, nombre_archivo)\n    plantilla = _cfg()[\"pl_diagnostico\" if tipo == \"diagnostico\" else \"pl_orden\"]\n    return enviar_plantilla(telefono, plantilla, parametros, documento={\"id\": media_id, \"filename\": nombre_archivo})\n\n\n# ---- Webhook ----\n\ndef verificar_suscripcion(modo, token, reto):\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "def _estados_permitidos_reparacion" not in f.read():
            print("Primero corre fix_reparaciones_flujo_areas.py (y los anteriores), y luego este.")
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
