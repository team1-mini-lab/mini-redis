# 5단계: lock (구현 완료)

## 팀 공유 요약

- **한 일**: `Store` 클래스에 `threading.Lock()`을 추가하고, `set`/`get`/`delete`를 `with self._lock:`으로 감쌌어요
- **다른 코드에 영향**: 없어요. `server.py`는 `Store`를 그대로 쓰고, lock이 `Store` 안에 있어서 서버가 신경 쓸 필요 없어요
- **확인 방법**: `python -m pytest -v` → `test_concurrent_set_get` 통과 확인

## 목표

여러 요청이 동시에 들어와도 저장소가 망가지지 않음. (R4)

- [x] 8개 스레드가 500번씩 저장·조회를 동시에 반복해도 오류가 없음

## 구현: `mini_redis/store.py`

```python
import threading
from mini_redis.hash_table import HashTable

class Store:
    def __init__(self):
        self._table = HashTable()
        self._lock = threading.Lock()

    def set(self, key, value, ttl=None):
        with self._lock:
            self._table.set(key, value, ttl)

    def get(self, key):
        with self._lock:
            return self._table.get(key)

    def delete(self, key):
        with self._lock:
            return self._table.delete(key)
```

`HashTable`은 lock을 모르고 순수하게 저장만 함. lock은 `Store`에서 한 곳에 모아서 처리함. 이렇게 하면 `HashTable` 단위 테스트가 단순해지고, 저장소를 쓰는 쪽이 lock을 빠뜨릴 수 없음 (DESIGN.md 결정 5단계).

## 왜 lock이 필요한가

Flask는 요청을 여러 스레드로 동시에 받음. 두 요청이 같은 `HashTable`을 동시에 건드리면 문제가 생김.

- 한 요청이 `_resize`로 새 버킷에 옮기는 도중에 다른 요청이 같은 테이블을 조회
- 두 요청이 같은 칸에 동시에 노드를 삽입
- **4단계 지연 삭제 때문에 `get`도 테이블을 고침** → 조회에도 lock 필요

진짜 Redis는 명령을 싱글 스레드에서 하나씩 처리해서 lock이 없음. 우리는 Flask의 멀티스레드 환경이라 lock으로 같은 효과를 냄.

## 고민했던 것

**lock을 어디에 두나: Store vs HashTable?**

HashTable 안에 두면 테이블을 직접 쓰는 경우에도 보호됨. 하지만 HashTable 단위 테스트에서 lock 없이 쓸 수 없어짐. Store 안에 두면 HashTable을 단순하게 유지하고 테스트하기 쉬움. → Store에 둠 (DESIGN.md 결정 5단계, DECISIONS.md 5단계).

**get에도 lock이 필요한가?**

읽기만 하는 것 같지만, 만료된 값을 발견하면 `delete`를 호출해 테이블을 고침. 그래서 get도 쓰기임 → lock 필요.

## 테스트: `tests/test_store.py`

```python
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
```

8개 스레드가 각자 500번씩 저장·조회함. lock 없이 실행하면 중간에 오류가 나거나 엉뚱한 값이 나옴.
