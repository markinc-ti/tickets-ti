# -*- coding: utf-8 -*-
"""
El Dashboard ahora tiene dos botones (visibles solo para quien ya podía ver
esta zona, permiso acceso_entregas): "Flotilla" y "Auditoría".

- Flotilla: lo que ya había (el mapa en vivo).
- Auditoría: las 5 tarjetas financieras que antes estaban sueltas en el
  Dashboard general (Ventas Punto de Venta, Valor del inventario,
  Artículos sin movimiento, Valor del inventario a precio de venta,
  Descuentos otorgados).

Ambas secciones empiezan ocultas; se muestran al hacer clic en su botón.
El mapa de Flotilla se inicializa solo la primera vez que se abre esa
sección (los mapas de Leaflet salen en blanco si se inicializan mientras
su contenedor está oculto).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_dashboard_flotilla_auditoria.py
"""
import sys

RUTA = 'frontend/index.html'

VIEJO = '''async function abrirDashboard() {
  document.getElementById('menuScreen').style.display = 'none';
  document.getElementById('app').style.display = 'none';
  document.getElementById('proyectosScreen').style.display = 'none';
  document.getElementById('marketingScreen').style.display = 'none';
  document.getElementById('equiposScreen').style.display = 'none';
  document.getElementById('comprasScreen').style.display = 'none';
  document.getElementById('rhScreen').style.display = 'none';
  document.getElementById('reparacionesScreen').style.display = 'none';
  document.getElementById('entregasScreen').style.display = 'none';
  document.getElementById('checadorPrecioScreen').style.display = 'none';
  document.getElementById('dashboardScreen').style.display = 'block';
  if (SESION.usuario.rol !== 'master') {
    document.getElementById('whoamiDashboard').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol]}`;
    document.getElementById('btnDashboardVolver').style.display = 'inline-block';
  }
  const cont = document.getElementById('dashboardContenido');
  cont.innerHTML = '<p style="color:var(--muted); font-family:\\'JetBrains Mono\\',monospace; font-size:12px;">Cargando estadísticas...</p>';
  try {
    const d = await api('/api/dashboard');
    const puedeAutorizar = SESION.usuario.rol === 'master' || SESION.usuario.rol === 'admin';
    const puedeVerFlotilla = META.mis_permisos.acceso_entregas;
    let resumenVentasPv = null;
    if (puedeVerFlotilla) {
      try {
        resumenVentasPv = await api(`/api/dashboard/ventas-pv?fecha=${new Date().toISOString().slice(0, 10)}`);
      } catch (e) {
        resumenVentasPv = null; // si Microsip no está configurado o falla, simplemente no se muestra la tarjeta
      }
    }
    let resumenValorInventario = null;
    if (puedeVerFlotilla) {
      try {
        resumenValorInventario = await api('/api/dashboard/valor-inventario');
      } catch (e) {
        resumenValorInventario = null;
      }
    }
    let resumenSinMovimiento = null;
    if (puedeVerFlotilla) {
      try {
        resumenSinMovimiento = await api('/api/dashboard/sin-movimiento');
      } catch (e) {
        resumenSinMovimiento = null;
      }
    }
    let resumenValorInventarioVenta = null;
    if (puedeVerFlotilla) {
      try {
        resumenValorInventarioVenta = await api('/api/dashboard/valor-inventario-venta');
      } catch (e) {
        resumenValorInventarioVenta = null;
      }
    }
    let resumenDescuentosPv = null;
    if (puedeVerFlotilla) {
      try {
        resumenDescuentosPv = await api(`/api/dashboard/descuentos-pv?fecha=${new Date().toISOString().slice(0, 10)}`);
      } catch (e) {
        resumenDescuentosPv = null;
      }
    }
    cont.innerHTML = `
      ${puedeVerFlotilla ? `
        <div style="margin-bottom:24px;">
          <h3 style="margin:0 0 8px;">📍 Flotilla en vivo</h3>
          <div id="dashFlotillaMsg" style="font-size:12px; color:var(--muted); margin-bottom:8px;">Cargando posiciones…</div>
          <div id="dashFlotillaMapa" style="width:100%; height:340px; border:1px solid rgba(155,157,159,0.3); border-radius:6px;"></div>
        </div>
      ` : ''}
      ${puedeAutorizar ? '<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>' : ''}
      <div class="dash-grid">
        ${tarjetaModuloDashboard('Tickets', '🎫', d.tickets.total, d.tickets.por_estado, 'var(--copper)', '/api/dashboard/tickets')}
        ${tarjetaModuloDashboard('Reparaciones', '🔧', d.reparaciones.total, d.reparaciones.por_estado, '#5B9BD5', '/api/dashboard/reparaciones')}
        ${tarjetaModuloDashboard('Proyectos', '📋', d.proyectos.total, d.proyectos.por_estado, '#70AD47', '/api/dashboard/proyectos')}
        ${tarjetaModuloDashboard('Equipos', '💻', d.equipos.total, d.equipos.por_estado, '#FFC000', '/api/dashboard/equipos')}
        <div class="dash-tarjeta">
          <div class="dash-tarjeta-header">
            <span class="dash-icono">🛒</span>
            <div>
              <div class="dash-titulo">Compras</div>
              <div class="dash-total">${d.compras.ciclos_total} ciclo(s) en total</div>
            </div>
          </div>
          <div class="dash-barras">
            ${Object.entries(d.compras.ciclos_por_estado).map(([estado, n]) => `
              <div class="dash-fila">
                <span class="dash-fila-label">${NOMBRES_ESTADO_DASHBOARD[estado] || estado}</span>
                <div class="dash-fila-barra-fondo"><div class="dash-fila-barra" style="width:${d.compras.ciclos_total > 0 ? Math.max(4, (n / d.compras.ciclos_total) * 100) : 0}%; background:#9B59B6;"></div></div>
                <span class="dash-fila-numero">${n}</span>
              </div>
            `).join('')}
          </div>
          <p style="font-size:12px; color:var(--muted); margin-top:10px;">${d.compras.pedidos_pendientes} pedido(s) en ciclos abiertos, esperando surtirse.</p>
          ${d.compras.por_sucursal && d.compras.por_sucursal.length ? `
            <div style="margin-top:12px; border-top:1px solid rgba(155,157,159,0.2); padding-top:10px;">
              <p style="font-size:11px; color:var(--muted); text-transform:uppercase; margin-bottom:6px;">Gasto por sucursal</p>
              ${d.compras.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('')}
              <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">
                <span>Total general</span>
                <span>$${d.compras.precio_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
              </div>
            </div>
          ` : ''}
          <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="descargarReporte(this, '/api/dashboard/compras', 'compras', 'pdf')">📄 Descargar PDF de Compras</button>
        </div>
${puedeVerFlotilla && resumenVentasPv ? `
          <div class="dash-tarjeta">
            <div id="dashResumenVentasPvCard">${contenidoTarjetaResumenVentasPv(resumenVentasPv)}</div>
            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>
          </div>
        ` : ''}
        ${puedeVerFlotilla && resumenValorInventario ? `
          <div class="dash-tarjeta">
            <div class="dash-tarjeta-header">
              <span class="dash-icono">📦</span>
              <div>
                <div class="dash-titulo">Valor del inventario</div>
                <div class="dash-total">$${resumenValorInventario.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
              </div>
            </div>
            <div style="margin-top:10px;">
              ${resumenValorInventario.por_sucursal.length ? resumenValorInventario.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con capas de costo activas.</p>`}
            </div>
<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioDashboard()">🔎 Ver desglose completo</button>
          </div>
        ` : ''}
        ${puedeVerFlotilla && resumenSinMovimiento ? `
          <div class="dash-tarjeta">
            <div class="dash-tarjeta-header">
              <span class="dash-icono">🐌</span>
              <div>
                <div class="dash-titulo">Artículos sin movimiento</div>
                <div class="dash-total">$${resumenSinMovimiento.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
              </div>
            </div>
            <div style="margin-top:10px;">
              ${resumenSinMovimiento.por_sucursal.length ? resumenSinMovimiento.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin artículos detectados sin movimiento.</p>`}
            </div>
<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseSinMovimientoDashboard()">🔎 Ver desglose completo</button>
          </div>
        ` : ''}
        ${puedeVerFlotilla && resumenValorInventarioVenta ? `
          <div class="dash-tarjeta">
            <div class="dash-tarjeta-header">
              <span class="dash-icono">💲</span>
              <div>
                <div class="dash-titulo">Valor del inventario (precio de venta)</div>
                <div class="dash-total">$${resumenValorInventarioVenta.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
              </div>
            </div>
            <div style="margin-top:10px;">
              ${resumenValorInventarioVenta.por_sucursal.length ? resumenValorInventarioVenta.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con precio de lista capturado.</p>`}
            </div>
<button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioVentaDashboard()">🔎 Ver desglose completo</button>
          </div>
        ` : ''}
        ${puedeVerFlotilla && resumenDescuentosPv ? `
          <div class="dash-tarjeta">
            <div class="dash-tarjeta-header">
              <span class="dash-icono">🏷️</span>
              <div>
                <div class="dash-titulo">Descuentos otorgados</div>
                <div class="dash-total">Hoy — $${resumenDescuentosPv.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
              </div>
            </div>
            <div style="margin-top:10px;">
              ${resumenDescuentosPv.por_sucursal.length ? resumenDescuentosPv.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.descuento_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin descuentos registrados hoy.</p>`}
            </div>
            <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseDescuentosDashboard()">🔎 Ver desglose completo</button>
          </div>
        ` : ''}
        ${tarjetaModuloDashboard('Recursos Humanos', '🩺', d.rh.total, d.rh.por_estado, '#E85D9E', '/api/dashboard/rh')}
      </div>
    `;
    if (puedeAutorizar) await renderAutorizacionesCompra();
    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();
    if (puedeVerFlotilla && resumenVentasPv) iniciarAutoRefrescoResumenVentasPv();
  } catch (e) {
    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;
  }
}'''

NUEVO = '''let DASH_FLOTILLA_MAPA_INICIALIZADO = false;

function dashMostrarSeccion(seccion) {
  const secFlotilla = document.getElementById('dashSeccionFlotilla');
  const secAuditoria = document.getElementById('dashSeccionAuditoria');
  const btnFlotilla = document.getElementById('dashBtnFlotilla');
  const btnAuditoria = document.getElementById('dashBtnAuditoria');
  if (secFlotilla) secFlotilla.style.display = seccion === 'flotilla' ? 'block' : 'none';
  if (secAuditoria) secAuditoria.style.display = seccion === 'auditoria' ? 'block' : 'none';
  [[btnFlotilla, 'flotilla'], [btnAuditoria, 'auditoria']].forEach(([btn, val]) => {
    if (!btn) return;
    btn.style.background = seccion === val ? 'var(--copper)' : '';
    btn.style.color = seccion === val ? '#fff' : '';
  });
  // El mapa de Leaflet sale en blanco si se inicializa mientras su
  // contenedor está oculto (display:none) — se inicializa la primera vez
  // que de verdad se muestra la sección de Flotilla.
  if (seccion === 'flotilla' && !DASH_FLOTILLA_MAPA_INICIALIZADO) {
    DASH_FLOTILLA_MAPA_INICIALIZADO = true;
    renderMapaFlotillaDashboard();
  }
}

async function abrirDashboard() {
  document.getElementById('menuScreen').style.display = 'none';
  document.getElementById('app').style.display = 'none';
  document.getElementById('proyectosScreen').style.display = 'none';
  document.getElementById('marketingScreen').style.display = 'none';
  document.getElementById('equiposScreen').style.display = 'none';
  document.getElementById('comprasScreen').style.display = 'none';
  document.getElementById('rhScreen').style.display = 'none';
  document.getElementById('reparacionesScreen').style.display = 'none';
  document.getElementById('entregasScreen').style.display = 'none';
  document.getElementById('checadorPrecioScreen').style.display = 'none';
  document.getElementById('dashboardScreen').style.display = 'block';
  DASH_FLOTILLA_MAPA_INICIALIZADO = false;
  if (SESION.usuario.rol !== 'master') {
    document.getElementById('whoamiDashboard').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol]}`;
    document.getElementById('btnDashboardVolver').style.display = 'inline-block';
  }
  const cont = document.getElementById('dashboardContenido');
  cont.innerHTML = '<p style="color:var(--muted); font-family:\\'JetBrains Mono\\',monospace; font-size:12px;">Cargando estadísticas...</p>';
  try {
    const d = await api('/api/dashboard');
    const puedeAutorizar = SESION.usuario.rol === 'master' || SESION.usuario.rol === 'admin';
    const puedeVerFlotilla = META.mis_permisos.acceso_entregas;
    let resumenVentasPv = null;
    if (puedeVerFlotilla) {
      try {
        resumenVentasPv = await api(`/api/dashboard/ventas-pv?fecha=${new Date().toISOString().slice(0, 10)}`);
      } catch (e) {
        resumenVentasPv = null; // si Microsip no está configurado o falla, simplemente no se muestra la tarjeta
      }
    }
    let resumenValorInventario = null;
    if (puedeVerFlotilla) {
      try {
        resumenValorInventario = await api('/api/dashboard/valor-inventario');
      } catch (e) {
        resumenValorInventario = null;
      }
    }
    let resumenSinMovimiento = null;
    if (puedeVerFlotilla) {
      try {
        resumenSinMovimiento = await api('/api/dashboard/sin-movimiento');
      } catch (e) {
        resumenSinMovimiento = null;
      }
    }
    let resumenValorInventarioVenta = null;
    if (puedeVerFlotilla) {
      try {
        resumenValorInventarioVenta = await api('/api/dashboard/valor-inventario-venta');
      } catch (e) {
        resumenValorInventarioVenta = null;
      }
    }
    let resumenDescuentosPv = null;
    if (puedeVerFlotilla) {
      try {
        resumenDescuentosPv = await api(`/api/dashboard/descuentos-pv?fecha=${new Date().toISOString().slice(0, 10)}`);
      } catch (e) {
        resumenDescuentosPv = null;
      }
    }
    cont.innerHTML = `
      ${puedeVerFlotilla ? `
        <div style="display:flex; gap:10px; margin-bottom:20px;">
          <button id="dashBtnFlotilla" class="secondary" style="flex:1; padding:12px; font-size:13px;" onclick="dashMostrarSeccion('flotilla')">🚚 Flotilla</button>
          <button id="dashBtnAuditoria" class="secondary" style="flex:1; padding:12px; font-size:13px;" onclick="dashMostrarSeccion('auditoria')">🔍 Auditoría</button>
        </div>
        <div id="dashSeccionFlotilla" style="display:none; margin-bottom:24px;">
          <h3 style="margin:0 0 8px;">📍 Flotilla en vivo</h3>
          <div id="dashFlotillaMsg" style="font-size:12px; color:var(--muted); margin-bottom:8px;">Cargando posiciones…</div>
          <div id="dashFlotillaMapa" style="width:100%; height:340px; border:1px solid rgba(155,157,159,0.3); border-radius:6px;"></div>
        </div>
        <div id="dashSeccionAuditoria" style="display:none; margin-bottom:24px;">
          <div class="dash-grid">
            ${resumenVentasPv ? `
              <div class="dash-tarjeta">
                <div id="dashResumenVentasPvCard">${contenidoTarjetaResumenVentasPv(resumenVentasPv)}</div>
                <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseVentasPvDashboard()">🔎 Ver desglose completo</button>
              </div>
            ` : ''}
            ${resumenValorInventario ? `
              <div class="dash-tarjeta">
                <div class="dash-tarjeta-header">
                  <span class="dash-icono">📦</span>
                  <div>
                    <div class="dash-titulo">Valor del inventario</div>
                    <div class="dash-total">$${resumenValorInventario.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
                  </div>
                </div>
                <div style="margin-top:10px;">
                  ${resumenValorInventario.por_sucursal.length ? resumenValorInventario.por_sucursal.map(s => `
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                      <span>${escapeHtml(s.sucursal)}</span>
                      <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                    </div>
                  `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con capas de costo activas.</p>`}
                </div>
                <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioDashboard()">🔎 Ver desglose completo</button>
              </div>
            ` : ''}
            ${resumenSinMovimiento ? `
              <div class="dash-tarjeta">
                <div class="dash-tarjeta-header">
                  <span class="dash-icono">🐌</span>
                  <div>
                    <div class="dash-titulo">Artículos sin movimiento</div>
                    <div class="dash-total">$${resumenSinMovimiento.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
                  </div>
                </div>
                <div style="margin-top:10px;">
                  ${resumenSinMovimiento.por_sucursal.length ? resumenSinMovimiento.por_sucursal.map(s => `
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                      <span>${escapeHtml(s.sucursal)}</span>
                      <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                    </div>
                  `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin artículos detectados sin movimiento.</p>`}
                </div>
                <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseSinMovimientoDashboard()">🔎 Ver desglose completo</button>
              </div>
            ` : ''}
            ${resumenValorInventarioVenta ? `
              <div class="dash-tarjeta">
                <div class="dash-tarjeta-header">
                  <span class="dash-icono">💲</span>
                  <div>
                    <div class="dash-titulo">Valor del inventario (precio de venta)</div>
                    <div class="dash-total">$${resumenValorInventarioVenta.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
                  </div>
                </div>
                <div style="margin-top:10px;">
                  ${resumenValorInventarioVenta.por_sucursal.length ? resumenValorInventarioVenta.por_sucursal.map(s => `
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                      <span>${escapeHtml(s.sucursal)}</span>
                      <span style="color:var(--text);">$${s.valor_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                    </div>
                  `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin inventario con precio de lista capturado.</p>`}
                </div>
                <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseInventarioVentaDashboard()">🔎 Ver desglose completo</button>
              </div>
            ` : ''}
            ${resumenDescuentosPv ? `
              <div class="dash-tarjeta">
                <div class="dash-tarjeta-header">
                  <span class="dash-icono">🏷️</span>
                  <div>
                    <div class="dash-titulo">Descuentos otorgados</div>
                    <div class="dash-total">Hoy — $${resumenDescuentosPv.total_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</div>
                  </div>
                </div>
                <div style="margin-top:10px;">
                  ${resumenDescuentosPv.por_sucursal.length ? resumenDescuentosPv.por_sucursal.map(s => `
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                      <span>${escapeHtml(s.sucursal)}</span>
                      <span style="color:var(--text);">$${s.descuento_total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                    </div>
                  `).join('') : `<p style="font-size:12px; color:var(--muted);">Sin descuentos registrados hoy.</p>`}
                </div>
                <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="abrirDesgloseDescuentosDashboard()">🔎 Ver desglose completo</button>
              </div>
            ` : ''}
          </div>
        </div>
      ` : ''}
      ${puedeAutorizar ? '<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>' : ''}
      <div class="dash-grid">
        ${tarjetaModuloDashboard('Tickets', '🎫', d.tickets.total, d.tickets.por_estado, 'var(--copper)', '/api/dashboard/tickets')}
        ${tarjetaModuloDashboard('Reparaciones', '🔧', d.reparaciones.total, d.reparaciones.por_estado, '#5B9BD5', '/api/dashboard/reparaciones')}
        ${tarjetaModuloDashboard('Proyectos', '📋', d.proyectos.total, d.proyectos.por_estado, '#70AD47', '/api/dashboard/proyectos')}
        ${tarjetaModuloDashboard('Equipos', '💻', d.equipos.total, d.equipos.por_estado, '#FFC000', '/api/dashboard/equipos')}
        <div class="dash-tarjeta">
          <div class="dash-tarjeta-header">
            <span class="dash-icono">🛒</span>
            <div>
              <div class="dash-titulo">Compras</div>
              <div class="dash-total">${d.compras.ciclos_total} ciclo(s) en total</div>
            </div>
          </div>
          <div class="dash-barras">
            ${Object.entries(d.compras.ciclos_por_estado).map(([estado, n]) => `
              <div class="dash-fila">
                <span class="dash-fila-label">${NOMBRES_ESTADO_DASHBOARD[estado] || estado}</span>
                <div class="dash-fila-barra-fondo"><div class="dash-fila-barra" style="width:${d.compras.ciclos_total > 0 ? Math.max(4, (n / d.compras.ciclos_total) * 100) : 0}%; background:#9B59B6;"></div></div>
                <span class="dash-fila-numero">${n}</span>
              </div>
            `).join('')}
          </div>
          <p style="font-size:12px; color:var(--muted); margin-top:10px;">${d.compras.pedidos_pendientes} pedido(s) en ciclos abiertos, esperando surtirse.</p>
          ${d.compras.por_sucursal && d.compras.por_sucursal.length ? `
            <div style="margin-top:12px; border-top:1px solid rgba(155,157,159,0.2); padding-top:10px;">
              <p style="font-size:11px; color:var(--muted); text-transform:uppercase; margin-bottom:6px;">Gasto por sucursal</p>
              ${d.compras.por_sucursal.map(s => `
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                  <span>${escapeHtml(s.sucursal)}</span>
                  <span style="color:var(--text);">$${s.total.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
                </div>
              `).join('')}
              <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:6px; font-weight:bold; border-top:1px solid rgba(155,157,159,0.2); padding-top:6px;">
                <span>Total general</span>
                <span>$${d.compras.precio_general.toLocaleString('es-MX', {minimumFractionDigits:2})}</span>
              </div>
            </div>
          ` : ''}
          <button class="secondary" style="width:100%; margin-top:14px; font-size:11px; padding:7px;" onclick="descargarReporte(this, '/api/dashboard/compras', 'compras', 'pdf')">📄 Descargar PDF de Compras</button>
        </div>
        ${tarjetaModuloDashboard('Recursos Humanos', '🩺', d.rh.total, d.rh.por_estado, '#E85D9E', '/api/dashboard/rh')}
      </div>
    `;
    if (puedeAutorizar) await renderAutorizacionesCompra();
    if (puedeVerFlotilla && resumenVentasPv) iniciarAutoRefrescoResumenVentasPv();
  } catch (e) {
    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;
  }
}'''


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO — asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if VIEJO in contenido:
        contenido = contenido.replace(VIEJO, NUEVO, 1)
    elif NUEVO in contenido:
        print(f"[{RUTA}] Ya estaba aplicado, no se hizo nada.")
        sys.exit(0)
    else:
        print(f"[{RUTA}] No se encontró el bloque esperado. El archivo pudo haber cambiado desde la última vez.")
        print("Avísale a Claude sin correr git add/commit todavía.")
        sys.exit(1)

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] Cambio aplicado.")
    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print("   git commit -m \"Dashboard: separar Flotilla y Auditoria en botones/secciones\"")
    print("   git push")


if __name__ == "__main__":
    main()
