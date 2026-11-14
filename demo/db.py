"""느린 원본 저장소 역할을 하는 가짜 DB.

원본은 SQLite 파일 하나에 둔다. 데모 API를 여러 대 띄워도 모두 같은 원본을 본다.
이 모듈은 캐시를 모른다. 캐시를 쓸지, 언제 지울지는 app.py가 정한다.
"""
import os
import sqlite3
import time
from contextlib import closing

DB_PATH = os.environ.get(
    "DEMO_DB_PATH", os.path.join(os.path.dirname(__file__), "demo.sqlite3")
)
QUERY_DELAY = float(os.environ.get("DEMO_DB_DELAY", "3"))
WRITE_LOCK_WAIT_SECONDS = 5

# (id, 이름, 가격, 판매량)
SEED_PRODUCTS = [
    (1, "키보드", 50000, 320),
    (2, "마우스", 20000, 280),
    (3, "모니터", 250000, 150),
    (4, "헤드셋", 80000, 95),
    (5, "웹캠", 45000, 40),
]


def init():
    """이미 상품이 있으면 건드리지 않는다. 다른 서버가 고쳐 둔 가격을 덮어쓰지 않기 위해서다."""
    with closing(_connect()) as connection, connection:
        _create_tables_if_missing(connection)
        if _has_no_products(connection):
            _insert_seed_products(connection)
        connection.execute("INSERT OR IGNORE INTO stats VALUES ('query_count', 0)")


def reset():
    """상품과 조회 횟수를 처음 상태로 돌린다."""
    init()
    with closing(_connect()) as connection, connection:
        connection.execute("DELETE FROM products")
        _insert_seed_products(connection)
        _set_query_count_to_zero(connection)


def get_popular_products(limit=3):
    """판매량 순 상위 상품. 무거운 집계 조회를 흉내 내려고 QUERY_DELAY초 걸린다."""
    time.sleep(QUERY_DELAY)
    with closing(_connect()) as connection, connection:
        _increase_query_count(connection)
        rows = connection.execute(
            "SELECT id, name, price, sales FROM products ORDER BY sales DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_product(product_id):
    """없는 상품이면 None."""
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT id, name, price, sales FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    return dict(row) if row else None


def update_price(product_id, price):
    """고쳤으면 True, 없는 상품이면 False."""
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            "UPDATE products SET price = ? WHERE id = ?", (price, product_id)
        )
        return cursor.rowcount == 1


def query_count():
    """get_popular_products가 불린 횟수. 같은 원본을 보는 모든 서버의 합계다."""
    with closing(_connect()) as connection:
        return connection.execute(
            "SELECT value FROM stats WHERE name = 'query_count'"
        ).fetchone()[0]


def reset_query_count():
    with closing(_connect()) as connection, connection:
        _set_query_count_to_zero(connection)


def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=WRITE_LOCK_WAIT_SECONDS)
    connection.row_factory = sqlite3.Row
    return connection


def _create_tables_if_missing(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS products "
        "(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, sales INTEGER)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS stats (name TEXT PRIMARY KEY, value INTEGER)"
    )


def _has_no_products(connection):
    return connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def _insert_seed_products(connection):
    connection.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", SEED_PRODUCTS)


def _increase_query_count(connection):
    connection.execute("UPDATE stats SET value = value + 1 WHERE name = 'query_count'")


def _set_query_count_to_zero(connection):
    connection.execute("UPDATE stats SET value = 0 WHERE name = 'query_count'")
