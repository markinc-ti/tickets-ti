"""
Unidental: tienda de unidades dentales (y equipo) de varias marcas para doctores.

Es una empresa más de tickets-ti (multiempresa). La empresa que tiene tienda
guarda su configuración en `tienda_config` con un `codigo` (ej. "unidental")
que usa la app para saber de qué tienda es.

- Público (sin sesión): catálogo, ficha del producto, fotos y feed de videos.
- Doctor (rol 'doctor', se registra solo; el registro es obligatorio para
  comprar): carrito, pedidos con seguimiento, comprobantes de pago, perfil y
  borrar su cuenta (Apple/Google lo exigen).
- Administrador de esa empresa: marcas, productos (precios, características,
  fotos, videos), pedidos (estado → aviso al doctor), pagos y configuración.

Pago: 'asesor' (transferencia/financiamiento con comprobante), 'linea' (todo en
línea) o 'anticipo' (un % en línea y el resto con asesor). En línea usa
Mercado Pago Checkout Pro cuando la tienda tiene su access token (o la
variable MP_ACCESS_TOKEN); si no, esas opciones no se ofrecen.
"""
import base64
import json
import os
import re
import secrets
from decimal import Decimal
from typing import List, Literal, Optional

import psycopg2.extras
import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

import auth
import avisos
import db
import r2

router = APIRouter()

ESTADOS_PEDIDO = ["recibido", "confirmado", "pagado", "en_fabricacion", "en_camino", "instalado", "entregado", "cancelado"]
NOMBRE_ESTADO = {
    "recibido": "Pedido recibido", "confirmado": "Confirmado por un asesor", "pagado": "Pago completo",
    "en_fabricacion": "En preparación", "en_camino": "En camino", "instalado": "Instalado",
    "entregado": "Entregado", "cancelado": "Cancelado",
    # Eventos que no son estado (salen en la línea de tiempo):
    "comprobante": "Comprobante enviado", "pago": "Pago registrado", "pago_rechazado": "Pago no confirmado",
}
MAX_FOTO = 4_000_000          # bytes de la foto ya reducida en el celular
MAX_COMPROBANTE = 6_000_000


# ------------------------------------------------------------------ tablas

def crear_tablas():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tienda_config (
            empresa_id INTEGER PRIMARY KEY REFERENCES empresas(id),
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'Unidental',
            activa BOOLEAN NOT NULL DEFAULT TRUE,
            pago_asesor BOOLEAN NOT NULL DEFAULT TRUE,
            pago_linea BOOLEAN NOT NULL DEFAULT TRUE,
            pago_anticipo BOOLEAN NOT NULL DEFAULT TRUE,
            anticipo_pct NUMERIC(5,2) NOT NULL DEFAULT 20,
            datos_pago TEXT,
            whatsapp TEXT,
            mp_access_token TEXT,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_marcas (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            nombre TEXT NOT NULL,
            descripcion TEXT,
            logo_foto_id INTEGER,
            orden INTEGER NOT NULL DEFAULT 0,
            activa BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS tienda_productos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            marca_id INTEGER REFERENCES tienda_marcas(id),
            nombre TEXT NOT NULL,
            modelo TEXT,
            categoria TEXT NOT NULL DEFAULT 'Unidades dentales',
            descripcion TEXT,
            caracteristicas JSONB NOT NULL DEFAULT '[]',
            precio NUMERIC(14,2) NOT NULL DEFAULT 0,
            precio_anterior NUMERIC(14,2),
            meses_sin_intereses INTEGER,
            entrega TEXT,
            garantia TEXT,
            destacado BOOLEAN NOT NULL DEFAULT FALSE,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            orden INTEGER NOT NULL DEFAULT 0,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_fotos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            producto_id INTEGER REFERENCES tienda_productos(id) ON DELETE CASCADE,
            datos BYTEA NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'image/jpeg',
            orden INTEGER NOT NULL DEFAULT 0,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_videos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            producto_id INTEGER REFERENCES tienda_productos(id) ON DELETE CASCADE,
            titulo TEXT,
            url TEXT NOT NULL,
            r2_key TEXT,
            en_feed BOOLEAN NOT NULL DEFAULT TRUE,
            orden INTEGER NOT NULL DEFAULT 0,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_doctores (
            usuario_id INTEGER PRIMARY KEY REFERENCES users(id),
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            consultorio TEXT,
            especialidad TEXT,
            ciudad TEXT,
            estado TEXT,
            direccion TEXT,
            rfc TEXT,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_carrito (
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            producto_id INTEGER NOT NULL REFERENCES tienda_productos(id) ON DELETE CASCADE,
            cantidad INTEGER NOT NULL DEFAULT 1,
            agregado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (usuario_id, producto_id)
        );
        CREATE TABLE IF NOT EXISTS tienda_pedidos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            folio TEXT NOT NULL,
            usuario_id INTEGER NOT NULL REFERENCES users(id),
            estado TEXT NOT NULL DEFAULT 'recibido',
            forma_pago TEXT NOT NULL DEFAULT 'asesor',
            total NUMERIC(14,2) NOT NULL DEFAULT 0,
            anticipo NUMERIC(14,2) NOT NULL DEFAULT 0,
            pagado NUMERIC(14,2) NOT NULL DEFAULT 0,
            notas TEXT,
            direccion_entrega TEXT,
            mp_preferencia TEXT,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_pedido_items (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES tienda_pedidos(id) ON DELETE CASCADE,
            producto_id INTEGER REFERENCES tienda_productos(id) ON DELETE SET NULL,
            nombre TEXT NOT NULL,
            modelo TEXT,
            marca TEXT,
            foto_id INTEGER,
            precio NUMERIC(14,2) NOT NULL,
            cantidad INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tienda_pedido_eventos (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES tienda_pedidos(id) ON DELETE CASCADE,
            estado TEXT NOT NULL,
            nota TEXT,
            usuario_id INTEGER,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tienda_pagos (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES tienda_pedidos(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL,
            monto NUMERIC(14,2) NOT NULL DEFAULT 0,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            comprobante BYTEA,
            comprobante_tipo TEXT,
            referencia TEXT,
            nota TEXT,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revisado_en TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_tienda_productos_emp ON tienda_productos (empresa_id, activo);
        CREATE INDEX IF NOT EXISTS idx_tienda_pedidos_usr ON tienda_pedidos (usuario_id);
        CREATE INDEX IF NOT EXISTS idx_tienda_pedidos_emp ON tienda_pedidos (empresa_id, creado_en DESC);
    """)
    conn.commit()
    cur.close(); conn.close()


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
        cur.close(); conn.close()


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _limpio(d):
    return {k: _num(v) for k, v in d.items()}


# ------------------------------------------------------------------ tienda / permisos

def tienda_por_codigo(codigo):
    t = _q("SELECT * FROM tienda_config WHERE codigo = %s AND activa", (codigo.strip().lower(),), uno=True)
    if not t:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    return t


def _mp_token(t):
    return (t.get("mp_access_token") or os.environ.get("MP_ACCESS_TOKEN") or "").strip()


def _publica(t):
    linea = bool(_mp_token(t))
    return {
        "codigo": t["codigo"], "nombre": t["nombre"], "whatsapp": t.get("whatsapp"), "datos_pago": t.get("datos_pago"),
        "formas_pago": [f for f, ok in (("asesor", t["pago_asesor"]), ("linea", t["pago_linea"] and linea),
                                         ("anticipo", t["pago_anticipo"] and linea)) if ok],
        "anticipo_pct": _num(t["anticipo_pct"]),
    }


def requiere_doctor(usuario: dict = Depends(auth.get_current_user)) -> dict:
    if usuario.get("rol") != "doctor":
        raise HTTPException(status_code=403, detail="Inicia sesión con tu cuenta de doctor.")
    return usuario


def requiere_admin_tienda(usuario: dict = Depends(auth.get_current_user)) -> dict:
    if usuario.get("rol") != "admin" or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Solo el administrador de la tienda.")
    t = _q("SELECT * FROM tienda_config WHERE empresa_id = %s", (usuario["empresa_id"],), uno=True)
    if not t:
        raise HTTPException(status_code=403, detail="Esta empresa no tiene tienda. Actívala primero (configuración de la tienda).")
    usuario = dict(usuario)
    usuario["tienda"] = t
    return usuario


def _token_respuesta(u):
    return {"token": auth.crear_token(u), "usuario": {"id": u["id"], "username": u["username"], "nombre": u["nombre_completo"],
                                                     "rol": u["rol"], "empresa_id": u["empresa_id"]}}


# ------------------------------------------------------------------ catálogo público

def _productos(empresa_id, solo_activos=True, ids=None):
    cond = ["p.empresa_id = %s"]
    params = [empresa_id]
    if solo_activos:
        cond.append("p.activo")
    if ids is not None:
        cond.append("p.id = ANY(%s)"); params.append(list(ids))
    filas = _q(f"""
        SELECT p.*, m.nombre AS marca,
               (SELECT f.id FROM tienda_fotos f WHERE f.producto_id = p.id ORDER BY f.orden, f.id LIMIT 1) AS foto_id,
               (SELECT COUNT(*) FROM tienda_fotos f WHERE f.producto_id = p.id) AS fotos,
               (SELECT COUNT(*) FROM tienda_videos v WHERE v.producto_id = p.id) AS videos
        FROM tienda_productos p LEFT JOIN tienda_marcas m ON m.id = p.marca_id
        WHERE {' AND '.join(cond)}
        ORDER BY p.destacado DESC, p.orden, p.nombre""", params)
    return [_limpio(f) for f in filas]


@router.get("/api/tienda/{codigo}/catalogo")
def api_catalogo(codigo: str):
    t = tienda_por_codigo(codigo)
    productos = _productos(t["empresa_id"])
    marcas = _q("SELECT id, nombre, descripcion, logo_foto_id FROM tienda_marcas WHERE empresa_id = %s AND activa ORDER BY orden, nombre",
                (t["empresa_id"],))
    categorias = sorted({p["categoria"] for p in productos if p.get("categoria")})
    for p in productos:
        p.pop("descripcion", None)
    return {"tienda": _publica(t), "marcas": marcas, "categorias": categorias, "productos": productos}


def _detalle(empresa_id, producto_id, solo_activo=True):
    p = _productos(empresa_id, solo_activo, ids=[producto_id])
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    p = p[0]
    p["fotos"] = [f["id"] for f in _q("SELECT id FROM tienda_fotos WHERE producto_id = %s ORDER BY orden, id", (producto_id,))]
    p["videos"] = _q("SELECT id, titulo, url, en_feed FROM tienda_videos WHERE producto_id = %s ORDER BY orden, id", (producto_id,))
    return p


@router.get("/api/tienda/{codigo}/producto/{producto_id}")
def api_producto(codigo: str, producto_id: int):
    t = tienda_por_codigo(codigo)
    return _detalle(t["empresa_id"], producto_id)


@router.get("/api/tienda/{codigo}/videos")
def api_videos(codigo: str):
    """Feed de videos (estilo clips): cada video lleva su producto para ir a comprarlo."""
    t = tienda_por_codigo(codigo)
    return _q("""SELECT v.id, v.titulo, v.url, p.id AS producto_id, p.nombre, p.modelo, p.precio, m.nombre AS marca
                 FROM tienda_videos v JOIN tienda_productos p ON p.id = v.producto_id AND p.activo
                 LEFT JOIN tienda_marcas m ON m.id = p.marca_id
                 WHERE v.empresa_id = %s AND v.en_feed ORDER BY v.orden, v.id DESC""", (t["empresa_id"],))


@router.get("/api/tienda/foto/{foto_id}")
def api_foto(foto_id: int):
    f = _q("SELECT datos, tipo FROM tienda_fotos WHERE id = %s", (foto_id,), uno=True)
    if not f:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    return Response(content=bytes(f["datos"]), media_type=f["tipo"],
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


# ------------------------------------------------------------------ registro / sesión

class RegistroDoctorIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    email: str = Field(min_length=5, max_length=150)
    telefono: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=100)
    consultorio: Optional[str] = Field(default=None, max_length=150)
    especialidad: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=80)
    estado: Optional[str] = Field(default=None, max_length=60)


class LoginTiendaIn(BaseModel):
    email: str
    password: str


def _email_ok(e):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e))


@router.post("/api/tienda/{codigo}/registro")
def api_registro(codigo: str, payload: RegistroDoctorIn):
    t = tienda_por_codigo(codigo)
    email = payload.email.strip().lower()
    if not _email_ok(email):
        raise HTTPException(status_code=400, detail="El correo no es válido.")
    if db.obtener_usuario_por_username(email):
        raise HTTPException(status_code=409, detail="Ese correo ya tiene cuenta. Inicia sesión.")
    uid = db.crear_usuario(t["empresa_id"], email, payload.password, payload.nombre.strip(), "doctor",
                           telefono_whatsapp=payload.telefono.strip())
    _q("UPDATE users SET email = %s WHERE id = %s", (email, uid), todos=False, commit=True)
    _q("""INSERT INTO tienda_doctores (usuario_id, empresa_id, consultorio, especialidad, ciudad, estado)
          VALUES (%s, %s, %s, %s, %s, %s)""",
       (uid, t["empresa_id"], payload.consultorio, payload.especialidad, payload.ciudad, payload.estado), todos=False, commit=True)
    return _token_respuesta(db.obtener_usuario_por_username(email))


@router.post("/api/tienda/{codigo}/login")
def api_login(codigo: str, payload: LoginTiendaIn):
    """Entra el doctor (o el administrador de la tienda) — solo cuentas de ESTA tienda.
    Mientras la tienda no está activada, puede entrar un administrador para activarla."""
    t = _q("SELECT * FROM tienda_config WHERE codigo = %s", (codigo.strip().lower(),), uno=True)
    u = db.obtener_usuario_por_username(payload.email.strip().lower()) or db.obtener_usuario_por_username(payload.email.strip())
    if not u or not u.get("activo") or not auth.verificar_password(payload.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    if t is None:
        if u["rol"] == "admin" and u.get("empresa_id"):
            return _token_respuesta(u)
        raise HTTPException(status_code=404, detail="La tienda todavía no está activada. Entra con el administrador para activarla.")
    if u.get("empresa_id") != t["empresa_id"] or u["rol"] not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Esta cuenta no es de esta tienda.")
    return _token_respuesta(u)


class PerfilIn(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=120)
    telefono: Optional[str] = Field(default=None, max_length=20)
    consultorio: Optional[str] = Field(default=None, max_length=150)
    especialidad: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=80)
    estado: Optional[str] = Field(default=None, max_length=60)
    direccion: Optional[str] = Field(default=None, max_length=300)
    rfc: Optional[str] = Field(default=None, max_length=13)


def _perfil(uid):
    return _q("""SELECT u.id, u.nombre_completo AS nombre, u.username AS email, u.telefono_whatsapp AS telefono,
                        d.consultorio, d.especialidad, d.ciudad, d.estado, d.direccion, d.rfc
                 FROM users u LEFT JOIN tienda_doctores d ON d.usuario_id = u.id WHERE u.id = %s""", (uid,), uno=True)


@router.get("/api/tienda/yo")
def api_yo(usuario: dict = Depends(auth.get_current_user)):
    if usuario.get("rol") not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Sin acceso")
    p = _perfil(usuario["id"]) or {}
    p["rol"] = usuario["rol"]
    return p


@router.put("/api/tienda/yo")
def api_editar_yo(payload: PerfilIn, usuario: dict = Depends(requiere_doctor)):
    d = payload.model_dump(exclude_unset=True)
    if d.get("nombre"):
        _q("UPDATE users SET nombre_completo = %s WHERE id = %s", (d["nombre"].strip(), usuario["id"]), todos=False, commit=True)
    if "telefono" in d:
        _q("UPDATE users SET telefono_whatsapp = %s WHERE id = %s", (d["telefono"], usuario["id"]), todos=False, commit=True)
    campos = {k: d[k] for k in ("consultorio", "especialidad", "ciudad", "estado", "direccion", "rfc") if k in d}
    if campos:
        _q(f"""INSERT INTO tienda_doctores (usuario_id, empresa_id) VALUES (%s, %s) ON CONFLICT (usuario_id) DO NOTHING""",
           (usuario["id"], usuario["empresa_id"]), todos=False, commit=True)
        _q(f"UPDATE tienda_doctores SET {', '.join(f'{k} = %s' for k in campos)} WHERE usuario_id = %s",
           list(campos.values()) + [usuario["id"]], todos=False, commit=True)
    return _perfil(usuario["id"])


@router.delete("/api/tienda/yo")
def api_borrar_cuenta(usuario: dict = Depends(requiere_doctor)):
    """El doctor borra su cuenta desde la app. Se quitan sus datos personales; sus pedidos
    se conservan sin datos de contacto (ley fiscal)."""
    sello = db.ahora().strftime("%Y%m%d%H%M%S")
    _q("""UPDATE users SET activo = FALSE, username = %s, password_hash = %s, nombre_completo = 'Doctor (cuenta eliminada)',
                         telefono_whatsapp = NULL, email = NULL WHERE id = %s AND rol = 'doctor'""",
       (f"eliminado-{usuario['id']}-{sello}", auth.hash_password(secrets.token_urlsafe(32)), usuario["id"]), todos=False, commit=True)
    _q("DELETE FROM tienda_doctores WHERE usuario_id = %s", (usuario["id"],), todos=False, commit=True)
    _q("DELETE FROM tienda_carrito WHERE usuario_id = %s", (usuario["id"],), todos=False, commit=True)
    _q("UPDATE tienda_pedidos SET direccion_entrega = NULL WHERE usuario_id = %s", (usuario["id"],), todos=False, commit=True)
    return {"ok": True}


# ------------------------------------------------------------------ carrito

def _carrito(usuario):
    filas = _q("""SELECT c.producto_id, c.cantidad FROM tienda_carrito c
                  JOIN tienda_productos p ON p.id = c.producto_id AND p.activo AND p.empresa_id = %s
                  WHERE c.usuario_id = %s ORDER BY c.agregado_en""", (usuario["empresa_id"], usuario["id"]))
    cant = {f["producto_id"]: f["cantidad"] for f in filas}
    productos = {p["id"]: p for p in _productos(usuario["empresa_id"], ids=list(cant))} if cant else {}
    items = []
    for pid, c in cant.items():
        p = productos.get(pid)
        if p:
            items.append({"producto_id": pid, "cantidad": c, "nombre": p["nombre"], "modelo": p.get("modelo"),
                          "marca": p.get("marca"), "precio": p["precio"], "foto_id": p.get("foto_id"),
                          "subtotal": round(p["precio"] * c, 2)})
    return {"items": items, "total": round(sum(i["subtotal"] for i in items), 2), "piezas": sum(i["cantidad"] for i in items)}


class CarritoIn(BaseModel):
    producto_id: int
    cantidad: int = Field(ge=0, le=99)   # 0 = quitar


@router.get("/api/tienda/carrito")
def api_carrito(usuario: dict = Depends(requiere_doctor)):
    return _carrito(usuario)


@router.put("/api/tienda/carrito")
def api_poner_carrito(payload: CarritoIn, usuario: dict = Depends(requiere_doctor)):
    if payload.cantidad == 0:
        _q("DELETE FROM tienda_carrito WHERE usuario_id = %s AND producto_id = %s", (usuario["id"], payload.producto_id),
           todos=False, commit=True)
    else:
        if not _q("SELECT 1 AS x FROM tienda_productos WHERE id = %s AND empresa_id = %s AND activo",
                  (payload.producto_id, usuario["empresa_id"]), uno=True):
            raise HTTPException(status_code=404, detail="Ese producto ya no está disponible.")
        _q("""INSERT INTO tienda_carrito (usuario_id, producto_id, cantidad) VALUES (%s, %s, %s)
              ON CONFLICT (usuario_id, producto_id) DO UPDATE SET cantidad = EXCLUDED.cantidad""",
           (usuario["id"], payload.producto_id, payload.cantidad), todos=False, commit=True)
    return _carrito(usuario)


# ------------------------------------------------------------------ pedidos (doctor)

class PedidoIn(BaseModel):
    forma_pago: Literal["asesor", "linea", "anticipo"] = "asesor"
    notas: Optional[str] = Field(default=None, max_length=1000)
    direccion_entrega: Optional[str] = Field(default=None, max_length=400)


def _evento(pedido_id, estado, nota=None, usuario_id=None):
    _q("INSERT INTO tienda_pedido_eventos (pedido_id, estado, nota, usuario_id) VALUES (%s, %s, %s, %s)",
       (pedido_id, estado, nota, usuario_id), todos=False, commit=True)


def _pedido(pedido_id, empresa_id, usuario_id=None):
    cond, params = "p.id = %s AND p.empresa_id = %s", [pedido_id, empresa_id]
    if usuario_id is not None:
        cond += " AND p.usuario_id = %s"; params.append(usuario_id)
    p = _q(f"""SELECT p.*, u.nombre_completo AS doctor, u.telefono_whatsapp AS telefono, u.username AS email,
                      d.consultorio, d.ciudad
               FROM tienda_pedidos p JOIN users u ON u.id = p.usuario_id
               LEFT JOIN tienda_doctores d ON d.usuario_id = p.usuario_id WHERE {cond}""", params, uno=True)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    p = _limpio(p)
    p.pop("mp_preferencia", None)
    p["items"] = [_limpio(i) for i in _q("SELECT * FROM tienda_pedido_items WHERE pedido_id = %s ORDER BY id", (pedido_id,))]
    p["eventos"] = [dict(e, nombre=NOMBRE_ESTADO.get(e["estado"], e["estado"]))
                    for e in _q("SELECT estado, nota, creado_en FROM tienda_pedido_eventos WHERE pedido_id = %s ORDER BY id", (pedido_id,))]
    p["pagos"] = [_limpio(x) for x in _q("""SELECT id, tipo, monto, estado, referencia, nota, creado_en, revisado_en,
                                                   comprobante IS NOT NULL AS tiene_comprobante
                                            FROM tienda_pagos WHERE pedido_id = %s ORDER BY id""", (pedido_id,))]
    p["estado_nombre"] = NOMBRE_ESTADO.get(p["estado"], p["estado"])
    p["saldo"] = round(p["total"] - p["pagado"], 2)
    return p


def _admins(empresa_id):
    return [r["id"] for r in _q("SELECT id FROM users WHERE empresa_id = %s AND rol = 'admin' AND activo", (empresa_id,))]


@router.post("/api/tienda/{codigo}/pedidos")
def api_crear_pedido(codigo: str, payload: PedidoIn, request: Request, usuario: dict = Depends(requiere_doctor)):
    t = tienda_por_codigo(codigo)
    if usuario["empresa_id"] != t["empresa_id"]:
        raise HTTPException(status_code=403, detail="Esta cuenta no es de esta tienda.")
    if payload.forma_pago not in _publica(t)["formas_pago"]:
        raise HTTPException(status_code=400, detail="Esa forma de pago no está disponible.")
    c = _carrito(usuario)
    if not c["items"]:
        raise HTTPException(status_code=400, detail="Tu carrito está vacío.")
    total = c["total"]
    anticipo = round(total * float(t["anticipo_pct"]) / 100, 2) if payload.forma_pago == "anticipo" else (total if payload.forma_pago == "linea" else 0)
    n = (_q("SELECT COUNT(*) AS n FROM tienda_pedidos WHERE empresa_id = %s", (t["empresa_id"],), uno=True) or {}).get("n", 0) + 1
    folio = f"UD-{n:05d}"
    pid = _q("""INSERT INTO tienda_pedidos (empresa_id, folio, usuario_id, forma_pago, total, anticipo, notas, direccion_entrega)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
             (t["empresa_id"], folio, usuario["id"], payload.forma_pago, total, anticipo, payload.notas, payload.direccion_entrega),
             uno=True, commit=True)["id"]
    for i in c["items"]:
        _q("""INSERT INTO tienda_pedido_items (pedido_id, producto_id, nombre, modelo, marca, foto_id, precio, cantidad)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
           (pid, i["producto_id"], i["nombre"], i.get("modelo"), i.get("marca"), i.get("foto_id"), i["precio"], i["cantidad"]),
           todos=False, commit=True)
    _q("DELETE FROM tienda_carrito WHERE usuario_id = %s", (usuario["id"],), todos=False, commit=True)
    _evento(pid, "recibido", None, usuario["id"])
    avisos.avisar_seguro(_admins(t["empresa_id"]), f"🛒 Pedido nuevo {folio}",
                         f"{usuario.get('nombre') or 'Un doctor'} · ${total:,.2f} · pago {payload.forma_pago}", modulo="tienda", ref=pid)
    r = {"pedido": _pedido(pid, t["empresa_id"])}
    if payload.forma_pago in ("linea", "anticipo"):
        r["pago_url"] = _preferencia_mp(t, pid, folio, anticipo, request)
    return r


@router.post("/api/tienda/{codigo}/pedidos/{pedido_id}/pagar")
def api_pagar_pedido(codigo: str, pedido_id: int, request: Request, usuario: dict = Depends(requiere_doctor)):
    """Vuelve a abrir el pago en línea de lo que falta (o del anticipo si no ha pagado nada)."""
    t = tienda_por_codigo(codigo)
    p = _pedido(pedido_id, t["empresa_id"], usuario["id"])
    if p["estado"] == "cancelado" or p["saldo"] <= 0:
        raise HTTPException(status_code=400, detail="Este pedido no tiene saldo por pagar.")
    monto = p["anticipo"] if p["pagado"] <= 0 and p["forma_pago"] == "anticipo" else p["saldo"]
    return {"pago_url": _preferencia_mp(t, pedido_id, p["folio"], monto, request)}


def _preferencia_mp(t, pedido_id, folio, monto, request):
    token = _mp_token(t)
    if not token or monto <= 0:
        return None
    base = str(request.base_url).rstrip("/")
    try:
        r = requests.post("https://api.mercadopago.com/checkout/preferences", timeout=20,
                          headers={"Authorization": f"Bearer {token}"},
                          json={"items": [{"title": f"Pedido {folio} — {t['nombre']}", "quantity": 1,
                                           "unit_price": round(float(monto), 2), "currency_id": "MXN"}],
                                "external_reference": f"{t['empresa_id']}:{pedido_id}",
                                "notification_url": f"{base}/api/tienda/mp/webhook",
                                "back_urls": {"success": f"{base}/tienda/pago-listo", "failure": f"{base}/tienda/pago-listo",
                                              "pending": f"{base}/tienda/pago-listo"},
                                "auto_return": "approved"})
        r.raise_for_status()
        d = r.json()
        _q("UPDATE tienda_pedidos SET mp_preferencia = %s WHERE id = %s", (d.get("id"), pedido_id), todos=False, commit=True)
        return d.get("init_point")
    except Exception as e:
        print(f"[tienda] Mercado Pago: {e}")
        return None


@router.post("/api/tienda/mp/webhook")
async def api_webhook_mp(request: Request):
    """Mercado Pago avisa de un pago: se consulta el pago con el token de la tienda y,
    si está aprobado, se registra (una sola vez por id de pago)."""
    try:
        cuerpo = await request.json()
    except Exception:
        cuerpo = {}
    q = request.query_params
    pago_id = str((cuerpo.get("data") or {}).get("id") or q.get("data.id") or q.get("id") or "")
    tipo = cuerpo.get("type") or q.get("type") or q.get("topic")
    if tipo != "payment" or not pago_id.isdigit():
        return {"ok": True}
    for t in _q("SELECT * FROM tienda_config WHERE activa"):
        token = _mp_token(t)
        if not token:
            continue
        try:
            r = requests.get(f"https://api.mercadopago.com/v1/payments/{pago_id}", headers={"Authorization": f"Bearer {token}"}, timeout=20)
            if r.status_code != 200:
                continue
            pago = r.json()
        except Exception:
            continue
        ref = str(pago.get("external_reference") or "")
        if not ref.startswith(f"{t['empresa_id']}:"):
            continue
        pedido_id = int(ref.split(":", 1)[1])
        if pago.get("status") == "approved" and not _q("SELECT 1 AS x FROM tienda_pagos WHERE referencia = %s", (f"mp:{pago_id}",), uno=True):
            monto = float(pago.get("transaction_amount") or 0)
            _q("""INSERT INTO tienda_pagos (pedido_id, tipo, monto, estado, referencia, revisado_en)
                  VALUES (%s, 'linea', %s, 'aprobado', %s, NOW())""", (pedido_id, monto, f"mp:{pago_id}"), todos=False, commit=True)
            _sumar_pago(t["empresa_id"], pedido_id, monto, "Pago en línea con Mercado Pago")
        return {"ok": True}
    return {"ok": True}


def _sumar_pago(empresa_id, pedido_id, monto, nota):
    p = _q("UPDATE tienda_pedidos SET pagado = pagado + %s, actualizado_en = NOW() WHERE id = %s AND empresa_id = %s RETURNING *",
           (monto, pedido_id, empresa_id), uno=True, commit=True)
    if not p:
        return
    _evento(pedido_id, "pago", f"{nota}: ${monto:,.2f}")
    if float(p["pagado"]) >= float(p["total"]) and p["estado"] in ("recibido", "confirmado"):
        _q("UPDATE tienda_pedidos SET estado = 'pagado' WHERE id = %s", (pedido_id,), todos=False, commit=True)
        _evento(pedido_id, "pagado")
    avisos.avisar_seguro([p["usuario_id"]], f"✅ Recibimos tu pago — {p['folio']}", f"${monto:,.2f}. Gracias.",
                         modulo="tienda", ref=pedido_id)


@router.get("/api/tienda/mis-pedidos")
def api_mis_pedidos(usuario: dict = Depends(requiere_doctor)):
    filas = _q("""SELECT p.id, p.folio, p.estado, p.forma_pago, p.total, p.pagado, p.creado_en,
                         (SELECT COUNT(*) FROM tienda_pedido_items i WHERE i.pedido_id = p.id) AS productos,
                         (SELECT i.foto_id FROM tienda_pedido_items i WHERE i.pedido_id = p.id ORDER BY i.id LIMIT 1) AS foto_id
                  FROM tienda_pedidos p WHERE p.usuario_id = %s ORDER BY p.id DESC""", (usuario["id"],))
    return [dict(_limpio(f), estado_nombre=NOMBRE_ESTADO.get(f["estado"], f["estado"])) for f in filas]


@router.get("/api/tienda/mis-pedidos/{pedido_id}")
def api_mi_pedido(pedido_id: int, usuario: dict = Depends(requiere_doctor)):
    return _pedido(pedido_id, usuario["empresa_id"], usuario["id"])


class ComprobanteIn(BaseModel):
    monto: float = Field(gt=0, le=100_000_000)
    archivo_base64: str = Field(min_length=100)
    referencia: Optional[str] = Field(default=None, max_length=100)


def _bytes_b64(texto, maximo):
    tipo = "image/jpeg"
    if texto.startswith("data:"):
        cab, texto = texto.split(",", 1)
        tipo = cab[5:].split(";")[0] or tipo
    try:
        b = base64.b64decode(texto)
    except Exception:
        raise HTTPException(status_code=400, detail="Archivo inválido.")
    if len(b) > maximo:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado.")
    return b, tipo


@router.post("/api/tienda/mis-pedidos/{pedido_id}/comprobante")
def api_comprobante(pedido_id: int, payload: ComprobanteIn, usuario: dict = Depends(requiere_doctor)):
    p = _pedido(pedido_id, usuario["empresa_id"], usuario["id"])
    if p["estado"] == "cancelado":
        raise HTTPException(status_code=400, detail="El pedido está cancelado.")
    datos, tipo = _bytes_b64(payload.archivo_base64, MAX_COMPROBANTE)
    _q("""INSERT INTO tienda_pagos (pedido_id, tipo, monto, comprobante, comprobante_tipo, referencia)
          VALUES (%s, 'comprobante', %s, %s, %s, %s)""",
       (pedido_id, payload.monto, psycopg2.Binary(datos), tipo, payload.referencia), todos=False, commit=True)
    _evento(pedido_id, "comprobante", f"Subió comprobante por ${payload.monto:,.2f}", usuario["id"])
    avisos.avisar_seguro(_admins(usuario["empresa_id"]), f"🧾 Comprobante — {p['folio']}",
                         f"{p['doctor']} subió ${payload.monto:,.2f}. Revísalo.", modulo="tienda", ref=pedido_id)
    return _pedido(pedido_id, usuario["empresa_id"], usuario["id"])


@router.post("/api/tienda/mis-pedidos/{pedido_id}/cancelar")
def api_cancelar_mi_pedido(pedido_id: int, usuario: dict = Depends(requiere_doctor)):
    p = _pedido(pedido_id, usuario["empresa_id"], usuario["id"])
    if p["estado"] != "recibido" or p["pagado"] > 0:
        raise HTTPException(status_code=400, detail="Ya no se puede cancelar desde la app; habla con tu asesor.")
    _q("UPDATE tienda_pedidos SET estado = 'cancelado', actualizado_en = NOW() WHERE id = %s", (pedido_id,), todos=False, commit=True)
    _evento(pedido_id, "cancelado", "Cancelado por el doctor", usuario["id"])
    avisos.avisar_seguro(_admins(usuario["empresa_id"]), f"Pedido cancelado {p['folio']}", p["doctor"], modulo="tienda", ref=pedido_id)
    return _pedido(pedido_id, usuario["empresa_id"], usuario["id"])


# ------------------------------------------------------------------ administración

class TiendaConfigIn(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=60)
    pago_asesor: Optional[bool] = None
    pago_linea: Optional[bool] = None
    pago_anticipo: Optional[bool] = None
    anticipo_pct: Optional[float] = Field(default=None, ge=1, le=99)
    datos_pago: Optional[str] = Field(default=None, max_length=1000)
    whatsapp: Optional[str] = Field(default=None, max_length=20)
    mp_access_token: Optional[str] = Field(default=None, max_length=200)


class ActivarTiendaIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=30, pattern=r"^[a-z0-9-]+$")
    nombre: str = Field(default="Unidental", max_length=60)


@router.post("/api/tienda/admin/activar")
def api_activar_tienda(payload: ActivarTiendaIn, usuario: dict = Depends(auth.get_current_user)):
    """El administrador de la empresa nueva activa su tienda una vez (código que usa la app)."""
    if usuario.get("rol") != "admin" or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Solo el administrador de la empresa.")
    otra = _q("SELECT empresa_id FROM tienda_config WHERE codigo = %s", (payload.codigo,), uno=True)
    if otra and otra["empresa_id"] != usuario["empresa_id"]:
        raise HTTPException(status_code=409, detail="Ese código ya lo usa otra tienda.")
    _q("""INSERT INTO tienda_config (empresa_id, codigo, nombre) VALUES (%s, %s, %s)
          ON CONFLICT (empresa_id) DO UPDATE SET codigo = EXCLUDED.codigo, nombre = EXCLUDED.nombre""",
       (usuario["empresa_id"], payload.codigo, payload.nombre), todos=False, commit=True)
    return {"ok": True, "codigo": payload.codigo}


@router.get("/api/tienda/admin/config")
def api_config(usuario: dict = Depends(requiere_admin_tienda)):
    t = _limpio(dict(usuario["tienda"]))
    t["mp_configurado"] = bool(_mp_token(usuario["tienda"]))
    t.pop("mp_access_token", None)
    return t


@router.put("/api/tienda/admin/config")
def api_guardar_config(payload: TiendaConfigIn, usuario: dict = Depends(requiere_admin_tienda)):
    d = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k == "mp_access_token"}
    if d.get("mp_access_token") == "":
        d["mp_access_token"] = None
    if d:
        _q(f"UPDATE tienda_config SET {', '.join(f'{k} = %s' for k in d)} WHERE empresa_id = %s",
           list(d.values()) + [usuario["empresa_id"]], todos=False, commit=True)
    usuario["tienda"] = _q("SELECT * FROM tienda_config WHERE empresa_id = %s", (usuario["empresa_id"],), uno=True)
    return api_config(usuario)


class MarcaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: Optional[str] = Field(default=None, max_length=500)
    orden: int = 0
    activa: bool = True


@router.get("/api/tienda/admin/marcas")
def api_marcas_admin(usuario: dict = Depends(requiere_admin_tienda)):
    return _q("SELECT * FROM tienda_marcas WHERE empresa_id = %s ORDER BY orden, nombre", (usuario["empresa_id"],))


@router.post("/api/tienda/admin/marcas")
def api_crear_marca(payload: MarcaIn, usuario: dict = Depends(requiere_admin_tienda)):
    return _q("""INSERT INTO tienda_marcas (empresa_id, nombre, descripcion, orden, activa) VALUES (%s, %s, %s, %s, %s) RETURNING *""",
              (usuario["empresa_id"], payload.nombre.strip(), payload.descripcion, payload.orden, payload.activa), uno=True, commit=True)


@router.put("/api/tienda/admin/marcas/{marca_id}")
def api_editar_marca(marca_id: int, payload: MarcaIn, usuario: dict = Depends(requiere_admin_tienda)):
    r = _q("""UPDATE tienda_marcas SET nombre = %s, descripcion = %s, orden = %s, activa = %s
              WHERE id = %s AND empresa_id = %s RETURNING *""",
           (payload.nombre.strip(), payload.descripcion, payload.orden, payload.activa, marca_id, usuario["empresa_id"]), uno=True, commit=True)
    if not r:
        raise HTTPException(status_code=404, detail="Marca no encontrada")
    return r


class CaracteristicaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    valor: str = Field(min_length=1, max_length=300)


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    marca_id: Optional[int] = None
    modelo: Optional[str] = Field(default=None, max_length=100)
    categoria: str = Field(default="Unidades dentales", max_length=60)
    descripcion: Optional[str] = Field(default=None, max_length=5000)
    caracteristicas: List[CaracteristicaIn] = []
    precio: float = Field(ge=0, le=100_000_000)
    precio_anterior: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    meses_sin_intereses: Optional[int] = Field(default=None, ge=0, le=48)
    entrega: Optional[str] = Field(default=None, max_length=120)
    garantia: Optional[str] = Field(default=None, max_length=120)
    destacado: bool = False
    activo: bool = True
    orden: int = 0


def _validar_marca(empresa_id, marca_id):
    if marca_id and not _q("SELECT 1 AS x FROM tienda_marcas WHERE id = %s AND empresa_id = %s", (marca_id, empresa_id), uno=True):
        raise HTTPException(status_code=404, detail="Marca no encontrada")


@router.get("/api/tienda/admin/productos")
def api_productos_admin(usuario: dict = Depends(requiere_admin_tienda)):
    return _productos(usuario["empresa_id"], solo_activos=False)


@router.get("/api/tienda/admin/productos/{producto_id}")
def api_producto_admin(producto_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    return _detalle(usuario["empresa_id"], producto_id, solo_activo=False)


@router.post("/api/tienda/admin/productos")
def api_crear_producto(payload: ProductoIn, usuario: dict = Depends(requiere_admin_tienda)):
    _validar_marca(usuario["empresa_id"], payload.marca_id)
    d = payload.model_dump()
    d["caracteristicas"] = psycopg2.extras.Json(d["caracteristicas"])
    cols = list(d)
    r = _q(f"INSERT INTO tienda_productos (empresa_id, {', '.join(cols)}) VALUES (%s, {', '.join(['%s'] * len(cols))}) RETURNING id",
           [usuario["empresa_id"]] + [d[c] for c in cols], uno=True, commit=True)
    return _detalle(usuario["empresa_id"], r["id"], solo_activo=False)


@router.put("/api/tienda/admin/productos/{producto_id}")
def api_editar_producto(producto_id: int, payload: ProductoIn, usuario: dict = Depends(requiere_admin_tienda)):
    _validar_marca(usuario["empresa_id"], payload.marca_id)
    d = payload.model_dump()
    d["caracteristicas"] = psycopg2.extras.Json(d["caracteristicas"])
    r = _q(f"""UPDATE tienda_productos SET {', '.join(f'{c} = %s' for c in d)}, actualizado_en = NOW()
               WHERE id = %s AND empresa_id = %s RETURNING id""",
           list(d.values()) + [producto_id, usuario["empresa_id"]], uno=True, commit=True)
    if not r:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _detalle(usuario["empresa_id"], producto_id, solo_activo=False)


@router.delete("/api/tienda/admin/productos/{producto_id}")
def api_quitar_producto(producto_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    """No se borra (está en pedidos): se oculta del catálogo."""
    _q("UPDATE tienda_productos SET activo = FALSE, actualizado_en = NOW() WHERE id = %s AND empresa_id = %s",
       (producto_id, usuario["empresa_id"]), todos=False, commit=True)
    return {"ok": True}


class FotoIn(BaseModel):
    foto_base64: str = Field(min_length=100)


def _producto_de_empresa(empresa_id, producto_id):
    if not _q("SELECT 1 AS x FROM tienda_productos WHERE id = %s AND empresa_id = %s", (producto_id, empresa_id), uno=True):
        raise HTTPException(status_code=404, detail="Producto no encontrado")


@router.post("/api/tienda/admin/productos/{producto_id}/fotos")
def api_subir_foto(producto_id: int, payload: FotoIn, usuario: dict = Depends(requiere_admin_tienda)):
    _producto_de_empresa(usuario["empresa_id"], producto_id)
    datos, tipo = _bytes_b64(payload.foto_base64, MAX_FOTO)
    orden = (_q("SELECT COALESCE(MAX(orden), -1) + 1 AS o FROM tienda_fotos WHERE producto_id = %s", (producto_id,), uno=True) or {}).get("o", 0)
    r = _q("INSERT INTO tienda_fotos (empresa_id, producto_id, datos, tipo, orden) VALUES (%s, %s, %s, %s, %s) RETURNING id",
           (usuario["empresa_id"], producto_id, psycopg2.Binary(datos), tipo, orden), uno=True, commit=True)
    return {"id": r["id"]}


@router.delete("/api/tienda/admin/fotos/{foto_id}")
def api_borrar_foto(foto_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    _q("DELETE FROM tienda_fotos WHERE id = %s AND empresa_id = %s", (foto_id, usuario["empresa_id"]), todos=False, commit=True)
    return {"ok": True}


class OrdenFotosIn(BaseModel):
    fotos: List[int]


@router.put("/api/tienda/admin/productos/{producto_id}/fotos/orden")
def api_orden_fotos(producto_id: int, payload: OrdenFotosIn, usuario: dict = Depends(requiere_admin_tienda)):
    """La primera es la portada del producto."""
    for i, fid in enumerate(payload.fotos):
        _q("UPDATE tienda_fotos SET orden = %s WHERE id = %s AND producto_id = %s AND empresa_id = %s",
           (i, fid, producto_id, usuario["empresa_id"]), todos=False, commit=True)
    return {"ok": True}


@router.post("/api/tienda/admin/productos/{producto_id}/videos")
def api_subir_video(producto_id: int, archivo: UploadFile = File(...), titulo: str = Form(""), en_feed: bool = Form(True),
                    usuario: dict = Depends(requiere_admin_tienda)):
    _producto_de_empresa(usuario["empresa_id"], producto_id)
    if not r2.configurado():
        raise HTTPException(status_code=400, detail="Falta configurar el almacenamiento de videos (R2) en el servidor.")
    key, url = r2.subir_video(usuario["empresa_id"], archivo.filename or "video.mp4", archivo.file, archivo.content_type)
    r = _q("""INSERT INTO tienda_videos (empresa_id, producto_id, titulo, url, r2_key, en_feed) VALUES (%s, %s, %s, %s, %s, %s)
              RETURNING id, titulo, url, en_feed""", (usuario["empresa_id"], producto_id, titulo.strip() or None, url, key, en_feed),
           uno=True, commit=True)
    return r


@router.delete("/api/tienda/admin/videos/{video_id}")
def api_borrar_video(video_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    v = _q("DELETE FROM tienda_videos WHERE id = %s AND empresa_id = %s RETURNING r2_key", (video_id, usuario["empresa_id"]), uno=True, commit=True)
    if v and v.get("r2_key"):
        try:
            r2.eliminar_video(v["r2_key"])
        except Exception:
            pass
    return {"ok": True}


@router.get("/api/tienda/admin/pedidos")
def api_pedidos_admin(estado: Optional[str] = None, usuario: dict = Depends(requiere_admin_tienda)):
    cond, params = ["p.empresa_id = %s"], [usuario["empresa_id"]]
    if estado:
        cond.append("p.estado = %s"); params.append(estado)
    filas = _q(f"""SELECT p.id, p.folio, p.estado, p.forma_pago, p.total, p.pagado, p.creado_en, u.nombre_completo AS doctor,
                          d.consultorio, d.ciudad,
                          (SELECT COUNT(*) FROM tienda_pagos g WHERE g.pedido_id = p.id AND g.estado = 'pendiente') AS pagos_por_revisar
                   FROM tienda_pedidos p JOIN users u ON u.id = p.usuario_id LEFT JOIN tienda_doctores d ON d.usuario_id = p.usuario_id
                   WHERE {' AND '.join(cond)} ORDER BY p.id DESC LIMIT 500""", params)
    return [dict(_limpio(f), estado_nombre=NOMBRE_ESTADO.get(f["estado"], f["estado"])) for f in filas]


@router.get("/api/tienda/admin/pedidos/{pedido_id}")
def api_pedido_admin(pedido_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    return _pedido(pedido_id, usuario["empresa_id"])


class EstadoPedidoIn(BaseModel):
    estado: str
    nota: Optional[str] = Field(default=None, max_length=500)


@router.post("/api/tienda/admin/pedidos/{pedido_id}/estado")
def api_estado_pedido(pedido_id: int, payload: EstadoPedidoIn, usuario: dict = Depends(requiere_admin_tienda)):
    if payload.estado not in ESTADOS_PEDIDO:
        raise HTTPException(status_code=400, detail="Estado inválido")
    p = _pedido(pedido_id, usuario["empresa_id"])
    _q("UPDATE tienda_pedidos SET estado = %s, actualizado_en = NOW() WHERE id = %s", (payload.estado, pedido_id), todos=False, commit=True)
    _evento(pedido_id, payload.estado, payload.nota, usuario["id"])
    avisos.avisar_seguro([p["usuario_id"]], f"📦 {p['folio']}: {NOMBRE_ESTADO[payload.estado]}",
                         payload.nota or "Toca para ver el seguimiento de tu pedido.", modulo="tienda", ref=pedido_id)
    return _pedido(pedido_id, usuario["empresa_id"])


class RevisarPagoIn(BaseModel):
    aprobar: bool
    monto: Optional[float] = Field(default=None, gt=0)
    nota: Optional[str] = Field(default=None, max_length=300)


@router.post("/api/tienda/admin/pagos/{pago_id}/revisar")
def api_revisar_pago(pago_id: int, payload: RevisarPagoIn, usuario: dict = Depends(requiere_admin_tienda)):
    g = _q("""SELECT g.*, p.empresa_id, p.usuario_id, p.folio FROM tienda_pagos g JOIN tienda_pedidos p ON p.id = g.pedido_id
              WHERE g.id = %s AND p.empresa_id = %s""", (pago_id, usuario["empresa_id"]), uno=True)
    if not g:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if g["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Ese pago ya se revisó.")
    monto = payload.monto or float(g["monto"])
    _q("UPDATE tienda_pagos SET estado = %s, monto = %s, nota = %s, revisado_en = NOW() WHERE id = %s",
       ("aprobado" if payload.aprobar else "rechazado", monto, payload.nota, pago_id), todos=False, commit=True)
    if payload.aprobar:
        _sumar_pago(usuario["empresa_id"], g["pedido_id"], monto, "Pago confirmado")
    else:
        _evento(g["pedido_id"], "pago_rechazado", payload.nota, usuario["id"])
        avisos.avisar_seguro([g["usuario_id"]], f"⚠️ Revisa tu pago — {g['folio']}", payload.nota or "No pudimos confirmar tu comprobante.",
                             modulo="tienda", ref=g["pedido_id"])
    return _pedido(g["pedido_id"], usuario["empresa_id"])


@router.get("/api/tienda/admin/pagos/{pago_id}/comprobante")
def api_ver_comprobante(pago_id: int, usuario: dict = Depends(requiere_admin_tienda)):
    g = _q("""SELECT g.comprobante, g.comprobante_tipo FROM tienda_pagos g JOIN tienda_pedidos p ON p.id = g.pedido_id
              WHERE g.id = %s AND p.empresa_id = %s""", (pago_id, usuario["empresa_id"]), uno=True)
    if not g or not g.get("comprobante"):
        raise HTTPException(status_code=404, detail="Sin comprobante")
    return Response(content=bytes(g["comprobante"]), media_type=g.get("comprobante_tipo") or "image/jpeg")


@router.get("/api/tienda/admin/doctores")
def api_doctores(usuario: dict = Depends(requiere_admin_tienda)):
    return [_limpio(f) for f in _q("""
        SELECT u.id, u.nombre_completo AS nombre, u.username AS email, u.telefono_whatsapp AS telefono, u.creado_en,
               d.consultorio, d.especialidad, d.ciudad, d.estado,
               (SELECT COUNT(*) FROM tienda_pedidos p WHERE p.usuario_id = u.id) AS pedidos,
               (SELECT COALESCE(SUM(p.total), 0) FROM tienda_pedidos p WHERE p.usuario_id = u.id AND p.estado != 'cancelado') AS comprado
        FROM users u LEFT JOIN tienda_doctores d ON d.usuario_id = u.id
        WHERE u.empresa_id = %s AND u.rol = 'doctor' AND u.activo ORDER BY u.id DESC""", (usuario["empresa_id"],))]
