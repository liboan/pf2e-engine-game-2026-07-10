"""Player Core 2 barbarian rules and explicit family actions.

The rules data here follows Player Core 2, pp. 70–75, as corrected by the
Spring 2026 Player Core 2 errata. The errata makes Dragon/Spirit damage-mode
selection part of taking Rage, and updates Frog's tongue to 1d6.

Sources:
* https://2e.aonprd.com/Classes.aspx?ID=57
* https://2e.aonprd.com/Instincts.aspx?ID=8
* https://2e.aonprd.com/Instincts.aspx?ID=9
* https://2e.aonprd.com/Instincts.aspx?ID=10
* https://2e.aonprd.com/Instincts.aspx?ID=11
* https://2e.aonprd.com/Instincts.aspx?ID=12
* https://2e.aonprd.com/Instincts.aspx?ID=13
* https://paizo.com/pathfinder/faq (Player Core 2 Errata, Spring 2026)

Timestamps passed to the helpers are non-negative integer seconds on the
engine's monotonic world clock. The family module does not advance time or
infer missing witness, willingness, fatigue, or downtime facts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from .checks import Modifier
from .damage import DamageTerm
from .model import (
    ActionContinuation,
    ChoiceOption,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
)


RAGE_DURATION_SECONDS = 60
RAGE_TEMP_HP_LOCK_SECONDS = 60
SUPERSTITION_HEAL_LOCK_SECONDS = 10 * 60
SUPERSTITION_WITNESS_SECONDS = 60 * 60

ANIMAL_INSTINCT = "animal"
DRAGON_INSTINCT = "dragon"
FURY_INSTINCT = "fury"
GIANT_INSTINCT = "giant"
SPIRIT_INSTINCT = "spirit"
SUPERSTITION_INSTINCT = "superstition"
RAGING_INTIMIDATION = "raging_intimidation"
MOMENT_OF_CLARITY = "moment_of_clarity"
BARBARIAN_FEAT_IDS = frozenset({RAGING_INTIMIDATION, MOMENT_OF_CLARITY})
KEEP_EXISTING_TEMP_HP = "keep_existing"
GAIN_NEW_RAGE_TEMP_HP = "gain_new"
RAGE_TEMP_HP_CHOICES = frozenset({KEEP_EXISTING_TEMP_HP, GAIN_NEW_RAGE_TEMP_HP})
INSTINCT_IDS = frozenset(
    {
        ANIMAL_INSTINCT,
        DRAGON_INSTINCT,
        FURY_INSTINCT,
        GIANT_INSTINCT,
        SPIRIT_INSTINCT,
        SUPERSTITION_INSTINCT,
    }
)


@dataclass(frozen=True)
class AnimalAttackProfile:
    attack_id: str
    name: str
    damage_type: str
    damage_dice: tuple[int, ...]
    traits: frozenset[str] = frozenset()
    # Animal Instinct's granted unarmed attacks use the brawling weapon group.
    # This family-local rule fact is recorded without adding weapon-group or
    # specialization machinery to the shared AttackDefinition model.
    weapon_group: str = "brawling"


@dataclass(frozen=True)
class AnimalChoice:
    animal_id: str
    attacks: tuple[AnimalAttackProfile, ...]


ANIMAL_CHOICES: tuple[AnimalChoice, ...] = (
    AnimalChoice("ape", (AnimalAttackProfile("animal_ape_fist", "Ape Fist", "bludgeoning", (10,), frozenset({"grapple"})),)),
    AnimalChoice(
        "bear",
        (
            AnimalAttackProfile("animal_bear_jaws", "Bear Jaws", "piercing", (10,)),
            AnimalAttackProfile("animal_bear_claw", "Bear Claw", "slashing", (6,), frozenset({"agile"})),
        ),
    ),
    AnimalChoice("bull", (AnimalAttackProfile("animal_bull_horn", "Bull Horn", "piercing", (10,), frozenset({"shove"})),)),
    AnimalChoice(
        "cat",
        (
            AnimalAttackProfile("animal_cat_jaws", "Cat Jaws", "piercing", (10,)),
            AnimalAttackProfile("animal_cat_claw", "Cat Claw", "slashing", (6,), frozenset({"agile"})),
        ),
    ),
    AnimalChoice("deer", (AnimalAttackProfile("animal_deer_antler", "Deer Antler", "piercing", (10,), frozenset({"grapple"})),)),
    AnimalChoice(
        "frog",
        (
            AnimalAttackProfile("animal_frog_jaws", "Frog Jaws", "bludgeoning", (10,)),
            AnimalAttackProfile("animal_frog_tongue", "Frog Tongue", "bludgeoning", (6,), frozenset({"agile"})),
        ),
    ),
    AnimalChoice("shark", (AnimalAttackProfile("animal_shark_jaws", "Shark Jaws", "piercing", (10,), frozenset({"grapple"})),)),
    AnimalChoice("snake", (AnimalAttackProfile("animal_snake_fangs", "Snake Fangs", "piercing", (10,), frozenset({"grapple"})),)),
    AnimalChoice("wolf", (AnimalAttackProfile("animal_wolf_jaws", "Wolf Jaws", "piercing", (10,), frozenset({"trip"})),)),
)
ANIMALS_BY_ID = {choice.animal_id: choice for choice in ANIMAL_CHOICES}


@dataclass(frozen=True)
class DragonChoice:
    dragon_id: str
    tradition: str
    damage_type: str


DRAGON_CHOICES: tuple[DragonChoice, ...] = (
    DragonChoice("adamantine", "primal", "bludgeoning"),
    DragonChoice("conspirator", "occult", "poison"),
    DragonChoice("diabolic", "divine", "fire"),
    DragonChoice("empyreal", "divine", "spirit"),
    DragonChoice("fortune", "arcane", "force"),
    DragonChoice("horned", "primal", "poison"),
    DragonChoice("mirage", "arcane", "mental"),
    DragonChoice("omen", "occult", "mental"),
)
DRAGONS_BY_ID = {choice.dragon_id: choice for choice in DRAGON_CHOICES}


@dataclass(frozen=True)
class GiantWeaponProfile:
    weapon_id: str
    base_weapon_id: str
    name: str
    price_gp: int
    large_price_gp: int
    bulk: int
    hands_required: int
    damage_type: str
    damage_dice: tuple[int, ...]
    traits: frozenset[str]


# Longsword: common martial melee, 1 gp and 1 Bulk in Player Core. The
# Large-item entry costs 2 gp and has Bulk 2; Titan Mauler's grant is based on
# the ordinary base weapon, while its damage die and reach stay unchanged.
GIANT_WEAPON_CHOICES: tuple[GiantWeaponProfile, ...] = (
    GiantWeaponProfile(
        weapon_id="giant_large_longsword",
        base_weapon_id="longsword",
        name="Large Longsword",
        price_gp=1,
        large_price_gp=2,
        bulk=2,
        hands_required=1,
        damage_type="slashing",
        damage_dice=(8,),
        traits=frozenset({"versatile-p"}),
    ),
)
GIANT_WEAPONS_BY_ID = {weapon.weapon_id: weapon for weapon in GIANT_WEAPON_CHOICES}


@dataclass(frozen=True)
class RageMode:
    mode_id: str
    label: str
    damage_type: str | None = None
    action_traits: frozenset[str] = frozenset()
    ghost_touch: bool = False


@dataclass(frozen=True)
class SpellcastWitness:
    caster_actor_id: str
    witnessed_at_seconds: int


@dataclass(frozen=True)
class AcceptedMagicEffect:
    effect_id: str
    expires_at_seconds: int | None


@dataclass(frozen=True)
class ActiveRage:
    mode_id: str
    started_at_seconds: int
    expires_at_seconds: int
    temporary_hp_source_id: str | None
    temporary_hp_gained: int
    damage_type: str | None
    action_traits: frozenset[str]
    ghost_touch: bool = False


@dataclass(frozen=True)
class BarbarianState:
    """Per-character Barbarian choices and long-lived class-specific facts.

    Core owns the temporary-HP quantity and provenance pool. ``ActiveRage``
    remembers only whether this Rage actually created that pool and its
    source ID, so core can clear the right source when Rage ends.
    """

    instinct_id: str
    animal_choice: str | None = None
    dragon_choice: str | None = None
    giant_weapon_id: str | None = None
    class_feat_id: str | None = None
    bonus_feat_id: str | None = None
    next_rage_instance: int = 1
    rage: ActiveRage | None = None
    rage_temp_hp_available_at_seconds: int = 0
    superstition_heal_available_at_seconds: int = 0
    spellcast_witnesses: tuple[SpellcastWitness, ...] = ()
    accepted_magic_effects: tuple[AcceptedMagicEffect, ...] = ()
    anathema_violated_at_downtime_day: int | None = None
    superstition_recentered_at_downtime_day: int | None = None

    @property
    def is_raging(self) -> bool:
        return self.rage is not None


@dataclass(frozen=True)
class RageActivation:
    state: BarbarianState
    temporary_hp_to_grant: int
    temporary_hp_source_id: str | None
    temporary_hp_expires_at_seconds: int | None
    healing_to_apply: int
    rage_traits: frozenset[str]


@dataclass(frozen=True)
class RageEnding:
    state: BarbarianState
    temporary_hp_source_to_clear: str | None


@dataclass(frozen=True)
class RageStrikeAdjustment:
    """Instinct consequences for one committed melee Strike."""

    allowed: bool
    rejection: str | None
    damage_term: DamageTerm | None
    ghost_touch: bool


@dataclass(frozen=True)
class Rage(FamilyCommand):
    """Take the one-action Rage action; choice-required instincts pause first."""

    family_id: ClassVar[str] = "martial"
    mode_id: str | None = None
    temporary_hp_choice: str | None = None


@dataclass(frozen=True)
class QuickTempered(FamilyCommand):
    """Use Quick-Tempered's free Rage trigger when core offers it at initiative."""

    family_id: ClassVar[str] = "martial"
    mode_id: str | None = None
    temporary_hp_choice: str | None = None


@dataclass(frozen=True)
class RageModeChoice:
    """Named payload used while a Dragon/Spirit Rage mode is pending."""

    procedure_id: str
    actor_id: str
    command_kind: str
    mode_id: str | None = None
    temporary_hp_choice: str | None = None


@dataclass(frozen=True)
class BarbarianBuildChoices:
    instinct_id: str
    class_feat_id: str | None = None
    animal_choice: str | None = None
    dragon_choice: str | None = None
    giant_weapon_id: str | None = None
    bonus_feat_id: str | None = None


class BarbarianChoiceError(ValueError):
    """A character or rage choice is not valid for its recorded instinct."""


def build_barbarian_state(choices: BarbarianBuildChoices) -> BarbarianState:
    if choices.instinct_id not in INSTINCT_IDS:
        raise BarbarianChoiceError(f"Unknown Barbarian instinct {choices.instinct_id!r}.")
    if choices.instinct_id == ANIMAL_INSTINCT:
        if choices.animal_choice not in ANIMALS_BY_ID:
            raise BarbarianChoiceError("Animal Instinct requires one of the nine Player Core 2 animal choices.")
    elif choices.animal_choice is not None:
        raise BarbarianChoiceError("An animal choice is only valid for Animal Instinct.")
    if choices.instinct_id == DRAGON_INSTINCT:
        if choices.dragon_choice not in DRAGONS_BY_ID:
            raise BarbarianChoiceError("Dragon Instinct requires one of the eight Player Core 2 dragon choices.")
    elif choices.dragon_choice is not None:
        raise BarbarianChoiceError("A dragon choice is only valid for Dragon Instinct.")
    if choices.instinct_id == GIANT_INSTINCT:
        if choices.giant_weapon_id not in GIANT_WEAPONS_BY_ID:
            raise BarbarianChoiceError("Giant Instinct requires a reviewed, qualifying oversized weapon grant.")
    elif choices.giant_weapon_id is not None:
        raise BarbarianChoiceError("An oversized weapon grant is only valid for Giant Instinct.")
    if choices.class_feat_id not in BARBARIAN_FEAT_IDS:
        raise BarbarianChoiceError("A Barbarian requires an admitted level-1 class feat choice.")
    if choices.bonus_feat_id is not None and choices.bonus_feat_id not in BARBARIAN_FEAT_IDS:
        raise BarbarianChoiceError("The selected level-1 Barbarian feat is not in the admitted curated menu.")
    if choices.instinct_id == FURY_INSTINCT and choices.bonus_feat_id is None:
        raise BarbarianChoiceError("Fury Instinct requires its additional level-1 Barbarian feat choice.")
    if choices.instinct_id != FURY_INSTINCT and choices.bonus_feat_id is not None:
        raise BarbarianChoiceError("The bonus feat grant is specific to Fury Instinct.")
    if choices.bonus_feat_id == choices.class_feat_id:
        raise BarbarianChoiceError("The ordinary and Fury bonus feat selections must be different.")
    return BarbarianState(
        instinct_id=choices.instinct_id,
        animal_choice=choices.animal_choice,
        dragon_choice=choices.dragon_choice,
        giant_weapon_id=choices.giant_weapon_id,
        class_feat_id=choices.class_feat_id,
        bonus_feat_id=choices.bonus_feat_id,
    )


def validate_barbarian_state(state: BarbarianState, *, now_seconds: int | None = None) -> None:
    """Reject corrupt persisted/build state instead of dropping bad choices."""
    expected = build_barbarian_state(
        BarbarianBuildChoices(
            state.instinct_id,
            class_feat_id=state.class_feat_id,
            animal_choice=state.animal_choice,
            dragon_choice=state.dragon_choice,
            giant_weapon_id=state.giant_weapon_id,
            bonus_feat_id=state.bonus_feat_id,
        )
    )
    if expected.instinct_id != state.instinct_id:
        raise BarbarianChoiceError("Barbarian instinct state is inconsistent.")
    if type(state.next_rage_instance) is not int or state.next_rage_instance < 1:
        raise BarbarianChoiceError("The next Rage instance must be a positive integer.")
    if now_seconds is not None and (type(now_seconds) is not int or now_seconds < 0):
        raise BarbarianChoiceError("The validation clock must be non-negative integer seconds.")
    for timestamp in (
        state.rage_temp_hp_available_at_seconds,
        state.superstition_heal_available_at_seconds,
    ):
        if type(timestamp) is not int or timestamp < 0:
            raise BarbarianChoiceError("Barbarian cooldown timestamps must be non-negative integer seconds.")
    if state.rage is not None:
        rage = state.rage
        if (
            not rage.mode_id
            or type(rage.started_at_seconds) is not int
            or type(rage.expires_at_seconds) is not int
            or rage.started_at_seconds < 0
            or rage.expires_at_seconds != rage.started_at_seconds + RAGE_DURATION_SECONDS
            or rage.temporary_hp_gained < 0
            or (rage.temporary_hp_gained == 0) != (rage.temporary_hp_source_id is None)
        ):
            raise BarbarianChoiceError("Saved Rage state is inconsistent.")
        if now_seconds is not None and rage.started_at_seconds > now_seconds:
            raise BarbarianChoiceError("Saved Rage cannot start in the future.")
        expected_mode = valid_rage_mode(state, rage.mode_id)
        if (
            rage.damage_type != expected_mode.damage_type
            or rage.action_traits != expected_mode.action_traits
            or rage.ghost_touch != expected_mode.ghost_touch
        ):
            raise BarbarianChoiceError("Saved Rage mode facts do not match its selected mode.")
    if tuple(sorted(state.spellcast_witnesses, key=lambda witness: (witness.caster_actor_id, witness.witnessed_at_seconds))) != state.spellcast_witnesses:
        raise BarbarianChoiceError("Spellcast witness history must have stable ordering.")
    if any(
        not witness.caster_actor_id
        or type(witness.witnessed_at_seconds) is not int
        or witness.witnessed_at_seconds < 0
        for witness in state.spellcast_witnesses
    ):
        raise BarbarianChoiceError("Saved spellcast witness history is invalid.")
    witness_ids = tuple(witness.caster_actor_id for witness in state.spellcast_witnesses)
    if len(set(witness_ids)) != len(witness_ids):
        raise BarbarianChoiceError("Spellcast witness history must retain only the latest timestamp per caster.")
    if now_seconds is not None and any(witness.witnessed_at_seconds > now_seconds for witness in state.spellcast_witnesses):
        raise BarbarianChoiceError("A spellcast witness cannot be recorded in the future.")
    effect_ids = tuple(effect.effect_id for effect in state.accepted_magic_effects)
    if len(set(effect_ids)) != len(effect_ids):
        raise BarbarianChoiceError("Accepted Superstition magic effects must have unique identities.")
    if tuple(sorted(effect_ids)) != effect_ids or any(
        not effect.effect_id
        or (
            effect.expires_at_seconds is not None
            and (type(effect.expires_at_seconds) is not int or effect.expires_at_seconds < 0)
        )
        for effect in state.accepted_magic_effects
    ):
        raise BarbarianChoiceError("Saved accepted magic-effect history is invalid.")
    if state.anathema_violated_at_downtime_day is not None and (
        type(state.anathema_violated_at_downtime_day) is not int
        or state.anathema_violated_at_downtime_day < 0
    ):
        raise BarbarianChoiceError("Saved Superstition anathema timestamp is invalid.")
    if state.superstition_recentered_at_downtime_day is not None and (
        type(state.superstition_recentered_at_downtime_day) is not int
        or state.superstition_recentered_at_downtime_day < 0
        or state.anathema_violated_at_downtime_day is None
        or state.superstition_recentered_at_downtime_day
        < state.anathema_violated_at_downtime_day + 1
    ):
        raise BarbarianChoiceError("Saved Superstition recentering is not after a full downtime day.")


def superstition_abilities_enabled(state: BarbarianState) -> bool:
    return state.instinct_id != SUPERSTITION_INSTINCT or (
        state.anathema_violated_at_downtime_day is None
        or state.superstition_recentered_at_downtime_day is not None
    )


def valid_rage_modes(state: BarbarianState) -> tuple[RageMode, ...]:
    if state.instinct_id == DRAGON_INSTINCT:
        dragon = DRAGONS_BY_ID.get(state.dragon_choice or "")
        if dragon is None:
            return ()
        return (
            RageMode("base", "Normal Rage damage"),
            RageMode(
                "dragon_damage",
                f"Draconic Rage ({dragon.damage_type})",
                damage_type=dragon.damage_type,
                action_traits=frozenset({dragon.tradition, dragon.damage_type}),
            ),
        )
    if state.instinct_id == SPIRIT_INSTINCT:
        return (
            RageMode("base", "Normal Rage damage"),
            RageMode(
                "spirit_damage",
                "Spirit damage and ghost touch",
                damage_type="spirit",
                action_traits=frozenset({"divine", "spirit"}),
                ghost_touch=True,
            ),
        )
    return (RageMode("base", "Normal Rage damage"),)


def valid_rage_mode(state: BarbarianState, mode_id: str) -> RageMode:
    for mode in valid_rage_modes(state):
        if mode.mode_id == mode_id:
            return mode
    raise BarbarianChoiceError(f"Rage mode {mode_id!r} is not available for {state.instinct_id} instinct.")


def rage_temporary_hp_choice_required(
    state: BarbarianState,
    *,
    level: int,
    constitution_modifier: int,
    now_seconds: int,
    current_temporary_hp: int,
) -> bool:
    """Whether an existing pool requires an explicit keep-or-gain decision."""
    if type(level) is not int or level < 1 or type(constitution_modifier) is not int:
        raise BarbarianChoiceError("Rage requires a valid character level and Constitution modifier.")
    if type(now_seconds) is not int or now_seconds < 0:
        raise BarbarianChoiceError("Rage requires a monotonic timestamp.")
    if type(current_temporary_hp) is not int or current_temporary_hp < 0:
        raise BarbarianChoiceError("Temporary HP must be a non-negative integer.")
    return (
        current_temporary_hp > 0
        and level + constitution_modifier > 0
        and now_seconds >= state.rage_temp_hp_available_at_seconds
    )


def activate_rage(
    state: BarbarianState,
    *,
    level: int,
    constitution_modifier: int,
    now_seconds: int,
    source_id: str | None = None,
    mode_id: str = "base",
    fatigued: bool = False,
    current_temporary_hp: int = 0,
    current_temporary_hp_source_id: str | None = None,
    current_temporary_hp_expires_at_seconds: int | None = None,
    temporary_hp_choice: str | None = None,
    current_hp: int = 0,
    maximum_hp: int = 0,
) -> RageActivation:
    """Begin Rage and return only the consequences core must commit.

    A blocked one-minute regrant lock suppresses Rage temporary HP, not the
    Rage action itself. If an old temporary-HP pool remains and this Rage can
    grant a new pool, the caller must supply the player's explicit choice. The
    two pools are alternatives: ``gain_new`` replaces the old pool even when
    the new amount is equal or lower. The core owns the shared pool, its
    provenance, and its expiry; this result describes only the chosen grant.
    """
    if state.rage is not None:
        raise BarbarianChoiceError("You cannot Rage while already raging.")
    if fatigued:
        raise BarbarianChoiceError("You cannot Rage while fatigued.")
    if type(level) is not int or level < 1 or type(constitution_modifier) is not int:
        raise BarbarianChoiceError("Rage requires a valid character level and Constitution modifier.")
    if type(now_seconds) is not int or now_seconds < 0:
        raise BarbarianChoiceError("Rage requires a monotonic timestamp.")
    if min(current_temporary_hp, current_hp, maximum_hp) < 0 or current_hp > maximum_hp:
        raise BarbarianChoiceError("Current HP and temporary HP must be valid non-negative values.")
    if current_temporary_hp == 0:
        if current_temporary_hp_source_id is not None or current_temporary_hp_expires_at_seconds is not None:
            raise BarbarianChoiceError("An empty temporary-HP pool cannot retain a source or expiry.")
    elif not current_temporary_hp_source_id:
        raise BarbarianChoiceError("An existing temporary-HP pool requires its provenance source.")
    if current_temporary_hp_expires_at_seconds is not None and (
        type(current_temporary_hp_expires_at_seconds) is not int
        or current_temporary_hp_expires_at_seconds <= now_seconds
    ):
        raise BarbarianChoiceError("The current temporary-HP pool has already expired.")
    mode = valid_rage_mode(state, mode_id)
    proposed_temporary_hp = max(0, level + constitution_modifier)
    grant_eligible = (
        proposed_temporary_hp > 0
        and now_seconds >= state.rage_temp_hp_available_at_seconds
    )
    needs_choice = rage_temporary_hp_choice_required(
        state,
        level=level,
        constitution_modifier=constitution_modifier,
        now_seconds=now_seconds,
        current_temporary_hp=current_temporary_hp,
    )
    if needs_choice:
        if temporary_hp_choice is None:
            raise BarbarianChoiceError("Choose whether to keep existing temporary HP or gain Rage temporary HP.")
        if temporary_hp_choice not in RAGE_TEMP_HP_CHOICES:
            raise BarbarianChoiceError("Choose keep_existing or gain_new for the temporary-HP pool.")
    elif temporary_hp_choice is not None:
        raise BarbarianChoiceError("A temporary-HP choice is not available for this Rage.")

    grant = proposed_temporary_hp if grant_eligible and temporary_hp_choice != KEEP_EXISTING_TEMP_HP else 0
    if grant > 0 and not source_id:
        raise BarbarianChoiceError("Gaining Rage temporary HP requires a unique source ID from core.")
    source = source_id if grant else None
    next_instance = state.next_rage_instance + (1 if grant else 0)
    next_state = replace(
        state,
        next_rage_instance=next_instance,
        rage=ActiveRage(
            mode_id=mode.mode_id,
            started_at_seconds=now_seconds,
            expires_at_seconds=now_seconds + RAGE_DURATION_SECONDS,
            temporary_hp_source_id=source,
            temporary_hp_gained=grant,
            damage_type=mode.damage_type,
            action_traits=mode.action_traits,
            ghost_touch=mode.ghost_touch,
        ),
    )
    healing = 0
    if (
        state.instinct_id == SUPERSTITION_INSTINCT
        and superstition_abilities_enabled(state)
        and grant > 0
        and now_seconds >= state.superstition_heal_available_at_seconds
    ):
        healing = min(grant, maximum_hp - current_hp)
        next_state = replace(
            next_state,
            superstition_heal_available_at_seconds=now_seconds + SUPERSTITION_HEAL_LOCK_SECONDS,
        )
    rage_traits = frozenset({"barbarian", "concentrate", "emotion", "mental", *mode.action_traits})
    if state.instinct_id == ANIMAL_INSTINCT:
        rage_traits |= frozenset({"morph", "primal"})
    return RageActivation(
        next_state,
        grant,
        source,
        now_seconds + RAGE_DURATION_SECONDS if grant else None,
        healing,
        rage_traits,
    )


def end_rage(state: BarbarianState, *, now_seconds: int) -> RageEnding:
    if state.rage is None:
        raise BarbarianChoiceError("The Barbarian is not raging.")
    if type(now_seconds) is not int or now_seconds < state.rage.started_at_seconds:
        raise BarbarianChoiceError("Rage cannot end before its recorded start time.")
    source_id = state.rage.temporary_hp_source_id
    return RageEnding(
        replace(
            state,
            rage=None,
            rage_temp_hp_available_at_seconds=now_seconds + RAGE_TEMP_HP_LOCK_SECONDS,
        ),
        source_id,
    )


def expire_rage(state: BarbarianState, *, now_seconds: int, unconscious: bool, encounter_ended: bool) -> RageEnding | None:
    """End Rage only for a published termination trigger; no voluntary stop."""
    if state.rage is None:
        return None
    if unconscious or encounter_ended or now_seconds >= state.rage.expires_at_seconds:
        return end_rage(state, now_seconds=now_seconds)
    return None


def witnessed_recent_spellcaster(state: BarbarianState, caster_actor_id: str, *, now_seconds: int) -> bool:
    if not caster_actor_id or type(now_seconds) is not int or now_seconds < 0:
        return False
    return any(
        witness.caster_actor_id == caster_actor_id
        and witness.witnessed_at_seconds <= now_seconds
        and now_seconds < witness.witnessed_at_seconds + SUPERSTITION_WITNESS_SECONDS
        for witness in state.spellcast_witnesses
    )


def record_spellcast_witness(state: BarbarianState, caster_actor_id: str, *, now_seconds: int) -> BarbarianState:
    if not caster_actor_id or type(now_seconds) is not int or now_seconds < 0:
        raise BarbarianChoiceError("A spellcast witness requires a creature ID and timestamp.")
    witnesses = tuple(
        witness
        for witness in state.spellcast_witnesses
        if now_seconds < witness.witnessed_at_seconds + SUPERSTITION_WITNESS_SECONDS
        and witness.caster_actor_id != caster_actor_id
    )
    witnesses += (SpellcastWitness(caster_actor_id, now_seconds),)
    return replace(state, spellcast_witnesses=tuple(sorted(witnesses, key=lambda item: (item.caster_actor_id, item.witnessed_at_seconds))))


def rage_damage_bonus(
    state: BarbarianState,
    *,
    attack_traits: frozenset[str],
    is_melee: bool,
    wielded_item_id: str | None = None,
    target_actor_id: str | None = None,
    now_seconds: int | None = None,
) -> int:
    """Return the instinct's flat Rage bonus for one actual melee Strike."""
    rage = state.rage
    if rage is None or not is_melee:
        return 0
    agile = "agile" in attack_traits
    instinct = state.instinct_id
    special_mode = rage.mode_id
    if instinct == SUPERSTITION_INSTINCT and superstition_abilities_enabled(state):
        bonus = 4 if (
            target_actor_id is not None
            and now_seconds is not None
            and witnessed_recent_spellcaster(state, target_actor_id, now_seconds=now_seconds)
        ) else 3
    elif instinct == FURY_INSTINCT:
        bonus = 3
    elif instinct == GIANT_INSTINCT and state.giant_weapon_id == wielded_item_id:
        bonus = 6
    elif instinct == SPIRIT_INSTINCT and special_mode == "spirit_damage":
        bonus = 3
    elif instinct == DRAGON_INSTINCT and special_mode == "dragon_damage":
        bonus = 4
    else:
        bonus = 2
    return bonus // 2 if agile else bonus


def rage_damage_term(
    state: BarbarianState,
    *,
    attack_id: str,
    attack_damage_type: str,
    attack_traits: frozenset[str],
    is_melee: bool,
    wielded_item_id: str | None = None,
    target_actor_id: str | None = None,
    now_seconds: int | None = None,
) -> DamageTerm | None:
    """Create the distinct typed damage component used by a real Strike."""
    bonus = rage_damage_bonus(
        state,
        attack_traits=attack_traits,
        is_melee=is_melee,
        wielded_item_id=wielded_item_id,
        target_actor_id=target_actor_id,
        now_seconds=now_seconds,
    )
    if bonus == 0:
        return None
    rage = state.rage
    assert rage is not None
    damage_type = rage.damage_type if rage.mode_id in {"dragon_damage", "spirit_damage"} else attack_damage_type
    return DamageTerm(
        source=f"{attack_id} Rage ({state.instinct_id})",
        damage_type=damage_type or attack_damage_type,
        dice=(),
        modifier=bonus,
        tags=frozenset({"rage", "instinct"}),
    )


def rage_strike_adjustment(
    state: BarbarianState,
    *,
    attack_id: str,
    attack_damage_type: str,
    attack_traits: frozenset[str],
    attack_is_weapon: bool,
    is_melee: bool,
    wielded_item_id: str | None,
    target_actor_id: str,
    now_seconds: int,
) -> RageStrikeAdjustment:
    """Resolve a Strike's actual Animal lock, Rage damage and ghost touch."""
    if not attack_allowed_during_rage(
        state,
        attack_is_weapon=attack_is_weapon,
        attack_id=attack_id,
    ):
        return RageStrikeAdjustment(
            False,
            "Animal Instinct cannot use weapons while raging.",
            None,
            False,
        )
    damage = rage_damage_term(
        state,
        attack_id=attack_id,
        attack_damage_type=attack_damage_type,
        attack_traits=attack_traits,
        is_melee=is_melee,
        wielded_item_id=wielded_item_id,
        target_actor_id=target_actor_id,
        now_seconds=now_seconds,
    )
    return RageStrikeAdjustment(
        True,
        None,
        damage,
        state.rage is not None and state.rage.ghost_touch,
    )


def attack_allowed_during_rage(
    state: BarbarianState,
    *,
    attack_is_weapon: bool,
    attack_id: str,
) -> bool:
    """Animal Instinct bars weapons only while raging; unarmed stays available."""
    if state.rage is None or state.instinct_id != ANIMAL_INSTINCT:
        return True
    if not attack_is_weapon:
        return True
    return False


def animal_attack_ids(state: BarbarianState) -> tuple[str, ...]:
    if state.instinct_id != ANIMAL_INSTINCT or state.animal_choice is None:
        return ()
    return tuple(attack.attack_id for attack in ANIMALS_BY_ID[state.animal_choice].attacks)


def giant_weapon_wielded(state: BarbarianState, held_item_ids: tuple[str, ...] | list[str]) -> bool:
    return (
        state.instinct_id == GIANT_INSTINCT
        and state.giant_weapon_id is not None
        and state.giant_weapon_id in held_item_ids
    )


def giant_clumsy_value(state: BarbarianState, held_item_ids: tuple[str, ...] | list[str], *, in_combat: bool) -> int:
    return 1 if in_combat and giant_weapon_wielded(state, held_item_ids) else 0


def action_allowed_while_raging(state: BarbarianState, action_id: str, traits: frozenset[str]) -> bool:
    if state.rage is None:
        return True
    if action_id == "seek":
        return True
    return "concentrate" not in traits or "rage" in traits


def superstition_save_modifier(state: BarbarianState, *, against_magic: bool) -> Modifier | None:
    if (
        state.instinct_id != SUPERSTITION_INSTINCT
        or not superstition_abilities_enabled(state)
        or state.rage is None
        or not against_magic
    ):
        return None
    return Modifier(2, "status", "Superstition Rage against magic")


def superstition_frightened_floor(state: BarbarianState, effect_id: str) -> int:
    if (
        state.instinct_id == SUPERSTITION_INSTINCT
        and superstition_abilities_enabled(state)
        and any(effect.effect_id == effect_id for effect in state.accepted_magic_effects)
    ):
        return 1
    return 0


def record_superstition_magic_acceptance(
    state: BarbarianState,
    *,
    effect_id: str,
    expires_at_seconds: int | None,
    while_raging: bool,
    willing: bool = True,
) -> BarbarianState:
    if (
        state.instinct_id != SUPERSTITION_INSTINCT
        or not superstition_abilities_enabled(state)
        or state.rage is None
        or not while_raging
        or not willing
    ):
        return state
    if not effect_id or (expires_at_seconds is not None and expires_at_seconds < state.rage.started_at_seconds):
        raise BarbarianChoiceError("Accepted Superstition magic requires the live effect's identity and expiry.")
    retained = tuple(item for item in state.accepted_magic_effects if item.effect_id != effect_id)
    return replace(
        state,
        accepted_magic_effects=tuple(
            sorted(retained + (AcceptedMagicEffect(effect_id, expires_at_seconds),), key=lambda item: item.effect_id)
        ),
    )


def remove_ended_magic_effects(state: BarbarianState, *, now_seconds: int) -> BarbarianState:
    if type(now_seconds) is not int or now_seconds < 0:
        raise BarbarianChoiceError("Magic-effect cleanup requires a timestamp.")
    effects = tuple(
        effect
        for effect in state.accepted_magic_effects
        if effect.expires_at_seconds is None or now_seconds < effect.expires_at_seconds
    )
    return replace(state, accepted_magic_effects=effects)


def remove_superstition_magic_effect(state: BarbarianState, effect_id: str) -> BarbarianState:
    """Forget the frightened floor when the specifically accepted effect ends."""
    if not effect_id:
        raise BarbarianChoiceError("An ended magic effect requires its source ID.")
    return replace(
        state,
        accepted_magic_effects=tuple(
            effect for effect in state.accepted_magic_effects if effect.effect_id != effect_id
        ),
    )


def record_superstition_anathema_violation(state: BarbarianState, *, downtime_day: int) -> BarbarianState:
    if state.instinct_id != SUPERSTITION_INSTINCT:
        return state
    if type(downtime_day) is not int or downtime_day < 0:
        raise BarbarianChoiceError("Anathema context requires a non-negative downtime-day index.")
    return replace(
        state,
        anathema_violated_at_downtime_day=downtime_day,
        superstition_recentered_at_downtime_day=None,
    )


def recenter_superstition(state: BarbarianState, *, completed_downtime_day: int) -> BarbarianState:
    violation_day = state.anathema_violated_at_downtime_day
    if state.instinct_id != SUPERSTITION_INSTINCT or violation_day is None:
        raise BarbarianChoiceError("There is no active Superstition anathema violation to recenter from.")
    if type(completed_downtime_day) is not int or completed_downtime_day < violation_day + 1:
        raise BarbarianChoiceError("Re-centering requires a full day of downtime after the violation.")
    return replace(state, superstition_recentered_at_downtime_day=completed_downtime_day)


def rage_action_traits(state: BarbarianState, mode_id: str) -> frozenset[str]:
    mode = valid_rage_mode(state, mode_id)
    traits = {"barbarian", "concentrate", "emotion", "mental", *mode.action_traits}
    if state.instinct_id == ANIMAL_INSTINCT:
        traits.update({"morph", "primal"})
    return frozenset(traits)


def has_intimidating_glare(
    state: BarbarianState, *, intimidation_trained: bool = False
) -> bool:
    """Whether the selected Raging Intimidation feat grants its prerequisite feat.

    Callers must establish trained Intimidation from the actor's skill sheet;
    a missing fact must not silently satisfy the prerequisite.
    """
    return intimidation_trained and RAGING_INTIMIDATION in {
        state.class_feat_id,
        state.bonus_feat_id,
    }


def action_traits_with_instinct_features(
    state: BarbarianState,
    action_id: str,
    traits: frozenset[str],
    *,
    intimidation_trained: bool = False,
) -> frozenset[str]:
    """Apply the admitted level-1 feat trait exception to its real action."""
    if (
        state.rage is not None
        and intimidation_trained
        and RAGING_INTIMIDATION in {state.class_feat_id, state.bonus_feat_id}
        and action_id == "demoralize"
    ):
        return traits | {"rage"}
    return traits


def quick_tempered_eligible(
    *,
    initiative_trigger: bool,
    fatigued: bool,
    encumbered: bool,
    wearing_heavy_armor: bool,
    is_raging: bool,
) -> bool:
    """Check Quick-Tempered's trigger, printed restrictions, and current Rage."""
    return (
        initiative_trigger
        and not is_raging
        and not fatigued
        and not encumbered
        and not wearing_heavy_armor
    )


def _rage_choice_modes(state: BarbarianState) -> tuple[RageMode, ...]:
    return tuple(mode for mode in valid_rage_modes(state) if mode.mode_id != "base")


def _family_rejection(text: str) -> FamilyProcedureResult:
    return FamilyProcedureResult(rejection=text)


def _family_unsupported(text: str) -> FamilyProcedureResult:
    return FamilyProcedureResult(unsupported=text)


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult:
    """Resolve Rage/Quick-Tempered inside core's atomic action draft.

    Character integration supplies ``actor.barbarian_state`` and the shared
    temporary-HP/timer hooks. Until those fields are present, fail explicitly
    instead of displaying Rage as a successful no-op.
    """
    return _handle_rage_action(
        context,
        context.command,
        quick_tempered_offered=getattr(context, "quick_tempered_trigger", False) is True,
    )


def _handle_rage_action(
    context: FamilyProcedureContext,
    command: object,
    *,
    quick_tempered_offered: bool,
) -> FamilyProcedureResult:
    if not isinstance(command, (Rage, QuickTempered)):
        return FamilyProcedureResult(unsupported="This Barbarian family action is not supported.")
    state = getattr(context.actor, "barbarian_state", None)
    if not isinstance(state, BarbarianState):
        return _family_unsupported("This actor has no admitted Barbarian state.")
    is_quick_tempered = isinstance(command, QuickTempered)
    if state.rage is not None:
        return _family_rejection("You cannot Rage while already raging.")
    if context.actor.actions_remaining < 1 and isinstance(command, Rage):
        return _family_rejection("Rage requires one action.")
    if is_quick_tempered and not quick_tempered_offered:
        return _family_rejection("Quick-Tempered is available only when its initiative trigger is offered.")
    if context.has_condition(context.actor.actor_id, "fatigued"):
        return _family_rejection("You cannot Rage while fatigued.")
    # The permission gate runs before either nested choice is offered. Rage is
    # concentrate, and the ordinary gate remains authoritative for conditions.
    mode_choices = _rage_choice_modes(state)
    if command.mode_id is not None and command.mode_id not in {
        mode.mode_id for mode in valid_rage_modes(state)
    }:
        return _family_rejection(f"Rage mode {command.mode_id!r} is not available for this instinct.")
    context.require_action_permitted("rage", rage_action_traits(state, command.mode_id or "base"))
    if mode_choices and command.mode_id is None:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            mode="barbarian_rage",
        )
        pending = context.present_choice(
            "barbarian:rage_mode",
            context.actor.actor_id,
            "Choose how this Rage changes its damage.",
            tuple(ChoiceOption(mode.mode_id, mode.label) for mode in _rage_choice_modes(state))
            + (ChoiceOption("base", "Keep normal Rage damage"),),
            continuation,
            details=tuple(f"{mode.mode_id}: {', '.join(sorted(mode.action_traits)) or 'no additional action traits'}." for mode in mode_choices),
            family_command=command,
        )
        pending.barbarian_choice = RageModeChoice(
            "barbarian:rage_mode", context.actor.actor_id, type(command).__name__
        )
        return FamilyProcedureResult(
            events=(Event("choice_offered", context.actor.actor_id, None, pending.prompt),)
        )
    if not mode_choices and command.mode_id not in (None, "base"):
        return _family_rejection(f"Rage mode {command.mode_id!r} is not available for this instinct.")
    if mode_choices and command.mode_id is not None:
        try:
            valid_rage_mode(state, command.mode_id)
        except BarbarianChoiceError as error:
            return _family_rejection(str(error))
    mode_id = command.mode_id or "base"
    now_seconds = getattr(context.state, "world_time_seconds", None)
    if type(now_seconds) is not int:
        return _family_unsupported("Rage requires the encounter's monotonic world-time clock.")
    ability_modifiers = dict(context.definition.ability_modifiers)
    level = context.definition.level
    constitution = ability_modifiers.get("constitution")
    if type(level) is not int or type(constitution) is not int:
        return _family_unsupported("Rage requires the actor's level and Constitution modifier.")
    fatigued = context.has_condition(context.actor.actor_id, "fatigued")
    current_temporary_hp = getattr(context.actor, "temporary_hp", 0)
    current_hp = context.actor.hp
    maximum_hp = context.definition.hp
    if rage_temporary_hp_choice_required(
        state,
        level=level,
        constitution_modifier=constitution,
        now_seconds=now_seconds,
        current_temporary_hp=current_temporary_hp,
    ) and command.temporary_hp_choice is None:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            mode="barbarian_rage",
        )
        pending = context.present_choice(
            "barbarian:temporary_hp",
            context.actor.actor_id,
            "Choose which temporary-HP pool to keep.",
            (
                ChoiceOption(KEEP_EXISTING_TEMP_HP, "Keep existing temporary HP"),
                ChoiceOption(GAIN_NEW_RAGE_TEMP_HP, f"Gain {level + constitution} Rage temporary HP"),
            ),
            continuation,
            details=(
                "Keeping the current pool preserves its source and remaining duration.",
                "Gaining the new pool replaces the current pool, even if the new amount is smaller or equal.",
            ),
            family_command=command,
        )
        pending.barbarian_choice = RageModeChoice(
            "barbarian:temporary_hp",
            context.actor.actor_id,
            type(command).__name__,
            mode_id=mode_id,
        )
        return FamilyProcedureResult(
            events=(Event("choice_offered", context.actor.actor_id, None, pending.prompt),)
        )
    source_id = (
        context.rage_source_id
        if command.temporary_hp_choice != KEEP_EXISTING_TEMP_HP
        else None
    )
    try:
        activation = activate_rage(
            state,
            level=level,
            constitution_modifier=constitution,
            now_seconds=now_seconds,
            source_id=source_id,
            mode_id=mode_id,
            fatigued=fatigued,
            current_temporary_hp=current_temporary_hp,
            current_temporary_hp_source_id=getattr(context.actor, "temporary_hp_source_id", None),
            current_temporary_hp_expires_at_seconds=getattr(
                context.actor, "temporary_hp_expires_at_seconds", None
            ),
            temporary_hp_choice=command.temporary_hp_choice,
            current_hp=current_hp,
            maximum_hp=maximum_hp,
        )
    except BarbarianChoiceError as error:
        return _family_rejection(str(error))
    if isinstance(command, Rage):
        context.commit_family_action(actions=1)
    setattr(context.actor, "barbarian_state", activation.state)
    if activation.temporary_hp_to_grant > 0:
        context.actor.temporary_hp = activation.temporary_hp_to_grant
        context.actor.temporary_hp_source_id = activation.temporary_hp_source_id
        context.actor.temporary_hp_expires_at_seconds = activation.temporary_hp_expires_at_seconds
    if activation.healing_to_apply:
        context.actor.hp = min(maximum_hp, context.actor.hp + activation.healing_to_apply)
    text = f"{context.actor.label} rages; temporary HP gained: {activation.temporary_hp_to_grant}."
    if activation.healing_to_apply:
        text += f" Superstition restores {activation.healing_to_apply} HP."
    return FamilyProcedureResult(
        events=(Event("rage_started", context.actor.actor_id, None, text, details=tuple(sorted(activation.rage_traits))),)
    )


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult:
    if context.pending is None or context.choice is None or context.pending.procedure_id not in {
        "barbarian:rage_mode", "barbarian:temporary_hp"
    }:
        return _family_unsupported("This Barbarian choice is not supported.")
    state = getattr(context.actor, "barbarian_state", None)
    if not isinstance(state, BarbarianState):
        return _family_unsupported("This actor has no admitted Barbarian state.")
    choice = getattr(context.pending, "barbarian_choice", None)
    if not isinstance(choice, RageModeChoice):
        return _family_unsupported("The saved Barbarian choice payload is invalid.")
    command_type = Rage if choice.command_kind == "Rage" else QuickTempered if choice.command_kind == "QuickTempered" else None
    if command_type is None:
        return _family_unsupported("The saved Barbarian Rage choice has an unknown originating action.")
    if context.pending.procedure_id == "barbarian:rage_mode":
        allowed = {mode.mode_id for mode in valid_rage_modes(state)}
        if context.choice.option_id not in allowed:
            return _family_rejection("That Rage mode is no longer available.")
        return _handle_rage_action(
            context,
            command_type(mode_id=context.choice.option_id),
            quick_tempered_offered=choice.command_kind == "QuickTempered",
        )
    if context.choice.option_id not in RAGE_TEMP_HP_CHOICES or choice.mode_id not in {
        mode.mode_id for mode in valid_rage_modes(state)
    }:
        return _family_rejection("That temporary-HP choice is no longer available.")
    return _handle_rage_action(
        context,
        command_type(mode_id=choice.mode_id, temporary_hp_choice=context.choice.option_id),
        quick_tempered_offered=choice.command_kind == "QuickTempered",
    )


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    state = getattr(context.actor, "barbarian_state", None)
    if (
        pending is None
        or pending.procedure_id not in {"barbarian:rage_mode", "barbarian:temporary_hp"}
        or not isinstance(state, BarbarianState)
        or not isinstance(getattr(pending, "barbarian_choice", None), RageModeChoice)
    ):
        raise ValueError("save has an invalid pending Barbarian Rage choice")
    choice = pending.barbarian_choice
    if (
        choice.actor_id != context.actor.actor_id
        or choice.procedure_id != pending.procedure_id
        or choice.command_kind not in {"Rage", "QuickTempered"}
    ):
        raise ValueError("save has a Barbarian Rage choice bound to another actor")
    if pending.procedure_id == "barbarian:rage_mode":
        expected = {mode.mode_id for mode in valid_rage_modes(state)}
        if {option.option_id for option in pending.options} != expected:
            raise ValueError("save has an altered Barbarian Rage mode menu")
    else:
        expected = RAGE_TEMP_HP_CHOICES
        if {option.option_id for option in pending.options} != expected or choice.mode_id not in {
            mode.mode_id for mode in valid_rage_modes(state)
        }:
            raise ValueError("save has an altered Barbarian temporary-HP menu")
    validate_barbarian_state(state)
