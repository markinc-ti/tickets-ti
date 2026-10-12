# -*- coding: utf-8 -*-
"""
WhatsApp con el PDF adjunto (ya no la liga):
  - "Enviar por WhatsApp" (cotizador, Realizadas, seguimientos) descarga el PDF
    de la cotizacion y lo manda como ARCHIVO:
      * celular / iPad: hoja de "Compartir" del sistema -> WhatsApp -> contacto.
      * computadora: descarga el PDF y abre el chat del cliente para arrastrarlo.

REQUIERE haber corrido antes fix_paqueterias_varias.py.
Toca: frontend/index.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "}\n\n// ---- Enviar por WhatsApp ----\n// Se manda una liga corta y pública al PDF (el mismo token de la impresión\n// Bluetooth) dentro de un mensaje de WhatsApp ya redactado — al abrir la\n// liga, WhatsApp se abre directo con el mensaje listo para mandar.\n\nfunction cot_abrirWhatsApp(cotizacion) {\n  api(`/api/cotizaciones/${cotizacion.id}/liga-impresion`, { method: 'POST' }).then(({ token }) => {\n    const pdfUrl = `${window.location.origin}/cotizacion-pdf/${token}`;\n    const texto = `Hola ${cotizacion.cliente_nombre}, te comparto tu cotización ${cotizacion.folio} por un total de $${cot_fmt(cotizacion.total)}. Puedes verla aquí: ${pdfUrl}`;\n    const soloDigitos = (cotizacion.cliente_telefono || '').replace(/\\D/g, '');\n    // Si son 10 dígitos se asume número mexicano (se le antepone 52); si ya\n    // trae más dígitos (con lada de país) se manda tal cual; si no hay\n    // teléfono capturado, WhatsApp deja elegir el contacto a mano.\n    const numero = soloDigitos.length === 10 ? `52${soloDigitos}` : (soloDigitos.length > 10 ? soloDigitos : '');\n    const waUrl = numero\n      ? `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`\n      : `https://wa.me/?text=${encodeURIComponent(texto)}`;\n    window.open(waUrl, '_blank');\n  }).catch(e => alert('No se pudo preparar el envío: ' + e.message));\n}\n\nasync function cot_enviarWhatsAppLista(id) {\n",
   "}\n\n// ---- Enviar por WhatsApp ----\n// Se manda el PDF como ARCHIVO, no una liga. En celular / iPad se usa la hoja\n// de \"Compartir\" del sistema (se toca WhatsApp y el contacto) — WhatsApp no\n// deja que una página adjunte un archivo a un chat de otra forma. En la\n// computadora el navegador no puede adjuntarlo: se descarga el PDF y se abre\n// el chat del cliente para arrastrarlo ahí.\n\nlet COT_WA = null;\n\nfunction cot_numeroWhatsApp(telefono) {\n  const d = (telefono || '').replace(/\\D/g, '');\n  // 10 dígitos = número mexicano (se le antepone 52); con más dígitos ya trae lada de país.\n  return d.length === 10 ? `52${d}` : (d.length > 10 ? d : '');\n}\n\nasync function cot_abrirWhatsApp(cotizacion) {\n  const texto = `Hola ${cotizacion.cliente_nombre}, te comparto tu cotización ${cotizacion.folio} por un total de $${cot_fmt(cotizacion.total)}.`;\n  let archivo;\n  try {\n    const r = await fetch(`/api/cotizaciones/${cotizacion.id}/pdf`, { headers: headers(false) });\n    if (!r.ok) throw new Error('No se pudo generar el PDF');\n    archivo = new File([await r.blob()], `cotizacion_${cotizacion.folio}.pdf`, { type: 'application/pdf' });\n  } catch (e) {\n    alert('No se pudo preparar el envío: ' + e.message);\n    return;\n  }\n  const compartible = !!(navigator.canShare && navigator.canShare({ files: [archivo] }));\n  COT_WA = { archivo, texto, numero: cot_numeroWhatsApp(cotizacion.cliente_telefono), folio: cotizacion.folio };\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2 style=\"margin-bottom:6px;\">💬 Enviar por WhatsApp</h2>\n    <p style=\"font-size:13px; color:var(--muted); margin-top:0;\">Cotización <b>${escapeHtml(cotizacion.folio)}</b> — ${escapeHtml(cotizacion.cliente_nombre)} · el PDF va como archivo.</p>\n    ${compartible ? `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waCompartir()\">📤 Mandar PDF (elige WhatsApp)</button>\n      <p style=\"font-size:11px; color:var(--muted);\">Se abre \"Compartir\": toca WhatsApp y luego el contacto del cliente.</p>` : `\n      <button class=\"primary\" style=\"width:100%; padding:14px;\" onclick=\"cot_waComputadora()\">⬇️ Descargar PDF y abrir el chat</button>\n      <p style=\"font-size:11px; color:var(--muted);\">En la computadora WhatsApp no deja adjuntar solo: se descarga el PDF y se abre el chat${COT_WA.numero ? ' del cliente' : ''}; arrastra el PDF ahí.</p>`}`;\n  abrirModal();\n}\n\nasync function cot_waCompartir() {\n  const w = COT_WA;\n  if (!w) return;\n  try {\n    await navigator.share({ files: [w.archivo], text: w.texto, title: `Cotización ${w.folio}` });\n    cerrarModal();\n  } catch (e) {\n    if (e && e.name === 'AbortError') return; // lo canceló\n    alert('No se pudo compartir: ' + (e && e.message ? e.message : e));\n  }\n}\n\nfunction cot_waComputadora() {\n  const w = COT_WA;\n  if (!w) return;\n  const url = URL.createObjectURL(w.archivo);\n  const a = document.createElement('a');\n  a.href = url; a.download = w.archivo.name;\n  document.body.appendChild(a); a.click(); a.remove();\n  setTimeout(() => URL.revokeObjectURL(url), 5000);\n  window.open(w.numero ? `https://wa.me/${w.numero}?text=${encodeURIComponent(w.texto)}` : `https://wa.me/?text=${encodeURIComponent(w.texto)}`, '_blank');\n  cerrarModal();\n}\n\nasync function cot_enviarWhatsAppLista(id) {\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    if not os.path.exists("backend/paqueterias.py"):
        print("Primero corre fix_paqueterias_varias.py (y luego este).")
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
