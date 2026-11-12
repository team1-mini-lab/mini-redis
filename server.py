from flask import Flask, request

from store import Store

app = Flask(__name__)
app.json.ensure_ascii = False  # 응답의 한글을 그대로 보여 줌

store = Store()


@app.get("/")
def index():
    return {"message": "mini-redis is running"}


@app.post("/set")
def set_value():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "key" not in body or "value" not in body:
        return {"error": "key와 value가 필요합니다"}, 400

    store.set(body["key"], body["value"])
    return {"ok": True}


@app.get("/get")
def get_value():
    key = request.args.get("key")
    if key is None:
        return {"error": "key가 필요합니다"}, 400

    value = store.get(key)
    if value is None:
        return {"error": "키가 없습니다"}, 404
    return {"key": key, "value": value}


@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    if key is None:
        return {"error": "key가 필요합니다"}, 400

    return {"deleted": store.delete(key)}


if __name__ == "__main__":
    app.run(port=8000, debug=True)
