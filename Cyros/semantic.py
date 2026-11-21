from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from parser import (
    ASTNode,
    AssignStmt,
    BinaryExpr,
    CallExpr,
    DictExpr,
    ExprStmt,
    FuncDefStmt,
    GuardStmt,
    IfStmt,
    IndexExpr,
    InputExpr,
    ListExpr,
    LiteralExpr,
    OutputStmt,
    Program,
    ReturnStmt,
    SpanLoopStmt,
    UnaryExpr,
    VarExpr,
    WhileLoopStmt,
)


@dataclass
class SemanticDiagnostic:
    level: str  # "ERROR" or "WARNING"
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"[Cryos Semantic {self.level}] Line {self.line}, Col {self.column}: {self.message}"


class SemanticError(Exception):
    def __init__(self, diagnostics: List[SemanticDiagnostic]) -> None:
        self.diagnostics = diagnostics
        formatted = "\n".join(str(d) for d in diagnostics)
        super().__init__(formatted)


BUILTIN_NAMES = {
    "append",
    "len",
    "type_of",
    "to_int",
    "to_str",
    "read_file",
    "write_file",
}


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.scopes: List[Set[str]] = [set(BUILTIN_NAMES)]
        self.functions: Dict[str, int] = {}
        self.diagnostics: List[SemanticDiagnostic] = []
        self.function_depth = 0

    def _push_scope(self) -> None:
        self.scopes.append(set())

    def _pop_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str) -> None:
        self.scopes[-1].add(name)

    def _is_declared(self, name: str) -> bool:
        return any(name in scope for scope in self.scopes)

    def _error(self, msg: str, node: ASTNode) -> None:
        self.diagnostics.append(SemanticDiagnostic("ERROR", msg, node.line, node.column))

    def _warn(self, msg: str, node: ASTNode) -> None:
        self.diagnostics.append(SemanticDiagnostic("WARNING", msg, node.line, node.column))

    def analyze(self, program: Program) -> List[SemanticDiagnostic]:
        self.diagnostics.clear()
        for stmt in program.statements:
            self._visit_stmt(stmt)

        errors = [d for d in self.diagnostics if d.level == "ERROR"]
        if errors:
            raise SemanticError(errors)
        return self.diagnostics

    def _visit_block(self, stmts: List[ASTNode], extra_vars: Optional[List[str]] = None) -> None:
        self._push_scope()
        if extra_vars:
            for v in extra_vars:
                self._declare(v)
        for stmt in stmts:
            self._visit_stmt(stmt)
        self._pop_scope()

    def _visit_stmt(self, stmt: ASTNode) -> None:
        if isinstance(stmt, AssignStmt):
            self._visit_expr(stmt.value)
            self._declare(stmt.name)

        elif isinstance(stmt, OutputStmt):
            self._visit_expr(stmt.value)

        elif isinstance(stmt, ReturnStmt):
            if self.function_depth == 0:
                self._error("'return' used outside of a function ('d!').", stmt)
            if stmt.value is not None:
                self._visit_expr(stmt.value)

        elif isinstance(stmt, ExprStmt):
            self._visit_expr(stmt.expr)

        elif isinstance(stmt, FuncDefStmt):
            if stmt.name in self.functions:
                self._warn(f"Function '{stmt.name}' is being redefined.", stmt)
            self.functions[stmt.name] = len(stmt.params)
            self._declare(stmt.name)

            seen_params: Set[str] = set()
            for p in stmt.params:
                if p in seen_params:
                    self._error(f"Duplicate parameter name '{p}' in function '{stmt.name}'.", stmt)
                seen_params.add(p)

            self.function_depth += 1
            self._visit_block(stmt.body, extra_vars=stmt.params)
            self.function_depth -= 1

        elif isinstance(stmt, IfStmt):
            for cond, block in stmt.branches:
                if cond is not None:
                    self._visit_expr(cond)
                self._visit_block(block)

        elif isinstance(stmt, SpanLoopStmt):
            self._visit_expr(stmt.start)
            self._visit_expr(stmt.end)
            if stmt.step is not None:
                self._visit_expr(stmt.step)
            self._visit_block(stmt.body, extra_vars=[stmt.var_name])

        elif isinstance(stmt, WhileLoopStmt):
            self._visit_expr(stmt.condition)
            self._visit_block(stmt.body)

        elif isinstance(stmt, GuardStmt):
            self._visit_block(stmt.try_body)
            rescue_vars = [stmt.rescue_var] if stmt.rescue_var else []
            self._visit_block(stmt.rescue_body, extra_vars=rescue_vars)

    def _visit_expr(self, expr: ASTNode) -> None:
        if isinstance(expr, LiteralExpr) or isinstance(expr, InputExpr):
            if isinstance(expr, InputExpr) and expr.prompt is not None:
                self._visit_expr(expr.prompt)
            return

        if isinstance(expr, VarExpr):
            if not self._is_declared(expr.name):
                self._error(f"Reference to undeclared variable or function '{expr.name}'.", expr)
            return

        if isinstance(expr, UnaryExpr):
            self._visit_expr(expr.operand)
            return

        if isinstance(expr, BinaryExpr):
            self._visit_expr(expr.left)
            self._visit_expr(expr.right)
            if expr.op == "d/" and isinstance(expr.right, LiteralExpr) and expr.right.value == 0:
                self._error("Division by zero ('d/' with literal 0).", expr)
            return

        if isinstance(expr, CallExpr):
            self._visit_expr(expr.callee)
            for arg in expr.args:
                self._visit_expr(arg)
            if isinstance(expr.callee, VarExpr) and expr.callee.name in self.functions:
                expected = self.functions[expr.callee.name]
                if len(expr.args) != expected:
                    self._error(
                        f"Function '{expr.callee.name}' expects {expected} argument(s), got {len(expr.args)}.",
                        expr,
                    )
            return

        if isinstance(expr, IndexExpr):
            self._visit_expr(expr.target)
            self._visit_expr(expr.index)
            return

        if isinstance(expr, ListExpr):
            for el in expr.elements:
                self._visit_expr(el)
            return

        if isinstance(expr, DictExpr):
            for k, v in expr.entries:
                self._visit_expr(k)
                self._visit_expr(v)