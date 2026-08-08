import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

import auth
import db
import notifications

db.init_db()

app = FastAPI(title="Tickets TI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def requiere_staff(usuario: dict = Depends(auth.get_current_user)):
    """admin o tecnico — para acciones de gestión del tablero."""
    if usuario["rol"] not in ("admin", "tecnico"):
        raise HTTPException(status_code=403, detail="No tienes permiso para hacer esto")
    return usuario


def requiere_admin(usuario: dict = Depends(auth.get_current_user)):
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede hacer esto")
    return usuario


# ---- Modelos ----

class LoginPayload(BaseModel):
    username: str
    password: str


class NuevoTicket(BaseModel):
    departamento: str
    descripcion: str = Field(min_length=3)
    categoria: str = "otro"
    prioridad: str = "media"


class ActualizacionTicket(BaseModel):
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    asignado_a_id: Optional[int] = None


class NuevoComentario(BaseModel):
    texto: str = Field(min_length=1)


class NuevoUsuario(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    nombre_completo: str
    rol: str
    telefono_whatsapp: Optional[str] = None


class ActualizacionUsuario(BaseModel):
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    telefono_whatsapp: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = None


# ---- Auth ----

@app.post("/api/auth/login")
def login(payload: LoginPayload):
    usuario = db.obtener_usuario_por_username(payload.username)
    if not usuario or not usuario["activo"] or not auth.verificar_password(payload.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = auth.crear_token(usuario)
    return {
        "token": token,
        "usuario": {"id": usuario["id"], "username": usuario["username"], "nombre": usuario["nombre_completo"], "rol": usuario["rol"]},
    }


@app.get("/api/auth/me")
def me(usuario: dict = Depends(auth.get_current_user)):
    return usuario


# ---- Meta ----

@app.get("/api/meta")
def meta():
    return {
        "estados": db.ESTADOS, "prioridades": db.PRIORIDADES,
        "categorias": db.CATEGORIAS, "departamentos": db.DEPARTAMENTOS, "roles": db.ROLES,
    }


# ---- Usuarios (solo admin) ----

@app.get("/api/usuarios")
def api_listar_usuarios(_: dict = Depends(requiere_admin)):
    return db.listar_usuarios()


@app.get("/api/usuarios/tecnicos")
def api_listar_tecnicos(_: dict = Depends(requiere_staff)):
    tecnicos = db.listar_tecnicos_activos()
    return [{"id": t["id"], "nombre_completo": t["nombre_completo"]} for t in tecnicos]


@app.post("/api/usuarios")
def api_crear_usuario(payload: NuevoUsuario, _: dict = Depends(requiere_admin)):
    if payload.rol not in db.ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.obtener_usuario_por_username(payload.username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya existe")
    uid = db.crear_usuario(payload.username, payload.password, payload.nombre_completo, payload.rol, payload.telefono_whatsapp)
    return {"id": uid}


@app.patch("/api/usuarios/{usuario_id}")
def api_actualizar_usuario(usuario_id: int, payload: ActualizacionUsuario, _: dict = Depends(requiere_admin)):
    if payload.rol and payload.rol not in db.ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    db.actualizar_usuario(
        usuario_id, nombre_completo=payload.nombre_completo, rol=payload.rol,
        telefono_whatsapp=payload.telefono_whatsapp, activo=payload.activo, password=payload.password,
    )
    return {"ok": True}


@app.delete("/api/usuarios/{usuario_id}")
def api_eliminar_usuario(usuario_id: int, admin: dict = Depends(requiere_admin)):
    if usuario_id == admin["id"]:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    db.eliminar_usuario(usuario_id)
    return {"ok": True}


# ---- Tickets ----

@app.get("/api/tickets")
def listar(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
           usuario: dict = Depends(auth.get_current_user)):
    # un "usuario" normal solo ve sus propios tickets; admin/tecnico ven todo
    solicitante_id = usuario["id"] if usuario["rol"] == "usuario" else None
    return db.listar_tickets(estado, prioridad, categoria, solicitante_id)


@app.get("/api/tickets/{ticket_id}")
def detalle(ticket_id: int, usuario: dict = Depends(auth.get_current_user)):
    ticket = db.obtener_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if usuario["rol"] == "usuario" and ticket["solicitante_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver tickets de otras personas")
    return ticket


@app.post("/api/tickets")
def crear(payload: NuevoTicket, usuario: dict = Depends(auth.get_current_user)):
    if payload.departamento not in db.DEPARTAMENTOS:
        raise HTTPException(status_code=400, detail="Departamento inválido")
    if payload.categoria not in db.CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    ticket = db.crear_ticket(payload.departamento, payload.descripcion, payload.categoria, payload.prioridad, usuario["id"])

    tecnicos = db.listar_tecnicos_activos()
    notifications.notificar_nuevo_ticket(tecnicos, ticket)

    return ticket


@app.patch("/api/tickets/{ticket_id}")
def actualizar(ticket_id: int, payload: ActualizacionTicket, _: dict = Depends(requiere_staff)):
    if payload.estado and payload.estado not in db.ESTADOS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    if payload.prioridad and payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    ticket_antes = db.obtener_ticket(ticket_id)
    ticket = db.actualizar_ticket(ticket_id, payload.estado, payload.prioridad, payload.asignado_a_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    # si se asignó a alguien nuevo, notificarle
    if payload.asignado_a_id and (not ticket_antes or ticket_antes.get("asignado_a_id") != payload.asignado_a_id):
        tecnicos = {t["id"]: t for t in db.listar_tecnicos_activos()}
        tecnico = tecnicos.get(payload.asignado_a_id)
        if tecnico:
            notifications.notificar_asignacion(tecnico, ticket)

    return ticket


@app.post("/api/tickets/{ticket_id}/comentarios")
def comentar(ticket_id: int, payload: NuevoComentario, usuario: dict = Depends(auth.get_current_user)):
    ticket = db.obtener_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if usuario["rol"] == "usuario" and ticket["solicitante_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes comentar tickets de otras personas")
    return db.agregar_comentario(ticket_id, usuario["id"], payload.texto)


@app.get("/api/stats")
def stats(_: dict = Depends(requiere_staff)):
    return db.estadisticas()


# Sirve el frontend estático
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")
