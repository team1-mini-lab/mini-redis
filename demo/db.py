"""가짜 DB: 느린 원본 저장소 역할을 한다.

8단계 데모 API가 "캐시가 왜 필요한가"를 보여 주려면 원본이 느려야 한다.
실제 DB에서 인기 상품을 뽑는 일(판매량 집계, 정렬)은 무거운 조회라서,
여기서는 time.sleep으로 그 비용을 흉내 낸다.

이 모듈은 캐시를 전혀 모른다. 캐시를 쓸지 말지는 app.py가 정한다 (Cache-Aside).
"""
import threading
import time

# 원본 데이터. 3차 체크인에서 발표한 "다섯 장면"의 키보드 가격 예시를 그대로 쓴다.
_PRODUCTS = {
    1: {"id": 1, "name": "키보드", "price": 50000, "sales": 320},
    2: {"id": 2, "name": "마우스", "price": 20000, "sales": 280},
    3: {"id": 3, "name": "모니터", "price": 250000, "sales": 150},
    4: {"id": 4, "name": "헤드셋", "price": 80000, "sales": 95},
    5: {"id": 5, "name": "웹캠", "price": 45000, "sales": 40},
}

# 무거운 조회를 흉내 내는 지연(초). 과제 예시가 3초라 기본값을 3으로 둔다.
QUERY_DELAY = 3.0

# 여러 요청이 동시에 _PRODUCTS를 만질 수 있으니 DB 쪽도 lock으로 보호한다.
# (실제 DB라면 DBMS가 해 주는 일이다)
_lock = threading.Lock()

# 이 과정에서 DB를 몇 번 조회했는지 센다. 9단계 성능 비교에서 "캐시가 DB를 얼마나
# 막아 줬는지"를 숫자로 보여 주는 데 쓴다.
query_count = 0


def _sleep_like_a_slow_query():
    """무거운 조회를 흉내 낸다."""
    time.sleep(QUERY_DELAY)


def get_popular_products(limit=3):
    """인기 상품을 판매량 순으로 돌려준다. 느리다 (QUERY_DELAY초).

    실제라면 "주문 테이블을 상품별로 집계하고 정렬"하는 무거운 조회에 해당한다.
    """
    global query_count
    _sleep_like_a_slow_query()
    with _lock:
        query_count += 1
        ranked = sorted(_PRODUCTS.values(), key=lambda p: p["sales"], reverse=True)
        # 사본을 돌려준다. 바깥에서 고쳐도 원본이 바뀌지 않게.
        return [dict(p) for p in ranked[:limit]]


def update_price(product_id, price):
    """상품 가격을 고친다. 없는 상품이면 False.

    쓰기는 원본만 고친다. 캐시를 지우는 일(무효화)은 app.py의 책임이다.
    레디스는 원본이 바뀐 것을 알 방법이 없기 때문이다.
    """
    with _lock:
        product = _PRODUCTS.get(product_id)
        if product is None:
            return False
        product["price"] = price
        return True


def get_product(product_id):
    """상품 하나를 돌려준다. 지연 없음 (가격 확인용)."""
    with _lock:
        product = _PRODUCTS.get(product_id)
        return dict(product) if product else None


def reset_query_count():
    """9단계 측정을 시작할 때 조회 횟수를 0으로 돌린다."""
    global query_count
    with _lock:
        query_count = 0
