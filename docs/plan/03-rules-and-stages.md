# Rules, content, and stages

## Source policy

Use PF2e Remaster rules and individually selected content, with the actual source edition, URL, and review date recorded alongside definitions, rule notes, or tests. The initial source pool is Player Core, Player Core 2, Monster Core, and NPC Core; this is a pool to select from, not a commitment to implement four books.

The planning research below reviewed Archives of Nethys on **2026-09-15**. It establishes planning facts, not complete executable coverage. Before implementing a rule, resolve the exact relevant text and expected cases. Do not silently fall back to a legacy version or guess from a familiar name.

The former July 10 website cutoff was never backed by a frozen source corpus. This plan replaces that claim with a versioned set of actually reviewed rules and content. No historical reconstruction blocks the first engine slice.

## Successive runnable stages

Stages give the default order. They are small encounter increments, not whole-subsystem prerequisites. Move a required mechanic earlier for a worthwhile selected build; change the build when its exceptional behavior would distort the stage.

| Stage | Runnable result | Rules and content focus |
|---|---|---|
| **S1 — First complete fight** | Start, play, finish, save, and restore a small fight through Python and the terminal. | Initiative and turns; ordinary action costs; Stride/Step/Strike; checks/degrees/MAP; grid costs and reach; typed damage and explicit prototype defeat. Synthetic actors are allowed and labeled. This proves execution, not complete published-content support. |
| **S2 — Reviewed starter encounter** | A few fixed low-level builds and opponents with their applicable behavior closed. A real reaction works and survives saving at its prompt. | Review the complete selected sheets, traits, equipment, and basic-action boundary. Implement required positioning, action/attack exceptions, conditions, and reactions. For PC support, include applicable dying/wounded/recovery and Hero Points; do not silently treat PCs as disposable enemies. |
| **S3 — Small mixed party** | A martial, ranged, and caster role create useful different decisions in complete encounters. | Bring targeted saves, spell attacks, healing, and simple durations in early. Implement the selected casting-resource model, relevant range/ammunition/reload/hands rules, and targeting defenses. A targeted basic-save spell need not wait for area geometry. Builds remain specific reviewed choices, not class-wide support claims. |
| **S3i — Class and interaction expansion** | The first 16 additional encounters are accepted. Bring representative builds from all sixteen PC1/PC2 classes through level 1, then level 2. | Required class features, selected common combat content, and complete interaction encounters. Pull their needed shared mechanics forward from later stages. See the [accepted first increment](05-interaction-encounters.md) and [active extension](06-class-and-content-expansion.md). |
| **S4 — More varied environments** | Encounters combine the expanded class rules with richer maps and positioning. | Terrain, cover and environment cases beyond those required by S3i; larger footprints/reach or areas not already delivered. The maneuvers, shields, persistent damage, dim-light targeting for selected Light, and restrictions needed by level-1/2 classes belong to S3i. |
| **S5 — Broader everyday play** | Extend beyond the curated level-1/2 class and content catalog. | Higher-level features and content; Ready/Delay and additional action restrictions; recovery, hazards, senses, auras or afflictions beyond S3i requirements. Do not reschedule casting sources, focus, common consumables/runes, defenses or preparation already delivered by S3i. |
| **S6 — Selective specialist work** | Individually chosen specialist encounters or options. | Advanced flight/vertical or aquatic scenes, mounts, complex hazards, unusual timing, and summons/forms/companion behavior beyond the required S3i choices. Their basic class-required versions are part of S3i, not deferred here. |

**S1 has passed independent review; S2 implementation, independent play review, and correction checks are accepted. S3 implementation and its integrated play review are accepted, and normal CLI play is enabled.** Keep the first fight runnable while adding the selected rules and content. Do not reopen a broad foundations phase. [STATUS](../../STATUS.md) records completion evidence and current blockers.

### S1 working brief

Use a fixed open 7-by-5 grid and two clearly labeled synthetic, grounded, one-cell NPC-style actors. Give each one simple non-agile melee attack, ordinary reach and movement, and explicit fixture statistics. They are test actors, not abbreviated published stat blocks or supported PCs. At zero HP, the prototype marks that actor defeated and ends the fight when one side has no active actor.

Deliver a working Python package and numbered terminal controls for Inspect, Stride, Step, Strike, End Turn, Save, Load, Restart, and Quit. A person controls both actors; rolls are automatic. Keep fixture selection and statistics in content/setup data, not identity checks inside engine functions.

Resolve the applicable initiative/tie, movement, check, critical-damage, and turn rules from sources before coding their expected cases. Focus checks on degree boundaries and natural rolls, successive attacks, diagonals spanning movement actions, legal action spending/refresh, and invalid requests leaving state and randomness unchanged.

Save/load must preserve initiative, the active turn, actions, attack and diagonal counts, HP, positions, and random state. Run a complete encounter, test an alternate legal action sequence, and compare uninterrupted play with a saved-and-restored run. Record a first command/query timing baseline.

S1 does not require a reaction framework, PC recovery, spellcasting, terrain engine, or character builder. S2 adds the first real reaction and verifies its choice and continuation. Keep S1's omissions visible in the terminal/help and current support summary.

### S2 working brief

Use two fixed level-1 melee fighters against two Guard Dogs. A second positioning setup uses three dogs to exercise Pack Attack. The [reviewed rules and roster note](../implementation/s1-s3-rules.md) supplies the exact sheets and sources; source review alone does not admit a build to normal play.

Add PC knockout, dying, wounded, recovery, and Hero Points to the same running encounter. A Hero Point decision occurs after seeing a check and before applying its consequences. Initiative choices, recovery, and interrupted actions must remain playable after save/load. Keep unconscious creatures and their dropped equipment in the scene.

Then implement Reactive Strike, Vicious Swing, Pack Attack, and the basic positioning/equipment actions these builds need. A reaction may interrupt movement or an item action. The engine pays each cost once, remembers declined reactions, and resumes or stops the original action according to its actual result. Keep the fighter's Shield Block grant visible but inactive with this shield-free loadout.

Finish S2 by playing the reviewed encounter through public commands, exercising alternate choices, and saving during a reaction and its nested Hero Point decision. Independently check the consequential health, timing, positioning, and resource interactions before accepting the starter as supported.

### S3 working brief

Use a melee fighter, a bow fighter, and a warpriest against three Guard Dogs. This adds contrasting decisions to the existing fight without requiring a character builder or a large spell catalog.

- **Bow fighter:** model the shortbow's range, hands, ammunition, and extra critical die. Keep switching to the carried melee weapon an actual equipment action.
- **Warpriest:** use one reviewed prepared divine casting model, including its separate Heal-only font slots. Implement Divine Lance, Void Warp, Guidance, Stabilize, shared Light, and Heal at the selected rank, then a legal alternate Sure Strike preparation. Light replaces the optional unimplemented Read Aura selection; Read Aura/Identify Magic are deferred rather than advertised as working exploration content.
- **Spell procedures:** reuse checks, saving throws, damage, health, and interruption rules. Use direct functions for the selected spells. Guidance and Void Warp keep their source and exact expiry turn; they do not require a universal effects language.
- **Heal:** preserve the different one-, two-, and three-action modes. The modest open-map emanation required for three-action Heal is a small addition, not a prerequisite for a general area/terrain system.

Finish with complete mixed-party encounters, meaningful alternate actions, resource exhaustion checks, and saving during consequential choices. Include a knockout followed by healing, standing, and retrieving a dropped weapon. Repeat the public deterministic-dice and performance checks with these real interactions. Only the selected builds, loadouts, spell ranks, targets, and environment are claimed; broader class or book coverage remains future work. The original S3 encounter uses a 7×5 map. S3i adds a larger catalogued encounter with 60/65-foot boundary checks and a second larger map for the Heal area edge. Those complete routes now pass and have been independently reviewed.

### S3i working brief — accepted first increment and active extension

The original three terminal encounters proved a runnable engine with limited tactical variety. S3i adds eight S2 and eight S3 complete encounters with distinct decisions and explicit interaction evidence. All sixteen are independently accepted, the catalog contains 21 setups, and the full suite passes 211 tests. Different seeds of the same fight do not count as new encounters. Published low-level content is admitted only when its applicable behavior fits the current rules or a small reusable correction; defer costly bespoke content and S4 mechanics.

Each case must continue through an actual outcome and demonstrate its promised milestones. Use legal public commands to produce injuries, spent resources, reactions, and ongoing effects. Save/load may interrupt the same continuing fight. Focused boundary checks complement complete play instead of being counted as additional encounters.

Design, implementation, and independent testing are delegated. The supervisor maintains the [scenario matrix and acceptance plan](05-interaction-encounters.md). The pending stable-zero damage ruling remains outside the admitted paths; no dependent behavior is silently selected.

The user narrowed S3i to representative builds from all sixteen Player Core 1/2 classes: complete level 1 first, then level 2, with limited common spells/items and explicitly granted rune test equipment. The completed checkpoint accepted all sixteen selected level-1 builds and six level-2 builds. The user directly authorized an extension to finish the remaining level-2 representatives and add curated, meaningful level-1/level-2 class-feat alternatives beyond each fixed build's original selection. Every admitted option must work correctly; every printed feat, subclass and nested choice is not required. Keep skill/general feats separate from class-feat coverage, the shared domain menu small, and alchemical/casting selections finite. The [extension plan](06-class-and-content-expansion.md) owns scope and acceptance checkpoints.

## Broad families and their shared engine support

| Family | Shared rules to grow | Content it enables |
|---|---|---|
| Checks | Typed modifiers, degrees, MAP, saves, skills, selected rerolls/fortune rules. | Weapon attacks, maneuvers, spell attacks, saving-throw effects, Hero Points. |
| Actions and timing | Costs, activities and subordinate steps, reactions, turns, durations, later restrictions and extra actions. | Class reactions, multi-action abilities, buffs/debuffs, Ready, quickened/slowed interactions. |
| Space and targeting | Grid paths, reach, relationships, cover, line of effect, areas, later senses and movement modes. | Melee/ranged weapons, tactical movement, area spells, larger creatures, hazards. |
| Damage and health | Typed effects/components, defenses, healing, knockout/recovery, persistent damage. | Strikes, damaging spells, shields, consumables, resistant creatures, recovery options. |
| Equipment and resources | Hands, held/worn items, ammunition, uses, spell source and pool ownership. | Fixed loadouts, bows/reload weapons, shields, prepared/spontaneous/focus/innate casting, activated items. |
| Conditions and ongoing effects | Source/subject, values, applicable modifiers/restrictions, precise expiry and owned choices. | Off-guard/prone/frightened, combat maneuvers, common spell effects, auras. |

Do not implement an entire row before offering its first useful content. Preserve enough information for the next real interaction and accept local refactoring as the game grows.

## Content families

- **Player characters:** fixed checked builds first; later additional ancestry/background/feat/class selections. Character building and leveling remain separate features.
- **Equipment:** ordinary weapons, armor, shields, and hand state; then ammunition, consumables, common runes, and item activations.
- **Spells:** direct attacks, targeted basic saves, and healing; then conditions/durations, areas/Sustain, and selective utility or unusual effects.
- **Creatures/NPCs:** grounded combatants with manageable complete abilities; then maneuvers, reactions, defenses, casters, auras, and specialist movement.
- **Environments:** open grids, then walls/cover/terrain, simple hazards, and only later vertical or complex scenes.
- **Recovery:** explicit starting resources first, then supported between-encounter recovery and eventually daily preparation. No campaign simulator is required.

Small stat blocks do not guarantee cheap content. Review granted abilities, weapon traits, passives, and referenced universal rules before selecting the starter roster. The selected starter builds now have a source review in the linked implementation note; runtime admission follows the checks above.

## Content admission

1. Record sources and the exact build, rank, level, loadout, or mode being offered.
2. List the mechanical behavior and relevant dependencies in a short checklist. Identify shared procedures or the small handler that implements each; explain any behavior outside the enforced environment.
3. Missing mandatory encounter behavior blocks that definition from the normal catalog. Keep drafts outside it. Do not substitute a no-op or approximate effect during play.
4. Verify costs, targets, outcomes, timing, duration, traits, and resources with focused source-backed cases. Reuse established tests for parameter-only content; add interaction cases when behavior changes.
5. Exercise the addition in a complete encounter, with consequential save/load coverage when it introduces state or a choice. Independent review is periodic and risk-based, not mandatory certification for every entry.

Decide scope by value and cost:

- Existing procedures express it: add the definition.
- A short dedicated function expresses a useful exception: use that function.
- A missing common mechanic unlocks worthwhile play: schedule a small mechanic increment.
- One or a few bespoke options require a large new subsystem: defer or replace those options.

Do not build a registry of per-clause digests, dependency graphs, approvals, or evidence dimensions.

## GM judgment and uncertainty

Where rules delegate judgment, use a documented default or ask for a specific ruling through the terminal; save the resulting fact. Suitable examples include special map cover, situational skill DCs, and whether a significant NPC uses PC-style dying. Unsupported narrative actions can remain unavailable.

Do not replace a player's actual choice with a deterministic shortcut. Preserve ordering and allocation decisions where the applicable rules give them to that player. The user controls both sides initially, so opponent tactics do not need an AI policy.

**Current P0 questions: none.** A P1 implementation ruling is pending: positive lethal damage to an unconscious, non-dying PC already at 0 HP. Current source wording does not explicitly resolve this boundary. The proposed ruling applies a fresh knockout (dying 1/2 plus wounded and initiative before the current turn); the alternative is an explicit unsupported result. The supervisor has asked the user and will not accept the dependent branch before the answer. A silent no-op is not source-established. Until a ruling is accepted, the implemented boundary rejects any positive damage to a stable unconscious PC at 0 HP, including nonlethal damage; this broader restriction stays explicit in the support summary.

Exact starter builds and other focused rulings are researched within their implementation slices. If a source conflict changes core behavior or the product promise, record the smallest unresolved question in STATUS and clarify before dependent work.

## Research references

These are limited planning findings reviewed by a rules subagent on 2026-09-15. S1–S3 now have the linked implementation rules note and runtime checks. Later additions need their own applicable cases and source/version check.

| Source | Planning consequence |
|---|---|
| [Degrees of success](https://2e.aonprd.com/Rules.aspx?ID=2286) | Keep the natural die and adjustment order, not just a final Boolean success. |
| [MAP](https://2e.aonprd.com/Rules.aspx?ID=2289) | Preserve attack-trait and current-attack context. |
| [Actions](https://2e.aonprd.com/Rules.aspx?ID=2335) and [disruption](https://2e.aonprd.com/Rules.aspx?ID=2342) | Activities have subordinate steps; interruption must preserve paid costs. |
| [Reactive Strike](https://2e.aonprd.com/Actions.aspx?ID=2256) | A real early reaction tests MAP exceptions, trigger details, and limited disruption. |
| [Grid movement](https://2e.aonprd.com/Rules.aspx?ID=2356) | Diagonal accounting spans movement actions in the turn. |
| [Start turn](https://2e.aonprd.com/Rules.aspx?ID=2428) and [end turn](https://2e.aonprd.com/Rules.aspx?ID=2430) | Explicit timing must coexist with player-owned ordering choices. |
| [Knockout](https://2e.aonprd.com/Rules.aspx?ID=2324), [recovery](https://2e.aonprd.com/Rules.aspx?ID=2326), and [Hero Points](https://2e.aonprd.com/Rules.aspx?ID=2333) | Ordinary PC support needs more than subtracting HP and removing actors. |
| [Resistance](https://2e.aonprd.com/Rules.aspx?ID=2318) | Preserve damage-effect grouping and applicable recipient choices. |
| [Persistent damage](https://2e.aonprd.com/Conditions.aspx?ID=86) | Damage, recovery, and assistance need correct timing and bounded judgment. |
| [Basic saves](https://2e.aonprd.com/Rules.aspx?ID=2297) and [Heal](https://2e.aonprd.com/Spells.aspx?ID=1554) | Shared save procedures help many spells; action modes can change targeting and effects. |
| [Focus spells](https://2e.aonprd.com/Rules.aspx?ID=2228) | A shared pool does not erase individual casting sources and statistics. |
| [Cover](https://2e.aonprd.com/Rules.aspx?ID=2372), [line of effect](https://2e.aonprd.com/Rules.aspx?ID=2382), and [detection](https://2e.aonprd.com/Rules.aspx?ID=2414) | Some facts are relative between actors; future support must preserve those relationships. |
