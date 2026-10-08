# -*- coding: utf-8 -*-
"""
Turnos por sucursal (como en un banco): pantalla con video + número
llamado, kiosko para tomar turno, y el mostrador lo llama a su ventanilla

Un cliente toma su turno en una tablet/PC de entrada (kiosko, sin login).
El mostrador -- desde su sesión normal, en el nuevo menú "🛎️ Turnos" --
llama al siguiente turno con un botón; se le asigna su ventanilla/caja
fija (o su nombre, si no tiene una asignada). Una pantalla en la sala de
espera (tampoco con login) muestra el número llamado + un video en loop
(YouTube/Drive/Vimeo/OneDrive), con un tono cuando se llama uno nuevo.

No todas las empresas lo usan -- es un módulo más, como RH o Shopify: se
prende/apaga por empresa en Administrar > Empresas, y cada persona del
mostrador necesita el permiso "🎫 Turnos" + tener una sucursal asignada
para poder llamar. Las sucursales son las mismas de Reparaciones
(sucursales_reparacion) -- ya es el catálogo general de la empresa, no
hace falta uno nuevo.

Cómo generar las ligas de Pantalla/Kiosko de una sucursal: Administrar >
Sucursales > botón "Configurar" en la fila de esa sucursal.

Qué toca:
  - backend/db.py -- tabla turnos, columnas nuevas en sucursales_reparacion
    (codigo_turnos, turnos_videos) y en users (acceso_turnos,
    ventanilla_turnos), módulo modulo_turnos, y las funciones para
    tomar/llamar/atender/cancelar turnos y generar las ligas.
  - backend/app.py -- endpoints nuevos (mostrador, admin, y las 2 páginas
    públicas de pantalla/kiosko) y los permisos de usuario/módulo.
  - frontend/index.html -- pantalla "🛎️ Turnos" del mostrador, la
    configuración por sucursal (videos + ligas), y los permisos en
    Usuarios/Accesos/Empresas.
  - frontend/pantalla_turnos.html, frontend/kiosko_turnos.html -- páginas
    NUEVAS (públicas, sin login) que este script coloca directo en
    frontend/ -- no tienen nada que parchar, solo hace falta el `git add`.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_turnos_por_sucursal.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['backend/db.py'] = [
    [
        '''    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'")
    if cur.fetchone()["n"] == 0:
''',
        '''    conn.commit()

    # ---- Turnos por sucursal (como en un banco): un cliente toma un turno,
    # el mostrador lo llama a su ventanilla fija, y una pantalla en sala de
    # espera muestra el número llamado + un video en loop. Reusa
    # sucursales_reparacion como catálogo de sucursales -- ya es el catálogo
    # general de la empresa (users.sucursal_id ya lo usa así), no exclusivo
    # de Reparaciones. La pantalla y el kiosko de "tomar turno" son páginas
    # públicas (sin login) protegidas por codigo_turnos, igual que el link
    # de seguimiento de entregas.
    cur.execute("""
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS codigo_turnos TEXT UNIQUE;
        ALTER TABLE sucursales_reparacion ADD COLUMN IF NOT EXISTS turnos_videos TEXT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS acceso_turnos BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS ventanilla_turnos TEXT;
        ALTER TABLE empresas ADD COLUMN IF NOT EXISTS modulo_turnos BOOLEAN NOT NULL DEFAULT TRUE;

        CREATE TABLE IF NOT EXISTS turnos (
            id SERIAL PRIMARY KEY,
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            sucursal_id INTEGER NOT NULL REFERENCES sucursales_reparacion(id),
            numero INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'esperando',
            ventanilla TEXT,
            llamado_por_id INTEGER REFERENCES users(id),
            creado_en TEXT NOT NULL,
            llamado_en TEXT,
            atendido_en TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_turnos_sucursal_fecha_estado ON turnos(sucursal_id, fecha, estado);
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM users WHERE rol = 'superadmin'")
    if cur.fetchone()["n"] == 0:
''',
    ],
    [
        '''    "modulo_marketing": "acceso_marketing", "modulo_crm": "acceso_crm", "modulo_asistente_ia": "acceso_asistente_ia",
    "modulo_shopify": "acceso_shopify",
}

''',
        '''    "modulo_marketing": "acceso_marketing", "modulo_crm": "acceso_crm", "modulo_asistente_ia": "acceso_asistente_ia",
    "modulo_shopify": "acceso_shopify",
    "modulo_turnos": "acceso_turnos",
}

''',
    ],
    [
        '''                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_entregas,
                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_shopify, u.monitoreo_activo,
                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,
                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,
''',
        '''                  u.acceso_rh, u.acceso_dashboard, u.acceso_tickets, u.acceso_reparaciones, u.acceso_laboratorio, u.acceso_laboratorio_entrega, u.acceso_entregas,
                  u.acceso_checador_precio, u.acceso_marketing, u.acceso_crm, u.acceso_asistente_ia, u.acceso_datos_empleado_rh, u.acceso_shopify, u.monitoreo_activo,
                  u.acceso_turnos, u.ventanilla_turnos,
                  (SELECT MAX(fecha_aceptacion) FROM consentimientos_monitoreo c WHERE c.usuario_id = u.id) AS monitoreo_aceptado_en,
                  u.numero_empleado, u.sucursal_id, s.nombre AS sucursal_nombre,
''',
    ],
    [
        '''        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,
                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_entregas, acceso_checador_precio,
                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_shopify, monitoreo_activo
           FROM users WHERE id = %s""",
        (usuario_id,),
''',
        '''        """SELECT restriccion_categoria, acceso_equipos, acceso_administracion, acceso_compras, acceso_rh,
                  acceso_dashboard, acceso_tickets, acceso_reparaciones, acceso_laboratorio, acceso_laboratorio_entrega, acceso_entregas, acceso_checador_precio,
                  acceso_marketing, acceso_crm, acceso_asistente_ia, acceso_datos_empleado_rh, acceso_shopify, monitoreo_activo,
                  acceso_turnos, ventanilla_turnos
           FROM users WHERE id = %s""",
        (usuario_id,),
''',
    ],
    [
        '''                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,
                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,
                        acceso_datos_empleado_rh=None, acceso_shopify=None,
                        monitoreo_activo=None,
                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",
                        rfc="__sin_cambio__", curp="__sin_cambio__", numero_licencia="__sin_cambio__",
                        tipo_licencia="__sin_cambio__", vigencia_licencia="__sin_cambio__"):
    conn = get_connection()
    cur = conn.cursor()
''',
        '''                        acceso_tickets=None, acceso_reparaciones=None, acceso_laboratorio=None, acceso_laboratorio_entrega=None, acceso_entregas=None,
                        acceso_checador_precio=None, acceso_marketing=None, acceso_crm=None, acceso_asistente_ia=None,
                        acceso_datos_empleado_rh=None, acceso_shopify=None, acceso_turnos=None,
                        monitoreo_activo=None,
                        sucursal_id="__sin_cambio__", numero_empleado="__sin_cambio__",
                        rfc="__sin_cambio__", curp="__sin_cambio__", numero_licencia="__sin_cambio__",
                        tipo_licencia="__sin_cambio__", vigencia_licencia="__sin_cambio__",
                        ventanilla_turnos="__sin_cambio__"):
    conn = get_connection()
    cur = conn.cursor()
''',
    ],
    [
        '''    if acceso_shopify is not None:
        campos.append("acceso_shopify = %s"); valores.append(acceso_shopify)
    if monitoreo_activo is not None:
        campos.append("monitoreo_activo = %s"); valores.append(monitoreo_activo)
''',
        '''    if acceso_shopify is not None:
        campos.append("acceso_shopify = %s"); valores.append(acceso_shopify)
    if acceso_turnos is not None:
        campos.append("acceso_turnos = %s"); valores.append(acceso_turnos)
    if ventanilla_turnos != "__sin_cambio__":  # permite mandar None explícito para quitarla
        campos.append("ventanilla_turnos = %s"); valores.append(ventanilla_turnos)
    if monitoreo_activo is not None:
        campos.append("monitoreo_activo = %s"); valores.append(monitoreo_activo)
''',
    ],
    [
        '''    cur.close(); conn.close()
    return obtener_sucursal_reparacion(empresa_id, sucursal_id)


''',
        '''    cur.close(); conn.close()
    return obtener_sucursal_reparacion(empresa_id, sucursal_id)


# ---- Turnos por sucursal ----

def obtener_o_crear_codigo_turnos(sucursal_id):
    """Igual que el token de calendario: cada sucursal tiene su propio link
    secreto de Pantalla/Kiosko, se genera la primera vez que se pide y de
    ahí siempre es el mismo (para no romper el que ya esté pegado en una
    tablet o una smart TV de la sucursal)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT codigo_turnos FROM sucursales_reparacion WHERE id = %s", (sucursal_id,))
    row = cur.fetchone()
    if row and row["codigo_turnos"]:
        cur.close(); conn.close()
        return row["codigo_turnos"]
    codigo = secrets.token_urlsafe(16)
    cur.execute("UPDATE sucursales_reparacion SET codigo_turnos = %s WHERE id = %s", (codigo, sucursal_id))
    conn.commit()
    cur.close(); conn.close()
    return codigo


def regenerar_codigo_turnos(sucursal_id):
    """Por si el link se compartió sin querer -- invalida el viejo (la
    pantalla/kiosko que ya lo tenían pegado dejan de funcionar hasta que
    se les ponga el nuevo)."""
    codigo = secrets.token_urlsafe(16)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sucursales_reparacion SET codigo_turnos = %s WHERE id = %s", (codigo, sucursal_id))
    conn.commit()
    cur.close(); conn.close()
    return codigo


def obtener_sucursal_por_codigo_turnos(codigo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sucursales_reparacion WHERE codigo_turnos = %s AND activo = TRUE", (codigo,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def actualizar_videos_turnos_sucursal(empresa_id, sucursal_id, videos):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sucursales_reparacion SET turnos_videos = %s WHERE id = %s AND empresa_id = %s",
                (json.dumps(videos), sucursal_id, empresa_id))
    conn.commit()
    cur.close(); conn.close()


def _fecha_hoy_turnos():
    return ahora().strftime("%Y-%m-%d")


def tomar_turno(empresa_id, sucursal_id):
    """El número más alto YA USADO ese día en esa sucursal + 1 -- mismo
    criterio que _next_folio_reparacion (no un conteo, para que no se
    repita si algún turno se cancela)."""
    conn = get_connection()
    cur = conn.cursor()
    fecha = _fecha_hoy_turnos()
    cur.execute("SELECT COALESCE(MAX(numero), 0) AS maximo FROM turnos WHERE sucursal_id = %s AND fecha = %s",
                (sucursal_id, fecha))
    numero = cur.fetchone()["maximo"] + 1
    cur.execute(
        """INSERT INTO turnos (empresa_id, sucursal_id, numero, fecha, estado, creado_en)
           VALUES (%s, %s, %s, %s, 'esperando', %s) RETURNING id""",
        (empresa_id, sucursal_id, numero, fecha, ahora().isoformat()),
    )
    turno_id = cur.fetchone()["id"]
    conn.commit()
    cur.close(); conn.close()
    return {"id": turno_id, "numero": numero}


def listar_turnos_esperando(sucursal_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM turnos WHERE sucursal_id = %s AND fecha = %s AND estado = 'esperando' ORDER BY numero ASC",
        (sucursal_id, _fecha_hoy_turnos()),
    )
    filas = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return filas


def obtener_turno(turno_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM turnos WHERE id = %s", (turno_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def llamar_turno(turno_id, ventanilla, usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE turnos SET estado = 'llamado', ventanilla = %s, llamado_por_id = %s, llamado_en = %s WHERE id = %s",
        (ventanilla, usuario_id, ahora().isoformat(), turno_id),
    )
    conn.commit()
    cur.close(); conn.close()


def atender_turno(turno_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE turnos SET estado = 'atendido', atendido_en = %s WHERE id = %s", (ahora().isoformat(), turno_id))
    conn.commit()
    cur.close(); conn.close()


def cancelar_turno(turno_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE turnos SET estado = 'cancelado' WHERE id = %s", (turno_id,))
    conn.commit()
    cur.close(); conn.close()


def estado_pantalla_turnos(sucursal_id):
    """Para la pantalla pública: los últimos turnos llamados (para que se
    sigan viendo un rato aunque ya se hayan atendido) y cuántos quedan
    esperando -- nada más, no se expone la fila completa."""
    conn = get_connection()
    cur = conn.cursor()
    fecha = _fecha_hoy_turnos()
    cur.execute(
        """SELECT numero, ventanilla, estado, llamado_en
           FROM turnos WHERE sucursal_id = %s AND fecha = %s AND estado IN ('llamado', 'atendido')
           ORDER BY llamado_en DESC LIMIT 6""",
        (sucursal_id, fecha),
    )
    llamados = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) AS n FROM turnos WHERE sucursal_id = %s AND fecha = %s AND estado = 'esperando'",
                (sucursal_id, fecha))
    esperando = cur.fetchone()["n"]
    cur.close(); conn.close()
    return {"llamados": llamados, "esperando": esperando}


''',
    ],
]

ARCHIVOS['backend/app.py'] = [
    [
        '''import os
import re
''',
        '''import json
import os
import re
''',
    ],
    [
        '''    if not usuario.get("acceso_shopify", True):
        raise HTTPException(status_code=403, detail="No tienes acceso a Shopify")
    return usuario

''',
        '''    if not usuario.get("acceso_shopify", True):
        raise HTTPException(status_code=403, detail="No tienes acceso a Shopify")
    return usuario


def requiere_acceso_turnos(usuario: dict = Depends(requiere_empresa)) -> dict:
    usuario = _con_permisos(usuario)
    if not usuario.get("acceso_turnos", True):
        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Turnos")
    return usuario

''',
    ],
    [
        '''            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),
            "acceso_shopify": usuario.get("acceso_shopify", True),
            "acceso_dashboard": usuario.get("acceso_dashboard", True) if es_admin else True,
            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,
        },
        "monitoreo": {
            "activo": usuario.get("monitoreo_activo", False),
''',
        '''            "acceso_datos_empleado_rh": usuario.get("acceso_datos_empleado_rh", False),
            "acceso_shopify": usuario.get("acceso_shopify", True),
            "acceso_turnos": usuario.get("acceso_turnos", True),
            "acceso_dashboard": usuario.get("acceso_dashboard", True) if es_admin else True,
            "restriccion_categoria": usuario.get("restriccion_categoria") if es_admin else None,
        },
        "mi_ventanilla_turnos": usuario.get("ventanilla_turnos"),
        "monitoreo": {
            "activo": usuario.get("monitoreo_activo", False),
''',
    ],
    [
        '''    acceso_datos_empleado_rh: Optional[bool] = None
    acceso_shopify: Optional[bool] = None
    monitoreo_activo: Optional[bool] = None
    sucursal_id: Optional[int] = None
''',
        '''    acceso_datos_empleado_rh: Optional[bool] = None
    acceso_shopify: Optional[bool] = None
    acceso_turnos: Optional[bool] = None
    ventanilla_turnos: Optional[str] = None
    monitoreo_activo: Optional[bool] = None
    sucursal_id: Optional[int] = None
''',
    ],
    [
        '''    if "vigencia_licencia" in enviados:
        kwargs_extra["vigencia_licencia"] = payload.vigencia_licencia

    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,
''',
        '''    if "vigencia_licencia" in enviados:
        kwargs_extra["vigencia_licencia"] = payload.vigencia_licencia
    if "ventanilla_turnos" in enviados:
        kwargs_extra["ventanilla_turnos"] = payload.ventanilla_turnos  # puede ser None para quitarla

    db.actualizar_usuario(usuario_id, payload.nombre_completo, payload.rol, payload.telefono_whatsapp,
''',
    ],
    [
        '''                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,
                           acceso_shopify=payload.acceso_shopify,
                           monitoreo_activo=payload.monitoreo_activo,
                           **kwargs_extra)
''',
        '''                           acceso_datos_empleado_rh=payload.acceso_datos_empleado_rh,
                           acceso_shopify=payload.acceso_shopify,
                           acceso_turnos=payload.acceso_turnos,
                           monitoreo_activo=payload.monitoreo_activo,
                           **kwargs_extra)
''',
    ],
    [
        '''

class NuevaReparacion(BaseModel):
    sucursal_id: int
''',
        '''

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
    ventanilla = usuario.get("ventanilla_turnos") or usuario["nombre_completo"]
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
    return {"sucursal_nombre": sucursal["nombre"], "videos": videos, **estado}


@app.post("/api/turnos/kiosko/{codigo}/tomar")
def api_kiosko_tomar_turno(codigo: str):
    sucursal = db.obtener_sucursal_por_codigo_turnos(codigo)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Este kiosko no es válido")
    turno = db.tomar_turno(sucursal["empresa_id"], sucursal["id"])
    return {"numero": turno["numero"], "sucursal_nombre": sucursal["nombre"]}


class NuevaReparacion(BaseModel):
    sucursal_id: int
''',
    ],
]

ARCHIVOS['frontend/index.html'] = [
    [
        '''      <button class="menu-boton" id="btnCRM" onclick="abrirCRM()" style="display:none;"><span class="menu-icono">🤝</span>CRM de Ventas</button>
      <button class="menu-boton" id="btnShopify" onclick="abrirShopify()" style="display:none;"><span class="menu-icono">🛍️</span>Shopify</button>
      <button class="menu-boton" id="btnUsuarios" onclick="abrirAdmin('usuarios')" style="display:none;"><span class="menu-icono">⚙️</span>Administrar</button>
    </div>
''',
        '''      <button class="menu-boton" id="btnCRM" onclick="abrirCRM()" style="display:none;"><span class="menu-icono">🤝</span>CRM de Ventas</button>
      <button class="menu-boton" id="btnShopify" onclick="abrirShopify()" style="display:none;"><span class="menu-icono">🛍️</span>Shopify</button>
      <button class="menu-boton" id="btnTurnos" onclick="abrirTurnos()" style="display:none;"><span class="menu-icono">🛎️</span>Turnos</button>
      <button class="menu-boton" id="btnUsuarios" onclick="abrirAdmin('usuarios')" style="display:none;"><span class="menu-icono">⚙️</span>Administrar</button>
    </div>
''',
    ],
    [
        '''    </div>
    <div id="crmContenido" style="max-width:1100px; margin:0 auto;"></div>
  </main>
</div>
''',
        '''    </div>
    <div id="crmContenido" style="max-width:1100px; margin:0 auto;"></div>
  </main>
</div>

<div id="turnosScreen" style="display:none;">
  <header>
    <div class="brand">
      <span class="chip-id">TI//TURNOS</span>
      <div>
        <h1>🛎️ Turnos</h1>
        <div class="subtitle">llamar el siguiente turno de tu sucursal</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="whoami" id="whoamiTurnos"></div>
      <button class="secondary" onclick="volverATableroDesdeTurnos()">← Menú principal</button>
      <button class="secondary" onclick="cerrarSesionConConfirmacion()">Salir</button>
    </div>
  </header>
  <main>
    <div id="turnosContenido" style="max-width:700px; margin:0 auto;"></div>
  </main>
</div>
''',
    ],
    [
        '''  document.getElementById('btnCRM').style.display = META.mis_permisos.acceso_crm ? 'flex' : 'none';
  document.getElementById('btnShopify').style.display = META.mis_permisos.acceso_shopify ? 'flex' : 'none';

  // El menú principal es la primera pantalla tras iniciar sesión — desde ahí
''',
        '''  document.getElementById('btnCRM').style.display = META.mis_permisos.acceso_crm ? 'flex' : 'none';
  document.getElementById('btnShopify').style.display = META.mis_permisos.acceso_shopify ? 'flex' : 'none';
  document.getElementById('btnTurnos').style.display = META.mis_permisos.acceso_turnos ? 'flex' : 'none';

  // El menú principal es la primera pantalla tras iniciar sesión — desde ahí
''',
    ],
    [
        '''  document.getElementById('whoamiCRM').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;
  await cambiarCRMTab('clientes');
}

''',
        '''  document.getElementById('whoamiCRM').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;
  await cambiarCRMTab('clientes');
}

// ---- 🛎️ Turnos por sucursal (llamar desde el mostrador) ----

let TURNOS_POLL_TIMER = null;
let TURNOS_ULTIMO_LLAMADO = null; // {id, numero} -- el último turno que ESTE usuario llamó en esta sesión

async function abrirTurnos() {
  document.getElementById('app').style.display = 'none';
  document.getElementById('menuScreen').style.display = 'none';
  document.getElementById('equiposScreen').style.display = 'none';
  document.getElementById('proyectosScreen').style.display = 'none';
  document.getElementById('marketingScreen').style.display = 'none';
  document.getElementById('reparacionesScreen').style.display = 'none';
  document.getElementById('laboratorioScreen').style.display = 'none';
  document.getElementById('entregasScreen').style.display = 'none';
  document.getElementById('checadorPrecioScreen').style.display = 'none';
  document.getElementById('dashboardScreen').style.display = 'none';
  document.getElementById('superadminScreen').style.display = 'none';
  document.getElementById('comprasScreen').style.display = 'none';
  document.getElementById('rhScreen').style.display = 'none';
  document.getElementById('crmScreen').style.display = 'none';
  document.getElementById('shopifyScreen').style.display = 'none';
  document.getElementById('turnosScreen').style.display = 'block';
  document.getElementById('whoamiTurnos').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol] || SESION.usuario.rol}`;
  TURNOS_ULTIMO_LLAMADO = null;
  await renderTurnosMostrador();
  if (TURNOS_POLL_TIMER) clearInterval(TURNOS_POLL_TIMER);
  TURNOS_POLL_TIMER = setInterval(renderTurnosMostrador, 8000);
}

function volverATableroDesdeTurnos() {
  if (TURNOS_POLL_TIMER) { clearInterval(TURNOS_POLL_TIMER); TURNOS_POLL_TIMER = null; }
  document.getElementById('turnosScreen').style.display = 'none';
  document.getElementById('menuScreen').style.display = 'block';
}

async function renderTurnosMostrador() {
  const cont = document.getElementById('turnosContenido');
  if (!cont) return;
  if (!META.mi_sucursal_id) {
    cont.innerHTML = `<p style="font-size:13px; color:var(--copper);">Tu usuario no tiene una sucursal asignada — pídele a tu administrador que te la asigne (Administrar → Usuarios) para poder llamar turnos.</p>`;
    return;
  }
  let esperando;
  try {
    esperando = await api('/api/turnos/esperando');
  } catch (e) {
    cont.innerHTML = `<p style="font-size:13px; color:var(--copper);">${escapeHtml(e.message)}</p>`;
    return;
  }
  const ventanilla = META.mi_ventanilla_turnos || SESION.usuario.nombre;
  cont.innerHTML = `
    ${!META.mi_ventanilla_turnos ? `<p style="font-size:12px; color:var(--muted); background:rgba(155,157,159,0.12); padding:8px 10px; border-radius:6px;">No tienes una ventanilla/caja fija asignada — en la pantalla se mostrará tu nombre. Pídele a tu administrador que te asigne una (ej. "Caja 1") en tu perfil si prefieres que se vea un número de caja.</p>` : ''}
    <div style="text-align:center; padding:16px 0;">
      <div style="font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:1px;">Esperando</div>
      <div style="font-size:52px; font-weight:700; line-height:1;">${esperando.length}</div>
      <div style="font-size:13px; color:var(--muted);">turno${esperando.length === 1 ? '' : 's'} en fila</div>
    </div>
    ${TURNOS_ULTIMO_LLAMADO ? `
      <div style="border:1px solid rgba(155,157,159,0.35); border-radius:8px; padding:14px; margin-bottom:16px; text-align:center;">
        <div style="font-size:12px; color:var(--muted); text-transform:uppercase;">Turno llamado</div>
        <div style="font-size:36px; font-weight:700;">#${TURNOS_ULTIMO_LLAMADO.numero}</div>
        <div style="font-size:13px; color:var(--muted); margin-bottom:10px;">→ ${escapeHtml(ventanilla)}</div>
        <div style="display:flex; gap:8px; justify-content:center;">
          <button class="primary" onclick="atenderTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})">Atender / Finalizar</button>
          <button class="secondary" onclick="cancelarTurnoUI(${TURNOS_ULTIMO_LLAMADO.id})">No se presentó</button>
        </div>
      </div>
    ` : ''}
    <button class="primary" style="width:100%; padding:16px; font-size:16px;" ${esperando.length === 0 ? 'disabled' : ''} onclick="llamarSiguienteTurnoUI(${esperando.length ? esperando[0].id : 'null'})">
      🔔 Llamar siguiente${esperando.length ? ` — Turno #${esperando[0].numero}` : ''}
    </button>
  `;
}

async function llamarSiguienteTurnoUI(turnoId) {
  if (!turnoId) return;
  try {
    const turno = await api(`/api/turnos/${turnoId}/llamar`, { method: 'POST' });
    TURNOS_ULTIMO_LLAMADO = { id: turno.id, numero: turno.numero };
    await renderTurnosMostrador();
  } catch (e) {
    alert(e.message);
    await renderTurnosMostrador();
  }
}

async function atenderTurnoUI(turnoId) {
  await api(`/api/turnos/${turnoId}/atender`, { method: 'POST' });
  TURNOS_ULTIMO_LLAMADO = null;
  await renderTurnosMostrador();
}

async function cancelarTurnoUI(turnoId) {
  if (!confirm('¿Marcar este turno como "no se presentó"?')) return;
  await api(`/api/turnos/${turnoId}/cancelar`, { method: 'POST' });
  TURNOS_ULTIMO_LLAMADO = null;
  await renderTurnosMostrador();
}

''',
    ],
    [
        '''  { clave: 'modulo_asistente_ia', etiqueta: '🐭 Asistente de IA' },
  { clave: 'modulo_shopify', etiqueta: '🛍️ Shopify' },
];

''',
        '''  { clave: 'modulo_asistente_ia', etiqueta: '🐭 Asistente de IA' },
  { clave: 'modulo_shopify', etiqueta: '🛍️ Shopify' },
  { clave: 'modulo_turnos', etiqueta: '🎫 Turnos por sucursal' },
];

''',
    ],
    [
        '''        <th>Persona</th><th>Rol</th>
        <th class="col-check">Tickets${casillaTodoColumna('acceso_tickets')}</th><th class="col-check">Reparaciones${casillaTodoColumna('acceso_reparaciones')}</th><th class="col-check">Laboratorio${casillaTodoColumna('acceso_laboratorio')}</th><th class="col-check" title="Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal">Recibir/Entregar Lab.${casillaTodoColumna('acceso_laboratorio_entrega')}</th><th class="col-check">Entregas${casillaTodoColumna('acceso_entregas')}</th><th class="col-check">Precios${casillaTodoColumna('acceso_checador_precio')}</th><th class="col-check">Equipos${casillaTodoColumna('acceso_equipos')}</th>
        <th class="col-check">Compras${casillaTodoColumna('acceso_compras')}</th><th class="col-check">RH${casillaTodoColumna('acceso_rh')}</th><th class="col-check">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class="col-check">CRM${casillaTodoColumna('acceso_crm')}</th><th class="col-check">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th>
        <th class="col-check">Dashboard${casillaTodoColumna('acceso_dashboard')}</th><th class="col-check">Admin.${casillaTodoColumna('acceso_administracion')}</th><th class="col-check">Monitoreo${casillaTodoColumna('monitoreo_activo')}</th>
      </tr></thead>
''',
        '''        <th>Persona</th><th>Rol</th>
        <th class="col-check">Tickets${casillaTodoColumna('acceso_tickets')}</th><th class="col-check">Reparaciones${casillaTodoColumna('acceso_reparaciones')}</th><th class="col-check">Laboratorio${casillaTodoColumna('acceso_laboratorio')}</th><th class="col-check" title="Puede recibir de vuelta y entregar trabajos de Laboratorio en su sucursal">Recibir/Entregar Lab.${casillaTodoColumna('acceso_laboratorio_entrega')}</th><th class="col-check">Entregas${casillaTodoColumna('acceso_entregas')}</th><th class="col-check">Precios${casillaTodoColumna('acceso_checador_precio')}</th><th class="col-check">Equipos${casillaTodoColumna('acceso_equipos')}</th>
        <th class="col-check">Compras${casillaTodoColumna('acceso_compras')}</th><th class="col-check">RH${casillaTodoColumna('acceso_rh')}</th><th class="col-check">Marketing${casillaTodoColumna('acceso_marketing')}</th><th class="col-check">CRM${casillaTodoColumna('acceso_crm')}</th><th class="col-check">🐭${casillaTodoColumna('acceso_asistente_ia')}</th><th class="col-check" title="Ver datos sensibles de empleados">Datos RH${casillaTodoColumna('acceso_datos_empleado_rh')}</th><th class="col-check">🛍️ Shopify${casillaTodoColumna('acceso_shopify')}</th><th class="col-check" title="Tomar/llamar turnos en su sucursal">🎫 Turnos${casillaTodoColumna('acceso_turnos')}</th>
        <th class="col-check">Dashboard${casillaTodoColumna('acceso_dashboard')}</th><th class="col-check">Admin.${casillaTodoColumna('acceso_administracion')}</th><th class="col-check">Monitoreo${casillaTodoColumna('monitoreo_activo')}</th>
      </tr></thead>
''',
    ],
    [
        '''            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_datos_empleado_rh', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_shopify', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>
            ${u.rol === 'admin' ? `
              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_dashboard', this)" data-campo="acceso_dashboard" /></td>
''',
        '''            <td class="col-check"><input type="checkbox" ${u.acceso_datos_empleado_rh ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_datos_empleado_rh', this)" title="Ver datos sensibles de empleados (salario, Microsip) en RH" data-campo="acceso_datos_empleado_rh" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_shopify ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_shopify', this)" title="Acceso al módulo de Shopify" data-campo="acceso_shopify" /></td>
            <td class="col-check"><input type="checkbox" ${u.acceso_turnos ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_turnos', this)" title="Tomar/llamar turnos en su sucursal" data-campo="acceso_turnos" /></td>
            ${u.rol === 'admin' ? `
              <td class="col-check"><input type="checkbox" ${u.acceso_dashboard ? 'checked' : ''} onchange="cambiarAccesoModuloUI(${u.id}, 'acceso_dashboard', this)" data-campo="acceso_dashboard" /></td>
''',
    ],
    [
        '''    </p>
    <table class="users">
      <thead><tr><th>Nombre</th><th>Prefijo</th><th>Departamento</th><th>Teléfonos</th><th>🦷 Laboratorio</th><th></th></tr></thead>
      <tbody>
        ${SUCURSALES_REPARACION_CACHE.map(s => `
''',
        '''    </p>
    <table class="users">
      <thead><tr><th>Nombre</th><th>Prefijo</th><th>Departamento</th><th>Teléfonos</th><th>🦷 Laboratorio</th><th>🛎️ Turnos</th><th></th></tr></thead>
      <tbody>
        ${SUCURSALES_REPARACION_CACHE.map(s => `
''',
    ],
    [
        '''              ? '<span class="badge baja">✅ Es el laboratorio</span>'
              : `<button class="secondary" style="padding:5px 10px; font-size:11px;" onclick="marcarSucursalLaboratorioUI(${s.id})">Marcar</button>`}</td>
            <td style="display:flex; gap:6px;">
              <button class="secondary" style="padding:5px 10px; font-size:11px;" onclick="abrirEditarSucursal(${s.id})">Editar</button>
''',
        '''              ? '<span class="badge baja">✅ Es el laboratorio</span>'
              : `<button class="secondary" style="padding:5px 10px; font-size:11px;" onclick="marcarSucursalLaboratorioUI(${s.id})">Marcar</button>`}</td>
            <td><button class="secondary" style="padding:5px 10px; font-size:11px;" onclick="abrirConfigTurnosSucursal(${s.id})">Configurar</button></td>
            <td style="display:flex; gap:6px;">
              <button class="secondary" style="padding:5px 10px; font-size:11px;" onclick="abrirEditarSucursal(${s.id})">Editar</button>
''',
    ],
    [
        '''            </td>
          </tr>
        `).join('') || '<tr><td colspan="6" class="empty-col">— sin sucursales —</td></tr>'}
      </tbody>
    </table>
''',
        '''            </td>
          </tr>
        `).join('') || '<tr><td colspan="7" class="empty-col">— sin sucursales —</td></tr>'}
      </tbody>
    </table>
''',
    ],
    [
        '''  await renderAdmin();
  mostrarExito('Sucursal marcada como Laboratorio');
}

''',
        '''  await renderAdmin();
  mostrarExito('Sucursal marcada como Laboratorio');
}

// ---- 🛎️ Turnos: ligas de Pantalla/Kiosko + video(s) por sucursal ----

function abrirConfigTurnosSucursal(id) {
  const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);
  if (!s) return;
  let videos = [];
  try { videos = s.turnos_videos ? JSON.parse(s.turnos_videos) : []; } catch (e) { videos = []; }
  document.getElementById('modalContent').innerHTML = `
    <button class="close-btn" onclick="cerrarModal()">cerrar</button>
    <h2>🛎️ Turnos — ${escapeHtml(s.nombre)}</h2>
    <p style="font-size:12px; color:var(--muted);">
      Genera las dos ligas de esta sucursal: la <b>Pantalla</b> (se deja abierta en la smart TV de la sala de espera, con el video en loop y el número llamado) y el <b>Kiosko</b> (se deja abierto en la tablet/PC de entrada para que el cliente tome su turno). Ninguna de las dos pide iniciar sesión.
    </p>
    <div id="turnosLigasBox">${s.codigo_turnos ? _htmlLigasTurnos(id, s.codigo_turnos) : `<button class="primary" style="width:100%;" onclick="generarLigasTurnosUI(${id})">Generar ligas</button>`}</div>
    <div class="field" style="margin-top:16px;"><label>Video(s) para la pantalla (un link por línea — YouTube, Drive, Vimeo o OneDrive, usa el link de "Insertar/Embed")</label>
      <textarea id="ct_videos" rows="4" placeholder="https://…">${videos.map(v => escapeHtml(v)).join('\\n')}</textarea>
    </div>
    <button class="primary" style="width:100%;" onclick="guardarVideosTurnosUI(${id}, this)">Guardar video(s)</button>
    <div id="turnosConfigError" class="error-msg"></div>
  `;
  abrirModal();
}

function _htmlLigasTurnos(id, codigo) {
  const base = window.location.origin;
  const urlPantalla = `${base}/pantalla-turnos/${codigo}`;
  const urlKiosko = `${base}/kiosko-turnos/${codigo}`;
  return `
    <div class="field"><label>Liga de la Pantalla</label><input readonly value="${escapeHtml(urlPantalla)}" onclick="this.select(); document.execCommand('copy');" /></div>
    <div class="field"><label>Liga del Kiosko (tomar turno)</label><input readonly value="${escapeHtml(urlKiosko)}" onclick="this.select(); document.execCommand('copy');" /></div>
    <p style="font-size:11px; color:var(--muted);">Dale clic a cualquiera para copiarla. Si alguna se compartió sin querer, <a href="#" onclick="regenerarLigasTurnosUI(${id}); return false;">genera unas nuevas</a> (las viejas dejan de servir).</p>
  `;
}

async function generarLigasTurnosUI(id) {
  const r = await api(`/api/reparaciones/sucursales/${id}/turnos/codigo`, { method: 'POST' });
  const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);
  if (s) s.codigo_turnos = r.codigo;
  document.getElementById('turnosLigasBox').innerHTML = _htmlLigasTurnos(id, r.codigo);
}

async function regenerarLigasTurnosUI(id) {
  if (!confirm('¿Generar ligas nuevas? Las que ya estén pegadas en la pantalla/kiosko de esa sucursal dejarán de funcionar.')) return;
  const r = await api(`/api/reparaciones/sucursales/${id}/turnos/codigo/regenerar`, { method: 'POST' });
  const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);
  if (s) s.codigo_turnos = r.codigo;
  document.getElementById('turnosLigasBox').innerHTML = _htmlLigasTurnos(id, r.codigo);
  mostrarExito('Ligas regeneradas');
}

async function guardarVideosTurnosUI(id, boton) {
  const videos = document.getElementById('ct_videos').value.split('\\n').map(v => v.trim()).filter(Boolean);
  await conBloqueoDeBoton(boton, async () => {
    try {
      await api(`/api/reparaciones/sucursales/${id}/turnos/videos`, { method: 'PUT', body: JSON.stringify({ videos }) });
      const s = SUCURSALES_REPARACION_CACHE.find(x => x.id === id);
      if (s) s.turnos_videos = JSON.stringify(videos);
      mostrarExito('Video(s) guardado(s)');
    } catch (e) {
      document.getElementById('turnosConfigError').textContent = e.message;
    }
  });
}

''',
    ],
    [
        '''          <input type="checkbox" id="e_acceso_shopify" ${u.acceso_shopify ? 'checked' : ''} /> Acceso al módulo de 🛍️ Shopify
        </label>
      </div>

      <div id="e_permisos_solo_admin" style="display:${u.rol==='admin' ? 'block' : 'none'};">
''',
        '''          <input type="checkbox" id="e_acceso_shopify" ${u.acceso_shopify ? 'checked' : ''} /> Acceso al módulo de 🛍️ Shopify
        </label>
        <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
          <input type="checkbox" id="e_acceso_turnos" ${u.acceso_turnos ? 'checked' : ''} /> Acceso al módulo de 🎫 Turnos (tomar/llamar turnos)
        </label>
      </div>
      <div class="field"><label>Ventanilla/Caja fija para Turnos (opcional)</label><input id="e_ventanilla_turnos" value="${u.ventanilla_turnos ? escapeHtml(u.ventanilla_turnos) : ''}" placeholder="ej. Caja 1, Ventanilla 3" /></div>
      <p style="font-size:11px; color:var(--muted); margin:-6px 0 10px;">Al llamar un turno, se muestra este nombre en la pantalla de sala de espera — necesita también tener asignada su sucursal.</p>

      <div id="e_permisos_solo_admin" style="display:${u.rol==='admin' ? 'block' : 'none'};">
''',
    ],
    [
        '''    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;
    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;
  }
  if (rol === 'admin') {
''',
        '''    payload.acceso_datos_empleado_rh = document.getElementById('e_acceso_datos_empleado_rh').checked;
    payload.acceso_shopify = document.getElementById('e_acceso_shopify').checked;
    payload.acceso_turnos = document.getElementById('e_acceso_turnos').checked;
    payload.ventanilla_turnos = document.getElementById('e_ventanilla_turnos').value.trim() || null;
  }
  if (rol === 'admin') {
''',
    ],
]


# ---------------------------------------------------------------------
# Páginas nuevas (públicas, sin login) -- se escriben tal cual, no se
# parchan porque no existen todavía en el repo del usuario.
# ---------------------------------------------------------------------
ARCHIVOS_NUEVOS = {}
ARCHIVOS_NUEVOS['frontend/pantalla_turnos.html'] = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0" />
<title>Turnos — Pantalla</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; height:100%; background:#0B0C0D; color:#EDEDED; font-family:'IBM Plex Sans','Segoe UI',sans-serif; overflow:hidden; }
  #layout { display:none; flex-direction:column; height:100vh; }
  #videoWrap { flex:1; position:relative; background:#000; }
  #videoWrap iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; }
  .sinVideo { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#6F7173; font-size:18px; }
  #panelInferior { flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:24px; padding:18px 32px; background:#141516; border-top:2px solid #D8192F; flex-wrap:wrap; }
  #sucursalNombre { font-size:16px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.05em; }
  #turnoActualBox { text-align:center; }
  #turnoActualLabel { font-size:13px; color:#9B9D9F; text-transform:uppercase; letter-spacing:0.08em; }
  #turnoActualNumero { font-size:88px; font-weight:800; line-height:1; color:#fff; }
  #turnoActualVentanilla { font-size:26px; color:#D8192F; font-weight:700; margin-top:2px; }
  #historial { display:flex; gap:20px; }
  #historial .item { text-align:center; opacity:0.55; }
  #historial .item .n { font-size:20px; font-weight:700; }
  #historial .item .v { font-size:11px; color:#9B9D9F; }
  #esperandoBox { font-size:14px; color:#9B9D9F; white-space:nowrap; }
  #mensajeError { display:none; position:fixed; inset:0; align-items:center; justify-content:center; font-size:16px; color:#9B9D9F; text-align:center; padding:20px; }
</style>
</head>
<body>

<div id="mensajeError"></div>
<div id="layout">
  <div id="videoWrap">
    <div class="sinVideo" id="sinVideoMsg" style="display:none;">Sin video configurado</div>
  </div>
  <div id="panelInferior">
    <div id="sucursalNombre"></div>
    <div id="turnoActualBox">
      <div id="turnoActualLabel">Turno</div>
      <div id="turnoActualNumero">—</div>
      <div id="turnoActualVentanilla"></div>
    </div>
    <div id="historial"></div>
    <div id="esperandoBox"></div>
  </div>
</div>

<script>
  // Página PÚBLICA (sin login) -- se deja abierta en la smart TV/PC de la
  // sala de espera. El código de la sucursal se lee de la URL y solo sirve
  // para pedir /api/turnos/pantalla/{codigo}; esta página no guarda nada.
  const codigo = window.location.pathname.split('/').filter(Boolean).pop();
  let videos = [];
  let videoIdx = 0;
  let videoTimer = null;
  let ultimoNumeroVisto = null;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function beep() {
    // Dos tonos cortos tipo "ding-dong" -- sintetizados con Web Audio, no
    // necesita ningún archivo de sonido. Si el navegador bloquea audio sin
    // interacción previa del usuario, simplemente no suena (no rompe nada).
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const tono = (freq, inicio) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination);
        o.type = 'sine'; o.frequency.value = freq;
        g.gain.setValueAtTime(0.0001, ctx.currentTime + inicio);
        g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + inicio + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + inicio + 0.5);
        o.start(ctx.currentTime + inicio);
        o.stop(ctx.currentTime + inicio + 0.55);
      };
      tono(880, 0);
      tono(1108, 0.26);
    } catch (e) { /* sin audio disponible -- no pasa nada */ }
  }

  function mostrarVideoActual() {
    const wrap = document.getElementById('videoWrap');
    const msg = document.getElementById('sinVideoMsg');
    wrap.querySelectorAll('iframe').forEach(f => f.remove());
    if (!videos.length) {
      msg.style.display = 'flex';
      return;
    }
    msg.style.display = 'none';
    const iframe = document.createElement('iframe');
    iframe.src = videos[videoIdx % videos.length];
    iframe.allow = 'autoplay; fullscreen';
    iframe.setAttribute('allowfullscreen', '');
    wrap.appendChild(iframe);
  }

  function rotarVideo() {
    videoIdx++;
    mostrarVideoActual();
  }

  async function actualizar() {
    let datos;
    try {
      const resp = await fetch(`/api/turnos/pantalla/${codigo}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Esta pantalla no es válida.');
      }
      datos = await resp.json();
    } catch (e) {
      document.getElementById('mensajeError').style.display = 'flex';
      document.getElementById('mensajeError').textContent = e.message || 'Esta pantalla no es válida.';
      document.getElementById('layout').style.display = 'none';
      return;
    }
    document.getElementById('mensajeError').style.display = 'none';
    document.getElementById('layout').style.display = 'flex';
    document.getElementById('sucursalNombre').textContent = datos.sucursal_nombre || '';
    document.getElementById('esperandoBox').textContent = `${datos.esperando || 0} esperando`;

    const nuevosVideos = datos.videos || [];
    if (JSON.stringify(nuevosVideos) !== JSON.stringify(videos)) {
      videos = nuevosVideos;
      videoIdx = 0;
      if (videoTimer) clearInterval(videoTimer);
      mostrarVideoActual();
      if (videos.length > 1) videoTimer = setInterval(rotarVideo, 3 * 60 * 1000);
    }

    const llamados = datos.llamados || [];
    const actual = llamados[0];
    if (actual) {
      document.getElementById('turnoActualNumero').textContent = `#${actual.numero}`;
      document.getElementById('turnoActualVentanilla').textContent = actual.ventanilla ? `→ ${actual.ventanilla}` : '';
      if (ultimoNumeroVisto !== null && actual.numero !== ultimoNumeroVisto) {
        beep();
      }
      ultimoNumeroVisto = actual.numero;
    } else {
      document.getElementById('turnoActualNumero').textContent = '—';
      document.getElementById('turnoActualVentanilla').textContent = '';
    }

    document.getElementById('historial').innerHTML = llamados.slice(1, 5).map(t => `
      <div class="item"><div class="n">#${t.numero}</div><div class="v">${escapeHtml(t.ventanilla || '')}</div></div>
    `).join('');
  }

  actualizar();
  setInterval(actualizar, 5000);
</script>
</body>
</html>
'''
ARCHIVOS_NUEVOS['frontend/kiosko_turnos.html'] = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<title>Tomar turno</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; height:100%; background:#0B0C0D; color:#EDEDED; font-family:'IBM Plex Sans','Segoe UI',sans-serif; }
  body { display:flex; align-items:center; justify-content:center; text-align:center; padding:24px; }
  #caja { max-width:420px; width:100%; }
  h1 { font-size:24px; margin:0 0 6px; }
  .sub { font-size:14px; color:#9B9D9F; margin-bottom:32px; }
  #btnTomar { width:100%; padding:28px; font-size:22px; font-weight:700; border-radius:14px; border:none; background:#D8192F; color:#fff; cursor:pointer; }
  #btnTomar:active { transform: scale(0.98); }
  #btnTomar:disabled { opacity:0.5; }
  #resultado { display:none; }
  #resultado .numero { font-size:96px; font-weight:800; margin:16px 0; }
  #resultado .nota { font-size:14px; color:#9B9D9F; margin-bottom:28px; }
  #btnOtro { padding:14px 24px; font-size:14px; border-radius:10px; border:1px solid rgba(155,157,159,0.35); background:transparent; color:#EDEDED; cursor:pointer; }
  #mensajeError { font-size:13px; color:#FF6B7A; min-height:18px; margin-top:14px; }
</style>
</head>
<body>

<div id="caja">
  <div id="pantallaInicial">
    <h1>🎫 Tomar turno</h1>
    <div class="sub">Presiona el botón para sacar tu turno</div>
    <button id="btnTomar" onclick="tomarTurno()">Tomar turno</button>
    <div id="mensajeError"></div>
  </div>
  <div id="resultado">
    <div class="sub">Tu turno es</div>
    <div class="numero" id="numeroTurno">—</div>
    <div class="nota">Espera a que te llamemos en la pantalla</div>
    <button id="btnOtro" onclick="volverAInicio()">Tomar otro turno</button>
  </div>
</div>

<script>
  // Página PÚBLICA (sin login) -- se deja abierta en la tablet/PC de
  // entrada de la sucursal. El código se lee de la URL y solo sirve para
  // pedir /api/turnos/kiosko/{codigo}/tomar; no guarda nada del cliente.
  const codigo = window.location.pathname.split('/').filter(Boolean).pop();

  async function tomarTurno() {
    const boton = document.getElementById('btnTomar');
    boton.disabled = true;
    document.getElementById('mensajeError').textContent = '';
    try {
      const resp = await fetch(`/api/turnos/kiosko/${codigo}/tomar`, { method: 'POST' });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'No se pudo tomar el turno.');
      }
      const datos = await resp.json();
      document.getElementById('numeroTurno').textContent = `#${datos.numero}`;
      document.getElementById('pantallaInicial').style.display = 'none';
      document.getElementById('resultado').style.display = 'block';
    } catch (e) {
      document.getElementById('mensajeError').textContent = e.message || 'Este kiosko no es válido.';
    } finally {
      boton.disabled = false;
    }
  }

  function volverAInicio() {
    document.getElementById('resultado').style.display = 'none';
    document.getElementById('pantallaInicial').style.display = 'block';
  }
</script>
</body>
</html>
'''


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False
    archivos_nuevos_creados = []

    for ruta, contenido_nuevo in ARCHIVOS_NUEVOS.items():
        if os.path.exists(ruta):
            print(f"[{ruta}] ya existe -- no se toca (puede que ya lo hayas aplicado antes).")
            continue
        os.makedirs(os.path.dirname(ruta) or '.', exist_ok=True)
        escribir(ruta, contenido_nuevo)
        archivos_nuevos_creados.append(ruta)
        print(f"[{ruta}] creado.")

    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print(f"[{ruta}] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys()) + archivos_nuevos_creados
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Turnos por sucursal: pantalla + kiosko + mostrador (modulo nuevo, como banco)"')
    print("   git push")


if __name__ == "__main__":
    main()
