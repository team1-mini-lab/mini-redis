# 1단계: 뼈대

## 목표

API 3개와 임시 저장소를 만듭니다. API로 저장한 값이 조회되고, 삭제한 뒤에는 404가 나오면 완료입니다.

## 핵심 문제: 서버와 저장소의 경계

```
server.py  (HTTP를 아는 쪽)      요청 해석 → 저장소 함수 호출 → 응답 코드 결정
    │  store.set / store.get / store.delete
    ▼
store.py   (HTTP를 모르는 쪽)    값을 넣고, 꺼내고, 지움
```

- 서버는 저장소 안에 `dict`가 있다는 사실을 모릅니다. 함수 3개만 압니다.
- 저장소는 HTTP를 모릅니다. 404 같은 응답 코드를 만들지 않고 `None`, `True`, `False`만 돌려줍니다.
- 그래서 2단계에서 `dict`를 해시 테이블로 바꿀 때 `store.py`만 고치면 됩니다.

## 질문과 정리

| 질문 | 정리 |
| --- | --- |
| 왜 `dict`를 감싸서 쓰는가 | 바깥에서 `dict`를 직접 만지지 못하고 `set`, `get`, `delete`로만 접근하게 함. 그 결과 안쪽 구현을 바꿔도 바깥 코드가 그대로임 |
| 클래스인가, 모듈 함수인가 | 클래스. 서버가 쓰는 저장소는 하나뿐이지만, 테스트에서는 테스트마다 빈 저장소를 새로 만들어야 서로 영향을 주지 않음 |
| "없음"을 누가 어떻게 알리는가 | 저장소는 `None`을 돌려주고, 서버가 그것을 404로 바꿈. `None`이 항상 "없음"을 뜻해야 하므로 값으로 `None`은 저장할 수 없음 |
| 1단계의 입력 검증 범위 | 필수 항목이 빠진 요청만 400으로 처리. 나머지는 6단계 |

## 이 단계에서 정한 것

| 관련 코드 | 정한 것 | 이유 |
| --- | --- | --- |
| `server.py` 경로 3개 (`@app.post`, `@app.get`, `@app.delete`) | API 형식은 HTTP | 구현, 테스트, 시연이 쉬움 (DESIGN.md 제안과 같음) |
| `server.py` 맨 위 (`app.json.ensure_ascii`) | 응답의 한글은 `\uXXXX`로 바꾸지 않고 그대로 보냄 (`ensure_ascii = False`) | 브라우저와 `curl`에서 값을 바로 읽을 수 있음 |
| `server.py` `store = Store()` · `store.py` `Store` | 저장소는 클래스(`Store`)로 만들고, 서버는 `Store()`를 하나만 만들어 사용 | 테스트마다 빈 저장소를 새로 만들 수 있어 테스트끼리 영향을 주지 않음 |
| `server.py` `set_value`, `get_value`, `delete_value`의 첫 `if` | 1단계에서는 필수 항목이 빠진 요청만 400으로 처리 (`/set`의 `key`·`value`, `/get`·`/delete`의 `key`). 나머지 검증은 6단계 | 항목이 빠지면 서버가 500 오류를 내므로 최소한만 먼저 막음 |
| `server.py` 실패 응답 (`return {"error": ...}, 400` 등) | 실패 응답(400, 404)의 본문은 `{"error": "설명"}` | DESIGN.md에는 상태 코드만 정해져 있음. 원인을 사람이 읽을 수 있게 함 |
| `server.py` `get_value` · `store.py` `Store.get` | 없는 키를 조회하면 `get`은 `None`, API는 404 | "없음"을 값과 구분되는 방식으로 알림. 404는 HTTP의 표현이므로 저장소가 아니라 서버가 정함 (DESIGN.md 제안과 같음) |
| `server.py` `delete_value` · `store.py` `Store.delete` | 없는 키를 삭제하면 `delete`는 `False`, API는 200 `{"deleted": false}` | 삭제의 목적은 "값이 없는 상태"이므로 이미 없어도 실패가 아님. 실제로 지웠는지는 본문으로 알림 (DESIGN.md 제안과 같음) |
| `store.py` `Store.set` | 이미 있는 키에 `set`을 하면 값을 덮어씀 | 캐시 값을 갱신하는 기본 동작 (DESIGN.md 제안과 같음) |
| `store.py` `Store.set` | `set`의 `ttl` 인자는 4단계에서 추가 | 1단계에서 받기만 하고 무시하면 동작하는 것처럼 보여 혼란을 줌 |
| 아직 없음 (6단계에서 `server.py`에 추가) | 키는 비어 있지 않은 문자열, 값은 JSON으로 표현할 수 있는 값. 검증은 6단계 | API로 주고받을 수 있는 형태여야 함 (DESIGN.md 제안과 같음) |
| 아직 없음 (6단계에서 `server.py`에 추가) | 값으로 `None`(JSON의 `null`)은 저장할 수 없음. 검증은 6단계 | `get`이 돌려주는 `None`이 항상 "없음"을 뜻하게 하기 위함 (DESIGN.md 제안과 같음) |

[DECISIONS.md](./DECISIONS.md)에도 같은 내용이 모여 있습니다.

## 만드는 파일

| 파일 | 내용 |
| --- | --- |
| `store.py` (새로 만듦) | `Store` 클래스. `set`, `get`, `delete` |
| `server.py` (고침) | `Store()`를 하나 만들고, `/set`, `/get`, `/delete` 경로를 추가 |

## 완료 테스트

터미널 하나에서 서버를 켭니다.

```bash
source .venv/bin/activate
python server.py
```

다른 터미널에서 아래 명령을 순서대로 실행합니다.

### 1. 저장하고 조회하기

```bash
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "name", "value": "현지"}'
curl -i "http://127.0.0.1:8000/get?key=name"
```

| 명령 | 기대 결과 |
| --- | --- |
| `POST /set` | 200 `{"ok": true}` |
| `GET /get?key=name` | 200 `{"key": "name", "value": "현지"}` |

### 2. 덮어쓰기

```bash
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "name", "value": [1, 2, 3]}'
curl -i "http://127.0.0.1:8000/get?key=name"
```

| 명령 | 기대 결과 |
| --- | --- |
| `GET /get?key=name` | 200 `{"key": "name", "value": [1, 2, 3]}` (이전 값 "현지"가 사라짐) |

### 3. 삭제하고 다시 조회하기 (완료 기준)

```bash
curl -i -X DELETE "http://127.0.0.1:8000/delete?key=name"
curl -i "http://127.0.0.1:8000/get?key=name"
curl -i -X DELETE "http://127.0.0.1:8000/delete?key=name"
```

| 명령 | 기대 결과 |
| --- | --- |
| 첫 번째 `DELETE` | 200 `{"deleted": true}` |
| `GET /get?key=name` | **404** `{"error": "키가 없습니다"}` |
| 두 번째 `DELETE` | 200 `{"deleted": false}` (오류가 아님) |

### 4. 필수 항목이 빠진 요청

```bash
curl -i "http://127.0.0.1:8000/get"
curl -i -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"value": 1}'
```

| 명령 | 기대 결과 |
| --- | --- |
| `GET /get` (key 없음) | 400 `{"error": "key가 필요합니다"}` |
| `POST /set` (key 없음) | 400 `{"error": "key와 value가 필요합니다"}` |

1~4가 모두 맞으면 1단계 완료입니다.

## 실습할 때 알아 둘 것

- 값은 RAM에 있으므로 서버를 끄면 사라집니다. `debug=True`라서 코드를 저장할 때도 서버가 다시 시작되며 값이 사라집니다.
- 브라우저 주소창으로는 GET 요청만 보낼 수 있습니다. `/get`은 브라우저로 확인할 수 있지만, `/set`과 `/delete`는 `curl`로 보내야 합니다.
- `curl`의 `-i`는 응답 코드(200, 404 등)를 함께 보여 주는 옵션입니다.

## 6단계로 미룬 것

지금은 아래 요청이 걸러지지 않습니다. 6단계에서 400으로 처리합니다.

- 빈 문자열 키 (`"key": ""`), 문자열이 아닌 키 (`"key": 123`)
- 값이 `null`인 요청

## 이해 확인 질문

코드를 보지 않고 한두 문장으로 답해 봅니다. 답은 눌러서 펼칠 수 있습니다.

<details>
<summary>1. <code>server.py</code>와 <code>store.py</code>는 각각 무엇을 알고, 무엇을 모르나요?</summary>

`server.py`는 HTTP(경로, 요청 본문, 상태 코드)를 알고, 저장소 안이 `dict`인지는 모릅니다. 함수 3개만 압니다. `store.py`는 값을 담는 방법을 알고, HTTP는 모릅니다. 그래서 404 같은 상태 코드 대신 `None`, `True`, `False`를 돌려줍니다.
</details>

<details>
<summary>2. 2단계에서 <code>dict</code>를 해시 테이블로 바꿀 때 <code>server.py</code>를 고치지 않아도 되는 이유는 뭔가요?</summary>

서버는 `store.set`, `store.get`, `store.delete`만 부르고 `dict`를 직접 만지지 않기 때문입니다. 함수의 이름과 동작이 같으면 안쪽 구현이 바뀌어도 서버는 알 필요가 없습니다.
</details>

<details>
<summary>3. 없는 키를 조회하면 404인데, 없는 키를 삭제하면 왜 200인가요?</summary>

조회의 목적은 값을 받는 것이라 값이 없으면 요청을 해낼 수 없어 404입니다. 삭제의 목적은 "키가 없는 상태"라서 이미 없으면 목적을 이룬 것이므로 200입니다. 실제로 지웠는지는 본문의 `deleted`로 알립니다.
</details>

<details>
<summary>4. 값으로 <code>None</code>을 저장할 수 없게 한 이유는 뭔가요?</summary>

`get`이 `None`을 돌려줄 때 "키가 없음"인지 "값이 `None`"인지 구분할 수 없기 때문입니다. `None`을 저장하지 못하게 하면 `None`은 언제나 "없음"을 뜻합니다.
</details>

<details>
<summary>5. 서버가 쓰는 저장소는 하나뿐인데 <code>Store</code>를 왜 클래스로 만들었나요?</summary>

테스트에서 테스트마다 빈 저장소를 새로 만들기 위해서입니다. 전역 `dict` 하나를 쓰면 앞 테스트가 넣은 값이 다음 테스트에 남아 결과가 꼬입니다.
</details>
