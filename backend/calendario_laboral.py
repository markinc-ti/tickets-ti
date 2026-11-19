# -*- coding: utf-8 -*-
"""Calendario laboral para contar días de vacaciones.

Un día de vacaciones solo se cuenta si es laborable: NO se cuentan los
domingos (descanso semanal) ni los días de descanso obligatorio de la Ley
Federal del Trabajo (art. 74). El sábado sí cuenta, igual que en Microsip.

Si la empresa da otro día de asueto (p. ej. 24 o 31 de diciembre), se agrega
en DIAS_EXTRA como (mes, día).
"""
from datetime import date, timedelta

# Asuetos de la empresa que tampoco cuentan como día de vacaciones: [(mes, día), ...]
DIAS_EXTRA = [(12, 24), (12, 31)]  # 24 y 31 de diciembre


def _lunes_numero(anio, mes, n):
    """El n-ésimo lunes del mes."""
    d = date(anio, mes, 1)
    d += timedelta(days=(0 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def festivos(anio):
    """{fecha: nombre} de los días de descanso obligatorio (LFT art. 74) del año."""
    f = {
        date(anio, 1, 1): "Año Nuevo",
        _lunes_numero(anio, 2, 1): "Día de la Constitución",
        _lunes_numero(anio, 3, 3): "Natalicio de Benito Juárez",
        date(anio, 5, 1): "Día del Trabajo",
        date(anio, 9, 16): "Día de la Independencia",
        _lunes_numero(anio, 11, 3): "Día de la Revolución",
        date(anio, 12, 25): "Navidad",
    }
    if anio >= 2024 and (anio - 2024) % 6 == 0:
        f[date(anio, 10, 1)] = "Transmisión del Poder Ejecutivo Federal"
    for mes, dia in DIAS_EXTRA:
        try:
            f.setdefault(date(anio, mes, dia), "Asueto de la empresa")
        except ValueError:
            pass
    return f


def es_festivo(d):
    return d in festivos(d.year)


def es_descanso(d):
    """Domingo o festivo: no cuenta como día de vacaciones."""
    return d.weekday() == 6 or es_festivo(d)


def rango_laboral(inicio, dias):
    """Reparte `dias` de vacaciones desde `inicio` brincando domingos y festivos.

    Regresa (dias_tomados, ultimo_dia, regreso, brincados):
      dias_tomados: lista de fechas que sí cuentan como vacaciones;
      ultimo_dia: el último de ellos;
      regreso: el siguiente día laborable;
      brincados: [(fecha, motivo)] domingos y festivos que quedaron dentro del periodo.
    Medio día (ej. 1.5) ocupa un día más."""
    n = max(int(-(-float(dias or 0) // 1)), 1)  # techo
    d, tomados, brincados = inicio, [], []
    while len(tomados) < n:
        if es_descanso(d):
            if tomados:  # lo que cae antes del primer día no es parte del periodo
                brincados.append((d, "Domingo" if d.weekday() == 6 else festivos(d.year)[d]))
        else:
            tomados.append(d)
        d += timedelta(days=1)
    regreso = d
    while es_descanso(regreso):
        regreso += timedelta(days=1)
    return tomados, tomados[-1], regreso, brincados
