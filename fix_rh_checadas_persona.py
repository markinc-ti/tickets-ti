# -*- coding: utf-8 -*-
"""
RH en la app: ver las checadas de una persona (a tiempo / tarde / no llego).
- Nuevo endpoint GET /api/rh/asistencia/usuario/{id} (solo RH / Datos RH).
- Ligar personas ya solo se hace desde la web.
REQUIERE haber corrido antes fix_asistencia_checador_app.py.
Toca: backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_rh_checadas_persona.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "            \"aviso\": None if yo else \"Todavía no hay checadas tuyas del reloj checador. Si checas en un reloj, pide a Recursos Humanos que te liguen.\"}\n\n\nclass LigarCodigoIn(BaseModel):\n    codigo: str = Field(min_length=1, max_length=40)\n    usuario_id: int\n",
   "            \"aviso\": None if yo else \"Todavía no hay checadas tuyas del reloj checador. Si checas en un reloj, pide a Recursos Humanos que te liguen.\"}\n\n\n@app.get(\"/api/rh/asistencia/usuario/{usuario_id}\")\ndef api_asistencia_de_usuario(usuario_id: int, desde: Optional[str] = None, hasta: Optional[str] = None,\n                              usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Para RH en la app: las checadas de una persona, día por día (a tiempo / tarde / no llegó).\"\"\"\n    d, h = _rango_fechas(desde, hasta)\n    rep = _reporte_asistencia(usuario[\"empresa_id\"], d, h, solo_usuario_id=usuario_id)\n    emp = rep[\"empleados\"][0] if rep[\"empleados\"] else None\n    return {\"desde\": d.isoformat(), \"hasta\": h.isoformat(), \"empleado\": emp, \"permitido\": True,\n            \"aviso\": None if emp else \"Esta persona todavía no tiene checadas (o no está ligada a ningún checador).\"}\n\n\nclass LigarCodigoIn(BaseModel):\n    codigo: str = Field(min_length=1, max_length=40)\n    usuario_id: int\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_checadas_persona.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "hay_checadas_app" not in f.read():
            print("Primero corre fix_asistencia_checador_app.py (y los anteriores), y luego este.")
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
