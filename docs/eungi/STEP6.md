# 6단계: 입력 검증 (구현 완료)

## 팀 공유 요약

- **한 일**: `server.py`에 입력 조건을 확인하는 함수 두 개를 추가하고, 조건을 어기면 400을 돌려줌
- **다른 코드에 영향**: 없어요. `HashTable`과 `Store`는 그대로이고, `server.py`만 바뀌었어요
- **확인 방법**: `python -m pytest -v` → `test_bad_inputs`, `test_good_flow` 통과 확인

## 목표

입력 조건을 어긴 요청을 서버가 걸러서 400으로 응답함. (R3, R9)

- [x] 빈 키, 없는 value, 잘못된 ttl 등에 400 응답
- [x] 저장소에는 올바른 입력만 전달

## 어떤 경우를 막아야 하는지 어떻게 알았나

서버를 켜고 `curl`로 의도적으로 이상한 요청을 보내 보면 알 수 있음.

```bash
# 키가 빈 문자열 → 저장은 되지만 조회할 때 ""로 찾아야 해서 쓸모없음
curl -X POST localhost:8000/set -d '{"key":"","value":1}'

# value가 없음 → data["value"] 접근 시 None이 되고,
#   get이 None을 돌려주는 것과 구분이 안 됨 (DESIGN.md: None은 저장 불가)
curl -X POST localhost:8000/set -d '{"key":"a"}'

# ttl이 문자열 → hash_table.py에서 time.time() + "5" → TypeError 500
curl -X POST localhost:8000/set -d '{"key":"a","value":1,"ttl":"5"}'

# ttl이 True → 파이썬에서 True == 1이라 1초 TTL이 조용히 들어감
curl -X POST localhost:8000/set -d '{"key":"a","value":1,"ttl":true}'

# ttl이 음수 → 저장 즉시 만료. 의미 없음 (DESIGN.md: 0보다 큰 숫자)
curl -X POST localhost:8000/set -d '{"key":"a","value":1,"ttl":-1}'
```

기준은 "이 값이 나중에 어디서 쓰이나"를 따라가는 것임. `ttl`은 `hash_table.py`에서 `time.time() + ttl`로 쓰이므로, 숫자가 아니거나 의미 없는 값이 오면 막아야 함.

## 구현: `mini_redis/server.py`

```python
import math

def _bad_request(message):
    return jsonify({"error": message}), 400

def _is_valid_key(key):
    return isinstance(key, str) and key != ""

def _is_valid_ttl(ttl):
    if ttl is None:
        return True                                      # 생략하면 만료 없음 → 허용
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        return False                                     # True/False, 문자열 등 → 거절
    return math.isfinite(ttl) and ttl > 0               # 0 이하, 무한대 → 거절
```

`isinstance(ttl, bool)`을 먼저 확인하는 이유: 파이썬에서 `bool`은 `int`의 하위 클래스라 `isinstance(True, int)`가 `True`가 됨. 순서를 바꾸면 `True`/`False`가 통과됨.

```python
@app.post("/set")
def set_value():
    data = request.get_json(silent=True, force=True)   # Content-Type 헤더가 없어도 JSON으로 해석
    if not isinstance(data, dict):
        return _bad_request("body must be a JSON object")
    if not _is_valid_key(data.get("key")):
        return _bad_request("key must be a non-empty string")
    if data.get("value") is None:
        return _bad_request("value is required and cannot be null")
    if not _is_valid_ttl(data.get("ttl")):
        return _bad_request("ttl must be a positive number of seconds")
    store.set(data["key"], data["value"], data.get("ttl"))
    return jsonify({"ok": True})
```

`force=True`를 추가한 이유: `curl -d '...'`처럼 `Content-Type` 헤더 없이 보내도 JSON으로 해석하게 함. 외부에서 쉽게 쓸 수 있어야 하는 요구사항(R3).

```python
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "no such endpoint"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "method not allowed"}), 405
```

Flask 기본값은 없는 주소나 잘못된 메서드에 HTML을 돌려줌. API를 쓰는 쪽이 실패 응답을 항상 `{"error": ...}` 모양으로 처리할 수 있도록 JSON으로 맞춤.

## 고민했던 것

**검증을 어디서 하나: server.py vs store.py?**

`store.py`에서 하면 HTTP가 아닌 경로로 `Store`를 써도 보호됨. 하지만 HTTP 400 응답은 `server.py`의 개념이라 `store.py`에 넣으면 섞임. `server.py`에서 하면 저장소는 단순하게 유지되고 "올바른 입력만 받는다"는 약속이 명확해짐 → `server.py`에서 처리 (DESIGN.md 결정 6단계).

**value가 None인 걸 왜 막나?**

`get`이 없는 키에 `None`을 돌려줌. 만약 `None`을 값으로 저장할 수 있으면, `get`의 `None`이 "없는 키"인지 "None이 저장된 키"인지 구분이 안 됨. → `None`은 저장 불가 (DESIGN.md 결정 1단계).

## 테스트: `tests/test_api.py`

```python
def test_bad_inputs():
    assert client.post("/set", json={"key": "", "value": 1}).status_code == 400
    assert client.post("/set", json={"key": "a"}).status_code == 400           # value 없음
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": -1}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": "5"}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": True}).status_code == 400
    assert client.get("/get").status_code == 400       # key 없음
    assert client.delete("/delete?key=").status_code == 400   # key 빈 문자열

def test_good_flow():
    assert client.post("/set", json={"key": "a", "value": 1}).status_code == 200
    assert client.get("/get?key=a").get_json() == {"key": "a", "value": 1}
```
