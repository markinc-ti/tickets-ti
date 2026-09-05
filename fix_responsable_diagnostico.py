# -*- coding: utf-8 -*-
"""
En Reparaciones → Diagnóstico, el campo "Responsable del diagnóstico"
salía vacío (solo "Sin asignar") por dos motivos combinados:

1. La lista de técnicos (TECNICOS) solo se cargaba al entrar por Tickets
   -- si un técnico entraba directo a Reparaciones sin pasar por ahí, la
   lista seguía vacía. Ahora también se carga al entrar a Reparaciones.

2. Aunque estuviera la lista, había que elegir manualmente el nombre.
   Ahora, si nadie ha asignado un responsable todavía, el dropdown
   preselecciona automáticamente al usuario que tiene la sesión abierta
   (si su rol es técnico o admin, que son los únicos que aparecen en esa
   lista) -- se puede cambiar manualmente si hace falta, pero ya no hay
   que hacerlo para el caso normal de "yo mismo estoy haciendo esto".

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_responsable_diagnostico.py
"""
import sys

RUTA = 'frontend/index.html'

CAMBIOS = [
    [
        "  document.getElementById('btnVolverDesdeReparaciones').style.display = esAlmacen ? 'none' : 'inline-block';\n"
        "  SUCURSALES_REPARACION_CACHE = await api('/api/reparaciones/sucursales');\n"
        "  await cambiarReparacionesTab('lista');\n"
        "}\n",

        "  document.getElementById('btnVolverDesdeReparaciones').style.display = esAlmacen ? 'none' : 'inline-block';\n"
        "  SUCURSALES_REPARACION_CACHE = await api('/api/reparaciones/sucursales');\n"
        "  // Se vuelve a cargar aquí también (no solo al entrar por Tickets) para\n"
        "  // que el dropdown de \"Responsable del diagnóstico\" tenga nombres aunque\n"
        "  // el técnico haya entrado directo a Reparaciones.\n"
        "  if (SESION.usuario.rol !== 'usuario') {\n"
        "    TECNICOS = await api('/api/usuarios/tecnicos');\n"
        "  }\n"
        "  await cambiarReparacionesTab('lista');\n"
        "}\n",
    ],
    [
        '      <div class="field"><label>Responsable del diagnóstico</label>\n'
        '        <select id="ed_responsable" ${diagnosticoBloqueado ? \'disabled\' : \'\'}>\n'
        '          <option value="">Sin asignar</option>\n'
        "          ${TECNICOS.map(t => `<option value=\"${t.id}\" ${r.responsable_diagnostico_id===t.id?'selected':''}>${escapeHtml(t.nombre_completo)}</option>`).join('')}\n"
        '        </select>\n'
        '      </div>\n',

        '      <div class="field"><label>Responsable del diagnóstico</label>\n'
        '        <select id="ed_responsable" ${diagnosticoBloqueado ? \'disabled\' : \'\'}>\n'
        '          <option value="">Sin asignar</option>\n'
        "          ${TECNICOS.map(t => `<option value=\"${t.id}\" ${(r.responsable_diagnostico_id ?? (['tecnico','admin'].includes(SESION.usuario.rol) ? SESION.usuario.id : null))===t.id?'selected':''}>${escapeHtml(t.nombre_completo)}</option>`).join('')}\n"
        '        </select>\n'
        '      </div>\n',
    ],
]


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    cambios = 0
    hubo_error = False
    for viejo, nuevo in CAMBIOS:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print(f"[{RUTA}] No se encontró el bloque esperado para uno de los cambios. El archivo pudo haber cambiado desde la última vez.")
            hubo_error = True

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] {cambios}/{len(CAMBIOS)} cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print("   git commit -m \"Preseleccionar responsable del diagnóstico con el usuario logueado\"")
    print("   git push")


if __name__ == "__main__":
    main()
