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
