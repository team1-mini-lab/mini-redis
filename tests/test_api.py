"""1단계 기능 테스트: API로 저장 → 조회 → 삭제 → 404."""
import unittest

from mini_redis import server
from mini_redis.store import Store


class ApiTest(unittest.TestCase):
    def setUp(self):
        server.store = Store()  # 테스트마다 빈 저장소
        self.client = server.app.test_client()  # 서버를 띄우지 않고 요청을 보내는 Flask 도구

    def test_set_get_delete(self):
        res = self.client.post("/set", json={"key": "name", "value": "정글전자"})
        self.assertEqual((res.status_code, res.get_json()), (200, {"ok": True}))

        res = self.client.get("/get?key=name")
        self.assertEqual((res.status_code, res.get_json()), (200, {"key": "name", "value": "정글전자"}))

        res = self.client.delete("/delete?key=name")
        self.assertEqual((res.status_code, res.get_json()), (200, {"deleted": True}))

        res = self.client.get("/get?key=name")
        self.assertEqual(res.status_code, 404)

    def test_delete_missing_key(self):
        res = self.client.delete("/delete?key=nope")
        self.assertEqual((res.status_code, res.get_json()), (200, {"deleted": False}))

    def test_set_overwrites(self):
        self.client.post("/set", json={"key": "k", "value": 1})
        self.client.post("/set", json={"key": "k", "value": 2})
        self.assertEqual(self.client.get("/get?key=k").get_json()["value"], 2)


if __name__ == "__main__":
    unittest.main()
