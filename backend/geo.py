"""Utilidades de geolocalización — 100% gratis, sin API de pago ni cuenta:
- Geocodifica direcciones de texto a lat/lng usando Nominatim (OpenStreetMap).
- Calcula distancia en línea recta (fórmula de Haversine) y un tiempo
  estimado de viaje asumiendo una velocidad promedio de ciudad.
No es tan preciso como Google Maps (no considera calles reales ni tráfico),
pero no tiene costo ni requiere ninguna cuenta."""
import math
import re

try:
    import requests
except ImportError:  # por si 'requests' todavía no está en requirements.txt
    requests = None

VELOCIDAD_PROMEDIO_KMH = 30  # velocidad promedio asumida en ciudad, con tráfico normal


def haversine_km(lat1, lng1, lat2, lng2):
    """Distancia en línea recta (km) entre dos puntos lat/lng."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def estimar_minutos(distancia_km):
    """Minutos estimados de viaje para una distancia dada, a velocidad promedio de ciudad."""
    return round((distancia_km / VELOCIDAD_PROMEDIO_KMH) * 60)


def extraer_latlng_de_liga(url):
    """Intenta sacar lat/lng directo de una liga de Google Maps, sin llamar a
    ninguna API — cubre los formatos más comunes. Si es una liga corta
    (maps.app.goo.gl/... o goo.gl/maps/...), esos textos NUNCA traen
    coordenadas visibles — hay que seguir la redirección para que Google
    entregue la URL larga real, que sí las trae. Regresa (lat, lng) o None."""
    if not url:
        return None

    if requests and re.search(r'(maps\.app\.goo\.gl|goo\.gl/maps)', url):
        try:
            resp = requests.head(url, allow_redirects=True, timeout=6,
                                  headers={"User-Agent": "Mozilla/5.0 (compatible; MarkIncTicketsTI/1.0)"})
            url = resp.url  # la URL larga real, después de seguir la(s) redirección(es)
        except Exception:
            pass  # si falla, seguimos con la URL corta original — el regex de abajo simplemente no va a encontrar nada

    patrones = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]destination=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',  # formato de "data=" en ligas de lugares/negocios de Google Maps
    ]
    for patron in patrones:
        m = re.search(patron, url)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
    return None


def _geocodificar_locationiq(direccion, api_key):
    """Geocodifica con LocationIQ (llave propia de la empresa, gratis hasta
    5,000 búsquedas/día) — a diferencia de Nominatim público, esta llave no
    se comparte con nadie más, así que no se ve afectada si otra app en el
    mismo hosting agota el límite. Regresa (lat, lng, motivo_si_fallo)."""
    try:
        resp = requests.get(
            "https://us1.locationiq.com/v1/search",
            params={"key": api_key, "q": direccion, "format": "json", "limit": 1},
            timeout=8,
        )
        if resp.status_code == 404:
            # LocationIQ regresa 404 (no 200 con lista vacía) cuando no encuentra nada
            return None, None, f"LocationIQ no reconoció \"{direccion}\" — intenta con menos detalle (ej. solo calle, colonia y ciudad) o revisa que esté bien escrita"
        resp.raise_for_status()
        datos = resp.json()
        if not datos:
            return None, None, f"LocationIQ no reconoció \"{direccion}\""
        return float(datos[0]["lat"]), float(datos[0]["lon"]), None
    except Exception as e:
        return None, None, f"error consultando LocationIQ: {e}"


def _geocodificar_nominatim(direccion):
    """Geocodifica con el servicio gratuito y sin cuenta Nominatim
    (OpenStreetMap) — usado como respaldo cuando la empresa todavía no
    configuró su propia llave de LocationIQ. Al ser compartido entre
    muchísimos usuarios (incluyendo otras apps del mismo hosting), puede
    bloquear por exceso de peticiones (429) sin que sea culpa nuestra."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": direccion, "format": "json", "limit": 1},
            headers={"User-Agent": "MarkIncTicketsTI/1.0 (contacto: soporte@markinc.mx)"},
            timeout=8,
        )
        resp.raise_for_status()
        datos = resp.json()
        if not datos:
            return None, None, f"Nominatim (OpenStreetMap) no reconoció \"{direccion}\" — intenta con menos detalle (ej. solo calle, colonia y ciudad) o revisa que esté bien escrita"
        return float(datos[0]["lat"]), float(datos[0]["lon"]), None
    except Exception as e:
        return None, None, f"error consultando el servicio de mapas: {e}"


def geocodificar(direccion, locationiq_api_key=None):
    """Convierte una dirección de texto en (lat, lng). Usa LocationIQ si la
    empresa ya configuró su llave propia (Administrar → Geocodificación);
    si no, cae en el Nominatim público como respaldo, para que nunca deje
    de funcionar del todo. Regresa (lat, lng, None) si encuentra, o
    (None, None, motivo) si no — el motivo es para mostrar en pantalla POR
    QUÉ falló, en vez de un genérico 'no se pudo'."""
    if not direccion:
        return None, None, "no se escribió ninguna dirección"
    if not requests:
        return None, None, "el servidor no tiene el paquete 'requests' instalado"
    if locationiq_api_key:
        return _geocodificar_locationiq(direccion, locationiq_api_key)
    return _geocodificar_nominatim(direccion)


def _parece_url(texto):
    """True si el texto es una liga web (http/https) y no una dirección normal
    escrita a mano — para no intentar geocodificar la URL cruda como si fuera
    una calle/colonia (eso nunca funciona y da un mensaje de error confuso)."""
    return bool(texto) and bool(re.match(r'^https?://', texto.strip(), re.IGNORECASE))


def resolver_coordenadas(liga_mapa, direccion, locationiq_api_key=None):
    """Intenta obtener lat/lng primero de la liga de mapa (si trae, o se le
    puede sacar, coordenadas), y si no, geocodifica la dirección de texto.
    Regresa (lat, lng, motivo_si_fallo)."""
    coords = extraer_latlng_de_liga(liga_mapa)
    if coords:
        return coords[0], coords[1], None
    if direccion and not _parece_url(direccion):
        return geocodificar(direccion, locationiq_api_key)
    if liga_mapa:
        return None, None, "esa liga no trae coordenadas y no se pudo seguir para obtenerlas — pega la dirección de texto en su lugar (calle, colonia, ciudad), o una liga larga de Google Maps (con @lat,lng en la URL)"
    return None, None, "no se dio ni liga de mapa ni dirección"

