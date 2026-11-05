# -*- coding: utf-8 -*-
"""Unidental: fichas tecnicas en PDF por producto, correo al administrador cuando llega un pedido
y contador de pendientes para el globito de la pestana Admin.
Correr en la carpeta tickets-ti:  py -3 fix_unidental_fichas_avisos.py
"""
import os, sys

ARCHIVOS = {
 "backend/tienda.py": [
  [
   "import secrets\nfrom decimal import Decimal\n",
   "import secrets\nimport unicodedata\nfrom decimal import Decimal\n"
  ],
  [
   "from pydantic import BaseModel, Field\n\nimport auth\nimport avisos\n",
   "from pydantic import BaseModel, Field\n\nimport threading\n\nimport auth\nimport avisos\n"
  ],
  [
   "import avisos\nimport db\n",
   "import avisos\nimport correo\nimport db\n"
  ],
  [
   "MAX_COMPROBANTE = 6_000_000\n\n",
   "MAX_COMPROBANTE = 6_000_000\nMAX_PDF = 15_000_000          # fichas técnicas / catálogos en PDF\n\n"
  ],
  [
   "        );\n        CREATE INDEX IF NOT EXISTS idx_tienda_productos_emp ON tienda_productos (empresa_id, activo);\n",
   "        );\n        CREATE TABLE IF NOT EXISTS tienda_documentos (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            producto_id INTEGER NOT NULL REFERENCES tienda_productos(id) ON DELETE CASCADE,\n            nombre TEXT NOT NULL,\n            datos BYTEA NOT NULL,\n            tamano INTEGER NOT NULL DEFAULT 0,\n            orden INTEGER NOT NULL DEFAULT 0,\n            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()\n        );\n        ALTER TABLE tienda_config ADD COLUMN IF NOT EXISTS correo_avisos TEXT;\n        CREATE INDEX IF NOT EXISTS idx_tienda_documentos_prod ON tienda_documentos (producto_id);\n        CREATE INDEX IF NOT EXISTS idx_tienda_productos_emp ON tienda_productos (empresa_id, activo);\n"
  ],
  [
   "               (SELECT COUNT(*) FROM tienda_videos v WHERE v.producto_id = p.id) AS videos\n",
   "               (SELECT COUNT(*) FROM tienda_videos v WHERE v.producto_id = p.id) AS videos,\n               (SELECT COUNT(*) FROM tienda_documentos d WHERE d.producto_id = p.id) AS documentos\n"
  ],
  [
   "    p[\"videos\"] = _q(\"SELECT id, titulo, url, en_feed FROM tienda_videos WHERE producto_id = %s ORDER BY orden, id\", (producto_id,))\n    return p\n",
   "    p[\"videos\"] = _q(\"SELECT id, titulo, url, en_feed FROM tienda_videos WHERE producto_id = %s ORDER BY orden, id\", (producto_id,))\n    p[\"documentos\"] = _q(\"SELECT id, nombre, tamano FROM tienda_documentos WHERE producto_id = %s ORDER BY orden, id\", (producto_id,))\n    return p\n"
  ],
  [
   "                 FROM tienda_videos v JOIN tienda_productos p ON p.id = v.producto_id AND p.activo\n                 LEFT JOIN tienda_marcas m ON m.id = p.marca_id\n                 WHERE v.empresa_id = %s AND v.en_feed ORDER BY v.orden, v.id DESC\"\"\", (t[\"empresa_id\"],))\n\n\n@router.get(\"/api/tienda/foto/{foto_id}\")\n",
   "                 FROM tienda_videos v JOIN tienda_productos p ON p.id = v.producto_id AND p.activo\n                 LEFT JOIN tienda_marcas m ON m.id = p.marca_id\n                 WHERE v.empresa_id = %s AND v.en_feed ORDER BY v.orden, v.id DESC\"\"\", (t[\"empresa_id\"],))\n\n\n@router.get(\"/api/tienda/documento/{doc_id}\")\ndef api_documento(doc_id: int):\n    \"\"\"Ficha técnica en PDF (pública, como las fotos): se abre en el visor del celular.\"\"\"\n    d = _q(\"SELECT nombre, datos FROM tienda_documentos WHERE id = %s\", (doc_id,), uno=True)\n    if not d:\n        raise HTTPException(status_code=404, detail=\"Documento no encontrado\")\n    nombre = unicodedata.normalize(\"NFKD\", d[\"nombre\"]).encode(\"ascii\", \"ignore\").decode()\n    nombre = re.sub(r\"[^A-Za-z0-9 ._-]\", \"\", nombre).strip() or \"ficha\"\n    return Response(content=bytes(d[\"datos\"]), media_type=\"application/pdf\",\n                    headers={\"Content-Disposition\": f'inline; filename=\"{nombre}.pdf\"', \"Cache-Control\": \"public, max-age=86400\"})\n\n\n@router.get(\"/api/tienda/foto/{foto_id}\")\n"
  ],
  [
   "    return [r[\"id\"] for r in _q(\"SELECT id FROM users WHERE empresa_id = %s AND rol = 'admin' AND activo\", (empresa_id,))]\n\n\n@router.post(\"/api/tienda/{codigo}/pedidos\")\ndef api_crear_pedido(codigo: str, payload: PedidoIn, request: Request, usuario: dict = Depends(requiere_doctor)):\n    t = tienda_por_codigo(codigo)\n",
   "    return [r[\"id\"] for r in _q(\"SELECT id FROM users WHERE empresa_id = %s AND rol = 'admin' AND activo\", (empresa_id,))]\n\n\ndef _correos_avisos(t):\n    \"\"\"A quién mandar el correo de pedido nuevo: los de Ajustes, o si no hay, el correo de cada administrador.\"\"\"\n    lista = [c.strip() for c in re.split(r\"[,;\\s]+\", t.get(\"correo_avisos\") or \"\") if \"@\" in c]\n    if not lista:\n        lista = [r[\"email\"] for r in _q(\"SELECT email FROM users WHERE empresa_id = %s AND rol = 'admin' AND activo AND email LIKE '%%@%%'\",\n                                          (t[\"empresa_id\"],))]\n    return list(dict.fromkeys(lista))\n\n\ndef _correo_pedido_nuevo(t, pedido):\n    \"\"\"En segundo plano: nunca retrasa ni tumba el pedido. Sin SMTP en Render no hace nada.\"\"\"\n    def mandar():\n        try:\n            if not correo.configurado():\n                return\n            renglones = \"\\n\".join(f\"  - {i['cantidad']} x {i['nombre']}{' ' + i['modelo'] if i.get('modelo') else ''}\"\n                                  f\" ({i.get('marca') or ''}) ${float(i['precio']) * i['cantidad']:,.2f}\" for i in pedido[\"items\"])\n            texto = (f\"Llegó un pedido nuevo en {t['nombre']}.\\n\\n\"\n                     f\"Folio: {pedido['folio']}\\nDoctor: {pedido.get('doctor') or ''}\\n\"\n                     f\"Teléfono: {pedido.get('telefono') or ''}\\nCorreo: {pedido.get('email') or ''}\\n\"\n                     f\"Consultorio: {pedido.get('consultorio') or ''} · {pedido.get('ciudad') or ''}\\n\"\n                     f\"Forma de pago: {pedido['forma_pago']}\\nTotal: ${float(pedido['total']):,.2f}\\n\\n\"\n                     f\"Productos:\\n{renglones}\\n\\nNotas: {pedido.get('notas') or '-'}\\n\"\n                     f\"Entrega: {pedido.get('direccion_entrega') or '-'}\\n\\n\"\n                     f\"Ábrelo en la app {t['nombre']} → Admin → Pedidos.\")\n            for c in _correos_avisos(t):\n                correo.enviar(c, f\"🛒 Pedido nuevo {pedido['folio']} — ${float(pedido['total']):,.2f}\", texto)\n        except Exception as e:\n            print(f\"[tienda] correo de pedido nuevo: {e}\")\n    threading.Thread(target=mandar, daemon=True).start()\n\n\n@router.post(\"/api/tienda/{codigo}/pedidos\")\ndef api_crear_pedido(codigo: str, payload: PedidoIn, request: Request, usuario: dict = Depends(requiere_doctor)):\n    t = tienda_por_codigo(codigo)\n"
  ],
  [
   "    r = {\"pedido\": _pedido(pid, t[\"empresa_id\"])}\n    if payload.forma_pago in (\"linea\", \"anticipo\"):\n",
   "    r = {\"pedido\": _pedido(pid, t[\"empresa_id\"])}\n    _correo_pedido_nuevo(t, r[\"pedido\"])\n    if payload.forma_pago in (\"linea\", \"anticipo\"):\n"
  ],
  [
   "    mp_access_token: Optional[str] = Field(default=None, max_length=200)\n\n",
   "    mp_access_token: Optional[str] = Field(default=None, max_length=200)\n    correo_avisos: Optional[str] = Field(default=None, max_length=300)\n\n"
  ],
  [
   "    return r\n\n\n@router.delete(\"/api/tienda/admin/videos/{video_id}\")\ndef api_borrar_video(video_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    v = _q(\"DELETE FROM tienda_videos WHERE id = %s AND empresa_id = %s RETURNING r2_key\", (video_id, usuario[\"empresa_id\"]), uno=True, commit=True)\n",
   "    return r\n\n\n@router.post(\"/api/tienda/admin/productos/{producto_id}/documentos\")\ndef api_subir_documento(producto_id: int, archivo: UploadFile = File(...), nombre: str = Form(\"\"),\n                        usuario: dict = Depends(requiere_admin_tienda)):\n    \"\"\"Ficha técnica, catálogo o manual en PDF (hasta 15 MB).\"\"\"\n    _producto_de_empresa(usuario[\"empresa_id\"], producto_id)\n    datos = archivo.file.read(MAX_PDF + 1)\n    if len(datos) > MAX_PDF:\n        raise HTTPException(status_code=400, detail=\"El PDF pesa más de 15 MB.\")\n    if not datos.startswith(b\"%PDF\"):\n        raise HTTPException(status_code=400, detail=\"El archivo no es un PDF.\")\n    nombre = (nombre or \"\").strip() or re.sub(r\"\\.pdf$\", \"\", (archivo.filename or \"Ficha técnica\"), flags=re.I).strip() or \"Ficha técnica\"\n    orden = (_q(\"SELECT COALESCE(MAX(orden), -1) + 1 AS o FROM tienda_documentos WHERE producto_id = %s\", (producto_id,), uno=True) or {}).get(\"o\", 0)\n    return _q(\"\"\"INSERT INTO tienda_documentos (empresa_id, producto_id, nombre, datos, tamano, orden) VALUES (%s, %s, %s, %s, %s, %s)\n                 RETURNING id, nombre, tamano\"\"\", (usuario[\"empresa_id\"], producto_id, nombre[:120], psycopg2.Binary(datos), len(datos), orden),\n              uno=True, commit=True)\n\n\n@router.delete(\"/api/tienda/admin/documentos/{doc_id}\")\ndef api_borrar_documento(doc_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    _q(\"DELETE FROM tienda_documentos WHERE id = %s AND empresa_id = %s\", (doc_id, usuario[\"empresa_id\"]), todos=False, commit=True)\n    return {\"ok\": True}\n\n\n@router.delete(\"/api/tienda/admin/videos/{video_id}\")\ndef api_borrar_video(video_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    v = _q(\"DELETE FROM tienda_videos WHERE id = %s AND empresa_id = %s RETURNING r2_key\", (video_id, usuario[\"empresa_id\"]), uno=True, commit=True)\n"
  ],
  [
   "        except Exception:\n            pass\n    return {\"ok\": True}\n\n\n@router.get(\"/api/tienda/admin/pedidos\")\n",
   "        except Exception:\n            pass\n    return {\"ok\": True}\n\n\n@router.get(\"/api/tienda/admin/pendientes\")\ndef api_pendientes_admin(usuario: dict = Depends(requiere_admin_tienda)):\n    \"\"\"Para el globito de la pestaña Admin: pedidos nuevos sin atender y comprobantes por revisar.\"\"\"\n    r = _q(\"\"\"SELECT (SELECT COUNT(*) FROM tienda_pedidos WHERE empresa_id = %s AND estado = 'recibido') AS nuevos,\n                      (SELECT COUNT(*) FROM tienda_pagos g JOIN tienda_pedidos p ON p.id = g.pedido_id\n                        WHERE p.empresa_id = %s AND g.estado = 'pendiente') AS pagos\"\"\",\n           (usuario[\"empresa_id\"], usuario[\"empresa_id\"]), uno=True) or {}\n    nuevos, pagos = int(r.get(\"nuevos\") or 0), int(r.get(\"pagos\") or 0)\n    return {\"nuevos\": nuevos, \"pagos\": pagos, \"total\": nuevos + pagos}\n\n\n@router.get(\"/api/tienda/admin/pedidos\")\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_unidental_fichas_avisos.py")
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
