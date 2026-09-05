"""Script de aplicación: agrega el endpoint GET /api/health a
backend/app.py — un endpoint liviano (sin login) que hace un SELECT 1
a la base de datos, pensado para que un servicio externo de "ping"
(cron-job.org, UptimeRobot, etc.) lo visite cada pocos minutos y así
evite que Render (plan gratis) duerma la app y que Neon (plan gratis)
suspenda la base de datos por inactividad.

Corre esto desde la raíz del repo (misma carpeta donde está la
carpeta backend/): py fix_app_health_endpoint.py
"""
import pathlib

RUTA = pathlib.Path("backend/app.py")

VIEJO = '''@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))'''

NUEVO = '''@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


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
    return {"ok": True}'''


def main():
    if not RUTA.exists():
        print(f"ERROR: no encuentro {RUTA}. Corre este script desde la raíz del repo (donde está la carpeta backend/).")
        return
    contenido = RUTA.read_text(encoding="utf-8")
    if NUEVO in contenido:
        print("Ya estaba aplicado, no hice nada.")
        return
    if VIEJO not in contenido:
        print("ERROR: no encontré el bloque esperado en app.py. Puede que ya lo hayas modificado a mano. Revisa manualmente.")
        return
    contenido = contenido.replace(VIEJO, NUEVO)
    RUTA.write_text(contenido, encoding="utf-8")
    print(f"Listo: {RUTA} actualizado con /api/health.")


if __name__ == "__main__":
    main()
