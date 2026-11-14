"""키-값 저장소. set / get / delete 세 함수만 바깥에 내놓는다.

해시 테이블에는 (값, 만료 시점) 묶음을 값으로 넣는다.
"""
import threading
import time

from mini_redis.hashtable import HashTable

NEVER_EXPIRES = None


class Store:
    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock
        # 재진입할 수 없는 lock이다. lock을 잡은 채로 set / get / delete를 다시 부르면 멈춘다.
        self._lock = threading.Lock()

    def set(self, key, value, ttl=None):
        """이미 있는 키면 값과 만료 시점을 모두 새로 정한다. ttl(초)이 없으면 만료되지 않는다."""
        with self._lock:
            self._table.put(key, (value, self._expire_at(ttl)))

    def get(self, key):
        """없거나 만료된 키면 None."""
        with self._lock:
            entry = self._find_live_entry(key)
            if entry is None:
                return None
            value, _ = entry
            return value

    def delete(self, key):
        """지웠으면 True, 없거나 만료된 키면 False."""
        with self._lock:
            if self._find_live_entry(key) is None:
                return False
            self._table.remove(key)
            return True

    def _expire_at(self, ttl):
        return NEVER_EXPIRES if ttl is None else self._clock() + ttl

    def _find_live_entry(self, key):
        """만료된 키는 찾은 김에 지우고 None을 돌려준다 (지연 삭제)."""
        entry = self._table.get(key)
        if entry is None:
            return None
        _, expire_at = entry
        if self._is_expired(expire_at):
            self._table.remove(key)
            return None
        return entry

    def _is_expired(self, expire_at):
        return expire_at is not NEVER_EXPIRES and self._clock() >= expire_at
