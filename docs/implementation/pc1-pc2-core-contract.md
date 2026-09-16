# PC1/PC2 core implementation contract

Design handoff, 2026-09-15. Inspected engine baseline: `185e52b`.
This document specifies code boundaries; the class-family source notes specify rules and mandatory options. It does not establish additional PF2e rules by assertion.

## Scope and sequence

- Implement one selected representative build for each of the 16 Player Core 1/2 classes at level 1, including that build's fixed grants and applicable behavior. Printed subclasses and nested options outside the approved roster are reference inventory, not required delivery. Optional feats, spells, and equipment use curated common selections.
- Then implement level 2 within S3i. Keep level, HP, proficiencies, spell ranks, attack modifiers, and DCs explicit; do not hardcode the first level's values in procedures.
- Permanent common runes may use explicitly labeled higher-item-level test grants. Actor level remains unchanged by those grants.
- After both levels work, identify further generalization opportunities from actual duplication. Do not front-load a broad rewrite.
- Daily preparation, loadout, and necessary exploration/context choices are local explicit inputs. No campaign simulator, network service, plugin registry, event bus, or effect language.
- Mandatory familiars, companions, focus features, forms, and other grants on a selected representative cannot be silently omitted. Unselected subclass and nested-option grants may remain in the source inventory; optional content selection is not permission to defer a grant that the approved roster actually selects.

## Ownership and compatibility

The **core owner** exclusively edits `model.py`, `encounter.py`, `persistence.py`, and `__init__.py`. Core owns transactional state, dice cursors, action/resource commitment, choices, timing, and save validation. One terminal owner edits `terminal.py`; one catalog integrator edits `content.py`. Family owners author separate definition/feature modules and tests.

Wave 1 helpers are independent of `Encounter`, `CreatureState`, and persistence. Their records are ordinary frozen dataclasses, with tuples/frozensets for collections. The helper module defines its own input/output records. Core imports those records and constructs snapshots or stores them directly; helpers must not import `model.py` except the geometry owner, who may import the existing `Position`.

Helpers do not mutate arguments, publish events, choose for players, advance time, or invoke public commands. A helper that rolls receives `roll: Callable[[int], int]`; it never creates an RNG. Query helpers never roll. Legality helpers return explicit allowed choices or a reason; they do not select the first legal option silently.

Existing `Encounter.start/execute/choose/inspect/options/save/load`, command records, `resolve_check`, `combine_modifiers`, and `resolve_damage(DamagePacket, ...)` remain usable while the new paths integrate. A save-version increment is appropriate when authoritative state changes; migrations are not a prerequisite. Unknown incompatible versions must reject clearly.

The signatures below freeze the first helper handoffs. Owners may add a sourced, necessary optional field or a named family helper within their owned file; notify core before changing shared constructor/function semantics. No separate approval registry is needed.

## Wave 1A: check and condition helpers

**Owner scope:** new `src/pf2e/conditions.py`, `tests/test_conditions.py`. Import existing `Modifier` from `checks.py`; do not edit core files.

```python
ConditionValue(kind: str, value: int, source_id: str)
CheckContext(
    statistic: str,             # attack, armor_class, fortitude, athletics, etc.
    attribute: str | None,      # explicit; never infer from attack name
    traits: frozenset[str] = frozenset(),
)
ActionContext(action_id: str, traits: frozenset[str])

condition_modifiers(
    conditions: tuple[ConditionValue, ...], context: CheckContext,
) -> tuple[Modifier, ...]
condition_restrictions(
    conditions: tuple[ConditionValue, ...], context: ActionContext,
) -> tuple[str, ...]            # stable reason identifiers, empty if none
effective_condition_value(conditions, kind: str) -> int
```

Source readers determine the supported condition set and reduction/removal rules. Unknown names must not be treated as implemented no-ops. Pure helpers may return applicable modifiers from several causes; `combine_modifiers` remains the stacking authority. Conditions whose effect depends on a specific target or cause need that eligibility established by core and passed as explicit applicable condition facts.

**Core state contract:** retain separately sourced effects. Each needs `effect_id`, `kind`, `source_actor_id`, `target_actor_id`, `value`, and a concrete expiration record. Minimum expiration facts are `anchor_actor_id`, `boundary` (`start` or `end`), and `occurrence`; other duration kinds are added only for admitted mechanics. Do not force sustained effects, encounter-long states, and timed item expirations into source-next-start semantics. Core calls named start/end procedures; no subscription system.

**Core check contract:** one saved check context carries check owner, statistic/attribute, DC, typed modifier snapshot, traits, pre-roll choices already made, result when rolled, fortune/reroll use, and parent continuation. Reuse it for attacks, saves, skills, and reaction checks. Validate the stored arithmetic from those facts and admitted sources.

## Wave 1B: typed damage helpers

**Owner scope:** `src/pf2e/damage.py`, `tests/test_damage_components.py`. Preserve existing dataclass positional arguments and simple entry point.

```python
DamageTerm(
    source: str,
    damage_type: str,
    dice: tuple[int, ...],      # individual die sizes; empty for flat damage
    modifier: int = 0,
    tags: frozenset[str] = frozenset(),  # e.g. precision/material facts
    critical_mode: str = "double",     # double, unchanged, critical_only
)
DamageDefense(
    kind: str,                 # immunity, weakness, resistance
    applies_to: str,           # admitted damage type or supported trait category
    value: int = 0,
    exceptions: frozenset[str] = frozenset(),
    source: str = "",
)
DamageGroup(
    group_id: str,
    results: tuple[DamageResult, ...],
    source_kind: str,           # strike, spell, persistent, other admitted source
    traits: frozenset[str] = frozenset(),
)
DamagePartRef(result_index: int, component_index: int)
DefenseChoice(defense_source: str, eligible_parts: tuple[DamagePartRef, ...])
DefenseSelection(defense_source: str, part: DamagePartRef)
DamageMitigation(results: tuple[DamageResult, ...], total: int, applied_defenses: tuple[str, ...])
TemporaryHPResult(temporary_hp: int, damage_to_hp: int, absorbed: int)

roll_damage_terms(terms: tuple[DamageTerm, ...], roll, *, critical=False) -> DamageResult
damage_defense_choices(group: DamageGroup, defenses: tuple[DamageDefense, ...]) -> tuple[DefenseChoice, ...]
apply_damage_defenses(group: DamageGroup, defenses: tuple[DamageDefense, ...], selections: tuple[DefenseSelection, ...] = ()) -> DamageMitigation
absorb_temporary_hp(amount: int, temporary_hp: int) -> TemporaryHPResult
```

Add defaulted metadata to `DamageComponent` as needed to preserve term tags and critical behavior. `DamageResult` must retain rolled components; mitigation must remain explainable without rolling again. Existing basic-save rounding and critical-only damage are distinct operations. The damage owner derives their exact ordering and grouping from the family source requirements. Do not treat precision as an ordinary extra weapon die or apply a weakness independently to every arbitrary component.

The divine-family source review identifies Spring 2026 broad resistance applying once to the single Strike/spell effect and requiring an eligible-component choice. Preserve group identity and return any rule-owned choice; never multiply a broad defense merely because damage was split into terms. The martial-family requirements also include combining Flurry damage for defenses. Core constructs the sourced group explicitly; the helper must not guess it from a shared source string. Different recipients still have different defense applications. Bomb primary/splash outcomes and critical treatment come from the alchemy-family note; preserve splash tags and undoubled terms rather than routing splash through ordinary Strike doubling or Strength damage.

**Core continuation contract:** a committed damage application stores attacker/source, recipients, check context, rolled damage, current mitigation/reaction step, already-offered/declined reactions, and parent continuation. Apply health only once after the applicable decisions. Temporary HP is a separate field/effect from HP and max HP. Core owns health transitions and Heroic Recovery.

## Wave 1C: casting-source helpers

**Owner scope:** new `src/pf2e/casting.py`, `tests/test_casting_resources.py`. No import of `model.py` or `spells.py`; source data comes in as records.

```python
SpellAccess(spell_id: str, rank: int, cantrip: bool = False, signature: bool = False)
CastingSource(
    source_id: str,
    kind: str,                 # prepared, spontaneous, focus, innate
    tradition: str | None,
    attribute: str | None,
    attack_modifier: int,
    dc: int,
    spells: tuple[SpellAccess, ...],
)
CastingResource(
    resource_id: str,
    source_id: str | None,     # None only for the actor's shared focus pool
    kind: str,                 # prepared_slot, rank_slots, focus_points, innate_uses
    rank: int,
    capacity: int,
    remaining: int,
    spell_id: str | None = None,  # prepared or spell-specific innate use
)
CastSelection(source_id: str, spell_id: str, rank: int, resource_id: str | None)
ResourceSpend(resource_id: str, amount: int)
CastPermission(selection: CastSelection, spends: tuple[ResourceSpend, ...])

available_casts(sources, resources) -> tuple[CastSelection, ...]
validate_cast(selection: CastSelection, sources, resources) -> CastPermission
```

Use a dedicated exception with a stable reason for invalid selection. Explicit casts with several eligible resources require a choice; helpers must not select a resource implicitly. A cantrip has no expenditure. Source-specific prepared grants such as font slots retain their provenance through resource IDs/source associations. Shared focus points belong to the actor and must not be duplicated per class feature. SpellAccess entries describe admitted ranks; access to unlisted ranks must follow an explicitly implemented rule, never the presence of a larger slot alone.

Core spends the returned resources only at the correct commitment point and records expenditure in the continuation. Prepared slots already supported by the engine can be adapted into these snapshots initially. Daily recovery/refocus is a named local operation with source-established time/context requirements, not a generic counter reset.

Core extends `Cast` with defaulted source/rank information as necessary while preserving old calls. Spell targeting, traits, action cost, concentration restrictions, and effects remain outside this resource helper. Shared spell attack/save handlers use the selected source's actual statistic and DC. Numeric spell helpers receive rank explicitly, even while only rank 1 is admitted.

## Wave 1D: equipment helpers

**Owner scope:** new `src/pf2e/items.py`, `tests/test_items.py`. No `model.py` imports. Definitions carry their source URLs; family readers select the actual content.

```python
ItemInstance(
    instance_id: str, definition_id: str, quantity: int = 1,
    charges: int | None = None, hp: int | None = None,
    rune_ids: tuple[str, ...] = (),
)
ShieldProfile(definition_id: str, ac_bonus: int, hardness: int, max_hp: int, broken_threshold: int)
ShieldBlockResult(prevented: int, damage_to_actor: int, damage_to_shield: int, shield_hp: int)
WeaponRuneProfile(potency: int = 0, striking_dice: int | None = None, property_runes: tuple[str, ...] = ())

shield_block_result(incoming_damage: int, profile: ShieldProfile, shield_hp: int) -> ShieldBlockResult
weapon_rune_dice(base_dice: tuple[int, ...], profile: WeaponRuneProfile, *, striking_applies: bool = True) -> tuple[int, ...]
```

Add dedicated sourced activation profiles/helpers for the curated consumables and permanent runes, rather than a generic item script. `weapon_rune_dice` applies fundamental weapon-die changes only; precision, deadly, property damage, and action-granted dice retain their own rules. The alchemy review identifies Bestial Mutagen as excluding striking: the sourced attack/effect context passes `striking_applies=False`; do not infer eligibility from an attack's name. Potency feeds a typed item modifier rather than altering a previously authored attack total invisibly.

Core owns inventory locations, hands, held/raised shield state, Interact/action costs, activation targets, consumption, expiration, and create/destroy records. Distinct copies can share a definition but need distinct identity where charges, HP, or attachments differ. Alchemical creation records producer/ability and admitted definition; do not fabricate untracked starting inventory. Created items and consumed items must survive save/load validation. Higher-level test grants belong explicitly in setup/loadout metadata; they do not relax actor-level validation.

## Wave 1E: geometry helpers

**Owner scope:** new `src/pf2e/areas.py`, `tests/test_areas.py`. Import existing `Position` and reuse `space.py` distance functions; do not change `Position`, `space.py`, or core until the required movement cases are specified.

```python
Footprint(origin: Position, width_cells: int = 1, height_cells: int = 1)

occupied_cells(footprint: Footprint) -> tuple[Position, ...]
footprint_distance_ft(first: Footprint, second: Footprint) -> int
emanation_cells(origin: Footprint, radius_ft: int) -> frozenset[Position]
burst_cells(origin: Position, radius_ft: int) -> frozenset[Position]
```

The geometry owner must source whether a particular origin is a cell center or grid intersection before adding a function for that shape. The `burst_cells` signature uses `Position` as an integer grid-intersection coordinate, not an actor's center; document this distinction and test it. Add named line/cone functions only with a concrete required origin/direction convention. Area helpers return candidate cells; core applies map clipping, line of effect, eligibility, willingness, and save ordering.

Flight, alternate movement, visibility, and form size are mandatory where the census requires them, but their state is not guessed in this first geometry slice. Family readers identify exact requirements; core and geometry owner then add the smallest coordinate/movement extension together. A one-cell bright-map restriction must not be presented as implementation of an option whose required behavior contradicts it.

## Class state and local preparation

Keep selected build choices in immutable reviewed definitions: class, level, named subclass selections, granted ability IDs, prepared/loadout choices, and source notes. Parameter-only variants can use ordinary constructor helpers or `dataclasses.replace`. Do not make sheet text the only representation of a mandatory active feature.

Use named small records for actual class state: for example a hunted target, active rage, a stance, or a class resource. A dedicated feature procedure may compute strike additions, permissions, and effect changes from explicit facts. Core applies the resulting changes at the right step. Do not route rules by actor display name, call nested `execute`, or add a universal `dict[str, Any]` feature-state interpreter.

For setup/preparation, preserve exact catalog admission. Add a validated preparation/loadout record when selected choices require it; only reviewed option/definition IDs are accepted. Persist those choices. Direct local methods/commands for daily preparation or a timed activity can be added when required; no campaign calendar or simulated travel is necessary. A contextual input records a real declared circumstance, not a switch that bypasses a mandatory rule.

## Owned actors and forms: coordinated core slice

The existing save requires the exact starting actor set and binds each actor to its original definition. Keep that binding for initial actors, while admitting explicit created actors:

```python
ActorOrigin(kind: str, owner_actor_id: str | None, source_id: str | None, instance_number: int | None)
SubordinateActions(owner_actor_id: str, subordinate_actor_id: str, actions_remaining: int, parent_continuation: ...)
FormState(form_id: str, source_id: str, expiration: ...)
```

Initial companions/familiars can be reviewed placements with an owner relation. A summoned actor has a reviewed definition and created origin, unique ID, source effect, and supported lifetime. Saves require every original actor and validate each additional actor's origin/capacity/lifetime. Removed created actors may be removed explicitly once no pending reference needs them; retain whatever origin counter prevents ID reuse.

Minions are separate from independently rolled initiative. A saved subordinate-action record temporarily selects the acting creature and resumes its owner/parent afterward. Do not accidentally refresh three actions and a reaction on every subordinate activation. Permanent companions and summoned minions use their source-established command/autonomy rules; ownership alone does not define behavior.

Core must change these assumptions together: actor-set equality, initiative membership, inactive action-resource validation, inspection order (currently initiative only), and the team-outcome predicate. Whether a surviving subordinate can keep an encounter active requires the applicable control rules and documented outcome policy, not an incidental dictionary scan.

Forms stay on the same actor and definition ID. Effective-stat/attack/size/movement queries apply the admitted form override and applicable stacking restrictions. Do not overwrite printed base statistics and then attempt to reconstruct them when the form ends.

## Current compatibility traps to cover

- Void Warp resolution and saved-check validation use literal DC 17; both must use source DC.
- `active_effects` and their serializer admit only Guidance/enfeebled and one expiry shape.
- Enfeebled currently retains only the strongest effect; broader overlapping durations require separately retained sources.
- Reaction refresh and save legality recognize only `reactive_strike`.
- Save validation assumes attacks made cannot exceed actions spent. Compound attacks require source-informed replacement bounds and committed action facts.
- Save movement bounds assume base land Speed; forms, modifiers, extra movement, and subordinate actions need effective context.
- Inventory validation assumes unique original weapon strings and fixed worn equipment; consumption, shields, copies, and creation violate it.
- Save validation assumes all actors roll Perception initiative and every active actor has at most three ordinary actions.
- Existing `DamageResult` validation distinguishes a small list of damage contexts. New component semantics must be encoded and validated together, preserving existing critical/basic-save/deadly cases.
- Existing catalog tests hardcode 21 setups/eight additions per stage. Preserve their original groups while extending the overall catalog expectations.

## Integration and evidence

1. Implement/test the independent Wave 1 helpers in their owned files. Core introduces only the state/query/continuation records needed for the first sourced family.
2. Integrate checks/conditions and damage timing; then casting sources and admitted spell behaviors. Add inventory and owned-actor/form paths as their mandatory families require them.
3. Admit class-family definitions only when their mandatory behavior works. Add terminal controls based on engine options and explicit choices.
4. Finish level-1 family and mixed encounters; then extend level-2 mandatory features/options and repeat relevant encounters. Keep rank/level arithmetic parameterized throughout.
5. After both levels work, report concrete repeated code and measured costs before proposing further generalization.

Use the existing bounded `EncounterHarness`. Keep focused helper tests independent of complete fights. Add S1 mechanism fixtures, S2 class-family fights, and S3 mixed-party interactions through public commands; the supervisor/source readers assign the final scenario matrix. Every new pause needs save/load and continued-play evidence with no repeated cost/roll. Every resource family needs depletion and rejected-request atomicity. Mandatory options need a coverage row, but parameter-only variants need not each duplicate an entire encounter.

Default encounter bounds remain 160 commands, 40 choices, 12 rounds, 2,000 events; tighten small cases and justify measured exceptions. Tests run serially per owner. Run complete encounters after coherent integration and one full suite at checkpoints, not after each definition. Terminal capture and subprocess time remain bounded. Benchmark an actual expanded mixed sequence rather than treating the existing S1 EndTurn benchmark as class-expansion evidence.

The old stable-zero damage limitation remains explicit until its outstanding ruling is resolved. It is not permission to skip a newly required affected feature: report any material dependency to the supervisor before admitting that path.
