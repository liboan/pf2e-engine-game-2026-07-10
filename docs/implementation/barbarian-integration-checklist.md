# Barbarian: two playable integration slices

Read/design handoff, 2026-09-15. Runtime inspected after common Trip/Grapple/Escape/Demoralize integration; no runtime changes or tests performed by this investigation. This is a bounded implementation checklist, not the later generalization audit.

## Decisions fixed for these slices

- **Slice 1 (completed admission):** Bear Animal Barbarian's ordinary Rage and Quick-Tempered, claws/jaws damage, temporary HP, restrictions, expiry, save/load, and complete encounter formed the initial accepted slice. It remains the regression baseline.
- **Slice 2:** preserve the accepted Bear, Cat, Frog, and eight Dragon representative builds, then connect their selected level-2 behavior. The remaining Animal variants, Bull, Fury, Giant, Spirit, and Superstition details remain source reference inventory unless a later representative is explicitly selected. Level 2 is subsequent work.
- Ordinary class feat menu: **Raging Intimidation**, plus **Moment of Clarity** when slice 2 lands. Fury has both, assigned to distinct ordinary/bonus feat selections. No Sudden Charge dependency in this Barbarian increment.
- Use a **longsword** for ordinary fixed armed loadouts and a **Large longsword** for Giant: d8 slashing, versatile P, one hand, unchanged reach/die. Base price 1 gp/Bulk 1; Large price 2 gp/Bulk 2. This replaces the staged greataxe choice, whose sweep is not yet implemented. Keep the greataxe draft unadmitted.
- Keep existing exact setup admission. Import explicitly named ready definitions/setups into `content.py`; do not merge the entire staged `EXPANSION_CREATURES/SETUPS` maps.

Sources supplementing [the martial source note](pc1-pc2-martial-rules.md): [Rage/Quick-Tempered](https://2e.aonprd.com/Classes.aspx?ID=57), [temporary HP](https://2e.aonprd.com/Rules.aspx?ID=2321), [Moment of Clarity, PC2 p77](https://2e.aonprd.com/Feats.aspx?ID=5809), [longsword](https://2e.aonprd.com/Weapons.aspx?ID=386), [Warrior background](https://2e.aonprd.com/Backgrounds.aspx?ID=445), [Spirit](https://2e.aonprd.com/Instincts.aspx?ID=12), [ghost touch](https://2e.aonprd.com/Equipment.aspx?ID=2840), [Superstition](https://2e.aonprd.com/Instincts.aspx?ID=13), [Shove](https://2e.aonprd.com/Actions.aspx?ID=2380). Rechecked these relevant entries during this read. Use the martial note's current errata/table for animal and dragon variants.

## Existing footholds; do not rebuild them

`CreatureState.barbarian_state`, `PendingChoice.barbarian_choice`, `BarbarianState`, `ActiveRage`, their JSON serializers, and startup lookup of `BARBARIAN_INITIAL_STATES` already exist. `family_martial.py` dispatches Barbarian commands/choices. `FamilyProcedureContext` already exposes shared checks, choice creation, action commitment, conditions, and damage/health integration. `DamageTerm`, `roll_damage_terms`, defense groups, and `absorb_temporary_hp` exist as pure helpers. Core already has sourced conditions, owner start/end counters, and `world_time_seconds`.

The original staged integration gaps described by the checklist have since been closed for the accepted Bear, Cat, Frog, and eight Dragon representatives. Remaining bullets cover follow-up validation and unselected variants; they are not evidence that the accepted roster is unplayable.

## Repair the staged helper/content before admission

- [ ] `activate_rage` incorrectly picks the numerically larger temporary-HP pool. Replace that rule with an explicit **keep existing / gain new** choice, including equal or smaller new pools. Preserve the chosen source and duration. Fix the test that currently blesses automatic rejection of a smaller Rage pool.
- [ ] Correct the ordinary fist to agile, finesse, nonlethal, unarmed; the current Str+4 build's fist damage modifier is **+4**, not 0. Keep Strength for its chosen attack calculation; finesse is optional Dexterity use, not forced Dexterity.
- [ ] Add `class_feat_id` to `BarbarianBuildChoices` and `BarbarianState`, retaining `bonus_feat_id` for Fury. Validate separate selections and no duplicate feat. Derive `definition.feats` from the normalized choices; currently Fury's default exists only in state, and every ordinary class-feat slot is empty.
- [ ] `has_intimidating_glare` / `action_traits_with_instinct_features` must recognize Raging Intimidation in either selected slot. Glare's grant still requires trained Intimidation. The outer `_run_family_action` gate must receive the modified Demoralize traits too; otherwise it rejects before the inner handler can add `rage`.
- [ ] Use a legal shared fixed ancestry/background sheet: Human, Skilled Human (Medicine), Natural Skill (Acrobatics/Society), Warrior (Intimidation/Warfare Lore/Intimidating Glare). Class training: Athletics plus Crafting/Nature/Survival. Keep Str4/Dex1/Con3/Int0/Wis1/Cha0, HP23, AC18, attacks+7, Fort8/Ref4/Will6. Record the actual grants, skills, and gear money. This avoids adding Assurance solely to repair the staged Farmhand sheet. The duplicated Glare grant from Raging Intimidation grants no extra feat; it is already present.
- [ ] `validate_barbarian_state` must compare active mode damage type/traits/ghost-touch flag to `valid_rage_mode`, validate accepted-effect rows and unique witnesses, and reject impossible future starts. Persistence must bind instinct/nested option/feat/weapon choices to the canonical initial state, require Barbarian state for admitted Barbarians, and reject state on other classes. Merely checking `class_name` is insufficient.
- [ ] Rage procedures must reject already-raging/fatigued actors **before** offering mode choices, call the shared action-permission gate, and complete the action/turn when the last action was spent. Current `handle_action` returns an event without the ordinary completion hook.

## Slice 1: minimum hook map

### A. Initiative and committed Rage

Add only the following ordinary state fields/records (defaulted for existing saves/builds after a version bump):

```python
EncounterState.quick_tempered_decided: set[str]
FamilyProcedureContext.quick_tempered_trigger: bool = False
CreatureState.temporary_hp_expires_at_seconds: int | None = None
BarbarianState.next_rage_instance: int = 1
RageModeChoice(..., mode_id: str | None = None,
               temporary_hp_choice: str | None = None)  # keep_existing / gain_new
```

Reuse `barbarian_choice` for the named Rage substeps; extend `procedure_id` to `barbarian:quick_tempered`, `barbarian:rage_mode`, and `barbarian:temporary_hp`. No arbitrary payload dictionary or new registry.

- [ ] `_continue_initiative_initialization`: after a PC's initiative Hero decision, offer their eligible Quick-Tempered accept/decline before proceeding to the next actor and before tie completion. Actors without a Hero choice still receive it. This ordering is a fixed local UI policy; no combat/time elapses between these initialization choices. A Hero reroll does not offer a second Quick-Tempered for the same initiative initialization.
- [ ] Accept constructs a normal family context for that **pending owner**, setting `quick_tempered_trigger=True`; do not route through `_resolve`'s active-turn requirement or public `execute`. Mode/temp-HP choices retain that origin. Mark decided only after decline or completed activation, then resume initiative initialization. Ordinary Rage has cost 1; Quick-Tempered has cost 0; neither increases MAP.
- [ ] Eligibility: no current Rage, fatigue, encumbrance, or heavy armor. Add explicit reviewed `armor_category` and carried item Bulk facts to the fixed loadout metadata; do not recognize an armor name or derive encumbrance from “number of items.” A named local starting-condition context may supply fatigue, but ordinary loaded inventory determines encumbrance. All playable default builds meet requirements.
- [ ] Save initialization permits these exact family choices while `initiative_finalized=False`, all actions remain zero, and the tied order is unfinished. Validate owner, undecided trigger, exact options, and command origin. A forged `RageModeChoice(command_kind="QuickTempered")` during a normal turn must reject.
- [ ] Ordinary and free activation collect mode/pool choices **before** commitment. Extend `activate_rage(..., temporary_hp_choice=None)` to require a supplied choice when a grant is eligible and an old pool remains. A temporary-HP cooldown suppresses the grant, not Rage itself. Core consumes a unique `rage:{actor}:{instance}` ID only on commitment. This avoids same-timestamp source collisions.
- [ ] After choosing, commit one state change containing Rage, selected pool/provenance/duration, any Superstition healing, and cost. Call `_complete_action` only for ordinary Rage; initialization resumes its own driver. No re-payment when a saved choice resumes.

### B. Attacks, restrictions, damage, and end conditions

- [ ] `_attack_usable` (and thus options/select/reactions/Escape profiles): Animal's granted attack IDs are available only during Rage; weapons unavailable during Animal Rage; ordinary unarmed attacks remain available. Use exact IDs from `animal_attack_ids`, not a name prefix. Apply the same rule to forced/explicit attack IDs.
- [ ] `_require_action_permitted`: apply selected feat trait changes, then `action_allowed_while_raging`, then existing condition checks. Preserve Seek's exception. `_cast` already uses the gate; family commands must too. Queries hide unavailable actions without mutating state; execute revalidates.
- [ ] `_roll_attack_damage` receives `target_id` and constructs base/extra weapon dice, separate `rage_strike_adjustment.damage_term`, and existing deadly term using `roll_damage_terms`. Keep different damage types separate. Pass actual attack traits/item ID, target ID, and world time. Base and Rage terms double on criticals; agile halves the flat Rage bonus only. No Rage AC penalty.
- [ ] Add one shared core `_absorb_damage_temporary_hp(state, target, amount)` wrapper around `absorb_temporary_hp`. Invoke it exactly once in **all three** real paths: `_resolve_attack_result`, `_apply_spell_damage`, `apply_family_damage`, before proposing PC health or subtracting ordinary HP. When pool reaches zero, clear its source/expiry. Preserve rolled `DamageResult` and record absorbed/remaining amounts in events/pending health data; do not falsify rolled damage to encode absorption.
- [ ] A Heroic Recovery pause occurs after temporary-HP absorption has committed to the draft and retains that fact. Choosing normal/Heroic later applies only the stored HP transition. Save at that pause must not absorb again. The stable-zero unsupported rule uses positive **remaining HP damage**, while preserving the existing ruling boundary.
- [ ] Add `_refresh_barbarian_state(state, actor, *, encounter_ended=False)` calling the existing ending helpers. Invoke after clock advancement, health transition to unconscious/dead, and encounter outcome. Clear only a temporary pool whose source equals the ended Rage source. An unrelated replacement pool survives. Source cleanup occurs before a healed actor can act again. No voluntary End Rage action.
- [ ] Preserve the existing six-second encounter clock convention for this increment; document its round-boundary granularity. Check the helper's 60-second expiry at clock advancement and before resolving actions. Do not silently advance time while handling choices. Cooldown timestamps survive save/load and the later local encounter handoff.
- [ ] Expose `barbarian_state` or an immutable `BarbarianView` plus temp-HP source/expiry in `ActorView`. Add `rage` to engine action options when legal. The separate terminal owner only renders this data, submits `Rage()`, and displays normal choices.

### C. Slice-1 acceptance

The completed Bear + Raging Intimidation acceptance exercised the existing ordinary guard fixture (with authored save modifiers), healthy startup, Quick decline/accept routes, Rage temporary HP absorption, jaws/claw damage and agile MAP, weapon rejection, Glare Demoralize, saved pending choices, encounter-end cleanup, paired initiative ordering, and the saved temp-HP-to-health/Recovery boundary. Expiry and denied eligibility use focused public/context cases, not 60-second sleeps.

Run the helper file, new `test_barbarian_runtime.py`, and touched health/skill/persistence selections serially. Then one complete encounter module and the integration checkpoint suite. Do not claim the remaining instincts are playable yet.

## Slice 2: selected representative follow-up

### A. Parameter variants and small feature procedures

- [ ] Preserve the 11 accepted representative builds (Bear, Cat, Frog and eight Dragons) through save/load. Remaining Animal variants, Bull, Fury, Giant, Spirit and Superstition are source reference inventory, not required delivery unless separately selected.
- [ ] Add `MomentOfClarity(FamilyCommand)` in `barbarian.py` and a saved `clarity_until_end_count`. It requires the selected feat and current Rage, costs one action, has concentrate/rage, and allows concentrate until the actor's current turn ends; ending Rage also removes it. Reuse `_source_turn_end`/Rage cleanup. Validate/inspect/options/export like Rage. Fury selects ordinary Raging Intimidation and bonus Moment of Clarity; another ordinary build may choose Clarity to prove the permission exception matters.
- [ ] **Animal trait machinery:** extend `Trip`/`Grapple` with defaulted `maneuver_attack_id`; reject simultaneous item/attack selections. `_check_maneuver` accepts the currently usable granted unarmed profile with the matching trip/grapple trait and its reach without requiring a free hand. Persist that selector in pending commands. Do not offer the “drop weapon to avoid critical failure” option for an unarmed profile. Add brawling-group metadata to granted attacks without adding level-5 specialization.
- [ ] **Bull:** its mandatory shove trait needs real `Shove(target_id, maneuver_item_id=None, maneuver_attack_id=None)`, using the existing Athletics/MAP/Guidance/Hero check path vs Fortitude DC. Add the named outcome and saved displacement/follow choice: success 5 feet, critical success up to 10; critical failure prone. Validate legal outward cells, bounds/occupancy; forced target movement triggers no movement reaction. Optional following is a subordinate Stride in the same direction/distance and retains ordinary movement/reaction continuation without another action charge. This is required by the Bull option, not an optional feat expansion.
- [ ] **Dragon:** store mode once per Rage; all eight choices use their exact typed +4 term and Rage traits. Base mode stays ordinary +2. Changing attack damage type or accepting a Hero reroll cannot change the Rage mode. No breath weapon or level-7 specialization.
- [ ] **Giant:** derive clumsy 1 from actually wielding the selected oversized weapon **in combat**, independent of Rage, through `_conditions_for_actor`. This makes it unremovable while its cause remains and feeds AC/Reflex/Dex skills with existing stacking. Releasing/stowing removes that contribution, without removing unrelated clumsy. Add +6 only for melee Strikes using that oversized weapon; other melee attacks use +2. Large item size/Bulk never change actor footprint, reach, or d8.
- [ ] **Spirit:** spirit mode's ghost-touch fact tags the **whole weapon/unarmed Strike**, not only the flat spirit term. Feed it into `DamageGroup`/`DamageDefense.exceptions` with a single canonical `ghost_touch` tag. Use a catalogued S1 defensive fixture exercising a ghost-touch-excepted resistance through actual Strike resolution. Such a fixture tests the resistance interaction; it is not a claim that a published incorporeal monster's complete movement/traits have been implemented. If a published incorporeal opponent is admitted, its full applicable traits are additional admission work.

### B. Superstition must use real casting/effect/check events

Add short direct core calls, not event-log parsing:

```python
_record_spellcast_witnesses(state, caster_id, witness_ids)
_record_magic_acceptance(state, target_id, effect_id, *, ongoing: bool)
_remove_magic_acceptance(state, target_id, effect_id)
_spell_save_modifiers(state, target, *, against_magic: bool) -> tuple[Modifier, ...]
```

- [ ] At actual `_cast` commitment, record which conscious observing actors witnessed this Cast a Spell once, before possible interruption. Current open/bright/fully-observed maps can derive witnesses explicitly; any departure uses declared visibility context. Rejected casts and target/slot queries never create witnesses. Do not identify a caster by class label. Keep only the latest timestamp per caster; saves preserve it. Witnessing an attempted cast counts even if its effect is later disrupted; this records the action witnessed, not a successful effect.
- [ ] `_roll_void_warp_save` and any new spell-save route add `superstition_save_modifier(..., against_magic=True)` to the typed snapshot, alongside condition modifiers/Guidance. Corresponding saved-check validation reconstructs the same modifiers. The +2 status bonus does not stack with Guidance's +1. A skill Fortitude **DC** or a nonmagical save does not receive it. Continue using the target-owned Hero choice.
- [ ] Guidance currently applies without a willingness choice. For a raging Superstition target, add one saved accept/refuse choice before application. Heal's existing willingness decision must call the same acceptance hook; three-action Heal needs a decision for each affected Superstition recipient whose acceptance matters. Never infer willingness merely from team membership.
- [ ] Accepting an effect applies frightened 1 through sourced conditions. Track ongoing accepted effect IDs separately; `_source_turn_end` decrements frightened but floors it at 1 while any such accepted effect persists. This floor survives Rage ending. Expiry, consumption, or removal of Guidance calls `_remove_magic_acceptance`; a timestamp alone cannot detect consuming Guidance early. With several effects, removing one does not clear another's floor. After the final effect ends, frightened decreases normally rather than disappearing immediately.
- [ ] Instantaneous accepted healing still applies frightened 1, but creates no permanent floor; remove its acceptance reference when resolution finishes. Its lasting healed HP is not an ongoing magical effect. A refused/unwilling hostile spell does not apply the acceptance penalty.
- [ ] Use the actual selected temporary-HP grant to calculate Superstition healing; retain separate 10-minute healing and 1-minute regrant timestamps. No healing of the temp pool. When anathema disables the instinct, ordinary Rage and Quick-Tempered remain; save bonus, enhanced instinct damage, healing, and dependent instinct feats stop.
- [ ] Narrative anathema/recentering uses a validated local GM context, with actor, declared reason, and completion time. Actual Cast a Spell or use/wield of an admitted spell-activation item records its own violation. No campaign history. Recentring advances a declared full downtime day and cannot be called during combat to erase the restriction.

### C. Local continuity and save invariants

Add a narrow `Encounter.next_encounter(setup, *, continuing_actor_ids, elapsed_seconds=0)` for the fixed repeated-Barbarian fixtures, or use an already-landed equivalent. Require the previous fight ended; continuing IDs and definition IDs match both reviewed setups. Preserve their actual HP/health, Hero Points, inventory, Barbarian state/cooldowns, and any surviving unrelated pool; reset only encounter/turn facts and place them at the new setup locations. Add `encounter_started_at_seconds`; save clock equality becomes `world_time_seconds == encounter_started_at_seconds + 6*(round_number-1)`. This is a local handoff, not simulated travel/recovery. No automatic heal or daily refresh. Reject impossible continuing dead/uncertain states rather than invent recovery.

Revalidate Rage's source, mode, duration, actual awarded amount, pending commitment phase, and Quick trigger; do not require the Rage source to remain the current pool after a legal replacement. Preserve damage component tags and post-absorption health facts through nested saved choices. New class state must not be changeable by editing only a serialized subclass string.

### D. Slice-2 acceptance and ownership

- Parameterized public startup/Rage/Strike cases cover the accepted representative builds; exact source-table assertions cover their profiles and mode traits. Selected alternate routes cover Quick decline and normal damage mode. Unselected instinct variants remain reference inventory.
- Reference-only future cases, if those variants are later selected, would exercise unarmed Trip/Grapple/Shove, Giant clumsy before Rage and after release, Fury's two working feats, separate Dragon typed damage on critical, and Spirit's real defense exception. Save at a mode choice and at Shove follow/reaction where applicable.
- Reference-only future Superstition work would prove actual witnessed casting changes damage, typed save stacking and saved target Hero reroll, Guidance acceptance, effect-floor expiry, instant Heal frightened, and temporary-HP healing/cooldown. Continue into the next fixed encounter without silently resetting the clock/HP.
- Include rejection/queries preserving dice and state; expired source cleanup; corrupt pending Quick/mode/temp-source saves; a last-action Rage/Clarity automatically ending the turn. Keep complete-route bounds at or below existing harness defaults, with explicitly justified exceptions.

**One sequential core owner per slice** owns `encounter.py`, `model.py`, `persistence.py`, `barbarian.py`, `barbarian_content.py`, canonical `content.py` imports, public exports, and new Barbarian runtime tests. Slice 2 additionally owns narrowly touched `skill_actions.py`/`skill_content.py` and their pending-command encoders for unarmed maneuvers/Shove. Reuse `damage.py`/`conditions.py` unchanged unless a focused test exposes a specific helper defect; do not reorganize them. Terminal ownership remains separate and starts from the stabilized public options/view handoff. Wait for the active bow-boundary owner to release the shared core files before starting either slice; preserve that correction.

**Questions:** no new P0/P1 user decision is required for the identified implementation gaps. Existing stable-zero positive-damage policy remains unchanged. The fixed initiative-choice ordering and round-clock granularity above are explicit implementation policies. If later content makes either ordering consequential, resolve that concrete interaction before broadening it.
