# -*- coding: utf-8 -*-
"""
Cotizador de Superadmin — Otros servicios: campo de Cantidad que
multiplica el precio automáticamente

Antes, en la pestaña "Otros servicios" (cámaras, cerco eléctrico, app a
la medida, o cualquier ítem libre que agregues), el precio que ponías
era el total de la línea — si ibas a vender 4 cámaras tenías que
calcular tú el total y escribirlo. Ahora hay un campo "Cantidad" (solo
en esa pestaña; Sistema TI y Dental Suite quedan exactamente igual) y
el precio que pones es el UNITARIO: la vista previa, los totales y el
PDF ya multiplican precio unitario × cantidad solos.

Qué toca (todo en frontend/cotizador_costos.html):
1. Los 4 ítems por default de "Otros servicios" llevan cantidad:1, y se
   actualizó el texto de ayuda de cámaras/cerco.
2. renderModules(): nuevo campo "Cantidad" (solo si estás en la
   pestaña Otros servicios) + su listener; las etiquetas de precio
   dicen "unitario" en esa pestaña.
3. agregarItemPersonalizado(): los ítems libres nuevos también nacen
   con cantidad:1.
4. renderInternal(), renderPreview() y la generación del PDF
   (buildPdfBlob): los totales y el precio por línea ahora son
   precio × cantidad, y el nombre del ítem muestra "×N" cuando la
   cantidad es mayor a 1.
5. _fusionarModulosServidor(): al cargar una cotización ya guardada,
   también recupera la cantidad guardada de cada ítem.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_cotizador_otros_servicios_cantidad.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS['frontend/cotizador_costos.html'] = [
    # 1) Ítems por default de Otros servicios: cantidad:1 + texto de ayuda.
    [
        '''      { id:'camaras', name:'Cámaras de seguridad (CCTV)', desc:'Venta e instalación de cámaras de videovigilancia — edita cantidad/modelo directo en el precio.',
        on:true, custom:true, setup:0, rent:0, resources:[] },
      { id:'cerco', name:'Cerco eléctrico perimetral', desc:'Venta e instalación de cerco eléctrico — edita metros/zona directo en el precio.',
        on:true, custom:true, setup:0, rent:0, resources:[] },
      { id:'app-medida', name:'Desarrollo de app a la medida', desc:'Desarrollo de una aplicación o sistema a la medida para el cliente.',
        on:true, custom:true, setup:0, rent:0, resources:[] },
      { id:'mantenimiento-otros', name:'Mantenimiento / monitoreo', desc:'Servicio recurrente de mantenimiento o monitoreo remoto del sistema instalado.',
        on:false, custom:true, setup:0, rent:0, resources:[] },
''',
        '''      { id:'camaras', name:'Cámaras de seguridad (CCTV)', desc:'Venta e instalación de cámaras de videovigilancia — pon el precio unitario y la cantidad.',
        on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] },
      { id:'cerco', name:'Cerco eléctrico perimetral', desc:'Venta e instalación de cerco eléctrico — pon el precio por metro/zona y la cantidad.',
        on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] },
      { id:'app-medida', name:'Desarrollo de app a la medida', desc:'Desarrollo de una aplicación o sistema a la medida para el cliente.',
        on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] },
      { id:'mantenimiento-otros', name:'Mantenimiento / monitoreo', desc:'Servicio recurrente de mantenimiento o monitoreo remoto del sistema instalado.',
        on:false, custom:true, setup:0, rent:0, cantidad:1, resources:[] },
''',
    ],
    # 2) Campo "Cantidad" nuevo (solo pestaña Otros) + etiquetas "unitario".
    [
        '''      <div class="module-body">
        <div class="price-line"><span class="lbl">Precio de implementación (único)</span><span>$<input type="number" data-mod-setup="${i}" value="${m.setup}"></span></div>
        <div class="price-line"><span class="lbl">Renta mensual</span><span>$<input type="number" data-mod-rent="${i}" value="${m.rent}"></span></div>
''',
        '''      <div class="module-body">
        ${state.producto==='otros' ? `<div class="price-line"><span class="lbl">Cantidad</span><span><input type="number" min="1" step="1" data-mod-cantidad="${i}" value="${m.cantidad||1}" style="width:60px;"></span></div>` : ''}
        <div class="price-line"><span class="lbl">${state.producto==='otros' ? 'Precio unitario de implementación' : 'Precio de implementación (único)'}</span><span>$<input type="number" data-mod-setup="${i}" value="${m.setup}"></span></div>
        <div class="price-line"><span class="lbl">${state.producto==='otros' ? 'Renta mensual unitaria' : 'Renta mensual'}</span><span>$<input type="number" data-mod-rent="${i}" value="${m.rent}"></span></div>
        ${state.producto==='otros' ? `<p style="font-size:0.72rem; color:var(--gris-1); margin:2px 0 0;">El total de esta línea (precio unitario × cantidad) se ve en la vista previa de la derecha.</p>` : ''}
''',
    ],
    # 3) Listener del campo Cantidad.
    [
        '''  box.querySelectorAll('[data-mod-rent]').forEach(el=>el.addEventListener('input', e=>{
    mods()[+e.target.dataset.modRent].rent = parseFloat(e.target.value)||0; renderAll(false);
  }));
  box.querySelectorAll('[data-res]').forEach(el=>el.addEventListener('change', e=>{
''',
        '''  box.querySelectorAll('[data-mod-rent]').forEach(el=>el.addEventListener('input', e=>{
    mods()[+e.target.dataset.modRent].rent = parseFloat(e.target.value)||0; renderAll(false);
  }));
  box.querySelectorAll('[data-mod-cantidad]').forEach(el=>el.addEventListener('input', e=>{
    mods()[+e.target.dataset.modCantidad].cantidad = Math.max(1, parseInt(e.target.value, 10)||1); renderAll(false);
  }));
  box.querySelectorAll('[data-res]').forEach(el=>el.addEventListener('change', e=>{
''',
    ],
    # 4) Ítems libres nuevos también nacen con cantidad:1.
    [
        '''  mods().push({ id:'custom_'+Date.now(), name:'Nuevo ítem', desc:'', on:true, custom:true, setup:0, rent:0, resources:[] });
''',
        '''  mods().push({ id:'custom_'+Date.now(), name:'Nuevo ítem', desc:'', on:true, custom:true, setup:0, rent:0, cantidad:1, resources:[] });
''',
    ],
    # 5) renderInternal(): totales × cantidad.
    [
        '''  const totalRent = activeMods.reduce((a,m)=>a+m.rent,0);
  const totalSetup = activeMods.reduce((a,m)=>a+m.setup,0);
  const margen = totalRent > 0 ? Math.round(((totalRent-totalCost)/totalRent)*100) : 0;
''',
        '''  const totalRent = activeMods.reduce((a,m)=>a+m.rent*(m.cantidad||1),0);
  const totalSetup = activeMods.reduce((a,m)=>a+m.setup*(m.cantidad||1),0);
  const margen = totalRent > 0 ? Math.round(((totalRent-totalCost)/totalRent)*100) : 0;
''',
    ],
    # 6) renderPreview(): totales, precio por línea y "×N" en el nombre.
    [
        '''  const activeMods = mods().filter(m=>m.on);
  const totalSetup = activeMods.reduce((a,m)=>a+m.setup,0);
  const totalRent = activeMods.reduce((a,m)=>a+m.rent,0);

  const modsHtml = activeMods.map(m => `
    <div class="doc-mod">
      <div class="doc-mod-head">
        <div><div class="nm">${m.name}</div><div class="ds">${m.desc}</div></div>
        <div class="pr">
          ${state.mode!=='venta' ? `<div class="rent">${fmt(m.rent)}/mes</div>`:''}
          ${state.mode!=='renta' ? `<div class="setup">${fmt(m.setup)} implementación</div>`:''}
        </div>
      </div>
''',
        '''  const activeMods = mods().filter(m=>m.on);
  const totalSetup = activeMods.reduce((a,m)=>a+m.setup*(m.cantidad||1),0);
  const totalRent = activeMods.reduce((a,m)=>a+m.rent*(m.cantidad||1),0);

  const modsHtml = activeMods.map(m => `
    <div class="doc-mod">
      <div class="doc-mod-head">
        <div><div class="nm">${m.name}${m.cantidad>1?` ×${m.cantidad}`:''}</div><div class="ds">${m.desc}</div></div>
        <div class="pr">
          ${state.mode!=='venta' ? `<div class="rent">${fmt(m.rent*(m.cantidad||1))}/mes</div>`:''}
          ${state.mode!=='renta' ? `<div class="setup">${fmt(m.setup*(m.cantidad||1))} implementación</div>`:''}
        </div>
      </div>
''',
    ],
    # 7) buildPdfBlob(): renglones y totales × cantidad.
    [
        '''  const activeMods = mods().filter(m=>m.on);
  const rows = activeMods.map(m=>{
    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';
    let precio = '';
    if(state.mode==='renta') precio = fmt(m.rent)+'/mes';
    else if(state.mode==='venta') precio = fmt(m.setup);
    else precio = fmt(m.setup)+' + '+fmt(m.rent)+'/mes';
    return [m.name, m.desc + (incluye? ('\\nIncluye: '+incluye):''), precio];
  });
''',
        '''  const activeMods = mods().filter(m=>m.on);
  const rows = activeMods.map(m=>{
    const cant = m.cantidad||1;
    const incluye = state.showResources ? m.resources.filter(r=>r.on).map(r=>r.name).join(', ') : '';
    let precio = '';
    if(state.mode==='renta') precio = fmt(m.rent*cant)+'/mes';
    else if(state.mode==='venta') precio = fmt(m.setup*cant);
    else precio = fmt(m.setup*cant)+' + '+fmt(m.rent*cant)+'/mes';
    return [m.name + (cant>1?` ×${cant}`:''), m.desc + (incluye? ('\\nIncluye: '+incluye):''), precio];
  });
''',
    ],
    # 8) buildPdfBlob(): totales finales × cantidad.
    [
        '''  const totalSetup = activeMods.reduce((a,m)=>a+m.setup,0);
  const totalRent = activeMods.reduce((a,m)=>a+m.rent,0);
  doc.setDrawColor(20,20,20); doc.setLineWidth(1); doc.line(margin, y, pageW-margin, y);
''',
        '''  const totalSetup = activeMods.reduce((a,m)=>a+m.setup*(m.cantidad||1),0);
  const totalRent = activeMods.reduce((a,m)=>a+m.rent*(m.cantidad||1),0);
  doc.setDrawColor(20,20,20); doc.setLineWidth(1); doc.line(margin, y, pageW-margin, y);
''',
    ],
    # 9) _fusionarModulosServidor(): recuperar la cantidad guardada.
    [
        '''    return Object.assign({}, def, {
      on: def.locked?true:!!g.on, setup: (g.setup ?? def.setup), rent: (g.rent ?? def.rent), resources,
      name: (def.custom && g.name) ? g.name : def.name,
      desc: (def.custom && g.desc!==undefined) ? g.desc : def.desc,
    });
''',
        '''    return Object.assign({}, def, {
      on: def.locked?true:!!g.on, setup: (g.setup ?? def.setup), rent: (g.rent ?? def.rent),
      cantidad: (g.cantidad ?? def.cantidad ?? 1), resources,
      name: (def.custom && g.name) ? g.name : def.name,
      desc: (def.custom && g.desc!==undefined) ? g.desc : def.desc,
    });
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
    print("   git add frontend/cotizador_costos.html")
    print('   git commit -m "Cotizador Otros servicios: campo de cantidad que multiplica el precio"')
    print("   git push")


if __name__ == "__main__":
    main()
