# -*- coding: utf-8 -*-
"""
Agrega la columna "% aplicado" a la tabla de Top 50 descuentos mas altos
(Dashboard -> Descuentos otorgados -> Ver desglose completo). Se calcula
como descuento / (monto + descuento) -- el % que representa el descuento
sobre el precio original de esa venta.

NOTA: este porcentaje se calcula con los montos que ya maneja la app; puede
no coincidir exacto con el "% de descuento" que Microsip muestra en el
documento (que a veces se calcula contra una base distinta, como el precio
de lista antes de otros ajustes).

Uso: colocalo en la carpeta del repo (junto a frontend/) y corre:
    py fix_porcentaje_descuento.py
"""
import sys

VIEJO = '        <thead><tr><th>#</th><th>Cliente</th><th>Folio</th><th>Fecha / Hora</th><th>Descuento</th><th>Monto del ticket</th></tr></thead>\n        <tbody>\n          ${pagina.length ? pagina.map((v, i) => `\n            <tr>\n              <td>${inicio + i + 1}</td>\n              <td>${escapeHtml(v.cliente)}</td>\n              <td>${escapeHtml(v.folio || \'—\')}</td>\n              <td>${escapeHtml(v.fecha || \'—\')} ${escapeHtml(v.hora || \'\')}</td>\n              <td>$${v.descuento.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n              <td>$${v.monto.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n            </tr>\n          `).join(\'\') : `<tr><td colspan="6" class="empty-col">— sin descuentos en esta sucursal —</td></tr>`}'
NUEVO = '        <thead><tr><th>#</th><th>Cliente</th><th>Folio</th><th>Fecha / Hora</th><th>Descuento</th><th>% aplicado</th><th>Monto del ticket</th></tr></thead>\n        <tbody>\n          ${pagina.length ? pagina.map((v, i) => `\n            <tr>\n              <td>${inicio + i + 1}</td>\n              <td>${escapeHtml(v.cliente)}</td>\n              <td>${escapeHtml(v.folio || \'—\')}</td>\n              <td>${escapeHtml(v.fecha || \'—\')} ${escapeHtml(v.hora || \'\')}</td>\n              <td>$${v.descuento.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n              <td>${(v.monto + v.descuento) > 0 ? ((v.descuento / (v.monto + v.descuento)) * 100).toFixed(1) + \'%\' : \'—\'}</td>\n              <td>$${v.monto.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n            </tr>\n          `).join(\'\') : `<tr><td colspan="7" class="empty-col">— sin descuentos en esta sucursal —</td></tr>`}'


def main():
    ruta = "frontend/index.html"
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
    print("   git add frontend/index.html")
    print('   git commit -m "Top descuentos: agregar columna de porcentaje aplicado"')
    print("   git push")


if __name__ == "__main__":
    main()
