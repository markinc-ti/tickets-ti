# -*- coding: utf-8 -*-
"""Sesiones de Escritorio remoto del servidor de Microsip: verlas y cerrarlas desde la app Mark·Inc.
- Nuevo backend/sesiones_remotas.py (tablas sesiones_equipos y sesiones_ordenes, se crean solas).
- backend/app.py: incluye el router y crea las tablas al arrancar.
En el servidor de Microsip corre sesiones_agente.ps1 (lo manda la lista y cierra las que pidas).
No se guarda ningun usuario ni contrasena de Windows: solo un token por servidor (guardado como hash).
Correr en la carpeta tickets-ti:  py -3 fix_sesiones_remotas.py
"""
import os, sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "import tienda\nimport facturacion_flete\n",
   "import tienda\nimport sesiones_remotas\nimport facturacion_flete\n"
  ],
  [
   "app.include_router(tienda.router)\n\n",
   "app.include_router(tienda.router)\n# Sesiones de Escritorio remoto del servidor de Microsip (backend/sesiones_remotas.py).\napp.include_router(sesiones_remotas.router)\n\n"
  ],
  [
   "        tienda.crear_tablas()\n    except Exception as e:\n        print(f\"[tienda] no se pudieron crear las tablas: {e}\")\n\n\n@app.get(\"/tienda/pago-listo\", response_class=HTMLResponse)\n",
   "        tienda.crear_tablas()\n    except Exception as e:\n        print(f\"[tienda] no se pudieron crear las tablas: {e}\")\n\n\n@app.on_event(\"startup\")\ndef _tablas_sesiones_remotas():\n    try:\n        sesiones_remotas.crear_tablas()\n    except Exception as e:\n        print(f\"[sesiones_remotas] no se pudieron crear las tablas: {e}\")\n\n\n@app.get(\"/tienda/pago-listo\", response_class=HTMLResponse)\n"
  ]
 ]
}

NUEVOS = {
 "backend/sesiones_remotas.py": "# -*- coding: utf-8 -*-\n\"\"\"Sesiones de Escritorio remoto del servidor de Microsip: verlas y cerrarlas desde la app.\n\nCómo funciona (sin guardar el usuario ni la contraseña del servidor en ningún lado):\n  1. En el servidor corre `sesiones_agente.ps1` (Programador de tareas, como SYSTEM). Cada pocos\n     segundos lee las sesiones abiertas (`quser`) y las manda aquí con su token de equipo.\n  2. El administrador ve la lista en la app (usuario, estado, inactiva desde, inicio) y toca\n     \"Cerrar sesión\": queda una orden pendiente.\n  3. El agente, en su siguiente vuelta (segundos), recibe la orden, corre `logoff <id>` y avisa\n     el resultado.\n\nTablas: sesiones_equipos (un renglón por servidor; token guardado solo como hash) y\nsesiones_ordenes (historial de cierres: quién lo pidió, a quién, cuándo y si se pudo).\"\"\"\nimport hashlib\nimport json\nimport secrets\nfrom datetime import datetime, timezone\nfrom typing import List, Optional\n\nfrom fastapi import APIRouter, Depends, Header, HTTPException\nfrom pydantic import BaseModel, Field\n\nimport auth\nimport db\n\nrouter = APIRouter()\n\n# Si el agente no reporta en este tiempo, la app avisa que el servidor está desconectado.\nSEGUNDOS_SIN_REPORTE = 120\n\n\ndef _q(sql, params=(), uno=False, todos=True, commit=False):\n    conn = db.get_connection()\n    cur = conn.cursor()\n    try:\n        cur.execute(sql, params)\n        r = None\n        if uno:\n            f = cur.fetchone()\n            r = dict(f) if f else None\n        elif todos and cur.description:\n            r = [dict(x) for x in cur.fetchall()]\n        if commit:\n            conn.commit()\n        return r\n    finally:\n        cur.close()\n        conn.close()\n\n\ndef crear_tablas():\n    conn = db.get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        CREATE TABLE IF NOT EXISTS sesiones_equipos (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            nombre TEXT NOT NULL,\n            token_hash TEXT NOT NULL UNIQUE,\n            sesiones_json TEXT,\n            ultimo_reporte TIMESTAMPTZ,\n            nombre_equipo TEXT,\n            activo BOOLEAN NOT NULL DEFAULT TRUE,\n            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()\n        );\n        CREATE TABLE IF NOT EXISTS sesiones_ordenes (\n            id SERIAL PRIMARY KEY,\n            empresa_id INTEGER NOT NULL REFERENCES empresas(id),\n            equipo_id INTEGER NOT NULL REFERENCES sesiones_equipos(id) ON DELETE CASCADE,\n            sesion_id INTEGER NOT NULL,\n            usuario_windows TEXT,\n            pedida_por INTEGER,\n            pedida_por_nombre TEXT,\n            estado TEXT NOT NULL DEFAULT 'pendiente',\n            resultado TEXT,\n            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n            hecha_en TIMESTAMPTZ\n        );\n        CREATE INDEX IF NOT EXISTS idx_sesiones_ordenes_eq ON sesiones_ordenes (equipo_id, estado);\n    \"\"\")\n    conn.commit()\n    cur.close()\n    conn.close()\n\n\ndef _hash(token):\n    return hashlib.sha256(token.encode(\"utf-8\")).hexdigest()\n\n\ndef requiere_admin(usuario: dict = Depends(auth.get_current_user)) -> dict:\n    if usuario.get(\"rol\") != \"admin\" or not usuario.get(\"empresa_id\"):\n        raise HTTPException(status_code=403, detail=\"Solo el administrador puede ver y cerrar sesiones del servidor.\")\n    return usuario\n\n\ndef _equipo_por_token(token):\n    if not token:\n        raise HTTPException(status_code=401, detail=\"Falta el token del equipo\")\n    e = _q(\"SELECT * FROM sesiones_equipos WHERE token_hash = %s AND activo\", (_hash(token.strip()),), uno=True)\n    if not e:\n        raise HTTPException(status_code=401, detail=\"Token de equipo no válido\")\n    return e\n\n\ndef _iso(v):\n    return v.isoformat() if hasattr(v, \"isoformat\") else v\n\n\ndef _vista_equipo(e, ordenes):\n    ahora = datetime.now(timezone.utc)\n    ultimo = e.get(\"ultimo_reporte\")\n    conectado = bool(ultimo and (ahora - ultimo).total_seconds() <= SEGUNDOS_SIN_REPORTE)\n    try:\n        sesiones = json.loads(e.get(\"sesiones_json\") or \"[]\")\n    except ValueError:\n        sesiones = []\n    pendientes = {o[\"sesion_id\"] for o in ordenes if o[\"equipo_id\"] == e[\"id\"] and o[\"estado\"] in (\"pendiente\", \"enviada\")}\n    for s in sesiones:\n        s[\"cerrando\"] = s.get(\"id\") in pendientes\n    return {\"id\": e[\"id\"], \"nombre\": e[\"nombre\"], \"nombre_equipo\": e.get(\"nombre_equipo\"), \"conectado\": conectado,\n            \"ultimo_reporte\": _iso(ultimo), \"sesiones\": sesiones,\n            \"ordenes\": [{k: _iso(v) for k, v in o.items() if k != \"empresa_id\"} for o in ordenes if o[\"equipo_id\"] == e[\"id\"]][:15]}\n\n\n# ------------------------------------------------------------------ administrador (app)\n\nclass EquipoIn(BaseModel):\n    nombre: str = Field(min_length=1, max_length=80)\n\n\n@router.get(\"/api/sesiones-remotas\")\ndef api_sesiones(usuario: dict = Depends(requiere_admin)):\n    equipos = _q(\"SELECT * FROM sesiones_equipos WHERE empresa_id = %s AND activo ORDER BY nombre\", (usuario[\"empresa_id\"],))\n    ordenes = _q(\"\"\"SELECT * FROM sesiones_ordenes WHERE empresa_id = %s AND creado_en > NOW() - INTERVAL '3 days'\n                    ORDER BY creado_en DESC\"\"\", (usuario[\"empresa_id\"],))\n    return {\"equipos\": [_vista_equipo(e, ordenes) for e in equipos], \"segundos_sin_reporte\": SEGUNDOS_SIN_REPORTE}\n\n\n@router.post(\"/api/sesiones-remotas/equipos\")\ndef api_crear_equipo(payload: EquipoIn, usuario: dict = Depends(requiere_admin)):\n    \"\"\"Da de alta el servidor y regresa su token UNA sola vez (se pega en sesiones_agente.ps1).\"\"\"\n    token = \"srv_\" + secrets.token_urlsafe(32)\n    e = _q(\"INSERT INTO sesiones_equipos (empresa_id, nombre, token_hash) VALUES (%s, %s, %s) RETURNING id, nombre\",\n           (usuario[\"empresa_id\"], payload.nombre.strip(), _hash(token)), uno=True, commit=True)\n    return {**e, \"token\": token}\n\n\n@router.post(\"/api/sesiones-remotas/equipos/{equipo_id}/token\")\ndef api_nuevo_token(equipo_id: int, usuario: dict = Depends(requiere_admin)):\n    \"\"\"Token nuevo (el anterior deja de servir), por si se perdió o se filtró.\"\"\"\n    token = \"srv_\" + secrets.token_urlsafe(32)\n    e = _q(\"UPDATE sesiones_equipos SET token_hash = %s WHERE id = %s AND empresa_id = %s RETURNING id, nombre\",\n           (_hash(token), equipo_id, usuario[\"empresa_id\"]), uno=True, commit=True)\n    if not e:\n        raise HTTPException(status_code=404, detail=\"Servidor no encontrado\")\n    return {**e, \"token\": token}\n\n\n@router.delete(\"/api/sesiones-remotas/equipos/{equipo_id}\")\ndef api_borrar_equipo(equipo_id: int, usuario: dict = Depends(requiere_admin)):\n    _q(\"UPDATE sesiones_equipos SET activo = FALSE WHERE id = %s AND empresa_id = %s\",\n       (equipo_id, usuario[\"empresa_id\"]), todos=False, commit=True)\n    return {\"ok\": True}\n\n\nclass CerrarIn(BaseModel):\n    equipo_id: int\n    sesion_id: int\n    usuario_windows: Optional[str] = Field(default=None, max_length=120)\n\n\n@router.post(\"/api/sesiones-remotas/cerrar\")\ndef api_cerrar(payload: CerrarIn, usuario: dict = Depends(requiere_admin)):\n    e = _q(\"SELECT * FROM sesiones_equipos WHERE id = %s AND empresa_id = %s AND activo\",\n           (payload.equipo_id, usuario[\"empresa_id\"]), uno=True)\n    if not e:\n        raise HTTPException(status_code=404, detail=\"Servidor no encontrado\")\n    ya = _q(\"\"\"SELECT id FROM sesiones_ordenes WHERE equipo_id = %s AND sesion_id = %s AND estado IN ('pendiente', 'enviada')\n               AND creado_en > NOW() - INTERVAL '10 minutes'\"\"\", (e[\"id\"], payload.sesion_id), uno=True)\n    if ya:\n        return {\"ok\": True, \"orden_id\": ya[\"id\"], \"ya_estaba\": True}\n    o = _q(\"\"\"INSERT INTO sesiones_ordenes (empresa_id, equipo_id, sesion_id, usuario_windows, pedida_por, pedida_por_nombre)\n              VALUES (%s, %s, %s, %s, %s, %s) RETURNING id\"\"\",\n           (usuario[\"empresa_id\"], e[\"id\"], payload.sesion_id, payload.usuario_windows, usuario.get(\"id\"),\n            usuario.get(\"nombre\") or usuario.get(\"username\")), uno=True, commit=True)\n    return {\"ok\": True, \"orden_id\": o[\"id\"]}\n\n\n# ------------------------------------------------------------------ agente (servidor)\n\nclass SesionIn(BaseModel):\n    id: int\n    usuario: Optional[str] = Field(default=None, max_length=120)\n    nombre_sesion: Optional[str] = Field(default=None, max_length=120)\n    estado: Optional[str] = Field(default=None, max_length=40)\n    inactiva: Optional[str] = Field(default=None, max_length=40)\n    inicio: Optional[str] = Field(default=None, max_length=60)\n\n\nclass ReporteIn(BaseModel):\n    equipo: Optional[str] = Field(default=None, max_length=120)\n    sesiones: List[SesionIn] = []\n\n\n@router.post(\"/api/sesiones-remotas/agente/reporte\")\ndef api_agente_reporte(payload: ReporteIn, x_token_sesiones: str = Header(None)):\n    \"\"\"El agente manda las sesiones abiertas y recibe las órdenes de cierre pendientes.\"\"\"\n    e = _equipo_por_token(x_token_sesiones)\n    _q(\"UPDATE sesiones_equipos SET sesiones_json = %s, ultimo_reporte = NOW(), nombre_equipo = %s WHERE id = %s\",\n       (json.dumps([s.dict() for s in payload.sesiones], ensure_ascii=False), payload.equipo, e[\"id\"]), todos=False, commit=True)\n    # Una orden que se mandó y nunca respondió en 5 min vuelve a intentarse.\n    _q(\"\"\"UPDATE sesiones_ordenes SET estado = 'pendiente' WHERE equipo_id = %s AND estado = 'enviada'\n          AND creado_en < NOW() - INTERVAL '5 minutes' AND creado_en > NOW() - INTERVAL '30 minutes'\"\"\",\n       (e[\"id\"],), todos=False, commit=True)\n    # Las de hace más de 30 min ya no se ejecutan (la sesión pudo ser de otra persona para entonces).\n    _q(\"\"\"UPDATE sesiones_ordenes SET estado = 'caducada', hecha_en = NOW(), resultado = 'El servidor no la recibió a tiempo'\n          WHERE equipo_id = %s AND estado IN ('pendiente', 'enviada') AND creado_en < NOW() - INTERVAL '30 minutes'\"\"\",\n       (e[\"id\"],), todos=False, commit=True)\n    ordenes = _q(\"\"\"UPDATE sesiones_ordenes SET estado = 'enviada' WHERE equipo_id = %s AND estado = 'pendiente'\n                    RETURNING id, sesion_id, usuario_windows\"\"\", (e[\"id\"],), commit=True) or []\n    return {\"ordenes\": ordenes}\n\n\nclass ResultadoIn(BaseModel):\n    orden_id: int\n    ok: bool\n    mensaje: Optional[str] = Field(default=None, max_length=500)\n\n\n@router.post(\"/api/sesiones-remotas/agente/resultado\")\ndef api_agente_resultado(payload: ResultadoIn, x_token_sesiones: str = Header(None)):\n    e = _equipo_por_token(x_token_sesiones)\n    _q(\"UPDATE sesiones_ordenes SET estado = %s, resultado = %s, hecha_en = NOW() WHERE id = %s AND equipo_id = %s\",\n       (\"hecha\" if payload.ok else \"error\", payload.mensaje, payload.orden_id, e[\"id\"]), todos=False, commit=True)\n    return {\"ok\": True}\n"
}


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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_sesiones_remotas.py")
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
