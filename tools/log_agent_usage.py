#!/usr/bin/env python3
"""Record token usage from one requested Codex session, without transcripts.

Reads only session_meta, turn_context, and event_msg/token_count fields. Cached
input is included in input_tokens; do not add cached_input_tokens again.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


class LogError(Exception):
    pass


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def session_snapshot(thread_id, sessions_root):
    if not UUID.fullmatch(thread_id):
        raise LogError("thread id must be a UUID")
    paths = list(Path(sessions_root).glob(f"*/*/*/rollout-*-{thread_id}.jsonl"))
    if len(paths) != 1:
        raise LogError("expected exactly one session JSONL for the requested thread id")

    started = parent_id = None
    configs, first_total, first_last, latest, latest_at = [], None, None, None, None
    with paths[0].open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            kind, stamp, payload = row.get("type"), row.get("timestamp"), row.get("payload")
            if not isinstance(payload, dict):
                continue
            if kind == "session_meta" and payload.get("id") == thread_id:
                started, parent_id = stamp, payload.get("parent_thread_id")
                continue
            # Forked session logs can contain the parent's metadata. Count only
            # events timestamped after this child's own session_meta boundary.
            if started is None or not isinstance(stamp, str) or not isinstance(started, str) or stamp <= started:
                continue
            if kind == "turn_context":
                model, effort = payload.get("model"), payload.get("effort")
                if isinstance(model, str) or isinstance(effort, str):
                    config = {"model": model if isinstance(model, str) else None,
                              "reasoning_effort": effort if isinstance(effort, str) else None,
                              "turn_id": payload.get("turn_id") if isinstance(payload.get("turn_id"), str) else None,
                              "timestamp": stamp}
                    if not configs or config != configs[-1]:
                        configs.append(config)
            elif kind == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info")
                if not isinstance(info, dict):
                    continue
                total = info.get("total_token_usage")
                last = info.get("last_token_usage")
                def usage(source):
                    if not isinstance(source, dict):
                        return None
                    values = {key: source.get(key) for key in FIELDS}
                    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values.values()):
                        return None
                    if values["cached_input_tokens"] > values["input_tokens"]:
                        raise LogError("cached input exceeds input in source telemetry")
                    return values
                total, last = usage(total), usage(last)
                if total is None:
                    continue
                if first_total is None:
                    first_total, first_last = total, last
                latest, latest_at = total, stamp

    if started is None:
        raise LogError("requested session JSONL has no matching session_meta")
    zero_verified = bool(first_total and first_last and first_total == first_last)
    return {
        "thread_id": thread_id,
        "parent_thread_id": parent_id,
        "session_file": paths[0].name,
        "session_started_at": started,
        "configs": configs,
        "first_cumulative": first_total,
        "first_last_usage": first_last,
        "zero_baseline_verified": zero_verified,
        "latest_cumulative": latest,
        "latest_token_count_at": latest_at,
    }


def load_ledger(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LogError(f"cannot read ledger: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise LogError("ledger must contain a runs array")
    return data


def save_ledger(path, data):
    path = Path(path)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            tmp = stream.name
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise LogError(f"cannot write ledger: {exc}") from exc


def find_run(data, run_id, thread_id):
    found = [row for row in data["runs"] if row.get("run_id") == run_id]
    if len(found) != 1 or found[0].get("thread_id") != thread_id:
        raise LogError("expected one existing ledger row matching run_id and thread_id")
    return found[0]


def delta(start, end):
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None, "start or end cumulative usage is unavailable"
    values = {key: end[key] - start[key] for key in FIELDS}
    if any(value < 0 for value in values.values()):
        return None, "cumulative usage regressed"
    if values["cached_input_tokens"] > values["input_tokens"]:
        return None, "cached input delta exceeds input delta"
    return values, None


def config_key(config):
    return tuple(config.get(key) for key in ("model", "reasoning_effort", "turn_id", "timestamp"))


def attach_config(run, configs):
    unique = list({c.get("model") for c in configs if c.get("model")})
    efforts = list({c.get("reasoning_effort") for c in configs if c.get("reasoning_effort")})
    run["model"] = unique[0] if len(unique) == 1 else None
    run["reasoning_effort"] = efforts[0] if len(efforts) == 1 else None
    run["observed_configs"] = configs
    if len(unique) > 1 or len(efforts) > 1:
        run["configuration_note"] = "multiple configurations observed; see observed_configs"
    else:
        run.pop("configuration_note", None)


def operate(args):
    snap = session_snapshot(args.thread_id, args.sessions_root)
    if args.command == "snapshot":
        print(json.dumps(snap, indent=2, sort_keys=True))
        return
    data = load_ledger(args.log)
    run = find_run(data, args.run_id, args.thread_id)
    run["parent_thread_id"] = snap["parent_thread_id"]
    run["session_file"] = snap["session_file"]
    run["session_started_at"] = snap["session_started_at"]

    if args.command == "begin":
        # Existing task/request/result fields are preserved; only telemetry fields change.
        if args.fresh_session:
            run["start_cumulative"] = {key: 0 for key in FIELDS}
            run["start_boundary"] = "caller asserted new one-run session"
        else:
            run["start_cumulative"] = snap["latest_cumulative"]
            run["start_boundary"] = "observed cumulative snapshot"
        run["run_started_at"] = timestamp()
        run["usage_status"] = "pending"
        run["end_cumulative"] = None
        run["delta"] = None
        run["telemetry_reason"] = "run has started; no completion usage recorded"
        run["_configs_at_start"] = snap["configs"]
    else:
        start = run.get("start_cumulative")
        if start is None and snap["zero_baseline_verified"]:
            start = {key: 0 for key in FIELDS}
            run["start_cumulative"] = start
            run["start_boundary"] = "first post-session total equals last usage"
        run["end_cumulative"] = snap["latest_cumulative"]
        run["latest_token_count_at"] = snap["latest_token_count_at"]
        run["boundary_evidence"] = (
            "first post-session total equals last usage; zero baseline verified"
            if snap["zero_baseline_verified"] else
            "zero baseline not established; delta left null unless begin snapshot exists"
        )
        values = [c for c in snap["configs"] if config_key(c) not in {
            config_key(old) for old in run.pop("_configs_at_start", [])
        }]
        attach_config(run, values or snap["configs"][-1:])
        run["delta"], reason = delta(start, snap["latest_cumulative"])
        run["usage_status"] = "available" if snap["latest_cumulative"] else "unavailable"
        run["telemetry_reason"] = reason or (None if snap["latest_cumulative"] else "no token_count event recorded")
        if args.command == "complete":
            run["run_completed_at"] = timestamp()
        else:
            run["telemetry_collected_at"] = timestamp()
        if not snap["latest_cumulative"]:
            run["delta"] = None
        # Keep the human-authored task status untouched; usage_status is separate.

    save_ledger(args.log, data)
    print(json.dumps({key: run.get(key) for key in (
        "run_id", "thread_id", "status", "model", "reasoning_effort", "start_cumulative",
        "end_cumulative", "delta", "usage_status", "start_boundary", "boundary_evidence",
    )}, indent=2, sort_keys=True))


def self_test():
    tid = "00000000-0000-4000-8000-000000000001"
    def line(kind, stamp, payload):
        return json.dumps({"type": kind, "timestamp": stamp, "payload": payload})
    counts = {"input_tokens": 120, "cached_input_tokens": 80, "output_tokens": 7}
    fixture = [
        line("event_msg", "before", {"type": "token_count", "info": {"total_token_usage": counts, "last_token_usage": counts}}),
        line("session_meta", "t0", {"id": tid, "parent_thread_id": "root"}),
        line("session_meta", "t0", {"id": "parent-thread", "parent_thread_id": None}),
        line("turn_context", "t0", {"model": "inherited-model", "effort": "ultra", "turn_id": "old"}),
        line("turn_context", "t1", {"model": "test", "effort": "high", "turn_id": "turn"}),
        line("event_msg", "t2", {"type": "token_count", "info": {"total_token_usage": counts, "last_token_usage": counts}}),
        json.dumps({"type": "user_message", "text": "transcript must not escape"}),
    ]
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp) / "2026" / "09" / "15"
        folder.mkdir(parents=True)
        (folder / f"rollout-test-{tid}.jsonl").write_text("\n".join(fixture) + "\n", encoding="utf-8")
        snap = session_snapshot(tid, temp)
    assert snap["zero_baseline_verified"] and snap["latest_cumulative"] == counts
    assert snap["configs"] == [{"model": "test", "reasoning_effort": "high", "turn_id": "turn", "timestamp": "t1"}]
    assert "transcript must not escape" not in json.dumps(snap)
    assert delta({"input_tokens": 20, "cached_input_tokens": 10, "output_tokens": 2}, snap["latest_cumulative"]) == (
        {"input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 5}, None)
    print("self-test passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default=str((Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))) / "sessions"))
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("begin", "complete", "backfill"):
        command = commands.add_parser(name)
        command.add_argument("--log", required=True)
        command.add_argument("--thread-id", required=True)
        command.add_argument("--run-id", required=True)
        if name == "begin":
            command.add_argument("--fresh-session", action="store_true")
    snap = commands.add_parser("snapshot")
    snap.add_argument("--thread-id", required=True)
    commands.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            self_test()
        else:
            operate(args)
        return 0
    except (LogError, OSError) as exc:
        print(f"usage log error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
