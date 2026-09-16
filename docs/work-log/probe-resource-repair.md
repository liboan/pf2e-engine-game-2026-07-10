# Bounded probe repair after Justice integration

## Outcome

Three temporary probes continued running after the Justice owner reported no retained jobs. One captured enough terminal output to reach about 2.4 GB resident memory. The independent audit stopped all three and confirmed exit. The cause has been repaired in the shared test helpers, the obsolete probe scripts have been removed, and a second independent inventory found no remaining Python, pytest or Justice probe processes at approximately 07:39 PDT on September 16.

This incident concerned temporary testing programs. The accepted 710-test integration used about 66 MiB, and production terminal end-of-input handling was already correct. That small full-suite measurement did not establish the safety of separate ad hoc probes.

## Diagnosis and fix reported by the owner

- `/tmp/justice_probe.py` looped after its one-shot prayer decision was consumed.
- `/tmp/justice_victory_idx.py` looped after victory when there was no current actor.
- `/tmp/justice_cli_dynamic.py` had no input limit and retained every terminal output line.
- Production `_read_line()` converts exhausted scripted input to `EOFError`, and `run_terminal()` exits correctly. No production rule or EOF change was needed.

The owner added `BoundedInput` to `tests/terminal_test_helpers.py`, with finite input calls and last-output diagnostics. Existing `BoundedTranscript` overflow errors now identify the last emitted line. The Justice terminal smoke uses both, and `tests/test_justice_champion.py` includes a repeating-input-policy regression. Direct encounter probes use existing bounded command/round helpers or finite loops; this change does not introduce a separate testing framework.

The owner removed only the three obsolete temporary scripts and checked each was absent. Their useful encounter evidence remains in checked-in tests. Future temporary probes must use the same bounds; a yielded command session must be followed through actual exit rather than inferred complete from a later passing test.

## Executed evidence and cleanup

- Focused resource/terminal selection: **5 passed in 0.15 seconds**.
- Timeout-bounded measurement: **0.398 seconds**, **73,760,768 bytes / 70.344 MiB** peak; exit 0 under a 20-second subprocess timeout.
- Diff check passed. No retained session or child was reported from the bounded check.
- The initial audit terminated PIDs 37146, 40265 and 47621 and confirmed no rows on a subsequent PID query. Commands, exact project cwd and start times strongly matched the completed Justice work; no direct OS session IDs were available.
- The independent post-repair inventory found no remaining Python/pytest/Justice resource-check processes. Shared desktop MCP/Node services and active Investigator work were preserved. No additional termination was needed.

Broader integration is deferred to the coherent Investigator checkpoint because its shared engine work is active. Focused failure-path assertions and the independent exit check establish this bounded repair; they do not replace the pending integration of Investigator.

## Closed usage records

| Assignment | Input | Cached input (subset) | Output | Requests / compactions |
|---|---:|---:|---:|---|
| Initial post-Justice audit | 997,143 | 982,272 | 4,051 | 7 / 0 |
| Resource repair and obsolete-script cleanup | 3,674,680 | 3,569,408 | 20,100 | 29 / 1 |
| Independent post-repair exit check | 295,534 | 289,280 | 566 | 2 / 0 |

All three used Luna/xhigh. Counts come from the deterministic collector; dollar cost is unavailable. The original Justice delivery record retains a correction noting that its owner-reported process all-clear was contradicted by this audit. Root authored this record from delegated reports and did not inspect the scripts or run the tests.
