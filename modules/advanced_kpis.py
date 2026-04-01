"""
KPIs avanzados - Análisis de tendencias y predicciones
"""
from collections import Counter
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AdvancedKPIs:
    def __init__(self, db=None):
        self.db = db
    
    def calculate_trend_score(self, data_list):
        """Calcula score de tendencia (0-100) basado en eventos recientes"""
        if len(data_list) < 5:
            return 50
        
        risks = [d.get('riesgo', d.get('risk', 'Medio')) for d in data_list]
        risk_counts = Counter(risks)
        total = len(data_list)
        criticos = risk_counts.get('Crítico', 0)
        altos = risk_counts.get('Alto', 0)
        
        score = (criticos * 40 + altos * 20) / max(total, 1)
        return min(100, int(score))
    
    def predict_risk(self, data_list):
        """Predicción simple de riesgo"""
        if len(data_list) < 10:
            return {'level': 'Moderado', 'trend': '→', 'confidence': 50}
        
        recent = []
        for d in data_list[:100]:
            try:
                fecha = d.get('fecha', d.get('published', ''))
                if isinstance(fecha, str):
                    fecha = datetime.fromisoformat(fecha[:19])
                recent.append({
                    'date': fecha,
                    'risk': d.get('riesgo', d.get('risk', 'Medio'))
                })
            except:
                pass
        
        if len(recent) < 5:
            return {'level': 'Moderado', 'trend': '→', 'confidence': 50}
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        
        last_week = [r for r in recent if week_ago <= r['date'] <= now]
        prev_week = [r for r in recent if two_weeks_ago <= r['date'] < week_ago]
        
        last_crit = sum(1 for r in last_week if r['risk'] == 'Crítico')
        prev_crit = sum(1 for r in prev_week if r['risk'] == 'Crítico')
        
        if last_crit > prev_crit * 1.5:
            trend = '↑↑'
            level = 'CRÍTICO'
            confidence = 80
        elif last_crit > prev_crit:
            trend = '↑'
            level = 'ELEVADO'
            confidence = 70
        elif last_crit < prev_crit * 0.5:
            trend = '↓↓'
            level = 'BAJO'
            confidence = 75
        elif last_crit < prev_crit:
            trend = '↓'
            level = 'MODERADO'
            confidence = 65
        else:
            trend = '→'
            level = 'MODERADO'
            confidence = 60
        
        return {
            'level': level,
            'trend': trend,
            'confidence': confidence,
            'last_week_criticos': last_crit,
            'prev_week_criticos': prev_crit,
            'predicted_events': int(last_crit * 1.2) if last_crit > prev_crit else int(last_crit * 0.9)
        }
    
    def sector_vulnerability(self, data_list):
        """Identifica sectores más afectados"""
        sectores = {
            'Sanidad': ['hospital', 'salud', 'health', 'médic', 'clinic', 'farmacia'],
            'Banca': ['bank', 'banco', 'financ', 'pago', 'payment', 'tarjeta'],
            'Infraestructura': ['energia', 'energy', 'electric', 'agua', 'water'],
            'Gobierno': ['gobierno', 'government', 'admin', 'ministerio'],
            'Industria': ['industrial', 'manufactur', 'scada', 'ics'],
            'Telecom': ['telecom', 'internet', 'network', '5g'],
            'Educación': ['educacion', 'education', 'universidad', 'school'],
            'Software/IT': ['software', 'windows', 'linux', 'cve', 'vulnerabilidad']
        }
        
        sector_counts = {s: 0 for s in sectores}
        for d in data_list[:200]:
            title = d.get('titulo', d.get('title', '')).lower()
            for sector, keywords in sectores.items():
                if any(kw in title for kw in keywords):
                    sector_counts[sector] += 1
                    break
        
        sorted_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)
        return [{'sector': s, 'count': c, 'risk_level': 'Alto' if c > 10 else 'Medio' if c > 3 else 'Bajo'} 
                for s, c in sorted_sectors if c > 0][:5]
    
    def botnet_activity(self, data_list):
        """Detecta actividad de botnets por keywords y campo botnet_family"""
        botnet_keywords = {
            'Mirai':         ['mirai', 'iot botnet', 'dvr exploit'],
            'Emotet':        ['emotet', 'geodo', 'maldoc'],
            'Trickbot':      ['trickbot', 'trickloader'],
            'LockBit':       ['lockbit', 'ransomware'],
            'Dridex':        ['dridex', 'bugat'],
            'Gafgyt':        ['gafgyt', 'bashlite'],
            'AgentTesla':    ['agenttesla', 'agent tesla'],
            'RedLine':       ['redline stealer', 'redlinestealer'],
            'Lumma':         ['lumma', 'lummac'],
            'AsyncRAT':      ['asyncrat'],
            'NjRAT':         ['njrat', 'bladabindi'],
            'Cobalt Strike': ['cobalt strike', 'cobaltstrike'],
        }

        detected = []
        for d in data_list[:500]:
            title   = d.get('titulo', d.get('title', '')).lower()
            resumen = d.get('resumen', d.get('summary', '')).lower()
            bf      = str(d.get('botnet_family', '') or '').strip('"\' ').lower()

            matched_family = None

            # 1. Campo botnet_family directo (MalwareBazaar)
            if bf and bf not in ('n/a', 'none', '', 'unknown', 'nan', 'null'):
                for family, keywords in botnet_keywords.items():
                    if any(kw in bf for kw in keywords) or bf == family.lower():
                        matched_family = family
                        break
                if not matched_family:
                    matched_family = bf.title()

            # 2. Buscar en title + resumen
            if not matched_family:
                for family, keywords in botnet_keywords.items():
                    if any(kw in title or kw in resumen for kw in keywords):
                        matched_family = family
                        break

            if matched_family:
                detected.append({
                    'family':  matched_family,
                    'title':   title[:80],
                    'source':  d.get('fuente', d.get('origin', 'Unknown')),
                    'country': d.get('botnet_country') or d.get('region', 'Global'),
                })

        family_counts = Counter([d['family'] for d in detected])

        return {
            'total_detected':  len(detected),
            'active_families': len(family_counts),
            'top_families':    family_counts.most_common(5),
            'recent_threats':  detected[:10],
            'alert_level':     'CRÍTICO' if len(detected) > 20 else 'Alto' if len(detected) > 10 else 'Moderado',
        }

    def weekly_summary(self, data_list):
        """Resumen semanal"""
        from datetime import datetime
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        last_week = []
        for d in data_list:
            try:
                fecha = d.get('fecha', d.get('published', ''))
                if isinstance(fecha, str):
                    fecha = datetime.fromisoformat(fecha[:19])
                if fecha >= week_ago:
                    last_week.append(d)
            except:
                pass
        
        if not last_week:
            return {'total': 0, 'criticos': 0, 'alto': 0, 'top_region': 'N/D'}
        
        risks = [d.get('riesgo', d.get('risk', 'Medio')) for d in last_week]
        risk_counts = Counter(risks)
        
        regions = [d.get('region', 'Global') for d in last_week]
        region_counts = Counter(regions)
        
        return {
            'total': len(last_week),
            'criticos': risk_counts.get('Crítico', 0),
            'alto': risk_counts.get('Alto', 0),
            'medio': risk_counts.get('Medio', 0),
            'bajo': risk_counts.get('Bajo', 0),
            'top_region': region_counts.most_common(1)[0][0] if region_counts else 'N/D',
            'top_region_count': region_counts.most_common(1)[0][1] if region_counts else 0
        }
