# eungi의 미니 레디스 기록

목요일 개인 구현(0~6단계)을 하면서 고민한 것, 정한 것, 구현한 것을 남기는 폴더입니다.
팀 설계는 [DESIGN.md](../DESIGN.md)를 따르고, 여기에는 개인 기록만 둡니다.

## 문서

| 문서 | 내용 | 상태 |
| --- | --- | --- |
| [STEP0.md](./STEP0.md) | 0단계: 준비 (Flask, venv, 포트) | 완료 |
| [STEP1.md](./STEP1.md) | 1단계: 뼈대 (API 3개 + dict를 감싼 임시 저장소) | 완료 |
| [STEP2.md](./STEP2.md) | 2단계: 해시 테이블과 체이닝 | 완료 |
| [STEP3.md](./STEP3.md) | 3단계: 칸 수 확장 (부하율 0.75, 2배, 재해싱) | 완료 |
| [DECISIONS.md](./DECISIONS.md) | 개인 결정 기록 (확정 / 미결정) | 계속 갱신 |
| [NOTES.md](./NOTES.md) | 공부하며 알게 된 것 (HTTP API, 만료와 무효화, 동시성, 증가 명령) | 계속 갱신 |
| [REDIS_STUDY.md](./REDIS_STUDY.md) | 레디스 공부 노트 (헷갈렸던 질문, 실제 레디스와 비교, redis-cli 실습) | 계속 갱신 |

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

## 진행 상황

| 단계 | 상태 |
| --- | --- |
| 0. 준비 | 완료 |
| 1. 뼈대 | 완료 (필수 항목 누락 시 400은 6단계로 미룸) |
| 2. 해시 테이블 | 완료 (연결 리스트 체이닝, 새 노드는 맨 앞) |
| 3. 칸 수 확장 | 완료 (부하율 0.75 초과 시 2배, 키 100개 테스트 통과) |
| 4~6단계 | 시작 전 |
