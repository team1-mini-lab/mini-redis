import threading
from mini_redis.hash_table import HashTable

class Store:
    """저장소 (접점 1). 실제 저장은 HashTable이 하고, 여기는 창구 역할만 한다. """
    def __init__(self):
        self._table = HashTable()
        self._lock = threading.Lock()

    def set(self, key, value, ttl=None):
        with self._lock:
            self._table.set(key, value, ttl)
    
    def get(self, key):
        with self._lock:
            return self._table.get(key)
    
    def delete(self, key):
        with self._lock:
            return self._table.delete(key)
    