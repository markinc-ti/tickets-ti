import os

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

import auth
import db
import notifications

db.init_db()

app = FastAPI(title="Tickets TI — Multiempresa")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Dependencias de autorización ----

def requiere_superadmin(usuario: dict = Depends(auth.get_current_user)) -> dict:
    if usuario["rol"] != "superadmin":
        raise HTTPException(status_code=403, detail="Solo el super administrador puede hacer esto")
    return usuario


def requiere_empresa(usuario: dict = Depends(auth.get_current_user)) -> dict:
    """Cualquier rol de una empresa (admin/tecnico/usuario), nunca superadmin."""
    if usuario["rol"] == "superadmin" or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Esta acción es solo para usuarios de una empresa")
    return usuario


def requiere_admin(usuario: dict = Depends(requiere_empresa)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador de tu empresa puede hacer esto")
    return usuario


def requiere_staff(usuario: dict = Depends(requiere_empresa)) -> dict:
    if usuario["rol"] not in ("admin", "tecnico"):
        raise HTTPException(status_code=403, detail="No tienes permiso para hacer esto")
    return usuario


# ==================== AUTENTICACIÓN ====================

class LoginPayload(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    usuario = db.obtener_usuario_por_username(payload.username)
    if not usuario or not usuario["activo"] or not auth.verificar_password(payload.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = auth.crear_token(usuario)
    return {
        "token": token,
        "usuario": {
            "id": usuario["id"], "username": usuario["username"],
            "nombre": usuario["nombre_completo"], "rol": usuario["rol"],
            "empresa_id": usuario["empresa_id"],
        },
    }


@app.get("/api/auth/me")
def me(usuario: dict = Depends(auth.get_current_user)):
    return usuario


# ==================== EMPRESAS (superadmin) ====================

class NuevaEmpresa(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    admin_username: str = Field(min_length=3, max_length=40)
    admin_password: str = Field(min_length=6)
    admin_nombre: str = Field(min_length=1, max_length=120)


class ActualizacionEmpresa(BaseModel):
    nombre: Optional[str] = None
    activo: Optional[bool] = None


class NuevoLogo(BaseModel):
    logo_base64: str = Field(min_length=100)


@app.get("/api/empresas")
def listar_empresas(_: dict = Depends(requiere_superadmin)):
    return db.listar_empresas()


@app.post("/api/empresas")
def crear_empresa(payload: NuevaEmpresa, _: dict = Depends(requiere_superadmin)):
    if db.obtener_usuario_por_username(payload.admin_username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    empresa_id = db.crear_empresa(payload.nombre.strip(), payload.admin_username.strip(), payload.admin_password, payload.admin_nombre.strip())
    return db.obtener_empresa(empresa_id)


@app.patch("/api/empresas/{empresa_id}")
def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo)
    return db.obtener_empresa(empresa_id)


@app.post("/api/empresas/{empresa_id}/logo")
def subir_logo(empresa_id: int, payload: NuevoLogo, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.actualizar_logo_empresa(empresa_id, payload.logo_base64)
    return db.obtener_empresa(empresa_id)


# ==================== META (para usuarios de una empresa) ====================

@app.get("/api/meta")
def meta(usuario: dict = Depends(requiere_empresa)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    return {
        "estados": db.ESTADOS, "prioridades": db.PRIORIDADES, "roles": ["admin", "tecnico", "usuario"],
        "departamentos": [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])],
        "categorias": [c["nombre"] for c in db.listar_categorias(usuario["empresa_id"])],
        "empresa_nombre": empresa["nombre"] if empresa else "",
        "empresa_logo": empresa["logo_base64"] if empresa else None,
        "tipos_equipo": db.TIPOS_EQUIPO, "estados_equipo": db.ESTADOS_EQUIPO,
        "tipos_mantenimiento": db.TIPOS_MANTENIMIENTO, "frecuencias_mantenimiento": db.FRECUENCIAS_MANTENIMIENTO,
    }


# ==================== USUARIOS (dentro de la empresa, admin) ====================

class NuevoUsuario(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6)
    nombre_completo: str = Field(min_length=1, max_length=120)
    rol: str
    telefono_whatsapp: Optional[str] = None


class ActualizacionUsuario(BaseModel):
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    telefono_whatsapp: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)


@app.get("/api/usuarios")
def api_listar_usuarios(usuario: dict = Depends(requiere_admin)):
    return db.listar_usuarios(usuario["empresa_id"])


@app.get("/api/usuarios/tecnicos")
def api_listar_tecnicos(usuario: dict = Depends(requiere_empresa)):
    return db.listar_tecnicos_activos(usuario["empresa_id"])


@app.post("/api/usuarios")
def api_crear_usuario(payload: NuevoUsuario, admin: dict = Depends(requiere_admin)):
    if payload.rol not in ("admin", "tecnico", "usuario"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.obtener_usuario_por_username(payload.username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    uid = db.crear_usuario(admin["empresa_id"], payload.username, payload.password, payload.nombre_completo, payload.rol, payload.telefono_whatsapp)
    return {"id": uid}


@app.patch("/api/usuarios/{usuario_id}")
def api_actualizar_usuario(usuario_id: int, payload: ActualizacionUsuario, admin: dict = Depends(requiere_admin)):
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if payload.rol and payload.rol not in ("admin", "tecnico", "usuario"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp, payload.activo, payload.password)
    return {"ok": True}


@app.delete("/api/usuarios/{usuario_id}")
def api_eliminar_usuario(usuario_id: int, admin: dict = Depends(requiere_admin)):
    if usuario_id == admin["id"]:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    db.eliminar_usuario(usuario_id)
    return {"ok": True}


# ==================== DEPARTAMENTOS Y CATEGORÍAS (admin) ====================

class NuevoNombre(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)


class CambioEstado(BaseModel):
    activo: bool


@app.get("/api/departamentos")
def api_listar_departamentos(usuario: dict = Depends(requiere_admin)):
    return db.listar_departamentos(usuario["empresa_id"], solo_activos=False)


@app.post("/api/departamentos")
def api_crear_departamento(payload: NuevoNombre, usuario: dict = Depends(requiere_admin)):
    try:
        db.crear_departamento(usuario["empresa_id"], payload.nombre.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Ese departamento ya existe")
    return {"ok": True}


@app.patch("/api/departamentos/{depto_id}")
def api_cambiar_estado_departamento(depto_id: int, payload: CambioEstado, usuario: dict = Depends(requiere_admin)):
    db.cambiar_estado_departamento(usuario["empresa_id"], depto_id, payload.activo)
    return {"ok": True}


@app.get("/api/categorias")
def api_listar_categorias(usuario: dict = Depends(requiere_admin)):
    return db.listar_categorias(usuario["empresa_id"], solo_activos=False)


@app.post("/api/categorias")
def api_crear_categoria(payload: NuevoNombre, usuario: dict = Depends(requiere_admin)):
    try:
        db.crear_categoria(usuario["empresa_id"], payload.nombre.strip().lower())
    except Exception:
        raise HTTPException(status_code=400, detail="Esa categoría ya existe")
    return {"ok": True}


@app.patch("/api/categorias/{cat_id}")
def api_cambiar_estado_categoria(cat_id: int, payload: CambioEstado, usuario: dict = Depends(requiere_admin)):
    db.cambiar_estado_categoria(usuario["empresa_id"], cat_id, payload.activo)
    return {"ok": True}


# ==================== TICKETS ====================

class NuevoTicket(BaseModel):
    departamento: str
    descripcion: str = Field(min_length=3)
    categoria: str
    prioridad: str = "media"


class ActualizacionTicket(BaseModel):
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    asignado_a_id: Optional[int] = None


class NuevoComentario(BaseModel):
    texto: str = Field(min_length=1)
    archivo_base64: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tipo: Optional[str] = None


class NuevaFirma(BaseModel):
    firma: str = Field(min_length=100)
    firmado_por: str = Field(min_length=1, max_length=120)


@app.get("/api/tickets")
def api_listar_tickets(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
                        departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                        usuario: dict = Depends(requiere_empresa)):
    solicitante_id = usuario["id"] if usuario["rol"] == "usuario" else None
    return db.listar_tickets(usuario["empresa_id"], estado, prioridad, categoria, solicitante_id,
                              departamento, fecha_desde, fecha_hasta)


# IMPORTANTE: esta ruta va ANTES de /api/tickets/{ticket_id} — FastAPI
# revisa las rutas en orden, y si {ticket_id} fuera primero,
# "reporte.pdf" se interpretaría como un intento de ticket_id (numérico)
# y fallaría con 422 antes de llegar aquí.
@app.get("/api/tickets/reporte.pdf")
def reporte_pdf(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
                 departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                 usuario: dict = Depends(requiere_staff)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    todos = db.listar_tickets(usuario["empresa_id"], estado, prioridad, categoria, None,
                               departamento, fecha_desde, fecha_hasta)
    abiertos = [t for t in todos if t["estado"] in ("abierto", "en_progreso")]
    cerrados = [t for t in todos if t["estado"] in ("resuelto", "cerrado") and t.get("resuelto_en")]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph(f"Reporte de tickets — {empresa['nombre'] if empresa else ''}", styles["Title"]))
    if fecha_desde or fecha_hasta:
        rango = f"Del {fecha_desde or '…'} al {fecha_hasta or '…'}"
        elementos.append(Paragraph(rango, styles["Normal"]))
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

    nombre_archivo = f"reporte_tickets_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


@app.get("/api/tickets/{ticket_id}")
def api_detalle_ticket(ticket_id: int, usuario: dict = Depends(requiere_empresa)):
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if usuario["rol"] == "usuario" and ticket["solicitante_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver tickets de otras personas")
    return ticket


@app.post("/api/tickets")
def api_crear_ticket(payload: NuevoTicket, usuario: dict = Depends(requiere_empresa)):
    departamentos_validos = {d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])}
    categorias_validas = {c["nombre"] for c in db.listar_categorias(usuario["empresa_id"])}
    if payload.departamento not in departamentos_validos:
        raise HTTPException(status_code=400, detail="Departamento inválido")
    if payload.categoria not in categorias_validas:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    ticket = db.crear_ticket(usuario["empresa_id"], payload.departamento, payload.descripcion, payload.categoria, payload.prioridad, usuario["id"])
    tecnicos = db.listar_tecnicos_activos(usuario["empresa_id"])
    notifications.notificar_nuevo_ticket(tecnicos, ticket)
    return ticket


@app.patch("/api/tickets/{ticket_id}")
def api_actualizar_ticket(ticket_id: int, payload: ActualizacionTicket, usuario: dict = Depends(requiere_staff)):
    ticket_antes = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket_antes:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if payload.estado and payload.estado not in db.ESTADOS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    if payload.prioridad and payload.prioridad not in db.PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    ticket = db.actualizar_ticket(ticket_id, payload.estado, payload.prioridad, payload.asignado_a_id)

    if payload.asignado_a_id and payload.asignado_a_id != ticket_antes.get("asignado_a_id"):
        tecnico = next((t for t in db.listar_tecnicos_activos(usuario["empresa_id"]) if t["id"] == payload.asignado_a_id), None)
        if tecnico:
            notifications.notificar_asignacion(tecnico, ticket)

    return ticket


MAX_ADJUNTO_BASE64 = 7_000_000  # ~5MB de archivo real (base64 pesa ~33% más)


@app.post("/api/tickets/{ticket_id}/comentarios")
def api_comentar(ticket_id: int, payload: NuevoComentario, usuario: dict = Depends(requiere_empresa)):
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if usuario["rol"] == "usuario" and ticket["solicitante_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes comentar tickets de otras personas")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    return db.agregar_comentario(ticket_id, usuario["id"], payload.texto,
                                  payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)


@app.post("/api/tickets/{ticket_id}/firmar")
def api_firmar(ticket_id: int, payload: NuevaFirma, usuario: dict = Depends(requiere_staff)):
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if ticket["estado"] == "cerrado":
        raise HTTPException(status_code=400, detail="Este ticket ya está cerrado")
    return db.firmar_ticket(ticket_id, payload.firma, payload.firmado_por.strip())


@app.get("/api/stats")
def api_stats(usuario: dict = Depends(requiere_staff)):
    return db.estadisticas(usuario["empresa_id"])


# ==================== EQUIPOS (inventario) ====================

class NuevoEquipo(BaseModel):
    tipo: str
    nombre: str = Field(min_length=1, max_length=120)
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    departamento: Optional[str] = None
    responsable: Optional[str] = None
    fecha_adquisicion: Optional[str] = None
    notas: Optional[str] = None


class ActualizacionEquipo(BaseModel):
    tipo: Optional[str] = None
    nombre: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    departamento: Optional[str] = None
    responsable: Optional[str] = None
    estado: Optional[str] = None
    fecha_adquisicion: Optional[str] = None
    notas: Optional[str] = None


@app.get("/api/equipos")
def api_listar_equipos(tipo: Optional[str] = None, estado: Optional[str] = None, usuario: dict = Depends(requiere_staff)):
    return db.listar_equipos(usuario["empresa_id"], tipo, estado)


@app.post("/api/equipos")
def api_crear_equipo(payload: NuevoEquipo, usuario: dict = Depends(requiere_staff)):
    if payload.tipo not in db.TIPOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Tipo de equipo inválido")
    return db.crear_equipo(usuario["empresa_id"], payload.tipo, payload.nombre, payload.marca, payload.modelo,
                            payload.numero_serie, payload.departamento, payload.responsable,
                            payload.fecha_adquisicion, payload.notas)


@app.patch("/api/equipos/{equipo_id}")
def api_actualizar_equipo(equipo_id: int, payload: ActualizacionEquipo, usuario: dict = Depends(requiere_staff)):
    if not db.obtener_equipo(usuario["empresa_id"], equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if payload.tipo and payload.tipo not in db.TIPOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Tipo de equipo inválido")
    if payload.estado and payload.estado not in db.ESTADOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Estado de equipo inválido")
    return db.actualizar_equipo(usuario["empresa_id"], equipo_id, **payload.dict(exclude_unset=True))


@app.delete("/api/equipos/{equipo_id}")
def api_dar_de_baja_equipo(equipo_id: int, usuario: dict = Depends(requiere_staff)):
    if not db.obtener_equipo(usuario["empresa_id"], equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    db.dar_de_baja_equipo(usuario["empresa_id"], equipo_id)
    return {"ok": True}


# ==================== MANTENIMIENTOS PROGRAMADOS ====================

class NuevoMantenimiento(BaseModel):
    equipo_id: int
    tipo: str = "preventivo"
    descripcion: str = Field(min_length=1)
    fecha_programada: str
    frecuencia: str = "unica"
    notas: Optional[str] = None
    tecnico_asignado_id: Optional[int] = None


class MarcarRealizado(BaseModel):
    realizado_por: str = Field(min_length=1, max_length=120)
    notas: Optional[str] = None


class ReprogramarMantenimiento(BaseModel):
    fecha_programada: Optional[str] = None
    descripcion: Optional[str] = None
    frecuencia: Optional[str] = None


@app.get("/api/mantenimientos")
def api_listar_mantenimientos(estado: Optional[str] = None, equipo_id: Optional[int] = None,
                               usuario: dict = Depends(requiere_staff)):
    return db.listar_mantenimientos(usuario["empresa_id"], estado, equipo_id)


@app.post("/api/mantenimientos")
def api_crear_mantenimiento(payload: NuevoMantenimiento, usuario: dict = Depends(requiere_staff)):
    if not db.obtener_equipo(usuario["empresa_id"], payload.equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if payload.tipo not in db.TIPOS_MANTENIMIENTO:
        raise HTTPException(status_code=400, detail="Tipo de mantenimiento inválido")
    if payload.frecuencia not in db.FRECUENCIAS_MANTENIMIENTO:
        raise HTTPException(status_code=400, detail="Frecuencia inválida")
    mant_id = db.crear_mantenimiento(usuario["empresa_id"], payload.equipo_id, payload.tipo, payload.descripcion,
                                      payload.fecha_programada, payload.frecuencia, payload.notas,
                                      tecnico_asignado_id=payload.tecnico_asignado_id, creado_por_id=usuario["id"])
    return {"id": mant_id}


@app.post("/api/mantenimientos/{mantenimiento_id}/realizar")
def api_marcar_realizado(mantenimiento_id: int, payload: MarcarRealizado, usuario: dict = Depends(requiere_staff)):
    resultado = db.marcar_mantenimiento_realizado(usuario["empresa_id"], mantenimiento_id, payload.realizado_por, payload.notas)
    if not resultado:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado")
    return resultado


@app.patch("/api/mantenimientos/{mantenimiento_id}")
def api_reprogramar_mantenimiento(mantenimiento_id: int, payload: ReprogramarMantenimiento, usuario: dict = Depends(requiere_staff)):
    if payload.frecuencia and payload.frecuencia not in db.FRECUENCIAS_MANTENIMIENTO:
        raise HTTPException(status_code=400, detail="Frecuencia inválida")
    db.reprogramar_mantenimiento(usuario["empresa_id"], mantenimiento_id, payload.fecha_programada,
                                  payload.descripcion, payload.frecuencia)
    return {"ok": True}


@app.delete("/api/mantenimientos/{mantenimiento_id}")
def api_eliminar_mantenimiento(mantenimiento_id: int, usuario: dict = Depends(requiere_staff)):
    db.eliminar_mantenimiento(usuario["empresa_id"], mantenimiento_id)
    return {"ok": True}


# ==================== FRONTEND ESTÁTICO ====================

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")
