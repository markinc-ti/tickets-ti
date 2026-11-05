# -*- coding: utf-8 -*-
"""Equipos por KIT (la PC con sus accesorios en la misma ficha y la misma responsiva), plantillas de kit,
lista de personas para asignar desde la app, y la carta responsiva con los accesorios incluidos.
Correr en la carpeta tickets-ti:  py -3 fix_equipos_kits_app.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\n# ==================== EQUIPOS (inventario) ====================\n\nclass NuevoEquipo(BaseModel):\n    tipo: str\n    nombre: str = Field(min_length=1, max_length=120)\n",
   "\n# ==================== EQUIPOS (inventario) ====================\n\nclass AccesorioEquipoIn(BaseModel):\n    nombre: str = Field(min_length=1, max_length=80)\n    marca: Optional[str] = Field(default=None, max_length=60)\n    modelo: Optional[str] = Field(default=None, max_length=60)\n    numero_serie: Optional[str] = Field(default=None, max_length=80)\n    cantidad: int = Field(default=1, ge=1, le=99)\n\n\ndef _accesorios_limpios(lista):\n    if lista is None:\n        return None\n    return [{k: (v.strip() if isinstance(v, str) else v) for k, v in a.model_dump().items() if v not in (None, \"\")}\n            for a in lista if a.nombre.strip()][:40]\n\n\n# Plantillas de kit: al dar de alta el equipo principal ya trae su lista de accesorios\n# (se puede quitar o agregar). Así todo el kit va en una sola ficha y una sola responsiva.\nKITS_EQUIPO = [\n    {\"clave\": \"pc\", \"nombre\": \"PC de escritorio\", \"tipo\": \"computadora\",\n     \"accesorios\": [\"Monitor\", \"Teclado\", \"Mouse\", \"Regulador / No-break\", \"Audífonos\", \"Cable de corriente\"]},\n    {\"clave\": \"laptop\", \"nombre\": \"Laptop\", \"tipo\": \"laptop\",\n     \"accesorios\": [\"Cargador\", \"Mouse\", \"Mochila / funda\", \"Audífonos\"]},\n    {\"clave\": \"impresora\", \"nombre\": \"Impresora\", \"tipo\": \"impresora\",\n     \"accesorios\": [\"Cable USB\", \"Cable de corriente\"]},\n    {\"clave\": \"telefono\", \"nombre\": \"Celular / teléfono\", \"tipo\": \"telefono\",\n     \"accesorios\": [\"Cargador\", \"Cable\", \"Funda\", \"Mica\"]},\n    {\"clave\": \"tablet\", \"nombre\": \"Tablet\", \"tipo\": \"tablet\",\n     \"accesorios\": [\"Cargador\", \"Funda\", \"Lápiz\"]},\n]\n\n\nclass NuevoEquipo(BaseModel):\n    tipo: str\n    nombre: str = Field(min_length=1, max_length=120)\n"
  ],
  [
   "    usuario_id: Optional[int] = None\n    usuario_microsip: Optional[str] = None\n    password_microsip: Optional[str] = None\n\n\nclass ActualizacionEquipo(BaseModel):\n",
   "    usuario_id: Optional[int] = None\n    usuario_microsip: Optional[str] = None\n    password_microsip: Optional[str] = None\n    accesorios: Optional[List[AccesorioEquipoIn]] = None\n\n\nclass ActualizacionEquipo(BaseModel):\n"
  ],
  [
   "    usuario_id: Optional[int] = None\n    usuario_microsip: Optional[str] = None\n    password_microsip: Optional[str] = None\n\n\nCAMPOS_EQUIPO_SOLO_ADMIN = [\"sucursal_id\", \"sucursal_nombre\", \"departamento\", \"usuario_id\", \"usuario_nombre\", \"usuario_microsip\", \"password_microsip\"]\n",
   "    usuario_id: Optional[int] = None\n    usuario_microsip: Optional[str] = None\n    password_microsip: Optional[str] = None\n    accesorios: Optional[List[AccesorioEquipoIn]] = None   # [] = quitarle todos los accesorios\n\n\nCAMPOS_EQUIPO_SOLO_ADMIN = [\"sucursal_id\", \"sucursal_nombre\", \"departamento\", \"usuario_id\", \"usuario_nombre\", \"usuario_microsip\", \"password_microsip\"]\n"
  ],
  [
   "    equipo = db.crear_equipo(usuario[\"empresa_id\"], payload.tipo, payload.nombre, payload.marca, payload.modelo,\n                              payload.numero_serie, payload.departamento, payload.responsable,\n                              payload.fecha_adquisicion, payload.notas, payload.sucursal_id,\n                              payload.usuario_id, payload.usuario_microsip, payload.password_microsip)\n    return _filtrar_equipo_por_rol(equipo, usuario[\"rol\"])\n\n\n@app.patch(\"/api/equipos/{equipo_id}\")\n",
   "    equipo = db.crear_equipo(usuario[\"empresa_id\"], payload.tipo, payload.nombre, payload.marca, payload.modelo,\n                              payload.numero_serie, payload.departamento, payload.responsable,\n                              payload.fecha_adquisicion, payload.notas, payload.sucursal_id,\n                              payload.usuario_id, payload.usuario_microsip, payload.password_microsip,\n                              _accesorios_limpios(payload.accesorios))\n    return _filtrar_equipo_por_rol(equipo, usuario[\"rol\"])\n\n\n@app.get(\"/api/equipos/kits\")\ndef api_kits_equipo(usuario: dict = Depends(requiere_acceso_equipos)):\n    \"\"\"Plantillas de kit (PC, laptop…) con sus accesorios, y los tipos de equipo.\"\"\"\n    return {\"kits\": KITS_EQUIPO, \"tipos\": db.TIPOS_EQUIPO, \"estados\": db.ESTADOS_EQUIPO}\n\n\n@app.get(\"/api/equipos/usuarios-asignables\")\ndef api_usuarios_asignables_equipo(usuario: dict = Depends(requiere_acceso_equipos)):\n    \"\"\"Personas activas de la empresa para asignarles un equipo (la app no usa /api/usuarios, que es de admin).\"\"\"\n    return [{\"id\": u[\"id\"], \"nombre\": u.get(\"nombre_completo\") or u.get(\"username\"),\n             \"departamento\": u.get(\"departamento\"), \"sucursal_id\": u.get(\"sucursal_id\")}\n            for u in db.listar_usuarios(usuario[\"empresa_id\"]) if u.get(\"activo\", True) and not u.get(\"fecha_baja\")]\n\n\n@app.patch(\"/api/equipos/{equipo_id}\")\n"
  ],
  [
   "    if payload.estado and payload.estado not in db.ESTADOS_EQUIPO:\n        raise HTTPException(status_code=400, detail=\"Estado de equipo inválido\")\n    datos = payload.dict(exclude_unset=True)\n    if usuario[\"rol\"] != \"admin\":\n        for campo in (\"sucursal_id\", \"departamento\", \"usuario_id\", \"usuario_microsip\", \"password_microsip\"):\n            datos.pop(campo, None)\n",
   "    if payload.estado and payload.estado not in db.ESTADOS_EQUIPO:\n        raise HTTPException(status_code=400, detail=\"Estado de equipo inválido\")\n    datos = payload.dict(exclude_unset=True)\n    if \"accesorios\" in datos:\n        datos[\"accesorios\"] = _accesorios_limpios(payload.accesorios) or []\n    if usuario[\"rol\"] != \"admin\":\n        for campo in (\"sucursal_id\", \"departamento\", \"usuario_id\", \"usuario_microsip\", \"password_microsip\"):\n            datos.pop(campo, None)\n"
  ]
 ],
 "backend/db.py": [
  [
   "        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS firma_responsiva_en TEXT;\n        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS telefonos TEXT;\n",
   "        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS firma_responsiva_en TEXT;\n        -- Kit: accesorios que van con el equipo (teclado, mouse, regulador…) en la misma ficha y responsiva.\n        ALTER TABLE equipos ADD COLUMN IF NOT EXISTS accesorios JSONB;\n        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS telefonos TEXT;\n"
  ],
  [
   "                  usuario_id=None, usuario_microsip=None, password_microsip=None):\n",
   "                  usuario_id=None, usuario_microsip=None, password_microsip=None, accesorios=None):\n"
  ],
  [
   "            creado_en, actualizado_en)\n           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'activo', %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id\"\"\",\n",
   "            accesorios, creado_en, actualizado_en)\n           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'activo', %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id\"\"\",\n"
  ],
  [
   "         fecha_adquisicion, notas, sucursal_id, usuario_id, usuario_microsip, password_microsip, now, now),\n",
   "         fecha_adquisicion, notas, sucursal_id, usuario_id, usuario_microsip, password_microsip,\n         psycopg2.extras.Json(accesorios) if accesorios else None, now, now),\n"
  ],
  [
   "                  \"usuario_id\", \"usuario_microsip\", \"password_microsip\"]\n",
   "                  \"usuario_id\", \"usuario_microsip\", \"password_microsip\", \"accesorios\"]\n    if \"accesorios\" in campos_nuevos and campos_nuevos[\"accesorios\"] is not None:\n        campos_nuevos = dict(campos_nuevos, accesorios=psycopg2.extras.Json(campos_nuevos[\"accesorios\"]))\n"
  ]
 ],
 "backend/pdfs_equipos.py": [
  [
   "    ]\n    if equipo.get(\"notas\"):\n",
   "    ]\n    accesorios = equipo.get(\"accesorios\") or []\n    if isinstance(accesorios, str):\n        try:\n            import json as _json\n            accesorios = _json.loads(accesorios) or []\n        except Exception:\n            accesorios = []\n    if accesorios:\n        # Kit: todo lo que se entrega con el equipo, en la misma carta.\n        lineas = []\n        for a in accesorios:\n            detalle = \" / \".join(x for x in [a.get(\"marca\"), a.get(\"modelo\")] if x)\n            texto = f\"{int(a.get('cantidad') or 1)} × {a.get('nombre', '')}\"\n            if detalle:\n                texto += f\" — {detalle}\"\n            if a.get(\"numero_serie\"):\n                texto += f\" (S/N {a['numero_serie']})\"\n            lineas.append(texto)\n        filas_tabla.append([celda_h(\"Accesorios incluidos:\"), Table([[celda(\"<br/>\".join(lineas))]], colWidths=[10.5*cm],\n                                                                      style=TableStyle([(\"SPAN\", (0,0), (-1,-1))]))])\n    if equipo.get(\"notas\"):\n"
  ],
  [
   "        filas_tabla.append([celda_h(\"Notas / accesorios:\"), Table([[celda(equipo[\"notas\"])]], colWidths=[10.5*cm],\n",
   "        filas_tabla.append([celda_h(\"Notas:\" if accesorios else \"Notas / accesorios:\"), Table([[celda(equipo[\"notas\"])]], colWidths=[10.5*cm],\n"
  ],
  [
   "    ] + ([(\"SPAN\", (1,3), (3,3))] if equipo.get(\"notas\") else [])))\n",
   "    ] + [(\"SPAN\", (1, i), (3, i)) for i in range(3, len(filas_tabla))]))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_equipos_kits_app.py")
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
