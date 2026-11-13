"""충돌 상황을 여러 번, 여러 방식으로 만들어 체이닝을 검증한다."""
import random

import pytest

from mini_redis.store import Store


def _chain(bucket):
    """칸의 첫 노드부터 체인을 따라가며 (키, 값) 목록을 만든다."""
    items = []
    current = bucket
    while current is not None:
        items.append((current.key, current.value))
        current = current.next
    return items


def _all_items(store):
    return [item for bucket in store.buckets for item in _chain(bucket)]


def _check_chains(store, expected):
    """체인 전체를 훑어 기대한 키-값과 정확히 같은지 확인한다."""
    items = _all_items(store)
    keys = [item[0] for item in items]
    assert len(keys) == len(set(keys)), "같은 키가 체인에 두 번 들어 있음"
    assert {item[0]: item[1] for item in items} == expected
    for i, bucket in enumerate(store.buckets):
        for item in _chain(bucket):
            assert store._get_bucket_index(item[0]) == i, "키가 엉뚱한 칸에 들어 있음"


def _keys_in_same_bucket(store, n):
    """같은 칸 번호를 받는 서로 다른 키 n개를 찾는다 (실제 충돌)."""
    groups = {}
    i = 0
    while True:
        key = f"key{i}"
        groups.setdefault(store._get_bucket_index(key), []).append(key)
        if len(groups[store._get_bucket_index(key)]) == n:
            return groups[store._get_bucket_index(key)]
        i += 1


def test_real_collision_with_normal_capacity():
    """칸이 8개여도 같은 칸에 걸리는 키를 골라 충돌을 만든다."""
    store = Store(capacity=8)
    keys = _keys_in_same_bucket(store, 5)
    for n, key in enumerate(keys):
        store.set(key, n)

    bucket = store.buckets[store._get_bucket_index(keys[0])]
    assert len(_chain(bucket)) == 5
    for n, key in enumerate(keys):
        assert store.get(key) == n


@pytest.mark.parametrize("capacity", [1, 2, 3, 4])
def test_more_keys_than_buckets(capacity):
    """칸보다 키가 훨씬 많으면 충돌이 반드시 생긴다 (비둘기집 원리)."""
    store = Store(capacity=capacity)
    expected = {f"k{i}": i for i in range(50)}
    for key, value in expected.items():
        store.set(key, value)

    assert max(len(_chain(b)) for b in store.buckets) >= 50 // capacity
    _check_chains(store, expected)
    for key, value in expected.items():
        assert store.get(key) == value


@pytest.mark.parametrize("capacity", [1, 2, 4])
def test_delete_every_position_in_chain(capacity):
    """체인의 앞, 가운데, 끝을 차례로 지워도 나머지를 찾는다."""
    store = Store(capacity=capacity)
    expected = {f"k{i}": i for i in range(10)}
    for key, value in expected.items():
        store.set(key, value)

    for key in ["k0", "k5", "k9", "k1", "k8"]:
        assert store.delete(key) is True
        del expected[key]
        assert store.get(key) is None
        _check_chains(store, expected)

    assert store.delete("k0") is False


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("capacity", [1, 3, 8])
def test_random_operations_match_dict(seed, capacity):
    """무작위 set/get/delete 500번을 dict와 똑같이 해서 결과가 항상 같은지 비교한다.

    키 종류를 15개로 좁혀 충돌, 덮어쓰기, 지웠다 다시 넣기가 자주 일어나게 한다.
    dict는 정답을 알려 주는 비교용일 뿐 저장소에는 쓰지 않는다.
    """
    rng = random.Random(seed)
    store = Store(capacity=capacity)
    expected = {}
    keys = [f"k{i}" for i in range(15)]

    for _ in range(500):
        op = rng.choice(["set", "set", "get", "delete"])
        key = rng.choice(keys)
        if op == "set":
            value = rng.choice([rng.randint(0, 100), "", 0, [], {"a": 1}, "벨로시티"])
            store.set(key, value)
            expected[key] = value
        elif op == "get":
            assert store.get(key) == expected.get(key)
        else:
            assert store.delete(key) is (key in expected)
            expected.pop(key, None)

    _check_chains(store, expected)
