"""
utils/infraestructura.py

Calcula indicadores de infraestructura para un predio:
  1. Distancia por carretera al centro urbano más cercano (Overpass + OSRM)
  2. Distancia en línea recta a la vía transitable más cercana (Overpass + Shapely)

APIs utilizadas (gratuitas, sin API key):
  - Overpass API  → centros urbanos y geometría de vías (OSM)
  - OSRM          → routing por carretera (router.project-osrm.org)
"""

import json
import time
import warnings
from pathlib import Path
import requests
import urllib3
import polyline as _polyline

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import geopandas as gpd
from shapely.geometry import Point, LineString

# ── Parámetros ────────────────────────────────────────────────────────────────
# Orden por fiabilidad medida (nov-2026); el primero que responda gana.
OVERPASS_URLS       = (
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
TIMEOUT_OVERPASS_SEG = 20
# Tope total por consulta: si los servidores públicos no responden en este
# tiempo, el indicador queda "no disponible" en lugar de bloquear la app.
PRESUPUESTO_OVERPASS_SEG = 30
OSRM_URL            = "http://router.project-osrm.org/route/v1/driving"

RADIO_BUSQUEDA_KM   = 80
N_CANDIDATOS        = 5
PAUSA_OSRM_SEG      = 0.5
PAUSA_OVERPASS_SEG  = 2
REINTENTOS_OVERPASS = 2
RADIO_CARRETERA_KM  = 5

HIGHWAY_TYPES = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|track"

# ── Modo demo: resultados precalculados ─────────────────────────────────────
# Los servidores públicos de Overpass fallan con frecuencia. En modo demo
# (sin base de datos) los predios de ejemplo usan distancias calculadas una
# vez con datos reales de OSM/OSRM (datos/infra_demo.json).
_INFRA_DEMO_PATH = Path(__file__).resolve().parent.parent / "datos" / "infra_demo.json"


def _infra_demo(lat: float, lon: float, clave: str):
    try:
        from utils.postgis_client import USE_REAL_DB
        if USE_REAL_DB or not _INFRA_DEMO_PATH.exists():
            return None
        datos = json.loads(_INFRA_DEMO_PATH.read_text(encoding="utf-8"))
        return datos.get(f"{lat:.4f},{lon:.4f}", {}).get(clave)
    except Exception:
        return None


# ── Helper Overpass con reintentos ────────────────────────────────────────────

def _overpass_get(query: str) -> list:
    """Consulta Overpass rotando entre servidores públicos.

    Los servidores públicos fallan con frecuencia (429/5xx). Se prueba cada
    servidor en orden y se reintenta con espera exponencial. Si todos fallan,
    se lanza RuntimeError para que la app muestre el indicador como
    no disponible en lugar de caerse.
    """
    headers = {
        "User-Agent": "AgroCredito/1.0",
        "Accept":     "application/json",
    }
    ultimo_error = None
    limite = time.monotonic() + PRESUPUESTO_OVERPASS_SEG
    for intento in range(REINTENTOS_OVERPASS):
        for url in OVERPASS_URLS:
            restante = limite - time.monotonic()
            if restante < 3:
                raise RuntimeError(f"Overpass no disponible (tiempo agotado): {ultimo_error}")
            try:
                resp = requests.get(url, params={"data": query}, headers=headers,
                                    timeout=min(TIMEOUT_OVERPASS_SEG, restante))
            except requests.exceptions.RequestException as e:
                ultimo_error = e
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                ultimo_error = f"{url} → HTTP {resp.status_code}"
                continue
            resp.raise_for_status()
            return resp.json().get("elements", [])
        time.sleep(PAUSA_OVERPASS_SEG * (2 ** intento))
    raise RuntimeError(f"Overpass no disponible: {ultimo_error}")


# ════════════════════════════════════════════════════════════════════════════════
#  1 · DISTANCIA AL CENTRO URBANO MÁS CERCANO
# ════════════════════════════════════════════════════════════════════════════════

def _get_centros_urbanos(lat: float, lon: float) -> list[dict]:
    radio_m = RADIO_BUSQUEDA_KM * 1000
    query = f"""
    [out:json][timeout:25];
    (
      node["place"~"^(city|town|village)$"]
         (around:{radio_m},{lat},{lon});
    );
    out body;
    """
    elementos = _overpass_get(query)
    centros = []
    for e in elementos:
        clat, clon = e["lat"], e["lon"]
        dist = ((lat - clat) ** 2 + (lon - clon) ** 2) ** 0.5 * 111.32
        centros.append({
            "nombre":        e.get("tags", {}).get("name", "Sin nombre"),
            "tipo":          e.get("tags", {}).get("place", ""),
            "lat":           clat,
            "lon":           clon,
            "dist_recta_km": round(dist, 2),
        })
    centros.sort(key=lambda x: x["dist_recta_km"])
    return centros[:N_CANDIDATOS]


def _get_ruta_osrm(lat1, lon1, lat2, lon2) -> dict | None:
    url = f"{OSRM_URL}/{lon1},{lat1};{lon2},{lat2}"
    try:
        resp = requests.get(url, params={"overview": "full", "geometries": "polyline"},
                            timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        ruta = data["routes"][0]
        coords = _polyline.decode(ruta["geometry"])
        return {
            "distancia_km": round(ruta["distance"] / 1000, 2),
            "duracion_min": round(ruta["duration"] / 60, 1),
            "coords":       coords,
        }
    except Exception:
        return None


def get_distancia_centro_urbano(lat: float, lon: float) -> dict | None:
    """
    Devuelve el centro urbano más cercano por carretera y las métricas de ruta.

    Retorna dict con:
        nombre          str     nombre del centro urbano
        tipo            str     city / town / village
        distancia_km    float   km por carretera
        duracion_min    float   minutos estimados en vehículo
        dist_recta_km   float   km en línea recta (referencia)
        coords          list    polyline de la ruta [(lat,lon), ...]
    Retorna None si no se encuentra ruta.
    """
    demo = _infra_demo(lat, lon, "centro")
    if demo is not None:
        return demo

    candidatos = _get_centros_urbanos(lat, lon)
    if not candidatos:
        return None

    mejor = None
    for c in candidatos:
        time.sleep(PAUSA_OSRM_SEG)
        ruta = _get_ruta_osrm(lat, lon, c["lat"], c["lon"])
        if ruta is None:
            continue
        c["ruta"] = ruta
        if mejor is None or ruta["distancia_km"] < mejor["ruta"]["distancia_km"]:
            mejor = c

    if mejor is None:
        return None

    r = mejor["ruta"]
    return {
        "nombre":        mejor["nombre"],
        "tipo":          mejor["tipo"],
        "distancia_km":  r["distancia_km"],
        "duracion_min":  r["duracion_min"],
        "dist_recta_km": mejor["dist_recta_km"],
        "coords":        r["coords"],
        "lat":           mejor["lat"],
        "lon":           mejor["lon"],
    }


# ════════════════════════════════════════════════════════════════════════════════
#  2 · DISTANCIA EN LÍNEA RECTA A LA VÍA MÁS CERCANA
# ════════════════════════════════════════════════════════════════════════════════

def get_distancia_via(lat: float, lon: float) -> dict | None:
    """
    Distancia en línea recta (perpendicular) desde el punto al segmento
    vial más cercano dentro de RADIO_CARRETERA_KM.

    Retorna dict con:
        nombre          str     nombre de la vía (o 'Sin nombre')
        tipo            str     highway type (primary, secondary, track, …)
        distancia_m     float   metros
        distancia_km    float   km
    Retorna None si no se encuentra vía.
    """
    demo = _infra_demo(lat, lon, "via")
    if demo is not None:
        return demo

    radio_m = RADIO_CARRETERA_KM * 1000
    query = f"""
    [out:json][timeout:25];
    way["highway"~"^({HIGHWAY_TYPES})$"]
      (around:{radio_m},{lat},{lon});
    out geom;
    """
    elementos = _overpass_get(query)
    if not elementos:
        return None

    # Una sola reproyección para todas las vías (antes era una por vía, lento
    # en zonas con miles de calles).
    vias = [e for e in elementos if len(e.get("geometry", [])) >= 2]
    if not vias:
        return None
    lineas = gpd.GeoSeries(
        [LineString([(g["lon"], g["lat"]) for g in e["geometry"]]) for e in vias],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")
    predio_m = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]

    distancias = lineas.distance(predio_m)
    i = int(distancias.values.argmin())
    mejor_dist = float(distancias.iloc[i])
    linea_m = lineas.iloc[i]
    nearest_m = linea_m.interpolate(linea_m.project(predio_m))
    nearest_wgs = gpd.GeoSeries([nearest_m], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
    tags = vias[i].get("tags", {})

    return {
        "nombre":       tags.get("name", "Sin nombre"),
        "tipo":         tags.get("highway", ""),
        "distancia_m":  round(mejor_dist, 1),
        "distancia_km": round(mejor_dist / 1000, 3),
        "nearest_lat":  nearest_wgs.y,
        "nearest_lon":  nearest_wgs.x,
    }
