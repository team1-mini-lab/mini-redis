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
| 1 | `server.py` `set_value`, `get_value`, `delete_value`의 첫 `if` (6단계에서 검증 함수 호출로 바뀜) | 1단계에서는 필수 항목이 빠진 요청만 400으로 처리 (`/set`의 `key`·`value`, `/get`·`/delete`의 `key`). 나머지 검증은 6단계 | 항목이 빠지면 서버가 500 오류를 내므로 최소한만 먼저 막음 |
| 1 | `server.py` 실패 응답 (`return {"error": ...}, 400` 등) | 실패 응답(400, 404)의 본문은 `{"error": "설명"}` | DESIGN.md에는 상태 코드만 정해져 있음. 원인을 사람이 읽을 수 있게 함 |
| 1 | `server.py` `get_value` · `store.py` `Store.get` | 없는 키를 조회하면 `get`은 `None`, API는 404 | "없음"을 값과 구분되는 방식으로 알림. 404는 HTTP의 표현이므로 저장소가 아니라 서버가 정함 (DESIGN.md 제안과 같음) |
| 1 | `server.py` `delete_value` · `store.py` `Store.delete` | 없는 키를 삭제하면 `delete`는 `False`, API는 200 `{"deleted": false}` | 삭제의 목적은 "값이 없는 상태"이므로 이미 없어도 실패가 아님. 실제로 지웠는지는 본문으로 알림 (DESIGN.md 제안과 같음) |
| 1 | `store.py` `Store.set` | 이미 있는 키에 `set`을 하면 값을 덮어씀 | 캐시 값을 갱신하는 기본 동작 (DESIGN.md 제안과 같음) |
| 1 | `store.py` `Store.set` | `set`의 `ttl` 인자는 4단계에서 추가 | 1단계에서 받기만 하고 무시하면 동작하는 것처럼 보여 혼란을 줌 |
| 1 | `server.py` `check_key`, `check_set_body` (6단계) | 키는 비어 있지 않은 문자열, 값은 JSON으로 표현할 수 있는 값. 검증은 6단계 | API로 주고받을 수 있는 형태여야 함 (DESIGN.md 제안과 같음) |
| 1 | `server.py` `check_set_body` (6단계) | 값으로 `None`(JSON의 `null`)은 저장할 수 없음. 검증은 6단계 | `get`이 돌려주는 `None`이 항상 "없음"을 뜻하게 하기 위함 (DESIGN.md 제안과 같음) |
| 2 | `store.py` `Store.__init__` · `hash_table.py` 전체 | 해시 테이블은 `hash_table.py`의 `HashTable`로 분리하고, `Store`는 그것을 감쌈 | 해시 테이블은 순수한 자료구조로 두고, 4단계의 만료와 5단계의 lock은 `Store`에서 처리 |
| 2 | `hash_table.py` `__init__` (`capacity=8`) | 처음 칸 수는 8 | 충돌이 자주 일어나 체이닝을 눈으로 확인하기 쉬움 |
| 2 | `hash_table.py` `__init__` (`_buckets`) · `set`, `get`, `delete` | 충돌 처리는 체이닝 | 구현과 설명이 단순하고 널리 쓰이는 방식. 실제 레디스도 체이닝을 씀 (DESIGN.md 제안과 같음) |
| 2 | `hash_table.py` `__init__` (`_buckets = [[] ...]`) · `set`, `get`, `delete` | 칸의 체인은 파이썬 `list`로 만들고, `Node` 클래스로 연결 리스트를 직접 만들지 않음 | 체이닝의 핵심은 "칸 찾기 → 그 칸의 항목을 키로 비교"이고, 체인을 무엇에 담든 이 알고리즘은 같음. 파이썬 `list`는 C로 구현된 동적 배열이라 짧은 체인을 훑는 데 빠르고, 삭제가 `pop(i)` 한 줄이라 첫 노드를 따로 처리할 필요가 없어 코드가 짧음. 연결 리스트 버전을 만들어 키 10만 개로 재 보니 조회·삭제 속도는 같았고, 저장은 약 20% 느리고 메모리는 2.7배(28MB 대 10.5MB)였음. 원인은 빈 칸마다 빈 리스트 객체(56바이트)를 두는 것과 확장 때 튜플을 새로 만든 것(3단계에서 고침)이며, 체이닝 알고리즘의 차이가 아님. 연결 리스트는 노드가 다음 노드를 가리키는 구조가 코드에 드러나 교과서와 레디스 `dict.c`와 같은 모양이라 설명에는 유리함. 이 트레이드오프를 알고 코드 길이를 택함 |
| 2 | `hash_table.py` `_hash` | 해시 함수는 직접 구현 (`h = h * 31 + 문자 코드`를 32비트 안으로 자름) | 파이썬 `hash()`는 실행할 때마다 값이 달라져서 어떤 키끼리 충돌하는지 재현할 수 없음. 해시 테이블 전체를 직접 설명할 수 있음 |
| 2 | `hash_table.py` `set` (`bucket[i] = (key, value)`, `bucket.append(...)`) | 칸의 항목은 `(키, 값)` 튜플. 덮어쓸 때는 튜플을 새로 바꿔 넣음 | 같은 칸의 항목 중 키가 일치하는 것을 찾아야 하므로 키와 값을 함께 저장 (DESIGN.md 제안과 같음) |
| 2 | `hash_table.py` `dump` | 칸 상태를 보는 `dump()`를 둠 | 완료 기준 "같은 칸에 여러 키가 이어진 것이 출력으로 확인됨"을 확인하기 위함 |
| 2 | `tests/` · `pytest.ini` · `requirements.txt` | 단위 테스트 도구는 pytest, 테스트는 `tests/` 폴더 | `assert` 한 줄로 쓸 수 있어 읽기 쉬움 |
| 3 | `hash_table.py` 맨 위 (`MAX_LOAD_FACTOR = 0.75`) | 적재율(키 수 ÷ 칸 수)이 0.75를 넘으면 칸을 늘림 | 속도(짧은 리스트)와 메모리(빈 칸) 사이에서 고른 중간 값. 자바 `HashMap`과 같고, 레디스는 1.0. DESIGN.md는 각자 정하도록 함 |
| 3 | `hash_table.py` 맨 위 (`GROWTH_FACTOR = 2`) | 늘릴 때는 칸 수를 2배로 | 더하기가 아닌 곱하기로 늘려야 확장이 점점 드물어짐 (키 100개에 191번 옮김. 1칸씩이면 5,029번). 레디스, 자바 `HashMap`과 같은 값. DESIGN.md는 각자 정하도록 함 |
| 3 | `hash_table.py` `set` | 확장 여부는 **새 키를 추가한 직후**에만 확인. 덮어쓰기에서는 확인하지 않음 | 키 수가 늘 때만 적재율이 올라감 |
| 3 | `hash_table.py` `set` | 한 칸의 리스트 길이는 확장 기준으로 쓰지 않음 | 칸이 작아서 생기는 충돌은 적재율 규칙이 미리 막음. 그래도 길어진 리스트는 해시 함수가 원인이라, 칸을 늘려도 풀리지 않고 칸 수만 끝없이 늘어날 수 있음 |
| 3 | `hash_table.py` `_resize` | 재배치는 한 번에 전부 옮김 | 가장 단순함. 점진적 재해싱은 시간이 남으면 차별화 요소(R12)로 검토 |
| 3 | `hash_table.py` `_resize` | 재배치할 때 해시 값을 다시 계산함 (항목에 해시 값을 저장해 두지 않음) | 항목을 `(키, 값)` 그대로 유지해 단순하게 둠. 튜플은 새로 만들지 않고 그대로 옮김 (변경: 이전에는 `for key, value in bucket`으로 풀었다가 `(key, value)`로 다시 묶어 넣었음. 키 10만 개 저장이 약 6% 빨라짐) |
| 3 | `hash_table.py` `delete` | 키를 지워도 칸 수는 줄이지 않음 | 과제 요구에 없고, 캐시는 지운 만큼 다시 채워지는 경우가 많음 |
| 3 | `hash_table.py` `capacity` | 현재 칸 수를 알려 주는 `capacity`를 둠 | 완료 기준 "칸 수가 늘어남"을 확인하기 위함 |
| 3 | `tests/test_hash_table.py` | 3단계 테스트를 같은 파일에 추가 | 해시 테이블의 약속을 한 파일에서 볼 수 있음 |
| 4 | `server.py` `set_value` (`body.get("ttl")`) | `/set` 본문의 `ttl`은 선택 항목. 있으면 그대로 `store.set`에 넘김 | DESIGN.md 접점 2의 요청 형식과 같음. 검증은 6단계 |
| 4 | `store.py` `Store.set` | 항목에 만료 "시점"(`지금 + ttl`)을 저장 | 기간만으로는 언제부터인지 알 수 없음. 조회할 때 현재 시각과 비교만 하면 됨 (DESIGN.md 제안과 같음) |
| 4 | `store.py` `Store.set` | 값 자리에 `(값, 만료 시점)` 튜플을 넣고, `HashTable`은 고치지 않음 | 해시 테이블은 값을 그대로 넣고 돌려주므로 만료를 몰라도 됨. 2단계에서 정한 "만료는 `Store`에서 처리"를 따름 |
| 4 | `store.py` `Store.set` | `ttl`을 생략하면 만료 시점은 `None` | "만료 없음"이 코드에 드러남. `float("inf")`는 표준 JSON에 없어 14단계 파일 저장과 맞지 않음 |
| 4 | `store.py` `Store.set` | 덮어쓰면 만료 시점도 새로 정함. `ttl`을 생략하면 만료가 없어짐 | 이전 값의 만료 시점이 새 값에 남으면 예상하지 못한 삭제가 생김. 실제 레디스 `SET`의 기본 동작과 같음 (DESIGN.md 제안과 같음) |
| 4 | `store.py` `Store.__init__` (`clock`) | 현재 시각은 `time.monotonic()` | 시계 설정이 바뀌어도 흐른 시간만 정확히 셈. 기준점이 재부팅마다 바뀌므로 14단계를 하면 저장 방식을 따로 정해야 함 |
| 4 | `store.py` `Store.__init__` (`clock`) | 시계를 인자로 받을 수 있게 함 (기본값 `time.monotonic`) | 테스트에서 가짜 시계를 넣어 5초를 기다리지 않고 만료를 확인하기 위함 |
| 4 | `store.py` `Store.get` | 만료 확인은 지연 삭제. `get`이 만료를 발견하면 그 자리에서 지우고 `None` | 과제 요구(R5)를 정확히 만족하고 비용이 작음. 지우지 않으면 메모리와 적재율이 부풂. 주기적 정리는 13단계 (DESIGN.md 제안과 같음) |
| 4 | `store.py` `Store.get` · `Store.delete` | 만료된 키는 없는 키와 똑같이 취급 (`get`은 `None`, `delete`는 `False`, API는 404). `delete`는 남아 있던 항목을 지우고 `False` | 사용하는 쪽에서는 이미 없는 키. `get`을 먼저 불렀는지에 따라 결과가 달라지지 않음 (DESIGN.md 제안과 같음) |
| 4 | `store.py` `_is_expired` | `지금 >= 만료 시점`이면 만료 | `ttl=5`는 "5초 동안 보관"이므로 정확히 5초가 되는 순간 기간이 끝남 |
| 4 | `tests/test_store.py` | 4단계 테스트는 `test_store.py`에 추가 | 만료는 `HashTable`이 아니라 `Store`의 일 |
| 4 | `server.py` `check_ttl` (6단계) | `ttl`의 단위는 초이고 0보다 큰 숫자. 검증은 6단계 | 단위를 하나로 통일. 0 이하는 저장 즉시 만료되어 의미가 없음 (DESIGN.md 제안과 같음) |
| 5 | `server.py` 맨 아래 (`app.run`) | 서버는 요청마다 스레드를 쓰는 Flask 기본 방식을 유지. 스레드 하나로 바꾸지 않음 | 느린 요청이 다른 요청을 막지 않음. 저장소의 안전은 서버 구조가 아니라 `Store`의 lock이 보장 |
| 5 | `store.py` `Store.__init__` (`_lock`) | lock은 `Store` 안에서 처리하고, 서버는 lock을 모름 | 저장소를 사용하는 쪽에서 lock을 빠뜨릴 수 없게 함. 만료 확인처럼 여러 단계로 된 동작을 아는 쪽이 `Store` (DESIGN.md 제안과 같음) |
| 5 | `store.py` `Store.__init__` (`_lock`) | 저장소 전체에 lock 하나. 칸마다 lock을 두지 않음 | resize 때 모든 칸을 잠가야 하고, 칸 수가 바뀌면 lock도 다시 만들어야 함. GIL 때문에 얻는 것도 적음. 명령을 하나씩 실행하는 레디스와 같은 보장 (DESIGN.md 제안과 같음) |
| 5 | `store.py` `Store.__init__` (`_lock`) | `threading.Lock` 사용 (`RLock` 아님) | lock을 쥔 채로 lock을 거는 `Store` 함수를 다시 부르는 곳이 없음 |
| 5 | `store.py` `Store.set`, `get`, `delete` | 세 함수의 전체를 `with self._lock:`으로 감쌈. 읽기인 `get`도 포함 | 읽기도 고치는 중간 상태를 볼 수 있음. `get`의 꺼내기 → 만료 확인 → 지우기 사이에 끼어들면 새 값이 지워짐 |
| 5 | `hash_table.py` | `HashTable`에는 lock을 걸지 않음 | 순수한 자료구조로 둠(2단계 결정). `Store`의 lock 안에서만 불려 안쪽 lock은 아무도 막지 않음 |
| 5 | `tests/test_store.py` | 동시성 테스트는 `test_store.py`에 추가하고, 테스트 동안 `sys.setswitchinterval(1e-6)`으로 스레드를 자주 교대시킴 | 기본 설정에서는 lock 없이도 20번 모두 통과해 lock의 효과를 확인할 수 없음. 자주 교대하면 lock 없이 20번 모두 깨짐 |
| 5 | `tests/test_store.py` (완료 테스트 순서) | lock 없는 코드로 동시성 테스트가 깨지는 것을 먼저 본 뒤 lock을 추가 | "lock 덕분에 통과했다"고 말할 수 있음 |
| 6 | `server.py` `check_set_body`, `check_key`, `check_ttl` | 입력 검증은 `server.py`의 검증 함수에서 함. 잘못되면 오류 설명, 괜찮으면 `None`을 돌려주고, 경로 함수가 400으로 응답. 저장소에는 올바른 입력만 전달 | 검증을 한 곳에 모아 저장소를 단순하게 유지. 요청의 모양은 HTTP를 받는 쪽만 앎 (DESIGN.md 제안과 같음) |
| 6 | `server.py` 경로 함수의 실패 응답 | 클라이언트의 잘못된 입력에는 500이 아니라 400 | 4xx는 "보낸 쪽이 고쳐야 함"을 알림. 500이면 보낸 쪽이 서버 고장으로 오해함 |
| 6 | `server.py` `check_set_body` | 잘못된 곳이 여러 개면 처음 발견한 하나만 `{"error": "설명"}`으로 알림 | 1단계의 실패 응답 형식 그대로. 하나씩 고치면 됨 |
| 6 | `server.py` `check_set_body` (`SET_FIELDS`) | `/set` 본문에 `key`, `value`, `ttl` 말고 다른 항목이 있으면 400 | 오타 `"tll"`이 무시되면, 곧 사라질 줄 안 키가 영원히 남음 |
| 6 | `server.py` `check_set_body` | `/set` 본문이 JSON 객체가 아니면 "요청 본문은 JSON 객체여야 합니다" | 1단계에서는 "key와 value가 필요합니다"로 함께 처리했지만, 원인을 정확히 알려 줌 |
| 6 | `server.py` `check_key` | 키는 비어 있지 않은 문자열. 공백뿐인 키(`" "`)는 허용 | 1단계에서 정한 규칙. 실제 레디스도 키 내용을 따지지 않음 (DESIGN.md 제안과 같음) |
| 6 | `server.py` `get_value`, `delete_value` (`check_key`) | 쿼리의 키가 비어 있으면(`?key=`) 400 | `/set`과 같은 규칙. 404("없음")가 아니라 "애초에 만들 수 없는 키"라고 알려 줌 |
| 6 | `server.py` `check_set_body` | 값은 `null`만 막고 나머지 JSON 값은 모두 허용. 리스트 안의 `null`도 허용 | `get`이 돌려주는 `None`이 언제나 "없음"이면 됨. 리스트는 `None`이 아님 (DESIGN.md 제안과 같음) |
| 6 | `server.py` `check_ttl` | `ttl`은 숫자(`int`, `float`)이고 `bool`은 막음 | 파이썬의 `bool`은 `int`의 한 종류라, 막지 않으면 `true`가 1초로 저장됨 |
| 6 | `server.py` `check_ttl` | `ttl`은 소수도 허용 (`1.5`초) | 시계가 소수 단위라 그대로 동작함 |
| 6 | `server.py` `check_ttl` (`MAX_TTL`) | `ttl`의 범위는 `0 < ttl <= 10년`(315,360,000초). 이 비교 하나로 0 이하, `NaN`, `Infinity`, 아주 큰 정수를 모두 막음 | `math.isfinite()`는 아주 큰 정수에서 `OverflowError`를 내 500이 됨. `NaN`은 비교가 모두 거짓이라 범위 밖으로 걸림. 10년 넘는 보관은 `ttl`을 생략하면 됨 (DESIGN.md의 "0보다 큰 숫자" 제안에 최댓값을 더함) |
| 6 | `server.py` `check_ttl` | `"ttl": null`은 생략과 같이 만료 없음 | JSON의 `null`은 "없음"이라는 뜻 |
| 6 | `tests/test_server.py` | 검증 테스트는 `tests/test_server.py`를 새로 만들어 Flask 테스트 클라이언트로 확인. 테스트마다 `server.store`를 빈 `Store()`로 바꿔 끼움 | 서버를 띄우지 않고 API를 확인할 수 있음. 테스트끼리 영향을 주지 않음. 다른 API 기능 테스트는 10단계 |
