# -*- coding: utf-8 -*-
"""
Corrige un bug introducido por fix_anticipo.py: al reutilizar el MISMO
cursor de Firebird para dos consultas seguidas (ventas por forma de cobro,
y luego el anticipo), el driver deja vacíos los resultados de la primera
consulta -- por eso "Ventas por sucursal" empezó a salir vacío incluso en
la vista de Día.

Este script:
1. Usa un cursor separado para cada consulta.
2. Envuelve la consulta del anticipo en try/except: si esa consulta en
   particular fallara por cualquier motivo, ya no tumba el desglose
   principal de ventas -- simplemente no se descuenta ningún anticipo ese
   rato, y las ventas normales se siguen viendo bien.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_anticipo_v2.py
"""
import sys

FUNCION_VIEJA = '''def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):
    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin
    (excluida), en formato 'YYYY-MM-DD', agrupadas por sucursal y forma de
    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por
    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se
    encontró la tabla real donde esa forma de cobro vive para CxC — se
    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se
    encuentra esa conexión, se puede volver a ampliar.) El artículo
    "ANTICIPO" se descuenta del total de cada sucursal (y se reporta
    aparte como "anticipo"/"total_anticipo") porque es un cobro
    adelantado, no una venta real — se identifica por NOMBRE del
    artículo, no por ID fijo, para que siga funcionando si cambia de
    empresa/base. Si los nombres de tabla/columna no coinciden con esta
    empresa, el error de Firebird se deja tal cual para poder ajustarlo
    rápido."""
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), fc.NOMBRE, SUM(fcd.IMPORTE)
        FROM DOCTOS_PV p
        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV'
        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, (fecha_inicio, fecha_fin))
    filas = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), SUM(d.PRECIO_TOTAL_NETO)
        FROM DOCTOS_PV p
        JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID
        JOIN ARTICULOS a ON a.ARTICULO_ID = d.ARTICULO_ID
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S' AND a.NOMBRE = 'ANTICIPO'
        GROUP BY 1
    """, (fecha_inicio, fecha_fin))
    filas_anticipo = cur.fetchall()
    con.close()

    anticipos_por_sucursal = {}
    for sucursal, importe in filas_anticipo:
        sucursal = (sucursal or "Sin sucursal").strip()
        anticipos_por_sucursal[sucursal] = anticipos_por_sucursal.get(sucursal, 0.0) + float(importe or 0)

    por_sucursal = {}
    total_general = 0.0
    for sucursal, forma_cobro, importe in filas:
        importe = float(importe or 0)
        sucursal = (sucursal or "Sin sucursal").strip()
        forma_cobro = (forma_cobro or "Sin especificar").strip()
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe
        entrada["total"] += importe
        total_general += importe

    total_anticipo_general = 0.0
    for sucursal, anticipo in anticipos_por_sucursal.items():
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["anticipo"] = anticipo
        entrada["total"] -= anticipo
        total_general -= anticipo
        total_anticipo_general += anticipo

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}


'''

FUNCION_NUEVA = '''def obtener_ventas_pv_por_sucursal(config: dict, fecha_inicio: str, fecha_fin: str):
    """Ventas de Punto de Venta entre fecha_inicio (incluida) y fecha_fin
    (excluida), en formato 'YYYY-MM-DD', agrupadas por sucursal y forma de
    cobro. (Nota: se probó ampliar esto para juntar también Cuentas por
    Cobrar, como hace el "Reporte de cobros" nativo de Microsip, pero no se
    encontró la tabla real donde esa forma de cobro vive para CxC — se
    revirtió a solo Punto de Venta, que sí es exacto. Si en el futuro se
    encuentra esa conexión, se puede volver a ampliar.) El artículo
    "ANTICIPO" se descuenta del total de cada sucursal (y se reporta
    aparte como "anticipo"/"total_anticipo") porque es un cobro
    adelantado, no una venta real — se identifica por NOMBRE del
    artículo, no por ID fijo, para que siga funcionando si cambia de
    empresa/base. Se usa un cursor separado para esta segunda consulta
    (reusar el mismo cursor para dos SELECT seguidos dejaba vacía la
    primera consulta con este driver de Firebird), y va envuelta en
    try/except: si llegara a fallar, no tumba el desglose principal de
    ventas, simplemente no se descuenta ningún anticipo ese rato. Si los
    nombres de tabla/columna no coinciden con esta empresa, el error de
    Firebird de la consulta principal se deja tal cual para poder
    ajustarlo rápido."""
    con = _conectar(config)
    cur = con.cursor()
    cur.execute("""
        SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), fc.NOMBRE, SUM(fcd.IMPORTE)
        FROM DOCTOS_PV p
        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV'
        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID
        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, (fecha_inicio, fecha_fin))
    filas = cur.fetchall()
    cur.close()

    filas_anticipo = []
    try:
        cur2 = con.cursor()
        cur2.execute("""
            SELECT COALESCE(s.NOMBRE, 'Sin sucursal'), SUM(d.PRECIO_TOTAL_NETO)
            FROM DOCTOS_PV p
            JOIN DOCTOS_PV_DET d ON d.DOCTO_PV_ID = p.DOCTO_PV_ID
            JOIN ARTICULOS a ON a.ARTICULO_ID = d.ARTICULO_ID
            LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID
            WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S' AND a.NOMBRE = 'ANTICIPO'
            GROUP BY 1
        """, (fecha_inicio, fecha_fin))
        filas_anticipo = cur2.fetchall()
        cur2.close()
    except Exception:
        filas_anticipo = []
    con.close()

    anticipos_por_sucursal = {}
    for sucursal, importe in filas_anticipo:
        sucursal = (sucursal or "Sin sucursal").strip()
        anticipos_por_sucursal[sucursal] = anticipos_por_sucursal.get(sucursal, 0.0) + float(importe or 0)

    por_sucursal = {}
    total_general = 0.0
    for sucursal, forma_cobro, importe in filas:
        importe = float(importe or 0)
        sucursal = (sucursal or "Sin sucursal").strip()
        forma_cobro = (forma_cobro or "Sin especificar").strip()
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["formas_cobro"][forma_cobro] = entrada["formas_cobro"].get(forma_cobro, 0.0) + importe
        entrada["total"] += importe
        total_general += importe

    total_anticipo_general = 0.0
    for sucursal, anticipo in anticipos_por_sucursal.items():
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["anticipo"] = anticipo
        entrada["total"] -= anticipo
        total_general -= anticipo
        total_anticipo_general += anticipo

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}


'''

RUTA = 'backend/microsip.py'


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if FUNCION_VIEJA in contenido:
        contenido = contenido.replace(FUNCION_VIEJA, FUNCION_NUEVA, 1)
    elif FUNCION_NUEVA in contenido:
        print(f"[{RUTA}] Este arreglo ya estaba aplicado, no se hizo nada.")
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
    print("   git commit -m \"Fix: usar cursor separado para la consulta del anticipo\"")
    print("   git push")


if __name__ == "__main__":
    main()
