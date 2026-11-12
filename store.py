from hash_table import HashTable


class Store:
    """키-값 저장소. 2단계부터 직접 만든 해시 테이블에 값을 담습니다."""

    def __init__(self):
        self._table = HashTable()

    def set(self, key, value):
        self._table.set(key, value)

    def get(self, key):
        return self._table.get(key)

    def delete(self, key):
        return self._table.delete(key)
