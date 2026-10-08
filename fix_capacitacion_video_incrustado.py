# -*- coding: utf-8 -*-
"""
Capacitación: el video se ve incrustado dentro de la app (no en pestaña
nueva de OneDrive)

Antes, al darle "Ver video" en 📚 Capacitación, se abría el link en una
pestaña nueva del navegador. Ahora se reemplaza el contenido del mismo
panel por un reproductor incrustado (iframe), con un botón "← Volver a
la lista" y, como respaldo, un link para abrirlo aparte por si el
proveedor no deja incrustarlo. También se actualizan los textos de
ayuda al crear/editar un material de tipo Video para avisar que, si es
de OneDrive, hay que usar el link de "Insertar/Embed" al compartirlo
(no el de "Copiar vínculo", que normalmente bloquea el incrustado).

Qué toca:
1. frontend/index.html — verMaterialCapacitacion() ahora llama a la
   función nueva verVideoCapacitacionIncrustado() en vez de abrir una
   pestaña; textos de ayuda nuevos junto al campo "Link del video"
   (tanto al crear como al editar un material).
2. backend/app.py — el mensaje de error cuando falta el link menciona
   también OneDrive (antes solo decía YouTube/Drive/Vimeo).

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_capacitacion_video_incrustado.py
"""
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------
# backend/app.py
# ---------------------------------------------------------------------
ARCHIVOS['backend/app.py'] = [
    [
        '''            raise HTTPException(status_code=400, detail="Falta un link de video válido (YouTube, Drive o Vimeo)")
''',
        '''            raise HTTPException(status_code=400, detail="Falta un link de video válido (YouTube, Drive, Vimeo o OneDrive)")
''',
    ],
]

# ---------------------------------------------------------------------
# frontend/index.html
# ---------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    # 1) Ver video -> ahora incrustado, no pestaña nueva.
    [
        '''function verMaterialCapacitacion(material) {
  if (material.tipo === 'video') {
    window.open(material.video_url, '_blank');
    return;
  }
''',
        '''function verMaterialCapacitacion(material) {
  if (material.tipo === 'video') {
    verVideoCapacitacionIncrustado(material);
    return;
  }
''',
    ],
    # 2) Función nueva del reproductor incrustado.
    [
        '''  const ventana = window.open();
  ventana.location.href = _dataURItoBlobUrl(material.archivo_base64);
}

async function marcarMaterialVistoUI(materialId, boton) {
''',
        '''  const ventana = window.open();
  ventana.location.href = _dataURItoBlobUrl(material.archivo_base64);
}

function verVideoCapacitacionIncrustado(material) {
  // Se ve incrustado (iframe) dentro del mismo panel — si el link no es
  // un link de "insertar/embed" (por ejemplo, un link normal de "copiar
  // vínculo" de OneDrive), el propio proveedor puede negarse a cargar
  // dentro de un iframe; por eso siempre dejamos también el link para
  // abrirlo aparte, como respaldo.
  const cont = document.getElementById('miCapacitacionLista');
  if (!cont) { window.open(material.video_url, '_blank'); return; }
  cont.innerHTML = `
    <button class="secondary" style="margin-bottom:10px;" onclick="renderMiCapacitacionLista()">← Volver a la lista</button>
    <div style="font-weight:600; font-size:13px; margin-bottom:8px;">🎥 ${escapeHtml(material.titulo)}</div>
    <div style="position:relative; width:100%; padding-top:56.25%; background:#000; border-radius:6px; overflow:hidden;">
      <iframe src="${escapeHtml(material.video_url)}" allow="autoplay; fullscreen" allowfullscreen
              style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;"></iframe>
    </div>
    <p style="font-size:11px; color:var(--muted); margin-top:8px;">
      ¿No carga el video aquí? <a href="${escapeHtml(material.video_url)}" target="_blank" rel="noopener">Ábrelo en OneDrive</a>.
    </p>
  `;
}

async function marcarMaterialVistoUI(materialId, boton) {
''',
    ],
    # 3) Aviso junto al campo del link, al EDITAR un material de video.
    [
        '''      ${material.tipo === 'video' ? `<div class="field"><label>Link del video</label><input id="capMatVideoUrl" value="${escapeHtml(material.video_url || '')}" /></div>` : `<div class="field"><label>Reemplazar PDF (opcional — déjalo vacío para conservar el actual)</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>`}
''',
        '''      ${material.tipo === 'video' ? `<div class="field"><label>Link del video</label><input id="capMatVideoUrl" value="${escapeHtml(material.video_url || '')}" /><p style="font-size:11px; color:var(--muted); margin:4px 0 0;">El video se ve incrustado dentro de la app. Si es de OneDrive, usa el link de "Insertar" (Insert/Embed) al compartirlo — no el de "Copiar vínculo", que normalmente no se deja incrustar.</p></div>` : `<div class="field"><label>Reemplazar PDF (opcional — déjalo vacío para conservar el actual)</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>`}
''',
    ],
    # 4) Selector de tipo + aviso junto al campo del link, al CREAR.
    [
        '''          <option value="pdf">PDF (se sube el archivo)</option>
          <option value="video">Video (link de YouTube, Drive o Vimeo)</option>
        </select>
      </div>
      <div class="field" id="capMatCampoPdf"><label>Archivo PDF</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>
      <div class="field" id="capMatCampoVideo" style="display:none;"><label>Link del video</label><input id="capMatVideoUrl" placeholder="https://…" /></div>
''',
        '''          <option value="pdf">PDF (se sube el archivo)</option>
          <option value="video">Video (link de YouTube, Drive, Vimeo o OneDrive)</option>
        </select>
      </div>
      <div class="field" id="capMatCampoPdf"><label>Archivo PDF</label><input type="file" id="capMatArchivo" accept="application/pdf" /></div>
      <div class="field" id="capMatCampoVideo" style="display:none;">
        <label>Link del video</label>
        <input id="capMatVideoUrl" placeholder="https://…" />
        <p style="font-size:11px; color:var(--muted); margin:4px 0 0;">El video se ve incrustado dentro de la app. Si es de OneDrive, usa el link de "Insertar" (Insert/Embed) al compartirlo — no el de "Copiar vínculo", que normalmente no se deja incrustar.</p>
      </div>
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
    print("   git add backend/app.py frontend/index.html")
    print('   git commit -m "Capacitacion: el video se ve incrustado en la app, no en pestana nueva"')
    print("   git push")


if __name__ == "__main__":
    main()
