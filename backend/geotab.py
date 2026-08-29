"""Cliente de la API de MyGeotab (JSON-RPC 2.0 sobre HTTPS) — para leer la
posición GPS en vivo de los vehículos de la flotilla (servicio contratado
con A&T). Documentación oficial: https://developers.geotab.com/myGeotab/

Cómo funciona, en resumen:
1. Authenticate con usuario/contraseña/base de datos -> regresa un
   sessionId. Geotab a veces indica que hay que usar OTRO servidor
   (ej. my23.geotab.com en vez de my.geotab.com) — eso viene en el
   campo 'path' de la respuesta, y hay que reintentar ahí.
2. Con ese sessionId, se puede pedir Get(typeName='Device') para listar
   los vehículos/unidades GPS, o Get(typeName='DeviceStatusInfo') para
   la posición (lat/lng), velocidad y fecha de la última lectura.
"""
import requests

SERVIDOR_POR_DEFECTO = "my.geotab.com"


def _llamar(servidor, metodo, params, timeout=10):
    """Hace una llamada JSON-RPC cruda al servidor de Geotab indicado."""
    resp = requests.post(
        f"https://{servidor}/apiv1",
        json={"method": metodo, "params": params, "id": 1},
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    datos = resp.json()
    if "error" in datos:
        mensaje = datos["error"].get("message", str(datos["error"]))
        raise ValueError(f"Geotab respondió con un error: {mensaje}")
    return datos.get("result")


def autenticar(config):
    """config: dict con geotab_database, geotab_usuario, geotab_password.
    Regresa un dict de credenciales {database, userName, sessionId, servidor}
    listo para usarse en las demás llamadas. Sigue automáticamente la
    indicación de servidor de Geotab si hace falta (algunas cuentas no
    viven en my.geotab.com, sino en un servidor regional específico)."""
    if not config or not config.get("geotab_usuario") or not config.get("geotab_password") or not config.get("geotab_database"):
        raise ValueError("Todavía no configuras las credenciales de Geotab (Administrar → Geotab)")

    servidor = SERVIDOR_POR_DEFECTO
    params = {
        "userName": config["geotab_usuario"],
        "password": config["geotab_password"],
        "database": config["geotab_database"],
    }
    resultado = _llamar(servidor, "Authenticate", params)

    # Si Geotab indica que la cuenta vive en otro servidor, reintentamos ahí.
    path = (resultado or {}).get("path")
    if path and path != "ThisServer" and path != servidor:
        servidor = path
        resultado = _llamar(servidor, "Authenticate", params)

    credenciales = resultado["credentials"]
    return {
        "database": credenciales["database"],
        "userName": credenciales["userName"],
        "sessionId": credenciales["sessionId"],
        "servidor": servidor,
    }


def listar_dispositivos(config):
    """Regresa la lista de vehículos/unidades GPS dadas de alta en Geotab
    (id, nombre, número de serie) — para poder elegir cuál corresponde a
    cada vehículo de la flotilla en la app."""
    cred = autenticar(config)
    resultado = _llamar(cred["servidor"], "Get", {
        "typeName": "Device",
        "credentials": cred,
    })
    return [
        {"id": d["id"], "nombre": d.get("name", d["id"]), "numero_serie": d.get("serialNumber")}
        for d in (resultado or [])
    ]


def obtener_posicion(config, device_id):
    """Posición GPS más reciente de un vehículo. Regresa dict con lat, lng,
    velocidad_kmh, fecha, o None si Geotab no tiene una lectura para ese
    dispositivo (por ejemplo si nunca se ha movido, o el ID ya no existe)."""
    cred = autenticar(config)
    resultado = _llamar(cred["servidor"], "Get", {
        "typeName": "DeviceStatusInfo",
        "credentials": cred,
        "search": {"deviceSearch": {"id": device_id}},
    })
    if not resultado:
        return None
    info = resultado[0]
    if info.get("latitude") is None or info.get("longitude") is None:
        return None
    return {
        "lat": info["latitude"],
        "lng": info["longitude"],
        "velocidad_kmh": info.get("speed"),
        "fecha": info.get("dateTime"),
    }


def obtener_posiciones_multiples(config, device_ids):
    """Igual que obtener_posicion, pero para varios vehículos de una sola
    vez (una sola sesión de Geotab) — para el mapa general de flotilla."""
    if not device_ids:
        return {}
    cred = autenticar(config)
    resultado = _llamar(cred["servidor"], "Get", {
        "typeName": "DeviceStatusInfo",
        "credentials": cred,
    })
    por_device = {}
    ids_buscados = set(device_ids)
    for info in (resultado or []):
        device = info.get("device") or {}
        device_id = device.get("id")
        if device_id in ids_buscados and info.get("latitude") is not None:
            por_device[device_id] = {
                "lat": info["latitude"],
                "lng": info["longitude"],
                "velocidad_kmh": info.get("speed"),
                "fecha": info.get("dateTime"),
            }
    return por_device
