# -*- coding: utf-8 -*-
"""
LABORATORIO: DESGLOSE AL REGISTRAR PAGO + AVISO AUTOMATICO SIN PAGO
1) "Registrar pago" en la sucursal ahora muestra Total del trabajo / Ya pagado /
   Se debe, y abajo "Total capturado - faltaria $X / queda cubierto".
2) Aviso automatico: si un estudiante hizo su pedido en la app y a 1 dia no ha
   pagado (ni reporto transferencia), le llega UNA vez una notificacion en la
   app + correo: "Si quiere ayuda contactenos al numero 2231128045 o acuda a
   nuestra sucursal Mark Inc / Dentigo mas cercana de su preferencia."
   Se revisa cada 30 min de 9 a 20 h; queda anotado en el historial del trabajo.
   Pedidos de mas de 7 dias sin pago no se avisan (viejos o de prueba).
Correr DESPUES de fix_laboratorio_columna_matricula.py y fix_laboratorio_telefono_y_permiso.py
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_laboratorio_pago_desglose_y_aviso.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "        -- 'sucursal' (alta en mostrador) o 'app' (el estudiante lo creó desde la app/portal):\n        -- los de la app empiezan como \"Registro pedido en app\".\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'sucursal';\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n",
   "        -- 'sucursal' (alta en mostrador) o 'app' (el estudiante lo creó desde la app/portal):\n        -- los de la app empiezan como \"Registro pedido en app\".\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS origen TEXT NOT NULL DEFAULT 'sucursal';\n        -- Aviso automático al estudiante si a 1 día de pedir en la app no ha pagado (una sola vez).\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS aviso_sin_pago_en TEXT;\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS recibido_sucursal_por_id INTEGER REFERENCES users(id);\n        ALTER TABLE trabajos_laboratorio ADD COLUMN IF NOT EXISTS entregado_por_id INTEGER REFERENCES users(id);\n        -- Datos que ahora se piden obligatorios desde la recepción: folio de\n"
  ],
  [
   "    return resultado\n\n\ndef marcar_aviso_vigencia(usuario_id, tipo, fecha):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return resultado\n\n\ndef pedidos_lab_sin_pago_para_aviso():\n    \"\"\"Pedidos hechos por estudiantes en la app que siguen sin pago (ni registrado\n    ni transferencia reportada) y a los que todavía no se les avisó.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT l.id, l.empresa_id, l.folio, l.creado_en, l.creado_por_id, l.paciente_nombre,\n                          u.nombre_completo, u.email\n                   FROM trabajos_laboratorio l JOIN users u ON u.id = l.creado_por_id\n                   WHERE l.origen = 'app' AND l.estado = 'recibido' AND l.pago_registrado_en IS NULL\n                     AND l.aviso_sin_pago_en IS NULL AND u.rol = 'estudiante' AND u.activo\n                     AND NOT EXISTS (SELECT 1 FROM laboratorio_pagos_reportados r WHERE r.trabajo_id = l.id)\n                   ORDER BY l.id\"\"\")\n    filas = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return filas\n\n\ndef marcar_aviso_sin_pago_lab(trabajo_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE trabajos_laboratorio SET aviso_sin_pago_en = %s WHERE id = %s\",\n                (ahora().isoformat(timespec=\"seconds\"), trabajo_id))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef marcar_aviso_vigencia(usuario_id, tipo, fecha):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "backend/app.py": [
  [
   "        print(f\"[vigencia] error revisando vigencias: {e}\")\n\n\n@app.on_event(\"startup\")\ndef iniciar_scheduler_vigencias():\n    if not APSCHEDULER_DISPONIBLE:\n",
   "        print(f\"[vigencia] error revisando vigencias: {e}\")\n\n\nTEXTO_AYUDA_PAGO_LAB = (\"Si quiere ayuda contáctenos al número 2231128045 o acuda a nuestra sucursal \"\n                        \"Mark Inc / Dentigo más cercana de su preferencia.\")\n\n\ndef _revisar_pedidos_lab_sin_pago():\n    \"\"\"Cada 30 min (de 9 a 20 h): a quien pidió en la app hace 1 día o más y no ha pagado,\n    le manda UNA vez un aviso (push en la app + correo) con el teléfono de ayuda.\n    Los pedidos de más de 7 días sin pago no se avisan (son viejos o de prueba).\"\"\"\n    from datetime import datetime as dt\n    try:\n        ahora = db.ahora()\n        if not (9 <= ahora.hour < 20):\n            return\n        for p in db.pedidos_lab_sin_pago_para_aviso():\n            try:\n                creado = dt.fromisoformat(str(p[\"creado_en\"]))\n                if creado.tzinfo is None:\n                    creado = creado.replace(tzinfo=ahora.tzinfo)\n            except (TypeError, ValueError):\n                continue\n            edad = ahora - creado\n            if edad < timedelta(days=1):\n                continue\n            db.marcar_aviso_sin_pago_lab(p[\"id\"])\n            if edad > timedelta(days=7):\n                continue\n            nombre = (p.get(\"nombre_completo\") or \"\").split(\" \")[0]\n            titulo = f\"Tu pedido {p['folio']} está pendiente de pago\"\n            texto = (f\"Hola {nombre}: su pedido {p['folio']}\" + (f\" ({p['paciente_nombre']})\" if p.get(\"paciente_nombre\") else \"\")\n                     + \" sigue pendiente de pago, por eso todavía no entra al laboratorio. \" + TEXTO_AYUDA_PAGO_LAB)\n            avisos.avisar_seguro([p[\"creado_por_id\"]], titulo, texto, modulo=\"laboratorio\", ref=p[\"id\"])\n            try:\n                correo.enviar(p.get(\"email\"), titulo, texto + \"\\n\\nMarkinc Lab\")\n            except Exception as e:  # noqa: BLE001\n                print(f\"[pago-lab] correo {p['folio']}: {e}\")\n            db.agregar_actualizacion_laboratorio(p[\"id\"], p[\"creado_por_id\"],\n                                                 \"Aviso automático: a 1 día del pedido seguía sin pago (se le mandó el teléfono de ayuda).\")\n            print(f\"[pago-lab] aviso sin pago {p['folio']}\")\n    except Exception as e:\n        print(f\"[pago-lab] error revisando pedidos sin pago: {e}\")\n\n\n@app.on_event(\"startup\")\ndef iniciar_scheduler_vigencias():\n    if not APSCHEDULER_DISPONIBLE:\n"
  ],
  [
   "    sched.add_job(_revisar_vigencias_estudiantes, \"cron\", hour=9, minute=5, id=\"vigencias_estudiantes\")\n    sched.add_job(_revisar_vigencias_estudiantes, \"date\",\n                  run_date=db.ahora() + timedelta(minutes=2), id=\"vigencias_estudiantes_arranque\")\n    sched.start()\n\n\n",
   "    sched.add_job(_revisar_vigencias_estudiantes, \"cron\", hour=9, minute=5, id=\"vigencias_estudiantes\")\n    sched.add_job(_revisar_vigencias_estudiantes, \"date\",\n                  run_date=db.ahora() + timedelta(minutes=2), id=\"vigencias_estudiantes_arranque\")\n    sched.add_job(_revisar_pedidos_lab_sin_pago, \"interval\", minutes=30, id=\"pedidos_lab_sin_pago\",\n                  next_run_time=db.ahora() + timedelta(minutes=3))\n    sched.start()\n\n\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    ${w.estado === 'recibido' && !yaPagado ? `\n      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;\">\n        <p style=\"font-size:13px; margin:0 0 8px;\">💳 Falta registrar el pago — es obligatorio antes de poder marcar los dientes en el odontograma.</p>\n        <button class=\"primary\" style=\"width:100%;\" onclick=\"abrirRegistrarPagoLaboratorio(${w.id})\">Registrar pago</button>\n      </div>\n    ` : ''}\n    ${yaPagado ? `\n",
   "    ${w.estado === 'recibido' && !yaPagado ? `\n      <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;\">\n        <p style=\"font-size:13px; margin:0 0 8px;\">💳 Falta registrar el pago — es obligatorio antes de poder marcar los dientes en el odontograma.</p>\n        <button class=\"primary\" style=\"width:100%;\" onclick=\"abrirRegistrarPagoLaboratorio(${w.id}, ${Number(w.costo_total) || 0}, ${Number(w.pago_monto_total) || 0})\">Registrar pago</button>\n      </div>\n    ` : ''}\n    ${yaPagado ? `\n"
  ],
  [
   "      ${saldo < 0 && w.estado === 'recibido' ? `\n        <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;\">\n          <p style=\"font-size:13px; margin:0 0 8px;\">⚠️ Falta cubrir ${_fmtC(-saldo)} — no se puede continuar (firmar recepción) hasta completar el pago.</p>\n          <button class=\"primary\" style=\"width:100%;\" onclick=\"abrirRegistrarPagoLaboratorio(${w.id})\">Registrar pago adicional</button>\n        </div>\n      ` : ''}\n    ` : ''}\n",
   "      ${saldo < 0 && w.estado === 'recibido' ? `\n        <div style=\"border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:8px;\">\n          <p style=\"font-size:13px; margin:0 0 8px;\">⚠️ Falta cubrir ${_fmtC(-saldo)} — no se puede continuar (firmar recepción) hasta completar el pago.</p>\n          <button class=\"primary\" style=\"width:100%;\" onclick=\"abrirRegistrarPagoLaboratorio(${w.id}, ${Number(w.costo_total) || 0}, ${Number(w.pago_monto_total) || 0})\">Registrar pago adicional</button>\n        </div>\n      ` : ''}\n    ` : ''}\n"
  ],
  [
   "// Igual que SIGUIENTE_ESTADO_LABORATORIO del servidor: uno por uno.\nconst SIGUIENTE_ESTADO_LAB_JS = { en_laboratorio: 'modelado', maquila: 'maquillado', maquillado: 'control_calidad', control_calidad: 'envio_sucursal' };\n\nfunction abrirRegistrarPagoLaboratorio(trabajoId) {\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Registrar pago</h2>\n    <p style=\"font-size:12px; color:var(--muted);\">Marca el o los métodos que usó y cuánto pagó con cada uno — se puede dividir entre varios.</p>\n    <div id=\"lp_metodos\">\n      ${(META.tipos_metodo_pago_laboratorio || ['efectivo','tarjeta_debito','tarjeta_credito','transferencia','otro']).map(m => `\n",
   "// Igual que SIGUIENTE_ESTADO_LABORATORIO del servidor: uno por uno.\nconst SIGUIENTE_ESTADO_LAB_JS = { en_laboratorio: 'modelado', maquila: 'maquillado', maquillado: 'control_calidad', control_calidad: 'envio_sucursal' };\n\nfunction abrirRegistrarPagoLaboratorio(trabajoId, costoTotal, yaPagado) {\n  const falta = Math.max(0, Math.round(((Number(costoTotal) || 0) - (Number(yaPagado) || 0)) * 100) / 100);\n  window._lpFalta = costoTotal != null ? falta : null;\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Registrar pago</h2>\n    ${costoTotal != null ? `\n      <div style=\"display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 10px;\">\n        <div style=\"flex:1; min-width:120px; border:1px solid rgba(155,157,159,.4); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">TOTAL DEL TRABAJO</div><b style=\"font-size:18px;\">${_fmtC(costoTotal)}</b></div>\n        <div style=\"flex:1; min-width:120px; border:1px solid rgba(155,157,159,.4); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">YA PAGADO</div><b style=\"font-size:18px;\">${_fmtC(yaPagado || 0)}</b></div>\n        <div style=\"flex:1; min-width:120px; border:1px solid var(--copper); border-radius:8px; padding:8px 10px;\"><div style=\"font-size:11px; color:var(--muted);\">SE DEBE</div><b style=\"font-size:18px; color:var(--copper);\">${_fmtC(falta)}</b></div>\n      </div>` : ''}\n    <p style=\"font-size:12px; color:var(--muted);\">Marca el o los métodos que usó y cuánto pagó con cada uno — se puede dividir entre varios.</p>\n    <div id=\"lp_metodos\">\n      ${(META.tipos_metodo_pago_laboratorio || ['efectivo','tarjeta_debito','tarjeta_credito','transferencia','otro']).map(m => `\n"
  ],
  [
   "        </div>\n      `).join('')}\n    </div>\n    <p style=\"font-size:13px; margin:8px 0;\">Total: <b id=\"lp_total\">$0.00</b></p>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;\">Foto del comprobante de pago *</label>\n    <div id=\"lp_comprobante_preview\" style=\"margin:6px 0;\"></div>\n    <label class=\"secondary btn-file\" style=\"display:inline-block;\">\n",
   "        </div>\n      `).join('')}\n    </div>\n    <p style=\"font-size:13px; margin:8px 0;\">Total capturado: <b id=\"lp_total\">$0.00</b> <span id=\"lp_dif\" style=\"font-size:12px;\"></span></p>\n    <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase;\">Foto del comprobante de pago *</label>\n    <div id=\"lp_comprobante_preview\" style=\"margin:6px 0;\"></div>\n    <label class=\"secondary btn-file\" style=\"display:inline-block;\">\n"
  ],
  [
   "  `;\n  window._lpComprobanteBase64 = null;\n  abrirModal();\n}\n\nfunction _lpToggleMetodo(metodo, activo) {\n",
   "  `;\n  window._lpComprobanteBase64 = null;\n  abrirModal();\n  _lpActualizarTotal();\n}\n\nfunction _lpToggleMetodo(metodo, activo) {\n"
  ],
  [
   "  let total = 0;\n  document.querySelectorAll('.lp_metodo_monto').forEach(inp => { if (!inp.disabled) total += parseFloat(inp.value) || 0; });\n  document.getElementById('lp_total').textContent = _fmtC(total);\n}\n\nasync function _lpSubirComprobante(input) {\n",
   "  let total = 0;\n  document.querySelectorAll('.lp_metodo_monto').forEach(inp => { if (!inp.disabled) total += parseFloat(inp.value) || 0; });\n  document.getElementById('lp_total').textContent = _fmtC(total);\n  const dif = document.getElementById('lp_dif');\n  if (dif && window._lpFalta != null) {\n    const resta = Math.round((window._lpFalta - total) * 100) / 100;\n    dif.innerHTML = resta > 0 ? `<span style=\"color:var(--copper);\">· faltaría ${_fmtC(resta)}</span>`\n      : resta < 0 ? `<span style=\"color:#e6a23c;\">· ${_fmtC(-resta)} de más</span>` : '<span style=\"color:#4caf50;\">· queda cubierto ✔</span>';\n  }\n}\n\nasync function _lpSubirComprobante(input) {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_laboratorio_pago_desglose_y_aviso.py")
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
