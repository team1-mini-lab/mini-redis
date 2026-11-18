"""데이터 유지(스냅샷) 테스트.

대부분은 가짜 시계 두 개(실행 중 시계, 벽시계)로 함수를 직접 부르거나, 임시 폴더에 진짜 파일을 쓰고 읽는다.
진짜 서버를 SIGTERM으로 껐다 켜는 테스트와 스냅샷 스레드 테스트는 하나씩만 둔다.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request

from mini_redis import snapshot
from mini_redis.snapshot import load_snapshot, save_snapshot
from mini_redis.store import Store


class Clocks:
    """실행 중 시계(monotonic 역할)와 벽시계(time.time 역할)를 따로 옮길 수 있는 가짜 시계."""

    def __init__(self, monotonic, wall):
        self.monotonic = monotonic
        self.wall = wall

    def store(self):
        return Store(clock=lambda: self.monotonic, wall_clock=lambda: self.wall)


class SnapshotItemsTest(unittest.TestCase):
    def setUp(self):
        self.clocks = Clocks(monotonic=1000, wall=5000)
        self.store = self.clocks.store()

    def test_collects_live_keys_with_wall_clock_expire(self):
        self.store.set("forever", "v")
        self.store.set("ttl", "v", ttl=10)
        items = sorted(self.store.snapshot_items(), key=lambda item: item["key"])
        self.assertEqual(items, [
            {"key": "forever", "value": "v", "expire": None},
            {"key": "ttl", "value": "v", "expire": 5010},   # 벽시계 5000 + 남은 10초
        ])

    def test_skips_expired_keys(self):
        self.store.set("short", "v", ttl=5)
        self.clocks.monotonic += 5
        self.clocks.wall += 5
        self.assertEqual(self.store.snapshot_items(), [])


class RestoreTest(unittest.TestCase):
    def test_remaining_time_continues_on_the_new_monotonic_clock(self):
        clocks = Clocks(monotonic=20, wall=5005)          # 재부팅해서 monotonic 기준점이 바뀐 상황
        store = clocks.store()
        restored = store.restore([{"key": "k", "value": "v", "expire": 5010}])
        self.assertEqual(restored, 1)
        self.assertEqual(store._table.get("k"), ("v", 25))   # 새 monotonic 20 + 남은 5초
        clocks.monotonic = 25
        self.assertIsNone(store.get("k"))

    def test_key_that_expired_while_server_was_off_is_not_restored(self):
        store = Clocks(monotonic=0, wall=5020).store()    # 5010에 만료, 5020에 다시 켬
        self.assertEqual(store.restore([{"key": "k", "value": "v", "expire": 5010}]), 0)
        self.assertEqual(len(store._table), 0)

    def test_no_expire_stays_no_expire(self):
        store = Clocks(monotonic=0, wall=0).store()
        store.restore([{"key": "k", "value": "v", "expire": None}])
        self.assertEqual(store._table.get("k"), ("v", None))


class ChangedFlagTest(unittest.TestCase):
    def setUp(self):
        self.clocks = Clocks(monotonic=1000, wall=5000)
        self.store = self.clocks.store()

    def test_set_and_successful_delete_turn_it_on_snapshot_turns_it_off(self):
        self.assertFalse(self.store.has_changes())
        self.store.set("k", "v")
        self.assertTrue(self.store.has_changes())
        self.store.snapshot_items()
        self.assertFalse(self.store.has_changes())
        self.assertFalse(self.store.delete("missing"))
        self.assertFalse(self.store.has_changes())        # 지운 게 없으면 바뀐 게 아님
        self.store.delete("k")
        self.assertTrue(self.store.has_changes())

    def test_cleanup_removal_is_not_a_change(self):
        self.store.set("short", "v", ttl=5)
        self.store.snapshot_items()
        self.clocks.monotonic += 10
        self.store.cleanup_expired_once()
        self.assertFalse(self.store.has_changes())


class SnapshotFileTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "data", "snapshot.json")
        self.clocks = Clocks(monotonic=1000, wall=5000)

    def tearDown(self):
        self.folder.cleanup()

    def test_round_trip_keeps_every_json_value(self):
        values = {"문자열": "빨강", "숫자": 0, "거짓": False, "빈 글자": "", "목록": [1, "a"], "묶음": {"price": 1200}}
        store = self.clocks.store()
        for key, value in values.items():
            store.set(key, value)
        store.set("ttl", "v", ttl=30)
        self.assertEqual(save_snapshot(store, self.path), len(values) + 1)

        restored = Clocks(monotonic=0, wall=5010).store()
        self.assertEqual(load_snapshot(restored, self.path), len(values) + 1)
        for key, value in values.items():
            self.assertEqual(restored.get(key), value)
        self.assertEqual(restored._table.get("ttl"), ("v", 20))   # 30초 중 10초가 꺼진 동안 흐름

    def test_file_shape(self):
        store = self.clocks.store()
        store.set("가방", "빨강")
        save_snapshot(store, self.path)
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(json.load(file), {"version": 1, "items": [{"key": "가방", "value": "빨강", "expire": None}]})
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_missing_file_starts_empty(self):
        store = self.clocks.store()
        self.assertEqual(load_snapshot(store, self.path), 0)
        self.assertEqual(len(store._table), 0)

    def test_leftover_tmp_is_ignored(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path + ".tmp", "w", encoding="utf-8") as file:
            file.write('{"version": 1, "items": [{"key": "반쪽')   # 쓰다 만 파일
        store = self.clocks.store()
        self.assertEqual(load_snapshot(store, self.path), 0)
        self.assertEqual(len(store._table), 0)

    def test_broken_files_are_moved_aside_and_store_starts_empty(self):
        broken_contents = [
            '{"version": 1, "items": [',                                                # JSON이 끊김
            '{"version": 2, "items": []}',                                              # 모르는 version
            '{"version": 1, "items": [{"key": "k", "value": null, "expire": null}]}',   # 값이 null
            '{"version": 1, "items": [{"key": "", "value": 1, "expire": null}]}',       # 빈 키
            '{"version": 1, "items": [{"key": "k", "value": 1, "expire": "내일"}]}',     # expire가 글자
        ]
        os.makedirs(os.path.dirname(self.path))
        for content in broken_contents:
            with self.subTest(content=content):
                with open(self.path, "w", encoding="utf-8") as file:
                    file.write(content)
                store = self.clocks.store()
                with open(os.devnull, "w") as quiet:
                    original_stderr, sys.stderr = sys.stderr, quiet
                    try:
                        self.assertEqual(load_snapshot(store, self.path), 0)
                    finally:
                        sys.stderr = original_stderr
                self.assertEqual(len(store._table), 0)
                self.assertFalse(os.path.exists(self.path))
                with open(self.path + ".broken", encoding="utf-8") as file:
                    self.assertEqual(file.read(), content)              # 증거를 그대로 남김

    def test_failed_write_keeps_previous_snapshot_and_retries_later(self):
        store = self.clocks.store()
        store.set("old", "v")
        save_snapshot(store, self.path)
        store.set("bad", object())                        # JSON으로 바꿀 수 없는 값으로 쓰기를 일부러 실패시킴
        with self.assertRaises(TypeError):
            save_snapshot(store, self.path)
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(json.load(file)["items"], [{"key": "old", "value": "v", "expire": None}])
        self.assertTrue(store.has_changes())              # 다음 차례에 다시 시도


class SnapshotThreadTest(unittest.TestCase):
    def test_thread_saves_changes_and_stops_on_event(self):
        folder = tempfile.TemporaryDirectory()
        path = os.path.join(folder.name, "snapshot.json")
        store = Store()
        stop = threading.Event()
        original_interval = snapshot.SNAPSHOT_INTERVAL
        snapshot.SNAPSHOT_INTERVAL = 0.05
        try:
            thread = threading.Thread(target=snapshot.run_snapshots, args=(store, path, stop), daemon=True)
            thread.start()
            store.set("k", "v")
            deadline = time.monotonic() + 2
            while not os.path.exists(path) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(os.path.exists(path))
        finally:
            stop.set()
            snapshot.SNAPSHOT_INTERVAL = original_interval
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        folder.cleanup()


class RealServerRestartTest(unittest.TestCase):
    """완료 기준: 서버를 껐다(SIGTERM) 켜도 값이 조회된다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = {**os.environ, "MINI_REDIS_SNAPSHOT": os.path.join(self.folder.name, "snapshot.json")}
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.folder.cleanup()

    def start_server(self):
        code = "import sys; from mini_redis import server; server.PORT = int(sys.argv[1]); server.main()"
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(self.port)],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(self.base + "/", timeout=1).close()
                return process
            except OSError:
                time.sleep(0.1)
        process.kill()
        self.fail("서버가 켜지지 않았습니다")

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_value_survives_sigterm_restart(self):
        process = self.start_server()
        try:
            self.request("POST", "/set", {"key": "가방", "value": "빨강"})
        finally:
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=10), 0)   # 바로 죽지 않고 마지막 저장 뒤 정상 종료

        process = self.start_server()
        try:
            answer = self.request("GET", "/get?key=" + urllib.parse.quote("가방"))
            self.assertEqual(answer, {"key": "가방", "value": "빨강"})
        finally:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
