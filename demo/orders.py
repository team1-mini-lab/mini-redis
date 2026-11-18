"""매수 주문을 미니 DBMS(orders 테이블)에 저장하고 읽어 온다.

미니 DBMS는 INSERT와 SELECT ... WHERE 하나만 안다 (UPDATE, 합계, 정렬 없음).
그래서 주문은 지우거나 고치지 않고 한 줄씩 쌓기만 하고,
보유 종목과 잔고는 그 사용자의 주문을 전부 읽어 여기서 계산한다.

    잔고      = 처음 돈 - (주문마다 수량 × 체결 가격)의 합
    보유 수량 = 종목별 주문 수량의 합
"""
import os
import time

import requests

DEFAULT_DBMS_URL = "http://127.0.0.1:8020"
STARTING_CASH = int(os.environ.get("DEMO_STARTING_CASH", "10000000"))   # 사용자마다 처음 주는 돈 1,000만 원
TIMEOUT_SECONDS = 5


class DbmsError(Exception):
    """미니 DBMS에 닿지 않거나, 미니 DBMS가 SQL을 거절했다."""


class OrderBook:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("DEMO_DBMS_URL", DEFAULT_DBMS_URL)

    def ping(self):
        try:
            return requests.get(f"{self.base_url}/health", timeout=1).ok
        except requests.RequestException:
            return False

    def add(self, user, stock, quantity):
        """주문 한 줄을 넣고, 넣은 주문을 dict로 돌려준다. 시장가로 바로 체결된다고 본다."""
        ordered_at = int(time.time())
        sql = (
            "INSERT INTO orders (user, stock_id, stock_name, quantity, price, ordered_at) VALUES ("
            f"{text(user)}, {stock['id']}, {text(stock['name'])}, {quantity}, {stock['price']}, {ordered_at});"
        )
        order_id = self._run(sql)["id"]
        return {
            "id": order_id, "stock_id": stock["id"], "stock_name": stock["name"],
            "quantity": quantity, "price": stock["price"], "ordered_at": ordered_at,
        }

    def list(self, user):
        """그 사용자의 주문을 최근 것부터."""
        answer = self._run(f"SELECT * FROM orders WHERE user = {text(user)};")
        orders = [dict(zip(answer["columns"], row)) for row in answer["rows"]]
        for order in orders:
            del order["user"]
        return sorted(orders, key=lambda order: order["id"], reverse=True)

    def _run(self, sql):
        try:
            response = requests.post(f"{self.base_url}/query", json={"sql": sql}, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:
            raise DbmsError(f"미니 DBMS({self.base_url})에 연결할 수 없습니다") from error
        answer = response.json() if response.content else {}
        if not response.ok:
            message = answer.get("error", {}).get("message", f"상태 {response.status_code}")
            raise DbmsError(f"미니 DBMS가 요청을 거절했습니다: {message}")
        return answer["results"][0]


def text(value):
    """SQL 문자열 값. 미니 DBMS 문법대로 작은따옴표 하나는 두 개로 적는다."""
    return "'" + value.replace("'", "''") + "'"


def cash_left(orders):
    return STARTING_CASH - sum(order["quantity"] * order["price"] for order in orders)


def holdings(orders, current_price):
    """종목별 보유 수량, 평균 매수가, 현재가, 평가 금액. current_price(stock_id)는 지금 가격 또는 None."""
    by_stock = {}
    for order in sorted(orders, key=lambda order: order["id"]):
        holding = by_stock.setdefault(order["stock_id"], {
            "stock_id": order["stock_id"], "stock_name": order["stock_name"], "quantity": 0, "spent": 0,
        })
        holding["quantity"] += order["quantity"]
        holding["spent"] += order["quantity"] * order["price"]
    result = []
    for holding in by_stock.values():
        price = current_price(holding["stock_id"])
        price = price if price is not None else holding["spent"] // holding["quantity"]
        result.append({
            "stock_id": holding["stock_id"],
            "stock_name": holding["stock_name"],
            "quantity": holding["quantity"],
            "average_price": round(holding["spent"] / holding["quantity"]),
            "current_price": price,
            "value": price * holding["quantity"],
        })
    return result
