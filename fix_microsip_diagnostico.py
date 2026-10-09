# -*- coding: utf-8 -*-
"""
Microsip -> Diagnostico: ya no truena con 'Error del servidor (500)'.
Si el usuario de Firebird de escritura no tiene permisos, ahora lo dice en
un paso con X y explica que hacer.

Toca: backend/app.py, backend/microsip_escritura.py. Se puede correr varias veces.
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    \"\"\"Revisa que se pueda escribir y hace una prueba completa (cliente +\n    cotización) que se deshace al final — no deja nada en Microsip.\"\"\"\n    cfg = _config_escritura_o_error(usuario[\"empresa_id\"])\n    return microsip_escritura.diagnostico(cfg, cfg.get(\"microsip_articulo_flete_id\"))\n\n\nclass LeerQrIn(BaseModel):\n",
   "    \"\"\"Revisa que se pueda escribir y hace una prueba completa (cliente +\n    cotización) que se deshace al final — no deja nada en Microsip.\"\"\"\n    cfg = _config_escritura_o_error(usuario[\"empresa_id\"])\n    try:\n        return microsip_escritura.diagnostico(cfg, cfg.get(\"microsip_articulo_flete_id\"))\n    except Exception as e:\n        raise HTTPException(status_code=400, detail=f\"El diagnóstico falló: {e}\")\n\n\nclass LeerQrIn(BaseModel):\n"
  ]
 ],
 "backend/microsip_escritura.py": [
  [
   "    partes = [l.strip(\" -\") for l in texto.splitlines() if l.strip(\" -\") and \"SQLCODE\" not in l and \"Error while\" not in l]\n    detalle = \"; \".join(partes[:4]) or texto\n    if \"no permission\" in texto.lower() or \"permission\" in texto.lower():\n        detalle += \" — el usuario de Firebird no tiene permiso de escritura (Administrar → Microsip → usuario de escritura).\"\n    if \"violation of PRIMARY or UNIQUE\" in texto or \"unique\" in texto.lower():\n        detalle += \" — ya existe un registro igual en Microsip.\"\n    return detalle\n",
   "    partes = [l.strip(\" -\") for l in texto.splitlines() if l.strip(\" -\") and \"SQLCODE\" not in l and \"Error while\" not in l]\n    detalle = \"; \".join(partes[:4]) or texto\n    if \"no permission\" in texto.lower() or \"permission\" in texto.lower():\n        detalle += (\" — ese usuario de Firebird no tiene permisos sobre las tablas de Microsip. Lo más sencillo: usa el mismo \"\n                    \"usuario con el que entra Microsip (normalmente SYSDBA) en 'Usuario de Firebird con escritura'.\")\n    if \"violation of PRIMARY or UNIQUE\" in texto or \"unique\" in texto.lower():\n        detalle += \" — ya existe un registro igual en Microsip.\"\n    return detalle\n"
  ],
  [
   "            aid = f[\"ARTICULO_ID\"] if f else None\n        if not paso(\"Artículo para la prueba\", bool(aid), str(aid or \"No hay artículos con precio\")):\n            return r\n    finally:\n        con.close()\n    try:\n",
   "            aid = f[\"ARTICULO_ID\"] if f else None\n        if not paso(\"Artículo para la prueba\", bool(aid), str(aid or \"No hay artículos con precio\")):\n            return r\n    except fdb.DatabaseError as e:\n        paso(\"Leer Microsip con ese usuario\", False, _error_fb(e))\n        return r\n    except Exception as e:\n        paso(\"Leer Microsip con ese usuario\", False, str(e))\n        return r\n    finally:\n        con.close()\n    try:\n"
  ]
 ]
}

NUEVOS = {}


def main():
    errores = []
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
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
