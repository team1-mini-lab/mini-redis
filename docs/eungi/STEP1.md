# 1단계: 뼈대

## 목표

API 3개와 임시 저장소를 만듭니다. API로 저장한 값이 조회되고, 삭제한 뒤에는 404가 나오면 완료입니다. (R3, R6)

## 핵심: 서버와 저장소의 경계

```
server.py  (HTTP를 아는 쪽)      요청 해석 → 저장소 함수 호출 → 응답 코드 결정
    │  store.set / store.get / store.delete
    ▼
store.py   (HTTP를 모르는 쪽)    값을 넣고, 꺼내고, 지움
```

- 서버는 저장소 안에 `dict`가 있다는 사실을 모르고, 함수 3개만 앎.
- 저장소는 404 같은 응답 코드를 만들지 않고 `None`, `True`, `False`만 돌려줌.

## 왜 임시 저장소는 dict를 "감싼" 것인가

1. **dict가 이미 해시 테이블이라서.** 파이썬 dict는 해시 테이블을 언어가 미리 만들어 둔 것임. 1단계에서는 완성품을 잠깐 빌려 쓰고, 그동안 서버와 API를 먼저 완성함. 한 번에 하나씩만 새로 만들어야 문제가 생겼을 때 어느 쪽 잘못인지 알 수 있음.
2. **나중에 속만 바꾸려고.** 서버가 dict를 직접 만지지 못하고 `set`, `get`, `delete`로만 접근하게 함. 그래서 2단계에서 dict를 해시 테이블로 바꿀 때 `store.py`만 고치고 `server.py`는 그대로 둠. (운전대와 페달은 그대로 두고 엔진만 교체)

## 구현

### mini_redis/store.py

```python
class Store:
    """1단계 임시 저장소. 2단계에서 내부의 dict를 해시 테이블로 교체한다."""

    def __init__(self):
        self._data = {}

    def set(self, key, value, ttl=None):
        self._data[key] = value          # ttl은 4단계에서 처리

    def get(self, key):
        return self._data.get(key)       # 없으면 None

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False
```

### mini_redis/server.py

```python
@app.post("/set")
def set_value():
    data = request.get_json()
    store.set(data["key"], data["value"], data.get("ttl"))
    return jsonify({"ok": True})

@app.get("/get")
def get_value():
    key = request.args.get("key")
    value = store.get(key)
    if value is None:
        return jsonify({"error": "key not found"}), 404
    return jsonify({"key": key, "value": value})

@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    return jsonify({"deleted": store.delete(key)})
```

- `app.json.ensure_ascii = False`: 한글을 `\uXXXX`가 아닌 글자 그대로 응답
- `data.get("ttl")`: ttl은 선택 값이라 `data["ttl"]`로 꺼내면 없을 때 `KeyError`가 남. `.get()`은 없으면 `None`

## 완료 확인 (통과)

```bash
curl -X POST localhost:5001/set -H "Content-Type: application/json" -d '{"key":"name","value":"벨로시티"}'
curl -i "localhost:5001/get?key=name"
curl -i -X DELETE "localhost:5001/delete?key=name"
curl -i "localhost:5001/get?key=name"
curl -i -X DELETE "localhost:5001/delete?key=name"
```

| 명령 | 결과 |
| --- | --- |
| `POST /set` | 200 `{"ok": true}` |
| `GET /get?key=name` | 200 `{"key": "name", "value": "벨로시티"}` (한글 그대로) |
| 첫 번째 `DELETE` | 200 `{"deleted": true}` |
| 다시 `GET` | **404** `{"error": "key not found"}` → 1단계 완료 |
| 두 번째 `DELETE` | 200 `{"deleted": false}` (오류가 아님) |

## 고민 1. 잘못된 요청이 500 에러가 됨

- 상태 코드: 4xx는 요청한 쪽 잘못(400 형식 틀림, 404 없음), 5xx는 서버 쪽 잘못(500 코드가 터짐)
- 지금 코드에서 500이 나는 요청:

| 요청 | 결과 | 이유 |
| --- | --- | --- |
| `{"key":"a"}` (value 빠짐) | 500 | `data["value"]`에서 `KeyError` |
| `{"value":1}` (key 빠짐) | 500 | `data["key"]`에서 `KeyError` |
| `{"key":[1,2],"value":1}` | 500 | 리스트는 dict 키로 쓸 수 없음 (unhashable) |
| 본문이 `[1,2]` 또는 `null` | 500 | 객체가 아니라 `["key"]`를 꺼낼 수 없음 |

- 사용자 실수인데 서버 고장처럼 보임 → 400이 맞음
- **결정: 6단계에서 서버가 입력을 검증해 400으로 응답. 저장소에는 올바른 입력만 전달** (팀 결정표 6단계와 같음)

## 고민 2. "키 없음"과 "값이 None"을 구분할 수 없음

`store.get()`이 `None`을 돌려주는 경우가 두 가지임.

| 상황 | `store.get("a")` |
| --- | --- |
| 키 `a`가 아예 없음 | `None` |
| 키 `a`가 있고 값이 `None` | `None` |

- 결과가 같으니 서버는 있는 키인데도 404로 답함
- 원인: 반환값 하나에 "키가 있는지"와 "값이 뭔지"를 함께 담으려 해서 겹침 (사물함이 없는 것과 사물함이 비어 있는 것을 "안에 뭐 있어?" 하나로만 물어본 셈)
- 빈 문자열, `0`, `[]` 같은 값은 `None`이 아니라서 구분됨. 그래서 `is None`으로 확인해야 하고 `if not value:`를 쓰면 안 됨

```python
>>> d = {"a": "", "d": None}
>>> d.get("a") is None   # False → 빈 문자열은 "없음"이 아님
>>> d.get("d") is None   # True
>>> d.get("x") is None   # True  ← 이 두 줄이 구분 안 됨
>>> not d.get("a")       # True  ← not을 쓰면 빈 값까지 "없음"으로 판단
```

### 선택지

| 선택지 | 아이디어 |
| --- | --- |
| ① `contains()` 분리 | "키가 있어?"를 묻는 함수를 따로 둠 (`key in d`와 같은 방식) |
| ② `(found, value)` 반환 | 있는지와 값을 한 번에 돌려줌 (Go의 `v, ok := m[key]`) |
| ③ 전용 표시 객체 | `None` 대신 "없음"만 뜻하는 객체 사용 (`MISSING = object()`) |
| ④ `KeyError` | 없으면 예외 (`d[key]`와 같은 방식) |
| ⑤ null 값 금지 | 값으로 `None`을 저장하지 못하게 함 |

### 결정: ⑤ null 값 금지

- 막는 것은 "키는 있는데 값이 `None`인 상태". 이 상태가 아예 생기지 않으니 `get`의 `None`은 항상 "키가 없음"을 뜻하게 됨
- 키가 없는 경우를 없애는 게 아니라, 키가 없는 경우와 헷갈릴 수 있는 상태를 없애는 것
- 이유: 실제 Redis와 같음(값은 항상 문자열), 6단계 입력 검증과 같이 처리 가능, 4단계 만료도 "None = 없음"으로 통일됨
- 단점: null을 저장할 수 없음. 필요한 경우(없음을 캐싱, 모름/비어 있음 구분)도 약속된 문자열이나 삭제로 대신할 수 있음. null 요청은 대부분 클라이언트 버그라 400으로 알려주는 게 나음
- 금지되는 건 값 자체가 `null`일 때만. `{"value": {"name": null}}`처럼 객체 안의 null은 괜찮음

> 정정: 처음에는 "정말 키가 None인 경우만 알아낼 수 있다"고 적었는데, 정확히는 "`get`이 `None`이면 **키가 없는 경우**라고 확신할 수 있다"임.

## 6단계로 미룬 것

- 필수 항목(`key`, `value`)이 빠진 요청 → 지금은 500
- `?key=` 없이 보낸 `/get`, `/delete` → 지금은 404와 200 `{"deleted": false}`
- 빈 문자열 키, 문자열이 아닌 키
- 값이 `null`인 요청 → 지금은 저장되고, 조회하면 404
- ttl 검증 (`true`는 파이썬에서 `int`로 통과하므로 `bool`을 따로 걸러야 함)
