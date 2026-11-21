from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
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


class RuntimeCryosError(Exception):
    def __init__(self, message: str, line: int = 0, column: int = 0) -> None:
        self.message = message
        self.line = line
        self.column = column
        loc = f"Line {line}, Col {column}: " if line > 0 else ""
        super().__init__(f"[Cryos Runtime Error] {loc}{message}")


class _ReturnSignal(Exception):
    def __init__(self, value: object) -> None:
        self.value = value


@dataclass
class CryosFunction:
    name: str
    params: List[str]
    body: List[ASTNode]
    closure: Environment


class Environment:
    def __init__(self, parent: Optional[Environment] = None) -> None:
        self.values: Dict[str, object] = {}
        self.parent = parent

    def define(self, name: str, value: object) -> None:
        self.values[name] = value

    def assign(self, name: str, value: object) -> None:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.values:
                env.values[name] = value
                return
            env = env.parent
        self.values[name] = value

    def get(self, name: str, line: int = 0, col: int = 0) -> object:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise RuntimeCryosError(f"Undefined variable or function '{name}'.", line, col)


def _is_truthy(val: object) -> bool:
    if val is None or val is False:
        return False
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, (str, list, dict)):
        return len(val) > 0
    return True


def _builtin_append(args: List[object]) -> object:
    if len(args) != 2 or not isinstance(args[0], list):
        raise RuntimeCryosError("append(list, item) requires a list and a value.")
    args[0].append(args[1])
    return args[0]


def _builtin_len(args: List[object]) -> object:
    if len(args) != 1 or not isinstance(args[0], (str, list, dict)):
        raise RuntimeCryosError("len(x) requires a string, list, or dictionary.")
    return len(args[0])


def _builtin_type_of(args: List[object]) -> object:
    if len(args) != 1:
        raise RuntimeCryosError("type_of(x) requires exactly 1 argument.")
    v = args[0]
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, CryosFunction):
        return "function"
    return type(v).__name__


def _builtin_to_int(args: List[object]) -> object:
    if len(args) != 1:
        raise RuntimeCryosError("to_int(x) requires 1 argument.")
    try:
        return int(float(str(args[0]).strip()))
    except (ValueError, TypeError) as exc:
        raise RuntimeCryosError(f"Cannot convert '{args[0]}' to int.") from exc


def _builtin_to_str(args: List[object]) -> object:
    if len(args) != 1:
        raise RuntimeCryosError("to_str(x) requires 1 argument.")
    if args[0] is None:
        return "null"
    if isinstance(args[0], bool):
        return "true" if args[0] else "false"
    return str(args[0])


def _builtin_read_file(args: List[object]) -> object:
    if len(args) != 1 or not isinstance(args[0], str):
        raise RuntimeCryosError("read_file(path) requires a string path.")
    try:
        return Path(args[0]).read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeCryosError(f"Failed to read file '{args[0]}': {exc}") from exc


def _builtin_write_file(args: List[object]) -> object:
    if len(args) != 2 or not isinstance(args[0], str):
        raise RuntimeCryosError("write_file(path, content) requires a string path and content.")
    try:
        Path(args[0]).write_text(str(args[1]), encoding="utf-8")
        return True
    except OSError as exc:
        raise RuntimeCryosError(f"Failed to write file '{args[0]}': {exc}") from exc


class NathanEngine:
    def __init__(self, output_fn: Callable[[str], None] = print, input_fn: Callable[[str], str] = input) -> None:
        self.output_fn = output_fn
        self.input_fn = input_fn
        self.globals = Environment()
        self._register_builtins()

    def _register_builtins(self) -> None:
        builtins: Dict[str, Callable[[List[object]], object]] = {
            "append": _builtin_append,
            "len": _builtin_len,
            "type_of": _builtin_type_of,
            "to_int": _builtin_to_int,
            "to_str": _builtin_to_str,
            "read_file": _builtin_read_file,
            "write_file": _builtin_write_file,
        }
        for name, fn in builtins.items():
            self.globals.define(name, fn)

    def execute(self, program: Program) -> None:
        for stmt in program.statements:
            self._exec_stmt(stmt, self.globals)

    def _exec_block(self, stmts: List[ASTNode], env: Environment) -> None:
        block_env = Environment(parent=env)
        for stmt in stmts:
            self._exec_stmt(stmt, block_env)

    def _exec_stmt(self, stmt: ASTNode, env: Environment) -> None:
        if isinstance(stmt, AssignStmt):
            val = self._eval_expr(stmt.value, env)
            env.define(stmt.name, val)

        elif isinstance(stmt, OutputStmt):
            val = self._eval_expr(stmt.value, env)
            self.output_fn(_builtin_to_str([val]))

        elif isinstance(stmt, ReturnStmt):
            val = self._eval_expr(stmt.value, env) if stmt.value is not None else None
            raise _ReturnSignal(val)

        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr, env)

        elif isinstance(stmt, FuncDefStmt):
            fn = CryosFunction(name=stmt.name, params=stmt.params, body=stmt.body, closure=env)
            env.define(stmt.name, fn)

        elif isinstance(stmt, IfStmt):
            for cond, block in stmt.branches:
                if cond is None or _is_truthy(self._eval_expr(cond, env)):
                    self._exec_block(block, env)
                    break

        elif isinstance(stmt, SpanLoopStmt):
            start_val = self._eval_expr(stmt.start, env)
            end_val = self._eval_expr(stmt.end, env)
            step_val = self._eval_expr(stmt.step, env) if stmt.step is not None else 1
            if not all(isinstance(x, int) and not isinstance(x, bool) for x in (start_val, end_val, step_val)):
                raise RuntimeCryosError("span(...) bounds and step must be integers.", stmt.line, stmt.column)
            if step_val == 0:
                raise RuntimeCryosError("span(...) step cannot be 0.", stmt.line, stmt.column)

            for i in range(start_val, end_val, step_val):
                loop_env = Environment(parent=env)
                loop_env.define(stmt.var_name, i)
                for inner in stmt.body:
                    self._exec_stmt(inner, loop_env)

        elif isinstance(stmt, WhileLoopStmt):
            while _is_truthy(self._eval_expr(stmt.condition, env)):
                self._exec_block(stmt.body, env)

        elif isinstance(stmt, GuardStmt):
            try:
                self._exec_block(stmt.try_body, env)
            except RuntimeCryosError as err:
                rescue_env = Environment(parent=env)
                if stmt.rescue_var:
                    rescue_env.define(stmt.rescue_var, err.message)
                for inner in stmt.rescue_body:
                    self._exec_stmt(inner, rescue_env)

    def _eval_expr(self, expr: ASTNode, env: Environment) -> object:
        if isinstance(expr, LiteralExpr):
            return expr.value

        if isinstance(expr, VarExpr):
            return env.get(expr.name, expr.line, expr.column)

        if isinstance(expr, InputExpr):
            prompt_text = ""
            if expr.prompt is not None:
                prompt_text = str(self._eval_expr(expr.prompt, env))
            return self.input_fn(prompt_text)

        if isinstance(expr, UnaryExpr):
            val = self._eval_expr(expr.operand, env)
            if expr.op == "!":
                return not _is_truthy(val)
            if expr.op == "s-":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    raise RuntimeCryosError("Unary 's-' requires a number.", expr.line, expr.column)
                return -val

        if isinstance(expr, BinaryExpr):
            # Short-circuit boolean operators
            if expr.op == "&":
                left_val = self._eval_expr(expr.left, env)
                if not _is_truthy(left_val):
                    return False
                return _is_truthy(self._eval_expr(expr.right, env))

            if expr.op == "|":
                left_val = self._eval_expr(expr.left, env)
                if _is_truthy(left_val):
                    return True
                return _is_truthy(self._eval_expr(expr.right, env))

            left = self._eval_expr(expr.left, env)
            right = self._eval_expr(expr.right, env)

            if expr.op == "==":
                return left == right
            if expr.op == "!=":
                return left != right

            if expr.op == "s+":
                if isinstance(left, str) or isinstance(right, str):
                    return _builtin_to_str([left]) + _builtin_to_str([right])
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                raise RuntimeCryosError("Invalid operands for 's+'.", expr.line, expr.column)

            if expr.op == "s-":
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left - right
                raise RuntimeCryosError("Invalid operands for 's-'.", expr.line, expr.column)

            if expr.op == "m*":
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left * right
                if isinstance(left, str) and isinstance(right, int) and not isinstance(right, bool):
                    return left * right
                if isinstance(left, list) and isinstance(right, int) and not isinstance(right, bool):
                    return left * right
                raise RuntimeCryosError("Invalid operands for 'm*'.", expr.line, expr.column)

            if expr.op == "d/":
                if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                    raise RuntimeCryosError("Invalid operands for 'd/'.", expr.line, expr.column)
                if right == 0:
                    raise RuntimeCryosError("Division by zero in 'd/'.", expr.line, expr.column)
                return left / right

            if expr.op == "%":
                if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                    raise RuntimeCryosError("Invalid operands for '%'.", expr.line, expr.column)
                if right == 0:
                    raise RuntimeCryosError("Modulo by zero in '%'.", expr.line, expr.column)
                return left % right

            if expr.op in ("<", ">", "<=", ">="):
                if not isinstance(left, (int, float, str)) or not isinstance(right, (int, float, str)):
                    raise RuntimeCryosError(f"Cannot compare values with '{expr.op}'.", expr.line, expr.column)
                if type(left) is not type(right) and not (
                    isinstance(left, (int, float)) and isinstance(right, (int, float))
                ):
                    raise RuntimeCryosError(f"Incompatible types for '{expr.op}'.", expr.line, expr.column)
                if expr.op == "<":
                    return left < right
                if expr.op == ">":
                    return left > right
                if expr.op == "<=":
                    return left <= right
                return left >= right

        if isinstance(expr, CallExpr):
            callee = self._eval_expr(expr.callee, env)
            arg_vals = [self._eval_expr(a, env) for a in expr.args]

            if callable(callee) and not isinstance(callee, CryosFunction):
                return callee(arg_vals)

            if isinstance(callee, CryosFunction):
                if len(arg_vals) != len(callee.params):
                    raise RuntimeCryosError(
                        f"Function '{callee.name}' expects {len(callee.params)} argument(s), got {len(arg_vals)}.",
                        expr.line,
                        expr.column,
                    )
                call_env = Environment(parent=callee.closure)
                for param, val in zip(callee.params, arg_vals):
                    call_env.define(param, val)
                try:
                    for stmt in callee.body:
                        self._exec_stmt(stmt, call_env)
                except _ReturnSignal as ret:
                    return ret.value
                return None

            raise RuntimeCryosError("Attempted to call a non-function value.", expr.line, expr.column)

        if isinstance(expr, IndexExpr):
            target = self._eval_expr(expr.target, env)
            idx = self._eval_expr(expr.index, env)

            if isinstance(target, list):
                if not isinstance(idx, int) or isinstance(idx, bool):
                    raise RuntimeCryosError("List index must be an integer.", expr.line, expr.column)
                try:
                    return target[idx]
                except IndexError as exc:
                    raise RuntimeCryosError("List index out of bounds.", expr.line, expr.column) from exc

            if isinstance(target, str):
                if not isinstance(idx, int) or isinstance(idx, bool):
                    raise RuntimeCryosError("String index must be an integer.", expr.line, expr.column)
                try:
                    return target[idx]
                except IndexError as exc:
                    raise RuntimeCryosError("String index out of bounds.", expr.line, expr.column) from exc

            if isinstance(target, dict):
                if not isinstance(idx, (str, int, float, bool)) or idx is None:
                    raise RuntimeCryosError("Invalid dictionary key.", expr.line, expr.column)
                if idx not in target:
                    raise RuntimeCryosError(f"Key '{idx}' not found in dictionary.", expr.line, expr.column)
                return target[idx]

            raise RuntimeCryosError("Target does not support indexing.", expr.line, expr.column)

        if isinstance(expr, ListExpr):
            return [self._eval_expr(el, env) for el in expr.elements]

        if isinstance(expr, DictExpr):
            out: Dict[object, object] = {}
            for k_node, v_node in expr.entries:
                k_val = self._eval_expr(k_node, env)
                v_val = self._eval_expr(v_node, env)
                out[k_val] = v_val
            return out

        raise RuntimeCryosError(f"Unsupported AST expression '{type(expr).__name__}'.", expr.line, expr.column)