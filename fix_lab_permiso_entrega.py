# -*- coding: utf-8 -*-
"""
LABORATORIO -- al dar el permiso "Recibir/Entregar Lab." a un usuario, se prende
tambien su acceso al modulo Laboratorio (antes habia que marcar las dos casillas
o la persona no veia el modulo ni en la web ni en la app).
REQUIERE haber corrido antes fix_rh_autorizar_app.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_lab_permiso_entrega.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    if \"ventanilla_turnos\" in enviados:\n        kwargs_extra[\"ventanilla_turnos\"] = payload.ventanilla_turnos  # puede ser None para quitarla\n\n    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,\n                           payload.activo, payload.password, payload.puesto,\n                           acceso_equipos=payload.acceso_equipos, acceso_administracion=payload.acceso_administracion,\n",
   "    if \"ventanilla_turnos\" in enviados:\n        kwargs_extra[\"ventanilla_turnos\"] = payload.ventanilla_turnos  # puede ser None para quitarla\n\n    # \"Recibir/Entregar Lab.\" es un permiso DENTRO del módulo Laboratorio: si se\n    # da, se prende también el módulo (si no, la persona no lo ve ni en la web\n    # ni en la app aunque tenga el permiso).\n    if payload.acceso_laboratorio_entrega is True:\n        payload.acceso_laboratorio = True\n    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,\n                           payload.activo, payload.password, payload.puesto,\n                           acceso_equipos=payload.acceso_equipos, acceso_administracion=payload.acceso_administracion,\n"
  ]
 ],
 "frontend/index.html": [
  [
   "  const valorAnterior = !checkbox.checked;\n  try {\n    await api(`/api/usuarios/${usuarioId}`, { method: 'PATCH', body: JSON.stringify({ [campo]: checkbox.checked }) });\n    mostrarExito('Acceso actualizado exitosamente');\n  } catch (e) {\n    checkbox.checked = valorAnterior;\n    alert(e.message);\n",
   "  const valorAnterior = !checkbox.checked;\n  try {\n    await api(`/api/usuarios/${usuarioId}`, { method: 'PATCH', body: JSON.stringify({ [campo]: checkbox.checked }) });\n    // Recibir/Entregar Lab. vive dentro del módulo Laboratorio: el servidor lo prende solo.\n    if (campo === 'acceso_laboratorio_entrega' && checkbox.checked) {\n      const fila = checkbox.closest('tr');\n      const lab = fila && fila.querySelector('input[data-campo=\"acceso_laboratorio\"]');\n      if (lab) lab.checked = true;\n    }\n    mostrarExito(campo === 'acceso_laboratorio_entrega' && checkbox.checked\n      ? 'Acceso actualizado (también se prendió el módulo Laboratorio). Que cierre y vuelva a abrir la app.'\n      : 'Acceso actualizado exitosamente');\n  } catch (e) {\n    checkbox.checked = valorAnterior;\n    alert(e.message);\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_lab_permiso_entrega.py")
        sys.exit(1)
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "/api/rh/por-autorizar" not in f.read():
            print("Primero corre fix_rh_autorizar_app.py (y los anteriores), y luego este.")
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
