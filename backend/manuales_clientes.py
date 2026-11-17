"""Portal de bienvenida para clientes: lectura de Microsip (solo lectura), emparejar
lo que compró el cliente con los equipos que tienen manuales, y la hoja de QR.

Un folio puede ser de pedido (P), remisión (R) o factura (F). Se buscan también los
documentos ligados en DOCTOS_VE_LIGAS (pedido -> remisión -> factura), así da igual
cuál folio tenga el doctor a la mano.
"""
import io
import re
import unicodedata

TIPOS_COMPRA = ("P", "R", "F")
NOMBRE_TIPO = {"P": "Pedido", "R": "Remisión", "F": "Factura", "C": "Cotización", "D": "Devolución"}


class FolioAmbiguo(ValueError):
    pass


def normalizar(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _partir_folio(folio):
    """'p-000123' -> ('P', '123'). Acepta con o sin letras y con o sin ceros."""
    t = normalizar(folio).replace(" ", "")
    m = re.fullmatch(r"([A-Z]*)[-_/]?0*(\d+)", t)
    if not m:
        return None
    return m.group(1), (m.group(2).lstrip("0") or "0")


def _existe_tabla(cur, tabla):
    cur.execute("SELECT 1 FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = ?", (tabla,))
    return cur.fetchone() is not None


def _fecha(v):
    try:
        return v.strftime("%Y-%m-%d")
    except Exception:
        return str(v or "")[:10]


def compra_por_folio(conectar, config, folio):
    """Regresa None si no hay ningún pedido/remisión/factura vigente con ese folio.
    Si el número coincide con documentos de clientes distintos (p. ej. escribieron
    solo el número y existe P123 y F123), lanza FolioAmbiguo para pedir el folio
    con su letra."""
    partes = _partir_folio(folio)
    if not partes:
        raise ValueError("Escribe el folio tal como aparece en tu pedido, factura o remisión (por ejemplo P0012345).")
    prefijo, numero = partes
    con = conectar(config)
    try:
        cur = con.cursor()
        cur.execute(f"""
            SELECT DOCTO_VE_ID, FOLIO, TIPO_DOCTO, CLIENTE_ID, FECHA, ESTATUS
            FROM DOCTOS_VE
            WHERE TIPO_DOCTO IN ({",".join("?" for _ in TIPOS_COMPRA)})
              AND FOLIO STARTING WITH ? AND FOLIO CONTAINING ?
        """, (*TIPOS_COMPRA, prefijo, numero))
        encontrados = {}
        for docto_id, folio_db, tipo, cliente_id, fecha, estatus in cur.fetchall():
            if (estatus or "").strip().upper() == "C":
                continue  # cancelado
            p = _partir_folio(folio_db)
            if not p or p[1] != numero or (prefijo and p[0] != prefijo):
                continue
            encontrados[docto_id] = {"id": docto_id, "folio": (folio_db or "").strip(), "tipo": (tipo or "").strip(),
                                     "cliente_id": cliente_id, "fecha": _fecha(fecha)}
        if not encontrados:
            return None
        clientes = {d["cliente_id"] for d in encontrados.values()}
        if len(clientes) > 1:
            ejemplos = ", ".join(f"{d['folio']} ({NOMBRE_TIPO.get(d['tipo'], d['tipo'])})" for d in encontrados.values())
            raise FolioAmbiguo(f"Hay varios documentos con ese número: {ejemplos}. Escribe el folio completo, con su letra.")
        cliente_id = clientes.pop()

        # Documentos ligados (pedido -> remisión -> factura), del mismo cliente.
        if _existe_tabla(cur, "DOCTOS_VE_LIGAS"):
            for _ in range(3):
                ids = list(encontrados.keys())
                marcas = ",".join("?" for _ in ids)
                cur.execute(f"""SELECT DOCTO_VE_FTE_ID, DOCTO_VE_DEST_ID FROM DOCTOS_VE_LIGAS
                                WHERE DOCTO_VE_FTE_ID IN ({marcas}) OR DOCTO_VE_DEST_ID IN ({marcas})""", (*ids, *ids))
                nuevos = {x for fila in cur.fetchall() for x in fila if x and x not in encontrados}
                if not nuevos:
                    break
                marcas2 = ",".join("?" for _ in nuevos)
                cur.execute(f"""SELECT DOCTO_VE_ID, FOLIO, TIPO_DOCTO, CLIENTE_ID, FECHA, ESTATUS FROM DOCTOS_VE
                                WHERE DOCTO_VE_ID IN ({marcas2})""", tuple(nuevos))
                agregados = 0
                for docto_id, folio_db, tipo, cli, fecha, estatus in cur.fetchall():
                    if cli != cliente_id or (tipo or "").strip() not in TIPOS_COMPRA or (estatus or "").strip().upper() == "C":
                        continue
                    encontrados[docto_id] = {"id": docto_id, "folio": (folio_db or "").strip(), "tipo": (tipo or "").strip(),
                                             "cliente_id": cli, "fecha": _fecha(fecha)}
                    agregados += 1
                if not agregados:
                    break

        ids = list(encontrados.keys())
        marcas = ",".join("?" for _ in ids)
        cur.execute(f"""SELECT d.ARTICULO_ID, d.CLAVE_ARTICULO, a.NOMBRE, d.UNIDADES
                        FROM DOCTOS_VE_DET d LEFT JOIN ARTICULOS a ON a.ARTICULO_ID = d.ARTICULO_ID
                        WHERE d.DOCTO_VE_ID IN ({marcas})""", tuple(ids))
        articulos = {}
        for articulo_id, clave, nombre, unidades in cur.fetchall():
            llave = articulo_id or f"clave:{clave}"
            a = articulos.setdefault(llave, {"articulo_id": articulo_id, "claves": set(), "nombre": (nombre or "").strip(),
                                             "unidades": 0})
            if clave:
                a["claves"].add(clave.strip().upper())
            a["unidades"] = max(a["unidades"], float(unidades or 0))  # pedido y factura repiten lo mismo
        con_id = [a["articulo_id"] for a in articulos.values() if a["articulo_id"]]
        if con_id:
            cur.execute(f"""SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS
                            WHERE ARTICULO_ID IN ({",".join("?" for _ in con_id)})""", tuple(con_id))
            for articulo_id, clave in cur.fetchall():
                if clave and articulo_id in articulos:
                    articulos[articulo_id]["claves"].add(clave.strip().upper())

        cur.execute("SELECT NOMBRE FROM CLIENTES WHERE CLIENTE_ID = ?", (cliente_id,))
        r = cur.fetchone()
        cliente_nombre = (r[0] if r else "") or ""
        telefono = ""
        try:
            cur.execute("""SELECT TELEFONO1 FROM DIRS_CLIENTES WHERE CLIENTE_ID = ? ORDER BY ES_DIR_PPAL DESC""", (cliente_id,))
            r = cur.fetchone()
            telefono = ((r[0] if r else "") or "").strip()
        except Exception:
            pass
    finally:
        con.close()

    documentos = sorted(encontrados.values(), key=lambda d: ("PRF".find(d["tipo"]), d["folio"]))
    return {
        "documentos": [{"folio": d["folio"], "tipo": d["tipo"], "tipo_nombre": NOMBRE_TIPO.get(d["tipo"], d["tipo"]),
                        "fecha": d["fecha"]} for d in documentos],
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre.strip(),
        "telefono": telefono,
        "articulos": [{**a, "claves": sorted(a["claves"])} for a in articulos.values()],
    }


def _regla_aplica(regla, articulo):
    tipo, valor = regla["tipo"], regla["valor"]
    if tipo == "articulo":
        return bool(regla.get("articulo_id")) and articulo.get("articulo_id") == regla["articulo_id"]
    if tipo == "clave":
        return normalizar(valor).replace(" ", "") in {c.replace(" ", "") for c in articulo.get("claves", [])}
    if tipo == "texto":
        nombre = normalizar(articulo.get("nombre"))
        palabras = normalizar(valor).split()
        return bool(palabras) and all(p in nombre for p in palabras)
    return False


def emparejar(articulos, equipos):
    """Qué equipos le tocan al cliente. Regresa (equipos_con_motivo, articulos_sin_equipo)."""
    elegidos, usados = [], set()
    for e in equipos:
        if not e.get("activo", True):
            continue
        motivos = []
        for i, a in enumerate(articulos):
            if any(_regla_aplica(r, a) for r in e.get("reglas", [])):
                motivos.append(a.get("nombre") or ", ".join(a.get("claves", [])))
                usados.add(i)
        if motivos or e.get("para_todos"):
            elegidos.append({**e, "motivos": motivos})
    sin_equipo = [a for i, a in enumerate(articulos) if i not in usados]
    # Primero lo que el cliente compró y al final lo general (garantía, bienvenida…).
    elegidos.sort(key=lambda e: (1 if (e.get("para_todos") and not e["motivos"]) else 0, e.get("orden") or 0, e["nombre"]))
    return elegidos, sin_equipo


def youtube_id(url):
    m = re.search(r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})",
                  url or "")
    return m.group(1) if m else None


def pdf_qr(url, empresa_nombre, modo="hoja"):
    """Hoja para imprimir con el QR que lleva al portal. modo='hoja': 6 etiquetas
    por hoja carta (para pegar en las unidades); modo='grande': una por hoja."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    salida = io.BytesIO()
    c = canvas.Canvas(salida, pagesize=letter)
    c.setTitle(f"QR manuales - {empresa_nombre}")
    ancho_pag, alto_pag = letter

    def etiqueta(x, y, w, h, escala):
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setDash(3, 3)
        c.roundRect(x, y, w, h, 8, stroke=1, fill=0)
        c.setDash()
        c.setFillColorRGB(0.1, 0.12, 0.15)
        c.setFont("Helvetica-Bold", 13 * escala)
        c.drawCentredString(x + w / 2, y + h - 1.0 * cm * escala, "Manuales y videos de tu equipo")
        c.setFont("Helvetica", 9.5 * escala)
        c.drawCentredString(x + w / 2, y + h - 1.55 * cm * escala, "Escanea con la cámara de tu celular")
        lado = min(w, h) * 0.58
        qr = QrCodeWidget(url)
        qr.barLevel = "M"
        b = qr.getBounds()
        d = Drawing(lado, lado, transform=[lado / (b[2] - b[0]), 0, 0, lado / (b[3] - b[1]), 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, x + (w - lado) / 2, y + h - 1.85 * cm * escala - lado)
        c.setFont("Helvetica", 8.5 * escala)
        c.drawCentredString(x + w / 2, y + 1.25 * cm * escala, "Ten a la mano el folio de tu pedido, factura o remisión")
        c.setFont("Helvetica-Bold", 8.5 * escala)
        c.drawCentredString(x + w / 2, y + 0.7 * cm * escala, empresa_nombre or "")
        c.setFont("Helvetica", 6.5 * escala)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(x + w / 2, y + 0.3 * cm * escala, url)

    if modo == "grande":
        etiqueta(2 * cm, 3 * cm, ancho_pag - 4 * cm, alto_pag - 6 * cm, 1.7)
    else:
        margen_x, margen_y, sep = 1.2 * cm, 1.2 * cm, 0.5 * cm
        w = (ancho_pag - 2 * margen_x - sep) / 2
        h = (alto_pag - 2 * margen_y - 2 * sep) / 3
        for fila in range(3):
            for col in range(2):
                etiqueta(margen_x + col * (w + sep), margen_y + (2 - fila) * (h + sep), w, h, 1.0)
    c.showPage()
    c.save()
    return salida.getvalue()
