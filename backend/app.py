import base64
import json
import os
import re
import threading
import secrets
import sys
import unicodedata
import urllib.parse
import xml.sax.saxutils as xml_escape_util
from datetime import date, timedelta

import requests

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, Header, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict

import auth
import db
import geo
import geotab
import notifications
import pdfs_reparaciones
import pdfs_laboratorio
import pdfs_rh
import pdfs_equipos
import pdfs_cotizaciones
import calendario_ics
import importar_reparaciones
import ia
import asistente
import imagen_ia
import chatbot_whatsapp
import shopify_api
import dscore
import kommo_import
import r2
import whatsapp_meta
import direccion
import correo
import push_notifications
import avisos
import facturacion_flete
import estafeta
import paqueterias
import asistencia
try:
    import microsip
    import microsip_escritura
    import microsip_usuarios
    import microsip_lotes
    import microsip_vacaciones
    import microsip_inventario
    MICROSIP_DISPONIBLE = True
except ImportError:
    # El driver 'fdb' todavía no está en requirements.txt / instalado en el
    # servidor — no tronamos toda la app por esto, solo dejamos claro el
    # motivo si alguien intenta usar las rutas de Microsip mientras tanto.
    microsip = None
    MICROSIP_DISPONIBLE = False

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    APSCHEDULER_DISPONIBLE = True
except ImportError:
    # apscheduler todavía no está en requirements.txt / instalado en el
    # servidor — no tronamos toda la app por esto; la sincronización
    # automática de inventario simplemente no arranca hasta que se
    # instale (el botón manual sigue funcionando igual).
    APSCHEDULER_DISPONIBLE = False

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


def requiere_empresa_o_master(usuario: dict = Depends(auth.get_current_user)) -> dict:
    """Como requiere_empresa, pero sin excluir al rol 'master' — solo se usa en los
    dos endpoints a los que master sí tiene acceso: /api/meta y /api/dashboard."""
    if usuario["rol"] == "superadmin" or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Esta acción es solo para usuarios de una empresa")
    return usuario


def requiere_empresa(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:
    """Cualquier rol de una empresa EXCEPTO 'master' (solo Dashboard). El rol
    'almacen' YA NO está bloqueado de fondo aquí — por defecto solo tiene
    Reparaciones (como siempre), pero el administrador puede darle acceso a
    otros módulos desde Administrar → Accesos, igual que a cualquier otro rol."""
    if usuario["rol"] == "master":
        raise HTTPException(status_code=403, detail="Tu usuario solo tiene acceso al Dashboard")
    return usuario


def requiere_empresa_o_almacen(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:
    """Como requiere_empresa, pero también permite al rol 'almacen' — se usa solo en
    los endpoints de Reparaciones a los que un encargado de almacén sí tiene acceso
    (ver reparaciones y firmar la recepción en su propia sucursal)."""
    if usuario["rol"] == "master":
        raise HTTPException(status_code=403, detail="Tu usuario solo tiene acceso al Dashboard")
    return usuario


def requiere_dashboard(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:
    if usuario["rol"] not in ("admin", "master"):
        raise HTTPException(status_code=403, detail="No tienes acceso al Dashboard")
    if usuario["rol"] == "admin":
        usuario = _con_permisos(usuario)
        if not usuario.get("acceso_dashboard", True):
            raise HTTPException(status_code=403, detail="No tienes acceso al Dashboard")
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
    no del JWT) — aplica a cualquier rol de empresa, para que el administrador pueda
    restringir módulos a técnicos y empleados, igual que ya podía hacerlo consigo
    mismo entre distintos administradores.

    También aplica los módulos habilitados a nivel EMPRESA: si la empresa
    tiene un módulo apagado, nadie de ahí lo ve, sin importar su permiso
    individual — un segundo nivel de permiso, independiente del de cada
    usuario (útil porque no todas las empresas usan los mismos módulos)."""
    if usuario["rol"] in ("admin", "tecnico", "usuario", "almacen", "encargado_sucursal", "instalador"):
        permisos = db.obtener_permisos_usuario(usuario["id"])
        usuario = {**usuario, **permisos}
        modulos_empresa = db.obtener_modulos_empresa(usuario["empresa_id"])
        for clave_acceso, habilitado_en_empresa in modulos_empresa.items():
            if not habilitado_en_empresa:
                usuario[clave_acceso] = False
    return usuario


def requiere_acceso_equipos(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Antes exigía ser admin/técnico (requiere_staff). Ahora también deja pasar
    a 'almacen' si el administrador le dio el acceso — el rol 'usuario' (empleado)
    se sigue quedando fuera, igual que siempre."""
    if usuario["rol"] not in ("admin", "tecnico", "almacen"):
        raise HTTPException(status_code=403, detail="No tienes permiso para hacer esto")
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_equipos", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Equipos")
    return usuario


def requiere_acceso_compras(usuario: dict = Depends(requiere_staff)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_compras", True):
        raise HTTPException(status_code=403, detail="No tienes acceso a administrar Compras")
    return usuario


def requiere_admin_compras(usuario: dict = Depends(requiere_admin)) -> dict:
    """Exclusivo del administrador: catálogo de artículos (crear/editar/dar de baja)
    y programar ciclos de compra. El técnico ya no gestiona ninguno de los dos,
    solo puede pedir del catálogo como cualquier empleado."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_compras", True):
        raise HTTPException(status_code=403, detail="No tienes acceso a administrar Compras")
    return usuario


def requiere_admin_rh(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Aprobar o rechazar una incidencia de Recursos Humanos: lo puede hacer
    el administrador (con acceso a RH) o quien tenga el permiso exclusivo
    'Datos RH' — la encargada de RH, aunque no sea administrador."""
    usuario = _con_permisos(usuario)
    es_admin_con_rh = usuario["rol"] == "admin" and usuario.get("acceso_rh", True)
    es_encargada_rh = usuario.get("acceso_datos_empleado_rh", False)
    if not (es_admin_con_rh or es_encargada_rh):
        raise HTTPException(status_code=403, detail="No tienes acceso a administrar Recursos Humanos")
    return usuario


def requiere_rh_o_logistica(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Ver y revisar las checadas del Checador app (selfie + ubicación): RH como
    siempre, y también Logística, que revisa si checaron los choferes (David, 21 oct 2026).
    Registrar la foto de la cara sigue siendo solo de RH."""
    usuario = _con_permisos(usuario)
    es_rh = (usuario["rol"] == "admin" and usuario.get("acceso_rh", True)) or usuario.get("acceso_datos_empleado_rh", False)
    if not (es_rh or (usuario["rol"] != "master" and _es_departamento_logistica(usuario["id"]))):
        raise HTTPException(status_code=403, detail="No tienes acceso a las checadas del Checador app")
    return usuario


def requiere_rh_o_encargado_sucursal(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Puede registrar una incidencia directamente a nombre de otro empleado
    (para las que nunca se metieron a tiempo): quien tenga 'Datos RH', o el
    encargado de una sucursal (solo para gente de su propia sucursal,
    validado dentro del endpoint)."""
    usuario = _con_permisos(usuario)
    if not (usuario.get("acceso_datos_empleado_rh", False) or usuario["rol"] == "encargado_sucursal"):
        raise HTTPException(status_code=403, detail="No tienes permiso para registrar incidencias a nombre de otra persona")
    return usuario


def requiere_datos_empleado_rh(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Ver la ficha de empleado (salario, datos personales, vacaciones de
    Microsip) — permiso aparte del resto de RH, para poder dárselo SOLO
    a la persona encargada de RH, ni siquiera a otros administradores
    por default."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_datos_empleado_rh", False):
        raise HTTPException(status_code=403, detail="No tienes acceso a los datos de empleados")
    return usuario


def requiere_acceso_monitoreo(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Ver la bitácora de monitoreo de empleados (pestaña 🕵️ Monitoreo) —
    permiso aparte, para dárselo SOLO a quien deba verlo, ni siquiera a
    otros administradores por default (mismo patrón que 'Datos RH')."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_monitoreo", False):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Monitoreo")
    return usuario


def requiere_acceso_shopify(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_shopify", True):
        raise HTTPException(status_code=403, detail="No tienes acceso a Shopify")
    return usuario


def requiere_acceso_soporte(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Soporte técnico (Peymar): solo el área de soporte (permiso acceso_soporte) y
    solo si la empresa tiene el módulo encendido."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_soporte", False):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Soporte técnico")
    return usuario


def requiere_acceso_turnos(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_turnos", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Turnos")
    return usuario


def requiere_ver_compras(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Como requiere_acceso_compras, pero para las rutas que también usan técnicos y
    empleados (ver catálogo, ver ciclos, hacer un pedido) — ahora respeta la
    restricción configurada para CUALQUIER rol, no solo administrador."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_compras", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Compras")
    return usuario


def requiere_acceso_crm(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_crm", False):
        raise HTTPException(status_code=403, detail="No tienes acceso al CRM de Ventas")
    return usuario


def requiere_acceso_asistente(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_asistente_ia", False):
        raise HTTPException(status_code=403, detail="No tienes acceso al asistente de IA")
    return usuario


def requiere_ver_rh(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Igual que requiere_ver_compras, pero para Recursos Humanos: cualquier
    persona puede levantar su propia incidencia salvo que el administrador le
    haya quitado el acceso al módulo entero."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_rh", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Recursos Humanos")
    return usuario


def requiere_ver_tickets(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Igual que requiere_ver_compras/requiere_ver_rh, pero para el tablero de
    Tickets — el módulo por defecto, que ahora también se le puede quitar a
    cualquier persona desde Administrar → Usuarios."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_tickets", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Tickets")
    return usuario


def _es_departamento_logistica(usuario_id: int) -> bool:
    """True si la persona hace la Logística de reparaciones: tiene el acceso
    "Logística Rep." (Administrar → Accesos) o su sucursal tiene departamento
    "Logística" (sin importar mayúsculas ni acentos). Logística ve todas las
    reparaciones y hace revisión por calidad, listo para envío y la entrega
    al chofer."""
    # También cuenta quien tenga el acceso "Logística Rep." (Administrar → Accesos).
    return db.es_logistica_reparaciones(usuario_id)


def requiere_ver_reparaciones(usuario: dict = Depends(requiere_empresa_o_almacen)) -> dict:
    """Igual que requiere_ver_tickets, pero para Reparaciones. El rol 'almacen'
    siempre tiene acceso — es su único módulo, no se le puede quitar — los
    demás roles sí pueden perder este acceso desde Administrar → Accesos."""
    if usuario["rol"] == "almacen":
        return usuario
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_reparaciones", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Reparaciones")
    return usuario


def requiere_ver_proyectos(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Módulo Proyectos: se puede quitar por persona en Administrar → Accesos."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_proyectos", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Proyectos")
    return usuario


def _es_gestor_proyectos(usuario: dict) -> bool:
    """Quién crea y administra proyectos: administrador, técnico, o quien
    tenga el acceso "Admin. Proyectos" (Administrar → Accesos)."""
    return usuario.get("rol") in ("admin", "tecnico") or bool(usuario.get("admin_proyectos"))


def requiere_gestor_proyectos(usuario: dict = Depends(requiere_ver_proyectos)) -> dict:
    if not _es_gestor_proyectos(usuario):
        raise HTTPException(status_code=403, detail="Solo el administrador de proyectos puede hacer esto")
    return usuario


def requiere_ver_laboratorio(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Igual que requiere_ver_tickets/reparaciones, pero para Laboratorio."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_laboratorio", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Laboratorio")
    return usuario


def requiere_laboratorio_entrega(usuario: dict = Depends(requiere_ver_laboratorio)) -> dict:
    """Recibir de vuelta un trabajo en la sucursal y entregarlo al doctor/
    estudiante: solo admin, quien tenga el privilegio 'acceso_laboratorio_entrega'
    (se lo das a quien tú decidas, sin importar su rol), o el encargado de esa
    misma sucursal (se valida en el endpoint que sea SU sucursal)."""
    if usuario["rol"] == "admin" or usuario.get("acceso_laboratorio_entrega", False) or usuario["rol"] == "encargado_sucursal":
        return usuario
    raise HTTPException(status_code=403, detail="No tienes el privilegio para recibir o entregar trabajos de laboratorio")


def _es_usuario_laboratorio(usuario: dict) -> bool:
    """El usuario del LABORATORIO (dado de alta en la sucursal marcada como
    laboratorio) — es el único que confirma pagos reportados y mueve los
    estatus. El administrador también puede."""
    if usuario.get("rol") in ("admin", "superadmin"):
        return True
    sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
    return bool(sucursal_lab) and db.obtener_sucursal_id_usuario(usuario["id"]) == sucursal_lab["id"]


def _como_data_url(b64):
    """Las apps mandan el comprobante como base64 "pelón" (sin data:...) — se
    guarda como data URL para que el navegador lo pueda mostrar."""
    if not b64 or b64.startswith("data:"):
        return b64
    tipo = "image/png" if b64.startswith("iVBOR") else "application/pdf" if b64.startswith("JVBER") \
        else "image/webp" if b64.startswith("UklGR") else "image/heic" if b64[4:12] == "ZnR5cGhl" else "image/jpeg"
    return f"data:{tipo};base64,{b64}"


def requiere_no_ser_estudiante_laboratorio(usuario: dict = Depends(requiere_ver_laboratorio)) -> dict:
    """Varias acciones de Laboratorio (dar de alta desde mostrador, ver la
    lista completa, registrar pagos, firmar recepción) son solo para el
    personal -- un estudiante con su propio usuario (portal de estudiantes,
    Fase 1) tiene su propio flujo, limitado a lo suyo, en /api/laboratorio/mios."""
    if usuario["rol"] == "estudiante":
        raise HTTPException(status_code=403, detail="Esta acción es solo para el personal de la sucursal")
    return usuario


MENSAJE_ESTUDIANTE_BLOQUEADO = "Tu cuenta de estudiante está bloqueada. Comunícate con el laboratorio o acude a cualquiera de nuestras sucursales."
MENSAJE_ESTUDIANTE_VENCIDO = ("Tu vigencia como estudiante terminó. Actualiza tu información de estudiante en cualquiera "
                              "de nuestras sucursales para volver a entrar.")


def _motivo_bloqueo_estudiante(cuenta):
    """Texto a mostrar si el estudiante no puede usar el portal/app, o None."""
    if not cuenta:
        return "Tu cuenta no se encontró."
    if not cuenta.get("activo"):
        return MENSAJE_ESTUDIANTE_BLOQUEADO
    if cuenta.get("vigencia_estado") == "vencida":
        return MENSAJE_ESTUDIANTE_VENCIDO
    return None


def requiere_estudiante_laboratorio(usuario: dict = Depends(auth.get_current_user)) -> dict:
    """Para el portal propio del estudiante (Fase 1) -- mismo login/JWT que el
    resto de la app, pero solo deja pasar cuentas con rol 'estudiante'.
    También corta la sesión si el laboratorio lo bloqueó o se le acabó la
    vigencia (aunque su token siga siendo válido)."""
    if usuario["rol"] != "estudiante":
        raise HTTPException(status_code=403, detail="Esta acción es solo para cuentas de estudiante")
    motivo = _motivo_bloqueo_estudiante(db.cuenta_estudiante_laboratorio(usuario["empresa_id"], usuario["id"]))
    if motivo:
        raise HTTPException(status_code=401, detail=motivo)
    return usuario


def _verificar_trabajo_laboratorio_del_estudiante(usuario: dict, trabajo: dict) -> None:
    """Un estudiante (portal propio, Fase 1) solo puede ver o tocar SUS
    PROPIOS trabajos de laboratorio -- nunca los de alguien más, aunque
    adivine el ID. El personal no tiene esta restricción (ven todo, como
    siempre)."""
    if usuario["rol"] == "estudiante" and trabajo.get("creado_por_id") != usuario["id"]:
        raise HTTPException(status_code=403, detail="Ese trabajo no es tuyo")


def requiere_ver_entregas(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Igual que requiere_ver_tickets/reparaciones, pero para Entregas. El rol
    'instalador' siempre tiene acceso — es su único módulo, no se le puede
    quitar — los demás roles sí pueden perder este acceso desde Administrar → Accesos."""
    if usuario["rol"] == "instalador":
        return usuario
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_entregas", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Entregas")
    return usuario


def requiere_ver_flotilla(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:
    """Como requiere_ver_entregas, pero además deja pasar a 'master' — el mapa
    de flotilla se muestra dentro de su Dashboard (su único lugar dentro de la
    app), aunque master no tiene acceso al resto del módulo de Entregas."""
    if usuario["rol"] in ("instalador", "master"):
        return usuario
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_entregas", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Entregas")
    return usuario


def requiere_ver_marketing(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Igual que requiere_ver_entregas, pero para Marketing."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Marketing")
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_marketing", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Marketing")
    return usuario


def requiere_ver_checador_precio(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Checador de precio — visible por default para todos los roles, pero
    revocable individualmente desde Administrar → Accesos."""
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_checador_precio", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al Checador de precio")
    return usuario


def requiere_inventarios(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Inventarios a puerta abierta (app). Permiso aparte (Administrar → Accesos →
    Inventarios), apagado por default: solo quien vaya a contar."""
    usuario = _con_permisos(usuario)
    if not (usuario.get("acceso_inventarios", False) or usuario["rol"] == "admin"):
        raise HTTPException(status_code=403, detail="No tienes acceso a Inventarios")
    return usuario


def requiere_admin_completo(usuario: dict = Depends(requiere_admin)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_administracion", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Administración")
    return usuario


def requiere_admin_completo_o_marketing(usuario: dict = Depends(requiere_empresa)) -> dict:
    """Deja pasar a un administrador completo, o a quien tenga acceso al
    módulo de Marketing -- para que Marketing pueda subir y asignar videos
    a la pantalla de Turnos de cada sucursal sin necesitar ser
    administrador."""
    if usuario["rol"] == "admin":
        con_permisos = _con_permisos(usuario)
        if con_permisos.get("acceso_administracion", True):
            return con_permisos
    if usuario["rol"] != "instalador":
        con_permisos = _con_permisos(usuario)
        if con_permisos.get("acceso_marketing", True):
            return con_permisos
    raise HTTPException(status_code=403, detail="No tienes permiso para subir o asignar videos")


# ==================== AUTENTICACIÓN ====================

class LoginPayload(BaseModel):
    username: str
    password: str
    app: Optional[str] = None  # la app móvil que entra: 'markinc' | 'peymar' (la web no lo manda)


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    usuario = db.obtener_usuario_por_username(payload.username)
    if usuario and usuario["rol"] == "estudiante" and auth.verificar_password(payload.password, usuario["password_hash"]):
        motivo = _motivo_bloqueo_estudiante(db.cuenta_estudiante_laboratorio(usuario["empresa_id"], usuario["id"]))
        if motivo:
            raise HTTPException(status_code=403, detail=motivo)
    if not usuario or not usuario["activo"] or not auth.verificar_password(payload.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    if usuario.get("acceso_app") is False:
        raise HTTPException(status_code=403, detail="Todavía no tienes acceso a la app. Pídele al administrador tu usuario.")
    if payload.app in db.APPS_MOVILES and usuario.get("empresa_id") and usuario["rol"] != "superadmin":
        suya = db.app_movil_empresa(usuario["empresa_id"])
        if suya != payload.app:
            raise HTTPException(status_code=403, detail=f"Tu cuenta es de otra empresa: entra con la app {db.APPS_MOVILES[suya]}.")
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


class CambiarMiNombre(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)


@app.post("/api/auth/cambiar-nombre")
def cambiar_mi_nombre(payload: CambiarMiNombre, usuario: dict = Depends(auth.get_current_user)):
    """Cada quien corrige su propio nombre (el usuario/login NO cambia).
    Regresa un token nuevo porque el nombre viaja dentro de la sesión."""
    nombre = " ".join(payload.nombre.split())
    if len(nombre) < 3:
        raise HTTPException(status_code=400, detail="Escribe tu nombre completo")
    db.actualizar_usuario(usuario["id"], nombre_completo=nombre)
    registro = db.obtener_usuario_por_username(usuario["username"])
    return {
        "token": auth.crear_token(registro),
        "usuario": {
            "id": registro["id"], "username": registro["username"],
            "nombre": registro["nombre_completo"], "rol": registro["rol"],
            "empresa_id": registro["empresa_id"],
        },
    }


# ==================== EMPRESAS (superadmin) ====================

class NuevaEmpresa(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    admin_username: str = Field(min_length=3, max_length=40)
    admin_password: str = Field(min_length=6)
    admin_nombre: str = Field(min_length=1, max_length=120)
    app_movil: Optional[str] = None  # 'markinc' | 'peymar' (sin elegir: por el nombre)


class ActualizacionEmpresa(BaseModel):
    nombre: Optional[str] = None
    activo: Optional[bool] = None
    datos_pago_cotizacion: Optional[str] = None
    app_movil: Optional[str] = None


def _validar_app_movil(app):
    if app is not None and app not in db.APPS_MOVILES:
        raise HTTPException(status_code=400, detail="App móvil inválida (markinc o peymar)")


class ModulosEmpresaIn(BaseModel):
    modulo_equipos: Optional[bool] = None
    modulo_compras: Optional[bool] = None
    modulo_rh: Optional[bool] = None
    modulo_dashboard: Optional[bool] = None
    modulo_reparaciones: Optional[bool] = None
    modulo_laboratorio: Optional[bool] = None
    modulo_entregas: Optional[bool] = None
    modulo_checador_precio: Optional[bool] = None
    modulo_marketing: Optional[bool] = None
    modulo_crm: Optional[bool] = None
    modulo_asistente_ia: Optional[bool] = None
    modulo_shopify: Optional[bool] = None
    modulo_turnos: Optional[bool] = None
    modulo_soporte: Optional[bool] = None


class NuevoLogo(BaseModel):
    logo_base64: str = Field(min_length=100)


@app.get("/api/empresas")
def listar_empresas(_: dict = Depends(requiere_superadmin)):
    return db.listar_empresas()


@app.post("/api/empresas")
def crear_empresa(payload: NuevaEmpresa, _: dict = Depends(requiere_superadmin)):
    if db.obtener_usuario_por_username(payload.admin_username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    _validar_app_movil(payload.app_movil)
    empresa_id = db.crear_empresa(payload.nombre.strip(), payload.admin_username.strip(), payload.admin_password, payload.admin_nombre.strip())
    if payload.app_movil:
        db.guardar_app_movil_empresa(empresa_id, payload.app_movil)
    return db.obtener_empresa(empresa_id)


@app.patch("/api/empresas/{empresa_id}")
def actualizar_empresa(empresa_id: int, payload: ActualizacionEmpresa, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    _validar_app_movil(payload.app_movil)
    db.actualizar_empresa(empresa_id, payload.nombre, payload.activo, payload.datos_pago_cotizacion)
    if payload.app_movil:
        db.guardar_app_movil_empresa(empresa_id, payload.app_movil)
    return db.obtener_empresa(empresa_id)


@app.patch("/api/empresas/{empresa_id}/modulos")
def actualizar_modulos_empresa(empresa_id: int, payload: ModulosEmpresaIn, _: dict = Depends(requiere_superadmin)):
    """Prende/apaga módulos completos para TODA la empresa — independiente
    de los permisos que cada usuario tenga individualmente. Si aquí se
    apaga un módulo, nadie de esa empresa lo va a poder usar aunque su
    permiso personal esté activo."""
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.actualizar_modulos_empresa(empresa_id, payload.model_dump(exclude_unset=True))
    return {"ok": True}


class BienvenidaEmpresaIn(BaseModel):
    activa: bool = True
    nombre: Optional[str] = Field(default=None, max_length=40)
    texto: Optional[str] = Field(default=None, max_length=2000)


class ConfigRHEmpresaIn(BaseModel):
    rh_sin_microsip: Optional[bool] = None
    bienvenida_obligatoria: Optional[bool] = None


@app.patch("/api/empresas/{empresa_id}/rh-config")
def actualizar_config_rh_empresa(empresa_id: int, payload: ConfigRHEmpresaIn, _: dict = Depends(requiere_superadmin)):
    """RH sin Microsip (alta de personal + nómina semanal aquí) y si las firmas
    de Bienvenido son obligatorias. Apagado/encendido por empresa."""
    db.guardar_config_rh_empresa(empresa_id, payload.rh_sin_microsip, payload.bienvenida_obligatoria)
    return db.config_rh_empresa(empresa_id)


@app.patch("/api/empresas/{empresa_id}/bienvenida")
def actualizar_bienvenida_empresa(empresa_id: int, payload: BienvenidaEmpresaIn, _: dict = Depends(requiere_superadmin)):
    """Módulo "Bienvenido" de la app Mark·Inc (antes Capacitación): prenderlo
    o apagarlo para la empresa, y su nombre y texto de bienvenida."""
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.guardar_bienvenida_empresa(empresa_id, payload.activa, _limpio(payload.nombre), _limpio(payload.texto))
    return db.obtener_bienvenida_empresa(empresa_id)


class ConfigWhatsappEmpresaIn(BaseModel):
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    whatsapp_from: Optional[str] = None
    template_sid: Optional[str] = None


@app.get("/api/empresas/{empresa_id}/whatsapp")
def obtener_config_whatsapp_empresa(empresa_id: int, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    config = db.obtener_config_whatsapp(empresa_id) or {}
    # El auth_token no se regresa completo por seguridad, solo si ya hay uno capturado.
    return {
        "account_sid": config.get("account_sid") or "",
        "tiene_auth_token": bool(config.get("auth_token")),
        "whatsapp_from": config.get("whatsapp_from") or "",
        "template_sid": config.get("template_sid") or "",
    }


@app.patch("/api/empresas/{empresa_id}/whatsapp")
def actualizar_config_whatsapp_empresa(empresa_id: int, payload: ConfigWhatsappEmpresaIn, _: dict = Depends(requiere_superadmin)):
    """WhatsApp propio de esta empresa (su propia cuenta de Twilio) — si
    se deja vacío, la empresa usa las variables de entorno globales de
    respaldo. Cada marca necesita su PROPIO número de WhatsApp Business
    verificado por Meta, no se puede compartir uno entre empresas distintas."""
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.actualizar_config_whatsapp(
        empresa_id,
        account_sid=payload.account_sid, auth_token=payload.auth_token,
        whatsapp_from=payload.whatsapp_from, template_sid=payload.template_sid,
    )
    return {"ok": True}


@app.get("/api/superadmin/consumo")
def obtener_consumo_superadmin(fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None, _: dict = Depends(requiere_superadmin)):
    """Consumo de IA (Mouse, leer imágenes, generar imágenes de promoción,
    chatbot de WhatsApp) y de WhatsApp (notificaciones, difusiones) por
    empresa — para que puedas cobrar/controlar el gasto de cada una."""
    return db.resumen_consumo_por_empresa(fecha_desde, fecha_hasta)


@app.get("/api/superadmin/uso-db")
def obtener_uso_db_superadmin(_: dict = Depends(requiere_superadmin)):
    """Cuántos registros tiene cada empresa y qué tanto pesa (ESTIMADO)
    dentro de la base de datos compartida -- para ver quién usa más
    espacio. No es exacto (Neon no separa el consumo por empresa)."""
    return db.resumen_uso_db_por_empresa()


class CostosEmpresaIn(BaseModel):
    config: dict


@app.get("/api/empresas/{empresa_id}/costos")
def obtener_costos_empresa(empresa_id: int, _: dict = Depends(requiere_superadmin)):
    """Configuración del cotizador interno para esta empresa (qué módulos
    tiene armados, qué le cobras y qué te cuesta) — {} si aún no se ha
    guardado nada para ella."""
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return db.obtener_costos_empresa(empresa_id) or {}


@app.put("/api/empresas/{empresa_id}/costos")
def guardar_costos_empresa(empresa_id: int, payload: CostosEmpresaIn, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    db.guardar_costos_empresa(empresa_id, payload.config)
    return {"ok": True}


@app.get("/api/superadmin/costos-resumen")
def obtener_costos_resumen(_: dict = Depends(requiere_superadmin)):
    """Para cada empresa con cotización configurada: renta mensual
    cobrada, costo real estimado y margen — vista rápida para el panel
    de Superadmin, sin entrar a cada empresa una por una."""
    return db.resumen_costos_empresas()


class NuevaCotizacionCostos(BaseModel):
    nombre_cliente: Optional[str] = None
    empresa_id: Optional[int] = None


class CotizacionCostosIn(BaseModel):
    nombre_cliente: Optional[str] = None
    empresa_id: Optional[int] = None
    config: dict


@app.get("/api/superadmin/cotizaciones")
def api_listar_cotizaciones(usuario: dict = Depends(requiere_superadmin)):
    """Todas las cotizaciones del Cotizador — con o sin empresa ligada
    (prospectos incluidos), independiente del módulo de empresas."""
    return db.listar_cotizaciones_costos()


@app.post("/api/superadmin/cotizaciones")
def api_crear_cotizacion(payload: NuevaCotizacionCostos, usuario: dict = Depends(requiere_superadmin)):
    if payload.empresa_id and not db.obtener_empresa(payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if not payload.empresa_id and not (payload.nombre_cliente or "").strip():
        raise HTTPException(status_code=400, detail="Ponle un nombre de cliente o vincúlala a una empresa existente")
    nuevo_id = db.crear_cotizacion_costos((payload.nombre_cliente or "").strip() or None, payload.empresa_id, usuario["id"])
    return {"id": nuevo_id}


@app.post("/api/superadmin/cotizaciones/por-empresa/{empresa_id}")
def api_cotizacion_por_empresa(empresa_id: int, usuario: dict = Depends(requiere_superadmin)):
    """Para el botón "🧾 Cotización" de la tarjeta de una empresa: reusa
    la cotización que ya tenga ligada, o crea una nueva la primera vez."""
    empresa = db.obtener_empresa(empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    existente = db.obtener_cotizacion_por_empresa(empresa_id)
    if existente:
        return {"id": existente["id"]}
    nuevo_id = db.crear_cotizacion_costos(empresa["nombre"], empresa_id, usuario["id"])
    return {"id": nuevo_id}


@app.get("/api/superadmin/cotizaciones/{cotizacion_id}")
def api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_superadmin)):
    cotizacion = db.obtener_cotizacion_costos(cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return cotizacion


@app.put("/api/superadmin/cotizaciones/{cotizacion_id}")
def api_guardar_cotizacion(cotizacion_id: int, payload: CotizacionCostosIn, usuario: dict = Depends(requiere_superadmin)):
    if not db.obtener_cotizacion_costos(cotizacion_id):
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if payload.empresa_id and not db.obtener_empresa(payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    config = db.asignar_folios_cotizacion(cotizacion_id, payload.config)
    db.actualizar_cotizacion_costos(cotizacion_id, (payload.nombre_cliente or "").strip() or None, payload.empresa_id, config)
    return {"ok": True, "folio": config["cliente"]["folio"],
            "nota_folio": (config.get("nota") or {}).get("folio") if (config.get("nota") or {}).get("activa") else None}


@app.delete("/api/superadmin/cotizaciones/{cotizacion_id}")
def api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_superadmin)):
    if not db.obtener_cotizacion_costos(cotizacion_id):
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    db.eliminar_cotizacion_costos(cotizacion_id)
    return {"ok": True}


class DatosPagoCotizadorCostosIn(BaseModel):
    datos_pago: Optional[str] = None


@app.get("/api/superadmin/cotizador-costos/datos-pago")
def api_obtener_datos_pago_cotizador_costos(_: dict = Depends(requiere_superadmin)):
    """Dato global (banco/cuenta) del Cotizador de sistema TI -- el mismo
    para todas las cotizaciones que arma el superadmin, no por cotización."""
    return {"datos_pago": db.obtener_datos_pago_cotizador_costos()}


@app.put("/api/superadmin/cotizador-costos/datos-pago")
def api_guardar_datos_pago_cotizador_costos(payload: DatosPagoCotizadorCostosIn, _: dict = Depends(requiere_superadmin)):
    db.guardar_datos_pago_cotizador_costos(payload.datos_pago)
    return {"ok": True}


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


class EliminarEmpresa(BaseModel):
    confirmacion_nombre: str


@app.delete("/api/empresas/{empresa_id}")
def eliminar_empresa(empresa_id: int, payload: EliminarEmpresa, _: dict = Depends(requiere_superadmin)):
    empresa = db.obtener_empresa(empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if payload.confirmacion_nombre.strip() != empresa["nombre"]:
        raise HTTPException(status_code=400, detail="El nombre no coincide — escribe el nombre exacto de la empresa para confirmar")
    try:
        db.eliminar_empresa_completa(empresa_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/empresas/{empresa_id}/clonar")
def clonar_empresa(empresa_id: int, payload: ClonarEmpresa, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    resultado = db.clonar_empresa(empresa_id, payload.nombre_nueva_empresa.strip(), payload.sufijo_usuarios.strip())
    if not resultado:
        raise HTTPException(status_code=400, detail="No se pudo clonar la empresa")
    return resultado


# ==================== POLÍTICAS DE LA EMPRESA (Reparaciones) ====================

DEFAULT_POLITICAS_TEXTO = """TÉRMINOS Y CONDICIONES DEL SERVICIO

1. GARANTÍA: El equipo cuenta con garantía únicamente si así se indica expresamente en la orden de servicio. Fuera de ese caso, NO EXISTE GARANTÍA sobre la reparación realizada ni sobre las refacciones utilizadas.

2. RESPALDO DE INFORMACIÓN: La empresa no se hace responsable por la pérdida de información, datos, programas o configuraciones almacenadas en el equipo. Es responsabilidad exclusiva del cliente respaldar su información antes de dejar el equipo a revisión.

3. TIEMPO DE RESGUARDO: Una vez que se notifica al cliente que el equipo está listo para su entrega, cuenta con 30 días naturales para recogerlo. Pasado ese plazo, la empresa no se hace responsable por el estado o resguardo del equipo.

4. DIAGNÓSTICO: El diagnóstico inicial puede variar una vez que el equipo es abierto. Cualquier cambio en el costo o alcance del servicio será notificado al cliente para su autorización antes de continuar con el trabajo.

5. ACCESORIOS: Solo se garantiza la devolución de los accesorios expresamente anotados en la orden de servicio al momento de la recepción.

Al firmar de conformidad, el cliente declara haber leído y estar de acuerdo con los términos aquí descritos."""


class ActualizacionPoliticas(BaseModel):
    texto: str = Field(min_length=1)


@app.get("/api/politicas")
def api_obtener_politicas(usuario: dict = Depends(requiere_empresa_o_almacen)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    texto = (empresa.get("politicas_texto") if empresa else None) or DEFAULT_POLITICAS_TEXTO
    return {"texto": texto}


@app.patch("/api/politicas")
def api_actualizar_politicas(payload: ActualizacionPoliticas, usuario: dict = Depends(requiere_admin)):
    db.actualizar_politicas_empresa(usuario["empresa_id"], payload.texto)
    return {"ok": True}


class ActualizacionApariencia(BaseModel):
    tema: Optional[str] = None
    color_acento: Optional[str] = None
    fondo_color: Optional[str] = None
    fondo_base64: Optional[str] = None


@app.patch("/api/apariencia")
def api_actualizar_apariencia(payload: ActualizacionApariencia, usuario: dict = Depends(requiere_admin)):
    enviados = payload.dict(exclude_unset=True)
    if payload.tema is not None and payload.tema not in ("oscuro", "claro"):
        raise HTTPException(status_code=400, detail="Tema inválido (usa 'oscuro' o 'claro')")
    patron_hex = re.compile(r"^#[0-9A-Fa-f]{6}$")
    if "color_acento" in enviados and payload.color_acento and not patron_hex.match(payload.color_acento):
        raise HTTPException(status_code=400, detail="El color de acento debe ser un código hexadecimal, ej. #D8192F")
    if "fondo_color" in enviados and payload.fondo_color and not patron_hex.match(payload.fondo_color):
        raise HTTPException(status_code=400, detail="El color de fondo debe ser un código hexadecimal, ej. #1A1B1D")
    if payload.fondo_base64 and len(payload.fondo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La imagen de fondo pesa demasiado (máximo 5MB)")

    kwargs = {}
    if "color_acento" in enviados:
        kwargs["color_acento"] = payload.color_acento
    if "fondo_color" in enviados:
        kwargs["fondo_color"] = payload.fondo_color
    if "fondo_base64" in enviados:
        kwargs["fondo_base64"] = payload.fondo_base64
    db.actualizar_apariencia_empresa(usuario["empresa_id"], tema=payload.tema, **kwargs)
    return {"ok": True}


# ==================== META (para usuarios de una empresa) ====================

@app.get("/api/meta")
def meta(usuario: dict = Depends(requiere_empresa_o_master)):
    usuario = _con_permisos(usuario)
    empresa = db.obtener_empresa(usuario["empresa_id"])
    es_admin = usuario["rol"] == "admin"
    return {
        "estados": db.ESTADOS, "prioridades": db.PRIORIDADES, "roles": ["admin", "tecnico", "usuario", "master", "almacen", "encargado_sucursal", "instalador"],
        "departamentos": [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])],
        "categorias": [c["nombre"] for c in db.listar_categorias(usuario["empresa_id"])],
        "empresa_nombre": empresa["nombre"] if empresa else "",
        "empresa_logo": empresa["logo_base64"] if empresa else None,
        "app_movil": db.app_movil_empresa(usuario["empresa_id"]) if usuario.get("empresa_id") else None,
        "apariencia": {
            "tema": (empresa.get("tema") if empresa else None) or "oscuro",
            "color_acento": empresa.get("color_acento") if empresa else None,
            "fondo_color": empresa.get("fondo_color") if empresa else None,
            "fondo_base64": empresa.get("fondo_base64") if empresa else None,
        },
        "tipos_equipo": db.TIPOS_EQUIPO, "estados_equipo": db.ESTADOS_EQUIPO,
        "tipos_mantenimiento": db.TIPOS_MANTENIMIENTO, "frecuencias_mantenimiento": db.FRECUENCIAS_MANTENIMIENTO,
        "estados_proyecto": db.ESTADOS_PROYECTO,
        "estados_tarea_proyecto": db.ESTADOS_TAREA_PROYECTO,
        "frecuencias_compra": db.FRECUENCIAS_COMPRA, "estados_ciclo_compra": db.ESTADOS_CICLO_COMPRA,
        "estados_reparacion": db.ESTADOS_REPARACION,
        "estados_laboratorio": db.ESTADOS_LABORATORIO, "tipos_solicitante_laboratorio": db.TIPOS_SOLICITANTE_LABORATORIO,
        "tipos_trabajo_laboratorio": db.TIPOS_TRABAJO_LABORATORIO,
        "tipos_metodo_pago_laboratorio": db.TIPOS_METODO_PAGO_LABORATORIO,
        "materiales_laboratorio": db.MATERIALES_LABORATORIO,
        "precios_fijos_laboratorio_buap": {f"{k[0]}|{k[1]}": v for k, v in db.PRECIOS_FIJOS_LABORATORIO_BUAP.items()},
        # Destinos de envío del laboratorio (Dentigo, 33, 13, Corporativo + escuela).
        "destinos_laboratorio": db.sucursales_destino_laboratorio(usuario["empresa_id"]) if usuario.get("empresa_id") else [],
        "sucursales_recogida_laboratorio": [
            {"id": s["id"], "nombre": s["nombre"], "es_recogida_default_estudiantes": s.get("es_recogida_default_estudiantes", False)}
            for s in db.listar_sucursales_reparacion(usuario["empresa_id"], solo_activas=True)
        ],
        "dscore_conectado_laboratorio": bool(db.obtener_tokens_dscore(usuario["empresa_id"])),
        "estados_entrega": list(db.TRANSICIONES_VALIDAS_ENTREGA.keys()),
        "tipos_incidencia_rh": db.TIPOS_INCIDENCIA_RH, "estados_incidencia_rh": db.ESTADOS_INCIDENCIA_RH,
        "tipos_movimiento_horas_rh": db.TIPOS_MOVIMIENTO_HORAS_RH,
        "tablas_borrado_masivo": [{"key": k, "etiqueta": v["etiqueta"]} for k, v in db.TABLAS_BORRADO_MASIVO.items()],
        "etapas_oportunidad_crm": db.ETAPAS_OPORTUNIDAD_CRM,
        "nombre_asistente_ia": db.obtener_nombre_asistente_ia(usuario["empresa_id"]) if usuario.get("empresa_id") else "Mouse",
        "tipos_interaccion_crm": db.TIPOS_INTERACCION_CRM,
        "tipos_cliente_crm": db.TIPOS_CLIENTE_CRM,
        "giros_cliente_crm": db.GIROS_CLIENTE_CRM,
        "mis_permisos": {
            "acceso_equipos": usuario.get("acceso_equipos", True),
            "acceso_administracion": usuario.get("acceso_administracion", True) if es_admin else False,
            "acceso_compras": usuario.get("acceso_compras", True),
            "acceso_rh": usuario.get("acceso_rh", True),
            "acceso_tickets": usuario.get("acceso_tickets", True),
            "acceso_reparaciones": True if usuario["rol"] == "almacen" else usuario.get("acceso_reparaciones", True),
            "acceso_laboratorio": usuario.get("acceso_laboratorio", True),
            "acceso_laboratorio_entrega": usuario.get("acceso_laboratorio_entrega", False),
            "acceso_logistica_reparaciones": usuario.get("acceso_logistica_reparaciones", False),
            "acceso_proyectos": usuario.get("acceso_proyectos", True),
            "admin_proyectos": usuario.get("admin_proyectos", False),
            "acceso_checador": usuario.get("acceso_checador", False),
            "acceso_entregas": True if usuario["rol"] == "instalador" else usuario.get("acceso_entregas", True),
            "acceso_checador_precio": usuario.get("acceso_checador_precio", True),
            "acceso_marketing": False if usuario["rol"] == "instalador" else usuario.get("acceso_marketing", True),
            "acceso_crm": False if usuario["rol"] in ("instalador", "almacen") else usuario.get("acceso_crm", False),
            "acceso_asistente_ia": usuario.get("acceso_asistente_ia", False),
            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),
            "ver_mi_asistencia": usuario.get("ver_mi_asistencia", True),
            "acceso_monitoreo": usuario.get("acceso_monitoreo", False),
            "acceso_shopify": usuario.get("acceso_shopify", True),
            "acceso_turnos": usuario.get("acceso_turnos", True),
            "acceso_soporte": usuario.get("acceso_soporte", False),
            "acceso_inventarios": bool(usuario.get("acceso_inventarios", False) or usuario["rol"] == "admin"),
            "acceso_dashboard": usuario.get("acceso_dashboard", True) if es_admin else True,
            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,
        },
        "monitoreo": {
            "activo": usuario.get("monitoreo_activo", False),
            "acepto": (not usuario.get("monitoreo_activo", False)) or db.usuario_acepto_monitoreo(usuario["id"]),
        },
        "mi_departamento": db.obtener_departamento_usuario(usuario["id"]) if usuario["rol"] != "master" else None,
        "mi_sucursal_id": db.obtener_sucursal_id_usuario(usuario["id"]) if usuario["rol"] != "master" else None,
        # Para la app: Logística ve todas las reparaciones y registra la entrega al chofer.
        "es_logistica": _es_departamento_logistica(usuario["id"]) if usuario["rol"] != "master" else False,
        # App: puede crear/administrar proyectos (admin, técnico o "Admin. Proyectos").
        "gestor_proyectos": _es_gestor_proyectos(usuario) and usuario.get("acceso_proyectos", True) if usuario["rol"] != "master" else False,
        # App: módulo de entregas de laboratorio (encargadas) y si soy del laboratorio.
        "soy_laboratorio": _es_usuario_laboratorio(usuario) if usuario.get("empresa_id") and usuario["rol"] != "master" else False,
        # Módulo "Bienvenido" de la app (nombre, texto y si está activo; Superadmin → Módulos).
        "bienvenida": db.obtener_bienvenida_empresa(usuario["empresa_id"]) if usuario.get("empresa_id") else None,
        "mi_ventanilla_turnos": usuario.get("ventanilla_turnos"),
        "terminos": _terminos_empresa(usuario["empresa_id"]) if usuario["rol"] != "master" else {},
        # RH sin Microsip (ej. Peymar): alta de personal y nómina semanal aquí; bienvenida opcional.
        "rh": db.config_rh_empresa(usuario["empresa_id"]) if usuario.get("empresa_id") else {},
        # Soporte técnico (Peymar): si la empresa tiene el módulo (para mostrar el permiso en Accesos).
        "modulo_soporte": bool(db.obtener_modulos_empresa(usuario["empresa_id"]).get("acceso_soporte")) if usuario.get("empresa_id") else False,
    }


def _terminos_empresa(empresa_id):
    terminos = db.obtener_terminos(empresa_id)
    if "campo.sucursal" not in terminos and db.config_rh_empresa(empresa_id)["rh_sin_microsip"]:
        terminos["campo.sucursal"] = "Nave"
    return terminos


class TerminoPersonalizado(BaseModel):
    clave: str
    valor: str = Field(min_length=1, max_length=100)


@app.get("/api/terminos/editables")
def api_terminos_editables(usuario: dict = Depends(requiere_admin_completo)):
    """Regresa el catálogo de términos que se pueden personalizar (clave,
    grupo, valor por default) junto con lo que la empresa ya personalizó."""
    return {"catalogo": db.TERMINOS_EDITABLES, "personalizados": db.obtener_terminos(usuario["empresa_id"])}


@app.post("/api/terminos")
def api_guardar_termino(payload: TerminoPersonalizado, usuario: dict = Depends(requiere_admin_completo)):
    try:
        db.guardar_termino(usuario["empresa_id"], payload.clave, payload.valor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.delete("/api/terminos/{clave}")
def api_restaurar_termino(clave: str, usuario: dict = Depends(requiere_admin_completo)):
    db.restaurar_termino(usuario["empresa_id"], clave)
    return {"ok": True}


# ==================== CALENDARIO PERSONAL (.ics) ====================
# Enlace de suscripción para el Calendario de iPhone o Google Calendar de
# Android — se suscriben UNA vez y de ahí en adelante los proyectos y
# mantenimientos que les toquen aparecen solos, sin volver a hacer nada.

@app.get("/api/mi-calendario")
def api_mi_calendario(usuario: dict = Depends(requiere_empresa)):
    token = db.obtener_o_crear_token_calendario(usuario["id"])
    return {"ruta": f"/calendario/{token}.ics"}


@app.post("/api/mi-calendario/regenerar")
def api_regenerar_mi_calendario(usuario: dict = Depends(requiere_empresa)):
    """Por si alguien comparte su enlace sin querer y quiere invalidarlo —
    esto rompe la suscripción vieja; hay que volver a suscribirse con la nueva."""
    token = db.regenerar_token_calendario(usuario["id"])
    return {"ruta": f"/calendario/{token}.ics"}


@app.get("/calendario/{token}.ics")
def calendario_ics_publico(token: str):
    """SIN autenticación normal a propósito — el Calendario de un celular no
    puede iniciar sesión ni mandar un token de sesión; el propio token (largo,
    aleatorio, imposible de adivinar) es la credencial, igual que hacen los
    calendarios de suscripción de Google Calendar, Notion, Trello, etc."""
    usuario = db.obtener_usuario_por_token_calendario(token)
    if not usuario:
        raise HTTPException(status_code=404, detail="Enlace de calendario no válido")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    eventos = db.listar_eventos_calendario_usuario(usuario["empresa_id"], usuario["id"], usuario["rol"])
    contenido = calendario_ics.generar_ics(empresa["nombre"] if empresa else "Mark Inc", eventos)
    return Response(content=contenido, media_type="text/calendar; charset=utf-8",
                     headers={"Content-Disposition": "inline; filename=calendario.ics"})


@app.get("/api/notificaciones")
def api_obtener_notificaciones(usuario: dict = Depends(requiere_empresa_o_almacen)):
    """Resumen en vivo de pendientes (tickets, proyectos, ciclos de compra abiertos,
    etc.) — accesible a cualquier rol de la empresa, cada quien ve solo lo suyo.
    Cada notificación trae el id del elemento exacto, para poder ir directo a él."""
    if usuario["rol"] in ("master",):
        return []
    usuario = _con_permisos(usuario)
    acceso_compras = usuario.get("acceso_compras", True) if usuario["rol"] == "admin" else True
    acceso_rh = usuario.get("acceso_rh", True) if usuario["rol"] == "admin" else True
    acceso_reparaciones = True if usuario["rol"] == "almacen" else usuario.get("acceso_reparaciones", True)
    acceso_equipos = usuario.get("acceso_equipos", True)
    return db.obtener_notificaciones(usuario["empresa_id"], usuario["id"], usuario["rol"],
                                      acceso_compras, acceso_rh, acceso_reparaciones, acceso_equipos)


@app.get("/api/dashboard")
def api_dashboard(usuario: dict = Depends(requiere_dashboard)):
    return db.estadisticas_dashboard(usuario["empresa_id"])


# ---- Dirección (vista del CEO en la app): solo lectura ----
# La ven el rol "master" (Dashboard, sin aprobar ni crear nada) y los
# administradores con acceso al Dashboard. Ver direccion.py.

@app.get("/api/direccion/resumen")
def api_direccion_resumen(dia: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """RH del día (retardos, faltas, quién no ha checado, permisos con motivo),
    reparaciones pendientes, proyectos con su avance, tickets, laboratorio y
    soporte — cada bloque solo si la empresa tiene ese módulo. dia: 'hoy'
    (default), 'ayer' o AAAA-MM-DD (solo cambia el bloque de RH)."""
    hoy = db.ahora().date()
    if not dia or dia == "hoy":
        d = hoy
    elif dia == "ayer":
        d = hoy - timedelta(days=1)
    else:
        try:
            d = date.fromisoformat(dia)
        except ValueError:
            raise HTTPException(status_code=400, detail="Día inválido, usa hoy, ayer o AAAA-MM-DD")
    modulos = db.obtener_modulos_empresa(usuario["empresa_id"])
    return direccion.resumen(usuario["empresa_id"], modulos, d, _reporte_asistencia)


@app.get("/api/rh/asistencia/del-dia")
def api_asistencia_del_dia_rh(dia: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Para RH en la app: lo mismo que ve el director en Dirección → Asistencia
    (quién llegó tarde, quién no ha checado, faltas con y sin permiso,
    checadores sin conexión). dia: 'hoy' (default), 'ayer' o AAAA-MM-DD."""
    hoy = db.ahora().date()
    if not dia or dia == "hoy":
        d = hoy
    elif dia == "ayer":
        d = hoy - timedelta(days=1)
    else:
        try:
            d = date.fromisoformat(dia)
        except ValueError:
            raise HTTPException(status_code=400, detail="Día inválido, usa hoy, ayer o AAAA-MM-DD")
    return {"fecha": d.isoformat(), "generado": db.ahora().strftime("%Y-%m-%d %H:%M"),
            "rh": direccion.bloque_asistencia(usuario["empresa_id"], d, _reporte_asistencia)}


def _microsip_direccion(usuario: dict):
    config = db.obtener_config_microsip(usuario["empresa_id"])
    return config if config and config.get("microsip_host") else None


@app.get("/api/direccion/consultas")
def api_direccion_consultas(usuario: dict = Depends(requiere_dashboard)):
    """Consultas de Microsip listas para el CEO. La app las dibuja sola, así
    que una consulta nueva en direccion.CONSULTAS aparece sin actualizar la app."""
    if not _microsip_direccion(usuario):
        return {"disponible": False, "consultas": []}
    return {"disponible": True, "consultas": direccion.lista_consultas()}


@app.get("/api/direccion/opciones/{tipo}")
def api_direccion_opciones(tipo: str, usuario: dict = Depends(requiere_dashboard)):
    config = _config_microsip_o_error(usuario) if tipo != "periodo" else None
    try:
        return direccion.opciones(tipo, config)
    except KeyError:
        raise HTTPException(status_code=404, detail="Tipo de opción desconocido")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@app.get("/api/direccion/consultas/{clave}")
def api_direccion_ejecutar(clave: str, request: Request, usuario: dict = Depends(requiere_dashboard)):
    config = _config_microsip_o_error(usuario)
    try:
        return direccion.ejecutar(clave, config, dict(request.query_params))
    except KeyError:
        raise HTTPException(status_code=404, detail="Esa consulta ya no existe")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@app.get("/api/dashboard/ventas-pv")
def api_dashboard_ventas_pv(fecha: Optional[str] = None, mes: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """Ventas de HOY (o del día/mes que se pida) del módulo de Punto de Venta
    de Microsip, por sucursal y desglosadas por forma de cobro."""
    config = _config_microsip_o_error(usuario)
    from datetime import date, datetime, timedelta
    if mes:
        try:
            primer_dia = datetime.strptime(mes, "%Y-%m").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Mes inválido, usa el formato AAAA-MM")
        fecha_inicio = primer_dia.isoformat()
        fecha_fin_dt = date(primer_dia.year + 1, 1, 1) if primer_dia.month == 12 else date(primer_dia.year, primer_dia.month + 1, 1)
        fecha_fin = fecha_fin_dt.isoformat()
        etiqueta = mes
    else:
        if fecha:
            try:
                dia = datetime.strptime(fecha, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")
        else:
            dia = date.today()
        fecha_inicio = dia.isoformat()
        fecha_fin = (dia + timedelta(days=1)).isoformat()
        etiqueta = fecha_inicio
    try:
        resultado = microsip.obtener_ventas_pv_por_sucursal(config, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")
    resultado["fecha"] = etiqueta
    return resultado


@app.get("/api/dashboard/bitacora-ventas-pv")
def api_dashboard_bitacora_ventas_pv(fecha: Optional[str] = None, mes: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """Primeras/últimas 10 ventas del día (o mes) y el rango de 12pm a 2pm,
    para revisar la actividad de Punto de Venta a lo largo del tiempo."""
    config = _config_microsip_o_error(usuario)
    from datetime import date, datetime, timedelta
    if mes:
        try:
            primer_dia = datetime.strptime(mes, "%Y-%m").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Mes inválido, usa el formato AAAA-MM")
        fecha_inicio = primer_dia.isoformat()
        fecha_fin_dt = date(primer_dia.year + 1, 1, 1) if primer_dia.month == 12 else date(primer_dia.year, primer_dia.month + 1, 1)
        fecha_fin = fecha_fin_dt.isoformat()
        etiqueta = mes
    else:
        if fecha:
            try:
                dia = datetime.strptime(fecha, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")
        else:
            dia = date.today()
        fecha_inicio = dia.isoformat()
        fecha_fin = (dia + timedelta(days=1)).isoformat()
        etiqueta = fecha_inicio
    try:
        resultado = microsip.obtener_bitacora_ventas_pv(config, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")
    resultado["fecha"] = etiqueta
    return resultado


def _parsear_valores_clasif(valores_clasif: Optional[str]) -> Optional[list]:
    """'19427,19623' -> [19427, 19623]; None o '' -> None (sin filtro)."""
    if not valores_clasif:
        return None
    try:
        return [int(v) for v in valores_clasif.split(",") if v.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="valores_clasif inválido")


@app.get("/api/dashboard/clasificadores-articulos")
def api_dashboard_clasificadores_articulos(usuario: dict = Depends(requiere_dashboard)):
    """Clasificadores que aplican a artículos (ej. MARCA, PROVEEDOR) para
    el selector del filtro en las tarjetas de inventario."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"clasificadores": microsip.listar_clasificadores_articulos(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (clasificadores): {e}")


@app.get("/api/dashboard/articulos-sin-clasificador")
def api_dashboard_articulos_sin_clasificador(usuario: dict = Depends(requiere_dashboard)):
    """Artículos de Microsip a los que les falta el clasificador de MARCA
    y/o PROVEEDOR (para exportarlo a Excel y completarlos)."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.articulos_sin_clasificador(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (clasificadores): {e}")


@app.get("/api/dashboard/clientes-microsip")
def api_dashboard_clientes_microsip(usuario: dict = Depends(requiere_dashboard)):
    """Todos los clientes de Microsip con todos sus datos, última compra y
    estado/municipio (por dirección o, si no tiene, por lada) para Excel."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"clientes": microsip.clientes_para_excel(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (clientes): {e}")


@app.get("/api/dashboard/valores-clasificador")
def api_dashboard_valores_clasificador(clasificador_id: int, usuario: dict = Depends(requiere_dashboard)):
    """Valores posibles de un clasificador (ej. para MARCA: 3M, Panorama...)."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"valores": microsip.listar_valores_clasificador(config, clasificador_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (valores de clasificador): {e}")


@app.get("/api/dashboard/valor-inventario")
def api_dashboard_valor_inventario(valores_clasif: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """Valor del inventario (a costo de compra) por sucursal, y los 50
    artículos que más valor representan en cada una. valores_clasif:
    lista de VALOR_CLASIF_ID separados por coma (opcional) para filtrar
    por clasificador (ej. Marca=3M)."""
    config = _config_microsip_o_error(usuario)
    try:
        resultado = microsip.obtener_valor_inventario_por_almacen(config, _parsear_valores_clasif(valores_clasif))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario): {e}")
    return resultado


@app.get("/api/dashboard/sin-movimiento")
def api_dashboard_sin_movimiento(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                  filtro_stock: str = "con_stock", valores_clasif: Optional[str] = None,
                                  consolidado: bool = False, usuario: dict = Depends(requiere_dashboard)):
    """Artículos sin movimiento de venta (Punto de Venta, Facturas o
    Remisiones — en ninguna sucursal, en todo el historial), por almacén,
    valuados a precio de venta. filtro_stock: "con_stock" (default, solo existencia > 0),
    "sin_stock" (solo los ya en 0 o negativo), "negativos" (solo los
    negativos estrictos, < 0), "todos" (todos). valores_clasif: lista de
    VALOR_CLASIF_ID separados por coma (opcional). consolidado=True junta
    todos los almacenes en un solo grupo. Si se dan fecha_inicio/fecha_fin
    (AAAA-MM-DD, fecha_fin excluida), solo incluye los que tuvieron una
    entrada de inventario en ese rango."""
    if filtro_stock not in ("con_stock", "sin_stock", "negativos", "todos"):
        raise HTTPException(status_code=400, detail="filtro_stock inválido")
    config = _config_microsip_o_error(usuario)
    try:
        resultado = microsip.obtener_articulos_sin_movimiento_por_almacen(
            config, fecha_inicio, fecha_fin, filtro_stock, _parsear_valores_clasif(valores_clasif), consolidado)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (sin movimiento): {e}")
    return resultado


@app.get("/api/dashboard/valor-inventario-venta")
def api_dashboard_valor_inventario_venta(valores_clasif: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """Valor del inventario a PRECIO DE VENTA (lista, no costo) por
    sucursal, y los 50 artículos que más valor representan en cada una.
    valores_clasif: lista de VALOR_CLASIF_ID separados por coma (opcional)."""
    config = _config_microsip_o_error(usuario)
    try:
        resultado = microsip.obtener_valor_inventario_precio_venta_por_almacen(config, _parsear_valores_clasif(valores_clasif))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (inventario a precio de venta): {e}")
    return resultado


@app.get("/api/dashboard/sucursales-venta")
def api_dashboard_sucursales_venta(usuario: dict = Depends(requiere_dashboard)):
    """Lista de sucursales (tabla SUCURSALES, la de Pedidos/Punto de
    Venta) para el selector de 'Pedidos pendientes'."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"sucursales": microsip.listar_sucursales_venta(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (sucursales): {e}")


@app.get("/api/dashboard/almacenes")
def api_dashboard_almacenes(usuario: dict = Depends(requiere_dashboard)):
    """Lista de almacenes (tabla ALMACENES) para el filtro opcional de
    'Pedidos pendientes' — independiente del selector de sucursal."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"almacenes": microsip.listar_almacenes(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (almacenes): {e}")


@app.get("/api/dashboard/almacenes-de-sucursal")
def api_dashboard_almacenes_de_sucursal(sucursal_id: int, usuario: dict = Depends(requiere_dashboard)):
    """Solo los almacenes que de verdad tienen pedidos de esa sucursal —
    para que el selector de 'Pedidos pendientes' no ofrezca combinaciones
    sucursal+almacén que nunca dan resultados."""
    config = _config_microsip_o_error(usuario)
    try:
        return {"almacenes": microsip.listar_almacenes_con_pedidos_de_sucursal(config, sucursal_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (almacenes de sucursal): {e}")


@app.get("/api/dashboard/pedidos-pendientes")
def api_dashboard_pedidos_pendientes(sucursal_id: int, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                      almacen_id: Optional[int] = None, usuario: dict = Depends(requiere_dashboard)):
    """Pedidos de una sucursal con piezas pendientes de surtir, más el
    desglose de productos sumado (mismo artículo en varios pedidos se
    suma en un solo total). fecha_inicio/fecha_fin (AAAA-MM-DD, fecha_fin
    excluida) filtran por la fecha del pedido. almacen_id filtra además
    por almacén (opcional, independiente de la sucursal)."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.obtener_pedidos_pendientes_por_sucursal(config, sucursal_id, fecha_inicio, fecha_fin, almacen_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (pedidos pendientes): {e}")


@app.get("/api/dashboard/traspasos-sucursales")
def api_dashboard_traspasos_sucursales(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                        usuario: dict = Depends(requiere_dashboard)):
    """Traspasos de mercancía únicamente entre Dentigo/13 Sur/33 Pte, con
    los productos desglosados y sumados. fecha_inicio/fecha_fin (AAAA-MM-DD,
    fecha_fin excluida) filtran por la fecha del envío."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.obtener_traspasos_entre_sucursales(config, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (traspasos): {e}")


@app.get("/api/dashboard/ventas-pv-almacen")
def api_dashboard_ventas_pv_almacen(almacen_id: int, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                     usuario: dict = Depends(requiere_dashboard)):
    """Ventas de Punto de Venta de un almacén, desglosadas por caja
    trabajada. fecha_inicio/fecha_fin (AAAA-MM-DD, fecha_fin excluida)."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.obtener_ventas_pv_por_almacen(config, almacen_id, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (ventas por caja): {e}")


@app.get("/api/dashboard/corte-dia")
def api_dashboard_corte_dia(sucursal_id: int, almacen_id: Optional[int] = None,
                             fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                             usuario: dict = Depends(requiere_dashboard)):
    """Corte del día por sucursal/almacén: ventas de Punto de Venta reales
    (sin anticipos) con su forma de cobro, anticipos aparte con SU PROPIA
    forma de cobro, y total generado en pedidos. fecha_inicio/fecha_fin
    (AAAA-MM-DD, fecha_fin excluida) — normalmente el día de hoy."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.obtener_corte_dia_sucursal(config, sucursal_id, almacen_id, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (corte del día): {e}")


@app.get("/api/dashboard/descuentos-pv")
def api_dashboard_descuentos_pv(fecha: Optional[str] = None, mes: Optional[str] = None, usuario: dict = Depends(requiere_dashboard)):
    """Descuento total (en dinero) por sucursal, y los 50 descuentos más
    altos otorgados en cada una, con el cliente y el monto del ticket."""
    config = _config_microsip_o_error(usuario)
    from datetime import date, datetime, timedelta
    if mes:
        try:
            primer_dia = datetime.strptime(mes, "%Y-%m").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Mes inválido, usa el formato AAAA-MM")
        fecha_inicio = primer_dia.isoformat()
        fecha_fin_dt = date(primer_dia.year + 1, 1, 1) if primer_dia.month == 12 else date(primer_dia.year, primer_dia.month + 1, 1)
        fecha_fin = fecha_fin_dt.isoformat()
        etiqueta = mes
    else:
        if fecha:
            try:
                dia = datetime.strptime(fecha, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha inválida, usa el formato AAAA-MM-DD")
        else:
            dia = date.today()
        fecha_inicio = dia.isoformat()
        fecha_fin = (dia + timedelta(days=1)).isoformat()
        etiqueta = fecha_inicio
    try:
        resultado = microsip.obtener_descuentos_pv(config, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip (Punto de Venta): {e}")
    resultado["fecha"] = etiqueta
    return resultado


NOMBRES_ESTADO_TICKET_PDF = {"abierto": "Abierto", "en_progreso": "En progreso", "resuelto": "Resuelto", "cerrado": "Cerrado"}
NOMBRES_ESTADO_REPARACION_BITACORA = {
    "nueva": "Reparación nueva en camino", "en_diagnostico": "Recibido en diagnóstico",
    "esperando_autorizacion": "Esperando autorización",
    "en_reparacion": "En reparación", "con_proveedor": "Con proveedor", "esperando_refaccion": "Esperando refacción",
    "terminado_taller": "Terminado en taller (revisa Logística)",
    "control_calidad": "Revisión por calidad", "envio_sucursal": "Listo para envío", "en_traslado": "En traslado",
    "listo_entrega": "Entregar al cliente", "entregado": "Entregado", "cancelado": "Cancelado",
}
NOMBRES_ESTADO_LABORATORIO_BITACORA = {
    "recibido": "Recibido en sucursal", "en_laboratorio": "Entró a laboratorio", "modelado": "Modelado / diseño",
    "aprobar_diseno": "Aprobar diseño", "maquila": "Maquila (fresado)",
    "maquillado": "Maquillado / acabado", "control_calidad": "Control de calidad",
    "envio_sucursal": "Envío a sucursal", "listo_entrega": "Listo para entrega",
    "entregado": "Entregado", "cancelado": "Cancelado", "devolucion": "Devolución (por revisar)",
}
NOMBRES_METODO_PAGO_LABORATORIO = {
    "efectivo": "Efectivo", "tarjeta_debito": "Tarjeta de débito", "tarjeta_credito": "Tarjeta de crédito",
    "transferencia": "Transferencia", "otro": "Otro",
}
NOMBRES_ESTADO_ENTREGA_BITACORA = {
    "pendiente": "Pendiente", "asignada": "Asignada", "en_camino": "En camino", "en_proceso": "En proceso",
    "entregada": "Entregada", "rechazada": "Rechazada", "reagendada": "Reagendada", "cancelada": "Cancelada",
}
_CAMPOS_ENTREGA_LABELS = {
    "cliente_nombre": "nombre del cliente", "cliente_direccion": "dirección", "cliente_telefono": "teléfono",
    "equipo_descripcion": "equipo", "fecha_programada": "fecha programada", "horario": "horario",
    "vehiculo_id": "vehículo", "liga_mapa": "liga del mapa", "comentarios": "comentarios",
    "estatus_pago": "estatus de pago", "confirmado": "confirmación del cliente",
}


@app.get("/api/dashboard/reporte.pdf")
def api_dashboard_reporte_pdf(usuario: dict = Depends(requiere_dashboard)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    empresa = db.obtener_empresa(usuario["empresa_id"])
    d = db.detalle_dashboard(usuario["empresa_id"])

    ROJO = colors.HexColor("#D8192F")
    GRIS_CLARO = colors.HexColor("#F2F2F2")

    def tabla_resumen(por_estado, nombres):
        filas = [["Estado", "Cantidad"]] + [[nombres.get(e, e), str(n)] for e, n in por_estado.items()]
        t = Table(filas, colWidths=[9 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ROJO), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ]))
        return t

    def tabla_desglose(titulo_col, pares, styles):
        total = sum(n for _, n in pares) or 1
        filas = [[titulo_col, "Cantidad", "%"]] + [
            [nombre or "—", str(n), f"{n / total * 100:.0f}%"] for nombre, n in pares
        ]
        t = Table(filas, colWidths=[8 * cm, 3 * cm, 2 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#74767A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ]))
        return t

    styles = getSampleStyleSheet()
    estilo_seccion = ParagraphStyle("Seccion", parent=styles["Heading2"], fontSize=13, textColor=ROJO, spaceBefore=16, spaceAfter=6)
    estilo_sub = ParagraphStyle("Sub", parent=styles["Heading3"], fontSize=10.5, textColor=colors.HexColor("#333333"), spaceBefore=10, spaceAfter=4)

    elementos = [
        Paragraph(f"Dashboard General — {empresa['nombre'] if empresa else ''}", styles["Title"]),
        Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        HRFlowable(width="100%", thickness=1, color=ROJO, spaceBefore=8, spaceAfter=10),
    ]

    # ---- Tickets ----
    elementos.append(Paragraph(f"Tickets — {d['tickets']['total']} en total", estilo_seccion))
    elementos.append(tabla_resumen(d["tickets"]["por_estado"], NOMBRES_ESTADO_TICKET_PDF))
    elementos.append(Paragraph("Desglose por departamento", estilo_sub))
    elementos.append(tabla_desglose("Departamento", d["tickets"]["por_departamento"], styles))
    elementos.append(Paragraph("Desglose por categoría", estilo_sub))
    elementos.append(tabla_desglose("Categoría", d["tickets"]["por_categoria"], styles))

    # ---- Reparaciones ----
    elementos.append(Paragraph(f"Reparaciones — {d['reparaciones']['total']} en total", estilo_seccion))
    elementos.append(tabla_resumen(d["reparaciones"]["por_estado"], NOMBRES_ESTADO_REPARACION_PDF))
    elementos.append(Paragraph("Desglose por sucursal", estilo_sub))
    elementos.append(tabla_desglose("Sucursal", d["reparaciones"]["por_sucursal"], styles))
    elementos.append(Paragraph("Desglose por cliente (doctor)", estilo_sub))
    elementos.append(tabla_desglose("Cliente", d["reparaciones"]["por_cliente"], styles))

    # ---- Proyectos ----
    elementos.append(Paragraph(f"Proyectos — {d['proyectos']['total']} en total", estilo_seccion))
    elementos.append(tabla_resumen(d["proyectos"]["por_estado"], NOMBRES_ESTADO_PROYECTO_PDF))

    # ---- Equipos ----
    elementos.append(Paragraph(f"Equipos — {d['equipos']['total']} en total", estilo_seccion))
    elementos.append(tabla_resumen(d["equipos"]["por_estado"], NOMBRES_ESTADO_EQUIPO))
    elementos.append(Paragraph("Desglose por tipo", estilo_sub))
    elementos.append(tabla_desglose("Tipo de equipo", [(NOMBRES_TIPO_EQUIPO.get(t, t), n) for t, n in d["equipos"]["por_tipo"]], styles))

    # ---- Compras ----
    elementos.append(Paragraph(f"Compras — {d['compras']['ciclos_total']} ciclo(s) en total", estilo_seccion))
    elementos.append(tabla_resumen(d["compras"]["ciclos_por_estado"], NOMBRES_ESTADO_CICLO_PDF))
    elementos.append(Paragraph(f"{d['compras']['pedidos_total']} pedido(s) registrados en total, en todos los ciclos.", styles["Normal"]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    doc.build(elementos)
    buffer.seek(0)
    nombre_archivo = f"dashboard_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


# ---- Reportes individuales por módulo, accesibles desde el Dashboard ----
# (mismo permiso que el Dashboard: admin o master — el usuario master no puede
# entrar a cada módulo por su cuenta, pero desde aquí sí puede bajar su PDF)

def _tabla_reporte_generica(encabezados, filas, color_header="#D8192F"):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    datos = [encabezados] + filas
    t = Table(datos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color_header)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
    ]))
    return t


def _armar_pdf_simple(titulo, empresa_nombre, elementos_extra, nombre_archivo):
    from io import BytesIO
    from datetime import datetime as dt
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = [
        Paragraph(f"{titulo} — {empresa_nombre}", styles["Title"]),
        Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 16),
    ] + elementos_extra
    doc.build(elementos)
    buffer.seek(0)
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}_{dt.now().strftime('%Y%m%d')}.pdf"})


@app.get("/api/dashboard/tickets.pdf")
def api_dashboard_tickets_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    tickets = db.listar_tickets(usuario["empresa_id"])
    filas = [[t["folio"], t["departamento"], t["solicitante_nombre"], t["prioridad"],
              NOMBRES_ESTADO_TICKET_PDF.get(t["estado"], t["estado"]), t["creado_en"][:16].replace("T", " ")] for t in tickets]
    tabla = _tabla_reporte_generica(["Folio", "Departamento", "Solicitante", "Prioridad", "Estado", "Creado"], filas)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    elementos = [Paragraph(f"{len(tickets)} ticket(s) en total", getSampleStyleSheet()["Heading2"]), tabla]
    return _armar_pdf_simple("Reporte de Tickets", empresa["nombre"] if empresa else "", elementos, "tickets")


@app.get("/api/dashboard/reparaciones.pdf")
def api_dashboard_reparaciones_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    reparaciones = db.listar_reparaciones(usuario["empresa_id"])
    filas = [[r["folio"], r.get("sucursal_nombre") or "—", r["cliente_nombre"], r.get("equipo") or "—",
              NOMBRES_ESTADO_REPARACION_PDF.get(r["estado"], r["estado"]), r.get("tecnico_nombre") or "sin asignar",
              f"${r.get('costo_total', 0):,.2f}"] for r in reparaciones]
    tabla = _tabla_reporte_generica(["Folio", "Sucursal", "Cliente", "Equipo", "Estado", "Técnico", "Costo total"], filas)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    elementos = [Paragraph(f"{len(reparaciones)} reparación(es) en total", getSampleStyleSheet()["Heading2"]), tabla]
    return _armar_pdf_simple("Reporte de Reparaciones", empresa["nombre"] if empresa else "", elementos, "reparaciones")


@app.get("/api/dashboard/proyectos.pdf")
def api_dashboard_proyectos_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    proyectos = db.listar_proyectos(usuario["empresa_id"], None)
    filas = []
    for p in proyectos:
        participantes = ", ".join(
            [u["nombre_completo"] for u in p.get("participantes_usuarios", [])] + p.get("participantes_departamentos", [])
        ) or "—"
        filas.append([p["nombre"], NOMBRES_ESTADO_PROYECTO_PDF.get(p["estado"], p["estado"]), participantes])
    tabla = _tabla_reporte_generica(["Nombre", "Estado", "Participantes"], filas)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    elementos = [Paragraph(f"{len(proyectos)} proyecto(s) en total", getSampleStyleSheet()["Heading2"]), tabla]
    return _armar_pdf_simple("Reporte de Proyectos", empresa["nombre"] if empresa else "", elementos, "proyectos")


@app.get("/api/dashboard/equipos.pdf")
def api_dashboard_equipos_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    equipos = db.listar_equipos(usuario["empresa_id"])
    filas = [[e["nombre"], NOMBRES_TIPO_EQUIPO.get(e["tipo"], e["tipo"]),
              " / ".join(filter(None, [e.get("marca"), e.get("modelo")])) or "—",
              e.get("responsable") or "—", NOMBRES_ESTADO_EQUIPO.get(e["estado"], e["estado"])] for e in equipos]
    tabla = _tabla_reporte_generica(["Nombre", "Tipo", "Marca/Modelo", "Responsable", "Estado"], filas)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    elementos = [Paragraph(f"{len(equipos)} equipo(s) en total", getSampleStyleSheet()["Heading2"]), tabla]
    return _armar_pdf_simple("Reporte de Equipos", empresa["nombre"] if empresa else "", elementos, "equipos")


@app.get("/api/dashboard/compras.pdf")
def api_dashboard_compras_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    ciclos = db.listar_ciclos_compra(usuario["empresa_id"])
    filas = [[c["nombre"], NOMBRES_FRECUENCIA_COMPRA_PDF.get(c["frecuencia"], c["frecuencia"]),
              NOMBRES_ESTADO_CICLO_PDF.get(c["estado"], c["estado"]), c["fecha_programada"][:10]] for c in ciclos]
    tabla = _tabla_reporte_generica(["Ciclo", "Frecuencia", "Estado", "Fecha programada"], filas)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    elementos = [Paragraph(f"{len(ciclos)} ciclo(s) en total", getSampleStyleSheet()["Heading2"]), tabla]
    return _armar_pdf_simple("Reporte de Compras", empresa["nombre"] if empresa else "", elementos, "compras")


@app.get("/api/dashboard/rh.pdf")
def api_dashboard_rh_pdf(usuario: dict = Depends(requiere_dashboard)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    elementos = _elementos_reporte_rh_por_empleado(usuario["empresa_id"])
    return _armar_pdf_simple("Reporte de Recursos Humanos", empresa["nombre"] if empresa else "", elementos, "incidencias_rh")


# ==================== USUARIOS (dentro de la empresa, admin) ====================

class NuevoUsuario(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6)
    nombre_completo: str = Field(min_length=1, max_length=120)
    rol: str
    telefono_whatsapp: Optional[str] = None
    puesto: Optional[str] = None
    sucursal_id: Optional[int] = None
    numero_empleado: Optional[str] = None
    empleado_prueba_id: Optional[int] = None


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
    acceso_compras: Optional[bool] = None
    acceso_rh: Optional[bool] = None
    acceso_dashboard: Optional[bool] = None
    acceso_tickets: Optional[bool] = None
    acceso_reparaciones: Optional[bool] = None
    acceso_laboratorio: Optional[bool] = None
    acceso_laboratorio_entrega: Optional[bool] = None
    acceso_logistica_reparaciones: Optional[bool] = None
    acceso_proyectos: Optional[bool] = None
    admin_proyectos: Optional[bool] = None
    acceso_checador: Optional[bool] = None
    acceso_entregas: Optional[bool] = None
    acceso_checador_precio: Optional[bool] = None
    acceso_inventarios: Optional[bool] = None
    acceso_marketing: Optional[bool] = None
    acceso_crm: Optional[bool] = None
    acceso_asistente_ia: Optional[bool] = None
    acceso_datos_empleado_rh: Optional[bool] = None
    acceso_monitoreo: Optional[bool] = None
    acceso_shopify: Optional[bool] = None
    acceso_turnos: Optional[bool] = None
    acceso_soporte: Optional[bool] = None
    ventanilla_turnos: Optional[str] = None
    monitoreo_activo: Optional[bool] = None
    sucursal_id: Optional[int] = None
    numero_empleado: Optional[str] = None
    rfc: Optional[str] = None
    curp: Optional[str] = None
    numero_licencia: Optional[str] = None
    tipo_licencia: Optional[str] = None
    vigencia_licencia: Optional[str] = None


@app.get("/api/usuarios")
def api_listar_usuarios(usuario: dict = Depends(requiere_admin_completo)):
    return db.listar_usuarios(usuario["empresa_id"])


@app.post("/api/monitoreo/aceptar")
def api_aceptar_monitoreo(request: Request, usuario: dict = Depends(requiere_empresa_o_master)):
    """El usuario acepta el aviso de monitoreo — queda registrado con
    fecha/hora e IP como prueba. Se puede llamar sin que el monitoreo
    esté activo (no pasa nada raro), aunque normalmente solo se llama
    desde la pantalla de aviso que solo sale si sí está activo."""
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else None)
    db.registrar_aceptacion_monitoreo(usuario["id"], ip)
    return {"ok": True}


@app.post("/api/monitoreo/usuarios/{usuario_id}/token")
def api_generar_token_monitoreo(usuario_id: int, admin: dict = Depends(requiere_acceso_monitoreo)):
    """Genera un token nuevo (invalida el anterior si había uno) para
    que el agente de Windows de esa persona se identifique. Se muestra
    UNA sola vez en el frontend — cópialo al agente en ese momento."""
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    token = db.generar_token_monitoreo(usuario_id)
    return {"token": token}


def requiere_token_monitoreo(x_monitoreo_token: str = Header(None)) -> dict:
    """Autenticación propia del agente de Windows — no usa sesión de
    usuario normal (JWT), usa el token generado desde Administrar."""
    if not x_monitoreo_token:
        raise HTTPException(status_code=401, detail="Falta el token de monitoreo (header X-Monitoreo-Token)")
    datos = db.obtener_usuario_por_token_monitoreo(x_monitoreo_token)
    if not datos:
        raise HTTPException(status_code=401, detail="Token de monitoreo inválido")
    if not datos.get("monitoreo_activo"):
        raise HTTPException(status_code=403, detail="El monitoreo está desactivado para este usuario")
    return datos


class EventoMonitoreo(BaseModel):
    tipo: str
    detalle: str
    fecha_hora: Optional[str] = None


class LoteEventosMonitoreo(BaseModel):
    computadora: str
    eventos: List[EventoMonitoreo]


@app.post("/api/monitoreo/eventos")
def api_registrar_eventos_monitoreo(payload: LoteEventosMonitoreo, datos: dict = Depends(requiere_token_monitoreo)):
    """El agente de Windows llama esto para subir eventos en lote —
    autenticado con su token propio, no con sesión de usuario."""
    db.registrar_eventos_monitoreo(datos["id"], datos["empresa_id"], payload.computadora,
                                    [e.dict() for e in payload.eventos])
    return {"ok": True, "recibidos": len(payload.eventos)}


@app.get("/api/monitoreo/eventos")
def api_listar_eventos_monitoreo(usuario_id: Optional[int] = None, computadora: Optional[str] = None,
                                  tipo: Optional[str] = None, fecha_inicio: Optional[str] = None,
                                  fecha_fin: Optional[str] = None, admin: dict = Depends(requiere_acceso_monitoreo)):
    """Bitácora de monitoreo — filtrable por persona/computadora/tipo/fecha."""
    return db.listar_eventos_monitoreo(admin["empresa_id"], usuario_id, computadora, tipo, fecha_inicio, fecha_fin)


@app.get("/api/monitoreo/computadoras")
def api_listar_computadoras_monitoreo(admin: dict = Depends(requiere_acceso_monitoreo)):
    """Nombres de computadoras que ya han mandado algún evento, para el
    filtro de la bitácora."""
    return db.listar_computadoras_monitoreo(admin["empresa_id"])


@app.get("/api/monitoreo/estado")
def api_estado_monitoreo(admin: dict = Depends(requiere_acceso_monitoreo)):
    """Última actividad y si está "en línea" (últimos 10 min), por cada
    persona monitoreada."""
    return db.listar_estado_monitoreo(admin["empresa_id"])


@app.get("/api/usuarios/tecnicos")
def api_listar_tecnicos(usuario: dict = Depends(requiere_empresa)):
    return db.listar_tecnicos_activos(usuario["empresa_id"])


@app.get("/api/usuarios/todos")
def api_listar_usuarios_activos(usuario: dict = Depends(requiere_empresa)):
    return db.listar_usuarios_activos(usuario["empresa_id"])


@app.post("/api/usuarios")
def api_crear_usuario(payload: NuevoUsuario, admin: dict = Depends(requiere_admin_completo)):
    if payload.rol not in ("admin", "tecnico", "usuario", "master", "almacen", "encargado_sucursal", "instalador"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.obtener_usuario_por_username(payload.username):
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    if payload.sucursal_id and not db.obtener_sucursal_reparacion(admin["empresa_id"], payload.sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    numero_empleado = payload.numero_empleado
    empleado_prueba = None
    if payload.empleado_prueba_id:
        empleado_prueba = db.obtener_empleado_prueba(admin["empresa_id"], payload.empleado_prueba_id)
        if not empleado_prueba:
            raise HTTPException(status_code=404, detail="Empleado en prueba no encontrado en tu empresa")
        if empleado_prueba.get("usuario_id"):
            raise HTTPException(status_code=400, detail="Ese empleado en prueba ya tiene una cuenta de usuario")
        # Si no se capturó número de empleado a mano pero el empleado en
        # prueba ya se dio de alta en Microsip, se usa ese automáticamente.
        if not numero_empleado and empleado_prueba.get("numero_empleado_microsip"):
            numero_empleado = empleado_prueba["numero_empleado_microsip"]

    if numero_empleado:
        duplicado = db.obtener_usuario_activo_por_numero_empleado(admin["empresa_id"], numero_empleado)
        if duplicado:
            raise HTTPException(status_code=400, detail=f"Ese número de empleado ya lo tiene {duplicado['nombre_completo']} ({duplicado['username']})")

    uid = db.crear_usuario(admin["empresa_id"], payload.username, payload.password, payload.nombre_completo,
                            payload.rol, payload.telefono_whatsapp, payload.puesto, payload.sucursal_id,
                            numero_empleado)
    if empleado_prueba:
        db.vincular_usuario_empleado_prueba(empleado_prueba["id"], uid)
    return {"id": uid}


@app.patch("/api/usuarios/{usuario_id}")
def api_actualizar_usuario(usuario_id: int, payload: ActualizacionUsuario, admin: dict = Depends(requiere_admin_completo)):
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if payload.rol and payload.rol not in ("admin", "tecnico", "usuario", "master", "almacen", "encargado_sucursal", "instalador"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if payload.sucursal_id and not db.obtener_sucursal_reparacion(admin["empresa_id"], payload.sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    enviados = payload.dict(exclude_unset=True)
    if "numero_empleado" in enviados and payload.numero_empleado:
        duplicado = db.obtener_usuario_activo_por_numero_empleado(admin["empresa_id"], payload.numero_empleado, excluir_id=usuario_id)
        if duplicado:
            raise HTTPException(status_code=400, detail=f"Ese número de empleado ya lo tiene {duplicado['nombre_completo']} ({duplicado['username']})")
    kwargs_extra = {}
    if "restriccion_categoria" in enviados:
        kwargs_extra["restriccion_categoria"] = payload.restriccion_categoria  # puede ser None para quitarla
    if "sucursal_id" in enviados:
        kwargs_extra["sucursal_id"] = payload.sucursal_id  # puede ser None para quitarla
    if "numero_empleado" in enviados:
        kwargs_extra["numero_empleado"] = payload.numero_empleado  # puede ser None para quitarlo
    if "rfc" in enviados:
        kwargs_extra["rfc"] = payload.rfc
    if "curp" in enviados:
        kwargs_extra["curp"] = payload.curp
    if "numero_licencia" in enviados:
        kwargs_extra["numero_licencia"] = payload.numero_licencia
    if "tipo_licencia" in enviados:
        kwargs_extra["tipo_licencia"] = payload.tipo_licencia
    if "vigencia_licencia" in enviados:
        kwargs_extra["vigencia_licencia"] = payload.vigencia_licencia
    if "ventanilla_turnos" in enviados:
        kwargs_extra["ventanilla_turnos"] = payload.ventanilla_turnos  # puede ser None para quitarla

    # "Recibir/Entregar Lab." es un permiso DENTRO del módulo Laboratorio: si se
    # da, se prende también el módulo (si no, la persona no lo ve ni en la web
    # ni en la app aunque tenga el permiso).
    if payload.acceso_laboratorio_entrega is True:
        payload.acceso_laboratorio = True
    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,
                           payload.activo, payload.password, payload.puesto,
                           acceso_equipos=payload.acceso_equipos, acceso_administracion=payload.acceso_administracion,
                           acceso_compras=payload.acceso_compras, acceso_rh=payload.acceso_rh,
                           acceso_dashboard=payload.acceso_dashboard, acceso_tickets=payload.acceso_tickets,
                           acceso_reparaciones=payload.acceso_reparaciones, acceso_laboratorio=payload.acceso_laboratorio,
                           acceso_laboratorio_entrega=payload.acceso_laboratorio_entrega, acceso_entregas=payload.acceso_entregas,
                           acceso_logistica_reparaciones=payload.acceso_logistica_reparaciones,
                           acceso_proyectos=payload.acceso_proyectos, admin_proyectos=payload.admin_proyectos,
                           acceso_checador=payload.acceso_checador,
                           acceso_checador_precio=payload.acceso_checador_precio,
                           acceso_inventarios=payload.acceso_inventarios,
                           acceso_marketing=payload.acceso_marketing,
                           acceso_crm=payload.acceso_crm,
                           acceso_asistente_ia=payload.acceso_asistente_ia,
                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,
                           acceso_monitoreo=payload.acceso_monitoreo,
                           acceso_shopify=payload.acceso_shopify,
                           acceso_turnos=payload.acceso_turnos,
                           acceso_soporte=payload.acceso_soporte,
                           monitoreo_activo=payload.monitoreo_activo,
                           **kwargs_extra)
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


@app.delete("/api/usuarios/{usuario_id}/permanente")
def api_eliminar_usuario_permanente(usuario_id: int, admin: dict = Depends(requiere_admin_completo)):
    if usuario_id == admin["id"]:
        raise HTTPException(status_code=400, detail="No puedes borrarte a ti mismo")
    objetivo = next((u for u in db.listar_usuarios(admin["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    try:
        db.eliminar_usuario_permanente(usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    if usuario["rol"] == "superadmin":
        return True
    return ticket["solicitante_id"] == usuario["id"]


@app.get("/api/tickets")
def api_listar_tickets(estado: Optional[str] = None, prioridad: Optional[str] = None, categoria: Optional[str] = None,
                        departamento: Optional[str] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                        tecnico_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_tickets)):
    # Solo sistemas (admin y técnicos) ve tickets de otros; cualquier otro rol
    # (encargadas, instaladores, etc.) ve únicamente los que él levantó.
    solicitante_id = usuario["id"] if usuario["rol"] not in ("admin", "tecnico", "superadmin") else None
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
def api_detalle_ticket(ticket_id: int, usuario: dict = Depends(requiere_ver_tickets)):
    ticket = db.obtener_ticket(ticket_id, empresa_id=usuario["empresa_id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _puede_ver_ticket(usuario, ticket):
        raise HTTPException(status_code=403, detail="No puedes ver este ticket")
    return ticket


@app.post("/api/tickets")
def api_crear_ticket(payload: NuevoTicket, usuario: dict = Depends(requiere_ver_tickets)):
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
    notifications.notificar_nuevo_ticket(usuario["empresa_id"], tecnicos, ticket)
    if ticket.get("asignado_a_id"):
        tecnico_asignado = next((t for t in tecnicos if t["id"] == ticket["asignado_a_id"]), None)
        if tecnico_asignado:
            notifications.notificar_asignacion(usuario["empresa_id"], tecnico_asignado, ticket)
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
            notifications.notificar_asignacion(usuario["empresa_id"], tecnico, ticket)
    if payload.estado and payload.estado != ticket_antes.get("estado"):
        avisos.avisar_seguro([ticket_antes.get("solicitante_id")], f"🎫 Tu ticket {ticket_antes.get('folio', '')}",
                             f"Ahora está: {payload.estado.replace('_', ' ')}", modulo="tickets", ref=ticket_id,
                             excluir=[usuario["id"]])

    return ticket


@app.delete("/api/tickets/{ticket_id}")
def api_eliminar_ticket(ticket_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_ticket(usuario["empresa_id"], ticket_id):
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return {"ok": True}


MAX_ADJUNTO_BASE64 = 7_000_000  # ~5MB de archivo real (base64 pesa ~33% más)
MAX_DISENO_ARCHIVO_BYTES = 90 * 1024 * 1024  # ~90MB de archivo real -- subido desde 30MB porque una arcada completa (2 archivos STL de alta resolución) se acerca a ese tamaño; el espacio se libera solo al entregar el trabajo (ver registrar_entrega_laboratorio en db.py). Se mide en bytes reales del archivo (ya no en caracteres de texto base64) porque el endpoint recibe el archivo como multipart, no metido en JSON -- ver api_subir_diseno_laboratorio.


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
    comentario = db.agregar_comentario(ticket_id, usuario["id"], payload.texto,
                                       payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)
    # Al otro lado: si comenta quien lo pidió, al técnico asignado (o a los
    # técnicos si nadie lo tiene); si comenta el técnico, a quien lo pidió.
    if usuario["id"] == ticket.get("solicitante_id"):
        destino = [ticket["asignado_a_id"]] if ticket.get("asignado_a_id") else \
            [t["id"] for t in db.listar_tecnicos_activos(usuario["empresa_id"])]
    else:
        destino = [ticket.get("solicitante_id"), ticket.get("asignado_a_id")]
    avisos.avisar_seguro(destino, f"💬 {usuario.get('nombre') or usuario.get('nombre_completo') or 'Comentario'} en {ticket.get('folio', '')}",
                         (payload.texto or "📎 Archivo adjunto")[:200], modulo="tickets", ref=ticket_id, excluir=[usuario["id"]])
    return comentario


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
    sucursal_id: Optional[int] = None
    usuario_id: Optional[int] = None
    usuario_microsip: Optional[str] = None
    password_microsip: Optional[str] = None


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
    sucursal_id: Optional[int] = None
    usuario_id: Optional[int] = None
    usuario_microsip: Optional[str] = None
    password_microsip: Optional[str] = None


CAMPOS_EQUIPO_SOLO_ADMIN = ["sucursal_id", "sucursal_nombre", "departamento", "usuario_id", "usuario_nombre", "usuario_microsip", "password_microsip"]


def _filtrar_equipo_por_rol(equipo, rol):
    if rol == "admin":
        return equipo
    return {k: v for k, v in equipo.items() if k not in CAMPOS_EQUIPO_SOLO_ADMIN}


@app.get("/api/equipos")
def api_listar_equipos(tipo: Optional[str] = None, estado: Optional[str] = None, usuario: dict = Depends(requiere_acceso_equipos)):
    equipos = db.listar_equipos(usuario["empresa_id"], tipo, estado)
    return [_filtrar_equipo_por_rol(e, usuario["rol"]) for e in equipos]


def _agrupar_equipos_por_departamento(equipos):
    grupos = {}
    for e in equipos:
        depto = e.get("departamento") or "Sin departamento"
        grupos.setdefault(depto, []).append(e)
    return dict(sorted(grupos.items()))


NOMBRES_TIPO_EQUIPO = {
    "computadora": "Computadora", "laptop": "Laptop", "monitor": "Monitor", "impresora": "Impresora",
    "escaner": "Escáner", "servidor": "Servidor",
    "mouse": "Mouse", "mouse_inalambrico": "Mouse inalámbrico", "teclado": "Teclado", "teclado_inalambrico": "Teclado inalámbrico",
    "router": "Router", "switch": "Switch", "modem": "Módem", "punto_acceso": "Punto de acceso (WiFi)",
    "dvr": "DVR", "camara_seguridad": "Cámara de seguridad", "no_break": "No-break (UPS)", "regulador": "Regulador de voltaje",
    "telefono": "Teléfono", "telefono_ip": "Teléfono IP", "proyector": "Proyector", "bocinas": "Bocinas", "microfono": "Micrófono",
    "tablet": "Tablet", "lector_codigo_barras": "Lector de código de barras", "disco_duro_externo": "Disco duro externo",
    "red": "Red", "otro": "Otro",
}
NOMBRES_ESTADO_EQUIPO = {
    "nuevo": "Nuevo", "buen_estado": "Buen estado", "sugerencia_cambio": "Sugerencia de cambio",
    "en_proceso_cambio": "En proceso de cambio", "cambio_urgente": "Cambio urgente", "baja": "Baja",
}


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
    if usuario["rol"] != "admin":
        payload.sucursal_id = None
        payload.departamento = None
        payload.usuario_id = None
        payload.usuario_microsip = None
        payload.password_microsip = None
    if payload.sucursal_id and not db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if payload.usuario_id and not any(u["id"] == payload.usuario_id for u in db.listar_usuarios(usuario["empresa_id"])):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    equipo = db.crear_equipo(usuario["empresa_id"], payload.tipo, payload.nombre, payload.marca, payload.modelo,
                              payload.numero_serie, payload.departamento, payload.responsable,
                              payload.fecha_adquisicion, payload.notas, payload.sucursal_id,
                              payload.usuario_id, payload.usuario_microsip, payload.password_microsip)
    return _filtrar_equipo_por_rol(equipo, usuario["rol"])


@app.patch("/api/equipos/{equipo_id}")
def api_actualizar_equipo(equipo_id: int, payload: ActualizacionEquipo, usuario: dict = Depends(requiere_acceso_equipos)):
    if not db.obtener_equipo(usuario["empresa_id"], equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if payload.tipo and payload.tipo not in db.TIPOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Tipo de equipo inválido")
    if payload.estado and payload.estado not in db.ESTADOS_EQUIPO:
        raise HTTPException(status_code=400, detail="Estado de equipo inválido")
    datos = payload.dict(exclude_unset=True)
    if usuario["rol"] != "admin":
        for campo in ("sucursal_id", "departamento", "usuario_id", "usuario_microsip", "password_microsip"):
            datos.pop(campo, None)
    if datos.get("sucursal_id") and not db.obtener_sucursal_reparacion(usuario["empresa_id"], datos["sucursal_id"]):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if datos.get("usuario_id") and not any(u["id"] == datos["usuario_id"] for u in db.listar_usuarios(usuario["empresa_id"])):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    equipo = db.actualizar_equipo(usuario["empresa_id"], equipo_id, **datos)
    return _filtrar_equipo_por_rol(equipo, usuario["rol"])


@app.get("/api/equipos/{equipo_id}")
def api_detalle_equipo(equipo_id: int, usuario: dict = Depends(requiere_empresa)):
    """Detalle de un solo equipo — cualquier persona de la empresa puede
    consultarlo (por ejemplo, para ver el texto de su propia responsiva antes
    de firmarla, sin necesitar acceso al módulo completo de Equipos)."""
    equipo = db.obtener_equipo(usuario["empresa_id"], equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@app.get("/api/equipos/{equipo_id}/carta-responsiva.pdf")
def api_carta_responsiva_equipo(equipo_id: int, usuario: dict = Depends(requiere_acceso_equipos)):
    equipo = db.obtener_equipo(usuario["empresa_id"], equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_equipos.generar_carta_responsiva(equipo, empresa)
    nombre_archivo = f"Carta_Responsiva_{(equipo.get('nombre') or 'equipo')[:30].replace(' ', '_')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


class FirmaResponsivaEquipo(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.post("/api/equipos/{equipo_id}/firmar-responsiva")
def api_firmar_responsiva_equipo(equipo_id: int, payload: FirmaResponsivaEquipo, usuario: dict = Depends(requiere_empresa)):
    """Cualquier persona puede firmar la responsiva del equipo que TIENE
    asignado a su nombre — no hace falta ser admin/técnico para esto, es su
    propio compromiso de resguardo. El administrador también puede firmarla
    en su nombre si hace falta (ej. la persona no tiene acceso al sistema)."""
    equipo = db.obtener_equipo(usuario["empresa_id"], equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if usuario["rol"] != "admin" and equipo.get("usuario_id") != usuario["id"]:
        raise HTTPException(status_code=403, detail="Este equipo no está asignado a tu nombre")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    return db.firmar_responsiva_equipo(usuario["empresa_id"], equipo_id, payload.firma_base64)


# ---- Notificaciones push: las apps registran aquí el token de su celular ----

class TokenPushIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    app: Optional[str] = None          # "markinc" | "lab"
    plataforma: Optional[str] = None   # "android" | "ios"


@app.post("/api/push/token")
def api_guardar_token_push(payload: TokenPushIn, usuario: dict = Depends(auth.get_current_user)):
    if usuario.get("rol") == "superadmin" or not usuario.get("empresa_id"):
        return {"ok": False}
    db.guardar_token_push(usuario["id"], payload.token, payload.app, payload.plataforma)
    return {"ok": True, "push_configurado": push_notifications.configurado()}


@app.get("/api/push/mis-dispositivos")
def api_mis_dispositivos_push(usuario: dict = Depends(auth.get_current_user)):
    return {"configurado": push_notifications.configurado(), "dispositivos": db.dispositivos_push_de_usuario(usuario["id"])}


@app.post("/api/push/prueba")
def api_prueba_push(usuario: dict = Depends(auth.get_current_user)):
    """Manda una notificación de prueba a MIS celulares y dice qué pasó con
    cada uno (para revisar por qué no llegan)."""
    if not push_notifications.configurado():
        return {"ok": False, "motivo": "El servidor no tiene FIREBASE_SERVICE_ACCOUNT_JSON (Render → Environment).", "resultados": []}
    tokens = db.tokens_push_de_usuarios([usuario["id"]])
    if not tokens:
        return {"ok": False, "motivo": "Tu cuenta no tiene ningún celular registrado: abre la app nueva, inicia sesión y "
                                       "acepta las notificaciones.", "resultados": []}
    resultados = []
    for t in tokens:
        estado, detalle = push_notifications.enviar_detalle(t, "🔔 Prueba de notificaciones",
                                                            "Si ves esto, las notificaciones de Mark·Inc funcionan.",
                                                            {"modulo": "", "ref": ""})
        if estado == "invalido":
            db.quitar_token_push(t)
        resultados.append({"token": t[-8:], "estado": estado, "detalle": detalle[:300]})
    return {"ok": any(r["estado"] == "ok" for r in resultados), "resultados": resultados}


@app.post("/api/push/quitar")
def api_quitar_token_push(payload: TokenPushIn, usuario: dict = Depends(auth.get_current_user)):
    """Al cerrar sesión: ese celular deja de recibir avisos de esta cuenta."""
    db.quitar_token_push(payload.token)
    return {"ok": True}


# ---- Anuncios de RH (notificación a todos o a sucursales/departamentos) ----

class NuevoAnuncioIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)
    texto: Optional[str] = Field(default=None, max_length=4000)
    imagen_base64: Optional[str] = None
    audiencia_tipo: Literal["todos", "segmentado"] = "todos"
    sucursales: List[int] = []
    departamentos: List[str] = []
    vigente_hasta: Optional[str] = None


@app.get("/api/anuncios")
def api_mis_anuncios(usuario: dict = Depends(requiere_empresa_o_master)):
    return db.anuncios_para_usuario(usuario["empresa_id"], usuario["id"])


@app.get("/api/rh/anuncios")
def api_listar_anuncios_rh(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.listar_anuncios(usuario["empresa_id"])


@app.post("/api/rh/anuncios")
def api_crear_anuncio_rh(payload: NuevoAnuncioIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """RH publica un anuncio (un evento, un aviso…): se guarda para verse en
    Bienvenido y se manda como notificación a quien le toca."""
    if payload.imagen_base64 and len(payload.imagen_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La imagen pesa demasiado (máximo 5MB)")
    if payload.audiencia_tipo == "segmentado" and not payload.sucursales and not payload.departamentos:
        raise HTTPException(status_code=400, detail="Elige al menos una sucursal o un departamento (o mándalo a todos).")
    titulo = payload.titulo.strip()
    texto = _limpio(payload.texto)
    nuevo = db.crear_anuncio(usuario["empresa_id"], titulo, texto, payload.imagen_base64 or None, payload.audiencia_tipo,
                             payload.sucursales, payload.departamentos, _limpio(payload.vigente_hasta), usuario["id"])
    ids = db.destinatarios_anuncio(usuario["empresa_id"], payload.audiencia_tipo, payload.sucursales, payload.departamentos)
    db.marcar_anuncio_enviados(nuevo, len(ids))
    avisos.avisar_seguro(ids, f"📣 {titulo}", (texto or "Toca para verlo.")[:300], modulo="capacitacion", ref=nuevo,
                         extra={"pantalla": "anuncio"})
    return {"id": nuevo, "enviados": len(ids), "push_configurado": push_notifications.configurado()}


@app.delete("/api/rh/anuncios/{anuncio_id}")
def api_borrar_anuncio_rh(anuncio_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.borrar_anuncio(usuario["empresa_id"], anuncio_id):
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    return {"ok": True}


@app.get("/api/mis-pendientes")
def api_mis_pendientes(usuario: dict = Depends(requiere_empresa)):
    """Todo lo que le falta resolver a esta persona en un solo lugar: equipos con
    responsiva sin firmar, proyectos esperando su firma de compromiso, tareas de
    proyecto que tiene asignadas y sin terminar, y mantenimientos de vehículo que
    le tocan — para el apartado 'Mis tareas'."""
    equipos_pendientes = db.listar_equipos_pendientes_firma(usuario["empresa_id"], usuario["id"])
    proyectos_pendientes = db.listar_proyectos_pendientes_firma_usuario(usuario["empresa_id"], usuario["id"])
    tareas_pendientes = db.listar_tareas_proyecto_usuario(usuario["empresa_id"], usuario["id"])
    mantenimientos_vehiculo_pendientes = db.listar_mantenimientos_vehiculo_pendientes_usuario(usuario["empresa_id"], usuario["id"])
    return {
        "equipos_pendientes": equipos_pendientes,
        "proyectos_pendientes": proyectos_pendientes,
        "tareas_pendientes": tareas_pendientes,
        "mantenimientos_vehiculo_pendientes": mantenimientos_vehiculo_pendientes,
    }


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

_RE_HORA = r"^([01]\d|2[0-3]):[0-5]\d$"
_RE_FECHA = r"^\d{4}-\d{2}-\d{2}$"


class NuevaTareaProyecto(BaseModel):
    usuario_ids: List[int] = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    fecha_limite: Optional[str] = None
    hora_limite: Optional[str] = Field(default=None, pattern=_RE_HORA)


class EdicionTareaProyecto(BaseModel):
    descripcion: Optional[str] = None
    fecha_limite: Optional[str] = None  # "" = quitar
    hora_limite: Optional[str] = None   # "" = quitar


class AsignarUsuariosTarea(BaseModel):
    usuario_ids: List[int]


class NuevoProyecto(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    descripcion: Optional[str] = None
    fecha_estimada: Optional[str] = None
    inicio_plan: Optional[str] = Field(default=None, pattern=_RE_FECHA)
    hora_inicio_plan: Optional[str] = Field(default=None, pattern=_RE_HORA)
    hora_entrega: Optional[str] = Field(default=None, pattern=_RE_HORA)
    participantes_usuarios: Optional[list[int]] = None
    participantes_departamentos: Optional[list[str]] = None
    tareas: Optional[list[NuevaTareaProyecto]] = None


class ActualizacionProyecto(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_estimada: Optional[str] = None
    inicio_plan: Optional[str] = None
    hora_inicio_plan: Optional[str] = None
    hora_entrega: Optional[str] = None


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


def _avisar_proyecto(usuario, proyecto, titulo, cuerpo, solo=None):
    """Aviso a la gente del proyecto (participantes + quien lo creó), menos a
    quien hizo el cambio. `solo`: mandar únicamente a esos ids."""
    if not proyecto:
        return
    ids = solo if solo is not None else \
        [p["id"] for p in proyecto.get("participantes_usuarios") or []] + [proyecto.get("creado_por_id")]
    avisos.avisar_seguro(ids, titulo, cuerpo, modulo="proyectos", ref=proyecto.get("id"), excluir=[usuario["id"]])


def _puede_mover_tareas(usuario, proyecto):
    return usuario.get("rol") == "admin" or usuario["id"] == proyecto.get("creado_por_id")


def _puede_ver_proyecto(usuario, proyecto):
    if usuario["rol"] == "admin" or usuario["id"] == proyecto.get("creado_por_id"):
        return True
    return any(p["id"] == usuario["id"] for p in proyecto["participantes_usuarios"])


def _bitacora_proyecto(proyecto_id, usuario, texto):
    """Renglón automático en la bitácora del proyecto (la misma lista de
    avances/comentarios), para que quede registro de cada cambio."""
    try:
        db.agregar_actualizacion_proyecto(proyecto_id, usuario["id"], f"📝 {texto}")
    except Exception as e:  # la bitácora nunca debe tumbar la acción
        print(f"[bitacora proyecto {proyecto_id}] {e}")


def _cuando(fecha, hora=None):
    """'2026-10-20' + '09:30' → '20/10/2026 09:30' (para avisos y bitácora)."""
    if not fecha:
        return ""
    f = str(fecha)[:10]
    try:
        f = date.fromisoformat(f).strftime("%d/%m/%Y")
    except ValueError:
        pass
    return f"{f} {hora}".strip() if hora else f


def _nombres_usuarios(proyecto, ids):
    nombres = {p["id"]: p["nombre_completo"] for p in proyecto.get("participantes_usuarios") or []}
    return ", ".join(nombres.get(i, f"#{i}") for i in ids)


@app.get("/api/proyectos")
def api_listar_proyectos(estado: Optional[str] = None, usuario: dict = Depends(requiere_ver_proyectos)):
    # El administrador ve todos; los demás, donde participan o los que crearon.
    participante_id = None if usuario["rol"] == "admin" else usuario["id"]
    return db.listar_proyectos(usuario["empresa_id"], participante_id, estado)


@app.post("/api/proyectos")
def api_crear_proyecto(payload: NuevoProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    participantes_usuarios = list(payload.participantes_usuarios or [])
    if usuario["rol"] == "tecnico" and usuario["id"] not in participantes_usuarios:
        participantes_usuarios.append(usuario["id"])  # para que quien lo crea siempre lo pueda ver después
    if payload.tareas:
        ids_invalidos = [uid for t in payload.tareas for uid in t.usuario_ids if uid not in participantes_usuarios]
        if ids_invalidos:
            raise HTTPException(status_code=400, detail="No puedes asignar una tarea a alguien que no es participante del proyecto")
    tareas = [t.dict() for t in payload.tareas] if payload.tareas else None
    proyecto_id = db.crear_proyecto(
        usuario["empresa_id"], payload.nombre, payload.descripcion, payload.fecha_estimada, usuario["id"],
        participantes_usuarios, payload.participantes_departamentos, tareas,
        inicio_plan=payload.inicio_plan, hora_inicio_plan=payload.hora_inicio_plan, hora_entrega=payload.hora_entrega,
    )
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    inicio = _cuando(payload.inicio_plan, payload.hora_inicio_plan)
    entrega = _cuando(payload.fecha_estimada, payload.hora_entrega)
    # Bitácora: nace con el proyecto.
    renglones = [f"Proyecto creado por {usuario.get('nombre', '')}."]
    if inicio:
        renglones.append(f"Inicio: {inicio}.")
    if entrega:
        renglones.append(f"Entrega: {entrega}.")
    if participantes_usuarios:
        renglones.append(f"Participantes: {_nombres_usuarios(proyecto, participantes_usuarios)}.")
    for t in payload.tareas or []:
        renglones.append(f"Tarea \"{t.descripcion.strip()[:120]}\" para {_nombres_usuarios(proyecto, t.usuario_ids)}"
                         + (f", límite {_cuando(t.fecha_limite, t.hora_limite)}" if t.fecha_limite else "") + ".")
    _bitacora_proyecto(proyecto_id, usuario, "\n".join(renglones))
    # Aviso a cada participante, con sus tareas.
    fechas = " · ".join(x for x in [f"Inicio {inicio}" if inicio else "", f"Entrega {entrega}" if entrega else ""] if x)
    for uid in set(participantes_usuarios):
        if uid == usuario["id"]:
            continue
        mias = [t for t in payload.tareas or [] if uid in t.usuario_ids]
        texto = f"{usuario.get('nombre', '')} te agregó al proyecto." + (f" {fechas}." if fechas else "")
        if mias:
            texto += " Tus tareas: " + "; ".join(
                t.descripcion.strip()[:60] + (f" ({_cuando(t.fecha_limite, t.hora_limite)})" if t.fecha_limite else "") for t in mias)
        texto += " Falta tu firma de conformidad."
        _avisar_proyecto(usuario, proyecto, f"📋 Nuevo proyecto: {payload.nombre}", texto[:350], solo=[uid])
    return {"id": proyecto_id}


# ---- 🎙️ Proyecto desde una reunión (minuta con IA) ----
# Se graba o sube el audio; Gemini lo escucha y regresa resumen, puntos clave,
# acuerdos, conclusión y tareas por persona. El audio no se guarda (solo vive
# en memoria mientras se procesa). Como puede tardar varios minutos, se procesa
# en segundo plano y la página pregunta cada pocos segundos.

MAX_AUDIO_MINUTA = 200 * 1024 * 1024


def _procesar_minuta(minuta_id, audio, nombre, participantes, contexto):
    import minuta_ia
    try:
        r = minuta_ia.analizar_reunion(audio, nombre, participantes, contexto, db.ahora().date())
        db.terminar_minuta(minuta_id, resultado=r)
    except minuta_ia.ErrorMinuta as e:
        db.terminar_minuta(minuta_id, error=str(e))
    except Exception as e:
        print(f"[minuta] error: {e}")
        db.terminar_minuta(minuta_id, error=f"No se pudo procesar la grabación: {e}")


@app.post("/api/proyectos/minuta")
async def api_crear_minuta(audio: UploadFile = File(...), participantes: str = Form("[]"), contexto: str = Form(""),
                           usuario: dict = Depends(requiere_gestor_proyectos)):
    """Recibe la grabación (webm/m4a/mp3/wav…) y los participantes (ids en JSON). Regresa el id para consultar."""
    datos = await audio.read()
    if len(datos) < 2000:
        raise HTTPException(status_code=400, detail="La grabación está vacía o es demasiado corta.")
    if len(datos) > MAX_AUDIO_MINUTA:
        raise HTTPException(status_code=400, detail="La grabación pesa demasiado (máximo 200 MB, unas 3 horas).")
    try:
        ids = [int(x) for x in json.loads(participantes or "[]")]
    except Exception:
        raise HTTPException(status_code=400, detail="Participantes inválidos")
    usuarios = {u["id"]: u for u in db.listar_usuarios(usuario["empresa_id"])}
    lista = [{"id": i, "nombre": usuarios[i]["nombre_completo"], "puesto": usuarios[i].get("puesto")} for i in ids if i in usuarios]
    minuta_id = db.crear_minuta(usuario["empresa_id"], usuario["id"], lista)
    threading.Thread(target=_procesar_minuta, args=(minuta_id, datos, audio.filename or "grabacion.webm", lista, contexto),
                     daemon=True).start()
    return {"id": minuta_id}


@app.get("/api/proyectos/minuta/{minuta_id}")
def api_estado_minuta(minuta_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    m = db.obtener_minuta(usuario["empresa_id"], minuta_id)
    if not m or m["usuario_id"] != usuario["id"]:
        raise HTTPException(status_code=404, detail="Minuta no encontrada")
    return {"id": m["id"], "estado": m["estado"], "error": m.get("error"), "resultado": m.get("resultado"),
            "participantes": m["participantes"], "creado_en": m["creado_en"]}


class MinutaPdfIn(BaseModel):
    minuta: dict
    participantes: List[int] = []
    fecha: Optional[str] = None
    minuta_id: Optional[int] = None      # para folio, fecha y hora reales de la reunión
    proyecto_id: Optional[int] = None    # si ya se creó el proyecto


@app.post("/api/proyectos/minuta/pdf")
def api_pdf_minuta(payload: MinutaPdfIn, usuario: dict = Depends(requiere_gestor_proyectos)):
    """El PDF oficial de la minuta (logo, folio, participantes con puesto, plan de trabajo)
    con lo que el usuario revisó/corrigió en pantalla."""
    import minuta_ia
    usuarios = {u["id"]: u for u in db.listar_usuarios(usuario["empresa_id"])}
    lista = [{"id": i, "nombre": usuarios[i]["nombre_completo"], "puesto": usuarios[i].get("puesto")}
             for i in payload.participantes if i in usuarios]
    empresa = db.obtener_empresa(usuario["empresa_id"]) or {}
    fecha = payload.fecha or db.ahora().date().isoformat()
    hora = None
    folio = None
    if payload.minuta_id:
        mi = db.obtener_minuta(usuario["empresa_id"], payload.minuta_id)
        if mi:
            folio = f"MIN-{mi['id']:06d}"
            creado = str(mi.get("creado_en") or "")
            if len(creado) >= 16:
                fecha, hora = creado[:10], creado[11:16]
            if payload.proyecto_id:
                try:
                    db.marcar_minuta_proyecto(mi["id"], payload.proyecto_id)
                except Exception:
                    pass
    if hora is None:
        hora = db.ahora().strftime("%H:%M")
    autor = usuario.get("nombre") or ""
    if usuarios.get(usuario["id"], {}).get("nombre_completo"):
        autor = usuarios[usuario["id"]]["nombre_completo"]
    contenido = minuta_ia.pdf_minuta(payload.minuta, empresa, lista, fecha, autor, folio=folio, hora=hora,
                                     proyecto_folio=f"#{payload.proyecto_id}" if payload.proyecto_id else None)
    nombre = re.sub(r"[^A-Za-z0-9_-]+", "_", (payload.minuta.get("titulo_proyecto") or "reunion"))[:50]
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=Minuta_{nombre}.pdf"})


@app.get("/api/proyectos/reporte.pdf")
def reporte_proyectos_pdf(usuario: dict = Depends(requiere_ver_proyectos)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    participante_id = usuario["id"] if usuario["rol"] == "usuario" else None
    proyectos = db.listar_proyectos(usuario["empresa_id"], participante_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = [
        Paragraph(f"Proyectos — {empresa['nombre'] if empresa else ''}", styles["Title"]),
        Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')} — {len(proyectos)} proyecto(s)", styles["Normal"]),
        Spacer(1, 16),
    ]

    datos = [["Nombre", "Estado", "Participantes", "Fecha estimada", "Días transcurridos", "Creado por"]]
    for p in proyectos:
        participantes = ", ".join(
            [u["nombre_completo"] for u in p["participantes_usuarios"]] + p["participantes_departamentos"]
        ) or "—"
        datos.append([
            p["nombre"], NOMBRES_ESTADO_PROYECTO_PDF.get(p["estado"], p["estado"]), participantes,
            (p.get("fecha_estimada") or "—")[:10],
            str(p["dias_transcurridos"]) if p.get("dias_transcurridos") is not None else "—",
            p["creado_por_nombre"],
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
    if not proyectos:
        elementos.append(Paragraph("No hay proyectos registrados.", styles["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    nombre_archivo = f"proyectos_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


@app.get("/api/proyectos/reporte.xlsx")
def reporte_proyectos_xlsx(usuario: dict = Depends(requiere_ver_proyectos)):
    from io import BytesIO
    from datetime import datetime as dt

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    participante_id = usuario["id"] if usuario["rol"] == "usuario" else None
    proyectos = db.listar_proyectos(usuario["empresa_id"], participante_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Proyectos"
    encabezados = ["Nombre", "Descripción", "Estado", "Personas", "Departamentos", "Fecha estimada",
                   "Fecha inicio", "Fecha completado", "Días transcurridos", "Creado por"]
    ws.append(encabezados)
    for col_idx, _ in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="D8192F", end_color="D8192F", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    for p in proyectos:
        ws.append([
            p["nombre"], p.get("descripcion") or "", NOMBRES_ESTADO_PROYECTO_PDF.get(p["estado"], p["estado"]),
            ", ".join(u["nombre_completo"] for u in p["participantes_usuarios"]),
            ", ".join(p["participantes_departamentos"]),
            (p.get("fecha_estimada") or "")[:10], (p.get("fecha_inicio") or "")[:10],
            (p.get("fecha_completado") or "")[:10],
            p["dias_transcurridos"] if p.get("dias_transcurridos") is not None else "",
            p["creado_por_nombre"],
        ])

    for col_idx, encabezado in enumerate(encabezados, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(encabezado), 14) + 4
    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    nombre_archivo = f"proyectos_{dt.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buffer.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


@app.get("/api/proyectos/{proyecto_id}")
def api_detalle_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    return proyecto


@app.post("/api/proyectos/{proyecto_id}/tareas")
def api_crear_tarea_proyecto(proyecto_id: int, payload: NuevaTareaProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    ids_participantes = {p["id"] for p in proyecto["participantes_usuarios"]}
    faltantes = [uid for uid in payload.usuario_ids if uid not in ids_participantes]
    if faltantes:
        raise HTTPException(status_code=400, detail="Alguna de esas personas no es participante del proyecto — agrégala primero")
    db.crear_tarea_proyecto(proyecto_id, payload.usuario_ids, payload.descripcion, payload.fecha_limite, payload.hora_limite)
    limite = _cuando(payload.fecha_limite, payload.hora_limite)
    _bitacora_proyecto(proyecto_id, usuario, f"Nueva tarea \"{payload.descripcion.strip()[:120]}\" para "
                       f"{_nombres_usuarios(proyecto, payload.usuario_ids)}" + (f", límite {limite}" if limite else "") + ".")
    _avisar_proyecto(usuario, proyecto, f"✅ Nueva tarea · {proyecto.get('nombre', '')}",
                     (payload.descripcion or "")[:200] + (f" (para el {limite})" if limite else ""),
                     solo=list(payload.usuario_ids))
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.patch("/api/proyectos/{proyecto_id}/tareas/{tarea_id}/fecha")
def api_editar_fecha_tarea_proyecto(proyecto_id: int, tarea_id: int, payload: EdicionTareaProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien creó el proyecto cambia las tareas")
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if payload.hora_limite and not re.match(_RE_HORA, payload.hora_limite):
        raise HTTPException(status_code=400, detail="La hora debe ser HH:MM (24 h)")
    db.actualizar_fecha_tarea_proyecto(tarea_id, payload.fecha_limite, payload.hora_limite, payload.descripcion)
    nueva = db.obtener_tarea_proyecto(tarea_id)
    limite = _cuando(nueva.get("fecha_limite"), nueva.get("hora_limite")) or "sin fecha"
    _bitacora_proyecto(proyecto_id, usuario, f"Tarea \"{(nueva.get('descripcion') or '')[:120]}\": límite {limite}.")
    asignados = [u["id"] for t in proyecto.get("tareas") or [] if t["id"] == tarea_id for u in t.get("usuarios") or []]
    _avisar_proyecto(usuario, proyecto, f"🕒 Cambió tu tarea · {proyecto.get('nombre', '')}",
                     f"\"{(nueva.get('descripcion') or '')[:80]}\": límite {limite}.", solo=asignados)
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.patch("/api/proyectos/tareas/{tarea_id}/asignados")
def api_asignar_usuarios_tarea_proyecto(tarea_id: int, payload: AsignarUsuariosTarea, usuario: dict = Depends(requiere_gestor_proyectos)):
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    proyecto = db.obtener_proyecto(usuario["empresa_id"], tarea["proyecto_id"])
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    ids_participantes = {p["id"] for p in proyecto["participantes_usuarios"]}
    faltantes = [uid for uid in payload.usuario_ids if uid not in ids_participantes]
    if faltantes:
        raise HTTPException(status_code=400, detail="Alguna de esas personas no es participante del proyecto — agrégala primero")
    db.asignar_usuarios_tarea_proyecto(tarea_id, payload.usuario_ids)
    _bitacora_proyecto(tarea["proyecto_id"], usuario, f"Tarea \"{(tarea.get('descripcion') or '')[:120]}\" ahora es de "
                       f"{_nombres_usuarios(proyecto, payload.usuario_ids) or 'nadie'}.")
    _avisar_proyecto(usuario, proyecto, f"✅ Te asignaron una tarea · {proyecto.get('nombre', '')}",
                     (tarea.get("descripcion") or "")[:200],
                     solo=[u for u in payload.usuario_ids if u != tarea.get("usuario_id")])
    return db.obtener_proyecto(usuario["empresa_id"], tarea["proyecto_id"])


class CambioEstadoTareaProyecto(BaseModel):
    estado: str


@app.patch("/api/proyectos/{proyecto_id}/tareas/{tarea_id}")
def api_cambiar_estado_tarea_proyecto(proyecto_id: int, tarea_id: int, payload: CambioEstadoTareaProyecto, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if payload.estado not in db.ESTADOS_TAREA_PROYECTO:
        raise HTTPException(status_code=400, detail="Estado inválido")
    # Solo el administrador o quien creó el proyecto cambia el estatus; quien
    # tiene la tarea avisa con "Terminé" (ver api_reportar_tarea_terminada).
    if not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien creó el proyecto cambia el estatus. "
                                                    "Si ya terminaste, usa \"Terminé\".")
    db.cambiar_estado_tarea_proyecto(tarea_id, payload.estado)
    if payload.estado != tarea.get("estado"):
        _bitacora_proyecto(proyecto_id, usuario, f"Tarea \"{(tarea.get('descripcion') or '')[:120]}\" → {payload.estado.replace('_', ' ')}.")
        _avisar_proyecto(usuario, proyecto, f"📋 {proyecto.get('nombre', '')}",
                         f"{usuario.get('nombre', '')} cambió la tarea \"{(tarea.get('descripcion') or '')[:80]}\" a {payload.estado.replace('_', ' ')}.",
                         solo=[proyecto.get("creado_por_id")] + [u["id"] for t in proyecto.get("tareas") or []
                                                                  if t["id"] == tarea_id for u in t.get("usuarios") or []])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


class TareaTerminadaIn(BaseModel):
    nota: Optional[str] = Field(default=None, max_length=1000)
    archivo_base64: Optional[str] = None
    archivo_nombre: Optional[str] = None
    archivo_tipo: Optional[str] = None


@app.post("/api/proyectos/{proyecto_id}/tareas/{tarea_id}/termine")
def api_reportar_tarea_terminada(proyecto_id: int, tarea_id: int, payload: TareaTerminadaIn, usuario: dict = Depends(requiere_ver_proyectos)):
    """Quien tiene la tarea avisa que ya terminó (con nota y/o foto). Queda
    "por revisar" hasta que el administrador o quien creó el proyecto la
    marque completada."""
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if not db.usuario_asignado_a_tarea(tarea_id, usuario["id"]) and not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Esta tarea no está asignada a ti")
    if tarea["estado"] == "completada":
        raise HTTPException(status_code=400, detail="Esta tarea ya está completada")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    nota = _limpio(payload.nota)
    db.reportar_tarea_terminada(tarea_id, usuario["id"], nota)
    db.agregar_actualizacion_proyecto(
        proyecto_id, usuario["id"],
        f"✅ Terminé la tarea \"{(tarea.get('descripcion') or '')[:120]}\"" + (f" — {nota}" if nota else "") + ". Falta que la revisen.",
        payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)
    _avisar_proyecto(usuario, proyecto, f"✅ Tarea terminada · {proyecto.get('nombre', '')}",
                     f"{usuario.get('nombre', '')} terminó \"{(tarea.get('descripcion') or '')[:80]}\". Revísala y márcala completada.",
                     solo=[proyecto.get("creado_por_id")])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.delete("/api/proyectos/{proyecto_id}/tareas/{tarea_id}")
def api_eliminar_tarea_proyecto(proyecto_id: int, tarea_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.eliminar_tarea_proyecto(tarea_id)
    _bitacora_proyecto(proyecto_id, usuario, f"Se eliminó la tarea \"{(tarea.get('descripcion') or '')[:120]}\".")
    return {"ok": True}


# ---- Gantt del proyecto ----

class SubtareaGantt(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class SubtareasGantt(BaseModel):
    planning: Optional[SubtareaGantt] = None
    execution: Optional[SubtareaGantt] = None
    completed: bool = False


class TareaGanttIn(BaseModel):
    name: str = Field(min_length=1)
    category: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    dependsOn: List[str] = []
    subtasks: Optional[SubtareasGantt] = None


@app.get("/api/proyectos/{proyecto_id}/gantt")
def api_obtener_gantt_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    return {"proyecto_nombre": proyecto["nombre"], "tareas": db.obtener_tareas_gantt(proyecto_id)}


@app.post("/api/proyectos/{proyecto_id}/gantt")
def api_crear_tarea_gantt(proyecto_id: int, payload: TareaGanttIn, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    tarea_id = db.crear_tarea_gantt(proyecto_id, usuario["id"], payload.model_dump())
    return {"id": str(tarea_id)}


@app.patch("/api/proyectos/{proyecto_id}/gantt/{tarea_id}")
def api_actualizar_tarea_gantt(proyecto_id: int, tarea_id: int, payload: TareaGanttIn, usuario: dict = Depends(requiere_gestor_proyectos)):
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.actualizar_tarea_gantt(tarea_id, payload.model_dump())
    return {"ok": True}


class CompletadoGanttIn(BaseModel):
    completed: bool


@app.patch("/api/proyectos/{proyecto_id}/gantt/{tarea_id}/completado")
def api_marcar_completado_gantt(proyecto_id: int, tarea_id: int, payload: CompletadoGanttIn, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien creó el proyecto marca tareas como completadas.")
    db.actualizar_completado_tarea_gantt(tarea_id, payload.completed)
    return {"ok": True}


@app.delete("/api/proyectos/{proyecto_id}/gantt/{tarea_id}")
def api_eliminar_tarea_gantt(proyecto_id: int, tarea_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    tarea = db.obtener_tarea_proyecto(tarea_id)
    if not tarea or tarea["proyecto_id"] != proyecto_id:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.eliminar_tarea_gantt(tarea_id)
    return {"ok": True}


@app.get("/gantt.html")
def pagina_gantt():
    """La página del Gantt es parte de la SPA (necesita login) — a
    diferencia de /seguimiento, que es pública."""
    return FileResponse(os.path.join(FRONTEND_DIR, "gantt.html"))


@app.get("/cotizador-costos.html")
def pagina_cotizador_costos():
    """Cotizador de módulos/precios/costos por empresa (Superadmin) —
    misma idea que gantt.html: es su propia página HTML (mismo diseño
    ya aprobado), parte de la SPA, necesita login, y lee/guarda su
    configuración con los endpoints /api/empresas/{id}/costos."""
    return FileResponse(os.path.join(FRONTEND_DIR, "cotizador_costos.html"))


@app.patch("/api/proyectos/{proyecto_id}")
def api_actualizar_proyecto(proyecto_id: int, payload: ActualizacionProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    nombre = payload.nombre.strip() if payload.nombre is not None else None
    if nombre is not None and not nombre:
        raise HTTPException(status_code=400, detail="El nombre del proyecto no puede quedar vacío")
    for h in (payload.hora_inicio_plan, payload.hora_entrega):
        if h and not re.match(_RE_HORA, h):
            raise HTTPException(status_code=400, detail="La hora debe ser HH:MM (24 h)")
    db.actualizar_proyecto(usuario["empresa_id"], proyecto_id, nombre, payload.descripcion, payload.fecha_estimada,
                           payload.inicio_plan, payload.hora_inicio_plan, payload.hora_entrega)
    nuevo = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    cambios = []
    if nombre is not None and nombre != proyecto.get("nombre"):
        cambios.append(f"nombre: {nombre}")
    if payload.descripcion is not None and payload.descripcion != (proyecto.get("descripcion") or ""):
        cambios.append("descripción")
    antes_i = _cuando(proyecto.get("inicio_plan"), proyecto.get("hora_inicio_plan"))
    ahora_i = _cuando(nuevo.get("inicio_plan"), nuevo.get("hora_inicio_plan"))
    antes_e = _cuando(proyecto.get("fecha_estimada"), proyecto.get("hora_entrega"))
    ahora_e = _cuando(nuevo.get("fecha_estimada"), nuevo.get("hora_entrega"))
    fechas = []
    if antes_i != ahora_i:
        fechas.append(f"inicio {ahora_i or 'sin fecha'}")
    if antes_e != ahora_e:
        fechas.append(f"entrega {ahora_e or 'sin fecha'}")
    cambios += fechas
    if cambios:
        _bitacora_proyecto(proyecto_id, usuario, "Cambios al proyecto: " + ", ".join(cambios) + ".")
    if fechas:
        _avisar_proyecto(usuario, nuevo, f"🕒 {nuevo.get('nombre', '')}", "Nuevas fechas: " + ", ".join(fechas) + ".")
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/iniciar")
def api_iniciar_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    resultado = db.iniciar_proyecto(usuario["empresa_id"], proyecto_id)
    if not resultado["ok"]:
        nombres = ", ".join(p["nombre_completo"] for p in resultado["pendientes"])
        raise HTTPException(status_code=400, detail=f"Todavía falta que firmen o digan por qué no están conformes: {nombres}")
    _bitacora_proyecto(proyecto_id, usuario, "Proyecto iniciado (todos firmaron o dejaron su motivo).")
    _avisar_proyecto(usuario, proyecto, f"🚀 {proyecto.get('nombre', '')}", "El proyecto ya inició.")
    return {"ok": True}


class FirmaParticipanteProyecto(BaseModel):
    firma_base64: str = Field(min_length=100)
    nombre: Optional[str] = Field(default=None, max_length=160)


class FirmaPresencialProyecto(BaseModel):
    usuario_id: int
    nombre: str = Field(min_length=2, max_length=160)
    firma_base64: str = Field(min_length=100)


class NoConformeProyecto(BaseModel):
    motivo: str = Field(min_length=3)


@app.post("/api/proyectos/{proyecto_id}/firmar-participante")
def api_firmar_participante_proyecto(proyecto_id: int, payload: FirmaParticipanteProyecto, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not any(p["id"] == usuario["id"] for p in proyecto["participantes_usuarios"]):
        raise HTTPException(status_code=403, detail="No eres participante de este proyecto")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    nombre = _limpio(payload.nombre) or usuario.get("nombre")
    db.firmar_participante_proyecto(proyecto_id, usuario["id"], payload.firma_base64, nombre=nombre)
    _bitacora_proyecto(proyecto_id, usuario, f"{nombre} firmó de conformidad desde su celular.")
    pendientes = db.participantes_pendientes_de_firma(proyecto_id)
    _avisar_proyecto(usuario, proyecto, f"✍️ Firma · {proyecto.get('nombre', '')}",
                     f"{nombre} firmó." + (" Ya firmaron todos: puedes iniciar el proyecto." if not pendientes else f" Faltan {len(pendientes)}."),
                     solo=[proyecto.get("creado_por_id")])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.post("/api/proyectos/{proyecto_id}/firma-presencial")
def api_firma_presencial_proyecto(proyecto_id: int, payload: FirmaPresencialProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    """El administrador del proyecto le pasa SU teléfono al participante para
    que escriba su nombre y firme ahí mismo."""
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien creó el proyecto puede recabar firmas")
    participante = next((p for p in proyecto["participantes_usuarios"] if p["id"] == payload.usuario_id), None)
    if not participante:
        raise HTTPException(status_code=400, detail="Esa persona no es participante del proyecto")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    nombre = _limpio(payload.nombre)
    db.firmar_participante_proyecto(proyecto_id, payload.usuario_id, payload.firma_base64, nombre=nombre, presencial_por=usuario["id"])
    _bitacora_proyecto(proyecto_id, usuario, f"{nombre} ({participante['nombre_completo']}) firmó de conformidad en persona, "
                       f"en el teléfono de {usuario.get('nombre', '')}.")
    _avisar_proyecto(usuario, proyecto, f"✍️ Firmaste · {proyecto.get('nombre', '')}",
                     "Quedó registrada tu firma de conformidad.", solo=[payload.usuario_id])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.post("/api/proyectos/{proyecto_id}/pedir-firmas")
def api_pedir_firmas_proyecto(proyecto_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    """Manda aviso a quien no ha firmado para que firme desde su celular."""
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_mover_tareas(usuario, proyecto):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien creó el proyecto puede pedir firmas")
    pendientes = db.participantes_pendientes_de_firma(proyecto_id)
    if not pendientes:
        return {"ok": True, "enviados": 0, "nombres": []}
    _avisar_proyecto(usuario, proyecto, f"✍️ Firma pendiente · {proyecto.get('nombre', '')}",
                     f"{usuario.get('nombre', '')} te pide firmar tu conformidad con el proyecto. Ábrelo en la app y toca \"Firmar\".",
                     solo=[p["id"] for p in pendientes])
    _bitacora_proyecto(proyecto_id, usuario, "Se pidió firma a: " + ", ".join(p["nombre_completo"] for p in pendientes) + ".")
    return {"ok": True, "enviados": len(pendientes), "nombres": [p["nombre_completo"] for p in pendientes]}


@app.get("/api/proyectos/{proyecto_id}/firmas/{usuario_id}")
def api_ver_firma_proyecto(proyecto_id: int, usuario_id: int, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto or not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    f = db.firma_participante_proyecto(proyecto_id, usuario_id)
    if not f or not f.get("firma_base64"):
        raise HTTPException(status_code=404, detail="Sin firma")
    return f


@app.post("/api/proyectos/{proyecto_id}/no-conforme")
def api_no_conforme_proyecto(proyecto_id: int, payload: NoConformeProyecto, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not any(p["id"] == usuario["id"] for p in proyecto["participantes_usuarios"]):
        raise HTTPException(status_code=403, detail="No eres participante de este proyecto")
    db.marcar_no_conforme_proyecto(proyecto_id, usuario["id"], payload.motivo.strip())
    _bitacora_proyecto(proyecto_id, usuario, f"{usuario.get('nombre', '')} no está conforme: {payload.motivo.strip()[:300]}")
    _avisar_proyecto(usuario, proyecto, f"⚠️ No conforme · {proyecto.get('nombre', '')}",
                     f"{usuario.get('nombre', '')}: {payload.motivo.strip()[:150]}", solo=[proyecto.get("creado_por_id")])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


@app.patch("/api/proyectos/{proyecto_id}/estado")
def api_cambiar_estado_proyecto(proyecto_id: int, payload: CambioEstadoProyecto, usuario: dict = Depends(requiere_gestor_proyectos)):
    if payload.estado not in db.ESTADOS_PROYECTO:
        raise HTTPException(status_code=400, detail="Estado inválido")
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.cambiar_estado_proyecto(usuario["empresa_id"], proyecto_id, payload.estado)
    if payload.estado != proyecto.get("estado"):
        _bitacora_proyecto(proyecto_id, usuario, f"Estado del proyecto: {NOMBRES_ESTADO_PROYECTO_PDF.get(payload.estado, payload.estado)}.")
        _avisar_proyecto(usuario, proyecto, f"📋 {proyecto.get('nombre', '')}",
                         f"El proyecto ahora está: {NOMBRES_ESTADO_PROYECTO_PDF.get(payload.estado, payload.estado)}.")
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/participantes/usuarios")
def api_agregar_participante_usuario(proyecto_id: int, payload: NuevoParticipanteUsuario, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    ya_estaba = any(p["id"] == payload.usuario_id for p in proyecto.get("participantes_usuarios") or [])
    db.agregar_participante_usuario(proyecto_id, payload.usuario_id)
    if not ya_estaba:
        nuevo = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
        _bitacora_proyecto(proyecto_id, usuario, f"Se agregó a {_nombres_usuarios(nuevo, [payload.usuario_id])} como participante.")
        _avisar_proyecto(usuario, proyecto, f"📋 Te agregaron al proyecto {proyecto.get('nombre', '')}",
                         f"{usuario.get('nombre', '')} te agregó como participante.", solo=[payload.usuario_id])
    return {"ok": True}


@app.delete("/api/proyectos/{proyecto_id}/participantes/usuarios/{usuario_id}")
def api_quitar_participante_usuario(proyecto_id: int, usuario_id: int, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    quien = _nombres_usuarios(proyecto, [usuario_id])
    db.quitar_participante_usuario(proyecto_id, usuario_id)
    _bitacora_proyecto(proyecto_id, usuario, f"Se quitó a {quien} del proyecto.")
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/participantes/departamentos")
def api_agregar_participante_departamento(proyecto_id: int, payload: NuevoParticipanteDepartamento, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.agregar_participante_departamento(proyecto_id, payload.departamento)
    return {"ok": True}


@app.delete("/api/proyectos/{proyecto_id}/participantes/departamentos/{departamento}")
def api_quitar_participante_departamento(proyecto_id: int, departamento: str, usuario: dict = Depends(requiere_gestor_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    db.quitar_participante_departamento(proyecto_id, departamento)
    return {"ok": True}


@app.post("/api/proyectos/{proyecto_id}/actualizaciones")
def api_comentar_proyecto(proyecto_id: int, payload: NuevaActualizacionProyecto, usuario: dict = Depends(requiere_ver_proyectos)):
    proyecto = db.obtener_proyecto(usuario["empresa_id"], proyecto_id)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _puede_ver_proyecto(usuario, proyecto):
        raise HTTPException(status_code=403, detail="No participas en este proyecto")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    db.agregar_actualizacion_proyecto(proyecto_id, usuario["id"], payload.texto,
                                       payload.archivo_base64, payload.archivo_nombre, payload.archivo_tipo)
    _avisar_proyecto(usuario, proyecto, f"💬 {usuario.get('nombre', '')} · {proyecto.get('nombre', '')}",
                     (payload.texto or "📎 Archivo adjunto")[:200])
    return db.obtener_proyecto(usuario["empresa_id"], proyecto_id)


# ==================== RH: CHECADOR DESDE LA APP ====================
# Quien tenga el acceso "Checador app" checa entrada, comida y salida con su
# celular: selfie (el servidor revisa que se vea una cara) + ubicación. RH
# registra antes la foto de su cara y revisa cada checada contra esa foto.

TIPOS_CHECADA_APP = {
    "entrada": "Entrada",
    "salida_comida": "Salida a comer",
    "regreso_comida": "Regreso de comer",
    "salida": "Salida",
}


def _siguientes_checadas(checadas_hoy):
    ultimo = checadas_hoy[-1]["tipo"] if checadas_hoy else None
    return {
        None: ["entrada"],
        "entrada": ["salida_comida", "salida"],
        "salida_comida": ["regreso_comida"],
        "regreso_comida": ["salida"],
        "salida": [],
    }.get(ultimo, [])


def _hay_cara(foto_base64):
    """True/False si se pudo revisar; None si el servidor no tiene OpenCV
    (entonces no se bloquea y RH revisa a ojo)."""
    try:
        import base64 as _b64
        import cv2
        import numpy as np
    except Exception:
        return None
    try:
        datos = foto_base64.split(",", 1)[1] if foto_base64.startswith("data:") else foto_base64
        img = cv2.imdecode(np.frombuffer(_b64.b64decode(datos), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False
        alto, ancho = img.shape[:2]
        escala = 800 / max(alto, ancho) if max(alto, ancho) > 800 else 1.0
        if escala != 1.0:
            img = cv2.resize(img, (int(ancho * escala), int(alto * escala)))
        img = cv2.equalizeHist(img)
        minimo = max(40, int(min(img.shape[:2]) * 0.12))
        for archivo in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"):
            cascada = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, archivo))
            if cascada.empty():
                continue
            caras = cascada.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(minimo, minimo))
            if len(caras):
                return True
        return False
    except Exception as e:
        print(f"[checador] no se pudo revisar la cara: {e}")
        return None


class ChecadaAppIn(BaseModel):
    tipo: Literal["entrada", "salida_comida", "regreso_comida", "salida"]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    precision_m: Optional[float] = None
    foto_base64: str = Field(min_length=200)


class FotoChecadorIn(BaseModel):
    foto_base64: str = Field(min_length=200)


class RevisionChecadaIn(BaseModel):
    revision: Literal["ok", "no_coincide"]
    nota: Optional[str] = Field(default=None, max_length=300)


def _requiere_checador(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_checador", False):
        raise HTTPException(status_code=403, detail="No tienes activado el checador en la app. Pídeselo a Recursos Humanos.")
    return usuario


@app.get("/api/checador/hoy")
def api_checador_hoy(usuario: dict = Depends(_requiere_checador)):
    hoy = db.ahora().date()
    checadas = db.checadas_app_dia(usuario["id"], hoy)
    foto = db.foto_checador_usuario(usuario["empresa_id"], usuario["id"]) or {}
    for c in checadas:
        c["etiqueta"] = TIPOS_CHECADA_APP.get(c["tipo"], c["tipo"])
    sig = _siguientes_checadas(checadas)
    return {
        "fecha": hoy.isoformat(),
        "tiene_foto": bool(foto.get("foto_checador")),
        "checadas": checadas,
        "siguientes": [{"tipo": t, "etiqueta": TIPOS_CHECADA_APP[t]} for t in sig],
    }


@app.post("/api/checador")
def api_checar_app(payload: ChecadaAppIn, usuario: dict = Depends(_requiere_checador)):
    foto_ref = (db.foto_checador_usuario(usuario["empresa_id"], usuario["id"]) or {}).get("foto_checador")
    if not foto_ref:
        raise HTTPException(status_code=400, detail="Recursos Humanos todavía no registra la foto de tu cara. Pídeles que te den de alta en el checador.")
    if len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado")
    hoy = db.ahora().date()
    sig = _siguientes_checadas(db.checadas_app_dia(usuario["id"], hoy))
    if payload.tipo not in sig:
        if not sig:
            raise HTTPException(status_code=400, detail="Ya registraste tu salida de hoy.")
        raise HTTPException(status_code=400, detail="Ahora te toca: " + " o ".join(TIPOS_CHECADA_APP[t] for t in sig))
    cara = _hay_cara(payload.foto_base64)
    if cara is False:
        raise HTTPException(status_code=400, detail="No se ve tu cara en la foto. Tómala de frente, con buena luz y sin cubrirte la cara.")
    etiqueta = TIPOS_CHECADA_APP[payload.tipo]
    nuevo = db.registrar_checada_app(usuario["empresa_id"], usuario["id"], payload.tipo, etiqueta,
                                     payload.lat, payload.lng, payload.precision_m, payload.foto_base64, cara)
    return {"ok": True, "id": nuevo, "etiqueta": etiqueta, "hora": db.ahora().strftime("%H:%M")}


@app.get("/api/rh/checador")
def api_rh_checadas_app(desde: Optional[str] = None, hasta: Optional[str] = None, usuario_id: Optional[int] = None,
                        usuario: dict = Depends(requiere_rh_o_logistica)):
    try:
        d = date.fromisoformat(desde) if desde else db.ahora().date()
        h = date.fromisoformat(hasta) if hasta else d
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    filas = db.listar_checadas_app(usuario["empresa_id"], d, h, usuario_id)
    for f in filas:
        f["etiqueta"] = TIPOS_CHECADA_APP.get(f["tipo"], f["tipo"])
    return filas


@app.get("/api/rh/checador/usuarios")
def api_rh_usuarios_checador(usuario: dict = Depends(requiere_admin_rh)):
    return db.usuarios_checador(usuario["empresa_id"])


@app.put("/api/rh/checador/usuarios/{usuario_id}/foto")
def api_rh_foto_checador(usuario_id: int, payload: FotoChecadorIn, usuario: dict = Depends(requiere_admin_rh)):
    if len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado")
    if _hay_cara(payload.foto_base64) is False:
        raise HTTPException(status_code=400, detail="No se reconoce una cara en esa foto. Usa una foto de frente, con buena luz.")
    if not db.guardar_foto_checador(usuario["empresa_id"], usuario_id, payload.foto_base64):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True}


@app.get("/api/rh/checador/usuarios/{usuario_id}/foto")
def api_rh_ver_foto_checador(usuario_id: int, usuario: dict = Depends(requiere_admin_rh)):
    f = db.foto_checador_usuario(usuario["empresa_id"], usuario_id)
    if not f or not f.get("foto_checador"):
        raise HTTPException(status_code=404, detail="Sin foto registrada")
    return {"foto": f["foto_checador"]}


@app.get("/api/rh/checador/{checada_id}")
def api_rh_detalle_checada(checada_id: int, usuario: dict = Depends(requiere_rh_o_logistica)):
    c = db.obtener_checada_app(usuario["empresa_id"], checada_id)
    if not c:
        raise HTTPException(status_code=404, detail="Checada no encontrada")
    return {"id": c["id"], "nombre": c["nombre_completo"], "tipo": c["tipo"], "etiqueta": TIPOS_CHECADA_APP.get(c["tipo"], c["tipo"]),
            "fecha_hora": c["fecha_hora"], "lat": c["lat"], "lng": c["lng"], "precision_m": c["precision_m"],
            "cara_detectada": c["cara_detectada"], "revision": c["revision"], "revision_nota": c["revision_nota"],
            "foto": c["foto_base64"], "foto_registrada": c["foto_checador"]}


@app.patch("/api/rh/checador/{checada_id}/revision")
def api_rh_revisar_checada(checada_id: int, payload: RevisionChecadaIn, usuario: dict = Depends(requiere_rh_o_logistica)):
    if not db.obtener_checada_app(usuario["empresa_id"], checada_id):
        raise HTTPException(status_code=404, detail="Checada no encontrada")
    db.revisar_checada_app(usuario["empresa_id"], checada_id, payload.revision, (payload.nota or "").strip() or None, usuario["id"])
    return {"ok": True}


NOMBRES_ESTADO_PROYECTO_PDF = {
    "planificacion": "Planificación", "en_progreso": "En progreso", "pausado": "Pausado",
    "completado": "Completado", "cancelado": "Cancelado",
}


# ==================== COMPRAS ====================

class NuevoArticuloCompra(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    proveedor: Optional[str] = None
    marca: Optional[str] = None
    foto_base64: Optional[str] = None
    notas: Optional[str] = None
    categoria: Optional[str] = None
    precio_unitario: Optional[float] = None
    stock_actual: Optional[int] = None
    stock_minimo: Optional[int] = None


class ActualizacionArticuloCompra(BaseModel):
    nombre: Optional[str] = None
    proveedor: Optional[str] = None
    marca: Optional[str] = None
    foto_base64: Optional[str] = None
    notas: Optional[str] = None
    categoria: Optional[str] = None
    precio_unitario: Optional[float] = None
    stock_minimo: Optional[int] = None


@app.get("/api/compras/articulos")
def api_listar_articulos_compra(usuario: dict = Depends(requiere_ver_compras)):
    return db.listar_articulos_compra(usuario["empresa_id"])


@app.get("/api/compras/categorias")
def api_listar_categorias_compra(usuario: dict = Depends(requiere_ver_compras)):
    return db.listar_categorias_compra(usuario["empresa_id"])


@app.post("/api/compras/articulos/catalogo-inicial")
def api_sembrar_catalogo_compras(usuario: dict = Depends(requiere_admin_compras)):
    """Carga de un solo golpe un catálogo de productos comunes (papelería, limpieza,
    ferretería, equipo de cómputo, cafetería, equipo de oficina) con precios de
    referencia — no duplica artículos que ya existan por nombre."""
    agregados = db.sembrar_catalogo_compras(usuario["empresa_id"])
    return {"agregados": agregados, "total_catalogo": len(db.CATALOGO_INICIAL_COMPRAS)}


@app.post("/api/compras/articulos")
def api_crear_articulo_compra(payload: NuevoArticuloCompra, usuario: dict = Depends(requiere_admin_compras)):
    if payload.foto_base64 and len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 5MB)")
    articulo_id = db.crear_articulo_compra(usuario["empresa_id"], payload.nombre, payload.proveedor,
                                            payload.marca, payload.foto_base64, payload.notas, payload.categoria,
                                            payload.precio_unitario, payload.stock_actual or 0, payload.stock_minimo or 0)
    return {"id": articulo_id}


@app.patch("/api/compras/articulos/{articulo_id}")
def api_actualizar_articulo_compra(articulo_id: int, payload: ActualizacionArticuloCompra, usuario: dict = Depends(requiere_admin_compras)):
    if not db.obtener_articulo_compra(usuario["empresa_id"], articulo_id):
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    if payload.foto_base64 and len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 5MB)")
    db.actualizar_articulo_compra(usuario["empresa_id"], articulo_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.delete("/api/compras/articulos/{articulo_id}")
def api_dar_de_baja_articulo_compra(articulo_id: int, usuario: dict = Depends(requiere_admin_compras)):
    if not db.obtener_articulo_compra(usuario["empresa_id"], articulo_id):
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    db.dar_de_baja_articulo_compra(usuario["empresa_id"], articulo_id)
    return {"ok": True}


class AjusteStockArticulo(BaseModel):
    delta: int  # positivo para sumar existencias, negativo para restar


@app.post("/api/compras/articulos/{articulo_id}/ajustar-stock")
def api_ajustar_stock_articulo(articulo_id: int, payload: AjusteStockArticulo, usuario: dict = Depends(requiere_admin_compras)):
    if not db.obtener_articulo_compra(usuario["empresa_id"], articulo_id):
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    nuevo_stock = db.ajustar_stock_articulo(usuario["empresa_id"], articulo_id, payload.delta)
    return {"stock_actual": nuevo_stock}


class NuevoCicloCompra(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    frecuencia: str = "unica"
    fecha_programada: str
    categoria: Optional[str] = None
    audiencia_tipo: Literal["todos", "segmentado"] = "todos"
    departamentos: Optional[List[str]] = None
    sucursales: Optional[List[int]] = None
    usuarios: Optional[List[int]] = None


class NuevoPedidoCompra(BaseModel):
    articulo_id: Optional[int] = None
    articulo_libre: Optional[str] = None
    cantidad: int = Field(default=1, ge=1)
    sucursal_id: Optional[int] = None
    notas: Optional[str] = None


@app.get("/api/compras/ciclos")
def api_listar_ciclos_compra(estado: Optional[str] = None, usuario: dict = Depends(requiere_ver_compras)):
    # Un empleado normal solo ve los ciclos que le apliquen (todos, o
    # segmentados donde caiga por depto/sucursal/usuario) — staff/admin
    # ven todos, porque los administran aunque no sean el público al que
    # van dirigidos.
    filtrar_por_usuario_id = usuario["id"] if usuario["rol"] == "usuario" else None
    return db.listar_ciclos_compra(usuario["empresa_id"], estado, filtrar_por_usuario_id)


@app.get("/api/compras/opciones-audiencia")
def api_opciones_audiencia_compras(usuario: dict = Depends(requiere_admin_compras)):
    """Sucursales y empleados activos, para armar los selectores de 'a
    quién le toca' al programar un ciclo segmentado. Los departamentos ya
    vienen en META (/api/meta), no hace falta repetirlos aquí."""
    return {
        "sucursales": db.listar_sucursales_reparacion(usuario["empresa_id"], solo_activas=True),
        "usuarios": db.listar_usuarios_activos(usuario["empresa_id"]),
    }


def _validar_audiencia_ciclo(audiencia_tipo, departamentos, sucursales, usuarios):
    if audiencia_tipo == "segmentado" and not (departamentos or sucursales or usuarios):
        raise HTTPException(status_code=400, detail="Elige al menos un departamento, sucursal o empleado para la audiencia segmentada")


@app.post("/api/compras/ciclos")
def api_crear_ciclo_compra(payload: NuevoCicloCompra, usuario: dict = Depends(requiere_admin_compras)):
    if payload.frecuencia not in db.FRECUENCIAS_COMPRA:
        raise HTTPException(status_code=400, detail="Frecuencia inválida")
    _validar_audiencia_ciclo(payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios)
    ciclo_id = db.crear_ciclo_compra(usuario["empresa_id"], payload.nombre, payload.frecuencia,
                                      payload.fecha_programada, usuario["id"], payload.categoria,
                                      payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios)
    return {"id": ciclo_id}


class EdicionAudienciaCiclo(BaseModel):
    audiencia_tipo: Literal["todos", "segmentado"]
    departamentos: Optional[List[str]] = None
    sucursales: Optional[List[int]] = None
    usuarios: Optional[List[int]] = None


@app.get("/api/compras/ciclos/{ciclo_id}/audiencia")
def api_obtener_audiencia_ciclo(ciclo_id: int, usuario: dict = Depends(requiere_admin_compras)):
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    return {"audiencia_tipo": ciclo["audiencia_tipo"], **db.obtener_audiencia_ciclo_compra(ciclo_id)}


@app.patch("/api/compras/ciclos/{ciclo_id}/audiencia")
def api_editar_audiencia_ciclo(ciclo_id: int, payload: EdicionAudienciaCiclo, usuario: dict = Depends(requiere_admin_compras)):
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    _validar_audiencia_ciclo(payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios)
    db.guardar_audiencia_ciclo_compra(ciclo_id, payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios)
    return {"ok": True}


# ---- Compras especiales (fuera de ciclo, para no esperar) ----

class NuevaCompraEspecial(BaseModel):
    articulo_id: Optional[int] = None
    articulo_libre: Optional[str] = None
    cantidad: int = Field(default=1, ge=1)
    motivo: str = Field(min_length=1, max_length=500)


@app.post("/api/compras/especiales")
def api_crear_compra_especial(payload: NuevaCompraEspecial, usuario: dict = Depends(requiere_ver_compras)):
    if usuario["rol"] == "usuario":
        raise HTTPException(status_code=403, detail="Las compras especiales son solo para encargados/administradores, no para empleados")
    if not payload.articulo_id and not payload.articulo_libre:
        raise HTTPException(status_code=400, detail="Elige un artículo del catálogo o escribe cuál necesitas")
    nuevo_id = db.crear_compra_especial(usuario["empresa_id"], usuario["id"], payload.articulo_id,
                                         payload.articulo_libre, payload.cantidad, payload.motivo.strip())
    return {"id": nuevo_id}


def _es_admin_compras_backend(usuario: dict) -> bool:
    return usuario["rol"] == "admin" and usuario.get("acceso_compras", True)


@app.get("/api/compras/especiales")
def api_listar_compras_especiales(estado: Optional[str] = None, usuario: dict = Depends(requiere_ver_compras)):
    # El administrador de Compras ve todas (para aprobar/rechazar); cualquier
    # otro rol (que sí puede pedir especiales) solo ve las suyas.
    filtrar_por_usuario_id = None if _es_admin_compras_backend(usuario) else usuario["id"]
    return db.listar_compras_especiales(usuario["empresa_id"], filtrar_por_usuario_id, estado)


class ResolucionCompraEspecial(BaseModel):
    estado: str
    respuesta: Optional[str] = None


@app.post("/api/compras/especiales/{compra_id}/resolver")
def api_resolver_compra_especial(compra_id: int, payload: ResolucionCompraEspecial, usuario: dict = Depends(requiere_admin_compras)):
    if payload.estado not in db.ESTADOS_COMPRA_ESPECIAL:
        raise HTTPException(status_code=400, detail="Estado inválido")
    compra = db.obtener_compra_especial(usuario["empresa_id"], compra_id)
    if not compra:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    db.resolver_compra_especial(compra_id, payload.estado, usuario["id"], payload.respuesta)
    return {"ok": True}


@app.get("/api/compras/ciclos/{ciclo_id}")
def api_detalle_ciclo_compra(ciclo_id: int, usuario: dict = Depends(requiere_ver_compras)):
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    if usuario["rol"] == "usuario":
        # Un empleado solo ve los pedidos de SU propia sucursal, nunca los de otras.
        # Si no tiene sucursal asignada, ve solo sus propios pedidos (no todos los "sin sucursal").
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if mi_sucursal_id:
            ciclo["pedidos"] = [p for p in ciclo["pedidos"] if p["sucursal_id"] == mi_sucursal_id]
        else:
            ciclo["pedidos"] = [p for p in ciclo["pedidos"] if p["usuario_id"] == usuario["id"]]
    return ciclo


@app.post("/api/compras/ciclos/{ciclo_id}/abrir")
def api_abrir_ciclo_compra(ciclo_id: int, usuario: dict = Depends(requiere_acceso_compras)):
    if not db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id):
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    db.abrir_ciclo_compra(usuario["empresa_id"], ciclo_id)
    return {"ok": True}


@app.post("/api/compras/ciclos/{ciclo_id}/cerrar")
def api_cerrar_ciclo_compra(ciclo_id: int, usuario: dict = Depends(requiere_acceso_compras)):
    resultado = db.cerrar_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    ciclo_cerrado = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    masters = db.listar_usuarios_master(usuario["empresa_id"])
    if masters:
        notifications.notificar_ciclo_pendiente_autorizacion(usuario["empresa_id"], masters, ciclo_cerrado, ciclo_cerrado["total_general"])
    return resultado


@app.post("/api/compras/ciclos/{ciclo_id}/pedidos")
def api_agregar_pedido_compra(ciclo_id: int, payload: NuevoPedidoCompra, usuario: dict = Depends(requiere_ver_compras)):
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    if ciclo["estado"] in ("esperando_autorizacion", "cerrado"):
        raise HTTPException(status_code=400, detail="Este ciclo ya se marcó como surtido — ya no se pueden agregar pedidos")
    if not payload.articulo_id and not (payload.articulo_libre and payload.articulo_libre.strip()):
        raise HTTPException(status_code=400, detail="Elige un artículo del catálogo o escribe uno libre")
    if payload.articulo_id and not db.obtener_articulo_compra(usuario["empresa_id"], payload.articulo_id):
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    if payload.sucursal_id and not db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    db.agregar_pedido_compra(ciclo_id, payload.articulo_id, usuario["id"], payload.cantidad,
                              payload.sucursal_id, payload.notas,
                              payload.articulo_libre.strip() if payload.articulo_libre else None)
    return db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)


@app.delete("/api/compras/pedidos/{pedido_id}")
def api_eliminar_pedido_compra(pedido_id: int, usuario: dict = Depends(requiere_ver_compras)):
    es_staff = usuario["rol"] in ("admin", "tecnico")
    db.eliminar_pedido_compra(pedido_id, usuario["id"], es_staff)
    return {"ok": True}


@app.post("/api/compras/pedidos/{pedido_id}/listo")
def api_marcar_pedido_listo(pedido_id: int, usuario: dict = Depends(requiere_acceso_compras)):
    pedido = db.obtener_pedido_compra(usuario["empresa_id"], pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    db.marcar_pedido_listo(pedido_id)
    notifications.notificar_pedido_listo(
        usuario["empresa_id"], {"id": pedido.get("usuario_id"), "telefono_whatsapp": pedido.get("usuario_telefono")}, pedido["articulo_nombre"], pedido["cantidad"],
    )
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], pedido["ciclo_id"])
    return ciclo


def requiere_autorizacion_compras(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:
    """Autorizar una compra ya cerrada es exclusivo del usuario master (para eso
    existe) y del administrador, como respaldo."""
    if usuario["rol"] not in ("admin", "master"):
        raise HTTPException(status_code=403, detail="No tienes permiso para autorizar compras")
    return usuario


class FirmaAutorizacionCompra(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.get("/api/compras/autorizaciones")
def api_listar_autorizaciones_compra(usuario: dict = Depends(requiere_autorizacion_compras)):
    return db.listar_ciclos_pendientes_autorizacion(usuario["empresa_id"])


@app.post("/api/compras/ciclos/{ciclo_id}/autorizar")
def api_autorizar_ciclo_compra(ciclo_id: int, payload: FirmaAutorizacionCompra, usuario: dict = Depends(requiere_autorizacion_compras)):
    ciclo = db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    if ciclo["estado"] != "esperando_autorizacion":
        raise HTTPException(status_code=400, detail="Este ciclo no está esperando autorización (o ya fue autorizado)")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.autorizar_ciclo_compra(usuario["empresa_id"], ciclo_id, usuario["id"], payload.firma_base64)
    return db.obtener_ciclo_compra(usuario["empresa_id"], ciclo_id)


NOMBRES_FRECUENCIA_COMPRA_PDF = {"unica": "Única vez", "semanal": "Semanal", "quincenal": "Quincenal", "mensual": "Mensual"}
NOMBRES_ESTADO_CICLO_PDF = {"pendiente": "Pendiente", "abierto": "Abierto", "cerrado": "Cerrado"}


@app.get("/api/compras/reporte.pdf")
def reporte_compras_pdf(usuario: dict = Depends(requiere_ver_compras)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    ciclos = db.listar_ciclos_compra(usuario["empresa_id"])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = [
        Paragraph(f"Compras — {empresa['nombre'] if empresa else ''}", styles["Title"]),
        Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')} — {len(ciclos)} ciclo(s)", styles["Normal"]),
        Spacer(1, 16),
    ]

    for c in ciclos:
        detalle = db.obtener_ciclo_compra(usuario["empresa_id"], c["id"])
        elementos.append(Paragraph(
            f"{c['nombre']} — {NOMBRES_FRECUENCIA_COMPRA_PDF.get(c['frecuencia'], c['frecuencia'])} — "
            f"{NOMBRES_ESTADO_CICLO_PDF.get(c['estado'], c['estado'])} ({c['fecha_programada'][:10]})",
            styles["Heading2"],
        ))
        datos = [["Artículo", "Cantidad", "Sucursal", "Pedido por", "Notas"]]
        for p in detalle["pedidos"]:
            datos.append([p["articulo_nombre"], str(p["cantidad"]), p.get("sucursal_nombre") or "—",
                          p["usuario_nombre"], p.get("notas") or "—"])
        if len(datos) == 1:
            datos.append(["— sin pedidos —", "", "", "", ""])
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

    if not ciclos:
        elementos.append(Paragraph("No hay ciclos de compra registrados.", styles["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    nombre_archivo = f"compras_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


@app.get("/api/compras/reporte.xlsx")
def reporte_compras_xlsx(usuario: dict = Depends(requiere_ver_compras)):
    from io import BytesIO
    from datetime import datetime as dt

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    ciclos = db.listar_ciclos_compra(usuario["empresa_id"])

    wb = Workbook()
    ws = wb.active
    ws.title = "Compras"
    encabezados = ["Ciclo", "Frecuencia", "Estado del ciclo", "Fecha programada",
                   "Artículo", "Cantidad", "Sucursal", "Pedido por", "Notas"]
    ws.append(encabezados)
    for col_idx, _ in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="D8192F", end_color="D8192F", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    for c in ciclos:
        detalle = db.obtener_ciclo_compra(usuario["empresa_id"], c["id"])
        filas = detalle["pedidos"] or [None]
        for p in filas:
            ws.append([
                c["nombre"], NOMBRES_FRECUENCIA_COMPRA_PDF.get(c["frecuencia"], c["frecuencia"]),
                NOMBRES_ESTADO_CICLO_PDF.get(c["estado"], c["estado"]), c["fecha_programada"][:10],
                p["articulo_nombre"] if p else "", p["cantidad"] if p else "",
                (p.get("sucursal_nombre") or "") if p else "", p["usuario_nombre"] if p else "",
                (p.get("notas") or "") if p else "",
            ])

    for col_idx, encabezado in enumerate(encabezados, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(encabezado), 14) + 4
    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    nombre_archivo = f"compras_{dt.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buffer.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


# ==================== CRM DE VENTAS ====================

class NuevoClienteCRM(BaseModel):
    nombre: str
    tipo: str = "prospecto"
    giro: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None
    microsip_cliente_id: Optional[int] = None


class ActualizacionClienteCRM(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    giro: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None


class NuevoContactoCRM(BaseModel):
    nombre: str
    puesto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    es_principal: bool = False


class ActualizacionContactoCRM(BaseModel):
    nombre: Optional[str] = None
    puesto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    es_principal: Optional[bool] = None


class NuevaOportunidadCRM(BaseModel):
    titulo: str
    valor_estimado: Optional[float] = None
    responsable_id: Optional[int] = None
    fecha_cierre_estimada: Optional[str] = None
    notas: Optional[str] = None


class ActualizacionOportunidadCRM(BaseModel):
    titulo: Optional[str] = None
    etapa: Optional[str] = None
    valor_estimado: Optional[float] = None
    responsable_id: Optional[int] = None
    fecha_cierre_estimada: Optional[str] = None
    notas: Optional[str] = None


class NuevaTareaCRM(BaseModel):
    oportunidad_id: Optional[int] = None
    titulo: str
    descripcion: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    asignado_a_id: Optional[int] = None


class NuevaInteraccionCRM(BaseModel):
    contacto_id: Optional[int] = None
    tipo: str = "nota"
    descripcion: str
    fecha: Optional[str] = None


@app.get("/api/crm/clientes")
def api_listar_clientes_crm(tipo: Optional[str] = None, buscar: Optional[str] = None, giro: Optional[str] = None,
                             usuario: dict = Depends(requiere_acceso_crm)):
    return db.listar_clientes_crm(usuario["empresa_id"], tipo=tipo, buscar=buscar, giro=giro)


@app.post("/api/crm/clientes")
def api_crear_cliente_crm(payload: NuevoClienteCRM, usuario: dict = Depends(requiere_acceso_crm)):
    if payload.tipo not in db.TIPOS_CLIENTE_CRM:
        raise HTTPException(status_code=400, detail="Tipo de cliente inválido")
    if payload.giro and payload.giro not in db.GIROS_CLIENTE_CRM:
        raise HTTPException(status_code=400, detail="Giro de cliente inválido")
    cliente_id = db.crear_cliente_crm(usuario["empresa_id"], payload.nombre, payload.tipo, payload.telefono,
                                       payload.email, payload.direccion, payload.notas, usuario["id"],
                                       microsip_cliente_id=payload.microsip_cliente_id, giro=payload.giro)
    return {"id": cliente_id}


@app.get("/api/crm/clientes/{cliente_id}")
def api_obtener_cliente_crm(cliente_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    cliente = db.obtener_cliente_crm(usuario["empresa_id"], cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente["contactos"] = db.listar_contactos_crm(cliente_id)
    cliente["oportunidades"] = db.listar_oportunidades_crm(usuario["empresa_id"], cliente_id=cliente_id)
    cliente["tareas"] = db.listar_tareas_crm(usuario["empresa_id"], cliente_id=cliente_id)
    cliente["interacciones"] = db.listar_interacciones_crm(usuario["empresa_id"], cliente_id)
    return cliente


@app.patch("/api/crm/clientes/{cliente_id}")
def api_actualizar_cliente_crm(cliente_id: int, payload: ActualizacionClienteCRM,
                                usuario: dict = Depends(requiere_acceso_crm)):
    if not db.obtener_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if payload.tipo and payload.tipo not in db.TIPOS_CLIENTE_CRM:
        raise HTTPException(status_code=400, detail="Tipo de cliente inválido")
    if payload.giro and payload.giro not in db.GIROS_CLIENTE_CRM:
        raise HTTPException(status_code=400, detail="Giro de cliente inválido")
    return db.actualizar_cliente_crm(usuario["empresa_id"], cliente_id, **payload.dict(exclude_unset=True))


@app.delete("/api/crm/clientes/{cliente_id}")
def api_eliminar_cliente_crm(cliente_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.eliminar_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"ok": True}


@app.post("/api/crm/clientes/{cliente_id}/contactos")
def api_crear_contacto_crm(cliente_id: int, payload: NuevoContactoCRM, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.obtener_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    contacto_id = db.crear_contacto_crm(cliente_id, payload.nombre, payload.puesto, payload.telefono,
                                         payload.email, payload.es_principal)
    return {"id": contacto_id}


@app.patch("/api/crm/contactos/{contacto_id}")
def api_actualizar_contacto_crm(contacto_id: int, payload: ActualizacionContactoCRM,
                                 usuario: dict = Depends(requiere_acceso_crm)):
    db.actualizar_contacto_crm(contacto_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.delete("/api/crm/contactos/{contacto_id}")
def api_eliminar_contacto_crm(contacto_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.eliminar_contacto_crm(contacto_id):
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return {"ok": True}


@app.get("/api/crm/oportunidades")
def api_listar_oportunidades_crm(cliente_id: Optional[int] = None, etapa: Optional[str] = None,
                                  usuario: dict = Depends(requiere_acceso_crm)):
    return db.listar_oportunidades_crm(usuario["empresa_id"], cliente_id=cliente_id, etapa=etapa)


@app.post("/api/crm/clientes/{cliente_id}/oportunidades")
def api_crear_oportunidad_crm(cliente_id: int, payload: NuevaOportunidadCRM,
                               usuario: dict = Depends(requiere_acceso_crm)):
    if not db.obtener_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    oportunidad_id = db.crear_oportunidad_crm(usuario["empresa_id"], cliente_id, payload.titulo,
                                               payload.valor_estimado, payload.responsable_id,
                                               payload.fecha_cierre_estimada, payload.notas, usuario["id"])
    return {"id": oportunidad_id}


@app.patch("/api/crm/oportunidades/{oportunidad_id}")
def api_actualizar_oportunidad_crm(oportunidad_id: int, payload: ActualizacionOportunidadCRM,
                                    usuario: dict = Depends(requiere_acceso_crm)):
    if payload.etapa and payload.etapa not in db.ETAPAS_OPORTUNIDAD_CRM:
        raise HTTPException(status_code=400, detail="Etapa inválida")
    db.actualizar_oportunidad_crm(usuario["empresa_id"], oportunidad_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.delete("/api/crm/oportunidades/{oportunidad_id}")
def api_eliminar_oportunidad_crm(oportunidad_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.eliminar_oportunidad_crm(usuario["empresa_id"], oportunidad_id):
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return {"ok": True}


@app.get("/api/crm/tareas")
def api_listar_tareas_crm(cliente_id: Optional[int] = None, solo_pendientes: bool = False,
                           solo_mias: bool = False, usuario: dict = Depends(requiere_acceso_crm)):
    asignado_a_id = usuario["id"] if solo_mias else None
    return db.listar_tareas_crm(usuario["empresa_id"], cliente_id=cliente_id, solo_pendientes=solo_pendientes,
                                 asignado_a_id=asignado_a_id)


@app.post("/api/crm/clientes/{cliente_id}/tareas")
def api_crear_tarea_crm(cliente_id: int, payload: NuevaTareaCRM, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.obtener_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    tarea_id = db.crear_tarea_crm(usuario["empresa_id"], cliente_id, payload.oportunidad_id, payload.titulo,
                                   payload.descripcion, payload.fecha_vencimiento, payload.asignado_a_id,
                                   usuario["id"])
    return {"id": tarea_id}


@app.post("/api/crm/tareas/{tarea_id}/completar")
def api_completar_tarea_crm(tarea_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    db.marcar_tarea_crm(usuario["empresa_id"], tarea_id, True)
    return {"ok": True}


@app.post("/api/crm/tareas/{tarea_id}/reabrir")
def api_reabrir_tarea_crm(tarea_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    db.marcar_tarea_crm(usuario["empresa_id"], tarea_id, False)
    return {"ok": True}


@app.delete("/api/crm/tareas/{tarea_id}")
def api_eliminar_tarea_crm(tarea_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.eliminar_tarea_crm(usuario["empresa_id"], tarea_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return {"ok": True}


@app.post("/api/crm/clientes/{cliente_id}/interacciones")
def api_crear_interaccion_crm(cliente_id: int, payload: NuevaInteraccionCRM,
                               usuario: dict = Depends(requiere_acceso_crm)):
    if not db.obtener_cliente_crm(usuario["empresa_id"], cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if payload.tipo not in db.TIPOS_INTERACCION_CRM:
        raise HTTPException(status_code=400, detail="Tipo de interacción inválido")
    interaccion_id = db.crear_interaccion_crm(usuario["empresa_id"], cliente_id, payload.contacto_id, payload.tipo,
                                               payload.descripcion, usuario["id"], payload.fecha)
    return {"id": interaccion_id}


@app.delete("/api/crm/interacciones/{interaccion_id}")
def api_eliminar_interaccion_crm(interaccion_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    if not db.eliminar_interaccion_crm(usuario["empresa_id"], interaccion_id):
        raise HTTPException(status_code=404, detail="Interacción no encontrada")
    return {"ok": True}


# ---- CRM: difusiones masivas por WhatsApp ----

class PreviewDifusionIn(BaseModel):
    tipo: Optional[str] = None
    giro: Optional[str] = None


class NuevaDifusionIn(BaseModel):
    nombre: str = Field(min_length=1)
    mensaje: str = Field(min_length=1)
    tipo: Optional[str] = None
    giro: Optional[str] = None


@app.post("/api/crm/difusiones/previsualizar")
def api_previsualizar_difusion(payload: PreviewDifusionIn, usuario: dict = Depends(requiere_acceso_crm)):
    return db.previsualizar_destinatarios_difusion(usuario["empresa_id"], tipo=payload.tipo, giro=payload.giro)


@app.get("/api/crm/difusiones")
def api_listar_difusiones(usuario: dict = Depends(requiere_acceso_crm)):
    return db.listar_difusiones(usuario["empresa_id"])


@app.get("/api/crm/difusiones/{difusion_id}")
def api_obtener_difusion(difusion_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    difusion = db.obtener_difusion(usuario["empresa_id"], difusion_id)
    if not difusion:
        raise HTTPException(status_code=404, detail="Difusión no encontrada")
    return difusion


@app.post("/api/crm/difusiones")
def api_crear_y_enviar_difusion(payload: NuevaDifusionIn, usuario: dict = Depends(requiere_acceso_crm)):
    """Crea la difusión y la manda de inmediato (sin programación por
    ahora). IMPORTANTE: con Twilio en modo Sandbox, solo le llega a
    números que ya se unieron al sandbox — con WhatsApp Business API de
    producción, el texto libre solo llega dentro de una conversación
    activa de 24h; fuera de eso Meta exige una plantilla pre-aprobada."""
    if not notifications.esta_habilitado(usuario["empresa_id"]):
        raise HTTPException(status_code=400, detail="WhatsApp (Twilio) no está configurado todavía para esta empresa.")
    destinatarios = db.previsualizar_destinatarios_difusion(usuario["empresa_id"], tipo=payload.tipo, giro=payload.giro)
    con_telefono = destinatarios["con_telefono"]
    if not con_telefono:
        raise HTTPException(status_code=400, detail="No hay ningún cliente con teléfono que cumpla ese filtro.")

    difusion_id = db.crear_difusion(usuario["empresa_id"], payload.nombre, payload.mensaje, payload.tipo, payload.giro, usuario["id"])
    enviados, fallidos = 0, 0
    for cliente in con_telefono:
        ok, error = notifications.enviar_difusion_individual(usuario["empresa_id"], cliente["telefono"], payload.mensaje)
        db.registrar_envio_difusion(
            difusion_id, cliente["id"], cliente["nombre"], cliente["telefono"],
            "enviado" if ok else "fallido", error,
        )
        if ok:
            enviados += 1
        else:
            fallidos += 1
    db.cerrar_difusion(difusion_id, len(con_telefono), enviados, fallidos)
    return {"id": difusion_id, "total_destinatarios": len(con_telefono), "total_enviados": enviados, "total_fallidos": fallidos}


# ---- Chatbot de WhatsApp para clientes ----

class ConfigKommo(BaseModel):
    subdominio: str = Field(min_length=1, max_length=100)
    token: Optional[str] = None


class ChatbotWhatsappIn(BaseModel):
    activo: bool


@app.get("/api/crm/chatbot-whatsapp")
def api_estado_chatbot_whatsapp(usuario: dict = Depends(requiere_acceso_crm)):
    return {
        "activo": db.chatbot_whatsapp_activo(usuario["empresa_id"]),
        "configurado_en_servidor": bool(os.getenv("WHATSAPP_CHATBOT_EMPRESA_ID", "").strip()),
    }


@app.patch("/api/crm/chatbot-whatsapp")
def api_actualizar_chatbot_whatsapp(payload: ChatbotWhatsappIn, usuario: dict = Depends(requiere_admin)):
    db.actualizar_chatbot_whatsapp_activo(usuario["empresa_id"], payload.activo)
    return {"ok": True}


@app.post("/webhook/whatsapp")
async def webhook_whatsapp_entrante(request: Request):
    """Twilio llama aquí cada vez que le llega un WhatsApp a tu número
    configurado — sin login (Twilio no puede mandar tu JWT), por eso este
    endpoint no usa Depends(requiere_...). La empresa a la que pertenece
    este número se define con la variable de entorno
    WHATSAPP_CHATBOT_EMPRESA_ID (el Twilio actual es UNO solo compartido
    por toda la app, no por empresa)."""
    form = await request.form()
    telefono_from = (form.get("From") or "").replace("whatsapp:", "").strip()
    mensaje = (form.get("Body") or "").strip()
    nombre_perfil = form.get("ProfileName")

    respuesta_texto = None
    empresa_id_str = os.getenv("WHATSAPP_CHATBOT_EMPRESA_ID", "").strip()
    if empresa_id_str and mensaje and telefono_from:
        try:
            empresa_id = int(empresa_id_str)
            if db.chatbot_whatsapp_activo(empresa_id):
                cliente, _es_nuevo = db.buscar_o_crear_cliente_crm_por_telefono(empresa_id, telefono_from, nombre_perfil)
                db.crear_interaccion_crm(empresa_id, cliente["id"], None, "whatsapp", f"Cliente: {mensaje}", None)
                empresa = db.obtener_empresa(empresa_id)
                marca = (empresa or {}).get("nombre") or "la empresa"
                respuesta_texto = chatbot_whatsapp.responder_mensaje_cliente(empresa_id, cliente["id"], mensaje, marca)
                db.crear_interaccion_crm(empresa_id, cliente["id"], None, "whatsapp", f"Chatbot: {respuesta_texto}", None)
        except Exception as e:
            print(f"[chatbot_whatsapp] Error procesando mensaje entrante: {e}")

    if respuesta_texto:
        cuerpo_xml = xml_escape_util.escape(respuesta_texto)
        twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{cuerpo_xml}</Message></Response>'
    else:
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(content=twiml, media_type="application/xml")


# ---- CRM: integración con Microsip (clientes reales, artículos y existencias) ----

@app.get("/api/crm/microsip/clientes")
def api_crm_buscar_clientes_microsip(q: str, usuario: dict = Depends(requiere_acceso_crm)):
    """Busca clientes YA DADOS DE ALTA en Microsip, para importarlos al CRM
    en vez de capturarlos a mano (mismo buscador que usa Reparaciones)."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.buscar_clientes(config, q, campo="nombre")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@app.get("/api/crm/microsip/articulos")
def api_crm_buscar_articulos_microsip(q: str, usuario: dict = Depends(requiere_acceso_crm)):
    """Búsqueda de artículos por nombre en Microsip (precio de lista + existencia
    real), para consultar sin salir del CRM mientras se habla con un cliente."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.buscar_productos_por_nombre(config, q)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@app.get("/api/crm/microsip/articulos/clave/{clave}")
def api_crm_buscar_articulo_por_clave_microsip(clave: str, usuario: dict = Depends(requiere_acceso_crm)):
    config = _config_microsip_o_error(usuario)
    try:
        resultado = microsip.buscar_producto_por_clave(config, clave)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")
    if not resultado:
        raise HTTPException(status_code=404, detail=f"No se encontró ningún producto con la clave '{clave}'")
    return resultado


@app.get("/api/crm/microsip/articulos/id/{articulo_id}")
def api_crm_buscar_articulo_por_id_microsip(articulo_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    """Detalle completo (precio de lista + existencia real por almacén) de
    un artículo ya localizado por nombre — la búsqueda por nombre solo trae
    nombre y clave, este segundo paso trae el precio y la existencia."""
    config = _config_microsip_o_error(usuario)
    try:
        resultado = microsip.buscar_producto_por_articulo_id(config, articulo_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")
    if not resultado:
        raise HTTPException(status_code=404, detail="No se encontró ese producto")
    return resultado


# ---- CRM: crear/ver cotizaciones ligadas a una oportunidad ----

@app.get("/api/crm/oportunidades/{oportunidad_id}/cotizaciones")
def api_crm_listar_cotizaciones_de_oportunidad(oportunidad_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    return db.listar_cotizaciones(usuario["empresa_id"], oportunidad_id=oportunidad_id)


@app.post("/api/crm/oportunidades/{oportunidad_id}/crear-cotizacion")
def api_crm_crear_cotizacion_desde_oportunidad(oportunidad_id: int, usuario: dict = Depends(requiere_acceso_crm)):
    """Crea una cotización en blanco (mismo Cotizador de Checador de precio),
    prellenada con los datos del cliente del CRM y ligada a esta oportunidad,
    para terminar de armarla en la pantalla de siempre."""
    if not usuario.get("acceso_checador_precio", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Checador de precio/Cotizador")
    oportunidad = db.obtener_oportunidad_crm(usuario["empresa_id"], oportunidad_id)
    if not oportunidad:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    cliente = db.obtener_cliente_crm(usuario["empresa_id"], oportunidad["cliente_id"])
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cotizacion = db.crear_cotizacion(
        usuario["empresa_id"], usuario["id"], cliente["nombre"], cliente.get("direccion"),
        cliente.get("telefono"), None, None, [], "publico", None, oportunidad_id=oportunidad_id,
    )
    return {"id": cotizacion["id"]}


# ---- CRM de ventas: importación desde Kommo (una sola vez) ----

def _credenciales_kommo_o_error(empresa_id):
    creds = db.obtener_credenciales_kommo(empresa_id)
    if not creds:
        raise HTTPException(status_code=400, detail="Guarda primero el subdominio y el token de Kommo.")
    return creds


@app.get("/api/crm/kommo/config")
def api_obtener_config_kommo(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_kommo(usuario["empresa_id"])
    return config or {"subdominio": None, "tiene_token": False}


@app.post("/api/crm/kommo/config")
def api_guardar_config_kommo(payload: ConfigKommo, usuario: dict = Depends(requiere_admin_completo)):
    db.guardar_config_kommo(usuario["empresa_id"], payload.subdominio.strip(), payload.token)
    return {"ok": True}


@app.post("/api/crm/kommo/probar-conexion")
def api_probar_conexion_kommo(usuario: dict = Depends(requiere_admin_completo)):
    creds = _credenciales_kommo_o_error(usuario["empresa_id"])
    ok, mensaje = kommo_import.probar_conexion(creds["subdominio"], creds["token"])
    if not ok:
        raise HTTPException(status_code=400, detail=mensaje)
    return {"ok": True, "mensaje": mensaje}


@app.post("/api/crm/kommo/importar/clientes")
def api_kommo_importar_clientes(usuario: dict = Depends(requiere_admin_completo)):
    """Paso 1 de 4: empresas y contactos de Kommo -> crm_clientes/crm_contactos.
    Un contacto sin empresa se importa como su propio cliente. Es seguro
    volver a correrlo (usa crm_kommo_map para no duplicar nada)."""
    creds = _credenciales_kommo_o_error(usuario["empresa_id"])
    empresa_id = usuario["empresa_id"]
    empresas_creadas = empresas_actualizadas = 0
    contactos_creados = contactos_actualizados = 0
    errores = []
    try:
        for empresa_kommo in kommo_import.listar_companies(creds["subdominio"], creds["token"]):
            try:
                existia = db.kommo_map_obtener(empresa_id, "company", empresa_kommo["id"]) is not None
                telefono = kommo_import.extraer_campo(empresa_kommo.get("custom_fields_values"), "PHONE")
                email = kommo_import.extraer_campo(empresa_kommo.get("custom_fields_values"), "EMAIL")
                db.kommo_upsert_cliente(
                    empresa_id, "company", empresa_kommo["id"],
                    empresa_kommo.get("name") or f"Empresa Kommo #{empresa_kommo['id']}",
                    telefono, email, usuario["id"],
                )
                if existia:
                    empresas_actualizadas += 1
                else:
                    empresas_creadas += 1
            except Exception as e:
                errores.append(f"Empresa Kommo #{empresa_kommo.get('id')}: {e}")

        for contacto in kommo_import.listar_contacts(creds["subdominio"], creds["token"]):
            try:
                telefono = kommo_import.extraer_campo(contacto.get("custom_fields_values"), "PHONE")
                email = kommo_import.extraer_campo(contacto.get("custom_fields_values"), "EMAIL")
                puesto = kommo_import.extraer_campo(contacto.get("custom_fields_values"), "POSITION")
                nombre_contacto = contacto.get("name") or f"Contacto Kommo #{contacto['id']}"
                companias = ((contacto.get("_embedded") or {}).get("companies")) or []
                cliente_id = None
                if companias:
                    mapa_empresa = db.kommo_map_obtener(empresa_id, "company", companias[0]["id"])
                    if mapa_empresa:
                        cliente_id = mapa_empresa["tickets_id"]
                es_principal = cliente_id is None
                if cliente_id is None:
                    # sin empresa conocida en Kommo -- el contacto es su propio cliente en el CRM
                    cliente_id = db.kommo_upsert_cliente(
                        empresa_id, "contact_standalone", contacto["id"], nombre_contacto,
                        telefono, email, usuario["id"],
                    )

                existia = db.kommo_map_obtener(empresa_id, "contact", contacto["id"]) is not None
                db.kommo_upsert_contacto(
                    empresa_id, cliente_id, contacto["id"], nombre_contacto,
                    puesto, telefono, email, es_principal,
                )
                if existia:
                    contactos_actualizados += 1
                else:
                    contactos_creados += 1
            except Exception as e:
                errores.append(f"Contacto Kommo #{contacto.get('id')}: {e}")
    except kommo_import.KommoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True,
        "empresas_creadas": empresas_creadas, "empresas_actualizadas": empresas_actualizadas,
        "contactos_creados": contactos_creados, "contactos_actualizados": contactos_actualizados,
        "errores": errores,
    }


@app.post("/api/crm/kommo/importar/oportunidades")
def api_kommo_importar_oportunidades(usuario: dict = Depends(requiere_admin_completo)):
    """Paso 2 de 4: leads de Kommo -> crm_oportunidades, con la etapa
    (status) tal como está en Kommo. Corre el paso 1 primero -- si un lead
    no tiene ni empresa ni contacto ya importado, se crea un cliente a
    partir del propio lead para no perder el dato."""
    creds = _credenciales_kommo_o_error(usuario["empresa_id"])
    empresa_id = usuario["empresa_id"]
    creadas = actualizadas = 0
    clientes_creados_desde_lead = 0
    errores = []
    try:
        etapas = kommo_import.obtener_pipelines_y_etapas(creds["subdominio"], creds["token"])
        mapa_empresas = db.kommo_map_cargar_todo(empresa_id, "company")
        mapa_contactos = db.kommo_map_cargar_todo(empresa_id, "contact")
        mapa_contactos_standalone = db.kommo_map_cargar_todo(empresa_id, "contact_standalone")

        for lead in kommo_import.listar_leads(creds["subdominio"], creds["token"]):
            try:
                cliente_id = None
                id_empresa_lead = kommo_import.empresa_principal_del_lead(lead)
                if id_empresa_lead is not None and id_empresa_lead in mapa_empresas:
                    cliente_id = mapa_empresas[id_empresa_lead]["cliente_id"]
                if cliente_id is None:
                    id_contacto_lead = kommo_import.contacto_principal_del_lead(lead)
                    if id_contacto_lead is not None:
                        if id_contacto_lead in mapa_contactos:
                            cliente_id = mapa_contactos[id_contacto_lead]["cliente_id"]
                        elif id_contacto_lead in mapa_contactos_standalone:
                            cliente_id = mapa_contactos_standalone[id_contacto_lead]["cliente_id"]
                if cliente_id is None:
                    cliente_id = db.kommo_upsert_cliente(
                        empresa_id, "lead_sin_contacto", lead["id"],
                        f"(Sin datos de contacto) {lead.get('name') or 'Lead #' + str(lead['id'])}",
                        None, None, usuario["id"],
                    )
                    clientes_creados_desde_lead += 1

                etapa_nombre = etapas.get(
                    (lead.get("pipeline_id"), lead.get("status_id")), f"Etapa {lead.get('status_id')}"
                )
                es_ganado = lead.get("status_id") == 142
                existia = db.kommo_map_obtener(empresa_id, "lead", lead["id"]) is not None
                precio = lead.get("price")
                db.kommo_upsert_oportunidad(
                    empresa_id, cliente_id, lead["id"],
                    lead.get("name") or f"Oportunidad Kommo #{lead['id']}",
                    etapa_nombre, float(precio) if precio else None,
                    usuario["id"], es_ganado,
                )
                if existia:
                    actualizadas += 1
                else:
                    creadas += 1
            except Exception as e:
                errores.append(f"Lead Kommo #{lead.get('id')}: {e}")
    except kommo_import.KommoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True, "creadas": creadas, "actualizadas": actualizadas,
        "clientes_creados_desde_lead": clientes_creados_desde_lead, "errores": errores,
    }


@app.post("/api/crm/kommo/importar/notas")
def api_kommo_importar_notas(usuario: dict = Depends(requiere_admin_completo)):
    """Paso 3 de 4: notas de Kommo (de leads, contactos y empresas) ->
    crm_interacciones. Corre los pasos 1 y 2 primero -- una nota de una
    entidad que no se haya podido importar antes se cuenta aparte, no se
    pierde silenciosamente."""
    from datetime import datetime as dt
    creds = _credenciales_kommo_o_error(usuario["empresa_id"])
    empresa_id = usuario["empresa_id"]
    creadas = 0
    sin_cliente_asociado = 0
    errores = []
    try:
        mapa_empresas = db.kommo_map_cargar_todo(empresa_id, "company")
        mapa_contactos = db.kommo_map_cargar_todo(empresa_id, "contact")
        mapa_contactos_standalone = db.kommo_map_cargar_todo(empresa_id, "contact_standalone")
        mapa_leads = db.kommo_map_cargar_todo(empresa_id, "lead")
        mapas_por_tipo = {"leads": mapa_leads, "companies": mapa_empresas}

        for tipo_entidad in ("leads", "contacts", "companies"):
            for nota in kommo_import.listar_notas(creds["subdominio"], creds["token"], tipo_entidad):
                try:
                    if tipo_entidad == "contacts":
                        fila = mapa_contactos.get(nota.get("entity_id")) or mapa_contactos_standalone.get(nota.get("entity_id"))
                    else:
                        fila = mapas_por_tipo[tipo_entidad].get(nota.get("entity_id"))
                    cliente_id = fila["cliente_id"] if fila else None
                    if cliente_id is None:
                        sin_cliente_asociado += 1
                        continue
                    try:
                        fecha = dt.fromtimestamp(nota["created_at"]).isoformat(timespec="seconds")
                    except Exception:
                        fecha = dt.now().isoformat(timespec="seconds")
                    _, se_creo = db.kommo_insertar_interaccion_si_no_existe(
                        empresa_id, cliente_id, nota["id"], kommo_import.texto_de_nota(nota), fecha,
                    )
                    if se_creo:
                        creadas += 1
                except Exception as e:
                    errores.append(f"Nota Kommo #{nota.get('id')}: {e}")
    except kommo_import.KommoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "creadas": creadas, "sin_cliente_asociado": sin_cliente_asociado, "errores": errores}


@app.post("/api/crm/kommo/importar/tareas")
def api_kommo_importar_tareas(usuario: dict = Depends(requiere_admin_completo)):
    """Paso 4 de 4: tareas de Kommo -> crm_tareas."""
    from datetime import datetime as dt
    creds = _credenciales_kommo_o_error(usuario["empresa_id"])
    empresa_id = usuario["empresa_id"]
    creadas = 0
    sin_cliente_asociado = 0
    errores = []
    try:
        mapa_empresas = db.kommo_map_cargar_todo(empresa_id, "company")
        mapa_contactos = db.kommo_map_cargar_todo(empresa_id, "contact")
        mapa_contactos_standalone = db.kommo_map_cargar_todo(empresa_id, "contact_standalone")
        mapa_leads = db.kommo_map_cargar_todo(empresa_id, "lead")
        mapas_por_tipo = {"leads": mapa_leads, "companies": mapa_empresas}

        for tarea in kommo_import.listar_tareas(creds["subdominio"], creds["token"]):
            try:
                tipo_entidad = tarea.get("entity_type")
                if tipo_entidad == "contacts":
                    fila = mapa_contactos.get(tarea.get("entity_id")) or mapa_contactos_standalone.get(tarea.get("entity_id"))
                else:
                    fila = mapas_por_tipo.get(tipo_entidad, {}).get(tarea.get("entity_id"))
                cliente_id = fila["cliente_id"] if fila else None
                if cliente_id is None:
                    sin_cliente_asociado += 1
                    continue
                try:
                    fecha_vencimiento = dt.fromtimestamp(tarea["complete_till"]).isoformat(timespec="seconds")
                except Exception:
                    fecha_vencimiento = None
                _, se_creo = db.kommo_insertar_tarea_si_no_existe(
                    empresa_id, cliente_id, tarea["id"],
                    tarea.get("text") or "Tarea importada de Kommo",
                    fecha_vencimiento, bool(tarea.get("is_completed")), usuario["id"],
                )
                if se_creo:
                    creadas += 1
            except Exception as e:
                errores.append(f"Tarea Kommo #{tarea.get('id')}: {e}")
    except kommo_import.KommoError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "creadas": creadas, "sin_cliente_asociado": sin_cliente_asociado, "errores": errores}


# ==================== RECURSOS HUMANOS (incidencias) ====================

class NuevaIncidenciaRH(BaseModel):
    tipo: str
    fecha_inicio: str
    fecha_fin: Optional[str] = None
    motivo: Optional[str] = None
    foto_base64: Optional[str] = None
    horas: Optional[float] = Field(default=None, ge=0, le=24)


class ResolverIncidenciaRH(BaseModel):
    estado: str  # 'aprobada' o 'rechazada'
    respuesta_admin: Optional[str] = None


@app.get("/api/rh/incidencias")
def api_listar_incidencias_rh(estado: Optional[str] = None, usuario: dict = Depends(requiere_ver_rh)):
    # El administrador y quien tenga "Datos RH" ven las de todos; cualquier
    # otro rol solo ve las suyas (para que cada quien siga viendo el estatus
    # de lo suyo, aunque siga esperando al encargado de su sucursal). Cuando
    # se piden "todas" sin filtro, no se mezclan las que ni siquiera ha visto
    # el encargado todavía — esas están en la bandeja del encargado, no aquí.
    # RH también ve las que esperan a la encargada (marcadas así) y las puede
    # decidir directamente si hace falta.
    puede_ver_todas = usuario["rol"] == "admin" or usuario.get("acceso_datos_empleado_rh", False)
    usuario_id_filtro = None if puede_ver_todas else usuario["id"]
    return db.listar_incidencias_rh(usuario["empresa_id"], usuario_id_filtro, estado)


def _saldo_vacaciones_ajustado(persona: dict, dias_consumidos_microsip: float) -> Optional[dict]:
    """Si esta persona tiene fecha_ingreso_ajustada activa, recalcula su
    saldo con el mínimo de LFT desde esa fecha — sumando a lo consumido
    tanto lo real de Microsip (dias_consumidos_microsip) como lo que se
    haya registrado en esta app desde que se activó el ajuste (tabla
    vacaciones_ajuste_usuario). None si no tiene ajuste activo.

    Solo lo 'aprobada' cuenta como consumido de verdad; lo 'pendiente'
    (esperando a RH) se resta aparte de los disponibles para que no se
    pueda pedir el mismo día dos veces mientras se aprueba, pero sin
    darlo por gastado todavía — si RH rechaza, el día se libera solo."""
    if not persona.get("fecha_ingreso_ajustada"):
        return None
    dias_correspondientes = db.dias_correspondientes_lft_acumulado(persona["fecha_ingreso_ajustada"])
    registros_app = db.listar_vacaciones_ajuste_usuario(persona["id"])
    dias_consumidos_app = sum(float(r["dias"]) for r in registros_app if r["estado"] == "aprobada")
    dias_pendientes_app = sum(float(r["dias"]) for r in registros_app if r["estado"] == "pendiente")
    # Empresas sin Microsip: lo que ya había tomado antes de llevarlo aquí (NULL en Mark Inc).
    dias_previos = float(persona.get("vacaciones_tomadas_previas") or 0)
    dias_consumidos_total = dias_consumidos_microsip + dias_consumidos_app + dias_previos
    return {
        "dias_otorgados": dias_correspondientes,
        "dias_consumidos": dias_consumidos_total,
        "dias_pendientes": dias_pendientes_app,
        "dias_disponibles": dias_correspondientes - dias_consumidos_total - dias_pendientes_app,
        "registros_app": registros_app,
    }


@app.get("/api/mis-vacaciones")
def api_mis_vacaciones(usuario: dict = Depends(requiere_empresa)):
    """Cada quien puede ver SUS PROPIAS vacaciones — no necesita el
    permiso de RH de ver datos de otros, porque es su propia
    información. Si su antigüedad fue corregida (ver ajuste-antiguedad),
    aquí mismo puede pedir sus vacaciones DESDE LA APP mientras Microsip
    siga con la fecha vieja — esto se revisa PRIMERO y no depende de que
    Microsip tenga todo en orden (número de empleado, conexión, etc.),
    porque justo esos son los casos típicos de alguien con el ajuste
    activo: se intenta traer lo consumido de Microsip nada más de
    adorno, y si no se puede, se sigue con 0 en vez de bloquear todo."""
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])
    if not persona:
        return {"disponible": False, "motivo": "Usuario no encontrado."}

    if persona.get("fecha_ingreso_ajustada"):
        dias_consumidos_microsip = 0.0
        if persona.get("numero_empleado"):
            config = db.obtener_config_microsip(usuario["empresa_id"])
            if config and config.get("microsip_host"):
                try:
                    empleado_ms = microsip.obtener_empleado_por_numero(config, persona["numero_empleado"])
                    if empleado_ms:
                        periodos = microsip.obtener_periodos_vacacionales_empleado(config, empleado_ms["empleado_id"])
                        dias_consumidos_microsip = sum(p["dias_consumidos"] for p in periodos)
                except Exception:
                    pass  # Microsip no respondió — seguimos con 0 de consumido ahí, no bloqueamos el ajuste por esto
        return {
            "disponible": True,
            "saldo": None,
            "periodos": [],
            "saldo_ajustado": _saldo_vacaciones_ajustado(persona, dias_consumidos_microsip),
        }

    if not persona.get("numero_empleado"):
        return {"disponible": False, "motivo": "No tienes número de empleado capturado — pídele al administrador que lo agregue en tu perfil."}

    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        return {"disponible": False, "motivo": "Microsip no está configurado todavía."}

    try:
        empleado_ms = microsip.obtener_empleado_por_numero(config, persona["numero_empleado"])
        if not empleado_ms:
            return {"disponible": False, "motivo": "No se encontró tu número de empleado en Microsip."}
        periodos = microsip.obtener_periodos_vacacionales_empleado(config, empleado_ms["empleado_id"])
        dias_consumidos = sum(p["dias_consumidos"] for p in periodos)
        disponibles = _dias_vigentes_microsip(periodos)
        solicitudes = db.listar_solicitudes_vacaciones_microsip(usuario["empresa_id"], usuario["id"])
        pendientes = sum(s["dias"] or 0 for s in solicitudes if s["estado"] == "pendiente")
        return {
            "disponible": True,
            "saldo": {
                "dias_otorgados": sum(p["dias_otorgados"] for p in periodos),
                "dias_consumidos": dias_consumidos,
                "dias_disponibles": sum(p["dias_disponibles"] for p in periodos),
            },
            "periodos": periodos,
            "saldo_ajustado": _saldo_vacaciones_ajustado(persona, dias_consumidos),
            # Pedir vacaciones desde la app → RH aprueba → se registran en Microsip.
            "puede_solicitar": _vacaciones_microsip_activas(usuario["empresa_id"]) and disponibles - pendientes > 0,
            "dias_pendientes": pendientes,
            "dias_para_pedir": max(round(disponibles - pendientes, 2), 0),
            "solicitudes": solicitudes,
        }
    except Exception as e:
        return {"disponible": False, "motivo": f"Error consultando Microsip: {e}"}


class SolicitudVacacionAjuste(BaseModel):
    fecha_inicio: str
    dias: float = Field(gt=0)
    descripcion: Optional[str] = None


@app.post("/api/mis-vacaciones/solicitar")
def api_solicitar_vacacion_ajuste(payload: SolicitudVacacionAjuste, usuario: dict = Depends(requiere_empresa)):
    """Pedir vacaciones DESDE LA APP — solo para quien tenga
    fecha_ingreso_ajustada activa (mientras Microsip no tenga la fecha
    correcta, sus vacaciones normales de Microsip están mal). En cuanto
    RH corrija Microsip y quite el ajuste, esto se cierra y vuelve a
    pedirlas por Microsip como todos.

    La solicitud queda 'pendiente' — no se descuenta el día hasta que RH
    (quien tenga 'Datos RH') la apruebe en /api/rh/vacaciones-ajuste."""
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])
    if persona and not persona.get("fecha_ingreso_ajustada"):
        return _solicitar_vacaciones_microsip(usuario, persona, payload)
    if not persona or not persona.get("fecha_ingreso_ajustada"):
        raise HTTPException(status_code=403, detail="Esto solo aplica si tu antigüedad fue corregida en la app — de otro modo, tus vacaciones se piden directo en Microsip.")
    dias_consumidos_microsip = 0.0
    if persona.get("numero_empleado"):
        config = db.obtener_config_microsip(usuario["empresa_id"])
        if config and config.get("microsip_host"):
            try:
                empleado_ms = microsip.obtener_empleado_por_numero(config, persona["numero_empleado"])
                if empleado_ms:
                    periodos = microsip.obtener_periodos_vacacionales_empleado(config, empleado_ms["empleado_id"])
                    dias_consumidos_microsip = sum(p["dias_consumidos"] for p in periodos)
            except Exception:
                pass  # si Microsip no responde, seguimos con 0 de consumido ahí — mejor pecar de permisivo que bloquear la solicitud
    saldo = _saldo_vacaciones_ajustado(persona, dias_consumidos_microsip)
    if payload.dias > saldo["dias_disponibles"]:
        raise HTTPException(status_code=400, detail=f"No tienes suficientes días disponibles (te quedan {saldo['dias_disponibles']:g}, pediste {payload.dias:g})")
    nuevo_id = db.solicitar_vacacion_ajuste_usuario(usuario["id"], payload.fecha_inicio, payload.dias, payload.descripcion)
    _avisar_vacaciones_rh(usuario, payload.fecha_inicio, payload.dias)
    return {"id": nuevo_id, "estado": "pendiente"}


# ---- Vacaciones de Microsip pedidas desde la app ----
# Para quien NO tiene ajuste de antigüedad: ve su saldo real de Microsip,
# pide sus días aquí, RH (Datos RH) aprueba y en ese momento se registran en
# Microsip Nómina (VACACIONES) — como la app de vacaciones de Microsip.

def _avisar_vacaciones_rh(usuario, fecha_inicio, dias):
    """Nueva solicitud de vacaciones → a quien las aprueba (Datos RH)."""
    avisos.avisar_seguro(db.ids_usuarios_con_permiso(usuario["empresa_id"], "acceso_datos_empleado_rh", incluir_admin=False),
                         "🏖️ Solicitud de vacaciones", f"{usuario.get('nombre', '')} pide {dias:g} día(s) desde el {str(fecha_inicio)[:10]}.",
                         modulo="rh", extra={"pantalla": "vacaciones_rh"}, excluir=[usuario["id"]])


def _avisar_vacaciones_resueltas(usuario_id, estado, fecha_inicio, dias, respuesta=None):
    avisos.avisar_seguro([usuario_id], f"{'✅' if estado == 'aprobada' else '❌'} Tus vacaciones fueron {'APROBADAS' if estado == 'aprobada' else 'RECHAZADAS'}",
                         f"{dias:g} día(s) desde el {str(fecha_inicio)[:10]}" + (f" · {respuesta}" if respuesta else ""),
                         modulo="rh", extra={"pantalla": "vacaciones"})


def _vacaciones_microsip_activas(empresa_id):
    if not MICROSIP_DISPONIBLE:
        return False
    cfg = db.obtener_config_microsip_escritura(empresa_id) or {}
    return bool(cfg.get("rh_vac_microsip_activa") and cfg.get("microsip_host"))


def _dias_vigentes_microsip(periodos, desde=None):
    hoy = (desde or db.ahora().date()).isoformat()
    return round(sum(p["dias_disponibles"] for p in periodos
                     if p["dias_disponibles"] > 0 and (not p.get("fecha_caducidad") or p["fecha_caducidad"][:10] >= hoy)), 2)


def _solicitar_vacaciones_microsip(usuario, persona, payload):
    if not _vacaciones_microsip_activas(usuario["empresa_id"]):
        raise HTTPException(status_code=403, detail="Pedir vacaciones desde la app todavía no está activado — pídelas con RH.")
    if not persona.get("numero_empleado"):
        raise HTTPException(status_code=400, detail="No tienes número de empleado capturado — pídele a RH que lo agregue en tu perfil.")
    try:
        inicio = date.fromisoformat(payload.fecha_inicio[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    if inicio < db.ahora().date():
        raise HTTPException(status_code=400, detail="La fecha de inicio ya pasó.")
    if payload.dias * 2 != int(payload.dias * 2):
        raise HTTPException(status_code=400, detail="Los días van enteros o medios (ej. 1, 1.5, 2).")
    config = db.obtener_config_microsip(usuario["empresa_id"])
    try:
        emp = microsip.obtener_empleado_por_numero(config, persona["numero_empleado"])
        if not emp:
            raise HTTPException(status_code=400, detail="No se encontró tu número de empleado en Microsip.")
        periodos = microsip.obtener_periodos_vacacionales_empleado(config, emp["empleado_id"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {e}")
    disponibles = _dias_vigentes_microsip(periodos, max(inicio, db.ahora().date()))
    pendientes = sum(s["dias"] or 0 for s in db.listar_solicitudes_vacaciones_microsip(usuario["empresa_id"], usuario["id"], "pendiente"))
    if payload.dias > disponibles - pendientes + 1e-6:
        raise HTTPException(status_code=400, detail=f"No tienes suficientes días: te quedan {max(disponibles - pendientes, 0):g}"
                                                    f"{f' (y {pendientes:g} ya pedidos esperando a RH)' if pendientes else ''}, pediste {payload.dias:g}.")
    nuevo = db.crear_solicitud_vacaciones_microsip(usuario["empresa_id"], usuario["id"], inicio, payload.dias, _limpio(payload.descripcion))
    _avisar_vacaciones_rh(usuario, inicio, payload.dias)
    return {"id": nuevo, "estado": "pendiente", "tipo": "microsip"}


@app.post("/api/mis-vacaciones/solicitudes/{solicitud_id}/cancelar")
def api_cancelar_mi_solicitud_vacaciones(solicitud_id: int, usuario: dict = Depends(requiere_empresa)):
    if not db.cancelar_solicitud_vacaciones_microsip(solicitud_id, usuario["id"]):
        raise HTTPException(status_code=400, detail="Solo puedes cancelar tus solicitudes que siguen pendientes.")
    return {"ok": True}


@app.get("/api/rh/vacaciones-microsip")
def api_listar_vacaciones_microsip_rh(estado: Optional[str] = "pendiente", usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.listar_solicitudes_vacaciones_microsip(usuario["empresa_id"], None, None if estado in (None, "", "todas") else estado)


class ResolverVacacionMicrosip(BaseModel):
    estado: str  # aprobada | rechazada
    respuesta_admin: Optional[str] = None


@app.post("/api/rh/vacaciones-microsip/{solicitud_id}/resolver")
def api_resolver_vacacion_microsip_rh(solicitud_id: int, payload: ResolverVacacionMicrosip, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Aprobar = registrarla en Microsip en ese momento (si Microsip no la
    acepta, sigue pendiente con el error para reintentar). Rechazar = solo aquí."""
    if payload.estado not in ("aprobada", "rechazada"):
        raise HTTPException(status_code=400, detail="Estado inválido")
    sol = db.obtener_solicitud_vacaciones_microsip(usuario["empresa_id"], solicitud_id)
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if sol["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Esta solicitud ya se resolvió.")
    respuesta = _limpio(payload.respuesta_admin)
    if payload.estado == "rechazada":
        db.resolver_solicitud_vacaciones_microsip(solicitud_id, usuario["id"], "rechazada", respuesta)
        _avisar_vacaciones_resueltas(sol["usuario_id"], "rechazada", sol["fecha_inicio"], sol["dias"] or 0, respuesta)
        return {"ok": True, "estado": "rechazada"}
    cfg = _config_escritura_o_error(usuario["empresa_id"])
    if not sol.get("numero_empleado"):
        raise HTTPException(status_code=400, detail="Esa persona no tiene número de empleado de Microsip.")
    try:
        r = microsip_vacaciones.registrar_vacacion(
            cfg, numero_empleado=sol["numero_empleado"], fecha_inicio=sol["fecha_inicio"], dias=sol["dias"],
            descripcion=sol.get("descripcion") or "Vacaciones (pedidas desde la app)",
            estatus=cfg.get("rh_vac_microsip_estatus"), usuario=cfg.get("rh_vac_microsip_usuario"))
    except microsip_escritura.ErrorMicrosip as e:
        db.marcar_error_solicitud_vacaciones_microsip(solicitud_id, str(e))
        raise HTTPException(status_code=400, detail=f"Microsip no aceptó las vacaciones — {e}")
    except Exception as e:
        db.marcar_error_solicitud_vacaciones_microsip(solicitud_id, str(e))
        raise HTTPException(status_code=400, detail=f"No se pudo conectar con Microsip: {e}")
    db.resolver_solicitud_vacaciones_microsip(solicitud_id, usuario["id"], "aprobada", respuesta, r.get("vacacion_id"))
    _avisar_vacaciones_resueltas(sol["usuario_id"], "aprobada", sol["fecha_inicio"], sol["dias"] or 0, respuesta)
    return {"ok": True, "estado": "aprobada", "microsip": r}


class CancelarVacacionIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)
    solo_en_app: bool = False   # si ya no existe en Microsip, cancelarla solo aquí


def _avisar_vacacion_cancelada(usuario_id, fecha_inicio, dias, motivo):
    try:
        avisos.avisar_seguro([usuario_id], "🏖️ Vacaciones CANCELADAS por RH",
                             f"{fecha_inicio} · {float(dias or 0):g} día(s). Motivo: {motivo}"[:300], modulo="rh")
    except Exception as e:
        print(f"[avisos] vacación cancelada: {e}")


@app.post("/api/rh/vacaciones-microsip/{solicitud_id}/cancelar")
def api_cancelar_vacacion_microsip_rh(solicitud_id: int, payload: CancelarVacacionIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """RH cancela una vacación pedida desde la app (pendiente o ya aprobada). Si ya estaba
    aprobada, se borra de Microsip y los días regresan al saldo de la persona."""
    sol = db.obtener_solicitud_vacaciones_microsip(usuario["empresa_id"], solicitud_id)
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if sol["estado"] not in ("pendiente", "aprobada"):
        raise HTTPException(status_code=400, detail="Solo se pueden cancelar vacaciones pendientes o aprobadas.")
    motivo = payload.motivo.strip()
    resultado = None
    if sol["estado"] == "aprobada" and sol.get("microsip_vacacion_id") and not payload.solo_en_app:
        cfg = _config_escritura_o_error(usuario["empresa_id"])
        try:
            resultado = microsip_vacaciones.cancelar_vacacion(cfg, numero_empleado=sol.get("numero_empleado"),
                                                              vacacion_id=sol["microsip_vacacion_id"], dias=sol["dias"] or 0,
                                                              usuario=cfg.get("rh_vac_microsip_usuario"))
        except microsip_escritura.ErrorMicrosip as e:
            raise HTTPException(status_code=400, detail=f"Microsip no dejó cancelarla — {e}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"No se pudo conectar con Microsip: {e}")
    if not db.cancelar_vacacion_por_rh("microsip", solicitud_id, usuario["id"], motivo):
        raise HTTPException(status_code=409, detail="Esta solicitud ya cambió; recarga la lista.")
    _avisar_vacacion_cancelada(sol["usuario_id"], sol["fecha_inicio"], sol["dias"], motivo)
    return {"ok": True, "microsip": resultado}


@app.post("/api/rh/vacaciones-ajuste/{vacacion_id}/cancelar")
def api_cancelar_vacacion_ajuste_rh(vacacion_id: int, payload: CancelarVacacionIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Cancela una vacación de ajuste de antigüedad (pendiente o aprobada): deja de contar en su saldo."""
    registro = db.obtener_vacacion_ajuste_usuario(vacacion_id)
    if not registro or not db.obtener_usuario_por_id(usuario["empresa_id"], registro["usuario_id"]):
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if registro.get("estado") not in ("pendiente", "aprobada"):
        raise HTTPException(status_code=400, detail="Solo se pueden cancelar vacaciones pendientes o aprobadas.")
    motivo = payload.motivo.strip()
    if not db.cancelar_vacacion_por_rh("ajuste", vacacion_id, usuario["id"], motivo):
        raise HTTPException(status_code=409, detail="Este registro ya cambió; recarga la lista.")
    _avisar_vacacion_cancelada(registro["usuario_id"], registro.get("fecha_inicio"), registro.get("dias"), motivo)
    return {"ok": True}


class ConfigVacacionesMicrosipIn(BaseModel):
    activa: bool = False
    estatus: Optional[str] = Field(default=None, max_length=10)
    usuario: Optional[str] = Field(default=None, max_length=31)


class DiagnosticoVacacionesIn(BaseModel):
    numero_empleado: Optional[str] = None


@app.get("/api/microsip/vacaciones")
def api_config_vacaciones_microsip(usuario: dict = Depends(requiere_admin_completo)):
    cfg = db.obtener_config_microsip_escritura(usuario["empresa_id"]) or {}
    return {"activa": bool(cfg.get("rh_vac_microsip_activa")), "estatus": cfg.get("rh_vac_microsip_estatus"),
            "usuario": cfg.get("rh_vac_microsip_usuario")}


@app.put("/api/microsip/vacaciones")
def api_guardar_config_vacaciones_microsip(payload: ConfigVacacionesMicrosipIn, usuario: dict = Depends(requiere_admin_completo)):
    db.guardar_config_vacaciones_microsip(usuario["empresa_id"], payload.activa,
                                          (payload.estatus or "").strip() or None,
                                          (_limpio(payload.usuario) or "").upper() or None)
    return api_config_vacaciones_microsip(usuario)


@app.post("/api/microsip/vacaciones/diagnostico")
def api_diagnostico_vacaciones_microsip(payload: DiagnosticoVacacionesIn, usuario: dict = Depends(requiere_admin_completo)):
    """Cómo guarda Microsip las vacaciones y, con un número de empleado, una
    prueba completa de 1 día que se deshace — no deja nada en Microsip."""
    cfg = _config_escritura_o_error(usuario["empresa_id"])
    try:
        return microsip_vacaciones.diagnostico(cfg, (payload.numero_empleado or "").strip() or None, cfg.get("rh_vac_microsip_estatus"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"El diagnóstico falló: {e}")


@app.get("/api/rh/ausencias")
def api_bitacora_ausencias_rh(usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Bitácora combinada de quién va a estar (o estuvo) ausente y
    cuándo: vacaciones aprobadas en Microsip (se jala en vivo, así que
    en cuanto RH la aprueba ahí, aparece aquí solo, sin sincronizar
    nada a mano) + incidencias de RH de esta app (permisos, faltas,
    etc.) — ordenado del más próximo/reciente al más viejo."""
    usuarios = db.listar_usuarios(usuario["empresa_id"])
    eventos = []

    numeros_empleado = [u["numero_empleado"] for u in usuarios if u.get("numero_empleado")]
    if numeros_empleado:
        config = db.obtener_config_microsip(usuario["empresa_id"])
        if config and config.get("microsip_host"):
            try:
                vacaciones = microsip.obtener_vacaciones_multiples_empleados(config, numeros_empleado)
                for v in vacaciones:
                    eventos.append({
                        "origen": "vacaciones_microsip",
                        "persona": v["nombre_completo"],
                        "tipo": "Vacaciones",
                        "fecha_inicio": v["fecha_inicial"],
                        "fecha_fin": v["fecha_fin"],
                        "estado": v["estatus"],
                        "detalle": v["descripcion"],
                    })
            except Exception as e:
                print(f"[rh_ausencias] Error consultando vacaciones de Microsip: {e}")

    incidencias = db.listar_incidencias_rh(usuario["empresa_id"], None, None)
    for i in incidencias:
        eventos.append({
            "origen": "incidencia_app",
            "persona": i.get("usuario_nombre"),
            "tipo": i.get("tipo"),
            "fecha_inicio": str(i.get("fecha_inicio")) if i.get("fecha_inicio") else None,
            "fecha_fin": str(i.get("fecha_fin")) if i.get("fecha_fin") else None,
            "estado": i.get("estado"),
            "detalle": i.get("motivo"),
            "horas": i.get("horas"),
        })

    # Vacaciones pedidas/aprobadas por ajuste de antigüedad (empleados con
    # fecha_ingreso_ajustada activa) — no salen en Microsip porque nunca lo
    # tocan, así que sin esto desaparecían por completo del calendario.
    for v in db.listar_vacaciones_ajuste_empresa(usuario["empresa_id"]):
        dias = float(v["dias"])
        fecha_inicio_str = str(v["fecha_inicio"])
        fecha_fin_str = fecha_inicio_str
        try:
            fecha_fin_str = (date.fromisoformat(fecha_inicio_str) + timedelta(days=max(int(dias) - 1, 0))).isoformat()
        except ValueError:
            pass
        eventos.append({
            "origen": "vacaciones_ajuste_app",
            "persona": v.get("usuario_nombre"),
            "tipo": "Vacaciones",
            "fecha_inicio": fecha_inicio_str,
            "fecha_fin": fecha_fin_str,
            "estado": v.get("estado"),
            "detalle": v.get("descripcion"),
            "vacacion_ajuste_id": v.get("id"),
        })

    for v in db.listar_solicitudes_vacaciones_microsip(usuario["empresa_id"], None, "pendiente"):
        eventos.append({
            "origen": "vacaciones_app_pendiente", "persona": v.get("usuario_nombre"), "tipo": "Vacaciones (por aprobar)",
            "fecha_inicio": v["fecha_inicio"], "fecha_fin": v["fecha_inicio"], "estado": "pendiente",
            "detalle": v.get("descripcion"),
        })

    eventos.sort(key=lambda e: e["fecha_inicio"] or "", reverse=True)
    return eventos


@app.get("/api/rh/empleado/{usuario_id}/ficha")
def api_ficha_empleado_rh(usuario_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Junta en un solo lugar: los datos del empleado en Microsip (si su
    numero_empleado coincide con el NUMERO de EMPLEADOS), sus periodos
    vacacionales REALES tal como Microsip los calcula (tabla
    PERIODOS_VAC — otorgados/disponibles/consumidos, no una estimación),
    y su historial de incidencias de RH ya en la app."""
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], usuario_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultado = {
        "usuario": persona,
        "microsip": None,
        "periodos_vacacionales": [],
        "saldo_vacaciones": None,
        "saldo_vacaciones_ajustado": None,
        "error_microsip": None,
        "incidencias": db.listar_incidencias_rh(usuario["empresa_id"], usuario_id, None),
    }
    if persona.get("numero_empleado"):
        config = db.obtener_config_microsip(usuario["empresa_id"])
        if not config or not config.get("microsip_host"):
            resultado["error_microsip"] = "Microsip no está configurado para esta empresa."
        else:
            try:
                empleado_ms = microsip.obtener_empleado_por_numero(config, persona["numero_empleado"])
                resultado["microsip"] = empleado_ms
                if empleado_ms:
                    periodos = microsip.obtener_periodos_vacacionales_empleado(config, empleado_ms["empleado_id"])
                    resultado["periodos_vacacionales"] = periodos
                    dias_consumidos = sum(p["dias_consumidos"] for p in periodos)
                    resultado["saldo_vacaciones"] = {
                        "dias_otorgados": sum(p["dias_otorgados"] for p in periodos),
                        "dias_consumidos": dias_consumidos,
                        "dias_disponibles": sum(p["dias_disponibles"] for p in periodos),
                    }
                    # Si RH capturó una fecha de ingreso corregida (ver
                    # guardar_ajuste_antiguedad_usuario), se recalcula el
                    # total de días correspondientes con esa fecha en vez
                    # de la que tiene Microsip — SOLO para mostrar en la
                    # app, no se toca nada en Microsip. Lo consumido suma
                    # lo real de Microsip más lo pedido desde la app.
                    resultado["saldo_vacaciones_ajustado"] = _saldo_vacaciones_ajustado(persona, dias_consumidos)
                else:
                    resultado["error_microsip"] = f"No se encontró ningún empleado en Microsip con NUMERO = {persona['numero_empleado']}."
            except Exception as e:
                resultado["error_microsip"] = f"Error consultando Microsip: {e}"
    else:
        resultado["error_microsip"] = "Este usuario no tiene número de empleado capturado — ponlo en Administrar → Usuarios para vincularlo con Microsip."
    return resultado


class AjusteAntiguedadUsuario(BaseModel):
    fecha_ingreso_ajustada: Optional[str] = None  # None/"" para quitar el ajuste
    notas: Optional[str] = None


@app.patch("/api/rh/empleado/{usuario_id}/ajuste-antiguedad")
def api_guardar_ajuste_antiguedad(usuario_id: int, payload: AjusteAntiguedadUsuario, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Corrige, SOLO dentro de tickets-ti, la fecha de ingreso que se usa
    para calcular las vacaciones de alguien que ya está en Microsip pero
    cuya fecha ahí quedó mal capturada (típico: los 3 meses de prueba no
    se contaron). No modifica nada en Microsip."""
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], usuario_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    fecha = payload.fecha_ingreso_ajustada or None
    if fecha:
        try:
            date.fromisoformat(fecha)
        except ValueError:
            raise HTTPException(status_code=400, detail="Fecha inválida")
    db.guardar_ajuste_antiguedad_usuario(usuario["empresa_id"], usuario_id, fecha, payload.notas)
    return {"ok": True}


class VacacionAjusteRH(BaseModel):
    fecha_inicio: str
    dias: float = Field(gt=0)
    descripcion: Optional[str] = None


@app.post("/api/rh/empleado/{usuario_id}/vacaciones-ajuste")
def api_registrar_vacacion_ajuste_rh(usuario_id: int, payload: VacacionAjusteRH, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Para cuando RH necesita capturar una vacación en nombre del
    empleado (ya la tomó, o no la pidió desde la app) — mismo mecanismo
    que si el empleado la hubiera pedido él mismo."""
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], usuario_id)
    if not persona or not persona.get("fecha_ingreso_ajustada"):
        raise HTTPException(status_code=400, detail="Este empleado no tiene un ajuste de antigüedad activo")
    nuevo_id = db.registrar_vacacion_ajuste_usuario(usuario_id, usuario["id"], payload.fecha_inicio, payload.dias, payload.descripcion)
    return {"id": nuevo_id}


@app.delete("/api/rh/vacaciones-ajuste/{vacacion_id}")
def api_eliminar_vacacion_ajuste_rh(vacacion_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    registro = db.obtener_vacacion_ajuste_usuario(vacacion_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], registro["usuario_id"])
    if not persona:
        raise HTTPException(status_code=404, detail="Ese registro no pertenece a tu empresa")
    db.eliminar_vacacion_ajuste_usuario(vacacion_id)
    return {"ok": True}


@app.get("/api/rh/vacaciones-ajuste")
def api_listar_vacaciones_ajuste_rh(estado: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Menú de RH: quién tiene vacaciones (de ajuste de antigüedad)
    aprobadas o pendientes de aprobar. Igual que la ficha de empleado,
    es dato sensible — restringido a 'Datos RH', ni los administradores
    sin ese permiso lo ven."""
    return db.listar_vacaciones_ajuste_empresa(usuario["empresa_id"], estado)


class ResolverVacacionAjuste(BaseModel):
    estado: str  # 'aprobada' o 'rechazada'
    respuesta_admin: Optional[str] = None


@app.post("/api/rh/vacaciones-ajuste/{vacacion_id}/resolver")
def api_resolver_vacacion_ajuste_rh(vacacion_id: int, payload: ResolverVacacionAjuste, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """RH aprueba o rechaza una vacación que el empleado pidió desde la
    app. Solo hasta aquí se descuenta de verdad (ver
    _saldo_vacaciones_ajustado) — mientras esté 'pendiente' no cuenta
    como consumida."""
    if payload.estado not in ("aprobada", "rechazada"):
        raise HTTPException(status_code=400, detail="Estado inválido — debe ser 'aprobada' o 'rechazada'")
    registro = db.obtener_vacacion_ajuste_usuario(vacacion_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    persona = db.obtener_usuario_por_id(usuario["empresa_id"], registro["usuario_id"])
    if not persona:
        raise HTTPException(status_code=404, detail="Ese registro no pertenece a tu empresa")
    ok = db.resolver_vacacion_ajuste_usuario(vacacion_id, usuario["id"], payload.estado, payload.respuesta_admin)
    if not ok:
        raise HTTPException(status_code=409, detail="Esta solicitud ya no está pendiente — alguien más ya la resolvió")
    _avisar_vacaciones_resueltas(registro["usuario_id"], payload.estado, registro.get("fecha_inicio"),
                                 float(registro.get("dias") or 0), payload.respuesta_admin)
    return {"ok": True}


# ---- Empleados en prueba (nuevo ingreso, aún no en Microsip/IMSS) ----

class NuevoEmpleadoPrueba(BaseModel):
    nombre_completo: str = Field(min_length=1)
    puesto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_ingreso: str
    notas: Optional[str] = None
    dias_prueba: Optional[int] = 90  # None = prueba indefinida, sin fecha límite (ej. nunca se dará de alta en IMSS)


class ActualizacionEmpleadoPrueba(BaseModel):
    nombre_completo: Optional[str] = None
    puesto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_ingreso: Optional[str] = None
    notas: Optional[str] = None
    dias_prueba: Optional[int] = None  # mandar null explícito = quitar la fecha límite (prueba indefinida)
    dias_otorgados_manual: Optional[float] = None  # mandar null explícito = volver al cálculo automático por LFT


class AltaMicrosipEmpleadoPrueba(BaseModel):
    numero_empleado_microsip: str = Field(min_length=1)


class NuevaVacacionEmpleadoPrueba(BaseModel):
    fecha_inicio: str
    dias: float = Field(gt=0)
    descripcion: Optional[str] = None


class ActualizacionVacacionEmpleadoPrueba(BaseModel):
    fecha_inicio: Optional[str] = None
    dias: Optional[float] = Field(default=None, gt=0)
    descripcion: Optional[str] = None


def _con_saldo_lft(empleado):
    """Agrega el saldo de vacaciones: por default calculado con el mínimo
    de la LFT acumulado desde su fecha de ingreso, pero si la empresa
    capturó un número manual de días otorgados, ese manda en su lugar.

    BUG real corregido: el rango sumaba de más un año completo de más
    desde el día 1 (range(1, anios_cumplidos+2) en vez de +1) — un
    empleado recién contratado (0 años cumplidos) salía con 12 días
    disponibles YA, en vez de 0 hasta cumplir su primer año. Con la
    fórmula vieja: 0 años→12, 1 año→26, 2 años→42... (un año de más
    siempre). Corregido: 0 años→0, 1 año→12, 2 años→26 (los correctos
    según la tabla de dias_vacaciones_lft)."""
    ingreso = date.fromisoformat(empleado["fecha_ingreso"])
    hoy = db.ahora().date()
    dias_transcurridos = (hoy - ingreso).days
    anios_cumplidos = max(0, dias_transcurridos) // 365
    dias_lft = sum(db.dias_vacaciones_lft(k) for k in range(1, anios_cumplidos + 1))
    dias_manual = empleado.get("dias_otorgados_manual")
    dias_correspondientes = float(dias_manual) if dias_manual is not None else dias_lft
    dias_tomados = sum(float(v["dias"]) for v in empleado.get("vacaciones", []))
    dias_prueba = empleado.get("dias_prueba")  # None = prueba indefinida (nunca se dará de alta en IMSS)
    empleado["saldo_vacaciones_lft"] = {
        "dias_desde_ingreso": dias_transcurridos,
        "dias_prueba": dias_prueba,
        "termina_periodo_prueba": (ingreso + timedelta(days=dias_prueba)).isoformat() if dias_prueba is not None else None,
        "prueba_indefinida": dias_prueba is None,
        "anios_de_antiguedad": anios_cumplidos,
        "dias_correspondientes_por_ley": dias_correspondientes,
        "dias_otorgados_manual": float(dias_manual) if dias_manual is not None else None,
        "dias_correspondientes_automatico_lft": dias_lft,
        "dias_tomados": dias_tomados,
        "dias_disponibles": dias_correspondientes - dias_tomados,
    }
    return empleado


@app.get("/api/rh/empleados-prueba")
def api_listar_empleados_prueba(estatus: Optional[str] = None, sin_usuario: bool = False,
                                 usuario: dict = Depends(requiere_datos_empleado_rh)):
    empleados = db.listar_empleados_prueba(usuario["empresa_id"], estatus, sin_usuario)
    for e in empleados:
        e["vacaciones"] = []  # el saldo detallado se calcula solo en el detalle, para no hacer N consultas aquí
        _con_saldo_lft(e)
    return empleados


@app.post("/api/rh/empleados-prueba")
def api_crear_empleado_prueba(payload: NuevoEmpleadoPrueba, usuario: dict = Depends(requiere_datos_empleado_rh)):
    duplicado = db.buscar_empleado_prueba_duplicado(usuario["empresa_id"], payload.nombre_completo)
    if duplicado:
        raise HTTPException(status_code=400, detail=f"Ya existe un registro de 'en prueba' con ese nombre: {duplicado['nombre_completo']} (revísalo antes de crear otro)")
    empleado_id = db.crear_empleado_prueba(
        usuario["empresa_id"], usuario["id"], payload.nombre_completo, payload.puesto,
        payload.telefono, payload.email, payload.fecha_ingreso, payload.notas, payload.dias_prueba,
    )
    return {"id": empleado_id}


class EmpleadoPruebaDesdeUsuario(BaseModel):
    usuario_id: int
    fecha_ingreso: str
    notas: Optional[str] = None
    dias_prueba: Optional[int] = 90


@app.post("/api/rh/empleados-prueba/desde-usuario")
def api_crear_empleado_prueba_desde_usuario(payload: EmpleadoPruebaDesdeUsuario, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Para cuando ya existe la cuenta de usuario del sistema (se creó
    directo, sin pasar por 'En prueba') y ahora se quiere llevar también
    su control de vacaciones aquí — crea el registro de "en prueba"
    tomando nombre/puesto/teléfono de esa cuenta, y lo liga de una vez."""
    objetivo = next((u for u in db.listar_usuarios(usuario["empresa_id"]) if u["id"] == payload.usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if db.obtener_empleado_prueba_por_usuario(usuario["empresa_id"], payload.usuario_id):
        raise HTTPException(status_code=400, detail="Ese usuario ya está ligado a otro registro de 'en prueba'")
    if objetivo.get("numero_empleado"):
        raise HTTPException(
            status_code=400,
            detail="Ese usuario ya tiene número de empleado capturado (ya está dado de alta en Microsip) — sus vacaciones reales ya se consultan en Empleados (Microsip) → Ver ficha, no hace falta llevarlas aquí también.",
        )
    duplicado = db.buscar_empleado_prueba_duplicado(usuario["empresa_id"], objetivo["nombre_completo"], objetivo.get("numero_empleado"))
    if duplicado:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un registro de 'en prueba' para esta persona: {duplicado['nombre_completo']} — probablemente se le dio de alta a mano antes. Vincúlalo desde ESE registro (botón 'Vincular con un usuario' en su ficha) en vez de crear uno nuevo.",
        )
    empleado_id = db.crear_empleado_prueba(
        usuario["empresa_id"], usuario["id"], objetivo["nombre_completo"], objetivo.get("puesto"),
        objetivo.get("telefono_whatsapp"), None, payload.fecha_ingreso, payload.notas, payload.dias_prueba,
    )
    db.vincular_usuario_empleado_prueba(empleado_id, payload.usuario_id)
    return {"id": empleado_id}


@app.post("/api/rh/empleados-prueba/{empleado_id}/vincular-usuario")
def api_vincular_usuario_empleado_prueba(empleado_id: int, payload: dict, usuario: dict = Depends(requiere_datos_empleado_rh)):
    usuario_id = payload.get("usuario_id")
    if not usuario_id:
        raise HTTPException(status_code=400, detail="Falta usuario_id")
    empleado = db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id)
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    if empleado.get("usuario_id"):
        raise HTTPException(status_code=400, detail="Este empleado ya está ligado a una cuenta de usuario")
    objetivo = next((u for u in db.listar_usuarios(usuario["empresa_id"]) if u["id"] == usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if db.obtener_empleado_prueba_por_usuario(usuario["empresa_id"], usuario_id):
        raise HTTPException(status_code=400, detail="Ese usuario ya está ligado a otro registro de 'en prueba'")
    db.vincular_usuario_empleado_prueba(empleado_id, usuario_id)
    return {"ok": True}


@app.post("/api/rh/empleados-prueba/{empleado_id}/desvincular-usuario")
def api_desvincular_usuario_empleado_prueba(empleado_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.desvincular_usuario_empleado_prueba(empleado_id)
    return {"ok": True}


@app.get("/api/rh/empleados-prueba/{empleado_id}")
def api_obtener_empleado_prueba(empleado_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    empleado = db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id)
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return _con_saldo_lft(empleado)


@app.patch("/api/rh/empleados-prueba/{empleado_id}")
def api_actualizar_empleado_prueba(empleado_id: int, payload: ActualizacionEmpleadoPrueba, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    enviados = payload.dict(exclude_unset=True)
    kwargs_extra = {}
    if "dias_prueba" in enviados:
        kwargs_extra["dias_prueba"] = payload.dias_prueba  # puede ser None = prueba indefinida
    if "dias_otorgados_manual" in enviados:
        kwargs_extra["dias_otorgados_manual"] = payload.dias_otorgados_manual  # puede ser None = volver a cálculo automático
    db.actualizar_empleado_prueba(
        empleado_id, payload.nombre_completo, payload.puesto, payload.telefono,
        payload.email, payload.fecha_ingreso, payload.notas, **kwargs_extra,
    )
    return {"ok": True}


@app.post("/api/rh/empleados-prueba/{empleado_id}/alta-microsip")
def api_marcar_alta_microsip(empleado_id: int, payload: AltaMicrosipEmpleadoPrueba, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Cuando ya se dio de alta a la persona en Microsip/IMSS (típicamente
    al terminar sus 3 meses de prueba) — a partir de aquí, Microsip lleva
    el control real de sus vacaciones, y este registro queda como
    histórico de su periodo de prueba."""
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.marcar_alta_microsip_empleado_prueba(empleado_id, payload.numero_empleado_microsip)
    return {"ok": True}


@app.post("/api/rh/empleados-prueba/{empleado_id}/baja")
def api_marcar_baja_empleado_prueba(empleado_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.marcar_baja_empleado_prueba(empleado_id)
    return {"ok": True}


@app.post("/api/rh/empleados-prueba/{empleado_id}/revertir-a-prueba")
def api_revertir_a_prueba_empleado_prueba(empleado_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Por si se marcó 'Ya está en Microsip/IMSS' o 'Baja' sin querer."""
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.revertir_a_prueba_empleado_prueba(empleado_id)
    return {"ok": True}


@app.delete("/api/rh/empleados-prueba/{empleado_id}")
def api_eliminar_empleado_prueba(empleado_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.eliminar_empleado_prueba(empleado_id)
    return {"ok": True}


@app.post("/api/rh/empleados-prueba/{empleado_id}/vacaciones")
def api_registrar_vacacion_empleado_prueba(empleado_id: int, payload: NuevaVacacionEmpleadoPrueba, usuario: dict = Depends(requiere_datos_empleado_rh)):
    empleado = db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id)
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    _con_saldo_lft(empleado)
    disponibles = empleado["saldo_vacaciones_lft"]["dias_disponibles"]
    if payload.dias > disponibles:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No tiene suficientes días disponibles (le quedan {disponibles:g}, "
                f"intentas registrar {payload.dias:g}). Si de todos modos le vas a dar el día, "
                "regístralo como incidencia de RH → 'Día libre sin goce de sueldo' en vez de vacación."
            ),
        )
    vac_id = db.registrar_vacacion_empleado_prueba(empleado_id, usuario["id"], payload.fecha_inicio, payload.dias, payload.descripcion)
    return {"id": vac_id}


@app.patch("/api/rh/empleados-prueba/{empleado_id}/vacaciones/{vacacion_id}")
def api_actualizar_vacacion_empleado_prueba(empleado_id: int, vacacion_id: int, payload: ActualizacionVacacionEmpleadoPrueba,
                                             usuario: dict = Depends(requiere_datos_empleado_rh)):
    empleado = db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id)
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    vacacion_actual = next((v for v in empleado.get("vacaciones", []) if v["id"] == vacacion_id), None)
    if not vacacion_actual:
        raise HTTPException(status_code=404, detail="Ese registro de vacaciones no pertenece a este empleado")
    enviados = payload.dict(exclude_unset=True)
    if "dias" in enviados:
        _con_saldo_lft(empleado)
        # el saldo ya incluye este mismo registro con su valor VIEJO —
        # hay que quitarlo antes de comparar, si no siempre se compara
        # contra un saldo que ya trae descontados estos mismos días.
        disponibles_sin_este = empleado["saldo_vacaciones_lft"]["dias_disponibles"] + float(vacacion_actual["dias"])
        if payload.dias > disponibles_sin_este:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No tiene suficientes días disponibles (le quedan {disponibles_sin_este:g} sin contar este registro, "
                    f"intentas dejarlo en {payload.dias:g}). Si de todos modos le vas a dar el día, "
                    "regístralo como incidencia de RH → 'Día libre sin goce de sueldo' en vez de vacación."
                ),
            )
    kwargs_extra = {}
    if "descripcion" in enviados:
        kwargs_extra["descripcion"] = payload.descripcion  # puede ser None para quitarla
    db.actualizar_vacacion_empleado_prueba(vacacion_id, payload.fecha_inicio, payload.dias, **kwargs_extra)
    return {"ok": True}


@app.delete("/api/rh/empleados-prueba/{empleado_id}/vacaciones/{vacacion_id}")
def api_eliminar_vacacion_empleado_prueba(empleado_id: int, vacacion_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.obtener_empleado_prueba(usuario["empresa_id"], empleado_id):
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    db.eliminar_vacacion_empleado_prueba(vacacion_id)
    return {"ok": True}


@app.post("/api/rh/incidencias")
def api_crear_incidencia_rh(payload: NuevaIncidenciaRH, usuario: dict = Depends(requiere_ver_rh)):
    if payload.tipo not in db.TIPOS_INCIDENCIA_RH:
        raise HTTPException(status_code=400, detail="Tipo de incidencia inválido")
    if payload.foto_base64 and len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 5MB)")
    if payload.horas is not None and payload.horas <= 0:
        raise HTTPException(status_code=400, detail="Las horas deben ser un número positivo")
    if payload.tipo == "permiso_horas" and not payload.horas:
        raise HTTPException(status_code=400, detail="En un permiso por horas indica cuántas horas o minutos.")
    if payload.tipo == "dia_libre_sin_goce" and payload.horas:
        raise HTTPException(status_code=400, detail="El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».")
    incidencia_id = db.crear_incidencia_rh(usuario["empresa_id"], usuario["id"], payload.tipo,
                                            payload.fecha_inicio, payload.fecha_fin, payload.motivo,
                                            payload.foto_base64, payload.horas)
    nueva = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id) or {}
    # Va a la encargada de su sucursal; si no tiene (o es ella misma), a RH.
    destinatarios = (db.ids_encargados_de_usuario(usuario["empresa_id"], usuario["id"])
                     if nueva.get("estado") == "pendiente_encargado"
                     else db.ids_usuarios_con_permiso(usuario["empresa_id"], "acceso_datos_empleado_rh"))
    avisos.avisar_seguro(destinatarios,
                         "🩺 Incidencia por revisar", f"{usuario.get('nombre', '')}: {payload.tipo.replace('_', ' ')} desde el {payload.fecha_inicio[:10]}.",
                         modulo="rh", ref=incidencia_id, excluir=[usuario["id"]])
    return {"id": incidencia_id}


class NuevaIncidenciaRHDirecta(BaseModel):
    usuario_id: int
    tipo: str
    fecha_inicio: str
    fecha_fin: Optional[str] = None
    motivo: Optional[str] = None
    horas: Optional[float] = Field(default=None, ge=0, le=24)


@app.post("/api/rh/incidencias/directa")
def api_crear_incidencia_rh_directa(payload: NuevaIncidenciaRHDirecta, usuario: dict = Depends(requiere_rh_o_encargado_sucursal)):
    """Para incidencias que nunca se registraron a tiempo (se le olvidó al
    empleado, se le descompuso o se le robó el celular, etc.) — RH o el
    encargado de sucursal la capturan directamente a nombre del empleado.
    Si la registra RH, queda aprobada de inmediato. Si la registra el
    encargado de sucursal, queda pendiente para que RH la revise y apruebe."""
    if payload.tipo not in db.TIPOS_INCIDENCIA_RH:
        raise HTTPException(status_code=400, detail="Tipo de incidencia inválido")
    if payload.horas is not None and payload.horas <= 0:
        raise HTTPException(status_code=400, detail="Las horas deben ser un número positivo")
    if payload.tipo == "permiso_horas" and not payload.horas:
        raise HTTPException(status_code=400, detail="En un permiso por horas indica cuántas horas o minutos.")
    if payload.tipo == "dia_libre_sin_goce" and payload.horas:
        raise HTTPException(status_code=400, detail="El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».")

    objetivo = next((u for u in db.listar_usuarios(usuario["empresa_id"]) if u["id"] == payload.usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Empleado no encontrado en tu empresa")

    es_rh = usuario.get("acceso_datos_empleado_rh", False)
    if not es_rh:
        # Es encargado de sucursal: solo puede registrar incidencias de gente de SU sucursal
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or objetivo.get("sucursal_id") != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Solo puedes registrar incidencias de gente de tu sucursal")

    nota_origen = f"[Registrada directamente por {usuario.get('nombre') or usuario.get('nombre_completo') or usuario.get('username')} — {'RH' if es_rh else 'encargado de sucursal'}, incidencia retroactiva]"
    motivo_final = f"{nota_origen} {payload.motivo}" if payload.motivo else nota_origen
    incidencia_id = db.crear_incidencia_rh_directa(
        usuario["empresa_id"], payload.usuario_id, payload.tipo, payload.fecha_inicio,
        payload.fecha_fin, motivo_final, payload.horas, usuario["id"],
    )
    if es_rh:
        db.resolver_incidencia_rh(usuario["empresa_id"], incidencia_id, usuario["id"], "aprobada",
                                   "Registrada directamente por RH — incidencia retroactiva, aprobada de inmediato.")
    return {"id": incidencia_id, "aprobada_de_inmediato": es_rh}


def requiere_encargado_sucursal(usuario: dict = Depends(requiere_empresa)) -> dict:
    if usuario["rol"] != "encargado_sucursal":
        raise HTTPException(status_code=403, detail="Esta acción es solo para el encargado de sucursal")
    return usuario


@app.get("/api/rh/incidencias/pendientes-encargado")
def api_incidencias_pendientes_encargado(usuario: dict = Depends(requiere_encargado_sucursal)):
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    if not mi_sucursal_id:
        return []
    return db.listar_incidencias_pendientes_encargado(usuario["empresa_id"], mi_sucursal_id)


class FirmaAceptacionEncargado(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.post("/api/rh/incidencias/{incidencia_id}/aceptar-encargado")
def api_aceptar_incidencia_encargado(incidencia_id: int, payload: FirmaAceptacionEncargado, usuario: dict = Depends(requiere_encargado_sucursal)):
    """La encargada de sucursal firma para ACEPTAR (aprobar) la incidencia de
    alguien de SU sucursal — esta es la decisión final, ya no pasa por RH
    para que la vuelva a aprobar (RH solo la ve informativamente después)."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    if incidencia["usuario_id"] == usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes autorizarte a ti misma: lo autoriza RH.")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
        raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if not db.aceptar_incidencia_encargado(usuario["empresa_id"], incidencia_id, usuario["id"], payload.firma_base64):
        raise HTTPException(status_code=400, detail="Esta incidencia ya no está esperando tu firma (puede que ya se haya resuelto)")
    incidencia_resuelta = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    notifications.notificar_incidencia_rh_resuelta(
        usuario["empresa_id"], {"telefono_whatsapp": incidencia_resuelta.get("usuario_telefono")}, incidencia_resuelta,
    )
    return {"ok": True}


class RechazoIncidenciaEncargado(BaseModel):
    motivo: str = Field(min_length=1)


@app.post("/api/rh/incidencias/{incidencia_id}/rechazar-encargado")
def api_rechazar_incidencia_encargado(incidencia_id: int, payload: RechazoIncidenciaEncargado, usuario: dict = Depends(requiere_encargado_sucursal)):
    """La encargada de sucursal RECHAZA la incidencia de alguien de SU
    sucursal, con el motivo — también es decisión final, no pasa por RH.
    A diferencia de aceptar, no pide firma."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    if incidencia["usuario_id"] == usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes autorizarte a ti misma: lo autoriza RH.")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
    if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
        raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
    if not db.rechazar_incidencia_encargado(usuario["empresa_id"], incidencia_id, usuario["id"], payload.motivo.strip()):
        raise HTTPException(status_code=400, detail="Esta incidencia ya no está esperando tu respuesta (puede que ya se haya resuelto)")
    incidencia_resuelta = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    notifications.notificar_incidencia_rh_resuelta(
        usuario["empresa_id"], {"telefono_whatsapp": incidencia_resuelta.get("usuario_telefono")}, incidencia_resuelta,
    )
    return {"ok": True}



@app.get("/api/rh/incidencias/{incidencia_id}")
def api_detalle_incidencia_rh(incidencia_id: int, usuario: dict = Depends(requiere_empresa)):
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    if usuario["rol"] == "admin" or incidencia["usuario_id"] == usuario["id"]:
        return incidencia
    # La encargada de RH ("Datos RH") ve la lista de todas, así que también
    # tiene que poder abrir el detalle para aprobar o rechazar.
    if _con_permisos(usuario).get("acceso_datos_empleado_rh", False):
        return incidencia
    if usuario["rol"] == "encargado_sucursal":
        # También puede ver (para revisarla antes de firmar) cualquier
        # incidencia de alguien de SU MISMA sucursal, sin importar quién sea.
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
        if mi_sucursal_id and sucursal_de_la_persona == mi_sucursal_id:
            return incidencia
    raise HTTPException(status_code=403, detail="No puedes ver la incidencia de alguien más")


@app.post("/api/rh/incidencias/{incidencia_id}/resolver")
def api_resolver_incidencia_rh(incidencia_id: int, payload: ResolverIncidenciaRH, usuario: dict = Depends(requiere_admin_rh)):
    if payload.estado not in ("aprobada", "rechazada", "pagada"):
        raise HTTPException(status_code=400, detail="Estado inválido")
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    if incidencia["estado"] not in ("pendiente", "pendiente_encargado"):
        raise HTTPException(status_code=400, detail="Esta incidencia ya fue resuelta")
    db.resolver_incidencia_rh(usuario["empresa_id"], incidencia_id, usuario["id"], payload.estado, payload.respuesta_admin)
    incidencia_resuelta = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    notifications.notificar_incidencia_rh_resuelta(
        usuario["empresa_id"], {"telefono_whatsapp": incidencia_resuelta.get("usuario_telefono")}, incidencia_resuelta,
    )
    return incidencia_resuelta


class RespuestaPropuestaDiaSinGoce(BaseModel):
    acepta: bool


@app.post("/api/rh/incidencias/{incidencia_id}/responder-propuesta")
def api_responder_propuesta_dia_sin_goce(incidencia_id: int, payload: RespuestaPropuestaDiaSinGoce, usuario: dict = Depends(requiere_empresa)):
    """El empleado responde si acepta o no convertir sus 8 horas acumuladas
    en un día sin goce de sueldo. Si acepta, pasa a que su encargada de
    sucursal lo autorice (o directo a RH si no tiene encargada asignada)."""
    if not db.responder_propuesta_dia_sin_goce(usuario["empresa_id"], incidencia_id, usuario["id"], payload.acepta):
        raise HTTPException(status_code=400, detail="Esta propuesta ya no está esperando tu respuesta")
    return {"ok": True}


@app.delete("/api/rh/incidencias/{incidencia_id}")
def api_eliminar_incidencia_rh(incidencia_id: int, usuario: dict = Depends(requiere_empresa)):
    usuario = _con_permisos(usuario)
    es_admin = usuario["rol"] == "admin" or usuario.get("acceso_datos_empleado_rh", False)
    es_encargado_de_esa_persona = False
    if usuario["rol"] == "encargado_sucursal" and not es_admin:
        incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
        if incidencia:
            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
            sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
            es_encargado_de_esa_persona = bool(mi_sucursal_id) and sucursal_de_la_persona == mi_sucursal_id
    ok = db.eliminar_incidencia_rh(usuario["empresa_id"], incidencia_id, usuario["id"], es_admin, es_encargado_de_esa_persona)
    if not ok:
        raise HTTPException(status_code=400, detail="No se pudo eliminar (no es tuya, no es de tu sucursal, o ya fue resuelta)")
    return {"ok": True}


# ==================== Capacitación obligatoria (RH) ====================

MAX_PDF_CAPACITACION_BASE64 = 20_000_000  # ~15MB de archivo real — más alto que el resto de la app a propósito: manuales de RH (vestimenta, políticas, prestaciones) suelen traer fotos/escaneos y pesar más que un simple adjunto de ticket


class MaterialCapacitacionPayload(BaseModel):
    titulo: str = Field(min_length=1)
    descripcion: Optional[str] = None
    tipo: Literal["pdf", "video"]
    archivo_base64: Optional[str] = None
    archivo_nombre: Optional[str] = None
    video_url: Optional[str] = None
    orden: int = 0
    audiencia_tipo: Literal["todos", "segmentado"] = "todos"
    departamentos: Optional[List[str]] = None
    sucursales: Optional[List[int]] = None
    usuarios: Optional[List[int]] = None
    requiere_firma: bool = True


@app.get("/api/rh/capacitacion/materiales")
def api_listar_materiales_capacitacion(usuario: dict = Depends(requiere_admin_rh)):
    """Lista de administración (incluye inactivos) — solo RH/admin."""
    return db.listar_materiales_capacitacion(usuario["empresa_id"], solo_activos=False)


@app.get("/api/rh/capacitacion/opciones-audiencia")
def api_opciones_audiencia_capacitacion(usuario: dict = Depends(requiere_admin_rh)):
    """Sucursales y empleados activos, para armar los selectores de 'a
    quién le toca' al crear/editar un material segmentado. Los
    departamentos ya vienen en META (/api/meta), no hace falta repetirlos aquí."""
    return {
        "sucursales": db.listar_sucursales_reparacion(usuario["empresa_id"], solo_activas=True),
        "usuarios": db.listar_usuarios_activos(usuario["empresa_id"]),
    }


def _validar_audiencia_payload(audiencia_tipo, departamentos, sucursales, usuarios):
    if audiencia_tipo == "segmentado" and not (departamentos or sucursales or usuarios):
        raise HTTPException(status_code=400, detail="Elige al menos un departamento, sucursal o empleado para la audiencia segmentada")


@app.post("/api/rh/capacitacion/materiales")
def api_crear_material_capacitacion(payload: MaterialCapacitacionPayload, usuario: dict = Depends(requiere_admin_rh)):
    if payload.tipo == "pdf":
        if not payload.archivo_base64:
            raise HTTPException(status_code=400, detail="Falta el archivo PDF")
        if len(payload.archivo_base64) > MAX_PDF_CAPACITACION_BASE64:
            raise HTTPException(status_code=400, detail="El PDF pesa demasiado (máximo ~15MB)")
    elif payload.tipo == "video":
        if not payload.video_url or not payload.video_url.strip().lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Falta un video (sube un archivo o pega un link de YouTube, Drive, Vimeo u OneDrive)")
    _validar_audiencia_payload(payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios)
    try:
        nuevo_id = db.crear_material_capacitacion(
            usuario["empresa_id"], payload.titulo.strip(), payload.descripcion, payload.tipo,
            payload.archivo_base64, payload.archivo_nombre, payload.video_url, payload.orden,
            usuario["nombre"], payload.audiencia_tipo, payload.departamentos, payload.sucursales, payload.usuarios,
            requiere_firma=payload.requiere_firma,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error guardando el material: {e}")
    _avisar_material_capacitacion(usuario, nuevo_id, payload.titulo.strip())
    return {"id": nuevo_id, "ok": True}


def _avisar_material_capacitacion(usuario, material_id, titulo):
    """Material nuevo → a quien le aplica (misma regla que el estatus de RH)."""
    try:
        datos = db.estatus_capacitacion_empresa(usuario["empresa_id"])
        m = next((x for x in datos["materiales"] if x["id"] == material_id), None)
        if not m:
            return
        ids = [u["id"] for u in datos["usuarios"] if (
            m["audiencia_tipo"] == "todos"
            or u["id"] in datos["usuarios_por_material"].get(m["id"], set())
            or u["sucursal_id"] in datos["sucursales_por_material"].get(m["id"], set())
            or (u["departamento"] is not None and u["departamento"] in datos["deptos_por_material"].get(m["id"], set())))]
        avisos.avisar_seguro(ids, "✍️ Documento por firmar", f"{titulo} — ábrelo y fírmalo de enterado en Bienvenido.", modulo="capacitacion",
                             ref=material_id, excluir=[usuario["id"]])
    except Exception as e:
        print(f"[avisos] capacitación: {e}")


class EdicionMaterialCapacitacion(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None
    video_url: Optional[str] = None
    archivo_base64: Optional[str] = None
    archivo_nombre: Optional[str] = None
    audiencia_tipo: Optional[Literal["todos", "segmentado"]] = None
    departamentos: Optional[List[str]] = None
    sucursales: Optional[List[int]] = None
    usuarios: Optional[List[int]] = None
    requiere_firma: Optional[bool] = None


@app.get("/api/rh/capacitacion/materiales/{material_id}/audiencia")
def api_obtener_audiencia_material(material_id: int, usuario: dict = Depends(requiere_admin_rh)):
    """Para precargar el formulario de edición con lo que ya tenía elegido."""
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    return {"audiencia_tipo": material["audiencia_tipo"], **db.obtener_audiencia_material_capacitacion(material_id)}


@app.patch("/api/rh/capacitacion/materiales/{material_id}")
def api_editar_material_capacitacion(material_id: int, payload: EdicionMaterialCapacitacion, usuario: dict = Depends(requiere_admin_rh)):
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    if payload.archivo_base64 and len(payload.archivo_base64) > MAX_PDF_CAPACITACION_BASE64:
        raise HTTPException(status_code=400, detail="El PDF pesa demasiado (máximo ~15MB)")
    datos = payload.dict(exclude_unset=True)
    campos_audiencia = {k: datos.pop(k) for k in ("audiencia_tipo", "departamentos", "sucursales", "usuarios") if k in datos}
    if campos_audiencia:
        audiencia_tipo = campos_audiencia.get("audiencia_tipo", material["audiencia_tipo"])
        _validar_audiencia_payload(
            audiencia_tipo, campos_audiencia.get("departamentos"), campos_audiencia.get("sucursales"), campos_audiencia.get("usuarios"),
        )
    if not datos and not campos_audiencia:
        return material
    try:
        if datos:
            db.actualizar_material_capacitacion(usuario["empresa_id"], material_id, datos)
        if campos_audiencia:
            db.guardar_audiencia_material_capacitacion(
                material_id, campos_audiencia.get("audiencia_tipo", material["audiencia_tipo"]),
                campos_audiencia.get("departamentos"), campos_audiencia.get("sucursales"), campos_audiencia.get("usuarios"),
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error guardando el material: {e}")
    return db.obtener_material_capacitacion(usuario["empresa_id"], material_id)


@app.delete("/api/rh/capacitacion/materiales/{material_id}")
def api_eliminar_material_capacitacion(material_id: int, usuario: dict = Depends(requiere_admin_rh)):
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    try:
        db.eliminar_material_capacitacion(usuario["empresa_id"], material_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error eliminando el material: {e}")
    return {"ok": True}


@app.get("/api/rh/capacitacion/materiales/{material_id}/archivo")
def api_obtener_archivo_material_capacitacion(material_id: int, usuario: dict = Depends(requiere_empresa)):
    """Cualquier usuario de la empresa puede pedir el PDF de un material
    (no solo RH) — es lo que abre al leerlo desde su checklist personal."""
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material or not material["activo"]:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    return {"archivo_base64": material["archivo_base64"], "archivo_nombre": material["archivo_nombre"]}


# ---- Subir un video de Capacitación directo a Cloudflare R2 ----
# Misma infraestructura que ya usan los videos de Turnos/Marketing (ver
# r2.py y /api/admin/videos/subir), pero con su propio tope de tamaño y
# su propio permiso (RH, no Marketing).
MAX_VIDEO_BYTES_CAPACITACION = 100 * 1024 * 1024  # 100 MB -- un video de RH no necesita pesar tanto como los de Turnos (500MB)


@app.post("/api/rh/capacitacion/videos/subir")
async def api_subir_video_capacitacion(request: Request, archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_rh)):
    """Sube el video elegido a Cloudflare R2 y regresa su URL pública, para
    usarla como video_url de un material de Capacitación (tipo="video").
    Reusa la misma tabla videos_subidos y el mismo cupo de almacenamiento
    por empresa que ya usan los videos de Turnos/Marketing."""
    if not r2.configurado():
        raise HTTPException(
            status_code=503,
            detail="La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.",
        )
    # Igual que en /api/admin/videos/subir: se revisa el tamaño ANTES de
    # leer el archivo completo, para rechazar de una vez un archivo
    # demasiado grande sin gastar memoria ni tiempo del servidor.
    content_length_header = request.headers.get("content-length")
    if content_length_header and content_length_header.isdigit():
        if int(content_length_header) > MAX_VIDEO_BYTES_CAPACITACION + (5 * 1024 * 1024):
            raise HTTPException(status_code=400, detail="El archivo pesa más de 100 MB -- comprime el video o sube uno más chico")
    archivo.file.seek(0, 2)
    tamano = archivo.file.tell()
    archivo.file.seek(0)
    if tamano == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if tamano > MAX_VIDEO_BYTES_CAPACITACION:
        raise HTTPException(status_code=400, detail="El archivo pesa más de 100 MB -- comprime el video o sube uno más chico")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    limite_bytes = (empresa.get("limite_almacenamiento_videos_mb") or 2048) * 1024 * 1024
    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario["empresa_id"])
    if usado_bytes + tamano > limite_bytes:
        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.",
        )
    try:
        key, url = await run_in_threadpool(r2.subir_video, usuario["empresa_id"], archivo.filename, archivo.file, archivo.content_type)
    except Exception as e:
        print(f"[videos-capacitacion] error subiendo a Cloudflare R2 (empresa {usuario['empresa_id']}, archivo {archivo.filename!r}, {tamano} bytes): {e}", file=sys.stderr)
        raise HTTPException(status_code=502, detail=f"No se pudo subir el video a Cloudflare R2: {e}")
    video = db.crear_video_subido(usuario["empresa_id"], key, archivo.filename, tamano, url, usuario["id"])
    return video


@app.get("/api/rh/capacitacion/estatus")
def api_estatus_capacitacion(usuario: dict = Depends(requiere_admin_rh)):
    """Matriz usuario x material con fecha de visto, para que RH sepa
    quién ya vio/leyó cada cosa y quién sigue pendiente. Los materiales
    segmentados que no le tocan a un usuario salen marcados 'aplica: false'
    en vez de contarse como pendientes."""
    datos = db.estatus_capacitacion_empresa(usuario["empresa_id"])
    vistos_por_usuario = {}
    for (usuario_id, material_id), visto_en in datos["vistos"].items():
        vistos_por_usuario.setdefault(usuario_id, {})[material_id] = visto_en
    firmas = datos.get("firmados", {})
    filas = []
    for u in datos["usuarios"]:
        estatus_materiales = []
        vistos_de_este = vistos_por_usuario.get(u["id"], {})
        pendientes = 0
        por_firmar = 0
        con_firma = 0
        for m in datos["materiales"]:
            aplica = (
                m["audiencia_tipo"] == "todos"
                or u["id"] in datos["usuarios_por_material"].get(m["id"], set())
                or u["sucursal_id"] in datos["sucursales_por_material"].get(m["id"], set())
                or (u["departamento"] is not None and u["departamento"] in datos["deptos_por_material"].get(m["id"], set()))
            )
            visto_en = vistos_de_este.get(m["id"]) if aplica else None
            firmado_en = firmas.get((u["id"], m["id"])) if aplica else None
            requiere = bool(m.get("requiere_firma"))
            if aplica and requiere:
                con_firma += 1
                if not firmado_en:
                    por_firmar += 1
            if aplica and (not visto_en or (requiere and not firmado_en)):
                pendientes += 1
            estatus_materiales.append({
                "material_id": m["id"], "titulo": m["titulo"], "tipo": m["tipo"],
                "aplica": aplica, "visto_en": visto_en, "firmado_en": firmado_en, "requiere_firma": requiere,
            })
        if con_firma == 0:
            estado = "sin_documentos"
        elif por_firmar == con_firma:
            estado = "sin_firma"
        elif por_firmar:
            estado = "parcial"
        else:
            estado = "completo"
        filas.append({
            "usuario_id": u["id"], "nombre": u["nombre_completo"], "rol": u["rol"],
            "pendientes": pendientes, "por_firmar": por_firmar, "con_firma": con_firma,
            "estado_firma": estado, "materiales": estatus_materiales,
        })
    return {"materiales": datos["materiales"], "usuarios": filas}


# ---- Rutas para CUALQUIER usuario (no solo RH) — su propio checklist ----

@app.get("/api/capacitacion/pendientes")
def api_capacitacion_pendientes(usuario: dict = Depends(requiere_empresa)):
    """Materiales que el usuario logueado todavía no ha marcado como
    vistos — se consulta al iniciar sesión para mostrar el aviso
    obligatorio (se puede posponer, pero vuelve a salir hasta que los
    marque como vistos)."""
    return db.materiales_pendientes_usuario(usuario["empresa_id"], usuario["id"])


@app.get("/api/capacitacion/mis-materiales")
def api_mis_materiales_capacitacion(usuario: dict = Depends(requiere_empresa)):
    """Checklist completo del usuario (vistos y pendientes), para
    consultarlo cuando quiera desde el menú, no solo al iniciar sesión."""
    return db.mis_materiales_capacitacion(usuario["empresa_id"], usuario["id"])


@app.post("/api/capacitacion/{material_id}/marcar-visto")
def api_marcar_material_visto(material_id: int, usuario: dict = Depends(requiere_empresa)):
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material or not material["activo"]:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    db.marcar_material_visto(material_id, usuario["id"])
    return {"ok": True}


# ---- Firma de enterado (Bienvenido) ----

MAX_FIRMA_ENTERADO_BASE64 = 600_000  # un PNG de firma pesa ~10-60 KB


class FirmaEnteradoPayload(BaseModel):
    firma_base64: str = Field(min_length=50)
    nombre: str = Field(min_length=3, max_length=150)
    origen: Optional[str] = None  # 'web' | 'app'


@app.get("/api/capacitacion/mi-estado")
def api_mi_estado_firmas(usuario: dict = Depends(requiere_empresa)):
    """Para pintar el módulo Bienvenido: rojo si no ha firmado nada,
    ámbar si le faltan, verde si ya firmó todo. 'obligatorio' le dice a la
    web/app si el aviso se puede cerrar o no (RH y el administrador sí lo
    pueden cerrar para poder seguir administrando; los demás, no)."""
    estado = db.estado_firmas_usuario(usuario["empresa_id"], usuario["id"])
    u = _con_permisos(usuario)
    opcional = not db.config_rh_empresa(usuario["empresa_id"])["bienvenida_obligatoria"]
    puede_posponer = u["rol"] == "admin" or bool(u.get("acceso_datos_empleado_rh")) or opcional
    estado["obligatorio"] = estado["por_firmar"] > 0 and not puede_posponer
    # Empresas con bienvenida opcional: se muestra al entrar, con "Omitir".
    estado["opcional"] = opcional
    estado["sugerir"] = opcional and estado["por_firmar"] > 0
    return estado


@app.post("/api/capacitacion/{material_id}/firmar")
def api_firmar_material(material_id: int, payload: FirmaEnteradoPayload, request: Request, usuario: dict = Depends(requiere_empresa)):
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material or not material["activo"]:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    firma = payload.firma_base64.strip()
    if not firma.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=400, detail="La firma no es válida")
    if len(firma) > MAX_FIRMA_ENTERADO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    origen = (payload.origen or "").strip().lower()[:10] or None
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else None)
    nueva = db.firmar_material_capacitacion(material_id, usuario["id"], firma, payload.nombre.strip(), origen, ip)
    return {"ok": True, "ya_estaba_firmado": not nueva, "estado": db.estado_firmas_usuario(usuario["empresa_id"], usuario["id"])}


@app.get("/api/rh/capacitacion/materiales/{material_id}/firmas")
def api_firmas_material(material_id: int, usuario: dict = Depends(requiere_admin_rh)):
    """Lista de enterados de un documento, con la imagen de cada firma,
    para imprimirla como evidencia (auditoría / expediente)."""
    material = db.obtener_material_capacitacion(usuario["empresa_id"], material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {
        "material": {"id": material["id"], "titulo": material["titulo"], "tipo": material["tipo"],
                     "descripcion": material["descripcion"], "creado_en": material["creado_en"]},
        "firmas": db.firmas_material_capacitacion(usuario["empresa_id"], material_id),
    }


@app.post("/api/rh/capacitacion/recordar-firmas")
def api_recordar_firmas(usuario: dict = Depends(requiere_admin_rh)):
    """Manda una notificación a todos los que todavía deben alguna firma."""
    datos = api_estatus_capacitacion(usuario)
    ids = [f["usuario_id"] for f in datos["usuarios"] if f["por_firmar"] > 0]
    if ids:
        avisos.avisar_seguro(ids, "✍️ Tienes documentos por firmar",
                             "Entra a Bienvenido y fírmalos de enterado.", modulo="capacitacion", ref=0)
    return {"ok": True, "avisados": len(ids)}


class EdicionIncidenciaRH(BaseModel):
    tipo: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    motivo: Optional[str] = None
    horas: Optional[float] = Field(default=None, ge=0, le=24)


@app.patch("/api/rh/incidencias/{incidencia_id}")
def api_editar_incidencia_rh(incidencia_id: int, payload: EdicionIncidenciaRH, usuario: dict = Depends(requiere_empresa)):
    """Para corregir una incidencia que se capturó mal — el administrador
    puede editar cualquiera; la encargada de sucursal, solo las de su gente
    y solo mientras sigan esperando su firma (no una vez que ya pasó a RH)."""
    incidencia = db.obtener_incidencia_rh(usuario["empresa_id"], incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    if usuario["rol"] != "admin":
        if usuario["rol"] != "encargado_sucursal":
            raise HTTPException(status_code=403, detail="No tienes permiso para editar incidencias")
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        sucursal_de_la_persona = db.obtener_sucursal_id_usuario(incidencia["usuario_id"])
        if not mi_sucursal_id or sucursal_de_la_persona != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Esta incidencia no es de tu sucursal")
        if incidencia["estado"] != "pendiente_encargado":
            raise HTTPException(status_code=400, detail="Ya no se puede editar — esta incidencia ya pasó a Recursos Humanos")
    if payload.tipo and payload.tipo not in db.TIPOS_INCIDENCIA_RH and payload.tipo != incidencia["tipo"]:
        raise HTTPException(status_code=400, detail="Tipo de incidencia inválido")
    # Permiso por horas: siempre con horas. Día sin goce: día completo (sin horas),
    # salvo la conversión automática de horas que ya debía (esa sí lleva 8 h).
    tipo_final = payload.tipo or incidencia["tipo"]
    horas_final = payload.horas if payload.horas is not None else incidencia.get("horas")
    horas = payload.horas
    if tipo_final == "permiso_horas" and not horas_final:
        raise HTTPException(status_code=400, detail="En un permiso por horas indica cuántas horas o minutos.")
    automatica = (incidencia.get("motivo") or "").startswith("Generado automáticamente")
    if tipo_final == "dia_libre_sin_goce" and not automatica and horas_final:
        if payload.horas:
            raise HTTPException(status_code=400, detail="El día sin goce de sueldo es por día completo: si es por horas, usa «Permiso por horas».")
        horas = 0  # se cambió a día sin goce: se le quitan las horas
    return db.editar_incidencia_rh(usuario["empresa_id"], incidencia_id, payload.tipo, payload.fecha_inicio,
                                    payload.fecha_fin, payload.motivo, horas)


# ---- Libro de horas (cuánto debe cada empleado, y cómo lo va pagando) ----

def formatear_horas_legible(decimal_horas: float) -> str:
    """Mismo criterio que formatearHoras() en el frontend — para que los
    mensajes de error del servidor se lean igual de claros ('30 min',
    '1 hr 30 min') en vez de un decimal crudo."""
    if decimal_horas is None:
        return "—"
    total_min = round(decimal_horas * 60)
    horas = abs(total_min) // 60
    minutos = abs(total_min) % 60
    signo = "-" if total_min < 0 else ""
    partes = []
    if horas > 0:
        partes.append(f"{horas} hr" + ("s" if horas != 1 else ""))
    if minutos > 0:
        partes.append(f"{minutos} min")
    return signo + (" ".join(partes) if partes else "0 min")


class NuevoMovimientoHorasRH(BaseModel):
    usuario_id: int
    tipo: str  # 'debe' o 'pago'
    horas: float = Field(gt=0, le=500)
    notas: Optional[str] = None


@app.get("/api/rh/horas")
def api_listar_saldos_horas_rh(usuario: dict = Depends(requiere_admin_rh)):
    """Resumen de todos los empleados con movimientos — solo administrador."""
    return db.listar_saldos_horas_todos(usuario["empresa_id"])


@app.get("/api/rh/horas/pendientes-encargado")
def api_pagos_horas_pendientes_encargado(usuario: dict = Depends(requiere_encargado_sucursal)):
    # IMPORTANTE: esta ruta específica tiene que registrarse ANTES que
    # "/api/rh/horas/{usuario_id}" — si no, FastAPI intenta interpretar
    # "pendientes-encargado" como si fuera un usuario_id numérico y truena
    # con un error 422 antes de siquiera llegar aquí.
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    if not mi_sucursal_id:
        return []
    return db.listar_pagos_horas_pendientes_encargado(usuario["empresa_id"], mi_sucursal_id)


@app.get("/api/rh/horas/{usuario_id}")
def api_consultar_horas_usuario(usuario_id: int, usuario: dict = Depends(requiere_empresa)):
    """Un empleado puede consultar SU PROPIO saldo; el administrador puede ver
    el de cualquiera; el encargado de sucursal puede ver el de su gente."""
    if usuario["rol"] != "admin" and usuario["id"] != usuario_id:
        puede_ver = False
        if usuario["rol"] == "encargado_sucursal":
            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
            sucursal_de_la_persona = db.obtener_sucursal_id_usuario(usuario_id)
            puede_ver = bool(mi_sucursal_id) and sucursal_de_la_persona == mi_sucursal_id
        if not puede_ver:
            raise HTTPException(status_code=403, detail="No puedes consultar las horas de alguien más")
    saldo = db.saldo_horas_usuario(usuario["empresa_id"], usuario_id)
    movimientos = db.listar_movimientos_horas_rh(usuario["empresa_id"], usuario_id)
    return {**saldo, "movimientos": movimientos}


@app.get("/api/rh/horas-sucursal/saldos")
def api_saldos_horas_mi_sucursal(usuario: dict = Depends(requiere_empresa)):
    """Para el encargado de sucursal: quiénes de su gente deben horas ahorita
    (y quiénes ya van al corriente) — así sabe a quién darle seguimiento."""
    if usuario["rol"] != "encargado_sucursal":
        raise HTTPException(status_code=403, detail="Esto es solo para el encargado de sucursal")
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    if not mi_sucursal_id:
        return []
    return db.listar_saldos_horas_sucursal(usuario["empresa_id"], mi_sucursal_id)


@app.post("/api/rh/horas/movimientos")
def api_registrar_movimiento_horas_rh(payload: NuevoMovimientoHorasRH, usuario: dict = Depends(requiere_admin_rh)):
    if payload.tipo not in db.TIPOS_MOVIMIENTO_HORAS_RH:
        raise HTTPException(status_code=400, detail="Tipo de movimiento inválido")
    if payload.horas <= 0:
        raise HTTPException(status_code=400, detail="Las horas deben ser un número positivo")
    objetivo = next((u for u in db.listar_usuarios(usuario["empresa_id"]) if u["id"] == payload.usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    if payload.tipo == "pago":
        saldo_actual = db.saldo_horas_usuario(usuario["empresa_id"], payload.usuario_id)["saldo"]
        if payload.horas > saldo_actual:
            raise HTTPException(
                status_code=400,
                detail=f"No puede pagar más de lo que debe (debe {formatear_horas_legible(saldo_actual)}, intentas registrar {formatear_horas_legible(payload.horas)})",
            )
    db.registrar_movimiento_horas_rh(usuario["empresa_id"], payload.usuario_id, payload.tipo, payload.horas,
                                      payload.notas, registrado_por_id=usuario["id"])
    saldo = db.saldo_horas_usuario(usuario["empresa_id"], payload.usuario_id)
    movimientos = db.listar_movimientos_horas_rh(usuario["empresa_id"], payload.usuario_id)
    return {**saldo, "movimientos": movimientos}


class SolicitudPagoHoras(BaseModel):
    fecha: str
    horas: float = Field(gt=0, le=24)
    motivo: str = Field(min_length=1, max_length=300)


@app.post("/api/rh/horas/solicitar-pago")
def api_solicitar_pago_horas(payload: SolicitudPagoHoras, usuario: dict = Depends(requiere_empresa)):
    """Cualquier persona puede registrar que 'pagó' horas (se quedó tiempo
    extra, trabajó parte de su comida, etc.) — queda pendiente de que el
    encargado de su sucursal lo autorice antes de que cuente en su saldo.
    Solo se puede registrar un pago si esa persona SÍ debe horas, y hasta
    por el monto que debe -- si no, la solicitud se queda atorada
    esperando una firma que nunca va a poder darse (la autorización ya
    bloqueaba esto del otro lado, pero es mejor avisar de una vez)."""
    saldo_actual = db.saldo_horas_usuario(usuario["empresa_id"], usuario["id"])["saldo"]
    if saldo_actual <= 0:
        raise HTTPException(status_code=400, detail="No tienes horas pendientes por pagar — estás al corriente.")
    if payload.horas > saldo_actual:
        raise HTTPException(
            status_code=400,
            detail=f"No puedes registrar más de lo que debes (debes {formatear_horas_legible(saldo_actual)}, intentas registrar {formatear_horas_legible(payload.horas)})",
        )
    movimiento_id = db.solicitar_pago_horas_empleado(usuario["empresa_id"], usuario["id"], payload.fecha,
                                                       payload.horas, payload.motivo)
    avisos.avisar_seguro(db.ids_encargados_de_usuario(usuario["empresa_id"], usuario["id"]),
                         "🕒 Pago de horas por autorizar", f"{usuario.get('nombre', '')} registró {formatear_horas_legible(payload.horas)}.",
                         modulo="rh", ref=movimiento_id, excluir=[usuario["id"]])
    return {"id": movimiento_id}


def _tipo_autorizador_rh(usuario):
    """'rh' = administrador con RH o quien tiene "Datos RH" (autoriza a todos);
    'encargado' = encargada de sucursal (autoriza a su gente); None = nadie."""
    u = _con_permisos(usuario)
    if (u["rol"] == "admin" and u.get("acceso_rh", True)) or u.get("acceso_datos_empleado_rh", False):
        return "rh"
    if u["rol"] == "encargado_sucursal":
        return "encargado"
    return None


def _puede_autorizar_de(usuario, usuario_id_persona):
    if usuario_id_persona == usuario["id"] and usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes autorizarte a ti misma: lo autoriza RH.")
    tipo = _tipo_autorizador_rh(usuario)
    if tipo == "rh":
        return
    if tipo == "encargado":
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if mi_sucursal_id and db.obtener_sucursal_id_usuario(usuario_id_persona) == mi_sucursal_id:
            return
        raise HTTPException(status_code=403, detail="Esta persona no es de tu sucursal")
    raise HTTPException(status_code=403, detail="No tienes permiso para autorizar esto")


@app.get("/api/rh/por-autorizar")
def api_rh_por_autorizar(usuario: dict = Depends(requiere_empresa)):
    """Para la app: permisos (incidencias) y pagos de horas que esta persona puede
    autorizar. Encargada: los de su sucursal. RH / administrador: todos."""
    tipo = _tipo_autorizador_rh(usuario)
    if not tipo:
        return {"rol": None, "incidencias": [], "horas": [], "saldos": []}
    yo = usuario["id"]
    if tipo == "rh":
        incidencias = [i for i in db.listar_incidencias_rh(usuario["empresa_id"])
                       if i["estado"] in ("pendiente", "pendiente_encargado") and i["usuario_id"] != yo]
        horas = [m for m in db.listar_pagos_horas_pendientes_todos(usuario["empresa_id"]) if m["usuario_id"] != yo]
        # Antes iba vacío: una encargada con "Datos RH" (o el admin) veía en la
        # app "Nadie de tu sucursal debe horas" aunque sí le debían.
        saldos = [s for s in db.listar_saldos_horas_todos(usuario["empresa_id"]) if s["usuario_id"] != yo]
    else:
        suc = db.obtener_sucursal_id_usuario(yo)
        incidencias = [i for i in (db.listar_incidencias_pendientes_encargado(usuario["empresa_id"], suc) if suc else [])
                       if i["usuario_id"] != yo]
        horas = [m for m in (db.listar_pagos_horas_pendientes_encargado(usuario["empresa_id"], suc) if suc else [])
                 if m["usuario_id"] != yo]
        saldos = db.listar_saldos_horas_sucursal(usuario["empresa_id"], suc) if suc else []
    for m in horas:
        m.pop("firma_aprobacion_base64", None)
        try:
            m["saldo_actual"] = db.saldo_horas_usuario(usuario["empresa_id"], m["usuario_id"])["saldo"]
        except Exception:
            m["saldo_actual"] = None
    return {"rol": tipo, "incidencias": incidencias, "horas": horas, "saldos": saldos}


class FirmaAprobacionHoras(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.post("/api/rh/horas/movimientos/{movimiento_id}/aprobar")
def api_aprobar_pago_horas(movimiento_id: int, payload: FirmaAprobacionHoras, usuario: dict = Depends(requiere_empresa)):
    movimiento = db.obtener_movimiento_horas_rh(usuario["empresa_id"], movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    _puede_autorizar_de(usuario, movimiento["usuario_id"])
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if movimiento["tipo"] == "pago":
        # el saldo pudo haber cambiado desde que el empleado lo solicitó
        # (por ejemplo, si mientras tanto le perdonaron un adeudo)
        saldo_actual = db.saldo_horas_usuario(usuario["empresa_id"], movimiento["usuario_id"])["saldo"]
        if movimiento["horas"] > saldo_actual:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede aprobar: esta persona ya no debe tantas horas (debe {formatear_horas_legible(saldo_actual)}, el pago es de {formatear_horas_legible(movimiento['horas'])}). Recházalo y pídele que ajuste la cantidad.",
            )
    if not db.aprobar_pago_horas(usuario["empresa_id"], movimiento_id, usuario["id"], payload.firma_base64):
        raise HTTPException(status_code=400, detail="Este pago ya no está pendiente de tu firma")
    avisos.avisar_seguro([movimiento["usuario_id"]], "✅ Tus horas fueron APROBADAS",
                         f"{formatear_horas_legible(movimiento['horas'])} ({movimiento['tipo']}).", modulo="rh", ref=movimiento_id)
    return {"ok": True}


class RechazoPagoHoras(BaseModel):
    motivo: Optional[str] = None


@app.post("/api/rh/horas/movimientos/{movimiento_id}/rechazar")
def api_rechazar_pago_horas(movimiento_id: int, payload: RechazoPagoHoras, usuario: dict = Depends(requiere_empresa)):
    movimiento = db.obtener_movimiento_horas_rh(usuario["empresa_id"], movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    _puede_autorizar_de(usuario, movimiento["usuario_id"])
    if not db.rechazar_pago_horas(usuario["empresa_id"], movimiento_id, usuario["id"], payload.motivo):
        raise HTTPException(status_code=400, detail="Este pago ya no está pendiente de tu firma")
    avisos.avisar_seguro([movimiento["usuario_id"]], "❌ Tus horas fueron RECHAZADAS",
                         f"{formatear_horas_legible(movimiento['horas'])}" + (f" · {payload.motivo}" if payload.motivo else ""),
                         modulo="rh", ref=movimiento_id)
    return {"ok": True}


@app.delete("/api/rh/horas/movimientos/{movimiento_id}")
def api_eliminar_movimiento_horas_rh(movimiento_id: int, usuario: dict = Depends(requiere_admin_rh)):
    movimiento = db.obtener_movimiento_horas_rh(usuario["empresa_id"], movimiento_id)
    if movimiento and movimiento["tipo"] == "debe" and movimiento["estado"] == "aprobado":
        # Borrar un adeudo que ya se pagó dejaría el saldo en negativo.
        saldo = db.saldo_horas_usuario(usuario["empresa_id"], movimiento["usuario_id"])
        if float(saldo["debe_total"]) - float(movimiento["horas"]) < float(saldo["pagado_total"]) - 0.001:
            raise HTTPException(status_code=400, detail=(
                "No se puede borrar: el saldo quedaría en negativo porque ya hay horas pagadas contra este adeudo. "
                "Borra primero el pago correspondiente."))
    if not db.eliminar_movimiento_horas_rh(usuario["empresa_id"], movimiento_id):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return {"ok": True}


# ---- Cursos por perfil de puesto ----

class NuevoCursoRH(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: Optional[str] = None
    puesto_objetivo: Optional[str] = None
    dias_duracion: Optional[int] = Field(default=None, ge=1, le=365)
    fecha_limite: Optional[str] = None


class ParticipanteCursoRH(BaseModel):
    usuario_id: int


class FirmaCursoRH(BaseModel):
    firma_base64: str = Field(min_length=100)
    evidencia_base64: str = Field(min_length=100)
    evidencia_nombre: Optional[str] = None


@app.get("/api/rh/cursos")
def api_listar_cursos_rh(usuario: dict = Depends(requiere_admin_rh)):
    return db.listar_cursos_rh(usuario["empresa_id"])


@app.post("/api/rh/cursos")
def api_crear_curso_rh(payload: NuevoCursoRH, usuario: dict = Depends(requiere_admin_rh)):
    curso_id = db.crear_curso_rh(usuario["empresa_id"], payload.nombre, payload.descripcion,
                                  payload.puesto_objetivo, payload.dias_duracion, payload.fecha_limite, usuario["id"])
    return db.obtener_curso_rh(usuario["empresa_id"], curso_id)


@app.get("/api/rh/cursos/{curso_id}")
def api_detalle_curso_rh(curso_id: int, usuario: dict = Depends(requiere_admin_rh)):
    curso = db.obtener_curso_rh(usuario["empresa_id"], curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    return curso


@app.delete("/api/rh/cursos/{curso_id}")
def api_eliminar_curso_rh(curso_id: int, usuario: dict = Depends(requiere_admin_rh)):
    if not db.eliminar_curso_rh(usuario["empresa_id"], curso_id):
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    return {"ok": True}


@app.post("/api/rh/cursos/{curso_id}/participantes")
def api_agregar_participante_curso(curso_id: int, payload: ParticipanteCursoRH, usuario: dict = Depends(requiere_admin_rh)):
    curso = db.obtener_curso_rh(usuario["empresa_id"], curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    objetivo = next((u for u in db.listar_usuarios(usuario["empresa_id"]) if u["id"] == payload.usuario_id), None)
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu empresa")
    db.agregar_participante_curso(curso_id, payload.usuario_id, usuario["id"])
    return db.obtener_curso_rh(usuario["empresa_id"], curso_id)


@app.delete("/api/rh/cursos/{curso_id}/participantes/{usuario_id}")
def api_quitar_participante_curso(curso_id: int, usuario_id: int, usuario: dict = Depends(requiere_admin_rh)):
    if not db.obtener_curso_rh(usuario["empresa_id"], curso_id):
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if not db.quitar_participante_curso(curso_id, usuario_id, usuario["id"]):
        raise HTTPException(status_code=400, detail="No se puede quitar: esta persona ya completó el curso (queda como historial)")
    return db.obtener_curso_rh(usuario["empresa_id"], curso_id)


@app.get("/api/rh/mis-cursos")
def api_mis_cursos_rh(usuario: dict = Depends(requiere_ver_rh)):
    return db.listar_cursos_usuario(usuario["empresa_id"], usuario["id"])


@app.post("/api/rh/cursos/{curso_id}/firmar")
def api_firmar_curso_rh(curso_id: int, payload: FirmaCursoRH, usuario: dict = Depends(requiere_ver_rh)):
    curso = db.obtener_curso_rh(usuario["empresa_id"], curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    if not db.es_participante_curso(curso_id, usuario["id"]):
        raise HTTPException(status_code=403, detail="No estás asignado a este curso")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if len(payload.evidencia_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La evidencia pesa demasiado")
    db.firmar_curso_rh(curso_id, usuario["id"], payload.firma_base64, payload.evidencia_base64, payload.evidencia_nombre)
    return {"ok": True}


@app.get("/api/rh/cursos/{curso_id}/constancia/{usuario_id}")
def api_constancia_curso_rh(curso_id: int, usuario_id: int, usuario: dict = Depends(requiere_ver_rh)):
    """El propio empleado descarga SU constancia; el administrador puede
    descargar la de cualquiera (por ejemplo, para reimprimirla)."""
    if usuario["rol"] != "admin" and usuario["id"] != usuario_id:
        raise HTTPException(status_code=403, detail="No puedes descargar la constancia de alguien más")
    curso = db.obtener_curso_rh(usuario["empresa_id"], curso_id)
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    participante = next((p for p in curso["participantes"] if p["usuario_id"] == usuario_id), None)
    if not participante or not participante.get("completado_en"):
        raise HTTPException(status_code=400, detail="Esta persona todavía no completó el curso")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_rh.generar_constancia_curso(curso, participante, empresa)
    nombre_archivo = f"constancia_{curso['nombre'][:30].replace(' ', '_')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


NOMBRES_TIPO_INCIDENCIA_RH_PDF = {
    "permiso_horas": "Permiso por horas", "dia_libre_sin_goce": "Día libre sin goce de sueldo", "enfermedad": "Falta por enfermedad",
    "lesion": "Lesión", "embarazo": "Embarazo", "accidente": "Accidente", "otro": "Otro",
}
NOMBRES_ESTADO_INCIDENCIA_RH_PDF = {"pendiente": "Pendiente", "aprobada": "Aprobada", "rechazada": "Rechazada"}


def _elementos_reporte_rh_por_empleado(empresa_id):
    """Arma las secciones del reporte de RH: una por empleado (orden alfabético),
    cada una con el detalle completo de sus incidencias — tipo, fechas, horas,
    motivo, estado y quién la resolvió."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    incidencias = db.listar_incidencias_rh(empresa_id)
    por_empleado = {}
    for i in incidencias:
        por_empleado.setdefault(i["usuario_nombre"], []).append(i)

    styles = getSampleStyleSheet()
    estilo_persona = ParagraphStyle("Persona", parent=styles["Heading3"], fontSize=12, textColor=colors.HexColor("#D8192F"),
                                     spaceBefore=14, spaceAfter=4)
    estilo_celda = ParagraphStyle("Celda", parent=styles["Normal"], fontSize=7.5, leading=9)

    elementos = [Paragraph(f"{len(incidencias)} incidencia(s) en total, de {len(por_empleado)} persona(s)", styles["Heading2"])]
    if not incidencias:
        elementos.append(Paragraph("No hay incidencias registradas.", styles["Normal"]))
        return elementos

    for nombre in sorted(por_empleado.keys()):
        lista = por_empleado[nombre]
        puesto = lista[0].get("usuario_puesto")
        elementos.append(Paragraph(f"{nombre}{f' — {puesto}' if puesto else ''} ({len(lista)})", estilo_persona))
        filas = []
        for i in lista:
            fechas = i["fecha_inicio"][:10]
            if i.get("fecha_fin") and i["fecha_fin"][:10] != fechas:
                fechas += f" al {i['fecha_fin'][:10]}"
            filas.append([
                Paragraph(NOMBRES_TIPO_INCIDENCIA_RH_PDF.get(i["tipo"], i["tipo"]), estilo_celda),
                fechas,
                f"{i['horas']} hrs" if i.get("horas") else "—",
                Paragraph((i.get("motivo") or "—")[:200], estilo_celda),
                NOMBRES_ESTADO_INCIDENCIA_RH_PDF.get(i["estado"], i["estado"]),
                i.get("resuelto_por_nombre") or "—",
            ])
        tabla = Table([["Tipo", "Fecha(s)", "Horas", "Motivo", "Estado", "Resuelto por"]] + filas,
                       colWidths=[3.3 * cm, 2.2 * cm, 1.3 * cm, 4.5 * cm, 2 * cm, 2.5 * cm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#74767A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elementos.append(tabla)
    return elementos


@app.get("/api/rh/reporte.pdf")
def api_reporte_rh_pdf(usuario: dict = Depends(requiere_admin_rh)):
    empresa = db.obtener_empresa(usuario["empresa_id"])
    elementos = _elementos_reporte_rh_por_empleado(usuario["empresa_id"])
    return _armar_pdf_simple("Reporte de Recursos Humanos", empresa["nombre"] if empresa else "", elementos, "incidencias_rh")


# ==================== REPARACIONES ====================

class NuevaSucursalReparacion(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    prefijo: str = Field(min_length=1, max_length=10)
    departamento: Optional[str] = None
    telefonos: Optional[str] = None
    notas: Optional[str] = None


@app.get("/api/reparaciones/sucursales")
def api_listar_sucursales_reparacion(usuario: dict = Depends(requiere_empresa)):
    return db.listar_sucursales_reparacion(usuario["empresa_id"])


@app.post("/api/reparaciones/sucursales")
def api_crear_sucursal_reparacion(payload: NuevaSucursalReparacion, usuario: dict = Depends(requiere_admin_completo)):
    prefijo = re.sub(r"[^A-Za-z0-9]", "", payload.prefijo).upper()
    if not prefijo:
        raise HTTPException(status_code=400, detail="El prefijo debe tener al menos una letra o número")
    if payload.departamento:
        departamentos_validos = {d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])}
        if payload.departamento not in departamentos_validos:
            raise HTTPException(status_code=400, detail="Departamento inválido")
    sucursal_id = db.crear_sucursal_reparacion(usuario["empresa_id"], payload.nombre, prefijo, payload.departamento,
                                                payload.telefonos, payload.notas)
    return {"id": sucursal_id}


class ActualizacionSucursalReparacion(BaseModel):
    nombre: Optional[str] = None
    prefijo: Optional[str] = None
    departamento: Optional[str] = None
    activo: Optional[bool] = None
    telefonos: Optional[str] = None
    notas: Optional[str] = None
    es_laboratorio: Optional[bool] = None
    es_recogida_default_estudiantes: Optional[bool] = None


@app.patch("/api/reparaciones/sucursales/{sucursal_id}")
def api_actualizar_sucursal_reparacion(sucursal_id: int, payload: ActualizacionSucursalReparacion, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    datos = payload.dict(exclude_unset=True)
    if "prefijo" in datos and datos["prefijo"]:
        prefijo = re.sub(r"[^A-Za-z0-9]", "", datos["prefijo"]).upper()
        if not prefijo:
            raise HTTPException(status_code=400, detail="El prefijo debe tener al menos una letra o número")
        datos["prefijo"] = prefijo
    if "departamento" in datos and datos["departamento"]:
        departamentos_validos = {d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])}
        if datos["departamento"] not in departamentos_validos:
            raise HTTPException(status_code=400, detail="Departamento inválido")
    return db.actualizar_sucursal_reparacion(usuario["empresa_id"], sucursal_id, **datos)


# ==================== TURNOS POR SUCURSAL ====================
# Como en un banco: un cliente toma un turno (pantalla/tablet de entrada,
# sin login), el mostrador lo llama desde su sesión normal a su ventanilla
# fija, y una pantalla de sala de espera (tampoco con login) muestra el
# número llamado + un video en loop. La pantalla y el "tomar turno" son
# páginas públicas protegidas por un código secreto por sucursal, igual
# que el link de seguimiento de entregas.

class VideosTurnosSucursal(BaseModel):
    videos: List[str] = []


@app.post("/api/reparaciones/sucursales/{sucursal_id}/turnos/codigo")
def api_obtener_codigo_turnos(sucursal_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    codigo = db.obtener_o_crear_codigo_turnos(sucursal_id)
    return {"codigo": codigo, "url_pantalla": f"/pantalla-turnos/{codigo}", "url_kiosko": f"/kiosko-turnos/{codigo}"}


@app.post("/api/reparaciones/sucursales/{sucursal_id}/turnos/codigo/regenerar")
def api_regenerar_codigo_turnos(sucursal_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    codigo = db.regenerar_codigo_turnos(sucursal_id)
    return {"codigo": codigo, "url_pantalla": f"/pantalla-turnos/{codigo}", "url_kiosko": f"/kiosko-turnos/{codigo}"}


@app.put("/api/reparaciones/sucursales/{sucursal_id}/turnos/videos")
def api_guardar_videos_turnos(sucursal_id: int, payload: VideosTurnosSucursal, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    videos = [v.strip() for v in payload.videos if v.strip()]
    db.actualizar_videos_turnos_sucursal(usuario["empresa_id"], sucursal_id, videos)
    return {"ok": True}


class VideoUrlTurnos(BaseModel):
    url: str


@app.post("/api/reparaciones/sucursales/{sucursal_id}/turnos/videos/agregar")
def api_agregar_video_turnos(sucursal_id: int, payload: VideoUrlTurnos, usuario: dict = Depends(requiere_admin_completo_o_marketing)):
    """Como el PUT de arriba pero suma UN video sin pisar los que ya
    tenía la sucursal -- pensado para que Marketing pueda ir agregando
    videos sin necesitar ver la configuración completa de Turnos."""
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Falta el link del video")
    videos = db.agregar_video_turnos_sucursal(usuario["empresa_id"], sucursal_id, url)
    return {"videos": videos}


@app.post("/api/reparaciones/sucursales/{sucursal_id}/turnos/videos/quitar")
def api_quitar_video_turnos(sucursal_id: int, payload: VideoUrlTurnos, usuario: dict = Depends(requiere_admin_completo_o_marketing)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    videos = db.quitar_video_turnos_sucursal(usuario["empresa_id"], sucursal_id, payload.url.strip())
    return {"videos": videos}


class ConfigPantallaTurnosSucursal(BaseModel):
    video_ajuste: Optional[str] = None
    logo_base64: Optional[str] = None


@app.patch("/api/reparaciones/sucursales/{sucursal_id}/turnos/config")
def api_config_pantalla_turnos(sucursal_id: int, payload: ConfigPantallaTurnosSucursal, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if payload.video_ajuste is not None and payload.video_ajuste not in ("cover", "contain"):
        raise HTTPException(status_code=400, detail="Ajuste de video inválido")
    db.actualizar_config_pantalla_turnos_sucursal(
        usuario["empresa_id"], sucursal_id,
        video_ajuste=payload.video_ajuste, logo_base64=payload.logo_base64,
    )
    return {"ok": True}


# ---- Categorías de Turnos (botones grandes del kiosko, por sucursal) ----

class NuevaCategoriaTurnos(BaseModel):
    nombre: str = Field(min_length=1)
    prefijo: str = Field(min_length=1, max_length=6)


class ActualizacionCategoriaTurnos(BaseModel):
    nombre: Optional[str] = None
    prefijo: Optional[str] = None
    activo: Optional[bool] = None
    orden: Optional[int] = None


@app.get("/api/reparaciones/sucursales/{sucursal_id}/turnos/categorias")
def api_listar_categorias_turnos(sucursal_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return db.listar_categorias_turnos(usuario["empresa_id"], sucursal_id)


@app.post("/api/reparaciones/sucursales/{sucursal_id}/turnos/categorias")
def api_crear_categoria_turnos(sucursal_id: int, payload: NuevaCategoriaTurnos, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    prefijo = re.sub(r"[^A-Za-z0-9]", "", payload.prefijo).upper()
    if not prefijo:
        raise HTTPException(status_code=400, detail="El prefijo debe tener al menos una letra o número")
    categoria_id = db.crear_categoria_turnos(usuario["empresa_id"], sucursal_id, payload.nombre.strip(), prefijo)
    return {"id": categoria_id}


@app.patch("/api/reparaciones/sucursales/{sucursal_id}/turnos/categorias/{categoria_id}")
def api_actualizar_categoria_turnos(sucursal_id: int, categoria_id: int, payload: ActualizacionCategoriaTurnos, usuario: dict = Depends(requiere_admin_completo)):
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    datos = payload.dict(exclude_unset=True)
    if "prefijo" in datos and datos["prefijo"]:
        prefijo = re.sub(r"[^A-Za-z0-9]", "", datos["prefijo"]).upper()
        if not prefijo:
            raise HTTPException(status_code=400, detail="El prefijo debe tener al menos una letra o número")
        datos["prefijo"] = prefijo
    db.actualizar_categoria_turnos(usuario["empresa_id"], sucursal_id, categoria_id, **datos)
    return {"ok": True}


@app.delete("/api/reparaciones/sucursales/{sucursal_id}/turnos/categorias/{categoria_id}")
def api_eliminar_categoria_turnos(sucursal_id: int, categoria_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_categoria_turnos(usuario["empresa_id"], sucursal_id, categoria_id):
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return {"ok": True}


# ---- Videos subidos desde la app (Cloudflare R2) ----

MAX_VIDEO_BYTES_UNA_SUBIDA = 500 * 1024 * 1024  # 500 MB por archivo -- si pesa más, mejor comprimirlo


@app.post("/api/admin/videos/subir")
async def api_subir_video(request: Request, archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_completo_o_marketing)):
    if not r2.configurado():
        raise HTTPException(
            status_code=503,
            detail="La subida de videos no está configurada todavía en el servidor (faltan las credenciales de Cloudflare R2). Avísale a tu administrador.",
        )
    # Se revisa el tamaño ANTES de leer el archivo completo -- si ya viene
    # marcado como demasiado grande en el header Content-Length, se rechaza
    # de una vez sin gastar memoria ni tiempo del servidor cargándolo
    # completo (eso era lo que causaba que un video de más de 500 MB
    # tardara un buen rato y terminara en un error 502 en vez de un
    # mensaje claro).
    content_length_header = request.headers.get("content-length")
    if content_length_header and content_length_header.isdigit():
        if int(content_length_header) > MAX_VIDEO_BYTES_UNA_SUBIDA + (5 * 1024 * 1024):
            raise HTTPException(status_code=400, detail="El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas")
    # IMPORTANTE: ya NO se carga el archivo completo a la memoria del
    # servidor con "archivo.read()". FastAPI ya guarda el archivo que se
    # está subiendo en un archivo temporal en disco -- aquí solo se mide
    # su tamaño (moviendo el cursor al final y regresándolo al inicio) y
    # más abajo se manda ese mismo archivo temporal directo a Cloudflare
    # R2, en pedazos. Antes, un video de 300-500 MB se cargaba COMPLETO
    # en memoria (en un servidor con solo 512 MB de RAM en el plan
    # gratis de Render) y eso podía tronar el proceso sin ningún mensaje
    # de error claro -- se veía como un "502" genérico del servidor,
    # incluso en archivos que sí pesaban menos de 500 MB.
    archivo.file.seek(0, 2)
    tamano = archivo.file.tell()
    archivo.file.seek(0)
    if tamano == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if tamano > MAX_VIDEO_BYTES_UNA_SUBIDA:
        raise HTTPException(status_code=400, detail="El archivo pesa más de 500 MB -- comprime el video o súbelo en partes más chicas")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    limite_bytes = (empresa.get("limite_almacenamiento_videos_mb") or 2048) * 1024 * 1024
    usado_bytes = db.sumar_almacenamiento_videos_empresa(usuario["empresa_id"])
    if usado_bytes + tamano > limite_bytes:
        disponible_mb = max(0, limite_bytes - usado_bytes) // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Ya no tienes espacio suficiente para subir videos (disponible: {disponible_mb} MB de {limite_bytes // (1024 * 1024)} MB). Borra algún video que ya no uses, o pídele a tu Superadmin que te suba el límite.",
        )
    try:
        # run_in_threadpool: la subida a R2 es una llamada bloqueante
        # (boto3), y sin esto se congelaría TODA la aplicación (para
        # todos los usuarios) mientras dura la subida de un video
        # grande. Se manda el archivo (archivo.file) en vez de los
        # bytes ya leídos, para que boto3 lo transmita en pedazos sin
        # necesitar tenerlo todo junto en memoria.
        key, url = await run_in_threadpool(r2.subir_video, usuario["empresa_id"], archivo.filename, archivo.file, archivo.content_type)
    except Exception as e:
        # Se deja un registro en los logs de Render con el error real de
        # R2 (por ejemplo credenciales, red, o el nombre del bucket) --
        # así, si vuelve a pasar, se puede ver la causa exacta en vez de
        # solo un "502" genérico.
        print(f"[videos] error subiendo a Cloudflare R2 (empresa {usuario['empresa_id']}, archivo {archivo.filename!r}, {tamano} bytes): {e}", file=sys.stderr)
        raise HTTPException(status_code=502, detail=f"No se pudo subir el video a Cloudflare R2: {e}")
    video = db.crear_video_subido(usuario["empresa_id"], key, archivo.filename, tamano, url, usuario["id"])
    return video


@app.get("/api/admin/videos")
def api_listar_videos_subidos(usuario: dict = Depends(requiere_admin_completo_o_marketing)):
    return db.listar_videos_subidos(usuario["empresa_id"])


@app.delete("/api/admin/videos/{video_id}")
def api_eliminar_video_subido(video_id: int, usuario: dict = Depends(requiere_admin_completo_o_marketing)):
    video = db.obtener_video_subido(video_id)
    if not video or video["empresa_id"] != usuario["empresa_id"]:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    try:
        r2.eliminar_video(video["r2_key"])
    except Exception:
        pass  # si ya no existe en R2 o algo falla, igual lo quitamos de la lista de la app
    db.eliminar_video_subido(video_id)
    return {"ok": True}


@app.get("/api/superadmin/almacenamiento-videos")
def api_almacenamiento_videos_superadmin(_: dict = Depends(requiere_superadmin)):
    return db.resumen_almacenamiento_videos_por_empresa()


class LimiteVideosIn(BaseModel):
    limite_mb: int


@app.put("/api/superadmin/empresas/{empresa_id}/limite-videos")
def api_actualizar_limite_videos(empresa_id: int, payload: LimiteVideosIn, _: dict = Depends(requiere_superadmin)):
    if not db.obtener_empresa(empresa_id):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if payload.limite_mb < 0:
        raise HTTPException(status_code=400, detail="El límite no puede ser negativo")
    db.actualizar_limite_videos_empresa(empresa_id, payload.limite_mb)
    return {"ok": True}


@app.get("/api/turnos/esperando")
def api_turnos_esperando(usuario: dict = Depends(requiere_acceso_turnos)):
    sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    if not sucursal_id:
        raise HTTPException(status_code=400, detail="Tu usuario no tiene una sucursal asignada -- pídele a tu administrador que te la asigne")
    return db.listar_turnos_esperando(sucursal_id)


@app.post("/api/turnos/{turno_id}/llamar")
def api_llamar_turno(turno_id: int, usuario: dict = Depends(requiere_acceso_turnos)):
    turno = db.obtener_turno(turno_id)
    if not turno or turno["empresa_id"] != usuario["empresa_id"]:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turno["estado"] != "esperando":
        raise HTTPException(status_code=400, detail="Ese turno ya fue llamado")
    ventanilla = usuario.get("ventanilla_turnos") or usuario["nombre"]
    db.llamar_turno(turno_id, ventanilla, usuario["id"])
    return db.obtener_turno(turno_id)


@app.post("/api/turnos/{turno_id}/atender")
def api_atender_turno(turno_id: int, usuario: dict = Depends(requiere_acceso_turnos)):
    turno = db.obtener_turno(turno_id)
    if not turno or turno["empresa_id"] != usuario["empresa_id"]:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    db.atender_turno(turno_id)
    return {"ok": True}


@app.post("/api/turnos/{turno_id}/cancelar")
def api_cancelar_turno(turno_id: int, usuario: dict = Depends(requiere_acceso_turnos)):
    turno = db.obtener_turno(turno_id)
    if not turno or turno["empresa_id"] != usuario["empresa_id"]:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    db.cancelar_turno(turno_id)
    return {"ok": True}


@app.get("/pantalla-turnos/{codigo}")
def pagina_pantalla_turnos(codigo: str):
    """Página PÚBLICA (sin login) -- se deja abierta en la smart TV/PC de
    la sala de espera. El HTML no necesita el código para nada, solo lo
    lee de la URL con JavaScript y llama a /api/turnos/pantalla/{codigo}."""
    return FileResponse(os.path.join(FRONTEND_DIR, "pantalla_turnos.html"))


@app.get("/kiosko-turnos/{codigo}")
def pagina_kiosko_turnos(codigo: str):
    """Página PÚBLICA (sin login) -- se deja abierta en la tablet/PC de
    entrada para que el cliente tome su turno."""
    return FileResponse(os.path.join(FRONTEND_DIR, "kiosko_turnos.html"))


@app.get("/api/turnos/pantalla/{codigo}")
def api_pantalla_turnos_publico(codigo: str):
    sucursal = db.obtener_sucursal_por_codigo_turnos(codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Esta pantalla no es válida")
    estado = db.estado_pantalla_turnos(sucursal["id"])
    videos = json.loads(sucursal["turnos_videos"]) if sucursal.get("turnos_videos") else []
    # Si la sucursal no tiene su propio logo, se usa el logo general de la
    # empresa (así una sucursal nueva ya sale con logo sin configurar nada).
    empresa = db.obtener_empresa(sucursal["empresa_id"])
    logo = sucursal.get("turnos_logo_base64") or (empresa.get("logo_base64") if empresa else None)
    return {
        "sucursal_nombre": sucursal["nombre"],
        "videos": videos,
        "video_ajuste": sucursal.get("turnos_video_ajuste") or "cover",
        "logo_base64": logo,
        **estado,
    }


@app.get("/api/turnos/kiosko/{codigo}/categorias")
def api_categorias_kiosko_turnos(codigo: str):
    """Categorías activas de esta sucursal (los botones grandes del
    kiosko) -- una lista vacía significa que la sucursal no configuró
    ninguna, y el kiosko se queda con el botón sencillo de siempre."""
    sucursal = db.obtener_sucursal_por_codigo_turnos(codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Este kiosko no es válido")
    return db.categorias_turnos_activas_por_codigo(codigo)


class TomarTurnoPayload(BaseModel):
    categoria_id: Optional[int] = None


@app.post("/api/turnos/kiosko/{codigo}/tomar")
def api_kiosko_tomar_turno(codigo: str, payload: TomarTurnoPayload):
    sucursal = db.obtener_sucursal_por_codigo_turnos(codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Este kiosko no es válido")
    turno = db.tomar_turno(sucursal["empresa_id"], sucursal["id"], categoria_id=payload.categoria_id)
    return {"numero": turno["numero"], "folio": turno["folio"], "categoria_nombre": turno.get("categoria_nombre"), "sucursal_nombre": sucursal["nombre"]}


class NuevaReparacion(BaseModel):
    sucursal_id: int
    cliente_nombre: str = Field(min_length=1, max_length=160)
    cliente_telefono: Optional[str] = None
    equipo: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    fecha_adquisicion: Optional[str] = None
    folio_adquisicion: Optional[str] = None
    garantia: bool = False
    falla_reportada: Optional[str] = None
    estado_fisico: Optional[str] = None
    accesorios_entregados: Optional[str] = None
    firma_recepcion: Optional[str] = None
    foto_estado_base64: Optional[str] = None
    foto_estado_nombre: Optional[str] = None
    # Ya no se piden al crear (13 oct 2026): el departamento sale de la
    # sucursal y la categoría es la de reparaciones. Se aceptan por compatibilidad.
    departamento: Optional[str] = None
    categoria: Optional[str] = None


class ActualizacionReparacion(BaseModel):
    folio_microsip: Optional[str] = None
    cliente_nombre: Optional[str] = None
    cliente_telefono: Optional[str] = None
    asesor_recibe: Optional[str] = None
    equipo: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    fecha_adquisicion: Optional[str] = None
    folio_adquisicion: Optional[str] = None
    garantia: Optional[bool] = None
    falla_reportada: Optional[str] = None
    estado_fisico: Optional[str] = None
    accesorios_entregados: Optional[str] = None
    diagnostico: Optional[str] = None
    autorizacion_precio: Optional[bool] = None
    autorizacion_medio: Optional[str] = None
    fecha_autorizacion: Optional[str] = None
    folio_solicitud_traspaso: Optional[str] = None
    costo_paqueteria: Optional[float] = None
    conclusion: Optional[str] = None
    recomendaciones: Optional[str] = None
    responsable_diagnostico_id: Optional[int] = None
    fecha_envio_proveedor: Optional[str] = None
    observaciones_entrega: Optional[str] = None
    firma_entrega: Optional[str] = None
    motivo_edicion: Optional[str] = None


class CambioEstadoReparacion(BaseModel):
    estado: str


class NuevoItemCosto(BaseModel):
    articulo: str = Field(min_length=1)
    cantidad: int = Field(default=1, ge=1)
    codigo: Optional[str] = None
    costo: float = Field(default=0, ge=0)


class NuevaEvidenciaReparacion(BaseModel):
    etapa: str = "ingreso"
    archivo_base64: str
    archivo_nombre: Optional[str] = None


class NuevaActualizacionReparacion(BaseModel):
    texto: str = Field(min_length=1)


@app.get("/api/reparaciones")
def api_listar_reparaciones(estado: Optional[str] = None, sucursal_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_reparaciones)):
    creado_por_id = usuario["id"] if usuario["rol"] == "usuario" else None
    # El departamento de Logística ve TODAS las reparaciones (solo consulta), sea
    # "encargado" (encargado_sucursal) o "empleado" (usuario) -- las acciones (editar,
    # firmar, entregar, eliminar) siguen bloqueadas igual que siempre, esos endpoints
    # no llaman a esta función. El rol "almacen" NO se incluye a propósito: su
    # restricción a la sucursal propia es de seguridad, no de filtro.
    ve_todo_por_logistica = usuario["rol"] in ("usuario", "encargado_sucursal", "almacen") and _es_departamento_logistica(usuario["id"])
    if ve_todo_por_logistica:
        creado_por_id = None
    if usuario["rol"] in ("almacen", "encargado_sucursal") and not ve_todo_por_logistica:
        # Un encargado de almacén o de sucursal solo ve reparaciones de SU propia
        # sucursal, sin importar qué sucursal_id le manden en la consulta (esto es
        # seguridad, no solo filtro).
        sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    return db.listar_reparaciones(usuario["empresa_id"], estado, sucursal_id, creado_por_id)


@app.post("/api/reparaciones")
def api_crear_reparacion(payload: NuevaReparacion, usuario: dict = Depends(requiere_empresa)):
    if usuario["rol"] == "encargado_sucursal":
        # La encargada da de alta en SU sucursal (es la única que ve).
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if mi_sucursal_id:
            payload.sucursal_id = mi_sucursal_id
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    departamentos = [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])]
    categorias = [c["nombre"] for c in db.listar_categorias(usuario["empresa_id"])]
    if payload.departamento not in departamentos:
        # El de la sucursal; si no tiene, el primero que haya.
        sucursal = db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_id) or {}
        payload.departamento = sucursal.get("departamento") if sucursal.get("departamento") in departamentos else \
            (departamentos[0] if departamentos else "General")
    if payload.categoria not in categorias:
        payload.categoria = next((c for c in categorias if "repara" in c.lower()), categorias[0] if categorias else "Reparación")

    # Todos los campos de la orden de servicio son obligatorios (incluida la firma
    # del cliente y la foto del estado en que se recibe el equipo). El asesor NO se
    # pide como campo — siempre es quien tiene la sesión iniciada en este momento.
    campos_obligatorios = {
        "Teléfono del cliente": payload.cliente_telefono,
        "Tipo de equipo": payload.equipo, "Marca": payload.marca, "Modelo": payload.modelo,
        "Número de serie": payload.numero_serie, "Fecha de adquisición": payload.fecha_adquisicion,
        "Folio de adquisición": payload.folio_adquisicion,
        "Falla reportada": payload.falla_reportada, "Estado físico": payload.estado_fisico,
        "Accesorios entregados": payload.accesorios_entregados,
    }
    faltantes = [nombre for nombre, valor in campos_obligatorios.items() if not (valor and valor.strip())]
    if faltantes:
        raise HTTPException(status_code=400, detail=f"Faltan campos obligatorios: {', '.join(faltantes)}")
    if not re.match(r"^\d{10}$", payload.cliente_telefono.strip()):
        raise HTTPException(status_code=400, detail="El teléfono debe ser un número de exactamente 10 dígitos")
    if not payload.firma_recepcion:
        raise HTTPException(status_code=400, detail="Falta la firma del cliente")
    if not payload.foto_estado_base64:
        raise HTTPException(status_code=400, detail="Falta la foto del estado en que se recibe el equipo")
    if payload.firma_recepcion and len(payload.firma_recepcion) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    if payload.foto_estado_base64 and len(payload.foto_estado_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 5MB)")

    reparacion = db.crear_reparacion(
        usuario["empresa_id"], payload.sucursal_id, payload.cliente_nombre, payload.cliente_telefono.strip(),
        usuario["nombre"], payload.equipo, payload.marca, payload.modelo, payload.numero_serie,
        payload.fecha_adquisicion, payload.folio_adquisicion, payload.garantia, payload.falla_reportada,
        payload.estado_fisico, payload.accesorios_entregados, payload.firma_recepcion, payload.departamento,
        payload.categoria, usuario["id"], payload.foto_estado_base64, payload.foto_estado_nombre,
    )
    db.agregar_actualizacion_reparacion(
        reparacion["id"], usuario["id"],
        f"Se creó la orden de servicio — el cliente ({payload.cliente_nombre.strip()}) firmó de recibido.",
    )
    tecnicos = db.listar_tecnicos_activos(usuario["empresa_id"])
    ticket = db.obtener_ticket(reparacion["ticket_id"])
    notifications.notificar_nuevo_ticket(usuario["empresa_id"], tecnicos, ticket)
    return reparacion


# ---- Importar reparaciones históricas desde Excel (solo admin) ----

@app.post("/api/reparaciones/importar-excel/previsualizar")
async def api_previsualizar_importacion_reparaciones(
    archivo: UploadFile = File(...), usuario: dict = Depends(requiere_admin_completo)
):
    """Sube un .xlsx, lo lee, e intenta hacer match de sucursal por fila —
    NO guarda nada todavía. El frontend revisa el resultado y llama a
    /confirmar con las correcciones (sucursal manual donde faltó, y qué
    filas sí quiere importar)."""
    contenido = await archivo.read()
    sucursales = db.listar_sucursales_reparacion(usuario["empresa_id"], solo_activas=False)
    folios_existentes = db.folios_reparacion_existentes(usuario["empresa_id"])
    try:
        filas = importar_reparaciones.previsualizar(contenido, sucursales, folios_existentes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    resumen = {
        "total": len(filas),
        "listas": sum(1 for f in filas if f["estatus"] == "lista"),
        "duplicadas": sum(1 for f in filas if f["estatus"] == "duplicada"),
        "sin_sucursal": sum(1 for f in filas if f["estatus"] == "sin_sucursal"),
    }
    return {"filas": filas, "resumen": resumen, "sucursales": sucursales}


@app.post("/api/reparaciones/importar-excel/confirmar")
def api_confirmar_importacion_reparaciones(payload: dict, usuario: dict = Depends(requiere_admin_completo)):
    """payload: {"filas": [ ...igual que en previsualizar, con sucursal_id
    ya corregido donde hacía falta... ]} — solo se insertan las filas con
    estatus 'lista' que traigan sucursal_id; el resto se ignora aquí (el
    frontend ya les debió avisar al usuario antes de llegar a este paso)."""
    filas = payload.get("filas", [])
    filas_a_importar = [f for f in filas if f.get("sucursal_id") and f.get("estatus") != "duplicada"]
    if not filas_a_importar:
        raise HTTPException(status_code=400, detail="No hay ninguna fila lista para importar (falta asignar sucursal, o todas son duplicadas)")
    try:
        importadas, omitidas = db.importar_reparaciones_lote(usuario["empresa_id"], filas_a_importar, usuario["id"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al guardar en la base de datos: {e}")
    return {"importadas": importadas, "omitidas_duplicadas": omitidas}


@app.get("/api/reparaciones/reporte.pdf")
def reporte_reparaciones_pdf(usuario: dict = Depends(requiere_staff)):
    from io import BytesIO
    from datetime import datetime as dt

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    empresa = db.obtener_empresa(usuario["empresa_id"])
    reparaciones = db.listar_reparaciones(usuario["empresa_id"])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elementos = [
        Paragraph(f"Reparaciones — {empresa['nombre'] if empresa else ''}", styles["Title"]),
        Paragraph(f"Generado el {dt.now().strftime('%d/%m/%Y %H:%M')} — {len(reparaciones)} reparación(es)", styles["Normal"]),
        Spacer(1, 16),
    ]

    datos = [["Folio", "Sucursal", "Cliente", "Equipo", "Estado", "Técnico", "Costo total"]]
    for r in reparaciones:
        datos.append([
            r["folio"], r.get("sucursal_nombre") or "—", r["cliente_nombre"], r.get("equipo") or "—",
            NOMBRES_ESTADO_REPARACION_PDF.get(r["estado"], r["estado"]),
            r.get("tecnico_nombre") or "sin asignar", f"${r.get('costo_total', 0):,.2f}",
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
    if not reparaciones:
        elementos.append(Paragraph("No hay reparaciones registradas.", styles["Normal"]))

    doc.build(elementos)
    buffer.seek(0)
    nombre_archivo = f"reparaciones_{dt.now().strftime('%Y%m%d')}.pdf"
    return Response(content=buffer.read(), media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"})


@app.get("/api/reparaciones/reporte.xlsx")
def reporte_reparaciones_xlsx(usuario: dict = Depends(requiere_staff)):
    from io import BytesIO
    from datetime import datetime as dt

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    reparaciones = db.listar_reparaciones(usuario["empresa_id"])

    wb = Workbook()
    ws = wb.active
    ws.title = "Reparaciones"
    encabezados = ["Folio", "Folio Microsip", "Sucursal", "Cliente", "Teléfono", "Equipo", "Marca", "Modelo",
                   "Estado", "Técnico", "Días transcurridos", "Costo total", "Fecha recepción", "Fecha entrega"]
    ws.append(encabezados)
    for col_idx, _ in enumerate(encabezados, start=1):
        celda = ws.cell(row=1, column=col_idx)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(start_color="D8192F", end_color="D8192F", fill_type="solid")
        celda.alignment = Alignment(horizontal="center")

    for r in reparaciones:
        ws.append([
            r["folio"], r.get("folio_microsip") or "", r.get("sucursal_nombre") or "", r["cliente_nombre"],
            r.get("cliente_telefono") or "", r.get("equipo") or "", r.get("marca") or "", r.get("modelo") or "",
            NOMBRES_ESTADO_REPARACION_PDF.get(r["estado"], r["estado"]), r.get("tecnico_nombre") or "",
            r.get("dias_transcurridos") if r.get("dias_transcurridos") is not None else "",
            r.get("costo_total", 0), (r.get("fecha_recepcion") or "")[:10], (r.get("fecha_entrega") or "")[:10],
        ])

    for col_idx, encabezado in enumerate(encabezados, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(encabezado), 14) + 4
    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    nombre_archivo = f"reparaciones_{dt.now().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buffer.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


@app.get("/api/reparaciones/{reparacion_id}")
def api_detalle_reparacion(reparacion_id: int, usuario: dict = Depends(requiere_ver_reparaciones)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    ve_todo_por_logistica = usuario["rol"] in ("usuario", "encargado_sucursal", "almacen") and _es_departamento_logistica(usuario["id"])
    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"] and not ve_todo_por_logistica:
        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
    if (usuario["rol"] in ("almacen", "encargado_sucursal")
            and reparacion["sucursal_id"] != db.obtener_sucursal_id_usuario(usuario["id"])
            and not ve_todo_por_logistica):
        raise HTTPException(status_code=403, detail="Esta reparación no es de tu sucursal")
    reparacion["estados_permitidos"] = _estados_permitidos_reparacion(usuario, reparacion)
    return reparacion


# ---- Flujo de reparaciones ----
# Taller (técnico): Nueva → En diagnóstico → (con diagnóstico guardado)
#   esperando autorización / en reparación / con proveedor / esperando
#   refacción → firma de salida = "Terminado en taller".
# Logística: Terminado en taller → Revisión por calidad → Listo para envío →
#   firma del chofer (en traslado).
# Sucursal (encargada o almacén): firma de recibido → "Entregar al cliente" →
#   entrega con firma del cliente.
ESTADOS_TALLER_REPARACION = ["en_diagnostico", "esperando_autorizacion", "en_reparacion", "con_proveedor", "esperando_refaccion"]


def _estados_permitidos_reparacion(usuario, r):
    """Estados a los que ESTE usuario puede mover la reparación ahorita."""
    estado = r.get("estado")
    if estado in ("entregado", "cancelado"):
        return []
    rol = usuario.get("rol")
    salio = bool(r.get("firma_salida_en"))
    res = []
    if rol in ("admin", "tecnico") and not (rol == "tecnico" and salio):
        if estado == "nueva":
            res.append("en_diagnostico")
        elif estado in ESTADOS_TALLER_REPARACION:
            res.append("en_diagnostico")
            if (r.get("diagnostico") or "").strip():
                res += ESTADOS_TALLER_REPARACION[1:]
        if estado not in ("en_traslado", "listo_entrega"):
            res.append("cancelado")
    if rol == "admin" or (usuario.get("id") and _es_departamento_logistica(usuario["id"])):
        if estado == "terminado_taller":
            res.append("control_calidad")
        if estado == "control_calidad":
            res.append("envio_sucursal")
    vistos = []
    for e in res:
        if e not in vistos and e != estado:
            vistos.append(e)
    return vistos


def _avisar_reparacion(ids, reparacion, titulo, texto, excluir=None):
    avisos.avisar_seguro(ids, f"{titulo} · {reparacion.get('folio', '')}", texto, modulo="reparaciones",
                         ref=reparacion.get("id"), excluir=excluir)


@app.patch("/api/reparaciones/{reparacion_id}")
def api_actualizar_reparacion(reparacion_id: int, payload: ActualizacionReparacion, usuario: dict = Depends(requiere_staff)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    enviados = payload.dict(exclude_unset=True)
    print(f"[DEBUG PATCH reparacion #{reparacion_id}] usuario={usuario.get('nombre')} (rol={usuario['rol']}) enviados={enviados}")
    motivo_edicion = (enviados.pop("motivo_edicion", None) or "").strip()
    toca_campos_tecnico = any(k in db._CAMPOS_TECNICO_REPARACION for k in enviados)
    # El bloqueo se activa específicamente cuando se guarda TEXTO real de
    # diagnóstico — no con cualquier otro campo de la misma pestaña (autorización,
    # folio de traspaso, costos) — para no bloquearlo antes de que el técnico
    # siquiera alcance a escribir el diagnóstico la primera vez.
    se_guarda_diagnostico_real = bool(enviados.get("diagnostico"))

    # No se puede empezar a diagnosticar mientras la reparación siga en "nueva"
    # (recién creada, todavía sin confirmar que se recibió) — aplica para
    # cualquier rol, incluido el administrador, es un orden de flujo, no un permiso.
    if toca_campos_tecnico and reparacion["estado"] == "nueva":
        raise HTTPException(status_code=400, detail="Primero cambia el estado a 'Recibido en diagnóstico' antes de llenar el diagnóstico")

    try:
        if usuario["rol"] == "tecnico":
            if reparacion.get("firma_salida_en"):
                raise HTTPException(status_code=403, detail="Esta reparación ya salió del taller — ya no puedes modificarla")

            # El técnico no puede tocar lo que la sucursal capturó al recibir el equipo
            # (cliente, equipo, falla reportada, accesorios, etc.) — solo su propio trabajo.
            campos_no_permitidos = [k for k in enviados if k in db._CAMPOS_RECEPCION_REPARACION]
            if campos_no_permitidos:
                raise HTTPException(status_code=403, detail="No puedes editar los datos de recepción capturados por la sucursal")

            # Una vez que el técnico guarda el diagnóstico, queda bloqueado — para
            # volver a tocar CUALQUIER campo de esta sección tiene que dar un motivo,
            # y eso se anota en la bitácora. Cambiar el ESTADO nunca pasa por aquí
            # (usa un endpoint aparte), así que el técnico siempre puede seguir
            # moviendo el estado sin ninguna restricción.
            if toca_campos_tecnico and reparacion.get("diagnostico_bloqueado"):
                if not motivo_edicion:
                    raise HTTPException(status_code=400, detail="El diagnóstico ya está guardado — indica el motivo del cambio para poder editarlo")
                db.agregar_actualizacion_reparacion(
                    reparacion_id, usuario["id"],
                    f"Editó el diagnóstico (ya estaba guardado). Motivo: {motivo_edicion}",
                )

            db.actualizar_reparacion(usuario["empresa_id"], reparacion_id, campos_permitidos=db._CAMPOS_TECNICO_REPARACION, **enviados)
            _rep_tras_guardar = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
            print(f"[DEBUG PATCH reparacion #{reparacion_id}] tras guardar -> diagnostico={_rep_tras_guardar.get('diagnostico')!r} "
                  f"autorizacion_precio={_rep_tras_guardar.get('autorizacion_precio')!r} autorizacion_medio={_rep_tras_guardar.get('autorizacion_medio')!r}")

            if se_guarda_diagnostico_real and not reparacion.get("diagnostico_bloqueado"):
                db.actualizar_reparacion(usuario["empresa_id"], reparacion_id,
                                          campos_permitidos=["diagnostico_bloqueado"], diagnostico_bloqueado=True)
                db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"],
                                                     "Guardó el diagnóstico — queda bloqueado para futuras ediciones.")
        else:
            # El administrador siempre puede editar sin necesidad de motivo, pero si el
            # diagnóstico ya estaba bloqueado, igual queda anotado en la bitácora.
            if toca_campos_tecnico and reparacion.get("diagnostico_bloqueado"):
                nota = "El administrador editó el diagnóstico (ya estaba guardado por el técnico)."
                if motivo_edicion:
                    nota += f" Motivo: {motivo_edicion}"
                db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], nota)
            db.actualizar_reparacion(usuario["empresa_id"], reparacion_id, **enviados)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al guardar: {e}")

    nueva = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not (reparacion.get("diagnostico") or "").strip() and (nueva.get("diagnostico") or "").strip():
        # Primer diagnóstico: la sucursal ya se lo puede mandar al cliente.
        ids = db.ids_personal_reparacion_sucursal(usuario["empresa_id"], reparacion["sucursal_id"]) + [reparacion.get("creado_por_id")]
        _avisar_reparacion(ids, reparacion, "🩺 Diagnóstico listo",
                           f"{reparacion.get('cliente_nombre', '')}: ya puedes enviarle el diagnóstico desde la app.", excluir=[usuario["id"]])
    return nueva


@app.delete("/api/reparaciones/{reparacion_id}")
def api_eliminar_reparacion(reparacion_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_reparacion(usuario["empresa_id"], reparacion_id):
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    return {"ok": True}


@app.patch("/api/reparaciones/{reparacion_id}/estado")
def api_cambiar_estado_reparacion(reparacion_id: int, payload: CambioEstadoReparacion, usuario: dict = Depends(requiere_ver_reparaciones)):
    if payload.estado not in db.ESTADOS_REPARACION:
        raise HTTPException(status_code=400, detail="Estado inválido")
    if payload.estado in ("terminado_taller", "en_traslado", "listo_entrega", "entregado"):
        raise HTTPException(status_code=400, detail="Este paso lleva firma: usa 'Terminar en taller (firma)', 'Entrega al chofer', 'Recibir en sucursal' o 'Entregar al cliente'")
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    permitidos = _estados_permitidos_reparacion(usuario, reparacion)
    if payload.estado not in permitidos:
        if (payload.estado in ESTADOS_TALLER_REPARACION and reparacion["estado"] in ESTADOS_TALLER_REPARACION
                and usuario["rol"] in ("admin", "tecnico") and not (reparacion.get("diagnostico") or "").strip()):
            raise HTTPException(status_code=400, detail="Primero guarda el diagnóstico: sin diagnóstico no se puede avanzar.")
        if reparacion["estado"] == "nueva":
            raise HTTPException(status_code=403, detail="Solo el técnico del taller cambia una reparación nueva a 'En diagnóstico'.")
        if payload.estado in ("control_calidad", "envio_sucursal"):
            raise HTTPException(status_code=403, detail="Este paso lo hace Logística (revisión por calidad y listo para envío).")
        raise HTTPException(status_code=403, detail="No puedes mover esta reparación a ese estado en este momento.")
    db.cambiar_estado_reparacion(usuario["empresa_id"], reparacion_id, payload.estado)
    nombre_estado = NOMBRES_ESTADO_REPARACION_BITACORA.get(payload.estado, payload.estado)
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")
    if payload.estado == "envio_sucursal":
        _avisar_reparacion(db.ids_usuarios_logistica(usuario["empresa_id"]), reparacion, "🚚 Listo para envío",
                           "Pasó la revisión de calidad: falta entregarla al chofer con su firma.", excluir=[usuario["id"]])
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


class FirmaSalidaReparacion(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.post("/api/reparaciones/{reparacion_id}/firma-salida")
def api_firmar_salida_reparacion(reparacion_id: int, payload: FirmaSalidaReparacion, usuario: dict = Depends(requiere_staff)):
    """El técnico (o admin) firma que el equipo sale del taller rumbo a la sucursal.
    A partir de este momento, el técnico ya no puede modificar NADA de la reparación
    — ni el diagnóstico, ni el estado — solo el administrador."""
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if reparacion["estado"] not in ESTADOS_TALLER_REPARACION:
        raise HTTPException(status_code=400, detail="Esta reparación no está en el taller (todavía no se recibe, o ya pasó este paso)")
    if not (reparacion.get("diagnostico") or "").strip():
        raise HTTPException(status_code=400, detail="Primero guarda el diagnóstico")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.firmar_salida_reparacion(usuario["empresa_id"], reparacion_id, usuario["id"], payload.firma_base64)
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], "Terminó en taller y firmó la salida: pasa a revisión de Logística.")
    _avisar_reparacion(db.ids_usuarios_logistica(usuario["empresa_id"]), reparacion, "🔧 Terminada en taller",
                       f"{reparacion.get('cliente_nombre', '')}: revísala y pásala a revisión por calidad.", excluir=[usuario["id"]])
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


class FirmaChoferReparacion(BaseModel):
    chofer_nombre: str = Field(min_length=1, max_length=160)
    firma_base64: str = Field(min_length=100)


@app.post("/api/reparaciones/{reparacion_id}/firma-chofer")
def api_firmar_chofer_reparacion(reparacion_id: int, payload: FirmaChoferReparacion, usuario: dict = Depends(requiere_ver_reparaciones)):
    """El chofer que se lleva el equipo firma de recibido — avanza el estado a
    'en_traslado'. Solo aplica justo después de la firma de salida. Lo puede
    hacer el administrador, o cualquier persona del departamento de Logística
    (sin importar su rol dentro del departamento) -- el resto queda bloqueado,
    incluido el técnico (que además ya queda bloqueado en cuanto firma la
    salida, justo lo que hace posible este paso)."""
    if usuario["rol"] != "admin" and not _es_departamento_logistica(usuario["id"]):
        raise HTTPException(status_code=403, detail="Solo el administrador o alguien del departamento de Logística puede registrar la entrega al chofer")
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if reparacion["estado"] != "envio_sucursal":
        raise HTTPException(status_code=400, detail="Todavía falta la firma de salida, o el chofer ya firmó")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.firmar_chofer_reparacion(usuario["empresa_id"], reparacion_id, usuario["id"], payload.chofer_nombre.strip(), payload.firma_base64)
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"],
                                         f"Se entregó al chofer {payload.chofer_nombre.strip()} para su traslado a la sucursal.")
    _avisar_reparacion(db.ids_personal_reparacion_sucursal(usuario["empresa_id"], reparacion["sucursal_id"]), reparacion,
                       "📦 Reparación en camino", f"Va con el chofer {payload.chofer_nombre.strip()}: recíbela con tu firma cuando llegue.",
                       excluir=[usuario["id"]])
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


class FirmaIngresoReparacion(BaseModel):
    firma_base64: str = Field(min_length=100)


@app.post("/api/reparaciones/{reparacion_id}/firma-ingreso")
def api_firmar_ingreso_reparacion(reparacion_id: int, payload: FirmaIngresoReparacion, usuario: dict = Depends(requiere_ver_reparaciones)):
    """Recepción en la sucursal — el encargado de almacén o de sucursal de
    esa misma sucursal (identificada por el folio) siempre puede hacerlo.
    El administrador TAMBIÉN puede recibir cualquier reparación, sin
    importar la sucursal — por si hace falta cubrir cuando no hay alguien
    de almacén/sucursal disponible."""
    if usuario["rol"] not in ("almacen", "encargado_sucursal", "admin"):
        raise HTTPException(status_code=403, detail="Solo un encargado de almacén, de sucursal, o un administrador puede firmar la recepción")
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] in ("almacen", "encargado_sucursal"):
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or reparacion["sucursal_id"] != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Esta reparación no es de tu sucursal — no puedes recibirla")
    if reparacion["estado"] != "en_traslado":
        raise HTTPException(status_code=400, detail="Esta reparación todavía no va en camino (falta la firma del chofer), o ya fue recibida")
    if len(payload.firma_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.firmar_ingreso_reparacion(usuario["empresa_id"], reparacion_id, usuario["id"], payload.firma_base64)
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], "Confirmó la recepción del equipo en la sucursal: listo para entregar al cliente.")
    _avisar_reparacion([reparacion.get("creado_por_id")], reparacion, "✅ Lista para entregar",
                       f"Ya está en la sucursal: avísale a {reparacion.get('cliente_nombre', 'tu cliente')}.", excluir=[usuario["id"]])
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


class EntregaReparacion(BaseModel):
    observaciones_entrega: Optional[str] = None
    firma_entrega: Optional[str] = None


@app.post("/api/reparaciones/{reparacion_id}/entregar")
def api_entregar_reparacion(reparacion_id: int, payload: EntregaReparacion, usuario: dict = Depends(requiere_ver_reparaciones)):
    """Registra la entrega al cliente y cierra la reparación. El staff puede usarlo
    siempre; un empleado solo puede entregar SU PROPIA reparación, y solo cuando ya
    está en 'Listo para entrega' (el almacén/sucursal ya la recibió). El encargado
    de almacén o de sucursal SOLO hace esto (recibir + entregar) — nada más del
    proceso — y únicamente para reparaciones de su propia sucursal."""
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    # Solo se entrega cuando la sucursal ya la recibió ("Entregar al cliente");
    # el administrador puede cerrarla en cualquier momento.
    if usuario["rol"] != "admin" and reparacion["estado"] != "listo_entrega":
        raise HTTPException(status_code=400, detail="Todavía no se puede entregar: falta que la sucursal la reciba con su firma.")
    if usuario["rol"] not in ("admin", "almacen", "encargado_sucursal", "usuario"):
        raise HTTPException(status_code=403, detail="La entrega al cliente la hace la sucursal")
    if usuario["rol"] == "usuario":
        if reparacion["creado_por_id"] != usuario["id"]:
            raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
        if reparacion["estado"] != "listo_entrega":
            raise HTTPException(status_code=400, detail="Esta reparación todavía no está lista para entregar (falta que el almacén la reciba)")
    if usuario["rol"] in ("almacen", "encargado_sucursal"):
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or reparacion["sucursal_id"] != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Esta reparación no es de tu sucursal — no puedes entregarla")
        if reparacion["estado"] != "listo_entrega":
            raise HTTPException(status_code=400, detail="Esta reparación todavía no está lista para entregar")
    if payload.firma_entrega and len(payload.firma_entrega) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")

    campos = {}
    if payload.observaciones_entrega is not None:
        campos["observaciones_entrega"] = payload.observaciones_entrega
    if payload.firma_entrega is not None:
        campos["firma_entrega"] = payload.firma_entrega
    if campos:
        db.actualizar_reparacion(usuario["empresa_id"], reparacion_id, **campos)
    db.cambiar_estado_reparacion(usuario["empresa_id"], reparacion_id, "entregado")
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], "Registró la entrega del equipo al cliente.")
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


@app.post("/api/reparaciones/{reparacion_id}/items-costo")
def api_agregar_item_costo(reparacion_id: int, payload: NuevoItemCosto, usuario: dict = Depends(requiere_staff)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] == "tecnico" and reparacion.get("firma_salida_en"):
        raise HTTPException(status_code=403, detail="Esta reparación ya salió del taller — ya no puedes modificarla")
    db.agregar_item_costo(reparacion_id, payload.articulo, payload.cantidad, payload.codigo, payload.costo)
    db.agregar_actualizacion_reparacion(
        reparacion_id, usuario["id"],
        f"Agregó al costo: {payload.articulo} — {payload.cantidad} x ${payload.costo:,.2f} = ${payload.cantidad * payload.costo:,.2f}",
    )
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


@app.delete("/api/reparaciones/items-costo/{item_id}")
def api_eliminar_item_costo(item_id: int, usuario: dict = Depends(requiere_staff)):
    reparacion_id = db.obtener_reparacion_id_de_item_costo(item_id)
    if reparacion_id:
        reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
        if reparacion and usuario["rol"] == "tecnico" and reparacion.get("firma_salida_en"):
            raise HTTPException(status_code=403, detail="Esta reparación ya salió del taller — ya no puedes modificarla")
    db.eliminar_item_costo(item_id)
    if reparacion_id:
        db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], "Quitó un ítem del costo de la reparación.")
    return {"ok": True}


@app.post("/api/reparaciones/{reparacion_id}/evidencias")
def api_agregar_evidencia_reparacion(reparacion_id: int, payload: NuevaEvidenciaReparacion, usuario: dict = Depends(requiere_staff)):
    if not db.obtener_reparacion(usuario["empresa_id"], reparacion_id):
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    db.agregar_evidencia_reparacion(reparacion_id, payload.etapa, payload.archivo_base64, payload.archivo_nombre, usuario["id"])
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


@app.post("/api/reparaciones/{reparacion_id}/actualizaciones")
def api_agregar_actualizacion_reparacion(reparacion_id: int, payload: NuevaActualizacionReparacion, usuario: dict = Depends(requiere_staff)):
    if not db.obtener_reparacion(usuario["empresa_id"], reparacion_id):
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    db.agregar_actualizacion_reparacion(reparacion_id, usuario["id"], payload.texto)
    return db.obtener_reparacion(usuario["empresa_id"], reparacion_id)


@app.get("/api/reparaciones/{reparacion_id}/orden-servicio.pdf")
def api_pdf_orden_servicio(reparacion_id: int, usuario: dict = Depends(requiere_empresa)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_reparaciones.generar_orden_servicio(reparacion, empresa)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename=orden_servicio_{reparacion['folio']}.pdf"})


class WhatsappReparacionIn(BaseModel):
    tipo: Literal["orden", "diagnostico"] = "orden"


@app.post("/api/reparaciones/{reparacion_id}/whatsapp")
def api_reparacion_whatsapp(reparacion_id: int, payload: WhatsappReparacionIn, usuario: dict = Depends(requiere_ver_reparaciones)):
    """Le manda al cliente, por WhatsApp Business (Meta), la orden de servicio
    o el diagnóstico con el PDF adjunto (igual que las cotizaciones)."""
    empresa_id = usuario["empresa_id"]
    reparacion = db.obtener_reparacion(empresa_id, reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"] and not _es_departamento_logistica(usuario["id"]):
        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
    if not whatsapp_meta.configurado():
        raise HTTPException(status_code=400, detail="WhatsApp Business (Meta) todavía no está configurado en el servidor.")
    telefono = (reparacion.get("cliente_telefono") or "").strip()
    if not whatsapp_meta.normalizar_telefono(telefono):
        raise HTTPException(status_code=400, detail="La reparación no tiene un teléfono válido del cliente (10 dígitos).")
    if payload.tipo == "diagnostico" and not (reparacion.get("diagnostico") or "").strip():
        raise HTTPException(status_code=400, detail="Todavía no hay diagnóstico.")
    empresa = db.obtener_empresa(empresa_id) or {}
    equipo = " ".join(x for x in [reparacion.get("equipo"), reparacion.get("marca"), reparacion.get("modelo")] if x) or "equipo"
    if payload.tipo == "diagnostico":
        pdf_bytes = pdfs_reparaciones.generar_diagnostico(reparacion, empresa)
        nombre = f"Diagnostico_{reparacion['folio']}.pdf"
        params = [reparacion["cliente_nombre"], equipo, reparacion["folio"], f"${float(reparacion.get('costo_total') or 0):,.2f}"]
    else:
        pdf_bytes = pdfs_reparaciones.generar_orden_servicio(reparacion, empresa)
        nombre = f"Orden_servicio_{reparacion['folio']}.pdf"
        params = [reparacion["cliente_nombre"], equipo, reparacion["folio"]]
    try:
        wamid = whatsapp_meta.enviar_documento_reparacion(payload.tipo, telefono, params, pdf_bytes, nombre)
    except whatsapp_meta.ErrorWhatsApp as e:
        db.registrar_envio_whatsapp(empresa_id, f"reparacion_{payload.tipo}", telefono, "error", usuario["id"], error=str(e))
        return {"ok": False, "error": str(e)}
    db.registrar_envio_whatsapp(empresa_id, f"reparacion_{payload.tipo}", telefono, "sent", usuario["id"], wamid=wamid)
    db.agregar_actualizacion_reparacion(
        reparacion_id, usuario["id"],
        f"Se le mandó al cliente por WhatsApp {'el diagnóstico' if payload.tipo == 'diagnostico' else 'la orden de servicio'} (PDF).",
    )
    return {"ok": True, "error": None}


@app.get("/api/reparaciones/{reparacion_id}/diagnostico.pdf")
def api_pdf_diagnostico(reparacion_id: int, usuario: dict = Depends(requiere_empresa)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_reparaciones.generar_diagnostico(reparacion, empresa)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename=diagnostico_{reparacion['folio']}.pdf"})


@app.get("/api/reparaciones/{reparacion_id}/conformidad-entrega.pdf")
def api_pdf_conformidad_entrega(reparacion_id: int, usuario: dict = Depends(requiere_empresa)):
    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)
    if not reparacion:
        raise HTTPException(status_code=404, detail="Reparación no encontrada")
    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_reparaciones.generar_conformidad_entrega(reparacion, empresa)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename=conformidad_entrega_{reparacion['folio']}.pdf"})


NOMBRES_ESTADO_REPARACION_PDF = {
    "en_diagnostico": "En diagnóstico", "esperando_autorizacion": "Esperando autorización",
    "en_reparacion": "En reparación", "con_proveedor": "Con proveedor", "esperando_refaccion": "Esperando refacción",
    "terminado_taller": "Terminado en taller", "control_calidad": "Revisión por calidad",
    "envio_sucursal": "Listo para envío", "en_traslado": "En traslado", "listo_entrega": "Listo para entregar al cliente",
    "entregado": "Entregado", "cancelado": "Cancelado",
}


# =============================================================================
# LABORATORIO (fabricación de coronas, implantes, etc. para doctores y
# estudiantes) — comparte las sucursales de Reparaciones; el doctor/
# estudiante no tiene usuario en el sistema, se captura como texto libre.
# =============================================================================

class PiezaLaboratorioIn(BaseModel):
    diente: str = Field(min_length=1, max_length=10)
    tipo_trabajo: str
    material: Optional[str] = None
    color: Optional[str] = None
    notas: Optional[str] = None
    costo: float = Field(default=0, ge=0)


class NuevoTrabajoLaboratorio(BaseModel):
    sucursal_id: Optional[int] = None  # solo se usa si quien crea no tiene sucursal propia (típicamente admin)
    solicitante_tipo: str  # 'estudiante' | 'doctor'
    solicitante_nombre: str = Field(min_length=1, max_length=160)
    universidad_clinica: str = Field(min_length=1, max_length=160)
    telefono: str = Field(min_length=10, max_length=20)
    paciente_nombre: Optional[str] = None
    fecha_compromiso: Optional[str] = None
    notas: Optional[str] = None
    folio_escaneo: str = Field(min_length=1, max_length=80)
    requiere_factura: bool
    piezas: List[PiezaLaboratorioIn] = Field(default_factory=list)


class FirmaRecepcionLaboratorio(BaseModel):
    firma_recepcion: str = Field(min_length=100)


class MetodoPagoIn(BaseModel):
    metodo: str
    monto: float = Field(gt=0)


class RegistroPagoLaboratorio(BaseModel):
    metodos: List[MetodoPagoIn] = Field(default_factory=list)
    comprobante_base64: str = Field(min_length=100)


class ActualizacionTrabajoLaboratorio(BaseModel):
    solicitante_tipo: Optional[str] = None
    solicitante_nombre: Optional[str] = None
    universidad_clinica: Optional[str] = None
    telefono: Optional[str] = None
    paciente_nombre: Optional[str] = None
    fecha_compromiso: Optional[str] = None
    notas: Optional[str] = None
    folio_escaneo: Optional[str] = None
    requiere_factura: Optional[bool] = None


class CambioEstadoLaboratorio(BaseModel):
    estado: str
    # Solo al pasar a "envio_sucursal": a qué sucursal va, o "escuela".
    destino_tipo: Optional[Literal["sucursal", "escuela"]] = None
    destino_sucursal_id: Optional[int] = None


class DestinoLaboratorioIn(BaseModel):
    destino_tipo: Literal["sucursal", "escuela"]
    destino_sucursal_id: Optional[int] = None
    # Una vez elegido, el destino queda anclado: cambiarlo pide el motivo.
    motivo: str = Field(min_length=3, max_length=500)


class EntregaMatriculaLaboratorio(BaseModel):
    matricula: str = Field(min_length=2, max_length=60)


class NuevaEvidenciaLaboratorio(BaseModel):
    archivo_base64: str
    archivo_nombre: Optional[str] = None
    descripcion: Optional[str] = None


# SubirDisenoLaboratorio (el modelo Pydantic que recibía el archivo como
# base64 dentro del JSON) ya no se usa -- el endpoint de abajo ahora recibe
# el archivo como multipart/form-data (UploadFile) directo, sin pasar por
# JSON, que es justo lo que evita los 502 con archivos grandes en Render.


class RechazarDisenoLaboratorio(BaseModel):
    motivo: Optional[str] = None


class NuevaActualizacionLaboratorio(BaseModel):
    texto: str = Field(min_length=1)


class EntregaLaboratorio(BaseModel):
    observaciones_entrega: Optional[str] = None
    firma_entrega: str = Field(min_length=100)


# ---- Portal de estudiantes (Fase 1): registro con matrícula + su propio
# alta de trabajo, sin folio de escaneo manual todavía se queda igual que
# hoy -- eso se reemplaza por la búsqueda real en DS Core en la Fase 2. ----
class RegistroEstudianteLaboratorio(BaseModel):
    matricula: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6)
    nombre_completo: str = Field(min_length=1, max_length=160)
    telefono: str = Field(min_length=10, max_length=20)
    email: str = Field(min_length=5, max_length=160)


_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _email_valido(email):
    return bool(email and _RE_EMAIL.match(email.strip()))


class DatosFacturaLabIn(BaseModel):
    """Datos fiscales que captura el estudiante al pedir factura (a mano, con
    el QR de su Constancia de Situación Fiscal o subiendo la constancia)."""
    rfc: Optional[str] = None
    razon_social: Optional[str] = None
    regimen_fiscal: Optional[str] = None
    uso_cfdi: Optional[str] = None
    codigo_postal: Optional[str] = None
    domicilio_fiscal: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    correo: Optional[str] = None
    constancia_base64: Optional[str] = None
    constancia_nombre: Optional[str] = None


class NuevoTrabajoLaboratorioEstudiante(BaseModel):
    paciente_nombre: Optional[str] = None
    fecha_compromiso: Optional[str] = None
    notas: Optional[str] = None
    folio_escaneo: Optional[str] = Field(default=None, max_length=80)
    requiere_factura: bool
    piezas: List[PiezaLaboratorioIn] = Field(default_factory=list)
    sucursal_recogida_id: Optional[int] = None
    datos_factura: Optional[DatosFacturaLabIn] = None


# ---- DS Core (Dentsply Sirona) -- el estudiante importa su pedido con
# el código que le da el maestro, en vez de escribirlo a mano. ----
class ConfigDSCore(BaseModel):
    base_host: str = Field(min_length=1, max_length=200)
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class ImportarPedidoDSCore(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)
    requiere_factura: bool
    sucursal_recogida_id: Optional[int] = None
    # Si un diente del pedido viene con un material que no está dentro del
    # acuerdo con el laboratorio (zirconia/disilicato), el primer intento se
    # rechaza pidiendo llamar al laboratorio o corregir el material. Este
    # mapeo (diente -> material corregido) se manda en un segundo intento
    # para forzar la corrección elegida en vez del material que traía DS Core.
    materiales_override: Optional[dict[str, str]] = None
    datos_factura: Optional[DatosFacturaLabIn] = None


# ---- Pago por transferencia reportado por el estudiante (Fase 2, sin
# Mercado Pago) -- la IA solo sugiere, el laboratorio siempre confirma. ----
class ReportarPagoTransferenciaEstudiante(BaseModel):
    comprobante_base64: str = Field(min_length=100)


class ConfirmarPagoReportado(BaseModel):
    metodos: List[MetodoPagoIn] = Field(default_factory=list)


class RechazarPagoReportado(BaseModel):
    motivo: str = Field(min_length=1)


# Estados que el laboratorio mueve libremente una vez que el trabajo ya
# está ahí — 'recibido' (alta en sucursal), 'en_laboratorio' (llegada al
# laboratorio), 'aprobar_diseno' (subir el STL y esperar a que el
# estudiante lo apruebe) y 'listo_entrega' (recepción de vuelta en
# sucursal) tienen cada uno su propio endpoint dedicado, con su
# firma/validación — por eso NO están en esta lista. 'maquila' tampoco:
# solo se llega ahí cuando el estudiante aprueba el diseño (endpoint
# /disenos/{id}/aprobar) -- nunca se manda a fresar sin ese visto bueno.
ESTADOS_LABORATORIO_LIBRES = ["modelado", "maquillado", "control_calidad", "envio_sucursal", "cancelado"]
# Estos son los que vienen DESPUÉS de "Aprobar diseño" en el flujo normal --
# si el trabajo todavía no tiene un diseño aprobado (o marcado como que no
# lo necesita, ver omite_aprobacion_diseno), "Mover estado" no debe dejar
# saltar directo a ninguno de estos desde modelado/aprobar_diseno.
ESTADOS_LABORATORIO_REQUIEREN_DISENO_APROBADO = {"maquillado", "control_calidad", "envio_sucursal"}
# Los estados avanzan UNO POR UNO, en este orden. De "modelado" no se sale
# con "Mover estado": se sube el diseño (→ aprobar_diseno → el estudiante lo
# aprueba → maquila) o se marca "no necesita diseño" (→ maquila).
SIGUIENTE_ESTADO_LABORATORIO = {
    "en_laboratorio": "modelado",
    "maquila": "maquillado",
    "maquillado": "control_calidad",
    "control_calidad": "envio_sucursal",
}


def _validar_destino_laboratorio(empresa_id, destino_tipo, destino_sucursal_id, trabajo):
    """Regresa (tipo, sucursal_id) ya validados. Sin destino → la sucursal de origen."""
    if destino_tipo == "escuela":
        return "escuela", None
    suc_id = destino_sucursal_id or trabajo.get("sucursal_id")
    permitidas = {s["id"] for s in db.sucursales_destino_laboratorio(empresa_id)}
    if not permitidas:  # si no se reconoce ninguna, cualquier sucursal activa
        permitidas = {s["id"] for s in db.listar_sucursales_reparacion(empresa_id, solo_activas=True)}
    if suc_id not in permitidas:
        raise HTTPException(status_code=400, detail="Elige uno de los destinos: Sucursal Dentigo, 33, 13, Corporativo o la escuela")
    return "sucursal", suc_id


def _avisar_envio_laboratorio(empresa_id, trabajo_id, actor_id):
    """Al mandar el trabajo (o cambiarle el destino): a las encargadas de la
    sucursal destino les llega el aviso; al estudiante, a dónde va."""
    try:
        t = db.obtener_trabajo_laboratorio(empresa_id, trabajo_id)
        if not t:
            return
        quien = t.get("solicitante_nombre") or ""
        if t.get("destino_tipo") != "escuela" and t.get("entrega_sucursal_id"):
            avisos.avisar_seguro(db.ids_encargados_sucursal(empresa_id, t["entrega_sucursal_id"]),
                                 f"📦 Trabajo de laboratorio en camino · {t.get('folio', '')}",
                                 f"{quien} — va a tu sucursal. Confirma cuando llegue y entrégalo con su firma.",
                                 modulo="laboratorio", ref=trabajo_id, excluir=[actor_id])
    except Exception as e:
        print(f"[avisos] envío laboratorio {trabajo_id}: {e}")


def _auto_entrada_laboratorio(usuario, trabajo_id):
    """Pago confirmado y cubierto + firma → el trabajo entra solo al laboratorio."""
    t = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if (t and t["estado"] == "recibido" and t.get("firma_recepcion")
            and round(t["costo_total"] - t["pago_monto_total"], 2) <= 0):
        db.marcar_entrada_laboratorio(usuario["empresa_id"], trabajo_id, usuario["id"])
        db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "Pago confirmado — el trabajo entró al laboratorio automáticamente.")


@app.get("/api/laboratorio")
def api_listar_laboratorio(estado: Optional[str] = None, sucursal_id: Optional[int] = None, ligero: bool = False,
                           usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    if usuario["rol"] != "admin":
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        es_laboratorio = bool(sucursal_lab) and mi_sucursal_id == sucursal_lab["id"]
        if not es_laboratorio:
            # Cualquier sucursal normal (sea cual sea su rol) solo ve lo suyo.
            sucursal_id = mi_sucursal_id
        # Si es la sucursal de Laboratorio, no se restringe — necesita ver los
        # trabajos de TODAS las sucursales para poder recibirlos y fabricarlos.
    lista = db.listar_trabajos_laboratorio(usuario["empresa_id"], estado, sucursal_id)
    if ligero:
        # Para la app: sin firmas ni comprobantes (pesan); el detalle los trae.
        for t in lista:
            t["tiene_firma_recepcion"] = bool(t.get("firma_recepcion"))
            for k in ("firma_recepcion", "firma_entrega", "pago_comprobante_base64", "datos_factura_json"):
                t.pop(k, None)
            for r in t.get("pagos_reportados") or []:
                r.pop("comprobante_base64", None)
    return lista


@app.get("/api/laboratorio/solicitantes/buscar")
def api_buscar_solicitante_laboratorio(telefono: str, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Si ese teléfono ya pidió un trabajo antes, regresa sus datos para
    cargarlos solos en el formulario de alta."""
    solicitante = db.buscar_solicitante_laboratorio(usuario["empresa_id"], telefono.strip())
    if not solicitante:
        return None
    return {
        "nombre": solicitante["nombre"],
        "solicitante_tipo": solicitante["solicitante_tipo"],
        "universidad_clinica": solicitante["universidad_clinica"],
    }


@app.post("/api/laboratorio")
def api_crear_trabajo_laboratorio(payload: NuevoTrabajoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    # La sucursal se ancla SOLA a la de quien está dando de alta — nadie
    # elige de un dropdown, para que no se equivoquen de sucursal. Solo
    # quien no tiene sucursal propia asignada (típicamente el admin) debe
    # mandarla explícita.
    mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
    sucursal_id = mi_sucursal_id or payload.sucursal_id
    if not sucursal_id:
        raise HTTPException(status_code=400, detail="No tienes una sucursal asignada — pide que te asignen una, o indica la sucursal")
    if not db.obtener_sucursal_reparacion(usuario["empresa_id"], sucursal_id):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if payload.solicitante_tipo not in db.TIPOS_SOLICITANTE_LABORATORIO:
        raise HTTPException(status_code=400, detail="Tipo de solicitante inválido")
    for pieza in payload.piezas:
        if pieza.tipo_trabajo not in db.TIPOS_TRABAJO_LABORATORIO:
            raise HTTPException(status_code=400, detail=f"Tipo de trabajo inválido para el diente {pieza.diente}")
    trabajo = db.crear_trabajo_laboratorio(
        usuario["empresa_id"], sucursal_id, payload.solicitante_tipo, payload.solicitante_nombre.strip(),
        payload.universidad_clinica.strip(), payload.telefono.strip(), payload.paciente_nombre, payload.fecha_compromiso,
        payload.notas, None, usuario["id"],
        payload.folio_escaneo.strip(), payload.requiere_factura, [p.model_dump() for p in payload.piezas],
    )
    db.agregar_actualizacion_laboratorio(
        trabajo["id"], usuario["id"],
        f"Se recibió el trabajo — solicitado por {payload.solicitante_nombre.strip()}. Falta registrar el pago.",
    )
    return trabajo


@app.post("/api/laboratorio/{trabajo_id}/registrar-pago")
def api_registrar_pago_laboratorio(trabajo_id: int, payload: RegistroPagoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """El primer pago es obligatorio ANTES de poder tocar el odontograma —
    se puede dividir entre varios métodos de pago, cada uno con su monto, y
    siempre pide la foto del comprobante. Si después de armar el
    odontograma el pago se queda corto, este mismo endpoint sirve para
    abonar lo que falte (ver 'faltante' en /api/laboratorio/{id})."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] != "recibido":
        raise HTTPException(status_code=400, detail="Este trabajo ya no está en recepción")
    if trabajo.get("pago_registrado_en"):
        faltante = round(trabajo["costo_total"] - trabajo["pago_monto_total"], 2)
        if faltante <= 0:
            raise HTTPException(status_code=400, detail="Este trabajo ya está cubierto — no hace falta abonar más")
    if usuario["rol"] != "admin":
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or trabajo["sucursal_id"] != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Este trabajo no es de tu sucursal")
    if not payload.metodos:
        raise HTTPException(status_code=400, detail="Indica al menos un método de pago")
    for m in payload.metodos:
        if m.metodo not in db.TIPOS_METODO_PAGO_LABORATORIO:
            raise HTTPException(status_code=400, detail="Método de pago inválido")
    if len(payload.comprobante_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto del comprobante pesa demasiado (máximo 5MB)")
    db.registrar_pago_laboratorio(
        usuario["empresa_id"], trabajo_id, usuario["id"],
        [m.model_dump() for m in payload.metodos], payload.comprobante_base64,
    )
    monto_total = round(sum(m.monto for m in payload.metodos), 2)
    metodos_texto = ", ".join(f"{NOMBRES_METODO_PAGO_LABORATORIO.get(m.metodo, m.metodo)} ${m.monto:,.2f}" for m in payload.metodos)
    verbo = "Se abonó" if trabajo.get("pago_registrado_en") else "Se registró el pago"
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"], f"{verbo} por ${monto_total:,.2f} — {metodos_texto}.",
    )
    _auto_entrada_laboratorio(usuario, trabajo_id)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/firmar-recepcion")
def api_firmar_recepcion_laboratorio(trabajo_id: int, payload: FirmaRecepcionLaboratorio, usuario: dict = Depends(requiere_ver_laboratorio)):
    """Firma del doctor/estudiante AL FINAL — después de llenar sus datos y de
    marcar los dientes en el odontograma, confirma que todo está correcto.
    Un estudiante SÍ puede firmar la SUYA desde su propio portal (Fase 2) --
    ya no tiene que ir a la sucursal para esta parte -- pero nunca la de otro."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "recibido":
        raise HTTPException(status_code=400, detail="Este trabajo ya no está en recepción")
    if not trabajo.get("pago_registrado_en"):
        raise HTTPException(status_code=400, detail="Todavía falta registrar el pago")
    faltante = round(trabajo["costo_total"] - trabajo["pago_monto_total"], 2)
    if faltante > 0:
        raise HTTPException(status_code=400, detail=f"Falta cubrir ${faltante:,.2f} del pago antes de continuar")
    if usuario["rol"] not in ("admin", "estudiante"):
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or trabajo["sucursal_id"] != mi_sucursal_id:
            raise HTTPException(status_code=403, detail="Este trabajo no es de tu sucursal")
    if len(payload.firma_recepcion) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.firmar_recepcion_laboratorio(usuario["empresa_id"], trabajo_id, payload.firma_recepcion)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"{trabajo['solicitante_nombre']} firmó de recepción.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.patch("/api/laboratorio/{trabajo_id}")
def api_actualizar_trabajo_laboratorio(trabajo_id: int, payload: ActualizacionTrabajoLaboratorio, usuario: dict = Depends(requiere_admin)):
    """Corregir los datos del solicitante que se capturaron al recibir el
    trabajo — quedan bloqueados para todos MENOS el administrador, porque
    ya se firmaron (igual que los datos de recepción en Reparaciones)."""
    if not db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if payload.solicitante_tipo and payload.solicitante_tipo not in db.TIPOS_SOLICITANTE_LABORATORIO:
        raise HTTPException(status_code=400, detail="Tipo de solicitante inválido")
    db.actualizar_trabajo_laboratorio(usuario["empresa_id"], trabajo_id, **payload.model_dump(exclude_unset=True))
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.delete("/api/laboratorio/{trabajo_id}")
def api_eliminar_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_admin)):
    if not db.eliminar_trabajo_laboratorio(usuario["empresa_id"], trabajo_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return {"ok": True}


@app.post("/api/laboratorio/{trabajo_id}/entrar-laboratorio")
def api_entrar_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """El laboratorio confirma que el trabajo ya llegó físicamente — solo
    quien esté asignado a la sucursal marcada como 'es_laboratorio' (o el
    administrador) puede hacerlo."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] != "recibido":
        raise HTTPException(status_code=400, detail="Este trabajo ya no está esperando entrar al laboratorio")
    if not trabajo.get("firma_recepcion"):
        raise HTTPException(status_code=400, detail="Todavía falta la firma de recepción del doctor/estudiante")
    if usuario["rol"] != "admin":
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
            raise HTTPException(status_code=403, detail="Solo el laboratorio puede confirmar que un trabajo ya llegó")
    db.marcar_entrada_laboratorio(usuario["empresa_id"], trabajo_id, usuario["id"])
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "El trabajo entró al laboratorio.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.patch("/api/laboratorio/{trabajo_id}/estado")
def api_cambiar_estado_laboratorio(trabajo_id: int, payload: CambioEstadoLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Mover el trabajo entre los pasos internos de fabricación — desde que
    entró al laboratorio hasta que se manda de vuelta a la sucursal. Una
    vez que se manda ('envio_sucursal') ya nadie lo puede tocar aquí, hasta
    que la sucursal lo reciba (endpoint /recibir-sucursal, no este)."""
    if payload.estado not in ESTADOS_LABORATORIO_LIBRES:
        raise HTTPException(status_code=400, detail="Ese estado no se cambia desde aquí")
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    destino = None
    if payload.estado != "cancelado":
        if trabajo["estado"] not in ("en_laboratorio", "maquila", *ESTADOS_LABORATORIO_LIBRES) or trabajo["estado"] == "envio_sucursal":
            raise HTTPException(status_code=400, detail="Este trabajo todavía no ha entrado al laboratorio, o ya se envió de vuelta a la sucursal")
        if trabajo["estado"] in ("modelado", "aprobar_diseno") and payload.estado != trabajo["estado"]:
            raise HTTPException(
                status_code=400,
                detail="Para avanzar, sube el diseño (STL) para que el estudiante lo apruebe, o usa \"Este trabajo no necesita diseño\".",
            )
        siguiente = SIGUIENTE_ESTADO_LABORATORIO.get(trabajo["estado"])
        if trabajo["estado"] not in ("modelado", "aprobar_diseno") and payload.estado != siguiente:
            nombre_sig = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(siguiente, siguiente or "—")
            raise HTTPException(status_code=400, detail=f"Los estados van uno por uno: el siguiente paso es \"{nombre_sig}\".")
        if payload.estado == "envio_sucursal":
            destino = _validar_destino_laboratorio(usuario["empresa_id"], payload.destino_tipo, payload.destino_sucursal_id, trabajo)
        if (payload.estado in ESTADOS_LABORATORIO_REQUIEREN_DISENO_APROBADO
                and trabajo["estado"] in ("modelado", "aprobar_diseno")
                and not trabajo.get("omite_aprobacion_diseno")):
            raise HTTPException(
                status_code=400,
                detail="Este trabajo todavía no tiene un diseño aprobado -- sube el diseño (STL) para que el estudiante lo apruebe, o usa \"Este trabajo no necesita diseño\" si no hace falta.",
            )
        if usuario["rol"] != "admin":
            sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
            if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
                raise HTTPException(status_code=403, detail="Solo el laboratorio puede mover estos estados")
    if payload.estado == "cancelado" and not _es_usuario_laboratorio(usuario):
        raise HTTPException(status_code=403, detail="Solo el laboratorio puede cambiar el estatus")
    if destino:
        db.fijar_destino_laboratorio(usuario["empresa_id"], trabajo_id, *destino)
    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, payload.estado)
    nombre_estado = NOMBRES_ESTADO_LABORATORIO_BITACORA.get(payload.estado, payload.estado)
    actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if destino:
        nombre_estado = f"Envío a {actualizado.get('destino_texto')}"
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Cambió el estado a: {nombre_estado}")
    if destino:
        threading.Thread(target=_avisar_envio_laboratorio, args=(usuario["empresa_id"], trabajo_id, usuario["id"]), daemon=True).start()
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.patch("/api/laboratorio/{trabajo_id}/destino")
def api_cambiar_destino_laboratorio(trabajo_id: int, payload: DestinoLaboratorioIn, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Ya en "Envío a…", el laboratorio lo puede cambiar a otra sucursal o a
    la escuela (mientras no lo hayan recibido)."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if not _es_usuario_laboratorio(usuario):
        raise HTTPException(status_code=403, detail="Solo el laboratorio puede cambiar a dónde se envía")
    if trabajo["estado"] != "envio_sucursal":
        raise HTTPException(status_code=400, detail="Solo se cambia el destino mientras el trabajo va en camino")
    destino = _validar_destino_laboratorio(usuario["empresa_id"], payload.destino_tipo, payload.destino_sucursal_id, trabajo)
    if destino == (trabajo.get("destino_tipo") or "sucursal", trabajo.get("destino_sucursal_id") if trabajo.get("destino_tipo") != "escuela" else None):
        raise HTTPException(status_code=400, detail="Ya va a ese destino")
    antes = trabajo.get("destino_texto")
    db.fijar_destino_laboratorio(usuario["empresa_id"], trabajo_id, *destino)
    actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"],
                                         f"Cambió el envío de {antes} a {actualizado.get('destino_texto')}. Motivo: {payload.motivo.strip()}")
    threading.Thread(target=_avisar_envio_laboratorio, args=(usuario["empresa_id"], trabajo_id, usuario["id"]), daemon=True).start()
    return actualizado


@app.post("/api/laboratorio/{trabajo_id}/omitir-diseno")
def api_omitir_diseno_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Para trabajos que no van a llevar un diseño que el estudiante tenga
    que aprobar (ej. una reparación simple que de todos modos entró al
    flujo de laboratorio) -- marca el trabajo para que 'Mover estado' lo
    deje avanzar más allá de modelado sin pasar por Aprobar diseño."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):
        raise HTTPException(status_code=400, detail="Este trabajo ya no está en un punto donde aplique esto")
    if usuario["rol"] != "admin":
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
            raise HTTPException(status_code=403, detail="Solo el laboratorio puede hacer esto")
    db.marcar_omite_diseno_laboratorio(usuario["empresa_id"], trabajo_id)
    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "maquila")
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        "Marcó que este trabajo no necesita diseño ni aprobación del estudiante -- pasa a maquila.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/subir-diseno")
async def api_subir_diseno_laboratorio(
    trabajo_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    archivo_2: Optional[UploadFile] = File(None),
    usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio),
):
    """El laboratorio sube el archivo de diseño (STL) para que el estudiante
    lo revise antes de mandarlo a fresar -- la primera vez mueve el trabajo
    de 'modelado' a 'aprobar_diseno'; si el estudiante ya lo había
    rechazado, esto sube la corrección y se queda en 'aprobar_diseno'.

    Se recibe como multipart/form-data (UploadFile), no como JSON con el
    archivo metido en base64: ese base64 pesa ~33% más que el archivo real
    y obligaba a leer/parsear el body completo como un JSON gigante antes
    de poder hacer nada -- con archivos de decenas de MB eso es lo que
    estaba tronando con 502 en Render (pasaba igual ya con el plan subido,
    porque no era falta de RAM/CPU sino el tiempo/tamaño de ese único
    paso). Aquí el archivo llega como bytes directos y se codifica a
    base64 ya del lado del servidor, en threadpool, solo para guardarlo
    igual que siempre en la base de datos."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] not in ("modelado", "aprobar_diseno"):
        raise HTTPException(status_code=400, detail="Este trabajo no está en modelado ni esperando aprobación de diseño")
    if usuario["rol"] != "admin":
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not sucursal_lab or mi_sucursal_id != sucursal_lab["id"]:
            raise HTTPException(status_code=403, detail="Solo el laboratorio puede subir el diseño")
    # Igual que en /api/rh/capacitacion/videos/subir: revisar el tamaño
    # ANTES de leer el archivo completo, para rechazar de una vez un
    # archivo demasiado grande sin gastar memoria ni tiempo del servidor.
    content_length_header = request.headers.get("content-length")
    if content_length_header and content_length_header.isdigit():
        if int(content_length_header) > (MAX_DISENO_ARCHIVO_BYTES * 2) + (5 * 1024 * 1024):
            raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")

    async def _leer_y_codificar(subida: UploadFile, etiqueta: str) -> str:
        contenido = await subida.read()
        if len(contenido) > MAX_DISENO_ARCHIVO_BYTES:
            raise HTTPException(status_code=400, detail=f"{etiqueta} pesa demasiado (máximo ~90MB) -- comprímelo o expórtalo con menos resolución")
        # base64.b64encode de un archivo grande es trabajo de CPU, no de
        # red/disco -- se manda al threadpool para no trabar el event loop
        # (y a las demás peticiones en curso) mientras se hace.
        return await run_in_threadpool(lambda: base64.b64encode(contenido).decode("ascii"))

    archivo_base64 = await _leer_y_codificar(archivo, "El archivo")
    archivo_base64_2 = await _leer_y_codificar(archivo_2, "El segundo archivo") if archivo_2 is not None else None

    estado_anterior = trabajo["estado"]
    db.subir_diseno_laboratorio(
        trabajo_id, archivo_base64, archivo.filename, usuario["id"],
        archivo_base64_2=archivo_base64_2, archivo_nombre_2=(archivo_2.filename if archivo_2 is not None else None),
    )
    if estado_anterior == "modelado":
        db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "aprobar_diseno")
    nombres_diseno = archivo.filename or "archivo"
    if archivo_2 is not None and archivo_2.filename:
        nombres_diseno += f" + {archivo_2.filename}"
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"Subió el diseño ({nombres_diseno}) para que el estudiante lo apruebe.",
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/archivo")
def api_obtener_archivo_diseno_laboratorio(trabajo_id: int, diseno_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    """El detalle del trabajo (GET /api/laboratorio/{id}) ya NO trae el
    contenido del STL de cada diseño, solo metadatos (ver nota en
    db.obtener_trabajo_laboratorio) -- este endpoint trae el contenido
    real de UN diseño puntual, para pedirlo solo cuando de verdad hace
    falta mostrar el visor 3D o descargar el archivo. Mismo permiso que
    ver el detalle del trabajo: personal de laboratorio, o el propio
    estudiante dueño del trabajo."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    diseno = db.obtener_diseno_laboratorio(diseno_id)
    if not diseno or diseno["trabajo_id"] != trabajo_id:
        raise HTTPException(status_code=404, detail="Diseño no encontrado")
    return {
        "archivo_base64": diseno["archivo_base64"],
        "archivo_nombre": diseno["archivo_nombre"],
        "archivo_base64_2": diseno.get("archivo_base64_2"),
        "archivo_nombre_2": diseno.get("archivo_nombre_2"),
    }


@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/aprobar")
def api_aprobar_diseno_laboratorio(trabajo_id: int, diseno_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    """El estudiante (o el laboratorio/admin, por si necesita ayudarlo)
    aprueba el diseño que se subió -- con eso el trabajo pasa a maquila.
    Nunca se manda a fresar sin este visto bueno."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "aprobar_diseno":
        raise HTTPException(status_code=400, detail="Este trabajo no está esperando aprobación de diseño")
    diseno = db.obtener_diseno_laboratorio(diseno_id)
    if not diseno or diseno["trabajo_id"] != trabajo_id:
        raise HTTPException(status_code=404, detail="Diseño no encontrado")
    if diseno["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Este diseño ya fue revisado")
    db.aprobar_diseno_laboratorio(diseno_id, usuario["id"])
    db.cambiar_estado_laboratorio(usuario["empresa_id"], trabajo_id, "maquila")
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"{trabajo['solicitante_nombre']} aprobó el diseño -- pasa a maquila.")
    if usuario.get("rol") == "estudiante":
        avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario["empresa_id"]), f"✅ Diseño aprobado · {trabajo.get('folio', '')}",
                             f"{trabajo['solicitante_nombre']} aprobó el diseño; pasa a maquila.", modulo="laboratorio", ref=trabajo_id)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/disenos/{diseno_id}/rechazar")
def api_rechazar_diseno_laboratorio(trabajo_id: int, diseno_id: int, payload: RechazarDisenoLaboratorio, usuario: dict = Depends(requiere_ver_laboratorio)):
    """El estudiante pide que se corrija el diseño -- el trabajo se queda en
    'aprobar_diseno' hasta que el laboratorio suba una corrección."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "aprobar_diseno":
        raise HTTPException(status_code=400, detail="Este trabajo no está esperando aprobación de diseño")
    diseno = db.obtener_diseno_laboratorio(diseno_id)
    if not diseno or diseno["trabajo_id"] != trabajo_id:
        raise HTTPException(status_code=404, detail="Diseño no encontrado")
    if diseno["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Este diseño ya fue revisado")
    motivo = (payload.motivo or "").strip() or None
    db.rechazar_diseno_laboratorio(diseno_id, usuario["id"], motivo)
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"{trabajo['solicitante_nombre']} pidió corregir el diseño" + (f": {motivo}" if motivo else "") + ".",
    )
    if usuario.get("rol") == "estudiante":
        avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario["empresa_id"]), f"✏️ Corregir diseño · {trabajo.get('folio', '')}",
                             f"{trabajo['solicitante_nombre']} pidió cambios" + (f": {motivo}" if motivo else "."),
                             modulo="laboratorio", ref=trabajo_id)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


def _stream_escaneo_original_dscore(empresa_id, trabajo):
    """Común a los dos endpoints de escaneo original de abajo (la descarga
    forzada, solo para el laboratorio, y la que usa el visor 3D para
    mostrar el diseño en contexto, que también puede pedir el propio
    estudiante) -- resuelve el pedido en DS Core, encuentra el archivo del
    escaneo (label 'DI_SCAN') y regresa el stream de su contenido real
    (.zip con los STL, uno por maxilar), SIN descargarlo completo a
    memoria ni guardar copia en la base de datos. Lanza HTTPException con
    el mensaje adecuado en cada paso que puede fallar -- así los dos
    endpoints comparten exactamente los mismos mensajes de error."""
    if not trabajo.get("dscore_order_name"):
        raise HTTPException(status_code=400, detail="Este trabajo no viene de un pedido de DS Core -- no hay escaneo original.")
    if not trabajo.get("pago_registrado_en") or round(trabajo["costo_total"] - trabajo["pago_monto_total"], 2) > 0:
        raise HTTPException(status_code=400, detail="Todavía no se puede ver el escaneo original -- falta confirmar el pago completo.")
    tokens = db.obtener_tokens_dscore(empresa_id)
    if not tokens:
        raise HTTPException(status_code=400, detail="DS Core todavía no está conectado -- ve a Administrar → Laboratorio → DS Core.")
    access_token = _access_token_dscore_vigente(empresa_id)
    try:
        order = dscore.obtener_order_por_name(tokens["base_host"], access_token, trabajo["dscore_order_name"])
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")
    if not order:
        raise HTTPException(status_code=404, detail="Ya no se encontró este pedido en DS Core.")
    archivo = dscore.buscar_archivo_escaneo_de_order(order)
    if not archivo or not archivo.get("uri"):
        raise HTTPException(status_code=404, detail="Este pedido de DS Core no trae ningún escaneo adjunto.")
    try:
        metadata = dscore.obtener_metadata_archivo(tokens["base_host"], access_token, archivo["uri"])
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")
    content_uri = metadata.get("contentUri")
    if not content_uri:
        raise HTTPException(status_code=502, detail="DS Core no indicó cómo descargar el contenido de este escaneo.")
    try:
        return dscore.descargar_contenido_stream(tokens["base_host"], access_token, content_uri, file_type="STL")
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo descargar el escaneo desde DS Core: {e}")


@app.get("/api/laboratorio/{trabajo_id}/descargar-escaneo-original")
def api_descargar_escaneo_original_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Descarga el/los archivo(s) STL del ESCANEO ORIGINAL que se hizo en
    DS Core (Dentsply Sirona) para este pedido -- distinto al diseño que
    el laboratorio sube después en 'Aprobar diseño' (eso ya tiene su
    propio endpoint, y su propio endpoint de SOLO VER -- ver
    /ver-escaneo-original abajo). Solo se puede descargar una vez que el
    pago quedó cubierto por completo. Fuerza la descarga (Content-
    Disposition: attachment) -- para verlo directo en el visor 3D del
    navegador se usa el otro endpoint de abajo."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    r = _stream_escaneo_original_dscore(usuario["empresa_id"], trabajo)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "Descargó el escaneo original (STL) del pedido de DS Core.")
    nombre_descarga = f"escaneo_original_{trabajo['folio']}.zip"
    return StreamingResponse(
        r.iter_content(chunk_size=65536),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre_descarga}"'},
    )


@app.get("/api/laboratorio/{trabajo_id}/ver-escaneo-original")
def api_ver_escaneo_original_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    """Mismo contenido que /descargar-escaneo-original (el .zip con los STL
    del escaneo original de DS Core), pero SIN forzar la descarga -- lo usa
    el visor 3D del paso 'Aprobar diseño' para mostrar el diseño puesto en
    contexto sobre el escaneo completo, en vez de la pieza sola flotando.
    A diferencia del endpoint de descarga (solo laboratorio/admin), este
    también lo puede pedir el propio estudiante dueño del trabajo -- es lo
    que ve al revisar y aprobar su diseño."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    r = _stream_escaneo_original_dscore(usuario["empresa_id"], trabajo)
    return StreamingResponse(r.iter_content(chunk_size=65536), media_type="application/zip")


@app.post("/api/laboratorio/{trabajo_id}/recibir-sucursal")
def api_recibir_sucursal_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_laboratorio_entrega)):
    """La sucursal confirma que el trabajo ya volvió del laboratorio — pasa
    directo a 'listo para entrega'."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo["estado"] != "envio_sucursal":
        raise HTTPException(status_code=400, detail="Este trabajo no está en camino de regreso a la sucursal")
    if trabajo.get("destino_tipo") == "escuela":
        raise HTTPException(status_code=400, detail="Este trabajo se lleva a la escuela: se entrega ahí directamente, con la firma del estudiante")
    if usuario["rol"] != "admin":
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        if not mi_sucursal_id or trabajo["entrega_sucursal_id"] != mi_sucursal_id:
            raise HTTPException(status_code=403, detail=f"Este trabajo va a {trabajo.get('destino_texto')}, no a tu sucursal")
    db.marcar_recibido_sucursal(usuario["empresa_id"], trabajo_id, usuario["id"])
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Confirmó que llegó a {trabajo.get('destino_texto')} — listo para entregar.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/entregas")
def api_entregas_laboratorio(todos: bool = False, usuario: dict = Depends(requiere_ver_laboratorio)):
    """Para la app de las encargadas: lo que viene en camino o está listo
    para entregar en MI sucursal (el laboratorio también ve lo que se lleva
    a la escuela; el admin ve todo)."""
    soy_lab = _es_usuario_laboratorio(usuario)
    if usuario["rol"] == "estudiante":
        raise HTTPException(status_code=403, detail="Solo personal")
    puede = (usuario["rol"] == "admin" or usuario.get("acceso_laboratorio_entrega", False)
             or usuario["rol"] == "encargado_sucursal" or soy_lab)
    if not puede:
        raise HTTPException(status_code=403, detail="No tienes el privilegio para recibir o entregar trabajos de laboratorio")
    mi_sucursal = db.obtener_sucursal_id_usuario(usuario["id"])
    if todos:
        lista = db.listar_trabajos_para_entregas(usuario["empresa_id"])
    else:
        lista = db.listar_entregas_laboratorio(usuario["empresa_id"], mi_sucursal,
                                               incluir_escuela=soy_lab, todas=usuario["rol"] in ("admin", "superadmin"))
    for t in lista:
        _resumen_entrega_laboratorio(t, usuario, mi_sucursal, soy_lab)
    return lista


def _resumen_entrega_laboratorio(t, usuario, mi_sucursal, soy_lab):
    """Deja solo lo que la app de entregas necesita y le agrega dónde está,
    qué pedido es, si se puede entregar aquí y con qué matrícula."""
    for k in ("firma_recepcion", "pago_comprobante_base64", "firma_entrega", "datos_factura_json", "escaneos"):
        t.pop(k, None)
    t["pagos_reportados"] = []
    estado = t.get("estado")
    if estado == "envio_sucursal":
        t["ubicacion_texto"] = "En camino a la escuela" if t.get("destino_tipo") == "escuela" else f"En camino a {t.get('destino_texto')}"
    elif estado == "listo_entrega":
        t["ubicacion_texto"] = f"En {t.get('destino_texto')} · listo para entregar"
    elif estado == "entregado":
        t["ubicacion_texto"] = f"Entregado {str(t.get('fecha_entrega') or '')[:10]}"
    elif estado == "recibido":
        t["ubicacion_texto"] = f"Sucursal {t.get('sucursal_nombre') or ''} · todavía no entra al laboratorio"
    else:
        t["ubicacion_texto"] = f"Laboratorio · {NOMBRES_ESTADO_LABORATORIO_BITACORA.get(estado, estado)}"
    piezas = t.get("piezas") or []
    partes = []
    for p in piezas:
        partes.append(" ".join(x for x in [p.get("tipo_trabajo"), p.get("material"), f"#{p.get('diente')}" if p.get("diente") else "", p.get("color")] if x))
    t["pedido_texto"] = "; ".join(partes)
    t["matricula_estudiante"] = t.get("matricula") if t.get("creado_por_rol") == "estudiante" else None
    es_escuela = t.get("destino_tipo") == "escuela"
    if usuario["rol"] == "admin":
        t["es_mi_sucursal"] = True
    elif es_escuela:
        t["es_mi_sucursal"] = bool(soy_lab or usuario.get("acceso_laboratorio_entrega", False))
    else:
        t["es_mi_sucursal"] = bool(mi_sucursal) and t.get("entrega_sucursal_id") == mi_sucursal
    t["puede_entregar"] = t["es_mi_sucursal"] and estado in ("envio_sucursal", "listo_entrega")
    return t


@app.get("/api/laboratorio/buscar-entrega")
def api_buscar_entrega_laboratorio(q: str, usuario: dict = Depends(requiere_laboratorio_entrega)):
    """Búsqueda por matrícula o nombre, disponible en la ventanilla de
    CUALQUIER sucursal -- para saber si el trabajo existe, si ya está
    pagado, y en qué sucursal está en realidad si no es la de quien busca
    (así se le puede decir al estudiante a dónde ir si se equivocó)."""
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Escribe al menos 2 caracteres para buscar")
    resultados = db.buscar_trabajos_laboratorio_para_entrega(usuario["empresa_id"], q)
    mi_sucursal_id = None if usuario["rol"] == "admin" else db.obtener_sucursal_id_usuario(usuario["id"])
    for r in resultados:
        r["es_mi_sucursal"] = usuario["rol"] == "admin" or (mi_sucursal_id is not None and r["sucursal_id"] == mi_sucursal_id)
    return resultados


@app.post("/api/laboratorio/{trabajo_id}/piezas")
def api_agregar_pieza_laboratorio(trabajo_id: int, payload: PiezaLaboratorioIn, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "recibido" and usuario["rol"] != "admin":
        raise HTTPException(status_code=400, detail="Ya no se pueden agregar dientes — el trabajo ya salió de la sucursal")
    if not trabajo.get("pago_registrado_en") and usuario["rol"] != "admin":
        raise HTTPException(status_code=400, detail="Primero hay que registrar el pago")
    if payload.tipo_trabajo not in db.TIPOS_TRABAJO_LABORATORIO:
        raise HTTPException(status_code=400, detail="Tipo de trabajo inválido")
    if any(p["diente"] == payload.diente for p in trabajo["piezas"]):
        raise HTTPException(status_code=400, detail=f"El diente {payload.diente} ya está en el odontograma — edítalo en vez de agregarlo de nuevo")
    precio_fijo = db.precio_fijo_laboratorio(trabajo.get("universidad_clinica"), payload.tipo_trabajo, payload.material)
    costo_final = precio_fijo if precio_fijo is not None else payload.costo
    db.agregar_pieza_laboratorio(trabajo_id, payload.diente, payload.tipo_trabajo, payload.material, payload.color, payload.notas, costo_final)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Agregó al odontograma: diente {payload.diente} — {payload.tipo_trabajo}.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.patch("/api/laboratorio/piezas/{pieza_id}")
def api_actualizar_pieza_laboratorio(pieza_id: int, payload: PiezaLaboratorioIn, usuario: dict = Depends(requiere_ver_laboratorio)):
    """Editar una pieza que ya estaba en el odontograma — se usa cuando en el
    odontograma le dan clic de nuevo a un diente que ya tenía trabajo, para
    corregirlo en vez de crear uno duplicado."""
    trabajo_id = db.obtener_trabajo_id_de_pieza(pieza_id)
    if not trabajo_id:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "recibido" and usuario["rol"] != "admin":
        raise HTTPException(status_code=400, detail="Ya no se pueden editar dientes — el trabajo ya salió de la sucursal")
    if payload.tipo_trabajo not in db.TIPOS_TRABAJO_LABORATORIO:
        raise HTTPException(status_code=400, detail="Tipo de trabajo inválido")
    precio_fijo = db.precio_fijo_laboratorio(trabajo.get("universidad_clinica"), payload.tipo_trabajo, payload.material)
    costo_final = precio_fijo if precio_fijo is not None else payload.costo
    db.actualizar_pieza_laboratorio(pieza_id, payload.tipo_trabajo, payload.material, payload.color, payload.notas, costo_final)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Editó en el odontograma: diente {payload.diente} — {payload.tipo_trabajo}.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.delete("/api/laboratorio/piezas/{pieza_id}")
def api_eliminar_pieza_laboratorio(pieza_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo_id = db.obtener_trabajo_id_de_pieza(pieza_id)
    if trabajo_id:
        trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
        if trabajo:
            _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
        if trabajo and trabajo["estado"] != "recibido" and usuario["rol"] != "admin":
            raise HTTPException(status_code=400, detail="Ya no se pueden quitar dientes — el trabajo ya salió de la sucursal")
    db.eliminar_pieza_laboratorio(pieza_id)
    if trabajo_id:
        db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "Quitó una pieza del odontograma.")
        return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    return {"ok": True}


@app.post("/api/laboratorio/{trabajo_id}/evidencias")
def api_agregar_evidencia_laboratorio(trabajo_id: int, payload: NuevaEvidenciaLaboratorio, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if len(payload.archivo_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    db.agregar_evidencia_laboratorio(trabajo_id, payload.archivo_base64, payload.archivo_nombre, payload.descripcion, usuario["id"])
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/actualizaciones")
def api_agregar_actualizacion_laboratorio(trabajo_id: int, payload: NuevaActualizacionLaboratorio, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], payload.texto)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/entregar")
def api_entregar_laboratorio(trabajo_id: int, payload: EntregaLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Entrega final con la firma del estudiante/doctor. En sucursal: ya
    recibido ahí (listo para entrega). En la escuela: el laboratorio lo
    entrega directo desde "Envío a la escuela"."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if trabajo.get("destino_tipo") == "escuela" and trabajo["estado"] == "envio_sucursal":
        if not (_es_usuario_laboratorio(usuario) or usuario.get("acceso_laboratorio_entrega", False)):
            raise HTTPException(status_code=403, detail="Solo el laboratorio entrega los trabajos que se llevan a la escuela")
    else:
        if trabajo["estado"] != "listo_entrega":
            raise HTTPException(status_code=400, detail="Este trabajo todavía no está listo para entregar")
        if not (usuario["rol"] == "admin" or usuario.get("acceso_laboratorio_entrega", False) or usuario["rol"] == "encargado_sucursal"):
            raise HTTPException(status_code=403, detail="No tienes el privilegio para recibir o entregar trabajos de laboratorio")
        if usuario["rol"] != "admin":
            mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
            if not mi_sucursal_id or trabajo["entrega_sucursal_id"] != mi_sucursal_id:
                raise HTTPException(status_code=403, detail=f"Este trabajo se entrega en {trabajo.get('destino_texto')}, no en tu sucursal")
    if len(payload.firma_entrega) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La firma pesa demasiado")
    db.registrar_entrega_laboratorio(usuario["empresa_id"], trabajo_id, usuario["id"], payload.observaciones_entrega, payload.firma_entrega)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], "Registró la entrega del trabajo — el doctor/estudiante firmó de recibido.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/{trabajo_id}/entregar-matricula")
def api_entregar_matricula_laboratorio(trabajo_id: int, payload: EntregaMatriculaLaboratorio, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Entrega en un solo paso desde la app de entregas: el estudiante dice su
    matrícula y, si coincide y el trabajo está en MI sucursal (en camino o
    listo), se entrega. Si venía en camino, primero se marca que llegó."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    usuario = _con_permisos(usuario)
    soy_lab = _es_usuario_laboratorio(usuario)
    if not (usuario["rol"] == "admin" or usuario.get("acceso_laboratorio_entrega", False)
            or usuario["rol"] == "encargado_sucursal" or soy_lab):
        raise HTTPException(status_code=403, detail="No tienes el privilegio para entregar trabajos de laboratorio")
    if trabajo["estado"] not in ("envio_sucursal", "listo_entrega"):
        raise HTTPException(status_code=400, detail="Este trabajo todavía no sale del laboratorio, o ya se entregó")
    mi_sucursal = db.obtener_sucursal_id_usuario(usuario["id"])
    resumen = _resumen_entrega_laboratorio(dict(trabajo), usuario, mi_sucursal, soy_lab)
    if not resumen["es_mi_sucursal"]:
        raise HTTPException(status_code=403, detail=f"Este trabajo se entrega en {trabajo.get('destino_texto')}, no en tu sucursal")
    esperada = (resumen.get("matricula_estudiante") or "").strip().upper()
    if not esperada:
        raise HTTPException(status_code=400, detail="Este trabajo no es de un estudiante con matrícula: entrégalo con firma")
    if payload.matricula.strip().upper() != esperada:
        raise HTTPException(status_code=400, detail="La matrícula no coincide con la del estudiante de este trabajo")
    if trabajo["estado"] == "envio_sucursal" and trabajo.get("destino_tipo") != "escuela":
        db.marcar_recibido_sucursal(usuario["empresa_id"], trabajo_id, usuario["id"])
        db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Llegó a {trabajo.get('destino_texto')}.")
    db.registrar_entrega_laboratorio(usuario["empresa_id"], trabajo_id, usuario["id"],
                                     f"Entregado con matrícula {esperada}", None)
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"],
                                         f"Registró la entrega — el estudiante confirmó con su matrícula {esperada}.")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/{trabajo_id}/orden-trabajo.pdf")
def api_pdf_orden_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    empresa = db.obtener_empresa(usuario["empresa_id"])
    pdf_bytes = pdfs_laboratorio.generar_orden_trabajo(trabajo, empresa)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename=orden_trabajo_{trabajo['folio']}.pdf"})


# ==================== LABORATORIO — PORTAL DE ESTUDIANTES (Fase 1) ====================
# Cuenta propia por estudiante (login = su matrícula), limitada a SUS PROPIOS
# trabajos. Por ahora el pago y la firma de recepción se siguen haciendo en
# persona en la sucursal (Fase 2 los mueve a en línea, con Mercado Pago). El
# "Folio de escaneo" sigue siendo texto libre por ahora -- la Fase 2 lo
# reemplaza por la búsqueda real del escaneo en DS Core.

@app.get("/privacidad")
@app.get("/soporte")
def pagina_privacidad():
    """Aviso de privacidad y soporte (público) — la URL que piden Google Play y
    App Store para publicar las apps."""
    return FileResponse(os.path.join(FRONTEND_DIR, "privacidad.html"))


@app.get("/eliminar-cuenta")
def pagina_eliminar_cuenta():
    """Cómo pedir que se borre la cuenta de Markinc Lab y qué datos se conservan
    (la URL que pide Google Play en Seguridad de los datos)."""
    return FileResponse(os.path.join(FRONTEND_DIR, "eliminar_cuenta.html"))


@app.get("/laboratorio-estudiantes/{codigo}")
def pagina_laboratorio_estudiantes(codigo: str):
    """Página PÚBLICA -- el login/registro vive DENTRO de esta página (con la
    matrícula del estudiante), igual que Pantalla/Kiosko de Turnos son
    páginas públicas identificadas por un código secreto en la URL."""
    return FileResponse(os.path.join(FRONTEND_DIR, "laboratorio_estudiantes.html"))


@app.get("/api/laboratorio/estudiantes/info/{codigo}")
def api_info_estudiantes_laboratorio(codigo: str):
    empresa = db.obtener_empresa_por_codigo_estudiantes_laboratorio(codigo)
    if not empresa:
        raise HTTPException(status_code=404, detail="Este enlace no es válido")
    return {"empresa_nombre": empresa["nombre"]}


@app.post("/api/laboratorio/estudiantes/registro/{codigo}")
def api_registro_estudiante_laboratorio(codigo: str, payload: RegistroEstudianteLaboratorio):
    empresa = db.obtener_empresa_por_codigo_estudiantes_laboratorio(codigo)
    if not empresa:
        raise HTTPException(status_code=404, detail="Este enlace no es válido")
    matricula = payload.matricula.strip()
    if db.obtener_usuario_por_username(matricula):
        raise HTTPException(status_code=409, detail="Esa matrícula ya está registrada — si ya tienes cuenta, inicia sesión.")
    email = payload.email.strip().lower()
    if not _email_valido(email):
        raise HTTPException(status_code=400, detail="El correo electrónico no es válido.")
    db.registrar_estudiante_laboratorio(
        empresa["id"], matricula, payload.password, payload.nombre_completo.strip(), payload.telefono.strip(), email,
    )
    usuario = db.obtener_usuario_por_username(matricula)
    token = auth.crear_token(usuario)
    return {
        "token": token,
        "usuario": {
            "id": usuario["id"], "username": usuario["username"],
            "nombre": usuario["nombre_completo"], "rol": usuario["rol"],
            "empresa_id": usuario["empresa_id"],
        },
    }


@app.post("/api/laboratorio/estudiantes/codigo")
def api_obtener_codigo_estudiantes_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    codigo = db.obtener_o_crear_codigo_estudiantes_laboratorio(usuario["empresa_id"])
    return {"codigo": codigo, "url_registro": f"/laboratorio-estudiantes/{codigo}"}


@app.post("/api/laboratorio/estudiantes/codigo/regenerar")
def api_regenerar_codigo_estudiantes_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    codigo = db.regenerar_codigo_estudiantes_laboratorio(usuario["empresa_id"])
    return {"codigo": codigo, "url_registro": f"/laboratorio-estudiantes/{codigo}"}


# ---- Base de estudiantes registrados (Administrar → Portal de estudiantes) ----
# Editar, bloquear, borrar, dar vigencia por meses y darlos de alta en
# Microsip como clientes. Con la vigencia vencida o bloqueado, el estudiante
# no puede entrar (ver _motivo_bloqueo_estudiante).

class EditarEstudianteIn(BaseModel):
    matricula: Optional[str] = Field(default=None, min_length=3, max_length=40)
    nombre_completo: Optional[str] = Field(default=None, min_length=1, max_length=160)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=160)
    password: Optional[str] = Field(default=None, min_length=6)


class BloquearEstudianteIn(BaseModel):
    bloqueado: bool


class VigenciaEstudianteIn(BaseModel):
    meses: Optional[int] = Field(default=None, ge=1, le=60)
    hasta: Optional[str] = None      # 'YYYY-MM-DD' exacta
    quitar: bool = False             # sin vigencia (sin límite)


class MicrosipEstudianteIn(BaseModel):
    microsip_cliente_id: Optional[int] = None
    nuevo: bool = False


def _estudiante_o_404(usuario, estudiante_id):
    e = db.obtener_estudiante_laboratorio(usuario["empresa_id"], estudiante_id)
    if not e:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return e


def _sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1
    dias_mes = [31, 29 if (anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return date(anio, mes, min(fecha.day, dias_mes))


@app.get("/api/laboratorio/estudiantes")
def api_listar_estudiantes_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    return {"estudiantes": db.listar_estudiantes_laboratorio(usuario["empresa_id"]),
            "avisos": {"correo": correo.configurado(), "push": push_notifications.configurado()}}


@app.patch("/api/laboratorio/estudiantes/{estudiante_id}")
def api_editar_estudiante_laboratorio(estudiante_id: int, payload: EditarEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):
    actual = _estudiante_o_404(usuario, estudiante_id)
    cambios = {}
    if payload.matricula is not None and payload.matricula.strip() != actual["matricula"]:
        nueva = payload.matricula.strip()
        if db.obtener_usuario_por_username(nueva):
            raise HTTPException(status_code=409, detail="Esa matrícula ya la usa otra cuenta.")
        cambios["matricula"] = nueva
    if payload.nombre_completo is not None:
        cambios["nombre_completo"] = payload.nombre_completo.strip()
    if payload.telefono is not None:
        cambios["telefono"] = payload.telefono.strip() or None
    if payload.email is not None:
        email = payload.email.strip().lower()
        if email and not _email_valido(email):
            raise HTTPException(status_code=400, detail="El correo electrónico no es válido.")
        cambios["email"] = email or None
    if payload.password:
        cambios["password"] = payload.password
    return db.actualizar_estudiante_laboratorio(usuario["empresa_id"], estudiante_id, cambios)


@app.post("/api/laboratorio/estudiantes/{estudiante_id}/bloquear")
def api_bloquear_estudiante_laboratorio(estudiante_id: int, payload: BloquearEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):
    _estudiante_o_404(usuario, estudiante_id)
    return db.actualizar_estudiante_laboratorio(usuario["empresa_id"], estudiante_id, {"activo": not payload.bloqueado})


@app.post("/api/laboratorio/estudiantes/{estudiante_id}/vigencia")
def api_vigencia_estudiante_laboratorio(estudiante_id: int, payload: VigenciaEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):
    """meses: se suman desde hoy, o desde su vigencia actual si todavía no vence.
    hasta: fecha exacta. quitar: sin límite."""
    actual = _estudiante_o_404(usuario, estudiante_id)
    if payload.quitar:
        hasta = None
    elif payload.hasta:
        try:
            hasta = date.fromisoformat(payload.hasta)
        except ValueError:
            raise HTTPException(status_code=400, detail="Fecha inválida")
    elif payload.meses:
        hoy = db.ahora().date()
        base = date.fromisoformat(actual["vigencia_hasta"]) if actual.get("vigencia_hasta") else hoy
        hasta = _sumar_meses(max(base, hoy), payload.meses)
    else:
        raise HTTPException(status_code=400, detail="Indica cuántos meses o la fecha.")
    return db.actualizar_estudiante_laboratorio(usuario["empresa_id"], estudiante_id, {"vigencia_hasta": hasta})


@app.delete("/api/laboratorio/estudiantes/{estudiante_id}")
def api_borrar_estudiante_laboratorio(estudiante_id: int, usuario: dict = Depends(requiere_admin_completo)):
    _estudiante_o_404(usuario, estudiante_id)
    if not db.borrar_estudiante_laboratorio(usuario["empresa_id"], estudiante_id):
        raise HTTPException(status_code=409, detail="Este estudiante ya tiene trabajos de laboratorio, no se puede borrar "
                                                    "(se perdería su historial). Mejor bloquéalo.")
    return {"ok": True}


class LimpiarLaboratorioIn(BaseModel):
    confirmacion: str
    movimientos: bool = True
    estudiantes: bool = True


@app.get("/api/laboratorio/limpiar")
def api_resumen_limpiar_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    return db.resumen_limpieza_laboratorio(usuario["empresa_id"])


@app.post("/api/laboratorio/limpiar")
def api_limpiar_laboratorio(payload: LimpiarLaboratorioIn, usuario: dict = Depends(requiere_admin_completo)):
    """Arrancar en limpio: borra pedidos/trabajos de laboratorio y/o a todos
    los estudiantes de la empresa. Hay que escribir BORRAR para confirmar."""
    if payload.confirmacion.strip().upper() != "BORRAR":
        raise HTTPException(status_code=400, detail="Escribe BORRAR para confirmar.")
    if not payload.movimientos and not payload.estudiantes:
        raise HTTPException(status_code=400, detail="Elige qué quieres borrar.")
    try:
        hecho = db.limpiar_laboratorio(usuario["empresa_id"], payload.movimientos, payload.estudiantes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se borró nada: {e}")
    return {"ok": True, **hecho}


@app.post("/api/laboratorio/estudiantes/{estudiante_id}/microsip")
def api_microsip_estudiante_laboratorio(estudiante_id: int, payload: MicrosipEstudianteIn, usuario: dict = Depends(requiere_admin_completo)):
    """Lo da de alta como cliente en Microsip. Si hay clientes parecidos y no
    se ha elegido, regresa {"estado": "elegir_cliente", "similares": [...]}."""
    e = _estudiante_o_404(usuario, estudiante_id)
    cfg = _config_escritura_o_error(usuario["empresa_id"])
    datos = {"nombre": e["nombre_completo"], "telefono": e.get("telefono"), "email": e.get("email")}
    ms_id = payload.microsip_cliente_id
    if not ms_id and not payload.nuevo:
        try:
            similares = _similares_microsip(cfg, datos)
        except Exception as ex:
            raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {ex}")
        if similares:
            return {"estado": "elegir_cliente", "similares": similares}
    try:
        r = microsip_escritura.alta_cliente(cfg, datos_cliente=datos, cliente_id=ms_id)
    except microsip_escritura.ErrorMicrosip as ex:
        raise HTTPException(status_code=400, detail=f"Microsip no aceptó el alta — {ex}")
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"No se pudo dar de alta en Microsip: {ex}")
    estudiante = db.actualizar_estudiante_laboratorio(usuario["empresa_id"], estudiante_id, {"microsip_cliente_id": r["cliente_id"]})
    return {"estado": "listo", **r, "estudiante": estudiante}


@app.post("/api/laboratorio/estudiantes/{estudiante_id}/avisar-vigencia")
def api_avisar_vigencia_estudiante(estudiante_id: int, usuario: dict = Depends(requiere_admin_completo)):
    """Manda ahora el aviso de vigencia (push + correo) — para probar."""
    e = _estudiante_o_404(usuario, estudiante_id)
    fila = db.obtener_usuario_por_username(e["matricula"])
    return _mandar_aviso_vigencia(fila, e.get("vigencia_dias"))


def _mandar_aviso_vigencia(fila, dias):
    hasta = fila.get("vigencia_hasta")
    hasta_txt = hasta.strftime("%d/%m/%Y") if hasattr(hasta, "strftime") else (hasta or "")
    if dias is None:
        titulo, texto = "Markinc Lab", "Tu cuenta de estudiante no tiene fecha de vencimiento."
    elif dias <= 0:
        titulo = "Tu acceso de estudiante vence hoy"
        texto = (f"Hola {fila.get('nombre_completo') or ''}: tu vigencia como estudiante en Markinc Lab vence hoy ({hasta_txt}). "
                 "Para seguir usando la app, actualiza tu información de estudiante en cualquiera de nuestras sucursales.")
    else:
        titulo = f"Tu acceso de estudiante vence en {dias} días"
        texto = (f"Hola {fila.get('nombre_completo') or ''}: tu vigencia como estudiante en Markinc Lab vence el {hasta_txt}. "
                 "Para no perder el acceso, actualiza tu información de estudiante en cualquiera de nuestras sucursales.")
    push = push_notifications.enviar(fila.get("fcm_token"), titulo, texto, {"tipo": "vigencia"})
    mail = correo.enviar(fila.get("email"), titulo, texto + "\n\nMarkinc Lab")
    return {"push": push, "correo": mail}


def _revisar_vigencias_estudiantes():
    """Diario: avisa 7 días antes y el día que vence (una vez cada uno)."""
    try:
        for fila, tipo in db.estudiantes_para_aviso_vigencia():
            r = _mandar_aviso_vigencia(fila, tipo)
            db.marcar_aviso_vigencia(fila["id"], tipo, fila["vigencia_hasta"])
            print(f"[vigencia] aviso {tipo}d a {fila.get('username')}: {r}")
    except Exception as e:
        print(f"[vigencia] error revisando vigencias: {e}")


@app.on_event("startup")
def iniciar_scheduler_vigencias():
    if not APSCHEDULER_DISPONIBLE:
        return
    sched = BackgroundScheduler(timezone=str(db.ZONA_MX))
    sched.add_job(_revisar_vigencias_estudiantes, "cron", hour=9, minute=5, id="vigencias_estudiantes")
    sched.add_job(_revisar_vigencias_estudiantes, "date",
                  run_date=db.ahora() + timedelta(minutes=2), id="vigencias_estudiantes_arranque")
    sched.start()


# ---- Escaneo que sube el estudiante con su pedido ----

@app.post("/api/laboratorio/mios/{trabajo_id}/escaneo")
async def api_subir_escaneo_estudiante(trabajo_id: int, request: Request, archivo: UploadFile = File(...),
                                       usuario: dict = Depends(requiere_estudiante_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] in ("entregado", "cancelado"):
        raise HTTPException(status_code=400, detail="Este trabajo ya está cerrado.")
    largo = request.headers.get("content-length")
    if largo and largo.isdigit() and int(largo) > MAX_DISENO_ARCHIVO_BYTES + 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB).")
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contenido) > MAX_DISENO_ARCHIVO_BYTES:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~90MB).")
    nombre = (archivo.filename or "escaneo").strip()[:200]
    await run_in_threadpool(db.guardar_escaneo_laboratorio, trabajo_id, nombre, contenido, usuario["id"])
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Subió su escaneo: {nombre}")
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/{trabajo_id}/escaneos/{escaneo_id}/archivo")
def api_descargar_escaneo_estudiante(trabajo_id: int, escaneo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    esc = db.obtener_escaneo_laboratorio(trabajo_id, escaneo_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escaneo no encontrado")
    if esc["liberado"] or esc["contenido"] is None:
        raise HTTPException(status_code=410, detail="Este archivo ya se borró porque el trabajo se entregó.")
    nombre = urllib.parse.quote(esc["nombre_archivo"] or "escaneo")
    return Response(content=bytes(esc["contenido"]), media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{nombre}"})


@app.get("/api/laboratorio/mios/cuenta")
def api_mi_cuenta_estudiante_laboratorio(usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """Datos de la cuenta del estudiante y su vigencia (para el aviso de
    'tu acceso vence en N días' en el portal y la app)."""
    return db.cuenta_estudiante_laboratorio(usuario["empresa_id"], usuario["id"])


class EliminarCuentaIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/laboratorio/mios/eliminar-cuenta")
def api_eliminar_mi_cuenta_estudiante(payload: EliminarCuentaIn, usuario: dict = Depends(auth.get_current_user)):
    """El estudiante elimina su cuenta desde la app (Apple 5.1.1(v) y Google
    Play). Pide su contraseña para confirmar. No se puede deshacer."""
    if usuario["rol"] != "estudiante":
        raise HTTPException(status_code=403, detail="Esta acción es solo para cuentas de estudiante")
    registro = db.obtener_usuario_por_username(usuario["username"])
    if not registro or not auth.verificar_password(payload.password, registro["password_hash"]):
        # 400 y no 401: la app trata cualquier 401 como "sesión terminada" y lo sacaría.
        raise HTTPException(status_code=400, detail="La contraseña no es correcta")
    if not db.eliminar_cuenta_estudiante_laboratorio(usuario["empresa_id"], usuario["id"]):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"ok": True}


class FcmTokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


@app.post("/api/laboratorio/mios/fcm-token")
def api_guardar_fcm_token_estudiante(payload: FcmTokenIn, usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """La app Android guarda aquí el token de notificaciones de su celular."""
    db.guardar_fcm_token_usuario(usuario["id"], payload.token.strip())
    return {"ok": True}


@app.get("/api/laboratorio/mios")
def api_listar_mis_trabajos_laboratorio(usuario: dict = Depends(requiere_estudiante_laboratorio)):
    return db.listar_trabajos_laboratorio_de_usuario(usuario["empresa_id"], usuario["id"])


class DevolucionLaboratorioIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=2000)
    foto_base64: Optional[str] = None


@app.post("/api/laboratorio/mios/{trabajo_id}/devolver")
def api_devolver_trabajo_laboratorio(trabajo_id: int, payload: DevolucionLaboratorioIn, usuario: dict = Depends(requiere_ver_laboratorio)):
    """El estudiante (o el personal, a su nombre) regresa un trabajo que
    quedó mal: queda en "Devolución" para que el laboratorio la revise."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] not in ("entregado", "listo_entrega"):
        raise HTTPException(status_code=400, detail="Solo se puede devolver un trabajo ya terminado (listo o entregado)")
    if payload.foto_base64 and len(payload.foto_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 5MB)")
    motivo = payload.motivo.strip()
    db.registrar_devolucion_laboratorio(usuario["empresa_id"], trabajo_id, motivo)
    if payload.foto_base64:
        db.agregar_evidencia_laboratorio(trabajo_id, _como_data_url(payload.foto_base64), "devolucion.jpg",
                                         f"Devolución: {motivo[:200]}", usuario["id"])
    db.agregar_actualizacion_laboratorio(trabajo_id, usuario["id"], f"Devolvió el trabajo. Motivo: {motivo}")
    # Para que el aviso al estudiante al resolverla parta de "devolución".
    try:
        db.marcar_push_trabajo_laboratorio(trabajo_id, _firma_push_lab(db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)))
    except Exception as e:
        print(f"[avisos] devolución {trabajo_id}: {e}")
    destinatarios = db.ids_usuarios_laboratorio(usuario["empresa_id"])
    if trabajo.get("entrega_sucursal_id"):
        destinatarios += db.ids_encargados_sucursal(usuario["empresa_id"], trabajo["entrega_sucursal_id"])
    avisos.avisar_seguro(destinatarios, f"↩️ Devolución · {trabajo.get('folio', '')}",
                         f"{trabajo.get('solicitante_nombre', '')}: {motivo[:200]}", modulo="laboratorio", ref=trabajo_id,
                         excluir=[usuario["id"]])
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


class ResolverDevolucionIn(BaseModel):
    acepta: bool
    respuesta: Optional[str] = Field(default=None, max_length=2000)


@app.post("/api/laboratorio/{trabajo_id}/devolucion")
def api_resolver_devolucion_laboratorio(trabajo_id: int, payload: ResolverDevolucionIn, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """El laboratorio revisa la devolución: la acepta (vuelve a "En
    laboratorio" para rehacerlo, otra vez paso por paso) o no procede
    (regresa a "Entregado" con su respuesta)."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if not _es_usuario_laboratorio(usuario):
        raise HTTPException(status_code=403, detail="Solo el laboratorio revisa las devoluciones")
    if trabajo["estado"] != "devolucion":
        raise HTTPException(status_code=400, detail="Este trabajo no tiene una devolución pendiente")
    respuesta = _limpio(payload.respuesta)
    if not payload.acepta and not respuesta:
        raise HTTPException(status_code=400, detail="Escribe por qué no procede la devolución (se le avisa al estudiante)")
    db.resolver_devolucion_laboratorio(usuario["empresa_id"], trabajo_id, payload.acepta, respuesta, usuario["id"])
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        ("Aceptó la devolución — el trabajo vuelve al laboratorio para rehacerse." if payload.acepta
         else "La devolución no procede") + (f" ({respuesta})" if respuesta else ""),
    )
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.get("/api/laboratorio/mios/{trabajo_id}")
def api_obtener_mi_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_estudiante_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    return trabajo


@app.post("/api/laboratorio/mios")
def api_crear_mi_trabajo_laboratorio(payload: NuevoTrabajoLaboratorioEstudiante, background_tasks: BackgroundTasks,
                                     usuario: dict = Depends(requiere_estudiante_laboratorio)):
    datos_factura = _datos_factura_lab(payload.requiere_factura, payload.datos_factura)
    sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
    if not sucursal_lab:
        raise HTTPException(status_code=400, detail="Todavía no hay una sucursal marcada como Laboratorio — pídele al administrador que marque una en Reparaciones → Sucursales.")
    if payload.sucursal_recogida_id:
        sucursal_recogida = db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_recogida_id)
        if not sucursal_recogida or not sucursal_recogida["activo"]:
            raise HTTPException(status_code=400, detail="La sucursal de recogida que elegiste no es válida")
    else:
        sucursal_recogida = db.obtener_sucursal_recogida_default_estudiantes(usuario["empresa_id"]) or sucursal_lab
    registro = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])
    if not registro:
        raise HTTPException(status_code=404, detail="Tu cuenta no se encontró")
    if not payload.piezas:
        raise HTTPException(status_code=400, detail="Elige al menos un diente en el odontograma.")
    piezas = []
    for pieza in payload.piezas:
        if pieza.tipo_trabajo not in db.TIPOS_TRABAJO_LABORATORIO:
            raise HTTPException(status_code=400, detail=f"Tipo de trabajo inválido para el diente {pieza.diente}")
        datos_pieza = pieza.model_dump()
        # El precio lo pone el servidor (precio fijo del acuerdo), no el celular.
        precio = db.precio_fijo_laboratorio("BUAP", pieza.tipo_trabajo, pieza.material)
        if precio is not None:
            datos_pieza["costo"] = precio
        piezas.append(datos_pieza)
    trabajo = db.crear_trabajo_laboratorio(
        usuario["empresa_id"], sucursal_recogida["id"], "estudiante", registro["nombre_completo"],
        "BUAP", registro.get("telefono_whatsapp") or "", payload.paciente_nombre, payload.fecha_compromiso,
        payload.notas, None, usuario["id"],
        (payload.folio_escaneo or "").strip() or None, payload.requiere_factura, piezas,
    )
    db.marcar_origen_app_laboratorio(trabajo["id"])
    trabajo["origen"] = "app"
    db.agregar_actualizacion_laboratorio(
        trabajo["id"], usuario["id"],
        f"Registro pedido en app — {registro['nombre_completo']} creó su pedido desde la app. Falta registrar el pago.",
    )
    _despues_de_crear_pedido_app(trabajo, usuario, payload.requiere_factura, datos_factura, payload.datos_factura, background_tasks)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo["id"])


def _access_token_dscore_vigente(empresa_id):
    """Trae un access_token vigente de DS Core para esta empresa,
    refrescándolo automáticamente si ya venció (o está por vencer)."""
    tokens = db.obtener_tokens_dscore(empresa_id)
    if not tokens:
        raise HTTPException(status_code=400, detail="DS Core todavía no está conectado -- ve a Administrar → Laboratorio → DS Core.")
    ahora_iso = db.ahora().isoformat(timespec="seconds")
    if tokens.get("expira_en") and ahora_iso < tokens["expira_en"]:
        return tokens["access_token"]
    creds = db.obtener_credenciales_oauth_dscore(empresa_id)
    if not creds or not tokens.get("refresh_token"):
        raise HTTPException(status_code=400, detail="La conexión con DS Core venció y no se pudo renovar sola -- hay que volver a conectar desde Administrar → Laboratorio → DS Core.")
    try:
        access_token, refresh_token, expires_in = dscore.refrescar_tokens(creds["client_id"], creds["client_secret"], tokens["refresh_token"])
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo renovar la conexión con DS Core: {e}")
    expira_en = None
    if expires_in:
        expira_en = (db.ahora() + timedelta(seconds=int(expires_in) - 60)).isoformat(timespec="seconds")
    db.guardar_tokens_dscore(empresa_id, access_token, refresh_token or tokens["refresh_token"], expira_en)
    return access_token


@app.post("/api/laboratorio/mios/importar-dscore")
def api_importar_pedido_dscore(payload: ImportarPedidoDSCore, background_tasks: BackgroundTasks,
                               usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """El estudiante mete el código que le dio su maestro (el readableId
    del pedido que se generó en DS Core al escanear) y se le arma el
    trabajo solo -- paciente y referencia al pedido, para no escribirlo
    a mano. El odontograma (piezas/dientes) se completa después, igual
    que cuando el trabajo se crea a mano sin piezas todavía."""
    datos_factura = _datos_factura_lab(payload.requiere_factura, payload.datos_factura)
    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])
    if not tokens:
        raise HTTPException(status_code=400, detail="La conexión con DS Core todavía no está lista -- avísale al administrador.")
    access_token = _access_token_dscore_vigente(usuario["empresa_id"])
    codigo = payload.codigo.strip()
    try:
        order = dscore.buscar_order_por_codigo(tokens["base_host"], access_token, codigo)
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")
    if not order:
        raise HTTPException(status_code=404, detail="No encontramos ningún pedido con ese código en DS Core. Verifica que esté bien escrito.")
    ya_existe = db.obtener_trabajo_laboratorio_por_dscore_order(usuario["empresa_id"], order["name"])
    if ya_existe:
        raise HTTPException(status_code=400, detail=f"Ese pedido ya fue importado antes (folio {ya_existe['folio']}).")
    paciente_nombre = dscore.nombre_paciente_de_order(tokens["base_host"], access_token, order)
    sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
    if not sucursal_lab:
        raise HTTPException(status_code=400, detail="Todavía no hay una sucursal marcada como Laboratorio — pídele al administrador que marque una en Reparaciones → Sucursales.")
    if payload.sucursal_recogida_id:
        sucursal_recogida = db.obtener_sucursal_reparacion(usuario["empresa_id"], payload.sucursal_recogida_id)
        if not sucursal_recogida or not sucursal_recogida["activo"]:
            raise HTTPException(status_code=400, detail="La sucursal de recogida que elegiste no es válida")
    else:
        sucursal_recogida = db.obtener_sucursal_recogida_default_estudiantes(usuario["empresa_id"]) or sucursal_lab
    registro = db.obtener_usuario_por_id(usuario["empresa_id"], usuario["id"])
    if not registro:
        raise HTTPException(status_code=404, detail="Tu cuenta no se encontró")
    # Si el pedido trae detalle de restauración por diente (tipo, material,
    # tono), se arma el odontograma solo -- así el estudiante ve de una vez
    # cuánto va a pagar en vez de ver el trabajo con costo $0.00.
    piezas_extraidas = dscore.extraer_piezas_de_order(order)
    # Solo zirconia/disilicato están dentro del acuerdo de precio fijo con el
    # laboratorio -- si el doctor especificó otro material en DS Core, no se
    # puede procesar solo: se le pide al estudiante llamar al laboratorio
    # para cotizarlo, o corregir el material antes de importar.
    materiales_override = payload.materiales_override or {}
    piezas_pendientes = []
    for pieza in piezas_extraidas:
        if pieza.get("material") in db.MATERIALES_LABORATORIO:
            continue
        diente = pieza["diente"]
        if diente in materiales_override:
            nuevo_material = materiales_override[diente]
            if nuevo_material not in db.MATERIALES_LABORATORIO:
                raise HTTPException(status_code=400, detail=f"Material inválido para el diente {diente}")
            pieza["material"] = nuevo_material
        else:
            piezas_pendientes.append(pieza)
    if piezas_pendientes:
        detalle_piezas = "; ".join(
            f"diente {p['diente']} ({p['tipo_trabajo']}): {p.get('material') or 'sin material especificado'}"
            for p in piezas_pendientes
        )
        raise HTTPException(status_code=409, detail={
            "msg": (
                "Este pedido tiene material que no está dentro del acuerdo con el laboratorio "
                f"(zirconia o disilicato) — {detalle_piezas}. Llama al laboratorio para cotizar ese "
                "material, o cambia el material de esas piezas antes de importar."
            ),
            "piezas_pendientes": [
                {"diente": p["diente"], "tipo_trabajo": p["tipo_trabajo"], "material_dscore": p.get("material")}
                for p in piezas_pendientes
            ],
        })
    for pieza in piezas_extraidas:
        precio_fijo = db.precio_fijo_laboratorio("BUAP", pieza["tipo_trabajo"], pieza.get("material"))
        if precio_fijo is not None:
            pieza["costo"] = precio_fijo
    trabajo = db.crear_trabajo_laboratorio(
        usuario["empresa_id"], sucursal_recogida["id"], "estudiante", registro["nombre_completo"],
        "BUAP", registro.get("telefono_whatsapp") or "", paciente_nombre, None,
        f"Importado desde DS Core (pedido {order.get('readableId') or codigo}).", None, usuario["id"],
        codigo, payload.requiere_factura, piezas_extraidas,
    )
    db.marcar_dscore_order_en_trabajo(usuario["empresa_id"], trabajo["id"], order["name"])
    if piezas_extraidas:
        mensaje_piezas = f"Se detectaron {len(piezas_extraidas)} pieza(s) en el pedido de DS Core y se agregaron solas al odontograma. Falta registrar el pago."
    else:
        mensaje_piezas = "Falta completar el odontograma y registrar el pago."
    db.agregar_actualizacion_laboratorio(
        trabajo["id"], usuario["id"],
        f"{registro['nombre_completo']} importó este trabajo desde DS Core (código {codigo}). {mensaje_piezas}",
    )
    _despues_de_crear_pedido_app(trabajo, usuario, payload.requiere_factura, datos_factura, payload.datos_factura, background_tasks)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo["id"])


# ---- Pedidos de la app: datos de factura y cotización en Microsip ----
# Si el estudiante pide factura, captura sus datos fiscales (a mano, con el
# QR de la constancia o subiéndola). En TODOS los pedidos de la app se crea
# una cotización en Microsip, en la sucursal y almacén del laboratorio, a
# precio de lista de Microsip y con el usuario de Microsip que elija el admin
# como creador (Administrar → Microsip → Pedidos del laboratorio). Se manda en
# segundo plano: si Microsip no responde, el pedido se crea igual y el
# laboratorio lo reintenta desde el detalle del trabajo.

def _datos_factura_lab(requiere_factura, df):
    """Valida y limpia los datos fiscales. Si pidió factura y no mandó datos
    (app vieja), regresa None y el pedido se crea igual con un aviso."""
    if not requiere_factura or df is None:
        return None
    rfc = (_limpio(df.rfc) or "").upper().replace(" ", "").replace("-", "") or None
    cp = _limpio(df.codigo_postal)
    regimen = _limpio(df.regimen_fiscal)
    uso = _limpio(df.uso_cfdi) or "G03"
    correo = (_limpio(df.correo) or "").lower() or None
    faltan = [n for n, v in (("RFC", rfc), ("razón social", _limpio(df.razon_social)),
                             ("régimen fiscal", regimen), ("código postal", cp)) if not v]
    if faltan:
        raise HTTPException(status_code=400, detail="Para la factura falta: " + ", ".join(faltan) + ".")
    if not facturacion_flete.rfc_valido(rfc):
        raise HTTPException(status_code=400, detail="El RFC no tiene el formato correcto (12 o 13 caracteres).")
    if not facturacion_flete.cp_valido(cp):
        raise HTTPException(status_code=400, detail="El código postal debe tener 5 dígitos.")
    if regimen not in facturacion_flete.REGIMENES_FISCALES:
        raise HTTPException(status_code=400, detail="Elige un régimen fiscal de la lista.")
    if uso not in facturacion_flete.USOS_CFDI:
        raise HTTPException(status_code=400, detail="Elige un uso de CFDI de la lista.")
    if correo and not _email_valido(correo):
        raise HTTPException(status_code=400, detail="El correo para la factura no es válido.")
    if df.constancia_base64 and len(df.constancia_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La constancia pesa demasiado (máximo ~5MB).")
    return {"rfc": rfc, "razon_social": (_limpio(df.razon_social) or "").upper(), "regimen_fiscal": regimen,
            "uso_cfdi": uso, "codigo_postal": cp, "domicilio_fiscal": _limpio(df.domicilio_fiscal),
            "municipio": _limpio(df.municipio), "estado": _limpio(df.estado), "correo": correo}


def _despues_de_crear_pedido_app(trabajo, usuario, requiere_factura, datos_factura, df_in, background_tasks):
    if datos_factura:
        db.guardar_datos_factura_trabajo_laboratorio(trabajo["id"], datos_factura)
        db.guardar_datos_fiscales_usuario(usuario["id"], datos_factura,
                                          _como_data_url(df_in.constancia_base64) if df_in and df_in.constancia_base64 else None,
                                          _limpio(df_in.constancia_nombre) if df_in else None)
        db.agregar_actualizacion_laboratorio(trabajo["id"], usuario["id"],
                                             f"Pidió factura a nombre de {datos_factura['razon_social']} (RFC {datos_factura['rfc']}).")
    elif requiere_factura:
        db.agregar_actualizacion_laboratorio(trabajo["id"], usuario["id"],
                                             "Pidió factura pero no mandó sus datos fiscales — pídeselos (o que actualice la app).")
    if _lab_microsip_activo(usuario["empresa_id"]):
        background_tasks.add_task(_enviar_trabajo_lab_microsip_seguro, usuario["empresa_id"], trabajo["id"])
    db.marcar_push_trabajo_laboratorio(trabajo["id"], _firma_push_lab(trabajo))
    avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario["empresa_id"]), f"🧪 Pedido nuevo de la app · {trabajo.get('folio', '')}",
                         f"{usuario.get('nombre', '')}" + (f" · paciente {trabajo['paciente_nombre']}" if trabajo.get("paciente_nombre") else ""),
                         modulo="laboratorio", ref=trabajo["id"])


# ---- Avisos (push) del laboratorio ----
# Al estudiante: cada vez que su trabajo cambia de estatus o le suben un
# diseño nuevo (se detecta comparando contra el último aviso, ver el
# middleware de abajo), y cuando le confirman o rechazan el pago.
# Al laboratorio: pedido nuevo de la app, pago reportado, diseño aprobado o
# con correcciones.

_TEXTO_ESTADO_LAB = {
    "recibido": "Recibimos tu pedido.",
    "en_laboratorio": "Tu trabajo ya está en el laboratorio.",
    "modelado": "Estamos diseñando tu trabajo.",
    "aprobar_diseno": "Tu diseño está listo: revísalo y apruébalo en la app.",
    "maquila": "Tu trabajo está en maquila (fresado).",
    "maquillado": "Tu trabajo está en maquillado / acabado.",
    "control_calidad": "Tu trabajo está en control de calidad.",
    "envio_sucursal": "Tu trabajo va en camino a la sucursal.",
    "listo_entrega": "¡Tu trabajo está listo para recoger!",
    "entregado": "Tu trabajo fue entregado. ¡Gracias!",
    "cancelado": "Tu trabajo fue cancelado.",
    "devolucion": "Recibimos tu devolución; el laboratorio la va a revisar.",
}


def _firma_push_lab(trabajo):
    return f"{trabajo.get('estado')}|{len(trabajo.get('disenos') or [])}|{trabajo.get('destino_texto') or ''}"


def _avisar_estudiante_trabajo(empresa_id, trabajo_id, actor_id=None):
    """Compara el trabajo contra el último aviso y, si cambió el estatus (o
    hay diseño nuevo), le avisa al estudiante que lo pidió."""
    try:
        trabajo = db.obtener_trabajo_laboratorio(empresa_id, trabajo_id)
        if not trabajo:
            return
        firma = _firma_push_lab(trabajo)
        antes = trabajo.get("push_ultimo_aviso")
        if firma == antes:
            return
        db.marcar_push_trabajo_laboratorio(trabajo_id, firma)
        estudiante_id = trabajo.get("creado_por_id")
        if antes is None or not estudiante_id or estudiante_id == actor_id or not db.es_estudiante(estudiante_id):
            return
        partes_antes = antes.split("|")
        estado_antes = partes_antes[0]
        estado = trabajo.get("estado")
        destino = trabajo.get("destino_texto") or "la sucursal"
        cambio_destino = (estado == estado_antes == "envio_sucursal" and len(partes_antes) >= 3
                          and partes_antes[2] != (trabajo.get("destino_texto") or ""))
        if estado == estado_antes and estado != "aprobar_diseno" and not cambio_destino:
            return
        if cambio_destino:
            texto = (f"Cambio de entrega: lo llevaremos a tu escuela." if trabajo.get("destino_tipo") == "escuela"
                     else f"Cambio de entrega: tu trabajo va ahora a {destino}.")
        elif estado == estado_antes:
            texto = "Te subimos un diseño corregido: revísalo y apruébalo en la app."
        elif estado == "envio_sucursal":
            texto = ("¡Tu trabajo está terminado! Lo llevaremos a tu escuela." if trabajo.get("destino_tipo") == "escuela"
                     else f"¡Tu trabajo está terminado! Va en camino a {destino}.")
        elif estado == "listo_entrega":
            texto = f"¡Tu trabajo ya está en {destino}! Pasa a recogerlo."
        elif estado_antes == "devolucion" and estado == "en_laboratorio":
            texto = "Aceptamos tu devolución: volvemos a trabajar tu pieza."
        elif estado_antes == "devolucion" and estado == "entregado":
            texto = "Revisamos tu devolución y no procede" + (f": {trabajo['devolucion_respuesta']}" if trabajo.get("devolucion_respuesta") else ".")
        else:
            texto = _TEXTO_ESTADO_LAB.get(estado, f"Ahora está: {str(estado).replace('_', ' ')}.")
        avisos.avisar([estudiante_id], f"🦷 {trabajo.get('folio', '')}" + (f" · {trabajo['paciente_nombre']}" if trabajo.get("paciente_nombre") else ""),
                      texto, modulo="laboratorio", ref=trabajo_id)
    except Exception as e:
        print(f"[avisos] laboratorio {trabajo_id}: {e}")


_RUTA_TRABAJO_LAB = re.compile(r"^/api/laboratorio/(\d+)(/|$)")


@app.middleware("http")
async def _middleware_avisos_laboratorio(request: Request, call_next):
    respuesta = await call_next(request)
    try:
        if request.method in ("POST", "PATCH", "PUT") and respuesta.status_code < 400:
            m = _RUTA_TRABAJO_LAB.match(request.url.path)
            if m:
                actor = None
                cab = request.headers.get("authorization") or ""
                if cab.startswith("Bearer "):
                    try:
                        actor = auth.verificar_token(cab.split(" ", 1)[1])
                    except Exception:
                        actor = None
                if actor and actor.get("empresa_id"):
                    threading.Thread(target=_avisar_estudiante_trabajo,
                                     args=(actor["empresa_id"], int(m.group(1)), actor.get("id")), daemon=True).start()
    except Exception as e:
        print(f"[avisos] middleware: {e}")
    return respuesta


def _lab_microsip_activo(empresa_id):
    if not MICROSIP_DISPONIBLE:
        return False
    cfg = db.obtener_config_microsip_escritura(empresa_id) or {}
    return bool(cfg.get("lab_microsip_activa") and cfg.get("microsip_host"))


def _articulos_lab(cfg):
    try:
        return json.loads(cfg.get("lab_microsip_articulos_json") or "{}") or {}
    except (TypeError, ValueError):
        return {}


def _partidas_microsip_lab(cfg, trabajo):
    """Una partida por pieza: el artículo de Microsip según el material
    (zirconia, disilicato) o el de "otro" si no tiene uno propio."""
    mapa = _articulos_lab(cfg)
    partidas, faltan = [], []
    for p in trabajo.get("piezas") or []:
        material = (p.get("material") or "").strip().lower()
        art = mapa.get(material) or mapa.get("otro")
        etiqueta = f"diente {p.get('diente')} ({p.get('tipo_trabajo')}{' ' + material if material else ''})"
        if not art or not art.get("id"):
            faltan.append(material or "sin material")
            continue
        nota = f"Diente {p.get('diente')} - {p.get('tipo_trabajo')}" + (f" {material}" if material else "") + \
               (f", color {p.get('color')}" if p.get("color") else "")
        partidas.append({"articulo_id": int(art["id"]), "cantidad": 1, "nombre": art.get("nombre") or etiqueta, "nota": nota})
    return partidas, sorted(set(faltan))


def _cliente_microsip_lab(cfg, datos, factura, estudiante):
    """Cliente de Microsip sin preguntarle a nadie: con factura, el que tenga
    el mismo RFC (o exactamente la misma razón social); sin factura, el ya
    ligado al estudiante o el que tenga su mismo teléfono/nombre. Si no hay,
    None = se da de alta."""
    if not factura and estudiante.get("microsip_cliente_id"):
        if microsip_escritura.leer_cliente(cfg, estudiante["microsip_cliente_id"]):
            return estudiante["microsip_cliente_id"]
    # Con factura se busca solo por RFC y razón social: el nombre o teléfono
    # del estudiante llevaría a SU cliente, no al de la factura.
    busqueda = {"razon_social": datos.get("razon_social"), "rfc": datos.get("rfc")} if factura else datos
    for c in _similares_microsip(cfg, busqueda):
        motivos = c.get("motivos") or []
        if "Mismo RFC" in motivos:
            return c["cliente_id"]
        if not factura and "Mismo teléfono" in motivos:
            return c["cliente_id"]
        if (c.get("puntaje") or 0) >= 0.85:  # mismo nombre (Microsip no deja repetirlo)
            return c["cliente_id"]
    return None


def _datos_cliente_lab(trabajo):
    """(estudiante, datos_cliente para Microsip, si es con factura)."""
    estudiante = db.obtener_datos_fiscales_usuario(trabajo["creado_por_id"]) or {}
    try:
        df = json.loads(trabajo.get("datos_factura_json") or "null")
    except (TypeError, ValueError):
        df = None
    factura = bool(trabajo.get("requiere_factura") and df)
    datos = {"nombre": trabajo.get("solicitante_nombre") or estudiante.get("nombre_completo"),
             "telefono": trabajo.get("telefono") or estudiante.get("telefono_whatsapp"),
             "email": estudiante.get("email")}
    if factura:
        datos.update({"razon_social": df.get("razon_social"), "rfc": df.get("rfc"), "regimen_fiscal": df.get("regimen_fiscal"),
                      "uso_cfdi": df.get("uso_cfdi"), "codigo_postal": df.get("codigo_postal"),
                      "domicilio": df.get("domicilio_fiscal"), "municipio": df.get("municipio"), "estado": df.get("estado"),
                      "email": df.get("correo") or estudiante.get("email")})
    return estudiante, datos, factura


def _cambiar_cliente_lab_microsip(cfg, trabajo, fallar):
    """La cotización ya estaba en Microsip y el estudiante pidió factura
    después: se le cambia el cliente al de la factura (mismo RFC o alta)."""
    estudiante, datos, factura = _datos_cliente_lab(trabajo)
    if not factura:
        db.marcar_factura_microsip_lista(trabajo["id"])
        return {"folio": trabajo["microsip_folio"], "ya_estaba": True}
    try:
        cliente_id = _cliente_microsip_lab(cfg, datos, True, estudiante)
        r = microsip_escritura.cambiar_cliente_cotizacion(
            cfg, docto_ve_id=trabajo["microsip_docto_id"], datos_cliente=datos, cliente_id=cliente_id,
            usuario=cfg.get("lab_microsip_usuario"))
    except microsip_escritura.ErrorMicrosip as e:
        fallar(f"No se pudo poner la factura en la cotización de Microsip — {e}")
    except Exception as e:
        fallar(f"No se pudo conectar con Microsip: {e}")
    db.marcar_factura_microsip_lista(trabajo["id"])
    db.agregar_actualizacion_laboratorio(
        trabajo["id"], trabajo["creado_por_id"],
        f"Cotización {r['folio']} de Microsip cambiada al cliente de la factura "
        f"({'cliente NUEVO ' if r['cliente_creado'] else ''}{r['cliente_nombre']})."
        + (" Avisos: " + " ".join(r["avisos"]) if r.get("avisos") else ""))
    return {**r, "factura": True}


def _enviar_trabajo_lab_microsip(empresa_id, trabajo_id):
    """Crea la cotización del pedido en Microsip. Regresa el resultado o lanza
    RuntimeError con el motivo (que también queda guardado en el trabajo)."""
    cfg = db.obtener_config_microsip_escritura(empresa_id) or {}
    trabajo = db.obtener_trabajo_laboratorio(empresa_id, trabajo_id)
    if not trabajo:
        raise RuntimeError("Trabajo no encontrado")

    def fallar(msg):
        db.marcar_trabajo_laboratorio_microsip(trabajo_id, error=msg)
        raise RuntimeError(msg)

    if trabajo.get("microsip_folio"):
        if trabajo.get("microsip_factura_pendiente"):
            return _cambiar_cliente_lab_microsip(cfg, trabajo, fallar)
        return {"folio": trabajo["microsip_folio"], "ya_estaba": True}

    if not cfg.get("microsip_host"):
        fallar("Microsip no está configurado (Administrar → Microsip).")
    if not cfg.get("lab_microsip_sucursal_id") or not cfg.get("lab_microsip_almacen_id"):
        fallar("Falta elegir la sucursal y el almacén del laboratorio en Administrar → Microsip → Pedidos del laboratorio.")
    partidas, faltan = _partidas_microsip_lab(cfg, trabajo)
    if faltan:
        fallar("Falta elegir el artículo de Microsip para: " + ", ".join(faltan) + " (Administrar → Microsip → Pedidos del laboratorio).")
    if not partidas:
        fallar("El pedido todavía no tiene piezas (odontograma vacío).")
    estudiante, datos, factura = _datos_cliente_lab(trabajo)
    try:
        cliente_id = _cliente_microsip_lab(cfg, datos, factura, estudiante)
        r = microsip_escritura.enviar_cotizacion(
            cfg, datos_cliente=datos, partidas=partidas, cliente_id=cliente_id,
            descripcion=f"Laboratorio {trabajo['folio']} - {datos['nombre'] or ''}".strip(" -"),
            sucursal_id=cfg["lab_microsip_sucursal_id"], almacen_id=cfg["lab_microsip_almacen_id"],
            usuario_creador=cfg.get("lab_microsip_usuario"))
    except microsip_escritura.ErrorMicrosip as e:
        fallar(f"Microsip no aceptó la cotización — {e}")
    except RuntimeError:
        raise
    except Exception as e:
        fallar(f"No se pudo conectar con Microsip: {e}")
    db.marcar_trabajo_laboratorio_microsip(trabajo_id, docto_id=r["docto_ve_id"], folio=r["folio"])
    if not factura and not estudiante.get("microsip_cliente_id") and r.get("cliente_id"):
        db.ligar_usuario_microsip(trabajo["creado_por_id"], r["cliente_id"])
    db.agregar_actualizacion_laboratorio(
        trabajo_id, trabajo["creado_por_id"],
        f"Cotización {r['folio']} creada en Microsip ({'cliente NUEVO ' if r['cliente_creado'] else ''}{r['cliente_nombre']}, "
        f"total ${r['total']:,.2f}{' con factura' if factura else ''})."
        + (" Avisos: " + " ".join(r["avisos"]) if r.get("avisos") else ""))
    return r


def _enviar_trabajo_lab_microsip_seguro(empresa_id, trabajo_id):
    try:
        _enviar_trabajo_lab_microsip(empresa_id, trabajo_id)
    except Exception as e:
        print(f"[laboratorio microsip] trabajo {trabajo_id}: {e}")


@app.post("/api/laboratorio/{trabajo_id}/microsip")
def api_enviar_trabajo_lab_microsip(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Reintento manual (o envío de un pedido de mostrador) desde el detalle."""
    if not _es_usuario_laboratorio(usuario):
        raise HTTPException(status_code=403, detail="Solo el laboratorio o el administrador pueden mandarlo a Microsip.")
    _requiere_microsip_disponible()
    if not db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    try:
        r = _enviar_trabajo_lab_microsip(usuario["empresa_id"], trabajo_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"resultado": r, "trabajo": db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)}


@app.get("/api/laboratorio/{trabajo_id}/constancia")
def api_constancia_trabajo_lab(trabajo_id: int, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    """Constancia fiscal que subió el estudiante (la última)."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    c = db.obtener_constancia_fiscal_usuario(trabajo["creado_por_id"])
    if not c:
        raise HTTPException(status_code=404, detail="El estudiante no subió constancia")
    return {"nombre": c["constancia_fiscal_nombre"], "archivo": c["constancia_fiscal_base64"]}


@app.get("/api/laboratorio/mios-datos-fiscales")
def api_mis_datos_fiscales_lab(usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """Para prellenar la factura con lo último que usó + los catálogos del SAT."""
    r = db.obtener_datos_fiscales_usuario(usuario["id"]) or {}
    datos = dict(r.get("datos") or {})
    if not datos.get("correo") and r.get("email"):
        datos["correo"] = r["email"]
    return {"datos": datos, "tiene_constancia": bool(r.get("constancia_fiscal_nombre")),
            "catalogos": {"regimenes": facturacion_flete.REGIMENES_FISCALES, "usos_cfdi": facturacion_flete.USOS_CFDI}}


@app.post("/api/laboratorio/mios/{trabajo_id}/factura")
def api_facturar_mi_trabajo_laboratorio(trabajo_id: int, payload: DatosFacturaLabIn, background_tasks: BackgroundTasks,
                                        usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """El estudiante pide factura DESPUÉS de crear su pedido (o cambia los
    datos). Si la cotización ya está en Microsip se le cambia el cliente al
    de la factura; si todavía no, se crea ya con la factura."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] in ("entregado", "cancelado"):
        raise HTTPException(status_code=400, detail="Este trabajo ya se cerró; pide la factura directo al laboratorio.")
    datos = _datos_factura_lab(True, payload)
    ya_en_microsip = bool(trabajo.get("microsip_folio"))
    db.marcar_factura_trabajo_laboratorio(trabajo_id, datos, ya_en_microsip)
    db.guardar_datos_fiscales_usuario(usuario["id"], datos,
                                      _como_data_url(payload.constancia_base64) if payload.constancia_base64 else None,
                                      _limpio(payload.constancia_nombre))
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"],
        f"{'Cambió los datos de' if trabajo.get('datos_factura_json') else 'Pidió'} factura a nombre de "
        f"{datos['razon_social']} (RFC {datos['rfc']}).")
    if _lab_microsip_activo(usuario["empresa_id"]):
        background_tasks.add_task(_enviar_trabajo_lab_microsip_seguro, usuario["empresa_id"], trabajo_id)
    return db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)


@app.post("/api/laboratorio/mios/{trabajo_id}/reportar-pago")
def api_reportar_pago_transferencia_estudiante(trabajo_id: int, payload: ReportarPagoTransferenciaEstudiante, usuario: dict = Depends(requiere_estudiante_laboratorio)):
    """El estudiante sube la foto/captura de su comprobante de transferencia
    desde su portal -- la IA solo lo LEE para sugerir monto/fecha/referencia,
    nunca da el pago por bueno sola: el trabajo se queda igual de bloqueado
    hasta que el laboratorio confirme este reporte contra el banco."""
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if trabajo["estado"] != "recibido":
        raise HTTPException(status_code=400, detail="Este trabajo ya no está en recepción")
    if trabajo.get("pago_registrado_en"):
        faltante = round(trabajo["costo_total"] - trabajo["pago_monto_total"], 2)
        if faltante <= 0:
            raise HTTPException(status_code=400, detail="Este trabajo ya está cubierto — no hace falta reportar otro pago")
    if len(payload.comprobante_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La foto del comprobante pesa demasiado (máximo 5MB)")
    payload.comprobante_base64 = _como_data_url(payload.comprobante_base64)
    datos_ia = ia.leer_comprobante_transferencia_laboratorio(payload.comprobante_base64, empresa_id=usuario["empresa_id"])
    reporte = db.reportar_pago_transferencia_laboratorio(
        trabajo_id, usuario["id"], payload.comprobante_base64,
        datos_ia.get("monto"), datos_ia.get("fecha"), datos_ia.get("referencia"), datos_ia.get("banco"),
    )
    db.agregar_actualizacion_laboratorio(
        trabajo_id, usuario["id"], "Reportó un pago por transferencia — queda pendiente de confirmar por el laboratorio.",
    )
    avisos.avisar_seguro(db.ids_usuarios_laboratorio(usuario["empresa_id"]), f"💳 Pago reportado · {trabajo.get('folio', '')}",
                         f"{usuario.get('nombre', '')} subió su comprobante" + (f" (${datos_ia['monto']:,.2f})" if isinstance(datos_ia.get("monto"), (int, float)) else "") + ". Confírmalo contra el banco.",
                         modulo="laboratorio", ref=trabajo_id)
    return reporte


@app.get("/api/laboratorio/pagos-reportados")
def api_listar_pagos_reportados_laboratorio(estado: Optional[str] = "pendiente", usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    sucursal_id = None
    if usuario["rol"] != "admin":
        mi_sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])
        sucursal_lab = db.obtener_sucursal_laboratorio(usuario["empresa_id"])
        es_laboratorio = bool(sucursal_lab) and mi_sucursal_id == sucursal_lab["id"]
        if not es_laboratorio:
            sucursal_id = mi_sucursal_id
    return db.listar_pagos_reportados_laboratorio(usuario["empresa_id"], estado, sucursal_id)


def _obtener_reporte_y_trabajo_o_404(usuario, reporte_id):
    reporte = db.obtener_pago_reportado_laboratorio(usuario["empresa_id"], reporte_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    if reporte["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Este reporte ya fue revisado")
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if not _es_usuario_laboratorio(usuario):
        raise HTTPException(status_code=403, detail="Solo el usuario del laboratorio puede confirmar o rechazar pagos reportados")
    return reporte, trabajo


@app.post("/api/laboratorio/pagos-reportados/{reporte_id}/confirmar")
def api_confirmar_pago_reportado_laboratorio(reporte_id: int, payload: ConfirmarPagoReportado, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    reporte, trabajo = _obtener_reporte_y_trabajo_o_404(usuario, reporte_id)
    if not payload.metodos:
        raise HTTPException(status_code=400, detail="Indica al menos un método de pago")
    for m in payload.metodos:
        if m.metodo not in db.TIPOS_METODO_PAGO_LABORATORIO:
            raise HTTPException(status_code=400, detail="Método de pago inválido")
    db.registrar_pago_laboratorio(
        usuario["empresa_id"], reporte["trabajo_id"], usuario["id"],
        [m.model_dump() for m in payload.metodos], reporte["comprobante_base64"],
    )
    db.confirmar_pago_reportado_laboratorio(usuario["empresa_id"], reporte_id, usuario["id"])
    monto_total = round(sum(m.monto for m in payload.metodos), 2)
    metodos_texto = ", ".join(f"{NOMBRES_METODO_PAGO_LABORATORIO.get(m.metodo, m.metodo)} ${m.monto:,.2f}" for m in payload.metodos)
    db.agregar_actualizacion_laboratorio(reporte["trabajo_id"], usuario["id"], f"Confirmó el pago reportado por transferencia — {metodos_texto}.")
    trabajo_actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])
    # El estudiante reportó este pago desde su propia cuenta en la app -- eso
    # YA es su confirmación de que los datos y el odontograma están
    # correctos, igual que si hubiera dibujado la firma a mano. En cuanto
    # queda cubierto el costo total, se le pone la firma sola para no
    # pedirle ese paso aparte.
    if not trabajo_actualizado.get("firma_recepcion"):
        faltante = round(trabajo_actualizado["costo_total"] - trabajo_actualizado["pago_monto_total"], 2)
        if faltante <= 0:
            db.firmar_recepcion_laboratorio(usuario["empresa_id"], reporte["trabajo_id"], db.FIRMA_AUTOMATICA_PAGO_APP)
            db.agregar_actualizacion_laboratorio(
                reporte["trabajo_id"], usuario["id"],
                "Firma de recepción automática: el estudiante ya había pagado desde su propia cuenta en la app.",
            )
            trabajo_actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])
    _auto_entrada_laboratorio(usuario, reporte["trabajo_id"])
    trabajo_actualizado = db.obtener_trabajo_laboratorio(usuario["empresa_id"], reporte["trabajo_id"])
    if db.es_estudiante(trabajo_actualizado.get("creado_por_id")):
        avisos.avisar_seguro([trabajo_actualizado.get("creado_por_id")], f"💳 Pago confirmado · {trabajo_actualizado.get('folio', '')}",
                             f"Recibimos tu pago de ${monto_total:,.2f}. ¡Ya empezamos tu trabajo!"
                             if trabajo_actualizado["costo_total"] - trabajo_actualizado["pago_monto_total"] <= 0
                             else f"Recibimos ${monto_total:,.2f}; te faltan ${trabajo_actualizado['costo_total'] - trabajo_actualizado['pago_monto_total']:,.2f}.",
                             modulo="laboratorio", ref=reporte["trabajo_id"])
    return trabajo_actualizado


@app.post("/api/laboratorio/pagos-reportados/{reporte_id}/rechazar")
def api_rechazar_pago_reportado_laboratorio(reporte_id: int, payload: RechazarPagoReportado, usuario: dict = Depends(requiere_no_ser_estudiante_laboratorio)):
    reporte, trabajo = _obtener_reporte_y_trabajo_o_404(usuario, reporte_id)
    db.rechazar_pago_reportado_laboratorio(usuario["empresa_id"], reporte_id, usuario["id"], payload.motivo.strip())
    db.agregar_actualizacion_laboratorio(reporte["trabajo_id"], usuario["id"], f"Rechazó un pago reportado por transferencia — {payload.motivo.strip()}")
    if db.es_estudiante(trabajo.get("creado_por_id")):
        avisos.avisar_seguro([trabajo.get("creado_por_id")], f"❌ Revisa tu comprobante · {trabajo.get('folio', '')}",
                             f"El laboratorio no pudo confirmar tu pago: {payload.motivo.strip()}", modulo="laboratorio",
                             ref=reporte["trabajo_id"])
    return {"ok": True}


# ==================== BORRADO MASIVO ====================

@app.get("/api/admin/borrado-masivo/contar")
def api_contar_borrado_masivo(tabla: str, fecha_desde: str, fecha_hasta: str, usuario: dict = Depends(requiere_admin_completo)):
    if tabla not in db.TABLAS_BORRADO_MASIVO:
        raise HTTPException(status_code=400, detail="Tabla inválida")
    cantidad = db.contar_registros_borrado_masivo(usuario["empresa_id"], tabla, fecha_desde, fecha_hasta)
    return {"cantidad": cantidad}


class BorradoMasivo(BaseModel):
    tabla: str
    fecha_desde: str
    fecha_hasta: str
    confirmacion: str


@app.post("/api/admin/borrado-masivo")
def api_borrado_masivo(payload: BorradoMasivo, usuario: dict = Depends(requiere_admin_completo)):
    if payload.tabla not in db.TABLAS_BORRADO_MASIVO:
        raise HTTPException(status_code=400, detail="Tabla inválida")
    if payload.confirmacion.strip().upper() != "BORRAR":
        raise HTTPException(status_code=400, detail="Debes escribir BORRAR para confirmar")
    eliminados = db.borrar_masivo(usuario["empresa_id"], payload.tabla, payload.fecha_desde, payload.fecha_hasta)
    return {"eliminados": eliminados}


# ==================== ENTREGAS (módulo de Logística fusionado) ====================

class ChecklistItemPayload(BaseModel):
    texto: str = Field(min_length=1, max_length=300)
    orden: int = 0
    obligatorio: bool = True


class ConfigCedis(BaseModel):
    cedis_direccion: str = Field(min_length=1, max_length=300)


class ImportarDesdeMicrosipPayload(BaseModel):
    liga_mapa: Optional[str] = None


class NuevaEntrega(BaseModel):
    cliente_nombre: str = Field(min_length=1, max_length=200)
    cliente_direccion: Optional[str] = None
    cliente_telefono: Optional[str] = None
    equipo_descripcion: str = Field(min_length=1)
    checklist_items: Optional[List[ChecklistItemPayload]] = None
    fecha_programada: Optional[str] = None
    horario: Optional[str] = None
    vehiculo_id: Optional[int] = None
    liga_mapa: Optional[str] = None
    comentarios: Optional[str] = None
    estatus_pago: Optional[str] = None


class ActualizacionEntrega(BaseModel):
    cliente_nombre: Optional[str] = None
    cliente_direccion: Optional[str] = None
    cliente_telefono: Optional[str] = None
    equipo_descripcion: Optional[str] = None
    fecha_programada: Optional[str] = None
    horario: Optional[str] = None
    vehiculo_id: Optional[int] = None
    liga_mapa: Optional[str] = None
    comentarios: Optional[str] = None
    estatus_pago: Optional[str] = None
    confirmado: Optional[bool] = None


class NuevoVehiculo(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    numero_serie: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    placa: Optional[str] = None
    kilometraje: Optional[int] = None
    notas: Optional[str] = None
    razon_social: Optional[str] = None
    combustible: Optional[str] = None
    numero_factura: Optional[str] = None
    aseguradora: Optional[str] = None
    numero_poliza: Optional[str] = None
    vigencia_poliza: Optional[str] = None
    numero_tarjeta_circulacion: Optional[str] = None
    aplica_verificacion: Optional[bool] = None
    periodo_verificacion_1: Optional[str] = None
    periodo_verificacion_2: Optional[str] = None
    chofer_habitual_id: Optional[int] = None
    geotab_device_id: Optional[str] = None


class ActualizacionVehiculo(BaseModel):
    nombre: Optional[str] = None
    numero_serie: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    placa: Optional[str] = None
    kilometraje: Optional[int] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None
    razon_social: Optional[str] = None
    combustible: Optional[str] = None
    numero_factura: Optional[str] = None
    aseguradora: Optional[str] = None
    numero_poliza: Optional[str] = None
    vigencia_poliza: Optional[str] = None
    numero_tarjeta_circulacion: Optional[str] = None
    aplica_verificacion: Optional[bool] = None
    periodo_verificacion_1: Optional[str] = None
    periodo_verificacion_2: Optional[str] = None
    chofer_habitual_id: Optional[int] = None
    geotab_device_id: Optional[str] = None


class NuevoMantenimientoVehiculo(BaseModel):
    vehiculo_id: int
    tipo: str = "preventivo"
    descripcion: str = Field(min_length=1)
    fecha_programada: str
    frecuencia: str = "unica"
    notas: Optional[str] = None
    responsable_id: Optional[int] = None
    kilometraje_en_servicio: Optional[int] = None
    kilometraje_proximo_servicio: Optional[int] = None


class RealizarMantenimientoVehiculo(BaseModel):
    notas: Optional[str] = None
    kilometraje_en_servicio: Optional[int] = None


class CambioEstadoEntrega(BaseModel):
    estado: str
    comentario: Optional[str] = None


class AsignarInstaladores(BaseModel):
    instalador_ids: List[int]


class NuevoItemChecklist(BaseModel):
    texto: str = Field(min_length=1, max_length=300)
    obligatorio: bool = True


class NuevoItemPlantillaChecklist(BaseModel):
    texto: str = Field(min_length=1, max_length=300)
    automatico: bool = False


class ActualizacionItemPlantillaChecklist(BaseModel):
    texto: Optional[str] = None
    automatico: Optional[bool] = None
    activo: Optional[bool] = None


class FirmaEntrega(BaseModel):
    receptor_nombre: str = Field(min_length=1, max_length=200)
    receptor_puesto: Optional[str] = None
    firma_base64: str = Field(min_length=1)
    latitud: Optional[str] = None
    longitud: Optional[str] = None


@app.get("/api/entregas")
def api_listar_entregas(estado: Optional[str] = None, fecha_desde: Optional[str] = None,
                         fecha_hasta: Optional[str] = None, usuario: dict = Depends(requiere_ver_entregas)):
    instalador_id = usuario["id"] if usuario["rol"] == "instalador" else None
    return db.listar_entregas(usuario["empresa_id"], estado=estado, instalador_id=instalador_id,
                               fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)


@app.get("/api/vehiculos-entrega")
def api_listar_vehiculos_entrega(usuario: dict = Depends(requiere_ver_entregas)):
    return db.listar_vehiculos_entrega(usuario["empresa_id"], solo_activos=False)


@app.post("/api/vehiculos-entrega")
def api_crear_vehiculo_entrega(payload: NuevoVehiculo, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede dar de alta vehículos")
    datos = payload.dict(exclude_unset=True, exclude={"nombre"})
    vid = db.crear_vehiculo_entrega(usuario["empresa_id"], payload.nombre, **datos)
    return {"id": vid}


@app.patch("/api/vehiculos-entrega/{vehiculo_id}")
def api_actualizar_vehiculo_entrega(vehiculo_id: int, payload: ActualizacionVehiculo, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede editar vehículos")
    datos = payload.dict(exclude_unset=True)
    if "activo" in datos:
        db.cambiar_estado_vehiculo_entrega(usuario["empresa_id"], vehiculo_id, datos.pop("activo"))
    if datos:
        db.actualizar_vehiculo_entrega(usuario["empresa_id"], vehiculo_id, **datos)
    return {"ok": True}


# ---- Mantenimientos de vehículo (verificación, servicio, reparaciones) ----

@app.get("/api/mantenimientos-vehiculo")
def api_listar_mantenimientos_vehiculo(estado: Optional[str] = None, vehiculo_id: Optional[int] = None,
                                        usuario: dict = Depends(requiere_ver_entregas)):
    return db.listar_mantenimientos_vehiculo(usuario["empresa_id"], estado=estado, vehiculo_id=vehiculo_id)


@app.post("/api/mantenimientos-vehiculo")
def api_crear_mantenimiento_vehiculo(payload: NuevoMantenimientoVehiculo, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede programar mantenimientos de vehículo")
    mant_id = db.crear_mantenimiento_vehiculo(
        usuario["empresa_id"], payload.vehiculo_id, payload.tipo, payload.descripcion, payload.fecha_programada,
        frecuencia=payload.frecuencia, notas=payload.notas, responsable_id=payload.responsable_id,
        creado_por_id=usuario["id"], kilometraje_en_servicio=payload.kilometraje_en_servicio,
        kilometraje_proximo_servicio=payload.kilometraje_proximo_servicio,
    )
    if not mant_id:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return {"id": mant_id}


@app.post("/api/mantenimientos-vehiculo/{mantenimiento_id}/realizado")
def api_marcar_mantenimiento_vehiculo_realizado(mantenimiento_id: int, payload: RealizarMantenimientoVehiculo,
                                                 usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede marcar mantenimientos de vehículo como realizados")
    resultado = db.marcar_mantenimiento_vehiculo_realizado(
        usuario["empresa_id"], mantenimiento_id, usuario["nombre"], notas=payload.notas,
        kilometraje_en_servicio=payload.kilometraje_en_servicio,
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado")
    return resultado


@app.get("/api/entregas/microsip-pendientes")
def api_buscar_pedidos_pendientes_microsip(prefijo: str, usuario: dict = Depends(requiere_ver_entregas)):
    """Busca pedidos pendientes de surtir cuyo folio empiece con el
    prefijo dado (ej. 'AMI') — para el botón de búsqueda por lote.
    IMPORTANTE: esta ruta debe declararse ANTES que /api/entregas/{entrega_id},
    porque si no, FastAPI intenta interpretar 'microsip-pendientes' como un
    entrega_id numérico y truena con un error 422 de validación."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede importar pedidos de Microsip")
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Todavía no configuras la conexión a Microsip (Administrar → Microsip)")
    try:
        return microsip.buscar_pedidos_pendientes(config, prefijo)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error conectando a Microsip: {e}")


@app.get("/api/entregas/microsip-clientes")
def api_buscar_clientes_microsip_entregas(q: str, usuario: dict = Depends(requiere_ver_entregas)):
    """Busca clientes de Microsip por nombre, para importar una entrega
    eligiendo primero al cliente. Misma ruta 'antes de {entrega_id}' que
    microsip-pendientes, por la misma razón (evitar choque con FastAPI)."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede importar pedidos de Microsip")
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Todavía no configuras la conexión a Microsip (Administrar → Microsip)")
    try:
        return microsip.buscar_clientes(config, q, campo="nombre")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error conectando a Microsip: {e}")


@app.get("/api/entregas/microsip-cliente-pedidos")
def api_pedidos_de_cliente_microsip(cliente_id: int, usuario: dict = Depends(requiere_ver_entregas)):
    """Regresa los pedidos/documentos de un cliente ya elegido, con su
    sucursal, si está facturado, y si le quedan piezas pendientes."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede importar pedidos de Microsip")
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Todavía no configuras la conexión a Microsip (Administrar → Microsip)")
    try:
        return microsip.buscar_pedidos_por_cliente(config, cliente_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error conectando a Microsip: {e}")


@app.get("/api/entregas/checklist-plantilla")
def api_listar_plantilla_checklist_entrega(usuario: dict = Depends(requiere_admin_completo)):
    return db.listar_plantilla_checklist_entrega(usuario["empresa_id"])


@app.post("/api/entregas/checklist-plantilla")
def api_crear_item_plantilla_checklist(payload: NuevoItemPlantillaChecklist, usuario: dict = Depends(requiere_admin_completo)):
    item_id = db.crear_item_plantilla_checklist_entrega(usuario["empresa_id"], payload.texto, payload.automatico)
    return {"id": item_id}


@app.patch("/api/entregas/checklist-plantilla/{item_id}")
def api_actualizar_item_plantilla_checklist(item_id: int, payload: ActualizacionItemPlantillaChecklist, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_item_plantilla_checklist_entrega(usuario["empresa_id"], item_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.delete("/api/entregas/checklist-plantilla/{item_id}")
def api_eliminar_item_plantilla_checklist(item_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_item_plantilla_checklist_entrega(usuario["empresa_id"], item_id):
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"ok": True}


@app.get("/api/entregas/config-cedis")
def api_obtener_config_cedis(usuario: dict = Depends(requiere_ver_entregas)):
    return db.obtener_config_cedis(usuario["empresa_id"]) or {}


@app.post("/api/entregas/config-cedis")
def api_guardar_config_cedis(payload: ConfigCedis, usuario: dict = Depends(requiere_admin_completo)):
    lat, lng, motivo = geo.resolver_coordenadas(payload.cedis_direccion, payload.cedis_direccion, db.obtener_config_locationiq(usuario["empresa_id"]))
    if lat is None:
        raise HTTPException(status_code=400, detail=f"No se pudo ubicar esa dirección — {motivo}")
    db.guardar_config_cedis(usuario["empresa_id"], payload.cedis_direccion, lat, lng)
    return {"ok": True, "cedis_lat": lat, "cedis_lng": lng}

@app.get("/api/entregas/mapa-flotilla")
def api_mapa_flotilla(usuario: dict = Depends(requiere_ver_flotilla)):
    """Para el administrador: posición en vivo de todos los vehículos que
    ya tienen una unidad Geotab asignada, en un solo mapa."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede ver esto")
    vehiculos = [v for v in db.listar_vehiculos_entrega(usuario["empresa_id"], solo_activos=True) if v.get("geotab_device_id")]
    if not vehiculos:
        return []
    config = db.obtener_config_geotab(usuario["empresa_id"])
    try:
        posiciones = geotab.obtener_posiciones_multiples(config, [v["geotab_device_id"] for v in vehiculos])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    resultado = []
    for v in vehiculos:
        pos = posiciones.get(v["geotab_device_id"])
        if pos:
            resultado.append({"vehiculo_id": v["id"], "nombre": v["nombre"], **pos})
    return resultado

@app.get("/api/entregas/{entrega_id}")
def api_obtener_entrega(entrega_id: int, usuario: dict = Depends(requiere_ver_entregas)):
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    if usuario["rol"] == "instalador" and usuario["id"] not in [i["instalador_id"] for i in entrega["instaladores"]]:
        raise HTTPException(status_code=403, detail="No tienes esta entrega asignada")
    _agregar_datos_geo_entrega(usuario["empresa_id"], entrega)
    return entrega


def _agregar_datos_geo_entrega(empresa_id, entrega):
    """Le agrega al dict de la entrega (in place) el tiempo estimado desde el
    CEDIS y las entregas cercanas del mismo día — todo en línea recta, sin
    ninguna API de pago."""
    cedis = db.obtener_config_cedis(empresa_id)
    if cedis and cedis.get("cedis_lat") is not None and entrega.get("destino_lat") is not None:
        distancia = geo.haversine_km(cedis["cedis_lat"], cedis["cedis_lng"], entrega["destino_lat"], entrega["destino_lng"])
        entrega["distancia_cedis_km"] = round(distancia, 1)
        entrega["tiempo_estimado_min"] = geo.estimar_minutos(distancia)
    else:
        entrega["distancia_cedis_km"] = None
        entrega["tiempo_estimado_min"] = None
    if entrega.get("destino_lat") is not None:
        entrega["entregas_cercanas"] = db.listar_entregas_cercanas(
            empresa_id, entrega["id"], entrega.get("fecha_programada"), entrega["destino_lat"], entrega["destino_lng"],
        )
    else:
        entrega["entregas_cercanas"] = []


@app.post("/api/entregas")
def api_crear_entrega(payload: NuevaEntrega, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede crear entregas")
    items = [i.dict() for i in payload.checklist_items] if payload.checklist_items else None
    lat, lng, _motivo = geo.resolver_coordenadas(payload.liga_mapa, payload.cliente_direccion, db.obtener_config_locationiq(usuario["empresa_id"]))
    entrega = db.crear_entrega(
        usuario["empresa_id"], payload.cliente_nombre, payload.cliente_direccion, payload.cliente_telefono,
        payload.equipo_descripcion, usuario["id"], checklist_items=items, fecha_programada=payload.fecha_programada,
        horario=payload.horario, vehiculo_id=payload.vehiculo_id, liga_mapa=payload.liga_mapa,
        comentarios=payload.comentarios, estatus_pago=payload.estatus_pago,
        destino_lat=lat, destino_lng=lng,
    )
    db.agregar_actualizacion_entrega(entrega["id"], usuario["id"], "Creó la entrega.")
    return entrega


@app.patch("/api/entregas/{entrega_id}")
def api_actualizar_entrega(entrega_id: int, payload: ActualizacionEntrega, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede editar los datos de la entrega")
    entrega_actual = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if not entrega_actual:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    campos = payload.dict(exclude_unset=True)
    if "liga_mapa" in campos or "cliente_direccion" in campos:
        liga = campos.get("liga_mapa", entrega_actual.get("liga_mapa"))
        direccion = campos.get("cliente_direccion", entrega_actual.get("cliente_direccion"))
        lat, lng, _motivo = geo.resolver_coordenadas(liga, direccion, db.obtener_config_locationiq(usuario["empresa_id"]))
        if lat is not None:
            campos["destino_lat"] = lat
            campos["destino_lng"] = lng
    db.actualizar_entrega(usuario["empresa_id"], entrega_id, **campos)
    if campos:
        etiquetas = [_CAMPOS_ENTREGA_LABELS.get(k, k) for k in campos if k in _CAMPOS_ENTREGA_LABELS]
        if etiquetas:
            db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"Editó los datos: {', '.join(etiquetas)}.")
    return {"ok": True}


@app.delete("/api/entregas/{entrega_id}")
def api_eliminar_entrega(entrega_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_entrega(usuario["empresa_id"], entrega_id):
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    return {"ok": True}


@app.post("/api/entregas/{entrega_id}/estado")
def api_cambiar_estado_entrega(entrega_id: int, payload: CambioEstadoEntrega, usuario: dict = Depends(requiere_ver_entregas)):
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    if usuario["rol"] == "instalador" and usuario["id"] not in [i["instalador_id"] for i in entrega["instaladores"]]:
        raise HTTPException(status_code=403, detail="No tienes esta entrega asignada")
    ok, error = db.cambiar_estado_entrega(usuario["empresa_id"], entrega_id, payload.estado, usuario["id"], payload.comentario)
    if not ok:
        raise HTTPException(status_code=400, detail=error)
    nombre_estado = NOMBRES_ESTADO_ENTREGA_BITACORA.get(payload.estado, payload.estado)
    texto = f"Cambió el estado a: {nombre_estado}."
    if payload.comentario:
        texto += f" Motivo: {payload.comentario}"
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], texto)
    return db.obtener_entrega(usuario["empresa_id"], entrega_id)


@app.post("/api/entregas/{entrega_id}/instaladores")
def api_asignar_instaladores(entrega_id: int, payload: AsignarInstaladores, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede reasignar la entrega")
    if not db.asignar_instaladores_entrega(usuario["empresa_id"], entrega_id, payload.instalador_ids):
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if entrega["estado"] == "pendiente" and payload.instalador_ids:
        db.cambiar_estado_entrega(usuario["empresa_id"], entrega_id, "asignada", usuario["id"])
        db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"Cambió el estado a: {NOMBRES_ESTADO_ENTREGA_BITACORA['asignada']}.")
    nombres_asignados = [i["nombre_completo"] for i in db.listar_instaladores_activos(usuario["empresa_id"]) if i["id"] in payload.instalador_ids]
    db.agregar_actualizacion_entrega(
        entrega_id, usuario["id"],
        f"Asignó instaladores: {', '.join(nombres_asignados)}." if nombres_asignados else "Quitó todos los instaladores asignados."
    )
    for instalador in db.listar_instaladores_activos(usuario["empresa_id"]):
        if instalador["id"] in payload.instalador_ids:
            notifications.notificar_asignacion(usuario["empresa_id"], instalador, {"folio": entrega["folio"], "departamento": "Entregas", "prioridad": "media"})
    return db.obtener_entrega(usuario["empresa_id"], entrega_id)


@app.post("/api/entregas/{entrega_id}/checklist")
def api_agregar_item_checklist(entrega_id: int, payload: NuevoItemChecklist, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede agregar puntos al checklist")
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    db.agregar_item_checklist_entrega(entrega_id, payload.texto, payload.obligatorio)
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"Agregó ítem al checklist: {payload.texto}.")
    return db.obtener_entrega(usuario["empresa_id"], entrega_id)


@app.post("/api/entregas/{entrega_id}/checklist/{item_id}/completar")
def api_completar_item_checklist(entrega_id: int, item_id: int, completado: bool = True, usuario: dict = Depends(requiere_ver_entregas)):
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    item = next((i for i in entrega["checklist_items"] if i["id"] == item_id), None) if entrega else None
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.marcar_item_checklist_entrega(item_id, usuario["id"], completado)
    verbo = "Marcó" if completado else "Desmarcó"
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"{verbo} ítem del checklist: {item['texto']}.")
    return db.obtener_entrega(usuario["empresa_id"], entrega_id)


@app.delete("/api/entregas/{entrega_id}/checklist/{item_id}")
def api_eliminar_item_checklist(entrega_id: int, item_id: int, usuario: dict = Depends(requiere_ver_entregas)):
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede quitar puntos del checklist")
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    item = next((i for i in entrega["checklist_items"] if i["id"] == item_id), None) if entrega else None
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.eliminar_item_checklist_entrega(item_id)
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"Quitó ítem del checklist: {item['texto']}.")
    return {"ok": True}


@app.post("/api/entregas/{entrega_id}/firmar")
def api_firmar_entrega(entrega_id: int, payload: FirmaEntrega, usuario: dict = Depends(requiere_ver_entregas)):
    entrega = db.obtener_entrega(usuario["empresa_id"], entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    if usuario["rol"] == "instalador" and usuario["id"] not in [i["instalador_id"] for i in entrega["instaladores"]]:
        raise HTTPException(status_code=403, detail="No tienes esta entrega asignada")
    ok, error = db.firmar_entrega(usuario["empresa_id"], entrega_id, payload.receptor_nombre, payload.receptor_puesto,
                                   payload.firma_base64, usuario["id"], payload.latitud, payload.longitud)
    if not ok:
        raise HTTPException(status_code=400, detail=error)
    texto = f"Firmó de conformidad — recibió: {payload.receptor_nombre}"
    if payload.receptor_puesto:
        texto += f" ({payload.receptor_puesto})"
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], texto + ".")
    db.agregar_actualizacion_entrega(entrega_id, usuario["id"], f"Cambió el estado a: {NOMBRES_ESTADO_ENTREGA_BITACORA['entregada']}.")
    return db.obtener_entrega(usuario["empresa_id"], entrega_id)


# ---- Buscar/crear entrega desde un pedido de Microsip (por folio) ----

@app.get("/api/entregas/microsip/{folio}")
def api_buscar_pedido_microsip(folio: str, usuario: dict = Depends(requiere_ver_entregas)):
    """Solo consulta y regresa los datos encontrados — no crea nada todavía,
    para que la persona pueda confirmarlos antes."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede importar pedidos de Microsip")
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Todavía no configuras la conexión a Microsip (Administrar → Microsip)")
    try:
        datos = microsip.buscar_pedido(config, folio)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error conectando a Microsip: {e}")
    if not datos:
        raise HTTPException(status_code=404, detail=f"No se encontró el pedido con folio '{folio}' en Microsip")
    return datos


@app.post("/api/entregas/desde-microsip/{folio}")
def api_crear_entrega_desde_microsip(folio: str, payload: ImportarDesdeMicrosipPayload = ImportarDesdeMicrosipPayload(), usuario: dict = Depends(requiere_ver_entregas)):
    """Busca el pedido en Microsip Y crea la entrega en un solo paso, con el
    checklist ya armado a partir de los artículos del pedido."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede importar pedidos de Microsip")
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Todavía no configuras la conexión a Microsip (Administrar → Microsip)")
    try:
        datos = microsip.buscar_pedido(config, folio)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error conectando a Microsip: {e}")
    if not datos:
        raise HTTPException(status_code=404, detail=f"No se encontró el pedido con folio '{folio}' en Microsip")

    lat, lng, _motivo = geo.resolver_coordenadas(payload.liga_mapa, datos["cliente_direccion"], db.obtener_config_locationiq(usuario["empresa_id"]))
    entrega = db.crear_entrega(
        usuario["empresa_id"], datos["cliente_nombre"], datos["cliente_direccion"], datos["cliente_telefono"],
        datos["equipo_descripcion"], usuario["id"], checklist_items=datos["checklist_items"],
        folio_pedido_microsip=datos["folio_encontrado"], comentarios=datos.get("descripcion_pedido"),
        liga_mapa=payload.liga_mapa, destino_lat=lat, destino_lng=lng,
    )
    db.agregar_actualizacion_entrega(entrega["id"], usuario["id"], f"Creó la entrega importando el pedido {datos['folio_encontrado']} de Microsip.")
    return entrega


# ==================== MICROSIP (conexión de solo lectura a Firebird) ====================

def _requiere_microsip_disponible():
    if not MICROSIP_DISPONIBLE:
        raise HTTPException(
            status_code=503,
            detail="El driver de Firebird ('fdb') todavía no está instalado en el servidor — agrégalo a requirements.txt y redespliega.",
        )


class ConfigMicrosip(BaseModel):
    host: str = Field(min_length=1)
    puerto: int = Field(default=3050, ge=1, le=65535)
    ruta_db: str = Field(min_length=1)
    usuario: str = Field(min_length=1)
    password: Optional[str] = None  # None = no cambiarla; "" = borrarla


@app.get("/api/microsip/config")
def api_obtener_config_microsip(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_microsip_publica(usuario["empresa_id"])
    return config or {"microsip_host": None, "microsip_puerto": 3050, "microsip_ruta_db": None,
                       "microsip_usuario": None, "tiene_password": False}


@app.post("/api/microsip/config")
def api_guardar_config_microsip(payload: ConfigMicrosip, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_config_microsip(usuario["empresa_id"], payload.host, payload.puerto, payload.ruta_db,
                                   payload.usuario, payload.password)
    return {"ok": True}


@app.post("/api/microsip/probar-conexion")
def api_probar_conexion_microsip(usuario: dict = Depends(requiere_admin_completo)):
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    ok, mensaje = microsip.probar_conexion(config)
    if not ok:
        raise HTTPException(status_code=400, detail=mensaje)
    return {"ok": True, "mensaje": mensaje}


# ---- Shopify (ventas de la tienda en línea) — OAuth ----
#
# Desde el 1 de enero de 2026, Shopify ya no da tokens estáticos para apps
# nuevas — hay que hacer el flujo de autorización (OAuth) completo:
# 1) el admin captura el dominio de su tienda + Client ID/Secret de su app
#    (creada en el Dev Dashboard de Shopify)
# 2) le damos clic a "Conectar con Shopify" -> lo mandamos a autorizar en
#    Shopify -> Shopify nos regresa aquí con un código -> lo canjeamos por
#    el access token real y lo guardamos.

class ConfigShopify(BaseModel):
    shop_domain: str = Field(min_length=1)
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # None = no cambiarlo; "" = borrarlo


SHOPIFY_SCOPES = "read_orders,read_products,read_customers"


def _dominio_shopify_normalizado(shop_domain: str) -> str:
    dominio = (shop_domain or "").strip().lower()
    if not dominio.endswith(".myshopify.com") and "." not in dominio:
        dominio = f"{dominio}.myshopify.com"
    return dominio


@app.get("/api/shopify/config")
def api_obtener_config_shopify(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_shopify_publica(usuario["empresa_id"])
    return config or {"shop_domain": None, "client_id": None, "tiene_client_secret": False, "conectado": False}


@app.post("/api/shopify/config")
def api_guardar_config_shopify(payload: ConfigShopify, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_config_shopify(usuario["empresa_id"], payload.shop_domain, payload.client_id, payload.client_secret)
    return {"ok": True}


@app.get("/api/shopify/oauth/iniciar")
def api_iniciar_oauth_shopify(usuario: dict = Depends(requiere_admin_completo)):
    """Regresa la URL de autorización de Shopify a la que el navegador
    debe ir (el frontend hace window.location = esa URL)."""
    creds = db.obtener_credenciales_oauth_shopify(usuario["empresa_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Guarda primero el dominio, Client ID y Client Secret.")
    # Shopify solo reconoce los parámetros estándar de OAuth en esta URL —
    # cualquier parámetro extra (como habíamos puesto antes: empresa_id)
    # hace que la rechace. Y de todas formas Shopify jamás nos regresaría
    # ese parámetro en el callback — solo nos regresa 'state' tal cual se
    # lo mandamos, así que ahí escondemos el empresa_id.
    token_aleatorio = secrets.token_urlsafe(24)
    state = f"{usuario['empresa_id']}.{token_aleatorio}"
    db.guardar_estado_oauth_shopify(usuario["empresa_id"], token_aleatorio)
    dominio = _dominio_shopify_normalizado(creds["shop_domain"])
    base_url = os.getenv("APP_BASE_URL", "https://tickets-ti-n4wn.onrender.com")
    redirect_uri = urllib.parse.quote(f"{base_url}/api/shopify/oauth/callback", safe="")
    url = (
        f"https://{dominio}/admin/oauth/authorize"
        f"?client_id={urllib.parse.quote(creds['client_id'])}"
        f"&scope={urllib.parse.quote(SHOPIFY_SCOPES)}"
        f"&redirect_uri={redirect_uri}"
        f"&state={urllib.parse.quote(state)}"
    )
    return {"url": url}


@app.get("/api/shopify/oauth/callback")
def api_callback_oauth_shopify(code: str, shop: str, state: str = ""):
    """Shopify redirige aquí después de que el admin autoriza — SIN login
    normal (viene del navegador redirigido por Shopify), por eso valida
    con el 'state' guardado en vez de con el JWT de la app. El empresa_id
    va escondido al inicio del 'state' (ver api_iniciar_oauth_shopify).

    Respaldo: si alguien instaló la app directo desde el botón "Instalar
    app" del Dev Dashboard de Shopify (en vez de nuestro link), Shopify no
    manda el 'state' que nosotros generamos — en ese caso identificamos la
    empresa por el dominio de la tienda, que ya tenemos guardado."""
    empresa_id = None
    if state and "." in state:
        try:
            empresa_id_str, token_aleatorio = state.split(".", 1)
            candidato = int(empresa_id_str)
            if db.verificar_y_limpiar_estado_oauth_shopify(candidato, token_aleatorio):
                empresa_id = candidato
        except (ValueError, IndexError):
            pass

    if empresa_id is None:
        empresa_id = db.obtener_empresa_id_por_shopify_domain(shop)

    if empresa_id is None:
        return Response(
            content="<h2>No se pudo identificar a qué empresa pertenece esta tienda. Ve a Administrar → Shopify, guarda el dominio correcto, y vuelve a intentar con el botón \"Conectar con Shopify\".</h2>",
            media_type="text/html", status_code=400,
        )

    creds = db.obtener_credenciales_oauth_shopify(empresa_id)
    if not creds:
        return Response(content="<h2>Faltan las credenciales de Shopify guardadas para esta empresa.</h2>", media_type="text/html", status_code=400)

    try:
        r = requests.post(
            f"https://{shop}/admin/oauth/access_token",
            json={"client_id": creds["client_id"], "client_secret": creds["client_secret"], "code": code},
            timeout=20,
        )
        r.raise_for_status()
        access_token = r.json()["access_token"]
    except Exception as e:
        return Response(content=f"<h2>Error canjeando el código de Shopify: {e}</h2>", media_type="text/html", status_code=400)

    db.guardar_access_token_shopify(empresa_id, access_token)
    return Response(
        content="<h2>✅ Shopify conectado correctamente.</h2><p>Ya puedes cerrar esta pestaña y regresar a tu app.</p>",
        media_type="text/html",
    )


@app.post("/api/shopify/probar-conexion")
def api_probar_conexion_shopify(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_shopify(usuario["empresa_id"])
    if not config:
        raise HTTPException(status_code=400, detail="Todavía no te has conectado con Shopify (dale 'Conectar con Shopify' primero).")
    ok, mensaje = shopify_api.probar_conexion(config)
    if not ok:
        raise HTTPException(status_code=400, detail=mensaje)
    return {"ok": True, "mensaje": mensaje}


@app.get("/api/laboratorio/{trabajo_id}")
def api_obtener_trabajo_laboratorio(trabajo_id: int, usuario: dict = Depends(requiere_ver_laboratorio)):
    trabajo = db.obtener_trabajo_laboratorio(usuario["empresa_id"], trabajo_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    _verificar_trabajo_laboratorio_del_estudiante(usuario, trabajo)
    if usuario["rol"] != "estudiante":
        trabajo["soy_laboratorio"] = _es_usuario_laboratorio(usuario)
    return trabajo


@app.get("/api/laboratorio/dscore/config")
def api_obtener_config_dscore(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_dscore_publica(usuario["empresa_id"])
    return config or {"base_host": None, "client_id": None, "tiene_client_secret": False, "conectado": False}


@app.post("/api/laboratorio/dscore/config")
def api_guardar_config_dscore(payload: ConfigDSCore, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_config_dscore(usuario["empresa_id"], payload.base_host.strip(), payload.client_id, payload.client_secret)
    return {"ok": True}


@app.get("/api/laboratorio/dscore/oauth/iniciar")
def api_iniciar_oauth_dscore(usuario: dict = Depends(requiere_admin_completo)):
    """Regresa la URL de login de DS Core a la que el navegador debe ir
    (el frontend hace window.location = esa URL) -- se conecta UNA sola
    vez como laboratorio, no un login por cada estudiante."""
    creds = db.obtener_credenciales_oauth_dscore(usuario["empresa_id"])
    if not creds:
        raise HTTPException(status_code=400, detail="Guarda primero el host y el Client ID de DS Core.")
    code_verifier, code_challenge = dscore.generar_pkce()
    token_aleatorio = secrets.token_urlsafe(24)
    state = f"{usuario['empresa_id']}.{token_aleatorio}"
    db.guardar_estado_oauth_dscore(usuario["empresa_id"], token_aleatorio, code_verifier)
    base_url = os.getenv("APP_BASE_URL", "https://tickets-ti-n4wn.onrender.com")
    redirect_uri = f"{base_url}/api/laboratorio/dscore/callback"
    url = dscore.armar_url_login(creds["base_host"], creds["client_id"], redirect_uri, code_challenge, state)
    return {"url": url}


@app.get("/api/laboratorio/dscore/callback")
def api_callback_oauth_dscore(code: str, state: str = ""):
    """DS Core redirige aquí después de que el admin autoriza -- SIN
    login normal (viene del navegador redirigido por DS Core), por eso
    valida con el 'state' guardado en vez del JWT de la app. El
    empresa_id va escondido al inicio del 'state' (ver
    api_iniciar_oauth_dscore), igual que con Shopify."""
    empresa_id = None
    code_verifier = None
    if state and "." in state:
        try:
            empresa_id_str, token_aleatorio = state.split(".", 1)
            candidato = int(empresa_id_str)
            verificado = db.verificar_y_limpiar_estado_oauth_dscore(candidato, token_aleatorio)
            if verificado:
                empresa_id = candidato
                code_verifier = verificado
        except (ValueError, IndexError):
            pass
    if empresa_id is None:
        return Response(
            content="<h2>No se pudo validar esta conexión (el enlace pudo haber expirado). Ve a Administrar → Laboratorio → DS Core y vuelve a intentar con el botón \"Conectar con DS Core\".</h2>",
            media_type="text/html", status_code=400,
        )
    creds = db.obtener_credenciales_oauth_dscore(empresa_id)
    if not creds:
        return Response(content="<h2>Faltan las credenciales de DS Core guardadas para esta empresa.</h2>", media_type="text/html", status_code=400)
    base_url = os.getenv("APP_BASE_URL", "https://tickets-ti-n4wn.onrender.com")
    redirect_uri = f"{base_url}/api/laboratorio/dscore/callback"
    try:
        access_token, refresh_token, expires_in = dscore.intercambiar_code_por_tokens(
            creds["client_id"], creds["client_secret"], redirect_uri, code, code_verifier,
        )
    except dscore.DSCoreError as e:
        return Response(content=f"<h2>Error canjeando el código de DS Core: {e}</h2>", media_type="text/html", status_code=400)
    expira_en = None
    if expires_in:
        expira_en = (db.ahora() + timedelta(seconds=int(expires_in) - 60)).isoformat(timespec="seconds")
    db.guardar_tokens_dscore(empresa_id, access_token, refresh_token, expira_en)
    return Response(
        content="<h2>✅ DS Core conectado correctamente.</h2><p>Ya puedes cerrar esta pestaña y regresar a tu app.</p>",
        media_type="text/html",
    )


@app.post("/api/laboratorio/dscore/desconectar")
def api_desconectar_dscore(usuario: dict = Depends(requiere_admin_completo)):
    db.desconectar_dscore(usuario["empresa_id"])
    return {"ok": True}


@app.post("/api/laboratorio/dscore/probar-conexion")
def api_probar_conexion_dscore(usuario: dict = Depends(requiere_admin_completo)):
    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])
    if not tokens:
        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale 'Conectar con DS Core' primero).")
    access_token = _access_token_dscore_vigente(usuario["empresa_id"])
    ok, mensaje = dscore.probar_conexion(tokens["base_host"], access_token)
    if not ok:
        raise HTTPException(status_code=400, detail=mensaje)
    return {"ok": True, "mensaje": mensaje}


@app.get("/api/laboratorio/dscore/debug-orders")
def api_debug_orders_dscore(usuario: dict = Depends(requiere_admin_completo)):
    """SOLO PARA DIAGNOSTICO (temporal) -- regresa tal cual lo que contesta
    DS Core en /v1beta/orders, para poder ver con un pedido real cómo se
    llama de verdad el campo del código legible y ajustar la búsqueda por
    código en consecuencia. Se puede quitar una vez resuelto."""
    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])
    if not tokens:
        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale 'Conectar con DS Core' primero).")
    access_token = _access_token_dscore_vigente(usuario["empresa_id"])
    try:
        return dscore.obtener_orders_crudo(tokens["base_host"], access_token, page_size=5)
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")


@app.get("/api/laboratorio/dscore/debug-file")
def api_debug_file_dscore(uri: str, usuario: dict = Depends(requiere_admin_completo)):
    """SOLO PARA DIAGNOSTICO (temporal) -- pide directamente el 'uri' de un
    archivo de un pedido (tomado del campo 'files' que ya vimos en
    /debug-orders, ej. 'digitalImpressions/dxd-...') para ver cómo lo
    expone DS Core de verdad (binario directo, JSON con link de descarga,
    etc.) antes de programar la descarga real de los escaneos STL
    originales del pedido. Se puede quitar una vez resuelto."""
    tokens = db.obtener_tokens_dscore(usuario["empresa_id"])
    if not tokens:
        raise HTTPException(status_code=400, detail="Todavía no te has conectado con DS Core (dale 'Conectar con DS Core' primero).")
    access_token = _access_token_dscore_vigente(usuario["empresa_id"])
    try:
        return dscore.obtener_archivo_crudo_diagnostico(tokens["base_host"], access_token, uri)
    except dscore.DSCoreError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar DS Core: {e}")


@app.get("/api/shopify/ventas")
def api_resumen_ventas_shopify(fecha_desde: str, fecha_hasta: str, usuario: dict = Depends(requiere_acceso_shopify)):
    config = db.obtener_config_shopify(usuario["empresa_id"])
    if not config:
        raise HTTPException(status_code=400, detail="Shopify no está configurado todavía para esta empresa (ve a Administrar → Shopify).")
    try:
        return shopify_api.obtener_resumen_ventas(config, fecha_desde, fecha_hasta)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Rastreo GPS en vivo (Geotab / A&T) ----

class ConfigGeotab(BaseModel):
    database: str = Field(min_length=1)
    usuario: str = Field(min_length=1)
    password: Optional[str] = None  # None = no cambiarla; "" = borrarla


@app.get("/api/geotab/config")
def api_obtener_config_geotab(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_geotab_publica(usuario["empresa_id"])
    return config or {"geotab_database": None, "geotab_usuario": None, "tiene_password": False}


@app.post("/api/geotab/config")
def api_guardar_config_geotab(payload: ConfigGeotab, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_config_geotab(usuario["empresa_id"], payload.database, payload.usuario, payload.password)
    return {"ok": True}


@app.post("/api/geotab/probar-conexion")
def api_probar_conexion_geotab(usuario: dict = Depends(requiere_admin_completo)):
    config = db.obtener_config_geotab(usuario["empresa_id"])
    try:
        dispositivos = geotab.listar_dispositivos(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "mensaje": f"Conexión exitosa — se encontraron {len(dispositivos)} vehículo(s)/unidad(es) en Geotab"}


@app.get("/api/geotab/dispositivos")
def api_listar_dispositivos_geotab(usuario: dict = Depends(requiere_ver_entregas)):
    """Para el selector 'Unidad GPS (Geotab)' al editar un vehículo de la flotilla."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede ver esto")
    config = db.obtener_config_geotab(usuario["empresa_id"])
    try:
        return geotab.listar_dispositivos(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ConfigLocationIQ(BaseModel):
    api_key: str = Field(min_length=1)


@app.get("/api/locationiq/config")
def api_obtener_config_locationiq(usuario: dict = Depends(requiere_admin_completo)):
    api_key = db.obtener_config_locationiq(usuario["empresa_id"])
    return {"tiene_api_key": bool(api_key)}


@app.post("/api/locationiq/config")
def api_guardar_config_locationiq(payload: ConfigLocationIQ, usuario: dict = Depends(requiere_admin_completo)):
    db.actualizar_config_locationiq(usuario["empresa_id"], payload.api_key)
    return {"ok": True}


@app.post("/api/locationiq/probar-conexion")
def api_probar_conexion_locationiq(usuario: dict = Depends(requiere_admin_completo)):
    api_key = db.obtener_config_locationiq(usuario["empresa_id"])
    if not api_key:
        raise HTTPException(status_code=400, detail="Todavía no guardas una llave de LocationIQ")
    lat, lng, motivo = geo.geocodificar("Ciudad de México", api_key)
    if lat is None:
        raise HTTPException(status_code=400, detail=f"La llave no funcionó — {motivo}")
    return {"ok": True, "mensaje": "Conexión exitosa con LocationIQ"}


@app.post("/api/entregas/{entrega_id}/liga-seguimiento")
def api_generar_liga_seguimiento(entrega_id: int, usuario: dict = Depends(requiere_ver_entregas)):
    """Crea (o regresa la ya existente) liga pública para que el cliente vea
    en un mapa dónde va su entrega en tiempo real — como el link de una app
    de comida a domicilio. No requiere que el cliente inicie sesión."""
    if usuario["rol"] == "instalador":
        raise HTTPException(status_code=403, detail="Un instalador no puede generar esta liga")
    token = db.generar_token_seguimiento_entrega(usuario["empresa_id"], entrega_id)
    if not token:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    return {"token": token}


@app.get("/api/seguimiento/{token}")
def api_seguimiento_publico(token: str):
    """Ruta PÚBLICA (sin login) — la abre el cliente desde la liga que se le
    manda. Regresa solo lo indispensable: nombre del cliente, qué se le va
    a entregar, el estado de la entrega, y la posición GPS actual del
    vehículo (si tiene una unidad Geotab asignada) — nada más de la empresa
    ni de otras entregas."""
    entrega = db.obtener_entrega_por_token_seguimiento(token)
    if not entrega:
        raise HTTPException(status_code=404, detail="Esta liga de seguimiento no es válida")

    posicion = None
    if entrega.get("geotab_device_id"):
        config = db.obtener_config_geotab(entrega["empresa_id"])
        try:
            posicion = geotab.obtener_posicion(config, entrega["geotab_device_id"])
        except Exception:
            posicion = None  # si Geotab falla, igual mostramos la entrega, solo sin el mapa

    return {
        "folio": entrega["folio"],
        "empresa_nombre": entrega["empresa_nombre"],
        "cliente_nombre": entrega["cliente_nombre"],
        "equipo_descripcion": entrega["equipo_descripcion"],
        "estado": entrega["estado"],
        "vehiculo_nombre": entrega.get("vehiculo_nombre"),
        "destino_lat": entrega.get("destino_lat"),
        "destino_lng": entrega.get("destino_lng"),
        "posicion_vehiculo": posicion,
    }


@app.get("/api/microsip/clientes")
def api_buscar_clientes_microsip(q: str, campo: str = "nombre", usuario: dict = Depends(requiere_ver_reparaciones)):
    """Búsqueda de clientes de Microsip por nombre o teléfono (parcial) —
    usada por el buscador (F4 / botón) al capturar los datos del cliente
    en una reparación."""
    _requiere_microsip_disponible()
    if campo not in ("nombre", "telefono"):
        raise HTTPException(status_code=400, detail="campo debe ser 'nombre' o 'telefono'")
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado todavía (Administrar → Microsip).")
    try:
        return microsip.buscar_clientes(config, q, campo=campo)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Checador de precio ----

def _config_microsip_o_error(usuario: dict):
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado todavía (Administrar → Microsip).")
    return config


@app.get("/api/checador-precio/clave/{clave}")
def api_checador_precio_por_clave(clave: str, usuario: dict = Depends(requiere_ver_checador_precio)):
    try:
        config = _config_microsip_o_error(usuario)
        resultado = microsip.buscar_producto_por_clave(config, clave)
        if resultado:
            resultado["fuente"] = "microsip_vivo"
    except Exception:
        # Microsip no respondió (túnel/ngrok caído, etc.) — se intenta con
        # el respaldo local de la última sincronización antes de rendirse.
        resultado = db.buscar_producto_cache_por_clave(usuario["empresa_id"], clave)
        if resultado:
            meta = db.obtener_meta_inventario_cache(usuario["empresa_id"])
            resultado["fuente"] = "respaldo_local"
            resultado["ultima_sincronizacion"] = meta["actualizado_en"] if meta else None
    if not resultado:
        raise HTTPException(status_code=404, detail=f"No se encontró ningún producto con la clave '{clave}'")
    return resultado


@app.get("/api/checador-precio/articulo/{articulo_id}")
def api_checador_precio_por_articulo(articulo_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    try:
        config = _config_microsip_o_error(usuario)
        resultado = microsip.buscar_producto_por_articulo_id(config, articulo_id)
        if resultado:
            resultado["fuente"] = "microsip_vivo"
    except Exception:
        resultado = db.buscar_producto_cache_por_articulo(usuario["empresa_id"], articulo_id)
        if resultado:
            meta = db.obtener_meta_inventario_cache(usuario["empresa_id"])
            resultado["fuente"] = "respaldo_local"
            resultado["ultima_sincronizacion"] = meta["actualizado_en"] if meta else None
    if not resultado:
        raise HTTPException(status_code=404, detail="No se encontró ese producto")
    return resultado


@app.get("/api/checador-precio/buscar")
def api_checador_precio_buscar(q: str, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Búsqueda de productos por nombre — botón de lupa cuando la
    clave/código de barras no dio resultado."""
    try:
        config = _config_microsip_o_error(usuario)
        return microsip.buscar_productos_por_nombre(config, q)
    except Exception:
        # Sin banner de "fuente" aquí porque es solo una lista para elegir
        # — el detalle que se abre después (por articulo_id) ya sí avisa.
        return db.buscar_productos_cache_por_nombre(usuario["empresa_id"], q)


# ---- Cotizador (dentro de Checador de precio) ----

class LeerImagenCotizacionIn(BaseModel):
    imagen_base64: str
    media_type: Optional[str] = "image/jpeg"
    nombre_archivo: Optional[str] = ""


class CotizacionItemIn(BaseModel):
    articulo_id: Optional[int] = None
    clave: Optional[str] = None
    nombre: str = Field(min_length=1)
    cantidad: float = Field(gt=0)
    precio_unitario: float = Field(ge=0)
    descuento_pct: float = Field(default=0, ge=0, le=100)
    nota: Optional[str] = None


class CotizacionIn(BaseModel):
    cliente_nombre: str = Field(min_length=1)
    cliente_direccion: Optional[str] = None
    cliente_telefono: Optional[str] = None
    folio_microsip_origen: Optional[str] = None
    notas: Optional[str] = None
    tipo_cliente: Literal["publico", "mayoreo", "distribuidor"] = "publico"
    meses_msi: Optional[int] = Field(default=None, ge=0, le=60)
    items: List[CotizacionItemIn] = Field(default_factory=list)
    # Solo las manda el Cotizador visual al CREAR: la foto del equipo ya
    # armado (JPG como Data URL) y qué se eligió. Al editar desde el
    # Cotizador normal no vienen, y la imagen guardada se respeta tal cual.
    imagen_visual: Optional[str] = None
    config_visual: Optional[dict] = None
    # Cliente del CRM elegido en la app de ventas (opcional).
    cliente_crm_id: Optional[int] = None
    # Flete de instalación calculado al cotizar (horas, km, CP destino…).
    flete: Optional[dict] = None
    # Envío por paquetería Estafeta elegido al cotizar (origen, CP, paquete, servicio…).
    envio: Optional[dict] = None


class EstatusCotizacionIn(BaseModel):
    estatus: Literal["creada", "viva", "posible_venta", "vendida", "perdida", "vencida"]


class SeguimientoCotizacionIn(BaseModel):
    fecha_seguimiento: Optional[str] = None


class PromocionItemIn(BaseModel):
    articulo_id: Optional[int] = None
    clave: Optional[str] = None
    nombre: str = Field(min_length=1)
    cantidad: float = Field(gt=0)
    precio_promocional: float = Field(ge=0)


class PromocionIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: Optional[str] = None
    imagen_base64: Optional[str] = None
    activa: bool = True
    items: List[PromocionItemIn] = Field(default_factory=list)


class GenerarImagenPromocionIn(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: Optional[str] = None
    items: List[PromocionItemIn] = Field(default_factory=list)
    fotos_referencia_base64: List[str] = Field(default_factory=list)


@app.post("/api/promociones/generar-imagen")
def api_generar_imagen_promocion(payload: GenerarImagenPromocionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Genera 3 variantes de imagen para la promoción con IA (Gemini),
    usando el nombre, artículos con su precio de promoción, la
    descripción libre del usuario sobre cómo quiere el diseño, y hasta 3
    fotos de referencia reales de los productos si se subieron."""
    if not payload.items:
        raise HTTPException(status_code=400, detail="Agrega al menos un artículo antes de generar la imagen")
    try:
        imagenes = imagen_ia.generar_imagenes_promocion(
            payload.nombre,
            [item.model_dump() for item in payload.items],
            payload.descripcion or "",
            payload.fotos_referencia_base64,
            empresa_id=usuario["empresa_id"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"imagenes": imagenes}


@app.get("/api/promociones")
def api_listar_promociones(activas: Optional[bool] = None, usuario: dict = Depends(requiere_ver_checador_precio)):
    return db.listar_promociones(usuario["empresa_id"], solo_activas=bool(activas))


@app.get("/api/promociones/{promocion_id}")
def api_obtener_promocion(promocion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    promo = db.obtener_promocion(usuario["empresa_id"], promocion_id)
    if not promo:
        raise HTTPException(status_code=404, detail="Promocion no encontrada")
    return promo


@app.post("/api/promociones")
def api_crear_promocion(payload: PromocionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    return db.crear_promocion(usuario["empresa_id"], usuario["id"], payload.nombre, payload.descripcion,
                               payload.imagen_base64, [item.model_dump() for item in payload.items])


@app.put("/api/promociones/{promocion_id}")
def api_actualizar_promocion(promocion_id: int, payload: PromocionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    resultado = db.actualizar_promocion(usuario["empresa_id"], promocion_id, payload.nombre, payload.descripcion,
                                         payload.imagen_base64, [item.model_dump() for item in payload.items], payload.activa)
    if not resultado:
        raise HTTPException(status_code=404, detail="Promocion no encontrada")
    return resultado


@app.delete("/api/promociones/{promocion_id}")
def api_eliminar_promocion(promocion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    if not db.eliminar_promocion(usuario["empresa_id"], promocion_id):
        raise HTTPException(status_code=404, detail="Promocion no encontrada")
    return {"ok": True}


class MensajeAsistenteIn(BaseModel):
    mensaje: str = Field(min_length=1)
    historial: List[dict] = Field(default_factory=list)


class NombreAsistenteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)


class ConocimientoAsistenteIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


@app.post("/api/asistente/mensaje")
def api_asistente_mensaje(payload: MensajeAsistenteIn, usuario: dict = Depends(requiere_acceso_asistente)):
    try:
        respuesta = asistente.responder(payload.mensaje, payload.historial, usuario["empresa_id"], usuario["rol"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"respuesta": respuesta}


@app.patch("/api/asistente/nombre")
def api_actualizar_nombre_asistente(payload: NombreAsistenteIn, usuario: dict = Depends(requiere_admin)):
    db.actualizar_nombre_asistente_ia(usuario["empresa_id"], payload.nombre)
    return {"ok": True}


@app.get("/api/asistente/saludo")
def api_asistente_saludo(usuario: dict = Depends(requiere_acceso_asistente)):
    """Saludo proactivo con pendientes reales (tareas de Proyectos,
    cotizaciones con seguimiento hoy) — None si no hay nada que avisar.
    No usa la API de Claude, así que no tiene costo por sí solo."""
    nombre = db.obtener_nombre_asistente_ia(usuario["empresa_id"])
    texto = asistente.saludo_proactivo(usuario["empresa_id"], usuario["id"], nombre)
    return {"saludo": texto}


@app.get("/api/asistente/conocimiento")
def api_listar_conocimiento_asistente(usuario: dict = Depends(requiere_admin)):
    return db.listar_conocimiento_asistente(usuario["empresa_id"])


@app.post("/api/asistente/conocimiento")
def api_crear_conocimiento_asistente(payload: ConocimientoAsistenteIn, usuario: dict = Depends(requiere_admin)):
    nuevo_id = db.crear_conocimiento_asistente(usuario["empresa_id"], payload.texto, usuario["id"])
    return {"id": nuevo_id}


@app.delete("/api/asistente/conocimiento/{conocimiento_id}")
def api_eliminar_conocimiento_asistente(conocimiento_id: int, usuario: dict = Depends(requiere_admin)):
    if not db.eliminar_conocimiento_asistente(usuario["empresa_id"], conocimiento_id):
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"ok": True}


@app.post("/api/cotizaciones/leer-imagen")
def api_cotizador_leer_imagen(payload: LeerImagenCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Lee una foto/imagen o un documento (PDF, Word, Excel, CSV) con
    Claude, extrae nombre+cantidad de cada artículo detectado, y busca
    coincidencias de cada uno en Microsip (mismo buscador multi-palabra
    del Cotizador), trayendo precio y existencia real para poder
    ordenarlas: primero las que sí tienen existencia disponible (de más
    barata a más cara), luego las que no tienen (también por precio)."""
    if len(payload.imagen_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    try:
        items_detectados = ia.leer_lista_de_archivo(payload.imagen_base64, payload.nombre_archivo or "", payload.media_type or "image/jpeg", usuario["empresa_id"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not items_detectados:
        return {"items": []}

    config = _config_microsip_o_error(usuario)
    resultado = []
    for it in items_detectados:
        try:
            candidatos_base = microsip.buscar_productos_por_nombre(config, it["nombre"], limite=5)
        except Exception:
            candidatos_base = []

        candidatos = []
        for c in candidatos_base:
            try:
                detalle = microsip.buscar_producto_por_articulo_id(config, c["articulo_id"])
            except Exception:
                detalle = None
            candidatos.append({
                "articulo_id": c["articulo_id"],
                "nombre": c["nombre"],
                "clave": c.get("clave"),
                "precio_con_impuesto": (detalle or {}).get("precio_con_impuesto"),
                "disponible_total": (detalle or {}).get("disponible_total") or 0,
            })
        # Primero los que sí tienen existencia (del más barato al más caro),
        # luego los que no tienen (también por precio) — así el primero de
        # la lista ya es "el más barato disponible", que es lo que se
        # preselecciona solo en la revisión.
        candidatos.sort(key=lambda c: (
            0 if (c["disponible_total"] or 0) > 0 else 1,
            c["precio_con_impuesto"] if c["precio_con_impuesto"] is not None else float("inf"),
        ))

        resultado.append({
            "texto_extraido": it["nombre"],
            "cantidad": it["cantidad"],
            "candidatos": candidatos,
        })
    return {"items": resultado}


@app.post("/api/promociones/leer-imagen")
def api_promocion_leer_imagen(payload: LeerImagenCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Como /api/cotizaciones/leer-imagen, pero para leer el anuncio/volante
    de una promoción: además de los artículos, saca un nombre sugerido para
    la promoción y el precio PROMOCIONAL de cada artículo (no el de
    Microsip) — cada artículo se busca en Microsip solo para traer su
    articulo_id/clave real, no su precio."""
    if len(payload.imagen_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo 5MB)")
    try:
        leido = ia.leer_promocion_de_archivo(payload.imagen_base64, payload.nombre_archivo or "", payload.media_type or "image/jpeg", usuario["empresa_id"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    items_detectados = leido["items"]
    if not items_detectados:
        return {"nombre_promocion": leido["nombre_promocion"], "items": []}

    config = _config_microsip_o_error(usuario)
    resultado = []
    for it in items_detectados:
        try:
            candidatos_base = microsip.buscar_productos_por_nombre(config, it["nombre"], limite=5)
        except Exception:
            candidatos_base = []

        candidatos = []
        for c in candidatos_base:
            try:
                detalle = microsip.buscar_producto_por_articulo_id(config, c["articulo_id"])
            except Exception:
                detalle = None
            candidatos.append({
                "articulo_id": c["articulo_id"],
                "nombre": c["nombre"],
                "clave": c.get("clave"),
                "precio_con_impuesto": (detalle or {}).get("precio_con_impuesto"),
                "disponible_total": (detalle or {}).get("disponible_total") or 0,
            })

        resultado.append({
            "texto_extraido": it["nombre"],
            "cantidad": it["cantidad"],
            "precio_promocional": it["precio_promocional"],
            "candidatos": candidatos,
        })
    return {"nombre_promocion": leido["nombre_promocion"], "items": resultado}


@app.get("/api/cotizaciones/microsip/{folio}")
def api_cotizador_buscar_microsip(folio: str, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Jala un documento de Microsip (cotización, pedido, o venta) con
    precio de lista por artículo, para empezar a armar la cotización."""
    config = _config_microsip_o_error(usuario)
    try:
        return microsip.buscar_cotizacion_microsip(config, folio)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@app.get("/api/cotizaciones")
def api_listar_cotizaciones(usuario: dict = Depends(requiere_ver_checador_precio)):
    # Igual que Tickets y Reparaciones: el rol "usuario" (empleado) solo ve
    # las cotizaciones que él mismo creó; los demás roles siguen viendo
    # todas las de la empresa.
    creado_por_id = usuario["id"] if usuario["rol"] == "usuario" else None
    return db.listar_cotizaciones(usuario["empresa_id"], creado_por_id)


@app.get("/api/cotizaciones/{cotizacion_id}")
def api_obtener_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")
    return cotizacion


@app.get("/api/cotizaciones/{cotizacion_id}/pdf")
def api_pdf_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")
    cotizacion["imagen_visual"] = db.obtener_imagen_visual_cotizacion(cotizacion_id)
    empresa = db.obtener_empresa(usuario["empresa_id"])
    diseno = db.obtener_plantilla_pdf(usuario["empresa_id"], "cotizacion")
    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, diseno)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"attachment; filename=cotizacion_{cotizacion['folio']}.pdf"})


# ---- Reportador: diseño configurable de PDFs (Fase 1: solo Cotizador) ----

TIPOS_DOCUMENTO_REPORTADOR = {
    "cotizacion": {
        "nombre": "Cotización (Cotizador)",
        "diseno_default": pdfs_cotizaciones.diseno_default_cotizacion,
        "nombres_bloques": pdfs_cotizaciones.NOMBRES_BLOQUES_COTIZACION,
    },
}


class DisenoPdfIn(BaseModel):
    config: dict


@app.get("/api/admin/plantillas-pdf")
def api_listar_tipos_plantillas_pdf(usuario: dict = Depends(requiere_admin_completo)):
    """Qué tipos de documento ya se pueden personalizar desde el Reportador."""
    return [{"tipo": t, "nombre": info["nombre"]} for t, info in TIPOS_DOCUMENTO_REPORTADOR.items()]


@app.get("/api/admin/plantillas-pdf/{tipo_documento}")
def api_obtener_plantilla_pdf(tipo_documento: str, usuario: dict = Depends(requiere_admin_completo)):
    info = TIPOS_DOCUMENTO_REPORTADOR.get(tipo_documento)
    if not info:
        raise HTTPException(status_code=404, detail="Ese tipo de documento todavía no es personalizable")
    guardado = db.obtener_plantilla_pdf(usuario["empresa_id"], tipo_documento)
    default = info["diseno_default"]()
    config = guardado if guardado is not None else default
    return {"config": config, "default": default, "nombres_bloques": info["nombres_bloques"]}


@app.put("/api/admin/plantillas-pdf/{tipo_documento}")
def api_guardar_plantilla_pdf(tipo_documento: str, payload: DisenoPdfIn, usuario: dict = Depends(requiere_admin_completo)):
    if tipo_documento not in TIPOS_DOCUMENTO_REPORTADOR:
        raise HTTPException(status_code=404, detail="Ese tipo de documento todavía no es personalizable")
    db.guardar_plantilla_pdf(usuario["empresa_id"], tipo_documento, payload.config, usuario["id"])
    return {"ok": True}


@app.post("/api/admin/plantillas-pdf/{tipo_documento}/vista-previa")
def api_vista_previa_plantilla_pdf(tipo_documento: str, payload: DisenoPdfIn, usuario: dict = Depends(requiere_admin_completo)):
    """Genera un PDF real con el diseño que se está editando (todavía sin
    guardar), usando la cotización más reciente de la empresa como
    muestra — o una de ejemplo si todavía no existe ninguna."""
    if tipo_documento != "cotizacion":
        raise HTTPException(status_code=404, detail="Ese tipo de documento todavía no es personalizable")
    empresa = db.obtener_empresa(usuario["empresa_id"])
    muestras = db.listar_cotizaciones(usuario["empresa_id"])
    if muestras:
        cotizacion = db.obtener_cotizacion(usuario["empresa_id"], muestras[0]["id"])
    else:
        cotizacion = {
            "folio": "EJEMPLO-001", "tipo_cliente": "publico", "creado_en": db.ahora().isoformat(timespec="seconds"),
            "cliente_nombre": "CLIENTE DE EJEMPLO", "cliente_telefono": "222 123 4567", "cliente_direccion": None,
            "items": [
                {"nombre": "ARTÍCULO DE EJEMPLO 1", "cantidad": 2, "precio_unitario": 1500, "descuento_pct": 10, "clave": "EJ-001", "nota": None},
                {"nombre": "ARTÍCULO DE EJEMPLO 2", "cantidad": 1, "precio_unitario": 3200, "descuento_pct": 0, "clave": None, "nota": "Nota de ejemplo"},
            ],
            "notas": "Estas son notas de ejemplo para la vista previa.",
            "vigencia_hasta": None, "meses_msi": 6,
            "creado_por_nombre": usuario.get("nombre") or usuario.get("nombre_completo"), "creador_telefono": None,
            "creador_sucursal_nombre": None, "creador_sucursal_telefonos": None,
        }
    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, payload.config)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": "inline; filename=vista_previa.pdf"})


@app.post("/api/cotizaciones/{cotizacion_id}/liga-impresion")
def api_generar_liga_impresion_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Genera la liga pública y corta que se le manda a la app Star PassPRNT
    (ella hace su propia petición HTTP para traer el recibo — no lleva el
    token de sesión de la app, así que necesita una ruta pública aparte)."""
    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")
    token = db.generar_token_impresion_cotizacion(usuario["empresa_id"], cotizacion_id)
    return {"token": token}


@app.get("/recibo-cotizacion/{token}")
def api_recibo_cotizacion_publico(token: str):
    """Ruta PÚBLICA (sin login) — la consulta directamente la app Star
    PassPRNT para traer el recibo a imprimir. Token corto, aleatorio, y de
    un solo uso por impresión (se regenera cada vez que se pide imprimir)."""
    cotizacion = db.obtener_cotizacion_por_token_impresion(token)
    if not cotizacion:
        return Response(content="<p>Esta liga de impresión ya no es válida — vuelve a la cotización e imprime de nuevo.</p>",
                         media_type="text/html; charset=utf-8", status_code=404)
    empresa = db.obtener_empresa(cotizacion["empresa_id"])
    datos_pago = (empresa or {}).get("datos_pago_cotizacion")
    html = pdfs_cotizaciones.generar_html_recibo_termico(cotizacion, datos_pago)
    return Response(content=html, media_type="text/html; charset=utf-8")


@app.get("/cotizacion-pdf/{token}")
def api_cotizacion_pdf_publico(token: str):
    """Ruta PÚBLICA (sin login) — el mismo token de /recibo-cotizacion/ pero
    para poder mandar la cotización en PDF por WhatsApp (el destinatario no
    tiene sesión en la app, necesita poder abrir la liga directo)."""
    cotizacion = db.obtener_cotizacion_por_token_impresion(token)
    if not cotizacion:
        return Response(content="Esta liga ya no es válida — vuelve a la cotización y genera el envío de nuevo.",
                         media_type="text/plain; charset=utf-8", status_code=404)
    cotizacion["imagen_visual"] = db.obtener_imagen_visual_cotizacion(cotizacion["id"])
    empresa = db.obtener_empresa(cotizacion["empresa_id"])
    diseno = db.obtener_plantilla_pdf(cotizacion["empresa_id"], "cotizacion")
    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, diseno)
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f"inline; filename=cotizacion_{cotizacion['folio']}.pdf"})


@app.patch("/api/cotizaciones/{cotizacion_id}/estatus")
def api_cambiar_estatus_cotizacion(cotizacion_id: int, payload: EstatusCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")
    if existente.get("oportunidad_id"):
        raise HTTPException(status_code=400, detail="Esta cotización viene de una oportunidad del CRM — su estatus se controla desde ahí, en el pipeline del CRM.")
    resultado = db.cambiar_estatus_cotizacion(usuario["empresa_id"], cotizacion_id, usuario["id"], payload.estatus)
    return resultado


@app.patch("/api/cotizaciones/{cotizacion_id}/seguimiento")
def api_programar_seguimiento_cotizacion(cotizacion_id: int, payload: SeguimientoCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")
    resultado = db.programar_seguimiento_cotizacion(usuario["empresa_id"], cotizacion_id, usuario["id"], payload.fecha_seguimiento)
    return resultado


@app.get("/api/cotizaciones/{cotizacion_id}/bitacora")
def api_bitacora_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")
    return db.listar_bitacora_cotizacion(usuario["empresa_id"], cotizacion_id)


@app.post("/api/cotizaciones")
def api_crear_cotizacion(payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    if payload.imagen_visual and len(payload.imagen_visual) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La imagen del equipo armado pesa demasiado (máximo ~5MB).")
    resultado = db.crear_cotizacion(
        usuario["empresa_id"], usuario["id"], payload.cliente_nombre, payload.cliente_direccion,
        payload.cliente_telefono, payload.folio_microsip_origen, payload.notas,
        [item.model_dump() for item in payload.items], payload.tipo_cliente, payload.meses_msi,
    )
    if payload.imagen_visual:
        db.guardar_imagen_visual_cotizacion(resultado["id"], payload.imagen_visual, payload.config_visual)
        resultado["tiene_imagen_visual"] = True
    if payload.flete and len(json.dumps(payload.flete)) < 4000:
        db.guardar_flete_json_cotizacion(usuario["empresa_id"], resultado["id"], payload.flete)
    if payload.envio and len(json.dumps(payload.envio)) < 4000:
        db.guardar_envio_json_cotizacion(usuario["empresa_id"], resultado["id"], payload.envio)
    if payload.cliente_crm_id:
        db.vincular_cotizacion_cliente_crm(usuario["empresa_id"], resultado["id"], payload.cliente_crm_id)
        resultado["cliente_crm_id"] = payload.cliente_crm_id
    return resultado


# ---- RH: Asistencia (reloj checador ZKTeco / BioTime Pro) ----

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
_POOL_ASISTENCIA = ThreadPoolExecutor(max_workers=2)

class ChecadasSyncIn(BaseModel):
    equipo: Optional[str] = None
    checadas: List[dict] = Field(default_factory=list, max_length=5000)


class ImportarChecadasIn(BaseModel):
    archivo: str = Field(min_length=10)
    nombre: Optional[str] = None


class HorarioIn(BaseModel):
    hora_entrada: str = Field(pattern=r"^\d{2}:\d{2}$")
    hora_salida: str = Field(pattern=r"^\d{2}:\d{2}$")
    dias: str = Field(pattern=r"^[1-7](,[1-7])*$")
    tolerancia_min: int = Field(ge=0, le=180)
    comida_min: int = Field(default=60, ge=0, le=240)


class HorarioUsuarioIn(BaseModel):
    horario: Optional[HorarioIn] = None   # None = usar el horario general


def _rango_fechas(desde: Optional[str], hasta: Optional[str]):
    hoy = db.ahora().date()
    try:
        d = date.fromisoformat(desde) if desde else hoy - timedelta(days=hoy.weekday())
        h = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas (usa AAAA-MM-DD).")
    if h < d:
        d, h = h, d
    if (h - d).days > 92:
        raise HTTPException(status_code=400, detail="El rango máximo es de 3 meses.")
    return d, h


def _horario_default(empresa_id):
    cfg = db.config_checador(empresa_id)
    return {**asistencia.HORARIO_DEFAULT, **(cfg.get("horario") or {})}


def _igual(a, b):
    return (a or "").strip().lower() == (b or "").strip().lower()


def _filtrar_reporte(reporte, empresa_id, checador=None, sucursal=None):
    """Para no traer a todos de golpe: solo un biométrico o una sucursal.
    Biométrico: quien checó en él en el rango, o es de la sucursal donde está ese checador.
    Sucursal: la gente de esa sucursal."""
    if not checador and not sucursal:
        return reporte
    if checador:
        k = next((x for x in db.listar_checadores_adms(empresa_id) if x["sn"] == checador), None) or {}
        suc_chk = k.get("sucursal")
        reporte["empleados"] = [e for e in reporte["empleados"]
                                if any(checador in (d.get("equipos") or []) or checador in (d.get("dispositivos") or []) for d in e["dias"])
                                or (suc_chk and _igual(e.get("sucursal"), suc_chk))]
        reporte["codigos_sin_empleado"] = [x for x in reporte["codigos_sin_empleado"] if x.get("sn") == checador]
    if sucursal:
        reporte["empleados"] = [e for e in reporte["empleados"] if _igual(e.get("sucursal"), sucursal)]
        reporte["codigos_sin_empleado"] = [x for x in reporte["codigos_sin_empleado"] if _igual(x.get("checador_sucursal"), sucursal)]
    reporte["filtro"] = {"checador": checador, "sucursal": sucursal}
    return reporte


def _reporte_asistencia(empresa_id, desde, hasta, solo_usuario_id=None, checador=None, sucursal=None):
    empleados = db.empleados_asistencia(empresa_id)
    # Las del checador de la app se toman directo de checador_app (abajo): así cuentan
    # también para quien no tiene número de empleado y se respeta la revisión de RH.
    checadas = [c for c in db.listar_checadas(empresa_id, desde, hasta) if c.get("origen") != "app"]
    # Checadores conectados directo (ADMS): la persona se identifica por (checador, número),
    # porque el mismo número puede ser otra persona en otro checador. Solo cuenta si RH la ligó.
    gente = db.mapa_gente_checador(empresa_id)
    con_numero = {e["id"] for e in empleados}
    # Checador de la app (selfie + ubicación): cuenta igual que el biométrico,
    # salvo las checadas que RH marcó como "no coincide".
    checadas_app = [x for x in db.listar_checadas_app(empresa_id, desde, hasta) if x.get("revision") != "no_coincide"]
    extra_ids = ({g["usuario_id"] for g in gente.values() if g.get("usuario_id")} | {x["usuario_id"] for x in checadas_app}) - con_numero
    sin_numero_ids = set()
    for u in db.usuarios_por_ids(empresa_id, extra_ids):
        u["numero_empleado"] = f"U{u['id']}"
        sin_numero_ids.add(u["id"])
        empleados.append(u)
    codigo_de_usuario = {e["id"]: asistencia.normalizar_codigo(e["numero_empleado"]) for e in empleados}
    # Checadas que no vienen de un checador directo (BioTime / archivo): número de empleado o equivalencia de RH.
    ligados = db.codigos_checador(empresa_id)
    equivalencias = {asistencia.normalizar_codigo(x["codigo"]): asistencia.normalizar_codigo(x["numero_empleado"])
                     for x in ligados if (x.get("numero_empleado") or "").strip()}
    nombres_chk = db.nombres_checador(empresa_id)
    claves_directas = {}
    for c in checadas:
        c["codigo"] = asistencia.normalizar_codigo(c["codigo"])
        if c.get("origen") == "adms" and c.get("equipo"):
            g = gente.get((c["equipo"], c["codigo"])) or {}
            uid = g.get("usuario_id")
            if uid and uid in codigo_de_usuario:
                c["codigo"] = codigo_de_usuario[uid]
            else:
                clave = f"{c['equipo']}:{c['codigo']}"
                claves_directas[clave] = {"sn": c["equipo"], "codigo_checador": c["codigo"], "gente_id": g.get("id")}
                c["codigo"] = clave
                c["nombre"] = g.get("nombre") or c.get("nombre")
            continue
        if not c.get("nombre") and nombres_chk.get(c["codigo"]):
            c["nombre"] = nombres_chk[c["codigo"]]
        c["codigo"] = equivalencias.get(c["codigo"], c["codigo"])
    for x in checadas_app:
        cod = codigo_de_usuario.get(x["usuario_id"])
        if cod:
            checadas.append({"codigo": cod, "fecha_hora": x["fecha_hora"], "dispositivo": "📱 App",
                             "equipo": "APP", "origen": "app", "nombre": x.get("nombre_completo")})
    if solo_usuario_id:
        empleados = [e for e in empleados if e["id"] == solo_usuario_id]
    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)
    avisos = []
    # Vacaciones aprobadas en Microsip (si la empresa lo tiene conectado)
    try:
        config = db.obtener_config_microsip(empresa_id)
        numeros = [e["numero_empleado"] for e in empleados]
        if numeros and config and config.get("microsip_host"):
            por_numero = {asistencia.normalizar_codigo(e["numero_empleado"]): e["id"] for e in empleados}
            # Máximo 8 segundos: si Microsip no contesta, el reporte sale igual (sin esas vacaciones).
            futuro = _POOL_ASISTENCIA.submit(microsip.obtener_vacaciones_multiples_empleados, config, numeros)
            try:
                vacaciones = futuro.result(timeout=8)
            except FuturesTimeout:
                vacaciones = []
                avisos.append("Microsip no respondió a tiempo: las vacaciones de Microsip no se tomaron en cuenta como faltas justificadas.")
            for v in vacaciones:
                uid = por_numero.get(asistencia.normalizar_codigo(v.get("numero_empleado")))
                a = asistencia.a_fecha(v.get("fecha_inicial"))
                b = asistencia.a_fecha(v.get("fecha_fin")) or a
                if uid and a:
                    justificaciones.setdefault(uid, []).append((a, b, "Vacaciones (Microsip)"))
    except Exception as e:
        print(f"[asistencia] vacaciones de Microsip no disponibles: {e}")
        avisos.append("No se pudieron consultar las vacaciones de Microsip.")
    reporte = asistencia.calcular_reporte(empleados, checadas, db.horarios_asistencia(empresa_id),
                                       _horario_default(empresa_id), desde, hasta, db.ahora().date(), justificaciones,
                                       db.primera_checada(empresa_id), db.horarios_sucursal_asistencia(empresa_id))
    reporte["avisos"] = avisos
    reporte["codigos_ligados"] = ligados
    checadores = {k["sn"]: k for k in db.listar_checadores_adms(empresa_id)}
    for x in reporte["codigos_sin_empleado"]:
        extra = claves_directas.get(x["codigo"])
        if extra:
            k = checadores.get(extra["sn"]) or {}
            x.update(extra, checador=k.get("nombre") or extra["sn"], checador_sucursal=k.get("sucursal"))
    for e in reporte["empleados"]:
        if e["usuario_id"] in sin_numero_ids:
            e["numero_empleado"] = None
    # Checadores fuera de línea: esas "faltas" se marcan "sin conexión del checador".
    conexion = db.estado_conexion_checadores(empresa_id)
    reporte["conexion_checadores"] = conexion
    if conexion:
        chk_de_usuario = {}
        for (sn, _cod), g in gente.items():
            if g.get("usuario_id"):
                chk_de_usuario.setdefault(g["usuario_id"], set()).add(sn)
        asistencia.marcar_sin_conexion(reporte, conexion, chk_de_usuario)
    return _filtrar_reporte(reporte, empresa_id, checador, sucursal)



# ==================== RH sin Microsip (ej. Peymar) ====================
# Solo para empresas con rh_sin_microsip = TRUE (Superadmin → Módulos). RH da
# de alta al personal (No. de empleado = el de los biométricos), el
# administrador le da usuario para la app, y RH lleva la nómina semanal
# (lunes a domingo) con lo que marca el checador.

def _requiere_rh_sin_microsip(usuario):
    if not db.config_rh_empresa(usuario["empresa_id"])["rh_sin_microsip"]:
        raise HTTPException(status_code=403, detail="Esta empresa lleva su personal en Microsip.")


def _numero_limpio(numero):
    n = re.sub(r"\s+", "", str(numero or ""))
    if not n.isdigit():
        raise HTTPException(status_code=400, detail="El No. de empleado debe ser solo números (es el que se usa en los biométricos).")
    n = n.lstrip("0") or "0"
    if len(n) > 9:
        raise HTTPException(status_code=400, detail="El No. de empleado es demasiado largo.")
    return n


def _antiguedad(fecha_ingreso):
    """(años cumplidos, días de vacaciones que le tocan en su año actual según la LFT)."""
    try:
        ingreso = date.fromisoformat(str(fecha_ingreso)[:10])
    except Exception:
        return None, None
    anios = max(0, (db.ahora().date() - ingreso).days) // 365
    return anios, db.dias_vacaciones_lft(max(1, anios + 1))


def _con_datos_personal(p):
    anios, dias = _antiguedad(p.get("fecha_ingreso"))
    p["antiguedad_anios"] = anios
    p["vacaciones_dias_por_ley"] = dias
    saldo = _saldo_vacaciones_ajustado({"id": p["id"], "fecha_ingreso_ajustada": p.get("fecha_ingreso"),
                                        "vacaciones_tomadas_previas": p.get("vacaciones_tomadas_previas")}, 0.0) if p.get("fecha_ingreso") else None
    if saldo:
        saldo.pop("registros_app", None)
    p["vacaciones"] = saldo
    if not p.get("acceso_app", True):
        p["username"] = None  # el usuario interno no sirve para entrar
    p["edad"] = None
    if p.get("fecha_nacimiento"):
        try:
            n, hoy = date.fromisoformat(p["fecha_nacimiento"][:10]), db.ahora().date()
            p["edad"] = hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day))
        except ValueError:
            pass
    return p


class PersonalRHIn(BaseModel):
    nombre_completo: Optional[str] = Field(default=None, max_length=150)
    numero_empleado: Optional[str] = None
    puesto: Optional[str] = Field(default=None, max_length=120)
    departamento: Optional[str] = None
    sucursal_id: Optional[int] = None
    fecha_ingreso: Optional[str] = None
    sueldo_semanal: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    telefono_whatsapp: Optional[str] = None
    rfc: Optional[str] = None
    curp: Optional[str] = None
    # Expediente (lo que trae la base de RH de Peymar).
    email: Optional[str] = Field(default=None, max_length=150)
    nss: Optional[str] = Field(default=None, max_length=20)
    numero_ine: Optional[str] = Field(default=None, max_length=40)
    fecha_nacimiento: Optional[str] = None
    estado_civil: Optional[str] = Field(default=None, max_length=40)
    bono_semanal: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    seguro_imss: Optional[str] = Field(default=None, max_length=40)
    fecha_alta_imss: Optional[str] = None
    razon_social: Optional[str] = Field(default=None, max_length=150)
    jefe_directo: Optional[str] = Field(default=None, max_length=150)
    # Días de vacaciones que le quedan HOY (si ya tenía antigüedad antes del sistema).
    # Vacío = todos los que le tocan por ley desde su ingreso.
    vacaciones_disponibles_hoy: Optional[float] = Field(default=None, ge=0, le=400)
    # Al dar de alta (o al cambiarle el nombre): mandarlo a los checadores conectados.
    pasar_a_checadores: Optional[bool] = None


def _pasar_a_checadores(empresa_id, persona, quien_id):
    """Da de alta (o actualiza el nombre de) la persona en TODOS los checadores
    conectados de la empresa, con su No. de empleado. Después solo se registra la
    cara o la huella en el checador. No toca a nadie más: si en un checador ese
    número ya es de otra persona ligada, ese checador se salta y se avisa."""
    checadores, gente, _ = db.datos_red_checadores(empresa_id)
    pin = asistencia.normalizar_codigo(persona.get("numero_empleado"))
    enviados, omitidos = [], []
    if not checadores:
        return {"enviados": [], "omitidos": [], "sin_checadores": True}
    if not pin.isdigit():
        return {"enviados": [], "omitidos": ["Su No. de empleado debe ser solo números para los checadores."], "sin_checadores": False}
    for k in checadores:
        nom_chk = k.get("nombre") or k["sn"]
        otro_numero = next((g for g in gente if g["sn"] == k["sn"] and g.get("usuario_id") == persona["id"]
                            and g["codigo"] != pin and not g.get("baja_en")), None)
        if otro_numero:
            omitidos.append(f"{nom_chk}: ahí ya está con el No. {otro_numero['codigo']} (para cambiárselo usa «Poner el No. de empleado» "
                            "en Asistencia → 🔌 Conexión checadores, así conserva su cara y huellas)")
            continue
        actual = next((g for g in gente if g["sn"] == k["sn"] and g["codigo"] == pin and not g.get("baja_en")), None)
        if actual and actual.get("usuario_id") not in (None, persona["id"]):
            omitidos.append(f"{nom_chk}: el No. {pin} ya lo tiene {actual.get('usuario_nombre') or actual.get('nombre') or 'otra persona'}")
            continue
        db.encolar_comando_checador(k["sn"], asistencia.comando_alta_usuario(actual.get("datos_usuario") if actual else None, pin,
                                                                             persona["nombre_completo"]))
        db.alta_gente_sin_foto(empresa_id, k["sn"], pin, persona["id"], persona["nombre_completo"], quien_id)
        enviados.append(nom_chk)
    return {"enviados": enviados, "omitidos": omitidos, "sin_checadores": False}


def _tomadas_previas(usuario_id, fecha_ingreso, disponibles_hoy):
    """Cuántos días 'ya tomados antes' hay que registrar para que hoy le queden disponibles_hoy."""
    otorgados = db.dias_correspondientes_lft_acumulado(fecha_ingreso)
    registros = db.listar_vacaciones_ajuste_usuario(usuario_id) if usuario_id else []
    app_aprob = sum(float(r["dias"]) for r in registros if r["estado"] == "aprobada")
    app_pend = sum(float(r["dias"]) for r in registros if r["estado"] == "pendiente")
    previas = otorgados - app_aprob - app_pend - float(disponibles_hoy)
    if previas < 0:
        raise HTTPException(status_code=400, detail=f"Por su antigüedad le tocan {otorgados:g} días en total: no le pueden quedar {float(disponibles_hoy):g}.")
    return round(previas, 1)


def _validar_personal(usuario, datos: dict, excluir_id=None):
    if "nombre_completo" in datos:
        datos["nombre_completo"] = (datos["nombre_completo"] or "").strip()
        if len(datos["nombre_completo"]) < 3:
            raise HTTPException(status_code=400, detail="Escribe el nombre completo.")
    if "numero_empleado" in datos:
        datos["numero_empleado"] = _numero_limpio(datos["numero_empleado"])
        otro = db.numero_empleado_ocupado(usuario["empresa_id"], datos["numero_empleado"], excluir_id)
        if otro:
            raise HTTPException(status_code=400, detail=f"El No. {datos['numero_empleado']} ya lo tiene {otro['nombre_completo']}.")
    if datos.get("fecha_ingreso"):
        try:
            f = date.fromisoformat(datos["fecha_ingreso"][:10])
        except Exception:
            raise HTTPException(status_code=400, detail="Fecha de ingreso inválida.")
        if f > db.ahora().date():
            raise HTTPException(status_code=400, detail="La fecha de ingreso no puede ser futura.")
        datos["fecha_ingreso"] = f.isoformat()
    if datos.get("departamento"):
        validos = {d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])}
        if datos["departamento"] not in validos:
            raise HTTPException(status_code=400, detail="Ese departamento no existe.")
    if datos.get("sucursal_id") and not db.obtener_sucursal_reparacion(usuario["empresa_id"], datos["sucursal_id"]):
        raise HTTPException(status_code=404, detail="Esa nave no existe.")
    for k in ("puesto", "telefono_whatsapp", "rfc", "curp", "departamento", "email", "nss", "numero_ine", "estado_civil",
              "seguro_imss", "razon_social", "jefe_directo"):
        if k in datos and isinstance(datos[k], str):
            datos[k] = datos[k].strip() or None
    for k in ("rfc", "curp", "numero_ine"):
        if datos.get(k):
            datos[k] = datos[k].upper().replace(" ", "")
    if datos.get("email") and "@" not in datos["email"]:
        raise HTTPException(status_code=400, detail="El correo no es válido.")
    for k, txt in (("fecha_nacimiento", "nacimiento"), ("fecha_alta_imss", "alta en el IMSS")):
        if datos.get(k):
            try:
                datos[k] = date.fromisoformat(datos[k][:10]).isoformat()
            except Exception:
                raise HTTPException(status_code=400, detail=f"Fecha de {txt} inválida.")
        elif k in datos:
            datos[k] = None
    return datos


def _naves_con_departamentos(empresa_id):
    deptos = db.departamentos_por_sucursal(empresa_id)
    return [{"id": s["id"], "nombre": s["nombre"], "departamentos": deptos.get(s["id"], [])}
            for s in db.listar_sucursales_reparacion(empresa_id, solo_activas=True)]


@app.get("/api/rh/personal")
def api_personal_rh(bajas: bool = False, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    personal = [_con_datos_personal(p) for p in db.listar_personal_rh(usuario["empresa_id"], incluir_bajas=bajas)]
    return {
        "personal": personal,
        "naves": _naves_con_departamentos(usuario["empresa_id"]),
        "departamentos": [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])],
        "puestos": sorted({p["puesto"] for p in personal if p.get("puesto")}),
        "siguiente_numero": db.siguiente_numero_empleado(usuario["empresa_id"]),
        "checadores": [k.get("nombre") or k["sn"] for k in db.listar_checadores_adms(usuario["empresa_id"])
                       if k.get("empresa_id") == usuario["empresa_id"] and k.get("activo")],
    }


@app.post("/api/rh/personal")
def api_alta_personal_rh(payload: PersonalRHIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Alta de un trabajador. Queda sin usuario para la app: el administrador se lo da después."""
    _requiere_rh_sin_microsip(usuario)
    datos = payload.model_dump()
    pasar = datos.pop("pasar_a_checadores", None) is not False
    # Sin número = el siguiente consecutivo (David, 20 oct 2026).
    if not str(datos.get("numero_empleado") or "").strip():
        datos["numero_empleado"] = db.siguiente_numero_empleado(usuario["empresa_id"])
    if not datos.get("nombre_completo") or not datos.get("fecha_ingreso"):
        raise HTTPException(status_code=400, detail="Faltan datos: nombre y fecha de ingreso son obligatorios.")
    datos = _validar_personal(usuario, datos)
    disponibles = datos.pop("vacaciones_disponibles_hoy", None)
    if disponibles is not None:
        datos["vacaciones_tomadas_previas"] = _tomadas_previas(None, datos["fecha_ingreso"], disponibles)
    uid = db.crear_personal_rh(usuario["empresa_id"], datos)
    persona = db.obtener_personal_rh(usuario["empresa_id"], uid)
    r = _con_datos_personal(persona)
    if pasar:
        r["checadores_alta"] = _pasar_a_checadores(usuario["empresa_id"], persona, usuario["id"])
    return r


@app.put("/api/rh/personal/{usuario_id}")
def api_editar_personal_rh(usuario_id: int, payload: PersonalRHIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    if not db.obtener_personal_rh(usuario["empresa_id"], usuario_id):
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    datos = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    datos.pop("pasar_a_checadores", None)
    antes = db.obtener_personal_rh(usuario["empresa_id"], usuario_id)
    if "numero_empleado" in datos and not datos["numero_empleado"]:
        raise HTTPException(status_code=400, detail="El No. de empleado no puede quedar vacío.")
    datos = _validar_personal(usuario, datos, excluir_id=usuario_id)
    disponibles = datos.pop("vacaciones_disponibles_hoy", None)
    if disponibles is not None:
        fecha = datos.get("fecha_ingreso") or db.obtener_personal_rh(usuario["empresa_id"], usuario_id).get("fecha_ingreso")
        if not fecha:
            raise HTTPException(status_code=400, detail="Primero pon su fecha de ingreso.")
        datos["vacaciones_tomadas_previas"] = _tomadas_previas(usuario_id, fecha, disponibles)
    db.actualizar_personal_rh(usuario["empresa_id"], usuario_id, datos)
    despues = db.obtener_personal_rh(usuario["empresa_id"], usuario_id)
    r = _con_datos_personal(despues)
    en_checadores = db.gente_de_usuario(usuario["empresa_id"], usuario_id)
    if en_checadores:
        mismo_numero = asistencia.normalizar_codigo(antes.get("numero_empleado")) == asistencia.normalizar_codigo(despues.get("numero_empleado"))
        if not mismo_numero:
            r["aviso_checadores"] = ("Le cambiaste el No.: en los checadores sigue con el anterior. Para pasarlo con sus huellas y "
                                     "caras usa Asistencia → 🔌 Conexión checadores → «Poner el No. de empleado».")
        elif antes.get("nombre_completo") != despues.get("nombre_completo"):
            r["checadores_alta"] = _pasar_a_checadores(usuario["empresa_id"], despues, usuario["id"])
    return r


@app.post("/api/rh/personal/{usuario_id}/checadores")
def api_personal_a_checadores(usuario_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Manda a la persona (No. y nombre) a todos los checadores conectados."""
    _requiere_rh_sin_microsip(usuario)
    p = db.obtener_personal_rh(usuario["empresa_id"], usuario_id)
    if not p or not p.get("activo"):
        raise HTTPException(status_code=404, detail="Persona no encontrada o dada de baja")
    if not p.get("numero_empleado"):
        raise HTTPException(status_code=400, detail="Primero ponle su No. de empleado.")
    r = _pasar_a_checadores(usuario["empresa_id"], p, usuario["id"])
    if r.get("sin_checadores"):
        raise HTTPException(status_code=400, detail="No hay checadores conectados: da de alta el checador en Asistencia → 🔌 Conexión checadores.")
    return r


@app.post("/api/rh/personal/a-checadores")
def api_todo_personal_a_checadores(simular: bool = False, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Manda a los checadores conectados a TODO el personal activo con No. que todavía no
    está en ninguno (para cuando se conectan checadores nuevos después de cargar al personal).
    A quien ya está ligado en algún checador no se le toca. simular=True solo cuenta."""
    _requiere_rh_sin_microsip(usuario)
    empresa_id = usuario["empresa_id"]
    checadores, gente, _ = db.datos_red_checadores(empresa_id)
    if not checadores:
        raise HTTPException(status_code=400, detail="No hay checadores conectados: da de alta el checador en Asistencia → 🔌 Conexión checadores.")
    ligados = {g["usuario_id"] for g in gente if g.get("usuario_id") and not g.get("baja_en")}
    pendientes = [p for p in db.listar_personal_rh(empresa_id)
                  if p.get("numero_empleado") and p["id"] not in ligados and str(p["numero_empleado"]).strip().isdigit()]
    # Sin ligar en el checador pero con nombre parecido: mejor ligarlos primero (no duplicar).
    sin_ligar = [g for g in gente if not g.get("usuario_id") and not g.get("baja_en")]
    if simular:
        return {"pendientes": len(pendientes), "checadores": [k.get("nombre") or k["sn"] for k in checadores],
                "sin_ligar_en_checadores": len(sin_ligar)}
    enviados, avisos = 0, []
    for p in pendientes:
        r = _pasar_a_checadores(empresa_id, p, usuario["id"])
        if r.get("enviados"):
            enviados += 1
        avisos += [f"{p['nombre_completo']}: {o}" for o in r.get("omitidos", [])]
    return {"enviados": enviados, "avisos": avisos[:50]}


class BajaPersonalIn(BaseModel):
    fecha: Optional[str] = None
    motivo: str = Field(min_length=3, max_length=300)
    quitar_de_checadores: bool = True


@app.post("/api/rh/personal/{usuario_id}/baja")
def api_baja_personal_rh(usuario_id: int, payload: BajaPersonalIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    p = db.obtener_personal_rh(usuario["empresa_id"], usuario_id)
    if not p:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    if usuario_id == usuario["id"]:
        raise HTTPException(status_code=400, detail="No puedes darte de baja a ti misma.")
    db.baja_personal_rh(usuario["empresa_id"], usuario_id, (payload.fecha or db.ahora().date().isoformat())[:10], payload.motivo.strip())
    checadores = 0
    if payload.quitar_de_checadores:
        for g in db.gente_de_usuario(usuario["empresa_id"], usuario_id):
            r = db.baja_gente_checador(usuario["empresa_id"], g["id"])
            if r:
                db.encolar_comando_checador(r["sn"], f"DATA DELETE USERINFO PIN={r['codigo']}")
                checadores += 1
    return {"ok": True, "checadores": checadores}


@app.post("/api/rh/personal/{usuario_id}/reactivar")
def api_reactivar_personal_rh(usuario_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    p = db.obtener_personal_rh(usuario["empresa_id"], usuario_id)
    if not p:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    if p.get("numero_empleado"):
        otro = db.numero_empleado_ocupado(usuario["empresa_id"], p["numero_empleado"], usuario_id)
        if otro:
            raise HTTPException(status_code=400, detail=f"Su No. {p['numero_empleado']} ya lo tiene {otro['nombre_completo']}: cámbialo antes de reactivar.")
    db.reactivar_personal_rh(usuario["empresa_id"], usuario_id)
    return _con_datos_personal(db.obtener_personal_rh(usuario["empresa_id"], usuario_id))


class ImportarPersonalIn(BaseModel):
    archivo_base64: str = Field(max_length=40_000_000)
    hoja: Optional[str] = None
    aplicar: bool = False
    # Los que NO están en ningún checador: mandarlos con su No. nuevo (después se registra cara/huella).
    pasar_a_checadores: bool = False


@app.post("/api/rh/personal/importar")
def api_importar_personal_rh(payload: ImportarPersonalIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Importa la base de personal (Excel). aplicar=false → solo la vista previa.
    A quien ya está en un checador se le deja el MISMO número y se liga (sin tocar
    su cara/huella); a los demás, el siguiente consecutivo."""
    _requiere_rh_sin_microsip(usuario)
    import importar_personal
    try:
        contenido = base64.b64decode(payload.archivo_base64.split(",", 1)[-1])
        filas, hoja, hojas, columnas = importar_personal.leer_excel(contenido, payload.hoja)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="No pude leer el archivo: debe ser un Excel (.xlsx) sin contraseña.")
    empresa_id = usuario["empresa_id"]

    def armar():
        checadores, gente, _ = db.datos_red_checadores(empresa_id)
        nombres_chk = {k["sn"]: k.get("nombre") or k["sn"] for k in checadores}
        gente_act = [{**g, "checador": nombres_chk[g["sn"]]} for g in gente if not g.get("baja_en") and g["sn"] in nombres_chk]
        # Con los departamentos desactivados también: si ya existe uno igual, se reactiva (no se duplica).
        return importar_personal.planear(filas, db.listar_personal_rh(empresa_id, incluir_bajas=True), gente_act,
                                         db.siguiente_numero_empleado(empresa_id),
                                         [d["nombre"] for d in db.listar_departamentos(empresa_id, solo_activos=False)])

    plan = armar()
    plan.update({"hoja": hoja, "hojas": hojas, "columnas": columnas})
    if not payload.aplicar:
        return plan
    existentes = {d["nombre"]: d for d in db.listar_departamentos(empresa_id, solo_activos=False)}
    for d in plan["departamentos_nuevos"]:
        if d not in existentes:
            try:
                db.crear_departamento(empresa_id, d)
            except Exception:  # noqa: BLE001  (ya existía con otra mayúscula/espacio)
                pass
    usados = {r["datos"].get("departamento") for r in plan["renglones"] if r.get("datos")}
    for nombre, d in existentes.items():
        if nombre in usados and not d.get("activo", True):
            db.cambiar_estado_departamento(empresa_id, d["id"], True)
    # Todos entran sin usuario de app (acceso_app = FALSE): una sola contraseña al azar
    # que nadie conoce, para no tardar ~0.3 s por persona calculándola.
    hash_sin_acceso = auth.hash_password(secrets.token_urlsafe(32))
    hechos = {"nuevos": 0, "actualizados": 0, "ligados": 0, "a_checadores": 0, "errores": []}
    for r in plan["renglones"]:
        if r["accion"] == "omitir":
            continue
        try:
            datos = dict(r["datos"])
            if r["accion"] == "nuevo":
                datos["numero_empleado"] = r["numero"]
                uid = db.crear_personal_rh(empresa_id, datos, password_hash=hash_sin_acceso)
                hechos["nuevos"] += 1
            else:
                uid = r["usuario_id"]
                cambios = {k: datos[k] for k in r["cambios"] if k in datos}
                actual = db.obtener_personal_rh(empresa_id, uid)
                if not str(actual.get("numero_empleado") or "").strip():
                    cambios["numero_empleado"] = r["numero"]
                if cambios:
                    db.actualizar_personal_rh(empresa_id, uid, cambios)
                    hechos["actualizados"] += 1
            persona = db.obtener_personal_rh(empresa_id, uid)
            for l in r["ligar"]:
                if db.ligar_gente_a_usuario(empresa_id, l["sn"], l["codigo"], uid, persona["nombre_completo"], usuario["id"]):
                    hechos["ligados"] += 1
            if payload.pasar_a_checadores and not r["checadores"] and persona.get("activo"):
                res = _pasar_a_checadores(empresa_id, persona, usuario["id"])
                if res.get("enviados"):
                    hechos["a_checadores"] += 1
        except Exception as e:  # noqa: BLE001
            hechos["errores"].append(f"Renglón {r['fila']} ({r['nombre']}): {e}")
    return {**hechos, "departamentos_nuevos": plan["departamentos_nuevos"]}


class NaveIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)


@app.post("/api/rh/naves")
def api_crear_nave(payload: NaveIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    nombre = payload.nombre.strip()
    if any(s["nombre"].strip().lower() == nombre.lower() for s in db.listar_sucursales_reparacion(usuario["empresa_id"])):
        raise HTTPException(status_code=400, detail="Ya existe una con ese nombre.")
    prefijo = (re.sub(r"[^A-Za-z0-9]", "", nombre).upper() or "NAVE")[:10]
    sid = db.crear_sucursal_reparacion(usuario["empresa_id"], nombre, prefijo)
    return {"id": sid, "naves": _naves_con_departamentos(usuario["empresa_id"])}


class DepartamentosNaveIn(BaseModel):
    departamentos: List[str] = []


@app.put("/api/rh/naves/{sucursal_id}/departamentos")
def api_departamentos_nave(sucursal_id: int, payload: DepartamentosNaveIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    validos = {d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])}
    malos = [d for d in payload.departamentos if d not in validos]
    if malos:
        raise HTTPException(status_code=400, detail=f"No existen: {', '.join(malos)}")
    try:
        db.guardar_departamentos_sucursal(usuario["empresa_id"], sucursal_id, payload.departamentos)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"naves": _naves_con_departamentos(usuario["empresa_id"])}


@app.post("/api/rh/departamentos")
def api_rh_crear_departamento(payload: NaveIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """RH también puede dar de alta departamentos (en empresas sin Microsip)."""
    _requiere_rh_sin_microsip(usuario)
    try:
        db.crear_departamento(usuario["empresa_id"], payload.nombre.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Ese departamento ya existe")
    return {"departamentos": [d["nombre"] for d in db.listar_departamentos(usuario["empresa_id"])]}


class AccesoAppIn(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=6, max_length=100)


@app.post("/api/usuarios/{usuario_id}/acceso-app")
def api_dar_acceso_app(usuario_id: int, payload: AccesoAppIn, admin: dict = Depends(requiere_admin_completo)):
    """El administrador le da usuario y contraseña a un trabajador que RH dio de alta."""
    p = db.obtener_personal_rh(admin["empresa_id"], usuario_id)
    if not p:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    username = payload.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9._@-]+", username):
        raise HTTPException(status_code=400, detail="El usuario solo puede llevar letras, números, punto, guion o @ (sin espacios).")
    otro = db.obtener_usuario_por_username(username)
    if otro and otro["id"] != usuario_id:
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está en uso")
    db.dar_acceso_app(admin["empresa_id"], usuario_id, username, payload.password)
    return {"ok": True, "username": username}


# ---- Nómina semanal (lunes a domingo) ----

def _lunes_de(semana: Optional[str]):
    try:
        d = date.fromisoformat(semana[:10]) if semana else db.ahora().date()
    except Exception:
        raise HTTPException(status_code=400, detail="Semana inválida")
    return d - timedelta(days=d.weekday())


def _calculo_nomina(empresa_id, lunes, solo_usuario_id=None):
    domingo = lunes + timedelta(days=6)
    hoy = db.ahora().date()
    rep = _reporte_asistencia(empresa_id, lunes, domingo, solo_usuario_id=solo_usuario_id)
    por_uid = {e["usuario_id"]: e for e in rep["empleados"]}
    guardadas = db.nomina_semana(empresa_id, lunes.isoformat())
    filas = []
    for p in db.listar_personal_rh(empresa_id, incluir_bajas=True):
        if solo_usuario_id and p["id"] != solo_usuario_id:
            continue
        g = guardadas.get(p["id"])
        if not p["activo"]:
            # Dados de baja: solo si ya tenían algo guardado esa semana o se fueron durante ella.
            if not g and not (p.get("fecha_baja") and p["fecha_baja"] >= lunes.isoformat()):
                continue
        if p.get("sueldo_semanal") is None and not p.get("numero_empleado") and not g:
            continue
        r = por_uid.get(p["id"])
        dias = r["dias"] if r else []
        # Solo cuentan los días desde que entró y hasta su baja.
        ini, fin = (p.get("fecha_ingreso") or "")[:10], (p.get("fecha_baja") or "")[:10]
        dias = [d for d in dias if (not ini or d["fecha"] >= ini) and (not fin or d["fecha"] <= fin)]
        laborables = [d for d in dias if d["laborable"]]
        trabajados = [d for d in dias if d["estatus"] in ("puntual", "retardo", "sin_salida", "dia_no_laboral")]
        por_venir = [d for d in laborables if d["estatus"] in (None, "pendiente") and d["fecha"] >= hoy.isoformat()]
        cuenta = lambda est: sum(1 for d in dias if d["estatus"] == est)
        resumen = {"faltas": cuenta("falta"), "retardos": cuenta("retardo"), "justificadas": cuenta("justificada"),
                   "sin_salida": cuenta("sin_salida"),
                   "minutos_retardo": sum(int(d.get("minutos_retardo") or 0) for d in dias)}
        faltas = resumen["faltas"]
        sueldo = p.get("sueldo_semanal")
        n_lab = len(laborables)
        sin_conexion = cuenta("sin_conexion")
        # Un día "sin conexión del checador" no se sabe si vino: la semana queda por revisar.
        completa = bool(r) and faltas == 0 and not sin_conexion and not por_venir and n_lab > 0
        sugerido = sueldo if completa and sueldo is not None else None
        fila = {
            "usuario_id": p["id"], "nombre": p["nombre_completo"], "numero_empleado": p.get("numero_empleado"),
            "puesto": p.get("puesto"), "departamento": p.get("departamento"), "nave": p.get("sucursal_nombre"),
            "activo": p["activo"], "sueldo_semanal": sueldo,
            "dias_laborables": n_lab, "dias_trabajados": len(trabajados), "faltas": faltas,
            "retardos": int(resumen.get("retardos") or 0), "minutos_retardo": int(resumen.get("minutos_retardo") or 0),
            "justificadas": int(resumen.get("justificadas") or 0), "sin_salida": int(resumen.get("sin_salida") or 0),
            "sin_conexion": sin_conexion,
            "dias_por_venir": len(por_venir), "semana_completa": completa,
            "dias": [{"fecha": d["fecha"], "dia": d["dia"], "estatus": d["estatus"], "entrada": d["entrada"],
                      "salida": d["salida"], "motivo": d.get("motivo"), "laborable": d["laborable"]} for d in (r["dias"] if r else [])],
            "sugerido": sugerido,
            "referencia_proporcional": round(sueldo * (n_lab - faltas) / n_lab, 2) if sueldo is not None and n_lab else None,
            "sin_checador": not r,
            "monto_pagar": None, "nota": None, "cerrada": False, "guardado_por": None, "guardado_en": None,
            "monto_manual": False,
        }
        if g:
            if g["cerrada"]:
                # Semana cerrada: se muestra tal como se cerró.
                for k in ("sueldo_semanal", "dias_laborables", "dias_trabajados", "faltas", "retardos", "justificadas"):
                    if g.get(k) is not None:
                        fila[k] = g[k]
            fila.update(monto_pagar=g.get("monto_pagar"), nota=g.get("nota"), cerrada=bool(g["cerrada"]),
                        guardado_por=g.get("actualizado_por_nombre"), guardado_en=g.get("actualizado_en"),
                        monto_manual=g.get("monto_pagar") is not None)
        if fila["monto_pagar"] is None:
            fila["monto_pagar"] = sugerido
        if fila["cerrada"]:
            fila["estado"] = "cerrada"
        elif sueldo is None:
            fila["estado"] = "sin_sueldo"
        elif fila["monto_manual"]:
            fila["estado"] = "capturado"
        elif por_venir:
            fila["estado"] = "en_curso"
        elif completa:
            fila["estado"] = "completa"
        else:
            fila["estado"] = "revisar"
        filas.append(fila)
    filas.sort(key=lambda f: (f["nave"] or "~", f["nombre"] or ""))
    return filas, rep.get("avisos") or []


@app.get("/api/rh/nomina")
def api_nomina_semanal(semana: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):
    _requiere_rh_sin_microsip(usuario)
    lunes = _lunes_de(semana)
    filas, avisos = _calculo_nomina(usuario["empresa_id"], lunes)
    total = sum(f["monto_pagar"] or 0 for f in filas)
    return {"semana_inicio": lunes.isoformat(), "semana_fin": (lunes + timedelta(days=6)).isoformat(),
            "filas": filas, "total": round(total, 2), "avisos": avisos,
            "cerrada": bool(filas) and all(f["cerrada"] for f in filas),
            "por_revisar": sum(1 for f in filas if f["estado"] == "revisar"),
            "sin_sueldo": sum(1 for f in filas if f["estado"] == "sin_sueldo")}


class NominaFilaIn(BaseModel):
    semana: str
    monto_pagar: Optional[float] = Field(default=None, ge=0, le=10_000_000)   # null = volver al cálculo
    nota: Optional[str] = Field(default=None, max_length=300)


def _datos_fila_nomina(f, monto, nota):
    return {k: f.get(k) for k in ("sueldo_semanal", "dias_laborables", "dias_trabajados", "faltas", "retardos", "justificadas")} | \
        {"monto_pagar": monto, "nota": nota}


@app.put("/api/rh/nomina/{usuario_id}")
def api_nomina_guardar(usuario_id: int, payload: NominaFilaIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """RH captura (o corrige) lo que se le paga a una persona esa semana."""
    _requiere_rh_sin_microsip(usuario)
    lunes = _lunes_de(payload.semana)
    filas, _ = _calculo_nomina(usuario["empresa_id"], lunes, solo_usuario_id=usuario_id)
    if not filas:
        raise HTTPException(status_code=404, detail="Esa persona no está en la nómina")
    f = filas[0]
    if f["cerrada"]:
        raise HTTPException(status_code=400, detail="Esa semana ya está cerrada. Reábrela para cambiarla.")
    db.guardar_nomina_fila(usuario["empresa_id"], lunes.isoformat(), usuario_id,
                           _datos_fila_nomina(f, payload.monto_pagar, (payload.nota or "").strip() or None), usuario["id"])
    filas, _ = _calculo_nomina(usuario["empresa_id"], lunes, solo_usuario_id=usuario_id)
    return filas[0]


class NominaCerrarIn(BaseModel):
    semana: str
    reabrir: bool = False


@app.post("/api/rh/nomina/cerrar")
def api_nomina_cerrar(payload: NominaCerrarIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Cierra la semana: guarda lo que se paga a cada quien (ya no cambia aunque
    lleguen checadas después). Todos deben tener monto; reabrir la deja editable."""
    _requiere_rh_sin_microsip(usuario)
    lunes = _lunes_de(payload.semana)
    filas, _ = _calculo_nomina(usuario["empresa_id"], lunes)
    if payload.reabrir:
        for f in filas:
            if f["cerrada"]:
                db.guardar_nomina_fila(usuario["empresa_id"], lunes.isoformat(), f["usuario_id"],
                                       _datos_fila_nomina(f, f["monto_pagar"] if f["monto_manual"] else None, f["nota"]),
                                       usuario["id"], cerrar=False)
        return {"ok": True, "reabierta": True}
    if lunes + timedelta(days=6) >= db.ahora().date() + timedelta(days=7):
        raise HTTPException(status_code=400, detail="No se puede cerrar una semana que todavía no empieza.")
    faltan = [f["nombre"] for f in filas if f["monto_pagar"] is None]
    if faltan:
        raise HTTPException(status_code=400, detail="Falta poner cuánto se le paga a: " + ", ".join(faltan[:15]) +
                            ("…" if len(faltan) > 15 else ""))
    for f in filas:
        db.guardar_nomina_fila(usuario["empresa_id"], lunes.isoformat(), f["usuario_id"],
                               _datos_fila_nomina(f, f["monto_pagar"], f["nota"]), usuario["id"], cerrar=True)
    return {"ok": True, "cerradas": len(filas), "total": round(sum(f["monto_pagar"] or 0 for f in filas), 2)}


@app.post("/api/rh/checadas/sync")
def api_checadas_sync(payload: ChecadasSyncIn, x_token_checador: Optional[str] = Header(None)):
    """Lo llama el programa biotime_sync.ps1 desde la PC de BioTime (sin
    login: se identifica con el token de la empresa)."""
    empresa = db.empresa_por_token_checador((x_token_checador or "").strip())
    if not empresa:
        raise HTTPException(status_code=401, detail="Token del checador inválido — descarga otra vez el programa desde RH → Asistencia.")
    checadas = [c for c in (asistencia.checada_de_api(t) for t in payload.checadas) if c]
    nuevas = db.guardar_checadas(empresa["id"], checadas, "biotime_pc", payload.equipo)
    db.marcar_sync_checador(empresa["id"], payload.equipo)
    return {"recibidas": len(payload.checadas), "validas": len(checadas), "nuevas": nuevas}


# ---- Checadores ZKTeco directo por ADMS ("Conf. Srvr. de Nube"), sin PC ----
# El checador se configura con: Modo ADMS, dominio = esta app, puerto 443, HTTPS.
# Se identifica por su número de serie (SN); RH lo da de alta en Asistencia.

def _texto_plano(t, status=200):
    return Response(content=t, media_type="text/plain", status_code=status)


def _ip_cliente(request: Request):
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()


@app.api_route("/iclock/cdata", methods=["GET", "POST"])
@app.api_route("/iclock/cdata.aspx", methods=["GET", "POST"])
async def adms_cdata(request: Request):
    q = request.query_params
    sn = (q.get("SN") or q.get("sn") or "").strip().upper()
    if not sn:
        return _texto_plano("ERROR: falta SN", 400)
    if request.method == "GET":
        info = "&".join(f"{k}={v}" for k, v in q.items() if k.lower() in ("options", "pushver", "language", "pushcommkey"))
        db.conexion_checador_adms(sn, _ip_cliente(request), info or None)
        # Respuesta de arranque (handshake). Pide todas las checadas que no haya mandado.
        return _texto_plano("\n".join([
            f"GET OPTION FROM: {sn}", "ATTLOGStamp=None", "OPERLOGStamp=9999", "ATTPHOTOStamp=None",
            "ErrorDelay=30", "Delay=10", "TransTimes=00:00;14:05", "TransInterval=1",
            "TransFlag=TransData AttLog\tAttPhoto", "TimeZone=-6", "Realtime=1", "Encrypt=None", ""]))
    cuerpo = (await request.body()).decode("utf-8", "replace")
    tabla = (q.get("table") or "").upper()
    chk = db.conexion_checador_adms(sn, _ip_cliente(request))
    if tabla == "ATTPHOTO":
        if chk and chk.get("empresa_id") and chk.get("activo"):
            foto = asistencia.leer_foto_checada(await request.body())
            if foto:
                db.foto_checada_gente(chk["empresa_id"], sn, foto[0], foto[1])
        return _texto_plano("OK")
    if tabla != "ATTLOG":
        if chk and chk.get("empresa_id") and tabla in ("OPERLOG", "USERINFO", "USER", "USERPIC", "BIOPHOTO", "BIODATA"):
            db.guardar_info_gente_checador(chk["empresa_id"], sn, *asistencia.leer_datos_checador(cuerpo))
        return _texto_plano("OK")
    if not chk or not chk.get("empresa_id") or not chk.get("activo"):
        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.
        return _texto_plano("ERROR: checador no registrado", 503)
    checadas, _malos = asistencia.leer_attlog(cuerpo, chk.get("nombre") or sn, chk.get("sucursal"))
    nuevas = db.guardar_checadas(chk["empresa_id"], checadas, "adms", sn)
    db.asegurar_gente_checador(chk["empresa_id"], sn, [c["codigo"] for c in checadas])
    if checadas:
        db.sumar_checadas_adms(sn, nuevas, max(c["fecha_hora"] for c in checadas).isoformat(timespec="seconds"))
        db.marcar_sync_checador(chk["empresa_id"], f"{chk.get('nombre') or sn} (directo)")
    return _texto_plano(f"OK: {len(checadas)}")


@app.get("/iclock/getrequest")
@app.get("/iclock/getrequest.aspx")
def adms_getrequest(request: Request, SN: Optional[str] = None):
    if SN:
        db.conexion_checador_adms(SN, _ip_cliente(request))
        sn = SN.strip().upper()
        # Cada 12 h se le piden al checador sus personas (número y nombre); además los comandos que pidió RH.
        if db.pedir_usuarios_checador(sn):
            db.encolar_comando_checador(sn, "DATA QUERY USERINFO")
        cmds = db.comandos_pendientes_checador(sn)
        if cmds:
            return _texto_plano("\n".join(f"C:{i}:{c}" for i, c in cmds) + "\n")
    return _texto_plano("OK")


@app.post("/iclock/querydata")
@app.post("/iclock/querydata.aspx")
async def adms_querydata(request: Request):
    sn = (request.query_params.get("SN") or "").strip().upper()
    chk = db.checador_adms(sn) if sn else None
    if chk and chk.get("empresa_id"):
        cuerpo = (await request.body()).decode("utf-8", "replace")
        db.guardar_info_gente_checador(chk["empresa_id"], sn, *asistencia.leer_datos_checador(cuerpo))
    return _texto_plano("OK")


@app.api_route("/iclock/devicecmd", methods=["GET", "POST"])
@app.api_route("/iclock/devicecmd.aspx", methods=["GET", "POST"])
async def adms_devicecmd(request: Request):
    """El checador avisa cómo le fue con cada comando: ID=..&Return=..&CMD=.. (uno por renglón)."""
    sn = (request.query_params.get("SN") or "").strip().upper()
    cuerpo = (await request.body()).decode("utf-8", "replace") if request.method == "POST" else ""
    for linea in cuerpo.replace("\r", "").split("\n"):
        datos = dict(p.split("=", 1) for p in linea.split("&") if "=" in p)
        if sn and str(datos.get("ID", "")).isdigit():
            db.resultado_comando_checador(sn, int(datos["ID"]), f"Return={datos.get('Return', '')} {datos.get('CMD', '')}".strip())
    return _texto_plano("OK")


@app.get("/iclock/ping")
@app.get("/iclock/test")
def adms_ok():
    return _texto_plano("OK")


class GenteChecadorIn(BaseModel):
    usuario_id: Optional[int] = None
    nombre: Optional[str] = Field(default=None, max_length=120)


@app.get("/api/rh/checadores/gente")
def api_gente_checadores(bajas: bool = False, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Personas de cada checador (número, nombre del checador, nombre corregido, foto, a quién están ligadas)."""
    return {"gente": db.listar_gente_checador(usuario["empresa_id"], bajas),
            "usuarios": db.usuarios_ligables_checador(usuario["empresa_id"])}


@app.get("/api/rh/checadores/gente/{gente_id}/foto")
def api_foto_gente_checador(gente_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    foto = db.foto_gente_checador(usuario["empresa_id"], gente_id)
    if not foto:
        raise HTTPException(status_code=404, detail="Sin foto")
    return {"foto": foto}


@app.patch("/api/rh/checadores/gente/{gente_id}")
def api_actualizar_gente_checador(gente_id: int, payload: GenteChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    try:
        n = db.actualizar_gente_checador(usuario["empresa_id"], gente_id, payload.usuario_id, _limpio(payload.nombre), usuario["id"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not n:
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"ok": True}


class PedirChecadorIn(BaseModel):
    que: str = Field(pattern="^(personas|fotos|todo)$")


@app.post("/api/rh/checadores/{sn}/pedir")
def api_pedir_al_checador(sn: str, payload: PedirChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Le pide al checador su lista de personas o sus fotos (llegan en su siguiente conexión, ~1 min)."""
    chk = db.checador_adms(sn)
    if not chk or chk.get("empresa_id") != usuario["empresa_id"]:
        raise HTTPException(status_code=404, detail="Checador no encontrado")
    comandos = {"personas": ["DATA QUERY USERINFO"],
                "fotos": ["DATA QUERY USERPIC", "DATA QUERY BIOPHOTO"],
                "todo": ["DATA QUERY USERINFO", "DATA QUERY FINGERTMP", "DATA QUERY BIODATA", "DATA QUERY FACE"]}[payload.que]
    for c in comandos:
        db.encolar_comando_checador(chk["sn"], c)
    return {"ok": True, "comandos": comandos}


class RedChecadoresIn(BaseModel):
    usuario_id: Optional[int] = None   # None = toda la gente ligada
    simular: bool = True


def _plan_red_checadores(empresa_id, solo_usuario_id=None):
    """Para cada persona ligada, en qué checadores falta, con qué número entraría y qué huellas/caras se copian."""
    checadores, gente, plantillas = db.datos_red_checadores(empresa_id)
    nombres_chk = {k["sn"]: (k.get("nombre") or k["sn"]) for k in checadores}
    usados = {}            # sn -> números ocupados en ese checador
    leidos = set()         # checadores de los que ya tenemos su lista de personas
    por_usuario = {}
    quitados = set()       # (usuario, checador) donde RH la dio de baja: no se vuelve a dar de alta ahí
    for g in gente:
        usados.setdefault(g["sn"], set()).add(g["codigo"])   # nunca se reutiliza un número (para no mezclar su historial)
        if g.get("en_checador"):
            leidos.add(g["sn"])
        if g.get("usuario_id") and g.get("baja_en"):
            quitados.add((g["usuario_id"], g["sn"]))
        elif g.get("usuario_id") and g.get("usuario_activo") is not False:
            por_usuario.setdefault(g["usuario_id"], []).append(g)
    plan, avisos, sin_biometria = [], [], []
    sin_numero, ocupado = [], []
    for k in checadores:
        if k["sn"] not in leidos:
            avisos.append(f"Todavía no tengo la lista de personas de {nombres_chk[k['sn']]}: toca «Leer personas, huellas y caras» y espera 2 min.")
    for uid, filas in por_usuario.items():
        if solo_usuario_id and uid != solo_usuario_id:
            continue
        presentes = {g["sn"] for g in filas}
        fuente = max(filas, key=lambda g: (len(plantillas.get((g["sn"], g["codigo"]), [])), bool(g.get("datos_usuario"))))
        pls = plantillas.get((fuente["sn"], fuente["codigo"]), [])
        nombre = fuente.get("nombre") or fuente.get("usuario_nombre") or fuente.get("nombre_checador")
        if not pls:
            if any(k["sn"] not in presentes and (uid, k["sn"]) not in quitados for k in checadores):
                sin_biometria.append(nombre or f"#{uid}")
            continue
        for k in checadores:
            if k["sn"] in presentes or (uid, k["sn"]) in quitados:
                continue
            ocupados = usados.setdefault(k["sn"], set())
            # El número en TODOS los checadores es el No. de empleado de Microsip.
            pin = asistencia.normalizar_codigo(fuente.get("numero_empleado"))
            if not pin.isdigit():
                sin_numero.append(nombre or f"#{uid}")
                break
            if pin in ocupados:
                ocupado.append(f"{nombre} (No. {pin} en {nombres_chk[k['sn']]})")
                continue
            ocupados.add(pin)
            plan.append({"usuario_id": uid, "persona": nombre, "desde": nombres_chk.get(fuente["sn"], fuente["sn"]),
                         "sn_destino": k["sn"], "destino": nombres_chk[k["sn"]], "numero": pin,
                         "huellas": sum(1 for x in pls if x["tabla"] == "FINGERTMP"), "caras": sum(1 for x in pls if x["tabla"] != "FINGERTMP"),
                         "listo": k["sn"] in leidos, "_fuente": fuente, "_plantillas": pls})
    if sin_biometria:
        avisos.append(f"{len(sin_biometria)} persona(s) sin huella ni cara leída, no se copian todavía: {', '.join(sorted(sin_biometria)[:12])}"
                      f"{'…' if len(sin_biometria) > 12 else ''}. Toca «Leer personas, huellas y caras» (o regístralas en un checador) y vuelve a intentar.")
    if sin_numero:
        avisos.append(f"{len(set(sin_numero))} persona(s) sin No. de empleado de Microsip, no se copian: {', '.join(sorted(set(sin_numero))[:12])}. "
                      "Captura su número de empleado y vuelve a intentar.")
    if ocupado:
        avisos.append(f"{len(ocupado)} no se copian porque su No. de Microsip ya lo tiene otra persona en ese checador: {'; '.join(ocupado[:10])}"
                      f"{'…' if len(ocupado) > 10 else ''}. Corre primero «Poner el No. de Microsip».")
    return plan, avisos


def _plan_numero_microsip(empresa_id):
    """Qué personas tienen en algún checador un número distinto a su No. de empleado de Microsip,
    y cómo dejarlos todos con ese número (sin perder huellas, caras ni checadas viejas)."""
    checadores, gente, plantillas = db.datos_red_checadores(empresa_id)
    nombres_chk = {k["sn"]: (k.get("nombre") or k["sn"]) for k in checadores}
    activos = [g for g in gente if not g.get("baja_en") and g["sn"] in nombres_chk]
    movimientos, problemas, bien = [], [], 0
    for k in checadores:
        filas = [g for g in activos if g["sn"] == k["sn"]]
        ocupante = {g["codigo"]: g for g in filas}
        de_baja = {g["codigo"]: g for g in gente if g["sn"] == k["sn"] and g.get("baja_en")}
        quiere = {}
        for g in filas:
            nombre = g.get("usuario_nombre") or g.get("nombre") or g.get("nombre_checador") or f"No. {g['codigo']}"
            if not g.get("usuario_id"):
                continue
            if g.get("usuario_activo") is False:
                continue
            obj = asistencia.normalizar_codigo(g.get("numero_empleado"))
            if not obj:
                problemas.append({"checador": nombres_chk[k["sn"]], "persona": nombre, "actual": g["codigo"], "motivo": "No tiene No. de empleado de Microsip capturado"})
                continue
            if not obj.isdigit():
                problemas.append({"checador": nombres_chk[k["sn"]], "persona": nombre, "actual": g["codigo"], "motivo": f"Su No. de empleado «{obj}» no es solo números (el checador solo acepta números)"})
                continue
            if g["codigo"] == obj:
                bien += 1
                continue
            pls = plantillas.get((k["sn"], g["codigo"]), [])
            if not pls:
                problemas.append({"checador": nombres_chk[k["sn"]], "persona": nombre, "actual": g["codigo"], "nuevo": obj,
                                  "motivo": "No tengo leída su huella/cara de este checador: toca «Leer personas, huellas y caras» y espera 2 min"})
                continue
            viejo_baja = de_baja.get(obj)
            if viejo_baja and viejo_baja.get("usuario_id") not in (None, g["usuario_id"]):
                problemas.append({"checador": nombres_chk[k["sn"]], "persona": nombre, "actual": g["codigo"], "nuevo": obj,
                                  "motivo": f"El No. {obj} ya se usó en este checador para otra persona (dada de baja); se mezclaría su historial"})
                continue
            quiere[g["codigo"]] = (g, obj, pls, nombre)
        # Orden: primero a quien su número nuevo ya está libre; los que se cruzan (A↔B) pasan por un número temporal.
        libres = lambda cod: cod not in ocupante
        pendientes = dict(quiere)
        temporal = 90000
        while pendientes:
            avanzo = False
            for cod, (g, obj, pls, nombre) in list(pendientes.items()):
                if libres(obj):
                    movimientos.append({"sn": k["sn"], "checador": nombres_chk[k["sn"]], "persona": nombre, "gente_id": g["id"],
                                        "actual": g["codigo"], "nuevo": obj, "via": g.get("_via"), "huellas": sum(1 for x in pls if x["tabla"] == "FINGERTMP"),
                                        "caras": sum(1 for x in pls if x["tabla"] != "FINGERTMP"), "_g": g, "_pls": pls})
                    del ocupante[g["_cod_actual"] if g.get("_cod_actual") else cod]
                    ocupante[obj] = g
                    del pendientes[cod]
                    avanzo = True
            if avanzo:
                continue
            bloqueados = [(cod, v) for cod, v in pendientes.items() if v[1] in ocupante and ocupante[v[1]]["codigo"] not in pendientes and ocupante[v[1]] is not v[0]]
            if bloqueados:
                for cod, (g, obj, pls, nombre) in bloqueados:
                    otro = ocupante[obj]
                    otro_nombre = otro.get("usuario_nombre") or otro.get("nombre") or otro.get("nombre_checador") or "alguien"
                    problemas.append({"checador": nombres_chk[k["sn"]], "persona": nombre, "actual": g["codigo"], "nuevo": obj,
                                      "motivo": f"El No. {obj} lo tiene {otro_nombre}" + ("" if otro.get("usuario_id") else " (sin ligar: lígalo o dalo de baja primero)")})
                    del pendientes[cod]
                continue
            # Ciclo (A quiere el de B y B el de A): A se pasa a un número temporal primero.
            cod, (g, obj, pls, nombre) = next(iter(pendientes.items()))
            while str(temporal) in ocupante or str(temporal) in de_baja:
                temporal += 1
            tmp = str(temporal)
            movimientos.append({"sn": k["sn"], "checador": nombres_chk[k["sn"]], "persona": nombre, "gente_id": g["id"], "actual": g["codigo"],
                                "nuevo": tmp, "temporal": True, "huellas": 0, "caras": 0, "_g": g, "_pls": pls})
            del ocupante[cod]
            ocupante[tmp] = g
            g2 = dict(g, _cod_actual=tmp, _via=tmp)
            del pendientes[cod]
            pendientes[tmp] = (g2, obj, pls, nombre)
    return movimientos, problemas, bien, [k for k in checadores]


class NumeroMicrosipIn(BaseModel):
    simular: bool = True


@app.post("/api/rh/checadores/numero-microsip")
def api_numero_microsip(payload: NumeroMicrosipIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Deja a cada persona ligada con su No. de empleado de Microsip como número en cada checador.
    En el checador: alta con el número nuevo + sus huellas/caras, y borra el número viejo."""
    movimientos, problemas, bien, _ = _plan_numero_microsip(usuario["empresa_id"])
    hechos = 0
    if not payload.simular:
        por_checador = {}
        for m in movimientos:
            g, nuevo = m["_g"], m["nuevo"]
            actual = g.get("_cod_actual") or m["actual"]
            nombre = g.get("usuario_nombre") or g.get("nombre") or g.get("nombre_checador")
            db.encolar_comando_checador(m["sn"], asistencia.comando_alta_usuario(g.get("datos_usuario"), nuevo, nombre))
            for t in m["_pls"]:
                db.encolar_comando_checador(m["sn"], asistencia.comando_plantilla(t["tabla"], t["linea"], nuevo))
            db.encolar_comando_checador(m["sn"], f"DATA DELETE USERINFO PIN={actual}")
            if not m.get("temporal"):
                por_checador.setdefault(m["sn"], []).append((g["id"], m["actual"], nuevo))
            hechos += 1
        for sn, cambios in por_checador.items():
            db.renumerar_gente_checador(usuario["empresa_id"], sn, cambios)
    visibles = [{k: v for k, v in m.items() if not k.startswith("_")} for m in movimientos if not m.get("temporal")]
    return {"cambios": visibles, "problemas": problemas, "ya_bien": bien, "aplicados": hechos, "simulado": payload.simular}


@app.post("/api/rh/checadores/red")
def api_red_checadores(payload: RedChecadoresIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Da de alta a cada persona ligada en los checadores donde no está (con sus huellas y caras),
    para que pueda checar en cualquier sucursal. simular=True solo dice qué haría."""
    plan, avisos = _plan_red_checadores(usuario["empresa_id"], payload.usuario_id)
    hechos = 0
    if not payload.simular:
        for p in plan:
            if not p["listo"]:
                continue
            f = p["_fuente"]
            db.encolar_comando_checador(p["sn_destino"], asistencia.comando_alta_usuario(f.get("datos_usuario"), p["numero"], p["persona"]))
            for t in p["_plantillas"]:
                db.encolar_comando_checador(p["sn_destino"], asistencia.comando_plantilla(t["tabla"], t["linea"], p["numero"]))
            db.alta_gente_por_red(usuario["empresa_id"], p["sn_destino"], p["numero"], p["usuario_id"], p["persona"], usuario["id"])
            hechos += 1
    return {"plan": [{k: v for k, v in p.items() if not k.startswith("_")} for p in plan], "avisos": avisos,
            "aplicados": hechos, "simulado": payload.simular}


class AltaChecadorIn(BaseModel):
    usuario_id: int
    nombre: Optional[str] = Field(default=None, max_length=120)
    foto_base64: str = Field(min_length=100)
    checadores: list[str] = Field(default_factory=list)   # vacío = todos los activos


@app.post("/api/rh/checadores/alta")
def api_alta_en_checadores(payload: AltaChecadorIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Da de alta a una persona en los checadores con la foto de su cara (tomada con el celular).
    El checador saca la cara de la foto; la persona ya puede checar sin registrarse en el aparato."""
    if len(payload.foto_base64) > 3_000_000:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado.")
    checadores, gente, _ = db.datos_red_checadores(usuario["empresa_id"])
    elegidos = [k for k in checadores if not payload.checadores or k["sn"] in payload.checadores]
    if not elegidos:
        raise HTTPException(status_code=400, detail="No hay checadores conectados para dar de alta.")
    persona = next((u for u in db.usuarios_ligables_checador(usuario["empresa_id"]) if u["id"] == payload.usuario_id), None)
    if not persona:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    nombre = _limpio(payload.nombre) or persona["nombre"]
    foto = payload.foto_base64 if payload.foto_base64.startswith("data:") else "data:image/jpeg;base64," + payload.foto_base64
    b64 = foto.split(",", 1)[1]
    hechos = []
    for k in elegidos:
        if any(g["sn"] == k["sn"] and g.get("usuario_id") == payload.usuario_id and not g.get("baja_en") for g in gente):
            continue   # ya está en ese checador
        ocupados = {g["codigo"]: g for g in gente if g["sn"] == k["sn"]}
        pin = asistencia.normalizar_codigo(persona.get("numero_empleado"))
        if not pin.isdigit():
            raise HTTPException(status_code=400, detail="Esta persona no tiene No. de empleado de Microsip (solo números). Captúralo primero: ese es su número en el checador.")
        if pin in ocupados and ocupados[pin].get("usuario_id") != payload.usuario_id:
            otro = ocupados[pin]
            raise HTTPException(status_code=400, detail=f"En {k.get('nombre') or k['sn']} el No. {pin} ya lo tiene "
                                f"{otro.get('usuario_nombre') or otro.get('nombre') or otro.get('nombre_checador') or 'otra persona'}. "
                                "Corre «Poner el No. de Microsip» o da de baja ese número primero.")
        tam = len(base64.b64decode(b64))
        db.encolar_comando_checador(k["sn"], asistencia.comando_alta_usuario(None, pin, nombre))
        db.encolar_comando_checador(k["sn"], f"DATA UPDATE BIOPHOTO PIN={pin}\tType=9\tSize={tam}\tContent={b64}")
        db.encolar_comando_checador(k["sn"], f"DATA UPDATE USERPIC PIN={pin}\tSize={tam}\tContent={b64}")
        db.alta_gente_desde_app(usuario["empresa_id"], k["sn"], pin, payload.usuario_id, nombre, foto, usuario["id"])
        hechos.append({"checador": k.get("nombre") or k["sn"], "numero": pin})
    return {"ok": True, "altas": hechos}


@app.post("/api/rh/checadores/gente/{gente_id}/baja")
def api_baja_gente_checador(gente_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """La borra de ese checador (deja de poder checar ahí). Su historial de checadas se conserva."""
    r = db.baja_gente_checador(usuario["empresa_id"], gente_id)
    if not r:
        raise HTTPException(status_code=404, detail="No encontrada o ya dada de baja")
    db.encolar_comando_checador(r["sn"], f"DATA DELETE USERINFO PIN={r['codigo']}")
    return {"ok": True}


class BajaUsuarioIn(BaseModel):
    usuario_id: int


@app.post("/api/rh/checadores/baja-usuario")
def api_baja_usuario_checadores(payload: BajaUsuarioIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Ya no trabaja: la borra de TODOS los checadores."""
    filas = db.gente_de_usuario(usuario["empresa_id"], payload.usuario_id)
    for g in filas:
        r = db.baja_gente_checador(usuario["empresa_id"], g["id"])
        if r:
            db.encolar_comando_checador(r["sn"], f"DATA DELETE USERINFO PIN={r['codigo']}")
    return {"ok": True, "checadores": len(filas)}


@app.get("/api/rh/checadores/comandos")
def api_resumen_comandos(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.resumen_comandos_checadores(usuario["empresa_id"])


@app.get("/api/rh/mi-asistencia")
def api_mi_asistencia(desde: Optional[str] = None, hasta: Optional[str] = None, usuario: dict = Depends(auth.get_current_user)):
    """La puntualidad de quien la consulta (checadas del reloj checador). RH decide quién la puede ver."""
    d, h = _rango_fechas(desde, hasta)
    if not db.puede_ver_mi_asistencia(usuario["id"]):
        return {"desde": d.isoformat(), "hasta": h.isoformat(), "empleado": None, "permitido": False,
                "aviso": "Recursos Humanos todavía no te ha dado acceso para ver tu asistencia."}
    rep = _reporte_asistencia(usuario["empresa_id"], d, h, solo_usuario_id=usuario["id"])
    yo = rep["empleados"][0] if rep["empleados"] else None
    return {"desde": d.isoformat(), "hasta": h.isoformat(), "empleado": yo, "permitido": True,
            "aviso": None if yo else "Todavía no hay checadas tuyas del reloj checador. Si checas en un reloj, pide a Recursos Humanos que te liguen."}


@app.get("/api/rh/asistencia/usuario/{usuario_id}")
def api_asistencia_de_usuario(usuario_id: int, desde: Optional[str] = None, hasta: Optional[str] = None,
                              usuario: dict = Depends(requiere_datos_empleado_rh)):
    """Para RH en la app: las checadas de una persona, día por día (a tiempo / tarde / no llegó)."""
    d, h = _rango_fechas(desde, hasta)
    rep = _reporte_asistencia(usuario["empresa_id"], d, h, solo_usuario_id=usuario_id)
    emp = rep["empleados"][0] if rep["empleados"] else None
    return {"desde": d.isoformat(), "hasta": h.isoformat(), "empleado": emp, "permitido": True,
            "aviso": None if emp else "Esta persona todavía no tiene checadas (o no está ligada a ningún checador)."}


class LigarCodigoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    usuario_id: int


@app.get("/api/rh/asistencia/usuarios-ligables")
def api_usuarios_ligables(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.usuarios_ligables_checador(usuario["empresa_id"])


@app.post("/api/rh/asistencia/ligar-codigo")
def api_ligar_codigo(payload: LigarCodigoIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    try:
        modo = db.ligar_codigo_checador(usuario["empresa_id"], asistencia.normalizar_codigo(payload.codigo), payload.usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "modo": modo}


@app.delete("/api/rh/asistencia/ligar-codigo/{codigo}")
def api_desligar_codigo(codigo: str, usuario: dict = Depends(requiere_datos_empleado_rh)):
    db.desligar_codigo_checador(usuario["empresa_id"], asistencia.normalizar_codigo(codigo))
    return {"ok": True}


class ChecadorAdmsIn(BaseModel):
    sn: str = Field(min_length=4, max_length=40)
    nombre: Optional[str] = Field(default=None, max_length=80)
    sucursal: Optional[str] = Field(default=None, max_length=80)
    activo: bool = True


@app.get("/api/rh/checadores")
def api_checadores_adms(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.listar_checadores_adms(usuario["empresa_id"])


@app.post("/api/rh/checadores")
def api_guardar_checador_adms(payload: ChecadorAdmsIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    try:
        return db.guardar_checador_adms(usuario["empresa_id"], payload.sn, _limpio(payload.nombre), _limpio(payload.sucursal), payload.activo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/rh/checadores/{checador_id}")
def api_quitar_checador_adms(checador_id: int, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if not db.quitar_checador_adms(usuario["empresa_id"], checador_id):
        raise HTTPException(status_code=404, detail="Checador no encontrado")
    return {"ok": True}


@app.post("/api/rh/checadas/importar")
def api_checadas_importar(payload: ImportarChecadasIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    if len(payload.archivo) > 20_000_000:
        raise HTTPException(status_code=400, detail="El archivo pesa demasiado (máximo ~14MB). Exporta un rango de fechas más corto.")
    try:
        datos, _ = ia._decodificar_base64(payload.archivo, "application/octet-stream")
        checadas = asistencia.leer_archivo_biotime(datos, payload.nombre or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {e}")
    nuevas = db.guardar_checadas(usuario["empresa_id"], checadas, "archivo", payload.nombre)
    fechas = [c["fecha_hora"] for c in checadas]
    return {"leidas": len(checadas), "nuevas": nuevas,
            "desde": min(fechas).date().isoformat() if fechas else None,
            "hasta": max(fechas).date().isoformat() if fechas else None}


def _opciones_asistencia(empresa_id):
    """Biométricos y sucursales para elegir qué ver, y el horario de cada sucursal."""
    sucursales = db.listar_sucursales_reparacion(empresa_id, solo_activas=True)
    hs = db.horarios_sucursal_asistencia(empresa_id)
    checadores = [{"sn": k["sn"], "nombre": k.get("nombre") or k["sn"], "sucursal": k.get("sucursal")}
                  for k in db.listar_checadores_adms(empresa_id)]
    if db.hay_checadas_app(empresa_id):
        checadores.append({"sn": "APP", "nombre": "📱 Checador de la app", "sucursal": None})
    return {
        "checadores": checadores,
        "sucursales": [{"id": x["id"], "nombre": x["nombre"], "horario": hs.get(x["id"])} for x in sucursales],
    }


@app.get("/api/rh/asistencia/opciones")
def api_asistencia_opciones(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return {**_opciones_asistencia(usuario["empresa_id"]), "horario_general": _horario_default(usuario["empresa_id"]),
            "conexion_checadores": db.estado_conexion_checadores(usuario["empresa_id"])}


@app.get("/api/rh/asistencia")
def api_asistencia(desde: Optional[str] = None, hasta: Optional[str] = None, checador: Optional[str] = None,
                   sucursal: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):
    d, h = _rango_fechas(desde, hasta)
    cfg = db.config_checador(usuario["empresa_id"])
    return {"desde": d.isoformat(), "hasta": h.isoformat(),
            **_reporte_asistencia(usuario["empresa_id"], d, h, checador=checador or None, sucursal=sucursal or None),
            "horario_general": _horario_default(usuario["empresa_id"]), **_opciones_asistencia(usuario["empresa_id"]),
            "ultima_sync": cfg.get("checador_ultima_sync"), "ultimo_equipo": cfg.get("checador_ultimo_equipo")}


@app.put("/api/rh/asistencia/horarios-sucursal/{sucursal_id}")
def api_asistencia_horario_sucursal(sucursal_id: int, payload: HorarioUsuarioIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    db.guardar_horario_sucursal(usuario["empresa_id"], sucursal_id, payload.horario.model_dump() if payload.horario else None)
    return {"ok": True}


class PermisoMiAsistenciaIn(BaseModel):
    usuario_ids: Optional[List[int]] = None   # None = a todos
    ver: bool


@app.get("/api/rh/asistencia/quien-ve")
def api_quien_ve_asistencia(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return db.permisos_mi_asistencia(usuario["empresa_id"])


@app.put("/api/rh/asistencia/quien-ve")
def api_cambiar_quien_ve_asistencia(payload: PermisoMiAsistenciaIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    return {"ok": True, "cambiados": db.cambiar_permiso_mi_asistencia(usuario["empresa_id"], payload.usuario_ids, payload.ver)}


@app.get("/api/rh/asistencia/excel")
def api_asistencia_excel(desde: Optional[str] = None, hasta: Optional[str] = None, checador: Optional[str] = None,
                         sucursal: Optional[str] = None, usuario: dict = Depends(requiere_datos_empleado_rh)):
    d, h = _rango_fechas(desde, hasta)
    empresa = db.obtener_empresa(usuario["empresa_id"]) or {}
    contenido = asistencia.excel_reporte(_reporte_asistencia(usuario["empresa_id"], d, h, checador=checador or None, sucursal=sucursal or None),
                                         d, h, empresa.get("nombre") or "")
    return Response(content=contenido,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=asistencia_{d.isoformat()}_{h.isoformat()}.xlsx"})


@app.get("/api/rh/asistencia/config")
def api_asistencia_config(usuario: dict = Depends(requiere_datos_empleado_rh)):
    cfg = db.config_checador(usuario["empresa_id"], crear_token=True)
    return {"token": cfg.get("checador_token"), "ultima_sync": cfg.get("checador_ultima_sync"),
            "ultimo_equipo": cfg.get("checador_ultimo_equipo"), "horario_general": _horario_default(usuario["empresa_id"])}


@app.post("/api/rh/asistencia/token")
def api_asistencia_nuevo_token(usuario: dict = Depends(requiere_datos_empleado_rh)):
    return {"token": db.regenerar_token_checador(usuario["empresa_id"])}


@app.put("/api/rh/asistencia/horario-general")
def api_asistencia_horario_general(payload: HorarioIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    db.guardar_horario_default_checador(usuario["empresa_id"], payload.model_dump())
    return {"ok": True}


@app.put("/api/rh/asistencia/horarios/{usuario_id}")
def api_asistencia_horario_usuario(usuario_id: int, payload: HorarioUsuarioIn, usuario: dict = Depends(requiere_datos_empleado_rh)):
    db.guardar_horario_usuario(usuario["empresa_id"], usuario_id, payload.horario.model_dump() if payload.horario else None)
    return {"ok": True}


@app.get("/api/rh/asistencia/programa")
def api_asistencia_programa(request: Request, usuario: dict = Depends(requiere_datos_empleado_rh)):
    """El programa para la PC de BioTime, ya con la dirección y el token de la empresa."""
    cfg = db.config_checador(usuario["empresa_id"], crear_token=True)
    base = os.getenv("APP_BASE_URL_PUBLICA") or \
        f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', request.url.netloc)}"
    contenido = asistencia.script_agente(base, cfg["checador_token"])
    return Response(content=contenido.encode("utf-8-sig"), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=biotime_sync.ps1"})


# ---- Ventas: clientes desde la app de iPad + WhatsApp automático (API de Meta) ----
# Cualquiera con acceso al Checador de precio puede dar de alta clientes
# (quedan en el CRM como prospecto). Un vendedor sin permiso de CRM solo ve
# los clientes que él mismo dio de alta; admin o quien tenga CRM ve todos.

class ClienteVentasIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str = Field(min_length=7, max_length=30)
    email: Optional[str] = None
    giro: Optional[str] = None
    notas: Optional[str] = None
    enviar_whatsapp: bool = True


def _ve_todos_los_clientes(usuario: dict) -> bool:
    return usuario["rol"] == "admin" or bool(usuario.get("acceso_crm"))


def _nombre_empresa(empresa_id) -> str:
    empresa = db.obtener_empresa(empresa_id) or {}
    return empresa.get("nombre") or "nuestra empresa"


def _whatsapp_bienvenida(usuario: dict, cliente: dict) -> dict:
    """Manda la plantilla de bienvenida y deja registro (tabla + historial
    del CRM). Nunca truena: regresa {ok, estatus, error}."""
    empresa_id = usuario["empresa_id"]
    telefono = cliente.get("telefono") or ""
    try:
        wamid = whatsapp_meta.enviar_bienvenida(telefono, cliente["nombre"], _nombre_empresa(empresa_id),
                                                usuario.get("nombre") or "tu asesor")
    except whatsapp_meta.ErrorWhatsApp as e:
        db.registrar_envio_whatsapp(empresa_id, "bienvenida", telefono, "error", usuario["id"], cliente["id"], error=str(e))
        return {"ok": False, "estatus": "error", "error": str(e)}
    db.registrar_envio_whatsapp(empresa_id, "bienvenida", telefono, "sent", usuario["id"], cliente["id"], wamid=wamid)
    try:
        db.crear_interaccion_crm(empresa_id, cliente["id"], None, "whatsapp",
                                 "WhatsApp automático: mensaje de bienvenida", usuario["id"])
    except Exception as e:
        print(f"[whatsapp_meta] no se pudo registrar la interacción: {e}")
    return {"ok": True, "estatus": "sent", "error": None}


@app.get("/api/ventas/whatsapp/estado")
def api_ventas_whatsapp_estado(usuario: dict = Depends(requiere_ver_checador_precio)):
    return {"configurado": whatsapp_meta.configurado()}


@app.get("/api/ventas/clientes")
def api_ventas_listar_clientes(buscar: Optional[str] = None, usuario: dict = Depends(requiere_ver_checador_precio)):
    solo = None if _ve_todos_los_clientes(usuario) else usuario["id"]
    return db.listar_clientes_ventas(usuario["empresa_id"], buscar, solo)


@app.post("/api/ventas/clientes")
def api_ventas_crear_cliente(payload: ClienteVentasIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    empresa_id = usuario["empresa_id"]
    if not whatsapp_meta.normalizar_telefono(payload.telefono):
        raise HTTPException(status_code=400, detail="El teléfono no es válido — captura los 10 dígitos.")
    existente = db.buscar_cliente_crm_por_ultimos10(empresa_id, whatsapp_meta.ultimos_10(payload.telefono))
    if existente:
        return {"cliente": existente, "ya_existia": True, "whatsapp": None}
    cliente_id = db.crear_cliente_crm(
        empresa_id, " ".join(payload.nombre.split()), "prospecto", payload.telefono.strip(),
        (payload.email or "").strip() or None, None, (payload.notas or "").strip() or None, usuario["id"],
        giro=(payload.giro or "").strip() or None,
    )
    cliente = db.obtener_cliente_crm(empresa_id, cliente_id)
    whatsapp = None
    if payload.enviar_whatsapp:
        whatsapp = _whatsapp_bienvenida(usuario, cliente) if whatsapp_meta.configurado() else \
            {"ok": False, "estatus": "error", "error": "WhatsApp Business (Meta) todavía no está configurado en el servidor."}
    return {"cliente": cliente, "ya_existia": False, "whatsapp": whatsapp}


@app.post("/api/ventas/clientes/{cliente_id}/whatsapp-bienvenida")
def api_ventas_reenviar_bienvenida(cliente_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    cliente = db.obtener_cliente_crm(usuario["empresa_id"], cliente_id)
    if not cliente or (not _ve_todos_los_clientes(usuario) and cliente.get("creado_por_id") != usuario["id"]):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if not whatsapp_meta.configurado():
        raise HTTPException(status_code=400, detail="WhatsApp Business (Meta) todavía no está configurado en el servidor.")
    return _whatsapp_bienvenida(usuario, cliente)


@app.post("/api/cotizaciones/{cotizacion_id}/whatsapp")
def api_cotizacion_whatsapp_automatico(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Manda al cliente, por la API de Meta, la plantilla de bienvenida con
    el PDF de la cotización adjunto. Si el teléfono no es de un cliente del
    CRM todavía, lo da de alta (prospecto) y liga la cotización."""
    empresa_id = usuario["empresa_id"]
    cotizacion = db.obtener_cotizacion(empresa_id, cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes enviar esta cotización")
    if not whatsapp_meta.configurado():
        raise HTTPException(status_code=400, detail="WhatsApp Business (Meta) todavía no está configurado en el servidor.")
    telefono = (cotizacion.get("cliente_telefono") or "").strip()
    if not whatsapp_meta.normalizar_telefono(telefono):
        raise HTTPException(status_code=400, detail="La cotización no tiene un teléfono válido del cliente (10 dígitos).")

    cliente_id = cotizacion.get("cliente_crm_id")
    if not cliente_id:
        cliente = db.buscar_cliente_crm_por_ultimos10(empresa_id, whatsapp_meta.ultimos_10(telefono))
        if not cliente:
            nuevo_id = db.crear_cliente_crm(empresa_id, cotizacion["cliente_nombre"], "prospecto", telefono,
                                            None, cotizacion.get("cliente_direccion"), None, usuario["id"])
            cliente = {"id": nuevo_id}
        cliente_id = cliente["id"]
        db.vincular_cotizacion_cliente_crm(empresa_id, cotizacion_id, cliente_id)

    cotizacion["imagen_visual"] = db.obtener_imagen_visual_cotizacion(cotizacion_id)
    empresa = db.obtener_empresa(empresa_id) or {}
    diseno = db.obtener_plantilla_pdf(empresa_id, "cotizacion")
    pdf_bytes = pdfs_cotizaciones.generar_cotizacion_pdf(cotizacion, empresa, diseno)
    total_texto = f"${float(cotizacion.get('total') or 0):,.2f}"
    try:
        wamid = whatsapp_meta.enviar_cotizacion(
            telefono, cotizacion["cliente_nombre"], empresa.get("nombre") or "nuestra empresa", cotizacion["folio"],
            total_texto, usuario.get("nombre") or "tu asesor", pdf_bytes, f"Cotizacion_{cotizacion['folio']}.pdf",
        )
    except whatsapp_meta.ErrorWhatsApp as e:
        db.registrar_envio_whatsapp(empresa_id, "cotizacion", telefono, "error", usuario["id"], cliente_id,
                                    cotizacion_id, error=str(e))
        return {"ok": False, "estatus": "error", "error": str(e), "cliente_crm_id": cliente_id}
    db.registrar_envio_whatsapp(empresa_id, "cotizacion", telefono, "sent", usuario["id"], cliente_id,
                                cotizacion_id, wamid=wamid)
    try:
        db.crear_interaccion_crm(empresa_id, cliente_id, None, "whatsapp",
                                 f"WhatsApp automático: cotización {cotizacion['folio']} ({total_texto}) con PDF",
                                 usuario["id"])
    except Exception as e:
        print(f"[whatsapp_meta] no se pudo registrar la interacción: {e}")
    return {"ok": True, "estatus": "sent", "error": None, "cliente_crm_id": cliente_id}


@app.get("/api/cotizaciones/{cotizacion_id}/whatsapp")
def api_cotizacion_whatsapp_estatus(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return db.ultimo_envio_whatsapp_cotizacion(cotizacion_id) or {}


@app.get("/webhook/whatsapp-meta")
def webhook_whatsapp_meta_verificar(request: Request):
    """Meta llama aquí (GET) una sola vez al configurar el webhook."""
    q = request.query_params
    reto = whatsapp_meta.verificar_suscripcion(q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"))
    if reto is None:
        raise HTTPException(status_code=403, detail="Token de verificación incorrecto")
    return Response(content=reto, media_type="text/plain")


@app.post("/webhook/whatsapp-meta")
async def webhook_whatsapp_meta(request: Request):
    """Avisos de Meta: estatus de los mensajes (entregado, leído, falló) y
    mensajes que nos contestan los clientes (quedan en el historial del CRM).
    Sin login (Meta no manda tu JWT); se valida con la firma si hay
    WHATSAPP_META_APP_SECRET. Siempre responde 200 para que Meta no reintente."""
    cuerpo = await request.body()
    if not whatsapp_meta.firma_valida(cuerpo, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="Firma inválida")
    try:
        estatus, mensajes = whatsapp_meta.extraer_eventos(json.loads(cuerpo or b"{}"))
        for s in estatus:
            db.actualizar_envio_whatsapp_por_wamid(s["wamid"], s["estatus"], s["error"])
        for m in mensajes:
            ult10 = whatsapp_meta.ultimos_10(m["telefono"])
            ref = db.empresa_de_ultimo_envio_whatsapp(ult10)
            if not ref:
                continue
            cliente = db.buscar_cliente_crm_por_ultimos10(ref["empresa_id"], ult10)
            if cliente:
                db.crear_interaccion_crm(ref["empresa_id"], cliente["id"], None, "whatsapp",
                                         f"Cliente respondió: {m['texto']}", None)
    except Exception as e:
        print(f"[whatsapp_meta] error procesando webhook: {e}")
    return {"ok": True}


# ---- Cliente aceptó la cotización: datos fiscales (con IA) y flete ----
# Desde el Cotizador visual (y Realizadas): el vendedor marca que el cliente
# aceptó → la cotización pasa a Vendida (si no viene del CRM) → si factura,
# captura sus datos fiscales (a mano o leyendo la Constancia de Situación
# Fiscal con IA); si no, solo su código postal. Con el CP y la ubicación del
# vendedor se calculan las horas de manejo (solo ida) y se agrega el
# renglón "Flete en instalación" = horas × precio por hora de la empresa.

class AceptarCotizacionIn(BaseModel):
    requiere_factura: bool
    rfc: Optional[str] = None
    razon_social: Optional[str] = None
    regimen_fiscal: Optional[str] = None
    uso_cfdi: Optional[str] = None
    codigo_postal: Optional[str] = None
    domicilio_fiscal: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    correo_factura: Optional[str] = None
    constancia_base64: Optional[str] = None
    constancia_nombre: Optional[str] = None


class LeerConstanciaIn(BaseModel):
    archivo: str = Field(min_length=10)
    nombre: Optional[str] = None


class FleteIn(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    cp_origen: Optional[str] = None
    codigo_postal: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None


class FleteConfigIn(BaseModel):
    precio_hora: float = Field(ge=0, le=1_000_000)


def _cotizacion_del_vendedor(usuario: dict, cotizacion_id: int) -> dict:
    cotizacion = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and cotizacion["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes modificar esta cotización")
    return cotizacion


def _limpio(v):
    v = " ".join(str(v).split()) if v is not None else ""
    return v or None


def _estado_aceptacion(usuario: dict, cotizacion: dict) -> dict:
    empresa_id = usuario["empresa_id"]
    cliente = db.obtener_cliente_crm(empresa_id, cotizacion["cliente_crm_id"]) if cotizacion.get("cliente_crm_id") else None
    constancia = db.obtener_constancia_fiscal(empresa_id, cliente["id"]) if cliente else None
    try:
        flete_actual = json.loads(cotizacion.get("flete_json")) if cotizacion.get("flete_json") else None
    except (TypeError, ValueError):
        flete_actual = None
    return {
        "cotizacion": {
            "id": cotizacion["id"], "folio": cotizacion["folio"], "cliente_nombre": cotizacion["cliente_nombre"],
            "cliente_telefono": cotizacion.get("cliente_telefono"), "estatus": cotizacion.get("estatus"),
            "aceptada_en": cotizacion.get("aceptada_en"), "requiere_factura": cotizacion.get("requiere_factura"),
            "bloqueada_crm": bool(cotizacion.get("oportunidad_id")), "total": cotizacion.get("total"),
            "cliente_crm_id": cotizacion.get("cliente_crm_id"),
        },
        "cliente": {k: cliente.get(k) for k in ("id", "nombre", "telefono") + db.CAMPOS_FISCALES_CLIENTE} if cliente else None,
        "constancia": constancia,
        "flete": {
            "precio_hora": db.obtener_flete_precio_hora(empresa_id),
            "ruta_configurada": facturacion_flete.ruta_configurada(),
            "nombre_item": facturacion_flete.NOMBRE_ITEM_FLETE,
            "actual": flete_actual,
        },
        "catalogos": {"regimenes": facturacion_flete.REGIMENES_FISCALES, "usos_cfdi": facturacion_flete.USOS_CFDI},
        "microsip": _estado_microsip_cotizacion(empresa_id, cotizacion),
    }


@app.get("/api/cotizaciones/{cotizacion_id}/aceptacion")
def api_cotizacion_aceptacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    return _estado_aceptacion(usuario, _cotizacion_del_vendedor(usuario, cotizacion_id))


@app.post("/api/cotizaciones/{cotizacion_id}/aceptar")
def api_cotizacion_aceptar(cotizacion_id: int, payload: AceptarCotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    empresa_id = usuario["empresa_id"]
    cotizacion = _cotizacion_del_vendedor(usuario, cotizacion_id)
    rfc = (_limpio(payload.rfc) or "").upper().replace(" ", "").replace("-", "") or None
    cp = _limpio(payload.codigo_postal)
    regimen = _limpio(payload.regimen_fiscal)
    uso = _limpio(payload.uso_cfdi) or "G03"
    if cp and not facturacion_flete.cp_valido(cp):
        raise HTTPException(status_code=400, detail="El código postal debe tener 5 dígitos.")
    if payload.requiere_factura:
        faltan = [n for n, v in (("RFC", rfc), ("razón social", _limpio(payload.razon_social)),
                                 ("régimen fiscal", regimen), ("código postal", cp)) if not v]
        if faltan:
            raise HTTPException(status_code=400, detail="Para facturar falta: " + ", ".join(faltan) + ".")
        if not facturacion_flete.rfc_valido(rfc):
            raise HTTPException(status_code=400, detail="El RFC no tiene el formato correcto (12 o 13 caracteres).")
        if regimen not in facturacion_flete.REGIMENES_FISCALES:
            raise HTTPException(status_code=400, detail="Elige un régimen fiscal de la lista.")
        if uso not in facturacion_flete.USOS_CFDI:
            raise HTTPException(status_code=400, detail="Elige un uso de CFDI de la lista.")
    if payload.constancia_base64 and len(payload.constancia_base64) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La constancia pesa demasiado (máximo ~5MB).")
    ms = _estado_microsip_cotizacion(empresa_id, cotizacion)
    if ms["activa"] and not ms["folio"] and ms["faltantes"]:
        raise HTTPException(status_code=400, detail="Para aceptar, todos los productos deben estar ligados a un artículo de Microsip. "
                            "Falta: " + "; ".join(ms["faltantes"]) + ". Edita la cotización y búscalos en Microsip.")

    cliente_id = db.asegurar_cliente_de_cotizacion(empresa_id, cotizacion, usuario["id"])
    datos = {"requiere_factura": payload.requiere_factura}
    for k in ("codigo_postal", "municipio", "estado"):
        v = _limpio(getattr(payload, k))
        if v or payload.requiere_factura:
            datos[k] = v
    if payload.requiere_factura:
        datos.update({"rfc": rfc, "razon_social": (_limpio(payload.razon_social) or "").upper(), "regimen_fiscal": regimen,
                      "uso_cfdi": uso, "domicilio_fiscal": _limpio(payload.domicilio_fiscal),
                      "correo_factura": _limpio(payload.correo_factura)})
    db.guardar_datos_fiscales_cliente(empresa_id, cliente_id, datos)
    if payload.constancia_base64:
        db.guardar_constancia_fiscal(cliente_id, _limpio(payload.constancia_nombre) or "constancia.pdf",
                                     payload.constancia_base64, usuario["id"])
    actualizada = db.marcar_cotizacion_aceptada(empresa_id, cotizacion_id, usuario["id"], payload.requiere_factura,
                                                marcar_vendida=not cotizacion.get("oportunidad_id"))
    try:
        db.crear_interaccion_crm(empresa_id, cliente_id, None, "nota",
                                 f"Aceptó la cotización {cotizacion['folio']} ({'con' if payload.requiere_factura else 'sin'} factura)",
                                 usuario["id"])
    except Exception as e:
        print(f"[aceptar cotizacion] no se pudo registrar en el CRM: {e}")
    return _estado_aceptacion(usuario, actualizada)


# ---- Cliente aceptó → Microsip: alta/corrección del cliente y su cotización ----
# Al aceptar, el cliente se busca en Microsip (mismo RFC, mismo teléfono o
# nombre parecido). Si hay parecidos el vendedor elige "es este" (se ligan y
# en Microsip solo se llenan los datos que estén vacíos) o "es nuevo" (se da
# de alta). Luego se crea la cotización en Microsip con los mismos artículos
# a precio de lista de Microsip. Todo o nada: si algo falla no queda nada a
# medias, y se puede reintentar.

class EnviarMicrosipIn(BaseModel):
    microsip_cliente_id: Optional[int] = None
    nuevo: bool = False
    probar: bool = False


class ConfigMicrosipEscrituraIn(BaseModel):
    activa: bool = False
    usuario: Optional[str] = None
    password: Optional[str] = None  # None = no cambiarla; "" = borrarla
    articulo_flete_id: Optional[int] = None
    articulo_flete_nombre: Optional[str] = None


def _es_item_flete(it):
    return not it.get("articulo_id") and ((it.get("nombre") or "").strip() == facturacion_flete.NOMBRE_ITEM_FLETE
                                           or (it.get("clave") or "").strip().upper() in ("FLETE",) + paqueterias.claves_item())


def _partidas_microsip(cfg, cotizacion):
    """(partidas para Microsip, nombres de los productos que no están ligados)."""
    partidas, faltantes = [], []
    flete_id = (cfg or {}).get("microsip_articulo_flete_id")
    for it in cotizacion.get("items") or []:
        cantidad = float(it.get("cantidad") or 0)
        if cantidad <= 0:
            continue
        nombre = (it.get("nombre") or "").strip() or "(sin nombre)"
        if it.get("articulo_id"):
            partidas.append({"articulo_id": int(it["articulo_id"]), "cantidad": cantidad, "nombre": nombre, "nota": it.get("nota")})
        elif _es_item_flete(it) and flete_id:
            partidas.append({"articulo_id": int(flete_id), "cantidad": cantidad, "nombre": nombre, "nota": it.get("nota")})
        elif _es_item_flete(it):
            faltantes.append(f"{nombre} (el admin debe elegir el artículo de flete en Administrar → Microsip)")
        else:
            faltantes.append(nombre)
    return partidas, faltantes


def _estado_microsip_cotizacion(empresa_id, cotizacion):
    """Lo que sabe la app sin tocar Microsip (rápido)."""
    cfg = db.obtener_config_microsip_escritura(empresa_id) if MICROSIP_DISPONIBLE else None
    activa = bool(cfg and cfg.get("microsip_escritura_activa") and cfg.get("microsip_host"))
    _, faltantes = _partidas_microsip(cfg, cotizacion)
    return {"activa": activa, "folio": cotizacion.get("microsip_folio"), "enviada_en": cotizacion.get("microsip_enviada_en"),
            "error": cotizacion.get("microsip_error"), "faltantes": faltantes}


def _datos_cliente_para_microsip(empresa_id, cotizacion):
    cliente = db.obtener_cliente_crm(empresa_id, cotizacion["cliente_crm_id"]) if cotizacion.get("cliente_crm_id") else {}
    cliente = cliente or {}
    factura = bool(cotizacion.get("requiere_factura"))
    return cliente, {
        "nombre": cotizacion.get("cliente_nombre") or cliente.get("nombre"),
        "razon_social": cliente.get("razon_social") if factura else None,
        "rfc": cliente.get("rfc") if factura else None,
        "telefono": cotizacion.get("cliente_telefono") or cliente.get("telefono"),
        "email": cliente.get("correo_factura") or cliente.get("email"),
        "domicilio": cliente.get("domicilio_fiscal") or cotizacion.get("cliente_direccion") or cliente.get("direccion"),
        "municipio": cliente.get("municipio"), "estado": cliente.get("estado"),
        "codigo_postal": cliente.get("codigo_postal"),
        "regimen_fiscal": cliente.get("regimen_fiscal") if factura else None,
        "uso_cfdi": cliente.get("uso_cfdi") if factura else None,
    }


def _config_escritura_o_error(empresa_id):
    _requiere_microsip_disponible()
    cfg = db.obtener_config_microsip_escritura(empresa_id)
    if not cfg or not cfg.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado todavía (Administrar → Microsip).")
    return cfg


def _similares_microsip(cfg, datos):
    nombres = [n for n in dict.fromkeys([datos.get("razon_social"), datos.get("nombre")]) if n]
    vistos = {}
    for i, nombre in enumerate(nombres):
        for c in microsip_escritura.buscar_similares(cfg, nombre, datos.get("rfc") if i == 0 else None,
                                                     datos.get("telefono") if i == 0 else None):
            previo = vistos.get(c["cliente_id"])
            if not previo:
                vistos[c["cliente_id"]] = c
            else:
                previo["motivos"] = list(dict.fromkeys(previo["motivos"] + c["motivos"]))
                previo["puntaje"] = max(previo["puntaje"], c["puntaje"])
    for c in vistos.values():
        # Si se buscó por nombre y por razón social, dejar solo el mejor "Nombre parecido (N%)".
        nombres = [m for m in c["motivos"] if m.startswith("Nombre parecido")]
        if len(nombres) > 1:
            mejor = max(nombres, key=lambda m: int("".join(ch for ch in m if ch.isdigit()) or 0))
            c["motivos"] = [m for m in c["motivos"] if not m.startswith("Nombre parecido") or m == mejor]
    return sorted(vistos.values(), key=lambda c: -c["puntaje"])[:8]


@app.get("/api/cotizaciones/{cotizacion_id}/microsip")
def api_cotizacion_microsip_estado(cotizacion_id: int, buscar: bool = True, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Estado del envío a Microsip y, si el cliente aún no está ligado, sus
    parecidos en Microsip para que el vendedor elija."""
    empresa_id = usuario["empresa_id"]
    cotizacion = _cotizacion_del_vendedor(usuario, cotizacion_id)
    r = _estado_microsip_cotizacion(empresa_id, cotizacion)
    r.update(cliente_ligado=None, similares=[], error_conexion=None)
    if not buscar or r["folio"] or not MICROSIP_DISPONIBLE:
        return r
    cfg = db.obtener_config_microsip_escritura(empresa_id)
    if not cfg or not cfg.get("microsip_host"):
        return r
    cliente, datos = _datos_cliente_para_microsip(empresa_id, cotizacion)
    try:
        if cliente.get("microsip_cliente_id"):
            r["cliente_ligado"] = microsip_escritura.leer_cliente(cfg, cliente["microsip_cliente_id"])
        if not r["cliente_ligado"]:
            r["similares"] = _similares_microsip(cfg, datos)
    except Exception as e:
        r["error_conexion"] = f"No se pudo consultar Microsip: {e}"
    return r


@app.post("/api/cotizaciones/{cotizacion_id}/microsip")
def api_cotizacion_microsip_enviar(cotizacion_id: int, payload: EnviarMicrosipIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Crea (o completa) el cliente y la cotización en Microsip.
    Si hay clientes parecidos y el vendedor no ha elegido, regresa
    {"estado": "elegir_cliente", "similares": [...]} sin escribir nada."""
    empresa_id = usuario["empresa_id"]
    cotizacion = _cotizacion_del_vendedor(usuario, cotizacion_id)
    cfg = _config_escritura_o_error(empresa_id)
    if not payload.probar:
        if not cfg.get("microsip_escritura_activa"):
            raise HTTPException(status_code=400, detail="El envío a Microsip está apagado (Administrar → Microsip → Enviar cotizaciones aceptadas).")
        if not cotizacion.get("aceptada_en"):
            raise HTTPException(status_code=400, detail="Primero marca que el cliente aceptó la cotización.")
        if cotizacion.get("microsip_folio"):
            raise HTTPException(status_code=409, detail=f"Esta cotización ya está en Microsip como {cotizacion['microsip_folio']}.")
    partidas, faltantes = _partidas_microsip(cfg, cotizacion)
    if faltantes:
        raise HTTPException(status_code=400, detail="Todos los productos deben estar ligados a Microsip. Falta: " + "; ".join(faltantes) + ".")
    if not partidas:
        raise HTTPException(status_code=400, detail="La cotización no tiene productos.")
    cliente, datos = _datos_cliente_para_microsip(empresa_id, cotizacion)

    ms_cliente_id = payload.microsip_cliente_id
    if not ms_cliente_id and not payload.nuevo:
        ms_cliente_id = cliente.get("microsip_cliente_id")
        if ms_cliente_id:
            try:
                if not microsip_escritura.leer_cliente(cfg, ms_cliente_id):
                    ms_cliente_id = None  # lo borraron en Microsip: se vuelve a buscar
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {e}")
        if not ms_cliente_id:
            try:
                similares = _similares_microsip(cfg, datos)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {e}")
            if similares:
                return {"estado": "elegir_cliente", "similares": similares}

    folio_app = cotizacion.get("folio") or cotizacion_id
    try:
        r = microsip_escritura.enviar_cotizacion(
            cfg, datos_cliente=datos, partidas=partidas, cliente_id=ms_cliente_id, probar=payload.probar,
            descripcion=f"App tickets-ti {folio_app} — {usuario.get('nombre_completo') or usuario.get('username') or ''}".strip(" —"))
    except microsip_escritura.ErrorMicrosip as e:
        if not payload.probar:
            db.marcar_cotizacion_microsip(empresa_id, cotizacion_id, usuario["id"], error=str(e))
        raise HTTPException(status_code=400, detail=f"Microsip no aceptó el envío — {e}")
    except Exception as e:
        if not payload.probar:
            db.marcar_cotizacion_microsip(empresa_id, cotizacion_id, usuario["id"], error=str(e))
        raise HTTPException(status_code=400, detail=f"No se pudo enviar a Microsip: {e}")

    if not payload.probar:
        detalle = (f"Cotización {r['folio']} creada en Microsip para "
                   f"{'cliente NUEVO ' if r['cliente_creado'] else ''}{r['cliente_nombre']}"
                   + (f" (se completó: {', '.join(r['campos_completados'])})" if r["campos_completados"] else ""))
        db.marcar_cotizacion_microsip(empresa_id, cotizacion_id, usuario["id"], docto_id=r["docto_ve_id"], folio=r["folio"],
                                      cliente_crm_id=cliente.get("id"), microsip_cliente_id=r["cliente_id"], detalle=detalle)
        if cliente.get("id"):
            try:
                db.crear_interaccion_crm(empresa_id, cliente["id"], None, "nota", detalle, usuario["id"])
            except Exception as e:
                print(f"[microsip] no se pudo registrar en el CRM: {e}")
    return {"estado": "probado" if payload.probar else "enviada", **r}


@app.get("/api/microsip/escritura")
def api_config_microsip_escritura(usuario: dict = Depends(requiere_admin_completo)):
    cfg = db.obtener_config_microsip_escritura(usuario["empresa_id"]) or {}
    return {"activa": bool(cfg.get("microsip_escritura_activa")), "usuario": cfg.get("microsip_escritura_usuario"),
            "tiene_password": bool(cfg.get("microsip_escritura_password")),
            "articulo_flete_id": cfg.get("microsip_articulo_flete_id"),
            "articulo_flete_nombre": cfg.get("microsip_articulo_flete_nombre")}


@app.put("/api/microsip/escritura")
def api_guardar_config_microsip_escritura(payload: ConfigMicrosipEscrituraIn, usuario: dict = Depends(requiere_admin_completo)):
    db.guardar_config_microsip_escritura(usuario["empresa_id"], payload.activa, _limpio(payload.usuario), payload.password,
                                         payload.articulo_flete_id, _limpio(payload.articulo_flete_nombre))
    return api_config_microsip_escritura(usuario)


class ConfigMicrosipLabIn(BaseModel):
    activa: bool = False
    sucursal_id: Optional[int] = None
    sucursal_nombre: Optional[str] = None
    almacen_id: Optional[int] = None
    almacen_nombre: Optional[str] = None
    usuario: Optional[str] = Field(default=None, max_length=31)
    articulos: dict = Field(default_factory=dict)  # {"zirconia": {"id": .., "nombre": ..}, "disilicato": .., "otro": ..}


@app.get("/api/microsip/laboratorio")
def api_config_microsip_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    cfg = db.obtener_config_microsip_escritura(usuario["empresa_id"]) or {}
    return {"activa": bool(cfg.get("lab_microsip_activa")),
            "sucursal_id": cfg.get("lab_microsip_sucursal_id"), "sucursal_nombre": cfg.get("lab_microsip_sucursal_nombre"),
            "almacen_id": cfg.get("lab_microsip_almacen_id"), "almacen_nombre": cfg.get("lab_microsip_almacen_nombre"),
            "usuario": cfg.get("lab_microsip_usuario"), "articulos": _articulos_lab(cfg),
            "materiales": db.MATERIALES_LABORATORIO + ["otro"]}


@app.put("/api/microsip/laboratorio")
def api_guardar_config_microsip_laboratorio(payload: ConfigMicrosipLabIn, usuario: dict = Depends(requiere_admin_completo)):
    if payload.activa and (not payload.sucursal_id or not payload.almacen_id):
        raise HTTPException(status_code=400, detail="Para activarlo elige la sucursal y el almacén del laboratorio.")
    articulos = {}
    for k, v in (payload.articulos or {}).items():
        if k in db.MATERIALES_LABORATORIO + ["otro"] and isinstance(v, dict) and v.get("id"):
            articulos[k] = {"id": int(v["id"]), "nombre": _limpio(v.get("nombre"))}
    if payload.activa and not articulos:
        raise HTTPException(status_code=400, detail="Elige al menos un artículo de Microsip (por material u \"otro\").")
    db.guardar_config_microsip_laboratorio(usuario["empresa_id"], payload.activa, payload.sucursal_id, _limpio(payload.sucursal_nombre),
                                           payload.almacen_id, _limpio(payload.almacen_nombre),
                                           (_limpio(payload.usuario) or "").upper() or None, articulos)
    return api_config_microsip_laboratorio(usuario)


@app.get("/api/microsip/laboratorio/opciones")
def api_opciones_microsip_laboratorio(usuario: dict = Depends(requiere_admin_completo)):
    """Sucursales y almacenes de Microsip para elegir los del laboratorio."""
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado todavía.")
    try:
        return {"sucursales": microsip.listar_sucursales_venta(config), "almacenes": microsip.listar_almacenes(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {e}")


@app.post("/api/microsip/escritura/diagnostico")
def api_diagnostico_microsip_escritura(usuario: dict = Depends(requiere_admin_completo)):
    """Revisa que se pueda escribir y hace una prueba completa (cliente +
    cotización) que se deshace al final — no deja nada en Microsip."""
    cfg = _config_escritura_o_error(usuario["empresa_id"])
    try:
        return microsip_escritura.diagnostico(cfg, cfg.get("microsip_articulo_flete_id"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"El diagnóstico falló: {e}")


class UsuariosMicrosipIn(BaseModel):
    ruta_config: Optional[str] = Field(default=None, max_length=300)


@app.post("/api/microsip/usuarios")
def api_usuarios_microsip(payload: UsuariosMicrosipIn, usuario: dict = Depends(requiere_admin_completo)):
    """Usuarios de Microsip, sus roles, empresas y derechos (solo lectura, de System\\Config.fdb)."""
    cfg = _config_escritura_o_error(usuario["empresa_id"])
    try:
        datos = microsip_usuarios.leer_config(cfg, _limpio(payload.ruta_config))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        datos["firebird"] = microsip_usuarios.permisos_firebird(cfg)
    except Exception as e:
        datos["firebird"] = {"error": str(e)}
    return datos


@app.get("/api/microsip/lote-serie-faltante")
def api_lote_serie_faltante(usuario: dict = Depends(requiere_admin_completo)):
    """Artículos con seguimiento por lote/serie cuya existencia no tiene lote/serie asignado, por almacén."""
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado todavía.")
    try:
        return microsip_lotes.articulos_sin_lote_serie(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo consultar Microsip: {e}")


class LeerQrIn(BaseModel):
    texto: str = Field(min_length=10, max_length=2000)


@app.post("/api/laboratorio/mios-leer-qr")
def api_leer_qr_constancia_lab(payload: LeerQrIn, usuario: dict = Depends(requiere_estudiante_laboratorio)):
    try:
        return facturacion_flete.leer_qr(payload.texto)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/laboratorio/mios-leer-constancia")
def api_leer_constancia_lab(payload: LeerConstanciaIn, usuario: dict = Depends(requiere_estudiante_laboratorio)):
    if len(payload.archivo) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La constancia pesa demasiado (máximo ~5MB).")
    try:
        return facturacion_flete.leer_constancia(payload.archivo, usuario["empresa_id"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


class FleteCalcularIn(BaseModel):
    codigo_postal: str
    municipio: Optional[str] = None
    estado: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    cp_origen: Optional[str] = None


@app.post("/api/facturacion/leer-qr")
def api_leer_qr_constancia(payload: LeerQrIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Texto del QR de la Constancia de Situación Fiscal (escaneado con la
    cámara) → datos del SAT."""
    try:
        return facturacion_flete.leer_qr(payload.texto)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/flete/calcular")
def api_flete_calcular(payload: FleteCalcularIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Flete de instalación al cotizar (antes de crear la cotización): horas de
    manejo solo ida × precio por hora de la empresa."""
    precio_hora = db.obtener_flete_precio_hora(usuario["empresa_id"])
    if precio_hora <= 0:
        raise HTTPException(status_code=400, detail="Falta el precio por hora del flete — el administrador lo pone en Cotizador visual (🚚 Flete).")
    try:
        return facturacion_flete.calcular_flete(
            (payload.codigo_postal or "").strip(), _limpio(payload.municipio), _limpio(payload.estado),
            payload.lat, payload.lng, (payload.cp_origen or "").strip() or None, precio_hora)
    except facturacion_flete.ErrorFlete as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/facturacion/leer-constancia")
def api_leer_constancia(payload: LeerConstanciaIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    if len(payload.archivo) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La constancia pesa demasiado (máximo ~5MB).")
    try:
        return facturacion_flete.leer_constancia(payload.archivo, usuario["empresa_id"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/cotizaciones/{cotizacion_id}/constancia")
def api_descargar_constancia(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    cotizacion = _cotizacion_del_vendedor(usuario, cotizacion_id)
    k = db.obtener_constancia_fiscal(usuario["empresa_id"], cotizacion["cliente_crm_id"], con_archivo=True) \
        if cotizacion.get("cliente_crm_id") else None
    if not k:
        raise HTTPException(status_code=404, detail="Este cliente no tiene constancia guardada")
    datos, media_type = ia._decodificar_base64(k["archivo_base64"], "application/pdf")
    return Response(content=datos, media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={k['nombre_archivo'] or 'constancia.pdf'}"})


@app.post("/api/cotizaciones/{cotizacion_id}/flete")
def api_cotizacion_flete(cotizacion_id: int, payload: FleteIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    empresa_id = usuario["empresa_id"]
    cotizacion = _cotizacion_del_vendedor(usuario, cotizacion_id)
    precio_hora = db.obtener_flete_precio_hora(empresa_id)
    if precio_hora <= 0:
        raise HTTPException(status_code=400, detail="Falta el precio por hora del flete — el administrador lo pone en Cotizador visual (🚚 Flete).")

    cp = _limpio(payload.codigo_postal)
    municipio, estado = _limpio(payload.municipio), _limpio(payload.estado)
    cliente = db.obtener_cliente_crm(empresa_id, cotizacion["cliente_crm_id"]) if cotizacion.get("cliente_crm_id") else None
    if cp and not facturacion_flete.cp_valido(cp):
        raise HTTPException(status_code=400, detail="El código postal del cliente debe tener 5 dígitos.")
    cp_destino = cp or (cliente or {}).get("codigo_postal")
    if not cp_destino:
        raise HTTPException(status_code=400, detail="Escribe el código postal del cliente.")
    if cp and cp != (cliente or {}).get("codigo_postal"):
        # CP nuevo: no usar municipio/estado viejos del cliente (pueden ser de otro lado)
        municipio_d, estado_d = municipio, estado
    else:
        municipio_d = municipio or (cliente or {}).get("municipio")
        estado_d = estado or (cliente or {}).get("estado")

    try:
        if payload.lat is not None and payload.lng is not None:
            origen = (payload.lat, payload.lng)
            origen_texto = "tu ubicación"
        elif facturacion_flete.cp_valido(payload.cp_origen or ""):
            lat, lng, _ = facturacion_flete.geocodificar_cp(payload.cp_origen.strip())
            origen = (lat, lng)
            origen_texto = f"CP {payload.cp_origen.strip()}"
        else:
            raise HTTPException(status_code=400, detail="Activa la ubicación o escribe el código postal de donde sales.")
        lat, lng, destino_texto = facturacion_flete.geocodificar_cp(cp_destino, municipio_d, estado_d)
        ruta = facturacion_flete.tiempo_manejo(origen, (lat, lng))
    except facturacion_flete.ErrorFlete as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ya se ubicó: ahora sí se guarda el CP (y municipio/estado) en el cliente.
    if cp:
        cliente_id = db.asegurar_cliente_de_cotizacion(empresa_id, cotizacion, usuario["id"])
        cambios = {"codigo_postal": cp}
        if municipio:
            cambios["municipio"] = municipio
        if estado:
            cambios["estado"] = estado
        db.guardar_datos_fiscales_cliente(empresa_id, cliente_id, cambios)
    cliente = {"codigo_postal": cp_destino}

    horas = facturacion_flete.redondear_horas(ruta["horas"])
    km = round(ruta["km"], 1)
    nota = f"Solo ida: {km:g} km desde {origen_texto} hasta CP {cliente['codigo_postal']}"
    info = {"horas": horas, "horas_exactas": round(ruta["horas"], 3), "km": km, "precio_hora": precio_hora,
            "origen": origen_texto, "destino_cp": cliente["codigo_postal"], "destino": destino_texto,
            "calculado_en": db.ahora().isoformat(timespec="seconds")}
    actualizada = db.poner_item_flete_cotizacion(empresa_id, cotizacion_id, usuario["id"],
                                                 facturacion_flete.NOMBRE_ITEM_FLETE, horas, precio_hora, nota, info)
    return {"flete": info, "importe": round(horas * precio_hora, 2), "cotizacion": actualizada}


@app.get("/api/cotizador-visual/flete-config")
def api_flete_config(usuario: dict = Depends(requiere_ver_checador_precio)):
    return {"precio_hora": db.obtener_flete_precio_hora(usuario["empresa_id"]),
            "ruta_configurada": facturacion_flete.ruta_configurada()}


@app.put("/api/cotizador-visual/flete-config")
def api_guardar_flete_config(payload: FleteConfigIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador cambia el precio del flete")
    db.guardar_flete_precio_hora(usuario["empresa_id"], payload.precio_hora)
    return {"precio_hora": payload.precio_hora}


# ---- Paquetería Estafeta: cotizar envío, guía y rastreo (ver estafeta.py) ----

class EstafetaConfigIn(BaseModel):
    margen_pct: float = Field(ge=0, le=500)


class EstafetaOrigenIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    contacto: Optional[str] = None
    telefono: Optional[str] = None
    calle: Optional[str] = None
    numero: Optional[str] = None
    colonia: Optional[str] = None
    cp: str
    ciudad: Optional[str] = None
    estado: Optional[str] = None
    referencia: Optional[str] = None
    activo: bool = True


class EstafetaPaqueteIn(BaseModel):
    peso: float
    largo: float
    ancho: float
    alto: float


class EstafetaCotizarIn(BaseModel):
    origen_id: int
    cp_destino: str
    paquete: EstafetaPaqueteIn


class EstafetaDestinoIn(BaseModel):
    nombre: str
    contacto: Optional[str] = None
    telefono: str
    correo: Optional[str] = None
    calle: str
    numero: Optional[str] = None
    colonia: str
    cp: str
    ciudad: str
    estado: str
    referencia: Optional[str] = None


class EstafetaGuiaIn(BaseModel):
    origen_id: int
    servicio_id: str
    servicio: Optional[str] = None
    paquete: EstafetaPaqueteIn
    destino: EstafetaDestinoIn
    contenido: Optional[str] = None


def _solo_admin(usuario, que):
    if usuario["rol"] != "admin":
        raise HTTPException(status_code=403, detail=f"Solo el administrador {que}")


def _origen_estafeta(empresa_id, origen_id):
    o = db.obtener_origen_estafeta(empresa_id, origen_id)
    if not o or not o.get("activo"):
        raise HTTPException(status_code=400, detail="Elige la sucursal de donde sale el paquete.")
    return o


def _origen_para_guia(o):
    return {k: (o.get(k) or "") for k in ("nombre", "contacto", "telefono", "calle", "numero", "colonia", "cp", "ciudad", "estado", "referencia")}


@app.get("/api/estafeta/config")
def api_estafeta_config(usuario: dict = Depends(requiere_ver_checador_precio)):
    es_admin = usuario["rol"] == "admin"
    return {"estado": estafeta.estado(), "margen_pct": db.obtener_estafeta_margen(usuario["empresa_id"]),
            "origenes": db.listar_origenes_estafeta(usuario["empresa_id"], solo_activos=not es_admin),
            "nombre_item": estafeta.NOMBRE_ITEM, "clave_item": estafeta.CLAVE_ITEM}


@app.put("/api/estafeta/config")
def api_estafeta_guardar_config(payload: EstafetaConfigIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    _solo_admin(usuario, "cambia el margen de Estafeta")
    db.guardar_estafeta_margen(usuario["empresa_id"], payload.margen_pct)
    return {"margen_pct": payload.margen_pct}


def _validar_origen(payload: EstafetaOrigenIn):
    datos = {k: (_limpio(v) if isinstance(v, str) else v) for k, v in payload.model_dump().items()}
    if not estafeta.cp_valido(datos.get("cp")):
        raise HTTPException(status_code=400, detail="El código postal de la sucursal debe tener 5 dígitos.")
    return datos


@app.post("/api/estafeta/origenes")
def api_estafeta_crear_origen(payload: EstafetaOrigenIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    _solo_admin(usuario, "da de alta sucursales de envío")
    return db.guardar_origen_estafeta(usuario["empresa_id"], _validar_origen(payload))


@app.put("/api/estafeta/origenes/{origen_id}")
def api_estafeta_editar_origen(origen_id: int, payload: EstafetaOrigenIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    _solo_admin(usuario, "edita sucursales de envío")
    r = db.guardar_origen_estafeta(usuario["empresa_id"], _validar_origen(payload), origen_id)
    if not r:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return r


@app.delete("/api/estafeta/origenes/{origen_id}")
def api_estafeta_borrar_origen(origen_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    _solo_admin(usuario, "borra sucursales de envío")
    db.eliminar_origen_estafeta(usuario["empresa_id"], origen_id)
    return {"ok": True}


@app.post("/api/estafeta/cotizar")
def api_estafeta_cotizar(payload: EstafetaCotizarIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Precio del envío con las tarifas de la cuenta Estafeta + el margen de la empresa."""
    empresa_id = usuario["empresa_id"]
    o = _origen_estafeta(empresa_id, payload.origen_id)
    cp = (payload.cp_destino or "").strip()
    try:
        paquete = estafeta.limpiar_paquete(payload.paquete.model_dump())
        servicios = estafeta.cotizar(o["cp"], cp, paquete)
    except estafeta.ErrorEstafeta as e:
        raise HTTPException(status_code=400, detail=str(e))
    margen = db.obtener_estafeta_margen(empresa_id)
    for sv in servicios:
        sv["precio"] = estafeta.precio_con_margen(sv["costo"], margen)
    r = {"origen": {"id": o["id"], "nombre": o["nombre"], "cp": o["cp"]}, "cp_destino": cp, "paquete": paquete,
         "peso_volumetrico": estafeta.peso_volumetrico(paquete), "servicios": servicios,
         "simulado": estafeta.simulado(), "cotizado_en": db.ahora().isoformat(timespec="seconds")}
    if usuario["rol"] != "admin":
        for sv in servicios:
            sv.pop("costo", None)  # el vendedor ve el precio al cliente, no el costo
    return r


@app.get("/api/cotizaciones/{cotizacion_id}/estafeta")
def api_cotizacion_estafeta(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Lo necesario para generar la guía: envío elegido al cotizar, destino
    sugerido (datos del cliente) y guías ya hechas."""
    empresa_id = usuario["empresa_id"]
    cot = _cotizacion_del_vendedor(usuario, cotizacion_id)
    envio = None
    try:
        envio = json.loads(cot["envio_json"]) if cot.get("envio_json") else None
    except ValueError:
        pass
    cli = db.obtener_cliente_crm(empresa_id, cot["cliente_crm_id"]) if cot.get("cliente_crm_id") else None
    cli = cli or {}
    destino = {
        "nombre": cli.get("razon_social") or cli.get("nombre") or cot.get("cliente_nombre") or "",
        "contacto": cli.get("nombre") or cot.get("cliente_nombre") or "",
        "telefono": cli.get("telefono") or cot.get("cliente_telefono") or "",
        "correo": cli.get("correo_factura") or cli.get("email") or "",
        "calle": cli.get("direccion") or cot.get("cliente_direccion") or "",
        "numero": "", "colonia": "",
        "cp": (envio or {}).get("cp_destino") or cli.get("codigo_postal") or "",
        "ciudad": cli.get("municipio") or "", "estado": cli.get("estado") or "", "referencia": "",
    }
    return {"envio": envio, "destino_sugerido": destino, "guias": db.listar_guias_estafeta(empresa_id, cotizacion_id),
            "origenes": db.listar_origenes_estafeta(empresa_id, solo_activos=True), "estado": estafeta.estado()}


@app.post("/api/cotizaciones/{cotizacion_id}/estafeta/guia")
def api_cotizacion_estafeta_guia(cotizacion_id: int, payload: EstafetaGuiaIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    empresa_id = usuario["empresa_id"]
    cot = _cotizacion_del_vendedor(usuario, cotizacion_id)
    o = _origen_estafeta(empresa_id, payload.origen_id)
    origen = _origen_para_guia(o)
    destino = {k: (_limpio(v) or "") for k, v in payload.destino.model_dump().items()}
    paquete = payload.paquete.model_dump()
    try:
        g = estafeta.generar_guia(origen, destino, paquete, payload.servicio_id, cot.get("folio"),
                                  _limpio(payload.contenido) or "Equipo dental")
    except estafeta.ErrorEstafeta as e:
        raise HTTPException(status_code=400, detail=str(e))
    gid = db.guardar_guia_estafeta(empresa_id, cotizacion_id, usuario["id"], g, payload.servicio or payload.servicio_id,
                                   origen, destino, paquete)
    return {"id": gid, "numero_guia": g["guia"], "simulada": g.get("simulada", False), "url_rastreo": estafeta.url_rastreo(g["guia"]),
            "guias": db.listar_guias_estafeta(empresa_id, cotizacion_id)}


def _guia_de_usuario(usuario, guia_id, con_pdf=False):
    g = db.obtener_guia_estafeta(usuario["empresa_id"], guia_id, con_pdf=con_pdf)
    if not g:
        raise HTTPException(status_code=404, detail="Guía no encontrada")
    if g.get("cotizacion_id"):
        _cotizacion_del_vendedor(usuario, g["cotizacion_id"])
    return g


@app.get("/api/estafeta/guias/{guia_id}/pdf")
def api_estafeta_guia_pdf(guia_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    g = _guia_de_usuario(usuario, guia_id, con_pdf=True)
    return Response(content=base64.b64decode(g["pdf_base64"]), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=guia_estafeta_{g['numero_guia']}.pdf"})


@app.get("/api/estafeta/guias/{guia_id}/rastreo")
def api_estafeta_guia_rastreo(guia_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    g = _guia_de_usuario(usuario, guia_id)
    try:
        r = estafeta.rastrear(g["codigo_rastreo"] or g["numero_guia"], simulada=g.get("simulada"), creada_en=g.get("creado_en"))
    except estafeta.ErrorEstafeta as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.guardar_estatus_guia_estafeta(guia_id, r["estatus"])
    return {"numero_guia": g["numero_guia"], "simulada": g.get("simulada"), **r}


# ---- Varias paqueterías (Estafeta, Paquetexpress, Castores): ver paqueterias.py ----
# Los /api/estafeta/* de arriba se quedan para las versiones anteriores de la app.

class PaqueteriaConfigIn(BaseModel):
    margenes: Dict[str, float]


class PaqueteriaGuiaIn(EstafetaGuiaIn):
    paqueteria: str = "estafeta"


def _paqueteria(clave):
    try:
        return paqueterias.obtener(clave)
    except paqueterias.ErrorEnvio as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/paqueteria/config")
def api_paqueteria_config(usuario: dict = Depends(requiere_ver_checador_precio)):
    es_admin = usuario["rol"] == "admin"
    margenes = db.obtener_margenes_paqueteria(usuario["empresa_id"])
    lista = [dict(p, margen_pct=margenes.get(p["clave"], 0.0)) for p in paqueterias.estados()]
    if not es_admin:
        for p in lista:
            p.pop("margen_pct", None)
            p["estado"] = {k: p["estado"][k] for k in ("modo", "conectada", "simulado")}
    return {"paqueterias": lista, "origenes": db.listar_origenes_estafeta(usuario["empresa_id"], solo_activos=not es_admin)}


@app.put("/api/paqueteria/config")
def api_paqueteria_guardar_config(payload: PaqueteriaConfigIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    _solo_admin(usuario, "cambia el margen de las paqueterías")
    margenes = db.obtener_margenes_paqueteria(usuario["empresa_id"])
    for clave, pct in payload.margenes.items():
        if clave not in paqueterias.PAQUETERIAS:
            raise HTTPException(status_code=400, detail=f"Paquetería desconocida: {clave}")
        if pct < 0 or pct > 500:
            raise HTTPException(status_code=400, detail="El margen debe estar entre 0 y 500%.")
        margenes[clave] = float(pct)
    db.guardar_margenes_paqueteria(usuario["empresa_id"], margenes)
    return {"margenes": margenes}


@app.post("/api/paqueteria/cotizar")
def api_paqueteria_cotizar(payload: EstafetaCotizarIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    """Pregunta a la vez a todas las paqueterías conectadas; regresa los
    servicios del más barato al más caro (precio al cliente = costo + margen
    de esa paquetería)."""
    empresa_id = usuario["empresa_id"]
    o = _origen_estafeta(empresa_id, payload.origen_id)
    cp = (payload.cp_destino or "").strip()
    try:
        paquete = estafeta.limpiar_paquete(payload.paquete.model_dump())
        if not estafeta.cp_valido(cp):
            raise paqueterias.ErrorEnvio("El código postal del cliente debe tener 5 dígitos.")
        servicios, errores = paqueterias.cotizar_todas(o["cp"], cp, paquete)
    except (paqueterias.ErrorEnvio,) + paqueterias.ERRORES as e:
        raise HTTPException(status_code=400, detail=str(e))
    margenes = db.obtener_margenes_paqueteria(empresa_id)
    for sv in servicios:
        sv["precio"] = estafeta.precio_con_margen(sv["costo"], margenes.get(sv["paqueteria"], 0))
        sv["clave_servicio"] = f"{sv['paqueteria']}:{sv['servicio_id']}"
    servicios.sort(key=lambda sv: sv["precio"])
    if servicios:
        servicios[0]["mas_barato"] = True
    simuladas = [p.NOMBRE for p in paqueterias.PAQUETERIAS.values() if p.simulado()]
    if usuario["rol"] != "admin":
        for sv in servicios:
            sv.pop("costo", None)
    return {"origen": {"id": o["id"], "nombre": o["nombre"], "cp": o["cp"]}, "cp_destino": cp, "paquete": paquete,
            "peso_volumetrico": estafeta.peso_volumetrico(paquete), "servicios": servicios, "errores": errores,
            "simulado": bool(simuladas), "simuladas": simuladas, "cotizado_en": db.ahora().isoformat(timespec="seconds")}


@app.get("/api/cotizaciones/{cotizacion_id}/paqueteria")
def api_cotizacion_paqueteria(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    r = api_cotizacion_estafeta(cotizacion_id, usuario)
    r["paqueterias"] = [{"clave": p["clave"], "nombre": p["nombre"],
                         "estado": {k: p["estado"][k] for k in ("modo", "conectada", "simulado")}} for p in paqueterias.estados()]
    return r


@app.post("/api/cotizaciones/{cotizacion_id}/paqueteria/guia")
def api_cotizacion_paqueteria_guia(cotizacion_id: int, payload: PaqueteriaGuiaIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    empresa_id = usuario["empresa_id"]
    cot = _cotizacion_del_vendedor(usuario, cotizacion_id)
    paq = _paqueteria(payload.paqueteria)
    o = _origen_estafeta(empresa_id, payload.origen_id)
    origen = _origen_para_guia(o)
    destino = {k: (_limpio(v) or "") for k, v in payload.destino.model_dump().items()}
    paquete = payload.paquete.model_dump()
    try:
        g = paq.generar_guia(origen, destino, paquete, payload.servicio_id, cot.get("folio"),
                             _limpio(payload.contenido) or "Equipo dental")
    except paqueterias.ERRORES as e:
        raise HTTPException(status_code=400, detail=str(e))
    gid = db.guardar_guia_estafeta(empresa_id, cotizacion_id, usuario["id"], g, payload.servicio or payload.servicio_id,
                                   origen, destino, paquete, paqueteria=paq.CLAVE, nombre_paqueteria=paq.NOMBRE)
    return {"id": gid, "numero_guia": g["guia"], "paqueteria": paq.CLAVE, "simulada": g.get("simulada", False),
            "url_rastreo": paq.url_rastreo(g["guia"]), "guias": db.listar_guias_estafeta(empresa_id, cotizacion_id)}


@app.get("/api/paqueteria/guias/{guia_id}/pdf")
def api_paqueteria_guia_pdf(guia_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    g = _guia_de_usuario(usuario, guia_id, con_pdf=True)
    return Response(content=base64.b64decode(g["pdf_base64"]), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=guia_{g.get('paqueteria') or 'estafeta'}_{g['numero_guia']}.pdf"})


@app.get("/api/paqueteria/guias/{guia_id}/rastreo")
def api_paqueteria_guia_rastreo(guia_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    g = _guia_de_usuario(usuario, guia_id)
    paq = _paqueteria(g.get("paqueteria"))
    try:
        r = paq.rastrear(g["codigo_rastreo"] or g["numero_guia"], simulada=g.get("simulada"), creada_en=g.get("creado_en"))
    except paqueterias.ERRORES as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.guardar_estatus_guia_estafeta(guia_id, r["estatus"])
    return {"numero_guia": g["numero_guia"], "paqueteria": paq.CLAVE, "paqueteria_nombre": paq.NOMBRE,
            "simulada": g.get("simulada"), **r}


@app.put("/api/cotizaciones/{cotizacion_id}")
def api_actualizar_cotizacion(cotizacion_id: int, payload: CotizacionIn, usuario: dict = Depends(requiere_ver_checador_precio)):
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes editar esta cotización")
    resultado = db.actualizar_cotizacion(
        usuario["empresa_id"], cotizacion_id, payload.cliente_nombre, payload.cliente_direccion,
        payload.cliente_telefono, payload.notas, [item.model_dump() for item in payload.items],
        payload.tipo_cliente, payload.meses_msi,
    )
    return resultado


@app.delete("/api/cotizaciones/{cotizacion_id}")
def api_eliminar_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes eliminar esta cotización")
    db.eliminar_cotizacion(usuario["empresa_id"], cotizacion_id)
    return {"ok": True}


@app.get("/api/cotizaciones/{cotizacion_id}/imagen-visual")
def api_imagen_visual_cotizacion(cotizacion_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    """La foto del equipo armado de una cotización hecha en el Cotizador
    visual (para volver a descargarla / mandarla por WhatsApp)."""
    existente = db.obtener_cotizacion(usuario["empresa_id"], cotizacion_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if usuario["rol"] == "usuario" and existente["creado_por_id"] != usuario["id"]:
        raise HTTPException(status_code=403, detail="No puedes ver esta cotización")
    imagen = db.obtener_imagen_visual_cotizacion(cotizacion_id)
    if not imagen:
        raise HTTPException(status_code=404, detail="Esta cotización no tiene imagen de equipo armado")
    return {"imagen": imagen}


# ---- Cotizador visual: equipos armables (unidad + accesorios con foto) ----
# Cualquiera con acceso al Checador de precio puede COTIZAR con los equipos;
# solo el administrador de la empresa puede darlos de alta/editarlos.

MAX_KIT_VISUAL_JSON = 20_000_000  # ~15MB de fotos — el navegador ya las reduce antes de mandarlas


class KitVisualIn(BaseModel):
    nombre: str = Field(min_length=1)
    activo: bool = True
    miniatura: Optional[str] = None
    config: dict


def _validar_kit_visual(payload: KitVisualIn):
    config = payload.config or {}
    base = config.get("base") or {}
    if not (base.get("nombre") or "").strip():
        raise HTTPException(status_code=400, detail="Falta el nombre del producto principal")
    if not base.get("imagen"):
        raise HTTPException(status_code=400, detail="Falta la foto del producto principal")
    if not isinstance(config.get("accesorios", []), list) or not isinstance(config.get("combos", []), list) \
            or not isinstance(config.get("colores", []), list):
        raise HTTPException(status_code=400, detail="Formato de equipo inválido")
    if len(json.dumps(config)) > MAX_KIT_VISUAL_JSON:
        raise HTTPException(status_code=400, detail="Las fotos de este equipo pesan demasiado en total — usa menos accesorios o fotos más ligeras.")
    if payload.miniatura and len(payload.miniatura) > MAX_ADJUNTO_BASE64:
        raise HTTPException(status_code=400, detail="La miniatura pesa demasiado")


@app.get("/api/cotizador-visual/kits")
def api_listar_kits_visual(incluir_inactivos: bool = False, usuario: dict = Depends(requiere_ver_checador_precio)):
    return db.listar_kits_visual(usuario["empresa_id"], incluir_inactivos and usuario["rol"] == "admin")


@app.get("/api/cotizador-visual/kits/{kit_id}")
def api_obtener_kit_visual(kit_id: int, usuario: dict = Depends(requiere_ver_checador_precio)):
    kit = db.obtener_kit_visual(usuario["empresa_id"], kit_id)
    if not kit or (not kit["activo"] and usuario["rol"] != "admin"):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return kit


@app.post("/api/cotizador-visual/kits")
def api_crear_kit_visual(payload: KitVisualIn, usuario: dict = Depends(requiere_admin_completo)):
    _validar_kit_visual(payload)
    nuevo_id = db.guardar_kit_visual(usuario["empresa_id"], None, payload.nombre.strip(), payload.activo,
                                     payload.miniatura, payload.config, usuario["id"])
    return {"id": nuevo_id}


@app.put("/api/cotizador-visual/kits/{kit_id}")
def api_actualizar_kit_visual(kit_id: int, payload: KitVisualIn, usuario: dict = Depends(requiere_admin_completo)):
    _validar_kit_visual(payload)
    guardado = db.guardar_kit_visual(usuario["empresa_id"], kit_id, payload.nombre.strip(), payload.activo,
                                     payload.miniatura, payload.config, usuario["id"])
    if not guardado:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return {"id": guardado}


@app.delete("/api/cotizador-visual/kits/{kit_id}")
def api_eliminar_kit_visual(kit_id: int, usuario: dict = Depends(requiere_admin_completo)):
    if not db.eliminar_kit_visual(usuario["empresa_id"], kit_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return {"ok": True}


@app.get("/api/microsip/tablas")
def api_listar_tablas_microsip(usuario: dict = Depends(requiere_admin_completo)):
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    try:
        return {"tablas": microsip.listar_tablas(config)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/microsip/tablas/{tabla}/columnas")
def api_listar_columnas_microsip(tabla: str, usuario: dict = Depends(requiere_admin_completo)):
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    try:
        return {"columnas": microsip.listar_columnas(config, tabla)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/microsip/tablas/{tabla}/muestra")
def api_muestra_tabla_microsip(tabla: str, limite: int = 20, columna: Optional[str] = None, valor: Optional[str] = None,
                                recientes: bool = False, columna_fecha: Optional[str] = None,
                                fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                                usuario: dict = Depends(requiere_admin_completo)):
    _requiere_microsip_disponible()
    config = db.obtener_config_microsip(usuario["empresa_id"])
    try:
        return {"filas": microsip.consultar_muestra(config, tabla, limite, columna, valor, recientes, columna_fecha, fecha_desde, fecha_hasta)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== MARKETING ====================

class NuevaRedSocialMarketing(BaseModel):
    plataforma: str
    nombre_cuenta: str = Field(min_length=1)
    url: Optional[str] = None


class ActualizacionRedSocialMarketing(BaseModel):
    plataforma: Optional[str] = None
    nombre_cuenta: Optional[str] = None
    url: Optional[str] = None
    activa: Optional[bool] = None


class RedCampanaMarketing(BaseModel):
    red_social_id: int
    presupuesto_asignado: Optional[float] = None


class NuevaCampanaMarketing(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    presupuesto_asignado: Optional[float] = None
    responsable_id: Optional[int] = None
    redes: Optional[List[RedCampanaMarketing]] = None


class ActualizacionCampanaMarketing(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    estado: Optional[str] = None
    presupuesto_asignado: Optional[float] = None
    responsable_id: Optional[int] = None


class AsignarRedesCampanaMarketing(BaseModel):
    redes: List[RedCampanaMarketing]


class NuevoGastoMarketing(BaseModel):
    concepto: str = Field(min_length=1)
    monto: float
    fecha: str
    campana_id: Optional[int] = None
    red_social_id: Optional[int] = None
    persona_id: Optional[int] = None


class NuevaMetricaMarketing(BaseModel):
    red_social_id: int
    fecha: str
    nombre_metrica: str = Field(min_length=1)
    valor: float
    campana_id: Optional[int] = None


@app.get("/api/marketing/redes-sociales")
def api_listar_redes_sociales_marketing(usuario: dict = Depends(requiere_ver_marketing)):
    return db.listar_redes_sociales_marketing(usuario["empresa_id"], solo_activas=False)


@app.post("/api/marketing/redes-sociales")
def api_crear_red_social_marketing(payload: NuevaRedSocialMarketing, usuario: dict = Depends(requiere_ver_marketing)):
    red_id = db.crear_red_social_marketing(usuario["empresa_id"], payload.plataforma, payload.nombre_cuenta, payload.url)
    return {"id": red_id}


@app.patch("/api/marketing/redes-sociales/{red_id}")
def api_actualizar_red_social_marketing(red_id: int, payload: ActualizacionRedSocialMarketing,
                                         usuario: dict = Depends(requiere_ver_marketing)):
    db.actualizar_red_social_marketing(usuario["empresa_id"], red_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.get("/api/marketing/campanas")
def api_listar_campanas_marketing(estado: Optional[str] = None, usuario: dict = Depends(requiere_ver_marketing)):
    return db.listar_campanas_marketing(usuario["empresa_id"], estado=estado)


@app.get("/api/marketing/campanas/{campana_id}")
def api_obtener_campana_marketing(campana_id: int, usuario: dict = Depends(requiere_ver_marketing)):
    campana = db.obtener_campana_marketing(usuario["empresa_id"], campana_id)
    if not campana:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return campana


@app.post("/api/marketing/campanas")
def api_crear_campana_marketing(payload: NuevaCampanaMarketing, usuario: dict = Depends(requiere_ver_marketing)):
    campana_id = db.crear_campana_marketing(
        usuario["empresa_id"], payload.nombre, payload.descripcion, payload.fecha_inicio, payload.fecha_fin,
        payload.presupuesto_asignado, payload.responsable_id, usuario["id"],
        redes=[r.dict() for r in payload.redes] if payload.redes else None,
    )
    return {"id": campana_id}


@app.patch("/api/marketing/campanas/{campana_id}")
def api_actualizar_campana_marketing(campana_id: int, payload: ActualizacionCampanaMarketing,
                                      usuario: dict = Depends(requiere_ver_marketing)):
    db.actualizar_campana_marketing(usuario["empresa_id"], campana_id, **payload.dict(exclude_unset=True))
    return {"ok": True}


@app.patch("/api/marketing/campanas/{campana_id}/redes")
def api_asignar_redes_campana_marketing(campana_id: int, payload: AsignarRedesCampanaMarketing,
                                         usuario: dict = Depends(requiere_ver_marketing)):
    db.asignar_redes_campana_marketing(campana_id, [r.dict() for r in payload.redes])
    return {"ok": True}


@app.delete("/api/marketing/campanas/{campana_id}")
def api_eliminar_campana_marketing(campana_id: int, usuario: dict = Depends(requiere_ver_marketing)):
    if not db.eliminar_campana_marketing(usuario["empresa_id"], campana_id):
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return {"ok": True}


@app.get("/api/marketing/gastos")
def api_listar_gastos_marketing(campana_id: Optional[int] = None, red_social_id: Optional[int] = None,
                                 persona_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_marketing)):
    return db.listar_gastos_marketing(usuario["empresa_id"], campana_id=campana_id, red_social_id=red_social_id,
                                       persona_id=persona_id)


@app.post("/api/marketing/gastos")
def api_crear_gasto_marketing(payload: NuevoGastoMarketing, usuario: dict = Depends(requiere_ver_marketing)):
    gasto_id = db.crear_gasto_marketing(
        usuario["empresa_id"], payload.concepto, payload.monto, payload.fecha,
        campana_id=payload.campana_id, red_social_id=payload.red_social_id, persona_id=payload.persona_id,
        creado_por_id=usuario["id"],
    )
    return {"id": gasto_id}


@app.delete("/api/marketing/gastos/{gasto_id}")
def api_eliminar_gasto_marketing(gasto_id: int, usuario: dict = Depends(requiere_ver_marketing)):
    if not db.eliminar_gasto_marketing(usuario["empresa_id"], gasto_id):
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return {"ok": True}


@app.get("/api/marketing/presupuesto-resumen")
def api_resumen_presupuesto_marketing(usuario: dict = Depends(requiere_ver_marketing)):
    return db.resumen_presupuesto_marketing(usuario["empresa_id"])


@app.get("/api/marketing/metricas")
def api_listar_metricas_marketing(red_social_id: Optional[int] = None, campana_id: Optional[int] = None,
                                   usuario: dict = Depends(requiere_ver_marketing)):
    return db.listar_metricas_marketing(usuario["empresa_id"], red_social_id=red_social_id, campana_id=campana_id)


@app.post("/api/marketing/metricas")
def api_crear_metrica_marketing(payload: NuevaMetricaMarketing, usuario: dict = Depends(requiere_ver_marketing)):
    metrica_id = db.crear_metrica_marketing(
        usuario["empresa_id"], payload.red_social_id, payload.fecha, payload.nombre_metrica, payload.valor,
        campana_id=payload.campana_id, registrado_por_id=usuario["id"],
    )
    return {"id": metrica_id}


@app.delete("/api/marketing/metricas/{metrica_id}")
def api_eliminar_metrica_marketing(metrica_id: int, usuario: dict = Depends(requiere_ver_marketing)):
    if not db.eliminar_metrica_marketing(usuario["empresa_id"], metrica_id):
        raise HTTPException(status_code=404, detail="Métrica no encontrada")
    return {"ok": True}


@app.get("/api/marketing/turnos/reporte")
def api_reporte_turnos_marketing(desde: str, hasta: str, sucursal_id: Optional[int] = None,
                                  usuario: dict = Depends(requiere_ver_marketing)):
    return db.reporte_turnos_marketing(usuario["empresa_id"], desde, hasta, sucursal_id=sucursal_id)


# ==================== FRONTEND ESTÁTICO ====================

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    # Sin esto, algún proxy intermedio (Render/Cloudflare) puede quedarse
    # sirviendo una versión vieja de la página por horas después de cada
    # despliegue nuevo, aunque el código ya esté actualizado en el servidor.
    return FileResponse(
        os.path.join(FRONTEND_DIR, "index.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/api/health")
def health():
    """Endpoint liviano sin login, pensado para que un servicio externo de
    'ping' (cron-job.org, UptimeRobot, etc.) lo visite cada pocos minutos.
    Al tocar la base de datos con un SELECT 1 evita que Neon (plan gratis)
    suspenda el cómputo por inactividad, y al recibir tráfico evita que
    Render (plan gratis) duerma la app — así se evitan los 10-30s de
    demora que se sienten cuando la base/la app tienen que 'despertar'."""
    con = db.get_connection()
    try:
        cur = con.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        con.close()
    return {"ok": True}


def _ejecutar_sync_inventario_empresa(empresa_id: int, actualizado_por: str) -> int:
    """Corre la sincronización completa del respaldo de inventario para
    una empresa — compartido entre el botón manual, el cron externo (de
    respaldo, por si alguien lo sigue usando) y el scheduler automático
    interno de la app. Regresa el total de filas guardadas; deja que
    cualquier excepción se propague (cada quien decide cómo reportarla)."""
    config = db.obtener_config_microsip(empresa_id)
    if not config or not config.get("microsip_host"):
        raise RuntimeError("Microsip no está configurado para esa empresa")
    filas = microsip.obtener_inventario_completo_todos_almacenes(config)
    db.guardar_inventario_cache(empresa_id, filas, actualizado_por)
    return len(filas)


@app.post("/api/admin/microsip/sincronizar-inventario")
def api_sincronizar_inventario_manual(usuario: dict = Depends(requiere_admin_completo)):
    """Sincronización del respaldo local, disparada a mano por un
    administrador desde la app (botón 'Sincronizar ahora')."""
    try:
        total_filas = _ejecutar_sync_inventario_empresa(usuario["empresa_id"], usuario["nombre"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error sincronizando el inventario: {e}")
    return {"ok": True, "total_filas": total_filas}


@app.get("/api/admin/microsip/inventario-cache-meta")
def api_meta_inventario_cache(usuario: dict = Depends(requiere_admin_completo)):
    """Cuándo fue la última sincronización del respaldo local, y cuántas
    filas trae — para mostrarlo en la pantalla de administración."""
    meta = db.obtener_meta_inventario_cache(usuario["empresa_id"])
    return meta or {"actualizado_en": None, "total_filas": 0, "actualizado_por": None}


class ConfigSyncInventarioPayload(BaseModel):
    activo: bool
    hora: int = Field(ge=0, le=23)


@app.get("/api/admin/microsip/sync-inventario-config")
def api_obtener_config_sync_inventario(usuario: dict = Depends(requiere_admin_completo)):
    """Configuración de la sincronización automática diaria del respaldo
    de inventario — editable desde la propia app, sin tocar Render ni
    un cron externo (ver POST de esta misma ruta)."""
    return db.obtener_config_sync_inventario(usuario["empresa_id"])


@app.post("/api/admin/microsip/sync-inventario-config")
def api_guardar_config_sync_inventario(payload: ConfigSyncInventarioPayload, usuario: dict = Depends(requiere_admin_completo)):
    """Activa/desactiva la sincronización automática y elige a qué hora
    del día corre (hora local de Puebla/CDMX). La corre un scheduler que
    vive DENTRO del proceso de la app (ver iniciar_scheduler_inventario),
    revisando cada 10 minutos si ya es la hora configurada — por eso
    sigue dependiendo de que la app esté despierta (el ping de
    /api/health cada 5 min ya se encarga de eso)."""
    db.guardar_config_sync_inventario(usuario["empresa_id"], payload.activo, payload.hora)
    return db.obtener_config_sync_inventario(usuario["empresa_id"])


SYNC_SECRET_KEY = os.getenv("SYNC_SECRET_KEY", "").strip()


@app.get("/api/cron/sincronizar-inventario")
def api_cron_sincronizar_inventario(empresa_id: int, clave: str):
    """Sin login — ruta de RESPALDO para quien prefiera disparar la
    sincronización desde un cron externo (cron-job.org) en vez de la
    automática interna de arriba. Requiere que SYNC_SECRET_KEY esté
    configurada en Render (Environment) y que la URL se llame con
    ?clave=esa_misma_clave — si no coincide, o si la variable ni
    siquiera está puesta, este endpoint no hace nada (por seguridad)."""
    if not SYNC_SECRET_KEY or clave != SYNC_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Clave inválida o SYNC_SECRET_KEY no configurada en Render")
    empresa = db.obtener_empresa(empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    try:
        total_filas = _ejecutar_sync_inventario_empresa(empresa_id, "automático (cron externo)")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error sincronizando el inventario: {e}")
    return {"ok": True, "total_filas": total_filas}


def _revisar_sync_automatico_inventario():
    """Llamada cada 10 min por el scheduler interno (ver
    iniciar_scheduler_inventario) — para cada empresa con la
    sincronización automática activada (Administrar → Inventario
    completo), si YA es la hora configurada y todavía no ha corrido HOY,
    la ejecuta. No requiere variables de entorno ni cron externo — vive
    dentro del propio proceso de la app."""
    hoy = db.ahora().strftime("%Y-%m-%d")
    hora_actual = db.ahora().hour
    for empresa in db.listar_empresas_con_sync_inventario_activo():
        if empresa["sync_inventario_hora"] != hora_actual:
            continue
        if empresa["sync_inventario_ultima_fecha"] == hoy:
            continue  # ya corrió hoy, no repetir hasta mañana
        try:
            _ejecutar_sync_inventario_empresa(empresa["id"], "automático (programado)")
        except Exception as e:
            print(f"[sync-inventario] Error sincronizando empresa {empresa['id']}: {e}")
        finally:
            # se marca como "ya corrida hoy" incluso si falló, para no
            # reintentar cada 10 min todo el resto del día si Microsip
            # está caído — volverá a intentar mañana a la misma hora.
            db.marcar_sync_inventario_ejecutado(empresa["id"], hoy)


@app.on_event("startup")
def iniciar_scheduler_inventario():
    if not APSCHEDULER_DISPONIBLE or not MICROSIP_DISPONIBLE:
        return
    scheduler = BackgroundScheduler(timezone=str(db.ZONA_MX))
    scheduler.add_job(_revisar_sync_automatico_inventario, "interval", minutes=10, id="sync_inventario_automatico")
    scheduler.start()


@app.get("/api/dashboard/inventario-respaldo")
def api_inventario_respaldo(almacen_id: Optional[int] = None, busqueda: Optional[str] = None,
                             usuario: dict = Depends(requiere_dashboard)):
    """Artículos + existencias: intenta Microsip EN VIVO primero (igual
    que las demás tarjetas); si Microsip no responde (túnel caído, etc.),
    cae automáticamente al respaldo local guardado en la última
    sincronización — el frontend distingue cuál de los dos le llegó
    con el campo 'fuente'."""
    almacenes_cache = db.listar_almacenes_inventario_cache(usuario["empresa_id"])
    meta = db.obtener_meta_inventario_cache(usuario["empresa_id"])
    try:
        config = _config_microsip_o_error(usuario)
        filas_vivo = microsip.obtener_inventario_completo_todos_almacenes(config)
        if almacen_id:
            filas_vivo = [f for f in filas_vivo if f["almacen_id"] == almacen_id]
        if busqueda:
            b = busqueda.strip().lower()
            filas_vivo = [f for f in filas_vivo if b in (f["nombre"] or "").lower() or b in (f.get("clave") or "").lower()]
        filas_vivo.sort(key=lambda f: f["nombre"] or "")
        almacenes_vivo = sorted({(f["almacen_id"], f["almacen_nombre"]) for f in filas_vivo}, key=lambda t: t[1] or "")
        return {
            "fuente": "microsip_vivo",
            "articulos": filas_vivo,
            "total": len(filas_vivo),
            "almacenes": [{"almacen_id": aid, "nombre": nombre} for aid, nombre in almacenes_vivo] or almacenes_cache,
            "ultima_sincronizacion": meta["actualizado_en"] if meta else None,
        }
    except Exception:
        # Microsip no respondió (túnel/ngrok caído, computadora apagada,
        # etc.) — se usa el respaldo local guardado en la última
        # sincronización, en vez de dejar la pantalla sin nada.
        filas_cache = db.listar_inventario_cache(usuario["empresa_id"], almacen_id, busqueda, limite=None)
        return {
            "fuente": "respaldo_local",
            "articulos": filas_cache,
            "total": len(filas_cache),
            "almacenes": almacenes_cache,
            "ultima_sincronizacion": meta["actualizado_en"] if meta else None,
        }



# ==================== Soporte técnico (Peymar) ====================
# Solo el área de soporte crea reportes. Flujo: reporte (mantenimiento o
# garantía, cliente, unidad dental, serie, problema, evidencia de WhatsApp) →
# orden de servicio en PDF que el cliente firma desde un link → diagnóstico
# (sin costos: refacciones y evidencia) + apartado interno de la empresa →
# documento de resolución (con encuesta de satisfacción) → enviado → cerrado.

import soporte_pdf

MAX_EVIDENCIA_SOPORTE = 20 * 1024 * 1024
CAUSAS_SOPORTE = ["Mala calidad del material", "Baja calidad", "Equipo o piezas defectuosas", "Métodos de envío", "Otro"]
TIPOS_PAQUETERIA_SOPORTE = ["Terrestre", "Express / día siguiente", "Aérea", "Flete / carga", "Entrega directa"]
PAQUETERIAS_SOPORTE = ["Estafeta", "DHL", "FedEx", "Paquetexpress", "Tres Guerras", "Castores", "99 Minutos", "Redpack"]


def _soporte_o_404(usuario, reporte_id):
    r = db.obtener_soporte(usuario["empresa_id"], reporte_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return r


def _soporte_detalle(usuario, r):
    r = dict(r)
    r["folio_txt"] = soporte_pdf.folio_txt(r)
    r["estado_nombre"] = db.ESTADOS_SOPORTE.get(r["estado"], r["estado"])
    r["evidencias"] = db.listar_evidencias_soporte(r["id"])
    r["historial"] = db.historial_soporte(r["id"])
    return r


class SoporteIn(BaseModel):
    tipo_servicio: Optional[str] = None
    cliente_nombre: Optional[str] = Field(default=None, max_length=200)
    cliente_telefono: Optional[str] = Field(default=None, max_length=40)
    cliente_email: Optional[str] = Field(default=None, max_length=150)
    cliente_direccion: Optional[str] = Field(default=None, max_length=400)
    cliente_ciudad: Optional[str] = Field(default=None, max_length=150)
    tipo_unidad: Optional[str] = Field(default=None, max_length=150)
    modelo: Optional[str] = Field(default=None, max_length=150)
    numero_serie: Optional[str] = Field(default=None, max_length=120)
    problema: Optional[str] = Field(default=None, max_length=5000)
    diagnostico: Optional[str] = Field(default=None, max_length=8000)
    refacciones: Optional[List[dict]] = None
    resolucion: Optional[str] = Field(default=None, max_length=8000)
    paqueteria: Optional[str] = Field(default=None, max_length=150)
    ocurre: Optional[bool] = None
    interno: Optional[dict] = None


def _limpiar_soporte(datos: dict):
    for k, v in list(datos.items()):
        if isinstance(v, str):
            datos[k] = v.strip() or None
    if "tipo_servicio" in datos and datos["tipo_servicio"] not in db.TIPOS_SERVICIO_SOPORTE:
        raise HTTPException(status_code=400, detail="Elige el tipo de servicio: mantenimiento o garantía.")
    if "refacciones" in datos and datos["refacciones"] is not None:
        limpias = []
        for x in datos["refacciones"][:100]:
            desc = str(x.get("descripcion") or "").strip()
            if desc:
                try:
                    cant = float(x.get("cantidad") or 1)
                except Exception:
                    cant = 1
                limpias.append({"cantidad": int(cant) if cant == int(cant) else cant, "descripcion": desc[:300],
                                "numero_parte": str(x.get("numero_parte") or "").strip()[:80] or None})
        datos["refacciones"] = limpias
    if "interno" in datos and datos["interno"] is not None:
        i = datos["interno"]
        costos = []
        for c in (i.get("costos") or [])[:100]:
            concepto = str(c.get("concepto") or "").strip()
            try:
                monto = round(float(c.get("monto") or 0), 2)
            except Exception:
                monto = 0
            if concepto or monto:
                costos.append({"concepto": concepto[:200], "monto": monto})
        causas = [c for c in (i.get("causas") or []) if c in CAUSAS_SOPORTE]
        datos["interno"] = {
            "causas": causas, "causa_otro": str(i.get("causa_otro") or "").strip()[:300] or None,
            "causa_falla": str(i.get("causa_falla") or "").strip()[:3000] or None,
            "metodo_envio": str(i.get("metodo_envio") or "").strip()[:150] or None,
            "guia": str(i.get("guia") or "").strip()[:120] or None,
            "paqueteria_tipo": str(i.get("paqueteria_tipo") or "").strip()[:100] or None,
            "paqueteria_nombre": str(i.get("paqueteria_nombre") or "").strip()[:120] or None,
            "distribuidor": str(i.get("distribuidor") or "").strip()[:200] or None,
            "costos": costos, "costo_total": round(sum(c["monto"] for c in costos), 2),
            "notas": str(i.get("notas") or "").strip()[:3000] or None,
        }
    return datos


@app.get("/api/soporte")
def api_soporte_lista(estado: Optional[str] = None, q: Optional[str] = None, usuario: dict = Depends(requiere_acceso_soporte)):
    reportes = db.listar_soporte(usuario["empresa_id"], estado or None, (q or "").strip() or None)
    for r in reportes:
        r["folio_txt"] = soporte_pdf.folio_txt(r)
        r["estado_nombre"] = db.ESTADOS_SOPORTE.get(r["estado"], r["estado"])
        r["costo_total"] = (r.pop("interno", None) or {}).get("costo_total")
    return {"reportes": reportes, "estados": db.ESTADOS_SOPORTE, "tipos": db.TIPOS_SERVICIO_SOPORTE,
            "causas": CAUSAS_SOPORTE, "tipos_paqueteria": TIPOS_PAQUETERIA_SOPORTE,
            "paqueterias": PAQUETERIAS_SOPORTE, "sugerencias": db.sugerencias_soporte(usuario["empresa_id"])}


@app.get("/api/soporte/analisis")
def api_soporte_analisis(desde: Optional[str] = None, hasta: Optional[str] = None, usuario: dict = Depends(requiere_acceso_soporte)):
    """Para la empresa: causas, distribuidores, unidades, costos y encuestas."""
    filas = db.listar_soporte(usuario["empresa_id"])
    d, h = (desde or "0000")[:10], (hasta or "9999")[:10]
    filas = [r for r in filas if d <= (r["creado_en"] or "")[:10] <= h]
    def contar(clave_fn):
        # Agrupa sin importar mayúsculas/espacios ("Dental Center" = "DENTAL CENTER").
        out, etiqueta = {}, {}
        for r in filas:
            for k in clave_fn(r):
                if k:
                    llave = " ".join(str(k).split()).casefold()
                    etiqueta.setdefault(llave, " ".join(str(k).split()))
                    out[llave] = out.get(llave, 0) + 1
        return sorted(((etiqueta[k], n) for k, n in out.items()), key=lambda x: -x[1])
    costos = {}
    for r in filas:
        i = r.get("interno") or {}
        for c in i.get("causas") or ["Sin clasificar"]:
            costos[c] = round(costos.get(c, 0) + float(i.get("costo_total") or 0), 2)
    encuestas = []
    for r in filas:
        if r.get("encuesta_en"):
            enc = db.obtener_soporte(usuario["empresa_id"], r["id"]).get("encuesta") or {}
            encuestas.append(enc)
    def prom(k):
        v = [float(e[k]) for e in encuestas if isinstance(e.get(k), (int, float))]
        return round(sum(v) / len(v), 2) if v else None
    return {
        "total": len(filas),
        "por_estado": contar(lambda r: [db.ESTADOS_SOPORTE.get(r["estado"], r["estado"])]),
        "por_tipo": contar(lambda r: [db.TIPOS_SERVICIO_SOPORTE.get(r["tipo_servicio"], r["tipo_servicio"])]),
        "por_causa": contar(lambda r: (r.get("interno") or {}).get("causas") or ["Sin clasificar"]),
        "por_distribuidor": contar(lambda r: [(r.get("interno") or {}).get("distribuidor") or "Sin dato"]),
        "por_unidad": contar(lambda r: [r.get("tipo_unidad") or "Sin dato"]),
        "por_paqueteria": contar(lambda r: [(r.get("interno") or {}).get("paqueteria_nombre")] if (r.get("interno") or {}).get("paqueteria_nombre") else []),
        "costo_total": round(sum(float((r.get("interno") or {}).get("costo_total") or 0) for r in filas), 2),
        "costo_por_causa": sorted(costos.items(), key=lambda x: -x[1]),
        "encuestas": len(encuestas),
        "encuesta_promedios": {k: prom(k) for k in ("satisfaccion_producto", "atencion", "rapidez", "recomendaria")},
    }


@app.post("/api/soporte")
def api_soporte_crear(payload: SoporteIn, usuario: dict = Depends(requiere_acceso_soporte)):
    datos = _limpiar_soporte(payload.model_dump(exclude_unset=True))
    if not datos.get("tipo_servicio"):
        raise HTTPException(status_code=400, detail="Elige el tipo de servicio: mantenimiento o garantía.")
    if not datos.get("cliente_nombre"):
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente.")
    if not datos.get("problema"):
        raise HTTPException(status_code=400, detail="Describe cuál es el problema.")
    rid = db.crear_soporte(usuario["empresa_id"], datos, usuario["id"])
    return _soporte_detalle(usuario, db.obtener_soporte(usuario["empresa_id"], rid))


@app.get("/api/soporte/{reporte_id}")
def api_soporte_detalle(reporte_id: int, usuario: dict = Depends(requiere_acceso_soporte)):
    return _soporte_detalle(usuario, _soporte_o_404(usuario, reporte_id))


@app.put("/api/soporte/{reporte_id}")
def api_soporte_editar(reporte_id: int, payload: SoporteIn, usuario: dict = Depends(requiere_acceso_soporte)):
    r = _soporte_o_404(usuario, reporte_id)
    if r["estado"] in ("cerrado", "cancelado"):
        raise HTTPException(status_code=400, detail="El reporte está cerrado. Reábrelo para cambiarlo.")
    datos = _limpiar_soporte(payload.model_dump(exclude_unset=True))
    for k in ("cliente_nombre", "problema"):
        if k in datos and not datos[k]:
            raise HTTPException(status_code=400, detail="El nombre del cliente y el problema no pueden quedar vacíos.")
    db.actualizar_soporte(usuario["empresa_id"], reporte_id, datos)
    return _soporte_detalle(usuario, db.obtener_soporte(usuario["empresa_id"], reporte_id))


@app.post("/api/soporte/{reporte_id}/evidencias")
async def api_soporte_evidencia(reporte_id: int, archivo: UploadFile = File(...), etapa: str = Form("reporte"),
                                descripcion: str = Form(""), usuario: dict = Depends(requiere_acceso_soporte)):
    """Fotos, videos, audios o PDFs (ej. lo que mandó el cliente por WhatsApp)."""
    _soporte_o_404(usuario, reporte_id)
    if etapa not in ("reporte", "diagnostico"):
        raise HTTPException(status_code=400, detail="Etapa inválida")
    datos = await archivo.read()
    if not datos:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(datos) > MAX_EVIDENCIA_SOPORTE:
        raise HTTPException(status_code=400, detail="El archivo pesa más de 20 MB. Mándalo más corto o comprimido.")
    tipo = archivo.content_type or "application/octet-stream"
    if tipo == "application/octet-stream":
        # Las apps suben sin tipo: se deduce del nombre (foto.jpg → image/jpeg).
        import mimetypes
        tipo = mimetypes.guess_type(archivo.filename or "")[0] or tipo
    url, b64 = None, None
    import r2
    if not tipo.startswith("image") and len(datos) > 3 * 1024 * 1024 and r2.configurado():
        from io import BytesIO as _B
        _, url = r2.subir_video(usuario["empresa_id"], f"soporte_{reporte_id}_{archivo.filename or 'archivo'}", _B(datos), tipo)
    else:
        b64 = f"data:{tipo};base64," + base64.b64encode(datos).decode()
    eid = db.agregar_evidencia_soporte(reporte_id, etapa, (archivo.filename or "archivo")[:200], tipo,
                                       (descripcion or "").strip()[:300] or None, b64, url, len(datos), usuario["id"])
    return {"id": eid, "evidencias": db.listar_evidencias_soporte(reporte_id)}


@app.get("/api/soporte/{reporte_id}/evidencias/{evidencia_id}")
def api_soporte_ver_evidencia(reporte_id: int, evidencia_id: int, usuario: dict = Depends(requiere_acceso_soporte)):
    _soporte_o_404(usuario, reporte_id)
    e = db.obtener_evidencia_soporte(reporte_id, evidencia_id)
    if not e:
        raise HTTPException(status_code=404, detail="No existe")
    if e.get("url"):
        return {"url": e["url"], "tipo": e["tipo"], "nombre": e["nombre"]}
    return {"data": e["archivo_base64"], "tipo": e["tipo"], "nombre": e["nombre"]}


@app.delete("/api/soporte/{reporte_id}/evidencias/{evidencia_id}")
def api_soporte_borrar_evidencia(reporte_id: int, evidencia_id: int, usuario: dict = Depends(requiere_acceso_soporte)):
    _soporte_o_404(usuario, reporte_id)
    if not db.borrar_evidencia_soporte(reporte_id, evidencia_id):
        raise HTTPException(status_code=404, detail="No existe")
    return {"evidencias": db.listar_evidencias_soporte(reporte_id)}


def _pdf_orden_soporte(r, empresa_id, liga=None):
    return soporte_pdf.orden_servicio_pdf(r, db.obtener_empresa(empresa_id) or {},
                                          db.listar_evidencias_soporte(r["id"], con_archivo=True, etapa="reporte"), liga)


def _pdf_resolucion_soporte(r, empresa_id, liga=None):
    return soporte_pdf.resolucion_pdf(r, db.obtener_empresa(empresa_id) or {},
                                      db.listar_evidencias_soporte(r["id"], con_archivo=True, etapa="diagnostico"), liga)


def _respuesta_pdf(contenido, nombre):
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nombre}"'})


@app.get("/api/soporte/{reporte_id}/orden.pdf")
def api_soporte_orden_pdf(reporte_id: int, liga: Optional[str] = None, usuario: dict = Depends(requiere_acceso_soporte)):
    r = _soporte_o_404(usuario, reporte_id)
    return _respuesta_pdf(_pdf_orden_soporte(r, usuario["empresa_id"], liga), f"Orden_servicio_{soporte_pdf.folio_txt(r)}.pdf")


@app.get("/api/soporte/{reporte_id}/resolucion.pdf")
def api_soporte_resolucion_pdf(reporte_id: int, liga: Optional[str] = None, usuario: dict = Depends(requiere_acceso_soporte)):
    r = _soporte_o_404(usuario, reporte_id)
    return _respuesta_pdf(_pdf_resolucion_soporte(r, usuario["empresa_id"], liga), f"Diagnostico_{soporte_pdf.folio_txt(r)}.pdf")


@app.post("/api/soporte/{reporte_id}/orden-enviada")
def api_soporte_orden_enviada(reporte_id: int, usuario: dict = Depends(requiere_acceso_soporte)):
    r = _soporte_o_404(usuario, reporte_id)
    db.actualizar_soporte(usuario["empresa_id"], reporte_id, {"orden_enviada_en": db.ahora().isoformat(timespec="seconds")},
                          usuario["id"], f"Se le mandó al cliente la orden para firmar{' (reenvío)' if r.get('orden_enviada_en') else ''}.")
    return {"ok": True}


class FirmaSoporteIn(BaseModel):
    firma_base64: str = Field(min_length=50, max_length=800_000)
    nombre: str = Field(min_length=3, max_length=150)


@app.post("/api/soporte/{reporte_id}/firmar")
def api_soporte_firmar_presencial(reporte_id: int, payload: FirmaSoporteIn, usuario: dict = Depends(requiere_acceso_soporte)):
    """El cliente firma en persona, en la pantalla de soporte."""
    r = _soporte_o_404(usuario, reporte_id)
    if r.get("firma_en"):
        raise HTTPException(status_code=400, detail="La orden ya está firmada.")
    db.firmar_soporte(reporte_id, payload.firma_base64, payload.nombre.strip(), "presencial", None, usuario["id"])
    return _soporte_detalle(usuario, db.obtener_soporte(usuario["empresa_id"], reporte_id))


@app.post("/api/soporte/{reporte_id}/enviar-resolucion")
def api_soporte_enviar_resolucion(reporte_id: int, usuario: dict = Depends(requiere_acceso_soporte)):
    """Deja lista la resolución para el cliente (el link ya le muestra diagnóstico y encuesta)."""
    r = _soporte_o_404(usuario, reporte_id)
    if not r.get("firma_en"):
        raise HTTPException(status_code=400, detail="Primero el cliente debe firmar la orden de servicio.")
    if not (r.get("diagnostico") or "").strip() or not (r.get("resolucion") or "").strip():
        raise HTTPException(status_code=400, detail="Falta capturar el diagnóstico y qué se le va a hacer.")
    if r["estado"] in ("cerrado", "cancelado"):
        raise HTTPException(status_code=400, detail="El reporte está cerrado.")
    cambios = {"resolucion_enviada_en": db.ahora().isoformat(timespec="seconds")}
    if r["estado"] in ("diagnostico", "orden_pendiente_firma"):
        cambios["estado"] = "resolucion_enviada"
    db.actualizar_soporte(usuario["empresa_id"], reporte_id, cambios, usuario["id"],
                          "Se le mandó al cliente el diagnóstico y la resolución, con la encuesta de satisfacción."
                          if not r.get("resolucion_enviada_en") else "Se reenvió la resolución al cliente.")
    return _soporte_detalle(usuario, db.obtener_soporte(usuario["empresa_id"], reporte_id))


class EstadoSoporteIn(BaseModel):
    estado: str
    texto: Optional[str] = Field(default=None, max_length=1000)


@app.post("/api/soporte/{reporte_id}/estado")
def api_soporte_estado(reporte_id: int, payload: EstadoSoporteIn, usuario: dict = Depends(requiere_acceso_soporte)):
    r = _soporte_o_404(usuario, reporte_id)
    nuevo = payload.estado
    texto = (payload.texto or "").strip()
    if nuevo not in db.ESTADOS_SOPORTE:
        raise HTTPException(status_code=400, detail="Estatus inválido")
    if nuevo == "cancelado" and len(texto) < 3:
        raise HTTPException(status_code=400, detail="Escribe el motivo de la cancelación.")
    if nuevo == "enviado" and not r.get("resolucion_enviada_en"):
        raise HTTPException(status_code=400, detail="Primero manda la resolución al cliente.")
    if nuevo == "diagnostico" and not r.get("firma_en"):
        raise HTTPException(status_code=400, detail="Pasa a diagnóstico solo cuando el cliente firme la orden.")
    cambios = {"estado": nuevo}
    if nuevo == "cancelado":
        cambios["motivo_cancelacion"] = texto
    nombre = db.ESTADOS_SOPORTE[nuevo]
    db.actualizar_soporte(usuario["empresa_id"], reporte_id, cambios, usuario["id"], f"Estatus: {nombre}" + (f" — {texto}" if texto else ""))
    return _soporte_detalle(usuario, db.obtener_soporte(usuario["empresa_id"], reporte_id))


# ---- Página pública del cliente (sin login): firmar la orden y contestar la encuesta ----

@app.get("/soporte/{token}")
def pagina_soporte_cliente(token: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "soporte_cliente.html"))


def _soporte_publico_o_404(token):
    r = db.obtener_soporte_por_token((token or "").strip())
    if not r or r["estado"] == "cancelado":
        raise HTTPException(status_code=404, detail="Este link ya no es válido.")
    return r


@app.get("/api/publico/soporte/{token}")
def api_soporte_publico(token: str):
    r = _soporte_publico_o_404(token)
    empresa = db.obtener_empresa(r["empresa_id"]) or {}
    resolucion = bool(r.get("resolucion_enviada_en"))
    return {
        "empresa": empresa.get("nombre"), "logo": empresa.get("logo_base64"), "color": empresa.get("color_acento"),
        "folio": soporte_pdf.folio_txt(r), "tipo_servicio": db.TIPOS_SERVICIO_SOPORTE.get(r["tipo_servicio"]),
        "estado": db.ESTADOS_SOPORTE.get(r["estado"]), "fecha": r["creado_en"],
        "cliente_nombre": r["cliente_nombre"], "tipo_unidad": r.get("tipo_unidad"), "modelo": r.get("modelo"),
        "numero_serie": r.get("numero_serie"), "problema": r["problema"],
        "firmada": bool(r.get("firma_en")), "firma_nombre": r.get("firma_nombre"), "firma_en": r.get("firma_en"),
        "resolucion": {
            "diagnostico": r.get("diagnostico"), "refacciones": r.get("refacciones") or [], "resolucion": r.get("resolucion"),
            "paqueteria": r.get("paqueteria"), "ocurre": r.get("ocurre"), "fecha": r.get("resolucion_enviada_en"),
        } if resolucion else None,
        "encuesta_pendiente": resolucion and not r.get("encuesta_en"),
        "encuesta_contestada": bool(r.get("encuesta_en")),
    }


@app.get("/api/publico/soporte/{token}/orden.pdf")
def api_soporte_publico_orden(token: str):
    r = _soporte_publico_o_404(token)
    return _respuesta_pdf(_pdf_orden_soporte(r, r["empresa_id"]), f"Orden_servicio_{soporte_pdf.folio_txt(r)}.pdf")


@app.get("/api/publico/soporte/{token}/resolucion.pdf")
def api_soporte_publico_resolucion(token: str, request: Request):
    r = _soporte_publico_o_404(token)
    if not r.get("resolucion_enviada_en"):
        raise HTTPException(status_code=404, detail="Todavía no hay diagnóstico.")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    liga = f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}/soporte/{r['token']}"
    return _respuesta_pdf(_pdf_resolucion_soporte(r, r["empresa_id"], liga), f"Diagnostico_{soporte_pdf.folio_txt(r)}.pdf")


@app.post("/api/publico/soporte/{token}/firmar")
def api_soporte_publico_firmar(token: str, payload: FirmaSoporteIn, request: Request):
    r = _soporte_publico_o_404(token)
    if r.get("firma_en"):
        raise HTTPException(status_code=400, detail="Esta orden ya está firmada. ¡Gracias!")
    db.firmar_soporte(r["id"], payload.firma_base64, payload.nombre.strip(), "link", _ip_cliente(request))
    return {"ok": True}


class EncuestaSoporteIn(BaseModel):
    satisfaccion_producto: int = Field(ge=1, le=5)
    atencion: int = Field(ge=1, le=5)
    rapidez: int = Field(ge=1, le=5)
    recomendaria: int = Field(ge=0, le=10)
    comentarios: Optional[str] = Field(default=None, max_length=2000)


@app.post("/api/publico/soporte/{token}/encuesta")
def api_soporte_publico_encuesta(token: str, payload: EncuestaSoporteIn):
    r = _soporte_publico_o_404(token)
    if not r.get("resolucion_enviada_en"):
        raise HTTPException(status_code=400, detail="La encuesta se contesta cuando te enviemos el diagnóstico.")
    if r.get("encuesta_en"):
        raise HTTPException(status_code=400, detail="Ya contestaste la encuesta. ¡Gracias!")
    db.actualizar_soporte(r["empresa_id"], r["id"], {"encuesta": payload.model_dump()}, None,
                          f"El cliente contestó la encuesta (producto {payload.satisfaccion_producto}/5, atención {payload.atencion}/5).")
    return {"ok": True}


@app.get("/seguimiento/{token}")
def pagina_seguimiento(token: str):
    """Página pública (sin login) que abre el cliente desde la liga que se
    le manda por WhatsApp — el HTML en sí no necesita el token para nada,
    solo lo lee de la URL con JavaScript y llama a /api/seguimiento/{token}."""
    return FileResponse(os.path.join(FRONTEND_DIR, "seguimiento.html"))


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")



# ==================== INVENTARIOS A PUERTA ABIERTA (app) ====================
# Contar sin cerrar la sucursal: cada conteo (producto + lote) guarda la "foto"
# de lo que Microsip decía que había de ese lote EN ESE MOMENTO; la diferencia
# se calcula contra esa foto, así lo que se venda después no la altera. Si el
# producto se vendió hace poco se avisa al contar, y al revisar se marcan los
# que se movieron después de contarlos. El ajuste se aplica a mano en Microsip
# (Inventario físico) con el Excel; la ubicación / máximo / mínimo / reorden sí
# se guardan directo en Microsip. Ver backend/microsip_inventario.py.

MINUTOS_VENTA_RECIENTE = 30


def _config_inventarios(usuario):
    if not MICROSIP_DISPONIBLE:
        raise HTTPException(status_code=503, detail="El servidor no tiene el driver de Microsip.")
    cfg = db.obtener_config_microsip(usuario["empresa_id"])
    if not cfg or not cfg.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Esta empresa no tiene Microsip conectado (Administrar → Microsip).")
    return cfg


def _inventario_de(usuario, inventario_id, abierto=False):
    inv = db.obtener_inventario_fisico(usuario["empresa_id"], inventario_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    if abierto and inv["estado"] != "abierto":
        raise HTTPException(status_code=400, detail="Este inventario ya está cerrado.")
    return inv


def _es_jefe_inventario(usuario, inv):
    return usuario["rol"] in ("admin", "encargado_sucursal") or inv.get("creado_por_id") == usuario["id"]


def _error_microsip(e):
    if isinstance(e, HTTPException):
        raise e
    raise HTTPException(status_code=502, detail=f"Microsip no respondió: {e}")


def _minutos_desde_venta(uv):
    """Minutos desde la última venta (solo si fue hoy), para el aviso."""
    from datetime import datetime as _dt
    if not uv or not uv.get("fecha") or not uv.get("hora"):
        return None
    try:
        t = _dt.fromisoformat(f"{uv['fecha']}T{uv['hora']}")
    except ValueError:
        return None
    m = int((db.ahora() - t).total_seconds() // 60)
    return m if 0 <= m <= 24 * 60 else None


@app.get("/api/inventarios/almacenes")
def api_inventarios_almacenes(usuario: dict = Depends(requiere_inventarios)):
    cfg = _config_inventarios(usuario)
    try:
        return microsip_inventario.almacenes(cfg)
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)


@app.get("/api/inventarios")
def api_listar_inventarios(usuario: dict = Depends(requiere_inventarios)):
    return db.listar_inventarios_fisicos(usuario["empresa_id"])


class InventarioNuevoIn(BaseModel):
    almacen_id: int
    almacen_nombre: Optional[str] = Field(default=None, max_length=120)
    nombre: Optional[str] = Field(default=None, max_length=120)


@app.post("/api/inventarios")
def api_crear_inventario(payload: InventarioNuevoIn, usuario: dict = Depends(requiere_inventarios)):
    nombre = (payload.nombre or "").strip() or f"Inventario {payload.almacen_nombre or ''} {db.ahora().strftime('%d/%m/%Y')}".replace("  ", " ")
    nuevo = db.crear_inventario_fisico(usuario["empresa_id"], payload.almacen_id, (payload.almacen_nombre or "").strip() or None,
                                       nombre, usuario["id"])
    return db.obtener_inventario_fisico(usuario["empresa_id"], nuevo)


def _agrupar_conteos(conteos):
    """Una fila por (artículo, lote): suma lo contado (varios anaqueles) y toma la
    foto de Microsip del PRIMER conteo de ese lote."""
    grupos = {}
    for c in conteos:
        k = (c["articulo_id"], c.get("lote") or None)
        g = grupos.get(k)
        if not g:
            g = grupos[k] = {"articulo_id": c["articulo_id"], "clave": c.get("clave"), "nombre": c.get("nombre"),
                             "seguimiento": c.get("seguimiento"), "lote": c.get("lote"), "caducidad": c.get("caducidad"),
                             "lote_nuevo": c.get("lote_nuevo"), "contado": 0.0, "teorico": c.get("teorico_lote"),
                             "primer_conteo": c["contado_en"], "conteos": []}
        g["contado"] += float(c["cantidad"] or 0)
        g["conteos"].append({"id": c["id"], "cantidad": c["cantidad"], "contado_por": c.get("contado_por"),
                             "contado_por_id": c.get("contado_por_id"), "contado_en": c["contado_en"],
                             "ubicacion": c.get("ubicacion"), "nota": c.get("nota")})
    for g in grupos.values():
        g["contado"] = round(g["contado"], 4)
        g["diferencia"] = round(g["contado"] - float(g["teorico"] or 0), 4) if g["teorico"] is not None else None
    return sorted(grupos.values(), key=lambda g: (g["nombre"] or "", g["lote"] or ""))


@app.get("/api/inventarios/{inventario_id}")
def api_ver_inventario(inventario_id: int, usuario: dict = Depends(requiere_inventarios)):
    inv = _inventario_de(usuario, inventario_id)
    filas = _agrupar_conteos(db.listar_conteos_inventario(inventario_id))
    inv.pop("resumen_json", None)
    con_imagen = db.articulos_con_imagen(usuario["empresa_id"], [f["articulo_id"] for f in filas])
    for f in filas:
        f["tiene_imagen"] = f["articulo_id"] in con_imagen
    return {**inv, "filas": filas, "puede_cerrar": _es_jefe_inventario(usuario, inv),
            "totales": {"productos": len({f["articulo_id"] for f in filas}), "lineas": len(filas),
                        "piezas": round(sum(f["contado"] for f in filas), 4),
                        "con_diferencia": sum(1 for f in filas if f["diferencia"]),
                        "sin_imagen": len({f["articulo_id"] for f in filas if not f["tiene_imagen"]})}}


@app.get("/api/inventarios/{inventario_id}/buscar")
def api_inventario_buscar(inventario_id: int, q: str, usuario: dict = Depends(requiere_inventarios)):
    _inventario_de(usuario, inventario_id)
    cfg = _config_inventarios(usuario)
    try:
        return microsip_inventario.buscar(cfg, q)
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)


@app.get("/api/inventarios/{inventario_id}/producto")
def api_inventario_producto(inventario_id: int, clave: Optional[str] = None, articulo_id: Optional[int] = None,
                            usuario: dict = Depends(requiere_inventarios)):
    """Al escanear: producto, lotes con caducidad, ubicación / máx / mín / reorden,
    rotación, última venta (aviso si fue hace poco) y lo que ya se contó aquí."""
    inv = _inventario_de(usuario, inventario_id)
    if not clave and not articulo_id:
        raise HTTPException(status_code=400, detail="Escanea o escribe la clave del producto.")
    cfg = _config_inventarios(usuario)
    try:
        p = microsip_inventario.producto(cfg, inv["almacen_id"], clave=clave, articulo_id=articulo_id)
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)
    if not p:
        raise HTTPException(status_code=404, detail=f"No encontré el producto «{clave}» en Microsip.")
    m = _minutos_desde_venta(p.get("ultima_venta"))
    p["minutos_desde_venta"] = m
    p["venta_reciente"] = m is not None and m <= MINUTOS_VENTA_RECIENTE
    p["ya_contado"] = [{"lote": g["lote"], "contado": g["contado"]}
                       for g in _agrupar_conteos(db.listar_conteos_inventario(inventario_id, p["articulo_id"]))]
    img = db.obtener_imagen_articulo(usuario["empresa_id"], p["articulo_id"])
    p["imagen"] = img["imagen"] if img else None
    p["imagen_por"] = img.get("subida_por") if img else None
    # Si ya tiene foto, solo el admin o el encargado la pueden cambiar.
    p["puede_cambiar_imagen"] = not img or usuario["rol"] in ("admin", "encargado_sucursal")
    return p


class ImagenArticuloIn(BaseModel):
    articulo_id: int
    imagen: str = Field(max_length=4_000_000)


@app.put("/api/inventarios/imagen")
def api_inventario_imagen(payload: ImagenArticuloIn, usuario: dict = Depends(requiere_inventarios)):
    """Foto del producto, tomada durante el inventario si no tiene."""
    if not payload.imagen.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="La imagen no es válida")
    if len(payload.imagen) > 3_500_000:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado (máximo 2.5 MB)")
    actual = db.obtener_imagen_articulo(usuario["empresa_id"], payload.articulo_id)
    if actual and usuario["rol"] not in ("admin", "encargado_sucursal"):
        raise HTTPException(status_code=403, detail="Este producto ya tiene foto; solo el encargado o el admin la pueden cambiar.")
    db.guardar_imagen_articulo(usuario["empresa_id"], payload.articulo_id, payload.imagen, usuario["id"])
    return {"ok": True}


class ConteoIn(BaseModel):
    articulo_id: int
    cantidad: float = Field(ge=0, le=10_000_000)
    lote: Optional[str] = Field(default=None, max_length=60)
    caducidad: Optional[str] = Field(default=None, max_length=10)
    ubicacion: Optional[str] = Field(default=None, max_length=60)
    nota: Optional[str] = Field(default=None, max_length=300)


@app.post("/api/inventarios/{inventario_id}/conteos")
def api_inventario_contar(inventario_id: int, payload: ConteoIn, usuario: dict = Depends(requiere_inventarios)):
    """Registra lo contado. Si el producto lleva lote o serie en Microsip, es
    obligatorio (como en el Inventario físico de Microsip). Se guarda la foto de
    la existencia de ese lote en Microsip en este momento."""
    inv = _inventario_de(usuario, inventario_id, abierto=True)
    cfg = _config_inventarios(usuario)
    try:
        p = microsip_inventario.producto(cfg, inv["almacen_id"], articulo_id=payload.articulo_id)
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)
    if not p:
        raise HTTPException(status_code=404, detail="Ese producto ya no existe en Microsip.")
    lote = (payload.lote or "").strip().upper() or None
    seg = p.get("seguimiento")
    if seg and not lote:
        raise HTTPException(status_code=400, detail=f"Este producto lleva {seg} en Microsip: es obligatorio capturarlo.")
    if not seg:
        lote = None
    if seg == "serie" and payload.cantidad not in (0, 1):
        raise HTTPException(status_code=400, detail="Por serie se cuenta 1 pieza por número de serie.")
    existente = next((x for x in p.get("lotes") or [] if (x["lote"] or "").upper() == (lote or "")), None) if lote else None
    caducidad = (existente or {}).get("caducidad") or ((payload.caducidad or "").strip() or None)
    if lote and not existente and seg == "lote" and not caducidad:
        raise HTTPException(status_code=400, detail=f"El lote {lote} no existe en Microsip: captura su caducidad.")
    uv = p.get("ultima_venta")
    datos = {
        "articulo_id": p["articulo_id"], "clave": p.get("clave"), "nombre": p["nombre"], "seguimiento": seg,
        "lote": lote, "caducidad": caducidad, "lote_nuevo": bool(lote and not existente),
        "cantidad": payload.cantidad,
        "teorico_lote": (existente or {}).get("existencia", 0.0) if lote else p["existencia_almacen"],
        "teorico_articulo": p["existencia_almacen"],
        "ultima_venta": f"{uv['fecha']} {uv.get('hora') or ''}".strip() if uv else None,
        "ubicacion": (payload.ubicacion or "").strip() or None, "nota": (payload.nota or "").strip() or None,
    }
    cid = db.agregar_conteo_inventario(inventario_id, datos, usuario["id"])
    return {"ok": True, "id": cid, "lote_nuevo": datos["lote_nuevo"], "teorico": datos["teorico_lote"]}


@app.delete("/api/inventarios/{inventario_id}/conteos/{conteo_id}")
def api_inventario_borrar_conteo(inventario_id: int, conteo_id: int, usuario: dict = Depends(requiere_inventarios)):
    inv = _inventario_de(usuario, inventario_id, abierto=True)
    c = db.obtener_conteo_inventario(conteo_id)
    if not c or c["inventario_id"] != inventario_id:
        raise HTTPException(status_code=404, detail="Conteo no encontrado")
    if c["contado_por_id"] != usuario["id"] and not _es_jefe_inventario(usuario, inv):
        raise HTTPException(status_code=403, detail="Solo quien lo contó o el encargado puede borrarlo.")
    db.eliminar_conteo_inventario(conteo_id)
    return {"ok": True}


class NivelesIn(BaseModel):
    articulo_id: int
    almacen_id: int
    ubicacion: Optional[str] = Field(default=None, max_length=40)
    maximo: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    minimo: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    reorden: Optional[float] = Field(default=None, ge=0, le=10_000_000)


@app.put("/api/inventarios/niveles")
def api_inventario_niveles(payload: NivelesIn, usuario: dict = Depends(requiere_inventarios)):
    """Guarda en Microsip la ubicación / máximo / mínimo / reorden del producto
    en ese almacén (lo que no se mande no se toca)."""
    if payload.maximo is not None and payload.minimo is not None and payload.minimo > payload.maximo:
        raise HTTPException(status_code=400, detail="El mínimo no puede ser mayor que el máximo.")
    cfg = _config_inventarios(usuario)
    datos = {"ubicacion": (payload.ubicacion or "").strip().upper() or None if payload.ubicacion is not None else None,
             "maximo": payload.maximo, "minimo": payload.minimo, "reorden": payload.reorden}
    try:
        cambio = microsip_inventario.guardar_niveles(cfg, payload.articulo_id, payload.almacen_id, datos,
                                                     usuario=usuario.get("username"))
    except microsip_escritura.ErrorMicrosip as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)
    return {"ok": True, "cambio": cambio}


def _revision_inventario(usuario, inv):
    """Diferencias contra la foto, quién se movió después de contarlo y lo que
    Microsip tiene en ese almacén y nadie contó."""
    cfg = _config_inventarios(usuario)
    filas = _agrupar_conteos(db.listar_conteos_inventario(inv["id"]))
    try:
        actuales, ventas, lotes_de = microsip_inventario.existencias_actuales(cfg, inv["almacen_id"], [(f["articulo_id"], f["lote"]) for f in filas])
        en_almacen = microsip_inventario.con_existencia_en_almacen(cfg, inv["almacen_id"])
    except Exception as e:  # noqa: BLE001
        _error_microsip(e)
    for f in filas:
        actual = actuales.get((f["articulo_id"], f["lote"]))
        f["existencia_actual"] = actual
        uv = ventas.get(f["articulo_id"])
        venta = f"{uv['fecha']}T{uv.get('hora') or '00:00'}" if uv else None
        # Se movió después de contarlo: se vendió o cambió su existencia desde la foto.
        f["movido_despues"] = bool((venta and venta[:16] > f["primer_conteo"][:16])
                                   or (actual is not None and f["teorico"] is not None and abs(actual - f["teorico"]) > 0.0001))
        f["ultima_venta"] = uv
    contados = {f["articulo_id"] for f in filas}
    no_contados = sorted((x for a, x in en_almacen.items() if a not in contados), key=lambda x: x["nombre"] or "")
    # Lotes / series con existencia de productos que sí se contaron, pero ese lote no.
    lotes_contados = {(f["articulo_id"], (f["lote"] or "").upper()) for f in filas}
    nombres = {f["articulo_id"]: (f.get("clave"), f.get("nombre")) for f in filas}
    lotes_sin_contar = [{"articulo_id": a, "clave": nombres[a][0], "nombre": nombres[a][1], "lote": x["lote"],
                         "caducidad": x.get("caducidad"), "existencia": x["existencia"]}
                        for a, lotes in lotes_de.items() for x in lotes
                        if x["existencia"] > 0 and (a, (x["lote"] or "").upper()) not in lotes_contados]
    return {
        "filas": filas, "no_contados": no_contados, "lotes_sin_contar": lotes_sin_contar,
        "totales": {"lineas": len(filas), "piezas": round(sum(f["contado"] for f in filas), 4),
                    "sobrantes": sum(1 for f in filas if (f["diferencia"] or 0) > 0),
                    "faltantes": sum(1 for f in filas if (f["diferencia"] or 0) < 0),
                    "exactos": sum(1 for f in filas if f["diferencia"] == 0),
                    "movidos_despues": sum(1 for f in filas if f["movido_despues"]),
                    "lotes_nuevos": sum(1 for f in filas if f["lote_nuevo"]),
                    "no_contados": len(no_contados), "lotes_sin_contar": len(lotes_sin_contar)},
    }


@app.get("/api/inventarios/{inventario_id}/revision")
def api_inventario_revision(inventario_id: int, usuario: dict = Depends(requiere_inventarios)):
    inv = _inventario_de(usuario, inventario_id)
    if inv["estado"] != "abierto" and inv.get("resumen_json"):
        return {**json.loads(inv["resumen_json"]), "cerrado": True}
    return _revision_inventario(usuario, inv)


class CerrarInventarioIn(BaseModel):
    cancelar: bool = False


@app.post("/api/inventarios/{inventario_id}/cerrar")
def api_inventario_cerrar(inventario_id: int, payload: CerrarInventarioIn, usuario: dict = Depends(requiere_inventarios)):
    """Cierra (deja fija la revisión para aplicarla en Microsip) o cancela."""
    inv = _inventario_de(usuario, inventario_id, abierto=True)
    if not _es_jefe_inventario(usuario, inv):
        raise HTTPException(status_code=403, detail="Lo cierra el encargado, un administrador o quien lo abrió.")
    if payload.cancelar:
        db.cambiar_estado_inventario(usuario["empresa_id"], inventario_id, "cancelado", usuario["id"])
        return {"ok": True}
    rev = _revision_inventario(usuario, inv)
    db.cambiar_estado_inventario(usuario["empresa_id"], inventario_id, "cerrado", usuario["id"], json.dumps(rev, default=str))
    return {"ok": True, **rev["totales"]}


@app.get("/api/inventarios/{inventario_id}/excel")
def api_inventario_excel(inventario_id: int, usuario: dict = Depends(requiere_inventarios)):
    """Excel para capturar el Inventario físico en Microsip (y la lista de lo no contado)."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    inv = _inventario_de(usuario, inventario_id)
    rev = json.loads(inv["resumen_json"]) if inv["estado"] != "abierto" and inv.get("resumen_json") else _revision_inventario(usuario, inv)
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Conteo"
    hoja.append([f"{inv['nombre']} — almacén {inv.get('almacen_nombre') or inv['almacen_id']} — {inv['estado']}"])
    hoja["A1"].font = Font(bold=True, size=13)
    hoja.append([])
    hoja.append(["Clave", "Artículo", "Lote/Serie", "Caducidad", "Contado", "Microsip al contar", "Diferencia",
                 "Existencia hoy", "Se movió después de contar", "Lote nuevo"])
    for c in hoja[3]:
        c.font = Font(bold=True)
    rojo, verde, ambar = PatternFill("solid", fgColor="F8CBAD"), PatternFill("solid", fgColor="C6EFCE"), PatternFill("solid", fgColor="FFF2CC")
    for f in rev["filas"]:
        hoja.append([f.get("clave"), f.get("nombre"), f.get("lote") or "", f.get("caducidad") or "", f["contado"],
                     f.get("teorico"), f.get("diferencia"), f.get("existencia_actual"),
                     "Sí, revisar" if f.get("movido_despues") else "", "Sí" if f.get("lote_nuevo") else ""])
        d = f.get("diferencia") or 0
        hoja.cell(row=hoja.max_row, column=7).fill = rojo if d < 0 else (verde if d > 0 else PatternFill())
        if f.get("movido_despues"):
            hoja.cell(row=hoja.max_row, column=9).fill = ambar
    if rev.get("lotes_sin_contar"):
        h3 = libro.create_sheet("Lotes sin contar")
        h3.append(["Clave", "Artículo", "Lote/Serie", "Caducidad", "Existencia en Microsip"])
        for c in h3[1]:
            c.font = Font(bold=True)
        for x in rev["lotes_sin_contar"]:
            h3.append([x.get("clave"), x.get("nombre"), x.get("lote"), x.get("caducidad"), x.get("existencia")])
    if rev.get("no_contados"):
        h2 = libro.create_sheet("No contados")
        h2.append(["Clave", "Artículo", "Existencia en Microsip"])
        for c in h2[1]:
            c.font = Font(bold=True)
        for x in rev["no_contados"]:
            h2.append([x.get("clave"), x.get("nombre"), x.get("existencia")])
    for h in libro.worksheets:
        for col in h.columns:
            h.column_dimensions[col[0].column_letter].width = min(48, max(10, *(len(str(c.value or "")) + 2 for c in col)))
    salida = io.BytesIO()
    libro.save(salida)
    return Response(content=salida.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=inventario_{inventario_id}.xlsx"})
