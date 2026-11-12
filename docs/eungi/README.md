# eungi의 미니 레디스 기록

목요일 개인 구현(0~6단계)을 하면서 고민한 것, 정한 것, 구현한 것을 남기는 폴더입니다.
팀 설계는 [DESIGN.md](../DESIGN.md)를 따르고, 여기에는 개인 기록만 둡니다.

## 문서

| 문서 | 내용 | 상태 |
| --- | --- | --- |
| [STEP0.md](./STEP0.md) | 0단계: 준비 (Flask, venv, 포트) | 완료 |
| [STEP1.md](./STEP1.md) | 1단계: 뼈대 (API 3개 + dict를 감싼 임시 저장소) | 완료 |
| [STEP2.md](./STEP2.md) | 2단계: 해시 테이블과 체이닝 | 진행 중 (테스트만 작성) |
| [DECISIONS.md](./DECISIONS.md) | 개인 결정 기록 (확정 / 미결정) | 계속 갱신 |
| [NOTES.md](./NOTES.md) | 공부하며 알게 된 것 (HTTP API, 만료와 무효화, 동시성, 증가 명령) | 계속 갱신 |

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

## 진행 상황

| 단계 | 상태 |
| --- | --- |
| 0. 준비 | 완료 |
| 1. 뼈대 | 완료 (필수 항목 누락 시 400은 6단계로 미룸) |
| 2. 해시 테이블 | 진행 중: `tests/test_store.py` 작성, `store.py`는 아직 dict 버전이라 테스트 3개 실패 (Red) |
| 3~6단계 | 시작 전 |
