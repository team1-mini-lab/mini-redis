"""서버 모듈: HTTP 요청을 받아 저장소 함수를 호출하고 JSON으로 응답한다 (접점 2)."""
from flask import Flask, jsonify, request

from mini_redis.store import Store

app = Flask(__name__)
store = Store()


@app.get("/")
def health():
    """0단계: 서버가 떠 있는지 확인하는 응답 하나."""
    return jsonify({"message": "mini-redis is running"})


@app.post("/set")
def set_value():
    """저장: 본문 {"key": ..., "value": ..., "ttl": ...}"""
    body = request.get_json()
    store.set(body["key"], body["value"], body.get("ttl"))
    return jsonify({"ok": True})


@app.get("/get")
def get_value():
    """조회: /get?key=name. 없으면 404."""
    key = request.args["key"]
    value = store.get(key)
    if value is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"key": key, "value": value})


@app.delete("/delete")
def delete_value():
    """삭제: /delete?key=name. 없는 키여도 200, deleted만 false."""
    key = request.args["key"]
    return jsonify({"deleted": store.delete(key)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
