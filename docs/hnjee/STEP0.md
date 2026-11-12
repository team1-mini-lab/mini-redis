# 0단계: 준비

## 목표

응답 하나짜리 서버를 띄웁니다. 브라우저에서 서버 주소를 열었을 때 응답이 나오면 완료입니다.

## 이 단계에서 정한 것

| 관련 코드 | 정한 것 | 이유 |
| --- | --- | --- |
| `server.py` 맨 위 (`Flask(__name__)`) | 서버 도구는 Flask | 코드가 짧고, 6단계의 400 응답을 직접 작성하기 쉬움 |
| `server.py` 파일 구성 | 0단계는 `server.py` 하나로 시작하고, `store.py`는 1단계에서 추가 | 저장소가 아직 없으므로 빈 파일을 미리 만들 이유가 없음 |
| `server.py` 맨 아래 (`app.run`) | 서버 포트는 8000 | macOS에서는 Flask 기본 포트 5000을 AirPlay 수신 기능이 사용해 충돌할 수 있음 |
| 개발 환경 (`.venv/`, `requirements.txt`) | 패키지는 프로젝트 폴더 안의 가상환경(`.venv`)에 설치하고 `requirements.txt`에 기록 | 시스템 파이썬을 건드리지 않고, 같은 환경을 다시 만들 수 있음 |

[DECISIONS.md](./DECISIONS.md)에도 같은 내용이 모여 있습니다.

## 만드는 파일

```
mini-redis/
├── .venv/              가상환경 (커밋하지 않음)
├── .gitignore          .venv, __pycache__, .DS_Store 제외
├── requirements.txt    flask
└── server.py           응답 하나짜리 서버
```

## 구현 순서

모든 명령은 `mini-redis` 폴더에서 실행합니다.

### 1. 가상환경 만들고 켜기

```bash
python3 -m venv .venv
source .venv/bin/activate
```

켜지면 터미널 줄 맨 앞에 `(.venv)`가 붙습니다. 터미널을 새로 열 때마다 `source .venv/bin/activate`를 다시 실행해야 합니다.

### 2. Flask 설치

```bash
pip install -r requirements.txt
```

### 3. 서버 실행

```bash
python server.py
```

`Running on http://127.0.0.1:8000`이 보이면 서버가 켜진 것입니다. 끌 때는 `Ctrl + C`를 누릅니다.

## 완료 테스트

서버를 켜 둔 채로 확인합니다.

| 확인 방법 | 기대 결과 |
| --- | --- |
| 브라우저에서 `http://127.0.0.1:8000` 열기 | `{"message": "mini-redis is running"}`이 보임 |
| 새 터미널에서 `curl -i http://127.0.0.1:8000` | 첫 줄이 `HTTP/1.1 200 OK`이고 본문에 같은 JSON이 나옴 |
| 서버를 켠 터미널 보기 | `GET / HTTP/1.1" 200` 형태의 요청 기록이 한 줄씩 찍힘 |

세 가지가 모두 맞으면 0단계 완료입니다.

## 문제가 생기면

| 증상 | 해결 |
| --- | --- |
| `ModuleNotFoundError: No module named 'flask'` | 가상환경이 꺼진 상태. `source .venv/bin/activate` 후 다시 실행 |
| `Address already in use` | 8000 포트를 다른 프로그램이 사용 중. `lsof -i :8000`으로 확인하고 그 프로그램을 끄기 |
| 코드를 고쳤는데 반영이 안 됨 | 저장했는지 확인. `debug=True`라서 저장하면 서버가 자동으로 다시 시작됨 |

## 코드에서 알아 둘 것

- `@app.get("/")`: 주소 `/`로 GET 요청이 오면 바로 아래 함수를 실행하라는 뜻입니다. 1단계에서 `/set`, `/get`, `/delete`를 같은 방식으로 추가합니다.
- 함수가 `dict`를 돌려주면 Flask가 JSON 응답으로 바꿔 줍니다.
- `debug=True`: 코드를 저장하면 서버가 자동으로 다시 시작되고, 오류가 나면 자세한 내용을 보여 줍니다. 개발할 때만 씁니다.
