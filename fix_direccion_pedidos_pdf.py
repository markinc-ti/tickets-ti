# -*- coding: utf-8 -*-
"""Direccion -> Consultas -> Pedidos pendientes:
- rango de fechas (del ... al ...) ademas de hoy/semana/mes/todo,
- ya salen TODOS los productos (antes solo 50),
- PDF de cada pedido, PDF de todos los pedidos (uno por hoja) y PDF de todos los productos
  sumados; si en la app se marcan pedidos, los PDF salen solo con esos.
Archivos: backend/app.py, backend/direccion.py y el nuevo backend/pdfs_direccion.py.
Correr en la carpeta tickets-ti:  py -3 fix_direccion_pedidos_pdf.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "import pdfs_cotizaciones\nimport calendario_ics\n",
   "import pdfs_cotizaciones\nimport pdfs_direccion\nimport calendario_ics\n"
  ],
  [
   "        raise HTTPException(status_code=400, detail=str(e))\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip: {e}\")\n\n\n@app.get(\"/api/dashboard/ventas-pv\")\n",
   "        raise HTTPException(status_code=400, detail=str(e))\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip: {e}\")\n\n\n@app.get(\"/api/direccion/pdf/pedidos/{tipo}\")\ndef api_direccion_pdf_pedidos(tipo: str, request: Request, usuario: dict = Depends(requiere_dashboard)):\n    \"\"\"PDF de Pedidos pendientes (Dirección → Consultas): tipo = 'pedido' (uno, ids=docto_ve_id),\n    'pedidos' (todos o los marcados, uno por hoja) o 'productos' (artículos sumados de todos o los marcados).\n    Mismos parámetros que la consulta (sucursal_venta, periodo o rango AAAA-MM-DD..AAAA-MM-DD).\"\"\"\n    if tipo not in (\"pedido\", \"pedidos\", \"productos\"):\n        raise HTTPException(status_code=404, detail=\"Tipo de PDF desconocido\")\n    config = _config_microsip_o_error(usuario)\n    params = dict(request.query_params)\n    if tipo == \"pedido\" and not str(params.get(\"ids\") or \"\").strip():\n        raise HTTPException(status_code=400, detail=\"Falta el pedido\")\n    try:\n        r, rango = direccion.pedidos_pendientes(config, params)\n        sucursal = next((s[\"nombre\"] for s in microsip.listar_sucursales_venta(config)\n                         if str(s[\"sucursal_id\"]) == str(params.get(\"sucursal_venta\"))), \"Sucursal\")\n    except ValueError as e:\n        raise HTTPException(status_code=400, detail=str(e))\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"Error consultando Microsip: {e}\")\n    pedidos = r.get(\"pedidos\") or []\n    if not pedidos:\n        raise HTTPException(status_code=404, detail=\"No hay pedidos pendientes con esos datos\")\n    empresa = db.obtener_empresa(usuario[\"empresa_id\"]) or {}\n    if tipo == \"productos\":\n        pdf = pdfs_direccion.pdf_productos(empresa, pedidos, sucursal, rango)\n        nombre = \"productos_pedidos_pendientes.pdf\"\n    else:\n        pdf = pdfs_direccion.pdf_pedidos(empresa, pedidos, sucursal, rango)\n        nombre = f\"pedido_{pedidos[0].get('folio')}.pdf\" if tipo == \"pedido\" else \"pedidos_pendientes.pdf\"\n    nombre = re.sub(r\"[^A-Za-z0-9_.-]\", \"_\", nombre)\n    return Response(content=pdf, media_type=\"application/pdf\", headers={\"Content-Disposition\": f'attachment; filename=\"{nombre}\"'})\n\n\n@app.get(\"/api/dashboard/ventas-pv\")\n"
  ]
 ],
 "backend/direccion.py": [
  [
   "    \"\"\"'hoy' | 'ayer' | 'semana' | 'mes' | 'mes_anterior' | 'todo' | 'AAAA-MM-DD'\n    → (inicio, fin_exclusivo, etiqueta). 'todo' → (None, None, 'Todo').\"\"\"\n",
   "    \"\"\"'hoy' | 'ayer' | 'semana' | 'mes' | 'mes_anterior' | 'todo' | 'AAAA-MM-DD'\n    | 'AAAA-MM-DD..AAAA-MM-DD' (rango, ambos días incluidos)\n    → (inicio, fin_exclusivo, etiqueta). 'todo' → (None, None, 'Todo').\"\"\"\n"
  ],
  [
   "        return None, None, \"Todo\"\n    if v == \"ayer\":\n",
   "        return None, None, \"Todo\"\n    if \"..\" in v:\n        try:\n            a, b = (datetime.strptime(x.strip(), \"%Y-%m-%d\").date() for x in v.split(\"..\", 1))\n            if b < a:\n                a, b = b, a\n            return a.isoformat(), (b + timedelta(days=1)).isoformat(), f\"{a.strftime('%d/%m/%Y')} – {b.strftime('%d/%m/%Y')}\"\n        except ValueError:\n            pass\n    if v == \"ayer\":\n"
  ],
  [
   "\ndef _c_pedidos(cfg, p):\n    ini, fin, et = rango_periodo(p.get(\"periodo\"), \"todo\")\n",
   "\ndef pedidos_pendientes(cfg, p):\n    \"\"\"Los pedidos pendientes de la sucursal y periodo (o rango de fechas) elegidos.\n    Si vienen `ids` (docto_ve_id separados por coma) solo esos. Lo usan la consulta y sus PDFs.\"\"\"\n    if not str(p.get(\"sucursal_venta\") or \"\").strip():\n        raise ValueError(\"Falta elegir: Sucursal\")\n    ini, fin, et = rango_periodo(p.get(\"periodo\"), \"todo\")\n"
  ],
  [
   "    r = microsip.obtener_pedidos_pendientes_por_sucursal(cfg, int(p[\"sucursal_venta\"]), ini, fin, None)\n    ped = r.get(\"pedidos\") or []\n",
   "    r = microsip.obtener_pedidos_pendientes_por_sucursal(cfg, int(p[\"sucursal_venta\"]), ini, fin, None)\n    ids = {int(x) for x in str(p.get(\"ids\") or \"\").split(\",\") if x.strip().isdigit()}\n    if ids:\n        r[\"pedidos\"] = [x for x in r.get(\"pedidos\") or [] if x.get(\"docto_ve_id\") in ids]\n    return r, et\n\n\ndef _c_pedidos(cfg, p):\n    r, et = pedidos_pendientes(cfg, p)\n    ped = r.get(\"pedidos\") or []\n"
  ],
  [
   "    return {\"subtitulo\": et,\n            \"resumen\": [{\"etiqueta\": \"Pedidos pendientes\", \"valor\": len(ped), \"formato\": \"numero\"},\n",
   "    return {\"subtitulo\": et,\n            # La app dibuja estos botones (PDF de todos los productos / de todos los pedidos); si el\n            # usuario marcó pedidos en la tabla, manda sus docto_ve_id en `ids` y el PDF sale solo con esos.\n            \"descargas\": [{\"etiqueta\": \"PDF de productos\", \"icono\": \"productos\", \"ruta\": \"/api/direccion/pdf/pedidos/productos\",\n                           \"archivo\": \"productos_pedidos_pendientes\"},\n                          {\"etiqueta\": \"PDF de pedidos (uno por hoja)\", \"icono\": \"pedidos\", \"ruta\": \"/api/direccion/pdf/pedidos/pedidos\",\n                           \"archivo\": \"pedidos_pendientes\"}],\n            \"resumen\": [{\"etiqueta\": \"Pedidos pendientes\", \"valor\": len(ped), \"formato\": \"numero\"},\n"
  ],
  [
   "                        \"filas\": [{k: x.get(k) for k in (\"folio\", \"fecha\", \"cliente_nombre\", \"total_piezas_pendientes\", \"total_pedido_con_iva\")} for x in ped]},\n                       {\"titulo\": \"Productos más pedidos\", \"columnas\": [_col(\"nombre\", \"Artículo\"), _col(\"clave\", \"Clave\"),\n                                                                       _col(\"cantidad_pendiente\", \"Piezas\", \"numero\"),\n                                                                       _col(\"valor_total_con_iva\", \"Valor con IVA\", \"dinero\")],\n                        \"filas\": [{k: x.get(k) for k in (\"nombre\", \"clave\", \"cantidad_pendiente\", \"valor_total_con_iva\")}\n                                  for x in (r.get(\"productos_resumen\") or [])[:50]]}]}\n",
   "                        # Se pueden marcar (para los PDF de arriba) y cada uno trae su botón de PDF.\n                        \"seleccion\": {\"id\": \"docto_ve_id\", \"texto\": \"pedido(s)\"},\n                        \"pdf_fila\": {\"ruta\": \"/api/direccion/pdf/pedidos/pedido\", \"nombre\": \"folio\"},\n                        \"filas\": [{k: x.get(k) for k in (\"docto_ve_id\", \"folio\", \"fecha\", \"cliente_nombre\", \"total_piezas_pendientes\", \"total_pedido_con_iva\")}\n                                  for x in ped]},\n                       {\"titulo\": \"Productos pedidos (todos)\", \"columnas\": [_col(\"nombre\", \"Artículo\"), _col(\"clave\", \"Clave\"),\n                                                                           _col(\"cantidad_pendiente\", \"Piezas\", \"numero\"),\n                                                                           _col(\"num_pedidos\", \"En pedidos\", \"numero\"),\n                                                                           _col(\"valor_total_con_iva\", \"Valor con IVA\", \"dinero\")],\n                        \"filas\": [{k: x.get(k) for k in (\"nombre\", \"clave\", \"cantidad_pendiente\", \"num_pedidos\", \"valor_total_con_iva\")}\n                                  for x in (r.get(\"productos_resumen\") or [])]}]}\n"
  ],
  [
   "                    {\"clave\": \"periodo\", \"tipo\": \"periodo\", \"etiqueta\": \"Periodo\", \"defecto\": \"todo\", \"permite_todo\": True}], \"fn\": _c_pedidos},\n",
   "                    {\"clave\": \"periodo\", \"tipo\": \"periodo\", \"etiqueta\": \"Periodo\", \"defecto\": \"todo\", \"permite_todo\": True,\n                     \"permite_rango\": True}], \"fn\": _c_pedidos},\n"
  ]
 ]
}

NUEVOS = {
 "backend/pdfs_direccion.py": "# -*- coding: utf-8 -*-\n\"\"\"PDFs de Dirección → Consultas → Pedidos pendientes (app Mark·Inc):\n- un pedido (sus artículos pendientes de surtir),\n- varios pedidos en un solo archivo (uno por hoja),\n- todos los productos de los pedidos elegidos, sumados (para surtir / comprar).\nMismo estilo que los demás PDFs (logo de la empresa, acento rojo).\"\"\"\nimport base64\nfrom datetime import datetime\nfrom io import BytesIO\nfrom xml.sax.saxutils import escape\nfrom zoneinfo import ZoneInfo\n\nfrom reportlab.lib import colors\nfrom reportlab.lib.pagesizes import letter\nfrom reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet\nfrom reportlab.lib.units import cm\nfrom reportlab.lib.utils import ImageReader\nfrom reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle\n\nROJO = colors.HexColor(\"#D8192F\")\nGRIS = colors.HexColor(\"#74767A\")\nNEGRO = colors.HexColor(\"#1C1E1B\")\nGRIS_CLARO = colors.HexColor(\"#F2F2F2\")\nANCHO = letter[0] - 3 * cm\n\n\ndef _logo(empresa):\n    b64 = (empresa or {}).get(\"logo_base64\")\n    if not b64:\n        return None\n    try:\n        datos = base64.b64decode(b64.split(\",\", 1)[1] if \",\" in b64 else b64)\n        iw, ih = ImageReader(BytesIO(datos)).getSize()\n        alto = 1.4 * cm\n        return Image(BytesIO(datos), width=alto * iw / ih, height=alto)\n    except Exception:\n        return None\n\n\ndef _estilos():\n    s = getSampleStyleSheet()\n    return {\n        \"titulo\": ParagraphStyle(\"t\", parent=s[\"Normal\"], fontName=\"Helvetica-Bold\", fontSize=15, leading=18, textColor=NEGRO),\n        \"sub\": ParagraphStyle(\"s\", parent=s[\"Normal\"], fontSize=9, leading=12, textColor=GRIS),\n        \"celda\": ParagraphStyle(\"c\", parent=s[\"Normal\"], fontSize=8.5, leading=10.5, textColor=NEGRO),\n        \"celda_b\": ParagraphStyle(\"cb\", parent=s[\"Normal\"], fontName=\"Helvetica-Bold\", fontSize=8.5, leading=10.5, textColor=NEGRO),\n        \"enc\": ParagraphStyle(\"e\", parent=s[\"Normal\"], fontName=\"Helvetica-Bold\", fontSize=8, leading=10, textColor=colors.white),\n        \"dato\": ParagraphStyle(\"d\", parent=s[\"Normal\"], fontSize=9.5, leading=13, textColor=NEGRO),\n    }\n\n\ndef _num(v):\n    try:\n        n = float(v or 0)\n    except (TypeError, ValueError):\n        return \"—\"\n    return f\"{n:,.0f}\" if abs(n - round(n)) < 0.005 else f\"{n:,.2f}\"\n\n\ndef _dinero(v):\n    if v is None:\n        return \"—\"\n    try:\n        return f\"${float(v):,.2f}\"\n    except (TypeError, ValueError):\n        return \"—\"\n\n\ndef _fecha(v):\n    t = str(v or \"\")\n    return f\"{t[8:10]}/{t[5:7]}/{t[0:4]}\" if len(t) >= 10 else t\n\n\ndef _encabezado(el, est, empresa, titulo, sub):\n    logo = _logo(empresa)\n    textos = [Paragraph(escape(titulo), est[\"titulo\"]), Paragraph(sub, est[\"sub\"])]\n    if logo:\n        t = Table([[textos, logo]], colWidths=[ANCHO - 5 * cm, 5 * cm])\n        t.setStyle(TableStyle([(\"VALIGN\", (0, 0), (-1, -1), \"MIDDLE\"), (\"ALIGN\", (1, 0), (1, 0), \"RIGHT\"),\n                               (\"LEFTPADDING\", (0, 0), (-1, -1), 0), (\"RIGHTPADDING\", (0, 0), (-1, -1), 0)]))\n        el.append(t)\n    else:\n        el.extend(textos)\n    el.append(Spacer(1, 4))\n    linea = Table([[\"\"]], colWidths=[ANCHO], rowHeights=[2])\n    linea.setStyle(TableStyle([(\"BACKGROUND\", (0, 0), (-1, -1), ROJO)]))\n    el.append(linea)\n    el.append(Spacer(1, 10))\n\n\ndef _tabla(est, encabezados, filas, anchos, derecha=(), total=None):\n    def p(texto, estilo, col):\n        if col in derecha:\n            estilo = ParagraphStyle(estilo.name + \"_d\", parent=estilo, alignment=2)\n        return Paragraph(escape(str(texto)), estilo)\n    datos = [[p(h, est[\"enc\"], i) for i, h in enumerate(encabezados)]]\n    for f in filas:\n        datos.append([p(c, est[\"celda\"], i) for i, c in enumerate(f)])\n    if total:\n        datos.append([p(c, est[\"celda_b\"], i) for i, c in enumerate(total)])\n    t = Table(datos, colWidths=anchos, repeatRows=1)\n    estilo = [(\"BACKGROUND\", (0, 0), (-1, 0), NEGRO), (\"VALIGN\", (0, 0), (-1, -1), \"MIDDLE\"),\n              (\"LINEBELOW\", (0, 1), (-1, -1), 0.3, colors.HexColor(\"#DDDDDD\")),\n              (\"TOPPADDING\", (0, 0), (-1, -1), 4), (\"BOTTOMPADDING\", (0, 0), (-1, -1), 4)]\n    for i in range(1, len(datos)):\n        if i % 2 == 0:\n            estilo.append((\"BACKGROUND\", (0, i), (-1, i), GRIS_CLARO))\n    if total:\n        estilo += [(\"BACKGROUND\", (0, len(datos) - 1), (-1, len(datos) - 1), colors.HexColor(\"#FDE8EA\")),\n                   (\"LINEABOVE\", (0, len(datos) - 1), (-1, len(datos) - 1), 1, ROJO)]\n    t.setStyle(TableStyle(estilo))\n    return t\n\n\ndef _pie(texto):\n    def pie(canvas, doc_):\n        canvas.saveState()\n        canvas.setFont(\"Helvetica\", 7.5)\n        canvas.setFillColor(GRIS)\n        ahora = datetime.now(ZoneInfo(\"America/Mexico_City\")).strftime(\"%d/%m/%Y %H:%M\")\n        canvas.drawString(1.5 * cm, 1.1 * cm, f\"{texto} · generado el {ahora}\")\n        canvas.drawRightString(letter[0] - 1.5 * cm, 1.1 * cm, f\"Hoja {doc_.page}\")\n        canvas.restoreState()\n    return pie\n\n\ndef _documento(buffer):\n    return SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.4 * cm, bottomMargin=1.7 * cm,\n                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)\n\n\ndef _bloque_pedido(el, est, empresa, pedido, sucursal, rango):\n    _encabezado(el, est, empresa, f\"Pedido {pedido.get('folio') or ''}\",\n                f\"Pendiente de surtir · {escape(sucursal)}\")\n    datos = [\n        [\"Cliente:\", pedido.get(\"cliente_nombre\") or \"—\", \"Fecha:\", _fecha(pedido.get(\"fecha\"))],\n        [\"Capturó:\", pedido.get(\"capturado_por\") or \"—\", \"Periodo:\", rango],\n    ]\n    t = Table([[Paragraph(f\"<b>{escape(str(a))}</b>\", est[\"dato\"]) if i % 2 == 0 else Paragraph(escape(str(a)), est[\"dato\"])\n                for i, a in enumerate(f)] for f in datos], colWidths=[2.2 * cm, ANCHO / 2 - 2.2 * cm, 2 * cm, ANCHO / 2 - 2 * cm])\n    t.setStyle(TableStyle([(\"LEFTPADDING\", (0, 0), (-1, -1), 0), (\"BOTTOMPADDING\", (0, 0), (-1, -1), 2)]))\n    el.append(t)\n    el.append(Spacer(1, 10))\n    items = pedido.get(\"items\") or []\n    filas = [[i.get(\"clave\") or \"\", i.get(\"nombre\") or \"\", _num(i.get(\"cantidad_pendiente\")),\n              _dinero(i.get(\"precio_unitario_con_iva\")), _dinero(i.get(\"total_con_iva\"))] for i in items]\n    total = [\"\", f\"{len(items)} artículo(s)\", _num(pedido.get(\"total_piezas_pendientes\")), \"\",\n             _dinero(pedido.get(\"total_pedido_con_iva\"))]\n    el.append(_tabla(est, [\"Clave\", \"Artículo\", \"Piezas\", \"Precio c/IVA\", \"Importe c/IVA\"], filas,\n                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 2.7 * cm - 3 * cm, 2 * cm, 2.7 * cm, 3 * cm], derecha=(2, 3, 4), total=total))\n\n\ndef pdf_pedidos(empresa, pedidos, sucursal, rango):\n    \"\"\"Un PDF con uno o varios pedidos, cada uno en su hoja.\"\"\"\n    buffer = BytesIO()\n    doc = _documento(buffer)\n    est = _estilos()\n    el = []\n    for i, p in enumerate(pedidos):\n        if i:\n            el.append(PageBreak())\n        _bloque_pedido(el, est, empresa, p, sucursal, rango)\n    if not el:\n        el.append(Paragraph(\"No hay pedidos pendientes con esos datos.\", est[\"dato\"]))\n    texto = f\"Pedido {pedidos[0].get('folio')}\" if len(pedidos) == 1 else f\"{len(pedidos)} pedidos pendientes · {sucursal}\"\n    doc.build(el, onFirstPage=_pie(texto), onLaterPages=_pie(texto))\n    return buffer.getvalue()\n\n\ndef pdf_productos(empresa, pedidos, sucursal, rango):\n    \"\"\"Todos los artículos de los pedidos, sumados (cuántas piezas y en cuántos pedidos).\"\"\"\n    suma = {}\n    for p in pedidos:\n        for it in p.get(\"items\") or []:\n            k = it.get(\"articulo_id\") or f\"{it.get('clave')}|{it.get('nombre')}\"\n            s = suma.setdefault(k, {\"clave\": it.get(\"clave\") or \"\", \"nombre\": it.get(\"nombre\") or \"\", \"piezas\": 0.0,\n                                    \"pedidos\": set(), \"importe\": 0.0})\n            s[\"piezas\"] += float(it.get(\"cantidad_pendiente\") or 0)\n            s[\"pedidos\"].add(p.get(\"folio\"))\n            s[\"importe\"] += float(it.get(\"total_con_iva\") or 0)\n    filas = sorted(suma.values(), key=lambda s: (-s[\"piezas\"], s[\"nombre\"]))\n    buffer = BytesIO()\n    doc = _documento(buffer)\n    est = _estilos()\n    el = []\n    folios = \", \".join(str(p.get(\"folio\")) for p in pedidos[:40]) + (f\" y {len(pedidos) - 40} más\" if len(pedidos) > 40 else \"\")\n    _encabezado(el, est, empresa, \"Productos de pedidos pendientes\",\n                f\"{escape(sucursal)} · {escape(rango)} · {len(pedidos)} pedido(s): {escape(folios)}\")\n    tabla = [[s[\"clave\"], s[\"nombre\"], _num(s[\"piezas\"]), str(len(s[\"pedidos\"])), _dinero(s[\"importe\"])] for s in filas]\n    total = [\"\", f\"{len(filas)} artículo(s)\", _num(sum(s[\"piezas\"] for s in filas)), str(len(pedidos)),\n             _dinero(sum(s[\"importe\"] for s in filas))]\n    el.append(_tabla(est, [\"Clave\", \"Artículo\", \"Piezas\", \"Pedidos\", \"Importe c/IVA\"], tabla,\n                     [2.6 * cm, ANCHO - 2.6 * cm - 2 * cm - 1.8 * cm - 3 * cm, 2 * cm, 1.8 * cm, 3 * cm], derecha=(2, 3, 4), total=total))\n    doc.build(el, onFirstPage=_pie(\"Productos de pedidos pendientes\"), onLaterPages=_pie(\"Productos de pedidos pendientes\"))\n    return buffer.getvalue()\n"
}


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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_direccion_pedidos_pdf.py")
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
