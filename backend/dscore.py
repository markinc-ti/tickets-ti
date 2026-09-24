# -*- coding: utf-8 -*-
"""Integración con la API de DS Core (Dentsply Sirona) para el módulo de
Laboratorio -- deja que el estudiante importe su pedido (paciente, tipo de
trabajo, archivos) a partir del código que le da su maestro, en vez de
escribirlo todo a mano. Mismo patrón que shopify_api.py: funciones puras
que reciben los datos de conexión como parámetro, sin tocar la base de
datos directamente (eso lo hace app.py/db.py, igual que con Shopify).

Se conecta UNA sola vez por empresa, como cuenta de servicio del
laboratorio (Administrar → Laboratorio → DS Core) -- no es un login por
cada estudiante.

Documentación usada (portal de desarrolladores, persona LAB, pestaña
"GET STARTED"):
  - Login/autorizar:  GET  https://{base_host}/secureLogin?client_id=...&code_challenge=...&redirect_uri=...&state=...
  - Canjear tokens:   POST https://api.dscore.com/v1beta/auth/token
  - Refrescar tokens: POST https://api.dscore.com/v1beta/auth/token:refresh
  - Pedidos:          GET  https://{base_host}/v1beta/orders
  - Paciente (FHIR):  GET  https://{base_host}/v1beta/fhir/Patient/{id}

Hosts de sandbox confirmados: base_host = https://api.r2.dscore.com,
global host (fijo, no cambia por región) = https://api.dscore.com.

⚠️ Programado con base en la documentación oficial, pero TODAVÍA NO se
pudo probar contra el sandbox real (seguimos esperando a que aprueben el
acceso -- ver Administrar → Laboratorio → DS Core). En cuanto haya
credenciales reales, hay que confirmar sobre todo:
  - si el filtro readableId="..." funciona tal cual en /v1beta/orders
    (si no, buscar_order_por_codigo ya trae un respaldo que revisa los
    pedidos más recientes a mano)
  - si code_challenge_method debe mandarse explícito en la URL de login
    (se asume S256, el método estándar de PKCE)
"""
import base64
import hashlib
import secrets
import urllib.parse

import requests

TIMEOUT = 20
GLOBAL_HOST = "https://api.dscore.com"  # fijo -- mismo para sandbox y todas las regiones de producción


class DSCoreError(Exception):
    pass


def generar_pkce():
    """Regresa (code_verifier, code_challenge) para el login con PKCE,
    método S256 (el estándar de RFC 7636)."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def armar_url_login(base_host, client_id, redirect_uri, code_challenge, state):
    return (
        f"{base_host.rstrip('/')}/secureLogin"
        f"?client_id={urllib.parse.quote(client_id)}"
        f"&code_challenge={urllib.parse.quote(code_challenge)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={urllib.parse.quote(state)}"
    )


def intercambiar_code_por_tokens(client_id, client_secret, redirect_uri, code, code_verifier):
    body = {"code": code, "client_id": client_id, "redirect_uri": redirect_uri, "code_verifier": code_verifier}
    if client_secret:
        body["client_secret"] = client_secret
    try:
        r = requests.post(f"{GLOBAL_HOST}/v1beta/auth/token", json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")
    if not r.ok:
        raise DSCoreError(f"DS Core rechazó el código ({r.status_code}): {r.text[:300]}")
    datos = r.json()
    return datos.get("accessToken"), datos.get("refreshToken"), datos.get("expiresIn")


def refrescar_tokens(client_id, client_secret, refresh_token):
    body = {"refreshToken": refresh_token, "clientId": client_id}
    if client_secret:
        body["clientSecret"] = client_secret
    try:
        r = requests.post(f"{GLOBAL_HOST}/v1beta/auth/token:refresh", json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise DSCoreError(f"No se pudo renovar la conexión con DS Core: {e}")
    if not r.ok:
        raise DSCoreError(f"DS Core rechazó la renovación ({r.status_code}): {r.text[:300]}")
    datos = r.json()
    return datos.get("accessToken"), datos.get("refreshToken"), datos.get("expiresIn")


def _get(base_host, access_token, ruta, params=None):
    try:
        r = requests.get(
            f"{base_host.rstrip('/')}{ruta}", params=params,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")
    if not r.ok:
        raise DSCoreError(f"DS Core respondió con error ({r.status_code}) en {ruta}: {r.text[:300]}")
    return r.json()


def buscar_order_por_codigo(base_host, access_token, codigo):
    """Busca el pedido cuyo código legible (readableId) es 'codigo'. Si el
    filtro directo no lo encuentra, revisa entre los pedidos más recientes
    a mano (hasta 200, por si el filtro de DS Core no soporta readableId
    tal cual -- pendiente de confirmar con credenciales reales)."""
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    try:
        datos = _get(base_host, access_token, "/v1beta/orders", params={"filter": f'readableId="{codigo}"', "pageSize": 5})
        for order in datos.get("orders", []):
            if (order.get("readableId") or "").strip().lower() == codigo.lower():
                return order
    except DSCoreError:
        pass
    page_token = None
    for _ in range(2):
        params = {"pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        datos = _get(base_host, access_token, "/v1beta/orders", params=params)
        for order in datos.get("orders", []):
            if (order.get("readableId") or "").strip().lower() == codigo.lower():
                return order
        page_token = datos.get("nextPageToken")
        if not page_token:
            break
    return None


def nombre_paciente_de_order(base_host, access_token, order):
    """El pedido solo trae la URI del paciente (ej. "fhir/Patient/123") --
    hay que pedirlo aparte para sacar su nombre. Si algo falla, no truena
    la importación completa -- solo se queda sin nombre prellenado."""
    patient_uri = (order.get("patient") or {}).get("uri")
    if not patient_uri:
        return None
    try:
        datos = _get(base_host, access_token, f"/v1beta/{patient_uri}")
    except DSCoreError:
        return None
    nombres = datos.get("name") or []
    if not nombres:
        return None
    given = " ".join(nombres[0].get("given") or [])
    family = nombres[0].get("family") or ""
    nombre = f"{given} {family}".strip()
    return nombre or None


def probar_conexion(base_host, access_token):
    try:
        _get(base_host, access_token, "/v1beta/orders", params={"pageSize": 1})
    except DSCoreError as e:
        return False, str(e)
    return True, "Conectado correctamente con DS Core."


def obtener_orders_crudo(base_host, access_token, page_size=5):
    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,
    sin interpretar nada, para poder ver con datos reales (no documentacion)
    como se llama de verdad el campo del codigo legible del pedido y que
    forma tiene cada order. Se usa una sola vez desde el endpoint de debug
    para ajustar buscar_order_por_codigo() con la forma real de los datos."""
    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})


def obtener_archivo_crudo_diagnostico(base_host, access_token, uri):
    """SOLO PARA DIAGNOSTICO -- pide directamente la 'uri' de un archivo
    del pedido (el campo 'files[].uri' de un order, ej.
    'digitalImpressions/dxd-...') siguiendo el mismo patron que ya
    funciona para resolver patient.uri (GET /v1beta/{uri}), pero SIN
    forzar que la respuesta sea JSON -- para poder ver si DS Core regresa
    el archivo binario directo, un JSON con metadatos/link de descarga, o
    algo mas, antes de programar la descarga real de los escaneos STL
    originales del pedido.

    Usa stream=True y solo lee los primeros bytes para el preview -- ya
    vimos que un escaneo real puede pesar 25-100+ MB (estimatedContentSizesBytes),
    y este servidor corre con poca RAM (plan gratis de Render), asi que NO
    conviene descargar el archivo completo nada mas para diagnostico."""
    try:
        r = requests.get(
            f"{base_host.rstrip('/')}/v1beta/{uri.lstrip('/')}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT,
            stream=True,
        )
    except requests.RequestException as e:
        raise DSCoreError(f"No se pudo conectar con DS Core: {e}")
    content_type = r.headers.get("Content-Type", "")
    resultado = {
        "status_code": r.status_code,
        "content_type": content_type,
        "content_length_header": r.headers.get("Content-Length"),
        "content_disposition": r.headers.get("Content-Disposition"),
        "hubo_redireccion": bool(r.history),
        "url_final": r.url,
        "headers_respuesta": dict(r.headers),
    }
    if "json" in content_type.lower():
        try:
            resultado["json"] = r.json()
        except ValueError:
            resultado["texto_preview"] = r.text[:2000]
    else:
        preview = b""
        try:
            preview = next(r.iter_content(chunk_size=800), b"")
        except requests.RequestException:
            pass
        resultado["primeros_bytes_base64"] = base64.b64encode(preview).decode("ascii")
        resultado["bytes_leidos_para_preview"] = len(preview)
    r.close()
    return resultado


# Mapeos confirmados contra un pedido real de DS Core (2AFABPE9: 3 coronas
# de oxido de zirconia, tono A2, para los dientes FDI 18/16/38). Los que no
# se han visto en un pedido real todavia son la mejor suposicion -- si no
# coinciden, el texto de DS Core se usa tal cual (legible) en vez de
# perderse, y el tipo de trabajo cae en "otro" para no romper el campo
# validado de tickets-ti.
TIPOS_TRABAJO_DSCORE = {
    "CROWN": "corona",  # confirmado con pedido real
    "BRIDGE": "puente",
    "INLAY": "incrustacion",
    "ONLAY": "incrustacion",
    "VENEER": "carilla",
    "IMPLANT": "implante",
}

MATERIALES_DSCORE = {
    "ZIRCONIUM_OXID": "zirconia",  # confirmado con pedido real
    "LITHIUM_DISILICATE": "disilicato",
}

PRODUCTION_OPTIONS_DSCORE = {
    "DESIGN_ONLY": "Diseño",  # confirmado con pedido real
    "MILLING": "Fresado",  # confirmado con pedido real (como productionUnit)
    "DESIGN_AND_MILLING": "Diseño y fresado",
    "DESIGN_AND_PRINTING": "Diseño e impresión",
    "PRINTING": "Impresión",
}


def _texto_legible_dscore(valor):
    """Convierte un valor tipo ENUM_DE_DS_CORE que no reconocemos en texto
    legible, para no perder la información aunque no tengamos el mapeo
    exacto todavía: 'GLASS_CERAMIC' -> 'Glass ceramic'."""
    if not valor:
        return None
    texto = str(valor).replace("_", " ").strip()
    if not texto:
        return None
    return texto[:1].upper() + texto[1:].lower()


def extraer_piezas_de_order(order):
    """A partir de un pedido de DS Core, arma la lista de piezas (diente +
    tipo de trabajo + material + tono) que se le puede pasar directo a
    db.crear_trabajo_laboratorio(..., piezas=...), para que el odontograma
    del trabajo quede prellenado con lo que el doctor ya especificó en DS
    Core, en vez de quedar vacío ($0.00) como hasta ahora.

    Solo los pedidos tipo "restorationSet" traen el detalle estructurado
    por diente (items[].detail.restorationSet.restorations[] -- confirmado
    con un pedido real). Los pedidos "customOrder" (pedido personalizado)
    no traen esa información, así que para esos -- o cualquier forma que no
    reconozcamos -- se regresa una lista vacía y el odontograma se completa
    a mano, igual que antes. No es un error, es el comportamiento esperado."""
    piezas = []
    for item in (order.get("items") or []):
        restauraciones = ((item.get("detail") or {}).get("restorationSet") or {}).get("restorations") or []
        for r in restauraciones:
            tipo_dscore = (r.get("type") or "").strip().upper()
            tipo_trabajo = TIPOS_TRABAJO_DSCORE.get(tipo_dscore, "otro")
            material_dscore = (r.get("material") or "").strip().upper()
            material = MATERIALES_DSCORE.get(material_dscore) or _texto_legible_dscore(material_dscore)
            color = r.get("shade") or None
            notas_partes = []
            if tipo_dscore and tipo_dscore not in TIPOS_TRABAJO_DSCORE:
                notas_partes.append(f"Tipo en DS Core: {_texto_legible_dscore(tipo_dscore)}")
            prod_opt = (r.get("productionOptions") or "").strip().upper()
            if prod_opt:
                notas_partes.append(PRODUCTION_OPTIONS_DSCORE.get(prod_opt) or _texto_legible_dscore(prod_opt))
            prod_unit = (r.get("productionUnit") or "").strip().upper()
            if prod_unit:
                notas_partes.append(PRODUCTION_OPTIONS_DSCORE.get(prod_unit) or _texto_legible_dscore(prod_unit))
            notas = " · ".join(p for p in notas_partes if p) or None
            dientes = r.get("toothPositionsFdi") or r.get("toothPositions") or []
            for diente in dientes:
                piezas.append({
                    "diente": str(diente),
                    "tipo_trabajo": tipo_trabajo,
                    "material": material,
                    "color": color,
                    "notas": notas,
                })
    return piezas
