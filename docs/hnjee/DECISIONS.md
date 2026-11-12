# 개인 결정 기록 (현지)

각 단계에서 정한 것을 모읍니다. 각 단계 문서(STEPn.md)의 "이 단계에서 정한 것"과 같은 내용입니다. DESIGN.md의 결정 기록은 제안이므로, 따르기로 한 것도 여기에 적고 이유 칸에 "(DESIGN.md 제안과 같음)"을 붙입니다. 팀 설계 문서([DESIGN.md](../DESIGN.md))의 결정 기록에는 합의된 내용만 들어가므로, 이 기록을 팀 회의에 가져가 팀 합의가 필요한 것만 논의한 뒤 DESIGN.md에 옮깁니다.

- 단계 번호는 DESIGN.md 3번의 개발 단계와 같습니다.
- 각 단계 안에서는 관련 코드의 순서(`server.py` → `store.py` → `hash_table.py` → 테스트·환경)로 정렬합니다.
- 결정을 바꿀 때는 그 줄을 고치고, 이유 칸에 "(변경: 이전에는 ...)"을 덧붙입니다.

| 단계 | 관련 코드 | 결정 | 이유 |
| --- | --- | --- | --- |
| 0 | `server.py` 맨 위 (`Flask(__name__)`) | 서버 도구는 Flask | 코드가 짧고, 6단계의 400 응답을 직접 작성하기 쉬움 |
| 0 | `server.py` 파일 구성 | 0단계는 `server.py` 하나로 시작하고, `store.py`는 1단계에서 추가 | 저장소가 아직 없으므로 빈 파일을 미리 만들 이유가 없음 |
| 0 | `server.py` 맨 아래 (`app.run`) | 서버 포트는 8000 | macOS에서는 Flask 기본 포트 5000을 AirPlay 수신 기능이 사용해 충돌할 수 있음 |
| 0 | 개발 환경 (`.venv/`, `requirements.txt`) | 패키지는 프로젝트 폴더 안의 가상환경(`.venv`)에 설치하고 `requirements.txt`에 기록 | 시스템 파이썬을 건드리지 않고, 같은 환경을 다시 만들 수 있음 |
| 1 | `server.py` 경로 3개 (`@app.post`, `@app.get`, `@app.delete`) | API 형식은 HTTP | 구현, 테스트, 시연이 쉬움 (DESIGN.md 제안과 같음) |
| 1 | `server.py` 맨 위 (`app.json.ensure_ascii`) | 응답의 한글은 `\uXXXX`로 바꾸지 않고 그대로 보냄 (`ensure_ascii = False`) | 브라우저와 `curl`에서 값을 바로 읽을 수 있음 |
| 1 | `server.py` `store = Store()` · `store.py` `Store` | 저장소는 클래스(`Store`)로 만들고, 서버는 `Store()`를 하나만 만들어 사용 | 테스트마다 빈 저장소를 새로 만들 수 있어 테스트끼리 영향을 주지 않음 |
| 1 | `server.py` `set_value`, `get_value`, `delete_value`의 첫 `if` | 1단계에서는 필수 항목이 빠진 요청만 400으로 처리 (`/set`의 `key`·`value`, `/get`·`/delete`의 `key`). 나머지 검증은 6단계 | 항목이 빠지면 서버가 500 오류를 내므로 최소한만 먼저 막음 |
| 1 | `server.py` 실패 응답 (`return {"error": ...}, 400` 등) | 실패 응답(400, 404)의 본문은 `{"error": "설명"}` | DESIGN.md에는 상태 코드만 정해져 있음. 원인을 사람이 읽을 수 있게 함 |
| 1 | `server.py` `get_value` · `store.py` `Store.get` | 없는 키를 조회하면 `get`은 `None`, API는 404 | "없음"을 값과 구분되는 방식으로 알림. 404는 HTTP의 표현이므로 저장소가 아니라 서버가 정함 (DESIGN.md 제안과 같음) |
| 1 | `server.py` `delete_value` · `store.py` `Store.delete` | 없는 키를 삭제하면 `delete`는 `False`, API는 200 `{"deleted": false}` | 삭제의 목적은 "값이 없는 상태"이므로 이미 없어도 실패가 아님. 실제로 지웠는지는 본문으로 알림 (DESIGN.md 제안과 같음) |
| 1 | `store.py` `Store.set` | 이미 있는 키에 `set`을 하면 값을 덮어씀 | 캐시 값을 갱신하는 기본 동작 (DESIGN.md 제안과 같음) |
| 1 | `store.py` `Store.set` | `set`의 `ttl` 인자는 4단계에서 추가 | 1단계에서 받기만 하고 무시하면 동작하는 것처럼 보여 혼란을 줌 |
| 1 | 아직 없음 (6단계에서 `server.py`에 추가) | 키는 비어 있지 않은 문자열, 값은 JSON으로 표현할 수 있는 값. 검증은 6단계 | API로 주고받을 수 있는 형태여야 함 (DESIGN.md 제안과 같음) |
| 1 | 아직 없음 (6단계에서 `server.py`에 추가) | 값으로 `None`(JSON의 `null`)은 저장할 수 없음. 검증은 6단계 | `get`이 돌려주는 `None`이 항상 "없음"을 뜻하게 하기 위함 (DESIGN.md 제안과 같음) |
| 2 | `store.py` `Store.__init__` · `hash_table.py` 전체 | 해시 테이블은 `hash_table.py`의 `HashTable`로 분리하고, `Store`는 그것을 감쌈 | 해시 테이블은 순수한 자료구조로 두고, 4단계의 만료와 5단계의 lock은 `Store`에서 처리 |
| 2 | `hash_table.py` `__init__` (`capacity=8`) | 처음 칸 수는 8 | 충돌이 자주 일어나 체이닝을 눈으로 확인하기 쉬움 |
| 2 | `hash_table.py` `__init__` (`_buckets`) · `set`, `get`, `delete` | 충돌 처리는 체이닝 | 구현과 설명이 단순하고 널리 쓰이는 방식. 실제 레디스도 체이닝을 씀 (DESIGN.md 제안과 같음) |
| 2 | `hash_table.py` `_hash` | 해시 함수는 직접 구현 (`h = h * 31 + 문자 코드`를 32비트 안으로 자름) | 파이썬 `hash()`는 실행할 때마다 값이 달라져서 어떤 키끼리 충돌하는지 재현할 수 없음. 해시 테이블 전체를 직접 설명할 수 있음 |
| 2 | `hash_table.py` `set` (`bucket[i] = (key, value)`, `bucket.append(...)`) | 칸의 항목은 `(키, 값)` 튜플. 덮어쓸 때는 튜플을 새로 바꿔 넣음 | 같은 칸의 항목 중 키가 일치하는 것을 찾아야 하므로 키와 값을 함께 저장 (DESIGN.md 제안과 같음) |
| 2 | `hash_table.py` `dump` | 칸 상태를 보는 `dump()`를 둠 | 완료 기준 "같은 칸에 여러 키가 이어진 것이 출력으로 확인됨"을 확인하기 위함 |
| 2 | `tests/` · `pytest.ini` · `requirements.txt` | 단위 테스트 도구는 pytest, 테스트는 `tests/` 폴더 | `assert` 한 줄로 쓸 수 있어 읽기 쉬움 |
