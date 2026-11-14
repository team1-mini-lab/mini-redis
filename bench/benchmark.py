"""성능 비교: 인기 상품 조회를 캐시 없이 N번, 캐시를 써서 N번 보내고 응답 시간을 잰다.

캐시를 쓰는 쪽은 첫 조회(미스)와 이후 조회(히트)를 따로 적는다. 둘을 섞어 평균을 내면
N에 따라 숫자가 달라져 뜻이 없어진다. 응답 시간과 함께 DB 조회 횟수도 적는다.

    터미널 1:  python -m mini_redis.server
    터미널 2:  python -m demo.app
    터미널 3:  python -m bench.benchmark            (기본 10회)
               python -m bench.benchmark -n 20
               python -m bench.benchmark --markdown (README에 붙일 표)
"""
import argparse
import statistics
import sys
import time

import requests

DEMO_URL = "http://127.0.0.1:8001"
TIMEOUT_SECONDS = 30.0
MIN_REQUESTS = 2


def main():
    args = parse_arguments()
    exit_if_demo_api_is_down()
    result = measure(args.n)
    if args.markdown:
        print_markdown_table(result)
    else:
        print_terminal_table(result)


def parse_arguments():
    parser = argparse.ArgumentParser(description="캐시 사용/미사용 응답 시간 비교")
    parser.add_argument("-n", type=int, default=10, help="각 경우를 몇 번 조회할지 (기본 10)")
    parser.add_argument("--markdown", action="store_true", help="README용 표로 출력")
    args = parser.parse_args()
    if args.n < MIN_REQUESTS:
        parser.error("-n은 2 이상이어야 합니다 (캐시 사용 쪽에 미스와 히트가 모두 있어야 함)")
    return args


def exit_if_demo_api_is_down():
    try:
        requests.get(f"{DEMO_URL}/", timeout=2).raise_for_status()
    except requests.RequestException:
        print(f"데모 API({DEMO_URL})에 연결할 수 없습니다. 먼저 실행하세요:", file=sys.stderr)
        print("  python -m mini_redis.server   (터미널 1)", file=sys.stderr)
        print("  python -m demo.app            (터미널 2)", file=sys.stderr)
        sys.exit(1)


def measure(request_count):
    print(f"측정 시작 (각 {request_count}회)\n")
    without_cache_times, without_cache_db_queries = measure_without_cache(request_count)
    miss_time, hit_times, with_cache_db_queries = measure_with_cache(request_count)
    return {
        "n": request_count,
        "nocache": summarize(without_cache_times),
        "nocache_queries": without_cache_db_queries,
        "miss": miss_time,
        "hit": summarize(hit_times) if hit_times else None,
        "cache_queries": with_cache_db_queries,
    }


def measure_without_cache(request_count):
    """(응답 시간 목록, DB 조회 횟수)"""
    clear_cache_and_db_query_count()
    print("[1/2] 캐시 미사용", end="", flush=True)
    elapsed_times = []
    for _ in range(request_count):
        elapsed_ms, _ = request_popular_products(use_cache=False)
        elapsed_times.append(elapsed_ms)
        print_progress(".")
    db_queries = db_query_count()
    print(f" 완료 (DB 조회 {db_queries}회)")
    return elapsed_times, db_queries


def measure_with_cache(request_count):
    """(첫 조회 시간, 이후 조회 시간 목록, DB 조회 횟수)"""
    clear_cache_and_db_query_count()
    print("[2/2] 캐시 사용  ", end="", flush=True)
    miss_time, first_source = request_popular_products(use_cache=True)
    print_progress("M")
    hit_times = []
    for _ in range(request_count - 1):
        elapsed_ms, source = request_popular_products(use_cache=True)
        hit_times.append(elapsed_ms)
        print_progress("." if source == "cache" else "M")
    db_queries = db_query_count()
    print(f" 완료 (DB 조회 {db_queries}회)")
    warn_if_first_request_was_not_a_miss(first_source)
    return miss_time, hit_times, db_queries


def request_popular_products(use_cache):
    """(응답 시간 ms, 가져온 곳). 고객이 기다리는 시간을 재려고 클라이언트 쪽에서 잰다."""
    params = None if use_cache else {"nocache": "1"}
    started = time.perf_counter()
    response = requests.get(f"{DEMO_URL}/products/popular", params=params, timeout=TIMEOUT_SECONDS)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return elapsed_ms, response.json()["source"]


def clear_cache_and_db_query_count():
    requests.delete(f"{DEMO_URL}/cache", timeout=TIMEOUT_SECONDS)
    requests.post(f"{DEMO_URL}/stats/reset", timeout=TIMEOUT_SECONDS)


def db_query_count():
    return requests.get(f"{DEMO_URL}/stats", timeout=TIMEOUT_SECONDS).json()["db_query_count"]


def print_progress(mark):
    print(mark, end="", flush=True)


def warn_if_first_request_was_not_a_miss(first_source):
    if first_source != "db":
        print(f"\n[경고] 첫 조회가 캐시에서 나왔습니다(source={first_source}). "
              "캐시가 비워지지 않은 것 같습니다.", file=sys.stderr)


def summarize(elapsed_times):
    return {
        "count": len(elapsed_times),
        "avg": statistics.mean(elapsed_times),
        "min": min(elapsed_times),
        "max": max(elapsed_times),
    }


def speedup(result):
    """캐시 히트가 캐시 미사용보다 몇 배 빠른지. 잴 수 없으면 None."""
    hit = result["hit"]
    if not hit or hit["avg"] <= 0:
        return None
    return result["nocache"]["avg"] / hit["avg"]


def blocked_db_queries(result):
    return result["nocache_queries"] - result["cache_queries"]


def print_terminal_table(result):
    nocache, hit = result["nocache"], result["hit"]
    print("\n" + "=" * 62)
    print(f"  인기 상품 조회 성능 비교 (각 {result['n']}회)")
    print("=" * 62)
    print(f"  {'경우':<22}{'평균':>10}{'최소':>10}{'최대':>10}")
    print("  " + "-" * 58)
    print(f"  {'캐시 미사용 (매번 DB)':<20}{nocache['avg']:>9.1f}ms"
          f"{nocache['min']:>9.1f}ms{nocache['max']:>9.1f}ms")
    print(f"  {'캐시 사용 - 첫 조회(미스)':<19}{result['miss']:>9.1f}ms{'-':>11}{'-':>11}")
    if hit:
        print(f"  {'캐시 사용 - 이후(히트)':<20}{hit['avg']:>9.1f}ms"
              f"{hit['min']:>9.1f}ms{hit['max']:>9.1f}ms")
    print("  " + "-" * 58)
    if speedup(result):
        print(f"  캐시 히트가 DB 조회보다 {speedup(result):,.0f}배 빠름")
    print(f"  DB 조회 횟수: 미사용 {result['nocache_queries']}회 → "
          f"사용 {result['cache_queries']}회 "
          f"({blocked_db_queries(result)}건 막음)")
    print("=" * 62)


def print_markdown_table(result):
    nocache, hit = result["nocache"], result["hit"]
    print()
    print(f"각 {result['n']}회 측정. 가짜 DB 지연 3초, 캐시 TTL 60초.")
    print()
    print("| 경우 | 평균 | 최소 | 최대 |")
    print("| --- | --- | --- | --- |")
    print(f"| 캐시 미사용 (매번 DB) | {nocache['avg']:.1f}ms "
          f"| {nocache['min']:.1f}ms | {nocache['max']:.1f}ms |")
    print(f"| 캐시 사용 — 첫 조회(미스) | {result['miss']:.1f}ms | - | - |")
    if hit:
        print(f"| 캐시 사용 — 이후(히트) | {hit['avg']:.1f}ms "
              f"| {hit['min']:.1f}ms | {hit['max']:.1f}ms |")
    print()
    if speedup(result):
        print(f"- 캐시 히트는 DB 조회보다 약 **{speedup(result):,.0f}배** 빠릅니다.")
    print(f"- DB 조회 횟수가 {result['nocache_queries']}회에서 "
          f"{result['cache_queries']}회로 줄어, "
          f"{blocked_db_queries(result)}건을 막았습니다.")
    print("- 첫 조회는 캐시에 값이 없어 느린 것이 정상입니다. 캐시의 효과는 그 다음부터 나옵니다.")
    print()


if __name__ == "__main__":
    main()
