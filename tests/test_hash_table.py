from hash_table import HashTable


def test_set_and_get():
    table = HashTable()
    table.set("name", "현지")
    assert table.get("name") == "현지"


def test_get_missing_key_returns_none():
    table = HashTable()
    assert table.get("name") is None


def test_set_existing_key_overwrites():
    table = HashTable()
    table.set("name", "현지")
    table.set("name", "민수")
    assert table.get("name") == "민수"
    assert len(table) == 1


def test_delete():
    table = HashTable()
    table.set("name", "현지")
    assert table.delete("name") is True
    assert table.get("name") is None
    assert len(table) == 0


def test_delete_missing_key_returns_false():
    table = HashTable()
    assert table.delete("name") is False


def test_same_key_always_same_index():
    table = HashTable()
    assert table._index("name") == table._index("name")


def test_colliding_keys_are_kept_separately():
    # "Aa"와 "BB"는 해시 값 자체가 같아서 언제나 같은 칸에 들어감
    table = HashTable()
    assert table._hash("Aa") == table._hash("BB")
    table.set("Aa", 1)
    table.set("BB", 2)
    assert table.get("Aa") == 1
    assert table.get("BB") == 2


def test_delete_one_of_colliding_keys_keeps_the_other():
    table = HashTable()
    table.set("Aa", 1)
    table.set("BB", 2)
    assert table.delete("Aa") is True
    assert table.get("Aa") is None
    assert table.get("BB") == 2


def test_more_keys_than_initial_buckets():
    # 처음 칸 수(8)보다 훨씬 많은 키 50개가 모두 저장되고 조회됨
    table = HashTable(capacity=8)
    for i in range(50):
        table.set(f"key{i}", i)
    assert len(table) == 50
    for i in range(50):
        assert table.get(f"key{i}") == i


# ---------- 3단계: 칸 수 확장 ----------


def test_capacity_grows_and_all_keys_remain():
    # 완료 기준: 키 100개를 저장하면 칸 수가 늘어나고, 100개 모두 조회됨
    table = HashTable()
    for i in range(100):
        table.set(f"key{i}", i)
    assert table.capacity == 256
    assert len(table) == 100
    for i in range(100):
        assert table.get(f"key{i}") == i


def test_resize_happens_when_load_factor_exceeds_limit():
    # 칸 8개의 기준은 8 * 0.75 = 6. 키 6개까지는 그대로, 7번째에 2배가 됨
    table = HashTable(capacity=8)
    for i in range(6):
        table.set(f"key{i}", i)
    assert table.capacity == 8
    table.set("key6", 6)
    assert table.capacity == 16


def test_overwrite_does_not_resize():
    table = HashTable(capacity=8)
    for i in range(100):
        table.set("name", i)
    assert table.capacity == 8
    assert len(table) == 1


def test_delete_does_not_shrink():
    table = HashTable()
    for i in range(100):
        table.set(f"key{i}", i)
    for i in range(100):
        assert table.delete(f"key{i}") is True
    assert table.capacity == 256
    assert len(table) == 0


def test_same_hash_keys_survive_resize():
    # 해시 값이 같은 키는 칸을 늘려도 같은 칸에 있지만, 각자의 값은 그대로 조회됨
    table = HashTable()
    table.set("Aa", 1)
    table.set("BB", 2)
    for i in range(100):
        table.set(f"key{i}", i)
    assert table._index("Aa") == table._index("BB")
    assert table.get("Aa") == 1
    assert table.get("BB") == 2


def test_resize_splits_keys_that_shared_a_bucket():
    # "name"과 "lemon"은 해시 값이 다르지만 8칸에서는 같은 칸. 16칸이 되면 갈라짐
    table = HashTable(capacity=8)
    assert table._index("name") == table._index("lemon")
    for i in range(7):
        table.set(f"key{i}", i)
    assert table.capacity == 16
    assert table._index("name") != table._index("lemon")
