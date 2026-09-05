# -*- coding: utf-8 -*-
"""
Corrige por qué activar el checkbox de "Monitoreo" no hacía nada: el
usuario en sesión se arma con datos frescos de la base vía
db.obtener_permisos_usuario() — pero esa consulta nunca incluía la
columna monitoreo_activo, así que /api/meta siempre veía False sin
importar lo que dijera el checkbox en Administrar.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_monitoreo_permisos.py
"""
import sys

RUTA = 'backend/db.py'

VIEJO = (
    '        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n'
    '                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_entregas, acceso_checador_precio,\n'
    '                  acceso_marketing\n'
    '           FROM users WHERE id = %s""",\n'
)

NUEVO = (
    '        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,\n'
    '                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_entregas, acceso_checador_precio,\n'
    '                  acceso_marketing, monitoreo_activo\n'
    '           FROM users WHERE id = %s""",\n'
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
    print("   git add backend/db.py")
    print("   git commit -m \"Fix: monitoreo_activo faltaba en obtener_permisos_usuario\"")
    print("   git push")


if __name__ == "__main__":
    main()
