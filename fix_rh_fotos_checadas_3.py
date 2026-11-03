# -*- coding: utf-8 -*-
"""
FOTOS DE LAS CHECADAS: DIAGNOSTICO POR CHECADOR
En "Fotos de las checadas" sale una tabla por checador: si manda fotos (y la
ultima), si mando una que no se pudo leer (con el detalle) y que tipo de datos
manda (ATTLOG = checadas, ATTPHOTO = fotos...). Asi se sabe si falta activar la
foto en el checador o si llega en otro formato.
REQUIERE haber corrido antes fix_rh_fotos_checadas_2.py.
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_fotos_checadas_3.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "            creado_en TEXT NOT NULL\n        );\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS usuarios_pedidos_en TEXT;\n        -- Número de la persona en el checador -> usuario (cuando no es igual a su número de empleado).\n        CREATE TABLE IF NOT EXISTS rh_codigos_checador (\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n",
   "            creado_en TEXT NOT NULL\n        );\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS usuarios_pedidos_en TEXT;\n        -- Diagnóstico de fotos de checadas: cuántas llegaron, el último intento y si alguna no se pudo leer.\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS fotos_recibidas INTEGER NOT NULL DEFAULT 0;\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS ultima_foto_intento TEXT;\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS error_foto TEXT;\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS tablas_recibidas TEXT;\n        -- Número de la persona en el checador -> usuario (cuando no es igual a su número de empleado).\n        CREATE TABLE IF NOT EXISTS rh_codigos_checador (\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n"
  ],
  [
   "    return filas\n\n\ndef ultimas_fotos_por_checador(empresa_id):\n    \"\"\"{sn: fecha de la última foto de checada recibida} — para saber si el checador sí manda fotos.\"\"\"\n    conn = get_connection()\n",
   "    return filas\n\n\ndef registrar_envio_checador(sn, tabla, foto_ok=None, error=None):\n    \"\"\"Lleva la cuenta de qué tipo de datos manda cada checador (ATTLOG, ATTPHOTO, USERINFO...) y,\n    para las fotos, cuántas llegaron bien y el último error. Sirve para saber por qué no hay fotos.\"\"\"\n    ts = ahora().isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT tablas_recibidas FROM rh_checadores WHERE sn = %s\", (sn,))\n    r = cur.fetchone()\n    if r is not None:\n        vistas = [t for t in (r[\"tablas_recibidas\"] or \"\").split(\",\") if t]\n        tabla = (tabla or \"?\").upper()[:20]\n        if tabla not in vistas:\n            vistas = (vistas + [tabla])[-15:]\n        if foto_ok is None:\n            cur.execute(\"UPDATE rh_checadores SET tablas_recibidas = %s WHERE sn = %s\", (\",\".join(vistas), sn))\n        else:\n            cur.execute(\"\"\"UPDATE rh_checadores SET tablas_recibidas = %s, ultima_foto_intento = %s,\n                             fotos_recibidas = fotos_recibidas + %s, error_foto = CASE WHEN %s THEN error_foto ELSE %s END\n                           WHERE sn = %s\"\"\", (\",\".join(vistas), ts, 1 if foto_ok else 0, bool(foto_ok), (error or \"\")[:300], sn))\n        conn.commit()\n    cur.close(); conn.close()\n\n\ndef diagnostico_fotos_checadores(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT sn, nombre, sucursal, fotos_recibidas, ultima_foto_intento, error_foto, tablas_recibidas, ultima_conexion\n                   FROM rh_checadores WHERE empresa_id = %s AND activo ORDER BY sucursal, sn\"\"\", (empresa_id,))\n    r = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return r\n\n\ndef ultimas_fotos_por_checador(empresa_id):\n    \"\"\"{sn: fecha de la última foto de checada recibida} — para saber si el checador sí manda fotos.\"\"\"\n    conn = get_connection()\n"
  ]
 ],
 "backend/app.py": [
  [
   "            if foto:\n                db.foto_checada_gente(chk[\"empresa_id\"], sn, foto[0], foto[1])\n                db.guardar_foto_checada(chk[\"empresa_id\"], sn, foto[0], asistencia.fecha_foto_checada(crudo), foto[1])\n        return _texto_plano(\"OK\")\n    if tabla != \"ATTLOG\":\n        if chk and chk.get(\"empresa_id\") and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\", \"USERPIC\", \"BIOPHOTO\", \"BIODATA\"):\n            if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)) and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\"):\n",
   "            if foto:\n                db.foto_checada_gente(chk[\"empresa_id\"], sn, foto[0], foto[1])\n                db.guardar_foto_checada(chk[\"empresa_id\"], sn, foto[0], asistencia.fecha_foto_checada(crudo), foto[1])\n                db.registrar_envio_checador(sn, tabla, foto_ok=True)\n            else:\n                cabeza = crudo[:160].split(b\"\\x00\")[0].decode(\"latin-1\", \"replace\").replace(\"\\n\", \" | \")\n                db.registrar_envio_checador(sn, tabla, foto_ok=False,\n                                            error=f\"No pude leer la foto ({len(crudo)} bytes): {cabeza}\")\n        return _texto_plano(\"OK\")\n    if chk and chk.get(\"empresa_id\") and tabla:\n        try:\n            db.registrar_envio_checador(sn, tabla)\n        except Exception:  # noqa: BLE001\n            pass\n    if tabla != \"ATTLOG\":\n        if chk and chk.get(\"empresa_id\") and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\", \"USERPIC\", \"BIOPHOTO\", \"BIODATA\"):\n            if db.guardar_info_gente_checador(chk[\"empresa_id\"], sn, *asistencia.leer_datos_checador(cuerpo)) and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\"):\n"
  ],
  [
   "    return {\"fecha\": dia.isoformat(), \"dias_guardadas\": db.DIAS_FOTOS_CHECADA,\n            \"fotos\": db.listar_fotos_checadas(usuario[\"empresa_id\"], dia, sn),\n            \"sin_foto\": db.checadas_sin_foto(usuario[\"empresa_id\"], dia, sn),\n            \"ultima_foto_por_checador\": db.ultimas_fotos_por_checador(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/rh/checadores/{sn}/pedir-fotos\")\n",
   "    return {\"fecha\": dia.isoformat(), \"dias_guardadas\": db.DIAS_FOTOS_CHECADA,\n            \"fotos\": db.listar_fotos_checadas(usuario[\"empresa_id\"], dia, sn),\n            \"sin_foto\": db.checadas_sin_foto(usuario[\"empresa_id\"], dia, sn),\n            \"ultima_foto_por_checador\": db.ultimas_fotos_por_checador(usuario[\"empresa_id\"]),\n            \"checadores\": db.diagnostico_fotos_checadores(usuario[\"empresa_id\"])}\n\n\n@app.post(\"/api/rh/checadores/{sn}/pedir-fotos\")\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      Puedes pedírselas al checador (si todavía las tiene y tu modelo lo acepta llegan en 1–2 min).\n      Si nunca llegan, activa en el checador <b>tomar/guardar foto al verificar</b> (Menú → Sistema o Asistencia → <i>Foto de verificación</i>).\n      ${ASIS_FCH.sn ? `<div style=\"margin-top:6px;\"><button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_pedirFotosDia(this)\">📥 Pedir al checador las fotos de este día</button></div>` : '<div style=\"margin-top:4px; color:var(--muted);\">Elige un checador para pedirle las fotos.</div>'}\n    </div>`;\n  const tarjetasSinFoto = (f === 'todas' ? sinFoto : []).map(x => `<div class=\"cv-caja\" style=\"padding:8px; opacity:.75;\">\n      <div style=\"height:120px; display:flex; align-items:center; justify-content:center; background:#0002; border-radius:8px; font-size:11px; color:var(--muted);\">📷 sin foto de esta checada</div>\n",
   "      Puedes pedírselas al checador (si todavía las tiene y tu modelo lo acepta llegan en 1–2 min).\n      Si nunca llegan, activa en el checador <b>tomar/guardar foto al verificar</b> (Menú → Sistema o Asistencia → <i>Foto de verificación</i>).\n      ${ASIS_FCH.sn ? `<div style=\"margin-top:6px;\"><button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_pedirFotosDia(this)\">📥 Pedir al checador las fotos de este día</button></div>` : '<div style=\"margin-top:4px; color:var(--muted);\">Elige un checador para pedirle las fotos.</div>'}\n      ${(d.checadores || []).length ? `<table class=\"users\" style=\"font-size:11px; margin-top:8px;\"><thead><tr><th>Checador</th><th>¿Manda fotos?</th><th>Qué manda</th></tr></thead><tbody>\n        ${(d.checadores || []).filter(k => !ASIS_FCH.sn || k.sn === ASIS_FCH.sn).map(k => {\n          const ult = ultimas[k.sn];\n          const estado = k.fotos_recibidas > 0 || ult\n            ? `<span style=\"color:#4caf50;\">✔ Sí</span>${ult ? ` · última ${escapeHtml(String(ult).replace('T', ' ').slice(0, 16))}` : ''}`\n            : k.error_foto ? `<span style=\"color:var(--copper);\">⚠️ Manda pero no se pudo leer</span><div style=\"color:var(--muted);\">${escapeHtml(k.error_foto)}</div>`\n            : '<span style=\"color:#e8a33d;\">✖ No ha mandado ninguna foto</span> — activa la foto de verificación en el checador';\n          return `<tr><td><b>${escapeHtml(k.nombre || k.sn)}</b><div style=\"color:var(--muted);\">${escapeHtml(k.sn)}</div></td><td>${estado}</td>\n            <td style=\"color:var(--muted);\">${escapeHtml((k.tablas_recibidas || '— (todavía no registra)').replace(/,/g, ', '))}</td></tr>`; }).join('')}\n      </tbody></table>` : ''}\n    </div>`;\n  const tarjetasSinFoto = (f === 'todas' ? sinFoto : []).map(x => `<div class=\"cv-caja\" style=\"padding:8px; opacity:.75;\">\n      <div style=\"height:120px; display:flex; align-items:center; justify-content:center; background:#0002; border-radius:8px; font-size:11px; color:var(--muted);\">📷 sin foto de esta checada</div>\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_fotos_checadas_3.py")
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
