# Selected level-1 Storm Druid

## Outcome and status

**Accepted at the September 18 15:37 UTC coordinator wake.** The selected Storm Druid is playable through normal terminal selection, a healthy encounter, saved choices and the next encounter. One Terra/high implementation owner retained all ordinary review repairs. Source-checked independent Sol play and the canonical gate passed. No new P0/P1 ruling was required. Luna native-messaging investigation is separate.

The handoff reused `docs/implementation/pc1-pc2-nature-rules.md` sections 1–2 and 7–8 and the accepted Wizard mechanisms. Other orders remain reference inventory. Entry baseline was 1,044 tests, 56/40 accepted setups/creatures, 17/7 staged, save version 17. Root records worker findings only; source and implementation inspection stay with workers. Earlier dated sections below preserve checkpoint history rather than the current acceptance state.

## Final acceptance and delivery

The initial canonical run compiled cleanly and found one stale catalog assertion: `_BASE_SETUP_IDS` omitted newly normal `STORM_DRUID_SETUP`. It failed 1 of 1,065 cases (reported wrapper 5.294 seconds; peak 78,397,440 bytes). The retained owner added only that import/ID; owner's focused check passed 18 / 0.15 seconds, independent Sol verification passed 29 / 0.18 seconds and confirmed `storm_druid_vs_guard_dog` alone entered the ordinary catalog. Auxiliary fixtures remained excluded.

The single justified rerun passed **1,065 tests / 4.79 seconds**, wrapper 5.182 seconds, peak **77,774,848 bytes (74.17 MiB)**. Compile and diff checks passed. Catalog: **57 admitted setups / 41 creatures; 21 staged setups / 8 creatures; save version 17**. Sol's final attributable PID/PPID/start-time/command inventory found only its audit shell/rg; no retained task-owned test/probe descendants and no termination needed. No commit was made. Final selected build, public interactions and limits are recorded in the independent-review section below.

### Usage and delivery observations

| Assignment | Observed model/effort | Input | Cached input (subset) | Output | Requests / compactions |
|---|---|---:|---:|---:|---:|
| `storm-druid-terra-implementation-2026-09-18` | Terra/high | 21,647,044 | 21,206,528 | 62,209 | 160 / 1 |
| `storm-druid-independent-review-2026-09-18` | Sol/high | 11,263,968 | 10,979,968 | 36,395 | 92 / 1 |
| Implementation and review total | — | 32,911,012 | 32,186,496 | 98,604 | 252 / 2 |

The earlier Astra source handoff adds 1,191,423 input / 1,087,488 cached / 5,295 output, 15 requests, no compaction. Including that handoff, this playable slice used **34,102,435 input / 33,273,984 cached / 103,899 output**, 267 requests, two compactions. Unsuccessful Luna/configuration work remains separately attributed and is not silently rolled into this content-delivery total. Dollar cost is unavailable.

No implementation owner changes occurred. Terra was registered at 14:52:59 UTC; a first real Tempest saved-resolution checkpoint arrived by the 15:00 wake (within approximately eight minutes). Acceptance at the 15:37:53 wake was about 45 minutes after dispatch and includes scheduler, review and one platform-error recovery; exact productive-work and dependency-wait durations are unavailable. Repairs stayed with the owner: animal attitude/time semantics, legal sheet/grants, Tempest traits, finite daily-preparation menu, supported background/language corrections and the final stale catalog assertion. The local review terminal-label failure was a fixture correction. Required public play, save/load and terminal paths passed before canonical integration.

## Finite behavior to deliver

- **Tempest Surge:** two actions, one Focus Point, 30-foot creature target, concentrate/manipulate, basic Reflex against 1d12 electricity. Damage roll 7 gives 0/3/7/14 across the four degrees. Failure and critical failure also cause clumsy 2 for one round; no persistent damage. The existing packet applies the unlisted-critical-effect rule to the rider; independent review checks all degrees. [Spell](https://2e.aonprd.com/Spells.aspx?ID=1860), [degree rule](https://2e.aonprd.com/Rules.aspx?ID=2286).
- **Storm Born:** finite authored weather facts affect real checks. Remove weather-caused circumstance penalties from ranged spell attacks and Perception; targeted spells ignore weather concealment. Preserve dim light, cover, unrelated penalties and weather effects on ordinary weapons. No weather simulator. [Feat](https://2e.aonprd.com/Feats.aspx?ID=4712).
- **Primal preparation:** five cantrips—Electric Arc, Guidance, Stabilize, Tangle Vine, Light—and two rank-1 slots initially Heal/Runic Weapon. All effects already exist and Astra checked primal eligibility. Either rank-1 spell may occupy either slot, including duplicate preparations. Do not grant a fictitious spellbook or Spell Substitution to enable choices.
- **Animal Empathy:** authored rudimentary questions/answers and actual Diplomacy with an eligible animal. A small social record provides willingness, attitude, Will DC, request DC and degree-specific answers. Make an Impression and Request use their printed outcomes and save attitude/results. This grants neither obedience nor extra combat commands. Reuse the authored Streetwise pattern, not a social-world simulator. [Animal Empathy](https://2e.aonprd.com/Feats.aspx?ID=4709), [Diplomacy](https://2e.aonprd.com/Skills.aspx?ID=39).
- **Fixed sheet:** legal selected ancestry/background grants; Wisdom casting; Nature/Acrobatics and class skills; trained Perception/Fortitude/Reflex, expert Will; simple/unarmed attacks and light/medium/unarmored defenses. Include Shield Block with a real held shield, Wildsong, Voice of Nature/Animal Empathy, Storm Born, Tempest Surge and focus capacity 1. Anathema remains an explicit sheet/GM fact unless a violation is authored. [Druid](https://2e.aonprd.com/Classes.aspx?ID=34), [orders](https://2e.aonprd.com/DruidicOrders.aspx).

## Execution handoff

Relevant files are under `src/pf2e/`. Add `druid_content.py` and only a narrow `druid.py` if useful; register through `content.py`. Fixed sheet analogue: `wizard_content.py::BATTLE_MAGIC_WIZARD`; physical shield: `justice_content.py`.

Spell pointers: `spells.py::SPELLS`, `CONCEALMENT_TARGETED_SPELL_IDS`; `encounter.py::_resolve_cast`, `_roll_frostbite_save`, `_resolve_direct_fortitude_result`, `_apply_spell_damage`, `_apply_enfeebled`; `model.py::ActiveConditionEffect`, `EffectExpiration`. Existing `conditions.py::condition_modifiers` supports clumsy. Extend pending cast/check/condition validation in Encounter and persistence; preserve source-start expiry through incapacitated caster turns.

Weather pointers: `EncounterSetup`, `EncounterState`, `Encounter.target_is_concealed`, `_resolve_spell_concealment`, `_validate_concealment_pending`, `_spell_attack_modifier_breakdown`; initiative in `start`, `start_next_encounter`, `_continue_initiative_initialization`. **Do not globally clear target concealment for Storm Born:** ordinary weapon/skill targeting must retain weather concealment. Saved initiative rerolls retain their correct modifiers.

Preparation hazard: live choices currently depend on Wizard flags. `wizard.prepared_slot_rejection` returns no restriction without a book, but `family_casting._prepared_casting_snapshots` and persistence still require exact original definition spells for non-Wizards. Add one finite Druid permission path consistently across daily choices, casting and loading.

Animal pattern: `model.py::EncounterSetup.streetwise`; `investigator.py::Streetwise`, `_streetwise_records`, `_resolve_streetwise`, `_streetwise_finalize`; family action/choice serializers. Reuse authored context without granting Investigator features. Terminal: `_choose_cast_inputs`, daily preparation branch, `run_terminal`; retain `BoundedInput`/`BoundedTranscript`.

## Acceptance and verified prerequisites

### Coherent implementation ready for independent review

At the September 18 15:15 UTC wake, the owner reported successful recovery from the prior API parameter error and no recurrence. The same owner completed the proposed Druid outcome and **80 focused tests in 0.41 seconds**, with diff-check clean. No broad suite has run and Druid is not yet accepted.

Reported paths include normal catalog and bounded terminal Tempest selection; legal duplicate rank-1 daily preparations; healthy Tempest victory → Refocus → saved next-day preparation → next-scene casting; weather-sourced spell attack/Perception penalties and targeted-spell concealment with ordinary concealment retained; authored Animal Empathy request records and save/load; and an actual held steel shield with Raise Shield → jaws Strike → saved Shield Block → all five damage prevented by Hardness.

Runtime pointers now include `src/pf2e/druid_content.py`, `Encounter._roll_tempest_surge_save`, `_resolve_tempest_surge_result`, `animal_empathy`, and `family_casting._prepared_casting_snapshots`. Owner completed the minimal AGENTS Terra/high restoration. Its process enumeration was sandbox-denied; no independently verified process all-clear follows from that report.

Sol/high `/root/storm_druid_review` is active under `storm-druid-independent-review-2026-09-18`. Source-check actual grants/rules and perform independent saved play/terminal checks. Ordinary production repairs remain with `/root/storm_druid_terra_owner`, activated directly through followup_task. Reviewer also performs attributable process audit. Root accepts the result and authorizes broad integration only after coherent focused/source/play evidence.

### Independent review complete; integration authorized

The final source-legal selection is **Human / Versatile Human / Scholar (Nature), Storm Druid**. Ability modifiers: Strength +1, Dexterity +2, Constitution +2, Intelligence +0, Wisdom +4, Charisma +0. HP 18, AC 16, Speed 30. Fleet works in movement; Natural Skill grants Athletics/Society; Scholar grants Nature, Academia Lore and Assurance (Nature), with Medicine replacing duplicate Nature. Wildsong replaces the legacy language label. The real authored guard-dog Recall Knowledge path uses Assurance total 13 with no die or Hero choice. Herbalist/Natural Medicine claims were removed, avoiding an unimplemented active grant and a new healing subsystem.

Sol's `tests/test_storm_druid_review.py` passed **11 independent cases / 0.16 seconds**. Combined focused compatibility passed **107 / 0.42 seconds**, with clean diff-check. Public evidence independently covers all Tempest degrees/costs/rider, Storm Born weather versus dim/weapon boundaries, actual held shield/save → healthy victory → Refocus → duplicate daily choices → save/load → next scene/changed-slot cast, authored 60-second Impression followed by saved eligible Request and critical-failure attitude reduction, complete sheet/Assurance and bounded terminal casting/recovery/preparation.

Sources checked include the Druid/Storm/Tempest/Diplomacy/Scholar packet plus basic-save/degree rules and clumsy. The only newly explicit selected-content boundary is GM-adjudicated anathema; earlier global engine limits remain. Narrow escalated process inventory found only the audit shell/rg, no retained task test descendants. One intermediate terminal failure was a reviewer fixture text/label mismatch rather than a production defect.

At the September 18 15:29 UTC wake, root accepted the independent focused/source/play evidence and authorized `.venv/bin/python tools/integration_checkpoint.py`. One localized broad failure may receive same-owner repair, independent focused verification and one justified rerun. No other broad runner is active. Druid admission and both usage closures await final integration/time/memory/catalog/save/cleanup evidence.

### Review repairs retained with the original owner

At the September 18 15:22 UTC wake, Sol identified four substantive repair areas and the retained owner reported fixes, with **80 focused tests / 0.36 seconds** and clean diff-check. Independent verification remains pending:

- Animal Empathy previously allowed Request against an indifferent animal, advanced no time, exhausted the conversation after one roll and retained no attitude. The repair adds a persisted one-minute Make an Impression followed by a separate Request with source-correct eligibility/outcomes.
- The fixed Human/Versatile Human/Herbalist sheet had HP 17 instead of 18 for Constitution +2, omitted ancestry/heritage/background grants and encoded eight rather than nine boosts. The reported correction includes Strength +1 and matching staff damage, plus the legal grants.
- Tempest Surge had an invented storm trait and omitted printed uncommon/air/druid traits; metadata was corrected.
- Terminal daily preparation offered only Wizard-book choices; the repair adds actual finite Druid choices, including changed/duplicate rank-1 preparations without a book or thesis.

Root asked review to distinguish active feat effects from sheet facts, especially Herbalist/Natural Medicine. If an optional background would require substantial unrelated machinery, use a source-legal choice backed by existing mechanics and report the final build. Required Storm/class behavior and complete encounter/save/terminal acceptance remain unchanged; do not count unimplemented active grants or expand into a general exploration system. Reviewer confirmed Natural Medicine was merely recorded while Treat Wounds stayed unsupported. Root clarified that the final selected build should instead use a source-legal already-supported background, without adding a healing subsystem; Scholar with Nature/Assurance is a candidate, subject to correct boosts/skills and an actual public check. Reviewer also flagged legacy Druidic language naming for Wildsong correction. All production repairs remain with the original Terra owner; no broad run is authorized yet.

### First new owner checkpoint

Received at the September 18 15:00 UTC coordinator wake from Terra/high `/root/storm_druid_terra_owner`: Tempest Surge spends one Focus Point without a prepared slot, exposes a real saved Reflex/Hero choice, loads and applies basic electricity damage/clumsy 2 once, then expires at the Druid's next source turn. The direct native report reached root. Exact focused command passed **33 tests in 0.17 seconds**:

```sh
/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q tests/test_storm_druid.py tests/test_spells.py tests/test_casting_resources.py
```

At the 15:07 UTC wake, the owner's turn had failed with platform HTTP 400 `unsupported_parameter: access_programs.cyber`. One recovery followup was issued to the same owner and accounting assignment; no new engine failure, broad test or accepted outcome is implied. Repeated failure must be reported without retry loops or silent model/config changes.

This is owner checkpoint evidence, not final source-review or Druid admission. Weather provenance, Animal Empathy/Diplomacy, terminal and continuous complete play remain in the same active implementation assignment. No broad integration has run.

First new public checkpoint: cast Tempest Surge, save during an actual pending save/reaction choice, load, apply damage/clumsy once and reach caster-start expiry. Inspect actual AC/Reflex/Dexterity-check changes and one Focus Point spent with no prepared-slot charge.

Full outcome: continuous healthy victory using Tempest/shared primal spells and physical Shield Block; Refocus; change legal daily choices; save/load into another encounter and cast the changed slot. Exercise weather versus ordinary controls, authored animal conversation/Diplomacy saved mid-choice, and bounded terminal selection/casting/shield/preparation/animal interactions. Preserve existing stable-unconscious-zero and persistent-damage limits. Independent source review and one root-authorized broad checkpoint precede promotion.

Verified root: `/Users/andrewlee/.codex/worktrees/45673ef6-8f9a-40a9-a1c9-e699d44667ca/pf2e-engine-game-2026-07-10`. Interpreter `.venv/bin/python` 3.11.1; pytest supplies `src`. Five parametrized prerequisites passed in 0.16 seconds, exit 0:

```sh
/opt/homebrew/bin/timeout 30s .venv/bin/python -m pytest -q \
  tests/test_wizard_admission.py::test_daily_preparation_selects_full_legal_book_then_saves_and_casts_next_scene \
  tests/test_movement_spells_review.py::test_saved_force_bolt_concealment_uses_its_committed_focus_point \
  tests/test_shield_integration.py::test_shield_block_choice_saves_and_resumes_without_reroll_or_double_spend \
  tests/test_investigator_streetwise.py::test_failed_recall_allows_separate_two_hour_gather_and_saved_hero_charges_once
```

Additional analogues: `test_wizard_direct_spells.py::test_direct_spell_effects_persist_with_their_printed_rank_one_boundaries`; `test_dim_targeting.py::test_dim_concealment_save_rerolls_four_to_five_then_attacks_once_and_saves_load`.

No broad run or retained pytest/timeout/integration processes. Handoff run `storm-druid-handoff-2026-09-18`: Astra/high, 1,191,423 input / 1,087,488 cached input / 5,295 output, fifteen requests, no compaction. Cached input is a subset. Current owner/next actions remain in [ACTIVE](ACTIVE.md).
