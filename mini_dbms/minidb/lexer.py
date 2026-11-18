"""토크나이저: SQL 문자열을 토큰 열로 자른다.

입력을 앞에서부터 한 글자씩 보며 "지금 문자열 안인가, 주석 안인가, 숫자 중간인가"를
추적해 어디서 자를지 정한다. 토큰이 문법에 맞게 배열됐는지는 보지 않는다(2단계 파서의 일).
카탈로그도 모른다. students 가 실제 테이블인지와 무관하게 IDENTIFIER 로 넘긴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from minidb.errors import ParseError

# 토큰 종류
KEYWORD = "KEYWORD"
IDENTIFIER = "IDENTIFIER"
NUMBER = "NUMBER"
STRING = "STRING"
SYMBOL = "SYMBOL"
OPERATOR = "OPERATOR"
EOF = "EOF"

KEYWORDS = frozenset({"SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES"})
SYMBOLS = frozenset("(),;*")
# 두 글자 연산자를 한 글자보다 먼저 확인해야 한다 (최장 일치). '<=' 를 '<' '=' 로 자르면
# 파서가 엉뚱한 오류를 낸다.
TWO_CHAR_OPERATORS = ("!=", "<=", ">=")
ONE_CHAR_OPERATORS = frozenset("=<>")


@dataclass(frozen=True)
class Token:
    kind: str
    value: object  # KEYWORD/IDENTIFIER/STRING/SYMBOL/OPERATOR 는 str, NUMBER 는 int, EOF 는 None
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


def tokenize(sql: str) -> list[Token]:
    """SQL 문자열 전체를 토큰 리스트로 만든다. 마지막 원소는 항상 EOF 토큰이다."""
    return _Lexer(sql).run()


def _is_ident_start(ch: str) -> bool:
    return ch == "_" or ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _is_ident_char(ch: str) -> bool:
    return _is_ident_start(ch) or ch.isdigit()


class _Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    # --- 글자 단위 도우미 ---------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        """현재 위치에서 offset 만큼 앞의 글자. 입력 끝이면 빈 문자열."""
        i = self.pos + offset
        return self.text[i] if i < len(self.text) else ""

    def _advance(self) -> str:
        """현재 글자를 소비하고 위치(줄, 열)를 갱신한다."""
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _error(self, message: str, line: int, col: int) -> ParseError:
        return ParseError(message, line, col)

    # --- 메인 루프 ----------------------------------------------------------

    def run(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_whitespace_and_comments()
            if not self._peek():
                tokens.append(Token(EOF, None, self.line, self.col))
                return tokens
            tokens.append(self._next_token())

    def _skip_whitespace_and_comments(self) -> None:
        while True:
            ch = self._peek()
            if ch and ch in " \t\r\n":
                self._advance()
            elif ch == "-" and self._peek(1) == "-":
                while self._peek() and self._peek() != "\n":
                    self._advance()
            else:
                return

    def _next_token(self) -> Token:
        ch = self._peek()
        line, col = self.line, self.col

        if ch == "'":
            return self._read_string()
        if ch.isdigit() or (ch == "-" and self._peek(1).isdigit()):
            return self._read_number()
        if _is_ident_start(ch):
            return self._read_word()
        if ch in SYMBOLS:
            self._advance()
            return Token(SYMBOL, ch, line, col)

        two = ch + self._peek(1)
        if two in TWO_CHAR_OPERATORS:
            self._advance()
            self._advance()
            return Token(OPERATOR, two, line, col)
        if ch in ONE_CHAR_OPERATORS:
            self._advance()
            return Token(OPERATOR, ch, line, col)

        raise self._error(f"허용되지 않는 문자 {ch!r}", line, col)

    # --- 종류별 읽기 --------------------------------------------------------

    def _read_string(self) -> Token:
        line, col = self.line, self.col
        self._advance()  # 여는 따옴표
        chars: list[str] = []
        while True:
            ch = self._peek()
            if not ch:
                raise self._error("닫히지 않은 문자열", line, col)
            self._advance()
            if ch == "'":
                if self._peek() == "'":  # '' 는 따옴표 한 글자
                    self._advance()
                    chars.append("'")
                else:
                    return Token(STRING, "".join(chars), line, col)
            else:
                chars.append(ch)

    def _read_number(self) -> Token:
        line, col = self.line, self.col
        chars: list[str] = []
        if self._peek() == "-":
            chars.append(self._advance())
        while self._peek().isdigit():
            chars.append(self._advance())
        return Token(NUMBER, int("".join(chars)), line, col)

    def _read_word(self) -> Token:
        line, col = self.line, self.col
        chars: list[str] = []
        while self._peek() and _is_ident_char(self._peek()):
            chars.append(self._advance())
        word = "".join(chars)
        upper = word.upper()
        if upper in KEYWORDS:
            return Token(KEYWORD, upper, line, col)
        return Token(IDENTIFIER, word.lower(), line, col)
