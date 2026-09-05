# -*- coding: utf-8 -*-
"""
Agrega el mapa de "Flotilla en vivo" como primera seccion del Dashboard
(arriba de todo lo demas), reutilizando el mismo endpoint que ya usa
Entregas -> Flotilla en vivo.

Uso: colocalo en la carpeta del repo (junto a frontend/) y corre:
    py fix_dashboard_flotilla.py
"""
import sys

ARCHIVOS = {'frontend/index.html': [['    const d = await api(\'/api/dashboard\');\n    const puedeAutorizar = SESION.usuario.rol === \'master\' || SESION.usuario.rol === \'admin\';\n    cont.innerHTML = `\n      ${puedeAutorizar ? \'<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>\' : \'\'}\n      <div class="dash-grid">', '    const d = await api(\'/api/dashboard\');\n    const puedeAutorizar = SESION.usuario.rol === \'master\' || SESION.usuario.rol === \'admin\';\n    const puedeVerFlotilla = META.mis_permisos.acceso_entregas;\n    cont.innerHTML = `\n      ${puedeVerFlotilla ? `\n        <div style="margin-bottom:24px;">\n          <h3 style="margin:0 0 8px;">📍 Flotilla en vivo</h3>\n          <div id="dashFlotillaMsg" style="font-size:12px; color:var(--muted); margin-bottom:8px;">Cargando posiciones…</div>\n          <div id="dashFlotillaMapa" style="width:100%; height:340px; border:1px solid rgba(155,157,159,0.3); border-radius:6px;"></div>\n        </div>\n      ` : \'\'}\n      ${puedeAutorizar ? \'<div id="dashAutorizaciones" style="margin-bottom:24px;"></div>\' : \'\'}\n      <div class="dash-grid">'], ['    if (puedeAutorizar) await renderAutorizacionesCompra();\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}', '    if (puedeAutorizar) await renderAutorizacionesCompra();\n    if (puedeVerFlotilla) await renderMapaFlotillaDashboard();\n  } catch (e) {\n    cont.innerHTML = `<p class="error-msg" style="display:block;">${e.message}</p>`;\n  }\n}\n\nasync function renderMapaFlotillaDashboard() {\n  const msg = document.getElementById(\'dashFlotillaMsg\');\n  if (!msg) return;\n  try {\n    const posiciones = await api(\'/api/entregas/mapa-flotilla\');\n    if (!posiciones.length) {\n      msg.textContent = \'Ningún vehículo con unidad Geotab vinculada tiene posición disponible todavía.\';\n      return;\n    }\n    msg.textContent = `${posiciones.length} vehículo(s) con ubicación en vivo:`;\n    const mapa = L.map(\'dashFlotillaMapa\');\n    L.tileLayer(\'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png\', { attribution: \'© OpenStreetMap\', maxZoom: 19 }).addTo(mapa);\n    const puntos = [];\n    posiciones.forEach(p => {\n      const marcador = L.marker([p.lat, p.lng]).addTo(mapa);\n      marcador.bindPopup(`<b>${escapeHtml(p.nombre)}</b><br>${p.velocidad_kmh != null ? Math.round(p.velocidad_kmh) + \' km/h\' : \'\'}`);\n      puntos.push([p.lat, p.lng]);\n    });\n    mapa.fitBounds(puntos, { padding: [30, 30] });\n  } catch (e) {\n    msg.innerHTML = `<span style="color:var(--copper);">${escapeHtml(e.message)}</span>`;\n  }\n}\n']]}


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
    print("   git add frontend/index.html")
    print('   git commit -m "Mapa de flotilla en vivo como primera seccion del Dashboard"')
    print("   git push")


if __name__ == "__main__":
    main()
