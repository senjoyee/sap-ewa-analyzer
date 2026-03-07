import compileall
import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = CURRENT_DIR.parent

DEFAULT_DIRS = [
    "agent",
    "converters",
    "core",
    "models",
    "routers",
    "schemas",
    "services",
    "utils",
    "workflow_orchestrator.py",
    "ewa_main.py",
]


def _compile_target(target: Path) -> bool:
    if target.is_dir():
        return compileall.compile_dir(str(target), quiet=1, force=False)
    if target.is_file():
        return compileall.compile_file(str(target), quiet=1, force=False)
    print(f"[skip] Missing target: {target}")
    return True


def main(argv: list[str]) -> int:
    requested = argv[1:] or DEFAULT_DIRS
    ok = True

    print(f"Backend root: {BACKEND_ROOT}")
    print("Validating targets:")

    for item in requested:
        target = (BACKEND_ROOT / item).resolve()
        print(f"- {target}")
        if BACKEND_ROOT not in target.parents and target != BACKEND_ROOT:
            print(f"[error] Target escapes backend root: {item}")
            ok = False
            continue
        if ".venv" in target.parts or "site-packages" in target.parts:
            print(f"[skip] Ignoring virtualenv target: {item}")
            continue
        ok = _compile_target(target) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
