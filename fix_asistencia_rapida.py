# -*- coding: utf-8 -*-
"""
RH -> Asistencia: no quedarse "Cargando" si Microsip no responde.
La consulta de vacaciones de Microsip (para justificar faltas) ahora tiene
maximo 8 segundos; si no contesta, el reporte sale igual con un aviso.

Toca: backend/app.py, frontend/index.html. Se puede correr varias veces.

Uso: en la carpeta del repo:
    py -3 fix_asistencia_rapida.py
"""
import os
import sys

ARCHIVOS = {'backend/app.py': [['# ---- RH: Asistencia (reloj checador ZKTeco / BioTime Pro) ----\n', '# ---- RH: Asistencia (reloj checador ZKTeco / BioTime Pro) ----\n\nfrom concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout\n_POOL_ASISTENCIA = ThreadPoolExecutor(max_workers=2)\n'], ['    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n    # Vacaciones aprobadas en Microsip', '    justificaciones = db.incidencias_justifican_asistencia(empresa_id, desde, hasta)\n    avisos = []\n    # Vacaciones aprobadas en Microsip'], ['            for v in microsip.obtener_vacaciones_multiples_empleados(config, numeros):\n                uid = por_numero.get(asistencia.normalizar_codigo(v.get("numero_empleado")))', '            # Máximo 8 segundos: si Microsip no contesta, el reporte sale igual (sin esas vacaciones).\n            futuro = _POOL_ASISTENCIA.submit(microsip.obtener_vacaciones_multiples_empleados, config, numeros)\n            try:\n                vacaciones = futuro.result(timeout=8)\n            except FuturesTimeout:\n                vacaciones = []\n                avisos.append("Microsip no respondió a tiempo: las vacaciones de Microsip no se tomaron en cuenta como faltas justificadas.")\n            for v in vacaciones:\n                uid = por_numero.get(asistencia.normalizar_codigo(v.get("numero_empleado")))'], ['    except Exception as e:\n        print(f"[asistencia] vacaciones de Microsip no disponibles: {e}")\n    return asistencia.calcular_reporte(', '    except Exception as e:\n        print(f"[asistencia] vacaciones de Microsip no disponibles: {e}")\n        avisos.append("No se pudieron consultar las vacaciones de Microsip.")\n    reporte = asistencia.calcular_reporte('], ['                                       db.primera_checada(empresa_id))\n\n\n@app.post("/api/rh/checadas/sync")', '                                       db.primera_checada(empresa_id))\n    reporte["avisos"] = avisos\n    return reporte\n\n\n@app.post("/api/rh/checadas/sync")']], 'frontend/index.html': [['    <div id="asis_aviso"></div>\n    ${d.codigos_sin_empleado.length ?', '    <div id="asis_aviso"></div>\n    ${(d.avisos || []).map(a => `<div style="font-size:12px; color:#e8a33d; margin-bottom:6px;">⚠️ ${escapeHtml(a)}</div>`).join(\'\')}\n    ${d.codigos_sin_empleado.length ?']]}

NUEVOS = {}


def main():
    errores = []
    cambios = {}
    for ruta, contenido in NUEVOS.items():
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                actual = f.read().replace("\r\n", "\n")
            if actual == contenido:
                continue
        cambios[ruta] = contenido
    for ruta, pares in ARCHIVOS.items():
        if not os.path.exists(ruta):
            errores.append(f"No encontre {ruta} -- corre el script desde la carpeta del repo.")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            original = f.read()
        texto = original
        for i, (viejo, nuevo) in enumerate(pares, 1):
            # En Windows los archivos pueden tener saltos de linea CRLF.
            variantes = [(viejo, nuevo)]
            if "\n" in viejo:
                variantes.append((viejo.replace("\n", "\r\n"), nuevo.replace("\n", "\r\n")))
            if any(nv in texto for _, nv in variantes):
                continue  # ya aplicado
            elegido = None
            for vj, nv in variantes:
                if texto.count(vj) == 1:
                    elegido = (vj, nv)
                    break
            if not elegido:
                n = max(texto.count(vj) for vj, _ in variantes)
                errores.append(f"{ruta}: cambio #{i} -- el texto a reemplazar aparece {n} veces (se esperaba 1).")
                continue
            texto = texto.replace(elegido[0], elegido[1], 1)
        if texto != original:
            cambios[ruta] = texto
    if errores:
        print("NO se aplico nada:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    for ruta, texto in cambios.items():
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
        print("Actualizado:", ruta)
    if not cambios:
        print("Todo ya estaba aplicado, no hubo cambios.")
    else:
        print("Listo.")


if __name__ == "__main__":
    main()
