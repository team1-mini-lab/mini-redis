from store import Store


def test_store_set_get_delete():
    store = Store()
    store.set("name", "현지")
    assert store.get("name") == "현지"
    assert store.delete("name") is True
    assert store.get("name") is None
    assert store.delete("name") is False
