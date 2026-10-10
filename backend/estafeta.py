"""Paquetería Estafeta: cotizar con las tarifas de la cuenta de la empresa,
generar la guía (PDF) y rastrear.

Credenciales (variables de entorno en Render — nunca en el código):
  ESTAFETA_MODO            "produccion" | "pruebas" | "simulado"  (vacío = no conectada)
  ESTAFETA_CLIENTE         número de cliente que da Estafeta
  ESTAFETA_SUSCRIPTOR      número de suscriptor / oficina que da Estafeta
  ESTAFETA_ORG_VENTAS      organización de ventas (Estafeta la indica; por omisión 112)
  ESTAFETA_COTIZAR_KEY / _ID / _SECRET    API de cotización
  ESTAFETA_GUIA_KEY    / _ID / _SECRET    API de guías (etiquetas)
  ESTAFETA_RASTREO_KEY / _ID / _SECRET    API de rastreo
  ESTAFETA_TOKEN_URL, ESTAFETA_COTIZAR_URL, ESTAFETA_GUIA_URL, ESTAFETA_RASTREO_URL
      (opcionales: si Estafeta entrega otras direcciones en su manual)

"simulado" sirve para probar las pantallas sin cuenta: precios inventados y
guías de ejemplo marcadas como SIMULADAS. No usar en producción.

Los formatos de petición/respuesta de Estafeta están aislados en las funciones
_cuerpo_* y _leer_*; cuando Estafeta entregue su manual de integración con las
credenciales, solo se ajustan ahí.
"""
import base64
import io
import math
import os
import threading
import time
from datetime import datetime, timedelta

import requests

URLS = {
    "pruebas": {
        "token": "https://apiqa.estafeta.com:8443/auth/oauth/v2/token",
        "cotizar": "https://wscotizadorqa.estafeta.com/Cotizacion/rest/Cotizador/Cotizacion",
        "guia": "https://labelqa.estafeta.com/v1/wayBills?outputType=FILE_PDF&outputGroup=REQUEST"
                "&responseMode=SYNC_INLINE&printingTemplate=NORMAL_TIPO7_ZEBRAORI",
        "rastreo": "https://trackingqa.estafeta.com/v1/tracking",
    },
    "produccion": {
        "token": "https://api.estafeta.com:8443/auth/oauth/v2/token",
        "cotizar": "https://wscotizador.estafeta.com/Cotizacion/rest/Cotizador/Cotizacion",
        "guia": "https://label.estafeta.com/v1/wayBills?outputType=FILE_PDF&outputGroup=REQUEST"
                "&responseMode=SYNC_INLINE&printingTemplate=NORMAL_TIPO7_ZEBRAORI",
        "rastreo": "https://tracking.estafeta.com/v1/tracking",
    },
}

URL_RASTREO_PUBLICO = "https://www.estafeta.com/Herramientas/Rastreo?wayBillType=1&wayBill={guia}"
NOMBRE_ITEM = "Envío por paquetería Estafeta"
CLAVE_ITEM = "ESTAFETA"
TIEMPO = 30


class ErrorEstafeta(Exception):
    pass


Error = ErrorEstafeta
CLAVE = "estafeta"
NOMBRE = "Estafeta"


def _env(nombre, defecto=""):
    return (os.environ.get(nombre) or defecto).strip()


def modo():
    m = _env("ESTAFETA_MODO").lower()
    return m if m in ("produccion", "pruebas", "simulado") else ""


def simulado():
    return modo() == "simulado"


def _credencial(api):
    p = f"ESTAFETA_{api.upper()}_"
    return {"key": _env(p + "KEY"), "id": _env(p + "ID"), "secret": _env(p + "SECRET")}


def estado():
    """Para la pantalla del administrador: qué falta configurar (sin secretos)."""
    m = modo()
    faltan = []
    if not m:
        faltan.append("ESTAFETA_MODO")
    elif m != "simulado":
        for v in ("ESTAFETA_CLIENTE", "ESTAFETA_SUSCRIPTOR"):
            if not _env(v):
                faltan.append(v)
        for api in ("cotizar", "guia", "rastreo"):
            c = _credencial(api)
            for k in ("key", "id", "secret"):
                if not c[k]:
                    faltan.append(f"ESTAFETA_{api.upper()}_{k.upper()}")
    return {"modo": m or None, "conectada": bool(m) and not faltan, "simulado": m == "simulado", "faltan": faltan}


def _verificar(api):
    e = estado()
    if not e["modo"]:
        raise ErrorEstafeta("Estafeta todavía no está conectada (falta configurar la cuenta en Render).")
    if e["simulado"]:
        return
    requeridas = ["ESTAFETA_CLIENTE", "ESTAFETA_SUSCRIPTOR"] + [f"ESTAFETA_{api.upper()}_{k}" for k in ("KEY", "ID", "SECRET")]
    faltan = [v for v in requeridas if not _env(v)]
    if faltan:
        raise ErrorEstafeta("Faltan datos de la cuenta Estafeta en Render: " + ", ".join(faltan))


def _url(tipo):
    propia = _env(f"ESTAFETA_{tipo.upper()}_URL")
    if propia:
        return propia
    return URLS["produccion" if modo() == "produccion" else "pruebas"][tipo]


# ---------- Token OAuth (client_credentials), uno por API, en caché ----------

_tokens = {}
_candado = threading.Lock()


def _token(api):
    with _candado:
        t = _tokens.get(api)
        if t and t[1] > time.time() + 60:
            return t[0]
    c = _credencial(api)
    try:
        r = requests.post(_url("token"), data={"grant_type": "client_credentials", "scope": "execute",
                                               "client_id": c["id"], "client_secret": c["secret"]},
                          headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=TIEMPO)
    except requests.RequestException as e:
        raise ErrorEstafeta(f"No se pudo conectar con Estafeta ({e.__class__.__name__}).")
    if r.status_code != 200:
        raise ErrorEstafeta(f"Estafeta rechazó las credenciales de {api} (HTTP {r.status_code}). Revisa ID y secreto.")
    d = r.json()
    valor = d.get("access_token")
    if not valor:
        raise ErrorEstafeta("Estafeta no regresó el token de acceso.")
    with _candado:
        _tokens[api] = (valor, time.time() + int(d.get("expires_in") or 3000))
    return valor


def _post(api, url, cuerpo):
    c = _credencial(api)
    try:
        r = requests.post(url, json=cuerpo, timeout=TIEMPO, headers={
            "Authorization": f"Bearer {_token(api)}", "apikey": c["key"], "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise ErrorEstafeta(f"No se pudo conectar con Estafeta ({e.__class__.__name__}).")
    try:
        datos = r.json()
    except ValueError:
        datos = None
    if r.status_code >= 400:
        raise ErrorEstafeta(f"Estafeta respondió con error (HTTP {r.status_code}): {_mensaje(datos) or r.text[:200]}")
    return datos


def _mensaje(d):
    if isinstance(d, dict):
        for k in ("message", "Message", "DescError", "descripcion", "description", "error_description", "error"):
            if d.get(k):
                return str(d[k])[:300]
    return ""


# ---------- Validaciones / utilidades ----------

def cp_valido(cp):
    cp = (cp or "").strip()
    return len(cp) == 5 and cp.isdigit()


def limpiar_paquete(p):
    try:
        peso = float(p.get("peso") or 0)
        largo, ancho, alto = (float(p.get(k) or 0) for k in ("largo", "ancho", "alto"))
    except (TypeError, ValueError):
        raise ErrorEstafeta("Peso y medidas deben ser números.")
    if peso <= 0 or peso > 70:
        raise ErrorEstafeta("El peso debe ser mayor a 0 y máximo 70 kg por paquete.")
    if min(largo, ancho, alto) <= 0 or max(largo, ancho, alto) > 300:
        raise ErrorEstafeta("Escribe largo, ancho y alto en centímetros (máximo 300 cm).")
    return {"peso": round(peso, 2), "largo": round(largo, 1), "ancho": round(ancho, 1), "alto": round(alto, 1)}


def peso_volumetrico(p):
    return round(p["largo"] * p["ancho"] * p["alto"] / 5000, 2)


def precio_con_margen(costo, margen_pct):
    """Precio al cliente: costo Estafeta + margen, redondeado hacia arriba al peso."""
    return float(math.ceil(float(costo) * (1 + max(0.0, float(margen_pct or 0)) / 100) - 1e-9))


# ---------- Cotizar ----------

def cotizar(cp_origen, cp_destino, paquete):
    """Lista de servicios disponibles: [{servicio_id, servicio, costo, dias}] (costo con IVA)."""
    if not cp_valido(cp_origen) or not cp_valido(cp_destino):
        raise ErrorEstafeta("Los códigos postales deben tener 5 dígitos.")
    paquete = limpiar_paquete(paquete)
    _verificar("cotizar")
    if simulado():
        return _cotizar_simulado(cp_origen, cp_destino, paquete)
    datos = _post("cotizar", _url("cotizar"), _cuerpo_cotizar(cp_origen, cp_destino, paquete))
    servicios = _leer_cotizacion(datos)
    if not servicios:
        raise ErrorEstafeta(_mensaje(datos) or "Estafeta no tiene servicio para ese código postal con ese paquete.")
    return servicios


def _cuerpo_cotizar(cp_origen, cp_destino, p):
    return {
        "Origin": cp_origen,
        "Destination": [cp_destino],
        "PackagingType": "Paquete",
        "IsInternational": False,
        "Dimensions": {"Length": p["largo"], "Width": p["ancho"], "Height": p["alto"], "Weight": p["peso"]},
        "CustomerNumber": _env("ESTAFETA_CLIENTE"),
    }


def _primero(d, *claves):
    for k in claves:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def _leer_cotizacion(datos):
    """Acepta las variantes de respuesta conocidas (lista de servicios dentro
    de Quotation / TipoServicio / Services)."""
    candidatos = []

    def recorrer(x):
        if isinstance(x, list):
            for i in x:
                recorrer(i)
        elif isinstance(x, dict):
            nombre = _primero(x, "ServiceName", "DescripcionServicio", "serviceName", "Description", "Servicio")
            total = _primero(x, "TotalAmount", "CostoTotal", "totalAmount", "Total", "ListPrice")
            if nombre and total is not None:
                candidatos.append(x)
            for v in x.values():
                if isinstance(v, (list, dict)):
                    recorrer(v)

    recorrer(datos)
    r = []
    for s in candidatos:
        try:
            costo = float(str(_primero(s, "TotalAmount", "CostoTotal", "totalAmount", "Total", "ListPrice")).replace(",", ""))
        except ValueError:
            continue
        if costo <= 0:
            continue
        r.append({
            "servicio_id": str(_primero(s, "ServiceId", "ServiceTypeId", "serviceTypeId", "IdServicio") or _primero(s, "ServiceName", "DescripcionServicio")),
            "servicio": str(_primero(s, "ServiceName", "DescripcionServicio", "serviceName", "Description", "Servicio")).strip(),
            "costo": round(costo, 2),
            "dias": _primero(s, "DeliveryTime", "DiasEntrega", "deliveryDays", "TiempoEntrega"),
        })
    vistos, unicos = set(), []
    for s in sorted(r, key=lambda s: s["costo"]):
        if s["servicio_id"] not in vistos:
            vistos.add(s["servicio_id"])
            unicos.append(s)
    return unicos


def _cotizar_simulado(cp_o, cp_d, p):
    zona = min(8, abs(int(cp_o[:2]) - int(cp_d[:2])) // 6 + 1)
    kg = max(p["peso"], peso_volumetrico(p))
    terrestre = 95 + zona * 18 + max(0, kg - 1) * (9 + zona * 2)
    return [
        {"servicio_id": "70", "servicio": "Terrestre (SIMULADO)", "costo": round(terrestre * 1.16, 2), "dias": f"{1 + zona // 2}-{2 + zona // 2} días"},
        {"servicio_id": "60", "servicio": "Día siguiente (SIMULADO)", "costo": round(terrestre * 1.75 * 1.16, 2), "dias": "1 día"},
    ]


# ---------- Guía ----------

def generar_guia(origen, destino, paquete, servicio_id, referencia, contenido):
    """origen/destino: {nombre, contacto, telefono, calle, numero, colonia, cp, ciudad, estado, referencia}.
    Regresa {guia, codigo_rastreo, pdf_base64, simulada}."""
    paquete = limpiar_paquete(paquete)
    for quien, d in (("origen", origen), ("destino", destino)):
        faltan = [c for c in ("nombre", "telefono", "calle", "colonia", "cp", "ciudad", "estado") if not (d.get(c) or "").strip()]
        if faltan:
            raise ErrorEstafeta(f"Faltan datos del {quien}: {', '.join(faltan)}.")
        if not cp_valido(d.get("cp")):
            raise ErrorEstafeta(f"El código postal del {quien} debe tener 5 dígitos.")
    _verificar("guia")
    if simulado():
        return _guia_simulada(origen, destino, paquete, servicio_id, referencia)
    datos = _post("guia", _url("guia"), _cuerpo_guia(origen, destino, paquete, servicio_id, referencia, contenido))
    return _leer_guia(datos)


def _contacto(d):
    return {
        "corporateName": (d.get("nombre") or "")[:50],
        "contactName": (d.get("contacto") or d.get("nombre") or "")[:30],
        "cellPhone": "".join(ch for ch in (d.get("telefono") or "") if ch.isdigit())[-10:],
        "telephone": "".join(ch for ch in (d.get("telefono") or "") if ch.isdigit())[-10:],
        "email": (d.get("correo") or "")[:100],
    }


def _domicilio(d):
    return {
        "bUsedCode": False,
        "roadTypeAbbName": "C.",
        "roadName": (d.get("calle") or "")[:50],
        "externalNum": (d.get("numero") or "S/N")[:10],
        "settlementTypeAbbName": "Col.",
        "settlementName": (d.get("colonia") or "")[:50],
        "townshipName": (d.get("ciudad") or "")[:50],
        "stateAbbName": (d.get("estado") or "")[:50],
        "zipCode": d.get("cp"),
        "countryCode": "484",
        "countryName": "MEX",
        "addressReference": (d.get("referencia") or "")[:50],
    }


def _cuerpo_guia(origen, destino, p, servicio_id, referencia, contenido):
    return {
        "identification": {"suscriberId": _env("ESTAFETA_SUSCRIPTOR"), "customerNumber": _env("ESTAFETA_CLIENTE")},
        "systemInformation": {"id": "AP01", "name": "AP01", "version": "1.10.20"},
        "labelDefinition": {
            "wayBillDocument": {"content": (contenido or "Mercancía")[:25], "referenceNumber": (referencia or "")[:30]},
            "itemDescription": {"parcelId": 4, "weight": p["peso"], "height": p["alto"], "length": p["largo"], "width": p["ancho"]},
            "serviceConfiguration": {
                "quantityOfLabels": 1, "serviceTypeId": str(servicio_id or "70"),
                "salesOrganization": _env("ESTAFETA_ORG_VENTAS", "112"),
                "effectiveDate": datetime.now().strftime("%Y%m%d"),
                "originZipCodeForRouting": origen.get("cp"), "isInsurance": False, "isReturnDocument": False,
            },
            "location": {
                "isDRAAlternative": False,
                "origin": {"contact": _contacto(origen), "address": _domicilio(origen)},
                "destination": {"isDeliveryToPUDO": False,
                                "homeAddress": {"contact": _contacto(destino), "address": _domicilio(destino)}},
            },
        },
    }


def _leer_guia(datos):
    pdf = _primero(datos, "data", "Data", "labelPDF", "pdf")
    guia = None

    def buscar(x):
        nonlocal guia
        if guia:
            return
        if isinstance(x, dict):
            g = _primero(x, "wayBill", "WayBill", "waybill", "guia", "numeroGuia")
            if g:
                guia = str(g)
                return
            for v in x.values():
                buscar(v)
        elif isinstance(x, list):
            for v in x:
                buscar(v)

    buscar(datos)
    if not pdf or not guia:
        raise ErrorEstafeta(_mensaje(datos) or "Estafeta no regresó la guía.")
    codigo = None
    if isinstance(datos, dict):
        def buscar_codigo(x):
            nonlocal codigo
            if codigo:
                return
            if isinstance(x, dict):
                c = _primero(x, "trackingCode", "TrackingCode", "codigoRastreo")
                if c:
                    codigo = str(c)
                    return
                for v in x.values():
                    buscar_codigo(v)
            elif isinstance(x, list):
                for v in x:
                    buscar_codigo(v)
        buscar_codigo(datos)
    return {"guia": guia, "codigo_rastreo": codigo or guia, "pdf_base64": pdf, "simulada": False}


def _guia_simulada(origen, destino, p, servicio_id, referencia, marca="ESTAFETA", prefijo="SIM"):
    from reportlab.lib.pagesizes import inch
    from reportlab.pdfgen import canvas

    guia = prefijo + datetime.now().strftime("%y%m%d%H%M%S") + "0000000"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(4 * inch, 6 * inch))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(14, 6 * inch - 30, f"{marca} — GUÍA SIMULADA")
    c.setFont("Helvetica", 9)
    y = 6 * inch - 55
    for linea in [
        "NO ES UNA GUÍA REAL — solo prueba del sistema",
        f"Guía: {guia}", f"Servicio: {servicio_id}", f"Referencia: {referencia or ''}",
        "", "REMITENTE:", origen.get("nombre", ""), f"{origen.get('calle', '')} {origen.get('numero', '')}",
        f"{origen.get('colonia', '')}, CP {origen.get('cp', '')}", f"{origen.get('ciudad', '')}, {origen.get('estado', '')}",
        "", "DESTINATARIO:", destino.get("nombre", ""), f"{destino.get('calle', '')} {destino.get('numero', '')}",
        f"{destino.get('colonia', '')}, CP {destino.get('cp', '')}", f"{destino.get('ciudad', '')}, {destino.get('estado', '')}",
        f"Tel: {destino.get('telefono', '')}",
        "", f"Paquete: {p['peso']} kg — {p['largo']}x{p['ancho']}x{p['alto']} cm",
    ]:
        c.drawString(14, y, linea[:60])
        y -= 13
    c.showPage()
    c.save()
    return {"guia": guia, "codigo_rastreo": guia, "pdf_base64": base64.b64encode(buf.getvalue()).decode(), "simulada": True}


# ---------- Rastreo ----------

def url_rastreo(guia):
    return URL_RASTREO_PUBLICO.format(guia=guia)


def rastreo_simulado(guia, creada_en, url):
    return rastrear(guia, simulada=True, creada_en=creada_en, url=url)


def rastrear(guia, simulada=False, creada_en=None, url=None):
    """{estatus, eventos: [{fecha, descripcion, lugar}], url}."""
    url = url or url_rastreo(guia)
    if simulada or simulado():
        base = datetime.fromisoformat(creada_en) if creada_en else datetime.now()
        pasos = [(0, "Guía generada (simulada)", "Origen"), (6, "Recolectado", "Origen"),
                 (20, "En tránsito", "Centro de distribución"), (44, "En ruta de entrega", "Destino"),
                 (50, "Entregado", "Destino")]
        horas = (datetime.now() - base).total_seconds() / 3600
        eventos = [{"fecha": (base + timedelta(hours=h)).isoformat(timespec="minutes"), "descripcion": d, "lugar": l}
                   for h, d, l in pasos if h <= max(horas, 0)]
        return {"estatus": eventos[-1]["descripcion"], "eventos": list(reversed(eventos)), "url": url}
    _verificar("rastreo")
    datos = _post("rastreo", _url("rastreo"), {
        "suscriberId": _env("ESTAFETA_SUSCRIPTOR"), "customerNumber": _env("ESTAFETA_CLIENTE"),
        "searchType": "LIST", "itemsSearch": [guia], "historyConfiguration": {"includeHistory": True}})
    return _leer_rastreo(datos, url)


def _leer_rastreo(datos, url):
    eventos = []

    def recorrer(x):
        if isinstance(x, list):
            for i in x:
                recorrer(i)
        elif isinstance(x, dict):
            desc = _primero(x, "eventDescriptionSPA", "description", "Descripcion", "eventDescription", "spanishName")
            fecha = _primero(x, "eventDateTime", "eventDate", "Fecha", "date")
            if desc and fecha:
                eventos.append({"fecha": str(fecha), "descripcion": str(desc),
                                "lugar": str(_primero(x, "eventPlaceName", "lugar", "place", "officeName") or "")})
            for v in x.values():
                if isinstance(v, (list, dict)):
                    recorrer(v)

    recorrer(datos)
    estatus = None
    if isinstance(datos, dict):
        def buscar(x):
            nonlocal estatus
            if estatus:
                return
            if isinstance(x, dict):
                s = _primero(x, "statusSPA", "status", "Estatus", "statusDescription")
                if isinstance(s, str):
                    estatus = s
                    return
                for v in x.values():
                    buscar(v)
            elif isinstance(x, list):
                for v in x:
                    buscar(v)
        buscar(datos)
    eventos.sort(key=lambda e: e["fecha"], reverse=True)
    return {"estatus": estatus or (eventos[0]["descripcion"] if eventos else "Sin movimientos todavía"),
            "eventos": eventos, "url": url}
