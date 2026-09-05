# -*- coding: utf-8 -*-
"""
Cotizador — estatus + bitácora + vigencia de 5 días hábiles + vista
filtrada (hoy y lo programado para hoy).

Qué hace:
1. Cada cotización tiene un ESTATUS (Creada, Cotización viva, Posible
   venta, Vendida, Perdida, Vencida) que puedes cambiar desde la lista.
2. BITÁCORA por cotización: queda registrado cada cambio de estatus y
   cada vez que se programa un seguimiento (quién y cuándo).
3. VIGENCIA de 5 días hábiles (lunes a viernes, sin calendario de
   festivos) calculada automáticamente al crear la cotización, y ahora sí
   se imprime la fecha real en el PDF (antes decía genérico "15 días").
4. La lista, por default, solo muestra lo de HOY (creadas hoy) y lo que
   tenga seguimiento PROGRAMADO para hoy — con un botón "Ver todas" para
   quitar ese filtro. Agrupado visualmente por estatus.
5. Si algo tiene seguimiento programado para hoy, sale un aviso arriba
   con un botón para abrir WhatsApp ya con el mensaje listo (reutiliza el
   mismo mecanismo que ya existía) — sigue sin ser 100% automático (eso
   necesitaría Twilio, ver conversación), pero ya no hay que ir a
   buscarla ni escribir nada.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_cotizador_estatus_bitacora.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/db.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    # 1) Migración: nuevas columnas + tabla de bitácora.
    [
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS token_impresion TEXT UNIQUE;\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS tipo_cliente TEXT NOT NULL DEFAULT 'publico';\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS meses_msi INTEGER;\n"
        "        ALTER TABLE cotizacion_items ADD COLUMN IF NOT EXISTS descuento_pct NUMERIC NOT NULL DEFAULT 0;\n"
        "        ALTER TABLE cotizacion_items ADD COLUMN IF NOT EXISTS nota TEXT;\n"
        "    \"\"\")\n"
        "    conn.commit()\n",

        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS token_impresion TEXT UNIQUE;\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS tipo_cliente TEXT NOT NULL DEFAULT 'publico';\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS meses_msi INTEGER;\n"
        "        ALTER TABLE cotizacion_items ADD COLUMN IF NOT EXISTS descuento_pct NUMERIC NOT NULL DEFAULT 0;\n"
        "        ALTER TABLE cotizacion_items ADD COLUMN IF NOT EXISTS nota TEXT;\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS estatus TEXT NOT NULL DEFAULT 'creada';\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS fecha_seguimiento DATE;\n"
        "        ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS vigencia_hasta DATE;\n"
        "\n"
        "        CREATE TABLE IF NOT EXISTS cotizacion_bitacora (\n"
        "            id SERIAL PRIMARY KEY,\n"
        "            cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,\n"
        "            usuario_id INTEGER REFERENCES users(id),\n"
        "            accion TEXT NOT NULL,\n"
        "            detalle TEXT,\n"
        "            fecha TEXT NOT NULL\n"
        "        );\n"
        "    \"\"\")\n"
        "    conn.commit()\n",
    ],
    # 2) Helper de vigencia hábil + funciones de estatus/seguimiento/bitácora,
    #    justo antes de _next_folio_cotizacion.
    [
        'def _next_folio_cotizacion(cur, empresa_id):',

        'NOMBRES_ESTATUS_COTIZACION = {\n'
        '    "creada": "Creada",\n'
        '    "viva": "Cotización viva",\n'
        '    "posible_venta": "Posible venta",\n'
        '    "vendida": "Vendida",\n'
        '    "perdida": "Perdida",\n'
        '    "vencida": "Vencida",\n'
        '}\n'
        '\n'
        '\n'
        'def _calcular_vigencia_habil(fecha_inicio, dias_habiles=5):\n'
        '    """Cuenta días hábiles (lunes a viernes, sin calendario de\n'
        '    festivos) a partir de fecha_inicio (date) y regresa la fecha límite."""\n'
        '    fecha = fecha_inicio\n'
        '    contados = 0\n'
        '    while contados < dias_habiles:\n'
        '        fecha += timedelta(days=1)\n'
        '        if fecha.weekday() < 5:\n'
        '            contados += 1\n'
        '    return fecha\n'
        '\n'
        '\n'
        'def _registrar_bitacora_cotizacion(cur, cotizacion_id, usuario_id, accion, detalle=None):\n'
        '    cur.execute(\n'
        '        "INSERT INTO cotizacion_bitacora (cotizacion_id, usuario_id, accion, detalle, fecha) VALUES (%s, %s, %s, %s, %s)",\n'
        '        (cotizacion_id, usuario_id, accion, detalle, ahora().isoformat(timespec="seconds")),\n'
        '    )\n'
        '\n'
        '\n'
        'def listar_bitacora_cotizacion(empresa_id, cotizacion_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n'
        '    if not cur.fetchone():\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    cur.execute("""\n'
        '        SELECT b.id, b.accion, b.detalle, b.fecha, u.nombre_completo AS usuario_nombre\n'
        '        FROM cotizacion_bitacora b\n'
        '        LEFT JOIN users u ON u.id = b.usuario_id\n'
        '        WHERE b.cotizacion_id = %s\n'
        '        ORDER BY b.id DESC\n'
        '    """, (cotizacion_id,))\n'
        '    filas = [dict(r) for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return filas\n'
        '\n'
        '\n'
        'def cambiar_estatus_cotizacion(empresa_id, cotizacion_id, usuario_id, estatus):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT estatus FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n'
        '    fila = cur.fetchone()\n'
        '    if not fila:\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    cur.execute("UPDATE cotizaciones SET estatus = %s, actualizado_en = %s WHERE id = %s",\n'
        '                (estatus, ahora().isoformat(timespec="seconds"), cotizacion_id))\n'
        '    nombre_anterior = NOMBRES_ESTATUS_COTIZACION.get(fila["estatus"], fila["estatus"])\n'
        '    nombre_nuevo = NOMBRES_ESTATUS_COTIZACION.get(estatus, estatus)\n'
        '    _registrar_bitacora_cotizacion(cur, cotizacion_id, usuario_id, "estatus", f"{nombre_anterior} → {nombre_nuevo}")\n'
        '    conn.commit()\n'
        '    resultado = obtener_cotizacion(empresa_id, cotizacion_id, _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        'def programar_seguimiento_cotizacion(empresa_id, cotizacion_id, usuario_id, fecha_seguimiento):\n'
        '    """fecha_seguimiento: \'YYYY-MM-DD\' o None para quitar el seguimiento."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id FROM cotizaciones WHERE id = %s AND empresa_id = %s", (cotizacion_id, empresa_id))\n'
        '    if not cur.fetchone():\n'
        '        cur.close(); conn.close()\n'
        '        return None\n'
        '    cur.execute("UPDATE cotizaciones SET fecha_seguimiento = %s, actualizado_en = %s WHERE id = %s",\n'
        '                (fecha_seguimiento, ahora().isoformat(timespec="seconds"), cotizacion_id))\n'
        '    detalle = f"Programado para {fecha_seguimiento}" if fecha_seguimiento else "Seguimiento quitado"\n'
        '    _registrar_bitacora_cotizacion(cur, cotizacion_id, usuario_id, "seguimiento", detalle)\n'
        '    conn.commit()\n'
        '    resultado = obtener_cotizacion(empresa_id, cotizacion_id, _conn_cur=(conn, cur))\n'
        '    cur.close(); conn.close()\n'
        '    return resultado\n'
        '\n'
        '\n'
        'def _next_folio_cotizacion(cur, empresa_id):',
    ],
    # 3) crear_cotizacion: calcular vigencia_hasta y dejar registro en
    #    bitácora al crearse.
    [
        '    cur.execute("""\n'
        '        INSERT INTO cotizaciones (empresa_id, folio, cliente_nombre, cliente_direccion, cliente_telefono,\n'
        '                                   folio_microsip_origen, notas, creado_por_id, creado_en, actualizado_en, tipo_cliente, meses_msi)\n'
        '        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)\n'
        '        RETURNING id\n'
        '    """, (empresa_id, folio, cliente_nombre, cliente_direccion, cliente_telefono,\n'
        '          folio_microsip_origen, notas, creado_por_id, ahora_iso, ahora_iso, tipo_cliente, meses_msi))\n'
        '    cotizacion_id = cur.fetchone()["id"]\n'
        '    _guardar_items_cotizacion(cur, cotizacion_id, items)\n'
        '    conn.commit()\n',

        '    vigencia_hasta = _calcular_vigencia_habil(ahora().date())\n'
        '    cur.execute("""\n'
        '        INSERT INTO cotizaciones (empresa_id, folio, cliente_nombre, cliente_direccion, cliente_telefono,\n'
        '                                   folio_microsip_origen, notas, creado_por_id, creado_en, actualizado_en, tipo_cliente, meses_msi,\n'
        '                                   vigencia_hasta)\n'
        '        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)\n'
        '        RETURNING id\n'
        '    """, (empresa_id, folio, cliente_nombre, cliente_direccion, cliente_telefono,\n'
        '          folio_microsip_origen, notas, creado_por_id, ahora_iso, ahora_iso, tipo_cliente, meses_msi,\n'
        '          vigencia_hasta))\n'
        '    cotizacion_id = cur.fetchone()["id"]\n'
        '    _guardar_items_cotizacion(cur, cotizacion_id, items)\n'
        '    _registrar_bitacora_cotizacion(cur, cotizacion_id, creado_por_id, "creada", f"Folio {folio}")\n'
        '    conn.commit()\n',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    # 1) Nuevos modelos, justo después de CotizacionIn.
    [
        'class CotizacionIn(BaseModel):\n'
        '    cliente_nombre: str = Field(min_length=1)\n'
        '    cliente_direccion: Optional[str] = None\n'
        '    cliente_telefono: Optional[str] = None\n'
        '    folio_microsip_origen: Optional[str] = None\n'
        '    notas: Optional[str] = None\n'
        '    tipo_cliente: Literal["publico", "mayoreo", "distribuidor"] = "publico"\n'
        '    meses_msi: Optional[int] = Field(default=None, ge=0, le=60)\n'
        '    items: List[CotizacionItemIn] = Field(default_factory=list)\n',

        'class CotizacionIn(BaseModel):\n'
        '    cliente_nombre: str = Field(min_length=1)\n'
        '    cliente_direccion: Optional[str] = None\n'
        '    cliente_telefono: Optional[str] = None\n'
        '    folio_microsip_origen: Optional[str] = None\n'
        '    notas: Optional[str] = None\n'
        '    tipo_cliente: Literal["publico", "mayoreo", "distribuidor"] = "publico"\n'
        '    meses_msi: Optional[int] = Field(default=None, ge=0, le=60)\n'
        '    items: List[CotizacionItemIn] = Field(default_factory=list)\n'
        '\n'
        '\n'
        'class EstatusCotizacionIn(BaseModel):\n'
        '    estatus: Literal["creada", "viva", "posible_venta", "vendida", "perdida", "vencida"]\n'
        '\n'
        '\n'
        'class SeguimientoCotizacionIn(BaseModel):\n'
        '    fecha_seguimiento: Optional[str] = None\n',
    ],
    # 2) Nuevos endpoints, justo antes de POST /api/cotizaciones.
    [
        '@app.post("/api/cotizaciones")\n'
        'def api_crear_cotizacion(payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):',

        '@app.patch("/api/cotizaciones/{cotizacion_id}/estatus")\n'
        'def api_cambiar_estatus_cotizacion(cotizacion_id: int, payload: EstatusCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n'
        '    if not existente:\n'
        '        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n'
        '    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:\n'
        '        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")\n'
        '    resultado = db.cambiar_estatus_cotizacion(usuario["empresa_id"], cotizacion_id, usuario["id"], payload.estatus)\n'
        '    return resultado\n'
        '\n'
        '\n'
        '@app.patch("/api/cotizaciones/{cotizacion_id}/seguimiento")\n'
        'def api_programar_seguimiento_cotizacion(cotizacion_id: int, payload: SeguimientoCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n'
        '    if not existente:\n'
        '        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n'
        '    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:\n'
        '        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")\n'
        '    resultado = db.programar_seguimiento_cotizacion(usuario["empresa_id"], cotizacion_id, usuario["id"], payload.fecha_seguimiento)\n'
        '    return resultado\n'
        '\n'
        '\n'
        '@app.get("/api/cotizaciones/{cotizacion_id}/bitacora")\n'
        'def api_bitacora_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n'
        '    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n'
        '    if not existente:\n'
        '        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n'
        '    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:\n'
        '        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")\n'
        '    return db.listar_bitacora_cotizacion(usuario["empresa_id"], cotizacion_id)\n'
        '\n'
        '\n'
        '@app.post("/api/cotizaciones")\n'
        'def api_crear_cotizacion(payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):',
    ],
]

# ---------------------------------------------------------------------------
# backend/pdfs_cotizaciones.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/pdfs_cotizaciones.py'] = [
    [
        '    elementos.append(Paragraph(\n'
        '        "Esta cotización es informativa y no representa una factura. Precios sujetos a cambio sin previo aviso; "\n'
        '        "vigencia de 15 días naturales salvo que se indique lo contrario.",\n'
        '        ParagraphStyle("Vigencia", parent=styles["Normal"], fontSize=7.5, textColor=GRIS),\n'
        '    ))',

        '    texto_vigencia = "Esta cotización es informativa y no representa una factura. Precios sujetos a cambio sin previo aviso."\n'
        '    if cotizacion.get("vigencia_hasta"):\n'
        '        texto_vigencia += f" Vigente hasta el {_formatear_fecha(str(cotizacion[\'vigencia_hasta\']))} (5 días hábiles)."\n'
        '    elementos.append(Paragraph(\n'
        '        texto_vigencia,\n'
        '        ParagraphStyle("Vigencia", parent=styles["Normal"], fontSize=7.5, textColor=GRIS),\n'
        '    ))',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        "async function renderCotizacionesRealizadas() {\n"
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        "  cont.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Cargando…</p>';\n"
        "  const cotizaciones = await api('/api/cotizaciones');\n"
        '  cont.innerHTML = `\n'
        '    <table class="users">\n'
        '      <thead><tr><th>Folio</th><th>Cliente</th><th>Fecha</th><th>Artículos</th><th>Total</th><th></th></tr></thead>\n'
        '      <tbody>\n'
        '        ${cotizaciones.map(c => `\n'
        '          <tr>\n'
        '            <td>${escapeHtml(c.folio)}${c.folio_microsip_origen ? `<br><span style="font-size:10px; color:var(--muted);">Microsip: ${escapeHtml(c.folio_microsip_origen)}</span>` : \'\'}</td>\n'
        '            <td>${escapeHtml(c.cliente_nombre)}</td>\n'
        "            <td>${escapeHtml((c.creado_en || '').slice(0, 10))}</td>\n"
        '            <td>${c.items.length}</td>\n'
        "            <td>$${cot_fmt(c.total)}</td>\n"
        '            <td style="white-space:nowrap;">\n'
        '              <button class="secondary" style="padding:4px 8px;" onclick="cot_editarCotizacion(${c.id})">Ver / editar</button>\n'
        "              <button class=\"secondary\" style=\"padding:4px 8px;\" onclick=\"cot_descargarPdfLista(${c.id}, '${escapeHtml(c.folio)}')\">📄 PDF</button>\n"
        '              <button class="secondary" style="padding:4px 8px;" onclick="cot_imprimirBluetoothLista(${c.id})">🖨️ Star</button>\n'
        '              <button class="secondary" style="padding:4px 8px;" onclick="cot_enviarWhatsAppLista(${c.id})">💬 WhatsApp</button>\n'
        '              <button class="secondary" style="padding:4px 8px; color:var(--copper); border-color:var(--copper);" onclick="cot_eliminarCotizacionUI(${c.id}, this)">Eliminar</button>\n'
        '            </td>\n'
        '          </tr>\n'
        "        `).join('') || `<tr><td colspan=\"6\" class=\"empty-col\">— todavía no hay cotizaciones guardadas —</td></tr>`}\n"
        '      </tbody>\n'
        '    </table>\n'
        '  `;\n'
        '}',

        "const NOMBRES_ESTATUS_COTIZACION = { creada: 'Creada', viva: 'Cotización viva', posible_venta: 'Posible venta', vendida: 'Vendida', perdida: 'Perdida', vencida: 'Vencida' };\n"
        "const COLORES_ESTATUS_COTIZACION = { creada: '#5B9BD5', viva: '#FFC000', posible_venta: '#9B59B6', vendida: 'var(--trace)', perdida: 'var(--copper)', vencida: 'var(--muted)' };\n"
        'let COT_LISTA_VER_TODAS = false;\n'
        '\n'
        'function _cotHoyISO() {\n'
        "  return new Date().toLocaleDateString('sv-SE');\n"
        '}\n'
        '\n'
        'function cot_alternarVerTodas() {\n'
        '  COT_LISTA_VER_TODAS = !COT_LISTA_VER_TODAS;\n'
        '  renderCotizacionesRealizadas();\n'
        '}\n'
        '\n'
        'async function cot_cambiarEstatusUI(id, estatus) {\n'
        '  try {\n'
        "    await api(`/api/cotizaciones/${id}/estatus`, { method: 'PATCH', body: JSON.stringify({ estatus }) });\n"
        '    await renderCotizacionesRealizadas();\n'
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        'async function cot_programarSeguimientoUI(id, fechaActual) {\n'
        "  const fecha = prompt('Programar seguimiento para (AAAA-MM-DD), o déjalo vacío para quitarlo:', fechaActual || _cotHoyISO());\n"
        '  if (fecha === null) return;\n'
        '  try {\n'
        "    await api(`/api/cotizaciones/${id}/seguimiento`, { method: 'PATCH', body: JSON.stringify({ fecha_seguimiento: fecha || null }) });\n"
        '    await renderCotizacionesRealizadas();\n'
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        'async function cot_verBitacoraUI(id, folio) {\n'
        '  try {\n'
        '    const entradas = await api(`/api/cotizaciones/${id}/bitacora`);\n'
        '    const texto = entradas.length\n'
        "      ? entradas.map(e => `${new Date(e.fecha).toLocaleString('es-MX')} — ${escapeHtml(e.usuario_nombre || 'Sistema')} — ${escapeHtml(e.detalle || e.accion)}`).join('\\n')\n"
        "      : 'Sin movimientos registrados.';\n"
        "    alert(`Bitácora de ${folio}:\\n\\n${texto}`);\n"
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        "async function renderCotizacionesRealizadas() {\n"
        "  const cont = document.getElementById('checadorPrecioContenido');\n"
        "  cont.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Cargando…</p>';\n"
        "  const todas = await api('/api/cotizaciones');\n"
        '  const hoy = _cotHoyISO();\n'
        '  const programadasHoy = todas.filter(c => c.fecha_seguimiento === hoy);\n'
        '  const cotizaciones = COT_LISTA_VER_TODAS\n'
        '    ? todas\n'
        "    : todas.filter(c => (c.creado_en || '').slice(0, 10) === hoy || c.fecha_seguimiento === hoy);\n"
        '\n'
        '  const porEstatus = {};\n'
        '  for (const c of cotizaciones) {\n'
        "    const est = c.estatus || 'creada';\n"
        '    (porEstatus[est] = porEstatus[est] || []).push(c);\n'
        '  }\n'
        '  const ordenEstatus = Object.keys(NOMBRES_ESTATUS_COTIZACION).filter(e => porEstatus[e]);\n'
        '\n'
        '  const filaCotizacion = (c) => `\n'
        '    <tr>\n'
        '      <td>${escapeHtml(c.folio)}${c.folio_microsip_origen ? `<br><span style="font-size:10px; color:var(--muted);">Microsip: ${escapeHtml(c.folio_microsip_origen)}</span>` : \'\'}</td>\n'
        '      <td>${escapeHtml(c.cliente_nombre)}</td>\n'
        "      <td>${escapeHtml((c.creado_en || '').slice(0, 10))}</td>\n"
        '      <td>${c.items.length}</td>\n'
        "      <td>$${cot_fmt(c.total)}</td>\n"
        '      <td>\n'
        '        <select onchange="cot_cambiarEstatusUI(${c.id}, this.value)" style="font-size:11px; padding:3px;">\n'
        "          ${Object.keys(NOMBRES_ESTATUS_COTIZACION).map(e => `<option value=\"${e}\" ${e===(c.estatus||'creada')?'selected':''}>${NOMBRES_ESTATUS_COTIZACION[e]}</option>`).join('')}\n"
        '        </select>\n'
        '      </td>\n'
        '      <td style="white-space:nowrap; font-size:11px;">\n'
        "        ${c.fecha_seguimiento ? `📅 ${escapeHtml(c.fecha_seguimiento)}` : '—'}\n"
        "        <button class=\"secondary\" style=\"padding:2px 6px; font-size:10px;\" onclick=\"cot_programarSeguimientoUI(${c.id}, ${c.fecha_seguimiento ? `'${c.fecha_seguimiento}'` : 'null'})\">${c.fecha_seguimiento ? 'cambiar' : 'programar'}</button>\n"
        '      </td>\n'
        '      <td style="white-space:nowrap;">\n'
        '        <button class="secondary" style="padding:4px 8px;" onclick="cot_editarCotizacion(${c.id})">Ver / editar</button>\n'
        "        <button class=\"secondary\" style=\"padding:4px 8px;\" onclick=\"cot_descargarPdfLista(${c.id}, '${escapeHtml(c.folio)}')\">📄 PDF</button>\n"
        '        <button class="secondary" style="padding:4px 8px;" onclick="cot_imprimirBluetoothLista(${c.id})">🖨️ Star</button>\n'
        '        <button class="secondary" style="padding:4px 8px;" onclick="cot_enviarWhatsAppLista(${c.id})">💬 WhatsApp</button>\n'
        "        <button class=\"secondary\" style=\"padding:4px 8px;\" onclick=\"cot_verBitacoraUI(${c.id}, '${escapeHtml(c.folio)}')\">🕓 Bitácora</button>\n"
        '        <button class="secondary" style="padding:4px 8px; color:var(--copper); border-color:var(--copper);" onclick="cot_eliminarCotizacionUI(${c.id}, this)">Eliminar</button>\n'
        '      </td>\n'
        '    </tr>\n'
        '  `;\n'
        '\n'
        '  cont.innerHTML = `\n'
        '    ${programadasHoy.length ? `\n'
        '      <div style="border:1px solid var(--copper); border-radius:6px; padding:10px 14px; margin-bottom:14px;">\n'
        '        <b style="color:var(--copper);">📌 ${programadasHoy.length} cotización(es) con seguimiento programado para hoy:</b>\n'
        '        <div style="margin-top:6px; display:flex; flex-wrap:wrap; gap:8px;">\n'
        '          ${programadasHoy.map(c => `\n'
        '            <div style="display:flex; align-items:center; gap:6px; font-size:12px; border:1px solid rgba(155,157,159,0.3); border-radius:6px; padding:4px 8px;">\n'
        '              <span>${escapeHtml(c.folio)} — ${escapeHtml(c.cliente_nombre)}</span>\n'
        '              <button class="secondary" style="padding:2px 8px; font-size:11px;" onclick="cot_enviarWhatsAppLista(${c.id})">💬 Enviar</button>\n'
        '            </div>\n'
        "          `).join('')}\n"
        '        </div>\n'
        '      </div>\n'
        "    ` : ''}\n"
        '    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">\n'
        '      <p style="font-size:12px; color:var(--muted); margin:0;">${COT_LISTA_VER_TODAS ? `Mostrando todas (${cotizaciones.length})` : `Mostrando lo de hoy y lo programado para hoy (${cotizaciones.length})`}</p>\n'
        '      <button class="secondary" style="padding:5px 12px; font-size:12px;" onclick="cot_alternarVerTodas()">${COT_LISTA_VER_TODAS ? \'Ver solo hoy\' : \'Ver todas\'}</button>\n'
        '    </div>\n'
        '    ${cotizaciones.length ? ordenEstatus.map(est => `\n'
        '      <div style="margin-bottom:18px;">\n'
        '        <h3 style="margin:0 0 6px; font-size:14px; color:${COLORES_ESTATUS_COTIZACION[est] || \'var(--text)\'};">${NOMBRES_ESTATUS_COTIZACION[est]} (${porEstatus[est].length})</h3>\n'
        '        <div style="overflow-x:auto;">\n'
        '          <table class="users">\n'
        '            <thead><tr><th>Folio</th><th>Cliente</th><th>Fecha</th><th>Artículos</th><th>Total</th><th>Estatus</th><th>Seguimiento</th><th></th></tr></thead>\n'
        "            <tbody>${porEstatus[est].map(filaCotizacion).join('')}</tbody>\n"
        '          </table>\n'
        '        </div>\n'
        '      </div>\n'
        "    `).join('') : `<p class=\"empty-col\">— sin cotizaciones con este filtro —</p>`}\n"
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
            print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print(f"[{ruta}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
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
    print("   git add backend/db.py backend/app.py backend/pdfs_cotizaciones.py frontend/index.html")
    print('   git commit -m "Cotizador: estatus, bitacora, vigencia habil, filtro de hoy"')
    print("   git push")


if __name__ == "__main__":
    main()
