# -*- coding: utf-8 -*-
"""Importar a Soporte técnico el Excel histórico de reportes (formato "SISTEMA DE SOPORTE TÉCNICO" de Peymar).

Lee la hoja de reportes (la que tiene la columna FOLIO), acomoda cada columna en su campo
del módulo y guarda lo que no tiene campo propio en `importado_json` (se ve en el detalle
y cuenta en el Análisis). No crea firmas ni manda WhatsApp: es historial.
"""
import io
import re
import unicodedata
from datetime import date, datetime

TIPOS = {  # texto del Excel (normalizado) -> tipo_servicio
    "garantia": "garantia", "garantia de servicio": "garantia",
    "servicio": "mantenimiento", "mantenimiento": "mantenimiento",
    "asesoria": "asesoria", "otro": "otro",
}
ESTADOS = {  # STATUS del Excel (normalizado) -> estado del módulo
    "cerrado": "cerrado", "cancelado": "cancelado",
    "partes enviadas": "enviado", "rastreando envio": "enviado", "paquete recibido": "enviado",
}  # todo lo demás (Abierto, Esperando…, Solicitud…, Cita programada…) -> diagnostico
CAUSAS = {  # CAUSA del Excel -> causa del apartado interno (lo que no está, va a "Otro")
    "mala calidad del material": "Mala calidad del material",
    "baja calidad del material o componente": "Baja calidad",
    "material fuera de especificaciones": "Baja calidad",
    "falla en la caja de control": "Equipo o piezas defectuosas",
    "dano durante la trasportacion": "Métodos de envío",
    "dano durante la transportacion": "Métodos de envío",
}


def norm(v):
    """Texto en minúsculas, sin acentos ni espacios dobles (para comparar encabezados y valores)."""
    s = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode()
    return " ".join(s.split()).casefold()


def _txt(v):
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    s = " ".join(str(v).replace("\r", "").split()) if "\n" not in str(v) else str(v).strip()
    return s or None


def _fecha(v):
    """ISO 'YYYY-MM-DD' o None (acepta fecha de Excel o texto dd/mm/aaaa)."""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d") if v.year > 1900 else None
    if isinstance(v, date):
        return v.isoformat()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(v or ""))
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _familia(modelo):
    """Línea de la unidad sin el año: "LUXOR 2025" -> "LUXOR", "NOVO X" y "NOVOX 2025" -> "NOVOX"."""
    if not modelo:
        return None
    m = re.sub(r"\s*\b20\d\d\b", "", str(modelo).upper()).replace("C.F.", "CF").replace("R.X.", "RX")
    m = re.sub(r"\b(NOVO|NOVA|JOY)\s+X\b", r"\1X", " ".join(m.split()))
    return m.strip() or None


def _folio(v):
    if isinstance(v, (int, float)) and float(v).is_integer() and v > 0:
        return int(v)
    s = str(v or "").strip()
    return int(s) if s.isdigit() and int(s) > 0 else None


def leer_excel(contenido: bytes):
    """Regresa (filas, avisos). Cada fila es un dict listo para guardarse."""
    from openpyxl import load_workbook
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    hoja, enc_fila, filas_hoja = None, None, None
    for ws in wb.worksheets:
        filas_hoja = list(ws.iter_rows(values_only=True))
        for i, fila in enumerate(filas_hoja[:15]):
            if any(norm(c) == "folio" for c in fila) and any("cliente" == norm(c) for c in fila):
                hoja, enc_fila = ws, i
                break
        if hoja:
            break
    if not hoja:
        raise ValueError("No encontré la hoja de reportes: debe tener las columnas FOLIO y CLIENTE.")
    enc = [norm(c) for c in filas_hoja[enc_fila]]
    # Encabezados de la fila de arriba (ej. "TOTAL", "COSTO DE ENVIO") para columnas sin nombre abajo.
    arriba = [norm(c) for c in filas_hoja[enc_fila - 1]] if enc_fila > 0 else []
    for j, a in enumerate(arriba):
        if j < len(enc) and not enc[j] and a:
            enc[j] = a

    def col(*nombres, empieza=False):
        for n in nombres:
            n = norm(n)
            for j, e in enumerate(enc):
                if e == n or (empieza and e.startswith(n)):
                    return j
        return None

    C = {
        "folio": col("folio"), "tipo": col("tipo de reporte"), "fecha": col("fecha del reporte"),
        "status": col("status"), "cliente": col("cliente"), "direccion": col("direccion"),
        "telefono": col("numero", "telefono", "whatsapp"), "seguimiento": col("seguimiento"),
        "modelo": col("modelo del equipo", "modelo"), "serie": col("numero de serie"),
        "fecha_compra": col("fecha de compra"), "garantia": col("status de garantia", empieza=True),
        "distribuidor": col("distribuidor"), "folio_fabrica": col("folio de fabrica"),
        "periodo1": col("periodo 1"), "periodo2": col("periodo 2"),
        "problema": col("descripcion de la falla", empieza=True), "tipo_falla": col("tipo de falla"),
        "causa": col("causa"), "accion": col("accion"), "notas_refacciones": col("notas adicionales"),
        "envio": col("envio de refacciones"), "tecnico": col("tecnico asignado"),
        "fecha_tecnico": col("fecha de asignacion del tecnico"), "guia": col("guia"),
        "paqueteria": col("paqueteria"), "fecha_envio": col("fecha de envio"),
        "fecha_entrega": col("fecha de entrega"), "atendio": col("quien atendio"),
        "fecha_cierre": col("fecha de cierre del reporte"), "devolucion": col("devolucion de piezas danadas"),
        "calificacion": col("calificacion"), "total": col("total"), "costo_envio": col("costo de envio"),
        "genera_costo": col("si genera costo"), "responsable": col("responsable"),
    }
    # "Notas adicionales" sale dos veces: la 1a es de refacciones y la 2a (después de Fecha de asignación) del técnico.
    notas = [j for j, e in enumerate(enc) if e == "notas adicionales"]
    C["notas_tecnico"] = notas[1] if len(notas) > 1 else None
    refacciones = []
    for k in range(1, 21):
        r, c = col(f"refaccion {k}"), col(f"cant {k}")
        if r is not None:
            refacciones.append((r, c))
    if C["folio"] is None or C["cliente"] is None:
        raise ValueError("Faltan las columnas FOLIO o CLIENTE.")

    def val(fila, clave):
        j = C.get(clave)
        return fila[j] if j is not None and j < len(fila) else None

    filas, avisos, vacias = [], [], 0
    for n, fila in enumerate(filas_hoja[enc_fila + 1:], start=enc_fila + 2):
        if not fila or all(c in (None, "") for c in fila):
            continue
        cliente, problema = _txt(val(fila, "cliente")), _txt(val(fila, "problema"))
        if not cliente and not problema:
            vacias += 1  # folio apartado sin capturar
            continue
        tipo_x = _txt(val(fila, "tipo")) or ""
        status_x = _txt(val(fila, "status")) or ""
        refac = []
        for r, c in refacciones:
            d = _txt(fila[r]) if r < len(fila) else None
            if d and d != "-":
                try:
                    cant = float(fila[c]) if c is not None and c < len(fila) and fila[c] not in (None, "") else 1
                except (TypeError, ValueError):
                    cant = 1
                refac.append({"cantidad": int(cant) if cant == int(cant) else cant, "descripcion": d[:300], "numero_parte": None})
        causa_x = _txt(val(fila, "causa"))
        causa = CAUSAS.get(norm(causa_x)) if causa_x else None
        costos = []
        for clave, concepto in (("total", "Costo total (Excel)"), ("costo_envio", "Costo de envío (Excel)")):
            try:
                m = float(val(fila, clave))
                if m:
                    costos.append({"concepto": concepto, "monto": round(m, 2)})
            except (TypeError, ValueError):
                pass
        fecha = _fecha(val(fila, "fecha"))
        modelo = _txt(val(fila, "modelo"))
        accion = _txt(val(fila, "accion"))
        tipo_falla = _txt(val(fila, "tipo_falla"))
        importado = {k: _txt(val(fila, k)) for k in (
            "seguimiento", "garantia", "folio_fabrica", "periodo1", "periodo2", "tipo_falla", "causa", "accion",
            "envio", "tecnico", "notas_tecnico", "atendio", "devolucion", "calificacion", "genera_costo", "responsable",
            "notas_refacciones")}
        importado.update({
            "folio_original": _txt(val(fila, "folio")), "estatus_original": status_x or None,
            "tipo_original": tipo_x or None, "fila_excel": n,
            "fecha_compra": _fecha(val(fila, "fecha_compra")) or _txt(val(fila, "fecha_compra")),
            "fecha_tecnico": _fecha(val(fila, "fecha_tecnico")),
            "fecha_envio": _fecha(val(fila, "fecha_envio")),
            "fecha_entrega": _fecha(val(fila, "fecha_entrega")), "fecha_entrega_texto": _txt(val(fila, "fecha_entrega")),
            "fecha_cierre": _fecha(val(fila, "fecha_cierre")),
        })
        importado = {k: v for k, v in importado.items() if v not in (None, "", "-")}
        importado["clave"] = f"{importado.get('folio_original')}|{norm(cliente)}|{fecha}"
        filas.append({
            "folio": _folio(val(fila, "folio")),
            "tipo_servicio": TIPOS.get(norm(tipo_x), "garantia" if "garant" in norm(tipo_x) else "otro"),
            # "Abierto" pero ya con fecha de envío de refacciones: en el sistema queda como Enviado.
            "estado": ESTADOS.get(norm(status_x)) or ("enviado" if importado.get("fecha_envio") else "diagnostico"),
            "cliente_nombre": (cliente or "(sin nombre)")[:200],
            "cliente_telefono": (_txt(val(fila, "telefono")) or "")[:40] or None,
            "cliente_direccion": (_txt(val(fila, "direccion")) or "")[:400] or None,
            "tipo_unidad": _familia(modelo),
            "modelo": modelo, "numero_serie": _txt(val(fila, "serie")),
            "problema": (problema or "(sin descripción en el Excel)")[:5000],
            "diagnostico": " · ".join(x for x in (f"Tipo de falla: {tipo_falla}" if tipo_falla else None,
                                                  f"Causa: {causa_x}" if causa_x else None) if x) or None,
            "resolucion": accion,
            "paqueteria": _txt(val(fila, "paqueteria")),
            "refacciones": refac,
            "interno": {
                "causas": [causa or "Otro"] if causa_x else [], "causa_otro": causa_x if causa_x and not causa else None,
                "causa_falla": causa_x, "metodo_envio": _txt(val(fila, "envio")), "guia": _txt(val(fila, "guia")),
                "paqueteria_tipo": None, "paqueteria_nombre": _txt(val(fila, "paqueteria")),
                "distribuidor": _txt(val(fila, "distribuidor")), "costos": costos,
                "costo_total": round(sum(c["monto"] for c in costos), 2),
                "notas": _txt(val(fila, "notas_tecnico")),
            },
            "creado_en": f"{fecha}T00:00:00" if fecha else None,
            "cerrado_en": importado.get("fecha_cierre") or importado.get("fecha_entrega") or importado.get("fecha_envio"),
            "importado": importado,
        })
    if vacias:
        avisos.append(f"{vacias} renglón(es) solo tienen folio, sin cliente ni falla: no se importan.")
    vistos, repetidos, sin_folio = set(), [], 0
    for f in filas:
        if f["folio"] is None:
            sin_folio += 1
        elif f["folio"] in vistos:
            repetidos.append(f["folio"])
            f["folio"] = None
        else:
            vistos.add(f["folio"])
    if sin_folio:
        avisos.append(f"{sin_folio} reporte(s) sin folio numérico válido (ej. «4620A» o vacío): se les da un folio nuevo y se guarda el original.")
    if repetidos:
        avisos.append(f"Folios repetidos en el Excel: {', '.join(str(x) for x in sorted(set(repetidos)))}. El segundo se guarda con folio nuevo.")
    sin_fecha = sum(1 for f in filas if not f["creado_en"])
    if sin_fecha:
        avisos.append(f"{sin_fecha} reporte(s) sin fecha del reporte: se guardan con la fecha de hoy.")
    return filas, avisos
