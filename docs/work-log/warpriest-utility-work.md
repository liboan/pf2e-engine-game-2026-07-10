# Warpriest Light and alternate preparation

## Decision and status

Use the already-working Light cantrip in place of the optional unimplemented Read Aura preparation. Keep the planned legal Sure Strike alternate because it exercises a common combat rule. Astra verified this scope reduction against the selected build and sources; no mandatory class, ancestry, background or deity grant requires Read Aura. This is the adopted S3i scope, not a proposal awaiting approval.

Read Aura was a prepared placeholder with combat rejection; its exploration procedure never worked. Read Aura and Identify Magic are **deferred optional content**, outside the selected roster's acceptance requirements. Their prior source research is [archived](archive/warpriest-utility-before-cantrip-simplification.md), not a delivery backlog. This avoids building object-knowledge, secret-check, misinformation and retry machinery solely for that optional spell.

## Legal Light substitution

Level-1 clerics choose five common divine cantrips, and Light qualifies. Iomedae grants Heal font and access to Sure Strike, Enlarge and Fire Shield, without imposing Read Aura. [Cleric](https://2e.aonprd.com/Classes.aspx?ID=33), [Light](https://2e.aonprd.com/Spells.aspx?ID=1585), [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285).

Replace only `cantrip_read_aura` with `cantrip_light`. Preserve the Warpriest definition/setup identity, statistics, four other cantrips, two ordinary Heal slots and four font Heal slots. Reuse the real Light handler; add no new identification system. Update preparation/terminal expectations and test the actual prepared-caster source, repeatable casting without slot expenditure, illumination and saved decisions/orbs. Shared Light tests already cover the common controls.

The actual Human/Skilled Human Warpriest now declares `vision="ordinary"` and prepares Light. A test-only vision substitute was removed: `tests/test_warpriest_light.py` uses the production definition. Public cases prove dim-to-bright illumination, saved willingness/dice, repeat cantrip casting without Heal-slot expenditure, and the exact legal preparation. Older saves containing this build's former Read Aura preparation are **strictly rejected**; no migration is claimed.

Validation: **51 passed** across the new Warpriest, casting integration, S3 terminal and spell tests; **15 passed** across shared Light orb-cast and terminal tests. Diff checks pass. Preparation expectations and README's support statement were updated. No core encounter/model/persistence changes were needed. This verifies the Light substitution, not the outstanding Sure Strike alternate or whole caster milestone.

## Sure Strike and a legal preparation

**Accepted:** Sure Strike's fixed Warpriest alternate, saved fortune and terminal path pass both owner checks and independent combined play. The owner reports 8 focused cases and 686 full-suite passes; Sol's later 14-check selection and five Angelic admission checks pass without P0/P1 or core repair. Owner and review usage runs are closed. The next bounded assignment is ordinary Angelic CLI admission; current ownership stays in ACTIVE. All implementation/source reading and verification remain delegated.

Add a fixed alternate Warpriest definition/setup: replace `ordinary_heal_2` with rank-1 Sure Strike, keeping one ordinary Heal, four font Heals and the existing five cantrips. Preserve the original build. Later preparation may select these named legal sets; it need not accept arbitrary slot rewriting. Iomedae grants Sure Strike, prepared normally as a divine cleric spell. [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285), [Cleric](https://2e.aonprd.com/Classes.aspx?ID=33).

Cast costs one action and the ordinary slot. Its concentrate/fortune traits do not create a manipulate reaction. The next actual attack roll before turn-end rolls two d20s and uses the better; preserve both dice, consume once, ignore negative circumstance attack modifiers and that attack's concealed targeting check. MAP, status penalties and the defender's cover/Nimble Dodge AC benefits remain. Grabbed manipulation and targeting for other spells still apply. Hidden creatures remain outside current scene admission. [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709), [errata](https://paizo.com/pathfinder/faq).

**Local unused-expiry ruling:** the ten-minute immunity starts when the attack consumes the spell. An unused spell expires at turn-end without a benefit or cooldown. The printed “then” follows the attack benefit; unused expiry is not separately specified. Keep this interpretation visible and test it.

Classify actual attack rolls, not just the attack trait: Strike, Divine Lance and unarmed-attack Escape qualify; Athletics/Acrobatics Escape, Trip and Grapple do not receive or consume Sure Strike. Assurance(Athletics) remains a fixed skill result, separate from the attack-roll fortune effect. [Attack rolls](https://2e.aonprd.com/Rules.aspx?ID=2288), [Fortune](https://2e.aonprd.com/Traits.aspx?ID=612), [Assurance](https://2e.aonprd.com/Feats.aspx?ID=5121).

## Implementation traps and bounded evidence

`SavedCheckContext.fortune_used` already persists, but the reroll helper currently checks only `reroll_used`; Strike/Divine Lance also have separate Hero paths. Suppress and reject every Sure Strike Hero reroll, including forged saves. Reuse existing casting permission, concrete item-location and clock helpers; one core owner handles encounter/model/persistence/check/spell/skill/content changes. Terminal remains presentation only.

Proposed Sure Strike public sequence: an alternate Warpriest in dim light makes one attack, casts Sure Strike, then attacks. With frightened 1 and nonlethal intent, +6 −5 −1 = 0: remove the −2 circumstance penalty, retain MAP/status, and use 3/18 = 18 with no targeting die or Hero reroll. Retain saved pre-roll Guidance/Nimble Dodge and actual defender choices where reachable.

Full implementation and completed play remain required before acceptance. The Light preparation change and Sure Strike are separate bounded assignments.

## Owner executable checkpoint

Owner handoff at **2026-09-16 13:07:34 UTC** identifies `WARPRIEST_C_SURE_STRIKE` and `SURE_STRIKE_WARPRIEST_SETUP`, `family_casting.begin_cast`, `Encounter._resolve_cast`, `_consume_sure_strike_for_attack`, `_roll_strike`, `_roll_divine_lance` and `_resolve_saved_check`. Persistence retains fortune dice/consumption, active effects and absolute cooldowns. Terminal `_choose_cast_inputs` exposes no-target casting.

`tests/test_sure_strike.py`: **8 passed**; `test_sure_strike_terminal_cast_and_attack_path` exercises the public Cast → save/load → Strike route. The owner reports both supplied dice retained, the better face used, negative circumstance penalties/concealment ignored, MAP retained, Hero rerolls suppressed, used-cast 600-second cooldown and unused turn-end expiry without cooldown. Adjacent recovery smoke: **18 passed**.

Pre-review full suite: **686 passed in 3.03s**. The existing final integration command reports measured pytest time **3.325s**, peak **68,190,208 bytes / 65.031 MiB**, compile/diff checks passing, runtime catalog 49 setups/33 creatures, staged8/3 and save version17. No benchmark emitted; no task-owned background jobs remained. These are owner reports, not independent acceptance or new whole-class coverage.

Sources used by the owner: [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709), [attack rolls](https://2e.aonprd.com/Rules.aspx?ID=2288), [Fortune](https://2e.aonprd.com/Traits.aspx?ID=612) and [Iomedae](https://2e.aonprd.com/Deities.aspx?ID=285). Sol now owns only `tests/test_caster_fortune_preparation_review.py` and source/runtime inspection, leaving repairs to Luna. The review also assesses the remaining concrete CLI-admission work for the selected Angelic Sorcerer and Warpriest package; future classes remain out of this review.

The app's progress display was stale while raw request records advanced. Delegated liveness and report recovery preserved the owner and read only session metadata/progress messages. Their recorded usage is respectively **1,087,330 / 1,043,456 / 7,409** and **763,130 / 749,312 / 4,611** input/cached/output tokens. Neither diagnostic verified code or warrants claiming the spell accepted. The implementation run stays open through independent review fixes.

## Independent acceptance and caster readiness

Sol retained two cases in `tests/test_caster_fortune_preparation_review.py`:

- `test_sure_strike_survives_assurance_then_preparation_restores_it_for_next_fight`: a healthy-start public fight saves failed dim targeting before fixed-result Assurance Trip. Sure Strike remains armed, with no cooldown. The following Strike uses supplied natural 1/20, retains MAP −5, bypasses concealment, suppresses Hero rerolls and wins. Declared rest and one-hour group preparation expire the cooldown, restore the slot and preserve HP/wounded/gear; duplicate-group and repeated-preparation calls reject atomically. Scene B begins at **3,601 seconds** and ends with a second Sure Strike victory.
- `test_sure_strike_cast_does_not_trigger_reaction_and_saved_nimble_keeps_ac`: real Warpriest/Fighter/Thief definitions prove the concentrate-only cast leaves the adjacent Fighter's reaction intact. Saved Nimble Dodge raises AC to20 before the two-die attack. After consumption, an ordinary nonlethal attack again uses one die, MAP and the −2 circumstance penalty.

`.venv/bin/python -m pytest -q tests/test_caster_fortune_preparation_review.py tests/test_sure_strike.py tests/test_daily_preparation.py` → **14 passed in 0.22s**, exit0. Separate selected Angelic admission evidence across Halo, Fear/Flee, Runic, Light and Refocus/save-load → **5 passed in 0.15s**, exit0. No P0/P1 or engine repair was found. Tests exited synchronously; no background work launched; OS enumeration was restricted.

Sol source-checked [Sure Strike](https://2e.aonprd.com/Spells.aspx?ID=1709), [Fortune](https://2e.aonprd.com/Traits.aspx?ID=612), [Daily Preparations](https://2e.aonprd.com/Rules.aspx?ID=2575), [Sorcerer](https://2e.aonprd.com/Classes.aspx?ID=62), and [Angelic bloodline](https://2e.aonprd.com/Bloodlines.aspx?ID=20), along with Assurance, Nimble Dodge and Reactive Strike in its detailed report.

The Warpriest/Sure Strike package is already in ordinary catalog and CLI selection. The selected Angelic Sorcerer's grants, repertoire, focus/spontaneous recovery and chosen spells have public evidence. Remaining ordinary-CLI work is packaging: promote the exact definition, necessary item-capable Fighter ally and one curated setup, update false staged/pending notes, and execute a real `main(["play", admitted_id])` save/load smoke. Offensive undead Heal remains an explicit unsupported boundary, not a blocker for the selected living-party path. This promotion is assigned separately to the retained Luna owner.

Closed run usage (cached input is a subset of input):

| Run | Input | Cached input | Output |
|---|---:|---:|---:|
| Sure Strike implementation and handoff | 28,968,252 | 28,457,728 | 69,311 |
| Combined fortune/preparation and admission review | 5,116,018 | 4,871,552 | 25,769 |

The implementation used197 requests/two compactions; review39 requests/one compaction. No owner change or independent-review repair occurred. Diagnostic usage is recorded separately above; monetary cost is unavailable. The full686 run preceded the two newly added review cases, which passed in the focused review; the next admission integration will include them together. Do not claim an unrun full688 result.
