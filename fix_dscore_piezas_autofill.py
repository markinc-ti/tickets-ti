#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DS Core: al importar un pedido, prellena el odontograma (piezas/dientes)
con lo que el doctor ya especifico en DS Core, en vez de dejarlo vacio.

Por que: ya funciona la conexion e importacion de pedidos de DS Core de
punta a punta, pero el trabajo se creaba siempre con el odontograma vacio
(costo total $0.00) y habia que llenarlo a mano despues. David pidio que,
si el pedido ya trae el detalle (corona, cuantos dientes, material, tono),
se use eso solo para que el estudiante vea de una vez cuanto va a pagar.

Se confirmo con un pedido real de DS Core (no solo documentacion) que los
pedidos tipo "restorationSet" traen ese detalle estructurado por diente
(items[].detail.restorationSet.restorations[], uno por diente, con type,
material, shade, toothPositionsFdi). Los pedidos "customOrder" (pedido
personalizado) NO traen esa informacion -- para esos, y para cualquier
forma que no se reconozca, el odontograma se sigue completando a mano
como hasta ahora (no truena nada, simplemente no hay nada que prellenar).

Mapeos confirmados contra datos reales: CROWN -> corona,
ZIRCONIUM_OXID -> zirconia (justo estos dos son los que activan el precio
fijo BUAP de $700 que ya existia). Los demas tipos/materiales de DS Core
(puente, carilla, implante, disilicato, etc.) son la mejor suposicion --
si algo no se reconoce, se guarda el texto de DS Core tal cual (legible)
en vez de perderse, y el tipo de trabajo cae en "otro" para no romper el
campo validado de tickets-ti.

Que cambia:
- backend/dscore.py: nueva funcion extraer_piezas_de_order() (no toca nada existente)
- backend/app.py: api_importar_pedido_dscore() ahora arma las piezas con
  esa funcion (antes siempre mandaba una lista vacia) y aplica el precio
  fijo BUAP igual que cuando se agrega una pieza a mano.
"""
import sys

ARCHIVOS = {
    'backend/dscore.py': [
        [
            'def obtener_orders_crudo(base_host, access_token, page_size=5):\n    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,\n    sin interpretar nada, para poder ver con datos reales (no documentacion)\n    como se llama de verdad el campo del codigo legible del pedido y que\n    forma tiene cada order. Se usa una sola vez desde el endpoint de debug\n    para ajustar buscar_order_por_codigo() con la forma real de los datos."""\n    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})\n',
            'def obtener_orders_crudo(base_host, access_token, page_size=5):\n    """SOLO PARA DIAGNOSTICO -- trae la respuesta tal cual de /v1beta/orders,\n    sin interpretar nada, para poder ver con datos reales (no documentacion)\n    como se llama de verdad el campo del codigo legible del pedido y que\n    forma tiene cada order. Se usa una sola vez desde el endpoint de debug\n    para ajustar buscar_order_por_codigo() con la forma real de los datos."""\n    return _get(base_host, access_token, "/v1beta/orders", params={"pageSize": page_size})\n\n\n# Mapeos confirmados contra un pedido real de DS Core (2AFABPE9: 3 coronas\n# de oxido de zirconia, tono A2, para los dientes FDI 18/16/38). Los que no\n# se han visto en un pedido real todavia son la mejor suposicion -- si no\n# coinciden, el texto de DS Core se usa tal cual (legible) en vez de\n# perderse, y el tipo de trabajo cae en "otro" para no romper el campo\n# validado de tickets-ti.\nTIPOS_TRABAJO_DSCORE = {\n    "CROWN": "corona",  # confirmado con pedido real\n    "BRIDGE": "puente",\n    "INLAY": "incrustacion",\n    "ONLAY": "incrustacion",\n    "VENEER": "carilla",\n    "IMPLANT": "implante",\n}\n\nMATERIALES_DSCORE = {\n    "ZIRCONIUM_OXID": "zirconia",  # confirmado con pedido real\n    "LITHIUM_DISILICATE": "disilicato",\n}\n\nPRODUCTION_OPTIONS_DSCORE = {\n    "DESIGN_ONLY": "Diseño",  # confirmado con pedido real\n    "MILLING": "Fresado",  # confirmado con pedido real (como productionUnit)\n    "DESIGN_AND_MILLING": "Diseño y fresado",\n    "DESIGN_AND_PRINTING": "Diseño e impresión",\n    "PRINTING": "Impresión",\n}\n\n\ndef _texto_legible_dscore(valor):\n    """Convierte un valor tipo ENUM_DE_DS_CORE que no reconocemos en texto\n    legible, para no perder la información aunque no tengamos el mapeo\n    exacto todavía: \'GLASS_CERAMIC\' -> \'Glass ceramic\'."""\n    if not valor:\n        return None\n    texto = str(valor).replace("_", " ").strip()\n    if not texto:\n        return None\n    return texto[:1].upper() + texto[1:].lower()\n\n\ndef extraer_piezas_de_order(order):\n    """A partir de un pedido de DS Core, arma la lista de piezas (diente +\n    tipo de trabajo + material + tono) que se le puede pasar directo a\n    db.crear_trabajo_laboratorio(..., piezas=...), para que el odontograma\n    del trabajo quede prellenado con lo que el doctor ya especificó en DS\n    Core, en vez de quedar vacío ($0.00) como hasta ahora.\n\n    Solo los pedidos tipo "restorationSet" traen el detalle estructurado\n    por diente (items[].detail.restorationSet.restorations[] -- confirmado\n    con un pedido real). Los pedidos "customOrder" (pedido personalizado)\n    no traen esa información, así que para esos -- o cualquier forma que no\n    reconozcamos -- se regresa una lista vacía y el odontograma se completa\n    a mano, igual que antes. No es un error, es el comportamiento esperado."""\n    piezas = []\n    for item in (order.get("items") or []):\n        restauraciones = ((item.get("detail") or {}).get("restorationSet") or {}).get("restorations") or []\n        for r in restauraciones:\n            tipo_dscore = (r.get("type") or "").strip().upper()\n            tipo_trabajo = TIPOS_TRABAJO_DSCORE.get(tipo_dscore, "otro")\n            material_dscore = (r.get("material") or "").strip().upper()\n            material = MATERIALES_DSCORE.get(material_dscore) or _texto_legible_dscore(material_dscore)\n            color = r.get("shade") or None\n            notas_partes = []\n            if tipo_dscore and tipo_dscore not in TIPOS_TRABAJO_DSCORE:\n                notas_partes.append(f"Tipo en DS Core: {_texto_legible_dscore(tipo_dscore)}")\n            prod_opt = (r.get("productionOptions") or "").strip().upper()\n            if prod_opt:\n                notas_partes.append(PRODUCTION_OPTIONS_DSCORE.get(prod_opt) or _texto_legible_dscore(prod_opt))\n            prod_unit = (r.get("productionUnit") or "").strip().upper()\n            if prod_unit:\n                notas_partes.append(PRODUCTION_OPTIONS_DSCORE.get(prod_unit) or _texto_legible_dscore(prod_unit))\n            notas = " · ".join(p for p in notas_partes if p) or None\n            dientes = r.get("toothPositionsFdi") or r.get("toothPositions") or []\n            for diente in dientes:\n                piezas.append({\n                    "diente": str(diente),\n                    "tipo_trabajo": tipo_trabajo,\n                    "material": material,\n                    "color": color,\n                    "notas": notas,\n                })\n    return piezas\n',
        ],
    ],
    'backend/app.py': [
        [
            '    registro = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])\n    if not registro:\n        raise HTTPException(status_code=404, detail="Tu cuenta no se encontró")\n    trabajo = db.crear_trabajo_laboratorio(\n        usuario["empresa_id"], sucursal_recogida["id"], "estudiante", registro["nombre_completo"],\n        "BUAP", registro.get("telefono_whatsapp") or "", paciente_nombre, None,\n        f"Importado desde DS Core (pedido {order.get(\'readableId\') or codigo}).", None, usuario["id"],\n        codigo, payload.requiere_factura, [],\n    )\n    db.marcar_dscore_order_en_trabajo(usuario["empresa_id"], trabajo["id"], order["name"])\n    db.agregar_actualizacion_laboratorio(\n        trabajo["id"], usuario["id"],\n        f"{registro[\'nombre_completo\']} importó este trabajo desde DS Core (código {codigo}). Falta completar el odontograma y registrar el pago.",\n    )\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo["id"])',
            '    registro = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])\n    if not registro:\n        raise HTTPException(status_code=404, detail="Tu cuenta no se encontró")\n    # Si el pedido trae detalle de restauración por diente (tipo, material,\n    # tono), se arma el odontograma solo -- así el estudiante ve de una vez\n    # cuánto va a pagar en vez de ver el trabajo con costo $0.00.\n    piezas_extraidas = dscore.extraer_piezas_de_order(order)\n    for pieza in piezas_extraidas:\n        precio_fijo = db.precio_fijo_laboratorio("BUAP", pieza["tipo_trabajo"], pieza.get("material"))\n        if precio_fijo is not None:\n            pieza["costo"] = precio_fijo\n    trabajo = db.crear_trabajo_laboratorio(\n        usuario["empresa_id"], sucursal_recogida["id"], "estudiante", registro["nombre_completo"],\n        "BUAP", registro.get("telefono_whatsapp") or "", paciente_nombre, None,\n        f"Importado desde DS Core (pedido {order.get(\'readableId\') or codigo}).", None, usuario["id"],\n        codigo, payload.requiere_factura, piezas_extraidas,\n    )\n    db.marcar_dscore_order_en_trabajo(usuario["empresa_id"], trabajo["id"], order["name"])\n    if piezas_extraidas:\n        mensaje_piezas = f"Se detectaron {len(piezas_extraidas)} pieza(s) en el pedido de DS Core y se agregaron solas al odontograma. Falta registrar el pago."\n    else:\n        mensaje_piezas = "Falta completar el odontograma y registrar el pago."\n    db.agregar_actualizacion_laboratorio(\n        trabajo["id"], usuario["id"],\n        f"{registro[\'nombre_completo\']} importó este trabajo desde DS Core (código {codigo}). {mensaje_piezas}",\n    )\n    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo["id"])',
        ],
    ],
}


def main():
    cambios_totales = 0
    for ruta, hunks in ARCHIVOS.items():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
        except FileNotFoundError:
            print(f"ERROR: no se encontro {ruta} -- corre este script desde la raiz del repo tickets-ti.")
            sys.exit(1)

        original = contenido
        cambios_archivo = 0
        for viejo, nuevo in hunks:
            if nuevo in contenido:
                continue  # ya aplicado antes -- idempotente
            if viejo not in contenido:
                print(f"ERROR: no se encontro el texto esperado en {ruta}.")
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
                print("--- fragmento esperado ---")
                print(viejo[:300])
                sys.exit(1)
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios_archivo += 1

        if contenido != original:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: {ruta} -- {cambios_archivo} cambio(s) aplicado(s).")
            cambios_totales += cambios_archivo
        else:
            print(f"(sin cambios) {ruta} -- ya estaba aplicado.")

    if cambios_totales == 0:
        print()
        print("No habia nada nuevo que aplicar (el parche ya estaba puesto).")
    else:
        print()
        print(f"{cambios_totales} cambio(s) aplicado(s) en total.")

    print()
    print("Ahora corre esto para subirlo:")
    print()
    print("    git add backend/dscore.py backend/app.py")
    print('    git commit -m "DS Core: prellenar el odontograma al importar un pedido con detalle de restauracion"')
    print("    git push")


if __name__ == "__main__":
    main()
