# -*- coding: utf-8 -*-
"""
Promociones dentro de Checador de precio.

Que hace:
1. Nueva pestana "Promociones": crear/editar promociones con nombre,
   descripcion, una imagen de referencia (ej. la que vieron en Facebook),
   y una lista de articulos con un PRECIO ESPECIAL propio (no el de
   Microsip).
2. En el Cotizador, una caja nueva "Aplicar promocion": eliges una por
   nombre y se agregan de golpe todos sus articulos (con el precio de la
   promocion) a la cotizacion que estas armando.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_promociones.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS['backend/db.py'] = [
    [
        'CREATE TABLE IF NOT EXISTS cotizacion_items (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,\n'
        '            articulo_id INTEGER,\n'
        '            clave TEXT,\n'
        '            nombre TEXT NOT NULL,\n'
        '            cantidad NUMERIC NOT NULL DEFAULT 1,\n'
        '            precio_unitario NUMERIC NOT NULL DEFAULT 0,\n'
        '            orden INTEGER NOT NULL DEFAULT 0,\n'
        '            descuento_pct NUMERIC NOT NULL DEFAULT 0,\n'
        '            nota TEXT\n'
        '        );\n',

        'CREATE TABLE IF NOT EXISTS cotizacion_items (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,\n'
        '            articulo_id INTEGER,\n'
        '            clave TEXT,\n'
        '            nombre TEXT NOT NULL,\n'
        '            cantidad NUMERIC NOT NULL DEFAULT 1,\n'
        '            precio_unitario NUMERIC NOT NULL DEFAULT 0,\n'
        '            orden INTEGER NOT NULL DEFAULT 0,\n'
        '            descuento_pct NUMERIC NOT NULL DEFAULT 0,\n'
        '            nota TEXT\n'
        '        );\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS promociones (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n'
        '            nombre TEXT NOT NULL,\n'
        '            descripcion TEXT,\n'
        '            imagen_base64 TEXT,\n'
        '            activa BOOLEAN NOT NULL DEFAULT TRUE,\n'
        '            creado_por_id INTEGER REFERENCES users(id),\n'
        '            creado_en TEXT NOT NULL,\n'
        '            actualizado_en TEXT NOT NULL\n'
        '        );\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS promocion_items (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            promocion_id INTEGER NOT NULL REFERENCES promociones(id) ON DELETE CASCADE,\n'
        '            articulo_id INTEGER,\n'
        '            clave TEXT,\n'
        '            nombre TEXT NOT NULL,\n'
        '            cantidad NUMERIC NOT NULL DEFAULT 1,\n'
        '            precio_promocional NUMERIC NOT NULL DEFAULT 0,\n'
        '            orden INTEGER NOT NULL DEFAULT 0\n'
        '        );\n',
    ],
    [
        'def obtener_cotizacion_por_token_impresion(token):\n'
        '    """Para la ruta pública que consulta la app Star PassPRNT (sin login)."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id, empresa_id FROM cotizaciones WHERE token_impresion = %s", (token,))\n'
        '    fila = cur.fetchone()\n'
        '    if not fila:\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    resultado = obtener_cotizacion(fila["empresa_id"], fila["id"], _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n',

        'def obtener_cotizacion_por_token_impresion(token):\n'
        '    """Para la ruta pública que consulta la app Star PassPRNT (sin login)."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id, empresa_id FROM cotizaciones WHERE token_impresion = %s", (token,))\n'
        '    fila = cur.fetchone()\n'
        '    if not fila:\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    resultado = obtener_cotizacion(fila["empresa_id"], fila["id"], _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        '# ---- Promociones ----\n'
        '\n'
        'def _guardar_items_promocion(cur, promocion_id, items):\n'
        '    cur.execute("DELETE FROM promocion_items WHERE promocion_id = %s", (promocion_id,))\n'
        '    for i, item in enumerate(items):\n'
        '        cur.execute("""\n'
        '            INSERT INTO promocion_items (promocion_id, articulo_id, clave, nombre, cantidad, precio_promocional, orden)\n'
        '            VALUES (%s, %s, %s, %s, %s, %s, %s)\n'
        '        """, (promocion_id, item.get("articulo_id"), item.get("clave"), item["nombre"],\n'
        '              item["cantidad"], item["precio_promocional"], i))\n'
        '\n'
        '\n'
        'def _enriquecer_promocion(cur, promocion):\n'
        '    cur.execute("""\n'
        '        SELECT id, articulo_id, clave, nombre, cantidad, precio_promocional\n'
        '        FROM promocion_items WHERE promocion_id = %s ORDER BY orden\n'
        '    """, (promocion["id"],))\n'
        '    promocion["items"] = [dict(r) for r in cur.fetchall()]\n'
        '    return promocion\n'
        '\n'
        '\n'
        'def crear_promocion(empresa_id, creado_por_id, nombre, descripcion, imagen_base64, items):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    ahora_iso = ahora().isoformat(timespec="seconds")\n'
        '    cur.execute("""\n'
        '        INSERT INTO promociones (empresa_id, nombre, descripcion, imagen_base64, creado_por_id, creado_en, actualizado_en)\n'
        '        VALUES (%s, %s, %s, %s, %s, %s, %s)\n'
        '        RETURNING id\n'
        '    """, (empresa_id, nombre, descripcion, imagen_base64, creado_por_id, ahora_iso, ahora_iso))\n'
        '    promocion_id = cur.fetchone()["id"]\n'
        '    _guardar_items_promocion(cur, promocion_id, items)\n'
        '    conn.commit()\n'
        '    resultado = obtener_promocion(empresa_id, promocion_id, _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        'def listar_promociones(empresa_id, solo_activas=False):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    query = "SELECT * FROM promociones WHERE empresa_id = %s"\n'
        '    params = [empresa_id]\n'
        '    if solo_activas:\n'
        '        query += " AND activa = TRUE"\n'
        '    query += " ORDER BY id DESC"\n'
        '    cur.execute(query, params)\n'
        '    promociones = [dict(r) for r in cur.fetchall()]\n'
        '    for p in promociones:\n'
        '        _enriquecer_promocion(cur, p)\n'
        '    cur.close(); conn.close()\n'
        '    return promociones\n'
        '\n'
        '\n'
        'def obtener_promocion(empresa_id, promocion_id, _conn_cur=None):\n'
        '    conn, cur = _conn_cur if _conn_cur else (get_connection(), None)\n'
        '    if cur is None:\n'
        '        cur = conn.cursor()\n'
        '    cur.execute("SELECT * FROM promociones WHERE id = %s AND empresa_id = %s", (promocion_id, empresa_id))\n'
        '    row = cur.fetchone()\n'
        '    resultado = _enriquecer_promocion(cur, dict(row)) if row else None\n'
        '    if not _conn_cur:\n'
        '        cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        'def actualizar_promocion(empresa_id, promocion_id, nombre, descripcion, imagen_base64, items, activa=True):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id FROM promociones WHERE id = %s AND empresa_id = %s", (promocion_id, empresa_id))\n'
        '    if not cur.fetchone():\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    cur.execute("""\n'
        '        UPDATE promociones SET nombre = %s, descripcion = %s, imagen_base64 = %s, activa = %s, actualizado_en = %s\n'
        '        WHERE id = %s\n'
        '    """, (nombre, descripcion, imagen_base64, activa, ahora().isoformat(timespec="seconds"), promocion_id))\n'
        '    _guardar_items_promocion(cur, promocion_id, items)\n'
        '    conn.commit()\n'
        '    resultado = obtener_promocion(empresa_id, promocion_id, _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        'def eliminar_promocion(empresa_id, promocion_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("DELETE FROM promociones WHERE id = %s AND empresa_id = %s", (promocion_id, empresa_id))\n'
        '    eliminado = cur.rowcount > 0\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '    return eliminado\n',
    ],
]

ARCHIVOS['backend/app.py'] = [
    [
        '@app.get("/api/cotizaciones/microsip/{folio}")',

        'class PromocionItemIn(BaseModel):\n'
        '    articulo_id: Optional[int] = None\n'
        '    clave: Optional[str] = None\n'
        '    nombre: str = Field(min_length=1)\n'
        '    cantidad: float = Field(gt=0)\n'
        '    precio_promocional: float = Field(ge=0)\n'
        '\n'
        '\n'
        'class PromocionIn(BaseModel):\n'
        '    nombre: str = Field(min_length=1)\n'
        '    descripcion: Optional[str] = None\n'
        '    imagen_base64: Optional[str] = None\n'
        '    activa: bool = True\n'
        '    items: List[PromocionItemIn] = Field(default_factory=list)\n'
        '\n'
        '\n'
        '@app.get("/api/promociones")\n'
        'def api_listar_promociones(activas: Optional[bool] = None, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    return db.listar_promociones(usuario["empresa_id"], solo_activas=bool(activas))\n'
        '\n'
        '\n'
        '@app.get("/api/promociones/{promocion_id}")\n'
        'def api_obtener_promocion(promocion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    promo = db.obtener_promocion(usuario["empresa_id"], promocion_id)\n'
        '    if not promo:\n'
        '        raise HTTPException(status_code=404, detail="Promocion no encontrada")\n'
        '    return promo\n'
        '\n'
        '\n'
        '@app.post("/api/promociones")\n'
        'def api_crear_promocion(payload: PromocionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    return db.crear_promocion(usuario["empresa_id"], usuario["id"], payload.nombre, payload.descripcion,\n'
        '                               payload.imagen_base64, [item.model_dump() for item in payload.items])\n'
        '\n'
        '\n'
        '@app.put("/api/promociones/{promocion_id}")\n'
        'def api_actualizar_promocion(promocion_id: int, payload: PromocionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    resultado = db.actualizar_promocion(usuario["empresa_id"], promocion_id, payload.nombre, payload.descripcion,\n'
        '                                         payload.imagen_base64, [item.model_dump() for item in payload.items], payload.activa)\n'
        '    if not resultado:\n'
        '        raise HTTPException(status_code=404, detail="Promocion no encontrada")\n'
        '    return resultado\n'
        '\n'
        '\n'
        '@app.delete("/api/promociones/{promocion_id}")\n'
        'def api_eliminar_promocion(promocion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    if not db.eliminar_promocion(usuario["empresa_id"], promocion_id):\n'
        '        raise HTTPException(status_code=404, detail="Promocion no encontrada")\n'
        '    return {"ok": True}\n'
        '\n'
        '\n'
        '@app.get("/api/cotizaciones/microsip/{folio}")',
    ],
]

ARCHIVOS['frontend/index.html'] = [
    [
        '      <button class="admin-tab" id="tabCPRealizadas" onclick="cambiarChecadorPrecioTab(\'realizadas\')">\U0001F4CB Cotizaciones realizadas</button>',

        '      <button class="admin-tab" id="tabCPRealizadas" onclick="cambiarChecadorPrecioTab(\'realizadas\')">\U0001F4CB Cotizaciones realizadas</button>\n'
        '      <button class="admin-tab" id="tabCPPromos" onclick="cambiarChecadorPrecioTab(\'promos\')">\U0001F3F7\uFE0F Promociones</button>',
    ],
    [
        "async function cambiarChecadorPrecioTab(tab) {\n"
        '  detenerEscaneoChecadorPrecio();\n'
        '  CP_TAB = tab;\n'
        "  document.getElementById('tabCPBuscar').classList.toggle('active', tab === 'buscar');\n"
        "  document.getElementById('tabCPCotizador').classList.toggle('active', tab === 'cotizador');\n"
        "  document.getElementById('tabCPRealizadas').classList.toggle('active', tab === 'realizadas');\n"
        "  if (tab === 'buscar') {\n"
        '    renderFormularioChecadorPrecio();\n'
        "  } else if (tab === 'cotizador') {\n"
        '    renderCotizadorNueva();\n'
        '  } else {\n'
        '    await renderCotizacionesRealizadas();\n'
        '  }\n'
        '}',

        "async function cambiarChecadorPrecioTab(tab) {\n"
        '  detenerEscaneoChecadorPrecio();\n'
        '  CP_TAB = tab;\n'
        "  document.getElementById('tabCPBuscar').classList.toggle('active', tab === 'buscar');\n"
        "  document.getElementById('tabCPCotizador').classList.toggle('active', tab === 'cotizador');\n"
        "  document.getElementById('tabCPRealizadas').classList.toggle('active', tab === 'realizadas');\n"
        "  document.getElementById('tabCPPromos').classList.toggle('active', tab === 'promos');\n"
        "  if (tab === 'buscar') {\n"
        '    renderFormularioChecadorPrecio();\n'
        "  } else if (tab === 'cotizador') {\n"
        '    await renderCotizadorNueva();\n'
        "  } else if (tab === 'promos') {\n"
        '    await renderPromocionesLista();\n'
        '  } else {\n'
        '    await renderCotizacionesRealizadas();\n'
        '  }\n'
        '}',
    ],
    [
        'function renderCotizadorNueva() {\n'
        '  COT_ACTUAL = cot_nuevaVacia();\n'
        '  renderCotizadorForm();\n'
        '}',

        'let COT_PROMOS_DISPONIBLES = [];\n'
        '\n'
        'async function cot_cargarPromosDisponibles() {\n'
        '  try {\n'
        "    COT_PROMOS_DISPONIBLES = await api('/api/promociones?activas=true');\n"
        '  } catch (e) {\n'
        '    COT_PROMOS_DISPONIBLES = [];\n'
        '  }\n'
        '}\n'
        '\n'
        'async function cot_aplicarPromocionUI() {\n'
        "  const select = document.getElementById('cot_promo_select');\n"
        '  const promoId = parseInt(select.value);\n'
        '  if (!promoId) return;\n'
        '  const promo = COT_PROMOS_DISPONIBLES.find(p => p.id === promoId);\n'
        '  if (!promo || !promo.items.length) return;\n'
        '  cot_sincronizarDesdeInputs();\n'
        '  for (const it of promo.items) {\n'
        '    COT_ACTUAL.items.push({\n'
        '      articulo_id: it.articulo_id, clave: it.clave, nombre: it.nombre,\n'
        '      cantidad: it.cantidad, precio_unitario: it.precio_promocional, descuento_pct: 0,\n'
        '      nota: `Promo: ${promo.nombre}`,\n'
        '    });\n'
        '  }\n'
        '  renderCotizadorForm();\n'
        '}\n'
        '\n'
        'async function renderCotizadorNueva() {\n'
        '  COT_ACTUAL = cot_nuevaVacia();\n'
        '  await cot_cargarPromosDisponibles();\n'
        '  renderCotizadorForm();\n'
        '}',
    ],
    [
        "async function cot_editarCotizacion(id) {\n"
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        "  cont.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Cargando\u2026</p>';\n"
        '  try {\n'
        '    COT_ACTUAL = await api(`/api/cotizaciones/${id}`);\n'
        "    CP_TAB = 'cotizador';\n"
        "    document.getElementById('tabCPBuscar').classList.remove('active');\n"
        "    document.getElementById('tabCPCotizador').classList.add('active');\n"
        "    document.getElementById('tabCPRealizadas').classList.remove('active');\n"
        '    renderCotizadorForm();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}',

        "async function cot_editarCotizacion(id) {\n"
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        "  cont.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Cargando\u2026</p>';\n"
        '  try {\n'
        '    COT_ACTUAL = await api(`/api/cotizaciones/${id}`);\n'
        "    CP_TAB = 'cotizador';\n"
        "    document.getElementById('tabCPBuscar').classList.remove('active');\n"
        "    document.getElementById('tabCPCotizador').classList.add('active');\n"
        "    document.getElementById('tabCPRealizadas').classList.remove('active');\n"
        "    document.getElementById('tabCPPromos').classList.remove('active');\n"
        '    await cot_cargarPromosDisponibles();\n'
        '    renderCotizadorForm();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}',
    ],
    [
        '      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:6px;">\n'
        '        <div style="border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:12px;">\n'
        '          <label style="font-size:11px; color:var(--muted); text-transform:uppercase;">Agregar art\u00edculo de Microsip</label>',

        '      ${COT_PROMOS_DISPONIBLES.length ? `\n'
        '        <div style="border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:12px; margin-top:10px;">\n'
        '          <label style="font-size:11px; color:var(--muted); text-transform:uppercase;">\U0001F3F7\uFE0F Aplicar promoci\u00f3n</label>\n'
        '          <div style="display:flex; gap:6px; margin-top:8px;">\n'
        '            <select id="cot_promo_select" style="flex:1;">\n'
        '              <option value="">Elige una promoci\u00f3n\u2026</option>\n'
        "              ${COT_PROMOS_DISPONIBLES.map(p => `<option value=\"${p.id}\">${escapeHtml(p.nombre)} (${p.items.length} art\u00edculo(s))</option>`).join('')}\n"
        '            </select>\n'
        '            <button type="button" class="secondary" onclick="cot_aplicarPromocionUI()">Agregar art\u00edculos</button>\n'
        '          </div>\n'
        '        </div>\n'
        "      ` : ''}\n"
        '      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:6px;">\n'
        '        <div style="border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:12px;">\n'
        '          <label style="font-size:11px; color:var(--muted); text-transform:uppercase;">Agregar art\u00edculo de Microsip</label>',
    ],
    [
        "async function cot_eliminarCotizacionUI(id, boton) {\n"
        "  if (!confirm('\u00bfEliminar esta cotizaci\u00f3n? No se puede deshacer.')) return;\n"
        '  await conBloqueoDeBoton(boton, async () => {\n'
        '    try {\n'
        "      await api(`/api/cotizaciones/${id}`, { method: 'DELETE' });\n"
        '      await renderCotizacionesRealizadas();\n'
        '    } catch (e) {\n'
        '      alert(e.message);\n'
        '    }\n'
        '  });\n'
        '}',

        "async function cot_eliminarCotizacionUI(id, boton) {\n"
        "  if (!confirm('\u00bfEliminar esta cotizaci\u00f3n? No se puede deshacer.')) return;\n"
        '  await conBloqueoDeBoton(boton, async () => {\n'
        '    try {\n'
        "      await api(`/api/cotizaciones/${id}`, { method: 'DELETE' });\n"
        '      await renderCotizacionesRealizadas();\n'
        '    } catch (e) {\n'
        '      alert(e.message);\n'
        '    }\n'
        '  });\n'
        '}\n'
        '\n'
        '// ---- Promociones ----\n'
        '\n'
        'let PROMO_ACTUAL = null;\n'
        '\n'
        'function promo_nuevaVacia() {\n'
        "  return { id: null, nombre: '', descripcion: '', imagen_base64: null, activa: true, items: [] };\n"
        '}\n'
        '\n'
        'async function renderPromocionesLista() {\n'
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando\u2026</p>\';\n'
        "  const promociones = await api('/api/promociones');\n"
        '  cont.innerHTML = `\n'
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">\n'
        '      <h3 style="margin:0;">Promociones</h3>\n'
        '      <button class="primary" onclick="promo_nueva()">+ Nueva promoci\u00f3n</button>\n'
        '    </div>\n'
        '    <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:14px;">\n'
        '      ${promociones.map(p => `\n'
        "        <div style=\"border:1px solid rgba(155,157,159,0.3); border-radius:8px; overflow:hidden; ${p.activa ? '' : 'opacity:0.5;'}\">\n"
        "          ${p.imagen_base64 ? `<img src=\"${p.imagen_base64}\" style=\"width:100%; height:140px; object-fit:cover; display:block;\" />` : `<div style=\"width:100%; height:140px; background:rgba(155,157,159,0.15); display:flex; align-items:center; justify-content:center; color:var(--muted); font-size:12px;\">Sin imagen</div>`}\n"
        '          <div style="padding:10px;">\n'
        "            <b>${escapeHtml(p.nombre)}</b>${p.activa ? '' : ' <span style=\"font-size:10px; color:var(--muted);\">(inactiva)</span>'}\n"
        '            <p style="font-size:11px; color:var(--muted); margin:4px 0;">${p.items.length} art\u00edculo(s)</p>\n'
        '            <div style="display:flex; gap:6px;">\n'
        '              <button class="secondary" style="flex:1; padding:5px;" onclick="promo_editar(${p.id})">Editar</button>\n'
        '              <button class="secondary" style="padding:5px 8px; color:var(--copper); border-color:var(--copper);" onclick="promo_eliminarUI(${p.id}, this)">\U0001F5D1\uFE0F</button>\n'
        '            </div>\n'
        '          </div>\n'
        '        </div>\n'
        "      `).join('') || `<p class=\"empty-col\">\u2014 sin promociones todav\u00eda \u2014</p>`}\n"
        '    </div>\n'
        '  `;\n'
        '}\n'
        '\n'
        'function promo_nueva() {\n'
        '  PROMO_ACTUAL = promo_nuevaVacia();\n'
        '  renderPromocionForm();\n'
        '}\n'
        '\n'
        'async function promo_editar(id) {\n'
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        '  cont.innerHTML = \'<p style="font-size:12px; color:var(--muted);">Cargando\u2026</p>\';\n'
        '  try {\n'
        '    PROMO_ACTUAL = await api(`/api/promociones/${id}`);\n'
        '    renderPromocionForm();\n'
        '  } catch (e) {\n'
        '    cont.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '  }\n'
        '}\n'
        '\n'
        'function promo_sincronizarDesdeInputs() {\n'
        '  const p = PROMO_ACTUAL;\n'
        "  p.nombre = document.getElementById('promo_nombre')?.value || '';\n"
        "  p.descripcion = document.getElementById('promo_descripcion')?.value || '';\n"
        "  p.activa = document.getElementById('promo_activa')?.checked ?? true;\n"
        '  p.items.forEach((it, i) => {\n'
        '    const nombreEl = document.getElementById(`promo_item_nombre_${i}`);\n'
        '    const cantEl = document.getElementById(`promo_item_cant_${i}`);\n'
        '    const precioEl = document.getElementById(`promo_item_precio_${i}`);\n'
        '    if (nombreEl) it.nombre = nombreEl.value;\n'
        '    if (cantEl) it.cantidad = parseFloat(cantEl.value) || 0;\n'
        '    if (precioEl) it.precio_promocional = parseFloat(precioEl.value) || 0;\n'
        '  });\n'
        '}\n'
        '\n'
        'function promo_quitarItem(i) {\n'
        '  promo_sincronizarDesdeInputs();\n'
        '  PROMO_ACTUAL.items.splice(i, 1);\n'
        '  renderPromocionForm();\n'
        '}\n'
        '\n'
        'function promo_agregarItemManual() {\n'
        "  const nombre = document.getElementById('promo_add_nombre').value.trim();\n"
        "  const cantidad = parseFloat(document.getElementById('promo_add_cantidad').value) || 1;\n"
        "  const precio = parseFloat(document.getElementById('promo_add_precio').value) || 0;\n"
        "  if (!nombre) { document.getElementById('promo_add_nombre').focus(); return; }\n"
        '  promo_sincronizarDesdeInputs();\n'
        '  PROMO_ACTUAL.items.push({ articulo_id: null, clave: null, nombre, cantidad, precio_promocional: precio });\n'
        '  renderPromocionForm();\n'
        '}\n'
        '\n'
        'function promo_subirImagen(input) {\n'
        '  const archivo = input.files[0];\n'
        '  if (!archivo) return;\n'
        '  const lector = new FileReader();\n'
        '  lector.onload = (e) => {\n'
        '    const img = new Image();\n'
        '    img.onload = () => {\n'
        '      const maxAncho = 800;\n'
        '      const escala = Math.min(1, maxAncho / img.width);\n'
        "      const canvas = document.createElement('canvas');\n"
        '      canvas.width = img.width * escala;\n'
        '      canvas.height = img.height * escala;\n'
        "      const ctx = canvas.getContext('2d');\n"
        '      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);\n'
        "      PROMO_ACTUAL.imagen_base64 = canvas.toDataURL('image/jpeg', 0.82);\n"
        '      renderPromocionForm();\n'
        '    };\n'
        '    img.src = e.target.result;\n'
        '  };\n'
        '  lector.readAsDataURL(archivo);\n'
        '}\n'
        '\n'
        'async function promo_guardarUI(boton) {\n'
        '  promo_sincronizarDesdeInputs();\n'
        "  const errDiv = document.getElementById('promo_guardar_error');\n"
        "  errDiv.innerHTML = '';\n"
        '  if (!PROMO_ACTUAL.nombre.trim()) {\n'
        '    errDiv.innerHTML = \'<p style="font-size:12px; color:var(--copper);">Falta el nombre de la promoci\u00f3n.</p>\';\n'
        '    return;\n'
        '  }\n'
        '  await conBloqueoDeBoton(boton, async () => {\n'
        '    try {\n'
        '      const payload = {\n'
        '        nombre: PROMO_ACTUAL.nombre, descripcion: PROMO_ACTUAL.descripcion || null,\n'
        '        imagen_base64: PROMO_ACTUAL.imagen_base64 || null, activa: PROMO_ACTUAL.activa !== false,\n'
        '        items: PROMO_ACTUAL.items.map(it => ({\n'
        '          articulo_id: it.articulo_id, clave: it.clave, nombre: it.nombre,\n'
        '          cantidad: it.cantidad, precio_promocional: it.precio_promocional,\n'
        '        })),\n'
        '      };\n'
        '      if (PROMO_ACTUAL.id) {\n'
        "        PROMO_ACTUAL = await api(`/api/promociones/${PROMO_ACTUAL.id}`, { method: 'PUT', body: JSON.stringify(payload) });\n"
        '      } else {\n'
        "        PROMO_ACTUAL = await api('/api/promociones', { method: 'POST', body: JSON.stringify(payload) });\n"
        '      }\n'
        '      await renderPromocionesLista();\n'
        '    } catch (e) {\n'
        '      errDiv.innerHTML = `<p style="font-size:12px; color:var(--copper);">${escapeHtml(e.message)}</p>`;\n'
        '    }\n'
        '  });\n'
        '}\n'
        '\n'
        'async function promo_eliminarUI(id, boton) {\n'
        "  if (!confirm('\u00bfEliminar esta promoci\u00f3n? No se puede deshacer.')) return;\n"
        '  await conBloqueoDeBoton(boton, async () => {\n'
        '    try {\n'
        "      await api(`/api/promociones/${id}`, { method: 'DELETE' });\n"
        '      await renderPromocionesLista();\n'
        '    } catch (e) {\n'
        '      alert(e.message);\n'
        '    }\n'
        '  });\n'
        '}\n'
        '\n'
        'function renderPromocionForm() {\n'
        '  const p = PROMO_ACTUAL;\n'
        "  document.getElementById('checadorPrecioContenido').innerHTML = `\n"
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">\n'
        "      <h3 style=\"margin:0;\">${p.id ? 'Editando promoci\u00f3n' : 'Nueva promoci\u00f3n'}</h3>\n"
        '      <button class="secondary" onclick="renderPromocionesLista()">\u2190 Volver a promociones</button>\n'
        '    </div>\n'
        '    <div class="field"><label>Nombre *</label><input id="promo_nombre" value="${escapeHtml(p.nombre || \'\')}" /></div>\n'
        "    <div class=\"field\"><label>Descripci\u00f3n (opcional)</label><textarea id=\"promo_descripcion\">${escapeHtml(p.descripcion || '')}</textarea></div>\n"
        '    <label style="display:flex; align-items:center; gap:6px; font-size:13px; margin:10px 0;">\n'
        "      <input type=\"checkbox\" id=\"promo_activa\" ${p.activa !== false ? 'checked' : ''} /> Activa (disponible para aplicar en cotizaciones)\n"
        '    </label>\n'
        '    <div class="field">\n'
        '      <label>Imagen de referencia (ej. lo que vieron en Facebook)</label>\n'
        '      <input type="file" accept="image/*" onchange="promo_subirImagen(this)" />\n'
        "      ${p.imagen_base64 ? `<img src=\"${p.imagen_base64}\" style=\"max-width:280px; margin-top:8px; border-radius:6px; display:block;\" />` : ''}\n"
        '    </div>\n'
        '\n'
        '    <label style="font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:18px;">Art\u00edculos de la promoci\u00f3n</label>\n'
        '    <table class="users" style="margin-top:6px;">\n'
        '      <thead><tr><th>Art\u00edculo</th><th style="width:80px;">Cantidad</th><th style="width:120px;">Precio promo</th><th></th></tr></thead>\n'
        '      <tbody>\n'
        '        ${p.items.map((it, i) => `\n'
        '          <tr>\n'
        '            <td><input id="promo_item_nombre_${i}" value="${escapeHtml(it.nombre)}" style="width:100%;" /></td>\n'
        '            <td><input id="promo_item_cant_${i}" type="number" step="any" min="0" value="${it.cantidad}" style="width:100%;" /></td>\n'
        '            <td><input id="promo_item_precio_${i}" type="number" step="0.01" min="0" value="${it.precio_promocional}" style="width:100%;" /></td>\n'
        '            <td><button type="button" class="secondary" style="padding:4px 8px; color:var(--copper); border-color:var(--copper);" onclick="promo_quitarItem(${i})">\u2715</button></td>\n'
        '          </tr>\n'
        "        `).join('') || `<tr><td colspan=\"4\" class=\"empty-col\">\u2014 sin art\u00edculos todav\u00eda \u2014</td></tr>`}\n"
        '      </tbody>\n'
        '    </table>\n'
        '    <div style="display:flex; gap:6px; margin-top:8px;">\n'
        '      <input id="promo_add_nombre" autocomplete="off" placeholder="Nombre del art\u00edculo" style="flex:1;" />\n'
        '      <input id="promo_add_cantidad" type="number" step="any" min="0" value="1" placeholder="Cant." style="width:80px;" />\n'
        '      <input id="promo_add_precio" type="number" step="0.01" min="0" placeholder="Precio promo" style="width:110px;" />\n'
        '      <button type="button" class="secondary" onclick="promo_agregarItemManual()">Agregar</button>\n'
        '    </div>\n'
        '\n'
        '    <div id="promo_guardar_error" style="margin-top:10px;"></div>\n'
        "    <button class=\"primary\" style=\"width:100%; margin-top:14px;\" onclick=\"promo_guardarUI(this)\">${p.id ? 'Guardar cambios' : 'Crear promoci\u00f3n'}</button>\n"
        '  `;\n'
        '}',
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False
    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1
            else:
                print(f"[{ruta}] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/db.py backend/app.py frontend/index.html")
    print('   git commit -m "Modulo de Promociones dentro de Checador de precio"')
    print("   git push")


if __name__ == "__main__":
    main()
