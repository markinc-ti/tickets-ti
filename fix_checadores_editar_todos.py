# -*- coding: utf-8 -*-
"""Checadores desde la app (Mark·Inc y Peymar): editar nombre/foto de una persona en los checadores
y darla de alta en TODOS los checadores donde le falta (copia huella/cara o su foto).
Correr en la carpeta tickets-ti:  py -3 fix_checadores_editar_todos.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return {\"ok\": True, \"altas\": hechos}\n\n\n@app.post(\"/api/rh/checadores/gente/{gente_id}/baja\")\ndef api_baja_gente_checador(gente_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"La borra de ese checador (deja de poder checar ahí). Su historial de checadas se conserva.\"\"\"\n",
   "    return {\"ok\": True, \"altas\": hechos}\n\n\ndef _comandos_foto_checador(sn, pin, foto):\n    \"\"\"Manda la foto de la cara al checador: él saca la cara de la foto y la persona ya puede checar.\"\"\"\n    foto = foto if foto.startswith(\"data:\") else \"data:image/jpeg;base64,\" + foto\n    b64 = foto.split(\",\", 1)[1]\n    tam = len(base64.b64decode(b64))\n    db.encolar_comando_checador(sn, f\"DATA UPDATE BIOPHOTO PIN={pin}\\tType=9\\tSize={tam}\\tContent={b64}\")\n    db.encolar_comando_checador(sn, f\"DATA UPDATE USERPIC PIN={pin}\\tSize={tam}\\tContent={b64}\")\n    return foto\n\n\nclass EditarGenteChecadorIn(BaseModel):\n    nombre: Optional[str] = Field(default=None, max_length=120)\n    foto_base64: Optional[str] = None\n    todos: bool = True   # si está ligada: aplicar en todos los checadores donde está\n\n\n@app.post(\"/api/rh/checadores/gente/{gente_id}/editar\")\ndef api_editar_gente_checador(gente_id: int, payload: EditarGenteChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Cambia el nombre y/o la foto de la cara de la persona en el checador (o en todos donde está, si está ligada).\"\"\"\n    nombre = _limpio(payload.nombre)\n    foto = (payload.foto_base64 or \"\").strip() or None\n    if not nombre and not foto:\n        raise HTTPException(status_code=400, detail=\"No hay cambios: escribe el nombre o toma una foto nueva.\")\n    if foto and len(foto) > 3_000_000:\n        raise HTTPException(status_code=400, detail=\"La foto pesa demasiado.\")\n    g = db.obtener_gente_checador(usuario[\"empresa_id\"], gente_id)\n    if not g:\n        raise HTTPException(status_code=404, detail=\"No encontrada\")\n    checadores, gente, _ = db.datos_red_checadores(usuario[\"empresa_id\"])\n    activas = [x for x in gente if not x.get(\"baja_en\")]\n    if payload.todos and g.get(\"usuario_id\"):\n        filas = [x for x in activas if x.get(\"usuario_id\") == g[\"usuario_id\"]]\n    else:\n        filas = [x for x in activas if x[\"id\"] == gente_id]\n    if not filas:\n        raise HTTPException(status_code=400, detail=\"Esta persona ya está dada de baja de ese checador.\")\n    nombres_chk = {k[\"sn\"]: (k.get(\"nombre\") or k[\"sn\"]) for k in checadores}\n    for x in filas:\n        if nombre:\n            db.encolar_comando_checador(x[\"sn\"], asistencia.comando_alta_usuario(x.get(\"datos_usuario\"), x[\"codigo\"], nombre))\n        if foto:\n            foto = _comandos_foto_checador(x[\"sn\"], x[\"codigo\"], foto)\n    db.editar_gente_checador(usuario[\"empresa_id\"], [x[\"id\"] for x in filas], nombre, foto)\n    return {\"ok\": True, \"checadores\": [nombres_chk.get(x[\"sn\"], x[\"sn\"]) for x in filas]}\n\n\nclass PersonaTodosChecadoresIn(BaseModel):\n    checadores: list[str] = Field(default_factory=list)   # vacío = todos los activos\n\n\n@app.post(\"/api/rh/checadores/persona/{usuario_id}/todos\")\ndef api_persona_todos_checadores(usuario_id: int, payload: PersonaTodosChecadoresIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Da de alta a la persona en todos los checadores donde todavía no está (o en los elegidos), con su\n    No. de empleado. Copia sus huellas/caras si ya las tenemos leídas de otro checador; si no, manda la foto\n    que se le tomó con la app; si tampoco hay foto, queda con nombre y número para registrarse en el aparato.\"\"\"\n    empresa_id = usuario[\"empresa_id\"]\n    persona = next((u for u in db.usuarios_ligables_checador(empresa_id) if u[\"id\"] == usuario_id), None)\n    if not persona:\n        raise HTTPException(status_code=404, detail=\"Usuario no encontrado o inactivo\")\n    pin = asistencia.normalizar_codigo(persona.get(\"numero_empleado\"))\n    if not pin.isdigit():\n        raise HTTPException(status_code=400, detail=\"Esta persona no tiene No. de empleado de Microsip (solo números). Captúralo primero: ese es su número en el checador.\")\n    checadores, gente, plantillas = db.datos_red_checadores(empresa_id)\n    destinos = [k for k in checadores if not payload.checadores or k[\"sn\"] in payload.checadores]\n    if not destinos:\n        raise HTTPException(status_code=400, detail=\"No hay checadores conectados.\")\n    suyas = [g for g in gente if g.get(\"usuario_id\") == usuario_id and not g.get(\"baja_en\")]\n    presentes = {g[\"sn\"] for g in suyas}\n    # De dónde copiar: el checador donde tenemos más huellas/caras leídas de esta persona.\n    fuente = max(suyas, key=lambda g: (len(plantillas.get((g[\"sn\"], g[\"codigo\"]), [])), bool(g.get(\"datos_usuario\"))), default=None)\n    pls = plantillas.get((fuente[\"sn\"], fuente[\"codigo\"]), []) if fuente else []\n    foto = None\n    if not pls:\n        for g in suyas:\n            foto = db.foto_gente_checador(empresa_id, g[\"id\"])\n            if foto:\n                break\n    nombre = (fuente or {}).get(\"nombre\") or persona[\"nombre\"]\n    altas, avisos = [], []\n    for k in destinos:\n        nom_chk = k.get(\"nombre\") or k[\"sn\"]\n        if k[\"sn\"] in presentes:\n            continue\n        en_ese = [g for g in gente if g[\"sn\"] == k[\"sn\"] and g[\"codigo\"] == pin]\n        otro = next((g for g in en_ese if g.get(\"usuario_id\") not in (None, usuario_id)), None)\n        if otro:\n            avisos.append(f\"{nom_chk}: el No. {pin} ya lo tiene {otro.get('usuario_nombre') or otro.get('nombre') or 'otra persona'}\"\n                          f\"{' (dado de baja; no se reutiliza para no mezclar checadas)' if otro.get('baja_en') else ''}.\")\n            continue\n        sin_ligar = next((g for g in en_ese if not g.get(\"usuario_id\") and not g.get(\"baja_en\")), None)\n        if sin_ligar:\n            avisos.append(f\"{nom_chk}: el No. {pin} ya existe ahí sin ligar ({sin_ligar.get('nombre_checador') or 'sin nombre'}). \"\n                          \"Lígalo a esta persona desde la web o quítalo primero.\")\n            continue\n        db.encolar_comando_checador(k[\"sn\"], asistencia.comando_alta_usuario((fuente or {}).get(\"datos_usuario\"), pin, nombre))\n        if pls:\n            for t in pls:\n                db.encolar_comando_checador(k[\"sn\"], asistencia.comando_plantilla(t[\"tabla\"], t[\"linea\"], pin))\n            db.alta_gente_sin_foto(empresa_id, k[\"sn\"], pin, usuario_id, nombre, usuario[\"id\"])\n            como = \"con su huella/cara\"\n        elif foto:\n            _comandos_foto_checador(k[\"sn\"], pin, foto)\n            db.alta_gente_desde_app(empresa_id, k[\"sn\"], pin, usuario_id, nombre, foto, usuario[\"id\"])\n            como = \"con su foto\"\n        else:\n            db.alta_gente_sin_foto(empresa_id, k[\"sn\"], pin, usuario_id, nombre, usuario[\"id\"])\n            como = \"solo nombre y número (registrar cara o huella en el checador)\"\n        altas.append({\"checador\": nom_chk, \"numero\": pin, \"como\": como})\n    ya = [k.get(\"nombre\") or k[\"sn\"] for k in destinos if k[\"sn\"] in presentes]\n    return {\"ok\": True, \"altas\": altas, \"avisos\": avisos, \"ya_estaba\": ya}\n\n\n@app.post(\"/api/rh/checadores/gente/{gente_id}/baja\")\ndef api_baja_gente_checador(gente_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"La borra de ese checador (deja de poder checar ahí). Su historial de checadas se conserva.\"\"\"\n"
  ]
 ],
 "backend/db.py": [
  [
   "    return dict(r) if r else None\n\n\ndef gente_de_usuario(empresa_id, usuario_id):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return dict(r) if r else None\n\n\ndef editar_gente_checador(empresa_id, gente_ids, nombre=None, foto=None):\n    \"\"\"RH corrige el nombre y/o la foto de una persona en uno o varios checadores (lo que se manda al aparato\n    lo encola app.py). None = no se toca.\"\"\"\n    if not gente_ids:\n        return 0\n    ts = ahora().isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"UPDATE rh_checador_gente SET nombre = COALESCE(%s, nombre),\n                     foto = COALESCE(%s, foto),\n                     foto_en = CASE WHEN %s IS NULL THEN foto_en ELSE %s END,\n                     foto_origen = CASE WHEN %s IS NULL THEN foto_origen ELSE 'app' END,\n                     actualizado_en = %s\n                   WHERE empresa_id = %s AND id = ANY(%s) AND baja_en IS NULL\"\"\",\n                (nombre, foto, foto, ts, foto, ts, empresa_id, list(gente_ids)))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef gente_de_usuario(empresa_id, usuario_id):\n    conn = get_connection()\n    cur = conn.cursor()\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checadores_editar_todos.py")
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
