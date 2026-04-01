"""
Cache manager optimizado para memoria limitada
"""
import json
import hashlib
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class LiteCache:
    """Cache en memoria con límite de tamaño"""
    def __init__(self, max_size_mb=50):
        self.cache = {}
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size = 0
        logger.info(f"Cache inicializado: {max_size_mb}MB máximo")
    
    def _get_size(self, obj):
        """Estima tamaño en memoria (simple)"""
        try:
            return len(json.dumps(obj, default=str))
        except:
            return 1000
    
    def set(self, key, value, ttl_seconds=600):
        """Guarda en cache con TTL"""
        size = self._get_size(value)
        
        if self.current_size + size > self.max_size_bytes:
            self._cleanup()
        
        self.cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl_seconds),
            'size': size
        }
        self.current_size += size
    
    def get(self, key):
        """Obtiene de cache si no expiró"""
        item = self.cache.get(key)
        if item and datetime.now() < item['expires']:
            return item['value']
        elif item:
            self.current_size -= item['size']
            del self.cache[key]
        return None
    
    def _cleanup(self):
        """Limpia items expirados"""
        now = datetime.now()
        expired = [k for k, v in self.cache.items() if now >= v['expires']]
        
        for k in expired:
            self.current_size -= self.cache[k]['size']
            del self.cache[k]
        
        if self.current_size > self.max_size_bytes:
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1]['expires'])
            for k, v in sorted_items[:10]:
                self.current_size -= v['size']
                del self.cache[k]
    
    def clear(self):
        self.cache.clear()
        self.current_size = 0

_cache = LiteCache()

def cache_result(ttl=600):
    """Decorador para cachear resultados"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}_{hashlib.md5(str(args).encode()).hexdigest()}"
            result = _cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                _cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator
