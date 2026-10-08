# -*- coding: utf-8 -*-
"""
Departamento de Logistica: ver TODAS las reparaciones + entregar al chofer
============================================================================

Pedido de David (en 2 partes, este script hace las 2):

1. Los "encargados" (rol encargado_sucursal) y "empleados" (rol usuario) del
   departamento de Logistica deben poder ver TODAS las reparaciones de la
   empresa, no solo las de su propia sucursal / las que ellos mismos
   crearon -- para esto, solo verlas (sin editar, cambiar estado, firmar ni
   eliminar).
2. Ese mismo departamento (cualquier persona, sin importar su rol dentro de
   Logistica) debe poder hacer el paso de "entregar al chofer" (firma-chofer)
   -- hoy es exclusivo del administrador. Es el paso donde, ya que el
   tecnico terminó de reparar el equipo, alguien de Logística se lo entrega
   al chofer para que lo lleve de vuelta a la sucursal.

Causa de fondo: GET /api/reparaciones (y el detalle GET /api/reparaciones/{id})
filtran:
- rol "usuario": solo ve las reparaciones que el mismo dio de alta (creado_por_id).
- rol "almacen" / "encargado_sucursal": solo ve las de su propia sucursal.
Y POST /api/reparaciones/{id}/firma-chofer solo dejaba pasar al rol "admin".

El departamento del usuario se hereda de su sucursal asignada
(users.sucursal_id -> sucursales_reparacion.departamento, via
db.obtener_departamento_usuario, que ya existia).

Que agrega este parche (SOLO backend/app.py, no toca db.py ni el frontend):

1. Import nuevo: `unicodedata` (para comparar el nombre del departamento sin
   importar mayusculas/acentos -- "Logistica", "logística", etc. todas
   cuentan igual).
2. Funcion nueva `_es_departamento_logistica(usuario_id)`.
3. `GET /api/reparaciones`: si el departamento del usuario es Logistica Y su
   rol es "usuario" o "encargado_sucursal", ya NO se filtra por
   creado_por_id ni por sucursal_id -- ve todas.
4. `GET /api/reparaciones/{id}`: mismo criterio para el detalle de una sola
   reparacion.
5. `POST /api/reparaciones/{id}/firma-chofer`: ya no es exclusivo de admin --
   cualquier persona del departamento de Logistica (sin importar su rol
   dentro del departamento) también puede registrar la entrega al chofer.

Que NO cambia:
- El rol "almacen" NO entra en el punto 3/4 -- sigue viendo solo su propia
  sucursal, es una restriccion de seguridad aparte (recepcion de equipos),
  no relacionada con este pedido.
- El resto de endpoints de accion (PATCH /api/reparaciones/{id}, DELETE,
  /estado, /firma-salida, /firma-ingreso, /entregar, /items-costo,
  /evidencias, /actualizaciones) siguen exactamente igual -- Logistica solo
  gana la vista completa (punto 3/4) y el paso de firma-chofer (punto 5),
  nada mas.

Uso:
    cd a la raiz de tu repo (donde esta la carpeta backend/) y correr:
        python3 fix_reparaciones_logistica_ve_todo.py
    (si "python3" no existe en tu terminal, prueba "py -3" en vez de "python3" --
    "python" a secas puede apuntar a una version vieja que no entiende este script)
    Es seguro correrlo mas de una vez (no duplica el cambio si ya esta aplicado).
"""

import pathlib
import sys

RUTA_APP = None
for candidato in ("backend/app.py", "app.py"):
    p = pathlib.Path(candidato)
    if p.is_file():
        RUTA_APP = p
        break

if RUTA_APP is None:
    print("No encontre backend/app.py ni app.py en esta carpeta.")
    print("Corre este script desde la raiz de tu repo de tickets-ti.")
    sys.exit(1)

texto = RUTA_APP.read_text(encoding="utf-8")
original = texto
cambios_aplicados = []

MARCADOR = "_es_departamento_logistica"

# ---- Hunk 1: import unicodedata ----
if "import unicodedata" not in texto:
    viejo = (
        "import base64\n"
        "import json\n"
        "import os\n"
        "import re\n"
        "import secrets\n"
        "import sys\n"
        "import urllib.parse\n"
    )
    nuevo = (
        "import base64\n"
        "import json\n"
        "import os\n"
        "import re\n"
        "import secrets\n"
        "import sys\n"
        "import unicodedata\n"
        "import urllib.parse\n"
    )
    n = texto.count(viejo)
    if n != 1:
        print("[ABORTADO] Hunk 1 (import unicodedata): esperaba encontrar el bloque de imports "
              "exactamente 1 vez, encontre %d. El archivo parece distinto al esperado -- avisa "
              "a Claude antes de continuar (pegale el error completo), no se modifico nada." % n)
        sys.exit(1)
    texto = texto.replace(viejo, nuevo, 1)
    cambios_aplicados.append("import unicodedata")
else:
    print("(ya tenia 'import unicodedata' -- se deja igual)")

# ---- Hunk 2: funcion _es_departamento_logistica + deja requiere_ver_reparaciones igual ----
if MARCADOR not in texto:
    viejo = (
        'def requiere_ver_reparaciones(usuario: dict = Depends(requiere_empresa_o_almacen)) -> dict:\n'
        '    """Igual que requiere_ver_tickets, pero para Reparaciones. El rol \'almacen\'\n'
        '    siempre tiene acceso — es su único módulo, no se le puede quitar — los\n'
        '    demás roles sí pueden perder este acceso desde Administrar → Accesos."""\n'
    )
    nuevo = (
        'def _es_departamento_logistica(usuario_id: int) -> bool:\n'
        '    """True si el departamento del usuario (heredado de su sucursal, ver\n'
        '    db.obtener_departamento_usuario) es "Logística" -- sin importar mayúsculas\n'
        '    ni acentos. Se usa SOLO para ampliar qué reparaciones puede VER un usuario\n'
        '    con rol "usuario"/"encargado_sucursal" (que por default solo ven lo suyo);\n'
        '    ningún endpoint de acción (editar, cambiar estado, firmar, entregar,\n'
        '    eliminar) llama a esta función, así que ese departamento sigue sin poder\n'
        '    hacer nada de eso -- únicamente consultar."""\n'
        '    depto = db.obtener_departamento_usuario(usuario_id) or ""\n'
        '    depto_normalizado = unicodedata.normalize("NFKD", depto).encode("ascii", "ignore").decode().strip().lower()\n'
        '    return depto_normalizado == "logistica"\n'
        '\n'
        '\n'
        'def requiere_ver_reparaciones(usuario: dict = Depends(requiere_empresa_o_almacen)) -> dict:\n'
        '    """Igual que requiere_ver_tickets, pero para Reparaciones. El rol \'almacen\'\n'
        '    siempre tiene acceso — es su único módulo, no se le puede quitar — los\n'
        '    demás roles sí pueden perder este acceso desde Administrar → Accesos."""\n'
    )
    n = texto.count(viejo)
    if n != 1:
        print("[ABORTADO] Hunk 2 (funcion _es_departamento_logistica): esperaba encontrar "
              "requiere_ver_reparaciones exactamente 1 vez, encontre %d. Avisa a Claude "
              "(pegale el error completo), no se modifico nada." % n)
        sys.exit(1)
    texto = texto.replace(viejo, nuevo, 1)
    cambios_aplicados.append("funcion _es_departamento_logistica")
else:
    print("(ya tenia '%s' -- se deja igual)" % MARCADOR)

# ---- Hunk 3: GET /api/reparaciones ----
viejo_listar = (
    '@app.get("/api/reparaciones")\n'
    'def api_listar_reparaciones(estado: Optional[str] = None, sucursal_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_reparaciones)):\n'
    '    creado_por_id = usuario["id"] if usuario["rol"] == "usuario" else None\n'
    '    if usuario["rol"] in ("almacen", "encargado_sucursal"):\n'
    '        # Un encargado de almacén o de sucursal solo ve reparaciones de SU propia\n'
    '        # sucursal, sin importar qué sucursal_id le manden en la consulta (esto es\n'
    '        # seguridad, no solo filtro).\n'
    '        sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n'
    '    return db.listar_reparaciones(usuario["empresa_id"], estado, sucursal_id, creado_por_id)\n'
)
if viejo_listar in texto:
    nuevo_listar = (
        '@app.get("/api/reparaciones")\n'
        'def api_listar_reparaciones(estado: Optional[str] = None, sucursal_id: Optional[int] = None, usuario: dict = Depends(requiere_ver_reparaciones)):\n'
        '    creado_por_id = usuario["id"] if usuario["rol"] == "usuario" else None\n'
        '    # El departamento de Logística ve TODAS las reparaciones (solo consulta), sea\n'
        '    # "encargado" (encargado_sucursal) o "empleado" (usuario) -- las acciones (editar,\n'
        '    # firmar, entregar, eliminar) siguen bloqueadas igual que siempre, esos endpoints\n'
        '    # no llaman a esta función. El rol "almacen" NO se incluye a propósito: su\n'
        '    # restricción a la sucursal propia es de seguridad, no de filtro.\n'
        '    ve_todo_por_logistica = usuario["rol"] in ("usuario", "encargado_sucursal") and _es_departamento_logistica(usuario["id"])\n'
        '    if ve_todo_por_logistica:\n'
        '        creado_por_id = None\n'
        '    if usuario["rol"] in ("almacen", "encargado_sucursal") and not ve_todo_por_logistica:\n'
        '        # Un encargado de almacén o de sucursal solo ve reparaciones de SU propia\n'
        '        # sucursal, sin importar qué sucursal_id le manden en la consulta (esto es\n'
        '        # seguridad, no solo filtro).\n'
        '        sucursal_id = db.obtener_sucursal_id_usuario(usuario["id"])\n'
        '    return db.listar_reparaciones(usuario["empresa_id"], estado, sucursal_id, creado_por_id)\n'
    )
    n = texto.count(viejo_listar)
    if n != 1:
        print("[ABORTADO] Hunk 3 (GET /api/reparaciones): encontre %d coincidencias, esperaba 1. "
              "Avisa a Claude (pegale el error completo), no se modifico nada." % n)
        sys.exit(1)
    texto = texto.replace(viejo_listar, nuevo_listar, 1)
    cambios_aplicados.append("GET /api/reparaciones")
elif "ve_todo_por_logistica = usuario[\"rol\"] in (\"usuario\", \"encargado_sucursal\")" in texto:
    print("(GET /api/reparaciones ya tenia el cambio -- se deja igual)")
else:
    print("[ABORTADO] Hunk 3 (GET /api/reparaciones): no encontre el texto esperado ni la version "
          "ya parchada. Avisa a Claude (pegale el error completo), no se modifico nada.")
    sys.exit(1)

# ---- Hunk 4: GET /api/reparaciones/{reparacion_id} (detalle) ----
viejo_detalle = (
    '    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)\n'
    '    if not reparacion:\n'
    '        raise HTTPException(status_code=404, detail="Reparación no encontrada")\n'
    '    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"]:\n'
    '        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")\n'
    '    if usuario["rol"] in ("almacen", "encargado_sucursal") and reparacion["sucursal_id"] != db.obtener_sucursal_id_usuario(usuario["id"]):\n'
    '        raise HTTPException(status_code=403, detail="Esta reparación no es de tu sucursal")\n'
    '    return reparacion\n'
)
if viejo_detalle in texto:
    nuevo_detalle = (
        '    reparacion = db.obtener_reparacion(usuario["empresa_id"], reparacion_id)\n'
        '    if not reparacion:\n'
        '        raise HTTPException(status_code=404, detail="Reparación no encontrada")\n'
        '    ve_todo_por_logistica = usuario["rol"] in ("usuario", "encargado_sucursal") and _es_departamento_logistica(usuario["id"])\n'
        '    if usuario["rol"] == "usuario" and reparacion["creado_por_id"] != usuario["id"] and not ve_todo_por_logistica:\n'
        '        raise HTTPException(status_code=403, detail="No puedes ver esta reparación")\n'
        '    if (usuario["rol"] in ("almacen", "encargado_sucursal")\n'
        '            and reparacion["sucursal_id"] != db.obtener_sucursal_id_usuario(usuario["id"])\n'
        '            and not ve_todo_por_logistica):\n'
        '        raise HTTPException(status_code=403, detail="Esta reparación no es de tu sucursal")\n'
        '    return reparacion\n'
    )
    n = texto.count(viejo_detalle)
    if n != 1:
        print("[ABORTADO] Hunk 4 (detalle reparacion): encontre %d coincidencias, esperaba 1. "
              "Avisa a Claude (pegale el error completo), no se modifico nada." % n)
        sys.exit(1)
    texto = texto.replace(viejo_detalle, nuevo_detalle, 1)
    cambios_aplicados.append("GET /api/reparaciones/{id} (detalle)")
elif "and not ve_todo_por_logistica):" in texto:
    print("(detalle de reparacion ya tenia el cambio -- se deja igual)")
else:
    print("[ABORTADO] Hunk 4 (detalle reparacion): no encontre el texto esperado ni la version ya "
          "parchada. Avisa a Claude (pegale el error completo), no se modifico nada.")
    sys.exit(1)

# ---- Hunk 5: POST /api/reparaciones/{id}/firma-chofer ----
viejo_chofer = (
    '@app.post("/api/reparaciones/{reparacion_id}/firma-chofer")\n'
    'def api_firmar_chofer_reparacion(reparacion_id: int, payload: FirmaChoferReparacion, usuario: dict = Depends(requiere_staff)):\n'
    '    """El chofer que se lleva el equipo firma de recibido — avanza el estado a\n'
    '    \'en_traslado\'. Solo aplica justo después de la firma de salida.\n'
    '    Exclusivo del administrador: el técnico ya queda bloqueado en cuanto firma la\n'
    '    salida (justo lo que hace posible este paso), así que nunca llega a hacerlo él."""\n'
    '    if usuario["rol"] != "admin":\n'
    '        raise HTTPException(status_code=403, detail="Solo el administrador puede registrar la entrega al chofer")\n'
)
if viejo_chofer in texto:
    nuevo_chofer = (
        '@app.post("/api/reparaciones/{reparacion_id}/firma-chofer")\n'
        'def api_firmar_chofer_reparacion(reparacion_id: int, payload: FirmaChoferReparacion, usuario: dict = Depends(requiere_ver_reparaciones)):\n'
        '    """El chofer que se lleva el equipo firma de recibido — avanza el estado a\n'
        '    \'en_traslado\'. Solo aplica justo después de la firma de salida. Lo puede\n'
        '    hacer el administrador, o cualquier persona del departamento de Logística\n'
        '    (sin importar su rol dentro del departamento) -- el resto queda bloqueado,\n'
        '    incluido el técnico (que además ya queda bloqueado en cuanto firma la\n'
        '    salida, justo lo que hace posible este paso)."""\n'
        '    if usuario["rol"] != "admin" and not _es_departamento_logistica(usuario["id"]):\n'
        '        raise HTTPException(status_code=403, detail="Solo el administrador o alguien del departamento de Logística puede registrar la entrega al chofer")\n'
    )
    n = texto.count(viejo_chofer)
    if n != 1:
        print("[ABORTADO] Hunk 5 (firma-chofer): encontre %d coincidencias, esperaba 1. "
              "Avisa a Claude (pegale el error completo), no se modifico nada." % n)
        sys.exit(1)
    texto = texto.replace(viejo_chofer, nuevo_chofer, 1)
    cambios_aplicados.append("POST /api/reparaciones/{id}/firma-chofer (Logística puede entregar al chofer)")
elif 'Solo el administrador o alguien del departamento de Logística puede registrar la entrega al chofer' in texto:
    print("(firma-chofer ya tenia el cambio -- se deja igual)")
else:
    print("[ABORTADO] Hunk 5 (firma-chofer): no encontre el texto esperado ni la version ya "
          "parchada. Avisa a Claude (pegale el error completo), no se modifico nada.")
    sys.exit(1)

if texto == original:
    print("\nNada que aplicar -- el archivo ya tenia todos estos cambios.")
    sys.exit(0)

RUTA_APP.write_text(texto, encoding="utf-8")
print("\nListo. Cambios aplicados en %s:" % RUTA_APP)
for c in cambios_aplicados:
    print("  - %s" % c)
print("\nAhora sube el cambio a GitHub:")
print("  git add " + str(RUTA_APP).replace("\\", "/"))
print('  git commit -m "Departamento de Logistica ve todas las reparaciones y puede entregar al chofer"')
print("  git push")
