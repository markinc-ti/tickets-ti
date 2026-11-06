# -*- coding: utf-8 -*-
"""Unidental: marcas/empresas con logo (arriba en la app), pagina de cada marca y carrusel
de promociones, videos y eventos (de Inicio y de cada marca) que se administra desde la app.
REQUIERE fix_unidental_fichas_avisos.py.
Correr en la carpeta tickets-ti:  py -3 fix_unidental_marcas_carrusel.py
"""
import os, sys

ARCHIVOS = {
 "backend/tienda.py": [
  [
   "        ALTER TABLE tienda_config ADD COLUMN IF NOT EXISTS correo_avisos TEXT;\n        CREATE INDEX IF NOT EXISTS idx_tienda_documentos_prod ON tienda_documentos (producto_id);\n",
   "        ALTER TABLE tienda_config ADD COLUMN IF NOT EXISTS correo_avisos TEXT;\n        CREATE TABLE IF NOT EXISTS tienda_banners (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            marca_id INTEGER REFERENCES tienda_marcas(id) ON DELETE CASCADE,\n            titulo TEXT,\n            texto TEXT,\n            etiqueta TEXT,\n            foto_id INTEGER,\n            video_url TEXT,\n            r2_key TEXT,\n            producto_id INTEGER REFERENCES tienda_productos(id) ON DELETE SET NULL,\n            link TEXT,\n            orden INTEGER NOT NULL DEFAULT 0,\n            activo BOOLEAN NOT NULL DEFAULT TRUE,\n            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()\n        );\n        CREATE INDEX IF NOT EXISTS idx_tienda_banners_emp ON tienda_banners (empresa_id, marca_id);\n        CREATE INDEX IF NOT EXISTS idx_tienda_documentos_prod ON tienda_documentos (producto_id);\n"
  ],
  [
   "    return {\"tienda\": _publica(t), \"marcas\": marcas, \"categorias\": categorias, \"productos\": productos}\n",
   "    for m in marcas:\n        m[\"productos\"] = sum(1 for p in productos if p.get(\"marca_id\") == m[\"id\"])\n    return {\"tienda\": _publica(t), \"marcas\": marcas, \"categorias\": categorias, \"productos\": productos,\n            \"banners\": _banners(t[\"empresa_id\"], None)}\n\n\ndef _banners(empresa_id, marca_id, solo_activos=True, todos=False):\n    \"\"\"Carrusel (promociones, videos, eventos): marca_id None = el de Inicio; todos=True = de todas (admin).\"\"\"\n    cond, params = [\"b.empresa_id = %s\"], [empresa_id]\n    if not todos:\n        if marca_id is None:\n            cond.append(\"b.marca_id IS NULL\")\n        else:\n            cond.append(\"b.marca_id = %s\"); params.append(marca_id)\n    if solo_activos:\n        cond.append(\"b.activo\")\n    return [_limpio(b) for b in _q(f\"\"\"SELECT b.id, b.marca_id, m.nombre AS marca, b.titulo, b.texto, b.etiqueta, b.foto_id, b.video_url,\n                                            b.producto_id, p.nombre AS producto, b.link, b.orden, b.activo\n                                     FROM tienda_banners b LEFT JOIN tienda_marcas m ON m.id = b.marca_id\n                                     LEFT JOIN tienda_productos p ON p.id = b.producto_id\n                                     WHERE {' AND '.join(cond)} ORDER BY b.marca_id NULLS FIRST, b.orden, b.id\"\"\", params)]\n\n\n@router.get(\"/api/tienda/{codigo}/marca/{marca_id}\")\ndef api_marca(codigo: str, marca_id: int):\n    \"\"\"Página de una marca/empresa: sus datos y su carrusel (los productos ya vienen en el catálogo).\"\"\"\n    t = tienda_por_codigo(codigo)\n    m = _q(\"SELECT id, nombre, descripcion, logo_foto_id FROM tienda_marcas WHERE id = %s AND empresa_id = %s AND activa\",\n           (marca_id, t[\"empresa_id\"]), uno=True)\n    if not m:\n        raise HTTPException(status_code=404, detail=\"Marca no encontrada\")\n    return {\"marca\": m, \"banners\": _banners(t[\"empresa_id\"], marca_id)}\n"
  ],
  [
   "    return r\n\n\nclass CaracteristicaIn(BaseModel):\n    nombre: str = Field(min_length=1, max_length=80)\n    valor: str = Field(min_length=1, max_length=300)\n",
   "    return r\n\n\nclass ImagenIn(BaseModel):\n    foto_base64: str = Field(min_length=100)\n\n\ndef _guardar_imagen(empresa_id, foto_base64):\n    datos, tipo = _bytes_b64(foto_base64, MAX_FOTO)\n    return _q(\"INSERT INTO tienda_fotos (empresa_id, producto_id, datos, tipo) VALUES (%s, NULL, %s, %s) RETURNING id\",\n              (empresa_id, psycopg2.Binary(datos), tipo), uno=True, commit=True)[\"id\"]\n\n\ndef _borrar_imagen(empresa_id, foto_id):\n    if foto_id:\n        _q(\"DELETE FROM tienda_fotos WHERE id = %s AND empresa_id = %s AND producto_id IS NULL\", (foto_id, empresa_id), todos=False, commit=True)\n\n\n@router.put(\"/api/tienda/admin/marcas/{marca_id}/logo\")\ndef api_logo_marca(marca_id: int, payload: ImagenIn, usuario: dict = Depends(requiere_admin_tienda)):\n    m = _q(\"SELECT logo_foto_id FROM tienda_marcas WHERE id = %s AND empresa_id = %s\", (marca_id, usuario[\"empresa_id\"]), uno=True)\n    if not m:\n        raise HTTPException(status_code=404, detail=\"Marca no encontrada\")\n    fid = _guardar_imagen(usuario[\"empresa_id\"], payload.foto_base64)\n    _q(\"UPDATE tienda_marcas SET logo_foto_id = %s WHERE id = %s\", (fid, marca_id), todos=False, commit=True)\n    _borrar_imagen(usuario[\"empresa_id\"], m[\"logo_foto_id\"])\n    return {\"logo_foto_id\": fid}\n\n\n@router.delete(\"/api/tienda/admin/marcas/{marca_id}/logo\")\ndef api_quitar_logo_marca(marca_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    m = _q(\"SELECT logo_foto_id FROM tienda_marcas WHERE id = %s AND empresa_id = %s\", (marca_id, usuario[\"empresa_id\"]), uno=True)\n    if m:\n        _q(\"UPDATE tienda_marcas SET logo_foto_id = NULL WHERE id = %s\", (marca_id,), todos=False, commit=True)\n        _borrar_imagen(usuario[\"empresa_id\"], m[\"logo_foto_id\"])\n    return {\"ok\": True}\n\n\nclass BannerIn(BaseModel):\n    marca_id: Optional[int] = None          # None = carrusel de Inicio\n    titulo: Optional[str] = Field(default=None, max_length=120)\n    texto: Optional[str] = Field(default=None, max_length=400)\n    etiqueta: Optional[str] = Field(default=None, max_length=30)   # PROMOCIÓN, EVENTO, NUEVO...\n    producto_id: Optional[int] = None\n    link: Optional[str] = Field(default=None, max_length=500)\n    activo: bool = True\n    foto_base64: Optional[str] = None       # para cambiar la imagen\n\n\ndef _validar_banner(empresa_id, payload):\n    if payload.marca_id is not None:\n        _validar_marca(empresa_id, payload.marca_id)\n    if payload.producto_id is not None:\n        _producto_de_empresa(empresa_id, payload.producto_id)\n    link = (payload.link or \"\").strip() or None\n    if link and not re.match(r\"^https?://\", link, re.I):\n        link = \"https://\" + link\n    return link\n\n\ndef _banner_de_empresa(empresa_id, banner_id):\n    b = _q(\"SELECT * FROM tienda_banners WHERE id = %s AND empresa_id = %s\", (banner_id, empresa_id), uno=True)\n    if not b:\n        raise HTTPException(status_code=404, detail=\"No se encontró esa promoción\")\n    return b\n\n\ndef _un_banner(empresa_id, banner_id):\n    return next((b for b in _banners(empresa_id, None, solo_activos=False, todos=True) if b[\"id\"] == banner_id), None)\n\n\n@router.get(\"/api/tienda/admin/banners\")\ndef api_banners_admin(usuario: dict = Depends(requiere_admin_tienda)):\n    return _banners(usuario[\"empresa_id\"], None, solo_activos=False, todos=True)\n\n\n@router.post(\"/api/tienda/admin/banners\")\ndef api_crear_banner(payload: BannerIn, usuario: dict = Depends(requiere_admin_tienda)):\n    link = _validar_banner(usuario[\"empresa_id\"], payload)\n    fid = _guardar_imagen(usuario[\"empresa_id\"], payload.foto_base64) if payload.foto_base64 else None\n    orden = (_q(\"SELECT COALESCE(MAX(orden), -1) + 1 AS o FROM tienda_banners WHERE empresa_id = %s AND marca_id IS NOT DISTINCT FROM %s\",\n                (usuario[\"empresa_id\"], payload.marca_id), uno=True) or {}).get(\"o\", 0)\n    r = _q(\"\"\"INSERT INTO tienda_banners (empresa_id, marca_id, titulo, texto, etiqueta, foto_id, producto_id, link, orden, activo)\n              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id\"\"\",\n           (usuario[\"empresa_id\"], payload.marca_id, payload.titulo, payload.texto, payload.etiqueta, fid, payload.producto_id, link,\n            orden, payload.activo), uno=True, commit=True)\n    return _un_banner(usuario[\"empresa_id\"], r[\"id\"])\n\n\n@router.put(\"/api/tienda/admin/banners/{banner_id}\")\ndef api_editar_banner(banner_id: int, payload: BannerIn, usuario: dict = Depends(requiere_admin_tienda)):\n    b = _banner_de_empresa(usuario[\"empresa_id\"], banner_id)\n    link = _validar_banner(usuario[\"empresa_id\"], payload)\n    fid = b[\"foto_id\"]\n    if payload.foto_base64:\n        fid = _guardar_imagen(usuario[\"empresa_id\"], payload.foto_base64)\n    _q(\"\"\"UPDATE tienda_banners SET marca_id = %s, titulo = %s, texto = %s, etiqueta = %s, foto_id = %s, producto_id = %s,\n                                     link = %s, activo = %s WHERE id = %s\"\"\",\n       (payload.marca_id, payload.titulo, payload.texto, payload.etiqueta, fid, payload.producto_id, link, payload.activo, banner_id),\n       todos=False, commit=True)\n    if fid != b[\"foto_id\"]:\n        _borrar_imagen(usuario[\"empresa_id\"], b[\"foto_id\"])\n    return _un_banner(usuario[\"empresa_id\"], banner_id)\n\n\n@router.post(\"/api/tienda/admin/banners/{banner_id}/video\")\ndef api_video_banner(banner_id: int, archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_tienda)):\n    b = _banner_de_empresa(usuario[\"empresa_id\"], banner_id)\n    if not r2.configurado():\n        raise HTTPException(status_code=400, detail=\"Falta configurar el almacenamiento de videos (R2) en el servidor.\")\n    key, url = r2.subir_video(usuario[\"empresa_id\"], archivo.filename or \"video.mp4\", archivo.file, archivo.content_type)\n    _q(\"UPDATE tienda_banners SET video_url = %s, r2_key = %s WHERE id = %s\", (url, key, banner_id), todos=False, commit=True)\n    if b.get(\"r2_key\"):\n        try:\n            r2.eliminar_video(b[\"r2_key\"])\n        except Exception:\n            pass\n    return _un_banner(usuario[\"empresa_id\"], banner_id)\n\n\n@router.delete(\"/api/tienda/admin/banners/{banner_id}/video\")\ndef api_quitar_video_banner(banner_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    b = _banner_de_empresa(usuario[\"empresa_id\"], banner_id)\n    _q(\"UPDATE tienda_banners SET video_url = NULL, r2_key = NULL WHERE id = %s\", (banner_id,), todos=False, commit=True)\n    if b.get(\"r2_key\"):\n        try:\n            r2.eliminar_video(b[\"r2_key\"])\n        except Exception:\n            pass\n    return _un_banner(usuario[\"empresa_id\"], banner_id)\n\n\n@router.delete(\"/api/tienda/admin/banners/{banner_id}\")\ndef api_borrar_banner(banner_id: int, usuario: dict = Depends(requiere_admin_tienda)):\n    b = _banner_de_empresa(usuario[\"empresa_id\"], banner_id)\n    _q(\"DELETE FROM tienda_banners WHERE id = %s\", (banner_id,), todos=False, commit=True)\n    _borrar_imagen(usuario[\"empresa_id\"], b[\"foto_id\"])\n    if b.get(\"r2_key\"):\n        try:\n            r2.eliminar_video(b[\"r2_key\"])\n        except Exception:\n            pass\n    return {\"ok\": True}\n\n\nclass OrdenBannersIn(BaseModel):\n    banners: List[int]\n\n\n@router.put(\"/api/tienda/admin/banners-orden\")\ndef api_orden_banners(payload: OrdenBannersIn, usuario: dict = Depends(requiere_admin_tienda)):\n    for i, bid in enumerate(payload.banners):\n        _q(\"UPDATE tienda_banners SET orden = %s WHERE id = %s AND empresa_id = %s\", (i, bid, usuario[\"empresa_id\"]), todos=False, commit=True)\n    return {\"ok\": True}\n\n\nclass CaracteristicaIn(BaseModel):\n    nombre: str = Field(min_length=1, max_length=80)\n    valor: str = Field(min_length=1, max_length=300)\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_unidental_marcas_carrusel.py")
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
