"""미니 DBMS 연결 테스트: 매수 주문이 미니 DBMS에 저장되고, 계좌가 그 주문으로 계산되는지 확인한다.

미니 DBMS는 진짜 서버(mini_dbms/server.py)를 demo/dbms_server.py로 빈 포트에 한 번 켜고,
테스트마다 새 데이터 폴더 대신 사용자 이름을 다르게 써서 서로 섞이지 않게 한다.
데모 API는 Flask test_client로 부르고, 세션 캐시는 LocalCache, 종목 DB는 임시 SQLite 파일을 쓴다.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

import requests

import demo.app as demo_app
from demo import db, orders
from demo.cache import LocalCache
from demo.orders import OrderBook

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_dbms(port, data_dir):
    process = subprocess.Popen(
        [sys.executable, "-m", "demo.dbms_server", "--port", str(port), "--data-dir", data_dir],
        cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=1).ok:
                return process
        except requests.RequestException:
            time.sleep(0.1)
    process.kill()
    raise RuntimeError("미니 DBMS가 켜지지 않았습니다")


def stop(process):
    process.terminate()
    process.wait(timeout=10)


class OrderTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbms_folder = tempfile.TemporaryDirectory()
        cls.dbms_port = free_port()
        cls.dbms = start_dbms(cls.dbms_port, cls.dbms_folder.name)

    @classmethod
    def tearDownClass(cls):
        stop(cls.dbms)
        cls.dbms_folder.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = (db.DB_PATH, db.QUERY_DELAY, demo_app.cache, demo_app.order_book)
        db.DB_PATH = os.path.join(self._tmp.name, "test.sqlite3")
        db.QUERY_DELAY = 0
        db.reset()
        demo_app.cache = LocalCache()
        demo_app.order_book = OrderBook(f"http://127.0.0.1:{self.dbms_port}")
        self.client = demo_app.app.test_client()

    def tearDown(self):
        db.DB_PATH, db.QUERY_DELAY, demo_app.cache, demo_app.order_book = self._saved
        self._tmp.cleanup()

    def log_in(self, user=None):
        user = user or f"user-{uuid.uuid4().hex[:6]}"
        return self.client.post("/login", json={"user": user}).get_json()["token"]

    def buy(self, token, stock_id, quantity):
        return self.client.post(f"/orders?token={token}", json={"stock_id": stock_id, "quantity": quantity})

    def account(self, token):
        response = self.client.get(f"/account?token={token}")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()


class BuyTest(OrderTestCase):
    def test_buy_saves_order_in_mini_dbms(self):
        token = self.log_in("소망")
        response = self.buy(token, 1, 3)                         # SW-AI 50,000원 × 3
        self.assertEqual(response.status_code, 200, response.get_json())
        answer = response.get_json()
        self.assertEqual(answer["source"], "mini-dbms (INSERT)")
        self.assertEqual(answer["cash"], orders.STARTING_CASH - 150_000)
        rows = requests.post(f"http://127.0.0.1:{self.dbms_port}/query",
                             json={"sql": f"SELECT quantity, price FROM orders WHERE id = {answer['order']['id']};"}
                             ).json()["results"][0]["rows"]
        self.assertEqual(rows, [[3, 50000]])                     # 데모 API를 거치지 않고 DBMS에 직접 물어봄

    def test_account_shows_cash_holdings_and_orders(self):
        token = self.log_in()
        self.buy(token, 1, 2)                                    # 50,000원에 2주
        self.client.put("/stocks/1/price", json={"price": 60000})
        self.buy(token, 1, 2)                                    # 60,000원에 2주
        self.buy(token, 2, 1)                                    # 게임 랩 20,000원에 1주
        account = self.account(token)
        self.assertEqual(account["cash"], orders.STARTING_CASH - 100_000 - 120_000 - 20_000)
        self.assertEqual(account["holdings"][0], {
            "stock_id": 1, "stock_name": "SW-AI", "quantity": 4,
            "average_price": 55000, "current_price": 60000, "value": 240000,
        })
        self.assertEqual([order["stock_id"] for order in account["orders"]], [2, 1, 1])   # 최근 것부터

    def test_users_do_not_see_each_others_orders(self):
        mine, theirs = self.log_in(), self.log_in()
        self.buy(mine, 1, 1)
        self.assertEqual(self.account(theirs)["orders"], [])
        self.assertEqual(self.account(theirs)["cash"], orders.STARTING_CASH)

    def test_quote_in_user_name_is_stored_as_text(self):
        token = self.log_in("O'Brien")
        self.assertEqual(self.buy(token, 1, 1).status_code, 200)
        self.assertEqual(len(self.account(token)["orders"]), 1)

    def test_cannot_buy_more_than_cash(self):
        token = self.log_in()
        response = self.buy(token, 3, 41)                        # 250,000원 × 41 = 1,025만 원 > 1,000만 원
        self.assertEqual(response.status_code, 400)
        self.assertIn("잔고가 부족합니다", response.get_json()["error"])
        self.assertEqual(self.account(token)["orders"], [])
        self.assertEqual(self.buy(token, 3, 40).status_code, 200)   # 딱 1,000만 원은 살 수 있음
        self.assertEqual(self.account(token)["cash"], 0)


class BadOrderTest(OrderTestCase):
    def test_login_required(self):
        self.assertEqual(self.buy("nope", 1, 1).status_code, 401)
        self.assertEqual(self.client.get("/account?token=nope").status_code, 401)
        self.assertEqual(self.client.get("/account").status_code, 401)

    def test_bad_body(self):
        token = self.log_in()
        for body in [None, {}, {"stock_id": 1}, {"stock_id": "1", "quantity": 1},
                     {"stock_id": 1, "quantity": 0}, {"stock_id": 1, "quantity": True},
                     {"stock_id": 1, "quantity": 1.5}, {"stock_id": 1, "quantity": 1_000_001}]:
            with self.subTest(body=body):
                response = self.client.post(f"/orders?token={token}", json=body)
                self.assertEqual(response.status_code, 400)

    def test_unknown_stock(self):
        self.assertEqual(self.buy(self.log_in(), 999, 1).status_code, 404)

    def test_dbms_down_is_502(self):
        token = self.log_in()
        demo_app.order_book = OrderBook(f"http://127.0.0.1:{free_port()}")   # 아무도 없는 포트
        self.assertEqual(self.buy(token, 1, 1).status_code, 502)
        self.assertEqual(self.client.get(f"/account?token={token}").status_code, 502)


class RestartTest(unittest.TestCase):
    def test_orders_survive_dbms_restart(self):
        """미니 DBMS는 주문을 파일에 쓰므로, 껐다 켜도 주문이 남는다."""
        with tempfile.TemporaryDirectory() as folder:
            port = free_port()
            book = OrderBook(f"http://127.0.0.1:{port}")
            stock = {"id": 1, "name": "SW-AI", "price": 50000}
            process = start_dbms(port, folder)
            try:
                book.add("소망", stock, 2)
            finally:
                stop(process)
            process = start_dbms(port, folder)
            try:
                self.assertEqual([order["quantity"] for order in book.list("소망")], [2])
            finally:
                stop(process)


if __name__ == "__main__":
    unittest.main()
