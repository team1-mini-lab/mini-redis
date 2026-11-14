import random
import threading
import time

from mini_redis.hash_table import HashTable

class Store:
    """저장소 (접점 1). 실제 저장은 HashTable이 하고, 여기는 창구 역할만 한다. """
    def __init__(self, cleanup_interval=1.0):
        self._table = HashTable()
        self._lock = threading.Lock()
        self._start_cleanup(cleanup_interval)

    def set(self, key, value, ttl=None):
        with self._lock:
            self._table.set(key, value, ttl)
    
    def get(self, key):
        with self._lock:
            return self._table.get(key)
    
    def delete(self, key):
        with self._lock:
            return self._table.delete(key)

    def _all_keys(self):
        keys = []
        for head in self._table.buckets:
            node = head
            while node is not None:
                keys.append(node.key)
                node = node.next
        return keys

    def _cleanup_once(self):
        with self._lock:
            keys = self._all_keys()
            if not keys:
                return
            sample = random.sample(keys, min(20, len(keys)))
            for key in sample:
                self._table.get(key)

    def _cleanup_loop(self, interval):
        while True:
            time.sleep(interval)
            try:
                self._cleanup_once()
            except Exception:
                pass

    def _start_cleanup(self, interval):
        t = threading.Thread(target=self._cleanup_loop, args=(interval,), daemon=True)
        t.start()
    