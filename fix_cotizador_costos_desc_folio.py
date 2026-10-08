# -*- coding: utf-8 -*-
"""
Cotizador de costos (Superadmin) — descripción editable por ítem +
folio automático y consecutivo.

Qué hace:
1. En cada tarjeta de módulo/ítem del cotizador (Recursos Humanos,
   Proyectos, Conexión a sistema externo, Dashboard y auditoría, etc.)
   la descripción ya se puede editar directamente ahí, igual que ya
   podías editar nombre/descripción de un ítem personalizado agregado
   a mano. El cambio se guarda solo en ESA cotización (no toca el
   catálogo base que ven las demás cotizaciones nuevas).
2. El campo "Folio" ya no es un texto libre con la misma plantilla
   fija (COT-SW-0001) repetida en todas las cotizaciones nuevas: al
   abrir una cotización nueva (o al cambiar de línea de producto:
   TI / Dental / Otros) se le asigna automáticamente el siguiente
   folio consecutivo, buscando entre TODAS las cotizaciones ya
   guardadas cuál es el número más alto usado con ese mismo prefijo
   (COT-SW-, COT-DS-, COT-OS-) y sumándole 1. Si el usuario escribe un
   folio a mano, se respeta tal cual (deja de autogenerarse) hasta que
   borre el campo o abra otra cotización nueva.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_cotizador_costos_desc_folio.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
# backend/db.py — expone el folio guardado de cada cotización en el listado,
# para poder calcular el siguiente consecutivo desde el frontend.
# ---------------------------------------------------------------------------
ARCHIVOS['backend/db.py'] = [
    [
        '        resultado.append({\n'
        '            "id": f["id"],\n'
        '            "empresa_id": f["empresa_id"],\n'
        '            "empresa_nombre": f["empresa_nombre"],\n'
        '            "nombre_cliente": f["nombre_cliente"] or f["empresa_nombre"] or "—",\n'
        '            "producto": config.get("producto", "ti"),\n'
        '            "renta_mensual": renta_total,\n'
        '            "setup_total": setup_total,\n'
        '            "costo_mensual": costo_total,\n'
        '            "margen_pct": margen,\n'
        '            "actualizado_en": f["actualizado_en"],\n'
        '        })',

        '        resultado.append({\n'
        '            "id": f["id"],\n'
        '            "empresa_id": f["empresa_id"],\n'
        '            "empresa_nombre": f["empresa_nombre"],\n'
        '            "nombre_cliente": f["nombre_cliente"] or f["empresa_nombre"] or "—",\n'
        '            "producto": config.get("producto", "ti"),\n'
        '            "folio": (config.get("cliente") or {}).get("folio"),\n'
        '            "renta_mensual": renta_total,\n'
        '            "setup_total": setup_total,\n'
        '            "costo_mensual": costo_total,\n'
        '            "margen_pct": margen,\n'
        '            "actualizado_en": f["actualizado_en"],\n'
        '        })',
    ],
]

# ---------------------------------------------------------------------------
# frontend/cotizador_costos.html
# ---------------------------------------------------------------------------
ARCHIVOS['frontend/cotizador_costos.html'] = [
    # 1) Descripción editable también para los ítems del catálogo (antes solo
    #    los ítems personalizados/agregados a mano tenían el campo editable).
    [
        "          ${m.custom ? `\n"
        '            <input type="text" data-mod-name="${i}" value="${m.name}" style="font-weight:700; font-size:0.92rem; padding:3px 6px; margin-bottom:3px;" placeholder="Nombre del ítem">\n'
        '            <input type="text" data-mod-desc="${i}" value="${m.desc}" style="font-size:0.78rem; padding:3px 6px;" placeholder="Descripción (opcional)">\n'
        '          ` : `\n'
        '            <div class="name">${m.name}${m.locked?\' <span style="color:var(--gris-1);font-weight:400;font-size:0.72rem;">(base, siempre incluido)</span>\':\'\'}</div>\n'
        '            <div class="desc">${m.desc}</div>\n'
        '          `}',

        "          ${m.custom ? `\n"
        '            <input type="text" data-mod-name="${i}" value="${m.name}" style="font-weight:700; font-size:0.92rem; padding:3px 6px; margin-bottom:3px;" placeholder="Nombre del ítem">\n'
        '            <input type="text" data-mod-desc="${i}" value="${m.desc}" style="font-size:0.78rem; padding:3px 6px;" placeholder="Descripción (opcional)">\n'
        '          ` : `\n'
        '            <div class="name">${m.name}${m.locked?\' <span style="color:var(--gris-1);font-weight:400;font-size:0.72rem;">(base, siempre incluido)</span>\':\'\'}</div>\n'
        '            <input type="text" data-mod-desc="${i}" value="${m.desc}" style="font-size:0.78rem; padding:3px 6px;" placeholder="Descripción">\n'
        '          `}',
    ],

    # 2) Marca cualquier edición manual del folio (para dejar de autogenerarlo).
    [
        "['c-empresa','c-contacto','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas','c-datos-pago'].forEach(id=>{\n"
        "  document.getElementById(id).addEventListener('input', renderPreview);\n"
        '});\n'
        "document.getElementById('t-recursos').addEventListener('change', e=>{ state.showResources = e.target.checked; renderPreview(); });",

        "['c-empresa','c-contacto','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas','c-datos-pago'].forEach(id=>{\n"
        "  document.getElementById(id).addEventListener('input', renderPreview);\n"
        '});\n'
        "document.getElementById('c-folio').addEventListener('input', e=>{ e.target.dataset.autogenerado = '0'; });\n"
        "document.getElementById('t-recursos').addEventListener('change', e=>{ state.showResources = e.target.checked; renderPreview(); });",
    ],

    # 3) Al cambiar de línea de producto, el folio se recalcula automático
    #    (ya no se rellena con la plantilla fija "-0001") salvo que el
    #    usuario ya lo haya editado a mano.
    [
        "document.getElementById('productbar').addEventListener('click', e=>{\n"
        "  const btn = e.target.closest('button[data-producto]'); if(!btn) return;\n"
        '  const anterior = PRODUCTOS[state.producto];\n'
        '  state.producto = btn.dataset.producto;\n'
        '  const nuevo = PRODUCTOS[state.producto];\n'
        "  document.querySelectorAll('#productbar button').forEach(b=>b.classList.toggle('on', b===btn));\n"
        '\n'
        '  // solo reemplaza la intro si el usuario no la había personalizado\n'
        "  const introEl = document.getElementById('c-intro');\n"
        '  if(introEl.value.trim() === anterior.introDefault.trim()) introEl.value = nuevo.introDefault;\n'
        '\n'
        '  // solo reemplaza el folio si sigue siendo el de plantilla del producto anterior\n'
        "  const folioEl = document.getElementById('c-folio');\n"
        "  if(!folioEl.value.trim() || folioEl.value.trim() === (anterior.folioPrefix + '-0001')){\n"
        "    folioEl.value = nuevo.folioPrefix + '-0001';\n"
        '  }\n'
        '\n'
        '  renderAll();\n'
        '});',

        "document.getElementById('productbar').addEventListener('click', async e=>{\n"
        "  const btn = e.target.closest('button[data-producto]'); if(!btn) return;\n"
        '  const anterior = PRODUCTOS[state.producto];\n'
        '  state.producto = btn.dataset.producto;\n'
        '  const nuevo = PRODUCTOS[state.producto];\n'
        "  document.querySelectorAll('#productbar button').forEach(b=>b.classList.toggle('on', b===btn));\n"
        '\n'
        '  // solo reemplaza la intro si el usuario no la había personalizado\n'
        "  const introEl = document.getElementById('c-intro');\n"
        '  if(introEl.value.trim() === anterior.introDefault.trim()) introEl.value = nuevo.introDefault;\n'
        '\n'
        '  // solo reemplaza el folio si sigue siendo automático (vacío, o el que\n'
        '  // nosotros mismos le pusimos) — si el usuario lo editó a mano, se respeta.\n'
        "  const folioEl = document.getElementById('c-folio');\n"
        "  if(!folioEl.value.trim() || folioEl.dataset.autogenerado === '1'){\n"
        '    folioEl.value = await _siguienteFolio(nuevo.folioPrefix);\n'
        "    folioEl.dataset.autogenerado = '1';\n"
        '  }\n'
        '\n'
        '  renderAll();\n'
        '});',
    ],

    # 4) Función que calcula el siguiente folio consecutivo consultando las
    #    cotizaciones ya guardadas.
    [
        'function _fusionarInfraServidor(guardada){\n'
        '  const porId = {}; (guardada||[]).forEach(i=>porId[i.id]=i);\n'
        '  return state.infra.map(def=>{\n'
        '    const g = porId[def.id];\n'
        '    return g ? Object.assign({}, def, { cost: (g.cost ?? def.cost), on: (g.on!==undefined?g.on:def.on) }) : def;\n'
        '  });\n'
        '}\n'
        '\n'
        'async function _resolverCotizacionId(){',

        'function _fusionarInfraServidor(guardada){\n'
        '  const porId = {}; (guardada||[]).forEach(i=>porId[i.id]=i);\n'
        '  return state.infra.map(def=>{\n'
        '    const g = porId[def.id];\n'
        '    return g ? Object.assign({}, def, { cost: (g.cost ?? def.cost), on: (g.on!==undefined?g.on:def.on) }) : def;\n'
        '  });\n'
        '}\n'
        '\n'
        'async function _siguienteFolio(prefix){\n'
        '  // Folio automático y consecutivo: busca el número más alto ya usado\n'
        '  // entre TODAS las cotizaciones guardadas con ese mismo prefijo\n'
        '  // (COT-SW-, COT-DS-, COT-OS-) y regresa el siguiente.\n'
        '  try{\n'
        "    const r = await fetch('/api/superadmin/cotizaciones', { headers: _authHeaders() });\n"
        "    if(!r.ok) return prefix + '-0001';\n"
        '    const lista = await r.json();\n'
        "    const re = new RegExp('^' + prefix.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '-(\\\\d+)$');\n"
        '    let max = 0;\n'
        '    lista.forEach(c=>{\n'
        "      const m = (c.folio || '').match(re);\n"
        '      if(m) max = Math.max(max, parseInt(m[1], 10));\n'
        '    });\n'
        "    return prefix + '-' + String(max + 1).padStart(4, '0');\n"
        '  }catch(e){\n'
        "    return prefix + '-0001';\n"
        '  }\n'
        '}\n'
        '\n'
        'async function _resolverCotizacionId(){',
    ],

    # 5) Cotización nueva (nada guardado todavía): le asigna folio automático
    #    en vez de dejarlo vacío / con la plantilla fija.
    [
        '    } else {\n'
        "      document.getElementById('carga-aviso').textContent = 'Todavía no hay nada guardado en esta cotización — estos son precios de plantilla, ajústalos y da Guardar.';\n"
        '    }',

        '    } else {\n'
        "      const folioEl = document.getElementById('c-folio');\n"
        '      folioEl.value = await _siguienteFolio(PRODUCTOS[state.producto].folioPrefix);\n'
        "      folioEl.dataset.autogenerado = '1';\n"
        "      document.getElementById('carga-aviso').textContent = 'Todavía no hay nada guardado en esta cotización — estos son precios de plantilla, ajústalos y da Guardar.';\n"
        '    }',
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
    print("   git add backend/db.py frontend/cotizador_costos.html")
    print('   git commit -m "Cotizador de costos: descripcion editable por item + folio automatico consecutivo"')
    print("   git push")


if __name__ == "__main__":
    main()
