# Fear and real escape actions

## Status and selected behavior

This packet is completed integration evidence for the 551-test checkpoint. Fear/Flee, strict saves, later-initiative timing, real saved reactions, continuous victory and terminal use were exercised. Historical intermediate notes below explain the delivered fixes; they are not outstanding assignments. Use [ACTIVE](ACTIVE.md) for current execution state.

Fear takes two actions, has concentrate/manipulate/emotion/fear/mental traits, targets one creature within 30 feet and uses Will. Critical success does nothing; success/failure give frightened 1/2; critical failure gives frightened 3 and fleeing for one round. It spends a rank slot but receives neither Sorcerous Potency nor Angelic Blood Magic: it does not damage/heal and is not an Angelic gift. [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524).

Fleeing requires each on-turn action to pursue escape as expediently as possible. Necessary actions such as opening an obstructing door can qualify; Delay and Ready are prohibited. It does not prohibit reactions. [Fleeing](https://2e.aonprd.com/Conditions.aspx?ID=74).

## Spell and condition connection

Reuse the generic spell-save procedure with Will, actual adjusted caster DC and target modifiers, target-owned Hero choice, one slot spend, and no condition application before the final save. Existing pending validation names Void Warp explicitly; admit Fear's statistic and result handler without bypassing validation.

Use the current frightened mechanism, plus a separate fleeing effect with caster, target, value 1, caster-next-start expiry and local-time deadline. Frightened reduces at the target's turn end; fleeing expires at the caster's next start. These are separate events.

## One concrete Flee action

Add public `Flee()` that chooses the necessary ordinary procedure:

1. Use actual Escape if an admitted escapable impediment prevents movement.
2. Stand when prone and doing so enables faster escape, preserving its reaction window.
3. Otherwise use ordinary Stride on the selected path.
4. If supported physical boundaries genuinely prevent farther escape, spend an action attempting escape and explain why.

Pay once through the selected procedure. Place the fleeing action gate before the existing early family-command and EndTurn dispatch, so those cannot bypass the condition. Reject unrelated actions and voluntary early EndTurn while actions remain; allow pending choices and necessary Escape methods. After three actions, use ordinary automatic turn completion. Reactions remain available. Any subordinate movement must also obey escape intent.

## Bounded route convention

For the first accepted Fear scene, explicitly author a closed physical arena. Use this delegated GM convention: choose the reachable square giving greatest separation from the current source, find a shortest legal route, and execute its Speed-limited prefix. Recalculate next action; choose deterministic ties.

The helper visits at most twice the map's cell count: position plus diagonal-cost parity. Retain one best cost and predecessor per state, then reconstruct one path. Reuse ordinary adjacency, movement cost and occupancy rules. Do not enumerate all routes or future turns. A legal detour may temporarily approach the source.

At the furthest reachable physical boundary, remaining actions become blocked escape attempts. Keep the actor on the board, alive and in combat; do not manufacture victory or permission to attack. Existing unspecified open edges must not silently become walls. Open-edge departure remains unsupported in this first scene boundary. If escaping requires an unsupported action such as Tumble Through, report that limit instead of asserting physical impossibility.

A small literal setup fact can identify the closed environment. Do not branch on scenario IDs or add a world-exit framework.

## Reactions and saves

Fleeing Stride is ordinary movement compelled by a condition, not the technical forced-movement exception. It provokes Reactive Strike normally. Preserve the actual chosen path, next step, diagonal state and considered reactors through save/load; do not charge or recompute another action after a saved reaction. An ordinary hit resumes the path; incapacitation stops it.

The current admitted reactions do not move the fear source, so a new planner during an unfinished move is unnecessary. A literal originating-effect reference may be added to the continuation if needed for validation.

## Six proposed public checks

- Four save outcomes from real casts, with one slot spent and no damage, healing, Potency or Blood Magic.
- A saved PC Will/Hero decision applies the final result once, without another resource spend.
- Three actual escape actions after critical failure on a healthy-start closed map, including a detour and atomic rejection of unrelated actions/early EndTurn.
- Flee provokes a saved reaction, then correctly resumes or stops its ordinary movement.
- A closed corner consumes blocked attempts without removing the actor or ending combat.
- Frightened decay and fleeing expiry occur separately; a prone or grabbed branch uses actual Stand/Escape rather than bypassing the impediment.

These are designs, not completed encounters. The source investigation found no new P0/P1; the deterministic route and explicitly closed scene are ordinary delegated GM choices.


## Delivered pure helper

`src/pf2e/fleeing.py` exports `choose_flee_route(start, fear_source, width, height, speed_ft, *, diagonals_already_made=0, occupied_positions=(), body_positions=(), ally_positions=(), illegal_final_positions=()) -> FleeRoute`.

The result carries one full route, its Speed-limited prefix, goal/destination, movement/goal costs, separation and literal stop/blocker facts. Deterministic ties use Position (x,y). Caller supplies ordinary endpoint restrictions: traversable ally/body positions are not automatically illegal endpoints because this pure helper does not own creature size or action context. The runtime integration must pass the existing movement rules' actual illegal endpoints. A prefix that would finish on a forbidden endpoint trims to its latest legal square.

Seven cases cover diagonal parity, detour, body/ally traversal, endpoint trimming, the occupied fear-source corner distinction and a real hostile blocker. The 80×60 allocation probe peaked at 2,282,000 bytes (about 2.18 MiB) and took roughly 0.48 seconds with tracemalloc; that is Python allocation tracking, not whole-process RSS. The focused module passed in 0.68 seconds; compile and diff checks pass. No doors, terrain, exits, reactions, conditions or action spending are implemented by the helper.


## Active integration checkpoint

The settled scene field is `EncounterSetup.closed_boundary: bool = False`. A staged 5×3 closed room uses setup `sorcerer_angelic_fear_closed`, caster at (1,1), dog at (3,1). Ordinary movement continuation carries `movement_kind="flee"` with no new fields. Fleeing uses the existing seven-field effect record, value 1, caster-next-start and cast-time-plus-six-seconds deadlines.

A public critical-failure cast applied frightened 3 and fleeing, spending one rank slot (3→2) without damage/healing/Blood Magic. A separate PC target probe kept a failed Will result or spent its Hero Point to reroll to critical success; the condition followed the final result. Save/reload evidence is still pending. Persistence has resumed under the settled contract; its earlier readiness-only run remains separately recorded.


## Runtime handoff and resumed verification

The runtime owner released actual Fear, Flee, closed-boundary spending and expiry. Eight Fear tests pass; overlapping groups of 62 casting/Flee checks, 40 conditions/encounter checks and six existing spell-reaction persistence checks pass. Compile and whitespace checks pass. Do not sum overlapping groups or treat existing spell reaction tests as proof of a new saved Flee reaction.

Public probes covered actual fleeing movement to (4,0), blocked escape spending and active-effect/paused-Hero save/load. Stand/Escape delegation also ran, but independent review must distinguish constructed impediments from conditions caused by ordinary play. No complete Fear fight or full-suite checkpoint is claimed yet.

User interruption stopped the separate persistence owner before final handoff. Partial edits are preserved and a fresh bounded owner is finishing their tests. A new Sol review checks actual saved reaction movement, continuous play and source timing, including a caster who is not first in initiative. The review’s initial work is source/static inspection while persistence owns test execution.


### Timing defect under review

Source/static review identified a likely early-expiry defect for casters later in initiative: a round wrap reaches the absolute deadline before the caster’s next start. This can remove Fear before a victim who already acted gets its next turn. Sol is verifying the exact public sequence and owns the narrow runtime correction; persistence owns admission of the corresponding legitimate saved interval. In-combat source-turn expiry must remain authoritative, with absolute expiry used for explicit time advancement outside combat. No new player ruling is required.


### Independent later-save failure found

Sol’s actual Halo cast and turn sequence reached world second 60 with source-start count 10 and expiry at source start 11; loading failed. The new persistence check had incorrectly equated the original cast’s source-start count with the current count. Sol owns the narrow repair and retained public regression, alongside the early-expiry correction. The current clock starts at zero; future scene recovery must include its encounter-start offset when validating this relationship. No broad checkpoint is claimed until these corrections pass.


## Independent actual-play result

Sol verified and fixed the timing defect, and corrected older-effect save validation. A healthy-start Sorcerer/Fighter/dog closed-room sequence has the dog act before the caster, fail Fear critically, remain fleeing after the round wraps, then provoke an actual Fighter Reactive Strike. Saving at that choice preserves the exact three-square route; the five-damage hit resolves and movement resumes. Frightened drops to 2 at the dog’s end, fleeing expires at the caster’s next start, and Divine Lance finishes a blue victory.

A separate actual Halo sequence reaches world second 60 with source-start count 10/deadline 11, saves/reloads the still-active aura, then expires it at source start 11. These are two retained public tests, not constructed pending snapshots. The combined focused group passes 72 tests in 0.97 seconds; diff check is clean and all probes exited. Terminal and full-suite integration remain pending.

Sources checked during review: [Fear](https://2e.aonprd.com/Spells.aspx?ID=1524), [Fleeing](https://2e.aonprd.com/Conditions.aspx?ID=74), [Frightened](https://2e.aonprd.com/Conditions.aspx?ID=76), [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256), [Angelic Halo](https://2e.aonprd.com/Spells.aspx?ID=2093).
