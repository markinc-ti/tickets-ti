# -*- coding: utf-8 -*-
"""
Corrige el botón "token" (junto al checkbox de Monitoreo en Administrar
-> Accesos): el nombre del empleado se pasaba con JSON.stringify (que usa
comillas dobles) dentro de un atributo onclick que TAMBIÉN usa comillas
dobles -- se chocaban y el navegador cortaba el atributo a la mitad, por
eso el clic no hacía nada.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_boton_token_monitoreo.py
"""
import sys

RUTA = 'frontend/index.html'

VIEJO = (
    '''              ${u.monitoreo_activo ? `<button type="button" style="font-size:9px; padding:2px 4px; margin-top:2px;" onclick="generarTokenMonitoreoUI(${u.id}, ${JSON.stringify(u.nombre_completo)})">token</button>` : ''}'''
)

NUEVO = (
    '''              ${u.monitoreo_activo ? `<button type="button" style="font-size:9px; padding:2px 4px; margin-top:2px;" onclick="generarTokenMonitoreoUI(${u.id}, ${JSON.stringify(u.nombre_completo).replace(/"/g, '&quot;')})">token</button>` : ''}'''
)


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO -- asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
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
    print("   git add frontend/index.html")
    print('   git commit -m "Fix: boton de token de monitoreo se rompia por comillas anidadas"')
    print("   git push")


if __name__ == "__main__":
    main()
