import ast
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
DASHBOARD_DIR = ROOT_DIR / "dashboard"


def _get_imports(py_file: Path) -> list[tuple[int, str]]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def test_deterministic_layers_import_no_network_or_llm() -> None:
    deterministic_dirs = ["scanner", "risk", "normalization", "strategies"]
    banned_roots = ("google.genai", "google", "alpaca", "httpx", "requests", "urllib", "socket")

    violations: list[str] = []
    for sub in deterministic_dirs:
        sub_dir = SRC_DIR / sub
        if not sub_dir.exists():
            continue
        for py_file in sub_dir.glob("*.py"):
            for lineno, mod in _get_imports(py_file):
                for banned in banned_roots:
                    if mod == banned or mod.startswith(f"{banned}."):
                        rel = py_file.relative_to(ROOT_DIR)
                        violations.append(f"{rel}:{lineno} imports banned module '{mod}'")

    assert not violations, "Deterministic layer boundary violations:\n" + "\n".join(violations)


def test_sdk_import_allow_list() -> None:
    violations: list[str] = []
    for py_file in SRC_DIR.rglob("*.py"):
        rel_str = str(py_file.relative_to(SRC_DIR)).replace("\\", "/")
        imports = _get_imports(py_file)
        for lineno, mod in imports:
            if (mod == "google.genai" or mod.startswith("google.genai.")) and not rel_str.startswith(
                "intelligence/"
            ):
                violations.append(f"{rel_str}:{lineno} imports {mod} outside src/intelligence/")
            if (
                mod.startswith("alpaca.trading") or mod == "alpaca.trading"
            ) and not rel_str.startswith("execution/"):
                violations.append(f"{rel_str}:{lineno} imports {mod} outside src/execution/")
            if (mod.startswith("alpaca.data") or mod == "alpaca.data") and not rel_str.startswith(
                "ingestion/"
            ):
                violations.append(f"{rel_str}:{lineno} imports {mod} outside src/ingestion/")

    assert not violations, "SDK allow-list violations:\n" + "\n".join(violations)


def test_ui_layers_have_no_sdk_or_sizing_imports() -> None:
    ui_paths = [SRC_DIR / "api", DASHBOARD_DIR]
    banned_prefixes = ("alpaca", "google.genai", "httpx", "src.risk.sizing")

    violations: list[str] = []
    for p in ui_paths:
        if not p.exists():
            continue
        for py_file in p.rglob("*.py"):
            rel_path = py_file.relative_to(ROOT_DIR)
            for lineno, mod in _get_imports(py_file):
                for banned in banned_prefixes:
                    if mod == banned or mod.startswith(f"{banned}."):
                        violations.append(f"{rel_path}:{lineno} imports banned UI module '{mod}'")

    assert not violations, "UI boundary violations:\n" + "\n".join(violations)


def test_domain_modules_do_not_call_datetime_now() -> None:
    # Domain modules must not call datetime.now() directly; use injected clocks (C-CQ-09)
    # Allow-list: composition roots, config, or tests
    excluded = {"config.py"}
    violations: list[str] = []

    for py_file in SRC_DIR.rglob("*.py"):
        if py_file.name in excluded or "api" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Look for datetime.now(...) or now(...)
                is_now = False
                if (isinstance(func, ast.Attribute) and func.attr == "now") or (
                    isinstance(func, ast.Name) and func.id == "now"
                ):
                    is_now = True
                if is_now:
                    violations.append(
                        f"{py_file.relative_to(ROOT_DIR)}:{node.lineno} calls datetime.now()"
                    )

    assert not violations, (
        "Prohibited datetime.now() calls in domain code (C-CQ-09):\n" + "\n".join(violations)
    )
