# -*- coding: utf-8 -*-
"""
Dirección (vista del CEO): un resumen de SOLO LECTURA de lo más importante de
la empresa, para la app (iPhone / Android) y para quien tenga el Dashboard.

Dos partes:
  1. resumen(...)  — RH del día (retardos, faltas, quién no ha checado, permisos
     con su motivo), reparaciones pendientes, proyectos y su avance, tickets,
     laboratorio y soporte. Cada bloque sale solo si la empresa tiene ese módulo.
  2. CONSULTAS     — consultas de Microsip ya armadas (ventas, corte, pedidos,
     inventario…). La app las dibuja SOLA a partir de lo que regresa cada una
     (resumen + tablas), así que para agregar una consulta nueva basta con
     sumarla a la lista CONSULTAS de abajo: aparece en la app sin actualizarla.
"""
from datetime import date, datetime, timedelta

import db
import microsip

# ---------------------------------------------------------------------------
# Textos para los estados (lo que ve el CEO, no las claves internas)
# ---------------------------------------------------------------------------
NOMBRES_REPARACION = {
    "nueva": "Nueva", "en_diagnostico": "En diagnóstico", "esperando_autorizacion": "Esperando autorización",
    "en_reparacion": "En reparación", "con_proveedor": "Con proveedor", "esperando_refaccion": "Esperando refacción",
    "terminado_taller": "Terminado en taller", "control_calidad": "Control de calidad",
    "envio_sucursal": "Envío a sucursal", "en_traslado": "En traslado", "listo_entrega": "Lista para entregar",
}
# Un color por estado de reparación (mismos en la web y en las apps), en el
# orden del flujo: así la barra de estatus se lee de izquierda a derecha.
COLORES_REPARACION = {
    "nueva": "#E11D48", "en_diagnostico": "#F59E0B", "esperando_autorizacion": "#EA580C",
    "en_reparacion": "#2563EB", "con_proveedor": "#0891B2", "esperando_refaccion": "#7C3AED",
    "terminado_taller": "#0D9488", "control_calidad": "#9333EA", "envio_sucursal": "#4F46E5",
    "en_traslado": "#DB2777", "listo_entrega": "#16A34A",
}
NOMBRES_PROYECTO = {"planificacion": "Planeación", "en_progreso": "En progreso", "pausado": "Pausado",
                    "completado": "Completado", "cancelado": "Cancelado"}
NOMBRES_TICKET = {"abierto": "Abierto", "en_progreso": "En progreso", "resuelto": "Resuelto", "cerrado": "Cerrado"}
NOMBRES_LAB = {
    "recibido": "Recibido", "en_laboratorio": "En laboratorio", "modelado": "Modelado", "aprobar_diseno": "Aprobar diseño",
    "maquila": "Maquila", "maquillado": "Maquillado", "control_calidad": "Control de calidad",
    "envio_sucursal": "Envío a sucursal", "listo_entrega": "Listo para entregar", "devolucion": "Devolución",
}
NOMBRES_SOPORTE = {"orden_pendiente_firma": "Falta firma del cliente", "diagnostico": "En diagnóstico",
                   "resolucion_enviada": "Resolución enviada", "enviado": "Enviado al cliente"}
NOMBRES_INCIDENCIA = {"permiso_horas": "Permiso por horas", "dia_libre_sin_goce": "Día libre sin goce", "enfermedad": "Enfermedad", "lesion": "Lesión",
                      "embarazo": "Embarazo", "accidente": "Accidente", "otro": "Permiso"}
NOMBRES_ESTADO_INCIDENCIA = {"propuesta_empleado": "Por confirmar", "pendiente_encargado": "Con la encargada",
                             "pendiente": "Por aprobar", "aprobada": "Aprobada", "pagada": "Pagada"}

DIAS_REPARACION_ATRASADA = 15


def _texto(mapa, clave):
    return mapa.get(clave) or (clave or "").replace("_", " ").capitalize()


def _fecha(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v)[:19]).date()
    except ValueError:
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _iso(v):
    f = _fecha(v)
    return f.isoformat() if f else None


def _consulta(sql, params):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()


# ---------------------------------------------------------------------------
# 1) RESUMEN
# ---------------------------------------------------------------------------

def _bloque_rh(empresa_id, dia: date, hoy: date, reporte_asistencia):
    """reporte_asistencia(empresa_id, desde, hasta) -> el mismo reporte de RH
    → Asistencia (checador biométrico + checador de la app + vacaciones)."""
    rep = reporte_asistencia(empresa_id, dia, dia)
    ahora = db.ahora()
    minutos_ahora = ahora.hour * 60 + ahora.minute

    # Permisos / incidencias que cubren ese día (con su motivo).
    incid = _consulta("""
        SELECT i.usuario_id, i.tipo, i.motivo, i.estado, i.fecha_inicio, i.fecha_fin, i.horas,
               COALESCE(u.nombre_completo, u.username) AS nombre
        FROM incidencias_rh i JOIN users u ON u.id = i.usuario_id
        WHERE i.empresa_id = %s AND i.estado NOT IN ('rechazada')
          AND i.fecha_inicio <= %s AND COALESCE(NULLIF(i.fecha_fin, ''), i.fecha_inicio) >= %s
        ORDER BY nombre
    """, (empresa_id, dia.isoformat(), dia.isoformat()))
    motivo_de = {}
    permisos = []
    for i in incid:
        texto = _texto(NOMBRES_INCIDENCIA, i["tipo"])
        motivo = f"{texto}: {i['motivo']}" if (i.get("motivo") or "").strip() else texto
        motivo_de.setdefault(i["usuario_id"], motivo)
        permisos.append({"nombre": i["nombre"], "tipo": texto, "motivo": (i.get("motivo") or "").strip() or None,
                         "estado": _texto(NOMBRES_ESTADO_INCIDENCIA, i["estado"]),
                         "desde": _iso(i["fecha_inicio"]), "hasta": _iso(i["fecha_fin"]) or _iso(i["fecha_inicio"]),
                         "horas": float(i["horas"]) if i.get("horas") else None})

    tot = {"plantilla": 0, "llegaron": 0, "puntuales": 0, "retardos": 0, "faltas": 0, "justificadas": 0, "sin_checar": 0,
           "sin_conexion": 0}
    retardos, faltas, justificadas, sin_checar, sin_conexion = [], [], [], [], []
    for e in rep.get("empleados", []):
        d = (e.get("dias") or [None])[0]
        if not d or not d.get("laborable") and not d.get("entrada"):
            continue
        tot["plantilla"] += 1
        h = e.get("horario") or {}
        base = {"nombre": e.get("nombre"), "sucursal": e.get("sucursal"), "hora_entrada": h.get("hora_entrada")}
        est = d.get("estatus")
        if d.get("entrada"):
            tot["llegaron"] += 1
        if est == "retardo":
            tot["retardos"] += 1
            retardos.append({**base, "entrada": d.get("entrada"), "minutos": d.get("minutos_retardo") or 0})
        elif est in ("puntual", "sin_salida", "dia_no_laboral"):
            tot["puntuales"] += 1 if est != "dia_no_laboral" else 0
        elif est == "justificada" or (est in ("falta", "pendiente") and e.get("usuario_id") in motivo_de):
            tot["justificadas"] += 1
            justificadas.append({**base, "motivo": d.get("motivo") or motivo_de.get(e.get("usuario_id"))})
        elif est == "sin_conexion":
            # El checador está fuera de línea: no se sabe si llegó, no es falta.
            tot["sin_conexion"] += 1
            sin_conexion.append({**base, "checadores": e.get("checadores_fuera") or []})
        elif est == "falta":
            tot["faltas"] += 1
            faltas.append(base)
        elif est == "pendiente":
            # Hoy, todavía dentro del horario: solo cuenta si ya pasó su hora de entrada + tolerancia.
            try:
                hh, mm = str(h.get("hora_entrada") or "00:00").split(":")[:2]
                limite = int(hh) * 60 + int(mm) + int(h.get("tolerancia_min") or 0)
            except ValueError:
                limite = 0
            if dia == hoy and minutos_ahora > limite:
                if e.get("sin_conexion_ahora"):
                    tot["sin_conexion"] += 1
                    sin_conexion.append({**base, "checadores": e.get("checadores_fuera") or []})
                else:
                    tot["sin_checar"] += 1
                    sin_checar.append(base)
    retardos.sort(key=lambda r: -(r["minutos"] or 0))
    return {
        "fecha": dia.isoformat(), "es_hoy": dia == hoy, "totales": tot,
        "retardos": retardos, "faltas": sorted(faltas, key=lambda r: r["nombre"] or ""),
        "justificadas": sorted(justificadas, key=lambda r: r["nombre"] or ""),
        "sin_checar": sorted(sin_checar, key=lambda r: r["nombre"] or ""),
        "sin_conexion": sorted(sin_conexion, key=lambda r: r["nombre"] or ""),
        # Estado de cada checador (verde en línea / rojo sin conexión).
        "checadores": [{"nombre": k["nombre"], "sucursal": k.get("sucursal"), "en_linea": k["en_linea"],
                        "minutos": k.get("minutos"), "ultima_conexion": k.get("ultima_conexion")}
                       for k in rep.get("conexion_checadores") or []],
        "permisos": permisos, "avisos": rep.get("avisos") or [],
    }


def bloque_asistencia(empresa_id, dia: date, reporte_asistencia) -> dict:
    """El bloque de asistencia del día solo (RH lo ve en su app)."""
    return _bloque_rh(empresa_id, dia, db.ahora().date(), reporte_asistencia)


def _paso_reparacion(estado):
    """Qué tan avanzada va (0 a 1) según el flujo: nueva → … → lista para entregar."""
    orden = list(NOMBRES_REPARACION)
    return round((orden.index(estado) + 1) / len(orden), 3) if estado in orden else 0


def _bloque_reparaciones(empresa_id, hoy: date):
    filas = _consulta("""
        SELECT r.folio, r.cliente_nombre, r.equipo, r.marca, r.modelo, r.estado, r.fecha_recepcion, r.creado_en,
               COALESCE(s.nombre, 'Sin sucursal') AS sucursal
        FROM reparaciones r LEFT JOIN sucursales_reparacion s ON s.id = r.sucursal_id
        WHERE r.empresa_id = %s AND r.estado NOT IN ('entregado', 'cancelado')
    """, (empresa_id,))
    por_estado, por_sucursal, lista = {}, {}, []
    for r in filas:
        por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1
        por_sucursal[r["sucursal"]] = por_sucursal.get(r["sucursal"], 0) + 1
        inicio = _fecha(r.get("fecha_recepcion")) or _fecha(r.get("creado_en")) or hoy
        equipo = " ".join(x for x in [r.get("equipo"), r.get("marca"), r.get("modelo")] if (x or "").strip()) or None
        lista.append({"folio": r["folio"], "cliente": r.get("cliente_nombre"), "equipo": equipo,
                      "estado": _texto(NOMBRES_REPARACION, r["estado"]), "estado_clave": r["estado"],
                      "color": COLORES_REPARACION.get(r["estado"], "#6B7280"), "sucursal": r["sucursal"],
                      "paso": _paso_reparacion(r["estado"]), "dias": (hoy - inicio).days})
    lista.sort(key=lambda x: -x["dias"])
    orden = list(NOMBRES_REPARACION)
    return {
        "pendientes": len(filas),
        "listas_para_entregar": por_estado.get("listo_entrega", 0),
        "atrasadas": sum(1 for x in lista if x["dias"] > DIAS_REPARACION_ATRASADA),
        "dias_atraso": DIAS_REPARACION_ATRASADA,
        "por_estado": [{"etiqueta": _texto(NOMBRES_REPARACION, e), "valor": n, "clave": e,
                        "color": COLORES_REPARACION.get(e, "#6B7280")}
                       for e, n in sorted(por_estado.items(), key=lambda kv: orden.index(kv[0]) if kv[0] in orden else 99)],
        "por_sucursal": [{"etiqueta": s, "valor": n} for s, n in sorted(por_sucursal.items(), key=lambda kv: -kv[1])],
        "mas_antiguas": lista[:15],
    }


def _bloque_proyectos(empresa_id, hoy: date):
    proyectos = _consulta("""
        SELECT p.id, p.nombre, p.estado, p.fecha_inicio, p.fecha_estimada, p.fecha_completado,
               COALESCE(u.nombre_completo, u.username) AS responsable,
               (SELECT COUNT(*) FROM proyecto_tareas t WHERE t.proyecto_id = p.id) AS tareas,
               (SELECT COUNT(*) FROM proyecto_tareas t WHERE t.proyecto_id = p.id AND t.estado = 'completada') AS hechas,
               (SELECT COUNT(*) FROM proyecto_tareas t WHERE t.proyecto_id = p.id AND t.estado <> 'completada'
                    AND t.fecha_limite IS NOT NULL AND t.fecha_limite <> '' AND t.fecha_limite < %s) AS vencidas
        FROM proyectos p LEFT JOIN users u ON u.id = p.creado_por_id
        WHERE p.empresa_id = %s
    """, (hoy.isoformat(), empresa_id))
    activos, completados_mes = [], 0
    for p in proyectos:
        if p["estado"] == "completado":
            fc = _fecha(p.get("fecha_completado"))
            if fc and fc.year == hoy.year and fc.month == hoy.month:
                completados_mes += 1
            continue
        if p["estado"] == "cancelado":
            continue
        tareas, hechas = int(p["tareas"] or 0), int(p["hechas"] or 0)
        fin = _fecha(p.get("fecha_estimada"))
        activos.append({
            "nombre": p["nombre"], "estado": _texto(NOMBRES_PROYECTO, p["estado"]), "estado_clave": p["estado"],
            "responsable": p.get("responsable"), "avance": round(hechas * 100 / tareas) if tareas else 0,
            "tareas": tareas, "hechas": hechas, "tareas_vencidas": int(p["vencidas"] or 0),
            "fecha_estimada": fin.isoformat() if fin else None, "vencido": bool(fin and fin < hoy),
        })
    orden = {"en_progreso": 0, "planificacion": 1, "pausado": 2}
    activos.sort(key=lambda x: (not x["vencido"], orden.get(x["estado_clave"], 9), x["fecha_estimada"] or "9999"))
    return {
        "activos": len(activos), "vencidos": sum(1 for x in activos if x["vencido"]),
        "completados_mes": completados_mes, "lista": activos,
    }


def _bloque_tickets(empresa_id, hoy: date):
    filas = _consulta("""
        SELECT folio, descripcion, prioridad, estado, departamento, creado_en
        FROM tickets WHERE empresa_id = %s AND estado IN ('abierto', 'en_progreso')
    """, (empresa_id,))
    urg = [f for f in filas if f.get("prioridad") in ("urgente", "alta")]
    lista = []
    for f in sorted(filas, key=lambda f: ({"urgente": 0, "alta": 1}.get(f.get("prioridad"), 2), str(f.get("creado_en") or ""))):
        ini = _fecha(f.get("creado_en")) or hoy
        lista.append({"folio": f["folio"], "descripcion": (f.get("descripcion") or "")[:140],
                      "prioridad": (f.get("prioridad") or "").capitalize(), "estado": _texto(NOMBRES_TICKET, f["estado"]),
                      "departamento": f.get("departamento"), "dias": (hoy - ini).days})
    return {"abiertos": sum(1 for f in filas if f["estado"] == "abierto"),
            "en_progreso": sum(1 for f in filas if f["estado"] == "en_progreso"),
            "urgentes": len(urg), "lista": lista[:10]}


def _bloque_laboratorio(empresa_id, hoy: date):
    """Trabajos del laboratorio: en curso, pasados de fecha, listos, por pagar,
    pagos por revisar, devoluciones, cuánto entró y lo cobrado en el mes."""
    filas = _consulta("""
        SELECT t.id, t.folio, t.estado, t.solicitante_nombre, t.universidad_clinica, t.paciente_nombre,
               t.fecha_recepcion, t.fecha_compromiso, t.pago_registrado_en, t.requiere_factura,
               t.microsip_docto_id, t.microsip_factura_pendiente, t.creado_en,
               COALESCE(s.nombre, 'Sin sucursal') AS sucursal,
               (SELECT COALESCE(SUM(p.costo), 0) FROM laboratorio_piezas p WHERE p.trabajo_id = t.id) AS importe,
               (SELECT COUNT(*) FROM laboratorio_pagos_reportados r WHERE r.trabajo_id = t.id AND r.estado = 'pendiente') AS pagos_por_revisar
        FROM trabajos_laboratorio t LEFT JOIN sucursales_reparacion s ON s.id = t.sucursal_id
        WHERE t.empresa_id = %s AND t.estado <> 'cancelado'
    """, (empresa_id,))
    semana = hoy - timedelta(days=hoy.weekday())
    activos, por_estado, por_sucursal, lista = [], {}, {}, []
    rec = {"hoy": 0, "semana": 0, "mes": 0}
    valor_mes = 0.0
    por_pagar = por_pagar_monto = pagos_revisar = devoluciones = facturas = 0
    for t in filas:
        ini = _fecha(t.get("fecha_recepcion")) or _fecha(t.get("creado_en"))
        if ini:
            if ini == hoy:
                rec["hoy"] += 1
            if ini >= semana:
                rec["semana"] += 1
            if ini.year == hoy.year and ini.month == hoy.month:
                rec["mes"] += 1
                valor_mes += float(t.get("importe") or 0)
        if t["estado"] == "entregado":
            continue
        activos.append(t)
        por_estado[t["estado"]] = por_estado.get(t["estado"], 0) + 1
        por_sucursal[t["sucursal"]] = por_sucursal.get(t["sucursal"], 0) + 1
        if not t.get("pago_registrado_en"):
            por_pagar += 1
            por_pagar_monto += float(t.get("importe") or 0)
        pagos_revisar += int(t.get("pagos_por_revisar") or 0)
        if t["estado"] == "devolucion":
            devoluciones += 1
        if t.get("microsip_factura_pendiente") or (t.get("requiere_factura") and not t.get("microsip_docto_id")):
            facturas += 1
        compromiso = _fecha(t.get("fecha_compromiso"))
        lista.append({"folio": t["folio"], "paciente": t.get("paciente_nombre"), "solicitante": t.get("solicitante_nombre"),
                      "clinica": t.get("universidad_clinica"), "estado": _texto(NOMBRES_LAB, t["estado"]), "sucursal": t["sucursal"],
                      "dias": (hoy - (ini or hoy)).days, "compromiso": compromiso.isoformat() if compromiso else None,
                      "vencido": bool(compromiso and compromiso < hoy), "pagado": bool(t.get("pago_registrado_en"))})
    cobrado = _consulta("""
        SELECT COALESCE(SUM(m.monto), 0) AS total
        FROM laboratorio_pago_metodos m JOIN trabajos_laboratorio t ON t.id = m.trabajo_id
        WHERE t.empresa_id = %s AND t.pago_registrado_en >= %s
    """, (empresa_id, hoy.replace(day=1).isoformat()))
    lista.sort(key=lambda x: (not x["vencido"], -x["dias"]))
    orden = list(NOMBRES_LAB)
    return {
        "activos": len(activos), "vencidos": sum(1 for x in lista if x["vencido"]),
        "listos_para_entregar": por_estado.get("listo_entrega", 0),
        "por_pagar": por_pagar, "por_pagar_monto": round(por_pagar_monto, 2), "pagos_por_revisar": pagos_revisar,
        "devoluciones": devoluciones, "facturas_pendientes": facturas,
        "recibidos": rec, "valor_mes": round(valor_mes, 2), "cobrado_mes": round(float(cobrado[0]["total"] or 0), 2),
        "por_estado": [{"etiqueta": _texto(NOMBRES_LAB, e), "valor": n}
                       for e, n in sorted(por_estado.items(), key=lambda kv: orden.index(kv[0]) if kv[0] in orden else 99)],
        "por_sucursal": [{"etiqueta": s, "valor": n} for s, n in sorted(por_sucursal.items(), key=lambda kv: -kv[1])],
        "lista": lista[:15],
    }


def _bloque_soporte(empresa_id, hoy: date):
    filas = _consulta("""
        SELECT folio, cliente_nombre, tipo_servicio, estado, creado_en FROM soporte_reportes
        WHERE empresa_id = %s AND estado NOT IN ('cerrado', 'cancelado')
    """, (empresa_id,))
    por_estado = {}
    lista = []
    for f in filas:
        por_estado[f["estado"]] = por_estado.get(f["estado"], 0) + 1
        ini = _fecha(f.get("creado_en")) or hoy
        lista.append({"folio": f["folio"], "cliente": f.get("cliente_nombre"),
                      "tipo": "Garantía" if f.get("tipo_servicio") == "garantia" else "Mantenimiento",
                      "estado": _texto(NOMBRES_SOPORTE, f["estado"]), "dias": (hoy - ini).days})
    lista.sort(key=lambda x: -x["dias"])
    return {"abiertos": len(filas),
            "por_estado": [{"etiqueta": _texto(NOMBRES_SOPORTE, e), "valor": n} for e, n in por_estado.items()],
            "lista": lista[:10]}


def resumen(empresa_id: int, modulos: dict, dia: date, reporte_asistencia) -> dict:
    """modulos: los de la empresa con llaves acceso_X (db.obtener_modulos_empresa).
    Un bloque que truena no tumba el resto: sale con 'error' y los demás siguen."""
    hoy = db.ahora().date()
    activo = lambda clave: modulos.get(clave, True) is not False
    bloques = {}

    def poner(nombre, fn):
        try:
            bloques[nombre] = fn()
        except Exception as e:  # noqa: BLE001 — se informa en la tarjeta, no se tumba la pantalla
            print(f"[direccion] bloque {nombre}: {e}")
            bloques[nombre] = {"error": "No se pudo cargar esta parte."}

    if activo("acceso_rh"):
        poner("rh", lambda: _bloque_rh(empresa_id, dia, hoy, reporte_asistencia))
    if activo("acceso_reparaciones"):
        poner("reparaciones", lambda: _bloque_reparaciones(empresa_id, hoy))
    poner("proyectos", lambda: _bloque_proyectos(empresa_id, hoy))
    poner("tickets", lambda: _bloque_tickets(empresa_id, hoy))
    if modulos.get("acceso_laboratorio") is True:
        poner("laboratorio", lambda: _bloque_laboratorio(empresa_id, hoy))
    if modulos.get("acceso_soporte") is True:
        poner("soporte", lambda: _bloque_soporte(empresa_id, hoy))
    # Las vacías no estorban: proyectos/tickets/soporte sin nada no se muestran.
    for nombre in ("proyectos", "tickets", "soporte", "laboratorio", "reparaciones"):
        b = bloques.get(nombre)
        if b and not b.get("error") and not any(b.get(k) for k in ("activos", "abiertos", "en_progreso", "pendientes", "completados_mes", "cobrado_mes", "valor_mes")):
            bloques.pop(nombre)
    return {"fecha": dia.isoformat(), "generado": db.ahora().strftime("%Y-%m-%d %H:%M"), "bloques": bloques}


# ---------------------------------------------------------------------------
# 2) CONSULTAS DE MICROSIP
# ---------------------------------------------------------------------------
# Cada consulta: clave, titulo, descripcion, icono (nombre corto que la app
# convierte en ícono), parametros y una función que regresa una "vista":
#   {"resumen": [{"etiqueta", "valor", "formato"}],
#    "tablas":  [{"titulo", "columnas": [{"clave","titulo","formato"}], "filas": [...]}]}
# formato: "dinero" | "numero" | "texto" | "porcentaje" | "fecha".
# Tipos de parámetro (la app sabe pedirlos):
#   periodo        → hoy / ayer / esta semana / este mes / mes pasado / un día
#   sucursal_venta → lista de sucursales de Microsip (Punto de Venta / Pedidos)
#   almacen        → lista de almacenes de Microsip

PERIODOS = [("hoy", "Hoy"), ("ayer", "Ayer"), ("semana", "Esta semana"), ("mes", "Este mes"), ("mes_anterior", "Mes pasado")]


def rango_periodo(valor: str | None, por_defecto: str = "hoy"):
    """'hoy' | 'ayer' | 'semana' | 'mes' | 'mes_anterior' | 'todo' | 'AAAA-MM-DD'
    → (inicio, fin_exclusivo, etiqueta). 'todo' → (None, None, 'Todo')."""
    hoy = db.ahora().date()
    v = (valor or por_defecto).strip()
    if v == "todo":
        return None, None, "Todo"
    if v == "ayer":
        d = hoy - timedelta(days=1)
        return d.isoformat(), hoy.isoformat(), "Ayer"
    if v == "semana":
        ini = hoy - timedelta(days=hoy.weekday())
        return ini.isoformat(), (hoy + timedelta(days=1)).isoformat(), "Esta semana"
    if v == "mes":
        ini = hoy.replace(day=1)
        return ini.isoformat(), (hoy + timedelta(days=1)).isoformat(), "Este mes"
    if v == "mes_anterior":
        fin = hoy.replace(day=1)
        ini = (fin - timedelta(days=1)).replace(day=1)
        return ini.isoformat(), fin.isoformat(), "Mes pasado"
    if v != "hoy":
        try:
            d = datetime.strptime(v, "%Y-%m-%d").date()
            return d.isoformat(), (d + timedelta(days=1)).isoformat(), d.strftime("%d/%m/%Y")
        except ValueError:
            pass
    return hoy.isoformat(), (hoy + timedelta(days=1)).isoformat(), "Hoy"


def _col(clave, titulo, formato="texto"):
    return {"clave": clave, "titulo": titulo, "formato": formato}


def _c_ventas(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"))
    r = microsip.obtener_ventas_pv_por_sucursal(cfg, ini, fin)
    suc = r.get("por_sucursal") or []
    formas = []
    for s in suc:
        for forma, imp in sorted((s.get("formas_cobro") or {}).items(), key=lambda kv: -kv[1]):
            formas.append({"sucursal": s["sucursal"], "forma": forma, "importe": round(imp, 2)})
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Vendido", "valor": round(r.get("total_general") or 0, 2), "formato": "dinero"},
                        {"etiqueta": "Anticipos (aparte)", "valor": round(r.get("total_anticipo") or 0, 2), "formato": "dinero"}],
            "tablas": [{"titulo": "Por sucursal", "columnas": [_col("sucursal", "Sucursal"), _col("total", "Vendido", "dinero"),
                                                                _col("anticipo", "Anticipos", "dinero")],
                        "filas": [{"sucursal": s["sucursal"], "total": round(s.get("total") or 0, 2),
                                   "anticipo": round(s.get("anticipo") or 0, 2)} for s in suc]},
                       {"titulo": "Por forma de cobro", "columnas": [_col("sucursal", "Sucursal"), _col("forma", "Forma de cobro"),
                                                                      _col("importe", "Importe", "dinero")], "filas": formas}]}


def _c_corte(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"))
    r = microsip.obtener_corte_dia_sucursal(cfg, int(p["sucursal_venta"]), None, ini, fin)
    v, a, pe = r.get("ventas_pv") or {}, r.get("anticipos") or {}, r.get("pedidos") or {}
    cols = [_col("forma_cobro", "Forma de cobro"), _col("importe", "Importe", "dinero")]
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Ventas (Punto de Venta)", "valor": v.get("total") or 0, "formato": "dinero"},
                        {"etiqueta": "Anticipos", "valor": a.get("total") or 0, "formato": "dinero"},
                        {"etiqueta": "Pedidos", "valor": pe.get("num_pedidos") or 0, "formato": "numero"},
                        {"etiqueta": "Pedidos con IVA", "valor": pe.get("total_con_iva") or 0, "formato": "dinero"}],
            "tablas": [{"titulo": "Ventas por forma de cobro", "columnas": cols, "filas": v.get("por_forma_cobro") or []},
                       {"titulo": "Anticipos por forma de cobro", "columnas": cols, "filas": a.get("por_forma_cobro") or []}]}


def _c_pedidos(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"), "todo")
    r = microsip.obtener_pedidos_pendientes_por_sucursal(cfg, int(p["sucursal_venta"]), ini, fin, None)
    ped = r.get("pedidos") or []
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Pedidos pendientes", "valor": len(ped), "formato": "numero"},
                        {"etiqueta": "Piezas por surtir", "valor": round(sum(x.get("total_piezas_pendientes") or 0 for x in ped), 2), "formato": "numero"},
                        {"etiqueta": "Valor con IVA", "valor": round(sum(x.get("total_pedido_con_iva") or 0 for x in ped), 2), "formato": "dinero"}],
            "tablas": [{"titulo": "Pedidos", "columnas": [_col("folio", "Folio"), _col("fecha", "Fecha", "fecha"), _col("cliente_nombre", "Cliente"),
                                                           _col("total_piezas_pendientes", "Piezas", "numero"),
                                                           _col("total_pedido_con_iva", "Total con IVA", "dinero")],
                        "filas": [{k: x.get(k) for k in ("folio", "fecha", "cliente_nombre", "total_piezas_pendientes", "total_pedido_con_iva")} for x in ped]},
                       {"titulo": "Productos más pedidos", "columnas": [_col("nombre", "Artículo"), _col("clave", "Clave"),
                                                                       _col("cantidad_pendiente", "Piezas", "numero"),
                                                                       _col("valor_total_con_iva", "Valor con IVA", "dinero")],
                        "filas": [{k: x.get(k) for k in ("nombre", "clave", "cantidad_pendiente", "valor_total_con_iva")}
                                  for x in (r.get("productos_resumen") or [])[:50]]}]}


def _c_cajas(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"))
    r = microsip.obtener_ventas_pv_por_almacen(cfg, int(p["almacen"]), ini, fin)
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Vendido", "valor": round(r.get("total_general") or 0, 2), "formato": "dinero"},
                        {"etiqueta": "Anticipos (aparte)", "valor": round(r.get("total_anticipo") or 0, 2), "formato": "dinero"}],
            "tablas": [{"titulo": "Por caja", "columnas": [_col("caja", "Caja"), _col("total", "Vendido", "dinero"), _col("anticipo", "Anticipos", "dinero")],
                        "filas": [{"caja": c["caja"], "total": round(c.get("total") or 0, 2), "anticipo": round(c.get("anticipo") or 0, 2)}
                                  for c in r.get("por_caja") or []]}]}


def _c_descuentos(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"))
    r = microsip.obtener_descuentos_pv(cfg, ini, fin)
    suc = r.get("por_sucursal") or []
    top = []
    for s in suc:
        for d in s.get("top_descuentos") or []:
            top.append({"sucursal": s.get("sucursal"), **{k: d.get(k) for k in ("cliente", "folio", "fecha", "descuento", "monto", "porcentaje")}})
    top.sort(key=lambda x: -(x.get("descuento") or 0))
    venta = sum(s.get("venta_total") or 0 for s in suc)
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Descuento otorgado", "valor": round(r.get("total_general") or 0, 2), "formato": "dinero"},
                        {"etiqueta": "% sobre la venta", "valor": round((r.get("total_general") or 0) * 100 / venta, 1) if venta else 0, "formato": "porcentaje"}],
            "tablas": [{"titulo": "Por sucursal", "columnas": [_col("sucursal", "Sucursal"), _col("descuento_total", "Descuento", "dinero"),
                                                                _col("venta_total", "Venta", "dinero")],
                        "filas": [{k: s.get(k) for k in ("sucursal", "descuento_total", "venta_total")} for s in suc]},
                       {"titulo": "Descuentos más altos", "columnas": [_col("sucursal", "Sucursal"), _col("cliente", "Cliente"), _col("folio", "Folio"),
                                                                      _col("fecha", "Fecha", "fecha"), _col("descuento", "Descuento", "dinero"),
                                                                      _col("porcentaje", "%", "porcentaje"), _col("monto", "Ticket", "dinero")],
                        "filas": top[:50]}]}


def _c_traspasos(cfg, p):
    ini, fin, et = rango_periodo(p.get("periodo"), "mes")
    r = microsip.obtener_traspasos_entre_sucursales(cfg, ini, fin)
    tr = r.get("traspasos") or []
    filas = [{"folio": t.get("folio_traspaso"), "origen": t.get("origen"), "destino": t.get("destino") or "En tránsito",
              "fecha": t.get("fecha_envio"), "estado": "Recibido" if t.get("estado") == "recibido" else "En tránsito",
              "piezas": round(sum(i.get("cantidad") or 0 for i in t.get("items") or []), 2)} for t in tr]
    return {"subtitulo": et,
            "resumen": [{"etiqueta": "Traspasos", "valor": len(tr), "formato": "numero"},
                        {"etiqueta": "En tránsito", "valor": sum(1 for t in tr if t.get("estado") != "recibido"), "formato": "numero"}],
            "tablas": [{"titulo": "Traspasos", "columnas": [_col("folio", "Folio"), _col("origen", "Sale de"), _col("destino", "Llega a"),
                                                             _col("fecha", "Envío", "fecha"), _col("estado", "Estado"), _col("piezas", "Piezas", "numero")],
                        "filas": filas},
                       {"titulo": "Productos más traspasados", "columnas": [_col("nombre", "Artículo"), _col("clave", "Clave"),
                                                                           _col("cantidad_total", "Piezas", "numero"), _col("num_traspasos", "Traspasos", "numero")],
                        "filas": [{k: x.get(k) for k in ("nombre", "clave", "cantidad_total", "num_traspasos")} for x in r.get("top_productos") or []]}]}


def _vista_inventario(r, etiqueta_valor, clave_precio, titulo_precio):
    suc = r.get("por_sucursal") or []
    top = []
    for s in suc:
        for a in (s.get("top_articulos") or [])[:10]:
            top.append({"sucursal": s.get("sucursal"), "nombre": a.get("nombre"), "cantidad": a.get("cantidad"),
                        "precio": a.get(clave_precio), "valor_total": a.get("valor_total")})
    top.sort(key=lambda x: -(x.get("valor_total") or 0))
    return {"resumen": [{"etiqueta": etiqueta_valor, "valor": round(r.get("total_general") or 0, 2), "formato": "dinero"},
                        {"etiqueta": "Piezas", "valor": round(sum(s.get("unidades_totales") or 0 for s in suc), 2), "formato": "numero"}],
            "tablas": [{"titulo": "Por sucursal", "columnas": [_col("sucursal", "Sucursal"), _col("valor_total", "Valor", "dinero"),
                                                                _col("unidades_totales", "Piezas", "numero")],
                        "filas": [{k: s.get(k) for k in ("sucursal", "valor_total", "unidades_totales")} for s in suc]},
                       {"titulo": "Artículos que más valen", "columnas": [_col("nombre", "Artículo"), _col("sucursal", "Sucursal"),
                                                                         _col("cantidad", "Piezas", "numero"), _col("precio", titulo_precio, "dinero"),
                                                                         _col("valor_total", "Valor", "dinero")],
                        "filas": top[:50]}]}


def _c_inventario_costo(cfg, p):
    return _vista_inventario(microsip.obtener_valor_inventario_por_almacen(cfg, None), "Valor a costo", "costo_unitario", "Costo")


def _c_inventario_venta(cfg, p):
    return _vista_inventario(microsip.obtener_valor_inventario_precio_venta_por_almacen(cfg, None), "Valor a precio de venta",
                             "precio_unitario", "Precio")


def _c_sin_movimiento(cfg, p):
    r = microsip.obtener_articulos_sin_movimiento_por_almacen(cfg, None, None, "con_stock", None, True)
    v = _vista_inventario(r, "Valor detenido (precio de venta)", "precio_unitario", "Precio")
    v["tablas"] = v["tablas"][1:]
    v["tablas"][0]["titulo"] = "Artículos con existencia que nunca se han vendido"
    return v


CONSULTAS = [
    {"clave": "ventas", "titulo": "Ventas por sucursal", "icono": "ventas",
     "descripcion": "Lo vendido en Punto de Venta por sucursal y forma de cobro.",
     "parametros": [{"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "hoy"}], "fn": _c_ventas},
    {"clave": "corte", "titulo": "Corte del día", "icono": "caja",
     "descripcion": "Ventas, anticipos y pedidos de una sucursal.",
     "parametros": [{"clave": "sucursal_venta", "tipo": "sucursal_venta", "etiqueta": "Sucursal", "requerido": True},
                    {"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "hoy"}], "fn": _c_corte},
    {"clave": "cajas", "titulo": "Ventas por caja", "icono": "caja",
     "descripcion": "Lo vendido en cada caja de un almacén.",
     "parametros": [{"clave": "almacen", "tipo": "almacen", "etiqueta": "Almacén", "requerido": True},
                    {"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "hoy"}], "fn": _c_cajas},
    {"clave": "pedidos", "titulo": "Pedidos pendientes", "icono": "pedidos",
     "descripcion": "Pedidos de una sucursal con piezas por surtir.",
     "parametros": [{"clave": "sucursal_venta", "tipo": "sucursal_venta", "etiqueta": "Sucursal", "requerido": True},
                    {"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "todo", "permite_todo": True}], "fn": _c_pedidos},
    {"clave": "descuentos", "titulo": "Descuentos otorgados", "icono": "descuento",
     "descripcion": "Cuánto se descontó por sucursal y los descuentos más altos.",
     "parametros": [{"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "mes"}], "fn": _c_descuentos},
    {"clave": "traspasos", "titulo": "Traspasos entre sucursales", "icono": "traspaso",
     "descripcion": "Mercancía que se movió entre sucursales y lo que sigue en tránsito.",
     "parametros": [{"clave": "periodo", "tipo": "periodo", "etiqueta": "Periodo", "defecto": "mes"}], "fn": _c_traspasos},
    {"clave": "inventario_costo", "titulo": "Valor del inventario (costo)", "icono": "inventario",
     "descripcion": "Cuánto vale lo que hay en cada sucursal, a costo.", "parametros": [], "fn": _c_inventario_costo},
    {"clave": "inventario_venta", "titulo": "Valor del inventario (venta)", "icono": "inventario",
     "descripcion": "Cuánto vale lo que hay en cada sucursal, a precio de venta.", "parametros": [], "fn": _c_inventario_venta},
    {"clave": "sin_movimiento", "titulo": "Artículos sin movimiento", "icono": "alerta",
     "descripcion": "Lo que tiene existencia pero nunca se ha vendido (dinero detenido).", "parametros": [], "fn": _c_sin_movimiento},
]


def lista_consultas():
    return [{k: v for k, v in c.items() if k != "fn"} for c in CONSULTAS]


def ejecutar(clave: str, cfg: dict, parametros: dict) -> dict:
    c = next((x for x in CONSULTAS if x["clave"] == clave), None)
    if not c:
        raise KeyError(clave)
    for p in c["parametros"]:
        if p.get("requerido") and not str(parametros.get(p["clave"]) or "").strip():
            raise ValueError(f"Falta elegir: {p['etiqueta']}")
    vista = c["fn"](cfg, parametros)
    vista.setdefault("subtitulo", None)
    vista["titulo"] = c["titulo"]
    return vista


def opciones(tipo: str, cfg: dict) -> list:
    if tipo == "periodo":
        return [{"valor": v, "etiqueta": e} for v, e in PERIODOS]
    if tipo == "sucursal_venta":
        return [{"valor": str(s["sucursal_id"]), "etiqueta": s["nombre"]} for s in microsip.listar_sucursales_venta(cfg)]
    if tipo == "almacen":
        return [{"valor": str(a["almacen_id"]), "etiqueta": a["nombre"]} for a in microsip.listar_almacenes(cfg)]
    raise KeyError(tipo)
