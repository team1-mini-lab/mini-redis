"""변이 검사: 코드를 일부러 망가뜨렸을 때 테스트가 정말 잡아내는지 확인한다.

테스트가 모두 통과해도, 그 테스트가 설계 결정을 실제로 지키는지는 알 수 없다.
그래서 설계 결정 하나씩 코드를 어긋나게 바꾸고(변이), 그 결정을 맡은 테스트가
실패하는지 본다. 실패하면 "잡았다", 그래도 통과하면 테스트에 빈틈이 있다는 뜻이다.
바꾼 파일은 매번 원래대로 되돌린다.

    python docs/eungi/check_tests_catch_bugs.py      (저장소 맨 위 폴더에서)

결과와 각 변이의 뜻은 같은 폴더의 TEST_RECORD.md에 정리되어 있다.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]   # docs/eungi/ → 저장소 맨 위

# (설계 결정, 파일, 바꿀 코드, 망가뜨린 코드, 실패해야 하는 테스트)
MUTATIONS = [
    (
        "수정하면 캐시를 지움 (무효화)",
        "demo/app.py",
        "    cache_invalidated = invalidate_top_stocks()\n",
        "    cache_invalidated = True\n",
        "test_price_update_invalidates_cache",
    ),
    (
        "DB를 먼저 고치고 그다음 캐시를 지움",
        "demo/app.py",
        '    if not db.update_price(stock_id, body["price"]):\n'
        '        return not_found("없는 종목입니다")\n'
        "    cache_invalidated = invalidate_top_stocks()\n",
        "    cache_invalidated = invalidate_top_stocks()\n"
        '    if not db.update_price(stock_id, body["price"]):\n'
        '        return not_found("없는 종목입니다")\n',
        "test_db_is_updated_before_cache_delete",
    ),
    (
        "캐시 삭제가 실패해도 가격 수정은 성공",
        "demo/app.py",
        "    cache_invalidated = invalidate_top_stocks()\n",
        "    cache_invalidated = invalidate_top_stocks()\n"
        "    if not cache_invalidated:\n"
        '        return jsonify({"error": "cache"}), 500\n',
        "test_write_still_succeeds",
    ),
    (
        "?nocache=1은 캐시를 쓰지 않음",
        "demo/app.py",
        "    if cache_is_bypassed():\n",
        "    if False:\n",
        "test_nocache_skips_cache",
    ),
    (
        "mini-redis가 죽어도 DB로 응답",
        "demo/cache.py",
        "            if warn_on_failure:\n                self._warn_once(error)\n            return None\n",
        "            raise\n",
        "test_read_answers_from_db",
    ),
    (
        "mini-redis 호출 타임아웃",
        "demo/cache.py",
        "    TIMEOUT_SECONDS = 1.0",
        "    TIMEOUT_SECONDS = 5.0",
        "test_slow_mini_redis_times_out",
    ),
    (
        "로컬 캐시도 같은 방식으로 만료",
        "demo/cache.py",
        "expire_at = None if ttl is None else time.monotonic() + ttl",
        "expire_at = None",
        "test_local_cache_expires_the_same_way",
    ),
    (
        "만료된 키 삭제는 두 캐시가 같음",
        "demo/cache.py",
        "            return entry is not None and not _is_expired(entry[1])\n",
        "            return entry is not None\n",
        "test_expired_key_delete_is_same_on_both_caches",
    ),
    (
        "세션 TTL = 로그인 유지 시간",
        "demo/app.py",
        "    cache.set(session_key(token), user, ttl=SESSION_TTL)\n",
        "    cache.set(session_key(token), user)\n",
        "test_session_expires_after_ttl",
    ),
    (
        "HTTP 조회 경로 (RedisCache.get)",
        "demo/cache.py",
        'return response.json()["value"]',
        'return response.json()["val"]',
        "test_cache_aside_and_invalidation_over_http",
    ),
    (
        "HTTP 삭제 경로 (RedisCache.delete)",
        "demo/cache.py",
        'return response.json().get("deleted", False)',
        'return False',
        "test_cache_aside_and_invalidation_over_http",
    ),
    (
        "HTTP 저장 경로 (RedisCache.set)",
        "demo/cache.py",
        'body["ttl"] = ttl',
        'pass',
        "test_ttl_is_sent_over_http",
    ),
]


def run_demo_tests():
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_demo"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    return result.returncode == 0, result.stderr


def check(decision, path, original, broken, expected_test):
    file = ROOT / path
    source = file.read_text(encoding="utf-8")
    if original not in source:
        return "코드를 못 찾음"
    file.write_text(source.replace(original, broken, 1), encoding="utf-8")
    try:
        passed, output = run_demo_tests()
    finally:
        file.write_text(source, encoding="utf-8")
    if passed:
        return "놓침"
    failed_lines = [line for line in output.splitlines() if line.startswith(("FAIL:", "ERROR:"))]
    if any(expected_test in line for line in failed_lines):
        return "잡음"
    return "다른 테스트가 잡음"


def main():
    passed, _ = run_demo_tests()
    if not passed:
        print("원래 코드에서 테스트가 실패합니다. 먼저 고치고 다시 실행하세요.")
        sys.exit(1)

    print(f"{'설계 결정':<28} {'실패해야 하는 테스트':<42} 결과")
    print("-" * 80)
    misses = 0
    for decision, path, original, broken, expected_test in MUTATIONS:
        outcome = check(decision, path, original, broken, expected_test)
        misses += outcome != "잡음"
        print(f"{decision:<28} {expected_test:<42} {outcome}")
    print("-" * 80)
    print(f"{len(MUTATIONS)}개 중 {len(MUTATIONS) - misses}개를 테스트가 잡았습니다.")
    sys.exit(1 if misses else 0)


if __name__ == "__main__":
    main()
