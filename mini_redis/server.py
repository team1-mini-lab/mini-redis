"""mini-redis HTTP API. 요청을 검증한 뒤 저장소를 호출하고 JSON으로 응답한다."""
from flask import Flask, jsonify, request

from mini_redis.store import Store

app = Flask(__name__)
app.json.ensure_ascii = False
store = Store()

HOST = "127.0.0.1"
PORT = 8000
SET_FIELDS = {"key", "value", "ttl"}
MAX_TTL = 10 * 365 * 24 * 60 * 60


@app.get("/")
def health():
    return jsonify({"message": "mini-redis is running"})


@app.post("/set")
def set_value():
    body = request.get_json(silent=True)
    error = find_set_body_error(body)
    if error:
        return bad_request(error)
    store.set(body["key"], body["value"], body.get("ttl"))
    return jsonify({"ok": True})


@app.get("/get")
def get_value():
    key = request.args.get("key")
    error = find_key_error(key)
    if error:
        return bad_request(error)
    value = store.get(key)
    if value is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"key": key, "value": value})


@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    error = find_key_error(key)
    if error:
        return bad_request(error)
    return jsonify({"deleted": store.delete(key)})


@app.errorhandler(404)
def unknown_path(error):
    return jsonify({"error": "없는 주소입니다"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "허용하지 않는 메서드입니다"}), 405


def bad_request(message):
    return jsonify({"error": message}), 400


def find_set_body_error(body):
    """처음 발견한 오류의 설명을 돌려준다. 문제가 없으면 None."""
    if not isinstance(body, dict):
        return "요청 본문은 JSON 객체여야 합니다"
    if "key" not in body or "value" not in body:
        return "key와 value가 필요합니다"
    unknown_fields = body.keys() - SET_FIELDS
    if unknown_fields:
        return f"알 수 없는 항목입니다: {', '.join(sorted(unknown_fields))}"
    return (
        find_key_error(body["key"])
        or find_value_error(body["value"])
        or find_ttl_error(body.get("ttl"))
    )


def find_key_error(key):
    if key is None:
        return "key가 필요합니다"
    if not isinstance(key, str):
        return "key는 문자열이어야 합니다"
    if key == "":
        return "key는 비어 있으면 안 됩니다"
    return None


def find_value_error(value):
    # 저장소의 get이 돌려주는 None은 "없는 키"를 뜻하므로 값으로는 받지 않는다.
    if value is None:
        return "value로 null은 저장할 수 없습니다"
    return None


def find_ttl_error(ttl):
    ttl_is_omitted = ttl is None
    if ttl_is_omitted or (is_number(ttl) and is_within_ttl_range(ttl)):
        return None
    return f"ttl은 0보다 크고 {MAX_TTL} 이하인 숫자(초)여야 합니다"


def is_number(value):
    # bool은 int의 하위 타입이라 따로 걸러야 true가 1로 통과하지 않는다.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_within_ttl_range(ttl):
    # NaN과 Infinity도 이 비교 하나로 걸러진다.
    return 0 < ttl <= MAX_TTL


if __name__ == "__main__":
    app.run(host=HOST, port=PORT)
