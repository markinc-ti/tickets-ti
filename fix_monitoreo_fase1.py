# -*- coding: utf-8 -*-
"""
Fase 1 de "Monitoreo de empleados": consentimiento digital y activación
selectiva por usuario. Nada de esto instala ningún programa todavía —
solo prepara la app para cuando llegue el agente de Windows (Fase 2).

Qué hace:
1. Nueva columna users.monitoreo_activo (por defecto apagada) y tabla
   consentimientos_monitoreo (queda el registro de quién aceptó y cuándo).
2. Nuevo checkbox "Monitoreo" en Administrar → Accesos (mismo mecanismo
   que ya usan los demás módulos) — actívalo solo para quien tú decidas.
3. Cuando un usuario con monitoreo activo entra a la app y todavía no ha
   aceptado, le sale una pantalla bloqueante con el aviso — no puede
   seguir usando la app sin aceptar. Queda guardada la fecha/hora e IP
   como prueba.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_monitoreo_fase1.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/db.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    # 1) Migración: nueva columna + nueva tabla.
    [
        '    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = \'superadmin\'")',

        '    # ---- Monitoreo de empleados (Fase 1: consentimiento + activación) ----\n'
        '    cur.execute("""\n'
        '        ALTER TABLE users ADD COLUMN IF NOT EXISTS monitoreo_activo BOOLEAN NOT NULL DEFAULT FALSE;\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS consentimientos_monitoreo (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            usuario_id INTEGER NOT NULL REFERENCES users(id),\n'
        '            fecha_aceptacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n'
        '            ip_address TEXT\n'
        '        );\n'
        '    """)\n'
        '    conn.commit()\n'
        '\n'
        '    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = \'superadmin\'")',
    ],
    # 2) listar_usuarios: agregar monitoreo_activo + fecha de aceptación.
    [
        '        """SELECT u.id, u.username, u.nombre_completo, u.rol, u.puesto, u.telefono_whatsapp, u.activo, u.creado_en,\n'
        '                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n'
        '                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_entregas,\n'
        '                  u.acceso_checador_precio, u.acceso_marketing,\n'
        '                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,\n'
        '                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n'
        '           FROM users u\n'
        '           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n'
        '           WHERE u.empresa_id = %s ORDER BY u.nombre_completo""",',

        '        """SELECT u.id, u.username, u.nombre_completo, u.rol, u.puesto, u.telefono_whatsapp, u.activo, u.creado_en,\n'
        '                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n'
        '                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_entregas,\n'
        '                  u.acceso_checador_precio, u.acceso_marketing, u.monitoreo_activo,\n'
        '                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,\n'
        '                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,\n'
        '                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n'
        '           FROM users u\n'
        '           LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n'
        '           WHERE u.empresa_id = %s ORDER BY u.nombre_completo""",',
    ],
    # 3) actualizar_usuario: firma + manejo del nuevo campo.
    [
        '                        acceso_checador_precio=None, acceso_marketing=None,\n'
        '                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",',

        '                        acceso_checador_precio=None, acceso_marketing=None, monitoreo_activo=None,\n'
        '                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",',
    ],
    [
        '    if acceso_marketing is not None:\n'
        '        campos.append("acceso_marketing = %s"); valores.append(acceso_marketing)\n'
        '    if sucursal_id != "__sin_cambio__":',

        '    if acceso_marketing is not None:\n'
        '        campos.append("acceso_marketing = %s"); valores.append(acceso_marketing)\n'
        '    if monitoreo_activo is not None:\n'
        '        campos.append("monitoreo_activo = %s"); valores.append(monitoreo_activo)\n'
        '    if sucursal_id != "__sin_cambio__":',
    ],
    # 4) Nuevas funciones, justo después de actualizar_usuario.
    [
        'def eliminar_usuario(usuario_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("UPDATE users SET activo = FALSE WHERE id = %s", (usuario_id,))\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n',

        '# ---- Monitoreo de empleados ----\n'
        '\n'
        'def usuario_acepto_monitoreo(usuario_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT 1 FROM consentimientos_monitoreo WHERE usuario_id = %s LIMIT 1", (usuario_id,))\n'
        '    existe = cur.fetchone() is not None\n'
        '    cur.close(); conn.close()\n'
        '    return existe\n'
        '\n'
        '\n'
        'def registrar_aceptacion_monitoreo(usuario_id, ip_address):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute(\n'
        '        "INSERT INTO consentimientos_monitoreo (usuario_id, ip_address) VALUES (%s, %s)",\n'
        '        (usuario_id, ip_address),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def eliminar_usuario(usuario_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("UPDATE users SET activo = FALSE WHERE id = %s", (usuario_id,))\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    # 1) Importar Request.
    [
        'from fastapi import FastAPI, HTTPException, Depends, UploadFile, File\n',
        'from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request\n',
    ],
    # 2) Nuevo campo en el modelo de actualización de usuario.
    [
        '    acceso_marketing: Optional[bool] = None\n'
        '    sucursal_id: Optional[int] = None\n',

        '    acceso_marketing: Optional[bool] = None\n'
        '    monitoreo_activo: Optional[bool] = None\n'
        '    sucursal_id: Optional[int] = None\n',
    ],
    # 3) Pasar el nuevo campo a db.actualizar_usuario.
    [
        '                           acceso_checador_precio=payload.acceso_checador_precio,\n'
        '                           acceso_marketing=payload.acceso_marketing,\n'
        '                           **kwargs_extra)',

        '                           acceso_checador_precio=payload.acceso_checador_precio,\n'
        '                           acceso_marketing=payload.acceso_marketing,\n'
        '                           monitoreo_activo=payload.monitoreo_activo,\n'
        '                           **kwargs_extra)',
    ],
    # 4) /api/meta: agregar el estado de monitoreo del usuario en sesión.
    [
        '        "mi_departamento": db.obtener_departamento_usuario(usuario["id"]) if usuario["rol"] != "master" else None,',

        '        "monitoreo": {\n'
        '            "activo": usuario.get("monitoreo_activo", False),\n'
        '            "acepto": (not usuario.get("monitoreo_activo", False)) or db.usuario_acepto_monitoreo(usuario["id"]),\n'
        '        },\n'
        '        "mi_departamento": db.obtener_departamento_usuario(usuario["id"]) if usuario["rol"] != "master" else None,',
    ],
    # 5) Nuevo endpoint para aceptar el aviso.
    [
        '@app.get("/api/usuarios/tecnicos")\n'
        'def api_listar_tecnicos(usuario: dict = Depends(requiere_empresa)):\n'
        '    return db.listar_tecnicos_activos(usuario["empresa_id"])\n',

        '@app.post("/api/monitoreo/aceptar")\n'
        'def api_aceptar_monitoreo(request: Request, usuario: dict = Depends(requiere_empresa_o_master)):\n'
        '    """El usuario acepta el aviso de monitoreo — queda registrado con\n'
        '    fecha/hora e IP como prueba. Se puede llamar sin que el monitoreo\n'
        '    esté activo (no pasa nada raro), aunque normalmente solo se llama\n'
        '    desde la pantalla de aviso que solo sale si sí está activo."""\n'
        '    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else None)\n'
        '    db.registrar_aceptacion_monitoreo(usuario["id"], ip)\n'
        '    return {"ok": True}\n'
        '\n'
        '\n'
        '@app.get("/api/usuarios/tecnicos")\n'
        'def api_listar_tecnicos(usuario: dict = Depends(requiere_empresa)):\n'
        '    return db.listar_tecnicos_activos(usuario["empresa_id"])\n',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # 1) Nueva pantalla bloqueante de aviso, justo después del login.
    [
        '<div id="dashboardScreen" style="display:none;">',

        '<div id="avisoMonitoreoScreen" class="login-wrap" style="display:none;">\n'
        '  <div class="login-box" style="max-width:520px;">\n'
        '    <h1>Aviso de monitoreo</h1>\n'
        '    <p style="font-size:13px; color:var(--text); line-height:1.6; margin:10px 0;">\n'
        '      Esta computadora y tu cuenta de trabajo están sujetas a monitoreo por parte de la empresa,\n'
        '      con fines de seguridad y control interno. Esto puede incluir el registro de páginas web que\n'
        '      visitas, programas que abres, y documentos que modificas mientras usas equipo de la empresa.\n'
        '    </p>\n'
        '    <p style="font-size:13px; color:var(--text); line-height:1.6; margin:10px 0;">\n'
        '      Este monitoreo aplica solo a tu actividad relacionada con el trabajo, en equipo de la empresa.\n'
        '      Si tienes dudas, pregunta a tu administrador antes de continuar.\n'
        '    </p>\n'
        '    <label style="display:flex; align-items:flex-start; gap:8px; font-size:13px; margin:16px 0; cursor:pointer;">\n'
        '      <input type="checkbox" id="avisoMonitoreoCheck" style="margin-top:3px;" onchange="document.getElementById(\'btnAceptarMonitoreo\').disabled = !this.checked;" />\n'
        '      <span>He leído y entiendo este aviso, y acepto continuar bajo estas condiciones.</span>\n'
        '    </label>\n'
        '    <button class="primary" id="btnAceptarMonitoreo" disabled onclick="aceptarMonitoreo()">Aceptar y continuar</button>\n'
        '    <div id="avisoMonitoreoError" class="error-msg"></div>\n'
        '  </div>\n'
        '</div>\n'
        '\n'
        '<div id="dashboardScreen" style="display:none;">',
    ],
    # 2) Gate en iniciarApp(): justo después de cargar META.
    [
        '  await cargarMeta();\n'
        '\n'
        '  // El usuario "master" solo tiene un lugar a dónde ir: el Dashboard.',

        '  await cargarMeta();\n'
        '\n'
        '  if (META.monitoreo && META.monitoreo.activo && !META.monitoreo.acepto) {\n'
        "    document.getElementById('avisoMonitoreoScreen').style.display = 'flex';\n"
        '    return;\n'
        '  }\n'
        '\n'
        '  // El usuario "master" solo tiene un lugar a dónde ir: el Dashboard.',
    ],
    # 3) Función para aceptar el aviso.
    [
        'async function iniciarApp() {',

        "async function aceptarMonitoreo() {\n"
        "  const boton = document.getElementById('btnAceptarMonitoreo');\n"
        "  const errorDiv = document.getElementById('avisoMonitoreoError');\n"
        "  boton.disabled = true;\n"
        "  errorDiv.textContent = '';\n"
        "  try {\n"
        "    await api('/api/monitoreo/aceptar', { method: 'POST' });\n"
        "    document.getElementById('avisoMonitoreoScreen').style.display = 'none';\n"
        "    await iniciarApp();\n"
        "  } catch (e) {\n"
        "    errorDiv.textContent = e.message;\n"
        "    boton.disabled = false;\n"
        "  }\n"
        "}\n"
        "\n"
        "async function iniciarApp() {",
    ],
    # 4) Columna "Monitoreo" en Administrar → Accesos (mismo mecanismo que
    #    los demás checkboxes de acceso).
    [
        '        <th>Persona</th><th>Rol</th>\n'
        '        <th class="col-check">Tickets</th><th class="col-check">Reparaciones</th><th class="col-check">Entregas</th><th class="col-check">Precios</th><th class="col-check">Equipos</th>\n'
        '        <th class="col-check">Compras</th><th class="col-check">RH</th><th class="col-check">Marketing</th>\n'
        '        <th class="col-check">Dashboard</th><th class="col-check">Admin.</th>\n'
        '      </tr></thead>',

        '        <th>Persona</th><th>Rol</th>\n'
        '        <th class="col-check">Tickets</th><th class="col-check">Reparaciones</th><th class="col-check">Entregas</th><th class="col-check">Precios</th><th class="col-check">Equipos</th>\n'
        '        <th class="col-check">Compras</th><th class="col-check">RH</th><th class="col-check">Marketing</th>\n'
        '        <th class="col-check">Dashboard</th><th class="col-check">Admin.</th><th class="col-check">Monitoreo</th>\n'
        '      </tr></thead>',
    ],
    [
        '            ${u.rol === \'admin\' ? `\n'
        '              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_dashboard\', this)" /></td>\n'
        '              <td class="col-check"><input type="checkbox" ${u.acceso_administracion ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_administracion\', this)" /></td>\n'
        '            ` : `\n'
        '              <td class="col-check" style="color:var(--muted);">—</td>\n'
        '              <td class="col-check" style="color:var(--muted);">—</td>\n'
        '            `}\n'
        '          </tr>',

        '            ${u.rol === \'admin\' ? `\n'
        '              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_dashboard\', this)" /></td>\n'
        '              <td class="col-check"><input type="checkbox" ${u.acceso_administracion ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_administracion\', this)" /></td>\n'
        '            ` : `\n'
        '              <td class="col-check" style="color:var(--muted);">—</td>\n'
        '              <td class="col-check" style="color:var(--muted);">—</td>\n'
        '            `}\n'
        '            <td class="col-check" title="${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'Aceptó el aviso\' : \'Activo, esperando que acepte el aviso\') : \'\'}">\n'
        '              <input type="checkbox" ${u.monitoreo_activo ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'monitoreo_activo\', this)" />\n'
        '              ${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'<div style="font-size:9px; color:var(--trace);">aceptó</div>\' : \'<div style="font-size:9px; color:var(--copper);">pendiente</div>\') : \'\'}\n'
        '            </td>\n'
        '          </tr>',
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
    print("   git commit -m \"Monitoreo de empleados Fase 1: consentimiento y activacion selectiva\"")
    print("   git push")


if __name__ == "__main__":
    main()
