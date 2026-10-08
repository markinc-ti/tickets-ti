#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio + DS Core: permite descargar el ESCANEO STL ORIGINAL del
pedido (el que se hizo en el programa de Dentsply Sirona), una vez que el
pago del trabajo ya está cubierto por completo.

Contexto: esto es DISTINTO al visor/diseño de la ronda anterior
(fix_laboratorio_aprobar_diseno.py / fix_laboratorio_visor_stl.py) -- ese
es el archivo que el LABORATORIO sube para que el estudiante lo apruebe
antes de fresar. Lo que pide este parche es que el laboratorio pueda
bajar el escaneo ORIGINAL que ya viene del pedido de DS Core (el insumo
con el que se hace el diseño), aclarado por David: "LO QUE QUIERO ES QUE
UNA VEZ PAGADO Y REVISADO POR LABORATORIO. LABORATORIO PUEDA DESCARGAR EL
ARCHIVO STL QUE CONTIENE EL PEDIDO EL ESCANEO QUE SE REALIZO EN EL
PORGRAMA DE DSIRONA".

Se investigó la API real de DS Core (con el endpoint temporal de
diagnóstico ya entregado, /debug-file, y JSON real que mandó David) antes
de programar esto, en vez de adivinar:
- Cada pedido trae un campo "files" con entradas como {"uri":
  "digitalImpressions/dxd-...", "label": "DI_SCAN"} -- ese es el escaneo.
- Pidiendo esa "uri" (GET /v1beta/{uri}) se obtienen los metadatos,
  incluyendo "contentUri" y el tamaño estimado (el STL solo puede pesar
  ~25MB por maxilar).
- Pidiendo "contentUri" con "?fileType=STL" (GET /v1beta/{contentUri}
  ?fileType=STL) se obtiene el contenido real -- SIEMPRE viene envuelto
  en un .zip (confirmado con los bytes reales), con un archivo .stl por
  cada maxilar escaneado (ej. UpperJaw.stl / LowerJaw.stl).

Por los tamaños (25MB+ cada uno), esto NO se guarda en la base de datos
como los demás adjuntos (fotos, firmas, el diseño que sube el
laboratorio) -- el servidor actúa como puente: cuando alguien del
laboratorio pide la descarga, se pide el archivo a DS Core EN ESE
MOMENTO y se transmite en streaming directo al navegador, sin guardar
ninguna copia ni cargarlo completo a memoria (importante en el plan
gratis de Render, con poca RAM).

Que cambia:
- backend/dscore.py: 4 funciones nuevas -- obtener_order_por_name()
  (trae el pedido completo por su "name", ya guardado en
  trabajos_laboratorio.dscore_order_name al importar),
  buscar_archivo_escaneo_de_order() (busca el archivo etiquetado
  "DI_SCAN" en order["files"], o el primero si no hay ninguno con esa
  etiqueta), obtener_metadata_archivo() (metadatos de un archivo, incl.
  "contentUri"), y descargar_contenido_stream() (pide el contenido real
  con stream=True, sin descargarlo completo a memoria).
- backend/app.py: nuevo endpoint GET
  /api/laboratorio/{trabajo_id}/descargar-escaneo-original (solo
  personal de laboratorio, nunca estudiantes) -- valida que el trabajo
  venga de un pedido de DS Core y que el pago ya esté cubierto por
  completo, y transmite el .zip de DS Core directo al navegador
  (Content-Disposition: attachment) sin guardar copia.
- frontend/index.html: en el detalle de un trabajo de laboratorio
  (panel del laboratorio/administrador), aparece el botón "⬇️ Descargar
  escaneo original (DS Core)" en cuanto el pago queda cubierto (solo si
  el trabajo se importó de DS Core, claro) -- descarga el .zip con el o
  los archivos .stl del escaneo. El estudiante NO ve este botón (esto es
  solo para el laboratorio, como pidió David) -- lo suyo sigue siendo el
  visor/aprobación del diseño que ya existía.
"""
import sys

ARCHIVOS = {
    'backend/dscore.py': [
        [
            'def extraer_piezas_de_order(order):',
            'def obtener_order_por_name(base_host, access_token, order_name):\n    """Trae el pedido completo por su \'name\' (el identificador que ya se\n    guarda en trabajos_laboratorio.dscore_order_name al importar) --\n    mismo patrón que nombre_paciente_de_order para resolver un\n    \'uri\'/\'name\' de DS Core pidiendo GET /v1beta/{name}. None si el\n    pedido ya no existe o el name viene vacío."""\n    order_name = (order_name or "").strip()\n    if not order_name:\n        return None\n    try:\n        return _get(base_host, access_token, f"/v1beta/{order_name.lstrip(\'/\')}")\n    except DSCoreError:\n        return None\n\n\ndef buscar_archivo_escaneo_de_order(order):\n    """De los archivos adjuntos al pedido (campo \'files\', confirmado con\n    un pedido real -- ej. {"uri": "digitalImpressions/dxd-...", "label":\n    "DI_SCAN"}), busca el escaneo original (label \'DI_SCAN\'); si el\n    pedido no trae ninguno con esa etiqueta exacta, regresa el primer\n    archivo que sí traiga, para no dejar sin descarga a un pedido que\n    etiquetó su único archivo distinto. None si no trae ningún archivo."""\n    archivos = order.get("files") or []\n    for archivo in archivos:\n        if (archivo.get("label") or "").strip().upper() == "DI_SCAN":\n            return archivo\n    return archivos[0] if archivos else None\n\n\ndef obtener_metadata_archivo(base_host, access_token, uri):\n    """Metadatos de un archivo del pedido (contentUri, supportedFileTypes,\n    estimatedContentSizesBytes, etc.) -- GET /v1beta/{uri}, mismo patrón\n    que el resto de recursos con \'uri\' de DS Core."""\n    return _get(base_host, access_token, f"/v1beta/{uri.lstrip(\'/\')}")\n\n\ndef descargar_contenido_stream(base_host, access_token, content_uri, file_type=None):\n    """Pide el CONTENIDO real de un archivo del pedido (ej. el escaneo\n    STL) usando stream=True -- confirmado con datos reales que\n    /v1beta/{contentUri}?fileType=STL regresa un .zip con el/los STL\n    (uno por maxilar). Regresa el objeto de respuesta de requests SIN\n    leerlo completo (el llamador debe iterar r.iter_content() y cerrar\n    la conexión, típicamente dentro de un StreamingResponse de FastAPI)\n    -- estos archivos pueden pesar 25MB+ y este servidor corre con poca\n    RAM (plan gratis de Render), así que nunca hay que descargarlos\n    completos a memoria."""\n    params = {"fileType": file_type} if file_type else None\n    try:\n        r = requests.get(\n            f"{base_host.rstrip(\'/\')}/v1beta/{content_uri.lstrip(\'/\')}",\n            params=params,\n            headers={"Authorization": f"Bearer {access_token}"},\n            timeout=TIMEOUT,\n            stream=True,\n        )\n    except requests.RequestException as e:\n        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")\n    if not r.ok:\n        r.close()\n        raise DSCoreError(f"DS Core respondió con error ({r.status_code}) al pedir el archivo")\n    return r\n\n\ndef extraer_piezas_de_order(order):',
        ],
    ],
    'backend/app.py': [
        [
            'from fastapi.responses import FileResponse, Response',
            'from fastapi.responses import FileResponse, Response, StreamingResponse',
        ],
        [
            '@app.post("/api/laboratorio/{trabajo_id}/recibir-sucursal")',
            '@app.get("/api/laboratorio/{trabajo_id}/descargar-escaneo-original")\ndef api_descargar_escaneo_original_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    """Descarga el/los archivo(s) STL del ESCANEO ORIGINAL que se hizo en\n    DS Core (Dentsply Sirona) para este pedido -- distinto al diseño que\n    el laboratorio sube después en \'Aprobar diseño\' (eso ya tiene su\n    propio endpoint). Solo se puede descargar una vez que el pago quedó\n    cubierto por completo.\n\n    DS Core siempre entrega el contenido dentro de un .zip (puede traer\n    un archivo por maxilar, ej. UpperJaw.stl/LowerJaw.stl -- confirmado\n    con un pedido real) -- este endpoint hace de puente: pide el archivo\n    a DS Core en el momento y lo transmite directo al navegador, SIN\n    guardar una copia en la base de datos (los escaneos pesan 25MB+ cada\n    uno, muy por encima de lo que se guarda hoy en Postgres para fotos,\n    firmas o el diseño que sube el laboratorio)."""\n    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail="Trabajo no encontrado")\n    if not trabajo.get("dscore_order_name"):\n        raise HTTPException(status_code=400, detail="Este trabajo no viene de un pedido de DS Core -- no hay escaneo original que descargar.")\n    if not trabajo.get("pago_registrado_en") or round(trabajo["costo_total"] - trabajo["pago_monto_total"], 2) > 0:\n        raise HTTPException(status_code=400, detail="Todavía no se puede descargar el escaneo original -- falta confirmar el pago completo.")\n    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])\n    if not tokens:\n        raise HTTPException(status_code=400, detail="DS Core todavía no está conectado -- ve a Administrar → Laboratorio → DS Core.")\n    access_token = _access_token_dscore_vigente(usuario["empresa_id"])\n    try:\n        order = dscore.obtener_order_por_name(tokens["base_host"], access_token, trabajo["dscore_order_name"])\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")\n    if not order:\n        raise HTTPException(status_code=404, detail="Ya no se encontró este pedido en DS Core.")\n    archivo = dscore.buscar_archivo_escaneo_de_order(order)\n    if not archivo or not archivo.get("uri"):\n        raise HTTPException(status_code=404, detail="Este pedido de DS Core no trae ningún escaneo adjunto.")\n    try:\n        metadata = dscore.obtener_metadata_archivo(tokens["base_host"], access_token, archivo["uri"])\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")\n    content_uri = metadata.get("contentUri")\n    if not content_uri:\n        raise HTTPException(status_code=502, detail="DS Core no indicó cómo descargar el contenido de este escaneo.")\n    try:\n        r = dscore.descargar_contenido_stream(tokens["base_host"], access_token, content_uri, file_type="STL")\n    except dscore.DSCoreError as e:\n        raise HTTPException(status_code=502, detail=f"No se pudo descargar el escaneo desde DS Core: {e}")\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "Descargó el escaneo original (STL) del pedido de DS Core.")\n    nombre_descarga = f"escaneo_original_{trabajo[\'folio\']}.zip"\n    return StreamingResponse(\n        r.iter_content(chunk_size=65536),\n        media_type="application/zip",\n        headers={"Content-Disposition": f\'attachment; filename="{nombre_descarga}"\'},\n    )\n\n\n@app.post("/api/laboratorio/{trabajo_id}/recibir-sucursal")',
        ],
    ],
    'frontend/index.html': [
        [
            '    ${yaPagado ? `\n      <label style="font-family:\'JetBrains Mono\',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;">Pago registrado — total pagado ${_fmtC(w.pago_monto_total)}</label>\n      <p style="font-size:12px; margin:4px 0;">${w.pago_metodos.map(m => `${NOMBRES_METODO_PAGO_LAB[m.metodo]||m.metodo}: ${_fmtC(m.monto)}`).join(\' · \')}</p>\n      ${w.pago_comprobante_base64 ? `<img src="${w.pago_comprobante_base64}" style="width:90px; height:90px; object-fit:cover; border-radius:6px; cursor:pointer;" onclick="window.open(\'${w.pago_comprobante_base64}\',\'_blank\')" title="Comprobante de pago" />` : \'\'}\n      ${saldo > 0 ? `<p style="font-size:13px; color:var(--trace); margin-top:6px;">💰 Sobrante: ${_fmtC(saldo)}</p>` : \'\'}\n      ${saldo < 0 && w.estado === \'recibido\' ? `\n        <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;">\n          <p style="font-size:13px; margin:0 0 8px;">⚠️ Falta cubrir ${_fmtC(-saldo)} — no se puede continuar (firmar recepción) hasta completar el pago.</p>\n          <button class="primary" style="width:100%;" onclick="abrirRegistrarPagoLaboratorio(${w.id})">Registrar pago adicional</button>\n        </div>\n      ` : \'\'}\n    ` : \'\'}',
            '    ${yaPagado ? `\n      <label style="font-family:\'JetBrains Mono\',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;">Pago registrado — total pagado ${_fmtC(w.pago_monto_total)}</label>\n      <p style="font-size:12px; margin:4px 0;">${w.pago_metodos.map(m => `${NOMBRES_METODO_PAGO_LAB[m.metodo]||m.metodo}: ${_fmtC(m.monto)}`).join(\' · \')}</p>\n      ${w.pago_comprobante_base64 ? `<img src="${w.pago_comprobante_base64}" style="width:90px; height:90px; object-fit:cover; border-radius:6px; cursor:pointer;" onclick="window.open(\'${w.pago_comprobante_base64}\',\'_blank\')" title="Comprobante de pago" />` : \'\'}\n      ${saldo > 0 ? `<p style="font-size:13px; color:var(--trace); margin-top:6px;">💰 Sobrante: ${_fmtC(saldo)}</p>` : \'\'}\n      ${saldo < 0 && w.estado === \'recibido\' ? `\n        <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;">\n          <p style="font-size:13px; margin:0 0 8px;">⚠️ Falta cubrir ${_fmtC(-saldo)} — no se puede continuar (firmar recepción) hasta completar el pago.</p>\n          <button class="primary" style="width:100%;" onclick="abrirRegistrarPagoLaboratorio(${w.id})">Registrar pago adicional</button>\n        </div>\n      ` : \'\'}\n    ` : \'\'}\n    ${w.dscore_order_name && saldo >= 0 ? `\n      <button class="secondary" style="width:100%; margin-top:10px;" onclick="descargarEscaneoOriginalLaboratorioUI(${w.id}, this)">⬇️ Descargar escaneo original (DS Core)</button>\n    ` : \'\'}',
        ],
        [
            "async function descargarPdfLaboratorio(id, nombreArchivo) {\n  try {\n    const r = await fetch(`/api/laboratorio/${id}/orden-trabajo.pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error('No se pudo generar el PDF');\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url;\n    a.download = `${nombreArchivo}.pdf`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  }\n}",
            "async function descargarPdfLaboratorio(id, nombreArchivo) {\n  try {\n    const r = await fetch(`/api/laboratorio/${id}/orden-trabajo.pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error('No se pudo generar el PDF');\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url;\n    a.download = `${nombreArchivo}.pdf`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nasync function descargarEscaneoOriginalLaboratorioUI(id, btn) {\n  const original = btn.textContent;\n  btn.disabled = true;\n  btn.textContent = 'Descargando…';\n  try {\n    const r = await fetch(`/api/laboratorio/${id}/descargar-escaneo-original`, { headers: headers(false) });\n    if (!r.ok) {\n      let msg = 'No se pudo descargar el escaneo original';\n      try { msg = (await r.json()).detail || msg; } catch (e) {}\n      throw new Error(msg);\n    }\n    const blob = await r.blob();\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url;\n    a.download = `escaneo_original_${id}.zip`;\n    document.body.appendChild(a);\n    a.click();\n    a.remove();\n    URL.revokeObjectURL(url);\n  } catch (e) {\n    alert(e.message);\n  } finally {\n    btn.disabled = false;\n    btn.textContent = original;\n  }\n}",
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
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
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
    print("    git add backend/dscore.py backend/app.py frontend/index.html")
    print('    git commit -m "Laboratorio: descargar el escaneo STL original del pedido de DS Core, una vez pagado"')
    print("    git push")


if __name__ == "__main__":
    main()
