# Completed Feint and casting handoff

Archived after the accepted 415-test checkpoint and final focused Feint victory check. This retains the original integration contract; its remaining-work language describes the historical handoff, not current outstanding work. See [current delivery state](../class-expansion-state.md) for active ownership.

## Summary

The Feint/casting core checkpoint now passes 415 tests in 1.04 seconds at about 53.6 MiB peak child memory. Seven public Feint cases verify scope, duration, maneuvers, saved attack defenses and Escape preserving the opening. The actual terminal route passes. Sol subsequently completed one Feint route to victory, and its focused test passed. All Feint ownership is released; shared core ownership has transferred to typed damage integration.

The following connection details are retained as implemented handoff context. The [damage and equipment work](damage-equipment-handoff.md) is the next active shared slice, alongside a separate Dragon Barbarian family owner.

These are part of the level-1 S3i pass. They do not complete Rogue, Druid or other new classes. See [current delivery state](../class-expansion-state.md) for accepted evidence and pending decisions.

## Ownership and order

1. The Bear checkpoint is accepted: 406 tests, two completed routes on one combat setup, a separate saved health/initiative fixture and two real terminal paths.
2. `expansion_typed_damage_runtime` now owns shared files; the Feint finisher has released all files. `expansion_dragon_runtime` owns Barbarian family files and coordinates one catalog edit with the shared owner. Family procedure files are at completed owner checkpoints; narrow changes to them are included in this bounded assignment.
3. The owner runs focused checks throughout implementation. Relevant public encounters and saved continuations precede the next broad regression checkpoint; do not repeatedly run the whole suite during every edit.
4. Continue the remaining mandatory level-1 features and subclasses. Level 2 and the later simplification review remain subsequent acceptance gates.

## Feint

Prepared files: `skill_actions.py`, `skill_content.py`, `tests/test_feint.py`. The owner reported 27 passing Feint/skill tests and one relevant Barbarian helper check. No public Feint encounter has yet run.

The procedure handles trained Deception, reach, mental eligibility, all four outcomes, Scoundrel’s effect and optional Step, and existing Guidance/Hero choices. Its `FeintOffGuardEffect` records the source, exposed creature, eligible attacker, melee scope, turn-end boundary and whether one eligible attack consumes it. The module provides `feint_off_guard_applies(...)` and `consume_feint_off_guard_on_attack(...)`.

Required connections:

- Store `EncounterState.feint_off_guard_effects`, serialize the typed records, and expire them at their recorded source turn-end boundary.
- Admit the command in dispatch, available actions, exports and command persistence; the terminal needs its ordinary numbered action.
- Include the attacker-specific effect in Strike AC. Consume a one-use effect only while preparing the eligible attack, and preserve its contribution in the saved check after consumption. Rerolls and save/load must use the same original defense.
- Validate and resume Scoundrel’s optional Step through normal movement handling. Keep ordinary unconditional conditions separate.
- Consume ordinary success on committed physical Trip/Grapple attempts against the feinted target, including failures, without reducing the maneuver DC. Rejected requests and attacks against other targets preserve it. Classify melee explicitly; do not mistake every attack-trait action for melee or change printed traits to manufacture that classification. Actual melee spell attacks qualify when introduced. The user explicitly ruled that Escape preserves the Feint opening, including Escape from the feinted creature’s physical hold. Test Feint → Escape → Strike; the Strike must still receive and consume the opening. Do not infer consumption from Escape’s attack trait or unarmed modifier.

Public acceptance must distinguish ordinary success, critical success and reversed critical-failure exposure; unrelated attackers and ranged attacks must not receive an ordinary melee-only benefit. Preserve actions, MAP, dice and saved choices. Use legal admitted actors and public movement/commands for encounter evidence. A procedure-only test does not establish a playable Rogue.

## Existing warpriest casting

Prepared files: `family_casting.py`, `tests/test_casting_integration.py`. Fifteen selected tests pass: seven direct new-procedure tests, one public legacy Heal range test and seven resource-helper tests. Public casts now use the new procedure. The later core checkpoint passed 13 selected checks, including a saved spell-slot prompt followed by saved Heal willingness; exactly the chosen slot was spent. An earlier combined focused selection passed 50 before that new case.

The new `begin_cast(context, command)` adapts existing prepared definitions and authoritative `PreparedSlotState.spent` values to `CastingSource`, `SpellAccess` and `CastingResource` snapshots. It applies the resulting `ResourceSpend` back to those existing slots. It does not create a second persisted resource ledger.

Required connections:

- Have `_cast` build `FamilyProcedureContext(self, state, dice, actor, get_definition(actor.definition_id), "casting")`, call `family_casting.begin_cast`, and use the existing result/error conversion.
- Supply `present_spell_slot_choice(command, options, *, spell_name, actions)`. It creates the existing `kind="spell_slot"` pending record with actor, spell, action count, target and self-inclusion fields. Preserve its existing prompt/options behavior and reject an already pending choice or an already selected slot.
- Keep the existing `_choose` route that re-enters `_cast` with the selected slot. Keep the public `Cast` constructor, saved slot choice, target/willingness/reaction/Hero choices and `ActionContinuation(kind="cast")`. No new family continuation or save schema is necessary for this migration.

The shared target resolver now enforces two-action Heal’s 30-foot range. The public regression uses ordinary movement in `s3_long_lane_crossfire` to test 30 feet versus 35 feet, including rejection without spending actions, slot or dice. The core owner confirmed that reaction-time revalidation uses this same resolver. Do not duplicate the range rule in the new procedure.

Public acceptance after connection: repeated cantrips, automatic single-slot and explicit multiple-slot selection, exhaustion, atomic rejected casts, disruption, willingness, save/load at actual prompts and a complete encounter using the existing admitted warpriest. This does not claim spontaneous or focus casting support.

## Following checkpoint

After these connections pass, follow the [damage and equipment handoff](damage-equipment-handoff.md): one shared typed-damage path, then steel shields and initial fundamental runes. These remain serial shared-core slices.

## Narrow questions still pending

Hag spell timing, broad resistance across paired attacks, and reload-0 bow manipulation remain user questions. Escape preserving Feint is now an explicit user ruling. Only their dependent behavior waits. The existing stable-unconscious-at-zero damage limit remains explicit.
