"""저장소: 행을 테이블 파일에 쓰고 읽는다.

파일 포맷 (docs/steps/step03-storage.md 2절):
  - 한 행은 한 줄. 값 사이는 탭. 줄 끝은 \\n.
  - 값 안의 탭, 줄바꿈, 백슬래시는 \\t, \\n, \\\\ 로 이스케이프한다.
  - INT 는 십진수 문자열, TEXT 는 이스케이프한 UTF-8.
  - 파일은 바이너리 모드. 줄이 시작하는 바이트 위치가 그 행의 오프셋이다.

저장소는 SQL 을 모른다. 실행기가 시킬 수 있는 일은 append, scan, read_at 셋뿐이다.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from minidb.catalog import INT, TEXT, Catalog, Table
from minidb.errors import StorageError

Row = tuple[int | str, ...]

_SEP = b"\t"
_EOL = b"\n"


# --- 포맷: 행 <-> 바이트 -------------------------------------------------------
# 파일을 전혀 모르는 순수 함수. 포맷 규칙은 전부 여기에 있다.


def _escape(text: str) -> str:
    # 백슬래시를 먼저 바꿔야 한다. 뒤에 바꾸면 \t 를 만들려고 넣은 백슬래시까지 다시 바뀐다.
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def _unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "t":
                out.append("\t")
            elif nxt == "n":
                out.append("\n")
            elif nxt == "\\":
                out.append("\\")
            else:
                raise StorageError(f"알 수 없는 이스케이프 \\{nxt}")
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def encode_row(table: Table, row: Row) -> bytes:
    """행 튜플을 줄바꿈까지 포함한 한 줄의 바이트로 만든다."""
    if len(row) != len(table.columns):
        raise StorageError(
            f"테이블 '{table.name}' 은 컬럼이 {len(table.columns)}개인데 값이 {len(row)}개입니다"
        )
    fields: list[str] = []
    for col, value in zip(table.columns, row):
        if col.type == INT:
            # bool 은 int 의 하위 타입이라 따로 막는다.
            if not isinstance(value, int) or isinstance(value, bool):
                raise StorageError(f"컬럼 '{col.name}' 은 INT 인데 {value!r} 가 왔습니다")
            fields.append(str(value))
        elif col.type == TEXT:
            if not isinstance(value, str):
                raise StorageError(f"컬럼 '{col.name}' 은 TEXT 인데 {value!r} 가 왔습니다")
            fields.append(_escape(value))
        else:  # 카탈로그가 막으므로 도달하지 않는다
            raise StorageError(f"알 수 없는 타입 {col.type}")
    return "\t".join(fields).encode("utf-8") + _EOL


def decode_row(table: Table, line: bytes) -> Row:
    """줄바꿈을 뗀 한 줄의 바이트를 행 튜플로 되돌린다."""
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        # 외부에서 편집되어 UTF-8 이 아닌 바이트가 들어온 경우. 바깥 예외를 우리 예외로 번역한다.
        raise StorageError(f"테이블 '{table.name}' 의 손상된 행: UTF-8 이 아닙니다") from None
    parts = text.split("\t")
    if len(parts) != len(table.columns):
        raise StorageError(
            f"테이블 '{table.name}' 의 손상된 행: 값이 {len(parts)}개 (컬럼 {len(table.columns)}개)"
        )
    values: list[int | str] = []
    for col, text in zip(table.columns, parts):
        if col.type == INT:
            try:
                values.append(int(text))
            except ValueError:
                raise StorageError(
                    f"테이블 '{table.name}' 의 손상된 행: 컬럼 '{col.name}' 에 {text!r}"
                ) from None
        else:
            values.append(_unescape(text))
    return tuple(values)


# --- 테이블 파일 하나 ----------------------------------------------------------


class TableFile:
    """테이블 하나의 파일. 열어 둔 채 유지하고 close() 에서 닫는다."""

    def __init__(self, path: Path, table: Table):
        self.path = path
        self.table = table
        self._file: BinaryIO | None = None
        self._open()

    def _open(self) -> None:
        # 디렉터리 생성부터 열기까지 바깥 세계와 닿는 모든 지점의 OSError 를 StorageError 로 바꾼다.
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=True)
            self._file = open(self.path, "r+b")
        except OSError as e:
            raise StorageError(f"테이블 파일을 열 수 없습니다: {self.path} ({e})") from None
        self._truncate_partial_row()

    def _truncate_partial_row(self) -> None:
        """끝에 \\n 이 없으면 쓰다 만 행이다. 마지막 \\n 이후를 잘라 낸다.

        그냥 두면 다음 append 가 그 뒤에 이어 붙어 반쪽 행과 새 행이 한 줄이 된다.
        """
        f = self._fh()
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return
        f.seek(size - 1)
        if f.read(1) == _EOL:
            return
        # 마지막 \n 을 뒤에서부터 찾는다. 큰 파일에서도 꼬리만 읽도록 블록 단위로 본다.
        block = 4096
        end = size
        while end > 0:
            start = max(0, end - block)
            f.seek(start)
            chunk = f.read(end - start)
            idx = chunk.rfind(_EOL)
            if idx != -1:
                f.truncate(start + idx + 1)
                f.flush()
                return
            end = start
        f.truncate(0)  # \n 이 하나도 없다: 전체가 쓰다 만 행
        f.flush()

    def _fh(self) -> BinaryIO:
        if self._file is None:
            raise StorageError(f"닫힌 테이블입니다: {self.table.name}")
        return self._file

    # --- 세 가지 연산 -----------------------------------------------------------

    def append(self, row: Row) -> int:
        """행을 파일 끝에 쓰고 그 행의 오프셋을 돌려준다."""
        data = encode_row(self.table, row)  # 파일을 건드리기 전에 검사가 끝난다
        f = self._fh()
        f.seek(0, 2)
        offset = f.tell()
        f.write(data)
        f.flush()  # Python 버퍼 -> 운영체제. CLI 가 끝났는데 행이 없는 상황을 막는다.
        return offset

    def scan(self) -> Iterator[tuple[int, Row]]:
        """모든 행을 (오프셋, 행) 으로 처음부터 차례로 내놓는다. 순회 중 append 금지."""
        f = self._fh()
        f.seek(0)
        offset = 0
        while True:
            line = f.readline()
            if not line:
                return
            if not line.endswith(_EOL):
                # _open 에서 정리했으므로 정상이라면 오지 않는다. 순회 중 외부에서 썼을 때 방어.
                raise StorageError(f"테이블 '{self.table.name}' 끝에 쓰다 만 행이 있습니다")
            yield offset, decode_row(self.table, line[:-1])
            offset += len(line)

    def read_at(self, offset: int) -> Row:
        """오프셋 위치의 행 하나를 읽는다. 앞의 행들을 거치지 않는다."""
        f = self._fh()
        f.seek(0, 2)
        size = f.tell()
        if offset < 0 or offset >= size:
            raise StorageError(f"테이블 '{self.table.name}' 에 오프셋 {offset} 은 없습니다")
        if offset > 0:
            f.seek(offset - 1)
            if f.read(1) != _EOL:
                raise StorageError(f"오프셋 {offset} 은 행의 시작이 아닙니다")
        else:
            f.seek(0)
        line = f.readline()
        if not line.endswith(_EOL):
            raise StorageError(f"테이블 '{self.table.name}' 의 오프셋 {offset} 행이 잘려 있습니다")
        return decode_row(self.table, line[:-1])

    # --- 수명 -------------------------------------------------------------------

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    @property
    def closed(self) -> bool:
        return self._file is None

    def __enter__(self) -> TableFile:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# --- 테이블 파일 모음 ----------------------------------------------------------


class Storage:
    """data 디렉터리 아래의 테이블 파일들. 이름으로 TableFile 을 찾아 준다."""

    def __init__(self, data_dir: str | Path, catalog: Catalog):
        self.data_dir = Path(data_dir)
        self.catalog = catalog
        self._tables: dict[str, TableFile] = {}

    def path_for(self, table_name: str) -> Path:
        return self.data_dir / f"{table_name}.tbl"

    def table(self, name: str) -> TableFile:
        """처음 요청될 때 연다. 없는 테이블은 카탈로그가 TableNotFoundError 를 낸다."""
        tf = self._tables.get(name)
        if tf is None:
            table = self.catalog.table(name)
            tf = TableFile(self.path_for(name), table)
            self._tables[name] = tf
        return tf

    def close(self) -> None:
        for tf in self._tables.values():
            tf.close()
        self._tables.clear()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
