"""Level-1 Rogue racket definitions and the deliberately small weapon subset.

These are sheet snapshots for four distinct Player Core racket choices, not
proof that their class abilities have been integrated into public encounters.
The Ruffian definition carries a simple club so its admitted critical
specialization uses the implemented Club effect. Other weapon groups remain
explicitly outside this slice's critical-specialization coverage.

Sources checked 2026-09-15:
- Rogue: https://2e.aonprd.com/Classes.aspx?ID=37
- Rackets: https://2e.aonprd.com/Rackets.aspx
- Club: https://2e.aonprd.com/Weapons.aspx?ID=166
- Nimble Dodge: https://2e.aonprd.com/Feats.aspx?ID=4916
- Intimidating Glare: https://2e.aonprd.com/Feats.aspx?ID=5162
"""

from dataclasses import dataclass
from types import MappingProxyType

from .model import AttackDefinition, CreatureDefinition, HealthMode
from .rogue import RogueRacket, WeaponCategory


@dataclass(frozen=True)
class RogueWeaponFacts:
    """Weapon-group/category facts absent from the shared Strike record."""

    item_id: str
    category: WeaponCategory
    group: str
    damage_die_sides: int
    is_melee_weapon: bool = True


ROGUE_WEAPON_FACTS = MappingProxyType(
    {
        "club": RogueWeaponFacts("club", WeaponCategory.SIMPLE, "club", 6),
        "dagger": RogueWeaponFacts("dagger", WeaponCategory.SIMPLE, "knife", 4),
        "rapier": RogueWeaponFacts("rapier", WeaponCategory.MARTIAL, "sword", 6),
        "shortsword": RogueWeaponFacts("shortsword", WeaponCategory.MARTIAL, "sword", 6),
    }
)


def _trained_skill(name: str, ability: str, modifiers: dict[str, int]) -> tuple[str, str, int]:
    return name, "trained", 3 + modifiers[ability]


def _build(racket: RogueRacket) -> CreatureDefinition:
    if racket is RogueRacket.MASTERMIND:
        ability_modifiers = {
            "strength": 0,
            "dexterity": 2,
            "constitution": 2,
            "intelligence": 4,
            "wisdom": 1,
            "charisma": 0,
        }
        key_attribute = "intelligence"
        weapon = "dagger"
        extra_racket_skills = (("society", "intelligence"), ("arcana", "intelligence"))
        additional = (
            ("acrobatics", "dexterity"),
            ("athletics", "strength"),
            ("crafting", "intelligence"),
            ("deception", "charisma"),
            ("diplomacy", "charisma"),
            ("intimidation", "charisma"),
            ("medicine", "wisdom"),
            ("nature", "wisdom"),
            ("occultism", "intelligence"),
            ("thievery", "dexterity"),
            ("survival", "wisdom"),
        )
        racket_note = "Mastermind trains Society and Arcana; its Intelligence key attribute is selected."
        background_skill = ("religion", "wisdom")
    elif racket is RogueRacket.RUFFIAN:
        ability_modifiers = {
            "strength": 4,
            "dexterity": 2,
            "constitution": 2,
            "intelligence": 1,
            "wisdom": 0,
            "charisma": 0,
        }
        key_attribute = "strength"
        weapon = "club"
        extra_racket_skills = (("intimidation", "charisma"),)
        additional = (
            ("acrobatics", "dexterity"),
            ("athletics", "strength"),
            ("crafting", "intelligence"),
            ("deception", "charisma"),
            ("diplomacy", "charisma"),
            ("medicine", "wisdom"),
            ("society", "intelligence"),
            ("thievery", "dexterity"),
        )
        racket_note = "Ruffian trains Intimidation and medium armor; its Strength key attribute is selected."
        background_skill = ("nature", "wisdom")
    elif racket is RogueRacket.SCOUNDREL:
        ability_modifiers = {
            "strength": 0,
            "dexterity": 3,
            "constitution": 1,
            "intelligence": 1,
            "wisdom": 0,
            "charisma": 4,
        }
        key_attribute = "charisma"
        weapon = "rapier"
        extra_racket_skills = (("deception", "charisma"), ("diplomacy", "charisma"))
        additional = (
            ("acrobatics", "dexterity"),
            ("athletics", "strength"),
            ("crafting", "intelligence"),
            ("intimidation", "charisma"),
            ("medicine", "wisdom"),
            ("nature", "wisdom"),
            ("society", "intelligence"),
            ("thievery", "dexterity"),
        )
        racket_note = "Scoundrel trains Deception and Diplomacy; its Charisma key attribute is selected."
        background_skill = ("survival", "wisdom")
    else:
        ability_modifiers = {
            "strength": 2,
            "dexterity": 4,
            "constitution": 2,
            "intelligence": 1,
            "wisdom": 0,
            "charisma": 0,
        }
        key_attribute = "dexterity"
        weapon = "dagger"
        extra_racket_skills = (("thievery", "dexterity"),)
        additional = (
            ("acrobatics", "dexterity"),
            ("athletics", "strength"),
            ("crafting", "intelligence"),
            ("deception", "charisma"),
            ("diplomacy", "charisma"),
            ("intimidation", "charisma"),
            ("medicine", "wisdom"),
            ("society", "intelligence"),
        )
        racket_note = "Thief trains Thievery and keeps Dexterity as its key attribute."
        background_skill = ("nature", "wisdom")

    training = (("stealth", "dexterity"),) + extra_racket_skills + additional
    supplemental_training = (
        ("performance", "charisma"),
        ("warfare_lore", "intelligence"),
        background_skill,
        ("underworld_lore", "intelligence"),
    )
    skills = tuple(
        _trained_skill(name, ability, ability_modifiers)
        for name, ability in training + supplemental_training
    )
    attacks = _attacks_for(racket, weapon, ability_modifiers)
    dexterity = ability_modifiers["dexterity"]
    constitution = ability_modifiers["constitution"]
    wisdom = ability_modifiers["wisdom"]
    key_modifier = ability_modifiers[key_attribute]
    definition_id = f"rogue_{racket.value}_level_1"
    proficiencies = (
        ("perception", "expert"),
        ("fortitude", "trained"),
        ("reflex", "expert"),
        ("will", "expert"),
        ("simple_weapons", "trained"),
        ("martial_weapons", "trained"),
        ("unarmed_attacks", "trained"),
        ("unarmored_defense", "trained"),
        ("light_armor", "trained"),
        ("class_dc", "trained"),
    )
    if racket is RogueRacket.RUFFIAN:
        proficiencies += (("medium_armor", "trained"),)

    # Each build uses a standard simple or martial one-handed melee weapon.
    # The shared module admits the Club critical specialization for the
    # Ruffian fixture only; other possible weapon-group choices are not
    # included in this bounded content family.
    return CreatureDefinition(
        definition_id=definition_id,
        name=f"Level 1 Rogue ({racket.value.title()} Racket)",
        hp=16 + constitution,
        ac=14 + dexterity,
        perception=5 + wisdom,
        land_speed_ft=25,
        attacks=attacks,
        kind="pc",
        health_mode=HealthMode.PC,
        abilities=("sneak_attack", "surprise_attack", f"rogue_racket_{racket.value}"),
        feats=("Natural Skill", "Nimble Dodge", "Intimidating Glare", "Assurance (Athletics)"),
        ability_modifiers=tuple(ability_modifiers.items()),
        skills=skills,
        saves=(
            ("fortitude", "trained", 3 + constitution),
            ("reflex", "expert", 5 + dexterity),
            ("will", "expert", 5 + wisdom),
        ),
        proficiencies=proficiencies,
        held_items=(weapon,),
        worn_items=("leather_armor",),
        hero_points=1,
        size="medium",
        level=1,
        ancestry="Human",
        heritage="Versatile Human",
        background="Custom",
        class_name="Rogue",
        languages=("Common",),
        class_dc=13 + key_modifier,
        sheet_notes=(
            f"Level-1 Human Rogue; {racket.value.title()} racket. Key attribute {key_attribute.title()} +{key_modifier}.",
            racket_note,
            "Rogue class skills: Stealth and racket skills, plus 7 + Intelligence modifier additional trained skills.",
            "Human Natural Skill trains Performance and Warfare Lore; the custom background trains one additional skill and Underworld Lore.",
            "Nimble Dodge is the selected level-1 Rogue feat. Intimidating Glare is the Rogue skill feat; Assurance (Athletics) is the background skill feat.",
            "Sneak Attack is 1d6 precision damage on each qualifying Strike; this definition does not impose a once-per-turn limit.",
            "Ruffian's admitted weapon is a simple d6 club. On a critical hit against an off-guard target, its supported Club critical specialization can push the target up to 10 feet.",
            "No public encounter playability is implied by this character definition alone.",
            "Sources: https://2e.aonprd.com/Classes.aspx?ID=37; https://2e.aonprd.com/Rackets.aspx; https://2e.aonprd.com/Weapons.aspx?ID=166; https://2e.aonprd.com/Feats.aspx?ID=4916; https://2e.aonprd.com/Feats.aspx?ID=5162",
        ),
    )


def _attacks_for(
    racket: RogueRacket,
    weapon: str,
    ability_modifiers: dict[str, int],
) -> tuple[AttackDefinition, ...]:
    weapon_data = {
        "club": ("Club", 6, "bludgeoning", frozenset({"attack", "melee", "thrown", "weapon"}), "strength", "strength", None),
        "dagger": ("Dagger", 4, "piercing", frozenset({"attack", "melee", "agile", "finesse", "thrown", "weapon"}), "dexterity", "strength", None),
        "rapier": ("Rapier", 6, "piercing", frozenset({"attack", "melee", "finesse", "deadly", "weapon"}), "dexterity", "strength", 8),
    }
    name, die, damage_type, traits, attack_attribute, damage_attribute, deadly_die = weapon_data[weapon]
    damage_mod = ability_modifiers[damage_attribute]
    if racket is RogueRacket.THIEF and weapon == "dagger":
        damage_attribute = "dexterity"
        damage_mod = ability_modifiers["dexterity"]
    fist_damage_attribute = "dexterity" if racket is RogueRacket.THIEF else "strength"
    attacks = [
        AttackDefinition(
            attack_id=weapon,
            name=name,
            modifier=3 + ability_modifiers[attack_attribute],
            reach_ft=5,
            traits=traits,
            damage_type=damage_type,
            damage_dice=(die,),
            damage_modifier=damage_mod,
            item_id=weapon,
            attack_attribute=attack_attribute,
            damage_attribute=damage_attribute,
            deadly_die=deadly_die,
            hands_required=1,
        ),
        AttackDefinition(
            attack_id="fist",
            name="Fist",
            modifier=3 + ability_modifiers["dexterity"],
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
            damage_type="bludgeoning",
            damage_dice=(4,),
            damage_modifier=ability_modifiers[fist_damage_attribute],
            attack_attribute="dexterity",
            damage_attribute=fist_damage_attribute,
            hands_required=0,
        ),
    ]
    if weapon == "dagger":
        attacks.append(
            AttackDefinition(
                attack_id="dagger_thrown",
                name="Dagger (Thrown)",
                modifier=3 + ability_modifiers["dexterity"],
                reach_ft=0,
                traits=frozenset({"attack", "ranged", "agile", "finesse", "thrown", "weapon"}),
                damage_type="piercing",
                damage_dice=(4,),
                damage_modifier=ability_modifiers["strength"],
                item_id="dagger",
                attack_attribute="dexterity",
                damage_attribute="strength",
                range_increment_ft=10,
                max_range_ft=60,
                hands_required=1,
            )
        )
    return tuple(attacks)


ROGUE_MASTERMIND = _build(RogueRacket.MASTERMIND)
ROGUE_RUFFIAN = _build(RogueRacket.RUFFIAN)
ROGUE_SCOUNDREL = _build(RogueRacket.SCOUNDREL)
ROGUE_THIEF = _build(RogueRacket.THIEF)

ROGUE_DEFINITIONS = MappingProxyType(
    {
        definition.definition_id: definition
        for definition in (
            ROGUE_MASTERMIND,
            ROGUE_RUFFIAN,
            ROGUE_SCOUNDREL,
            ROGUE_THIEF,
        )
    }
)


def _playable_thief() -> CreatureDefinition:
    """The one level-1 Thief build admitted to public encounter play.

    The four racket snapshots above remain source/reference fixtures.  This
    definition is the legal Warrior/Skilled Human/Natural Skill sheet used by
    the runtime encounter and intentionally contains only shortsword and fist
    attacks.
    """
    modifiers = {
        "strength": 2,
        "dexterity": 4,
        "constitution": 2,
        "intelligence": 1,
        "wisdom": 0,
        "charisma": 0,
    }
    skills = tuple(
        _trained_skill(name, ability, modifiers)
        for name, ability in (
            ("stealth", "dexterity"),
            ("thievery", "dexterity"),
            ("acrobatics", "dexterity"),
            ("athletics", "strength"),
            ("deception", "charisma"),
            ("diplomacy", "charisma"),
            ("nature", "wisdom"),
            ("occultism", "intelligence"),
            ("religion", "wisdom"),
            ("survival", "wisdom"),
            ("medicine", "wisdom"),
            ("crafting", "intelligence"),
            ("society", "intelligence"),
            ("intimidation", "charisma"),
            ("warfare_lore", "intelligence"),
        )
    )
    shortsword = AttackDefinition(
        attack_id="shortsword",
        name="Shortsword",
        modifier=7,
        reach_ft=5,
        traits=frozenset({"attack", "melee", "agile", "finesse", "versatile-s", "weapon"}),
        damage_type="piercing",
        damage_dice=(6,),
        damage_modifier=4,
        item_id="shortsword",
        attack_attribute="dexterity",
        damage_attribute="dexterity",
        hands_required=1,
    )
    fist = AttackDefinition(
        attack_id="fist",
        name="Fist",
        modifier=7,
        reach_ft=5,
        traits=frozenset({"attack", "melee", "agile", "finesse", "nonlethal", "unarmed"}),
        damage_type="bludgeoning",
        damage_dice=(4,),
        damage_modifier=4,
        attack_attribute="dexterity",
        damage_attribute="dexterity",
        hands_required=0,
    )
    return CreatureDefinition(
        definition_id="rogue_thief_warrior_level_1",
        name="Level 1 Thief Rogue (Warrior)",
        hp=18,
        ac=18,
        perception=5,
        land_speed_ft=25,
        attacks=(shortsword, fist),
        kind="pc",
        health_mode=HealthMode.PC,
        abilities=("sneak_attack", "surprise_attack", "rogue_racket_thief"),
        feats=("Natural Skill", "Nimble Dodge", "Intimidating Glare", "Assurance (Athletics)"),
        ability_modifiers=tuple(modifiers.items()),
        skills=skills,
        saves=(
            ("fortitude", "trained", 5),
            ("reflex", "expert", 9),
            ("will", "expert", 5),
        ),
        proficiencies=(
            ("perception", "expert"),
            ("fortitude", "trained"),
            ("reflex", "expert"),
            ("will", "expert"),
            ("simple_weapons", "trained"),
            ("martial_weapons", "trained"),
            ("unarmed_attacks", "trained"),
            ("unarmored_defense", "trained"),
            ("light_armor", "trained"),
            ("class_dc", "trained"),
        ),
        held_items=("shortsword",),
        worn_items=("leather_armor",),
        hero_points=1,
        size="medium",
        level=1,
        ancestry="Human",
        heritage="Skilled Human",
        background="Warrior",
        class_name="Rogue",
        languages=("Common", "Goblin"),
        class_dc=17,
        armor_category="light",
        carried_item_bulk=(("shortsword", 1), ("leather_armor", 1)),
        sheet_notes=(
            "Legal fixed build: Warrior background, Skilled Human, Natural Skill, Assurance (Athletics), and Nimble Dodge.",
            "Shortsword: +7 attack, 1d6 piercing/slashing; Thief applies Dexterity to this finesse melee damage.",
            "Fist: +7 attack, 1d4 bludgeoning, nonlethal; Thief applies Dexterity to this finesse melee damage.",
            "Skilled Human trains Medicine; Natural Skill trains Crafting and Society; Warrior trains Intimidation and Warfare Lore.",
            "Rogue class skills are Stealth, Thievery, Acrobatics, Athletics, Deception, Diplomacy, Nature, Occultism, Religion, and Survival.",
            "This setup uses Deception for initiative only in an observed social confrontation. Stealth selection does not implement Avoid Notice or detection.",
            "Starting equipment is leather armor and shortsword; 12 gp, 1 sp remains. One additional legal language is selected for Intelligence +1.",
            "Sources: https://2e.aonprd.com/Classes.aspx?ID=37; https://2e.aonprd.com/Rackets.aspx?ID=9; https://2e.aonprd.com/Backgrounds.aspx?ID=445; https://2e.aonprd.com/Weapons.aspx?ID=398; https://2e.aonprd.com/Feats.aspx?ID=4916; https://2e.aonprd.com/Feats.aspx?ID=5121",
        ),
    )


ROGUE_THIEF_PLAYABLE = _playable_thief()
# Public aliases make the selected representative discoverable without
# changing the older four-racket source inventory above.
THIEF_ROGUE = ROGUE_THIEF_PLAYABLE
ROGUE_PLAYABLE_DEFINITIONS = MappingProxyType(
    {ROGUE_THIEF_PLAYABLE.definition_id: ROGUE_THIEF_PLAYABLE}
)
