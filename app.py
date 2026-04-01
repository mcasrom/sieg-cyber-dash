"""
app.py - SIEG-CYBER Intelligence Dashboard v3.2
Mejoras: Tab Metodología, Footer copyright, Canal Telegram público
"""
import os
import json
import requests
from datetime import datetime
from collections import Counter

from dash import Dash, dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from data_loader import load_cyber_data_list, get_botnet_origins
from modules.historical_db import HistoricalDB
from modules.advanced_kpis import AdvancedKPIs

from dotenv import load_dotenv
load_dotenv()

# ── Constantes globales ───────────────────────────────────────────────────────
DASHBOARD_URL  = "https://sieg-cyber-dash.onrender.com"
SIEG_OSINT_URL = "https://mcasrom.github.io/sieg-osint"
GITHUB_URL     = "https://github.com/mcasrom/sieg-cyber-dash"

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "-1003730038735")
TELEGRAM_CHANNEL  = "@sieg_politica_bot"   # canal/bot público para suscripción
_telegram_sent    = set()

def send_telegram_alert(event: dict):
    if not TELEGRAM_TOKEN:
        return
    title = event.get("title", event.get("titulo", "Sin título"))
    key   = title[:80]
    if key in _telegram_sent:
        return
    _telegram_sent.add(key)
    origin    = event.get("origin", event.get("fuente", "?"))
    region    = event.get("region", "Global")
    published = str(event.get("published", event.get("fecha", "")))[:16]
    msg = (
        f"🔴 *ALERTA CRÍTICA · SIEG-CYBER*\n\n"
        f"*{title[:120]}*\n\n"
        f"📡 Fuente: `{origin}`\n"
        f"🌍 Región: `{region}`\n"
        f"🕐 Fecha: `{published}`\n\n"
        f"🔗 [Ver dashboard]({DASHBOARD_URL})\n\n"
        f"_Monitor SIEG · sieg-cyber-dash_"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")

# ── Paleta ────────────────────────────────────────────────────────────────────
C = {
    "bg":       "#0d0f14",
    "panel":    "#13161e",
    "border":   "#1e2433",
    "accent":   "#00d4ff",
    "accent2":  "#ff4757",
    "accent3":  "#ffa502",
    "text":     "#c8d0e0",
    "muted":    "#4a5568",
    "critical": "#ff4757",
    "alto":     "#ffa502",
    "medio":    "#00d4ff",
    "bajo":     "#2ed573",
    "hero_bg":  "#080a10",
}

RISK_COLOR = {
    "Crítico": "#ff4757",
    "Alto":    "#ffa502",
    "Medio":   "#00d4ff",
    "Bajo":    "#2ed573",
}

PLOTLY_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="monospace", color=C["text"], size=12),
)

# ── Módulos ───────────────────────────────────────────────────────────────────
db   = HistoricalDB(max_days=14)
kpis = AdvancedKPIs()

# ── Caché + carga inicial ─────────────────────────────────────────────────────
_cache = {"data": None, "ts": None}

def _normalize(data: list) -> list:
    """Normaliza campos y convierte Timestamps a str."""
    for d in data:
        if 'titulo' in d and 'title'     not in d: d['title']     = d['titulo']
        if 'riesgo' in d and 'risk'      not in d: d['risk']      = d['riesgo']
        if 'fuente' in d and 'origin'    not in d: d['origin']    = d['fuente']
        if 'fecha'  in d and 'published' not in d: d['published'] = d['fecha']
        # Convertir cualquier Timestamp/datetime a str
        for key in ('published', 'fecha'):
            val = d.get(key)
            if val is not None and hasattr(val, 'isoformat'):
                d[key] = val.isoformat()
            elif val is not None and str(val) in ('NaT', 'nan', 'None'):
                d[key] = datetime.now().isoformat()
        # Mapear campos español→inglés antes de setdefault
        if not d.get('origin') or d.get('origin') == '?':
            d['origin'] = d.get('fuente') or d.get('feed') or 'Desconocido'
        if not d.get('title'):
            d['title'] = d.get('titulo', 'Sin título')
        if not d.get('risk'):
            d['risk'] = d.get('riesgo', 'Medio')
        d.setdefault('title',   d.get('titulo', 'Sin título'))
        d.setdefault('risk',    d.get('riesgo', 'Medio'))
        d.setdefault('origin',  d.get('fuente', 'Desconocido'))
        d.setdefault('region',  'Global')
        d.setdefault('lat',     0.0)
        d.setdefault('lon',     0.0)
        # Preservar campos especiales MalwareBazaar
        if 'botnet_family' not in d:
            d['botnet_family'] = ''
        if 'botnet_country' not in d:
            d['botnet_country'] = ''
    return data

def get_data() -> list:
    now = datetime.now()
    if _cache["data"] is None or _cache["ts"] is None or (now - _cache["ts"]).seconds > 600:
        print("[CACHE] Actualizando datos...")
        raw = load_cyber_data_list()
        _cache["data"] = _normalize(raw)
        _cache["ts"]   = now
        db.save_events(_cache["data"])
        db.cleanup_old_data()
        print(f"[CACHE] Cargados {len(_cache['data'])} eventos")
        for event in _cache["data"]:
            if event.get("risk") == "Crítico":
                send_telegram_alert(event)
    return _cache["data"]

# Carga inicial al arrancar (evita esperar el primer Interval)
print("[INIT] Cargando datos iniciales...")
try:
    _INITIAL_DATA = get_data()
    print(f"[INIT] {len(_INITIAL_DATA)} eventos listos")
except Exception as e:
    print(f"[INIT] Error en carga inicial (modo seguro): {e}")
    _INITIAL_DATA = []
    # Reset cache para que el primer Interval reintente
    _cache["data"] = None
    _cache["ts"]   = None

# ── Widget flotante: Ko-fi + links ───────────────────────────────────────────
KOFI_WIDGET = html.Div([
    # Ko-fi
    html.A(
        html.Img(src="https://storage.ko-fi.com/cdn/kofi3.png?v=3",
                 alt="Support on Ko-fi",
                 style={"height": "32px", "border": "0px"}),
        href="https://ko-fi.com/mcasrom",
        target="_blank",
        style={"textDecoration": "none", "display": "block", "marginBottom": "8px"},
    ),
    html.Hr(style={"borderColor": C["border"], "margin": "4px 0"}),
    # SIEG OSINT
    html.A("🌐 SIEG-OSINT",
           href=SIEG_OSINT_URL,
           target="_blank",
           style={"color": C["accent"], "textDecoration": "none",
                  "fontSize": "0.75rem", "display": "block", "marginBottom": "4px"}),
    # GitHub
    html.A("⚙️ GitHub",
           href=GITHUB_URL,
           target="_blank",
           style={"color": C["muted"], "textDecoration": "none",
                  "fontSize": "0.75rem", "display": "block"}),
], style={
    "position":     "fixed",
    "bottom":       "24px",
    "right":        "24px",
    "zIndex":       "9999",
    "background":   C["panel"],
    "border":       f"1px solid {C['border']}",
    "borderRadius": "8px",
    "padding":      "10px 14px",
    "boxShadow":    "0 4px 20px rgba(0,212,255,0.15)",
    "minWidth":     "130px",
})



# ── Layout ────────────────────────────────────────────────────────────────────
def build_layout():
    return html.Div([

        # Header
        html.Div([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        html.H1([
                            html.Span("🛡️ SIEG", style={"color": C["accent"]}),
                            html.Span(" · Cyber-Dash", style={"color": C["text"]}),
                        ], style={"fontSize": "2.5rem", "margin": "0"}),
                        html.P("Monitor de ciberamenazas en tiempo real · INCIBE · NVD · CISA · ANSSI · MalwareBazaar",
                               style={"color": C["muted"]}),
                    ], md=7),
                    dbc.Col([
                        html.Div(id="hero-status", style={"textAlign": "right"})
                    ], md=5),
                ]),
            ], fluid=False),  # fluid=False añade márgenes laterales automáticos
        ], style={"background": C["hero_bg"], "padding": "20px",
                  "borderBottom": f"1px solid {C['border']}"}),

        dbc.Container([
            dbc.Row(id="kpi-row",           className="mb-3 mt-3"),
            dbc.Row(id="advanced-kpis-row", className="mb-3"),

            dcc.Tabs([
                dcc.Tab(label="📊 Dashboard", children=[
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="risk-chart"),   md=6),
                        dbc.Col(dcc.Graph(id="origin-chart"), md=6),
                    ]),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="trend-chart"),  md=8),
                        dbc.Col(dcc.Graph(id="sector-chart"), md=4),
                    ]),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="geo-map"), md=12),
                    ]),
                ]),
                dcc.Tab(label="📋 Feed de Alertas", children=[
                    html.Div(id="events-table", className="mt-3")
                ]),
                dcc.Tab(label="📈 Tendencias", children=[
                    dbc.Row([
                        dbc.Col([
                            html.H4("Predicción de riesgo",   style={"color": C["accent"]}),
                            html.Div(id="prediction-card"),
                            html.Hr(),
                            html.H4("Actividad de Botnets",   style={"color": C["accent"]}),
                            html.Div(id="botnet-card"),
                        ], md=6),
                        dbc.Col([
                            html.H4("Sectores más vulnerables", style={"color": C["accent"]}),
                            html.Div(id="sector-list"),
                            html.Hr(),
                            html.H4("Resumen semanal",          style={"color": C["accent"]}),
                            html.Div(id="weekly-summary"),
                        ], md=6),
                    ])
                ]),

                dcc.Tab(label="📖 Metodología", children=[
                    dbc.Container([
                        dbc.Row([
                            dbc.Col([

                                # ── Sobre el proyecto ──
                                html.Div([
                                    html.H3("🛡️ SIEG-CYBER · Sistema de Inteligencia de Ciberamenazas",
                                            style={"color": C["accent"], "marginBottom": "8px"}),
                                    html.P([
                                        "SIEG-CYBER es un dashboard de monitorización de ciberamenazas en tiempo real, "
                                        "desarrollado como parte del ecosistema ",
                                        html.Strong("SIEG (Sistema de Inteligencia Estratégica Global)"),
                                        ". Agrega y analiza feeds RSS de las principales fuentes oficiales de ciberseguridad "
                                        "— INCIBE-CERT, NVD/NIST y CISA — clasificando automáticamente las alertas por "
                                        "severidad, sector y región geográfica."
                                    ], style={"color": C["text"], "lineHeight": "1.7"}),
                                ], style={"background": C["panel"], "border": f"1px solid {C['border']}",
                                          "borderLeft": f"4px solid {C['accent']}",
                                          "borderRadius": "8px", "padding": "20px", "marginBottom": "20px"}),

                                # ── Infraestructura ──
                                html.Div([
                                    html.H4("⚙️ Infraestructura · Odroid C2",
                                            style={"color": C["accent3"], "marginBottom": "12px"}),
                                    html.P([
                                        "El pipeline de datos corre en un ",
                                        html.Strong("Odroid C2"),
                                        " (ARM64, DietPi) en red local (192.168.1.147). "
                                        "Este servidor actúa como motor de scraping, procesamiento y sincronización con GitHub, "
                                        "desde donde Streamlit Cloud o Railway sirven el dashboard al público."
                                    ], style={"color": C["text"]}),
                                    html.Ul([
                                        html.Li("🖥️  Odroid C2 · DietPi · ARM64 · 2GB RAM", style={"color": C["text"]}),
                                        html.Li("🐍  Python 3.13 · Dash · Plotly · feedparser · SQLite", style={"color": C["text"]}),
                                        html.Li("⏱️  Cron cada 10 min · pipeline RSS → normalización → SQLite → GitHub push", style={"color": C["text"]}),
                                        html.Li("☁️  Deploy: Railway (producción) · GitHub como transporte de datos", style={"color": C["text"]}),
                                        html.Li("🔒  .env local · tokens fuera de git · .gitignore estricto", style={"color": C["text"]}),
                                    ], style={"paddingLeft": "20px", "lineHeight": "2"}),
                                ], style={"background": C["panel"], "border": f"1px solid {C['border']}",
                                          "borderLeft": f"4px solid {C['accent3']}",
                                          "borderRadius": "8px", "padding": "20px", "marginBottom": "20px"}),

                                # ── Fuentes y clasificación ──
                                html.Div([
                                    html.H4("📡 Fuentes de datos y clasificación de riesgo",
                                            style={"color": C["accent"], "marginBottom": "12px"}),
                                    dbc.Row([
                                        dbc.Col([
                                            html.H6("Fuentes RSS", style={"color": C["accent3"]}),
                                            html.Ul([
                                                html.Li("INCIBE-CERT · Vulnerabilidades y Avisos", style={"color": C["text"]}),
                                                html.Li("NVD/NIST · CVE feed + CVE Analyzed",     style={"color": C["text"]}),
                                                html.Li("CISA · Cybersecurity Advisories",         style={"color": C["text"]}),
                                            ]),
                                        ], md=6),
                                        dbc.Col([
                                            html.H6("Niveles de riesgo", style={"color": C["accent3"]}),
                                            html.Ul([
                                                html.Li([html.Span("🔴 Crítico", style={"color": C["critical"]}),
                                                         " — RCE, zero-day, CVSS ≥ 9.8"], style={"color": C["text"]}),
                                                html.Li([html.Span("🟠 Alto",    style={"color": C["alto"]}),
                                                         " — Privilege escalation, SQLi, XSS"], style={"color": C["text"]}),
                                                html.Li([html.Span("🔵 Medio",   style={"color": C["medio"]}),
                                                         " — Vulnerabilidades moderadas"], style={"color": C["text"]}),
                                                html.Li([html.Span("🟢 Bajo",    style={"color": C["bajo"]}),
                                                         " — Informativas, parches menores"], style={"color": C["text"]}),
                                            ]),
                                        ], md=6),
                                    ]),
                                ], style={"background": C["panel"], "border": f"1px solid {C['border']}",
                                          "borderRadius": "8px", "padding": "20px", "marginBottom": "20px"}),

                                # ── Históricos y rotación ──
                                html.Div([
                                    html.H4("🗄️ Política de datos · Históricos y rotación",
                                            style={"color": C["accent"], "marginBottom": "12px"}),
                                    html.P("El sistema mantiene una base de datos SQLite local con rotación automática:",
                                           style={"color": C["text"]}),
                                    html.Ul([
                                        html.Li("📅  Retención: 14 días de histórico de eventos",          style={"color": C["text"]}),
                                        html.Li("🔄  Limpieza automática en cada ciclo de actualización",   style={"color": C["text"]}),
                                        html.Li("💾  Tamaño estimado: < 5 MB en operación normal",          style={"color": C["text"]}),
                                        html.Li("🚫  Sin datos personales · solo metadatos de alertas públicas", style={"color": C["text"]}),
                                        html.Li("📤  GitHub actúa como transporte, no como almacén permanente", style={"color": C["text"]}),
                                    ], style={"paddingLeft": "20px", "lineHeight": "2"}),
                                ], style={"background": C["panel"], "border": f"1px solid {C['border']}",
                                          "borderLeft": f"4px solid {C['bajo']}",
                                          "borderRadius": "8px", "padding": "20px", "marginBottom": "20px"}),

                                # ── How-To alertas ──
                                html.Div([
                                    html.H4("📱 Cómo actuar ante una alerta crítica",
                                            style={"color": C["critical"], "marginBottom": "12px"}),
                                    html.P("Si el dashboard detecta un evento Crítico, recibirás una alerta en Telegram. "
                                           "Estos son los pasos recomendados:",
                                           style={"color": C["text"]}),
                                    html.Ol([
                                        html.Li([html.Strong("Identifica el sistema afectado"),
                                                 " — Lee el CVE o aviso y comprueba si usas el software/versión mencionada."],
                                                style={"color": C["text"], "marginBottom": "8px"}),
                                        html.Li([html.Strong("Consulta la fuente oficial"),
                                                 " — Accede a INCIBE (incibe.es), NVD (nvd.nist.gov) o CISA (cisa.gov) para el advisory completo."],
                                                style={"color": C["text"], "marginBottom": "8px"}),
                                        html.Li([html.Strong("Aplica el parche o mitigación"),
                                                 " — Sigue las instrucciones del vendor. Prioriza sistemas expuestos a Internet."],
                                                style={"color": C["text"], "marginBottom": "8px"}),
                                        html.Li([html.Strong("Verifica logs"),
                                                 " — Comprueba si hay indicios de explotación activa (IoCs publicados en el advisory)."],
                                                style={"color": C["text"], "marginBottom": "8px"}),
                                        html.Li([html.Strong("Reporta si es necesario"),
                                                 " — Si detectas un incidente real, contacta con INCIBE-CERT: incibe-cert@incibe.es · Tel: 017"],
                                                style={"color": C["text"]}),
                                    ], style={"paddingLeft": "20px", "lineHeight": "1.8"}),
                                    html.Hr(style={"borderColor": C["border"]}),
                                    html.P([
                                        "📲 Suscríbete a las alertas en Telegram: ",
                                        html.A(TELEGRAM_CHANNEL,
                                               href=f"https://t.me/{TELEGRAM_CHANNEL.lstrip('@')}",
                                               target="_blank",
                                               style={"color": C["accent"]}),
                                    ], style={"color": C["text"]}),
                                ], style={"background": C["panel"], "border": f"1px solid {C['critical']}",
                                          "borderRadius": "8px", "padding": "20px", "marginBottom": "20px"}),

                            ], md=12),
                        ]),
                    ], fluid=True, style={"paddingTop": "20px"}),
                ]),
            ]),
        ], fluid=True, style={"padding": "20px"}),

        # Footer
        html.Footer([
            dbc.Container([
                html.Hr(style={"borderColor": C["border"]}),
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Span("SIEG-CYBER · Datos INCIBE/NVD/CISA · ", style={"color": C["muted"]}),
                            html.Span("Actualización cada 10 min · ",           style={"color": C["muted"]}),
                            html.Span(id="footer-db-size",                      style={"color": C["accent"]}),
                        ], style={"fontSize": "0.75rem", "textAlign": "center", "marginBottom": "4px"}),
                        html.Div([
                            html.Span("© 2026 M. Castillo · ", style={"color": C["muted"]}),
                            html.A("mybloggingnotes@gmail.com",
                                   href="mailto:mybloggingnotes@gmail.com",
                                   style={"color": C["muted"], "textDecoration": "none"}),
                            html.Span(" · ", style={"color": C["muted"]}),
                            html.A("⚙️ GitHub",
                                   href="https://github.com/mcasrom/sieg-cyber-dash",
                                   target="_blank",
                                   style={"color": C["muted"], "textDecoration": "none"}),
                            html.Span(" · ", style={"color": C["muted"]}),
                            html.A(f"📢 Telegram {TELEGRAM_CHANNEL}",
                                   href=f"https://t.me/{TELEGRAM_CHANNEL.lstrip('@')}",
                                   target="_blank",
                                   style={"color": C["accent"], "textDecoration": "none", "fontWeight": "600"}),
                        ], style={"fontSize": "0.75rem", "textAlign": "center"}),
                    ], md=12),
                ]),
            ], fluid=True),
        ], style={"marginTop": "40px", "marginBottom": "20px"}),

        KOFI_WIDGET,

        # Interval + Store con datos iniciales ya cargados
        dcc.Interval(id="refresh", interval=600_000, n_intervals=0),
        dcc.Store(id="store-data", data=json.dumps(_INITIAL_DATA)),

    ], style={"background": C["bg"], "minHeight": "100vh"})


app        = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.layout = build_layout()
server     = app.server


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    [Output("store-data",     "data"),
     Output("hero-status",    "children"),
     Output("footer-db-size", "children")],
    Input("refresh", "n_intervals")
)
def refresh_data(n):
    data  = get_data()
    stats = db.get_stats()
    size  = db.get_size_mb()
    last_sync = db.get_last_sync()
    sync_str  = last_sync[:16] if last_sync else datetime.now().strftime("%Y-%m-%d %H:%M")
    status = html.Div([
        html.Span(f"📡 {len(data)} eventos", style={"color": C["accent"]}),
        html.Br(),
        html.Small(f"Histórico: {stats['total']} eventos · {stats['criticos']} críticos",
                   style={"color": C["muted"]}),
        html.Br(),
        html.Small(f"🕐 Sync: {sync_str}", style={"color": C["accent3"]}),
    ])
    return json.dumps(data), status, f"Base de datos: {size} MB"


def _empty_fig(title="Sin datos"):
    fig = go.Figure()
    fig.update_layout(**PLOTLY_BASE, title=title, height=400)
    return fig


@app.callback(
    [Output("kpi-row",           "children"),
     Output("advanced-kpis-row", "children"),
     Output("risk-chart",        "figure"),
     Output("origin-chart",      "figure"),
     Output("trend-chart",       "figure"),
     Output("sector-chart",      "figure"),
     Output("geo-map",           "figure"),
     Output("events-table",      "children"),
     Output("prediction-card",   "children"),
     Output("botnet-card",       "children"),
     Output("sector-list",       "children"),
     Output("weekly-summary",    "children")],
    Input("store-data", "data")
)
def update_all(json_data):
    # Fallback seguro si no hay datos aún
    if not json_data:
        empty_figs = [_empty_fig() for _ in range(5)]
        return ([], [], *empty_figs,
                html.Div("Cargando..."), html.Div(""), html.Div(""),
                html.Ul(), html.Div(""))

    try:
        data = json.loads(json_data)
    except Exception:
        empty_figs = [_empty_fig("Error de datos") for _ in range(5)]
        return ([], [], *empty_figs,
                html.Div("Error"), html.Div(""), html.Div(""),
                html.Ul(), html.Div(""))

    if not data:
        empty_figs = [_empty_fig("Sin datos disponibles") for _ in range(5)]
        return ([], [], *empty_figs,
                html.Div("Sin datos"), html.Div(""), html.Div(""),
                html.Ul(), html.Div(""))

    # KPIs avanzados
    trend_score  = kpis.calculate_trend_score(data)
    prediction   = kpis.predict_risk(data)
    sector_data  = kpis.sector_vulnerability(data)
    botnet_data  = kpis.botnet_activity(data)
    weekly       = kpis.weekly_summary(data)

    # KPIs principales
    risks       = [d.get('risk', 'Medio') for d in data]
    risk_counts = Counter(risks)
    total    = len(data)
    criticos = risk_counts.get('Crítico', 0)
    altos    = risk_counts.get('Alto', 0)

    kpi_row = [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("📊 Total", style={"color": C["muted"], "fontSize": "0.8rem"}),
            html.H2(total, style={"color": C["accent"], "fontSize": "2rem", "fontWeight": "700"}),
        ]), style={"background": C["panel"], "borderLeft": f"4px solid {C['accent']}"}), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("🔴 Críticos", style={"color": C["muted"], "fontSize": "0.8rem"}),
            html.H2(criticos, style={"color": C["critical"], "fontSize": "2rem", "fontWeight": "700"}),
            html.Small(f"Alto: {altos}", style={"color": C["muted"]}),
        ]), style={"background": C["panel"], "borderLeft": f"4px solid {C['critical']}"}), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("📈 Tendencia", style={"color": C["muted"], "fontSize": "0.8rem"}),
            html.H2(f"{trend_score}%", style={"color": C["accent3"], "fontSize": "2rem", "fontWeight": "700"}),
            html.Small(prediction['trend'], style={"color": C["accent3"]}),
        ]), style={"background": C["panel"], "borderLeft": f"4px solid {C['accent3']}"}), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4("🦠 Botnets", style={"color": C["muted"], "fontSize": "0.8rem"}),
            html.H2(botnet_data['total_detected'], style={"color": C["medio"], "fontSize": "2rem", "fontWeight": "700"}),
            html.Small(f"{botnet_data['active_families']} familias · {botnet_data['alert_level']}", style={"color": C["muted"]}),
        ]), style={"background": C["panel"], "borderLeft": f"4px solid {C['medio']}"}), width=3),
    ]

    advanced_row = [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("🎯 Predicción", style={"color": C["accent"]}),
            html.H3(prediction['level'], style={"color": RISK_COLOR.get(prediction['level'], C["accent"])}),
            html.P(f"Tendencia: {prediction['trend']}  |  Confianza: {prediction['confidence']}%"),
            html.Small(f"Eventos predichos: {prediction.get('predicted_events', 0)}", style={"color": C["muted"]}),
        ])), width=4),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("🏭 Top Sector", style={"color": C["accent"]}),
            html.H3(sector_data[0]['sector'] if sector_data else "N/D", style={"color": C["accent3"]}),
            html.P(f"{sector_data[0]['count'] if sector_data else 0} eventos", style={"color": C["muted"]}),
            html.Small(f"Nivel: {sector_data[0]['risk_level'] if sector_data else 'N/D'}", style={"color": C["muted"]}),
        ])), width=4),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("📅 Última semana", style={"color": C["accent"]}),
            html.H3(weekly['total'], style={"color": C["accent"]}),
            html.P(f"Críticos: {weekly['criticos']}  |  Alto: {weekly['alto']}"),
            html.Small(f"Top región: {weekly['top_region']}", style={"color": C["muted"]}),
        ])), width=4),
    ]

    # ── Figuras ───────────────────────────────────────────────────────────────
    risk_fig = go.Figure()
    if risk_counts:
        risk_fig.add_trace(go.Pie(
            labels=list(risk_counts.keys()),
            values=list(risk_counts.values()),
            hole=0.4,
            marker_colors=[RISK_COLOR.get(r, C["medio"]) for r in risk_counts.keys()],
            textinfo='percent+label',
        ))
    risk_fig.update_layout(**PLOTLY_BASE, title="Distribución por severidad", height=400)

    origins       = [d.get('origin', 'Unknown') for d in data]
    origin_counts = Counter(origins)
    origin_fig    = go.Figure()
    if origin_counts:
        origin_fig.add_trace(go.Bar(
            x=list(origin_counts.values()),
            y=list(origin_counts.keys()),
            orientation='h',
            marker_color=C["accent"],
        ))
    origin_fig.update_layout(**PLOTLY_BASE, title="Eventos por fuente", height=400)

    # Tendencia histórica desde SQLite (14 días reales)
    hist = db.get_historical_kpis(days=14)
    trend_fig = go.Figure()
    if hist:
        trend_fig.add_trace(go.Scatter(
            x=[h['day'] for h in hist],
            y=[h['total'] for h in hist],
            name='Total',
            mode='lines+markers',
            line=dict(color=C["accent"], width=2),
            fill='tozeroy',
            fillcolor='rgba(0, 212, 255, 0.08)',
        ))
        trend_fig.add_trace(go.Scatter(
            x=[h['day'] for h in hist],
            y=[h['criticos'] for h in hist],
            name='Críticos',
            mode='lines+markers',
            line=dict(color=C["critical"], width=2, dash='dot'),
        ))
        trend_fig.add_trace(go.Scatter(
            x=[h['day'] for h in hist],
            y=[h['altos'] for h in hist],
            name='Altos',
            mode='lines+markers',
            line=dict(color=C["alto"], width=1, dash='dot'),
        ))
    else:
        # Fallback: datos en memoria del RSS actual
        dates = []
        for d in data[:200]:
            try:
                pub = d.get('published', d.get('fecha', ''))
                if pub and isinstance(pub, str) and pub not in ('NaT', 'nan', 'None'):
                    dates.append(datetime.fromisoformat(pub[:19]).date())
            except Exception:
                pass
        if dates:
            date_counts  = Counter(dates)
            sorted_dates = sorted(date_counts.items())[-14:]
            trend_fig.add_trace(go.Scatter(
                x=[str(d[0]) for d in sorted_dates],
                y=[d[1]      for d in sorted_dates],
                name='Total',
                mode='lines+markers',
                line=dict(color=C["accent"], width=2),
                fill='tozeroy',
                fillcolor='rgba(0, 212, 255, 0.1)',
            ))
    last_sync = db.get_last_sync()
    sync_label = f"Último sync: {last_sync[:16]}" if last_sync else "Histórico 14 días"
    trend_fig.update_layout(**PLOTLY_BASE,
        title=f"Evolución histórica · {sync_label}",
        height=400,
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
    )

    sector_fig = go.Figure()
    if sector_data:
        sector_fig.add_trace(go.Bar(
            x=[s['count']  for s in sector_data],
            y=[s['sector'] for s in sector_data],
            orientation='h',
            marker_color=[RISK_COLOR.get(s['risk_level'], C["accent"]) for s in sector_data],
        ))
    sector_fig.update_layout(**PLOTLY_BASE, title="Sectores afectados", height=400)

    # ── Mapa mejorado: fuentes de amenazas + origen botnets ──────────────────
    geo_fig = go.Figure()

    # Capa 1: burbujas por región fuente (eventos por país)
    region_coords = {}
    for d in data:
        region = d.get('region', 'Global')
        lat, lon = d.get('lat'), d.get('lon')
        risk = d.get('risk', 'Medio')
        if lat and lon and lat != 0.0 and region != 'Global':
            if region not in region_coords:
                region_coords[region] = {'lat': lat, 'lon': lon, 'count': 0, 'criticos': 0}
            region_coords[region]['count'] += 1
            if risk == 'Crítico':
                region_coords[region]['criticos'] += 1

    for region, coords in region_coords.items():
        color = C["critical"] if coords['criticos'] > 2 else C["accent"]
        geo_fig.add_trace(go.Scattergeo(
            lon=[coords['lon']], lat=[coords['lat']],
            mode='markers+text',
            marker=dict(
                size=12 + min(25, coords['count'] * 2),
                color=color,
                opacity=0.75,
                line=dict(color='white', width=1),
            ),
            text=region,
            textposition="top center",
            textfont=dict(color="white", size=9),
            hovertext=f"<b>{region}</b><br>Eventos: {coords['count']}<br>Críticos: {coords['criticos']}",
            hoverinfo="text",
            name=region,
            showlegend=True,
        ))

    # Capa 2: origen botnets → líneas hacia España
    botnet_origins = get_botnet_origins(data)
    SPAIN_LAT, SPAIN_LON = 40.4168, -3.7038

    for origin in botnet_origins[:8]:  # top 8 orígenes
        lat_o = origin['lat']
        lon_o = origin['lon']
        count = origin['count']
        families = ", ".join(origin['families'][:3]) if origin['families'] else "desconocida"

        # Línea de ataque: origen → España
        geo_fig.add_trace(go.Scattergeo(
            lon=[lon_o, SPAIN_LON],
            lat=[lat_o, SPAIN_LAT],
            mode='lines',
            line=dict(width=max(1, min(4, count)), color=C["critical"]),
            opacity=0.4,
            hoverinfo='skip',
            showlegend=False,
        ))
        # Burbuja origen botnet
        geo_fig.add_trace(go.Scattergeo(
            lon=[lon_o], lat=[lat_o],
            mode='markers',
            marker=dict(
                size=10 + min(20, count * 3),
                color=C["accent2"],
                opacity=0.85,
                symbol='diamond',
                line=dict(color=C["critical"], width=2),
            ),
            hovertext=f"<b>🦠 Origen botnet: {origin['country']}</b><br>"
                      f"Detecciones: {count}<br>Familias: {families}",
            hoverinfo="text",
            name=f"Botnet: {origin['country']}",
            showlegend=True,
        ))

    # España como objetivo central
    geo_fig.add_trace(go.Scattergeo(
        lon=[SPAIN_LON], lat=[SPAIN_LAT],
        mode='markers+text',
        marker=dict(size=18, color=C["bajo"], symbol='star',
                    line=dict(color='white', width=2)),
        text="🛡️ España",
        textposition="bottom center",
        textfont=dict(color=C["bajo"], size=11),
        hovertext="<b>🛡️ España — Objetivo monitorizado</b>",
        hoverinfo="text",
        name="España (objetivo)",
        showlegend=True,
    ))

    geo_fig.update_layout(
        **PLOTLY_BASE,
        title=f"Mapa de amenazas · {len(botnet_origins)} orígenes botnet detectados",
        height=500,
        geo=dict(
            scope='world',
            projection_type='natural earth',
            showland=True,
            landcolor='#1a1f2e',
            showocean=True,
            oceancolor='#080a10',
            showcoastlines=True,
            coastlinecolor='#2a3048',
            showcountries=True,
            countrycolor='#1e2433',
            showframe=False,
        ),
        legend=dict(
            bgcolor='rgba(13,15,20,0.8)',
            bordercolor=C["border"],
            borderwidth=1,
            font=dict(size=9),
        ),
    )

    # ── Tabla ─────────────────────────────────────────────────────────────────
    table = dash_table.DataTable(
        data=[{
            'title':     str(d.get('title', d.get('titulo', '')))[:80],
            'risk':      str(d.get('risk',  d.get('riesgo', ''))),
            'origin':    str(d.get('origin', d.get('fuente', ''))),
            'region':    str(d.get('region', '')),
            'published': str(d.get('published', d.get('fecha', '')))[:16],
        } for d in data[:100]],
        columns=[
            {"name": "Descripción", "id": "title"},
            {"name": "Nivel",       "id": "risk"},
            {"name": "Fuente",      "id": "origin"},
            {"name": "Región",      "id": "region"},
            {"name": "Fecha",       "id": "published"},
        ],
        style_table={"overflowX": "auto"},
        style_cell={
            "background": C["panel"], "color": C["text"],
            "border": f"1px solid {C['border']}", "padding": "8px",
        },
        style_header={"background": C["hero_bg"], "color": C["accent"], "fontWeight": "700"},
        style_data_conditional=[
            {"if": {"filter_query": '{risk} = "Crítico"'}, "color": C["critical"], "fontWeight": "700"},
        ],
        page_size=20,
    )

    # ── Cards tendencias ──────────────────────────────────────────────────────
    pred_color = RISK_COLOR.get(prediction['level'], C["accent"])
    prediction_card = html.Div([
        html.Div([
            html.H3(prediction['level'],
                    style={"color": pred_color, "display": "inline", "marginRight": "10px"}),
            html.Span(prediction['trend'], style={"color": C["accent3"], "fontSize": "1.5rem"}),
        ]),
        html.P(f"Confianza: {prediction['confidence']}%", style={"color": C["muted"]}),
        html.P(f"Críticos última semana: {prediction['last_week_criticos']} "
               f"vs {prediction['prev_week_criticos']} semana anterior"),
        html.Progress(value=str(prediction['confidence']), max="100", style={"width": "100%"}),
    ])

    botnet_card = html.Div([
        html.P(f"🦠 Total detecciones: {botnet_data['total_detected']}", style={"color": C["accent"]}),
        html.P(f"Familias activas: {botnet_data['active_families']}",    style={"color": C["accent3"]}),
        html.Ul([html.Li(f"{f}: {c}", style={"color": C["text"]}) for f, c in botnet_data['top_families'][:3]]),
    ])

    sector_list = html.Ul([
        html.Li(f"{s['sector']}: {s['count']} eventos ({s['risk_level']})",
                style={"color": RISK_COLOR.get(s['risk_level'], C["text"])})
        for s in sector_data
    ])

    weekly_summary = html.Div([
        html.P(f"📊 Total: {weekly['total']} eventos",                  style={"color": C["accent"]}),
        html.P(f"🔴 Críticos: {weekly['criticos']}  |  🟠 Alto: {weekly['alto']}"),
        html.P(f"🌍 Región más afectada: {weekly['top_region']} ({weekly['top_region_count']} eventos)"),
    ])

    return (kpi_row, advanced_row, risk_fig, origin_fig, trend_fig, sector_fig,
            geo_fig, table, prediction_card, botnet_card, sector_list, weekly_summary)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8055))
    app.run(host="0.0.0.0", port=port, debug=False)
