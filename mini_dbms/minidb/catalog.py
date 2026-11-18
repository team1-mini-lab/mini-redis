"""스키마 카탈로그: 어떤 테이블에 어떤 컬럼이 어떤 타입으로 있는가.

카탈로그는 data/schema.json 을 읽어서 만든다. CREATE TABLE 을 구현하지 않으므로
이 파일은 사람이 직접 편집하고, 처리기는 읽기만 한다. 사람이 편집하는 파일이라
읽을 때 규칙을 검사하고, 어기면 SchemaError 를 낸다.

카탈로그는 테이블 파일의 경로나 저장 포맷을 모른다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from minidb.errors import ColumnNotFoundError, SchemaError, TableNotFoundError

# 지원하는 컬럼 타입. 비교와 직렬화 규칙은 뒤 단계에서 이 이름을 기준으로 정한다.
INT = "INT"
TEXT = "TEXT"
TYPES = frozenset({INT, TEXT})

# 모든 테이블의 첫 컬럼은 이 이름과 타입이어야 한다. 값은 처리기가 자동 부여한다.
ID_COLUMN = "id"

# 식별자 규칙: 소문자로 시작, 소문자/숫자/밑줄. SQL 방언이 식별자를 소문자로
# 정규화하므로 카탈로그도 같은 규칙을 따른다.
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # INT 또는 TEXT


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    @property
    def user_columns(self) -> tuple[Column, ...]:
        """사용자가 INSERT 로 값을 넣는 컬럼. id 는 자동 부여이므로 제외한다."""
        return self.columns[1:]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise ColumnNotFoundError(f"테이블 '{self.name}' 에 컬럼 '{name}' 이 없습니다")

    def column_index(self, name: str) -> int:
        """행(튜플) 안에서 해당 컬럼이 몇 번째인지. 실행기가 값을 꺼낼 때 쓴다."""
        for i, c in enumerate(self.columns):
            if c.name == name:
                return i
        raise ColumnNotFoundError(f"테이블 '{self.name}' 에 컬럼 '{name}' 이 없습니다")


class Catalog:
    def __init__(self, tables: dict[str, Table]):
        self._tables = tables

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._tables)

    def table(self, name: str) -> Table:
        try:
            return self._tables[name]
        except KeyError:
            raise TableNotFoundError(f"테이블 '{name}' 이 없습니다") from None

    @classmethod
    def load(cls, path: str | Path) -> Catalog:
        """schema.json 을 읽어 검증한 뒤 Catalog 를 만든다."""
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SchemaError(f"스키마 파일이 없습니다: {path}") from None
        except json.JSONDecodeError as e:
            raise SchemaError(f"스키마 파일이 올바른 JSON 이 아닙니다: {path} ({e})") from None
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: object) -> Catalog:
        """파싱된 JSON 객체에서 Catalog 를 만든다. 테스트에서 파일 없이 쓸 수 있다."""
        if not isinstance(raw, dict):
            raise SchemaError("스키마의 최상위는 테이블 이름을 키로 갖는 객체여야 합니다")

        tables: dict[str, Table] = {}
        for table_name, spec in raw.items():
            tables[table_name] = _parse_table(table_name, spec)
        return cls(tables)


def _parse_table(name: str, spec: object) -> Table:
    if not _IDENTIFIER.match(name):
        raise SchemaError(f"테이블 이름 '{name}' 은 소문자 식별자여야 합니다")
    if not isinstance(spec, dict) or not isinstance(spec.get("columns"), list):
        raise SchemaError(f"테이블 '{name}' 에 columns 목록이 없습니다")

    columns = tuple(_parse_column(name, c) for c in spec["columns"])

    if len(columns) < 2:
        raise SchemaError(f"테이블 '{name}' 은 id 외에 컬럼이 하나 이상 있어야 합니다")
    first = columns[0]
    if first.name != ID_COLUMN or first.type != INT:
        raise SchemaError(f"테이블 '{name}' 의 첫 컬럼은 'id INT' 여야 합니다")

    seen: set[str] = set()
    for c in columns:
        if c.name in seen:
            raise SchemaError(f"테이블 '{name}' 에 컬럼 '{c.name}' 이 중복됩니다")
        seen.add(c.name)

    return Table(name=name, columns=columns)


def _parse_column(table_name: str, spec: object) -> Column:
    if not isinstance(spec, dict) or "name" not in spec or "type" not in spec:
        raise SchemaError(f"테이블 '{table_name}' 의 컬럼 정의에는 name 과 type 이 있어야 합니다")
    col_name, col_type = spec["name"], spec["type"]
    if not isinstance(col_name, str) or not _IDENTIFIER.match(col_name):
        raise SchemaError(f"테이블 '{table_name}' 의 컬럼 이름 '{col_name}' 은 소문자 식별자여야 합니다")
    if col_type not in TYPES:
        raise SchemaError(
            f"테이블 '{table_name}' 의 컬럼 '{col_name}' 타입 '{col_type}' 은 지원하지 않습니다 "
            f"(가능: {', '.join(sorted(TYPES))})"
        )
    return Column(name=col_name, type=col_type)
