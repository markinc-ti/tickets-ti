# -*- coding: utf-8 -*-
"""
RH ASISTENCIA: EXCEL POR SEMANA Y POR MES (DESGLOSADO DIA POR DIA)
RH -> Asistencia: botones "Excel por semana" y "Excel por mes" (toman la fecha
"Desde" y la vista elegida: todos, un checador o una sucursal).
- Hoja "Asistencia": una fila por persona y una columna por dia con su
  entrada-salida, R (retardo +min), FALTA, J (justificada), Descanso, Extra,
  con colores; al final los totales (asistencias, retardos, faltas, horas...).
- Por mes: hoja "Por semana" con los totales de cada semana (lunes-domingo).
- Hoja "Detalle": un renglon por persona y dia, con filtros.
El Excel de siempre (rango Desde-Hasta) sigue igual.
Toca: backend/asistencia.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_asistencia_excel_semana_mes.py
"""
import os
import sys

ARCHIVOS = {
 "backend/asistencia.py": [
  [
   "                c.alignment = Alignment(vertical=\"center\")\n    salida = io.BytesIO()\n    libro.save(salida)\n    return salida.getvalue()\n\n\n# ---------- Programa para la PC de BioTime ----------\n\nPLANTILLA_AGENTE = r'''# biotime_sync.ps1 -- Manda las checadas de BioTime Pro a tickets-ti.\n# Se instala en la PC donde esta BioTime. Corre cada 5 minutos con el\n# Programador de tareas de Windows (ver \"Instalar\" abajo). No hay que\n# abrir puertos del router: esta PC es la que se conecta a internet.\n",
   "                c.alignment = Alignment(vertical=\"center\")\n    salida = io.BytesIO()\n    libro.save(salida)\n    return salida.getvalue()\n\n\ndef excel_desglose(reporte: dict, desde: date, hasta: date, empresa: str, por: str = \"semana\") -> bytes:\n    \"\"\"Excel por SEMANA o por MES con la asistencia de todos desglosada día por día:\n    una fila por persona y una columna por día (entrada-salida, retardo, falta,\n    justificada, descanso…) con colores, más los totales del periodo. Por mes\n    agrega la hoja \"Por semana\" (totales de cada semana lunes-domingo) y siempre\n    la hoja \"Detalle\" (un renglón por persona y día, para filtrar).\"\"\"\n    import openpyxl\n    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side\n    from openpyxl.utils import get_column_letter\n    libro = openpyxl.Workbook()\n    blanco = Font(bold=True, color=\"FFFFFF\")\n    rojo = PatternFill(\"solid\", fgColor=\"D8192F\")\n    gris_enc = PatternFill(\"solid\", fgColor=\"3A3A3A\")\n    colores = {\"puntual\": \"E2F0D9\", \"retardo\": \"FFF2CC\", \"falta\": \"F8CBAD\", \"justificada\": \"DDEBF7\",\n               \"sin_salida\": \"FCE4D6\", \"sin_conexion\": \"E2E2E2\", \"descanso\": \"F2F2F2\", \"dia_no_laboral\": \"EDE7F6\"}\n    borde = Border(*(Side(style=\"thin\", color=\"D9D9D9\"),) * 4)\n    centro = Alignment(horizontal=\"center\", vertical=\"center\", wrap_text=True)\n    dias_cortos = {1: \"Lun\", 2: \"Mar\", 3: \"Mié\", 4: \"Jue\", 5: \"Vie\", 6: \"Sáb\", 7: \"Dom\"}\n    fechas = []\n    d = desde\n    while d <= hasta:\n        fechas.append(d)\n        d += timedelta(days=1)\n\n    def celda(dia):\n        if not dia or not dia.get(\"estatus\"):\n            return \"\"\n        est = dia[\"estatus\"]\n        if est == \"puntual\":\n            return f\"{dia['entrada'] or ''}-{dia['salida'] or ''}\".strip(\"-\")\n        if est == \"retardo\":\n            return f\"R {dia['entrada'] or ''} (+{dia['minutos_retardo']})\" + (f\"\\n-{dia['salida']}\" if dia.get(\"salida\") else \"\")\n        if est == \"sin_salida\":\n            return f\"{dia['entrada'] or ''} sin salida\"\n        if est == \"falta\":\n            return \"FALTA\"\n        if est == \"justificada\":\n            return \"J \" + (dia.get(\"motivo\") or \"\")[:18]\n        if est == \"descanso\":\n            return \"Descanso\"\n        if est == \"dia_no_laboral\":\n            return f\"Extra {dia['entrada'] or ''}-{dia['salida'] or ''}\".strip(\"-\")\n        if est == \"sin_conexion\":\n            return \"Sin conexión\"\n        return NOMBRES_ESTATUS.get(est, est)\n\n    titulo = \"semana\" if por == \"semana\" else \"mes\"\n    hoja = libro.active\n    hoja.title = \"Asistencia\"\n    hoja.append([f\"Asistencia por {titulo} — {empresa} — del {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}\"])\n    hoja[\"A1\"].font = Font(bold=True, size=13)\n    hoja.append([\"R = retardo (minutos tarde)  ·  J = justificada  ·  FALTA  ·  Extra = trabajó en día no laboral  ·  Sin conexión = el checador no ha mandado checadas\"])\n    hoja[\"A2\"].font = Font(italic=True, size=9, color=\"666666\")\n    fijos = [\"Empleado\", \"No. empleado\", \"Sucursal\"]\n    totales = [\"Asistencias\", \"Retardos\", \"Min. retardo\", \"Faltas\", \"Justificadas\", \"Sin salida\", \"Horas trabajadas\"]\n    hoja.append(fijos + [f\"{dias_cortos[f.isoweekday()]} {f.strftime('%d/%m')}\" for f in fechas] + totales)\n    for i, c in enumerate(hoja[3], start=1):\n        c.font = blanco\n        c.fill = gris_enc if len(fijos) < i <= len(fijos) + len(fechas) else rojo\n        c.alignment = centro\n    for e in sorted(reporte[\"empleados\"], key=lambda x: ((x.get(\"sucursal\") or \"\"), x[\"nombre\"] or \"\")):\n        por_fecha = {x[\"fecha\"]: x for x in e[\"dias\"]}\n        r = e[\"resumen\"]\n        fila = [e[\"nombre\"], e[\"numero_empleado\"], e.get(\"sucursal\") or \"\"]\n        fila += [celda(por_fecha.get(f.isoformat())) for f in fechas]\n        fila += [r[\"dias_trabajados\"], r[\"retardos\"], r[\"minutos_retardo\"], r[\"faltas\"], r[\"justificadas\"],\n                 r[\"sin_salida\"], _hhmm(r[\"minutos_trabajados\"])]\n        hoja.append(fila)\n        n = hoja.max_row\n        for j, f in enumerate(fechas):\n            c = hoja.cell(row=n, column=len(fijos) + 1 + j)\n            est = (por_fecha.get(f.isoformat()) or {}).get(\"estatus\")\n            if colores.get(est):\n                c.fill = PatternFill(\"solid\", fgColor=colores[est])\n            if est == \"falta\":\n                c.font = Font(bold=True, color=\"C00000\")\n        for c in hoja[n]:\n            c.border = borde\n            if c.column > 3:\n                c.alignment = centro\n    hoja.column_dimensions[\"A\"].width = 32\n    hoja.column_dimensions[\"B\"].width = 12\n    hoja.column_dimensions[\"C\"].width = 18\n    for j in range(len(fechas)):\n        hoja.column_dimensions[get_column_letter(4 + j)].width = 14\n    for j, ancho in enumerate((12, 10, 12, 8, 12, 10, 15)):\n        hoja.column_dimensions[get_column_letter(4 + len(fechas) + j)].width = ancho\n    hoja.freeze_panes = \"D4\"\n    hoja.auto_filter.ref = f\"A3:{get_column_letter(hoja.max_column)}{hoja.max_row}\"\n\n    if por == \"mes\":\n        sem = libro.create_sheet(\"Por semana\")\n        semanas = []\n        for f in fechas:\n            ini = f - timedelta(days=f.weekday())\n            if not semanas or semanas[-1][0] != ini:\n                semanas.append((ini, []))\n            semanas[-1][1].append(f.isoformat())\n        enc = [\"Empleado\", \"No. empleado\", \"Sucursal\"]\n        for ini, dias_sem in semanas:\n            fin = ini + timedelta(days=6)\n            et = f\"{ini.strftime('%d/%m')}-{fin.strftime('%d/%m')}\"\n            enc += [f\"{et} Asist.\", f\"{et} Ret.\", f\"{et} Faltas\", f\"{et} Horas\"]\n        sem.append(enc)\n        for c in sem[1]:\n            c.font, c.fill, c.alignment = blanco, rojo, centro\n        for e in sorted(reporte[\"empleados\"], key=lambda x: ((x.get(\"sucursal\") or \"\"), x[\"nombre\"] or \"\")):\n            por_fecha = {x[\"fecha\"]: x for x in e[\"dias\"]}\n            fila = [e[\"nombre\"], e[\"numero_empleado\"], e.get(\"sucursal\") or \"\"]\n            for _ini, dias_sem in semanas:\n                ds = [por_fecha.get(x) or {} for x in dias_sem]\n                fila += [sum(1 for x in ds if x.get(\"entrada\")), sum(1 for x in ds if x.get(\"estatus\") == \"retardo\"),\n                         sum(1 for x in ds if x.get(\"estatus\") == \"falta\"), _hhmm(sum(int(x.get(\"minutos\") or 0) for x in ds))]\n            sem.append(fila)\n            for c in sem[sem.max_row]:\n                c.border = borde\n                if c.column > 3:\n                    c.alignment = centro\n        sem.column_dimensions[\"A\"].width = 32\n        sem.column_dimensions[\"B\"].width = 12\n        sem.column_dimensions[\"C\"].width = 18\n        for j in range(4, sem.max_column + 1):\n            sem.column_dimensions[get_column_letter(j)].width = 12\n        sem.freeze_panes = \"D2\"\n\n    det = libro.create_sheet(\"Detalle\")\n    det.append([\"Empleado\", \"No. empleado\", \"Sucursal\", \"Fecha\", \"Día\", \"Entrada\", \"Salida\", \"Horas\", \"Estatus\", \"Min. retardo\", \"Motivo\", \"Todas las checadas\"])\n    for c in det[1]:\n        c.font, c.fill = blanco, rojo\n    for e in reporte[\"empleados\"]:\n        for x in e[\"dias\"]:\n            if not x[\"estatus\"]:\n                continue\n            det.append([e[\"nombre\"], e[\"numero_empleado\"], e.get(\"sucursal\") or \"\", x[\"fecha\"], x[\"dia\"], x[\"entrada\"] or \"\",\n                        x[\"salida\"] or \"\", _hhmm(x[\"minutos\"]) if x[\"minutos\"] else \"\", NOMBRES_ESTATUS.get(x[\"estatus\"], x[\"estatus\"]),\n                        x[\"minutos_retardo\"] or \"\", x[\"motivo\"] or \"\", \", \".join(x[\"checadas\"])])\n            if colores.get(x[\"estatus\"]) and x[\"estatus\"] not in (\"puntual\", \"descanso\"):\n                for c in det[det.max_row]:\n                    c.fill = PatternFill(\"solid\", fgColor=colores[x[\"estatus\"]])\n    for col, ancho in zip(\"ABCDEFGHIJKL\", (32, 12, 18, 12, 6, 9, 9, 8, 16, 12, 30, 40)):\n        det.column_dimensions[col].width = ancho\n    det.freeze_panes = \"A2\"\n    det.auto_filter.ref = f\"A1:L{det.max_row}\"\n    salida = io.BytesIO()\n    libro.save(salida)\n    return salida.getvalue()\n\n\n# ---------- Programa para la PC de BioTime ----------\n\nPLANTILLA_AGENTE = r'''# biotime_sync.ps1 -- Manda las checadas de BioTime Pro a tickets-ti.\n# Se instala en la PC donde esta BioTime. Corre cada 5 minutos con el\n# Programador de tareas de Windows (ver \"Instalar\" abajo). No hay que\n# abrir puertos del router: esta PC es la que se conecta a internet.\n"
  ]
 ],
 "backend/app.py": [
  [
   "                         sucursal: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):\n",
   "                         sucursal: Optional[str] = None, por: Optional[str] = None,\n                         usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"por=semana|mes: Excel desglosado día por día de todos (semana lunes-domingo o mes\n    completo que contiene 'desde'). Sin 'por': el Excel de siempre del rango.\"\"\"\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"]) or {}\n    if por in (\"semana\", \"mes\"):\n        try:\n            ref = date.fromisoformat(desde) if desde else db.ahora().date()\n        except ValueError:\n            raise HTTPException(status_code=400, detail=\"Fecha inválida (usa AAAA-MM-DD).\")\n        if por == \"semana\":\n            d = ref - timedelta(days=ref.weekday())\n            h = d + timedelta(days=6)\n        else:\n            d = ref.replace(day=1)\n            h = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)\n        rep = _reporte_asistencia(usuario[\"empresa_id\"], d, h, checador=checador or None, sucursal=sucursal or None)\n        contenido = asistencia.excel_desglose(rep, d, h, empresa.get(\"nombre\") or \"\", por)\n        nombre = f\"asistencia_{por}_{d.isoformat()}_{h.isoformat()}.xlsx\"\n        return Response(content=contenido,\n                        media_type=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\",\n                        headers={\"Content-Disposition\": f\"attachment; filename={nombre}\"})\n"
  ],
  [
   "    d, h = _rango_fechas(desde, hasta)\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"]) or {}\n    contenido = asistencia.excel_reporte(_reporte_asistencia(usuario[\"empresa_id\"], d, h, checador=checador or None, sucursal=sucursal or None),\n",
   "    d, h = _rango_fechas(desde, hasta)\n    contenido = asistencia.excel_reporte(_reporte_asistencia(usuario[\"empresa_id\"], d, h, checador=checador or None, sucursal=sucursal or None),\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <button class=\"secondary\" onclick=\"asis_excel(this)\">📥 Exportar Excel</button>\n      <button class=\"secondary\" onclick=\"document.getElementById('asis_archivo').click()\">📄 Importar archivo de BioTime</button>\n",
   "      <button class=\"secondary\" onclick=\"asis_excel(this)\">📥 Exportar Excel</button>\n      <button class=\"secondary\" onclick=\"asis_excelPeriodo(this, 'semana')\" title=\"La semana (lunes a domingo) de la fecha 'Desde', día por día de todos\">📅 Excel por semana</button>\n      <button class=\"secondary\" onclick=\"asis_excelPeriodo(this, 'mes')\" title=\"El mes de la fecha 'Desde', día por día de todos, con totales por semana\">📆 Excel por mes</button>\n      <button class=\"secondary\" onclick=\"document.getElementById('asis_archivo').click()\">📄 Importar archivo de BioTime</button>\n"
  ],
  [
   "    try {\n      const r = await fetch(`${API}/api/rh/asistencia/excel?desde=${ASIS.datos.desde}&hasta=${ASIS.datos.hasta}${asis_queryVista()}`, { headers: headers(false) });\n      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'No se pudo generar el Excel');\n      const url = URL.createObjectURL(await r.blob());\n      const a = document.createElement('a');\n      a.href = url; a.download = `asistencia_${ASIS.datos.desde}_${ASIS.datos.hasta}.xlsx`; a.click();\n      setTimeout(() => URL.revokeObjectURL(url), 2000);\n    } catch (e) { alert(e.message); }\n  });\n}\n\nfunction asis_importar(input) {\n",
   "    try {\n      const r = await fetch(`${API}/api/rh/asistencia/excel?desde=${ASIS.datos.desde}&hasta=${ASIS.datos.hasta}${asis_queryVista()}`, { headers: headers(false) });\n      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'No se pudo generar el Excel');\n      const url = URL.createObjectURL(await r.blob());\n      const a = document.createElement('a');\n      a.href = url; a.download = `asistencia_${ASIS.datos.desde}_${ASIS.datos.hasta}.xlsx`; a.click();\n      setTimeout(() => URL.revokeObjectURL(url), 2000);\n    } catch (e) { alert(e.message); }\n  });\n}\n\nasync function asis_excelPeriodo(btn, por) {\n  const ref = (document.getElementById('asis_desde') || {}).value || ASIS.datos.desde;\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      const r = await fetch(`${API}/api/rh/asistencia/excel?por=${por}&desde=${ref}${asis_queryVista()}`, { headers: headers(false) });\n      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'No se pudo generar el Excel');\n      const nombre = ((r.headers.get('Content-Disposition') || '').match(/filename=([^;]+)/) || [])[1] || `asistencia_${por}_${ref}.xlsx`;\n      const url = URL.createObjectURL(await r.blob());\n      const a = document.createElement('a');\n      a.href = url; a.download = nombre; a.click();\n      setTimeout(() => URL.revokeObjectURL(url), 2000);\n    } catch (e) { alert(e.message); }\n  });\n}\n\nfunction asis_importar(input) {\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_asistencia_excel_semana_mes.py")
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
