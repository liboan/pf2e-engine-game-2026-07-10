# Dim targeting for skills and items

## Decision and status

Connect the remaining selected actions to the existing visibility check. Keep a single ordinary/low-light observer rule and literal target location; do not introduce a perception framework. Astra completed the source/code review. The selected skill and Runic connections are delivered, independently played and integrated; the contracts below describe their supported limits.

**First public checkpoint:** the `trip` selection in `tests/test_dim_skill_targeting.py` passes real target-failure and target-success paths with a saved pending targeting choice. Failure emits no Trip skill check, leaves two actions and commits the attack count once. Success continues to the real skill check and applies prone. Other skill outcomes and Runic item targeting are not yet accepted by this checkpoint.

The review corrected an earlier report: **skill handlers lacked a dim guard** and proceeded directly to skill resolution. The clock owner first added an atomic unsupported guard. The delivered skill connection now replaces that guard for supported actions; the external Runic item guard was subsequently replaced by the verified item connection.

## Delivered skill connection

Eight new cases in `tests/test_dim_skill_targeting.py` join recovery, ordinary skills and Assurance for **39 focused passes**; compilation passes. Shared targeting/Hero continuation now covers Trip, Grapple, Assurance, Feint and Demoralize. Tests cover saved pass/failure and reroll, separate skill outcomes, one-time MAP, Guidance preservation, fixed Assurance without an Athletics die, old Grapple retention, attempt-based Demoralize immunity and Scoundrel's saved free Step. Escape remains unchanged. The later combined review below adds an independently completed skill encounter.

The continuation gains `attack_count_committed` and `targeting_failed`; the worker reports no save-version change. Newly saved Assurance exposed a prior validation bug: its intrinsic proficiency breakdown must be validated as a fixed check rather than a d20 breakdown. Both check parsers now handle that distinction. The temporary Refocus rejection expectation was updated for the new supported behavior. Command: `PYTHONPATH=src pytest -q tests/test_dim_skill_targeting.py tests/test_recovery_refocus.py tests/test_skill_actions.py tests/test_assurance.py`. No full suite was run for this slice; the test process exited.

No new P0/P1 decision is required. The user delegated routine GM judgment; the interpretations below are explicit.

## Shared order

[Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62) requires DC 5 to target with attacks, spells or other effects. [Light](https://2e.aonprd.com/Rules.aspx?ID=2401) includes objects. Use the acting observer's vision and the target's current position.

1. Validate legality, range, weapon/hand requirements, action availability and Assurance eligibility before commitment.
2. Prepare the underlying skill context using the attack count before this attempt. Do not draw the skill die or consume Guidance.
3. Commit one action. For Trip/Grapple, commit the attack count and consume the applicable one-use melee Feint opening once. Escape continues preserving Feint, as the user ruled.
4. Resolve the targeting flat check and its separately saved Hero reroll.
5. Failure ends the targeting attempt without an underlying skill roll, skill-degree consequences or Guidance consumption.
6. Success resumes ordinary Guidance, skill check, any separate skill Hero choice, and outcome. [Assurance](https://2e.aonprd.com/Feats.aspx?ID=5121) replaces only the skill check; targeting still rolls and can have its own Hero choice.

## Action-specific outcomes

- **Trip/Grapple:** a failed targeting check causes no prone, damage, new hold, weapon-drop option or target retaliation. Preserve an existing hold until its ordinary expiry/termination. This is the chosen interpretation: the [Grapple failure entry](https://2e.aonprd.com/Actions.aspx?ID=2376) applies to the Athletics check, which was never made.
- **Demoralize:** a committed failed targeting attempt creates the ordinary actor-to-target ten-minute immunity but no frightened condition. This is the chosen reading of [immunity regardless of result](https://2e.aonprd.com/Actions.aspx?ID=2395). Its auditory trait does not remove creature targeting.
- **Feint:** targeting failure gives no exposure or off-guard result. Preserve [Scoundrel's free Step](https://2e.aonprd.com/Rackets.aspx?ID=8) with the required agile/finesse melee weapon: the benefit depends on using Feint. Save the actual failed-targeting provenance; never fabricate a Deception failure to unlock the Step.

These distinctions follow the same principle as the repaired Blood Magic case: target failure need not remove a benefit granted to the acting character.

## Runic Weapon

**Runnable implementation checkpoint:** the held/ground item gate now passes **56 focused regression checks**, with compile/diff clean. It reuses the targeting Hero continuation with `target_id=None` and saved `spell_target_item_id`, supports unattended ground weapons, and validates exact identity/location through save/load. A saved flat 5 applies one item effect; a saved flat 4 leaves one action/two slots after committed casting and creates no effect. Refusal/disruption never draw the flat check; bright/low-light and documented self-held bypasses remain. The temporary unsupported guard was removed. The later combined review and terminal/integration closure below complete this assignment.

Preserve [actual spell eligibility](https://2e.aonprd.com/Spells.aspx?ID=1658), touch range, two actions and one-minute duration, within the admitted longsword/shortsword content. Resolve exact item identity and location: a held weapon uses its holder's position; a ground weapon uses its ground position. Reject missing, duplicate, worn/stowed, ineligible or unreachable items before costs.

The existing self-held bypass is retained as an explicit local convention; the light rules do not themselves state that exemption. Otherwise the caster's vision controls targeting, regardless of the wielder's vision.

Commit the cast/source, obtain existing willingness when applicable, resolve manipulation/reactions, then revalidate the original item and wielder before the item-targeting check. Refusal/disruption does not draw a targeting die. Failed targeting spends committed costs but creates or refreshes no enhancement.

## Bounded implementation ownership

One Luna worker owns these connections after the current clock/Refocus writer releases core:

- `skill_actions.py`: resumable pre-skill targeting, choice handling/validation, Demoralize tail and extracted Scoundrel Step tail.
- `encounter.py`: shared targeting preparation/choice handling, Runic item resolution and item-aware saved validation; remove temporary guards only for connected routes.
- Model/persistence: reuse existing command/check/item fields. Add a committed-attack marker only if needed; strict saved choices must not infer a rolled skill result that does not exist.

Known traps from the review: `_resolve_saved_check` currently increments attacks when rolling, so precommit must not double-count; shared targeting validation expects a creature and must recognize unattended item identity; the current Scoundrel Step validator expects resolved Deception and needs an explicit failed-targeting alternative.

## Combined independent play and repair

Sol's `tests/test_caster_recovery_play_review.py` adds three healthy-start completed public sequences. With recovery, skill, Warpriest Light, dim Runic and earlier Runic review cases, the bounded selection passes **28 in 0.21 seconds**. It retains Demoralize immunity, Scoundrel Step and source-turn duration counterexamples.

The dim skills encounter saves failed targeting before fixed Assurance, preserves Guidance, commits MAP once, then uses Guidance on a later attack and reaches victory. The dim Runic encounter resolves willingness, saves failed DC 5 targeting, rerolls through an explicitly granted initial Hero Point, uses an actual enhanced 2d8 Strike, reaches victory and expires the effect through Refocus without restoring slots. The Hero grant is a labeled legal session fixture, not a new class implementation.

The review found one P1: using Guidance rebuilt a Strike continuation without `concealment_checked`, causing a second targeting check. The same Runic implementation owner copied that marker; the named case, **57 repair regressions**, and all three independent encounters pass. The initially shortened file link was only a typo: the canonical modified `encounter.py` is inside this project; no outside file was changed.

Sources checked include [Assurance](https://2e.aonprd.com/Feats.aspx?ID=5121), [Runic Weapon](https://2e.aonprd.com/Spells.aspx?ID=1658), [Guidance](https://2e.aonprd.com/Spells.aspx?ID=1549) and [start-of-turn duration tracking](https://2e.aonprd.com/Rules.aspx?ID=436). All checks exited synchronously; host enumeration was unavailable in that review. The same owner subsequently completed terminal evidence and integration; its usage record is now closed.

## Evidence to retain

Focused cases cover flat 4/5 and saved rerolls, separate Hero stages, Guidance preservation, MAP once, Assurance without Athletics dice, Feint consumption, Demoralize immunity, existing Grapple, saved Scoundrel Step, bright/low-light bypass, item identity, refusal/disruption and tampered saves.

At most two complete interaction encounters should demonstrate the coherent family: a dim skills fight with real Feint/maneuver/MAP/Assurance and Step; and a dim Runic fight with saved willingness/targeting, actual enhancement/Strike, item movement and expiry. Use healthy starts and real public commands; do not count private-state probes as completed play. Reuse existing valid encounter evidence where it already covers an unchanged branch.

## Accepted integration and working-model comparison — first outcome

The terminal regression `test_terminal_dim_runic_saves_item_concealment_then_applies_effect` proves saving at the real dim item targeting check, loading, keeping the result and applying the enhancement. `.venv/bin/python -m pytest -q tests/test_runic_weapon_terminal.py` passes **3 tests**. The exact Guidance repair regression is `test_dim_assurance_target_save_preserves_guidance_and_commits_map_once`.

The repeatable `.venv/bin/python tools/integration_checkpoint.py` now exists and passes **668 tests**, compilation and diff checks. Pytest 2.97 s; measured child 3.276 s; peak RSS **67,747,840 bytes / 64.609 MiB**. Accepted catalog 48 setups/32 creatures; runtime staged 7/3; save version 17. The existing 100-sample benchmark reports command/query p95 0.205 ms and menu p95 0.264 ms, peak 28,180,480 bytes / 26.875 MiB. The scoped process audit found no lingering engine tests, benchmarks or probes.

This outcome straddled adoption of the updated operating model. It retained **one implementation owner, zero owner changes, one independent-review repair**. The pre-implementation read-only hold lasted **2m29s** (11:00:35–11:03:04 UTC). The previously reported 1h58m14s interval preceded this assignment and is not evidence of a dependency wait for this outcome. Exact first feature-check latency is unavailable: the owner's 5m23s figure belonged to an earlier admission-fix assignment; a test's 0.09s runtime is not delivery latency. Do not substitute either.

Implementation release to final handoff: **31m50.156s**, 11:03:04–11:34:54.156 UTC. Including the read-only preparation: **34m19.156s**. Accounting closed at 11:36:15; that later administrative close is not the delivery finish. These are observed run intervals, including review and handoff, not model compute time.

| Attributed run | Input tokens | Cached input (subset) | Output tokens |
|---|---:|---:|---:|
| Runic read-only preparation | 847,162 | 596,992 | 5,457 |
| Runic implementation, review repair, terminal and integration | 15,810,157 | 15,478,016 | 61,535 |
| Combined Sol review of recovery, skills and Runic | 8,973,380 | 8,787,712 | 23,350 |
| Total of these runs | 25,630,699 | 24,862,720 | 90,342 |

The review row covers all three families, so it is not solely Runic cost. Earlier design and foundational implementation are recorded separately in the ledger and are not included in this scoped total. Monetary cost is unavailable. The implementation run includes 119 requests and one compaction; internal checkpoints and ordinary fixes did not open new usage runs. Historical preparation fragmentation is preserved rather than rewritten. Scene carry is the second outcome for this comparison.
