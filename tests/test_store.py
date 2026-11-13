import threading
from mini_redis.store import Store

def test_concurrent_set_get():
    store = Store()
    errors = []

    def worker(n):
        try:
            for i in range(500):
                store.set(f"t{n}-{i}", i)
                assert store.get(f"t{n}-{i}") == i
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert errors == []
    assert all(store.get(f"t{n}-{i}") == i for n in range(8) for i in range(500))