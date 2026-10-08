#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DS Core: valida el material de cada pieza importada contra el acuerdo con
el laboratorio (zirconia/disilicato). Si un diente trae otro material, no
se importa solo -- se le explica al estudiante que hay que llamar al
laboratorio para cotizarlo, o se le deja elegir un material del acuerdo
para esa pieza antes de continuar.

IMPORTANTE -- este parche depende de que YA esté aplicado
fix_dscore_piezas_autofill.py (el que agrega extraer_piezas_de_order() y
el llenado automático del odontograma al importar). Si ese parche todavía
no se ha corrido, corre PRIMERO fix_dscore_piezas_autofill.py y DESPUÉS
este.

Por qué: siguiendo el llenado automático del odontograma, David pidió que
si el doctor especificó en DS Core un material que no está dentro del
acuerdo de precio fijo con el laboratorio (solo zirconia y disilicato),
no se procese solo -- que se avise que hay que llamar al laboratorio para
cotizar ese material, y que de perdida se pueda cambiar el material antes
de importar.

Que cambia:
- backend/app.py: ImportarPedidoDSCore ahora acepta un mapeo opcional
  materiales_override (diente -> material corregido). api_importar_pedido_dscore
  revisa cada pieza detectada -- si su material no está en zirconia/disilicato
  y no viene un override para ese diente, se rechaza el import completo (409)
  con un mensaje claro y la lista de piezas pendientes, en vez de crear el
  trabajo con un material fuera de acuerdo.
- frontend/laboratorio_estudiantes.html: la pantalla "Importar desde DS Core"
  ahora, si el servidor rechaza el import por materiales pendientes, muestra
  un selector por cada pieza (cambiar a Zirconia/Disilicato, o dejarlo así y
  llamar al laboratorio) y un botón para reintentar el import ya con esas
  correcciones.
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            'class ImportarPedidoDSCore(BaseModel):\n    codigo: str = Field(min_length=3, max_length=40)\n    requiere_factura: bool\n    sucursal_recogida_id: Optional[int] = None',
            'class ImportarPedidoDSCore(BaseModel):\n    codigo: str = Field(min_length=3, max_length=40)\n    requiere_factura: bool\n    sucursal_recogida_id: Optional[int] = None\n    # Si un diente del pedido viene con un material que no está dentro del\n    # acuerdo con el laboratorio (zirconia/disilicato), el primer intento se\n    # rechaza pidiendo llamar al laboratorio o corregir el material. Este\n    # mapeo (diente -> material corregido) se manda en un segundo intento\n    # para forzar la corrección elegida en vez del material que traía DS Core.\n    materiales_override: Optional[dict[str, str]] = None',
        ],
        [
            '    # Si el pedido trae detalle de restauración por diente (tipo, material,\n    # tono), se arma el odontograma solo -- así el estudiante ve de una vez\n    # cuánto va a pagar en vez de ver el trabajo con costo $0.00.\n    piezas_extraidas = dscore.extraer_piezas_de_order(order)\n    for pieza in piezas_extraidas:\n        precio_fijo = db.precio_fijo_laboratorio("BUAP", pieza["tipo_trabajo"], pieza.get("material"))\n        if precio_fijo is not None:\n            pieza["costo"] = precio_fijo',
            '    # Si el pedido trae detalle de restauración por diente (tipo, material,\n    # tono), se arma el odontograma solo -- así el estudiante ve de una vez\n    # cuánto va a pagar en vez de ver el trabajo con costo $0.00.\n    piezas_extraidas = dscore.extraer_piezas_de_order(order)\n    # Solo zirconia/disilicato están dentro del acuerdo de precio fijo con el\n    # laboratorio -- si el doctor especificó otro material en DS Core, no se\n    # puede procesar solo: se le pide al estudiante llamar al laboratorio\n    # para cotizarlo, o corregir el material antes de importar.\n    materiales_override = payload.materiales_override or {}\n    piezas_pendientes = []\n    for pieza in piezas_extraidas:\n        if pieza.get("material") in db.MATERIALES_LABORATORIO:\n            continue\n        diente = pieza["diente"]\n        if diente in materiales_override:\n            nuevo_material = materiales_override[diente]\n            if nuevo_material not in db.MATERIALES_LABORATORIO:\n                raise HTTPException(status_code=400, detail=f"Material inválido para el diente {diente}")\n            pieza["material"] = nuevo_material\n        else:\n            piezas_pendientes.append(pieza)\n    if piezas_pendientes:\n        detalle_piezas = "; ".join(\n            f"diente {p[\'diente\']} ({p[\'tipo_trabajo\']}): {p.get(\'material\') or \'sin material especificado\'}"\n            for p in piezas_pendientes\n        )\n        raise HTTPException(status_code=409, detail={\n            "msg": (\n                "Este pedido tiene material que no está dentro del acuerdo con el laboratorio "\n                f"(zirconia o disilicato) — {detalle_piezas}. Llama al laboratorio para cotizar ese "\n                "material, o cambia el material de esas piezas antes de importar."\n            ),\n            "piezas_pendientes": [\n                {"diente": p["diente"], "tipo_trabajo": p["tipo_trabajo"], "material_dscore": p.get("material")}\n                for p in piezas_pendientes\n            ],\n        })\n    for pieza in piezas_extraidas:\n        precio_fijo = db.precio_fijo_laboratorio("BUAP", pieza["tipo_trabajo"], pieza.get("material"))\n        if precio_fijo is not None:\n            pieza["costo"] = precio_fijo',
        ],
    ],
    'frontend/laboratorio_estudiantes.html': [
        [
            '  let TRABAJOS_CACHE = [];\n  let PIEZAS_NUEVAS = [];\n  let FIRMA_VACIA = true;\n  let TRABAJO_DETALLE_ID = null;',
            '  let TRABAJOS_CACHE = [];\n  let PIEZAS_NUEVAS = [];\n  let FIRMA_VACIA = true;\n  let TRABAJO_DETALLE_ID = null;\n  let DSCORE_PIEZAS_PENDIENTES = [];',
        ],
        [
            '    <div class="card" id="nt_dscoreCard" style="display:none;">\n      <h2 style="margin-top:0;">Importar desde DS Core</h2>\n      <p class="sub">Pide el código a tu maestro (el de la orden que se generó en DS Core al escanear) y captúralo aquí -- se llena solo el nombre del paciente.</p>\n      <div class="field"><label>Código de DS Core</label><input id="nt_dscore_codigo" placeholder="ej. DAA04BDC" /></div>\n      <div class="field"><label>¿Requiere factura?</label><select id="nt_dscore_factura"><option value="0">No</option><option value="1">Sí</option></select></div>\n      <div class="field"><label>¿Dónde vas a recoger tu trabajo?</label><select id="nt_dscore_sucursal_recogida"></select></div>\n      <div class="error" id="nt_dscore_error"></div>\n      <button class="primary" style="width:100%;" onclick="importarDesdeDSCore()">Importar pedido</button>\n      <p class="sub" style="margin-top:10px; margin-bottom:0;">Después de importarlo, completa el odontograma (dientes/piezas) y sube tu comprobante de pago desde el detalle del trabajo.</p>\n    </div>',
            '    <div class="card" id="nt_dscoreCard" style="display:none;">\n      <h2 style="margin-top:0;">Importar desde DS Core</h2>\n      <p class="sub">Pide el código a tu maestro (el de la orden que se generó en DS Core al escanear) y captúralo aquí -- se llena solo el nombre del paciente.</p>\n      <div class="field"><label>Código de DS Core</label><input id="nt_dscore_codigo" placeholder="ej. DAA04BDC" /></div>\n      <div class="field"><label>¿Requiere factura?</label><select id="nt_dscore_factura"><option value="0">No</option><option value="1">Sí</option></select></div>\n      <div class="field"><label>¿Dónde vas a recoger tu trabajo?</label><select id="nt_dscore_sucursal_recogida"></select></div>\n      <div class="error" id="nt_dscore_error"></div>\n      <div id="nt_dscore_pendientes" style="display:none; margin:10px 0;">\n        <p class="sub" style="margin-bottom:8px;">Elige el material correcto para estas piezas, o déjalas así y llama al laboratorio para cotizar ese material aparte:</p>\n        <div id="nt_dscore_pendientes_lista"></div>\n        <button class="secondary" style="width:100%; margin-top:8px;" onclick="reintentarImportarDSCoreConMateriales()">Reintentar con estos materiales</button>\n      </div>\n      <button class="primary" style="width:100%;" onclick="importarDesdeDSCore()">Importar pedido</button>\n      <p class="sub" style="margin-top:10px; margin-bottom:0;">Después de importarlo, completa el odontograma (dientes/piezas) y sube tu comprobante de pago desde el detalle del trabajo.</p>\n    </div>',
        ],
        [
            "    document.getElementById('nt_dscore_codigo').value = '';\n    document.getElementById('nt_dscore_factura').value = '0';\n    document.getElementById('nt_dscore_error').textContent = '';\n    const dscoreListo = !!(META && META.dscore_conectado_laboratorio);",
            "    document.getElementById('nt_dscore_codigo').value = '';\n    document.getElementById('nt_dscore_factura').value = '0';\n    document.getElementById('nt_dscore_error').textContent = '';\n    DSCORE_PIEZAS_PENDIENTES = [];\n    document.getElementById('nt_dscore_pendientes').style.display = 'none';\n    const dscoreListo = !!(META && META.dscore_conectado_laboratorio);",
        ],
        [
            "  async function importarDesdeDSCore() {\n    const err = document.getElementById('nt_dscore_error');\n    err.textContent = '';\n    const codigo = document.getElementById('nt_dscore_codigo').value.trim();\n    if (!codigo) { err.textContent = 'Escribe el código que te dio tu maestro.'; return; }\n    const sucursalRecogida = document.getElementById('nt_dscore_sucursal_recogida').value;\n    const payload = {\n      codigo,\n      requiere_factura: document.getElementById('nt_dscore_factura').value === '1',\n      sucursal_recogida_id: sucursalRecogida ? parseInt(sucursalRecogida, 10) : null,\n    };\n    try {\n      await api('/api/laboratorio/mios/importar-dscore', { method: 'POST', body: JSON.stringify(payload) });\n      mostrarLista();\n    } catch (e) { err.textContent = e.message; }\n  }",
            '  async function importarDesdeDSCore(materialesOverride) {\n    const err = document.getElementById(\'nt_dscore_error\');\n    err.textContent = \'\';\n    const codigo = document.getElementById(\'nt_dscore_codigo\').value.trim();\n    if (!codigo) { err.textContent = \'Escribe el código que te dio tu maestro.\'; return; }\n    const sucursalRecogida = document.getElementById(\'nt_dscore_sucursal_recogida\').value;\n    const payload = {\n      codigo,\n      requiere_factura: document.getElementById(\'nt_dscore_factura\').value === \'1\',\n      sucursal_recogida_id: sucursalRecogida ? parseInt(sucursalRecogida, 10) : null,\n    };\n    if (materialesOverride) payload.materiales_override = materialesOverride;\n    // No se usa el helper api() aquí a propósito -- cuando el pedido tiene\n    // un material fuera del acuerdo, el servidor regresa un detalle con\n    // estructura (piezas_pendientes) que hay que leer para armar los\n    // selectores de corrección, no solo un texto de error.\n    const headers = { \'Content-Type\': \'application/json\' };\n    if (TOKEN) headers[\'Authorization\'] = `Bearer ${TOKEN}`;\n    let resp;\n    try {\n      resp = await fetch(\'/api/laboratorio/mios/importar-dscore\', { method: \'POST\', headers, body: JSON.stringify(payload) });\n    } catch (e) {\n      err.textContent = \'No se pudo conectar, intenta de nuevo.\';\n      return;\n    }\n    if (resp.ok) {\n      DSCORE_PIEZAS_PENDIENTES = [];\n      document.getElementById(\'nt_dscore_pendientes\').style.display = \'none\';\n      mostrarLista();\n      return;\n    }\n    const cuerpo = await resp.json().catch(() => ({}));\n    const detalle = cuerpo.detail;\n    if (resp.status === 409 && detalle && typeof detalle === \'object\' && Array.isArray(detalle.piezas_pendientes)) {\n      DSCORE_PIEZAS_PENDIENTES = detalle.piezas_pendientes;\n      err.textContent = detalle.msg || \'Hay piezas con un material que no está dentro del acuerdo.\';\n      renderPendientesMaterialDSCore();\n      return;\n    }\n    let mensaje = (detalle && typeof detalle === \'object\') ? (detalle.msg || JSON.stringify(detalle)) : detalle;\n    err.textContent = mensaje || \'Ocurrió un error, intenta de nuevo.\';\n  }\n\n  function renderPendientesMaterialDSCore() {\n    const cont = document.getElementById(\'nt_dscore_pendientes\');\n    const lista = document.getElementById(\'nt_dscore_pendientes_lista\');\n    if (!DSCORE_PIEZAS_PENDIENTES.length) { cont.style.display = \'none\'; return; }\n    lista.innerHTML = DSCORE_PIEZAS_PENDIENTES.map(p => `\n      <div class="field">\n        <label>Diente ${escapeHtml(p.diente)} — ${escapeHtml(NOMBRES_TIPO[p.tipo_trabajo] || p.tipo_trabajo)} (trae: ${escapeHtml(p.material_dscore || \'sin material\')})</label>\n        <select id="nt_dscore_override_${escapeHtml(p.diente)}">\n          <option value="">— déjalo así y llama al laboratorio —</option>\n          <option value="zirconia">Cambiar a Zirconia</option>\n          <option value="disilicato">Cambiar a Disilicato</option>\n        </select>\n      </div>\n    `).join(\'\');\n    cont.style.display = \'block\';\n  }\n\n  function reintentarImportarDSCoreConMateriales() {\n    const override = {};\n    let faltaAlguno = false;\n    DSCORE_PIEZAS_PENDIENTES.forEach(p => {\n      const sel = document.getElementById(`nt_dscore_override_${p.diente}`);\n      if (sel && sel.value) override[p.diente] = sel.value;\n      else faltaAlguno = true;\n    });\n    if (faltaAlguno) {\n      document.getElementById(\'nt_dscore_error\').textContent = \'Elige un material para cada pieza pendiente, o llama al laboratorio antes de continuar.\';\n      return;\n    }\n    importarDesdeDSCore(override);\n  }',
        ],
    ],
}


def main():
    cambios_totales = 0
    for ruta, hunks in ARCHIVOS.items():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
        except FileNotFoundError:
            print(f"ERROR: no se encontro {ruta} -- corre este script desde la raiz del repo tickets-ti.")
            sys.exit(1)

        original = contenido
        cambios_archivo = 0
        for viejo, nuevo in hunks:
            if nuevo in contenido:
                continue  # ya aplicado antes -- idempotente
            if viejo not in contenido:
                print(f"ERROR: no se encontro el texto esperado en {ruta}.")
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche,")
                print("o que todavia falte aplicar fix_dscore_piezas_autofill.py primero.")
                print("--- fragmento esperado ---")
                print(viejo[:300])
                sys.exit(1)
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios_archivo += 1

        if contenido != original:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: {ruta} -- {cambios_archivo} cambio(s) aplicado(s).")
            cambios_totales += cambios_archivo
        else:
            print(f"(sin cambios) {ruta} -- ya estaba aplicado.")

    if cambios_totales == 0:
        print()
        print("No habia nada nuevo que aplicar (el parche ya estaba puesto).")
    else:
        print()
        print(f"{cambios_totales} cambio(s) aplicado(s) en total.")

    print()
    print("Ahora corre esto para subirlo:")
    print()
    print("    git add backend/app.py frontend/laboratorio_estudiantes.html")
    print('    git commit -m "DS Core: validar material contra el acuerdo (zirconia/disilicato) al importar"')
    print("    git push")


if __name__ == "__main__":
    main()
