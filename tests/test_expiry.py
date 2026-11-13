"""4단계 만료 테스트: 캔버스 "지연 삭제 (시간이 흐르면)" 그룹의 다섯 장면을 그대로 확인한다.

진짜 시간을 기다리지 않고, 가짜 시계(self.now)를 1000 → 1005 → 1010 → 1020초로 직접 옮긴다.
"""
import unittest

from mini_redis import server
from mini_redis.store import Store


class ExpiryTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000                                   # 가짜 시계: 지금 = 1000초
        server.store = Store(clock=lambda: self.now)      # 저장소가 이 가짜 시계를 보게 한다
        self.client = server.app.test_client()

    def set_popular(self, **extra):
        return self.client.post("/set", json={"key": "popular", "value": "상품목록", **extra})

    def test_1_set_stores_value_with_expire_time(self):
        """장면 1: ttl=10으로 저장하면 노드의 value에 ("상품목록", 1010) 묶음이 들어간다."""
        self.set_popular(ttl=10)
        self.assertEqual(server.store._table.get("popular"), ("상품목록", 1010))

    def test_2_get_before_expire_returns_value(self):
        """장면 2: 1005초에는 아직 만료 전이라 값이 나오고, 노드도 그대로 있다."""
        self.set_popular(ttl=10)
        self.now = 1005
        res = self.client.get("/get?key=popular")
        self.assertEqual((res.status_code, res.get_json()), (200, {"key": "popular", "value": "상품목록"}))
        self.assertEqual(server.store._table.get("popular"), ("상품목록", 1010))

    def test_3_get_after_expire_removes_node_and_404(self):
        """장면 3: 1010초(경계값)에 get하면 만료로 보고 노드를 지운 뒤 404."""
        self.set_popular(ttl=10)
        self.now = 1010
        self.assertEqual(server.store._table.get("popular"), ("상품목록", 1010))  # get 전에는 노드가 남아 있음
        res = self.client.get("/get?key=popular")
        self.assertEqual((res.status_code, res.get_json()), (404, {"error": "not found"}))
        self.assertIsNone(server.store._table.get("popular"))                    # get 후에는 노드가 사라짐

    def test_4_delete_after_expire_removes_node_and_false(self):
        """장면 4: 1010초에 delete하면 노드는 지우지만 응답은 200 {"deleted": false}."""
        self.set_popular(ttl=10)
        self.now = 1010
        res = self.client.delete("/delete?key=popular")
        self.assertEqual((res.status_code, res.get_json()), (200, {"deleted": False}))
        self.assertIsNone(server.store._table.get("popular"))

    def test_5_overwrite_without_ttl_removes_expire(self):
        """장면 5: 1005초에 ttl 없이 덮어쓰면 만료가 사라져서 1020초에도 새 값이 나온다."""
        self.set_popular(ttl=10)
        self.now = 1005
        self.client.post("/set", json={"key": "popular", "value": "새목록"})
        self.assertEqual(server.store._table.get("popular"), ("새목록", None))
        self.assertEqual(len(server.store._table), 1)                            # 같은 노드를 덮어씀 (새 노드 없음)
        self.now = 1020
        res = self.client.get("/get?key=popular")
        self.assertEqual((res.status_code, res.get_json()), (200, {"key": "popular", "value": "새목록"}))

    def test_criterion_ttl5_then_404_and_no_ttl_stays(self):
        """3차 체크인 완료 기준: TTL을 주면 바로 조회되고 5초 뒤에는 404. TTL 없으면 계속 조회된다."""
        self.client.post("/set", json={"key": "a", "value": 1, "ttl": 5})
        self.client.post("/set", json={"key": "b", "value": 2})
        self.assertEqual(self.client.get("/get?key=a").status_code, 200)
        self.now = 1005
        self.assertEqual(self.client.get("/get?key=a").status_code, 404)
        self.now = 999_999
        self.assertEqual(self.client.get("/get?key=b").get_json(), {"key": "b", "value": 2})

    def test_expire_time_survives_resize(self):
        """확장(_resize)이 일어나도 만료 시점이 노드와 함께 따라간다."""
        self.set_popular(ttl=10)
        capacity_before = server.store._table.capacity
        for i in range(20):                                  # 키 20개를 더 넣어 8칸 → 32칸으로 확장시킨다
            self.client.post("/set", json={"key": f"k{i}", "value": i})
        self.assertGreater(server.store._table.capacity, capacity_before)
        self.assertEqual(server.store._table.get("popular"), ("상품목록", 1010))
        self.now = 1010
        self.assertEqual(self.client.get("/get?key=popular").status_code, 404)

    def test_put_tuple_again_keeps_expire_time(self):
        """해시 테이블 put에 (값, 만료 시점) 튜플을 다시 넣어도 만료 시점은 사라지지 않는다 (튜플은 값 하나)."""
        self.set_popular(ttl=10)
        entry = server.store._table.get("popular")          # ("상품목록", 1010)
        server.store._table.put("popular", entry)            # 같은 튜플로 다시 put
        self.assertEqual(server.store._table.get("popular"), ("상품목록", 1010))


if __name__ == "__main__":
    unittest.main()
