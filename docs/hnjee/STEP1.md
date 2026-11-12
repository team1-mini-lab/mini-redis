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

## 지키는 결정 (DESIGN.md 4번, 1단계)

| 결정 | 코드에서 지키는 곳 |
| --- | --- |
| API 형식은 HTTP | `server.py`의 경로 3개 |
| 없는 키를 조회하면 `get`은 `None`, API는 404 | `Store.get`, `get_value`의 `if value is None` |
| 없는 키를 삭제하면 `delete`는 `False`, API는 200 `{"deleted": false}` | `Store.delete`, `delete_value` |
| 이미 있는 키에 `set`을 하면 값을 덮어씀 | `Store.set` |
| 키는 비어 있지 않은 문자열, 값은 JSON으로 표현할 수 있는 값 | 6단계에서 검증 |
| 값으로 `None`은 저장할 수 없음 | 6단계에서 검증 (지금은 `null`을 저장하면 조회할 때 404가 나옴) |

새로 정한 것은 [DECISIONS.md](./DECISIONS.md)의 1단계 줄에 있습니다.

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
