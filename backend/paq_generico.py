"""Conector genérico de paquetería (Paquetexpress, Castores…).

Estas paqueterías no publican su API: las direcciones, el formato y las
credenciales los entregan a cada cliente con su manual. Por eso aquí todo es
configurable por variables de entorno y los formatos de petición/respuesta
están aislados en _cuerpo_* y en lectores tolerantes (aceptan los nombres de
campo más comunes). Cuando llegue el manual se ajustan solo esas funciones.

Variables (PREFIJO = PAQUETEXPRESS, CASTORES…):
  {P}_MODO           "produccion" | "pruebas" | "simulado"  (vacío = no conectada)
  {P}_CLIENTE        número de cliente / cuenta
  {P}_USUARIO, {P}_PASSWORD   usuario de la API
  {P}_API_KEY        (opcional) si la paquetería da una llave
  {P}_TOKEN_URL      (opcional) si primero hay que pedir un token con usuario/contraseña
  {P}_COTIZAR_URL, {P}_GUIA_URL, {P}_RASTREO_URL   direcciones del manual
  {P}_RASTREO_PUBLICO_URL  (opcional) liga pública de rastreo con {guia}
"""
import os
import threading
import time
from datetime import datetime

import requests

import estafeta  # utilidades comunes (validaciones, guía y rastreo simulados)

TIEMPO = 30


class ErrorPaqueteria(Exception):
    pass


def _primero(d, *claves):
    for k in claves:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def _recorrer(x, alVer):
    if isinstance(x, list):
        for i in x:
            _recorrer(i, alVer)
    elif isinstance(x, dict):
        alVer(x)
        for v in x.values():
            if isinstance(v, (list, dict)):
                _recorrer(v, alVer)


CAMPOS_NOMBRE = ("servicio", "Servicio", "nombreServicio", "ServiceName", "serviceName", "descripcion", "Descripcion",
                 "DescripcionServicio", "tipoServicio", "service")
CAMPOS_TOTAL = ("total", "Total", "importeTotal", "ImporteTotal", "TotalAmount", "totalAmount", "CostoTotal", "precio",
                "Precio", "importe", "Importe", "amount")
CAMPOS_ID = ("idServicio", "IdServicio", "servicioId", "ServiceId", "serviceId", "claveServicio", "ClaveServicio", "codigo")
CAMPOS_DIAS = ("diasEntrega", "DiasEntrega", "tiempoEntrega", "TiempoEntrega", "DeliveryTime", "deliveryDays", "dias")


class Conector:
    def __init__(self, clave, nombre, prefijo, url_rastreo_publico, factor_simulado, servicios_simulados):
        self.CLAVE = clave
        self.NOMBRE = nombre
        self.PREFIJO = prefijo
        self.URL_RASTREO_PUBLICO = url_rastreo_publico
        self.factor = factor_simulado
        self.servicios_sim = servicios_simulados
        self.Error = ErrorPaqueteria
        self._token = None
        self._candado = threading.Lock()

    # ---------- configuración ----------

    def _env(self, nombre, defecto=""):
        return (os.environ.get(f"{self.PREFIJO}_{nombre}") or defecto).strip()

    def modo(self):
        m = self._env("MODO").lower()
        return m if m in ("produccion", "pruebas", "simulado") else ""

    def simulado(self):
        return self.modo() == "simulado"

    def _requeridas(self, que=None):
        base = ["CLIENTE", "USUARIO", "PASSWORD"]
        urls = {"cotizar": ["COTIZAR_URL"], "guia": ["GUIA_URL"], "rastreo": ["RASTREO_URL"]}
        extra = urls[que] if que else [u for v in urls.values() for u in v]
        return [f"{self.PREFIJO}_{v}" for v in base + extra]

    def estado(self):
        m = self.modo()
        faltan = [f"{self.PREFIJO}_MODO"] if not m else []
        if m and m != "simulado":
            faltan = [v for v in self._requeridas() if not (os.environ.get(v) or "").strip()]
        return {"modo": m or None, "conectada": bool(m) and not faltan, "simulado": m == "simulado", "faltan": faltan}

    def _verificar(self, que):
        m = self.modo()
        if not m:
            raise ErrorPaqueteria(f"{self.NOMBRE} todavía no está conectada (falta configurar la cuenta en Render).")
        if m == "simulado":
            return
        faltan = [v for v in self._requeridas(que) if not (os.environ.get(v) or "").strip()]
        if faltan:
            raise ErrorPaqueteria(f"Faltan datos de la cuenta {self.NOMBRE} en Render: " + ", ".join(faltan))

    # ---------- HTTP ----------

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._env("API_KEY"):
            h["apikey"] = self._env("API_KEY")
            h["x-api-key"] = self._env("API_KEY")
        url_token = self._env("TOKEN_URL")
        if url_token:
            h["Authorization"] = f"Bearer {self._obtener_token(url_token)}"
        return h

    def _obtener_token(self, url):
        with self._candado:
            if self._token and self._token[1] > time.time() + 60:
                return self._token[0]
        try:
            r = requests.post(url, json={"usuario": self._env("USUARIO"), "password": self._env("PASSWORD"),
                                         "username": self._env("USUARIO"), "cliente": self._env("CLIENTE")}, timeout=TIEMPO)
        except requests.RequestException as e:
            raise ErrorPaqueteria(f"No se pudo conectar con {self.NOMBRE} ({e.__class__.__name__}).")
        if r.status_code >= 400:
            raise ErrorPaqueteria(f"{self.NOMBRE} rechazó el usuario de la API (HTTP {r.status_code}).")
        d = r.json() if r.content else {}
        token = _primero(d, "token", "access_token", "Token", "accessToken") or \
            _primero(d.get("data") if isinstance(d, dict) else None, "token", "access_token")
        if not token:
            raise ErrorPaqueteria(f"{self.NOMBRE} no regresó el token de acceso.")
        with self._candado:
            self._token = (token, time.time() + int(_primero(d, "expires_in", "expiresIn") or 3000))
        return token

    def _post(self, url, cuerpo):
        auth = None if self._env("TOKEN_URL") else (self._env("USUARIO"), self._env("PASSWORD"))
        try:
            r = requests.post(url, json=cuerpo, headers=self._headers(), auth=auth, timeout=TIEMPO)
        except requests.RequestException as e:
            raise ErrorPaqueteria(f"No se pudo conectar con {self.NOMBRE} ({e.__class__.__name__}).")
        try:
            datos = r.json()
        except ValueError:
            datos = None
        if r.status_code >= 400:
            msg = _primero(datos, "message", "mensaje", "Mensaje", "error", "descripcion") if isinstance(datos, dict) else None
            raise ErrorPaqueteria(f"{self.NOMBRE} respondió con error (HTTP {r.status_code}): {msg or r.text[:200]}")
        return datos

    # ---------- cotizar ----------

    def cotizar(self, cp_origen, cp_destino, paquete):
        if not estafeta.cp_valido(cp_origen) or not estafeta.cp_valido(cp_destino):
            raise ErrorPaqueteria("Los códigos postales deben tener 5 dígitos.")
        try:
            paquete = estafeta.limpiar_paquete(paquete)
        except estafeta.ErrorEstafeta as e:
            raise ErrorPaqueteria(str(e))
        self._verificar("cotizar")
        if self.simulado():
            return self._cotizar_simulado(cp_origen, cp_destino, paquete)
        datos = self._post(self._env("COTIZAR_URL"), self._cuerpo_cotizar(cp_origen, cp_destino, paquete))
        servicios = self._leer_cotizacion(datos)
        if not servicios:
            raise ErrorPaqueteria(f"{self.NOMBRE} no tiene servicio para ese código postal con ese paquete.")
        return servicios

    def _cuerpo_cotizar(self, cp_o, cp_d, p):
        return {"cliente": self._env("CLIENTE"),
                "origen": {"codigoPostal": cp_o}, "destino": {"codigoPostal": cp_d},
                "paquetes": [{"cantidad": 1, "peso": p["peso"], "largo": p["largo"], "ancho": p["ancho"], "alto": p["alto"]}]}

    def _leer_cotizacion(self, datos):
        r = []

        def ver(x):
            nombre, total = _primero(x, *CAMPOS_NOMBRE), _primero(x, *CAMPOS_TOTAL)
            if nombre is None or total is None or isinstance(total, (dict, list)):
                return
            try:
                costo = float(str(total).replace(",", "").replace("$", ""))
            except ValueError:
                return
            if costo > 0:
                r.append({"servicio_id": str(_primero(x, *CAMPOS_ID) or nombre), "servicio": str(nombre).strip(),
                          "costo": round(costo, 2), "dias": _primero(x, *CAMPOS_DIAS)})

        _recorrer(datos, ver)
        vistos, unicos = set(), []
        for s in sorted(r, key=lambda s: s["costo"]):
            if s["servicio_id"] not in vistos:
                vistos.add(s["servicio_id"])
                unicos.append(s)
        return unicos

    def _cotizar_simulado(self, cp_o, cp_d, p):
        base = estafeta._cotizar_simulado(cp_o, cp_d, p)[0]["costo"]
        return [{"servicio_id": sid, "servicio": f"{nom} (SIMULADO)", "costo": round(base * self.factor * f, 2), "dias": dias}
                for sid, nom, f, dias in self.servicios_sim]

    # ---------- guía ----------

    def generar_guia(self, origen, destino, paquete, servicio_id, referencia, contenido):
        try:
            paquete = estafeta.limpiar_paquete(paquete)
        except estafeta.ErrorEstafeta as e:
            raise ErrorPaqueteria(str(e))
        for quien, d in (("origen", origen), ("destino", destino)):
            faltan = [c for c in ("nombre", "telefono", "calle", "colonia", "cp", "ciudad", "estado") if not (d.get(c) or "").strip()]
            if faltan:
                raise ErrorPaqueteria(f"Faltan datos del {quien}: {', '.join(faltan)}.")
            if not estafeta.cp_valido(d.get("cp")):
                raise ErrorPaqueteria(f"El código postal del {quien} debe tener 5 dígitos.")
        self._verificar("guia")
        if self.simulado():
            return estafeta._guia_simulada(origen, destino, paquete, servicio_id, referencia,
                                           marca=self.NOMBRE.upper(), prefijo="SIM" + self.CLAVE[:2].upper())
        datos = self._post(self._env("GUIA_URL"), self._cuerpo_guia(origen, destino, paquete, servicio_id, referencia, contenido))
        return self._leer_guia(datos)

    def _cuerpo_guia(self, origen, destino, p, servicio_id, referencia, contenido):
        def dom(d):
            return {"nombre": d.get("nombre"), "contacto": d.get("contacto") or d.get("nombre"), "telefono": d.get("telefono"),
                    "correo": d.get("correo") or "", "calle": d.get("calle"), "numero": d.get("numero") or "S/N",
                    "colonia": d.get("colonia"), "codigoPostal": d.get("cp"), "ciudad": d.get("ciudad"),
                    "estado": d.get("estado"), "referencia": d.get("referencia") or ""}
        return {"cliente": self._env("CLIENTE"), "servicio": servicio_id, "referencia": referencia or "",
                "contenido": contenido or "Mercancía", "remitente": dom(origen), "destinatario": dom(destino),
                "paquetes": [{"cantidad": 1, "peso": p["peso"], "largo": p["largo"], "ancho": p["ancho"], "alto": p["alto"]}],
                "fecha": datetime.now().strftime("%Y-%m-%d")}

    def _leer_guia(self, datos):
        guia, pdf = [None], [None]

        def ver(x):
            if not guia[0]:
                g = _primero(x, "guia", "Guia", "numeroGuia", "NumeroGuia", "trackingNumber", "wayBill", "rastreo")
                if isinstance(g, (str, int)):
                    guia[0] = str(g)
            if not pdf[0]:
                p = _primero(x, "pdf", "PDF", "etiqueta", "label", "labelPDF", "documento", "archivo", "data")
                if isinstance(p, str) and len(p) > 200:
                    pdf[0] = p.split(",", 1)[1] if p.startswith("data:") else p

        _recorrer(datos, ver)
        if not guia[0] or not pdf[0]:
            raise ErrorPaqueteria(f"{self.NOMBRE} no regresó la guía (o su PDF).")
        return {"guia": guia[0], "codigo_rastreo": guia[0], "pdf_base64": pdf[0], "simulada": False}

    # ---------- rastreo ----------

    def url_rastreo(self, guia):
        # {P}_RASTREO_PUBLICO_URL con {guia}, si la paquetería da una liga directa
        return (self._env("RASTREO_PUBLICO_URL") or self.URL_RASTREO_PUBLICO).replace("{guia}", str(guia))

    def rastrear(self, guia, simulada=False, creada_en=None):
        url = self.url_rastreo(guia)
        if simulada or self.simulado():
            return estafeta.rastreo_simulado(guia, creada_en, url)
        self._verificar("rastreo")
        datos = self._post(self._env("RASTREO_URL"), {"cliente": self._env("CLIENTE"), "guias": [guia], "guia": guia})
        eventos = []

        def ver(x):
            desc = _primero(x, "descripcion", "Descripcion", "evento", "Evento", "estatus", "status", "description")
            fecha = _primero(x, "fecha", "Fecha", "fechaHora", "FechaHora", "date", "eventDate")
            if isinstance(desc, str) and fecha:
                eventos.append({"fecha": str(fecha), "descripcion": desc,
                                "lugar": str(_primero(x, "lugar", "Lugar", "plaza", "sucursal", "ciudad", "location") or "")})

        _recorrer(datos, ver)
        eventos.sort(key=lambda e: e["fecha"], reverse=True)
        return {"estatus": eventos[0]["descripcion"] if eventos else "Sin movimientos todavía", "eventos": eventos, "url": url}
