# Angelic Sorcerer: ordinary terminal admission

## Outcome

The selected level-1 Angelic Sorcerer is now available through the normal terminal command. The stable Sorcerer definition, item-capable Fighter ally and one curated first-cast encounter are admitted. Existing saved identifiers are retained. This completes the selected caster package, not every Sorcerer option.

From the project directory:

```sh
.venv/bin/python -m pf2e play sorcerer_angelic_first_cast --seed 13
```

## Delegated acceptance evidence

Luna owner `/root/scene_carry_recovery` reports changes to `src/pf2e/content.py`, `src/pf2e/sorcerer_content.py`, `src/pf2e/terminal.py` and `tests/test_angelic_admission.py`. The real `main(["play", ...])` smoke resolves initiative, casts two-action Heal, saves and loads the pending Blood Magic decision, resolves willingness and exits. Engine and terminal execution are retained in the test.

- Focused selection: **34 passed**.
- Existing integration command: `.venv/bin/python tools/integration_checkpoint.py`.
- Full suite: **690 passed in 3.34 seconds**; measured wrapper time **3.728 seconds**.
- Peak memory: **68,911,104 bytes / 65.719 MiB**. Compile and diff checks exited 0.
- Catalog: **50 admitted setups / 35 admitted creatures**, **7 staged setups / 1 staged creature**, save version **17**.
- All launched checks ran synchronously and exited. Host process enumeration was denied; no host-wide cleanup is claimed.

This follows Sol's accepted source-and-play review of the selected grants, spell repertoire, Halo, Blood Magic, Potency, Light, Refocus and daily preparation. The admission introduced no reported rule repair. Offensive Heal against undead and broader Sorcerer options remain unsupported.

## Accounting and next action

Run `angelic-cli-admission-2026-09-16`, session `01a0aa0e-81f6-7ca1-b2f5-9c94988dc370`, is closed. The deterministic collector reports Luna/xhigh, 53 requests including one compaction: **6,274,902 input tokens**, of which **6,085,376 were cached**, and **27,013 output tokens**. Dollar cost is unavailable. These are this assignment's counts, not the reused worker's cumulative session totals.

The selected Justice Champion is next. Its catalog overlap and broad-integration hold are released. Current ownership is recorded only in [ACTIVE](ACTIVE.md). The supervisor records worker evidence and has not independently inspected implementation or run checks.
