# -*- coding: utf-8 -*-
"""
APPS SEPARADAS (Mark·Inc / Peymar)
- Cada empresa tiene su "App movil": Mark·Inc o Peymar (Superadmin -> Modulos de
  la empresa, o al crearla). Sin elegir, se deduce del nombre (Peymar -> Peymar).
- El login de la app manda cual app es; si la cuenta es de la otra empresa, no
  entra ("entra con la app Peymar"). La web no cambia. El superadmin entra con las dos.
- /api/meta regresa app_movil (la app saca sesiones guardadas de otra empresa).
REQUIERE haber corrido antes fix_soporte_evidencia_app.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_apps_separadas.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "class LoginPayload(BaseModel):\n    username: str\n    password: str\n\n\n@app.post(\"/api/auth/login\")\n",
   "class LoginPayload(BaseModel):\n    username: str\n    password: str\n    app: Optional[str] = None  # la app móvil que entra: 'markinc' | 'peymar' (la web no lo manda)\n\n\n@app.post(\"/api/auth/login\")\n"
  ],
  [
   "        raise HTTPException(status_code=401, detail=\"Usuario o contraseña incorrectos\")\n    if usuario.get(\"acceso_app\") is False:\n        raise HTTPException(status_code=403, detail=\"Todavía no tienes acceso a la app. Pídele al administrador tu usuario.\")\n    token = auth.crear_token(usuario)\n    return {\n        \"token\": token,\n",
   "        raise HTTPException(status_code=401, detail=\"Usuario o contraseña incorrectos\")\n    if usuario.get(\"acceso_app\") is False:\n        raise HTTPException(status_code=403, detail=\"Todavía no tienes acceso a la app. Pídele al administrador tu usuario.\")\n    if payload.app in db.APPS_MOVILES and usuario.get(\"empresa_id\") and usuario[\"rol\"] != \"superadmin\":\n        suya = db.app_movil_empresa(usuario[\"empresa_id\"])\n        if suya != payload.app:\n            raise HTTPException(status_code=403, detail=f\"Tu cuenta es de otra empresa: entra con la app {db.APPS_MOVILES[suya]}.\")\n    token = auth.crear_token(usuario)\n    return {\n        \"token\": token,\n"
  ],
  [
   "    admin_username: str = Field(min_length=3, max_length=40)\n    admin_password: str = Field(min_length=6)\n    admin_nombre: str = Field(min_length=1, max_length=120)\n\n\nclass ActualizacionEmpresa(BaseModel):\n    nombre: Optional[str] = None\n    activo: Optional[bool] = None\n    datos_pago_cotizacion: Optional[str] = None\n\n\nclass ModulosEmpresaIn(BaseModel):\n",
   "    admin_username: str = Field(min_length=3, max_length=40)\n    admin_password: str = Field(min_length=6)\n    admin_nombre: str = Field(min_length=1, max_length=120)\n    app_movil: Optional[str] = None  # 'markinc' | 'peymar' (sin elegir: por el nombre)\n\n\nclass ActualizacionEmpresa(BaseModel):\n    nombre: Optional[str] = None\n    activo: Optional[bool] = None\n    datos_pago_cotizacion: Optional[str] = None\n    app_movil: Optional[str] = None\n\n\ndef _validar_app_movil(app):\n    if app is not None and app not in db.APPS_MOVILES:\n        raise HTTPException(status_code=400, detail=\"App móvil inválida (markinc o peymar)\")\n\n\nclass ModulosEmpresaIn(BaseModel):\n"
  ],
  [
   "def crear_empresa(payload: NuevaEmpresa, _: dict = Depends(requiere_superadmin)):\n    if db.obtener_usuario_por_username(payload.admin_username):\n        raise HTTPException(status_code=400, detail=\"Ese nombre de usuario ya está en uso\")\n    empresa_id = db.crear_empresa(payload.nombre.strip(), payload.admin_username.strip(), payload.admin_password, payload.admin_nombre.strip())\n    return db.obtener_empresa(empresa_id)\n\n\n",
   "def crear_empresa(payload: NuevaEmpresa, _: dict = Depends(requiere_superadmin)):\n    if db.obtener_usuario_por_username(payload.admin_username):\n        raise HTTPException(status_code=400, detail=\"Ese nombre de usuario ya está en uso\")\n    _validar_app_movil(payload.app_movil)\n    empresa_id = db.crear_empresa(payload.nombre.strip(), payload.admin_username.strip(), payload.admin_password, payload.admin_nombre.strip())\n    if payload.app_movil:\n        db.guardar_app_movil_empresa(empresa_id, payload.app_movil)\n    return db.obtener_empresa(empresa_id)\n\n\n"
  ],
  [
   "def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):\n    if not db.obtener_empresa(empresa_id):\n        raise HTTPException(status_code=404, detail=\"Empresa no encontrada\")\n    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo, payload.datos_pago_cotizacion)\n    return db.obtener_empresa(empresa_id)\n\n\n",
   "def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):\n    if not db.obtener_empresa(empresa_id):\n        raise HTTPException(status_code=404, detail=\"Empresa no encontrada\")\n    _validar_app_movil(payload.app_movil)\n    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo, payload.datos_pago_cotizacion)\n    if payload.app_movil:\n        db.guardar_app_movil_empresa(empresa_id, payload.app_movil)\n    return db.obtener_empresa(empresa_id)\n\n\n"
  ],
  [
   "        \"categorias\": [c[\"nombre\"] for c in db.listar_categorias(usuario[\"empresa_id\"])],\n        \"empresa_nombre\": empresa[\"nombre\"] if empresa else \"\",\n        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        \"apariencia\": {\n            \"tema\": (empresa.get(\"tema\") if empresa else None) or \"oscuro\",\n            \"color_acento\": empresa.get(\"color_acento\") if empresa else None,\n",
   "        \"categorias\": [c[\"nombre\"] for c in db.listar_categorias(usuario[\"empresa_id\"])],\n        \"empresa_nombre\": empresa[\"nombre\"] if empresa else \"\",\n        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        \"app_movil\": db.app_movil_empresa(usuario[\"empresa_id\"]) if usuario.get(\"empresa_id\") else None,\n        \"apariencia\": {\n            \"tema\": (empresa.get(\"tema\") if empresa else None) or \"oscuro\",\n            \"color_acento\": empresa.get(\"color_acento\") if empresa else None,\n"
  ]
 ],
 "backend/db.py": [
  [
   "        -- cada cotización (justo después del total) para que el cliente\n        -- sepa cómo pagar si la acepta.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS datos_pago_cotizacion TEXT;\n        -- Cuentas bancarias de Mark·Inc en el PDF de las cotizaciones (solo si\n        -- nunca se han capturado; después se editan en Administrar -> Empresas).\n        UPDATE empresas SET datos_pago_cotizacion = 'BBVA Bancomer\n",
   "        -- cada cotización (justo después del total) para que el cliente\n        -- sepa cómo pagar si la acepta.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS datos_pago_cotizacion TEXT;\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS app_movil TEXT;\n        -- Cuentas bancarias de Mark·Inc en el PDF de las cotizaciones (solo si\n        -- nunca se han capturado; después se editan en Administrar -> Empresas).\n        UPDATE empresas SET datos_pago_cotizacion = 'BBVA Bancomer\n"
  ],
  [
   "    columnas_modulos = \", \".join(MODULOS_EMPRESA.keys())\n    cur.execute(f\"\"\"SELECT id, nombre, logo_base64, activo, creado_en, datos_pago_cotizacion, {columnas_modulos},\n                           modulo_bienvenida, bienvenida_nombre, bienvenida_texto,\n                           rh_sin_microsip, bienvenida_obligatoria FROM empresas ORDER BY nombre\"\"\")\n    rows = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    return rows\n\n\ndef obtener_config_microsip(empresa_id):\n",
   "    columnas_modulos = \", \".join(MODULOS_EMPRESA.keys())\n    cur.execute(f\"\"\"SELECT id, nombre, logo_base64, activo, creado_en, datos_pago_cotizacion, {columnas_modulos},\n                           modulo_bienvenida, bienvenida_nombre, bienvenida_texto,\n                           rh_sin_microsip, bienvenida_obligatoria, app_movil FROM empresas ORDER BY nombre\"\"\")\n    rows = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    for r in rows:\n        r[\"app_movil\"] = app_movil_de(r)\n    return rows\n\n\n# ---- App móvil de cada empresa: los usuarios de Mark·Inc entran solo con la\n# app Mark·Inc y los de Peymar solo con la app Peymar. Sin elegir (NULL), se\n# deduce del nombre de la empresa. El superadmin entra con las dos.\nAPPS_MOVILES = {\"markinc\": \"Mark·Inc\", \"peymar\": \"Peymar\"}\n\n\ndef app_movil_de(empresa):\n    if not empresa:\n        return \"markinc\"\n    elegida = (empresa.get(\"app_movil\") or \"\").strip()\n    if elegida in APPS_MOVILES:\n        return elegida\n    return \"peymar\" if \"peymar\" in (empresa.get(\"nombre\") or \"\").lower() else \"markinc\"\n\n\ndef app_movil_empresa(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT nombre, app_movil FROM empresas WHERE id = %s\", (empresa_id,))\n    r = cur.fetchone()\n    cur.close(); conn.close()\n    return app_movil_de(dict(r) if r else None)\n\n\ndef guardar_app_movil_empresa(empresa_id, app):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE empresas SET app_movil = %s WHERE id = %s\", (app, empresa_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef obtener_config_microsip(empresa_id):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      ${e.logo_base64 ? `<img src=\"${e.logo_base64}\" class=\"empresa-logo-chico\" />` : '<div class=\"empresa-logo-chico empresa-logo-vacio\">?</div>'}\n      <div class=\"empresa-info\">\n        <div class=\"empresa-nombre\">${escapeHtml(e.nombre)}</div>\n        <div class=\"empresa-fecha\">Creada ${e.creado_en.slice(0,10)}</div>\n      </div>\n      <details class=\"menu-desplegable\">\n        <summary>⋮ Acciones</summary>\n",
   "      ${e.logo_base64 ? `<img src=\"${e.logo_base64}\" class=\"empresa-logo-chico\" />` : '<div class=\"empresa-logo-chico empresa-logo-vacio\">?</div>'}\n      <div class=\"empresa-info\">\n        <div class=\"empresa-nombre\">${escapeHtml(e.nombre)}</div>\n        <div class=\"empresa-fecha\">Creada ${e.creado_en.slice(0,10)} · 📱 App ${e.app_movil === 'peymar' ? 'Peymar' : 'Mark·Inc'}</div>\n      </div>\n      <details class=\"menu-desplegable\">\n        <summary>⋮ Acciones</summary>\n"
  ],
  [
   "  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Módulos de ${escapeHtml(nombre)}</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">Apaga aquí los módulos que esta empresa no necesite — quedan invisibles para TODOS sus usuarios, sin importar el permiso individual de cada quien.</p>\n    ${MODULOS_EMPRESA_CONFIG.map(m => `\n      <label style=\"font-size:13px; display:flex; align-items:center; gap:8px; padding:6px 0; ${m.siempre ? 'opacity:0.6;' : ''}\">\n",
   "  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Módulos de ${escapeHtml(nombre)}</h2>\n    <div class=\"field\"><label>📱 App móvil de sus usuarios (solo entran con esa app; tú entras con las dos)</label>\n      <select id=\"mod_app_movil\"><option value=\"markinc\" ${empresa.app_movil !== 'peymar' ? 'selected' : ''}>Mark·Inc</option><option value=\"peymar\" ${empresa.app_movil === 'peymar' ? 'selected' : ''}>Peymar</option></select>\n    </div>\n    <p style=\"font-size:12px; color:var(--muted);\">Apaga aquí los módulos que esta empresa no necesite — quedan invisibles para TODOS sus usuarios, sin importar el permiso individual de cada quien.</p>\n    ${MODULOS_EMPRESA_CONFIG.map(m => `\n      <label style=\"font-size:13px; display:flex; align-items:center; gap:8px; padding:6px 0; ${m.siempre ? 'opacity:0.6;' : ''}\">\n"
  ],
  [
   "  });\n  try {\n    await api(`/api/empresas/${id}/modulos`, { method: 'PATCH', body: JSON.stringify(payload) });\n    await api(`/api/empresas/${id}/bienvenida`, { method: 'PATCH', body: JSON.stringify({\n      activa: document.getElementById('mod_bienvenida_activa').checked,\n      nombre: document.getElementById('mod_bienvenida_nombre').value.trim() || null,\n",
   "  });\n  try {\n    await api(`/api/empresas/${id}/modulos`, { method: 'PATCH', body: JSON.stringify(payload) });\n    await api(`/api/empresas/${id}`, { method: 'PATCH', body: JSON.stringify({ app_movil: document.getElementById('mod_app_movil').value }) });\n    await api(`/api/empresas/${id}/bienvenida`, { method: 'PATCH', body: JSON.stringify({\n      activa: document.getElementById('mod_bienvenida_activa').checked,\n      nombre: document.getElementById('mod_bienvenida_nombre').value.trim() || null,\n"
  ],
  [
   "      <div class=\"field\"><label>Contraseña</label><input id=\"emp_admin_pass\" type=\"password\" autocomplete=\"new-password\" /></div>\n    </div>\n    <div class=\"field\"><label>Nombre completo del administrador</label><input id=\"emp_admin_nombre\" autocomplete=\"off\" /></div>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Módulos que usará esta empresa</label>\n    <p style=\"font-size:11px; color:var(--muted); margin:4px 0 8px;\">Puedes cambiar esto después desde el botón \"Módulos\" de cada empresa.</p>\n    ${MODULOS_EMPRESA_CONFIG.map(m => `\n",
   "      <div class=\"field\"><label>Contraseña</label><input id=\"emp_admin_pass\" type=\"password\" autocomplete=\"new-password\" /></div>\n    </div>\n    <div class=\"field\"><label>Nombre completo del administrador</label><input id=\"emp_admin_nombre\" autocomplete=\"off\" /></div>\n    <div class=\"field\"><label>📱 App móvil de sus usuarios</label><select id=\"emp_app_movil\"><option value=\"markinc\">Mark·Inc</option><option value=\"peymar\">Peymar</option></select></div>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Módulos que usará esta empresa</label>\n    <p style=\"font-size:11px; color:var(--muted); margin:4px 0 8px;\">Puedes cambiar esto después desde el botón \"Módulos\" de cada empresa.</p>\n    ${MODULOS_EMPRESA_CONFIG.map(m => `\n"
  ],
  [
   "    admin_username: document.getElementById('emp_admin_user').value.trim(),\n    admin_password: document.getElementById('emp_admin_pass').value,\n    admin_nombre: document.getElementById('emp_admin_nombre').value.trim(),\n  };\n  if (!payload.nombre || !payload.admin_username || payload.admin_password.length < 6 || !payload.admin_nombre) {\n    document.getElementById('empresaError').textContent = 'Revisa los campos (contraseña mínimo 6 caracteres)';\n",
   "    admin_username: document.getElementById('emp_admin_user').value.trim(),\n    admin_password: document.getElementById('emp_admin_pass').value,\n    admin_nombre: document.getElementById('emp_admin_nombre').value.trim(),\n    app_movil: document.getElementById('emp_app_movil').value,\n  };\n  if (!payload.nombre || !payload.admin_username || payload.admin_password.length < 6 || !payload.admin_nombre) {\n    document.getElementById('empresaError').textContent = 'Revisa los campos (contraseña mínimo 6 caracteres)';\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_apps_separadas.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "Las apps suben sin tipo: se deduce del nombre" not in f.read():
            print("Primero corre fix_soporte_evidencia_app.py (y los anteriores), y luego este.")
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
