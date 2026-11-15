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


def test_gaps_found_by_cross_check():
    """3단계 교차 검증(STEP7.md)에서 찾은 빈틈. 모두 500이나 200이 아니라 400이어야 한다."""
    # 아주 큰 정수 ttl: 예전에는 math.isfinite()가 OverflowError를 내서 500
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": 10**400}).status_code == 400
    # 10년을 넘는 ttl, NaN·무한대
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": 1e300}).status_code == 400
    assert client.post("/set", data='{"key":"a","value":1,"ttl":NaN}',
                       content_type="application/json").status_code == 400
    # 오타 난 칸: 예전에는 무시하고 만료 없이 저장(200)
    assert client.post("/set", json={"key": "a", "value": 1, "ttI": 5}).status_code == 400
    # Content-Type 없이 보낸 본문: 예전에는 force=True로 받아 줌(200)
    assert client.post("/set", data='{"key": "a", "value": 1}').status_code == 400


def test_ttl_boundaries_still_work():
    """빈틈을 막으면서 정상 범위는 그대로 받는다."""
    ten_years = 10 * 365 * 24 * 60 * 60
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": ten_years}).status_code == 200
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": ten_years + 1}).status_code == 400
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": 0.5}).status_code == 200
    assert client.post("/set", json={"key": "a", "value": 1, "ttl": 0}).status_code == 400
