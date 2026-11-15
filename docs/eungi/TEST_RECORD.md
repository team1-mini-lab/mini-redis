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

설계 결정과 테스트를 한 줄씩 짝지어 보니 테스트가 없는 결정이 있었고, 처음 보는 사람에게 검토를 맡기자 차이 몇 개가 더 나왔습니다.

| 왜 추가했나 | 테스트 | 확인하는 것 |
|---|---|---|
| 결정에 테스트가 없었음 | `test_db_is_updated_before_cache_delete` | 캐시를 지우는 순간 DB는 이미 새 가격 (DB 먼저, 캐시 나중) |
| | `test_slow_mini_redis_times_out` | 연결만 받고 답하지 않는 mini-redis 앞에서 기다리지 않고 DB로 감, 기본 타임아웃 1초 |
| | `test_local_cache_expires_the_same_way` | 로컬 캐시도 mini-redis처럼 TTL이 지나면 만료 |
| | `test_session_expires_after_ttl` | 세션 TTL이 지나면 401 |
| 두 캐시의 동작이 달랐음 | `test_expired_key_delete_is_same_on_both_caches` | 만료된 키를 지우면 두 캐시 모두 `False` (고치기 전엔 로컬 캐시만 `True`) |
| 실제 네트워크 경로가 테스트되지 않았음 | `test_cache_aside_and_invalidation_over_http` | mini-redis를 실제 포트에 띄우고 `RedisCache`로 조회·무효화 |
| | `test_ttl_is_sent_over_http` | TTL이 네트워크 요청에 실려 mini-redis까지 가서 만료가 일어남 |
| | `test_session_over_http` | 실제 네트워크로 서버 A 로그인, 서버 B 확인, 로그아웃 |

처음 테스트는 서버를 띄우지 않으려고 mini-redis를 `test_client`로 흉내 냈습니다. 그래서 데모 API가 실제로 쓰는 `RedisCache`는 한 번도 테스트되지 않았고, 이를 메우려고 마지막 세 개를 만들었습니다.

## 3. 변이 검사: 테스트가 정말 일하는지

테스트가 모두 통과해도, 그 테스트가 설계 결정을 지키는지는 알 수 없습니다. 그래서 결정 하나씩 코드를 일부러 어긋나게 바꾸고(변이), 그 결정을 맡은 테스트가 실패하는지 봤습니다. `check_tests_catch_bugs.py`가 변이를 넣고, 테스트를 돌리고, 코드를 되돌리는 일을 자동으로 반복합니다.

| 망가뜨린 것 | 실패해야 하는 테스트 | 결과 |
|---|---|---|
| 가격 수정 후 캐시를 지우지 않음 | `test_price_update_invalidates_cache` | 잡음 |
| 캐시를 DB 수정보다 먼저 지움 | `test_db_is_updated_before_cache_delete` | 잡음 |
| 캐시 삭제가 실패하면 500을 돌려줌 | `test_write_still_succeeds` | 잡음 |
| `?nocache=1`이어도 캐시를 씀 | `test_nocache_skips_cache` | 잡음 |
| 통신 실패를 예외로 터뜨림 | `test_read_answers_from_db` | 잡음 |
| 타임아웃 기본값을 5초로 바꿈 | `test_slow_mini_redis_times_out` | 잡음 |
| 로컬 캐시가 TTL을 무시함 | `test_local_cache_expires_the_same_way` | 잡음 |
| 로컬 캐시가 만료된 키 삭제에 `True`를 돌려줌 | `test_expired_key_delete_is_same_on_both_caches` | 잡음 |
| 세션에 TTL을 주지 않음 | `test_session_expires_after_ttl` | 잡음 |
| `RedisCache.get`이 응답을 잘못 읽음 | `test_cache_aside_and_invalidation_over_http` | 잡음 |
| `RedisCache.delete`가 항상 `False` | `test_cache_aside_and_invalidation_over_http` | 잡음 |
| `RedisCache.set`이 TTL을 보내지 않음 | `test_ttl_is_sent_over_http` | 잡음 |

처음 돌렸을 때는 잡지 못한 변이가 있었습니다. 타임아웃 기본값을 바꿔도 테스트가 통과했고(테스트가 값을 덮어쓰고 있었음), `RedisCache`를 깨뜨려도 통과했습니다(실제 네트워크 경로를 테스트하지 않았음). 2절의 테스트로 메운 뒤 12가지를 모두 잡습니다.

## 성과

같은 변이 12가지를 테스트 파일의 세 시점에 돌려 비교했습니다.

| 시점 | `test_demo.py` 테스트 수 | 잡은 변이 | 잡지 못한 것 |
|---|---|---|---|
| 8·9단계를 처음 만들었을 때 | 14개 | **4 / 12** | DB 먼저 고치는 순서, 타임아웃, 로컬 캐시 만료, 만료 키 삭제 결과, 세션 TTL, `RedisCache` 조회·삭제·저장 |
| 결정과 테스트를 짝지어 빈 결정을 채운 뒤 | 17개 | **6 / 12** | 타임아웃 기본값, 만료 키 삭제 결과, 세션 TTL, `RedisCache` 조회·삭제·저장 |
| 처음 보는 검토자의 검토를 반영한 뒤 | 22개 | **12 / 12** | 없음 |

- 테스트가 모두 통과하던 처음 상태에서도, 설계 결정 12가지 중 8가지는 코드가 틀어져도 알아챌 수 없었습니다. "통과한다"와 "지킨다"는 다른 말이라는 걸 숫자로 확인했습니다.
- 가장 큰 빈칸은 실제 네트워크 경로였습니다. 배포된 주식 화면이 실제로 쓰는 `RedisCache`가 한 번도 테스트되지 않았고, mini-redis를 실제 포트에 띄우는 테스트 3개로 메웠습니다.
- 그 과정에서 코드 차이 하나(로컬 캐시의 만료 키 삭제 결과)와 README의 사실과 다른 설명 여러 곳을 찾아 고쳤습니다(4절).
- 전체 테스트는 63개에서 71개가 되었고, 데모 API 테스트 22개는 3초 안에 끝납니다.

## 4. 검토에서 고친 것

| 찾은 것 | 고친 것 |
|---|---|
| README에 "캐시 삭제를 빼면 로그아웃 테스트가 실패"라고 적혀 있었지만 사실이 아님 | 실제로 실패하는 테스트 이름으로 바꿈 |
| 로컬 캐시만 만료된 키 삭제에 `True`를 돌려줘 `cache_invalidated` 값이 달라짐 | `demo/cache.py`의 `LocalCache.delete`를 mini-redis와 같게 고침 |
| "mini-redis가 죽어도 기능 문제 없음"이 세션에는 맞지 않음 | README에 예외를 적고 「알고 남겨 둔 한계」 절을 추가 |
| 벤치마크 결과 표에 DB 지연이 항상 "3초"로 찍힘 | 실제 값을 받아 표시하고, mini-redis가 꺼져 있거나 로컬 캐시면 측정하지 않음 |

이 테스트와 검사는 Claude Code와 함께 설계하고 실행했습니다.
