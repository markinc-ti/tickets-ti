#!/usr/bin/env python3
"""
Cotizador de costos (Superadmin -> Cotizador -> "Otros servicios", donde
está el ítem "Cámaras de seguridad (CCTV)" con Cantidad + Precio unitario):
en pantalla ya se captura el precio unitario y la cantidad por separado,
pero al generar el PDF la tabla solo mostraba el TOTAL de cada línea
(precio unitario x cantidad ya multiplicado) -- el precio unitario en sí
no aparecía en ningún lado del PDF.

Pedido de David: que el precio unitario también salga en el PDF.

Fix: cuando la cotización tiene ítems con cantidad > 1 (columna "Cant."
visible), la tabla del PDF ahora trae una columna más -- "Precio unitario"
además de "Total" -- en vez de solo el total. Cuando ningún ítem tiene
cantidad > 1 (la mayoría de las cotizaciones de Sistema TI / Dental Suite),
la tabla se queda exactamente igual que antes (una sola columna "Precio"),
porque ahí unitario y total ya son lo mismo -- no hace falta duplicar la
columna.
"""

ARCHIVOS = {
    "frontend/cotizador_costos.html": [
        [
            '''  const activeMods = mods().filter(m=>m.on);
  const hayCantidades = activeMods.some(m => (m.cantidad||1) > 1);
  const rows = activeMods.map(m=>{
    const cant = m.cantidad||1;
    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';
    let precio = '';
    if(state.mode==='renta') precio = fmt(m.rent*cant)+'/mes';
    else if(state.mode==='venta') precio = fmt(m.setup*cant);
    else precio = fmt(m.setup*cant)+' + '+fmt(m.rent*cant)+'/mes';
    // Si hay cantidades, van en su propia columna -- ya no pegadas al nombre.
    const nombre = m.name + (!hayCantidades && cant>1 ? ` ×${cant}` : '');
    const descripcion = m.desc + (incluye? ('\\nIncluye: '+incluye):'');
    return hayCantidades ? [nombre, String(cant), descripcion, precio] : [nombre, descripcion, precio];
  });

  doc.autoTable({
    startY: y,
    head: hayCantidades ? [['Módulo','Cant.','Descripción','Precio']] : [['Módulo','Descripción','Precio']],
    body: rows,
    margin: { left: margin, right: margin },
    styles: { font:'helvetica', fontSize:8.5, cellPadding:6, textColor:[40,40,40], valign:'top' },
    headStyles: { fillColor:[216,25,47], textColor:255, fontStyle:'bold' },
    columnStyles: hayCantidades
      ? { 0:{cellWidth:100, fontStyle:'bold'}, 1:{cellWidth:36, halign:'center'}, 3:{cellWidth:90, halign:'right'} }
      : { 0:{cellWidth:110, fontStyle:'bold'}, 2:{cellWidth:90, halign:'right'} },
    alternateRowStyles: { fillColor:[250,249,247] },
    didDrawPage: dibujarMarcaAgua,
  });''',
            '''  const activeMods = mods().filter(m=>m.on);
  const hayCantidades = activeMods.some(m => (m.cantidad||1) > 1);
  const rows = activeMods.map(m=>{
    const cant = m.cantidad||1;
    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';
    let precioUnitario = '';
    if(state.mode==='renta') precioUnitario = fmt(m.rent)+'/mes';
    else if(state.mode==='venta') precioUnitario = fmt(m.setup);
    else precioUnitario = fmt(m.setup)+' + '+fmt(m.rent)+'/mes';
    let precio = '';
    if(state.mode==='renta') precio = fmt(m.rent*cant)+'/mes';
    else if(state.mode==='venta') precio = fmt(m.setup*cant);
    else precio = fmt(m.setup*cant)+' + '+fmt(m.rent*cant)+'/mes';
    // Si hay cantidades, van en su propia columna -- ya no pegadas al nombre.
    const nombre = m.name + (!hayCantidades && cant>1 ? ` ×${cant}` : '');
    const descripcion = m.desc + (incluye? ('\\nIncluye: '+incluye):'');
    return hayCantidades ? [nombre, String(cant), descripcion, precioUnitario, precio] : [nombre, descripcion, precio];
  });

  doc.autoTable({
    startY: y,
    head: hayCantidades ? [['Módulo','Cant.','Descripción','Precio unitario','Total']] : [['Módulo','Descripción','Precio']],
    body: rows,
    margin: { left: margin, right: margin },
    styles: { font:'helvetica', fontSize:8.5, cellPadding:6, textColor:[40,40,40], valign:'top' },
    headStyles: { fillColor:[216,25,47], textColor:255, fontStyle:'bold' },
    columnStyles: hayCantidades
      ? { 0:{cellWidth:90, fontStyle:'bold'}, 1:{cellWidth:34, halign:'center'}, 3:{cellWidth:82, halign:'right'}, 4:{cellWidth:82, halign:'right', fontStyle:'bold'} }
      : { 0:{cellWidth:110, fontStyle:'bold'}, 2:{cellWidth:90, halign:'right'} },
    alternateRowStyles: { fillColor:[250,249,247] },
    didDrawPage: dibujarMarcaAgua,
  });''',
        ],
    ],
}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    for ruta, cambios in ARCHIVOS.items():
        contenido = leer(ruta)
        original = contenido
        for viejo, nuevo in cambios:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                raise SystemExit(f"[ERROR] No se encontró el texto esperado en {ruta} -- puede que ya haya cambiado. Aborta sin tocar nada.")
            contenido = contenido.replace(viejo, nuevo, 1)
        if contenido != original:
            escribir(ruta, contenido)
            print(f"[OK] Actualizado: {ruta}")
        else:
            print(f"[OK] Ya estaba aplicado: {ruta}")

    print()
    print("Listo. Ahora corre:")
    print("  git add frontend/cotizador_costos.html")
    print('  git commit -m "Cotizador de costos: precio unitario tambien en el PDF, no solo el total"')
    print("  git push")


if __name__ == "__main__":
    main()
