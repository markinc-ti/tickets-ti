"""Portal de bienvenida para clientes (doctores) + su administración en Logística.

Público (sin login):
  GET  /bienvenida, /bienvenida/{codigo}           -> la página (frontend/bienvenida_clientes.html)
  GET  /api/publico/bienvenida/info                 -> nombre, mensaje y color del portal
  GET  /api/publico/bienvenida/logo                 -> logo de la empresa
  POST /api/publico/bienvenida/consultar            -> {folio} o {token}: equipos, manuales y videos
  GET  /api/publico/bienvenida/archivo/{id}         -> PDF guardado en la base (liga firmada, caduca)

Logística (admin de la empresa o quien es de Logística):
  /api/manuales-clientes/...  config, equipos, recursos, prueba de folio, ligas para WhatsApp, QR.
"""
import base64
import hashlib
import hmac
import os
import sys
import time
import urllib.parse
from collections import defaultdict, deque
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import auth
import db
import manuales_clientes as mc
import manuales_db as mdb
import r2

try:
    import microsip
    MICROSIP_OK = True
except ImportError:
    microsip = None
    MICROSIP_OK = False

router = APIRouter()
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
MAX_PDF_BYTES_R2 = 60 * 1024 * 1024     # en Cloudflare R2
MAX_PDF_BYTES_BASE = 15 * 1024 * 1024   # si R2 no está configurado, se guarda en la base


# ---------------------------------------------------------------- utilidades

def _base_url(request: Request):
    base = os.getenv("APP_BASE_URL_PUBLICA") or os.getenv("APP_BASE_URL")
    if base:
        return base.rstrip("/")
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{request.headers.get('host', request.url.netloc)}"


def _url_portal(request: Request, codigo: str):
    return f"{_base_url(request)}/bienvenida/{codigo}"


def _firma(texto: str) -> str:
    return hmac.new(auth.JWT_SECRET.encode(), texto.encode(), hashlib.sha256).hexdigest()[:24]


def _url_archivo(recurso_id: int) -> str:
    vence = int(time.time()) + 6 * 3600
    return f"/api/publico/bienvenida/archivo/{recurso_id}?e={vence}&k={_firma(f'{recurso_id}.{vence}')}"


def _config_microsip(empresa_id):
    if not MICROSIP_OK:
        raise HTTPException(status_code=503, detail="El servidor no tiene el conector de Microsip instalado.")
    config = db.obtener_config_microsip(empresa_id, real=True)
    if not config or not config.get("microsip_host"):
        raise HTTPException(status_code=400, detail="Microsip no está configurado (Administrar → Microsip).")
    return config


def _buscar_compra(empresa_id, folio):
    config = _config_microsip(empresa_id)
    try:
        return mc.compra_por_folio(microsip._conectar, config, folio)
    except mc.FolioAmbiguo as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[manuales] error consultando Microsip (empresa {empresa_id}, folio {folio!r}): {e}", file=sys.stderr)
        raise HTTPException(status_code=503, detail="No pudimos consultar tu folio en este momento. Intenta más tarde o escríbenos por WhatsApp.")


def _equipos_para_cliente(equipos):
    """Lo que ve el cliente: sin reglas internas ni datos de archivos."""
    salida = []
    for e in equipos:
        recursos = []
        for r in e["recursos"]:
            item = {"id": r["id"], "tipo": r["tipo"], "titulo": r["titulo"]}
            if r["tipo"] == "pdf":
                item["url"] = r["url"] if r.get("url") else _url_archivo(r["id"])
                item["archivo_nombre"] = r.get("archivo_nombre")
            else:
                item["url"] = r.get("url")
                if r["tipo"] == "video":
                    item["youtube_id"] = mc.youtube_id(r.get("url"))
            recursos.append(item)
        salida.append({"id": e["id"], "nombre": e["nombre"], "descripcion": e.get("descripcion"),
                       "categoria": e.get("categoria"), "general": bool(e.get("para_todos") and not e.get("motivos")),
                       "recursos": recursos})
    return salida


def requiere_admin_manuales(usuario: dict = Depends(auth.get_current_user)) -> dict:
    """El administrador de la empresa o quien sea de Logística."""
    if usuario.get("rol") in ("superadmin", "master") or not usuario.get("empresa_id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a los manuales para clientes")
    if usuario["rol"] == "admin" or db.es_logistica_reparaciones(usuario["id"]):
        return usuario
    raise HTTPException(status_code=403, detail="Solo Logística o el administrador pueden administrar los manuales para clientes")


# Límite de intentos por IP para que no se puedan adivinar folios en serie.
_INTENTOS = defaultdict(deque)
_MAX_INTENTOS, _VENTANA_SEG = 15, 600


def _limitar(ip):
    ahora = time.time()
    q = _INTENTOS[ip]
    while q and ahora - q[0] > _VENTANA_SEG:
        q.popleft()
    if len(q) >= _MAX_INTENTOS:
        raise HTTPException(status_code=429, detail="Hiciste muchas búsquedas seguidas. Espera unos minutos e inténtalo de nuevo.")
    q.append(ahora)


def _ip(request: Request):
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()


# ---------------------------------------------------------------- páginas públicas

@router.get("/bienvenida")
def pagina_bienvenida():
    return FileResponse(os.path.join(FRONTEND_DIR, "bienvenida_clientes.html"), headers={"Cache-Control": "no-cache"})


@router.get("/bienvenida/{codigo}")
def pagina_bienvenida_codigo(codigo: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "bienvenida_clientes.html"), headers={"Cache-Control": "no-cache"})


@router.get("/api/publico/bienvenida/info")
def api_info_portal(codigo: Optional[str] = None):
    cfg = mdb.config_publica(codigo)
    if not cfg:
        raise HTTPException(status_code=404, detail="Esta página no está disponible.")
    return {"codigo": cfg["codigo"], "empresa": cfg["empresa_nombre"], "titulo": cfg.get("titulo"),
            "mensaje": cfg.get("mensaje"), "whatsapp": cfg.get("whatsapp"), "color": cfg.get("color_acento"),
            "tiene_logo": bool(mdb.logo_empresa(cfg["empresa_id"]))}


@router.get("/api/publico/bienvenida/logo")
def api_logo_portal(codigo: Optional[str] = None):
    cfg = mdb.config_publica(codigo)
    logo = mdb.logo_empresa(cfg["empresa_id"]) if cfg else None
    if not logo:
        raise HTTPException(status_code=404, detail="Sin logo")
    tipo = "image/png"
    if logo.startswith("data:"):
        cabecera, logo = logo.split(",", 1)
        tipo = cabecera[5:].split(";")[0] or tipo
    return Response(content=base64.b64decode(logo), media_type=tipo, headers={"Cache-Control": "public, max-age=86400"})


class ConsultaIn(BaseModel):
    codigo: Optional[str] = None
    folio: Optional[str] = Field(default=None, max_length=30)
    token: Optional[str] = Field(default=None, max_length=40)


@router.post("/api/publico/bienvenida/consultar")
async def api_consultar_portal(payload: ConsultaIn, request: Request):
    saludo = None
    if payload.token:
        liga = await run_in_threadpool(mdb.obtener_liga, payload.token.strip())
        if not liga:
            raise HTTPException(status_code=404, detail="Esta liga ya no es válida. Escribe el folio de tu pedido, factura o remisión.")
        cfg = mdb.obtener_config(liga["empresa_id"], crear=False)
        if not cfg or not cfg.get("activo"):
            raise HTTPException(status_code=404, detail="Esta página no está disponible.")
        folio, origen, saludo = liga["folio"], "liga", liga.get("cliente_nombre")
    else:
        cfg = mdb.config_publica(payload.codigo)
        if not cfg:
            raise HTTPException(status_code=404, detail="Esta página no está disponible.")
        folio = (payload.folio or "").strip()
        if len(folio) < 2:
            raise HTTPException(status_code=400, detail="Escribe el folio de tu pedido, factura o remisión.")
        _limitar(_ip(request))
        origen = "folio"
    empresa_id = cfg["empresa_id"]
    compra = await run_in_threadpool(_buscar_compra, empresa_id, folio)
    if not compra:
        mdb.registrar_consulta(empresa_id, folio, origen, False, "", _ip(request))
        raise HTTPException(status_code=404, detail="No encontramos ese folio. Revisa que esté escrito igual que en tu pedido, factura o remisión.")
    equipos, _ = mc.emparejar(compra["articulos"], mdb.listar_equipos(empresa_id, solo_activos=True))
    mdb.registrar_consulta(empresa_id, folio, origen, True, ", ".join(e["nombre"] for e in equipos), _ip(request))
    return {
        "saludo": saludo,  # solo con la liga personal; con el folio no se muestra el nombre del cliente
        "documentos": [{"folio": d["folio"], "tipo": d["tipo_nombre"]} for d in compra["documentos"]],
        "equipos": _equipos_para_cliente(equipos),
        "whatsapp": cfg.get("whatsapp"),
    }


@router.get("/api/publico/bienvenida/archivo/{recurso_id}")
def api_archivo_portal(recurso_id: int, e: int, k: str):
    if e < time.time() or not hmac.compare_digest(k, _firma(f"{recurso_id}.{e}")):
        raise HTTPException(status_code=403, detail="La liga del archivo ya caducó. Vuelve a abrir la página y consulta tu folio.")
    rec = mdb.archivo_recurso(recurso_id)
    if not rec or not rec.get("archivo_base64"):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    nombre = (rec.get("archivo_nombre") or "manual.pdf").replace('"', "")
    return Response(content=base64.b64decode(rec["archivo_base64"]), media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=\"{nombre}\""})


# ---------------------------------------------------------------- administración (Logística)

class ConfigIn(BaseModel):
    activo: bool = True
    codigo: str = Field(min_length=2, max_length=41)
    titulo: Optional[str] = Field(default=None, max_length=120)
    mensaje: Optional[str] = Field(default=None, max_length=1500)
    whatsapp: Optional[str] = Field(default=None, max_length=20)


@router.get("/api/manuales-clientes/config")
def api_config(request: Request, usuario: dict = Depends(requiere_admin_manuales)):
    cfg = mdb.obtener_config(usuario["empresa_id"])
    return {**cfg, "url_portal": _url_portal(request, cfg["codigo"]), "url_corta": f"{_base_url(request)}/bienvenida",
            "r2": r2.configurado()}


@router.put("/api/manuales-clientes/config")
def api_guardar_config(payload: ConfigIn, request: Request, usuario: dict = Depends(requiere_admin_manuales)):
    whatsapp = _tel_mx(payload.whatsapp) or None
    try:
        cfg = mdb.guardar_config(usuario["empresa_id"], payload.activo, payload.codigo, (payload.titulo or "").strip() or None,
                                 (payload.mensaje or "").strip() or None, whatsapp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**cfg, "url_portal": _url_portal(request, cfg["codigo"]), "url_corta": f"{_base_url(request)}/bienvenida",
            "r2": r2.configurado()}


class ReglaIn(BaseModel):
    tipo: Literal["articulo", "clave", "texto"]
    valor: str = Field(min_length=1, max_length=200)
    articulo_id: Optional[int] = None
    etiqueta: Optional[str] = Field(default=None, max_length=300)


class EquipoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=1000)
    categoria: Optional[str] = Field(default=None, max_length=60)
    para_todos: bool = False
    activo: bool = True
    orden: int = 0
    reglas: List[ReglaIn] = []


@router.get("/api/manuales-clientes/equipos")
def api_equipos(usuario: dict = Depends(requiere_admin_manuales)):
    return mdb.listar_equipos(usuario["empresa_id"])


def _validar_equipo(payload: EquipoIn):
    if not payload.para_todos and not payload.reglas:
        raise HTTPException(status_code=400, detail="Agrega al menos un artículo de Microsip o una palabra para saber a quién le toca este equipo (o márcalo 'para todos los clientes').")


@router.post("/api/manuales-clientes/equipos")
def api_crear_equipo(payload: EquipoIn, usuario: dict = Depends(requiere_admin_manuales)):
    _validar_equipo(payload)
    datos = payload.model_dump()
    datos["nombre"] = datos["nombre"].strip()
    nuevo = mdb.crear_equipo(usuario["empresa_id"], datos)
    return mdb.obtener_equipo(usuario["empresa_id"], nuevo)


@router.put("/api/manuales-clientes/equipos/{equipo_id}")
def api_editar_equipo(equipo_id: int, payload: EquipoIn, usuario: dict = Depends(requiere_admin_manuales)):
    _validar_equipo(payload)
    datos = payload.model_dump()
    datos["nombre"] = datos["nombre"].strip()
    if not mdb.editar_equipo(usuario["empresa_id"], equipo_id, datos):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return mdb.obtener_equipo(usuario["empresa_id"], equipo_id)


@router.delete("/api/manuales-clientes/equipos/{equipo_id}")
def api_eliminar_equipo(equipo_id: int, usuario: dict = Depends(requiere_admin_manuales)):
    ok, llaves = mdb.eliminar_equipo(usuario["empresa_id"], equipo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    for k in llaves:
        try:
            r2.eliminar_video(k)
        except Exception as e:
            print(f"[manuales] no se pudo borrar {k} de R2: {e}", file=sys.stderr)
    return {"ok": True}


@router.post("/api/manuales-clientes/equipos/{equipo_id}/recursos")
async def api_agregar_recurso(equipo_id: int, request: Request, tipo: str = Form(...), titulo: str = Form(...),
                              url: Optional[str] = Form(None), archivo: Optional[UploadFile] = File(None),
                              usuario: dict = Depends(requiere_admin_manuales)):
    titulo = (titulo or "").strip()[:200]
    if not titulo:
        raise HTTPException(status_code=400, detail="Ponle un título (por ejemplo: Manual de usuario).")
    if tipo not in ("pdf", "video", "link"):
        raise HTTPException(status_code=400, detail="Tipo inválido")
    empresa_id = usuario["empresa_id"]
    if tipo in ("video", "link"):
        url = (url or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Pega la liga completa (debe empezar con https://).")
        if tipo == "video" and not mc.youtube_id(url):
            raise HTTPException(status_code=400, detail="Esa liga no parece de YouTube. Si es de otro sitio, agrégala como 'Liga'.")
        nuevo = mdb.agregar_recurso(empresa_id, equipo_id, tipo, titulo, url=url)
    else:
        if archivo is None:
            raise HTTPException(status_code=400, detail="Elige el archivo PDF.")
        nombre = archivo.filename or "manual.pdf"
        archivo.file.seek(0, 2)
        tamano = archivo.file.tell()
        archivo.file.seek(0)
        if tamano == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío.")
        cabeza = archivo.file.read(5)
        archivo.file.seek(0)
        if cabeza != b"%PDF-":
            raise HTTPException(status_code=400, detail="El archivo no es un PDF.")
        if r2.configurado():
            if tamano > MAX_PDF_BYTES_R2:
                raise HTTPException(status_code=400, detail="El PDF pesa más de 60 MB. Comprímelo antes de subirlo.")
            try:
                key, url_pub = await run_in_threadpool(r2.subir_video, empresa_id, nombre, archivo.file, "application/pdf")
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"No se pudo subir el PDF a Cloudflare R2: {e}")
            nuevo = mdb.agregar_recurso(empresa_id, equipo_id, "pdf", titulo, url=url_pub, r2_key=key,
                                        archivo_nombre=nombre, tamano=tamano)
        else:
            if tamano > MAX_PDF_BYTES_BASE:
                raise HTTPException(status_code=400, detail="El PDF pesa más de 15 MB. Comprímelo o configura Cloudflare R2 para archivos grandes.")
            contenido = base64.b64encode(archivo.file.read()).decode()
            nuevo = mdb.agregar_recurso(empresa_id, equipo_id, "pdf", titulo, archivo_base64=contenido,
                                        archivo_nombre=nombre, tamano=tamano)
    if not nuevo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return mdb.obtener_equipo(empresa_id, equipo_id)


class RecursoEdicion(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    orden: int = 0
    url: Optional[str] = Field(default=None, max_length=1000)


@router.put("/api/manuales-clientes/recursos/{recurso_id}")
def api_editar_recurso(recurso_id: int, payload: RecursoEdicion, usuario: dict = Depends(requiere_admin_manuales)):
    if not mdb.editar_recurso(usuario["empresa_id"], recurso_id, payload.titulo.strip(), payload.orden,
                              (payload.url or "").strip() or None):
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"ok": True}


@router.delete("/api/manuales-clientes/recursos/{recurso_id}")
def api_eliminar_recurso(recurso_id: int, usuario: dict = Depends(requiere_admin_manuales)):
    ok, key = mdb.eliminar_recurso(usuario["empresa_id"], recurso_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No encontrado")
    if key:
        try:
            r2.eliminar_video(key)
        except Exception as e:
            print(f"[manuales] no se pudo borrar {key} de R2: {e}", file=sys.stderr)
    return {"ok": True}


@router.get("/api/manuales-clientes/recursos/{recurso_id}/ver")
def api_ver_recurso(recurso_id: int, usuario: dict = Depends(requiere_admin_manuales)):
    """Liga para que Logística revise un PDF guardado en la base."""
    for e in mdb.listar_equipos(usuario["empresa_id"]):
        for r in e["recursos"]:
            if r["id"] == recurso_id:
                return {"url": r["url"] or _url_archivo(recurso_id)}
    raise HTTPException(status_code=404, detail="No encontrado")


@router.get("/api/manuales-clientes/microsip/articulos")
def api_buscar_articulos(q: str, usuario: dict = Depends(requiere_admin_manuales)):
    config = _config_microsip(usuario["empresa_id"])
    try:
        return microsip.buscar_productos_por_nombre(config, q, limite=40)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error consultando Microsip: {e}")


@router.get("/api/manuales-clientes/probar")
def api_probar_folio(folio: str, usuario: dict = Depends(requiere_admin_manuales)):
    """Lo que vería el cliente con ese folio, más los artículos que no tienen equipo ligado."""
    compra = _buscar_compra(usuario["empresa_id"], folio)
    if not compra:
        raise HTTPException(status_code=404, detail="No hay ningún pedido, remisión o factura vigente con ese folio.")
    equipos, sin_equipo = mc.emparejar(compra["articulos"], mdb.listar_equipos(usuario["empresa_id"], solo_activos=True))
    return {
        "documentos": compra["documentos"], "cliente_nombre": compra["cliente_nombre"], "telefono": compra["telefono"],
        "equipos": [{"id": e["id"], "nombre": e["nombre"], "motivos": e["motivos"], "general": bool(e.get("para_todos") and not e["motivos"]),
                     "recursos": len(e["recursos"])} for e in equipos],
        "sin_equipo": [{"nombre": a["nombre"], "claves": a["claves"], "articulo_id": a["articulo_id"]} for a in sin_equipo],
    }


class LigaIn(BaseModel):
    folio: str = Field(min_length=2, max_length=30)
    telefono: Optional[str] = Field(default=None, max_length=20)


def _nombre_bonito(n):
    return " ".join(p[:1].upper() + p[1:].lower() for p in (n or "").split())


def _tel_mx(t):
    d = "".join(ch for ch in (t or "") if ch.isdigit())
    if len(d) == 10:
        d = "52" + d
    return d


@router.post("/api/manuales-clientes/ligas")
def api_crear_liga(payload: LigaIn, request: Request, usuario: dict = Depends(requiere_admin_manuales)):
    """Liga personal para mandar por WhatsApp: abre directo los manuales de esa compra y saluda al doctor."""
    empresa_id = usuario["empresa_id"]
    cfg = mdb.obtener_config(empresa_id)
    compra = _buscar_compra(empresa_id, payload.folio)
    if not compra:
        raise HTTPException(status_code=404, detail="No hay ningún pedido, remisión o factura vigente con ese folio.")
    folio = compra["documentos"][0]["folio"]
    telefono = _tel_mx(payload.telefono or compra["telefono"])
    token = mdb.crear_liga(empresa_id, folio, compra["cliente_nombre"], telefono, usuario["id"])
    url = f"{_url_portal(request, cfg['codigo'])}?t={token}"
    equipos, _ = mc.emparejar(compra["articulos"], mdb.listar_equipos(empresa_id, solo_activos=True))
    nombres = [e["nombre"] for e in equipos if e["motivos"]]
    empresa = (db.obtener_empresa(empresa_id) or {}).get("nombre", "")
    texto = (f"¡Hola, Dr(a). {_nombre_bonito(compra['cliente_nombre'])}! 👋\n\n"
             f"Gracias por tu compra en {empresa}. Te damos la bienvenida.\n\n"
             + (f"Aquí tienes los manuales y videos de tu {', '.join(nombres)}:\n" if nombres else
                "Aquí tienes los manuales y videos de tu equipo:\n")
             + f"{url}\n\nCualquier duda, estamos para ayudarte.")
    return {"url": url, "telefono": telefono, "mensaje": texto,
            "wa_url": f"https://wa.me/{telefono}?text={urllib.parse.quote(texto)}" if telefono else
                      f"https://wa.me/?text={urllib.parse.quote(texto)}",
            "cliente_nombre": compra["cliente_nombre"], "equipos": nombres}


@router.get("/api/manuales-clientes/ligas")
def api_listar_ligas(request: Request, usuario: dict = Depends(requiere_admin_manuales)):
    cfg = mdb.obtener_config(usuario["empresa_id"])
    base = _url_portal(request, cfg["codigo"])
    return [{**x, "url": f"{base}?t={x['token']}"} for x in mdb.listar_ligas(usuario["empresa_id"])]


@router.get("/api/manuales-clientes/consultas")
def api_listar_consultas(usuario: dict = Depends(requiere_admin_manuales)):
    return mdb.listar_consultas(usuario["empresa_id"])


@router.get("/api/manuales-clientes/qr.pdf")
def api_qr_pdf(request: Request, modo: str = "hoja", corta: bool = False, usuario: dict = Depends(requiere_admin_manuales)):
    cfg = mdb.obtener_config(usuario["empresa_id"])
    url = f"{_base_url(request)}/bienvenida" if corta else _url_portal(request, cfg["codigo"])
    empresa = (db.obtener_empresa(usuario["empresa_id"]) or {}).get("nombre", "")
    pdf = mc.pdf_qr(url, empresa, "grande" if modo == "grande" else "hoja")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=qr_manuales_{cfg['codigo']}.pdf"})
