"""Vacaciones en Microsip Nómina: registrar las que RH aprueba en la app.

Microsip guarda:
  - PERIODOS_VAC: un renglón por año de antigüedad (DIAS_CALC otorgados,
    DIAS lo que queda disponible, FECHA_CADUCIDAD).
  - VACACIONES: cada vacación tomada (EMPLEADO_ID, FECHA_INICIAL, DIAS,
    DESCRIPCION, ESTATUS, …).

No tenemos la documentación de la base de Microsip, así que se escribe igual
que microsip_escritura: columnas leídas del catálogo de Firebird, las
obligatorias desconocidas se copian del último registro de VACACIONES, y
todo en una transacción. Si Microsip no descuenta solo los días del periodo
(con un trigger), se descuentan aquí del periodo vigente más antiguo, como
hace Microsip. El diagnóstico hace una prueba completa y la deshace.
"""
from datetime import date, timedelta

import microsip
import microsip_escritura as mse

fdb = mse.fdb


def _hoy():
    return mse._ahora().date()


def _a_fecha(v):
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _empleado(esq, numero):
    return esq.fila("SELECT FIRST 1 EMPLEADO_ID, NUMERO, NOMBRE_COMPLETO FROM EMPLEADOS WHERE NUMERO = ?",
                    (str(numero).strip(),))


def _periodos(esq, empleado_id):
    esq.cur.execute("""SELECT * FROM PERIODOS_VAC WHERE EMPLEADO_ID = ? ORDER BY FECHA_INICIAL""", (empleado_id,))
    nombres = [d[0].strip() for d in esq.cur.description]
    return [dict(zip(nombres, r)) for r in esq.cur.fetchall()]


def _id_periodo(p):
    for k in ("PERIODO_VAC_ID", "PERIODO_ID", "ID"):
        if k in p:
            return k
    return next(iter(p))


def _vigentes(periodos, hoy):
    """Periodos con días y sin caducar, del más viejo al más nuevo."""
    r = []
    for p in periodos:
        disp = float(p.get("DIAS") or 0)
        cad = p.get("FECHA_CADUCIDAD")
        if disp > 0 and (not cad or _a_fecha(cad) >= hoy):
            r.append(p)
    return r


def _estatus_frecuentes(esq):
    if "ESTATUS" not in esq.columnas("VACACIONES"):
        return []
    esq.cur.execute("SELECT ESTATUS, COUNT(*) FROM VACACIONES GROUP BY ESTATUS ORDER BY 2 DESC")
    return [((e or "").strip(), int(n)) for e, n in esq.cur.fetchall()]


def _fecha_final(inicio, dias, dias_descanso=(6,)):
    """Último día de vacaciones contando solo días laborables (por defecto
    se brinca el domingo). dias puede traer medio día."""
    n = max(int(round(float(dias) + 0.49)), 1)
    d = inicio
    contados = 0
    while True:
        if d.weekday() not in dias_descanso:
            contados += 1
            if contados >= n:
                return d
        d += timedelta(days=1)


def _registrar(esq, empleado_id, fecha_inicio, dias, descripcion, estatus=None, avisos=None):
    avisos = avisos if avisos is not None else []
    cols = esq.columnas("VACACIONES")
    if not cols:
        raise mse.ErrorMicrosip("Vacaciones", "no existe la tabla VACACIONES en esta base de Microsip")
    inicio = _a_fecha(fecha_inicio)
    hoy = _hoy()
    periodos = _periodos(esq, empleado_id)
    vigentes = _vigentes(periodos, inicio if inicio > hoy else hoy)
    disponibles = sum(float(p.get("DIAS") or 0) for p in vigentes)
    if float(dias) > disponibles + 1e-6:
        raise mse.ErrorMicrosip("Vacaciones", f"en Microsip solo tiene {disponibles:g} día(s) disponible(s) y se pidieron {float(dias):g}")
    antes = {(_id_periodo(p), p[_id_periodo(p)]): float(p.get("DIAS") or 0) for p in periodos}

    plantilla = esq.fila("SELECT FIRST 1 * FROM VACACIONES ORDER BY FECHA_INICIAL DESC") or {}
    id_col = next((c for c in ("VACACION_ID", "VACACIONES_ID", "VAC_ID") if c in cols), None)
    valores = {"EMPLEADO_ID": empleado_id, "FECHA_INICIAL": inicio, "DIAS": float(dias),
               "DESCRIPCION": mse._txt(descripcion, 200)}
    if "ESTATUS" in cols:
        valores["ESTATUS"] = estatus or (plantilla.get("ESTATUS") or "").strip() or None
    fin = _fecha_final(inicio, dias)
    for c in ("FECHA_FINAL", "FECHA_FIN"):
        if c in cols:
            valores[c] = fin
    for c in ("FECHA_REGRESO", "FECHA_REINGRESO"):
        if c in cols:
            valores[c] = _fecha_final(fin + timedelta(days=1), 1)
    per_col = next((c for c in ("PERIODO_VAC_ID", "PERIODO_ID") if c in cols), None)
    if per_col and vigentes:
        valores[per_col] = vigentes[0][_id_periodo(vigentes[0])]
    for c, v in (("USUARIO_CREADOR", esq.usuario), ("USUARIO_ULT_MODIF", esq.usuario),
                 ("FECHA_HORA_CREACION", mse._ahora()), ("FECHA_HORA_ULT_MODIF", mse._ahora())):
        if c in cols:
            valores[c] = v
    try:
        vac_id = mse._insertar(esq, "VACACIONES", valores, plantilla, (), id_col, "ID_DOCTOS")
    except fdb.DatabaseError as e:
        raise mse.ErrorMicrosip("Vacaciones (alta)", mse._error_fb(e))

    # ¿Microsip descontó solo (trigger)? Si no, se descuenta aquí, del periodo
    # vigente más viejo al más nuevo.
    despues = {(_id_periodo(p), p[_id_periodo(p)]): float(p.get("DIAS") or 0) for p in _periodos(esq, empleado_id)}
    descontado = sum(antes[k] - despues.get(k, antes[k]) for k in antes)
    manual = False
    if descontado < float(dias) - 1e-6:
        manual = True
        faltan = float(dias) - max(descontado, 0)
        for p in vigentes:
            if faltan <= 0:
                break
            k = (_id_periodo(p), p[_id_periodo(p)])
            disp = despues.get(k, float(p.get("DIAS") or 0))
            usar = min(disp, faltan)
            if usar > 0:
                try:
                    mse._actualizar(esq, "PERIODOS_VAC", k[0], k[1], {"DIAS": round(disp - usar, 4)})
                except fdb.DatabaseError as e:
                    raise mse.ErrorMicrosip("Vacaciones (descontar del periodo)", mse._error_fb(e))
                faltan -= usar
    return {"vacacion_id": vac_id, "fecha_final": fin.isoformat(), "descontado_por_microsip": not manual,
            "disponibles_antes": disponibles, "disponibles_despues": round(disponibles - float(dias), 4), "avisos": avisos}


def registrar_vacacion(config, *, numero_empleado, fecha_inicio, dias, descripcion, estatus=None, usuario=None, probar=False):
    con = mse._conectar(config)
    try:
        esq = mse._Esquema(con.cursor(), usuario)
        emp = _empleado(esq, numero_empleado)
        if not emp:
            raise mse.ErrorMicrosip("Empleado", f"no existe el empleado número {numero_empleado} en Microsip")
        r = _registrar(esq, emp["EMPLEADO_ID"], fecha_inicio, dias, descripcion, estatus)
        if probar:
            con.rollback()
        else:
            con.commit()
        r.update(empleado=(emp.get("NOMBRE_COMPLETO") or "").strip(), probado=probar)
        return r
    except fdb.DatabaseError as e:
        con.rollback()
        raise mse.ErrorMicrosip("Microsip", mse._error_fb(e))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def cancelar_vacacion(config, *, numero_empleado, vacacion_id, dias, usuario=None):
    """Borra de Microsip una vacación que se registró desde la app y regresa
    los días al saldo. Si Microsip los regresa solo (trigger), no se toca
    nada más; si no, se regresan aquí a los periodos vigentes al revés de como
    se descontaron (del más nuevo al más viejo), sin pasar lo que cada periodo
    otorgó (DIAS_CALC)."""
    con = mse._conectar(config)
    try:
        esq = mse._Esquema(con.cursor(), usuario)
        cols = esq.columnas("VACACIONES")
        id_col = next((c for c in ("VACACION_ID", "VACACIONES_ID", "VAC_ID") if c in cols), None)
        if not id_col:
            raise mse.ErrorMicrosip("Vacaciones", "no encontré la columna de folio de VACACIONES")
        fila = esq.fila(f"SELECT FIRST 1 * FROM VACACIONES WHERE {id_col} = ?", (vacacion_id,))
        if not fila:
            raise mse.ErrorMicrosip("Vacaciones", f"la vacación {vacacion_id} ya no existe en Microsip (¿la borraron allá?)")
        empleado_id = fila["EMPLEADO_ID"]
        emp = _empleado(esq, numero_empleado) if numero_empleado else None
        if emp and emp["EMPLEADO_ID"] != empleado_id:
            raise mse.ErrorMicrosip("Vacaciones", "esa vacación de Microsip es de otro empleado; no se tocó")
        antes = {(_id_periodo(p), p[_id_periodo(p)]): float(p.get("DIAS") or 0) for p in _periodos(esq, empleado_id)}
        try:
            esq.cur.execute(f"DELETE FROM VACACIONES WHERE {id_col} = ?", (vacacion_id,))
        except fdb.DatabaseError as e:
            raise mse.ErrorMicrosip("Vacaciones (borrar)", mse._error_fb(e))
        periodos = _periodos(esq, empleado_id)
        despues = {(_id_periodo(p), p[_id_periodo(p)]): float(p.get("DIAS") or 0) for p in periodos}
        regresado = sum(despues.get(k, v) - v for k, v in antes.items())
        manual = 0.0
        faltan = float(dias) - max(regresado, 0)
        if faltan > 1e-6:
            hoy = _hoy()
            vigentes = [p for p in periodos if not p.get("FECHA_CADUCIDAD") or _a_fecha(p["FECHA_CADUCIDAD"]) >= hoy]
            if not vigentes:
                vigentes = periodos[-1:]
            vigentes = list(reversed(vigentes))
            for i, p in enumerate(vigentes):
                if faltan <= 1e-6:
                    break
                k = (_id_periodo(p), p[_id_periodo(p)])
                disp = despues.get(k, float(p.get("DIAS") or 0))
                tope = float(p["DIAS_CALC"]) if p.get("DIAS_CALC") is not None else None
                cabe = faltan if tope is None or i == len(vigentes) - 1 else max(min(faltan, tope - disp), 0)
                if cabe > 0:
                    try:
                        mse._actualizar(esq, "PERIODOS_VAC", k[0], k[1], {"DIAS": round(disp + cabe, 4)})
                    except fdb.DatabaseError as e:
                        raise mse.ErrorMicrosip("Vacaciones (regresar días al periodo)", mse._error_fb(e))
                    faltan -= cabe
                    manual += cabe
        con.commit()
        return {"borrada": vacacion_id, "regresados_por_microsip": round(max(regresado, 0), 4), "regresados_por_app": round(manual, 4)}
    except fdb.DatabaseError as e:
        con.rollback()
        raise mse.ErrorMicrosip("Microsip", mse._error_fb(e))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def diagnostico(config, numero_empleado=None, estatus=None):
    """Muestra cómo guarda Microsip las vacaciones (columnas, triggers,
    estatus usados, últimos registros) y, si se da un número de empleado con
    días, hace un alta de prueba de 1 día y la DESHACE."""
    r = {"pasos": [], "ok": False, "estatus_usados": [], "columnas": [], "ultimos": []}

    def paso(nombre, ok, detalle=""):
        r["pasos"].append({"paso": nombre, "ok": ok, "detalle": detalle})
        return ok

    try:
        con = mse._conectar(config)
    except Exception as e:
        paso("Conectar con el usuario de escritura", False, mse._error_fb(e) if isinstance(e, fdb.DatabaseError) else str(e))
        return r
    paso("Conectar con el usuario de escritura", True, config.get("microsip_escritura_usuario") or config.get("microsip_usuario"))
    try:
        esq = mse._Esquema(con.cursor())
        cols = esq.columnas("VACACIONES")
        if not paso("Tabla VACACIONES", bool(cols), ", ".join(cols) if cols else "No existe"):
            return r
        r["columnas"] = [{"nombre": c, "obligatoria": bool(d["obligatoria"] and not d["default"])} for c, d in cols.items()]
        paso("Tabla PERIODOS_VAC", bool(esq.columnas("PERIODOS_VAC")), ", ".join(esq.columnas("PERIODOS_VAC")))
        esq.cur.execute("""SELECT TRIM(RDB$TRIGGER_NAME), RDB$TRIGGER_TYPE FROM RDB$TRIGGERS
                           WHERE RDB$RELATION_NAME = 'VACACIONES' AND COALESCE(RDB$TRIGGER_INACTIVE, 0) = 0""")
        trig = [f"{n} ({t})" for n, t in esq.cur.fetchall()]
        paso("Triggers de VACACIONES", True, ", ".join(trig) if trig else "Ninguno (los días del periodo los descontará la app)")
        r["estatus_usados"] = [{"estatus": e, "veces": n} for e, n in _estatus_frecuentes(esq)]
        paso("Estatus que usa Microsip", True, ", ".join(f"'{e}' ({n})" for e, n in _estatus_frecuentes(esq)) or "sin registros")
        esq.cur.execute("SELECT FIRST 5 * FROM VACACIONES ORDER BY FECHA_INICIAL DESC")
        nombres = [d[0].strip() for d in esq.cur.description]
        r["ultimos"] = [{k: (v.isoformat() if hasattr(v, "isoformat") else (str(v).strip() if v is not None else None))
                         for k, v in zip(nombres, fila)} for fila in esq.cur.fetchall()]
        if not numero_empleado:
            paso("Prueba de alta", True, "Escribe un número de empleado con días disponibles para probar el alta (se deshace).")
            r["ok"] = True
            return r
        emp = _empleado(esq, numero_empleado)
        if not paso("Empleado de prueba", bool(emp), (emp.get("NOMBRE_COMPLETO") or "").strip() if emp else f"No existe el número {numero_empleado}"):
            return r
        prueba = _registrar(esq, emp["EMPLEADO_ID"], _hoy() + timedelta(days=30), 1, "PRUEBA TICKETS-TI (se deshace)", estatus)
        paso("Alta de 1 día (deshecha)", True,
             f"Fin {prueba['fecha_final']} · disponibles {prueba['disponibles_antes']:g} → {prueba['disponibles_despues']:g} · "
             + ("Microsip descontó solo el día" if prueba["descontado_por_microsip"] else "la app descontó el día del periodo"))
        r["ok"] = True
    except mse.ErrorMicrosip as e:
        paso(e.paso, False, e.detalle)
    except fdb.DatabaseError as e:
        paso("Microsip", False, mse._error_fb(e))
    except Exception as e:
        paso("Error", False, str(e))
    finally:
        try:
            con.rollback()
        except Exception:
            pass
        con.close()
    return r
