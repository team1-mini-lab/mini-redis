# 구조

[← README로 돌아가기](../../README.md)

```
데모 API (demo/app.py, 웹 서버 여러 대)
   │ HTTP
   ▼
mini_redis/server.py   요청 해석 → 입력 검증 → 저장소 호출 → JSON 응답
   │ set / get / delete
   ▼
mini_redis/store.py    lock 하나 · (값, 만료 시점) 묶음 · 지연 삭제
   │ put / get / remove
   ▼
mini_redis/hashtable.py  FNV-1a 해시 · 체이닝 · 0.75 넘으면 2배 확장
```

각 층은 아래 층의 함수만 알고 내부는 모릅니다. 그래서 3가지 API 요청을 테스트 한 뒤 임시용으로 쓰고 있던 파이썬 `dict`를 직접 만든 해시 테이블로 바꿀 때 `server.py`는 변경하지 않았습니다.

| 폴더 | 내용 |
| --- | --- |
| `mini_redis/` | mini-redis 본체 |
| `demo/` | 캐시를 쓰는 데모 API, 가짜 DB(SQLite, 3초 지연), 시연 스크립트 |
| `bench/` | 캐시 사용·미사용 응답 시간 비교 |
| `stock/` | 데모 API를 화면으로 보여 주는 주식 매수 페이지 (거래량 상위 종목, 시세 변경, 캐시 켜고 끄기) |
| `deploy/` | 세 서버(mini-redis, 데모 API, 주식 화면)를 한 번에 띄우는 배포용 시작 스크립트 |
| `tests/` | 단위·기능·동시 요청 테스트 (66개) |
| `docs/` | 설계 문서, 요구사항, 팀 결정 기록, 실제 Redis와 비교 |
