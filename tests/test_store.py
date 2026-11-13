from mini_redis.store import Store


def _chain(bucket):
    """칸의 첫 노드부터 체인을 따라가며 (키, 값) 목록을 만든다."""
    items = []
    current = bucket
    while current is not None:
        items.append((current.key, current.value))
        current = current.next
    return items


def test_chaining_in_one_bucket():
    store = Store(capacity=1)          # 칸 1개 → 모든 키가 같은 칸에 들어감
    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)
    store.set("a", 100)                # 같은 키 → 추가가 아니라 덮어쓰기

    assert len(_chain(store.buckets[0])) == 3
    assert store.size == 3
    assert store.get("a") == 100
    assert store.get("b") == 2
    assert store.get("c") == 3
    assert store.get("x") is None      # 없는 키


def test_delete_every_position():
    store = Store(capacity=1)
    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)                  # 맨 앞 삽입 → 체인: [c] → [b] → [a]

    assert store.delete("b") is True   # 가운데
    assert store.get("a") == 1 and store.get("c") == 3
    assert store.delete("a") is True   # 끝
    assert store.get("c") == 3
    assert store.delete("c") is True   # 처음
    assert store.delete("c") is False  # 이미 없는 키
    assert store.buckets[0] is None and store.size == 0
