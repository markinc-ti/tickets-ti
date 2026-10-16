# -*- coding: utf-8 -*-
"""
Personas de los checadores: boton "Ligar todas las sugeridas" (las de la estrella)
y las consultas que el modelo no maneja (fotos) ya no se cuentan como error.
REQUIERE haber corrido antes fix_red_checadores.py.
Toca: backend/db.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_red_sugerencias.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "                (empresa_id, limite))\n    r = {}\n    for x in cur.fetchall():\n        d = r.setdefault(x[\"sn\"], {\"pendientes\": 0, \"enviados\": 0, \"ok\": 0, \"error\": 0, \"ultimo_error\": None})\n        if not x[\"enviado_en\"]:\n            d[\"pendientes\"] += 1\n        elif not x[\"resultado\"]:\n            d[\"enviados\"] += 1\n        elif x[\"resultado\"].startswith(\"Return=0\"):\n            d[\"ok\"] += 1\n        else:\n            d[\"error\"] += 1\n            d[\"ultimo_error\"] = f\"{x['resultado']} · {x['comando'][:40]}\"\n",
   "                (empresa_id, limite))\n    r = {}\n    for x in cur.fetchall():\n        d = r.setdefault(x[\"sn\"], {\"pendientes\": 0, \"enviados\": 0, \"ok\": 0, \"error\": 0, \"no_soportado\": 0, \"ultimo_error\": None})\n        if not x[\"enviado_en\"]:\n            d[\"pendientes\"] += 1\n        elif not x[\"resultado\"]:\n            d[\"enviados\"] += 1\n        elif x[\"resultado\"].startswith(\"Return=0\"):\n            d[\"ok\"] += 1\n        elif x[\"comando\"].startswith(\"DATA QUERY\"):\n            # Consultas que el modelo no maneja (fotos, huellas en un equipo solo de cara…): no es error.\n            d[\"no_soportado\"] += 1\n        else:\n            d[\"error\"] += 1\n            d[\"ultimo_error\"] = f\"{x['resultado']} · {x['comando'][:40]}\"\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      </ol>\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n        <button class=\"secondary\" onclick=\"asis_leerTodos(this)\">1️⃣ Leer personas, huellas y caras de todos</button>\n        <button class=\"secondary\" onclick=\"asis_red(true, null, this)\">2️⃣ Ver qué falta</button>\n        <button class=\"primary\" onclick=\"asis_red(false, null, this)\">3️⃣ Dar de alta en los que faltan</button>\n      </div>\n",
   "      </ol>\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n        <button class=\"secondary\" onclick=\"asis_leerTodos(this)\">1️⃣ Leer personas, huellas y caras de todos</button>\n        <button class=\"secondary\" onclick=\"asis_ligarSugeridas(this)\">⭐ Ligar todas las sugeridas</button>\n        <button class=\"secondary\" onclick=\"asis_red(true, null, this)\">2️⃣ Ver qué falta</button>\n        <button class=\"primary\" onclick=\"asis_red(false, null, this)\">3️⃣ Dar de alta en los que faltan</button>\n      </div>\n"
  ],
  [
   "          <button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_pedirChk('${escapeHtml(sn)}', 'fotos', this)\">📷 Pedir fotos</button>\n        </div>\n        ${(() => { const c = (ASIS_GENTE.comandos || {})[sn]; return c ? `<div style=\"font-size:11px; color:var(--muted); margin-bottom:6px;\">Instrucciones al checador (7 días):\n          ${c.pendientes} por mandar · ${c.enviados} enviadas · <span style=\"color:#4caf50;\">${c.ok} aplicadas</span>${c.error ? ` · <span style=\"color:var(--copper);\">${c.error} con error (${escapeHtml(c.ultimo_error || '')})</span>` : ''}</div>` : ''; })()}\n        <div style=\"overflow-x:auto;\"><table class=\"users\" style=\"font-size:12px;\">\n          <thead><tr><th>Foto</th><th>No.</th><th>Nombre en el checador</th><th>Nombre corregido</th><th>Es…</th><th>Huella / cara</th><th>Checadas</th><th></th></tr></thead>\n          <tbody>${lista.map(g => `<tr>\n",
   "          <button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_pedirChk('${escapeHtml(sn)}', 'fotos', this)\">📷 Pedir fotos</button>\n        </div>\n        ${(() => { const c = (ASIS_GENTE.comandos || {})[sn]; return c ? `<div style=\"font-size:11px; color:var(--muted); margin-bottom:6px;\">Instrucciones al checador (7 días):\n          ${c.pendientes} por mandar · ${c.enviados} enviadas · <span style=\"color:#4caf50;\">${c.ok} aplicadas</span>${c.error ? ` · <span style=\"color:var(--copper);\">${c.error} con error (${escapeHtml(c.ultimo_error || '')})</span>` : ''}${c.no_soportado ? ` · ${c.no_soportado} que este modelo no maneja (ej. fotos)` : ''}</div>` : ''; })()}\n        <div style=\"overflow-x:auto;\"><table class=\"users\" style=\"font-size:12px;\">\n          <thead><tr><th>Foto</th><th>No.</th><th>Nombre en el checador</th><th>Nombre corregido</th><th>Es…</th><th>Huella / cara</th><th>Checadas</th><th></th></tr></thead>\n          <tbody>${lista.map(g => `<tr>\n"
  ],
  [
   "          </tr>`).join('')}</tbody></table></div>\n      </div>`).join('') || '<p style=\"font-size:13px; color:var(--muted);\">— todavía no hay personas: aparecen cuando alguien checa en un checador conectado directo, o al pedir los nombres al checador —</p>'}`;\n}\nasync function asis_leerTodos(btn) {\n  const sns = [...new Set(ASIS_GENTE.gente.map(g => g.sn))];\n  let chks = [];\n",
   "          </tr>`).join('')}</tbody></table></div>\n      </div>`).join('') || '<p style=\"font-size:13px; color:var(--muted);\">— todavía no hay personas: aparecen cuando alguien checa en un checador conectado directo, o al pedir los nombres al checador —</p>'}`;\n}\n// Liga de una vez a todas las personas sin ligar que tienen una sugerencia ⭐ (o una persona elegida en su lista).\nasync function asis_ligarSugeridas(btn) {\n  const pendientes = ASIS_GENTE.gente.filter(g => !g.usuario_id).map(g => {\n    const sel = document.getElementById(`gusr_${g.id}`);\n    const nom = document.getElementById(`gnom_${g.id}`);\n    return { g, uid: Number(sel ? sel.value : asis_sugerir(ASIS_GENTE.usuarios, g.nombre || g.nombre_checador)) || null, nombre: nom ? nom.value.trim() || null : g.nombre };\n  }).filter(x => x.uid);\n  if (!pendientes.length) { alert('No hay sugerencias pendientes: las que faltan elígelas a mano.'); return; }\n  if (!confirm(`¿Ligar ${pendientes.length} persona(s) con la persona sugerida (⭐)? Revisa antes que las sugerencias sean correctas.`)) return;\n  await conBloqueoDeBoton(btn, async () => {\n    let ok = 0;\n    for (const x of pendientes) {\n      try { await api(`/api/rh/checadores/gente/${x.g.id}`, { method: 'PATCH', body: JSON.stringify({ usuario_id: x.uid, nombre: x.nombre }) }); Object.assign(x.g, { usuario_id: x.uid, nombre: x.nombre }); ok++; } catch (e) {}\n    }\n    try { ASIS_GENTE = Object.assign(await api('/api/rh/checadores/gente'), { comandos: ASIS_GENTE.comandos }); } catch (e) {}\n    asis_pintarGente();\n    alert(`✔ ${ok} persona(s) ligadas.`);\n  });\n}\n\nasync function asis_leerTodos(btn) {\n  const sns = [...new Set(ASIS_GENTE.gente.map(g => g.sn))];\n  let chks = [];\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_red_sugerencias.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "/api/rh/checadores/red" not in f.read():
            print("Primero corre fix_red_checadores.py (y los anteriores), y luego este.")
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
