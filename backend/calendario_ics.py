# -*- coding: utf-8 -*-
"""Genera archivos de calendario (.ics, formato iCalendar / RFC 5545) para
que cada persona se suscriba UNA vez desde su celular (iPhone o Android) y,
de ahí en adelante, los proyectos y mantenimientos que le tocan aparezcan
solos en su calendario — sin necesitar ninguna integración oficial con
Apple/Google (que requeriría registrar la app como desarrollador ante
ambos, algo fuera de alcance para una app interna como esta)."""
from datetime import datetime
from zoneinfo import ZoneInfo


def _escapar_texto(texto):
    """RFC 5545: hay que escapar backslash, coma, punto y coma, y saltos de línea."""
    if not texto:
        return ""
    return (
        texto.replace("\\", "\\\\")
             .replace(";", "\\;")
             .replace(",", "\\,")
             .replace("\n", "\\n")
    )


def _fecha_a_ics(fecha_texto):
    """Convierte 'YYYY-MM-DD' (o un texto con hora pegada) al formato de
    fecha de un evento de todo el día en iCalendar: YYYYMMDD."""
    solo_fecha = fecha_texto[:10].replace("-", "")
    return solo_fecha


def generar_ics(nombre_empresa, eventos):
    """eventos: lista de dicts con tipo, id, titulo, descripcion, fecha
    (tal como los regresa db.listar_eventos_calendario_usuario)."""
    ahora = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mark Inc TI//Tickets y Proyectos//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escapar_texto(nombre_empresa)} — Proyectos y mantenimientos",
        "X-WR-TIMEZONE:America/Mexico_City",
        # Refrescar cada 4 horas es un valor sugerido — Apple/Google lo
        # respetan la mayoría de las veces, aunque no está 100% garantizado
        # (cada calendario decide su propio intervalo real de sincronía).
        "REFRESH-INTERVAL;VALUE=DURATION:PT4H",
        "X-PUBLISHED-TTL:PT4H",
    ]
    for ev in eventos:
        fecha_ics = _fecha_a_ics(ev["fecha"])
        uid = f"{ev['tipo']}-{ev['id']}@tickets-ti.markinc"
        lineas += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{ahora}",
            f"DTSTART;VALUE=DATE:{fecha_ics}",
            f"SUMMARY:{_escapar_texto(ev['titulo'])}",
        ]
        if ev.get("descripcion"):
            lineas.append(f"DESCRIPTION:{_escapar_texto(ev['descripcion'])}")
        lineas.append("END:VEVENT")
    lineas.append("END:VCALENDAR")
    # iCalendar exige terminar cada línea con \r\n (no solo \n).
    return "\r\n".join(lineas) + "\r\n"
