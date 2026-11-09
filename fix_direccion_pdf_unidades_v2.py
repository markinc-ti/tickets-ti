# -*- coding: utf-8 -*-
"""PDFs de Pedidos pendientes (2): vuelven a quedar como antes (sin la hoja/recuadro de
referencia ni el aviso), solo que las UNIDADES DENTALES van hasta arriba (negritas, azul) y
justo debajo un renglon "TOTAL UNIDADES DENTALES" con cuantas unidades se vendieron (piezas
por surtir), en cuantos pedidos y su importe.
REQUIERE fix_direccion_pdf_unidades.py.
Correr en la carpeta tickets-ti:  py -3 fix_direccion_pdf_unidades_v2.py
"""
import os, sys

ARCHIVOS = {
 "backend/pdfs_direccion.py": [
  [
   "def _tabla(est, encabezados, filas, anchos, derecha=(), total=None, resaltar=()):\n    \"\"\"resaltar: índices de `filas` que son unidades dentales (negritas, azul, fondo azul claro).\"\"\"\n",
   "def _tabla(est, encabezados, filas, anchos, derecha=(), total=None, resaltar=(), subtotal=None):\n    \"\"\"resaltar: índices de `filas` que son unidades dentales (negritas, azul, fondo azul claro).\n    subtotal: renglón \"Total unidades dentales\" que va justo después de ellas.\"\"\"\n    if subtotal and resaltar:\n        k = max(resaltar) + 1\n        filas = list(filas[:k]) + [subtotal] + list(filas[k:])\n        resaltar = set(resaltar) | {k}\n        fila_sub = k\n    else:\n        fila_sub = None\n"
  ],
  [
   "        if (i - 1) in resaltar:\n",
   "        if (i - 1) == fila_sub:\n            estilo += [(\"BACKGROUND\", (0, i), (-1, i), colors.HexColor(\"#C9DDF8\")), (\"LINEABOVE\", (0, i), (-1, i), 1, AZUL),\n                       (\"LINEBELOW\", (0, i), (-1, i), 1, AZUL), (\"LINEBEFORE\", (0, i), (0, i), 3, AZUL)]\n        elif (i - 1) in resaltar:\n"
  ],
  [
   "def _referencia_unidades(el, est, pedidos):\n    \"\"\"Al principio del PDF: qué unidades dentales hay y en qué pedidos (si hay).\"\"\"\n    filas = []\n    for p in pedidos:\n        for it in p.get(\"items\") or []:\n            if es_unidad_dental(it.get(\"nombre\")):\n                filas.append([p.get(\"folio\") or \"\", p.get(\"cliente_nombre\") or \"\", it.get(\"nombre\") or \"\",\n                              _num(it.get(\"cantidad_pendiente\"))])\n    if not filas:\n        return\n    piezas = sum(float(p.get(\"cantidad_pendiente\") or 0) for ped in pedidos for p in ped.get(\"items\") or []\n                 if es_unidad_dental(p.get(\"nombre\")))\n    el.append(Paragraph(f\"UNIDADES DENTALES · {_num(piezas)} pieza(s) en {len({f[0] for f in filas})} pedido(s)\", est[\"ref_titulo\"]))\n    el.append(Spacer(1, 4))\n    el.append(_tabla(est, [\"Pedido\", \"Cliente\", \"Unidad\", \"Piezas\"], filas,\n                     [2.4 * cm, 5 * cm, ANCHO - 2.4 * cm - 5 * cm - 1.8 * cm, 1.8 * cm], derecha=(3,),\n                     resaltar=set(range(len(filas)))))\n    el.append(Spacer(1, 14))\n\n\n",
   ""
  ],
  [
   "    if resaltar:\n        el.append(Paragraph(f\"Incluye {len(resaltar)} unidad(es) dental(es) — van primero y en azul.\", est[\"ref_titulo\"]))\n        el.append(Spacer(1, 4))\n",
   "    uds = [items[n] for n in resaltar]\n    subtotal = [\"\", \"TOTAL UNIDADES DENTALES\", _num(sum(float(i.get(\"cantidad_pendiente\") or 0) for i in uds)), \"\",\n                _dinero(sum(float(i.get(\"total_con_iva\") or 0) for i in uds))] if uds else None\n"
  ],
  [
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar))\n\n",
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar, subtotal=subtotal))\n\n"
  ],
  [
   "    if len(pedidos) > 1 and any(es_unidad_dental(i.get(\"nombre\")) for p in pedidos for i in p.get(\"items\") or []):\n        # Hoja de referencia al principio: dónde hay unidades dentales.\n        _encabezado(el, est, empresa, f\"{len(pedidos)} pedidos pendientes\", f\"{escape(sucursal)} · {escape(rango)}\")\n        _referencia_unidades(el, est, pedidos)\n        el.append(PageBreak())\n",
   ""
  ],
  [
   "                f\"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}\")\n    _referencia_unidades(el, est, pedidos)\n    tabla = [[s[\"clave\"], s[\"nombre\"], _num(s[\"piezas\"]), str(len(s[\"pedidos\"])), _dinero(s[\"importe\"])] for s in filas]\n",
   "                f\"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}\")\n    tabla = [[s[\"clave\"], s[\"nombre\"], _num(s[\"piezas\"]), str(len(s[\"pedidos\"])), _dinero(s[\"importe\"])] for s in filas]\n"
  ],
  [
   "             _dinero(sum(s[\"importe\"] for s in filas))]\n    el.append(_tabla(est, [\"Clave\", \"Artículo\", \"Piezas\", \"Pedidos\", \"Importe c/IVA\"], tabla,\n",
   "             _dinero(sum(s[\"importe\"] for s in filas))]\n    uds = [filas[n] for n in resaltar]\n    subtotal = [\"\", \"TOTAL UNIDADES DENTALES\", _num(sum(s[\"piezas\"] for s in uds)),\n                str(len(set().union(*[s[\"pedidos\"] for s in uds]))), _dinero(sum(s[\"importe\"] for s in uds))] if uds else None\n    el.append(_tabla(est, [\"Clave\", \"Artículo\", \"Piezas\", \"Pedidos\", \"Importe c/IVA\"], tabla,\n"
  ],
  [
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar))\n    doc.build(el, onFirstPage=_pie(\"Productos de pedidos pendientes\"), onLaterPages=_pie(\"Productos de pedidos pendientes\"))\n",
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar, subtotal=subtotal))\n    doc.build(el, onFirstPage=_pie(\"Productos de pedidos pendientes\"), onLaterPages=_pie(\"Productos de pedidos pendientes\"))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_direccion_pdf_unidades_v2.py")
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
