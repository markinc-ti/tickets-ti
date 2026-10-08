# -*- coding: utf-8 -*-
"""
Turnos -- pantalla: video en loop directo desde archivo (Cloudflare R2)

Antes la pantalla de turnos SOLO podia mostrar el video metido en un
<iframe> (pensado para links de \"insertar/embed\" de YouTube, Drive,
Vimeo, OneDrive) -- por eso costaba tanto trabajo: cada uno de esos
servicios tiene sus propias reglas para dejarse incrustar dentro de
otra pagina (bloqueadores, permisos, sesion, etc.), no fue un bug de
la app.

Ahora, si el link que pongas termina en .mp4/.webm/.ogg/.mov (por
ejemplo un archivo subido a Cloudflare R2), la pantalla usa un <video>
nativo del navegador en vez de un iframe: lo descarga UNA vez y lo
repite solo (loop), sin pedirlo de nuevo al servidor en cada vuelta --
por eso no importa que este muchas horas seguidas reproduciendose,
el costo real es minimo. Si el link no es un archivo directo, se sigue
usando <iframe> como antes (por si algun dia usas otro tipo de link).

Que toca:
  - frontend/pantalla_turnos.html -- CSS + logica de mostrarVideoActual()
  - frontend/index.html -- solo el texto de ayuda junto al campo de video(s)

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py -3 fix_turnos_video_r2.py
"""
import os
import sys

ARCHIVOS = {}

ARCHIVOS['frontend/pantalla_turnos.html'] = [
    [
        "  #videoWrap iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; }",
        "  #videoWrap iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; }\n  #videoWrap video { position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; }",
    ],
    [
        "  function mostrarVideoActual() {\n    const wrap = document.getElementById('videoWrap');\n    const msg = document.getElementById('sinVideoMsg');\n    wrap.querySelectorAll('iframe').forEach(f => f.remove());\n    if (!videos.length) {\n      msg.style.display = 'flex';\n      return;\n    }\n    msg.style.display = 'none';\n    const iframe = document.createElement('iframe');\n    iframe.src = videos[videoIdx % videos.length];\n    iframe.allow = 'autoplay; fullscreen';\n    iframe.setAttribute('allowfullscreen', '');\n    wrap.appendChild(iframe);\n  }",
        "  function mostrarVideoActual() {\n    const wrap = document.getElementById('videoWrap');\n    const msg = document.getElementById('sinVideoMsg');\n    wrap.querySelectorAll('iframe, video').forEach(f => f.remove());\n    if (!videos.length) {\n      msg.style.display = 'flex';\n      return;\n    }\n    msg.style.display = 'none';\n    const url = videos[videoIdx % videos.length];\n    // Si es un link directo a un archivo de video (ej. subido a Cloudflare\n    // R2), se reproduce con <video> nativo -- el navegador lo descarga UNA\n    // vez y lo repite en loop solo, sin volver a pedirlo al servidor en\n    // cada vuelta. Para cualquier otro link (embed de YouTube/Drive/etc.)\n    // se sigue usando <iframe> como respaldo.\n    const esArchivoDirecto = /\\.(mp4|webm|ogg|mov)(\\?|#|$)/i.test(url);\n    if (esArchivoDirecto) {\n      const video = document.createElement('video');\n      video.src = url;\n      video.autoplay = true;\n      video.muted = true;\n      video.loop = true;\n      video.playsInline = true;\n      video.setAttribute('webkit-playsinline', '');\n      wrap.appendChild(video);\n    } else {\n      const iframe = document.createElement('iframe');\n      iframe.src = url;\n      iframe.allow = 'autoplay; fullscreen';\n      iframe.setAttribute('allowfullscreen', '');\n      wrap.appendChild(iframe);\n    }\n  }",
    ],
]

ARCHIVOS['frontend/index.html'] = [
    [
        "    <div class=\"field\" style=\"margin-top:16px;\"><label>Video(s) para la pantalla (un link por línea — YouTube, Drive, Vimeo o OneDrive, usa el link de \"Insertar/Embed\")</label>",
        "    <div class=\"field\" style=\"margin-top:16px;\"><label>Video(s) para la pantalla (un link por línea — recomendado: link directo a un archivo .mp4, por ejemplo de Cloudflare R2. También acepta un link de \"Insertar/Embed\" de YouTube/Drive/Vimeo/OneDrive)</label>",
    ],
]


def leer(ruta):
    with open(ruta, 'r', encoding='utf-8') as f:
        return f.read()


def escribir(ruta, contenido):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    hubo_error_total = False

    for ruta, cambios_lista in ARCHIVOS.items():
        try:
            contenido = leer(ruta)
        except FileNotFoundError:
            print("[" + ruta + "] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
            hubo_error_total = True
            continue
        cambios = 0
        hubo_error = False
        for viejo, nuevo in cambios_lista:
            if viejo in contenido:
                contenido = contenido.replace(viejo, nuevo, 1)
                cambios += 1
            elif nuevo in contenido:
                cambios += 1  # ya aplicado antes
            else:
                print("[" + ruta + "] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print("[" + ruta + "] " + str(cambios) + "/" + str(len(cambios_lista)) + " cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Turnos: pantalla soporta video directo (Cloudflare R2) en vez de solo iframe"')
    print("   git push")


if __name__ == "__main__":
    main()
