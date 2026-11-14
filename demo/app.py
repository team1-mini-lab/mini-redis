"""8단계 데모 API: mini-redis를 DB 앞의 캐시로 쓴다 (Cache-Aside).

구조
    고객 → 데모 API(8001) → mini-redis(8000)  있으면 바로 응답
                         ↘ 가짜 DB (3초)      없으면 DB 조회 후 캐시에 저장

읽기(Cache-Aside): 캐시에 있으면 바로 반환(hit). 없으면 DB를 조회해 캐시에 저장하고 반환(miss).
쓰기(무효화):      DB를 고친 뒤 캐시 키를 지운다. 다음 읽기 때 새 값으로 채워진다.

왜 "지우기"인가: 캐시에 새 값을 덮어쓰는 방법도 있지만, 지우는 쪽이 단순하고 안전하다.
덮어쓰려면 "DB 수정"과 "캐시 수정" 두 번의 쓰기 순서가 어긋날 때 옛 값이 남을 수 있다.
지워 두면 다음 읽기가 반드시 DB에서 최신 값을 가져온다.

실행
    터미널 1:  python -m mini_redis.server      (mini-redis, 8000)
    터미널 2:  python -m demo.app               (데모 API, 8001)

서버 여러 대로 띄우기 (3차 체크인의 "서버가 여러 대가 되면?")
    python -m demo.app --port 8001
    python -m demo.app --port 8002              두 대가 같은 mini-redis, 같은 DB를 본다
    python -m demo.app --port 8003 --cache local   비교용: 캐시를 서버 안 dict에 둔다
"""
import argparse
import os
import time
import uuid

from flask import Flask, jsonify, request

from demo import db
from demo.cache import make_cache

app = Flask(__name__)
app.json.ensure_ascii = False

POPULAR_KEY = "popular_products"   # 접점 합의: 캐시 키 이름
# 접점 합의: TTL 60초. 시연 스크립트는 단계마다 멈춰 설명하는 사이 만료되지 않도록
# DEMO_CACHE_TTL로 길게 바꿔 쓴다.
POPULAR_TTL = float(os.environ.get("DEMO_CACHE_TTL", "60"))
POPULAR_LIMIT = 3

# 세션 보관 시간. 로그인 유지 시간이 그대로 TTL이 된다 (장면 ② 로그인이 풀림).
SESSION_TTL = float(os.environ.get("DEMO_SESSION_TTL", "1800"))   # 30분

# 실행할 때 main()에서 정한다. import만 했을 때(테스트 등)는 기본값을 쓴다.
PORT = int(os.environ.get("DEMO_PORT", "8001"))
cache = make_cache(os.environ.get("DEMO_CACHE", "redis"))


def _server_name():
    """응답에 넣을 서버 이름. 여러 대를 띄웠을 때 어느 서버가 답했는지 보여 준다."""
    return f"{PORT} ({cache.name})"


def _wants_cache():
    """?nocache=1이면 캐시를 건너뛴다. 9단계 성능 비교에서 "캐시 미사용"을 재는 데 쓴다.

    같은 코드 경로에서 캐시만 빼는 것이라, 캐시 말고 다른 조건은 똑같이 유지된다.
    """
    return request.args.get("nocache") != "1"


@app.get("/")
def health():
    """데모 API와 캐시가 모두 떠 있는지 알려 준다."""
    return jsonify({
        "message": "demo api is running",
        "server": _server_name(),
        "cache": cache.name,
        "cache_status": "up" if cache.ping() else "down",
    })


@app.get("/products/popular")
def popular_products():
    """인기 상품 조회. 캐시를 먼저 보고, 없으면 DB에서 가져와 캐시에 채운다.

    응답의 source로 캐시에서 왔는지(cache) DB에서 왔는지(db) 알 수 있다.
    두 번째 조회부터 source가 cache로 바뀌고 elapsed_ms가 크게 줄어든다 (완료 기준).
    """
    started = time.perf_counter()
    use_cache = _wants_cache()

    if use_cache:
        cached = cache.get(POPULAR_KEY)
        if cached is not None:                      # 캐시 히트
            return jsonify({
                "server": _server_name(),
                "source": "cache",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "products": cached,
            })

    products = db.get_popular_products(POPULAR_LIMIT)   # 캐시 미스 → 느린 DB 조회

    if use_cache:
        # TTL을 함께 준다. 무효화를 깜빡해도 60초 뒤에는 사라지므로 안전망이 된다.
        cache.set(POPULAR_KEY, products, ttl=POPULAR_TTL)

    return jsonify({
        "server": _server_name(),
        "source": "db" if use_cache else "db (nocache)",
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "products": products,
    })


@app.put("/products/<int:product_id>/price")
def update_price(product_id):
    """가격 수정: DB를 고치고 캐시를 지운다 (무효화).

    3차 체크인의 장면 ①이 여기서 해결된다. 로컬 캐시였다면 요청을 받은 서버만
    자기 캐시를 지울 수 있어서 다른 서버에는 옛 가격이 남는다 (--cache local로 확인).
    공용 저장소라면 키 하나를 지우는 것으로 캐시를 보는 모든 서버가 새 값을 본다.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "price" not in body:
        return jsonify({"error": "본문에 price가 필요합니다"}), 400

    price = body["price"]
    if isinstance(price, bool) or not isinstance(price, int) or price < 0:
        return jsonify({"error": "price는 0 이상의 정수여야 합니다"}), 400

    if not db.update_price(product_id, price):      # ① 원본을 먼저 고친다
        return jsonify({"error": "없는 상품입니다"}), 404

    invalidated = cache.delete(POPULAR_KEY)         # ② 그 다음 캐시를 지운다

    return jsonify({
        "server": _server_name(),
        "ok": True,
        "product": db.get_product(product_id),
        "cache_invalidated": invalidated,
    })


@app.get("/products/<int:product_id>")
def get_product(product_id):
    """상품 하나 조회. 가격이 바뀌었는지 확인하는 데 쓴다 (캐시를 쓰지 않음)."""
    product = db.get_product(product_id)
    if product is None:
        return jsonify({"error": "없는 상품입니다"}), 404
    return jsonify(product)


def _session_key(token):
    return f"session:{token}"


@app.post("/login")
def login():
    """로그인: 세션을 캐시에 저장하고 토큰을 돌려준다 (장면 ② 로그인이 풀림).

    세션도 결국 키-값이라 인기 상품과 똑같은 set / get을 쓴다. 따로 만든 기능이 없다.
    로컬 캐시라면 로그인을 받은 서버만 이 세션을 알고, 공용 저장소라면 어느 서버든 안다.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("user"), str) or not body["user"]:
        return jsonify({"error": "본문에 user가 필요합니다"}), 400

    token = uuid.uuid4().hex[:8]
    cache.set(_session_key(token), body["user"], ttl=SESSION_TTL)

    return jsonify({
        "server": _server_name(),
        "token": token,
        "user": body["user"],
        "ttl": SESSION_TTL,
    })


@app.get("/me")
def me():
    """내가 누구인지: /me?token=... 세션이 없거나 만료되면 401 (로그인이 풀린 상태).

    로그인을 서버 A로 했는데 이 요청이 서버 B로 갔을 때 무엇이 나오는지가 장면 ②다.
    """
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "token이 필요합니다"}), 400

    user = cache.get(_session_key(token))
    if user is None:
        return jsonify({"server": _server_name(), "error": "로그인이 필요합니다"}), 401

    return jsonify({"server": _server_name(), "user": user})


@app.post("/logout")
def logout():
    """로그아웃: 세션 키를 지운다. 공용 저장소라면 모든 서버에서 한 번에 풀린다."""
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "token이 필요합니다"}), 400
    return jsonify({"server": _server_name(), "logged_out": cache.delete(_session_key(token))})


@app.get("/stats")
def stats():
    """DB를 몇 번 조회했는지 (모든 서버 합계). 캐시가 DB를 얼마나 막아 줬는지 보여 준다."""
    return jsonify({"db_query_count": db.query_count()})


@app.post("/stats/reset")
def reset_stats():
    """측정을 시작할 때 DB 조회 횟수를 0으로 돌린다 (9단계용)."""
    db.reset_query_count()
    return jsonify({"ok": True, "db_query_count": db.query_count()})


@app.delete("/cache")
def clear_cache():
    """캐시를 비운다. 측정이나 시연을 처음부터 다시 할 때 쓴다."""
    return jsonify({"deleted": cache.delete(POPULAR_KEY)})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "없는 주소입니다"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "허용하지 않는 메서드입니다"}), 405


def main():
    global PORT, cache
    parser = argparse.ArgumentParser(description="mini-redis 데모 API")
    parser.add_argument("--port", type=int, default=PORT, help="포트 (기본 8001)")
    parser.add_argument(
        "--cache", choices=["redis", "local"], default=cache.name,
        help="redis: mini-redis를 HTTP로 사용 (기본) / local: 서버 안 dict (비교용)",
    )
    args = parser.parse_args()

    PORT = args.port
    cache = make_cache(args.cache)
    db.init()

    if args.cache == "redis" and not cache.ping():
        print("[경고] mini-redis(8000)가 떠 있지 않습니다. 먼저 실행하세요:")
        print("        python -m mini_redis.server")
    print(f"데모 API {_server_name()} 시작")
    # threaded=True: 요청마다 스레드를 따로 써서 동시에 처리한다. 한 요청이 DB에서
    # 3초 기다리는 동안 다른 요청(캐시 히트 등)이 줄 서서 기다리지 않게 한다.
    # Flask 1.0부터 기본값이 True라 없어도 같지만, 의도를 보이려고 적어 둔다.
    app.run(host="127.0.0.1", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
