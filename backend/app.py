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
        "estados": db.ESTADOS, "prioridades": db.PRIORIDADES, "roles": db.ROLES,
        "departamentos": [d["nombre"] for d in db.listar_departamentos()],
        "categorias": [c["nombre"] for c in db.listar_categorias()],
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


# ---- Departamentos (solo admin gestiona; cualquiera logueado los lista vía /api/meta) ----

class NuevoNombre(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)


class CambioEstado(BaseModel):
    activo: bool


@app.get("/api/departamentos")
def api_listar_departamentos(_: dict = Depends(requiere_admin)):
    return db.listar_departamentos(solo_activos=False)


@app.post("/api/departamentos")
def api_crear_departamento(payload: NuevoNombre, _: dict = Depends(requiere_admin)):
    try:
        db.crear_departamento(payload.nombre.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Ese departamento ya existe")
    return {"ok": True}


@app.patch("/api/departamentos/{depto_id}")
def api_cambiar_estado_departamento(depto_id: int, payload: CambioEstado, _: dict = Depends(requiere_admin)):
    db.cambiar_estado_departamento(depto_id, payload.activo)
    return {"ok": True}


# ---- Categorías (mismo patrón que departamentos) ----

@app.get("/api/categorias")
def api_listar_categorias(_: dict = Depends(requiere_admin)):
    return db.listar_categorias(solo_activos=False)


@app.post("/api/categorias")
def api_crear_categoria(payload: NuevoNombre, _: dict = Depends(requiere_admin)):
    try:
        db.crear_categoria(payload.nombre.strip().lower())
    except Exception:
        raise HTTPException(status_code=400, detail="Esa categoría ya existe")
    return {"ok": True}


@app.patch("/api/categorias/{cat_id}")
def api_cambiar_estado_categoria(cat_id: int, payload: CambioEstado, _: dict = Depends(requiere_admin)):
    db.cambiar_estado_categoria(cat_id, payload.activo)
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
    departamentos_validos = {d["nombre"] for d in db.listar_departamentos()}
    categorias_validas = {c["nombre"] for c in db.listar_categorias()}
    if payload.departamento not in departamentos_validos:
        raise HTTPException(status_code=400, detail="Departamento inválido")
    if payload.categoria not in categorias_validas:
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


class NuevaFirma(BaseModel):
    firma: str = Field(min_length=100)  # imagen en base64 (data URL del canvas)
    firmado_por: str = Field(min_length=1, max_length=120)


@app.post("/api/tickets/{ticket_id}/firmar")
def firmar(ticket_id: int, payload: NuevaFirma, _: dict = Depends(requiere_staff)):
    ticket = db.obtener_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if ticket["estado"] == "cerrado":
        raise HTTPException(status_code=400, detail="Este ticket ya está cerrado")
    return db.firmar_ticket(ticket_id, payload.firma, payload.firmado_por.strip())


@app.get("/api/stats")
def stats(_: dict = Depends(requiere_staff)):
    return db.estadisticas()


@app.get("/api/tickets/reporte.pdf")
def reporte_pdf(_: dict = Depends(requiere_staff)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    todos = db.listar_tickets()
    abiertos = [t for t in todos if t["estado"] in ("abierto", "en_progreso")]
    cerrados = [t for t in todos if t["estado"] in ("resuelto", "cerrado") and t.get("resuelto_en")]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph("Reporte de tickets — Mark·Inc TI", styles["Title"]))
    elementos.append(Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elementos.append(Spacer(1, 16))

    elementos.append(Paragraph(f"Tickets abiertos ({len(abiertos)})", styles["Heading2"]))
    datos_abiertos = [["Folio", "Departamento", "Solicitante", "Prioridad", "Estado", "Creado"]]
    for t in abiertos:
        datos_abiertos.append([
            t["folio"], t["departamento"], t["solicitante_nombre"],
            t["prioridad"], t["estado"], t["creado_en"][:16].replace("T", " "),
        ])
    tabla1 = Table(datos_abiertos, repeatRows=1)
    tabla1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D8192F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
    ]))
    elementos.append(tabla1)
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph(f"Tickets cerrados y tiempo de resolución ({len(cerrados)})", styles["Heading2"]))
    datos_cerrados = [["Folio", "Departamento", "Solicitante", "Creado", "Cerrado", "Horas"]]
    for t in cerrados:
        creado = dt.fromisoformat(t["creado_en"])
        resuelto = dt.fromisoformat(t["resuelto_en"])
        horas = round((resuelto - creado).total_seconds() / 3600, 1)
        datos_cerrados.append([
            t["folio"], t["departamento"], t["solicitante_nombre"],
            t["creado_en"][:16].replace("T", " "), t["resuelto_en"][:16].replace("T", " "), str(horas),
        ])
    tabla2 = Table(datos_cerrados, repeatRows=1)
    tabla2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#74767A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
    ]))
    elementos.append(tabla2)

    doc.build(elementos)
    buffer.seek(0)

    from fastapi.responses import Response
    return Response(
        content=buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reporte_tickets_{dt.now().strftime('%Y%m%d')}.pdf"},
    )


# Sirve el frontend estático
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")
