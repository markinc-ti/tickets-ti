# -*- coding: utf-8 -*-
"""
LABORATORIO: COLUMNA MATRICULA EN LUGAR DE SUCURSAL
En la lista de trabajos del Laboratorio, la columna "Sucursal" ahora es
"Matricula" (la del estudiante que hizo el pedido en la app). Si el trabajo
lo dio de alta el mostrador, sale "-". El buscador tambien encuentra por matricula.
Toca: frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_laboratorio_columna_matricula.py
"""
import os
import sys

ARCHIVOS = {
 "frontend/index.html": [
  [
   "        ${db_estados_laboratorio().map(e => `<option value=\"${e}\" ${e===LABORATORIO_FILTRO_ESTADO?'selected':''}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join('')}\n      </select>\n    </div>\n    ${barraBusquedaDiscreta('busq_laboratorio', 'tbody_laboratorio', 'folio, solicitante, paciente…')}\n    <table class=\"users\">\n      <thead><tr><th>Folio</th><th>${t(\"campo.sucursal\",\"Sucursal\")}</th><th>Solicitante</th><th>Universidad/Clínica</th><th>Piezas</th><th>Estado</th><th>Días</th><th></th></tr></thead>\n      <tbody id=\"tbody_laboratorio\">\n        ${trabajos.map(w => `\n          <tr>\n            <td>${escapeHtml(w.folio)}</td>\n            <td>${w.sucursal_nombre ? escapeHtml(w.sucursal_nombre) : '—'}</td>\n            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n",
   "        ${db_estados_laboratorio().map(e => `<option value=\"${e}\" ${e===LABORATORIO_FILTRO_ESTADO?'selected':''}>${NOMBRES_ESTADO_LABORATORIO[e]}</option>`).join('')}\n      </select>\n    </div>\n    ${barraBusquedaDiscreta('busq_laboratorio', 'tbody_laboratorio', 'folio, matrícula, solicitante…')}\n    <table class=\"users\">\n      <thead><tr><th>Folio</th><th>Matrícula</th><th>Solicitante</th><th>Universidad/Clínica</th><th>Piezas</th><th>Estado</th><th>Días</th><th></th></tr></thead>\n      <tbody id=\"tbody_laboratorio\">\n        ${trabajos.map(w => `\n          <tr>\n            <td>${escapeHtml(w.folio)}</td>\n            <td style=\"font-family:'JetBrains Mono',monospace;\">${w.creado_por_rol === 'estudiante' && w.matricula ? escapeHtml(w.matricula) : '<span style=\"color:var(--muted);\">—</span>'}</td>\n            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_laboratorio_columna_matricula.py")
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
