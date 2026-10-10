"""Paqueterías disponibles para cotizar envíos, generar guías y rastrear.

Cada una es un módulo/objeto con: CLAVE, NOMBRE, Error, estado(), simulado(),
cotizar(), generar_guia(), rastrear(), url_rastreo().
  - Estafeta: estafeta.py
  - Paquetexpress y Castores: paq_generico.Conector (se ajustan con el manual
    que entrega cada paquetería junto con las credenciales).
"""
from concurrent.futures import ThreadPoolExecutor

import estafeta
import paq_generico

paquetexpress = paq_generico.Conector(
    "paquetexpress", "Paquetexpress", "PAQUETEXPRESS",
    "https://www.paquetexpress.com.mx/",
    0.93, [("STD", "Estándar terrestre", 1.0, "2-4 días"), ("EXP", "Express", 1.6, "1-2 días")])

castores = paq_generico.Conector(
    "castores", "Castores", "CASTORES",
    "https://www.castores.com.mx/",
    0.88, [("PAQ", "Paquetería", 1.0, "2-5 días")])

PAQUETERIAS = {"estafeta": estafeta, "paquetexpress": paquetexpress, "castores": castores}
ERRORES = (estafeta.ErrorEstafeta, paq_generico.ErrorPaqueteria)


class ErrorEnvio(Exception):
    pass


def obtener(clave):
    p = PAQUETERIAS.get((clave or "estafeta").strip().lower())
    if not p:
        raise ErrorEnvio("Paquetería desconocida.")
    return p


def clave_item(clave):
    return obtener(clave).CLAVE.upper()


def nombre_item(clave):
    return f"Envío por paquetería {obtener(clave).NOMBRE}"


def claves_item():
    return tuple(c.upper() for c in PAQUETERIAS)


def estados():
    return [{"clave": c, "nombre": p.NOMBRE, "estado": p.estado()} for c, p in PAQUETERIAS.items()]


def conectadas():
    return [c for c, p in PAQUETERIAS.items() if p.modo()]


def cotizar_todas(cp_origen, cp_destino, paquete):
    """Consulta a la vez a todas las paqueterías conectadas.
    Regresa (servicios ordenados por costo, errores por paquetería)."""
    claves = conectadas()
    if not claves:
        raise ErrorEnvio("Ninguna paquetería está conectada todavía (falta configurar las cuentas en Render).")

    def una(c):
        p = PAQUETERIAS[c]
        try:
            return c, [dict(s, paqueteria=c, paqueteria_nombre=p.NOMBRE) for s in p.cotizar(cp_origen, cp_destino, paquete)], None
        except ERRORES as e:
            return c, [], str(e)
        except Exception as e:  # una paquetería caída no tumba a las demás
            return c, [], f"{p.NOMBRE}: error inesperado ({e.__class__.__name__})."

    with ThreadPoolExecutor(max_workers=len(claves)) as ex:
        resultados = list(ex.map(una, claves))
    servicios = sorted([s for _, lista, _ in resultados for s in lista], key=lambda s: s["costo"])
    errores = [{"paqueteria": c, "paqueteria_nombre": PAQUETERIAS[c].NOMBRE, "error": err} for c, _, err in resultados if err]
    if not servicios:
        raise ErrorEnvio(" · ".join(e["error"] for e in errores) or "Ninguna paquetería tiene servicio para ese envío.")
    return servicios, errores
