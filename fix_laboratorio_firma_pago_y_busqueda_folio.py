#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio: el pago del estudiante hecho desde su propia app cuenta como
firma de recepcion (ya no le pide dibujar una firma aparte), y la busqueda
de "entrega" en cualquier sucursal ahora tambien encuentra el trabajo por
numero de pedido (folio), no solo por matricula o nombre.

Por que: David pidio que, como el estudiante paga desde su propia cuenta
autenticada en la app, eso ya cuente como si hubiera firmado -- no tiene
sentido pedirle dibujar una firma extra despues de eso. Tambien pidio que
en la ventanilla de entrega se pueda buscar el trabajo por matricula O por
numero de pedido.

Que cambia:
- backend/db.py: nueva constante FIRMA_AUTOMATICA_PAGO_APP (el valor que se
  guarda en firma_recepcion en vez de un dibujo, para marcar que fue
  automatica); buscar_trabajos_laboratorio_para_entrega() ahora tambien
  busca por folio.
- backend/app.py: api_confirmar_pago_reportado_laboratorio() -- cuando el
  laboratorio confirma un pago que el ESTUDIANTE reporto desde su portal, si
  con eso el trabajo queda totalmente cubierto y todavia no tiene firma, se
  le pone la firma automatica sola (nunca toca pagos registrados a mano en
  el mostrador -- esos siguen pidiendo la firma de siempre).
- backend/pdfs_laboratorio.py: la orden de trabajo en PDF, en vez de decir
  "sin firma registrada" cuando la firma es automatica, explica que el
  estudiante confirmo al pagar desde la app.
- frontend/index.html (panel del laboratorio/administrador): en vez de
  intentar mostrar la firma automatica como imagen (saldria en blanco),
  muestra un texto explicando que fue automatica por el pago.

No se toca nada del flujo de pagos registrados en persona en el mostrador
(api_registrar_pago_laboratorio) -- esos trabajos siguen pidiendo la firma
de siempre, a mano.
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '    return PRECIOS_FIJOS_LABORATORIO_BUAP.get((tipo_trabajo, (material or "").lower()))\n\nTABLAS_BORRADO_MASIVO = {',
            '    return PRECIOS_FIJOS_LABORATORIO_BUAP.get((tipo_trabajo, (material or "").lower()))\n\n# Valor especial que se guarda en trabajos_laboratorio.firma_recepcion cuando\n# el estudiante paga desde su propia cuenta en la app: eso YA cuenta como\n# firma (lo hizo él mismo, autenticado), así que no se le vuelve a pedir que\n# dibuje una firma aparte. No es un data-URI de imagen -- el frontend y el\n# generador de PDF lo detectan y muestran un texto en vez de intentar\n# dibujarlo como imagen.\nFIRMA_AUTOMATICA_PAGO_APP = "AUTO_FIRMA_PAGO_APP"\n\nTABLAS_BORRADO_MASIVO = {',
        ],
        [
            'def buscar_trabajos_laboratorio_para_entrega(empresa_id, texto_busqueda):\n    """Para la ventanilla de CUALQUIER sucursal: busca por matrícula\n    (usuario del estudiante) o por el nombre de quien pide, sin importar a\n    qué sucursal esté asignado el trabajo -- así el personal sabe si existe,\n    si ya está pagado, y en qué sucursal está en realidad (por si el\n    estudiante llegó a la sucursal equivocada a recogerlo)."""\n    conn = get_connection()\n    cur = conn.cursor()\n    como_texto = f"%{texto_busqueda.strip()}%"\n    cur.execute(\n        _trabajo_laboratorio_query_base() + """\n            WHERE l.empresa_id = %s\n              AND (uc.username ILIKE %s OR l.solicitante_nombre ILIKE %s)\n            ORDER BY l.creado_en DESC\n            LIMIT 20\n        """,\n        (empresa_id, como_texto, como_texto),\n    )',
            'def buscar_trabajos_laboratorio_para_entrega(empresa_id, texto_busqueda):\n    """Para la ventanilla de CUALQUIER sucursal: busca por matrícula\n    (usuario del estudiante), por el nombre de quien pide, o por el número\n    de pedido (folio) -- sin importar a qué sucursal esté asignado el\n    trabajo -- así el personal sabe si existe, si ya está pagado, y en qué\n    sucursal está en realidad (por si el estudiante llegó a la sucursal\n    equivocada a recogerlo)."""\n    conn = get_connection()\n    cur = conn.cursor()\n    como_texto = f"%{texto_busqueda.strip()}%"\n    cur.execute(\n        _trabajo_laboratorio_query_base() + """\n            WHERE l.empresa_id = %s\n              AND (uc.username ILIKE %s OR l.solicitante_nombre ILIKE %s OR l.folio ILIKE %s)\n            ORDER BY l.creado_en DESC\n            LIMIT 20\n        """,\n        (empresa_id, como_texto, como_texto, como_texto),\n    )',
        ],
    ],
    'backend/app.py': [
        [
            '@app.post("/api/laboratorio/pagos-reportados/{reporte_id}/confirmar")\ndef api_confirmar_pago_reportado_laboratorio(reporte_id: int, payload: ConfirmarPagoReportado, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    reporte, trabajo = _obtener_reporte_y_trabajo_o_404(usuario, reporte_id)\n    if not payload.metodos:\n        raise HTTPException(status_code=400, detail="Indica al menos un método de pago")\n    for m in payload.metodos:\n        if m.metodo not in db.TIPOS_METODO_PAGO_LABORATORIO:\n            raise HTTPException(status_code=400, detail="Método de pago inválido")\n    db.registrar_pago_laboratorio(\n        usuario["empresa_id"], reporte["trabajo_id"], usuario["id"],\n        [m.model_dump() for m in payload.metodos], reporte["comprobante_base64"],\n    )\n    db.confirmar_pago_reportado_laboratorio(usuario["empresa_id"], reporte_id, usuario["id"])\n    monto_total = round(sum(m.monto for m in payload.metodos), 2)\n    metodos_texto = ", ".join(f"{NOMBRES_METODO_PAGO_LABORATORIO.get(m.metodo, m.metodo)} ${m.monto:,.2f}" for m in payload.metodos)\n    db.agregar_actualizacion_laboratorio(reporte["trabajo_id"], usuario["id"], f"Confirmó el pago reportado por transferencia — {metodos_texto}.")\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])',
            '@app.post("/api/laboratorio/pagos-reportados/{reporte_id}/confirmar")\ndef api_confirmar_pago_reportado_laboratorio(reporte_id: int, payload: ConfirmarPagoReportado, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    reporte, trabajo = _obtener_reporte_y_trabajo_o_404(usuario, reporte_id)\n    if not payload.metodos:\n        raise HTTPException(status_code=400, detail="Indica al menos un método de pago")\n    for m in payload.metodos:\n        if m.metodo not in db.TIPOS_METODO_PAGO_LABORATORIO:\n            raise HTTPException(status_code=400, detail="Método de pago inválido")\n    db.registrar_pago_laboratorio(\n        usuario["empresa_id"], reporte["trabajo_id"], usuario["id"],\n        [m.model_dump() for m in payload.metodos], reporte["comprobante_base64"],\n    )\n    db.confirmar_pago_reportado_laboratorio(usuario["empresa_id"], reporte_id, usuario["id"])\n    monto_total = round(sum(m.monto for m in payload.metodos), 2)\n    metodos_texto = ", ".join(f"{NOMBRES_METODO_PAGO_LABORATORIO.get(m.metodo, m.metodo)} ${m.monto:,.2f}" for m in payload.metodos)\n    db.agregar_actualizacion_laboratorio(reporte["trabajo_id"], usuario["id"], f"Confirmó el pago reportado por transferencia — {metodos_texto}.")\n    trabajo_actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])\n    # El estudiante reportó este pago desde su propia cuenta en la app -- eso\n    # YA es su confirmación de que los datos y el odontograma están\n    # correctos, igual que si hubiera dibujado la firma a mano. En cuanto\n    # queda cubierto el costo total, se le pone la firma sola para no\n    # pedirle ese paso aparte.\n    if not trabajo_actualizado.get("firma_recepcion"):\n        faltante = round(trabajo_actualizado["costo_total"] - trabajo_actualizado["pago_monto_total"], 2)\n        if faltante <= 0:\n            db.firmar_recepcion_laboratorio(usuario["empresa_id"], reporte["trabajo_id"], db.FIRMA_AUTOMATICA_PAGO_APP)\n            db.agregar_actualizacion_laboratorio(\n                reporte["trabajo_id"], usuario["id"],\n                "Firma de recepción automática: el estudiante ya había pagado desde su propia cuenta en la app.",\n            )\n            trabajo_actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])\n    return trabajo_actualizado',
        ],
    ],
    'backend/pdfs_laboratorio.py': [
        [
            '    firma_img = _imagen_desde_base64(trabajo.get("firma_recepcion"))\n    if firma_img:\n        alto_firma = 2.6 * cm\n        c.drawImage(firma_img, MARGIN, y - alto_firma - 6, width=6.5 * cm, height=alto_firma,\n                    preserveAspectRatio=True, anchor="sw", mask="auto")\n        y -= (alto_firma + 14)\n    else:\n        c.setFont("Helvetica-Oblique", 9)\n        c.setFillColor(MUTED)\n        c.drawString(MARGIN, y - 16, "— sin firma registrada —")\n        y -= 26',
            '    firma_img = _imagen_desde_base64(trabajo.get("firma_recepcion"))\n    if firma_img:\n        alto_firma = 2.6 * cm\n        c.drawImage(firma_img, MARGIN, y - alto_firma - 6, width=6.5 * cm, height=alto_firma,\n                    preserveAspectRatio=True, anchor="sw", mask="auto")\n        y -= (alto_firma + 14)\n    elif trabajo.get("firma_recepcion") == "AUTO_FIRMA_PAGO_APP":\n        c.setFont("Helvetica-Oblique", 9)\n        c.setFillColor(MUTED)\n        c.drawString(MARGIN, y - 16, "Firma automática — el estudiante confirmó al pagar desde su cuenta en la app.")\n        y -= 26\n    else:\n        c.setFont("Helvetica-Oblique", 9)\n        c.setFillColor(MUTED)\n        c.drawString(MARGIN, y - 16, "— sin firma registrada —")\n        y -= 26',
        ],
    ],
    'frontend/index.html': [
        [
            '    ${w.firma_recepcion ? `\n      <img src="${w.firma_recepcion}" style="max-width:220px; background:#fff; border-radius:6px; margin-bottom:6px;" title="Firma de recepción" />\n      <br><button class="secondary" style="margin-bottom:10px;" onclick="descargarPdfLaboratorio(${w.id}, \'orden_trabajo_${w.folio}\')">📄 Descargar orden de trabajo (PDF)</button>\n    ` : \'\'}',
            '    ${w.firma_recepcion ? `\n      ${w.firma_recepcion === \'AUTO_FIRMA_PAGO_APP\' ? `\n        <p style="font-size:13px; color:var(--muted); margin-bottom:6px;">✅ Firma automática — el estudiante confirmó al pagar desde su propia cuenta en la app.</p>\n      ` : `\n        <img src="${w.firma_recepcion}" style="max-width:220px; background:#fff; border-radius:6px; margin-bottom:6px;" title="Firma de recepción" />\n      `}\n      <br><button class="secondary" style="margin-bottom:10px;" onclick="descargarPdfLaboratorio(${w.id}, \'orden_trabajo_${w.folio}\')">📄 Descargar orden de trabajo (PDF)</button>\n    ` : \'\'}',
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
    print("    git add backend/db.py backend/app.py backend/pdfs_laboratorio.py frontend/index.html")
    print('    git commit -m "Laboratorio: pago del estudiante desde la app cuenta como firma; buscar entrega tambien por folio"')
    print("    git push")


if __name__ == "__main__":
    main()
