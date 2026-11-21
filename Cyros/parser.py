from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from lexer import Token, TokenType


class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        self.message = message
        self.token = token
        super().__init__(f"[Cryos Parse Error] Line {token.line}, Col {token.column}: {message}")


# --- AST Nodes ---
class ASTNode:
    line: int
    column: int


@dataclass
class Program(ASTNode):
    statements: List[ASTNode]
    line: int = 1
    column: int = 1


@dataclass
class AssignStmt(ASTNode):
    name: str
    value: ASTNode
    line: int
    column: int


@dataclass
class OutputStmt(ASTNode):
    value: ASTNode
    line: int
    column: int


@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode]
    line: int
    column: int


@dataclass
class ExprStmt(ASTNode):
    expr: ASTNode
    line: int
    column: int


@dataclass
class FuncDefStmt(ASTNode):
    name: str
    params: List[str]
    body: List[ASTNode]
    line: int
    column: int


@dataclass
class IfStmt(ASTNode):
    branches: List[Tuple[Optional[ASTNode], List[ASTNode]]]  # (condition or None for otherwise, block)
    line: int
    column: int


@dataclass
class SpanLoopStmt(ASTNode):
    var_name: str
    start: ASTNode
    end: ASTNode
    step: Optional[ASTNode]
    body: List[ASTNode]
    line: int
    column: int


@dataclass
class WhileLoopStmt(ASTNode):
    condition: ASTNode
    body: List[ASTNode]
    line: int
    column: int


@dataclass
class GuardStmt(ASTNode):
    try_body: List[ASTNode]
    rescue_var: Optional[str]
    rescue_body: List[ASTNode]
    line: int
    column: int


@dataclass
class LiteralExpr(ASTNode):
    value: object
    line: int
    column: int


@dataclass
class VarExpr(ASTNode):
    name: str
    line: int
    column: int


@dataclass
class InputExpr(ASTNode):
    prompt: Optional[ASTNode]
    line: int
    column: int


@dataclass
class UnaryExpr(ASTNode):
    op: str
    operand: ASTNode
    line: int
    column: int


@dataclass
class BinaryExpr(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode
    line: int
    column: int


@dataclass
class CallExpr(ASTNode):
    callee: ASTNode
    args: List[ASTNode]
    line: int
    column: int


@dataclass
class IndexExpr(ASTNode):
    target: ASTNode
    index: ASTNode
    line: int
    column: int


@dataclass
class ListExpr(ASTNode):
    elements: List[ASTNode]
    line: int
    column: int


@dataclass
class DictExpr(ASTNode):
    entries: List[Tuple[ASTNode, ASTNode]]
    line: int
    column: int


# --- Recursive Descent Parser ---
class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self._peek().type in types:
            return self._advance()
        return None

    def _expect(self, ttype: TokenType, message: str) -> Token:
        tok = self._peek()
        if tok.type == ttype:
            return self._advance()
        raise ParseError(f"{message} (found '{tok.value}')", tok)

    def _skip_newlines(self) -> None:
        while self._match(TokenType.NEWLINE):
            pass

    def parse(self) -> Program:
        statements: List[ASTNode] = []
        self._skip_newlines()
        while self._peek().type != TokenType.EOF:
            statements.append(self._parse_statement())
            self._skip_newlines()
        return Program(statements=statements)

    def _parse_block(self) -> List[ASTNode]:
        self._expect(TokenType.COLON, "Expected ':' to start block.")
        self._expect(TokenType.NEWLINE, "Expected newline after ':'.")
        self._expect(TokenType.INDENT, "Expected indented block after ':'.")

        stmts: List[ASTNode] = []
        while self._peek().type not in (TokenType.DEDENT, TokenType.EOF):
            if self._peek().type == TokenType.NEWLINE:
                self._advance()
                continue
            stmts.append(self._parse_statement())

        self._expect(TokenType.DEDENT, "Expected dedent at end of block.")
        return stmts

    def _parse_statement(self) -> ASTNode:
        tok = self._peek()

        if tok.type == TokenType.FUNC_DEF:
            return self._parse_func_def()
        if tok.type == TokenType.WHEN:
            return self._parse_if_chain()
        if tok.type == TokenType.CYCLE:
            return self._parse_cycle_span()
        if tok.type == TokenType.LOOP:
            return self._parse_loop_while()
        if tok.type == TokenType.GUARD:
            return self._parse_guard_rescue()
        if tok.type == TokenType.OUTPUT:
            return self._parse_output()
        if tok.type == TokenType.RETURN:
            return self._parse_return()

        # Check assignment: IDENT (%! | =) expr
        if tok.type == TokenType.IDENT and self._peek(1).type in (TokenType.BIND, TokenType.ASSIGN):
            ident = self._advance()
            self._advance()  # consume %! or =
            expr = self._parse_expr()
            self._consume_stmt_end()
            return AssignStmt(name=str(ident.value), value=expr, line=ident.line, column=ident.column)

        expr = self._parse_expr()
        self._consume_stmt_end()
        return ExprStmt(expr=expr, line=tok.line, column=tok.column)

    def _consume_stmt_end(self) -> None:
        if self._peek().type in (TokenType.NEWLINE, TokenType.EOF):
            self._match(TokenType.NEWLINE)
            return
        raise ParseError("Expected end of line after statement.", self._peek())

    def _parse_func_def(self) -> FuncDefStmt:
        kw = self._advance()  # d!
        name_tok = self._expect(TokenType.IDENT, "Expected function name after 'd!'.")
        self._expect(TokenType.LPAREN, "Expected '(' after function name.")
        params: List[str] = []
        if self._peek().type != TokenType.RPAREN:
            while True:
                p = self._expect(TokenType.IDENT, "Expected parameter name.")
                params.append(str(p.value))
                if not self._match(TokenType.COMMA):
                    break
        self._expect(TokenType.RPAREN, "Expected ')' after parameter list.")
        body = self._parse_block()
        return FuncDefStmt(
            name=str(name_tok.value),
            params=params,
            body=body,
            line=kw.line,
            column=kw.column,
        )

    def _parse_if_chain(self) -> IfStmt:
        start = self._advance()  # when
        branches: List[Tuple[Optional[ASTNode], List[ASTNode]]] = []
        cond = self._parse_expr()
        block = self._parse_block()
        branches.append((cond, block))

        while self._peek().type == TokenType.ALT:
            self._advance()
            alt_cond = self._parse_expr()
            alt_block = self._parse_block()
            branches.append((alt_cond, alt_block))

        if self._peek().type == TokenType.OTHERWISE:
            self._advance()
            else_block = self._parse_block()
            branches.append((None, else_block))

        return IfStmt(branches=branches, line=start.line, column=start.column)

    def _parse_cycle_span(self) -> SpanLoopStmt:
        start_tok = self._advance()  # cycle
        var_tok = self._expect(TokenType.IDENT, "Expected loop variable after 'cycle'.")
        self._expect(TokenType.IN, "Expected 'in' after loop variable.")
        self._expect(TokenType.SPAN, "Expected 'span' after 'in'.")
        self._expect(TokenType.LPAREN, "Expected '(' after 'span'.")

        first = self._parse_expr()
        self._expect(TokenType.COMMA, "Expected ',' in span(...) arguments.")
        second = self._parse_expr()
        third: Optional[ASTNode] = None
        if self._match(TokenType.COMMA):
            third = self._parse_expr()
        self._expect(TokenType.RPAREN, "Expected ')' after span(...) arguments.")

        body = self._parse_block()
        return SpanLoopStmt(
            var_name=str(var_tok.value),
            start=first,
            end=second,
            step=third,
            body=body,
            line=start_tok.line,
            column=start_tok.column,
        )

    def _parse_loop_while(self) -> WhileLoopStmt:
        start_tok = self._advance()  # loop
        self._expect(TokenType.WHILE, "Expected 'while' after 'loop'.")
        cond = self._parse_expr()
        body = self._parse_block()
        return WhileLoopStmt(condition=cond, body=body, line=start_tok.line, column=start_tok.column)

    def _parse_guard_rescue(self) -> GuardStmt:
        start_tok = self._advance()  # guard
        try_body = self._parse_block()
        self._expect(TokenType.RESCUE, "Expected 'rescue' block after 'guard' block.")
        rescue_var: Optional[str] = None
        if self._peek().type == TokenType.IDENT:
            rescue_var = str(self._advance().value)
        rescue_body = self._parse_block()
        return GuardStmt(
            try_body=try_body,
            rescue_var=rescue_var,
            rescue_body=rescue_body,
            line=start_tok.line,
            column=start_tok.column,
        )

    def _parse_output(self) -> OutputStmt:
        kw = self._advance()  # Output
        expr = self._parse_expr()
        self._consume_stmt_end()
        return OutputStmt(value=expr, line=kw.line, column=kw.column)

    def _parse_return(self) -> ReturnStmt:
        kw = self._advance()  # return
        val: Optional[ASTNode] = None
        if self._peek().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.DEDENT):
            val = self._parse_expr()
        self._consume_stmt_end()
        return ReturnStmt(value=val, line=kw.line, column=kw.column)

    # --- Expressions ---
    def _parse_expr(self) -> ASTNode:
        return self._parse_or()

    def _parse_or(self) -> ASTNode:
        expr = self._parse_and()
        while tok := self._match(TokenType.OR_OP):
            right = self._parse_and()
            expr = BinaryExpr(op="|", left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_and(self) -> ASTNode:
        expr = self._parse_equality()
        while tok := self._match(TokenType.AND_OP):
            right = self._parse_equality()
            expr = BinaryExpr(op="&", left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_equality(self) -> ASTNode:
        expr = self._parse_comparison()
        while tok := self._match(TokenType.EQ, TokenType.NEQ):
            right = self._parse_comparison()
            expr = BinaryExpr(op=str(tok.value), left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_comparison(self) -> ASTNode:
        expr = self._parse_additive()
        while tok := self._match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            right = self._parse_additive()
            expr = BinaryExpr(op=str(tok.value), left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_additive(self) -> ASTNode:
        expr = self._parse_multiplicative()
        while tok := self._match(TokenType.SUM_OP, TokenType.SUB_OP):
            right = self._parse_multiplicative()
            expr = BinaryExpr(op=str(tok.value), left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_multiplicative(self) -> ASTNode:
        expr = self._parse_unary()
        while tok := self._match(TokenType.MUL_OP, TokenType.DIV_OP, TokenType.MOD):
            right = self._parse_unary()
            expr = BinaryExpr(op=str(tok.value), left=expr, right=right, line=tok.line, column=tok.column)
        return expr

    def _parse_unary(self) -> ASTNode:
        if tok := self._match(TokenType.NOT_OP, TokenType.SUB_OP):
            operand = self._parse_unary()
            op = "!" if tok.type == TokenType.NOT_OP else "s-"
            return UnaryExpr(op=op, operand=operand, line=tok.line, column=tok.column)
        return self._parse_postfix()

    def _parse_postfix(self) -> ASTNode:
        expr = self._parse_primary()
        while True:
            if lp := self._match(TokenType.LPAREN):
                args: List[ASTNode] = []
                if self._peek().type != TokenType.RPAREN:
                    while True:
                        args.append(self._parse_expr())
                        if not self._match(TokenType.COMMA):
                            break
                self._expect(TokenType.RPAREN, "Expected ')' after arguments.")
                expr = CallExpr(callee=expr, args=args, line=lp.line, column=lp.column)
            elif lb := self._match(TokenType.LBRACKET):
                idx = self._parse_expr()
                self._expect(TokenType.RBRACKET, "Expected ']' after index.")
                expr = IndexExpr(target=expr, index=idx, line=lb.line, column=lb.column)
            else:
                break
        return expr

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()

        if tok.type in (TokenType.NUMBER, TokenType.STRING, TokenType.BOOL, TokenType.NULL):
            self._advance()
            return LiteralExpr(value=tok.value, line=tok.line, column=tok.column)

        if tok.type == TokenType.INPUT_OP:
            self._advance()  # &&
            prompt: Optional[ASTNode] = None
            if self._match(TokenType.LPAREN):
                if self._peek().type != TokenType.RPAREN:
                    prompt = self._parse_expr()
                self._expect(TokenType.RPAREN, "Expected ')' after && prompt.")
            return InputExpr(prompt=prompt, line=tok.line, column=tok.column)

        if tok.type == TokenType.IDENT:
            self._advance()
            return VarExpr(name=str(tok.value), line=tok.line, column=tok.column)

        if tok.type == TokenType.LPAREN:
            self._advance()
            inner = self._parse_expr()
            self._expect(TokenType.RPAREN, "Expected ')' after expression.")
            return inner

        if tok.type == TokenType.LBRACKET:
            self._advance()
            elements: List[ASTNode] = []
            if self._peek().type != TokenType.RBRACKET:
                while True:
                    elements.append(self._parse_expr())
                    if not self._match(TokenType.COMMA):
                        break
            self._expect(TokenType.RBRACKET, "Expected ']' after list elements.")
            return ListExpr(elements=elements, line=tok.line, column=tok.column)

        if tok.type == TokenType.LBRACE:
            self._advance()
            entries: List[Tuple[ASTNode, ASTNode]] = []
            if self._peek().type != TokenType.RBRACE:
                while True:
                    k = self._parse_expr()
                    self._expect(TokenType.COLON, "Expected ':' between dictionary key and value.")
                    v = self._parse_expr()
                    entries.append((k, v))
                    if not self._match(TokenType.COMMA):
                        break
            self._expect(TokenType.RBRACE, "Expected '}' after dictionary entries.")
            return DictExpr(entries=entries, line=tok.line, column=tok.column)

        raise ParseError(f"Unexpected token '{tok.value}' in expression.", tok)