# 테스트

[← README로 돌아가기](../../README.md)

```bash
python -m unittest -v
```

| 파일 | 확인하는 것 |
| --- | --- |
| `test_api.py` | 저장 → 조회 → 삭제 → 404, 없는 키 삭제, 덮어쓰기, 여러 키 독립, 응답 모양 |
| `test_concurrent_http.py` | 실제 HTTP 서버에 여러 클라이언트가 동시에 요청해도 유실·500 없음, 같은 키 삭제는 한 번만 `true` |
| `test_edge_cases.py` | ttl 다시 주면 연장, 만료 뒤 ttl 없이 저장하면 영구, 아주 작은 ttl, 같은 키가 쿼리에 두 번, 특이한 키, 크기 제한 없음 |
| `test_hashtable.py` | 충돌 체인의 앞·중간·끝 삭제, FNV-1a 공식 값, 0.75 경계 확장, 키 10만 개 |
| `test_expiry.py` | 가짜 시계로 만료 경계(정확히 그 시각), 덮어쓰면 만료 초기화, 확장 후에도 만료 유지 |
| `test_lock.py` | 스레드 8개 × 2,000개 동시 저장에 유실 없음, 만료 확인과 삭제 사이에 `set`이 끼어들지 못함 |
| `test_validation.py` | 입력 검증 규칙, 1단계 때 찾은 빈틈 3개, JSON 404·405 |
| `test_demo.py` | 캐시 어사이드, 무효화, 서버 두 대 장면, 캐시가 죽어도 DB로 응답, 무효화를 놓쳐도 TTL이 지나면 맞아짐 |
