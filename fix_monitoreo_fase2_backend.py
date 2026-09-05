# -*- coding: utf-8 -*-
"""
Fase 2 (parte backend) de "Monitoreo de empleados": infraestructura para
que el agente de Windows (proximo archivo, aparte) le reporte a la app.

Que hace:
1. Cada usuario monitoreado tiene un TOKEN propio (no su contrasena) --
   el agente de Windows lo usa para identificarse. Se genera desde
   Administrar -> Accesos con un boton nuevo junto al checkbox de
   Monitoreo.
2. Nueva tabla monitoreo_eventos: guarda cada evento (tipo: web /
   programa / documento), el detalle, la computadora de origen, y
   cuando paso.
3. Nuevo endpoint POST /api/monitoreo/eventos -- el agente lo llama para
   subir eventos en lote, autenticado con el token (no con sesion de
   usuario normal). Si el monitoreo se desactiva para esa persona, el
   endpoint deja de aceptar sus eventos automaticamente.
4. Endpoint GET /api/monitoreo/eventos para admins -- base para la
   bitacora de la Fase 3 (todavia sin pantalla en el frontend, eso
   viene despues).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_monitoreo_fase2_backend.py
"""
import sys

ARCHIVOS = {}

ARCHIVOS['backend/db.py'] = [
    [
        '    # ---- Monitoreo de empleados (Fase 1: consentimiento + activaci\u00f3n) ----\n'
        '    cur.execute("""\n'
        '        ALTER TABLE users ADD COLUMN IF NOT EXISTS monitoreo_activo BOOLEAN NOT NULL DEFAULT FALSE;\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS consentimientos_monitoreo (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            usuario_id INTEGER NOT NULL REFERENCES users(id),\n'
        '            fecha_aceptacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n'
        '            ip_address TEXT\n'
        '        );\n'
        '    """)\n'
        '    conn.commit()\n',

        '    # ---- Monitoreo de empleados (Fase 1: consentimiento + activaci\u00f3n) ----\n'
        '    cur.execute("""\n'
        '        ALTER TABLE users ADD COLUMN IF NOT EXISTS monitoreo_activo BOOLEAN NOT NULL DEFAULT FALSE;\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS consentimientos_monitoreo (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            usuario_id INTEGER NOT NULL REFERENCES users(id),\n'
        '            fecha_aceptacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n'
        '            ip_address TEXT\n'
        '        );\n'
        '    """)\n'
        '    conn.commit()\n'
        '\n'
        '    # ---- Monitoreo de empleados (Fase 2: token del agente + eventos) ----\n'
        '    cur.execute("""\n'
        '        ALTER TABLE users ADD COLUMN IF NOT EXISTS monitoreo_token TEXT;\n'
        '\n'
        '        CREATE TABLE IF NOT EXISTS monitoreo_eventos (\n'
        '            id SERIAL PRIMARY KEY,\n'
        '            usuario_id INTEGER NOT NULL REFERENCES users(id),\n'
        '            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n'
        '            computadora TEXT,\n'
        '            tipo TEXT NOT NULL,\n'
        '            detalle TEXT NOT NULL,\n'
        '            fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()\n'
        '        );\n'
        '        CREATE INDEX IF NOT EXISTS idx_monitoreo_eventos_usuario ON monitoreo_eventos(usuario_id, fecha_hora);\n'
        '    """)\n'
        '    conn.commit()\n',
    ],
    [
        'def registrar_aceptacion_monitoreo(usuario_id, ip_address):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute(\n'
        '        "INSERT INTO consentimientos_monitoreo (usuario_id, ip_address) VALUES (%s, %s)",\n'
        '        (usuario_id, ip_address),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n',

        'def registrar_aceptacion_monitoreo(usuario_id, ip_address):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute(\n'
        '        "INSERT INTO consentimientos_monitoreo (usuario_id, ip_address) VALUES (%s, %s)",\n'
        '        (usuario_id, ip_address),\n'
        '    )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def generar_token_monitoreo(usuario_id):\n'
        '    """Genera (o reemplaza) el token del agente de Windows para este\n'
        '    usuario. Se muestra UNA vez en el momento de generarlo -- la app no\n'
        '    lo vuelve a mostrar despu\u00e9s, hay que copiarlo entonces al agente."""\n'
        '    import secrets\n'
        '    token = secrets.token_urlsafe(32)\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("UPDATE users SET monitoreo_token = %s WHERE id = %s", (token, usuario_id))\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '    return token\n'
        '\n'
        '\n'
        'def obtener_usuario_por_token_monitoreo(token):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute("SELECT id, empresa_id, monitoreo_activo FROM users WHERE monitoreo_token = %s", (token,))\n'
        '    row = cur.fetchone()\n'
        '    cur.close(); conn.close()\n'
        '    return dict(row) if row else None\n'
        '\n'
        '\n'
        'def registrar_eventos_monitoreo(usuario_id, empresa_id, computadora, eventos):\n'
        '    """eventos: lista de dicts con \'tipo\', \'detalle\', y opcionalmente\n'
        '    \'fecha_hora\' (si no se manda, se usa el momento en que llega al\n'
        '    servidor)."""\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    for ev in eventos:\n'
        '        cur.execute(\n'
        '            """INSERT INTO monitoreo_eventos (usuario_id, empresa_id, computadora, tipo, detalle, fecha_hora)\n'
        '               VALUES (%s, %s, %s, %s, %s, COALESCE(%s, NOW()))""",\n'
        '            (usuario_id, empresa_id, computadora, ev.get("tipo"), ev.get("detalle"), ev.get("fecha_hora")),\n'
        '        )\n'
        '    conn.commit()\n'
        '    cur.close(); conn.close()\n'
        '\n'
        '\n'
        'def listar_eventos_monitoreo(empresa_id, usuario_id=None, computadora=None, tipo=None, limite=300):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    query = """SELECT e.id, e.usuario_id, u.nombre_completo, e.computadora, e.tipo, e.detalle, e.fecha_hora\n'
        '               FROM monitoreo_eventos e JOIN users u ON u.id = e.usuario_id\n'
        '               WHERE e.empresa_id = %s"""\n'
        '    params = [empresa_id]\n'
        '    if usuario_id:\n'
        '        query += " AND e.usuario_id = %s"; params.append(usuario_id)\n'
        '    if computadora:\n'
        '        query += " AND e.computadora = %s"; params.append(computadora)\n'
        '    if tipo:\n'
        '        query += " AND e.tipo = %s"; params.append(tipo)\n'
        '    query += " ORDER BY e.fecha_hora DESC LIMIT %s"; params.append(limite)\n'
        '    cur.execute(query, params)\n'
        '    rows = [dict(r) for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return rows\n'
        '\n'
        '\n'
        'def listar_computadoras_monitoreo(empresa_id):\n'
        '    conn = get_connection()\n'
        '    cur = conn.cursor()\n'
        '    cur.execute(\n'
        '        "SELECT DISTINCT computadora FROM monitoreo_eventos WHERE empresa_id = %s AND computadora IS NOT NULL ORDER BY 1",\n'
        '        (empresa_id,),\n'
        '    )\n'
        '    nombres = [r["computadora"] for r in cur.fetchall()]\n'
        '    cur.close(); conn.close()\n'
        '    return nombres\n',
    ],
]

ARCHIVOS['backend/app.py'] = [
    [
        'from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request\n',
        'from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, Header\n',
    ],
    [
        '@app.post("/api/monitoreo/aceptar")\ndef api_aceptar_monitoreo(request: Request, usuario: dict = Depends(requiere_empresa_o_master)):\n    """El usuario acepta el aviso de monitoreo — queda registrado con\n    fecha/hora e IP como prueba. Se puede llamar sin que el monitoreo\n    esté activo (no pasa nada raro), aunque normalmente solo se llama\n    desde la pantalla de aviso que solo sale si sí está activo."""\n    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else None)\n    db.registrar_aceptacion_monitoreo(usuario["id"], ip)\n    return {"ok": True}\n\n\n',
        '@app.post("/api/monitoreo/aceptar")\ndef api_aceptar_monitoreo(request: Request, usuario: dict = Depends(requiere_empresa_o_master)):\n    """El usuario acepta el aviso de monitoreo — queda registrado con\n    fecha/hora e IP como prueba. Se puede llamar sin que el monitoreo\n    esté activo (no pasa nada raro), aunque normalmente solo se llama\n    desde la pantalla de aviso que solo sale si sí está activo."""\n    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else None)\n    db.registrar_aceptacion_monitoreo(usuario["id"], ip)\n    return {"ok": True}\n\n\n@app.post("/api/monitoreo/usuarios/{usuario_id}/token")\ndef api_generar_token_monitoreo(usuario_id: int, admin: dict = Depends(requiere_admin)):\n    """Genera un token nuevo (invalida el anterior si había uno) para\n    que el agente de Windows de esa persona se identifique. Se muestra\n    UNA sola vez en el frontend — cópialo al agente en ese momento."""\n    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)\n    if not objetivo:\n        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")\n    token = db.generar_token_monitoreo(usuario_id)\n    return {"token": token}\n\n\ndef requiere_token_monitoreo(x_monitoreo_token: str = Header(None)) -> dict:\n    """Autenticación propia del agente de Windows — no usa sesión de\n    usuario normal (JWT), usa el token generado desde Administrar."""\n    if not x_monitoreo_token:\n        raise HTTPException(status_code=401, detail="Falta el token de monitoreo (header X-Monitoreo-Token)")\n    datos = db.obtener_usuario_por_token_monitoreo(x_monitoreo_token)\n    if not datos:\n        raise HTTPException(status_code=401, detail="Token de monitoreo inválido")\n    if not datos.get("monitoreo_activo"):\n        raise HTTPException(status_code=403, detail="El monitoreo está desactivado para este usuario")\n    return datos\n\n\nclass EventoMonitoreo(BaseModel):\n    tipo: str\n    detalle: str\n    fecha_hora: Optional[str] = None\n\n\nclass LoteEventosMonitoreo(BaseModel):\n    computadora: str\n    eventos: List[EventoMonitoreo]\n\n\n@app.post("/api/monitoreo/eventos")\ndef api_registrar_eventos_monitoreo(payload: LoteEventosMonitoreo, datos: dict = Depends(requiere_token_monitoreo)):\n    """El agente de Windows llama esto para subir eventos en lote —\n    autenticado con su token propio, no con sesión de usuario."""\n    db.registrar_eventos_monitoreo(datos["id"], datos["empresa_id"], payload.computadora,\n                                    [e.dict() for e in payload.eventos])\n    return {"ok": True, "recibidos": len(payload.eventos)}\n\n\n@app.get("/api/monitoreo/eventos")\ndef api_listar_eventos_monitoreo(usuario_id: Optional[int] = None, computadora: Optional[str] = None,\n                                  tipo: Optional[str] = None, admin: dict = Depends(requiere_admin)):\n    """Base para la bitácora (Fase 3 — la pantalla en el frontend viene\n    después). Por ahora ya se puede consultar directo por la URL."""\n    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo)\n\n\n',
    ],
]

ARCHIVOS['frontend/index.html'] = [
    [
        '            <td class="col-check" title="${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'Acept\u00f3 el aviso\' : \'Activo, esperando que acepte el aviso\') : \'\'}">\n'
        '              <input type="checkbox" ${u.monitoreo_activo ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'monitoreo_activo\', this)" />\n'
        '              ${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'<div style="font-size:9px; color:var(--trace);">acept\u00f3</div>\' : \'<div style="font-size:9px; color:var(--copper);">pendiente</div>\') : \'\'}\n'
        '            </td>\n'
        '          </tr>',

        '            <td class="col-check" title="${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'Acept\u00f3 el aviso\' : \'Activo, esperando que acepte el aviso\') : \'\'}">\n'
        '              <input type="checkbox" ${u.monitoreo_activo ? \'checked\' : \'\'} onchange="cambiarAccesoModuloUI(${u.id}, \'monitoreo_activo\', this)" />\n'
        '              ${u.monitoreo_activo ? (u.monitoreo_aceptado_en ? \'<div style="font-size:9px; color:var(--trace);">acept\u00f3</div>\' : \'<div style="font-size:9px; color:var(--copper);">pendiente</div>\') : \'\'}\n'
        '              ${u.monitoreo_activo ? `<button type="button" style="font-size:9px; padding:2px 4px; margin-top:2px;" onclick="generarTokenMonitoreoUI(${u.id}, ${JSON.stringify(u.nombre_completo)})">token</button>` : \'\'}\n'
        '            </td>\n'
        '          </tr>',
    ],
    [
        'async function cambiarAccesoModuloUI(usuarioId, campo, checkbox) {',

        'async function generarTokenMonitoreoUI(usuarioId, nombre) {\n'
        '  if (!confirm(`\u00bfGenerar un token nuevo de monitoreo para ${nombre}? Si ya ten\u00eda uno, deja de funcionar.`)) return;\n'
        '  try {\n'
        "    const r = await api(`/api/monitoreo/usuarios/${usuarioId}/token`, { method: 'POST' });\n"
        '    prompt(`Token para el agente de Windows de ${nombre} (c\u00f3pialo ahora, no se vuelve a mostrar):`, r.token);\n'
        '  } catch (e) {\n'
        '    alert(e.message);\n'
        '  }\n'
        '}\n'
        '\n'
        'async function cambiarAccesoModuloUI(usuarioId, campo, checkbox) {',
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False
    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] NO ENCONTRADO -- aseg\u00farate de correr este script desde la ra\u00edz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1
            else:
                print(f"[{ruta}] No se encontr\u00f3 un bloque esperado. El archivo pudo haber cambiado desde la \u00faltima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/db.py backend/app.py frontend/index.html")
    print('   git commit -m "Monitoreo Fase 2 (backend): tokens y eventos del agente"')
    print("   git push")


if __name__ == "__main__":
    main()
