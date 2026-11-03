# -*- coding: utf-8 -*-
"""
INVENTARIO: EXCEL DE ARTICULOS DE MICROSIP SIN MARCA / PROVEEDOR
Boton "Sin marca / proveedor" junto al filtro de clasificador (tarjetas de
inventario del panel). Descarga un Excel con los articulos a los que les falta
el clasificador de MARCA y/o PROVEEDOR: clave, articulo, linea, estatus,
existencia, lo que tiene en cada clasificador y que le falta. Hoja de resumen.
Toca: backend/microsip.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_microsip_sin_marca_proveedor.py
"""
import os
import sys

ARCHIVOS = {
 "backend/microsip.py": [
  [
   "        tuple(valores_clasif_ids),\n    )\n    return {fila[0] for fila in cur.fetchall()}\n\n\ndef obtener_valor_inventario_por_almacen(config: dict, valores_clasif_ids: list = None):\n",
   "        tuple(valores_clasif_ids),\n    )\n    return {fila[0] for fila in cur.fetchall()}\n\n\ndef _columnas_tabla(cur, tabla):\n    cur.execute(\"SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME = ?\", (tabla,))\n    return {r[0] for r in cur.fetchall()}\n\n\ndef articulos_sin_clasificador(config: dict, palabras=(\"MARCA\", \"PROVEEDOR\")):\n    \"\"\"Artículos a los que les falta alguno de los clasificadores cuyo\n    nombre lleva MARCA o PROVEEDOR (ej. \"MARCA\", \"PROVEEDOR\" o uno solo\n    \"MARCA - PROVEEDOR\"). Regresa los clasificadores revisados y, por\n    artículo, el valor que tiene en cada uno ('' si no tiene), su clave,\n    línea, estatus y existencia total.\"\"\"\n    con = _conectar(config)\n    cur = con.cursor()\n    try:\n        cur.execute(\"SELECT CLASIFICADOR_ID, NOMBRE FROM CLASIFICADORES_CAT WHERE TIPO_OBJETO = 'A' ORDER BY NOMBRE\")\n        todos = [(cid, (nom or \"\").strip()) for cid, nom in cur.fetchall()]\n        clasif = [(cid, nom) for cid, nom in todos if any(p in nom.upper() for p in palabras)]\n        if not clasif:\n            raise ValueError(\"No hay clasificadores de artículos con MARCA o PROVEEDOR en el nombre. Los que hay: \"\n                             + (\", \".join(n for _, n in todos) or \"ninguno\"))\n        ids = [cid for cid, _ in clasif]\n        ph = \",\".join(\"?\" for _ in ids)\n        # valor que tiene cada artículo en cada clasificador revisado\n        cur.execute(f\"\"\"\n            SELECT e.ELEMENTO_ID, v.CLASIFICADOR_ID, v.VALOR\n            FROM ELEMENTOS_CAT_CLASIF e\n            JOIN CLASIFICADORES_CAT_VALORES v ON v.VALOR_CLASIF_ID = e.VALOR_CLASIF_ID\n            WHERE v.CLASIFICADOR_ID IN ({ph})\n        \"\"\", tuple(ids))\n        valores = {}\n        for aid, cid, valor in cur.fetchall():\n            valores.setdefault(aid, {})[cid] = (valor or \"\").strip()\n\n        cols = _columnas_tabla(cur, \"ARTICULOS\")\n        con_linea = \"LINEA_ARTICULO_ID\" in cols and _columnas_tabla(cur, \"LINEAS_ARTICULOS\")\n        if con_linea:\n            cur.execute(\"\"\"SELECT a.ARTICULO_ID, a.NOMBRE, a.ESTATUS, l.NOMBRE FROM ARTICULOS a\n                           LEFT JOIN LINEAS_ARTICULOS l ON l.LINEA_ARTICULO_ID = a.LINEA_ARTICULO_ID\"\"\")\n            articulos = cur.fetchall()\n        else:\n            cur.execute(\"SELECT ARTICULO_ID, NOMBRE, ESTATUS FROM ARTICULOS\")\n            articulos = [tuple(r) + (None,) for r in cur.fetchall()]\n\n        claves = {}\n        cur.execute(\"SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS ORDER BY CLAVE_ARTICULO_ID\")\n        for aid, clave in cur.fetchall():\n            if aid not in claves and clave:\n                claves[aid] = clave.strip()\n\n        existencias = {}\n        if _columnas_tabla(cur, \"CAPAS_COSTOS\"):\n            cur.execute(\"SELECT ARTICULO_ID, SUM(EXISTENCIA) FROM CAPAS_COSTOS WHERE CAPA_AGOTADA = 'N' GROUP BY ARTICULO_ID\")\n            existencias = {aid: float(ex or 0) for aid, ex in cur.fetchall()}\n    finally:\n        con.close()\n\n    estatus_txt = {\"A\": \"Activo\", \"B\": \"Baja\", \"S\": \"Suspendido\", \"C\": \"Cancelado\"}\n    resultado = []\n    for aid, nombre, estatus, linea in articulos:\n        tiene = valores.get(aid, {})\n        faltan = [nom for cid, nom in clasif if not tiene.get(cid)]\n        if not faltan:\n            continue\n        resultado.append({\n            \"articulo_id\": aid,\n            \"clave\": claves.get(aid, \"\"),\n            \"nombre\": (nombre or \"\").strip(),\n            \"linea\": (linea or \"\").strip(),\n            \"estatus\": estatus_txt.get((estatus or \"\").strip(), (estatus or \"\").strip()),\n            \"existencia\": existencias.get(aid, 0.0),\n            \"valores\": {nom: tiene.get(cid, \"\") for cid, nom in clasif},\n            \"faltan\": faltan,\n        })\n    resultado.sort(key=lambda r: (r[\"estatus\"] != \"Activo\", r[\"nombre\"]))\n    return {\"clasificadores\": [nom for _, nom in clasif], \"articulos\": resultado}\n\n\ndef obtener_valor_inventario_por_almacen(config: dict, valores_clasif_ids: list = None):\n"
  ]
 ],
 "backend/app.py": [
  [
   "    \"\"\"Clasificadores que aplican a artículos (ej. MARCA, PROVEEDOR) para\n    el selector del filtro en las tarjetas de inventario.\"\"\"\n    config = _config_microsip_o_error(usuario)\n    try:\n        return {\"clasificadores\": microsip.listar_clasificadores_articulos(config)}\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (clasificadores): {e}\")\n\n\n@app.get(\"/api/dashboard/valores-clasificador\")\n",
   "    \"\"\"Clasificadores que aplican a artículos (ej. MARCA, PROVEEDOR) para\n    el selector del filtro en las tarjetas de inventario.\"\"\"\n    config = _config_microsip_o_error(usuario)\n    try:\n        return {\"clasificadores\": microsip.listar_clasificadores_articulos(config)}\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (clasificadores): {e}\")\n\n\n@app.get(\"/api/dashboard/articulos-sin-clasificador\")\ndef api_dashboard_articulos_sin_clasificador(usuario: dict = Depends(requiere_dashboard)):\n    \"\"\"Artículos de Microsip a los que les falta el clasificador de MARCA\n    y/o PROVEEDOR (para exportarlo a Excel y completarlos).\"\"\"\n    config = _config_microsip_o_error(usuario)\n    try:\n        return microsip.articulos_sin_clasificador(config)\n    except ValueError as e:\n        raise HTTPException(status_code=400, detail=str(e))\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip (clasificadores): {e}\")\n\n\n@app.get(\"/api/dashboard/valores-clasificador\")\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  XLSX.writeFile(libro, `${nombreArchivo}_${new Date().toISOString().slice(0,10)}.xlsx`);\n}\n\nasync function cargarClasificadoresArticulos() {\n  if (!CLASIFICADORES_ARTICULOS_CACHE) {\n    const r = await api('/api/dashboard/clasificadores-articulos');\n",
   "  XLSX.writeFile(libro, `${nombreArchivo}_${new Date().toISOString().slice(0,10)}.xlsx`);\n}\n\n// Excel de los artículos de Microsip que no tienen clasificador de MARCA\n// y/o PROVEEDOR (para completarlos en Microsip).\nasync function exportarSinClasificadorExcel(btn) {\n  if (typeof XLSX === 'undefined') {\n    alert('No se pudo cargar el generador de Excel — revisa tu conexión e intenta de nuevo.');\n    return;\n  }\n  const original = btn ? btn.textContent : '';\n  if (btn) { btn.disabled = true; btn.textContent = 'Consultando Microsip…'; }\n  try {\n    const r = await api('/api/dashboard/articulos-sin-clasificador');\n    if (!r.articulos.length) {\n      alert('Todos los artículos tienen ' + r.clasificadores.join(' y ') + '.');\n      return;\n    }\n    const filas = r.articulos.map(a => {\n      const f = { 'Clave': a.clave, 'Artículo': a.nombre, 'Línea': a.linea, 'Estatus': a.estatus, 'Existencia': a.existencia };\n      r.clasificadores.forEach(c => { f[c] = a.valores[c] || ''; });\n      f['Le falta'] = a.faltan.join(' y ');\n      return f;\n    });\n    const hoja = XLSX.utils.json_to_sheet(filas);\n    hoja['!cols'] = [{ wch: 16 }, { wch: 50 }, { wch: 22 }, { wch: 11 }, { wch: 11 }, ...r.clasificadores.map(() => ({ wch: 22 })), { wch: 26 }];\n    hoja['!autofilter'] = { ref: hoja['!ref'] };\n    const activos = r.articulos.filter(a => a.estatus === 'Activo');\n    const resumen = [\n      { 'Concepto': 'Clasificadores revisados', 'Valor': r.clasificadores.join(', ') },\n      { 'Concepto': 'Artículos con algo faltante', 'Valor': r.articulos.length },\n      { 'Concepto': '   de esos, activos', 'Valor': activos.length },\n      { 'Concepto': '   activos con existencia', 'Valor': activos.filter(a => a.existencia > 0).length },\n    ];\n    r.clasificadores.forEach(c => resumen.push({ 'Concepto': 'Sin ' + c, 'Valor': r.articulos.filter(a => !a.valores[c]).length }));\n    if (r.clasificadores.length > 1) resumen.push({ 'Concepto': 'Sin ninguno', 'Valor': r.articulos.filter(a => a.faltan.length === r.clasificadores.length).length });\n    const hojaRes = XLSX.utils.json_to_sheet(resumen);\n    hojaRes['!cols'] = [{ wch: 32 }, { wch: 40 }];\n    const libro = XLSX.utils.book_new();\n    XLSX.utils.book_append_sheet(libro, hoja, 'Sin marca o proveedor');\n    XLSX.utils.book_append_sheet(libro, hojaRes, 'Resumen');\n    XLSX.writeFile(libro, `articulos_sin_marca_proveedor_${new Date().toISOString().slice(0,10)}.xlsx`);\n  } catch (e) {\n    alert(e.message || 'No se pudo consultar Microsip.');\n  } finally {\n    if (btn) { btn.disabled = false; btn.textContent = original; }\n  }\n}\n\nasync function cargarClasificadoresArticulos() {\n  if (!CLASIFICADORES_ARTICULOS_CACHE) {\n    const r = await api('/api/dashboard/clasificadores-articulos');\n"
  ],
  [
   "      </div>\n      <button class=\"secondary\" style=\"padding:5px 10px;\" onclick=\"${nombreFuncionRender}()\">Aplicar filtro</button>\n      <button class=\"secondary\" style=\"padding:5px 10px;\" onclick=\"quitarFiltroClasificador('${prefix}'); ${nombreFuncionRender}();\">Quitar</button>\n    </div>\n  `;\n}\n",
   "      </div>\n      <button class=\"secondary\" style=\"padding:5px 10px;\" onclick=\"${nombreFuncionRender}()\">Aplicar filtro</button>\n      <button class=\"secondary\" style=\"padding:5px 10px;\" onclick=\"quitarFiltroClasificador('${prefix}'); ${nombreFuncionRender}();\">Quitar</button>\n      <button class=\"secondary\" style=\"padding:5px 10px;\" title=\"Excel con los artículos a los que les falta el clasificador de marca y/o proveedor\" onclick=\"exportarSinClasificadorExcel(this)\">📥 Sin marca / proveedor</button>\n    </div>\n  `;\n}\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_microsip_sin_marca_proveedor.py")
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
