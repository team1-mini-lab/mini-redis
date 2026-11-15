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

## 데모 API와 성능 비교의 설계 결정

결정마다 그 결정이 지켜지는지 확인하는 테스트나 시연을 짝지어 두었습니다.

| | 결정 | 이유 | 확인 |
|---|---|---|---|
| 구조 | mini-redis를 HTTP로 호출 | 과제의 "외부에서 사용". import하면 같은 프로세스라 공용 저장소를 보여 줄 수 없음 | `test_cache_aside_and_invalidation_over_http`, `test_session_over_http` (실제 포트에 띄운 mini-redis에 HTTP로 요청) |
| | 가짜 DB는 SQLite 파일 | 서버를 여러 대 띄워도 원본은 하나여야 함. dict로 두면 서버마다 DB가 따로 생겨 시연이 성립하지 않음. 실제 서비스도 앱 서버는 여러 대, DB는 공유 | 시연 `python -m demo.scenario` (서버 A와 B가 별도 프로세스로 DB 파일 하나를 함께 씀) |
| | 로컬 캐시 모드(`--cache local`)를 일부러 둠 | 문제가 생기는 모습을 먼저 봐야 mini-redis로 풀리는 게 보임. 앱 코드는 그대로 두고 캐시만 바꿔 끼워 비교 | `test_local_cache_goes_stale`, `test_mini_redis_stays_consistent` |
| | 로컬 캐시도 mini-redis와 같은 TTL·지연 삭제로 구현 | 시연의 1부(로컬 캐시)와 2부(mini-redis)의 차이가 캐시 위치 하나뿐이어야 비교가 성립함 | `test_local_cache_expires_the_same_way`, `test_expired_key_delete_is_same_on_both_caches` |
| 조회와 무효화 | 조회는 Cache-Aside | 앱이 캐시를 먼저 보고, 없으면 DB에서 가져와 저장. 캐시가 없어도 DB로 동작하므로 장애 대비(아래)가 가능함 | `test_second_read_comes_from_cache` |
| | 쓰기 때 캐시를 덮어쓰지 않고 지움 | 덮어쓰면 "DB 수정"과 "캐시 수정" 순서가 어긋날 때 옛 값이 남을 수 있음. 지우면 다음 읽기가 반드시 DB에서 최신 값을 가져옴 | `test_price_update_invalidates_cache` |
| | DB 먼저 고치고, 그다음 캐시 삭제 | 캐시를 먼저 지우면, DB를 고치기 전에 다른 요청이 옛 값을 다시 캐시에 채울 수 있음 | `test_db_is_updated_before_cache_delete` |
| | 종목 하나가 바뀌어도 목록 키 전체를 지움 | 거래량 상위 목록을 키 하나에 통째로 저장하기 때문. 그 종목만 골라 고치는 것보다 단순하고, 다음 조회 한 번으로 다시 채워짐 | `test_price_update_invalidates_cache` |
| | 캐시 삭제가 실패해도 가격 수정은 성공으로 처리 | 원본(DB)이 맞는 게 우선. 응답의 `cache_invalidated`로 알림(`true`는 지웠음, `false`는 못 지웠거나 지울 키가 없었음). 남은 옛 값은 TTL이 지나면 사라짐 | `test_write_still_succeeds` |
| 만료(TTL) | TTL 60초를 함께 줌 | 무효화를 깜빡해도 60초 뒤엔 사라지는 안전망. 시연 스크립트만 환경변수로 600초. 근거는 아래 「TTL 60초는 어떻게 정했나」 | `test_expired_cache_goes_back_to_db`, `test_ttl_heals_missed_invalidation`, `test_ttl_is_sent_over_http` |
| | 세션에 별도 기능을 만들지 않음 | 세션도 키-값이라 거래량 상위 종목과 같은 set / get으로 끝남. 로그인 유지 시간이 그대로 TTL이 됨 (`DEMO_SESSION_TTL`, 기본 30분). 30분은 흔히 쓰는 로그인 유지 시간(30분~하루) 중 짧은 쪽 | `test_session_local_cache_logs_out_on_other_server`, `test_session_mini_redis_keeps_login`, `test_session_expires_after_ttl` |
| 장애 대비 | mini-redis가 죽어도 DB로 응답 | 캐시는 성능 문제일 뿐 기능 문제가 아님. 통신 실패를 "캐시 미스"로 처리 (Cache-Aside라 가능). 단, 세션은 원본이 캐시뿐이라 예외 (아래 「알고 남겨 둔 한계」) | `test_read_answers_from_db` |
| | mini-redis 호출 타임아웃 1초 (`cache.py`의 `TIMEOUT_SECONDS`) | mini-redis가 응답하지 않을 때 고객이 오래 기다리지 않고 DB로 넘어가게. 조회와 저장이 둘 다 막히면 요청마다 최대 약 2초 늘어남 | `test_slow_mini_redis_times_out` |
| 성능 비교 | 캐시 미사용은 `?nocache=1`로 | 같은 코드 경로에서 캐시만 빼서, 다른 조건은 똑같이 유지 | `test_nocache_skips_cache` |
| | 첫 조회(미스)와 이후(히트)를 따로 측정 | 섞어서 평균을 내면 측정 횟수에 따라 숫자가 달라져 뜻이 없어짐 | 아래 「측정 결과」 |
| | 시간은 클라이언트(벤치마크)에서 잼 | 고객이 실제로 기다리는 시간이라서. 서버가 돌려주는 `elapsed_ms`에는 네트워크 왕복이 빠짐 | 아래 「측정 결과」 |
| | 응답 시간과 함께 DB 조회 횟수를 셈 | 캐시의 목적은 DB 보호. 배수는 가짜 DB 지연에 따라 달라지지만, 막은 건수는 그렇지 않음 | 아래 「측정 결과」 |

### 만료와 무효화는 어디서 일어나나

| | 만료 (expiration) | 무효화 (invalidation) |
|---|---|---|
| 누가 지우나 | mini-redis (앱은 저장할 때 TTL만 정함) | 데모 API |
| 언제 | TTL이 지난 키를 조회하거나 지울 때 (지연 삭제) | DB를 고친 직후 |
| 코드 | `mini_redis/store.py`의 `get()`, `delete()` — 만료 시점이 지났으면 지우고 「없음」 | `demo/app.py`의 `update_price()` → `invalidate_top_stocks()` → `DELETE /delete` |
| 남는 틈 | 아무도 조회하지 않는 만료 키는 메모리에 남음 (주기적 정리는 13단계) | 수정 직전에 시작된 조회가 DB에서 옛 값을 읽어, 삭제가 끝난 뒤 캐시에 다시 넣을 수 있음 |

두 방식은 함께 씁니다. 무효화가 정상이면 만료가 오기 전에 이미 지워지고, 무효화를 놓친 경우(삭제 실패, 위의 틈, 앱을 거치지 않은 DB 수정)에만 만료가 안전망으로 일합니다.

### TTL 60초는 어떻게 정했나

TTL은 무효화의 대체가 아니라 **안전망**입니다. 무효화가 제대로 되면 TTL은 거의 발동하지 않고, 실제로 일하는 순간은 무효화를 놓쳤을 때(삭제 실패, 위의 틈, 앱을 거치지 않은 DB 수정)뿐입니다. 그래서 "얼마나 캐시하고 싶은가"가 아니라 **"무효화가 실패했을 때 고객이 틀린 값을 보는 시간을 얼마까지 참을 수 있나"**로 역산했습니다.

| TTL | 무효화 실패 시 최대 오차 | 1분당 DB 조회 | 판단 |
|---|---|---|---|
| 5초 | 5초 | 12회 | 안전망은 촘촘하지만 캐시 효과가 거의 없어짐. 시연도 성립하지 않음 |
| 60초 | 60초 | 1회 | 거래량 상위 종목 목록에는 충분 — **채택** |
| 10분 | 10분 | 0.1회 | DB는 가장 편하지만 무효화 버그가 10분간 고객에게 노출 |
| `DEMO_CACHE_TTL` | - | - | 시연 스크립트만 600초. 운영 기본값과 분리돼 있어 길어도 위험이 없음 |

"1분당 DB 조회"는 같은 키를 계속 조회할 때의 값입니다. 캐시 미스는 TTL마다 한 번씩 나므로 `60초 ÷ TTL`입니다.

- **시연·테스트용 값은 코드 기본값을 바꾸지 않고 환경변수로 줍니다.** 기본값을 바꾸면 운영 설정이 시연 편의에 끌려갑니다. `demo/app.py`의 `TOP_STOCKS_TTL`은 `DEMO_CACHE_TTL`이 없으면 60초 그대로입니다.
- 기본 60초, 시연 스크립트만 600초로 팀이 정했습니다 ([docs/DECISIONS.md](../docs/DECISIONS.md)의 「기준 구현을 고른 뒤의 결정」).

> 만료(TTL)는 **저장소**가 시간이 되면 알아서 지우는 것이고, 무효화는 값이 바뀐 걸 아는 **앱**이 바로 지우는 것입니다. 둘을 헷갈리면 "가격이 틀리게 보인다"는 문제를 TTL 숫자를 줄여서 풀려고 하게 되는데, 그러면 틀린 시간이 짧아질 뿐 없어지지 않고 DB 조회만 늘어납니다. 가격이 바뀌는 순간 지우는 것(무효화)이 진짜 해결입니다.

## 테스트

```bash
python -m unittest tests.test_demo -v      # 22개, 3초 안에 끝남
```

테스트 22개가 각각 무엇을 확인하는지, 변이 검사 결과, 검토하며 고친 내용은 [docs/eungi/TEST_RECORD.md](../docs/eungi/TEST_RECORD.md)에 있습니다.

**어떻게 돌리는지**

| 테스트 | 방법 |
|---|---|
| 대부분 (19개) | 포트를 열지 않고 Flask `test_client`로 처리 함수를 바로 부릅니다. mini-redis도 같은 방식으로 불러서, 네트워크만 빠지고 `server.py` → `store.py` → 해시 테이블은 실제 코드가 돕니다. 서버 두 대는 캐시 객체 두 개를 요청마다 바꿔 끼워 흉내 냅니다. |
| `RealHttpTest` (3개) | mini-redis를 실제 포트에 띄우고, 배포와 같은 `RedisCache`로 네트워크 요청을 보냅니다. |

**무엇을 확인하는지**

| 대상 | 테스트 |
|---|---|
| 설계 결정 | 위 「설계 결정」 표의 "확인" 칸 |
| 잘못된 입력 (가격이 음수·문자·소수·true면 400, 없는 종목 404, 로그인 본문 없으면 400) | `test_bad_price`, `test_unknown_stock`, `test_session_input` |

**테스트가 정말 잡아내는지**

코드를 일부러 12군데 망가뜨렸고, 12군데 모두 테스트가 실패했습니다.

예를 들어 `update_price()`에서 캐시를 지우는 줄을 빼면 `test_price_update_invalidates_cache`가 실패합니다.

```bash
python docs/eungi/check_tests_catch_bugs.py   # 다시 돌려 보기
```

### 알고 남겨 둔 한계

데모 범위라 고치지 않았지만 알고 있는 점입니다.

| 한계 | 무슨 일이 생기나 | 이후 계획 |
|---|---|---|
| 세션은 캐시가 원본 | mini-redis가 꺼지면 로그인은 토큰을 주지만 세션이 저장되지 않아 다음 요청에서 401. mini-redis를 재시작하면 세션이 모두 사라짐 | 재시작 문제는 14단계(데이터 유지)에서 풀림 |
| 캐시 스탬피드 | 무효화나 만료 직후 동시에 들어온 요청이 모두 미스가 되어 한꺼번에 DB로 감 | 없음 |
| 서킷 브레이커 없음 | mini-redis가 느리면 요청마다 타임아웃(1초)만큼 기다림 | 없음 |
| 짧은 세션 토큰 | 16진수 8자이고 주소(`?token=`)에 실어 보냄. 시연용 | 없음 |
| DB 조회 횟수는 합계 | 같은 DB 파일을 쓰는 모든 서버의 합계. 벤치마크를 잴 때는 다른 데모 서버를 끄고 재야 함 | 측정할 때 주의할 점 |

## 성능 비교 결과

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

데모 API와 성능 비교를 어떻게 만들고 검증했는지 설명한 팀 내 발표 자료는 [feat/8-demo 브랜치 docs/eungi](https://github.com/team1-mini-lab/mini-redis/tree/feat/8-demo/docs/eungi)에 있습니다. 슬라이드 PDF는 바로 열어 볼 수 있고, 서버 A·B 화면이 움직이는 모습은 HTML 파일을 내려받아 브라우저로 열면 볼 수 있습니다.
