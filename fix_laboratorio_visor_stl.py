#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Laboratorio: visor 3D (solo lectura) para los archivos de diseno (STL) que
se suben en el paso "Aprobar diseno".

Antes solo se podia descargar el STL para verlo en otro programa. Ahora se
puede ver directo en el navegador -- se puede girar el modelo con el mouse
o el dedo, pero no se puede editar ni marcar nada sobre el (solo
visualizacion, como pidio David).

Se agrega en los dos lados:
- Portal del estudiante (frontend/laboratorio_estudiantes.html): dentro de
  "Revisa tu diseno", arriba del boton de descargar.
- Panel del laboratorio/administrador (frontend/index.html): dentro del
  detalle de un trabajo en Modelado/Aprobar diseno, para que el staff vea
  lo mismo que el estudiante.

Usa Three.js r128 cargado desde CDN publico (cdnjs.cloudflare.com y
cdn.jsdelivr.net) -- no se agrega ninguna libreria al backend ni se guarda
nada nuevo en la base de datos, es puro frontend sobre el archivo_base64
que ya se sube y se manda al navegador. Si el navegador no puede cargar el
visor (sin internet para el CDN, celular muy viejo, etc.) se muestra un
mensaje y sigue disponible el boton de descargar de siempre.

Por que: David pidio "un lector de archivos STL, visualizacion nada mas"
como complemento al paso de Aprobar diseno que ya se entrego.

Que cambia:
- frontend/index.html: <script> de Three.js/STLLoader/OrbitControls en el
  <head>; un <div> visor dentro del bloque de diseno del detalle del
  trabajo (panel de laboratorio); funcion iniciarVisorSTL() que decodifica
  el base64, arma la escena y la deja girando con el mouse/dedo; se llama
  despues de pintar el detalle si hay un diseno para mostrar.
- frontend/laboratorio_estudiantes.html: mismo <script> de Three.js en el
  <head>; el mismo visor (su propia copia de iniciarVisorSTL, siguiendo
  como ya esta hecho el resto del archivo) dentro de "Revisa tu diseno";
  se llama despues de pintar el detalle del trabajo.
"""
import sys

ARCHIVOS = {
    'frontend/index.html': [
        [
            '<title>Tickets TI</title>',
            '<title>Tickets TI</title>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>',
        ],
        [
            '    ${(w.estado === \'modelado\' || w.estado === \'aprobar_diseno\') ? (disenoActual && disenoActual.estado === \'pendiente\' ? `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0;">🦷 Diseño subido (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — esperando que el estudiante lo apruebe.</p>\n      </div>\n    ` : `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0 0 8px;">🦷 ${disenoActual && disenoActual.estado === \'rechazado\' ? `El estudiante pidió corregir el diseño${disenoActual.motivo_rechazo ? \': \' + escapeHtml(disenoActual.motivo_rechazo) : \'\'} — sube el archivo corregido.` : \'Sube el archivo de diseño (STL) para que el estudiante lo apruebe.\'}</p>\n        <label class="secondary btn-file" style="display:inline-block;">\n          📎 Subir diseño (STL)\n          <input type="file" accept=".stl,.ply,.obj" style="display:none;" onchange="subirDisenoLaboratorioUI(${w.id}, this)" />\n        </label>\n      </div>\n    `) : \'\'}',
            '    ${(w.estado === \'modelado\' || w.estado === \'aprobar_diseno\') ? (disenoActual && disenoActual.estado === \'pendiente\' ? `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0 0 8px;">🦷 Diseño subido (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — esperando que el estudiante lo apruebe.</p>\n        <div id="visorSTL_lab" style="width:100%; height:260px; background:#12151a; border-radius:6px;"></div>\n        <p style="font-size:11px; color:var(--muted); margin:6px 0 0;">Arrastra para girar el modelo (solo vista previa).</p>\n      </div>\n    ` : `\n      <div style="border:1px solid var(--copper); border-radius:8px; padding:12px; margin-top:14px;">\n        <p style="font-size:13px; margin:0 0 8px;">🦷 ${disenoActual && disenoActual.estado === \'rechazado\' ? `El estudiante pidió corregir el diseño${disenoActual.motivo_rechazo ? \': \' + escapeHtml(disenoActual.motivo_rechazo) : \'\'} — sube el archivo corregido.` : \'Sube el archivo de diseño (STL) para que el estudiante lo apruebe.\'}</p>\n        ${disenoActual ? \'<div id="visorSTL_lab" style="width:100%; height:220px; background:#12151a; border-radius:6px; margin-bottom:8px;"></div>\' : \'\'}\n        <label class="secondary btn-file" style="display:inline-block;">\n          📎 Subir diseño (STL)\n          <input type="file" accept=".stl,.ply,.obj" style="display:none;" onchange="subirDisenoLaboratorioUI(${w.id}, this)" />\n        </label>\n      </div>\n    `) : \'\'}',
        ],
        [
            "  if (document.getElementById('lab_firma_recepcion_canvas')) {\n    MODAL_PROTEGIDO = true;\n    inicializarFirmaCanvas('lab_firma_recepcion_canvas', () => { firmaLabRecepcionFinalVacia = false; });\n    firmaLabRecepcionFinalVacia = true;\n  } else {\n    MODAL_PROTEGIDO = false;\n  }\n}",
            "  if (document.getElementById('lab_firma_recepcion_canvas')) {\n    MODAL_PROTEGIDO = true;\n    inicializarFirmaCanvas('lab_firma_recepcion_canvas', () => { firmaLabRecepcionFinalVacia = false; });\n    firmaLabRecepcionFinalVacia = true;\n  } else {\n    MODAL_PROTEGIDO = false;\n  }\n  if (disenoActual && document.getElementById('visorSTL_lab')) {\n    iniciarVisorSTL('visorSTL_lab', disenoActual.archivo_base64);\n  }\n}",
        ],
        [
            'async function subirDisenoLaboratorioUI(trabajoId, input) {',
            'function iniciarVisorSTL(contenedorId, base64) {\n  const cont = document.getElementById(contenedorId);\n  if (!cont) return;\n  const mostrarError = (msg) => {\n    cont.innerHTML = `<p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">${msg}</p>`;\n  };\n  if (typeof THREE === \'undefined\' || !THREE.STLLoader) {\n    mostrarError(\'No se pudo cargar el visor 3D — descarga el archivo para revisarlo.\');\n    return;\n  }\n  let buffer;\n  try {\n    const partes = String(base64).split(\',\');\n    const binario = atob(partes[1] || partes[0]);\n    buffer = new Uint8Array(binario.length);\n    for (let i = 0; i < binario.length; i++) buffer[i] = binario.charCodeAt(i);\n  } catch (e) {\n    mostrarError(\'No se pudo leer el archivo para mostrarlo.\');\n    return;\n  }\n  let geometry;\n  try {\n    geometry = new THREE.STLLoader().parse(buffer.buffer);\n  } catch (e) {\n    mostrarError(\'Este archivo no se puede previsualizar (formato no compatible) — descárgalo para revisarlo.\');\n    return;\n  }\n  try {\n    cont.innerHTML = \'\';\n    const ancho = cont.clientWidth || 300;\n    const alto = cont.clientHeight || 260;\n    const scene = new THREE.Scene();\n    scene.background = new THREE.Color(0x12151a);\n    const camera = new THREE.PerspectiveCamera(45, ancho / alto, 0.1, 5000);\n    const renderer = new THREE.WebGLRenderer({ antialias: true });\n    renderer.setSize(ancho, alto);\n    cont.appendChild(renderer.domElement);\n    scene.add(new THREE.AmbientLight(0xffffff, 0.7));\n    const luz1 = new THREE.DirectionalLight(0xffffff, 0.9);\n    luz1.position.set(1, 1, 1);\n    scene.add(luz1);\n    const luz2 = new THREE.DirectionalLight(0xffffff, 0.5);\n    luz2.position.set(-1, -0.6, -1);\n    scene.add(luz2);\n    const material = new THREE.MeshStandardMaterial({ color: 0xd8c9a3, metalness: 0.05, roughness: 0.65 });\n    const mesh = new THREE.Mesh(geometry, material);\n    geometry.computeBoundingBox();\n    geometry.center();\n    const tam = new THREE.Vector3();\n    geometry.boundingBox.getSize(tam);\n    const maxDim = Math.max(tam.x, tam.y, tam.z) || 1;\n    camera.position.set(0, maxDim * 0.5, maxDim * 2.2);\n    camera.lookAt(0, 0, 0);\n    scene.add(mesh);\n    const controls = new THREE.OrbitControls(camera, renderer.domElement);\n    controls.target.set(0, 0, 0);\n    controls.enableDamping = true;\n    controls.dampingFactor = 0.1;\n    controls.update();\n    (function animar() {\n      if (!document.body.contains(cont)) return;\n      requestAnimationFrame(animar);\n      controls.update();\n      renderer.render(scene, camera);\n    })();\n  } catch (e) {\n    mostrarError(\'No se pudo mostrar la vista previa 3D — descarga el archivo para revisarlo.\');\n  }\n}\n\nasync function subirDisenoLaboratorioUI(trabajoId, input) {',
        ],
    ],
    'frontend/laboratorio_estudiantes.html': [
        [
            '<title>Laboratorio — Portal de estudiantes</title>',
            '<title>Laboratorio — Portal de estudiantes</title>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>',
        ],
        [
            '  function _seccionAprobarDiseno(w) {\n    if (w.estado !== \'aprobar_diseno\') return \'\';\n    const disenos = w.disenos || [];\n    const disenoActual = disenos.length ? disenos[disenos.length - 1] : null;\n    if (!disenoActual || disenoActual.estado !== \'pendiente\') {\n      return `\n        <div class="card destacada">\n          <h2 style="margin-top:0;">Diseño</h2>\n          <p class="sub">El laboratorio todavía no sube el diseño para que lo revises.</p>\n        </div>\n      `;\n    }\n    return `\n      <div class="card destacada">\n        <h2 style="margin-top:0;">Revisa tu diseño</h2>\n        <p class="sub" style="margin-bottom:10px;">El laboratorio subió el diseño de tu trabajo (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — descárgalo y revísalo antes de que se mande a fresar.</p>\n        <a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${disenoActual.archivo_base64}" download="${escapeHtml(disenoActual.archivo_nombre || \'diseno.stl\')}">⬇️ Descargar diseño (STL)</a>\n        <button class="primary" style="width:100%; margin-bottom:10px;" onclick="aprobarDisenoUI(${w.id}, ${disenoActual.id})">✅ Todo está bien</button>\n        <p class="sub" style="margin-bottom:4px;">¿Algo no está bien? Cuéntanos qué (opcional):</p>\n        <textarea id="diseno_motivo_rechazo" placeholder="ej. falta ajustar el contacto con el diente 16"></textarea>\n        <button class="secondary" style="width:100%; margin-top:8px;" onclick="rechazarDisenoUI(${w.id}, ${disenoActual.id})">No está bien — pedir corrección</button>\n        <div class="error" id="disenoError"></div>\n      </div>\n    `;\n  }',
            '  function iniciarVisorSTL(contenedorId, base64) {\n    const cont = document.getElementById(contenedorId);\n    if (!cont) return;\n    const mostrarError = (msg) => {\n      cont.innerHTML = `<p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">${msg}</p>`;\n    };\n    if (typeof THREE === \'undefined\' || !THREE.STLLoader) {\n      mostrarError(\'No se pudo cargar el visor 3D — descarga el archivo para revisarlo.\');\n      return;\n    }\n    let buffer;\n    try {\n      const partes = String(base64).split(\',\');\n      const binario = atob(partes[1] || partes[0]);\n      buffer = new Uint8Array(binario.length);\n      for (let i = 0; i < binario.length; i++) buffer[i] = binario.charCodeAt(i);\n    } catch (e) {\n      mostrarError(\'No se pudo leer el archivo para mostrarlo.\');\n      return;\n    }\n    let geometry;\n    try {\n      geometry = new THREE.STLLoader().parse(buffer.buffer);\n    } catch (e) {\n      mostrarError(\'Este archivo no se puede previsualizar (formato no compatible) — descárgalo para revisarlo.\');\n      return;\n    }\n    try {\n      cont.innerHTML = \'\';\n      const ancho = cont.clientWidth || 300;\n      const alto = cont.clientHeight || 260;\n      const scene = new THREE.Scene();\n      scene.background = new THREE.Color(0x12151a);\n      const camera = new THREE.PerspectiveCamera(45, ancho / alto, 0.1, 5000);\n      const renderer = new THREE.WebGLRenderer({ antialias: true });\n      renderer.setSize(ancho, alto);\n      cont.appendChild(renderer.domElement);\n      scene.add(new THREE.AmbientLight(0xffffff, 0.7));\n      const luz1 = new THREE.DirectionalLight(0xffffff, 0.9);\n      luz1.position.set(1, 1, 1);\n      scene.add(luz1);\n      const luz2 = new THREE.DirectionalLight(0xffffff, 0.5);\n      luz2.position.set(-1, -0.6, -1);\n      scene.add(luz2);\n      const material = new THREE.MeshStandardMaterial({ color: 0xd8c9a3, metalness: 0.05, roughness: 0.65 });\n      const mesh = new THREE.Mesh(geometry, material);\n      geometry.computeBoundingBox();\n      geometry.center();\n      const tam = new THREE.Vector3();\n      geometry.boundingBox.getSize(tam);\n      const maxDim = Math.max(tam.x, tam.y, tam.z) || 1;\n      camera.position.set(0, maxDim * 0.5, maxDim * 2.2);\n      camera.lookAt(0, 0, 0);\n      scene.add(mesh);\n      const controls = new THREE.OrbitControls(camera, renderer.domElement);\n      controls.target.set(0, 0, 0);\n      controls.enableDamping = true;\n      controls.dampingFactor = 0.1;\n      controls.update();\n      (function animar() {\n        if (!document.body.contains(cont)) return;\n        requestAnimationFrame(animar);\n        controls.update();\n        renderer.render(scene, camera);\n      })();\n    } catch (e) {\n      mostrarError(\'No se pudo mostrar la vista previa 3D — descarga el archivo para revisarlo.\');\n    }\n  }\n\n  function _seccionAprobarDiseno(w) {\n    if (w.estado !== \'aprobar_diseno\') return \'\';\n    const disenos = w.disenos || [];\n    const disenoActual = disenos.length ? disenos[disenos.length - 1] : null;\n    if (!disenoActual || disenoActual.estado !== \'pendiente\') {\n      return `\n        <div class="card destacada">\n          <h2 style="margin-top:0;">Diseño</h2>\n          <p class="sub">El laboratorio todavía no sube el diseño para que lo revises.</p>\n        </div>\n      `;\n    }\n    return `\n      <div class="card destacada">\n        <h2 style="margin-top:0;">Revisa tu diseño</h2>\n        <p class="sub" style="margin-bottom:10px;">El laboratorio subió el diseño de tu trabajo (${escapeHtml(disenoActual.archivo_nombre || \'archivo\')}) — revísalo aquí abajo (arrastra para girarlo) o descárgalo antes de que se mande a fresar.</p>\n        <div id="visorSTL_estudiante" style="width:100%; height:260px; background:#12151a; border-radius:8px; margin-bottom:6px;"></div>\n        <p class="sub" style="font-size:11px; margin:0 0 10px;">Arrastra para girar — esto es solo para revisar, no reemplaza el archivo descargado.</p>\n        <a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${disenoActual.archivo_base64}" download="${escapeHtml(disenoActual.archivo_nombre || \'diseno.stl\')}">⬇️ Descargar diseño (STL)</a>\n        <button class="primary" style="width:100%; margin-bottom:10px;" onclick="aprobarDisenoUI(${w.id}, ${disenoActual.id})">✅ Todo está bien</button>\n        <p class="sub" style="margin-bottom:4px;">¿Algo no está bien? Cuéntanos qué (opcional):</p>\n        <textarea id="diseno_motivo_rechazo" placeholder="ej. falta ajustar el contacto con el diente 16"></textarea>\n        <button class="secondary" style="width:100%; margin-top:8px;" onclick="rechazarDisenoUI(${w.id}, ${disenoActual.id})">No está bien — pedir corrección</button>\n        <div class="error" id="disenoError"></div>\n      </div>\n    `;\n  }',
        ],
        [
            '      const canvas = document.getElementById(\'firmaCanvas\');\n      if (canvas) {\n        FIRMA_VACIA = true;\n        inicializarFirmaCanvas(canvas);\n      }\n    } catch (e) {\n      cont.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;\n    }\n  }',
            '      const canvas = document.getElementById(\'firmaCanvas\');\n      if (canvas) {\n        FIRMA_VACIA = true;\n        inicializarFirmaCanvas(canvas);\n      }\n      const disenosDetalle = w.disenos || [];\n      const disenoActualDetalle = disenosDetalle.length ? disenosDetalle[disenosDetalle.length - 1] : null;\n      if (disenoActualDetalle && disenoActualDetalle.estado === \'pendiente\' && document.getElementById(\'visorSTL_estudiante\')) {\n        iniciarVisorSTL(\'visorSTL_estudiante\', disenoActualDetalle.archivo_base64);\n      }\n    } catch (e) {\n      cont.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;\n    }\n  }',
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
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche,")
                print("o que todavia falte aplicar fix_laboratorio_aprobar_diseno.py primero.")
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
    print("    git add frontend/index.html frontend/laboratorio_estudiantes.html")
    print('    git commit -m "Laboratorio: visor 3D (solo lectura) para el diseno STL en Aprobar diseno"')
    print("    git push")


if __name__ == "__main__":
    main()
