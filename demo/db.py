"""가짜 DB: 느린 원본 저장소 역할을 한다.

8단계 데모 API가 "캐시가 왜 필요한가"를 보여 주려면 원본이 느려야 한다.
실제 DB에서 인기 상품을 뽑는 일(판매량 집계, 정렬)은 무거운 조회라서,
여기서는 time.sleep으로 그 비용을 흉내 낸다.

원본은 SQLite 파일에 둔다. 데모 API를 여러 대 띄워도 모두 같은 원본을 봐야
"서버가 여러 대일 때"를 제대로 재현할 수 있기 때문이다. 실제 서비스에서도
앱 서버는 여러 대여도 DB는 함께 쓴다. (파이썬 dict로 두면 서버마다 DB가 따로 생긴다)

이 모듈은 캐시를 전혀 모른다. 캐시를 쓸지 말지는 app.py가 정한다 (Cache-Aside).
"""
import os
import sqlite3
import time
from contextlib import closing

# 원본 파일 위치. 여러 프로세스가 같은 파일을 열어 원본을 공유한다.
DB_PATH = os.environ.get(
    "DEMO_DB_PATH", os.path.join(os.path.dirname(__file__), "demo.sqlite3")
)

# 무거운 조회를 흉내 내는 지연(초). 과제 예시가 3초라 기본값을 3으로 둔다.
QUERY_DELAY = float(os.environ.get("DEMO_DB_DELAY", "3"))

# 처음 상태. 3차 체크인에서 발표한 "다섯 장면"의 키보드 가격 예시를 그대로 쓴다.
SEED_PRODUCTS = [
    (1, "키보드", 50000, 320),
    (2, "마우스", 20000, 280),
    (3, "모니터", 250000, 150),
    (4, "헤드셋", 80000, 95),
    (5, "웹캠", 45000, 40),
]


def _connect():
    # timeout: 다른 프로세스가 쓰는 중이면 최대 5초 기다린다
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    """테이블이 없으면 만들고 처음 상태로 채운다. 이미 있으면 건드리지 않는다.

    두 번째 서버가 켜질 때 첫 번째 서버가 고친 가격을 덮어쓰면 안 되므로,
    비어 있을 때만 채운다.
    """
    with closing(_connect()) as conn, conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS products "
            "(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, sales INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS stats (name TEXT PRIMARY KEY, value INTEGER)"
        )
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", SEED_PRODUCTS)
        conn.execute("INSERT OR IGNORE INTO stats VALUES ('query_count', 0)")


def reset():
    """가격과 조회 횟수를 처음 상태로 돌린다. 시연을 처음부터 다시 할 때 쓴다."""
    init()
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM products")
        conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", SEED_PRODUCTS)
        conn.execute("UPDATE stats SET value = 0 WHERE name = 'query_count'")


def get_popular_products(limit=3):
    """인기 상품을 판매량 순으로 돌려준다. 느리다 (QUERY_DELAY초).

    실제라면 "주문 테이블을 상품별로 집계하고 정렬"하는 무거운 조회에 해당한다.
    조회할 때마다 횟수를 센다. 캐시가 DB를 얼마나 막아 줬는지 보여 주는 숫자다.
    """
    time.sleep(QUERY_DELAY)
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE stats SET value = value + 1 WHERE name = 'query_count'")
        rows = conn.execute(
            "SELECT id, name, price, sales FROM products ORDER BY sales DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_price(product_id, price):
    """상품 가격을 고친다. 없는 상품이면 False.

    쓰기는 원본만 고친다. 캐시를 지우는 일(무효화)은 app.py의 책임이다.
    레디스는 원본이 바뀐 것을 알 방법이 없기 때문이다.
    """
    with closing(_connect()) as conn, conn:
        cursor = conn.execute(
            "UPDATE products SET price = ? WHERE id = ?", (price, product_id)
        )
        return cursor.rowcount == 1


def get_product(product_id):
    """상품 하나를 돌려준다. 지연 없음 (가격 확인용)."""
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id, name, price, sales FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    return dict(row) if row else None


def query_count():
    """지금까지 인기 상품 조회(느린 조회)를 몇 번 했는지. 모든 서버를 합친 숫자다."""
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT value FROM stats WHERE name = 'query_count'"
        ).fetchone()[0]


def reset_query_count():
    """9단계 측정을 시작할 때 조회 횟수를 0으로 돌린다."""
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE stats SET value = 0 WHERE name = 'query_count'")
