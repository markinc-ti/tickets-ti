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


def _con_permisos(usuario: dict) -> dict:
    """Agrega al dict del usuario sus permisos vigentes (leídos frescos de la base,
    no del JWT) — solo aplica a administradores, que pueden tener restricciones especiales."""
    if usuario["rol"] == "admin":
        permisos = db.obtener_permisos_usuario(usuario["id"])
        usuario = {**usuario, **permisos}
    return usuario


def requiere_acceso_equipos(usuario: dict = Depends(requiere_staff)) -> dict:
    usuario = _con_permisos(usuario)
    if usuario["rol"] == "admin" and not usuario.get("acceso_equipos", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Equipos")
    return usuario


def requiere_admin_completo(usuario: dict = Depends(requiere_admin)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_administracion", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Administración")
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


class CambiarMiContrasena(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=6)


@app.post("/api/auth/cambiar-password")
def cambiar_mi_password(payload: CambiarMiContrasena, usuario: dict = Depends(auth.get_current_user)):
    registro = db.obtener_usuario_por_username(usuario["username"])
    if not registro or not auth.verificar_password(payload.password_actual, registro["password_hash"]):
        raise HTTPException(status_code=401, detail="Tu contraseña actual no es correcta")
    db.actualizar_usuario(usuario["id"], password=payload.password_nueva)
    return {"ok": True}


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


class ClonarEmpresa(BaseModel):
    nombre_nueva_empresa: str = Field(min_length=1, max_length=120)
    sufijo_usuarios: str = Field(min_length=1, max_length=20, pattern=r"^[a-zA-Z0-9_-]+$")


@app.get("/api/empresas/{empresa_id}/respaldo")
def respaldo_empresa(empresa_id: int, _: dict = Depends(requiere_superadmin)):
    datos = db.exportar_empresa(empresa_id)
    if not datos:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    import json
    from datetime import datetime as dt

    contenido = json.dumps(datos, indent=2, ensure_ascii=False, default=str)
    nombre_archivo = f"respaldo_{datos['empresa']['nombre'].replace(' ', '_')}_{dt.now().strftime('%Y%m%d')}.json"
    return Response(
        content=contenido, media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


@app.post("/api/empresas/{empresa_id}/clonar")
def clonar_empresa(empresa_id: int, payload: ClonarEmpresa, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    resultado = db.clonar_empresa(empresa_id, payload.nombre_nueva_empresa.strip(), payload.sufijo_usuarios.strip())
    if not resultado:
        raise HTTPException(status_code=400, detail="No se pudo clonar la empresa")
    return resultado


# ==================== META (para usuarios de una empresa) ====================

@app.get("/api/meta")
def meta(usuario: dict = Depends(requiere_empresa)):
    usuario = _con_permisos(usuario)
    empresa = db.obtener_empresa(usuario["empresa_id"])
    es_admin = usuario["rol"] == "admin"
    return {
        "estados": db.ESTADOS, "prioridades": db.PRIORIDADES, "roles": ["admin", "tecnico", "usuario"],
        "departamentos": [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])],
        "categorias": [c["nombre"] for c in db.listar_categorias(usuario["empresa_id"])],
        "empresa_nombre": empresa["nombre"] if empresa else "",
        "empresa_logo": empresa["logo_base64"] if empresa else None,
        "tipos_equipo": db.TIPOS_EQUIPO, "estados_equipo": db.ESTADOS_EQUIPO,
        "tipos_mantenimiento": db.TIPOS_MANTENIMIENTO, "frecuencias_mantenimiento": db.FRECUENCIAS_MANTENIMIENTO,
        "estados_proyecto": db.ESTADOS_PROYECTO,
        "mis_permisos": {
            "acceso_equipos": usuario.get("acceso_equipos", True) if es_admin else True,
            "acceso_administracion": usuario.get("acceso_administracion", True) if es_admin else False,
            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,
        },
    }


# ==================== USUARIOS (dentro de la empresa, admin) ====================

class NuevoUsuario(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6)
    nombre_completo: str = Field(min_length=1, max_length=120)
    rol: str
    telefono_whatsapp: Optional[str] = None
    puesto: Optional[str] = None


class ActualizacionUsuario(BaseModel):
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    telefono_whatsapp: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    puesto: Optional[str] = None
    restriccion_categoria: Optional[str] = None
    acceso_equipos: Optional[bool] = None
    acceso_administracion: Optional[bool] = None


@app.get("/api/usuarios")
def api_listar_usuarios(usuario: dict = Depends(requiere_admin_completo)):
    return db.listar_usuarios(usuario["empresa_id"])


@app.get("/api/usuarios/tecnicos")
def api_listar_tecnicos(usuario: dict = Depends(requiere_empresa)):
    return db.listar_tecnicos_activos(usuario["empresa_id"])


@app.get("/api/usuarios/todos")
def api_listar_usuarios_activos(usuario: dict = Depends(requiere_empresa)):
    return db.listar_usuarios_activos(usuario["empresa_id"])


@app.post("/api/usuarios")
def api_crear_usuario(payload: NuevoUsuario, admin: dict = Depends(requiere_admin_completo)):
    if payload.rol not in ("admin", "tecnico", "usuario"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.obtener_usuario_por_username(payload.username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    uid = db.crear_usuario(admin["empresa_id"], payload.username, payload.password, payload.nombre_completo,
                            payload.rol, payload.telefono_whatsapp, payload.puesto)
    return {"id": uid}


@app.patch("/api/usuarios/{usuario_id}")
def api_actualizar_usuario(usuario_id: int, payload: ActualizacionUsuario, admin: dict = Depends(requiere_admin_completo)):
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if payload.rol and payload.rol not in ("admin", "tecnico", "usuario"):
        raise HTTPException(status_code=400, detail="Rol inválido")

    enviados = payload.dict(exclude_unset=True)
    kwargs_restriccion = {}
    if "restriccion_categoria" in enviados:
        kwargs_restriccion["restriccion_categoria"] = payload.restriccion_categoria  # puede ser None para quitarla

    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,
                           payload.activo, payload.password, payload.puesto,
                           acceso_equipos=payload.acceso_equipos, acceso_administracion=payload.acceso_administracion,
                           **kwargs_restriccion)
    return {"ok": True}


@app.delete("/api/usuarios/{usuario_id}")
def api_eliminar_usuario(usuario_id: int, admin: dict = Depends(requiere_admin_completo)):
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
def api_listar_departamentos(usuario: dict = Depends(requiere_admin_completo)):
    return db.listar_departamentos(usuario["empresa_id"], solo_activos=False)


@app.post("/api/departamentos")
def api_crear_departamento(payload: NuevoNombre, usuario: dict = Depends(requiere_admin_completo)):
    try:
        db.crear_departamento(usuario["empresa_id"], payload.nombre.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Ese departamento ya existe")
    return {"ok": True}


@app.patch("/api/departamentos/{depto_id}")
def api_cambiar_estado_departamento(depto_id: int, payload: CambioEstado, usuario: dict = Depends(requiere_admin_completo)):
    db.cambiar_estado_departamento(usuario["empresa_id"], depto_id, payload.activo)
    return {"ok": True}


@app.get("/api/categorias")
def api_listar_categorias(usuario: dict = Depends(requiere_admin_completo)):
    return db.listar_categorias(usuario["empresa_id"], solo_activos=False)


@app.post("/api/categorias")
def api_crear_categoria(payload: NuevoNombre, usuario: dict = Depends(requiere_admin_completo)):
    try:
        db.crear_categoria(usuario["empresa_id"], payload.nombre.strip().lower())
    except Exception:
        raise HTTPException(status_code=400, detail="Esa categoría ya existe")
    return {"ok": True}


@app.patch("/api/categorias/{cat_id}")
def api_cambiar_estado_categoria(cat_id: int, payload: CambioEstado, usuario: dict = Depends(requiere_admin_completo)):
    db.cambiar_estado_categoria(usuario["empresa_id"], cat_id, payload.activo)
    return {"ok": True}


class AsignarTecnicoCategoria(BaseModel):
    tecnico_id: Optional[int] = None  # None quita la auto-asignación


@app.patch("/api/categorias/{cat_id}/tecnico")
def api_asignar_tecnico_categoria(cat_id: int, payload: AsignarTecnicoCategoria, usuario: dict = Depends(requiere_admin_completo)):
    if payload.tecnico_id:
        tecnicos_validos = {t["id"] for t in db.listar_tecnicos_activos(usuario["empresa_id"])}
        if payload.tecnico_id not in tecnicos_validos:
            raise HTTPException(status_code=400, detail="Ese técnico no existe o no está activo en tu empresa")
    db.asignar_tecnico_categoria(usuario["empresa_id"], cat_id, payload.tecnico_id)
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


def _puede_ver_ticket(usuario, ticket):
    if usuario["rol"] == "usuario":
        return ticket["solicitante_id"] == usuario["id"]
    if usuario["rol"] == "tecnico":
        return ticket["asignado_a_id"] == usuario["id"]
    if usuario["rol"] == "admin":
        restriccion = usuario.get("restriccion_categoria")
        if restriccion:
            return ticket["categoria"] == restriccion
        return True
    return True


@app.get("/api/tickets")
def api_listar_tickets(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
                        departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                        tecnico_id: Optional[int] = None, usuario: dict = Depends(requiere_empresa)):
    usuario = _con_permisos(usuario)
    solicitante_id = usuario["id"] if usuario["rol"] == "usuario" else None
    asignado_a_id = usuario["id"] if usuario["rol"] == "tecnico" else tecnico_id
    if usuario["rol"] == "admin" and usuario.get("restriccion_categoria"):
        categoria = usuario["restriccion_categoria"]  # se impone, ignora lo que haya mandado el cliente
    return db.listar_tickets(usuario["empresa_id"], estado, prioridad, categoria, solicitante_id,
                              departamento, fecha_desde, fecha_hasta, asignado_a_id)


# IMPORTANTE: esta ruta va ANTES de /api/tickets/{ticket_id} — FastAPI
# revisa las rutas en orden, y si {ticket_id} fuera primero,
# "reporte.pdf" se interpretaría como un intento de ticket_id (numérico)
# y fallaría con 422 antes de llegar aquí.
@app.get("/api/tickets/reporte.pdf")
def reporte_pdf(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
                 departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                 tecnico_id: Optional[int] = None, usuario: dict = Depends(requiere_staff)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    usuario = _con_permisos(usuario)
    asignado_a_id = usuario["id"] if usuario["rol"] == "tecnico" else tecnico_id
    if usuario["rol"] == "admin" and usuario.get("restriccion_categoria"):
        categoria = usuario["restriccion_categoria"]
    todos = db.listar_tickets(usuario["empresa_id"], estado, prioridad, categoria, None,
                               departamento, fecha_desde, fecha_hasta, asignado_a_id)
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
    usuario = _con_permisos(usuario)
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _puede_ver_ticket(usuario, ticket):
        raise HTTPException(status_code=403, detail="No puedes ver este ticket")
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
    if ticket.get("asignado_a_id"):
        tecnico_asignado = next((t for t in tecnicos if t["id"] == ticket["asignado_a_id"]), None)
        if tecnico_asignado:
            notifications.notificar_asignacion(tecnico_asignado, ticket)
    return ticket


@app.patch("/api/tickets/{ticket_id}")
def api_actualizar_ticket(ticket_id: int, payload: ActualizacionTicket, usuario: dict = Depends(requiere_staff)):
    usuario = _con_permisos(usuario)
    ticket_antes = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket_antes:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _puede_ver_ticket(usuario, ticket_antes):
        raise HTTPException(status_code=403, detail="No puedes modificar este ticket")
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
    usuario = _con_permisos(usuario)
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _puede_ver_ticket(usuario, ticket):
        raise HTTPException(status_code=403, detail="No puedes comentar este ticket")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    return db.agregar_comentario(ticket_id, usuario["id"], payload.texto,
                                  payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)


@app.post("/api/tickets/{ticket_id}/firmar")
def api_firmar(ticket_id: int, payload: NuevaFirma, usuario: dict = Depends(requiere_staff)):
    usuario = _con_permisos(usuario)
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _puede_ver_ticket(usuario, ticket):
        raise HTTPException(status_code=403, detail="No puedes firmar este ticket")
    if ticket["estado"] == "cerrado":
        raise HTTPException(status_code=400, detail="Este ticket ya está cerrado")
    return db.firmar_ticket(ticket_id, payload.firma, payload.firmado_por.strip())


@app.get("/api/stats")
def api_stats(usuario: dict = Depends(requiere_staff)):
    usuario = _con_permisos(usuario)
    asignado_a_id = usuario["id"] if usuario["rol"] == "tecnico" else None
    categoria = usuario.get("restriccion_categoria") if usuario["rol"] == "admin" else None
    return db.estadisticas(usuario["empresa_id"], asignado_a_id, categoria)


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
def api_listar_equipos(tipo: Optional[str] = None, estado: Optional[str] = None, usuario: dict = Depends(requiere_acceso_equipos)):
    return db.listar_equipos(usuario["empresa_id"], tipo, estado)


def _agrupar_equipos_por_departamento(equipos):
    grupos = {}
    for e in equipos:
        depto = e.get("departamento") or "Sin departamento"
        grupos.setdefault(depto, []).append(e)
    return dict(sorted(grupos.items()))


NOMBRES_TIPO_EQUIPO = {
    "computadora": "Computadora", "laptop": "Laptop", "impresora": "Impresora",
    "monitor": "Monitor", "servidor": "Servidor", "red": "Red", "otro": "Otro",
}
NOMBRES_ESTADO_EQUIPO = {"activo": "Activo", "en_reparacion": "En reparación", "baja": "Baja"}


@app.get("/api/equipos/reporte.pdf")
def reporte_equipos_pdf(usuario: dict = Depends(requiere_acceso_equipos)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    equipos = db.listar_equipos(usuario["empresa_id"])
    grupos = _agrupar_equipos_por_departamento(equipos)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph(f"Inventario de equipos por departamento — {empresa['nombre'] if empresa else ''}", styles["Title"]))
    elementos.append(Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')} — {len(equipos)} equipos activos", styles["Normal"]))
    elementos.append(Spacer(1, 16))

    for depto, items in grupos.items():
        elementos.append(Paragraph(f"{depto} ({len(items)})", styles["Heading2"]))
        datos = [["Nombre", "Tipo", "Marca/Modelo", "N° Serie", "Responsable", "Estado"]]
        for e in items:
            datos.append([
                e["nombre"], NOMBRES_TIPO_EQUIPO.get(e["tipo"], e["tipo"]),
                " / ".join(filter(None, [e.get("marca"), e.get("modelo")])) or "—",
                e.get("numero_serie") or "—", e.get("responsable") or "—",
                NOMBRES_ESTADO_EQUIPO.get(e["estado"], e["estado"]),
            ])
        tabla = Table(datos, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D8192F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ]))
        elementos.append(tabla)
        elementos.append(Spacer(1, 18))

    if not equipos:
        elementos.append(Paragraph("No hay equipos registrados en el inventario.", styles["Normal"]))

    doc.build(elementos)
    buffer.seek(0)

    nombre_archivo = f"inventario_equipos_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


@app.get("/api/equipos/reporte.xlsx")
def reporte_equipos_xlsx(usuario: dict = Depends(requiere_acceso_equipos)):
    from io import BytesIO
    from datetime import datetime as dt

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    empresa = db.obtener_empresa(usuario["empresa_id"])
    equipos = db.listar_equipos(usuario["empresa_id"])
    grupos = _agrupar_equipos_por_departamento(equipos)

    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"

    encabezados = ["Departamento", "Nombre", "Tipo", "Marca", "Modelo", "N° Serie", "Responsable", "Estado", "Fecha adquisición", "Notas"]
    ws.append(encabezados)
    for col_idx, _ in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="D8192F", end_color="D8192F", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    fila = 2
    for depto, items in grupos.items():
        for e in items:
            ws.append([
                depto, e["nombre"], NOMBRES_TIPO_EQUIPO.get(e["tipo"], e["tipo"]),
                e.get("marca") or "", e.get("modelo") or "", e.get("numero_serie") or "",
                e.get("responsable") or "", NOMBRES_ESTADO_EQUIPO.get(e["estado"], e["estado"]),
                (e.get("fecha_adquisicion") or "")[:10], e.get("notas") or "",
            ])
            fila += 1

    for col_idx, encabezado in enumerate(encabezados, start=1):
        ancho = max(len(encabezado), 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = ancho + 4

    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"inventario_equipos_{dt.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


@app.post("/api/equipos")
def api_crear_equipo(payload: NuevoEquipo, usuario: dict = Depends(requiere_acceso_equipos)):
    if payload.tipo not in db.TIPOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Tipo de equipo inválido")
    return db.crear_equipo(usuario["empresa_id"], payload.tipo, payload.nombre, payload.marca, payload.modelo,
                            payload.numero_serie, payload.departamento, payload.responsable,
                            payload.fecha_adquisicion, payload.notas)


@app.patch("/api/equipos/{equipo_id}")
def api_actualizar_equipo(equipo_id: int, payload: ActualizacionEquipo, usuario: dict = Depends(requiere_acceso_equipos)):
    if not db.obtener_equipo(usuario["empresa_id"], equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if payload.tipo and payload.tipo not in db.TIPOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Tipo de equipo inválido")
    if payload.estado and payload.estado not in db.ESTADOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Estado de equipo inválido")
    return db.actualizar_equipo(usuario["empresa_id"], equipo_id, **payload.dict(exclude_unset=True))


@app.delete("/api/equipos/{equipo_id}")
def api_dar_de_baja_equipo(equipo_id: int, usuario: dict = Depends(requiere_acceso_equipos)):
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
                               usuario: dict = Depends(requiere_acceso_equipos)):
    return db.listar_mantenimientos(usuario["empresa_id"], estado, equipo_id)


@app.post("/api/mantenimientos")
def api_crear_mantenimiento(payload: NuevoMantenimiento, usuario: dict = Depends(requiere_acceso_equipos)):
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
def api_marcar_realizado(mantenimiento_id: int, payload: MarcarRealizado, usuario: dict = Depends(requiere_acceso_equipos)):
    resultado = db.marcar_mantenimiento_realizado(usuario["empresa_id"], mantenimiento_id, payload.realizado_por, payload.notas)
    if not resultado:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado")
    return resultado


@app.patch("/api/mantenimientos/{mantenimiento_id}")
def api_reprogramar_mantenimiento(mantenimiento_id: int, payload: ReprogramarMantenimiento, usuario: dict = Depends(requiere_acceso_equipos)):
    if payload.frecuencia and payload.frecuencia not in db.FRECUENCIAS_MANTENIMIENTO:
        raise HTTPException(status_code=400, detail="Frecuencia inválida")
    db.reprogramar_mantenimiento(usuario["empresa_id"], mantenimiento_id, payload.fecha_programada,
                                  payload.descripcion, payload.frecuencia)
    return {"ok": True}


@app.delete("/api/mantenimientos/{mantenimiento_id}")
def api_eliminar_mantenimiento(mantenimiento_id: int, usuario: dict = Depends(requiere_acceso_equipos)):
    db.eliminar_mantenimiento(usuario["empresa_id"], mantenimiento_id)
    return {"ok": True}


# ==================== PROYECTOS ====================

class NuevoProyecto(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    descripcion: Optional[str] = None
    fecha_estimada: Optional[str] = None
    participantes_usuarios: Optional[list[int]] = None
    participantes_departamentos: Optional[list[str]] = None


class ActualizacionProyecto(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_estimada: Optional[str] = None


class CambioEstadoProyecto(BaseModel):
    estado: str


class NuevoParticipanteUsuario(BaseModel):
    usuario_id: int


class NuevoParticipanteDepartamento(BaseModel):
    departamento: str


class NuevaActualizacionProyecto(BaseModel):
    texto: str = Field(min_length=1)
    archivo_base64: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tipo: Optional[str] = None


def _puede_ver_proyecto(usuario, proyecto):
    if usuario["rol"] == "admin":
        return True
    return any(p["id"] == usuario["id"] for p in proyecto["participantes_usuarios"])


@app.get("/api/proyectos")
def api_listar_proyectos(estado: Optional[str] = None, usuario: dict = Depends(requiere_empresa)):
    participante_id = usuario["id"] if usuario["rol"] in ("usuario", "tecnico") else None
    return db.listar_proyectos(usuario["empresa_id"], participante_id, estado)


@app.post("/api/proyectos")
def api_crear_proyecto(payload: NuevoProyecto, usuario: dict = Depends(requiere_staff)):
    participantes_usuarios = list(payload.participantes_usuarios or [])
    if usuario["rol"] == "tecnico" and usuario["id"] not in participantes_usuarios:
        participantes_usuarios.append(usuario["id"])  # para que quien lo crea siempre lo pueda ver después
    proyecto_id = db.crear_proyecto(
        usuario["empresa_id"], payload.nombre, payload.descripcion, payload.fecha_estimada, usuario["id"],
        participantes_usuarios, payload.participantes_departamentos,
    )
    return {"id": proyecto_id}


@app.get("/api/proyectos/{proyecto_id}")
def api_detalle_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_empresa)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    return proyecto


@app.patch("/api/proyectos/{proyecto_id}")
def api_actualizar_proyecto(proyecto_id: int, payload: ActualizacionProyecto, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.actualizar_proyecto(usuario["empresa_id"], proyecto_id, payload.nombre, payload.descripcion, payload.fecha_estimada)
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/iniciar")
def api_iniciar_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.iniciar_proyecto(usuario["empresa_id"], proyecto_id)
    return {"ok": True}


@app.patch("/api/proyectos/{proyecto_id}/estado")
def api_cambiar_estado_proyecto(proyecto_id: int, payload: CambioEstadoProyecto, usuario: dict = Depends(requiere_staff)):
    if payload.estado not in db.ESTADOS_PROYECTO:
        raise HTTPException(status_code=400, detail="Estado inválido")
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.cambiar_estado_proyecto(usuario["empresa_id"], proyecto_id, payload.estado)
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/participantes/usuarios")
def api_agregar_participante_usuario(proyecto_id: int, payload: NuevoParticipanteUsuario, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.agregar_participante_usuario(proyecto_id, payload.usuario_id)
    return {"ok": True}


@app.delete("/api/proyectos/{proyecto_id}/participantes/usuarios/{usuario_id}")
def api_quitar_participante_usuario(proyecto_id: int, usuario_id: int, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.quitar_participante_usuario(proyecto_id, usuario_id)
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/participantes/departamentos")
def api_agregar_participante_departamento(proyecto_id: int, payload: NuevoParticipanteDepartamento, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.agregar_participante_departamento(proyecto_id, payload.departamento)
    return {"ok": True}


@app.delete("/api/proyectos/{proyecto_id}/participantes/departamentos/{departamento}")
def api_quitar_participante_departamento(proyecto_id: int, departamento: str, usuario: dict = Depends(requiere_staff)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.quitar_participante_departamento(proyecto_id, departamento)
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/actualizaciones")
def api_comentar_proyecto(proyecto_id: int, payload: NuevaActualizacionProyecto, usuario: dict = Depends(requiere_empresa)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    db.agregar_actualizacion_proyecto(proyecto_id, usuario["id"], payload.texto,
                                       payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


# ==================== FRONTEND ESTÁTICO ====================

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")
