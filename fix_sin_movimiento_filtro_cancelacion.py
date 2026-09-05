# -*- coding: utf-8 -*-
"""
"Artículos sin movimiento" tenía el mismo bug que ya corregimos en
"Ventas por sucursal": la consulta de "qué artículos ya se vendieron"
filtraba por p.ESTATUS = 'S', y ese campo NUNCA vale 'S' en documentos
reales (siempre 'N' o 'P', sin relación con el corte de caja). Por eso
la lista de "ya vendidos" siempre salía vacía, y artículos que sí se
movieron seguían apareciendo como si nunca se hubieran vendido.

Se cambia a p.FECHA_HORA_CANCELACION IS NULL (documento no cancelado),
mismo criterio ya confirmado con datos reales.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_sin_movimiento_filtro_cancelacion.py
"""
import sys

RUTA = 'backend/microsip.py'

VIEJO = (
    '    cur.execute("""\n'
    '        SELECT DISTINCT d.ARTICULO_ID\n'
    '        FROM DOCTOS_PV_DET d\n'
    '        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n'
    '        WHERE p.ESTATUS = \'S\'\n'
    '    """)\n'
    '    vendidos_alguna_vez = {fila[0] for fila in cur.fetchall()}\n'
)

NUEVO = (
    '    cur.execute("""\n'
    '        SELECT DISTINCT d.ARTICULO_ID\n'
    '        FROM DOCTOS_PV_DET d\n'
    '        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n'
    '        WHERE p.FECHA_HORA_CANCELACION IS NULL\n'
    '    """)\n'
    '    vendidos_alguna_vez = {fila[0] for fila in cur.fetchall()}\n'
)


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if VIEJO in contenido:
        contenido = contenido.replace(VIEJO, NUEVO, 1)
    elif NUEVO in contenido:
        print(f"[{RUTA}] Ya estaba aplicado, no se hizo nada.")
        sys.exit(0)
    else:
        print(f"[{RUTA}] No se encontró el bloque esperado. El archivo pudo haber cambiado desde la última vez.")
        print("Avísale a Claude sin correr git add/commit todavía.")
        sys.exit(1)

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] Corregido.")
    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/microsip.py")
    print("   git commit -m \"Fix: articulos sin movimiento usaba ESTATUS en vez de FECHA_HORA_CANCELACION\"")
    print("   git push")


if __name__ == "__main__":
    main()
