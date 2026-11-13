import pytest

import server
from store import Store


@pytest.fixture
def client(monkeypatch):
    # 테스트마다 빈 저장소로 바꿔 끼워, 테스트끼리 영향을 주지 않게 함
    monkeypatch.setattr(server, "store", Store())
    return server.app.test_client()


def post_set(client, raw_json):
    """JSON 문자열을 그대로 보냄. NaN처럼 파이썬 dict로 만들기 어려운 본문도 보낼 수 있음"""
    return client.post("/set", data=raw_json, content_type="application/json")


@pytest.mark.parametrize(
    "raw_json",
    [
        '[1, 2]',                                     # 객체가 아님
        '{"key": "a"}',                               # value 없음
        '{"key": "a", "value": 1, "tll": 5}',         # 모르는 항목 (오타)
        '{"key": 123, "value": 1}',                   # 문자열이 아닌 키
        '{"key": "", "value": 1}',                    # 빈 키
        '{"key": "a", "value": null}',                # null 값
        '{"key": "a", "value": 1, "ttl": "abc"}',     # 숫자가 아닌 ttl
        '{"key": "a", "value": 1, "ttl": 0}',         # 0
        '{"key": "a", "value": 1, "ttl": -1}',        # 음수
        '{"key": "a", "value": 1, "ttl": true}',      # 불리언
        '{"key": "a", "value": 1, "ttl": NaN}',       # NaN
        '{"key": "a", "value": 1, "ttl": Infinity}',  # 무한대
        '{"key": "a", "value": 1, "ttl": 1' + "0" * 400 + '}',  # 아주 큰 정수
        '{"key": "a", "value": 1, "ttl": 315360001}',  # 10년 초과
    ],
)
def test_set_rejects_invalid_body(client, raw_json):
    response = post_set(client, raw_json)
    assert response.status_code == 400
    assert "error" in response.get_json()
    assert client.get("/get?key=a").status_code == 404  # 거절된 요청은 저장되지 않음


def test_set_without_body(client):
    response = client.post("/set")
    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/get", "/get?key=", "/delete?key="])
def test_query_key_must_be_non_empty(client, path):
    method = client.delete if path.startswith("/delete") else client.get
    response = method(path)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "value",
    ["현지", 0, False, 1.5, [1, None], {"a": 1}, ""],
)
def test_set_accepts_any_json_value_except_null(client, value):
    # 0, false, 빈 문자열처럼 "거짓"으로 취급되는 값도 null이 아니므로 저장됨
    assert client.post("/set", json={"key": "k", "value": value}).status_code == 200
    assert client.get("/get?key=k").get_json() == {"key": "k", "value": value}


def test_set_accepts_whitespace_key(client):
    assert client.post("/set", json={"key": " ", "value": 1}).status_code == 200
    assert client.get("/get?key=%20").status_code == 200


def test_set_accepts_float_ttl(client):
    assert client.post("/set", json={"key": "k", "value": 1, "ttl": 1.5}).status_code == 200
    assert client.get("/get?key=k").status_code == 200


def test_set_accepts_max_ttl(client):
    assert client.post("/set", json={"key": "k", "value": 1, "ttl": server.MAX_TTL}).status_code == 200


def test_null_ttl_means_no_expiry(client):
    assert client.post("/set", json={"key": "k", "value": 1, "ttl": None}).status_code == 200
    assert client.get("/get?key=k").status_code == 200
