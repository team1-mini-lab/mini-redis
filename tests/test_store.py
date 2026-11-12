from mini_redis.store import Store


def test_all_keys_in_one_bucket():
    store = Store(capacity=1)          # 칸 1개 → 모든 키가 같은 칸에 들어감

    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)

    # 정말 한 칸에 몰렸는지 확인
    assert len(store._buckets) == 1
    assert len(store._buckets[0]) == 3

    # 조회: 같은 칸에서도 키로 정확히 찾는지
    assert store.get("a") == 1
    assert store.get("b") == 2
    assert store.get("c") == 3
    assert store.get("x") is None      # 없는 키


def test_overwrite_in_chain():
    store = Store(capacity=1)
    store.set("a", 1)
    store.set("b", 2)
    store.set("a", 100)                # 같은 키 → 추가가 아니라 덮어쓰기

    assert store.get("a") == 100
    assert len(store._buckets[0]) == 2  # 항목 수는 그대로 2개


def test_delete_middle_of_chain():
    store = Store(capacity=1)
    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)

    assert store.delete("b") is True   # 가운데 항목 삭제
    assert store.get("b") is None
    assert store.get("a") == 1         # 앞뒤 항목은 멀쩡해야 함
    assert store.get("c") == 3
    assert store.delete("b") is False  # 이미 없는 키
