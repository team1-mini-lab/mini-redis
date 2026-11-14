"""10단계 엣지 케이스 테스트: 만료를 다시 주거나 없앨 때, 아주 작은 ttl, 특이한 키, 크기 제한 없음."""
import unittest

from mini_redis import server
from mini_redis.store import Store


class EdgeCaseTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000                                   # 가짜 시계
        server.store = Store(clock=lambda: self.now)
        self.client = server.app.test_client()

    def status(self, key):
        return self.client.get("/get", query_string={"key": key}).status_code

    def test_set_with_ttl_again_extends_expiry(self):
        """ttl 10으로 저장한 키에 1005초에 다시 ttl 10을 주면 만료가 1015로 늦춰진다."""
        self.client.post("/set", json={"key": "s", "value": 1, "ttl": 10})
        self.now = 1005
        self.client.post("/set", json={"key": "s", "value": 1, "ttl": 10})
        self.now = 1010                                   # 처음 만료 시점: 이제는 살아 있다
        self.assertEqual(self.status("s"), 200)
        self.now = 1015                                   # 새 만료 시점
        self.assertEqual(self.status("s"), 404)

    def test_set_after_expired_without_ttl_lives_forever(self):
        """만료된 키에 ttl 없이 다시 저장하면 만료 없는 새 값이 된다."""
        self.client.post("/set", json={"key": "s", "value": "old", "ttl": 10})
        self.now = 1010
        self.assertEqual(self.status("s"), 404)
        self.client.post("/set", json={"key": "s", "value": "new"})
        self.now = 999_999
        self.assertEqual(self.client.get("/get?key=s").get_json()["value"], "new")

    def test_tiny_ttl_is_accepted_and_expires(self):
        """ttl이 아주 작아도(0.000000001초) 0보다 크므로 저장은 200, 시간이 조금만 지나면 404."""
        res = self.client.post("/set", json={"key": "t", "value": 1, "ttl": 1e-9})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.status("t"), 200)           # 가짜 시계가 멈춰 있으면 아직 만료 전
        self.now = 1000.001
        self.assertEqual(self.status("t"), 404)

    def test_duplicate_key_in_query_uses_first(self):
        """?key=a&key=b 처럼 key가 두 번 오면 첫 번째(a)를 쓴다."""
        self.client.post("/set", json={"key": "a", "value": 1})
        self.client.post("/set", json={"key": "b", "value": 2})
        self.assertEqual(self.client.get("/get?key=a&key=b").get_json(), {"key": "a", "value": 1})

    def test_unusual_keys(self):
        """이모지, 줄바꿈, 탭, 문자열 "null"·"None"도 평범한 키로 저장·조회·삭제된다."""
        for key in ("😀", "a\nb", "a\tb", "null", "None"):
            with self.subTest(key=repr(key)):
                self.client.post("/set", json={"key": key, "value": key})
                res = self.client.get("/get", query_string={"key": key})
                self.assertEqual(res.get_json(), {"key": key, "value": key})
                res = self.client.delete("/delete", query_string={"key": key})
                self.assertEqual(res.get_json(), {"deleted": True})

    def test_no_size_limit(self):
        """크기 제한이 없다(소망 결정, DECISIONS.md 6단계): 키 10만 글자, 값 200만 글자도 저장된다."""
        key, value = "k" * 100_000, "v" * 2_000_000
        self.assertEqual(self.client.post("/set", json={"key": key, "value": value}).status_code, 200)
        self.assertEqual(server.store.get(key), value)


if __name__ == "__main__":
    unittest.main()
