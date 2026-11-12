"""저장소 모듈: 키-값을 저장, 조회, 삭제한다 (접점 1).

2단계: 내부를 직접 만든 해시 테이블로 바꿨다. 함수 이름과 돌려주는 값은 1단계와 같다.
"""
from mini_redis.hashtable import HashTable


class Store:
    def __init__(self):
        self._table = HashTable()

    def set(self, key, value, ttl=None):
        """key에 value를 저장한다. 이미 있으면 덮어쓴다. ttl은 4단계에서 다룬다."""
        self._table.put(key, value)

    def get(self, key):
        """key의 값을 돌려준다. 없으면 None."""
        return self._table.get(key)

    def delete(self, key):
        """지웠으면 True, 지울 키가 없었으면 False."""
        return self._table.remove(key)
