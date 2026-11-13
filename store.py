import time

from hash_table import HashTable


class Store:
    """키-값 저장소. 값은 직접 만든 해시 테이블에 담고, 만료는 여기서 처리합니다."""

    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock  # 현재 시각을 돌려주는 함수. 테스트에서는 가짜 시계를 넣음

    def set(self, key, value, ttl=None):
        # 기간(ttl)을 만료 "시점"으로 바꿔 저장. ttl이 없으면 None(만료 없음)
        expires_at = None if ttl is None else self._clock() + ttl
        self._table.set(key, (value, expires_at))

    def _is_expired(self, expires_at):
        return expires_at is not None and self._clock() >= expires_at

    def get(self, key):
        item = self._table.get(key)
        if item is None:
            return None
        value, expires_at = item
        if self._is_expired(expires_at):
            self._table.delete(key)  # 지연 삭제: 만료를 발견한 자리에서 지움
            return None
        return value

    def delete(self, key):
        item = self._table.get(key)
        if item is None:
            return False
        _, expires_at = item
        self._table.delete(key)  # 만료됐든 아니든 항목은 치움
        return not self._is_expired(expires_at)  # 만료된 키는 "없던 키"이므로 False
