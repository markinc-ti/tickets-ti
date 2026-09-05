# -*- coding: utf-8 -*-
"""
Agrega la fecha del último movimiento (última vez que se vendió ese
artículo por Punto de Venta, en cualquier sucursal) junto a "Disponible"
en el Checador de precio.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_checador_ultimo_movimiento.py
"""
import sys

RUTA_BACKEND = 'backend/microsip.py'
RUTA_FRONTEND = 'frontend/index.html'

VIEJO_BACKEND = (
    '    return {\n'
    '        "articulo_id": articulo_id,\n'
    '        "nombre": nombre,\n'
    '        "claves": claves,\n'
    '        "precio_sin_impuesto": precio_sin_impuesto,\n'
    '        "precio_con_impuesto": precio_con_impuesto,\n'
    '        "existencia_total": total_existencia,\n'
    '        "comprometido_total": sum(comprometido_por_almacen.values()),\n'
    '        "disponible_total": total_existencia - sum(comprometido_por_almacen.values()),\n'
    '        "almacenes": almacenes,\n'
    '        "capas_detalle": sorted(capas_detalle, key=lambda c: -c["capa_id"]),\n'
    '    }'
)

NUEVO_BACKEND = (
    '    # Fecha del último movimiento (última vez que se vendió este\n'
    '    # artículo por Punto de Venta, en cualquier sucursal, sin importar el\n'
    '    # estatus del documento).\n'
    '    cur.execute("""\n'
    '        SELECT MAX(p.FECHA)\n'
    '        FROM DOCTOS_PV_DET d\n'
    '        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n'
    '        WHERE d.ARTICULO_ID = ?\n'
    '    """, (articulo_id,))\n'
    '    fila_ultimo_mov = cur.fetchone()\n'
    '    ultimo_movimiento = str(fila_ultimo_mov[0]) if fila_ultimo_mov and fila_ultimo_mov[0] else None\n'
    '\n'
    '    return {\n'
    '        "articulo_id": articulo_id,\n'
    '        "nombre": nombre,\n'
    '        "claves": claves,\n'
    '        "precio_sin_impuesto": precio_sin_impuesto,\n'
    '        "precio_con_impuesto": precio_con_impuesto,\n'
    '        "existencia_total": total_existencia,\n'
    '        "comprometido_total": sum(comprometido_por_almacen.values()),\n'
    '        "disponible_total": total_existencia - sum(comprometido_por_almacen.values()),\n'
    '        "ultimo_movimiento": ultimo_movimiento,\n'
    '        "almacenes": almacenes,\n'
    '        "capas_detalle": sorted(capas_detalle, key=lambda c: -c["capa_id"]),\n'
    '    }'
)

VIEJO_FRONTEND = (
    '      <p style="font-size:13px; color:var(--muted);">\n'
    '        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style="color:var(--trace);">${fmt(datos.disponible_total)} disponibles</b>\n'
    '      </p>\n'
)

NUEVO_FRONTEND = (
    '      <p style="font-size:13px; color:var(--muted);">\n'
    '        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style="color:var(--trace);">${fmt(datos.disponible_total)} disponibles</b>\n'
    '        ${datos.ultimo_movimiento ? ` — último movimiento: ${new Date(datos.ultimo_movimiento).toLocaleDateString(\'es-MX\')}` : \' — sin movimiento registrado\'}\n'
    '      </p>\n'
)


def aplicar(ruta, viejo, nuevo):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        return False

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
    elif nuevo in contenido:
        print(f"[{ruta}] Ya estaba aplicado, no se hizo nada.")
        return True
    else:
        print(f"[{ruta}] No se encontró el bloque esperado. El archivo pudo haber cambiado desde la última vez.")
        print("Avísale a Claude sin correr git add/commit todavía.")
        return False

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[{ruta}] Cambio aplicado.")
    return True


def main():
    ok1 = aplicar(RUTA_BACKEND, VIEJO_BACKEND, NUEVO_BACKEND)
    ok2 = aplicar(RUTA_FRONTEND, VIEJO_FRONTEND, NUEVO_FRONTEND)

    if not (ok1 and ok2):
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/microsip.py frontend/index.html")
    print("   git commit -m \"Checador de precio: mostrar fecha del último movimiento\"")
    print("   git push")


if __name__ == "__main__":
    main()
