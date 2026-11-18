"""실행기: 파서의 문장 객체를 받아 카탈로그로 뜻을 확정하고 저장소에 동작을 시킨다.

카탈로그와 저장소를 둘 다 아는 유일한 층이다. 하는 일은 셋이다.
  - 해석: columns=None 을 실제 컬럼으로, 사용자가 쓴 컬럼 순서를 스키마 순서로.
  - 검증: 테이블과 컬럼이 있는가, 타입이 맞는가.
  - 절차: 어떤 순서로 저장소를 부를까.

실행기는 SQL 문자열도, 파일 포맷도 모른다.

Phase 2 (7~9단계, docs/phase2.md): 테이블마다 B+ 트리(id -> 오프셋)를 메모리에 둔다.
  - 테이블을 처음 쓸 때 한 번 scan 하며 최대 id 와 트리를 함께 만든다. (재시작 복구)
  - INSERT 는 파일에 쓴 뒤 돌려받은 오프셋을 트리에 등록한다.
  - SELECT 는 조건이 `id = 값` 이면 트리로 오프셋을 찾아 그 행만 읽고,
    `id <, <=, >, >= 값` 이면 range_search 로 해당 행들만 읽는다. 그 외에는 전체 스캔한다.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from minidb.ast import Condition, Insert, Literal, Select, Statement
from minidb.bptree import BPlusTree
from minidb.catalog import ID_COLUMN, INT, TEXT, Catalog, Column, Table
from minidb.errors import ExecutionError, TypeMismatchError
from minidb.storage import Row, Storage


@dataclass(frozen=True)
class QueryResult:
    """모든 문장의 결과. SELECT 는 요청한 컬럼과 행, INSERT 는 ("id",) 와 부여된 id 한 행.

    used_index: SELECT 가 B+ 트리로 행을 찾았는지. 결과 '내용' 이 아니라 '경로' 정보라서
    비교(==)에서는 뺀다. 그래야 인덱스로 찾든 스캔으로 찾든 같은 행이면 같은 결과다.
    """

    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    used_index: bool = field(default=False, compare=False)

    @property
    def rowcount(self) -> int:
        return len(self.rows)


_OPERATORS: dict[str, Callable[[object, object], bool]] = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

# id 조건 중 B+ 트리의 range_search 로 처리하는 연산자.
_RANGE_OPS = frozenset({"<", "<=", ">", ">="})


def _id_bounds(op: str, value: int) -> tuple[float, float]:
    """범위 연산자를 range_search 의 양끝 포함 구간 [start, end] 로 바꾼다.

    id 는 정수이므로 `< v` 는 `<= v - 1`, `> v` 는 `>= v + 1` 과 같다.
    열린 쪽은 무한대로 둔다 (정수와 비교 가능).
    """
    if op == "<":
        return float("-inf"), value - 1
    if op == "<=":
        return float("-inf"), value
    if op == ">":
        return value + 1, float("inf")
    return value, float("inf")  # ">="


def _literal_matches(col: Column, value: Literal) -> bool:
    """파서가 넘긴 리터럴(int 또는 str)이 컬럼 타입에 맞는가."""
    if col.type == INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if col.type == TEXT:
        return isinstance(value, str)
    return False


def _type_name(value: Literal) -> str:
    return "숫자" if isinstance(value, int) else "문자열"


class Executor:
    def __init__(self, catalog: Catalog, storage: Storage):
        self.catalog = catalog
        self.storage = storage
        # 테이블별 다음 id 와 B+ 트리. 테이블을 처음 사용할 때 _load 가 한 번 scan 해서 채운다.
        self._next_ids: dict[str, int] = {}
        self._indexes: dict[str, BPlusTree] = {}

    # --- 진입점 -------------------------------------------------------------

    def execute(self, stmt: Statement) -> QueryResult:
        if isinstance(stmt, Insert):
            return self._execute_insert(stmt)
        if isinstance(stmt, Select):
            return self._execute_select(stmt)
        raise ExecutionError(f"알 수 없는 문장: {type(stmt).__name__}")  # 파서가 막는다

    # --- INSERT -------------------------------------------------------------

    def _execute_insert(self, stmt: Insert) -> QueryResult:
        table = self.catalog.table(stmt.table)
        user_values = self._resolve_insert_values(table, stmt)  # 검증은 여기서 전부 끝난다

        index = self._load(table)
        new_id = self._next_ids[table.name]
        row: Row = (new_id, *user_values)  # 스키마 순서. 사용자가 쓴 순서는 사라진다.
        offset = self.storage.table(table.name).append(row)
        # 파일에 쓴 뒤에 번호를 올리고 트리에 등록한다. 쓰기가 실패하면 번호도 트리도 그대로다.
        self._next_ids[table.name] = new_id + 1
        index.insert(new_id, offset)
        return QueryResult(columns=(ID_COLUMN,), rows=((new_id,),))

    def _resolve_insert_values(self, table: Table, stmt: Insert) -> tuple[Literal, ...]:
        """사용자가 준 (컬럼, 값) 을 검증하고, id 를 뺀 스키마 순서의 값 튜플로 만든다."""
        if stmt.columns is None:
            columns = table.user_columns
            if len(stmt.values) != len(columns):
                raise ExecutionError(
                    f"테이블 '{table.name}' 은 값이 {len(columns)}개 필요한데 "
                    f"{len(stmt.values)}개가 왔습니다"
                )
        else:
            columns = tuple(table.column(name) for name in stmt.columns)  # ColumnNotFoundError
            if ID_COLUMN in stmt.columns:
                raise ExecutionError(f"'{ID_COLUMN}' 는 자동으로 부여되므로 지정할 수 없습니다")
            # 파서가 길이와 중복은 이미 확인했다.

        given = dict(zip(columns, stmt.values))

        for col, value in given.items():
            if not _literal_matches(col, value):
                raise TypeMismatchError(
                    f"컬럼 '{col.name}' 은 {col.type} 인데 {_type_name(value)} {value!r} 가 왔습니다"
                )

        # NULL 이 없으므로 모든 사용자 컬럼에 값이 있어야 한다.
        missing = [c.name for c in table.user_columns if c not in given]
        if missing:
            raise ExecutionError(f"컬럼 {', '.join(repr(m) for m in missing)} 의 값이 없습니다")

        return tuple(given[c] for c in table.user_columns)

    def _load(self, table: Table) -> BPlusTree:
        """테이블을 처음 건드릴 때 한 번 scan 해 최대 id 와 B+ 트리를 함께 만든다.

        트리는 메모리에만 있으므로 실행기를 새로 만들 때마다(= CLI 를 실행할 때마다) 다시 만든다.
        INSERT 든 SELECT 든 먼저 오는 쪽이 부른다. 이후에는 만들어 둔 것을 돌려준다.
        """
        if table.name not in self._indexes:
            index = BPlusTree()
            max_id = 0
            for offset, row in self.storage.table(table.name).scan():
                row_id = int(row[0])
                index.insert(row_id, offset)
                max_id = max(max_id, row_id)
            self._indexes[table.name] = index
            self._next_ids[table.name] = max_id + 1
        return self._indexes[table.name]

    # --- SELECT -------------------------------------------------------------

    def _execute_select(self, stmt: Select) -> QueryResult:
        table = self.catalog.table(stmt.table)

        if stmt.columns is None:
            out_names = table.column_names
        else:
            for name in stmt.columns:
                table.column(name)  # ColumnNotFoundError
            out_names = stmt.columns
        out_indexes = [table.column_index(n) for n in out_names]

        predicate = self._make_predicate(table, stmt.where)  # 컬럼, 타입 검증은 경로와 무관하게 먼저
        table_file = self.storage.table(table.name)

        # 경로 선택 (9단계). 가장 단순한 옵티마이저: 조건이 id 에 대한 `=` 또는 범위일 때 인덱스를 쓴다.
        # `!=` 는 거의 모든 행이 해당하므로 스캔한다.
        cond = stmt.where
        candidates: Iterable[Row]
        if cond is not None and cond.column == ID_COLUMN and cond.op == "=":
            offset = self._load(table).search(cond.value)
            # 오프셋 0 (첫 행) 도 유효하므로 `is None` 으로 구별한다.
            candidates = [] if offset is None else [table_file.read_at(offset)]
            used_index = True
        elif cond is not None and cond.column == ID_COLUMN and cond.op in _RANGE_OPS:
            start, end = _id_bounds(cond.op, cond.value)
            pairs = self._load(table).range_search(start, end)
            # 오프셋 순으로 읽어 스캔과 같은 순서(파일 순서)로 돌려준다.
            # 경계 포함 여부는 아래 predicate 가 한 번 더 확인한다.
            candidates = (table_file.read_at(off) for off in sorted(off for _key, off in pairs))
            used_index = True
        else:
            candidates = (row for _offset, row in table_file.scan())  # 한 행씩 흘려보낸다
            used_index = False

        rows = [tuple(row[i] for i in out_indexes) for row in candidates if predicate(row)]
        return QueryResult(columns=tuple(out_names), rows=tuple(rows), used_index=used_index)

    def _make_predicate(self, table: Table, cond: Condition | None) -> Callable[[Row], bool]:
        """조건을 검증하고 '행을 받아 참/거짓을 돌려주는 함수' 를 만든다."""
        if cond is None:
            return lambda row: True

        col = table.column(cond.column)  # ColumnNotFoundError
        if not _literal_matches(col, cond.value):
            raise TypeMismatchError(
                f"컬럼 '{col.name}' 은 {col.type} 인데 {_type_name(cond.value)} "
                f"{cond.value!r} 와 비교했습니다"
            )
        index = table.column_index(cond.column)
        compare = _OPERATORS[cond.op]  # 파서가 여섯 개만 넘긴다
        value = cond.value
        return lambda row: compare(row[index], value)
