# -*- coding: utf-8 -*-
"""
Cotizaciones: igual que Tickets y Reparaciones, el rol "usuario" (empleado)
ahora solo ve/edita/elimina las cotizaciones que el mismo creo -- los demas
roles (admin, tecnico, etc.) siguen viendo todas las de la empresa.

Uso: colocalo en la carpeta del repo (junto a backend/) y corre:
    py fix_cotizaciones_solo_mias.py
"""
import sys

ARCHIVOS = {'backend/db.py': [['def listar_cotizaciones(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("""\n        SELECT c.*, u.nombre_completo AS creado_por_nombre,\n               u.telefono_whatsapp AS creador_telefono, u.sucursal_id AS creador_sucursal_id\n        FROM cotizaciones c\n        LEFT JOIN users u ON u.id = c.creado_por_id\n        WHERE c.empresa_id = %s ORDER BY c.id DESC\n    """, (empresa_id,))\n    cotizaciones = [dict(r) for r in cur.fetchall()]\n    for c in cotizaciones:\n        _enriquecer_cotizacion(cur, c)\n    cur.close(); conn.close()\n    return cotizaciones', 'def listar_cotizaciones(empresa_id, creado_por_id=None):\n    conn = get_connection()\n    cur = conn.cursor()\n    query = """\n        SELECT c.*, u.nombre_completo AS creado_por_nombre,\n               u.telefono_whatsapp AS creador_telefono, u.sucursal_id AS creador_sucursal_id\n        FROM cotizaciones c\n        LEFT JOIN users u ON u.id = c.creado_por_id\n        WHERE c.empresa_id = %s\n    """\n    params = [empresa_id]\n    if creado_por_id:\n        query += " AND c.creado_por_id = %s"\n        params.append(creado_por_id)\n    query += " ORDER BY c.id DESC"\n    cur.execute(query, params)\n    cotizaciones = [dict(r) for r in cur.fetchall()]\n    for c in cotizaciones:\n        _enriquecer_cotizacion(cur, c)\n    cur.close(); conn.close()\n    return cotizaciones']], 'backend/app.py': [['@app.get("/api/cotizaciones")\ndef api_listar_cotizaciones(usuario: dict = Depends(requiere_ver_checador_precio)):\n    return db.listar_cotizaciones(usuario["empresa_id"])', '@app.get("/api/cotizaciones")\ndef api_listar_cotizaciones(usuario: dict = Depends(requiere_ver_checador_precio)):\n    # Igual que Tickets y Reparaciones: el rol "usuario" (empleado) solo ve\n    # las cotizaciones que él mismo creó; los demás roles siguen viendo\n    # todas las de la empresa.\n    creado_por_id = usuario["id"] if usuario["rol"] == "usuario" else None\n    return db.listar_cotizaciones(usuario["empresa_id"], creado_por_id)'], ['@app.get("/api/cotizaciones/{cotizacion_id}")\ndef api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return cotizacion\n\n\n@app.get("/api/cotizaciones/{cotizacion_id}/pdf")\ndef api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    empresa = db.obtener_empresa(usuario["empresa_id"])\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa)\n    return Response(content=pdf_bytes, media_type="application/pdf",\n                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion[\'folio\']}.pdf"})\n\n\n@app.post("/api/cotizaciones/{cotizacion_id}/liga-impresion")\ndef api_generar_liga_impresion_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    """Genera la liga pública y corta que se le manda a la app Star PassPRNT\n    (ella hace su propia petición HTTP para traer el recibo — no lleva el\n    token de sesión de la app, así que necesita una ruta pública aparte)."""\n    token = db.generar_token_impresion_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not token:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return {"token": token}', '@app.get("/api/cotizaciones/{cotizacion_id}")\ndef api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:\n        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")\n    return cotizacion\n\n\n@app.get("/api/cotizaciones/{cotizacion_id}/pdf")\ndef api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:\n        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")\n    empresa = db.obtener_empresa(usuario["empresa_id"])\n    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa)\n    return Response(content=pdf_bytes, media_type="application/pdf",\n                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion[\'folio\']}.pdf"})\n\n\n@app.post("/api/cotizaciones/{cotizacion_id}/liga-impresion")\ndef api_generar_liga_impresion_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    """Genera la liga pública y corta que se le manda a la app Star PassPRNT\n    (ella hace su propia petición HTTP para traer el recibo — no lleva el\n    token de sesión de la app, así que necesita una ruta pública aparte)."""\n    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not cotizacion:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:\n        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")\n    token = db.generar_token_impresion_cotizacion(usuario["empresa_id"], cotizacion_id)\n    return {"token": token}'], ['@app.put("/api/cotizaciones/{cotizacion_id}")\ndef api_actualizar_cotizacion(cotizacion_id: int, payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n    resultado = db.actualizar_cotizacion(\n        usuario["empresa_id"], cotizacion_id, payload.cliente_nombre, payload.cliente_direccion,\n        payload.cliente_telefono, payload.notas, [item.model_dump() for item in payload.items],\n        payload.tipo_cliente, payload.meses_msi,\n    )\n    if not resultado:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return resultado\n\n\n@app.delete("/api/cotizaciones/{cotizacion_id}")\ndef api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    if not db.eliminar_cotizacion(usuario["empresa_id"], cotizacion_id):\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    return {"ok": True}', '@app.put("/api/cotizaciones/{cotizacion_id}")\ndef api_actualizar_cotizacion(cotizacion_id: int, payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):\n    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not existente:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:\n        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")\n    resultado = db.actualizar_cotizacion(\n        usuario["empresa_id"], cotizacion_id, payload.cliente_nombre, payload.cliente_direccion,\n        payload.cliente_telefono, payload.notas, [item.model_dump() for item in payload.items],\n        payload.tipo_cliente, payload.meses_msi,\n    )\n    return resultado\n\n\n@app.delete("/api/cotizaciones/{cotizacion_id}")\ndef api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):\n    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)\n    if not existente:\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:\n        raise HTTPException(status_code=403, detail="No puedes eliminar esta cotización")\n    db.eliminar_cotizacion(usuario["empresa_id"], cotizacion_id)\n    return {"ok": True}']]}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    hubo_error = False
    for ruta, reemplazos in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
            hubo_error = True
            continue
        cambios = 0
        for viejo, nuevo in reemplazos:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
                hubo_error = True
                continue
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py backend/db.py")
    print('   git commit -m "Cotizaciones: rol usuario solo ve las suyas, igual que otros modulos"')
    print("   git push")


if __name__ == "__main__":
    main()
