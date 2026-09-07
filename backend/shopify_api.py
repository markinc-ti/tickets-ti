"""Integración con la API de Shopify (ventas de la tienda en línea) —
cada empresa configura su propio dominio y access token (Configuración
→ Apps y canales de venta → Desarrollar apps, en su admin de Shopify),
igual que ya hace con Microsip.

Shopify NO da datos de tráfico/visitas por esta API en planes normales
(eso es Google Analytics, aparte) — esto es solo ventas/pedidos reales.
"""
import datetime as _dt

import requests

VERSION_API = "2024-01"
TIMEOUT = 20


def _url(config, recurso, params=""):
    dominio = config["shop_domain"].strip()
    if not dominio.endswith(".myshopify.com") and "." not in dominio:
        dominio = f"{dominio}.myshopify.com"
    return f"https://{dominio}/admin/api/{VERSION_API}/{recurso}{params}"


def _headers(config):
    return {"X-Shopify-Access-Token": config["access_token"], "Content-Type": "application/json"}


def probar_conexion(config):
    try:
        r = requests.get(_url(config, "shop.json"), headers=_headers(config), timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, f"No se pudo conectar: {e}"
    if r.status_code == 401:
        return False, "El access token no es válido."
    if not r.ok:
        return False, f"Shopify respondió con error ({r.status_code}): {r.text[:200]}"
    nombre = r.json().get("shop", {}).get("name", "")
    return True, f"Conectado correctamente a la tienda \"{nombre}\"."


def _obtener_pedidos(config, fecha_desde, fecha_hasta):
    """Trae TODOS los pedidos en el rango (con paginación real de
    Shopify vía el header Link), pagados o no — el llamador decide qué
    filtrar."""
    pedidos = []
    params = (
        f"?status=any&created_at_min={fecha_desde}T00:00:00-00:00"
        f"&created_at_max={fecha_hasta}T23:59:59-00:00&limit=250"
    )
    url = _url(config, "orders.json", params)
    while url:
        r = requests.get(url, headers=_headers(config), timeout=TIMEOUT)
        if r.status_code == 401:
            raise RuntimeError("El access token de Shopify no es válido.")
        if not r.ok:
            raise RuntimeError(f"Shopify respondió con error ({r.status_code}): {r.text[:200]}")
        data = r.json()
        pedidos.extend(data.get("orders", []))
        # Paginación real de Shopify: viene en el header Link, no en el JSON.
        link = r.headers.get("Link", "")
        url = None
        if 'rel="next"' in link:
            for parte in link.split(","):
                if 'rel="next"' in parte:
                    url = parte.split(";")[0].strip().strip("<>")
        if len(pedidos) > 5000:  # tope de seguridad, para no quedarse pidiendo páginas para siempre
            break
    return pedidos


def obtener_resumen_ventas(config, fecha_desde, fecha_hasta):
    """Resumen de ventas del rango: total vendido (solo pedidos
    pagados), número de pedidos, ticket promedio, y desglose por día —
    para el dashboard de Shopify."""
    pedidos = _obtener_pedidos(config, fecha_desde, fecha_hasta)
    pagados = [p for p in pedidos if p.get("financial_status") == "paid"]

    por_dia = {}
    for p in pagados:
        dia = (p.get("created_at") or "")[:10]
        if not dia:
            continue
        por_dia.setdefault(dia, {"fecha": dia, "total": 0.0, "pedidos": 0})
        por_dia[dia]["total"] += float(p.get("total_price") or 0)
        por_dia[dia]["pedidos"] += 1

    total_ventas = sum(float(p.get("total_price") or 0) for p in pagados)
    num_pedidos = len(pagados)

    return {
        "total_ventas": round(total_ventas, 2),
        "num_pedidos": num_pedidos,
        "ticket_promedio": round(total_ventas / num_pedidos, 2) if num_pedidos else 0,
        "moneda": pagados[0].get("currency") if pagados else None,
        "ventas_por_dia": sorted(por_dia.values(), key=lambda d: d["fecha"]),
        "ultimos_pedidos": [
            {
                "folio": p.get("name"),
                "fecha": p.get("created_at"),
                "cliente": (p.get("customer") or {}).get("first_name", "") + " " + (p.get("customer") or {}).get("last_name", ""),
                "total": float(p.get("total_price") or 0),
                "estatus_pago": p.get("financial_status"),
                "estatus_envio": p.get("fulfillment_status"),
            }
            for p in sorted(pedidos, key=lambda p: p.get("created_at") or "", reverse=True)[:20]
        ],
    }
