"""Cliente de SOLO LECTURA hacia la API de Kommo (api/v4) -- usado para
importar, de una sola vez, todo el CRM de Kommo (empresas, contactos,
leads/oportunidades con su etapa, notas y tareas) hacia el CRM interno de
tickets-ti. Igual que dscore.py/shopify_api.py con su API externa
correspondiente: este modulo NUNCA toca la base de datos, solo trae datos
crudos de Kommo -- quien decide que hacer con ellos es backend/db.py /
backend/app.py.

Autenticacion: token de larga duracion de una "integracion privada" de
Kommo (Ajustes -> Integraciones -> Crear integracion -> pestana "Claves y
alcances"). No se usa OAuth porque es una importacion de una sola vez, no
una conexion permanente -- el token se pega directo, sin el ir-y-venir de
un login.
"""
import time

import requests

TIMEOUT = 25
LIMITE_POR_PAGINA = 250  # maximo que permite Kommo por pagina
PAUSA_ENTRE_PAGINAS = 0.2  # Kommo limita a ~7 solicitudes/segundo por cuenta

ETAPAS_ESPECIALES = {142: "ganado", 143: "perdido"}  # ids fijos en TODA cuenta de Kommo


class KommoError(Exception):
    pass


def _url(subdominio, ruta):
    return f"https://{subdominio.strip()}.kommo.com/api/v4{ruta}"


def _get(subdominio, token, ruta, params=None, intentos=3):
    for intento in range(1, intentos + 1):
        try:
            r = requests.get(
                _url(subdominio, ruta),
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise KommoError(f"No se pudo conectar con Kommo: {e}")
        if r.status_code == 429 and intento < intentos:
            time.sleep(float(r.headers.get("Retry-After", 2)))
            continue
        if r.status_code == 204 or not r.text:
            return {}
        if not r.ok:
            raise KommoError(f"Kommo respondió con error ({r.status_code}) en {ruta}: {r.text[:300]}")
        return r.json()
    raise KommoError(f"Kommo sigue limitando las solicitudes (429) en {ruta} tras {intentos} intentos.")


def probar_conexion(subdominio, token):
    if not subdominio or not token:
        return False, "Falta el subdominio o el token de Kommo."
    try:
        datos = _get(subdominio, token, "/account")
    except KommoError as e:
        return False, str(e)
    nombre = datos.get("name") or subdominio
    return True, f'Conectado a la cuenta de Kommo "{nombre}".'


def _paginar(subdominio, token, ruta, clave_lista, params=None):
    """Generador que recorre TODAS las paginas de un listado de Kommo."""
    pagina = 1
    base_params = dict(params or {})
    while True:
        params_pagina = dict(base_params)
        params_pagina["limit"] = LIMITE_POR_PAGINA
        params_pagina["page"] = pagina
        datos = _get(subdominio, token, ruta, params=params_pagina)
        elementos = (datos.get("_embedded") or {}).get(clave_lista) or []
        if not elementos:
            break
        for el in elementos:
            yield el
        if len(elementos) < LIMITE_POR_PAGINA:
            break
        pagina += 1
        time.sleep(PAUSA_ENTRE_PAGINAS)


def obtener_pipelines_y_etapas(subdominio, token):
    """Regresa {(pipeline_id, status_id): "Nombre de etapa"} para poder
    traducir el status_id de cada lead a un nombre de etapa legible."""
    datos = _get(subdominio, token, "/leads/pipelines")
    pipelines = (datos.get("_embedded") or {}).get("pipelines") or []
    mapa = {}
    for p in pipelines:
        etapas = ((p.get("_embedded") or {}).get("statuses")) or []
        for e in etapas:
            mapa[(p["id"], e["id"])] = e.get("name") or f"Etapa {e['id']}"
    return mapa


def listar_companies(subdominio, token):
    yield from _paginar(subdominio, token, "/companies", "companies", params={"with": "contacts"})


def listar_contacts(subdominio, token):
    yield from _paginar(subdominio, token, "/contacts", "contacts", params={"with": "companies"})


def listar_leads(subdominio, token):
    yield from _paginar(subdominio, token, "/leads", "leads", params={"with": "contacts,companies"})


def listar_notas(subdominio, token, tipo_entidad):
    """tipo_entidad: 'leads' | 'contacts' | 'companies' -- trae TODAS las
    notas de ese tipo de entidad en una sola pasada paginada (no una
    llamada por cada entidad, para no tardar horas en cuentas grandes)."""
    yield from _paginar(subdominio, token, f"/{tipo_entidad}/notes", "notes")


def listar_tareas(subdominio, token):
    yield from _paginar(subdominio, token, "/tasks", "tasks")


def extraer_campo(custom_fields_values, field_code):
    """Saca el primer valor de un campo por su field_code (ej. 'PHONE',
    'EMAIL') de la lista custom_fields_values que trae Kommo en companies/
    contacts/leads. PHONE y EMAIL son campos que Kommo crea por default en
    toda cuenta, con ese field_code fijo."""
    if not custom_fields_values:
        return None
    for campo in custom_fields_values:
        if campo.get("field_code") == field_code:
            valores = campo.get("values") or []
            if valores:
                valor = valores[0].get("value")
                return str(valor).strip() if valor else None
    return None


def empresa_principal_del_lead(lead):
    companias = ((lead.get("_embedded") or {}).get("companies")) or []
    return companias[0]["id"] if companias else None


def contacto_principal_del_lead(lead):
    contactos = ((lead.get("_embedded") or {}).get("contacts")) or []
    if not contactos:
        return None
    for c in contactos:
        if c.get("is_main"):
            return c["id"]
    return contactos[0]["id"]


_ETIQUETAS_TIPO_NOTA = {
    "common": "Nota",
    "call_in": "Llamada entrante",
    "call_out": "Llamada saliente",
    "service_message": "Mensaje del sistema",
    "sms_in": "SMS entrante",
    "sms_out": "SMS saliente",
    "lead_created": "Se creó el lead",
    "lead_status_changed": "Cambio de etapa",
    "geolocation": "Ubicación",
}


def texto_de_nota(nota):
    params = nota.get("params") or {}
    tipo = nota.get("note_type") or "common"
    etiqueta = _ETIQUETAS_TIPO_NOTA.get(tipo, tipo)
    texto = params.get("text")
    if texto:
        return f"[{etiqueta}] {texto}"
    if tipo in ("call_in", "call_out") and params.get("duration") is not None:
        return f"[{etiqueta}] Duración: {params.get('duration')}s"
    return f"[{etiqueta}]"
