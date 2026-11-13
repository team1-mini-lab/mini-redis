from mini_redis.store import Store


def _chain(bucket):
    """칸의 첫 노드부터 체인을 따라가며 (키, 값) 목록을 만든다."""
    items = []
    current = bucket
    while current is not None:
        items.append((current.key, current.value))
        current = current.next
    return items


def _keys_in_same_bucket(store, n):
    """같은 칸 번호를 받는 서로 다른 키 n개를 찾는다 (충돌 만들기)."""
    groups = {}
    i = 0
    while True:
        key = f"key{i}"
        index = store._get_bucket_index(key)
        groups.setdefault(index, []).append(key)
        if len(groups[index]) == n:
            return groups[index]
        i += 1


def test_chaining_in_one_bucket():
    # 3단계부터 칸이 0.75 넘게 차면 늘어나므로, 칸 8개에 3개만 넣어 확장 없이 충돌을 만든다
    store = Store(capacity=8)
    a, b, c = _keys_in_same_bucket(store, 3)
    store.set(a, 1)
    store.set(b, 2)
    store.set(c, 3)                    # 맨 앞 삽입 → 체인: [c] → [b] → [a]
    store.set(a, 100)                  # 같은 키 → 덮어쓰기

    index = store._get_bucket_index(a)
    assert len(_chain(store.buckets[index])) == 3
    assert store.get(a) == 100 and store.get(b) == 2 and store.get(c) == 3

    assert store.delete(b) is True     # 가운데
    assert store.delete(a) is True     # 끝
    assert store.delete(c) is True     # 처음
    assert store.delete(c) is False    # 이미 없는 키
    assert store.buckets[index] is None and store.size == 0


def test_resize_keeps_all_keys():
    store = Store()                    # 칸 4개로 시작
    for i in range(100):
        store.set(f"k{i}", i)

    assert store.capacity > 4          # 칸 수가 늘어남
    assert store.size == 100
    assert all(store.get(f"k{i}") == i for i in range(100))   # 100개 모두 조회
