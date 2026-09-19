# Selected Maestro Bard completion

## Graceful pause checkpoint — September 18

The user paused development. Owner and reviewer have completed; no follow-ups or new workers are authorized until explicit resumption. The execution heartbeat is PAUSED. The remaining sections retain the contract for recovery and are not permission to continue during the pause.

Source-settled implementation is completed and independently reviewed: corrected legal sheet/cantrips/Fear, actual held rapier and Assurance, spontaneous Shield casting plus Shield/Ward saved provenance. Owner: **96 focused tests / 0.47 seconds**, targeted compilation passed. Independent command: `.venv/bin/python -m pytest -q tests/test_bard_lingering_composition_review.py` → **17 passed / 0.23 seconds**, covering real reactions/saves, resources, terminal, persistence and healthy victory/rest/daily preparation. No canonical suite followed this group; the earlier 1,205-test checkpoint predates these changes.

Final verification gap: owner reports removing duplicate `Versatile Human` from feats, retaining heritage; reviewer did not inspect or rerun after that categorization edit. Check this narrowly after resumption. Counter Performance remains entirely held on the two user decisions; Bard stays partial. No class admission is inferred from adding its focus-spell grant.

Reviewer’s final process audit found no pytest, timeout, integration-checkpoint or worktree process. Owner’s own `ps` attempt was sandbox-denied; that denial is not cleanup proof. No new shutdown test or repair round was launched.

Closed actual usage (input / cached subset / output): owner **9,122,962 / 8,886,016 / 23,964** (58 requests, 0 compactions); reviewer **10,473,908 / 10,215,680 / 27,629** (68 requests, 1 compaction). With the source handoff: **21,128,284 / 20,341,120 / 59,863**, 138 requests, 2 compactions, 3 assignments. Dollars unavailable. Future resumed assignments require new accounting boundaries. See [ACTIVE](ACTIVE.md) for pause status and all remaining work.

## Scope and pending decisions

Complete the selected level1 Maestro after accepted Anthem, Lingering and Soothe, preserving the finite legal build and existing class evidence. Root accepted Astra’s source/current-seam handoff at September18 22:16UTC. Fourteen other classes are fully accepted; Bard and Monk remain partial. This handoff is not a new general design pass.

Two previously surfaced Counter Performance decisions remain unanswered: whether a substituted Performance total retains the ally’s original natural1/20 adjustment (recommended) versus independently resolved own-die candidates; and whether each beneficiary chooses Counter Performance or its own Hero reroll before extra dice, with Bard-owned Hero reroll available on the separate Performance check (recommended). Do not implement dependent substitution/fortune choices before a recorded user answer. No new user ruling is needed for the source-settled legal sheet, selected cantrip replacements or printed Fear traits.

Monk’s separate horizontal-only admission versus High Jump question remains pending. This Bard owner does not edit Monk or add vertical terrain.

## Assigned workers and usage

Fresh owner `/root/bard_completion_owner`, session `01a0b699-e9ff-75f2-adc7-1d43ef116905`, verified Terra/high, run `bard-completion-implementation-2026-09-18`. Fresh reviewer `/root/bard_completion_review`, session `01a0b69a-3319-7781-872e-2521803a35b9`, requested Sol/high, run `bard-completion-review-2026-09-18`. Both identities are registered and their assignments are closed with final usage in the pause checkpoint above. Sol verified actual native Terra/high in feedback/run-turn records for owner turn `01a0b699-ea92-7152-9880-127b3fa227e3` and directly released the source-settled group. Counter-dependent behavior remains held for user answers. Owner’s first inventory check preceded reviewer creation; root supplied the now-live identity, resolving that launch-order question.

Astra handoff run closed: **1,531,414 input /1,239,424 cached /8,270 output**,12requests,1compaction, actual Astra/high. No edits or retained processes; three ready prerequisites passed0.15seconds. Ordinary future checkpoints/fixes remain inside the respective new owner/review runs, with no per-test accounting resets.

## First independent executable group: legal selected sheet and spells

Astra found these concrete corrections in `src/pf2e/bard_content.py::MAESTRO_BARD_STAGED`:

- Perception+5 and Will+5, correcting current+6/+4.
- Versatile Human/Fleet, Natural Skill Society/Medicine, required Farmhand Athletics/Farming Lore/Assurance Athletics. Keep existing attributes; Athletics+4, Medicine+3, Speed30, ordinary vision, Hero1, actually held rapier. Source-check all applicable sheet quantities and actual grant behavior.
- Five ordinary cantrips: Light, Guidance, Void Warp, Forbidding Ward, Shield. Replace unavailable Read Aura and illegal occult Stabilize (divine/primal). All proposed replacements already execute in the engine; no new spell family.
- Anthem stays separate. Fear/Runic Weapon plus muse Soothe are three repertoire entries sharing two rank1 daily slots. Counter Performance grant contributes focus capacity2 but does not imply implemented behavior. Daily preparation restores spontaneous resources without a prepared-spell selector.
- Correct `spells.py::SPELLS["fear"]`: remove erroneous auditory, add printed manipulate. Fear cannot trigger Counter Performance. Verify actual relevant cast/reaction/save paths; do not merely change an inventory assertion.

One Terra owner handles runtime/content/save/terminal/tests for this selected public outcome; it retains future approved Counter Performance implementation and ordinary fixes. Keep old saved definition IDs. Required legal sheet/ordinary casting/Assurance/held rapier and saved terminal proof can proceed while the two adjudications wait. Do not admit the full Bard or run a full suite yet.

## Counter Performance after the user answers

Use existing Witch **Command** as the real auditory trigger; no Dizzying Colors implementation is needed. A Common-speaking ally targeted by an opposing Flamekeeper supplies an actual Will save and commanded consequences. Fear is ineligible; speech used while casting does not add auditory to the spell.

`Encounter._apply_spell` Command currently rolls and immediately applies consequences. Add the smallest saved reaction/fortune choices before consequences (including Command’s reaction suppression). Reuse `_set_pending`, `_choose`, `_hero_reroll_check`, `model.ActionContinuation/PendingChoice`, strict persistence serialization/validation and `terminal.render_pending_choice`. Counter Performance requires matching Performance type, reaction and focus,60foot eligibility; use singing. An existing Anthem must end when the new composition is cast. Track the actual current turn for the composition limit: existing `composition_cast_at_start` keys the Bard’s own starts and is insufficient for off-turn compositions. Do not build a generic reaction/fortune framework.

First dependent checkpoint after approval: Command→Counter offer→saved/reloaded choice→agreed Performance calculation→Command consequences exactly once. Independent review should cover decline, exhausted reaction/focus, range, Fear rejection, natural1/20 under the chosen convention, fortune ownership and Anthem replacement. Then complete healthy victory→Refocus→daily preparation→save/load→next encounter with retained PC identity→new actual action and terminal play, followed by normal catalog admission and a root-authorized canonical run.

## Source packet and executable pointers

Astra source references: [Command](https://2e.aonprd.com/Spells.aspx?ID=1470), [Stabilize](https://2e.aonprd.com/Spells.aspx?ID=1689), [Ward](https://2e.aonprd.com/Spells.aspx?ID=1535), [Shield](https://2e.aonprd.com/Spells.aspx?ID=1671), [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524), [Counter Performance](https://2e.aonprd.com/Spells.aspx?ID=1762), [composition](https://2e.aonprd.com/Traits.aspx?ID=559). Existing detailed source/accepted partial evidence and numeric decision examples: [Bard first-play work](bard-first-play-work.md). Root only summarizes findings; workers check sources/implementation.

Analogues: `tests/test_soothe_play_review.py`, Witch’s healthy-victory saved/terminal route. Source worker ran the current Command, Lingering and Monk reaction prerequisites: **3 passed /0.15seconds**:

- `tests/test_witch_flamekeeper.py::test_command_uses_common_speaking_target_will_save`
- `tests/test_bard_lingering_composition_review.py::test_resolved_extended_anthem_survives_save_with_exact_expiry`
- `tests/test_monk_mobility_review.py::test_saved_accepted_missed_reactive_strike_resumes_quick_jump`

No Counter Performance probe exists yet. Counter behavior stays held by the two unanswered choices.

## Environment and working model

Exact cwd `/Users/andrewlee/.codex/worktrees/45673ef6-8f9a-40a9-a1c9-e699d44667ca/pf2e-engine-game-2026-07-10`; `.venv/bin/python`3.11.1, pytest supplies src; standalone `PYTHONPATH=src`. Focused command `/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q <selection>`. Last full checkpoint1,205 /5.93seconds, peak81,739,776bytes, compile/diff clean;60admitted setups/46creatures,staged25/12,save17.

Terra/high implementation must have actual native adoption verified by the retained/new Sol reviewer before engine edits. Positive verification directly releases source-settled work without waiting for root; mismatch/unavailable stops without fallback/config changes. Review source-settled public groups as soon as ready, route ordinary repairs directly to the same owner. Root handles durable docs and per-run usage; workers do not edit plan/work-log files. No commits, browser work, broad suite without root authorization, xdist/watch/background tests. One synchronous bounded focused test per worker; exact attributable process audit at final handoff, never name-wide kills. Preserve existing health/persistent limits and all accepted classes.
