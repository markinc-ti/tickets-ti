# -*- coding: utf-8 -*-
"""
RH ASISTENCIA: BOTONES DE EXCEL POR SEMANA / MES TAMBIEN EN LA PRIMERA PANTALLA
En RH -> Asistencia, en "Que quieres ver?" (antes de elegir checador o sucursal)
ahora hay una fecha y los botones "Excel por semana" y "Excel por mes" de TODOS.
Dentro de un checador/sucursal siguen junto a "Exportar Excel".
Correr DESPUES de fix_asistencia_excel_semana_mes.py
Toca: frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_asistencia_excel_botones_inicio.py
"""
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "        x.horario ? asis_txtHorario(x.horario) : 'horario general')).join('')}</div>` : ''}\n    <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n",
   "        x.horario ? asis_txtHorario(x.horario) : 'horario general')).join('')}</div>` : ''}\n    <div class=\"cv-caja\" style=\"display:flex; gap:8px; align-items:flex-end; flex-wrap:wrap; margin:0 0 14px; padding:10px 12px;\">\n      <div class=\"field\" style=\"margin:0;\"><label>📥 Excel de todos · semana o mes de</label><input type=\"date\" id=\"asis_ref\" value=\"${new Date().toLocaleDateString('sv-SE')}\" /></div>\n      <button class=\"secondary\" onclick=\"ASIS.vista=null; asis_excelPeriodo(this, 'semana')\">📅 Excel por semana</button>\n      <button class=\"secondary\" onclick=\"ASIS.vista=null; asis_excelPeriodo(this, 'mes')\">📆 Excel por mes</button>\n    </div>\n    <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">\n"
  ],
  [
   "  const ref = (document.getElementById('asis_desde') || {}).value || ASIS.datos.desde;\n",
   "  const ref = (document.getElementById('asis_desde') || {}).value || (document.getElementById('asis_ref') || {}).value\n    || (ASIS.datos && ASIS.datos.desde) || new Date().toLocaleDateString('sv-SE');\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_asistencia_excel_botones_inicio.py")
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
