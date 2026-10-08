#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador de sistema TI (frontend/cotizador_costos.html, el que arma
cotizaciones de Sistema TI / Dental Suite / Otros servicios para
prospectos, distinto del Cotizador de articulos): agrega una seccion
"06 Datos de pago" donde puedes escribir tu cuenta bancaria/CLABE para
esa cotizacion -- si la llenas, sale como una seccion "Como pagar" tanto
en la vista previa como en el PDF descargable, justo despues del total.
Se guarda junto con el resto de la configuracion de esa cotizacion (igual
que el folio, la intro o las notas), asi que si la vuelves a abrir sigue
ahi.

Que cambia (un solo archivo, frontend/cotizador_costos.html):
- Nuevo campo de texto "Datos de pago" en el panel de configuracion.
- Se ve en la vista previa (recuadro "Como pagar") y en el PDF.
- Se guarda y se carga junto con el resto de la cotizacion.
"""
import sys

ARCHIVOS = {
    'frontend/cotizador_costos.html': [
        [
            '  .doc-notes{ margin-top:22px; font-size:0.75rem; color:var(--gris-1); line-height:1.6; white-space:pre-wrap; }\n  .doc-foot{ margin-top:30px; padding-top:14px; border-top:1px solid var(--linea); font-size:0.72rem; color:var(--gris-1); display:flex; justify-content:space-between; }',
            '  .doc-notes{ margin-top:22px; font-size:0.75rem; color:var(--gris-1); line-height:1.6; white-space:pre-wrap; }\n  .doc-pago{ margin-top:22px; padding:14px 16px; border-radius:8px; background:color-mix(in srgb, var(--rojo) 6%, transparent); border:1px solid color-mix(in srgb, var(--rojo) 20%, transparent); }\n  .doc-pago h4{ margin:0 0 6px; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.04em; color:var(--rojo); }\n  .doc-pago p{ margin:0; font-size:0.82rem; line-height:1.55; white-space:pre-wrap; }\n  .doc-foot{ margin-top:30px; padding-top:14px; border-top:1px solid var(--linea); font-size:0.72rem; color:var(--gris-1); display:flex; justify-content:space-between; }',
        ],
        [
            '    <div class="toggle-row">\n      <div class="lbl">Incluir sección "para crecer después"<small>Los módulos marcados en el paso 04</small></div>\n      <label class="switch"><input type="checkbox" id="t-growth" checked><span class="slider"></span></label>\n    </div>\n\n    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>',
            '    <div class="toggle-row">\n      <div class="lbl">Incluir sección "para crecer después"<small>Los módulos marcados en el paso 04</small></div>\n      <label class="switch"><input type="checkbox" id="t-growth" checked><span class="slider"></span></label>\n    </div>\n\n    <h2 class="section-title"><span class="n">06</span>Datos de pago</h2>\n    <p style="font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;">Si lo llenas, aparece al final de la cotización para que el cliente sepa cómo pagarte si la acepta.</p>\n    <label class="field"><span class="lbl">Banco, cuenta, CLABE, etc. (opcional)</span>\n      <textarea id="c-datos-pago" placeholder="Ej. BBVA, cuenta 0123456789, CLABE 012345678901234567, a nombre de Mark Inc"></textarea>\n    </label>\n\n    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>',
        ],
        [
            "    marca: document.getElementById('c-marca').value,\n    intro: document.getElementById('c-intro').value,\n    notas: document.getElementById('c-notas').value,\n  };",
            "    marca: document.getElementById('c-marca').value,\n    intro: document.getElementById('c-intro').value,\n    notas: document.getElementById('c-notas').value,\n    datos_pago: document.getElementById('c-datos-pago').value,\n  };",
        ],
        [
            '  document.getElementById(\'doc-inner\').innerHTML = `\n    <div class="doc-header">\n      <div class="co"><img src="${LOGO_DATA_URI}" alt="logo" style="height:40px;display:block;"><small>${c.marca}</small></div>\n      <div class="meta">Folio <b>${c.folio}</b><br>${fechaFmt}</div>\n    </div>\n    <div class="doc-client">\n      <div><span class="k">Cotización para</span><b>${c.empresa}</b></div>\n      ${c.contacto?`<div><span class="k">Contacto</span>${c.contacto}</div>`:\'\'}\n      ${c.giro?`<div><span class="k">Giro</span>${c.giro}</div>`:\'\'}\n    </div>\n    <div class="doc-intro">${c.intro}</div>\n    <div class="doc-mods">${modsHtml}</div>\n    <div class="doc-totals">${totalsHtml}</div>\n    ${growthHtml}\n    <div class="doc-notes">${c.notas}</div>\n    <div class="doc-foot"><span>Mark·Inc — Sistemas TI</span><span>Cotización válida por 15 días</span></div>\n  `;\n}',
            '  const pagoHtml = c.datos_pago ? `\n    <div class="doc-pago">\n      <h4>Cómo pagar</h4>\n      <p>${c.datos_pago}</p>\n    </div>` : \'\';\n\n  document.getElementById(\'doc-inner\').innerHTML = `\n    <div class="doc-header">\n      <div class="co"><img src="${LOGO_DATA_URI}" alt="logo" style="height:40px;display:block;"><small>${c.marca}</small></div>\n      <div class="meta">Folio <b>${c.folio}</b><br>${fechaFmt}</div>\n    </div>\n    <div class="doc-client">\n      <div><span class="k">Cotización para</span><b>${c.empresa}</b></div>\n      ${c.contacto?`<div><span class="k">Contacto</span>${c.contacto}</div>`:\'\'}\n      ${c.giro?`<div><span class="k">Giro</span>${c.giro}</div>`:\'\'}\n    </div>\n    <div class="doc-intro">${c.intro}</div>\n    <div class="doc-mods">${modsHtml}</div>\n    <div class="doc-totals">${totalsHtml}</div>\n    ${pagoHtml}\n    ${growthHtml}\n    <div class="doc-notes">${c.notas}</div>\n    <div class="doc-foot"><span>Mark·Inc — Sistemas TI</span><span>Cotización válida por 15 días</span></div>\n  `;\n}',
        ],
        [
            "['c-empresa','c-contacto','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas'].forEach(id=>{",
            "['c-empresa','c-contacto','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas','c-datos-pago'].forEach(id=>{",
        ],
        [
            "  const intro = document.getElementById('c-intro').value;\n  const notas = document.getElementById('c-notas').value;\n  const fechaFmt = fecha ? new Date(fecha+'T00:00:00').toLocaleDateString('es-MX',{day:'numeric',month:'long',year:'numeric'}) : '';",
            "  const intro = document.getElementById('c-intro').value;\n  const notas = document.getElementById('c-notas').value;\n  const datosPago = document.getElementById('c-datos-pago').value;\n  const fechaFmt = fecha ? new Date(fecha+'T00:00:00').toLocaleDateString('es-MX',{day:'numeric',month:'long',year:'numeric'}) : '';",
        ],
        [
            "  doc.text(totalLabel, margin, y);\n  doc.text(totalValue, pageW-margin, y, { align:'right' });\n  y += 26;\n\n  const offMods = mods().filter(m=>!m.on);",
            "  doc.text(totalLabel, margin, y);\n  doc.text(totalValue, pageW-margin, y, { align:'right' });\n  y += 26;\n\n  if(datosPago && datosPago.trim()){\n    doc.setFont('helvetica','bold'); doc.setFontSize(9); doc.setTextColor(216,25,47);\n    doc.text('CÓMO PAGAR', margin, y);\n    y += 13;\n    doc.setFont('helvetica','normal'); doc.setFontSize(8.5); doc.setTextColor(90,90,90);\n    const pagoLines = doc.splitTextToSize(datosPago, pageW - margin*2);\n    doc.text(pagoLines, margin, y);\n    y += pagoLines.length*11 + 12;\n  }\n\n  const offMods = mods().filter(m=>!m.on);",
        ],
        [
            "      if(cli.notas) document.getElementById('c-notas').value = cli.notas;",
            "      if(cli.notas) document.getElementById('c-notas').value = cli.notas;\n      if(cli.datos_pago) document.getElementById('c-datos-pago').value = cli.datos_pago;",
        ],
        [
            "      intro: document.getElementById('c-intro').value,\n      notas: document.getElementById('c-notas').value,\n    },\n    showResources: state.showResources,",
            "      intro: document.getElementById('c-intro').value,\n      notas: document.getElementById('c-notas').value,\n      datos_pago: document.getElementById('c-datos-pago').value,\n    },\n    showResources: state.showResources,",
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
    print('    git commit -m "Cotizador de sistema TI: campo de datos de pago (banco/cuenta) en la cotizacion"')
    print("    git push")


if __name__ == "__main__":
    main()
