#!/usr/bin/env python3
"""
Cliente de consulta al SRI (catastro de contribuyentes) con control de tasa.

Diseño anti-banneo (requisito: acceso RESTRINGIDO al SRI):
  * Mínimo SRI_MIN_INTERVAL_MS entre dos llamadas salientes (default 2000 ms).
  * Ventana deslizante: máximo SRI_MAX_PER_MIN por minuto (default 5).
  * Reintento con backoff exponencial ante 429/5xx (2 intentos: 2s, 4s).
  * Nunca reintenta ante 4xx (404 = RUC inexistente; no es error de red).
  * Caché en disco: SRI_CACHE_TTL h por RUC/cédula -> una misma consulta
    NUNCA genera una segunda llamada al SRI dentro de la vigencia.
  * SRI_MAX_TOTAL_LIMIT global opcional (tope duro de llamadas por proceso).
  * SRI_DISABLED=1 apaga por completo la salida al SRI (modo sólo-caché).

Sin dependencias externas: urllib + json (stdlib). Compatible con Odoo o MCP.
Endpoint oficial: srienlinea.sri.gob.ec / ConsolidadoContribuyente.
"""
from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SRI_RUC_ENDPOINT = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet"
    "/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc"
)
SRI_CEDULA_ENDPOINT = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet"
    "/rest/ConsolidadoContribuyente/obtenerPorNumeroCedula"
)
SRI_NOMBRE_ENDPOINT = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet"
    "/rest/ConsolidadoContribuyente/obtenerPorRazonSocial"
)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Odoo/18.0 SomatechEC/1.0",
}

ENV = os.environ.get


def _int_env(name: str, default: int) -> int:
    try:
        return int(ENV(name, default))
    except ValueError:
        return default


MIN_INTERVAL_MS = _int_env("SRI_MIN_INTERVAL_MS", 2000)
MAX_PER_MIN = _int_env("SRI_MAX_PER_MIN", 5)
TIMEOUT = _int_env("SRI_TIMEOUT", 15)
CACHE_TTL_S = _int_env("SRI_CACHE_TTL", 24 * 3600)
MAX_TOTAL = _int_env("SRI_MAX_TOTAL", 0)          # 0 = sin tope duro
DISABLED = ENV("SRI_DISABLED", "0") == "1"
RETRIES = _int_env("SRI_RETRIES", 2)

CACHE_DIR = Path(ENV("SRI_CACHE_DIR", Path.home() / ".cache" / "ec-sri"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class RateLimiter:
    """Límite de tasa en proceso: intervalo mínimo + ventana de 60 s."""

    def __init__(self, min_interval_ms: int, max_per_min: int):
        self.min_interval = min_interval_ms / 1000.0
        self.max_per_min = max_per_min
        self._lock = threading.Lock()
        self._last = 0.0
        self._window_start = 0.0
        self._window_count = 0
        self.calls = 0

    def acquire(self) -> float:
        """Bloquea hasta que la llamada sea permitida. Devuelve segundos esperados."""
        waited = 0.0
        with self._lock:
            while True:
                now = time.monotonic()
                if now - self._window_start >= 60.0:
                    self._window_start, self._window_count = now, 0
                ok_interval = (now - self._last) >= self.min_interval
                ok_window = self._window_count < self.max_per_min
                if ok_interval and ok_window:
                    self._last = now
                    self._window_count += 1
                    self.calls += 1
                    return waited
                sleep = max(self.min_interval - (now - self._last), 0.05)
                if not ok_window:
                    sleep = max(sleep, 60.0 - (now - self._window_start) + 0.05)
                time.sleep(sleep)
                waited += sleep

    def stats(self) -> dict:
        with self._lock:
            return {
                "calls": self.calls,
                "min_interval_ms": int(self.min_interval * 1000),
                "max_per_min": self.max_per_min,
            }


LIMITER = RateLimiter(MIN_INTERVAL_MS, MAX_PER_MIN)


def _cache_path(kind: str, key: str) -> Path:
    return CACHE_DIR / f"{kind}-{key}.json"


def _cache_get(kind: str, key: str):
    p = _cache_path(kind, key)
    try:
        if p.exists():
            payload = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - payload.get("_ts", 0) < CACHE_TTL_S:
                return payload.get("data")
    except Exception:
        pass
    return None


def _cache_put(kind: str, key: str, data) -> None:
    try:
        _cache_path(kind, key).write_text(
            json.dumps({"_ts": time.time(), "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # la caché nunca debe tumbar la consulta


def _parse(data: dict) -> dict:
    """Mapea la respuesta del SRI.

    IMPORTANTE: el SRI cambió el esquema (verificado en vivo 2026-10):
      * `estadoContribuyente`        -> `estadoContribuyenteRuc`
      * `obligadoContabilidad`       -> `obligadoLlevarContabilidad`
      * `regimenRimpe`               -> `regimen`
      * fechas ahora anidadas en     -> `informacionFechasContribuyente{}`
      * el consolidado NO incluye dirección/teléfono/correo
        (se marcan como no disponibles en vez de devolver "" silencioso)
    Se aceptan las llaves viejas como fallback por si el SRI revierte.
    """
    fechas = data.get("informacionFechasContribuyente") or {}

    def pick(*keys, default=""):
        for k in keys:
            if data.get(k) not in (None, ""):
                return data.get(k)
        return default

    return {
        "ruc": pick("numeroRuc", "ruc"),
        "razon_social": pick("razonSocial", "razon_social"),
        "nombre_comercial": pick("nombreComercial", "nombre_comercial"),
        "estado": pick("estadoContribuyenteRuc", "estadoContribuyente"),
        "estado_establecimiento": pick("estadoEstablecimiento"),
        "clase_contribuyente": pick("claseContribuyente"),
        "tipo_contribuyente": pick("tipoContribuyente"),
        "regimen": pick("regimen", "regimenRimpe"),
        "categoria": pick("categoria"),
        "obligado_contabilidad": str(
            pick("obligadoLlevarContabilidad", "obligadoContabilidad",
                 default="NO")
        ).upper() == "SI",
        "actividad_economica": pick("actividadEconomicaPrincipal"),
        "codigo_actividad": pick("codigoActividadEconomica"),
        # --- dirección/contacto: NO vienen en el consolidado -----------
        "direccion": pick("direccionMatriz", "direccion"),
        "calle": pick("nombreCalle"),
        "numero": pick("numeroCasa"),
        "interseccion": pick("interseccion"),
        "provincia": pick("nombreProvincia"),
        "canton": pick("nombreCanton"),
        "parroquia": pick("nombreParroquia"),
        "telefono": pick("telefono1"),
        "email": pick("correo"),
        "direccion_disponible_en_sri": bool(
            pick("direccionMatriz", "nombreProvincia", "nombreCanton")
        ),
        # --- fechas (ahora anidadas) -----------------------------------
        "fecha_inicio_actividades": fechas.get(
            "fechaInicioActividades", pick("fechaInicioActividades")
        ),
        "fecha_actualizacion": fechas.get(
            "fechaActualizacion", pick("fechaActualizacion")
        ),
        "fecha_cese": fechas.get("fechaCese", ""),
        "fecha_reinicio_actividades": fechas.get("fechaReinicioActividades", ""),
        # --- especiales -------------------------------------------------
        "contribuyente_especial": pick("contribuyenteEspecial"),
        "agente_retencion": pick("agenteRetencion"),
        "regimen_rimpe": pick("regimenRimpe", "regimen"),
        "contribuyente_fantasma": pick("contribuyenteFantasma"),
        "transacciones_inexistentes": pick("transaccionesInexistente"),
        "motivo_cancelacion_suspension": pick("motivoCancelacionSuspension"),
        "representantes_legales": data.get("representantesLegales") or [],
        "schema_version": "consolidado-2026",
    }


def _ssl_context():
    """Contexto TLS con CA fiable (certifi -> /etc/ssl/cert.pem -> sistema).

    En macOS el Python de sistema no trae bundle CA instalado; sin esto el SRI
    falla con CERTIFICATE_VERIFY_FAILED aunque curl funcione.
    """
    import ssl

    for cafile in (ENV("SRI_CA_BUNDLE", ""), _certifi_path(), "/etc/ssl/cert.pem"):
        if cafile and os.path.exists(cafile):
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                continue
    return ssl.create_default_context()


def _certifi_path() -> str:
    try:
        import certifi

        return certifi.where()
    except Exception:
        return ""


def _http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT,
                                    context=_ssl_context()) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body
    except urllib.error.URLError as exc:
        return 0, f"connection error: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - debe degradar, nunca lanzar
        return 0, f"error: {exc}"


def _query(endpoint: str, param: str, kind: str, key: str, use_cache: bool = True):
    if use_cache:
        cached = _cache_get(kind, key)
        if cached is not None:
            return {"success": True, "data": cached, "source": "cache", "live": False}

    if DISABLED:
        return {
            "success": False,
            "error": "Consultas al SRI deshabilitadas (SRI_DISABLED=1) y sin caché.",
            "source": "disabled",
        }
    if MAX_TOTAL and LIMITER.calls >= MAX_TOTAL:
        return {
            "success": False,
            "error": f"Tope duro de llamadas al SRI alcanzado ({MAX_TOTAL}).",
            "source": "limit",
        }

    url = f"{endpoint}?{urllib.parse.urlencode({param: key})}"
    attempt = 0
    while True:
        waited = LIMITER.acquire()
        status, body = _http_get(url)

        if status == 200:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return {"success": False, "error": "Respuesta no-JSON del SRI",
                        "source": "sri"}
            if isinstance(payload, list) and payload:
                parsed = _parse(payload[0])
                _cache_put(kind, key, parsed)
                return {"success": True, "data": parsed, "source": "sri",
                        "live": True, "throttle_wait_s": round(waited, 2)}
            return {"success": False, "error": f"{key} no existe en el SRI",
                    "source": "sri", "status": status}

        if status == 404:
            return {"success": False, "error": f"{key} no existe en el SRI",
                    "source": "sri", "status": 404}
        if status in (429, 500, 502, 503, 504) and attempt < RETRIES:
            attempt += 1
            backoff = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(backoff)
            continue
        if status == 0:
            return {"success": False,
                    "error": "Sin conexión con el SRI (modo local/caché).",
                    "source": "offline"}
        return {"success": False, "error": f"SRI respondió {status}",
                "source": "sri", "status": status}


def consultar_ruc(ruc: str, use_cache: bool = True) -> dict:
    ruc = str(ruc).strip()
    if len(ruc) != 13 or not ruc.isdigit():
        return {"success": False, "error": "El RUC debe tener 13 dígitos"}
    return _query(SRI_RUC_ENDPOINT, "ruc", "ruc", ruc, use_cache)


def consultar_cedula(cedula: str, use_cache: bool = True) -> dict:
    cedula = str(cedula).strip()
    if len(cedula) != 10 or not cedula.isdigit():
        return {"success": False, "error": "La cédula debe tener 10 dígitos"}
    return _query(SRI_CEDULA_ENDPOINT, "cedula", "cedula", cedula, use_cache)


def consultar_por_nombre(nombre: str) -> dict:
    nombre = str(nombre).strip()
    if len(nombre) < 3:
        return {"success": False, "error": "Nombre demasiado corto"}
    return _query(SRI_NOMBRE_ENDPOINT, "razonSocial", "nombre", nombre)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: sri_client.py <RUC13|CEDULA10> [--no-cache]  |  --stats")
        return 2
    if argv[1] == "--stats":
        print(json.dumps({"limiter": LIMITER.stats(),
                          "cache_dir": str(CACHE_DIR),
                          "disabled": DISABLED}, ensure_ascii=False, indent=2))
        return 0
    use_cache = "--no-cache" not in argv
    arg = argv[1]
    res = (consultar_ruc(arg, use_cache) if len(arg) == 13
           else consultar_cedula(arg, use_cache))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
