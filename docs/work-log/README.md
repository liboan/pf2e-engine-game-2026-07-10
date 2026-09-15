# Work log

## Current summary — 2026-09-15

**S1–S3 and S3i are delivered: 16 added complete encounters, eight for S2 and eight for S3, and 21 catalogued setups overall.** All sixteen interaction routes and four independent alternate routes are accepted. The full repository suite passes **211 tests in 0.69 seconds**. The [scenario matrix](../plan/05-interaction-encounters.md) explains which rules each fight exercises.

The added content is a Fleet shortsword fighter, a rapier fighter, and elite Guard Dogs, using the existing spells and shared mechanics. Two 15×5 maps exercise bow range and healing-area edges. Tests exposed and fixed two shared defects: a saved reaction inside casting could not load, and a team of unconscious opponents could leave combat running forever. Both fixes have independent continued-play evidence.

Tests now use small reusable helpers, finite commands/choices/dice/output, frequent focused selections, and less frequent full integration. The interaction collection measured **45.70 MiB peak child RSS**. The full-suite run passed, but its timer could not query memory under the macOS sandbox; no full-suite memory figure is claimed for this increment. The earlier runaway-process cleanup and bounded terminal-output fix remain in place; the exact historical cause of multi-gigabyte growth was not reproduced.

The game uses fixed reviewed setups and manual control of all sides. Damage to an unconscious, stable PC already at 0 HP remains explicitly unsupported pending the earlier ruling. S4 is not active. The completed project work is committed on `engine-only`.

The supervisor maintains the plan and log from delegated findings. All completed and superseded subagent runs have measured usage in the ledger. Final documentation checks passed. The independent process audit found no leftover test/probe processes; the later integrator could not list processes under its sandbox, but waited for and reaped its own test wrapper. All workers reported their test commands exited.

## Index

- [Project summary and plan index](../../README.md)
- [Latest project state](../../STATUS.md)
- [Product and interface](../plan/01-product-and-interface.md)
- [Engine and content](../plan/02-engine-and-content.md)
- [Rules and stages](../plan/03-rules-and-stages.md)
- [Delivery and checks](../plan/04-delivery-and-checks.md)
- [Completed interaction encounter work item](../plan/05-interaction-encounters.md)
- [Per-run usage ledger](agent-runs.json)

## Work history

### 2026-09-15 — Branch and commit completed

- **Authorization:** create a new branch and commit the completed local engine, tests and documentation. The requested name “engine only” is represented as `engine-only`, because Git branch names cannot contain spaces.
- **Delivered:** a Luna/xhigh worker created `engine-only` from the current checkout and committed 81 project files, preserving all 27 archived baseline payloads. The cached diff check and targeted credential-pattern scan passed; environments and caches were excluded. The worker reported a clean checkout. The existing 211-test integration result remains current; no implementation changed during delivery.
- **Accounting:** root collected the completed worker's final usage and includes this final log update through an amendment to the same delivery commit.

### 2026-09-15 — S3i closed

- **Delivered:** eight new S2 and eight new S3 encounters, 21 catalogued setups, three additional reusable content definitions, two larger maps, and fixes for saved spell reactions and nonlethal encounter endings. All sixteen routes, independent alternatives, and the 211-test suite pass.
- **Working model:** five small scenario modules share bounded helpers. Focused checks run during iteration; one passing broad run satisfies an integration checkpoint until a new change or failure warrants another. Idle/completed-worker process checks and exact-ownership cleanup are part of normal supervision.
- **Documentation:** 41 internal links across 11 active Markdown files pass, all 27 archived baseline payloads remain byte-identical, ledger JSON parses, and the final diff whitespace check passes. Root subsequently refreshed only log text and final usage values without changing link targets.
- **Processes:** the independent audit found no pytest/PF2e/probe leftovers. The final integrator's process listing was denied; its own test wrapper was synchronously waited/reaped, and all completed workers reported exited test commands. No process was signaled in this final pass.
- **Accounting:** all delegated runs, including the superseded route-mapping work and reused-agent follow-ups, have final input/cached-input/output counters. S4 has not started; no commit or merge was made.

### 2026-09-15 — Full integration passed

- **Single broad run:** pytest reports 211 passed in 0.69 seconds; wrapper wall time is 0.912 seconds. The timing wrapper then exits 1 because macOS denies its clockrate query; pytest itself succeeds. It produces no RSS/footprint figures, and the suite is not repeated solely for memory telemetry.
- **Memory evidence retained:** the independent five-module interaction collection measured 45.70 MiB peak child RSS. The earlier 179-test full-suite memory result remains historical, not a measurement of this expanded suite.
- **Documentation:** product, engine/content, stages and encounter matrix now describe the completed increment. README/STATUS/AGENTS and final links/archive/process checks belong to the integration worker; root owns this log and per-run usage.

### 2026-09-15 — Independent interaction review accepted

- **Accepted:** all sixteen matrix scenarios; no remaining omitted interaction or P0/P1 defect found. Content was checked against current rule sources, including Fleet, both new weapons, elite adjustment, Pack Attack and existing spells.
- **Combined execution:** five modules pass 18 tests (16 complete encounters plus two content checks) in 0.41 seconds; bounded wrapper wall time is 0.6245 seconds and peak child RSS is 47,923,200 bytes (45.70 MiB). This measures that collection, not the whole repository.
- **Alternate play:** four complete routes with different actions/order/dice also pass on the final core. Catalog admission, both core corrections, the stable-zero rejection, and the helper's bounded failure path pass their targeted checks.
- **Lifecycle:** review commands exited and were reaped; no pytest/PF2e/independent-route process remained. The sole full-suite run is now released to the integration owner.

### 2026-09-15 — All sixteen encounter scripts pass

- **Final two:** saved Guidance on Reactive Strike retains its bonus through an actual Hero Point reroll, consumes it before the fighter's next check, rejects an immune recast without changing state, and finishes the fight. Interrupted two-action Heal spends its chosen slot/actions, saves the critical reaction's nested choice, produces no healing, and continues through a slot-safe cantrip and victory.
- **Evidence:** the new reaction module passes two tests in 0.08 seconds. Its author reports no remaining pytest process. All sixteen authored routes now have focused passing evidence.
- **Next:** the separate reviewer checks the final two and combined five-file collection. The integration owner then runs the full suite once with memory measurement and closes entrypoint documentation/process checks. Root maintains the plan and measured run ledger.

### 2026-09-15 — All S2 cases accepted; final route planning moved to targeted play

- **S2:** all eight new encounters are independently reviewed and passing. The recovery/reaction module passes four tests, including exact knockout initiative reordering and preservation of the stabilized fighter through later turns.
- **Remaining:** two S3 spell-reaction scripts. Their Luna owner had reported no authored case or running test after route mapping; the mapping run was interrupted, measured and marked superseded. A separate Sol/high targeted-play author now owns the same new file. No completed code is discarded.
- **Separation:** the existing independent reviewer remains separate from the new test author. The sixteen-case target and final integration requirements are unchanged.

### 2026-09-15 — Emanation and finesse cases completed

- **Focused result:** both cases in the effects module pass and finish actual encounters. Their processes exited synchronously.
- **Emanation evidence:** the outside dog is first injured to 7 HP and remains at 7 after Heal. The included injured recipients gain the shared d8 result of 4, one ordinary slot is spent, font slots remain untouched, and a saved inclusion choice resumes correctly. A later legal movement reaction is explicitly declined before the fight ends.
- **Finesse evidence:** Void Warp, Dexterity versus Strength effects, expiration, rapier deadly/Vicious Swing, nonlethal PC knockout with a conscious ally, and final outcome are all exercised.
- **Remaining:** the Heroic Recovery case is adding an exact initiative-order assertion; the two separate spell-reaction scripts and final combined checks remain active.

### 2026-09-15 — Central integration complete; final spell cases reassigned

- **Core/terminal completion:** the central slice passed 31 focused shared-rule checks, six catalog checks and two terminal notices. README, STATUS and AGENTS now describe the outcome policy and modular test/process cadence. No full suite has run yet; its processes all exited.
- **Parallel closeout:** the effects worker keeps its already-authored emanation and void/finesse cases. The freed integration worker now owns a separate two-case file for guided reaction and interrupted preparation, which were still unwritten. No edits are discarded or shared between owners.
- **Collection:** the sixteen scenarios now span five small test modules. This changes ownership and selection commands, not the number or acceptance requirements of the encounters.

### 2026-09-15 — Shared fixes accepted; twelve new routes complete

- **Core checks:** 31 focused tests pass in 0.16 seconds across the new persistence/outcome cases and existing S2 reaction/encounter/S3 core tests. Catalog checks remain six passes. One legacy stable-zero rejection case now keeps a conscious ally; its unsupported-damage and dice-preservation assertions remain.
- **Independent confirmation:** seven selected persistence/outcome/nonlethal-passage checks pass, including valid spell-parent continuation, malformed-parent rejection, nonlethal winner save/load and rescue with an active ally. The six catalog checks independently pass too.
- **Scenario progress:** seven S2 and five S3 new routes have completed. Remaining work is heroic last stand, emanation edge, guided reaction and interrupted preparation, plus combined execution and final measurements.
- **No new ruling:** the fixed outcome policy is separate from the still-unsupported stable-zero damage branch.

### 2026-09-15 — First S3 group accepted; alternate independent fights pass

- **S3 first group:** all four range/cover/rescue/stabilization fights and their content check pass. Review corrections prove a real hit and miss each spend an arrow, range/cover/MAP are separate, Divine Lance resolves through creature cover without a slot, and Step clears the lane. Two revised cases independently pass in 0.17 seconds.
- **Independent alternatives:** four distinct public-command routes complete under a 20-second outer timeout. S2 flank/reaction variants use 11 and 15 commands; S3 interrupted-Heal and void/finesse variants use 17 and 16. Each finishes in round one after its selected interaction and save/load checks; these are alternative runs, not additional scenarios or endurance evidence.
- **Remaining case progress:** reaction relay and contested weapon handling now finish, with saved nested choices and the new incapacitation outcome. Void/finesse also completes while preserving a knocked-out PC as non-dead. Other case work remains active.
- **Lifecycle:** the ~12:58 PDT independent audit found no stale pytest, route-driver or PF2e probe processes. Shared app-owned services were retained.

### 2026-09-15 — Nested spell-reaction save defect independently closed

- **Fix:** the pending reaction validator now recognizes its valid spell parent; serialization and the save schema did not need redesign.
- **Independent replay:** the exact public repro saves and loads at the nested Hero prompt, then resolves critical disruption. The cleric has 12 HP and one action remaining, the ordinary Heal slot stays spent, and no healing or willingness prompt occurs. The bounded command exits successfully.
- **Remaining acceptance:** the full interrupted-preparation route, coherent encounter outcomes, remaining scenario milestones, and final integrated measurements.

### 2026-09-15 — S2 milestone review corrections pass

- **Stronger evidence:** Fleet explicitly records Vicious Swing counting as two attacks before reset. Weapon switching compares second-attack shortsword −4 with longsword −5 and later shortsword −8. Flank changes now cause hit → miss → hit and corresponding damage changes.
- **Checks:** the three changed nodes pass in 0.10 seconds; all five owned module tests pass in 0.12 seconds. Every process exited synchronously; the worker is complete and its follow-up usage is separately measured.
- **Still active:** spell-parent save correction, coherent nonlethal outcome handling, the remaining eight reaction/effect encounters, and final independent/integration verification.

### 2026-09-15 — First S3 group passes; nonlethal outcome policy accepted

- **S3 evidence:** five tests pass in 0.23 seconds, including all four range/cover/rescue/stabilization fights. Stabilization uses one ordinary dog so its explicit recovery sequence finishes within existing limits; the earlier slow two-foe script was a test-route issue, not an engine playability defect. Rescue still has two opponents.
- **Outcome defect confirmed:** stable nonlethal opposing PCs were skipped forever but kept their team active, with no supported way to finish. The accepted GM policy ends combat when a side has no conscious living combat-capable actor. Unconscious participants remain in state and are healable while an active ally keeps combat going. This does not decide damage at stable zero.
- **Correction ownership:** the central worker handles consistent ending/save validation after its spell-parent save fix. Generic dead/defeated semantics for other mechanics must remain unchanged.
- **Review refinements:** first S2 tests are adding explicit attack-count, non-agile second-attack and consequential flank assertions. The separate reaction/recovery worker was interrupted for missing progress reports, confirmed no live processes, and resumed the same four-case task with edits preserved.

### 2026-09-15 — Four S2 routes complete; spell-reaction save defect assigned

- **S2 evidence:** five module tests pass in 0.11 seconds, including all four movement/weapon/flank/Pack encounters. Mixed-pack completed in 104 commands, 45 choices, eight rounds and 207 events; its explicit choice cap was tightened from 120 to 50. All processes exited cleanly.
- **S3 progress:** range and cover cases pass; rescue/stabilization reach their milestones and are correcting a blocked movement path in their completion sequence. The effects worker has exercised Void Warp/finesse/deadly milestones but is still finishing that fight.
- **Independent P1 defect:** a saved Hero choice inside Reactive Strike against two-action Heal cannot load because validation fails to recognize the spell parent. The central owner now owns a narrow persistence correction and a public save/continue regression. This is an implementation failure with clear required behavior, not a user ruling request.
- **Separate review:** whether stable nonlethal opposing PCs should count as defeated remains under examination. Current lethal routes do not establish that end-of-fight policy is correct. No stable-zero damage behavior is being guessed.
- **Final-layout terminal:** a 65-foot shot now shows +7 versus AC16, reflecting range and cover; Save → Load → Quit passes with bounded capture and no lingering process.

### 2026-09-15 — First new full encounter passes

- **Fleet route:** the new four-diagonal assault passes as a complete public-command fight. It saves/restores the 30-foot Stride, uses the remaining two actions for Vicious Swing, and defeats both dogs through later turns.
- **Focused command:** `pytest -q tests/test_s2_interaction_encounters.py -k fleet_four_diagonals` reports 1 passed, 4 deselected in 0.07 seconds. The development test processes exited cleanly; no core defect was found.
- **Parallel review:** the independent reviewer is authorized to play four alternate full routes now that catalog and terminal smoke pass. Running all sixteen authored tests remains gated on their local completion.

### 2026-09-15 — New terminal paths exercised

- **Actual runner:** the shortsword scenario completed initiative, Inspect, weapon selection and Strike, then Save → Load → Quit. The larger-map scenario completed the same flow with a target at 65 feet and the expected −2 bow range penalty.
- **Bounds:** the S3 flow used 18 inputs, 73 output entries and 27,915 characters, below its 512-entry/100,000-character limits. All commands exited synchronously and temporary saves were removed.
- **Independent check:** the initial far dog is offset from the nearer dog's line, so AC15 without cover is correct. The scenario owner will legally move it into that line to demonstrate range and lesser cover together. No core cover defect was found.
- **Remaining:** complete the four test modules and independent alternate routes, then run the single full integration/memory check.

### 2026-09-15 — Source review clear; test writing split into four-case slices

- **Independent source check:** Fleet/General Training, shortsword, rapier, elite adjustment and unchanged Pack Attack agree with the new definitions. No P0/P1 issue found. The rapier owner is adding a missing source/currency sheet note.
- **Progress:** all sixteen setups and their content are authored and registered. Complete scenario tests were not yet written at this checkpoint. To shorten the remaining critical path, four Luna owners now each implement four cases in non-overlapping modules.
- **Lifecycle audit:** independent inspection at 12:34 PDT found no active repository pytest or pf2e Python process. App-owned Node/MCP/Playwright services with unrelated ownership were retained. No review-owned persistent child exists.
- **Acceptance remains unchanged:** all sixteen complete outcomes and their milestones must pass before broad review; registration alone does not close the stage.

### 2026-09-15 — Expanded catalog and map checks pass

- **Implemented:** the catalog now contains 21 setups, preserving the original five and adding sixteen. Existing terminal commands accept the new setup IDs. Two 15×5 maps are admitted while altered/ad hoc setups remain rejected.
- **Focused evidence:** six catalog tests pass in 0.06 seconds, including both larger-map save/load round trips and terminal name routing. The complete scenario tests remain in progress; registration alone is not interaction evidence.
- **Review:** one Sol/high reader is checking the new content and helper behavior against sources while implementation finishes. Broad execution waits for both eight-case scenario modules to pass. The integration owner alone will run the full suite at the later checkpoint.

### 2026-09-15 — Shared helper ready; lifecycle checkpoint clear

- **Helper:** checked public commands, explicit choices, actor inspection, save/load checkpoints and final outcome checks are available to both scenario owners. Defaults cap 160 commands, 40 choices, 12 rounds and 2,000 events.
- **Focused verification:** two meaningful helper tests pass under a 45-second CPU and 60-second wall limit. No full-suite rerun was needed for this isolated slice.
- **Lifecycle:** helper commands exited inline. Design readers launched no persistent work; the central owner's read/edit commands also exited inline. No unused attributable process remained to stop at this checkpoint.
- **Active work:** eight S2 and eight S3 scenario/content tests plus central catalog/map/terminal integration. All dependent workers received the completed matrix and helper path.

### 2026-09-15 — S3i design handed to implementation

- **Accepted scope:** sixteen distinct scenarios, eight per stage, plus three new reusable definitions: Fleet shortsword fighter, rapier fighter and elite Guard Dog. Two 15×5 maps exercise bow range and Heal emanation boundaries; exact catalog admission remains.
- **Evidence targets:** every new scenario starts healthy, reaches named interaction milestones, saves/restores meaningful state, and continues to a winner. Shared default limits are 160 commands, 12 rounds and 2,000 events. Expected arithmetic remains in scenario tests.
- **Ownership:** four Luna/xhigh slices own stage content/tests, shared helpers, and central integration. The designer and test investigator completed without launching tests or persistent processes. No new P0/P1 decision was found; existing stable-zero damage remains excluded.
- **Reviewable plan:** [scenario matrix and sources](../plan/05-interaction-encounters.md) now replaces the design placeholder. Independent actual-engine/source review follows the integrated collection.

### 2026-09-15 — S3i encounter expansion started

- **Authorized result:** about 8–10 additional encounters each for S2 and S3. Initial target is eight each, with distinct interactions and useful in-scope low-level content.
- **Delegation:** Astra/high designs the scenario/content matrix and sources; a parallel Astra/high reader defines small modular test helpers and lifecycle checks. Luna/xhigh implementation and periodic Sol/high actual-engine/source review follow those contracts.
- **Working model updated:** frequent focused checks, broader full-encounter integration less often, bounded execution/output, and attribution-based cleanup when workers become idle/complete and at integration/handoff. No recurring automation or background monitor.
- **Boundary:** the stable-zero damage ruling remains pending. This stage does not silently choose it or widen into S4 mechanics.

### 2026-09-15 — Encounter coverage inventory completed

- **Question:** how many playable encounters exist, which rules they exercise, and which rule interactions have been demonstrated.
- **Assignment:** one read-only Astra/high inventory of shipped setups and existing evidence, distinguishing complete play from isolated checks and alternate seeds of the same scenario. No implementation or scope expansion.
- **Inventory:** 3 terminal encounters (synthetic duel; two melee fighters versus two dogs; mixed melee/bow/warpriest party versus three dogs), plus 2 catalogued Python diagnostic setups (one fighter versus three adjacent dogs; opposing fighters). All five use open 7×5 maps.
- **Evidence:** 9 retained regression cases finish fights: 7 S1, 1 S2, 1 S3. Historical independent fights are additional runs of existing setups. The 179-test total includes focused rules and interaction checks; it is not an encounter count. No new tests or play sessions were run for this inventory.
- **Interactions:** public-command sequences cover nested reactions/Hero choices/save-load, Vicious Swing and MAP/critical knockout, bow ammunition/deadly/rerolls, Guidance through a saved reroll, enfeebled Strength damage with a Dexterity attack, shared Heal rolls/slots/willingness, and knockout → Heal → Stand → retrieve. Most are focused sequences; complete-fight coverage is narrower.
- **Gaps:** short S2/S3 victory regressions and limited map/monster variety. S2's two dogs cannot activate Pack Attack; the three-dog diagnostic setup supplies that threshold check. Long bow ranges are unexercised on the admitted map. Geometry and stacking checks do not establish complete-fight tactical coverage. Temporary independent harness evidence remains distinct from retained tests.
- **Outcome:** answered from the reader's findings and existing work-log evidence. S1–S3 delivery and completed memory cleanup remain unchanged.

### 2026-09-15 — Shared test-memory guard completed

- **Change:** one small test helper bounds dynamic S2/S3 terminal output at 4,096 entries or 1,048,576 characters. It raises before retaining excess output. Existing full-fight and detailed assertions remain; production rules and terminal code are unchanged.
- **Failure evidence:** repeated invalid S3 input and an S2 answer misrouted to an unresolved initiative choice stop at their test limits. Ordinary captures remain well below the defaults.
- **Regression evidence:** 18 focused tests and **179 full-suite tests pass**. The full run used a 90-second CPU limit and finished in 0.52 seconds wall time; peak RSS was 49,512,448 bytes (47.2 MiB), and peak footprint was 39,339,648 bytes (37.5 MiB). All commands completed synchronously without background work.
- **Closeout:** fresh checks found PIDs 82927, 83479, 77393 and 77416 absent, with no repository pytest process remaining. An older Python stdin process (76947, approximately 7 MiB RSS) was retained because its ownership by completed tests was unproven. `git diff --check` passed after the status/log update. All subagent runs are complete and measured; no S4 work is active.


### 2026-09-15 — One-time Node cleanup and independent memory review

- **Cleanup:** Playwright MCP PIDs 77393 and 77416 received SIGTERM and were verified absent. Attribution used their start time and process grouping relative to a completed source-review session. No Chrome/Chromium/headless process was present. Another pair (85571/85679) and generic Node/MCP services were retained because exclusive ownership could not be proven. The one-time pass is closed.
- **Guard review:** the S3 capture guard raises before retaining excess output; it neither truncates required evidence nor hides failed/incomplete play. Defaults are 4,096 output entries and 1,048,576 characters. Eight ordinary S3 captures peaked at 135 entries / 42,124 characters.
- **Independent evidence:** 52 focused terminal tests pass under a 15-second process timeout; every probe exited and was reaped. S1 finite-input tests remain bounded with outcome assertions.
- **Final correction:** one dynamic S2 capture had the same repeated-answer risk. The memory worker is sharing the small test-only helper with S2/S3 and adding a failing-input regression before the final full-suite/memory check.

### 2026-09-15 — Initial test-memory guard and measurements

- **Process attribution:** the reported PIDs were pytest runs of this repository's S3 terminal tests, parented by the app server. The implementation worker sent SIGTERM to those exact PIDs and immediately saw them gone. The later cleanup worker independently found them absent. Causal attribution between the signal and a concurrent natural exit is unavailable.
- **Change:** bounded S3 transcript capture fails loudly at line/character limits. A deliberately repeated invalid input proves the capture aborts quickly; normal assertions and complete-play tests remain. No production rules or terminal code changed.
- **Evidence:** 16 S3 terminal tests pass; 178 full-suite tests pass in 0.32 seconds. A controlled timed run measured maximum RSS 50,429,952 bytes (~48.1 MiB), peak footprint 40,240,832 bytes (~38.4 MiB), 0.56 seconds wall time.
- **Limit:** the old multi-gigabyte growth was not reproduced, so unbounded capture is a confirmed risk rather than a proven historical cause. An independent reviewer is checking the guard and related S1/S2 scripted-capture paths.

### 2026-09-15 — Cleanup scope and process status

- **Python status:** two fresh PID-specific checks found 82927 and 83479 absent; that cleanup run sent no signals. The initial implementation worker is being asked to report any earlier cleanup before resuming diagnosis.
- **One-time additional authorization:** identify closed/completed subagents and terminate their attributable orphan Node/Playwright/Chrome workloads. The dedicated cleanup worker owns that pass; active Codex/browser/plugin services and unrelated user processes are excluded.
- **Continued goal:** complete the bounded test-memory optimization and correctness/process verification, then finish the S3 delivery. No recurring monitoring or S4 expansion was added.

### 2026-09-15 — User-reported test memory pressure

- **Preserved S3 checkpoint:** enabled normal play; 177 passing tests; complete API and terminal fights; independent correctness and deterministic-save review accepted.
- **New report:** Activity Monitor shows Python PIDs 82927 and 83479 at approximately 11 GB and 9.6 GB, plus substantial swap use. This is a user observation, not yet a diagnosis of engine or test behavior.
- **Authorized work:** identify the processes, stop unused task-owned runs, and dedicate a scoped implementation/debug pass to reduce test memory without changing game correctness or weakening coverage. Verify process cleanup and before/after memory with bounded runs.
- **Outstanding:** root cause, fix, memory evidence, final regression pass, and updated usage accounting.

### 2026-09-15 — Final S3 admission and verification

- **Delivered:** S3 normal CLI is enabled; S1 and S2 remain available. README describes the fixed party/spells, manual menus, Python API, supplied dice, and scope boundaries.
- **Final checks:** 177 current tests; installed S3 startup with three initiative choices, Inspect and Quit; the README dice example; compilation; whitespace check; 35 local links/anchors across 11 active Markdown files. All pass.
- **Range scope:** altering S3 to a larger map is rejected because public setup must match a catalogued definition. No engine scope was expanded for the probe. Longer bow range arithmetic is source-reviewed, while public runtime evidence is limited to the admitted map; add a larger catalogue entry and boundary cases before offering longer shots.
- **Preserved:** 27 archive payloads plus their manifest; no commit or merge. All completed worker runs have final token counters.
- **Next:** the requested S1–S3 implementation is complete. Future work can address the pending stable-zero ruling or deliberately select an S4 increment.

### 2026-09-15 — Independent S3 runtime review accepted

- **Verdict:** admit S3; no P0/P1 rules/runtime defect found. The final engine-aligned snapshot passes 172 tests; 12 focused correction checks and the temporary boundary harness pass.
- **Complete play:** two public mixed-party fights with different seeds, routes, bow use, and spell choices finish normally in round two. The separate terminal review also completed a fight through normal menus.
- **Boundaries:** saved choices preserve dice and costs; bow ammunition and all six Heal slots exhaust correctly; refusal/rejection/query/exhaustion do not consume supplied dice; Guidance expires at a dead caster's next initiative slot; basic saves, enfeebled, cast disruption, and recovery transitions match reviewed sources.
- **Timing:** 500 representative S3 startup/initiative/Guidance/Divine Lance/choice sequences measured median 2.6444 ms and p95 2.8115 ms. Mean was 2.7535 ms, including one 39.7 ms scheduling outlier. These are small local sequences, not a claim about large encounters.
- **Final delivery:** the packaging owner enables S3, updates README, checks normal CLI/full suite and active links, and probes longer bow range boundaries if existing public setup dimensions permit them. The fixed S3 map itself uses the first bow increment.

### 2026-09-15 — Complete S3 terminal play passed

- **Played:** all three roles used legal terminal actions to defeat the three Guard Dogs in a complete encounter.
- **Choices:** actual runner tests cover Heal touch/ranged modes, ordinary/font slot selection, willingness/self-inclusion saves, and a saved target-owned Void Warp Hero choice. Earlier Guidance/bow/DL flows remain covered.
- **Correction:** spent Hero Points now display as zero, avoiding stale or missing resource information.
- **Evidence:** three focused terminal files pass 51 tests. This is a different selection from the earlier 53 content/terminal checks; the counts are not additive. S3 remains gated pending independent edge review.

### 2026-09-15 — S3 full-suite implementation checkpoint

- **Evidence:** 171 tests pass. Nine public S3 cases include all Heal modes, Stabilize, target-owned save/Hero choices, Guidance through a reroll, attribute-specific enfeebled behavior, and knockout → Heal → Stand → retrieve after saving at willingness.
- **Performance:** 500 actual startup/initiative/Guidance/Divine Lance/choice sequences averaged 2.4518 ms, range 2.3321–2.8619 ms, including command state-copy work.
- **Independent review:** a frozen snapshot will be played through complete and alternate mixed-party encounters and decisive new rule/save boundaries, with final median/p95 measurements. The terminal owner is completing the actual runner fight. S3 remains gated until that evidence closes.
- **Boundary clarified:** unsupported stable-zero targeting covers every positive damage kind, including nonlethal. README now matches the implementation; the proposed lethal-damage ruling remains pending.

### 2026-09-15 — S2 correction conditions closed

- **Accepted:** the independent S2 review conditions are satisfied. The latest reaction/encounter files pass 16 tests covering dead-only Pack Attack, legal four-diagonal movement at Speed 30 with save/load, and clearer fatal-recovery outcomes. Legal weapon stow/load was already corrected and verified.
- **Delivery:** the packaging owner enabled normal `play s2`; actual CLI startup, initiative choices and quit passed. README includes a verified deterministic-dice example; seven focused content tests pass. S3 stays gated until its own integration and review close.
- **S3 terminal evidence:** 53 focused content/terminal tests; actual Guidance, Divine Lance, and bow flows. The bow preserves its saved Hero choice, consumes one arrow, and reports doubled base damage plus its separate deadly die.

### 2026-09-15 — Simplicity audit

- **Verdict:** the implemented architecture fits the local playable-engine goal: ordinary Python records, direct rules, and bounded target options. The reviewer found no creature-name-selected combat behavior or speculative plugin framework.
- **Correction now:** save validation assumes the prototype movement speed and can reject a faster dog's legal diagonal movement. Core owns a conservative speed-aware fix and a public movement/save/load regression.
- **Keep scope:** explicit saved reactions, transactional dice/state, choice ownership, and health alternatives remain useful. Recovery-completion duplication can be cleaned up later; broad continuation refactoring is not an S3 prerequisite.

### 2026-09-15 — Independent S2 play review completed

- **Played:** a complete public duel with movement reaction, nested Hero Point choice, knockout, recovery reroll and death; an alternate complete fight used nonlethal fist and Vicious Swing. Both finished normally.
- **Verified:** 147 frozen-snapshot tests; saved choice and scripted-dice continuation; reaction timing and MAP; equipment/armor boundaries; nonlethal health; inconsistent saved-check rejection; stable-zero unsupported requests remaining atomic.
- **Conditional acceptance:** the remaining rules condition is the dead-only Pack Attack correction. Core owns its regression plus clearer bonus-die and fatal-recovery narration. The review does not establish additional conscious-ally restrictions.
- **Accounting:** this review and the completed S3 content/terminal run have final input/cached-input/output counters in the ledger.

### 2026-09-15 — S3 content and terminal checkpoint

- **Content:** the ranged fighter, Iomedaean warpriest, and mixed party versus three Guard Dogs are authored. Prepared cantrips and six rank-1 Heal uses have explicit provenance.
- **Terminal:** engine-offered casting modes, targets, slots, self-inclusion, Take Cover, ammunition, and sourced effects are represented. Ten focused new checks and 40 earlier content/terminal checks pass.
- **Core correction:** legal weapon stowing now has a passing public stow/save/load/draw regression. Independent review subsequently verified that regression and the fixed-armor action boundary. The review also requested explicit narration when recovery causes death.
- **Next:** complete casting and bow integration, exercise actual terminal play, and independently check the mixed encounter. S3 remains gated.

### 2026-09-15 — S2 implementation checkpoint; S3 started

- **Core evidence:** 147 tests pass; complete public PC duel and an alternate saved movement-reaction sequence pass. The alternate selects a nonlethal fist and continues the original movement.
- **Performance:** 100 actual S2 startup/initiative/Stride/Hero-Strike cycles measured 1.008 ms median and 1.161 ms p95. This is a multi-command sequence, not directly comparable to the earlier single-command baseline.
- **Corrections delivered:** selectable reaction attacks/intents, typed attack modifiers, nonlethal health integration, consistent saved checks/reaction context, unused-reaction lifetime, allied Strike legality, and early rejection of known stable-zero damage requests.
- **Independent review:** fresh snapshot passes 147 tests. Review found legal stow/save/load rejection, dead-ally Pack Attack qualification, and a bonus-die narration issue. Core owns the corrections. The dead-ally finding does not establish an unconscious-ally restriction.
- **S3 handoff:** a short architectural read mapped casting directly onto existing continuations. It identified shared check/health extractions and save invariants that need to distinguish spell action counts, basic saves, and deadly dice. Core and content/terminal S3 work are now active.

### 2026-09-15 — Actual S2 terminal flow passed

- **Player flow:** the real terminal runner completed initiative choices, Vicious Swing, reaction acceptance and decline, save/load at a reaction and its nested Hero prompt, and continued into round two without patching game state.
- **Evidence:** 13 S2 content/terminal tests and 27 S1 terminal tests pass. This is meaningful continued play, not yet a complete S2 encounter acceptance.
- **Correction:** the flow exposed an unused reaction being cleared at End Turn. Core fixed its lifetime, and the terminal sequence passed afterward.
- **Next:** finish core rule regressions and the complete S2 encounter check, then review reactions and proceed to S3 integration. S2 stays gated until admission.

### 2026-09-15 — Health checkpoint; reactions started

- **Implementation evidence:** ten public health/choice tests and 129 full-suite tests pass. A 100-sample timing check measured 0.112 ms p95 for command plus query and 0.120 ms for scripted input plus menu.
- **Independent findings:** the reviewer reproduced a nonlethal fist attack incorrectly killing a dog, and a contradictory saved check being accepted as a critical hit. The core slice corrects nonlethal handling for PC/ordinary targets and adds small check-consistency validation before admission.
- **Active work:** the same core owner adds Reactive Strike, its saved interruptions, required equipment/positioning actions, Vicious Swing, and Pack Attack. The terminal owner adds their controls. The independent health reviewer finished with the two reported corrections and no additional P0/P1. The terminal controls pass 12 focused checks; actual S2 CLI admission follows core readiness.
- **Scope:** S2 remains gated. S3 numeric helpers are ready for later integration; no S3 encounter claim is made.

### 2026-09-15 — S2 choices prepared; S3 calculations prepared

- **Content and terminal:** fixed fighter and dog definitions, readable saved choices, and health/equipment inspection are written. Eight focused S2 tests pass. S2 stays gated until the engine supports its required mechanics.
- **Independent pieces:** 15 focused positioning checks pass; 23 spell-helper tests and 10 related pure-rule checks pass. These cover useful calculations, not complete encounter behavior.
- **Integration in progress:** core health, Hero Points, and turn/save state are being joined. Other workers reported turn/save regressions during integration. The core owner fixed the reaction save issue and reports 75 shared regression tests passing, plus saved initiative Hero/tie prompts. Focused PC knockout/recovery checks remain in progress.
- **Design boundary:** S3 reuses the same check, health, and reaction procedures, with short direct spell handlers and two sourced effects. No new general spell or terrain framework is planned.
- **Accounting:** completed helper and design runs have evidenced input, cached-input, and output counts in the ledger. The active core run remains provisional.

### 2026-09-15 — S1 passed; S2 integration started

- **Delivered:** the synthetic terminal encounter and callable engine, source-backed basic rules, individual scripted dice, seeded randomness, and JSON persistence.
- **Independent evidence:** 56 S1/terminal tests; an interactive fight; 25 varied-policy seeded fights; supplied-die range/exhaustion checks; queries/rejections preserving randomness; and valid/corrupt-save tests. The 75-test repository total also includes unintegrated health cases and is not a claim of S2 completion.
- **Measured:** 1,000-sample p95 of 0.065 ms for command plus query and 0.081 ms from scripted input to menu on the recorded local machine.
- **Local setup:** editable installation and module startup work in the workspace virtual environment; 75 then-current tests passed there.
- **Corrections:** malformed saves now reject contradictory fights. The S2 terminal worker fixed the nonblocking summary-before-events presentation issue.
- **Active ownership:** `s1_core` now owns S2 health/check-choice integration in model/encounter/persistence; `s1_terminal` owns content and terminal files; `local_packaging` completed packaging and README startup instructions. Shared engine files have one writer.
- **Next:** finish PC health/check choices, then Reactive Strike and the reviewed starter encounter; extend that running engine with S3 ranged equipment and spells. The stable-zero health ruling remains pending.


### 2026-09-15 — S1–S3 implementation started

- **Authorization:** implement through S3 using the accepted plan and model routing.
- **Additional requirement:** deterministic dice input is a public engine feature for tests. Check and damage dice are supplied individually, with saved sequence position and no consumption by rejected commands or queries.
- **Readiness:** the repository still has no game runtime; its uncommitted documentation reset is intentional and preserved. Python 3.11, pytest, and packaging tools are available locally.
- **Assignments:** Astra/high reviewed readiness and is researching exact rules/roster scope. Luna/xhigh owns S1 core and the separate terminal/benchmark files. A short logging task registers this batch using the existing collector.
- **Rules decisions:** source research confirmed turn-wide diagonal costs, ordinary MAP, ordered degrees of success, critical damage, Step restrictions, and automatic turn completion after actions are spent. Synthetic actor tie ordering is an explicit scenario GM policy.
- **Source research complete:** [implementation rules and roster note](../implementation/s1-s3-rules.md) records the fixed fighter/warpriest builds and Guard Dog opponents, with required traits, reactions, health, spell modes, and expected cases. This is source review, not a claim that the content already runs.
- **Health review:** the pure helper is written with 19 focused cases, but independent source review rejected its claim that damage at stabilized 0 HP is harmless. The user has been asked the explicit P1 ruling; no dependent behavior is accepted yet.
- **S1 progress:** the terminal runs, its 27 tests pass, and a saved scripted-dice test resumes the next face correctly. Initial p95 EndTurn-plus-inspection/menu measurements were 0.077 ms. Core tests and independent S1 play review are still underway.
- **Next:** finish S1, execute it in a periodic Sol review, then add reviewed S2 and S3 mechanics/content in bounded increments. Current outcomes and measurements will replace this in-progress state.


### 2026-09-15 — Integrated plan reviewed

- **Decision:** use a callable Python engine, numbered terminal choices, manual control of both sides, automatic dice, Python content definitions, and JSON saves.
- **Research:** three Astra/high readers audited the existing plan, specified the smaller engine, and checked core rules and content priorities against sources. They found no blocking product question.
- **Repository baseline:** audit reports clean detached HEAD `115a55d844021c479a2b9d140bc0e7bf92aee40c`, equal to main, with 27 tracked documentation/metadata files and no runtime. Other worktrees were not inspected or modified.
- **Integration:** the supervisor wrote four connected plan segments. A Luna/xhigh worker archived all 27 baseline files and replaced the active project instructions and entrypoints. A Sol/high reviewer checked the integrated plan and selected live rule references. Luna workers completed the usage collector and final status/link checks.
- **Checks so far:** independent review confirmed 27/27 byte-for-byte preserved originals, zero broken active links/anchors, a valid usage ledger, and a passing `git diff --check`. Selected AoN rule claims were rechecked. No runtime test or benchmark has run because no engine exists.
- **Design decisions:** use direct Python rule procedures and small records for checks, damage, turns, effects, space, and interrupted actions. Content supplies parameters or a short dedicated function. Save choice state and randomness; omit network revisions, retry receipts, and compatibility frameworks.
- **Review corrections:** S1 now specifies a small open map, synthetic actors, exact terminal controls, visible omissions, and the state a save must preserve. The collector now enriches existing ledger entries without discarding their task descriptions, and it verifies run boundaries before attributing usage.
- **Final checks:** active links/anchors across nine Markdown files, ledger JSON, active-document inventory, and `git diff --check` passed. The collector's synthetic test and compilation passed; generated cache files were removed by its owner. All seven completed subagent runs have final input/cached-input/output records. Only the supervisor's current-turn accounting remains unfinalized.
- **Next:** review the linked plan. S1 is ready for a scoped implementation assignment: a complete small terminal fight. No commit or worktree merge was made during this reset.

## Usage accounting

The ledger records actual input, cached-input, and output counters for each run. Cached input is already included in input. All completed subagent runs have measured counters. The supervisor has a partial measured interval: it excludes work before its starting snapshot and final closeout after its ending snapshot. Missing telemetry is explicit; estimates are not substituted.

The accounting policy starts with this reset. Earlier exploratory conversation runs are outside this ledger's scope. The ledger stores task/configuration/usage metadata and short results, not private transcripts.

### Maintaining the ledger

Use [the existing collector](../../tools/log_agent_usage.py) for routine updates; no separate research task is needed to collect usage.

1. Register the run's task, requested model/effort, and session identity in `agent-runs.json`.
2. For a new single-run session, collect its evidenced full-session usage after completion with `backfill`. Mark the task complete and record its result after receiving the agent's final response.
3. Before a follow-up in a reused session, register a new run ID and use `begin` to capture its starting counters. After that run finishes, use `complete` with the same identity.
4. Preserve an explicit unknown boundary if the tool cannot establish one. Never substitute the full conversation total for one run.

Example command shapes:

```sh
python3 tools/log_agent_usage.py backfill --log docs/work-log/agent-runs.json --thread-id THREAD_ID --run-id RUN_ID
python3 tools/log_agent_usage.py begin --log docs/work-log/agent-runs.json --thread-id THREAD_ID --run-id NEXT_RUN_ID
python3 tools/log_agent_usage.py complete --log docs/work-log/agent-runs.json --thread-id THREAD_ID --run-id NEXT_RUN_ID
```

The session and run values above are placeholders. The supervisor can run these as part of maintaining its work log without reading implementation files or source material.

## Completed subagent usage

This summary includes finished measured runs from the plan reset, implementation, and follow-up work, including one superseded route-mapping run. The [ledger](agent-runs.json) retains each individual task, outcome, model, and input/cached-input/output count. Cached input is part of input; do not add those columns together.

| Model / reasoning | Runs | Input | Cached input | Output |
|---|---:|---:|---:|---:|
| gpt-5.6-luna / xhigh | 35 | 205,184,436 | 199,731,968 | 1,322,455 |
| gpt-5.6-sol / high | 11 | 59,935,464 | 57,892,992 | 218,086 |
| gpt-6-astra / high | 13 | 12,124,247 | 11,230,208 | 62,539 |
| **Finished total** | **59** | **277,244,147** | **268,855,168** | **1,603,080** |

Supervisor accounting is separate in the ledger. Its earlier missing boundary and partial measured interval are explicit; no full-turn usage is inferred. Routine accounting uses the existing collector, with no new telemetry framework.
