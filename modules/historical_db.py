"""
Histórico con SQLite - Rotación automática 14 días
"""
import sqlite3
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class HistoricalDB:
    def __init__(self, db_path="data/cyber_historical.db", max_days=14):
        self.db_path = db_path
        self.max_days = max_days
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        logger.info(f"HistoricalDB inicializado: {db_path}")
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    risk TEXT,
                    origin TEXT,
                    region TEXT,
                    lat REAL,
                    lon REAL,
                    published TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_published ON events(published)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_risk ON events(risk)")
            conn.commit()
    
    def save_events(self, data_list):
        """Guarda lista de eventos (no DataFrame)"""
        if not data_list:
            return 0
        
        saved = 0
        with sqlite3.connect(self.db_path) as conn:
            for d in data_list:
                try:
                    # Obtener campos con nombres en español o inglés
                    event_id = d.get('id')
                    title = d.get('titulo', d.get('title', ''))[:200]
                    risk = d.get('riesgo', d.get('risk', 'Medio'))
                    origin = d.get('fuente', d.get('origin', 'Unknown'))
                    region = d.get('region', 'Global')
                    lat = d.get('lat', 0.0)
                    lon = d.get('lon', 0.0)
                    published = d.get('fecha', d.get('published', datetime.now().isoformat()))
                    # Convertir Timestamp/datetime a str para SQLite
                    if hasattr(published, 'isoformat'):
                        published = published.isoformat()
                    elif published is None or str(published) in ('NaT', 'nan'):
                        published = datetime.now().isoformat()
                    else:
                        published = str(published)
                    
                    conn.execute("""
                        INSERT OR IGNORE INTO events 
                        (id, title, risk, origin, region, lat, lon, published)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id, title, risk, origin, region, lat, lon, published))
                    saved += 1
                except Exception as e:
                    logger.error(f"Error guardando evento: {e}")
            conn.commit()
        logger.info(f"Guardados {saved} eventos en histórico")
        return saved
    
    def get_trend_data(self, days=14):
        """Obtiene datos de tendencia"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    date(published) as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN risk='Crítico' THEN 1 ELSE 0 END) as critical,
                    SUM(CASE WHEN risk='Alto' THEN 1 ELSE 0 END) as high,
                    region
                FROM events
                WHERE published >= date('now', ?)
                GROUP BY day, region
                ORDER BY day DESC
            """, (f'-{days} days',))
            return cursor.fetchall()
    
    def cleanup_old_data(self):
        """Limpia datos antiguos"""
        cutoff = datetime.now() - timedelta(days=self.max_days)
        with sqlite3.connect(self.db_path) as conn:
            deleted = conn.execute(
                "DELETE FROM events WHERE date(published) < date(?)",
                (cutoff.date().isoformat(),)
            ).rowcount
            conn.commit()
            if deleted:
                logger.info(f"Limpieza: {deleted} eventos eliminados")
            return deleted
    
    def get_stats(self):
        """Estadísticas rápidas"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                criticos = conn.execute("SELECT COUNT(*) FROM events WHERE risk='Crítico'").fetchone()[0]
                return {'total': total, 'criticos': criticos}
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
            return {'total': 0, 'criticos': 0}
    

    def get_historical_kpis(self, days=14):
        """KPIs históricos por día para gráfico de tendencia real"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT
                        date(published)                                          AS day,
                        COUNT(*)                                                 AS total,
                        SUM(CASE WHEN risk='Crítico' THEN 1 ELSE 0 END)         AS criticos,
                        SUM(CASE WHEN risk='Alto'    THEN 1 ELSE 0 END)         AS altos,
                        SUM(CASE WHEN risk='Medio'   THEN 1 ELSE 0 END)         AS medios
                    FROM events
                    WHERE published >= date('now', ?)
                    GROUP BY day
                    ORDER BY day ASC
                """, (f'-{days} days',))
                rows = cursor.fetchall()
                return [{'day': r[0], 'total': r[1], 'criticos': r[2],
                         'altos': r[3], 'medios': r[4]} for r in rows]
        except Exception as e:
            logger.error(f"Error get_historical_kpis: {e}")
            return []

    def get_last_sync(self):
        """Timestamp del último evento guardado"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT MAX(created_at) FROM events"
                ).fetchone()
                return row[0] if row and row[0] else None
        except:
            return None
    def get_size_mb(self):
        """Obtiene tamaño de la base de datos en MB"""
        try:
            size = os.path.getsize(self.db_path)
            return round(size / (1024 * 1024), 2)
        except:
            return 0
