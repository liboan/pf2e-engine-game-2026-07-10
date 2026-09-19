"""Selected normal-catalog level-2 Precision Ranger facts.

This definition retains the admitted level-1 bow package and adds only the
selected level-2 class and skill feats.

Sources checked 2026-09-18:

* Ranger class advancement: https://2e.aonprd.com/Classes.aspx?ID=36
* Hunter's Aim: https://2e.aonprd.com/Feats.aspx?ID=4867
* Assurance: https://2e.aonprd.com/Feats.aspx?ID=5121
"""

from dataclasses import replace

from .model import CreatureDefinition, CreaturePlacement, EncounterSetup, Position
from .ranger_monk_content import RANGER_PRECISION


# At level 2 the selected Ranger has no ability boosts yet.  Each trained or
# expert total increases by one from level, HP gains class HP + Constitution,
# and the Dex-keyed class DC gains one likewise.
_LEVEL_2_SKILLS = (
    ("acrobatics", "trained", 8),
    ("athletics", "trained", 5),
    ("crafting", "trained", 4),
    ("deception", "trained", 4),
    ("forest_lore", "trained", 4),
    ("medicine", "trained", 6),
    ("nature", "trained", 6),
    ("society", "trained", 4),
    ("stealth", "trained", 8),
    ("survival", "trained", 6),
)
_LEVEL_2_SAVES = (
    ("fortitude", "expert", 8),
    ("reflex", "expert", 10),
    ("will", "trained", 6),
)


RANGER_PRECISION_LEVEL_2: CreatureDefinition = replace(
    RANGER_PRECISION,
    definition_id="ranger_precision_level_2_hunters_aim",
    name="Level 2 Ranger (Precision, Hunter's Aim)",
    hp=32,
    ac=19,
    perception=8,
    attacks=tuple(replace(attack, modifier=attack.modifier + 1) for attack in RANGER_PRECISION.attacks),
    abilities=(*RANGER_PRECISION.abilities, "hunters_aim", "assurance_athletics"),
    feats=(*RANGER_PRECISION.feats, "Hunter's Aim", "Assurance (Athletics)"),
    skills=_LEVEL_2_SKILLS,
    saves=_LEVEL_2_SAVES,
    vision="ordinary",
    level=2,
    class_dc=18,
    sheet_notes=(
        *RANGER_PRECISION.sheet_notes,
        "Level 2: Ranger HP is 20 + (10 class HP + Constitution 2), for 32 HP. Proficiency totals increase with level; there are no ability boosts at level 2.",
        "Hunter's Aim is the selected level-2 Ranger class feat: spend two actions to make one ranged weapon Strike against current hunted prey, with +2 circumstance to the attack roll. This admitted procedure ignores concealment and lesser creature cover only; ordinary cover, range penalties, ammunition, reactions, and MAP remain in the common Strike route.",
        "Assurance (Athletics) is the selected level-2 skill feat. It uses the existing public Athletics maneuver route and its fixed proficiency result; it does not add an exploration requirement.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=36; https://2e.aonprd.com/Feats.aspx?ID=4867; https://2e.aonprd.com/Feats.aspx?ID=5121.",
    ),
)


RANGER_PRECISION_LEVEL_2_HUNTERS_AIM_SETUP = EncounterSetup(
    setup_id="staged_ranger_precision_level_2_hunters_aim",
    name="Staged Level 2 Precision Ranger Hunter's Aim",
    width=7,
    height=3,
    placements=(
        CreaturePlacement(
            "ranger",
            RANGER_PRECISION_LEVEL_2.definition_id,
            "Level 2 Precision Ranger",
            "blue",
            Position(0, 1),
        ),
        # This living creature supplies lesser creature cover to the actual
        # prey, so the set-up exercises the narrowly admitted cover exception.
        CreaturePlacement("cover", "guard_dog_mc2924", "Cover Dog", "red", Position(2, 1)),
        CreaturePlacement("prey", "guard_dog_mc2924", "Prey Dog", "red", Position(4, 1)),
    ),
)
