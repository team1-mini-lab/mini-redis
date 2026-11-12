"""저장소 모듈: 키-값을 저장, 조회, 삭제한다 (접점 1).

1단계: 파이썬 dict를 감싼 임시 저장소.
2단계에서 내부를 직접 만든 해시 테이블로 바꾼다. 함수 이름과 돌려주는 값은 그대로 둔다.
"""


class Store:
    def __init__(self):
        self._data = {}  # 1단계 임시. 2단계에서 해시 테이블로 교체

    def set(self, key, value, ttl=None):
        """key에 value를 저장한다. 이미 있으면 덮어쓴다. ttl은 4단계에서 다룬다."""
        self._data[key] = value

    def get(self, key):
        """key의 값을 돌려준다. 없으면 None."""
        return self._data.get(key)

    def delete(self, key):
        """지웠으면 True, 지울 키가 없었으면 False."""
        if key in self._data:
            del self._data[key]
            return True
        return False
