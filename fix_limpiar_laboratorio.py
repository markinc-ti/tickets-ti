# -*- coding: utf-8 -*-
"""
Limpiar laboratorio (empezar en limpio):
  - Administrar → Portal de estudiantes → "🧹 Limpiar laboratorio".
  - Muestra cuántos pedidos/trabajos (con piezas, fotos, avances, pagos,
    diseños y escaneos) y cuántos estudiantes hay, y los borra al escribir
    BORRAR. Todo en una sola transacción. Los folios vuelven a empezar en 1.
  - No toca precios, catálogos, solicitantes, el enlace de registro ni la
    configuración de Microsip. Las cotizaciones ya creadas en Microsip no se
    borran de Microsip.
REQUIERE haber corrido antes fix_usuarios_sin_estudiantes.py.
Toca: backend/app.py, backend/db.py, frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return {\"ok\": True}\n\n\n@app.post(\"/api/laboratorio/estudiantes/{estudiante_id}/microsip\")\ndef api_microsip_estudiante_laboratorio(estudiante_id: int, payload: MicrosipEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):\n    \"\"\"Lo da de alta como cliente en Microsip. Si hay clientes parecidos y no\n",
   "    return {\"ok\": True}\n\n\nclass LimpiarLaboratorioIn(BaseModel):\n    confirmacion: str\n    movimientos: bool = True\n    estudiantes: bool = True\n\n\n@app.get(\"/api/laboratorio/limpiar\")\ndef api_resumen_limpiar_laboratorio(usuario: dict = Depends(requiere_admin_completo)):\n    return db.resumen_limpieza_laboratorio(usuario[\"empresa_id\"])\n\n\n@app.post(\"/api/laboratorio/limpiar\")\ndef api_limpiar_laboratorio(payload: LimpiarLaboratorioIn, usuario: dict = Depends(requiere_admin_completo)):\n    \"\"\"Arrancar en limpio: borra pedidos/trabajos de laboratorio y/o a todos\n    los estudiantes de la empresa. Hay que escribir BORRAR para confirmar.\"\"\"\n    if payload.confirmacion.strip().upper() != \"BORRAR\":\n        raise HTTPException(status_code=400, detail=\"Escribe BORRAR para confirmar.\")\n    if not payload.movimientos and not payload.estudiantes:\n        raise HTTPException(status_code=400, detail=\"Elige qué quieres borrar.\")\n    try:\n        hecho = db.limpiar_laboratorio(usuario[\"empresa_id\"], payload.movimientos, payload.estudiantes)\n    except Exception as e:\n        raise HTTPException(status_code=500, detail=f\"No se borró nada: {e}\")\n    return {\"ok\": True, **hecho}\n\n\n@app.post(\"/api/laboratorio/estudiantes/{estudiante_id}/microsip\")\ndef api_microsip_estudiante_laboratorio(estudiante_id: int, payload: MicrosipEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):\n    \"\"\"Lo da de alta como cliente en Microsip. Si hay clientes parecidos y no\n"
  ]
 ],
 "backend/db.py": [
  [
   "    return True\n\n\ndef cuenta_estudiante_laboratorio(empresa_id, usuario_id):\n    \"\"\"Para el propio estudiante: si está activo y su vigencia.\"\"\"\n    conn = get_connection()\n",
   "    return True\n\n\n# ---- Limpiar laboratorio (Administrar → Portal de estudiantes) ----\n# Para arrancar en limpio: borra los pedidos/trabajos de laboratorio de la\n# empresa (con piezas, fotos, avances, pagos, diseños y escaneos, que se van\n# en cascada) y/o a todos los estudiantes. NO toca precios, catálogos,\n# solicitantes, el enlace de registro ni la configuración de Microsip.\n\n_TABLAS_HIJAS_LAB = [\"laboratorio_piezas\", \"laboratorio_evidencias\", \"laboratorio_actualizaciones\",\n                     \"laboratorio_pagos_reportados\", \"laboratorio_disenos\", \"laboratorio_escaneos\",\n                     \"laboratorio_pago_metodos\"]\n\n\ndef resumen_limpieza_laboratorio(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT COUNT(*) AS n FROM trabajos_laboratorio WHERE empresa_id = %s\", (empresa_id,))\n    datos = {\"trabajos\": cur.fetchone()[\"n\"]}\n    for t in _TABLAS_HIJAS_LAB:\n        cur.execute(f\"\"\"SELECT COUNT(*) AS n FROM {t} x JOIN trabajos_laboratorio l ON l.id = x.trabajo_id\n                        WHERE l.empresa_id = %s\"\"\", (empresa_id,))\n        datos[t.replace(\"laboratorio_\", \"\")] = cur.fetchone()[\"n\"]\n    cur.execute(\"SELECT COUNT(*) AS n FROM users WHERE empresa_id = %s AND rol = 'estudiante'\", (empresa_id,))\n    datos[\"estudiantes\"] = cur.fetchone()[\"n\"]\n    cur.execute(\"\"\"SELECT COUNT(*) AS n FROM trabajos_laboratorio\n                   WHERE empresa_id = %s AND microsip_docto_id IS NOT NULL\"\"\", (empresa_id,))\n    datos[\"cotizaciones_microsip\"] = cur.fetchone()[\"n\"]\n    cur.close(); conn.close()\n    return datos\n\n\ndef _referencias_a_users(cur):\n    \"\"\"(tabla, columna, acepta_null, accion_al_borrar) de cada llave foránea\n    que apunta a users.id — para soltar o borrar lo del estudiante antes de\n    borrarlo, sin tener que listar las tablas a mano.\"\"\"\n    cur.execute(\"\"\"\n        SELECT c.conrelid::regclass::text AS tabla, a.attname AS columna,\n               NOT a.attnotnull AS acepta_null, c.confdeltype AS accion\n        FROM pg_constraint c\n        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]\n        WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass AND array_length(c.conkey, 1) = 1\n    \"\"\")\n    return [dict(r) for r in cur.fetchall()]\n\n\ndef limpiar_laboratorio(empresa_id, movimientos=True, estudiantes=True):\n    \"\"\"Todo en una sola transacción: si algo falla no se borra nada.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    hecho = {\"trabajos\": 0, \"estudiantes\": 0}\n    try:\n        if movimientos:\n            cur.execute(\"DELETE FROM trabajos_laboratorio WHERE empresa_id = %s\", (empresa_id,))\n            hecho[\"trabajos\"] = cur.rowcount\n        if estudiantes:\n            cur.execute(\"SELECT id FROM users WHERE empresa_id = %s AND rol = 'estudiante'\", (empresa_id,))\n            ids = [r[\"id\"] for r in cur.fetchall()]\n            if ids:\n                # Sus pedidos primero (si no se borraron arriba) para que se\n                # lleven en cascada sus piezas, fotos, pagos, etc.\n                cur.execute(\"DELETE FROM trabajos_laboratorio WHERE empresa_id = %s AND creado_por_id = ANY(%s)\",\n                            (empresa_id, ids))\n                hecho[\"trabajos\"] += cur.rowcount\n                for ref in _referencias_a_users(cur):\n                    if ref[\"tabla\"] == \"users\" or ref[\"accion\"] in (\"c\", \"n\"):\n                        continue   # ON DELETE CASCADE / SET NULL: Postgres lo hace solo\n                    tabla, col = ref[\"tabla\"], ref[\"columna\"]\n                    if ref[\"acepta_null\"]:\n                        cur.execute(f'UPDATE {tabla} SET \"{col}\" = NULL WHERE \"{col}\" = ANY(%s)', (ids,))\n                    else:\n                        cur.execute(f'DELETE FROM {tabla} WHERE \"{col}\" = ANY(%s)', (ids,))\n                cur.execute(\"DELETE FROM users WHERE empresa_id = %s AND rol = 'estudiante' AND id = ANY(%s)\",\n                            (empresa_id, ids))\n                hecho[\"estudiantes\"] = cur.rowcount\n        conn.commit()\n    except Exception:\n        conn.rollback()\n        raise\n    finally:\n        cur.close(); conn.close()\n    return hecho\n\n\ndef cuenta_estudiante_laboratorio(empresa_id, usuario_id):\n    \"\"\"Para el propio estudiante: si está activo y su vigencia.\"\"\"\n    conn = get_connection()\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    </div>\n    <button class=\"secondary\" style=\"width:100%; margin-top:10px; color:var(--urgente);\" onclick=\"regenerarEnlaceEstudiantesLaboratorioUI()\">Generar un enlace nuevo (invalida el anterior)</button>\n    <div id=\"est_lab\" style=\"margin-top:24px;\"></div>\n  `;\n  abrirModal(true);\n  est_cargar();\n}\n\n// ---------- Base de estudiantes registrados ----------\n",
   "    </div>\n    <button class=\"secondary\" style=\"width:100%; margin-top:10px; color:var(--urgente);\" onclick=\"regenerarEnlaceEstudiantesLaboratorioUI()\">Generar un enlace nuevo (invalida el anterior)</button>\n    <div id=\"est_lab\" style=\"margin-top:24px;\"></div>\n    <div id=\"lab_limpiar\" style=\"margin-top:28px; border-top:1px solid var(--border, #ddd); padding-top:16px;\">\n      <button class=\"secondary\" style=\"width:100%; color:var(--urgente);\" onclick=\"lab_abrirLimpiar()\">🧹 Limpiar laboratorio (empezar en limpio)</button>\n    </div>\n  `;\n  abrirModal(true);\n  est_cargar();\n}\n\n// ---------- Limpiar laboratorio ----------\n// Borra pedidos/trabajos (con piezas, fotos, avances, pagos, diseños y\n// escaneos) y/o a todos los estudiantes. Deja precios, catálogos,\n// solicitantes, el enlace de registro y la configuración de Microsip.\n\nasync function lab_abrirLimpiar() {\n  const caja = document.getElementById('lab_limpiar');\n  if (!caja) return;\n  caja.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">Contando…</p>';\n  let r;\n  try { r = await api('/api/laboratorio/limpiar'); }\n  catch (e) { caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; return; }\n  caja.innerHTML = `\n    <h3 style=\"margin:0 0 8px; color:var(--urgente);\">🧹 Limpiar laboratorio</h3>\n    <p style=\"font-size:12px; margin:0 0 10px;\">Esto <b>no se puede deshacer</b>. No toca precios, catálogos, solicitantes, el enlace de registro ni la configuración de Microsip.</p>\n    <label style=\"display:flex; gap:8px; align-items:flex-start; font-size:13px; margin-bottom:8px;\">\n      <input type=\"checkbox\" id=\"lab_lim_mov\" checked style=\"width:auto; margin-top:3px;\">\n      <span><b>Pedidos y trabajos:</b> ${r.trabajos} trabajo(s) con ${r.piezas} pieza(s), ${r.evidencias} foto(s), ${r.actualizaciones} avance(s), ${r.pagos_reportados} pago(s) reportado(s), ${r.disenos} diseño(s) y ${r.escaneos} escaneo(s). Los folios vuelven a empezar en 1.</span>\n    </label>\n    <label style=\"display:flex; gap:8px; align-items:flex-start; font-size:13px; margin-bottom:8px;\">\n      <input type=\"checkbox\" id=\"lab_lim_est\" checked style=\"width:auto; margin-top:3px;\">\n      <span><b>Todos los estudiantes:</b> ${r.estudiantes} cuenta(s) de la app Mark·Inc Lab. Tendrán que registrarse otra vez.</span>\n    </label>\n    ${r.cotizaciones_microsip ? `<p style=\"font-size:12px; color:#e8a33d; margin:0 0 8px;\">⚠️ ${r.cotizaciones_microsip} pedido(s) ya crearon cotización en Microsip. Esas cotizaciones no se borran de Microsip; cancélalas allá si eran de prueba.</p>` : ''}\n    <div class=\"field\">\n      <label>Escribe BORRAR para confirmar</label>\n      <input type=\"text\" id=\"lab_lim_conf\" autocomplete=\"off\" placeholder=\"BORRAR\">\n    </div>\n    <div id=\"lab_lim_msg\"></div>\n    <div style=\"display:flex; gap:8px;\">\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"renderLimpiarBoton()\">Cancelar</button>\n      <button class=\"primary\" style=\"flex:1; background:var(--urgente);\" onclick=\"lab_ejecutarLimpiar(this)\">Borrar</button>\n    </div>`;\n}\n\nfunction renderLimpiarBoton() {\n  const caja = document.getElementById('lab_limpiar');\n  if (caja) caja.innerHTML = `<button class=\"secondary\" style=\"width:100%; color:var(--urgente);\" onclick=\"lab_abrirLimpiar()\">🧹 Limpiar laboratorio (empezar en limpio)</button>`;\n}\n\nasync function lab_ejecutarLimpiar(btn) {\n  const msg = document.getElementById('lab_lim_msg');\n  const movimientos = document.getElementById('lab_lim_mov').checked;\n  const estudiantes = document.getElementById('lab_lim_est').checked;\n  const confirmacion = document.getElementById('lab_lim_conf').value;\n  if (confirmacion.trim().toUpperCase() !== 'BORRAR') { msg.innerHTML = '<div class=\"error-msg\">Escribe BORRAR para confirmar.</div>'; return; }\n  if (!movimientos && !estudiantes) { msg.innerHTML = '<div class=\"error-msg\">Elige qué quieres borrar.</div>'; return; }\n  btn.disabled = true; btn.textContent = 'Borrando…';\n  try {\n    const r = await api('/api/laboratorio/limpiar', { method: 'POST', body: JSON.stringify({ confirmacion, movimientos, estudiantes }) });\n    document.getElementById('lab_limpiar').innerHTML = `<div style=\"font-size:13px; color:#4caf50; font-weight:700;\">✓ Listo: se borraron ${r.trabajos} trabajo(s) y ${r.estudiantes} estudiante(s).</div>`;\n    est_cargar();\n  } catch (e) {\n    msg.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`;\n    btn.disabled = false; btn.textContent = 'Borrar';\n  }\n}\n\n// ---------- Base de estudiantes registrados ----------\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/db.py", encoding="utf-8") as f:
        if "IS DISTINCT FROM 'estudiante'" not in f.read():
            print("Primero corre fix_usuarios_sin_estudiantes.py (y luego este).")
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
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
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
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
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
