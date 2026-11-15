# 데모 API와 성능 비교

mini-redis를 **DB 앞의 캐시**로 쓰는 앱입니다. mini-redis는 `import`가 아니라 **HTTP로** 부릅니다. 데모 API와 mini-redis가 서로 다른 프로세스라는 것, 이게 "상태를 서버 밖으로 뺀다"의 실제 모습입니다.

```
고객 → 데모 API(8001) ─→ mini-redis(8000)   있으면 바로 응답 (hit)
                      └→ 가짜 DB (3초)       없으면 DB 조회 후 캐시에 저장 (miss)
```

## 실행

```bash
python -m mini_redis.server    # 터미널 1 — mini-redis (8000)
python -m demo.app             # 터미널 2 — 데모 API (8001)
python -m bench.benchmark      # 터미널 3 — 성능 비교
```

## 시연: 서버가 여러 대가 되면

서버가 한 대면 파이썬 `dict`로 만든 로컬 캐시도 mini-redis와 똑같이 동작합니다. 차이는 **서버가 여러 대일 때** 드러납니다. 그래서 같은 데모 API를 두 대씩 띄우고, 캐시 위치만 바꿔서 똑같은 순서로 요청을 보냅니다.

```bash
python -m demo.scenario            # 처음부터 끝까지 자동으로 (약 30초)
python -m demo.scenario --step     # Enter를 누를 때마다 한 단계씩 (발표용)
python -m demo.scenario --delay 1  # DB 지연을 1초로 줄여서 빠르게
```

서버는 스크립트가 직접 띄우고 끝나면 끕니다. 터미널 하나면 됩니다. 단계마다 멈춰 설명하는 사이 캐시가 만료되지 않도록 시연에서는 TTL을 10분으로 씁니다 (기본 60초).

| 순서 | 하는 일 | 로컬 캐시 | mini-redis |
|---|---|---|---|
| ① | 서버 A로 조회 | DB (캐시 비어 있음) | DB (캐시 비어 있음) |
| ② | 서버 B로 조회 | **DB에 또 감** (같은 데이터를 서버 수만큼 저장하는 장면) | 캐시 (A가 채운 걸 B도 봄) |
| ③ | 서버 A에서 SW-AI 시세를 40,000원으로 변경 | A의 캐시만 지움 | mini-redis 키를 지움 |
| ④ | A, B로 조회 | **B는 50,000원** (데이터가 바뀌어도 다른 서버는 옛 값을 주는 장면) | A, B 모두 40,000원 |
| ⑤ | 서버 A 재시작 후 조회 | **DB** (재시작하면 DB로 요청이 몰리는 장면) | 캐시 (서버 밖이라 그대로) |
| ⑥ | 서버 A로 로그인 | A의 캐시에만 세션 저장 | mini-redis에 세션 저장 |
| ⑦ | 서버 B로 `/me` | **401 로그인이 필요합니다** (로그인이 풀리는 장면) | 알아봄 (어느 서버든 유지) |
| | 전체 DB 조회 | 4번 | 2번 |

직접 띄워서 확인하려면:

```bash
python -m demo.app --port 8001                 # mini-redis를 쓰는 서버 두 대
python -m demo.app --port 8002
python -m demo.app --port 8101 --cache local   # 로컬 캐시 서버 두 대 (비교용)
python -m demo.app --port 8102 --cache local
```

모든 응답에 `server`가 들어 있어서 어느 서버가 답했는지 보입니다.

## API

| 메서드 | 주소 | 하는 일 |
|---|---|---|
| GET | `/stocks/top` | 거래량 상위 종목 조회 (Cache-Aside). 응답의 `source`가 `cache`/`db` |
| GET | `/stocks/top?nocache=1` | 캐시를 건너뛰고 DB로 (성능 비교용) |
| PUT | `/stocks/<id>/price` | 가격 수정 → DB 수정 후 캐시 삭제 (무효화) |
| GET | `/stocks/<id>` | 종목 하나 (가격 확인용, 캐시 안 씀) |
| POST | `/login` | 로그인 → 세션을 캐시에 저장하고 토큰 반환 (본문 `{"user":"..."}`) |
| GET | `/me?token=` | 세션 조회. 없거나 만료되면 401 (로그인이 풀리는 장면 시연용) |
| POST | `/logout?token=` | 세션 키 삭제 |
| GET | `/stats` | DB 조회 횟수 |
| POST | `/stats/reset` | DB 조회 횟수 초기화 |
| DELETE | `/cache` | 캐시 비우기 |

## 시연 순서: 다른 서버가 옛 값을 주는 문제를 무효화로 해결

```bash
curl localhost:8001/stocks/top        # source=db,    약 3000ms, SW-AI 50000원
curl localhost:8001/stocks/top        # source=cache, 약 4ms,    SW-AI 50000원

curl -X PUT localhost:8001/stocks/1/price \
     -H "Content-Type: application/json" -d '{"price":40000}'
                                            # cache_invalidated=true

curl localhost:8001/stocks/top        # source=db,    약 3000ms, SW-AI 40000원
curl localhost:8001/stocks/top        # source=cache, 약 4ms,    SW-AI 40000원
```

## 시연 순서: 로그인이 풀리는 문제를 공용 저장소로 해결

세션도 결국 키-값이라 거래량 상위 종목과 똑같은 `set` / `get`을 씁니다. 따로 만든 기능이 없습니다.

```bash
# 서버 두 대를 띄워 두고 (한 대는 로그인, 다른 한 대로 조회)
python -m demo.app --port 8001
python -m demo.app --port 8002

TOKEN=$(curl -s -X POST localhost:8001/login \
        -H "Content-Type: application/json" -d '{"user":"guest"}' | python -c 'import json,sys;print(json.load(sys.stdin)["token"])')

curl "localhost:8002/me?token=$TOKEN"       # {"user":"guest"}  — 다른 서버인데 알아봄
curl -X POST "localhost:8001/logout?token=$TOKEN"
curl -i "localhost:8002/me?token=$TOKEN"    # 401 로그인이 필요합니다 — 모든 서버에서 풀림
```

`--cache local`로 띄운 두 대에 같은 순서로 보내면 첫 `/me`부터 401이 나옵니다. 로그인을 받은 서버만 세션을 알기 때문입니다.

## 설계 결정

| 결정 | 이유 |
|---|---|
| mini-redis를 HTTP로 호출 | 과제의 "외부에서 사용". import하면 같은 프로세스라 공용 저장소를 보여 줄 수 없음 |
| 쓰기 때 캐시를 **덮어쓰지 않고 지움** | 덮어쓰면 "DB 수정"과 "캐시 수정" 순서가 어긋날 때 옛 값이 남을 수 있음. 지우면 다음 읽기가 반드시 DB에서 최신 값을 가져옴 |
| DB 먼저 고치고, 그다음 캐시 삭제 | 캐시를 먼저 지우면, DB를 고치기 전에 다른 요청이 옛 값을 다시 캐시에 채울 수 있음 |
| 캐시 삭제가 실패해도 가격 수정은 성공으로 처리 | 원본(DB)이 맞는 게 우선. 응답의 `cache_invalidated: false`로 알리고, 남은 옛 값은 TTL이 지나면 사라짐 |
| 종목 하나가 바뀌어도 목록 키 전체를 지움 | 거래량 상위 목록을 키 하나에 통째로 저장하기 때문. 그 종목만 골라 고치는 것보다 단순하고, 다음 조회 한 번으로 다시 채워짐 |
| mini-redis 호출 타임아웃 1초 (`cache.py`의 `TIMEOUT_SECONDS`) | mini-redis가 응답하지 않을 때 고객이 오래 기다리지 않고 바로 DB로 넘어가게 |
| TTL 60초를 함께 줌 | 무효화를 깜빡해도 60초 뒤엔 사라지는 안전망. 값을 정한 근거는 아래 「TTL 60초는 어떻게 정했나」 |
| mini-redis가 죽어도 DB로 응답 | 캐시는 성능 문제일 뿐 기능 문제가 아님. 통신 실패를 "캐시 미스"로 처리 (Cache-Aside라 가능) |
| 성능 비교는 `?nocache=1`로 | 같은 코드 경로에서 캐시만 빼서, 다른 조건은 똑같이 유지 |
| 가짜 DB는 SQLite 파일 | 서버를 여러 대 띄워도 원본은 하나여야 함. `dict`로 두면 서버마다 DB가 따로 생겨 시연이 성립하지 않음. 실제 서비스도 앱 서버는 여러 대, DB는 공유 |
| 로컬 캐시 모드(`--cache local`)를 일부러 둠 | 문제가 생기는 모습을 먼저 봐야 mini-redis로 풀리는 게 보임. 앱 코드는 그대로 두고 캐시만 바꿔 끼워 비교 |
| 로컬 캐시도 mini-redis와 같은 TTL·지연 삭제로 구현 | 시연의 1부(로컬 캐시)와 2부(mini-redis)의 차이가 캐시 위치 하나뿐이어야 비교가 성립함 |
| 세션에 별도 기능을 만들지 않음 | 세션도 키-값이라 거래량 상위 종목과 같은 `set` / `get`으로 끝남. 로그인 유지 시간이 그대로 TTL이 됨 (`DEMO_SESSION_TTL`, 기본 30분). 30분은 흔히 쓰는 로그인 유지 시간(30분~하루) 중 짧은 쪽 |
| 첫 조회(미스)와 이후(히트)를 따로 측정 | 섞어서 평균을 내면 측정 횟수에 따라 숫자가 달라져 뜻이 없어짐 |
| 시간은 클라이언트(벤치마크)에서 잼 | 고객이 실제로 기다리는 시간이라서. 서버가 돌려주는 `elapsed_ms`에는 네트워크 왕복이 빠짐 |
| 응답 시간과 함께 DB 조회 횟수를 셈 | 캐시의 목적은 DB 보호. 배수는 가짜 DB 지연에 따라 달라지지만, 막은 건수는 그렇지 않음 |

### 만료와 무효화는 어디서 일어나나

| | 만료 (expiration) | 무효화 (invalidation) |
|---|---|---|
| 누가 지우나 | mini-redis (앱은 저장할 때 TTL만 정함) | 데모 API |
| 언제 | TTL이 지난 키를 조회할 때 (지연 삭제) | DB를 고친 직후 |
| 코드 | `mini_redis/store.py`의 `get()` — 만료 시점이 지났으면 지우고 「없음」 | `demo/app.py`의 `update_price()` → `invalidate_top_stocks()` → `DELETE /delete` |
| 남는 틈 | 아무도 조회하지 않는 만료 키는 메모리에 남음 (주기적 정리는 13단계) | 수정 직전에 시작된 조회가 DB에서 옛 값을 읽어, 삭제가 끝난 뒤 캐시에 다시 넣을 수 있음 |
| 테스트 | `test_expired_cache_goes_back_to_db` | `test_price_update_invalidates_cache` |

두 방식은 함께 씁니다. 무효화가 정상이면 만료가 오기 전에 이미 지워지고, 무효화를 놓친 경우(삭제 실패, 위의 틈, 앱을 거치지 않은 DB 수정)에만 만료가 안전망으로 일합니다.

### TTL 60초는 어떻게 정했나

TTL은 무효화의 대체가 아니라 **안전망**입니다. 무효화가 제대로 되면 TTL은 거의 발동하지 않고, 실제로 일하는 순간은 쓰기 때 캐시를 지우는 데 실패했을 때뿐입니다. 그래서 "얼마나 캐시하고 싶은가"가 아니라 **"무효화가 실패했을 때 고객이 틀린 값을 보는 시간을 얼마까지 참을 수 있나"**로 역산했습니다.

| TTL | 무효화 실패 시 최대 오차 | 1분당 DB 조회 | 판단 |
|---|---|---|---|
| 5초 | 5초 | 12회 | 안전망은 촘촘하지만 캐시 효과가 거의 없어짐. 시연도 성립하지 않음 |
| 60초 | 60초 | 1회 | 거래량 상위 종목 목록에는 충분 — **채택** |
| 10분 | 10분 | 0.1회 | DB는 가장 편하지만 무효화 버그가 10분간 고객에게 노출 |
| `DEMO_CACHE_TTL` | - | - | 시연 스크립트만 600초. 운영 기본값과 분리돼 있어 길어도 위험이 없음 |

"1분당 DB 조회"는 같은 키를 계속 조회할 때의 값입니다. 캐시 미스는 TTL마다 한 번씩 나므로 `60초 ÷ TTL`입니다.

- **TTL을 짧게 해도 다른 서버가 옛 값을 주는 문제는 풀리지 않습니다.** 그 시간 동안은 여전히 틀린 값이고, 노출 시간만 줄어듭니다. 근본 해결은 쓰기 때 지우는 것입니다.
- **시연·테스트용 값은 코드 기본값을 바꾸지 않고 환경변수로 줍니다.** 기본값을 바꾸면 운영 설정이 시연 편의에 끌려갑니다. `demo/app.py`의 `TOP_STOCKS_TTL`은 `DEMO_CACHE_TTL`이 없으면 60초 그대로입니다.
- 기본 60초, 시연 스크립트만 600초로 팀이 정했습니다 ([docs/DECISIONS.md](../docs/DECISIONS.md)의 「기준 구현을 고른 뒤의 결정」).

> 만료(TTL)는 **저장소**가 시간이 되면 알아서 지우는 것이고, 무효화는 값이 바뀐 걸 아는 **앱**이 바로 지우는 것입니다. 둘을 헷갈리면 "가격이 틀리게 보인다"는 문제를 TTL 숫자를 줄여서 풀려고 하게 되는데, 그러면 틀린 시간이 짧아질 뿐 없어지지 않고 DB 조회만 늘어납니다. 가격이 바뀌는 순간 지우는 것(무효화)이 진짜 해결입니다.

## 테스트

```bash
python -m unittest tests.test_demo -v      # 14개, 서버를 띄우지 않고 1초 안에 끝남
```

서버를 띄우지 않고 Flask `test_client`로 요청을 보냅니다. mini-redis 쪽도 실제 `mini_redis/server.py`를 `test_client`로 부르므로, 데모 API → mini-redis HTTP API → 저장소 → 해시 테이블까지 실제 코드가 그대로 돕니다. "서버 두 대"는 요청마다 데모 API가 쓰는 캐시 객체를 바꿔 끼워 흉내 냅니다.

| 묶음 | 확인하는 것 |
|---|---|
| 완료 기준 | 두 번째 조회는 캐시에서(DB 1회) · 가격 수정 후 새 가격 · `?nocache=1`은 캐시를 안 씀 |
| 서버 두 대 | 로컬 캐시는 B가 옛 가격(50,000원)을 봄 · mini-redis는 B도 새 가격 · 세션도 같은 차이(401 / 알아봄) · 로그아웃은 모든 서버에서 |
| 캐시가 죽으면 | 조회는 DB로 답함 · 가격 수정도 성공하고 `cache_invalidated: false` |
| 만료 | TTL이 지나면 다시 DB · DB를 앱 밖에서 고쳐도(무효화 실패) TTL이 지나면 저절로 맞음 |
| 잘못된 입력 | 가격이 음수·문자·소수·true면 400 · 없는 종목 404 · 로그인 본문 없으면 400 |

캐시 삭제를 일부러 빼고 돌려 보면 "가격 수정 후 새 가격", "mini-redis는 B도 새 가격", "로그아웃" 세 테스트가 실패합니다. 무효화가 빠지면 테스트가 잡아냅니다.

## 측정 결과

각 10회 측정. 가짜 DB 지연 3초, 캐시 TTL 60초.

| 경우 | 평균 | 최소 | 최대 |
| --- | --- | --- | --- |
| 캐시 미사용 (매번 DB) | 3007.0ms | 3005.1ms | 3017.7ms |
| 캐시 사용 — 첫 조회(미스) | 3009.6ms | - | - |
| 캐시 사용 — 이후(히트) | 4.1ms | 2.9ms | 6.2ms |

- 캐시 히트는 DB 조회보다 약 **700배** 빠릅니다. 이 배수는 가짜 DB에 넣은 지연 시간에 따라 달라집니다.
- DB 조회 횟수가 10회에서 1회로 줄어, 9건을 막았습니다.
- 첫 조회는 캐시에 값이 없어 느린 것이 정상입니다. 캐시의 효과는 그 다음부터 나옵니다.

> 숫자는 측정 환경마다 다릅니다. `python -m bench.benchmark --markdown`으로 다시 재서 바꿔 넣으세요.

실제 Redis와 어디가 다르고 왜 그렇게 했는지는 [docs/eungi/REDIS_COMPARISON.md](../docs/eungi/REDIS_COMPARISON.md)에 정리되어 있습니다.

8·9단계 발표 자료와 대본(PDF)은 [feat/8-demo 브랜치 docs/eungi](https://github.com/team1-mini-lab/mini-redis/tree/feat/8-demo/docs/eungi)에 있습니다.
