# -*- coding: utf-8 -*-
"""PDFs de Pedidos pendientes (Direccion -> Consultas): las UNIDADES DENTALES van primero,
en negritas y en azul (fondo azul claro), y al principio del PDF sale una referencia con las
unidades y en que pedido estan. Se reconocen por el nombre del articulo en Microsip
("UNIDAD DENTAL ...", "UNIDADES DENTALES ...", "SILLON DENTAL ...", "EQUIPO DENTAL ...").
REQUIERE fix_direccion_pedidos_pdf.py.
Correr en la carpeta tickets-ti:  py -3 fix_direccion_pdf_unidades.py
"""
import os, sys

ARCHIVOS = {
 "backend/pdfs_direccion.py": [
  [
   "import base64\nfrom datetime import datetime\n",
   "import base64\nimport re\nimport unicodedata\nfrom datetime import datetime\n"
  ],
  [
   "ANCHO = letter[0] - 3 * cm\n\n",
   "ANCHO = letter[0] - 3 * cm\n# Unidades dentales: van primero, en negritas y en azul, para ubicarlas rápido.\nAZUL = colors.HexColor(\"#0B4FA8\")\nAZUL_FONDO = colors.HexColor(\"#E3EEFC\")\n_PATRON_UNIDAD = re.compile(r\"\\bUNIDAD(ES)?\\s+(DENTAL|ODONTOLOGICA)|\\bSILLON(ES)?\\s+DENTAL|\\bEQUIPO\\s+DENTAL\\b\")\n\n\ndef es_unidad_dental(nombre):\n    \"\"\"Por el nombre del artículo en Microsip (ej. \"UNIDAD DENTAL PEYMAR ...\", \"SILLÓN DENTAL ...\").\"\"\"\n    t = unicodedata.normalize(\"NFKD\", str(nombre or \"\")).encode(\"ascii\", \"ignore\").decode().upper()\n    return bool(_PATRON_UNIDAD.search(t))\n\n"
  ],
  [
   "        \"dato\": ParagraphStyle(\"d\", parent=s[\"Normal\"], fontSize=9.5, leading=13, textColor=NEGRO),\n    }\n",
   "        \"dato\": ParagraphStyle(\"d\", parent=s[\"Normal\"], fontSize=9.5, leading=13, textColor=NEGRO),\n        \"celda_u\": ParagraphStyle(\"cu\", parent=s[\"Normal\"], fontName=\"Helvetica-Bold\", fontSize=9, leading=11, textColor=AZUL),\n        \"ref_titulo\": ParagraphStyle(\"rt\", parent=s[\"Normal\"], fontName=\"Helvetica-Bold\", fontSize=11, leading=14, textColor=AZUL),\n    }\n"
  ],
  [
   "def _tabla(est, encabezados, filas, anchos, derecha=(), total=None):\n",
   "def _tabla(est, encabezados, filas, anchos, derecha=(), total=None, resaltar=()):\n    \"\"\"resaltar: índices de `filas` que son unidades dentales (negritas, azul, fondo azul claro).\"\"\"\n"
  ],
  [
   "    for f in filas:\n        datos.append([p(c, est[\"celda\"], i) for i, c in enumerate(f)])\n",
   "    for n, f in enumerate(filas):\n        datos.append([p(c, est[\"celda_u\"] if n in resaltar else est[\"celda\"], i) for i, c in enumerate(f)])\n"
  ],
  [
   "        if i % 2 == 0:\n",
   "        if (i - 1) in resaltar:\n            estilo += [(\"BACKGROUND\", (0, i), (-1, i), AZUL_FONDO), (\"LINEBEFORE\", (0, i), (0, i), 3, AZUL)]\n        elif i % 2 == 0:\n"
  ],
  [
   "    return pie\n\n\ndef _documento(buffer):\n    return SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.4 * cm, bottomMargin=1.7 * cm,\n                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)\n",
   "    return pie\n\n\ndef _referencia_unidades(el, est, pedidos):\n    \"\"\"Al principio del PDF: qué unidades dentales hay y en qué pedidos (si hay).\"\"\"\n    filas = []\n    for p in pedidos:\n        for it in p.get(\"items\") or []:\n            if es_unidad_dental(it.get(\"nombre\")):\n                filas.append([p.get(\"folio\") or \"\", p.get(\"cliente_nombre\") or \"\", it.get(\"nombre\") or \"\",\n                              _num(it.get(\"cantidad_pendiente\"))])\n    if not filas:\n        return\n    piezas = sum(float(p.get(\"cantidad_pendiente\") or 0) for ped in pedidos for p in ped.get(\"items\") or []\n                 if es_unidad_dental(p.get(\"nombre\")))\n    el.append(Paragraph(f\"UNIDADES DENTALES · {_num(piezas)} pieza(s) en {len({f[0] for f in filas})} pedido(s)\", est[\"ref_titulo\"]))\n    el.append(Spacer(1, 4))\n    el.append(_tabla(est, [\"Pedido\", \"Cliente\", \"Unidad\", \"Piezas\"], filas,\n                     [2.4 * cm, 5 * cm, ANCHO - 2.4 * cm - 5 * cm - 1.8 * cm, 1.8 * cm], derecha=(3,),\n                     resaltar=set(range(len(filas)))))\n    el.append(Spacer(1, 14))\n\n\ndef _documento(buffer):\n    return SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.4 * cm, bottomMargin=1.7 * cm,\n                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)\n"
  ],
  [
   "    items = pedido.get(\"items\") or []\n",
   "    # Unidades dentales primero (resaltadas), luego lo demás en el orden de Microsip.\n    items = sorted(pedido.get(\"items\") or [], key=lambda i: not es_unidad_dental(i.get(\"nombre\")))\n    resaltar = {n for n, i in enumerate(items) if es_unidad_dental(i.get(\"nombre\"))}\n    if resaltar:\n        el.append(Paragraph(f\"Incluye {len(resaltar)} unidad(es) dental(es) — van primero y en azul.\", est[\"ref_titulo\"]))\n        el.append(Spacer(1, 4))\n"
  ],
  [
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total))\n",
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar))\n"
  ],
  [
   "    el = []\n    for i, p in enumerate(pedidos):\n",
   "    el = []\n    if len(pedidos) > 1 and any(es_unidad_dental(i.get(\"nombre\")) for p in pedidos for i in p.get(\"items\") or []):\n        # Hoja de referencia al principio: dónde hay unidades dentales.\n        _encabezado(el, est, empresa, f\"{len(pedidos)} pedidos pendientes\", f\"{escape(sucursal)} · {escape(rango)}\")\n        _referencia_unidades(el, est, pedidos)\n        el.append(PageBreak())\n    for i, p in enumerate(pedidos):\n"
  ],
  [
   "    filas = sorted(suma.values(), key=lambda s: (-s[\"piezas\"], s[\"nombre\"]))\n",
   "    # Unidades dentales primero (negritas y en azul), luego lo demás de más a menos piezas.\n    filas = sorted(suma.values(), key=lambda s: (not es_unidad_dental(s[\"nombre\"]), -s[\"piezas\"], s[\"nombre\"]))\n    resaltar = {n for n, s in enumerate(filas) if es_unidad_dental(s[\"nombre\"])}\n"
  ],
  [
   "                f\"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}\")\n    tabla = [[s[\"clave\"], s[\"nombre\"], _num(s[\"piezas\"]), str(len(s[\"pedidos\"])), _dinero(s[\"importe\"])] for s in filas]\n",
   "                f\"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}\")\n    _referencia_unidades(el, est, pedidos)\n    tabla = [[s[\"clave\"], s[\"nombre\"], _num(s[\"piezas\"]), str(len(s[\"pedidos\"])), _dinero(s[\"importe\"])] for s in filas]\n"
  ],
  [
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total))\n",
   "                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total,\n                     resaltar=resaltar))\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_direccion_pdf_unidades.py")
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
