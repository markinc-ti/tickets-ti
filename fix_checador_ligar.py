# -*- coding: utf-8 -*-
"""
Asistencia: ligar los numeros del checador a cada persona cuando no son
iguales a su numero de empleado (RH -> Asistencia -> "Ligar"), y el checador
manda los nombres de su gente (DATA QUERY USERINFO cada 12 h) para identificarlos.
REQUIERE haber corrido antes fix_checador_adms.py.
Toca: backend/app.py, backend/db.py, backend/asistencia.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_checador_ligar.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "def _reporte_asistencia(empresa_id, desde, hasta):\n    empleados = db.empleados_asistencia(empresa_id)\n    checadas = db.listar_checadas(empresa_id, desde, hasta)\n    for c in checadas:\n        c[\"codigo\"] = asistencia.normalizar_codigo(c[\"codigo\"])\n    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n    avisos = []\n    # Vacaciones aprobadas en Microsip (si la empresa lo tiene conectado)\n",
   "def _reporte_asistencia(empresa_id, desde, hasta):\n    empleados = db.empleados_asistencia(empresa_id)\n    checadas = db.listar_checadas(empresa_id, desde, hasta)\n    # Número en el checador distinto al número de empleado: se traduce con las equivalencias de RH.\n    ligados = db.codigos_checador(empresa_id)\n    equivalencias = {asistencia.normalizar_codigo(x[\"codigo\"]): asistencia.normalizar_codigo(x[\"numero_empleado\"])\n                     for x in ligados if (x.get(\"numero_empleado\") or \"\").strip()}\n    nombres_chk = db.nombres_checador(empresa_id)\n    for c in checadas:\n        c[\"codigo\"] = asistencia.normalizar_codigo(c[\"codigo\"])\n        if not c.get(\"nombre\") and nombres_chk.get(c[\"codigo\"]):\n            c[\"nombre\"] = nombres_chk[c[\"codigo\"]]\n        c[\"codigo\"] = equivalencias.get(c[\"codigo\"], c[\"codigo\"])\n    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n    avisos = []\n    # Vacaciones aprobadas en Microsip (si la empresa lo tiene conectado)\n"
  ],
  [
   "                                       _horario_default(empresa_id), desde, hasta, db.ahora().date(), justificaciones,\n                                       db.primera_checada(empresa_id))\n    reporte[\"avisos\"] = avisos\n    return reporte\n\n\n",
   "                                       _horario_default(empresa_id), desde, hasta, db.ahora().date(), justificaciones,\n                                       db.primera_checada(empresa_id))\n    reporte[\"avisos\"] = avisos\n    reporte[\"codigos_ligados\"] = ligados\n    return reporte\n\n\n"
  ],
  [
   "    tabla = (q.get(\"table\") or \"\").upper()\n    chk = db.conexion_checador_adms(sn, _ip_cliente(request))\n    if tabla != \"ATTLOG\":\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.\n",
   "    tabla = (q.get(\"table\") or \"\").upper()\n    chk = db.conexion_checador_adms(sn, _ip_cliente(request))\n    if tabla != \"ATTLOG\":\n        if chk and chk.get(\"empresa_id\") and tabla in (\"OPERLOG\", \"USERINFO\", \"USER\"):\n            db.guardar_personas_checador(chk[\"empresa_id\"], sn, asistencia.leer_personas_checador(cuerpo))\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.\n"
  ],
  [
   "def adms_getrequest(request: Request, SN: Optional[str] = None):\n    if SN:\n        db.conexion_checador_adms(SN, _ip_cliente(request))\n    return _texto_plano(\"OK\")\n\n\n",
   "def adms_getrequest(request: Request, SN: Optional[str] = None):\n    if SN:\n        db.conexion_checador_adms(SN, _ip_cliente(request))\n        # Cada 12 h se le piden al checador sus personas (número y nombre) para ayudar a ligarlas.\n        if db.pedir_usuarios_checador(SN.strip().upper()):\n            return _texto_plano(f\"C:{secrets.randbelow(90000000) + 10000000}:DATA QUERY USERINFO\")\n    return _texto_plano(\"OK\")\n\n\n@app.post(\"/iclock/querydata\")\n@app.post(\"/iclock/querydata.aspx\")\nasync def adms_querydata(request: Request):\n    sn = (request.query_params.get(\"SN\") or \"\").strip().upper()\n    chk = db.checador_adms(sn) if sn else None\n    if chk and chk.get(\"empresa_id\"):\n        cuerpo = (await request.body()).decode(\"utf-8\", \"replace\")\n        db.guardar_personas_checador(chk[\"empresa_id\"], sn, asistencia.leer_personas_checador(cuerpo))\n    return _texto_plano(\"OK\")\n\n\n"
  ],
  [
   "@app.get(\"/iclock/test\")\ndef adms_ok():\n    return _texto_plano(\"OK\")\n\n\nclass ChecadorAdmsIn(BaseModel):\n",
   "@app.get(\"/iclock/test\")\ndef adms_ok():\n    return _texto_plano(\"OK\")\n\n\nclass LigarCodigoIn(BaseModel):\n    codigo: str = Field(min_length=1, max_length=40)\n    usuario_id: int\n\n\n@app.get(\"/api/rh/asistencia/usuarios-ligables\")\ndef api_usuarios_ligables(usuario: dict = Depends(requiere_datos_empleado_rh)):\n    return db.usuarios_ligables_checador(usuario[\"empresa_id\"])\n\n\n@app.post(\"/api/rh/asistencia/ligar-codigo\")\ndef api_ligar_codigo(payload: LigarCodigoIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    try:\n        modo = db.ligar_codigo_checador(usuario[\"empresa_id\"], asistencia.normalizar_codigo(payload.codigo), payload.usuario_id)\n    except ValueError as e:\n        raise HTTPException(status_code=404, detail=str(e))\n    return {\"ok\": True, \"modo\": modo}\n\n\n@app.delete(\"/api/rh/asistencia/ligar-codigo/{codigo}\")\ndef api_desligar_codigo(codigo: str, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    db.desligar_codigo_checador(usuario[\"empresa_id\"], asistencia.normalizar_codigo(codigo))\n    return {\"ok\": True}\n\n\nclass ChecadorAdmsIn(BaseModel):\n"
  ]
 ],
 "backend/db.py": [
  [
   "            total_checadas INTEGER NOT NULL DEFAULT 0,\n            info TEXT,\n            creado_en TEXT NOT NULL\n        );\n        CREATE TABLE IF NOT EXISTS rh_horarios (\n            usuario_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,\n",
   "            total_checadas INTEGER NOT NULL DEFAULT 0,\n            info TEXT,\n            creado_en TEXT NOT NULL\n        );\n        ALTER TABLE rh_checadores ADD COLUMN IF NOT EXISTS usuarios_pedidos_en TEXT;\n        -- Número de la persona en el checador -> usuario (cuando no es igual a su número de empleado).\n        CREATE TABLE IF NOT EXISTS rh_codigos_checador (\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            codigo TEXT NOT NULL,\n            usuario_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n            creado_en TEXT NOT NULL,\n            PRIMARY KEY (empresa_id, codigo)\n        );\n        -- Nombres que trae cada checador para cada número (los manda el propio checador).\n        CREATE TABLE IF NOT EXISTS rh_checador_personas (\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            codigo TEXT NOT NULL,\n            nombre TEXT,\n            sn TEXT,\n            actualizado_en TEXT NOT NULL,\n            PRIMARY KEY (empresa_id, codigo)\n        );\n        CREATE TABLE IF NOT EXISTS rh_horarios (\n            usuario_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,\n"
  ],
  [
   "    return r\n\n\ndef quitar_checador_adms(empresa_id, checador_id):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return r\n\n\ndef pedir_usuarios_checador(sn, horas=12):\n    \"\"\"True si toca pedirle al checador su lista de personas (y lo marca).\"\"\"\n    limite = (ahora() - timedelta(hours=horas)).isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"UPDATE rh_checadores SET usuarios_pedidos_en = %s\n                   WHERE sn = %s AND empresa_id IS NOT NULL AND activo\n                     AND (usuarios_pedidos_en IS NULL OR usuarios_pedidos_en < %s)\"\"\",\n                (ahora().isoformat(timespec=\"seconds\"), sn, limite))\n    toca = cur.rowcount > 0\n    conn.commit()\n    cur.close(); conn.close()\n    return toca\n\n\ndef guardar_personas_checador(empresa_id, sn, personas):\n    \"\"\"personas: [(codigo, nombre)]\"\"\"\n    if not personas:\n        return 0\n    ts = ahora().isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    for codigo, nombre in personas:\n        cur.execute(\"\"\"INSERT INTO rh_checador_personas (empresa_id, codigo, nombre, sn, actualizado_en) VALUES (%s, %s, %s, %s, %s)\n                       ON CONFLICT (empresa_id, codigo) DO UPDATE SET nombre = COALESCE(EXCLUDED.nombre, rh_checador_personas.nombre),\n                         sn = EXCLUDED.sn, actualizado_en = EXCLUDED.actualizado_en\"\"\",\n                    (empresa_id, codigo[:40], (nombre or \"\")[:120] or None, sn, ts))\n    conn.commit()\n    cur.close(); conn.close()\n    return len(personas)\n\n\ndef nombres_checador(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT codigo, nombre FROM rh_checador_personas WHERE empresa_id = %s AND nombre IS NOT NULL\", (empresa_id,))\n    r = {x[\"codigo\"]: x[\"nombre\"] for x in cur.fetchall()}\n    cur.close(); conn.close()\n    return r\n\n\ndef codigos_checador(empresa_id):\n    \"\"\"[{codigo, usuario_id, nombre, numero_empleado}] — equivalencias número del checador -> usuario.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT c.codigo, c.usuario_id, u.nombre_completo AS nombre, u.numero_empleado\n                   FROM rh_codigos_checador c JOIN users u ON u.id = c.usuario_id\n                   WHERE c.empresa_id = %s ORDER BY c.codigo\"\"\", (empresa_id,))\n    r = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return r\n\n\ndef ligar_codigo_checador(empresa_id, codigo, usuario_id):\n    \"\"\"Si el usuario no tiene número de empleado, se le pone el del checador; si ya tiene, se guarda la equivalencia.\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT id, numero_empleado FROM users WHERE id = %s AND empresa_id = %s\", (usuario_id, empresa_id))\n    u = cur.fetchone()\n    if not u:\n        cur.close(); conn.close()\n        raise ValueError(\"Usuario no encontrado\")\n    if not (u[\"numero_empleado\"] or \"\").strip():\n        cur.execute(\"UPDATE users SET numero_empleado = %s WHERE id = %s\", (codigo, usuario_id))\n        cur.execute(\"DELETE FROM rh_codigos_checador WHERE empresa_id = %s AND codigo = %s\", (empresa_id, codigo))\n        modo = \"numero_empleado\"\n    else:\n        cur.execute(\"\"\"INSERT INTO rh_codigos_checador (empresa_id, codigo, usuario_id, creado_en) VALUES (%s, %s, %s, %s)\n                       ON CONFLICT (empresa_id, codigo) DO UPDATE SET usuario_id = EXCLUDED.usuario_id\"\"\",\n                    (empresa_id, codigo, usuario_id, ahora().isoformat(timespec=\"seconds\")))\n        modo = \"equivalencia\"\n    conn.commit()\n    cur.close(); conn.close()\n    return modo\n\n\ndef desligar_codigo_checador(empresa_id, codigo):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"DELETE FROM rh_codigos_checador WHERE empresa_id = %s AND codigo = %s\", (empresa_id, codigo))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef usuarios_ligables_checador(empresa_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT u.id, u.nombre_completo AS nombre, u.numero_empleado, s.nombre AS sucursal\n                   FROM users u LEFT JOIN sucursales_reparacion s ON s.id = u.sucursal_id\n                   WHERE u.empresa_id = %s AND u.activo = TRUE AND u.rol <> 'estudiante'\n                   ORDER BY u.nombre_completo\"\"\", (empresa_id,))\n    r = [dict(x) for x in cur.fetchall()]\n    cur.close(); conn.close()\n    return r\n\n\ndef quitar_checador_adms(empresa_id, checador_id):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "backend/asistencia.py": [
  [
   "                         \"tipo\": ESTADOS_ADMS.get(estado, f\"Estado {estado}\" if estado else None),\n                         \"dispositivo\": dispositivo, \"area\": area})\n    return checadas, malos\n\n\ndef checada_de_api(t: dict):\n",
   "                         \"tipo\": ESTADOS_ADMS.get(estado, f\"Estado {estado}\" if estado else None),\n                         \"dispositivo\": dispositivo, \"area\": area})\n    return checadas, malos\n\n\ndef leer_personas_checador(texto: str):\n    \"\"\"Personas que manda el checador (USERINFO/OPERLOG): renglones con PIN=... y Name=...\n    Regresa [(codigo, nombre)].\"\"\"\n    salida = []\n    for linea in (texto or \"\").replace(\"\\r\", \"\").split(\"\\n\"):\n        m = re.search(r\"(?i)(?:^|[\\s\\t&])pin=([^\\t&\\s]+)\", linea)\n        if not m:\n            continue\n        n = re.search(r\"(?i)(?:^|[\\t&])name=([^\\t&]*)\", linea)\n        nombre = (n.group(1).strip() if n else \"\") or None\n        salida.append((normalizar_codigo(m.group(1)), nombre))\n    return salida\n\n\ndef checada_de_api(t: dict):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <button class=\"secondary\" onclick=\"document.getElementById('asis_archivo').click()\">📄 Importar archivo de BioTime</button>\n      <input id=\"asis_archivo\" type=\"file\" accept=\".xlsx,.csv,.txt\" style=\"display:none;\" onchange=\"asis_importar(this)\" />\n      <button class=\"secondary\" onclick=\"asis_abrirHorarios()\">🕘 Horarios</button>\n      <button class=\"secondary\" onclick=\"asis_abrirConexion()\">🔌 Conexión BioTime</button>\n    </div>\n    <div style=\"font-size:12px; color:var(--muted); margin-bottom:10px;\">\n      Checadas automáticas desde BioTime: <b>${asis_hace(d.ultima_sync)}</b>${d.ultimo_equipo ? ` (${escapeHtml(d.ultimo_equipo)})` : ''}\n",
   "      <button class=\"secondary\" onclick=\"document.getElementById('asis_archivo').click()\">📄 Importar archivo de BioTime</button>\n      <input id=\"asis_archivo\" type=\"file\" accept=\".xlsx,.csv,.txt\" style=\"display:none;\" onchange=\"asis_importar(this)\" />\n      <button class=\"secondary\" onclick=\"asis_abrirHorarios()\">🕘 Horarios</button>\n      <button class=\"secondary\" onclick=\"asis_abrirConexion()\">🔌 Conexión checadores</button>\n    </div>\n    <div style=\"font-size:12px; color:var(--muted); margin-bottom:10px;\">\n      Checadas automáticas desde BioTime: <b>${asis_hace(d.ultima_sync)}</b>${d.ultimo_equipo ? ` (${escapeHtml(d.ultimo_equipo)})` : ''}\n"
  ],
  [
   "    <div id=\"asis_aviso\"></div>\n    ${(d.avisos || []).map(a => `<div style=\"font-size:12px; color:#e8a33d; margin-bottom:6px;\">⚠️ ${escapeHtml(a)}</div>`).join('')}\n    ${d.codigos_sin_empleado.length ? `\n      <div class=\"cv-aviso\" style=\"margin-bottom:10px; font-size:12px;\">⚠️ Hay checadas de ${d.codigos_sin_empleado.length} número(s) de empleado que no corresponden a ningún usuario activo:\n        ${d.codigos_sin_empleado.slice(0, 15).map(c => `<b>${escapeHtml(c.codigo)}</b>${c.nombre ? ` (${escapeHtml(c.nombre)})` : ''}`).join(', ')}${d.codigos_sin_empleado.length > 15 ? '…' : ''}.\n        Pon ese número en el campo <b>Número de empleado</b> del usuario (Administrar → Usuarios) para que se le cuenten.</div>` : ''}\n    <input placeholder=\"Buscar empleado o sucursal…\" value=\"${escapeHtml(ASIS.filtro)}\" oninput=\"ASIS.filtro=this.value; asis_pintarTabla()\" style=\"max-width:320px; margin-bottom:8px;\" />\n    <div id=\"asis_tabla\"></div>`;\n  asis_pintarTabla();\n}\n\nfunction asis_pintarTabla() {\n",
   "    <div id=\"asis_aviso\"></div>\n    ${(d.avisos || []).map(a => `<div style=\"font-size:12px; color:#e8a33d; margin-bottom:6px;\">⚠️ ${escapeHtml(a)}</div>`).join('')}\n    ${d.codigos_sin_empleado.length ? `\n      <div class=\"cv-aviso\" style=\"margin-bottom:10px; font-size:12px;\">⚠️ Hay checadas de <b>${d.codigos_sin_empleado.length}</b> número(s) del checador que no corresponden a ningún usuario.\n        Elige a qué persona pertenece cada número y toca <b>Ligar</b> (si la persona no tiene número de empleado, se le pone ese).\n        <div id=\"asis_ligar\" style=\"margin-top:8px;\"></div></div>` : ''}\n    ${(d.codigos_ligados || []).length ? `<details style=\"font-size:12px; margin-bottom:10px;\"><summary>🔗 Números del checador ligados a otra persona (${d.codigos_ligados.length})</summary>\n        ${d.codigos_ligados.map(x => `<div style=\"margin:3px 0;\">Checador <b>${escapeHtml(x.codigo)}</b> → ${escapeHtml(x.nombre)} (No. ${escapeHtml(x.numero_empleado || '—')})\n          <button class=\"secondary\" style=\"font-size:11px; padding:2px 8px;\" onclick=\"asis_desligar('${escapeHtml(x.codigo)}', this)\">Quitar</button></div>`).join('')}</details>` : ''}\n    <input placeholder=\"Buscar empleado o sucursal…\" value=\"${escapeHtml(ASIS.filtro)}\" oninput=\"ASIS.filtro=this.value; asis_pintarTabla()\" style=\"max-width:320px; margin-bottom:8px;\" />\n    <div id=\"asis_tabla\"></div>`;\n  asis_pintarTabla();\n  if (d.codigos_sin_empleado.length) asis_pintarLigar();\n}\n\nasync function asis_pintarLigar() {\n  const caja = document.getElementById('asis_ligar');\n  if (!caja) return;\n  if (!ASIS.usuarios) {\n    try { ASIS.usuarios = await api('/api/rh/asistencia/usuarios-ligables'); } catch (e) { caja.innerHTML = escapeHtml(e.message); return; }\n  }\n  const opciones = '<option value=\"\">— ¿De quién es? —</option>' + ASIS.usuarios.map(u =>\n    `<option value=\"${u.id}\">${escapeHtml(u.nombre)}${u.numero_empleado ? ` (No. ${escapeHtml(u.numero_empleado)})` : ''}${u.sucursal ? ` · ${escapeHtml(u.sucursal)}` : ''}</option>`).join('');\n  caja.innerHTML = ASIS.datos.codigos_sin_empleado.map(c => `\n    <div style=\"display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:4px 0;\">\n      <span style=\"min-width:200px;\">Checador <b>${escapeHtml(c.codigo)}</b>${c.nombre ? ` — ${escapeHtml(c.nombre)}` : ''} <span style=\"color:var(--muted);\">(${c.checadas} checadas)</span></span>\n      <select id=\"asis_lig_${escapeHtml(c.codigo)}\" style=\"max-width:340px; font-size:12px;\">${opciones}</select>\n      <button class=\"secondary\" style=\"font-size:11px; padding:3px 10px;\" onclick=\"asis_ligar('${escapeHtml(c.codigo)}', this)\">Ligar</button>\n    </div>`).join('');\n}\n\nasync function asis_ligar(codigo, btn) {\n  const uid = Number((document.getElementById(`asis_lig_${codigo}`) || {}).value || 0);\n  if (!uid) { alert('Elige a la persona.'); return; }\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      await api('/api/rh/asistencia/ligar-codigo', { method: 'POST', body: JSON.stringify({ codigo, usuario_id: uid }) });\n      ASIS.usuarios = null;\n      await renderAsistenciaRH();\n    } catch (e) { alert(e.message); }\n  });\n}\n\nasync function asis_desligar(codigo, btn) {\n  if (!confirm(`¿Quitar la equivalencia del número ${codigo} del checador?`)) return;\n  await conBloqueoDeBoton(btn, async () => {\n    try { await api(`/api/rh/asistencia/ligar-codigo/${encodeURIComponent(codigo)}`, { method: 'DELETE' }); await renderAsistenciaRH(); }\n    catch (e) { alert(e.message); }\n  });\n}\n\nfunction asis_pintarTabla() {\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_ligar.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "/iclock/cdata" not in f.read():
            print("Primero corre fix_checador_adms.py (y los anteriores), y luego este.")
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
