# -*- coding: utf-8 -*-
"""
Agrega un buscador dentro del explorador de tablas de Microsip (Administrar
-> Microsip), para poder filtrar la muestra por un folio o valor especifico
en vez de solo ver las primeras 10 filas al azar.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_explorador_filtro.py
"""
import sys

ARCHIVOS = {'backend/microsip.py': [['def consultar_muestra(config: dict, tabla: str, limite: int = 20):\n    con = _conectar(config)\n    cur = con.cursor()\n    # El nombre de tabla no viene parametrizable en SQL — se limita a\n    # identificadores válidos para evitar inyección.\n    if not re.match(r"^[A-Za-z0-9_$]+$", tabla):\n        raise ValueError("Nombre de tabla inválido")\n    cur.execute(f"SELECT FIRST {int(limite)} * FROM {tabla}")\n    columnas = [d[0] for d in cur.description]\n    filas = [dict(zip(columnas, row)) for row in cur.fetchall()]\n    con.close()', 'def consultar_muestra(config: dict, tabla: str, limite: int = 20, columna_filtro: str = None, valor_filtro: str = None):\n    con = _conectar(config)\n    cur = con.cursor()\n    # El nombre de tabla/columna no viene parametrizable en SQL — se limita a\n    # identificadores válidos para evitar inyección.\n    if not re.match(r"^[A-Za-z0-9_$]+$", tabla):\n        raise ValueError("Nombre de tabla inválido")\n    if columna_filtro:\n        if not re.match(r"^[A-Za-z0-9_$]+$", columna_filtro):\n            raise ValueError("Nombre de columna inválido")\n        # CONTAINING busca la coincidencia sin importar mayúsculas/minúsculas\n        # ni si el valor está en medio del texto — funciona tanto para\n        # folios exactos como para nombres parciales.\n        cur.execute(f"SELECT FIRST {int(limite)} * FROM {tabla} WHERE {columna_filtro} CONTAINING ?", (valor_filtro,))\n    else:\n        cur.execute(f"SELECT FIRST {int(limite)} * FROM {tabla}")\n    columnas = [d[0] for d in cur.description]\n    filas = [dict(zip(columnas, row)) for row in cur.fetchall()]\n    con.close()']], 'backend/app.py': [['@app.get("/api/microsip/tablas/{tabla}/muestra")\ndef api_muestra_tabla_microsip(tabla: str, limite: int = 20, usuario: dict = Depends(requiere_admin_completo)):\n    _requiere_microsip_disponible()\n    config = db.obtener_config_microsip(usuario["empresa_id"])\n    try:\n        return {"filas": microsip.consultar_muestra(config, tabla, limite)}\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=str(e))', '@app.get("/api/microsip/tablas/{tabla}/muestra")\ndef api_muestra_tabla_microsip(tabla: str, limite: int = 20, columna: Optional[str] = None, valor: Optional[str] = None, usuario: dict = Depends(requiere_admin_completo)):\n    _requiere_microsip_disponible()\n    config = db.obtener_config_microsip(usuario["empresa_id"])\n    try:\n        return {"filas": microsip.consultar_muestra(config, tabla, limite, columna, valor)}\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=str(e))']], 'frontend/index.html': [['async function explorarTablaMicrosipUI(tabla) {\n  const detalle = document.getElementById(\'microsipDetalleTabla\');\n  detalle.innerHTML = \'<p style="color:var(--muted); font-size:12px; margin-top:12px;">Cargando…</p>\';\n  try {\n    const [{ columnas }, { filas }] = await Promise.all([\n      api(`/api/microsip/tablas/${encodeURIComponent(tabla)}/columnas`),\n      api(`/api/microsip/tablas/${encodeURIComponent(tabla)}/muestra?limite=10`),\n    ]);\n    detalle.innerHTML = `\n      <p style="font-size:12px; font-weight:bold; margin-top:14px;">${escapeHtml(tabla)} — columnas</p>\n      <div style="overflow-x:auto; margin-bottom:10px;">\n        <table class="users"><thead><tr><th>Columna</th><th>Tipo</th></tr></thead>\n          <tbody>${columnas.map(c => `<tr><td>${escapeHtml(c.nombre)}</td><td>${escapeHtml(c.tipo)}</td></tr>`).join(\'\')}</tbody>\n        </table>\n      </div>\n      <p style="font-size:12px; font-weight:bold;">Muestra de datos (hasta 10 filas)</p>\n      <div style="overflow-x:auto;">\n        <table class="users">\n          <thead><tr>${columnas.map(c => `<th>${escapeHtml(c.nombre)}</th>`).join(\'\')}</tr></thead>\n          <tbody>\n            ${filas.map(f => `<tr>${columnas.map(c => `<td>${f[c.nombre] != null ? escapeHtml(String(f[c.nombre])) : \'—\'}</td>`).join(\'\')}</tr>`).join(\'\') || `<tr><td colspan="${columnas.length}" class="empty-col">— sin filas —</td></tr>`}\n          </tbody>\n        </table>\n      </div>\n    `;\n  } catch (e) {\n    detalle.innerHTML = `<p style="color:var(--urgente); font-size:12px; margin-top:12px;">${escapeHtml(e.message)}</p>`;\n  }\n}\n', 'async function explorarTablaMicrosipUI(tabla) {\n  const detalle = document.getElementById(\'microsipDetalleTabla\');\n  detalle.innerHTML = \'<p style="color:var(--muted); font-size:12px; margin-top:12px;">Cargando…</p>\';\n  try {\n    const [{ columnas }, { filas }] = await Promise.all([\n      api(`/api/microsip/tablas/${encodeURIComponent(tabla)}/columnas`),\n      api(`/api/microsip/tablas/${encodeURIComponent(tabla)}/muestra?limite=10`),\n    ]);\n    TABLA_MICROSIP_ACTUAL = tabla;\n    COLUMNAS_MICROSIP_ACTUAL = columnas;\n    detalle.innerHTML = `\n      <p style="font-size:12px; font-weight:bold; margin-top:14px;">${escapeHtml(tabla)} — columnas</p>\n      <div style="overflow-x:auto; margin-bottom:10px;">\n        <table class="users"><thead><tr><th>Columna</th><th>Tipo</th></tr></thead>\n          <tbody>${columnas.map(c => `<tr><td>${escapeHtml(c.nombre)}</td><td>${escapeHtml(c.tipo)}</td></tr>`).join(\'\')}</tbody>\n        </table>\n      </div>\n      <div style="display:flex; gap:6px; align-items:end; margin-bottom:8px; flex-wrap:wrap;">\n        <div class="field" style="margin:0;"><label>Buscar en columna</label>\n          <select id="microsipFiltroColumna" style="width:auto;">\n            ${columnas.map(c => `<option value="${escapeHtml(c.nombre)}">${escapeHtml(c.nombre)}</option>`).join(\'\')}\n          </select>\n        </div>\n        <div class="field" style="margin:0; flex:1; min-width:140px;"><label>Valor que contenga</label>\n          <input id="microsipFiltroValor" autocomplete="off" placeholder="ej. un folio" onkeydown="if(event.key===\'Enter\'){event.preventDefault(); buscarEnTablaMicrosipUI();}" />\n        </div>\n        <button class="secondary" onclick="buscarEnTablaMicrosipUI()">Buscar</button>\n        <button class="secondary" onclick="explorarTablaMicrosipUI(TABLA_MICROSIP_ACTUAL)">Quitar filtro</button>\n      </div>\n      <p style="font-size:12px; font-weight:bold;">Muestra de datos (hasta 10 filas)</p>\n      <div id="microsipMuestraTabla" style="overflow-x:auto;">\n        ${renderMuestraTablaMicrosip(columnas, filas)}\n      </div>\n    `;\n  } catch (e) {\n    detalle.innerHTML = `<p style="color:var(--urgente); font-size:12px; margin-top:12px;">${escapeHtml(e.message)}</p>`;\n  }\n}\n\nlet TABLA_MICROSIP_ACTUAL = null;\nlet COLUMNAS_MICROSIP_ACTUAL = [];\n\nfunction renderMuestraTablaMicrosip(columnas, filas) {\n  return `\n    <table class="users">\n      <thead><tr>${columnas.map(c => `<th>${escapeHtml(c.nombre)}</th>`).join(\'\')}</tr></thead>\n      <tbody>\n        ${filas.map(f => `<tr>${columnas.map(c => `<td>${f[c.nombre] != null ? escapeHtml(String(f[c.nombre])) : \'—\'}</td>`).join(\'\')}</tr>`).join(\'\') || `<tr><td colspan="${columnas.length}" class="empty-col">— sin filas que coincidan —</td></tr>`}\n      </tbody>\n    </table>\n  `;\n}\n\nasync function buscarEnTablaMicrosipUI() {\n  const columna = document.getElementById(\'microsipFiltroColumna\').value;\n  const valor = document.getElementById(\'microsipFiltroValor\').value.trim();\n  const cont = document.getElementById(\'microsipMuestraTabla\');\n  if (!valor) return;\n  cont.innerHTML = \'<p style="color:var(--muted); font-size:12px;">Buscando…</p>\';\n  try {\n    const { filas } = await api(`/api/microsip/tablas/${encodeURIComponent(TABLA_MICROSIP_ACTUAL)}/muestra?limite=10&columna=${encodeURIComponent(columna)}&valor=${encodeURIComponent(valor)}`);\n    cont.innerHTML = renderMuestraTablaMicrosip(COLUMNAS_MICROSIP_ACTUAL, filas);\n  } catch (e) {\n    cont.innerHTML = `<p style="color:var(--urgente); font-size:12px;">${escapeHtml(e.message)}</p>`;\n  }\n}\n']]}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    hubo_error = False
    for ruta, reemplazos in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
            hubo_error = True
            continue
        cambios = 0
        for viejo, nuevo in reemplazos:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
                hubo_error = True
                continue
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py backend/microsip.py frontend/index.html")
    print('   git commit -m "Buscador por columna en el explorador de tablas de Microsip"')
    print("   git push")


if __name__ == "__main__":
    main()
