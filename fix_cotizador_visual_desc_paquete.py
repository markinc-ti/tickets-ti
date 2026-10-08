# -*- coding: utf-8 -*-
"""
Cotizador visual: el descuento del PAQUETE se coloca en cada accesorio y ya
no afecta a la unidad.

- Al quedar completo un paquete con descuento, ese % se pone en el campo
  "Desc. %" de cada accesorio del paquete (visible y editable para mejorarlo).
  Si el vendedor ya lo cambio a mano, se respeta. Al quitar el paquete vuelve
  al descuento sugerido del accesorio.
- La unidad (producto principal) nunca se ve afectada por paquetes y su
  descuento es fijo (el que pone el administrador al crear el equipo).
- Se quita la opcion "el descuento tambien aplica al producto principal".

Requiere los parches anteriores del Cotizador visual.
Toca: frontend/index.html. Se puede correr varias veces.

Uso: en la carpeta del repo:
    py -3 fix_cotizador_visual_desc_paquete.py
"""
import os
import sys

ARCHIVOS = {'frontend/index.html': [["  CV_SEL = { activos: [], desc: {}, precio: {}, fuente: {}, color: CV_BASE, libres: [], aviso: '', cliente: { nombre: '', telefono: '', tipo: 'publico' } };\n", "  CV_SEL = { activos: [], desc: {}, precio: {}, fuente: {}, color: CV_BASE, libres: [], aviso: '', descPaq: {}, cliente: { nombre: '', telefono: '', tipo: 'publico' } };\n"], ['function cv_togglePaquete(i) {', '// El descuento de un paquete se COLOCA en el campo "Desc. %" de cada uno de\n// sus accesorios cuando el paquete queda completo (visible y editable, por si\n// el vendedor lo quiere mejorar). Si el vendedor ya cambió ese % a mano, no\n// se le toca. Al deshacer el paquete, vuelve al descuento sugerido del\n// accesorio. La unidad (producto principal) NUNCA se ve afectada.\nfunction cv_sincronizarDescPaquetes() {\n  const cfg = CV_KIT.config;\n  const completos = (cfg.combos || []).filter(cb => Number(cb.descuento_pct) > 0 && cv_paqueteCompleto(cb));\n  CV_SEL.descPaq = CV_SEL.descPaq || {};\n  cfg.accesorios.forEach(a => {\n    const sugerido = Number(a.descuento_pct) || 0;\n    const pctPaq = completos.filter(cb => cb.requiere.includes(a.uid))\n      .reduce((m, cb) => Math.max(m, Number(cb.descuento_pct) || 0), 0);\n    const previo = CV_SEL.descPaq[a.uid];\n    const actual = Number(CV_SEL.desc[a.uid]) || 0;\n    const automatico = previo !== undefined ? actual === previo : actual === sugerido;\n    if (!automatico) { delete CV_SEL.descPaq[a.uid]; return; }\n    if (pctPaq > 0) {\n      const nuevo = Math.max(sugerido, pctPaq);\n      CV_SEL.desc[a.uid] = nuevo;\n      CV_SEL.descPaq[a.uid] = nuevo;\n    } else if (previo !== undefined) {\n      CV_SEL.desc[a.uid] = sugerido;\n      delete CV_SEL.descPaq[a.uid];\n    }\n  });\n}\n\nfunction cv_togglePaquete(i) {'], ['    const misCombos = combos.filter(cb => uid === CV_BASE ? cb.incluye_base !== false : cb.requiere.includes(uid));\n    const factor = misCombos.reduce((f, cb) => f * (1 - Number(cb.descuento_pct) / 100), 1 - desc / 100);\n    const descEfectivo = Math.round((1 - factor) * 10000) / 100;\n', '    const misCombos = uid === CV_BASE ? [] : combos.filter(cb => cb.requiere.includes(uid) && CV_SEL.descPaq && CV_SEL.descPaq[uid] === desc);\n    const descEfectivo = desc;\n'], ["          nota: l.combos.length ? `Incluye descuento de paquete: ${l.combos.map(cb => `${cb.nombre || 'paquete'} (${cb.descuento_pct}%)`).join(', ')}` : null,", "          nota: l.combos.length ? `Descuento de paquete: ${l.combos.map(cb => cb.nombre || 'paquete').join(', ')}` : null,"], ['      ${editable ? `\n        <label style="font-size:11px; color:var(--muted); display:flex; align-items:center; gap:4px;">Desc.', '      ${editable === \'fijo\' ? `\n        ${Number(CV_SEL.desc[uid]) > 0 ? `<span style="font-size:11px; color:var(--muted);">Desc. ${CV_SEL.desc[uid]}% <span class="cv-chip">fijo</span></span>` : \'\'}\n        <span style="margin-left:auto; font-weight:600;" id="cv_neto_${uid}"></span>` : editable ? `\n        <label style="font-size:11px; color:var(--muted); display:flex; align-items:center; gap:4px;">Desc.'], ['            ${cv_htmlLineaPrecio(CV_BASE, cfg.base, true)}', "            ${cv_htmlLineaPrecio(CV_BASE, cfg.base, 'fijo')}"], ["function cv_renderCotizar() {\n  const cont = document.getElementById('checadorPrecioContenido');\n  const cfg = CV_KIT.config;\n", "function cv_renderCotizar() {\n  const cont = document.getElementById('checadorPrecioContenido');\n  const cfg = CV_KIT.config;\n  cv_sincronizarDescPaquetes();\n"], ["🎁 Descuento <b>${escapeHtml(cb.nombre || 'por paquete')}</b> aplicado: −${cb.descuento_pct}% extra</div>", "🎁 Paquete <b>${escapeHtml(cb.nombre || '')}</b>: se puso −${cb.descuento_pct}% en sus accesorios (lo puedes mejorar en cada uno)</div>"], ["y obtén <b>${escapeHtml(s.cb.nombre || 'descuento por paquete')}</b> (−${s.cb.descuento_pct}% extra)</div>", "para el paquete <b>${escapeHtml(s.cb.nombre || '')}</b> (−${s.cb.descuento_pct}% en sus accesorios)</div>"], ['Si le pones descuento, se aplica solo cuando están TODOS sus accesorios — encima del descuento de cada producto.</p>', 'Si le pones descuento, al quedar completo se coloca ese % en el descuento de cada accesorio del paquete (el vendedor lo ve y lo puede mejorar). El paquete NUNCA cambia el precio ni el descuento de la unidad — ese es el que pones arriba y queda fijo.</p>'], ['Ya viene seleccionado al abrir el equipo</label>\n          <label style="text-transform:none; font-weight:400; font-size:12px; display:flex; gap:5px; align-items:center;">\n            <input type="checkbox" class="cv-check" ${cb.incluye_base !== false ? \'checked\' : \'\'} onchange="CV_EDIT.config.combos[${i}].incluye_base=this.checked" /> El descuento también aplica al producto principal</label>\n', 'Ya viene seleccionado al abrir el equipo</label>\n          <!-- (el descuento del paquete ya no aplica a la unidad) -->\n'], ['          <div class="field"><label>Descuento extra %</label>', '          <div class="field"><label>Descuento del paquete % (en sus accesorios)</label>'], ['        <div style="font-size:11px; color:var(--muted); margin-top:3px;">El vendedor lo puede cambiar al cotizar.</div>', '        <div style="font-size:11px; color:var(--muted); margin-top:3px;">${key === CV_BASE ? \'Fijo: el vendedor no lo puede cambiar y los paquetes no lo afectan.\' : \'El vendedor lo puede cambiar al cotizar.\'}</div>']]}

def main():
    errores = []
    cambios = {}
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        texto = original
        for i, (viejo, nuevo) in enumerate(pares, 1):
            # En Windows git puede dejar los archivos con saltos de linea
            # CRLF (\r\n): se prueba el texto tal cual y, si no aparece,
            # la version con CRLF.
            variantes = [(viejo, nuevo)]
            if "\n" in viejo:
                variantes.append((viejo.replace("\n", "\r\n"), nuevo.replace("\n", "\r\n")))
            if any(nv in texto for _, nv in variantes):
                continue  # ya aplicado
            elegido = None
            for vj, nv in variantes:
                if texto.count(vj) == 1:
                    elegido = (vj, nv)
                    break
            if not elegido:
                n = max(texto.count(vj) for vj, _ in variantes)
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
                continue
            texto = texto.replace(elegido[0], elegido[1], 1)
        if texto != original:
            cambios[ruta] = texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
