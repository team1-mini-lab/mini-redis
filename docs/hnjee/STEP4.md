# 4단계: 만료

## 목표

값을 저장할 때 보관 기간(`ttl`, 초)을 함께 받을 수 있게 합니다. 기간이 지난 값은 없는 키와 똑같이 다룹니다.

완료 기준

- 5초짜리로 저장한 값이 바로 조회되고, 5초 뒤에는 404가 나옴
- `ttl` 없이 저장한 값은 시간이 지나도 조회됨
- 단위 테스트가 모두 통과함

## 핵심 문제

지금 저장소는 한 번 넣은 값이 **`delete`를 부르기 전까지 영원히 남습니다.** 이러면 두 가지가 깨집니다.

1. **오래된 값이 계속 나갑니다.** 원본이 바뀌었는데 캐시 삭제를 빠뜨린 코드 경로가 있거나, 원본이 외부 API라서 바뀐 것을 알 방법이 없으면 캐시의 값이 영원히 그대로입니다.
2. **메모리가 줄지 않습니다.** 한 번 조회되고 다시는 쓰이지 않는 키도 계속 쌓입니다.

그래서 "이 값은 5초만 유효하다"는 정보를 함께 저장하고, 기간이 지나면 없는 키처럼 다뤄야 합니다. 풀어야 할 문제는 세 가지입니다.

1. 무엇을 저장하는가 → 만료 **시점** (`지금 + ttl`)
2. 어디에 저장하는가 → 값 자리에 `(값, 만료 시점)` 튜플. `HashTable`은 고치지 않음
3. 누가 언제 지우는가 → 조회할 때 확인하고 그 자리에서 지움 (지연 삭제)

## 질문과 정리

| 질문 | 정리 |
| --- | --- |
| 기간(`ttl`)과 시점 중 무엇을 저장하는가 | 시점. "5초"만으로는 언제부터 5초인지 알 수 없음. 시점을 저장하면 `get`에서 현재 시각과 비교만 하면 됨 |
| 원본 DB가 바뀌면 캐시를 지우는 건 누구 책임인가 | 원본을 수정하는 코드(8단계 데모 API). 레디스는 원본이 있는지조차 모르고 키와 값만 앎. 아래 설명 참고 |
| 원본 수정 때 지운다면 만료는 왜 필요한가 | 안전망. 삭제를 빠뜨려도, 원본이 바뀐 걸 알 수 없어도, 늦어도 언젠가는 사라지게 함 |
| 만료된 항목은 누가 언제 지우는가 | 4단계는 지연 삭제(조회할 때 확인). 주기적 정리는 13단계. 아래 설명 참고 |
| 만료 시점을 어디에 넣는가 | 값 자리에 `(값, 만료 시점)` 튜플. `HashTable`은 값을 그대로 넣고 돌려주므로 한 줄도 고치지 않음 |
| `ttl`을 생략하면 만료 시점 자리에 무엇을 넣는가 | `None`. 아래 설명 참고 |
| `get`이 만료를 발견하면 `None`만 돌려주면 되는가 | 그 자리에서 지워야 함. 안 지우면 메모리에 남고, `_size`에 계속 세어져 적재율이 부풀고 필요 없는 확장이 생길 수 있음 |
| 만료됐지만 아직 테이블에 남은 키를 `delete`하면 | 항목은 지우고 `False`. 사용하는 쪽에서는 이미 없는 키였음. 아래 설명 참고 |
| 덮어쓰면 만료 시점은 | 새로 정함. `ttl`을 생략하면 만료가 없어짐 |
| 현재 시각은 어디서 얻는가 | `time.monotonic()`. 아래 설명 참고 |

### 무효화와 만료는 서로 다른 일

| | 무효화 (8단계) | 만료 (4단계) |
| --- | --- | --- |
| 하는 일 | 원본이 바뀐 **즉시** 캐시를 지움 | **늦어도 언젠가는** 사라지게 함 |
| 누가 | 원본을 수정하는 코드가 `delete`를 부름 | 미니 레디스가 스스로 |
| 놓치는 것 | 삭제를 빠뜨린 경로, 바뀐 걸 알 수 없는 원본 | 만료 전까지는 오래된 값이 나갈 수 있음 |

둘은 서로를 대신하지 않고 같이 씁니다.

### 지연 삭제와 주기적 정리

| | (a) 지연 삭제 | (b) 주기적 정리 |
| --- | --- | --- |
| 방법 | `get`이 그 키만 확인하고, 지났으면 그때 지움 | 별도 스레드가 일정 간격으로 훑으며 지움 |
| 장점 | 만료된 값이 절대 나가지 않음. 비용이 작음 | 조회되지 않는 키도 사라짐 |
| 약점 | 다시 조회되지 않는 키는 메모리에 계속 남음 | 훑는 간격 사이에 조회가 오면 만료된 값이 나감 |
| 단계 | 4단계 | 13단계 (시간이 남으면) |

- 과제 요구(R5)는 **"만료된 값을 요청받았을 때의 처리"**입니다. "만료된 값을 돌려주지 않는다"가 핵심이고, 이건 (a)만으로 완전히 만족됩니다.
- (b)만 쓰면 R5를 어깁니다. 그래서 **(a)가 정확성을 책임지고, (b)는 메모리를 돕는 보조**입니다. 실제 레디스도 둘을 함께 씁니다.

### 만료 없음은 `None`으로 표시

| 만료 시점 자리 | 만료 확인 코드 | 특징 |
| --- | --- | --- |
| `None` (고름) | `expires_at is not None and now >= expires_at` | "만료 없음"이 코드에 드러남 |
| `float("inf")` | `now >= expires_at` | 비교가 한 줄로 끝나지만, 출력하면 `inf`라 뜻이 덜 분명함 |

- `None`과 숫자를 크기 비교하면 `TypeError`가 납니다. 그래서 `is not None`을 앞에 둡니다. `and`는 앞쪽이 거짓이면 뒤쪽을 실행하지 않으므로 비교가 일어나지 않습니다.
- `inf`는 표준 JSON에 없는 값이라 14단계에서 파일로 남길 때 문제가 될 수 있습니다. `None`은 JSON의 `null`로 저장됩니다.
- 실제 레디스의 `TTL` 명령도 만료가 없는 키에 큰 숫자 대신 `-1`을 돌려줘 따로 표시합니다.

### 만료된 키의 `delete`가 `False`인 이유

1단계에서 정한 뜻은 이렇습니다.

- **HTTP 200**: "값이 없는 상태가 됐다". 이미 없었어도 목적을 이뤘으므로 언제나 200
- **`deleted`의 `True`/`False`**: "지울 키가 있었는가"

만료된 키는 사용하는 쪽에서 보면 만료 시점부터 이미 없는 키였으므로 `False`입니다. 테이블에서 항목을 치우는 건 저장소 안의 뒷정리일 뿐입니다. 이렇게 하면 `get`을 먼저 불렀든 안 불렀든 `delete`의 결과가 같습니다.

| 상황 | 테이블에서 지우나 | `delete` 반환값 | API 응답 |
| --- | --- | --- | --- |
| 만료되지 않은 키 | 지움 | `True` | 200 `{"deleted": true}` |
| 만료됐지만 테이블에 남아 있던 키 | 지움 | `False` | 200 `{"deleted": false}` |
| 원래 없던 키 | 지울 것이 없음 | `False` | 200 `{"deleted": false}` |

가운데 경우만 "테이블에서는 실제로 지웠는데 반환값은 `False`"입니다. 바깥에서 보면 두 번째와 세 번째 경우는 구분되지 않고, 둘 다 "지울 키가 없었다"입니다. 코드에서는 `delete`의 마지막 줄 `return not self._is_expired(expires_at)`이 첫 번째와 두 번째 경우를 가르고, 세 번째 경우는 그 앞의 `if item is None: return False`에서 끝납니다.

```
get을 먼저 부른 경우:   get → 만료 발견, 지움, None  →  delete → 키 없음 → False
바로 delete한 경우:     delete → 만료 발견, 지움     → False   (같은 결과)
```

### 덮어쓰면 만료 시점도 새로 정함

```
set("name", "현지", ttl=5)    # 5초 뒤 만료
3초 뒤 set("name", "민수")     # ttl 없음 → 만료 없음
```

`Store.set`은 매번 `(값, 만료 시점)` 튜플을 새로 만들어 넣으므로, 이전 만료 시점은 덮어쓰면서 저절로 사라집니다. 이전 만료 시점을 유지하려면 먼저 꺼내 옮겨 와야 해서 일이 더 생기고, 이전 값의 만료 시점이 새 값에 남아 예상하지 못한 삭제가 일어납니다. 실제 레디스의 `SET`도 같은 동작이고, 유지하려면 `KEEPTTL` 옵션을 따로 붙입니다.

### `time.time()` 대신 `time.monotonic()`

60초짜리 값을 저장한 직후 맥의 시계가 인터넷 시간과 맞춰지며 1시간 앞으로 당겨졌다고 합시다.

| 시계 | 저장할 때 | 시계가 바뀐 직후 | 결과 |
| --- | --- | --- | --- |
| `time.time()` (달력 시각) | 만료 시점 = 10:00:00 + 60초 | 지금이 11:00:00 | 저장하자마자 만료됨 |
| `time.monotonic()` | 만료 시점 = 5000 + 60 | 지금은 여전히 5000 근처 | 정확히 60초 뒤 만료됨 |

- 달력 시각은 뒤로 가거나 건너뛸 수 있습니다. 반대로 1시간 뒤로 밀리면 60초짜리 값이 1시간 넘게 살아남습니다.
- `monotonic()`은 줄어들지 않는 것만 보장하고, 시계 설정과 무관하게 흐른 시간만 셉니다. "60초가 지났는가"를 재는 데 맞습니다.
- 대가: 기준점이 컴퓨터를 켤 때마다 바뀝니다. 14단계에서 파일로 남긴다면 저장 직전에 "남은 초"로 바꾸는 등의 처리가 필요합니다. 실제 레디스는 파일 저장을 기본으로 하므로 달력 시각으로 저장하고 시계 변경의 위험을 감수합니다.

## 이 단계에서 정한 것

| 관련 코드 | 정한 것 | 이유 |
| --- | --- | --- |
| `server.py` `set_value` (`body.get("ttl")`) | `/set` 본문의 `ttl`은 선택 항목. 있으면 그대로 `store.set`에 넘김 | DESIGN.md 접점 2의 요청 형식과 같음. 검증은 6단계 |
| `store.py` `Store.set` | 항목에 만료 "시점"(`지금 + ttl`)을 저장 | 기간만으로는 언제부터인지 알 수 없음. 조회할 때 현재 시각과 비교만 하면 됨 (DESIGN.md 제안과 같음) |
| `store.py` `Store.set` | 값 자리에 `(값, 만료 시점)` 튜플을 넣고, `HashTable`은 고치지 않음 | 해시 테이블은 값을 그대로 넣고 돌려주므로 만료를 몰라도 됨. 2단계에서 정한 "만료는 `Store`에서 처리"를 따름 |
| `store.py` `Store.set` | `ttl`을 생략하면 만료 시점은 `None` | "만료 없음"이 코드에 드러남. `float("inf")`는 표준 JSON에 없어 14단계 파일 저장과 맞지 않음 |
| `store.py` `Store.set` | 덮어쓰면 만료 시점도 새로 정함. `ttl`을 생략하면 만료가 없어짐 | 이전 값의 만료 시점이 새 값에 남으면 예상하지 못한 삭제가 생김. 실제 레디스 `SET`의 기본 동작과 같음 (DESIGN.md 제안과 같음) |
| `store.py` `Store.__init__` (`clock`) | 현재 시각은 `time.monotonic()` | 시계 설정이 바뀌어도 흐른 시간만 정확히 셈. 기준점이 재부팅마다 바뀌므로 14단계를 하면 저장 방식을 따로 정해야 함 |
| `store.py` `Store.__init__` (`clock`) | 시계를 인자로 받을 수 있게 함 (기본값 `time.monotonic`) | 테스트에서 가짜 시계를 넣어 5초를 기다리지 않고 만료를 확인하기 위함 |
| `store.py` `Store.get` | 만료 확인은 지연 삭제. `get`이 만료를 발견하면 그 자리에서 지우고 `None` | 과제 요구(R5)를 정확히 만족하고 비용이 작음. 지우지 않으면 메모리와 적재율이 부풂. 주기적 정리는 13단계 (DESIGN.md 제안과 같음) |
| `store.py` `Store.get` · `Store.delete` | 만료된 키는 없는 키와 똑같이 취급 (`get`은 `None`, `delete`는 `False`, API는 404). `delete`는 남아 있던 항목을 지우고 `False` | 사용하는 쪽에서는 이미 없는 키. `get`을 먼저 불렀는지에 따라 결과가 달라지지 않음 (DESIGN.md 제안과 같음) |
| `store.py` `_is_expired` | `지금 >= 만료 시점`이면 만료 | `ttl=5`는 "5초 동안 보관"이므로 정확히 5초가 되는 순간 기간이 끝남 |
| `tests/test_store.py` | 4단계 테스트는 `test_store.py`에 추가 | 만료는 `HashTable`이 아니라 `Store`의 일 |
| `server.py` `check_ttl` (6단계) | `ttl`의 단위는 초이고 0보다 큰 숫자. 검증은 6단계 | 단위를 하나로 통일. 0 이하는 저장 즉시 만료되어 의미가 없음 (DESIGN.md 제안과 같음) |

[DECISIONS.md](./DECISIONS.md)에도 같은 내용이 모여 있습니다.

## 만드는 파일

| 파일 | 내용 |
| --- | --- |
| `server.py` (고침) | `set_value`에서 `body.get("ttl")`을 `store.set`에 넘김. 한 줄만 바뀜 |
| `store.py` (고침) | `__init__`에 `clock`, `set`에 `ttl`, `_is_expired` 추가. `get`과 `delete`에 만료 확인 추가 |
| `tests/test_store.py` (고침) | 가짜 시계 `FakeClock`과 4단계 테스트 9개 추가 |
| `hash_table.py` | **고치지 않음** (값 자리에 튜플이 들어가는 줄도 모름) |

## 주요 함수

```
server.set_value  → store.set(key, value, ttl)
                      → expires_at = 지금 + ttl  (ttl이 없으면 None)
                      → HashTable.set(key, (value, expires_at))

server.get_value  → store.get(key)
                      → HashTable.get(key) → (value, expires_at) 또는 None
                      → 만료됐으면 HashTable.delete(key) 후 None, 아니면 value
```

| 함수 | 하는 일 |
| --- | --- |
| `Store.__init__(clock=time.monotonic)` | 해시 테이블을 만들고, 현재 시각을 얻을 함수를 기억함 |
| `Store.set(key, value, ttl=None)` | 만료 시점을 계산해 `(값, 만료 시점)`을 저장 |
| `Store._is_expired(expires_at)` | `expires_at is not None and 지금 >= expires_at` |
| `Store.get(key)` | 없으면 `None`. 만료됐으면 지우고 `None`. 아니면 값 |
| `Store.delete(key)` | 없으면 `False`. 있으면 지우고, 만료되지 않았던 경우에만 `True` |

`store.py`는 이런 모양이 됩니다.

```python
import time

from hash_table import HashTable


class Store:
    def __init__(self, clock=time.monotonic):
        self._table = HashTable()
        self._clock = clock  # 테스트에서는 가짜 시계를 넣음

    def set(self, key, value, ttl=None):
        expires_at = None if ttl is None else self._clock() + ttl
        self._table.set(key, (value, expires_at))

    def _is_expired(self, expires_at):
        return expires_at is not None and self._clock() >= expires_at

    def get(self, key):
        item = self._table.get(key)
        if item is None:
            return None
        value, expires_at = item
        if self._is_expired(expires_at):
            self._table.delete(key)  # 지연 삭제: 발견한 자리에서 지움
            return None
        return value

    def delete(self, key):
        item = self._table.get(key)
        if item is None:
            return False
        _, expires_at = item
        self._table.delete(key)  # 만료됐든 아니든 항목은 치움
        return not self._is_expired(expires_at)  # 만료된 키는 "없던 키"
```

`clock=time.monotonic`에 괄호가 없는 것은 함수를 **부르지 않고 함수 자체를 넘기기** 때문입니다. `self._clock()`처럼 괄호를 붙여 부를 때마다 그 순간의 시각을 얻습니다.

## 완료 테스트

### 1. 단위 테스트

```bash
source .venv/bin/activate
pytest -v
```

기대 결과: `25 passed` (3단계까지 16개 + 4단계 9개). 테스트는 가짜 시계를 써서 기다리지 않고 바로 끝납니다.

```python
class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):  # clock()으로 부르면 지금 시각을 돌려줌
        return self.now
```

테스트에서 `clock.now += 5`로 시간을 5초 흘려보냅니다.

| 테스트 | 확인하는 것 |
| --- | --- |
| `ttl` 없이 저장하면 만료되지 않음 | 시간을 10만 초 흘려도 조회됨 |
| 만료 전에는 조회됨 | `ttl=5`, 4.9초 뒤 조회됨 |
| 만료 시점이 되면 `None` | `ttl=5`, 정확히 5초 뒤 `None` |
| 만료된 키는 `get`할 때 테이블에서 지워짐 | 조회 전 `len`은 1, 조회 후 0 |
| 만료된 키를 `delete`하면 `False`이고 테이블에서 지워짐 | 반환값 `False`, `len`은 0 |
| 만료 전에 `delete`하면 `True` | 2단계와 같은 동작 |
| 덮어쓰면 만료 시점이 새로 정해짐 | 0초에 `ttl=5`, 3초에 다시 `ttl=5`. 6초에는 조회되고 8초에는 `None` |
| `ttl` 없이 덮어쓰면 만료가 없어짐 | 0초에 `ttl=5`, 3초에 `ttl` 없이 덮어씀. 100초 뒤에도 조회됨 |
| 만료된 키에 다시 저장하면 조회됨 | 만료 후 `set`하면 새 값이 나옴 |

### 2. API로 5초 만료 확인 (완료 기준)

서버를 켭니다(`python server.py`). 다른 터미널에서 실행합니다.

```bash
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "temp", "value": "5초짜리", "ttl": 5}'
curl -i "http://127.0.0.1:8000/get?key=temp"
sleep 5
curl -i "http://127.0.0.1:8000/get?key=temp"
```

| 명령 | 기대 결과 |
| --- | --- |
| `POST /set` (`ttl` 5) | 200 `{"ok": true}` |
| 바로 `GET` | 200 `{"key": "temp", "value": "5초짜리"}` |
| 5초 뒤 `GET` | **404** `{"error": "키가 없습니다"}` |

### 3. 만료된 키의 삭제와 덮어쓰기

```bash
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "temp", "value": 1, "ttl": 2}'
sleep 2
curl -i -X DELETE "http://127.0.0.1:8000/delete?key=temp"

curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "name", "value": "현지", "ttl": 2}'
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "name", "value": "민수"}'
sleep 2
curl -i "http://127.0.0.1:8000/get?key=name"
```

| 명령 | 기대 결과 |
| --- | --- |
| 2초 뒤 `DELETE` | 200 `{"deleted": false}` (이미 만료된 키) |
| `ttl` 없이 덮어쓰고 2초 뒤 `GET` | 200 `{"key": "name", "value": "민수"}` (만료가 없어짐) |

### 4. `ttl` 없이 쓰던 API가 그대로인지

[STEP1.md](./STEP1.md)의 완료 테스트 1~4를 다시 실행합니다. 결과가 같으면 됩니다.

1~4가 모두 맞으면 4단계 완료입니다.

## 알아 둘 것

- **서버를 코드 저장으로 다시 시작하면 값이 사라집니다.** `debug=True` 때문입니다. `sleep` 도중에 코드를 저장하면 404가 만료 때문인지 재시작 때문인지 구분할 수 없습니다.
- **`get` 안에서 테이블을 두 번 만집니다.** `HashTable.get`으로 꺼내고, 만료됐으면 `HashTable.delete`로 지웁니다. 그 사이에 다른 요청이 같은 키에 새 값을 `set`하면, 방금 저장된 새 값이 지워질 수 있습니다. 지금은 요청이 하나씩 처리된다고 보고 넘어가고, 5단계에서 `Store` 함수 전체를 lock으로 감싸 막습니다.
- **`dump()`로 보면 값이 튜플로 보입니다.** `name=('현지', 5012.3)`처럼 나옵니다. `HashTable`은 그게 튜플인지 모르고 그대로 보여 줄 뿐입니다.

## 6단계로 미룬 것

지금은 아래 요청이 걸러지지 않습니다. 6단계에서 400으로 처리합니다.

- `"ttl": "abc"` 같은 숫자가 아닌 값 → 지금은 더하기에서 `TypeError`가 나 500
- `"ttl": 0`, `"ttl": -1` → 지금은 저장 즉시 만료됨
- `"ttl": true` → 파이썬에서 `True`는 1로 계산되어 1초짜리로 저장됨

## 이해 확인 질문

코드를 보지 않고 한두 문장으로 답해 봅니다. 답은 눌러서 펼칠 수 있습니다.

<details>
<summary>1. <code>ttl</code>(기간)을 그대로 저장하지 않고 만료 시점으로 바꿔 저장하는 이유는 뭔가요?</summary>

"5초"만으로는 언제부터 5초인지 알 수 없기 때문입니다. 저장할 때 `지금 + 5`를 계산해 두면, 조회할 때 현재 시각과 비교만 하면 됩니다.
</details>

<details>
<summary>2. 만료를 추가하는데 <code>hash_table.py</code>를 한 줄도 고치지 않아도 되는 이유는 뭔가요?</summary>

`HashTable`은 값이 무엇이든 그대로 넣고 그대로 돌려줍니다. `Store`가 값 자리에 `(값, 만료 시점)` 튜플을 넣고 꺼낼 때 풀어서 확인하므로, 해시 테이블은 만료라는 개념을 몰라도 됩니다.
</details>

<details>
<summary>3. 원본 DB를 수정할 때 캐시를 지우면 되는데, 만료는 왜 필요한가요?</summary>

안전망이기 때문입니다. 삭제를 빠뜨린 코드 경로가 있거나 원본이 외부 API라서 바뀐 걸 알 수 없어도, 만료가 있으면 늦어도 언젠가는 오래된 값이 사라집니다. 무효화는 즉시, 만료는 언젠가는 지우는 일이라 둘을 같이 씁니다.
</details>

<details>
<summary>4. 지연 삭제의 약점은 뭐고, 그런데도 4단계에서 지연 삭제만 쓰는 이유는 뭔가요?</summary>

다시 조회되지 않는 키는 만료돼도 메모리에 계속 남습니다. 하지만 과제 요구는 "만료된 값을 요청받았을 때의 처리"이고, 지연 삭제는 만료된 값을 절대 돌려주지 않으므로 그 요구를 완전히 만족합니다. 메모리 문제는 13단계의 주기적 정리가 보조로 맡습니다.
</details>

<details>
<summary>5. <code>get</code>이 만료를 발견했을 때 <code>None</code>만 돌려주고 지우지 않으면 어떤 문제가 생기나요?</summary>

항목이 메모리에 계속 남습니다. 또 `_size`에 계속 세어져 `len()`이 실제보다 커지고, 적재율이 부풀어 필요 없는 확장이 일어날 수 있습니다.
</details>

<details>
<summary>6. 만료됐지만 테이블에 아직 남은 키를 <code>delete</code>하면 왜 <code>False</code>인가요?</summary>

`deleted`는 "지울 키가 있었는가"를 알리는데, 사용하는 쪽에서 보면 그 키는 만료 시점부터 이미 없는 키였기 때문입니다. 이렇게 해야 `get`을 먼저 불렀든 아니든 `delete`의 결과가 같습니다.
</details>

<details>
<summary>7. <code>ttl</code>이 없을 때 만료 시점에 <code>None</code>을 넣었는데, <code>now >= None</code> 같은 비교 오류는 왜 안 나나요?</summary>

`expires_at is not None and ...`처럼 `None`인지 먼저 확인하기 때문입니다. `and`는 앞쪽이 거짓이면 뒤쪽을 실행하지 않으므로 숫자와 `None`을 비교하는 일이 일어나지 않습니다.
</details>

<details>
<summary>8. <code>time.time()</code> 대신 <code>time.monotonic()</code>을 쓰는 이유는 뭔가요? 대가는 뭔가요?</summary>

`time.time()`은 달력 시각이라 시계가 맞춰지거나 바뀌면 건너뛰어서, 값이 너무 일찍 또는 너무 늦게 만료될 수 있습니다. `monotonic()`은 흐른 시간만 세서 정확합니다. 대신 기준점이 재부팅마다 바뀌어 그 값을 파일에 남겨도 다음에 쓸 수 없습니다.
</details>

<details>
<summary>9. 테스트에서 5초를 실제로 기다리지 않고 만료를 확인하는 방법은 뭔가요?</summary>

`Store`가 시계를 인자로 받게 해 두고, 테스트에서는 `now`를 직접 바꿀 수 있는 가짜 시계를 넣습니다. `clock.now += 5`로 시간을 흘려보내면 바로 확인할 수 있습니다.
</details>
