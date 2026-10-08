#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador de sistema TI: varios ajustes pedidos sobre lo ya aplicado
(fix_cotizador_costos_datos_pago_global.py):

1. Columna de Cantidad en la tabla del PDF -- solo aparece si de verdad
   pusiste una cantidad mayor a 1 en algun modulo (modo "Otros
   servicios"); si no, el PDF sale exactamente igual que hasta ahora.
   En la vista previa en pantalla, la cantidad ya no va pegada al
   nombre del modulo, sino en una etiqueta aparte.

2. "+ Nueva cotizacion" ahora tambien deja elegir un cliente al que ya
   le hayas cotizado antes, para partir de esa cotizacion (mismos
   modulos, precios y textos) en vez de empezar en blanco -- antes esto
   solo se podia hacer desde el boton 📋 de la lista, ahora tambien
   esta en el flujo de creacion.

3. En el PDF: el logo va mas grande y a la izquierda, el texto que
   estaba pegado debajo del logo ("SISTEMAS Y SOFTWARE A LA MEDIDA")
   ahora va centrado en la pagina, y se agrega tu mismo logo como marca
   de agua muy tenue de fondo en todo el documento.

4. En el PDF y en la vista previa: el total ahora se desglosa en
   Subtotal / IVA (16%) / Total a pagar -- el total que paga el cliente
   NO cambia (los precios ya incluian el IVA, igual que en el resto de
   la app), solo se desglosa.

Que cambia:
- frontend/cotizador_costos.html (los puntos 1, 3 y 4)
- frontend/index.html (el punto 2, en el panel de superadmin)
"""
import sys

ARCHIVOS = {
    'frontend/cotizador_costos.html': [
        [
            '  .doc-notes{ margin-top:22px; font-size:0.75rem; color:var(--gris-1); line-height:1.6; white-space:pre-wrap; }',
            '  .qty-badge{ display:inline-block; font-size:0.68rem; font-weight:700; color:var(--rojo); background:color-mix(in srgb, var(--rojo) 10%, transparent); padding:1px 7px; border-radius:20px; margin-left:5px; vertical-align:1px; }\n  .doc-notes{ margin-top:22px; font-size:0.75rem; color:var(--gris-1); line-height:1.6; white-space:pre-wrap; }',
        ],
        [
            '        <div><div class="nm">${m.name}${m.cantidad>1?` ×${m.cantidad}`:\'\'}</div><div class="ds">${m.desc}</div></div>',
            '        <div><div class="nm">${m.name}${m.cantidad>1?` <span class="qty-badge">×${m.cantidad}</span>`:\'\'}</div><div class="ds">${m.desc}</div></div>',
        ],
        [
            '  let totalsHtml = \'\';\n  if(state.mode===\'renta\'){\n    totalsHtml = `<div class="trow big"><span>Renta mensual total</span><span class="v">${fmt(totalRent)}/mes</span></div>`;\n  } else if(state.mode===\'venta\'){\n    totalsHtml = `<div class="trow big"><span>Inversión total</span><span class="v">${fmt(totalSetup)}</span></div>`;\n  } else {\n    totalsHtml = `\n      <div class="trow"><span>Implementación (pago único)</span><span>${fmt(totalSetup)}</span></div>\n      <div class="trow big"><span>Renta mensual</span><span class="v">${fmt(totalRent)}/mes</span></div>`;\n  }',
            '  let totalsHtml = \'\';\n  if(state.mode===\'renta\'){\n    const subtotal = totalRent/1.16, iva = totalRent-subtotal;\n    totalsHtml = `\n      <div class="trow"><span>Subtotal</span><span>${fmt(subtotal)}/mes</span></div>\n      <div class="trow"><span>IVA (16%)</span><span>${fmt(iva)}/mes</span></div>\n      <div class="trow big"><span>Renta mensual total</span><span class="v">${fmt(totalRent)}/mes</span></div>`;\n  } else if(state.mode===\'venta\'){\n    const subtotal = totalSetup/1.16, iva = totalSetup-subtotal;\n    totalsHtml = `\n      <div class="trow"><span>Subtotal</span><span>${fmt(subtotal)}</span></div>\n      <div class="trow"><span>IVA (16%)</span><span>${fmt(iva)}</span></div>\n      <div class="trow big"><span>Inversión total</span><span class="v">${fmt(totalSetup)}</span></div>`;\n  } else {\n    const subtotal = totalRent/1.16, iva = totalRent-subtotal;\n    totalsHtml = `\n      <div class="trow"><span>Implementación (pago único)</span><span>${fmt(totalSetup)}</span></div>\n      <div class="trow"><span>Subtotal</span><span>${fmt(subtotal)}/mes</span></div>\n      <div class="trow"><span>IVA (16%)</span><span>${fmt(iva)}/mes</span></div>\n      <div class="trow big"><span>Renta mensual</span><span class="v">${fmt(totalRent)}/mes</span></div>`;\n  }',
        ],
        [
            "  const { jsPDF } = window.jspdf;\n  const doc = new jsPDF({ unit:'pt', format:'letter' });\n  const pageW = doc.internal.pageSize.getWidth();\n  const margin = 48;\n  let y = 56;",
            "  const { jsPDF } = window.jspdf;\n  const doc = new jsPDF({ unit:'pt', format:'letter' });\n  const pageW = doc.internal.pageSize.getWidth();\n  const pageH = doc.internal.pageSize.getHeight();\n  const margin = 48;\n  let y = 56;\n\n  function dibujarMarcaAgua(){\n    const wmW = 260, wmH = wmW / LOGO_RATIO;\n    doc.saveGraphicsState();\n    doc.setGState(new doc.GState({ opacity: 0.06 }));\n    doc.addImage(LOGO_DATA_URI, 'PNG', (pageW - wmW) / 2, (pageH - wmH) / 2, wmW, wmH);\n    doc.restoreGraphicsState();\n  }",
        ],
        [
            "  const logoH = 26, logoW = logoH * LOGO_RATIO;\n  doc.addImage(LOGO_DATA_URI, 'PNG', margin, y - 20, logoW, logoH);\n  doc.setFont('helvetica','normal'); doc.setFontSize(7.5); doc.setTextColor(116,118,122);\n  doc.text(marca, margin, y + 11);\n\n  doc.setFontSize(9);\n  doc.text('Folio: ' + folio, pageW - margin, y - 6, { align:'right' });\n  doc.text(fechaFmt, pageW - margin, y + 8, { align:'right' });\n\n  y += 34;",
            "  const logoH = 42, logoW = logoH * LOGO_RATIO;\n  doc.addImage(LOGO_DATA_URI, 'PNG', margin, y - 26, logoW, logoH);\n  doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(116,118,122);\n  doc.text(marca, pageW / 2, y - 2, { align:'center' });\n\n  doc.setFontSize(9);\n  doc.text('Folio: ' + folio, pageW - margin, y - 6, { align:'right' });\n  doc.text(fechaFmt, pageW - margin, y + 8, { align:'right' });\n\n  y += 44;",
        ],
        [
            "  const activeMods = mods().filter(m=>m.on);\n  const rows = activeMods.map(m=>{\n    const cant = m.cantidad||1;\n    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';\n    let precio = '';\n    if(state.mode==='renta') precio = fmt(m.rent*cant)+'/mes';\n    else if(state.mode==='venta') precio = fmt(m.setup*cant);\n    else precio = fmt(m.setup*cant)+' + '+fmt(m.rent*cant)+'/mes';\n    return [m.name + (cant>1?` ×${cant}`:''), m.desc + (incluye? ('\\nIncluye: '+incluye):''), precio];\n  });\n\n  doc.autoTable({\n    startY: y,\n    head: [['Módulo','Descripción','Precio']],\n    body: rows,\n    margin: { left: margin, right: margin },\n    styles: { font:'helvetica', fontSize:8.5, cellPadding:6, textColor:[40,40,40], valign:'top' },\n    headStyles: { fillColor:[216,25,47], textColor:255, fontStyle:'bold' },\n    columnStyles: { 0:{cellWidth:110, fontStyle:'bold'}, 2:{cellWidth:90, halign:'right'} },\n    alternateRowStyles: { fillColor:[250,249,247] },\n  });",
            "  const activeMods = mods().filter(m=>m.on);\n  const hayCantidades = activeMods.some(m => (m.cantidad||1) > 1);\n  const rows = activeMods.map(m=>{\n    const cant = m.cantidad||1;\n    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';\n    let precio = '';\n    if(state.mode==='renta') precio = fmt(m.rent*cant)+'/mes';\n    else if(state.mode==='venta') precio = fmt(m.setup*cant);\n    else precio = fmt(m.setup*cant)+' + '+fmt(m.rent*cant)+'/mes';\n    // Si hay cantidades, van en su propia columna -- ya no pegadas al nombre.\n    const nombre = m.name + (!hayCantidades && cant>1 ? ` ×${cant}` : '');\n    const descripcion = m.desc + (incluye? ('\\nIncluye: '+incluye):'');\n    return hayCantidades ? [nombre, String(cant), descripcion, precio] : [nombre, descripcion, precio];\n  });\n\n  doc.autoTable({\n    startY: y,\n    head: hayCantidades ? [['Módulo','Cant.','Descripción','Precio']] : [['Módulo','Descripción','Precio']],\n    body: rows,\n    margin: { left: margin, right: margin },\n    styles: { font:'helvetica', fontSize:8.5, cellPadding:6, textColor:[40,40,40], valign:'top' },\n    headStyles: { fillColor:[216,25,47], textColor:255, fontStyle:'bold' },\n    columnStyles: hayCantidades\n      ? { 0:{cellWidth:100, fontStyle:'bold'}, 1:{cellWidth:36, halign:'center'}, 3:{cellWidth:90, halign:'right'} }\n      : { 0:{cellWidth:110, fontStyle:'bold'}, 2:{cellWidth:90, halign:'right'} },\n    alternateRowStyles: { fillColor:[250,249,247] },\n    didDrawPage: dibujarMarcaAgua,\n  });",
        ],
        [
            "  doc.setFont('helvetica','normal'); doc.setFontSize(10); doc.setTextColor(60,60,60);\n  if(state.mode==='ambas'){\n    doc.text('Implementación (pago único)', margin, y);\n    doc.text(fmt(totalSetup), pageW-margin, y, { align:'right' });\n    y += 20;\n  }\n  doc.setFont('helvetica','bold'); doc.setFontSize(14); doc.setTextColor(216,25,47);\n  const totalLabel = state.mode==='venta' ? 'Inversión total' : 'Renta mensual total';\n  const totalValue = state.mode==='venta' ? fmt(totalSetup) : fmt(totalRent)+'/mes';\n  doc.text(totalLabel, margin, y);\n  doc.text(totalValue, pageW-margin, y, { align:'right' });\n  y += 26;",
            "  doc.setFont('helvetica','normal'); doc.setFontSize(10); doc.setTextColor(60,60,60);\n  if(state.mode==='ambas'){\n    doc.text('Implementación (pago único)', margin, y);\n    doc.text(fmt(totalSetup), pageW-margin, y, { align:'right' });\n    y += 20;\n  }\n\n  // Los precios ya incluyen el 16% de IVA (igual que en el resto de la\n  // app) -- aqui solo se desglosa el total ya conocido, no se le suma nada.\n  const totalPrincipal = state.mode==='venta' ? totalSetup : totalRent;\n  const sufijoPrincipal = state.mode==='venta' ? '' : '/mes';\n  const subtotalPrincipal = totalPrincipal / 1.16;\n  const ivaPrincipal = totalPrincipal - subtotalPrincipal;\n  doc.text('Subtotal', margin, y);\n  doc.text(fmt(subtotalPrincipal) + sufijoPrincipal, pageW-margin, y, { align:'right' });\n  y += 15;\n  doc.text('IVA (16%)', margin, y);\n  doc.text(fmt(ivaPrincipal) + sufijoPrincipal, pageW-margin, y, { align:'right' });\n  y += 18;\n\n  doc.setFont('helvetica','bold'); doc.setFontSize(14); doc.setTextColor(216,25,47);\n  const totalLabel = state.mode==='venta' ? 'Inversión total' : 'Renta mensual total';\n  const totalValue = state.mode==='venta' ? fmt(totalSetup) : fmt(totalRent)+'/mes';\n  doc.text(totalLabel, margin, y);\n  doc.text(totalValue, pageW-margin, y, { align:'right' });\n  y += 26;",
        ],
    ],
    'frontend/index.html': [
        [
            'let EMPRESAS_CACHE = [];',
            'let EMPRESAS_CACHE = [];\nlet COTIZACIONES_CACHE = [];',
        ],
        [
            "async function renderCotizadorSuperadmin() {\n  const filas = await api('/api/superadmin/cotizaciones');\n  const rentaGlobal = filas.reduce((a, f) => a + f.renta_mensual, 0);",
            "async function renderCotizadorSuperadmin() {\n  const filas = await api('/api/superadmin/cotizaciones');\n  COTIZACIONES_CACHE = filas;\n  const rentaGlobal = filas.reduce((a, f) => a + f.renta_mensual, 0);",
        ],
        [
            '    <div class="field"><label>Nombre del cliente/prospecto</label><input id="nc_nombre" placeholder="ej. Juan Pérez / Ferretería La Económica" /></div>\n    <button class="primary" style="width:100%;" onclick="crearCotizacionUI(this)">Crear y abrir</button>\n    <div id="ncError" class="error-msg"></div>\n  `;\n}',
            '    <div class="field"><label>Nombre del cliente/prospecto</label><input id="nc_nombre" placeholder="ej. Juan Pérez / Ferretería La Económica" /></div>\n    <div class="field"><label>¿Ya le habías cotizado antes? (opcional)</label>\n      <select id="nc_clonar_de">\n        <option value="">— Empezar en blanco —</option>\n        ${COTIZACIONES_CACHE.map(f => `<option value="${f.id}">${escapeHtml(f.nombre_cliente)}${f.empresa_nombre ? \' — \' + escapeHtml(f.empresa_nombre) : \'\'}</option>`).join(\'\')}\n      </select>\n      <p style="font-size:11px; color:var(--muted); margin:4px 0 0;">Si eliges uno, se copian sus módulos, precios y textos — solo ajusta lo que cambie.</p>\n    </div>\n    <button class="primary" style="width:100%;" onclick="crearCotizacionUI(this)">Crear y abrir</button>\n    <div id="ncError" class="error-msg"></div>\n  `;\n}',
        ],
        [
            "async function crearCotizacionUI(boton) {\n  const payload = {\n    empresa_id: document.getElementById('nc_empresa').value ? parseInt(document.getElementById('nc_empresa').value, 10) : null,\n    nombre_cliente: document.getElementById('nc_nombre').value.trim() || null,\n  };\n  if (!payload.empresa_id && !payload.nombre_cliente) {\n    document.getElementById('ncError').textContent = 'Ponle un nombre o vincúlala a una empresa';\n    return;\n  }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const { id } = await api('/api/superadmin/cotizaciones', { method: 'POST', body: JSON.stringify(payload) });\n      window.open(`/cotizador-costos.html?cotizacion_id=${id}`, '_blank');\n      cerrarModal();\n      await abrirCotizadorSuperadmin();\n    } catch (e) {\n      document.getElementById('ncError').textContent = e.message;\n    }\n  });\n}",
            "async function crearCotizacionUI(boton) {\n  const payload = {\n    empresa_id: document.getElementById('nc_empresa').value ? parseInt(document.getElementById('nc_empresa').value, 10) : null,\n    nombre_cliente: document.getElementById('nc_nombre').value.trim() || null,\n  };\n  const clonarDeId = document.getElementById('nc_clonar_de') ? document.getElementById('nc_clonar_de').value : '';\n  if (!payload.empresa_id && !payload.nombre_cliente) {\n    document.getElementById('ncError').textContent = 'Ponle un nombre o vincúlala a una empresa';\n    return;\n  }\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      const { id } = await api('/api/superadmin/cotizaciones', { method: 'POST', body: JSON.stringify(payload) });\n      if (clonarDeId) {\n        const origen = await api(`/api/superadmin/cotizaciones/${clonarDeId}`);\n        await api(`/api/superadmin/cotizaciones/${id}`, { method: 'PUT', body: JSON.stringify({ ...payload, config: origen.config || {} }) });\n      }\n      window.open(`/cotizador-costos.html?cotizacion_id=${id}`, '_blank');\n      cerrarModal();\n      await abrirCotizadorSuperadmin();\n    } catch (e) {\n      document.getElementById('ncError').textContent = e.message;\n    }\n  });\n}",
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
    print("    git add frontend/cotizador_costos.html frontend/index.html")
    print('    git commit -m "Cotizador de sistema TI: cantidad en tabla, clonar cliente anterior, logo/marca de agua y desglose IVA"')
    print("    git push")


if __name__ == "__main__":
    main()
