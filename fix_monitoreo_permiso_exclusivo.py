# -*- coding: utf-8 -*-
"""
Monitoreo como módulo con permiso exclusivo (igual que "Datos RH")

Hasta ahora, la pestaña 🕵️ Monitoreo la veía CUALQUIER usuario con
rol=admin, sin permiso aparte. Este cambio la vuelve igual de restringida
que "Datos RH": un permiso nuevo, acceso_monitoreo, cerrado por default
incluso para administradores — nadie lo tiene hasta que tú se lo des,
usuario por usuario, desde Administrar → Accesos (o al editar a la
persona). Es un mecanismo general (no exclusivo de una empresa): cada
empresa decide a quién se lo da.

Qué toca:
1. backend/db.py — columna nueva acceso_monitoreo en users (default
   FALSE), incluida en listar_usuarios/obtener_permisos_usuario, y
   actualizable desde actualizar_usuario.
2. backend/app.py — nueva dependencia requiere_acceso_monitoreo (mismo
   patrón que requiere_datos_empleado_rh), usada en los 4 endpoints de
   /api/monitoreo/* que antes solo pedían ser admin; se agrega también
   al modelo de edición de usuario, al PATCH, y a /api/meta.
3. frontend/index.html — la pestaña Monitoreo y su contenido ahora se
   muestran según el permiso nuevo (no según ser admin); columna "Ver
   Monitoreo" en la tabla de Accesos y checkbox en editar usuario.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_monitoreo_permiso_exclusivo.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------
# backend/db.py
# ---------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    # 1) Columna nueva, junto a la de Datos RH.
    [
        '''        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_datos_empleado_rh BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_shopify BOOLEAN NOT NULL DEFAULT TRUE;
''',
        '''        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_datos_empleado_rh BOOLEAN NOT NULL DEFAULT FALSE;
        -- Ver la pestaña 🕵️ Monitoreo (bitácora de actividad de empleados)
        -- es igual de sensible que Datos RH — permiso aparte, cerrado por
        -- default incluso para administradores, para dárselo solo a quien
        -- deba verlo. Aplica a cualquier empresa (no es exclusivo de una).
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_monitoreo BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_shopify BOOLEAN NOT NULL DEFAULT TRUE;
''',
    ],
    # 2) listar_usuarios (tabla de Accesos).
    [
        '''                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_shopify, u.monitoreo_activo,
''',
        '''                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_monitoreo, u.acceso_shopify, u.monitoreo_activo,
''',
    ],
    # 3) obtener_permisos_usuario (permisos vigentes de sesión).
    [
        '''                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_shopify, monitoreo_activo
           FROM users WHERE id = %s""",
''',
        '''                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_monitoreo, acceso_shopify, monitoreo_activo
           FROM users WHERE id = %s""",
''',
    ],
    # 4) actualizar_usuario: parámetro nuevo.
    [
        '''                        acceso_datos_empleado_rh=None, acceso_shopify=None,
                        monitoreo_activo=None,
''',
        '''                        acceso_datos_empleado_rh=None, acceso_monitoreo=None, acceso_shopify=None,
                        monitoreo_activo=None,
''',
    ],
    # 5) actualizar_usuario: aplicar el campo al UPDATE.
    [
        '''    if acceso_datos_empleado_rh is not None:
        campos.append("acceso_datos_empleado_rh = %s"); valores.append(acceso_datos_empleado_rh)
    if acceso_shopify is not None:
''',
        '''    if acceso_datos_empleado_rh is not None:
        campos.append("acceso_datos_empleado_rh = %s"); valores.append(acceso_datos_empleado_rh)
    if acceso_monitoreo is not None:
        campos.append("acceso_monitoreo = %s"); valores.append(acceso_monitoreo)
    if acceso_shopify is not None:
''',
    ],
]

# ---------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    # 1) Nueva dependencia, mismo patrón que requiere_datos_empleado_rh.
    [
        '''def requiere_acceso_shopify(usuario: dict = Depends(requiere_empresa)) -> dict:
''',
        '''def requiere_acceso_monitoreo(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Ver la bitácora de monitoreo de empleados (pestaña 🕵️ Monitoreo) —
    permiso aparte, para dárselo SOLO a quien deba verlo, ni siquiera a
    otros administradores por default (mismo patrón que 'Datos RH')."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_monitoreo", False):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Monitoreo")
    return usuario


def requiere_acceso_shopify(usuario: dict = Depends(requiere_empresa)) -> dict:
''',
    ],
    # 2) Generar token del agente — ahora pide el permiso nuevo, no ser admin.
    [
        '''@app.post("/api/monitoreo/usuarios/{usuario_id}/token")
def api_generar_token_monitoreo(usuario_id: int, admin: dict = Depends(requiere_admin)):
''',
        '''@app.post("/api/monitoreo/usuarios/{usuario_id}/token")
def api_generar_token_monitoreo(usuario_id: int, admin: dict = Depends(requiere_acceso_monitoreo)):
''',
    ],
    # 3) Listar eventos / computadoras / estado — mismo cambio.
    [
        '''                                  fecha_fin: Optional[str] = None, admin: dict = Depends(requiere_admin)):
    """Bitácora de monitoreo — filtrable por persona/computadora/tipo/fecha."""
    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo, fecha_inicio, fecha_fin)


@app.get("/api/monitoreo/computadoras")
def api_listar_computadoras_monitoreo(admin: dict = Depends(requiere_admin)):
    """Nombres de computadoras que ya han mandado algún evento, para el
    filtro de la bitácora."""
    return db.listar_computadoras_monitoreo(admin["empresa_id"])


@app.get("/api/monitoreo/estado")
def api_estado_monitoreo(admin: dict = Depends(requiere_admin)):
''',
        '''                                  fecha_fin: Optional[str] = None, admin: dict = Depends(requiere_acceso_monitoreo)):
    """Bitácora de monitoreo — filtrable por persona/computadora/tipo/fecha."""
    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo, fecha_inicio, fecha_fin)


@app.get("/api/monitoreo/computadoras")
def api_listar_computadoras_monitoreo(admin: dict = Depends(requiere_acceso_monitoreo)):
    """Nombres de computadoras que ya han mandado algún evento, para el
    filtro de la bitácora."""
    return db.listar_computadoras_monitoreo(admin["empresa_id"])


@app.get("/api/monitoreo/estado")
def api_estado_monitoreo(admin: dict = Depends(requiere_acceso_monitoreo)):
''',
    ],
    # 4) Modelo de edición de usuario: campo nuevo.
    [
        '''    acceso_datos_empleado_rh: Optional[bool] = None
    acceso_shopify: Optional[bool] = None
    monitoreo_activo: Optional[bool] = None
''',
        '''    acceso_datos_empleado_rh: Optional[bool] = None
    acceso_monitoreo: Optional[bool] = None
    acceso_shopify: Optional[bool] = None
    monitoreo_activo: Optional[bool] = None
''',
    ],
    # 5) PATCH /api/usuarios/{id}: pasar el campo nuevo a la BD.
    [
        '''                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,
                           acceso_shopify=payload.acceso_shopify,
''',
        '''                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,
                           acceso_monitoreo=payload.acceso_monitoreo,
                           acceso_shopify=payload.acceso_shopify,
''',
    ],
    # 6) /api/meta: exponer el permiso al frontend (mis_permisos).
    [
        '''            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),
            "acceso_shopify": usuario.get("acceso_shopify", True),
''',
        '''            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),
            "acceso_monitoreo": usuario.get("acceso_monitoreo", False),
            "acceso_shopify": usuario.get("acceso_shopify", True),
''',
    ],
]

# ---------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # 1) Variable nueva en renderAdmin().
    [
        '''async function renderAdmin() {
  const esAdmin = SESION.usuario.rol === 'admin';
  const tabs = `
''',
        '''async function renderAdmin() {
  const esAdmin = SESION.usuario.rol === 'admin';
  const puedeVerMonitoreo = !!META.mis_permisos.acceso_monitoreo;
  const tabs = `
''',
    ],
    # 2) Botón de la pestaña: ahora según el permiso nuevo, no esAdmin.
    [
        '''      ${esAdmin ? `<button class="admin-tab ${ADMIN_TAB==='monitoreo'?'active':''}" onclick="cambiarAdminTab('monitoreo')">🕵️ Monitoreo</button>` : ''}
''',
        '''      ${puedeVerMonitoreo ? `<button class="admin-tab ${ADMIN_TAB==='monitoreo'?'active':''}" onclick="cambiarAdminTab('monitoreo')">🕵️ Monitoreo</button>` : ''}
''',
    ],
    # 3) Rama que renderiza el contenido de la pestaña: mismo cambio.
    [
        '''  } else if (ADMIN_TAB === 'monitoreo' && esAdmin) {
''',
        '''  } else if (ADMIN_TAB === 'monitoreo' && puedeVerMonitoreo) {
''',
    ],
    # 4) Encabezado nuevo en la tabla de Accesos ("Ver Monitoreo").
    [
        '''        <th class="col-check">Compras${casillaTodoColumna('acceso_compras')}</th><th class="col-check">RH${casillaTodoColumna('acceso_rh')}</th><th class="col-check">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class="col-check">CRM${casillaTodoColumna('acceso_crm')}</th><th class="col-check">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th>
''',
        '''        <th class="col-check">Compras${casillaTodoColumna('acceso_compras')}</th><th class="col-check">RH${casillaTodoColumna('acceso_rh')}</th><th class="col-check">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class="col-check">CRM${casillaTodoColumna('acceso_crm')}</th><th class="col-check">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class="col-check" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad) — distinto de la columna 'Monitoreo' de más adelante, que es si a ESA persona se le vigila">Ver Monitoreo${casillaTodoColumna('acceso_monitoreo')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th>
''',
    ],
    # 5) Celda nueva por usuario en esa misma tabla.
    [
        '''            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_datos_empleado_rh', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_shopify', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>
''',
        '''            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_datos_empleado_rh', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_monitoreo ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_monitoreo', this)" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad de empleados)" data-campo="acceso_monitoreo" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_shopify', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>
''',
    ],
    # 6) Checkbox nuevo en el modal de editar usuario.
    [
        '''        <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="e_acceso_datos_empleado_rh" ${u.acceso_datos_empleado_rh ? 'checked' : ''} /> Ver datos sensibles de empleados en RH (salario, Microsip)
        </label>
        <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="e_acceso_shopify" ${u.acceso_shopify ? 'checked' : ''} /> Acceso al módulo de 🛍️ Shopify
        </label>
''',
        '''        <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="e_acceso_datos_empleado_rh" ${u.acceso_datos_empleado_rh ? 'checked' : ''} /> Ver datos sensibles de empleados en RH (salario, Microsip)
        </label>
        <label style="font-size:12px; display:flex; align-items:center; gap:6px;" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad de empleados)">
          <input type="checkbox" id="e_acceso_monitoreo" ${u.acceso_monitoreo ? 'checked' : ''} /> Ver módulo de 🕵️ Monitoreo
        </label>
        <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="e_acceso_shopify" ${u.acceso_shopify ? 'checked' : ''} /> Acceso al módulo de 🛍️ Shopify
        </label>
''',
    ],
    # 7) Guardar edición: mandar el campo nuevo en el payload.
    [
        '''    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;
    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;
''',
        '''    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;
    payload.acceso_monitoreo = document.getElementById('e_acceso_monitoreo').checked;
    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;
''',
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
    print("   git add backend/db.py backend/app.py frontend/index.html")
    print('   git commit -m "Monitoreo: permiso exclusivo (como Datos RH), ya no lo ve cualquier admin"')
    print("   git push")
    print()
    print("Después, en Administrar -> Accesos, dale la casilla \"Ver Monitoreo\"")
    print("solo a quien deba ver esa pestaña (nadie la tiene al inicio, ni los")
    print("administradores).")


if __name__ == "__main__":
    main()
