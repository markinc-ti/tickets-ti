# -*- coding: utf-8 -*-
"""
tickets-ti (web): Pedidos por almacén ordenados por folio de menor a mayor y
folio sin ceros (AMC000282 → AMC282), también en el Excel. Se puede buscar AMC282.

Uso (en la carpeta tickets-ti):  py -3 fix_pedidos_almacen_folio.py
Se puede correr varias veces (si ya está aplicado no cambia nada).
"""
import io
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "  pintarPedidosAlmacen();\n}\n\nfunction _paFiltrados() {\n  const q = (PED_ALM.q || '').toLowerCase().trim();\n  const lista = (PED_ALM.datos && PED_ALM.datos.pedidos) || [];\n  if (!q) return lista;\n  return lista.filter(p => [p.folio, p.cliente, p.almacen, p.descripcion, ...p.partidas.map(d => d.articulo + ' ' + d.clave)].join(' ').toLowerCase().includes(q));\n}\n\nfunction pintarPedidosAlmacen() {\n",
   "  pintarPedidosAlmacen();\n}\n\n// Folio sin los ceros de relleno: AMC000282 → AMC282.\nfunction _paFolio(f) { return String(f || '').trim().replace(/^([^0-9]*)0+(?=\\d)/, '$1'); }\n// Orden de menor a mayor por folio (primero la serie, luego el número).\nfunction _paOrdenFolio(a, b) {\n  const pa = String(a.folio || '').trim().match(/^(\\D*)(\\d*)/), pb = String(b.folio || '').trim().match(/^(\\D*)(\\d*)/);\n  return pa[1].localeCompare(pb[1]) || (Number(pa[2] || 0) - Number(pb[2] || 0));\n}\n\nfunction _paFiltrados() {\n  const q = (PED_ALM.q || '').toLowerCase().trim();\n  const lista = [...((PED_ALM.datos && PED_ALM.datos.pedidos) || [])].sort(_paOrdenFolio);\n  if (!q) return lista;\n  return lista.filter(p => [p.folio, _paFolio(p.folio), p.cliente, p.almacen, p.descripcion, ...p.partidas.map(d => d.articulo + ' ' + d.clave)].join(' ').toLowerCase().includes(q));\n}\n\nfunction pintarPedidosAlmacen() {\n"
  ],
  [
   "      const abierto = PED_ALM.abiertos.has(p.docto_ve_id);\n      return `<div class=\"cv-caja\" style=\"padding:0; margin-bottom:8px; overflow:hidden;\">\n        <div style=\"display:flex; gap:10px; align-items:center; padding:10px 12px; cursor:pointer; flex-wrap:wrap;\" onclick=\"PED_ALM.abiertos.has(${p.docto_ve_id}) ? PED_ALM.abiertos.delete(${p.docto_ve_id}) : PED_ALM.abiertos.add(${p.docto_ve_id}); pintarPedidosAlmacen()\">\n          <b style=\"min-width:90px;\">${abierto ? '▾' : '▸'} ${escapeHtml(p.folio)}</b>\n          <span style=\"font-size:12px; color:var(--muted); min-width:80px;\">${escapeHtml((p.fecha || '').slice(0, 10))}</span>\n          <span style=\"flex:1; min-width:160px;\">${escapeHtml(p.cliente || '—')}</span>\n          <span style=\"font-size:12px; color:var(--muted);\">${escapeHtml(p.almacen || '')}</span>\n",
   "      const abierto = PED_ALM.abiertos.has(p.docto_ve_id);\n      return `<div class=\"cv-caja\" style=\"padding:0; margin-bottom:8px; overflow:hidden;\">\n        <div style=\"display:flex; gap:10px; align-items:center; padding:10px 12px; cursor:pointer; flex-wrap:wrap;\" onclick=\"PED_ALM.abiertos.has(${p.docto_ve_id}) ? PED_ALM.abiertos.delete(${p.docto_ve_id}) : PED_ALM.abiertos.add(${p.docto_ve_id}); pintarPedidosAlmacen()\">\n          <b style=\"min-width:90px;\">${abierto ? '▾' : '▸'} ${escapeHtml(_paFolio(p.folio))}</b>\n          <span style=\"font-size:12px; color:var(--muted); min-width:80px;\">${escapeHtml((p.fecha || '').slice(0, 10))}</span>\n          <span style=\"flex:1; min-width:160px;\">${escapeHtml(p.cliente || '—')}</span>\n          <span style=\"font-size:12px; color:var(--muted);\">${escapeHtml(p.almacen || '')}</span>\n"
  ],
  [
   "  if (!lista.length) { alert('No hay pedidos que exportar.'); return; }\n  const filas = [];\n  lista.forEach(p => (p.partidas.length ? p.partidas : [{}]).forEach(d => filas.push({\n    'Folio': p.folio, 'Fecha': (p.fecha || '').slice(0, 10), 'Estatus': p.estatus_nombre, 'Almacén': p.almacen, 'Cliente': p.cliente,\n    'Clave': d.clave || '', 'Artículo': d.articulo || '', 'Pedidas': d.unidades ?? '', 'Surtidas': d.surtidas ?? '', 'Pendientes': d.pendientes ?? '',\n    'Precio': d.precio ?? '', 'Desc %': d.descuento_pct || '', 'Importe': d.importe ?? '', 'Total pedido con IVA': p.importe_con_iva, 'Capturó': p.capturado_por,\n  })));\n",
   "  if (!lista.length) { alert('No hay pedidos que exportar.'); return; }\n  const filas = [];\n  lista.forEach(p => (p.partidas.length ? p.partidas : [{}]).forEach(d => filas.push({\n    'Folio': _paFolio(p.folio), 'Fecha': (p.fecha || '').slice(0, 10), 'Estatus': p.estatus_nombre, 'Almacén': p.almacen, 'Cliente': p.cliente,\n    'Clave': d.clave || '', 'Artículo': d.articulo || '', 'Pedidas': d.unidades ?? '', 'Surtidas': d.surtidas ?? '', 'Pendientes': d.pendientes ?? '',\n    'Precio': d.precio ?? '', 'Desc %': d.descuento_pct || '', 'Importe': d.importe ?? '', 'Total pedido con IVA': p.importe_con_iva, 'Capturó': p.capturado_por,\n  })));\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_pedidos_almacen_folio.py")
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
