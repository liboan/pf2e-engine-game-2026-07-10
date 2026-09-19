# S3i: More encounters that combine the existing rules

## Purpose and result

Before proceeding to S4, add **eight distinct S2 encounters and eight distinct S3 encounters**. These are complete fights that expose how existing mechanics affect one another, with useful additional low-level content where the current engine can represent its applicable rules accurately.

The goal is stronger coverage and more varied decisions. Repeating a seed, adding renamed copies, or checking one rule in isolation does not constitute another encounter.

## Current state

**Complete and independently accepted:** eight new S2 encounters and eight new S3 encounters. Their combined collection passes **18 tests: 16 complete encounters and two content checks**. Four independent alternate complete routes also pass. The full repository suite passes **211 tests**. S4 has not started.

There are **21 catalogued setups**: the existing five plus sixteen additions. New source-backed content consists of two fixed fighter loadouts and elite Guard Dogs. Existing rank-1 spells supply the casting variety. Two catalogued 15×5 maps expose range/area boundaries; the others retain the open 7×5 map. Exact catalogue admission remains enforced.

## Scope

- Reuse S2 martial, equipment, reaction, positioning, Hero Point and health rules.
- Reuse S3 ranged, casting, basic-save, healing, resource and simple-effect rules.
- Select useful low-level spells, feats or creatures whose mandatory applicable behavior is supported. Additional content need not mean adding every content category.
- Permit small shared corrections exposed by these encounters. Defer a content choice that needs disproportionate machinery or later-stage mechanics.
- Retain the explicit unsupported stable-zero damage boundary while the existing user ruling remains pending.

## Selected content and source review

The design reader checked these sources on 2026-09-15. Keep the exact build and trait boundaries visible; these additions do not claim whole-class support.

| Added definition | Changes from an existing reviewed sheet |
|---|---|
| Fleet shortsword fighter | Fighter M replaces Natural Skill with General Training → Fleet, removes the two trainings it supplied, and gains Speed 30. Held shortsword is +9, 1d6+4 piercing with agile, finesse and versatile slashing; this Strength build still uses Strength. Original longsword is carried. Vicious Swing remains available. |
| Elite Guard Dog | Published elite adjustment: level 1, HP18, AC17, Perception8, Fortitude7/Reflex9/Will6, jaws +8 and 1d4+3 piercing. Speed 30 and Pack Attack remain. Its extra Pack die is still 1d4; elite damage applies once to the Strike. |
| Rapier fighter | Fighter R replaces bow/arrows with a held rapier: +9, 1d6+1 piercing, finesse and deadly d8. Retains carried longsword, fist and Vicious Swing. The disarm trait is visible, while the Disarm action remains explicitly unavailable. |

Sources: [shortsword](https://2e.aonprd.com/Weapons.aspx?ID=398), [rapier](https://2e.aonprd.com/Weapons.aspx?ID=391), [General Training](https://2e.aonprd.com/Feats.aspx?ID=4476), [Fleet](https://2e.aonprd.com/Feats.aspx?ID=5150), [elite adjustment](https://2e.aonprd.com/Rules.aspx?ID=3262). Unchanged character, dog and spell facts retain the [S1–S3 source note](../implementation/s1-s3-rules.md).

## S2 encounter matrix

All start healthy on open 7×5 maps. All eight tests observe their named interactions, save and restore meaningful state, then continue to an actual fight outcome. Layout details are ordinary catalogued data and may be adjusted to make the intended legal decisions possible.

| Encounter ID | Cast and tactical situation | Required interaction evidence |
|---|---|---|
| `s2_fleet_diagonal_assault` | Fleet fighter and melee ally approach a dog and elite dog. | Four diagonal squares cost 30 feet in one Stride; two actions remain for Vicious Swing. Verify attack count and next-round refresh. |
| `s2_mixed_blade_pressure` | Fleet fighter switches blades against an elite dog, with a melee ally and ordinary dog nearby. | Paid draw; second shortsword attack uses −4 while longsword uses −5. Vicious Swing advances attack count by two; later shortsword uses −8. Exercise versatile slashing. |
| `s2_flank_rotation` | Two fighters surround an elite dog, with another dog nearby. | Flanking changes a consequential melee attack. Step removes the flank without a reaction; later movement re-establishes it. |
| `s2_mixed_pack_screen` | Two fighters face an elite dog supported by an ordinary dog and a humanoid fighter. | Both unlike allies qualify for Pack Attack; moving one away removes the extra die. Distinguish its ally requirement from flanking and apply elite damage only once. |
| `s2_reaction_relay` | Two allied fighters threaten an opposing fighter's movement, with a dog behind. | Decline one reaction and accept another; no repeated offer by the same reactor for the same move. Save at reaction and nested Hero choice; resume movement without duplicated cost or MAP changes. |
| `s2_contested_weapon_swap` | A Fleet fighter changes weapons beside an opposing fighter; each side has support. | Critical Reactive Strike disrupts Interact after its action is paid, without transferring the item. Retry after the reaction is spent. Release remains exempt. |
| `s2_nonlethal_passage` | Two fighters must pass an ordinary dog to reach an elite dog. | Nonlethal knockout leaves the dog prone and unconscious in the scene. Use the supported unconscious-creature occupancy rule; later lethal defeat has a different result. |
| `s2_heroic_last_stand` | Elite and ordinary dogs knock out one of two fighters. | Real damage triggers weapon drop and initiative movement. Save the health decision, spend all remaining Hero Points to stabilize without adding wounded, and have the ally complete the fight. Never attack the stabilized PC. |

Applicable reviewed sources: [MAP](https://2e.aonprd.com/Rules.aspx?ID=2289), [grid movement](https://2e.aonprd.com/Rules.aspx?ID=2356), [Vicious Swing](https://2e.aonprd.com/Feats.aspx?ID=4775), [flanking](https://2e.aonprd.com/Rules.aspx?ID=2375), [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256), [movement reactions](https://2e.aonprd.com/Rules.aspx?ID=2355), [disruption](https://2e.aonprd.com/Rules.aspx?ID=2342), [occupancy](https://2e.aonprd.com/Rules.aspx?ID=2360), [knockout](https://2e.aonprd.com/Rules.aspx?ID=2324), [dying and heroic recovery](https://2e.aonprd.com/Rules.aspx?ID=2325).

## S3 encounter matrix

All eight completed routes start healthy. These fights use the existing warpriest and its reviewed rank-1 spells, bow fighter, and selected melee builds against dogs or opposing fighters.

| Encounter ID | Tactical situation | Required interaction evidence |
|---|---|---|
| `s3_long_lane_crossfire` | On a 15×5 map, a mixed party faces dogs at 60 and 65 feet. | Bow range penalties are 0 and −2; distinguish intervening-creature cover from range. Hits and misses spend one arrow each. Save a pending shot without changing its distance, costs or check, then close and finish. |
| `s3_cover_lane_rotation` | A melee ally initially stands between a bow fighter and elite dog. | Lesser cover adds 1 AC; moving the ally removes it. Divine Lance also observes applicable cover while the intervening creature does not block line of effect. Keep MAP distinct. |
| `s3_rescue_under_pressure` | Dogs knock out the mixed party's melee fighter. | Two-action Heal ends dying/unconscious and adds wounded once, preserving prone and dropped weapon. Save, Stand, retrieve and rejoin combat. Verify ordinary versus font slot ownership. |
| `s3_stabilize_then_touch` | A mixed party stabilizes its knocked-out melee fighter before healing later. | Stabilize leaves 0 HP, wounded 1 and unconscious/prone. Save that state; later one-action touch Heal rolls 1d8 with no +8. Recover equipment and finish. No damage during the stable-zero interval. |
| `s3_emanation_edge` | On a 15×5 map, injured allies and an elite dog are near the caster; another dog is 35 feet away. | Three-action Heal shares one 1d8 across injured living allies/enemy in 30 feet, with explicit caster inclusion. Outside target is unchanged; slot paid once and no two-action +8. Continue combat. |
| `s3_void_against_finesse` | Warpriest and melee allies face a rapier fighter and elite dog. | Surviving Void Warp critical failure gives enfeebled 1: Dex rapier attack stays +9, Strength damage falls to 0; carried longsword Strength attack falls +6→+5. Save effect and verify expiry. Rapier/Vicious Swing critical rolls deadly d8 after ordinary doubling. |
| `s3_guided_reaction` | Guided Fleet fighter reacts to an opposing fighter's movement. | Guidance applies to Reactive Strike, survives a saved Hero reroll, then cannot benefit another check. Reaction ignores MAP; Guidance immunity blocks immediate reapplication. |
| `s3_interrupted_preparation` | An injured warpriest casts beside an opposing rapier fighter. | Critical reaction disrupts two-action Heal after actions and selected slot are spent. Save the nested choice; no healing occurs. Later cantrip use spends no slot; mixed actions finish the fight. |

Applicable reviewed sources: [shortbow](https://2e.aonprd.com/Weapons.aspx?ID=437), [ranged attacks](https://2e.aonprd.com/Rules.aspx?ID=2288), [cover](https://2e.aonprd.com/Rules.aspx?ID=2372), [line of effect](https://2e.aonprd.com/Rules.aspx?ID=2382), [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554), [Stabilize](https://2e.aonprd.com/Spells.aspx?ID=1689), [Void Warp](https://2e.aonprd.com/Spells.aspx?ID=1745), [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549), [Divine Lance](https://2e.aonprd.com/Spells.aspx?ID=1498), plus S2 health and reaction sources.

## Ownership

| Slice | Files and responsibility |
|---|---|
| S2 content and movement/weapon tests | New S2 content module, all eight setups, and the first four complete encounter tests. |
| S2 reaction and recovery tests | Separate test module for the remaining four S2 scenarios. |
| S3 content and range/rescue tests | New S3 content module, all eight setups, and the first four complete encounter tests. |
| S3 healing/effect tests | Separate module for emanation and void/finesse scenarios. |
| S3 spell-reaction tests | Separate module for Guidance on reactions and interrupted preparation. |
| Shared test helpers | Small checked command/choice/save helpers with finite limits and meaningful failure tests. |
| Central integration | Explicit catalogue registration, supported map admission, terminal access, focused catalogue test, README, STATUS and AGENTS. |
| Supervisor | Plan, scenario matrix, assignments, current work log and measured run usage. |

Stage modules build their few new definitions from existing immutable definitions; they do not duplicate complete sheets or import the central catalogue. Shared engine behavior has one integration owner. No new importer, package registry, or test framework is needed.

## Required evidence

Each scenario states its roster, starting circumstances, intended interaction, expected observable milestones, meaningful save point, and legitimate fight outcome. All sixteen must run through the public Python engine without editing hidden state or resetting progress. Representative terminal runs will check that the same choices remain playable.

Shared test defaults cap each encounter at 160 commands, 40 choices, 12 rounds and 2,000 events; cases may use smaller explicit bounds. The longer mixed-pack case explicitly allows 50 choices after its measured 45-choice route. Unexpected choices or exhausted dice fail visibly. These are test limits and do not modify game rules.

Use focused tests during implementation; run the complete interaction collection and existing suite at integration. Independent review will play a selected set with alternate choices and verify the applicable source rules. Record completion, command/round bounds, timing, memory, and process cleanup separately from the encounter count.

## Accepted evidence

- **Complete encounters:** all sixteen use public commands, finite dice/choices, meaningful save/load and a real outcome. All promised matrix milestones were independently checked.
- **Broader play:** four independent alternate routes finish, covering flanking, movement reactions, interrupted healing, and Void Warp/finesse. They are alternate runs of existing setups, not four additional encounters or endurance evidence. The authored mixed-pack route previously completed eight rounds and 104 commands.
- **Integration:** the five scenario modules pass 18 tests in 0.41 seconds (0.625 seconds including the wrapper). The full suite passes 211 tests in 0.69 seconds (0.912 seconds including its wrapper).
- **Memory:** the interaction collection peaks at 47,923,200 bytes (45.70 MiB) child RSS. Full-suite memory is unavailable: macOS blocked the timer's system query after pytest passed. The suite was not repeated just to recover that metric.
- **Terminal:** representative new shortsword and long-range setups execute actions and Save → Load → Quit. Existing full terminal encounter regressions also pass in the full suite.
- **Bounds:** shared helpers cap commands, choices, rounds and events; the deliberate limit-failure test passes. Process cleanup and the modular testing cadence are part of the working model.

## Running the checks

Use a single named test while changing its script, or run its small module:

```sh
.venv/bin/python -m pytest -q tests/test_s2_interaction_encounters.py
.venv/bin/python -m pytest -q tests/test_s2_interaction_recovery.py
.venv/bin/python -m pytest -q tests/test_s3_interaction_encounters.py
.venv/bin/python -m pytest -q tests/test_s3_interaction_effects.py
.venv/bin/python -m pytest -q tests/test_s3_interaction_reactions.py
```

Append `-k <case-name>` to select a scenario. The five files together are the interaction integration set. The ordinary repository-wide `pytest -q` run belongs at the broader integration/handoff checkpoint, together with representative terminal play and memory measurement. Do not repeatedly launch it while a single scenario is still being corrected.

## Execution and cleanup

Follow the [working model](04-delivery-and-checks.md): small reusable helpers, bounded output and command counts, synchronous test runs, no combinatorial expansion, and attributable-process checks when workers finish and before handoff.

## Decisions

No new user decision is currently required. The earlier stable-zero damage ruling remains pending and does not authorize an implementation choice here.

**Closed implementation defect:** the pending reaction validator now accepts its valid spell parent. Independent public reproduction saves/loads the nested Hero choice, then resolves critical disruption with the Heal slot and actions spent once and no healing or willingness prompt. The complete interrupted-preparation fight, independent alternate route, and full-suite integration all pass.

**Accepted encounter-ending policy:** a team loses when it has no conscious living combat-capable actor. Its unconscious actors stay in the saved state and can still be healed while a conscious ally keeps the fight active. This is a documented GM encounter-outcome choice, separate from the pending stable-zero damage rule. The same purpose-specific predicate now governs ending and save validation, while general dead/defeated semantics used by other rules remain unchanged. Focused tests and independent replay verify nonlethal victory and rescue while an ally remains active.
