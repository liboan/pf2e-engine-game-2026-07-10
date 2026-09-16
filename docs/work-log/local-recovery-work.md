# Local recovery and the next encounter

## Decision and status

Keep the same Python `Encounter` handle between fights. Carry its existing character records into the next authored scene; do not create a second party model or a campaign simulator. Clock/deadlines, Refocus, the first same-party scene transition, declared rest and daily preparation are delivered. The sections below preserve the design and execution history; the final acceptance section records the latest preparation evidence. Optional Read Aura/Identify Magic remain deferred after a legal shared-Light preparation was selected for the Warpriest.

**Delivered first slice:** `python3 -m pytest tests/test_recovery_refocus.py -q` passes **four cases**, with **56 focused existing checks**. A healthy-start public Angelic fight spends focus through Halo, ends through real commands and Divine Lance, then Refocus advances 600 seconds, restores focus and survives save/load. At that checkpoint the same file verified atomic rejection for dim Assurance Trip; the subsequently delivered skill-targeting connection replaced that temporary guard and updated the test. The worker also reports **643 full-suite passes** and a clean diff, after repairing an overstrict save check that rejected legitimate self-Guidance. That broad run exceeded the assigned focused-only cadence; subsequent checks return to bounded selections. All test processes exited.

The public method is `refocus(actor_id)`. Strict saved encounter-start and world seconds support a literal outside-combat expiry helper; Guidance's cooldown starts at actual expiry, and combat source-turn anchors remain authoritative. Refocus rejects combat, pending choices and unresolved dying/unsupported unconscious state, restores one capped focus point and preserves HP/wounded, slots, daily uses and Light. At that first checkpoint there was no scene transition; the accepted transition is recorded below. Arbitrary time advance, rest/preparation and Read Aura remain absent.

Terminal validation now passes **29 checks in 0.12 seconds** across `tests/test_recovery_terminal.py` and `tests/test_terminal.py`. Post-combat non-S1 play offers Refocus, actor selection, Save/Load/Quit and a clear ten-minute focus-only result. The public completed Angelic fight continues through Refocus, save and load. An initial adapter error was repaired: `refocus` already returns `ActionResult`, so the terminal must not submit that result through `execute` again. Scoped diff checks pass, the test process exited and no future recovery placeholders were exposed.

Independent combined play now supplies stronger public recovery evidence: the real Sorcerer/Warpriest party takes injury, spends Heal and focus, attaches prepared Light and wins. Refocus moves time from **6 to 606**, restores focus and preserves exact HP, slots and Light; save/load matches. Guidance expires at **12**, so its immunity ends at **612**, not 1,206. The three-encounter review group passes **28 checks in 0.21 seconds**, with primary [Refocus](https://2e.aonprd.com/Actions.aspx?ID=2621), [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549) and [Light](https://2e.aonprd.com/Spells.aspx?ID=1585) rules checked. Scene carry was subsequently accepted below; preparation remains outstanding.

The first supported route keeps the same party identities and definitions in both scenes. It preserves injuries, equipment and resources, replaces opponents and positions, and rolls actual new initiative. Use the Refocus-first route: active turn-bound effects must have expired before transfer. Reject unsupported surviving effects explicitly; do not silently clear or rebase them. General party changes, loot transfer and direct transfer of active turn-bound effects are outside this initial route.

## Small public interface

Named methods or equivalent typed commands may expose:

```python
game.refocus(actor_id)
game.record_rested(actor_ids, day_number=..., elapsed_seconds=...)
game.daily_prepare(actor_ids)
game.next_encounter(next_setup)
```

Each uses the current result/inspection format and the same private-state/dice transaction as ordinary commands. Invalid requests leave both unchanged.

- **Refocus:** outside combat, a conscious eligible actor with an actual focus pool spends ten minutes and restores one point, capped at capacity. It does not restore slots, HP, equipment or daily uses. Sorcerers require no special deed. [Refocus](https://2e.aonprd.com/Actions.aspx?ID=2621), [bloodlines](https://2e.aonprd.com/Bloodlines.aspx).
- **Record rested:** explicitly declare eligibility from externally adjudicated rest and elapsed time. This is not a simulated sleep action and does not claim natural healing, armor/fatigue or condition recovery.
- **Daily preparation:** require that eligibility and no completed preparation on the current declared day. Advance one hour once for the selected group; refill actual prepared/spontaneous/focus resources and relevant daily uses, end their Lights and consume eligibility. Preserve fixed prepared choices until the alternate preparation is implemented. [Rest and preparation](https://2e.aonprd.com/Rules.aspx?ID=2440).
- **Next encounter:** after the current fight ends with no pending decision, transfer the literal party state into the next validated setup and run initiative.

## Authoritative facts

Existing creature records keep HP/health, Hero Points, casting resources, items/ammunition and class state. Add only the necessary preparation facts: rested eligibility and the last prepared day.

The encounter continues owning item instances, effects, immunities, pending decisions and elapsed seconds. Add an encounter-start timestamp and one declared preparation-day ordinal. The ordinal never decreases; advancing it invalidates old unused rest eligibility before marking the named actors rested. Initial fixtures start already prepared for their initial day.

The declared day controls once-per-day preparation. Elapsed seconds control durations. Do not also derive an independent day counter from seconds or reset resources merely because time advanced.

## Time and saved state

Replace the unconditional equality between world seconds and `(round - 1) * 6`:

- During combat, world seconds equal the encounter start plus `(round - 1) * 6`.
- Between fights, world seconds may be later than that value.
- A new fight begins at the current clock and round 1.

One small time-advance function handles the supported concrete effects; it does not simulate empty turns or dispatch through a new registry.

Required rules connections:

1. Convert Guidance immunity from encounter rounds to an absolute seconds deadline before rounds can reset.
2. Preserve absolute Demoralize, temporary-HP and later Sure Strike deadlines.
3. Keep exact actor-start/end anchors during combat and sufficient time information for expiry outside combat. Victory alone does not erase effects. A round wrap can reach an absolute deadline before a later-initiative caster’s turn: the source-turn anchor remains authoritative in combat. Use elapsed expiry when explicitly advancing time outside combat, not as an earlier competing combat timer.
4. An expired effect starts a resulting cooldown at its actual expiration, not at the end of a long time jump. Otherwise Refocus incorrectly lengthens Guidance immunity.
5. Expire turn-bound defenses and reduce ordinary frightened when time passes; do not erase persistent wounded.
6. Light survives until preparation. Attached orbs can follow carried actors. Reject unsupported scene-object transfer rather than silently deleting or recreating it.

The Halo slice should store its elapsed-time deadline alongside its combat boundary before this work begins.

## Atomic scene transition

Require the same PC actor IDs and definitions, at least one combat-capable carried PC, distinct new opponent identities, and fully accounted-for party gear. All changes happen in one draft:

1. Carry whole character records and existing item instances, including shield HP, runes and investment.
2. Replace scene placements/labels/teams and instantiate new opponents only.
3. Reset encounter-local initiative, actions/reactions, attack/diagonal counters and per-round movement facts centrally.
4. Preserve HP, wounds, resources, Hero Points, ammunition, daily facts, applicable absolute immunities and attached Light. Reject unsupported remaining turn-bound spell/item/condition/Feint/raised-shield state before transfer. Refocus expires the current short-lived effects.
5. Preserve monotonic choice identity; use the existing cloned dice provider for new initiative.
6. Validate the new scene and commit once. Missing supplied dice or an invalid setup leaves the old scene intact.

Require party gear to be carried before departure in the first route. Never rebuild a dropped or damaged shield from the new setup's initial loadout. If post-combat retrieval is exposed, reuse the existing item-location procedure through a small actor-explicit Interact operation.

Keep persistence's exact actor/item validation. It should validate carried values against definitions without resetting those values to their initial state.

## Concrete first transition packet

Astra inspected the delivered clock and current lifecycle. This first route needs **no new party or timing fields**. Add `next_encounter(next_setup)` alongside Refocus, with one helper reusing `start`'s creature/item construction for new opponents. Carry whole PC records; replace only authored label/team/position and encounter-local counters. Preserve monotonic choice and orb IDs.

Before the transaction, reject active combat/pending choices, unresolved dying or living unconscious state, mismatched PC identities/definitions, reused opponent IDs, unaccounted ground gear, party equipment held by departing actors, imported opponent loot, and unsupported surviving turn-bound effects. Every retained Light must have a retained caster and retained attached carrier; point or departing-actor attachments need an explicit supported disposition before transfer.

On a cloned state/dice draft, reset initiative metadata, round to one, actions/reactions, attack/diagonal and per-round markers, movement obligations and actor start/end counters. Clear departed Hunted Prey references. Set encounter start to unchanged world time. Keep Guidance's absolute deadline and valid lasting immunities; reject an immunity requiring unsupported departed-source state and discard records concerning only departed targets. Draw real initiative in placement order and reuse `_continue_initiative_initialization`, including genuine paused initiative choices.

Validate the candidate state and pending choice before committing once. `save_encounter` only serializes; reuse the existing `_state_to_data`/`_state_from_data` validation through a small helper. Invalid setup/state or `DiceSourceError` must preserve both old state and old dice.

**Required nonzero-clock repair:** Halo, Flee and Runic Weapon callers of `_valid_active_duration_deadline` currently omit `encounter_start_seconds` and `in_progress`. Supply them, as Guidance already does. Otherwise a real Halo cast in scene B cannot reload. This is necessary even when all old turn-bound effects expired before departure.

Use current `ANGELIC_FIRST_CAST_SETUP` as scene A. Add only staged `ANGELIC_NEXT_ENCOUNTER_SETUP`, ID `sorcerer_angelic_next_encounter`, bright 7×5: `angelic_sorcerer` / `sorcerer_angelic_level_1_staged` at (1,1), `sorcerer_ally` / `fighter_m_weapon_identity_staged` at (2,1), and new `sorcerer_dog_b` / `guard_dog_mc2924` at (5,1). Register in `_STAGED_SETUPS`; no new creature definition is needed. Existing Fear fixtures do not preserve this exact party.

Proposed complete sequence: adapt the real Halo fight, cast Light with the remaining two actions after Halo and attach it to the Fighter, then finish the fight. The existing sequence ends with Sorcerer HP 16/focus 0/slots 2 and Fighter HP 19. Refocus, save/load and enter B on the same handle using real initiative; verify resources, weapon identity and attached Light. Cast Halo and finish B through a critical Divine Lance, then reload the completed second fight with its new active Halo at nonzero time. Proposed additional rolls are `(20, 1, 1, 20, 4, 4)`; the implementing owner must verify them through actual public play. Separate focused cases cover damaged shields, ammunition, runes/investment, wounded and changed Hero Points, which this two-PC scene does not all demonstrate.

If later admitted content requires direct active-effect transfer, preserve remaining source-turn occurrences as well as elapsed deadlines. Deriving occurrences from remaining seconds alone can delay an effect by a new-scene turn. That reasoning is retained for future work; no speculative timing-origin fields are required for this guarded first route.

## Health and unsupported transitions

Acting creatures must be alive, conscious and able to perform the selected recovery activity. No transition heals, wakes or revives a character. Pending spell/reaction/Hero/resource decisions block recovery and scene changes.

Reject the whole long time jump when a retained actor has unresolved dying checks or unsupported unconscious recovery. This first route does not pretend those health procedures happened offscreen. Refocus leaves wounded unchanged. Rest eligibility declares only preparation eligibility, with the rest-simulation limitation visible in the interface.

Later Desperate Prayer needs its own daily-use fact and temporary devotion-only point. The point expires at that turn's end; it cannot enlarge permanent focus capacity or survive into another scene. Refocus does not reset daily Prayer; eligible preparation does. [Desperate Prayer](https://2e.aonprd.com/Feats.aspx?ID=5884).

## Delivery order and evidence

These are implementation checkpoints, not required worker handoffs. For the next scene-carry assignment, one Luna owner completes the actual fight → Refocus → save/load → second fight sequence, required atomic rejection cases and representative terminal use across all necessary files. Keep that owner for ordinary Sol review repairs. Reuse the concrete packet above; no new planning pass is needed.

1. Clock/deadline persistence, without resource reset.
2. Real public Refocus and saved spent-focus restoration.
3. Two authored scenes carrying the same party atomically.
4. Rest declaration and daily preparation.

Use five families of public tests:

- Finish a healthy-start fight with real injuries, a spent slot/focus, used ammunition and damaged equipment; Refocus, save/load and enter scene B with exact carried values.
- Refocus restores one focus but leaves depleted slots depleted; an unavailable slot cast rejects atomically.
- Active Halo/Blood Magic/Guidance expire correctly across Refocus, with the correct remaining immunity in the second scene.
- Saved rest eligibility permits one preparation; repeated same-day or unqualified preparation rejects without changes.
- Pending decisions, mismatched party identity, unaccounted gear, unresolved health and exhausted initiative dice each leave state/dice unchanged.

Scene-carry and Refocus cases now have accepted evidence below. Preparation cases remain proposals. No new P0/P1 decision remained after selecting the explicit-rest boundary.

## Current complete-outcome assignment

Scene carry was dispatched at **2026-09-16 11:36:15 UTC** to the existing clock/Refocus Luna owner. One assignment owns the complete two-fight path, necessary terminal integration, strict saved state and rejection checks, and ordinary review repairs. No new research or separate persistence/terminal handoff is required. This is the second working-model comparison; record first executable check, actual dependency waits, owner changes, review repairs, total delivery interval and measured usage here after acceptance.

Verified execution environment: canonical project cwd, `.venv/bin/python -m pytest -q <focused files>`; project pytest configuration supplies `src` on the Python path. Public analogues: `_finished_spent_focus_game()` and `test_refocus_advances_clock_restores_focus_and_round_trips_save()` in `tests/test_recovery_refocus.py`, plus `test_injury_spent_resources_prepared_light_refocus_and_save_load()` in `tests/test_caster_recovery_play_review.py`. Latest full integration is **668 passed / 64.609 MiB**, via `.venv/bin/python tools/integration_checkpoint.py`. Reuse that command at acceptance; focused checks do not require a global test window.

### Resume interruption

Desktop resume interrupted the original scene-carry owner before a public checkpoint reached the supervisor. The app confirmed its latest turn interrupted/not loaded; native collaboration no longer had that worker. A recovery Luna owner now continues the existing edits and the same acceptance outcome. This is **one forced owner change**, not an ordinary review handoff or a checkpoint timeout. Root did not inspect implementation.

The interrupted implementation run records **8,416,601 input / 8,211,456 cached input / 35,376 output tokens**, 52 requests and one compaction. Preserve it in total delivery accounting. The interrupted process audit records provisional **114,307 / 81,152 / 1,327 tokens** and no completed attribution or cleanup claim; a resumed scoped audit is active. First scene-carry executable-check time remains unavailable until recovered evidence establishes it.

The resumed process audit completed one bounded inventory: no active Python/pytest/game probe or attributable leftover. Node/Playwright commands belonged to shared ChatGPT MCP infrastructure; parent PID 1 alone did not establish project ownership. Zero terminations; active implementation was preserved.

### First recovered public checkpoint

By **11:56:10 UTC**, the recovery owner reports a complete public sequence: fight A creates injury, a depleted spell slot and attached Light; Refocus advances 600 seconds and creates Guidance's correct 612-second immunity deadline; save/load preserves state; scene B starts at 606 with fresh initiative and ends through Halo and Divine Lance. This is an observed checkpoint bound, not an invented exact first-check timestamp. The owner is checking atomic failure edges and integration; terminal and changed-equipment coverage still need its final report. Sol independent review is now released because the required public API and probe work.

The recovery owner's **intermediate 670-test integration** passed, followed by two contract fixes: explicitly validate retained PC definition identity, and instantiate new opponents' real equipment while retaining existing PC item instances. This count is not final acceptance of those later edits. The owner finishes terminal and atomic/save checks; Sol supplies one independent public pair with actually damaged shield, spent ammunition/Hero Point and newly acquired wounded state, avoiding duplicate complete play scripts.

### Independent review repair in progress

The changed-equipment encounter exposed a real P1 before transfer: actual knockout and subsequent two-action Warpriest Heal produce HP 16/wounded 1, but a stale `initiative_reordered` marker causes reload to reject the conscious PC. `tests/test_scene_carry_review.py` reproduces this through public commands (initial selection: 1 failed, 1 passed). The same Luna owner repairs the saved-state invariant while preserving correct initiative placement. Carry assertions remain pending that repair. Healing does not automatically clear prone; reviewer and owner distinguish that correct rule from test-order mistakes.

## Accepted scene carry and working-model comparison — second outcome

**Completed 2026-09-16 12:11:20 UTC.** The same public Encounter now continues into a validated next scene. It carries literal PC records/items and attached Light, refreshes encounter-local turns/initiative and creates new opponents with their own equipment. Supported invalid transfers and exhausted supplied initiative dice preserve both prior state and dice. The terminal exposes the staged next encounter. Daily preparation and ordinary CLI admission of the staged Sorcerer are separate remaining work.

Independent `tests/test_scene_carry_review.py` retains three source-checked public cases:

- `test_changed_shield_ammo_hero_and_wounded_carry_through_saved_two_fight_play`: healthy start, shield HP **20→18**, arrows **20→19→18**, Hero **1→0** through a saved reroll, knockout and two-action Heal to **HP16/wounded1**, correct retained prone, actual later Stand/retrieval, spent Heal, identical shield item, new turn counters and a second victory.
- `test_exhausted_next_initiative_and_invalid_party_transfer_preserve_state_and_dice`: exact atomic rejection, including supplied dice exhaustion.
- `test_nonzero_clock_halo_runic_and_flee_deadlines_round_trip`: actual casts after Refocus/scene transfer, Halo/Runic deadlines **660**, Flee **612**, then exact save/load.

The P1 repair is in `persistence.py::_state_from_data`: allow a recovered PC's valid `initiative_reordered` marker, preserving its knockout-driven initiative placement; non-PC markers still reject. Healing retains prone, and the test reaches the actor's real turn before Stand. No rule was weakened to clear the test.

Verification: independent **3 passed in 0.13s**; owner+review **5 passed in 0.12s**; combined carry/Refocus/terminal/recovery **25 passed**. Final `.venv/bin/python tools/integration_checkpoint.py`: **674 passed**, reported pytest runtime **3.362s**, peak **66,945,024 bytes / 63.844 MiB**. Compile/diff/catalog passed: 48 accepted setups/32 creatures, 8 staged setups/3 creatures, save version17. No benchmark was emitted; retain the prior benchmark separately. Synchronous integration/tests exited. Reviewer jobs list was empty; final OS inventory was restricted. The recent independent host audit found no attributable leftovers and performed zero terminations.

Sources checked by Sol: [Refocus](https://2e.aonprd.com/Actions.aspx?ID=2621), [Light](https://2e.aonprd.com/Spells.aspx?ID=1585), [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549), [durations](https://2e.aonprd.com/Rules.aspx?ID=2221), [Halo](https://2e.aonprd.com/Spells.aspx?ID=2093), [Runic](https://2e.aonprd.com/Spells.aspx?ID=1658), [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524), [wounded](https://2e.aonprd.com/Conditions.aspx?ID=99), and [shield/item rules](https://2e.aonprd.com/Rules.aspx?ID=181). Diagnostic fixtures do not add class coverage.

Delivery interval **35m05s**, from original dispatch 11:36:15 to final handoff12:11:20 UTC. First recovered public result was observed by11:56:10; exact first executable-check timestamp is unavailable. **One forced owner change** followed desktop interruption; ordinary review repairs stayed with the recovery owner. **One review repair**; no explicit dependency wait was imposed. Interruption/recovery overhead is included in total elapsed time, with no unsupported separate duration estimate.

| Attributed run | Input tokens | Cached input (subset) | Output tokens |
|---|---:|---:|---:|
| Interrupted initial scene implementation | 8,416,601 | 8,211,456 | 35,376 |
| Recovery implementation, terminal, repair and final integration | 14,314,535 | 13,924,864 | 52,834 |
| Independent Sol play/source review | 5,970,340 | 5,767,040 | 26,281 |
| Interrupted process audit (provisional telemetry) | 114,307 | 81,152 | 1,327 |
| Completed resumed process audit | 91,489 | 75,264 | 884 |
| Observed total of these runs | 28,907,272 | 28,059,776 | 116,702 |

The total includes provisional audit telemetry and excludes earlier foundational design/clock work, which remains separately accounted in the ledger. Monetary cost is unavailable. This outcome and the Runic outcome differ in scope and include an interruption, so they do not establish a controlled efficiency comparison.

## Daily preparation accepted

The Luna owner reports completion at **2026-09-16 12:35:57 UTC**. Public `Encounter.record_rested(...)` and `Encounter.daily_prepare(...)` now persist strict declared-day, eligibility and last-prepared facts. The terminal distinguishes declaring completed rest from spending the preparation hour. These are worker-reported implementation and verification results; the supervisor did not inspect or execute the implementation.

Exact focused command: `.venv/bin/python -m pytest -q tests/test_daily_preparation.py`. Its four cases are:

- `test_record_rested_save_load_prepares_and_casts_restored_resources_in_next_scene`
- `test_downtime_rejections_preserve_state_and_dice`
- `test_daily_preparation_save_validation_rejects_inexact_declared_facts`
- `test_terminal_distinguishes_declared_rest_from_daily_preparation`

The strengthened public sequence actually spends restored Halo focus **1→0**, restored spontaneous Heal capacity **3→2**, and the Warpriest's restored `ordinary_heal_1` slot, then defeats the next scene's dog. This closes the earlier cantrip-only evidence gap. Group preparation advances **3,600 seconds once**. Separate partial preparation removes only the selected caster's Light and preserves the other caster's orb. HP, wounded, equipment and ammunition remain unchanged. Invalid day/group/state/dice requests and inexact saved preparation facts have explicit rejection coverage.

Final existing integration command: **678 passed in 3.34s**, peak **67,649,536 bytes / 64.516 MiB**, compile/diff checks pass, save version **17**. All synchronous commands exited 0; no background jobs started. OS process census was unavailable because sandboxed `ps` was blocked. The earlier scoped audit remains separately recorded rather than presented as a new inventory.

Sources used from the existing packets: [Rest and preparation](https://2e.aonprd.com/Rules.aspx?ID=2440), [Cleric](https://2e.aonprd.com/Classes.aspx?ID=33), [Light](https://2e.aonprd.com/Spells.aspx?ID=1585) and [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285). The explicit limits remain: caller-adjudicated rest eligibility, no sleep/natural-healing/fatigue simulation, no deriving a competing day from elapsed seconds, and fixed prepared choices. Read Aura remains deferred.

One owner completed this outcome, including the stronger public evidence and final handoff. Recorded run usage: **18,186,667 input / 17,828,352 cached input / 67,025 output tokens**, 130 requests and one compaction. Cached input is a subset of input; monetary cost is unavailable. The next broader independent caster review will group this with Sure Strike and admission checks. Sure Strike is a genuinely new assignment with its own usage boundary; no new class is claimed solely from this recovery feature.

## Preparation assignment history

The same Luna now owns a genuinely new assignment for `record_rested` and `daily_prepare`, through actual restored-resource use, saves, terminal and ordinary fixes. There is no public preparation probe yet. Follow the existing contract above: declared external rest eligibility, monotonic explicit day, once-per-day preparation, one group hour, actual slot/focus/daily-resource restoration, only preparing casters' Lights ending, HP/wounded/equipment preserved. Source ambiguity must be surfaced; do not silently add a sleep/natural-healing simulation. Current assignment identity remains only in ACTIVE.

Daily-preparation diagnosis checkpoint: after adding its saved-state schema, `test_refocus_advances_clock_restores_focus_and_round_trips_save` passes (1 case). This is compatibility evidence, not a claim that the new public preparation path works. Public operations and their saved/terminal/atomic cases remain the current implementation work; the owner and run are unchanged.

First public preparation checkpoint: `tests/test_daily_preparation.py::test_record_rested_save_load_prepares_and_casts_restored_resources_in_next_scene` passes (1 case, 0.12s). The owner reports a real mixed-caster fight, spent prepared/spontaneous/focus resources, two Light orbs, saved day-2 eligibility, separate caster preparation, resource/HP/wounded/orb checks and entry to a new scene. **Evidence gap identified by supervision:** its reported final Divine Lance is a cantrip, so it does not prove expenditure of a restored slot or focus. The same owner must extend actual resource-consuming casts and separately verify that a multi-actor preparation costs one group hour. Terminal and atomic day/group/dice cases remain unfinished. The reported exact timestamp was unavailable and is not recorded as a real time.
