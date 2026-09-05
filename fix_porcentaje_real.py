# -*- coding: utf-8 -*-
"""
Top descuentos: en vez de calcular nosotros el % (que no coincidia exacto
con el numero real de Microsip), ahora se usa DOCTOS_PV.DSCTO_PCTJE -- el
porcentaje que Microsip ya trae guardado en el documento.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_porcentaje_real.py
"""
import sys

ARCHIVOS = {'backend/microsip.py': [['    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(c.NOMBRE, \'Público en general\'),\n               p.FOLIO, p.FECHA, p.HORA, (d.DSCTO_ART + d.DSCTO_EXTRA), d.PRECIO_TOTAL_NETO\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN CLIENTES c ON c.CLIENTE_ID = p.CLIENTE_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\' AND (d.DSCTO_ART + d.DSCTO_EXTRA) > 0\n        ORDER BY (d.DSCTO_ART + d.DSCTO_EXTRA) DESC\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    # Como la consulta ya viene ordenada de mayor a menor descuento, ir\n    # repartiendo cada fila en su sucursal y cortar en 50 mantiene el orden\n    # correcto dentro de cada sucursal sin tener que reordenar después.\n    por_sucursal_desc = {}\n    for sucursal_id, cliente, folio, fecha, hora, descuento, monto in filas:\n        lista = por_sucursal_desc.setdefault(sucursal_id, [])\n        if len(lista) >= 50:\n            continue\n        lista.append({\n            "cliente": (cliente or "Público en general").strip(),\n            "folio": folio,\n            "fecha": str(fecha)[:10] if fecha else None,\n            "hora": str(hora)[:8] if hora else None,\n            "descuento": float(descuento or 0),\n            "monto": float(monto or 0),\n        })', '    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(c.NOMBRE, \'Público en general\'),\n               p.FOLIO, p.FECHA, p.HORA, (d.DSCTO_ART + d.DSCTO_EXTRA), d.PRECIO_TOTAL_NETO, p.DSCTO_PCTJE\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN CLIENTES c ON c.CLIENTE_ID = p.CLIENTE_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\' AND (d.DSCTO_ART + d.DSCTO_EXTRA) > 0\n        ORDER BY (d.DSCTO_ART + d.DSCTO_EXTRA) DESC\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    # Como la consulta ya viene ordenada de mayor a menor descuento, ir\n    # repartiendo cada fila en su sucursal y cortar en 50 mantiene el orden\n    # correcto dentro de cada sucursal sin tener que reordenar después.\n    por_sucursal_desc = {}\n    for sucursal_id, cliente, folio, fecha, hora, descuento, monto, pctje_docto in filas:\n        lista = por_sucursal_desc.setdefault(sucursal_id, [])\n        if len(lista) >= 50:\n            continue\n        lista.append({\n            "cliente": (cliente or "Público en general").strip(),\n            "folio": folio,\n            "fecha": str(fecha)[:10] if fecha else None,\n            "hora": str(hora)[:8] if hora else None,\n            "descuento": float(descuento or 0),\n            "monto": float(monto or 0),\n            # Porcentaje real del documento en Microsip (no uno calculado\n            # por nosotros) — es el mismo % para todas las líneas de un\n            # mismo ticket, porque el descuento se aplica a nivel documento.\n            "porcentaje": float(pctje_docto or 0),\n        })']], 'frontend/index.html': [["              <td>${(v.monto + v.descuento) > 0 ? ((v.descuento / (v.monto + v.descuento)) * 100).toFixed(1) + '%' : '—'}</td>", "              <td>${v.porcentaje ? v.porcentaje.toFixed(1) + '%' : '—'}</td>"]]}


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
    print("   git add backend/microsip.py frontend/index.html")
    print('   git commit -m "Top descuentos: usar el porcentaje real de Microsip"')
    print("   git push")


if __name__ == "__main__":
    main()
