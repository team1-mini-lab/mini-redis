class HashTable:
    """체이닝으로 충돌을 처리하는 해시 테이블. 2단계에서는 칸 수가 고정입니다."""

    def __init__(self, capacity=8):
        # 칸마다 서로 다른 빈 리스트를 만듦. [[]] * capacity로 만들면 모든 칸이 같은 리스트를 가리킴
        self._buckets = [[] for _ in range(capacity)]
        self._size = 0

    def _hash(self, key):
        """문자열을 정수로 바꿈. 같은 문자열은 언제나 같은 정수가 됨"""
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF  # 32비트 안으로 자름
        return h

    def _index(self, key):
        """키가 들어갈 칸 번호 (0 ~ 칸 수 - 1)"""
        return self._hash(key) % len(self._buckets)

    def set(self, key, value):
        bucket = self._buckets[self._index(key)]
        for i, (k, _) in enumerate(bucket):
            if k == key:  # 이미 있는 키: 값만 바꿈
                bucket[i] = (key, value)
                return
        bucket.append((key, value))  # 새 키: 칸의 리스트 끝에 이어 붙임
        self._size += 1

    def get(self, key):
        bucket = self._buckets[self._index(key)]
        for k, v in bucket:
            if k == key:
                return v
        return None

    def delete(self, key):
        bucket = self._buckets[self._index(key)]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self._size -= 1
                return True
        return False

    def __len__(self):
        return self._size

    def dump(self):
        """칸마다 들어 있는 항목을 한 줄씩 보여 주는 문자열"""
        lines = []
        for i, bucket in enumerate(self._buckets):
            items = " -> ".join(f"{k}={v!r}" for k, v in bucket)
            lines.append(f"[{i}] {items}")
        return "\n".join(lines)
