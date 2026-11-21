from __future__ import annotations
import argparse
import sys
from pathlib import Path
from lexer import Lexer, LexerError
from parser import Parser, ParseError
from semantic import SemanticAnalyzer, SemanticError
from nathan_engine import NathanEngine, RuntimeCryosError


def run_source(source: str, engine: NathanEngine | None = None, show_tokens: bool = False, show_ast: bool = False) -> None:
    active_engine = engine if engine is not None else NathanEngine()
    tokens = Lexer(source).tokenize()
    if show_tokens:
        for tok in tokens:
            print(tok)

    program = Parser(tokens).parse()
    if show_ast:
        print(program)

    SemanticAnalyzer().analyze(program)
    active_engine.execute(program)


def run_file(path_str: str, show_tokens: bool = False, show_ast: bool = False) -> int:
    path = Path(path_str)
    if not path.exists():
        print(f"[Cryos CLI Error] File not found: {path}", file=sys.stderr)
        return 1

    try:
        source = path.read_text(encoding="utf-8")
        run_source(source, show_tokens=show_tokens, show_ast=show_ast)
        return 0
    except (LexerError, ParseError, SemanticError, RuntimeCryosError) as err:
        print(err, file=sys.stderr)
        return 1


def repl() -> int:
    print("Cryos Compiler v1.0 (.nth runtime) — type 'exit' or 'quit' to leave.")
    engine = NathanEngine()
    buffer: list[str] = []

    while True:
        prompt = "... " if buffer else "cryos> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Cryos.")
            return 0

        stripped = line.strip()
        if not buffer and stripped in ("exit", "quit"):
            print("Exiting Cryos.")
            return 0

        if not buffer and stripped == "":
            continue

        buffer.append(line)
        # Continue collecting lines if line ends with ':' or is indented
        if line.rstrip().endswith(":") or line.startswith((" ", "\t")):
            if stripped != "":
                continue

        source = "\n".join(buffer)
        buffer.clear()
        try:
            run_source(source, engine=engine)
        except (LexerError, ParseError, SemanticError, RuntimeCryosError) as err:
            print(err, file=sys.stderr)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nathan", description="Cryos compiler & runner for .nth scripts")
    sub = parser.add_subparsers(dest="command")

    run_cmd = sub.add_parser("run", help="Compile and execute a .nth script")
    run_cmd.add_argument("file", help="Path to the .nth source file")
    run_cmd.add_argument("--tokens", action="store_true", help="Print lexer tokens")
    run_cmd.add_argument("--ast", action="store_true", help="Print parsed AST")

    sub.add_parser("repl", help="Start interactive Cryos REPL")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.command == "run":
        return run_file(args.file, show_tokens=args.tokens, show_ast=args.ast)
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())