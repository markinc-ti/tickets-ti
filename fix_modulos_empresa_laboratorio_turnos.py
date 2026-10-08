# -*- coding: utf-8 -*-
"""
Arregla que, al apagar/prender los modulos "Laboratorio" o "Turnos por
sucursal" de una empresa (Superadmin -> Empresas -> boton "Modulos") y
darle Guardar, el cambio no se guarde.

Causa: cuando se agregaron esos 2 modulos (Laboratorio y Turnos) se
agrego la columna en la base de datos y el checkbox en el frontend, pero
se les olvido agregarlos tambien a la clase ModulosEmpresaIn del backend
(backend/app.py). FastAPI ignora en silencio cualquier campo que el
frontend mande y que no este declarado en esa clase -- por eso el
checkbox se ve, se puede desmarcar, el boton "Guardar" no da ningun
error, pero el valor nunca llega a guardarse en la base de datos. Los
demas modulos (Equipos, Compras, RH, etc.) si estan declarados ahi y
por eso a esos si les funciona apagarlos/prenderlos.

Uso: colocalo en la carpeta del repo (junto a backend/ y frontend/) y
corre:  py -3 fix_modulos_empresa_laboratorio_turnos.py
"""
import sys

ARCHIVOS = {
    'backend/app.py': [
        [
            'class ModulosEmpresaIn(BaseModel):\n'
            '    modulo_equipos: Optional[bool] = None\n'
            '    modulo_compras: Optional[bool] = None\n'
            '    modulo_rh: Optional[bool] = None\n'
            '    modulo_dashboard: Optional[bool] = None\n'
            '    modulo_reparaciones: Optional[bool] = None\n'
            '    modulo_entregas: Optional[bool] = None\n'
            '    modulo_checador_precio: Optional[bool] = None\n'
            '    modulo_marketing: Optional[bool] = None\n'
            '    modulo_crm: Optional[bool] = None\n'
            '    modulo_asistente_ia: Optional[bool] = None\n'
            '    modulo_shopify: Optional[bool] = None',

            'class ModulosEmpresaIn(BaseModel):\n'
            '    modulo_equipos: Optional[bool] = None\n'
            '    modulo_compras: Optional[bool] = None\n'
            '    modulo_rh: Optional[bool] = None\n'
            '    modulo_dashboard: Optional[bool] = None\n'
            '    modulo_reparaciones: Optional[bool] = None\n'
            '    modulo_laboratorio: Optional[bool] = None\n'
            '    modulo_entregas: Optional[bool] = None\n'
            '    modulo_checador_precio: Optional[bool] = None\n'
            '    modulo_marketing: Optional[bool] = None\n'
            '    modulo_crm: Optional[bool] = None\n'
            '    modulo_asistente_ia: Optional[bool] = None\n'
            '    modulo_shopify: Optional[bool] = None\n'
            '    modulo_turnos: Optional[bool] = None',
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
    print("   git add backend/app.py")
    print('   git commit -m "Fix: modulos Laboratorio y Turnos no se guardaban al apagarlos/prenderlos por empresa"')
    print("   git push")


if __name__ == "__main__":
    main()
