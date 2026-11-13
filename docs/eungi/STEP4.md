# 4단계: 만료 (구현 완료)

## 팀 공유 요약

- **한 일**: `Node`에 `expire_at` 필드를 추가하고, `get`과 `delete`에서 조회할 때 만료를 확인해 지우는 지연 삭제를 구현했어요
- **다른 코드에 영향**: `server.py`와 `store.py`는 그대로예요. `set(key, value, ttl=None)` 모양도 그대로라 1단계부터 맞춰 둔 접점 그대로예요
- **확인 방법**: `python -m pytest -v` → `test_expire`, `test_overwrite_resets_ttl` 통과 확인

## 목표

만료 시점을 저장하고, 조회할 때 지났으면 지우고 없는 키처럼 돌려줌. (R5, R7)

- [x] 5초짜리로 저장한 값이 바로 조회되고, 5초 뒤에는 404가 나옴
- [x] ttl 없이 덮어쓰면 만료가 없어짐

## 구현: `mini_redis/hash_table.py`

### Node에 expire_at 추가

```python
class Node:
    def __init__(self, key, value, expire_at=None, next=None):
        self.key = key
        self.value = value
        self.expire_at = expire_at   # 만료 시각. None이면 만료 없음
        self.next = next

    def is_expired(self):
        return self.expire_at is not None and time.time() >= self.expire_at
```

### set에서 expire_at 계산

```python
def set(self, key, value, ttl=None):
    expire_at = time.time() + ttl if ttl is not None else None
    # 같은 키가 있으면 덮어쓰기 (만료 시각도 새로 정함)
    ...
    node.expire_at = expire_at
```

ttl을 받아서 "지금 시각 + ttl"로 끝나는 시각을 계산해 저장함. 덮어쓸 때도 같이 갱신하므로 ttl 없이 덮어쓰면 만료가 없어짐 (진짜 Redis와 같은 동작).

### get에서 지연 삭제

```python
def get(self, key):
    ...
    if current.key == key:
        if current.is_expired():
            self.delete(key)   # 만료됐으면 지우고
            return None        # 없는 키처럼 돌려줌
        return current.value
```

### delete에서도 만료 확인

```python
def delete(self, key):
    ...
    if current.key == key:
        ...
        self.size -= 1
        return not current.is_expired()  # 만료된 키 삭제는 False (없는 키 취급)
```

만료된 키를 지우면 `False`를 돌려줌. 사용하는 쪽에서 만료 여부를 따로 구분할 필요 없게 함 (DESIGN.md 결정 4단계).

## 고민했던 것

**지연 삭제만으로 충분한가?**

만료된 키를 아무도 조회하지 않으면 메모리에 계속 남음. 진짜 Redis는 주기적으로 만료 키를 샘플링해서 지움. 우리는 과제 요구사항이 "만료된 값을 요청받았을 때"의 처리라 지연 삭제로 충족함. 주기적 정리는 13단계에서 시간이 남으면 함.

**만료 시각인가, 남은 시간인가?**

남은 시간을 저장하면 시간이 흐를 때마다 값을 줄여 줘야 함. 만료 시각을 저장하면 조회할 때 현재 시각과 비교 한 번으로 끝남. → 만료 시각 저장.

**get이 쓰기가 되는 문제**

만료된 값을 지연 삭제하면 `get`도 테이블을 고침. 그래서 5단계에서 `get`에도 lock을 걸어야 함 (NOTES.md 동시성 참고).

## 테스트: `tests/test_hash_table.py`

```python
def test_expire():
    table = HashTable()
    table.set("code", "1234", ttl=1)
    assert table.get("code") == "1234"   # 바로는 조회됨
    time.sleep(1.1)
    assert table.get("code") is None     # 1초 뒤엔 없음
    assert table.size == 0               # 지연 삭제로 실제로 지워짐

def test_overwrite_resets_ttl():
    table = HashTable()
    table.set("a", 1, ttl=1)
    table.set("a", 2)                    # ttl 없이 덮어씀 → 만료 없어짐
    time.sleep(1.1)
    assert table.get("a") == 2
```
