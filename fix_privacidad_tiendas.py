# -*- coding: utf-8 -*-
"""
Página pública de aviso de privacidad y soporte para publicar las apps en
Google Play y App Store: /privacidad y /soporte (frontend/privacidad.html).
REQUIERE haber corrido antes fix_lab_entregas_checador.py.
Toca: backend/app.py; crea frontend/privacidad.html
Se puede correr varias veces.
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "# \"Folio de escaneo\" sigue siendo texto libre por ahora -- la Fase 2 lo\n# reemplaza por la búsqueda real del escaneo en DS Core.\n\n@app.get(\"/laboratorio-estudiantes/{codigo}\")\ndef pagina_laboratorio_estudiantes(codigo: str):\n    \"\"\"Página PÚBLICA -- el login/registro vive DENTRO de esta página (con la\n",
   "# \"Folio de escaneo\" sigue siendo texto libre por ahora -- la Fase 2 lo\n# reemplaza por la búsqueda real del escaneo en DS Core.\n\n@app.get(\"/privacidad\")\n@app.get(\"/soporte\")\ndef pagina_privacidad():\n    \"\"\"Aviso de privacidad y soporte (público) — la URL que piden Google Play y\n    App Store para publicar las apps.\"\"\"\n    return FileResponse(os.path.join(FRONTEND_DIR, \"privacidad.html\"))\n\n\n@app.get(\"/laboratorio-estudiantes/{codigo}\")\ndef pagina_laboratorio_estudiantes(codigo: str):\n    \"\"\"Página PÚBLICA -- el login/registro vive DENTRO de esta página (con la\n"
  ]
 ]
}

NUEVOS = {
 "frontend/privacidad.html": "<!doctype html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Mark·Inc — Aviso de privacidad y soporte</title>\n<style>\n  :root { --tinta:#2b2522; --gris:#6b625d; --marca:#a0342a; --fondo:#faf6f2; --linea:#e6ddd5; }\n  * { box-sizing:border-box; }\n  body { margin:0; background:var(--fondo); color:var(--tinta); font:16px/1.6 -apple-system, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; }\n  main { max-width:760px; margin:0 auto; padding:32px 18px 60px; }\n  header { display:flex; align-items:center; gap:14px; margin-bottom:24px; }\n  .m { width:52px; height:52px; border-radius:12px; background:linear-gradient(135deg,#d1644f,#8c2a22); color:#fff; font:900 30px/52px Arial, sans-serif; text-align:center; }\n  h1 { font-size:26px; margin:0; }\n  h2 { font-size:19px; margin:28px 0 8px; color:var(--marca); }\n  p, li { color:var(--tinta); }\n  .nota { color:var(--gris); font-size:14px; }\n  section { border-top:1px solid var(--linea); padding-top:6px; }\n  a { color:var(--marca); }\n</style>\n</head>\n<body>\n<main>\n  <header><div class=\"m\">M</div><div><h1>Mark·Inc</h1><div class=\"nota\">Aviso de privacidad de las apps Mark·Inc y soporte</div></div></header>\n\n  <p class=\"nota\">Última actualización: 13 de octubre de 2026.</p>\n\n  <section id=\"privacidad\">\n    <h2>¿Quiénes somos?</h2>\n    <p>Mark·Inc (en adelante, \"nosotros\") ofrece la app <b>Mark·Inc</b> y el sistema web asociado para uso interno de sus colaboradores, encargados de sucursal y personal autorizado, y la app de laboratorio para estudiantes y doctores que solicitan trabajos dentales.</p>\n\n    <h2>Datos que recabamos</h2>\n    <ul>\n      <li><b>Datos de cuenta:</b> nombre, usuario o matrícula, teléfono, correo electrónico, sucursal y puesto.</li>\n      <li><b>Ubicación:</b> solo en el momento en que el usuario registra una checada de entrada, comida o salida (checador de Recursos Humanos) y cuando se calcula el flete de una instalación. La app no rastrea la ubicación en segundo plano.</li>\n      <li><b>Fotos y cámara:</b> la selfie que se toma al checar, las fotos de evidencia (reparaciones, avances de proyectos, justificantes) y el escaneo de códigos de barras. Solo se usan cuando el usuario toca el botón correspondiente.</li>\n      <li><b>Firmas:</b> firmas de recibido y de conformidad capturadas en pantalla.</li>\n      <li><b>Notificaciones:</b> un identificador del dispositivo para enviarle avisos de la app.</li>\n      <li><b>Información del trabajo:</b> tickets, reparaciones, pedidos de laboratorio, proyectos, tareas e incidencias que el usuario registra.</li>\n    </ul>\n\n    <h2>Para qué los usamos</h2>\n    <ul>\n      <li>Operar los módulos de la app: tickets, reparaciones, laboratorio, proyectos, ventas y Recursos Humanos.</li>\n      <li>Registrar la asistencia de los colaboradores que tienen activado el checador, y verificar que la persona que checa sea quien dice ser (comparación de la selfie con su foto registrada, que hace personal de Recursos Humanos).</li>\n      <li>Enviar avisos sobre el estado de sus trámites, tareas o trabajos.</li>\n      <li>Emitir comprobantes, órdenes de servicio y facturas cuando se solicitan.</li>\n    </ul>\n    <p>No vendemos ni rentamos datos personales, y no los usamos para publicidad.</p>\n\n    <h2>Con quién se comparten</h2>\n    <p>Solo con proveedores que nos ayudan a operar el servicio (alojamiento del servidor y base de datos, envío de notificaciones de Google Firebase, mensajería de WhatsApp Business de Meta para enviar órdenes y diagnósticos al cliente, y nuestro sistema administrativo), bajo obligación de confidencialidad, o cuando lo exija una autoridad competente.</p>\n\n    <h2>Conservación y seguridad</h2>\n    <p>La información viaja cifrada (HTTPS) y se guarda en servidores con acceso restringido. Conservamos los datos mientras exista la relación laboral o comercial y el tiempo que exijan las obligaciones legales y fiscales.</p>\n\n    <h2>Tus derechos (ARCO)</h2>\n    <p>Puedes solicitar acceso, rectificación, cancelación u oposición al uso de tus datos, o pedir que se elimine tu cuenta, escribiendo a <a href=\"mailto:sistemas@markinc.com.mx\">sistemas@markinc.com.mx</a>. Responderemos en un máximo de 20 días hábiles.</p>\n  </section>\n\n  <section id=\"soporte\">\n    <h2>Soporte</h2>\n    <p>¿Problemas para entrar o usar la app? Escríbenos a <a href=\"mailto:sistemas@markinc.com.mx\">sistemas@markinc.com.mx</a> o acércate al departamento de Sistemas. Las cuentas de colaboradores las da de alta el administrador de tu empresa.</p>\n  </section>\n</main>\n</body>\n</html>\n"
}

NUEVOS_BIN = {}


def main():
    errores = []
    with open("backend/app.py", encoding="utf-8") as f:
        if "def _hay_cara" not in f.read():
            print("Primero corre fix_lab_entregas_checador.py (y los anteriores), y luego este.")
            sys.exit(1)
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    bin_cambios = {}
    for ruta, b64 in NUEVOS_BIN.items():
        datos = base64.b64decode(b64)
        if os.path.exists(ruta):
            with open(ruta, "rb") as f:
                if f.read() == datos:
                    continue
        bin_cambios[ruta] = datos
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        # Windows: el archivo puede tener saltos CRLF, LF o una mezcla.
        # Se trabaja todo en LF y al guardar se deja como estaba (CRLF si tenia).
        crlf = "\r\n" in original
        texto = original.replace("\r\n", "\n")
        inicial = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue  # ya aplicado
            n = texto.count(viejo)
            if n != 1:
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
                continue
            texto = texto.replace(viejo, nuevo, 1)
        if texto != inicial:
            cambios[ruta] = texto.replace("\n", "\r\n") if crlf else texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, datos in bin_cambios.items():
        with open(ruta, "wb") as f:
            f.write(datos)
        print("Actualizado:", ruta)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios and not bin_cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
