"""8단계 데모 API 기능 테스트.

무엇을 확인하나
    1. 8단계 완료 기준 두 개 — 두 번째 조회는 캐시에서, 가격을 바꾸면 새 가격
    2. 서버가 두 대일 때 — 로컬 캐시는 어긋나고, mini-redis는 같은 값을 본다
    3. 캐시가 죽어도 — DB로 응답하고, 가격 수정도 성공한다
    4. 만료 — TTL이 지나면 다시 DB로 간다
    5. 잘못된 입력 — 400 / 404

서버를 띄우지 않는다. Flask의 test_client로 요청을 보낸다.
mini-redis 쪽도 실제 mini_redis/server.py 코드를 test_client로 부르므로,
데모 API → mini-redis HTTP API → 저장소 → 해시 테이블까지 실제 코드가 그대로 돈다.

"서버 두 대"는 요청마다 데모 API가 쓰는 캐시 객체를 바꿔 끼워 흉내 낸다.
    로컬 캐시:  서버 A, B가 각자 다른 LocalCache (각 서버 안의 dict)
    mini-redis: 서버 A, B가 각자 클라이언트를 갖지만 같은 mini-redis 저장소를 본다
DB는 두 경우 모두 임시 SQLite 파일 하나를 함께 쓴다.
"""
import os
import tempfile
import time
import unittest

import demo.app as demo_app
from demo import db
from demo.cache import LocalCache, RedisCache
from mini_redis import server as mini_redis_server
from mini_redis.store import Store


class InProcessMiniRedis:
    """RedisCache와 같은 모양(get / set / delete)으로, 실제 mini-redis 서버 코드를 부른다.

    RedisCache는 requests로 네트워크를 타지만, 테스트에서는 서버를 띄우지 않으려고
    같은 HTTP 요청을 test_client로 보낸다. 주소와 본문 모양은 RedisCache와 똑같다.
    """

    name = "redis"

    def __init__(self):
        self.client = mini_redis_server.app.test_client()

    def get(self, key):
        res = self.client.get("/get", query_string={"key": key})
        return res.get_json()["value"] if res.status_code == 200 else None

    def set(self, key, value, ttl=None):
        body = {"key": key, "value": value}
        if ttl is not None:
            body["ttl"] = ttl
        self.client.post("/set", json=body)

    def delete(self, key):
        res = self.client.delete("/delete", query_string={"key": key})
        return res.status_code == 200 and res.get_json()["deleted"]

    def ping(self):
        return True


class DemoTestCase(unittest.TestCase):
    def setUp(self):
        # DB: 테스트마다 새 임시 파일, 지연 없음
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = (db.DB_PATH, db.QUERY_DELAY, demo_app.cache, demo_app.POPULAR_TTL)
        db.DB_PATH = os.path.join(self._tmp.name, "test.sqlite3")
        db.QUERY_DELAY = 0
        db.reset()
        # mini-redis: 테스트마다 빈 저장소
        mini_redis_server.store = Store()
        self.client = demo_app.app.test_client()

    def tearDown(self):
        db.DB_PATH, db.QUERY_DELAY, demo_app.cache, demo_app.POPULAR_TTL = self._saved
        self._tmp.cleanup()

    # ── 도우미 ────────────────────────────────────────────

    def on(self, cache):
        """다음 요청을 이 캐시를 쓰는 서버가 받게 한다."""
        demo_app.cache = cache
        return self.client

    def popular(self, cache):
        res = self.on(cache).get("/products/popular")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        keyboard = next(p for p in data["products"] if p["id"] == 1)
        return data["source"], keyboard["price"]

    def set_price(self, cache, price):
        return self.on(cache).put("/products/1/price", json={"price": price})


class CompletionCriteriaTest(DemoTestCase):
    """8단계 완료 기준."""

    def test_second_read_comes_from_cache(self):
        cache = InProcessMiniRedis()
        self.assertEqual(self.popular(cache), ("db", 50000))
        self.assertEqual(self.popular(cache), ("cache", 50000))
        self.assertEqual(db.query_count(), 1)      # DB에는 한 번만 갔다

    def test_price_update_invalidates_cache(self):
        cache = InProcessMiniRedis()
        self.popular(cache)                         # 캐시를 채운다

        res = self.set_price(cache, 40000)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["cache_invalidated"])

        self.assertEqual(self.popular(cache), ("db", 40000))      # 지워졌으니 DB에서 새 값
        self.assertEqual(self.popular(cache), ("cache", 40000))   # 다시 캐시에

    def test_nocache_skips_cache(self):
        cache = InProcessMiniRedis()
        for _ in range(2):
            res = self.on(cache).get("/products/popular?nocache=1")
            self.assertEqual(res.get_json()["source"], "db (nocache)")
        self.assertEqual(db.query_count(), 2)
        self.assertIsNone(cache.get(demo_app.POPULAR_KEY))   # 캐시도 채우지 않는다


class TwoServersTest(DemoTestCase):
    """서버가 두 대일 때. 같은 순서로 요청하고 캐시 위치만 바꾼다."""

    def run_scene(self, cache_a, cache_b):
        """A 조회 → B 조회 → A에서 할인 → B 조회. (B의 첫 조회 출처, 할인 후 B가 본 가격)"""
        self.popular(cache_a)
        b_first, _ = self.popular(cache_b)
        self.set_price(cache_a, 40000)
        _, b_price = self.popular(cache_b)
        return b_first, b_price

    def test_local_cache_goes_stale(self):
        b_first, b_price = self.run_scene(LocalCache(), LocalCache())
        self.assertEqual(b_first, "db")       # B는 A의 캐시를 모른다 (장면 ④)
        self.assertEqual(b_price, 50000)      # A가 지운 건 A의 캐시뿐 (장면 ①)

    def test_mini_redis_stays_consistent(self):
        b_first, b_price = self.run_scene(InProcessMiniRedis(), InProcessMiniRedis())
        self.assertEqual(b_first, "cache")    # A가 채운 캐시를 B도 본다
        self.assertEqual(b_price, 40000)      # 키 하나 지우면 모두 새 값

    def test_session_local_cache_logs_out_on_other_server(self):
        token = self.on(LocalCache()).post("/login", json={"user": "guest"}).get_json()["token"]
        res = self.on(LocalCache()).get(f"/me?token={token}")
        self.assertEqual(res.status_code, 401)     # 장면 ② 로그인이 풀림

    def test_session_mini_redis_keeps_login(self):
        token = self.on(InProcessMiniRedis()).post("/login", json={"user": "guest"}).get_json()["token"]
        res = self.on(InProcessMiniRedis()).get(f"/me?token={token}")
        self.assertEqual((res.status_code, res.get_json()["user"]), (200, "guest"))

        self.on(InProcessMiniRedis()).post(f"/logout?token={token}")
        res = self.on(InProcessMiniRedis()).get(f"/me?token={token}")
        self.assertEqual(res.status_code, 401)     # 로그아웃은 모든 서버에서 한 번에


class CacheDownTest(DemoTestCase):
    """mini-redis가 죽어 있어도 서비스는 멈추지 않는다."""

    def setUp(self):
        super().setUp()
        self.dead = RedisCache("http://127.0.0.1:9")   # 아무것도 듣지 않는 포트
        self.dead._warned = True                        # 경고 출력 끄기

    def test_read_answers_from_db(self):
        self.assertEqual(self.popular(self.dead), ("db", 50000))
        self.assertEqual(self.popular(self.dead), ("db", 50000))   # 느려질 뿐 답은 맞다

    def test_write_still_succeeds(self):
        res = self.set_price(self.dead, 40000)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["cache_invalidated"])   # 지우지 못했다고 알려 준다
        self.assertEqual(db.get_product(1)["price"], 40000)     # DB는 고쳐졌다


class ExpiryTest(DemoTestCase):
    """TTL이 지나면 캐시가 사라지고 다시 DB로 간다 (무효화를 놓쳤을 때의 안전망)."""

    def test_expired_cache_goes_back_to_db(self):
        demo_app.POPULAR_TTL = 0.05
        cache = InProcessMiniRedis()
        self.popular(cache)
        self.assertEqual(self.popular(cache)[0], "cache")
        time.sleep(0.1)
        self.assertEqual(self.popular(cache)[0], "db")

    def test_ttl_heals_missed_invalidation(self):
        """DB를 앱 밖에서 직접 고치면(무효화 실패) TTL 동안만 옛 값이 보인다."""
        demo_app.POPULAR_TTL = 0.05
        cache = InProcessMiniRedis()
        self.popular(cache)
        db.update_price(1, 40000)                   # 앱을 거치지 않음 → 캐시를 아무도 안 지움
        self.assertEqual(self.popular(cache), ("cache", 50000))   # 아직 옛 값
        time.sleep(0.1)
        self.assertEqual(self.popular(cache), ("db", 40000))      # TTL이 지나 저절로 맞음


class ValidationTest(DemoTestCase):
    """잘못된 입력."""

    def test_bad_price(self):
        cache = InProcessMiniRedis()
        for body in ({}, {"price": -1}, {"price": "40000"}, {"price": True}, {"price": 1.5}):
            with self.subTest(body=body):
                res = self.on(cache).put("/products/1/price", json=body)
                self.assertEqual(res.status_code, 400)
        self.assertEqual(db.get_product(1)["price"], 50000)    # 아무것도 바뀌지 않았다

    def test_unknown_product(self):
        res = self.set_price(InProcessMiniRedis(), 40000)
        self.assertEqual(res.status_code, 200)
        res = self.on(InProcessMiniRedis()).put("/products/999/price", json={"price": 1})
        self.assertEqual(res.status_code, 404)
        res = self.on(InProcessMiniRedis()).get("/products/999")
        self.assertEqual(res.status_code, 404)

    def test_session_input(self):
        cache = InProcessMiniRedis()
        self.assertEqual(self.on(cache).post("/login", json={}).status_code, 400)
        self.assertEqual(self.on(cache).post("/login", json={"user": ""}).status_code, 400)
        self.assertEqual(self.on(cache).get("/me").status_code, 400)


if __name__ == "__main__":
    unittest.main()
