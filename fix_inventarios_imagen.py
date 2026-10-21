# -*- coding: utf-8 -*-
"""
INVENTARIOS: FOTO DEL PRODUCTO (servidor)
- Al contar, si el producto no tiene foto, se le puede tomar una desde la app.
  Se guarda en la base de tickets-ti (tabla articulos_imagenes, por empresa y
  articulo de Microsip). Si ya tiene foto, solo el admin o la encargada la cambian.
- PUT /api/inventarios/imagen ; el producto escaneado trae su foto y la lista
  del inventario marca los que no tienen.
REQUIERE haber corrido antes fix_inventarios.py.
Toca: backend/db.py, backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_inventarios_imagen.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "            contado_en TEXT NOT NULL\n        );\n        CREATE INDEX IF NOT EXISTS idx_inventario_conteos_inv ON inventario_conteos (inventario_id, articulo_id);\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_crm BOOLEAN NOT NULL DEFAULT TRUE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_asistente_ia BOOLEAN NOT NULL DEFAULT FALSE;\n        -- Ver la ficha de empleado (salario, datos personales, vacaciones de\n",
   "            contado_en TEXT NOT NULL\n        );\n        CREATE INDEX IF NOT EXISTS idx_inventario_conteos_inv ON inventario_conteos (inventario_id, articulo_id);\n        -- Foto del producto (se toma en el inventario si no tiene). Por empresa y\n        -- ARTICULO_ID de Microsip; se guarda como Data URL.\n        CREATE TABLE IF NOT EXISTS articulos_imagenes (\n            empresa_id INTEGER NOT NULL,\n            articulo_id INTEGER NOT NULL,\n            imagen TEXT NOT NULL,\n            subida_por_id INTEGER REFERENCES users(id),\n            subida_en TEXT NOT NULL,\n            PRIMARY KEY (empresa_id, articulo_id)\n        );\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_crm BOOLEAN NOT NULL DEFAULT TRUE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_asistente_ia BOOLEAN NOT NULL DEFAULT FALSE;\n        -- Ver la ficha de empleado (salario, datos personales, vacaciones de\n"
  ],
  [
   "    return n > 0\n\n\ndef cambiar_estado_inventario(empresa_id, inventario_id, estado, usuario_id, resumen_json=None):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return n > 0\n\n\ndef obtener_imagen_articulo(empresa_id, articulo_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT a.imagen, a.subida_en, u.nombre_completo AS subida_por FROM articulos_imagenes a\n                   LEFT JOIN users u ON u.id = a.subida_por_id WHERE a.empresa_id = %s AND a.articulo_id = %s\"\"\",\n                (empresa_id, articulo_id))\n    r = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(r) if r else None\n\n\ndef guardar_imagen_articulo(empresa_id, articulo_id, imagen, usuario_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"INSERT INTO articulos_imagenes (empresa_id, articulo_id, imagen, subida_por_id, subida_en)\n                   VALUES (%s, %s, %s, %s, %s)\n                   ON CONFLICT (empresa_id, articulo_id) DO UPDATE\n                   SET imagen = EXCLUDED.imagen, subida_por_id = EXCLUDED.subida_por_id, subida_en = EXCLUDED.subida_en\"\"\",\n                (empresa_id, articulo_id, imagen, usuario_id, ahora().isoformat(timespec=\"seconds\")))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef articulos_con_imagen(empresa_id, articulo_ids):\n    ids = list({int(a) for a in articulo_ids or []})\n    if not ids:\n        return set()\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT articulo_id FROM articulos_imagenes WHERE empresa_id = %s AND articulo_id = ANY(%s)\", (empresa_id, ids))\n    r = {x[\"articulo_id\"] for x in cur.fetchall()}\n    cur.close(); conn.close()\n    return r\n\n\ndef cambiar_estado_inventario(empresa_id, inventario_id, estado, usuario_id, resumen_json=None):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "backend/app.py": [
  [
   "    inv = _inventario_de(usuario, inventario_id)\n    filas = _agrupar_conteos(db.listar_conteos_inventario(inventario_id))\n    inv.pop(\"resumen_json\", None)\n    return {**inv, \"filas\": filas, \"puede_cerrar\": _es_jefe_inventario(usuario, inv),\n            \"totales\": {\"productos\": len({f[\"articulo_id\"] for f in filas}), \"lineas\": len(filas),\n                        \"piezas\": round(sum(f[\"contado\"] for f in filas), 4),\n                        \"con_diferencia\": sum(1 for f in filas if f[\"diferencia\"])}}\n\n\n@app.get(\"/api/inventarios/{inventario_id}/buscar\")\n",
   "    inv = _inventario_de(usuario, inventario_id)\n    filas = _agrupar_conteos(db.listar_conteos_inventario(inventario_id))\n    inv.pop(\"resumen_json\", None)\n    con_imagen = db.articulos_con_imagen(usuario[\"empresa_id\"], [f[\"articulo_id\"] for f in filas])\n    for f in filas:\n        f[\"tiene_imagen\"] = f[\"articulo_id\"] in con_imagen\n    return {**inv, \"filas\": filas, \"puede_cerrar\": _es_jefe_inventario(usuario, inv),\n            \"totales\": {\"productos\": len({f[\"articulo_id\"] for f in filas}), \"lineas\": len(filas),\n                        \"piezas\": round(sum(f[\"contado\"] for f in filas), 4),\n                        \"con_diferencia\": sum(1 for f in filas if f[\"diferencia\"]),\n                        \"sin_imagen\": len({f[\"articulo_id\"] for f in filas if not f[\"tiene_imagen\"]})}}\n\n\n@app.get(\"/api/inventarios/{inventario_id}/buscar\")\n"
  ],
  [
   "    p[\"venta_reciente\"] = m is not None and m <= MINUTOS_VENTA_RECIENTE\n    p[\"ya_contado\"] = [{\"lote\": g[\"lote\"], \"contado\": g[\"contado\"]}\n                       for g in _agrupar_conteos(db.listar_conteos_inventario(inventario_id, p[\"articulo_id\"]))]\n    return p\n\n\nclass ConteoIn(BaseModel):\n",
   "    p[\"venta_reciente\"] = m is not None and m <= MINUTOS_VENTA_RECIENTE\n    p[\"ya_contado\"] = [{\"lote\": g[\"lote\"], \"contado\": g[\"contado\"]}\n                       for g in _agrupar_conteos(db.listar_conteos_inventario(inventario_id, p[\"articulo_id\"]))]\n    img = db.obtener_imagen_articulo(usuario[\"empresa_id\"], p[\"articulo_id\"])\n    p[\"imagen\"] = img[\"imagen\"] if img else None\n    p[\"imagen_por\"] = img.get(\"subida_por\") if img else None\n    # Si ya tiene foto, solo el admin o el encargado la pueden cambiar.\n    p[\"puede_cambiar_imagen\"] = not img or usuario[\"rol\"] in (\"admin\", \"encargado_sucursal\")\n    return p\n\n\nclass ImagenArticuloIn(BaseModel):\n    articulo_id: int\n    imagen: str = Field(max_length=4_000_000)\n\n\n@app.put(\"/api/inventarios/imagen\")\ndef api_inventario_imagen(payload: ImagenArticuloIn, usuario: dict = Depends(requiere_inventarios)):\n    \"\"\"Foto del producto, tomada durante el inventario si no tiene.\"\"\"\n    if not payload.imagen.startswith(\"data:image/\"):\n        raise HTTPException(status_code=400, detail=\"La imagen no es válida\")\n    if len(payload.imagen) > 3_500_000:\n        raise HTTPException(status_code=400, detail=\"La foto pesa demasiado (máximo 2.5 MB)\")\n    actual = db.obtener_imagen_articulo(usuario[\"empresa_id\"], payload.articulo_id)\n    if actual and usuario[\"rol\"] not in (\"admin\", \"encargado_sucursal\"):\n        raise HTTPException(status_code=403, detail=\"Este producto ya tiene foto; solo el encargado o el admin la pueden cambiar.\")\n    db.guardar_imagen_articulo(usuario[\"empresa_id\"], payload.articulo_id, payload.imagen, usuario[\"id\"])\n    return {\"ok\": True}\n\n\nclass ConteoIn(BaseModel):\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_inventarios_imagen.py")
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
            if nuevo in texto:
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
