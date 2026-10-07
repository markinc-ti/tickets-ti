"""Lectura de la Constancia de Situación Fiscal (CSF) del SAT SIN IA.

1) PDF descargado del SAT: trae texto, se lee directo (gratis, instantáneo).
2) Código QR de la constancia: apunta a la página de validación del SAT
   (siat.sat.gob.mx/app/qr/...?D1=10&D2=1&D3=<idCIF>_<RFC>), que regresa los
   datos vigentes del contribuyente. Se puede mandar el texto del QR (escaneado
   con la cámara del iPad) o se busca el QR dentro del PDF / foto.
Si nada de eso funciona, el que llama puede usar la IA como último recurso.
"""
import io
import re
import ssl
import unicodedata
from html import unescape

import requests

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import zxingcpp
    from PIL import Image
except Exception:  # pragma: no cover
    zxingcpp = None
    Image = None

TIMEOUT = 20
SAT_HOST = "siat.sat.gob.mx"

CAMPOS = ["rfc", "razon_social", "regimen_fiscal", "codigo_postal", "calle", "numero_exterior",
          "numero_interior", "colonia", "municipio", "estado", "correo"]

_RFC_RE = re.compile(r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b")


class ErrorConstancia(Exception):
    pass


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


# Palabras clave del nombre del régimen (como lo escribe el SAT) → clave del catálogo
_REGIMEN_CLAVES = [
    ("general de ley personas morales", "601"),
    ("fines no lucrativos", "603"),
    ("sueldos y salarios", "605"),
    ("arrendamiento", "606"),
    ("enajenacion o adquisicion de bienes", "607"),
    ("demas ingresos", "608"),
    ("residentes en el extranjero", "610"),
    ("dividendos", "611"),
    ("actividades empresariales y profesionales", "612"),
    ("ingresos por intereses", "614"),
    ("obtencion de premios", "615"),
    ("sin obligaciones fiscales", "616"),
    ("sociedades cooperativas", "620"),
    ("incorporacion fiscal", "621"),
    ("agricolas, ganaderas", "622"),
    ("agricolas", "622"),
    ("grupos de sociedades", "623"),
    ("coordinados", "624"),
    ("plataformas tecnologicas", "625"),
    ("simplificado de confianza", "626"),
]


def regimen_de_texto(texto: str):
    """Clave del primer régimen que aparece en el texto (el SAT los lista en orden)."""
    t = _sin_acentos(texto)
    mejor = None
    for frase, clave in _REGIMEN_CLAVES:
        i = t.find(frase)
        if i >= 0 and (mejor is None or i < mejor[0]):
            mejor = (i, clave)
    if mejor:
        return mejor[1]
    m = re.search(r"\b(6\d{2})\b", texto or "")
    return m.group(1) if m else None


def _limpio(v):
    v = " ".join(str(v or "").split()).strip(" :.-")
    return v or None


# ---------- 1) Texto del PDF ----------

# Etiquetas de la CSF (con espacios flexibles). Las que no se usan sirven de "tope".
_ETIQUETAS = {
    "rfc": r"RFC\s*:",
    "curp": r"CURP\s*:",
    "nombres": r"Nombre\s*\(s\)\s*:",
    "apellido1": r"Primer\s+Apellido\s*:",
    "apellido2": r"Segundo\s+Apellido\s*:",
    "denominacion": r"Denominaci[oó]n\s*/\s*Raz[oó]n\s+Social\s*:",
    "regimen_capital": r"R[eé]gimen\s+Capital\s*:",
    "codigo_postal": r"C[oó]digo\s+Postal\s*:",
    "tipo_vialidad": r"Tipo\s+de\s+Vialidad\s*:",
    "calle": r"Nombre\s+de\s+(?:la\s+)?Vialidad\s*:",
    "numero_exterior": r"N[uú]mero\s+Exterior\s*:",
    "numero_interior": r"N[uú]mero\s+Interior\s*:",
    "colonia": r"Nombre\s+de\s+la\s+Colonia\s*:",
    "localidad": r"Nombre\s+de\s+la\s+Localidad\s*:",
    "municipio": r"Nombre\s+del\s+Municipio\s+o\s+Demarcaci[oó]n\s+Territorial\s*:",
    "estado": r"Nombre\s+de\s+la\s+Entidad\s+Federativa\s*:",
    "entre_calle": r"Entre\s+Calle\s*:",
    "y_calle": r"Y\s+Calle\s*:",
    "correo": r"Correo\s+Electr[oó]nico\s*:",
    "tel": r"Tel\.\s*(?:Fijo|M[oó]vil)\s*Lada\s*:",
    "numero": r"\bN[uú]mero\s*:",
    "nombre_comercial": r"Nombre\s+Comercial\s*:",
    "fecha_inicio": r"Fecha\s+(?:de\s+)?inicio\s+de\s+operaciones\s*:",
    "estatus": r"Estatus\s+en\s+el\s+padr[oó]n\s*:",
    "fecha_cambio": r"Fecha\s+de\s+[uú]ltimo\s+cambio\s+de\s+estado\s*:",
    "estado_domicilio": r"Estado\s+del\s+domicilio\s*:",
    "estado_contrib": r"Estado\s+del\s+contribuyente\s+en\s+el\s+domicilio\s*:",
    "actividades": r"Actividades\s+Econ[oó]micas\s*:",
    "regimenes": r"Reg[ií]menes\s*:",
    "obligaciones": r"Obligaciones\s*:",
    "datos_domicilio": r"Datos\s+del\s+domicilio\s+registrado",
    "datos_ident": r"Datos\s+de\s+Identificaci[oó]n\s+del\s+Contribuyente\s*:?",
    "idcif": r"idCIF\s*:",
    "pagina": r"P[aá]gina\s*\[?\d",
    "cadena": r"Cadena\s+Original",
}


def texto_de_pdf(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        return ""
    try:
        lector = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in lector.pages[:4])
    except Exception:
        return ""


def datos_de_texto(texto: str) -> dict:
    """Saca los datos de la CSF a partir de su texto. Cada valor es lo que hay
    entre su etiqueta y la siguiente etiqueta conocida."""
    t = " ".join((texto or "").split())
    marcas = []
    for clave, patron in _ETIQUETAS.items():
        for m in re.finditer(patron, t, flags=re.IGNORECASE):
            marcas.append((m.start(), m.end(), clave))
    marcas.sort()
    valores = {}
    for i, (ini, fin, clave) in enumerate(marcas):
        sig = marcas[i + 1][0] if i + 1 < len(marcas) else len(t)
        valor = _limpio(t[fin:sig][:200])
        if clave not in valores or (not valores[clave] and valor):
            valores[clave] = valor
    r = {k: None for k in CAMPOS}
    rfcs = [v for v in [valores.get("rfc")] if v]
    m = _RFC_RE.search((valores.get("rfc") or "").upper()) or _RFC_RE.search(t.upper())
    r["rfc"] = m.group(1) if m else (rfcs[0] if rfcs else None)
    if valores.get("denominacion"):
        r["razon_social"] = valores["denominacion"]
    else:
        partes = [valores.get("nombres"), valores.get("apellido1"), valores.get("apellido2")]
        r["razon_social"] = _limpio(" ".join(p for p in partes if p)) if any(partes) else None
    cp = re.search(r"\d{5}", valores.get("codigo_postal") or "")
    r["codigo_postal"] = cp.group(0) if cp else None
    for k in ("calle", "numero_exterior", "numero_interior", "colonia", "municipio", "estado", "correo"):
        r[k] = valores.get(k)
    if r["correo"] and "@" not in r["correo"]:
        r["correo"] = None
    seccion = ""
    m_reg = re.search(_ETIQUETAS["regimenes"], t, flags=re.IGNORECASE)
    if m_reg:
        m_obl = re.search(_ETIQUETAS["obligaciones"], t[m_reg.end():], flags=re.IGNORECASE)
        seccion = t[m_reg.end(): m_reg.end() + (m_obl.start() if m_obl else 600)]
    r["regimen_fiscal"] = regimen_de_texto(seccion) if seccion else None
    if r["razon_social"]:
        r["razon_social"] = r["razon_social"].upper()
    return r


def suficiente(d: dict) -> bool:
    return bool(d and d.get("rfc") and d.get("razon_social") and d.get("codigo_postal"))


# ---------- 2) Código QR → página de validación del SAT ----------

def url_sat_valida(texto: str):
    """Regresa la URL si el texto del QR es el de una constancia del SAT."""
    t = (texto or "").strip()
    if not re.match(r"^https?://", t, flags=re.IGNORECASE):
        return None
    from urllib.parse import urlparse, parse_qs
    u = urlparse(t)
    if (u.hostname or "").lower() != SAT_HOST:
        return None
    d3 = (parse_qs(u.query).get("D3") or [""])[0]
    if "_" not in d3:
        return None
    return "https://" + SAT_HOST + u.path + "?" + u.query


def rfc_de_url(url: str):
    from urllib.parse import urlparse, parse_qs
    d3 = (parse_qs(urlparse(url).query).get("D3") or [""])[0]
    rfc = d3.split("_", 1)[1] if "_" in d3 else ""
    return rfc.upper() or None


class _AdaptadorSatTLS(requests.adapters.HTTPAdapter):
    """El servidor del SAT a veces exige cifrados viejos: se baja el nivel de
    seguridad de los cifrados (sin desactivar la verificación del certificado)."""
    def init_poolmanager(self, *a, **kw):
        ctx = ssl.create_default_context()
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        kw["ssl_context"] = ctx
        return super().init_poolmanager(*a, **kw)


def _descargar_sat(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.SSLError:
        s = requests.Session()
        s.mount("https://", _AdaptadorSatTLS())
        try:
            resp = s.get(url, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise ErrorConstancia(f"No se pudo conectar con el SAT: {e}")
    except requests.RequestException as e:
        raise ErrorConstancia(f"No se pudo conectar con el SAT: {e}")
    if not resp.ok:
        raise ErrorConstancia(f"El SAT respondió con error ({resp.status_code}). Intenta más tarde.")
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def _celdas(html: str):
    celdas = re.findall(r"<td[^>]*>(.*?)</td>", html, flags=re.IGNORECASE | re.DOTALL)
    return [" ".join(unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in celdas]


_ETIQ_SAT = {
    "denominacion o razon social": "razon_social",
    "nombre": "nombres",
    "apellido paterno": "apellido1",
    "apellido materno": "apellido2",
    "entidad federativa": "estado",
    "municipio o delegacion": "municipio",
    "colonia": "colonia",
    "nombre de la vialidad": "calle",
    "numero exterior": "numero_exterior",
    "numero interior": "numero_interior",
    "cp": "codigo_postal",
    "codigo postal": "codigo_postal",
    "correo electronico": "correo",
    "regimen": "regimen",
}


def datos_de_html_sat(html: str, rfc_url: str | None = None) -> dict:
    celdas = _celdas(html)
    v = {}
    for i in range(len(celdas) - 1):
        etiqueta = _sin_acentos(celdas[i]).rstrip(":").strip()
        if celdas[i].endswith(":") and etiqueta in _ETIQ_SAT:
            clave = _ETIQ_SAT[etiqueta]
            valor = _limpio(celdas[i + 1])
            if clave not in v and valor and not celdas[i + 1].endswith(":"):
                v[clave] = valor
    r = {k: None for k in CAMPOS}
    m = re.search(r"El RFC:\s*([A-ZÑ&0-9]{12,13})", unescape(html))
    r["rfc"] = (m.group(1) if m else rfc_url)
    if v.get("razon_social"):
        r["razon_social"] = v["razon_social"].upper()
    elif v.get("nombres"):
        r["razon_social"] = " ".join(x for x in (v.get("nombres"), v.get("apellido1"), v.get("apellido2")) if x).upper()
    cp = re.search(r"\d{5}", v.get("codigo_postal") or "")
    r["codigo_postal"] = cp.group(0) if cp else None
    for k in ("calle", "numero_exterior", "numero_interior", "colonia", "municipio", "estado", "correo"):
        r[k] = v.get(k)
    r["regimen_fiscal"] = regimen_de_texto(v.get("regimen") or "")
    return r


def datos_de_qr(texto_qr: str) -> dict:
    url = url_sat_valida(texto_qr)
    if not url:
        raise ErrorConstancia("Ese QR no es el de una Constancia de Situación Fiscal del SAT.")
    datos = datos_de_html_sat(_descargar_sat(url), rfc_de_url(url))
    if not datos.get("razon_social") and not datos.get("codigo_postal"):
        raise ErrorConstancia("El SAT no regresó los datos de esa constancia (puede estar caída la página del SAT). Intenta subir el PDF o captúralos a mano.")
    return datos


def qr_de_imagenes(imagenes) -> str | None:
    if zxingcpp is None:
        return None
    for img in imagenes:
        try:
            for r in zxingcpp.read_barcodes(img):
                if url_sat_valida(r.text):
                    return r.text
        except Exception:
            continue
    return None


def qr_de_pdf(pdf_bytes: bytes) -> str | None:
    if PdfReader is None or Image is None:
        return None
    imagenes = []
    try:
        lector = PdfReader(io.BytesIO(pdf_bytes))
        for p in lector.pages[:2]:
            for im in p.images:
                try:
                    imagenes.append(Image.open(io.BytesIO(im.data)).convert("RGB"))
                except Exception:
                    continue
    except Exception:
        return None
    return qr_de_imagenes(imagenes)


def qr_de_foto(img_bytes: bytes) -> str | None:
    if Image is None:
        return None
    try:
        return qr_de_imagenes([Image.open(io.BytesIO(img_bytes)).convert("RGB")])
    except Exception:
        return None
