# -*- coding: utf-8 -*-
"""
LABORATORIO: TELEFONO EN LA LISTA Y PERMISO DE ADMINISTRADOR AL LABORATORIO
1) Lista de trabajos: nueva columna "Telefono" (del pedido o del estudiante);
   al tocarlo abre WhatsApp.
2) Quien es del Laboratorio (dado de alta en la sucursal marcada como
   laboratorio) tiene permiso de administrador en el modulo: registra pagos,
   firma, confirma llegada y entrega trabajos de CUALQUIER sucursal, y ya no le
   sale "este trabajo no es de tu sucursal" / "asignado a otra sucursal".
   Las demas sucursales siguen igual (solo lo suyo).
Correr DESPUES de fix_laboratorio_columna_matricula.py
Toca: backend/db.py, backend/app.py, frontend/index.html
Se puede correr varias veces.  Correr con:  py -3 fix_laboratorio_telefono_y_permiso.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    return \"\"\"\n        SELECT l.*, s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,\n               uc.nombre_completo AS creado_por_nombre, uc.username AS matricula, uc.rol AS creado_por_rol,\n               uel.nombre_completo AS entro_laboratorio_por_nombre,\n               urs.nombre_completo AS recibido_sucursal_por_nombre,\n               uent.nombre_completo AS entregado_por_nombre,\n",
   "    return \"\"\"\n        SELECT l.*, s.nombre AS sucursal_nombre, s.prefijo AS sucursal_prefijo,\n               uc.nombre_completo AS creado_por_nombre, uc.username AS matricula, uc.rol AS creado_por_rol,\n               uc.telefono_whatsapp AS creado_por_telefono,\n               uel.nombre_completo AS entro_laboratorio_por_nombre,\n               urs.nombre_completo AS recibido_sucursal_por_nombre,\n               uent.nombre_completo AS entregado_por_nombre,\n"
  ]
 ],
 "backend/app.py": [
  [
   "    estudiante: solo admin, quien tenga el privilegio 'acceso_laboratorio_entrega'\n    (se lo das a quien tú decidas, sin importar su rol), o el encargado de esa\n    misma sucursal (se valida en el endpoint que sea SU sucursal).\"\"\"\n    if usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\":\n        return usuario\n    raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n\n",
   "    estudiante: solo admin, quien tenga el privilegio 'acceso_laboratorio_entrega'\n    (se lo das a quien tú decidas, sin importar su rol), o el encargado de esa\n    misma sucursal (se valida en el endpoint que sea SU sucursal).\"\"\"\n    if usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\" \\\n            or _es_usuario_laboratorio(usuario):  # el Laboratorio tiene permiso de administrador en su módulo\n        return usuario\n    raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n\n"
  ],
  [
   "        faltante = round(trabajo[\"costo_total\"] - trabajo[\"pago_monto_total\"], 2)\n        if faltante <= 0:\n            raise HTTPException(status_code=400, detail=\"Este trabajo ya está cubierto — no hace falta abonar más\")\n    if usuario[\"rol\"] != \"admin\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n",
   "        faltante = round(trabajo[\"costo_total\"] - trabajo[\"pago_monto_total\"], 2)\n        if faltante <= 0:\n            raise HTTPException(status_code=400, detail=\"Este trabajo ya está cubierto — no hace falta abonar más\")\n    if not _es_usuario_laboratorio(usuario):  # el Laboratorio (y el admin) puede con cualquier sucursal\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n"
  ],
  [
   "    faltante = round(trabajo[\"costo_total\"] - trabajo[\"pago_monto_total\"], 2)\n    if faltante > 0:\n        raise HTTPException(status_code=400, detail=f\"Falta cubrir ${faltante:,.2f} del pago antes de continuar\")\n    if usuario[\"rol\"] not in (\"admin\", \"estudiante\"):\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n",
   "    faltante = round(trabajo[\"costo_total\"] - trabajo[\"pago_monto_total\"], 2)\n    if faltante > 0:\n        raise HTTPException(status_code=400, detail=f\"Falta cubrir ${faltante:,.2f} del pago antes de continuar\")\n    if usuario[\"rol\"] != \"estudiante\" and not _es_usuario_laboratorio(usuario):\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=\"Este trabajo no es de tu sucursal\")\n"
  ],
  [
   "        raise HTTPException(status_code=400, detail=\"Este trabajo no está en camino de regreso a la sucursal\")\n    if trabajo.get(\"destino_tipo\") == \"escuela\":\n        raise HTTPException(status_code=400, detail=\"Este trabajo se lleva a la escuela: se entrega ahí directamente, con la firma del estudiante\")\n    if usuario[\"rol\"] != \"admin\":\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"entrega_sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=f\"Este trabajo va a {trabajo.get('destino_texto')}, no a tu sucursal\")\n",
   "        raise HTTPException(status_code=400, detail=\"Este trabajo no está en camino de regreso a la sucursal\")\n    if trabajo.get(\"destino_tipo\") == \"escuela\":\n        raise HTTPException(status_code=400, detail=\"Este trabajo se lleva a la escuela: se entrega ahí directamente, con la firma del estudiante\")\n    if not _es_usuario_laboratorio(usuario):\n        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n        if not mi_sucursal_id or trabajo[\"entrega_sucursal_id\"] != mi_sucursal_id:\n            raise HTTPException(status_code=403, detail=f\"Este trabajo va a {trabajo.get('destino_texto')}, no a tu sucursal\")\n"
  ],
  [
   "    if len(q) < 2:\n        raise HTTPException(status_code=400, detail=\"Escribe al menos 2 caracteres para buscar\")\n    resultados = db.buscar_trabajos_laboratorio_para_entrega(usuario[\"empresa_id\"], q)\n    mi_sucursal_id = None if usuario[\"rol\"] == \"admin\" else db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    for r in resultados:\n        r[\"es_mi_sucursal\"] = usuario[\"rol\"] == \"admin\" or (mi_sucursal_id is not None and r[\"sucursal_id\"] == mi_sucursal_id)\n    return resultados\n\n\n",
   "    if len(q) < 2:\n        raise HTTPException(status_code=400, detail=\"Escribe al menos 2 caracteres para buscar\")\n    resultados = db.buscar_trabajos_laboratorio_para_entrega(usuario[\"empresa_id\"], q)\n    es_lab = _es_usuario_laboratorio(usuario)  # admin o Laboratorio: todas las sucursales son \"suyas\"\n    mi_sucursal_id = None if es_lab else db.obtener_sucursal_id_usuario(usuario[\"id\"])\n    for r in resultados:\n        r[\"es_mi_sucursal\"] = es_lab or (mi_sucursal_id is not None and r[\"sucursal_id\"] == mi_sucursal_id)\n    return resultados\n\n\n"
  ],
  [
   "    else:\n        if trabajo[\"estado\"] != \"listo_entrega\":\n            raise HTTPException(status_code=400, detail=\"Este trabajo todavía no está listo para entregar\")\n        if not (usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\"):\n            raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n        if usuario[\"rol\"] != \"admin\":\n            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n            if not mi_sucursal_id or trabajo[\"entrega_sucursal_id\"] != mi_sucursal_id:\n                raise HTTPException(status_code=403, detail=f\"Este trabajo se entrega en {trabajo.get('destino_texto')}, no en tu sucursal\")\n",
   "    else:\n        if trabajo[\"estado\"] != \"listo_entrega\":\n            raise HTTPException(status_code=400, detail=\"Este trabajo todavía no está listo para entregar\")\n        if not (usuario[\"rol\"] == \"admin\" or usuario.get(\"acceso_laboratorio_entrega\", False) or usuario[\"rol\"] == \"encargado_sucursal\"\n                or _es_usuario_laboratorio(usuario)):\n            raise HTTPException(status_code=403, detail=\"No tienes el privilegio para recibir o entregar trabajos de laboratorio\")\n        if not _es_usuario_laboratorio(usuario):\n            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario[\"id\"])\n            if not mi_sucursal_id or trabajo[\"entrega_sucursal_id\"] != mi_sucursal_id:\n                raise HTTPException(status_code=403, detail=f\"Este trabajo se entrega en {trabajo.get('destino_texto')}, no en tu sucursal\")\n"
  ]
 ],
 "frontend/index.html": [
  [
   "    </div>\n    ${barraBusquedaDiscreta('busq_laboratorio', 'tbody_laboratorio', 'folio, matrícula, solicitante…')}\n    <table class=\"users\">\n      <thead><tr><th>Folio</th><th>Matrícula</th><th>Solicitante</th><th>Universidad/Clínica</th><th>Piezas</th><th>Estado</th><th>Días</th><th></th></tr></thead>\n      <tbody id=\"tbody_laboratorio\">\n        ${trabajos.map(w => `\n          <tr>\n            <td>${escapeHtml(w.folio)}</td>\n            <td style=\"font-family:'JetBrains Mono',monospace;\">${w.creado_por_rol === 'estudiante' && w.matricula ? escapeHtml(w.matricula) : '<span style=\"color:var(--muted);\">—</span>'}</td>\n            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n",
   "    </div>\n    ${barraBusquedaDiscreta('busq_laboratorio', 'tbody_laboratorio', 'folio, matrícula, solicitante…')}\n    <table class=\"users\">\n      <thead><tr><th>Folio</th><th>Matrícula</th><th>Teléfono</th><th>Solicitante</th><th>Universidad/Clínica</th><th>Piezas</th><th>Estado</th><th>Días</th><th></th></tr></thead>\n      <tbody id=\"tbody_laboratorio\">\n        ${trabajos.map(w => `\n          <tr>\n            <td>${escapeHtml(w.folio)}</td>\n            <td style=\"font-family:'JetBrains Mono',monospace;\">${w.creado_por_rol === 'estudiante' && w.matricula ? escapeHtml(w.matricula) : '<span style=\"color:var(--muted);\">—</span>'}</td>\n            <td style=\"white-space:nowrap;\">${(() => { const tel = w.telefono || (w.creado_por_rol === 'estudiante' ? w.creado_por_telefono : ''); return tel ? `<a href=\"https://wa.me/${String(tel).replace(/\\D/g, '').replace(/^(\\d{10})$/, '52$1')}\" target=\"_blank\" title=\"Abrir WhatsApp\" style=\"color:inherit;\">${escapeHtml(tel)}</a>` : '<span style=\"color:var(--muted);\">—</span>'; })()}</td>\n            <td>${escapeHtml(w.solicitante_nombre)} <span style=\"color:var(--muted); font-size:11px;\">(${NOMBRES_TIPO_SOLICITANTE_LAB[w.solicitante_tipo] || w.solicitante_tipo})</span></td>\n            <td>${w.universidad_clinica ? escapeHtml(w.universidad_clinica) : '—'}</td>\n            <td>${w.piezas.length}</td>\n"
  ],
  [
   "            <td>${w.dias_transcurridos !== null ? `${w.dias_transcurridos}d` : '—'}</td>\n            <td><button class=\"secondary\" style=\"padding:5px 10px; font-size:11px;\" onclick=\"abrirDetalleLaboratorio(${w.id})\">Ver</button></td>\n          </tr>\n        `).join('') || '<tr><td colspan=\"8\" class=\"empty-col\">— sin trabajos registrados —</td></tr>'}\n      </tbody>\n    </table>\n  `;\n",
   "            <td>${w.dias_transcurridos !== null ? `${w.dias_transcurridos}d` : '—'}</td>\n            <td><button class=\"secondary\" style=\"padding:5px 10px; font-size:11px;\" onclick=\"abrirDetalleLaboratorio(${w.id})\">Ver</button></td>\n          </tr>\n        `).join('') || '<tr><td colspan=\"9\" class=\"empty-col\">— sin trabajos registrados —</td></tr>'}\n      </tbody>\n    </table>\n  `;\n"
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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_laboratorio_telefono_y_permiso.py")
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
