# -*- coding: utf-8 -*-
"""
Laboratorio en la app: GET /api/laboratorio?ligero=true regresa la lista sin
firmas ni comprobantes (pesan), para el módulo Laboratorio de la app.
REQUIERE haber corrido antes fix_privacidad_tiendas.py.
Toca: backend/app.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "\n\n@app.get(\"/api/laboratorio\")\ndef api_listar_laboratorio(estado: Optional[str] = None, sucursal_id: Optional[int] = None, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    if usuario[\"rol\"] != \"admin\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        sucursal_lab = db.obtener_sucursal_laboratorio(usuario[\"empresa_id\"])\n",
   "\n\n@app.get(\"/api/laboratorio\")\ndef api_listar_laboratorio(estado: Optional[str] = None, sucursal_id: Optional[int] = None, ligero: bool = False,\n                           usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):\n    if usuario[\"rol\"] != \"admin\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        sucursal_lab = db.obtener_sucursal_laboratorio(usuario[\"empresa_id\"])\n"
  ],
  [
   "            sucursal_id = mi_sucursal_id\n        # Si es la sucursal de Laboratorio, no se restringe — necesita ver los\n        # trabajos de TODAS las sucursales para poder recibirlos y fabricarlos.\n    return db.listar_trabajos_laboratorio(usuario[\"empresa_id\"], estado, sucursal_id)\n\n\n@app.get(\"/api/laboratorio/solicitantes/buscar\")\n",
   "            sucursal_id = mi_sucursal_id\n        # Si es la sucursal de Laboratorio, no se restringe — necesita ver los\n        # trabajos de TODAS las sucursales para poder recibirlos y fabricarlos.\n    lista = db.listar_trabajos_laboratorio(usuario[\"empresa_id\"], estado, sucursal_id)\n    if ligero:\n        # Para la app: sin firmas ni comprobantes (pesan); el detalle los trae.\n        for t in lista:\n            t[\"tiene_firma_recepcion\"] = bool(t.get(\"firma_recepcion\"))\n            for k in (\"firma_recepcion\", \"firma_entrega\", \"pago_comprobante_base64\", \"datos_factura_json\"):\n                t.pop(k, None)\n            for r in t.get(\"pagos_reportados\") or []:\n                r.pop(\"comprobante_base64\", None)\n    return lista\n\n\n@app.get(\"/api/laboratorio/solicitantes/buscar\")\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "def pagina_privacidad" not in f.read():
            print("Primero corre fix_privacidad_tiendas.py (y los anteriores), y luego este.")
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
