Cryos (.nth Compiler & Runtime)

Cryos is a custom compiler and runtime toolchain for .nth source files, structured into modular lexing, parsing, semantic analysis, and execution stages alongside a centered splash-to-PowerShell launcher.

Project Structure

• lexer.py — Tokenizes .nth source code with line/column tracking and indentation blocks.
• parser.py — Builds the Abstract Syntax Tree (AST) and reports syntax errors.
• semantic.py — Performs scope checks, function arity/declaration validation, and static diagnostics.
• nathan_engine.py — Executes the AST, manages call frames and built-ins, and handles guard/rescue runtime errors.
• nathan.py — CLI entry point supporting run &lt;file.nth> and an interactive repl.
• launcher.py — Displays cryos_logo.png centered on screen with a transparent background before opening Windows PowerShell.
• cryos_logo.png — Centered splash logo asset (1000x1000 design).
• sample.nth — End-to-end sample program exercising functions, conditionals, loops, and error handling.

.nth Syntax Highlights

• Comments:!# single-line comment
• Binding & Output:x %! 10, Output expr, &&("Prompt: ")
• Arithmetic & Logic:s+, s-, m*, d/, %, ==, !=, <, >, <=, >=, &, |, !
• Functions:d! fn_name(a, b): with return
• Branching:when cond: / alt cond2: / otherwise:
• Loops:cycle i in span(0, 5): and loop while cond:
• Error Handling:guard: / rescue err:

Usage (VS Code / PowerShell)

Run a .nth script:

powershell
python nathan.py run sample.nth
