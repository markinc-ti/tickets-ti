# -*- coding: utf-8 -*-
"""
Turnos: en el mostrador, poder elegir A QUIEN llamar (no solo "el
siguiente" de la fila) -- para que si llega un proveedor o alguien que
conviene atender mas rapido / de forma mas profesional, se le pueda
llamar sin tener que esperar su turno en orden.

IMPORTANTE: este script es una continuacion de
fix_turnos_categorias_reporte.py -- aplica DESPUES de ese (si todavia
no lo corres, corre primero ese y luego este; si ya lo corriste, este
se aplica normal encima).

Que cambia:
  - El boton grande "Llamar siguiente" se queda igual (sigue siendo lo
    mas rapido para el caso normal).
  - Debajo aparece la lista completa de quienes estan esperando (folio
    + categoria si tiene), cada uno con su propio boton "Llamar" --
    para poder llamar a cualquiera fuera de orden.
  - No se toco el backend: el endpoint para llamar un turno
    (POST /api/turnos/{id}/llamar) ya aceptaba cualquier turno en
    espera, nomas que el mostrador antes solo tenia boton para el
    primero de la fila.

Que toca:
  - frontend/index.html -- la pantalla de Turnos del mostrador
    (Administrar/menu -> Turnos).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_turnos_llamar_elegir.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS["frontend/index.html"] = [
    [
        "async function renderTurnosMostrador() {\n  const cont = document.getElementById('turnosContenido');\n  if (!cont) return;\n  if (!META.mi_sucursal_id) {\n    cont.innerHTML = `<p style=\"font-size:13px; color:var(--copper);\">Tu usuario no tiene una sucursal asignada — pídele a tu administrador que te la asigne (Administrar → Usuarios) para poder llamar turnos.</p>`;\n    return;\n  }\n  let esperando;\n  try {\n    esperando = await api('/api/turnos/esperando');\n  } catch (e) {\n    cont.innerHTML = `<p style=\"font-size:13px; color:var(--copper);\">${escapeHtml(e.message)}</p>`;\n    return;\n  }\n  const ventanilla = META.mi_ventanilla_turnos || SESION.usuario.nombre;\n  cont.innerHTML = `\n    ${!META.mi_ventanilla_turnos ? `<p style=\"font-size:12px; color:var(--muted); background:rgba(155,157,159,0.12); padding:8px 10px; border-radius:6px;\">No tienes una ventanilla/caja fija asignada — en la pantalla se mostrará tu nombre. Pídele a tu administrador que te asigne una (ej. \"Caja 1\") en tu perfil si prefieres que se vea un número de caja.</p>` : ''}\n    <div style=\"text-align:center; padding:16px 0;\">\n      <div style=\"font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:1px;\">Esperando</div>\n      <div style=\"font-size:52px; font-weight:700; line-height:1;\">${esperando.length}</div>\n      <div style=\"font-size:13px; color:var(--muted);\">turno${esperando.length === 1 ? '' : 's'} en fila</div>\n    </div>\n    ${TURNOS_ULTIMO_LLAMADO ? `\n      <div style=\"border:1px solid rgba(155,157,159,0.35); border-radius:8px; padding:14px; margin-bottom:16px; text-align:center;\">\n        <div style=\"font-size:12px; color:var(--muted); text-transform:uppercase;\">Turno llamado</div>\n        <div style=\"font-size:36px; font-weight:700;\">#${TURNOS_ULTIMO_LLAMADO.folio}</div>\n        ${TURNOS_ULTIMO_LLAMADO.categoria_nombre ? `<div style=\"font-size:12px; color:var(--muted);\">${escapeHtml(TURNOS_ULTIMO_LLAMADO.categoria_nombre)}</div>` : ''}\n        <div style=\"font-size:13px; color:var(--muted); margin-bottom:10px;\">→ ${escapeHtml(ventanilla)}</div>\n        <div style=\"display:flex; gap:8px; justify-content:center;\">\n          <button class=\"primary\" onclick=\"atenderTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})\">Atender / Finalizar</button>\n          <button class=\"secondary\" onclick=\"cancelarTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})\">No se presentó</button>\n        </div>\n      </div>\n    ` : ''}\n    <button class=\"primary\" style=\"width:100%; padding:16px; font-size:16px;\" ${esperando.length === 0 ? 'disabled' : ''} onclick=\"llamarSiguienteTurnoUI(${esperando.length ? esperando[0].id : 'null'})\">\n      🔔 Llamar siguiente${esperando.length ? ` — Turno #${esperando[0].folio}${esperando[0].categoria_nombre ? ` (${escapeHtml(esperando[0].categoria_nombre)})` : ''}` : ''}\n    </button>\n  `;\n}\n\nasync function llamarSiguienteTurnoUI(turnoId) {",
        "async function renderTurnosMostrador() {\n  const cont = document.getElementById('turnosContenido');\n  if (!cont) return;\n  if (!META.mi_sucursal_id) {\n    cont.innerHTML = `<p style=\"font-size:13px; color:var(--copper);\">Tu usuario no tiene una sucursal asignada — pídele a tu administrador que te la asigne (Administrar → Usuarios) para poder llamar turnos.</p>`;\n    return;\n  }\n  let esperando;\n  try {\n    esperando = await api('/api/turnos/esperando');\n  } catch (e) {\n    cont.innerHTML = `<p style=\"font-size:13px; color:var(--copper);\">${escapeHtml(e.message)}</p>`;\n    return;\n  }\n  const ventanilla = META.mi_ventanilla_turnos || SESION.usuario.nombre;\n  cont.innerHTML = `\n    ${!META.mi_ventanilla_turnos ? `<p style=\"font-size:12px; color:var(--muted); background:rgba(155,157,159,0.12); padding:8px 10px; border-radius:6px;\">No tienes una ventanilla/caja fija asignada — en la pantalla se mostrará tu nombre. Pídele a tu administrador que te asigne una (ej. \"Caja 1\") en tu perfil si prefieres que se vea un número de caja.</p>` : ''}\n    <div style=\"text-align:center; padding:16px 0;\">\n      <div style=\"font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:1px;\">Esperando</div>\n      <div style=\"font-size:52px; font-weight:700; line-height:1;\">${esperando.length}</div>\n      <div style=\"font-size:13px; color:var(--muted);\">turno${esperando.length === 1 ? '' : 's'} en fila</div>\n    </div>\n    ${TURNOS_ULTIMO_LLAMADO ? `\n      <div style=\"border:1px solid rgba(155,157,159,0.35); border-radius:8px; padding:14px; margin-bottom:16px; text-align:center;\">\n        <div style=\"font-size:12px; color:var(--muted); text-transform:uppercase;\">Turno llamado</div>\n        <div style=\"font-size:36px; font-weight:700;\">#${TURNOS_ULTIMO_LLAMADO.folio}</div>\n        ${TURNOS_ULTIMO_LLAMADO.categoria_nombre ? `<div style=\"font-size:12px; color:var(--muted);\">${escapeHtml(TURNOS_ULTIMO_LLAMADO.categoria_nombre)}</div>` : ''}\n        <div style=\"font-size:13px; color:var(--muted); margin-bottom:10px;\">→ ${escapeHtml(ventanilla)}</div>\n        <div style=\"display:flex; gap:8px; justify-content:center;\">\n          <button class=\"primary\" onclick=\"atenderTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})\">Atender / Finalizar</button>\n          <button class=\"secondary\" onclick=\"cancelarTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})\">No se presentó</button>\n        </div>\n      </div>\n    ` : ''}\n    <button class=\"primary\" style=\"width:100%; padding:16px; font-size:16px;\" ${esperando.length === 0 ? 'disabled' : ''} onclick=\"llamarSiguienteTurnoUI(${esperando.length ? esperando[0].id : 'null'})\">\n      🔔 Llamar siguiente${esperando.length ? ` — Turno #${esperando[0].folio}${esperando[0].categoria_nombre ? ` (${escapeHtml(esperando[0].categoria_nombre)})` : ''}` : ''}\n    </button>\n    ${esperando.length > 1 ? `\n      <div style=\"margin-top:14px;\">\n        <div style=\"font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;\">O elige a quién atender (ej. un proveedor)</div>\n        <div style=\"display:flex; flex-direction:column; gap:6px; max-height:280px; overflow-y:auto;\">\n          ${esperando.map(t => `\n            <div style=\"display:flex; align-items:center; justify-content:space-between; gap:8px; padding:8px 10px; border:1px solid rgba(155,157,159,0.25); border-radius:6px;\">\n              <span style=\"font-size:13px;\">#${t.folio}${t.categoria_nombre ? ` <span style=\"color:var(--muted); font-size:11px;\">(${escapeHtml(t.categoria_nombre)})</span>` : ''}</span>\n              <button class=\"secondary\" style=\"padding:4px 10px; font-size:12px;\" onclick=\"llamarSiguienteTurnoUI(${t.id})\">Llamar</button>\n            </div>\n          `).join('')}\n        </div>\n      </div>\n    ` : ''}\n  `;\n}\n\nasync function llamarSiguienteTurnoUI(turnoId) {",
    ],
]



def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in ARCHIVOS[ruta]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print("[" + ruta + "] No se encontro un bloque esperado. Corriste primero fix_turnos_categorias_reporte.py? El archivo pudo haber cambiado desde la ultima vez.")
            hubo_error = True
    escribir(ruta, contenido)
    print("[" + ruta + "] " + str(cambios) + "/" + str(len(ARCHIVOS[ruta])) + " cambio(s) aplicado(s).")
    return not hubo_error


def main():
    ok = True
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Turnos: en el mostrador se puede elegir a quien llamar, no solo el siguiente"')
    print("   git push")


if __name__ == "__main__":
    main()
