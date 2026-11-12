# -*- coding: utf-8 -*-
"""
tickets-ti: el checador de la app sigue el proceso del checador de la sucursal.

Si la persona checó la entrada en el biométrico (huella/cara) de su sucursal, en la app
ya no le sale "Entrada" sino "Salida a comer" o "Salida" (y así con lo demás).
Las checadas del biométrico también se ven en "Mis checadas de hoy" de la app
(ej. "Entrada · Checador 13 Sur"). No hay que cambiar ni recompilar la app.

Necesita fix_reiniciar_checador.py aplicado antes.
Uso (en la carpeta tickets-ti):  py -3 fix_checador_app_sigue_biometrico.py
Se puede correr varias veces (si ya está aplicado no cambia nada).
"""
import io
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    }.get(ultimo, [])\n\n\ndef _hay_cara(foto_base64):\n    \"\"\"True/False si se pudo revisar; None si el servidor no tiene OpenCV\n    (entonces no se bloquea y RH revisa a ojo).\"\"\"\n",
   "    }.get(ultimo, [])\n\n\n# Lo que toca después de cada checada. Las del biométrico (huella/cara en la sucursal) no traen\n# tipo: se les pone por orden del día (1a entrada, 2a salida a comer, 3a regreso, 4a salida).\n_SIGUE_NATURAL = {None: \"entrada\", \"entrada\": \"salida_comida\", \"salida_comida\": \"regreso_comida\",\n                  \"regreso_comida\": \"salida\", \"salida\": \"salida\"}\n\n\ndef _checadas_biometrico_dia(usuario, dia):\n    \"\"\"Checadas de ese día de la persona en los checadores de la sucursal (ADMS directo, BioTime o archivo).\"\"\"\n    empresa_id, uid = usuario[\"empresa_id\"], usuario[\"id\"]\n    filas = [c for c in db.listar_checadas(empresa_id, dia, dia) if c.get(\"origen\") != \"app\"]\n    if not filas:\n        return []\n    gente = db.mapa_gente_checador(empresa_id)\n    u = (db.usuarios_por_ids(empresa_id, [uid]) or [{}])[0]\n    mi_num = asistencia.normalizar_codigo(u.get(\"numero_empleado\")) if (u.get(\"numero_empleado\") or \"\").strip() else None\n    equivalencias = {asistencia.normalizar_codigo(x[\"codigo\"]): x[\"usuario_id\"] for x in db.codigos_checador(empresa_id)}\n    nombres = {k[\"sn\"]: k.get(\"nombre\") or k.get(\"sucursal\") or k[\"sn\"] for k in db.listar_checadores_adms(empresa_id)}\n    no_coinciden = db.checadas_no_coinciden(empresa_id, dia, dia)\n    out = []\n    for c in filas:\n        cod = asistencia.normalizar_codigo(c[\"codigo\"])\n        if c.get(\"origen\") == \"adms\" and c.get(\"equipo\"):\n            if (gente.get((c[\"equipo\"], cod)) or {}).get(\"usuario_id\") != uid:\n                continue\n            if (c[\"equipo\"], cod, c[\"fecha_hora\"].replace(microsecond=0)) in no_coinciden:\n                continue\n            donde = nombres.get(c[\"equipo\"]) or c[\"equipo\"]\n        else:\n            if cod in equivalencias:\n                if equivalencias[cod] != uid:\n                    continue\n            elif not (mi_num and cod == mi_num):\n                continue\n            donde = c.get(\"dispositivo\") or \"checador\"\n        out.append({\"fecha_hora\": c[\"fecha_hora\"], \"donde\": donde})\n    return out\n\n\ndef _checadas_del_dia(usuario, dia):\n    \"\"\"Checadas de la app + las del checador de la sucursal, en orden, cada una con su tipo.\n    Así, si checó la entrada en la sucursal, en la app ya le toca la comida o la salida.\"\"\"\n    def _fh(v):\n        return _fecha_chk(v) or datetime_min\n    datetime_min = _fecha_chk(\"2000-01-01T00:00:00\")\n    app_ = [dict(c, origen=\"app\") for c in db.checadas_app_dia(usuario[\"id\"], dia)]\n    try:\n        bio = [{\"tipo\": None, \"fecha_hora\": b[\"fecha_hora\"], \"donde\": b[\"donde\"], \"origen\": \"checador\"}\n               for b in _checadas_biometrico_dia(usuario, dia)]\n    except Exception as e:  # noqa: BLE001  (si falla, el checador de la app sigue como antes)\n        print(f\"[checador app] no se pudieron leer las del biométrico: {e}\")\n        bio = []\n    res, ultimo = [], None\n    for c in sorted(app_ + bio, key=lambda x: _fh(x[\"fecha_hora\"])):\n        if c[\"tipo\"] is None:\n            # Marcó dos veces seguidas en el reloj (menos de 2 min): cuenta una.\n            if res and abs((_fh(c[\"fecha_hora\"]) - _fh(res[-1][\"fecha_hora\"])).total_seconds()) < 120:\n                continue\n            c[\"tipo\"] = _SIGUE_NATURAL.get(ultimo, \"salida\")\n        res.append(c)\n        ultimo = c[\"tipo\"]\n    return res\n\n\ndef _hay_cara(foto_base64):\n    \"\"\"True/False si se pudo revisar; None si el servidor no tiene OpenCV\n    (entonces no se bloquea y RH revisa a ojo).\"\"\"\n"
  ],
  [
   "    checadas = db.checadas_app_dia(usuario[\"id\"], hoy)\n",
   "    checadas = _checadas_del_dia(usuario, hoy)\n"
  ],
  [
   "        c[\"etiqueta\"] = TIPOS_CHECADA_APP.get(c[\"tipo\"], c[\"tipo\"])\n",
   "        c[\"etiqueta\"] = TIPOS_CHECADA_APP.get(c[\"tipo\"], c[\"tipo\"]) + (f\" · {c['donde']}\" if c.get(\"origen\") == \"checador\" else \"\")\n"
  ],
  [
   "    sig = _siguientes_checadas(db.checadas_app_dia(usuario[\"id\"], hoy))\n",
   "    sig = _siguientes_checadas(_checadas_del_dia(usuario, hoy))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_app_sigue_biometrico.py")
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
