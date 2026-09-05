# -*- coding: utf-8 -*-
"""
Corrige la causa real de que "Ventas por sucursal" saliera vacío (ni
siquiera era el corte de caja): el filtro WHERE p.ESTATUS = 'S' estaba
mal. Se confirmó con datos reales de Microsip que documentos de ventas
completamente normales y cobradas (de hoy, de ayer, de meses atrás) NUNCA
tienen ESTATUS = 'S' — tienen 'N' o 'P'. El campo confiable para saber si
un documento sigue siendo válido es FECHA_HORA_CANCELACION: si está vacío
(NULL), el documento nunca se canceló.

Se cambia el filtro en las dos consultas (ventas normales y anticipo) de
"p.ESTATUS = 'S'" a "p.FECHA_HORA_CANCELACION IS NULL".

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_ventas_pv_filtro_cancelacion.py
"""
import sys

RUTA = 'backend/microsip.py'

VIEJO = (
    "        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'\n"
    "        GROUP BY 1, 2\n"
)

NUEVO = (
    "        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.FECHA_HORA_CANCELACION IS NULL\n"
    "        GROUP BY 1, 2\n"
)

VIEJO_ANTICIPO = (
    "            WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S' AND a.NOMBRE = 'ANTICIPO'\n"
)

NUEVO_ANTICIPO = (
    "            WHERE p.FECHA >= ? AND p.FECHA < ? AND p.FECHA_HORA_CANCELACION IS NULL AND a.NOMBRE = 'ANTICIPO'\n"
)

VIEJO_DOCSTRING = (
    '    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n'
    "    (excluida), en formato 'YYYY-MM-DD', agrupadas por sucursal y forma de\n"
)

NUEVO_DOCSTRING = (
    '    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n'
    "    (excluida), en formato 'YYYY-MM-DD', agrupadas por sucursal y forma de\n"
    "    cobro. Un documento cuenta como válido si FECHA_HORA_CANCELACION está\n"
    "    vacío (nunca se canceló) — el campo ESTATUS NO sirve para esto: se\n"
    "    confirmó con datos reales que documentos normales y ya cobrados\n"
    "    tienen ESTATUS 'N' o 'P', nunca 'S'.\n"
)


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    cambios = 0
    hubo_error = False
    for viejo, nuevo in [(VIEJO_DOCSTRING, NUEVO_DOCSTRING), (VIEJO, NUEVO), (VIEJO_ANTICIPO, NUEVO_ANTICIPO)]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print(f"[{RUTA}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
            hubo_error = True

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] {cambios}/3 cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/microsip.py")
    print("   git commit -m \"Fix: filtro real de Ventas por sucursal (FECHA_HORA_CANCELACION, no ESTATUS)\"")
    print("   git push")


if __name__ == "__main__":
    main()
