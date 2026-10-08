#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RH — nueva pestaña "Mis horas" para que CUALQUIER empleado vea su propio
registro: cuánto debe, cuánto ya pagó, y el estado de cada solicitud de
"horas pagadas" que haya mandado (pendiente / aceptada / rechazada, con
el motivo si se la rechazaron).

Pedido de David: "EL EMPLEADO DEBE TENER SU REGISTRO PARA CUANDO PAGUE
SUS HORAS, PARA QUE SEPA QUE SI ACEPTARON SU ESTATUS DE SU SOLICITUD".

Hoy el empleado puede registrar que "pagó horas" (botón "Registrar
horas pagadas"), pero no tenía ningún lugar donde ver qué pasó después
-- si su encargado ya lo autorizó, lo rechazó, o sigue pendiente. Esa
información ya existía en el backend (el mismo endpoint que usa RH
para consultar el historial de cualquiera ya permite que cada quien
consulte el suyo propio) -- solo faltaba una pantalla para verlo.

Qué toca:
- frontend/index.html:
  - Nueva pestaña "🕒 Mis horas", visible para todos (no solo RH/admin/
    encargado), junto a "Mis incidencias".
  - Nueva función renderMisHorasRH() que muestra debe/pagado/saldo y la
    lista de movimientos con su estado (⏳ esperando autorización /
    ✅ aceptado / ❌ rechazado, con el motivo del rechazo si aplica).
  - cambiarRHTab() ahora reconoce la pestaña 'mishoras'.

No se toca el backend -- el endpoint GET /api/rh/horas/{usuario_id} ya
dejaba que cada quien consultara su propio saldo y movimientos.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_mis_horas_empleado.py
"""
import sys

ARCHIVOS = {
    'frontend/index.html': [
        [
            '''      <button class="admin-tab" id="tabRHMias" onclick="cambiarRHTab('mias')">Mis incidencias</button>
      <button class="admin-tab" id="tabRHEncargado" onclick="cambiarRHTab('encargado')" style="display:none;">Por aceptar (mi sucursal)</button>''',
            '''      <button class="admin-tab" id="tabRHMias" onclick="cambiarRHTab('mias')">Mis incidencias</button>
      <button class="admin-tab" id="tabRHMisHoras" onclick="cambiarRHTab('mishoras')">🕒 Mis horas</button>
      <button class="admin-tab" id="tabRHEncargado" onclick="cambiarRHTab('encargado')" style="display:none;">Por aceptar (mi sucursal)</button>''',
        ],
        [
            '''async function cambiarRHTab(tab) {
  RH_TAB = tab;
  document.getElementById('tabRHMias').classList.toggle('active', tab === 'mias');
  document.getElementById('tabRHEncargado').classList.toggle('active', tab === 'encargado');''',
            '''async function cambiarRHTab(tab) {
  RH_TAB = tab;
  document.getElementById('tabRHMias').classList.toggle('active', tab === 'mias');
  document.getElementById('tabRHMisHoras').classList.toggle('active', tab === 'mishoras');
  document.getElementById('tabRHEncargado').classList.toggle('active', tab === 'encargado');''',
        ],
        [
            '''  if (tab === 'horas') await renderConsultaHorasRH();''',
            '''  if (tab === 'mishoras') await renderMisHorasRH();
  else if (tab === 'horas') await renderConsultaHorasRH();''',
        ],
        [
            '''// ---- Consulta de horas (cuánto debe cada empleado, y cómo lo va pagando) ----

let HORAS_RH_FILTRO = 'deben';''',
            '''// ---- Mis horas (cada empleado ve su propio saldo y el estado de sus solicitudes) ----

async function renderMisHorasRH() {
  const datos = await api(`/api/rh/horas/${SESION.usuario.id}`);
  const cont = document.getElementById('rhContenido');
  const BADGE_ESTADO_MOV = {
    pendiente: '<span class="rol-tag">⏳ Esperando autorización</span>',
    aprobado: '<span class="badge baja">✅ Aceptado</span>',
    rechazado: '<span class="badge urgente">❌ Rechazado</span>',
  };
  cont.innerHTML = `
    <p style="font-size:12px; color:var(--muted); margin-bottom:14px;">
      Aquí ves cuántas horas debes, cuáles ya se te reconocieron como pagadas, y si el encargado de tu sucursal ya aceptó o rechazó cada solicitud que mandaste.
    </p>
    <div style="display:flex; gap:14px; margin-bottom:16px;">
      <div style="flex:1; background:var(--substrate); padding:12px; text-align:center;">
        <div style="font-size:11px; color:var(--muted); text-transform:uppercase;">Debes</div>
        <div style="font-size:20px; font-weight:bold;">${formatearHoras(datos.debe_total)}</div>
      </div>
      <div style="flex:1; background:var(--substrate); padding:12px; text-align:center;">
        <div style="font-size:11px; color:var(--muted); text-transform:uppercase;">Pagado</div>
        <div style="font-size:20px; font-weight:bold;">${formatearHoras(datos.pagado_total)}</div>
      </div>
      <div style="flex:1; background:var(--substrate); padding:12px; text-align:center; border:1px solid ${datos.saldo > 0 ? 'var(--urgente)' : 'var(--baja)'};">
        <div style="font-size:11px; color:var(--muted); text-transform:uppercase;">Saldo</div>
        <div style="font-size:20px; font-weight:bold; color:${datos.saldo > 0 ? 'var(--urgente)' : 'var(--baja)'};">${formatearHoras(datos.saldo)}</div>
      </div>
    </div>
    <table class="users">
      <thead><tr><th>Fecha</th><th>Tipo</th><th>Horas</th><th>Notas</th><th>Estado</th></tr></thead>
      <tbody>
        ${datos.movimientos.map(m => `
          <tr>
            <td>${(m.fecha || m.creado_en).slice(0,10)}</td>
            <td>${m.tipo === 'debe' ? '<span class="badge urgente">Debo</span>' : '<span class="badge baja">Pagué</span>'}</td>
            <td>${formatearHoras(m.horas)}</td>
            <td>${m.notas ? escapeHtml(m.notas) : '—'}${m.estado === 'rechazado' && m.motivo_rechazo ? `<div style="font-size:10px; color:var(--urgente); margin-top:2px;">Motivo: ${escapeHtml(m.motivo_rechazo)}</div>` : ''}</td>
            <td>${BADGE_ESTADO_MOV[m.estado] || m.estado}</td>
          </tr>
        `).join('') || '<tr><td colspan="5" class="empty-col">— todavía no tienes movimientos de horas —</td></tr>'}
      </tbody>
    </table>
    <button class="secondary" style="margin-top:14px;" onclick="abrirSolicitarPagoHoras()">+ Registrar horas pagadas</button>
  `;
}

// ---- Consulta de horas (cuánto debe cada empleado, y cómo lo va pagando) ----

let HORAS_RH_FILTRO = 'deben';''',
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
    print('    git commit -m "RH: nueva pestana Mis horas para que el empleado vea su saldo y el estatus de sus solicitudes"')
    print("    git push")


if __name__ == "__main__":
    main()
