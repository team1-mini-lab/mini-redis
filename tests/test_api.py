from mini_redis.server import app      # ← app은 server.py에서 가져옴

client = app.test_client()


def test_bad_inputs():
    assert client.post("/set", json={"key": "", "value": 1}).status_code == 400
    assert client.post("/set", json={"key": "a"}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": -1}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": "5"}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": True}).status_code == 400
    assert client.get("/get").status_code == 400
    assert client.delete("/delete?key=").status_code == 400


def test_good_flow():
    assert client.post("/set", json={"key": "a", "value": 1}).status_code == 200
    assert client.get("/get?key=a").get_json() == {"key": "a", "value": 1}