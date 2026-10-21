# -*- coding: utf-8 -*-
"""
MARKINC LAB: pagina publica /eliminar-cuenta (la pide Google Play en
"Seguridad de los datos"): pasos para pedir que se borre la cuenta, que datos
se borran y cuales se conservan (facturas, 5 anios).
Toca: backend/app.py   Crea: frontend/eliminar_cuenta.html
Se puede correr varias veces.  Correr con:  py -3 fix_eliminar_cuenta_lab.py
"""
import os
import sys

ARCHIVOS = {
 "backend/app.py": [
  [
   "    return FileResponse(os.path.join(FRONTEND_DIR, \"privacidad.html\"))\n\n\n@app.get(\"/laboratorio-estudiantes/{codigo}\")\ndef pagina_laboratorio_estudiantes(codigo: str):\n    \"\"\"Página PÚBLICA -- el login/registro vive DENTRO de esta página (con la\n",
   "    return FileResponse(os.path.join(FRONTEND_DIR, \"privacidad.html\"))\n\n\n@app.get(\"/eliminar-cuenta\")\ndef pagina_eliminar_cuenta():\n    \"\"\"Cómo pedir que se borre la cuenta de Markinc Lab y qué datos se conservan\n    (la URL que pide Google Play en Seguridad de los datos).\"\"\"\n    return FileResponse(os.path.join(FRONTEND_DIR, \"eliminar_cuenta.html\"))\n\n\n@app.get(\"/laboratorio-estudiantes/{codigo}\")\ndef pagina_laboratorio_estudiantes(codigo: str):\n    \"\"\"Página PÚBLICA -- el login/registro vive DENTRO de esta página (con la\n"
  ]
 ]
}

NUEVOS = {
 "frontend/eliminar_cuenta.html": "<!doctype html>\n<html lang=\"es\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Markinc Lab — Eliminar tu cuenta</title>\n<style>\n  :root { --tinta:#2b2522; --gris:#6b625d; --marca:#a0342a; --fondo:#faf6f2; --linea:#e6ddd5; }\n  * { box-sizing:border-box; }\n  body { margin:0; background:var(--fondo); color:var(--tinta); font:16px/1.6 -apple-system, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif; }\n  main { max-width:760px; margin:0 auto; padding:32px 18px 60px; }\n  header { display:flex; align-items:center; gap:14px; margin-bottom:24px; }\n  .m { width:52px; height:52px; border-radius:12px; background:linear-gradient(135deg,#d1644f,#8c2a22); color:#fff; font:900 30px/52px Arial, sans-serif; text-align:center; flex:none; }\n  h1 { font-size:26px; margin:0; }\n  h2 { font-size:19px; margin:28px 0 8px; color:var(--marca); }\n  .nota { color:var(--gris); font-size:14px; }\n  section { border-top:1px solid var(--linea); padding-top:6px; }\n  a { color:var(--marca); }\n  .caja { background:#fff; border:1px solid var(--linea); border-radius:10px; padding:14px 16px; }\n</style>\n</head>\n<body>\n<main>\n  <header><div class=\"m\">M</div><div><h1>Markinc Lab</h1><div class=\"nota\">Cómo eliminar tu cuenta y tus datos — app Markinc Lab (portal de estudiantes)</div></div></header>\n\n  <p class=\"nota\">Desarrollador: Mark·Inc. Última actualización: 20 de octubre de 2026.</p>\n\n  <section id=\"pasos\">\n    <h2>Cómo pedir que se elimine tu cuenta</h2>\n    <ol>\n      <li>Escribe un correo a <a href=\"mailto:sistemas@markinc.com.mx?subject=Eliminar%20mi%20cuenta%20de%20Markinc%20Lab\">sistemas@markinc.com.mx</a> con el asunto <b>\"Eliminar mi cuenta de Markinc Lab\"</b>.</li>\n      <li>Envíalo desde el correo que registraste en la app e indica tu <b>matrícula o usuario</b> y tu nombre completo.</li>\n      <li>Te confirmaremos por correo que recibimos tu solicitud. Si tienes trabajos en proceso o pagos pendientes, te avisaremos antes de borrar la cuenta.</li>\n      <li>Eliminamos tu cuenta en un máximo de <b>20 días hábiles</b> y te avisamos cuando quede hecho. Después ya no podrás entrar a la app con esa matrícula.</li>\n    </ol>\n    <p class=\"caja\">También puedes pedirlo en persona en cualquier sucursal del laboratorio Markinc Lab.</p>\n  </section>\n\n  <section id=\"datos\">\n    <h2>Qué datos se eliminan</h2>\n    <ul>\n      <li>Tu cuenta y acceso: matrícula/usuario y contraseña.</li>\n      <li>Tus datos de contacto: nombre, correo electrónico, teléfono y dirección.</li>\n      <li>Los comprobantes de pago (fotos) que subiste.</li>\n      <li>El identificador del dispositivo que se usa para mandarte notificaciones.</li>\n    </ul>\n\n    <h2>Qué datos se conservan y por cuánto tiempo</h2>\n    <ul>\n      <li><b>Facturas y datos fiscales</b> (RFC, razón social, régimen fiscal) de los trabajos ya facturados: se conservan <b>5 años</b>, porque lo exige la legislación fiscal mexicana (Código Fiscal de la Federación).</li>\n      <li><b>Registro de los trabajos y pagos</b> realizados (folio, fecha, tipo de trabajo, importe): se conserva <b>5 años</b> por la misma razón, sin tus datos de contacto.</li>\n    </ul>\n    <p>Pasado ese plazo, también se eliminan.</p>\n  </section>\n\n  <section id=\"parcial\">\n    <h2>Borrar solo algunos datos (sin eliminar tu cuenta)</h2>\n    <p>Si solo quieres que borremos algunos datos, por ejemplo tu teléfono, tu dirección o un comprobante de pago, escribe a <a href=\"mailto:sistemas@markinc.com.mx?subject=Borrar%20datos%20de%20Markinc%20Lab\">sistemas@markinc.com.mx</a> con el asunto <b>\"Borrar datos de Markinc Lab\"</b> e indica tu matrícula y qué datos quieres que eliminemos. Lo hacemos en un máximo de 20 días hábiles.</p>\n    <p class=\"nota\">Consulta el <a href=\"/privacidad\">aviso de privacidad completo</a>.</p>\n  </section>\n</main>\n</body>\n</html>\n"
}


def leer(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read().decode("utf-8")
    crlf = "\r\n" in crudo
    return crudo.replace("\r\n", "\n"), crlf


def escribir(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "wb") as f:
        f.write(texto.encode("utf-8"))


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_eliminar_cuenta_lab.py")
        sys.exit(1)
    if not os.path.exists(os.path.join("backend", "app.py")):
        print("Corre el script dentro de la carpeta tickets-ti (donde esta la carpeta backend).")
        sys.exit(1)
    cambios = {}
    errores = []
    for ruta, pares in ARCHIVOS.items():
        texto, crlf = leer(ruta)
        original = texto
        for i, (viejo, nuevo) in enumerate(pares, 1):
            if nuevo in texto:
                continue
            n = texto.count(viejo)
            if n != 1:
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
                continue
            texto = texto.replace(viejo, nuevo)
        if texto != original:
            cambios[ruta] = (texto, crlf)
    if errores:
        print("No se cambio nada. Problemas:")
        for e in errores:
            print("  - " + e)
        sys.exit(1)
    nuevos = 0
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta) and leer(ruta)[0] == contenido:
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        escribir(ruta, contenido, False)
        print("Creado/actualizado:", ruta)
        nuevos += 1
    for ruta, (texto, crlf) in cambios.items():
        escribir(ruta, texto, crlf)
        print("Actualizado:", ruta)
    if not cambios and not nuevos:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo. Ahora sube los cambios con git (add, commit, push).")


if __name__ == "__main__":
    main()
