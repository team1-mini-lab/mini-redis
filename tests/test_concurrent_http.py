"""10단계 동시 요청 테스트: 진짜 HTTP 서버(threaded=True)에 여러 요청을 한꺼번에 보낸다.

test_client는 요청을 하나씩 처리하므로, 여기서는 실제 서버를 백그라운드 스레드로 띄운다.
threaded=True라서 요청마다 서버 스레드가 따로 생기고, 그 스레드들이 같은 Store를 함께 쓴다.
"""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from werkzeug.serving import WSGIRequestHandler, make_server

from mini_redis import server
from mini_redis.store import Store


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args):        # 요청마다 찍히는 접속 로그를 끈다
        pass


class ConcurrentHttpTest(unittest.TestCase):
    def setUp(self):
        self._old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)                     # 스레드를 자주 바꿔 끼어들기가 잘 일어나게 한다
        server.store = Store()
        self.http = make_server("127.0.0.1", 0, server.app, threaded=True,
                                request_handler=QuietHandler)   # 0 = 빈 포트 아무거나
        self.base = f"http://127.0.0.1:{self.http.server_port}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def tearDown(self):
        self.http.shutdown()
        sys.setswitchinterval(self._old_interval)

    def call(self, method, path, body=None, key=None):
        """요청 하나를 보내고 (상태 코드, JSON)을 돌려준다."""
        url = self.base + path + ("?" + urllib.parse.urlencode({"key": key}) if key else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_many_clients_set_different_keys(self):
        """클라이언트 8개가 동시에 키 100개씩 저장해도 800개가 전부 남는다 (확장 여러 번 포함)."""
        def writer(t):
            return [self.call("POST", "/set", {"key": f"{t}-{i}", "value": i})[0] for i in range(100)]

        with ThreadPoolExecutor(8) as pool:
            codes = [c for codes in pool.map(writer, range(8)) for c in codes]
        self.assertEqual(set(codes), {200})
        self.assertEqual(len(server.store._table), 800)
        missing = [(t, i) for t in range(8) for i in range(100) if server.store.get(f"{t}-{i}") != i]
        self.assertEqual(missing, [])

    def test_same_key_last_value_is_one_of_written(self):
        """여러 클라이언트가 같은 키에 동시에 다른 값을 써도 오류가 없고, 남은 값은 쓴 값 중 하나다."""
        def writer(t):
            return [self.call("POST", "/set", {"key": "hot", "value": f"{t}-{i}"})[0] for i in range(50)]

        with ThreadPoolExecutor(8) as pool:
            codes = [c for codes in pool.map(writer, range(8)) for c in codes]
        self.assertEqual(set(codes), {200})
        self.assertEqual(len(server.store._table), 1)            # 같은 키라 노드는 하나
        written = {f"{t}-{i}" for t in range(8) for i in range(50)}
        self.assertIn(self.call("GET", "/get", key="hot")[1]["value"], written)

    def test_mixed_set_get_delete_never_500(self):
        """같은 키 몇 개에 set·get·delete를 섞어 동시에 보내도 응답은 정해진 것(200/404)뿐이다."""
        keys = [f"k{i}" for i in range(5)]

        def worker(t):
            results = []
            for i in range(60):
                key = keys[(t + i) % 5]
                op = (t + i) % 3
                if op == 0:
                    code, body = self.call("POST", "/set", {"key": key, "value": t})
                    results.append(code == 200 and body == {"ok": True})
                elif op == 1:
                    code, body = self.call("GET", "/get", key=key)
                    results.append((code == 200 and body["key"] == key and body["value"] in range(8))
                                   or (code == 404 and body == {"error": "not found"}))
                else:
                    code, body = self.call("DELETE", "/delete", key=key)
                    results.append(code == 200 and body["deleted"] in (True, False))
            return results

        with ThreadPoolExecutor(8) as pool:
            ok = [r for results in pool.map(worker, range(8)) for r in results]
        self.assertTrue(all(ok), f"이상한 응답 {ok.count(False)}개")

    def test_delete_true_only_once(self):
        """같은 키를 동시에 여러 번 지우면 deleted: true는 딱 한 번만 나온다."""
        self.call("POST", "/set", {"key": "once", "value": 1})
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.call("DELETE", "/delete", key="once")[1]["deleted"], range(16)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 15)


if __name__ == "__main__":
    unittest.main()
