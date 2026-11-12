# 0단계: 준비

## 목표

응답 하나짜리 서버를 띄웁니다. 브라우저에서 서버 주소를 열었을 때 응답이 나오면 완료입니다.

## 정한 것

| 정한 것 | 이유 |
| --- | --- |
| 서버 도구는 Flask | 가볍고 API 몇 개 만들기에 충분함 |
| `venv`로 가상환경 생성 후 그 안에 Flask 설치 | 프로젝트별로 패키지를 분리함. `venv`는 파이썬에 기본으로 들어 있어 따로 설치하지 않고 만들기만 하면 됨 |
| 서버 포트는 5001 | macOS는 Flask 기본 포트 5000을 AirPlay 수신 기능이 사용해서 충돌함 |

## 구현 순서

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask
mkdir mini_redis && touch mini_redis/__init__.py
```

실행:

```bash
flask --app mini_redis.server run --port 5001 --debug
```

## 완료 확인

브라우저에서 `http://127.0.0.1:5001`을 열면 `{"message": "mini redis is running"}`이 보입니다.

서버 터미널 기록:

```
* Running on http://127.0.0.1:5001
127.0.0.1 - - [12/Nov/2026 18:00:52] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [12/Nov/2026 18:00:52] "GET /favicon.ico HTTP/1.1" 404 -
```

- `GET / 200`: 메인 페이지 응답 성공 → 0단계 완료
- `GET /favicon.ico 404`: 브라우저가 탭 아이콘을 자동으로 요청한 것. 무시해도 됨

## 겪은 문제

| 증상 | 원인과 해결 |
| --- | --- |
| 프롬프트에 `(.venv) (base)`가 같이 뜸 | Anaconda가 `base` 환경을 자동으로 켬. `conda config --set auto_activate_base false`로 끌 수 있음 |
| `pytest`가 `/opt/anaconda3/...` 파이썬으로 실행됨 | `.venv`를 켜지 않은 상태. `source .venv/bin/activate` 후 `pip install pytest` |
| `docs/study`에서 pytest를 돌려 `collected 0 items` | pytest는 현재 폴더 아래에서 테스트를 찾음. 항상 저장소 최상위 폴더에서 실행 |
| curl 명령 뒤 `# 주석`이 주소로 해석되어 `Could not resolve host` | zsh는 대화형 입력에서 `#`을 주석으로 처리하지 않음. 주석을 빼거나 `setopt interactivecomments` |

## 참고

- 처음 메모에 적었던 `http://localhost:8000/docs`는 FastAPI의 기능이라 Flask에는 없습니다. 포트도 5001로 정했습니다.
