# -*- coding: utf-8 -*-
"""
Tres cambios:
1. El rol "master" ya puede ver el mapa de flotilla en su Dashboard (antes
   estaba bloqueado sin querer por la regla "master solo entra al Dashboard").
2. Mientras master tenga la sesion abierta, un ping cada 4 minutos mantiene
   despierto el backend (evita el arranque en frio del plan gratis de Render).
3. "Ventas por sucursal" del Dashboard se actualiza sola cada 30 segundos.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_master_dashboard.py
"""
import sys

ARCHIVOS = {'backend/app.py': [['def requiere_ver_entregas(usuario: dict = Depends(requiere_empresa)) -> dict:\n    """Igual que requiere_ver_tickets/reparaciones, pero para Entregas. El rol\n    \'instalador\' siempre tiene acceso — es su único módulo, no se le puede\n    quitar — los demás roles sí pueden perder este acceso desde Administrar → Accesos."""\n    if usuario["rol"] == "instalador":\n        return usuario\n    usuario = _con_permisos(usuario)\n    if not usuario.get("acceso_entregas", True):\n        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Entregas")\n    return usuario', 'def requiere_ver_entregas(usuario: dict = Depends(requiere_empresa)) -> dict:\n    """Igual que requiere_ver_tickets/reparaciones, pero para Entregas. El rol\n    \'instalador\' siempre tiene acceso — es su único módulo, no se le puede\n    quitar — los demás roles sí pueden perder este acceso desde Administrar → Accesos."""\n    if usuario["rol"] == "instalador":\n        return usuario\n    usuario = _con_permisos(usuario)\n    if not usuario.get("acceso_entregas", True):\n        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Entregas")\n    return usuario\n\n\ndef requiere_ver_flotilla(usuario: dict = Depends(requiere_empresa_o_master)) -> dict:\n    """Como requiere_ver_entregas, pero además deja pasar a \'master\' — el mapa\n    de flotilla se muestra dentro de su Dashboard (su único lugar dentro de la\n    app), aunque master no tiene acceso al resto del módulo de Entregas."""\n    if usuario["rol"] in ("instalador", "master"):\n        return usuario\n    usuario = _con_permisos(usuario)\n    if not usuario.get("acceso_entregas", True):\n        raise HTTPException(status_code=403, detail="No tienes acceso al módulo de Entregas")\n    return usuario'], ['@app.get("/api/entregas/mapa-flotilla")\ndef api_mapa_flotilla(usuario: dict = Depends(requiere_ver_entregas)):', '@app.get("/api/entregas/mapa-flotilla")\ndef api_mapa_flotilla(usuario: dict = Depends(requiere_ver_flotilla)):']], 'frontend/index.html': [["function cerrarSesion() {\n  SESION = null;\n  localStorage.removeItem('sesion_tickets_ti');\n  if (autoRefreshTimer) clearInterval(autoRefreshTimer);\n  if (inactividadTimer) clearTimeout(inactividadTimer);\n  if (notificacionesTimer) clearInterval(notificacionesTimer);", "function cerrarSesion() {\n  SESION = null;\n  localStorage.removeItem('sesion_tickets_ti');\n  if (autoRefreshTimer) clearInterval(autoRefreshTimer);\n  if (inactividadTimer) clearTimeout(inactividadTimer);\n  if (notificacionesTimer) clearInterval(notificacionesTimer);\n  if (mantenerActivaTimer) clearInterval(mantenerActivaTimer);\n  if (ventasPvAutoRefreshTimer) clearInterval(ventasPvAutoRefreshTimer);"], ['let autoRefreshTimer = null;', 'let autoRefreshTimer = null;\nlet mantenerActivaTimer = null;\nlet ventasPvAutoRefreshTimer = null;\n\n// Solo para el rol "master": su Dashboard queda abierto de fondo casi todo\n// el tiempo, y el plan gratis de Render "duerme" el backend tras un rato\n// sin uso — el próximo dato tardaría en cargar por el arranque en frío.\n// Este ping cada 4 minutos mantiene el servidor despierto mientras master\n// tenga la sesión abierta (no se activa para otros roles).\nfunction iniciarMantenerAppActiva() {\n  if (mantenerActivaTimer) return;\n  mantenerActivaTimer = setInterval(() => {\n    fetch(`${API}/api/meta`, { headers: headers(false) }).catch(() => {});\n  }, 4 * 60 * 1000);\n}\n'], ["  if (SESION.usuario.rol === 'master') {\n    document.getElementById('whoamiDashboard').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol]}`;\n    document.getElementById('btnDashboardVolver').style.display = 'none';\n    await abrirDashboard();\n    return;\n  }", "  if (SESION.usuario.rol === 'master') {\n    document.getElementById('whoamiDashboard').innerHTML = `<b>${escapeHtml(SESION.usuario.nombre)}</b><br>${NOMBRES_ROL[SESION.usuario.rol]}`;\n    document.getElementById('btnDashboardVolver').style.display = 'none';\n    await abrirDashboard();\n    iniciarMantenerAppActiva();\n    return;\n  }"], ["    if (puedeVerFlotilla) {\n      document.getElementById('dashVentasPvFecha').value = new Date().toISOString().slice(0, 10);\n      document.getElementById('dashVentasPvMes').value = new Date().toISOString().slice(0, 7);\n      cambiarPeriodoVentasPv(PERIODO_VENTAS_PV);\n    }", "    if (puedeVerFlotilla) {\n      document.getElementById('dashVentasPvFecha').value = new Date().toISOString().slice(0, 10);\n      document.getElementById('dashVentasPvMes').value = new Date().toISOString().slice(0, 7);\n      cambiarPeriodoVentasPv(PERIODO_VENTAS_PV);\n      iniciarAutoRefrescoVentasPv();\n    }"], ['async function renderVentasPvDashboard() {', "// Se actualiza sola cada 30 segundos mientras el Dashboard siga abierto, para\n// que el desglose de ventas no se quede desfasado. Solo refresca si el\n// Dashboard sigue en pantalla y la sección todavía existe (evita seguir\n// jalando datos de fondo si el usuario ya se fue a otra parte de la app).\nfunction iniciarAutoRefrescoVentasPv() {\n  if (ventasPvAutoRefreshTimer) return;\n  ventasPvAutoRefreshTimer = setInterval(() => {\n    const dash = document.getElementById('dashboardScreen');\n    if (dash && dash.style.display !== 'none' && document.getElementById('dashVentasPvContenido')) {\n      renderVentasPvDashboard();\n    }\n  }, 30 * 1000);\n}\n\nasync function renderVentasPvDashboard() {"]]}


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def main():
    hubo_error = False
    for ruta, reemplazos in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
            hubo_error = True
            continue
        cambios = 0
        for viejo, nuevo in reemplazos:
            if nuevo in contenido:
                continue
            if viejo not in contenido:
                print(f"[{ruta}] No encontre un bloque esperado (el archivo pudo haber cambiado). Avisale a Claude.")
                hubo_error = True
                continue
            contenido = contenido.replace(viejo, nuevo, 1)
            cambios += 1
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios} cambio(s) aplicado(s).")

    if hubo_error:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add backend/app.py frontend/index.html")
    print('   git commit -m "Master ve GPS en Dashboard + mantener app activa + ventas PV en vivo"')
    print("   git push")


if __name__ == "__main__":
    main()
