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

    # ---- 10단계 보완: API 세 가지 기능 ----

    def test_health(self):
        """GET / 는 서버가 떠 있다는 응답을 준다."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("message", res.get_json())

    def test_value_types_round_trip(self):
        """JSON 값 종류(숫자, 소수, 문자열, bool, 배열, 객체)가 저장한 그대로 돌아온다."""
        for value in (42, 3.14, "글자", True, [1, "a"], {"price": 1000}):
            with self.subTest(value=value):
                self.client.post("/set", json={"key": "v", "value": value})
                self.assertEqual(self.client.get("/get?key=v").get_json()["value"], value)

    def test_falsy_values_are_not_missing(self):
        """0, false, 빈 문자열, 빈 배열은 "없음"이 아니라 값이다: 404가 아니라 200."""
        for value in (0, False, "", []):
            with self.subTest(value=value):
                self.client.post("/set", json={"key": "f", "value": value})
                res = self.client.get("/get?key=f")
                self.assertEqual((res.status_code, res.get_json()["value"]), (200, value))
                self.assertEqual(self.client.delete("/delete?key=f").get_json(), {"deleted": True})

    def test_special_keys_in_query_string(self):
        """한글, 공백, &, =, /, ? 가 든 키도 URL로 주고받을 수 있다 (query_string이 인코딩해 준다)."""
        for key in ("한글", "a b", "a&b", "a=b", "a/b", "a?b"):
            with self.subTest(key=key):
                self.client.post("/set", json={"key": key, "value": key})
                res = self.client.get("/get", query_string={"key": key})
                self.assertEqual(res.get_json(), {"key": key, "value": key})
                res = self.client.delete("/delete", query_string={"key": key})
                self.assertEqual(res.get_json(), {"deleted": True})

    def test_delete_twice(self):
        """같은 키를 두 번 지우면 처음은 true, 두 번째는 false."""
        self.client.post("/set", json={"key": "k", "value": 1})
        self.assertEqual(self.client.delete("/delete?key=k").get_json(), {"deleted": True})
        self.assertEqual(self.client.delete("/delete?key=k").get_json(), {"deleted": False})

    def test_set_again_after_delete(self):
        """지운 키에 다시 저장하면 새 값이 조회된다."""
        self.client.post("/set", json={"key": "k", "value": "old"})
        self.client.delete("/delete?key=k")
        self.client.post("/set", json={"key": "k", "value": "new"})
        self.assertEqual(self.client.get("/get?key=k").get_json()["value"], "new")

    def test_keys_are_independent(self):
        """한 키를 바꾸거나 지워도 다른 키는 그대로다. 대소문자도 다른 키다."""
        self.client.post("/set", json={"key": "a", "value": 1})
        self.client.post("/set", json={"key": "A", "value": 2})
        self.client.post("/set", json={"key": "b", "value": 3})
        self.client.delete("/delete?key=a")
        self.assertEqual(self.client.get("/get?key=a").status_code, 404)
        self.assertEqual(self.client.get("/get?key=A").get_json()["value"], 2)
        self.assertEqual(self.client.get("/get?key=b").get_json()["value"], 3)

    def test_many_keys_through_api(self):
        """API로 키 200개를 넣어도(칸 확장 여러 번) 전부 조회되고 전부 지워진다."""
        for i in range(200):
            self.client.post("/set", json={"key": f"k{i}", "value": i})
        for i in range(200):
            self.assertEqual(self.client.get(f"/get?key=k{i}").get_json()["value"], i)
        for i in range(200):
            self.assertEqual(self.client.delete(f"/delete?key=k{i}").get_json(), {"deleted": True})
        self.assertEqual(len(server.store._table), 0)


if __name__ == "__main__":
    unittest.main()
