#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador (Superadmin) — nueva sección "Acta de entrega" para generar,
con un clic, el documento que hoy David arma a mano en Word cada vez que
entrega un sistema instalado (cámaras, acceso vehicular, cerco eléctrico,
etc.) bajo "Otros servicios".

Pedido de David (con dos actas de entrega reales como ejemplo:
ENTREGA_PLATINO_ACCESO_VEHICULAR.docx y Copia_de_entrega_adriatico.pdf):
"esto es para el superadmin al hacer cotizacion tambien hago entregas con
estos documentos, los podria simplificar y tambien hacer que sean
automatizados y no es para todas las cotizacion y que se hagan que tenga
la facultad de elegir a quien darsela y a quien no".

Cómo quedó (confirmado con David):
- Va dentro del Cotizador de Superadmin (frontend/cotizador_costos.html),
  que ya es donde cotiza cámaras/cerco eléctrico bajo "Otros servicios".
- Nueva sección "Acta de entrega (opcional)" con un interruptor apagado
  por default -- SOLO se activa (y solo se piden/guardan sus datos) en
  las cotizaciones donde David decide que sí hay una entrega física. El
  resto de sus cotizaciones (software, prospectos sin instalación, etc.)
  no se ven afectadas en nada.
- Cuando está activo: unos cuantos campos (tipo de sistema, fecha, ciudad,
  lugar, meses de garantía de equipo/instalación, proveedor, y la lista
  de equipos como texto libre -- igual que como ya la escribe hoy, una
  línea por artículo) más un botón "Descargar acta de entrega (PDF)".
- Todo lo que YA es texto fijo en sus dos documentos reales (exclusiones
  de garantía, recomendaciones de mantenimiento, la carta de
  presentación, los bloques de firma) queda automatizado dentro del PDF
  -- David ya no lo vuelve a escribir cada vez.
- El PDF se genera 100% en el navegador (con la misma librería jsPDF que
  ya usa el botón "Descargar cotización en PDF" de esta misma página),
  así que no se toca nada del backend ni de las demás pantallas de la
  app -- cero riesgo de romper otra cosa.
- Los datos de la entrega se guardan junto con el resto de la cotización
  (dentro de su "config", como ya se guarda todo lo demás en este
  Cotizador), así que "Guardar en el sistema" también guarda esto.

Qué toca:
- frontend/cotizador_costos.html (único archivo -- no toca backend/).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_cotizador_acta_entrega.py
"""
import sys

ARCHIVOS = {
    'frontend/cotizador_costos.html': [
        # 1) Sección nueva en el panel de configuración (después de "Datos de pago").
        [
            '''    <button class="add-resource" style="width:100%; text-align:center; padding:8px;" id="btn-guardar-datos-pago">Guardar datos de pago (aplica a todas tus cotizaciones)</button>
    <div class="hint" id="datos-pago-hint"></div>

    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>''',
            '''    <button class="add-resource" style="width:100%; text-align:center; padding:8px;" id="btn-guardar-datos-pago">Guardar datos de pago (aplica a todas tus cotizaciones)</button>
    <div class="hint" id="datos-pago-hint"></div>

    <h2 class="section-title"><span class="n">07</span>Acta de entrega (opcional)</h2>
    <p style="font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;">Solo para las cotizaciones donde también instalas equipo físico (cámaras, acceso vehicular, cerco eléctrico, etc.) -- actívalo nada más en esas, no en todas.</p>
    <div class="toggle-row">
      <div class="lbl">Generar acta de entrega para esta cotización<small>Apagado por default -- si está apagado, no se pide ni se guarda nada de esto</small></div>
      <label class="switch"><input type="checkbox" id="t-entrega"><span class="slider"></span></label>
    </div>
    <div id="entrega-fields" style="display:none;">
      <div class="row-2">
        <label class="field"><span class="lbl">Sistema entregado</span><input type="text" id="c-entrega-tipo" placeholder="Ej. Sistema de CCTV, Acceso vehicular, Cerco eléctrico"></label>
        <label class="field"><span class="lbl">Fecha de entrega</span><input type="date" id="c-entrega-fecha"></label>
      </div>
      <div class="row-2">
        <label class="field"><span class="lbl">Ciudad</span><input type="text" id="c-entrega-ciudad" placeholder="Ej. Puebla"></label>
        <label class="field"><span class="lbl">Lugar</span><input type="text" id="c-entrega-lugar" placeholder="Ej. Coronango"></label>
      </div>
      <div class="row-2">
        <label class="field"><span class="lbl">Garantía de equipo (meses)</span><input type="number" id="c-entrega-garantia-equipo" min="0" value="6"></label>
        <label class="field"><span class="lbl">Garantía de instalación (meses)</span><input type="number" id="c-entrega-garantia-instalacion" min="0" value="1"></label>
      </div>
      <label class="field"><span class="lbl">Proveedor (quien entrega)</span><input type="text" id="c-entrega-proveedor" placeholder="Tu nombre"></label>
      <label class="field"><span class="lbl">Equipos y materiales entregados</span>
        <textarea id="c-entrega-equipos" placeholder="Uno por línea, tal como ya lo escribes hoy, ej.:&#10;1 DVR 32 CANALES DAHUA DH-XVR5832S&#10;28 CÁMARAS DAHUA HFW1200T-36&#10;1 GABINETE TIPO RACK 6 UNIDADES"></textarea>
      </label>
    </div>

    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>''',
        ],
        # 2) Botón de descarga, junto al de la cotización.
        [
            '''    <button class="download-btn" id="btn-pdf">Descargar cotización en PDF</button>
    <div class="hint" id="pdf-hint">"Guardar" deja esta configuración ligada a la empresa; el PDF es lo que le compartes al cliente.</div>''',
            '''    <button class="download-btn" id="btn-pdf">Descargar cotización en PDF</button>
    <button class="download-btn" id="btn-entrega-pdf" style="display:none;">Descargar acta de entrega (PDF)</button>
    <div class="hint" id="pdf-hint">"Guardar" deja esta configuración ligada a la empresa; el PDF es lo que le compartes al cliente.</div>''',
        ],
        # 3) Cargar los datos guardados de la entrega (dentro de _cargarDesdeServidor).
        [
            '''      if(cli.notas) document.getElementById('c-notas').value = cli.notas;
      if(guardado.showResources !== undefined){ state.showResources = guardado.showResources; document.getElementById('t-recursos').checked = guardado.showResources; }''',
            '''      if(cli.notas) document.getElementById('c-notas').value = cli.notas;
      const ent = guardado.entrega || {};
      if(ent.activa){
        document.getElementById('t-entrega').checked = true;
        document.getElementById('entrega-fields').style.display = 'block';
        document.getElementById('btn-entrega-pdf').style.display = 'block';
      }
      if(ent.tipo) document.getElementById('c-entrega-tipo').value = ent.tipo;
      if(ent.fecha) document.getElementById('c-entrega-fecha').value = ent.fecha;
      if(ent.ciudad) document.getElementById('c-entrega-ciudad').value = ent.ciudad;
      if(ent.lugar) document.getElementById('c-entrega-lugar').value = ent.lugar;
      if(ent.garantiaEquipo !== undefined) document.getElementById('c-entrega-garantia-equipo').value = ent.garantiaEquipo;
      if(ent.garantiaInstalacion !== undefined) document.getElementById('c-entrega-garantia-instalacion').value = ent.garantiaInstalacion;
      if(ent.proveedor) document.getElementById('c-entrega-proveedor').value = ent.proveedor;
      if(ent.equipos) document.getElementById('c-entrega-equipos').value = ent.equipos;
      if(guardado.showResources !== undefined){ state.showResources = guardado.showResources; document.getElementById('t-recursos').checked = guardado.showResources; }''',
        ],
        # 4) Guardar los datos de la entrega junto con el resto de la cotización.
        [
            '''    showResources: state.showResources,
    showGrowth: state.showGrowth,
  };
  const payload = {''',
            '''    showResources: state.showResources,
    showGrowth: state.showGrowth,
    entrega: {
      activa: document.getElementById('t-entrega').checked,
      tipo: document.getElementById('c-entrega-tipo').value,
      fecha: document.getElementById('c-entrega-fecha').value,
      ciudad: document.getElementById('c-entrega-ciudad').value,
      lugar: document.getElementById('c-entrega-lugar').value,
      garantiaEquipo: parseInt(document.getElementById('c-entrega-garantia-equipo').value, 10) || 0,
      garantiaInstalacion: parseInt(document.getElementById('c-entrega-garantia-instalacion').value, 10) || 0,
      proveedor: document.getElementById('c-entrega-proveedor').value,
      equipos: document.getElementById('c-entrega-equipos').value,
    },
  };
  const payload = {''',
        ],
        # 5) Interruptor + generador de PDF del acta + botón, después del handler de btn-pdf.
        [
            '''document.getElementById('btn-pdf').addEventListener('click', async () => {
  const btn = document.getElementById('btn-pdf');
  const hint = document.getElementById('pdf-hint');
  const original = btn.textContent;
  btn.disabled = true; btn.textContent = 'Generando…';
  try{
    const blob = await buildPdfBlob();
    const folio = (document.getElementById('c-folio').value || 'cotizacion').replace(/[^a-z0-9\\-]/gi,'_');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = folio + '.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url), 4000);
    hint.textContent = 'PDF descargado.';
  } catch(e){
    hint.textContent = 'Ocurrió un error generando el PDF.';
    console.error(e);
  } finally {
    btn.disabled = false; btn.textContent = original;
  }
});''',
            '''document.getElementById('btn-pdf').addEventListener('click', async () => {
  const btn = document.getElementById('btn-pdf');
  const hint = document.getElementById('pdf-hint');
  const original = btn.textContent;
  btn.disabled = true; btn.textContent = 'Generando…';
  try{
    const blob = await buildPdfBlob();
    const folio = (document.getElementById('c-folio').value || 'cotizacion').replace(/[^a-z0-9\\-]/gi,'_');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = folio + '.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url), 4000);
    hint.textContent = 'PDF descargado.';
  } catch(e){
    hint.textContent = 'Ocurrió un error generando el PDF.';
    console.error(e);
  } finally {
    btn.disabled = false; btn.textContent = original;
  }
});

// ==================================================================
// ---- Acta de entrega -- se activa por cotización con el interruptor,
// se guarda junto con el resto de "config", y el PDF se arma 100% en
// el navegador con jsPDF (igual que la cotización) para no depender de
// nada del backend.
// ==================================================================

document.getElementById('t-entrega').addEventListener('change', function(){
  const on = this.checked;
  document.getElementById('entrega-fields').style.display = on ? 'block' : 'none';
  document.getElementById('btn-entrega-pdf').style.display = on ? 'block' : 'none';
});

async function buildEntregaPdfBlob(){
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit:'pt', format:'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 48;
  const bottomLimit = pageH - 60;
  let y = 56;

  const cliente = document.getElementById('c-empresa').value || 'Cliente';
  const folio = document.getElementById('c-folio').value || 'COT-SW-0001';
  const tipo = document.getElementById('c-entrega-tipo').value || 'sistema instalado';
  const fecha = document.getElementById('c-entrega-fecha').value;
  const ciudad = document.getElementById('c-entrega-ciudad').value || '—';
  const lugar = document.getElementById('c-entrega-lugar').value || '—';
  const garantiaEquipo = document.getElementById('c-entrega-garantia-equipo').value || '0';
  const garantiaInstalacion = document.getElementById('c-entrega-garantia-instalacion').value || '0';
  const proveedor = document.getElementById('c-entrega-proveedor').value || '';
  const equiposTexto = document.getElementById('c-entrega-equipos').value || '';
  const fechaFmt = fecha ? new Date(fecha+'T00:00:00').toLocaleDateString('es-MX',{day:'numeric',month:'long',year:'numeric'}) : '';

  function nuevaPagina(){
    doc.addPage();
    doc.setFillColor(216,25,47); doc.rect(0,0,pageW,8,'F');
    y = 56;
  }
  function espacioPara(alto){
    if(y + alto > bottomLimit) nuevaPagina();
  }
  function tituloSeccion(texto){
    espacioPara(30);
    doc.setFont('helvetica','bold'); doc.setFontSize(11.5); doc.setTextColor(216,25,47);
    doc.text(texto, margin, y);
    y += 8;
    doc.setDrawColor(228,225,220); doc.line(margin, y, pageW-margin, y);
    y += 16;
  }
  function parrafo(texto, opts){
    opts = opts || {};
    doc.setFont('helvetica', opts.bold ? 'bold' : 'normal');
    doc.setFontSize(opts.size || 9.5);
    const color = opts.color || [40,40,40];
    doc.setTextColor(color[0], color[1], color[2]);
    const indent = opts.indent || 0;
    const lineas = doc.splitTextToSize(texto, pageW - margin*2 - indent);
    espacioPara(lineas.length * 12 + 6);
    doc.text(lineas, margin + indent, y);
    y += lineas.length * 12 + (opts.espacioExtra !== undefined ? opts.espacioExtra : 8);
  }
  function lineaFirma(etiquetaIzq, etiquetaDer){
    espacioPara(50);
    y += 30;
    doc.setDrawColor(90,90,90);
    doc.line(margin, y, margin+180, y);
    doc.line(pageW-margin-180, y, pageW-margin, y);
    y += 12;
    doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(40,40,40);
    doc.text(etiquetaIzq, margin, y);
    doc.text(etiquetaDer, pageW-margin, y, { align:'right' });
    y += 24;
  }

  // Encabezado
  doc.setFillColor(216,25,47); doc.rect(0,0,pageW,8,'F');
  const logoH = 42, logoW = logoH * LOGO_RATIO;
  doc.addImage(LOGO_DATA_URI, 'PNG', margin, y - 26, logoW, logoH);
  doc.setFont('helvetica','bold'); doc.setFontSize(15); doc.setTextColor(20,20,20);
  doc.text('ACTA DE ENTREGA', pageW - margin, y - 6, { align:'right' });
  doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(116,118,122);
  doc.text('Folio: ' + folio, pageW - margin, y + 10, { align:'right' });
  y += 40;
  doc.setDrawColor(228,225,220); doc.line(margin, y, pageW-margin, y);
  y += 20;

  // I. Carta de entrega
  tituloSeccion('I. ENTREGA DEL SISTEMA: ' + tipo.toUpperCase());
  parrafo('Ref. ' + cliente, { bold:true, size:11, espacioExtra:12 });
  parrafo('De antemano agradezco la confianza depositada en nuestras capacidades para la instalación de los equipos en referencia.');
  parrafo('Adjuntamos a la presente para la firma el acta de entrega correspondiente, la cual contiene información importante para la operación y mantenimiento de los equipos instalados.');
  parrafo('Gustosamente atenderemos cualquier inquietud al respecto en nuestro departamento de soporte técnico.', { espacioExtra: 10 });
  lineaFirma('', proveedor || 'Proveedor');

  // II. Acta de entrega
  tituloSeccion('II. ACTA DE ENTREGA');
  parrafo('Ciudad y fecha: ' + ciudad + (fechaFmt ? ', ' + fechaFmt : ''), { bold:true });
  parrafo('Cliente: ' + cliente, { bold:true });
  parrafo('Lugar: ' + lugar, { bold:true });
  parrafo('Proveedor: ' + (proveedor || '—'), { bold:true, espacioExtra: 12 });
  parrafo('En la ciudad, fecha y lugar indicados se procedió a la entrega del suministro e instalación en perfecto estado de funcionamiento, habiéndose revisado y probado su correcto funcionamiento:');
  parrafo('Equipos electrónicos y materiales utilizados:', { bold:true, espacioExtra: 10 });
  const lineasEquipo = equiposTexto.split('\\n').map(function(l){ return l.trim(); }).filter(Boolean);
  if(lineasEquipo.length){
    lineasEquipo.forEach(function(linea){ parrafo('• ' + linea, { indent: 6, espacioExtra: 4 }); });
  } else {
    parrafo('(sin equipos capturados)', { color:[150,150,150] });
  }

  // III. Recibo a satisfacción
  tituloSeccion('III. RECIBO A SATISFACCIÓN');
  parrafo((proveedor || 'El proveedor') + ' hace la entrega formal a satisfacción de ' + tipo + ' a ' + cliente + '. Firman de conformidad las dos partes que intervienen en el proyecto.', { espacioExtra: 6 });
  lineaFirma('Recibe / Administrador', proveedor || 'Proveedor');
  lineaFirma('Testigo', 'Testigo');

  // IV. Garantía de los equipos
  tituloSeccion('IV. GARANTÍA DE LOS EQUIPOS');
  parrafo('a) Se certifica que los equipos suministrados tienen un periodo de garantía contra defectos de fabricación de ' + garantiaEquipo + ' mes(es), contados a partir de la fecha de entrega del sistema con firma del acta; la instalación tiene garantía de ' + garantiaInstalacion + ' mes(es).');
  parrafo('b) Cuando en las instalaciones del cliente sea necesaria cualquier modificación en el suministro de las redes (cambio de transformadores, rutas de cableado o cargas externas sobre los circuitos de seguridad), debe reportarse por escrito o correo electrónico al proveedor, quien evaluará los riesgos que estas modificaciones representen para los equipos instalados.');
  parrafo('c) Si se presentan fallas en el sistema o cualquier eventualidad con los equipos durante el periodo de garantía, esto debe reportarse de inmediato al proveedor, quien procederá con la respectiva revisión.', { espacioExtra: 14 });

  // V. Exclusiones de la garantía
  tituloSeccion('V. EXCLUSIONES DE LA GARANTÍA');
  parrafo('La garantía sobre los equipos instalados se perderá en los siguientes casos:', { espacioExtra: 10 });
  [
    'Cuando los equipos sean operados bajo condiciones ambientales, eléctricas o de temperaturas adversas.',
    'Cuando los equipos son instalados en cableados eléctricos o de video con más de un año de uso.',
    'Cuando se presenten eventos de fuerza mayor o casos fortuitos (rayos, inundaciones, terremotos, incendios, guerra, desastres naturales, granizo, actos vandálicos o de terrorismo).',
    'Cuando los equipos sean objeto de mal uso, abuso, instalación inapropiada o mal uso del cliente o sus dependientes.',
    'Cuando los equipos sean manipulados por personal técnico diferente al autorizado por el proveedor.',
    'Cuando los equipos se vean afectados por cortos circuitos o fluctuaciones de corriente eléctrica.',
    'Cuando los equipos son instalados en circuitos ya existentes con cableado de tiempo de uso considerable.',
    'Cuando provoquen un corto al tirar un poste u otro elemento donde esté instalado un equipo.',
    'Cuando provoquen un corto en la instalación eléctrica al conectar equipos de alto voltaje (parrillas eléctricas, resistencias para agua, etc.).',
    'Cuando afecten la instalación subterránea al hacer alguna excavación sin dar aviso al proveedor.',
    'No habrá garantía si se roban los equipos instalados (reembolso).',
    'Toda visita fuera de garantía tendrá un costo dependiendo del asunto a resolver (por ejemplo, extraer grabaciones de eventos).',
  ].forEach(function(e){ parrafo(e, { indent: 6, espacioExtra: 4 }); });

  // VI. Recomendaciones
  tituloSeccion('VI. RECOMENDACIONES');
  parrafo('En el cuidado y mantenimiento de sus equipos se debe tener en cuenta las siguientes recomendaciones:', { espacioExtra: 10 });
  [
    'Una vez finalizado el periodo de garantía se recomienda la limpieza y mantenimiento preventivo de los equipos con una periodicidad sugerida de 6 meses.',
    'Los equipos no deben ser sometidos a condiciones extremas de calor y humedad.',
    'Se requiere el uso de energía regulada y/o UPS.',
    'No se debe desconectar la UPS sin antes apagar correctamente el equipo instalado conectado a la misma.',
    'El punto de alimentación debe mantener un buen polo a tierra para la protección de los equipos (voltaje neutro-tierra menor a 1 v.a.c.).',
    'La toma de alimentación usada por los equipos instalados no debe ser compartida con ningún otro equipo.',
    'Se debe evitar que los equipos estén expuestos a factores ambientales como rayos directos del sol, ceniza, polvo o suciedad.',
    'La limpieza de los equipos debe realizarse con un paño húmedo en agua -- no usar disolventes ni jabones.',
    'En las actividades de limpieza se debe evitar el derramamiento de líquidos al interior de los equipos.',
    'Las condiciones de ventilación deben ser adecuadas, especialmente para monitores, CPU y módulos.',
    'De no seguir las recomendaciones escritas, se perderá la garantía de forma inmediata.',
  ].forEach(function(r){ parrafo(r, { indent: 6, espacioExtra: 4 }); });

  return doc.output('blob');
}

document.getElementById('btn-entrega-pdf').addEventListener('click', async () => {
  const btn = document.getElementById('btn-entrega-pdf');
  const hint = document.getElementById('pdf-hint');
  const original = btn.textContent;
  btn.disabled = true; btn.textContent = 'Generando…';
  try{
    const blob = await buildEntregaPdfBlob();
    const folio = (document.getElementById('c-folio').value || 'entrega').replace(/[^a-z0-9\\-]/gi,'_');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'acta_entrega_' + folio + '.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url), 4000);
    hint.textContent = 'Acta de entrega descargada.';
  } catch(e){
    hint.textContent = 'Ocurrió un error generando el acta de entrega.';
    console.error(e);
  } finally {
    btn.disabled = false; btn.textContent = original;
  }
});''',
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
    print("    git add frontend/cotizador_costos.html")
    print('    git commit -m "Cotizador: nueva seccion Acta de entrega, opcional por cotizacion, PDF automatico"')
    print("    git push")


if __name__ == "__main__":
    main()
