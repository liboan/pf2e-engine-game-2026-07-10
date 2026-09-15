# Working rules

## Direction and ownership

- Build a local Python PF2e engine with a simple terminal interface. Keep state literal and local; do not add browser, server, network, or distributed-state machinery.
- The supervisor assigns bounded slices, tracks progress, and integrates results. It does not read repository implementation or rules-source content. Its exception is authoring `docs/plan/*.md` and `docs/work-log/*`, and reading those files it wrote.
- Give each implementation slice one owner and clear file scope. The owner may make routine refactors inside that scope. Do not require a registry package, package approval, or a separate review for every change.
- Do not edit plan or work-log files unless you are the supervisor assigned to author them. Leave unrelated worktrees and branches alone.

## Model choice

- Use `gpt-5.6-luna` with `xhigh` reasoning for bounded implementation and debugging.
- Use `gpt-5.6-sol` with `high` reasoning less often for broader play, debugging, and critique. Once an engine exists, these reviews must run the actual Python engine and check applicable rules against sources.
- Use `gpt-6-astra` with `high` reasoning for high-level design, investigations, and extensive rules critique.
- When setting model overrides for subagents, use `fork_turns: "none"` or a positive number; do not use `"all"`.

## Correctness and evidence

- Implement applicable supported PF2e rules accurately. Defer costly bespoke content when it is not needed for the current playable slice. Cite the rules sources used. Do not silently approximate unsupported behavior; state the limit and stop where it affects play.
- Keep rules behavior in the engine, not in a growing set of one-off scenario exceptions.
- Use source-informed ordinary tests, then verify continuous local encounters, save/load, and performance as each capability becomes available. Do not claim evidence for a path that was not exercised.
- Keep durable run records in `docs/work-log/agent-runs.json`: record actual input, cached input, and output token metadata for each run. Cached input is a subset of input. If a value is unavailable, record `null` with the reason. Refresh final counters after completion and distinguish cumulative reused-agent counters from per-run counters.

## Test and process cadence

- During implementation, run the smallest relevant test selection for the changed rule, content family, or encounter. Keep cheap focused checks frequent; run complete scripted encounters after a coherent group of changes, and run the full suite plus broader end-to-end play at integration checkpoints and handoff.
- Keep checks serial and bounded: one pytest process by default, no `xdist`, watch loops, or background launches. Retain meaningful assertions and bounded output; a timeout or capture limit must fail with the case and last useful state.
- At integration checkpoints, when agents go idle or complete, and before handoff, audit their reported test and probe processes. Stop only confirmed unused task-owned descendants; verify process identity (PID, start time, command, and working directory when needed), request graceful exit, and confirm exit. Never kill by process name or stop a shared service with unclear ownership.

## Decisions and stopping

- Treat a P0 blocker as a stop condition and ask for clarification with the available structured question tool. Resolve P1 questions before making materially dependent decisions. Use judgment for routine, reversible choices.
- Stop and report the smallest decision needed when a source is unclear, a rule would have to be guessed, a check fails, or the slice would exceed its agreed scope. Keep the result and evidence reviewable before escalating.
