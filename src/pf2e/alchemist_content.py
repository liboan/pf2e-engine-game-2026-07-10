"""Selected Human Bomber Alchemist level-1 sheet and first combat fixture."""

from .items import ItemInstance
from .model import AttackDefinition, CreatureDefinition, CreaturePlacement, EncounterSetup, HealthMode, Position
from .alchemy_content import BombFacts, FORMULAS_BY_ID


BOMBER_FIELD_FORMULA_IDS = ("bottled_lightning_lesser", "frost_vial_lesser")
BOMBER_LEVEL_2_BOMB_FORMULA_IDS = ("alchemists_fire_lesser", "acid_flask_lesser")
BOMBER_COMBAT_FORMULA_IDS = (*BOMBER_FIELD_FORMULA_IDS, *BOMBER_LEVEL_2_BOMB_FORMULA_IDS)
BOMBER_FORMULA_IDS = (*BOMBER_FIELD_FORMULA_IDS, "elixir_of_life_minor", "antidote_lesser", "antiplague_lesser", "bestial_mutagen_lesser", "cognitive_mutagen_lesser", "giant_centipede_venom")


def admitted_bomber_bomb_facts(formula_id: object, *, character_level: int = 1) -> BombFacts | None:
    """Return facts for the finite Bomber bomb menu at a character level.

    The general catalog intentionally contains additional reference bombs.  A
    combat caller must opt into this finite menu before treating a formula's
    catalog facts as an admitted thrown-bomb effect.  The two level-2 variants
    are deliberately unavailable to the level-1 sheet.
    """
    if type(character_level) is not int or character_level not in {1, 2}:
        return None
    allowed = BOMBER_FIELD_FORMULA_IDS if character_level == 1 else BOMBER_COMBAT_FORMULA_IDS
    if not isinstance(formula_id, str) or formula_id not in allowed:
        return None
    facts = FORMULAS_BY_ID[formula_id].facts
    return facts if isinstance(facts, BombFacts) else None


def _bomber_bomb_attack(attack_id: str, name: str, formula_id: str, *, modifier: int = 6, character_level: int = 1) -> AttackDefinition:
    facts = admitted_bomber_bomb_facts(formula_id, character_level=character_level)
    if facts is None:  # The selected sheet and its finite field pair must agree.
        raise ValueError(f"Bomber attack {attack_id!r} lacks admitted bomb facts.")
    return AttackDefinition(
        attack_id, name, modifier, facts.range_increment_ft,
        frozenset({"attack", "ranged", "thrown", "bomb", "splash"}),
        facts.damage_type, facts.initial_damage_dice, facts.initial_damage_flat,
        item_id=formula_id, attack_attribute="dexterity", damage_attribute=None,
        range_increment_ft=facts.range_increment_ft,
        max_range_ft=facts.range_increment_ft * 6, striking_applies=False,
    )


BOMBER_LEVEL_2_BOMB_ATTACKS = (
    _bomber_bomb_attack("alchemists_fire", "Alchemist's Fire", "alchemists_fire_lesser", modifier=7, character_level=2),
    _bomber_bomb_attack("acid_flask", "Acid Flask", "acid_flask_lesser", modifier=7, character_level=2),
)


BOMBER_ALCHEMIST = CreatureDefinition(
    definition_id="bomber_alchemist_level_1_staged", name="Level 1 Bomber Alchemist",
    hp=17, ac=17, perception=4, land_speed_ft=30, kind="pc", health_mode=HealthMode.PC, hero_points=1,
    attacks=(
        AttackDefinition("dagger", "Dagger", 6, 5, frozenset({"attack", "melee", "agile", "finesse", "thrown"}), "piercing", (4,), 0, item_id="dagger", attack_attribute="dexterity", range_increment_ft=10, max_range_ft=50),
        _bomber_bomb_attack("bottled_lightning", "Bottled Lightning", "bottled_lightning_lesser"),
        _bomber_bomb_attack("frost_vial", "Frost Vial", "frost_vial_lesser"),
    ),
    ability_modifiers=(("strength", 0), ("dexterity", 3), ("constitution", 1), ("intelligence", 4), ("wisdom", 1), ("charisma", 0)),
    skills=(("crafting", "trained", 7), ("arcana", "trained", 7), ("occultism", "trained", 7), ("society", "trained", 7), ("stealth", "trained", 6), ("thievery", "trained", 6), ("survival", "trained", 4), ("acrobatics", "trained", 6), ("athletics", "trained", 3), ("medicine", "trained", 4), ("nature", "trained", 4), ("academia_lore", "trained", 7)),
    saves=(("fortitude", "expert", 6), ("reflex", "expert", 8), ("will", "trained", 4)),
    proficiencies=(("perception", "trained"), ("fortitude", "expert"), ("reflex", "expert"), ("will", "trained"), ("simple_weapons", "trained"), ("unarmed_attacks", "trained"), ("bombs", "trained"), ("light_armor", "trained"), ("medium_armor", "trained"), ("unarmored_defense", "trained"), ("class_dc", "trained")),
    ancestry="Human", heritage="Versatile Human", background="Scholar", class_name="Alchemist", languages=("Common", "Elven"), class_dc=17,
    abilities=("bomber_alchemist", "quick_bomber", "assurance_nature"), feats=("Quick Bomber", "Fleet", "Natural Skill", "Assurance (Nature)", "Alchemical Crafting"),
    held_items=("dagger",), worn_items=("leather_armor", "alchemists_toolkit"), stowed_items=("bottled_lightning_lesser", "frost_vial_lesser"),
    item_instances=(ItemInstance("dagger", "dagger"), ItemInstance("bottled_lightning_lesser", "bottled_lightning_lesser"), ItemInstance("frost_vial_lesser", "frost_vial_lesser")),
    sheet_notes=("Human Versatile Human Scholar Bomber Alchemist: 17 HP, AC 17, Speed 30, and a finite eight-formula book.", "Quick Bomber draws selected infused bombs; ordinary thrown weapons still use the separate recovery rule.", "Other field benefits, general crafting, persistent Alchemist's Fire, and the stabilized-0-HP positive-damage boundary remain outside this selected level-1 slice."),
)

BOMBER_ALCHEMIST_SETUP = EncounterSetup(
    "staged_bomber_alchemist_vs_guard_dog", "Staged Bomber Alchemist versus Guard Dog", 7, 5,
    (CreaturePlacement("alchemist", BOMBER_ALCHEMIST.definition_id, "Bomber Alchemist", "blue", Position(1, 2)), CreaturePlacement("dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))),
)

# A fresh opponent keeps the authored recovery route playable after the
# Bomber's rest, preparation, and save/load boundary.
BOMBER_ALCHEMIST_NEXT_SETUP = EncounterSetup(
    "staged_bomber_alchemist_next_vs_guard_dog", "Prepared Bomber Alchemist versus Guard Dog", 7, 5,
    (CreaturePlacement("alchemist", BOMBER_ALCHEMIST.definition_id, "Bomber Alchemist", "blue", Position(1, 2)), CreaturePlacement("next_dog", "guard_dog_mc2924", "Guard Dog", "red", Position(4, 2))),
)
