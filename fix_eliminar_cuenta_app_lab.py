# -*- coding: utf-8 -*-
"""
MARKINC LAB: ELIMINAR CUENTA DESDE LA APP (lo exige Apple, regla 5.1.1(v))
- Nuevo POST /api/laboratorio/mios/eliminar-cuenta (pide la contrasena):
  borra acceso, nombre, correo, telefono, token de avisos y comprobantes;
  libera la matricula; conserva trabajos, pagos y facturas sin contacto.
REQUIERE haber corrido antes fix_eliminar_cuenta_lab.py.
Toca: backend/app.py, backend/db.py
Se puede correr varias veces.  Correr con:  py -3 fix_eliminar_cuenta_app_lab.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    return nuevo_id\n\n\n# ---- Base de estudiantes (Administrar → Portal de estudiantes) ----\n\n_COLUMNAS_ESTUDIANTE = \"\"\"u.id, u.username AS matricula, u.nombre_completo, u.telefono_whatsapp AS telefono, u.email,\n",
   "    return nuevo_id\n\n\ndef eliminar_cuenta_estudiante_laboratorio(empresa_id, usuario_id):\n    \"\"\"El estudiante borra su propia cuenta desde la app (lo exigen Apple y\n    Google). Se borran su acceso y sus datos personales -- nombre, correo,\n    teléfono, token de notificaciones y las fotos de comprobantes que subió --\n    y se libera su matrícula. Se conservan los trabajos, pagos y facturas\n    (sin datos de contacto) porque la ley fiscal pide guardarlos 5 años.\n    Ver frontend/eliminar_cuenta.html.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    sello = ahora().strftime(\"%Y%m%d%H%M%S\")\n    cur.execute(\n        \"\"\"UPDATE users SET activo = FALSE, username = %s, password_hash = %s,\n                            nombre_completo = 'Estudiante (cuenta eliminada)', telefono_whatsapp = NULL,\n                            email = NULL, fcm_token = NULL\n           WHERE id = %s AND empresa_id = %s AND rol = 'estudiante'\"\"\",\n        (f\"eliminado-{usuario_id}-{sello}\", auth.hash_password(secrets.token_urlsafe(32)), usuario_id, empresa_id),\n    )\n    n = cur.rowcount\n    if n:\n        cur.execute(\"UPDATE laboratorio_pagos_reportados SET comprobante_base64 = '' WHERE reportado_por_id = %s\", (usuario_id,))\n    conn.commit()\n    cur.close(); conn.close()\n    return n > 0\n\n\n# ---- Base de estudiantes (Administrar → Portal de estudiantes) ----\n\n_COLUMNAS_ESTUDIANTE = \"\"\"u.id, u.username AS matricula, u.nombre_completo, u.telefono_whatsapp AS telefono, u.email,\n"
  ]
 ],
 "backend/app.py": [
  [
   "    return db.cuenta_estudiante_laboratorio(usuario[\"empresa_id\"], usuario[\"id\"])\n\n\nclass FcmTokenIn(BaseModel):\n    token: str = Field(min_length=10, max_length=4096)\n\n",
   "    return db.cuenta_estudiante_laboratorio(usuario[\"empresa_id\"], usuario[\"id\"])\n\n\nclass EliminarCuentaIn(BaseModel):\n    password: str = Field(min_length=1, max_length=200)\n\n\n@app.post(\"/api/laboratorio/mios/eliminar-cuenta\")\ndef api_eliminar_mi_cuenta_estudiante(payload: EliminarCuentaIn, usuario: dict = Depends(auth.get_current_user)):\n    \"\"\"El estudiante elimina su cuenta desde la app (Apple 5.1.1(v) y Google\n    Play). Pide su contraseña para confirmar. No se puede deshacer.\"\"\"\n    if usuario[\"rol\"] != \"estudiante\":\n        raise HTTPException(status_code=403, detail=\"Esta acción es solo para cuentas de estudiante\")\n    registro = db.obtener_usuario_por_username(usuario[\"username\"])\n    if not registro or not auth.verificar_password(payload.password, registro[\"password_hash\"]):\n        # 400 y no 401: la app trata cualquier 401 como \"sesión terminada\" y lo sacaría.\n        raise HTTPException(status_code=400, detail=\"La contraseña no es correcta\")\n    if not db.eliminar_cuenta_estudiante_laboratorio(usuario[\"empresa_id\"], usuario[\"id\"]):\n        raise HTTPException(status_code=404, detail=\"Cuenta no encontrada\")\n    return {\"ok\": True}\n\n\nclass FcmTokenIn(BaseModel):\n    token: str = Field(min_length=10, max_length=4096)\n\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_eliminar_cuenta_app_lab.py")
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
