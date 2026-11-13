from flask import Flask, request

from store import Store

app = Flask(__name__)
app.json.ensure_ascii = False  # 응답의 한글을 그대로 보여 줌

store = Store()

SET_FIELDS = {"key", "value", "ttl"}  # /set 본문에 올 수 있는 항목
MAX_TTL = 10 * 365 * 24 * 60 * 60  # ttl의 최댓값: 10년(초)


def check_key(key):
    """키가 올바르면 None, 아니면 오류 설명을 돌려줌"""
    if key is None:
        return "key가 필요합니다"
    if not isinstance(key, str):
        return "key는 문자열이어야 합니다"
    if key == "":
        return "key는 비어 있으면 안 됩니다"
    return None


def check_ttl(ttl):
    """ttl이 올바르면 None, 아니면 오류 설명을 돌려줌. None(생략)은 만료 없음"""
    if ttl is None:
        return None
    # bool은 int의 한 종류라 먼저 막음. 범위 비교 하나로 0 이하, NaN, Infinity, 너무 큰 수를 모두 막음
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not (0 < ttl <= MAX_TTL):
        return f"ttl은 0보다 크고 {MAX_TTL} 이하인 숫자(초)여야 합니다"
    return None


def check_set_body(body):
    """/set 본문이 올바르면 None, 아니면 처음 발견한 오류 설명을 돌려줌"""
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
    if body["value"] is None:
        return "value로 null은 저장할 수 없습니다"
    return check_ttl(body.get("ttl"))


@app.get("/")
def index():
    return {"message": "mini-redis is running"}


@app.post("/set")
def set_value():
    body = request.get_json(silent=True)
    error = check_set_body(body)
    if error:
        return {"error": error}, 400

    store.set(body["key"], body["value"], body.get("ttl"))
    return {"ok": True}


@app.get("/get")
def get_value():
    key = request.args.get("key")
    error = check_key(key)
    if error:
        return {"error": error}, 400

    value = store.get(key)
    if value is None:
        return {"error": "키가 없습니다"}, 404
    return {"key": key, "value": value}


@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    error = check_key(key)
    if error:
        return {"error": error}, 400

    return {"deleted": store.delete(key)}


if __name__ == "__main__":
    app.run(port=8000, debug=True)
