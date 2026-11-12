"""직접 만든 해시 테이블 (2단계: 체이닝, 3단계: 칸 수 확장).

파이썬 dict를 쓰지 않는다. 칸 배열만 list로 두고, 해시 계산과 충돌 처리는 직접 한다.
이 파일은 만료, lock, HTTP를 모른다. 키로 값을 넣고, 찾고, 지우는 일만 한다.
"""


def fnv1a(key):
    """문자열 키를 64비트 숫자로 바꾸는 해시 함수 (FNV-1a).

    키의 바이트를 하나씩 섞는다: XOR로 바이트를 넣고, 큰 소수를 곱해 퍼뜨린다.
    같은 키는 언제 실행해도 같은 숫자가 나온다.
    """
    h = 14695981039346656037                      # 시작값 (offset basis)
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF  # 소수를 곱하고 64비트로 자름
    return h


class _Node:
    """체인의 한 항목. 같은 칸에 배정된 키들을 next로 이어 붙인다."""

    def __init__(self, key, value, next):
        self.key = key      # 키도 함께 저장해야 같은 칸의 다른 키와 구분할 수 있다
        self.value = value
        self.next = next


class HashTable:
    MAX_LOAD = 0.75   # 저장된 개수 ÷ 칸 수가 이 값을 넘으면 확장한다
    GROWTH = 2        # 확장할 때 칸 수를 몇 배로 늘릴지

    def __init__(self, capacity=8, hash_fn=fnv1a):
        self._buckets = [None] * capacity  # 칸 배열. 각 칸은 체인의 첫 노드 또는 None
        self._size = 0                     # 저장된 키 개수
        self._hash = hash_fn               # 테스트에서 일부러 충돌을 만들 때 바꿔 끼운다

    @property
    def capacity(self):
        return len(self._buckets)

    def __len__(self):
        return self._size

    def _index(self, key):
        """키가 들어갈 칸 번호: 해시값을 칸 수로 나눈 나머지."""
        return self._hash(key) % len(self._buckets)

    def put(self, key, value):
        """저장한다. 새 키면 True, 이미 있어서 덮어썼으면 False."""
        i = self._index(key)
        node = self._buckets[i]
        while node is not None:            # 체인을 따라가며 같은 키가 있는지 찾는다
            if node.key == key:
                node.value = value
                return False
            node = node.next
        self._buckets[i] = _Node(key, value, self._buckets[i])  # 체인 맨 앞에 붙인다
        self._size += 1
        if self._size / len(self._buckets) > self.MAX_LOAD:     # 넘을 때만 확장 (같으면 그대로)
            self._resize(len(self._buckets) * self.GROWTH)
        return True

    def _resize(self, new_capacity):
        """칸 수를 늘리고 모든 항목을 새 위치로 옮긴다.

        칸 수가 바뀌면 "해시값 % 칸 수"의 결과도 바뀌므로, 항목마다 칸 번호를 다시 계산해야 한다.
        """
        old_buckets = self._buckets
        self._buckets = [None] * new_capacity
        for node in old_buckets:
            while node is not None:
                next_node = node.next              # 옮기면 next가 바뀌므로 미리 기억해 둔다
                i = self._index(node.key)          # 새 칸 수로 다시 계산
                node.next = self._buckets[i]       # 기존 노드를 새 칸의 맨 앞에 그대로 옮겨 붙인다
                self._buckets[i] = node
                node = next_node

    def get(self, key, default=None):
        """값을 돌려준다. 없으면 default."""
        node = self._buckets[self._index(key)]
        while node is not None:
            if node.key == key:
                return node.value
            node = node.next
        return default

    def remove(self, key):
        """지웠으면 True, 없었으면 False."""
        i = self._index(key)
        prev = None
        node = self._buckets[i]
        while node is not None:
            if node.key == key:
                if prev is None:
                    self._buckets[i] = node.next   # 체인의 첫 노드를 지움
                else:
                    prev.next = node.next          # 앞 노드가 다음 노드를 가리키게 해서 끊어냄
                self._size -= 1
                return True
            prev = node
            node = node.next
        return False

    def debug_dump(self):
        """칸별 체인을 문자열로 보여 준다. 충돌이 체인으로 이어진 것을 눈으로 확인하는 용도."""
        lines = []
        for i, node in enumerate(self._buckets):
            chain = []
            while node is not None:
                chain.append(f"({node.key} → {node.value})")
                node = node.next
            lines.append(f"[{i}] " + " → ".join(chain))
        return "\n".join(lines)
