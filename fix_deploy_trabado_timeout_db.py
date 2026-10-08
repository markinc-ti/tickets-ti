# -*- coding: utf-8 -*-
"""
Arregla un deploy que se queda "trabado" en Render sin avanzar y sin
ningun mensaje de error.

Que estaba pasando: la app se conecta a la base de datos (Neon) sin
ningun limite de tiempo. Si en el momento del arranque la base de
datos tarda en responder (por ejemplo porque estaba "dormida" y
Neon tarda en despertarla, o hay un problema de red pasajero), o si
alguna tabla queda bloqueada por otra conexion (una instancia
anterior que no cerro bien, una sesion abierta en el editor SQL de
Neon, etc.), la app se queda esperando PARA SIEMPRE sin decir nada
-- y el deploy en Render se ve trabado en "Deploying..." sin subir
ningun log nuevo, sin importar cuanto tiempo pase ni cuantas veces lo
canceles y lo vuelvas a correr.

Que se arregla:
  1. Conectarse a la base de datos ahora tiene un limite de 20
     segundos -- si no responde a tiempo, la app lo dice claramente
     en el log en vez de quedarse esperando para siempre.
  2. Las tablas que se revisan/crean al arrancar la app (la
     "migracion") ahora tienen un limite de 20 segundos para
     conseguir el candado que necesitan -- si algo mas tiene una
     tabla bloqueada, se ve el error exacto en el log en vez de que
     el deploy se quede trabado sin explicacion.

Esto NO cambia como se comporta la app cuando todo esta bien -- nomas
hace que, si algo sale mal, se entere rapido y con un mensaje claro
en vez de quedarse colgada.

Que toca:
  - backend/db.py -- la conexion a la base de datos y el arranque de
    las tablas.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_deploy_trabado_timeout_db.py

IMPORTANTE: si tienes ahorita un deploy trabado en Render, cancelalo
primero (boton "Cancel" arriba a la derecha del deploy), aplica este
script, haz commit y push, y espera el deploy nuevo -- con este
cambio, si algo sigue mal con la conexion a la base de datos, el log
te va a decir exactamente que fallo en vez de quedarse en silencio.
"""
import sys

ARCHIVOS = {}

ARCHIVOS["backend/db.py"] = [
    [
        "    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)",
        "    # connect_timeout: si la base de datos no responde (por ejemplo si Neon\n    # está despertando de estar suspendida y tarda de más, o hay un\n    # problema de red), esto falla con un error claro en unos segundos en\n    # vez de dejar la conexión colgada indefinidamente -- eso era lo que\n    # podía trabar TODO el arranque de la app (y el deploy en Render) sin\n    # ningún mensaje de error en el log.\n    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=20)",
    ],
    [
        "def init_db():\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"\"\"\n        CREATE TABLE IF NOT EXISTS empresas (",
        "def init_db():\n    conn = get_connection()\n    cur = conn.cursor()\n    # Si alguna otra conexión (una instancia anterior que no terminó de\n    # cerrar, una sesión abierta en el editor SQL de Neon, etc.) tiene una\n    # de estas tablas bloqueada, esto hace que la migración falle con un\n    # error claro después de 20 segundos en vez de colgarse para siempre\n    # -- eso era lo que podía dejar un deploy \"trabado\" sin avanzar y sin\n    # ningún mensaje en el log.\n    cur.execute(\"SET lock_timeout = '20s'\")\n    cur.execute(\"\"\"\n        CREATE TABLE IF NOT EXISTS empresas (",
    ],
]



def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
        return False
    cambios = 0
    hubo_error = False
    for viejo, nuevo in ARCHIVOS[ruta]:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        elif nuevo in contenido:
            cambios += 1  # ya aplicado antes
        else:
            print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
            hubo_error = True
    escribir(ruta, contenido)
    print("[" + ruta + "] " + str(cambios) + "/" + str(len(ARCHIVOS[ruta])) + " cambio(s) aplicado(s).")
    return not hubo_error


def main():
    ok = True
    for ruta in ARCHIVOS:
        ok = aplicar_reemplazos(ruta) and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "DB: limite de tiempo al conectar y al arrancar, para que un deploy no se quede trabado sin avisar"')
    print("   git push")


if __name__ == "__main__":
    main()
