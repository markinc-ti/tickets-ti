# -*- coding: utf-8 -*-
"""
ACTA DE INVENTARIO: QUIEN ENTREGA ES EL ENCARGADO DE INVENTARIOS
En el PDF del acta de entrega de inventario, donde decia "Departamento de
Sistemas" / "Sistemas" ahora dice "Encargado de Inventarios" (texto, datos
generales, compromisos, inventarios periodicos y firma de quien entrega).
REQUIERE haber corrido antes fix_acta_inventario_pdf.py.
Toca: backend/acta_inventario.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_acta_encargado_inventarios.py
"""
import os
import sys

ARCHIVOS = {
 "backend/acta_inventario.py": [
  [
   "    s.append(_p('Acta de entrega de inventario físico', 'titulo'))\n    s.append(_p(f'Folio {folio}  ·  Entrega del almacén al encargado con {_fmt_pct(pct)} de exactitud y compromiso de mantenerla', 'sub'))\n    s.append(Spacer(1, 12))\n    s.append(_p(f'En la fecha indicada, el Departamento de Sistemas de <b>{empresa}</b> entrega al encargado del almacén el '\n                f'inventario físico, conciliado contra {sistema_largo}, con una exactitud del <b>{_fmt_pct(pct)}</b>. '\n                'Con su firma, el encargado recibe el inventario en estas condiciones y se compromete a mantenerlo así, con '\n                'inventarios físicos periódicos que lo verifiquen.'))\n",
   "    s.append(_p('Acta de entrega de inventario físico', 'titulo'))\n    s.append(_p(f'Folio {folio}  ·  Entrega del almacén al encargado con {_fmt_pct(pct)} de exactitud y compromiso de mantenerla', 'sub'))\n    s.append(Spacer(1, 12))\n    s.append(_p(f'En la fecha indicada, el Encargado de Inventarios de <b>{empresa}</b> entrega al encargado del almacén el '\n                f'inventario físico, conciliado contra {sistema_largo}, con una exactitud del <b>{_fmt_pct(pct)}</b>. '\n                'Con su firma, el encargado recibe el inventario en estas condiciones y se compromete a mantenerlo así, con '\n                'inventarios físicos periódicos que lo verifiquen.'))\n"
  ],
  [
   "        ['Sucursal / almacén', v('sucursal')],\n        ['Fecha del conteo físico', _fecha_larga(d.get('fecha_conteo')) if d.get('fecha_conteo') else ''],\n        ['Fecha de entrega', _fecha_larga(d.get('fecha_entrega')) if d.get('fecha_entrega') else ''],\n        ['Entrega', 'Departamento de Sistemas. Nombre: ' + v('entrega_nombre')],\n        ['Recibe (encargado)', 'Nombre: ' + v('recibe_nombre')],\n        ['Puesto del encargado', v('recibe_puesto')],\n        ['Sistema de inventario', sistema_nombre or 'Sistema de inventarios'],\n",
   "        ['Sucursal / almacén', v('sucursal')],\n        ['Fecha del conteo físico', _fecha_larga(d.get('fecha_conteo')) if d.get('fecha_conteo') else ''],\n        ['Fecha de entrega', _fecha_larga(d.get('fecha_entrega')) if d.get('fecha_entrega') else ''],\n        ['Entrega', 'Encargado de Inventarios. Nombre: ' + v('entrega_nombre')],\n        ['Recibe (encargado)', 'Nombre: ' + v('recibe_nombre')],\n        ['Puesto del encargado', v('recibe_puesto')],\n        ['Sistema de inventario', sistema_nombre or 'Sistema de inventarios'],\n"
  ],
  [
   "        f'Registrar en {sistema} toda entrada y salida de mercancía el mismo día en que ocurre.',\n        'No entregar ni recibir mercancía sin su documento (factura, remisión, traspaso o vale).',\n        'Registrar los traspasos entre almacenes y sucursales antes de mover la mercancía.',\n        'Reportar de inmediato a su jefe y a Sistemas cualquier faltante, sobrante, merma o producto dañado.',\n        'Mantener el almacén ordenado: cada artículo en su lugar, identificado y con su clave visible.',\n        'Permitir el acceso al almacén solo al personal autorizado.',\n        'Dar las facilidades y el tiempo necesarios para los inventarios físicos programados y sorpresa.',\n",
   "        f'Registrar en {sistema} toda entrada y salida de mercancía el mismo día en que ocurre.',\n        'No entregar ni recibir mercancía sin su documento (factura, remisión, traspaso o vale).',\n        'Registrar los traspasos entre almacenes y sucursales antes de mover la mercancía.',\n        'Reportar de inmediato a su jefe y al Encargado de Inventarios cualquier faltante, sobrante, merma o producto dañado.',\n        'Mantener el almacén ordenado: cada artículo en su lugar, identificado y con su clave visible.',\n        'Permitir el acceso al almacén solo al personal autorizado.',\n        'Dar las facilidades y el tiempo necesarios para los inventarios físicos programados y sorpresa.',\n"
  ],
  [
   "    s.append(_tabla([\n        ['Tipo de inventario', 'Frecuencia', 'Alcance'],\n        ['Conteo cíclico', 'Mensual', 'Una parte de los artículos cada vez (por línea o ubicación), empezando por los de mayor valor y movimiento.'],\n        ['Inventario sorpresa', 'Sin aviso previo', 'Una muestra de artículos elegida por Sistemas o Dirección.'],\n        ['Inventario general', 'Cada 6 meses', 'Todo el almacén.'],\n    ], [3.8 * cm, 3.0 * cm, AN - 6.8 * cm]))\n    s.append(Spacer(1, 6))\n    s.append(_p(f'Si un inventario resulta por debajo del {_fmt_pct(meta)}, el encargado y Sistemas revisan las causas, se '\n                f'ajusta {sistema} y se repite el conteo de esos artículos en un plazo máximo de 15 días.'))\n    s.append(KeepTogether([\n        _p('<b>Seguimiento de inventarios</b>'),\n",
   "    s.append(_tabla([\n        ['Tipo de inventario', 'Frecuencia', 'Alcance'],\n        ['Conteo cíclico', 'Mensual', 'Una parte de los artículos cada vez (por línea o ubicación), empezando por los de mayor valor y movimiento.'],\n        ['Inventario sorpresa', 'Sin aviso previo', 'Una muestra de artículos elegida por el Encargado de Inventarios o Dirección.'],\n        ['Inventario general', 'Cada 6 meses', 'Todo el almacén.'],\n    ], [3.8 * cm, 3.0 * cm, AN - 6.8 * cm]))\n    s.append(Spacer(1, 6))\n    s.append(_p(f'Si un inventario resulta por debajo del {_fmt_pct(meta)}, el encargado del almacén y el Encargado de Inventarios revisan las causas, se '\n                f'ajusta {sistema} y se repite el conteo de esos artículos en un plazo máximo de 15 días.'))\n    s.append(KeepTogether([\n        _p('<b>Seguimiento de inventarios</b>'),\n"
  ],
  [
   "\n    nombres = {'Entrega': d.get('entrega_nombre'), 'Recibe': d.get('recibe_nombre'), 'Visto bueno': None}\n    firmas = []\n    for rol, puesto in [('Entrega', 'Departamento de Sistemas'), ('Recibe', d.get('recibe_puesto') or 'Encargado del almacén'),\n                        ('Visto bueno', 'Dirección')]:\n        nom = nombres[rol]\n        firmas.append([Spacer(1, 1.7 * cm), _p('_______________________________', 'firma'), _p(rol, 'firmaB'),\n",
   "\n    nombres = {'Entrega': d.get('entrega_nombre'), 'Recibe': d.get('recibe_nombre'), 'Visto bueno': None}\n    firmas = []\n    for rol, puesto in [('Entrega', 'Encargado de Inventarios'), ('Recibe', d.get('recibe_puesto') or 'Encargado del almacén'),\n                        ('Visto bueno', 'Dirección')]:\n        nom = nombres[rol]\n        firmas.append([Spacer(1, 1.7 * cm), _p('_______________________________', 'firma'), _p(rol, 'firmaB'),\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <div class=\"field\"><label>Fecha de entrega</label><input id=\"acta_fecha_entrega\" type=\"date\" value=\"${hoy}\" /></div>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Entrega (Sistemas)</label><input id=\"acta_entrega_nombre\" value=\"${escapeHtml((SESION.usuario || {}).nombre || '')}\" /></div>\n      <div class=\"field\"><label>Recibe (encargado)</label><input id=\"acta_recibe_nombre\" /></div>\n    </div>\n    <div class=\"row-2\">\n",
   "      <div class=\"field\"><label>Fecha de entrega</label><input id=\"acta_fecha_entrega\" type=\"date\" value=\"${hoy}\" /></div>\n    </div>\n    <div class=\"row-2\">\n      <div class=\"field\"><label>Entrega (Encargado de inventarios)</label><input id=\"acta_entrega_nombre\" value=\"${escapeHtml((SESION.usuario || {}).nombre || '')}\" /></div>\n      <div class=\"field\"><label>Recibe (encargado)</label><input id=\"acta_recibe_nombre\" /></div>\n    </div>\n    <div class=\"row-2\">\n"
  ]
 ]
}

NUEVOS = {}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_acta_encargado_inventarios.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto and viejo not in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
