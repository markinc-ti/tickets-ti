# -*- coding: utf-8 -*-
"""
- Equipo especial: cada pieza (unidad, compresor...) puede tener COLORES con
  foto derecha e izquierda (como el selector de color de la unidad). Al
  cotizar, la pieza elegida muestra sus colores; el renglon dice "— COLOR: X".
  Boton "Duplicar pieza" para dar de alta otro modelo en el mismo lugar sin
  volver a acomodarlo (para meter los 9 modelos de unidad, etc.).
- WhatsApp: mensaje de agradecimiento "gracias por cotizar con Mark Inc &
  Peymar" + invitacion a www.markinc.com.mx, con el PDF adjunto (no liga).
- PDF de la cotizacion: bloque "Como pagar" con las cuentas de banco en
  recuadro (Bancomer, Banamex, Santander) y franja "A nombre de...".
  Se arreglo que ese bloque nunca salia (no se leia el dato de la empresa).

REQUIERE haber corrido antes fix_whatsapp_pdf.py.
Toca: frontend/index.html, backend/db.py, backend/pdfs_cotizaciones.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "  cfg.accesorios.forEach(a => { CV_SEL.desc[a.uid] = Number(a.descuento_pct) || 0; });\n  if (cfg.tipo === 'escena') {\n    CV_SEL.lado = {};\n    const puestos = new Set();\n    cfg.accesorios.filter(a => a.por_defecto).forEach(a => {\n      const k = cv_esc_lugarKey(a);\n",
   "  cfg.accesorios.forEach(a => { CV_SEL.desc[a.uid] = Number(a.descuento_pct) || 0; });\n  if (cfg.tipo === 'escena') {\n    CV_SEL.lado = {};\n    CV_SEL.colorPieza = {};\n    const puestos = new Set();\n    cfg.accesorios.filter(a => a.por_defecto).forEach(a => {\n      const k = cv_esc_lugarKey(a);\n"
  ],
  [
   "    const desc = Math.min(100, Math.max(0, Number(CV_SEL.desc[uid]) || 0));\n    const misCombos = uid === CV_BASE ? [] : combos.filter(cb => cb.requiere.includes(uid) && CV_SEL.descPaq && CV_SEL.descPaq[uid] === desc);\n    const descEfectivo = desc;\n    const nota = (escena && p.imagen_izq) ? `Orientación: ${(CV_SEL.lado || {})[cv_esc_lugarKey(p)] === 'izq' ? 'izquierda' : 'derecha'}` : null;\n    return { uid, p, precio, desc, combos: misCombos, descEfectivo, neto: precio * (1 - descEfectivo / 100), nota };\n  }).filter(Boolean).concat((CV_SEL.libres || []).map(l => {\n    const precio = Math.max(0, Number(l.precio) || 0);\n    return { uid: l.uid, p: { nombre: (l.nombre || '').trim() }, precio, desc: 0, combos: [], descEfectivo: 0, neto: precio, libre: true };\n",
   "    const desc = Math.min(100, Math.max(0, Number(CV_SEL.desc[uid]) || 0));\n    const misCombos = uid === CV_BASE ? [] : combos.filter(cb => cb.requiere.includes(uid) && CV_SEL.descPaq && CV_SEL.descPaq[uid] === desc);\n    const descEfectivo = desc;\n    const conIzq = escena && (p.imagen_izq || (p.colores || []).some(c => c.imagen_izq));\n    const nota = conIzq ? `Orientación: ${cv_esc_ladoIzq(p) ? 'izquierda' : 'derecha'}` : null;\n    const colorPieza = (escena && uid !== CV_BASE) ? cv_esc_nombreColor(p) : '';\n    return { uid, p: colorPieza ? { ...p, nombre: `${p.nombre} — COLOR: ${colorPieza.toUpperCase()}` } : p, precio, desc, combos: misCombos, descEfectivo, neto: precio * (1 - descEfectivo / 100), nota };\n  }).filter(Boolean).concat((CV_SEL.libres || []).map(l => {\n    const precio = Math.max(0, Number(l.precio) || 0);\n    return { uid: l.uid, p: { nombre: (l.nombre || '').trim() }, precio, desc: 0, combos: [], descEfectivo: 0, neto: precio, libre: true };\n"
  ],
  [
   "          nota: l.nota ? l.nota : l.combos.length ? `Descuento de paquete: ${l.combos.map(cb => cb.nombre || 'paquete').join(', ')}` : null,\n        })),\n        imagen_visual: canvas.toDataURL('image/jpeg', 0.85),\n        config_visual: { kit_id: CV_KIT.id, kit_nombre: CV_KIT.nombre, activos: CV_SEL.activos, descuentos: CV_SEL.desc, color: CV_SEL.color, color_nombre: color || null, entrega: CV_SEL.entrega, lados: CV_SEL.lado || null },\n        flete: (CV_SEL.entrega === 'instalamos' && CV_SEL.flete) ? CV_SEL.flete : null,\n        envio: cv_est_envioPayload(),\n      };\n",
   "          nota: l.nota ? l.nota : l.combos.length ? `Descuento de paquete: ${l.combos.map(cb => cb.nombre || 'paquete').join(', ')}` : null,\n        })),\n        imagen_visual: canvas.toDataURL('image/jpeg', 0.85),\n        config_visual: { kit_id: CV_KIT.id, kit_nombre: CV_KIT.nombre, activos: CV_SEL.activos, descuentos: CV_SEL.desc, color: CV_SEL.color, color_nombre: color || null, entrega: CV_SEL.entrega, lados: CV_SEL.lado || null, colores_piezas: CV_SEL.colorPieza || null },\n        flete: (CV_SEL.entrega === 'instalamos' && CV_SEL.flete) ? CV_SEL.flete : null,\n        envio: cv_est_envioPayload(),\n      };\n"
  ],
  [
   "  return ((a.lugar || a.grupo || '').trim().toLowerCase()) || a.uid;\n}\n\nfunction cv_esc_vista(cfg) {\n  const lados = (CV_SEL && CV_SEL.lado) || {};\n  return {\n    ...cfg,\n    accesorios: cfg.accesorios.map(a => (lados[cv_esc_lugarKey(a)] === 'izq' && a.imagen_izq)\n      ? { ...a, imagen: a.imagen_izq, x: a.xi ?? a.x, y: a.yi ?? a.y, w: a.wi ?? a.w, rot: a.roti ?? a.rot }\n      : a),\n  };\n}\n\nfunction cv_esc_lugares(cfg) {\n",
   "  return ((a.lugar || a.grupo || '').trim().toLowerCase()) || a.uid;\n}\n\n// Color elegido de una pieza (cada pieza puede tener sus colores, como la\n// unidad en el cotizador normal): {uid, nombre, hex, imagen (derecha), imagen_izq}.\nfunction cv_esc_colorDe(a) {\n  const id = ((CV_SEL && CV_SEL.colorPieza) || {})[a.uid];\n  return id ? (a.colores || []).find(c => c.uid === id && (c.imagen || c.imagen_izq)) || null : null;\n}\n\nfunction cv_esc_ladoIzq(a) {\n  if (((CV_SEL && CV_SEL.lado) || {})[cv_esc_lugarKey(a)] !== 'izq') return false;\n  const c = cv_esc_colorDe(a);\n  return !!(a.imagen_izq || (c && c.imagen_izq));\n}\n\n// Foto de la pieza según el lado y el color elegidos.\nfunction cv_esc_fotoPieza(a) {\n  const izq = cv_esc_ladoIzq(a), c = cv_esc_colorDe(a);\n  if (c) {\n    const f = izq ? (c.imagen_izq || c.imagen) : (c.imagen || c.imagen_izq);\n    if (f) return f;\n  }\n  return (izq && a.imagen_izq) ? a.imagen_izq : a.imagen;\n}\n\nfunction cv_esc_vista(cfg) {\n  return {\n    ...cfg,\n    accesorios: cfg.accesorios.map(a => {\n      const foto = cv_esc_fotoPieza(a);\n      return cv_esc_ladoIzq(a)\n        ? { ...a, imagen: foto, x: a.xi ?? a.x, y: a.yi ?? a.y, w: a.wi ?? a.w, rot: a.roti ?? a.rot }\n        : { ...a, imagen: foto };\n    }),\n  };\n}\n\nfunction cv_esc_setColor(uid, colorUid) {\n  CV_SEL.colorPieza = CV_SEL.colorPieza || {};\n  if (colorUid) CV_SEL.colorPieza[uid] = colorUid; else delete CV_SEL.colorPieza[uid];\n  cv_renderCotizar();\n}\n\nfunction cv_esc_nombreColor(a) {\n  const conColores = (a.colores || []).some(c => c.imagen || c.imagen_izq);\n  if (!conColores) return '';\n  const c = cv_esc_colorDe(a);\n  return c ? (c.nombre || '').trim() : (a.color_nombre || '').trim();\n}\n\nfunction cv_esc_htmlColores(a) {\n  const colores = (a.colores || []).filter(c => c.imagen || c.imagen_izq);\n  if (!colores.length) return '';\n  const sel = cv_esc_colorDe(a);\n  const chip = (id, nombre, hex, on) => `<button type=\"button\" class=\"${on ? 'primary' : 'secondary'}\" style=\"padding:3px 8px; font-size:11px; display:inline-flex; gap:5px; align-items:center;\"\n      onclick=\"event.stopPropagation(); cv_esc_setColor('${a.uid}', ${id ? `'${id}'` : 'null'})\"><span style=\"width:12px; height:12px; border-radius:50%; background:${escapeHtml(hex || '#ccc')}; border:1px solid rgba(0,0,0,.25);\"></span>${escapeHtml(nombre)}</button>`;\n  return `<div style=\"display:flex; gap:4px; flex-wrap:wrap; margin-top:6px;\" onclick=\"event.stopPropagation()\">\n    ${chip(null, (a.color_nombre || '').trim() || 'Original', a.color_hex || '#cccccc', !sel)}\n    ${colores.map(c => chip(c.uid, (c.nombre || '').trim() || 'Sin nombre', c.hex, sel && sel.uid === c.uid)).join('')}\n  </div>`;\n}\n\nfunction cv_esc_lugares(cfg) {\n"
  ],
  [
   "\nfunction cv_esc_htmlPiezas(cfg) {\n  return cv_esc_lugares(cfg).map((g, i) => {\n    const conIzq = g.piezas.some(a => a.imagen_izq);\n    const lado = (CV_SEL.lado || {})[g.k] === 'izq' ? 'izq' : 'der';\n    return `\n      <div style=\"display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:12px 0 6px;\">\n",
   "\nfunction cv_esc_htmlPiezas(cfg) {\n  return cv_esc_lugares(cfg).map((g, i) => {\n    const conIzq = g.piezas.some(a => a.imagen_izq || (a.colores || []).some(c => c.imagen_izq));\n    const lado = (CV_SEL.lado || {})[g.k] === 'izq' ? 'izq' : 'der';\n    return `\n      <div style=\"display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:12px 0 6px;\">\n"
  ],
  [
   "      ${g.piezas.map(a => {\n        const on = CV_SEL.activos.includes(a.uid);\n        const precio = Number(CV_SEL.precio[a.uid] ?? a.precio) || 0;\n        const foto = (lado === 'izq' && a.imagen_izq) ? a.imagen_izq : a.imagen;\n        return `\n        <div class=\"cv-acc${on ? ' on' : ''}\" onclick=\"cv_toggleAccesorio('${a.uid}')\">\n          <div class=\"cv-thumb\">${foto ? `<img src=\"${foto}\" alt=\"\" />` : '📦'}</div>\n",
   "      ${g.piezas.map(a => {\n        const on = CV_SEL.activos.includes(a.uid);\n        const precio = Number(CV_SEL.precio[a.uid] ?? a.precio) || 0;\n        const foto = cv_esc_fotoPieza(a);\n        return `\n        <div class=\"cv-acc${on ? ' on' : ''}\" onclick=\"cv_toggleAccesorio('${a.uid}')\">\n          <div class=\"cv-thumb\">${foto ? `<img src=\"${foto}\" alt=\"\" />` : '📦'}</div>\n"
  ],
  [
   "              <span style=\"font-size:18px;\">${on ? '✅' : '➕'}</span>\n            </div>\n            ${on ? cv_htmlLineaPrecio(a.uid, a, true) : `<div style=\"font-size:12px; color:var(--muted); margin-top:4px;\">$${cot_fmt(precio)}</div>`}\n          </div>\n        </div>`;\n      }).join('')}`;\n",
   "              <span style=\"font-size:18px;\">${on ? '✅' : '➕'}</span>\n            </div>\n            ${on ? cv_htmlLineaPrecio(a.uid, a, true) : `<div style=\"font-size:12px; color:var(--muted); margin-top:4px;\">$${cot_fmt(precio)}</div>`}\n            ${on ? cv_esc_htmlColores(a) : ''}\n          </div>\n        </div>`;\n      }).join('')}`;\n"
  ],
  [
   "          <button type=\"button\" class=\"secondary\" style=\"color:var(--copper); border-color:var(--copper);\" onclick=\"cv_quitarAccesorio('${a.uid}')\">✕ Quitar</button>\n        </div>\n        ${cv_htmlProductoEditor(a.uid)}\n      </div>`;\n    }).join('')}\n    <button type=\"button\" class=\"secondary\" onclick=\"cv_agregarAccesorio()\">+ Agregar pieza</button>\n",
   "          <button type=\"button\" class=\"secondary\" style=\"color:var(--copper); border-color:var(--copper);\" onclick=\"cv_quitarAccesorio('${a.uid}')\">✕ Quitar</button>\n        </div>\n        ${cv_htmlProductoEditor(a.uid)}\n        ${cv_esc_htmlEditorColores(a)}\n        <div style=\"margin-top:8px;\"><button type=\"button\" class=\"secondary\" onclick=\"cv_esc_duplicar('${a.uid}')\" title=\"Copia el lugar, la posición y el tamaño de esta pieza (para dar de alta otro modelo igual de acomodado)\">⧉ Duplicar pieza (otro modelo en el mismo lugar)</button></div>\n      </div>`;\n    }).join('')}\n    <button type=\"button\" class=\"secondary\" onclick=\"cv_agregarAccesorio()\">+ Agregar pieza</button>\n"
  ],
  [
   "    </div>\n  `;\n  cv_activarArrastre();\n}\n\nasync function cv_esc_guardar(boton) {\n",
   "    </div>\n  `;\n  cv_activarArrastre();\n}\n\n// ---- Colores de una pieza (editor del equipo especial) ----\n// Cada color lleva su foto derecha (imagen) e izquierda (imagen_izq); usan la\n// misma posición y tamaño que la pieza, así que deben ser la misma toma.\n\nfunction cv_esc_htmlEditorColores(a) {\n  const colores = a.colores || [];\n  const thumb = (src) => `<div class=\"cv-thumb\" style=\"width:46px; height:46px;\">${src ? `<img src=\"${src}\" alt=\"\" />` : '—'}</div>`;\n  return `\n    <div class=\"cv-caja\" style=\"margin-top:8px;\">\n      <div style=\"font-size:12px; font-weight:600; margin-bottom:6px;\">🎨 Colores de esta pieza (opcional)</div>\n      <div class=\"row-2\">\n        <div class=\"field\" style=\"margin:0;\"><label>Color de la foto principal</label><input value=\"${escapeHtml(a.color_nombre || '')}\" placeholder=\"ej. Gris medio\" oninput=\"cv_setProd('${a.uid}','color_nombre',this.value)\" /></div>\n        <div class=\"field\" style=\"margin:0;\"><label>Muestra</label><input type=\"color\" value=\"${escapeHtml(a.color_hex || '#cccccc')}\" onchange=\"cv_setProd('${a.uid}','color_hex',this.value)\" style=\"height:38px; padding:2px;\" /></div>\n      </div>\n      ${colores.map(c => `\n        <div style=\"display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-top:8px; border-top:1px solid rgba(155,157,159,0.25); padding-top:8px;\">\n          <input type=\"color\" value=\"${escapeHtml(c.hex || '#cccccc')}\" onchange=\"cv_esc_setColorCampo('${a.uid}','${c.uid}','hex',this.value)\" style=\"width:42px; height:36px; padding:2px;\" />\n          <input value=\"${escapeHtml(c.nombre || '')}\" placeholder=\"Nombre del color\" oninput=\"cv_esc_setColorCampo('${a.uid}','${c.uid}','nombre',this.value)\" style=\"flex:1; min-width:120px;\" />\n          <div style=\"text-align:center;\">${thumb(c.imagen_izq)}<div style=\"font-size:9px; color:var(--muted);\">◀ izq</div></div>\n          <div style=\"text-align:center;\">${thumb(c.imagen)}<div style=\"font-size:9px; color:var(--muted);\">der ▶</div></div>\n          <button type=\"button\" class=\"secondary\" style=\"padding:4px 8px; font-size:11px;\" onclick=\"cv_esc_fotoColor('${a.uid}','${c.uid}','izq')\">📷 Izquierda</button>\n          <button type=\"button\" class=\"secondary\" style=\"padding:4px 8px; font-size:11px;\" onclick=\"cv_esc_fotoColor('${a.uid}','${c.uid}','der')\">📷 Derecha</button>\n          <button type=\"button\" class=\"secondary\" style=\"padding:4px 8px; font-size:11px; color:var(--copper); border-color:var(--copper);\" onclick=\"cv_esc_quitarColor('${a.uid}','${c.uid}')\">✕</button>\n        </div>`).join('')}\n      <button type=\"button\" class=\"secondary\" style=\"margin-top:8px; padding:4px 10px; font-size:12px;\" onclick=\"cv_esc_agregarColor('${a.uid}')\">+ Color</button>\n      <div style=\"font-size:11px; color:var(--muted); margin-top:4px;\">Sube cada color sin fondo (PNG), con el mismo encuadre que la foto principal de la pieza.</div>\n    </div>`;\n}\n\nfunction cv_esc_agregarColor(uid) {\n  const a = cv_prod(uid);\n  if (!a) return;\n  a.colores = a.colores || [];\n  a.colores.push({ uid: cv_uid(), nombre: '', hex: '#cccccc', imagen: null, imagen_izq: null });\n  cv_renderEditor();\n}\n\nfunction cv_esc_setColorCampo(uid, cuid, campo, valor) {\n  const c = ((cv_prod(uid) || {}).colores || []).find(x => x.uid === cuid);\n  if (c) c[campo] = valor;\n}\n\nfunction cv_esc_quitarColor(uid, cuid) {\n  const a = cv_prod(uid);\n  if (!a || !confirm('¿Quitar este color?')) return;\n  a.colores = (a.colores || []).filter(x => x.uid !== cuid);\n  cv_renderEditor();\n}\n\nfunction cv_esc_fotoColor(uid, cuid, lado) {\n  const inp = document.createElement('input');\n  inp.type = 'file';\n  inp.accept = 'image/*';\n  inp.onchange = async () => {\n    const f = inp.files && inp.files[0];\n    const c = ((cv_prod(uid) || {}).colores || []).find(x => x.uid === cuid);\n    if (!f || !c) return;\n    try {\n      c[lado === 'izq' ? 'imagen_izq' : 'imagen'] = await cv_recortarVisible(await cv_leerArchivoImagen(f, 1000, false));\n      cv_renderEditor();\n    } catch (e) { alert(e.message); }\n  };\n  inp.click();\n}\n\n// Copia una pieza (lugar, posición y tamaño de los dos lados) para dar de\n// alta otro modelo en el mismo lugar sin volver a acomodarlo.\nfunction cv_esc_duplicar(uid) {\n  const a = cv_prod(uid);\n  if (!a) return;\n  const zMax = CV_EDIT.config.accesorios.reduce((m, x) => Math.max(m, x.z || 0), 0);\n  const copia = JSON.parse(JSON.stringify(a));\n  Object.assign(copia, { uid: cv_uid(), nombre: `${a.nombre || 'Pieza'} (copia)`, articulo_id: null, clave: null, por_defecto: false,\n                         colores: [], z: zMax + 1 });\n  const i = CV_EDIT.config.accesorios.findIndex(x => x.uid === uid);\n  CV_EDIT.config.accesorios.splice(i + 1, 0, copia);\n  CV_EDIT_SEL = copia.uid;\n  cv_renderEditor();\n  const el = document.getElementById(`cv_nom_${copia.uid}`);\n  if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.select(); }\n}\n\nasync function cv_esc_guardar(boton) {\n"
  ],
  [
   "  if (sinLugar) { alert(`A \"${sinLugar.nombre}\" le falta el lugar (ej. Unidad, Compresor).`); return; }\n  const sinFoto = c.accesorios.find(a => !a.imagen && !a.imagen_izq);\n  if (sinFoto) { alert(`A \"${sinFoto.nombre}\" le falta su foto.`); return; }\n  c.accesorios.forEach(a => {\n    a.lugar = a.lugar.trim();\n    a.grupo = a.lugar;\n",
   "  if (sinLugar) { alert(`A \"${sinLugar.nombre}\" le falta el lugar (ej. Unidad, Compresor).`); return; }\n  const sinFoto = c.accesorios.find(a => !a.imagen && !a.imagen_izq);\n  if (sinFoto) { alert(`A \"${sinFoto.nombre}\" le falta su foto.`); return; }\n  for (const a of c.accesorios) {\n    a.colores = (a.colores || []).filter(col => col.imagen || col.imagen_izq || (col.nombre || '').trim());\n    const sinNombreColor = a.colores.find(col => !(col.nombre || '').trim());\n    if (sinNombreColor) { alert(`\"${a.nombre}\" tiene un color sin nombre — escríbelo o quítalo.`); return; }\n    const sinFotoColor = a.colores.find(col => !col.imagen && !col.imagen_izq);\n    if (sinFotoColor) { alert(`El color \"${sinFotoColor.nombre}\" de \"${a.nombre}\" no tiene foto.`); return; }\n  }\n  c.accesorios.forEach(a => {\n    a.lugar = a.lugar.trim();\n    a.grupo = a.lugar;\n"
  ],
  [
   "  }\n  c.base = { ...cv_productoVacio(), ...(c.base || {}) };\n  c.accesorios = (c.accesorios || []).map(a => ({ ...cv_productoVacio(), x: 0.5, y: 0.5, w: 0.25, rot: 0, z: 0, grupo: '',\n                                                  ...(c.tipo === 'escena' ? { lugar: a.grupo || '', imagen_izq: null, por_defecto: false } : {}), ...a }));\n  c.combos = (c.combos || []).map(cb => ({ uid: cv_uid(), nombre: '', descuento_pct: 0, incluye_base: true, por_defecto: false, requiere: [], ...cb }));\n  c.colores = (c.colores || []).map(col => ({ uid: cv_uid(), nombre: '', hex: '#cccccc', imagen: null, ...col }));\n  cv_renderEditor();\n",
   "  }\n  c.base = { ...cv_productoVacio(), ...(c.base || {}) };\n  c.accesorios = (c.accesorios || []).map(a => ({ ...cv_productoVacio(), x: 0.5, y: 0.5, w: 0.25, rot: 0, z: 0, grupo: '',\n                                                  ...(c.tipo === 'escena' ? { lugar: a.grupo || '', imagen_izq: null, por_defecto: false, color_nombre: '', colores: [] } : {}), ...a }));\n  c.combos = (c.combos || []).map(cb => ({ uid: cv_uid(), nombre: '', descuento_pct: 0, incluye_base: true, por_defecto: false, requiere: [], ...cb }));\n  c.colores = (c.colores || []).map(col => ({ uid: cv_uid(), nombre: '', hex: '#cccccc', imagen: null, ...col }));\n  cv_renderEditor();\n"
  ],
  [
   "      // y \"imagen_izq\" la del otro lado (ver cv_esc_swap).\n      const campo = (escena && lado && lado !== CV_EDIT_LADO) ? 'imagen_izq' : 'imagen';\n      if (key === CV_BASE) p.imagen = await cv_leerFotoPrincipal(f);\n      else if (escena) p[campo] = await cv_recortarVisible(await cv_leerArchivoImagen(f, 1400, false));\n      else p[campo] = await cv_leerArchivoImagen(f, 900, false);\n      if (campo === 'imagen') delete CV_DESHACER[key];\n      if (key !== CV_BASE && campo === 'imagen') CV_EDIT_SEL = key;\n",
   "      // y \"imagen_izq\" la del otro lado (ver cv_esc_swap).\n      const campo = (escena && lado && lado !== CV_EDIT_LADO) ? 'imagen_izq' : 'imagen';\n      if (key === CV_BASE) p.imagen = await cv_leerFotoPrincipal(f);\n      else if (escena) p[campo] = await cv_recortarVisible(await cv_leerArchivoImagen(f, 1000, false));\n      else p[campo] = await cv_leerArchivoImagen(f, 900, false);\n      if (campo === 'imagen') delete CV_DESHACER[key];\n      if (key !== CV_BASE && campo === 'imagen') CV_EDIT_SEL = key;\n"
  ],
  [
   "\nlet COT_WA = null;\n\nfunction cot_numeroWhatsApp(telefono) {\n  const d = (telefono || '').replace(/\\D/g, '');\n  // 10 dígitos = número mexicano (se le antepone 52); con más dígitos ya trae lada de país.\n",
   "\nlet COT_WA = null;\n\nfunction cot_mensajeWhatsApp(cotizacion) {\n  return `Hola ${cotizacion.cliente_nombre}, ¡gracias por cotizar con Mark Inc & Peymar! `\n    + `Te compartimos tu cotización ${cotizacion.folio} por un total de $${cot_fmt(cotizacion.total)} (va en el PDF adjunto). `\n    + `Te invitamos a visitar nuestra página: www.markinc.com.mx`;\n}\n\nfunction cot_copiarTexto(texto) {\n  try { if (navigator.clipboard) navigator.clipboard.writeText(texto).catch(() => {}); } catch (e) { /* sin portapapeles */ }\n}\n\nfunction cot_numeroWhatsApp(telefono) {\n  const d = (telefono || '').replace(/\\D/g, '');\n  // 10 dígitos = número mexicano (se le antepone 52); con más dígitos ya trae lada de país.\n"
  ],
  [
   "}\n\nasync function cot_abrirWhatsApp(cotizacion) {\n  const texto = `Hola ${cotizacion.cliente_nombre}, te comparto tu cotización ${cotizacion.folio} por un total de $${cot_fmt(cotizacion.total)}.`;\n  let archivo;\n  try {\n    const r = await fetch(`/api/cotizaciones/${cotizacion.id}/pdf`, { headers: headers(false) });\n",
   "}\n\nasync function cot_abrirWhatsApp(cotizacion) {\n  const texto = cot_mensajeWhatsApp(cotizacion);\n  let archivo;\n  try {\n    const r = await fetch(`/api/cotizaciones/${cotizacion.id}/pdf`, { headers: headers(false) });\n"
  ],
  [
   "    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2 style=\"margin-bottom:6px;\">💬 Enviar por WhatsApp</h2>\n    <p style=\"font-size:13px; color:var(--muted); margin-top:0;\">Cotización <b>${escapeHtml(cotizacion.folio)}</b> — ${escapeHtml(cotizacion.cliente_nombre)} · el PDF va como archivo.</p>\n    ${compartible ? `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waCompartir()\">📤 Mandar PDF (elige WhatsApp)</button>\n      <p style=\"font-size:11px; color:var(--muted);\">Se abre \"Compartir\": toca WhatsApp y luego el contacto del cliente.</p>` : `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waComputadora()\">⬇️ Descargar PDF y abrir el chat</button>\n      <p style=\"font-size:11px; color:var(--muted);\">En la computadora WhatsApp no deja adjuntar solo: se descarga el PDF y se abre el chat${COT_WA.numero ? ' del cliente' : ''}; arrastra el PDF ahí.</p>`}`;\n  abrirModal();\n",
   "    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2 style=\"margin-bottom:6px;\">💬 Enviar por WhatsApp</h2>\n    <p style=\"font-size:13px; color:var(--muted); margin-top:0;\">Cotización <b>${escapeHtml(cotizacion.folio)}</b> — ${escapeHtml(cotizacion.cliente_nombre)} · el PDF va como archivo.</p>\n    <div class=\"cv-caja\" style=\"font-size:12px; margin-bottom:10px;\">${escapeHtml(texto)}</div>\n    ${compartible ? `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waCompartir()\">📤 Mandar PDF (elige WhatsApp)</button>\n      <p style=\"font-size:11px; color:var(--muted);\">Se abre \"Compartir\": toca WhatsApp y luego el contacto del cliente. El mensaje de agradecimiento también queda copiado: si WhatsApp no lo pone solo, déjalo presionado y pega.</p>` : `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waComputadora()\">⬇️ Descargar PDF y abrir el chat</button>\n      <p style=\"font-size:11px; color:var(--muted);\">En la computadora WhatsApp no deja adjuntar solo: se descarga el PDF y se abre el chat${COT_WA.numero ? ' del cliente' : ''}; arrastra el PDF ahí.</p>`}`;\n  abrirModal();\n"
  ],
  [
   "async function cot_waCompartir() {\n  const w = COT_WA;\n  if (!w) return;\n  try {\n    await navigator.share({ files: [w.archivo], text: w.texto, title: `Cotización ${w.folio}` });\n    cerrarModal();\n",
   "async function cot_waCompartir() {\n  const w = COT_WA;\n  if (!w) return;\n  cot_copiarTexto(w.texto); // por si WhatsApp no toma el mensaje junto con el archivo: se pega\n  try {\n    await navigator.share({ files: [w.archivo], text: w.texto, title: `Cotización ${w.folio}` });\n    cerrarModal();\n"
  ],
  [
   "function cot_waComputadora() {\n  const w = COT_WA;\n  if (!w) return;\n  const url = URL.createObjectURL(w.archivo);\n  const a = document.createElement('a');\n  a.href = url; a.download = w.archivo.name;\n",
   "function cot_waComputadora() {\n  const w = COT_WA;\n  if (!w) return;\n  cot_copiarTexto(w.texto);\n  const url = URL.createObjectURL(w.archivo);\n  const a = document.createElement('a');\n  a.href = url; a.download = w.archivo.name;\n"
  ]
 ],
 "backend/db.py": [
  [
   "        -- cada cotización (justo después del total) para que el cliente\n        -- sepa cómo pagar si la acepta.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS datos_pago_cotizacion TEXT;\n\n        CREATE TABLE IF NOT EXISTS videos_subidos (\n            id SERIAL PRIMARY KEY,\n",
   "        -- cada cotización (justo después del total) para que el cliente\n        -- sepa cómo pagar si la acepta.\n        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS datos_pago_cotizacion TEXT;\n        -- Cuentas bancarias de Mark·Inc en el PDF de las cotizaciones (solo si\n        -- nunca se han capturado; después se editan en Administrar -> Empresas).\n        UPDATE empresas SET datos_pago_cotizacion = 'BBVA Bancomer\nNo. de Cuenta 0189802797\nCLABE 012650001898027975\n\nBanamex\nNo. de Cuenta 2871449 · Sucursal 7000\nCLABE 002650700028714495\n\nSantander\nNo. de Cuenta 65504304515\nCLABE 014650655043045156\n\nA nombre de Productos Dentales Mark Inc S. de R.L. de C.V.'\n        WHERE datos_pago_cotizacion IS NULL AND (nombre ILIKE '%%mark%%');\n\n        CREATE TABLE IF NOT EXISTS videos_subidos (\n            id SERIAL PRIMARY KEY,\n"
  ],
  [
   "    cur.execute(\n        \"\"\"SELECT id, nombre, logo_base64, activo, creado_en, politicas_texto,\n                  tema, color_acento, fondo_color, fondo_base64,\n                  limite_almacenamiento_videos_mb\n           FROM empresas WHERE id = %s\"\"\",\n        (empresa_id,),\n    )\n",
   "    cur.execute(\n        \"\"\"SELECT id, nombre, logo_base64, activo, creado_en, politicas_texto,\n                  tema, color_acento, fondo_color, fondo_base64,\n                  limite_almacenamiento_videos_mb, datos_pago_cotizacion\n           FROM empresas WHERE id = %s\"\"\",\n        (empresa_id,),\n    )\n"
  ]
 ],
 "backend/pdfs_cotizaciones.py": [
  [
   "\n\ndef _bloque_datos_pago(elementos, styles, cot, ctx):\n    \"\"\"Datos de pago (ej. cuenta bancaria) configurados por el superadmin\n    desde Administrar -> Empresas -> Datos de pago (uno por empresa) — solo\n    se dibuja si se llenaron, para no dejar un hueco vacío en empresas que\n    no los hayan configurado.\"\"\"\n    texto = ctx.get(\"datos_pago\")\n    if not texto:\n        return False\n    elementos.append(Paragraph(\"Cómo pagar\", styles[\"Seccion\"]))\n    texto_html = (\n        texto.replace(\"&\", \"&amp;\").replace(\"<\", \"&lt;\").replace(\">\", \"&gt;\").replace(\"\\n\", \"<br/>\")\n    )\n    elementos.append(Paragraph(texto_html, styles[\"Cuerpo\"]))\n    return True\n\n\n",
   "\n\ndef _bloque_datos_pago(elementos, styles, cot, ctx):\n    \"\"\"Datos de pago (cuentas bancarias) configurados por el superadmin\n    desde Administrar -> Empresas -> Datos de pago (uno por empresa) — solo\n    se dibuja si se llenaron, para no dejar un hueco vacío en empresas que\n    no los hayan configurado.\n\n    Formato libre, un renglón por línea; se acomoda en un recuadro:\n      - renglones SIN números (nombre del banco, \"A nombre de…\") van en negritas\n      - un renglón vacío separa un banco del siguiente (se reparten en columnas).\"\"\"\n    texto = (ctx.get(\"datos_pago\") or \"\").strip()\n    if not texto:\n        return False\n    factor = ctx.get(\"factor\", 1.0)\n    esc = lambda t: t.replace(\"&\", \"&amp;\").replace(\"<\", \"&lt;\").replace(\">\", \"&gt;\")\n    est_banco = ParagraphStyle(\"PagoBanco\", parent=styles[\"Cuerpo\"], fontName=\"Helvetica-Bold\", fontSize=9.5 * factor,\n                               textColor=NEGRO, leading=12 * factor)\n    est_dato = ParagraphStyle(\"PagoDato\", parent=styles[\"Cuerpo\"], fontSize=8.5 * factor, leading=11 * factor)\n    est_pie = ParagraphStyle(\"PagoPie\", parent=styles[\"Cuerpo\"], fontName=\"Helvetica-Bold\", fontSize=9 * factor,\n                             textColor=colors.white, alignment=1, leading=11 * factor)\n\n    grupos = [[l.strip() for l in g.splitlines() if l.strip()] for g in texto.replace(\"\\r\", \"\").split(\"\\n\\n\")]\n    grupos = [g for g in grupos if g]\n    # Un último grupo de un solo renglón sin números (\"A nombre de …\") va como franja roja abajo.\n    pie = None\n    if len(grupos) > 1 and len(grupos[-1]) <= 2 and not any(ch.isdigit() for ch in \" \".join(grupos[-1])):\n        pie = \" \".join(grupos.pop())\n\n    def celda(grupo):\n        return [Paragraph(esc(l), est_banco if not any(ch.isdigit() for ch in l) else est_dato) for l in grupo]\n\n    elementos.append(Paragraph(\"Cómo pagar\", styles[\"Seccion\"]))\n    ancho = 17.5 * cm\n    por_fila = min(3, len(grupos)) or 1\n    filas = [grupos[i:i + por_fila] for i in range(0, len(grupos), por_fila)]\n    datos = [[celda(g) for g in fila] + [\"\"] * (por_fila - len(fila)) for fila in filas]\n    tabla = Table(datos, colWidths=[ancho / por_fila] * por_fila)\n    tabla.setStyle(TableStyle([\n        (\"BOX\", (0, 0), (-1, -1), 0.8, GRIS),\n        (\"INNERGRID\", (0, 0), (-1, -1), 0.4, GRIS_CLARO),\n        (\"BACKGROUND\", (0, 0), (-1, -1), colors.white),\n        (\"VALIGN\", (0, 0), (-1, -1), \"TOP\"),\n        (\"TOPPADDING\", (0, 0), (-1, -1), 6), (\"BOTTOMPADDING\", (0, 0), (-1, -1), 6),\n        (\"LEFTPADDING\", (0, 0), (-1, -1), 8), (\"RIGHTPADDING\", (0, 0), (-1, -1), 8),\n    ]))\n    elementos.append(tabla)\n    if pie:\n        franja = Table([[Paragraph(esc(pie), est_pie)]], colWidths=[ancho])\n        franja.setStyle(TableStyle([\n            (\"BACKGROUND\", (0, 0), (-1, -1), ROJO),\n            (\"TOPPADDING\", (0, 0), (-1, -1), 5), (\"BOTTOMPADDING\", (0, 0), (-1, -1), 5),\n        ]))\n        elementos.append(franja)\n    return True\n\n\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    if not os.path.exists("backend/paqueterias.py"):
        print("Primero corre fix_paqueterias_varias.py y fix_whatsapp_pdf.py (y luego este).")
        sys.exit(1)
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    bin_cambios = {}
    for ruta, b64 in NUEVOS_BIN.items():
        datos = base64.b64decode(b64)
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                if f.read() == datos:
                    continue
        bin_cambios[ruta] = datos
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        # Windows: el archivo puede tener saltos CRLF, LF o una mezcla.
        # Se trabaja todo en LF y al guardar se deja como estaba (CRLF si tenia).
        crlf = "\r\n" in original
        texto = original.replace("\r\n", "\n")
        inicial = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue  # ya aplicado
            n = texto.count(viejo)
            if n != 1:
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
                continue
            texto = texto.replace(viejo, nuevo, 1)
        if texto != inicial:
            cambios[ruta] = texto.replace("\n", "\r\n") if crlf else texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, datos in bin_cambios.items():
        with open(ruta, "wb") as f:
            f.write(datos)
        print("Actualizado:", ruta)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios and not bin_cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
