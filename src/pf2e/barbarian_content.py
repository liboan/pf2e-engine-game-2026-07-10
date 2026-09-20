"""Barbarian level-1 sheets and local test encounters.

This module authors fixed content. The central content catalog explicitly
admits the supported Bear, Cat, Frog, and Dragon definitions and their test
setups.

Class and proficiency facts are from Player Core 2 pp. 70–75. Item facts are
from Player Core's equipment tables. Rules references:
https://2e.aonprd.com/Classes.aspx?ID=57
https://2e.aonprd.com/Instincts.aspx?ID=8
https://2e.aonprd.com/Instincts.aspx?ID=9
https://2e.aonprd.com/Instincts.aspx?ID=10
https://2e.aonprd.com/Instincts.aspx?ID=11
https://2e.aonprd.com/Instincts.aspx?ID=12
https://2e.aonprd.com/Instincts.aspx?ID=13
https://2e.aonprd.com/Equipment.aspx?Category=1&Subcategory=2
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .barbarian import (
    ANIMAL_INSTINCT,
    ANIMALS_BY_ID,
    DRAGON_INSTINCT,
    DRAGONS_BY_ID,
    FURY_INSTINCT,
    GIANT_INSTINCT,
    GIANT_WEAPONS_BY_ID,
    INSTINCT_IDS,
    MOMENT_OF_CLARITY,
    RAGING_THROWER,
    RAGING_INTIMIDATION,
    SPIRIT_INSTINCT,
    SUPERSTITION_INSTINCT,
    BarbarianBuildChoices,
    BarbarianState,
    DRAGON_CHOICES,
    build_barbarian_state,
)
from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
)


@dataclass(frozen=True)
class LoadoutItem:
    item_id: str
    bulk: int
    market_price_gp: int
    paid_price_gp: int
    granted_by: str | None = None


@dataclass(frozen=True)
class BarbarianLoadout:
    armor_category: str
    starting_money_gp: int
    items: tuple[LoadoutItem, ...]

    @property
    def remaining_money_gp(self) -> int:
        return self.starting_money_gp - sum(item.paid_price_gp for item in self.items)

    @property
    def total_bulk(self) -> int:
        return sum(item.bulk for item in self.items)


@dataclass(frozen=True)
class BarbarianCharacter:
    definition: CreatureDefinition
    barbarian_state: BarbarianState
    loadout: BarbarianLoadout


def _animal_attacks(animal_choice: str | None) -> tuple[AttackDefinition, ...]:
    if animal_choice is None:
        return ()
    animal = ANIMALS_BY_ID[animal_choice]
    return tuple(
        AttackDefinition(
            attack_id=profile.attack_id,
            name=profile.name,
            modifier=7,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "unarmed", *profile.traits}),
            damage_type=profile.damage_type,
            damage_dice=profile.damage_dice,
            damage_modifier=4,
            attack_attribute="strength",
            damage_attribute="strength",
        )
        for profile in animal.attacks
    )


def _feat_label(feat_id: str) -> str:
    return {
        RAGING_INTIMIDATION: "Raging Intimidation",
        MOMENT_OF_CLARITY: "Moment of Clarity",
    }.get(feat_id, " ".join(word.capitalize() for word in feat_id.split("_")))


def build_barbarian(
    *,
    instinct_id: str,
    animal_choice: str | None = None,
    dragon_choice: str | None = None,
    giant_weapon_id: str | None = None,
    class_feat_id: str | None = None,
    bonus_feat_id: str | None = None,
    actor_definition_id: str | None = None,
) -> BarbarianCharacter:
    """Build the reviewed shared human sheet with a selected instinct.

    The fixed build records Human/Skilled Human/Natural Skill, Warrior, class
    skills, costs, and the free Titan Mauler weapon where used.
    """
    if instinct_id not in INSTINCT_IDS:
        raise ValueError(f"Unknown Barbarian instinct {instinct_id!r}.")
    if class_feat_id is None:
        class_feat_id = RAGING_INTIMIDATION
    if instinct_id == FURY_INSTINCT and bonus_feat_id is None:
        bonus_feat_id = MOMENT_OF_CLARITY
    state = build_barbarian_state(
        BarbarianBuildChoices(
            instinct_id=instinct_id,
            class_feat_id=class_feat_id,
            animal_choice=animal_choice,
            dragon_choice=dragon_choice,
            giant_weapon_id=giant_weapon_id,
            bonus_feat_id=bonus_feat_id,
        )
    )

    if instinct_id == ANIMAL_INSTINCT:
        suffix = animal_choice
    elif instinct_id == DRAGON_INSTINCT:
        suffix = dragon_choice
    elif instinct_id == GIANT_INSTINCT:
        suffix = giant_weapon_id
    else:
        suffix = instinct_id
    definition_id = actor_definition_id or f"barbarian_{instinct_id}_{suffix}"

    weapon_id = "longsword"
    weapon_name = "Longsword"
    weapon_damage_type = "slashing"
    weapon_damage_dice = (8,)
    weapon_traits = frozenset({"attack", "melee", "versatile-p"})
    weapon_hands_required = 1
    held_items = (weapon_id,)
    weapon_bulk = 1
    weapon_market_price_gp = 1
    weapon_paid_gp = 1
    weapon_grant = None
    if instinct_id == GIANT_INSTINCT:
        giant_weapon = GIANT_WEAPONS_BY_ID[giant_weapon_id or ""]
        weapon_id = giant_weapon.weapon_id
        weapon_name = f"{giant_weapon.name} (free Titan Mauler weapon)"
        weapon_damage_type = giant_weapon.damage_type
        weapon_damage_dice = giant_weapon.damage_dice
        weapon_traits = frozenset({"attack", "melee", *giant_weapon.traits})
        weapon_hands_required = giant_weapon.hands_required
        held_items = (weapon_id,)
        weapon_bulk = giant_weapon.bulk
        weapon_market_price_gp = giant_weapon.large_price_gp
        weapon_paid_gp = 0
        weapon_grant = "Titan Mauler"

    loadout = BarbarianLoadout(
        armor_category="medium",
        starting_money_gp=15,
        items=(
            LoadoutItem("breastplate", bulk=2, market_price_gp=8, paid_price_gp=8),
            LoadoutItem(
                weapon_id,
                bulk=weapon_bulk,
                market_price_gp=weapon_market_price_gp,
                paid_price_gp=weapon_paid_gp,
                granted_by=weapon_grant,
            ),
        ),
    )
    notes: tuple[str, ...] = (
        "Level 1 Human Barbarian: ancestry 8 HP + class 12 HP + Constitution 3 HP = 23 HP.",
        "Flexible ancestry boosts and class boosts produce Str +4, Dex +1, Con +3, Int +0, Wis +1, Cha +0.",
        "Skilled Human trains Medicine; Natural Skill trains Acrobatics and Society.",
        "Warrior background trains Intimidation and Warfare Lore and grants Intimidating Glare.",
        "Raging Intimidation grants Intimidating Glare, already granted by Warrior; the duplicate grants no additional feat.",
        "Barbarian skills: Athletics, Crafting, Nature, and Survival. Other skills are the recorded ancestry, heritage, and background grants.",
        "Breastplate is trained medium armor (+4 item bonus, Dexterity cap +1); AC 18.",
        f"Starting money remaining after breastplate and weapon: {loadout.remaining_money_gp} gp.",
        "Quick-Tempered is a free Rage trigger at initiative when its requirements hold.",
    )
    if instinct_id == GIANT_INSTINCT:
        notes += (
            f"Titan Mauler grant: common martial melee longsword; base price {giant_weapon.price_gp} gp before size adjustment.",
            f"The Large longsword has ordinary Large-item price {giant_weapon.large_price_gp} gp and Bulk {giant_weapon.bulk}.",
            "This free personal weapon has no resale value before runes and does not enlarge the actor or increase its damage die or reach.",
        )
    if instinct_id == ANIMAL_INSTINCT:
        animal = ANIMALS_BY_ID[animal_choice or ""]
        groups = ", ".join(
            f"{profile.name} ({profile.weapon_group} group)"
            for profile in animal.attacks
        )
        notes += (
            f"Animal Instinct attack groups: {groups}.",
            "Granted Animal Instinct attacks count as unarmed attacks in the brawling weapon group; the group is family-local metadata, and this level-1 sheet does not model level-5 Weapon Specialization.",
        )

    feats = (
        "Natural Skill",
        "Intimidating Glare",
        _feat_label(state.class_feat_id or RAGING_INTIMIDATION),
        *((_feat_label(state.bonus_feat_id),) if state.bonus_feat_id is not None else ()),
    )
    skills = (
        ("acrobatics", "trained", 4),
        ("athletics", "trained", 7),
        ("crafting", "trained", 3),
        ("intimidation", "trained", 3),
        ("medicine", "trained", 4),
        ("nature", "trained", 4),
        ("society", "trained", 3),
        ("survival", "trained", 4),
        ("warfare_lore", "trained", 3),
    )
    if RAGING_INTIMIDATION in {state.class_feat_id, state.bonus_feat_id} and not any(
        name == "intimidation" and rank is not None for name, rank, _modifier in skills
    ):
        raise ValueError("Raging Intimidation requires trained Intimidation.")
    abilities = (
        "rage",
        "quick_tempered",
        f"barbarian_instinct:{instinct_id}",
    )
    if instinct_id == ANIMAL_INSTINCT:
        abilities += ("animal_instinct_attacks",)
    elif instinct_id == DRAGON_INSTINCT:
        abilities += ("draconic_rage",)
    elif instinct_id == FURY_INSTINCT:
        abilities += ("unstoppable_frenzy",)
    elif instinct_id == GIANT_INSTINCT:
        abilities += ("titan_mauler",)
    elif instinct_id == SPIRIT_INSTINCT:
        abilities += ("spirit_rage",)
    elif instinct_id == SUPERSTITION_INSTINCT:
        abilities += ("superstitious_resilience",)

    attacks = (
        AttackDefinition(
            attack_id=weapon_id,
            name=weapon_name,
            modifier=7,
            reach_ft=5,
            traits=weapon_traits,
            damage_type=weapon_damage_type,
            damage_dice=weapon_damage_dice,
            damage_modifier=4,
            item_id=weapon_id,
            hands_required=weapon_hands_required,
            attack_attribute="strength",
            damage_attribute="strength",
        ),
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=7,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "unarmed", "nonlethal"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=4,
            attack_attribute="strength",
            damage_attribute="strength",
        ),
        *_animal_attacks(animal_choice),
    )
    carried_bulk = tuple((item.item_id, item.bulk) for item in loadout.items)
    definition = CreatureDefinition(
        definition_id=definition_id,
        name=f"Level 1 {instinct_id.title()} Instinct Barbarian",
        hp=23,
        ac=18,
        perception=6,
        land_speed_ft=25,
        attacks=attacks,
        kind="pc",
        health_mode=HealthMode.PC,
        abilities=abilities,
        feats=feats,
        ability_modifiers=(
            ("strength", 4),
            ("dexterity", 1),
            ("constitution", 3),
            ("intelligence", 0),
            ("wisdom", 1),
            ("charisma", 0),
        ),
        skills=skills,
        saves=(
            ("fortitude", "expert", 8),
            ("reflex", "trained", 4),
            ("will", "expert", 6),
        ),
        proficiencies=(
            ("perception", "expert"),
            ("fortitude", "expert"),
            ("reflex", "trained"),
            ("will", "expert"),
            ("simple_weapons", "trained"),
            ("martial_weapons", "trained"),
            ("unarmed_attacks", "trained"),
            ("unarmored_defense", "trained"),
            ("light_armor", "trained"),
            ("medium_armor", "trained"),
            ("class_dc", "trained"),
        ),
        sheet_notes=notes,
        held_items=held_items,
        worn_items=("breastplate",),
        hero_points=1,
        size="medium",
        level=1,
        ancestry="Human",
        heritage="Skilled Human",
        background="Warrior",
        class_name="Barbarian",
        languages=("Common",),
        class_dc=17,
        armor_category=loadout.armor_category,
        carried_item_bulk=carried_bulk,
    )
    return BarbarianCharacter(definition, state, loadout)


def _build_raging_thrower() -> BarbarianCharacter:
    """The selected Fury alternate with three tracked mundane daggers."""
    from dataclasses import replace
    from .items import ItemInstance

    base = build_barbarian(
        instinct_id=FURY_INSTINCT,
        class_feat_id=RAGING_THROWER,
        bonus_feat_id=MOMENT_OF_CLARITY,
        actor_definition_id="barbarian_fury_raging_thrower",
    )
    dagger = AttackDefinition(
        "dagger", "Dagger", 7, 5,
        frozenset({"attack", "melee", "agile", "finesse", "thrown", "weapon"}),
        "piercing", (4,), 4, item_id="dagger", attack_attribute="strength",
        damage_attribute="strength", range_increment_ft=10, max_range_ft=60,
    )
    thrown = replace(
        dagger, attack_id="dagger_thrown", name="Dagger (Thrown)", modifier=4,
        attack_attribute="dexterity", reach_ft=0,
        traits=frozenset({"attack", "ranged", "agile", "finesse", "thrown", "weapon"}),
    )
    definition = replace(
        base.definition,
        name="Level 1 Fury Barbarian (Raging Thrower)",
        attacks=(dagger, thrown, base.definition.attacks[1]),
        held_items=("dagger_1",), stowed_items=("dagger_2", "dagger_3"),
        item_instances=(
            ItemInstance("dagger_1", "dagger"),
            ItemInstance("dagger_2", "dagger"),
            ItemInstance("dagger_3", "dagger"),
        ),
        carried_item_bulk=(("dagger_1", 0), ("dagger_2", 0), ("dagger_3", 0), ("breastplate", 2)),
        sheet_notes=base.definition.sheet_notes + (
            "Raging Thrower applies Rage damage to authorized thrown weapon Strikes; the three daggers retain stable instance identities.",
            "Moment of Clarity remains the distinct Fury bonus feat.",
        ),
    )
    return BarbarianCharacter(definition, base.barbarian_state, base.loadout)


DRAGON_BARBARIAN_CHARACTERS: Mapping[str, BarbarianCharacter] = MappingProxyType(
    {
        dragon.dragon_id: build_barbarian(
            instinct_id=DRAGON_INSTINCT,
            dragon_choice=dragon.dragon_id,
            actor_definition_id=f"barbarian_dragon_{dragon.dragon_id}",
        )
        for dragon in DRAGON_CHOICES
    }
)

DRAGON_BARBARIAN_DEFINITIONS: tuple[CreatureDefinition, ...] = tuple(
    character.definition for character in DRAGON_BARBARIAN_CHARACTERS.values()
)

DRAGON_BARBARIAN_INITIAL_STATES: Mapping[str, BarbarianState] = MappingProxyType(
    {
        character.definition.definition_id: character.barbarian_state
        for character in DRAGON_BARBARIAN_CHARACTERS.values()
    }
)

ANIMAL_BARBARIAN_CHARACTERS: Mapping[str, BarbarianCharacter] = MappingProxyType(
    {
        animal_id: build_barbarian(
            instinct_id=ANIMAL_INSTINCT,
            animal_choice=animal_id,
            actor_definition_id=f"barbarian_animal_{animal_id}",
        )
        for animal_id in ("cat", "frog")
    }
)

ANIMAL_BARBARIAN_DEFINITIONS: tuple[CreatureDefinition, ...] = tuple(
    character.definition for character in ANIMAL_BARBARIAN_CHARACTERS.values()
)

ANIMAL_BARBARIAN_INITIAL_STATES: Mapping[str, BarbarianState] = MappingProxyType(
    {
        character.definition.definition_id: character.barbarian_state
        for character in ANIMAL_BARBARIAN_CHARACTERS.values()
    }
)

BARBARIAN_SAMPLE_CHARACTERS: Mapping[str, BarbarianCharacter] = MappingProxyType(
    {
        "animal": build_barbarian(instinct_id=ANIMAL_INSTINCT, animal_choice="bear"),
        "dragon": DRAGON_BARBARIAN_CHARACTERS["diabolic"],
        "fury": build_barbarian(instinct_id=FURY_INSTINCT),
        "giant": build_barbarian(instinct_id=GIANT_INSTINCT, giant_weapon_id="giant_large_longsword"),
        "spirit": build_barbarian(instinct_id=SPIRIT_INSTINCT),
        "superstition": build_barbarian(instinct_id=SUPERSTITION_INSTINCT),
        "raging_thrower": _build_raging_thrower(),
    }
)

# The accepted Bear slice and the complete Dragon level-1 family are admitted
# to the runtime. Other instinct examples remain source/table fixtures.
BARBARIAN_SLICE1_CHARACTER = BARBARIAN_SAMPLE_CHARACTERS["animal"]
BARBARIAN_DEFINITIONS: tuple[CreatureDefinition, ...] = (
    BARBARIAN_SLICE1_CHARACTER.definition,
    *DRAGON_BARBARIAN_DEFINITIONS,
    *ANIMAL_BARBARIAN_DEFINITIONS,
    BARBARIAN_SAMPLE_CHARACTERS["raging_thrower"].definition,
)
BARBARIAN_INITIAL_STATES: Mapping[str, BarbarianState] = MappingProxyType(
    {
        BARBARIAN_SLICE1_CHARACTER.definition.definition_id: BARBARIAN_SLICE1_CHARACTER.barbarian_state,
        **DRAGON_BARBARIAN_INITIAL_STATES,
        **ANIMAL_BARBARIAN_INITIAL_STATES,
        BARBARIAN_SAMPLE_CHARACTERS["raging_thrower"].definition.definition_id: BARBARIAN_SAMPLE_CHARACTERS["raging_thrower"].barbarian_state,
    }
)
BARBARIAN_LOADOUTS: Mapping[str, BarbarianLoadout] = MappingProxyType(
    {
        character.definition.definition_id: character.loadout
        for character in (
            *BARBARIAN_SAMPLE_CHARACTERS.values(),
            *DRAGON_BARBARIAN_CHARACTERS.values(),
            *ANIMAL_BARBARIAN_CHARACTERS.values(),
            BARBARIAN_SAMPLE_CHARACTERS["raging_thrower"],
        )
    }
)


BARBARIAN_TEST_ENEMY = CreatureDefinition(
    definition_id="barbarian_test_enemy",
    name="Barbarian Test Guard",
    hp=24,
    ac=15,
    perception=2,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="guard_spear",
            name="Spear",
            modifier=5,
            reach_ft=5,
            traits=frozenset({"attack", "melee"}),
            damage_type="piercing",
            damage_dice=(6,),
            damage_modifier=2,
        ),
    ),
    kind="ordinary_npc",
    health_mode=HealthMode.ORDINARY,
    abilities=(),
    saves=(("will", "trained", 3),),
    size="medium",
    level=0,
)

DRAGON_BARBARIAN_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        f"barbarian_dragon_{dragon_id}_rage_test": EncounterSetup(
            setup_id=f"barbarian_dragon_{dragon_id}_rage_test",
            name=f"{dragon_id.capitalize()} Dragon Barbarian Rage Test",
            width=7,
            height=5,
            placements=(
                CreaturePlacement(
                    actor_id="dragon_barbarian",
                    definition_id=character.definition.definition_id,
                    label=f"{dragon_id.capitalize()} Dragon Barbarian",
                    team="blue",
                    position=Position(2, 2),
                ),
                CreaturePlacement(
                    actor_id="dragon_guard",
                    definition_id=BARBARIAN_TEST_ENEMY.definition_id,
                    label="Test Guard",
                    team="red",
                    position=Position(3, 2),
                ),
            ),
        )
        for dragon_id, character in DRAGON_BARBARIAN_CHARACTERS.items()
    }
)

ANIMAL_BARBARIAN_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        f"barbarian_animal_{animal_id}_rage_test": EncounterSetup(
            setup_id=f"barbarian_animal_{animal_id}_rage_test",
            name=f"{animal_id.capitalize()} Animal Barbarian Rage Test",
            width=7,
            height=5,
            placements=(
                CreaturePlacement(
                    actor_id="animal_barbarian",
                    definition_id=character.definition.definition_id,
                    label=f"{animal_id.capitalize()} Barbarian",
                    team="blue",
                    position=Position(2, 2),
                ),
                CreaturePlacement(
                    actor_id="animal_guard",
                    definition_id=BARBARIAN_TEST_ENEMY.definition_id,
                    label="Test Guard",
                    team="red",
                    position=Position(3, 2),
                ),
            ),
        )
        for animal_id, character in ANIMAL_BARBARIAN_CHARACTERS.items()
    }
)

BARBARIAN_TEST_SETUP = EncounterSetup(
    setup_id="barbarian_rage_test",
    name="Barbarian Rage and Instinct Test",
    width=7,
    height=5,
    placements=(
        CreaturePlacement(
            actor_id="barbarian_test",
            definition_id=BARBARIAN_SLICE1_CHARACTER.definition.definition_id,
            label="Barbarian",
            team="blue",
            position=Position(2, 2),
        ),
        CreaturePlacement(
            actor_id="barbarian_guard",
            definition_id=BARBARIAN_TEST_ENEMY.definition_id,
            label="Test Guard",
            team="red",
            position=Position(4, 2),
        ),
    ),
)
