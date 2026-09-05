# -*- coding: utf-8 -*-
"""
Regresa "Ventas por sucursal" del Dashboard a mostrar SOLO Punto de Venta
(se revierte el intento de juntarlo con Cuentas por Cobrar, ya que no se
encontro la tabla real donde vive la forma de cobro para CxC en este
Microsip). Punto de Venta ya se confirmo exacto y funcionando bien.

Uso: colocalo en la carpeta del repo (junto a backend/) y corre:
    py fix_revertir_solo_pv.py
"""
import sys

VIEJO = '    cur.execute("""\n        SELECT sucursal, forma_cobro, SUM(importe)\n        FROM (\n            SELECT s.NOMBRE AS sucursal, fc.NOMBRE AS forma_cobro, fcd.IMPORTE AS importe\n            FROM FORMAS_COBRO_DOCTOS fcd\n            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n            JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = fcd.DOCTO_ID\n            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n            WHERE fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\' AND p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n\n            UNION ALL\n\n            SELECT s.NOMBRE, fc.NOMBRE, fcd.IMPORTE\n            FROM FORMAS_COBRO_DOCTOS fcd\n            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n            JOIN DOCTOS_CC cc ON cc.DOCTO_CC_ID = fcd.DOCTO_ID\n            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = cc.SUCURSAL_ID\n            WHERE fcd.NOM_TABLA_DOCTOS = \'DOCTOS_CC\' AND cc.FECHA >= ? AND cc.FECHA < ? AND cc.ESTATUS <> \'C\'\n        ) t\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin, fecha_inicio, fecha_fin))'
NUEVO = '    cur.execute("""\n        SELECT COALESCE(s.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n        FROM DOCTOS_PV p\n        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\'\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin))'
DOCSTRING_VIEJO = '    """TODO el dinero cobrado entre fecha_inicio (incluida) y fecha_fin\n    (excluida), en formato \'YYYY-MM-DD\', agrupado por sucursal y forma de\n    cobro — igual que el "Reporte de cobros" nativo de Microsip: junta lo\n    cobrado en Punto de Venta (tickets de caja) CON lo cobrado en Cuentas\n    por Cobrar (pagos de crédito, condonaciones, etc.), ya que ambos usan\n    la misma tabla de formas de cobro (FORMAS_COBRO_DOCTOS es compartida,\n    distinguida por NOM_TABLA_DOCTOS). Si los nombres de tabla/columna no\n    coinciden con esta empresa, el error de Firebird se deja tal cual."""'
DOCSTRING_NUEVO = '    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n    (excluida), en formato \'YYYY-MM-DD\', agrupadas por sucursal y forma de\n    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por\n    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se\n    encontró la tabla real donde esa forma de cobro vive para CxC — se\n    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se\n    encuentra esa conexión, se puede volver a ampliar.) Si los nombres de\n    tabla/columna no coinciden con esta empresa, el error de Firebird se\n    deja tal cual para poder ajustarlo rápido."""'


def main():
    ruta = "backend/microsip.py"
    try:
        with open(ruta, "r", encoding="utf-8", newline=None) as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        sys.exit(1)

    ya_aplicado = NUEVO in contenido and DOCSTRING_NUEVO in contenido
    if ya_aplicado:
        print(f"[{ruta}] Ya estaba aplicado. No hace falta nada.")
        return

    if DOCSTRING_VIEJO not in contenido or VIEJO not in contenido:
        print(f"[{ruta}] No encontre el bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
        sys.exit(1)

    contenido = contenido.replace(DOCSTRING_VIEJO, DOCSTRING_NUEVO, 1)
    contenido = contenido.replace(VIEJO, NUEVO, 1)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)
    print(f"[{ruta}] Revertido a solo Punto de Venta.")
    print()
    print("Ahora corre:")
    print("   git add backend/microsip.py")
    print('   git commit -m "Revertir ventas por sucursal a solo Punto de Venta"')
    print("   git push")


if __name__ == "__main__":
    main()
