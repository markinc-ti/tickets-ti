# -*- coding: utf-8 -*-
"""
Uso de base de datos por empresa (estimado) -- panel de Superadmin

Nuevo botón "📊 Uso de BD" en el panel de Superadmin (junto a "💰
Consumo"), que muestra, por cada empresa: cuántos registros tiene en
total y qué tanto pesa (ESTIMADO) dentro de tu base de datos
compartida de Neon, con un desglose por tabla si le das "ver detalle".

Cómo lo calcula: Neon (o cualquier Postgres) no separa el consumo por
empresa -- todas viven en la misma base. Por cada tabla que tenga una
columna empresa_id (esto lo detecta automático, no hay que mantener
una lista a mano -- si mañana agregas un módulo nuevo con su propia
tabla, ya sale solo), se reparte el tamaño real de esa tabla
proporcional a cuántas filas le tocan a cada empresa, y se suman todas
las tablas. Es un estimado razonable para comparar quién pesa más, NO
una factura exacta -- para eso hay que ver la consola de Neon
(por eso el aviso dentro del panel).

Qué toca:
  - backend/db.py -- función resumen_uso_db_por_empresa().
  - backend/app.py -- endpoint GET /api/superadmin/uso-db (solo
    superadmin).
  - frontend/index.html -- botón nuevo en el panel de Superadmin +
    la pantalla que lo muestra.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:
    py fix_uso_db_por_empresa.py
"""
import os
import sys

ARCHIVOS = {
    'backend/db.py': [
        [
            '\nimport psycopg2\nimport psycopg2.extras\n\nimport auth\nimport geo\n',
            '\nimport psycopg2\nimport psycopg2.extras\nimport psycopg2.sql\n\nimport auth\nimport geo\n',
        ],
        [
            '    return list(por_empresa.values())\n\n\n# ---- Cotizador interno de costos por empresa (Superadmin > Costos y renta) ----\n\ndef obtener_costos_empresa(empresa_id):\n',
            '    return list(por_empresa.values())\n\n\n# ---- Uso de la base de datos por empresa (estimado, Superadmin) ----\n\ndef resumen_uso_db_por_empresa():\n    """Para el panel de Superadmin: cuántos registros tiene cada empresa\n    y qué tanto pesa (ESTIMADO) dentro de la base de datos compartida.\n\n    No es un número exacto -- Neon (o cualquier Postgres) no separa el\n    consumo por empresa, todas viven en la misma base. Lo que hacemos:\n    por cada tabla que tenga una columna empresa_id, repartimos el\n    tamaño real de esa tabla (pg_total_relation_size, ya incluye\n    índices) proporcional a cuántas filas le tocan a cada empresa, y\n    sumamos todas las tablas. Es un estimado razonable para comparar\n    quién pesa más, no una factura exacta -- para eso hay que ver la\n    consola de Neon."""\n    conn = get_connection()\n    cur = conn.cursor()\n\n    cur.execute("SELECT id, nombre FROM empresas ORDER BY nombre")\n    empresas = {\n        r["id"]: {\n            "empresa_id": r["id"],\n            "empresa_nombre": r["nombre"],\n            "total_registros": 0,\n            "espacio_estimado_bytes": 0,\n            "detalle_por_tabla": {},\n        }\n        for r in cur.fetchall()\n    }\n\n    cur.execute("""\n        SELECT DISTINCT c.table_name\n        FROM information_schema.columns c\n        JOIN information_schema.tables t\n          ON t.table_name = c.table_name AND t.table_schema = c.table_schema\n        WHERE c.table_schema = \'public\' AND c.column_name = \'empresa_id\'\n          AND t.table_type = \'BASE TABLE\'\n        ORDER BY c.table_name\n    """)\n    tablas = [r["table_name"] for r in cur.fetchall()]\n\n    cur.execute("SELECT pg_database_size(current_database()) AS total")\n    total_bd_bytes = cur.fetchone()["total"] or 0\n\n    for tabla in tablas:\n        cur.execute(\n            psycopg2.sql.SQL(\n                "SELECT empresa_id, COUNT(*) AS n FROM {} WHERE empresa_id IS NOT NULL GROUP BY empresa_id"\n            ).format(psycopg2.sql.Identifier(tabla))\n        )\n        conteos = {r["empresa_id"]: r["n"] for r in cur.fetchall()}\n        if not conteos:\n            continue\n        total_tabla_filas = sum(conteos.values())\n        cur.execute("SELECT pg_total_relation_size(%s) AS bytes", (tabla,))\n        tabla_bytes = cur.fetchone()["bytes"] or 0\n        for empresa_id, n in conteos.items():\n            if empresa_id not in empresas:\n                continue  # empresa ya no existe -- no la mostramos\n            empresas[empresa_id]["total_registros"] += n\n            empresas[empresa_id]["espacio_estimado_bytes"] += tabla_bytes * (n / total_tabla_filas)\n            empresas[empresa_id]["detalle_por_tabla"][tabla] = n\n\n    cur.close(); conn.close()\n\n    resultado = []\n    for emp in empresas.values():\n        emp["espacio_estimado_mb"] = round(emp["espacio_estimado_bytes"] / (1024 * 1024), 2)\n        emp["porcentaje_bd"] = round((emp["espacio_estimado_bytes"] / total_bd_bytes * 100), 2) if total_bd_bytes else 0\n        del emp["espacio_estimado_bytes"]\n        resultado.append(emp)\n    resultado.sort(key=lambda e: e["total_registros"], reverse=True)\n\n    return {"total_bd_mb": round(total_bd_bytes / (1024 * 1024), 2), "empresas": resultado}\n\n\n# ---- Cotizador interno de costos por empresa (Superadmin > Costos y renta) ----\n\ndef obtener_costos_empresa(empresa_id):\n',
        ],
    ],
    'backend/app.py': [
        [
            '    chatbot de WhatsApp) y de WhatsApp (notificaciones, difusiones) por\n    empresa — para que puedas cobrar/controlar el gasto de cada una."""\n    return db.resumen_consumo_por_empresa(fecha_desde, fecha_hasta)\n\n\nclass CostosEmpresaIn(BaseModel):\n',
            '    chatbot de WhatsApp) y de WhatsApp (notificaciones, difusiones) por\n    empresa — para que puedas cobrar/controlar el gasto de cada una."""\n    return db.resumen_consumo_por_empresa(fecha_desde, fecha_hasta)\n\n\n@app.get("/api/superadmin/uso-db")\ndef obtener_uso_db_superadmin(_: dict = Depends(requiere_superadmin)):\n    """Cuántos registros tiene cada empresa y qué tanto pesa (ESTIMADO)\n    dentro de la base de datos compartida -- para ver quién usa más\n    espacio. No es exacto (Neon no separa el consumo por empresa)."""\n    return db.resumen_uso_db_por_empresa()\n\n\nclass CostosEmpresaIn(BaseModel):\n',
        ],
    ],
    'frontend/index.html': [
        [
            '      <div class="whoami" id="whoamiSuper"></div>\n      <button class="secondary" onclick="abrirMiCuenta()">Mi cuenta</button>\n      <button class="secondary" onclick="abrirConsumoSuperadmin()">💰 Consumo</button>\n      <button class="secondary" onclick="abrirCotizadorSuperadmin()">🧾 Cotizador</button>\n      <button class="primary" onclick="abrirCrearEmpresa()">+ NUEVA EMPRESA</button>\n      <button class="secondary" onclick="cerrarSesionConConfirmacion()">Salir</button>\n',
            '      <div class="whoami" id="whoamiSuper"></div>\n      <button class="secondary" onclick="abrirMiCuenta()">Mi cuenta</button>\n      <button class="secondary" onclick="abrirConsumoSuperadmin()">💰 Consumo</button>\n      <button class="secondary" onclick="abrirUsoDBSuperadmin()">📊 Uso de BD</button>\n      <button class="secondary" onclick="abrirCotizadorSuperadmin()">🧾 Cotizador</button>\n      <button class="primary" onclick="abrirCrearEmpresa()">+ NUEVA EMPRESA</button>\n      <button class="secondary" onclick="cerrarSesionConConfirmacion()">Salir</button>\n',
        ],
        [
            '  `;\n}\n\n// ==================================================================\n// ---- Cotizador interno de costos por empresa (Superadmin) ----\n// La edición vive en su propia página (mismo diseño que el cotizador\n',
            '  `;\n}\n\nasync function abrirUsoDBSuperadmin() {\n  document.getElementById(\'modalContent\').innerHTML = `<button class="close-btn" onclick="cerrarModal()">cerrar</button><h2>📊 Uso de base de datos por empresa</h2><p style="color:var(--muted);">Cargando…</p>`;\n  abrirModal(true);\n  await renderUsoDBSuperadmin();\n}\n\nasync function renderUsoDBSuperadmin() {\n  const datos = await api(\'/api/superadmin/uso-db\');\n  document.getElementById(\'modalContent\').innerHTML = `\n    <button class="close-btn" onclick="cerrarModal()">cerrar</button>\n    <h2>📊 Uso de base de datos por empresa</h2>\n    <p style="font-size:12px; color:var(--muted);">\n      Estimado, no exacto -- tu base de datos (Neon) no separa el consumo por empresa, todas comparten la misma base.\n      Repartimos el tamaño real de cada tabla según cuántos registros le tocan a cada empresa. Para la factura exacta, revisa la consola de Neon.\n      Base de datos total: <b>${datos.total_bd_mb.toLocaleString(\'es-MX\')} MB</b>.\n    </p>\n    <table class="users" style="margin-top:8px;">\n      <thead><tr><th>Empresa</th><th>Registros</th><th>Espacio estimado</th><th>% de la BD</th><th></th></tr></thead>\n      <tbody>\n        ${datos.empresas.map((e, i) => `\n          <tr>\n            <td>${escapeHtml(e.empresa_nombre)}</td>\n            <td>${e.total_registros.toLocaleString(\'es-MX\')}</td>\n            <td>${e.espacio_estimado_mb.toLocaleString(\'es-MX\')} MB</td>\n            <td>${e.porcentaje_bd}%</td>\n            <td><button class="secondary" style="padding:2px 8px; font-size:11px;" onclick="toggleDetalleUsoDB(${i})">ver detalle</button></td>\n          </tr>\n          <tr id="detalleUsoDB_${i}" style="display:none;">\n            <td colspan="5">\n              <table class="users">\n                <thead><tr><th>Tabla</th><th>Registros</th></tr></thead>\n                <tbody>\n                  ${Object.entries(e.detalle_por_tabla).sort((a, b) => b[1] - a[1]).map(([tabla, n]) => `\n                    <tr><td>${escapeHtml(tabla)}</td><td>${n.toLocaleString(\'es-MX\')}</td></tr>\n                  `).join(\'\')}\n                </tbody>\n              </table>\n            </td>\n          </tr>\n        `).join(\'\')}\n      </tbody>\n    </table>\n  `;\n}\n\nfunction toggleDetalleUsoDB(i) {\n  const fila = document.getElementById(`detalleUsoDB_${i}`);\n  fila.style.display = fila.style.display === \'none\' ? \'\' : \'none\';\n}\n\n// ==================================================================\n// ---- Cotizador interno de costos por empresa (Superadmin) ----\n// La edición vive en su propia página (mismo diseño que el cotizador\n',
        ],
    ],
}


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
            print(f"[{ruta}] NO ENCONTRADO -- asegurate de correr este script desde la raiz del repo (junto a backend/ y frontend/).")
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
                print(f"[{ruta}] No se encontro un bloque esperado. El archivo pudo haber cambiado desde la ultima vez.")
                hubo_error = True
        escribir(ruta, contenido)
        print(f"[{ruta}] {cambios}/{len(cambios_lista)} cambio(s) aplicado(s).")
        hubo_error_total = hubo_error_total or hubo_error

    if hubo_error_total:
        print()
        print("Algo no se pudo aplicar automaticamente. Avisale a Claude que mensaje salio, sin correr git add/commit todavia.")
        sys.exit(1)

    print()
    print("Todo listo. Ahora corre:")
    archivos_git = list(ARCHIVOS.keys())
    print("   git add " + " ".join(archivos_git))
    print('   git commit -m "Uso de base de datos por empresa (estimado) en panel de Superadmin"')
    print("   git push")


if __name__ == "__main__":
    main()
