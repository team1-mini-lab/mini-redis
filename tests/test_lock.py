"""5단계 lock 테스트: 여러 요청이 동시에 와도 해시 테이블이 꼬이지 않는지 확인한다."""
import sys
import threading
import unittest

from mini_redis.store import Store


class LockTest(unittest.TestCase):
    def setUp(self):
        self._old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)          # 스레드를 아주 자주 바꿔서 끼어들기가 잘 일어나게 한다

    def tearDown(self):
        sys.setswitchinterval(self._old_interval)

    def test_many_threads_set_no_key_lost(self):
        """스레드 8개가 동시에 키 2000개씩 넣어도(확장 여러 번 포함) 16000개가 전부 남는다."""
        store = Store()

        def writer(t):
            for i in range(2000):
                store.set(f"{t}-{i}", i)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(len(store._table), 16000)
        missing = [(t, i) for t in range(8) for i in range(2000) if store.get(f"{t}-{i}") != i]
        self.assertEqual(missing, [])

    def test_set_cannot_cut_in_between_expire_check_and_remove(self):
        """get이 "만료 확인 → 삭제"를 하는 도중에 다른 스레드의 set이 끼어들지 못한다.

        get이 시계를 읽는 순간(만료 확인 중)에 다른 스레드가 새 값을 set하도록 만든다.
        lock이 있으면 그 set은 get이 끝날 때까지 기다리고, 끝난 뒤에 새 값이 남는다.
        """
        now = [1000]
        store = Store(clock=lambda: now[0])
        store.set("popular", "상품목록", ttl=10)      # 만료 시점 1010
        now[0] = 1010

        other = threading.Thread(target=lambda: store.set("popular", "새목록"))
        state = {}

        def clock_during_get():
            if not state:                              # get 안의 _is_expired가 처음 시계를 읽을 때
                other.start()                          # 다른 스레드가 set을 시도한다
                other.join(timeout=0.2)
                state["set_was_blocked"] = other.is_alive()   # 아직 끝나지 못했으면 lock에 막힌 것
            return now[0]

        store._clock = clock_during_get
        self.assertIsNone(store.get("popular"))        # 만료된 옛 값은 지워지고 None
        other.join()
        store._clock = lambda: now[0]

        self.assertTrue(state["set_was_blocked"])      # set은 get이 끝날 때까지 기다렸다
        self.assertEqual(store.get("popular"), "새목록")  # 새 값은 지워지지 않고 남아 있다


if __name__ == "__main__":
    unittest.main()
