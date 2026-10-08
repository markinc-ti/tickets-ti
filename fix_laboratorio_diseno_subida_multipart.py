# -*- coding: utf-8 -*-
"""
Arregla de raíz el 502 al subir el diseño (STL) de un trabajo de
laboratorio con archivos grandes -- el que seguía pasando incluso después
de subir el plan de Render.

La causa real: "Subir diseño" mandaba el archivo convertido a base64
metido dentro de un body JSON. Eso infla el archivo ~33% (un STL de 90MB
se vuelve un JSON de ~120MB) y además obliga al servidor a leer y parsear
el body COMPLETO como un solo JSON gigante antes de poder contestar nada
-- con archivos grandes eso es lo que se estaba tronando con 502, y por
eso subir de plan (más RAM/CPU) no lo arreglaba: el problema no era falta
de recursos sino ese único paso pesado y bloqueante.

La solución: el archivo ahora se manda como multipart/form-data (igual
que ya funciona para subir videos de Capacitación/Turnos/Marketing a
Cloudflare R2) -- llega como bytes directos, sin el brinco de tamaño del
base64 ni el parseo de un JSON enorme, y se codifica a base64 ya del lado
del servidor (en threadpool) solo para guardarlo en la base de datos
igual que siempre.

De paso corrige un bug independiente que se encontró revisando esto: la
versión anterior guardaba el archivo como Data URL completo
("data:...;base64,XXXX"), y el visor 3D de la app de estudiantes
(Flutter) hace atob() directo sobre ese valor sin quitarle el prefijo --
un diseño subido así no cargaba en el visor de la app (el de la página
web sí lo toleraba). Este fix guarda solo el base64 puro de ahora en
adelante, y de una vez normaliza los diseños que ya estaban guardados con
el prefijo viejo.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_laboratorio_diseno_subida_multipart.py
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            '''import json
import os''',
            '''import base64
import json
import os''',
        ],
        [
            '''MAX_DISENO_STL_BASE64 = 120_000_000  # ~90MB de archivo real -- subido desde 30MB porque una arcada completa (2 archivos STL de alta resolución) se acerca a ese tamaño; el espacio se libera solo al entregar el trabajo (ver registrar_entrega_laboratorio en db.py)''',
            '''MAX_DISENO_ARCHIVO_BYTES = 90 * 1024 * 1024  # ~90MB de archivo real -- subido desde 30MB porque una arcada completa (2 archivos STL de alta resolución) se acerca a ese tamaño; el espacio se libera solo al entregar el trabajo (ver registrar_entrega_laboratorio en db.py). Se mide en bytes reales del archivo (ya no en caracteres de texto base64) porque el endpoint recibe el archivo como multipart, no metido en JSON -- ver api_subir_diseno_laboratorio.''',
        ],
        [
            '''class NuevaEvidenciaLaboratorio(BaseModel):
    archivo_base64: str
    archivo_nombre: Optional[str] = None
    descripcion: Optional[str] = None


class SubirDisenoLaboratorio(BaseModel):
    archivo_base64: str = Field(min_length=100)
    archivo_nombre: Optional[str] = None
    # Segunda pieza opcional -- para subir 2 archivos juntos (ej. arcada
    # superior + inferior) y verlos juntos en el mismo visor 3D.
    archivo_base64_2: Optional[str] = None
    archivo_nombre_2: Optional[str] = None


class RechazarDisenoLaboratorio(BaseModel):''',
            '''class NuevaEvidenciaLaboratorio(BaseModel):
    archivo_base64: str
    archivo_nombre: Optional[str] = None
    descripcion: Optional[str] = None


# SubirDisenoLaboratorio (el modelo Pydantic que recibía el archivo como
# base64 dentro del JSON) ya no se usa -- el endpoint de abajo ahora recibe
# el archivo como multipart/form-data (UploadFile) directo, sin pasar por
# JSON, que es justo lo que evita los 502 con archivos grandes en Render.


class RechazarDisenoLaboratorio(BaseModel):''',
        ],
        [
            '''@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")
def api_subir_diseno_laboratorio(trabajo_id: int, payload: SubirDisenoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """El laboratorio sube el archivo de diseño (STL) para que el estudiante
    lo revise antes de mandarlo a fresar -- la primera vez mueve el trabajo
    de 'modelado' a 'aprobar_diseno'; si el estudiante ya lo había
    rechazado, esto sube la corrección y se queda en 'aprobar_diseno'."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):
        raise HTTPException(status_code=400, detail="Este trabajo no está en modelado ni esperando aprobación de diseño")
    if usuario["rol"] != "admin":
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
            raise HTTPException(status_code=403, detail="Solo el laboratorio puede subir el diseño")
    if len(payload.archivo_base64) > MAX_DISENO_STL_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")
    if payload.archivo_base64_2 and len(payload.archivo_base64_2) > MAX_DISENO_STL_BASE64:
        raise HTTPException(status_code=400, detail="El segundo archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")
    estado_anterior = trabajo["estado"]
    db.subir_diseno_laboratorio(
        trabajo_id, payload.archivo_base64, payload.archivo_nombre, usuario["id"],
        archivo_base64_2=payload.archivo_base64_2, archivo_nombre_2=payload.archivo_nombre_2,
    )
    if estado_anterior == "modelado":
        db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "aprobar_diseno")
    nombres_diseno = payload.archivo_nombre or "archivo"
    if payload.archivo_nombre_2:
        nombres_diseno += f" + {payload.archivo_nombre_2}"
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"Subió el diseño ({nombres_diseno}) para que el estudiante lo apruebe.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)''',
            '''@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")
async def api_subir_diseno_laboratorio(
    trabajo_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    archivo_2: Optional[UploadFile] = File(None),
    usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio),
):
    """El laboratorio sube el archivo de diseño (STL) para que el estudiante
    lo revise antes de mandarlo a fresar -- la primera vez mueve el trabajo
    de 'modelado' a 'aprobar_diseno'; si el estudiante ya lo había
    rechazado, esto sube la corrección y se queda en 'aprobar_diseno'.

    Se recibe como multipart/form-data (UploadFile), no como JSON con el
    archivo metido en base64: ese base64 pesa ~33% más que el archivo real
    y obligaba a leer/parsear el body completo como un JSON gigante antes
    de poder hacer nada -- con archivos de decenas de MB eso es lo que
    estaba tronando con 502 en Render (pasaba igual ya con el plan subido,
    porque no era falta de RAM/CPU sino el tiempo/tamaño de ese único
    paso). Aquí el archivo llega como bytes directos y se codifica a
    base64 ya del lado del servidor, en threadpool, solo para guardarlo
    igual que siempre en la base de datos."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):
        raise HTTPException(status_code=400, detail="Este trabajo no está en modelado ni esperando aprobación de diseño")
    if usuario["rol"] != "admin":
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
            raise HTTPException(status_code=403, detail="Solo el laboratorio puede subir el diseño")
    # Igual que en /api/rh/capacitacion/videos/subir: revisar el tamaño
    # ANTES de leer el archivo completo, para rechazar de una vez un
    # archivo demasiado grande sin gastar memoria ni tiempo del servidor.
    content_length_header = request.headers.get("content-length")
    if content_length_header and content_length_header.isdigit():
        if int(content_length_header) > (MAX_DISENO_ARCHIVO_BYTES * 2) + (5 * 1024 * 1024):
            raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")

    async def _leer_y_codificar(subida: UploadFile, etiqueta: str) -> str:
        contenido = await subida.read()
        if len(contenido) > MAX_DISENO_ARCHIVO_BYTES:
            raise HTTPException(status_code=400, detail=f"{etiqueta} pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")
        # base64.b64encode de un archivo grande es trabajo de CPU, no de
        # red/disco -- se manda al threadpool para no trabar el event loop
        # (y a las demás peticiones en curso) mientras se hace.
        return await run_in_threadpool(lambda: base64.b64encode(contenido).decode("ascii"))

    archivo_base64 = await _leer_y_codificar(archivo, "El archivo")
    archivo_base64_2 = await _leer_y_codificar(archivo_2, "El segundo archivo") if archivo_2 is not None else None

    estado_anterior = trabajo["estado"]
    db.subir_diseno_laboratorio(
        trabajo_id, archivo_base64, archivo.filename, usuario["id"],
        archivo_base64_2=archivo_base64_2, archivo_nombre_2=(archivo_2.filename if archivo_2 is not None else None),
    )
    if estado_anterior == "modelado":
        db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "aprobar_diseno")
    nombres_diseno = archivo.filename or "archivo"
    if archivo_2 is not None and archivo_2.filename:
        nombres_diseno += f" + {archivo_2.filename}"
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"Subió el diseño ({nombres_diseno}) para que el estudiante lo apruebe.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)''',
        ],
    ],
    'backend/db.py': [
        [
            '''        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_nombre_2 TEXT;
        -- Cuando el trabajo ya se entregó, se vacía el contenido de estos
        -- archivos (pueden pesar decenas de MB) para liberar espacio -- este
        -- campo marca que ya se hizo, para no reintentarlo ni mostrar un
        -- archivo vacío como si fuera válido.
        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_liberado BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    conn.commit()

    # Migración no destructiva: las tareas de proyecto que ya existían solo
    # tenían UN asignado (columna usuario_id) — se copian a la tabla nueva de
    # muchos-a-muchos para no perder esas asignaciones ya hechas. Ya no se
    # vuelve a tocar después de la primera vez (ON CONFLICT DO NOTHING).
    cur.execute("""
        INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id)
        SELECT id, usuario_id FROM proyecto_tareas WHERE usuario_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)
    conn.commit()''',
            '''        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_nombre_2 TEXT;
        -- Cuando el trabajo ya se entregó, se vacía el contenido de estos
        -- archivos (pueden pesar decenas de MB) para liberar espacio -- este
        -- campo marca que ya se hizo, para no reintentarlo ni mostrar un
        -- archivo vacío como si fuera válido.
        ALTER TABLE laboratorio_disenos ADD COLUMN IF NOT EXISTS archivo_liberado BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    conn.commit()

    # Normaliza diseños viejos subidos por la versión anterior del
    # formulario web: esa versión mandaba el archivo como Data URL
    # completo ("data:...;base64,XXXX") porque el navegador lo armaba con
    # FileReader.readAsDataURL. El visor 3D de la app de estudiantes
    # (Flutter) hace atob() directo sobre el valor guardado sin quitarle
    # ese prefijo -- un diseño viejo con el prefijo no cargaba ahí (el
    # visor de la web sí lo toleraba, porque recorta todo antes de la
    # primera coma). Se deja solo la parte de base64 puro. Después de la
    # primera vez este UPDATE ya no encuentra filas que cambiar, así que
    # es seguro dejarlo aquí para que corra en cada arranque.
    cur.execute("""
        UPDATE laboratorio_disenos SET archivo_base64 = split_part(archivo_base64, ',', 2)
        WHERE archivo_base64 LIKE 'data:%,%';
        UPDATE laboratorio_disenos SET archivo_base64_2 = split_part(archivo_base64_2, ',', 2)
        WHERE archivo_base64_2 LIKE 'data:%,%';
    """)
    conn.commit()

    # Migración no destructiva: las tareas de proyecto que ya existían solo
    # tenían UN asignado (columna usuario_id) — se copian a la tabla nueva de
    # muchos-a-muchos para no perder esas asignaciones ya hechas. Ya no se
    # vuelve a tocar después de la primera vez (ON CONFLICT DO NOTHING).
    cur.execute("""
        INSERT INTO proyecto_tarea_usuarios (tarea_id, usuario_id)
        SELECT id, usuario_id FROM proyecto_tareas WHERE usuario_id IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)
    conn.commit()''',
        ],
    ],
    'frontend/index.html': [
        [
            '''async function subirDisenoLaboratorioUI(trabajoId, input) {
  const archivo = input.files[0];
  if (!archivo) return;
  const archivo2 = input.files[1] || null;
  const leerComoBase64 = (f) => new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsDataURL(f);
  });
  const base64 = await leerComoBase64(archivo);
  const base64_2 = archivo2 ? await leerComoBase64(archivo2) : null;
  try {
    const body = { archivo_base64: base64, archivo_nombre: archivo.name };
    if (base64_2) {
      body.archivo_base64_2 = base64_2;
      body.archivo_nombre_2 = archivo2.name;
    }
    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: 'POST', body: JSON.stringify(body) });
    mostrarExito('Diseño subido correctamente');
    await abrirDetalleLaboratorio(trabajoId);
  } catch (e) {
    alert(e.message + '\\n\\nRevisando si el archivo alcanzó a guardarse antes del error...');
    try {
      await abrirDetalleLaboratorio(trabajoId);
    } catch (e2) {
      // El servidor sigue sin responder -- no hay forma de confirmar desde aquí todavía.
      // Cierra y vuelve a abrir el trabajo en un momento para revisar si se subió o no.
    }
  }
}''',
            '''async function subirDisenoLaboratorioUI(trabajoId, input) {
  const archivo = input.files[0];
  if (!archivo) return;
  const archivo2 = input.files[1] || null;
  // Se manda como multipart/form-data (FormData), no como JSON con el
  // archivo convertido a base64: eso inflaba el archivo ~33% y obligaba
  // al servidor a leer el body completo como un JSON gigante antes de
  // poder contestar -- con archivos grandes eso era lo que tronaba con
  // 502 en Render, incluso en un plan más grande. Por eso ya no se usa
  // el helper api() (que siempre manda JSON) sino fetch directo, igual
  // que ya se hace para subir videos de Capacitación/Turnos/Marketing.
  try {
    const formData = new FormData();
    formData.append('archivo', archivo);
    if (archivo2) formData.append('archivo_2', archivo2);
    const r = await fetch(`${API}/api/laboratorio/${trabajoId}/subir-diseno`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${SESION.token}` }, // sin Content-Type: el navegador arma el multipart solo
      body: formData,
    });
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error del servidor (código ${r.status}) — puede que falte redesplegar la última versión`); }
    mostrarExito('Diseño subido correctamente');
    await abrirDetalleLaboratorio(trabajoId);
  } catch (e) {
    alert(e.message + '\\n\\nRevisando si el archivo alcanzó a guardarse antes del error...');
    try {
      await abrirDetalleLaboratorio(trabajoId);
    } catch (e2) {
      // El servidor sigue sin responder -- no hay forma de confirmar desde aquí todavía.
      // Cierra y vuelve a abrir el trabajo en un momento para revisar si se subió o no.
    }
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
    print("   git add backend/app.py backend/db.py frontend/index.html")
    print('   git commit -m "Laboratorio: subir diseno (STL) como multipart en vez de base64 en JSON -- arregla 502 con archivos grandes"')
    print("   git push")


if __name__ == "__main__":
    main()
