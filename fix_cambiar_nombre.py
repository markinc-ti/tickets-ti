# -*- coding: utf-8 -*-
"""
Cada quien puede cambiar su propio nombre desde la app (el usuario para
entrar no cambia): POST /api/auth/cambiar-nombre {nombre} -> token nuevo.
REQUIERE haber corrido antes fix_lab_app_ligero.py.
Toca: backend/app.py
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "        raise HTTPException(status_code=401, detail=\"Tu contraseña actual no es correcta\")\n    db.actualizar_usuario(usuario[\"id\"], password=payload.password_nueva)\n    return {\"ok\": True}\n\n\n# ==================== EMPRESAS (superadmin) ====================\n",
   "        raise HTTPException(status_code=401, detail=\"Tu contraseña actual no es correcta\")\n    db.actualizar_usuario(usuario[\"id\"], password=payload.password_nueva)\n    return {\"ok\": True}\n\n\nclass CambiarMiNombre(BaseModel):\n    nombre: str = Field(min_length=3, max_length=120)\n\n\n@app.post(\"/api/auth/cambiar-nombre\")\ndef cambiar_mi_nombre(payload: CambiarMiNombre, usuario: dict = Depends(auth.get_current_user)):\n    \"\"\"Cada quien corrige su propio nombre (el usuario/login NO cambia).\n    Regresa un token nuevo porque el nombre viaja dentro de la sesión.\"\"\"\n    nombre = \" \".join(payload.nombre.split())\n    if len(nombre) < 3:\n        raise HTTPException(status_code=400, detail=\"Escribe tu nombre completo\")\n    db.actualizar_usuario(usuario[\"id\"], nombre_completo=nombre)\n    registro = db.obtener_usuario_por_username(usuario[\"username\"])\n    return {\n        \"token\": auth.crear_token(registro),\n        \"usuario\": {\n            \"id\": registro[\"id\"], \"username\": registro[\"username\"],\n            \"nombre\": registro[\"nombre_completo\"], \"rol\": registro[\"rol\"],\n            \"empresa_id\": registro[\"empresa_id\"],\n        },\n    }\n\n\n# ==================== EMPRESAS (superadmin) ====================\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "ligero: bool = False" not in f.read():
            print("Primero corre fix_lab_app_ligero.py (y los anteriores), y luego este.")
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
