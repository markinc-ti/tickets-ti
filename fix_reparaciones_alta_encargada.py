# -*- coding: utf-8 -*-
"""
REPARACIONES -- la encargada de sucursal tambien da de alta reparaciones (orden de
servicio con foto y firma del cliente), en la web y en las apps. Lo que da de alta
queda siempre en SU sucursal. Recibir y entregar al cliente sigue igual.
REQUIERE haber corrido antes fix_lab_permiso_entrega.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_reparaciones_alta_encargada.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\n@app.post(\"/api/reparaciones\")\ndef api_crear_reparacion(payload: NuevaReparacion, usuario: dict = Depends(requiere_empresa)):\n    if not db.obtener_sucursal_reparacion(usuario[\"empresa_id\"], payload.sucursal_id):\n        raise HTTPException(status_code=404, detail=\"Sucursal no encontrada\")\n    departamentos = [d[\"nombre\"] for d in db.listar_departamentos(usuario[\"empresa_id\"])]\n",
   "\n@app.post(\"/api/reparaciones\")\ndef api_crear_reparacion(payload: NuevaReparacion, usuario: dict = Depends(requiere_empresa)):\n    if usuario[\"rol\"] == \"encargado_sucursal\":\n        # La encargada da de alta en SU sucursal (es la única que ve).\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if mi_sucursal_id:\n            payload.sucursal_id = mi_sucursal_id\n    if not db.obtener_sucursal_reparacion(usuario[\"empresa_id\"], payload.sucursal_id):\n        raise HTTPException(status_code=404, detail=\"Sucursal no encontrada\")\n    departamentos = [d[\"nombre\"] for d in db.listar_departamentos(usuario[\"empresa_id\"])]\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  document.getElementById('btnReporteReparacionesPDF').style.display = esStaff ? 'inline-block' : 'none';\n  document.getElementById('btnReporteReparacionesXLSX').style.display = esStaff ? 'inline-block' : 'none';\n  // El encargado de almacén SOLO entrega — no gestiona sucursales, y no tiene\n  // menú principal al que volver. El encargado de sucursal SOLO ve las\n  // reparaciones de su sucursal — no crea, ni gestiona nada.\n  document.getElementById('btnNuevaReparacion').style.display = esEncargadoSucursal ? 'none' : 'inline-block';\n  document.getElementById('tabRepSucursales').style.display = esAlmacen ? 'none' : 'inline-block';\n  document.getElementById('btnVolverDesdeReparaciones').style.display = esAlmacen ? 'none' : 'inline-block';\n  SUCURSALES_REPARACION_CACHE = await api('/api/reparaciones/sucursales');\n",
   "  document.getElementById('btnReporteReparacionesPDF').style.display = esStaff ? 'inline-block' : 'none';\n  document.getElementById('btnReporteReparacionesXLSX').style.display = esStaff ? 'inline-block' : 'none';\n  // El encargado de almacén SOLO entrega — no gestiona sucursales, y no tiene\n  // menú principal al que volver. La encargada de sucursal ve las reparaciones\n  // de su sucursal, las da de alta (orden de servicio), las recibe y las entrega.\n  document.getElementById('btnNuevaReparacion').style.display = 'inline-block';\n  document.getElementById('tabRepSucursales').style.display = esAlmacen ? 'none' : 'inline-block';\n  document.getElementById('btnVolverDesdeReparaciones').style.display = esAlmacen ? 'none' : 'inline-block';\n  SUCURSALES_REPARACION_CACHE = await api('/api/reparaciones/sucursales');\n"
  ],
  [
   "  REPARACIONES_TAB = tab;\n  document.getElementById('tabRepLista').classList.toggle('active', tab === 'lista');\n  document.getElementById('tabRepSucursales').classList.toggle('active', tab === 'sucursales');\n  document.getElementById('btnNuevaReparacion').style.display = (tab === 'lista' && SESION.usuario.rol !== 'encargado_sucursal') ? 'inline-block' : 'none';\n  if (tab === 'lista') await renderListaReparaciones();\n  else renderSucursalesReparacion();\n}\n",
   "  REPARACIONES_TAB = tab;\n  document.getElementById('tabRepLista').classList.toggle('active', tab === 'lista');\n  document.getElementById('tabRepSucursales').classList.toggle('active', tab === 'sucursales');\n  document.getElementById('btnNuevaReparacion').style.display = tab === 'lista' ? 'inline-block' : 'none';\n  if (tab === 'lista') await renderListaReparaciones();\n  else renderSucursalesReparacion();\n}\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_reparaciones_alta_encargada.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "acceso_laboratorio_entrega is True" not in f.read():
            print("Primero corre fix_lab_permiso_entrega.py (y los anteriores), y luego este.")
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
