# -*- coding: utf-8 -*-
"""
CHECADOR DE PRECIO: IVA REAL POR ARTICULO + ALMACENES VISIBLES
1) Precio con IVA: ahora usa el impuesto que cada articulo tiene en Microsip.
   Los exentos o tasa 0 (ej. anestesias) se muestran a su precio real, sin
   sumarles el 16% ("exento de IVA"). Tambien en el respaldo de inventario.
2) Administrar -> Microsip -> "Checador de precio": con checks eliges que
   almacenes muestran su existencia al consultar un precio (web y app).
   Los no marcados no le aparecen a nadie; el administrador siempre ve todos.
Toca: backend/db.py, backend/app.py, backend/microsip.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_checador_iva_almacenes.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "        -- Base de PRUEBAS de Microsip (copia): ruta (y opcional host/usuario) y, por módulo,\n        -- qué personas la usan. Todos los demás siguen en la base real.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_pruebas_json TEXT;\n    \"\"\")\n    conn.commit()\n\n",
   "        -- Base de PRUEBAS de Microsip (copia): ruta (y opcional host/usuario) y, por módulo,\n        -- qué personas la usan. Todos los demás siguen en la base real.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_pruebas_json TEXT;\n        -- Checador de precio: almacenes cuya existencia se muestra (NULL = todos).\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS checador_almacenes_json TEXT;\n    \"\"\")\n    conn.commit()\n\n"
  ],
  [
   "    \"ventas\": \"🧾 Checador de precio, cotizador y CRM\",\n    \"entregas\": \"🚚 Entregas / Logística (pedidos de Microsip)\",\n}\n\n\ndef obtener_microsip_pruebas(empresa_id):\n",
   "    \"ventas\": \"🧾 Checador de precio, cotizador y CRM\",\n    \"entregas\": \"🚚 Entregas / Logística (pedidos de Microsip)\",\n}\n\n\ndef almacenes_visibles_checador(empresa_id):\n    \"\"\"Lista de ALMACEN_ID que se muestran en el checador de precio, o None = todos.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT checador_almacenes_json FROM empresas WHERE id = %s\", (empresa_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    try:\n        v = json.loads((row or {}).get(\"checador_almacenes_json\") or \"null\")\n    except (TypeError, ValueError):\n        v = None\n    return [int(x) for x in v] if isinstance(v, list) else None\n\n\ndef guardar_almacenes_visibles_checador(empresa_id, ids):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET checador_almacenes_json = %s WHERE id = %s\",\n                (None if ids is None else json.dumps([int(x) for x in ids]), empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef obtener_microsip_pruebas(empresa_id):\n"
  ]
 ],
 "backend/app.py": [
  [
   "    return config\n\n\n@app.get(\"/api/checador-precio/clave/{clave}\")\ndef api_checador_precio_por_clave(clave: str, usuario: dict = Depends(requiere_ver_checador_precio)):\n    try:\n",
   "    return config\n\n\ndef _filtrar_almacenes_checador(usuario, resultado):\n    \"\"\"Solo los almacenes que el administrador marcó como visibles (el admin ve todos).\"\"\"\n    if not resultado or usuario.get(\"rol\") == \"admin\":\n        return resultado\n    visibles = db.almacenes_visibles_checador(usuario[\"empresa_id\"])\n    if visibles is None:\n        return resultado\n    vis = set(visibles)\n    almacenes = [a for a in (resultado.get(\"almacenes\") or []) if a.get(\"almacen_id\") in vis]\n    resultado[\"almacenes\"] = almacenes\n    if \"existencia_total\" in resultado:\n        resultado[\"existencia_total\"] = sum(float(a.get(\"existencia\") or 0) for a in almacenes)\n    if \"comprometido_total\" in resultado:\n        resultado[\"comprometido_total\"] = sum(float(a.get(\"comprometido\") or 0) for a in almacenes)\n    if \"disponible_total\" in resultado:\n        resultado[\"disponible_total\"] = sum(float(a.get(\"disponible\") or 0) for a in almacenes)\n    if resultado.get(\"capas_detalle\"):\n        resultado[\"capas_detalle\"] = [c for c in resultado[\"capas_detalle\"] if c.get(\"almacen_id\") in vis]\n    return resultado\n\n\nclass AlmacenesChecadorIn(BaseModel):\n    todos: bool = True\n    almacen_ids: List[int] = []\n\n\n@app.get(\"/api/checador-precio/almacenes-config\")\ndef api_ver_almacenes_checador(usuario: dict = Depends(requiere_admin_completo)):\n    config = _config_microsip_o_error(usuario)\n    try:\n        todos = microsip.listar_almacenes(config)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (almacenes): {e}\")\n    return {\"almacenes\": todos, \"visibles\": db.almacenes_visibles_checador(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/checador-precio/almacenes-config\")\ndef api_guardar_almacenes_checador(payload: AlmacenesChecadorIn, usuario: dict = Depends(requiere_admin_completo)):\n    if not payload.todos and not payload.almacen_ids:\n        raise HTTPException(status_code=400, detail=\"Marca al menos un almacén (o deja 'Todos')\")\n    db.guardar_almacenes_visibles_checador(usuario[\"empresa_id\"], None if payload.todos else payload.almacen_ids)\n    return {\"ok\": True}\n\n\n@app.get(\"/api/checador-precio/clave/{clave}\")\ndef api_checador_precio_por_clave(clave: str, usuario: dict = Depends(requiere_ver_checador_precio)):\n    try:\n"
  ],
  [
   "            resultado[\"ultima_sincronizacion\"] = meta[\"actualizado_en\"] if meta else None\n    if not resultado:\n        raise HTTPException(status_code=404, detail=f\"No se encontró ningún producto con la clave '{clave}'\")\n    return resultado\n\n\n@app.get(\"/api/checador-precio/articulo/{articulo_id}\")\n",
   "            resultado[\"ultima_sincronizacion\"] = meta[\"actualizado_en\"] if meta else None\n    if not resultado:\n        raise HTTPException(status_code=404, detail=f\"No se encontró ningún producto con la clave '{clave}'\")\n    return _filtrar_almacenes_checador(usuario, resultado)\n\n\n@app.get(\"/api/checador-precio/articulo/{articulo_id}\")\n"
  ],
  [
   "            resultado[\"ultima_sincronizacion\"] = meta[\"actualizado_en\"] if meta else None\n    if not resultado:\n        raise HTTPException(status_code=404, detail=\"No se encontró ese producto\")\n    return resultado\n\n\n@app.get(\"/api/checador-precio/buscar\")\n",
   "            resultado[\"ultima_sincronizacion\"] = meta[\"actualizado_en\"] if meta else None\n    if not resultado:\n        raise HTTPException(status_code=404, detail=\"No se encontró ese producto\")\n    return _filtrar_almacenes_checador(usuario, resultado)\n\n\n@app.get(\"/api/checador-precio/buscar\")\n"
  ]
 ],
 "backend/microsip.py": [
  [
   "# de capas de Microsip) y COMPROM_ARTICULOS (piezas comprometidas por almacén).\n# =============================================================================\n\ndef _consultar_producto_por_articulo_id(cur, articulo_id):\n    cur.execute(\"SELECT NOMBRE FROM ARTICULOS WHERE ARTICULO_ID = ?\", (articulo_id,))\n    row = cur.fetchone()\n",
   "# de capas de Microsip) y COMPROM_ARTICULOS (piezas comprometidas por almacén).\n# =============================================================================\n\ndef tasas_iva_articulos(cur, articulo_ids):\n    \"\"\"% de IVA REAL de cada artículo según Microsip (IMPUESTOS_ARTICULOS + IMPUESTOS):\n    ej. anestesias exentas o tasa 0 -> 0. Sin impuesto asignado (o si la tabla no\n    existe) se usa 16%, como antes.\"\"\"\n    tasas = {}\n    ids = sorted({int(a) for a in articulo_ids if a})\n    if not ids:\n        return tasas\n    try:\n        for i in range(0, len(ids), 400):\n            lote = ids[i:i + 400]\n            cur.execute(f\"\"\"SELECT ia.ARTICULO_ID, MAX(i.PCTJE_IMPUESTO)\n                            FROM IMPUESTOS_ARTICULOS ia JOIN IMPUESTOS i ON i.IMPUESTO_ID = ia.IMPUESTO_ID\n                            WHERE ia.ARTICULO_ID IN ({\",\".join(\"?\" for _ in lote)})\n                            GROUP BY ia.ARTICULO_ID\"\"\", tuple(lote))\n            for aid, pct in cur.fetchall():\n                if pct is not None:\n                    tasas[aid] = float(pct)\n    except Exception:\n        pass\n    return tasas\n\n\ndef _consultar_producto_por_articulo_id(cur, articulo_id):\n    cur.execute(\"SELECT NOMBRE FROM ARTICULOS WHERE ARTICULO_ID = ?\", (articulo_id,))\n    row = cur.fetchone()\n"
  ],
  [
   "    cur.execute(\"SELECT FIRST 1 PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID = ?\", (articulo_id,))\n    fila_precio = cur.fetchone()\n    precio_sin_impuesto = float(fila_precio[0]) if fila_precio and fila_precio[0] is not None else None\n    precio_con_impuesto = round(precio_sin_impuesto * 1.16, 2) if precio_sin_impuesto is not None else None\n\n    # Solo las capas de costo NO agotadas cuentan como existencia real.\n    # Un artículo puede tener varias capas (compras en distintas fechas a\n",
   "    cur.execute(\"SELECT FIRST 1 PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID = ?\", (articulo_id,))\n    fila_precio = cur.fetchone()\n    precio_sin_impuesto = float(fila_precio[0]) if fila_precio and fila_precio[0] is not None else None\n    # IVA REAL del artículo (exentos / tasa 0, como las anestesias, no llevan 16%).\n    pct_iva = tasas_iva_articulos(cur, [articulo_id]).get(articulo_id, 16.0)\n    precio_con_impuesto = round(precio_sin_impuesto * (1 + pct_iva / 100), 2) if precio_sin_impuesto is not None else None\n\n    # Solo las capas de costo NO agotadas cuentan como existencia real.\n    # Un artículo puede tener varias capas (compras en distintas fechas a\n"
  ],
  [
   "        \"claves\": claves,\n        \"precio_sin_impuesto\": precio_sin_impuesto,\n        \"precio_con_impuesto\": precio_con_impuesto,\n        \"existencia_total\": total_existencia,\n        \"comprometido_total\": sum(comprometido_por_almacen.values()),\n        \"disponible_total\": total_existencia - sum(comprometido_por_almacen.values()),\n",
   "        \"claves\": claves,\n        \"precio_sin_impuesto\": precio_sin_impuesto,\n        \"precio_con_impuesto\": precio_con_impuesto,\n        \"pct_iva\": pct_iva,\n        \"existencia_total\": total_existencia,\n        \"comprometido_total\": sum(comprometido_por_almacen.values()),\n        \"disponible_total\": total_existencia - sum(comprometido_por_almacen.values()),\n"
  ],
  [
   "        for aid, clave in cur.fetchall():\n            if aid not in claves and clave:\n                claves[aid] = clave\n        cur.execute(f\"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})\", tuple(lote))\n        for aid, precio in cur.fetchall():\n            if aid not in precios and precio is not None:\n                precios[aid] = round(float(precio) * 1.16, 2)\n\n    con.close()\n\n",
   "        for aid, clave in cur.fetchall():\n            if aid not in claves and clave:\n                claves[aid] = clave\n        tasas = tasas_iva_articulos(cur, lote)\n        cur.execute(f\"SELECT ARTICULO_ID, PRECIO FROM PRECIOS_ARTICULOS WHERE ARTICULO_ID IN ({placeholders})\", tuple(lote))\n        for aid, precio in cur.fetchall():\n            if aid not in precios and precio is not None:\n                precios[aid] = round(float(precio) * (1 + tasas.get(aid, 16.0) / 100), 2)\n\n    con.close()\n\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    <div style=\"border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:14px; margin-top:14px;\">\n      <h3 style=\"margin-top:0;\">${escapeHtml(datos.nombre)}</h3>\n      ${datos.claves.length ? `<p style=\"font-size:11px; color:var(--muted);\">Clave(s): ${datos.claves.map(escapeHtml).join(', ')}</p>` : ''}\n      <p style=\"font-size:20px; margin:10px 0;\"><b>Precio de lista:</b> $${fmt(datos.precio_con_impuesto)} <span style=\"font-size:11px; color:var(--muted); font-weight:400;\">(con IVA)</span></p>\n      <p style=\"font-size:13px; color:var(--muted);\">\n        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style=\"color:var(--trace);\">${fmt(datos.disponible_total)} disponibles</b>\n      </p>\n",
   "    <div style=\"border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:14px; margin-top:14px;\">\n      <h3 style=\"margin-top:0;\">${escapeHtml(datos.nombre)}</h3>\n      ${datos.claves.length ? `<p style=\"font-size:11px; color:var(--muted);\">Clave(s): ${datos.claves.map(escapeHtml).join(', ')}</p>` : ''}\n      <p style=\"font-size:20px; margin:10px 0;\"><b>Precio de lista:</b> $${fmt(datos.precio_con_impuesto)} <span style=\"font-size:11px; color:var(--muted); font-weight:400;\">${datos.pct_iva === 0 ? '(exento de IVA)' : '(con IVA)'}</span></p>\n      <p style=\"font-size:13px; color:var(--muted);\">\n        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style=\"color:var(--trace);\">${fmt(datos.disponible_total)} disponibles</b>\n      </p>\n"
  ],
  [
   "      ['ms_usr', '👥 Usuarios y permisos', esAdmin],\n      ['ms_lote', '📦 Lote / serie faltante', esAdmin],\n      ['ms_pruebas', '🧪 Base de pruebas', esAdmin],\n      ['explorador_microsip', '🔍 Explorador de tablas', esAdmin],\n    ] },\n    { titulo: '🔗 Otras integraciones', tabs: [\n",
   "      ['ms_usr', '👥 Usuarios y permisos', esAdmin],\n      ['ms_lote', '📦 Lote / serie faltante', esAdmin],\n      ['ms_pruebas', '🧪 Base de pruebas', esAdmin],\n      ['ms_checador', '🏷️ Checador de precio', esAdmin],\n      ['explorador_microsip', '🔍 Explorador de tablas', esAdmin],\n    ] },\n    { titulo: '🔗 Otras integraciones', tabs: [\n"
  ],
  [
   "  } else if (ADMIN_TAB === 'terminologia' && esAdmin) {\n    const datos = await api('/api/terminos/editables');\n    renderTerminologiaAdmin(tabs, datos);\n  } else if (['microsip', 'ms_escritura', 'ms_lab', 'ms_vac', 'ms_usr', 'ms_lote', 'ms_pruebas'].includes(ADMIN_TAB) && esAdmin) {\n    const config = await api('/api/microsip/config');\n    renderMicrosipAdmin(tabs, config, ADMIN_TAB);\n  } else if (ADMIN_TAB === 'shopify' && esAdmin) {\n",
   "  } else if (ADMIN_TAB === 'terminologia' && esAdmin) {\n    const datos = await api('/api/terminos/editables');\n    renderTerminologiaAdmin(tabs, datos);\n  } else if (['microsip', 'ms_escritura', 'ms_lab', 'ms_vac', 'ms_usr', 'ms_lote', 'ms_pruebas', 'ms_checador'].includes(ADMIN_TAB) && esAdmin) {\n    const config = await api('/api/microsip/config');\n    renderMicrosipAdmin(tabs, config, ADMIN_TAB);\n  } else if (ADMIN_TAB === 'shopify' && esAdmin) {\n"
  ],
  [
   "    `;\n    abrirModal(true);\n    if (config.microsip_host) {\n      ({ ms_escritura: ms_cargarEscritura, ms_lab: ms_cargarLab, ms_vac: ms_cargarVac, ms_usr: ms_renderUsr, ms_lote: ms_renderLote, ms_pruebas: ms_cargarPruebas })[seccion]();\n    }\n    return;\n  }\n",
   "    `;\n    abrirModal(true);\n    if (config.microsip_host) {\n      ({ ms_escritura: ms_cargarEscritura, ms_lab: ms_cargarLab, ms_vac: ms_cargarVac, ms_usr: ms_renderUsr, ms_lote: ms_renderLote, ms_pruebas: ms_cargarPruebas, ms_checador: ms_cargarChecador })[seccion]();\n    }\n    return;\n  }\n"
  ],
  [
   "\n// ---- Artículos que piden lote/serie y no lo tienen asignado ----\nlet MS_LOTE = null;\n// ---- 🧪 Base de PRUEBAS de Microsip: por módulo y SOLO para quien la marca ----\nasync function ms_cargarPruebas() {\n  const caja = document.getElementById('ms_pruebas');\n",
   "\n// ---- Artículos que piden lote/serie y no lo tienen asignado ----\nlet MS_LOTE = null;\n// ---- 🏷️ Checador de precio: qué almacenes muestran su existencia (web y app) ----\nasync function ms_cargarChecador() {\n  const caja = document.getElementById('ms_checador');\n  caja.innerHTML = '<p style=\"color:var(--muted);\">Cargando almacenes de Microsip…</p>';\n  let d;\n  try { d = await api('/api/checador-precio/almacenes-config'); } catch (e) { caja.innerHTML = `<p class=\"error-msg\">${escapeHtml(e.message)}</p>`; return; }\n  const todos = d.visibles === null;\n  const vis = new Set(d.visibles || []);\n  caja.innerHTML = `\n    <p style=\"font-size:12px; color:var(--muted); margin-bottom:10px;\">Marca los almacenes cuya <b>existencia</b> se muestra al consultar un precio (web y app). Los que no marques no le aparecen a nadie; el <b>administrador</b> siempre ve todos.</p>\n    <label style=\"display:flex; gap:8px; align-items:center; margin-bottom:8px; font-weight:700;\">\n      <input type=\"checkbox\" id=\"msc_todos\" ${todos ? 'checked' : ''} style=\"width:auto;\" onchange=\"document.querySelectorAll('.msc_alm').forEach(c => { c.disabled = this.checked; })\" /> Mostrar todos los almacenes\n    </label>\n    <div style=\"columns:2; column-gap:18px; margin-bottom:12px;\">\n      ${(d.almacenes || []).map(a => `<label style=\"display:flex; gap:8px; align-items:center; padding:4px 0; break-inside:avoid;\">\n        <input type=\"checkbox\" class=\"msc_alm\" value=\"${a.almacen_id}\" ${todos || vis.has(a.almacen_id) ? 'checked' : ''} ${todos ? 'disabled' : ''} style=\"width:auto;\" /> ${escapeHtml(a.nombre)}</label>`).join('') || '<p class=\"empty-col\">— sin almacenes —</p>'}\n    </div>\n    <button class=\"primary\" style=\"width:100%;\" onclick=\"ms_guardarChecador(this)\">Guardar</button>\n    <div id=\"msc_error\" class=\"error-msg\"></div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:12px;\">💲 El precio con IVA usa el impuesto que cada artículo tiene en Microsip: los exentos o tasa 0 (ej. anestesias) se muestran sin el 16%.</p>`;\n}\n\nasync function ms_guardarChecador(boton) {\n  const todos = document.getElementById('msc_todos').checked;\n  const ids = [...document.querySelectorAll('.msc_alm:checked')].map(c => Number(c.value));\n  const err = document.getElementById('msc_error'); err.textContent = '';\n  await conBloqueoDeBoton(boton, async () => {\n    try { await api('/api/checador-precio/almacenes-config', { method: 'POST', body: JSON.stringify({ todos, almacen_ids: ids }) });\n          mostrarExito(todos ? 'Se muestran todos los almacenes' : `Se muestran ${ids.length} almacén(es) en el checador`); }\n    catch (e) { err.textContent = e.message; }\n  });\n}\n\n// ---- 🧪 Base de PRUEBAS de Microsip: por módulo y SOLO para quien la marca ----\nasync function ms_cargarPruebas() {\n  const caja = document.getElementById('ms_pruebas');\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_iva_almacenes.py")
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
