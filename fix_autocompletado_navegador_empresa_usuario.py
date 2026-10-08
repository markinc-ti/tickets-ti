# -*- coding: utf-8 -*-
"""
Evita que el navegador sugiera nombres/datos que se escribieron antes en
los formularios de "Nueva empresa" y "Nuevo usuario"/"Editar usuario" del
panel de Administrar -- como es la MISMA pantalla y los MISMOS campos para
cualquier empresa (solo cambia el ID que se manda al servidor), el
navegador guarda todo lo que se ha escrito ahi con el tiempo y lo sugiere
despues sin importar de que empresa era, lo cual confunde (parece que el
sistema esta mezclando datos entre empresas, cuando en realidad es
autocompletado del navegador, no un problema de la base de datos).

Que hace: agrega autocomplete="off" a los campos de texto de esos 3
formularios (Nueva empresa, Nuevo usuario, Editar usuario) para que el
navegador deje de guardar/sugerir lo que se escribe ahi. No toca ningun
dato guardado en la base de datos -- esto es puramente que el navegador
ya no muestre el cuadrito de sugerencias.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:  py -3 fix_autocompletado_navegador_empresa_usuario.py
"""
import sys

ARCHIVOS = {
    'frontend/index.html': [
        # --- Nueva empresa ---
        [
            '<div class="field"><label>Nombre de la empresa</label><input id="emp_nombre" /></div>',
            '<div class="field"><label>Nombre de la empresa</label><input id="emp_nombre" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Usuario (username)</label><input id="emp_admin_user" /></div>',
            '<div class="field"><label>Usuario (username)</label><input id="emp_admin_user" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Contraseña</label><input id="emp_admin_pass" type="password" /></div>',
            '<div class="field"><label>Contraseña</label><input id="emp_admin_pass" type="password" autocomplete="new-password" /></div>',
        ],
        [
            '<div class="field"><label>Nombre completo del administrador</label><input id="emp_admin_nombre" /></div>',
            '<div class="field"><label>Nombre completo del administrador</label><input id="emp_admin_nombre" autocomplete="off" /></div>',
        ],
        # --- Nuevo usuario ---
        [
            '<div class="field"><label>Nombre completo</label><input id="u_nombre" /></div>',
            '<div class="field"><label>Nombre completo</label><input id="u_nombre" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Usuario (username)</label><input id="u_username" /></div>',
            '<div class="field"><label>Usuario (username)</label><input id="u_username" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Puesto</label><input id="u_puesto" placeholder="ej. Auxiliar contable" /></div>',
            '<div class="field"><label>Puesto</label><input id="u_puesto" placeholder="ej. Auxiliar contable" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Número de empleado / ID (opcional)</label><input id="u_numero_empleado" placeholder="ej. EMP-0042" /></div>',
            '<div class="field"><label>Número de empleado / ID (opcional)</label><input id="u_numero_empleado" placeholder="ej. EMP-0042" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Contraseña</label><input id="u_password" type="password" /></div>',
            '<div class="field"><label>Contraseña</label><input id="u_password" type="password" autocomplete="new-password" /></div>',
        ],
        [
            '<input id="u_telefono" placeholder="+5215512345678" />',
            '<input id="u_telefono" placeholder="+5215512345678" autocomplete="off" />',
        ],
        # --- Editar usuario ---
        [
            '<div class="field"><label>Nombre completo</label><input id="e_nombre" value="${escapeHtml(u.nombre_completo)}" /></div>',
            '<div class="field"><label>Nombre completo</label><input id="e_nombre" value="${escapeHtml(u.nombre_completo)}" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Puesto</label><input id="e_puesto" value="${u.puesto ? escapeHtml(u.puesto) : \'\'}" placeholder="ej. Auxiliar contable" /></div>',
            '<div class="field"><label>Puesto</label><input id="e_puesto" value="${u.puesto ? escapeHtml(u.puesto) : \'\'}" placeholder="ej. Auxiliar contable" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Número de empleado / ID</label><input id="e_numero_empleado" value="${u.numero_empleado ? escapeHtml(u.numero_empleado) : \'\'}" placeholder="ej. EMP-0042" /></div>',
            '<div class="field"><label>Número de empleado / ID</label><input id="e_numero_empleado" value="${u.numero_empleado ? escapeHtml(u.numero_empleado) : \'\'}" placeholder="ej. EMP-0042" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>WhatsApp</label><input id="e_telefono" value="${u.telefono_whatsapp ? escapeHtml(u.telefono_whatsapp) : \'\'}" placeholder="+5215512345678" /></div>',
            '<div class="field"><label>WhatsApp</label><input id="e_telefono" value="${u.telefono_whatsapp ? escapeHtml(u.telefono_whatsapp) : \'\'}" placeholder="+5215512345678" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Nueva contraseña (déjalo vacío para no cambiarla)</label><input id="e_password" type="password" placeholder="mínimo 6 caracteres" /></div>',
            '<div class="field"><label>Nueva contraseña (déjalo vacío para no cambiarla)</label><input id="e_password" type="password" placeholder="mínimo 6 caracteres" autocomplete="new-password" /></div>',
        ],
        [
            '<div class="field"><label>RFC</label><input id="e_rfc" value="${u.rfc ? escapeHtml(u.rfc) : \'\'}" /></div>',
            '<div class="field"><label>RFC</label><input id="e_rfc" value="${u.rfc ? escapeHtml(u.rfc) : \'\'}" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>CURP</label><input id="e_curp" value="${u.curp ? escapeHtml(u.curp) : \'\'}" /></div>',
            '<div class="field"><label>CURP</label><input id="e_curp" value="${u.curp ? escapeHtml(u.curp) : \'\'}" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>N° de licencia</label><input id="e_numero_licencia" value="${u.numero_licencia ? escapeHtml(u.numero_licencia) : \'\'}" /></div>',
            '<div class="field"><label>N° de licencia</label><input id="e_numero_licencia" value="${u.numero_licencia ? escapeHtml(u.numero_licencia) : \'\'}" autocomplete="off" /></div>',
        ],
        [
            '<div class="field"><label>Tipo de licencia</label><input id="e_tipo_licencia" value="${u.tipo_licencia ? escapeHtml(u.tipo_licencia) : \'\'}" placeholder="ej. Mercantil" /></div>',
            '<div class="field"><label>Tipo de licencia</label><input id="e_tipo_licencia" value="${u.tipo_licencia ? escapeHtml(u.tipo_licencia) : \'\'}" placeholder="ej. Mercantil" autocomplete="off" /></div>',
        ],
    ],
}


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
    print('   git commit -m "Quita autocompletado del navegador en Nueva empresa / Nuevo usuario / Editar usuario"')
    print("   git push")


if __name__ == "__main__":
    main()
