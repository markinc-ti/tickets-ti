# -*- coding: utf-8 -*-
"""
Laboratorio: cerrar el hueco de "Mover estado" que saltaba Aprobar diseño,
con un botón de escape para los trabajos que no necesitan diseño -- y subir
el límite de tamaño del STL + liberar ese espacio al entregar el trabajo.

Qué hace (2 cambios independientes, pedidos juntos por David):

1) "Mover estado" ya no deja saltar Aprobar diseño sin querer.
   Antes, el selector genérico "Mover estado dentro del laboratorio" dejaba
   pasar un trabajo de "Modelado" directo a "Maquillado"/"Control de
   calidad"/"Envío a sucursal" a mano, sin pasar por "Aprobar diseño" --
   aunque el laboratorio nunca hubiera subido ni el estudiante aprobado
   ningún diseño. Eso fue justo lo que le pasó a David con un trabajo de
   prueba: se saltó ese paso y luego no encontraba el botón de "Subir
   diseño" (ese botón solo aparece en Modelado/Aprobar diseño).

   Ahora, "Mover estado" bloquea ese salto con un mensaje claro, A MENOS
   que el trabajo ya tenga un diseño aprobado (pasó de verdad por Aprobar
   diseño) o esté marcado como "no necesita diseño". Para eso se agrega un
   botón nuevo, junto al de "Subir diseño (STL)": "Este trabajo no necesita
   diseño" -- para los trabajos que sí entran al flujo de laboratorio pero
   no requieren que el estudiante apruebe nada (ej. reparaciones simples).
   Al usarlo, "Mover estado" vuelve a dejarlo avanzar libremente.

2) Límite del archivo de diseño (STL) subido de ~30MB a ~90MB de archivo
   real, y se libera solo al entregar el trabajo.
   David intentó subir un diseño y chocó con el límite de ~30MB puesto en
   fix_laboratorio_diseno_limite_mb.py. Una arcada completa (2 archivos STL
   de alta resolución) se puede acercar a ese tamaño, así que se sube el
   límite a ~90MB de archivo real (~120MB en base64) por archivo.

   Para que esto no crezca la base de datos sin control (estos archivos se
   guardan como texto base64 en Postgres, no en un storage aparte), en
   cuanto se registra la ENTREGA del trabajo al doctor/estudiante (estado
   "entregado") se vacía el contenido de los archivos de diseño de ese
   trabajo -- se deja el nombre del archivo y todo el historial de
   aprobación/rechazo, solo se libera el peso real. Como el botón de subir/
   ver diseño solo aparece mientras el trabajo está en Modelado o Aprobar
   diseño (nunca en "Entregado"), esto no rompe nada en pantalla.

Columnas nuevas (se agregan solas al arrancar, como las demás):
  - trabajos_laboratorio.omite_aprobacion_diseno (BOOLEAN, default FALSE)
  - laboratorio_disenos.archivo_liberado (BOOLEAN, default FALSE)

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_laboratorio_diseno_omitir_y_espacio.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/db.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    # Columna nueva en trabajos_laboratorio
    [
        '        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS dscore_order_name TEXT;\n'
        '\n'
        '        -- El pago se puede dividir entre varios métodos (ej. mitad efectivo,',
        '        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS dscore_order_name TEXT;\n'
        '        -- Para trabajos que no necesitan que el laboratorio suba un diseño\n'
        '        -- para que el estudiante lo apruebe (ej. reparaciones simples) --\n'
        '        -- deja que "Mover estado" avance el trabajo más allá de modelado\n'
        '        -- sin pasar por Aprobar diseño.\n'
        '        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS omite_aprobacion_diseno BOOLEAN NOT NULL DEFAULT FALSE;\n'
        '\n'
        '        -- El pago se puede dividir entre varios métodos (ej. mitad efectivo,',
    ],
    # Columna nueva en laboratorio_disenos
    [
        '        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_base64_2 TEXT;\n'
        '        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_nombre_2 TEXT;\n'
        '    """)\n'
        '    conn.commit()',
        '        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_base64_2 TEXT;\n'
        '        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_nombre_2 TEXT;\n'
        '        -- Cuando el trabajo ya se entregó, se vacía el contenido de estos\n'
        '        -- archivos (pueden pesar decenas de MB) para liberar espacio -- este\n'
        '        -- campo marca que ya se hizo, para no reintentarlo ni mostrar un\n'
        '        -- archivo vacío como si fuera válido.\n'
        '        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_liberado BOOLEAN NOT NULL DEFAULT FALSE;\n'
        '    """)\n'
        '    conn.commit()',
    ],
    # registrar_entrega_laboratorio: libera el espacio de los diseños al entregar
    # + función nueva marcar_omite_diseno_laboratorio
    [
        'def registrar_entrega_laboratorio(empresa_id, trabajo_id, usuario_id, observaciones_entrega, firma_entrega):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    now = ahora().isoformat(timespec="seconds")\n'
        '    cur.execute(\n'
        '        """UPDATE trabajos_laboratorio\n'
        '           SET estado = \'entregado\', fecha_entrega = %s, entregado_por_id = %s,\n'
        '               observaciones_entrega = %s, firma_entrega = %s, actualizado_en = %s\n'
        '           WHERE id = %s AND empresa_id = %s""",\n'
        '        (now, usuario_id, observaciones_entrega, firma_entrega, now, trabajo_id, empresa_id),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def eliminar_trabajo_laboratorio(empresa_id, trabajo_id):',
        'def registrar_entrega_laboratorio(empresa_id, trabajo_id, usuario_id, observaciones_entrega, firma_entrega):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    now = ahora().isoformat(timespec="seconds")\n'
        '    cur.execute(\n'
        '        """UPDATE trabajos_laboratorio\n'
        '           SET estado = \'entregado\', fecha_entrega = %s, entregado_por_id = %s,\n'
        '               observaciones_entrega = %s, firma_entrega = %s, actualizado_en = %s\n'
        '           WHERE id = %s AND empresa_id = %s""",\n'
        '        (now, usuario_id, observaciones_entrega, firma_entrega, now, trabajo_id, empresa_id),\n'
        '    )\n'
        '    # El trabajo ya se entregó -- los archivos de diseño (STL) ya cumplieron\n'
        '    # su función (el estudiante ya los revisó/aprobó) y pueden pesar decenas\n'
        '    # de MB cada uno. Se libera ese espacio vaciando el contenido, pero se\n'
        '    # deja el nombre del archivo y el historial de aprobación intactos.\n'
        '    cur.execute(\n'
        '        """UPDATE laboratorio_disenos\n'
        '               SET archivo_base64 = \'\', archivo_base64_2 = NULL, archivo_liberado = TRUE\n'
        '           WHERE trabajo_id = %s AND archivo_liberado = FALSE""",\n'
        '        (trabajo_id,),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def marcar_omite_diseno_laboratorio(empresa_id, trabajo_id):\n'
        '    """Para trabajos que no necesitan que el laboratorio suba un diseño para\n'
        '    que el estudiante lo apruebe -- deja que \'Mover estado\' avance el\n'
        '    trabajo más allá de modelado sin pasar por Aprobar diseño."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    now = ahora().isoformat(timespec="seconds")\n'
        '    cur.execute(\n'
        '        "UPDATE trabajos_laboratorio SET omite_aprobacion_diseno = TRUE, actualizado_en = %s WHERE id = %s AND empresa_id = %s",\n'
        '        (now, trabajo_id, empresa_id),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def eliminar_trabajo_laboratorio(empresa_id, trabajo_id):',
    ],
]

# ---------------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    # Sube el límite de tamaño del STL de ~30MB a ~90MB
    [
        'MAX_DISENO_STL_BASE64 = 40_000_000  # ~30MB de archivo real -- un diseño STL de laboratorio pesa mucho más que una foto/firma/comprobante',
        'MAX_DISENO_STL_BASE64 = 120_000_000  # ~90MB de archivo real -- subido desde 30MB porque una arcada completa (2 archivos STL de alta resolución) se acerca a ese tamaño; el espacio se libera solo al entregar el trabajo (ver registrar_entrega_laboratorio en db.py)',
    ],
    [
        '    if len(payload.archivo_base64) > MAX_DISENO_STL_BASE64:\n'
        '        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~30MB) -- comprímelo o expórtalo con menos resolución")\n'
        '    if payload.archivo_base64_2 and len(payload.archivo_base64_2) > MAX_DISENO_STL_BASE64:\n'
        '        raise HTTPException(status_code=400, detail="El segundo archivo pesa demasiado (máximo ~30MB) -- comprímelo o expórtalo con menos resolución")',
        '    if len(payload.archivo_base64) > MAX_DISENO_STL_BASE64:\n'
        '        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")\n'
        '    if payload.archivo_base64_2 and len(payload.archivo_base64_2) > MAX_DISENO_STL_BASE64:\n'
        '        raise HTTPException(status_code=400, detail="El segundo archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")',
    ],
    # Constante nueva junto a ESTADOS_LABORATORIO_LIBRES
    [
        'ESTADOS_LABORATORIO_LIBRES = ["modelado", "maquillado", "control_calidad", "envio_sucursal", "cancelado"]\n'
        '\n'
        '\n'
        '@app.get("/api/laboratorio")',
        'ESTADOS_LABORATORIO_LIBRES = ["modelado", "maquillado", "control_calidad", "envio_sucursal", "cancelado"]\n'
        '# Estos son los que vienen DESPUÉS de "Aprobar diseño" en el flujo normal --\n'
        '# si el trabajo todavía no tiene un diseño aprobado (o marcado como que no\n'
        '# lo necesita, ver omite_aprobacion_diseno), "Mover estado" no debe dejar\n'
        '# saltar directo a ninguno de estos desde modelado/aprobar_diseno.\n'
        'ESTADOS_LABORATORIO_REQUIEREN_DISENO_APROBADO = {"maquillado", "control_calidad", "envio_sucursal"}\n'
        '\n'
        '\n'
        '@app.get("/api/laboratorio")',
    ],
    # Bloqueo en /estado + endpoint nuevo /omitir-diseno
    [
        '@app.patch("/api/laboratorio/{trabajo_id}/estado")\n'
        'def api_cambiar_estado_laboratorio(trabajo_id: int, payload: CambioEstadoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n'
        '    """Mover el trabajo entre los pasos internos de fabricación — desde que\n'
        '    entró al laboratorio hasta que se manda de vuelta a la sucursal. Una\n'
        '    vez que se manda (\'envio_sucursal\') ya nadie lo puede tocar aquí, hasta\n'
        '    que la sucursal lo reciba (endpoint /recibir-sucursal, no este)."""\n'
        '    if payload.estado not in ESTADOS_LABORATORIO_LIBRES:\n'
        '        raise HTTPException(status_code=400, detail="Ese estado no se cambia desde aquí")\n'
        '    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '    if not trabajo:\n'
        '        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n'
        '    if payload.estado != "cancelado":\n'
        '        if trabajo["estado"] not in ("en_laboratorio", *ESTADOS_LABORATORIO_LIBRES) or trabajo["estado"] == "envio_sucursal":\n'
        '            raise HTTPException(status_code=400, detail="Este trabajo todavía no ha entrado al laboratorio, o ya se envió de vuelta a la sucursal")\n'
        '        if usuario["rol"] != "admin":\n'
        '            sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])\n'
        '            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n'
        '            if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:\n'
        '                raise HTTPException(status_code=403, detail="Solo el laboratorio puede mover estos estados")\n'
        '    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, payload.estado)\n'
        '    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n'
        '    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")\n'
        '    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '\n'
        '\n'
        '@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")',

        '@app.patch("/api/laboratorio/{trabajo_id}/estado")\n'
        'def api_cambiar_estado_laboratorio(trabajo_id: int, payload: CambioEstadoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n'
        '    """Mover el trabajo entre los pasos internos de fabricación — desde que\n'
        '    entró al laboratorio hasta que se manda de vuelta a la sucursal. Una\n'
        '    vez que se manda (\'envio_sucursal\') ya nadie lo puede tocar aquí, hasta\n'
        '    que la sucursal lo reciba (endpoint /recibir-sucursal, no este)."""\n'
        '    if payload.estado not in ESTADOS_LABORATORIO_LIBRES:\n'
        '        raise HTTPException(status_code=400, detail="Ese estado no se cambia desde aquí")\n'
        '    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '    if not trabajo:\n'
        '        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n'
        '    if payload.estado != "cancelado":\n'
        '        if trabajo["estado"] not in ("en_laboratorio", *ESTADOS_LABORATORIO_LIBRES) or trabajo["estado"] == "envio_sucursal":\n'
        '            raise HTTPException(status_code=400, detail="Este trabajo todavía no ha entrado al laboratorio, o ya se envió de vuelta a la sucursal")\n'
        '        if (payload.estado in ESTADOS_LABORATORIO_REQUIEREN_DISENO_APROBADO\n'
        '                and trabajo["estado"] in ("modelado", "aprobar_diseno")\n'
        '                and not trabajo.get("omite_aprobacion_diseno")):\n'
        '            raise HTTPException(\n'
        '                status_code=400,\n'
        '                detail="Este trabajo todavía no tiene un diseño aprobado -- sube el diseño (STL) para que el estudiante lo apruebe, o usa \\"Este trabajo no necesita diseño\\" si no hace falta.",\n'
        '            )\n'
        '        if usuario["rol"] != "admin":\n'
        '            sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])\n'
        '            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n'
        '            if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:\n'
        '                raise HTTPException(status_code=403, detail="Solo el laboratorio puede mover estos estados")\n'
        '    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, payload.estado)\n'
        '    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)\n'
        '    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")\n'
        '    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '\n'
        '\n'
        '@app.post("/api/laboratorio/{trabajo_id}/omitir-diseno")\n'
        'def api_omitir_diseno_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n'
        '    """Para trabajos que no van a llevar un diseño que el estudiante tenga\n'
        '    que aprobar (ej. una reparación simple que de todos modos entró al\n'
        '    flujo de laboratorio) -- marca el trabajo para que \'Mover estado\' lo\n'
        '    deje avanzar más allá de modelado sin pasar por Aprobar diseño."""\n'
        '    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '    if not trabajo:\n'
        '        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n'
        '    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):\n'
        '        raise HTTPException(status_code=400, detail="Este trabajo ya no está en un punto donde aplique esto")\n'
        '    if usuario["rol"] != "admin":\n'
        '        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])\n'
        '        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n'
        '        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:\n'
        '            raise HTTPException(status_code=403, detail="Solo el laboratorio puede hacer esto")\n'
        '    db.marcar_omite_diseno_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '    db.agregar_actualizacion_laboratorio(\n'
        '        trabajo_id, usuario["id"],\n'
        '        "Marcó que este trabajo no necesita subir diseño ni aprobación del estudiante -- puede seguir avanzando.",\n'
        '    )\n'
        '    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n'
        '\n'
        '\n'
        '@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")',
    ],
]

# ---------------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # Botón "Este trabajo no necesita diseño" junto al de subir STL
    [
        '        <label class="secondary btn-file" style="display:inline-block;">\n'
        '          📎 Subir diseño (STL) — 1 o 2 archivos (arcada completa)\n'
        '          <input type="file" accept=".stl,.ply,.obj" multiple style="display:none;" onchange="subirDisenoLaboratorioUI(${w.id}, this)" />\n'
        '        </label>\n'
        '      </div>\n'
        '    `) : \'\'}',
        '        <label class="secondary btn-file" style="display:inline-block;">\n'
        '          📎 Subir diseño (STL) — 1 o 2 archivos (arcada completa)\n'
        '          <input type="file" accept=".stl,.ply,.obj" multiple style="display:none;" onchange="subirDisenoLaboratorioUI(${w.id}, this)" />\n'
        '        </label>\n'
        '        <button class="secondary" style="margin-left:8px;" onclick="omitirDisenoLaboratorioUI(${w.id}, this)">Este trabajo no necesita diseño</button>\n'
        '      </div>\n'
        '    `) : \'\'}',
    ],
    # Función JS nueva, junto a subirDisenoLaboratorioUI
    [
        'async function subirDisenoLaboratorioUI(trabajoId, input) {\n'
        '  const archivo = input.files[0];\n'
        '  if (!archivo) return;\n'
        '  const archivo2 = input.files[1] || null;\n'
        '  const leerComoBase64 = (f) => new Promise((res, rej) => {\n'
        '    const r = new FileReader();\n'
        '    r.onload = () => res(r.result);\n'
        '    r.onerror = rej;\n'
        '    r.readAsDataURL(f);\n'
        '  });\n'
        '  const base64 = await leerComoBase64(archivo);\n'
        '  const base64_2 = archivo2 ? await leerComoBase64(archivo2) : null;\n'
        '  try {\n'
        '    const body = { archivo_base64: base64, archivo_nombre: archivo.name };\n'
        '    if (base64_2) {\n'
        '      body.archivo_base64_2 = base64_2;\n'
        '      body.archivo_nombre_2 = archivo2.name;\n'
        '    }\n'
        '    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: \'POST\', body: JSON.stringify(body) });\n'
        '    await abrirDetalleLaboratorio(trabajoId);\n'
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        'async function agregarNotaLaboratorioUI(trabajoId, boton) {',
        'async function subirDisenoLaboratorioUI(trabajoId, input) {\n'
        '  const archivo = input.files[0];\n'
        '  if (!archivo) return;\n'
        '  const archivo2 = input.files[1] || null;\n'
        '  const leerComoBase64 = (f) => new Promise((res, rej) => {\n'
        '    const r = new FileReader();\n'
        '    r.onload = () => res(r.result);\n'
        '    r.onerror = rej;\n'
        '    r.readAsDataURL(f);\n'
        '  });\n'
        '  const base64 = await leerComoBase64(archivo);\n'
        '  const base64_2 = archivo2 ? await leerComoBase64(archivo2) : null;\n'
        '  try {\n'
        '    const body = { archivo_base64: base64, archivo_nombre: archivo.name };\n'
        '    if (base64_2) {\n'
        '      body.archivo_base64_2 = base64_2;\n'
        '      body.archivo_nombre_2 = archivo2.name;\n'
        '    }\n'
        '    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: \'POST\', body: JSON.stringify(body) });\n'
        '    await abrirDetalleLaboratorio(trabajoId);\n'
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        'async function omitirDisenoLaboratorioUI(trabajoId, boton) {\n'
        '  if (!confirm(\'¿Seguro que este trabajo no necesita que el estudiante apruebe un diseño? Vas a poder moverlo de estado sin pasar por ahí.\')) return;\n'
        '  await conBloqueoDeBoton(boton, async () => {\n'
        '    try {\n'
        '      await api(`/api/laboratorio/${trabajoId}/omitir-diseno`, { method: \'POST\' });\n'
        '      mostrarExito(\'Este trabajo ya no necesita diseño -- puedes moverlo de estado libremente\');\n'
        '      await abrirDetalleLaboratorio(trabajoId);\n'
        '    } catch (e) {\n'
        '      document.getElementById(\'labDetalleError\').textContent = e.message;\n'
        '    }\n'
        '  });\n'
        '}\n'
        '\n'
        'async function agregarNotaLaboratorioUI(trabajoId, boton) {',
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
    print('   git commit -m "Laboratorio: bloquear saltar Aprobar diseno sin querer (con boton de escape) y subir limite de STL liberando espacio al entregar"')
    print("   git push")


if __name__ == "__main__":
    main()
