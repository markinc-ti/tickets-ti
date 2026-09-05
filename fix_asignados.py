# -*- coding: utf-8 -*-
"""
Corrige el bug por el cual las tareas de proyecto con persona(s) asignada(s)
se mostraban como "SIN ASIGNAR" (la asignacion en si NUNCA se perdio de la
base de datos -- era solo un error al leer los datos para mostrarlos).

Uso: colocalo en la carpeta del repo (junto a backend/) y corre:
    py fix_asignados.py
"""
import sys

VIEJO = '        for tarea_id, usuario_id, nombre in cur.fetchall():\n            asignados_por_tarea.setdefault(tarea_id, []).append({"id": usuario_id, "nombre_completo": nombre})'
NUEVO = '        for fila in cur.fetchall():\n            asignados_por_tarea.setdefault(fila["tarea_id"], []).append(\n                {"id": fila["id"], "nombre_completo": fila["nombre_completo"]}\n            )'


def main():
    ruta = "backend/db.py"
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
    print("   git add backend/db.py")
    print('   git commit -m "Fix: tareas de proyecto se mostraban como SIN ASIGNAR por error al leer la asignacion"')
    print("   git push")


if __name__ == "__main__":
    main()
