# -*- coding: utf-8 -*-
"""
Checadores ZKTeco conectados DIRECTO a la app por ADMS (Conf. Srvr. de Nube),
sin PC ni BioTime: rutas /iclock/cdata, /iclock/getrequest, /iclock/devicecmd.
RH -> Asistencia -> Conexion de los checadores: alta por numero de serie.
REQUIERE haber corrido antes fix_microsip_lote_serie.py.
Toca: backend/app.py, backend/db.py, backend/asistencia.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_checador_adms.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return {\"recibidas\": len(payload.checadas), \"validas\": len(checadas), \"nuevas\": nuevas}\n\n\n@app.post(\"/api/rh/checadas/importar\")\ndef api_checadas_importar(payload: ImportarChecadasIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    if len(payload.archivo) > 20_000_000:\n",
   "    return {\"recibidas\": len(payload.checadas), \"validas\": len(checadas), \"nuevas\": nuevas}\n\n\n# ---- Checadores ZKTeco directo por ADMS (\"Conf. Srvr. de Nube\"), sin PC ----\n# El checador se configura con: Modo ADMS, dominio = esta app, puerto 443, HTTPS.\n# Se identifica por su número de serie (SN); RH lo da de alta en Asistencia.\n\ndef _texto_plano(t, status=200):\n    return Response(content=t, media_type=\"text/plain\", status_code=status)\n\n\ndef _ip_cliente(request: Request):\n    return (request.headers.get(\"x-forwarded-for\") or (request.client.host if request.client else \"\") or \"\").split(\",\")[0].strip()\n\n\n@app.api_route(\"/iclock/cdata\", methods=[\"GET\", \"POST\"])\n@app.api_route(\"/iclock/cdata.aspx\", methods=[\"GET\", \"POST\"])\nasync def adms_cdata(request: Request):\n    q = request.query_params\n    sn = (q.get(\"SN\") or q.get(\"sn\") or \"\").strip().upper()\n    if not sn:\n        return _texto_plano(\"ERROR: falta SN\", 400)\n    if request.method == \"GET\":\n        info = \"&\".join(f\"{k}={v}\" for k, v in q.items() if k.lower() in (\"options\", \"pushver\", \"language\", \"pushcommkey\"))\n        db.conexion_checador_adms(sn, _ip_cliente(request), info or None)\n        # Respuesta de arranque (handshake). Pide todas las checadas que no haya mandado.\n        return _texto_plano(\"\\n\".join([\n            f\"GET OPTION FROM: {sn}\", \"ATTLOGStamp=None\", \"OPERLOGStamp=9999\", \"ATTPHOTOStamp=None\",\n            \"ErrorDelay=30\", \"Delay=10\", \"TransTimes=00:00;14:05\", \"TransInterval=1\",\n            \"TransFlag=TransData AttLog\", \"TimeZone=-6\", \"Realtime=1\", \"Encrypt=None\", \"\"]))\n    cuerpo = (await request.body()).decode(\"utf-8\", \"replace\")\n    tabla = (q.get(\"table\") or \"\").upper()\n    chk = db.conexion_checador_adms(sn, _ip_cliente(request))\n    if tabla != \"ATTLOG\":\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.\n        return _texto_plano(\"ERROR: checador no registrado\", 503)\n    checadas, _malos = asistencia.leer_attlog(cuerpo, chk.get(\"nombre\") or sn, chk.get(\"sucursal\"))\n    nuevas = db.guardar_checadas(chk[\"empresa_id\"], checadas, \"adms\", sn)\n    if checadas:\n        db.sumar_checadas_adms(sn, nuevas, max(c[\"fecha_hora\"] for c in checadas).isoformat(timespec=\"seconds\"))\n        db.marcar_sync_checador(chk[\"empresa_id\"], f\"{chk.get('nombre') or sn} (directo)\")\n    return _texto_plano(f\"OK: {len(checadas)}\")\n\n\n@app.get(\"/iclock/getrequest\")\n@app.get(\"/iclock/getrequest.aspx\")\ndef adms_getrequest(request: Request, SN: Optional[str] = None):\n    if SN:\n        db.conexion_checador_adms(SN, _ip_cliente(request))\n    return _texto_plano(\"OK\")\n\n\n@app.api_route(\"/iclock/devicecmd\", methods=[\"GET\", \"POST\"])\n@app.api_route(\"/iclock/devicecmd.aspx\", methods=[\"GET\", \"POST\"])\n@app.get(\"/iclock/ping\")\n@app.get(\"/iclock/test\")\ndef adms_ok():\n    return _texto_plano(\"OK\")\n\n\nclass ChecadorAdmsIn(BaseModel):\n    sn: str = Field(min_length=4, max_length=40)\n    nombre: Optional[str] = Field(default=None, max_length=80)\n    sucursal: Optional[str] = Field(default=None, max_length=80)\n    activo: bool = True\n\n\n@app.get(\"/api/rh/checadores\")\ndef api_checadores_adms(usuario: dict = Depends(requiere_datos_empleado_rh)):\n    return db.listar_checadores_adms(usuario[\"empresa_id\"])\n\n\n@app.post(\"/api/rh/checadores\")\ndef api_guardar_checador_adms(payload: ChecadorAdmsIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    try:\n        return db.guardar_checador_adms(usuario[\"empresa_id\"], payload.sn, _limpio(payload.nombre), _limpio(payload.sucursal), payload.activo)\n    except ValueError as e:\n        raise HTTPException(status_code=400, detail=str(e))\n\n\n@app.delete(\"/api/rh/checadores/{checador_id}\")\ndef api_quitar_checador_adms(checador_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    if not db.quitar_checador_adms(usuario[\"empresa_id\"], checador_id):\n        raise HTTPException(status_code=404, detail=\"Checador no encontrado\")\n    return {\"ok\": True}\n\n\n@app.post(\"/api/rh/checadas/importar\")\ndef api_checadas_importar(payload: ImportarChecadasIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    if len(payload.archivo) > 20_000_000:\n"
  ]
 ],
 "backend/db.py": [
  [
   "            UNIQUE (empresa_id, codigo_empleado, fecha_hora)\n        );\n        CREATE INDEX IF NOT EXISTS idx_rh_checadas_fecha ON rh_checadas(empresa_id, fecha_hora);\n        CREATE TABLE IF NOT EXISTS rh_horarios (\n            usuario_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n",
   "            UNIQUE (empresa_id, codigo_empleado, fecha_hora)\n        );\n        CREATE INDEX IF NOT EXISTS idx_rh_checadas_fecha ON rh_checadas(empresa_id, fecha_hora);\n        -- Checadores ZKTeco conectados directo por ADMS (sin PC en medio).\n        -- empresa_id NULL = se conectó pero nadie lo ha vinculado.\n        CREATE TABLE IF NOT EXISTS rh_checadores (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER REFERENCES empresas(id),\n            sn TEXT NOT NULL UNIQUE,\n            nombre TEXT,\n            sucursal TEXT,\n            activo BOOLEAN NOT NULL DEFAULT TRUE,\n            ultima_conexion TEXT,\n            ultima_ip TEXT,\n            ultima_checada TEXT,\n            total_checadas INTEGER NOT NULL DEFAULT 0,\n            info TEXT,\n            creado_en TEXT NOT NULL\n        );\n        CREATE TABLE IF NOT EXISTS rh_horarios (\n            usuario_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n"
  ],
  [
   "    return nuevas\n\n\ndef marcar_sync_checador(empresa_id, equipo):\n    conn = get_connection()\n    cur = conn.cursor()\n",
   "    return nuevas\n\n\ndef checador_adms(sn):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"SELECT * FROM rh_checadores WHERE sn = %s\", ((sn or \"\").strip().upper(),))\n    r = cur.fetchone()\n    cur.close(); conn.close()\n    return dict(r) if r else None\n\n\ndef conexion_checador_adms(sn, ip, info=None):\n    \"\"\"Registra que el checador se conectó (lo crea sin empresa si es nuevo).\"\"\"\n    sn = (sn or \"\").strip().upper()[:40]\n    if not sn:\n        return None\n    ts = ahora().isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"\"\"INSERT INTO rh_checadores (sn, ultima_conexion, ultima_ip, info, creado_en) VALUES (%s, %s, %s, %s, %s)\n           ON CONFLICT (sn) DO UPDATE SET ultima_conexion = EXCLUDED.ultima_conexion, ultima_ip = EXCLUDED.ultima_ip,\n             info = COALESCE(EXCLUDED.info, rh_checadores.info)\n           RETURNING *\"\"\",\n        (sn, ts, (ip or \"\")[:60] or None, (info or \"\")[:500] or None, ts))\n    r = dict(cur.fetchone())\n    conn.commit()\n    cur.close(); conn.close()\n    return r\n\n\ndef sumar_checadas_adms(sn, nuevas, ultima):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"UPDATE rh_checadores SET total_checadas = total_checadas + %s,\n                   ultima_checada = GREATEST(COALESCE(ultima_checada, ''), %s) WHERE sn = %s\"\"\",\n                (nuevas, ultima or \"\", sn))\n    conn.commit()\n    cur.close(); conn.close()\n\n\ndef listar_checadores_adms(empresa_id):\n    \"\"\"Los de la empresa y los que se conectaron sin vincular (últimos 30 días).\"\"\"\n    limite = (ahora() - timedelta(days=30)).isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"SELECT id, empresa_id, sn, nombre, sucursal, activo, ultima_conexion, ultima_ip, ultima_checada, total_checadas, creado_en\n                   FROM rh_checadores WHERE empresa_id = %s OR (empresa_id IS NULL AND ultima_conexion >= %s)\n                   ORDER BY empresa_id NULLS FIRST, sucursal, sn\"\"\", (empresa_id, limite))\n    filas = [dict(r) for r in cur.fetchall()]\n    cur.close(); conn.close()\n    return filas\n\n\ndef guardar_checador_adms(empresa_id, sn, nombre, sucursal, activo=True):\n    \"\"\"Alta o vinculación de un checador a la empresa. Error si ya es de otra.\"\"\"\n    sn = (sn or \"\").strip().upper()[:40]\n    actual = checador_adms(sn)\n    if actual and actual.get(\"empresa_id\") not in (None, empresa_id):\n        raise ValueError(\"Ese número de serie ya está dado de alta en otra empresa.\")\n    ts = ahora().isoformat(timespec=\"seconds\")\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        \"\"\"INSERT INTO rh_checadores (empresa_id, sn, nombre, sucursal, activo, creado_en) VALUES (%s, %s, %s, %s, %s, %s)\n           ON CONFLICT (sn) DO UPDATE SET empresa_id = EXCLUDED.empresa_id, nombre = EXCLUDED.nombre,\n             sucursal = EXCLUDED.sucursal, activo = EXCLUDED.activo\n           RETURNING *\"\"\",\n        (empresa_id, sn, nombre, sucursal, activo, ts))\n    r = dict(cur.fetchone())\n    conn.commit()\n    cur.close(); conn.close()\n    return r\n\n\ndef quitar_checador_adms(empresa_id, checador_id):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"UPDATE rh_checadores SET empresa_id = NULL, activo = TRUE WHERE id = %s AND empresa_id = %s\", (checador_id, empresa_id))\n    n = cur.rowcount\n    conn.commit()\n    cur.close(); conn.close()\n    return n\n\n\ndef marcar_sync_checador(empresa_id, equipo):\n    conn = get_connection()\n    cur = conn.cursor()\n"
  ]
 ],
 "backend/asistencia.py": [
  [
   "        raise ValueError(\"No encontré las columnas del reporte (se necesitan al menos el número de empleado y la fecha/hora de la checada). \"\n                         \"En BioTime usa Asistencia → Transacciones → Exportar.\")\n    return checadas\n\n\ndef checada_de_api(t: dict):\n",
   "        raise ValueError(\"No encontré las columnas del reporte (se necesitan al menos el número de empleado y la fecha/hora de la checada). \"\n                         \"En BioTime usa Asistencia → Transacciones → Exportar.\")\n    return checadas\n\n\n# Estados del checador ZKTeco (columna 3 del ATTLOG del protocolo ADMS).\nESTADOS_ADMS = {\"0\": \"Entrada\", \"1\": \"Salida\", \"2\": \"Salida descanso\", \"3\": \"Entrada descanso\",\n                \"4\": \"Entrada T.E.\", \"5\": \"Salida T.E.\"}\n\n\ndef leer_attlog(texto: str, dispositivo=None, area=None):\n    \"\"\"Renglones ATTLOG que manda el checador por ADMS:\n    PIN<TAB>AAAA-MM-DD HH:MM:SS<TAB>estado<TAB>verificación<TAB>...\n    Regresa (checadas, renglones_malos).\"\"\"\n    checadas, malos = [], 0\n    for linea in (texto or \"\").replace(\"\\r\", \"\").split(\"\\n\"):\n        if not linea.strip():\n            continue\n        partes = linea.split(\"\\t\")\n        if len(partes) < 2:\n            partes = linea.split()\n            if len(partes) >= 3:\n                partes = [partes[0], partes[1] + \" \" + partes[2]] + partes[3:]\n        codigo = normalizar_codigo(partes[0]) if partes else \"\"\n        try:\n            fh = datetime.strptime(partes[1].strip()[:19], \"%Y-%m-%d %H:%M:%S\")\n        except (ValueError, IndexError):\n            fh = None\n        if not codigo or not fh:\n            malos += 1\n            continue\n        estado = partes[2].strip() if len(partes) > 2 else \"\"\n        checadas.append({\"codigo\": codigo, \"nombre\": None, \"fecha_hora\": fh,\n                         \"tipo\": ESTADOS_ADMS.get(estado, f\"Estado {estado}\" if estado else None),\n                         \"dispositivo\": dispositivo, \"area\": area})\n    return checadas, malos\n\n\ndef checada_de_api(t: dict):\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  }\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>🔌 Conexión con BioTime</h2>\n    <p style=\"font-size:13px;\">Última vez que llegaron checadas: <b>${asis_hace(c.ultima_sync)}</b>${c.ultimo_equipo ? ` desde <b>${escapeHtml(c.ultimo_equipo)}</b>` : ''}.</p>\n    <ol style=\"font-size:13px; line-height:1.6; padding-left:18px;\">\n      <li>Descarga el programa y cópialo a la PC donde está <b>BioTime Pro</b> (por ejemplo en <code>C:\\\\biotime_sync\\\\</code>). Si cada sucursal tiene su propio BioTime, se instala en cada PC.</li>\n      <li>Ábrelo con el Bloc de notas y escribe arriba el <b>usuario y contraseña de BioTime</b> y la dirección con la que entras a BioTime en esa PC (ej. <code>http://127.0.0.1:8081</code>).</li>\n",
   "  }\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>🔌 Conexión de los checadores</h2>\n    <p style=\"font-size:13px;\">Última vez que llegaron checadas: <b>${asis_hace(c.ultima_sync)}</b>${c.ultimo_equipo ? ` desde <b>${escapeHtml(c.ultimo_equipo)}</b>` : ''}.</p>\n    <div id=\"asis_adms\" class=\"cv-caja\" style=\"margin:10px 0 16px;\"><p style=\"font-size:12px; color:var(--muted);\">Cargando checadores…</p></div>\n    <h3 style=\"margin:14px 0 6px;\">Opción con PC (BioTime)</h3>\n    <ol style=\"font-size:13px; line-height:1.6; padding-left:18px;\">\n      <li>Descarga el programa y cópialo a la PC donde está <b>BioTime Pro</b> (por ejemplo en <code>C:\\\\biotime_sync\\\\</code>). Si cada sucursal tiene su propio BioTime, se instala en cada PC.</li>\n      <li>Ábrelo con el Bloc de notas y escribe arriba el <b>usuario y contraseña de BioTime</b> y la dirección con la que entras a BioTime en esa PC (ej. <code>http://127.0.0.1:8081</code>).</li>\n"
  ],
  [
   "      <button class=\"secondary\" onclick=\"asis_nuevoToken(this)\">Generar clave nueva</button>\n    </div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:10px;\">El programa trae la clave secreta de tu empresa. \"Generar clave nueva\" invalida los programas ya instalados (hay que descargarlo e instalarlo otra vez).</p>`;\n}\n\nasync function asis_descargarPrograma(btn) {\n",
   "      <button class=\"secondary\" onclick=\"asis_nuevoToken(this)\">Generar clave nueva</button>\n    </div>\n    <p style=\"font-size:11px; color:var(--muted); margin-top:10px;\">El programa trae la clave secreta de tu empresa. \"Generar clave nueva\" invalida los programas ya instalados (hay que descargarlo e instalarlo otra vez).</p>`;\n  asis_cargarAdms();\n}\n\n// ---- Checadores conectados directo (ADMS), sin PC ----\nasync function asis_cargarAdms() {\n  const caja = document.getElementById('asis_adms');\n  if (!caja) return;\n  let lista = [];\n  try { lista = await api('/api/rh/checadores'); } catch (e) { caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; return; }\n  const host = location.host;\n  const mios = lista.filter(x => x.empresa_id), sinVincular = lista.filter(x => !x.empresa_id);\n  const fila = x => `<tr>\n      <td><b>${escapeHtml(x.sn)}</b></td>\n      <td><input id=\"adms_nom_${x.id}\" value=\"${escapeHtml(x.nombre || '')}\" placeholder=\"ej. Checador Dentigo\" style=\"font-size:12px;\" /></td>\n      <td><input id=\"adms_suc_${x.id}\" value=\"${escapeHtml(x.sucursal || '')}\" placeholder=\"Sucursal\" style=\"font-size:12px;\" /></td>\n      <td style=\"font-size:12px;\">${x.ultima_conexion ? asis_hace(x.ultima_conexion) : '<span style=\"color:var(--muted);\">nunca</span>'}</td>\n      <td style=\"font-size:12px;\">${x.ultima_checada ? escapeHtml(x.ultima_checada.replace('T', ' ').slice(0, 16)) : '—'} <span style=\"color:var(--muted);\">(${x.total_checadas || 0})</span></td>\n      <td style=\"white-space:nowrap;\">\n        <button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_guardarAdms('${escapeHtml(x.sn)}', ${x.id}, this)\">${x.empresa_id ? 'Guardar' : 'Vincular'}</button>\n        ${x.empresa_id ? `<button class=\"secondary\" style=\"font-size:11px;\" onclick=\"asis_quitarAdms(${x.id}, this)\">Quitar</button>` : ''}\n      </td></tr>`;\n  caja.innerHTML = `\n    <h3 style=\"margin:0 0 6px;\">📡 Conexión directa (sin PC)</h3>\n    <p style=\"font-size:12px; margin:0 0 6px;\">En el checador: <b>Menú → Red → Conf. Srvr. de Nube</b>:\n      Modo de servidor <b>ADMS</b> · Habilitar nombre de dominio <b>Sí</b> · Dirección del servidor <code>${escapeHtml(host)}</code> ·\n      Puerto <b>443</b> · HTTPS <b>Sí</b> · Proxy <b>No</b>. Reinícialo. Las checadas llegan al momento, sin BioTime ni PC.</p>\n    <p style=\"font-size:11px; color:var(--muted); margin:0 0 8px;\">El checador solo manda a un servidor: al apuntarlo aquí, BioTime deja de recibir sus checadas.\n      Las huellas y caras se quedan en el checador. El número de empleado del checador debe ser igual al del usuario. Revisa que la hora del checador esté bien.</p>\n    <table class=\"users\" style=\"font-size:12px;\">\n      <thead><tr><th>No. de serie</th><th>Nombre</th><th>Sucursal</th><th>Última conexión</th><th>Última checada (total)</th><th></th></tr></thead>\n      <tbody>${mios.map(fila).join('') || '<tr><td colspan=\"6\" class=\"empty-col\">— ningún checador dado de alta —</td></tr>'}</tbody>\n    </table>\n    ${sinVincular.length ? `<p style=\"font-size:12px; margin:10px 0 4px; color:#e8a33d;\"><b>Se conectaron y falta vincularlos</b> (mientras tanto el checador guarda sus checadas y las vuelve a mandar):</p>\n      <table class=\"users\" style=\"font-size:12px;\"><tbody>${sinVincular.map(fila).join('')}</tbody></table>` : ''}\n    <div style=\"display:flex; gap:6px; align-items:end; flex-wrap:wrap; margin-top:10px;\">\n      <div class=\"field\" style=\"margin:0; flex:1;\"><label>No. de serie</label><input id=\"adms_nuevo_sn\" placeholder=\"ej. TFEE243400091\" /></div>\n      <div class=\"field\" style=\"margin:0; flex:1;\"><label>Nombre</label><input id=\"adms_nuevo_nom\" placeholder=\"ej. Checador Matriz\" /></div>\n      <div class=\"field\" style=\"margin:0; flex:1;\"><label>Sucursal</label><input id=\"adms_nuevo_suc\" /></div>\n      <button class=\"primary\" onclick=\"asis_guardarAdms(null, null, this)\">+ Dar de alta</button>\n      <button class=\"secondary\" onclick=\"asis_cargarAdms()\">⟳</button>\n    </div>`;\n}\n\nasync function asis_guardarAdms(sn, id, btn) {\n  const v = k => (document.getElementById(k) || {}).value || '';\n  const datos = id ? { sn, nombre: v(`adms_nom_${id}`).trim() || null, sucursal: v(`adms_suc_${id}`).trim() || null }\n                   : { sn: v('adms_nuevo_sn').trim().toUpperCase(), nombre: v('adms_nuevo_nom').trim() || null, sucursal: v('adms_nuevo_suc').trim() || null };\n  if (!datos.sn) { alert('Escribe el número de serie (Menú → Información del equipo).'); return; }\n  await conBloqueoDeBoton(btn, async () => {\n    try { await api('/api/rh/checadores', { method: 'POST', body: JSON.stringify(datos) }); await asis_cargarAdms(); }\n    catch (e) { alert(e.message); }\n  });\n}\n\nasync function asis_quitarAdms(id, btn) {\n  if (!confirm('¿Quitar este checador? Dejará de recibir sus checadas (las que ya llegaron se quedan).')) return;\n  await conBloqueoDeBoton(btn, async () => {\n    try { await api(`/api/rh/checadores/${id}`, { method: 'DELETE' }); await asis_cargarAdms(); }\n    catch (e) { alert(e.message); }\n  });\n}\n\nasync function asis_descargarPrograma(btn) {\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checador_adms.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "/api/microsip/lote-serie-faltante" not in f.read():
            print("Primero corre fix_microsip_lote_serie.py (y los anteriores), y luego este.")
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
