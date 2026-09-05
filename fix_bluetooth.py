# -*- coding: utf-8 -*-
"""
Corrige la impresion Bluetooth a la Star SM-L200: en vez de mandar el
recibo completo incrustado en la liga que abre PassPRNT (podia pasarse del
limite de longitud y salir basura -- letras raras, tira de papel larga),
ahora se manda una liga CORTA a una pagina publica que la propia app
PassPRNT va a buscar por su cuenta.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_bluetooth.py
"""
import sys

ARCHIVOS = {'backend/db.py': [['        CREATE TABLE IF NOT EXISTS cotizacion_items (\n            id SERIAL PRIMARY KEY,\n            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,\n            articulo_id INTEGER,\n            clave TEXT,\n            nombre TEXT NOT NULL,\n            cantidad NUMERIC NOT NULL DEFAULT 1,\n            precio_unitario NUMERIC NOT NULL DEFAULT 0,\n            orden INTEGER NOT NULL DEFAULT 0\n        );\n    """)', 'CREATE TABLE IF NOT EXISTS cotizacion_items (\n            id SERIAL PRIMARY KEY,\n            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,\n            articulo_id INTEGER,\n            clave TEXT,\n            nombre TEXT NOT NULL,\n            cantidad NUMERIC NOT NULL DEFAULT 1,\n            precio_unitario NUMERIC NOT NULL DEFAULT 0,\n            orden INTEGER NOT NULL DEFAULT 0\n        );\n\n        -- Token público para la impresión Bluetooth (Star PassPRNT): la app\n        -- PassPRNT hace su propia petición HTTP para traer el recibo, sin\n        -- mandar el token de sesión de la app — necesita una liga corta y\n        -- pública (no adivinable) que apunte solo a ESA cotización.\n        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS token_impresion TEXT UNIQUE;\n    """)'], ['def eliminar_cotizacion(empresa_id, cotizacion_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("DELETE FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n    eliminado = cur.rowcount > 0\n    conn.commit()\n    cur.close(); conn.close()\n    return eliminado', 'def eliminar_cotizacion(empresa_id, cotizacion_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("DELETE FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n    eliminado = cur.rowcount > 0\n    conn.commit()\n    cur.close(); conn.close()\n    return eliminado\n\n\ndef generar_token_impresion_cotizacion(empresa_id, cotizacion_id):\n    """Token público para la liga corta que la app Star PassPRNT usa para\n    ir a buscar el recibo por su cuenta (ver generar_token_seguimiento_entrega,\n    mismo patrón). Se genera uno nuevo cada vez que se pide imprimir, para no\n    dejar ligas viejas de cotizaciones ya editadas circulando indefinidamente."""\n    import secrets\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("SELECT id FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n    if not cur.fetchone():\n        cur.close(); conn.close()\n        return None\n    token = secrets.token_urlsafe(24)\n    cur.execute("UPDATE cotizaciones SET token_impresion = %s WHERE id = %s", (token, cotizacion_id))\n    conn.commit()\n    cur.close(); conn.close()\n    return token\n\n\ndef obtener_cotizacion_por_token_impresion(token):\n    """Para la ruta pública que consulta la app Star PassPRNT (sin login)."""\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("SELECT id, empresa_id FROM cotizaciones WHERE token_impresion = %s", (token,))\n    fila = cur.fetchone()\n    if not fila:\n        cur.close(); conn.close()\n        return None\n    resultado = obtener_cotizacion(fila["empresa_id"], fila["id"], _conn_cur=(conn, cur))\n    cur.close(); conn.close()\n    return resultado']], 'backend/app.py': [['@app.get("/api/cotizaciones/{cotizacion_id}/pdf")\ndef api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    empresa = db.obtener_empresa(usuario["empresa_id"])\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa)\n    return Response(content=pdf_bytes, media_type="application/pdf",\n                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion[\'folio\']}.pdf"})', '@app.get("/api/cotizaciones/{cotizacion_id}/pdf")\ndef api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    empresa = db.obtener_empresa(usuario["empresa_id"])\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa)\n    return Response(content=pdf_bytes, media_type="application/pdf",\n                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion[\'folio\']}.pdf"})\n\n\n@app.post("/api/cotizaciones/{cotizacion_id}/liga-impresion")\ndef api_generar_liga_impresion_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    """Genera la liga pública y corta que se le manda a la app Star PassPRNT\n    (ella hace su propia petición HTTP para traer el recibo — no lleva el\n    token de sesión de la app, así que necesita una ruta pública aparte)."""\n    token = db.generar_token_impresion_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not token:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return {"token": token}\n\n\n@app.get("/recibo-cotizacion/{token}")\ndef api_recibo_cotizacion_publico(token: str):\n    """Ruta PÚBLICA (sin login) — la consulta directamente la app Star\n    PassPRNT para traer el recibo a imprimir. Token corto, aleatorio, y de\n    un solo uso por impresión (se regenera cada vez que se pide imprimir)."""\n    cotizacion = db.obtener_cotizacion_por_token_impresion(token)\n    if not cotizacion:\n        return Response(content="<p>Esta liga de impresión ya no es válida — vuelve a la cotización e imprime de nuevo.</p>",\n                         media_type="text/html; charset=utf-8", status_code=404)\n    html = pdfs_cotizaciones.generar_html_recibo_termico(cotizacion)\n    return Response(content=html, media_type="text/html; charset=utf-8")']], 'frontend/index.html': [['async function cot_descargarPdfLista(id, folio) {\n  try {\n    const r = await fetch(`/api/cotizaciones/${id}/pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error(\'No se pudo generar el PDF\');\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement(\'a\');\n    a.href = url;\n    a.download = `cotizacion_${folio}.pdf`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nfunction cot_descargarPdfActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  cot_descargarPdfLista(COT_ACTUAL.id, COT_ACTUAL.folio);\n}\n\nfunction cot_construirHtmlRecibo(c) {\n  const total = c.items.reduce((s, it) => s + (Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0), 0);\n  const filas = c.items.map(it => `\n    <tr>\n      <td style="text-align:left; padding:3px 0;">${escapeHtml(it.nombre)}${it.clave ? ` (${escapeHtml(it.clave)})` : \'\'}<br>${it.cantidad} x $${cot_fmt(it.precio_unitario)}</td>\n      <td style="text-align:right; white-space:nowrap; padding:3px 0;">$${cot_fmt((Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0))}</td>\n    </tr>\n  `).join(\'\');\n  return `<html><head><meta charset="utf-8"><style>\n    body { width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }\n    h1 { font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }\n    .centro { text-align:center; margin:2px 0; }\n    .linea { border-top:1px dashed #000; margin:8px 0; }\n    table { width:100%; border-collapse:collapse; }\n    .total td { font-size:15px; font-weight:bold; padding-top:6px; }\n  </style></head><body>\n    <h1>MARK · INC</h1>\n    <p class="centro">Cotización ${escapeHtml(c.folio)}</p>\n    <div class="linea"></div>\n    <p><b>Cliente:</b> ${escapeHtml(c.cliente_nombre)}${c.cliente_telefono ? `<br>Tel: ${escapeHtml(c.cliente_telefono)}` : \'\'}</p>\n    <div class="linea"></div>\n    <table>${filas}</table>\n    <div class="linea"></div>\n    <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">$${cot_fmt(total)}</td></tr></table>\n    <div class="linea"></div>\n    <p class="centro" style="font-size:10px;">Cotización informativa, sujeta a cambios.<br>Vigencia 15 días.</p>\n  </body></html>`;\n}\n\nfunction cot_abrirPassPRNT(c) {\n  const html = cot_construirHtmlRecibo(c);\n  const uri = `starpassprnt://v1/print/nopreview?back=${encodeURIComponent(window.location.href)}&html=${encodeURIComponent(html)}`;\n  window.location.href = uri;\n}\n\nasync function cot_imprimirBluetoothLista(id) {\n  try {\n    const c = await api(`/api/cotizaciones/${id}`);\n    cot_abrirPassPRNT(c);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nfunction cot_imprimirBluetoothActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  cot_sincronizarDesdeInputs();\n  cot_abrirPassPRNT(COT_ACTUAL);\n}\n\n// ---- Cotizaciones realizadas ----\n', "async function cot_descargarPdfLista(id, folio) {\n  try {\n    const r = await fetch(`/api/cotizaciones/${id}/pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error('No se pudo generar el PDF');\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url;\n    a.download = `cotizacion_${folio}.pdf`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nasync function cot_guardarCambiosActuales() {\n  // Antes de imprimir (PDF o Bluetooth), se guardan los cambios que haya en\n  // pantalla — si no, se imprimiría la última versión guardada, no lo que\n  // se está viendo/editando ahorita.\n  cot_sincronizarDesdeInputs();\n  const payload = {\n    cliente_nombre: COT_ACTUAL.cliente_nombre.trim(),\n    cliente_direccion: COT_ACTUAL.cliente_direccion || null,\n    cliente_telefono: COT_ACTUAL.cliente_telefono || null,\n    folio_microsip_origen: COT_ACTUAL.folio_microsip_origen || null,\n    notas: COT_ACTUAL.notas || null,\n    items: COT_ACTUAL.items.map(it => ({\n      articulo_id: it.articulo_id || null, clave: it.clave || null, nombre: it.nombre,\n      cantidad: Number(it.cantidad) || 0, precio_unitario: Number(it.precio_unitario) || 0,\n    })),\n  };\n  COT_ACTUAL = await api(`/api/cotizaciones/${COT_ACTUAL.id}`, { method: 'PUT', body: JSON.stringify(payload) });\n}\n\nasync function cot_descargarPdfActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  try {\n    await cot_guardarCambiosActuales();\n  } catch (e) {\n    alert('No se pudo guardar antes de imprimir: ' + e.message);\n    return;\n  }\n  cot_descargarPdfLista(COT_ACTUAL.id, COT_ACTUAL.folio);\n}\n\nfunction cot_abrirPassPRNT(id) {\n  api(`/api/cotizaciones/${id}/liga-impresion`, { method: 'POST' }).then(({ token }) => {\n    // Se manda una liga CORTA (url=) en vez del recibo completo incrustado en\n    // la liga — mandar el HTML entero como texto (html=) puede pasarse del\n    // límite de longitud que aceptan estas ligas, y el resultado es basura\n    // impresa (letras raras, tira de papel larguísima). PassPRNT va él solo\n    // a buscar el recibo a esa liga pública.\n    const reciboUrl = `${window.location.origin}/recibo-cotizacion/${token}`;\n    const uri = `starpassprnt://v1/print/nopreview?back=${encodeURIComponent(window.location.href)}&url=${encodeURIComponent(reciboUrl)}`;\n    window.location.href = uri;\n  }).catch(e => alert('No se pudo preparar la impresión: ' + e.message));\n}\n\nasync function cot_imprimirBluetoothLista(id) {\n  cot_abrirPassPRNT(id);\n}\n\nfunction cot_imprimirBluetoothActual() {\n  if (!COT_ACTUAL || !COT_ACTUAL.id) return;\n  cot_guardarCambiosActuales()\n    .then(() => cot_abrirPassPRNT(COT_ACTUAL.id))\n    .catch(e => alert('No se pudo guardar antes de imprimir: ' + e.message));\n}\n\n// ---- Cotizaciones realizadas ----\n"]]}

PDFS_COTIZACIONES_APPEND = '\n\ndef _escapar_html(texto):\n    return (\n        (texto or "")\n        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")\n        .replace(\'"\', "&quot;")\n    )\n\n\ndef _fmt_cant(n):\n    n = float(n or 0)\n    return f"{n:g}"\n\n\ndef generar_html_recibo_termico(cotizacion):\n    """Recibo angosto (58mm) para la impresora térmica Star SM-L200, servido\n    en la ruta pública que la app Star PassPRNT consulta directamente (no\n    lleva sesión ni token de la app — por eso nunca incluye datos sensibles\n    de más, solo lo mismo que ya trae la cotización). Se evitan caracteres\n    tipográficos poco comunes (guion en vez de punto medio, etc.) por si la\n    fuente de la impresora no los trae."""\n    filas = ""\n    total = 0.0\n    for item in cotizacion["items"]:\n        cantidad = float(item["cantidad"])\n        precio = float(item["precio_unitario"])\n        subtotal = cantidad * precio\n        total += subtotal\n        clave = f" ({_escapar_html(item[\'clave\'])})" if item.get("clave") else ""\n        filas += f"""\n          <tr>\n            <td style="text-align:left; padding:3px 0;">{_escapar_html(item[\'nombre\'])}{clave}<br>{_fmt_cant(cantidad)} x {_fmt_dinero(precio)}</td>\n            <td style="text-align:right; white-space:nowrap; padding:3px 0;">{_fmt_dinero(subtotal)}</td>\n          </tr>\n        """\n    telefono = f"<br>Tel: {_escapar_html(cotizacion[\'cliente_telefono\'])}" if cotizacion.get("cliente_telefono") else ""\n    return f"""<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>Cotizacion {_escapar_html(cotizacion[\'folio\'])}</title><style>\n  body {{ width:380px; margin:0; padding:8px; font-family:monospace; font-size:13px; color:#000; }}\n  h1 {{ font-size:16px; text-align:center; margin:4px 0; letter-spacing:1px; }}\n  .centro {{ text-align:center; margin:2px 0; }}\n  .linea {{ border-top:1px dashed #000; margin:8px 0; }}\n  table {{ width:100%; border-collapse:collapse; }}\n  .total td {{ font-size:15px; font-weight:bold; padding-top:6px; }}\n</style></head><body>\n  <h1>MARK - INC</h1>\n  <p class="centro">Cotizacion {_escapar_html(cotizacion[\'folio\'])}</p>\n  <div class="linea"></div>\n  <p><b>Cliente:</b> {_escapar_html(cotizacion[\'cliente_nombre\'])}{telefono}</p>\n  <div class="linea"></div>\n  <table>{filas}</table>\n  <div class="linea"></div>\n  <table><tr class="total"><td>TOTAL</td><td style="text-align:right;">{_fmt_dinero(total)}</td></tr></table>\n  <div class="linea"></div>\n  <p class="centro" style="font-size:10px;">Cotizacion informativa, sujeta a cambios.<br>Vigencia 15 dias.</p>\n</body></html>"""\n'


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    reemplazos = ARCHIVOS[ruta]
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in reemplazos:
        if nuevo in contenido:
            continue
        if viejo not in contenido:
            print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
            hubo_error = True
            continue
        contenido = contenido.replace(viejo, nuevo, 1)
        cambios += 1
    escribir(ruta, contenido)
    print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")
    return not hubo_error


def aplicar_pdfs_cotizaciones():
    ruta = "backend/pdfs_cotizaciones.py"
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    if PDFS_COTIZACIONES_APPEND.strip() in contenido:
        print(f"[{ruta}] Ya estaba aplicado. No hace falta nada.")
        return True
    contenido = contenido + PDFS_COTIZACIONES_APPEND
    escribir(ruta, contenido)
    print(f"[{ruta}] Funciones agregadas al final del archivo.")
    return True


def main():
    ok = True
    ok = aplicar_reemplazos("backend/db.py") and ok
    ok = aplicar_pdfs_cotizaciones() and ok
    ok = aplicar_reemplazos("backend/app.py") and ok
    ok = aplicar_reemplazos("frontend/index.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py backend/db.py backend/pdfs_cotizaciones.py frontend/index.html")
    print('   git commit -m "Fix impresion Bluetooth Star: liga corta en vez de recibo incrustado"')
    print("   git push")


if __name__ == "__main__":
    main()
