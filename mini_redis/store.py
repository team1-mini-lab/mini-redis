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

    def __init__(self, clock=time.monotonic, wall_clock=time.time):
        self._table = HashTable()
        self._clock = clock               # 실행 중 만료 판단용. 컴퓨터 시계가 바뀌어도 뒤로 가지 않는다
        self._wall_clock = wall_clock     # 스냅샷 파일에 적는 만료 시각용. 재부팅해도 뜻이 같다
        # 재진입할 수 없는 lock이다. lock을 잡은 채로 set / get / delete를 다시 부르면 멈춘다.
        self._lock = threading.Lock()
        self._cleanup_cursor = 0   # 다음 주기적 정리를 몇 번 칸부터 볼지
        self._changed = False      # 마지막 스냅샷 뒤에 set·delete가 있었는지

    def set(self, key, value, ttl=None):
        """이미 있는 키면 값과 만료 시점을 모두 새로 정한다. ttl(초)이 없으면 만료되지 않는다."""
        with self._lock:
            self._table.put(key, (value, self._expire_at(ttl)))
            self._changed = True

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
            self._changed = True
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

    def has_changes(self):
        """마지막 스냅샷 뒤에 set·delete가 있었으면 True. 만료로 지워진 것은 바뀜으로 치지 않는다."""
        with self._lock:
            return self._changed

    def snapshot_items(self):
        """스냅샷의 빠른 단계: 살아 있는 키를 [{key, value, expire}, ...] list로 모은다.

        lock 안에서는 이 list만 만들고, JSON으로 바꾸고 파일에 쓰는 느린 단계는 lock 밖에서 한다.
        expire는 벽시계(time.time) 기준 만료 시각이고, 만료가 없으면 None이다.
        모으는 순간 바뀜 표시를 끈다. 파일 쓰기에 실패하면 mark_changed()로 다시 켠다.
        """
        with self._lock:
            items = []
            cursor = 0
            while True:
                cursor, entries = self._table.scan(cursor, self._table.capacity)
                for key, (value, expire_at) in entries:
                    if not self._is_expired(expire_at):
                        items.append({"key": key, "value": value, "expire": self._to_wall_time(expire_at)})
                if cursor == 0:
                    break
            self._changed = False
            return items

    def mark_changed(self):
        with self._lock:
            self._changed = True

    def restore(self, items):
        """스냅샷 파일에서 읽은 [{key, value, expire}, ...]로 저장소를 채운다. 넣은 키 수를 돌려준다.

        꺼져 있던 동안 만료 시각이 이미 지난 키는 넣지 않는다.
        lock 안에서 self.set을 부르면 멈추므로 self._table.put을 직접 쓴다.
        """
        with self._lock:
            restored = 0
            for item in items:
                expire_at = self._from_wall_time(item["expire"])
                if self._is_expired(expire_at):
                    continue
                self._table.put(item["key"], (item["value"], expire_at))
                restored += 1
            return restored

    def _to_wall_time(self, expire_at):
        if expire_at is NEVER_EXPIRES:
            return None
        return self._wall_clock() + (expire_at - self._clock())

    def _from_wall_time(self, expire):
        if expire is None:
            return NEVER_EXPIRES
        return self._clock() + (expire - self._wall_clock())

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
