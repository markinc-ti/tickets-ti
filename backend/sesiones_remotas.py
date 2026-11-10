# -*- coding: utf-8 -*-
"""Sesiones de Escritorio remoto del servidor de Microsip: verlas y cerrarlas desde la app.

Cómo funciona (sin guardar el usuario ni la contraseña del servidor en ningún lado):
  1. En el servidor corre `sesiones_agente.ps1` (Programador de tareas, como SYSTEM). Cada pocos
     segundos lee las sesiones abiertas (`quser`) y las manda aquí con su token de equipo.
  2. El administrador ve la lista en la app (usuario, estado, inactiva desde, inicio) y toca
     "Cerrar sesión": queda una orden pendiente.
  3. El agente, en su siguiente vuelta (segundos), recibe la orden, corre `logoff <id>` y avisa
     el resultado.

Tablas: sesiones_equipos (un renglón por servidor; token guardado solo como hash) y
sesiones_ordenes (historial de cierres: quién lo pidió, a quién, cuándo y si se pudo)."""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

import auth
import db

router = APIRouter()

# Si el agente no reporta en este tiempo, la app avisa que el servidor está desconectado.
SEGUNDOS_SIN_REPORTE = 120


def _q(sql, params=(), uno=False, todos=True, commit=False):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        r = None
        if uno:
            f = cur.fetchone()
            r = dict(f) if f else None
        elif todos and cur.description:
            r = [dict(x) for x in cur.fetchall()]
        if commit:
            conn.commit()
        return r
    finally:
        cur.close()
        conn.close()


def crear_tablas():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_equipos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            sesiones_json TEXT,
            ultimo_reporte TIMESTAMPTZ,
            nombre_equipo TEXT,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS sesiones_ordenes (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            equipo_id INTEGER NOT NULL REFERENCES sesiones_equipos(id) ON DELETE CASCADE,
            sesion_id INTEGER NOT NULL,
            usuario_windows TEXT,
            pedida_por INTEGER,
            pedida_por_nombre TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            resultado TEXT,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            hecha_en TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_sesiones_ordenes_eq ON sesiones_ordenes (equipo_id, estado);
    """)
    conn.commit()
    cur.close()
    conn.close()


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def requiere_admin(usuario: dict = Depends(auth.get_current_user)) -> dict:
    if usuario.get("rol") != "admin" or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Solo el administrador puede ver y cerrar sesiones del servidor.")
    return usuario


def _equipo_por_token(token):
    if not token:
        raise HTTPException(status_code=401, detail="Falta el token del equipo")
    e = _q("SELECT * FROM sesiones_equipos WHERE token_hash = %s AND activo", (_hash(token.strip()),), uno=True)
    if not e:
        raise HTTPException(status_code=401, detail="Token de equipo no válido")
    return e


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _vista_equipo(e, ordenes):
    ahora = datetime.now(timezone.utc)
    ultimo = e.get("ultimo_reporte")
    conectado = bool(ultimo and (ahora - ultimo).total_seconds() <= SEGUNDOS_SIN_REPORTE)
    try:
        sesiones = json.loads(e.get("sesiones_json") or "[]")
    except ValueError:
        sesiones = []
    pendientes = {o["sesion_id"] for o in ordenes if o["equipo_id"] == e["id"] and o["estado"] in ("pendiente", "enviada")}
    for s in sesiones:
        s["cerrando"] = s.get("id") in pendientes
    return {"id": e["id"], "nombre": e["nombre"], "nombre_equipo": e.get("nombre_equipo"), "conectado": conectado,
            "ultimo_reporte": _iso(ultimo), "sesiones": sesiones,
            "ordenes": [{k: _iso(v) for k, v in o.items() if k != "empresa_id"} for o in ordenes if o["equipo_id"] == e["id"]][:15]}


# ------------------------------------------------------------------ administrador (app)

class EquipoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


@router.get("/api/sesiones-remotas")
def api_sesiones(usuario: dict = Depends(requiere_admin)):
    equipos = _q("SELECT * FROM sesiones_equipos WHERE empresa_id = %s AND activo ORDER BY nombre", (usuario["empresa_id"],))
    ordenes = _q("""SELECT * FROM sesiones_ordenes WHERE empresa_id = %s AND creado_en > NOW() - INTERVAL '3 days'
                    ORDER BY creado_en DESC""", (usuario["empresa_id"],))
    return {"equipos": [_vista_equipo(e, ordenes) for e in equipos], "segundos_sin_reporte": SEGUNDOS_SIN_REPORTE}


@router.post("/api/sesiones-remotas/equipos")
def api_crear_equipo(payload: EquipoIn, usuario: dict = Depends(requiere_admin)):
    """Da de alta el servidor y regresa su token UNA sola vez (se pega en sesiones_agente.ps1)."""
    token = "srv_" + secrets.token_urlsafe(32)
    e = _q("INSERT INTO sesiones_equipos (empresa_id, nombre, token_hash) VALUES (%s, %s, %s) RETURNING id, nombre",
           (usuario["empresa_id"], payload.nombre.strip(), _hash(token)), uno=True, commit=True)
    return {**e, "token": token}


@router.post("/api/sesiones-remotas/equipos/{equipo_id}/token")
def api_nuevo_token(equipo_id: int, usuario: dict = Depends(requiere_admin)):
    """Token nuevo (el anterior deja de servir), por si se perdió o se filtró."""
    token = "srv_" + secrets.token_urlsafe(32)
    e = _q("UPDATE sesiones_equipos SET token_hash = %s WHERE id = %s AND empresa_id = %s RETURNING id, nombre",
           (_hash(token), equipo_id, usuario["empresa_id"]), uno=True, commit=True)
    if not e:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")
    return {**e, "token": token}


@router.delete("/api/sesiones-remotas/equipos/{equipo_id}")
def api_borrar_equipo(equipo_id: int, usuario: dict = Depends(requiere_admin)):
    _q("UPDATE sesiones_equipos SET activo = FALSE WHERE id = %s AND empresa_id = %s",
       (equipo_id, usuario["empresa_id"]), todos=False, commit=True)
    return {"ok": True}


class CerrarIn(BaseModel):
    equipo_id: int
    sesion_id: int
    usuario_windows: Optional[str] = Field(default=None, max_length=120)


@router.post("/api/sesiones-remotas/cerrar")
def api_cerrar(payload: CerrarIn, usuario: dict = Depends(requiere_admin)):
    e = _q("SELECT * FROM sesiones_equipos WHERE id = %s AND empresa_id = %s AND activo",
           (payload.equipo_id, usuario["empresa_id"]), uno=True)
    if not e:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")
    ya = _q("""SELECT id FROM sesiones_ordenes WHERE equipo_id = %s AND sesion_id = %s AND estado IN ('pendiente', 'enviada')
               AND creado_en > NOW() - INTERVAL '10 minutes'""", (e["id"], payload.sesion_id), uno=True)
    if ya:
        return {"ok": True, "orden_id": ya["id"], "ya_estaba": True}
    o = _q("""INSERT INTO sesiones_ordenes (empresa_id, equipo_id, sesion_id, usuario_windows, pedida_por, pedida_por_nombre)
              VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
           (usuario["empresa_id"], e["id"], payload.sesion_id, payload.usuario_windows, usuario.get("id"),
            usuario.get("nombre") or usuario.get("username")), uno=True, commit=True)
    return {"ok": True, "orden_id": o["id"]}


# ------------------------------------------------------------------ agente (servidor)

class SesionIn(BaseModel):
    id: int
    usuario: Optional[str] = Field(default=None, max_length=120)
    nombre_sesion: Optional[str] = Field(default=None, max_length=120)
    estado: Optional[str] = Field(default=None, max_length=40)
    inactiva: Optional[str] = Field(default=None, max_length=40)
    inicio: Optional[str] = Field(default=None, max_length=60)


class ReporteIn(BaseModel):
    equipo: Optional[str] = Field(default=None, max_length=120)
    sesiones: List[SesionIn] = []


@router.post("/api/sesiones-remotas/agente/reporte")
def api_agente_reporte(payload: ReporteIn, x_token_sesiones: str = Header(None)):
    """El agente manda las sesiones abiertas y recibe las órdenes de cierre pendientes."""
    e = _equipo_por_token(x_token_sesiones)
    _q("UPDATE sesiones_equipos SET sesiones_json = %s, ultimo_reporte = NOW(), nombre_equipo = %s WHERE id = %s",
       (json.dumps([s.dict() for s in payload.sesiones], ensure_ascii=False), payload.equipo, e["id"]), todos=False, commit=True)
    # Una orden que se mandó y nunca respondió en 5 min vuelve a intentarse.
    _q("""UPDATE sesiones_ordenes SET estado = 'pendiente' WHERE equipo_id = %s AND estado = 'enviada'
          AND creado_en < NOW() - INTERVAL '5 minutes' AND creado_en > NOW() - INTERVAL '30 minutes'""",
       (e["id"],), todos=False, commit=True)
    # Las de hace más de 30 min ya no se ejecutan (la sesión pudo ser de otra persona para entonces).
    _q("""UPDATE sesiones_ordenes SET estado = 'caducada', hecha_en = NOW(), resultado = 'El servidor no la recibió a tiempo'
          WHERE equipo_id = %s AND estado IN ('pendiente', 'enviada') AND creado_en < NOW() - INTERVAL '30 minutes'""",
       (e["id"],), todos=False, commit=True)
    ordenes = _q("""UPDATE sesiones_ordenes SET estado = 'enviada' WHERE equipo_id = %s AND estado = 'pendiente'
                    RETURNING id, sesion_id, usuario_windows""", (e["id"],), commit=True) or []
    return {"ordenes": ordenes}


class ResultadoIn(BaseModel):
    orden_id: int
    ok: bool
    mensaje: Optional[str] = Field(default=None, max_length=500)


@router.post("/api/sesiones-remotas/agente/resultado")
def api_agente_resultado(payload: ResultadoIn, x_token_sesiones: str = Header(None)):
    e = _equipo_por_token(x_token_sesiones)
    _q("UPDATE sesiones_ordenes SET estado = %s, resultado = %s, hecha_en = NOW() WHERE id = %s AND equipo_id = %s",
       ("hecha" if payload.ok else "error", payload.mensaje, payload.orden_id, e["id"]), todos=False, commit=True)
    return {"ok": True}
