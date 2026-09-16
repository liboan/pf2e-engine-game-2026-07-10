# Investigator: execution pointers for the next owner

## Purpose and evidence limit

This is the historical read-only implementation handoff for the existing [Investigator contract](investigator-runtime-work.md). It is not a new design pass or accepted class delivery. Luna `/root/remaining_roster_handoff` identified these APIs and gaps before implementation. The first Investigator sequence is now under independent review and repair; use [its work record](investigator-first-play-work.md) and [ACTIVE](ACTIVE.md) for current behavior, ownership and acceptance counts. The table below describes the earlier handoff, not the current repository.

## Existing entry points and gaps

| Area | Existing entry points reported by the worker | Missing Investigator behavior |
|---|---|---|
| Definition and setup | `src/pf2e/content.py`: `get_definition`, `get_setup`; `src/pf2e/model.py`: `CreatureDefinition` | No Investigator definition, setup or staged resource in `content.py` or `expansion_catalog.py` |
| Saved rolls and action commitment | `model.py`: `FamilyProcedureContext.prepare_skill_check`, `resolve_saved_check`, `reroll_saved_check`, `commit_family_action`; `SavedCheckContext`; `encounter.py`: `_prepare_skill_check`, `_resolve_saved_check`, `_reroll_saved_check` | Devise a Stratagem state/consumption and Strategic Strike; do not assume generic saved checks already enforce all fortune restrictions |
| Precision damage analogues | `src/pf2e/ranger.py`, `src/pf2e/rogue.py` | Investigator-specific eligible weapon/attack and once-consumed roll rules |
| Skills | `src/pf2e/skill_actions.py` dispatch; `src/pf2e/skill_content.py` metadata; existing Encounter skill/stat/DC helpers | Recall Knowledge, Pursue a Lead, Clue In and Known Weaknesses |
| Healing and immunity | `src/pf2e/health.py`, Encounter healing application; `FamilyProcedureContext.grant_condition_immunity`, persisted `EncounterState.condition_immunities` | Battle Medicine DCs, healing, critical-failure damage and Forensic medic/recipient timing |
| Saved choices and reactions | `FamilyProcedureContext.present_choice`, `PendingChoice`, `ActionContinuation`; `family_martial.py`, Encounter `_family_handler_module`, persistence family validation | Clue In trigger and Investigator family routing/validation |
| Terminal | `src/pf2e/terminal.py`: action labels and `run_terminal` dispatch | Investigator action inputs and labels, preserving generic saved `Choose` handling |

## First bounded executable checkpoint

The worker recommends one selected Investigator setup and public Devise action, then a saved roll that survives save/load and is consumed by a following Strike. Start with actual public commands before adding the remaining selected features. The source packet still governs legality and exact rules; the handoff does not approve guesses or replace source checks.

Closest reported test analogues:

- `tests/test_skill_actions.py::test_public_trip_saved_hero_choice_round_trips_then_applies_damage_and_prone`
- `tests/test_skill_terminal.py::test_terminal_routes_all_four_skill_actions_and_resumes_saved_trip_choice`

Verified shared invocation: from the project directory, `.venv/bin/python -m pytest -q <focused files>`; pytest configuration supplies `src`. The existing integration command is `.venv/bin/python tools/integration_checkpoint.py`. Latest accepted engine baseline at handoff is 690 tests and save version 17. No Investigator public probe has been run.

The handoff's usage record is closed after correcting a late reused-worker registration with the prior completed assignment's exact cursor. The authoritative collector reports 34 requests including one compaction: 5,157,662 input tokens (4,936,192 cached), 14,273 output tokens. These are assignment totals, not the reused worker's cumulative session usage. The correction and its diagnostic cost are recorded in [ACTIVE](ACTIVE.md) and the ledger.
