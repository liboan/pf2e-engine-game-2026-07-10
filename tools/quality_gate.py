#!/usr/bin/env python3
"""Run ratcheted Pylint, Pyright, and aggregate size enforcement."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(os.environ.get("PF2E_REPO_ROOT", SCRIPT_ROOT)).resolve()
TRUSTED_GIT_ROOT = Path(os.environ.get("PF2E_TRUSTED_GIT_ROOT", REPO_ROOT)).resolve()
sys.path.insert(0, str(SCRIPT_ROOT))

from tools.quality_budget import compare_metrics, load_policy, measure_repository  # noqa: E402


POLICY_PATH = REPO_ROOT / ".quality" / "baseline.json"
POLICY_FILES = (
    ".githooks/pre-push",
    ".github/workflows/quality.yml",
    ".github/workflows/trusted-policy.yml",
    ".pylintrc",
    "pyrightconfig.json",
    "pyproject.toml",
    "requirements-quality.txt",
    "tools/install_git_hooks.py",
    "tools/__init__.py",
    "tools/integration_checkpoint.py",
    "tools/quality_budget.py",
    "tools/quality_gate.py",
)
COUNT_RE = re.compile(r"\((\d+)/(\d+)\)")
DUPLICATE_HEADER_RE = re.compile(r"^==([\w.]+):\[(\d+):(\d+)\]$")


def _run(command: list[str], *, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _relative(path: str) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _significant_lines(path: Path, start: int = 0, end: int | None = None) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[start:end]
    except OSError:
        return []
    return [" ".join(line.split()) for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _longest_common_block(sequences: Sequence[Sequence[str]]) -> tuple[str, ...]:
    if not sequences or any(not sequence for sequence in sequences):
        return ()
    shortest = min(sequences, key=len)
    for size in range(len(shortest), 5, -1):
        for start in range(len(shortest) - size + 1):
            candidate = tuple(shortest[start : start + size])
            if all(
                any(tuple(sequence[index : index + size]) == candidate for index in range(len(sequence) - size + 1))
                for sequence in sequences
            ):
                return candidate
    return ()


def _duplicate_signature(item: Mapping[str, Any]) -> tuple[str, int]:
    ranges: list[tuple[str, int, int]] = []
    for line in str(item["message"]).splitlines():
        match = DUPLICATE_HEADER_RE.match(line)
        if match:
            ranges.append((match.group(1), int(match.group(2)), int(match.group(3))))
    sequences = [
        _significant_lines(REPO_ROOT / (module.replace(".", "/") + ".py"), start, end)
        for module, start, end in ranges
    ]
    common = _longest_common_block(sequences)
    if common:
        occurrences = 0
        for path in (REPO_ROOT / "src").rglob("*.py"):
            sequence = _significant_lines(path)
            occurrences += sum(
                tuple(sequence[index : index + len(common)]) == common
                for index in range(len(sequence) - len(common) + 1)
            )
        return f"R0801:{_digest(chr(10).join(common))}", len(common) * max(occurrences - 1, 1)

    modules = sorted(module for module, _start, _end in ranges)
    spans = [end - start for _module, start, end in ranges]
    return f"R0801:{_digest(':'.join(modules))}", min(spans, default=1) * max(len(ranges) - 1, 1)


def pylint_fingerprint(item: Mapping[str, Any]) -> str:
    message_id = str(item["messageId"])
    if message_id == "R0801":
        return _duplicate_signature(item)[0]
    return ":".join(
        (message_id, _relative(str(item["path"])), str(item.get("obj", "")))
    )


def pylint_debt(messages: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    debt: dict[str, dict[str, Any]] = {}
    for item in messages:
        fingerprint = pylint_fingerprint(item)
        match = COUNT_RE.search(str(item["message"]))
        duplicate_size = _duplicate_signature(item)[1]
        record = {
            "path": _relative(str(item["path"])),
            "symbol": str(item.get("obj", "")),
            "rule": str(item["messageId"]),
            "actual": int(match.group(1)) if match else duplicate_size,
        }
        if fingerprint in debt and record["rule"] == "R0801":
            record["actual"] = max(record["actual"], debt[fingerprint]["actual"])
        debt[fingerprint] = record
    return debt


def _source_line(path: Path, line: int) -> str:
    try:
        return " ".join(path.read_text(encoding="utf-8").splitlines()[line].split())
    except (OSError, IndexError):
        return ""


def pyright_fingerprint(item: Mapping[str, Any]) -> str:
    path = Path(str(item["file"]))
    relative = _relative(str(path))
    rule = str(item.get("rule") or "unclassified")
    message = " ".join(str(item["message"]).split())
    line = int(item["range"]["start"]["line"])
    source = _source_line(path, line)
    return f"{relative}:{rule}:{_digest(message)}:{_digest(source)}"


def pyright_debt(messages: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for item in messages:
        fingerprint = pyright_fingerprint(item)
        counts[fingerprint] += 1
        records[fingerprint] = {
            "fingerprint": fingerprint,
            "path": _relative(str(item["file"])),
            "rule": str(item.get("rule") or "unclassified"),
        }
    return [dict(records[key], count=counts[key]) for key in sorted(records)]


def compact_pylint_debt(messages: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return {key: int(record["actual"]) for key, record in pylint_debt(messages).items()}


def compact_pyright_debt(messages: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return {
        str(record["fingerprint"]): int(record["count"])
        for record in pyright_debt(messages)
    }


def _tool(command: str) -> str:
    candidate = Path(sys.executable).with_name(command)
    return str(candidate) if candidate.exists() else command


def pinned_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator or not name or not version:
            raise ValueError(f"quality dependency must use an exact == pin: {raw_line}")
        versions[name] = version
    return versions


def version_failures(requirements: Path, *, allow_drift: bool) -> list[str]:
    if allow_drift:
        print("trusted dependency-version check was satisfied by prior hash authorization")
        return []
    failures: list[str] = []
    for package, expected in pinned_versions(requirements).items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"missing pinned quality dependency {package}=={expected}")
            continue
        print(f"quality_dependency {package}: expected={expected} actual={actual}")
        if actual != expected:
            failures.append(f"quality dependency {package} must be {expected}, found {actual}")
    return failures


def collect_pylint(rcfile: Path = REPO_ROOT / ".pylintrc") -> tuple[int, list[dict[str, Any]], str]:
    result = _run(
        [
            _tool("pylint"),
            f"--rcfile={rcfile}",
            "--output-format=json2",
            "src/pf2e",
        ],
        env={**os.environ, "PYTHONPATH": "src"},
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.returncode, [], result.stdout
    return result.returncode, list(payload["messages"]), ""


def collect_pyright(project: Path = REPO_ROOT / "pyrightconfig.json") -> tuple[int, list[dict[str, Any]], str]:
    result = _run([_tool("pyright"), "--project", str(project), "--outputjson"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.returncode, [], result.stdout
    return result.returncode, list(payload["generalDiagnostics"]), ""


def collect_pair(
    pylint_config: Path = REPO_ROOT / ".pylintrc",
    pyright_config: Path = REPO_ROOT / "pyrightconfig.json",
) -> tuple[
    tuple[int, list[dict[str, Any]], str],
    tuple[int, list[dict[str, Any]], str],
]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        pylint_future = executor.submit(collect_pylint, pylint_config)
        pyright_future = executor.submit(collect_pyright, pyright_config)
        return pylint_future.result(), pyright_future.result()


def git_environment() -> dict[str, str]:
    """Return an environment free of Git's caller/repository-local overrides."""

    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def git_show(ref: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=TRUSTED_GIT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=git_environment(),
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def git_ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
        cwd=TRUSTED_GIT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=git_environment(),
        check=False,
    )
    return result.returncode == 0


def _git_entry(ref: str, path: str) -> tuple[str, bytes] | None:
    result = subprocess.run(
        ["git", "ls-tree", ref, "--", path],
        cwd=TRUSTED_GIT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=git_environment(),
        check=False,
    )
    if result.returncode or not result.stdout.strip():
        return None
    metadata, listed_path = result.stdout.rstrip("\n").split("\t", 1)
    mode, object_type, _object_id = metadata.split()
    if listed_path != path or object_type != "blob":
        return mode, b""
    return mode, git_show(ref, path) or b""


def working_policy_entry(path: str) -> tuple[str, bytes] | None:
    candidate = REPO_ROOT / path
    try:
        details = candidate.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(details.st_mode):
        return "120000", os.readlink(candidate).encode("utf-8")
    if not stat.S_ISREG(details.st_mode):
        return "000000", b""
    mode = "100755" if details.st_mode & 0o111 else "100644"
    return mode, candidate.read_bytes()


def policy_entry_hash(entry: tuple[str, bytes] | None) -> str:
    if entry is None:
        return "<deleted>"
    mode, content = entry
    return hashlib.sha256(mode.encode("ascii") + b"\0" + content).hexdigest()


def approved_policy(ref: str | None) -> dict[str, Any] | None:
    if not ref:
        return None
    baseline = git_show(ref, ".quality/baseline.json")
    if baseline is None:
        print(f"policy trust: {ref} has no baseline; allowing one-time bootstrap")
        return None
    return json.loads(baseline)


def policy_change_failures(ref: str, policy: Mapping[str, Any]) -> tuple[list[str], bool]:
    failures: list[str] = []
    requirements_authorized = False
    approvals = cast(Mapping[str, str], policy.get("approved_policy_hashes", {}))
    changed: list[str] = []
    for path in POLICY_FILES:
        base_entry = _git_entry(ref, path)
        current_entry = working_policy_entry(path)
        if base_entry == current_entry:
            continue
        changed.append(path)
        actual_hash = policy_entry_hash(current_entry)
        if approvals.get(path) != actual_hash:
            failures.append(
                f"unauthorized policy change {path}; first approve hash {actual_hash} in a separate baseline-only change"
            )
        elif path == "requirements-quality.txt":
            requirements_authorized = True
    if changed:
        print("policy files changed: " + ", ".join(changed))
    return failures, requirements_authorized


def run_trusted_gate(ref: str, *, allow_version_drift: bool) -> subprocess.CompletedProcess[str]:
    required = (
        "tools/__init__.py",
        "tools/quality_budget.py",
        "tools/quality_gate.py",
        ".pylintrc",
        "pyrightconfig.json",
        "requirements-quality.txt",
        ".quality/baseline.json",
    )
    with tempfile.TemporaryDirectory(prefix="pf2e-trusted-gate-") as directory:
        root = Path(directory)
        for path in required:
            content = git_show(ref, path)
            if content is None:
                return subprocess.CompletedProcess(
                    args=[], returncode=2, stdout=f"trusted policy is missing {path}\n", stderr=""
                )
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        with tempfile.NamedTemporaryFile(
            dir=REPO_ROOT, prefix=".trusted-pyright-", suffix=".json"
        ) as pyright_file:
            pyright_file.write((root / "pyrightconfig.json").read_bytes())
            pyright_file.flush()
            command = [
                sys.executable,
                str(root / "tools/quality_gate.py"),
                "--no-trusted",
                "--policy",
                str(root / ".quality/baseline.json"),
                "--pylint-config",
                str(root / ".pylintrc"),
                "--pyright-config",
                pyright_file.name,
                "--requirements",
                str(root / "requirements-quality.txt"),
            ]
            if allow_version_drift:
                command.append("--allow-version-drift")
            return _run(command, env={**os.environ, "PF2E_REPO_ROOT": str(REPO_ROOT)})


def compare_debt(
    current_pylint: Mapping[str, Mapping[str, Any]],
    current_pyright: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    allowed_pylint = cast(Mapping[str, int], policy["pylint_debt"])
    for fingerprint, record in current_pylint.items():
        allowed = allowed_pylint.get(fingerprint)
        if allowed is None:
            failures.append(
                f"new Pylint {record['rule']} at {record['path']}:{record['symbol'] or '<module>'}"
            )
        elif record["actual"] > allowed:
            failures.append(
                f"worsened Pylint {record['rule']} at {record['path']}:{record['symbol'] or '<module>'} "
                f"({allowed} -> {record['actual']})"
            )

    allowed_pyright = Counter(cast(Mapping[str, int], policy["pyright_debt"]))
    current_counter = Counter(
        {record["fingerprint"]: int(record["count"]) for record in current_pyright}
    )
    record_by_key = {record["fingerprint"]: record for record in current_pyright}
    for fingerprint, count in current_counter.items():
        if count > allowed_pyright[fingerprint]:
            record = record_by_key[fingerprint]
            failures.append(
                f"new Pyright {record['rule']} at {record['path']} "
                f"(allowed {allowed_pyright[fingerprint]}, actual {count})"
            )
    return failures


def build_baseline(source_revision: str, pylint_messages: list[dict[str, Any]], pyright_messages: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = measure_repository(REPO_ROOT)
    return {
        "schema_version": 1,
        "source_revision": source_revision,
        "counting_convention": "token code lines; non-docstring ast.stmt; all sync/async function and method definitions",
        "budgets": {
            "groups": {
                name: metrics["groups"][name]["total"] for name in ("production", "tests", "maintenance")
            },
            "overall": metrics["overall"],
        },
        "approved_policy_hashes": {},
        "reduction_targets": [],
        "pylint_debt": compact_pylint_debt(pylint_messages),
        "pyright_debt": compact_pyright_debt(pyright_messages),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trusted-ref",
        default=os.environ.get("PF2E_TRUSTED_BASE", "origin/main"),
        help="approved base ref whose implementation and policy must also gate this tree",
    )
    parser.add_argument("--no-trusted", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--pylint-config", type=Path, default=REPO_ROOT / ".pylintrc")
    parser.add_argument("--pyright-config", type=Path, default=REPO_ROOT / "pyrightconfig.json")
    parser.add_argument("--requirements", type=Path, default=REPO_ROOT / "requirements-quality.txt")
    parser.add_argument("--allow-version-drift", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--source-revision", help="named source revision for a new baseline")
    args = parser.parse_args(argv)

    trusted_ref = None if args.no_trusted else args.trusted_ref
    if trusted_ref and not git_ref_exists(trusted_ref):
        print(f"ERROR: trusted ref does not resolve to a commit: {trusted_ref}")
        return 2
    failures = version_failures(args.requirements, allow_drift=args.allow_version_drift)
    hook_entry = working_policy_entry(".githooks/pre-push")
    if hook_entry is None or hook_entry[0] != "100755":
        failures.append(".githooks/pre-push must be a regular executable file (Git mode 100755)")
    pylint_result, pyright_result = collect_pair(args.pylint_config, args.pyright_config)
    pylint_exit, pylint_messages, pylint_error = pylint_result
    pyright_exit, pyright_messages, pyright_error = pyright_result
    if pylint_error or pyright_error:
        print(pylint_error or pyright_error, end="")
        return 2
    print(f"pylint_diagnostics={len(pylint_messages)} pylint_exit={pylint_exit}")
    print(f"pyright_diagnostics={len(pyright_messages)} pyright_exit={pyright_exit}")

    if args.write_baseline:
        if not args.source_revision:
            parser.error("--source-revision is required with --write-baseline")
        baseline = build_baseline(args.source_revision, pylint_messages, pyright_messages)
        args.policy.parent.mkdir(parents=True, exist_ok=True)
        args.policy.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.policy}")
        return bool(failures)

    policy = load_policy(args.policy)
    approved = approved_policy(trusted_ref)
    baseline_changed = bool(
        trusted_ref
        and approved is not None
        and git_show(trusted_ref, ".quality/baseline.json") != args.policy.read_bytes()
    )
    failures.extend(compare_debt(pylint_debt(pylint_messages), pyright_debt(pyright_messages), policy))
    failures.extend(
        compare_metrics(measure_repository(REPO_ROOT), policy, enforce_targets=not baseline_changed)
    )
    if trusted_ref and approved is not None:
        policy_failures, requirements_authorized = policy_change_failures(trusted_ref, approved)
        failures.extend(policy_failures)
        trusted_result = run_trusted_gate(
            trusted_ref, allow_version_drift=requirements_authorized
        )
        print("trusted_gate_output_begin")
        print(trusted_result.stdout, end="")
        print("trusted_gate_output_end")
        if trusted_result.returncode:
            failures.append(f"trusted gate failed with exit {trusted_result.returncode}")

    for failure in failures:
        print(f"ERROR: {failure}")
    if not failures:
        print("quality_gate=passed")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
