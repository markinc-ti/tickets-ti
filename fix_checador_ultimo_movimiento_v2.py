# -*- coding: utf-8 -*-
"""
Cambia "último movimiento" en el Checador de precio de una sola fecha
global a una fecha por sucursal (almacén) — usa DOCTOS_PV.ALMACEN_ID
(que sí existe en el encabezado, aunque no en el detalle) para saber de
qué almacén salió cada venta.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_checador_ultimo_movimiento_v2.py
"""
import sys

RUTA_BACKEND = 'backend/microsip.py'
RUTA_FRONTEND = 'frontend/index.html'

VIEJO_BACKEND = (
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
)

# Este bloque viejo se ELIMINA de su posición original (justo antes del
# "return {") porque la nueva versión de la consulta se inserta más
# arriba, antes de armar la lista de almacenes (ver NUEVO_ALMACENES_BACKEND
# más abajo) — de lo contrario quedaría duplicado.
NUEVO_BACKEND = ''

VIEJO_ALMACENES_BACKEND = (
    '        nombres_almacen = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}\n'
    '\n'
    '    almacenes = []\n'
    '    for almacen_id in almacen_ids:\n'
    '        existencia = capas_por_almacen.get(almacen_id, {}).get("existencia", 0.0)\n'
    '        comprometido = comprometido_por_almacen.get(almacen_id, 0.0)\n'
    '        # No mostramos almacenes donde no hay ni existencia ni comprometido\n'
    '        # (evita llenar la lista con decenas de almacenes internos vacíos).\n'
    '        if existencia == 0 and comprometido == 0:\n'
    '            continue\n'
    '        almacenes.append({\n'
    '            "almacen_id": almacen_id,\n'
    '            "almacen_nombre": nombres_almacen.get(almacen_id, f"Almacén {almacen_id}"),\n'
    '            "existencia": existencia,\n'
    '            "comprometido": comprometido,\n'
    '            "disponible": existencia - comprometido,\n'
    '        })\n'
)

NUEVO_ALMACENES_BACKEND = (
    '        nombres_almacen = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}\n'
    '\n'
    '    # Fecha del último movimiento (última vez que se vendió este\n'
    '    # artículo por Punto de Venta) POR ALMACÉN — DOCTOS_PV_DET no trae\n'
    '    # ALMACEN_ID propio, pero el encabezado DOCTOS_PV sí lo tiene (cada\n'
    '    # venta completa sale de un solo almacén). Sin importar el estatus\n'
    '    # del documento.\n'
    '    cur.execute("""\n'
    '        SELECT p.ALMACEN_ID, MAX(p.FECHA)\n'
    '        FROM DOCTOS_PV_DET d\n'
    '        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n'
    '        WHERE d.ARTICULO_ID = ?\n'
    '        GROUP BY p.ALMACEN_ID\n'
    '    """, (articulo_id,))\n'
    '    ultimo_movimiento_por_almacen = {aid: str(fecha) for aid, fecha in cur.fetchall() if fecha}\n'
    '    ultimo_movimiento = max(ultimo_movimiento_por_almacen.values()) if ultimo_movimiento_por_almacen else None\n'
    '\n'
    '    almacenes = []\n'
    '    for almacen_id in almacen_ids:\n'
    '        existencia = capas_por_almacen.get(almacen_id, {}).get("existencia", 0.0)\n'
    '        comprometido = comprometido_por_almacen.get(almacen_id, 0.0)\n'
    '        # No mostramos almacenes donde no hay ni existencia ni comprometido\n'
    '        # (evita llenar la lista con decenas de almacenes internos vacíos).\n'
    '        if existencia == 0 and comprometido == 0:\n'
    '            continue\n'
    '        almacenes.append({\n'
    '            "almacen_id": almacen_id,\n'
    '            "almacen_nombre": nombres_almacen.get(almacen_id, f"Almacén {almacen_id}"),\n'
    '            "existencia": existencia,\n'
    '            "comprometido": comprometido,\n'
    '            "disponible": existencia - comprometido,\n'
    '            "ultimo_movimiento": ultimo_movimiento_por_almacen.get(almacen_id),\n'
    '        })\n'
)

VIEJO_FRONTEND = (
    '      <p style="font-size:13px; color:var(--muted);">\n'
    '        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style="color:var(--trace);">${fmt(datos.disponible_total)} disponibles</b>\n'
    "        ${datos.ultimo_movimiento ? ` — último movimiento: ${new Date(datos.ultimo_movimiento).toLocaleDateString('es-MX')}` : ' — sin movimiento registrado'}\n"
    '      </p>\n'
    '      <table class="users" style="margin-top:10px;">\n'
    '        <thead><tr><th>Almacén</th><th>Existencia</th><th>Comprometido</th><th>Disponible</th></tr></thead>\n'
    '        <tbody>\n'
    '          ${datos.almacenes.map(a => `\n'
    '            <tr>\n'
    '              <td>${escapeHtml(a.almacen_nombre)}</td>\n'
    '              <td>${fmt(a.existencia)}</td>\n'
    '              <td>${fmt(a.comprometido)}</td>\n'
    '              <td><b style="color:${a.disponible > 0 ? \'var(--trace)\' : \'var(--copper)\'};">${fmt(a.disponible)}</b></td>\n'
    '            </tr>\n'
    "          `).join('') || `<tr><td colspan=\"4\" class=\"empty-col\">— sin existencia registrada en ningún almacén —</td></tr>`}\n"
    '        </tbody>\n'
    '      </table>\n'
)

NUEVO_FRONTEND = (
    '      <p style="font-size:13px; color:var(--muted);">\n'
    '        Total: ${fmt(datos.existencia_total)} en existencia — ${fmt(datos.comprometido_total)} comprometidas — <b style="color:var(--trace);">${fmt(datos.disponible_total)} disponibles</b>\n'
    '      </p>\n'
    '      <table class="users" style="margin-top:10px;">\n'
    '        <thead><tr><th>Almacén</th><th>Existencia</th><th>Comprometido</th><th>Disponible</th><th>Último movimiento</th></tr></thead>\n'
    '        <tbody>\n'
    '          ${datos.almacenes.map(a => `\n'
    '            <tr>\n'
    '              <td>${escapeHtml(a.almacen_nombre)}</td>\n'
    '              <td>${fmt(a.existencia)}</td>\n'
    '              <td>${fmt(a.comprometido)}</td>\n'
    '              <td><b style="color:${a.disponible > 0 ? \'var(--trace)\' : \'var(--copper)\'};">${fmt(a.disponible)}</b></td>\n'
    "              <td>${a.ultimo_movimiento ? new Date(a.ultimo_movimiento).toLocaleDateString('es-MX') : '—'}</td>\n"
    '            </tr>\n'
    "          `).join('') || `<tr><td colspan=\"5\" class=\"empty-col\">— sin existencia registrada en ningún almacén —</td></tr>`}\n"
    '        </tbody>\n'
    '      </table>\n'
)


def aplicar(ruta, cambios):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        return False

    ok = True
    total = 0
    for viejo, nuevo in cambios:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            total += 1
        elif nuevo in contenido:
            total += 1  # ya aplicado antes
        else:
            print(f"[{ruta}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
            ok = False

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[{ruta}] {total}/{len(cambios)} cambio(s) aplicado(s).")
    return ok


def main():
    ok1 = aplicar(RUTA_BACKEND, [
        (VIEJO_BACKEND, NUEVO_BACKEND),
        (VIEJO_ALMACENES_BACKEND, NUEVO_ALMACENES_BACKEND),
    ])
    ok2 = aplicar(RUTA_FRONTEND, [
        (VIEJO_FRONTEND, NUEVO_FRONTEND),
    ])

    if not (ok1 and ok2):
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/microsip.py frontend/index.html")
    print("   git commit -m \"Checador de precio: ultimo movimiento por sucursal\"")
    print("   git push")


if __name__ == "__main__":
    main()
