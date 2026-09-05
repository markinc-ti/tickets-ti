"""Asistente de IA flotante ("Mouse" por default, el nombre lo elige cada
empresa) — responde preguntas en lenguaje natural sobre los datos REALES
de la app (tickets, reparaciones, CRM, cotizaciones), usando la API de
Claude con "tool use": Claude decide qué consulta necesita, este módulo
la ejecuta contra la base de datos de la empresa, y Claude arma la
respuesta final con el resultado real (nunca inventa números).

Requiere la misma variable de entorno ANTHROPIC_API_KEY que ya usa
ia.py para leer imágenes. Sin ella, lanza RuntimeError con un mensaje
claro (el resto de la app sigue funcionando normal).
"""
import json
import os

import requests

import db

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODELO_ASISTENTE = "claude-sonnet-5"
MAX_VUELTAS_HERRAMIENTAS = 4  # tope de idas y vueltas Claude<->herramientas por mensaje, para no dejarlo en bucle

SYSTEM_PROMPT = """Eres el asistente interno de una app de gestión para una empresa (tickets de TI, \
reparaciones, CRM de ventas, cotizaciones). Respondes en español, de forma breve y directa, \
como un compañero de trabajo que ya sabe los datos, no como un reporte formal.

Reglas importantes:
- SIEMPRE usa las herramientas disponibles para consultar datos reales antes de dar cualquier \
número o estatus. NUNCA inventes cifras.
- Si una herramienta no tiene la información exacta que piden, dilo claramente en vez de adivinar.
- Si preguntan algo que no tiene que ver con los datos de la empresa (charla general, temas \
externos), puedes responder normal, sin necesidad de usar herramientas.
- Sé conciso. Nadie quiere un párrafo largo para "¿cuántos tickets abiertos hay?" — dale el número \
y, si aporta, un detalle corto."""


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta la variable de entorno ANTHROPIC_API_KEY. Configúrala en Render "
            "(Environment) con tu API key de console.anthropic.com para poder usar el asistente."
        )
    return key


# ---- Definición de herramientas (lo único que el asistente puede consultar) ----

HERRAMIENTAS = [
    {
        "name": "contar_tickets",
        "description": "Cuenta tickets de TI, opcionalmente filtrados por estado o prioridad. Usa esto para preguntas como '¿cuántos tickets abiertos hay?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "estado": {"type": "string", "enum": ["abierto", "en_progreso", "resuelto", "cerrado"], "description": "Opcional, deja vacío para contar todos"},
                "prioridad": {"type": "string", "enum": ["baja", "media", "alta", "urgente"], "description": "Opcional"},
            },
        },
    },
    {
        "name": "contar_reparaciones",
        "description": "Cuenta reparaciones de clientes, opcionalmente filtradas por estado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "estado": {"type": "string", "description": "Opcional, ej. 'en_reparacion', 'entregado', 'listo_entrega' — deja vacío para contar todas"},
            },
        },
    },
    {
        "name": "resumen_pipeline_crm",
        "description": "Trae el pipeline de ventas del CRM: cuántas oportunidades hay en cada etapa (nuevo, contactado, propuesta, negociacion, ganado, perdido) y su valor estimado total. Usa esto para '¿cómo van las ventas?' o '¿cómo va el pipeline?'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "tareas_crm_pendientes",
        "description": "Lista las tareas de seguimiento pendientes del CRM (recordatorios de venta no completados), con su cliente y fecha límite.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resumen_cotizaciones",
        "description": "Cuenta las cotizaciones agrupadas por estatus (creada, viva, posible_venta, vendida, perdida, vencida) y suma su monto total por estatus.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resumen_ventas_hoy_microsip",
        "description": "Ventas reales de hoy en Microsip (Punto de Venta), por sucursal y total del día. Solo funciona si la empresa ya configuró la conexión a Microsip.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _ejecutar_herramienta(nombre, entrada, empresa_id):
    """Corre la consulta real contra la base de datos de la empresa (o
    Microsip) y regresa un dict JSON-serializable. Cualquier error se
    regresa como {"error": "..."} para que Claude se lo explique al
    usuario en vez de que truene toda la conversación."""
    try:
        if nombre == "contar_tickets":
            tickets = db.listar_tickets(empresa_id, estado=entrada.get("estado"), prioridad=entrada.get("prioridad"))
            return {"total": len(tickets)}

        if nombre == "contar_reparaciones":
            reparaciones = db.listar_reparaciones(empresa_id, estado=entrada.get("estado"))
            return {"total": len(reparaciones)}

        if nombre == "resumen_pipeline_crm":
            oportunidades = db.listar_oportunidades_crm(empresa_id)
            por_etapa = {}
            for o in oportunidades:
                etapa = o["etapa"]
                acumulado = por_etapa.setdefault(etapa, {"cantidad": 0, "valor_estimado_total": 0})
                acumulado["cantidad"] += 1
                acumulado["valor_estimado_total"] += float(o.get("valor_estimado") or 0)
            return {"por_etapa": por_etapa, "total_oportunidades": len(oportunidades)}

        if nombre == "tareas_crm_pendientes":
            tareas = db.listar_tareas_crm(empresa_id, solo_pendientes=True)
            return {
                "total": len(tareas),
                "tareas": [
                    {"titulo": t["titulo"], "cliente": t.get("cliente_nombre"), "fecha_vencimiento": t.get("fecha_vencimiento")}
                    for t in tareas[:20]
                ],
            }

        if nombre == "resumen_cotizaciones":
            cotizaciones = db.listar_cotizaciones(empresa_id)
            por_estatus = {}
            for c in cotizaciones:
                estatus = c.get("estatus") or "creada"
                acumulado = por_estatus.setdefault(estatus, {"cantidad": 0, "monto_total": 0})
                acumulado["cantidad"] += 1
                acumulado["monto_total"] += float(c.get("total") or 0)
            return {"por_estatus": por_estatus, "total_cotizaciones": len(cotizaciones)}

        if nombre == "resumen_ventas_hoy_microsip":
            import microsip
            config = db.obtener_config_microsip(empresa_id)
            if not config or not config.get("microsip_host"):
                return {"error": "Microsip no está configurado todavía para esta empresa."}
            hoy = db.ahora().date().isoformat()
            ventas = microsip.obtener_ventas_pv_por_sucursal(config, hoy, hoy)
            return {"ventas_de_hoy": ventas}

        return {"error": f"Herramienta desconocida: {nombre}"}
    except Exception as e:
        return {"error": f"No se pudo consultar eso: {e}"}


def _system_prompt_con_conocimiento(empresa_id):
    notas = db.listar_conocimiento_asistente(empresa_id)
    if not notas:
        return SYSTEM_PROMPT
    lista = "\n".join(f"- {n['texto']}" for n in notas)
    return f"{SYSTEM_PROMPT}\n\nAdemás, esto es información específica que el administrador de esta empresa te enseñó directamente — tómala como cierta y úsala cuando aplique:\n{lista}"


def responder(mensaje, historial, empresa_id):
    """historial: lista de {"role": "user"|"assistant", "content": str} de
    turnos ANTERIORES (sin incluir el mensaje actual). Regresa el texto
    de la respuesta final del asistente."""
    api_key = _api_key()
    system_prompt = _system_prompt_con_conocimiento(empresa_id)
    mensajes = list(historial) + [{"role": "user", "content": mensaje}]

    for _ in range(MAX_VUELTAS_HERRAMIENTAS):
        try:
            r = requests.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": MODELO_ASISTENTE,
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "tools": HERRAMIENTAS,
                    "messages": mensajes,
                },
                timeout=45,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"No se pudo conectar con la API de Claude: {e}")

        if r.status_code == 401:
            raise RuntimeError("La API key de Anthropic no es válida (revisa ANTHROPIC_API_KEY en Render).")
        if r.status_code == 429:
            raise RuntimeError("Se alcanzó el límite de uso de la API de Claude por ahora — intenta en un momento.")
        if not r.ok:
            raise RuntimeError(f"La API de Claude respondió con error ({r.status_code}): {r.text[:300]}")

        data = r.json()
        contenido = data.get("content", [])
        mensajes.append({"role": "assistant", "content": contenido})

        bloques_tool_use = [b for b in contenido if b.get("type") == "tool_use"]
        if not bloques_tool_use:
            # No pidió ninguna herramienta más: esto ya es la respuesta final.
            textos = [b["text"] for b in contenido if b.get("type") == "text"]
            return "\n".join(textos).strip() or "No tengo una respuesta clara para eso."

        # Ejecuta cada herramienta pedida y regresa los resultados en un
        # solo mensaje "user" con bloques tool_result (así lo pide la API).
        resultados = []
        for bloque in bloques_tool_use:
            resultado = _ejecutar_herramienta(bloque["name"], bloque.get("input", {}), empresa_id)
            resultados.append({
                "type": "tool_result",
                "tool_use_id": bloque["id"],
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })
        mensajes.append({"role": "user", "content": resultados})

    return "Esto se puso más complicado de lo esperado — intenta preguntarlo de otra forma, más específica."


def saludo_proactivo(empresa_id, usuario_id, nombre_asistente="Mouse"):
    """Mensaje de bienvenida que Mouse muestra solo si de verdad hay algo
    pendiente que valga la pena avisar (tareas de proyecto sin terminar,
    o una cotización con seguimiento programado para hoy). No llama a la
    API de Claude — se arma directo con los datos, así no tiene costo ni
    depende de que la API key esté configurada. Regresa None si no hay
    nada pendiente que avisar."""
    resumen = db.resumen_pendientes_usuario(empresa_id, usuario_id)
    tareas = resumen["tareas_proyecto_pendientes"]
    cotizaciones = resumen["cotizaciones_seguimiento_hoy"]
    if not tareas and not cotizaciones:
        return None

    partes = [f"Antes de que preguntes algo, {nombre_asistente} te avisa:"]
    if tareas:
        partes.append(f"\n📋 Tienes {len(tareas)} tarea{'s' if len(tareas) != 1 else ''} de Proyectos sin terminar:")
        for t in tareas[:5]:
            venc = f" (vence {t['fecha_limite']})" if t.get("fecha_limite") else ""
            partes.append(f"  • {t['descripcion']} — {t['proyecto']}{venc}")
        if len(tareas) > 5:
            partes.append(f"  ...y {len(tareas) - 5} más.")
    if cotizaciones:
        partes.append(f"\n🧾 Tienes {len(cotizaciones)} cotización{'es' if len(cotizaciones) != 1 else ''} con seguimiento programado para hoy:")
        for c in cotizaciones[:5]:
            partes.append(f"  • {c['folio']} — {c['cliente_nombre']}")
    return "\n".join(partes)
