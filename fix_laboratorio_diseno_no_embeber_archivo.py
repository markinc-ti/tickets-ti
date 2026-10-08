# -*- coding: utf-8 -*-
"""
Arregla el timeout/tardanza al abrir el DETALLE de un trabajo de
laboratorio que tiene un diseño (STL) subido -- el que salía en la app
(Flutter) como "TimeoutException after 0:00:25.000000" al cargar
LaboratorioService.detalle(), justo después de que subir diseños grandes
(hasta ~90MB) ya funciona bien con el fix anterior.

Causa real: aunque subir el archivo ya no truena, GET /api/laboratorio/{id}
(el detalle del trabajo -- lo que carga tanto el panel web como la app al
abrir un trabajo) seguía regresando, DENTRO del JSON de ese detalle, el
contenido COMPLETO en base64 de CADA intento de diseño que se le haya
subido a ese trabajo (todo el historial, no solo el vigente) -- para un
trabajo con un solo diseño de 60-90MB eso ya es un JSON gigante solo para
ver el estatus del trabajo; si hubo una corrección de por medio (2
intentos), se duplica. En la app, el timeout de 25 segundos del cliente
HTTP no alcanza a bajar eso; en la web tarda muchísimo aunque no truene.

Fix: el detalle del trabajo ya NO trae el contenido de los archivos de
diseño (solo metadatos: nombre, estado, fechas, quién lo subió, si ya se
liberó, etc. -- exactamente lo que ya se usaba para mostrar el historial y
decidir qué botones mostrar). El contenido real de un diseño puntual se
pide aparte, con un endpoint nuevo, SOLO cuando de verdad hace falta
mostrar el visor 3D o descargar el archivo -- nunca solo para ver el
estatus del trabajo. Ya no cambia el almacenamiento (sigue igual en
Postgres), solo cuándo se manda ese contenido por la red.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_laboratorio_diseno_no_embeber_archivo.py
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '''    cur.execute("""
        SELECT d.*, u.nombre_completo AS subido_por_nombre
        FROM laboratorio_disenos d JOIN users u ON u.id = d.subido_por_id
        WHERE d.trabajo_id = %s ORDER BY d.creado_en ASC
    """, (trabajo_id,))
    trabajo["disenos"] = [dict(r) for r in cur.fetchall()]''',
            '''    # A propósito NO se traen aquí archivo_base64/archivo_base64_2 (el
    # contenido real, que puede pesar hasta ~90MB por archivo) -- eso
    # hacía que solo ABRIR el detalle de un trabajo con un diseño grande
    # tardara muchísimo o tronara con timeout en la app. El contenido se
    # pide aparte, solo cuando hace falta, con
    # GET /api/laboratorio/{trabajo_id}/disenos/{diseno_id}/archivo.
    cur.execute("""
        SELECT d.id, d.trabajo_id, d.archivo_nombre, d.subido_por_id, d.creado_en, d.estado,
               d.revisado_por_id, d.revisado_en, d.motivo_rechazo, d.archivo_nombre_2, d.archivo_liberado,
               u.nombre_completo AS subido_por_nombre
        FROM laboratorio_disenos d JOIN users u ON u.id = d.subido_por_id
        WHERE d.trabajo_id = %s ORDER BY d.creado_en ASC
    """, (trabajo_id,))
    trabajo["disenos"] = [dict(r) for r in cur.fetchall()]''',
        ],
    ],
    'backend/app.py': [
        [
            '''    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"Subió el diseño ({nombres_diseno}) para que el estudiante lo apruebe.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/aprobar")''',
            '''    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"Subió el diseño ({nombres_diseno}) para que el estudiante lo apruebe.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/archivo")
def api_obtener_archivo_diseno_laboratorio(trabajo_id: int, diseno_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    """El detalle del trabajo (GET /api/laboratorio/{id}) ya NO trae el
    contenido del STL de cada diseño, solo metadatos (ver nota en
    db.obtener_trabajo_laboratorio) -- este endpoint trae el contenido
    real de UN diseño puntual, para pedirlo solo cuando de verdad hace
    falta mostrar el visor 3D o descargar el archivo. Mismo permiso que
    ver el detalle del trabajo: personal de laboratorio, o el propio
    estudiante dueño del trabajo."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    diseno = db.obtener_diseno_laboratorio(diseno_id)
    if not diseno or diseno["trabajo_id"] != trabajo_id:
        raise HTTPException(status_code=404, detail="Diseño no encontrado")
    return {
        "archivo_base64": diseno["archivo_base64"],
        "archivo_nombre": diseno["archivo_nombre"],
        "archivo_base64_2": diseno.get("archivo_base64_2"),
        "archivo_nombre_2": diseno.get("archivo_nombre_2"),
    }


@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/aprobar")''',
        ],
    ],
    'frontend/index.html': [
        [
            '''  if (disenoActual && document.getElementById('visorSTL_lab')) {
    iniciarVisorSTL('visorSTL_lab', disenoActual.archivo_base64, w.dscore_order_name ? w.id : null, disenoActual.archivo_base64_2 || null, disenoActual.archivo_nombre, disenoActual.archivo_nombre_2);
  }
}''',
            '''  if (disenoActual && document.getElementById('visorSTL_lab')) {
    // El detalle del trabajo ya no trae el contenido del STL (solo
    // metadatos) -- se pide aparte, solo cuando de verdad hace falta
    // mostrar el visor, para que abrir el detalle no se tarde ni truene
    // con diseños grandes.
    document.getElementById('visorSTL_lab').innerHTML = '<p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">Cargando modelo 3D…</p>';
    try {
      const archivo = await api(`/api/laboratorio/${w.id}/disenos/${disenoActual.id}/archivo`);
      iniciarVisorSTL('visorSTL_lab', archivo.archivo_base64, w.dscore_order_name ? w.id : null, archivo.archivo_base64_2 || null, archivo.archivo_nombre, archivo.archivo_nombre_2);
    } catch (e) {
      const visor = document.getElementById('visorSTL_lab');
      if (visor) visor.innerHTML = `<p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">No se pudo cargar el modelo 3D: ${escapeHtml(e.message)}</p>`;
    }
  }
}''',
        ],
    ],
    'frontend/laboratorio_estudiantes.html': [
        [
            '''        <div id="visorSTL_estudiante" style="width:100%; height:260px; background:#12151a; border-radius:8px; margin-bottom:6px;"></div>
        <div id="visorSTL_estudiante_controles" style="margin-bottom:6px;"></div>
        <p class="sub" style="font-size:11px; margin:0 0 10px;">Arrastra para girar — esto es solo para revisar, no reemplaza el archivo descargado.</p>
        <a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${disenoActual.archivo_base64}" download="${escapeHtml(disenoActual.archivo_nombre || 'diseno.stl')}">⬇️ Descargar diseño (STL)</a>
        ${disenoActual.archivo_base64_2 ? `<a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${disenoActual.archivo_base64_2}" download="${escapeHtml(disenoActual.archivo_nombre_2 || 'diseno_2.stl')}">⬇️ Descargar segunda pieza (STL)</a>` : ''}
        <button class="primary" style="width:100%; margin-bottom:10px;" onclick="aprobarDisenoUI(${w.id}, ${disenoActual.id})">✅ Todo está bien</button>''',
            '''        <div id="visorSTL_estudiante" style="width:100%; height:260px; background:#12151a; border-radius:8px; margin-bottom:6px;"><p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">Cargando modelo 3D…</p></div>
        <div id="visorSTL_estudiante_controles" style="margin-bottom:6px;"></div>
        <p class="sub" style="font-size:11px; margin:0 0 10px;">Arrastra para girar — esto es solo para revisar, no reemplaza el archivo descargado.</p>
        <div id="disenoDescargas"><p class="sub" style="font-size:12px;">Preparando la descarga…</p></div>
        <button class="primary" style="width:100%; margin-bottom:10px;" onclick="aprobarDisenoUI(${w.id}, ${disenoActual.id})">✅ Todo está bien</button>''',
        ],
        [
            '''      const disenosDetalle = w.disenos || [];
      const disenoActualDetalle = disenosDetalle.length ? disenosDetalle[disenosDetalle.length - 1] : null;
      if (disenoActualDetalle && disenoActualDetalle.estado === 'pendiente' && document.getElementById('visorSTL_estudiante')) {
        iniciarVisorSTL('visorSTL_estudiante', disenoActualDetalle.archivo_base64, w.dscore_order_name ? w.id : null, disenoActualDetalle.archivo_base64_2 || null, disenoActualDetalle.archivo_nombre, disenoActualDetalle.archivo_nombre_2);
      }
    } catch (e) {
      cont.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
    }
  }''',
            '''      const disenosDetalle = w.disenos || [];
      const disenoActualDetalle = disenosDetalle.length ? disenosDetalle[disenosDetalle.length - 1] : null;
      if (disenoActualDetalle && disenoActualDetalle.estado === 'pendiente' && document.getElementById('visorSTL_estudiante')) {
        // El detalle ya no trae el contenido del STL (solo metadatos) --
        // se pide aparte para que abrir el trabajo no se tarde ni truene
        // con diseños grandes.
        try {
          const archivo = await api(`/api/laboratorio/${w.id}/disenos/${disenoActualDetalle.id}/archivo`);
          iniciarVisorSTL('visorSTL_estudiante', archivo.archivo_base64, w.dscore_order_name ? w.id : null, archivo.archivo_base64_2 || null, archivo.archivo_nombre, archivo.archivo_nombre_2);
          const descargas = document.getElementById('disenoDescargas');
          if (descargas) {
            descargas.innerHTML = `
              <a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${archivo.archivo_base64}" download="${escapeHtml(archivo.archivo_nombre || 'diseno.stl')}">⬇️ Descargar diseño (STL)</a>
              ${archivo.archivo_base64_2 ? `<a class="primary" style="display:block; text-align:center; text-decoration:none; margin-bottom:10px;" href="${archivo.archivo_base64_2}" download="${escapeHtml(archivo.archivo_nombre_2 || 'diseno_2.stl')}">⬇️ Descargar segunda pieza (STL)</a>` : ''}
            `;
          }
        } catch (e) {
          const visor = document.getElementById('visorSTL_estudiante');
          if (visor) visor.innerHTML = '<p style="font-size:12px; color:var(--muted); padding:10px; margin:0;">No se pudo cargar el modelo 3D.</p>';
          const descargas = document.getElementById('disenoDescargas');
          if (descargas) descargas.innerHTML = `<p class="sub" style="font-size:12px; color:var(--muted);">No se pudo preparar la descarga: ${escapeHtml(e.message)}</p>`;
        }
      }
    } catch (e) {
      cont.innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
    }
  }''',
        ],
    ],
}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    hubo_error = False
    for ruta, reemplazos in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
            hubo_error = True
            continue
        cambios = 0
        for viejo, nuevo in reemplazos:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
                hubo_error = True
                continue
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/db.py backend/app.py frontend/index.html frontend/laboratorio_estudiantes.html")
    print('   git commit -m "Laboratorio: el detalle del trabajo ya no trae el archivo STL completo -- arregla timeout al abrir un trabajo con diseno grande"')
    print("   git push")


if __name__ == "__main__":
    main()
