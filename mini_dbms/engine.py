"""엔진: 서버(와 확인 스크립트)가 SQL을 넘기는 단 하나의 입구(execute).

SQL을 읽고 검사하고 실행하고 저장하는 일, B+ 트리로 찾는 일은 Phase 1·2의 minidb가 맡는다
(lexer → parser → catalog → executor(+ bptree) → storage).
엔진이 하는 일은 셋뿐이다.
  - lock (Phase 3, 16단계): execute 전체를 한 번에 한 스레드만 지나가게 한다.
    minidb의 Executor는 스레드 안전하지 않다 (다음 id, 테이블별 B+ 트리, 처음 쓸 때 트리를 만드는 _load,
    파일 append에 잠금이 없음). 그래서 Executor를 부르는 일은 모두 이 lock 안에서만 한다.
  - Executor 하나를 서버 전체가 같이 쓴다. B+ 트리는 Executor 메모리에만 있어서,
    요청마다 새로 만들면 매번 파일 전체를 다시 읽는다 (100만 건이면 약 1.9초).
  - 결과를 서버가 읽는 dict 모양으로 바꾼다 (접점 1).
켤 때(__init__)는 테이블마다 B+ 트리를 미리 만들어 둔다 (예열). 첫 요청이 lock을 오래 잡지 않게.
"""
import functools
import threading
from pathlib import Path

from minidb.ast import Select
from minidb.catalog import Catalog
from minidb.errors import MiniDBError, StorageError
from minidb.executor import Executor
from minidb.parser import parse
from minidb.storage import Storage


def locked(method):
    """Phase 3(16단계): 함수를 lock 안에서 실행한다.

    함수 위에 @locked를 붙이면, 그 아랫줄 함수가 method로 들어온다 (지금은 execute).
    """
    @functools.wraps(method)                        # wrapper에 원래 함수 이름(execute)을 붙여 줌
    def wrapper(self, *args, **kwargs):             # 받은 값은 그대로 method에 넘김
        with self._lock:                            # 잠금 (이미 잠겨 있으면 풀릴 때까지 기다림)
            return method(self, *args, **kwargs)    # 우리가 쓴 execute를 실행. 끝나면 자동으로 풂
    return wrapper


class Engine:
    def __init__(self, data_dir):
        self._lock = threading.Lock()   # Phase 3(16단계): execute를 부를 때마다 이 lock을 잠근다
        schema_path = Path(data_dir) / "schema.json"
        if not schema_path.exists():    # 서버가 "데이터 폴더를 열 수 없습니다"로 알려 주게 OSError로
            raise FileNotFoundError(f"스키마 파일이 없습니다: {schema_path}")
        self.catalog = Catalog.load(schema_path)
        self.schema = {                 # 서버의 테스트 페이지가 보여 주는 테이블 모양
            name: [[c.name, c.type] for c in self.catalog.table(name).columns]
            for name in self.catalog.table_names
        }
        self.storage = Storage(data_dir, self.catalog)
        self.executor = Executor(self.catalog, self.storage)   # 서버 전체가 이것 하나를 같이 씀
        # 예열: 실행기는 테이블을 처음 쓸 때 파일을 읽어 B+ 트리를 만든다 (100만 건이면 약 1.9초).
        # 첫 요청이 그 일을 하면 그동안 lock을 잡아 다른 요청도 모두 기다리므로, 요청을 받기 전에 미리 만든다
        for name in self.catalog.table_names:
            self.executor.execute(parse(f"SELECT id FROM {name} WHERE id = 0;")[0])

    @locked
    def execute(self, sql, stop_on_error=True):
        """SQL 전체를 해석하고, 문장마다 실행해 결과 dict 목록을 돌려준다.

        - 문법 오류: 아무 문장도 실행하지 않는다 (minidb 설계, step02).
        - 실행 오류(없는 열 등): 결과에 담고, 기본은 그 문장에서 멈춘다 (step04 결정 2). 앞 문장은 되돌리지 않음.
        - 파일 손상(StorageError)과 그 밖의 예외: 잡지 않고 위로 올린다 → 서버는 500.
        """
        try:
            statements = parse(sql)
        except MiniDBError as e:
            return [{"type": "error", "stage": "parse",
                     "message": f"문법 오류라 아무 문장도 실행하지 않았습니다: {e}"}]
        results = []
        for stmt in statements:
            try:
                results.append(self._run(stmt))
            except StorageError:        # 손님이 고칠 수 없는 데이터 문제 → 위로 → 500
                raise
            except MiniDBError as e:    # SQL이 틀림 → 결과에 담음 → 서버는 400
                results.append({"type": "error", "message": str(e)})
                if stop_on_error:
                    break
        return results

    def _run(self, stmt):
        result = self.executor.execute(stmt)
        if isinstance(stmt, Select):
            return {"type": "select", "columns": list(result.columns),
                    "rows": [list(row) for row in result.rows], "used_index": result.used_index}
        return {"type": "insert", "id": result.rows[0][0]}

    def close(self):
        self.storage.close()
