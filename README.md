# mini-redis

직접 구현한 해시 테이블 자료구조의 키-값 저장소를 HTTP 서버로 띄우고, 웹 서버 여러 대가 함께 하나의 캐시를 쓰는 것을 구현했습니다.

## 목차

1. [redis는 왜 만들어졌나?](#1-redis는-왜-만들어졌나)
2. [실행 방법](#2-실행-방법)
3. [직접 실행](#3-직접-실행)

## 1. redis는 왜 만들어졌나?

캐시는 DB에서 한 번 읽어 온 값을 가까운 메모리에 잠깐 보관해 두었다가, 같은 요청이 다시 오면 DB에 가지 않고 바로 돌려주는 장치입니다. DB는 값을 하나 돌려주기 위해서도 요청을 해석하고, 조건에 맞는 데이터를 찾고, 필요하면 디스크에서 읽어 오는 일을 합니다. 캐시는 키 하나로 메모리에서 값을 바로 꺼내기 때문에 이 과정을 건너뜁니다.

웹 서버가 한 대뿐이라면 캐시는 웹 서버 프로그램 안에 두는 것으로 충분합니다. 모든 요청이 같은 서버로 오고, 그 서버의 메모리는 하나뿐이라서 캐시도 하나뿐이기 때문입니다. 값이 바뀌면 그 캐시에서 지우기만 하면 됩니다.

프로그램 안의 캐시는 네트워크를 거치지 않으니 캐시 중에서 가장 빠릅니다. Redis 같은 캐시는 서버 밖의 별도 프로그램이라 요청마다 네트워크를 한 번 더 오가야 해서, 프로그램 안의 캐시보다 느립니다. **더 빠른 방법을 두고 왜 굳이 캐시를 서버 밖에 두게 되었을까요?**

![장면 1 데이터가 바뀌어도 다른 서버는 옛 값을 줌](docs/images/scene-1.svg)

![장면 2 로그인이 풀림](docs/images/scene-2.svg)

![장면 3 재시작하면 DB로 요청이 몰림](docs/images/scene-3.svg)

![장면 4 같은 데이터를 서버 수만큼 저장](docs/images/scene-4.svg)

![장면 5 함께 세야 하는 값이 어긋남](docs/images/scene-5.svg)

mini-redis를 직접 만들면서, 다섯 문제의 원인이 모두 같다는 것을 알게 되었습니다. **문제는 캐시가 각 서버의 메모리 안에 따로 있다는 것**입니다. Redis는 캐시를 서버 밖의 한 곳으로 빼서, 모든 웹 서버가 같은 캐시를 함께 쓰게 하는 방법으로 이 문제들을 해결합니다.

캐시를 서버 밖에 두면 요청마다 네트워크를 한 번 더 오가야 해서 프로그램 안의 캐시보다 조금 느립니다. 하지만 그 비용은 DB 조회보다 훨씬 작고, 그 대신 모든 서버가 같은 값을 보게 됩니다. 조금 느려지는 것을 받아들이고 서버 사이에 값이 어긋나지 않는 쪽을 고른 것입니다.

## 2. 실행 방법

https://mini-stock-tu7t.onrender.com

링크를 열면 mini-redis를 캐시로 쓰는 주식 매수 화면이 나옵니다. 따로 설치할 것은 없습니다. 오랫동안 아무도 접속하지 않았다면 서버가 깨어나는 동안 첫 화면이 늦게 뜰 수 있습니다.

화면 왼쪽의 **거래량 상위 종목** 목록은 DB에서 읽어 오는 데이터입니다. 이 데모의 DB는 일부러 조회마다 3초가 걸리게 만들어 두었습니다. **캐시 사용**을 켠 채 **새로고침**을 누르면 첫 조회만 DB에 가고, 그다음부터는 mini-redis에 저장된 값을 바로 받아 옵니다. 아래의 **화면 뒤에서 일어난 일**에서 데이터 출처(캐시인지 DB인지), 걸린 시간, 지금까지의 DB 조회 횟수를 확인할 수 있습니다. **캐시 사용**을 끄고 새로고침하면 매번 DB로 가서 3초씩 걸리고 DB 조회 횟수가 계속 늘어나는 것을 볼 수 있습니다.

종목 이름을 누르면 오른쪽 **매수 주문**에 그 종목이 선택됩니다. **시세 변경**에 새 가격을 넣고 **반영**을 누르면 DB의 가격을 바꾼 뒤 캐시에서 그 데이터를 지웁니다. 그래서 바로 다음 조회는 DB에서 새 가격을 읽어 오고, 그 뒤로는 다시 캐시에서 새 가격을 받아 옵니다. **캐시 비우기**는 캐시를 직접 비우고, **조회 횟수 초기화**는 DB 조회 횟수를 0으로 되돌립니다.

오른쪽 위에서 이름을 넣고 **로그인**하면 로그인 정보(세션)가 mini-redis에 30분 동안 저장됩니다. 새로고침해도 로그인이 유지되는 것은 서버가 mini-redis에서 세션을 찾기 때문입니다. **매수** 버튼은 아직 주문을 저장하지 않습니다. 주문을 저장할 DB(미니 DBMS)를 붙인 뒤에 동작합니다.

## 3. 직접 실행

코드를 받아서 내 컴퓨터에서 직접 돌려 보거나 테스트를 실행하려면, 먼저 한 번 아래처럼 준비합니다.

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
| 4. 구조 | [docs/readme/structure.md](docs/readme/structure.md) |
| 5. API | [docs/readme/api.md](docs/readme/api.md) |
| 6. 해시 테이블은 이렇게 동작한다 | [docs/readme/hashtable.md](docs/readme/hashtable.md) |
| 7. 성능 비교 | [docs/readme/performance.md](docs/readme/performance.md) |
| 8. 테스트 | [docs/readme/tests.md](docs/readme/tests.md) |
| 9. 실제 Redis와 다른 점 | [docs/readme/redis-differences.md](docs/readme/redis-differences.md) |
| 10. 결정 기록과 문서 모음 | [docs/readme/documents.md](docs/readme/documents.md) |
