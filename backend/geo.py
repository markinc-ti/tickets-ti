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
    ninguna API — cubre los formatos más comunes. Regresa (lat, lng) o None."""
    if not url:
        return None
    patrones = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]destination=(-?\d+\.\d+),(-?\d+\.\d+)',
    ]
    for patron in patrones:
        m = re.search(patron, url)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
    return None


def geocodificar(direccion):
    """Convierte una dirección de texto en (lat, lng) usando el servicio
    gratuito Nominatim (OpenStreetMap). Regresa None si no encuentra nada,
    si no hay dirección, o si 'requests' no está disponible."""
    if not direccion or not requests:
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": direccion, "format": "json", "limit": 1},
            headers={"User-Agent": "MarkIncTicketsTI/1.0"},
            timeout=6,
        )
        resp.raise_for_status()
        datos = resp.json()
        if not datos:
            return None
        return float(datos[0]["lat"]), float(datos[0]["lon"])
    except Exception:
        return None


def resolver_coordenadas(liga_mapa, direccion):
    """Intenta obtener lat/lng primero de la liga de mapa (si trae
    coordenadas visibles en la URL), y si no, geocodifica la dirección de
    texto. Regresa (lat, lng) o (None, None)."""
    coords = extraer_latlng_de_liga(liga_mapa) or geocodificar(direccion)
    return coords if coords else (None, None)
