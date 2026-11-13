# 2단계: 해시 테이블 (구현 완료)

## 팀 공유 요약

- **한 일**: `Store` 안쪽의 dict를 체이닝 해시 테이블로 바꿨어요. 체인은 `Node` 연결 리스트로 구현해 봤어요
- **다른 코드에 영향**: 없어요. `set`/`get`/`delete` 사용법과 `server.py`는 그대로예요
- **DESIGN.md와 다른 점**: 결정 기록 2번(제안)에는 "리스트의 각 항목에 키와 값을 함께 저장"으로 되어 있는데, 리스트 대신 연결 리스트를 썼어요. 키와 값을 함께 저장하는 건 같아요
- **확인 방법**: `python -m pytest -v` (2개), 서버는 1단계 curl 순서 그대로
- **의견 부탁드려요**
  - 체인을 연결 리스트로 둬도 괜찮을까요?
  - 해시 함수는 내장 `hash()`를 계속 쓸까요, 직접 만들까요?

### 연결 리스트를 고른 이유와 고려한 점

직접 성능을 비교해 본 건 아니고, 구현하면서 생각한 내용이에요.

| | 연결 리스트 (이번 구현) | 리스트 |
| --- | --- | --- |
| 덮어쓰기 | `node.value = ...`로 바로 바꿈 | 튜플이면 새 항목으로 교체해야 함 |
| 삭제 | 앞 노드의 `next`만 바꿈 | 뺀 뒤 뒤 항목들이 한 칸씩 당겨짐 |
| 코드 양 | `prev`, `current` 관리가 필요해서 조금 김 | 짧고 읽기 쉬움 |
| 속도 | 체인이 짧으면 차이가 거의 없을 것 같음 | 파이썬 list는 최적화돼 있어서 짧은 체인에선 더 빠를 수도 있음 |
| 고른 이유 | 체이닝이 "노드를 이어 붙이는 것"이라는 걸 직접 구현해 보고 싶었음 | |

7단계 비교 때 리스트 버전과 실제로 비교해 보면 좋을 것 같아요.

## 목표

`store.py` 안쪽의 dict를 직접 만든 해시 테이블(체이닝)로 바꿈. 서버 코드와 `set`/`get`/`delete` 사용법은 1단계 그대로.

- [x] 같은 칸에 여러 키가 이어져도 키로 정확히 찾고 지움
- [ ] 1단계 curl 확인을 다시 돌려 같은 결과
- [ ] `dump()`로 칸 상태를 눈으로 확인

체이닝은 해시 테이블의 칸(버킷)에 값을 하나만 두는 게 아니라, 연결 리스트로 여러 개를 이어 저장하는 방법.

```
buckets  (칸 4개)
[0] → None
[1] → [ "e" | 5 | ●] → [ "a" | 1 | None ]    ← 같은 칸에 두 키
[2] → [ "b" | 2 | None ]
[3] → None
        key  val next
```

## 구현: `mini_redis/store.py`

```python
class Node:
    def __init__(self, key, value, next=None):
        self.key = key          # 해시값이 아니라 원래 키 (같은 칸 안에서 비교용)
        self.value = value
        self.next = next        # 다음 노드, 없으면 None


class Store:
    """해시 테이블 저장소.
    바깥은 버킷 리스트, 안쪽 체인은 연결 리스트(Node)로 한다.
    """
    def __init__(self, capacity=4):
        self.capacity = capacity              # 칸 개수
        self.buckets = [None] * capacity      # 각 칸의 첫 노드 (비어 있으면 None)
        self.size = 0                         # 저장된 키 개수

    def _get_bucket_index(self, key):
        return hash(key) % self.capacity      # 키 → 칸 번호 (0 ~ capacity-1)

    def set(self, key, value, ttl=None):
        index = self._get_bucket_index(key)
        head = self.buckets[index]            # 고정: 원래 첫 노드
        node = head                           # 이동: 체인을 따라감
        while node is not None:
            if node.key == key:               # 같은 키 → 덮어쓰기
                node.value = value
                return
            node = node.next
        self.buckets[index] = Node(key, value, head)   # 없으면 맨 앞에 삽입
        self.size += 1

    def get(self, key):
        index = self._get_bucket_index(key)
        current = self.buckets[index]
        while current is not None:
            if current.key == key:
                return current.value
            current = current.next
        return None                           # 없으면 None (1단계와 같음)

    def delete(self, key):
        index = self._get_bucket_index(key)
        prev = None
        current = self.buckets[index]
        while current is not None:
            if current.key == key:            # 1. 찾는 키인가
                if prev is None:              # 2. 첫 노드인가
                    self.buckets[index] = current.next
                else:
                    prev.next = current.next
                self.size -= 1
                return True
            prev = current                    # 못 찾았을 때만 한 칸 이동
            current = current.next
        return False
```

만든 순서: `Node` → `__init__` → `_get_bucket_index` → `set` → `get` → `delete`

## 완료 확인

```bash
python -m pytest -v    # 2개 통과
```

서버까지 확인할 때는 1단계 curl 순서를 그대로 씀 (`flask --app mini_redis.server run --port 5001 --debug`).

## 짜면서 막혔던 것

### `Node`

- 처음엔 `Class Node:`에 `__init__(self)`만 있고 `self.key = self.value = self.next = None` → 키워드는 소문자 `class`, 만들 때 바로 넣을 수 있게 `key, value, next=None`을 받음. 기본값 있는 인자는 맨 뒤
- 노드에 `hash(key)`를 저장해야 하나? → 아님. 해시는 칸 번호 구할 때만 씀. 같은 칸에 다른 키가 섞이니까 원래 키로 비교해야 함. 해시값이 같은 다른 키도 구분 가능

### 칸 번호 헬퍼

- `hash(key) % self.capacity return` → `return`이 앞에 와야 함
- `__get_bucket_index(self, key)`로 호출 → 정의한 이름은 밑줄 하나. 그리고 메서드는 `self._get_bucket_index(key)`로 부르고 괄호 안에 `self`를 안 넣음

### `set` (제일 오래 걸림)

- 1단계 `self._data`가 남아 있었음 → 이제 `self.buckets[index]`가 그 칸의 첫 노드
- `if index == key` → 칸 번호와 키를 비교하고 있었음 → `node.key == key`
- `self.value = value` → `self`는 Store 전체, 값은 노드에 있음 → `node.value`
- `Node(key, value, ttl)` → `Node(key, value, next)` → 세 번째 칸은 다음 노드 자리. `next`는 내장 함수 → 원래 첫 노드를 넣어야 함
- 앞에서 `self.buckets[index]`를 구했는데 왜 마지막에 또 쓰나? → 반복문이 끝나면 `node`는 항상 `None`. `node`를 넣으면 기존 체인이 끊김 → 그래서 처음에 `head`로 따로 저장해 둠
- 항상 맨 앞에 넣나? → 새 키일 때만. 첫 노드만 바꾸면 돼서 간단하고, 키로 찾으니 순서는 상관없음

### `get`

- `head`에 넣고 `node`로 꺼냄 → 이름이 다르면 다른 변수. 움직이는 변수는 `current` 하나로 통일 (`head`는 움직이지 않는 첫 노드에만)
- `return node.key` → 키를 주고 키를 받으면 의미 없음 → `current.value`
- 반복문 밖 `return node.key` → 그때 `node`는 `None`이라 오류 → `return None`
- `while Node is not None` → 대문자 `Node`는 클래스라 항상 참 → 소문자 변수

### `delete`

- 삭제 = 노드를 없애는 게 아니라 `current`를 가리키던 화살표가 `current.next`를 가리키게 바꾸는 것
  - 첫 노드면 `self.buckets[index]`, 아니면 `prev.next`를 바꿈
- 연결 리스트는 뒤로 못 감 → 앞 노드를 `prev`로 들고 다녀야 함. 처음엔 앞이 없으니 `prev = None`
- `if prev is None`을 바깥에 둠 → 첫 노드가 찾는 키가 아니면 `prev.next`에서 오류 → "찾는 키인가"가 먼저, "첫 노드인가"가 나중
- `self.buckets[index] = current` → 지울 노드를 다시 넣은 것 → `current.next`
- 끝 노드는? → `current.next`가 `None`이라 `prev.next = None`이 되고 자연스럽게 끝남

## 내가 이해한 것

- `self.` → 이 객체 안의 것을 꺼낼 때 붙임. `index`, `current`처럼 메서드 안에서만 쓰는 변수에는 안 붙음
- `_` 하나 → "내부용" 표시 (막지는 않음)
- 칸이 많으면 체인 길이가 1이라 `delete`의 `else`(중간·끝 삭제)가 실행되지 않음 → 그래서 `capacity=1`로 테스트
- 해시 함수는 지금 내장 `hash()`를 씀. 문자열은 실행할 때마다 값이 달라지지만 메모리에만 저장하니 문제없음 (직접 만들지는 팀에 확인)
- 체이닝 vs 개방 주소법: 개방 주소법은 한 칸에 하나만 두고 차 있으면 옆 칸을 찾음. 삭제할 때 툼스톤이 필요해서 체이닝이 더 단순함

## 다음 단계

칸 수가 고정이라 키가 많아지면 체인이 길어짐 → 3단계 칸 수 확장. [STEP3.md](./STEP3.md)
