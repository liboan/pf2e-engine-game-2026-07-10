#!/usr/bin/env python3
"""Install or audit the checked-in hooks without clobbering existing hooks."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".githooks"


def git(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )


def current_hooks_path(cwd: Path = REPO_ROOT) -> str | None:
    result = git("config", "--path", "--get", "core.hooksPath", cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else None


def _default_pre_push(cwd: Path) -> Path | None:
    result = git("rev-parse", "--git-path", "hooks/pre-push", cwd=cwd)
    if result.returncode:
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else cwd / path


def audit_worktrees() -> int:
    result = git("worktree", "list", "--porcelain")
    if result.returncode:
        print(result.stderr, end="")
        return result.returncode
    paths = [Path(line.removeprefix("worktree ")) for line in result.stdout.splitlines() if line.startswith("worktree ")]
    for path in paths:
        configured = current_hooks_path(path)
        default_hook = _default_pre_push(path)
        default_status = "present" if default_hook and default_hook.exists() else "none"
        print(f"{path}: core.hooksPath={configured or '<unset>'}; default-pre-push={default_status}")
    return 0


def install() -> int:
    expected = str(HOOKS_DIR.resolve())
    configured = current_hooks_path()
    default_hook = _default_pre_push(REPO_ROOT)
    if configured and Path(configured).resolve() != HOOKS_DIR.resolve():
        print(f"refusing to replace existing core.hooksPath={configured}")
        return 2
    if not configured and default_hook and default_hook.exists():
        print(f"refusing to bypass existing hook {default_hook}")
        return 2

    extension = git("config", "--get", "extensions.worktreeConfig")
    if extension.stdout.strip().lower() != "true":
        enabled = git("config", "extensions.worktreeConfig", "true")
        if enabled.returncode:
            print(enabled.stderr, end="")
            return enabled.returncode
    configured_result = git("config", "--worktree", "core.hooksPath", expected)
    if configured_result.returncode:
        print(configured_result.stderr, end="")
        return configured_result.returncode

    hook = HOOKS_DIR / "pre-push"
    hook.chmod(hook.stat().st_mode | 0o111)
    print(f"installed worktree-local core.hooksPath={expected}")
    return 0


def check() -> int:
    expected = HOOKS_DIR.resolve()
    configured = current_hooks_path()
    if configured is None or Path(configured).resolve() != expected:
        print(f"hook inactive: run {Path(__file__).relative_to(REPO_ROOT)}")
        return 1
    hook = HOOKS_DIR / "pre-push"
    if not hook.is_file() or not os.access(hook, os.X_OK):
        print(f"hook inactive: {hook} is missing or not executable")
        return 1
    print(f"hook active for this worktree: {expected}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--audit-worktrees", action="store_true")
    args = parser.parse_args(argv)
    if args.audit_worktrees:
        return audit_worktrees()
    if args.check:
        return check()
    return install()


if __name__ == "__main__":
    raise SystemExit(main())
