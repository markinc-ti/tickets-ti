# -*- coding: utf-8 -*-
"""
RH PEYMAR: "MANDAR A TODOS A LOS CHECADORES"
- RH -> Personal: boton "Mandar a todos a los checadores" (sale cuando ya hay
  checadores conectados). Da de alta, con su No. y nombre, a todo el personal
  activo que todavia no esta en ningun checador. Antes avisa si en los
  checadores hay gente sin ligar (para ligarla primero y no duplicar).
REQUIERE haber corrido antes fix_logistica_checadas.py.
Toca: backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_rh_personal_a_checadores.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return r\n\n\nclass BajaPersonalIn(BaseModel):\n    fecha: Optional[str] = None\n    motivo: str = Field(min_length=3, max_length=300)\n",
   "    return r\n\n\n@app.post(\"/api/rh/personal/a-checadores\")\ndef api_todo_personal_a_checadores(simular: bool = False, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    \"\"\"Manda a los checadores conectados a TODO el personal activo con No. que todavía no\n    está en ninguno (para cuando se conectan checadores nuevos después de cargar al personal).\n    A quien ya está ligado en algún checador no se le toca. simular=True solo cuenta.\"\"\"\n    _requiere_rh_sin_microsip(usuario)\n    empresa_id = usuario[\"empresa_id\"]\n    checadores, gente, _ = db.datos_red_checadores(empresa_id)\n    if not checadores:\n        raise HTTPException(status_code=400, detail=\"No hay checadores conectados: da de alta el checador en Asistencia → 🔌 Conexión checadores.\")\n    ligados = {g[\"usuario_id\"] for g in gente if g.get(\"usuario_id\") and not g.get(\"baja_en\")}\n    pendientes = [p for p in db.listar_personal_rh(empresa_id)\n                  if p.get(\"numero_empleado\") and p[\"id\"] not in ligados and str(p[\"numero_empleado\"]).strip().isdigit()]\n    # Sin ligar en el checador pero con nombre parecido: mejor ligarlos primero (no duplicar).\n    sin_ligar = [g for g in gente if not g.get(\"usuario_id\") and not g.get(\"baja_en\")]\n    if simular:\n        return {\"pendientes\": len(pendientes), \"checadores\": [k.get(\"nombre\") or k[\"sn\"] for k in checadores],\n                \"sin_ligar_en_checadores\": len(sin_ligar)}\n    enviados, avisos = 0, []\n    for p in pendientes:\n        r = _pasar_a_checadores(empresa_id, p, usuario[\"id\"])\n        if r.get(\"enviados\"):\n            enviados += 1\n        avisos += [f\"{p['nombre_completo']}: {o}\" for o in r.get(\"omitidos\", [])]\n    return {\"enviados\": enviados, \"avisos\": avisos[:50]}\n\n\nclass BajaPersonalIn(BaseModel):\n    fecha: Optional[str] = None\n    motivo: str = Field(min_length=3, max_length=300)\n"
  ]
 ],
 "frontend/index.html": [
  [
   "      <button class=\"primary\" onclick=\"abrirFormPersonal()\">➕ Dar de alta</button>\n      <button class=\"secondary\" onclick=\"abrirNavesDepartamentos()\">🏭 ${escapeHtml(etiquetaNave())}s y departamentos</button>\n      <button class=\"secondary\" onclick=\"abrirImportarPersonal()\">📥 Importar Excel</button>\n      <input placeholder=\"Buscar nombre, No., puesto…\" value=\"${escapeHtml(PERSONAL.filtro)}\" oninput=\"PERSONAL.filtro=this.value; pintarPersonalRH(); const i=document.getElementById('busqPersonal'); i.focus(); i.setSelectionRange(i.value.length,i.value.length);\" id=\"busqPersonal\" style=\"flex:1; min-width:180px;\" />\n      <select onchange=\"PERSONAL.nave=this.value; pintarPersonalRH();\">\n        <option value=\"\">Todas las ${escapeHtml(etiquetaNave().toLowerCase())}s</option>\n",
   "      <button class=\"primary\" onclick=\"abrirFormPersonal()\">➕ Dar de alta</button>\n      <button class=\"secondary\" onclick=\"abrirNavesDepartamentos()\">🏭 ${escapeHtml(etiquetaNave())}s y departamentos</button>\n      <button class=\"secondary\" onclick=\"abrirImportarPersonal()\">📥 Importar Excel</button>\n      ${(d.checadores || []).length ? `<button class=\"secondary\" onclick=\"mandarTodosAChecadores(this)\" title=\"Para checadores nuevos: da de alta a todos los que todavía no están en ninguno\">📲 Mandar a todos a los checadores</button>` : ''}\n      <input placeholder=\"Buscar nombre, No., puesto…\" value=\"${escapeHtml(PERSONAL.filtro)}\" oninput=\"PERSONAL.filtro=this.value; pintarPersonalRH(); const i=document.getElementById('busqPersonal'); i.focus(); i.setSelectionRange(i.value.length,i.value.length);\" id=\"busqPersonal\" style=\"flex:1; min-width:180px;\" />\n      <select onchange=\"PERSONAL.nave=this.value; pintarPersonalRH();\">\n        <option value=\"\">Todas las ${escapeHtml(etiquetaNave().toLowerCase())}s</option>\n"
  ],
  [
   "      }\n      await renderPersonalRH();\n    } catch (e) { err.textContent = e.message; }\n  });\n}\n\n",
   "      }\n      await renderPersonalRH();\n    } catch (e) { err.textContent = e.message; }\n  });\n}\n\nasync function mandarTodosAChecadores(btn) {\n  await conBloqueoDeBoton(btn, async () => {\n    try {\n      const s = await api('/api/rh/personal/a-checadores?simular=true', { method: 'POST' });\n      if (!s.pendientes) { mostrarExito('Todos ya están en los checadores'); return; }\n      const aviso = s.sin_ligar_en_checadores\n        ? `\\n\\n⚠️ En los checadores hay ${s.sin_ligar_en_checadores} persona(s) sin ligar. Si son de tu personal, primero lígalas en Asistencia → 🔌 Conexión checadores (⭐ Ligar todas las sugeridas) para no duplicarlas.` : '';\n      if (!confirm(`Se van a dar de alta ${s.pendientes} persona(s) con su No. y nombre en: ${s.checadores.join(', ')}.${aviso}\\n\\n¿Continuar?`)) return;\n      const r = await api('/api/rh/personal/a-checadores', { method: 'POST' });\n      mostrarExito(`Mandados ${r.enviados}. Les llega en 1 o 2 minutos; después se registra la cara o la huella en el checador.`);\n      if (r.avisos.length) alert('No se mandó:\\n' + r.avisos.join('\\n'));\n    } catch (e) { alert(e.message); }\n  });\n}\n\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_rh_personal_a_checadores.py")
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
