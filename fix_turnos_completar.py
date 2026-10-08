# -*- coding: utf-8 -*-
"""
Completar Turnos por sucursal -- parche de continuacion

Este script es SOLO para quien ya corrio fix_turnos_por_sucursal.py y le
salieron errores de "No se encontro un bloque esperado" en backend/db.py,
backend/app.py y/o frontend/index.html (con solo una parte de los cambios
aplicados, ej. "4/7 cambio(s) aplicado(s)"). NO hace falta volver a correr
fix_turnos_por_sucursal.py -- este script termina justo lo que quedo a
medias.

Por que paso: el modulo de Monitoreo (fix_monitoreo_permiso_exclusivo.py)
y el de Turnos (fix_turnos_por_sucursal.py) tocan varios de los mismos
lugares del codigo (la lista de permisos del usuario, la tabla de Accesos,
etc.). Cuando Monitoreo ya estaba aplicado, unos pocos bloques de Turnos
ya no coincidian exactamente con lo que esperaban -- por eso se aplicaron
la mayoria de los cambios pero no todos. Este script trae solo los
bloques que faltaron, ya ajustados para el archivo tal como quedo.

Que toca (los pocos bloques que faltaron):
  - backend/db.py -- acceso_turnos/ventanilla_turnos en las consultas de
    usuarios y en actualizar_usuario().
  - backend/app.py -- acceso_turnos/mi_ventanilla_turnos en /api/meta, el
    modelo de edicion de usuario, y el guardado de usuario.
  - frontend/index.html -- la columna "🎫 Turnos" en la tabla de Accesos y
    su guardado en el modal de editar usuario.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_turnos_completar.py
"""
import os
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            '            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),\n            "acceso_monitoreo": usuario.get("acceso_monitoreo", False),\n            "acceso_shopify": usuario.get("acceso_shopify", True),\n            "acceso_dashboard": usuario.get("acceso_dashboard", True) if es_admin else True,\n            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,\n        },\n',
            '            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),\n            "acceso_monitoreo": usuario.get("acceso_monitoreo", False),\n            "acceso_shopify": usuario.get("acceso_shopify", True),\n            "acceso_turnos": usuario.get("acceso_turnos", True),\n            "acceso_dashboard": usuario.get("acceso_dashboard", True) if es_admin else True,\n            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,\n        },\n',
        ],
        [
            '        },\n        "mi_departamento": db.obtener_departamento_usuario(usuario["id"]) if usuario["rol"] != "master" else None,\n        "mi_sucursal_id": db.obtener_sucursal_id_usuario(usuario["id"]) if usuario["rol"] != "master" else None,\n        "terminos": db.obtener_terminos(usuario["empresa_id"]) if usuario["rol"] != "master" else {},\n    }\n\n',
            '        },\n        "mi_departamento": db.obtener_departamento_usuario(usuario["id"]) if usuario["rol"] != "master" else None,\n        "mi_sucursal_id": db.obtener_sucursal_id_usuario(usuario["id"]) if usuario["rol"] != "master" else None,\n        "mi_ventanilla_turnos": usuario.get("ventanilla_turnos"),\n        "terminos": db.obtener_terminos(usuario["empresa_id"]) if usuario["rol"] != "master" else {},\n    }\n\n',
        ],
        [
            '    acceso_datos_empleado_rh: Optional[bool] = None\n    acceso_monitoreo: Optional[bool] = None\n    acceso_shopify: Optional[bool] = None\n    monitoreo_activo: Optional[bool] = None\n    sucursal_id: Optional[int] = None\n    numero_empleado: Optional[str] = None\n',
            '    acceso_datos_empleado_rh: Optional[bool] = None\n    acceso_monitoreo: Optional[bool] = None\n    acceso_shopify: Optional[bool] = None\n    acceso_turnos: Optional[bool] = None\n    ventanilla_turnos: Optional[str] = None\n    monitoreo_activo: Optional[bool] = None\n    sucursal_id: Optional[int] = None\n    numero_empleado: Optional[str] = None\n',
        ],
        [
            '                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,\n                           acceso_monitoreo=payload.acceso_monitoreo,\n                           acceso_shopify=payload.acceso_shopify,\n                           monitoreo_activo=payload.monitoreo_activo,\n                           **kwargs_extra)\n    return {"ok": True}\n',
            '                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,\n                           acceso_monitoreo=payload.acceso_monitoreo,\n                           acceso_shopify=payload.acceso_shopify,\n                           acceso_turnos=payload.acceso_turnos,\n                           monitoreo_activo=payload.monitoreo_activo,\n                           **kwargs_extra)\n    return {"ok": True}\n',
        ],
    ],
    'backend/db.py': [
        [
            '                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_entregas,\n                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_monitoreo, u.acceso_shopify, u.monitoreo_activo,\n                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,\n                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,\n                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n',
            '                  u.restriccion_categoria, u.acceso_equipos, u.acceso_administracion, u.acceso_compras,\n                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_entregas,\n                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_monitoreo, u.acceso_shopify, u.monitoreo_activo,\n                  u.acceso_turnos, u.ventanilla_turnos,\n                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,\n                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,\n                  u.rfc, u.curp, u.numero_licencia, u.tipo_licencia, u.vigencia_licencia\n',
        ],
        [
            '    cur.execute(\n        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_entregas, acceso_checador_precio,\n                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_monitoreo, acceso_shopify, monitoreo_activo\n           FROM users WHERE id = %s""",\n        (usuario_id,),\n    )\n',
            '    cur.execute(\n        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_entregas, acceso_checador_precio,\n                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_monitoreo, acceso_shopify, monitoreo_activo,\n                  acceso_turnos, ventanilla_turnos\n           FROM users WHERE id = %s""",\n        (usuario_id,),\n    )\n',
        ],
        [
            '                        acceso_administracion=None, acceso_compras=None, acceso_rh=None, acceso_dashboard=None,\n                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,\n                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,\n                        acceso_datos_empleado_rh=None, acceso_monitoreo=None, acceso_shopify=None,\n                        monitoreo_activo=None,\n                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",\n                        rfc="__sin_cambio__", curp="__sin_cambio__", numero_licencia="__sin_cambio__",\n                        tipo_licencia="__sin_cambio__", vigencia_licencia="__sin_cambio__"):\n    conn = get_connection()\n    cur = conn.cursor()\n    campos, valores = [], []\n',
            '                        acceso_administracion=None, acceso_compras=None, acceso_rh=None, acceso_dashboard=None,\n                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,\n                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,\n                        acceso_datos_empleado_rh=None, acceso_monitoreo=None, acceso_shopify=None, acceso_turnos=None,\n                        monitoreo_activo=None,\n                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",\n                        rfc="__sin_cambio__", curp="__sin_cambio__", numero_licencia="__sin_cambio__",\n                        tipo_licencia="__sin_cambio__", vigencia_licencia="__sin_cambio__",\n                        ventanilla_turnos="__sin_cambio__"):\n    conn = get_connection()\n    cur = conn.cursor()\n    campos, valores = [], []\n',
        ],
    ],
    'frontend/index.html': [
        [
            '      <thead><tr>\n        <th>Persona</th><th>Rol</th>\n        <th class="col-check">Tickets${casillaTodoColumna(\'acceso_tickets\')}</th><th class="col-check">Reparaciones${casillaTodoColumna(\'acceso_reparaciones\')}</th><th class="col-check">Laboratorio${casillaTodoColumna(\'acceso_laboratorio\')}</th><th class="col-check" title="Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal">Recibir/Entregar Lab.${casillaTodoColumna(\'acceso_laboratorio_entrega\')}</th><th class="col-check">Entregas${casillaTodoColumna(\'acceso_entregas\')}</th><th class="col-check">Precios${casillaTodoColumna(\'acceso_checador_precio\')}</th><th class="col-check">Equipos${casillaTodoColumna(\'acceso_equipos\')}</th>\n        <th class="col-check">Compras${casillaTodoColumna(\'acceso_compras\')}</th><th class="col-check">RH${casillaTodoColumna(\'acceso_rh\')}</th><th class="col-check">Marketing${casillaTodoColumna(\'acceso_marketing\')}</th><th class="col-check">CRM${casillaTodoColumna(\'acceso_crm\')}</th><th class="col-check">🐭${casillaTodoColumna(\'acceso_asistente_ia\')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna(\'acceso_datos_empleado_rh\')}</th><th class="col-check" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad) — distinto de la columna \'Monitoreo\' de más adelante, que es si a ESA persona se le vigila">Ver Monitoreo${casillaTodoColumna(\'acceso_monitoreo\')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna(\'acceso_shopify\')}</th>\n        <th class="col-check">Dashboard${casillaTodoColumna(\'acceso_dashboard\')}</th><th class="col-check">Admin.${casillaTodoColumna(\'acceso_administracion\')}</th><th class="col-check">Monitoreo${casillaTodoColumna(\'monitoreo_activo\')}</th>\n      </tr></thead>\n      <tbody id="tbody_accesos">\n',
            '      <thead><tr>\n        <th>Persona</th><th>Rol</th>\n        <th class="col-check">Tickets${casillaTodoColumna(\'acceso_tickets\')}</th><th class="col-check">Reparaciones${casillaTodoColumna(\'acceso_reparaciones\')}</th><th class="col-check">Laboratorio${casillaTodoColumna(\'acceso_laboratorio\')}</th><th class="col-check" title="Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal">Recibir/Entregar Lab.${casillaTodoColumna(\'acceso_laboratorio_entrega\')}</th><th class="col-check">Entregas${casillaTodoColumna(\'acceso_entregas\')}</th><th class="col-check">Precios${casillaTodoColumna(\'acceso_checador_precio\')}</th><th class="col-check">Equipos${casillaTodoColumna(\'acceso_equipos\')}</th>\n        <th class="col-check">Compras${casillaTodoColumna(\'acceso_compras\')}</th><th class="col-check">RH${casillaTodoColumna(\'acceso_rh\')}</th><th class="col-check">Marketing${casillaTodoColumna(\'acceso_marketing\')}</th><th class="col-check">CRM${casillaTodoColumna(\'acceso_crm\')}</th><th class="col-check">🐭${casillaTodoColumna(\'acceso_asistente_ia\')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna(\'acceso_datos_empleado_rh\')}</th><th class="col-check" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad) — distinto de la columna \'Monitoreo\' de más adelante, que es si a ESA persona se le vigila">Ver Monitoreo${casillaTodoColumna(\'acceso_monitoreo\')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna(\'acceso_shopify\')}</th><th class="col-check" title="Tomar/llamar turnos en su sucursal">🎫 Turnos${casillaTodoColumna(\'acceso_turnos\')}</th>\n        <th class="col-check">Dashboard${casillaTodoColumna(\'acceso_dashboard\')}</th><th class="col-check">Admin.${casillaTodoColumna(\'acceso_administracion\')}</th><th class="col-check">Monitoreo${casillaTodoColumna(\'monitoreo_activo\')}</th>\n      </tr></thead>\n      <tbody id="tbody_accesos">\n',
        ],
        [
            '            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_datos_empleado_rh\', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>\n            <td class="col-check"><input type="checkbox" ${u.acceso_monitoreo ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_monitoreo\', this)" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad de empleados)" data-campo="acceso_monitoreo" /></td>\n            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_shopify\', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>\n            ${u.rol === \'admin\' ? `\n              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_dashboard\', this)" data-campo="acceso_dashboard" /></td>\n              <td class="col-check"><input type="checkbox" ${u.acceso_administracion ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_administracion\', this)" data-campo="acceso_administracion" /></td>\n',
            '            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_datos_empleado_rh\', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>\n            <td class="col-check"><input type="checkbox" ${u.acceso_monitoreo ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_monitoreo\', this)" title="Ver la pestaña 🕵️ Monitoreo (bitácora de actividad de empleados)" data-campo="acceso_monitoreo" /></td>\n            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_shopify\', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>\n            <td class="col-check"><input type="checkbox" ${u.acceso_turnos ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_turnos\', this)" title="Tomar/llamar turnos en su sucursal" data-campo="acceso_turnos" /></td>\n            ${u.rol === \'admin\' ? `\n              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_dashboard\', this)" data-campo="acceso_dashboard" /></td>\n              <td class="col-check"><input type="checkbox" ${u.acceso_administracion ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'acceso_administracion\', this)" data-campo="acceso_administracion" /></td>\n',
        ],
        [
            "    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;\n    payload.acceso_monitoreo = document.getElementById('e_acceso_monitoreo').checked;\n    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;\n  }\n  if (rol === 'admin') {\n    payload.restriccion_categoria = document.getElementById('e_restriccion_categoria').value || null;\n",
            "    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;\n    payload.acceso_monitoreo = document.getElementById('e_acceso_monitoreo').checked;\n    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;\n    payload.acceso_turnos = document.getElementById('e_acceso_turnos').checked;\n    payload.ventanilla_turnos = document.getElementById('e_ventanilla_turnos').value.trim() || null;\n  }\n  if (rol === 'admin') {\n    payload.restriccion_categoria = document.getElementById('e_restriccion_categoria').value || null;\n",
        ],
    ],
}


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
                cambios += 1  # ya aplicado antes
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
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Completar Turnos por sucursal (bloques que faltaron por choque con Monitoreo)"')
    print("   git push")


if __name__ == "__main__":
    main()
