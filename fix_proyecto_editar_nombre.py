# -*- coding: utf-8 -*-
"""
Proyectos: editar el nombre (y la descripción) de un proyecto desde la web.

- En el detalle del proyecto aparece un botón ✏️ junto al nombre
  (solo administrador y técnico, los mismos que ya pueden cambiar estado
  y fecha estimada).
- El servidor ya no acepta un nombre vacío.

Uso (en la carpeta tickets-ti):
    py -3 fix_proyecto_editar_nombre.py
Se puede correr varias veces.
"""
import io
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RAIZ, "backend", "app.py")
HTML = os.path.join(RAIZ, "frontend", "index.html")
MARCA = "editarNombreProyectoUI"


def leer(ruta):
    with io.open(ruta, "r", encoding="utf-8", newline="") as f:
        return f.read()


def escribir(ruta, texto):
    with io.open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(texto)


def reemplazar(texto, viejo, nuevo, archivo):
    for v, n in ((viejo, nuevo), (viejo.replace("\n", "\r\n"), nuevo.replace("\n", "\r\n"))):
        if texto.count(v) == 1:
            return texto.replace(v, n)
    print("No encontré el lugar para el cambio en", archivo, "->", viejo.strip().splitlines()[0][:80])
    sys.exit(1)


def main():
    for r in (APP, HTML):
        if not os.path.exists(r):
            print("Corre este script dentro de la carpeta tickets-ti (no encuentro %s)." % r)
            sys.exit(1)

    html = leer(HTML)
    if MARCA in html:
        print("Ya estaba aplicado. Nada que hacer.")
        return

    # --- Backend: no aceptar nombre vacío ---
    app = leer(APP)
    app = reemplazar(app,
        """        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.actualizar_proyecto(usuario["empresa_id"], proyecto_id, payload.nombre, payload.descripcion, payload.fecha_estimada)""",
        """        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    nombre = payload.nombre.strip() if payload.nombre is not None else None
    if nombre is not None and not nombre:
        raise HTTPException(status_code=400, detail="El nombre del proyecto no puede quedar vacío")
    db.actualizar_proyecto(usuario["empresa_id"], proyecto_id, nombre, payload.descripcion, payload.fecha_estimada)""",
        "app.py")

    # --- Frontend: título editable ---
    html = reemplazar(html,
        """    <h2>${escapeHtml(p.nombre)}</h2>
    <button class="secondary" style="margin-bottom:10px;" onclick="window.open('/gantt.html?proyecto_id=${p.id}', '_blank')">📊 Ver Gantt</button>
    ${p.descripcion ? `<p style="font-size:13px; color:var(--muted);">${escapeHtml(p.descripcion)}</p>` : ''}""",
        """    <div id="py_titulo_bloque">
      <h2 style="display:flex; align-items:center; gap:8px;">${escapeHtml(p.nombre)}${['admin','tecnico'].includes(SESION.usuario.rol) ? `<button class="secondary" style="padding:2px 8px; font-size:13px;" title="Editar nombre y descripción" onclick="editarNombreProyectoUI(${p.id})">✏️</button>` : ''}</h2>
      <button class="secondary" style="margin-bottom:10px;" onclick="window.open('/gantt.html?proyecto_id=${p.id}', '_blank')">📊 Ver Gantt</button>
      ${p.descripcion ? `<p style="font-size:13px; color:var(--muted);">${escapeHtml(p.descripcion)}</p>` : ''}
    </div>""",
        "index.html")

    html = reemplazar(html,
        """async function guardarFechaEstimada(id, fecha) {""",
        """function editarNombreProyectoUI(id) {
  const p = PROYECTO_DETALLE_ACTUAL;
  if (!p || p.id !== id) return;
  document.getElementById('py_titulo_bloque').innerHTML = `
    <div class="field"><label>Nombre del proyecto</label><input type="text" id="py_nombre_edit" maxlength="160" value="${escapeHtml(p.nombre)}" /></div>
    <div class="field"><label>Descripción</label><textarea id="py_desc_edit" rows="3">${escapeHtml(p.descripcion || '')}</textarea></div>
    <div style="display:flex; gap:8px; margin-bottom:10px;">
      <button class="primary" onclick="guardarNombreProyectoUI(${id}, this)">Guardar</button>
      <button class="secondary" onclick="abrirDetalleProyecto(${id})">Cancelar</button>
    </div>
    <div id="py_nombre_error" class="error-msg"></div>`;
  const input = document.getElementById('py_nombre_edit');
  input.focus();
  input.select();
}

async function guardarNombreProyectoUI(id, boton) {
  const nombre = document.getElementById('py_nombre_edit').value.trim();
  const descripcion = document.getElementById('py_desc_edit').value.trim();
  if (!nombre) { document.getElementById('py_nombre_error').textContent = 'El nombre no puede quedar vacío'; return; }
  boton.disabled = true;
  try {
    await api(`/api/proyectos/${id}`, { method: 'PATCH', body: JSON.stringify({ nombre, descripcion }) });
    await abrirDetalleProyecto(id);
    await cargarBoardProyectos();
    mostrarExito('Proyecto actualizado');
  } catch (e) {
    boton.disabled = false;
    document.getElementById('py_nombre_error').textContent = e.message;
  }
}

async function guardarFechaEstimada(id, fecha) {""",
        "index.html")

    escribir(APP, app)
    escribir(HTML, html)
    print("Listo: ya se puede editar el nombre del proyecto (botón ✏️ en el detalle).")
    print("Ahora: git add -A ; git commit -m \"Editar nombre de proyecto\" ; git push")


if __name__ == "__main__":
    main()
