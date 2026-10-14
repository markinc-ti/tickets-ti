# -*- coding: utf-8 -*-
"""
Logística de reparaciones por persona: nuevo acceso "Logística Rep." en
Administrar → Accesos (y en Editar usuario). Quien lo tenga -- o esté en una
sucursal con departamento "Logística" -- ve todas las reparaciones y hace
revisión por calidad, listo para envío y la entrega al chofer, sin importar
su rol (también almacén).
REQUIERE haber corrido antes fix_reparaciones_whatsapp.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\n\ndef _es_departamento_logistica(usuario_id: int) -> bool:\n    \"\"\"True si el departamento del usuario (heredado de su sucursal, ver\n    db.obtener_departamento_usuario) es \"Logística\" -- sin importar mayúsculas\n    ni acentos. Se usa SOLO para ampliar qué reparaciones puede VER un usuario\n    con rol \"usuario\"/\"encargado_sucursal\" (que por default solo ven lo suyo);\n    ningún endpoint de acción (editar, cambiar estado, firmar, entregar,\n    eliminar) llama a esta función, así que ese departamento sigue sin poder\n    hacer nada de eso -- únicamente consultar.\"\"\"\n    depto = db.obtener_departamento_usuario(usuario_id) or \"\"\n    depto_normalizado = unicodedata.normalize(\"NFKD\", depto).encode(\"ascii\", \"ignore\").decode().strip().lower()\n    return depto_normalizado == \"logistica\"\n\n\ndef requiere_ver_reparaciones(usuario: dict = Depends(requiere_empresa_o_almacen)) -> dict:\n",
   "\n\ndef _es_departamento_logistica(usuario_id: int) -> bool:\n    \"\"\"True si la persona hace la Logística de reparaciones: tiene el acceso\n    \"Logística Rep.\" (Administrar → Accesos) o su sucursal tiene departamento\n    \"Logística\" (sin importar mayúsculas ni acentos). Logística ve todas las\n    reparaciones y hace revisión por calidad, listo para envío y la entrega\n    al chofer.\"\"\"\n    # También cuenta quien tenga el acceso \"Logística Rep.\" (Administrar → Accesos).\n    return db.es_logistica_reparaciones(usuario_id)\n\n\ndef requiere_ver_reparaciones(usuario: dict = Depends(requiere_empresa_o_almacen)) -> dict:\n"
  ],
  [
   "            \"acceso_reparaciones\": True if usuario[\"rol\"] == \"almacen\" else usuario.get(\"acceso_reparaciones\", True),\n            \"acceso_laboratorio\": usuario.get(\"acceso_laboratorio\", True),\n            \"acceso_laboratorio_entrega\": usuario.get(\"acceso_laboratorio_entrega\", False),\n            \"acceso_entregas\": True if usuario[\"rol\"] == \"instalador\" else usuario.get(\"acceso_entregas\", True),\n            \"acceso_checador_precio\": usuario.get(\"acceso_checador_precio\", True),\n            \"acceso_marketing\": False if usuario[\"rol\"] == \"instalador\" else usuario.get(\"acceso_marketing\", True),\n",
   "            \"acceso_reparaciones\": True if usuario[\"rol\"] == \"almacen\" else usuario.get(\"acceso_reparaciones\", True),\n            \"acceso_laboratorio\": usuario.get(\"acceso_laboratorio\", True),\n            \"acceso_laboratorio_entrega\": usuario.get(\"acceso_laboratorio_entrega\", False),\n            \"acceso_logistica_reparaciones\": usuario.get(\"acceso_logistica_reparaciones\", False),\n            \"acceso_entregas\": True if usuario[\"rol\"] == \"instalador\" else usuario.get(\"acceso_entregas\", True),\n            \"acceso_checador_precio\": usuario.get(\"acceso_checador_precio\", True),\n            \"acceso_marketing\": False if usuario[\"rol\"] == \"instalador\" else usuario.get(\"acceso_marketing\", True),\n"
  ],
  [
   "    acceso_reparaciones: Optional[bool] = None\n    acceso_laboratorio: Optional[bool] = None\n    acceso_laboratorio_entrega: Optional[bool] = None\n    acceso_entregas: Optional[bool] = None\n    acceso_checador_precio: Optional[bool] = None\n    acceso_marketing: Optional[bool] = None\n",
   "    acceso_reparaciones: Optional[bool] = None\n    acceso_laboratorio: Optional[bool] = None\n    acceso_laboratorio_entrega: Optional[bool] = None\n    acceso_logistica_reparaciones: Optional[bool] = None\n    acceso_entregas: Optional[bool] = None\n    acceso_checador_precio: Optional[bool] = None\n    acceso_marketing: Optional[bool] = None\n"
  ],
  [
   "                           acceso_dashboard=payload.acceso_dashboard, acceso_tickets=payload.acceso_tickets,\n                           acceso_reparaciones=payload.acceso_reparaciones, acceso_laboratorio=payload.acceso_laboratorio,\n                           acceso_laboratorio_entrega=payload.acceso_laboratorio_entrega, acceso_entregas=payload.acceso_entregas,\n                           acceso_checador_precio=payload.acceso_checador_precio,\n                           acceso_marketing=payload.acceso_marketing,\n                           acceso_crm=payload.acceso_crm,\n",
   "                           acceso_dashboard=payload.acceso_dashboard, acceso_tickets=payload.acceso_tickets,\n                           acceso_reparaciones=payload.acceso_reparaciones, acceso_laboratorio=payload.acceso_laboratorio,\n                           acceso_laboratorio_entrega=payload.acceso_laboratorio_entrega, acceso_entregas=payload.acceso_entregas,\n                           acceso_logistica_reparaciones=payload.acceso_logistica_reparaciones,\n                           acceso_checador_precio=payload.acceso_checador_precio,\n                           acceso_marketing=payload.acceso_marketing,\n                           acceso_crm=payload.acceso_crm,\n"
  ],
  [
   "    # firmar, entregar, eliminar) siguen bloqueadas igual que siempre, esos endpoints\n    # no llaman a esta función. El rol \"almacen\" NO se incluye a propósito: su\n    # restricción a la sucursal propia es de seguridad, no de filtro.\n    ve_todo_por_logistica = usuario[\"rol\"] in (\"usuario\", \"encargado_sucursal\") and _es_departamento_logistica(usuario[\"id\"])\n    if ve_todo_por_logistica:\n        creado_por_id = None\n    if usuario[\"rol\"] in (\"almacen\", \"encargado_sucursal\") and not ve_todo_por_logistica:\n",
   "    # firmar, entregar, eliminar) siguen bloqueadas igual que siempre, esos endpoints\n    # no llaman a esta función. El rol \"almacen\" NO se incluye a propósito: su\n    # restricción a la sucursal propia es de seguridad, no de filtro.\n    ve_todo_por_logistica = usuario[\"rol\"] in (\"usuario\", \"encargado_sucursal\", \"almacen\") and _es_departamento_logistica(usuario[\"id\"])\n    if ve_todo_por_logistica:\n        creado_por_id = None\n    if usuario[\"rol\"] in (\"almacen\", \"encargado_sucursal\") and not ve_todo_por_logistica:\n"
  ],
  [
   "    reparacion = db.obtener_reparacion(usuario[\"empresa_id\"], reparacion_id)\n    if not reparacion:\n        raise HTTPException(status_code=404, detail=\"Reparación no encontrada\")\n    ve_todo_por_logistica = usuario[\"rol\"] in (\"usuario\", \"encargado_sucursal\") and _es_departamento_logistica(usuario[\"id\"])\n    if usuario[\"rol\"] == \"usuario\" and reparacion[\"creado_por_id\"] != usuario[\"id\"] and not ve_todo_por_logistica:\n        raise HTTPException(status_code=403, detail=\"No puedes ver esta reparación\")\n    if (usuario[\"rol\"] in (\"almacen\", \"encargado_sucursal\")\n",
   "    reparacion = db.obtener_reparacion(usuario[\"empresa_id\"], reparacion_id)\n    if not reparacion:\n        raise HTTPException(status_code=404, detail=\"Reparación no encontrada\")\n    ve_todo_por_logistica = usuario[\"rol\"] in (\"usuario\", \"encargado_sucursal\", \"almacen\") and _es_departamento_logistica(usuario[\"id\"])\n    if usuario[\"rol\"] == \"usuario\" and reparacion[\"creado_por_id\"] != usuario[\"id\"] and not ve_todo_por_logistica:\n        raise HTTPException(status_code=403, detail=\"No puedes ver esta reparación\")\n    if (usuario[\"rol\"] in (\"almacen\", \"encargado_sucursal\")\n"
  ]
 ],
 "backend/db.py": [
  [
   "        -- admin lo puede hacer siempre por su rol, ver requiere_laboratorio_entrega\n        -- en app.py) — el dueño se lo da a quien él decida, uno por uno.\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_laboratorio_entrega BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS calendario_token TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_dashboard BOOLEAN NOT NULL DEFAULT TRUE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS numero_empleado TEXT;\n",
   "        -- admin lo puede hacer siempre por su rol, ver requiere_laboratorio_entrega\n        -- en app.py) — el dueño se lo da a quien él decida, uno por uno.\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_laboratorio_entrega BOOLEAN NOT NULL DEFAULT FALSE;\n        -- Logística de reparaciones (revisión por calidad, listo para envío,\n        -- entrega al chofer). Se da por persona en Administrar → Accesos, además\n        -- de quien esté en una sucursal con departamento \"Logística\".\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_logistica_reparaciones BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS calendario_token TEXT;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_dashboard BOOLEAN NOT NULL DEFAULT TRUE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS numero_empleado TEXT;\n"
  ],
  [
   "    cur.execute(\n        \"\"\"SELECT u.id, u.username, u.nombre_completo, u.rol, u.puesto, u.telefono_whatsapp, u.activo, u.creado_en,\n                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_entregas,\n                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_monitoreo, u.acceso_shopify, u.monitoreo_activo,\n                  u.acceso_turnos, u.ventanilla_turnos,\n                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,\n",
   "    cur.execute(\n        \"\"\"SELECT u.id, u.username, u.nombre_completo, u.rol, u.puesto, u.telefono_whatsapp, u.activo, u.creado_en,\n                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_logistica_reparaciones, u.acceso_entregas,\n                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_monitoreo, u.acceso_shopify, u.monitoreo_activo,\n                  u.acceso_turnos, u.ventanilla_turnos,\n                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,\n"
  ],
  [
   "    cur = conn.cursor()\n    cur.execute(\n        \"\"\"SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_entregas, acceso_checador_precio,\n                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_monitoreo, acceso_shopify, monitoreo_activo,\n                  acceso_turnos, ventanilla_turnos\n           FROM users WHERE id = %s\"\"\",\n",
   "    cur = conn.cursor()\n    cur.execute(\n        \"\"\"SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_logistica_reparaciones, acceso_entregas, acceso_checador_precio,\n                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_monitoreo, acceso_shopify, monitoreo_activo,\n                  acceso_turnos, ventanilla_turnos\n           FROM users WHERE id = %s\"\"\",\n"
  ],
  [
   "                        puesto=None, restriccion_categoria=\"__sin_cambio__\", acceso_equipos=None,\n                        acceso_administracion=None, acceso_compras=None, acceso_rh=None, acceso_dashboard=None,\n                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,\n                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,\n                        acceso_datos_empleado_rh=None, acceso_monitoreo=None, acceso_shopify=None, acceso_turnos=None,\n                        monitoreo_activo=None,\n",
   "                        puesto=None, restriccion_categoria=\"__sin_cambio__\", acceso_equipos=None,\n                        acceso_administracion=None, acceso_compras=None, acceso_rh=None, acceso_dashboard=None,\n                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,\n                        acceso_logistica_reparaciones=None,\n                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,\n                        acceso_datos_empleado_rh=None, acceso_monitoreo=None, acceso_shopify=None, acceso_turnos=None,\n                        monitoreo_activo=None,\n"
  ],
  [
   "        campos.append(\"acceso_laboratorio = %s\"); valores.append(acceso_laboratorio)\n    if acceso_laboratorio_entrega is not None:\n        campos.append(\"acceso_laboratorio_entrega = %s\"); valores.append(acceso_laboratorio_entrega)\n    if acceso_entregas is not None:\n        campos.append(\"acceso_entregas = %s\"); valores.append(acceso_entregas)\n    if acceso_checador_precio is not None:\n",
   "        campos.append(\"acceso_laboratorio = %s\"); valores.append(acceso_laboratorio)\n    if acceso_laboratorio_entrega is not None:\n        campos.append(\"acceso_laboratorio_entrega = %s\"); valores.append(acceso_laboratorio_entrega)\n    if acceso_logistica_reparaciones is not None:\n        campos.append(\"acceso_logistica_reparaciones = %s\"); valores.append(acceso_logistica_reparaciones)\n    if acceso_entregas is not None:\n        campos.append(\"acceso_entregas = %s\"); valores.append(acceso_entregas)\n    if acceso_checador_precio is not None:\n"
  ],
  [
   "    import unicodedata as _u\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT u.id, s.departamento FROM users u\n                   LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n                   WHERE u.empresa_id = %s AND u.activo = TRUE AND u.rol IS DISTINCT FROM 'estudiante'\"\"\", (empresa_id,))\n    filas = cur.fetchall()\n    cur.close(); conn.close()\n    def norm(t):\n        return _u.normalize(\"NFKD\", t or \"\").encode(\"ascii\", \"ignore\").decode().strip().lower()\n    return [f[\"id\"] for f in filas if norm(f[\"departamento\"]) == \"logistica\"]\n\n\ndef ids_encargados_sucursal(empresa_id, sucursal_id):\n",
   "    import unicodedata as _u\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT u.id, s.departamento, u.acceso_logistica_reparaciones FROM users u\n                   LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n                   WHERE u.empresa_id = %s AND u.activo = TRUE AND u.rol IS DISTINCT FROM 'estudiante'\"\"\", (empresa_id,))\n    filas = cur.fetchall()\n    cur.close(); conn.close()\n    def norm(t):\n        return _u.normalize(\"NFKD\", t or \"\").encode(\"ascii\", \"ignore\").decode().strip().lower()\n    return [f[\"id\"] for f in filas if f[\"acceso_logistica_reparaciones\"] or norm(f[\"departamento\"]) == \"logistica\"]\n\n\ndef es_logistica_reparaciones(usuario_id):\n    \"\"\"True si la persona hace Logística de reparaciones: tiene el acceso\n    \"Logística Rep.\" (Administrar → Accesos) o su sucursal tiene departamento\n    Logística (sin importar mayúsculas ni acentos).\"\"\"\n    import unicodedata as _u\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT u.acceso_logistica_reparaciones, s.departamento FROM users u\n                   LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n                   WHERE u.id = %s\"\"\", (usuario_id,))\n    f = cur.fetchone()\n    cur.close(); conn.close()\n    if not f:\n        return False\n    depto = _u.normalize(\"NFKD\", f[\"departamento\"] or \"\").encode(\"ascii\", \"ignore\").decode().strip().lower()\n    return bool(f[\"acceso_logistica_reparaciones\"]) or depto == \"logistica\"\n\n\ndef ids_encargados_sucursal(empresa_id, sucursal_id):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    <table class=\"users tabla-fija\">\n      <thead><tr>\n        <th>Persona</th><th>Rol</th>\n        <th class=\"col-check\">Tickets${casillaTodoColumna('acceso_tickets')}</th><th class=\"col-check\">Reparaciones${casillaTodoColumna('acceso_reparaciones')}</th><th class=\"col-check\">Laboratorio${casillaTodoColumna('acceso_laboratorio')}</th><th class=\"col-check\" title=\"Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal\">Recibir/Entregar Lab.${casillaTodoColumna('acceso_laboratorio_entrega')}</th><th class=\"col-check\">Entregas${casillaTodoColumna('acceso_entregas')}</th><th class=\"col-check\">Precios${casillaTodoColumna('acceso_checador_precio')}</th><th class=\"col-check\">Equipos${casillaTodoColumna('acceso_equipos')}</th>\n        <th class=\"col-check\">Compras${casillaTodoColumna('acceso_compras')}</th><th class=\"col-check\">RH${casillaTodoColumna('acceso_rh')}</th><th class=\"col-check\">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class=\"col-check\">CRM${casillaTodoColumna('acceso_crm')}</th><th class=\"col-check\">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class=\"col-check\" title=\"Ver datos sensibles de empleados\">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class=\"col-check\" title=\"Ver la pestaña 🕵️ Monitoreo (bitácora de actividad) — distinto de la columna 'Monitoreo' de más adelante, que es si a ESA persona se le vigila\">Ver Monitoreo${casillaTodoColumna('acceso_monitoreo')}</th><th class=\"col-check\">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th><th class=\"col-check\" title=\"Tomar/llamar turnos en su sucursal\">🎫 Turnos${casillaTodoColumna('acceso_turnos')}</th>\n        <th class=\"col-check\">Dashboard${casillaTodoColumna('acceso_dashboard')}</th><th class=\"col-check\">Admin.${casillaTodoColumna('acceso_administracion')}</th><th class=\"col-check\">Monitoreo${casillaTodoColumna('monitoreo_activo')}</th>\n      </tr></thead>\n",
   "    <table class=\"users tabla-fija\">\n      <thead><tr>\n        <th>Persona</th><th>Rol</th>\n        <th class=\"col-check\">Tickets${casillaTodoColumna('acceso_tickets')}</th><th class=\"col-check\">Reparaciones${casillaTodoColumna('acceso_reparaciones')}</th><th class=\"col-check\">Laboratorio${casillaTodoColumna('acceso_laboratorio')}</th><th class=\"col-check\" title=\"Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal\">Recibir/Entregar Lab.${casillaTodoColumna('acceso_laboratorio_entrega')}</th><th class=\"col-check\" title=\"Logística de reparaciones: revisión por calidad, listo para envío y entrega al chofer (ve todas las reparaciones)\">Logística Rep.${casillaTodoColumna('acceso_logistica_reparaciones')}</th><th class=\"col-check\">Entregas${casillaTodoColumna('acceso_entregas')}</th><th class=\"col-check\">Precios${casillaTodoColumna('acceso_checador_precio')}</th><th class=\"col-check\">Equipos${casillaTodoColumna('acceso_equipos')}</th>\n        <th class=\"col-check\">Compras${casillaTodoColumna('acceso_compras')}</th><th class=\"col-check\">RH${casillaTodoColumna('acceso_rh')}</th><th class=\"col-check\">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class=\"col-check\">CRM${casillaTodoColumna('acceso_crm')}</th><th class=\"col-check\">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class=\"col-check\" title=\"Ver datos sensibles de empleados\">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class=\"col-check\" title=\"Ver la pestaña 🕵️ Monitoreo (bitácora de actividad) — distinto de la columna 'Monitoreo' de más adelante, que es si a ESA persona se le vigila\">Ver Monitoreo${casillaTodoColumna('acceso_monitoreo')}</th><th class=\"col-check\">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th><th class=\"col-check\" title=\"Tomar/llamar turnos en su sucursal\">🎫 Turnos${casillaTodoColumna('acceso_turnos')}</th>\n        <th class=\"col-check\">Dashboard${casillaTodoColumna('acceso_dashboard')}</th><th class=\"col-check\">Admin.${casillaTodoColumna('acceso_administracion')}</th><th class=\"col-check\">Monitoreo${casillaTodoColumna('monitoreo_activo')}</th>\n      </tr></thead>\n"
  ],
  [
   "              : `<input type=\"checkbox\" ${u.acceso_reparaciones ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_reparaciones', this)\" data-campo=\"acceso_reparaciones\" />`}</td>\n            <td class=\"col-check\"><input type=\"checkbox\" ${u.acceso_laboratorio ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_laboratorio', this)\" data-campo=\"acceso_laboratorio\" /></td>\n            <td class=\"col-check\"><input type=\"checkbox\" ${u.acceso_laboratorio_entrega ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_laboratorio_entrega', this)\" data-campo=\"acceso_laboratorio_entrega\" /></td>\n            <td class=\"col-check\">${u.rol === 'instalador'\n              ? '<span title=\"Instalador siempre conserva Entregas\" style=\"color:var(--trace);\">✅</span>'\n              : `<input type=\"checkbox\" ${u.acceso_entregas ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_entregas', this)\" data-campo=\"acceso_entregas\" />`}</td>\n",
   "              : `<input type=\"checkbox\" ${u.acceso_reparaciones ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_reparaciones', this)\" data-campo=\"acceso_reparaciones\" />`}</td>\n            <td class=\"col-check\"><input type=\"checkbox\" ${u.acceso_laboratorio ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_laboratorio', this)\" data-campo=\"acceso_laboratorio\" /></td>\n            <td class=\"col-check\"><input type=\"checkbox\" ${u.acceso_laboratorio_entrega ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_laboratorio_entrega', this)\" data-campo=\"acceso_laboratorio_entrega\" /></td>\n            <td class=\"col-check\"><input type=\"checkbox\" ${u.acceso_logistica_reparaciones ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_logistica_reparaciones', this)\" data-campo=\"acceso_logistica_reparaciones\" /></td>\n            <td class=\"col-check\">${u.rol === 'instalador'\n              ? '<span title=\"Instalador siempre conserva Entregas\" style=\"color:var(--trace);\">✅</span>'\n              : `<input type=\"checkbox\" ${u.acceso_entregas ? 'checked' : ''} onchange=\"cambiarAccesoModuloUI(${u.id}, 'acceso_entregas', this)\" data-campo=\"acceso_entregas\" />`}</td>\n"
  ],
  [
   "        <label style=\"font-size:12px; display:flex; align-items:center; gap:6px;\" title=\"Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal\">\n          <input type=\"checkbox\" id=\"e_acceso_laboratorio_entrega\" ${u.acceso_laboratorio_entrega ? 'checked' : ''} /> Recibir/Entregar en Laboratorio\n        </label>\n        <label style=\"font-size:12px; display:flex; align-items:center; gap:6px;\">\n          <input type=\"checkbox\" id=\"e_acceso_entregas\" ${u.acceso_entregas !== false ? 'checked' : ''} /> Acceso a Entregas\n        </label>\n",
   "        <label style=\"font-size:12px; display:flex; align-items:center; gap:6px;\" title=\"Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal\">\n          <input type=\"checkbox\" id=\"e_acceso_laboratorio_entrega\" ${u.acceso_laboratorio_entrega ? 'checked' : ''} /> Recibir/Entregar en Laboratorio\n        </label>\n        <label style=\"font-size:12px; display:flex; align-items:center; gap:6px;\" title=\"Revisión por calidad, listo para envío y entrega al chofer; ve todas las reparaciones\">\n          <input type=\"checkbox\" id=\"e_acceso_logistica_reparaciones\" ${u.acceso_logistica_reparaciones ? 'checked' : ''} /> Logística de reparaciones\n        </label>\n        <label style=\"font-size:12px; display:flex; align-items:center; gap:6px;\">\n          <input type=\"checkbox\" id=\"e_acceso_entregas\" ${u.acceso_entregas !== false ? 'checked' : ''} /> Acceso a Entregas\n        </label>\n"
  ],
  [
   "    payload.acceso_reparaciones = document.getElementById('e_acceso_reparaciones').checked;\n    payload.acceso_laboratorio = document.getElementById('e_acceso_laboratorio').checked;\n    payload.acceso_laboratorio_entrega = document.getElementById('e_acceso_laboratorio_entrega').checked;\n    payload.acceso_entregas = document.getElementById('e_acceso_entregas').checked;\n    payload.acceso_checador_precio = document.getElementById('e_acceso_checador_precio').checked;\n    payload.acceso_equipos = document.getElementById('e_acceso_equipos').checked;\n",
   "    payload.acceso_reparaciones = document.getElementById('e_acceso_reparaciones').checked;\n    payload.acceso_laboratorio = document.getElementById('e_acceso_laboratorio').checked;\n    payload.acceso_laboratorio_entrega = document.getElementById('e_acceso_laboratorio_entrega').checked;\n    if (document.getElementById('e_acceso_logistica_reparaciones')) payload.acceso_logistica_reparaciones = document.getElementById('e_acceso_logistica_reparaciones').checked;\n    payload.acceso_entregas = document.getElementById('e_acceso_entregas').checked;\n    payload.acceso_checador_precio = document.getElementById('e_acceso_checador_precio').checked;\n    payload.acceso_equipos = document.getElementById('e_acceso_equipos').checked;\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "class WhatsappReparacionIn" not in f.read():
            print("Primero corre fix_reparaciones_whatsapp.py (y los anteriores), y luego este.")
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
