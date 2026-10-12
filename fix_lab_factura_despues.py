# -*- coding: utf-8 -*-
"""
Laboratorio: factura DESPUÉS de crear el pedido.
  - Nuevo POST /api/laboratorio/mios/{id}/factura: el estudiante pide factura
    (o cambia sus datos) de un pedido ya creado, mientras no se entregue.
  - Si la cotización ya estaba en Microsip, se le cambia el cliente al de la
    factura (mismo RFC o alta). Si no se pudo, el detalle del trabajo en la
    web muestra "📤 Poner factura en Microsip" para reintentar.
  - Con factura, el cliente de Microsip se busca solo por RFC / razón social
    (antes podía caer en el cliente del estudiante por su nombre).
REQUIERE haber corrido antes fix_limpiar_laboratorio.py.
Toca: backend/app.py, backend/db.py, backend/microsip_escritura.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    if not factura and estudiante.get(\"microsip_cliente_id\"):\n        if microsip_escritura.leer_cliente(cfg, estudiante[\"microsip_cliente_id\"]):\n            return estudiante[\"microsip_cliente_id\"]\n    for c in _similares_microsip(cfg, datos):\n        motivos = c.get(\"motivos\") or []\n        if \"Mismo RFC\" in motivos:\n            return c[\"cliente_id\"]\n",
   "    if not factura and estudiante.get(\"microsip_cliente_id\"):\n        if microsip_escritura.leer_cliente(cfg, estudiante[\"microsip_cliente_id\"]):\n            return estudiante[\"microsip_cliente_id\"]\n    # Con factura se busca solo por RFC y razón social: el nombre o teléfono\n    # del estudiante llevaría a SU cliente, no al de la factura.\n    busqueda = {\"razon_social\": datos.get(\"razon_social\"), \"rfc\": datos.get(\"rfc\")} if factura else datos\n    for c in _similares_microsip(cfg, busqueda):\n        motivos = c.get(\"motivos\") or []\n        if \"Mismo RFC\" in motivos:\n            return c[\"cliente_id\"]\n"
  ],
  [
   "    return None\n\n\ndef _enviar_trabajo_lab_microsip(empresa_id, trabajo_id):\n    \"\"\"Crea la cotización del pedido en Microsip. Regresa el resultado o lanza\n    RuntimeError con el motivo (que también queda guardado en el trabajo).\"\"\"\n    cfg = db.obtener_config_microsip_escritura(empresa_id) or {}\n    trabajo = db.obtener_trabajo_laboratorio(empresa_id, trabajo_id)\n    if not trabajo:\n        raise RuntimeError(\"Trabajo no encontrado\")\n    if trabajo.get(\"microsip_folio\"):\n        return {\"folio\": trabajo[\"microsip_folio\"], \"ya_estaba\": True}\n\n    def fallar(msg):\n        db.marcar_trabajo_laboratorio_microsip(trabajo_id, error=msg)\n        raise RuntimeError(msg)\n\n    if not cfg.get(\"microsip_host\"):\n        fallar(\"Microsip no está configurado (Administrar → Microsip).\")\n    if not cfg.get(\"lab_microsip_sucursal_id\") or not cfg.get(\"lab_microsip_almacen_id\"):\n        fallar(\"Falta elegir la sucursal y el almacén del laboratorio en Administrar → Microsip → Pedidos del laboratorio.\")\n    partidas, faltan = _partidas_microsip_lab(cfg, trabajo)\n    if faltan:\n        fallar(\"Falta elegir el artículo de Microsip para: \" + \", \".join(faltan) + \" (Administrar → Microsip → Pedidos del laboratorio).\")\n    if not partidas:\n        fallar(\"El pedido todavía no tiene piezas (odontograma vacío).\")\n    estudiante = db.obtener_datos_fiscales_usuario(trabajo[\"creado_por_id\"]) or {}\n    try:\n        df = json.loads(trabajo.get(\"datos_factura_json\") or \"null\")\n",
   "    return None\n\n\ndef _datos_cliente_lab(trabajo):\n    \"\"\"(estudiante, datos_cliente para Microsip, si es con factura).\"\"\"\n    estudiante = db.obtener_datos_fiscales_usuario(trabajo[\"creado_por_id\"]) or {}\n    try:\n        df = json.loads(trabajo.get(\"datos_factura_json\") or \"null\")\n"
  ],
  [
   "                      \"uso_cfdi\": df.get(\"uso_cfdi\"), \"codigo_postal\": df.get(\"codigo_postal\"),\n                      \"domicilio\": df.get(\"domicilio_fiscal\"), \"municipio\": df.get(\"municipio\"), \"estado\": df.get(\"estado\"),\n                      \"email\": df.get(\"correo\") or estudiante.get(\"email\")})\n    try:\n        cliente_id = _cliente_microsip_lab(cfg, datos, factura, estudiante)\n        r = microsip_escritura.enviar_cotizacion(\n",
   "                      \"uso_cfdi\": df.get(\"uso_cfdi\"), \"codigo_postal\": df.get(\"codigo_postal\"),\n                      \"domicilio\": df.get(\"domicilio_fiscal\"), \"municipio\": df.get(\"municipio\"), \"estado\": df.get(\"estado\"),\n                      \"email\": df.get(\"correo\") or estudiante.get(\"email\")})\n    return estudiante, datos, factura\n\n\ndef _cambiar_cliente_lab_microsip(cfg, trabajo, fallar):\n    \"\"\"La cotización ya estaba en Microsip y el estudiante pidió factura\n    después: se le cambia el cliente al de la factura (mismo RFC o alta).\"\"\"\n    estudiante, datos, factura = _datos_cliente_lab(trabajo)\n    if not factura:\n        db.marcar_factura_microsip_lista(trabajo[\"id\"])\n        return {\"folio\": trabajo[\"microsip_folio\"], \"ya_estaba\": True}\n    try:\n        cliente_id = _cliente_microsip_lab(cfg, datos, True, estudiante)\n        r = microsip_escritura.cambiar_cliente_cotizacion(\n            cfg, docto_ve_id=trabajo[\"microsip_docto_id\"], datos_cliente=datos, cliente_id=cliente_id,\n            usuario=cfg.get(\"lab_microsip_usuario\"))\n    except microsip_escritura.ErrorMicrosip as e:\n        fallar(f\"No se pudo poner la factura en la cotización de Microsip — {e}\")\n    except Exception as e:\n        fallar(f\"No se pudo conectar con Microsip: {e}\")\n    db.marcar_factura_microsip_lista(trabajo[\"id\"])\n    db.agregar_actualizacion_laboratorio(\n        trabajo[\"id\"], trabajo[\"creado_por_id\"],\n        f\"Cotización {r['folio']} de Microsip cambiada al cliente de la factura \"\n        f\"({'cliente NUEVO ' if r['cliente_creado'] else ''}{r['cliente_nombre']}).\"\n        + (\" Avisos: \" + \" \".join(r[\"avisos\"]) if r.get(\"avisos\") else \"\"))\n    return {**r, \"factura\": True}\n\n\ndef _enviar_trabajo_lab_microsip(empresa_id, trabajo_id):\n    \"\"\"Crea la cotización del pedido en Microsip. Regresa el resultado o lanza\n    RuntimeError con el motivo (que también queda guardado en el trabajo).\"\"\"\n    cfg = db.obtener_config_microsip_escritura(empresa_id) or {}\n    trabajo = db.obtener_trabajo_laboratorio(empresa_id, trabajo_id)\n    if not trabajo:\n        raise RuntimeError(\"Trabajo no encontrado\")\n\n    def fallar(msg):\n        db.marcar_trabajo_laboratorio_microsip(trabajo_id, error=msg)\n        raise RuntimeError(msg)\n\n    if trabajo.get(\"microsip_folio\"):\n        if trabajo.get(\"microsip_factura_pendiente\"):\n            return _cambiar_cliente_lab_microsip(cfg, trabajo, fallar)\n        return {\"folio\": trabajo[\"microsip_folio\"], \"ya_estaba\": True}\n\n    if not cfg.get(\"microsip_host\"):\n        fallar(\"Microsip no está configurado (Administrar → Microsip).\")\n    if not cfg.get(\"lab_microsip_sucursal_id\") or not cfg.get(\"lab_microsip_almacen_id\"):\n        fallar(\"Falta elegir la sucursal y el almacén del laboratorio en Administrar → Microsip → Pedidos del laboratorio.\")\n    partidas, faltan = _partidas_microsip_lab(cfg, trabajo)\n    if faltan:\n        fallar(\"Falta elegir el artículo de Microsip para: \" + \", \".join(faltan) + \" (Administrar → Microsip → Pedidos del laboratorio).\")\n    if not partidas:\n        fallar(\"El pedido todavía no tiene piezas (odontograma vacío).\")\n    estudiante, datos, factura = _datos_cliente_lab(trabajo)\n    try:\n        cliente_id = _cliente_microsip_lab(cfg, datos, factura, estudiante)\n        r = microsip_escritura.enviar_cotizacion(\n"
  ],
  [
   "        datos[\"correo\"] = r[\"email\"]\n    return {\"datos\": datos, \"tiene_constancia\": bool(r.get(\"constancia_fiscal_nombre\")),\n            \"catalogos\": {\"regimenes\": facturacion_flete.REGIMENES_FISCALES, \"usos_cfdi\": facturacion_flete.USOS_CFDI}}\n\n\n@app.post(\"/api/laboratorio/mios/{trabajo_id}/reportar-pago\")\n",
   "        datos[\"correo\"] = r[\"email\"]\n    return {\"datos\": datos, \"tiene_constancia\": bool(r.get(\"constancia_fiscal_nombre\")),\n            \"catalogos\": {\"regimenes\": facturacion_flete.REGIMENES_FISCALES, \"usos_cfdi\": facturacion_flete.USOS_CFDI}}\n\n\n@app.post(\"/api/laboratorio/mios/{trabajo_id}/factura\")\ndef api_facturar_mi_trabajo_laboratorio(trabajo_id: int, payload: DatosFacturaLabIn, background_tasks: BackgroundTasks,\n                                        usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    \"\"\"El estudiante pide factura DESPUÉS de crear su pedido (o cambia los\n    datos). Si la cotización ya está en Microsip se le cambia el cliente al\n    de la factura; si todavía no, se crea ya con la factura.\"\"\"\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if trabajo[\"estado\"] in (\"entregado\", \"cancelado\"):\n        raise HTTPException(status_code=400, detail=\"Este trabajo ya se cerró; pide la factura directo al laboratorio.\")\n    datos = _datos_factura_lab(True, payload)\n    ya_en_microsip = bool(trabajo.get(\"microsip_folio\"))\n    db.marcar_factura_trabajo_laboratorio(trabajo_id, datos, ya_en_microsip)\n    db.guardar_datos_fiscales_usuario(usuario[\"id\"], datos,\n                                      _como_data_url(payload.constancia_base64) if payload.constancia_base64 else None,\n                                      _limpio(payload.constancia_nombre))\n    db.agregar_actualizacion_laboratorio(\n        trabajo_id, usuario[\"id\"],\n        f\"{'Cambió los datos de' if trabajo.get('datos_factura_json') else 'Pidió'} factura a nombre de \"\n        f\"{datos['razon_social']} (RFC {datos['rfc']}).\")\n    if _lab_microsip_activo(usuario[\"empresa_id\"]):\n        background_tasks.add_task(_enviar_trabajo_lab_microsip_seguro, usuario[\"empresa_id\"], trabajo_id)\n    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\n@app.post(\"/api/laboratorio/mios/{trabajo_id}/reportar-pago\")\n"
  ]
 ],
 "backend/db.py": [
  [
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_folio TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_enviada_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_error TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS constancia_fiscal_base64 TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS constancia_fiscal_nombre TEXT;\n",
   "        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_folio TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_enviada_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_error TEXT;\n        -- Factura pedida DESPUÉS de crear el pedido: si la cotización ya\n        -- estaba en Microsip, falta cambiarle el cliente al de la factura.\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS microsip_factura_pendiente BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS datos_fiscales_json TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS constancia_fiscal_base64 TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS constancia_fiscal_nombre TEXT;\n"
  ],
  [
   "    cur.close(); conn.close()\n\n\ndef marcar_trabajo_laboratorio_microsip(trabajo_id, docto_id=None, folio=None, error=None):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    cur.close(); conn.close()\n\n\ndef marcar_factura_trabajo_laboratorio(trabajo_id, datos, microsip_pendiente):\n    \"\"\"El estudiante pidió factura después de crear el pedido.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"UPDATE trabajos_laboratorio SET requiere_factura = TRUE, datos_factura_json = %s,\n                          microsip_factura_pendiente = %s WHERE id = %s\"\"\",\n                (json.dumps(datos, ensure_ascii=False), bool(microsip_pendiente), trabajo_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef marcar_factura_microsip_lista(trabajo_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE trabajos_laboratorio SET microsip_factura_pendiente = FALSE, microsip_error = NULL WHERE id = %s\",\n                (trabajo_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef marcar_trabajo_laboratorio_microsip(trabajo_id, docto_id=None, folio=None, error=None):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "backend/microsip_escritura.py": [
  [
   "    }\n\n\ndef alta_cliente(config, *, datos_cliente, cliente_id=None):\n    \"\"\"Solo el cliente (sin cotización): da de alta en Microsip o, si ya se\n    eligió uno, le llena los datos que tenga vacíos. Se usa, por ejemplo,\n",
   "    }\n\n\ndef cambiar_cliente_cotizacion(config, *, docto_ve_id, datos_cliente, cliente_id=None, usuario=None):\n    \"\"\"Le cambia el cliente a una cotización que ya está en Microsip (por\n    ejemplo, el estudiante pidió factura después de crear su pedido). Solo\n    si sigue siendo cotización pendiente (no convertida ni cancelada).\n    cliente_id: el de Microsip ya elegido; None = dar de alta con datos_cliente.\"\"\"\n    avisos = []\n    con = _conectar(config)\n    try:\n        esq = _Esquema(con.cursor(), usuario)\n        doc = esq.fila(\"SELECT DOCTO_VE_ID, TIPO_DOCTO, FOLIO, ESTATUS, APLICADO, CLIENTE_ID FROM DOCTOS_VE WHERE DOCTO_VE_ID = ?\",\n                       (docto_ve_id,))\n        if not doc:\n            raise ErrorMicrosip(\"Cotización\", f\"ya no existe en Microsip (documento #{docto_ve_id})\")\n        folio = (doc[\"FOLIO\"] or \"\").strip()\n        if (doc[\"TIPO_DOCTO\"] or \"\").strip() != \"C\":\n            raise ErrorMicrosip(\"Cotización\", f\"el documento {folio} ya no es una cotización\")\n        if (doc[\"ESTATUS\"] or \"\").strip() != \"P\":\n            raise ErrorMicrosip(\"Cotización\", f\"la cotización {folio} ya se convirtió o se canceló en Microsip; cambia el cliente allá\")\n        creado = False\n        if cliente_id:\n            dir_id, clave, nombre, _ = _completar_cliente(esq, cliente_id, datos_cliente, avisos)\n        else:\n            cliente_id, dir_id, clave, nombre = _crear_cliente(esq, datos_cliente, avisos)\n            creado = True\n        aplicado = (doc[\"APLICADO\"] or \"\").strip() == \"S\"\n        cambios = {\"CLIENTE_ID\": cliente_id, \"CLAVE_CLIENTE\": clave, \"DIR_CLI_ID\": dir_id, \"DIR_CONSIG_ID\": dir_id,\n                   \"USUARIO_ULT_MODIF\": esq.usuario, \"FECHA_HORA_ULT_MODIF\": _ahora()}\n        for col in esq.columnas_texto(\"DOCTOS_VE\", \"USO_CFDI\"):\n            if datos_cliente.get(\"uso_cfdi\"):\n                cambios[col] = datos_cliente[\"uso_cfdi\"]\n        try:\n            # Igual que Microsip al editar: se \"desaplica\", se cambia y se vuelve a aplicar.\n            if aplicado:\n                _actualizar(esq, \"DOCTOS_VE\", \"DOCTO_VE_ID\", docto_ve_id, {\"APLICADO\": \"N\"})\n            _actualizar(esq, \"DOCTOS_VE\", \"DOCTO_VE_ID\", docto_ve_id, cambios)\n            if aplicado:\n                _actualizar(esq, \"DOCTOS_VE\", \"DOCTO_VE_ID\", docto_ve_id, {\"APLICADO\": \"S\"})\n        except fdb.DatabaseError as e:\n            raise ErrorMicrosip(f\"Cotización {folio} (cambiar cliente)\", _error_fb(e))\n        con.commit()\n    except fdb.DatabaseError as e:\n        con.rollback()\n        raise ErrorMicrosip(\"Microsip\", _error_fb(e))\n    except Exception:\n        con.rollback()\n        raise\n    finally:\n        con.close()\n    return {\"folio\": folio, \"cliente_id\": cliente_id, \"cliente_nombre\": nombre, \"cliente_clave\": clave,\n            \"cliente_creado\": creado, \"avisos\": avisos}\n\n\ndef alta_cliente(config, *, datos_cliente, cliente_id=None):\n    \"\"\"Solo el cliente (sin cotización): da de alta en Microsip o, si ya se\n    eligió uno, le llena los datos que tenga vacíos. Se usa, por ejemplo,\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  let ms = '';\n  if (w.microsip_folio) {\n    ms = `<div style=\"font-size:13px; margin-top:${factura ? 8 : 0}px;\">✅ Cotización en Microsip: <b>${escapeHtml(w.microsip_folio)}</b>${w.microsip_enviada_en ? ` <span style=\"color:var(--muted);\">(${escapeHtml(w.microsip_enviada_en.slice(0, 16).replace('T', ' '))})</span>` : ''}</div>`;\n  } else if (w.microsip_error || puedeMandar) {\n    ms = `<div style=\"font-size:13px; margin-top:${factura ? 8 : 0}px;\">\n      ${w.microsip_error ? `<span style=\"color:#e8a33d;\">⚠️ Microsip: ${escapeHtml(w.microsip_error)}</span><br>` : '<span style=\"color:var(--muted);\">Sin cotización en Microsip todavía.</span><br>'}\n",
   "  let ms = '';\n  if (w.microsip_folio) {\n    ms = `<div style=\"font-size:13px; margin-top:${factura ? 8 : 0}px;\">✅ Cotización en Microsip: <b>${escapeHtml(w.microsip_folio)}</b>${w.microsip_enviada_en ? ` <span style=\"color:var(--muted);\">(${escapeHtml(w.microsip_enviada_en.slice(0, 16).replace('T', ' '))})</span>` : ''}</div>`;\n    if (w.microsip_factura_pendiente) {\n      ms += `<div style=\"font-size:13px; margin-top:4px;\">\n        <span style=\"color:#e8a33d;\">⚠️ Pidió factura después de crear el pedido: falta poner el cliente de la factura en esta cotización.${w.microsip_error ? ' ' + escapeHtml(w.microsip_error) : ''}</span>\n        ${puedeMandar ? `<br><button class=\"secondary\" style=\"margin-top:6px; padding:3px 10px; font-size:12px;\" onclick=\"lab_mandarMicrosip(${w.id}, this)\">📤 Poner factura en Microsip</button>` : ''}\n      </div>`;\n    }\n  } else if (w.microsip_error || puedeMandar) {\n    ms = `<div style=\"font-size:13px; margin-top:${factura ? 8 : 0}px;\">\n      ${w.microsip_error ? `<span style=\"color:#e8a33d;\">⚠️ Microsip: ${escapeHtml(w.microsip_error)}</span><br>` : '<span style=\"color:var(--muted);\">Sin cotización en Microsip todavía.</span><br>'}\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "def limpiar_laboratorio" not in f.read():
            print("Primero corre fix_usuarios_sin_estudiantes.py y fix_limpiar_laboratorio.py (y luego este).")
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
