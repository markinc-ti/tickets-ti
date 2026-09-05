# -*- coding: utf-8 -*-
"""
Corrige un caso raro que fix_anticipo_v2.py no contemplaba: si una
sucursal tiene un anticipo registrado ese periodo pero CERO ventas
cobradas (con forma de pago) ese mismo periodo, el anticipo se estaba
restando de un total que nunca existió, mostrando un "Total" negativo
sin sentido (ej. "$-1,120.69" con ninguna otra venta detrás).

A partir de ahora, el anticipo solo se descuenta de sucursales que SÍ
tienen ventas reales cobradas ese periodo. Si una sucursal solo tiene el
anticipo y nada más cobrado, no se fabrica una fila con total negativo —
simplemente no aparece ese periodo (igual que si no hubiera tenido
ventas).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_anticipo_v3.py
"""
import sys

VIEJO = '''    total_anticipo_general = 0.0
    for sucursal, anticipo in anticipos_por_sucursal.items():
        entrada = por_sucursal.setdefault(sucursal, {"sucursal": sucursal, "formas_cobro": {}, "total": 0.0, "anticipo": 0.0})
        entrada["anticipo"] = anticipo
        entrada["total"] -= anticipo
        total_general -= anticipo
        total_anticipo_general += anticipo

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}'''

NUEVO = '''    total_anticipo_general = 0.0
    for sucursal, anticipo in anticipos_por_sucursal.items():
        entrada = por_sucursal.get(sucursal)
        if entrada is None:
            # No hay ventas cobradas (forma de cobro) en esta sucursal ese
            # periodo — no se fabrica una fila solo con el anticipo, para
            # no mostrar un total negativo sin ventas reales detrás.
            continue
        entrada["anticipo"] = anticipo
        entrada["total"] = max(0.0, entrada["total"] - anticipo)
        total_anticipo_general += anticipo

    total_general = sum(e["total"] for e in por_sucursal.values())

    resultado = sorted(por_sucursal.values(), key=lambda r: -r["total"])
    return {"por_sucursal": resultado, "total_general": total_general, "total_anticipo": total_anticipo_general}'''

RUTA = 'backend/microsip.py'


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
    print("   git commit -m \"Fix: no descontar anticipo de sucursales sin ventas cobradas ese periodo\"")
    print("   git push")


if __name__ == "__main__":
    main()
