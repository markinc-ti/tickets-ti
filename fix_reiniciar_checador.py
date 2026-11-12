# -*- coding: utf-8 -*-
"""
tickets-ti: reiniciar un checador ZKTeco desde la app (RH → Checadores → Reiniciar).

- GET  /api/rh/checadores/estado         → checadores con en línea / última conexión / estado del reinicio
- POST /api/rh/checadores/{sn}/reiniciar → manda REBOOT por ADMS (le llega en su siguiente conexión)

Uso (en la carpeta tickets-ti):  py -3 fix_reiniciar_checador.py
Se puede correr varias veces (si ya está aplicado no cambia nada).
"""
import io
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return {\"ok\": True, \"nave\": ((nave or {}).get(\"cambios\") or [None])[0]}\n\n\nclass PedirChecadorIn(BaseModel):\n    que: str = Field(pattern=\"^(personas|fotos|todo)$\")\n\n",
   "    return {\"ok\": True, \"nave\": ((nave or {}).get(\"cambios\") or [None])[0]}\n\n\ndef _fecha_chk(v):\n    from datetime import datetime as _dt\n    try:\n        return _dt.fromisoformat(str(v)).replace(tzinfo=None) if v else None\n    except ValueError:\n        return None\n\n\ndef _estado_checadores(empresa_id):\n    \"\"\"Checadores activos de la empresa con su última conexión y su último reinicio pedido desde la app.\"\"\"\n    ahora = db.ahora().replace(tzinfo=None)\n    reinicios = db.reinicios_checadores(empresa_id)\n    filas = []\n    for k in db.listar_checadores_adms(empresa_id):\n        if k.get(\"empresa_id\") != empresa_id:\n            continue\n        ult = _fecha_chk(k.get(\"ultima_conexion\"))\n        hace = (ahora - ult).total_seconds() if ult else None\n        r = reinicios.get(k[\"sn\"])\n        reinicio = None\n        if r:\n            enviado = _fecha_chk(r.get(\"enviado_en\"))\n            if not enviado:\n                paso = \"pendiente\"\n            elif ult and (ult - enviado).total_seconds() > 20 and hace is not None and hace < 300:\n                paso = \"volvio\"     # se reinició y ya se volvió a conectar\n            else:\n                paso = \"enviado\"    # ya lo recibió; está reiniciando\n            reinicio = {\"estado\": paso, \"pedido_en\": r.get(\"creado_en\"), \"enviado_en\": r.get(\"enviado_en\"),\n                        \"resultado\": r.get(\"resultado\")}\n        filas.append({\"sn\": k[\"sn\"], \"nombre\": k.get(\"nombre\"), \"sucursal\": k.get(\"sucursal\"), \"activo\": k.get(\"activo\"),\n                      \"ultima_conexion\": k.get(\"ultima_conexion\"), \"ultima_checada\": k.get(\"ultima_checada\"),\n                      \"segundos_sin_conexion\": int(hace) if hace is not None else None,\n                      \"en_linea\": hace is not None and hace < 300, \"reinicio\": reinicio})\n    return filas\n\n\n@app.get(\"/api/rh/checadores/estado\")\ndef api_estado_checadores(usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Para el botón Reiniciar de la app: cada checador, si está en línea y cómo va su reinicio.\"\"\"\n    return {\"checadores\": _estado_checadores(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/rh/checadores/{sn}/reiniciar\")\ndef api_reiniciar_checador(sn: str, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Manda REBOOT al checador (le llega en su siguiente conexión, segundos si está en línea).\n    Tarda 1-2 min en apagarse, prender y volver a conectarse; mientras, no se puede checar.\"\"\"\n    chk = db.checador_adms((sn or \"\").strip().upper())\n    if not chk or chk.get(\"empresa_id\") != usuario[\"empresa_id\"]:\n        raise HTTPException(status_code=404, detail=\"Checador no encontrado\")\n    previo = db.reinicios_checadores(usuario[\"empresa_id\"]).get(chk[\"sn\"])\n    if previo and not previo.get(\"enviado_en\"):\n        return {\"ok\": True, \"ya_pedido\": True, \"mensaje\": \"Ya estaba pedido; le llega en cuanto se conecte.\"}\n    db.encolar_comando_checador(chk[\"sn\"], \"REBOOT\")\n    return {\"ok\": True, \"ya_pedido\": False, \"mensaje\": \"Listo: el checador se reinicia en cuanto reciba la orden.\"}\n\n\nclass PedirChecadorIn(BaseModel):\n    que: str = Field(pattern=\"^(personas|fotos|todo)$\")\n\n"
  ]
 ],
 "backend/db.py": [
  [
   "    conn.commit()\n    cur.close(); conn.close()\n    return r\n\n\ndef resumen_comandos_checadores(empresa_id):\n    \"\"\"{sn: {pendientes, enviados, ok, error, ultimo_error}} de los checadores de la empresa (últimos 7 días).\"\"\"\n    limite = (ahora() - timedelta(days=7)).isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    conn.commit()\n    cur.close(); conn.close()\n    return r\n\n\ndef reinicios_checadores(empresa_id):\n    \"\"\"{sn: {id, creado_en, enviado_en, resultado}}: el último REBOOT pedido a cada checador de la empresa.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT DISTINCT ON (c.sn) c.sn, c.id, c.creado_en, c.enviado_en, c.resultado FROM rh_checador_comandos c\n                   JOIN rh_checadores k ON k.sn = c.sn WHERE k.empresa_id = %s AND c.comando = 'REBOOT'\n                   ORDER BY c.sn, c.id DESC\"\"\", (empresa_id,))\n    r = {x[\"sn\"]: dict(x) for x in cur.fetchall()}\n    cur.close(); conn.close()\n    return r\n\n\ndef resumen_comandos_checadores(empresa_id):\n    \"\"\"{sn: {pendientes, enviados, ok, error, ultimo_error}} de los checadores de la empresa (últimos 7 días).\"\"\"\n    limite = (ahora() - timedelta(days=7)).isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_reiniciar_checador.py")
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
