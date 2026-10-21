# -*- coding: utf-8 -*-
"""
RH: "PERMISO POR HORAS" OBLIGA LAS HORAS Y "DIA SIN GOCE" ES EL DIA COMPLETO
- Permiso por horas: la casilla de horas queda marcada y fija; sin horas no se
  puede mandar (web, app y servidor).
- Dia sin goce de sueldo: por dia completo, sin horas (la casilla queda quitada
  y fija). La conversion automatica de 8 h debidas sigue igual.
REQUIERE haber corrido antes fix_rh_permiso_horas.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_permiso_horas_obligatorio.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n",
   "        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n    if payload.tipo == \"dia_libre_sin_goce\" and payload.horas:\n        raise HTTPException(status_code=400, detail=\"El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».\")\n    incidencia_id = db.crear_incidencia_rh(usuario[\"empresa_id\"], usuario[\"id\"], payload.tipo,\n                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,\n                                            payload.foto_base64, payload.horas)\n"
  ],
  [
   "        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n\n    objetivo = next((u for u in db.listar_usuarios(usuario[\"empresa_id\"]) if u[\"id\"] == payload.usuario_id), None)\n    if not objetivo:\n",
   "        raise HTTPException(status_code=400, detail=\"Las horas deben ser un número positivo\")\n    if payload.tipo == \"permiso_horas\" and not payload.horas:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n    if payload.tipo == \"dia_libre_sin_goce\" and payload.horas:\n        raise HTTPException(status_code=400, detail=\"El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».\")\n\n    objetivo = next((u for u in db.listar_usuarios(usuario[\"empresa_id\"]) if u[\"id\"] == payload.usuario_id), None)\n    if not objetivo:\n"
  ],
  [
   "            raise HTTPException(status_code=400, detail=\"Ya no se puede editar — esta incidencia ya pasó a Recursos Humanos\")\n    if payload.tipo and payload.tipo not in db.TIPOS_INCIDENCIA_RH and payload.tipo != incidencia[\"tipo\"]:\n        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    return db.editar_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, payload.tipo, payload.fecha_inicio,\n                                    payload.fecha_fin, payload.motivo, payload.horas)\n\n\n# ---- Libro de horas (cuánto debe cada empleado, y cómo lo va pagando) ----\n",
   "            raise HTTPException(status_code=400, detail=\"Ya no se puede editar — esta incidencia ya pasó a Recursos Humanos\")\n    if payload.tipo and payload.tipo not in db.TIPOS_INCIDENCIA_RH and payload.tipo != incidencia[\"tipo\"]:\n        raise HTTPException(status_code=400, detail=\"Tipo de incidencia inválido\")\n    # Permiso por horas: siempre con horas. Día sin goce: día completo (sin horas),\n    # salvo la conversión automática de horas que ya debía (esa sí lleva 8 h).\n    tipo_final = payload.tipo or incidencia[\"tipo\"]\n    horas_final = payload.horas if payload.horas is not None else incidencia.get(\"horas\")\n    horas = payload.horas\n    if tipo_final == \"permiso_horas\" and not horas_final:\n        raise HTTPException(status_code=400, detail=\"En un permiso por horas indica cuántas horas o minutos.\")\n    automatica = (incidencia.get(\"motivo\") or \"\").startswith(\"Generado automáticamente\")\n    if tipo_final == \"dia_libre_sin_goce\" and not automatica and horas_final:\n        if payload.horas:\n            raise HTTPException(status_code=400, detail=\"El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».\")\n        horas = 0  # se cambió a día sin goce: se le quitan las horas\n    return db.editar_incidencia_rh(usuario[\"empresa_id\"], incidencia_id, payload.tipo, payload.fecha_inicio,\n                                    payload.fecha_fin, payload.motivo, horas)\n\n\n# ---- Libro de horas (cuánto debe cada empleado, y cómo lo va pagando) ----\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rhd_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rhd_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked' : ''} onchange=\"document.getElementById('rhd_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rhd_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n",
   "      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rhd_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rhd_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked disabled' : ''} onchange=\"document.getElementById('rhd_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <p id=\"rhd_nota_horas\" style=\"font-size:11px; color:var(--muted); margin:-6px 0 8px;\">${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'Obligatorio: indica las horas y minutos.' : ''}</p>\n    <div class=\"field\" id=\"rhd_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n"
  ],
  [
   "  });\n}\n\n// \"Permiso por horas\" deja marcada la casilla de horas; los demás tipos la quitan.\nfunction tipoIncidenciaPorHoras(p) {\n  const porHoras = document.getElementById(p + '_tipo').value === 'permiso_horas';\n  const caja = document.getElementById(p + '_es_por_horas');\n  if (!caja) return;\n  caja.checked = porHoras;\n  document.getElementById(p + '_horas_wrap').style.display = porHoras ? 'block' : 'none';\n}\n\n",
   "  });\n}\n\n// \"Permiso por horas\": las horas son obligatorias (casilla marcada y fija).\n// \"Día sin goce de sueldo\": es el día completo (casilla quitada y fija).\n// Los demás tipos: se puede elegir.\nfunction tipoIncidenciaPorHoras(p) {\n  const tipo = document.getElementById(p + '_tipo').value;\n  const caja = document.getElementById(p + '_es_por_horas');\n  if (!caja) return;\n  const fijo = tipo === 'permiso_horas' || tipo === 'dia_libre_sin_goce';\n  const porHoras = tipo === 'permiso_horas';\n  caja.checked = porHoras;\n  caja.disabled = fijo;\n  const nota = document.getElementById(p + '_nota_horas');\n  if (nota) nota.textContent = tipo === 'permiso_horas' ? 'Obligatorio: indica las horas y minutos.'\n    : tipo === 'dia_libre_sin_goce' ? 'Es por el día completo (si es por horas, usa «Permiso por horas»).' : '';\n  document.getElementById(p + '_horas_wrap').style.display = porHoras ? 'block' : 'none';\n}\n\n"
  ],
  [
   "      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rh_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rh_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked' : ''} onchange=\"document.getElementById('rh_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <div class=\"field\" id=\"rh_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n",
   "      <div class=\"field\"><label>Fecha de fin (opcional, si son varios días)</label><input type=\"date\" id=\"rh_fecha_fin\" /></div>\n    </div>\n    <label style=\"font-size:12px; display:flex; align-items:center; gap:6px; margin: 4px 0 10px;\">\n      <input type=\"checkbox\" id=\"rh_es_por_horas\" ${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'checked disabled' : ''} onchange=\"document.getElementById('rh_horas_wrap').style.display = this.checked ? 'block' : 'none'\" style=\"width:auto;\" />\n      Es un permiso por horas, no todo el día\n    </label>\n    <p id=\"rh_nota_horas\" style=\"font-size:11px; color:var(--muted); margin:-6px 0 8px;\">${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'Obligatorio: indica las horas y minutos.' : ''}</p>\n    <div class=\"field\" id=\"rh_horas_wrap\" style=\"display:${META.tipos_incidencia_rh[0] === 'permiso_horas' ? 'block' : 'none'};\">\n      <label>¿Cuánto tiempo?</label>\n      <div class=\"row-2\">\n"
  ],
  [
   "          </select>\n        </div>\n      </div>\n      <p style=\"font-size:11px; color:var(--muted); margin-top:4px;\">Si el tipo es \"Día libre sin goce de sueldo\", estas horas se sumarán automáticamente a tu saldo por pagar cuando se apruebe.</p>\n    </div>\n    <div class=\"field\"><label>Motivo / detalles</label><textarea id=\"rh_motivo\" placeholder=\"Explica brevemente qué pasó...\"></textarea></div>\n    <div class=\"field\"><label>Foto de la receta o comprobante (opcional, máx. 5MB)</label><input type=\"file\" id=\"rh_foto\" accept=\"image/*\" /></div>\n",
   "          </select>\n        </div>\n      </div>\n      <p style=\"font-size:11px; color:var(--muted); margin-top:4px;\">Cuando se apruebe, estas horas se suman a las horas que debes.</p>\n    </div>\n    <div class=\"field\"><label>Motivo / detalles</label><textarea id=\"rh_motivo\" placeholder=\"Explica brevemente qué pasó...\"></textarea></div>\n    <div class=\"field\"><label>Foto de la receta o comprobante (opcional, máx. 5MB)</label><input type=\"file\" id=\"rh_foto\" accept=\"image/*\" /></div>\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_permiso_horas_obligatorio.py")
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
            if nuevo in texto:
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
