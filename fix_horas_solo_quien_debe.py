#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RH — "Quién te debe horas (tu sucursal)": ya no lista a todos los
empleados de la sucursal, solo a los que sí deben horas.

Pedido de David: "en la parte donde dice quien te debe horas, solo
quiero que salgan los que deban, no tiene caso que esten los demas".

Antes, esa tabla (en la pantalla de la encargada de sucursal, pestaña
"Por aceptar") listaba a TODOS los empleados de la sucursal, con "Al
corriente" para quien no debe nada -- ahora filtra y solo aparecen los
que tienen saldo pendiente (saldo > 0).

Qué toca:
- frontend/index.html: se agrega .filter(s => s.saldo > 0) antes de
  pintar la lista, y el mensaje de "vacío" cambia para reflejar que
  ahora puede estar vacío tanto porque no hay nadie en la sucursal como
  porque nadie debe horas.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_horas_solo_quien_debe.py
"""
import sys

ARCHIVOS = {
    'frontend/index.html': [
        [
            '''        ${saldosSucursal.map(s => `
          <tr>
            <td>${escapeHtml(s.nombre_completo)}</td>
            <td>${s.puesto ? escapeHtml(s.puesto) : '—'}</td>
            <td>${formatearHoras(s.debe_total)}</td>
            <td>${formatearHoras(s.pagado_total)}</td>
            <td>${s.saldo > 0
              ? `<span class="badge ${s.saldo >= 6 ? 'urgente' : 'alta'}">Debe ${formatearHoras(s.saldo)}</span>`
              : '<span class="badge baja">Al corriente</span>'}
            </td>
          </tr>
        `).join('') || '<tr><td colspan="5" class="empty-col">— sin personas en tu sucursal todavía —</td></tr>'}''',
            '''        ${saldosSucursal.filter(s => s.saldo > 0).map(s => `
          <tr>
            <td>${escapeHtml(s.nombre_completo)}</td>
            <td>${s.puesto ? escapeHtml(s.puesto) : '—'}</td>
            <td>${formatearHoras(s.debe_total)}</td>
            <td>${formatearHoras(s.pagado_total)}</td>
            <td><span class="badge ${s.saldo >= 6 ? 'urgente' : 'alta'}">Debe ${formatearHoras(s.saldo)}</span></td>
          </tr>
        `).join('') || '<tr><td colspan="5" class="empty-col">— nadie de tu sucursal debe horas —</td></tr>'}''',
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
    print("    git add frontend/index.html")
    print('    git commit -m "RH: Quien te debe horas solo lista a quien si debe"')
    print("    git push")


if __name__ == "__main__":
    main()
