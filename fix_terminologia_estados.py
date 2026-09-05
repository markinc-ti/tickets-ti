# -*- coding: utf-8 -*-
"""
Agrega los 12 estatus de Reparaciones ("Con proveedor", "Esperando
refacción", etc.) al catálogo de "Terminología" ya existente, para que
cada empresa pueda renombrarlos igual que ya hace con roles/módulos/
"Sucursal".

Backend (db.py): se agregan las 12 claves nuevas a TERMINOS_EDITABLES,
grupo "Estados de reparación" (aparecen solas en el panel de
Administrar → Terminología, no hay que tocar esa pantalla).

Frontend (index.html): el objeto NOMBRES_ESTADO_REPARACION (usado en la
lista, el detalle y el dropdown de cambio de estado de Reparaciones) se
actualiza con el término personalizado si existe — mismo patrón que ya
usan los nombres de rol.

(Nota: NO se tocó la tarjeta del Dashboard general porque ahí varios
módulos comparten algunas claves de estado, ej. "esperando_autorizacion"
lo usan también Ciclos de compra — cambiarlo ahí de raíz podría afectar
por accidente el nombre en otro módulo.)

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_terminologia_estados.py
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '    # Campos comunes\n'
            '    "campo.sucursal": {"grupo": "Campos", "default": "Sucursal"},\n'
            '}',

            '    # Campos comunes\n'
            '    "campo.sucursal": {"grupo": "Campos", "default": "Sucursal"},\n'
            '    # Estados de reparación\n'
            '    "estado_reparacion.nueva": {"grupo": "Estados de reparación", "default": "Reparación nueva en camino"},\n'
            '    "estado_reparacion.en_diagnostico": {"grupo": "Estados de reparación", "default": "Recibido en diagnóstico"},\n'
            '    "estado_reparacion.esperando_autorizacion": {"grupo": "Estados de reparación", "default": "Esperando autorización"},\n'
            '    "estado_reparacion.en_reparacion": {"grupo": "Estados de reparación", "default": "En reparación"},\n'
            '    "estado_reparacion.con_proveedor": {"grupo": "Estados de reparación", "default": "Con proveedor"},\n'
            '    "estado_reparacion.esperando_refaccion": {"grupo": "Estados de reparación", "default": "Esperando refacción"},\n'
            '    "estado_reparacion.control_calidad": {"grupo": "Estados de reparación", "default": "Control de calidad"},\n'
            '    "estado_reparacion.envio_sucursal": {"grupo": "Estados de reparación", "default": "Envío a sucursal"},\n'
            '    "estado_reparacion.en_traslado": {"grupo": "Estados de reparación", "default": "En traslado"},\n'
            '    "estado_reparacion.listo_entrega": {"grupo": "Estados de reparación", "default": "Listo para entrega"},\n'
            '    "estado_reparacion.entregado": {"grupo": "Estados de reparación", "default": "Entregado"},\n'
            '    "estado_reparacion.cancelado": {"grupo": "Estados de reparación", "default": "Cancelado"},\n'
            '}'
        ],
    ],
    'frontend/index.html': [
        [
            '  const BOTONES_MODULO = {\n'
            "    btnTickets: 'modulo.tickets', btnReparaciones: 'modulo.reparaciones',\n"
            "    btnEntregas: 'modulo.entregas', btnChecadorPrecio: 'modulo.checador_precio',\n"
            "    btnRH: 'modulo.rh', btnEquipos: 'modulo.equipos', btnCompras: 'modulo.compras',\n"
            '  };\n'
            '  for (const [idBoton, clave] of Object.entries(BOTONES_MODULO)) {\n'
            '    const boton = document.getElementById(idBoton);\n'
            '    const valor = META.terminos[clave];\n'
            '    if (boton && valor && boton.lastChild && boton.lastChild.nodeType === Node.TEXT_NODE) {\n'
            '      boton.lastChild.textContent = valor;\n'
            '    }\n'
            '  }\n'
            '}',

            '  const BOTONES_MODULO = {\n'
            "    btnTickets: 'modulo.tickets', btnReparaciones: 'modulo.reparaciones',\n"
            "    btnEntregas: 'modulo.entregas', btnChecadorPrecio: 'modulo.checador_precio',\n"
            "    btnRH: 'modulo.rh', btnEquipos: 'modulo.equipos', btnCompras: 'modulo.compras',\n"
            '  };\n'
            '  for (const [idBoton, clave] of Object.entries(BOTONES_MODULO)) {\n'
            '    const boton = document.getElementById(idBoton);\n'
            '    const valor = META.terminos[clave];\n'
            '    if (boton && valor && boton.lastChild && boton.lastChild.nodeType === Node.TEXT_NODE) {\n'
            '      boton.lastChild.textContent = valor;\n'
            '    }\n'
            '  }\n'
            '\n'
            '  // Nombres de estado de Reparaciones (lista, detalle, dropdown de\n'
            '  // cambio de estado) — mismo patrón que NOMBRES_ROL: se muta en sitio.\n'
            '  Object.keys(NOMBRES_ESTADO_REPARACION).forEach(estado => {\n'
            '    NOMBRES_ESTADO_REPARACION[estado] = t(`estado_reparacion.${estado}`, NOMBRES_ESTADO_REPARACION[estado]);\n'
            '  });\n'
            '}'
        ],
    ],
}


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False
    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print(f"[{ruta}] No se encontró el bloque esperado para uno de los cambios. El archivo pudo haber cambiado desde la última vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/db.py frontend/index.html")
    print("   git commit -m \"Estados de reparación editables en Terminología\"")
    print("   git push")


if __name__ == "__main__":
    main()
