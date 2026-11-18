"""원자적 명령(incr / decr) 테스트: 여러 요청이 동시에 세어도 하나도 사라지지 않는지 확인한다."""
import sys
import threading
import unittest

from mini_redis import server
from mini_redis.store import NotAnInteger, Store


class StoreIncrTest(unittest.TestCase):
    def setUp(self):
        self._old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)          # 스레드를 아주 자주 바꿔서 끼어들기가 잘 일어나게 한다

    def tearDown(self):
        sys.setswitchinterval(self._old_interval)

    def test_missing_key_starts_at_zero(self):
        store = Store()
        self.assertEqual(store.incr("views"), 1)
        self.assertEqual(store.incr("stock", -1), -1)

    def test_keeps_ttl(self):
        """incr는 값만 바꾸고 만료 시점은 그대로 둔다."""
        now = [1000]
        store = Store(clock=lambda: now[0])
        store.set("count", 5, ttl=10)
        self.assertEqual(store.incr("count"), 6)
        now[0] = 1010
        self.assertIsNone(store.get("count"))

    def test_not_an_integer(self):
        store = Store()
        for value in ("5", 1.5, True, [1]):
            with self.subTest(value=value):
                store.set("k", value)
                with self.assertRaises(NotAnInteger):
                    store.incr("k")

    def test_concurrent_incr_loses_nothing(self):
        """스레드 8개가 1000번씩 incr하면 정확히 8000이 된다."""
        store = Store()

        def worker():
            for _ in range(1000):
                store.incr("views")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(store.get("views"), 8000)

    def test_get_then_set_can_lose_updates(self):
        """비교: get으로 읽고 set으로 저장하면, 그 사이에 끼어든 요청 때문에 숫자가 사라질 수 있다 (장면 5)."""
        store = Store()
        store.set("views", 0)
        both_read = threading.Barrier(2)

        def worker():
            value = store.get("views")
            both_read.wait()                 # 두 요청이 모두 읽은 뒤에 저장하게 해서 끼어들기를 확실히 만든다
            store.set("views", value + 1)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(store.get("views"), 1)   # 두 번 더했는데 1


class ApiIncrTest(unittest.TestCase):
    def setUp(self):
        server.store = Store()
        self.client = server.app.test_client()

    def test_incr_and_decr(self):
        self.client.post("/set", json={"key": "stock", "value": 1})
        res = self.client.post("/decr", json={"key": "stock"})
        self.assertEqual((res.status_code, res.get_json()), (200, {"key": "stock", "value": 0}))
        res = self.client.post("/incr", json={"key": "stock"})
        self.assertEqual(res.get_json()["value"], 1)
        self.assertEqual(self.client.get("/get?key=stock").get_json()["value"], 1)

    def test_decr_can_go_negative(self):
        """실제 Redis처럼 0 밑으로도 내려간다. 품절 판단은 앱이 돌려받은 값을 보고 한다."""
        self.client.post("/set", json={"key": "stock", "value": 0})
        self.assertEqual(self.client.post("/decr", json={"key": "stock"}).get_json()["value"], -1)

    def test_bad_requests(self):
        self.client.post("/set", json={"key": "name", "value": "글자"})
        cases = [
            {"key": "name"},                  # 정수가 아닌 값
            {"key": ""},                      # 빈 키
            {},                               # 키 없음
            {"key": "k", "amount": 5},        # 모르는 항목
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/incr", json=body).status_code, 400)
        self.assertEqual(self.client.post("/incr", data="숫자").status_code, 400)


if __name__ == "__main__":
    unittest.main()
