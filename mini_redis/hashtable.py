"""체이닝으로 충돌을 처리하고, 가득 차면 칸 수를 늘리는 해시 테이블.

파이썬 dict를 쓰지 않는다. 칸 배열만 list로 두고 해시 계산, 충돌 처리, 확장은 직접 한다.
"""


class HashTable:
    INITIAL_CAPACITY = 8
    MAX_LOAD_FACTOR = 0.75
    GROWTH_FACTOR = 2

    def __init__(self, capacity=INITIAL_CAPACITY, hash_fn=None):
        self._buckets = [None] * capacity
        self._size = 0
        self._hash = hash_fn or fnv1a

    @property
    def capacity(self):
        return len(self._buckets)

    def __len__(self):
        return self._size

    def put(self, key, value):
        """새 키를 넣었으면 True, 있던 키의 값을 덮어썼으면 False."""
        node = self._find_node(key)
        if node is not None:
            node.value = value
            return False
        self._prepend_node(key, value)
        if self._is_overloaded():
            self._grow()
        return True

    def get(self, key, default=None):
        node = self._find_node(key)
        return default if node is None else node.value

    def remove(self, key):
        """지웠으면 True, 없던 키면 False."""
        index = self._bucket_index(key)
        previous = None
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                self._unlink(index, previous, node)
                return True
            previous = node
            node = node.next
        return False

    def debug_dump(self):
        """칸마다 이어진 체인을 한 줄씩 보여 준다."""
        return "\n".join(
            f"[{index}] " + " → ".join(f"({node.key} → {node.value})" for node in _chain(head))
            for index, head in enumerate(self._buckets)
        )

    def _bucket_index(self, key):
        return self._hash(key) % len(self._buckets)

    def _find_node(self, key):
        for node in _chain(self._buckets[self._bucket_index(key)]):
            if node.key == key:
                return node
        return None

    def _prepend_node(self, key, value):
        index = self._bucket_index(key)
        self._buckets[index] = _Node(key, value, self._buckets[index])
        self._size += 1

    def _unlink(self, index, previous, node):
        if previous is None:
            self._buckets[index] = node.next
        else:
            previous.next = node.next
        self._size -= 1

    def _is_overloaded(self):
        return self._size / len(self._buckets) > self.MAX_LOAD_FACTOR

    def _grow(self):
        old_buckets = self._buckets
        self._buckets = [None] * (len(old_buckets) * self.GROWTH_FACTOR)
        for head in old_buckets:
            for node in _chain(head):
                self._move_node_to_new_bucket(node)

    def _move_node_to_new_bucket(self, node):
        index = self._bucket_index(node.key)
        node.next = self._buckets[index]
        self._buckets[index] = node


class _Node:
    def __init__(self, key, value, next):
        self.key = key
        self.value = value
        self.next = next


def _chain(head):
    """head부터 next를 따라가며 노드를 하나씩 내준다. 순회 중에 node.next를 바꿔도 안전하다."""
    node = head
    while node is not None:
        following = node.next
        yield node
        node = following


FNV_OFFSET_BASIS = 14695981039346656037
FNV_PRIME = 1099511628211
MASK_64_BITS = 0xFFFFFFFFFFFFFFFF


def fnv1a(key):
    """FNV-1a 64비트 해시. 같은 문자열은 언제 실행해도 같은 숫자가 된다."""
    hashed = FNV_OFFSET_BASIS
    for byte in key.encode("utf-8"):
        hashed ^= byte
        hashed = (hashed * FNV_PRIME) & MASK_64_BITS
    return hashed
