# -*- coding: utf-8 -*-
"""
Cambia el reporte de "Ventas por sucursal" del Dashboard para que sea igual
al "Reporte de cobros" nativo de Microsip: junta lo cobrado en Punto de
Venta (tickets de caja) CON lo cobrado en Cuentas por Cobrar (pagos de
credito, condonaciones, etc.), en vez de solo tickets de caja.

Uso: colocalo en la carpeta del repo (junto a backend/) y corre:
    py fix_ventas_cobros_completo.py
"""
import sys

VIEJO = 'def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):\n    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin\n    (excluida), en formato \'YYYY-MM-DD\', agrupadas por sucursal y forma de\n    cobro. Si los nombres de tabla/columna no coinciden con esta empresa,\n    el error de Firebird se deja tal cual para poder ajustarlo rápido."""\n    con = _conectar(config)\n    cur = con.cursor()\n    cur.execute("""\n        SELECT COALESCE(s.NOMBRE, \'Sin sucursal\'), fc.NOMBRE, SUM(fcd.IMPORTE)\n        FROM DOCTOS_PV p\n        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\'\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    por_sucursal = {}\n    total_general = 0.0\n    for sucursal, forma_cobro, importe in filas:\n        importe = float(importe or 0)\n        sucursal = (sucursal or "Sin sucursal").strip()\n        forma_cobro = (forma_cobro or "Sin especificar").strip()\n        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0})\n        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe\n        entrada["total"] += importe\n        total_general += importe\n\n    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])\n    return {"por_sucursal": resultado, "total_general": total_general}'
NUEVO = 'def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):\n    """TODO el dinero cobrado entre fecha_inicio (incluida) y fecha_fin\n    (excluida), en formato \'YYYY-MM-DD\', agrupado por sucursal y forma de\n    cobro — igual que el "Reporte de cobros" nativo de Microsip: junta lo\n    cobrado en Punto de Venta (tickets de caja) CON lo cobrado en Cuentas\n    por Cobrar (pagos de crédito, condonaciones, etc.), ya que ambos usan\n    la misma tabla de formas de cobro (FORMAS_COBRO_DOCTOS es compartida,\n    distinguida por NOM_TABLA_DOCTOS). Si los nombres de tabla/columna no\n    coinciden con esta empresa, el error de Firebird se deja tal cual."""\n    con = _conectar(config)\n    cur = con.cursor()\n    cur.execute("""\n        SELECT sucursal, forma_cobro, SUM(importe)\n        FROM (\n            SELECT s.NOMBRE AS sucursal, fc.NOMBRE AS forma_cobro, fcd.IMPORTE AS importe\n            FROM FORMAS_COBRO_DOCTOS fcd\n            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n            JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = fcd.DOCTO_ID\n            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n            WHERE fcd.NOM_TABLA_DOCTOS = \'DOCTOS_PV\' AND p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n\n            UNION ALL\n\n            SELECT s.NOMBRE, fc.NOMBRE, fcd.IMPORTE\n            FROM FORMAS_COBRO_DOCTOS fcd\n            JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n            JOIN DOCTOS_CC cc ON cc.DOCTO_CC_ID = fcd.DOCTO_ID\n            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = cc.SUCURSAL_ID\n            WHERE fcd.NOM_TABLA_DOCTOS = \'DOCTOS_CC\' AND cc.FECHA >= ? AND cc.FECHA < ? AND cc.ESTATUS <> \'C\'\n        ) t\n        GROUP BY 1, 2\n        ORDER BY 1, 2\n    """, (fecha_inicio, fecha_fin, fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    por_sucursal = {}\n    total_general = 0.0\n    for sucursal, forma_cobro, importe in filas:\n        importe = float(importe or 0)\n        sucursal = (sucursal or "Sin sucursal").strip()\n        forma_cobro = (forma_cobro or "Sin especificar").strip()\n        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0})\n        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe\n        entrada["total"] += importe\n        total_general += importe\n\n    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])\n    return {"por_sucursal": resultado, "total_general": total_general}'


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
    print('   git commit -m "Ventas por sucursal ahora junta PV + CC, igual que Reporte de cobros"')
    print("   git push")


if __name__ == "__main__":
    main()
