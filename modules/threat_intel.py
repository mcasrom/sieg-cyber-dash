"""
Inteligencia de amenazas - Botnets y OSINT ligero
"""
import requests
from datetime import datetime
import logging
from .cache_manager import cache_result

logger = logging.getLogger(__name__)

BOTNET_FAMILIES = {
    'Emotet': ['emotet', 'geodo'],
    'Trickbot': ['trickbot', 'trickloader'],
    'Dridex': ['dridex', 'bugat'],
    'LockBit': ['lockbit', 'lockbit3'],
    'Mirai': ['mirai', 'okiru', 'satori'],
    'Gafgyt': ['gafgyt', 'bashlite'],
}

BOTNET_SOURCES = {
    'Rusia': ['ru', 'russian', 'moscow'],
    'China': ['cn', 'china', 'beijing'],
    'Ucrania': ['ua', 'ukraine'],
    'EEUU': ['us', 'usa', 'america'],
}

class ThreatIntel:
    def __init__(self):
        pass
    
    def detect_botnet_family(self, text):
        text_lower = text.lower()
        for family, keywords in BOTNET_FAMILIES.items():
            if any(kw in text_lower for kw in keywords):
                return family
        return None
    
    def detect_botnet_source(self, text):
        text_lower = text.lower()
        for source, keywords in BOTNET_SOURCES.items():
            if any(kw in text_lower for kw in keywords):
                return source
        return 'Desconocido'
    
    @cache_result(ttl=600)
    def get_botnet_threats(self):
        threats = []
        
        try:
            resp = requests.get('https://urlhaus.abuse.ch/downloads/csv_recent/', timeout=10)
            if resp.status_code == 200:
                for line in resp.text.split('\n')[1:100]:
                    if line and 'botnet' in line.lower():
                        threats.append({
                            'source': 'URLhaus',
                            'family': self.detect_botnet_family(line),
                            'timestamp': datetime.now().isoformat(),
                            'origin': self.detect_botnet_source(line)
                        })
        except Exception as e:
            logger.error(f"Error URLhaus: {e}")
        
        logger.info(f"Recuperadas {len(threats)} amenazas")
        return threats
    
    def get_botnet_map_data(self):
        threats = self.get_botnet_threats()
        origin_coords = {
            'Rusia': {'lat': 61.5240, 'lon': 105.3188},
            'China': {'lat': 35.8617, 'lon': 104.1954},
            'Ucrania': {'lat': 48.3794, 'lon': 31.1656},
            'EEUU': {'lat': 37.0902, 'lon': -95.7129},
            'Desconocido': {'lat': 0, 'lon': 0}
        }
        
        map_data = []
        for t in threats:
            origin = t.get('origin', 'Desconocido')
            coords = origin_coords.get(origin, origin_coords['Desconocido'])
            map_data.append({
                'family': t.get('family', 'Desconocido'),
                'origin': origin,
                'lat': coords['lat'],
                'lon': coords['lon']
            })
        return map_data
