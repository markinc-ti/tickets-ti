# -*- coding: utf-8 -*-
"""
CONCURSOS: MODULO POR EMPRESA (QUITARLO A PEYMAR)
Nuevo modulo "Concursos" en Superadmin -> Empresas -> Modulos. Al publicar
queda prendido solo en Mark Inc y APAGADO en Peymar (y las demas): ya no sale
el boton Concursos en el menu, no pueden crear concursos ni votar.
Se puede prender/apagar despues desde Superadmin.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_concursos_modulo_empresa.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "        -- dentales. Apagado por default en todas las empresas; solo quien tenga\n        -- acceso_soporte (el área de soporte) lo ve.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS modulo_soporte BOOLEAN NOT NULL DEFAULT FALSE;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_soporte BOOLEAN NOT NULL DEFAULT FALSE;\n        CREATE TABLE IF NOT EXISTS soporte_reportes (\n            id SERIAL PRIMARY KEY,\n",
   "        -- dentales. Apagado por default en todas las empresas; solo quien tenga\n        -- acceso_soporte (el área de soporte) lo ve.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS modulo_soporte BOOLEAN NOT NULL DEFAULT FALSE;\n        -- Concursos internos (ofrendas): módulo por empresa. Al crearse la columna\n        -- queda prendido solo en Mark·Inc; las demás (ej. Peymar) apagado.\n        DO $$ BEGIN\n            IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n                           WHERE table_name = 'empresas' AND column_name = 'modulo_concursos') THEN\n                ALTER TABLE empresas ADD COLUMN modulo_concursos BOOLEAN NOT NULL DEFAULT FALSE;\n                UPDATE empresas SET modulo_concursos = TRUE WHERE id = 1 OR nombre ILIKE '%%mark%%';\n            END IF;\n        END $$;\n        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_soporte BOOLEAN NOT NULL DEFAULT FALSE;\n        CREATE TABLE IF NOT EXISTS soporte_reportes (\n            id SERIAL PRIMARY KEY,\n"
  ],
  [
   "    \"modulo_shopify\": \"acceso_shopify\",\n    \"modulo_turnos\": \"acceso_turnos\",\n    \"modulo_soporte\": \"acceso_soporte\",\n}\n\n\n",
   "    \"modulo_shopify\": \"acceso_shopify\",\n    \"modulo_turnos\": \"acceso_turnos\",\n    \"modulo_soporte\": \"acceso_soporte\",\n    \"modulo_concursos\": \"acceso_concursos\",\n}\n\n\n"
  ]
 ],
 "backend/app.py": [
  [
   "    modulo_shopify: Optional[bool] = None\n    modulo_turnos: Optional[bool] = None\n    modulo_soporte: Optional[bool] = None\n\n\nclass NuevoLogo(BaseModel):\n",
   "    modulo_shopify: Optional[bool] = None\n    modulo_turnos: Optional[bool] = None\n    modulo_soporte: Optional[bool] = None\n    modulo_concursos: Optional[bool] = None\n\n\nclass NuevoLogo(BaseModel):\n"
  ],
  [
   "        \"empresa_nombre\": empresa[\"nombre\"] if empresa else \"\",\n        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        # Concurso interno activo (ej. ofrendas): el menú muestra el botón para ir a votar.\n        \"concurso_activo\": next(({\"id\": c[\"id\"], \"nombre\": c[\"nombre\"]} for c in db.listar_concursos(usuario[\"empresa_id\"])\n                                 if c[\"activo\"] and (c[\"abierto\"] or usuario[\"rol\"] == \"admin\")), None) if usuario.get(\"empresa_id\") else None,\n        \"app_movil\": db.app_movil_empresa(usuario[\"empresa_id\"]) if usuario.get(\"empresa_id\") else None,\n        \"apariencia\": {\n            \"tema\": (empresa.get(\"tema\") if empresa else None) or \"oscuro\",\n",
   "        \"empresa_nombre\": empresa[\"nombre\"] if empresa else \"\",\n        \"empresa_logo\": empresa[\"logo_base64\"] if empresa else None,\n        # Concurso interno activo (ej. ofrendas): el menú muestra el botón para ir a votar.\n        \"modulo_concursos\": _concursos_habilitados(usuario.get(\"empresa_id\")),\n        \"concurso_activo\": next(({\"id\": c[\"id\"], \"nombre\": c[\"nombre\"]} for c in db.listar_concursos(usuario[\"empresa_id\"])\n                                 if c[\"activo\"] and (c[\"abierto\"] or usuario[\"rol\"] == \"admin\")), None) if _concursos_habilitados(usuario.get(\"empresa_id\")) else None,\n        \"app_movil\": db.app_movil_empresa(usuario[\"empresa_id\"]) if usuario.get(\"empresa_id\") else None,\n        \"apariencia\": {\n            \"tema\": (empresa.get(\"tema\") if empresa else None) or \"oscuro\",\n"
  ],
  [
   "    ofrenda_id: int\n\n\ndef _concurso_de_mi_empresa(concurso_id, usuario):\n    c = db.obtener_concurso(concurso_id)\n    if not c or c[\"empresa_id\"] != usuario.get(\"empresa_id\"):\n        raise HTTPException(status_code=404, detail=\"Concurso no encontrado\")\n",
   "    ofrenda_id: int\n\n\ndef _concursos_habilitados(empresa_id):\n    \"\"\"Módulo de Concursos de la empresa (Superadmin → Empresas → Módulos).\"\"\"\n    if not empresa_id:\n        return False\n    return db.obtener_modulos_empresa(empresa_id).get(\"acceso_concursos\") is not False\n\n\ndef _concurso_de_mi_empresa(concurso_id, usuario):\n    if not _concursos_habilitados(usuario.get(\"empresa_id\")):\n        raise HTTPException(status_code=403, detail=\"Tu empresa no tiene el módulo de Concursos\")\n    c = db.obtener_concurso(concurso_id)\n    if not c or c[\"empresa_id\"] != usuario.get(\"empresa_id\"):\n        raise HTTPException(status_code=404, detail=\"Concurso no encontrado\")\n"
  ],
  [
   "@app.get(\"/api/concursos/mios\")\ndef api_mis_concursos(usuario: dict = Depends(requiere_empresa)):\n    \"\"\"Concursos de mi empresa (para entrar sin liga).\"\"\"\n    return [c for c in db.listar_concursos(usuario[\"empresa_id\"]) if c[\"activo\"] or usuario[\"rol\"] == \"admin\"]\n\n\n",
   "@app.get(\"/api/concursos/mios\")\ndef api_mis_concursos(usuario: dict = Depends(requiere_empresa)):\n    \"\"\"Concursos de mi empresa (para entrar sin liga).\"\"\"\n    if not _concursos_habilitados(usuario.get(\"empresa_id\")):\n        return []\n    return [c for c in db.listar_concursos(usuario[\"empresa_id\"]) if c[\"activo\"] or usuario[\"rol\"] == \"admin\"]\n\n\n"
  ],
  [
   "    c = db.obtener_concurso(concurso_id)\n    if not c:\n        raise HTTPException(status_code=404, detail=\"Concurso no encontrado\")\n    misma = c[\"empresa_id\"] == usuario.get(\"empresa_id\")\n    est = db.estado_votante_concurso(concurso_id, usuario[\"id\"]) if misma else {\"mi_ofrenda_id\": None, \"mi_voto_ofrenda_id\": None, \"es_juez\": False}\n    puede, motivo = True, None\n    if not misma:\n",
   "    c = db.obtener_concurso(concurso_id)\n    if not c:\n        raise HTTPException(status_code=404, detail=\"Concurso no encontrado\")\n    misma = c[\"empresa_id\"] == usuario.get(\"empresa_id\") and _concursos_habilitados(usuario.get(\"empresa_id\"))\n    est = db.estado_votante_concurso(concurso_id, usuario[\"id\"]) if misma else {\"mi_ofrenda_id\": None, \"mi_voto_ofrenda_id\": None, \"es_juez\": False}\n    puede, motivo = True, None\n    if not misma:\n"
  ],
  [
   "\n@app.post(\"/api/concursos\")\ndef api_crear_concurso(payload: ConcursoIn, usuario: dict = Depends(requiere_admin)):\n    return {\"id\": db.guardar_concurso(usuario[\"empresa_id\"], payload.model_dump(), quien_id=usuario[\"id\"])}\n\n\n",
   "\n@app.post(\"/api/concursos\")\ndef api_crear_concurso(payload: ConcursoIn, usuario: dict = Depends(requiere_admin)):\n    if not _concursos_habilitados(usuario.get(\"empresa_id\")):\n        raise HTTPException(status_code=403, detail=\"Tu empresa no tiene el módulo de Concursos\")\n    return {\"id\": db.guardar_concurso(usuario[\"empresa_id\"], payload.model_dump(), quien_id=usuario[\"id\"])}\n\n\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  document.getElementById('btnTickets').style.display = META.mis_permisos.acceso_tickets ? 'flex' : 'none';\n  document.getElementById('btnDashboard').style.display = (SESION.usuario.rol === 'admin' && META.mis_permisos.acceso_dashboard) ? 'flex' : 'none';\n  // Concurso interno activo (ofrendas…): todos lo ven para ir a votar; el admin además lo administra.\n  document.getElementById('btnConcurso').style.display = (META.concurso_activo || SESION.usuario.rol === 'admin') ? 'flex' : 'none';\n  document.getElementById('btnConcursoTxt').textContent = META.concurso_activo ? META.concurso_activo.nombre : 'Concursos';\n  document.getElementById('btnUsuarios').style.display = META.mis_permisos.acceso_administracion ? 'flex' : 'none';\n  document.getElementById('btnEquipos').style.display = (SESION.usuario.rol !== 'usuario' && META.mis_permisos.acceso_equipos) ? 'flex' : 'none';\n",
   "  document.getElementById('btnTickets').style.display = META.mis_permisos.acceso_tickets ? 'flex' : 'none';\n  document.getElementById('btnDashboard').style.display = (SESION.usuario.rol === 'admin' && META.mis_permisos.acceso_dashboard) ? 'flex' : 'none';\n  // Concurso interno activo (ofrendas…): todos lo ven para ir a votar; el admin además lo administra.\n  document.getElementById('btnConcurso').style.display = (META.modulo_concursos !== false && (META.concurso_activo || SESION.usuario.rol === 'admin')) ? 'flex' : 'none';\n  document.getElementById('btnConcursoTxt').textContent = META.concurso_activo ? META.concurso_activo.nombre : 'Concursos';\n  document.getElementById('btnUsuarios').style.display = META.mis_permisos.acceso_administracion ? 'flex' : 'none';\n  document.getElementById('btnEquipos').style.display = (SESION.usuario.rol !== 'usuario' && META.mis_permisos.acceso_equipos) ? 'flex' : 'none';\n"
  ],
  [
   "  { clave: 'modulo_shopify', etiqueta: '🛍️ Shopify' },\n  { clave: 'modulo_turnos', etiqueta: '🎫 Turnos por sucursal' },\n  { clave: 'modulo_soporte', etiqueta: '🛠️ Soporte técnico (mantenimiento y garantías de unidades dentales)' },\n];\n\nfunction renderEmpresas(empresas) {\n",
   "  { clave: 'modulo_shopify', etiqueta: '🛍️ Shopify' },\n  { clave: 'modulo_turnos', etiqueta: '🎫 Turnos por sucursal' },\n  { clave: 'modulo_soporte', etiqueta: '🛠️ Soporte técnico (mantenimiento y garantías de unidades dentales)' },\n  { clave: 'modulo_concursos', etiqueta: '🏆 Concursos (ej. ofrendas de Día de Muertos)' },\n];\n\nfunction renderEmpresas(empresas) {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_concursos_modulo_empresa.py")
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
