#!/usr/bin/env python3
"""Measure and enforce small, repository-wide Python size budgets."""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import tokenize
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast


REPO_ROOT = Path(os.environ.get("PF2E_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
DEFAULT_POLICY = REPO_ROOT / ".quality" / "baseline.json"
GROUPS: Mapping[str, str] = {
    "production": "src",
    "tests": "tests",
    "maintenance": "tools",
}


@dataclass(frozen=True)
class Metrics:
    code_lines: int = 0
    statements: int = 0
    definitions: int = 0

    def __add__(self, other: Metrics) -> Metrics:
        return Metrics(
            self.code_lines + other.code_lines,
            self.statements + other.statements,
            self.definitions + other.definitions,
        )


def _docstring_nodes(tree: ast.AST) -> Iterable[ast.Expr]:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            yield first


def measure_source(source: str, *, filename: str = "<memory>") -> Metrics:
    """Count code-bearing lines, non-docstring statements, and definitions.

    A code-bearing line contains at least one significant Python token. Blank
    lines, comments, and lines occupied only by a standalone module/class/
    function docstring are excluded. Every ``ast.stmt`` except those
    standalone docstring expressions is counted. Function and async-function
    definitions include methods and nested functions.
    """

    tree = ast.parse(source, filename=filename)
    ignored_token_types = {
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.COMMENT,
    }
    code_lines = {
        token.start[0]
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in ignored_token_types
    }
    docstrings = set(_docstring_nodes(tree))
    for node in docstrings:
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        code_lines.difference_update(range(start, end + 1))

    statements = sum(
        1 for node in ast.walk(tree) if isinstance(node, ast.stmt) and node not in docstrings
    )
    definitions = sum(
        1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return Metrics(len(code_lines), statements, definitions)


def python_files(root: Path, group_dir: str) -> list[Path]:
    """Return all tracked-source Python paths in a budget group.

    Build products, virtual environments, and third-party dependencies live
    outside the three fixed first-party roots and are therefore excluded.
    New ``.py`` files below a root are included automatically, even before
    they are added to Git.
    """

    directory = root / group_dir
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.py") if path.is_file())


def measure_repository(root: Path = REPO_ROOT) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    overall = Metrics()
    for name, group_dir in GROUPS.items():
        total = Metrics()
        files: dict[str, dict[str, int]] = {}
        for path in python_files(root, group_dir):
            relative = path.relative_to(root).as_posix()
            measured = measure_source(path.read_text(encoding="utf-8"), filename=relative)
            total += measured
            files[relative] = asdict(measured)
        groups[name] = {"total": asdict(total), "files": files}
        overall += total
    return {"groups": groups, "overall": asdict(overall)}


def _metric_failures(
    actual: Mapping[str, int], limit: Mapping[str, int], *, label: str
) -> list[str]:
    failures: list[str] = []
    for metric in ("code_lines", "statements", "definitions"):
        value = actual[metric]
        maximum = limit[metric]
        print(f"budget {label}.{metric}: baseline={maximum} actual={value}")
        if value > maximum:
            failures.append(f"{label}.{metric} grew by {value - maximum} ({maximum} -> {value})")
    return failures


def compare_metrics(
    actual: Mapping[str, Any], policy: Mapping[str, Any], *, enforce_targets: bool = True
) -> list[str]:
    failures: list[str] = []
    budgets = policy["budgets"]
    for group in GROUPS:
        failures.extend(
            _metric_failures(
                actual["groups"][group]["total"], budgets["groups"][group], label=group
            )
        )
    failures.extend(_metric_failures(actual["overall"], budgets["overall"], label="overall"))

    targets = (
        cast(Sequence[Mapping[str, Any]], policy.get("reduction_targets", []))
        if enforce_targets
        else ()
    )
    for target in targets:
        paths = tuple(str(path) for path in cast(Sequence[object], target["paths"]))
        aggregate = Metrics()
        matched = {prefix: False for prefix in paths}
        for group_name in GROUPS:
            for path, values in actual["groups"][group_name]["files"].items():
                matching = [
                    prefix for prefix in paths if path == prefix or path.startswith(f"{prefix}/")
                ]
                if matching:
                    aggregate += Metrics(**values)
                    for prefix in matching:
                        matched[prefix] = True
        for prefix, did_match in matched.items():
            if not did_match:
                failures.append(f"{target['name']} path matches no Python files: {prefix}")
        maximum = cast(Mapping[str, int], target["maximum"])
        failures.extend(_metric_failures(asdict(aggregate), maximum, label=str(target["name"])))
    return failures


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--json", action="store_true", help="print measurements as JSON")
    args = parser.parse_args(argv)

    actual = measure_repository(args.root.resolve())
    if args.json:
        print(json.dumps(actual, indent=2, sort_keys=True))
        return 0
    failures = compare_metrics(actual, load_policy(args.policy))
    for failure in failures:
        print(f"ERROR: {failure}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
