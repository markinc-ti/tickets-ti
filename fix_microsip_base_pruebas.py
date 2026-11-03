# -*- coding: utf-8 -*-
"""
MICROSIP: BASE DE PRUEBAS POR MODULO (SOLO PARA QUIEN LA MARCA)
Administrar -> Microsip -> "Base de pruebas": ruta de la copia de Microsip
(opcional otro host/usuario) y casillas por modulo: Dashboard/consultas,
Inventarios, RH, Laboratorio, Checador/cotizador/CRM, Entregas.
- Solo TU quedas en pruebas en los modulos que marques (web y apps); todos
  los demas siguen en la base REAL al mismo tiempo.
- Lo automatico (respaldo de inventario, avisos, etc.), la configuracion y el
  explorador de Microsip siempre usan la REAL.
- Mientras estes en pruebas, arriba sale un aviso naranja con los modulos.
- "Todo a la real" te regresa en un clic.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_microsip_base_pruebas.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "import os\nimport secrets\nimport json\nimport re\nfrom datetime import date, datetime, timedelta\nfrom zoneinfo import ZoneInfo\n",
   "import os\nimport secrets\nimport json\nimport contextvars\nimport re\nfrom datetime import date, datetime, timedelta\nfrom zoneinfo import ZoneInfo\n"
  ],
  [
   "        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_activa BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_estatus TEXT;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_usuario TEXT;\n    \"\"\")\n    conn.commit()\n\n",
   "        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_activa BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_estatus TEXT;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS rh_vac_microsip_usuario TEXT;\n        -- Base de PRUEBAS de Microsip (copia): ruta (y opcional host/usuario) y, por módulo,\n        -- qué personas la usan. Todos los demás siguen en la base real.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS microsip_pruebas_json TEXT;\n    \"\"\")\n    conn.commit()\n\n"
  ],
  [
   "    cur.close(); conn.close()\n\n\ndef obtener_config_microsip(empresa_id):\n    \"\"\"Trae TODO, incluida la contraseña — solo para uso interno (conectar de\n    verdad a Firebird). Nunca se manda esto tal cual al frontend.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n",
   "    cur.close(); conn.close()\n\n\n# ---- Base de PRUEBAS de Microsip por módulo y por persona ----\n# Cada petición web/app deja aquí (middleware de app.py) quién la hace y de qué\n# módulo es. Si esa persona marcó \"usar pruebas\" en ese módulo, la conexión a\n# Microsip va a la copia; cualquier otra persona (y lo automático) va a la real.\nMICROSIP_CTX = contextvars.ContextVar(\"microsip_ctx\", default=None)  # (usuario_id, modulo) o None\n\nMODULOS_MICROSIP_PRUEBAS = {\n    \"dashboard\": \"📊 Dashboard, consultas y reportes (inventario, ventas, clientes)\",\n    \"inventarios\": \"📦 Inventarios a puerta abierta (app)\",\n    \"rh\": \"👥 RH (vacaciones, asistencia, fichas)\",\n    \"laboratorio\": \"🦷 Laboratorio (clientes, cotizaciones y facturas)\",\n    \"ventas\": \"🧾 Checador de precio, cotizador y CRM\",\n    \"entregas\": \"🚚 Entregas / Logística (pedidos de Microsip)\",\n}\n\n\ndef obtener_microsip_pruebas(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT microsip_pruebas_json FROM empresas WHERE id = %s\", (empresa_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    try:\n        d = json.loads((row or {}).get(\"microsip_pruebas_json\") or \"{}\") or {}\n    except (TypeError, ValueError):\n        d = {}\n    d.setdefault(\"modulos\", {})\n    return d\n\n\ndef guardar_microsip_pruebas(empresa_id, datos):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET microsip_pruebas_json = %s WHERE id = %s\", (json.dumps(datos, ensure_ascii=False), empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef modulos_pruebas_de_usuario(empresa_id, usuario_id):\n    \"\"\"Módulos en los que esta persona está usando la base de pruebas (solo si hay ruta de pruebas).\"\"\"\n    if not empresa_id or not usuario_id:\n        return []\n    d = obtener_microsip_pruebas(empresa_id)\n    if not (d.get(\"ruta_db\") or \"\").strip():\n        return []\n    return [m for m, ids in (d.get(\"modulos\") or {}).items() if m in MODULOS_MICROSIP_PRUEBAS and int(usuario_id) in [int(x) for x in ids or []]]\n\n\ndef config_microsip_pruebas(empresa_id, cfg_real):\n    \"\"\"La config real con la conexión cambiada a la base de pruebas (lo vacío = igual que la real).\"\"\"\n    d = obtener_microsip_pruebas(empresa_id)\n    if not cfg_real or not (d.get(\"ruta_db\") or \"\").strip():\n        return None\n    c = dict(cfg_real)\n    c[\"microsip_ruta_db\"] = d[\"ruta_db\"].strip()\n    if (d.get(\"host\") or \"\").strip():\n        c[\"microsip_host\"] = d[\"host\"].strip()\n    if d.get(\"puerto\"):\n        c[\"microsip_puerto\"] = int(d[\"puerto\"])\n    if (d.get(\"usuario\") or \"\").strip():\n        c[\"microsip_usuario\"] = d[\"usuario\"].strip()\n        c[\"microsip_password\"] = d.get(\"password\") or \"\"\n    c[\"_pruebas\"] = True\n    return c\n\n\ndef _aplicar_microsip_pruebas(empresa_id, cfg):\n    ctx = MICROSIP_CTX.get()\n    if not ctx or not cfg:\n        return cfg\n    usuario_id, modulo = ctx\n    if not modulo or modulo not in modulos_pruebas_de_usuario(empresa_id, usuario_id):\n        return cfg\n    return config_microsip_pruebas(empresa_id, cfg) or cfg\n\n\ndef obtener_config_microsip(empresa_id, real=False):\n    \"\"\"Trae TODO, incluida la contraseña — solo para uso interno (conectar de\n    verdad a Firebird). Nunca se manda esto tal cual al frontend.\n    Si quien hace la petición marcó \"usar pruebas\" en ese módulo, regresa la base de\n    pruebas (real=True siempre la real).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n"
  ],
  [
   "    )\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef obtener_config_microsip_publica(empresa_id):\n    \"\"\"Igual que obtener_config_microsip, pero SIN la contraseña — para\n    mostrar en la pantalla de Administrar (solo dice si ya hay una guardada).\"\"\"\n    config = obtener_config_microsip(empresa_id)\n    if not config:\n        return None\n    return {\n",
   "    )\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    if not row:\n        return None\n    return dict(row) if real else _aplicar_microsip_pruebas(empresa_id, dict(row))\n\n\ndef obtener_config_microsip_publica(empresa_id):\n    \"\"\"Igual que obtener_config_microsip, pero SIN la contraseña — para\n    mostrar en la pantalla de Administrar (solo dice si ya hay una guardada).\"\"\"\n    config = obtener_config_microsip(empresa_id, real=True)\n    if not config:\n        return None\n    return {\n"
  ],
  [
   "                   FROM empresas WHERE id = %s\"\"\", (empresa_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(row) if row else None\n\n\ndef guardar_config_microsip_escritura(empresa_id, activa, usuario, password=None,\n",
   "                   FROM empresas WHERE id = %s\"\"\", (empresa_id,))\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return _aplicar_microsip_pruebas(empresa_id, dict(row)) if row else None\n\n\ndef guardar_config_microsip_escritura(empresa_id, activa, usuario, password=None,\n"
  ]
 ],
 "backend/app.py": [
  [
   "        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        # Concurso interno activo (ej. ofrendas): el menú muestra el botón para ir a votar.\n        \"modulo_concursos\": _concursos_habilitados(usuario.get(\"empresa_id\")),\n        \"concurso_activo\": next(({\"id\": c[\"id\"], \"nombre\": c[\"nombre\"]} for c in db.listar_concursos(usuario[\"empresa_id\"])\n                                 if c[\"activo\"] and (c[\"abierto\"] or usuario[\"rol\"] == \"admin\")), None) if _concursos_habilitados(usuario.get(\"empresa_id\")) else None,\n        \"app_movil\": db.app_movil_empresa(usuario[\"empresa_id\"]) if usuario.get(\"empresa_id\") else None,\n",
   "        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        # Concurso interno activo (ej. ofrendas): el menú muestra el botón para ir a votar.\n        \"modulo_concursos\": _concursos_habilitados(usuario.get(\"empresa_id\")),\n        # Módulos en los que ESTA persona está conectada a la base de PRUEBAS de Microsip (aviso en pantalla).\n        \"microsip_pruebas\": [{\"modulo\": m, \"nombre\": db.MODULOS_MICROSIP_PRUEBAS[m]}\n                             for m in db.modulos_pruebas_de_usuario(usuario.get(\"empresa_id\"), usuario.get(\"id\"))]\n                            if usuario.get(\"empresa_id\") and usuario[\"rol\"] != \"master\" else [],\n        \"concurso_activo\": next(({\"id\": c[\"id\"], \"nombre\": c[\"nombre\"]} for c in db.listar_concursos(usuario[\"empresa_id\"])\n                                 if c[\"activo\"] and (c[\"abierto\"] or usuario[\"rol\"] == \"admin\")), None) if _concursos_habilitados(usuario.get(\"empresa_id\")) else None,\n        \"app_movil\": db.app_movil_empresa(usuario[\"empresa_id\"]) if usuario.get(\"empresa_id\") else None,\n"
  ],
  [
   "_RUTA_TRABAJO_LAB = re.compile(r\"^/api/laboratorio/(\\d+)(/|$)\")\n\n\n@app.middleware(\"http\")\nasync def _middleware_avisos_laboratorio(request: Request, call_next):\n    respuesta = await call_next(request)\n",
   "_RUTA_TRABAJO_LAB = re.compile(r\"^/api/laboratorio/(\\d+)(/|$)\")\n\n\n# ---- Microsip: base de PRUEBAS por módulo y por persona ----\n# Ruta -> módulo. Lo de configuración/explorador de Microsip (/api/microsip/...,\n# /api/admin/...) y lo automático siempre van a la base REAL.\n_RUTAS_MODULO_MICROSIP = [\n    (\"/api/microsip/vacaciones\", \"rh\"),\n    (\"/api/mis-vacaciones\", \"rh\"),\n    (\"/api/rh/\", \"rh\"),\n    (\"/api/dashboard/\", \"dashboard\"),\n    (\"/api/direccion/\", \"dashboard\"),\n    (\"/api/inventarios\", \"inventarios\"),\n    (\"/api/laboratorio\", \"laboratorio\"),\n    (\"/api/checador-precio\", \"ventas\"),\n    (\"/api/cotizaciones\", \"ventas\"),\n    (\"/api/promociones\", \"ventas\"),\n    (\"/api/crm/\", \"ventas\"),\n    (\"/api/entregas\", \"entregas\"),\n]\n\n\ndef _modulo_microsip_de_ruta(ruta):\n    for prefijo, modulo in _RUTAS_MODULO_MICROSIP:\n        if ruta.startswith(prefijo):\n            return modulo\n    return None\n\n\n@app.middleware(\"http\")\nasync def _middleware_microsip_pruebas(request: Request, call_next):\n    marca = None\n    try:\n        modulo = _modulo_microsip_de_ruta(request.url.path)\n        cab = request.headers.get(\"authorization\") or \"\"\n        if modulo and cab.startswith(\"Bearer \"):\n            try:\n                quien = auth.verificar_token(cab.split(\" \", 1)[1])\n            except Exception:\n                quien = None\n            if quien and quien.get(\"id\"):\n                marca = db.MICROSIP_CTX.set((quien[\"id\"], modulo))\n    except Exception as e:  # noqa: BLE001\n        print(f\"[microsip-pruebas] middleware: {e}\")\n    try:\n        return await call_next(request)\n    finally:\n        if marca is not None:\n            db.MICROSIP_CTX.reset(marca)\n\n\nclass MicrosipPruebasIn(BaseModel):\n    ruta_db: Optional[str] = Field(default=None, max_length=500)\n    host: Optional[str] = Field(default=None, max_length=200)\n    puerto: Optional[int] = Field(default=None, ge=1, le=65535)\n    usuario: Optional[str] = Field(default=None, max_length=100)\n    password: Optional[str] = None  # None = no cambiarla; \"\" = borrarla\n    mis_modulos: List[str] = []      # módulos donde YO uso la base de pruebas\n\n\n@app.get(\"/api/microsip/pruebas\")\ndef api_ver_microsip_pruebas(usuario: dict = Depends(requiere_admin_completo)):\n    d = db.obtener_microsip_pruebas(usuario[\"empresa_id\"])\n    nombres = {u[\"id\"]: u[\"nombre_completo\"] for u in db.listar_usuarios(usuario[\"empresa_id\"])}\n    return {\n        \"ruta_db\": d.get(\"ruta_db\") or \"\", \"host\": d.get(\"host\") or \"\", \"puerto\": d.get(\"puerto\"),\n        \"usuario\": d.get(\"usuario\") or \"\", \"tiene_password\": bool(d.get(\"password\")),\n        \"modulos\": [{\"clave\": m, \"nombre\": n,\n                     \"yo\": int(usuario[\"id\"]) in [int(x) for x in (d[\"modulos\"].get(m) or [])],\n                     \"otros\": [nombres.get(int(x), f\"#{x}\") for x in (d[\"modulos\"].get(m) or []) if int(x) != int(usuario[\"id\"])]}\n                    for m, n in db.MODULOS_MICROSIP_PRUEBAS.items()],\n    }\n\n\n@app.post(\"/api/microsip/pruebas\")\ndef api_guardar_microsip_pruebas(payload: MicrosipPruebasIn, usuario: dict = Depends(requiere_admin_completo)):\n    d = db.obtener_microsip_pruebas(usuario[\"empresa_id\"])\n    d[\"ruta_db\"] = (payload.ruta_db or \"\").strip()\n    d[\"host\"] = (payload.host or \"\").strip()\n    d[\"puerto\"] = payload.puerto\n    d[\"usuario\"] = (payload.usuario or \"\").strip()\n    if payload.password is not None:\n        d[\"password\"] = payload.password\n    yo = int(usuario[\"id\"])\n    for m in db.MODULOS_MICROSIP_PRUEBAS:\n        ids = [int(x) for x in (d[\"modulos\"].get(m) or []) if int(x) != yo]\n        if m in payload.mis_modulos:\n            ids.append(yo)\n        d[\"modulos\"][m] = ids\n    if payload.mis_modulos and not d[\"ruta_db\"]:\n        raise HTTPException(status_code=400, detail=\"Primero escribe la ruta de la base de PRUEBAS\")\n    db.guardar_microsip_pruebas(usuario[\"empresa_id\"], d)\n    return {\"ok\": True, \"mis_modulos\": db.modulos_pruebas_de_usuario(usuario[\"empresa_id\"], usuario[\"id\"])}\n\n\n@app.post(\"/api/microsip/pruebas/probar-conexion\")\ndef api_probar_microsip_pruebas(usuario: dict = Depends(requiere_admin_completo)):\n    _requiere_microsip_disponible()\n    cfg = db.config_microsip_pruebas(usuario[\"empresa_id\"], db.obtener_config_microsip(usuario[\"empresa_id\"], real=True))\n    if not cfg:\n        raise HTTPException(status_code=400, detail=\"Falta configurar la conexión real o la ruta de la base de pruebas\")\n    ok, mensaje = microsip.probar_conexion(cfg)\n    if not ok:\n        raise HTTPException(status_code=400, detail=mensaje)\n    return {\"ok\": True, \"mensaje\": \"Base de PRUEBAS: \" + mensaje}\n\n\n@app.middleware(\"http\")\nasync def _middleware_avisos_laboratorio(request: Request, call_next):\n    respuesta = await call_next(request)\n"
  ]
 ],
 "frontend/index.html": [
  [
   "\nasync function cargarMeta() {\n  META = await api('/api/meta');\n  aplicarApariencia(META.apariencia);\n  aplicarTerminosPersonalizados();\n  if (document.getElementById('f_departamento')) {\n",
   "\nasync function cargarMeta() {\n  META = await api('/api/meta');\n  try { pintarAvisoMicrosipPruebas(); } catch (e) {}\n  aplicarApariencia(META.apariencia);\n  aplicarTerminosPersonalizados();\n  if (document.getElementById('f_departamento')) {\n"
  ],
  [
   "      ['ms_vac', '🏖️ Vacaciones (RH)', esAdmin],\n      ['ms_usr', '👥 Usuarios y permisos', esAdmin],\n      ['ms_lote', '📦 Lote / serie faltante', esAdmin],\n      ['explorador_microsip', '🔍 Explorador de tablas', esAdmin],\n    ] },\n    { titulo: '🔗 Otras integraciones', tabs: [\n",
   "      ['ms_vac', '🏖️ Vacaciones (RH)', esAdmin],\n      ['ms_usr', '👥 Usuarios y permisos', esAdmin],\n      ['ms_lote', '📦 Lote / serie faltante', esAdmin],\n      ['ms_pruebas', '🧪 Base de pruebas', esAdmin],\n      ['explorador_microsip', '🔍 Explorador de tablas', esAdmin],\n    ] },\n    { titulo: '🔗 Otras integraciones', tabs: [\n"
  ],
  [
   "  } else if (ADMIN_TAB === 'terminologia' && esAdmin) {\n    const datos = await api('/api/terminos/editables');\n    renderTerminologiaAdmin(tabs, datos);\n  } else if (['microsip', 'ms_escritura', 'ms_lab', 'ms_vac', 'ms_usr', 'ms_lote'].includes(ADMIN_TAB) && esAdmin) {\n    const config = await api('/api/microsip/config');\n    renderMicrosipAdmin(tabs, config, ADMIN_TAB);\n  } else if (ADMIN_TAB === 'shopify' && esAdmin) {\n",
   "  } else if (ADMIN_TAB === 'terminologia' && esAdmin) {\n    const datos = await api('/api/terminos/editables');\n    renderTerminologiaAdmin(tabs, datos);\n  } else if (['microsip', 'ms_escritura', 'ms_lab', 'ms_vac', 'ms_usr', 'ms_lote', 'ms_pruebas'].includes(ADMIN_TAB) && esAdmin) {\n    const config = await api('/api/microsip/config');\n    renderMicrosipAdmin(tabs, config, ADMIN_TAB);\n  } else if (ADMIN_TAB === 'shopify' && esAdmin) {\n"
  ],
  [
   "    `;\n    abrirModal(true);\n    if (config.microsip_host) {\n      ({ ms_escritura: ms_cargarEscritura, ms_lab: ms_cargarLab, ms_vac: ms_cargarVac, ms_usr: ms_renderUsr, ms_lote: ms_renderLote })[seccion]();\n    }\n    return;\n  }\n",
   "    `;\n    abrirModal(true);\n    if (config.microsip_host) {\n      ({ ms_escritura: ms_cargarEscritura, ms_lab: ms_cargarLab, ms_vac: ms_cargarVac, ms_usr: ms_renderUsr, ms_lote: ms_renderLote, ms_pruebas: ms_cargarPruebas })[seccion]();\n    }\n    return;\n  }\n"
  ],
  [
   "\n// ---- Artículos que piden lote/serie y no lo tienen asignado ----\nlet MS_LOTE = null;\nfunction ms_renderLote() {\n  const caja = document.getElementById('ms_lote');\n  if (!caja) return;\n",
   "\n// ---- Artículos que piden lote/serie y no lo tienen asignado ----\nlet MS_LOTE = null;\n// ---- 🧪 Base de PRUEBAS de Microsip: por módulo y SOLO para quien la marca ----\nasync function ms_cargarPruebas() {\n  const caja = document.getElementById('ms_pruebas');\n  caja.innerHTML = '<p style=\"color:var(--muted);\">Cargando…</p>';\n  let d;\n  try { d = await api('/api/microsip/pruebas'); } catch (e) { caja.innerHTML = `<p class=\"error-msg\">${escapeHtml(e.message)}</p>`; return; }\n  caja.innerHTML = `\n    <p style=\"font-size:12px; color:var(--muted); margin-bottom:12px;\">\n      Conecta una <b>copia</b> de la base de Microsip para probar cambios (consultas, altas de clientes, cotizaciones, vacaciones…).\n      Marca los módulos donde <b>tú</b> quieres usar la copia: <b>solo tú</b> quedas en pruebas en esos módulos;\n      todos los demás (y lo automático, como el respaldo de inventario) siguen en la base <b>real</b>.\n      Cuando todo salga bien, desmárcalos y vuelves a la real.</p>\n    <div class=\"field\"><label>Ruta de la base de PRUEBAS en el servidor *</label>\n      <input id=\"msp_ruta\" value=\"${escapeHtml(d.ruta_db || '')}\" placeholder=\"ej. C:\\\\Microsip datos\\\\EMPRESA_PRUEBAS.FDB\" /></div>\n    <details style=\"margin-bottom:10px;\"><summary style=\"cursor:pointer; font-size:12px; color:var(--muted);\">Otro servidor o usuario (opcional — vacío = el mismo de la conexión real)</summary>\n      <div class=\"row-2\" style=\"margin-top:8px;\">\n        <div class=\"field\"><label>Host / IP</label><input id=\"msp_host\" value=\"${escapeHtml(d.host || '')}\" placeholder=\"igual que la real\" /></div>\n        <div class=\"field\"><label>Puerto</label><input id=\"msp_puerto\" type=\"number\" value=\"${d.puerto || ''}\" placeholder=\"igual que la real\" /></div>\n      </div>\n      <div class=\"row-2\">\n        <div class=\"field\"><label>Usuario de Firebird</label><input id=\"msp_usuario\" value=\"${escapeHtml(d.usuario || '')}\" placeholder=\"igual que la real\" /></div>\n        <div class=\"field\"><label>Contraseña ${d.tiene_password ? '<span style=\"color:var(--muted); font-weight:400; text-transform:none;\">(ya hay una — vacío = no cambiarla)</span>' : ''}</label><input id=\"msp_password\" type=\"password\" /></div>\n      </div>\n    </details>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase;\">¿En qué módulos uso YO la base de pruebas?</label>\n    <div style=\"margin:6px 0 12px;\">\n      ${d.modulos.map(m => `\n        <label style=\"display:flex; gap:8px; align-items:flex-start; padding:7px 4px; border-bottom:1px solid var(--line); cursor:pointer;\">\n          <input type=\"checkbox\" class=\"msp_mod\" value=\"${m.clave}\" ${m.yo ? 'checked' : ''} style=\"width:auto; margin-top:3px;\" />\n          <span>${escapeHtml(m.nombre)}${m.otros.length ? `<br><span style=\"font-size:11px; color:var(--muted);\">También en pruebas: ${m.otros.map(escapeHtml).join(', ')}</span>` : ''}</span>\n        </label>`).join('')}\n    </div>\n    <div style=\"display:flex; gap:8px;\">\n      <button class=\"primary\" style=\"flex:1;\" onclick=\"ms_guardarPruebas(this)\">Guardar</button>\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"ms_probarPruebas(this)\">Probar conexión a pruebas</button>\n      <button class=\"secondary\" onclick=\"document.querySelectorAll('.msp_mod').forEach(c => c.checked = false); ms_guardarPruebas(this)\" title=\"Desmarca todos tus módulos: vuelves a la base real en todo\">↩️ Todo a la real</button>\n    </div>\n    <div id=\"msp_error\" class=\"error-msg\"></div><div id=\"msp_ok\"></div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:12px;\">⚠️ Lo que hagas en pruebas puede guardar en el sistema folios o IDs de la copia (ej. el cliente de Microsip de un estudiante o el folio de una cotización). Usa estudiantes, clientes y trabajos <b>de prueba</b>.</p>`;\n}\n\nasync function ms_guardarPruebas(boton) {\n  const err = document.getElementById('msp_error'); err.textContent = '';\n  const pw = document.getElementById('msp_password').value;\n  const payload = {\n    ruta_db: document.getElementById('msp_ruta').value.trim(),\n    host: document.getElementById('msp_host').value.trim(),\n    puerto: parseInt(document.getElementById('msp_puerto').value, 10) || null,\n    usuario: document.getElementById('msp_usuario').value.trim(),\n    password: pw ? pw : null,\n    mis_modulos: [...document.querySelectorAll('.msp_mod:checked')].map(c => c.value),\n  };\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api('/api/microsip/pruebas', { method: 'POST', body: JSON.stringify(payload) });\n      await cargarMeta(); pintarAvisoMicrosipPruebas();\n      mostrarExito(payload.mis_modulos.length ? `Listo: estás en PRUEBAS en ${payload.mis_modulos.length} módulo(s)` : 'Listo: estás en la base REAL en todo');\n      await ms_cargarPruebas();\n    } catch (e) { err.textContent = e.message; }\n  });\n}\n\nasync function ms_probarPruebas(boton) {\n  const err = document.getElementById('msp_error'); err.textContent = '';\n  await conBloqueoDeBoton(boton, async () => {\n    try { const r = await api('/api/microsip/pruebas/probar-conexion', { method: 'POST' });\n          document.getElementById('msp_ok').innerHTML = `<p style=\"font-size:13px; color:#4caf50;\">✅ ${escapeHtml(r.mensaje)}</p>`; }\n    catch (e) { err.textContent = e.message; }\n  });\n}\n\n// Aviso fijo en pantalla mientras ESTA persona tenga módulos en la base de pruebas.\nfunction pintarAvisoMicrosipPruebas() {\n  let el = document.getElementById('avisoMicrosipPruebas');\n  const mods = (META && META.microsip_pruebas) || [];\n  if (!mods.length) { if (el) el.remove(); return; }\n  if (!el) {\n    el = document.createElement('div');\n    el.id = 'avisoMicrosipPruebas';\n    el.style.cssText = 'position:fixed; top:8px; left:50%; transform:translateX(-50%); z-index:9999; background:#e6a23c; color:#1a1a1a; font-weight:700; font-size:12px; padding:6px 14px; border-radius:20px; box-shadow:0 4px 14px rgba(0,0,0,.35); cursor:pointer; max-width:92vw; text-align:center;';\n    el.title = 'Toca para cambiar (Administrar → Microsip → 🧪 Base de pruebas)';\n    el.onclick = () => { if (typeof abrirAdmin === 'function') abrirAdmin('ms_pruebas'); };\n    document.body.appendChild(el);\n  }\n  el.textContent = '🧪 MICROSIP DE PRUEBAS (solo tú): ' + mods.map(m => m.nombre.replace(/^\\S+\\s/, '').split(' (')[0]).join(' · ');\n}\n\nfunction ms_renderLote() {\n  const caja = document.getElementById('ms_lote');\n  if (!caja) return;\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_microsip_base_pruebas.py")
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
