"""파서: 토큰 열을 AST 로 바꾼다.

재귀 하강 방식이다. docs/steps/step02-parser.md 2절의 문법 규칙 하나가 함수 하나에 대응한다.
각 함수는 "현재 토큰부터 내 규칙에 맞는 만큼 소비하고 결과 객체를 돌려준다" 는 약속을 지킨다.

파서는 카탈로그를 모른다. 테이블이 존재하는지, 컬럼 타입이 맞는지는 보지 않는다.
기준: 카탈로그 없이 문장만 보고 알 수 있으면 파서, 아니면 실행기.
"""

from __future__ import annotations

from minidb.ast import Condition, Insert, Literal, Select, Statement
from minidb.errors import ParseError
from minidb.lexer import (
    EOF, IDENTIFIER, KEYWORD, NUMBER, OPERATOR, STRING, SYMBOL, Token, tokenize,
)


def parse(sql: str) -> list[Statement]:
    """SQL 문자열 전체를 문장 리스트로 만든다.

    문법이 틀린 문장이 하나라도 있으면 아무것도 돌려주지 않고 ParseError 를 낸다.
    세 번째 문장의 오타 때문에 앞의 두 INSERT 만 실행된 상태를 막기 위해서다.
    """
    return _Parser(tokenize(sql)).parse_program()


def _describe(tok: Token) -> str:
    """오류 메시지에서 토큰을 사람이 읽을 수 있게 표현한다."""
    if tok.kind == EOF:
        return "입력이 끝났습니다"
    if tok.kind == KEYWORD:
        return f"{tok.value} 가 왔습니다"
    if tok.kind == IDENTIFIER:
        return f"식별자 '{tok.value}' 가 왔습니다"
    if tok.kind == NUMBER:
        return f"숫자 {tok.value} 가 왔습니다"
    if tok.kind == STRING:
        return f"문자열 '{tok.value}' 가 왔습니다"
    return f"'{tok.value}' 가 왔습니다"  # SYMBOL, OPERATOR


class _Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- 토큰 단위 도우미 ---------------------------------------------------

    def _peek(self) -> Token:
        """현재 토큰을 소비하지 않고 본다. 선택 규칙("WHERE 가 있는가")에서 쓴다."""
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != EOF:
            self.pos += 1
        return tok

    def _at(self, kind: str, value: object = None) -> bool:
        tok = self._peek()
        return tok.kind == kind and (value is None or tok.value == value)

    def _expect(self, kind: str, value: object = None, expected: str | None = None) -> Token:
        """현재 토큰이 기대한 것이면 소비하고 돌려준다. 아니면 ParseError.

        expected 는 메시지에 쓸 이름이다. 생략하면 value 나 kind 에서 만든다.
        """
        if self._at(kind, value):
            return self._advance()
        if expected is None:
            expected = str(value) if value is not None else _KIND_NAMES.get(kind, kind)
        raise self._error(expected)

    def _error(self, expected: str, tok: Token | None = None) -> ParseError:
        tok = tok or self._peek()
        return ParseError(f"{expected} 이 와야 하는데 {_describe(tok)}", tok.line, tok.col)

    # --- 문법 규칙 ----------------------------------------------------------

    def parse_program(self) -> list[Statement]:
        """program := statement* EOF"""
        statements: list[Statement] = []
        while not self._at(EOF):
            statements.append(self._parse_statement())
        return statements

    def _parse_statement(self) -> Statement:
        """statement := ( insert | select ) ';'"""
        tok = self._peek()
        if self._at(KEYWORD, "INSERT"):
            stmt = self._parse_insert()
        elif self._at(KEYWORD, "SELECT"):
            stmt = self._parse_select()
        else:
            raise self._error("SELECT 또는 INSERT")
        self._expect(SYMBOL, ";", expected="';'")
        return stmt

    def _parse_insert(self) -> Insert:
        """insert := INSERT INTO identifier [ '(' id_list ')' ] VALUES '(' literal_list ')'"""
        start = self._expect(KEYWORD, "INSERT")
        self._expect(KEYWORD, "INTO")
        table = self._expect(IDENTIFIER, expected="테이블 이름").value

        columns: tuple[str, ...] | None = None
        if self._at(SYMBOL, "("):
            self._advance()
            columns = self._parse_id_list()
            self._expect(SYMBOL, ")", expected="')'")

        self._expect(KEYWORD, "VALUES")
        self._expect(SYMBOL, "(", expected="'('")
        values = self._parse_literal_list()
        self._expect(SYMBOL, ")", expected="')'")

        # 카탈로그 없이도 문장만 보고 알 수 있는 검사 두 가지
        if columns is not None:
            if len(columns) != len(values):
                raise ParseError(
                    f"컬럼 {len(columns)}개에 값 {len(values)}개가 왔습니다", start.line, start.col
                )
            dup = _first_duplicate(columns)
            if dup is not None:
                raise ParseError(f"컬럼 '{dup}' 이 두 번 나왔습니다", start.line, start.col)

        return Insert(table=table, columns=columns, values=values, line=start.line)

    def _parse_select(self) -> Select:
        """select := SELECT ( '*' | id_list ) FROM identifier [ WHERE condition ]"""
        start = self._expect(KEYWORD, "SELECT")

        columns: tuple[str, ...] | None
        if self._at(SYMBOL, "*"):
            self._advance()
            columns = None
        else:
            columns = self._parse_id_list()

        self._expect(KEYWORD, "FROM")
        table = self._expect(IDENTIFIER, expected="테이블 이름").value

        where: Condition | None = None
        if self._at(KEYWORD, "WHERE"):
            self._advance()
            where = self._parse_condition()

        return Select(table=table, columns=columns, where=where, line=start.line)

    def _parse_condition(self) -> Condition:
        """condition := identifier operator literal"""
        column = self._expect(IDENTIFIER, expected="컬럼 이름").value
        op = self._expect(OPERATOR, expected="비교 연산자").value
        value = self._parse_literal()
        return Condition(column=column, op=op, value=value)

    def _parse_id_list(self) -> tuple[str, ...]:
        """id_list := identifier ( ',' identifier )*"""
        names = [self._expect(IDENTIFIER, expected="컬럼 이름").value]
        while self._at(SYMBOL, ","):
            self._advance()
            names.append(self._expect(IDENTIFIER, expected="컬럼 이름").value)
        return tuple(names)

    def _parse_literal_list(self) -> tuple[Literal, ...]:
        """literal_list := literal ( ',' literal )*"""
        values = [self._parse_literal()]
        while self._at(SYMBOL, ","):
            self._advance()
            values.append(self._parse_literal())
        return tuple(values)

    def _parse_literal(self) -> Literal:
        """literal := NUMBER | STRING"""
        if self._at(NUMBER) or self._at(STRING):
            return self._advance().value
        raise self._error("숫자 또는 문자열")


_KIND_NAMES = {
    IDENTIFIER: "식별자",
    NUMBER: "숫자",
    STRING: "문자열",
    KEYWORD: "키워드",
    OPERATOR: "비교 연산자",
}


def _first_duplicate(names: tuple[str, ...]) -> str | None:
    seen: set[str] = set()
    for n in names:
        if n in seen:
            return n
        seen.add(n)
    return None
