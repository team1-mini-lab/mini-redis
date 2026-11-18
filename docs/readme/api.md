# API

[← README로 돌아가기](../../README.md)

| 동작 | 요청 | 성공 | 실패 |
| --- | --- | --- | --- |
| 저장 | `POST /set` 본문 `{"key": "name", "value": "mini", "ttl": 600}` (`ttl`은 선택, 초) | 200 `{"ok":true}` | 400 |
| 조회 | `GET /get?key=name` | 200 `{"key":"name","value":"mini"}` | 404 (없거나 만료됨), 400 |
| 삭제 | `DELETE /delete?key=name` | 200 `{"deleted":true}` 또는 `{"deleted":false}` | 400 |
| 1 늘리기 | `POST /incr` 본문 `{"key": "views"}` | 200 `{"key":"views","value":1}` | 400 (정수가 아닌 값, 빈 키, 모르는 칸) |
| 1 줄이기 | `POST /decr` 본문 `{"key": "stock"}` | 200 `{"key":"stock","value":0}` | 400 |

- 만료된 키는 없는 키와 똑같이 다룹니다 (조회 404, 삭제 `deleted: false`).
- `incr`·`decr`은 읽기·계산·저장을 저장소 안에서 한 번에 하는 원자적 명령입니다. 없는 키는 0에서 시작하고, 만료 시간은 그대로 두며, 0 밑으로도 내려갑니다.
- 없는 키를 삭제해도 실패가 아닙니다. 삭제의 목적인 "그 키가 없는 상태"는 이미 이뤄져 있기 때문입니다.
- 잘못된 입력은 모두 JSON 400입니다: 빈 키, `value`가 `null`, `ttl`이 0 이하·`true`·10년 초과, 모르는 칸(`"tll"` 같은 오타), JSON이 아닌 본문. 없는 주소와 잘못된 메서드도 JSON 404·405로 답합니다.

데모 API의 주소 목록은 [demo/README.md](../../demo/README.md#api)에 있습니다.
