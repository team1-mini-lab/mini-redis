class Store:
    """1단계 임시 저장소. 2단계에서 내부의 dict를 해시 테이블로 교체한다."""

    def __init__(self):
        self._data = {}

    def set(self, key, value, ttl=None):
        self._data[key] = value          # ttl은 4단계에서 처리

    def get(self, key):
        return self._data.get(key)       # 없으면 None

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False