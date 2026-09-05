# -*- coding: utf-8 -*-
"""
Fix importante: los reportes de Punto de Venta (Ventas por sucursal,
Bitacora, Descuentos) estaban contando CADA VENTA DOS VECES. Microsip
genera un documento "espejo" (TIPO_DOCTO distinto, ej. 'V') identico al
ticket real para cada venta, pero marcado con ESTATUS='N' en vez de 'S'.
El filtro anterior (ESTATUS <> 'C', solo excluia cancelados) SI contaba ese
espejo por error. Ahora se filtra ESTATUS = 'S' (solo el documento real).

Tambien se agrega "Monto vendido" al lado de "Descuento total" en el
desglose de Descuentos, como se pidio.

IMPORTANTE: los numeros de Ventas por sucursal, Bitacora y Descuentos que
hayas visto hasta ahora estaban aproximadamente el DOBLE de lo real -- tras
aplicar esto deberian bajar a la mitad (los totales de HOY en las tarjetas
del Dashboard se corrigen la proxima vez que carguen).

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    py fix_estatus_duplicado.py
"""
import sys

ARCHIVOS = {'backend/microsip.py': [["        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV'\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> 'C'", "        JOIN FORMAS_COBRO_DOCTOS fcd ON fcd.DOCTO_ID = p.DOCTO_PV_ID AND fcd.NOM_TABLA_DOCTOS = 'DOCTOS_PV'\n        JOIN FORMAS_COBRO fc ON fc.FORMA_COBRO_ID = fcd.FORMA_COBRO_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'"], ["        SELECT p.FOLIO, p.HORA, COALESCE(s.NOMBRE, 'Sin sucursal'), p.IMPORTE_NETO\n        FROM DOCTOS_PV p\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> 'C'", "        SELECT p.FOLIO, p.HORA, COALESCE(s.NOMBRE, 'Sin sucursal'), p.IMPORTE_NETO\n        FROM DOCTOS_PV p\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = 'S'"], ['def obtener_descuentos_pv(config: dict, fecha_inicio: str, fecha_fin: str):\n    """Descuento total (en dinero) por sucursal entre fecha_inicio (incluida)\n    y fecha_fin (excluida), y los 50 descuentos más altos otorgados en cada\n    una, con el cliente y el monto del ticket."""\n    con = _conectar(config)\n    cur = con.cursor()\n\n    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(s.NOMBRE, \'Sin sucursal\'), SUM(d.DSCTO_ART + d.DSCTO_EXTRA)\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\'\n        GROUP BY p.SUCURSAL_ID, s.NOMBRE\n    """, (fecha_inicio, fecha_fin))\n    totales = {}\n    for sucursal_id, nombre, descuento in cur.fetchall():\n        totales[sucursal_id] = {\n            "sucursal_id": sucursal_id,\n            "sucursal": (nombre or "Sin sucursal").strip(),\n            "descuento_total": float(descuento or 0),\n        }\n\n    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(c.NOMBRE, \'Público en general\'),\n               p.FOLIO, p.FECHA, p.HORA, (d.DSCTO_ART + d.DSCTO_EXTRA), d.PRECIO_TOTAL_NETO\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN CLIENTES c ON c.CLIENTE_ID = p.CLIENTE_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS <> \'C\' AND (d.DSCTO_ART + d.DSCTO_EXTRA) > 0\n        ORDER BY (d.DSCTO_ART + d.DSCTO_EXTRA) DESC\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    # Como la consulta ya viene ordenada de mayor a menor descuento, ir\n    # repartiendo cada fila en su sucursal y cortar en 50 mantiene el orden\n    # correcto dentro de cada sucursal sin tener que reordenar después.\n    por_sucursal_desc = {}\n    for sucursal_id, cliente, folio, fecha, hora, descuento, monto in filas:\n        lista = por_sucursal_desc.setdefault(sucursal_id, [])\n        if len(lista) >= 50:\n            continue\n        lista.append({\n            "cliente": (cliente or "Público en general").strip(),\n            "folio": folio,\n            "fecha": str(fecha)[:10] if fecha else None,\n            "hora": str(hora)[:8] if hora else None,\n            "descuento": float(descuento or 0),\n            "monto": float(monto or 0),\n        })\n\n    resultado = []\n    for sucursal_id, datos in sorted(totales.items(), key=lambda kv: -kv[1]["descuento_total"]):\n        datos = dict(datos)\n        datos["top_descuentos"] = por_sucursal_desc.get(sucursal_id, [])\n        resultado.append(datos)\n\n    total_general = sum(d["descuento_total"] for d in resultado)\n    return {"por_sucursal": resultado, "total_general": total_general}', 'def obtener_descuentos_pv(config: dict, fecha_inicio: str, fecha_fin: str):\n    """Descuento total (en dinero) por sucursal entre fecha_inicio (incluida)\n    y fecha_fin (excluida), y los 50 descuentos más altos otorgados en cada\n    una, con el cliente y el monto del ticket."""\n    con = _conectar(config)\n    cur = con.cursor()\n\n    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(s.NOMBRE, \'Sin sucursal\'), SUM(d.DSCTO_ART + d.DSCTO_EXTRA), SUM(d.PRECIO_TOTAL_NETO)\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN SUCURSALES s ON s.SUCURSAL_ID = p.SUCURSAL_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\'\n        GROUP BY p.SUCURSAL_ID, s.NOMBRE\n    """, (fecha_inicio, fecha_fin))\n    totales = {}\n    for sucursal_id, nombre, descuento, venta_total in cur.fetchall():\n        totales[sucursal_id] = {\n            "sucursal_id": sucursal_id,\n            "sucursal": (nombre or "Sin sucursal").strip(),\n            "descuento_total": float(descuento or 0),\n            "venta_total": float(venta_total or 0),\n        }\n\n    cur.execute("""\n        SELECT p.SUCURSAL_ID, COALESCE(c.NOMBRE, \'Público en general\'),\n               p.FOLIO, p.FECHA, p.HORA, (d.DSCTO_ART + d.DSCTO_EXTRA), d.PRECIO_TOTAL_NETO\n        FROM DOCTOS_PV_DET d\n        JOIN DOCTOS_PV p ON p.DOCTO_PV_ID = d.DOCTO_PV_ID\n        LEFT JOIN CLIENTES c ON c.CLIENTE_ID = p.CLIENTE_ID\n        WHERE p.FECHA >= ? AND p.FECHA < ? AND p.ESTATUS = \'S\' AND (d.DSCTO_ART + d.DSCTO_EXTRA) > 0\n        ORDER BY (d.DSCTO_ART + d.DSCTO_EXTRA) DESC\n    """, (fecha_inicio, fecha_fin))\n    filas = cur.fetchall()\n    con.close()\n\n    # Como la consulta ya viene ordenada de mayor a menor descuento, ir\n    # repartiendo cada fila en su sucursal y cortar en 50 mantiene el orden\n    # correcto dentro de cada sucursal sin tener que reordenar después.\n    por_sucursal_desc = {}\n    for sucursal_id, cliente, folio, fecha, hora, descuento, monto in filas:\n        lista = por_sucursal_desc.setdefault(sucursal_id, [])\n        if len(lista) >= 50:\n            continue\n        lista.append({\n            "cliente": (cliente or "Público en general").strip(),\n            "folio": folio,\n            "fecha": str(fecha)[:10] if fecha else None,\n            "hora": str(hora)[:8] if hora else None,\n            "descuento": float(descuento or 0),\n            "monto": float(monto or 0),\n        })\n\n    resultado = []\n    for sucursal_id, datos in sorted(totales.items(), key=lambda kv: -kv[1]["descuento_total"]):\n        datos = dict(datos)\n        datos["top_descuentos"] = por_sucursal_desc.get(sucursal_id, [])\n        resultado.append(datos)\n\n    total_general = sum(d["descuento_total"] for d in resultado)\n    return {"por_sucursal": resultado, "total_general": total_general}']], 'frontend/index.html': [['      <div style="overflow-x:auto; margin-bottom:20px;">\n        <table class="users">\n          <thead><tr><th>Sucursal</th><th>Descuento total</th></tr></thead>\n          <tbody>\n            ${d.por_sucursal.map(s => `\n              <tr><td>${escapeHtml(s.sucursal)}</td><td>$${s.descuento_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td></tr>\n            `).join(\'\')}\n          </tbody>\n          <tfoot><tr><td><b>Total general</b></td><td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n        </table>\n      </div>', '      <div style="overflow-x:auto; margin-bottom:20px;">\n        <table class="users">\n          <thead><tr><th>Sucursal</th><th>Monto vendido</th><th>Descuento total</th></tr></thead>\n          <tbody>\n            ${d.por_sucursal.map(s => `\n              <tr>\n                <td>${escapeHtml(s.sucursal)}</td>\n                <td>$${s.venta_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n                <td>$${s.descuento_total.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</td>\n              </tr>\n            `).join(\'\')}\n          </tbody>\n          <tfoot><tr><td><b>Total general</b></td><td><b>$${d.por_sucursal.reduce((s, x) => s + x.venta_total, 0).toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td><td><b>$${d.total_general.toLocaleString(\'es-MX\', {minimumFractionDigits:2})}</b></td></tr></tfoot>\n        </table>\n      </div>']]}


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
    print('   git commit -m "Fix: Punto de Venta contaba cada venta 2 veces (documento espejo)"')
    print("   git push")


if __name__ == "__main__":
    main()
