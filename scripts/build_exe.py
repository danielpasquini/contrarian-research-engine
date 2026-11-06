"""
PyInstaller Standalone Windows Executable Builder (`scripts/build_exe.py`).
"""

import shutil
import subprocess
from pathlib import Path

PYINSTALLER_CLI_LINE = (
    'pyinstaller --noconsole --onefile --name="Contrarian Engine" '
    '--icon="favicon.ico" app.py'
)


def get_pyinstaller_command() -> list[str]:
    """Returns the canonical PyInstaller arguments for single-file `.exe` packaging."""
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--name=Contrarian Engine",
        "--icon=favicon.ico",
        "--add-data=favicon.ico;.",
        "--add-data=favicon.png;.",
        "--add-data=dashboard;dashboard",
        "--add-data=src;src",
    ]
    if Path(".env").exists():
        cmd.append("--add-data=.env;.")
    cmd.append("app.py")
    return cmd


def run_build(repo_root: Path | None = None) -> int:
    cwd = repo_root or Path(__file__).resolve().parent.parent
    result = subprocess.run(get_pyinstaller_command(), cwd=str(cwd), check=False)  # noqa: S603
    if result.returncode == 0:
        env_src = cwd / ".env"
        dist_dir = cwd / "dist"
        if env_src.exists() and dist_dir.exists():
            shutil.copy2(env_src, dist_dir / ".env")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(run_build())
