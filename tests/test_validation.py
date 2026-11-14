"""6단계 입력 검증 테스트: 규칙을 어긴 요청은 저장소에 닿기 전에 400(또는 404/405 JSON)으로 돌아온다."""
import unittest

from mini_redis import server
from mini_redis.store import Store


class ValidationTest(unittest.TestCase):
    def setUp(self):
        server.store = Store()
        self.client = server.app.test_client()

    def set_status(self, body):
        return self.client.post("/set", json=body).status_code

    def test_stage1_gaps_are_closed(self):
        """1단계에서 찾은 빈틈 3개: key 없음 500 → 400, value null 저장 → 400, /get key 없음 HTML 400 → JSON 400."""
        res = self.client.post("/set", json={"value": "x"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

        self.assertEqual(self.set_status({"key": "a", "value": None}), 400)

        res = self.client.get("/get")
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())          # HTML이 아니라 JSON

    def test_body_shape(self):
        """본문이 JSON 객체가 아니면 400."""
        self.assertEqual(self.client.post("/set", data="key=a").status_code, 400)      # JSON 아님
        self.assertEqual(self.client.post("/set", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.set_status(["a", 1]), 400)                                 # 배열
        self.assertEqual(self.set_status({"key": "a", "value": 1, "tll": 5}), 400)     # 모르는 칸(오타)

    def test_key_rules(self):
        """빈 키, 문자열이 아닌 키는 400. 공백 키는 허용."""
        self.assertEqual(self.set_status({"key": "", "value": 1}), 400)
        self.assertEqual(self.set_status({"key": 123, "value": 1}), 400)
        self.assertEqual(self.set_status({"key": " ", "value": 1}), 200)
        self.assertEqual(self.client.get("/get?key=").status_code, 400)
        self.assertEqual(self.client.delete("/delete").status_code, 400)

    def test_ttl_rules(self):
        """ttl: 0 이하·문자열·bool·10년 초과는 400. 소수와 null(만료 없음)은 허용."""
        for bad in (0, -1, "5", True, server.MAX_TTL + 1):
            self.assertEqual(self.set_status({"key": "a", "value": 1, "ttl": bad}), 400, bad)
        for good in (1.5, server.MAX_TTL, None):
            self.assertEqual(self.set_status({"key": "a", "value": 1, "ttl": good}), 200, good)

    def test_rejected_request_does_not_touch_store(self):
        """400으로 거절된 set은 저장소에 아무것도 남기지 않는다."""
        self.client.post("/set", json={"key": "a", "value": "old"})
        self.client.post("/set", json={"key": "a", "value": "new", "ttl": -1})
        self.assertEqual(self.client.get("/get?key=a").get_json(), {"key": "a", "value": "old"})

    def test_unknown_path_and_method_are_json(self):
        """없는 주소는 404 JSON, 틀린 메서드는 405 JSON."""
        res = self.client.get("/nope")
        self.assertEqual(res.status_code, 404)
        self.assertIn("error", res.get_json())
        res = self.client.get("/set")
        self.assertEqual(res.status_code, 405)
        self.assertIn("error", res.get_json())


if __name__ == "__main__":
    unittest.main()
