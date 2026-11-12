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


def test_more_keys_than_buckets():
    # 칸은 8개뿐이지만 키 50개가 모두 저장되고 조회됨 (체이닝)
    table = HashTable(capacity=8)
    for i in range(50):
        table.set(f"key{i}", i)
    assert len(table) == 50
    for i in range(50):
        assert table.get(f"key{i}") == i
