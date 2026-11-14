# eungi의 미니 레디스 기록

개인 구현(0~6단계)을 하면서 고민한 것, 정한 것, 구현한 것을 남기는 폴더입니다.
팀 설계는 [DESIGN.md](../DESIGN.md)를 따르고, 여기에는 개인 기록만 둡니다.

## 문서

| 문서 | 내용 | 상태 |
| --- | --- | --- |
| [STEP0.md](./STEP0.md) | 0단계: 준비 (Flask, venv, 포트) | 완료 |
| [STEP1.md](./STEP1.md) | 1단계: 뼈대 (API 3개 + dict를 감싼 임시 저장소) | 완료 |
| [STEP2.md](./STEP2.md) | 2단계: 해시 테이블과 체이닝 | 완료 |
| [STEP3.md](./STEP3.md) | 3단계: 칸 수 확장 (부하율 0.75, 2배, 재해싱) | 완료 |
| [STEP4.md](./STEP4.md) | 4단계: 만료 (`expire_at` 저장, 조회할 때 확인하는 지연 삭제) | 완료 |
| [STEP5.md](./STEP5.md) | 5단계: lock (`Store`가 `HashTable`을 lock 하나로 감쌈) | 완료 |
| [STEP6.md](./STEP6.md) | 6단계: 입력 검증 (빈 키, null 값, 잘못된 `ttl`에 400) | 완료 |
| [DECISIONS.md](./DECISIONS.md) | 개인 결정 기록 (확정 / 미결정) | 계속 갱신 |

팀 공유용 "왜 레디스인가" 설명은 [docs/study/WHY_REDIS.md](../study/WHY_REDIS.md)에 있습니다.

## 실행 방법

모든 명령은 저장소 최상위 폴더(`mini-redis/`)에서 실행합니다.

```bash
source .venv/bin/activate
pip install -r requirements.txt
flask --app mini_redis.server run --port 5001 --debug
```

테스트:

```bash
python -m pytest -v
```

## 코드 구조

```
HTTP 요청
   ▼
mini_redis/server.py      요청 해석 → 입력 검증(6단계) → Store 호출 → JSON 응답
   ▼
mini_redis/store.py       Store: lock 하나로 set/get/delete를 감쌈 (5단계)
   ▼
mini_redis/hash_table.py  HashTable: 직접 만든 해시 함수, 연결 리스트 체이닝,
                          칸 수 확장(3단계), 만료 확인과 지연 삭제(4단계)
```

각 층은 아래 층만 알고, 위 층은 모릅니다. `HashTable`은 lock을 모르고, `Store`는 HTTP를 모릅니다.

| 테스트 파일 | 확인하는 것 |
| --- | --- |
| `tests/test_hash_table.py` | 저장·조회·삭제, 체이닝, 칸 수 확장, 만료(`test_expire`), 덮어쓰면 만료 초기화(`test_overwrite_resets_ttl`) |
| `tests/test_store.py` | 8개 스레드가 500번씩 동시에 저장·조회해도 오류 없음(`test_concurrent_set_get`) |
| `tests/test_api.py` | 잘못된 입력에 400(`test_bad_inputs`), 정상 흐름(`test_good_flow`) |

## 진행 상황

| 단계 | 상태 |
| --- | --- |
| 0. 준비 | 완료 |
| 1. 뼈대 | 완료 (1단계에서 미뤘던 "필수 항목 누락 시 400"은 6단계에서 처리) |
| 2. 해시 테이블 | 완료 (연결 리스트 체이닝, 새 노드는 맨 앞) |
| 3. 칸 수 확장 | 완료 (부하율 0.75 초과 시 2배, 키 100개 테스트 통과) |
| 4. 만료 | 완료 (만료 "시각"을 저장, `get`·`delete`에서 지연 삭제, `ttl` 없이 덮어쓰면 만료 없어짐) |
| 5. lock | 완료 (lock은 `Store`에 둠. 지연 삭제 때문에 `get`도 쓰기라서 조회에도 lock) |
| 6. 입력 검증 | 완료 (검증은 `server.py`에서. `ttl`은 `bool`을 먼저 걸러냄, 없는 주소·메서드도 JSON 오류로 응답) |

전체 테스트 7개 통과. 0~6단계 개인 구현을 마쳤고, 다음은 7단계(비교와 선택)입니다.
