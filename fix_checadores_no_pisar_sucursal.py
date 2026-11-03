# -*- coding: utf-8 -*-
"""
CHECADORES: YA NO CAMBIAN SOLOS LA SUCURSAL DE LOS EMPLEADOS
Cada 12 h el checador manda su lista de personas y el sistema volvia a poner
a todos en la sucursal (nave) de ese checador, pisando lo que RH corrigio.
Ahora lo automatico (checador, ligar solo, editar checador) SOLO llena la
sucursal a quien no tiene. La que RH pone a mano ya no se toca.
El boton "Asignar naves" de RH sigue funcionando (con vista previa).
Toca: backend/db.py, backend/app.py
Se puede correr varias veces.  Correr con:  py -3 fix_checadores_no_pisar_sucursal.py
"""
import os
import sys

ARCHIVOS = {
 "backend/db.py": [
  [
   "    return {\"sucursales\": sucursales, \"checadores\": checadores}\n\n\ndef asignar_naves_por_checador(empresa_id, usuario_ids=None, sns=None, aplicar=True):\n    \"\"\"A cada persona ligada a un checador le pone como sucursal (nave) la\n    del checador donde está. Si está en varios checadores (ej. después de\n    \"Red de checadores\" todos quedan en todos), su nave principal es donde\n",
   "    return {\"sucursales\": sucursales, \"checadores\": checadores}\n\n\ndef asignar_naves_por_checador(empresa_id, usuario_ids=None, sns=None, aplicar=True, solo_sin_sucursal=False):\n    \"\"\"A cada persona ligada a un checador le pone como sucursal (nave) la\n    del checador donde está. Si está en varios checadores (ej. después de\n    \"Red de checadores\" todos quedan en todos), su nave principal es donde\n"
  ],
  [
   "    tiene checadas: la de su checador original (no la copia de la red); si\n    tiene varias y su nave actual es una de ellas, se respeta la actual.\n    usuario_ids / sns: limitar a esas personas o a la gente de esos checadores.\n    Regresa {\"cambios\": [...], \"sin_cambio\": n, \"checadores_sin_nave\": [...]}.\"\"\"\n    naves = naves_de_checadores(empresa_id)\n    nave_de_sn = {k[\"sn\"]: k[\"sucursal_id\"] for k in naves[\"checadores\"] if k[\"sucursal_id\"]}\n",
   "    tiene checadas: la de su checador original (no la copia de la red); si\n    tiene varias y su nave actual es una de ellas, se respeta la actual.\n    usuario_ids / sns: limitar a esas personas o a la gente de esos checadores.\n    solo_sin_sucursal: lo automático (lo que manda el checador, ligar solo) solo\n    llena a quien NO tiene sucursal; nunca cambia la que RH ya puso a mano.\n    Regresa {\"cambios\": [...], \"sin_cambio\": n, \"checadores_sin_nave\": [...]}.\"\"\"\n    naves = naves_de_checadores(empresa_id)\n    nave_de_sn = {k[\"sn\"]: k[\"sucursal_id\"] for k in naves[\"checadores\"] if k[\"sucursal_id\"]}\n"
  ],
  [
   "                p[2] = p[2] or not g[\"creado_por_red\"]\n                p[3] = min(p[3], g[\"id\"])\n            actual = u[\"sucursal_id\"]\n            con_checadas = {n: p for n, p in puntos.items() if p[1] > 0}\n            if con_checadas:\n                elegida = max(con_checadas, key=lambda n: (con_checadas[n][0], con_checadas[n][1], n == actual))\n",
   "                p[2] = p[2] or not g[\"creado_por_red\"]\n                p[3] = min(p[3], g[\"id\"])\n            actual = u[\"sucursal_id\"]\n            if solo_sin_sucursal and actual:\n                resultado[\"sin_cambio\"] += 1\n                continue\n            con_checadas = {n: p for n, p in puntos.items() if p[1] > 0}\n            if con_checadas:\n                elegida = max(con_checadas, key=lambda n: (con_checadas[n][0], con_checadas[n][1], n == actual))\n"
  ]
 ],
 "backend/app.py": [
  [
   "                    _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n                except Exception as e:  # noqa: BLE001\n                    print(f\"[auto-ligar] {e}\")\n                _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.\n",
   "                    _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n                except Exception as e:  # noqa: BLE001\n                    print(f\"[auto-ligar] {e}\")\n                _asignar_naves(chk[\"empresa_id\"], sns=[sn], solo_sin_sucursal=True)\n        return _texto_plano(\"OK\")\n    if not chk or not chk.get(\"empresa_id\") or not chk.get(\"activo\"):\n        # Sin vincular: el checador guarda las checadas y las vuelve a mandar después.\n"
  ],
  [
   "                _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n            except Exception as e:  # noqa: BLE001\n                print(f\"[auto-ligar] {e}\")\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn])\n    return _texto_plano(\"OK\")\n\n\n",
   "                _auto_ligar_gente(chk[\"empresa_id\"], sns=[sn])\n            except Exception as e:  # noqa: BLE001\n                print(f\"[auto-ligar] {e}\")\n            _asignar_naves(chk[\"empresa_id\"], sns=[sn], solo_sin_sucursal=True)\n    return _texto_plano(\"OK\")\n\n\n"
  ],
  [
   "    anterior = antes.get(\"usuario_id\")\n    if anterior and anterior != payload.usuario_id:\n        # Se cambió el vínculo: a quien tenía antes se le recalcula su nave con los checadores que le quedan.\n        _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[anterior])\n    return {\"ok\": True, \"nave\": (nave or {}).get(\"cambios\", [None])[0] if (nave or {}).get(\"cambios\") else None,\n            \"cambio_vinculo\": bool(anterior and anterior != payload.usuario_id)}\n\n",
   "    anterior = antes.get(\"usuario_id\")\n    if anterior and anterior != payload.usuario_id:\n        # Se cambió el vínculo: a quien tenía antes se le recalcula su nave con los checadores que le quedan.\n        _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[anterior], solo_sin_sucursal=True)\n    return {\"ok\": True, \"nave\": (nave or {}).get(\"cambios\", [None])[0] if (nave or {}).get(\"cambios\") else None,\n            \"cambio_vinculo\": bool(anterior and anterior != payload.usuario_id)}\n\n"
  ],
  [
   "    if not ok:\n        raise HTTPException(status_code=404, detail=\"No encontrado\")\n    if anterior:\n        _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[anterior])\n    return {\"ok\": True}\n\n\n",
   "    if not ok:\n        raise HTTPException(status_code=404, detail=\"No encontrado\")\n    if anterior:\n        _asignar_naves(usuario[\"empresa_id\"], usuario_ids=[anterior], solo_sin_sucursal=True)\n    return {\"ok\": True}\n\n\n"
  ],
  [
   "    if aplicar and hechos:\n        for h in hechos:\n            db.actualizar_gente_checador(empresa_id, h[\"gente_id\"], h[\"usuario_id\"], h[\"persona\"], None)\n        _asignar_naves(empresa_id, usuario_ids=[h[\"usuario_id\"] for h in hechos])\n    return {\"ligados\": hechos, \"dudas\": dudas}\n\n\n",
   "    if aplicar and hechos:\n        for h in hechos:\n            db.actualizar_gente_checador(empresa_id, h[\"gente_id\"], h[\"usuario_id\"], h[\"persona\"], None)\n        # Ligado solo (por el checador): solo llena la sucursal a quien no tiene; no pisa la de RH.\n        _asignar_naves(empresa_id, usuario_ids=[h[\"usuario_id\"] for h in hechos], solo_sin_sucursal=bool(sns))\n    return {\"ligados\": hechos, \"dudas\": dudas}\n\n\n"
  ],
  [
   "def api_guardar_checador_adms(payload: ChecadorAdmsIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    try:\n        r = db.guardar_checador_adms(usuario[\"empresa_id\"], payload.sn, _limpio(payload.nombre), _limpio(payload.sucursal), payload.activo)\n        _asignar_naves(usuario[\"empresa_id\"], sns=[r[\"sn\"]])\n        return r\n    except ValueError as e:\n        raise HTTPException(status_code=400, detail=str(e))\n",
   "def api_guardar_checador_adms(payload: ChecadorAdmsIn, usuario: dict = Depends(requiere_datos_empleado_rh)):\n    try:\n        r = db.guardar_checador_adms(usuario[\"empresa_id\"], payload.sn, _limpio(payload.nombre), _limpio(payload.sucursal), payload.activo)\n        _asignar_naves(usuario[\"empresa_id\"], sns=[r[\"sn\"]], solo_sin_sucursal=True)\n        return r\n    except ValueError as e:\n        raise HTTPException(status_code=400, detail=str(e))\n"
  ]
 ]
}

NUEVOS = {}


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
        print("Este script necesita Python 3. Correlo asi:  py -3 fix_checadores_no_pisar_sucursal.py")
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
            if nuevo in texto and viejo not in texto:
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
