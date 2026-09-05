# -*- coding: utf-8 -*-
"""
Aplica automáticamente el arreglo de "Flotilla en vivo":
1. Mueve la ruta /api/entregas/mapa-flotilla ANTES de /api/entregas/{entrega_id}
   (para que FastAPI no la confunda con un ID numérico -> error 422).
2. Corrige la función api() del frontend para que nunca muestre "[object Object]".

Uso: colócalo en la carpeta del repo (junto a las carpetas backend/ y frontend/)
y corre:  py fix_flotilla.py
"""
import re
import sys

RUTA_BACKEND = "backend/app.py"
RUTA_FRONTEND = "frontend/index.html"


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def arreglar_backend():
    contenido = leer(RUTA_BACKEND)

    marcador_inicio = '@app.get("/api/entregas/mapa-flotilla")'
    marcador_fin = "    return resultado\n"
    marcador_entrega_id = '@app.get("/api/entregas/{entrega_id}")'

    if marcador_inicio not in contenido:
        print("[backend] No encontré la ruta mapa-flotilla. ¿Ya se aplicó el arreglo antes?")
        return False

    pos_ya_movido = contenido.find(marcador_entrega_id)
    pos_mapa = contenido.find(marcador_inicio)
    if pos_mapa != -1 and pos_ya_movido != -1 and pos_mapa < pos_ya_movido:
        print("[backend] La ruta mapa-flotilla ya está ANTES de {entrega_id}. No hace falta nada.")
        return True

    inicio = contenido.index(marcador_inicio)
    fin_marcador = contenido.index(marcador_fin, inicio) + len(marcador_fin)
    bloque = contenido[inicio:fin_marcador]

    # Quita el bloque de su lugar original (junto con las líneas en blanco que lo separan)
    contenido_sin_bloque = contenido[:inicio] + contenido[fin_marcador:]
    contenido_sin_bloque = contenido_sin_bloque.replace("\n\n\n\n", "\n\n\n", 1)

    # Lo inserta justo antes de la ruta {entrega_id}
    pos_entrega_id = contenido_sin_bloque.index(marcador_entrega_id)
    nuevo_contenido = (
        contenido_sin_bloque[:pos_entrega_id]
        + bloque
        + "\n\n"
        + contenido_sin_bloque[pos_entrega_id:]
    )

    escribir(RUTA_BACKEND, nuevo_contenido)
    print("[backend] Listo: mapa-flotilla movida antes de {entrega_id}.")
    return True


def arreglar_frontend():
    contenido = leer(RUTA_FRONTEND)

    viejo = (
        "if (!r.ok) { const e = await r.json().catch(() => ({})); "
        "throw new Error(e.detail || `Error del servidor (código ${r.status}) "
        "— puede que falte redesplegar la última versión`); }"
    )

    if viejo not in contenido:
        if "let mensaje = e.detail;" in contenido:
            print("[frontend] Ya está aplicado el arreglo. No hace falta nada.")
            return True
        print("[frontend] No encontré la línea esperada. Puede que el archivo ya haya cambiado.")
        return False

    nuevo = """if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      let mensaje = e.detail;
      if (Array.isArray(mensaje)) {
        mensaje = mensaje.map(m => (m && typeof m === 'object') ? (m.msg || JSON.stringify(m)) : m).join('; ');
      } else if (mensaje && typeof mensaje === 'object') {
        mensaje = mensaje.msg || JSON.stringify(mensaje);
      }
      throw new Error(mensaje || `Error del servidor (código ${r.status}) — puede que falte redesplegar la última versión`);
    }"""

    contenido = contenido.replace(viejo, nuevo)
    escribir(RUTA_FRONTEND, contenido)
    print("[frontend] Listo: ya no va a mostrar [object Object].")
    return True


if __name__ == "__main__":
    ok1 = arreglar_backend()
    ok2 = arreglar_frontend()
    if ok1 and ok2:
        print("\n✅ Todo listo. Ahora corre:")
        print('   git add backend/app.py frontend/index.html')
        print('   git commit -m "Fix: mapa-flotilla daba 422 por orden de rutas"')
        print("   git push")
    else:
        print("\n⚠️  Algo no se pudo aplicar automáticamente. Avísale a Claude qué mensaje salió.")
        sys.exit(1)
