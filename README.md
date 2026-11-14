# mini-redis

해시 테이블을 직접 구현한 키-값 저장소와 HTTP API입니다. (hnjee 브랜치: 현지의 0~6단계 개인 구현)

## 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python server.py          # http://127.0.0.1:8000
```

```bash
curl -X POST http://127.0.0.1:8000/set -H "Content-Type: application/json" -d '{"key": "name", "value": "현지", "ttl": 5}'
curl "http://127.0.0.1:8000/get?key=name"        # 5초 안에는 200, 뒤에는 404
curl -X DELETE "http://127.0.0.1:8000/delete?key=name"
```

## 구조

```
server.py       HTTP를 아는 쪽. 요청 해석, 입력 검증(400), 응답 코드(404) 결정
    │ store.set(key, value, ttl) / store.get(key) / store.delete(key)
store.py        만료(지연 삭제)와 lock. 값 자리에 (값, 만료 시점)을 담음
    │
hash_table.py   순수한 자료구조. 직접 만든 해시 함수, 체이닝(칸마다 list), 적재율 0.75 넘으면 2배 확장
```

## 테스트

```bash
pytest -v    # 56 passed
```

`tests/test_hash_table.py`(자료구조), `tests/test_store.py`(만료·동시성, 가짜 시계 사용), `tests/test_server.py`(입력 검증).

## 문서

- [docs/hnjee/DECISIONS.md](docs/hnjee/DECISIONS.md): 단계마다 무엇을 왜 정했는지 (코드 위치와 함께)
- [docs/hnjee/STEP0.md](docs/hnjee/STEP0.md) ~ [STEP6.md](docs/hnjee/STEP6.md): 단계별 핵심 문제, 질의응답, 완료 테스트
- [docs/DESIGN.md](docs/DESIGN.md): 팀 설계 문서
