#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador de sistema TI (frontend/cotizador_costos.html): los "Datos de
pago" que agregamos en el parche anterior (fix_cotizador_costos_datos_pago.py)
eran por cotizacion -- este los cambia a un solo dato GLOBAL que se
configura una sola vez y aplica automaticamente a TODAS tus cotizaciones
(la que estes viendo y las nuevas que hagas), sin tener que volver a
escribirlo cada vez.

REEMPLAZA al comportamiento del parche anterior (ese ya no hace falta
volver a correrlo -- este script asume que ya lo corriste, porque ya
esta subido a tu repo).

Que cambia:

1. backend/db.py
   - Nueva tabla cotizador_costos_configuracion: una sola fila (id=1)
     con el dato de pago global (no por empresa, no por cotizacion).
   - Funciones para leerlo y guardarlo.

2. backend/app.py
   - GET/PUT /api/superadmin/cotizador-costos/datos-pago (solo
     superadmin) para leer/guardar ese dato global.

3. frontend/cotizador_costos.html
   - La seccion "06 Datos de pago" ahora tiene su propio boton
     "Guardar datos de pago" (independiente del boton "Guardar en el
     sistema" de la cotizacion) -- lo que escribas ahi se guarda una
     sola vez y ya sale en todas tus cotizaciones.
   - Al abrir cualquier cotizacion, ese campo se precarga solo con el
     dato global guardado.
   - Ya no se guarda ni se carga ese dato dentro de cada cotizacion
     individual (config_json) -- ahora vive en un solo lugar.
"""
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '        WHERE NOT EXISTS (SELECT 1 FROM cotizaciones_costos cc WHERE cc.empresa_id = c.empresa_id)\n    """)\n    conn.commit()\n\n    # ---- Turnos por sucursal (como en un banco): un cliente toma un turno,',
            '        WHERE NOT EXISTS (SELECT 1 FROM cotizaciones_costos cc WHERE cc.empresa_id = c.empresa_id)\n    """)\n    conn.commit()\n\n    # Datos de pago (banco, cuenta, CLABE...) del Cotizador de sistema TI\n    # (frontend/cotizador_costos.html) -- es UNA sola fila global (no por\n    # empresa ni por cotizacion): ese cotizador lo usa solo el superadmin\n    # para armar propuestas a prospectos, y sus datos de pago deben salir\n    # igual en todas sus cotizaciones sin repetirlos cada vez.\n    cur.execute("""\n        CREATE TABLE IF NOT EXISTS cotizador_costos_configuracion (\n            id INTEGER PRIMARY KEY,\n            datos_pago TEXT\n        );\n    """)\n    conn.commit()\n\n    # ---- Turnos por sucursal (como en un banco): un cliente toma un turno,',
        ],
        [
            '            "margen_pct": margen,\n            "actualizado_en": f["actualizado_en"],\n        })\n    return resultado\n\n\n# ---- Shopify (ventas de la tienda en línea) ----',
            '            "margen_pct": margen,\n            "actualizado_en": f["actualizado_en"],\n        })\n    return resultado\n\n\ndef obtener_datos_pago_cotizador_costos():\n    """Dato global (no por empresa ni por cotizacion) del Cotizador de\n    sistema TI -- ver comentario en la creación de la tabla."""\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute("SELECT datos_pago FROM cotizador_costos_configuracion WHERE id = 1")\n    row = cur.fetchone()\n    cur.close(); conn.close()\n    return row["datos_pago"] if row else None\n\n\ndef guardar_datos_pago_cotizador_costos(datos_pago):\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\n        """INSERT INTO cotizador_costos_configuracion (id, datos_pago) VALUES (1, %s)\n           ON CONFLICT (id) DO UPDATE SET datos_pago = EXCLUDED.datos_pago""",\n        (datos_pago,),\n    )\n    conn.commit()\n    cur.close(); conn.close()\n\n\n# ---- Shopify (ventas de la tienda en línea) ----',
        ],
    ],
    'backend/app.py': [
        [
            '@app.delete("/api/superadmin/cotizaciones/{cotizacion_id}")\ndef api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_superadmin)):\n    if not db.obtener_cotizacion_costos(cotizacion_id):\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    db.eliminar_cotizacion_costos(cotizacion_id)\n    return {"ok": True}\n\n\n@app.post("/api/empresas/{empresa_id}/logo")',
            '@app.delete("/api/superadmin/cotizaciones/{cotizacion_id}")\ndef api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_superadmin)):\n    if not db.obtener_cotizacion_costos(cotizacion_id):\n        raise HTTPException(status_code=404, detail="Cotización no encontrada")\n    db.eliminar_cotizacion_costos(cotizacion_id)\n    return {"ok": True}\n\n\nclass DatosPagoCotizadorCostosIn(BaseModel):\n    datos_pago: Optional[str] = None\n\n\n@app.get("/api/superadmin/cotizador-costos/datos-pago")\ndef api_obtener_datos_pago_cotizador_costos(_: dict = Depends(requiere_superadmin)):\n    """Dato global (banco/cuenta) del Cotizador de sistema TI -- el mismo\n    para todas las cotizaciones que arma el superadmin, no por cotización."""\n    return {"datos_pago": db.obtener_datos_pago_cotizador_costos()}\n\n\n@app.put("/api/superadmin/cotizador-costos/datos-pago")\ndef api_guardar_datos_pago_cotizador_costos(payload: DatosPagoCotizadorCostosIn, _: dict = Depends(requiere_superadmin)):\n    db.guardar_datos_pago_cotizador_costos(payload.datos_pago)\n    return {"ok": True}\n\n\n@app.post("/api/empresas/{empresa_id}/logo")',
        ],
    ],
    'frontend/cotizador_costos.html': [
        [
            '    <h2 class="section-title"><span class="n">06</span>Datos de pago</h2>\n    <p style="font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;">Si lo llenas, aparece al final de la cotización para que el cliente sepa cómo pagarte si la acepta.</p>\n    <label class="field"><span class="lbl">Banco, cuenta, CLABE, etc. (opcional)</span>\n      <textarea id="c-datos-pago" placeholder="Ej. BBVA, cuenta 0123456789, CLABE 012345678901234567, a nombre de Mark Inc"></textarea>\n    </label>\n\n    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>',
            '    <h2 class="section-title"><span class="n">06</span>Datos de pago</h2>\n    <p style="font-size:0.78rem;color:var(--gris-1);margin-top:-6px;margin-bottom:8px;">Se configura una sola vez aquí y aparece automáticamente al final de TODAS tus cotizaciones (esta y las que hagas después) — no hace falta repetirlo en cada una.</p>\n    <label class="field"><span class="lbl">Banco, cuenta, CLABE, etc. (opcional)</span>\n      <textarea id="c-datos-pago" placeholder="Ej. BBVA, cuenta 0123456789, CLABE 012345678901234567, a nombre de Mark Inc"></textarea>\n    </label>\n    <button class="add-resource" style="width:100%; text-align:center; padding:8px;" id="btn-guardar-datos-pago">Guardar datos de pago (aplica a todas tus cotizaciones)</button>\n    <div class="hint" id="datos-pago-hint"></div>\n\n    <div class="internal-box" id="internal-box"><!-- se llena por JS --></div>',
        ],
        [
            "      if(cli.notas) document.getElementById('c-notas').value = cli.notas;\n      if(cli.datos_pago) document.getElementById('c-datos-pago').value = cli.datos_pago;\n      if(guardado.showResources !== undefined){ state.showResources = guardado.showResources; document.getElementById('t-recursos').checked = guardado.showResources; }",
            "      if(cli.notas) document.getElementById('c-notas').value = cli.notas;\n      if(guardado.showResources !== undefined){ state.showResources = guardado.showResources; document.getElementById('t-recursos').checked = guardado.showResources; }",
        ],
        [
            "      intro: document.getElementById('c-intro').value,\n      notas: document.getElementById('c-notas').value,\n      datos_pago: document.getElementById('c-datos-pago').value,\n    },\n    showResources: state.showResources,",
            "      intro: document.getElementById('c-intro').value,\n      notas: document.getElementById('c-notas').value,\n    },\n    showResources: state.showResources,",
        ],
        [
            "async function _cargarDesdeServidor(){\n  const s = _sesionActual();\n  if(!s){ location.href = '/'; return; }\n  await _cargarListaEmpresas();",
            "async function _cargarDatosPagoGlobal(){\n  try{\n    const r = await fetch('/api/superadmin/cotizador-costos/datos-pago', { headers: _authHeaders() });\n    if(!r.ok) return;\n    const { datos_pago } = await r.json();\n    if(datos_pago) document.getElementById('c-datos-pago').value = datos_pago;\n    renderPreview();\n  }catch(e){ /* si falla, se sigue sin el dato precargado -- no bloquea el resto */ }\n}\n\nasync function _cargarDesdeServidor(){\n  const s = _sesionActual();\n  if(!s){ location.href = '/'; return; }\n  await _cargarListaEmpresas();\n  await _cargarDatosPagoGlobal();",
        ],
        [
            '_cargarDesdeServidor();\n\n})();\n</script>\n</body>\n</html>',
            "document.getElementById('btn-guardar-datos-pago').addEventListener('click', async () => {\n  const btn = document.getElementById('btn-guardar-datos-pago');\n  const hint = document.getElementById('datos-pago-hint');\n  const original = btn.textContent;\n  btn.disabled = true; btn.textContent = 'Guardando…';\n  try{\n    const r = await fetch('/api/superadmin/cotizador-costos/datos-pago', {\n      method: 'PUT', headers: _authHeaders(),\n      body: JSON.stringify({ datos_pago: document.getElementById('c-datos-pago').value }),\n    });\n    if(r.status === 401){ location.href = '/'; return; }\n    if(!r.ok) throw new Error('error');\n    hint.textContent = 'Datos de pago guardados — ya aplican a todas tus cotizaciones.';\n  } catch(e){\n    hint.textContent = 'No se pudo guardar — revisa tu conexión e inténtalo de nuevo.';\n  } finally {\n    btn.disabled = false; btn.textContent = original;\n  }\n});\n\n_cargarDesdeServidor();\n\n})();\n</script>\n</body>\n</html>",
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
                print("Es probable que el archivo ya haya cambiado desde que se genero este parche.")
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
    print("    git add backend/db.py backend/app.py frontend/cotizador_costos.html")
    print('    git commit -m "Cotizador de sistema TI: datos de pago globales (aplican a todas las cotizaciones)"')
    print("    git push")


if __name__ == "__main__":
    main()
