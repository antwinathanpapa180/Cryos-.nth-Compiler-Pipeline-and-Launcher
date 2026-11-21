from __future__ import annotations
import subprocess
import sys
import tkinter as tk
from pathlib import Path


SPLASH_DURATION_MS = 1800
SPLASH_MAX_SIZE = 380
TRANSPARENT_KEY = "#010203"


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def get_work_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def show_centered_splash(logo_path: Path, duration_ms: int = SPLASH_DURATION_MS) -> None:
    if not logo_path.exists():
        return

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=TRANSPARENT_KEY)

    try:
        root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
    except tk.TclError:
        pass

    raw_img = tk.PhotoImage(file=str(logo_path))
    w, h = raw_img.width(), raw_img.height()
    scale = max(1, (max(w, h) + SPLASH_MAX_SIZE - 1) // SPLASH_MAX_SIZE)
    img = raw_img.subsample(scale, scale) if scale > 1 else raw_img

    disp_w, disp_h = img.width(), img.height()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    pos_x = (screen_w - disp_w) // 2
    pos_y = (screen_h - disp_h) // 2

    root.geometry(f"{disp_w}x{disp_h}+{pos_x}+{pos_y}")

    canvas = tk.Canvas(
        root,
        width=disp_w,
        height=disp_h,
        bg=TRANSPARENT_KEY,
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_image(disp_w // 2, disp_h // 2, image=img, anchor="center")

    root._cryos_img = img  # type: ignore[attr-defined]
    canvas.bind("<Button-1>", lambda _e: root.destroy())
    root.after(duration_ms, root.destroy)
    root.mainloop()


def launch_powershell(script_arg: str | None = None) -> None:
    base_dir = get_base_dir()
    work_dir = get_work_dir()
    nathan_py = base_dir / "nathan.py"

    if getattr(sys, "frozen", False):
        host_exe = sys.executable
        inner_cmd = f"& '{host_exe}' run '{script_arg}'" if script_arg else f"& '{host_exe}' repl"
    else:
        py_exe = sys.executable
        inner_cmd = (
            f"& '{py_exe}' '{nathan_py}' run '{script_arg}'"
            if script_arg
            else f"& '{py_exe}' '{nathan_py}' repl"
        )

    ps_command = (
        f"Set-Location -LiteralPath '{work_dir}'; "
        f"Write-Host 'Cryos (.nth) PowerShell Ready' -ForegroundColor Cyan; "
        f"{inner_cmd}"
    )

    creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_command,
        ],
        cwd=str(work_dir),
        creationflags=creation_flags,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("run", "repl"):
        from nathan import main as nathan_main
        return nathan_main(args)

    script_file = args[0] if args else None
    logo_path = get_base_dir() / "cryos_logo.png"

    show_centered_splash(logo_path)
    launch_powershell(script_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
