"""Focused metadata-only usage collector fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "tools" / "log_agent_usage.py"
sys.path.insert(0, str(SCRIPT.parent))
from log_agent_usage import session_snapshot


def row(kind: str, stamp: str, payload: dict) -> str:
    return json.dumps({"type": kind, "timestamp": stamp, "payload": payload})


def usage(input_tokens: int, cached: int, output: int) -> dict:
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "cache_write_input_tokens": 0,
    }


def record(thread_id: str, response_id: str, stamp: str, values: dict, cumulative: dict, turn: str = "turn-1") -> str:
    return row(
        "token_usage_record",
        stamp,
        {
            "response_id": response_id,
            "root_turn_id": "root-turn",
            "session_id": thread_id,
            "thread_id": thread_id,
            "turn_id": turn,
            "usage": values,
            "thread_token_usage": cumulative,
        },
    )


def write_session(root: Path, thread_id: str, lines: list[str], *, agent_path: str = "/root/worker") -> Path:
    folder = root / "2026" / "09" / "15"
    folder.mkdir(parents=True)
    path = folder / "rollout-arbitrary-name.jsonl"
    meta = {
        "id": thread_id,
        "session_id": thread_id,
        "parent_thread_id": "00000000-0000-4000-8000-000000000099",
        "agent_path": agent_path,
        "cwd": "/workspace",
        "model_provider": "openai",
        "thread_source": "subagent",
        "timestamp": "2026-09-15T12:00:00.000Z",
        "base_instructions": {"text": "must never appear in snapshot"},
    }
    path.write_text("\n".join([row("session_meta", meta["timestamp"], meta), *lines]) + "\n", encoding="utf-8")
    return path


def test_snapshot_deduplicates_parent_and_compaction_records_and_keeps_config(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000001"
    parent_usage = usage(999, 500, 99)
    first = usage(10, 5, 1)
    second = usage(20, 10, 2)
    lines = [
        record("parent", "parent-response", "before", parent_usage, parent_usage),
        row("turn_context", "2026-09-15T12:00:01.000Z", {"model": "gpt-5.6-luna", "effort": "xhigh", "turn_id": "turn-1"}),
        record(thread_id, "response-1", "2026-09-15T12:00:02.000Z", first, first),
        record(thread_id, "response-1", "2026-09-15T12:00:02.001Z", first, first),
        row("compacted", "2026-09-15T12:00:03.000Z", {"compaction_response_id": "response-2"}),
        record(thread_id, "response-2", "2026-09-15T12:00:03.001Z", second, usage(30, 15, 3)),
        row("event_msg", "2026-09-15T12:00:04.000Z", {"type": "task_complete", "completed_at": "done"}),
        json.dumps({"type": "user_message", "text": "private transcript"}),
    ]
    write_session(tmp_path, thread_id, lines, agent_path="/root/metadata-worker")

    snapshot = session_snapshot(thread_id, tmp_path)

    assert snapshot["request_count"] == 2
    assert snapshot["duplicate_request_count"] == 1
    assert snapshot["compaction_request_count"] == 1
    assert snapshot["request_usage_totals"] == {
        "input_tokens": 30,
        "cached_input_tokens": 15,
        "output_tokens": 3,
        "cache_write_input_tokens": 0,
    }
    assert snapshot["configs"] == [{
        "model": "gpt-5.6-luna",
        "reasoning_effort": "xhigh",
        "turn_id": "turn-1",
        "timestamp": "2026-09-15T12:00:01.000Z",
    }]
    assert snapshot["final_seen"] is True
    assert snapshot["agent_path"] == "/root/metadata-worker"
    assert "private transcript" not in json.dumps(snapshot)
    assert "must never appear" not in json.dumps(snapshot)


def test_snapshot_can_discover_session_by_agent_path_and_nested_compaction_record(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000002"
    nested = {
        "response_id": "compaction-response",
        "usage": usage(7, 2, 1),
        "thread_token_usage": usage(7, 2, 1),
        "thread_id": thread_id,
        "turn_id": "turn-1",
    }
    write_session(
        tmp_path,
        thread_id,
        [row("compacted", "2026-09-15T12:01:00.000Z", {
            "compaction_response_id": "compaction-response",
            "latest_token_usage_record": nested,
        })],
        agent_path="/root/nested-worker",
    )

    snapshot = session_snapshot(None, tmp_path, agent_path="/root/nested-worker")

    assert snapshot["thread_id"] == thread_id
    assert snapshot["request_count"] == 1
    assert snapshot["compaction_request_count"] == 1
    assert snapshot["request_usage_totals"]["output_tokens"] == 1


def test_snapshot_excludes_parent_record_after_local_session_boundary_when_thread_id_is_missing(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000007"
    parent_id = "00000000-0000-4000-8000-000000000008"
    inherited = {
        "response_id": "parent-after-boundary",
        "session_id": parent_id,
        "usage": usage(99, 10, 9),
        "thread_token_usage": usage(99, 10, 9),
    }
    local = {
        "response_id": "local-record",
        "session_id": parent_id,
        "thread_id": thread_id,
        "usage": usage(3, 1, 1),
        "thread_token_usage": usage(102, 11, 10),
    }
    write_session(
        tmp_path,
        thread_id,
        [row("token_usage_record", "2026-09-15T12:01:01.000Z", inherited),
         row("token_usage_record", "2026-09-15T12:01:02.000Z", local)],
    )

    snapshot = session_snapshot(thread_id, tmp_path)

    assert snapshot["request_count"] == 1
    assert snapshot["request_usage_totals"] == {
        "input_tokens": 3,
        "cached_input_tokens": 1,
        "output_tokens": 1,
        "cache_write_input_tokens": 0,
    }
    assert [record["response_id"] for record in snapshot["requests"]] == ["local-record"]


def run_cli(sessions_root: Path, ledger: Path, *args: str) -> dict:
    command = [sys.executable, str(SCRIPT), "--sessions-root", str(sessions_root), *args]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_dispatch_bootstraps_fresh_worker_and_complete_records_actual_status_result(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000003"
    first = usage(12, 6, 2)
    write_session(
        tmp_path / "sessions",
        thread_id,
        [
            row("turn_context", "2026-09-15T12:02:01.000Z", {"model": "gpt-5.6-sol", "effort": "high", "turn_id": "turn-1"}),
            record(thread_id, "response-1", "2026-09-15T12:02:02.000Z", first, first),
            row("event_msg", "2026-09-15T12:02:03.000Z", {"type": "task_complete", "completed_at": "done"}),
        ],
        agent_path="/root/fresh-worker",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"schema_version": 1, "runs": []}) + "\n", encoding="utf-8")

    dispatch = run_cli(
        tmp_path / "sessions",
        ledger,
        "dispatch",
        "--log", str(ledger),
        "--run-id", "fresh-run",
        "--agent-path", "/root/fresh-worker",
        "--task", "fresh bootstrap",
        "--model", "gpt-5.6-sol",
        "--effort", "high",
    )
    completion = run_cli(
        tmp_path / "sessions",
        ledger,
        "complete",
        "--log", str(ledger),
        "--run-id", "fresh-run",
        "--agent-path", "/root/fresh-worker",
        "--status", "complete",
        "--result", "worker finished",
    )

    assert dispatch["changed_rows"][0]["usage_status"] == "pending"
    run = json.loads(ledger.read_text(encoding="utf-8"))["runs"][0]
    assert run["thread_id"] == thread_id
    assert run["agent_path"] == "/root/fresh-worker"
    assert run["status"] == "complete"
    assert run["result"] == "worker finished"
    assert run["model"] == "gpt-5.6-sol"
    assert run["reasoning_effort"] == "high"
    assert run["usage_status"] == "available"
    assert run["request_count"] == 1
    assert run["delta"] == {"input_tokens": 12, "cached_input_tokens": 6, "output_tokens": 2}
    assert completion["totals"]["requests"] == 1


def test_reused_legacy_baseline_is_recovered_and_old_telemetry_is_preserved(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000004"
    old = usage(10, 4, 1)
    new = usage(20, 8, 2)
    write_session(
        tmp_path / "sessions",
        thread_id,
        [
            record(thread_id, "old-response", "2026-09-15T12:03:01.000Z", old, old),
            record(thread_id, "new-response", "2026-09-15T12:03:02.000Z", new, usage(30, 12, 3)),
            row("event_msg", "2026-09-15T12:03:03.000Z", {"type": "task_complete", "completed_at": "done"}),
        ],
    )
    old_delta = {"input_tokens": 19, "cached_input_tokens": 7, "output_tokens": 1}
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"runs": [{
        "run_id": "reused-run",
        "thread_id": thread_id,
        "status": "pending",
        "usage_status": "available",
        "usage_source": "event_msg.token_count",
        "start_boundary": "observed cumulative snapshot",
        "start_cumulative": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 1},
        "end_cumulative": {"input_tokens": 29, "cached_input_tokens": 11, "output_tokens": 2},
        "delta": old_delta,
    }]}), encoding="utf-8")

    run_cli(
        tmp_path / "sessions",
        ledger,
        "complete",
        "--log", str(ledger),
        "--run-id", "reused-run",
        "--thread-id", thread_id,
        "--status", "complete",
    )
    run = json.loads(ledger.read_text(encoding="utf-8"))["runs"][0]

    assert run["delta"] == {"input_tokens": 20, "cached_input_tokens": 8, "output_tokens": 2}
    assert run["request_count"] == 1
    assert run["usage_source"] == "session_jsonl.token_usage_record"
    assert run["usage_history"][0]["previous"]["usage_source"] == "event_msg.token_count"
    assert run["usage_reconciliation"]["corrected_delta"] == run["delta"]


def test_missing_final_record_is_provisional_until_task_complete_metadata_exists(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000005"
    values = usage(8, 2, 1)
    write_session(tmp_path / "sessions", thread_id, [record(thread_id, "response-1", "2026-09-15T12:04:01.000Z", values, values)])
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"runs": []}) + "\n", encoding="utf-8")

    run_cli(
        tmp_path / "sessions",
        ledger,
        "dispatch", "--log", str(ledger), "--run-id", "provisional-run", "--thread-id", thread_id,
    )
    run_cli(
        tmp_path / "sessions",
        ledger,
        "complete", "--log", str(ledger), "--run-id", "provisional-run", "--thread-id", thread_id,
    )
    run = json.loads(ledger.read_text(encoding="utf-8"))["runs"][0]

    assert run["usage_status"] == "provisional"
    assert run["delta"] == {"input_tokens": 8, "cached_input_tokens": 2, "output_tokens": 1}
    assert "no task_complete" in run["telemetry_reason"]


def test_legacy_token_count_remains_compatibility_evidence_but_is_unavailable_as_request_usage(tmp_path: Path) -> None:
    thread_id = "00000000-0000-4000-8000-000000000006"
    legacy = usage(50, 25, 4)
    write_session(tmp_path, thread_id, [row("event_msg", "2026-09-15T12:05:01.000Z", {
        "type": "token_count",
        "info": {"total_token_usage": legacy, "last_token_usage": legacy},
    })])

    snapshot = session_snapshot(thread_id, tmp_path)

    assert snapshot["request_count"] == 0
    assert snapshot["latest_cumulative"] == {"input_tokens": 50, "cached_input_tokens": 25, "output_tokens": 4}
    assert snapshot["zero_baseline_verified"] is True
