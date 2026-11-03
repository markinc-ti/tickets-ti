# -*- coding: utf-8 -*-
"""
COTIZADOR (SUPERADMIN): QUE SE COTIZO, BUSCADOR Y VISTA PREVIA DEL PDF
En la lista de cotizaciones del superadmin:
- Columna "Que se cotizo" con los conceptos (y cantidades) de cada cotizacion.
- Buscador por cliente, folio, contacto o lo cotizado (sin importar acentos).
- Ojo: vista previa del PDF de la cotizacion sin salir de la lista; si tiene
  nota de venta, otro boton para su PDF. Desde ahi "Abrir para editar".
Toca: backend/db.py, frontend/index.html, frontend/cotizador_costos.html
Se puede correr varias veces.  Correr con:  py -3 fix_cotizador_lista_descripcion_pdf.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "            \"nombre_cliente\": f[\"nombre_cliente\"] or f[\"empresa_nombre\"] or \"—\",\n            \"producto\": config.get(\"producto\", \"ti\"),\n            \"folio\": (config.get(\"cliente\") or {}).get(\"folio\"),\n            \"nota_folio\": (config.get(\"nota\") or {}).get(\"folio\") if (config.get(\"nota\") or {}).get(\"activa\") else None,\n            \"renta_mensual\": renta_total,\n            \"setup_total\": setup_total,\n",
   "            \"nombre_cliente\": f[\"nombre_cliente\"] or f[\"empresa_nombre\"] or \"—\",\n            \"producto\": config.get(\"producto\", \"ti\"),\n            \"folio\": (config.get(\"cliente\") or {}).get(\"folio\"),\n            # Qué se cotizó (para buscar): los conceptos incluidos, con su cantidad.\n            \"descripcion\": [((f\"{int(m.get('cantidad') or 1)} × \" if int(m.get(\"cantidad\") or 1) > 1 else \"\") + str(m.get(\"name\") or \"\").strip())\n                            for m in modulos if str(m.get(\"name\") or \"\").strip()],\n            \"contacto\": (config.get(\"cliente\") or {}).get(\"contacto\"),\n            \"nota_folio\": (config.get(\"nota\") or {}).get(\"folio\") if (config.get(\"nota\") or {}).get(\"activa\") else None,\n            \"renta_mensual\": renta_total,\n            \"setup_total\": setup_total,\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    <button class=\"primary\" style=\"width:100%; margin:10px 0;\" onclick=\"abrirNuevaCotizacionUI()\">+ Nueva cotización</button>\n    <p style=\"font-size:14px;\"><b>Renta mensual total: ${_fmtC(rentaGlobal)}</b> &nbsp;|&nbsp; Costo real total: ${_fmtC(costoGlobal)} &nbsp;|&nbsp; Margen global: ${rentaGlobal ? Math.round(((rentaGlobal - costoGlobal) / rentaGlobal) * 100) : 0}%</p>\n    ${filas.length ? `\n    <table class=\"users\" style=\"margin-top:10px;\">\n      <thead><tr><th>Cliente</th><th>Empresa vinculada</th><th>Producto</th><th>Renta/mes</th><th>Costo real/mes</th><th>Margen</th><th></th></tr></thead>\n      <tbody>\n        ${filas.map(f => `\n          <tr>\n            <td style=\"cursor:pointer;\" onclick=\"cerrarModal(); window.open('/cotizador-costos.html?cotizacion_id=${f.id}', '_blank')\">${escapeHtml(f.nombre_cliente)}${f.folio ? `<br><span style=\"font-size:11px; color:var(--muted);\">${escapeHtml(f.folio)}</span>` : ''}${f.nota_folio ? ` <span style=\"font-size:11px; background:#e8f5e9; color:#1b5e20; border-radius:8px; padding:1px 6px;\">🧾 ${escapeHtml(f.nota_folio)}</span>` : ''}</td>\n            <td>${f.empresa_nombre ? escapeHtml(f.empresa_nombre) : '<span style=\"color:var(--muted);\">— prospecto —</span>'}</td>\n            <td>${NOMBRES_PRODUCTO_COTIZADOR[f.producto] || f.producto}</td>\n            <td>${_fmtC(f.renta_mensual)}</td>\n            <td>${_fmtC(f.costo_mensual)}</td>\n            <td>${f.margen_pct}%</td>\n            <td>\n              <span style=\"cursor:pointer; margin-right:10px;\" title=\"Duplicar — usarla como base para una cotización nueva\" onclick=\"abrirDuplicarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,\"\\\\'\")}')\">📋</span>\n              <span class=\"quitar\" onclick=\"eliminarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,\"\\\\'\")}')\">✕</span>\n            </td>\n          </tr>\n        `).join('')}\n      </tbody>\n    </table>` : '<p class=\"empty-col\">— todavía no hay ninguna cotización, crea la primera —</p>'}\n  `;\n}\nfunction abrirCrearEmpresa() {\n  document.getElementById('modalContent').innerHTML = `\n",
   "    <button class=\"primary\" style=\"width:100%; margin:10px 0;\" onclick=\"abrirNuevaCotizacionUI()\">+ Nueva cotización</button>\n    <p style=\"font-size:14px;\"><b>Renta mensual total: ${_fmtC(rentaGlobal)}</b> &nbsp;|&nbsp; Costo real total: ${_fmtC(costoGlobal)} &nbsp;|&nbsp; Margen global: ${rentaGlobal ? Math.round(((rentaGlobal - costoGlobal) / rentaGlobal) * 100) : 0}%</p>\n    ${filas.length ? `\n    <input id=\"cotBuscar\" placeholder=\"🔎 Buscar por cliente, folio, contacto o lo cotizado (ej. cámaras, nómina, DVR)…\" oninput=\"filtrarCotizacionesSuperadmin(this.value)\" style=\"margin:6px 0 4px;\" />\n    <div id=\"cotBuscarInfo\" style=\"font-size:11px; color:var(--muted); margin-bottom:4px;\">${filas.length} cotizaciones</div>\n    <div style=\"overflow-x:auto;\"><table class=\"users\" style=\"margin-top:6px;\">\n      <thead><tr><th>Cliente</th><th>Qué se cotizó</th><th>Producto</th><th>Renta/mes</th><th>Costo real/mes</th><th>Margen</th><th></th></tr></thead>\n      <tbody>\n        ${filas.map(f => {\n          const desc = f.descripcion || [];\n          const texto = [f.nombre_cliente, f.empresa_nombre, f.folio, f.nota_folio, f.contacto, NOMBRES_PRODUCTO_COTIZADOR[f.producto] || f.producto, ...desc].join(' ');\n          return `\n          <tr class=\"cot-fila\" data-busca=\"${escapeHtml(_sinAcentosCot(texto))}\">\n            <td style=\"cursor:pointer;\" onclick=\"cerrarModal(); window.open('/cotizador-costos.html?cotizacion_id=${f.id}', '_blank')\">${escapeHtml(f.nombre_cliente)}${f.folio ? `<br><span style=\"font-size:11px; color:var(--muted);\">${escapeHtml(f.folio)}</span>` : ''}${f.nota_folio ? ` <span style=\"font-size:11px; background:#e8f5e9; color:#1b5e20; border-radius:8px; padding:1px 6px;\">🧾 ${escapeHtml(f.nota_folio)}</span>` : ''}\n              <div style=\"font-size:10px; color:var(--muted);\">${f.empresa_nombre ? escapeHtml(f.empresa_nombre) : '— prospecto —'}${f.actualizado_en ? ` · ${escapeHtml(String(f.actualizado_en).slice(0, 10))}` : ''}</div></td>\n            <td style=\"font-size:12px; max-width:320px;\" title=\"${escapeHtml(desc.join('\\n'))}\">${desc.length ? escapeHtml(desc.slice(0, 4).join(', ')) + (desc.length > 4 ? ` <span style=\"color:var(--muted);\">+${desc.length - 4} más</span>` : '') : '<span style=\"color:var(--muted);\">— sin conceptos —</span>'}</td>\n            <td>${NOMBRES_PRODUCTO_COTIZADOR[f.producto] || f.producto}</td>\n            <td>${_fmtC(f.renta_mensual)}</td>\n            <td>${_fmtC(f.costo_mensual)}</td>\n            <td>${f.margen_pct}%</td>\n            <td style=\"white-space:nowrap;\">\n              <span style=\"cursor:pointer; margin-right:10px;\" title=\"Ver el PDF de la cotización\" onclick=\"verPdfCotizacionSuperadmin(${f.id}, 'cotizacion', '${escapeHtml(f.folio || f.nombre_cliente || '').replace(/'/g, \"\\\\'\")}')\">👁️</span>\n              ${f.nota_folio ? `<span style=\"cursor:pointer; margin-right:10px;\" title=\"Ver el PDF de la nota de venta\" onclick=\"verPdfCotizacionSuperadmin(${f.id}, 'nota', '${escapeHtml(f.nota_folio).replace(/'/g, \"\\\\'\")}')\">🧾</span>` : ''}\n              <span style=\"cursor:pointer; margin-right:10px;\" title=\"Duplicar — usarla como base para una cotización nueva\" onclick=\"abrirDuplicarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,\"\\\\'\")}')\">📋</span>\n              <span class=\"quitar\" onclick=\"eliminarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,\"\\\\'\")}')\">✕</span>\n            </td>\n          </tr>`; }).join('')}\n      </tbody>\n    </table></div>` : '<p class=\"empty-col\">— todavía no hay ninguna cotización, crea la primera —</p>'}\n  `;\n}\n\nfunction _sinAcentosCot(t) {\n  return String(t || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();\n}\n\n// Búsqueda en la lista: todas las palabras deben aparecer (cliente, folio, contacto o lo cotizado).\nfunction filtrarCotizacionesSuperadmin(q) {\n  const palabras = _sinAcentosCot(q).split(/\\s+/).filter(Boolean);\n  let n = 0;\n  document.querySelectorAll('#modalContent tr.cot-fila').forEach(tr => {\n    const ok = palabras.every(p => tr.dataset.busca.includes(p));\n    tr.style.display = ok ? '' : 'none';\n    if (ok) n++;\n  });\n  const info = document.getElementById('cotBuscarInfo');\n  if (info) info.textContent = palabras.length ? `${n} de ${(COTIZACIONES_CACHE || []).length} cotizaciones` : `${(COTIZACIONES_CACHE || []).length} cotizaciones`;\n}\n\n// Vista previa del PDF (cotización o nota de venta) sin salir de la lista.\nfunction verPdfCotizacionSuperadmin(id, que, titulo) {\n  const v = document.createElement('div');\n  v.id = 'cotPdfPrevia';\n  v.style.cssText = 'position:fixed; inset:0; background:#000c; z-index:10000; display:flex; flex-direction:column; padding:16px; gap:8px;';\n  v.innerHTML = `<div style=\"display:flex; gap:8px; align-items:center; color:#fff;\">\n      <b style=\"flex:1;\">${que === 'nota' ? '🧾 Nota de venta' : '👁️ Cotización'} ${escapeHtml(titulo || '')}</b>\n      <button class=\"secondary\" onclick=\"window.open('/cotizador-costos.html?cotizacion_id=${id}', '_blank')\">Abrir para editar</button>\n      <button class=\"secondary\" onclick=\"document.getElementById('cotPdfPrevia').remove()\">Cerrar</button></div>\n    <iframe src=\"/cotizador-costos.html?cotizacion_id=${id}&pdf=${que}\" style=\"flex:1; width:100%; border:0; border-radius:10px; background:#fff;\"></iframe>`;\n  document.body.appendChild(v);\n}\nfunction abrirCrearEmpresa() {\n  document.getElementById('modalContent').innerHTML = `\n"
  ]
 ],
 "frontend/cotizador_costos.html": [
  [
   "    document.getElementById('carga-aviso').textContent = 'No se pudo cargar la configuración guardada (se muestra la plantilla).';\n  }\n  renderAll();\n}\n\n// Guarda en el servidor; el servidor regresa los folios automáticos\n",
   "    document.getElementById('carga-aviso').textContent = 'No se pudo cargar la configuración guardada (se muestra la plantilla).';\n  }\n  renderAll();\n  // ?pdf=cotizacion | nota: vista previa del PDF (desde la lista de cotizaciones del superadmin).\n  const modoPdf = _PARAMS.get('pdf');\n  if(modoPdf){\n    try{\n      const blob = modoPdf === 'nota' ? await buildNotaPdfBlob() : await buildPdfBlob();\n      const url = URL.createObjectURL(blob);\n      const est = document.getElementById('estilo-previa-pdf'); if(est) est.remove();\n      document.body.innerHTML = '<iframe src=\"' + url + '\" style=\"position:fixed; inset:0; width:100%; height:100%; border:0;\"></iframe>';\n    }catch(e){\n      const est = document.getElementById('estilo-previa-pdf'); if(est) est.remove();\n      document.body.innerHTML = '<p style=\"font-family:sans-serif; padding:20px;\">No se pudo generar la vista previa del PDF.</p>';\n    }\n  }\n}\n\n// Guarda en el servidor; el servidor regresa los folios automáticos\n"
  ],
  [
   "  }\n});\n\n_cargarDesdeServidor();\n\n})();\n",
   "  }\n});\n\nif(_PARAMS.get('pdf')){\n  // En vista previa no se muestra el editor mientras se arma el PDF.\n  const est = document.createElement('style');\n  est.id = 'estilo-previa-pdf';\n  est.textContent = 'body > *{display:none !important;} body::before{content:\"Generando vista previa…\"; display:block; font:14px sans-serif; padding:24px; color:#666;}';\n  document.head.appendChild(est);\n}\n_cargarDesdeServidor();\n\n})();\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_cotizador_lista_descripcion_pdf.py")
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
