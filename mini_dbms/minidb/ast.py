"""AST(추상 구문 트리): 파서의 출력.

문장의 의미만 남기고 표기(공백, 세미콜론, 괄호, 쉼표)는 버린 구조다.
실행기는 토큰이 어떤 순서로 왔는지 모른 채 stmt.table, stmt.where.column 처럼 꺼내 쓴다.

파서는 카탈로그를 모르므로, "SELECT *" 와 컬럼을 생략한 INSERT 는 실제 컬럼 이름으로
바꾸지 않고 columns=None 으로 넘긴다. 해석은 실행기가 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Literal = int | str


@dataclass(frozen=True)
class Condition:
    column: str
    op: str  # = != < <= > >=
    value: Literal


@dataclass(frozen=True)
class Insert:
    table: str
    columns: tuple[str, ...] | None  # None 이면 컬럼 생략 (id 를 뺀 스키마 순서)
    values: tuple[Literal, ...]
    # 파일에서 이 문장이 시작하는 줄. 실행기 오류 메시지용이며 문장의 의미가 아니므로
    # 동등 비교에서 제외한다.
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Select:
    table: str
    columns: tuple[str, ...] | None  # None 이면 SELECT *
    where: Condition | None
    line: int = field(default=0, compare=False)


Statement = Insert | Select
