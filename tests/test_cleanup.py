"""주기적 정리 테스트: 아무도 조회하지 않는 만료 키를 저장소가 스스로 치우는지 확인한다.

대부분은 가짜 시계를 옮기고 정리 함수를 직접 불러 확인한다. 진짜 스레드는 마지막 테스트 하나만 켠다.
"""
import threading
import time
import unittest

from mini_redis import server
from mini_redis.hashtable import HashTable
from mini_redis.store import Store


class ScanTest(unittest.TestCase):
    def test_scan_returns_items_of_given_buckets_and_next_cursor(self):
        t = HashTable(capacity=8, hash_fn=lambda key: int(key))   # 키 "3"은 3번 칸에
        for key in ("1", "3", "5"):
            t.put(key, key)
        self.assertEqual(t.scan(0, 4), (4, [("1", "1"), ("3", "3")]))
        self.assertEqual(t.scan(4, 4), (0, [("5", "5")]))          # 끝까지 봤으면 다음 cursor는 0

    def test_cursor_past_the_end_starts_from_zero(self):
        t = HashTable(capacity=8, hash_fn=lambda key: int(key))
        t.put("1", "1")
        self.assertEqual(t.scan(100, 4), (4, [("1", "1")]))

    def test_one_round_returns_every_key_once(self):
        t = HashTable()
        for i in range(100):
            t.put(f"key{i}", i)
        seen, cursor = [], 0
        while True:
            cursor, items = t.scan(cursor, 5)
            seen += [key for key, _ in items]
            if cursor == 0:
                break
        self.assertEqual(sorted(seen), sorted(f"key{i}" for i in range(100)))

    def test_scan_does_not_remove_anything(self):
        t = HashTable()
        t.put("a", 1)
        t.scan(0, t.capacity)
        self.assertEqual((len(t), t.get("a")), (1, 1))


class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.store = Store(clock=lambda: self.now)

    def test_removes_only_expired_keys(self):
        self.store.set("expired", "v", ttl=5)
        self.store.set("alive", "v", ttl=100)
        self.store.set("forever", "v")
        self.now = 1010
        self.assertEqual(self.store.cleanup_expired_once(), 1)
        table = self.store._table
        self.assertIsNone(table.get("expired"))          # get을 부르지 않았는데도 사라짐
        self.assertIsNotNone(table.get("alive"))
        self.assertIsNotNone(table.get("forever"))

    def test_len_shrinks_by_removed_count(self):
        for i in range(5):
            self.store.set(f"k{i}", i, ttl=5)
        self.store.set("forever", "v")
        self.now = 1010
        self.store.cleanup_expired_once()
        self.assertEqual(len(self.store._table), 1)

    def test_boundary_expire_time_counts_as_expired(self):
        self.store.set("k", "v", ttl=5)
        self.now = 1005                                   # 지금 >= 만료 시점이면 만료
        self.assertEqual(self.store.cleanup_expired_once(), 1)

    def test_looks_at_cleanup_buckets_at_a_time_and_wraps_around(self):
        self.store.CLEANUP_BUCKETS = 2                    # 8칸을 2칸씩: 네 번에 한 바퀴
        self.store._table = HashTable(capacity=8, hash_fn=lambda key: int(key))
        for bucket in range(6):                           # 0~5번 칸에 하나씩 (6개면 칸이 늘지 않음)
            self.store.set(str(bucket), "v", ttl=5)
        self.now = 1010
        removed = [self.store.cleanup_expired_once() for _ in range(4)]
        self.assertEqual(removed, [2, 2, 2, 0])           # 6, 7번 칸은 비어 있음
        self.assertEqual(self.store._cleanup_cursor, 0)   # 한 바퀴 돌아 0번 칸으로
        self.assertEqual(len(self.store._table), 0)

    def test_answers_stay_correct_without_cleanup(self):
        """정리가 아직 안 와도 지연 삭제가 만료 키를 숨긴다."""
        self.store.set("k", "v", ttl=5)
        self.now = 1010
        self.assertIsNone(self.store.get("k"))
        self.assertFalse(self.store.delete("k"))


class CleanupThreadTest(unittest.TestCase):
    def test_background_thread_removes_unread_expired_key(self):
        original = server.store
        server.store = Store()
        stop = threading.Event()
        try:
            server.store.set("short", "v", ttl=0.05)
            thread = server.start_cleanup_thread(stop)
            deadline = time.monotonic() + 2
            while server.store._table.get("short") is not None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIsNone(server.store._table.get("short"))
        finally:
            stop.set()
            server.store = original
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())               # Event를 켜면 스레드가 멈춘다


if __name__ == "__main__":
    unittest.main()
