# Wizard: completing the selected spellbook

## Purpose and current evidence

The Battle Magic Wizard can already fight, block with Shield, recover focus, substitute a prepared spell and recast through Arcane Bond. It remains staged because its starting spellbook, preparations and character sheet are incomplete. Completing a book means each selected spell has real supported behavior; names and duplicate permission entries do not count as extra spells.

Astra's completed handoff checked the existing source packets, inspected implementation and ran three accepted public analogues in0.10s: substitution/cast/Bond/save, saved Breathe Fire recipients and saved Runic Weapon. It changed no code and retained no processes. Root records these findings without independently inspecting implementation or sources.

Sources: [Wizard](https://2e.aonprd.com/Classes.aspx?ID=39), [schools](https://2e.aonprd.com/ArcaneSchools.aspx), [Battle Magic](https://2e.aonprd.com/ArcaneSchools.aspx?ID=22).

## Finite selected book

The source-checked level-1 target is eleven distinct cantrips and seven distinct rank1 spells. Prepare five ordinary plus one curriculum cantrip, and two ordinary plus one curriculum rank1 spell. Force Bolt is separate focus magic.

| Selection | Existing executable effects | Required new effects |
|---|---|---|
| Ten chosen cantrips | Light, Void Warp, Telekinetic Projectile, Electric Arc, Frostbite, Ignition, Caustic Blast, Gouging Claw, Tangle Vine, Gale Blast | None |
| Curriculum cantrip | Shield | None |
| Five chosen rank1 spells | Sure Strike, Fear, Runic Weapon, Enfeeble, Runic Body | None |
| Two curriculum rank1 spells | Breathe Fire, Force Barrage | None |

Read Aura remains unavailable. Guidance, Stabilize and Divine Lance are not arcane and cannot fill this book. This finite selection adds shared combat rules useful to other classes; it is not an exhaustive arcane catalog.

## Delivery groups

### 1. Direct attacks, saves and unarmed enhancement — accepted

Terra/high `/root/wizard_direct_spells_owner` completed all five spells under `wizard-direct-spells-replacement-2026-09-17`; Sol/high `/root/bard_lingering_review` independently reviewed them under `wizard-direct-spells-review-2026-09-17`. All runs are closed. One ownership change followed two premature final reports from the initial owner; its partial edits and cost remain attributed separately.

Acceptance: source-checked public/save effects, a full healthy Electric Arc victory and bounded terminal target selection passed. Four review production repairs remained with the replacement owner; a fifth shared Divine Lance save-validator regression found by integration was repaired and independently checked before one justified rerun. Final995tests/4.13s, measured4.479s,75,563,008bytes peak, compile/diff clean;55/39admitted16/6staged,save17. No attributable test processes remained. Projectile supports only the authored staff profile; full Wizard admission remains unfinished. Exact case names and usage totals are in [ACTIVE](ACTIVE.md).

- [Telekinetic Projectile](https://2e.aonprd.com/Spells.aspx?ID=1718): spell attack and physical damage using an actual eligible loose unattended object. Reuse literal `ground_items`; avoid a general environmental-object simulator.
- [Electric Arc](https://2e.aonprd.com/Spells.aspx?ID=1509): one or two targets, shared damage roll, separate basic Reflex saves. First public checkpoint must save a recipient decision and resolve each target exactly once.
- [Frostbite](https://2e.aonprd.com/Spells.aspx?ID=1539): basic Fortitude cold damage; critical failure adds temporary weakness to bludgeoning with the printed expiry.
- [Enfeeble](https://2e.aonprd.com/Spells.aspx?ID=1513): degree-dependent enfeebled values and duration, exercising actual Strength-based rolls/damage.
- [Runic Body](https://2e.aonprd.com/Spells.aspx?ID=1657): willing touched recipient; temporary unarmed accuracy/weapon-dice benefits interact correctly with existing handwraps/runes.

Compact source expectations are a handoff, not a substitute for checking exact spell traits, ranges, degrees and durations. Preserve interruptions, costs, deterministic dice, Shield and health decisions, and completed prepared-cast Bond eligibility. Use healthy continuous encounters and bounded terminal/save paths. No new-spell public probe existed at dispatch; the accepted analogues above establish the prerequisites only.

Execution pointers: `spells.py` `SPELLS`; `encounter.py` `_resolve_cast`, `_roll_divine_lance`, `_resolve_divine_lance_result`, `_roll_void_warp_save`, `_apply_enfeebled`, `_resolve_breathe_fire`, `_finish_damage_application`, `_weapon_rune_profile_for_attack`; casting validation, saved continuations and terminal `_choose_cast_inputs`. Preserve the accepted Wizard live-slot ledger and save17 Shield fields. No other runtime owner is active.

### 2. Persistent combat damage — accepted

Implement [Ignition](https://2e.aonprd.com/Spells.aspx?ID=1565), [Caustic Blast](https://2e.aonprd.com/Spells.aspx?ID=1461) and [Gouging Claw](https://2e.aonprd.com/Spells.aspx?ID=1546) with one literal persistent-damage mechanism. Alchemy metadata is not evidence of a runtime. Required pointers are `_end_turn`, typed persisted conditions and the normal damage path. First checkpoint: save before a tick, apply damage once, then attempt recovery.

Astra/high `/root/native_messaging_rca` completed the concrete contract under `persistent-damage-handoff-2026-09-17`. Terra/high `/root/wizard_direct_spells_owner` implemented `persistent-spells-group-2026-09-17`; Sol/high `/root/bard_lingering_review` reviewed `persistent-spells-review-2026-09-17`. All three runs are closed. One implementation owner retained the complete outcome through ordinary review repairs. No new persistent probe existed at dispatch; three accepted analogues passed0.11s.

Accepted integration: **1,011 tests / 6.14 seconds**, wrapper6.651s, peak76,398,592bytes, compile/diff clean;55/39admitted17/7staged,save17. Independent10tests/0.16s and owner/direct/review75/0.43s passed. Actual healthy last-enemy defeat keeps initiative active until the affected Wizard recovers, then save/Refocus/next scene work. Bounded terminal selects Ignition's form/target and resolves the saved Hero attack. Final audit found no retained test/integration descendants. Exact case names and usage totals are in [ACTIVE](ACTIVE.md).

The selected profiles use a declared **one-minute local GM expiration convention**; this is not presented as a universal printed spell duration. Assisted recovery, incomparable replacement amounts, mixed-source reaction attribution and exceptional initial-negation cases remain unsupported, along with the existing stable-unconscious-zero positive-damage boundary. Caustic Blast supports its own burst self-damage only.

Accepted new pointers: `PersistentDamageEffect`, `EncounterState.persistent_effects`, `_resolve_persistent_damage_end_turn`, `_continue_persistent_recovery`, `_finish_persistent_recovery_check`, `_finish_end_turn`, `_roll_persistent_attack_spell`, `_resolve_persistent_attack_spell_result`, `_resolve_caustic_blast`, `Cast.spell_mode`. Preserve finite source/deadline/recovery-cursor/mode validation and the legal main five-plus-one cantrip preparation, with Projectile in an alternate.

#### Source contract and literal state

Keep one active persistent condition per target/type, with stable identity, source actor/spell, dice/flat amount, provenance and optional explicitly authored expiration. A stronger same-type condition replaces the weaker permanently; do not add them or revive the replaced one. Keep different types together in one saved end-turn batch: snapshotted condition IDs, already rolled values and separate defenses, health-commit state, recovery cursor/current check, and turn-advance state. Apply defenses per effect, then one combined temporary-HP/health event. Do not invoke the full damage-to-health function once per type or invent one attacker for mixed provenance.

After damage, make separateDC15recovery checks; saved Hero Point rerolls must not repeat committed damage. Recovery precedes frightened reduction. Bleed counts as physical for defenses, requires applicable blood and ends when healing restores full HP. Expiration is an authored GM fact, commonly one minute, not a universal fixed spell duration. Assisted recovery may remain outside this group. Sources: [persistent damage](https://2e.aonprd.com/Conditions.aspx?ID=86), [turns and damage](https://2e.aonprd.com/Rules.aspx?ID=2263), [flat checks](https://2e.aonprd.com/Rules.aspx?ID=333), [Hero Points](https://2e.aonprd.com/Rules.aspx?ID=2333).

Rank1 spell details from Astra: Ignition's initial2d4fire changes to2d6in melee; a critical doubles the initial hit and adds persistent1d4(or1d6melee), without doubling this critical-only benefit. Caustic Blast uses30ft range/5ft burst/shared1d8acid/basic Reflex, with1persistent acid on critical failure. Gouging Claw uses melee2d6piercing/slashing and2bleed on a hit,4on a critical. Verify exact traits and source durations during implementation.

#### Integration and explicit limits

Current pointers: `model.py` `CreatureState`, `ActionContinuation`, `DamageResolution`; `encounter.py` `_resolve_damage_to_health`, `_finish_damage_application`, `_end_turn`, `_source_turn_end`, `_begin_turn`, `_finish_if_team_defeated`; `damage.py` `DamageTerm`, `DamageResult`, `_PHYSICAL_TYPES` (currently omits bleed); persistence state/continuation/damage serializers and pending-choice/source-kind validation. The existing full damage method combines defenses and health and rejects self-damage. Add a narrow caster-in-Caustic-Blast path; unconscious turn skipping still needs applicable end-turn processing. Preserve accepted attack identifiers, Shield, Wizard live preparations/Bond and saved recipient continuations.

Approved local execution convention: keep ordinary initiative active while a living participant remains affected, finish once surviving participants clear. Existing End Turn and bounded terminal suffice; guard elapsed-time, Refocus/rest/substitution and next-scene APIs against skipping ticks. No downtime simulator or general event framework is needed.

Stable-unconscious-at-zero positive damage remains explicitly unsupported; Heroic Recovery can expose it on the next tick. Initial-damage-negation exceptions, genuinely ambiguous strength comparisons and mixed-attacker Champion attribution require explicit adjudication or a declared unsupported boundary. Do not invent universal rules. Healthy single-caster proof encounters with ordinary blood-bearing targets and authored expiration can establish this group without those cases; stop dependent work if they become necessary.

#### Required executable sequence

1. Save before tick: fire3+bleed2 causes one5damage health event; recovery15/14 removes fire only.
2. Save during recovery/Hero choice: no repeated damage, damage dice or turn transition after load.
3. Replace bleed2with4, then recover without restoring2.
4. Defeat the last enemy while a healthy ally remains affected; continue turns, recover, save/refocus and enter the next scene.
5. Complete source-valid spell play through the bounded terminal using existing `BoundedInput`/`BoundedTranscript`, alongside focused spell-degree/defense/expiry checks.

These are internal executable checkpoints, not separate assignments. Independent review checks actual play and sources; root authorizes the canonical broad checkpoint afterward.

Check the exact critical outcomes, simultaneous damage types and damage-before-recovery order against [persistent damage](https://2e.aonprd.com/Conditions.aspx?ID=86). Preserve explicit GM recovery/duration facts and the unresolved stable-unconscious-at-zero boundary. No implementation or new public probe is claimed.

### 3. Movement-control spells — accepted

[Tangle Vine](https://2e.aonprd.com/Spells.aspx?ID=1713) adds temporary circumstance Speed reduction and, on a critical hit, immobilization removable by Escape against spell DC. [Gale Blast](https://2e.aonprd.com/Spells.aspx?ID=1994) adds Fortitude-based damage and forced movement.

Astra/high `/root/movement_control_handoff` completed `movement-control-handoff-2026-09-17`: three existing public analogues passed in 0.16 seconds; no edits or retained processes. Terra/high `/root/movement_spells_owner` completed `movement-spells-group-2026-09-17`, independently reviewed by Sol/high `/root/movement_spells_review` under `movement-spells-review-2026-09-17`. All three runs are closed. One owner retained both spells and their movement/save/terminal paths through repairs.

Accepted evidence: 12 independent tests / 0.19 seconds; combined 50 / 0.35–0.36 seconds; actual healthy Vine→Gale victory and bounded self-inclusion terminal play. Review repaired diagonal cost overrun, saved knockout continuation losing the earned push, and premature victory before later recipients. Persistent round-wrap expiry/load was also checked. One frozen spell-inventory assertion needed the two new IDs, independently verified before a justified canonical rerun. Final **1,030 tests / 6.99 seconds**, wrapper 7.539 seconds, peak 77,463,552 bytes, compile/diff clean; 55/39 admitted, 18/8 staged, save 17. Final audit found no retained task test processes.

#### Source and saved-state contract

Vine costs two actions, uses a spell attack at 30 feet and applies a minus-10-foot circumstance penalty to Speeds on a hit, adding immobilized on a critical. Rank 1 lasts until the caster's next start, including an incapacitated/dead caster's turn occurrence. Escape against spell DC removes this Vine's linked effects even when only the Speed penalty is present. Failure degrees apply neither effect. Preserve attack/MAP and manipulate reactions.

Gale costs two actions, has no attack trait and uses a 5-foot emanation with optional caster inclusion. Fortitude: critical success no effect; success half 1d6 bludgeoning; failure full damage plus 5-foot push; critical failure double damage plus 10-foot push. Snapshot origin, recipients and shared damage once. Finish each saved health/defense choice, apply its earned push exactly once, then advance the recipient or finish combat. Resistance reducing damage to zero does not cancel a failed-save push. A recipient knocked unconscious still receives the earned push; dropped equipment stays at the prior square.

Use saved deterministic recipient order and an outward legal grid path with ordinary distance accounting. Stop at map boundaries or obstructing occupants, preserving existing body-sharing rules. Forced displacement spends no voluntary movement action and causes no movement reaction. Escape's optional critical-success 5-foot Stride still uses ordinary reactions. Including the caster causes damage without pushing it away from itself. These are bounded local execution conventions; no vertical terrain or new obstacle framework.

**User-approved P1 resolution:** the external-force check against an immobilized target uses the Gale caster's spell-attack bonus without MAP or attack-count increment, against each relevant holding effect's DC. Failure prevents displacement; success allows movement without removing the hold. This supplies the modifier omitted by the [Immobilized rule](https://2e.aonprd.com/Conditions.aspx?ID=81), not a claim that the printed rule names this bonus.

Other sources: [Escape](https://2e.aonprd.com/Actions.aspx?ID=2296), [forced movement](https://2e.aonprd.com/Rules.aspx?ID=2364), [occupied spaces](https://2e.aonprd.com/Rules.aspx?ID=2360), [turns and emanations](https://2e.aonprd.com/Rules.aspx?ID=2263).

#### Exact owner pointers and acceptance

- `skill_actions.py`: `Escape(impediment_id, check_method, attack_id=None, use_assurance=False)`, `_escape`, `_finish_escape`, `_escape_stride_destinations`. Existing code rejects Speed-only effects and removes all same-caster holds; use linked effect identity so another Grapple or spell survives Escape.
- `model.py`: `ActiveConditionEffect`, `EffectExpiration`, `ActionContinuation`, `DamageResolution`. Persist the Vine source identity, spell DC and source-start expiry.
- `swashbuckler.py` `effective_speed_ft`: currently only panache. Use one state-aware Speed calculation for inspection, Stride/Step and skill movement; same-type penalties do not stack. `Encounter._source_turn_start` needs start-anchored condition-effect expiry as well as active-effect expiry.
- `encounter.py`: `_resolve_cast`, `_roll_persistent_attack_spell`, `_spell_attack_modifier_breakdown`, `_resolve_caustic_blast`, `_continue_caustic_blast`; `_occupant_at`, `_can_share_with_body`, `_release_sourced_holds`; `space.step_cost` and `grid_distance_feet`. Do not model a push by spending the target's voluntary action through `_begin_move`.
- Extend condition/continuation save validation, casting `include_self` eligibility, and terminal `_choose_cast_inputs`. Preserve the persistent tick/recovery cursor and `_advance_after_incapacitated_turn`; pushing must not tick or advance turns.

First new public check: critical Vine, save/load, Escape, normal movement restored. Required branches also include ordinary-hit Escape, unrelated same-caster holds, caster-KO expiry, saved Gale damage then one push, obstruction, forced-versus-voluntary movement reactions, the approved immobilized force check, caster inclusion, a healthy completed encounter and bounded terminal play. Keep legal spell preparation counts and use an alternate setup where necessary.

Adjacent expiry repair is now accepted: persistent records are purged at the source-start round-wrap boundary, and independent saved-wrap tests preserve committed ticks and load correctly. The original concern was that an expired record could remain until end-turn while loading rejected its deadline. The 60-second expiration still matches the declared local GM convention.

Reuse `skill_actions._escape`, `_finish_escape` and sourced impediments. An isolated Rogue critical-specialization helper does not establish public forced movement. Analogue: `test_public_escape_uses_unarmed_attack_and_current_grappler_dc_after_save_load`. First checkpoint: save an immobilizing Vine, Escape it and verify restored movement. No new public probe exists.

### Final legal preparation and admission — accepted

All selected spell effects are accepted within their explicit limits. Astra/high `/root/movement_control_handoff` completed the finite source-checked handoff under `wizard-admission-handoff-2026-09-17`. Terra/high `/root/movement_spells_owner` completed `wizard-admission-group-2026-09-17` across runtime, content, persistence, terminal and tests. Sol/high `/root/movement_spells_review` completed independent review under `wizard-admission-review-2026-09-17`. Ordinary repairs remain with the owner. No materially dependent rules decision is open for this outcome.

The player should be able to select this Wizard normally, see a legal character sheet, choose tomorrow's prepared spells, save, and use those choices in a later encounter. This finishes the selected level-1 build; it does not create a general character builder or add more spells.

#### Known book and daily choices

Astra found no owned cantrips and only five distinct rank-1 spells in the current book; duplicated permission rows do not count as distinct spells. Use the finite eleven-cantrip/seven-rank-1 selection above. Force Bolt stays separate focus magic. Mystic Armor is part of the curriculum but is not needed in this selected book.

Keep nine stable preparation slots:

- Five ordinary cantrips may draw from any of the eleven known cantrips, including Shield.
- One curriculum cantrip may be Shield or Telekinetic Projectile.
- Two ordinary rank-1 slots may draw from any of the seven known spells, including curriculum spells.
- One curriculum rank-1 slot may be Breathe Fire or Force Barrage.
- Preparing the same rank-1 spell in multiple eligible slots is legal.

Add optional actor → slot → spell choices to `Encounter.daily_prepare(actor_ids)` without breaking existing callers that retain their current legal selections. Validate the whole request and accessible owned book before committing elapsed time or resources. Reuse one finite permission helper across preparation, saved Spell Substitution, casting and loading. A small record extension or deduplicated known-book view is sufficient.

Pointers: `wizard_content.py`; `model.py` `SpellbookSpellDefinition(spell_id, rank, source)` and `PreparedSlotState(slot_id, source, spell_id, rank, cantrip, spent=False)`; `family_casting._prepared_casting_snapshots`; live prepared-slot validation in `persistence.py`. The latter two currently skip cantrip membership. Preserve the accepted saved ten-minute substitution path. Sources: [Wizard](https://2e.aonprd.com/Classes.aspx?ID=39), [Battle Magic](https://2e.aonprd.com/ArcaneSchools.aspx?ID=22).

First new executable checkpoint: healthy completed encounter → record rested eligibility → choose a different legal preparation → save/load → next encounter → cast the selected spell. Reject unknown spells, wrong curriculum and altered capacity without changing state.

Owner checkpoint received on the 08:30 UTC coordinator wake: healthy Breathe Fire victory → record rest → changed legal nine-slot preparation → save/load → next scene → cast newly prepared Fear. `tests/test_wizard_admission.py` passed three tests in 0.16 seconds, including atomic unknown-spell, wrong-curriculum and missing-slot rejection. The owner reports the shared permission helper and corrected sheet facts in place. This is focused owner evidence; independent final admission remains pending. Astra also identified `test_owned_curriculum_spell_is_also_legal_in_an_ordinary_slot` and `test_authored_recall_knowledge_is_shared_with_another_supported_actor` as existing analogues.

#### Arcane Bond and selected item

`_record_arcane_bond_completed` already covers Sure Strike, Enfeeble, Runic Body, Breathe Fire and Force Barrage. Add the missing actual completed-cast recording to `_resolve_fear_result` and `_resolve_runic_weapon`, including Fear when the enemy succeeds at its save. Record after the final saved resolution, not merely after paying a slot before possible disruption. Exercise all seven rank-1 spells; cantrips do not need expended-slot history.

`wizard.py` `DrainBondedItem(item_id)` currently accepts any carried item. Enforce the selected `bonded_staff`; the spellbook is not an interchangeable bond. Preserve item-on-person behavior and existing daily reset of history and same-turn recast permission.

Astra resolved the owner's timing question from the [Remaster Drain Bonded Item action](https://2e.aonprd.com/Actions.aspx?ID=2260): there is no requirement to use it before acting. Keep the existing current-turn expiry. The saved proof should complete Fear or Runic Weapon on turn A, then Drain for free on turn B, save/load the permission and recast for the normal two actions before turn B ends. No new ruling or timing redesign is needed.

#### Legal Human Scholar sheet

| Part of the build | Selected legal result |
|---|---|
| Combat values | HP 16, fist +5, Will +5; retain AC 15, spell attack +7 and DC 17 |
| Versatile Human | Fleet, giving Speed 30 feet |
| Ancestry feat | Natural Skill: Athletics +3 and Acrobatics +5 |
| Scholar | Nature +3, Academia Lore +7, Assurance (Nature) |
| Wizard skills | Arcana +7, Crafting +7, Medicine +3, Society +7, Stealth +5, Thievery +5, Occultism +7 |
| Languages | Common, Draconic, Dwarven, Elven, Gnomish, Goblin |
| Ability boosts | Human Intelligence/Constitution; Scholar Intelligence/Dexterity; class Intelligence; free Intelligence/Dexterity/Constitution/Charisma |

This gives eleven trained skills without duplicate grants. Languages and Lore are recorded facts; they do not require an exploration subsystem. Sources: [Human](https://2e.aonprd.com/Ancestries.aspx?ID=64), [Versatile Human](https://2e.aonprd.com/Heritages.aspx?Ancestry=64), [Scholar](https://2e.aonprd.com/Backgrounds.aspx?ID=440), [Natural Skill](https://2e.aonprd.com/Feats.aspx?ID=4479), [Fleet](https://2e.aonprd.com/Feats.aspx?ID=5150), [languages](https://2e.aonprd.com/Rules.aspx?ID=2095).

Public Assurance currently supports Athletics only. Extend the existing authored Recall Knowledge path to accept an explicit Assurance choice for selected Nature, including the terminal. The result is 13, with no die, attribute or other modifiers and no Hero reroll. Reuse `investigator.py` `RecallKnowledge`, `_resolve_recall_knowledge`, `_knowledge_records`, `_finalize_knowledge`, and `checks.resolve_assurance_check`. Existing `GUARD_DOG_KNOWLEDGE` accepts Nature at DC 16; its correct failure/exhaustion is valid public evidence. Attach that authored packet to the Wizard scene. Source: [Assurance](https://2e.aonprd.com/Feats.aspx?ID=5121).

#### Admission evidence and handoff

Require normal catalog/terminal selection, the corrected inspectable sheet, public daily choices, saved Fear/Runic Weapon Bond recasts, public Assurance, preserved spell/substitution play, healthy victory, Refocus and a saved next encounter. Promote the primary Wizard definition/setup to `CREATURES`/`SETUPS` in `content.py`; keep diagnostic alternates staged and preserve stable IDs where practical. Terminal pointers: `main`, `run_terminal`, daily preparation branch. Source review precedes one root-authorized canonical integration checkpoint. No admission is claimed until that evidence passes.

Astra's prerequisite command passed five tests in 0.21 seconds with exit 0:

```sh
/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q \
  tests/test_wizard_substitution.py::test_replacement_cast_round_trips_bond_in_a_healthy_next_encounter \
  tests/test_wizard_substitution.py::test_bounded_terminal_completes_spell_substitution_after_daily_preparation \
  tests/test_daily_preparation.py::test_record_rested_save_load_prepares_and_casts_restored_resources_in_next_scene \
  tests/test_investigator_knowledge.py::test_authored_recall_knowledge_is_shared_with_another_supported_actor \
  tests/test_investigator.py::test_investigator_slice_is_catalogued_with_its_stable_ids
```

The owner's coherent group initially passed 111 focused tests in 0.71 seconds, with compile/diff clean. It included public preparation, the fixed sheet/book, Assurance Nature and terminal choice, and saved later-turn Fear/Runic Bond recasts. A narrow Runic Weapon target repair added the selected bonded staff. Four existing movement fixtures were updated for HP 16.

Independent review completed before the 08:59 UTC wake. Its final combined command passed **85 tests in 0.63 seconds**, exit 0, with compile/scoped diff clean and no retained pytest/integration descendants:

```sh
/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q \
  tests/test_movement_spells_review.py tests/test_wizard_admission.py \
  tests/test_wizard_substitution.py tests/test_wizard_substitution_review.py \
  tests/test_battle_wizard_combat.py tests/test_runic_weapon_play.py \
  tests/test_runic_weapon_saves.py tests/test_runic_weapon_refusal.py \
  tests/test_expansion_catalog.py tests/test_dim_spell_targeting.py
```

Seven production findings were repaired by the original owner and independently checked:

1. Prepared Runic Weapon paused for a manipulate reaction could not load because validators required spontaneous casting.
2. Forged saved Bond permissions could name an item other than the designated staff.
3. Normal catalog labels still called the selected build staged.
4. A completed Runic cast lost Bond history when an ally refused the effect.
5. The Human sheet lacked ordinary vision, preventing a dim-light setup.
6. Selected targeted spells had inconsistent concealment handling across live, resumed and saved casts; failed targeting also lost completed-cast Bond history.
7. Saved Force Bolt concealment lacked the correct committed Focus Point provenance.

The independent file now has seven admission cases alongside twelve movement cases. One reviewer fixture needed to resolve the existing Hero choice after a PC failed concealment; that was a test error, not an eighth production finding. Source checks included the build/grant sources above, Spell Substitution, Drain Bonded Item and [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62).

Actual public evidence covers catalog membership/sheet, finite daily choices and inaccessible-book atomicity, healthy victory → preparation/save/next scene/Fear, saved Fear/Runic recasts, Runic refusal/disruption, saved dim Enfeeble/Force Bolt, and bounded terminal Assurance, daily preparation, substitution and Bond. No new admission limit was found; the pre-existing unconscious-at-zero and persistent recovery/attribution limits remain.

Root accepted that focused/source/play evidence and authorized **one canonical integration run** at the 08:59 UTC wake. The owner reports performance, catalog/save counts and cleanup afterward. The first canonical run found six stale assertions in catalog membership, HP-dependent persistent/Shield expectations and staff-inclusive Runic diagnostics. Their narrow repair passed independent verification (56 tests / 0.41 seconds), followed by one justified rerun: **1,044 tests / 6.13 seconds**, wrapper 6.651 seconds, peak 77,643,776 bytes, compile/diff clean; catalog 56/40 accepted and 17/7 staged, save version 17. Final attributable audit found no retained test/integration processes. Root accepts the selected Wizard as the tenth level-1 class; owner and reviewer runs are closed. No commit was made. Final combined usage: 47,133,053 input / 46,222,080 cached input / 104,525 output; 319 requests and three compactions.

These are existing prerequisites, not evidence for the new daily-choice or final admission behavior. Astra made no edits, ran no broad integration and reported no retained descendants. Closed handoff usage: 1,710,444 input / 1,532,672 cached input / 6,226 output, eleven requests and no compaction. Implementation/review accounting was registered before activation; current ownership and acceptance remain in [ACTIVE](ACTIVE.md).

## Environment and accounting

Verified project root: `/Users/andrewlee/.codex/worktrees/45673ef6-8f9a-40a9-a1c9-e699d44667ca/pf2e-engine-game-2026-07-10`. Interpreter `.venv/bin/python`3.11.1; pytest adds`src`. Focused command: `/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q <selection>`. One synchronous process per worker; finite capture, no background/watch/xdist. Canonical command remains `.venv/bin/python tools/integration_checkpoint.py` at root-authorized boundaries.

Closed investigation `wizard-legal-book-handoff-2026-09-17`: Astra/high,3,213,214input /3,112,832cached /14,251output,23requests,1compaction. Cached input is a subset; dollar cost unavailable. Implementation and review boundaries were registered before dispatch/reservation; current status lives in [ACTIVE](ACTIVE.md).
