# -*- coding: utf-8 -*-
"""
COTIZADOR DE LA PLATAFORMA (superadmin): PDF Y WHATSAPP, TAMBIEN DESDE LA APP
- Campo "WhatsApp del cliente" (se guarda con la cotizacion).
- Botones "Enviar cotizacion por WhatsApp" y "Enviar acta de entrega por WhatsApp".
  Celular: hoja de compartir con el PDF. Computadora: descarga el PDF y abre el chat.
- Dentro de las apps (Mark·Inc y Peymar) los botones de PDF le pasan el archivo
  a la app, que abre la hoja de Compartir (WhatsApp, Archivos, correo...).
Toca: frontend/cotizador_costos.html
Se puede correr varias veces.  Correr con:  py -3 fix_cotizador_whatsapp_app.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "frontend/cotizador_costos.html": [
  [
   "  .growth-item{ display:flex; align-items:flex-start; gap:8px; padding:6px 0; font-size:0.82rem; }\n  .growth-item input{ accent-color:var(--rojo); margin-top:3px; }\n\n  .download-btn{\n    width:100%; margin-top:24px; padding:13px; border:1px solid var(--rojo-oscuro); border-radius:8px;\n    background:linear-gradient(180deg, #ED3A50 0%, var(--rojo) 55%, var(--rojo-oscuro) 100%); color:#fff; font-family:var(--font-body); font-weight:700; font-size:0.92rem;\n",
   "  .growth-item{ display:flex; align-items:flex-start; gap:8px; padding:6px 0; font-size:0.82rem; }\n  .growth-item input{ accent-color:var(--rojo); margin-top:3px; }\n\n  .download-btn.btn-wa{ margin-top:10px; background:linear-gradient(180deg, #2BD46A 0%, #1FAF55 55%, #178A43 100%); border-color:#178A43; box-shadow:0 4px 14px rgba(31,175,85,0.30), inset 0 1px 0 rgba(255,255,255,0.2); }\n  .download-btn{\n    width:100%; margin-top:24px; padding:13px; border:1px solid var(--rojo-oscuro); border-radius:8px;\n    background:linear-gradient(180deg, #ED3A50 0%, var(--rojo) 55%, var(--rojo-oscuro) 100%); color:#fff; font-family:var(--font-body); font-weight:700; font-size:0.92rem;\n"
  ],
  [
   "      <label class=\"field\"><span class=\"lbl\">Folio</span><input type=\"text\" id=\"c-folio\" placeholder=\"COT-SW-0001\"></label>\n      <label class=\"field\"><span class=\"lbl\">Fecha</span><input type=\"date\" id=\"c-fecha\"></label>\n    </div>\n    <label class=\"field\"><span class=\"lbl\">Giro del cliente (opcional)</span><input type=\"text\" id=\"c-giro\" placeholder=\"Ej. clínica dental, ferretería, distribuidora…\"></label>\n    <label class=\"field\"><span class=\"lbl\">Texto bajo tu logo</span><input type=\"text\" id=\"c-marca\" value=\"SISTEMAS Y SOFTWARE A LA MEDIDA\"></label>\n    <div id=\"carga-aviso\" style=\"font-size:0.78rem;color:var(--gris-1);\"></div>\n",
   "      <label class=\"field\"><span class=\"lbl\">Folio</span><input type=\"text\" id=\"c-folio\" placeholder=\"COT-SW-0001\"></label>\n      <label class=\"field\"><span class=\"lbl\">Fecha</span><input type=\"date\" id=\"c-fecha\"></label>\n    </div>\n    <label class=\"field\"><span class=\"lbl\">WhatsApp del cliente (opcional)</span><input type=\"tel\" id=\"c-whatsapp\" placeholder=\"10 dígitos, ej. 2221234567\"></label>\n    <label class=\"field\"><span class=\"lbl\">Giro del cliente (opcional)</span><input type=\"text\" id=\"c-giro\" placeholder=\"Ej. clínica dental, ferretería, distribuidora…\"></label>\n    <label class=\"field\"><span class=\"lbl\">Texto bajo tu logo</span><input type=\"text\" id=\"c-marca\" value=\"SISTEMAS Y SOFTWARE A LA MEDIDA\"></label>\n    <div id=\"carga-aviso\" style=\"font-size:0.78rem;color:var(--gris-1);\"></div>\n"
  ],
  [
   "\n    <button class=\"download-btn\" id=\"btn-guardar\" style=\"background:var(--tinta);\">Guardar en el sistema</button>\n    <button class=\"download-btn\" id=\"btn-pdf\">Descargar cotización en PDF</button>\n    <button class=\"download-btn\" id=\"btn-entrega-pdf\" style=\"display:none;\">Descargar acta de entrega (PDF)</button>\n    <div class=\"hint\" id=\"pdf-hint\">\"Guardar\" deja esta configuración ligada a la empresa; el PDF es lo que le compartes al cliente.</div>\n  </div>\n\n",
   "\n    <button class=\"download-btn\" id=\"btn-guardar\" style=\"background:var(--tinta);\">Guardar en el sistema</button>\n    <button class=\"download-btn\" id=\"btn-pdf\">Descargar cotización en PDF</button>\n    <button class=\"download-btn btn-wa\" id=\"btn-pdf-wa\">Enviar cotización por WhatsApp</button>\n    <button class=\"download-btn\" id=\"btn-entrega-pdf\" style=\"display:none;\">Descargar acta de entrega (PDF)</button>\n    <button class=\"download-btn btn-wa\" id=\"btn-entrega-wa\" style=\"display:none;\">Enviar acta de entrega por WhatsApp</button>\n    <div class=\"hint\" id=\"pdf-hint\">\"Guardar\" deja esta configuración ligada a la empresa; el PDF es lo que le compartes al cliente.</div>\n  </div>\n\n"
  ],
  [
   "}\n\n// ---------- listeners de campos de cliente / notas / toggles ----------\n['c-empresa','c-contacto','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas','c-datos-pago'].forEach(id=>{\n  document.getElementById(id).addEventListener('input', renderPreview);\n});\ndocument.getElementById('c-folio').addEventListener('input', e=>{ e.target.dataset.autogenerado = '0'; });\n",
   "}\n\n// ---------- listeners de campos de cliente / notas / toggles ----------\n['c-empresa','c-contacto','c-whatsapp','c-folio','c-fecha','c-giro','c-marca','c-intro','c-notas','c-datos-pago'].forEach(id=>{\n  document.getElementById(id).addEventListener('input', renderPreview);\n});\ndocument.getElementById('c-folio').addEventListener('input', e=>{ e.target.dataset.autogenerado = '0'; });\n"
  ],
  [
   "  try{\n    const blob = await buildPdfBlob();\n    const folio = (document.getElementById('c-folio').value || 'cotizacion').replace(/[^a-z0-9\\-]/gi,'_');\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url; a.download = folio + '.pdf';\n    document.body.appendChild(a); a.click(); a.remove();\n    setTimeout(()=>URL.revokeObjectURL(url), 4000);\n    hint.textContent = 'PDF descargado.';\n  } catch(e){\n    hint.textContent = 'Ocurrió un error generando el PDF.';\n    console.error(e);\n",
   "  try{\n    const blob = await buildPdfBlob();\n    const folio = (document.getElementById('c-folio').value || 'cotizacion').replace(/[^a-z0-9\\-]/gi,'_');\n    hint.textContent = await entregarPdf(blob, folio + '.pdf', 'descargar', 'cotización');\n  } catch(e){\n    hint.textContent = 'Ocurrió un error generando el PDF.';\n    console.error(e);\n"
  ],
  [
   "  const on = this.checked;\n  document.getElementById('entrega-fields').style.display = on ? 'block' : 'none';\n  document.getElementById('btn-entrega-pdf').style.display = on ? 'block' : 'none';\n});\n\nasync function buildEntregaPdfBlob(){\n",
   "  const on = this.checked;\n  document.getElementById('entrega-fields').style.display = on ? 'block' : 'none';\n  document.getElementById('btn-entrega-pdf').style.display = on ? 'block' : 'none';\n  document.getElementById('btn-entrega-wa').style.display = on ? 'block' : 'none';\n});\n\nasync function buildEntregaPdfBlob(){\n"
  ],
  [
   "  try{\n    const blob = await buildEntregaPdfBlob();\n    const folio = (document.getElementById('c-folio').value || 'entrega').replace(/[^a-z0-9\\-]/gi,'_');\n    const url = URL.createObjectURL(blob);\n    const a = document.createElement('a');\n    a.href = url; a.download = 'acta_entrega_' + folio + '.pdf';\n    document.body.appendChild(a); a.click(); a.remove();\n    setTimeout(()=>URL.revokeObjectURL(url), 4000);\n    hint.textContent = 'Acta de entrega descargada.';\n  } catch(e){\n    hint.textContent = 'Ocurrió un error generando el acta de entrega.';\n    console.error(e);\n",
   "  try{\n    const blob = await buildEntregaPdfBlob();\n    const folio = (document.getElementById('c-folio').value || 'entrega').replace(/[^a-z0-9\\-]/gi,'_');\n    hint.textContent = await entregarPdf(blob, 'acta_entrega_' + folio + '.pdf', 'descargar', 'acta de entrega');\n  } catch(e){\n    hint.textContent = 'Ocurrió un error generando el acta de entrega.';\n    console.error(e);\n"
  ],
  [
   "    btn.disabled = false; btn.textContent = original;\n  }\n});\n\n// ==================================================================\n// ---- Integración con tickets-ti: cargar/guardar por empresa ----\n",
   "    btn.disabled = false; btn.textContent = original;\n  }\n});\n\n// ==================================================================\n// ---- Entregar el PDF: descargar o mandar por WhatsApp ----\n// En la web se descarga (o se comparte con la hoja del celular). Dentro\n// de la app (superadmin → Plataforma → Cotizador) el visor no descarga\n// archivos: el PDF se le pasa a la app (canal AppMovil) y ella abre la\n// hoja de Compartir (WhatsApp, guardar en Archivos, correo…).\n// ==================================================================\nfunction _blobABase64(blob){\n  return new Promise((ok, mal) => {\n    const fr = new FileReader();\n    fr.onload = () => ok(String(fr.result).split(',')[1] || '');\n    fr.onerror = () => mal(fr.error);\n    fr.readAsDataURL(blob);\n  });\n}\nfunction _telefonoWhatsApp(){\n  const d = (document.getElementById('c-whatsapp').value || '').replace(/\\D/g, '');\n  if(d.length === 10) return '52' + d;\n  return d.length > 10 ? d : '';\n}\nfunction _mensajeWhatsApp(que){\n  const contacto = document.getElementById('c-contacto').value.trim();\n  const folio = document.getElementById('c-folio').value.trim();\n  return 'Hola' + (contacto ? ' ' + contacto : '') + ', te comparto ' + (que === 'acta de entrega' ? 'el acta de entrega' : 'la cotización')\n    + (folio ? ' ' + folio : '') + '. Quedo atento a cualquier duda.';\n}\nasync function entregarPdf(blob, nombre, modo, que){\n  const texto = _mensajeWhatsApp(que);\n  const telefono = _telefonoWhatsApp();\n  if(window.AppMovil && typeof window.AppMovil.postMessage === 'function'){\n    const base64 = await _blobABase64(blob);\n    window.AppMovil.postMessage(JSON.stringify({ accion: modo, nombre, base64, texto: modo === 'whatsapp' ? texto : '', telefono }));\n    return modo === 'whatsapp' ? 'Elige WhatsApp y el contacto para mandar el PDF.' : 'Elige dónde guardar o compartir el PDF.';\n  }\n  if(modo === 'whatsapp'){\n    const archivo = new File([blob], nombre, { type: 'application/pdf' });\n    if(navigator.canShare && navigator.canShare({ files: [archivo] })){\n      try{ await navigator.share({ files: [archivo], text: texto }); return 'Listo: elige WhatsApp en la hoja de compartir.'; }\n      catch(e){ if(e && e.name === 'AbortError') return 'Envío cancelado.'; }\n    }\n  }\n  const url = URL.createObjectURL(blob);\n  const a = document.createElement('a');\n  a.href = url; a.download = nombre;\n  document.body.appendChild(a); a.click(); a.remove();\n  setTimeout(()=>URL.revokeObjectURL(url), 4000);\n  if(modo !== 'whatsapp') return (que === 'acta de entrega' ? 'Acta de entrega descargada.' : 'PDF descargado.');\n  // Computadora: WhatsApp no deja adjuntar por liga; se abre el chat con el\n  // mensaje y el PDF ya descargado solo se arrastra / adjunta.\n  window.open('https://wa.me/' + telefono + '?text=' + encodeURIComponent(texto), '_blank');\n  return 'Se descargó el PDF y se abrió WhatsApp: adjúntalo en el chat.';\n}\nfunction _botonWhatsApp(idBoton, construir, prefijo, que){\n  document.getElementById(idBoton).addEventListener('click', async () => {\n    const btn = document.getElementById(idBoton);\n    const hint = document.getElementById('pdf-hint');\n    const original = btn.textContent;\n    btn.disabled = true; btn.textContent = 'Generando…';\n    try{\n      const blob = await construir();\n      const folio = (document.getElementById('c-folio').value || prefijo).replace(/[^a-z0-9\\-]/gi,'_');\n      hint.textContent = await entregarPdf(blob, (que === 'acta de entrega' ? 'acta_entrega_' : '') + folio + '.pdf', 'whatsapp', que);\n    } catch(e){\n      hint.textContent = 'Ocurrió un error generando el PDF.';\n      console.error(e);\n    } finally {\n      btn.disabled = false; btn.textContent = original;\n    }\n  });\n}\n_botonWhatsApp('btn-pdf-wa', () => buildPdfBlob(), 'cotizacion', 'cotización');\n_botonWhatsApp('btn-entrega-wa', () => buildEntregaPdfBlob(), 'entrega', 'acta de entrega');\n\n// ==================================================================\n// ---- Integración con tickets-ti: cargar/guardar por empresa ----\n"
  ],
  [
   "  return h;\n}\nwindow.volverAlPanel = function(){\n  if(window.opener && !window.opener.closed){ window.close(); } else { location.href = '/'; }\n};\n\n",
   "  return h;\n}\nwindow.volverAlPanel = function(){\n  if(window.AppMovil && typeof window.AppMovil.postMessage === 'function'){ window.AppMovil.postMessage(JSON.stringify({ accion: 'cerrar' })); return; }\n  if(window.opener && !window.opener.closed){ window.close(); } else { location.href = '/'; }\n};\n\n"
  ],
  [
   "      state.infra = _fusionarInfraServidor(guardado.infra);\n      const cli = guardado.cliente || {};\n      if(cli.contacto) document.getElementById('c-contacto').value = cli.contacto;\n      if(cli.folio) document.getElementById('c-folio').value = cli.folio;\n      if(cli.giro) document.getElementById('c-giro').value = cli.giro;\n      if(cli.marca) document.getElementById('c-marca').value = cli.marca;\n",
   "      state.infra = _fusionarInfraServidor(guardado.infra);\n      const cli = guardado.cliente || {};\n      if(cli.contacto) document.getElementById('c-contacto').value = cli.contacto;\n      if(cli.whatsapp) document.getElementById('c-whatsapp').value = cli.whatsapp;\n      if(cli.folio) document.getElementById('c-folio').value = cli.folio;\n      if(cli.giro) document.getElementById('c-giro').value = cli.giro;\n      if(cli.marca) document.getElementById('c-marca').value = cli.marca;\n"
  ],
  [
   "        document.getElementById('t-entrega').checked = true;\n        document.getElementById('entrega-fields').style.display = 'block';\n        document.getElementById('btn-entrega-pdf').style.display = 'block';\n      }\n      if(ent.tipo) document.getElementById('c-entrega-tipo').value = ent.tipo;\n      if(ent.fecha) document.getElementById('c-entrega-fecha').value = ent.fecha;\n",
   "        document.getElementById('t-entrega').checked = true;\n        document.getElementById('entrega-fields').style.display = 'block';\n        document.getElementById('btn-entrega-pdf').style.display = 'block';\n        document.getElementById('btn-entrega-wa').style.display = 'block';\n      }\n      if(ent.tipo) document.getElementById('c-entrega-tipo').value = ent.tipo;\n      if(ent.fecha) document.getElementById('c-entrega-fecha').value = ent.fecha;\n"
  ],
  [
   "    infra: state.infra,\n    cliente: {\n      contacto: document.getElementById('c-contacto').value,\n      folio: document.getElementById('c-folio').value,\n      giro: document.getElementById('c-giro').value,\n      marca: document.getElementById('c-marca').value,\n",
   "    infra: state.infra,\n    cliente: {\n      contacto: document.getElementById('c-contacto').value,\n      whatsapp: document.getElementById('c-whatsapp').value,\n      folio: document.getElementById('c-folio').value,\n      giro: document.getElementById('c-giro').value,\n      marca: document.getElementById('c-marca').value,\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_cotizador_whatsapp_app.py")
        sys.exit(1)
    errores = []
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
            errores.append("No encontre {} -- corre el script desde la carpeta del repo.".format(ruta))
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
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
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
