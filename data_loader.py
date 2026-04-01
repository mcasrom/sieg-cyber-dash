"""
data_loader.py — SIEG-CYBER v2.0
Fuentes: INCIBE, NVD, CISA, ENISA, BSI, ANSSI, CERT-EU, CSIRT.es,
         Abuse.ch URLhaus, Feodo Tracker, MalwareBazaar
"""

import feedparser
import pandas as pd
import requests
import csv
import io
from datetime import datetime, timezone
import hashlib
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# ── Fuentes RSS ───────────────────────────────────────────────────────────────
RSS_SOURCES = {
    # España
    "INCIBE-Vulnerabilidades": {
        "url":    "https://www.incibe.es/incibe-cert/alerta-temprana/vulnerabilidades/feed",
        "origin": "INCIBE", "region": "España",
        "lat": 40.4168, "lon": -3.7038,
    },
    "INCIBE-Avisos": {
        "url":    "https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed",
        "origin": "INCIBE", "region": "España",
        "lat": 40.4168, "lon": -3.7038,
    },
    "CSIRT-es": {
        "url":    "https://www.csirt.es/rss/",
        "origin": "CSIRT.es", "region": "España",
        "lat": 40.4168, "lon": -3.7038,
    },
    # EEUU
    "NVD-CVE": {
        "url":    "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml",
        "origin": "NVD/NIST", "region": "EEUU",
        "lat": 38.9072, "lon": -77.0369,
    },
    "NVD-CVE-Analyzed": {
        "url":    "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml",
        "origin": "NVD/NIST", "region": "EEUU",
        "lat": 38.9072, "lon": -77.0369,
    },
    "CISA-Advisories": {
        "url":    "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        "origin": "CISA", "region": "EEUU",
        "lat": 38.8951, "lon": -77.0364,
    },
    # Europa
    "ENISA": {
        "url":    "https://www.enisa.europa.eu/news/rss",
        "origin": "ENISA", "region": "UE",
        "lat": 50.8503, "lon": 4.3517,
    },
    "BSI": {
        "url":    "https://www.bsi.bund.de/SiteGlobals/Functions/RSSFeed/RSSNewsfeed_Sicherheitswarnung/RSSNewsfeed_Sicherheitswarnung_en.xml",
        "origin": "BSI", "region": "Alemania",
        "lat": 52.5200, "lon": 13.4050,
    },
    "ANSSI": {
        "url":    "https://www.cert.ssi.gouv.fr/feed/",
        "origin": "ANSSI", "region": "Francia",
        "lat": 48.8566, "lon": 2.3522,
    },
    "CERT-EU": {
        "url":    "https://cert.europa.eu/publications/threat-intelligence/rss.xml",
        "origin": "CERT-EU", "region": "UE",
        "lat": 50.8503, "lon": 4.3517,
    },
    # Abuse.ch
    "URLhaus": {
        "url":    "https://urlhaus.abuse.ch/feeds/recent/",
        "origin": "Abuse.ch/URLhaus", "region": "Global",
        "lat": 47.3769, "lon": 8.5417,
    },
}

# ── Fuentes especiales (no RSS) ───────────────────────────────────────────────
FEODO_URL      = "https://feodotracker.abuse.ch/downloads/ipblocklist.csv"
BAZAAR_URL     = "https://bazaar.abuse.ch/export/csv/recent/"

# ── Clasificación ─────────────────────────────────────────────────────────────
RISK_CRITICAL = [
    "crítica", "crítico", "critical", "zero-day", "0-day", "rce",
    "exploit", "ejecución remota", "unauthenticated", "cvss:10",
    "cvss: 10", "score: 10", "9.8", "9.9", "10.0",
]
RISK_HIGH = [
    "alta", "alto", "high", "importante", "privilege escalation",
    "sql injection", "xss", "buffer overflow", "7.", "8.", "9.",
]
RISK_LOW = ["baja", "bajo", "low", "informativa", "informational"]

THREAT_TYPES = {
    "Ransomware":     ["ransomware", "cifrado", "rescate"],
    "Phishing":       ["phishing", "smishing", "vishing", "suplantación"],
    "Vulnerabilidad": ["vulnerabilidad", "cve-", "patch", "parche", "fallo"],
    "Botnet/DDoS":    ["botnet", "ddos", "denegación de servicio", "c2", "c&c", "feodo", "emotet", "qakbot"],
    "Zero-Day":       ["zero-day", "0-day", "día cero"],
    "Malware":        ["malware", "troyano", "virus", "spyware", "backdoor", "loader", "stealer"],
    "URLhaus":        ["urlhaus", "url maliciosa", "malicious url"],
    "Otro":           [],
}

# Países origen botnets conocidos → coordenadas para el mapa
BOTNET_ORIGINS = {
    "Rusia":         {"lat": 55.7558, "lon": 37.6173, "region": "Rusia"},
    "China":         {"lat": 39.9042, "lon": 116.4074, "region": "China"},
    "Brasil":        {"lat": -15.7801, "lon": -47.9292, "region": "Brasil"},
    "Ucrania":       {"lat": 50.4501, "lon": 30.5234, "region": "Ucrania"},
    "India":         {"lat": 28.6139, "lon": 77.2090, "region": "India"},
    "EEUU":          {"lat": 38.9072, "lon": -77.0369, "region": "EEUU"},
    "Alemania":      {"lat": 52.5200, "lon": 13.4050, "region": "Alemania"},
    "Países Bajos":  {"lat": 52.3676, "lon": 4.9041,  "region": "Países Bajos"},
    "Corea del Sur": {"lat": 37.5665, "lon": 126.9780, "region": "Corea del Sur"},
    "Irán":          {"lat": 35.6892, "lon": 51.3890,  "region": "Irán"},
}

# Familias botnet → país origen probable
BOTNET_FAMILY_ORIGIN = {
    "emotet":    "Ucrania",
    "qakbot":    "Rusia",
    "trickbot":  "Rusia",
    "dridex":    "Rusia",
    "mirai":     "China",
    "necurs":    "Rusia",
    "andromeda": "Rusia",
    "glupteba":  "Rusia",
    "cobalt":    "Rusia",
    "lazarus":   "Corea del Sur",
    "revil":     "Rusia",
    "lockbit":   "Rusia",
}


def _score_risk(text: str) -> str:
    t = text.lower()
    if any(k in t for k in RISK_CRITICAL): return "Crítico"
    if any(k in t for k in RISK_HIGH):     return "Alto"
    if any(k in t for k in RISK_LOW):      return "Bajo"
    return "Medio"


def _score_type(text: str) -> str:
    t = text.lower()
    for ttype, keywords in THREAT_TYPES.items():
        if any(k in t for k in keywords):
            return ttype
    return "Otro"


def _parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _entry_id(title: str, source: str) -> str:
    return hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:8]


def _detect_botnet_origin(text: str) -> dict | None:
    """Detecta familia de botnet y devuelve coordenadas de origen."""
    t = text.lower()
    for family, country in BOTNET_FAMILY_ORIGIN.items():
        if family in t:
            coords = BOTNET_ORIGINS.get(country, {})
            return {
                "botnet_family":  family,
                "botnet_country": country,
                "lat_origin":     coords.get("lat", 0),
                "lon_origin":     coords.get("lon", 0),
            }
    return None


# ── Fetch RSS genérico ────────────────────────────────────────────────────────
def _fetch_feed(name: str, cfg: dict, max_items: int = 20) -> list:
    rows = []
    try:
        resp = requests.get(cfg["url"], headers=HEADERS, timeout=12)
        feed = feedparser.parse(resp.text)
    except Exception:
        try:
            feed = feedparser.parse(cfg["url"])
        except Exception as e:
            logger.warning(f"[{name}] Error: {e}")
            return []

    for entry in feed.entries[:max_items]:
        title    = entry.get("title", "Sin título")
        summary  = entry.get("summary", entry.get("description", ""))
        combined = f"{title} {summary}"
        botnet   = _detect_botnet_origin(combined)
        row = {
            "id":       _entry_id(title, name),
            "titulo":   title,
            "enlace":   entry.get("link", "#"),
            "fecha":    _parse_date(entry),
            "fuente":   cfg["origin"],
            "feed":     name,
            "region":   cfg["region"],
            "lat":      cfg["lat"],
            "lon":      cfg["lon"],
            "riesgo":   _score_risk(combined),
            "tipo":     _score_type(combined),
            "resumen":  summary[:300] if summary else "",
            "botnet_family":  botnet["botnet_family"]  if botnet else None,
            "botnet_country": botnet["botnet_country"] if botnet else None,
            "lat_origin":     botnet["lat_origin"]     if botnet else None,
            "lon_origin":     botnet["lon_origin"]     if botnet else None,
        }
        rows.append(row)
    return rows


# ── Feodo Tracker (IPs C2 botnets bancarios) ─────────────────────────────────
def _fetch_feodo(max_items: int = 30) -> list:
    rows = []
    try:
        resp = requests.get(FEODO_URL, headers=HEADERS, timeout=15)
        lines = resp.text.splitlines()
        count = 0
        for line in lines:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            # formato: first_seen, dst_ip, dst_port, c2_status, malware
            first_seen = parts[0].strip() if parts[0] else datetime.now().strftime("%Y-%m-%d %H:%M")
            ip         = parts[1].strip()
            status     = parts[3].strip()  # online/offline
            family     = parts[4].strip().lower() if len(parts) > 4 else "unknown"
            if status != "online":
                continue
            botnet_info = BOTNET_ORIGINS.get(
                BOTNET_FAMILY_ORIGIN.get(family, "Rusia"),
                BOTNET_ORIGINS["Rusia"]
            )
            title = f"C2 Botnet activo: {family.upper()} — {ip}"
            rows.append({
                "id":       _entry_id(title, "Feodo"),
                "titulo":   title,
                "enlace":   f"https://feodotracker.abuse.ch/browse/host/{ip}/",
                "fecha":    first_seen[:16],
                "fuente":   "Feodo Tracker",
                "feed":     "Feodo-Tracker",
                "region":   botnet_info["region"],
                "lat":      botnet_info["lat"],
                "lon":      botnet_info["lon"],
                "riesgo":   "Crítico",
                "tipo":     "Botnet/DDoS",
                "resumen":  f"Servidor C2 {status}: {ip} — Familia: {family}",
                "botnet_family":  family,
                "botnet_country": botnet_info["region"],
                "lat_origin":     botnet_info["lat"],
                "lon_origin":     botnet_info["lon"],
            })
            count += 1
            if count >= max_items:
                break
        logger.info(f"[Feodo] {len(rows)} C2 activos")
    except Exception as e:
        logger.warning(f"[Feodo] Error: {e}")
    return rows


# ── MalwareBazaar (muestras recientes) ───────────────────────────────────────
def _fetch_bazaar(max_items: int = 20) -> list:
    rows = []
    try:
        resp  = requests.get(BAZAAR_URL, headers=HEADERS, timeout=15)
        lines = resp.text.splitlines()
        count = 0
        for line in lines:
            if line.startswith("#") or not line.strip():
                continue
            try:
                parts = next(csv.reader([line]))
            except Exception:
                continue
            if len(parts) < 9:
                continue
            # formato: first_seen, sha256, md5, sha1, reporter, file_name, file_type, mime_type, signature, ...
            first_seen = parts[0].strip()
            sha256     = parts[1].strip()[:16]
            file_name  = parts[5].strip() if len(parts) > 5 else "unknown"
            file_type  = parts[6].strip() if len(parts) > 6 else "unknown"
            signature  = parts[8].strip() if len(parts) > 8 else "unknown"
            family     = signature.lower() if signature else "unknown"
            botnet_info = BOTNET_ORIGINS.get(
                BOTNET_FAMILY_ORIGIN.get(family, ""),
                None
            )
            title = f"Malware: {signature or file_type} — {file_name[:40]}"
            rows.append({
                "id":       sha256[:8],
                "titulo":   title,
                "enlace":   f"https://bazaar.abuse.ch/sample/{parts[1].strip()}/",
                "fecha":    first_seen[:16],
                "fuente":   "MalwareBazaar",
                "feed":     "MalwareBazaar",
                "region":   botnet_info["region"] if botnet_info else "Global",
                "lat":      botnet_info["lat"]    if botnet_info else 20.0,
                "lon":      botnet_info["lon"]    if botnet_info else 0.0,
                "riesgo":   _score_risk(f"{signature} {file_type}"),
                "tipo":     "Malware",
                "resumen":  f"SHA256: {parts[1].strip()[:32]}... | Tipo: {file_type} | Firma: {signature}",
                "botnet_family":  family if family != "unknown" else None,
                "botnet_country": botnet_info["region"] if botnet_info else None,
                "lat_origin":     botnet_info["lat"]    if botnet_info else None,
                "lon_origin":     botnet_info["lon"]    if botnet_info else None,
            })
            count += 1
            if count >= max_items:
                break
        logger.info(f"[MalwareBazaar] {len(rows)} muestras")
    except Exception as e:
        logger.warning(f"[MalwareBazaar] Error: {e}")
    return rows


# ── Entry points ──────────────────────────────────────────────────────────────
def load_cyber_data() -> pd.DataFrame:
    all_rows = []

    # RSS feeds
    for name, cfg in RSS_SOURCES.items():
        rows = _fetch_feed(name, cfg)
        print(f"[{cfg['origin']}] {name}: {len(rows)} entradas")
        all_rows.extend(rows)

    # Feodo Tracker
    feodo_rows = _fetch_feodo()
    print(f"[Feodo] {len(feodo_rows)} C2 activos")
    all_rows.extend(feodo_rows)

    # MalwareBazaar
    bazaar_rows = _fetch_bazaar()
    print(f"[MalwareBazaar] {len(bazaar_rows)} muestras")
    all_rows.extend(bazaar_rows)

    if not all_rows:
        print("[WARN] Sin datos reales — usando mock")
        return _mock_data()

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["id"])
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.sort_values("fecha", ascending=False).reset_index(drop=True)
    return df


def load_cyber_data_list() -> list:
    """Devuelve lista de dicts con todos los campos incluyendo botnet info."""
    df = load_cyber_data()
    return df.to_dict("records")


def get_botnet_origins(data: list) -> list:
    """
    Extrae eventos con origen botnet geolocalizado.
    Útil para el mapa de origen de ataques hacia España.
    """
    origins = {}
    for d in data:
        country = d.get("botnet_country")
        family  = d.get("botnet_family")
        lat     = d.get("lat_origin")
        lon     = d.get("lon_origin")
        if not country or not lat or not lon:
            continue
        key = country
        if key not in origins:
            origins[key] = {
                "country":  country,
                "lat":      lat,
                "lon":      lon,
                "count":    0,
                "families": set(),
            }
        origins[key]["count"] += 1
        if family:
            origins[key]["families"].add(family)

    result = []
    for o in origins.values():
        o["families"] = list(o["families"])
        result.append(o)
    return sorted(result, key=lambda x: x["count"], reverse=True)


def _mock_data() -> pd.DataFrame:
    import random
    risks  = ["Crítico"] * 5 + ["Alto"] * 8 + ["Medio"] * 6 + ["Bajo"] * 3
    tipos  = list(THREAT_TYPES.keys())
    fuentes = ["INCIBE", "NVD/NIST", "CISA", "ENISA", "BSI", "Feodo Tracker"]
    rows = []
    for i in range(30):
        family  = random.choice(list(BOTNET_FAMILY_ORIGIN.keys()))
        country = BOTNET_FAMILY_ORIGIN[family]
        coords  = BOTNET_ORIGINS.get(country, BOTNET_ORIGINS["Rusia"])
        rows.append({
            "id":       f"mock{i:03d}",
            "titulo":   f"Alerta #{i+1} — {random.choice(['Vulnerabilidad crítica', 'C2 activo', 'Malware detectado'])}",
            "enlace":   "https://www.incibe.es",
            "fecha":    pd.Timestamp("2026-04-01"),
            "fuente":   random.choice(fuentes),
            "feed":     "Mock",
            "region":   random.choice(["España", "EEUU", "UE", "Alemania"]),
            "lat":      40.4168 + random.uniform(-5, 5),
            "lon":      -3.7038 + random.uniform(-5, 5),
            "riesgo":   random.choice(risks),
            "tipo":     random.choice(tipos),
            "resumen":  "Datos de prueba.",
            "botnet_family":  family,
            "botnet_country": country,
            "lat_origin":     coords["lat"],
            "lon_origin":     coords["lon"],
        })
    return pd.DataFrame(rows)
