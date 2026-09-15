# Engine components and content

## Design rule

Use ordinary Python records and functions to preserve the facts PF2e needs. Add an abstraction when a real mechanic benefits from it. Do not build a compiler, plugin framework, generic event bus, or resource-accounting language.

The following are responsibility boundaries, not a requirement to create every file before the first fight works. Start under `src/pf2e/`; split modules when they acquire distinct work.

## Main components

| Component | Owns |
|---|---|
| Model | Definitions, creature instances, encounter state, commands, results, and pending-action records. |
| Encounter | The public interface; input validation; resolution; publishing a completed change or a pause. |
| Checks | Modifier stacking, attack context, MAP, rolls, DCs, and ordered degree-of-success calculations. |
| Damage and health | Typed damage components, defenses, healing, HP changes, and the implemented knockout/recovery rules. |
| Space | Grid distance, occupancy, reach, path legality and cost; later terrain, cover, and areas. |
| Actions and reactions | Shared action procedures and explicit steps for the supported interruptions. |
| Turns and effects | Initiative, action availability, start/end timing, conditions, and effect expiration. |
| Content | Trusted Python definitions, an explicit catalog, encounter setups, and small specialized ability functions. |
| Persistence | JSON encoding, compatibility checks, and safe file replacement. |
| Terminal | Menus, input parsing, maps, and readable result formatting. |

## Definitions, participants, and state

An immutable definition describes reusable statistics, attacks, traits, abilities, and source notes. A creature in an encounter refers to a definition and has its own changing HP, position, equipment, resources, conditions, and health state. Two creatures sharing a definition never share mutable combat state.

The encounter holds the map, participants, initiative, current turn, effects, pending actions, current choice, and random-generator state. Turn information includes available actions, reaction availability, attack count, and the applicable diagonal-movement count.

Use explicit fields for ordinary actions and reactions. Add restricted extra actions or distinct casting-resource records when an admitted mechanic needs them. Keep identifiers for references and explicit catalog dispatch; do not select shared-rule behavior by recognizing a creature's name.

Store the facts required to continue play. Menus, target lists, calculated displays, and complete histories do not belong in authoritative state.

## Commands and changes

A command describes intent: Stride along a path, Strike a target with an attack, use an ability, or End Turn. The engine checks legality even when the terminal offered the command.

Resolve each call against a private draft of mutable encounter state and random state. Publish that draft when the call completes or pauses for a real choice. Discard it on rejection or an internal failure. Earlier calls, including already-resolved reactions, remain committed.

Start with straightforward copying while sharing immutable definitions. Measure before adopting more elaborate transaction or caching machinery.

There is one active controller. Do not require HTTP envelopes, command UUIDs, network retry receipts, whole-engine revision checks, or synchronization. A pending-choice identifier is sufficient to reject an answer to an old or already-answered prompt.

## Interruptions

Keep a small serializable stack: a list of unfinished actions, with the currently resolving action on top. Each record states who acts, selected inputs, the current step, costs already paid, resolved facts, and remaining work.

For example, movement pays its cost and advances along a path. A supported reaction opens a choice. Accepting it puts the reaction above movement. Once the reaction resolves, the engine checks whether and how the remaining movement can continue. It preserves historical trigger facts and already-completed effects.

Remember declined offers, completed rolls, and paid costs. Saving and loading must not repeat them. Use direct calls at supported timing points, not arbitrary content instructions, saved Python generators, or an extensibility protocol.

Add only interruption points required by selected content. Preserve player-owned ordering choices; apply a documented GM policy only where the rules delegate judgment.

For the selected S2/S3 content, reuse the same check decision inside an ordinary attack, a reaction, or a saving throw. The saved record identifies whose check it is and preserves the modifiers already chosen. For example, the target owns a Void Warp saving throw and its Hero Point decision. Guidance is chosen before the check rolls; a Hero reroll is chosen after seeing the original result. Neither decision may repeat the parent action cost.

## Rules data that must stay explicit

- **Checks:** retain modifier type/source, DC, natural die, total, attack context, and ordered degree changes. Queries do not roll dice.
- **Damage:** keep the source effect and its typed components together. Preserve relevant precision/material/critical facts as needed. Do not flatten damage before defenses can inspect it; healing is its own operation.
- **Health:** apply the correct implemented zero-HP treatment for the actor. PCs cannot silently use an ordinary-enemy removal shortcut. Ending an encounter is separate from declaring creatures dead: the shared outcome check asks whether each team still has a conscious living combatant. Preserve unconscious actors and their health facts in the final state.
- **Effects:** retain source, subject, value, and an expiration anchor such as a particular actor's next end of turn. Distinct sources may need separate records even when one currently dominates.
- **Space:** keep position and footprint conceptually distinct. The first map may use one-cell actors; later larger footprints should use the same central spatial functions. Save turn-wide movement accounting.
- **Resources:** record the owning item or casting source when that matters. A future restricted action or spell use must not become an indistinguishable generic counter.

These are small rule-specific records, not universal frameworks.

S3 needs two explicit ongoing spell effects: Guidance and enfeebled from Void Warp. Both retain their caster, target, and expiry at the caster's next initiative start. Reaching that position expires the effect even if the caster cannot act or is dead. Guidance also records its separate one-hour immunity using encounter time, with any consumed bonus retained in the current check for a later Hero reroll.

The initial caster has individually labeled prepared slots: two ordinary slots and four Heal-only font slots. Each records its source, prepared spell, rank, and whether it is spent. Cantrips do not spend those slots. This concrete casting model is enough for S3; additional casting models follow when selected content needs them.

## How content uses the engine

Author frozen Python definitions through one explicitly imported catalog. Encounter setups select definitions, teams, positions, supported map data, and starting circumstances; register each setup in that catalog before starting it. The original S1–S3 setups use 7×5 open maps. S3i adds two catalogued 15×5 maps; exact catalog matching continues to reject modified/ad hoc setups. Larger-map save/load, named terminal startup, and complete range/area interaction routes have passed independent S3i acceptance. Definitions cannot replace rule procedures or patch outcomes to force a win.

**Simple content reuses procedures.** An attack supplies its statistic, reach, traits, and damage profile to the shared Strike/check/damage functions. Another creature with different numbers should need only another definition.

**Specialized content gets a small function.** A useful ability can call shared movement, checks, damage, and effects with its particular restrictions. If it can pause, its unfinished work has an explicit record. It does not invoke another public command that accidentally charges subordinate action costs again.

The selected content demonstrates this division directly. Vicious Swing changes a shared Strike's action cost, weapon dice, and attack count. Pack Attack adds dice when its own ally/reach condition holds. The shortbow supplies range, hand, ammunition, and deadly-die facts to the ordinary attack procedure. Spell helpers calculate the selected numeric outcomes; the encounter owns targets, willingness, costs, reactions, health changes, and saved continuation. Three-action Heal rolls once for its qualifying living recipients and keeps the caster's self-inclusion choice explicit.

The catalog binds an ability to its handler. Normal Python imports and tests are sufficient for trusted project code. Do not introduce dynamic module loading, executable JSON, arbitrary expressions, module authority digests, or a custom effect language.

Extract a shared procedure when multiple abilities reveal the same rules behavior. A single useful exception can remain a short function. If it demands a large subsystem, apply the [content admission rule](03-rules-and-stages.md#content-admission).

## Setup, inspection, and saving

Setup validates content references, map support, positions, quantities, and selected options before starting. A saved fight is different: loading restores the exact situation without rerolling initiative or resetting resources.

Save at externally visible decision boundaries, including reaction prompts. JSON contains the encounter, map, unfinished actions, current choice, resolved facts, and full random-generator state. A seed alone cannot restore a generator after play has consumed rolls. A public scripted-dice provider is also required for tests: callers supply individual die results in order, including check and damage dice. Validate each result against its die size and report an exhausted script clearly. Save/load preserves the provider kind and sequence position; rejected commands and queries do not consume either scripted or random rolls. Tests must use this interface rather than monkeypatching hidden random calls.

Validate saved checks by reconstructing their arithmetic and degree from their stored facts. Validate damage in its actual context: ordinary critical multiplication, basic-save rounding, and an undoubled deadly die are different supported calculations. Spell actions also break the prototype assumption that actions spent equal attacks counted. Keep these as explicit known cases, not universal equations imposed on every effect.

Use a save-format version and one engine/content compatibility identifier. Support compatible-build restoration first; reject incompatible saves clearly. Write a temporary file and replace the destination atomically. Do not serialize Python callables or use pickle. Save migrations can wait until released saves need preservation.

Inspections return safe read-only information: current actors, resources, effects, choice, and focused check/damage explanations. Keep a bounded recent combat log for people. Tests examine structured results and state directly; they do not parse prose to decide correctness.
