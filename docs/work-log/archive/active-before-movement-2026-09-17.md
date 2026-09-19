# Archived recovery snapshot before movement-control work

This is historical state. Use [ACTIVE](../ACTIVE.md) for current ownership, counts and next actions.

# Current work and recovery checkpoint

**S3i content expansion remains active.** Build the sixteen representative Player Core 1/2 classes at level 1, then level 2, then have Astra review demonstrated opportunities to simplify the implementation. The engine is local Python with a terminal. Recent work is uncommitted after `eacf9ac` on `engine-only`.

## What works

**Accepted level-1 classes: 9 of 16.** Fighter, Barbarian, Cleric, Rogue, Sorcerer, Champion, Swashbuckler, Investigator and **combat-only Ranger**. Preserve the eleven accepted Barbarian builds. Bard, Monk and Wizard have accepted staged capabilities; no level-2 progression is accepted.

**Latest accepted integration: 995 tests.** Test-reported4.13s / measured4.479s; peak75,563,008 bytes (**72.063 MiB**); compile and diff checks clean. Catalog: **55 admitted setups /39 creatures;16 staged setups /6 creatures; save version17**. The older command/menu p95 benchmark was not remeasured.

Ranger is available through stable IDs `ranger_precision_level_1` and `staged_ranger_precision_bow` (the historical setup name remains compatible). Supported combat includes Fleet30ft, finesse fist+7 with Strength damage+1, Hunt Prey, Precision, shortbow/Hunted Shot, range, arrows, reactions/Grabbed and saved/terminal play. Seek, Track, Forager and exploration are recorded non-gating sheet facts, not an implementation queue.

Monk's accepted staged behavior now includes Powerful Fist, fist/fist and kama/kama Flurry, kama Trip's drop-or-prone choice, and horizontal Quick Jump with saved reactions/knockout interruption and terminal play. High Jump/vertical terrain remains unsupported; full-build admission awaits the user's scope choice. Maestro Anthem/Lingering remain staged while Counter Performance decisions are pending. Wizard has accepted staged Force Bolt, Force Barrage, Breathe Fire, Arcane Bond, rank1 Shield and Spell Substitution, plus Telekinetic Projectile, Electric Arc, Frostbite, Enfeeble and Runic Body. Actual saved/terminal/recovery play is evidenced. Five remaining book cantrips, legal preparation/sheet closure and class admission remain unfinished.

[Combat and mobility evidence](paired-strike-boundaries.md) · [Bard evidence](bard-first-play-work.md) · [Investigator evidence](investigator-remaining-grants-work.md).

## Active work and authorized queue

| Next outcome | Owner and recovery pointer | Evidence, dependency and next action |
|---|---|---|
| Persistent damage and three spells — canonical gate authorized | Terra/high `/root/wizard_direct_spells_owner`; session `01a0addb-fa80-7b00-a2ad-cf16b236b00b`; run `persistent-spells-group-2026-09-17` | Source/public review clean; owner/direct/review75tests/0.43s, compile/diff clean. Actual Ignition terminal choices and healthy final-enemy→affected survivor recovery→save/refocus/next-scene pass. Owner is sole authorized canonical runner, followed by attributable process audit and exact symbol/limit handoff. No whole-group acceptance before that evidence. [Contract](wizard-spellbook-work.md) |
| Persistent spell group — review complete, retained for gate repairs | Sol/high `/root/bard_lingering_review`; session `01a0ad10-032b-7250-b0e6-7087e79af342`; run `persistent-spells-review-2026-09-17` | Independent10tests/0.16s; requested combined68/0.52s. Source-checked repairs: legal5+1cantrips, per-condition defenses/physical bleed, spell modes and terminal, saved profile/deadline/cursor/Hero/reaction validation, lethal persistent cleanup. Reviewer corrected two fixture/assertion errors. No outstanding production defect; accounting remains open until canonical acceptance |
| Monk High Jump — P1 scope choice pending | Retained owner `/root/monk_kama_flurry`, session `01a0ad05-6791-7ce1-a152-639160f8df8f`; reviewer `/root/fresh_sol_message_probe`; [evidence](paired-strike-boundaries.md) | Horizontal slice integrated and its runs closed. Structured question asks whether horizontal-only jumping suffices for the bounded build or High Jump must precede admission. Do not assume an answer; no whole-Monk admission yet |
| Counter Performance — P1 decisions pending | [Source findings/questions](bard-first-play-work.md) | Await natural-die substitution and Hero Point/fortune timing decisions. Independent other-class work proceeds; Read Aura remains declared unavailable |
| Mixed-type paired defenses — P1 decision pending | [Existing source boundary](paired-strike-boundaries.md) | Same-type sequences are accepted. No convention for mixed damage against shared broad resistance is authorized |

The five direct spells are accepted at995tests, with completed healthy encounter/terminal evidence and no remaining attributable test processes. All three direct-group run boundaries are closed, including the earlier incomplete owner. Persistent implementation/review is ready for its now-authorized sole canonical gate; no conflicting runtime editor is active. Movement control and final legal preparations/sheet grants follow. Monk/Bard scope questions remain pending.

## Accepted preparation contract and next-book constraints

Astra's source-backed next outcome is a saved ten-minute Spell Substitution using existing supported rank1 spells. No rule-choice blocker was identified. The unspent-only rule is an inference combining [Spell Substitution](https://2e.aonprd.com/ArcaneThesis.aspx?ID=9) with [Prepared Spells](https://2e.aonprd.com/Rules.aspx?ID=2223): a prepared spell is expended by casting, and substitution grants no restoration exception.

- Keep `PreparedSlotState` authoritative. Slot ID/source/rank/cantrip constraints are immutable; spell ID and spent state are live. Validate against a small accessible book and curriculum ledger. Use Force Barrage, Breathe Fire and Sure Strike; Shield remains its existing cantrip. This is not a complete printed book.
- Thin start/advance/interrupt procedures keep one actor/slot/original/replacement/elapsed record. Start leaves the old preparation intact; advance charges actual elapsed seconds; completion alone changes the spell. Save300+load+advance300 completes at600. Interrupt180 preserves the original and discards progress; restarting needs600more. Incompatible activity requires explicit interruption.
- Ordinary Breathe Fire→Sure Strike is legal; curriculum Force Barrage→Sure Strike rejects atomically; curriculum Force Barrage→Breathe Fire is legal. Reject spent/absent-book/inaccessible/wrong-rank/type/unchanged requests without time/dice mutation. Source: [Wizard](https://2e.aonprd.com/Classes.aspx?ID=39), [Battle Magic](https://2e.aonprd.com/ArcaneSchools.aspx?ID=22).
- Reuse the existing Bond representation: eligible completed-cast slots are spent and cannot be swapped. Replacement becomes eligible only after it is actually cast. Add `_record_arcane_bond_completed` to the supported Sure Strike completion branch. Daily preparation may reprepare the current legal choices and clear history/refresh expenditure with existing rest/day gates; substitution itself refreshes nothing.

Implementation pointers: `wizard.py` procedure/validation; `wizard_content.py` and `CreatureDefinition` book/thesis/constraints; `CreatureState` pending record; `family_casting._prepared_casting_snapshots` Wizard-specific live-slot validation; persistence actor/prepared state; thin Encounter downtime APIs using `_downtime_group_error`/`_advance_elapsed_time`; terminal and focused tests. Preserve fixed validation for other casters. Latest focused owner/reviewer selection passed51tests/0.33s, including `tests/test_wizard_substitution.py` and `tests/test_wizard_substitution_review.py`. Environment remains projectroot, `.venv/bin/python`3.11.1, pytest`src`, bounded30s command. The legal book also includes ordinary Force Barrage: curriculum grants add it to the owned spellbook and do not prevent use in ordinary slots.

Preserve accepted Shield fields `magic_shield_expires_at_start` and `shield_recast_available_at_seconds`; damage flags `DamageResolution.shield_block_magic`/`ShieldBlockRecord.magic`; v17defaults/validators; positive post-IWR damage gating. Magical Block clears the active marker and sets600seconds suppression without creating inventory HP. Zero damage offers no reaction; declined Block followed by knockout retains timed AC but removes reaction availability. [Shield](https://2e.aonprd.com/Spells.aspx?ID=1671).

Preserve the accepted staged Wizard actor `wizard_battle_magic_level_1_staged`, setup `staged_battle_magic_wizard_vs_two_guard_dogs`, automatic Force Bolt, allocated same-recipient Barrage, shared-roll cone basic saves, saved multi-recipient health/reaction continuation and bonded-item recasting. No new spell effects, character-builder UI, general downtime framework or full Wizard admission are authorized by this preparation group. Full book counts and broader choices remain explicitly unfinished.

## Working model

- Root coordinates and authors its plan/work-log documents; workers inspect sources/code and execute the engine. Terra/high implements, Sol/high selectively reviews actual play, Astra/high investigates substantial rules/design questions.
- Keep related grants in one bounded outcome with one retained owner and frequent internal executable checks. Do not close/re-register for a passing subfeature or ordinary repair. Avoid speculative frameworks and whole-class rewrites.
- Call native tools directly. `send_message` queues information; it does not wake idle peers. Use `followup_task` for authorized review activation, repairs and dependency responses requiring action. A submitted call alone is not proof of handling. No app cross-task worker reports.
- Keep focused checks bounded, one synchronous pytest per worker; no watch/background/xdist. Reuse the existing canonical integration command at coherent checkpoints, with one broad runner. Audit attributable descendants; never kill by name or touch an unclear shared service.
- Root uses the five-minute execution heartbeat, inspects once and ends when no immediate decision remains. No wait loops, repeated status pings or routine acknowledgements. The scheduled-cycle and one-time all-worker synchronization checks are already complete; do not repeat them. [Historical operating evidence](operating-workflow-checkpoint.md).
- The rejected Ranger field-play proposal is closed and outside the queue. Combat-only scope applies to its acceptance. Preserve pending user decisions rather than inferring permission from elapsed time.

## Latest acceptance and cleanup

The direct group is accepted: Telekinetic Projectile, Electric Arc, Frostbite, Enfeeble and Runic Body. Independent review passed7cases/0.14s and the initial combined selection71/0.31s. Four production repairs stayed with the replacement owner: Projectile range/Bulk; attack-trait/MAP/Sure Strike and pending validation; excess rank1 preparation; saved allied Runic Body willingness. The Projectile profile is explicitly limited to the authored staff.

`test_electric_arc_ends_a_healthy_continuous_encounter` verifies one shared4+4 roll, ordinary failed saves,8damage once per full-health dog, both defeated, blue victory and Wizard14HP. `test_bounded_terminal_selects_electric_arc_and_two_distinct_recipients` finishes through the actual terminal,35input/260line bounds, excluding the first recipient from the second menu. Independent reopened acceptance passed13tests/0.15s after correcting the owner's natural1 fixture that implied critical rather than ordinary failure. The Wizard's eventual16HP sheet correction remains separately outstanding; this is staged spell evidence, not full-class admission.

First canonical integration found five Divine Lance save/reload regressions. Owner repaired the exact pending attack identifier (Divine Lance requires its name; Projectile requires none), independently reviewed18tests/0.20s. One justified rerun passed995tests, metrics above. Final process audit found no attributable pytest/Python descendants; no cleanup required.

Spell Substitution is accepted against the finite rank1 book. Five independent public/save cases plus owner cases exercise atomic combat/spent-slot rejection, saved599→600 and300+300 completion, interrupted restart, incompatible Refocus/rest/next-scene rejection, source constraints and absence of the book. Actual substituted Sure Strike casting, saved Bond recasting, healthy next-encounter completion, daily preparation retaining current choices and bounded terminal play pass. One source-led production repair remained with Terra: ordinary slots may prepare the book's curriculum-granted Force Barrage. No required example was missing at independent acceptance.

The prior substitution checkpoint passed982tests on its first attempt, with compile/diff clean and preserved Shield regressions. The owner's escalated scoped audit found only the audit shell/search process; no test/integration descendants required termination. Full legal Wizard book, higher-rank substitution and general curriculum selection UI remain unfinished or outside this slice; Wizard is still staged.

Shield's owner finished182focused tests/0.69s; independent review added4cases/0.10s, combined81/0.30s. Two production repairs remained with that owner: suppress magical Block when post-defense damage is zero, and preserve the hand-free timed spell through knockout when Block was declined. Actual AC thresholds/stacking, expiry, physical and spell/magical damage, saved multi-recipient continuations, terminal, scene/refocus clock and exact600s cooldown are exercised. Ordinary nonmagical nonphysical damage does not qualify. Rank1/Hardness5 only; no future heightening, magical shield HP or general defense rewrite.

The prior Shield canonical gate passed970tests on its first attempt, compile/diff clean. The synchronous harness exited. After sandbox denial of `ps`, a narrow escalated read-only process audit found no attributable pytest/integration-checkpoint descendants; nothing needed termination.

Prior staged Wizard group passed957tests after a frozen spell-roster expectation repair; independent review had found empty-cone Bond history and curriculum/ordinary slot provenance defects, both repaired by its retained owner. Ranger's prior935-test admission and Monk's horizontal slice remain accepted within their stated limits.

## Usage and delivery

Latest closed direct-spell group, including incomplete first owner: **37,051,050 input /36,225,152 cached input /101,942 output**,243requests,1compaction,3runs. Cached input is a subset; dollar cost is unavailable.

| Assignment | Model/effort | Input | Cached input | Output | Requests / compactions |
|---|---|---:|---:|---:|---:|
| Initial direct-spell owner, incomplete/reassigned | Terra/high |2,339,777|2,167,296|4,394|15 /0|
| Replacement implementation | Terra/high |24,367,519|23,849,472|69,698|163 /1|
| Independent review | Sol/high |10,343,754|10,208,384|27,850|65 /0|

One owner change followed two premature final reports. Replacement delivered the first coherent63-test checkpoint, completed ordinary review repairs, added missing complete-play evidence and repaired one canonical regression before a justified rerun. No external dependency wait was reported; exact time-to-first-check and delivery elapsed remain unavailable. All three boundaries are closed. Persistent handoff closed: Astra/high1,094,905input /1,037,696cached /6,097output,11requests,no compaction; three existing public analogues passed0.11s, no edits/retained processes. Persistent implementation/review boundaries were registered before dispatch/reservation and are open.

Prior closed Spell Substitution group: **11,971,333 input /11,541,504 cached input /46,562 output**,102requests,2compactions.

| Assignment | Model/effort | Input | Cached input | Output | Requests / compactions |
|---|---|---:|---:|---:|---:|
| Spell Substitution implementation | Terra/high |9,624,908|9,277,952|31,640|78 /1|
| Spell Substitution review | Sol/high |2,346,425|2,263,552|14,922|24 /1|

Spell Substitution had no owner change, one ordinary review repair and no canonical repair/rerun. First executable check intentionally failed at the absent public API, then the coherent implementation passed28focused tests before broader45/51-test checks. No explicit dependency wait was reported; precise time to first check and elapsed delivery are unavailable. Both assignments are closed. The legal-book handoff also closed: Astra/high3,213,214input /3,112,832cached /14,251output,23requests,1compaction; three public analogues passed0.10s, no edits/retained jobs.

The first direct-spell implementation run closed by reassignment, not acceptance; its cost is included in the completed three-run group above. The premature stops were a delivery interruption, not a demonstrated rules/dependency blocker.

Prior closed Shield group: **25,408,447 input /24,923,392 cached input /67,480 output**,167requests,1compaction.

| Assignment | Model/effort | Input | Cached input | Output | Requests / compactions |
|---|---|---:|---:|---:|---:|
| Shield implementation | Terra/high |20,010,207|19,562,240|57,528|137 /1|
| Shield review | Sol/high |5,398,240|5,361,152|9,952|30 /0|

Shield's owner was retained through two review repairs; no canonical rerun. Its initial shared-snapshot dependency was explicitly released; the single startup diagnosis was satisfied by the coherent executable report. Exact first-probe, delivery and dependency durations are unavailable. Preparation handoff closed: Astra/high1,366,965input /1,327,872cached /4,806output,8requests,no compaction; two prerequisite tests passed and no processes remained.

Earlier closed Wizard combat group:39,528,858input /38,728,960cached /96,542output,235requests,1compaction. Ranger/Monk:21,436,471 /21,079,040 /60,002,149requests,2compactions. Original Wizard handoff:1,340,180 /1,278,720 /4,873; Shield independence check:885,231 /877,056 /1,277. Preserve the [ledger](agent-runs.json); never recollect a closed reused run or split ordinary repairs into new assignments.

## Other limits and settled decisions

- Wizard self-damage resolution remains unsupported; do not imply it from the accepted target/area tests.
- Positive damage to a stable unconscious PC already at zero HP is unsupported. Pre-first-turn reaction/Surprise Attack uncertainty remains outside accepted scenes.
- Tumble currently supports one enemy and one-square ground traversal; no broad alternate-movement, large-creature or multi-enemy traversal claim.
- Escape preserves Feint. Rest eligibility is explicitly declared; preparation does not simulate sleep, natural healing or fatigue.
- Fundamental runes above the character's level remain explicitly granted test equipment, not ordinary starting purchases.

## Index

[Selected roster and delivery plan](../plan/06-class-and-content-expansion.md) · [Working guidance](../plan/04-delivery-and-checks.md) · [Work-log index](README.md) · [Usage ledger](agent-runs.json) · [Combat/mobility evidence](paired-strike-boundaries.md) · [Historical operating evidence](operating-workflow-checkpoint.md).
