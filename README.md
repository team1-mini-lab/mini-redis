# mini-redis

직접 구현한 해시 테이블 자료구조의 키-값 저장소를 HTTP 서버로 띄우고, 웹 서버 여러 대가 함께 하나의 캐시를 쓰는 것을 구현했습니다.

## 목차

1. [redis는 왜 만들어졌나?](#1-redis는-왜-만들어졌나)
2. [실행 방법](#2-실행-방법)

## 1. redis는 왜 만들어졌나?

서버가 한 대라면 캐시는 서버 메모리의 `dict` 하나로 충분합니다. 사용자가 늘어 서버가 여러 대가 되면, 서버마다 따로 들고 있는 캐시 때문에 문제가 생깁니다.

| 장면 | 로컬 캐시 (서버마다 따로) | mini-redis (서버 밖 한 곳) |
| --- | --- | --- |
| ① 가격이 왔다 갔다 | 서버 A에서 시세를 바꿔도 서버 B는 옛 가격 50,000원 | A, B 모두 40,000원 |
| ② 로그인이 풀림 | A에서 로그인했는데 B는 모름 (401) | B도 알아봄 |
| ③ 배포하면 DB가 몰림 | 서버를 재시작하면 캐시가 사라져 DB로 감 | 캐시가 서버 밖에 있어 그대로 |
| ④ 같은 데이터를 서버 수만큼 저장 | 서버마다 DB를 따로 조회 (DB 4번) | 한 번 채우면 모두 씀 (DB 2번) |
| ⑤ 함께 세야 하는 값이 틀림 | 재고 1개가 두 번 팔림 | 아직 미구현 (12단계 원자적 증가) |

다섯 문제의 공통 원인은 **상태가 각 서버의 메모리에 묶여 있다는 것**이고, Redis의 답은 **상태를 서버 밖 한 곳으로 빼는 것**입니다. 그 한 곳에서 키로 값을 찾는 입구가 이 프로젝트에서 직접 만든 해시 테이블입니다.

위 표는 `python -m demo.scenario`로 그대로 재현됩니다 (8단계 데모, 웹 서버 2대가 같은 mini-redis 사용).

## 2. 실행 방법

배포된 화면: https://mini-stock-tu7t.onrender.com (Render 무료, 15분 동안 아무도 안 쓰면 잠들어 첫 접속이 30초쯤 걸립니다)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

| 하고 싶은 것 | 명령 |
| --- | --- |
| mini-redis 서버 띄우기 (포트 8000) | `python -m mini_redis.server` |
| 서버 두 대 시연 (로컬 캐시 vs mini-redis, 약 20초) | `python -m demo.scenario` |
| 시연을 한 단계씩 (발표용) | `python -m demo.scenario --step` |
| 성능 비교 (mini-redis, 데모 API를 먼저 띄운 뒤) | `python -m demo.app` → `python -m bench.benchmark` |
| 주식 화면 (데모 API를 먼저 띄운 뒤, 포트 8010) | `python -m stock.server` |
| 세 서버를 한 번에 (배포와 같은 방식) | `python -m deploy.start` |
| 전체 테스트 | `python -m unittest -v` |

직접 요청을 보내 보려면 (mini-redis를 띄운 상태에서):

```bash
curl -X POST localhost:8000/set -H "Content-Type: application/json" -d '{"key":"name","value":"mini","ttl":5}'
curl "localhost:8000/get?key=name"        # 200 {"key":"name","value":"mini"}
# 5초 뒤
curl "localhost:8000/get?key=name"        # 404 {"error":"not found"}
```

## 더 보기

| 더 보기 | 문서 |
| --- | --- |
| 3. 구조 | [docs/readme/structure.md](docs/readme/structure.md) |
| 4. API | [docs/readme/api.md](docs/readme/api.md) |
| 5. 해시 테이블은 이렇게 동작한다 | [docs/readme/hashtable.md](docs/readme/hashtable.md) |
| 6. 성능 비교 | [docs/readme/performance.md](docs/readme/performance.md) |
| 7. 테스트 | [docs/readme/tests.md](docs/readme/tests.md) |
| 8. 실제 Redis와 다른 점 | [docs/readme/redis-differences.md](docs/readme/redis-differences.md) |
| 9. 결정 기록과 문서 모음 | [docs/readme/documents.md](docs/readme/documents.md) |
