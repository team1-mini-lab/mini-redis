# mini-redis

직접 구현한 해시 테이블 자료구조의 키-값 저장소를 HTTP 서버로 띄우고, 웹 서버 여러 대가 함께 하나의 캐시를 쓰는 것을 구현했습니다.

## 목차

1. [redis는 왜 만들어졌나?](#1-redis는-왜-만들어졌나)
2. [실행 방법](#2-실행-방법)

## 1. redis는 왜 만들어졌나?

캐시는 DB에서 한 번 읽어 온 값을 가까운 메모리에 잠깐 보관해 두었다가, 같은 요청이 다시 오면 DB에 가지 않고 바로 돌려주는 장치입니다. DB 조회는 디스크와 네트워크를 거쳐 느리지만, 메모리에서 꺼내는 것은 훨씬 빠릅니다.

웹 서버가 한 대뿐이라면 캐시는 그 서버 프로그램 안의 파이썬 `dict` 하나로 충분합니다. 모든 요청이 같은 서버로 오고, 그 서버의 메모리는 하나뿐이라서 캐시도 하나뿐이기 때문입니다. 값이 바뀌면 그 `dict`에서 지우기만 하면 됩니다.

그런데 프로그램 안의 `dict`는 네트워크를 거치지 않으니 캐시 중에서 가장 빠릅니다. Redis 같은 캐시는 서버 밖의 별도 프로그램이라 요청마다 네트워크를 한 번 더 오가야 해서, 프로그램 안의 `dict`보다 느립니다. **더 빠른 방법을 두고 왜 굳이 캐시를 서버 밖에 두게 되었을까요?** 답은 서버가 여러 대가 되는 순간에 있습니다.

사용자가 늘어 서버 한 대로 감당이 안 되면 같은 웹 서버를 여러 대 띄우고, 요청을 여러 서버에 나눠 보냅니다. 이때 각 서버는 서로 다른 프로그램이라 메모리를 공유하지 않습니다. 그래서 서버마다 `dict` 캐시를 따로 갖게 되고, 같은 키에 대해 서버 A의 캐시와 서버 B의 캐시가 서로 다른 값을 들고 있을 수 있습니다. 서버 A에서 값을 바꾸고 A의 캐시를 지워도 서버 B는 그 사실을 모르고 옛 값을 계속 돌려줍니다. 아래 표는 이렇게 서버마다 캐시를 따로 들고 있을 때 생기는 다섯 가지 문제입니다.

| 장면 | 로컬 캐시 (서버마다 따로) | mini-redis (서버 밖 한 곳) |
| --- | --- | --- |
| ① 가격이 왔다 갔다 | 서버 A에서 시세를 바꿔도 서버 B는 옛 가격 50,000원 | A, B 모두 40,000원 |
| ② 로그인이 풀림 | A에서 로그인했는데 B는 모름 (401) | B도 알아봄 |
| ③ 배포하면 DB가 몰림 | 서버를 재시작하면 캐시가 사라져 DB로 감 | 캐시가 서버 밖에 있어 그대로 |
| ④ 같은 데이터를 서버 수만큼 저장 | 서버마다 DB를 따로 조회 (DB 4번) | 한 번 채우면 모두 씀 (DB 2번) |
| ⑤ 함께 세야 하는 값이 틀림 | 재고 1개가 두 번 팔림 | 아직 미구현 (12단계 원자적 증가) |

다섯 문제의 공통 원인은 **상태가 각 서버의 메모리에 묶여 있다는 것**이고, Redis의 답은 **상태를 서버 밖 한 곳으로 빼는 것**입니다. 캐시를 서버 밖에 두면 요청마다 네트워크를 한 번 더 오가는 비용이 생깁니다. 하지만 그 비용은 몇 밀리초 정도로 DB 조회보다 훨씬 작고(이 프로젝트 측정에서 캐시 히트 약 4ms, 3초 지연을 넣은 가짜 DB 조회 약 3,000ms), 그 대신 모든 서버가 같은 값을 보게 됩니다. 조금 느려지는 것을 받아들이고 서버 사이에 값이 어긋나지 않는 쪽을 고른 것입니다.

그 한 곳에서 키로 값을 찾는 입구가 이 프로젝트에서 직접 만든 해시 테이블입니다.

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
