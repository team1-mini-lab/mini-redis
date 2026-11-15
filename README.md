# mini-redis

해시 테이블을 직접 구현한 키-값 저장소를 HTTP 서버로 띄우고, 웹 서버 여러 대가 함께 쓰는 캐시로 써 보는 프로젝트입니다.

크래프톤 정글 11주차 팀 과제 · 김은기, 이현지, 김소망 · Python 3, Flask

## 목차

1. [왜 만들었나: 서버가 여러 대가 되면](#1-왜-만들었나-서버가-여러-대가-되면)
2. [실행 방법](#2-실행-방법)
3. [구조](#3-구조)
4. [API](#4-api)
5. [해시 테이블은 이렇게 동작한다](#5-해시-테이블은-이렇게-동작한다)
6. [성능 비교](#6-성능-비교)
7. [테스트](#7-테스트)
8. [실제 Redis와 다른 점](#8-실제-redis와-다른-점)
9. [결정 기록과 문서 모음](#9-결정-기록과-문서-모음)

## 1. 왜 만들었나: 서버가 여러 대가 되면

서버가 한 대라면 캐시는 서버 메모리의 `dict` 하나로 충분합니다. 사용자가 늘어 서버가 여러 대가 되면, 서버마다 따로 들고 있는 캐시 때문에 문제가 생깁니다.

| 장면 | 로컬 캐시 (서버마다 따로) | mini-redis (서버 밖 한 곳) |
| --- | --- | --- |
| ① 가격이 왔다 갔다 | 서버 A에서 시세를 바꿔도 서버 B는 옛 가격 50,000원 | A, B 모두 40,000원 |
| ② 로그인이 풀림 | A에서 로그인했는데 B는 모름 (401) | B도 알아봄 |
| ③ 배포하면 DB가 몰림 | 서버를 재시작하면 캐시가 사라져 DB로 감 | 캐시가 서버 밖에 있어 그대로 |
| ④ 같은 데이터를 서버 수만큼 저장 | 서버마다 DB를 따로 조회 (DB 4번) | 한 번 채우면 모두 씀 (DB 2번) |
| ⑤ 함께 세야 하는 값이 틀림 | 재고 1개가 두 번 팔림 | 아직 미구현 (12단계 원자적 증가) |

다섯 문제의 공통 원인은 **상태가 각 서버의 메모리에 묶여 있다는 것**이고, Redis의 답은 **상태를 서버 밖 한 곳으로 빼는 것**입니다. 그 한 곳에서 키로 값을 찾는 입구가 이 프로젝트에서 직접 만든 해시 테이블입니다.

위 표는 `python -m demo.scenario`로 그대로 재현됩니다 (8단계 데모, 웹 서버 2대가 같은 mini-redis 사용).

## 2. 실행 방법

배포된 화면: https://mini-stock-tu7t.onrender.com (Render 무료, 15분 동안 아무도 안 쓰면 잠들어 첫 접속이 30초쯤 걸립니다)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

| 하고 싶은 것 | 명령 |
| --- | --- |
| mini-redis 서버 띄우기 (포트 8000) | `python -m mini_redis.server` |
| 서버 두 대 시연 (로컬 캐시 vs mini-redis, 약 20초) | `python -m demo.scenario` |
| 시연을 한 단계씩 (발표용) | `python -m demo.scenario --step` |
| 성능 비교 (mini-redis, 데모 API를 먼저 띄운 뒤) | `python -m demo.app` → `python -m bench.benchmark` |
| 주식 화면 (데모 API를 먼저 띄운 뒤, 포트 8010) | `python -m stock.server` |
| 세 서버를 한 번에 (배포와 같은 방식) | `python -m deploy.start` |
| 전체 테스트 | `python -m unittest -v` |

직접 요청을 보내 보려면 (mini-redis를 띄운 상태에서):

```bash
curl -X POST localhost:8000/set -H "Content-Type: application/json" -d '{"key":"name","value":"mini","ttl":5}'
curl "localhost:8000/get?key=name"        # 200 {"key":"name","value":"mini"}
# 5초 뒤
curl "localhost:8000/get?key=name"        # 404 {"error":"not found"}
```

## 3. 구조

```
데모 API (demo/app.py, 웹 서버 여러 대)
   │ HTTP                                       접점 2
   ▼
mini_redis/server.py   요청 해석 → 입력 검증 → 저장소 호출 → JSON 응답
   │ set / get / delete                         접점 1
   ▼
mini_redis/store.py    lock 하나 · (값, 만료 시점) 묶음 · 지연 삭제
   │ put / get / remove
   ▼
mini_redis/hashtable.py  FNV-1a 해시 · 체이닝 · 0.75 넘으면 2배 확장
```

각 층은 바로 아래 층의 함수만 알고, 아래 층의 내부를 모릅니다. 그래서 2단계에서 임시 `dict`를 직접 만든 해시 테이블로 바꿀 때 `server.py`는 한 줄도 바뀌지 않았습니다.

| 폴더 | 내용 |
| --- | --- |
| `mini_redis/` | mini-redis 본체 (0~6단계) |
| `demo/` | 캐시를 쓰는 데모 API, 가짜 DB(SQLite, 3초 지연), 시연 스크립트 (8단계) |
| `bench/` | 캐시 사용·미사용 응답 시간 비교 (9단계) |
| `stock/` | 데모 API를 화면으로 보여 주는 주식 매수 페이지 (거래량 상위 종목, 시세 변경, 캐시 켜고 끄기) |
| `deploy/` | 세 서버(mini-redis, 데모 API, 주식 화면)를 한 번에 띄우는 배포용 시작 스크립트 |
| `tests/` | 단위·기능·동시 요청 테스트 (63개) |
| `docs/` | 설계 문서, 요구사항, 팀 결정 기록, 실제 Redis와 비교 |

## 4. API

| 동작 | 요청 | 성공 | 실패 |
| --- | --- | --- | --- |
| 저장 | `POST /set` 본문 `{"key": "name", "value": "mini", "ttl": 600}` (`ttl`은 선택, 초) | 200 `{"ok": true}` | 400 |
| 조회 | `GET /get?key=name` | 200 `{"key": "name", "value": "mini"}` | 404 (없거나 만료됨), 400 |
| 삭제 | `DELETE /delete?key=name` | 200 `{"deleted": true}` 또는 `{"deleted": false}` | 400 |

- 만료된 키는 없는 키와 똑같이 다룹니다 (조회 404, 삭제 `deleted: false`).
- 없는 키를 삭제해도 실패가 아닙니다. 삭제의 목적인 "그 키가 없는 상태"는 이미 이뤄져 있기 때문입니다.
- 잘못된 입력은 모두 JSON 400입니다: 빈 키, `value`가 `null`, `ttl`이 0 이하·`true`·10년 초과, 모르는 칸(`"tll"` 같은 오타), JSON이 아닌 본문. 없는 주소와 잘못된 메서드도 JSON 404·405로 답합니다.

데모 API의 주소 목록은 [demo/README.md](demo/README.md#api)에 있습니다.

## 5. 해시 테이블은 이렇게 동작한다

| 질문 | 우리 답 | 이유 |
| --- | --- | --- |
| 키를 어느 칸에? | FNV-1a 64비트 해시 % 칸 수 | 글자 순서가 결과에 반영되고 실행할 때마다 값이 같아 충돌을 재현할 수 있음 |
| 같은 칸에 두 키가 오면? | 체이닝: 노드(`key`, `value`, `next`)를 연결 리스트로 | 삭제가 "끊어내기"로 끝남. 개방 주소법은 삭제 표시가 필요 |
| 새 노드는 어디에? | 체인 맨 앞 | 방금 넣은 값을 곧바로 다시 읽는 캐시에 유리 |
| 언제 칸을 늘리나? | 키 수 ÷ 칸 수 > 0.75 | 체인 평균 길이를 1 아래로 유지 |
| 얼마나 늘리나? | 2배, 노드를 새 칸으로 옮겨 붙임 | 곱해서 늘려야 키 하나당 옮기는 비용이 일정 |
| 만료는? | `store.py`가 `(값, 만료 시점)`을 값으로 저장, 조회할 때 확인해 지움 | 해시 테이블은 만료를 몰라도 됨 |
| 동시 요청은? | `store.py`에 lock 하나로 `set`·`get`·`delete`를 감쌈 | "만료 확인 → 삭제" 사이에 다른 `set`이 끼어들지 못함 |

## 6. 성능 비교

같은 데모 API에서 `?nocache=1`로 캐시만 빼고 인기 상품 조회를 각 10회 측정했습니다.

측정 조건: 가짜 DB 지연 3초(`DEMO_DB_DELAY`), 캐시 TTL 60초, 한 컴퓨터에서 mini-redis·데모 API·측정 스크립트 실행, 클라이언트에서 잰 응답 시간.

| 경우 | 평균 | 최소 | 최대 |
| --- | --- | --- | --- |
| 캐시 미사용 (매번 DB) | 3007.0ms | 3005.1ms | 3017.7ms |
| 캐시 사용, 첫 조회 (미스) | 3009.6ms | - | - |
| 캐시 사용, 이후 (히트) | 4.1ms | 2.9ms | 6.2ms |

- 캐시 히트는 DB 조회보다 약 **700배** 빠릅니다. 이 배수는 가짜 DB에 넣은 지연 시간에 따라 달라지므로, 더 중요한 숫자는 아래의 DB 조회 횟수입니다.
- DB 조회가 10회에서 1회로 줄었습니다. 캐시의 원래 목적은 DB 보호입니다.
- 다시 재려면 `python -m bench.benchmark --markdown`.

## 7. 테스트

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

## 8. 실제 Redis와 다른 점

| 항목 | 실제 Redis | 우리 구현 | 이유 |
| --- | --- | --- | --- |
| 통신 | TCP 위 자체 프로토콜(RESP) | HTTP + JSON | `curl`로 바로 확인, 과제의 "외부에서 사용" |
| 동시성 | 싱글 스레드 | Flask 멀티 스레드 + lock 하나 | Flask가 요청을 스레드로 받음. lock으로 같은 효과 |
| 해시 함수 | SipHash + 무작위 시드 | FNV-1a 고정 | 충돌 재현. 해시 플러딩 방어는 범위 밖 |
| 확장 | 두 테이블로 조금씩 옮김 | 한 번에 2배 | 설명이 단순하고 우리 규모에선 멈춤이 체감되지 않음 |
| 만료 삭제 | 지연 삭제 + 주기적 무작위 검사 | 지연 삭제만 | 13단계(선택) |
| 원자적 증가 | `INCR`, `DECR` | 없음 | 12단계(선택) |
| 파일 저장 | RDB, AOF | 없음 | 14단계(선택) |

자세한 비교와 예상 질문은 [docs/eungi/REDIS_COMPARISON.md](docs/eungi/REDIS_COMPARISON.md)에 있습니다.

## 9. 결정 기록과 문서 모음

| 보고 싶은 것 | 문서 |
| --- | --- |
| 요구사항(R1~R12)과 개발 단계(0~14), 접점, 결정 참고사항 | [docs/DESIGN.md](docs/DESIGN.md) |
| 과제 원문과 팀 학습 원칙 | [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) |
| 팀 결정 기록: 세 사람이 단계별로 고른 것, 주고받은 피드백, 기준 구현을 고른 이유 | [docs/DECISIONS.md](docs/DECISIONS.md) |
| 그중 단계별 선택 비교 (0~6단계) | [DECISIONS.md 3장](docs/DECISIONS.md#3-단계별로-세-사람이-고른-것) |
| 그중 기준 구현을 고른 과정 | [DECISIONS.md 5장](docs/DECISIONS.md#5-기준-구현을-고른-과정) |
| 그중 알고도 남겨 둔 약점 | [DECISIONS.md 7장](docs/DECISIONS.md#7-알고도-남겨-둔-약점) |
| 데모 API 설계, TTL 60초를 정한 근거, 측정 방법 (8·9단계) | [demo/README.md](demo/README.md) |
| 실제 Redis와 비교, 예상 질문 | [docs/eungi/REDIS_COMPARISON.md](docs/eungi/REDIS_COMPARISON.md) |
