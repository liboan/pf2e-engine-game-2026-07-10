#!/usr/bin/env python3
"""Record metadata-only usage for identified local Codex sessions.

The authoritative source is the session JSONL's per-request
``token_usage_record`` metadata. Records are deduplicated by response ID,
inherited records before this session's own ``session_meta`` are excluded,
and compaction requests are retained. No transcript or tool output is read
into the returned data.

``dispatch`` (also available as ``register``) creates a run row and captures
the pre-dispatch cursor. Use ``--mode fresh`` for a newly spawned session or
``--mode reused`` immediately before a follow-up in an existing session.
``complete`` sums records after that cursor. ``backfill`` remains compatible
with the original full-session operation.
"""

import argparse
import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")
OPTIONAL_FIELDS = ("cache_write_input_tokens",)
ALL_FIELDS = FIELDS + OPTIONAL_FIELDS
COLLECTOR_VERSION = 2
USAGE_SOURCE = "session_jsonl.token_usage_record"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)


class LogError(Exception):
    """A user-correctable usage collection or ledger error."""


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_meta(payload):
    """Keep identity/configuration metadata while excluding transcript text."""
    allowed = {
        "id", "session_id", "parent_thread_id", "agent_path", "cwd", "timestamp",
        "model_provider", "thread_source", "originator", "cli_version", "history_mode",
        "multi_agent_version",
    }
    result = {}
    for key in allowed:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
    source = payload.get("source")
    if isinstance(source, (str, int, float, bool)) or source is None:
        result["source"] = source
    elif isinstance(source, dict):
        # source is routing metadata, not conversation content. Preserve only
        # its scalar leaves so an agent prompt cannot escape through output.
        result["source"] = {
            key: value for key, value in source.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
    context = payload.get("context_window")
    if isinstance(context, dict) and isinstance(context.get("window_id"), str):
        result["context_window_id"] = context["window_id"]
    return result


def _json_rows(path):
    try:
        stream = path.open(encoding="utf-8")
    except OSError as exc:
        raise LogError(f"cannot read session JSONL: {exc}") from exc
    with stream:
        for ordinal, line in enumerate(stream):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield ordinal, row


def _metadata_from_first(path):
    for _ordinal, row in _json_rows(path):
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            return row["payload"]
    return None


def _session_candidates(sessions_root):
    root = Path(sessions_root)
    if not root.exists():
        raise LogError(f"sessions root does not exist: {root}")
    return sorted(root.rglob("rollout-*.jsonl"))


def locate_session(thread_id=None, sessions_root=None, *, agent_path=None, session_id=None):
    """Locate one JSONL by identity metadata, with filename lookup as a fast path."""
    if sessions_root is None:
        sessions_root = (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions")
    if thread_id is not None and not UUID.fullmatch(thread_id):
        raise LogError("thread id must be a UUID")
    if session_id is not None and not UUID.fullmatch(session_id):
        raise LogError("session id must be a UUID")
    if thread_id is None and session_id is None and not agent_path:
        raise LogError("provide --thread-id, --session-id, or --agent-path")
    root = Path(sessions_root)
    candidates = []
    if thread_id:
        candidates.extend(root.glob(f"*/*/*/rollout-*-{thread_id}.jsonl"))
    if not candidates:
        candidates = _session_candidates(root)
    matches = []
    for path in candidates:
        meta = _metadata_from_first(path)
        if not meta:
            continue
        own_id = meta.get("id") or meta.get("thread_id")
        # session_meta.id is the local thread/session identity in current logs.
        # session_id is accepted as an explicit alias for callers which only
        # retained that identity.
        if thread_id and own_id != thread_id:
            continue
        if session_id and own_id != session_id and meta.get("session_id") != session_id:
            continue
        if agent_path and meta.get("agent_path") != agent_path:
            continue
        matches.append(path)
    if len(matches) != 1:
        if not matches:
            raise LogError("no session JSONL matched the requested session metadata")
        raise LogError("expected exactly one session JSONL for the requested metadata")
    return matches[0]


def _token_values(source):
    if not isinstance(source, dict):
        return None
    values = {}
    for key in FIELDS:
        value = source.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values[key] = value
    for key in OPTIONAL_FIELDS:
        value = source.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values[key] = value
    if values["cached_input_tokens"] > values["input_tokens"]:
        raise LogError("cached input exceeds input in source telemetry")
    return values


def _sum_usage(records):
    total = {key: 0 for key in ALL_FIELDS}
    for record in records:
        usage = record["usage"]
        for key in ALL_FIELDS:
            total[key] += usage.get(key, 0)
    return total


def _public_usage(values):
    if not isinstance(values, dict):
        return None
    return {key: values.get(key, 0) for key in FIELDS}


def _record_key(payload, stamp):
    response_id = payload.get("response_id")
    if isinstance(response_id, str) and response_id:
        return ("response_id", response_id)
    # A response ID is canonical. For malformed older records, retain a
    # deterministic fallback so an exact raw duplicate is not counted twice.
    usage = payload.get("usage")
    return ("fallback", stamp, payload.get("turn_id"), json.dumps(usage, sort_keys=True, separators=(",", ":")))


def _normalize_record(payload, stamp, *, compaction=False):
    if not isinstance(payload, dict):
        return None
    usage = _token_values(payload.get("usage"))
    if usage is None:
        return None
    response_id = payload.get("response_id")
    return {
        "response_id": response_id if isinstance(response_id, str) else None,
        "root_turn_id": payload.get("root_turn_id") if isinstance(payload.get("root_turn_id"), str) else None,
        "session_id": payload.get("session_id") if isinstance(payload.get("session_id"), str) else None,
        "thread_id": payload.get("thread_id") if isinstance(payload.get("thread_id"), str) else None,
        "turn_id": payload.get("turn_id") if isinstance(payload.get("turn_id"), str) else None,
        "timestamp": stamp,
        "usage": usage,
        "thread_token_usage": _public_usage(payload.get("thread_token_usage")),
        "compaction": bool(compaction),
    }


def _cursor(snapshot):
    requests = snapshot.get("requests", [])
    return {
        "boundary": snapshot.get("session_started_at"),
        "request_count": len(requests),
        "response_ids": [r["response_id"] for r in requests if r.get("response_id")],
        "latest_response_id": requests[-1].get("response_id") if requests else None,
        "latest_token_count_at": snapshot.get("latest_token_count_at"),
    }


def session_snapshot(thread_id=None, sessions_root=None, *, agent_path=None, session_id=None):
    """Read one identified session's metadata and per-request usage only."""
    if sessions_root is None:
        sessions_root = (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions")
    path = locate_session(thread_id, sessions_root, agent_path=agent_path, session_id=session_id)

    own_meta = None
    own_ordinal = None
    rows = list(_json_rows(path))
    for ordinal, row in rows:
        if row.get("type") != "session_meta" or not isinstance(row.get("payload"), dict):
            continue
        payload = row["payload"]
        own_id = payload.get("id") or payload.get("thread_id")
        if thread_id and own_id == thread_id:
            own_meta, own_ordinal = payload, ordinal
            break
        if not thread_id and session_id and (own_id == session_id or payload.get("session_id") == session_id):
            own_meta, own_ordinal = payload, ordinal
            break
        if not thread_id and not session_id and agent_path and payload.get("agent_path") == agent_path:
            if own_meta is not None:
                raise LogError("agent path matched more than one session metadata record")
            own_meta, own_ordinal = payload, ordinal
    if own_meta is None:
        raise LogError("requested session JSONL has no matching session_meta")

    # Collect compaction IDs in the local suffix first, then classify matching
    # per-request records regardless of whether the compacted marker follows.
    suffix = [(ordinal, row) for ordinal, row in rows if ordinal > own_ordinal]
    compaction_ids = set()
    for _ordinal, row in suffix:
        if row.get("type") == "compacted" and isinstance(row.get("payload"), dict):
            value = row["payload"].get("compaction_response_id")
            if isinstance(value, str) and value:
                compaction_ids.add(value)

    requests = []
    seen = {}
    duplicate_count = 0
    invalid_count = 0
    completion_at = None
    configs = []
    config_by_turn = {}
    cumulative_first = None
    cumulative_last = None
    latest_at = None
    first_last = None
    legacy_first = None
    legacy_last = None
    legacy_first_last = None
    legacy_latest_at = None

    def add_record(payload, stamp, *, is_compaction=False):
        nonlocal duplicate_count, invalid_count, cumulative_first, cumulative_last, latest_at, first_last
        if not isinstance(payload, dict):
            invalid_count += 1
            return
        key = _record_key(payload, stamp)
        record = _normalize_record(payload, stamp, compaction=is_compaction)
        if record is None:
            invalid_count += 1
            return
        if key in seen:
            duplicate_count += 1
            old = seen[key]
            if old["usage"] != record["usage"]:
                raise LogError(f"duplicate response id has conflicting usage: {key[-1]}")
            old["compaction"] = old["compaction"] or record["compaction"]
            return
        seen[key] = record
        requests.append(record)
        if record.get("thread_token_usage"):
            if cumulative_first is None:
                cumulative_first = record["thread_token_usage"]
                first_last = _public_usage(record["usage"])
            cumulative_last = record["thread_token_usage"]
            latest_at = stamp

    for _ordinal, row in suffix:
        stamp = row.get("timestamp")
        if not isinstance(stamp, str):
            stamp = None
        kind, payload = row.get("type"), row.get("payload")
        if kind == "turn_context" and isinstance(payload, dict):
            model = payload.get("model")
            effort = payload.get("effort") or payload.get("reasoning_effort")
            settings = payload.get("collaboration_mode", {}).get("settings") if isinstance(payload.get("collaboration_mode"), dict) else None
            if not isinstance(model, str) and isinstance(settings, dict) and isinstance(settings.get("model"), str):
                model = settings["model"]
            if isinstance(model, str) or isinstance(effort, str):
                config = {
                    "model": model if isinstance(model, str) else None,
                    "reasoning_effort": effort if isinstance(effort, str) else None,
                    "turn_id": payload.get("turn_id") if isinstance(payload.get("turn_id"), str) else None,
                    "timestamp": stamp,
                }
                if not configs or config != configs[-1]:
                    configs.append(config)
                if config.get("turn_id"):
                    config_by_turn[config["turn_id"]] = config
        elif kind == "token_usage_record":
            if isinstance(payload, dict):
                response_id = payload.get("response_id")
                record_thread_id = payload.get("thread_id")
                record_session_id = payload.get("session_id")
                local_id = own_meta.get("id") or own_meta.get("thread_id")
                # Older records may omit thread_id. In that case, a session_id
                # belonging to the parent still identifies an inherited record
                # and must not be charged to the local session.
                if record_thread_id not in (None, local_id, thread_id) or (
                    record_thread_id is None
                    and record_session_id not in (None, local_id)
                ):
                    # A parent or sibling record cannot become part of this
                    # run even if a malformed log places it after session_meta.
                    continue
                add_record(payload, stamp, is_compaction=response_id in compaction_ids)
        elif kind == "compacted" and isinstance(payload, dict):
            latest = payload.get("latest_token_usage_record")
            compaction_id = payload.get("compaction_response_id")
            # Current logs have a separate token_usage_record. This fallback
            # handles older/fixture logs that retained only the nested latest
            # record, without reading its summary/message fields.
            if isinstance(latest, dict):
                candidate = latest.get("payload") if isinstance(latest.get("payload"), dict) else latest
                if isinstance(candidate, dict):
                    if compaction_id and "response_id" not in candidate:
                        candidate = dict(candidate)
                        candidate["response_id"] = compaction_id
                    key = _record_key(candidate, stamp)
                    if key not in seen:
                        add_record(candidate, stamp, is_compaction=True)
        elif kind == "event_msg" and isinstance(payload, dict):
            if payload.get("type") == "task_complete":
                completion_at = stamp or payload.get("completed_at")
            elif payload.get("type") == "token_count" and isinstance(payload.get("info"), dict):
                # Compatibility evidence only. The collector never uses this
                # source for request totals, because it omits compactions.
                legacy = _token_values(payload["info"].get("total_token_usage"))
                legacy_last_usage = _token_values(payload["info"].get("last_token_usage"))
                if legacy is not None:
                    if legacy_first is None:
                        legacy_first = legacy
                        legacy_first_last = _public_usage(legacy_last_usage)
                    legacy_last = legacy
                    legacy_latest_at = stamp

    for record in requests:
        config = config_by_turn.get(record.get("turn_id"))
        if config:
            record["model"] = config.get("model")
            record["reasoning_effort"] = config.get("reasoning_effort")

    meta = _safe_meta(own_meta)
    own_id = own_meta.get("id") or own_meta.get("thread_id") or thread_id or session_id
    parent_id = own_meta.get("parent_thread_id")
    if parent_id is None and isinstance(own_meta.get("session_id"), str) and own_meta.get("session_id") != own_id:
        parent_id = own_meta.get("session_id")
    if cumulative_first is None:
        cumulative_first = _public_usage(legacy_first)
        first_last = legacy_first_last
    if cumulative_last is None:
        cumulative_last = _public_usage(legacy_last)
        latest_at = legacy_latest_at
    zero_verified = bool(cumulative_first and first_last and cumulative_first == first_last)
    totals = _sum_usage(requests)
    return {
        "thread_id": own_id,
        "session_id": own_id,
        "source_session_id": own_meta.get("session_id"),
        "parent_thread_id": parent_id,
        "agent_path": own_meta.get("agent_path"),
        "session_metadata": meta,
        "session_file": path.name,
        "session_path": str(path),
        "session_started_at": own_meta.get("timestamp"),
        "configs": configs,
        "first_cumulative": cumulative_first,
        "first_last_usage": first_last,
        "zero_baseline_verified": zero_verified,
        "latest_cumulative": cumulative_last,
        "latest_token_count_at": latest_at,
        "requests": requests,
        "request_usage_totals": totals,
        "request_count": len(requests),
        "duplicate_request_count": duplicate_count,
        "invalid_request_count": invalid_count,
        "compaction_request_count": sum(1 for r in requests if r.get("compaction")),
        "final_seen": completion_at is not None,
        "session_completed_at": completion_at,
        "source": USAGE_SOURCE,
        "source_version": COLLECTOR_VERSION,
        "usage_source": USAGE_SOURCE,
        "usage_source_version": COLLECTOR_VERSION,
        "cursor": _cursor({"session_started_at": own_meta.get("timestamp"), "requests": requests,
                            "latest_token_count_at": latest_at}),
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


def find_run(data, run_id, thread_id=None):
    found = [row for row in data["runs"] if row.get("run_id") == run_id]
    if len(found) != 1:
        raise LogError("expected one existing ledger row matching run_id")
    if thread_id is not None and found[0].get("thread_id") not in (None, thread_id):
        raise LogError("ledger run identity does not match requested thread id")
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
    unique = list(dict.fromkeys(c.get("model") for c in configs if c.get("model")))
    efforts = list(dict.fromkeys(c.get("reasoning_effort") for c in configs if c.get("reasoning_effort")))
    # A dispatch may be registered before a worker emits its first
    # turn_context. Keep the requested values in that provisional case.
    if unique:
        run["model"] = unique[0] if len(unique) == 1 else None
    else:
        run.setdefault("model", None)
    if efforts:
        run["reasoning_effort"] = efforts[0] if len(efforts) == 1 else None
    else:
        run.setdefault("reasoning_effort", None)
    run["observed_configs"] = configs
    if len(unique) > 1 or len(efforts) > 1:
        run["configuration_note"] = "multiple configurations observed; see observed_configs"
    else:
        run.pop("configuration_note", None)


def _prior_telemetry(run):
    keys = ("usage_source", "usage_source_version", "start_cumulative", "end_cumulative", "delta",
            "usage_status", "telemetry_reason", "request_count", "compaction_request_count")
    prior = {key: copy.deepcopy(run[key]) for key in keys if key in run}
    # A pending row has no historical measurement to preserve.
    if not prior or all(prior.get(key) is None for key in ("end_cumulative", "delta")):
        return None
    return prior


def _record_reconciliation(run, prior, corrected):
    if prior is None:
        return
    before = {key: prior.get(key) for key in ("end_cumulative", "delta", "usage_status", "request_count")}
    after = {key: corrected.get(key) for key in ("end_cumulative", "delta", "usage_status", "request_count")}
    if before == after and prior.get("usage_source") == USAGE_SOURCE:
        return
    evidence = {
        "recorded_at": timestamp(),
        "previous": prior,
        "corrected": corrected,
        "method": "per-request records deduplicated after session_meta boundary",
    }
    history = run.setdefault("usage_history", [])
    if not history or history[-1] != evidence:
        history.append(evidence)
    run["usage_reconciliation"] = {
        "previous_end_cumulative": before.get("end_cumulative"),
        "corrected_end_cumulative": after.get("end_cumulative"),
        "previous_delta": before.get("delta"),
        "corrected_delta": after.get("delta"),
        "source": USAGE_SOURCE,
        "source_version": COLLECTOR_VERSION,
    }


def _apply_identity(run, snap):
    run["thread_id"] = snap["thread_id"]
    run["session_id"] = snap.get("session_id")
    run["source_session_id"] = snap.get("source_session_id")
    run["parent_thread_id"] = snap.get("parent_thread_id")
    run["agent_path"] = snap.get("agent_path")
    run["session_file"] = snap["session_file"]
    run["session_started_at"] = snap["session_started_at"]


def _start_run(run, snap, *, fresh):
    if fresh:
        run["start_cumulative"] = {key: 0 for key in FIELDS}
        run["start_boundary"] = "session_meta local boundary (fresh session)"
    else:
        run["start_cumulative"] = _public_usage(snap.get("latest_cumulative"))
        run["start_boundary"] = "pre-follow-up request cursor (reused session)"
    run["run_started_at"] = timestamp()
    run["usage_status"] = "pending"
    run["end_cumulative"] = None
    run["delta"] = None
    run["telemetry_reason"] = "run has started; no completion usage recorded"
    run["dispatch_boundary"] = "session_meta" if fresh else "pre-follow-up request cursor"
    run["_usage_cursor"] = {"mode": "fresh" if fresh else "reused", **snap["cursor"]}
    run["_configs_at_start"] = snap.get("configs", [])


def _records_after(snap, run):
    records = snap.get("requests", [])
    cursor = run.get("_usage_cursor")
    if not isinstance(cursor, dict):
        # Rows created by the old collector do not have a request cursor. For a
        # reused row, its cumulative baseline identifies the last request seen
        # by the old begin operation. Recover that boundary from the direct
        # records before falling back to a full-session measurement.
        start = _public_usage(run.get("start_cumulative"))
        if start and run.get("start_boundary") == "observed cumulative snapshot":
            for index, record in enumerate(records):
                if record.get("thread_token_usage") == start:
                    return records[index + 1:], "recovered cumulative baseline cursor"
            # A malformed or truncated record should not be attributed to a
            # reused run. Keep the usage unavailable rather than silently
            # charging the full lifetime session.
            return [], "legacy cumulative baseline not found"
        # A complete/backfill operation can still expose the direct full-
        # session measurement, while preserving the prior interval in
        # usage_history.
        return records, "full-session legacy fallback"
    if cursor.get("mode") == "fresh":
        return records, "session_meta local boundary"
    count = cursor.get("request_count")
    if isinstance(count, int) and 0 <= count <= len(records):
        return records[count:], "pre-follow-up request cursor"
    # A cursor's response IDs are an additional recovery path if a log gained
    # malformed records between begin and complete.
    ids = set(cursor.get("response_ids", []))
    index = 0
    while index < len(records) and records[index].get("response_id") in ids:
        index += 1
    return records[index:], "response-id follow-up cursor"


def _finish_run(run, snap, *, command, status=None, result=None):
    prior = _prior_telemetry(run)
    records, boundary = _records_after(snap, run)
    totals = _sum_usage(records)
    end = _public_usage(snap.get("latest_cumulative"))
    run["end_cumulative"] = end
    run["latest_token_count_at"] = snap.get("latest_token_count_at")
    run["completion_boundary"] = boundary
    run["completion_turn_id"] = records[-1].get("turn_id") if records else None
    run["request_count"] = len(records)
    run["duplicate_request_count"] = snap.get("duplicate_request_count", 0)
    run["invalid_request_count"] = snap.get("invalid_request_count", 0)
    run["compaction_request_count"] = sum(1 for record in records if record.get("compaction"))
    run["request_usage"] = totals
    run["delta"] = _public_usage(totals) if records else None
    if records:
        run["usage_status"] = "available" if snap.get("final_seen") else "provisional"
        run["telemetry_reason"] = None if snap.get("final_seen") else "usage records observed, but no task_complete metadata"
    else:
        run["usage_status"] = "unavailable"
        run["telemetry_reason"] = "no per-request token_usage_record observed after run boundary"
    run["usage_source"] = USAGE_SOURCE
    run["usage_source_version"] = COLLECTOR_VERSION
    run["source_session_metadata"] = snap.get("session_metadata")
    run["session_completed_at"] = snap.get("session_completed_at")
    if status is not None:
        run["status"] = status
    if result is not None:
        run["result"] = result
    interval_configs = []
    for record in records:
        config = {key: record.get(key) for key in ("model", "reasoning_effort", "turn_id", "timestamp")}
        if config.get("model") or config.get("reasoning_effort"):
            if not interval_configs or config_key(config) != config_key(interval_configs[-1]):
                interval_configs.append(config)
    if not interval_configs:
        starts = {config_key(old) for old in run.get("_configs_at_start", [])}
        interval_configs = [c for c in snap.get("configs", []) if config_key(c) not in starts]
    attach_config(run, interval_configs or snap.get("configs", [])[-1:])
    _record_reconciliation(run, prior, {
        "end_cumulative": run.get("end_cumulative"),
        "delta": run.get("delta"),
        "usage_status": run.get("usage_status"),
        "request_count": run.get("request_count"),
    })
    run.pop("_usage_cursor", None)
    run.pop("_configs_at_start", None)
    if command == "complete":
        run["run_completed_at"] = timestamp()
    else:
        run["telemetry_collected_at"] = timestamp()


def _compact_row(run):
    return {key: run.get(key) for key in (
        "run_id", "thread_id", "status", "model", "reasoning_effort", "usage_status",
        "request_count", "compaction_request_count", "delta", "result",
    )}


def operate(args):
    sessions_root = args.sessions_root
    thread_id = getattr(args, "thread_id", None)
    session_id = getattr(args, "session_id", None)
    agent_path = getattr(args, "agent_path", None)
    snap = session_snapshot(thread_id, sessions_root, agent_path=agent_path, session_id=session_id)
    if args.command == "snapshot":
        print(json.dumps(snap, indent=2, sort_keys=True))
        return
    data = load_ledger(args.log)
    run_id = getattr(args, "run_id", None)
    try:
        run = find_run(data, run_id, snap["thread_id"])
    except LogError:
        # A worker can finish spawning before the supervisor writes its row.
        # dispatch/register is the one operation allowed to bootstrap that
        # row; completion and legacy commands still require an existing row.
        existing = [row for row in data["runs"] if row.get("run_id") == run_id]
        if args.command not in ("dispatch", "register") or existing:
            raise
        run = {"run_id": run_id, "status": "pending"}
        data["runs"].append(run)
    prior_identity = _prior_telemetry(run)
    _apply_identity(run, snap)

    if args.command in ("dispatch", "register"):
        mode = args.mode
        if args.fresh:
            mode = "fresh"
        if args.reused:
            mode = "reused"
        _start_run(run, snap, fresh=mode == "fresh")
        run["dispatch_mode"] = mode
        run["dispatched_at"] = timestamp()
        for field, value in (("task", args.task), ("role", args.role),
                             ("requested_model", args.model), ("requested_reasoning_effort", args.effort)):
            if value is not None:
                run[field] = value
        if args.status is not None:
            run["status"] = args.status
        if args.result is not None:
            run["result"] = args.result
        run["usage_source"] = USAGE_SOURCE
        run["usage_source_version"] = COLLECTOR_VERSION
        run["source_session_metadata"] = snap.get("session_metadata")
        run["telemetry_reason"] = "run dispatched; completion usage not yet recorded"
        # Keep the previous direct telemetry if a legacy row is being reused;
        # this dispatch itself has not corrected it yet.
        if prior_identity and "usage_history" not in run:
            run["pre_dispatch_telemetry"] = prior_identity
    elif args.command == "begin":
        _start_run(run, snap, fresh=args.fresh_session)
    else:
        _finish_run(run, snap, command=args.command, status=getattr(args, "status", None),
                    result=getattr(args, "result", None))

    save_ledger(args.log, data)
    print(json.dumps({
        "changed_rows": [_compact_row(run)],
        "source": {"name": USAGE_SOURCE, "version": COLLECTOR_VERSION},
        "totals": {"input_tokens": (run.get("request_usage") or {}).get("input_tokens", 0),
                   "cached_input_tokens": (run.get("request_usage") or {}).get("cached_input_tokens", 0),
                   "output_tokens": (run.get("request_usage") or {}).get("output_tokens", 0),
                   "requests": run.get("request_count", 0),
                   "compactions": run.get("compaction_request_count", 0)},
    }, indent=2, sort_keys=True))


def milestone(args):
    data = load_ledger(args.log)
    selected = set(args.run_id or [])
    known = {row.get("run_id") for row in data["runs"]}
    missing = sorted(selected - known)
    if missing:
        raise LogError(f"milestone run id not found: {', '.join(missing)}")
    rows = [row for row in data["runs"] if not selected or row.get("run_id") in selected]
    totals = {key: 0 for key in FIELDS}
    request_count = compactions = 0
    for row in rows:
        values = row.get("request_usage") or row.get("delta")
        if isinstance(values, dict):
            for key in FIELDS:
                value = values.get(key)
                if isinstance(value, int) and value >= 0:
                    totals[key] += value
        request_count += row.get("request_count", 0) if isinstance(row.get("request_count"), int) else 0
        compactions += row.get("compaction_request_count", 0) if isinstance(row.get("compaction_request_count"), int) else 0
    print(json.dumps({
        "totals": {**totals, "requests": request_count, "compactions": compactions, "runs": len(rows)},
        "changed_rows": [_compact_row(row) for row in rows if selected],
    }, indent=2, sort_keys=True))


def self_test():
    tid = "00000000-0000-4000-8000-000000000001"
    def line(kind, stamp, payload):
        return json.dumps({"type": kind, "timestamp": stamp, "payload": payload})
    usage = {"input_tokens": 120, "cached_input_tokens": 80, "output_tokens": 7, "cache_write_input_tokens": 0}
    record = {"response_id": "resp-1", "thread_id": tid, "session_id": tid,
              "root_turn_id": "turn-root", "turn_id": "turn-1", "usage": usage,
              "thread_token_usage": usage}
    fixture = [
        line("token_usage_record", "before", {**record, "response_id": "parent-record", "thread_id": "parent"}),
        line("session_meta", "t0", {"id": tid, "session_id": tid, "parent_thread_id": "root",
                                      "agent_path": "/root/example"}),
        line("turn_context", "t1", {"model": "test", "effort": "high", "turn_id": "turn-1"}),
        line("token_usage_record", "t2", record),
        line("token_usage_record", "t2", record),
        line("compacted", "t3", {"compaction_response_id": "resp-2"}),
        line("token_usage_record", "t3", {**record, "response_id": "resp-2", "usage": usage,
                                             "thread_token_usage": {"input_tokens": 240, "cached_input_tokens": 160,
                                                                     "output_tokens": 14, "cache_write_input_tokens": 0}}),
        line("event_msg", "t4", {"type": "task_complete", "completed_at": "t4"}),
        json.dumps({"type": "user_message", "text": "transcript must not escape"}),
    ]
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp) / "2026" / "09" / "15"
        folder.mkdir(parents=True)
        path = folder / f"rollout-test-{tid}.jsonl"
        path.write_text("\n".join(fixture) + "\n", encoding="utf-8")
        snap = session_snapshot(tid, temp)
    assert snap["request_count"] == 2 and snap["duplicate_request_count"] == 1
    assert snap["compaction_request_count"] == 1 and snap["final_seen"]
    assert snap["request_usage_totals"]["input_tokens"] == 240
    assert snap["configs"] == [{"model": "test", "reasoning_effort": "high", "turn_id": "turn-1", "timestamp": "t1"}]
    assert "transcript must not escape" not in json.dumps(snap)
    print("self-test passed")


def _add_identity(command):
    command.add_argument("--thread-id", "--thread", dest="thread_id")
    command.add_argument("--session-id", "--session", dest="session_id")
    command.add_argument("--agent-path", "--agent", dest="agent_path")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default=str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"))
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("dispatch", "register"):
        command = commands.add_parser(name, help="register a fresh or reused worker run")
        command.add_argument("--log", required=True)
        command.add_argument("--run-id", required=True)
        _add_identity(command)
        command.add_argument("--mode", choices=("fresh", "reused"), default="fresh")
        command.add_argument("--fresh", action="store_true")
        command.add_argument("--reused", action="store_true")
        command.add_argument("--task", "--task-name", dest="task")
        command.add_argument("--role")
        command.add_argument("--model", "--requested-model", dest="model")
        command.add_argument("--effort", "--requested-effort", "--requested-reasoning-effort", dest="effort")
        command.add_argument("--status")
        command.add_argument("--result")

    for name in ("begin", "complete", "backfill"):
        command = commands.add_parser(name)
        command.add_argument("--log", required=True)
        command.add_argument("--run-id", required=True)
        _add_identity(command)
        if name == "begin":
            command.add_argument("--fresh-session", action="store_true")
        else:
            command.add_argument("--status")
            command.add_argument("--result")

    snap = commands.add_parser("snapshot")
    _add_identity(snap)
    commands.add_parser("self-test")
    total = commands.add_parser("milestone", aliases=["totals", "summary"])
    total.add_argument("--log", required=True)
    total.add_argument("--run-id", action="append")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            self_test()
        elif args.command in ("milestone", "totals", "summary"):
            milestone(args)
        else:
            operate(args)
        return 0
    except (LogError, OSError) as exc:
        print(f"usage log error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
