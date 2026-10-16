# -*- coding: utf-8 -*-
"""
Minuta con IA: Google retiro el modelo gemini-2.5-flash para cuentas nuevas
(error 404 "no longer available to new users").
Ahora se prueban modelos vigentes en orden (gemini-3.8-flash, gemini-flash-latest...)
y si Gemini sugiere otro modelo en el error, se usa ese automaticamente.
REQUIERE haber corrido antes fix_proyectos_minuta_reunion.py.
Toca: backend/minuta_ia.py
Se puede correr varias veces.  Correr con:  py -3 fix_minuta_modelo_gemini.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/minuta_ia.py": [
  [
   "import requests\n\nAPI = \"https://generativelanguage.googleapis.com\"\nMODELO = os.getenv(\"GEMINI_MODELO_MINUTA\", \"gemini-2.5-flash\")\n\n\nclass ErrorMinuta(Exception):\n",
   "import requests\n\nAPI = \"https://generativelanguage.googleapis.com\"\n# Google va retirando modelos (\"no longer available to new users\"). Se prueba en orden:\n# el de la variable GEMINI_MODELO_MINUTA (si existe), luego estos; si Gemini responde 404\n# y sugiere otro modelo en el mensaje, se usa ese. El que funcione se recuerda.\nMODELOS = [m for m in [os.getenv(\"GEMINI_MODELO_MINUTA\", \"\").strip(),\n                       \"gemini-3.8-flash\", \"gemini-flash-latest\", \"gemini-2.5-flash\"] if m]\n_modelo_bueno = None\n\n\nclass ErrorMinuta(Exception):\n"
  ],
  [
   "        raise ErrorMinuta(f\"Gemini respondió con error ({r.status_code}): {r.text[:300]}\")\n\n\ndef _prompt(participantes, contexto, hoy):\n    lista = \"\\n\".join(f\"- {p['nombre']}\" + (f\" ({p['puesto']})\" if p.get(\"puesto\") else \"\") for p in participantes) or \"- (no se indicaron)\"\n    return f\"\"\"Eres el asistente que levanta la minuta de una reunión de trabajo de una empresa mexicana\n",
   "        raise ErrorMinuta(f\"Gemini respondió con error ({r.status_code}): {r.text[:300]}\")\n\n\ndef _generar(cuerpo, key):\n    \"\"\"generateContent probando modelos hasta dar con uno vigente.\"\"\"\n    global _modelo_bueno\n    pendientes = ([_modelo_bueno] if _modelo_bueno else []) + [m for m in MODELOS if m != _modelo_bueno]\n    probados = []\n    r = None\n    while pendientes:\n        modelo = pendientes.pop(0)\n        if modelo in probados:\n            continue\n        probados.append(modelo)\n        r = requests.post(f\"{API}/v1beta/models/{modelo}:generateContent\",\n                          headers={\"x-goog-api-key\": key, \"content-type\": \"application/json\"},\n                          json=cuerpo, timeout=900)\n        if r.status_code == 404 or (r.status_code == 400 and \"model\" in r.text.lower() and \"not\" in r.text.lower()):\n            # \"This model ... is no longer available ... use models/gemini-X-flash\"\n            sugerido = re.findall(r\"models/([A-Za-z0-9.\\-]+)\", r.text)\n            for m in reversed([x for x in sugerido if x != modelo]):\n                if m not in probados:\n                    pendientes.insert(0, m)\n            print(f\"[minuta] modelo {modelo} no disponible ({r.status_code}); probando otro\")\n            continue\n        _revisar(r)\n        _modelo_bueno = modelo\n        return r\n    raise ErrorMinuta(\"Ningún modelo de Gemini respondió (\" + \", \".join(probados) + \"). \"\n                      \"Pon el nombre de un modelo vigente en la variable GEMINI_MODELO_MINUTA de Render. \"\n                      + (r.text[:200] if r is not None else \"\"))\n\n\ndef _prompt(participantes, contexto, hoy):\n    lista = \"\\n\".join(f\"- {p['nombre']}\" + (f\" ({p['puesto']})\" if p.get(\"puesto\") else \"\") for p in participantes) or \"- (no se indicaron)\"\n    return f\"\"\"Eres el asistente que levanta la minuta de una reunión de trabajo de una empresa mexicana\n"
  ],
  [
   "            ]}],\n            \"generationConfig\": {\"responseMimeType\": \"application/json\", \"temperature\": 0.2},\n        }\n        r = requests.post(f\"{API}/v1beta/models/{MODELO}:generateContent\", headers={\"x-goog-api-key\": key,\n                          \"content-type\": \"application/json\"}, json=cuerpo, timeout=900)\n        _revisar(r)\n        cands = r.json().get(\"candidates\") or []\n        if not cands:\n            raise ErrorMinuta(\"Gemini no regresó respuesta (puede que el audio haya sido bloqueado por sus filtros).\")\n",
   "            ]}],\n            \"generationConfig\": {\"responseMimeType\": \"application/json\", \"temperature\": 0.2},\n        }\n        r = _generar(cuerpo, key)\n        cands = r.json().get(\"candidates\") or []\n        if not cands:\n            raise ErrorMinuta(\"Gemini no regresó respuesta (puede que el audio haya sido bloqueado por sus filtros).\")\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_minuta_modelo_gemini.py")
        sys.exit(1)
    errores = []
    if not os.path.exists("backend/minuta_ia.py"):
            print("Primero corre fix_proyectos_minuta_reunion.py (y los anteriores), y luego este.")
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
            errores.append("No encontre {} -- corre el script desde la carpeta del repo.".format(ruta))
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
                errores.append("{}: cambio #{} -- el texto a reemplazar aparece {} veces (se esperaba 1).".format(ruta, i, n))
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
