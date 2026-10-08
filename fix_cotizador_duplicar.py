# -*- coding: utf-8 -*-
"""
Cotizador de Superadmin: duplicar una cotización pasada como plantilla
para una nueva

Antes, para reusar lo que ya habías cotizado a alguien más, tenías que
volver a escribir cada ítem a mano en una cotización nueva (o editar
encima de la vieja, perdiéndola). Ahora, en el listado "🧾 Cotizador",
cada fila trae un botón 📋 "Duplicar" — copia todos los ítems, precios
y textos de esa cotización a una nueva, ligada al cliente/empresa que
tú elijas, y la abre lista para que solo ajustes lo que cambie (casi
siempre nada más el precio). La cotización original queda intacta.

No se tocó nada del backend — el duplicado se arma en el navegador
combinando los mismos 3 endpoints que ya existían (leer la cotización
de origen, crear una nueva, guardarle la configuración copiada).

Qué toca: frontend/index.html (panel de Superadmin → 🧾 Cotizador).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_cotizador_duplicar.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS['frontend/index.html'] = [
    # 1) Funciones nuevas: abrir el diálogo de duplicar, y duplicar de verdad.
    [
        '''async function eliminarCotizacionUI(id, nombre) {
  if (!confirm(`¿Eliminar la cotización de "${nombre}"? Esto no se puede deshacer.`)) return;
  await api(`/api/superadmin/cotizaciones/${id}`, { method: 'DELETE' });
  await renderCotizadorSuperadmin();
}

async function renderCotizadorSuperadmin() {
''',
        '''async function eliminarCotizacionUI(id, nombre) {
  if (!confirm(`¿Eliminar la cotización de "${nombre}"? Esto no se puede deshacer.`)) return;
  await api(`/api/superadmin/cotizaciones/${id}`, { method: 'DELETE' });
  await renderCotizadorSuperadmin();
}

function abrirDuplicarCotizacionUI(origenId, nombreOrigen) {
  document.getElementById('modalContent').innerHTML = `
    <button class="close-btn" onclick="cerrarModal()">cerrar</button>
    <h2>📋 Duplicar cotización</h2>
    <p style="font-size:12px; color:var(--muted);">Se copian todos los ítems, precios y textos de "${escapeHtml(nombreOrigen)}" a una cotización nueva — solo ajusta el cliente y lo que cambie.</p>
    <div class="field"><label>Vincular a empresa existente (opcional)</label>
      <select id="dc_empresa"><option value="">— Sin vincular / prospecto —</option>${EMPRESAS_CACHE.map(e => `<option value="${e.id}">${escapeHtml(e.nombre)}</option>`).join('')}</select>
    </div>
    <div class="field"><label>Nombre del cliente/prospecto</label><input id="dc_nombre" placeholder="ej. Juan Pérez / Ferretería La Económica" /></div>
    <button class="primary" style="width:100%;" onclick="duplicarCotizacionUI(${origenId}, this)">Duplicar y abrir</button>
    <div id="dcError" class="error-msg"></div>
  `;
}

async function duplicarCotizacionUI(origenId, boton) {
  const payload = {
    empresa_id: document.getElementById('dc_empresa').value ? parseInt(document.getElementById('dc_empresa').value, 10) : null,
    nombre_cliente: document.getElementById('dc_nombre').value.trim() || null,
  };
  if (!payload.empresa_id && !payload.nombre_cliente) {
    document.getElementById('dcError').textContent = 'Ponle un nombre o vincúlala a una empresa';
    return;
  }
  await conBloqueoDeBoton(boton, async () => {
    try {
      const origen = await api(`/api/superadmin/cotizaciones/${origenId}`);
      const { id } = await api('/api/superadmin/cotizaciones', { method: 'POST', body: JSON.stringify(payload) });
      await api(`/api/superadmin/cotizaciones/${id}`, { method: 'PUT', body: JSON.stringify({ ...payload, config: origen.config || {} }) });
      window.open(`/cotizador-costos.html?cotizacion_id=${id}`, '_blank');
      cerrarModal();
      await abrirCotizadorSuperadmin();
    } catch (e) {
      document.getElementById('dcError').textContent = e.message;
    }
  });
}

async function renderCotizadorSuperadmin() {
''',
    ],
    # 2) Botón 📋 Duplicar en cada fila del listado, junto al de eliminar.
    [
        '''            <td>${f.margen_pct}%</td>
            <td><span class="quitar" onclick="eliminarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,"\\\\'")}')">✕</span></td>
''',
        '''            <td>${f.margen_pct}%</td>
            <td>
              <span style="cursor:pointer; margin-right:10px;" title="Duplicar — usarla como base para una cotización nueva" onclick="abrirDuplicarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,"\\\\'")}')">📋</span>
              <span class="quitar" onclick="eliminarCotizacionUI(${f.id}, '${escapeHtml(f.nombre_cliente).replace(/'/g,"\\\\'")}')">✕</span>
            </td>
''',
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False
    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print(f"[{ruta}] No se encontró un bloque esperado. El archivo pudo haber cambiado desde la última vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print('   git commit -m "Cotizador: duplicar una cotizacion pasada como plantilla para una nueva"')
    print("   git push")


if __name__ == "__main__":
    main()
