"""키-값 저장소. set / get / delete 세 함수만 바깥에 내놓는다.

해시 테이블에는 (값, 만료 시점) 묶음을 값으로 넣는다.
"""
import threading
import time

from mini_redis.hashtable import HashTable

NEVER_EXPIRES = None


class Store:
    CLEANUP_INTERVAL = 0.1   # 주기적 정리 사이에 쉬는 시간(초)
    CLEANUP_BUCKETS = 256    # 주기적 정리 한 번에 보는 칸 수

    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock
        # 재진입할 수 없는 lock이다. lock을 잡은 채로 set / get / delete를 다시 부르면 멈춘다.
        self._lock = threading.Lock()
        self._cleanup_cursor = 0   # 다음 주기적 정리를 몇 번 칸부터 볼지

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

    def cleanup_expired_once(self):
        """칸 CLEANUP_BUCKETS개를 훑어 만료된 키를 지운다. 지운 키 수를 돌려준다.

        아무도 조회하지 않는 만료 키를 치우는 보조 장치다. 응답이 맞는지는 여전히 지연 삭제가 책임진다.
        lock 안에서 self.delete를 부르면 멈추므로 self._table.remove를 직접 쓴다.
        """
        with self._lock:
            self._cleanup_cursor, items = self._table.scan(self._cleanup_cursor, self.CLEANUP_BUCKETS)
            removed = 0
            for key, (_, expire_at) in items:
                if self._is_expired(expire_at):
                    self._table.remove(key)
                    removed += 1
            return removed

    def run_cleanup(self, stop):
        """stop(threading.Event)이 켜질 때까지 CLEANUP_INTERVAL초마다 주기적 정리를 한다.

        백그라운드 스레드에서 돌린다. 스레드는 server.py에서 서버를 실행할 때 한 번만 켠다.
        """
        while not stop.wait(self.CLEANUP_INTERVAL):
            self.cleanup_expired_once()

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
