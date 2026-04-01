# 🛡️ SIEG-CYBER · Monitor de Ciberamenazas

[![Deploy](https://img.shields.io/badge/deploy-Render-46E3B7?logo=render)](https://sieg-cyber-dash.onrender.com)
[![Python](https://img.shields.io/badge/python-3.13-blue?logo=python)](https://python.org)
[![Dash](https://img.shields.io/badge/dash-2.14-informational?logo=plotly)](https://dash.plotly.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Dashboard de inteligencia de ciberamenazas en tiempo real. Parte del ecosistema **[SIEG · Sistema de Inteligencia Estratégica Global](https://mcasrom.github.io/sieg-osint)**.

🔗 **Dashboard público:** https://sieg-cyber-dash.onrender.com  
📢 **Alertas Telegram:** [@sieg_politica_bot](https://t.me/sieg_politica_bot)  
☕ **Apoya el proyecto:** [Ko-fi](https://ko-fi.com/mcasrom)

---

## 📡 Fuentes de datos

| Fuente | Tipo | Región |
|--------|------|--------|
| INCIBE-CERT | Vulnerabilidades + Avisos | España |
| CSIRT.es | Alertas nacionales | España |
| NVD/NIST | CVE feed + CVE Analyzed | EEUU |
| CISA | Cybersecurity Advisories | EEUU |
| ENISA | Threat intelligence | UE |
| BSI | Sicherheitswarnungen | Alemania |
| ANSSI | Advisories CERT-FR | Francia |
| CERT-EU | Threat intelligence | UE |
| Abuse.ch URLhaus | URLs maliciosas | Global |
| Feodo Tracker | C2 botnets activos | Global |
| MalwareBazaar | Muestras de malware | Global |

## 🎯 Clasificación de riesgo

| Nivel | Criterios |
|-------|-----------|
| 🔴 Crítico | RCE, Zero-day, CVSS ≥ 9.8, C2 activo |
| 🟠 Alto | Privilege escalation, SQLi, XSS, CVSS 7-9.7 |
| 🔵 Medio | Vulnerabilidades moderadas |
| 🟢 Bajo | Informativas, parches menores |

## ⚙️ Infraestructura

```
Odroid C2 (DietPi · ARM64)
    │
    ├── Pipeline RSS (cron cada 10 min)
    │       feedparser → normalización → SQLite (14 días)
    │
    ├── GitHub (transporte de código)
    │
    └── Render.com (deploy público)
            Dash + Gunicorn → sieg-cyber-dash.onrender.com
```

## 🚀 Instalación local

```bash
git clone https://github.com/mcasrom/sieg-cyber-dash.git
cd sieg-cyber-dash
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
nano .env  # añadir TELEGRAM_TOKEN y TELEGRAM_CHAT_ID

python app.py
# → http://localhost:8055
```

## 📁 Estructura

```
sieg-cyber-dash/
├── app.py                  # Dashboard principal (Dash)
├── data_loader.py          # Scraping RSS + Feodo + Bazaar
├── requirements.txt
├── Procfile                # Deploy Render/Railway
├── modules/
│   ├── historical_db.py    # SQLite · retención 14 días
│   ├── advanced_kpis.py    # KPIs, predicción, botnets
│   ├── geo_spain.py        # Geolocalización regional
│   ├── telegram_bot.py     # Alertas críticas
│   ├── threat_intel.py     # Inteligencia de amenazas
│   └── cache_manager.py    # Caché en memoria
└── data/
    └── cyber_historical.db # SQLite local (gitignored)
```

## 🗄️ Política de datos

- **Retención:** 14 días de histórico de eventos
- **Limpieza:** automática en cada ciclo de actualización
- **Tamaño estimado:** < 5 MB en operación normal
- **Datos personales:** ninguno — solo metadatos de alertas públicas
- **GitHub:** transporte de código, no de datos

## 📱 Alertas Telegram

El bot envía alertas automáticas para eventos **Críticos** incluyendo:
- Título y descripción del evento
- Fuente y región de origen
- Enlace directo al dashboard

Suscríbete: [@sieg_politica_bot](https://t.me/sieg_politica_bot)

## 🔧 Cron en Odroid

```bash
# Ver crons activos
crontab -l

# Pipeline de datos cada 10 minutos
*/10 * * * * cd ~/sieg-cyber-dash && python3 data_loader.py >> ~/logs/cyber.log 2>&1

# Ping a Render para evitar sleep (cada 14 min)
*/14 * * * * curl -s https://sieg-cyber-dash.onrender.com/ > /dev/null
```

## 🌐 Ecosistema SIEG

| Proyecto | Descripción |
|----------|-------------|
| [SIEG-Hub](https://mcasrom.github.io/sieg-osint) | Portal principal OSINT |
| [SIEG-Conflicts](https://github.com/mcasrom/SIEG-Conflicts) | Monitor de conflictos geopolíticos |
| [SIEG-Energia](https://github.com/mcasrom/sieg-energia) | Monitor de mercados energéticos |
| [SIEG-Politica](https://github.com/mcasrom/SIEG-Politica-Nacional) | Análisis político nacional |
| [Narrative Radar](https://fake-news-narrative.streamlit.app) | Detector de desinformación |
| **SIEG-CYBER** | Monitor de ciberamenazas ← estás aquí |

---

*Desarrollado por [M. Castillo](mailto:mcasrom@gmail.com) · Madrid, España*  
*Datos de fuentes públicas oficiales: INCIBE, NVD, CISA, ENISA, BSI, ANSSI, Abuse.ch*
