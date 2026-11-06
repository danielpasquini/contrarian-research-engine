import ast
import os
import re
import socket
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_no_secrets_in_tracked_files() -> None:
    gemini_key_pattern = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
    alpaca_key_pattern = re.compile(r"\b(PK|AK)[A-Z0-9]{16,}\b")
    assignment_pattern = re.compile(
        r"^[A-Z0-9_]*(?:SECRET_KEY|API_KEY)\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE
    )

    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea", ".vscode"}
    text_extensions = {
        ".py",
        ".md",
        ".toml",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".env.example",
        ".sh",
        ".ini",
    }

    violations: list[str] = []

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for f in files:
            path = Path(root) / f
            rel_path = path.relative_to(ROOT_DIR)
            if path.suffix not in text_extensions and path.name != ".env.example":
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            if gemini_key_pattern.search(content):
                violations.append(f"{rel_path}: matches Gemini API key pattern")
            if alpaca_key_pattern.search(content):
                violations.append(f"{rel_path}: matches Alpaca API key pattern")

            if path.name != ".env.example":
                for match in assignment_pattern.finditer(content):
                    val = match.group(1).strip()
                    if val and not val.startswith("your_") and not val.startswith("sample_"):
                        violations.append(
                            f"{rel_path}: non-empty secret key assignment '{match.group(0)}'"
                        )

    assert not violations, "Secret leakage detected:\n" + "\n".join(violations)


def test_dotenv_is_gitignored() -> None:
    gitignore_path = ROOT_DIR / ".gitignore"
    assert gitignore_path.exists(), ".gitignore does not exist"
    lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    entries = {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}
    assert ".env" in entries or any(
        e.startswith(".env") and not e.startswith("!") for e in entries
    ), ".env is not ignored in .gitignore"


def test_socket_guard_active() -> None:
    # Attempting an outbound connection to non-loopback IP must raise an error
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises((RuntimeError, OSError)):
            s.connect(("8.8.8.8", 53))
    finally:
        s.close()


def test_no_skips_in_safety_suites() -> None:
    safety_test_dirs = [ROOT_DIR / "tests" / "unit", ROOT_DIR / "tests" / "constraints"]
    skips: list[str] = []

    for test_dir in safety_test_dirs:
        if not test_dir.exists():
            continue
        for py_file in test_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in ("skip", "xfail"):
                    skips.append(
                        f"{py_file.relative_to(ROOT_DIR)}:{node.lineno} uses pytest.{node.attr}"
                    )

    assert not skips, "Found prohibited skip/xfail markers in safety test suites:\n" + "\n".join(
        skips
    )
