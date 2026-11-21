from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int) -> None:
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[Cryos Lexer Error] Line {line}, Col {column}: {message}")


class TokenType(Enum):
    # Literals & Identifiers
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    BOOL = auto()
    NULL = auto()

    # Keywords
    OUTPUT = auto()
    RETURN = auto()
    WHEN = auto()
    ALT = auto()
    OTHERWISE = auto()
    CYCLE = auto()
    IN = auto()
    SPAN = auto()
    LOOP = auto()
    WHILE = auto()
    GUARD = auto()
    RESCUE = auto()

    # Custom & Standard Operators / Punctuation
    FUNC_DEF = auto()      # d!
    BIND = auto()          # %!
    ASSIGN = auto()        # =
    INPUT_OP = auto()      # &&
    SUM_OP = auto()        # s+
    SUB_OP = auto()        # s-
    MUL_OP = auto()        # m*
    DIV_OP = auto()        # d/
    MOD = auto()           # %
    AND_OP = auto()        # &
    OR_OP = auto()         # |
    NOT_OP = auto()        # !
    EQ = auto()            # ==
    NEQ = auto()           # !=
    LT = auto()            # <
    GT = auto()            # >
    LTE = auto()           # <=
    GTE = auto()           # >=

    LPAREN = auto()        # (
    RPAREN = auto()        # )
    LBRACKET = auto()      # [
    RBRACKET = auto()      # ]
    LBRACE = auto()        # {
    RBRACE = auto()        # }
    COLON = auto()         # :
    COMMA = auto()         # ,
    DOT = auto()           # .

    # Structure
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


KEYWORDS = {
    "Output": TokenType.OUTPUT,
    "return": TokenType.RETURN,
    "when": TokenType.WHEN,
    "alt": TokenType.ALT,
    "otherwise": TokenType.OTHERWISE,
    "cycle": TokenType.CYCLE,
    "in": TokenType.IN,
    "span": TokenType.SPAN,
    "loop": TokenType.LOOP,
    "while": TokenType.WHILE,
    "guard": TokenType.GUARD,
    "rescue": TokenType.RESCUE,
    "true": TokenType.BOOL,
    "false": TokenType.BOOL,
    "null": TokenType.NULL,
    "none": TokenType.NULL,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: object
    line: int
    column: int


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source.replace("\r\n", "\n").replace("\r", "\n")
        self.pos = 0
        self.line = 1
        self.column = 1
        self.indent_stack: List[int] = [0]
        self.at_line_start = True
        self.bracket_depth = 0

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return "\0"
        return self.source[idx]

    def _advance(self) -> str:
        ch = self._peek()
        if ch == "\0":
            return ch
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_comment(self) -> None:
        # !# starts a single-line comment until newline or EOF
        while self._peek() not in ("\n", "\0"):
            self._advance()

    def _handle_indentation(self) -> List[Token]:
        tokens: List[Token] = []
        indent_spaces = 0
        start_col = self.column

        while self._peek() in (" ", "\t"):
            ch = self._advance()
            if ch == "\t":
                indent_spaces += 4
            else:
                indent_spaces += 1

        # Ignore blank lines or comment-only lines
        if self._peek() == "\n" or self._peek() == "\0":
            return tokens
        if self._peek() == "!" and self._peek(1) == "#":
            self._skip_comment()
            return tokens

        if self.bracket_depth > 0:
            return tokens

        current_indent = self.indent_stack[-1]
        if indent_spaces > current_indent:
            self.indent_stack.append(indent_spaces)
            tokens.append(Token(TokenType.INDENT, indent_spaces, self.line, start_col))
        elif indent_spaces < current_indent:
            while indent_spaces < self.indent_stack[-1]:
                self.indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, indent_spaces, self.line, start_col))
            if indent_spaces != self.indent_stack[-1]:
                raise LexerError(
                    f"Indentation mismatch ({indent_spaces} spaces does not match outer block).",
                    self.line,
                    start_col,
                )

        return tokens

    def _read_number(self) -> Token:
        start_col = self.column
        chars: List[str] = []
        has_dot = False

        while self._peek().isdigit() or (self._peek() == "." and not has_dot and self._peek(1).isdigit()):
            if self._peek() == ".":
                has_dot = True
            chars.append(self._advance())

        raw = "".join(chars)
        val: object = float(raw) if has_dot else int(raw)
        return Token(TokenType.NUMBER, val, self.line, start_col)

    def _read_string(self) -> Token:
        start_line = self.line
        start_col = self.column
        quote = self._advance()  # consume " or '
        chars: List[str] = []
        escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}

        while self._peek() != quote:
            ch = self._peek()
            if ch == "\0":
                raise LexerError("Unterminated string literal.", start_line, start_col)
            if ch == "\\":
                self._advance()
                esc = self._advance()
                if esc not in escapes:
                    raise LexerError(f"Unknown escape sequence '\\{esc}'.", self.line, self.column - 1)
                chars.append(escapes[esc])
            else:
                chars.append(self._advance())

        self._advance()  # consume closing quote
        return Token(TokenType.STRING, "".join(chars), start_line, start_col)

    def _read_word_or_custom_op(self) -> Token:
        start_col = self.column
        # Check custom arithmetic words: s+, s-, m*, d/
        two_char = self._peek() + self._peek(1)
        if two_char == "s+":
            self._advance(); self._advance()
            return Token(TokenType.SUM_OP, "s+", self.line, start_col)
        if two_char == "s-":
            self._advance(); self._advance()
            return Token(TokenType.SUB_OP, "s-", self.line, start_col)
        if two_char == "m*":
            self._advance(); self._advance()
            return Token(TokenType.MUL_OP, "m*", self.line, start_col)
        if two_char == "d/":
            self._advance(); self._advance()
            return Token(TokenType.DIV_OP, "d/", self.line, start_col)

        chars: List[str] = []
        while self._peek().isalnum() or self._peek() == "_":
            chars.append(self._advance())

        word = "".join(chars)
        if word in KEYWORDS:
            ttype = KEYWORDS[word]
            if ttype == TokenType.BOOL:
                return Token(ttype, word == "true", self.line, start_col)
            if ttype == TokenType.NULL:
                return Token(ttype, None, self.line, start_col)
            return Token(ttype, word, self.line, start_col)

        return Token(TokenType.IDENT, word, self.line, start_col)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while self.pos < len(self.source):
            if self.at_line_start:
                tokens.extend(self._handle_indentation())
                self.at_line_start = False

            ch = self._peek()
            if ch == "\0":
                break

            if ch in (" ", "\t"):
                self._advance()
                continue

            if ch == "\n":
                self._advance()
                if self.bracket_depth == 0:
                    tokens.append(Token(TokenType.NEWLINE, "\\n", self.line - 1, self.column))
                self.at_line_start = True
                continue

            # Comment: !#
            if ch == "!" and self._peek(1) == "#":
                self._skip_comment()
                continue

            # Function definition keyword: d!
            if ch == "d" and self._peek(1) == "!":
                col = self.column
                self._advance(); self._advance()
                tokens.append(Token(TokenType.FUNC_DEF, "d!", self.line, col))
                continue

            # Variable assignment binding: %!
            if ch == "%" and self._peek(1) == "!":
                col = self.column
                self._advance(); self._advance()
                tokens.append(Token(TokenType.BIND, "%!", self.line, col))
                continue

            # Input operator: &&
            if ch == "&" and self._peek(1) == "&":
                col = self.column
                self._advance(); self._advance()
                tokens.append(Token(TokenType.INPUT_OP, "&&", self.line, col))
                continue

            if ch.isdigit():
                tokens.append(self._read_number())
                continue

            if ch in ('"', "'"):
                tokens.append(self._read_string())
                continue

            if ch.isalpha() or ch == "_":
                tokens.append(self._read_word_or_custom_op())
                continue

            # Two-character relational operators
            col = self.column
            two = ch + self._peek(1)
            if two == "==":
                self._advance(); self._advance()
                tokens.append(Token(TokenType.EQ, "==", self.line, col))
                continue
            if two == "!=":
                self._advance(); self._advance()
                tokens.append(Token(TokenType.NEQ, "!=", self.line, col))
                continue
            if two == "<=":
                self._advance(); self._advance()
                tokens.append(Token(TokenType.LTE, "<=", self.line, col))
                continue
            if two == ">=":
                self._advance(); self._advance()
                tokens.append(Token(TokenType.GTE, ">=", self.line, col))
                continue

            # Single-character tokens
            self._advance()
            single_map = {
                "=": TokenType.ASSIGN,
                "%": TokenType.MOD,
                "&": TokenType.AND_OP,
                "|": TokenType.OR_OP,
                "!": TokenType.NOT_OP,
                "<": TokenType.LT,
                ">": TokenType.GT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                ":": TokenType.COLON,
                ",": TokenType.COMMA,
                ".": TokenType.DOT,
            }
            if ch in single_map:
                ttype = single_map[ch]
                if ttype in (TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE):
                    self.bracket_depth += 1
                elif ttype in (TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE):
                    self.bracket_depth = max(0, self.bracket_depth - 1)
                tokens.append(Token(ttype, ch, self.line, col))
                continue

            raise LexerError(f"Unexpected character '{ch}'.", self.line, col)

        if tokens and tokens[-1].type != TokenType.NEWLINE:
            tokens.append(Token(TokenType.NEWLINE, "\\n", self.line, self.column))

        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, 0, self.line, self.column))

        tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return tokens