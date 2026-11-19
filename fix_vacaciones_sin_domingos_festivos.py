# -*- coding: utf-8 -*-
"""Vacaciones: no contar domingos ni dias festivos (empleados en prueba y ajuste de antiguedad).

- Nuevo backend/calendario_laboral.py: domingos + descanso obligatorio LFT art. 74
  (1 ene, 1er lunes feb, 3er lunes mar, 1 may, 16 sep, 3er lunes nov, 25 dic y 1 oct cada 6 anios).
  Si la empresa da otro asueto, se agrega en DIAS_EXTRA.
- 14 dias desde el 22/dic -> ultimo dia 8/ene, regresa 9/ene (brinca 25/dic, 1/ene y domingos).
- Mis vacaciones y RH -> Vacaciones muestran "al ... - regresa ...".
- RH -> Ausencias ya no pinta domingos ni festivos como vacaciones (prueba y ajuste; ajuste
  antes contaba dias naturales).
- El formato PDF usa el mismo calculo y dice que domingos y festivos no se cuentan.
- No deja pedir vacaciones que empiecen en domingo o festivo (empleados en prueba).
Requiere fix_rh_vacaciones_prueba_formato.py. Correr en tickets-ti:  py -3 fix_vacaciones_sin_domingos_festivos.py
"""
import os, sys

NOMBRE = 'fix_vacaciones_sin_domingos_festivos.py'
CARPETA = 'tickets-ti'
MARCA = 'backend/app.py'

ARCHIVOS = {
 "backend/app.py": [
  [
   "import pdfs_laboratorio\nimport pdfs_rh\nimport rh_formato_pdf\nimport pdfs_equipos\nimport pdfs_cotizaciones\nimport pdfs_direccion",
   "import pdfs_laboratorio\nimport pdfs_rh\nimport rh_formato_pdf\nimport calendario_laboral\nimport pdfs_equipos\nimport pdfs_cotizaciones\nimport pdfs_direccion"
  ],
  [
   "# Solo quien está en RH → Empleados en prueba (estatus 'prueba') y ligado a un usuario.\n# Sus días son los de su ficha (manuales o por LFT); RH aprueba en RH → Vacaciones.\n\ndef _mis_vacaciones_prueba(usuario, prueba):\n    emp = _con_saldo_lft(db.obtener_empleado_prueba(usuario[\"empresa_id\"], prueba[\"id\"]))\n    s = emp[\"saldo_vacaciones_lft\"]",
   "# Solo quien está en RH → Empleados en prueba (estatus 'prueba') y ligado a un usuario.\n# Sus días son los de su ficha (manuales o por LFT); RH aprueba en RH → Vacaciones.\n\ndef _periodo_vacacion(fecha_inicio, dias):\n    \"\"\"{fecha_fin, fecha_regreso, dias_lista}: los días que sí cuentan, sin domingos ni festivos.\"\"\"\n    try:\n        ini = date.fromisoformat(str(fecha_inicio)[:10])\n    except ValueError:\n        return {}\n    tomados, fin, regreso, _ = calendario_laboral.rango_laboral(ini, dias)\n    return {\"fecha_fin\": fin.isoformat(), \"fecha_regreso\": regreso.isoformat(), \"dias_lista\": [d.isoformat() for d in tomados]}\n\n\ndef _mis_vacaciones_prueba(usuario, prueba):\n    emp = _con_saldo_lft(db.obtener_empleado_prueba(usuario[\"empresa_id\"], prueba[\"id\"]))\n    s = emp[\"saldo_vacaciones_lft\"]"
  ],
  [
   "    for x, v in zip(solicitudes, emp.get(\"vacaciones\", [])):\n        x[\"dias\"] = float(x[\"dias\"] or 0)\n        x[\"pedida_por_mi\"] = v.get(\"solicitado_por_id\") == usuario[\"id\"]  # las que capturó RH no se cancelan aquí\n    return {\n        \"disponible\": True,\n        \"tipo\": \"prueba\",",
   "    for x, v in zip(solicitudes, emp.get(\"vacaciones\", [])):\n        x[\"dias\"] = float(x[\"dias\"] or 0)\n        x[\"pedida_por_mi\"] = v.get(\"solicitado_por_id\") == usuario[\"id\"]  # las que capturó RH no se cancelan aquí\n        x.update({k: v2 for k, v2 in _periodo_vacacion(x[\"fecha_inicio\"], x[\"dias\"]).items() if k != \"dias_lista\"})\n    return {\n        \"disponible\": True,\n        \"tipo\": \"prueba\","
  ],
  [
   "        raise HTTPException(status_code=400, detail=\"La fecha de inicio ya pasó.\")\n    if payload.dias * 2 != int(payload.dias * 2):\n        raise HTTPException(status_code=400, detail=\"Los días van enteros o medios (ej. 1, 1.5, 2).\")\n    emp = _con_saldo_lft(db.obtener_empleado_prueba(usuario[\"empresa_id\"], prueba[\"id\"]))\n    s = emp[\"saldo_vacaciones_lft\"]\n    if payload.dias > s[\"dias_disponibles\"] + 1e-6:",
   "        raise HTTPException(status_code=400, detail=\"La fecha de inicio ya pasó.\")\n    if payload.dias * 2 != int(payload.dias * 2):\n        raise HTTPException(status_code=400, detail=\"Los días van enteros o medios (ej. 1, 1.5, 2).\")\n    if calendario_laboral.es_descanso(inicio):\n        motivo = \"domingo\" if inicio.weekday() == 6 else f\"día festivo ({calendario_laboral.festivos(inicio.year)[inicio]})\"\n        raise HTTPException(status_code=400, detail=f\"El {inicio.strftime('%d/%m/%Y')} es {motivo}: elige como inicio un día laborable.\")\n    emp = _con_saldo_lft(db.obtener_empleado_prueba(usuario[\"empresa_id\"], prueba[\"id\"]))\n    s = emp[\"saldo_vacaciones_lft\"]\n    if payload.dias > s[\"dias_disponibles\"] + 1e-6:"
  ],
  [
   "\n@app.get(\"/api/rh/vacaciones-prueba\")\ndef api_listar_vacaciones_prueba_rh(estado: Optional[str] = \"pendiente\", usuario: dict = Depends(requiere_datos_empleado_rh)):\n    return db.listar_vacaciones_prueba_empresa(usuario[\"empresa_id\"], None if estado in (None, \"\", \"todas\") else estado)\n\n\n@app.post(\"/api/rh/vacaciones-prueba/{vacacion_id}/resolver\")",
   "\n@app.get(\"/api/rh/vacaciones-prueba\")\ndef api_listar_vacaciones_prueba_rh(estado: Optional[str] = \"pendiente\", usuario: dict = Depends(requiere_datos_empleado_rh)):\n    lista = db.listar_vacaciones_prueba_empresa(usuario[\"empresa_id\"], None if estado in (None, \"\", \"todas\") else estado)\n    for v in lista:\n        v.update({k: x for k, x in _periodo_vacacion(v[\"fecha_inicio\"], v[\"dias\"]).items() if k != \"dias_lista\"})\n    return lista\n\n\n@app.post(\"/api/rh/vacaciones-prueba/{vacacion_id}/resolver\")"
  ],
  [
   "    for v in db.listar_vacaciones_prueba_empresa(usuario[\"empresa_id\"], solo_solicitadas=False):\n        if v.get(\"estado\") not in (\"pendiente\", \"aprobada\"):\n            continue\n        fin, _ = rh_formato_pdf.rango_vacaciones(v[\"fecha_inicio\"], v[\"dias\"])\n        eventos.append({\n            \"origen\": \"vacaciones_prueba_app\",\n            \"persona\": v.get(\"usuario_nombre\"),\n            \"tipo\": \"Vacaciones\",\n            \"fecha_inicio\": str(v[\"fecha_inicio\"])[:10],\n            \"fecha_fin\": fin.isoformat() if fin else str(v[\"fecha_inicio\"])[:10],\n            \"estado\": v.get(\"estado\"),\n            \"detalle\": v.get(\"descripcion\"),\n        })",
   "    for v in db.listar_vacaciones_prueba_empresa(usuario[\"empresa_id\"], solo_solicitadas=False):\n        if v.get(\"estado\") not in (\"pendiente\", \"aprobada\"):\n            continue\n        per = _periodo_vacacion(v[\"fecha_inicio\"], v[\"dias\"])\n        eventos.append({\n            \"origen\": \"vacaciones_prueba_app\",\n            \"persona\": v.get(\"usuario_nombre\"),\n            \"tipo\": \"Vacaciones\",\n            \"fecha_inicio\": str(v[\"fecha_inicio\"])[:10],\n            \"fecha_fin\": per.get(\"fecha_fin\") or str(v[\"fecha_inicio\"])[:10],\n            \"dias_lista\": per.get(\"dias_lista\"),  # el calendario no pinta domingos ni festivos\n            \"estado\": v.get(\"estado\"),\n            \"detalle\": v.get(\"descripcion\"),\n        })"
  ],
  [
   "    # fecha_ingreso_ajustada activa) — no salen en Microsip porque nunca lo\n    # tocan, así que sin esto desaparecían por completo del calendario.\n    for v in db.listar_vacaciones_ajuste_empresa(usuario[\"empresa_id\"]):\n        dias = float(v[\"dias\"])\n        fecha_inicio_str = str(v[\"fecha_inicio\"])\n        fecha_fin_str = fecha_inicio_str\n        try:\n            fecha_fin_str = (date.fromisoformat(fecha_inicio_str) + timedelta(days=max(int(dias) - 1, 0))).isoformat()\n        except ValueError:\n            pass\n        eventos.append({\n            \"origen\": \"vacaciones_ajuste_app\",\n            \"persona\": v.get(\"usuario_nombre\"),\n            \"tipo\": \"Vacaciones\",\n            \"fecha_inicio\": fecha_inicio_str,\n            \"fecha_fin\": fecha_fin_str,\n            \"estado\": v.get(\"estado\"),\n            \"detalle\": v.get(\"descripcion\"),\n            \"vacacion_ajuste_id\": v.get(\"id\"),",
   "    # fecha_ingreso_ajustada activa) — no salen en Microsip porque nunca lo\n    # tocan, así que sin esto desaparecían por completo del calendario.\n    for v in db.listar_vacaciones_ajuste_empresa(usuario[\"empresa_id\"]):\n        fecha_inicio_str = str(v[\"fecha_inicio\"])[:10]\n        per = _periodo_vacacion(fecha_inicio_str, v[\"dias\"])  # sin domingos ni festivos\n        eventos.append({\n            \"origen\": \"vacaciones_ajuste_app\",\n            \"persona\": v.get(\"usuario_nombre\"),\n            \"tipo\": \"Vacaciones\",\n            \"fecha_inicio\": fecha_inicio_str,\n            \"fecha_fin\": per.get(\"fecha_fin\") or fecha_inicio_str,\n            \"dias_lista\": per.get(\"dias_lista\"),\n            \"estado\": v.get(\"estado\"),\n            \"detalle\": v.get(\"descripcion\"),\n            \"vacacion_ajuste_id\": v.get(\"id\"),"
  ]
 ],
 "backend/rh_formato_pdf.py": [
  [
   "from reportlab.lib.units import inch, mm\nfrom reportlab.lib.utils import ImageReader\nfrom reportlab.pdfgen import canvas\n\nMEDIA_CARTA = (5.5 * inch, 8.5 * inch)\nROJO = colors.HexColor(\"#B3121F\")",
   "from reportlab.lib.units import inch, mm\nfrom reportlab.lib.utils import ImageReader\nfrom reportlab.pdfgen import canvas\n\nimport calendario_laboral\n\nMEDIA_CARTA = (5.5 * inch, 8.5 * inch)\nROJO = colors.HexColor(\"#B3121F\")"
  ],
  [
   "\n\ndef rango_vacaciones(fecha_inicio, dias):\n    \"\"\"Último día y día de regreso contando días laborables (se brinca el domingo).\"\"\"\n    d = _fecha(fecha_inicio)\n    if not d:\n        return None, None\n    n = max(int(math.ceil(float(dias or 0))), 1)\n    fin, contados = d, 0\n    while True:\n        if fin.weekday() != 6:\n            contados += 1\n            if contados == n:\n                break\n        fin += timedelta(days=1)\n    regreso = fin + timedelta(days=1)\n    while regreso.weekday() == 6:\n        regreso += timedelta(days=1)\n    return fin, regreso\n\n",
   "\n\ndef rango_vacaciones(fecha_inicio, dias):\n    \"\"\"Último día y día de regreso contando solo días laborables: no cuentan\n    los domingos ni los festivos oficiales (ver calendario_laboral).\"\"\"\n    d = _fecha(fecha_inicio)\n    if not d:\n        return None, None\n    _, fin, regreso, _ = calendario_laboral.rango_laboral(d, dias)\n    return fin, regreso\n\n"
  ],
  [
   "\ndef detalle_vacaciones(fecha_inicio, dias):\n    fin, regreso = rango_vacaciones(fecha_inicio, dias)\n    dias_f = float(dias or 0)\n    filas = [(\"Tipo\", \"Vacaciones\"),\n             (\"Días solicitados\", f\"{_num(dias_f)} día{'s' if dias_f != 1 else ''}\" + (\" (incluye medio día)\" if dias_f != int(dias_f) else \"\")),\n             (\"Desde\", fecha_larga(fecha_inicio))]\n    if fin:\n        filas.append((\"Último día\", fecha_larga(fin)))\n        filas.append((\"Regresa a laborar\", fecha_larga(regreso)))\n    return filas\n\n",
   "\ndef detalle_vacaciones(fecha_inicio, dias):\n    fin, regreso = rango_vacaciones(fecha_inicio, dias)\n    d0 = _fecha(fecha_inicio)\n    brincados = calendario_laboral.rango_laboral(d0, dias)[3] if d0 else []\n    festivos_txt = \", \".join(f\"{f.day} {MESES[f.month - 1][:3]}\" for f, n in brincados if n != \"Domingo\")\n    dias_f = float(dias or 0)\n    filas = [(\"Tipo\", \"Vacaciones\"),\n             (\"Días solicitados\", f\"{_num(dias_f)} día{'s' if dias_f != 1 else ''}\" + (\" (incluye medio día)\" if dias_f != int(dias_f) else \"\")),\n             (\"Desde\", fecha_larga(fecha_inicio))]\n    if fin:\n        filas.append((\"Último día\", fecha_larga(fin)))\n        filas.append((\"Regresa a laborar\", fecha_larga(regreso)))\n        filas.append((\"No se cuentan\", \"Domingos y festivos\" + (f\" ({festivos_txt})\" if festivos_txt else \"\")))\n    return filas\n\n"
  ]
 ],
 "frontend/index.html": [
  [
   "        ${listaPrueba.map(v => `\n          <tr>\n            <td>${escapeHtml(v.usuario_nombre)}</td>\n            <td>${v.fecha_inicio}</td>\n            <td>${Number(v.dias)}</td>\n            <td style=\"max-width:220px;\">${v.descripcion ? escapeHtml(v.descripcion) : '—'}${v.resuelto_por_nombre ? `<div style=\"font-size:10px; color:var(--muted);\">Resuelta por ${escapeHtml(v.resuelto_por_nombre)}</div>` : ''}${v.respuesta_admin ? `<div style=\"font-size:11px;\">${escapeHtml(v.respuesta_admin)}</div>` : ''}</td>\n            <td>${BADGE_ESTADO_VAC[v.estado] || escapeHtml(v.estado)}</td>",
   "        ${listaPrueba.map(v => `\n          <tr>\n            <td>${escapeHtml(v.usuario_nombre)}</td>\n            <td>${v.fecha_inicio}${v.fecha_regreso ? `<div style=\"font-size:10px; color:var(--muted);\">al ${v.fecha_fin} · regresa ${v.fecha_regreso}</div>` : ''}</td>\n            <td>${Number(v.dias)}</td>\n            <td style=\"max-width:220px;\">${v.descripcion ? escapeHtml(v.descripcion) : '—'}${v.resuelto_por_nombre ? `<div style=\"font-size:10px; color:var(--muted);\">Resuelta por ${escapeHtml(v.resuelto_por_nombre)}</div>` : ''}${v.respuesta_admin ? `<div style=\"font-size:11px;\">${escapeHtml(v.respuesta_admin)}</div>` : ''}</td>\n            <td>${BADGE_ESTADO_VAC[v.estado] || escapeHtml(v.estado)}</td>"
  ],
  [
   "    if (!e.fecha_inicio) return;\n    const inicio = e.fecha_inicio;\n    const fin = e.fecha_fin || e.fecha_inicio;\n    Object.keys(porDia).forEach(fechaDia => {\n      if (fechaDia >= inicio && fechaDia <= fin) porDia[fechaDia].push(e);\n    });\n  });\n  window.__AUSENCIAS_POR_DIA = porDia;",
   "    if (!e.fecha_inicio) return;\n    const inicio = e.fecha_inicio;\n    const fin = e.fecha_fin || e.fecha_inicio;\n    // Vacaciones de la app: solo los días que cuentan (sin domingos ni festivos).\n    const soloDias = Array.isArray(e.dias_lista) && e.dias_lista.length ? new Set(e.dias_lista) : null;\n    Object.keys(porDia).forEach(fechaDia => {\n      if (soloDias ? soloDias.has(fechaDia) : (fechaDia >= inicio && fechaDia <= fin)) porDia[fechaDia].push(e);\n    });\n  });\n  window.__AUSENCIAS_POR_DIA = porDia;"
  ],
  [
   "        ${esPrueba && datos.dias_pendientes > 0 ? `<p style=\"font-size:12px; color:#b7791f;\">⏳ ${datos.dias_pendientes} día(s) esperando aprobación de RH.</p>` : ''}\n        ${datos.puede_solicitar ? `\n          <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:14px;\">Pedir vacaciones (te quedan ${datos.dias_para_pedir})</label>\n          <p style=\"font-size:11px; color:var(--muted); margin:4px 0 6px;\">${esPrueba ? 'RH la revisa y la aprueba; hasta entonces no se descuenta.' : 'RH la aprueba y en ese momento queda registrada en Microsip.'}</p>\n          <div class=\"row-2\" style=\"margin-top:6px;\">\n            <div class=\"field\"><label>Primer día</label><input type=\"date\" id=\"mv_fecha\" /></div>\n            <div class=\"field\"><label>Días</label><input type=\"number\" id=\"mv_dias\" value=\"1\" min=\"0.5\" step=\"0.5\" /></div>",
   "        ${esPrueba && datos.dias_pendientes > 0 ? `<p style=\"font-size:12px; color:#b7791f;\">⏳ ${datos.dias_pendientes} día(s) esperando aprobación de RH.</p>` : ''}\n        ${datos.puede_solicitar ? `\n          <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:14px;\">Pedir vacaciones (te quedan ${datos.dias_para_pedir})</label>\n          <p style=\"font-size:11px; color:var(--muted); margin:4px 0 6px;\">${esPrueba ? 'RH la revisa y la aprueba; hasta entonces no se descuenta. Solo cuentan días laborables: los domingos y los días festivos no se descuentan.' : 'RH la aprueba y en ese momento queda registrada en Microsip.'}</p>\n          <div class=\"row-2\" style=\"margin-top:6px;\">\n            <div class=\"field\"><label>Primer día</label><input type=\"date\" id=\"mv_fecha\" /></div>\n            <div class=\"field\"><label>Días</label><input type=\"number\" id=\"mv_dias\" value=\"1\" min=\"0.5\" step=\"0.5\" /></div>"
  ],
  [
   "          <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Mis solicitudes</label>\n          <table class=\"users\">\n            <thead><tr><th>Desde</th><th>Días</th><th>Nota</th><th>Estado</th><th></th></tr></thead>\n            <tbody>${datos.solicitudes.map(r => `<tr><td>${r.fecha_inicio}</td><td>${r.dias}</td><td>${r.descripcion ? escapeHtml(r.descripcion) : '—'}${r.respuesta_admin ? `<div style=\"font-size:11px; color:var(--muted);\">RH: ${escapeHtml(r.respuesta_admin)}</div>` : ''}</td><td>${{pendiente:'⏳ Pendiente', aprobada:'✅ Aprobada', rechazada:'❌ Rechazada', cancelada:'Cancelada'}[r.estado] || escapeHtml(r.estado)}</td><td style=\"display:flex; gap:4px;\">${r.estado === 'pendiente' && r.pedida_por_mi !== false ? `<button class=\"secondary\" style=\"padding:3px 8px; font-size:11px;\" onclick=\"cancelarMiSolicitudVacacionesUI(${r.id}, this)\">Cancelar</button>` : ''}${r.estado !== 'cancelada' ? pdfMio(r) : ''}</td></tr>`).join('')}</tbody>\n          </table>` : ''}\n      `}\n    `;",
   "          <label style=\"font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); text-transform:uppercase; display:block; margin-top:16px;\">Mis solicitudes</label>\n          <table class=\"users\">\n            <thead><tr><th>Desde</th><th>Días</th><th>Nota</th><th>Estado</th><th></th></tr></thead>\n            <tbody>${datos.solicitudes.map(r => `<tr><td>${r.fecha_inicio}${r.fecha_regreso ? `<div style=\"font-size:10px; color:var(--muted);\">al ${r.fecha_fin} · regresas ${r.fecha_regreso}</div>` : ''}</td><td>${r.dias}</td><td>${r.descripcion ? escapeHtml(r.descripcion) : '—'}${r.respuesta_admin ? `<div style=\"font-size:11px; color:var(--muted);\">RH: ${escapeHtml(r.respuesta_admin)}</div>` : ''}</td><td>${{pendiente:'⏳ Pendiente', aprobada:'✅ Aprobada', rechazada:'❌ Rechazada', cancelada:'Cancelada'}[r.estado] || escapeHtml(r.estado)}</td><td style=\"display:flex; gap:4px;\">${r.estado === 'pendiente' && r.pedida_por_mi !== false ? `<button class=\"secondary\" style=\"padding:3px 8px; font-size:11px;\" onclick=\"cancelarMiSolicitudVacacionesUI(${r.id}, this)\">Cancelar</button>` : ''}${r.estado !== 'cancelada' ? pdfMio(r) : ''}</td></tr>`).join('')}</tbody>\n          </table>` : ''}\n      `}\n    `;"
  ]
 ]
}

NUEVOS = {
 "backend/calendario_laboral.py": "# -*- coding: utf-8 -*-\n\"\"\"Calendario laboral para contar días de vacaciones.\n\nUn día de vacaciones solo se cuenta si es laborable: NO se cuentan los\ndomingos (descanso semanal) ni los días de descanso obligatorio de la Ley\nFederal del Trabajo (art. 74). El sábado sí cuenta, igual que en Microsip.\n\nSi la empresa da otro día de asueto (p. ej. 24 o 31 de diciembre), se agrega\nen DIAS_EXTRA como (mes, día).\n\"\"\"\nfrom datetime import date, timedelta\n\n# Asuetos de la empresa que tampoco cuentan como día de vacaciones: [(mes, día), ...]\nDIAS_EXTRA = []\n\n\ndef _lunes_numero(anio, mes, n):\n    \"\"\"El n-ésimo lunes del mes.\"\"\"\n    d = date(anio, mes, 1)\n    d += timedelta(days=(0 - d.weekday()) % 7)\n    return d + timedelta(weeks=n - 1)\n\n\ndef festivos(anio):\n    \"\"\"{fecha: nombre} de los días de descanso obligatorio (LFT art. 74) del año.\"\"\"\n    f = {\n        date(anio, 1, 1): \"Año Nuevo\",\n        _lunes_numero(anio, 2, 1): \"Día de la Constitución\",\n        _lunes_numero(anio, 3, 3): \"Natalicio de Benito Juárez\",\n        date(anio, 5, 1): \"Día del Trabajo\",\n        date(anio, 9, 16): \"Día de la Independencia\",\n        _lunes_numero(anio, 11, 3): \"Día de la Revolución\",\n        date(anio, 12, 25): \"Navidad\",\n    }\n    if anio >= 2024 and (anio - 2024) % 6 == 0:\n        f[date(anio, 10, 1)] = \"Transmisión del Poder Ejecutivo Federal\"\n    for mes, dia in DIAS_EXTRA:\n        try:\n            f.setdefault(date(anio, mes, dia), \"Asueto\")\n        except ValueError:\n            pass\n    return f\n\n\ndef es_festivo(d):\n    return d in festivos(d.year)\n\n\ndef es_descanso(d):\n    \"\"\"Domingo o festivo: no cuenta como día de vacaciones.\"\"\"\n    return d.weekday() == 6 or es_festivo(d)\n\n\ndef rango_laboral(inicio, dias):\n    \"\"\"Reparte `dias` de vacaciones desde `inicio` brincando domingos y festivos.\n\n    Regresa (dias_tomados, ultimo_dia, regreso, brincados):\n      dias_tomados: lista de fechas que sí cuentan como vacaciones;\n      ultimo_dia: el último de ellos;\n      regreso: el siguiente día laborable;\n      brincados: [(fecha, motivo)] domingos y festivos que quedaron dentro del periodo.\n    Medio día (ej. 1.5) ocupa un día más.\"\"\"\n    n = max(int(-(-float(dias or 0) // 1)), 1)  # techo\n    d, tomados, brincados = inicio, [], []\n    while len(tomados) < n:\n        if es_descanso(d):\n            if tomados:  # lo que cae antes del primer día no es parte del periodo\n                brincados.append((d, \"Domingo\" if d.weekday() == 6 else festivos(d.year)[d]))\n        else:\n            tomados.append(d)\n        d += timedelta(days=1)\n    regreso = d\n    while es_descanso(regreso):\n        regreso += timedelta(days=1)\n    return tomados, tomados[-1], regreso, brincados\n"
}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    return crudo.replace("\r\n", "\n"), "\r\n" in crudo


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo con:  py -3 " + NOMBRE)
        sys.exit(1)
    if not os.path.exists(MARCA):
        print("Corre el script dentro de la carpeta " + CARPETA + " (no encontre " + MARCA + ").")
        sys.exit(1)
    cambios, errores = {}, []
    for ruta, pasos in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pasos, 1):
            if nuevo in texto:
                continue
            n = texto.count(viejo)
            if n == 1:
                texto = texto.replace(viejo, nuevo)
            else:
                errores.append("{}: cambio #{} -- {}".format(ruta, i, "no encontre el texto donde va" if n == 0 else "el texto aparece varias veces"))
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
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
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
