# 6단계: 입력 검증

## 목표

입력 조건을 어긴 요청을 서버가 걸러 400으로 돌려보냅니다. 저장소에는 올바른 입력만 전달합니다.

완료 기준

- 빈 키, 잘못된 `ttl` 등에 400 응답
- 거절된 요청은 저장되지 않음
- API 동작이 5단계와 같음 (올바른 요청은 그대로 동작)
- 단위 테스트가 모두 통과함

## 핵심 문제

5단계까지의 서버에 잘못된 입력을 보내면 이렇게 됩니다.

| 입력 | 지금 응답 | 무엇이 문제인가 |
| --- | --- | --- |
| 숫자 키 `123`, `ttl`이 `"abc"` | **500** | 해시 함수와 만료 계산에서 파이썬 오류가 나서 서버가 터짐 |
| 값이 `null`, `ttl`이 `0`이나 `-1` | 200 | 저장 성공이라고 해 놓고, 조회하면 바로 404 |
| `ttl`이 `true` | 200 | `true`를 1로 계산해 1초짜리로 저장됨 |
| `ttl`이 `NaN` | 200 | **영원히 만료되지 않음** |
| `ttl`을 `"tll"`로 오타 | 200 | 오타가 무시되어 만료 없는 키로 저장됨 |
| 빈 키 `""` | 200 | 저장되고 조회도 됨. 1단계 규칙("비어 있지 않은 문자열")이 지켜지지 않음 |
| `/get?key=` | 404 | "그런 키는 없다"고 답함. 애초에 만들 수 없는 키인데도 |

공통점은 **잘못된 것은 요청인데, 서버가 그걸 알려 주지 못한다**는 것입니다. 500은 "서버가 고장 났다"는 말이라 보낸 쪽은 자기 코드를 의심하지 않고, 200은 "잘 됐다"는 말이라 잘못을 숨깁니다.

풀어야 할 문제는 세 가지입니다.

1. 왜 400인가 → 상태 코드는 "누가 고쳐야 하는가"를 알려 주는 약속
2. 어디서 검사하는가 → `server.py`
3. 무엇을 검사하는가 → 키, 값, `ttl`, 모르는 항목

## 질문과 정리

| 질문 | 정리 |
| --- | --- |
| 실패는 실패인데 왜 500이 아니라 400인가 | 4xx는 클라이언트, 5xx는 서버의 잘못. 500을 받으면 보낸 쪽은 서버 고장으로 알고 다시 보내거나 문의함. 400과 이유를 받으면 바로 자기 코드를 고침 |
| 검증도 lock처럼 `Store`에 넣어야 하는가 | 아님. 둘 다 "그 일을 알 수 있는 쪽이 맡는다"는 원칙. 아래 설명 참고 |
| `ttl`이 `true`이면 | `bool`은 `int`의 한 종류라 숫자 검사를 통과함. `bool`인지 먼저 검사해 막음 |
| `ttl`에 소수를 허용하는가 | 허용함. 시계가 소수 단위라 그대로 동작함 |
| `ttl`이 `NaN`이나 `Infinity`이면 | 파이썬 JSON 파서가 표준이 아닌 이 둘도 받아들임. 범위 검사로 막음. 아래 설명 참고 |
| 키가 공백뿐이면 (`" "`) | 허용함. 빈 문자열만 막음. 실제 레디스도 키 내용을 따지지 않음 |
| `/get?key=`처럼 쿼리의 키가 비어 있으면 | 400. `/set`과 같은 규칙. "그런 키는 애초에 만들 수 없다"고 알려 줌 |
| 값의 범위는 | `null`만 막고 나머지 JSON 값은 모두 허용. 리스트 안의 `null`(`[1, null]`)도 허용. `get`은 리스트를 돌려주므로 "없음"과 헷갈리지 않음 |
| 모르는 항목이 오면 | 400. 오타 `"tll"`을 무시하면 1초 뒤 사라질 줄 안 키가 영원히 남음 |
| 잘못된 곳이 여러 개면 | 처음 발견한 하나만 `{"error": "설명"}`으로 알림. 1단계 형식 그대로 |
| 검증 코드를 어디에 두는가 | `server.py` 안의 검증 함수. 잘못되면 오류 문장, 괜찮으면 `None`을 돌려줌 |
| 테스트는 | `tests/test_server.py`를 새로 만들어 Flask 테스트 클라이언트로 확인. 다른 API 기능 테스트는 10단계 |

### lock은 `Store`에, 검증은 서버에

5단계에서 "저장소는 누가 어떻게 쓰든 스스로 안전해야 한다"며 lock을 `Store`에 넣었습니다. 그 논리라면 검증도 `Store`에 들어가야 할 것 같지만, 그렇지 않습니다.

| | lock | 입력 검증 |
| --- | --- | --- |
| 지키는 것 | 저장소 **안쪽** 상태 (칸, `_size`, 만료 확인 동작) | 바깥에서 들어온 **요청의 모양** |
| 누가 알 수 있나 | 저장소만 앎. 바깥에서는 안이 어떻게 생겼는지 모름 | 서버가 앎. 요청이 JSON으로 왔고, `true`가 JSON의 불리언이라는 건 HTTP를 받는 쪽만 앎 |
| 실패를 알리는 말 | 없음 (기다릴 뿐) | 400과 이유. HTTP의 표현 |

둘 다 **"그 일을 알 수 있는 쪽이 맡는다"**는 같은 원칙에서 나온 결론입니다. 1단계에서 "404는 HTTP의 표현이므로 서버가 정한다"고 한 것과도 같습니다.

8단계 데모 API처럼 파이썬 코드가 `Store`를 직접 부를 때 숫자 키를 넣으면 바로 `TypeError`가 납니다. 그 파이썬 코드를 쓴 개발자의 실수라 바로 드러나고 고치면 되므로 괜찮습니다.

### `true`가 숫자 검사를 통과하는 이유

```bash
python -c 'print(isinstance(True, int), True + 1)'
```

```
True 2
```

파이썬에서 `bool`은 `int`를 물려받은 종류이고, `True`는 1, `False`는 0처럼 계산됩니다. 그래서 `isinstance(ttl, (int, float))`만으로는 `true`가 1초짜리 `ttl`로 통과합니다. `isinstance(ttl, bool)`을 **먼저** 검사해서 막습니다.

### `NaN`, `Infinity`, 아주 큰 정수는 범위 비교 하나로 막음

파이썬의 `json`은 표준 JSON에 없는 `NaN`과 `Infinity`도 숫자로 읽습니다.

| `ttl` | 무엇이 문제인가 |
| --- | --- |
| `NaN` | 어떤 비교도 거짓. `ttl <= 0` 검사를 통과하고, 만료 확인 `지금 >= 만료 시점`도 늘 거짓이라 **영원히 만료되지 않음** |
| `Infinity` | 만료 시점이 무한대라 사실상 만료 없음. 그렇게 하려면 `ttl`을 생략하면 됨 |
| `1` 뒤에 0이 400개인 정수 | 파이썬 정수는 한없이 커질 수 있음. `math.isfinite()`에 넣으면 `OverflowError`가 나서 **검증 코드가 오히려 500**을 냄. `저장소의 지금 + ttl`에서도 같은 오류 |

처음에는 `math.isfinite()`로 `NaN`과 `Infinity`를 막으려 했지만, 아주 큰 정수에서 검증 코드 자체가 터지는 것을 확인했습니다. 그래서 **최댓값을 정하고 범위 비교 하나로** 모두 막습니다.

```python
if not (0 < ttl <= MAX_TTL):   # 범위 밖이면 400
```

| `ttl` | `0 < ttl <= MAX_TTL` | 결과 |
| --- | --- | --- |
| `5`, `1.5` | 참 | 통과 |
| `0`, `-1` | 거짓 (`0 < ttl`이 거짓) | 400 |
| `NaN` | 거짓 (`NaN`과의 비교는 모두 거짓) | 400 |
| `Infinity`, 아주 큰 정수 | 거짓 (`ttl <= MAX_TTL`이 거짓) | 400 |

파이썬은 정수와 소수를 비교할 때 소수로 바꾸지 않고 정확히 비교하므로, 아주 큰 정수도 오류 없이 비교됩니다.

최댓값은 **10년**(315,360,000초)으로 정합니다. 캐시를 10년 넘게 보관하는 것은 사실상 "만료 없음"이고, 그러려면 `ttl`을 생략하면 됩니다.

### 검증 순서

여러 군데가 잘못돼도 처음 발견한 하나만 알립니다. 순서는 이렇습니다.

```
/set 본문
1. JSON 객체인가               → 아니면 "요청 본문은 JSON 객체여야 합니다"
2. key와 value가 있는가        → 없으면 "key와 value가 필요합니다" (1단계 문장 그대로)
3. 모르는 항목이 없는가         → 있으면 "알 수 없는 항목입니다: tll"
4. key가 비어 있지 않은 문자열인가
5. value가 null이 아닌가
6. ttl이 생략됐거나 올바른 숫자인가

/get, /delete 쿼리
1. key가 있는가                → 없으면 "key가 필요합니다" (1단계 문장 그대로)
2. key가 비어 있지 않은가
```

쿼리로 오는 키는 언제나 문자열이라, 문자열인지 검사는 `/set`에서만 의미가 있습니다. `/get`과 `/delete`에서 `key` 말고 다른 쿼리 항목은 무시합니다.

## 이 단계에서 정한 것

| 관련 코드 | 정한 것 | 이유 |
| --- | --- | --- |
| `server.py` `check_set_body`, `check_key`, `check_ttl` | 입력 검증은 `server.py`의 검증 함수에서 함. 잘못되면 오류 설명, 괜찮으면 `None`을 돌려주고, 경로 함수가 400으로 응답. 저장소에는 올바른 입력만 전달 | 검증을 한 곳에 모아 저장소를 단순하게 유지. 요청의 모양은 HTTP를 받는 쪽만 앎 (DESIGN.md 제안과 같음) |
| `server.py` 경로 함수의 실패 응답 | 클라이언트의 잘못된 입력에는 500이 아니라 400 | 4xx는 "보낸 쪽이 고쳐야 함"을 알림. 500이면 보낸 쪽이 서버 고장으로 오해함 |
| `server.py` `check_set_body` | 잘못된 곳이 여러 개면 처음 발견한 하나만 `{"error": "설명"}`으로 알림 | 1단계의 실패 응답 형식 그대로. 하나씩 고치면 됨 |
| `server.py` `check_set_body` (`SET_FIELDS`) | `/set` 본문에 `key`, `value`, `ttl` 말고 다른 항목이 있으면 400 | 오타 `"tll"`이 무시되면, 곧 사라질 줄 안 키가 영원히 남음 |
| `server.py` `check_set_body` | `/set` 본문이 JSON 객체가 아니면 "요청 본문은 JSON 객체여야 합니다" | 1단계에서는 "key와 value가 필요합니다"로 함께 처리했지만, 원인을 정확히 알려 줌 |
| `server.py` `check_key` | 키는 비어 있지 않은 문자열. 공백뿐인 키(`" "`)는 허용 | 1단계에서 정한 규칙. 실제 레디스도 키 내용을 따지지 않음 (DESIGN.md 제안과 같음) |
| `server.py` `get_value`, `delete_value` (`check_key`) | 쿼리의 키가 비어 있으면(`?key=`) 400 | `/set`과 같은 규칙. 404("없음")가 아니라 "애초에 만들 수 없는 키"라고 알려 줌 |
| `server.py` `check_set_body` | 값은 `null`만 막고 나머지 JSON 값은 모두 허용. 리스트 안의 `null`도 허용 | `get`이 돌려주는 `None`이 언제나 "없음"이면 됨. 리스트는 `None`이 아님 (DESIGN.md 제안과 같음) |
| `server.py` `check_ttl` | `ttl`은 숫자(`int`, `float`)이고 `bool`은 막음 | 파이썬의 `bool`은 `int`의 한 종류라, 막지 않으면 `true`가 1초로 저장됨 |
| `server.py` `check_ttl` | `ttl`은 소수도 허용 (`1.5`초) | 시계가 소수 단위라 그대로 동작함 |
| `server.py` `check_ttl` (`MAX_TTL`) | `ttl`의 범위는 `0 < ttl <= 10년`(315,360,000초). 이 비교 하나로 0 이하, `NaN`, `Infinity`, 아주 큰 정수를 모두 막음 | `math.isfinite()`는 아주 큰 정수에서 `OverflowError`를 내 500이 됨. `NaN`은 비교가 모두 거짓이라 범위 밖으로 걸림. 10년 넘는 보관은 `ttl`을 생략하면 됨 (DESIGN.md의 "0보다 큰 숫자" 제안에 최댓값을 더함) |
| `server.py` `check_ttl` | `"ttl": null`은 생략과 같이 만료 없음 | JSON의 `null`은 "없음"이라는 뜻 |
| `tests/test_server.py` | 검증 테스트는 `tests/test_server.py`를 새로 만들어 Flask 테스트 클라이언트로 확인. 테스트마다 `server.store`를 빈 `Store()`로 바꿔 끼움 | 서버를 띄우지 않고 API를 확인할 수 있음. 테스트끼리 영향을 주지 않음. 다른 API 기능 테스트는 10단계 |

[DECISIONS.md](./DECISIONS.md)에도 같은 내용이 모여 있습니다.

## 만드는 파일

| 파일 | 내용 |
| --- | --- |
| `server.py` (고침) | `SET_FIELDS`, `MAX_TTL`, `check_key`, `check_ttl`, `check_set_body` 추가. 경로 3개의 첫 `if`를 검증 함수 호출로 바꿈 |
| `tests/test_server.py` (새로 만듦) | 검증 테스트 29개 (같은 테스트에 입력만 바꾼 것 포함) |
| `docs/hnjee/DECISIONS.md`, `STEP1.md`, `STEP4.md` (고침) | "아직 없음 (6단계에서 `server.py`에 추가)"로 적어 둔 줄의 관련 코드를 실제 함수 이름으로 바꿈 |
| `store.py`, `hash_table.py` | **고치지 않음** |

구현은 이 순서로 합니다.

1. `tests/test_server.py`를 먼저 만들고, 지금 서버로 실행해 **실패하는 것을 확인**
2. `server.py`에 검증 추가
3. 같은 테스트가 통과하는 것을 확인

## 주요 함수

```python
SET_FIELDS = {"key", "value", "ttl"}       # /set 본문에 올 수 있는 항목
MAX_TTL = 10 * 365 * 24 * 60 * 60          # ttl의 최댓값: 10년(초)


def check_key(key):
    if key is None:
        return "key가 필요합니다"
    if not isinstance(key, str):
        return "key는 문자열이어야 합니다"
    if key == "":
        return "key는 비어 있으면 안 됩니다"
    return None


def check_ttl(ttl):
    if ttl is None:                         # 생략하거나 null이면 만료 없음
        return None
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not (0 < ttl <= MAX_TTL):
        return f"ttl은 0보다 크고 {MAX_TTL} 이하인 숫자(초)여야 합니다"
    return None


def check_set_body(body):
    if not isinstance(body, dict):
        return "요청 본문은 JSON 객체여야 합니다"
    if "key" not in body or "value" not in body:
        return "key와 value가 필요합니다"
    unknown = body.keys() - SET_FIELDS
    if unknown:
        return f"알 수 없는 항목입니다: {', '.join(sorted(unknown))}"
    error = check_key(body["key"])
    if error:
        return error
    if body["value"] is None:
        return "value로 null은 저장할 수 없습니다"
    return check_ttl(body.get("ttl"))
```

경로 함수는 이런 모양이 됩니다.

```python
@app.post("/set")
def set_value():
    body = request.get_json(silent=True)
    error = check_set_body(body)
    if error:
        return {"error": error}, 400

    store.set(body["key"], body["value"], body.get("ttl"))
    return {"ok": True}
```

`/get`과 `/delete`는 첫 `if key is None:`을 `error = check_key(key)`로 바꿉니다.

| 부분 | 하는 일 |
| --- | --- |
| `body.keys() - SET_FIELDS` | 본문의 항목 이름들에서 허용된 이름을 뺀 나머지. 비어 있지 않으면 모르는 항목이 있음 |
| `isinstance(ttl, bool) or ...` | `or`는 앞에서 참이 나오면 뒤를 실행하지 않음. 그래서 문자열 `ttl`은 `0 < ttl` 비교까지 가지 않아 오류가 나지 않음 |
| `0 < ttl <= MAX_TTL` | 파이썬의 연쇄 비교. `0 < ttl and ttl <= MAX_TTL`과 같음 |

## 완료 테스트

### 1. 단위 테스트: 검증 없이 먼저, 그다음 검증과 함께

```bash
source .venv/bin/activate
pytest -v
```

| 테스트 | 확인하는 것 |
| --- | --- |
| 잘못된 `/set` 본문 14가지 | 객체가 아님, `value` 없음, 오타 `tll`, 숫자 키, 빈 키, `null` 값, `ttl`이 `"abc"`·`0`·`-1`·`true`·`NaN`·`Infinity`·아주 큰 정수·10년 초과. 모두 400이고, 저장되지 않음 |
| 본문 없는 `/set` | 400 |
| 비어 있거나 없는 쿼리 키 3가지 | `/get`, `/get?key=`, `/delete?key=` 모두 400 |
| `null` 말고는 모든 값 허용 7가지 | `"현지"`, `0`, `false`, `1.5`, `[1, null]`, `{"a": 1}`, `""`가 저장되고 그대로 조회됨 |
| 공백 키 허용 | `" "`가 저장되고 조회됨 |
| 소수 `ttl` 허용 | `1.5`가 저장됨 |
| 최댓값 `ttl` 허용 | 정확히 10년이 저장됨 |
| `"ttl": null` | 만료 없음으로 저장됨 |

| 시점 | 기대 결과 |
| --- | --- |
| 테스트만 추가하고 검증은 아직 없을 때 | `15 failed, 41 passed`. 잘못된 입력을 막지 못해 **14개 실패**하고, 아직 없는 `MAX_TTL`을 참조하는 테스트 1개가 `AttributeError`로 실패 |
| 검증을 추가한 뒤 | `56 passed` (5단계까지 27개 + 6단계 29개) |

`0`, `false`, `""`를 허용하는 테스트가 있는 이유: 검증을 `if not body["value"]:`처럼 쓰면 이 값들도 "거짓"이라 막혀 버립니다. 막아야 하는 것은 `None`뿐이므로 `is None`으로 검사해야 합니다.

### 2. 서버로 직접 확인

서버를 켜고(`python server.py`) 다른 터미널에서 실행합니다.

```bash
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "", "value": 1}'
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "a", "value": 1, "ttl": true}'
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "a", "value": 1, "ttl": NaN}'
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "a", "value": 1, "tll": 5}'
curl -i "http://127.0.0.1:8000/get?key="
```

| 명령 | 기대 결과 |
| --- | --- |
| 빈 키 | 400 `{"error": "key는 비어 있으면 안 됩니다"}` |
| `ttl`이 `true` | 400 `{"error": "ttl은 0보다 크고 315360000 이하인 숫자(초)여야 합니다"}` |
| `ttl`이 `NaN` | 400 (같은 문장) |
| 오타 `tll` | 400 `{"error": "알 수 없는 항목입니다: tll"}` |
| `/get?key=` | 400 `{"error": "key는 비어 있으면 안 됩니다"}` |

### 3. API 동작이 5단계와 같은지

[STEP1.md](./STEP1.md)의 완료 테스트 1~4와 [STEP4.md](./STEP4.md)의 완료 테스트 2~3을 다시 실행합니다. 결과가 같으면 됩니다.

1~3이 모두 맞으면 6단계 완료입니다.

## 알아 둘 것

- **검증은 "들어오는 문"에 둡니다.** 서버가 걸러 주므로 `Store`는 키가 문자열이라고 믿고 동작합니다. 대신 `Store`를 직접 부르는 파이썬 코드(8단계 데모 API, 테스트)는 올바른 값을 넣을 책임이 있습니다.
- **`null`과 "거짓 같은 값"은 다릅니다.** `0`, `false`, `""`, `[]`는 파이썬에서 거짓으로 취급되지만 모두 정상적인 값입니다. "없음"은 `None`뿐입니다.
- **`curl`의 `-d '...'` 안에 `NaN`을 써도 그대로 보내집니다.** 표준 JSON은 아니지만 파이썬 서버가 읽어 들이므로 검증에서 막아야 합니다.
- **1단계 문장은 그대로 둡니다.** "key가 필요합니다", "key와 value가 필요합니다"는 STEP1.md 완료 테스트의 기대 결과와 같게 유지합니다.

## 이해 확인 질문

코드를 보지 않고 한두 문장으로 답해 봅니다. 답은 눌러서 펼칠 수 있습니다.

<details>
<summary>1. 숫자 키를 보내면 원래 500이 났는데, 400으로 바꾸는 이유는 뭔가요?</summary>

상태 코드의 첫 자리는 누구의 잘못인지를 알립니다. 4xx는 보낸 쪽, 5xx는 서버의 잘못입니다. 500을 받은 개발자는 서버가 고장 났다고 생각해 다시 보내거나 문의하지만, 400과 이유를 받으면 바로 자기 코드를 고칩니다.
</details>

<details>
<summary>2. 5단계에서 lock은 <code>Store</code>에 넣었는데, 검증은 왜 서버에 두나요?</summary>

둘 다 "그 일을 알 수 있는 쪽이 맡는다"는 원칙입니다. lock이 지키는 칸과 만료 확인 동작은 저장소만 알고, 검증이 보는 요청의 모양(JSON, 불리언, 쿼리)은 HTTP를 받는 서버만 압니다. 400도 HTTP의 표현이라 서버가 정합니다.
</details>

<details>
<summary>3. <code>ttl</code>이 <code>true</code>이면 왜 숫자 검사를 통과하나요? 어떻게 막나요?</summary>

파이썬에서 `bool`은 `int`를 물려받은 종류라 `isinstance(True, int)`가 참이고, `True`는 1로 계산됩니다. 그래서 숫자인지 검사하기 전에 `isinstance(ttl, bool)`로 먼저 막습니다.
</details>

<details>
<summary>4. <code>ttl</code>이 <code>NaN</code>이면 어떤 일이 생기고, 어떻게 막나요?</summary>

`NaN`은 어떤 비교도 거짓이라 `ttl <= 0` 검사를 통과하고, 만료 확인 `지금 >= 만료 시점`도 늘 거짓이라 영원히 만료되지 않습니다. `0 < ttl <= MAX_TTL`처럼 "범위 안이어야 통과"로 쓰면 `NaN`은 이 비교가 거짓이라 걸립니다.
</details>

<details>
<summary>5. <code>math.isfinite()</code>를 쓰지 않고 최댓값을 둔 이유는 뭔가요?</summary>

아주 큰 정수를 `math.isfinite()`에 넣으면 소수로 바꾸다가 `OverflowError`가 나서, 검증 코드가 오히려 500을 냅니다. 최댓값을 두면 범위 비교 하나로 0 이하, `NaN`, `Infinity`, 아주 큰 정수를 모두 오류 없이 막을 수 있습니다.
</details>

<details>
<summary>6. 모르는 항목(<code>"tll"</code>)을 무시하지 않고 400으로 막는 이유는 뭔가요?</summary>

오타를 무시하면 보낸 쪽은 5초 뒤 사라질 줄 알았던 키가 만료 없이 영원히 남습니다. 잘못이 조용히 숨겨지므로, 바로 알려서 고치게 합니다.
</details>

<details>
<summary>7. 값으로 <code>0</code>이나 <code>false</code>는 왜 허용하고, 검사할 때 무엇을 조심해야 하나요?</summary>

막아야 하는 것은 "없음"을 뜻하는 `null`뿐이고, `0`과 `false`는 정상적인 값입니다. `if not value:`로 검사하면 이 값들도 거짓이라 막히므로, `if value is None:`으로 검사해야 합니다.
</details>

<details>
<summary>8. <code>/get?key=</code>에 404가 아니라 400을 주는 이유는 뭔가요?</summary>

404는 "그런 키는 지금 없다"는 뜻이지만, 빈 키는 `/set`에서 막히므로 애초에 만들 수 없는 키입니다. 그래서 "키가 없다"가 아니라 "요청이 잘못됐다"고 알려 줍니다.
</details>
