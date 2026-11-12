from flask import Flask, request, jsonify
from mini_redis.store import Store

app = Flask(__name__)
app.json.ensure_ascii = False   # 한글을 \uXXXX가 아닌 글자 그대로 응답
store = Store()

@app.post("/set")
def set_value():
    data = request.get_json()
    store.set(data["key"], data["value"], data.get("ttl"))
    return jsonify({"ok": True})

@app.get("/get")
def get_value():
    key = request.args.get("key")
    value = store.get(key)
    if value is None:
        return jsonify({"error": "key not found"}), 404
    return jsonify({"key": key, "value": value})

@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    return jsonify({"deleted": store.delete(key)})

@app.get("/")
def index():
    return jsonify({"message": "mini redis is running"})