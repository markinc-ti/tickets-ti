# -*- coding: utf-8 -*-
"""
RH: LAS HORAS QUE DEBE LA GENTE (para la encargada, en la web y en las apps)
- Al aprobar un permiso POR HORAS de cualquier tipo (no solo "dia libre sin
  goce") se anota el adeudo de esas horas. Antes la encargada veia en
  "Mi gente": "Nadie de tu sucursal debe horas".
- "Marcar como pagada" (la empresa cubre esas horas) sigue sin generar adeudo.
- Al arrancar el servidor, UNA SOLA VEZ, se anotan los permisos por horas que ya
  estaban aprobados y no tenian su adeudo (en el log sale cuantos fueron).
Toca: backend/db.py
Se puede correr varias veces.  Correr con:  py -3 fix_horas_permisos_adeudo.py
"""
import base64
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    cur.close()\n    conn.close()\n    try:\n        corregir_horas_negativas()\n    except Exception as e:\n        print(f\"[horas] no se pudieron corregir negativos: {e}\")\n\n\ndef corregir_horas_negativas():\n",
   "    cur.close()\n    conn.close()\n    try:\n        anotar_horas_permisos_ya_aprobados()\n    except Exception as e:\n        print(f\"[horas] no se pudieron anotar los permisos por horas anteriores: {e}\")\n    try:\n        corregir_horas_negativas()\n    except Exception as e:\n        print(f\"[horas] no se pudieron corregir negativos: {e}\")\n\n\ndef anotar_horas_permisos_ya_aprobados():\n    \"\"\"UNA SOLA VEZ por empresa (marca empresas.horas_permisos_anotados): los\n    permisos por horas que ya estaban aprobados antes del cambio y nunca\n    generaron su adeudo (solo lo hacía el \"día libre sin goce\") se anotan\n    ahora, para que la encargada vea lo que de verdad le debe su gente. No\n    toca los que ya tienen un movimiento ligado ni las conversiones\n    automáticas. Después ya no vuelve a correr (si RH borra uno a mano, no\n    reaparece).\"\"\"\n    conn = get_connection()\n    cur = conn.cursor()\n    cur.execute(\"ALTER TABLE empresas ADD COLUMN IF NOT EXISTS horas_permisos_anotados BOOLEAN NOT NULL DEFAULT FALSE\")\n    conn.commit()\n    cur.execute(\"SELECT id FROM empresas WHERE horas_permisos_anotados = FALSE\")\n    empresas = [r[\"id\"] for r in cur.fetchall()]\n    total = 0\n    for empresa_id in empresas:\n        cur.execute(\"\"\"\n            SELECT i.id, i.usuario_id, i.horas, i.fecha_inicio, i.resuelto_por_id\n            FROM incidencias_rh i\n            WHERE i.empresa_id = %s AND i.estado = 'aprobada' AND COALESCE(i.horas, 0) > 0\n              AND COALESCE(i.motivo, '') NOT LIKE 'Generado automáticamente%%'\n              AND NOT EXISTS (SELECT 1 FROM horas_rh_movimientos m WHERE m.incidencia_id = i.id)\n        \"\"\", (empresa_id,))\n        pendientes = [dict(r) for r in cur.fetchall()]\n        now = ahora().isoformat(timespec=\"seconds\")\n        for i in pendientes:\n            cur.execute(\n                \"\"\"INSERT INTO horas_rh_movimientos (empresa_id, usuario_id, incidencia_id, tipo, horas, notas,\n                                                       registrado_por_id, creado_en, estado, fecha)\n                   VALUES (%s, %s, %s, 'debe', %s, %s, %s, %s, 'aprobado', %s)\"\"\",\n                (empresa_id, i[\"usuario_id\"], i[\"id\"], i[\"horas\"],\n                 f\"Permiso por horas #{i['id']} aprobado antes del cambio: se anota el adeudo que faltaba.\",\n                 i.get(\"resuelto_por_id\"), now, (i.get(\"fecha_inicio\") or now)[:10]),\n            )\n        total += len(pendientes)\n        cur.execute(\"UPDATE empresas SET horas_permisos_anotados = TRUE WHERE id = %s\", (empresa_id,))\n        conn.commit()\n    # Las empresas nuevas ya nacen con el comportamiento nuevo: no hay nada que anotar.\n    cur.execute(\"ALTER TABLE empresas ALTER COLUMN horas_permisos_anotados SET DEFAULT TRUE\")\n    conn.commit()\n    cur.close(); conn.close()\n    if total:\n        print(f\"[horas] permisos por horas ya aprobados anotados como adeudo: {total}\")\n\n\ndef corregir_horas_negativas():\n"
  ],
  [
   "    sin pasar por RH).\"\"\"\n    incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)\n    es_conversion_automatica = incidencia and incidencia.get(\"motivo\") and incidencia[\"motivo\"].startswith(\"Generado automáticamente\")\n    if incidencia and incidencia[\"tipo\"] == \"dia_libre_sin_goce\" and incidencia.get(\"horas\"):\n        if es_conversion_automatica:\n            # Este NO es un permiso pedido de más — es la conversión de horas\n            # que YA debía, que el propio empleado aceptó. Aquí se registra\n",
   "    sin pasar por RH).\"\"\"\n    incidencia = obtener_incidencia_rh(empresa_id, incidencia_id)\n    es_conversion_automatica = incidencia and incidencia.get(\"motivo\") and incidencia[\"motivo\"].startswith(\"Generado automáticamente\")\n    # Cualquier permiso POR HORAS aprobado (no solo el día sin goce) genera el\n    # adeudo de esas horas -- David lo pidió así (19 oct 2026): antes un\n    # permiso \"Otro\" por horas se aprobaba sin anotar nada y la encargada no\n    # veía cuánto le debía su gente. Si la empresa cubre esas horas, RH lo\n    # marca como \"pagada\" (ese estado no pasa por aquí).\n    if incidencia and incidencia.get(\"horas\") and float(incidencia[\"horas\"]) > 0:\n        if es_conversion_automatica:\n            # Este NO es un permiso pedido de más — es la conversión de horas\n            # que YA debía, que el propio empleado aceptó. Aquí se registra\n"
  ]
 ]
}

NUEVOS = {}

NUEVOS_BIN = {}


def main():
    if sys.version_info < (3, 0):
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_horas_permisos_adeudo.py")
        sys.exit(1)
    errores = []
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
