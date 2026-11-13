import math
from flask import Flask, request, jsonify
from mini_redis.store import Store

app = Flask(__name__)
app.json.ensure_ascii = False
store = Store()


def _bad_request(message):
    return jsonify({"error": message}), 400


def _is_valid_key(key):
    return isinstance(key, str) and key != ""


def _is_valid_ttl(ttl):
    if ttl is None:
        return True
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        return False
    return math.isfinite(ttl) and ttl > 0


@app.post("/set")
def set_value():
    data = request.get_json(silent=True, force=True)
    if not isinstance(data, dict):
        return _bad_request("body must be a JSON object")
    if not _is_valid_key(data.get("key")):
        return _bad_request("key must be a non-empty string")
    if data.get("value") is None:
        return _bad_request("value is required and cannot be null")
    if not _is_valid_ttl(data.get("ttl")):
        return _bad_request("ttl must be a positive number of seconds")
    store.set(data["key"], data["value"], data.get("ttl"))
    return jsonify({"ok": True})


@app.get("/get")
def get_value():
    key = request.args.get("key")
    if not _is_valid_key(key):
        return _bad_request("key must be a non-empty string")
    value = store.get(key)
    if value is None:
        return jsonify({"error": "key not found"}), 404
    return jsonify({"key": key, "value": value})


@app.delete("/delete")
def delete_value():
    key = request.args.get("key")
    if not _is_valid_key(key):
        return _bad_request("key must be a non-empty string")
    return jsonify({"deleted": store.delete(key)})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "no such endpoint"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "method not allowed"}), 405


@app.get("/")
def index():
    return jsonify({"message": "mini redis is running"})
