import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

import db

db.init_db()

app = FastAPI(title="Tickets TI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NuevoTicket(BaseModel):
    titulo: str = Field(min_length=3, max_length=140)
    descripcion: str = Field(min_length=3)
    categoria: str = "otro"
    prioridad: str = "media"
    solicitante: str = Field(min_length=1)


class ActualizacionTicket(BaseModel):
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    asignado_a: Optional[str] = None


class NuevoComentario(BaseModel):
    autor: str
    texto: str = Field(min_length=1)


@app.get("/api/meta")
def meta():
    return {"estados": db.ESTADOS, "prioridades": db.PRIORIDADES, "categorias": db.CATEGORIAS}


@app.get("/api/tickets")
def listar(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None):
    return db.listar_tickets(estado, prioridad, categoria)


@app.get("/api/tickets/{ticket_id}")
def detalle(ticket_id: int):
    ticket = db.obtener_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket


@app.post("/api/tickets")
def crear(payload: NuevoTicket):
    if payload.categoria not in db.CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    return db.crear_ticket(payload.titulo, payload.descripcion, payload.categoria, payload.prioridad, payload.solicitante)


@app.patch("/api/tickets/{ticket_id}")
def actualizar(ticket_id: int, payload: ActualizacionTicket):
    if payload.estado and payload.estado not in db.ESTADOS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    if payload.prioridad and payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    ticket = db.actualizar_ticket(ticket_id, payload.estado, payload.prioridad, payload.asignado_a)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket


@app.post("/api/tickets/{ticket_id}/comentarios")
def comentar(ticket_id: int, payload: NuevoComentario):
    ticket = db.agregar_comentario(ticket_id, payload.autor, payload.texto)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket


@app.get("/api/stats")
def stats():
    return db.estadisticas()


# Sirve el frontend estático
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/sw.js")
def service_worker():
    # Se sirve desde la raíz (no desde /static) para que su alcance
    # cubra toda la app, no solo la carpeta de estáticos.
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")
