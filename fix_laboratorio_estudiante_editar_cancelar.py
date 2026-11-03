# -*- coding: utf-8 -*-
"""Laboratorio: el estudiante puede EDITAR o CANCELAR su pedido desde la app
mientras no lo haya pagado (ni reportado su pago). Ya pagado, no se puede cambiar.
Correr en la carpeta tickets-ti:  py -3 fix_laboratorio_estudiante_editar_cancelar.py
"""
import os, sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "                (trabajo_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef marcar_trabajo_laboratorio_microsip(trabajo_id, docto_id=None, folio=None, error=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    if folio:\n        cur.execute(\"\"\"UPDATE trabajos_laboratorio SET microsip_docto_id = %s, microsip_folio = %s, microsip_enviada_en = %s,\n",
   "                (trabajo_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef reemplazar_piezas_laboratorio(trabajo_id, piezas):\n    \"\"\"Borra las piezas del trabajo y pone las nuevas (el estudiante editó su pedido antes de pagar).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM laboratorio_piezas WHERE trabajo_id = %s\", (trabajo_id,))\n    for p in piezas:\n        cur.execute(\"\"\"INSERT INTO laboratorio_piezas (trabajo_id, diente, tipo_trabajo, material, color, notas, costo)\n                       VALUES (%s, %s, %s, %s, %s, %s, %s)\"\"\",\n                    (trabajo_id, p.get(\"diente\"), p.get(\"tipo_trabajo\"), p.get(\"material\"), p.get(\"color\"), p.get(\"notas\"), p.get(\"costo\") or 0))\n    cur.execute(\"UPDATE trabajos_laboratorio SET actualizado_en = %s WHERE id = %s\", (ahora().isoformat(timespec=\"seconds\"), trabajo_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef olvidar_microsip_trabajo_laboratorio(trabajo_id):\n    \"\"\"Quita la liga con la cotización de Microsip (para volver a mandar el pedido editado).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"UPDATE trabajos_laboratorio SET microsip_docto_id = NULL, microsip_folio = NULL, microsip_enviada_en = NULL,\n                          microsip_error = NULL WHERE id = %s\"\"\", (trabajo_id,))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef marcar_trabajo_laboratorio_microsip(trabajo_id, docto_id=None, folio=None, error=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    if folio:\n        cur.execute(\"\"\"UPDATE trabajos_laboratorio SET microsip_docto_id = %s, microsip_folio = %s, microsip_enviada_en = %s,\n"
  ]
 ],
 "backend/app.py": [
  [
   "    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\n@app.get(\"/api/laboratorio/mios/{trabajo_id}\")\ndef api_obtener_mi_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n",
   "    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\nclass EditarPedidoEstudianteIn(BaseModel):\n    paciente_nombre: Optional[str] = Field(default=None, max_length=200)\n    notas: Optional[str] = Field(default=None, max_length=2000)\n    piezas: List[PiezaLaboratorioIn] = Field(default_factory=list)\n\n\nclass CancelarPedidoEstudianteIn(BaseModel):\n    motivo: Optional[str] = Field(default=None, max_length=300)\n\n\ndef _pedido_estudiante_editable(usuario, trabajo_id):\n    \"\"\"El estudiante solo puede cambiar o cancelar SU pedido mientras no haya pagado\n    (sin pago registrado ni comprobante por confirmar) y siga en recepción.\"\"\"\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if not trabajo:\n        raise HTTPException(status_code=404, detail=\"Trabajo no encontrado\")\n    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)\n    if trabajo[\"estado\"] != \"recibido\":\n        raise HTTPException(status_code=400, detail=\"Este pedido ya no se puede cambiar: ya entró al laboratorio o está cerrado.\")\n    if trabajo.get(\"pago_registrado_en\") or float(trabajo.get(\"pago_monto_total\") or 0) > 0:\n        raise HTTPException(status_code=400, detail=\"Este pedido ya está pagado: ya no se puede cambiar ni cancelar desde la app. Si necesitas algo, contáctanos.\")\n    if any(r.get(\"estado\") == \"pendiente\" for r in (trabajo.get(\"pagos_reportados\") or [])):\n        raise HTTPException(status_code=400, detail=\"Ya reportaste el pago de este pedido: ya no se puede cambiar ni cancelar desde la app.\")\n    return trabajo\n\n\n@app.patch(\"/api/laboratorio/mios/{trabajo_id}\")\ndef api_editar_mi_pedido_laboratorio(trabajo_id: int, payload: EditarPedidoEstudianteIn, background_tasks: BackgroundTasks,\n                                     usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    \"\"\"El estudiante corrige su pedido (dientes, material, tono, paciente, notas) antes de pagar.\"\"\"\n    trabajo = _pedido_estudiante_editable(usuario, trabajo_id)\n    if not payload.piezas:\n        raise HTTPException(status_code=400, detail=\"Elige al menos un diente en el odontograma.\")\n    piezas = []\n    for pieza in payload.piezas:\n        if pieza.tipo_trabajo not in db.TIPOS_TRABAJO_LABORATORIO:\n            raise HTTPException(status_code=400, detail=f\"Tipo de trabajo inválido para el diente {pieza.diente}\")\n        datos_pieza = pieza.model_dump()\n        precio = db.precio_fijo_laboratorio(\"BUAP\", pieza.tipo_trabajo, pieza.material)\n        if precio is not None:\n            datos_pieza[\"costo\"] = precio\n        piezas.append(datos_pieza)\n    antes = \", \".join(f\"{p.get('diente')} {p.get('material') or ''} {p.get('color') or ''}\".strip() for p in trabajo.get(\"piezas\") or [])\n    db.actualizar_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id,\n                                      paciente_nombre=(payload.paciente_nombre or \"\").strip(), notas=(payload.notas or \"\").strip())\n    db.reemplazar_piezas_laboratorio(trabajo_id, piezas)\n    ahora_txt = \", \".join(f\"{p['diente']} {p.get('material') or ''} {p.get('color') or ''}\".strip() for p in piezas)\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"], f\"✏️ El estudiante editó su pedido desde la app. Antes: {antes or '—'}. Ahora: {ahora_txt}.\")\n    folio_ms = trabajo.get(\"microsip_folio\")\n    if folio_ms:\n        # La cotización de Microsip ya no cuadra: se manda una nueva y se avisa de la anterior.\n        db.olvidar_microsip_trabajo_laboratorio(trabajo_id)\n        db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"],\n                                             f\"⚠️ La cotización {folio_ms} de Microsip quedó sin usar por la edición: cancélala en Microsip. Se manda una nueva.\")\n    if _lab_microsip_activo(usuario[\"empresa_id\"]):\n        background_tasks.add_task(_enviar_trabajo_lab_microsip_seguro, usuario[\"empresa_id\"], trabajo_id)\n    avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario[\"empresa_id\"]), f\"✏️ Pedido editado · {trabajo.get('folio', '')}\",\n                         f\"{usuario.get('nombre', '')} cambió su pedido antes de pagar.\", modulo=\"laboratorio\", ref=trabajo_id)\n    return db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n\n\n@app.post(\"/api/laboratorio/mios/{trabajo_id}/cancelar\")\ndef api_cancelar_mi_pedido_laboratorio(trabajo_id: int, payload: CancelarPedidoEstudianteIn,\n                                       usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    \"\"\"El estudiante cancela (borra) su pedido antes de pagar. Queda registrado, no se borra de la base.\"\"\"\n    trabajo = _pedido_estudiante_editable(usuario, trabajo_id)\n    motivo = \"Cancelado por el estudiante desde la app\" + (f\": {payload.motivo.strip()}\" if (payload.motivo or \"\").strip() else \"\")\n    db.cancelar_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id, motivo, usuario[\"id\"])\n    db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"], f\"❌ {motivo}.\")\n    if trabajo.get(\"microsip_folio\"):\n        db.agregar_actualizacion_laboratorio(trabajo_id, usuario[\"id\"],\n                                             f\"⚠️ Cancela también la cotización {trabajo['microsip_folio']} en Microsip.\")\n    t = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n    if t:\n        db.marcar_push_trabajo_laboratorio(trabajo_id, _firma_push_lab(t))  # que no le llegue \"tu trabajo fue cancelado\" a él mismo\n    avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario[\"empresa_id\"]), f\"❌ Pedido cancelado · {trabajo.get('folio', '')}\",\n                         f\"{usuario.get('nombre', '')} canceló su pedido antes de pagar.\", modulo=\"laboratorio\", ref=trabajo_id)\n    return t\n\n\n@app.get(\"/api/laboratorio/mios/{trabajo_id}\")\ndef api_obtener_mi_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_estudiante_laboratorio)):\n    trabajo = db.obtener_trabajo_laboratorio(usuario[\"empresa_id\"], trabajo_id)\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_laboratorio_estudiante_editar_cancelar.py")
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
