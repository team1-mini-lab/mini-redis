import sys
import threading

import pytest

from store import Store


def test_store_set_get_delete():
    store = Store()
    store.set("name", "현지")
    assert store.get("name") == "현지"
    assert store.delete("name") is True
    assert store.get("name") is None
    assert store.delete("name") is False


# ---------- 4단계: 만료 ----------


class FakeClock:
    """테스트용 가짜 시계. now를 바꿔서 시간을 흘려보냄"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):  # clock()으로 부르면 지금 시각을 돌려줌
        return self.now


def test_no_ttl_never_expires():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지")
    clock.now += 100_000
    assert store.get("name") == "현지"


def test_get_before_expiry_returns_value():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 4.9
    assert store.get("name") == "현지"


def test_get_at_expiry_returns_none():
    # 완료 기준: 5초짜리 값은 5초 뒤에 없는 키가 됨
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 5
    assert store.get("name") is None


def test_get_removes_expired_item_from_table():
    # 지연 삭제: 만료된 항목은 get이 발견한 자리에서 지워짐
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 5
    assert len(store._table) == 1  # 아직 아무도 조회하지 않아 남아 있음
    assert store.get("name") is None
    assert len(store._table) == 0


def test_delete_expired_key_returns_false_and_removes_item():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 5
    assert store.delete("name") is False  # 이미 없는 키로 취급
    assert len(store._table) == 0  # 남아 있던 항목은 치움


def test_delete_before_expiry_returns_true():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 4.9
    assert store.delete("name") is True
    assert store.get("name") is None


def test_overwrite_sets_new_expiry():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)  # 5초에 만료 예정
    clock.now = 3
    store.set("name", "민수", ttl=5)  # 8초에 만료로 바뀜
    clock.now = 6
    assert store.get("name") == "민수"
    clock.now = 8
    assert store.get("name") is None


def test_overwrite_without_ttl_removes_expiry():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now = 3
    store.set("name", "민수")  # ttl 생략: 만료가 없어짐
    clock.now = 100
    assert store.get("name") == "민수"


def test_set_after_expiry_stores_new_value():
    clock = FakeClock()
    store = Store(clock=clock)
    store.set("name", "현지", ttl=5)
    clock.now += 5
    store.set("name", "민수")
    assert store.get("name") == "민수"


# ---------- 5단계: lock ----------


@pytest.fixture
def frequent_thread_switch():
    """테스트 동안 스레드를 아주 자주 교대시켜, lock이 없으면 끼어들기가 드러나게 함"""
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # 기본값은 약 0.005초
    yield
    sys.setswitchinterval(old)  # 파이썬 전체 설정이므로 끝나면 되돌림


def run_threads(worker, count):
    """worker(n)을 스레드 count개로 동시에 실행하고, 스레드 안에서 난 오류를 모아 돌려줌"""
    errors = []

    def wrapped(n):
        try:
            worker(n)
        except Exception as e:  # 스레드 안의 오류는 테스트로 전달되지 않으므로 직접 모음
            errors.append(e)

    threads = [threading.Thread(target=wrapped, args=(n,)) for n in range(count)]
    for t in threads:
        t.start()  # 모두 동시에 시작
    for t in threads:
        t.join()  # 모두 끝날 때까지 기다림
    return errors


def test_concurrent_set_and_get_different_keys(frequent_thread_switch):
    # 완료 기준: 스레드 10개가 각자 키 100개를 저장하고 바로 조회. 끝나면 1,000개 모두 있어야 함
    store = Store()

    def worker(n):
        for i in range(100):
            key = f"key{n * 100 + i}"
            store.set(key, i)
            assert store.get(key) == i

    errors = run_threads(worker, 10)
    assert errors == []
    assert len(store._table) == 1000
    for k in range(1000):
        assert store.get(f"key{k}") is not None


def test_concurrent_set_get_delete_same_keys(frequent_thread_switch):
    # 스레드 10개가 같은 키 20개를 두고 저장, 조회, 삭제를 반복
    store = Store()

    def worker(n):
        for i in range(200):
            key = f"key{i % 20}"
            store.set(key, n)
            store.get(key)
            store.delete(key)

    errors = run_threads(worker, 10)
    assert errors == []
    # 키 수(len)와 실제로 조회되는 키 수가 같아야 함
    found = sum(store.get(f"key{i}") is not None for i in range(20))
    assert len(store._table) == found
