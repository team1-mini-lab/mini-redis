# mini_dbms (팀 미니 DBMS 복사본)

[team1-mini-lab/mini-dbms](https://github.com/team1-mini-lab/mini-dbms) main 브랜치 커밋 `d45edad`의
실행에 필요한 파일만 **고치지 않고 그대로** 복사했다.

| 복사한 파일 | 하는 일 |
|---|---|
| `server.py`, `server_guard.py` | `POST /query`로 SQL을 받는 서버 (스레드 4개, 대기열 16칸) |
| `engine.py` | SQL을 해석해 실행하는 엔진. lock 하나로 한 번에 한 문장씩 |
| `minidb/` | 토크나이저, 파서, 실행기, 파일 저장, B+ 트리 인덱스 |

테스트, 문서, 벤치마크, 예제 SQL, 그쪽 `data/schema.json`은 가져오지 않았다.
미니 증권이 쓰는 테이블 모양은 `demo/dbms_schema.json`에 따로 둔다.

## 켜는 법

```bash
python -m demo.dbms_server            # http://127.0.0.1:8020, 데이터는 data/mini-dbms/data/
```

미니 DBMS 서버는 켠 폴더 아래의 `data/schema.json`을 읽는다.
`demo/dbms_server.py`가 그 폴더(`data/mini-dbms/`)를 만들고 스키마를 넣은 뒤, 그 폴더에서 `server.py`를 켠다.

## 새 버전으로 바꾸는 법

mini-dbms main이 바뀌면 위 파일들을 다시 복사하고 이 문서의 커밋 번호를 고친다.
