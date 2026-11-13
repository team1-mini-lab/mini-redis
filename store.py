import threading
import time

from hash_table import HashTable


class Store:
    """키-값 저장소. 값은 직접 만든 해시 테이블에 담고, 만료와 lock은 여기서 처리합니다."""

    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock  # 현재 시각을 돌려주는 함수. 테스트에서는 가짜 시계를 넣음
        self._lock = threading.Lock()  # 저장소 전체에 lock 하나. 한 번에 한 스레드만 저장소를 만짐

    def set(self, key, value, ttl=None):
        with self._lock:  # 들어갈 때 잠그고, 블록을 나올 때 자동으로 풂 (오류가 나도 풂)
            # 기간(ttl)을 만료 "시점"으로 바꿔 저장. ttl이 없으면 None(만료 없음)
            expires_at = None if ttl is None else self._clock() + ttl
            self._table.set(key, (value, expires_at))  # 확장(_resize)도 이 lock 안에서 일어남

    def _is_expired(self, expires_at):
        # lock 안에서만 불림
        return expires_at is not None and self._clock() >= expires_at

    def get(self, key):
        with self._lock:  # 꺼내기 → 만료 확인 → 지우기를 한 덩어리로 보호
            item = self._table.get(key)
            if item is None:
                return None
            value, expires_at = item
            if self._is_expired(expires_at):
                self._table.delete(key)  # 지연 삭제: 만료를 발견한 자리에서 지움
                return None
            return value

    def delete(self, key):
        with self._lock:
            item = self._table.get(key)
            if item is None:
                return False
            _, expires_at = item
            self._table.delete(key)  # 만료됐든 아니든 항목은 치움
            return not self._is_expired(expires_at)  # 만료된 키는 "없던 키"이므로 False
