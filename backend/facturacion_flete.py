"""Aceptación de cotizaciones: datos fiscales del cliente (con lectura de la
Constancia de Situación Fiscal por IA) y cálculo del flete de instalación
por horas de manejo.

Tiempo de manejo: OpenRouteService (gratis con clave, 2,000 rutas/día).
  OPENROUTESERVICE_API_KEY   la clave de openrouteservice.org
El código postal se ubica con el geocodificador de OpenRouteService y, si
no lo encuentra, con Nominatim (OpenStreetMap) como respaldo.
"""
import base64
import os
import re

import requests

import constancia_sat
import ia

# OpenRouteService cambió a la puerta de enlace de HeiGIT (api.heigit.org):
#   rutas:   /openrouteservice/v2/directions/{perfil}
#   geocodif.: /pelias/v1/search/structured
# Se intenta primero la dirección nueva y, si no responde (404 / sin
# conexión), la anterior (api.openrouteservice.org).
# (rutas, geocodificación)
_ORS_BASES = [
    ("https://api.heigit.org/openrouteservice", "https://api.heigit.org/pelias/v1"),
    ("https://api.openrouteservice.org", "https://api.openrouteservice.org/geocode"),
]
if os.getenv("OPENROUTESERVICE_URL"):  # para pruebas / servidor propio
    _b = os.getenv("OPENROUTESERVICE_URL").rstrip("/")
    _ORS_BASES = [(_b, f"{_b}/geocode")]
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/")
TIMEOUT = 20

NOMBRE_ITEM_FLETE = "Flete en instalación"

REGIMENES_FISCALES = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses",
    "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
}

USOS_CFDI = {
    "G01": "Adquisición de mercancías",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I04": "Equipo de cómputo y accesorios",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
}

_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


class ErrorFlete(Exception):
    """Mensaje entendible para el vendedor."""


def rfc_valido(rfc: str) -> bool:
    return bool(_RFC_RE.match((rfc or "").strip().upper()))


def cp_valido(cp: str) -> bool:
    return bool(re.fullmatch(r"\d{5}", (cp or "").strip()))


# ---------- Constancia de Situación Fiscal (IA) ----------

PROMPT_CONSTANCIA = """Este documento es una CONSTANCIA DE SITUACIÓN FISCAL del SAT (México). \
Extrae los datos del contribuyente y responde SOLO este JSON:
{"rfc": "...", "razon_social": "...", "regimen_fiscal": "612", "codigo_postal": "44100",
 "calle": "...", "numero_exterior": "...", "numero_interior": "...", "colonia": "...",
 "municipio": "...", "estado": "...", "correo": "..."}

Reglas:
- rfc: tal cual, en mayúsculas.
- razon_social: para persona moral, la "Denominación/Razón Social" SIN el régimen capital \
(sin "SA DE CV", "S DE RL", etc., que vienen aparte en "Régimen Capital"). Para persona \
física: Nombre(s) + Primer Apellido + Segundo Apellido, en mayúsculas, como aparecen.
- regimen_fiscal: SOLO la clave numérica de 3 dígitos del catálogo del SAT del régimen \
vigente (si hay varios, el primero de la tabla de regímenes). Claves: 601 General de Ley \
Personas Morales, 603 Fines no Lucrativos, 605 Sueldos y Salarios, 606 Arrendamiento, \
612 Actividades Empresariales y Profesionales, 616 Sin obligaciones fiscales, 621 \
Incorporación Fiscal, 625 Plataformas Tecnológicas, 626 Régimen Simplificado de Confianza.
- codigo_postal: los 5 dígitos del domicilio fiscal.
- municipio: "Nombre del Municipio o Demarcación Territorial". estado: "Nombre de la Entidad Federativa".
- correo: el correo electrónico si aparece.
- Cualquier dato que no aparezca: null. No inventes nada."""

_CAMPOS_CONSTANCIA = ["rfc", "razon_social", "regimen_fiscal", "codigo_postal", "calle", "numero_exterior",
                      "numero_interior", "colonia", "municipio", "estado", "correo"]


def _leer_constancia_ia(datos: bytes, media_type: str, empresa_id=None) -> dict:
    """Último recurso: lee la constancia (PDF o foto) con Claude. Regresa los campos (los que
    no encontró vienen en None). Lanza RuntimeError con mensaje entendible."""
    if media_type == "application/pdf":
        bloque = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                 "data": base64.b64encode(datos).decode()}}
    elif media_type.startswith("image/"):
        bloque = {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                              "data": base64.b64encode(datos).decode()}}
    else:
        raise RuntimeError("Sube la constancia en PDF (o una foto clara).")
    parseado = ia._pedir_json_a_claude([bloque, {"type": "text", "text": PROMPT_CONSTANCIA}], empresa_id,
                                       tipo_consumo="leer_constancia_fiscal")
    if not isinstance(parseado, dict):
        raise RuntimeError("No se pudieron leer los datos de la constancia.")
    r = {}
    for k in _CAMPOS_CONSTANCIA:
        v = parseado.get(k)
        r[k] = (" ".join(str(v).split()) or None) if v not in (None, "") else None
    if r["rfc"]:
        r["rfc"] = r["rfc"].upper().replace(" ", "").replace("-", "")
    if r["regimen_fiscal"]:
        m = re.search(r"\d{3}", r["regimen_fiscal"])
        r["regimen_fiscal"] = m.group(0) if m else None
    if r["codigo_postal"]:
        m = re.search(r"\d{5}", r["codigo_postal"])
        r["codigo_postal"] = m.group(0) if m else None
    return r


def _combinar(base: dict, extra: dict) -> dict:
    r = dict(base or {})
    for k, v in (extra or {}).items():
        if v and not r.get(k):
            r[k] = v
    return r


def leer_constancia(archivo_base64: str, empresa_id=None) -> dict:
    """Lee la Constancia de Situación Fiscal. Orden: 1) texto del PDF (gratis),
    2) QR del PDF/foto → página del SAT, 3) IA. Regresa los campos + "fuente"
    ("pdf", "qr_sat" o "ia"). Lanza RuntimeError con el motivo si nada funcionó."""
    datos, media_type = ia._decodificar_base64(archivo_base64, "application/pdf")
    if not datos:
        raise RuntimeError("El archivo está vacío.")
    es_pdf = datos[:4] == b"%PDF"
    if es_pdf:
        media_type = "application/pdf"
    motivos = []
    parcial = {}
    if es_pdf:
        parcial = constancia_sat.datos_de_texto(constancia_sat.texto_de_pdf(datos))
        if constancia_sat.suficiente(parcial):
            return {**parcial, "fuente": "pdf"}
        motivos.append("el PDF no trae texto legible (¿es escaneado?)")
    qr = constancia_sat.qr_de_pdf(datos) if es_pdf else constancia_sat.qr_de_foto(datos)
    if qr:
        try:
            return {**_combinar(constancia_sat.datos_de_qr(qr), parcial), "fuente": "qr_sat"}
        except constancia_sat.ErrorConstancia as e:
            motivos.append(f"QR: {e}")
    else:
        motivos.append("no se encontró el código QR")
    try:
        return {**_combinar(_leer_constancia_ia(datos, media_type, empresa_id), parcial), "fuente": "ia"}
    except RuntimeError as e:
        motivos.append(f"IA: {e}")
    if any(parcial.values()):
        return {**parcial, "fuente": "pdf"}
    raise RuntimeError("No se pudieron leer los datos de la constancia (" + "; ".join(motivos) + "). Captúralos a mano o escanea el QR.")


def leer_qr(texto_qr: str) -> dict:
    try:
        return {**constancia_sat.datos_de_qr(texto_qr), "fuente": "qr_sat"}
    except constancia_sat.ErrorConstancia as e:
        raise RuntimeError(str(e))


# ---------- Tiempo de manejo (OpenRouteService) ----------

def _ors_key():
    return os.getenv("OPENROUTESERVICE_API_KEY", "").strip()


def ruta_configurada() -> bool:
    return bool(_ors_key())


def _ors_error(resp) -> str:
    try:
        err = resp.json().get("error")
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err or resp.text[:200])
    except Exception:
        return resp.text[:200]


def geocodificar_cp(cp: str, municipio: str | None = None, estado: str | None = None):
    """(lat, lng, texto) del código postal en México. Usa municipio/estado
    si se tienen, para no confundir el CP con otro lugar."""
    key = _ors_key()
    if key:
        params = {"api_key": key, "postalcode": cp, "country": "MX", "size": 1}
        if municipio:
            params["locality"] = municipio
        if estado:
            params["region"] = estado
        sin_extra = {"api_key": key, "postalcode": cp, "country": "MX", "size": 1}
        for _, base_geo in _ORS_BASES:
            respondio = False
            for p in (params, sin_extra):
                try:
                    resp = requests.get(f"{base_geo}/search/structured", params=p,
                                        headers={"Authorization": key}, timeout=TIMEOUT)
                except requests.RequestException:
                    break
                if resp.status_code == 404:
                    break
                respondio = True
                if resp.ok:
                    feats = (resp.json() or {}).get("features") or []
                    if feats:
                        lng, lat = feats[0]["geometry"]["coordinates"][:2]
                        return float(lat), float(lng), (feats[0].get("properties") or {}).get("label") or f"CP {cp}"
            if respondio:
                break
    # Respaldo: Nominatim (OpenStreetMap)
    try:
        params = {"postalcode": cp, "country": "mx", "format": "json", "limit": 1}
        if estado:
            params["state"] = estado
        resp = requests.get(f"{NOMINATIM_URL}/search", params=params,
                            headers={"User-Agent": "MarkIncTicketsTI/1.0 (contacto: soporte@markinc.mx)"}, timeout=10)
        if resp.ok and resp.json():
            d = resp.json()[0]
            return float(d["lat"]), float(d["lon"]), d.get("display_name") or f"CP {cp}"
    except Exception:
        pass
    raise ErrorFlete(f"No se encontró el código postal {cp} en el mapa. Revisa que esté bien (o agrega municipio y estado).")


def tiempo_manejo(origen, destino) -> dict:
    """origen/destino = (lat, lng). Regresa {horas, km} por carretera (solo ida)."""
    key = _ors_key()
    if not key:
        raise ErrorFlete("Falta configurar OpenRouteService en el servidor (OPENROUTESERVICE_API_KEY).")
    cuerpo = {"coordinates": [[origen[1], origen[0]], [destino[1], destino[0]]], "radiuses": [-1, -1]}
    resp, ultimo_error = None, None
    for base_rutas, _ in _ORS_BASES:
        try:
            r = requests.post(f"{base_rutas}/v2/directions/driving-car", json=cuerpo,
                              headers={"Authorization": key, "Content-Type": "application/json"}, timeout=TIMEOUT)
        except requests.RequestException as e:
            ultimo_error = e
            continue
        if r.status_code == 404:
            resp = r
            continue
        resp = r
        break
    if resp is None:
        raise ErrorFlete(f"No se pudo conectar con el servicio de rutas: {ultimo_error}")
    if resp.status_code in (401, 403):
        raise ErrorFlete("La clave de OpenRouteService no es válida (revisa OPENROUTESERVICE_API_KEY en Render).")
    if resp.status_code == 429:
        raise ErrorFlete("Se acabaron las rutas gratis de hoy en OpenRouteService; intenta mañana.")
    if not resp.ok:
        raise ErrorFlete(f"No se pudo calcular la ruta: {_ors_error(resp)}")
    rutas = (resp.json() or {}).get("routes") or []
    if not rutas:
        raise ErrorFlete("No se encontró una ruta en carretera entre los dos puntos.")
    resumen = rutas[0].get("summary") or {}
    segundos = float(resumen.get("duration") or 0)
    metros = float(resumen.get("distance") or 0)
    return {"horas": segundos / 3600.0, "km": metros / 1000.0}


def redondear_horas(horas: float) -> float:
    """A una décima, mínimo 0.1 h."""
    return max(0.1, round(horas + 1e-9, 1))


def calcular_flete(cp_destino: str, municipio=None, estado=None, lat=None, lng=None, cp_origen=None,
                   precio_hora: float = 0) -> dict:
    """Horas de manejo (solo ida) desde la ubicación (lat/lng) o un CP de origen
    hasta el CP del cliente. Regresa la info del flete con el importe."""
    if not cp_valido(cp_destino or ""):
        raise ErrorFlete("Escribe el código postal del cliente (5 dígitos).")
    if lat is not None and lng is not None:
        origen, origen_texto = (lat, lng), "tu ubicación"
    elif cp_valido(cp_origen or ""):
        la, ln, _ = geocodificar_cp(cp_origen.strip())
        origen, origen_texto = (la, ln), f"CP {cp_origen.strip()}"
    else:
        raise ErrorFlete("Activa la ubicación o escribe el código postal de donde sales.")
    la, ln, destino_texto = geocodificar_cp(cp_destino, municipio, estado)
    ruta = tiempo_manejo(origen, (la, ln))
    horas = redondear_horas(ruta["horas"])
    km = round(ruta["km"], 1)
    return {
        "horas": horas, "horas_exactas": round(ruta["horas"], 3), "km": km, "precio_hora": precio_hora,
        "importe": round(horas * precio_hora, 2), "origen": origen_texto, "destino_cp": cp_destino,
        "destino": destino_texto, "municipio": municipio, "estado": estado,
        "nota": f"Solo ida: {km:g} km desde {origen_texto} hasta CP {cp_destino}",
    }
