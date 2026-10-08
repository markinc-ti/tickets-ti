# -*- coding: utf-8 -*-
"""
Agrega el boton que faltaba en Administrar -> Integraciones para poder dar
de alta al primer estudiante de Laboratorio: "Portal de estudiantes".

Por que hacia falta: el backend YA tenia listas las funciones para generar
el enlace de auto-registro de estudiantes (matricula + contrasena) desde
hace tiempo -- pero nunca se conecto un boton en el panel para verlo. Sin
ese enlace, un estudiante nunca podia registrarse la primera vez (nadie
sabia que URL usar), y por lo tanto tampoco se podia probar la tarjeta de
"Importar desde DS Core" en la vista de estudiante.

Que agrega, con nombres exactos (solo frontend/index.html, no toca nada
del backend porque los endpoints ya existian):
  - Pestana nueva "🎓 Portal de estudiantes" dentro de Administrar ->
    Integraciones, junto a DS Core y Kommo.
  - Esa pestana muestra el enlace de registro (algo como
    https://tickets-ti-n4wn.onrender.com/laboratorio-estudiantes/XXXXXXXX)
    con un boton para copiarlo, listo para mandarselo a los estudiantes
    (por WhatsApp, correo, o pegado en el salon).
  - Boton "Generar un enlace nuevo" por si el enlace se comparte sin
    querer -- invalida el anterior, igual que ya existe para otras ligas
    de la app (turnos, mi-calendario).

Una vez que un estudiante entra a ese enlace, se registra el solo con su
matricula y una contrasena, y ya puede dar de alta sus propios trabajos --
incluida la tarjeta de "Importar desde DS Core" si ya esta conectado.

Uso: coloca este script en la carpeta del repo (junto a backend/ y
frontend/) y corre:
    py fix_portal_estudiantes.py
"""
import os
import sys

ARCHIVOS = {}

# ---------------------------------------------------------------------------
ARCHIVOS['frontend/index.html'] = [
    [
        "const grupoIntegraciones = ['microsip','explorador_microsip','shopify','dscore','geotab','locationiq','kommo','importar-reparaciones'].includes(ADMIN_TAB);",
        "const grupoIntegraciones = ['microsip','explorador_microsip','shopify','dscore','estudiantes-laboratorio','geotab','locationiq','kommo','importar-reparaciones'].includes(ADMIN_TAB);",
    ],
    [
        '          <button class="admin-tab ${ADMIN_TAB===\'dscore\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'dscore\')">🦷 DS Core (Laboratorio)</button>\n          <button class="admin-tab ${ADMIN_TAB===\'geotab\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'geotab\')">📍 Geotab (GPS)</button>',
        '          <button class="admin-tab ${ADMIN_TAB===\'dscore\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'dscore\')">🦷 DS Core (Laboratorio)</button>\n          <button class="admin-tab ${ADMIN_TAB===\'estudiantes-laboratorio\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'estudiantes-laboratorio\')">🎓 Portal de estudiantes</button>\n          <button class="admin-tab ${ADMIN_TAB===\'geotab\'?\'active\':\'\'}" onclick="cambiarAdminTab(\'geotab\')">📍 Geotab (GPS)</button>',
    ],
    [
        "  } else if (ADMIN_TAB === 'dscore' && esAdmin) {\n    const config = await api('/api/laboratorio/dscore/config');\n    renderDSCoreAdmin(tabs, config);\n  } else if (ADMIN_TAB === 'geotab' && esAdmin) {",
        "  } else if (ADMIN_TAB === 'dscore' && esAdmin) {\n    const config = await api('/api/laboratorio/dscore/config');\n    renderDSCoreAdmin(tabs, config);\n  } else if (ADMIN_TAB === 'estudiantes-laboratorio' && esAdmin) {\n    const datosEstudiantes = await api('/api/laboratorio/estudiantes/codigo', { method: 'POST' });\n    renderEstudiantesLaboratorioAdmin(tabs, datosEstudiantes);\n  } else if (ADMIN_TAB === 'geotab' && esAdmin) {",
    ],
    [
        "async function desconectarDSCoreUI(boton) {\n  if (!confirm('¿Desconectar DS Core? El estudiante ya no podrá importar pedidos por código hasta que se vuelva a conectar.')) return;\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api('/api/laboratorio/dscore/desconectar', { method: 'POST' });\n      await cambiarAdminTab('dscore');\n    } catch (e) {\n      document.getElementById('dscoreError').textContent = e.message;\n    }\n  });\n}\n\nfunction renderKommoAdmin(tabsHtml, config) {",
        'async function desconectarDSCoreUI(boton) {\n  if (!confirm(\'¿Desconectar DS Core? El estudiante ya no podrá importar pedidos por código hasta que se vuelva a conectar.\')) return;\n  await conBloqueoDeBoton(boton, async () => {\n    try {\n      await api(\'/api/laboratorio/dscore/desconectar\', { method: \'POST\' });\n      await cambiarAdminTab(\'dscore\');\n    } catch (e) {\n      document.getElementById(\'dscoreError\').textContent = e.message;\n    }\n  });\n}\n\nfunction renderEstudiantesLaboratorioAdmin(tabsHtml, datos) {\n  const urlCompleta = location.origin + datos.url_registro;\n  document.getElementById(\'modalContent\').innerHTML = `\n    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n    <h2>Administrar</h2>\n    ${tabsHtml}\n    <p style="font-size:12px; color:var(--muted); margin-bottom:16px;">\n      Enlace para que los estudiantes se registren ellos mismos (matrícula + contraseña) y puedan dar de alta sus propios trabajos de laboratorio, incluida la importación desde DS Core. Compárteselo una sola vez -- cualquiera con este enlace se puede registrar.\n    </p>\n    <div class="field">\n      <label>Enlace de registro</label>\n      <div style="display:flex; gap:8px;">\n        <input type="text" id="estudiantes_lab_url" value="${escapeHtml(urlCompleta)}" readonly style="flex:1; font-size:11px;" />\n        <button class="secondary" onclick="copiarEnlaceEstudiantesLaboratorio()">Copiar</button>\n      </div>\n    </div>\n    <button class="secondary" style="width:100%; margin-top:10px; color:var(--urgente);" onclick="regenerarEnlaceEstudiantesLaboratorioUI()">Generar un enlace nuevo (invalida el anterior)</button>\n  `;\n  abrirModal(true);\n}\n\nfunction copiarEnlaceEstudiantesLaboratorio() {\n  const input = document.getElementById(\'estudiantes_lab_url\');\n  input.select();\n  navigator.clipboard.writeText(input.value).then(() => mostrarExito(\'Enlace copiado\'));\n}\n\nasync function regenerarEnlaceEstudiantesLaboratorioUI() {\n  if (!confirm(\'El enlace anterior va a dejar de funcionar -- los estudiantes que todavía no se registren tendrían que usar el nuevo. ¿Seguro?\')) return;\n  try {\n    await api(\'/api/laboratorio/estudiantes/codigo/regenerar\', { method: \'POST\' });\n    await cambiarAdminTab(\'estudiantes-laboratorio\');\n    mostrarExito(\'Nuevo enlace generado\');\n  } catch (e) {\n    alert(e.message);\n  }\n}\n\nfunction renderKommoAdmin(tabsHtml, config) {',
    ]
]

# ---------------------------------------------------------------------------


def leer(ruta):
    with open(ruta, "r", encoding="utf-8", newline=None) as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)


def aplicar_reemplazos(ruta):
    reemplazos = ARCHIVOS[ruta]
    try:
        contenido = leer(ruta)
    except FileNotFoundError:
        print(f"[{ruta}] No encontre el archivo -- corre esto desde la carpeta del repo.")
        return False
    cambios = 0
    hubo_error = False
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
    return not hubo_error


def main():
    ok = True
    ok = aplicar_reemplazos("frontend/index.html") and ok

    if not ok:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print('   git commit -m "Agrega boton de Portal de estudiantes en Administrar para generar el enlace de auto-registro"')
    print("   git push")


if __name__ == "__main__":
    main()
