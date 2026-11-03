# -*- coding: utf-8 -*-
"""
ADMINISTRAR: EXCEL CON TODOS LOS USUARIOS
Administrar -> Usuarios -> boton "Descargar Excel de usuarios": nombre,
usuario para entrar, N.o empleado, puesto, departamento, sucursal, rol,
WhatsApp y estado (activos primero). Sin contrasenas (estan cifradas).
Toca: frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_usuarios_excel.py
"""
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "  const libro = XLSX.utils.book_new();\n  XLSX.utils.book_append_sheet(libro, hoja, nombreHoja);\n  XLSX.writeFile(libro, `${nombreArchivo}_${new Date().toISOString().slice(0,10)}.xlsx`);\n}\n\n// Reportes de Microsip en Excel (botón \"📥 Reportes Microsip\" del Dashboard).\n",
   "  const libro = XLSX.utils.book_new();\n  XLSX.utils.book_append_sheet(libro, hoja, nombreHoja);\n  XLSX.writeFile(libro, `${nombreArchivo}_${new Date().toISOString().slice(0,10)}.xlsx`);\n}\n\n// Administrar → Usuarios → \"📥 Descargar Excel de usuarios\": todos los usuarios con su\n// usuario para entrar (las contraseñas no se pueden sacar: están cifradas).\nfunction descargarUsuariosExcel() {\n  if (typeof XLSX === 'undefined') { alert('No se pudo cargar el generador de Excel — revisa tu conexión e intenta de nuevo.'); return; }\n  const lista = (window._usuariosParaExcel || []).slice().sort((a, b) => (Number(b.activo) - Number(a.activo)) || String(a.nombre_completo || '').localeCompare(String(b.nombre_completo || ''), 'es'));\n  if (!lista.length) { alert('No hay usuarios.'); return; }\n  const filas = lista.map(u => ({\n    'Nombre': u.nombre_completo || '',\n    'Usuario (para entrar)': u.acceso_app === false ? '(sin acceso todavía)' : (u.username || ''),\n    'N.° empleado': u.numero_empleado || '',\n    'Puesto': u.puesto || '',\n    'Departamento': u.departamento || '',\n    'Sucursal': u.sucursal_nombre || '',\n    'Rol': NOMBRES_ROL[u.rol] || u.rol || '',\n    'WhatsApp': u.telefono_whatsapp || '',\n    'Estado': u.activo ? 'Activo' : 'Inactivo',\n  }));\n  const hoja = XLSX.utils.json_to_sheet(filas);\n  hoja['!cols'] = [{ wch: 34 }, { wch: 22 }, { wch: 12 }, { wch: 24 }, { wch: 18 }, { wch: 22 }, { wch: 18 }, { wch: 14 }, { wch: 10 }];\n  hoja['!autofilter'] = { ref: `A1:I${filas.length + 1}` };\n  const libro = XLSX.utils.book_new();\n  XLSX.utils.book_append_sheet(libro, hoja, 'Usuarios');\n  XLSX.writeFile(libro, `usuarios_${(META.empresa_nombre || 'empresa').replace(/[^\\w]+/g, '_')}_${new Date().toISOString().slice(0, 10)}.xlsx`);\n}\n\n// Reportes de Microsip en Excel (botón \"📥 Reportes Microsip\" del Dashboard).\n"
  ],
  [
   "// ---- Usuarios ----\n\nfunction renderUsuarios(tabsHtml, usuarios) {\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Administrar</h2>\n    ${tabsHtml}\n    ${barraBusquedaDiscreta('busq_usuarios', 'tbody_usuarios', 'nombre, N° empleado, puesto…')}\n    <table class=\"users\">\n      <thead><tr><th>Nombre</th><th>N.° empleado</th><th>Puesto</th><th>Usuario</th><th>Rol</th><th>${t(\"campo.sucursal\",\"Sucursal\")}</th><th>WhatsApp</th><th></th></tr></thead>\n",
   "// ---- Usuarios ----\n\nfunction renderUsuarios(tabsHtml, usuarios) {\n  window._usuariosParaExcel = usuarios;\n  document.getElementById('modalContent').innerHTML = `\n    <button class=\"close-btn\" onclick=\"cerrarModal()\">cerrar</button>\n    <h2>Administrar</h2>\n    ${tabsHtml}\n    <div style=\"display:flex; justify-content:flex-end; margin-bottom:6px;\">\n      <button class=\"secondary\" style=\"font-size:12px;\" onclick=\"descargarUsuariosExcel()\" title=\"Lista de todos los usuarios (sin contraseñas)\">📥 Descargar Excel de usuarios</button>\n    </div>\n    ${barraBusquedaDiscreta('busq_usuarios', 'tbody_usuarios', 'nombre, N° empleado, puesto…')}\n    <table class=\"users\">\n      <thead><tr><th>Nombre</th><th>N.° empleado</th><th>Puesto</th><th>Usuario</th><th>Rol</th><th>${t(\"campo.sucursal\",\"Sucursal\")}</th><th>WhatsApp</th><th></th></tr></thead>\n"
  ]
 ]
}

NUEVOS = {}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_usuarios_excel.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto and viejo not in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
