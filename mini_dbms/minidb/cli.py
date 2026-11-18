"""CLI: SQL 파일을 받아 실행하고 결과를 화면에 찍는다.

바깥 세계(파일, 터미널, 종료 코드)와 엔진(파서, 실행기) 사이의 번역기다. 하는 일은 넷뿐이다.
  1. 인자를 해석하고 파일을 읽는다.
  2. 파서와 실행기를 부른다.
  3. QueryResult 를 글자로 바꾼다.
  4. 예외를 메시지와 종료 코드로 바꾼다.
결과 정렬, 행 수 제한 같은 로직은 넣지 않는다. 13단계 서버가 같은 것을 복제해야 하기 때문이다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from minidb.ast import Insert
from minidb.catalog import Catalog
from minidb.errors import MiniDBError, ParseError
from minidb.executor import Executor, QueryResult
from minidb.parser import parse
from minidb.storage import Storage

EXIT_OK = 0
EXIT_INPUT = 1      # SQL 파일을 고치면 된다: 파일을 못 읽음, 문법 오류
EXIT_EXECUTION = 2  # 실행 환경이나 데이터 상태의 문제: 카탈로그, 실행 오류


# --- 결과 -> 글자 -------------------------------------------------------------


def format_insert(result: QueryResult) -> str:
    (new_id,) = result.rows[0]
    return f"{result.rowcount} row inserted (id={new_id})"


def format_table(result: QueryResult) -> str:
    """컬럼 너비를 맞춘 표. 0행이면 헤더와 구분선만 찍고 (0 rows) 를 붙인다."""
    cells = [[str(v) for v in row] for row in result.rows]
    widths = [len(name) for name in result.columns]
    for row in cells:
        for i, text in enumerate(row):
            widths[i] = max(widths[i], len(text))

    def line(values: list[str]) -> str:
        return " | ".join(v.ljust(w) for v, w in zip(values, widths)).rstrip()

    out = [line(list(result.columns)), "-+-".join("-" * w for w in widths)]
    out.extend(line(row) for row in cells)
    if not cells:
        out.append("(0 rows)")
    return "\n".join(out)


# --- 흐름 ---------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m minidb", description="미니 DBMS: SQL 파일을 실행한다.")
    p.add_argument("sql_file", help="실행할 SQL 문장들이 든 텍스트 파일")
    p.add_argument("--data-dir", default="data", help="테이블 파일(*.tbl) 디렉터리 (기본: data)")
    p.add_argument("--schema", default=None, help="카탈로그 파일 (기본: <data-dir>/schema.json)")
    return p


def main(argv: list[str] | None = None, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """종료 코드를 돌려준다. sys.exit 는 __main__ 이 한다. 테스트가 함수로 부를 수 있게."""
    args = _build_parser().parse_args(argv)
    data_dir = Path(args.data_dir)
    schema_path = Path(args.schema) if args.schema else data_dir / "schema.json"

    # 1. 파일 읽기
    # utf-8-sig: 윈도우 메모장 등이 붙이는 BOM 이 있으면 떼고, 없으면 일반 UTF-8 과 같다.
    try:
        sql = Path(args.sql_file).read_text(encoding="utf-8-sig")
    except OSError as e:
        print(f"오류: 파일을 열 수 없습니다: {args.sql_file} ({e.strerror})", file=stderr)
        return EXIT_INPUT
    except UnicodeDecodeError:
        print(f"오류: UTF-8 로 읽을 수 없는 파일입니다: {args.sql_file}", file=stderr)
        return EXIT_INPUT

    # 2. 전체 파싱. 문법 오류가 하나라도 있으면 아무것도 실행하지 않는다 (2단계 결정).
    try:
        statements = parse(sql)
    except ParseError as e:
        print(f"문법 오류: {e}", file=stderr)
        return EXIT_INPUT

    # 3. 카탈로그와 저장소
    try:
        catalog = Catalog.load(schema_path)
    except MiniDBError as e:
        print(f"실행 오류: {e}", file=stderr)
        return EXIT_EXECUTION

    # 4. 문장마다 실행. 첫 실행 오류에서 멈춘다 (4단계 결정). 앞 문장은 되돌리지 않는다.
    with Storage(data_dir, catalog) as storage:
        executor = Executor(catalog, storage)
        for stmt in statements:
            try:
                result = executor.execute(stmt)
            except MiniDBError as e:
                print(f"실행 오류 ({stmt.line}번째 줄): {e}", file=stderr)
                return EXIT_EXECUTION
            print(format_insert(result) if isinstance(stmt, Insert) else format_table(result), file=stdout)

    return EXIT_OK
