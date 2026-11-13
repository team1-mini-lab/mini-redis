"""저장소 모듈: 키-값을 저장, 조회, 삭제한다 (접점 1).

2단계: 내부를 직접 만든 해시 테이블로 바꿨다. 함수 이름과 돌려주는 값은 1단계와 같다.
4단계: 만료. 해시 테이블에는 (값, 만료 시점) 묶음을 값으로 넣는다. 해시 테이블은 만료를 모른다.
5단계: lock. 저장소 전체에 lock 하나를 두고 set, get, delete를 모두 그 안에서 실행한다.
"""
import threading
import time

from mini_redis.hashtable import HashTable


class Store:
    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock  # 현재 시각을 돌려주는 함수. 테스트에서 가짜 시계로 바꿔 끼울 수 있다
        self._lock = threading.Lock()  # 한 번에 한 요청만 해시 테이블을 만지게 한다
        # 주의: lock 안에서 self.set/get/delete를 다시 부르면 같은 lock을 기다리며 멈춘다.
        # lock 안에서는 self._table만 직접 쓴다.

    def set(self, key, value, ttl=None):
        """key에 value를 저장한다. 이미 있으면 덮어쓰고 만료 시점도 새로 정한다.

        ttl(초)이 있으면 "지금 + ttl"을 만료 시점으로 함께 저장하고, 없으면 만료 없음(None).
        """
        with self._lock:
            expire_at = None if ttl is None else self._clock() + ttl
            self._table.put(key, (value, expire_at))   # put 안의 확장(_resize)도 lock 안에서 끝난다

    def _is_expired(self, expire_at):
        """만료 시점이 지났거나 딱 그 시점이면 만료로 본다."""
        return expire_at is not None and self._clock() >= expire_at

    def get(self, key):
        """key의 값을 돌려준다. 없거나 만료됐으면 None.

        만료된 키는 이때 발견해서 지운다 (지연 삭제).
        "만료 확인 → 삭제"가 lock 안에서 한 덩어리로 실행되므로,
        그 사이에 다른 요청의 set이 끼어들어 새 값이 지워지는 일이 없다.
        """
        with self._lock:
            entry = self._table.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if self._is_expired(expire_at):
                self._table.remove(key)
                return None
            return value

    def delete(self, key):
        """지웠으면 True, 지울 키가 없었거나 이미 만료됐으면 False."""
        with self._lock:
            entry = self._table.get(key)
            if entry is None:
                return False
            _, expire_at = entry
            self._table.remove(key)            # 만료됐든 아니든 지운다
            return not self._is_expired(expire_at)
