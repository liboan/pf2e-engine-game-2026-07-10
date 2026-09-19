# Investigator: first playable attack sequence

## Current result

The selected Investigator can store a die with Devise a Stratagem, save and load it, then use it for an attack. This **bounded sequence is accepted** after independent complete-fight review and repairs. The full class remains staged until its remaining required features work. Six of the sixteen selected level-1 classes are accepted; this work does not increase that count.

The supervisor records worker reports here without reading implementation or rules sources or running verification. [ACTIVE](ACTIVE.md) is the current ownership and acceptance index.

## Scope and ownership

Luna/xhigh `/root/investigator_first_play` retained ownership of the action, stored state, attack integration, persistence, terminal path and tests through ordinary review repairs. Sol/high `/root/caster_recovery_play_review` independently ran bounded Python encounters and checked applicable sources. These assignments are now closed. The same Luna worker has a separately registered next assignment for Forensic healing.

The first sequence covers Devise, eligible attack substitution, Strategic Strike precision, target and turn limits, fortune restrictions, deterministic dice and saved choices. The selected build's remaining Recall Knowledge/Known Weaknesses, Lead/Clue In and Forensic healing behavior are not delivered by this sequence. Unsupported invocations must remain explicit.

## Executable checkpoints and review findings

The owner reported a saved d20 of 14 used by an actual Strike as 14+7=21, with no additional attack die and the stored result consumed. Sixteen focused checks and 715 full-suite checks passed before independent review. The reported damage result was wrong, and those passes do not establish acceptance.

The independent reviewer reported:

1. **Intelligence affected weapon damage incorrectly.** Devise substitutes the attack modifier only. Stored-14 shortsword attacks with damage rolls 3+5 produced 12 instead of 8; a saved Nimble Dodge path with rolls 3+4 produced 11 instead of 7. Repair the runtime and earlier expectations.
2. **Unused state survived its expiry.** Cycling from Devise through both opponents and back to the Investigator left the unused stratagem stored. Ignoring it during attack resolution is insufficient for the literal saved-state contract; clear it at the next turn start.
3. **The chosen sheet was incomplete.** Human / Skilled Human / Detective needs Underworld Lore and Streetwise, a replacement skill for duplicate Society, the heritage's skill, a named first-level ancestry feat, and five additional languages. Correct the selected grants without advertising unimplemented actions.

The reviewer confirms the partial Investigator setup is staged. Earlier final file links omitted the project directory; the owner subsequently confirmed every actual edited file is inside the project and no outside duplicate exists. This was a reporting error.

### Repair checkpoint

The independent reviewer reports **six passing review cases** after the production repairs. The combined selection initially retained two failures in the owner's tests: an expiry assertion held an obsolete creature reference across state replacement, and a terminal input script expected the old inflated damage to finish the fight. The reviewer identifies these as fixture drift, not new production defects. The retained owner is correcting them before final integration. This checkpoint still does not establish complete class support.

## Accepted evidence and execution pointers

Staged setup: `investigator_forensic_vs_two_guard_dogs`. Public sequence: `DeviseStratagem("investigator_guard_dog_a")`, save/load, then `Strike(..., attack_id="shortsword", use_intelligence=True)`. Corrected deterministic probe: d20 14, attack 14+7=21, damage 7 (weapon3 plus precision4), targetHP1, stored die consumed. The terminal path works for the staged fixture; ordinary CLI catalog admission remains withheld.

The six independent cases in `tests/test_investigator_play_review.py` cover:

- Healthy two-dog victory with saved Devise, an ordinary attack on the other target, selected-target agile MAP−4, enemy turns, another Devise and natural20 critical damage.
- Mandatory stored-die use while separately declining Intelligence; precision is then absent.
- Stored natural1 without Hero reroll, followed by an ordinary natural20 MAP attack with a saved Hero decision.
- A real saved Nimble Dodge choice before the stored die is consumed.
- Once-per-round enforcement, literal next-turn expiry, and atomic rejection of skill/free/Known Weaknesses modes without changing state or dice.
- Legal selected sheet grants and staged catalog placement.

Owner/reviewer combined: **18 passed**. Owner's focused owner/review/catalog/helper selection: **40 passed**. Canonical integration: **723 passed**, measured pytest **3.374s**, peak **68,386,816 bytes (65.219MiB)**, compile/diff exit0. Accepted catalog51/36, staged8/2, save17. No new command/menu benchmark was reported.

The owner reports corrected probe PIDs57685 and57688 exited0; obsolete probe57680 exited1 on a stale assertion, and all three were absent afterward. The reviewer used only synchronous pytest and reported no yielded/background sessions. Independent audit at **08:00:24PDT September16** found no Python/pytest, project-command, Justice probe or Chrome/Chromium leftovers; zero terminations. Shared MCP/Node services remained untouched.

Source-checked by Sol: [Devise a Stratagem](https://2e.aonprd.com/Actions.aspx?ID=2813), [Investigator and Strategic Strike](https://2e.aonprd.com/Classes.aspx?ID=59), [Hero Points](https://2e.aonprd.com/Rules.aspx?ID=2333), [fortune](https://2e.aonprd.com/Rules.aspx?ID=2263).

## Remaining class work

Pursue a Lead, Clue In, Skill Stratagem, lead-aware free Devise, Known Weaknesses Recall Knowledge, Streetwise procedures, Battle Medicine and Forensic Acumen remain explicitly unsupported at this checkpoint. Next is bounded Forensic healing; a parallel read-only Astra task supplies the narrow knowledge contract from existing research. These are genuine new assignments after acceptance, not reassignment of unfinished repairs.

## Closed usage

Counts below are per assignment from the deterministic collector; cached input is included in total input. Dollar cost is unavailable.

| Assignment | Model / effort | Input | Cached input | Output | Requests / compactions |
|---|---|---:|---:|---:|---:|
| First sequence delivery and ordinary repairs | Luna / xhigh | 36,883,486 | 36,172,544 | 117,535 | 257 / 2 |
| Independent actual-play review | Sol / high | 8,992,878 | 8,662,400 | 20,788 | 54 / 0 |
| Independent process audit | Luna / xhigh | 303,133 | 298,496 | 609 | 2 / 0 |

No implementation-owner change occurred. Explicit dependency waits covered Justice shared-file work and its terminal resource repair. Time to first executable check and exact elapsed delivery duration are not reconstructed here; those values remain unavailable. The actual checkpoints and repaired defects above are preserved rather than inferred from token totals.

Use the existing [source contract](investigator-runtime-work.md) and [execution handoff](investigator-execution-handoff.md). They are design and API pointers, not proof of delivered behavior.
