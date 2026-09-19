# Justice Champion delivery and independent review

## Current outcome

The selected level-1 Champion is accepted after independent source-and-play review and three ordinary repairs by its original owner. A complete healthy-start fight reaches victory and survives saved reaction and Hero decisions. The final integration passes 710 tests with measured peak memory below 66 MiB. Current ownership and counts live in [ACTIVE](ACTIVE.md); the source/build contract remains in [the Justice packet](justice-runtime-work.md).

Verified launch from the project directory: `.venv/bin/python -m pf2e play justice_champion_iomedae_vs_guard_dog --seed 0`.

## Owner's executable handoff

- Setup: `get_setup("justice_champion_iomedae_vs_guard_dog")`.
- Commands: `LayOnHands("justice_ally")`, `SuppressAura()`, `ResumeAura()`, `ToggleAura(active)`; ordinary `Choose(choice_id, option_id, owner_actor_id)` handles reaction decisions.
- Desperate Prayer is offered at the Champion's turn start with zero Focus; an unused temporary point expires at turn end.
- Exact content: `src/pf2e/justice_content.py`, `JUSTICE_CHAMPION`, `JUSTICE_CHAMPION_SETUP`; family procedures in `src/pf2e/justice.py`; integration in Encounter, persistence and terminal.
- Owner tests: `tests/test_justice_champion.py`, eight focused passes; 32 adjacent regression passes and 698 full-suite passes before review. An earlier 697-test integration measured 3.41 seconds pytest and 68,829,184 bytes peak memory; do not treat that older measurement as a new post-repair benchmark.
- The owner reports a continuous damage/protection/retaliation sequence and terminal healing/aura controls. The initial saved Hero decision report is superseded by the independent reload failure below.

## Independent findings repaired and verified

1. **Selected build proficiency metadata.** Sol checked [the Champion's initial proficiencies](https://2e.aonprd.com/Classes.aspx?ID=58). Fortitude and Will are expert at level 1; their numeric modifiers already match expert, but the stored labels say trained. Required trained spell attack and spell DC proficiency entries are also absent despite numeric values being present. Correct the metadata and retain assertions for the actual selected sheet.
2. **Saved retaliation cannot reload at the Hero choice.** Sol's public healthy-start sequence raises the ally's shield, takes a dog attack, saves/loads the protection offer, accepts protection, chooses ally Shield Block and reaches a Hero decision on the Champion's retaliation. Saving succeeds but loading rejects the pending Strike because its physical weapon identity is missing. The requested repair preserves strict item validation and attaches the real held weapon identity to the continuation.
3. **Lay on Hands expires on the wrong turn.** The same continued fight confirms AC22 while a raised shield and Lay on Hands stack. At the ally's next turn, the shield ends but Lay on Hands must remain, giving AC20 until the Champion's next turn starts. Actual AC18 exposed an effect sourced to the target and target-turn expiry. Sol checked [spell duration rules](https://2e.aonprd.com/Rules.aspx?ID=2221). The owner must use the real caster and ordinary caster-turn spell timing, also correcting any earlier focused test that expected target-turn expiry.

All three repairs now pass independent review. The retaliation reload retains physical item identity and interrupted parent state, and the fight reaches victory after correct healing-bonus expiry. The earlier AC20 expectation while both bonuses were active was a review-test error and has been corrected to AC22; the subsequent AC20 after only the shield ends is the distinct valid expectation.

Retained reproduction: `tests/test_justice_play_review.py::test_healthy_fight_saves_protection_block_retaliation_and_lay_expiry`, deterministic rolls `(1, 20, 10, 20, 4, 10, 1, 1, 10, 3)`.

## Independent acceptance evidence

Sol's five retained review cases pass; combined with the owner's Justice file, **14 tests pass in 0.20 seconds**. The complete public encounter covers resistance, allied Shield Block ordering, off-turn retaliation without an attack penalty, holy weapon damage, actual injury, Lay on Hands healing, saves at both reaction and retaliation-Hero choices, the AC22→20→18 sequence, an actual Desperate Prayer offer and victory. Other cases cover protection when the foe cannot be reached, suppressed/unconscious aura, retaining a reaction after declining protection, own-turn retaliation at −5, prayer point saves/spending, Refocus, preparation and the selected sheet grants.

The mixed 6 slashing + 2 fire example correctly deals 5 under [Spring 2026 errata](https://paizo.com/blog/spring-errata-2026): resistance to all damage applies once, with the defender choosing the most beneficial component. This independently source-checked result does not decide the separate pending paired-Strikes issue.

Additional reviewed sources: [Justice](https://2e.aonprd.com/Causes.aspx?ID=11), [Lay on Hands](https://2e.aonprd.com/Spells.aspx?ID=2047), [Desperate Prayer](https://2e.aonprd.com/Feats.aspx?ID=5884), and the Champion/duration references above. Both review pytest processes exited 0 and no background process was launched.

Undead Lay on Hands, other causes/domains/blessings and the existing stable-unconscious-at-zero damage boundary remain explicitly unsupported. The reviewer reports no remaining blocker for the selected slice. Shared paths are released to the existing Investigator owner; root writes this record from delegated reports only.

## Final integration and accounting

The original owner's existing integration command reports **710 passed in 3.73 seconds**, measured `pytest_seconds=4.162`, peak **69,107,712 bytes / 65.906 MiB**, compile/pytest/diff exit codes 0. Catalog: 51 admitted setups / 36 creatures, 7 staged setups / 1 staged creature, save version 17. The final adjacent selection reports 33 passes. The owner reported synchronous integration/CLI exits and no retained jobs, but could not enumerate host processes.

**That process claim was contradicted by the subsequent independent audit.** Three earlier temporary Justice Python probes remained alive, one at about 2.4 GB RSS. The auditor stopped PIDs 37146, 40265 and 47621 and confirmed exit. The separately accounted [resource repair](probe-resource-repair.md) is now complete: shared scripted-input/capture bounds, a repeating-input regression, removal of the three obsolete scripts and an independent all-clear for those processes. No production rule or EOF behavior changed. Rules acceptance and the 710-test memory measurement remain valid; neither alone proved those separate ad hoc probes were safe.

Closed run records:

| Assignment | Observed model | Input tokens | Cached input (subset) | Output tokens | Requests / compactions |
|---|---|---:|---:|---:|---|
| `justice-champion-delivery-2026-09-16` | Luna/xhigh | 42,343,701 | 41,416,704 | 135,660 | 296 / 3 |
| `justice-independent-play-review-2026-09-16` | Sol/high | 6,872,187 | 6,657,536 | 24,636 | 60 / 1 |

The original implementation owner retained all three review repairs; no owner change or separate repair assignment was created. Dollar cost is unavailable. Counts come from the deterministic raw-metadata collector, including compactions and excluding inherited parent records.
