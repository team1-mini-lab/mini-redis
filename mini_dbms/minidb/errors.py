"""미니 DBMS 가 사용자에게 돌려주는 오류 타입.

모든 오류는 MiniDBError 를 상속한다. CLI 와 서버는 이 예외만 잡아서
각자의 출력 형식으로 바꾼다. MiniDBError 가 아닌 예외가 밖으로 새어 나오면
그것은 사용자 입력 문제가 아니라 우리 코드의 버그다.
"""


class MiniDBError(Exception):
    """모든 미니 DBMS 오류의 부모."""


class ParseError(MiniDBError):
    """SQL 문법 오류. 토크나이저와 파서가 낸다.

    line, col 은 원문에서의 위치(1부터 셈)다. 메시지에 박아 넣지 않고 속성으로 두는
    이유는 CLI 는 "3:12: ..." 로 찍고 서버는 JSON 필드로 따로 실을 수 있게 하기 위해서다.
    """

    def __init__(self, message: str, line: int | None = None, col: int | None = None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self) -> str:
        if self.line is None:
            return self.message
        return f"{self.line}:{self.col}: {self.message}"


class SchemaError(MiniDBError):
    """카탈로그(schema.json) 가 규칙에 맞지 않거나, 없는 테이블/컬럼을 참조했다."""


class TableNotFoundError(SchemaError):
    """카탈로그에 없는 테이블을 참조했다."""


class ColumnNotFoundError(SchemaError):
    """테이블에 없는 컬럼을 참조했다."""


class TypeMismatchError(MiniDBError):
    """값의 타입이 컬럼 타입과 맞지 않는다."""


class ExecutionError(MiniDBError):
    """문법도 맞고 테이블과 컬럼도 있지만 이 문장은 실행할 수 없다.

    예: INSERT 에 id 를 지정함, 컬럼을 생략한 INSERT 의 값 수가 스키마와 다름.
    """


class StorageError(MiniDBError):
    """테이블 파일을 읽거나 쓰는 중 문제가 생겼다."""
