# -*- coding: utf-8 -*-
"""
Administrar -> Microsip -> "Articulos que piden lote/serie y no lo tienen":
articulos con seguimiento por lote o serie cuya existencia en un almacen no
tiene lote/serie asignado. Consulta en pantalla y Excel (clave, nombre,
sucursal, cuantos hay, con y sin lote/serie). Solo lectura.
REQUIERE haber corrido antes fix_microsip_usuarios.py.
Toca: backend/app.py, frontend/index.html; nuevo: backend/microsip_lotes.py
Se puede correr varias veces.  Correr con:  py -3 fix_microsip_lote_serie.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    import microsip\n    import microsip_escritura\n    import microsip_usuarios\n    import microsip_vacaciones\n    MICROSIP_DISPONIBLE = True\nexcept ImportError:\n",
   "    import microsip\n    import microsip_escritura\n    import microsip_usuarios\n    import microsip_lotes\n    import microsip_vacaciones\n    MICROSIP_DISPONIBLE = True\nexcept ImportError:\n"
  ],
  [
   "    return datos\n\n\nclass LeerQrIn(BaseModel):\n    texto: str = Field(min_length=10, max_length=2000)\n\n",
   "    return datos\n\n\n@app.get(\"/api/microsip/lote-serie-faltante\")\ndef api_lote_serie_faltante(usuario: dict = Depends(requiere_admin_completo)):\n    \"\"\"Artículos con seguimiento por lote/serie cuya existencia no tiene lote/serie asignado, por almacén.\"\"\"\n    _requiere_microsip_disponible()\n    config = db.obtener_config_microsip(usuario[\"empresa_id\"])\n    if not config or not config.get(\"microsip_host\"):\n        raise HTTPException(status_code=400, detail=\"Microsip no está configurado todavía.\")\n    try:\n        return microsip_lotes.articulos_sin_lote_serie(config)\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"No se pudo consultar Microsip: {e}\")\n\n\nclass LeerQrIn(BaseModel):\n    texto: str = Field(min_length=10, max_length=2000)\n\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    <div id=\"ms_lab\" style=\"margin-top:22px;\"></div>\n    <div id=\"ms_vac\" style=\"margin-top:22px;\"></div>\n    <div id=\"ms_usr\" style=\"margin-top:22px;\"></div>\n  `;\n  abrirModal(true);\n  if (config.microsip_host) { ms_cargarEscritura(); ms_cargarLab(); ms_cargarVac(); ms_renderUsr(); }\n}\n\n// ---- Usuarios de Microsip: quién está activo, su rol, empresas y derechos (solo lectura) ----\n",
   "    <div id=\"ms_lab\" style=\"margin-top:22px;\"></div>\n    <div id=\"ms_vac\" style=\"margin-top:22px;\"></div>\n    <div id=\"ms_usr\" style=\"margin-top:22px;\"></div>\n    <div id=\"ms_lote\" style=\"margin-top:22px;\"></div>\n  `;\n  abrirModal(true);\n  if (config.microsip_host) { ms_cargarEscritura(); ms_cargarLab(); ms_cargarVac(); ms_renderUsr(); ms_renderLote(); }\n}\n\n// ---- Artículos que piden lote/serie y no lo tienen asignado ----\nlet MS_LOTE = null;\nfunction ms_renderLote() {\n  const caja = document.getElementById('ms_lote');\n  if (!caja) return;\n  caja.innerHTML = `\n    <h3 style=\"margin:0 0 6px;\">📦 Artículos que piden lote/serie y no lo tienen</h3>\n    <p style=\"font-size:12px; color:var(--muted); margin:0 0 10px;\">\n      Artículos con seguimiento por <b>lote</b> o <b>serie</b> en Microsip cuya existencia en un almacén no tiene lote/serie asignado\n      (existencia del almacén menos la que sí tiene lote/serie). Solo lectura.\n    </p>\n    <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n      <button class=\"primary\" style=\"flex:1;\" onclick=\"ms_consultarLote(this)\">Consultar</button>\n      <button class=\"secondary\" style=\"flex:1;\" onclick=\"ms_excelLote()\">⬇️ Descargar Excel</button>\n    </div>\n    <div id=\"ms_lote_resultado\"></div>`;\n}\nasync function ms_consultarLote(btn) {\n  const caja = document.getElementById('ms_lote_resultado');\n  caja.innerHTML = '<p style=\"font-size:12px; color:var(--muted);\">⏳ Revisando inventario en Microsip…</p>';\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      MS_LOTE = await api('/api/microsip/lote-serie-faltante');\n      const f = MS_LOTE.filas || [];\n      const piezas = f.reduce((t, x) => t + Number(x.sin_lote_serie || 0), 0);\n      const porSuc = {};\n      f.forEach(x => { porSuc[x.sucursal] = (porSuc[x.sucursal] || 0) + 1; });\n      caja.innerHTML = `<div class=\"cv-caja\" style=\"margin-top:10px; font-size:13px;\">\n        ${MS_LOTE.aviso ? `<div class=\"error-msg\" style=\"margin-bottom:6px;\">${escapeHtml(MS_LOTE.aviso)}</div>` : ''}\n        <p><b>${f.length}</b> renglones (artículo × sucursal) · <b>${piezas.toLocaleString('es-MX')}</b> piezas sin lote/serie ·\n          ${MS_LOTE.articulos_con_seguimiento} artículos piden lote/serie en total.</p>\n        <p style=\"font-size:12px; color:var(--muted);\">Por sucursal: ${Object.entries(porSuc).map(([k, n]) => `${escapeHtml(k)}: ${n}`).join(' · ') || '—'}\n          · Columna de seguimiento: ${escapeHtml(MS_LOTE.columna_seguimiento)} (${Object.entries(MS_LOTE.valores_seguimiento || {}).map(([k, n]) => `${escapeHtml(k || 'vacío')}=${n}`).join(', ')})</p>\n        <div style=\"overflow-x:auto; max-height:420px;\"><table class=\"users\" style=\"font-size:12px;\">\n          <thead><tr><th>Clave</th><th>Artículo</th><th>Sucursal</th><th>Seguimiento</th><th>Existencia</th><th>Con lote/serie</th><th>Sin lote/serie</th></tr></thead>\n          <tbody>${f.slice(0, 300).map(x => `<tr><td>${escapeHtml(x.clave)}</td><td>${escapeHtml(x.nombre)}</td><td>${escapeHtml(x.sucursal)}</td>\n            <td>${escapeHtml(x.seguimiento)}</td><td>${x.existencia}</td><td>${x.con_lote_serie}</td><td><b>${x.sin_lote_serie}</b></td></tr>`).join('')\n            || '<tr><td colspan=\"7\" class=\"empty-col\">— todo lo que pide lote/serie lo tiene asignado —</td></tr>'}</tbody></table></div>\n        ${f.length > 300 ? `<p style=\"font-size:11px; color:var(--muted);\">Se muestran 300; el Excel trae los ${f.length}.</p>` : ''}</div>`;\n    } catch (e) { caja.innerHTML = `<div class=\"error-msg\">${escapeHtml(e.message)}</div>`; }\n  });\n}\nasync function ms_excelLote() {\n  if (!MS_LOTE) { await ms_consultarLote(document.querySelector('#ms_lote button.primary')); }\n  if (!MS_LOTE) return;\n  exportarArticulosExcel(MS_LOTE.filas, [\n    { header: 'Clave producto', campo: 'clave' },\n    { header: 'Nombre del artículo', campo: 'nombre' },\n    { header: 'Sucursal', campo: 'sucursal' },\n    { header: 'Cuántos hay (existencia)', campo: 'existencia' },\n    { header: 'Con lote/serie', campo: 'con_lote_serie' },\n    { header: 'Sin lote/serie', campo: 'sin_lote_serie' },\n    { header: 'Seguimiento', campo: 'seguimiento' },\n    { header: 'Estado', campo: 'estado' },\n  ], 'Sin lote o serie', 'articulos_sin_lote_serie');\n}\n\n// ---- Usuarios de Microsip: quién está activo, su rol, empresas y derechos (solo lectura) ----\n"
  ]
 ]
}

NUEVOS = {
 "backend/microsip_lotes.py": "\"\"\"\nArtículos que en Microsip piden lote o serie (seguimiento por lotes/series)\npero cuya existencia no tiene lote o serie asignado, por almacén.\n\nSolo lectura. Existencia del almacén = CAPAS_COSTOS activas (mismo criterio\nque Valor del inventario). Existencia con lote/serie = EXIS_DISCRETOS unido\ncon ARTICULOS_DISCRETOS. Lo que falta = existencia − con lote/serie.\n\nLos nombres de columnas se leen del catálogo de Firebird, para no depender de\nla versión de Microsip.\n\"\"\"\nimport microsip\n\nSIN_SEGUIMIENTO = {\"\", \"N\", \"NINGUNO\", \"0\"}\nNOMBRE_SEGUIMIENTO = {\"L\": \"Lote\", \"S\": \"Serie\"}\n\n\ndef _columnas(cur, tabla):\n    cur.execute(\"\"\"SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS\n                   WHERE RDB$RELATION_NAME = ? ORDER BY RDB$FIELD_POSITION\"\"\", (tabla,))\n    return [r[0] for r in cur.fetchall()]\n\n\ndef _por_lotes(cur, sql, ids):\n    salida = []\n    for i in range(0, len(ids), 400):\n        lote = ids[i:i + 400]\n        cur.execute(sql.format(\",\".join(\"?\" for _ in lote)), tuple(lote))\n        salida.extend(cur.fetchall())\n    return salida\n\n\ndef articulos_sin_lote_serie(config):\n    con = microsip._conectar(config)\n    try:\n        cur = con.cursor()\n        cols_art = _columnas(cur, \"ARTICULOS\")\n        col_seg = \"SEGUIMIENTO\" if \"SEGUIMIENTO\" in cols_art else next((c for c in cols_art if \"SEGUIM\" in c), None)\n        if not col_seg:\n            pistas = [c for c in cols_art if \"LOTE\" in c or \"SERIE\" in c or \"DISCRET\" in c]\n            raise RuntimeError(\"No encontré la columna de seguimiento en ARTICULOS. Columnas parecidas: \" + (\", \".join(pistas) or \"ninguna\"))\n\n        cur.execute(f'SELECT TRIM(\"{col_seg}\"), COUNT(*) FROM ARTICULOS GROUP BY 1')\n        valores = {(v or \"\"): n for v, n in cur.fetchall()}\n        cur.execute(f'SELECT ARTICULO_ID, TRIM(\"{col_seg}\") FROM ARTICULOS')\n        seguimiento = {aid: (v or \"\").upper() for aid, v in cur.fetchall() if (v or \"\").strip().upper() not in SIN_SEGUIMIENTO}\n\n        cur.execute(\"\"\"SELECT cc.ALMACEN_ID, cc.ARTICULO_ID, SUM(cc.EXISTENCIA) FROM CAPAS_COSTOS cc\n                       WHERE cc.CAPA_AGOTADA = 'N' GROUP BY cc.ALMACEN_ID, cc.ARTICULO_ID\"\"\")\n        existencia = {(a, art): float(e or 0) for a, art, e in cur.fetchall() if art in seguimiento}\n\n        # Existencia que sí tiene lote/serie.\n        con_discreto = {}\n        aviso = None\n        cur.execute(\"\"\"SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS\n                       WHERE RDB$RELATION_NAME IN ('ARTICULOS_DISCRETOS', 'EXIS_DISCRETOS')\"\"\")\n        tablas = {r[0] for r in cur.fetchall()}\n        if tablas == {\"ARTICULOS_DISCRETOS\", \"EXIS_DISCRETOS\"}:\n            ca, ce = _columnas(cur, \"ARTICULOS_DISCRETOS\"), _columnas(cur, \"EXIS_DISCRETOS\")\n            llave = next((c for c in ce if c.endswith(\"DISCRETO_ID\") and c in ca), None)\n            col_exis = \"EXISTENCIA\" if \"EXISTENCIA\" in ce else next((c for c in ce if \"EXIS\" in c and not c.endswith(\"_ID\")), None)\n            if llave and col_exis and \"ALMACEN_ID\" in ce and \"ARTICULO_ID\" in ca:\n                cur.execute(f'''SELECT e.ALMACEN_ID, d.ARTICULO_ID, SUM(e.\"{col_exis}\")\n                                FROM EXIS_DISCRETOS e JOIN ARTICULOS_DISCRETOS d ON d.\"{llave}\" = e.\"{llave}\"\n                                GROUP BY e.ALMACEN_ID, d.ARTICULO_ID''')\n                con_discreto = {(a, art): float(e or 0) for a, art, e in cur.fetchall()}\n            else:\n                aviso = f\"No pude unir EXIS_DISCRETOS ({', '.join(ce)}) con ARTICULOS_DISCRETOS ({', '.join(ca)}).\"\n        else:\n            aviso = \"Esta base no tiene las tablas ARTICULOS_DISCRETOS / EXIS_DISCRETOS; se toma toda la existencia como sin lote/serie.\"\n\n        filas = []\n        for (alm, art), exis in existencia.items():\n            con_ls = con_discreto.get((alm, art), 0.0)\n            falta = round(exis - con_ls, 4)\n            if exis > 0.0001 and falta > 0.0001:\n                filas.append({\"almacen_id\": alm, \"articulo_id\": art, \"existencia\": round(exis, 4),\n                              \"con_lote_serie\": round(con_ls, 4), \"sin_lote_serie\": falta,\n                              \"seguimiento\": NOMBRE_SEGUIMIENTO.get(seguimiento[art], seguimiento[art])})\n\n        ids = sorted({f[\"articulo_id\"] for f in filas})\n        nombres = {a: (n or \"\").strip() for a, n in _por_lotes(cur, \"SELECT ARTICULO_ID, NOMBRE FROM ARTICULOS WHERE ARTICULO_ID IN ({})\", ids)}\n        claves = {}\n        for a, c in _por_lotes(cur, \"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS WHERE ARTICULO_ID IN ({})\", ids):\n            if a not in claves and c:\n                claves[a] = c.strip()\n        cur.execute(\"SELECT ALMACEN_ID, NOMBRE FROM ALMACENES\")\n        almacenes = {a: (n or \"\").strip() for a, n in cur.fetchall()}\n        for f in filas:\n            f[\"clave\"] = claves.get(f[\"articulo_id\"], \"\")\n            f[\"nombre\"] = nombres.get(f[\"articulo_id\"], \"\")\n            f[\"sucursal\"] = almacenes.get(f[\"almacen_id\"], f\"Almacén {f['almacen_id']}\")\n            f[\"estado\"] = \"Sin ningún lote/serie\" if f[\"con_lote_serie\"] <= 0.0001 else \"Le faltan\"\n        filas.sort(key=lambda f: (f[\"sucursal\"], f[\"nombre\"]))\n        return {\"columna_seguimiento\": col_seg, \"valores_seguimiento\": valores,\n                \"articulos_con_seguimiento\": len(seguimiento), \"aviso\": aviso, \"filas\": filas}\n    finally:\n        con.close()\n"
}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_microsip_lote_serie.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "/api/microsip/usuarios" not in f.read():
            print("Primero corre fix_microsip_usuarios.py (y los anteriores), y luego este.")
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
