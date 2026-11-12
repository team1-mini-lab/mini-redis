# 개발 결정 기록

팀 `docs/DESIGN.md`의 단계 번호를 따릅니다. 단계마다 "고른 것 / 고르지 않은 것 / 이유"를 남겨, 7단계 비교에서 그대로 설명할 수 있게 합니다.

## 0단계. 준비

| 결정 | 고른 것 | 고르지 않은 것 | 이유 |
| --- | --- | --- | --- |
| 서버 도구 | Flask 3.1 | 표준 `http.server`, FastAPI | 코드가 짧아 저장소(해시 테이블) 구현에 집중할 수 있고 자료가 많음. FastAPI의 자동 검증은 6단계 입력 검증을 직접 이해할 기회를 가림 |
| 가상 환경 | `.venv` (venv) | 전역 설치 | 팀원과 버전을 맞추고 내 컴퓨터의 다른 프로젝트와 섞이지 않게 함. 버전은 `requirements.txt`에 고정 |
| 폴더 구조 | `mini_redis/server.py`, `mini_redis/store.py`, `tests/` | 파일 하나 | 서버와 저장소를 나누면 접점 1(저장소 함수)이 파일 경계와 같아짐 |

완료 기준: 브라우저에서 `http://127.0.0.1:8000`을 열면 `{"message": "mini-redis is running"}`이 나온다.

## 1단계. 뼈대

| 결정 | 고른 것 | 고르지 않은 것 | 이유 |
| --- | --- | --- | --- |
| 임시 저장소 | `Store` 클래스가 `dict`를 감쌈 | 서버에서 `dict`를 직접 사용 | 2단계에서 `Store` 내부만 해시 테이블로 바꾸면 서버 코드는 그대로 둘 수 있음 |
| 저장소 모양 | 클래스(`Store`)의 메서드 `set/get/delete` | 모듈 함수 세 개 | 테스트마다 새 저장소를 만들어 서로 영향을 주지 않게 할 수 있음 |
| 테스트 도구 | 표준 `unittest` + Flask `test_client` | `pytest` | 추가 설치가 없고, 서버를 띄우지 않고도 API 요청을 보낼 수 있음 |
| 입력 검증 | 하지 않음 (키나 본문이 없으면 Flask 기본 오류) | 지금 400 처리 | 팀 설계상 6단계에서 한 곳에 모아 처리 |

완료 기준: API로 저장한 값이 조회되고, 삭제하면 404가 나온다. (`tests/test_api.py` 3개 통과)

## 0~1단계 검증

### 0단계
- `python -m mini_redis.server` 실행 후 `http://127.0.0.1:8000` 접속 → `{"message": "mini-redis is running"}`

### 1단계: API 요청으로 확인 (curl)

| 확인 | 요청 | 기대 | 결과 |
| --- | --- | --- | --- |
| 저장 | `POST /set` `{"key": "name", "value": "somang"}` | 200 `{"ok": true}` | 통과 |
| 조회 | `GET /get?key=name` | 200 `{"key": "name", "value": "somang"}` | 통과 |
| 삭제 | `DELETE /delete?key=name` | 200 `{"deleted": true}` | 통과 |
| 삭제 후 조회 | `GET /get?key=name` | 404 `{"error": "not found"}` | 통과 |
| 없는 키 삭제 | `DELETE /delete?key=name` | 200 `{"deleted": false}` | 통과 |

### 1단계: 자동 테스트
- `python -m unittest -v` → 3개 통과
  - `test_set_get_delete`: 저장 → 조회 → 삭제 → 404
  - `test_delete_missing_key`: 없는 키 삭제는 200, `deleted: false`
  - `test_set_overwrites`: 같은 키로 다시 저장하면 덮어씀

### 6단계(입력 검증)로 미룬 빈틈

| 입력 | 지금 응답 | 문제 |
| --- | --- | --- |
| `POST /set` 본문에 `key`가 없음 | 500 | 서버 오류로 보임. 잘못된 입력이므로 400이어야 함 |
| `POST /set` `value`가 `null` | 저장 후 조회하면 404 | `get`의 `None`(없음)과 구분되지 않음 |
| `GET /get` 에 `key` 파라미터가 없음 | 400 (HTML 본문) | 다른 응답처럼 JSON이어야 함 |
