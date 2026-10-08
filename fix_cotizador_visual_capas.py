# -*- coding: utf-8 -*-
"""
Cotizador visual (editor): orden de capas de los accesorios.

Antes el accesorio seleccionado se dibujaba siempre hasta enfrente, asi que
"Atras" no se notaba. Ahora se ve en su capa real, se puede arrastrar aunque
quede detras de otro (si el toque cae dentro de el), y hay 4 botones:
Al frente, Subir, Bajar, Al fondo, con el numero de capa.

Toca: frontend/index.html. Se puede correr varias veces.

Uso: en la carpeta del repo:
    py -3 fix_cotizador_visual_capas.py
"""
import os
import sys

ARCHIVOS = {'frontend/index.html': [['transform:translate(-50%,-50%) rotate(${a.rot || 0}deg); z-index:${sel ? 999 : 10 + (a.z || 0)};" />`;', 'transform:translate(-50%,-50%) rotate(${a.rot || 0}deg); z-index:${10 + (a.z || 0)};" />`;'], ["  stage.addEventListener('pointerdown', (ev) => {\n    const capa = ev.target.closest('.cv-layer');\n    if (!capa) return;", '  stage.addEventListener(\'pointerdown\', (ev) => {\n    let capa = ev.target.closest(\'.cv-layer\');\n    const capaSel = CV_EDIT_SEL ? stage.querySelector(`.cv-layer[data-uid="${CV_EDIT_SEL}"]`) : null;\n    if (capaSel) {\n      const r = capaSel.getBoundingClientRect();\n      if (ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom) capa = capaSel;\n    }\n    if (!capa) return;'], ['        l.style.zIndex = sel ? 999 : 10 + ((a && a.z) || 0);', '        l.style.zIndex = 10 + ((a && a.z) || 0);'], ['  const ordenados = [...accs].sort((x, y) => (x.z || 0) - (y.z || 0));\n  const i = ordenados.indexOf(a);\n  ordenados.splice(i, 1);\n  ordenados.splice(direccion > 0 ? ordenados.length : 0, 0, a);\n  ordenados.forEach((x, k) => { x.z = k; });\n  cv_renderEditor();', '  // direccion: 2 = hasta el frente, 1 = subir una capa, -1 = bajar una, -2 = hasta atrás\n  const ordenados = [...accs].sort((x, y) => (x.z || 0) - (y.z || 0));\n  const i = ordenados.indexOf(a);\n  ordenados.splice(i, 1);\n  let destino = direccion === 2 ? ordenados.length : direccion === -2 ? 0 : i + direccion;\n  destino = Math.max(0, Math.min(ordenados.length, destino));\n  ordenados.splice(destino, 0, a);\n  ordenados.forEach((x, k) => { x.z = k; });\n  cv_renderEditor();'], ['      <button type="button" class="secondary" onclick="cv_capaOrden(1)">⬆️ Al frente</button>\n      <button type="button" class="secondary" onclick="cv_capaOrden(-1)">⬇️ Atrás</button>', '      <span style="font-size:11px; color:var(--muted); flex-basis:100%;">Capa ${cv_numeroCapa(a)} de ${CV_EDIT.config.accesorios.filter(x => x.imagen).length} (1 = hasta atrás)</span>\n      <button type="button" class="secondary" onclick="cv_capaOrden(2)" title="Hasta el frente">⏫ Al frente</button>\n      <button type="button" class="secondary" onclick="cv_capaOrden(1)" title="Subir una capa">⬆️ Subir</button>\n      <button type="button" class="secondary" onclick="cv_capaOrden(-1)" title="Bajar una capa">⬇️ Bajar</button>\n      <button type="button" class="secondary" onclick="cv_capaOrden(-2)" title="Hasta atrás">⏬ Al fondo</button>'], ['function cv_capaOrden(direccion) {', 'function cv_numeroCapa(a) {\n  const ordenados = CV_EDIT.config.accesorios.filter(x => x.imagen).sort((x, y) => (x.z || 0) - (y.z || 0));\n  return ordenados.indexOf(a) + 1;\n}\n\nfunction cv_capaOrden(direccion) {']]}

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
