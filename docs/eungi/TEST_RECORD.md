# 데모 API 테스트 기록

8·9단계(데모 API, 성능 비교)의 테스트를 어떻게 만들고, 그 테스트가 정말 설계 결정을 지키는지 어떻게 확인했는지 남긴 기록입니다. 설계 결정과 각 결정을 확인하는 테스트의 짝은 [demo/README.md](../../demo/README.md)의 설계 결정 표에 있습니다.

```bash
python -m unittest tests.test_demo -v           # 데모 API 테스트 22개
python docs/eungi/check_tests_catch_bugs.py     # 변이 검사 12가지
```

## 1. 처음 만든 테스트 (14개)

8·9단계를 만들면서 완료 기준과 서버 두 대 장면을 확인하려고 만든 테스트입니다.

| 묶음 | 테스트 | 확인하는 것 |
|---|---|---|
| 완료 기준 | `test_second_read_comes_from_cache` | 두 번째 조회는 캐시에서 나오고 DB는 한 번만 감 |
| | `test_price_update_invalidates_cache` | 가격을 바꾸면 캐시가 지워져 다음 조회가 새 가격 |
| | `test_nocache_skips_cache` | `?nocache=1`은 캐시를 쓰지도 채우지도 않음 |
| 서버 두 대 | `test_local_cache_goes_stale` | 로컬 캐시는 서버 B가 옛 가격을 봄 |
| | `test_mini_redis_stays_consistent` | mini-redis는 서버 B도 새 가격 |
| | `test_session_local_cache_logs_out_on_other_server` | 로컬 캐시는 다른 서버에서 로그인이 풀림 |
| | `test_session_mini_redis_keeps_login` | mini-redis는 다른 서버에서도 로그인 유지, 로그아웃은 모든 서버에서 |
| 캐시 장애 | `test_read_answers_from_db` | mini-redis가 꺼져도 조회는 DB로 답함 |
| | `test_write_still_succeeds` | 캐시를 못 지워도 가격 수정은 성공하고 `cache_invalidated: false` |
| 만료 | `test_expired_cache_goes_back_to_db` | TTL이 지나면 다시 DB로 감 |
| | `test_ttl_heals_missed_invalidation` | 무효화를 놓쳐도 TTL이 지나면 맞는 값이 됨 |
| 잘못된 입력 | `test_bad_price` | 가격이 음수·문자·소수·true면 400 |
| | `test_unknown_stock` | 없는 종목은 404 |
| | `test_session_input` | 로그인 본문이 없거나 비면 400 |

## 2. 검토 뒤 추가한 테스트 (8개)

설계 결정을 12가지로 정리한 뒤, 결정마다 테스트 짝을 맞추면서 추가한 테스트입니다. 별도의 AI 검토자에게 검토를 맡겨 짝이 비어 있던 곳을 더 찾았습니다.

**`test_db_is_updated_before_cache_delete`: DB를 먼저 고치고 그다음 캐시를 지우는지**

가격을 바꿀 때는 순서가 중요합니다. 캐시를 먼저 지우고 DB를 나중에 고치면, 그 사이에 들어온 다른 요청이 DB에서 옛 가격을 읽어 캐시에 다시 넣을 수 있습니다. 테스트는 캐시를 지우는 순간에 DB 가격을 들여다보고, 그때 이미 새 가격(40,000원)인지 확인합니다.

**`test_slow_mini_redis_times_out`: 대답하지 않는 mini-redis 앞에서 기다리지 않는지**

mini-redis가 꺼진 게 아니라, 연결은 받는데 대답을 하지 않는 경우도 있습니다. 이때 데모 API가 계속 기다리면 고객 화면이 멈춥니다. 테스트는 일부러 대답하지 않는 가짜 mini-redis를 만들고, 데모 API가 정해진 시간만 기다린 뒤 DB로 넘어가 답하는지 봅니다. 기본 대기 시간이 1초인지도 함께 확인합니다.

**`test_local_cache_expires_the_same_way`: 로컬 캐시도 mini-redis처럼 만료되는지**

시연은 로컬 캐시와 mini-redis를 나란히 비교합니다. 비교가 공정하려면 로컬 캐시도 TTL이 지나면 값이 사라져야 합니다. 테스트는 로컬 캐시에 짧은 TTL로 저장하고, 바로 조회하면 캐시에서, 조금 기다린 뒤 조회하면 DB에서 나오는지 봅니다.

**`test_session_expires_after_ttl`: 세션이 TTL이 지나면 사라지는지**

로그인 세션은 30분 동안 유지되도록 정했습니다(`DEMO_SESSION_TTL`, 1800초). 테스트는 로그인한 다음 바로 확인하면 "로그인됨(200)", TTL이 지난 뒤 확인하면 "로그인 필요(401)"가 나오는지 봅니다.

**`test_expired_key_delete_is_same_on_both_caches`: 두 캐시의 삭제 결과가 같은지**

이미 만료된 키를 지우라고 했을 때, 로컬 캐시와 mini-redis가 똑같이 "지울 게 없었다(`false`)"고 답하는지 봅니다. 5절 첫 줄에서 고친 동작을 지키는 테스트입니다.

**`RealHttpTest` 3개: 실제 네트워크 경로**

다른 테스트들은 빠르게 돌리려고 mini-redis 서버를 켜지 않고 코드를 바로 부릅니다(`test_client`). 그런데 배포된 주식 화면에서는 데모 API가 `RedisCache`로 mini-redis에 실제 네트워크(HTTP) 요청을 보냅니다. 이 세 테스트는 테스트 안에서 mini-redis 서버를 실제 포트에 켜고, 실제 서비스와 똑같이 `RedisCache`로 요청합니다.

| 테스트 | 확인하는 것 |
|---|---|
| `test_cache_aside_and_invalidation_over_http` | 서버 A가 채운 캐시를 서버 B도 보는지, 가격을 바꾸면 캐시가 지워지고 다음 조회가 새 가격인지 |
| `test_ttl_is_sent_over_http` | 만료 시간이 네트워크 요청에 실려 mini-redis까지 전달되어 실제로 만료되는지 |
| `test_session_over_http` | 서버 A에서 로그인하고 서버 B가 알아보는지, 로그아웃하면 모든 서버에서 풀리는지 |

**테스트에서 TTL을 0.05초로 줄이는 이유**

실제 TTL은 60초(세션은 30분)입니다. 테스트에서 그대로 쓰면 만료를 확인하려고 테스트마다 1분 넘게 기다려야 합니다. 시간이 지나면 사라지는 원리는 TTL 길이와 상관없이 같으므로, 테스트 안에서만 TTL을 0.05초로 줄이고 0.1초 뒤에 확인합니다. 테스트가 끝나면 원래 값으로 되돌립니다.

## 3. 변이 검사: 테스트가 정말 일하는지

테스트가 모두 통과해도, 그 테스트가 설계 결정을 지키는지는 알 수 없습니다. 그래서 결정 하나씩 코드를 일부러 어긋나게 바꾸고(변이), 그 결정을 맡은 테스트가 실패하는지 봤습니다. `check_tests_catch_bugs.py`가 변이를 넣고, 테스트를 돌리고, 코드를 되돌리는 일을 자동으로 반복합니다.

| 망가뜨린 것 | 무슨 뜻인가 | 실패해야 하는 테스트 | 결과 |
|---|---|---|---|
| 가격 수정 후 캐시를 지우지 않음 | 무효화가 빠지면 가격을 바꿔도 옛 가격이 계속 나옴 | `test_price_update_invalidates_cache` | 잡음 |
| 캐시를 DB 수정보다 먼저 지움 | 순서가 바뀌면 그 사이 다른 요청이 옛 가격을 캐시에 다시 넣을 수 있음 | `test_db_is_updated_before_cache_delete` | 잡음 |
| 캐시 삭제가 실패하면 500을 돌려줌 | DB는 이미 고쳐졌는데 "실패"라고 답하게 됨 | `test_write_still_succeeds` | 잡음 |
| `?nocache=1`이어도 캐시를 씀 | 성능 비교의 "캐시 미사용" 쪽이 사실은 캐시를 쓰게 됨 | `test_nocache_skips_cache` | 잡음 |
| 통신 실패를 예외로 터뜨림 | 지금은 mini-redis에 연결하지 못하면 `RedisCache`가 실패를 붙잡아 "캐시에 없음(`None`)"으로 바꾸고, 앱은 DB로 갑니다(`demo/cache.py` `_request`). 이 붙잡는 부분을 빼서 실패를 그대로 위로 던지게(예외) 바꾸면, mini-redis가 꺼졌을 때 고객이 DB 답 대신 500 오류를 받습니다 | `test_read_answers_from_db` | 잡음 |
| 타임아웃 기본값을 5초로 바꿈 | mini-redis가 대답하지 않을 때 고객이 5초씩 기다리게 됨 | `test_slow_mini_redis_times_out` | 잡음 |
| 로컬 캐시가 TTL을 무시함 | 로컬 캐시 값이 영원히 남아, 시연의 두 캐시 비교가 공정하지 않게 됨 | `test_local_cache_expires_the_same_way` | 잡음 |
| 로컬 캐시가 만료된 키 삭제에 `True`를 돌려줌 | 같은 상황에서 두 캐시의 `cache_invalidated` 값이 달라짐 | `test_expired_key_delete_is_same_on_both_caches` | 잡음 |
| 세션에 TTL을 주지 않음 | 로그인이 30분이 지나도 풀리지 않음 | `test_session_expires_after_ttl` | 잡음 |
| `RedisCache.get`이 응답을 잘못 읽음 | 실제 네트워크로 조회할 때 값을 못 꺼냄 | `test_cache_aside_and_invalidation_over_http` | 잡음 |
| `RedisCache.delete`가 항상 `False` | 실제 네트워크로 지워도 "못 지웠다"고 답함 | `test_cache_aside_and_invalidation_over_http` | 잡음 |
| `RedisCache.set`이 TTL을 보내지 않음 | mini-redis에 만료 시간이 전달되지 않아 값이 영원히 남음 | `test_ttl_is_sent_over_http` | 잡음 |

2절의 테스트를 더한 지금은 12가지를 모두 잡습니다.

## 4. 테스트를 늘린 과정

같은 변이 12가지를 테스트 파일의 세 시점에 돌려 비교했습니다.

| 시점 | `test_demo.py` 테스트 수 | 잡은 변이 | 아직 확인 범위 밖이던 것 |
|---|---|---|---|
| 8·9단계를 처음 만들었을 때 | 14개 | **4 / 12** | DB 먼저 고치는 순서, 타임아웃, 로컬 캐시 만료, 만료 키 삭제 결과, 세션 TTL, `RedisCache` 조회·삭제·저장 |
| 결정과 테스트를 짝지어 빈 결정을 채운 뒤 | 17개 | **6 / 12** | 타임아웃 기본값, 만료 키 삭제 결과, 세션 TTL, `RedisCache` 조회·삭제·저장 |
| AI 검토자의 검토를 반영한 뒤 | 22개 | **12 / 12** | 없음 |

- 처음 14개 테스트는 완료 기준과 서버 두 대 장면을 확인하려고 만든 것이라, 설계 결정 12가지 중 8가지는 확인 범위 밖이었습니다.
- 그 과정에서 찾은 기능상의 차이는 5절에 정리했습니다.
- 전체 테스트는 63개에서 71개가 되었습니다.

## 5. 검토에서 고친 것

테스트를 더한 것 말고, 코드 동작을 고치거나 한계로 기록한 것입니다.

**로컬 캐시의 삭제 결과** (`demo/cache.py` `LocalCache.delete`)

이미 만료된 키를 지우라고 하면, mini-redis는 "지울 게 없었다(`false`)"고 답하는데 로컬 캐시는 "지웠다(`true`)"고 답했습니다. 그래서 같은 상황에서 가격 수정 응답의 `cache_invalidated`가 캐시 종류에 따라 달랐습니다. 로컬 캐시가 지울 때 만료 여부도 확인하게 고쳐서, 이제 둘이 같은 대답을 합니다.

**로그인 세션의 한계** (`demo/README.md` 「알고 남겨 둔 한계」)

로그인 세션은 DB에 없고 mini-redis에만 있습니다. mini-redis가 꺼지면 로그인은 토큰을 돌려주지만 세션이 저장되지 않아 다음 요청에서 401이 납니다. 데모 범위라 동작은 그대로 두고 한계로 적었습니다.

**벤치마크 표의 측정 조건** (`demo/app.py`, `bench/benchmark.py`)

벤치마크는 결과 표 맨 위에 "가짜 DB 지연 3초, 캐시 TTL 60초"라고 적습니다. 이 문장이 코드에 고정되어 있어서, DB 지연을 0.3초로 바꿔 재도 "3초"라고 적혔습니다. 그래서 데모 API의 `/` 응답이 실제 설정값(`db_delay_seconds`, `cache_ttl_seconds`)을 알려 주게 하고, 벤치마크가 그 값을 받아 표에 적게 고쳤습니다.

**잘못된 조건에서의 측정** (`bench/benchmark.py`)

벤치마크는 "mini-redis를 쓸 때"를 재는 도구입니다. 그런데 mini-redis가 꺼져 있거나 데모 API가 로컬 캐시 모드로 떠 있어도 그대로 측정해서, mini-redis와 상관없는 숫자가 나올 수 있었습니다. 이제는 그런 경우 "먼저 이렇게 실행하세요"라고 안내하고 멈춥니다.

**테스트의 `ResourceWarning`** (`tests/test_demo.py`)

타임아웃 테스트에서 가짜 mini-redis가 받은 연결을 닫지 않아, 테스트가 끝날 때 "닫히지 않은 연결이 있다"는 경고가 떴습니다. 결과에는 영향이 없었지만 끝날 때 연결을 닫도록 정리했습니다.

이 테스트와 검사는 Claude Code와 함께 설계하고 실행했습니다.
