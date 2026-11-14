"""데모 API: mini-redis를 DB 앞의 캐시로 쓴다 (Cache-Aside).

    고객 → 데모 API(8001) → 캐시(mini-redis, 8000)  있으면 바로 응답
                          ↘ DB (느림)               없으면 조회해서 캐시에 채움

읽기: 캐시에 있으면 그대로 응답하고, 없으면 DB에서 가져와 캐시에 넣는다.
쓰기: DB를 고친 뒤 캐시 키를 지운다. 새 값은 다음 읽기가 DB에서 가져와 채운다.
      캐시에 새 값을 덮어쓰지 않는 이유는, DB 쓰기와 캐시 쓰기의 순서가 어긋나면
      옛 값이 남을 수 있기 때문이다.
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

HOST = "127.0.0.1"
PORT = int(os.environ.get("DEMO_PORT", "8001"))
cache = make_cache(os.environ.get("DEMO_CACHE", "redis"))

POPULAR_KEY = "popular_products"
POPULAR_LIMIT = 3
POPULAR_TTL = float(os.environ.get("DEMO_CACHE_TTL", "60"))
SESSION_TTL = float(os.environ.get("DEMO_SESSION_TTL", "1800"))
SESSION_TOKEN_LENGTH = 8


@app.get("/")
def health():
    return jsonify({
        "message": "demo api is running",
        "server": server_name(),
        "cache": cache.name,
        "cache_status": "up" if cache.ping() else "down",
    })


@app.get("/products/popular")
def popular_products():
    started = time.perf_counter()
    if cache_is_bypassed():
        products, source = db.get_popular_products(POPULAR_LIMIT), "db (nocache)"
    else:
        products, source = read_popular_products_through_cache()
    return jsonify({
        "server": server_name(),
        "source": source,
        "elapsed_ms": elapsed_ms_since(started),
        "products": products,
    })


@app.put("/products/<int:product_id>/price")
def update_price(product_id):
    body = request.get_json(silent=True)
    error = find_price_error(body)
    if error:
        return bad_request(error)
    if not db.update_price(product_id, body["price"]):
        return not_found("없는 상품입니다")
    cache_invalidated = invalidate_popular_products()
    return jsonify({
        "server": server_name(),
        "ok": True,
        "product": db.get_product(product_id),
        "cache_invalidated": cache_invalidated,
    })


@app.get("/products/<int:product_id>")
def get_product(product_id):
    product = db.get_product(product_id)
    if product is None:
        return not_found("없는 상품입니다")
    return jsonify(product)


@app.post("/login")
def login():
    body = request.get_json(silent=True)
    error = find_user_error(body)
    if error:
        return bad_request(error)
    user = body["user"]
    token = new_session_token()
    cache.set(session_key(token), user, ttl=SESSION_TTL)
    return jsonify({"server": server_name(), "token": token, "user": user, "ttl": SESSION_TTL})


@app.get("/me")
def me():
    token = token_from_query()
    if not token:
        return bad_request("token이 필요합니다")
    user = cache.get(session_key(token))
    if user is None:
        return jsonify({"server": server_name(), "error": "로그인이 필요합니다"}), 401
    return jsonify({"server": server_name(), "user": user})


@app.post("/logout")
def logout():
    token = token_from_query()
    if not token:
        return bad_request("token이 필요합니다")
    return jsonify({"server": server_name(), "logged_out": cache.delete(session_key(token))})


@app.get("/stats")
def stats():
    return jsonify({"db_query_count": db.query_count()})


@app.post("/stats/reset")
def reset_stats():
    db.reset_query_count()
    return jsonify({"ok": True, "db_query_count": db.query_count()})


@app.delete("/cache")
def clear_cache():
    return jsonify({"deleted": invalidate_popular_products()})


@app.errorhandler(404)
def unknown_path(error):
    return not_found("없는 주소입니다")


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "허용하지 않는 메서드입니다"}), 405


def read_popular_products_through_cache():
    """(상품 목록, 가져온 곳)을 돌려준다. 가져온 곳은 "cache" 또는 "db"."""
    cached = cache.get(POPULAR_KEY)
    if cached is not None:
        return cached, "cache"
    products = db.get_popular_products(POPULAR_LIMIT)
    # 무효화를 놓쳐도 TTL이 지나면 낡은 값이 사라진다.
    cache.set(POPULAR_KEY, products, ttl=POPULAR_TTL)
    return products, "db"


def invalidate_popular_products():
    return cache.delete(POPULAR_KEY)


def cache_is_bypassed():
    return request.args.get("nocache") == "1"


def find_price_error(body):
    if not isinstance(body, dict) or "price" not in body:
        return "본문에 price가 필요합니다"
    if not is_non_negative_integer(body["price"]):
        return "price는 0 이상의 정수여야 합니다"
    return None


def is_non_negative_integer(value):
    # bool은 int의 하위 타입이라 따로 걸러야 true가 1로 통과하지 않는다.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def find_user_error(body):
    if not isinstance(body, dict) or not isinstance(body.get("user"), str) or not body["user"]:
        return "본문에 user가 필요합니다"
    return None


def new_session_token():
    return uuid.uuid4().hex[:SESSION_TOKEN_LENGTH]


def session_key(token):
    return f"session:{token}"


def token_from_query():
    return request.args.get("token", "")


def server_name():
    return f"{PORT} ({cache.name})"


def elapsed_ms_since(started):
    return round((time.perf_counter() - started) * 1000, 1)


def bad_request(message):
    return jsonify({"error": message}), 400


def not_found(message):
    return jsonify({"error": message}), 404


def main():
    global PORT, cache
    args = parse_arguments()
    PORT = args.port
    cache = make_cache(args.cache)
    db.init()
    warn_if_mini_redis_is_down()
    print(f"데모 API {server_name()} 시작")
    # 느린 DB 조회 하나가 다른 요청을 줄 세우지 않도록 요청마다 스레드를 쓴다.
    app.run(host=HOST, port=PORT, threaded=True)


def parse_arguments():
    parser = argparse.ArgumentParser(description="mini-redis 데모 API")
    parser.add_argument("--port", type=int, default=PORT, help="포트 (기본 8001)")
    parser.add_argument(
        "--cache", choices=["redis", "local"], default=cache.name,
        help="redis: mini-redis를 HTTP로 사용 (기본) / local: 서버 안 dict (비교용)",
    )
    return parser.parse_args()


def warn_if_mini_redis_is_down():
    if cache.name == "redis" and not cache.ping():
        print("[경고] mini-redis(8000)가 떠 있지 않습니다. 먼저 실행하세요:")
        print("        python -m mini_redis.server")


if __name__ == "__main__":
    main()
