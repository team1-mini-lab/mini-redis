# 3단계: 칸 수 확장 (구현 완료)

## 팀 공유 요약

- **한 일**: 칸이 0.75 넘게 차면 칸 수를 2배로 늘리고, 모든 노드를 새 칸 번호로 다시 넣도록 했어요 (재해싱)
- **다른 코드에 영향**: 없어요. `set`/`get`/`delete` 사용법은 그대로이고, `set` 안에서 자동으로 늘어나요
- **정한 값**: 최대 부하율 0.75, 2배씩, 시작 칸 4개
- **확인 방법**: `python mini_redis/store.py` → `256 100`, `3단계 통과!` / `python -m pytest -v` (2개)
- **알아 둘 점**: 이제 `Store(capacity=1)`은 키 하나만 넣어도 바로 칸이 늘어나요. 그래서 "모든 키를 한 칸에 몰기" 테스트는 칸 8개에서 같은 칸에 걸리는 키를 골라 넣는 방식으로 바꿨어요

## 목표

일정 수준 이상 차면 칸을 늘리고 재배치함. (R1, R7)

- [x] 키 100개를 저장하면 칸 수가 늘어나고, 100개 모두 조회됨

칸 수가 고정이면 키가 늘수록 체인이 길어져서 `get`이 느려짐. 칸 수를 늘려 체인을 다시 짧게 만듦.

## 구현: `mini_redis/store.py`

`set` 끝에 검사 두 줄, 그리고 `_resize` 메서드 하나를 추가함.

```python
def set(self, key, value, ttl=None):
    ...                                        # 2단계 그대로
    self.buckets[index] = Node(key, value, head)
    self.size += 1
    if self.size / self.capacity > 0.75:       # 부하율 검사
        self._resize()

def _resize(self):
    old_buckets = self.buckets                 # 1. 옛 칸 보관
    self.capacity = self.capacity * 2          # 2. 칸 수 2배
    self.buckets = [None] * self.capacity      #    빈 새 칸

    for old_head in old_buckets:               # 3. 옛 칸의 노드를 하나씩 옮김
        current = old_head
        while current is not None:
            next_node = current.next                       # 옛 체인의 다음을 메모
            index = self._get_bucket_index(current.key)    # 새 칸 번호 (어디로)
            new_head = self.buckets[index]                 # 새 칸의 맨 앞 (누구 앞에)
            current.next = new_head                        # ① 내가 맨 앞을 붙잡고
            self.buckets[index] = current                  # ② 칸이 나를 가리킴
            current = next_node                            # 메모해 둔 다음으로
```

옮기는 과정 (옛 1번 칸의 a, e, i → 새 5, 1, 5번 칸):

```
옛[1] → (a) → (e) → (i)

a 옮김:  새[5] → (a)
e 옮김:  새[1] → (e)
i 옮김:  새[5] → (i) → (a)      ← i가 a를 먼저 붙잡고, 칸이 i를 가리킴
```

## 완료 확인

```bash
python mini_redis/store.py
# 모든 테스트 통과!
# 256 100
# 3단계 통과!

python -m pytest -v    # 2개 통과
```

## 짜면서 막혔던 것

### 빈칸 채우기

- `self.capacity = capacity * 2` → `_resize`는 인자로 `capacity`를 안 받음 → `self.capacity * 2`
- `index = self.buckets[index]` → `self.buckets[index]`는 칸 안의 **노드**지 칸 **번호**가 아님. 그리고 오른쪽 `index`는 아직 없음 → `self._get_bucket_index(current.key)`
- `current.next = head`, `self.buckets[index] = head` → `head`는 **옛 칸**의 첫 노드. 붙여야 하는 건 **새 칸**의 맨 앞 → `current.next = self.buckets[index]`, `self.buckets[index] = current`
- `current = current.next` → 바로 위에서 `current.next`를 새 칸 쪽으로 바꿨으니 옛 체인을 잃어버림 → 미리 메모해 둔 `next_node`로 이동

### head가 두 개라 헷갈림

- 새 칸의 맨 앞도 head인데, 코드에는 옛 칸의 head(`for head in ...`)만 이름이 있었음
- → `old_head`, `new_head`로 이름을 나눠서 어느 칸의 head인지 드러나게 함

### `current.next = self.buckets[index]`는 뭘 구하는 건가?

- 구하는 게 아니라 **연결**하는 것. `=`는 오른쪽을 왼쪽에 넣음
- `self.buckets[index]`가 오른쪽이면 "칸에 지금 뭐가 있지?"(읽기), 왼쪽이면 "칸에 이걸 넣어"(쓰기)
- `index`와 `new_head`는 줄 서기로 생각하면 됨 → "몇 번 줄?"(`index`) + "그 줄 맨 앞이 누구?"(`new_head`)

### ①, ② 순서

- ②를 먼저 하면 칸이 `current`로 바뀌어서 원래 맨 앞 노드를 가리키는 게 없어짐 → 그 노드를 잃어버림
- 2단계 `set`의 `Node(key, value, head)`와 같은 원리: 새 노드가 기존 head를 잡고 → 칸이 새 노드를 가리킴

## 내가 이해한 것

- **부하율** = `size / capacity`. 칸당 평균 몇 개인지. 0.75가 모든 칸에 0.75개씩이라는 뜻은 아님
- **재해싱이 필요한 이유**: 칸 번호가 `hash(key) % capacity`라서 칸 수가 바뀌면 번호도 바뀜. 통째로 복사하면 `get`이 엉뚱한 칸을 봐서 못 찾음
- **`capacity`를 먼저 바꾸는 이유**: `_get_bucket_index`가 `self.capacity`를 쓰니까 새 칸 번호를 계산하기 전에 바뀌어 있어야 함
- **`set`을 다시 부르지 않는 이유**: `size`가 두 번 세지고, `set` 안에서 또 `_resize`가 불릴 수 있음. 노드도 새로 만들 필요 없이 있던 걸 옮기면 됨 (`size`도 그대로)
- **2배로 늘리는 이유**: 1칸씩 늘리면 거의 매번 재해싱. 2배씩이면 가끔만 해서 평균 비용이 거의 일정함
- **검사 위치**: 항목 수가 늘어나는 곳은 `set`의 새 키 추가뿐. 덮어쓰기는 개수가 그대로라 검사 안 함
- 키 100개면 4 → 8 → 16 → 32 → 64 → 128 → 256 (97번째 키에서 97 / 128 ≈ 0.76이 돼서 한 번 더 늘어남)

## 남은 것 / 미결정

- 지우다 보면 부하율이 아주 낮아질 수 있음. 줄이는 건 이번에 안 함 (선택)
- 확장할 때 이미 만료된 항목을 옮길지 버릴지 → 4단계 만료를 만든 뒤에 정함
