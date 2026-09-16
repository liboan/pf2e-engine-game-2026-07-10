# Light and a minimal useful lighting scene

## Status and scope

The targeting prerequisite passes integration: **611 full-suite tests**, including the new spell gates and Halo encounter. The subsequent Light cast/attachment/save slice passes **62 focused checks**, delivered controls pass **50 adjacent checks**, and terminal controls pass a **90-check focused/terminal group**. Independent completed play is in progress. A separate source review found and repaired lost caster Blood Magic after failed Heal targeting: three review cases now pass normally. The earlier full-suite result does not certify these latest edits. Keep meaningful illumination in a flat, open, ambient-dim scene with known combatants. Do not build hiding, searching or a general vision framework solely for this cantrip. Current ownership is in [ACTIVE](ACTIVE.md).

## Printed rules

Rank-1 Light is a two-action cantrip with concentrate, light and manipulate traits and 120-foot creation range. It creates a chosen-color orb: bright within 20 feet, dim for the next 20 feet. An orb can attach to a willing creature in its space and follow that creature. Sustain moves it up to 60 feet and allows attachment/detachment. Dismiss ends it. At four active Lights, the next cast requires choosing an existing one to end. It lasts until that caster’s next daily preparations, not merely until an unsustained turn ends. There is no object target, attack roll or saving throw. [Light](https://2e.aonprd.com/Spells.aspx?ID=1585).

Sustain and Dismiss each cost one concentrate action. Light’s Sustain grants a special benefit without changing its lifetime; skipping Sustain does not end it. A disrupted Sustain ends the effect. No printed once-per-round Sustain limit applies here. [Sustain](https://2e.aonprd.com/Actions.aspx?ID=2317), [Dismiss](https://2e.aonprd.com/Actions.aspx?ID=2311).

The cantrip spends no slot/focus and triggers no Angelic Blood Magic. [Bloodlines](https://2e.aonprd.com/Bloodlines.aspx).

Dim-light creatures and objects are concealed to ordinary vision, while low-light vision/darkvision overcome this cause. Guard Dog has actual low-light vision; its imprecise scent need not be implemented for this scene. Concealment remains observer-relative and does not make these combatants hidden. [Dim light](https://2e.aonprd.com/Rules.aspx?ID=2403), [Low-light vision](https://2e.aonprd.com/Rules.aspx?ID=2411), [Guard Dog](https://2e.aonprd.com/Monsters.aspx?ID=2924).

Targeting a concealed creature with an attack, spell or other effect requires a DC 5 flat check. Areas bypass it. No modifiers/bonuses/penalties apply; simultaneous flat checks preventing the same thing use the highest DC. Hero Points can reroll this check, using the second result. Guidance/Assurance cannot replace or modify it. Save its choice separately from a later attack Hero choice; rerolling the attack never rerolls concealment. [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62), [Checks](https://2e.aonprd.com/Rules.aspx?ID=2278), [Hero Points](https://2e.aonprd.com/Rules.aspx?ID=2333).

## Minimal state and reuse

The first slice implements ambient bright/dim queries and selected vision declarations. Descriptive senses strings and staged dazzled identifiers do not themselves constitute supported vision. The complete feature needs only:

- Scene ambient light, with existing scenes defaulting bright; initially admit bright/dim.
- Explicit supported vision for the selected ordinary-vision PCs and low-light Guard Dog.
- A literal orb record: stable ID, caster, rank, color, and either position or attached actor; lifetime belongs to its caster’s preparation.
- Point cast, willing attachment, Sustain, Dismiss and fifth-cast replacement choices.
- A shared observer/target illumination query and saved targeting-check procedure.

Reuse grid distance, area geometry, ordinary command transactions, casting/manipulate reactions, flat-check patterns and strict continuations. Orbs are effects, not creatures/equipment: no HP, occupancy, initiative, inventory or action pool. Do not force the record into the current actor-targeted, source-turn-expiring spell record.

## Every enabled targeted route needs the gate

| Route | Treatment in the dim scene |
|---|---|
| Strike, Vicious Swing, Reactive Strike | Flat check before attack roll |
| Divine Lance | Flat check before spell attack |
| Void Warp/Fear | Flat check before target save |
| Guidance/Stabilize/one- and two-action Heal | Flat check; beneficial targets are not automatically exempt |
| Trip/Grapple, including Assurance | Flat check before skill result; Assurance follows separately |
| Feint/targeted Demoralize | Connect or explicitly reject before costs |
| Runic Weapon/Read Aura objects | Connect when admitted, otherwise reject dim use before costs |
| Paired/staged attack families | Unsupported in dim scenes until every targeted constituent is connected |

Three-action Heal and Halo area effects bypass concealment. Movement, Raise Shield, handling one’s own equipment, End Turn and an unattached Light location cast do not get blanket checks. Escape concerns an impediment; do not invent a visual targeting check against its source. Preserve a narrow later Sure Strike bypass without implementing that spell in this assignment.

Darkness, hidden/undetected actors, invisibility, fog, magical-darkness counteraction, occluding terrain, elevation and unsupported senses remain explicitly outside this first environment. Darkness requires additional blinded/detection behavior and is not another DC 5 case. [Darkness](https://2e.aonprd.com/Rules.aspx?ID=2404).

## Resolution and saving

Validate legality/supported environment, then commit costs and attack count once. Resolve existing reaction/manipulate windows before reading current illumination. A failed targeting flat check retains committed action/resource/ammunition costs; a successful one proceeds to ordinary attack/save/Guidance/Nimble behavior. Preserve exact target, check, die, accepted fortune result, remaining continuation and paid costs in saves.

Divine Lance currently increments attack count inside its roll procedure; move that commitment ahead of a new concealment-failure exit with the existing committed marker so a failed attempt still contributes MAP.

For Light, collect point/color/attachment/replacement intent and validate before commitment. The fifth cast uses an explicitly selected `replacement_orb_id` command argument; the terminal can collect it before submission. No extra uncharged engine choice phase is needed just for that selection. A genuine later reaction/willingness pause must retain the selected ID in its saved continuation. Obtain explicit attachment willingness through the existing choice system; team membership does not decide it, and ordinary inability to act is not automatically unwillingness. [Targets](https://2e.aonprd.com/Rules.aspx?ID=2240).

Commit two actions, then ordinary manipulate interruption. Create/replace only after successful resolution; disruption must not delete the selected old orb. Declined attachment leaves the successfully created orb at its chosen location.

Sustain validates the owned orb and permitted movement/attachment, then costs one concentrate action. Derive an attached orb’s location from its carrier, including during reaction-paused movement. Daily preparation removes only that caster’s orbs; rounds, Refocus, victory and elapsed time alone do not.

## Scene conventions and excluded edges

Use a cell-center orb with no footprint and ordinary grid distance. Take the brightest applicable illumination; overlapping dim regions do not become bright. Create/move the orb before optional attachment, so the creature at that point is brightly illuminated. Choose replacement before resolution, but remove the old orb only after the new cast succeeds. These are explicit local conventions.

The printed 120-foot range governs creation and does not explicitly supply a later control tether. The first accepted scene remains within 120 feet and does not claim a broader control-range rule. Withdrawal of attachment consent likewise has no implemented command in this slice. These two broader edges remain excluded; clarify them before any materially dependent broader admission. They are not P0 blockers for the selected scene.

Recovery carries attached orbs with retained actors. Reject an unresolved unattached-orb departure instead of silently deleting it. Preparation owns the actual cleanup.

## Serial slices and six public checks

The following sequence records implementation checkpoints, not mandatory ownership changes. New remaining playable outcomes keep one Luna owner across runtime, saves, terminal and tests through review fixes; preserve current owners and completed work.

1. Scene lighting/selected vision and the first shared targeting check: ordinary Strike first, then Vicious Swing/Reactive Strike and saved flat-check/Hero continuation. Guard other affected routes explicitly before costs while incomplete.
2. Connect the selected targeted spell routes to that same check, preserving area/self/vision exceptions and one-time action, slot and attack-count commitment. This group is delivered. Unsupported skill/item routes stay explicitly guarded while the actual Light feature is built.
3. Implement actual point creation, illumination, attachment and strict orb persistence; then Sustain/Dismiss/fifth-cast replacement. The first bounded cast slice rejects a fifth orb before costs until replacement is connected. Add terminal choices after the command contract stabilizes. Keep one core owner and require the first executable point cast before expanding that worker's scope.
4. Complete the remaining required skill/item targeting connections, then complete dim-light play and local recovery. The guarded intermediate feature does not establish whole-spell, general dim-scene or whole-Sorcerer coverage.

Planned checks:

- Ordinary-vision attack fails DC 5 on 4 without an attack roll; costs/MAP remain. Save a Hero choice, reroll to 5, proceed once. Dog needs no dim-light check.
- Actual Light removes concealment at 20 feet; 25–40 feet stays dim. Creation 120 feet succeeds and 125 feet rejects atomically. No slot/focus/Blood Magic.
- Saved willingness, actual carrier/reaction movement, Sustain detach/move/reattach, over 60 feet rejection; repeated Sustain costs actions without creating a turn deadline.
- Four orbs, explicit fifth-cast replacement retained through a saved reaction/willingness pause, one Dismiss, rounds/Refocus preserve others, preparation removes only owner's orbs.
- Targeted save spell and healing honor concealment; area Heal bypasses it; Assurance still needs a targeting check; unsupported dim routes reject before spending.
- Healthy-start dim fight with injury, useful Light placement/movement, saved choice, healing/offense and victory, then attached-orb carry until preparation.

These are acceptance proposals, not a claim that all paths exist. Whole-Sorcerer acceptance requires actual implementation and saved play.

## First delivered targeting slice

The first Luna slice reports seven passing focused tests plus an earlier 39-check regression group. Bright remains the default scene setting; dim is now explicit. Selected vision is `ordinary` or `low_light`, exposed in inspection. Runtime queries are `illumination_at`, `target_illumination` and `target_is_concealed`. Save version 16 validates ambient light and preserves a distinct `concealment_hero_reroll` choice, with `check_kind="concealment"` and the completed targeting flag.

Public evidence includes flat 4 versus DC 5, keeping it to complete `concealment_failed` without drawing an attack die, and saving that Hero choice before rerolling to 5 and resolving one attack. Action and MAP commitment occur once. The Guard Dog bypasses dim concealment with low-light vision; Vicious Swing and Reactive Strike paths are covered. No orb, Light cast, Sustain, Dismiss or darkness behavior is delivered by this slice.

Independent Sol review retained six additional public tests: the combined selection reports **11 passed, 2 failed**. The failures reproduce an omitted item-target boundary and undeclared special vision. Casting Runic Weapon on another creature's sword in dim light reaches willingness and spends two actions and one slot without the targeting check; until connected, that route must reject atomically. Vision must default to undeclared, with only explicitly ordinary/low-light actors admitted to dim scenes; bright legacy scenes remain usable. No free-text senses parser is needed.

Passing independent paths demonstrate self-Guidance survives a failed flat check, targeting and attack Hero choices stay separate through save/load, nested saved Reactive Strike failure resumes movement and spends its reaction once, area Heal bypasses the gate, and Divine Lance initially rejects before costs. The persistence file is correctly inside the project; an earlier shorter link was a typo, not an external duplicate. All probes exited; process enumeration was denied.

The bounded Luna repair made both retained failures pass: **13 dim tests**, **31 dim/Runic checks**, and **67 content/persistence checks** pass. Vision now defaults to undeclared; selected Fighter/Sorcerer explicitly use ordinary sight and the dog low-light vision. Dim admission rejects unsupported declarations; bright scenes remain compatible. External Runic item targeting by an ordinary observer rejects before costs, while self-held equipment remains allowed. Save version 16 needs no change. No background processes were launched. Divine Lance and targeted Heal are the next bounded connections, using this same procedure rather than new independent targeting systems.

The next run reached its first executable checkpoint: `test_dim_divine_lance_fails_concealment_before_spell_attack` passes in the real staged Sorcerer fixture. Supplied flat4 emits the cast and targeting events, pauses at the distinct targeting Hero choice, spends two actions and increments MAP once without drawing a spell-attack die. This initial result is not yet the full keep-failure, saved-reroll or Heal acceptance; those checks remain with the current owner.

That run subsequently completed the bounded Divine Lance and targeted Heal connection with **94 passing focused checks** and a clean diff check. Shared spell concealment continuation handles the flat check after existing manipulate/reaction/Grabbed resolution. Failure keeps committed actions/slots and Divine Lance's attack count, with no attack/healing die. The eventual spell attack uses the original MAP; later attack rerolls do not repeat targeting. Saved flat choices validate directly and resume the existing spell flow once. Self Heal and three-action area Heal bypass the check. Other unfinished routes still reject before costs. All checks were synchronous; no full suite or background work ran. The next run adds Fear, Void Warp, Guidance and Stabilize to the same procedure.

The following run connected **Fear, Void Warp, Guidance and Stabilize** using that same saved spell procedure, with **98 focused checks passing** and a clean diff check. Failed targeting spends committed actions/slots but creates no save, effect, immunity or healing roll. Flat and spell-save Hero choices remain separate through save/load, saved cast source/resources validate strictly, and the appropriate self-target exceptions remain. Stabilize tests create injury through an actual Strike instead of mutating health. Light orbs, item/skill targeting and recovery are still outside this delivered slice. Core edits are frozen for the next full integration/memory measurement.

The full checkpoint initially found one accepted-catalog invariant failure: the unfinished dim targeting/reaction fixtures had been added to normal `SETUPS`. Moving them into the existing `_STAGED_SETUPS` preserved public constants and strict saved lookup without adding a runtime hook. The focused catalog/dim/save group passed 31 checks; the final full suite passed **611 tests in 2.54 seconds**, wrapper wall 2.832768 seconds, child peak 64,995,328 bytes (**61.984 MiB**) on Python 3.11.1/macOS 26.3.1 arm64. Compile/diff checks pass; all subprocesses exited. Accepted catalog remains 48 setups/32 creatures; runtime-staged lookup has 7 setups, distinct from expansion staged maps with 2 setups/6 definitions. The old staging summaries must not be mixed as one count.

## First actual orb checkpoint

The next Luna worker reports four passing checks in `tests/test_light_orb_cast.py`. Public `Cast("light", point=Position(0, 2), color="red")` creates `light:angelic_sorcerer:1`, spends two actions and no slot/focus, lights its point through 20 feet brightly and leaves a target at 25 feet dim. The focused checks include save/load and atomic 125-foot rejection. The probe exited; no running process remained. The appended Cast fields are `point`, `color`, `attachment_actor_id` and `replacement_orb_id`; replacement remains unsupported in this first slice. Saved willingness and interruption checks are still being completed, so this is partial Light evidence, not complete spell or class acceptance.

The worker then released point casting, willing attachment/refusal and strict orb/continuation persistence with **62 passing focused checks** across Light, casting, dim targeting, Sorcerer and Runic Weapon. `LightOrb` retains a stable ID, caster, rank, color, point or attached actor and preparation owner. Manipulate/reaction/Grabbed handling gates creation; critical disruption creates no orb. The fifth cast still rejects before commitment. Compilation/diff checks pass. The old `tests/test_spells.py` unavailable expectation remains a known integration follow-up, owned with terminal casting. Sustain/Dismiss/replacement are now a separate core assignment; terminal point casting runs in parallel in non-overlapping files. This remains partial spell coverage.

Terminal casting subsequently delivered point/color/optional carrier selection, useful orb identity and location display, and bounded saved-willingness/invalid-coordinate tests. The old metadata assertion now checks executable two-action, 120-foot point casting. Its focused terminal/spell group passed **28 checks**; compile/diff pass. Unpublished control options stay hidden. Broader terminal testing was blocked by the concurrent controls owner's incomplete options helper and must be rerun after that shared contract settles.

## Delivered orb controls

Public `Sustain(orb_id, point=None, attachment_actor_id=None)` costs one concentrate action and supports movement up to 60 feet, detachment and willing attachment. Attached positions derive from the carrier, repeated Sustains spend ordinary actions, and skipping Sustain does not create an expiry. `Dismiss(orb_id)` costs one action and removes a caster-owned orb. Light-specific aliases also exist; terminal integration uses the canonical commands.

Fifth casts now require a valid selected `replacement_orb_id`. Missing, stale and foreign IDs reject atomically; old orbs remain through interrupted casts and are removed only after new creation. Saved willingness and replacement continuations validate strictly. Save version remains 17. Focused cast/control tests report **14 passed**, the adjacent Light/casting selection **50 passed**, and diff checks pass. All processes exited without background work. Terminal controls, independent complete play, the remaining guarded targeting routes and preparation cleanup are still separate acceptance requirements.

Terminal follow-up now exposes the canonical controls, owned-orb selectors and pre-cast replacement selection. It shows stable IDs, colors and current carrier/location, submits public engine commands and leaves rules validation to the engine. Retained terminal tests cover saved Sustain willingness, Dismiss and a full fifth-orb replacement sequence, alongside casting and input bounds. The broader focused/terminal selection passed **90 checks**; compile/diff checks pass, and no background processes were started.

## Independent completed Light play

Sol added three passing public-command cases in `tests/test_light_play_review.py`; the adjacent Light cast/control/terminal/Blood Magic selection passes **28 checks**. The healthy-start dim fight saves genuine attachment willingness, inflicts real injury, fails DC 5 targeting before Sustain, moves the orb to make the target bright, and ends with Divine Lance victory. Another case saves a real movement reaction and verifies the attached orb follows its carrier. The final case rejects under-cap replacement as a free Dismiss and protects another caster's orb; the retained interrupted fifth-cast case preserves the old orb.

Sources checked: [Light](https://2e.aonprd.com/Spells.aspx?ID=1585), [Sustain](https://2e.aonprd.com/Actions.aspx?ID=2317), [Dismiss](https://2e.aonprd.com/Actions.aspx?ID=2311), [Targets](https://2e.aonprd.com/Rules.aspx?ID=2240), [dim light](https://2e.aonprd.com/Rules.aspx?ID=2403), and [Concealed](https://2e.aonprd.com/Conditions.aspx?ID=62). No P0/P1 defect was found. All task-owned checks and CLI probes exited; host process enumeration remained unavailable.

The staged `sorcerer_angelic_first_cast` scene works through the tested `run_terminal(setup=...)` API. The normal CLI intentionally rejects that unaccepted catalog entry; do not advertise a ready CLI launch yet. Preparation lifetime and the remaining guarded skill/item routes still gate whole-Sorcerer acceptance.

The subsequent full serial integration passed **639 tests in 2.74 seconds** (wrapper 3.072901 seconds), with child peak RSS **65,994,752 bytes / 62.938 MiB**, Python 3.11.1/macOS 26.3.1 arm64. Compile, diff and supported catalog/API checks passed. Accepted catalog remains **48 setups / 32 definitions**; runtime staged lookup is **7 setups / 3 definitions**, separate from expansion maps **2 setups / 6 definitions**. Log: `/private/tmp/pf2e-full-checkpoint-20260916-light.log`. All checks exited synchronously, with no background processes or browser tools.
