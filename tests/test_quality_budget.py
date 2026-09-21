from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import tools.quality_gate as quality_gate
from tools.quality_budget import compare_metrics, measure_repository, measure_source
from tools.quality_gate import compare_debt, pinned_versions, pylint_debt, pyright_fingerprint


def test_measure_source_excludes_comments_blanks_and_docstrings() -> None:
    measured = measure_source(
        '''"""module docs"""

# comment
value = 1

def outer() -> int:
    """function docs"""
    def inner() -> int:
        return value
    return inner()
'''
    )

    assert measured.code_lines == 5
    assert measured.statements == 5
    assert measured.definitions == 2


def test_repository_measurement_automatically_includes_new_files(tmp_path: Path) -> None:
    for directory in ("src", "tests", "tools"):
        (tmp_path / directory).mkdir()
    before = measure_repository(tmp_path)
    (tmp_path / "src" / "new_helper.py").write_text("value = 1\n", encoding="utf-8")
    after = measure_repository(tmp_path)

    assert before["overall"]["code_lines"] == 0
    assert after["groups"]["production"]["files"]["src/new_helper.py"]["code_lines"] == 1
    assert after["overall"]["code_lines"] == 1


def test_budget_comparison_rejects_growth_in_each_metric(tmp_path: Path) -> None:
    for directory in ("src", "tests", "tools"):
        (tmp_path / directory).mkdir()
    (tmp_path / "src" / "runtime.py").write_text("def added():\n    return 1\n", encoding="utf-8")
    actual = measure_repository(tmp_path)
    zero = {"code_lines": 0, "statements": 0, "definitions": 0}
    policy: dict[str, Any] = {
        "budgets": {
            "groups": {name: dict(zero) for name in ("production", "tests", "maintenance")},
            "overall": dict(zero),
        },
        "reduction_targets": [],
    }

    failures = compare_metrics(actual, policy)

    assert any("production.code_lines grew" in failure for failure in failures)
    assert any("overall.statements grew" in failure for failure in failures)
    assert any("overall.definitions grew" in failure for failure in failures)


def test_committed_baseline_is_valid_json() -> None:
    baseline = Path(".quality/baseline.json")
    if baseline.exists():
        assert json.loads(baseline.read_text(encoding="utf-8"))["schema_version"] == 1


def test_debt_comparison_rejects_new_and_worsened_diagnostics() -> None:
    current_pylint = {
        "R0912:src/example.py:legacy": {
            "path": "src/example.py",
            "symbol": "legacy",
            "rule": "R0912",
            "actual": 14,
        }
    }
    current_pyright = [
        {
            "fingerprint": "tests/example.py:reportPrivateUsage:message:source",
            "path": "tests/example.py",
            "rule": "reportPrivateUsage",
            "count": 1,
        }
    ]
    policy: dict[str, Any] = {
        "pylint_debt": {
            "R0912:src/example.py:legacy": 13
        },
        "pyright_debt": {},
    }

    failures = compare_debt(current_pylint, current_pyright, policy)

    assert any("worsened Pylint" in failure for failure in failures)
    assert any("new Pyright reportPrivateUsage" in failure for failure in failures)


def test_pyright_fingerprint_survives_line_motion(tmp_path: Path) -> None:
    path = tmp_path / "example.py"
    path.write_text("value = thing._private\n", encoding="utf-8")
    diagnostic: dict[str, Any] = {
        "file": str(path),
        "rule": "reportPrivateUsage",
        "message": '"_private" is private and used outside its class',
        "range": {"start": {"line": 0, "character": 14}},
    }
    before = pyright_fingerprint(diagnostic)
    path.write_text("\nvalue = thing._private\n", encoding="utf-8")
    diagnostic["range"]["start"]["line"] = 1

    assert pyright_fingerprint(diagnostic) == before


def test_reduction_target_must_match_every_configured_path(tmp_path: Path) -> None:
    for directory in ("src", "tests", "tools"):
        (tmp_path / directory).mkdir()
    actual = measure_repository(tmp_path)
    zero = {"code_lines": 0, "statements": 0, "definitions": 0}
    policy: dict[str, Any] = {
        "budgets": {
            "groups": {name: dict(zero) for name in ("production", "tests", "maintenance")},
            "overall": dict(zero),
        },
        "reduction_targets": [
            {"name": "typo", "paths": ["src/does-not-exist"], "maximum": dict(zero)}
        ],
    }

    assert compare_metrics(actual, policy) == [
        "typo path matches no Python files: src/does-not-exist"
    ]


def test_duplicate_debt_measures_span_and_participant_growth() -> None:
    def message(end: int, files: int) -> dict[str, Any]:
        headers = "\n".join(f"==pf2e.module{index}:[10:{end}]" for index in range(files))
        return {
            "messageId": "R0801",
            "message": f"Similar lines in {files} files\n{headers}\nrepeated()",
            "path": "src/pf2e/example.py",
            "obj": "",
        }

    baseline = next(iter(pylint_debt([message(16, 2)]).values()))
    longer = next(iter(pylint_debt([message(18, 2)]).values()))
    extra_participant = next(iter(pylint_debt([message(16, 3)]).values()))

    assert baseline["actual"] == 6
    assert longer["actual"] == 8
    assert extra_participant["actual"] == 12


def test_quality_requirements_require_exact_pins(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pylint==4.0.8\npyright==1.1.414\n", encoding="utf-8")

    assert pinned_versions(requirements) == {"pylint": "4.0.8", "pyright": "1.1.414"}


def test_policy_change_needs_hash_from_trusted_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(quality_gate, "REPO_ROOT", tmp_path)
    (tmp_path / ".pylintrc").write_bytes(b"proposed")

    def trusted_entry(_ref: str, path: str) -> tuple[str, bytes] | None:
        return ("100644", b"approved") if path == ".pylintrc" else None

    monkeypatch.setattr(quality_gate, "_git_entry", trusted_entry)
    expected = quality_gate.policy_entry_hash(("100644", b"proposed"))

    failures, _authorized = quality_gate.policy_change_failures("base", {})
    allowed, _authorized = quality_gate.policy_change_failures(
        "base", {"approved_policy_hashes": {".pylintrc": expected}}
    )

    assert failures == [
        f"unauthorized policy change .pylintrc; first approve hash {expected} in a separate baseline-only change"
    ]
    assert allowed == []
    assert quality_gate.policy_entry_hash(
        ("100644", b"proposed")
    ) != quality_gate.policy_entry_hash(
        ("100755", b"proposed")
    )


def test_trusted_git_root_and_invalid_ref_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    subprocess.run(["git", "init", "-q"], cwd=trusted, check=True, env=git_env)
    marker = trusted / "marker.txt"
    marker.write_text("trusted\n", encoding="utf-8")
    subprocess.run(["git", "add", "marker.txt"], cwd=trusted, check=True, env=git_env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "trusted"],
        cwd=trusted,
        check=True,
        env={
            **git_env,
            "GIT_AUTHOR_NAME": "Quality Test",
            "GIT_AUTHOR_EMAIL": "quality@example.invalid",
            "GIT_COMMITTER_NAME": "Quality Test",
            "GIT_COMMITTER_EMAIL": "quality@example.invalid",
        },
    )
    monkeypatch.setattr(quality_gate, "TRUSTED_GIT_ROOT", trusted)

    assert quality_gate.git_ref_exists("HEAD")
    assert not quality_gate.git_ref_exists("definitely-missing")
    assert quality_gate.git_show("HEAD", "marker.txt") == b"trusted\n"


def test_hook_policy_entry_includes_executable_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(quality_gate, "REPO_ROOT", tmp_path)
    hook = tmp_path / ".githooks" / "pre-push"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    hook.chmod(0o644)
    assert quality_gate.working_policy_entry(".githooks/pre-push") == (
        "100644",
        b"#!/bin/sh\n",
    )

    hook.chmod(0o755)
    assert quality_gate.working_policy_entry(".githooks/pre-push") == (
        "100755",
        b"#!/bin/sh\n",
    )
