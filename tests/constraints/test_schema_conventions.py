import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"


def test_no_pydantic_v1_patterns() -> None:
    violations: list[str] = []

    for py_file in SRC_DIR.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        rel_path = py_file.relative_to(ROOT_DIR)

        for node in ast.walk(tree):
            # Check for pydantic.v1 import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pydantic.v1" in alias.name:
                        violations.append(f"{rel_path}:{node.lineno} imports pydantic.v1")
            elif isinstance(node, ast.ImportFrom) and node.module and "pydantic.v1" in node.module:
                violations.append(f"{rel_path}:{node.lineno} imports from pydantic.v1")

            # Check for inner class Config
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.ClassDef) and item.name == "Config":
                        violations.append(
                            f"{rel_path}:{item.lineno} defines inner 'class Config:' (use model_config)"
                        )

            # Check for @validator or @root_validator
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    dec_name = ""
                    if isinstance(dec, ast.Name):
                        dec_name = dec.id
                    elif isinstance(dec, ast.Attribute):
                        dec_name = dec.attr
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            dec_name = dec.func.id
                        elif isinstance(dec.func, ast.Attribute):
                            dec_name = dec.func.attr
                    if dec_name in ("validator", "root_validator"):
                        violations.append(f"{rel_path}:{node.lineno} uses deprecated @{dec_name}")

    assert not violations, "Pydantic v1 patterns found (C-CQ-03):\n" + "\n".join(violations)


def _iter_src_models() -> list[tuple[str, type[BaseModel]]]:
    models: list[tuple[str, type[BaseModel]]] = []
    # Import all modules under src
    for module_info in pkgutil.walk_packages([str(SRC_DIR)], prefix="src."):
        try:
            mod = importlib.import_module(module_info.name)
        except Exception:
            continue
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(cls, BaseModel)
                and cls not in (BaseModel, BaseSettings)
                and not issubclass(cls, BaseSettings)
                and cls.__module__.startswith("src.")
            ):
                models.append((f"{cls.__module__}.{name}", cls))
    return models


def test_boundary_models_forbid_extra_and_frozen() -> None:
    models = _iter_src_models()
    assert models, "No Pydantic models found in src/"

    violations: list[str] = []
    for full_name, model_cls in models:
        config = model_cls.model_config
        extra = config.get("extra")
        if extra != "forbid":
            violations.append(f"{full_name}: model_config['extra'] is '{extra}', must be 'forbid'")

        # Domain records, order intents, and LLM outputs must be frozen=True (C-CQ-04)
        if any(
            keyword in full_name.lower()
            for keyword in ["order", "intent", "bar", "snapshot", "cluster", "analysis", "signal"]
        ):
            frozen = config.get("frozen")
            if not frozen:
                violations.append(f"{full_name}: model_config['frozen'] is False, must be True")

    assert not violations, "Model configuration violations (C-CQ-04):\n" + "\n".join(violations)


def test_all_at_fields_are_aware_datetime() -> None:
    models = _iter_src_models()
    violations: list[str] = []

    for full_name, model_cls in models:
        for field_name, field_info in model_cls.model_fields.items():
            if field_name.endswith("_at"):
                ann = str(field_info.annotation)
                if "datetime" not in ann:
                    violations.append(
                        f"{full_name}.{field_name} ends in '_at' but "
                        f"annotation is '{ann}', expected datetime"
                    )

    assert not violations, "Timestamp field annotation violations (C-CQ-04):\n" + "\n".join(
        violations
    )
