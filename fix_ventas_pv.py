# -*- coding: utf-8 -*-
"""
Corrige la consulta de ventas de Punto de Venta por forma de cobro: la
columna correcta es DOCTO_ID (generica, compartida entre modulos) en vez de
DOCTO_PV_ID, y hay que filtrar por NOM_TABLA_DOCTOS = 'DOCTOS_PV'.

Uso: colocalo en la carpeta del repo (junto a backend/) y corre:
    py fix_ventas_pv.py
"""
import sys

VIEJO = '    cur.execute("""\n        SELECT COALESCE(a.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n        FROM DOCTOS_PV p\n        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_PV_ID = p.DOCTO_PV_ID\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN ALMACENES a ON a.ALMACEN_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin))'
NUEVO = '    cur.execute("""\n        SELECT COALESCE(a.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n        FROM DOCTOS_PV p\n        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\'\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN ALMACENES a ON a.ALMACEN_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin))'


def main():
    ruta = "backend/microsip.py"
    try:
        with open(ruta, "r", encoding="utf-8", newline=None) as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        sys.exit(1)

    if NUEVO in contenido:
        print(f"[{ruta}] Ya estaba aplicado. No hace falta nada.")
        return

    if VIEJO not in contenido:
        print(f"[{ruta}] No encontre el bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
        sys.exit(1)

    contenido = contenido.replace(VIEJO, NUEVO, 1)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)
    print(f"[{ruta}] Corregido.")
    print()
    print("Ahora corre:")
    print("   git add backend/microsip.py")
    print('   git commit -m "Fix: columna correcta en FORMAS_COBRO_DOCTOS (DOCTO_ID + NOM_TABLA_DOCTOS)"')
    print("   git push")


if __name__ == "__main__":
    main()
