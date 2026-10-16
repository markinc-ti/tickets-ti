# -*- coding: utf-8 -*-
"""
Asistencia: el checador de la app (selfie + ubicacion) cuenta igual que el biometrico.
- Entra en el reporte de RH, el informe del dia, el Excel y "Mi asistencia".
- Cuenta tambien para quien no tiene numero de empleado; no cuenta lo que RH marco "no coincide".
- Nueva opcion "Checador de la app" al elegir biometrico. En el detalle de cada dia se ve de donde vino cada checada.
REQUIERE haber corrido antes fix_checadores_numero_microsip.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_asistencia_checador_app.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\ndef _reporte_asistencia(empresa_id, desde, hasta, solo_usuario_id=None, checador=None, sucursal=None):\n    empleados = db.empleados_asistencia(empresa_id)\n    checadas = db.listar_checadas(empresa_id, desde, hasta)\n    # Checadores conectados directo (ADMS): la persona se identifica por (checador, número),\n    # porque el mismo número puede ser otra persona en otro checador. Solo cuenta si RH la ligó.\n    gente = db.mapa_gente_checador(empresa_id)\n    con_numero = {e[\"id\"] for e in empleados}\n    extra_ids = {g[\"usuario_id\"] for g in gente.values() if g.get(\"usuario_id\")} - con_numero\n    sin_numero_ids = set()\n    for u in db.usuarios_por_ids(empresa_id, extra_ids):\n        u[\"numero_empleado\"] = f\"U{u['id']}\"\n",
   "\ndef _reporte_asistencia(empresa_id, desde, hasta, solo_usuario_id=None, checador=None, sucursal=None):\n    empleados = db.empleados_asistencia(empresa_id)\n    # Las del checador de la app se toman directo de checador_app (abajo): así cuentan\n    # también para quien no tiene número de empleado y se respeta la revisión de RH.\n    checadas = [c for c in db.listar_checadas(empresa_id, desde, hasta) if c.get(\"origen\") != \"app\"]\n    # Checadores conectados directo (ADMS): la persona se identifica por (checador, número),\n    # porque el mismo número puede ser otra persona en otro checador. Solo cuenta si RH la ligó.\n    gente = db.mapa_gente_checador(empresa_id)\n    con_numero = {e[\"id\"] for e in empleados}\n    # Checador de la app (selfie + ubicación): cuenta igual que el biométrico,\n    # salvo las checadas que RH marcó como \"no coincide\".\n    checadas_app = [x for x in db.listar_checadas_app(empresa_id, desde, hasta) if x.get(\"revision\") != \"no_coincide\"]\n    extra_ids = ({g[\"usuario_id\"] for g in gente.values() if g.get(\"usuario_id\")} | {x[\"usuario_id\"] for x in checadas_app}) - con_numero\n    sin_numero_ids = set()\n    for u in db.usuarios_por_ids(empresa_id, extra_ids):\n        u[\"numero_empleado\"] = f\"U{u['id']}\"\n"
  ],
  [
   "        if not c.get(\"nombre\") and nombres_chk.get(c[\"codigo\"]):\n            c[\"nombre\"] = nombres_chk[c[\"codigo\"]]\n        c[\"codigo\"] = equivalencias.get(c[\"codigo\"], c[\"codigo\"])\n    if solo_usuario_id:\n        empleados = [e for e in empleados if e[\"id\"] == solo_usuario_id]\n    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n",
   "        if not c.get(\"nombre\") and nombres_chk.get(c[\"codigo\"]):\n            c[\"nombre\"] = nombres_chk[c[\"codigo\"]]\n        c[\"codigo\"] = equivalencias.get(c[\"codigo\"], c[\"codigo\"])\n    for x in checadas_app:\n        cod = codigo_de_usuario.get(x[\"usuario_id\"])\n        if cod:\n            checadas.append({\"codigo\": cod, \"fecha_hora\": x[\"fecha_hora\"], \"dispositivo\": \"📱 App\",\n                             \"equipo\": \"APP\", \"origen\": \"app\", \"nombre\": x.get(\"nombre_completo\")})\n    if solo_usuario_id:\n        empleados = [e for e in empleados if e[\"id\"] == solo_usuario_id]\n    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n"
  ],
  [
   "    \"\"\"Biométricos y sucursales para elegir qué ver, y el horario de cada sucursal.\"\"\"\n    sucursales = db.listar_sucursales_reparacion(empresa_id, solo_activas=True)\n    hs = db.horarios_sucursal_asistencia(empresa_id)\n    return {\n        \"checadores\": [{\"sn\": k[\"sn\"], \"nombre\": k.get(\"nombre\") or k[\"sn\"], \"sucursal\": k.get(\"sucursal\")}\n                       for k in db.listar_checadores_adms(empresa_id)],\n        \"sucursales\": [{\"id\": x[\"id\"], \"nombre\": x[\"nombre\"], \"horario\": hs.get(x[\"id\"])} for x in sucursales],\n    }\n\n",
   "    \"\"\"Biométricos y sucursales para elegir qué ver, y el horario de cada sucursal.\"\"\"\n    sucursales = db.listar_sucursales_reparacion(empresa_id, solo_activas=True)\n    hs = db.horarios_sucursal_asistencia(empresa_id)\n    checadores = [{\"sn\": k[\"sn\"], \"nombre\": k.get(\"nombre\") or k[\"sn\"], \"sucursal\": k.get(\"sucursal\")}\n                  for k in db.listar_checadores_adms(empresa_id)]\n    if db.hay_checadas_app(empresa_id):\n        checadores.append({\"sn\": \"APP\", \"nombre\": \"📱 Checador de la app\", \"sucursal\": None})\n    return {\n        \"checadores\": checadores,\n        \"sucursales\": [{\"id\": x[\"id\"], \"nombre\": x[\"nombre\"], \"horario\": hs.get(x[\"id\"])} for x in sucursales],\n    }\n\n"
  ]
 ],
 "backend/db.py": [
  [
   "    return rows\n\n\ndef obtener_checada_app(empresa_id, checada_id):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return rows\n\n\ndef hay_checadas_app(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT 1 AS x FROM checador_app WHERE empresa_id = %s LIMIT 1\", (empresa_id,))\n    r = cur.fetchone() is not None\n    cur.close(); conn.close()\n    return r\n\n\ndef obtener_checada_app(empresa_id, checada_id):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "frontend/index.html": [
  [
   "                  <td>${x.comida ? `${x.comida} min` : '—'}${x.comida_excedida ? ` <span style=\"font-size:11px; color:#e8a33d; font-weight:700;\">+${x.comida_excedida}</span>` : ''}</td>\n                  <td>${x.minutos ? asis_hhmm(x.minutos) : '—'}</td>\n                  <td>${asis_badge(x.estatus)}${x.minutos_retardo ? ` <span style=\"font-size:11px;\">+${x.minutos_retardo} min</span>` : ''}${x.motivo ? ` <span style=\"font-size:11px; color:var(--muted);\">${escapeHtml(x.motivo)}</span>` : ''}</td>\n                  <td style=\"font-size:11px; color:var(--muted);\">${x.checadas.join(', ') || '—'}</td>\n                </tr>`).join('')}</tbody>\n            </table></td></tr>` : ''}`;\n        }).join('') || '<tr><td colspan=\"11\" class=\"empty-col\">— Nadie en esta vista (o sin número de empleado) —</td></tr>'}\n",
   "                  <td>${x.comida ? `${x.comida} min` : '—'}${x.comida_excedida ? ` <span style=\"font-size:11px; color:#e8a33d; font-weight:700;\">+${x.comida_excedida}</span>` : ''}</td>\n                  <td>${x.minutos ? asis_hhmm(x.minutos) : '—'}</td>\n                  <td>${asis_badge(x.estatus)}${x.minutos_retardo ? ` <span style=\"font-size:11px;\">+${x.minutos_retardo} min</span>` : ''}${x.motivo ? ` <span style=\"font-size:11px; color:var(--muted);\">${escapeHtml(x.motivo)}</span>` : ''}</td>\n                  <td style=\"font-size:11px; color:var(--muted);\">${x.checadas.join(', ') || '—'}${(x.dispositivos || []).length ? `<div style=\"font-size:10px;\">${x.dispositivos.map(escapeHtml).join(' · ')}</div>` : ''}</td>\n                </tr>`).join('')}</tbody>\n            </table></td></tr>` : ''}`;\n        }).join('') || '<tr><td colspan=\"11\" class=\"empty-col\">— Nadie en esta vista (o sin número de empleado) —</td></tr>'}\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_asistencia_checador_app.py")
        sys.exit(1)
    errores = []
    with open("frontend/index.html", encoding="utf-8") as f:
        if "asis_numeroMicrosip" not in f.read():
            print("Primero corre fix_checadores_numero_microsip.py (y los anteriores), y luego este.")
            sys.exit(1)
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    bin_cambios = {}
    for ruta, b64 in NUEVOS_BIN.items():
        datos = base64.b64decode(b64)
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                if f.read() == datos:
                    continue
        bin_cambios[ruta] = datos
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append("No encontre {} -- corre el script desde la carpeta del repo.".format(ruta))
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        # Windows: el archivo puede tener saltos CRLF, LF o una mezcla.
        # Se trabaja todo en LF y al guardar se deja como estaba (CRLF si tenia).
        crlf = "\r\n" in original
        texto = original.replace("\r\n", "\n")
        inicial = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue  # ya aplicado
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo, 1)
        if texto != inicial:
            cambios[ruta] = texto.replace("\n", "\r\n") if crlf else texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, datos in bin_cambios.items():
        with open(ruta, "wb") as f:
            f.write(datos)
        print("Actualizado:", ruta)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios and not bin_cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
