"""서버 모듈: HTTP 요청을 받아 저장소 함수를 호출하고 JSON으로 응답한다 (접점 2).

6단계: 입력 검증. 규칙을 어긴 요청은 저장소에 닿기 전에 여기서 400으로 돌려보낸다.
검증 방식은 현지님(hnjee 브랜치 server.py)을 참고했고, 없는 주소와 잘못된 메서드를
JSON으로 응답하는 부분은 은기님(eungi 브랜치 server.py)을 참고했다.
"""
from flask import Flask, jsonify, request

from mini_redis.store import Store

app = Flask(__name__)
app.json.ensure_ascii = False  # 응답의 한글을 그대로 보여 준다
store = Store()

SET_FIELDS = {"key", "value", "ttl"}   # /set 본문에 올 수 있는 칸
MAX_TTL = 10 * 365 * 24 * 60 * 60      # ttl 상한: 10년(초)


def check_key(key):
    """키가 올바르면 None, 아니면 오류 설명을 돌려준다."""
    if key is None:
        return "key가 필요합니다"
    if not isinstance(key, str):
        return "key는 문자열이어야 합니다"
    if key == "":                       # 공백 " "은 받아 준다 (엄연한 문자열)
        return "key는 비어 있으면 안 됩니다"
    return None


def check_ttl(ttl):
    """ttl이 올바르면 None, 아니면 오류 설명을 돌려준다. None(생략)은 만료 없음."""
    if ttl is None:
        return None
    # bool은 int의 한 종류라 먼저 막는다 (true가 1초로 통과하지 않게).
    # 범위 비교 한 줄로 0 이하, NaN, Infinity, 10년 초과를 모두 막는다. 소수(1.5)는 허용.
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not (0 < ttl <= MAX_TTL):
        return f"ttl은 0보다 크고 {MAX_TTL} 이하인 숫자(초)여야 합니다"
    return None


def check_set_body(body):
    """/set 본문이 올바르면 None, 아니면 처음 발견한 오류 설명을 돌려준다.

    확인 순서: 모양(JSON 객체인가) → 빠진 칸 → 모르는 칸 → key → value → ttl
    """
    if not isinstance(body, dict):
        return "요청 본문은 JSON 객체여야 합니다"
    if "key" not in body or "value" not in body:
        return "key와 value가 필요합니다"
    unknown = body.keys() - SET_FIELDS
    if unknown:
        return f"알 수 없는 항목입니다: {', '.join(sorted(unknown))}"
    error = check_key(body["key"])
    if error:
        return error
    if body["value"] is None:           # get의 None(없음)과 구분할 수 없으므로 막는다
        return "value로 null은 저장할 수 없습니다"
    return check_ttl(body.get("ttl"))


def bad_request(message):
    return jsonify({"error": message}), 400


@app.get("/")
def health():
    """0단계: 서버가 떠 있는지 확인하는 응답 하나."""
    return jsonify({"message": "mini-redis is running"})


@app.post("/set")
def set_value():
    """저장: 본문 {"key": ..., "value": ..., "ttl": ...}"""
    body = request.get_json(silent=True)  # JSON이 아니면 오류 대신 None을 받아 400으로 처리
    error = check_set_body(body)
    if error:
        return bad_request(error)
    store.set(body["key"], body["value"], body.get("ttl"))
    return jsonify({"ok": True})


@app.get("/get")
def get_value():
    """조회: /get?key=name. 없거나 만료되면 404."""
    key = request.args.get("key")
    error = check_key(key)
    if error:
        return bad_request(error)
    value = store.get(key)
    if value is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"key": key, "value": value})


@app.delete("/delete")
def delete_value():
    """삭제: /delete?key=name. 없는 키여도 200, deleted만 false."""
    key = request.args.get("key")
    error = check_key(key)
    if error:
        return bad_request(error)
    return jsonify({"deleted": store.delete(key)})


@app.errorhandler(404)
def not_found(error):
    """없는 주소도 HTML 대신 JSON으로 알린다."""
    return jsonify({"error": "없는 주소입니다"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """주소는 맞지만 메서드가 틀린 요청(예: GET /set)도 JSON으로 알린다."""
    return jsonify({"error": "허용하지 않는 메서드입니다"}), 405


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
