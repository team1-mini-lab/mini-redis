"""9단계 성능 비교: 캐시를 썼을 때와 안 썼을 때의 응답 시간을 잰다.

재는 방법
    캐시 미사용:  /products/popular?nocache=1 을 N번 — 매번 DB로 간다
    캐시 사용:    /products/popular 을 N번 — 첫 번째만 DB(미스), 나머지는 캐시(히트)

캐시 사용 쪽은 첫 조회와 이후 조회를 따로 적는다. 둘을 섞어 평균을 내면
"캐시를 쓰면 평균 몇 ms"라는 숫자가 N에 따라 달라져서 아무 뜻이 없어진다.
첫 조회는 원래 느린 것이 맞고(캐시에 아직 없으니), 캐시의 효과는 그 다음부터 나온다.

응답 시간 외에 DB 조회 횟수도 함께 적는다. 캐시의 원래 목적이 DB 보호라서,
"몇 배 빨라졌나"보다 "DB 요청을 몇 건 막았나"가 더 중요한 숫자다.

실행
    터미널 1:  python -m mini_redis.server
    터미널 2:  python -m demo.app
    터미널 3:  python -m bench.benchmark            (기본 10회)
               python -m bench.benchmark -n 20      (20회)
               python -m bench.benchmark --markdown (README에 붙일 표로 출력)
"""
import argparse
import statistics
import sys
import time

import requests

DEMO_URL = "http://127.0.0.1:8001"
TIMEOUT = 30.0        # DB 지연이 3초라 넉넉히 둔다


def _request(nocache):
    """인기 상품을 한 번 조회하고 (걸린 시간 ms, source)를 돌려준다.

    시간은 클라이언트 쪽에서 잰다. 고객이 실제로 기다리는 시간이기 때문이다.
    (서버가 돌려주는 elapsed_ms는 서버 안에서만 잰 시간이라 네트워크가 빠진다)
    """
    params = {"nocache": "1"} if nocache else None
    started = time.perf_counter()
    response = requests.get(f"{DEMO_URL}/products/popular", params=params, timeout=TIMEOUT)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return elapsed_ms, response.json()["source"]


def _reset():
    """캐시를 비우고 DB 조회 횟수를 0으로 돌린다."""
    requests.delete(f"{DEMO_URL}/cache", timeout=TIMEOUT)
    requests.post(f"{DEMO_URL}/stats/reset", timeout=TIMEOUT)


def _db_query_count():
    return requests.get(f"{DEMO_URL}/stats", timeout=TIMEOUT).json()["db_query_count"]


def _summary(samples):
    """측정값 목록에서 평균·최소·최대를 뽑는다."""
    return {
        "count": len(samples),
        "avg": statistics.mean(samples),
        "min": min(samples),
        "max": max(samples),
    }


def run(n):
    """두 경우를 각각 N번 재고 결과를 돌려준다."""
    print(f"측정 시작 (각 {n}회)\n")

    # ── 캐시 미사용: 매번 DB ────────────────────────────────
    _reset()
    print("[1/2] 캐시 미사용", end="", flush=True)
    nocache_samples = []
    for _ in range(n):
        elapsed, _source = _request(nocache=True)
        nocache_samples.append(elapsed)
        print(".", end="", flush=True)
    nocache_queries = _db_query_count()
    print(f" 완료 (DB 조회 {nocache_queries}회)")

    # ── 캐시 사용: 첫 번째만 미스 ───────────────────────────
    _reset()
    print("[2/2] 캐시 사용  ", end="", flush=True)
    miss_elapsed, miss_source = _request(nocache=False)
    print("M", end="", flush=True)          # M = 미스
    hit_samples = []
    for _ in range(n - 1):
        elapsed, source = _request(nocache=False)
        hit_samples.append(elapsed)
        print("." if source == "cache" else "M", end="", flush=True)
    cache_queries = _db_query_count()
    print(f" 완료 (DB 조회 {cache_queries}회)")

    if miss_source != "db":
        print(f"\n[경고] 첫 조회가 캐시에서 나왔습니다(source={miss_source}). "
              "캐시가 비워지지 않은 것 같습니다.", file=sys.stderr)

    return {
        "n": n,
        "nocache": _summary(nocache_samples),
        "nocache_queries": nocache_queries,
        "miss": miss_elapsed,
        "hit": _summary(hit_samples) if hit_samples else None,
        "cache_queries": cache_queries,
    }


def print_table(result):
    """사람이 읽는 표."""
    nocache = result["nocache"]
    hit = result["hit"]

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

    if hit and hit["avg"] > 0:
        print(f"  캐시 히트가 DB 조회보다 {nocache['avg'] / hit['avg']:,.0f}배 빠름")
    print(f"  DB 조회 횟수: 미사용 {result['nocache_queries']}회 → "
          f"사용 {result['cache_queries']}회 "
          f"({result['nocache_queries'] - result['cache_queries']}건 막음)")
    print("=" * 62)


def print_markdown(result):
    """README에 그대로 붙일 수 있는 표."""
    nocache = result["nocache"]
    hit = result["hit"]

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
    if hit and hit["avg"] > 0:
        print(f"- 캐시 히트는 DB 조회보다 약 **{nocache['avg'] / hit['avg']:,.0f}배** 빠릅니다.")
    print(f"- DB 조회 횟수가 {result['nocache_queries']}회에서 "
          f"{result['cache_queries']}회로 줄어, "
          f"{result['nocache_queries'] - result['cache_queries']}건을 막았습니다.")
    print("- 첫 조회는 캐시에 값이 없어 느린 것이 정상입니다. 캐시의 효과는 그 다음부터 나옵니다.")
    print()


def main():
    parser = argparse.ArgumentParser(description="캐시 사용/미사용 응답 시간 비교")
    parser.add_argument("-n", type=int, default=10, help="각 경우를 몇 번 조회할지 (기본 10)")
    parser.add_argument("--markdown", action="store_true", help="README용 표로 출력")
    args = parser.parse_args()

    if args.n < 2:
        parser.error("-n은 2 이상이어야 합니다 (캐시 사용 쪽에 미스와 히트가 모두 있어야 함)")

    try:
        requests.get(f"{DEMO_URL}/", timeout=2).raise_for_status()
    except requests.RequestException:
        print(f"데모 API({DEMO_URL})에 연결할 수 없습니다. 먼저 실행하세요:", file=sys.stderr)
        print("  python -m mini_redis.server   (터미널 1)", file=sys.stderr)
        print("  python -m demo.app            (터미널 2)", file=sys.stderr)
        sys.exit(1)

    result = run(args.n)
    if args.markdown:
        print_markdown(result)
    else:
        print_table(result)


if __name__ == "__main__":
    main()
