#!/usr/bin/env python3
"""Run one bounded integration checkpoint with local health metrics.

The checkpoint is deliberately serial: compile, the full pytest suite, and
the whitespace check run as separate child processes.  The test child is
timed and its peak resident set size is reported using ``resource``.
"""

from __future__ import annotations

import platform
import resource
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    compile_result = run([sys.executable, "-m", "compileall", "-q", "src"])
    print(f"compile_exit={compile_result.returncode}")
    if compile_result.returncode:
        print(compile_result.stdout, end="")
        return compile_result.returncode

    started = time.perf_counter()
    pytest_result = run([sys.executable, "-m", "pytest", "-q"])
    elapsed = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_unit = "bytes" if platform.system() == "Darwin" else "KiB"
    print(f"pytest_exit={pytest_result.returncode} pytest_seconds={elapsed:.3f}")
    print(f"pytest_child_maxrss={usage.ru_maxrss} {rss_unit}")
    print(pytest_result.stdout, end="")
    if pytest_result.returncode:
        return pytest_result.returncode

    diff_result = run(["git", "diff", "--check"])
    print(f"diff_check_exit={diff_result.returncode}")
    if diff_result.returncode:
        print(diff_result.stdout, end="")
        return diff_result.returncode

    from pf2e import content, persistence  # noqa: PLC0415

    print(f"accepted_setups={len(content.SETUPS)} accepted_creatures={len(content.CREATURES)}")
    print(
        f"staged_setups={len(content._STAGED_SETUPS)} "
        f"staged_creatures={len(content._STAGED_CREATURES)} "
        f"save_version={persistence.SAVE_VERSION}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
