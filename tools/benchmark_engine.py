#!/usr/bin/env python3
"""Small S1 command/query and scripted-terminal timing baseline.

Run from the repository root with ``python3 tools/benchmark_engine.py``.
Only aggregate timings are printed; no profiles or raw traces are written.
"""

from __future__ import annotations

import argparse
import math
import platform
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pf2e.content import S1_SETUP  # noqa: E402
from pf2e.encounter import Encounter  # noqa: E402
from pf2e.model import EndTurn  # noqa: E402
from pf2e.terminal import run_terminal  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def command_query_samples(samples: int, seed: int) -> list[float]:
    timings: list[float] = []
    for sample in range(samples):
        game = Encounter.start(setup=S1_SETUP, seed=seed + sample)
        start = time.perf_counter_ns()
        result = game.execute(EndTurn())
        game.inspect()
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        if str(getattr(result.status, "value", result.status)).lower() == "rejected":
            raise RuntimeError(f"benchmark EndTurn rejected: {result.message}")
        timings.append(elapsed)
    return timings


def scripted_menu_samples(samples: int, seed: int) -> list[float]:
    timings: list[float] = []
    for sample in range(samples):
        started: int | None = None
        prompt_count = 0

        def next_input() -> str:
            nonlocal started, prompt_count
            prompt_count += 1
            if prompt_count == 1:
                started = time.perf_counter_ns()
                return "5"  # End Turn
            if prompt_count == 2:
                if started is None:
                    raise RuntimeError("terminal benchmark missed its first prompt")
                timings.append((time.perf_counter_ns() - started) / 1_000_000)
                return "9"  # Quit
            raise RuntimeError("terminal benchmark requested unexpected extra input")

        run_terminal(
            setup=S1_SETUP,
            seed=seed + sample,
            input_fn=next_input,
            output_fn=lambda _line: None,
        )
    return timings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=41)
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error("--samples must be at least 1")

    command_timings = command_query_samples(args.samples, args.seed)
    menu_timings = scripted_menu_samples(args.samples, args.seed + args.samples)
    command_p95 = percentile(command_timings, 0.95)
    menu_p95 = percentile(menu_timings, 0.95)

    print(f"Machine: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Workload: S1 setup, EndTurn + inspect; {args.samples} samples per measurement")
    print(
        "Command + next query p95: "
        f"{command_p95:.3f} ms (provisional target <100 ms; "
        f"median {statistics.median(command_timings):.3f} ms)"
    )
    print(
        "Scripted input to next menu p95: "
        f"{menu_p95:.3f} ms (provisional target <250 ms; "
        f"median {statistics.median(menu_timings):.3f} ms)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
