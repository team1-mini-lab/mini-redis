class Store:
    """키-값 저장소. 1단계에서는 파이썬 dict를 감싼 임시 구현입니다."""

    def __init__(self):
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        return self._data.get(key)

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False
