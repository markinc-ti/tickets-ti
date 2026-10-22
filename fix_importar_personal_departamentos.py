# -*- coding: utf-8 -*-
"""
IMPORTAR PERSONAL: ARREGLO DEL ERROR 500 AL CONFIRMAR
- Si la empresa ya tenia un departamento con el mismo nombre pero DESACTIVADO,
  al importar se intentaba crear otra vez y truena (500). Ahora se reactiva.
REQUIERE haber corrido antes fix_rh_personal_a_checadores.py.
Toca: backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_importar_personal_departamentos.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "        checadores, gente, _ = db.datos_red_checadores(empresa_id)\n        nombres_chk = {k[\"sn\"]: k.get(\"nombre\") or k[\"sn\"] for k in checadores}\n        gente_act = [{**g, \"checador\": nombres_chk[g[\"sn\"]]} for g in gente if not g.get(\"baja_en\") and g[\"sn\"] in nombres_chk]\n        return importar_personal.planear(filas, db.listar_personal_rh(empresa_id, incluir_bajas=True), gente_act,\n                                         db.siguiente_numero_empleado(empresa_id),\n                                         [d[\"nombre\"] for d in db.listar_departamentos(empresa_id)])\n\n    plan = armar()\n    plan.update({\"hoja\": hoja, \"hojas\": hojas, \"columnas\": columnas})\n    if not payload.aplicar:\n        return plan\n    for d in plan[\"departamentos_nuevos\"]:\n        db.crear_departamento(empresa_id, d)\n    # Todos entran sin usuario de app (acceso_app = FALSE): una sola contraseña al azar\n    # que nadie conoce, para no tardar ~0.3 s por persona calculándola.\n    hash_sin_acceso = auth.hash_password(secrets.token_urlsafe(32))\n",
   "        checadores, gente, _ = db.datos_red_checadores(empresa_id)\n        nombres_chk = {k[\"sn\"]: k.get(\"nombre\") or k[\"sn\"] for k in checadores}\n        gente_act = [{**g, \"checador\": nombres_chk[g[\"sn\"]]} for g in gente if not g.get(\"baja_en\") and g[\"sn\"] in nombres_chk]\n        # Con los departamentos desactivados también: si ya existe uno igual, se reactiva (no se duplica).\n        return importar_personal.planear(filas, db.listar_personal_rh(empresa_id, incluir_bajas=True), gente_act,\n                                         db.siguiente_numero_empleado(empresa_id),\n                                         [d[\"nombre\"] for d in db.listar_departamentos(empresa_id, solo_activos=False)])\n\n    plan = armar()\n    plan.update({\"hoja\": hoja, \"hojas\": hojas, \"columnas\": columnas})\n    if not payload.aplicar:\n        return plan\n    existentes = {d[\"nombre\"]: d for d in db.listar_departamentos(empresa_id, solo_activos=False)}\n    for d in plan[\"departamentos_nuevos\"]:\n        if d not in existentes:\n            try:\n                db.crear_departamento(empresa_id, d)\n            except Exception:  # noqa: BLE001  (ya existía con otra mayúscula/espacio)\n                pass\n    usados = {r[\"datos\"].get(\"departamento\") for r in plan[\"renglones\"] if r.get(\"datos\")}\n    for nombre, d in existentes.items():\n        if nombre in usados and not d.get(\"activo\", True):\n            db.cambiar_estado_departamento(empresa_id, d[\"id\"], True)\n    # Todos entran sin usuario de app (acceso_app = FALSE): una sola contraseña al azar\n    # que nadie conoce, para no tardar ~0.3 s por persona calculándola.\n    hash_sin_acceso = auth.hash_password(secrets.token_urlsafe(32))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_importar_personal_departamentos.py")
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
