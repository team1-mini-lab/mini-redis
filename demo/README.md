# 8·9단계: 데모 API와 성능 비교

mini-redis를 **DB 앞의 캐시**로 쓰는 앱입니다. mini-redis는 `import`가 아니라 **HTTP로** 부릅니다. 데모 API와 mini-redis가 서로 다른 프로세스라는 것, 이게 "상태를 서버 밖으로 뺀다"의 실제 모습입니다.

```
고객 → 데모 API(8001) ─→ mini-redis(8000)   있으면 바로 응답 (hit)
                      └→ 가짜 DB (3초)       없으면 DB 조회 후 캐시에 저장 (miss)
```

## 실행

```bash
python -m mini_redis.server    # 터미널 1 — mini-redis (8000)
python -m demo.app             # 터미널 2 — 데모 API (8001)
python -m bench.benchmark      # 터미널 3 — 성능 비교 (9단계)
```

## API

| 메서드 | 주소 | 하는 일 |
|---|---|---|
| GET | `/products/popular` | 인기 상품 조회 (Cache-Aside). 응답의 `source`가 `cache`/`db` |
| GET | `/products/popular?nocache=1` | 캐시를 건너뛰고 DB로 (9단계 비교용) |
| PUT | `/products/<id>/price` | 가격 수정 → DB 수정 후 캐시 삭제 (무효화) |
| GET | `/products/<id>` | 상품 하나 (가격 확인용, 캐시 안 씀) |
| GET | `/stats` | DB 조회 횟수 |
| POST | `/stats/reset` | DB 조회 횟수 초기화 |
| DELETE | `/cache` | 캐시 비우기 |

## 시연 순서 (장면 ①)

```bash
curl localhost:8001/products/popular        # source=db,    약 3000ms, 키보드 50000원
curl localhost:8001/products/popular        # source=cache, 약 2ms,    키보드 50000원

curl -X PUT localhost:8001/products/1/price \
     -H "Content-Type: application/json" -d '{"price":40000}'
                                            # cache_invalidated=true

curl localhost:8001/products/popular        # source=db,    약 3000ms, 키보드 40000원
curl localhost:8001/products/popular        # source=cache, 약 2ms,    키보드 40000원
```

## 설계 결정

| 결정 | 이유 |
|---|---|
| mini-redis를 HTTP로 호출 | 과제 R8 "외부에서 사용". import하면 같은 프로세스라 공용 저장소를 보여 줄 수 없음 |
| 쓰기 때 캐시를 **덮어쓰지 않고 지움** | 덮어쓰면 "DB 수정"과 "캐시 수정" 순서가 어긋날 때 옛 값이 남을 수 있음. 지우면 다음 읽기가 반드시 DB에서 최신 값을 가져옴 |
| DB 먼저 고치고, 그다음 캐시 삭제 | 캐시를 먼저 지우면, DB를 고치기 전에 다른 요청이 옛 값을 다시 캐시에 채울 수 있음 |
| TTL 60초를 함께 줌 | 무효화를 깜빡해도 60초 뒤엔 사라지는 안전망 |
| mini-redis가 죽어도 DB로 응답 | 캐시는 성능 문제일 뿐 기능 문제가 아님. 통신 실패를 "캐시 미스"로 처리 (Cache-Aside라 가능) |
| 성능 비교는 `?nocache=1`로 | 같은 코드 경로에서 캐시만 빼서, 다른 조건은 똑같이 유지 |
| 첫 조회(미스)와 이후(히트)를 따로 측정 | 섞어서 평균을 내면 측정 횟수에 따라 숫자가 달라져 뜻이 없어짐 |

## 측정 결과 (9단계)

각 5회 측정. 가짜 DB 지연 3초, 캐시 TTL 60초.

| 경우 | 평균 | 최소 | 최대 |
| --- | --- | --- | --- |
| 캐시 미사용 (매번 DB) | 3003.0ms | 3002.7ms | 3003.3ms |
| 캐시 사용 — 첫 조회(미스) | 3007.9ms | - | - |
| 캐시 사용 — 이후(히트) | 4.2ms | 3.8ms | 4.7ms |

- 캐시 히트는 DB 조회보다 약 **711배** 빠릅니다.
- DB 조회 횟수가 5회에서 1회로 줄어, 4건을 막았습니다.
- 첫 조회는 캐시에 값이 없어 느린 것이 정상입니다. 캐시의 효과는 그 다음부터 나옵니다.

> 숫자는 측정 환경마다 다릅니다. `python -m bench.benchmark --markdown`으로 다시 재서 바꿔 넣으세요.
