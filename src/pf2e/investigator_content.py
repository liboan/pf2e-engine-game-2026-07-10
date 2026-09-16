"""Selected level-1 Forensic Investigator sheet and first-play setup.

This is one authored build for the Player Core 2 Investigator. It records the
legal sheet facts needed by the first Devise a Stratagem, Recall Knowledge,
Known Weaknesses and Battle Medicine encounters. Keeping the definition here
lets the runtime catalog admit the whole sheet only when its public actions
are ready.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=59
* https://2e.aonprd.com/Methodologies.aspx?ID=7
* https://2e.aonprd.com/Feats.aspx?ID=5936
* https://2e.aonprd.com/Ancestries.aspx?ID=64 (Human)
* https://2e.aonprd.com/Heritages.aspx?ID=261 (Skilled Human)
* https://2e.aonprd.com/Feats.aspx?ID=4479 (Natural Skill)
* https://2e.aonprd.com/Backgrounds.aspx (Detective)
* https://2e.aonprd.com/Weapons.aspx?ID=398 (shortsword)
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .model import (
    AttackDefinition,
    CreatureDefinition,
    CreaturePlacement,
    EncounterSetup,
    HealthMode,
    Position,
)
from .items import ItemInstance
from .investigator import (
    DEVISE_ABILITY,
    FORENSIC_ACUMEN_ABILITY,
    BATTLE_MEDICINE_ABILITY,
    FORENSIC_MEDICINE_ABILITY,
    KNOWN_WEAKNESSES_ABILITY,
)


@dataclass(frozen=True)
class RecallKnowledgeContent:
    """One authored Recall Knowledge question for a bounded encounter.

    A record supplies the GM judgments that the engine cannot infer: the
    question, eligible skills and DC progression, and the information allowed
    for each degree. ``subject_definition_id`` lets one record apply to all
    instances of a creature without introducing a creature-fact ontology.
    """

    subject_key: str
    question: str
    allowed_skills: tuple[tuple[str, int], ...]
    dc_progression: tuple[int, ...]
    answer: str
    critical_context: str = ""
    failure_answer: str | None = None
    critical_failure_answer: str | None = None
    false_answer: str | None = None
    communication_recipients: tuple[str, ...] = ()
    subject_actor_id: str | None = None
    subject_definition_id: str | None = None
    investigation_relevant: bool = False
    # A non-creature subject (such as an examined body) has a label but no
    # fabricated CreatureState. Existing creature records leave this unset.
    subject_label: str | None = None

    def __post_init__(self) -> None:
        if not self.subject_key or not self.question or not self.answer:
            raise ValueError("Recall Knowledge records need a subject, question, and answer")
        if any(
            not isinstance(value, str) or not value
            for value in (self.subject_key, self.question, self.answer)
        ):
            raise ValueError("Recall Knowledge subject, question, and answer must be non-empty text")
        if (
            not isinstance(self.allowed_skills, tuple)
            or not self.allowed_skills
            or any(
                not isinstance(row, tuple)
                or len(row) != 2
                or not isinstance(row[0], str)
                or not row[0]
                or type(row[1]) is not int
                or row[1] < 0
                for row in self.allowed_skills
            )
        ):
            raise ValueError("Recall Knowledge records need typed skill/DC pairs")
        if len({skill for skill, _dc in self.allowed_skills}) != len(self.allowed_skills):
            raise ValueError("Recall Knowledge records cannot repeat an allowed skill")
        if (
            not isinstance(self.dc_progression, tuple)
            or not self.dc_progression
            or any(type(dc) is not int or dc < 0 for dc in self.dc_progression)
        ):
            raise ValueError("Recall Knowledge records need a non-empty DC progression")
        if (
            self.subject_actor_id is not None
            and (not isinstance(self.subject_actor_id, str) or not self.subject_actor_id)
        ):
            raise ValueError("Recall Knowledge subject actor id must be non-empty text")
        if (
            self.subject_definition_id is not None
            and (not isinstance(self.subject_definition_id, str) or not self.subject_definition_id)
        ):
            raise ValueError("Recall Knowledge subject definition id must be non-empty text")
        if self.subject_label is not None and (
            not isinstance(self.subject_label, str) or not self.subject_label
        ):
            raise ValueError("Recall Knowledge subject label must be non-empty text")
        optional_answers = (
            self.critical_context,
            self.failure_answer,
            self.critical_failure_answer,
            self.false_answer,
        )
        if any(value is not None and (not isinstance(value, str) or not value) for value in optional_answers):
            raise ValueError("Recall Knowledge outcome text must be non-empty text or None")
        if type(self.investigation_relevant) is not bool:
            raise ValueError("Recall Knowledge investigation relevance must be boolean")
        if (
            not isinstance(self.communication_recipients, tuple)
            or any(not isinstance(recipient, str) or not recipient for recipient in self.communication_recipients)
            or len(set(self.communication_recipients)) != len(self.communication_recipients)
        ):
            raise ValueError("Recall Knowledge communication recipients must be non-empty actor ids")

    @property
    def skills(self) -> tuple[tuple[str, int], ...]:
        """Compatibility alias for callers that call the pairs ``skills``."""
        return self.allowed_skills

    @property
    def successive_dcs(self) -> tuple[int, ...]:
        """Compatibility alias for the authored successive attempt stages."""
        return self.dc_progression


KnowledgeContent = RecallKnowledgeContent


@dataclass(frozen=True)
class ForensicExaminationContent:
    """One authored outside-combat Forensic Acumen examination.

    ``follow_up_records`` are the finite relevant Recall Knowledge questions
    offered after a successful Medicine check. They remain authored content;
    no creature-fact or mystery ontology is inferred by the runtime.
    """

    body_key: str
    body_label: str
    medicine_question: str
    medicine_dc: int
    ordinary_duration_seconds: int
    success_answer: str
    critical_success_answer: str | None = None
    failure_answer: str | None = None
    critical_failure_answer: str | None = None
    accessible: bool = True
    body_actor_id: str | None = None
    follow_up_records: tuple[RecallKnowledgeContent, ...] = ()
    examination_key: str | None = None

    def __post_init__(self) -> None:
        text_values = (
            self.body_key,
            self.body_label,
            self.medicine_question,
            self.success_answer,
        )
        if any(not isinstance(value, str) or not value for value in text_values):
            raise ValueError("Forensic examination needs non-empty body, question, and result text")
        if self.examination_key is not None and (
            not isinstance(self.examination_key, str) or not self.examination_key
        ):
            raise ValueError("Forensic examination key must be non-empty text")
        if type(self.medicine_dc) is not int or self.medicine_dc < 0:
            raise ValueError("Forensic examination Medicine DC must be non-negative")
        if (
            type(self.ordinary_duration_seconds) is not int
            or self.ordinary_duration_seconds < 600
        ):
            raise ValueError("Forensic examination duration must be at least ten minutes")
        if type(self.accessible) is not bool:
            raise ValueError("Forensic examination accessibility must be boolean")
        if self.body_actor_id is not None and (
            not isinstance(self.body_actor_id, str) or not self.body_actor_id
        ):
            raise ValueError("Forensic examination body actor id must be non-empty text")
        outcome_text = (
            self.critical_success_answer,
            self.failure_answer,
            self.critical_failure_answer,
        )
        if any(value is not None and (not isinstance(value, str) or not value) for value in outcome_text):
            raise ValueError("Forensic examination outcome text must be non-empty text or None")
        if (
            not isinstance(self.follow_up_records, tuple)
            or any(not isinstance(record, RecallKnowledgeContent) for record in self.follow_up_records)
        ):
            raise ValueError("Forensic examination follow-ups must be authored Recall Knowledge records")
        keys = [record.subject_key for record in self.follow_up_records]
        if len(set(keys)) != len(keys):
            raise ValueError("Forensic examination follow-ups cannot repeat a subject key")
        if any(not record.investigation_relevant for record in self.follow_up_records):
            raise ValueError("Forensic examination follow-ups must be relevant authored knowledge")

    @property
    def subject_key(self) -> str:
        """Use the body key as the shared subject-history key."""
        return self.body_key

    @property
    def duration_seconds(self) -> int:
        """Compatibility alias for callers that use the shorter duration name."""
        return self.ordinary_duration_seconds

    @property
    def accessible_body(self) -> bool:
        """Compatibility alias for the authored accessible-body fact."""
        return self.accessible

    @property
    def key(self) -> str:
        """Stable completion key; defaults to the authored body key."""
        return self.examination_key or self.body_key


ExaminationContent = ForensicExaminationContent


# This is a deliberately small GM-authored fact packet.  It supplies a
# concrete question for the staged guard-dog scenes while the engine remains
# agnostic about creature knowledge in general.
GUARD_DOG_KNOWLEDGE = RecallKnowledgeContent(
    subject_key="guard_dog",
    question="What useful weakness can you recall about this guard dog?",
    allowed_skills=(
        ("society", 16),
        ("nature", 16),
        ("crafting", 18),
    ),
    dc_progression=(16, 18, 20),
    answer="The guard dog is trained to track by scent and has no special resistance relevant to this scene.",
    critical_context="You also recognize the pack's practiced signals; an informed ally can exploit its opening.",
    communication_recipients=(),
    subject_definition_id="guard_dog_mc2924",
)

FORENSIC_INJURY_CAUSE_KNOWLEDGE = RecallKnowledgeContent(
    subject_key="forensic_injury_cause",
    subject_label="the body's injury",
    question="What caused the injuries to this body?",
    allowed_skills=(("crafting", 16),),
    dc_progression=(16, 18),
    answer="The wound pattern came from a hooked blade, not a natural attack.",
    critical_context="You can reconstruct the attacker's angle and the creature's final movement.",
    investigation_relevant=True,
)

FORENSIC_CREATURE_TYPE_KNOWLEDGE = RecallKnowledgeContent(
    subject_key="forensic_creature_type",
    subject_label="the examined body",
    question="What creature type does this body belong to?",
    allowed_skills=(("nature", 16),),
    dc_progression=(16, 18),
    answer="The remains are from a trained guard dog.",
    critical_context="The signs confirm the same handler's training marks found elsewhere in the case.",
    investigation_relevant=True,
)


def _guard_dog_examination(body_actor_id: str) -> ForensicExaminationContent:
    return ForensicExaminationContent(
        body_key="forensic_guard_dog_body",
        body_label="Guard Dog Body",
        medicine_question="What can you determine from the injuries on this body?",
        medicine_dc=15,
        ordinary_duration_seconds=600,
        success_answer="The injuries were inflicted shortly before death and show a deliberate attack.",
        critical_success_answer="The injuries were inflicted shortly before death; you also reconstruct the attack's sequence.",
        failure_answer="You cannot determine a useful cause from the injuries.",
        critical_failure_answer="The injuries yield no reliable information.",
        body_actor_id=body_actor_id,
        follow_up_records=(
            FORENSIC_INJURY_CAUSE_KNOWLEDGE,
            FORENSIC_CREATURE_TYPE_KNOWLEDGE,
        ),
    )


FORENSIC_GUARD_DOG_EXAMINATION = _guard_dog_examination("investigator_guard_dog_a")
FORENSIC_HEALING_DOG_EXAMINATION = _guard_dog_examination("healing_dog")
# Short aliases for callers authoring a single staged body examination.
FORENSIC_EXAMINATION = FORENSIC_GUARD_DOG_EXAMINATION
BODY_EXAMINATION = FORENSIC_GUARD_DOG_EXAMINATION


FORENSIC_INVESTIGATOR = CreatureDefinition(
    definition_id="investigator_forensic_level_1",
    name="Level 1 Forensic Investigator",
    hp=17,
    ac=17,
    perception=6,
    land_speed_ft=25,
    attacks=(
        AttackDefinition(
            attack_id="shortsword",
            name="Shortsword",
            modifier=6,
            reach_ft=5,
            traits=frozenset({"attack", "melee", "agile", "finesse", "weapon"}),
            damage_type="piercing",
            damage_dice=(6,),
            damage_modifier=0,
            item_id="shortsword",
            attack_attribute="dexterity",
            damage_attribute="strength",
        ),
    ),
    kind="pc",
    health_mode=HealthMode.PC,
    abilities=(
        DEVISE_ABILITY,
        FORENSIC_MEDICINE_ABILITY,
        FORENSIC_ACUMEN_ABILITY,
        BATTLE_MEDICINE_ABILITY,
        KNOWN_WEAKNESSES_ABILITY,
    ),
    feats=("Natural Skill", "Forensic Acumen", "Known Weaknesses", "Battle Medicine", "Streetwise"),
    ability_modifiers=(
        ("strength", 0),
        ("dexterity", 3),
        ("constitution", 1),
        ("intelligence", 4),
        ("wisdom", 1),
        ("charisma", 0),
    ),
    skills=(
        ("society", "trained", 7),
        ("medicine", "trained", 4),
        ("underworld_lore", "trained", 7),
        ("diplomacy", "trained", 3),
        ("deception", "trained", 3),
        ("survival", "trained", 4),
        ("intimidation", "trained", 3),
        ("crafting", "trained", 7),
        ("arcana", "trained", 7),
        ("occultism", "trained", 7),
        ("religion", "trained", 4),
        ("stealth", "trained", 6),
        ("thievery", "trained", 6),
        ("acrobatics", "trained", 6),
        ("athletics", "trained", 3),
    ),
    saves=(
        ("fortitude", "trained", 4),
        ("reflex", "expert", 8),
        ("will", "expert", 6),
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
    worn_items=("leather_armor", "healers_toolkit"),
    item_instances=(ItemInstance("healers_toolkit", "healers_toolkit"),),
    hero_points=1,
    size="medium",
    level=1,
    ancestry="Human",
    heritage="Skilled Human",
    background="Detective",
    class_name="Investigator",
    languages=("Common", "Dwarven", "Elven", "Goblin", "Halfling", "Orcish"),
    class_dc=17,
    sheet_notes=(
        "Level-1 Human Forensic Investigator; Intelligence is the key attribute (+4).",
        "Class HP 8 + Human ancestry HP 8 + Constitution 1 = 17 HP.",
        "The fixed ability spread is Str +0, Dex +3, Con +1, Int +4, Wis +1, Cha +0.",
        "Initial proficiencies: expert Perception, expert Reflex and Will, trained Fortitude, trained attacks and light armor.",
        "Detective grants Society and Underworld Lore; Society duplicates the class training, so Diplomacy is the selected replacement skill.",
        "Skilled Human selects Deception; Natural Skill selects Survival and Intimidation as its two additional trained skills.",
        "The Human has five extra languages from 1 + Intelligence modifier: Dwarven, Elven, Goblin, Halfling, and Orcish.",
        "Streetwise is the Detective skill feat; Natural Skill is the selected level-1 Human ancestry feat.",
        "Society, the replacement Diplomacy, the selected heritage and ancestry skills, and the Forensic Medicine methodology's Medicine are trained; the remaining listed skills are the authored additional training.",
        "Forensic Medicine grants Battle Medicine. Known Weaknesses embeds the authored Recall Knowledge question in Devise for these scenes.",
        "Forensic Medicine adds the investigator's level to Battle Medicine healing on a success and changes that target's Battle Medicine immunity to 1 hour.",
        "Forensic Acumen halves this authored body examination to 5 minutes and offers relevant immediate Recall Knowledge follow-up.",
        "Devise's attack stratagem is the only Investigator family action admitted by the first-play slice; the skill stratagem and lead-aware free use reject explicitly until their procedures exist.",
        "A shortsword is agile and finesse, so an attack stratagem may substitute Intelligence for Strength or Dexterity and then add Strategic Strike 1d6 precision.",
        "Sources: https://2e.aonprd.com/Classes.aspx?ID=59; https://2e.aonprd.com/Methodologies.aspx?ID=7; https://2e.aonprd.com/Feats.aspx?ID=5936",
    ),
)


FORENSIC_INVESTIGATOR_VS_TWO_DOGS = EncounterSetup(
    setup_id="investigator_forensic_vs_two_guard_dogs",
    name="Forensic Investigator's Attack Stratagem",
    width=7,
    height=3,
    placements=(
        CreaturePlacement(
            "forensic_investigator",
            FORENSIC_INVESTIGATOR.definition_id,
            "Forensic Investigator",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "investigator_guard_dog_a",
            "guard_dog_mc2924",
            "Guard Dog A",
            "red",
            Position(2, 1),
        ),
        CreaturePlacement(
            "investigator_guard_dog_b",
            "guard_dog_mc2924",
            "Guard Dog B",
            "red",
            Position(2, 2),
        ),
    ),
    knowledge=(GUARD_DOG_KNOWLEDGE,),
    examinations=(FORENSIC_GUARD_DOG_EXAMINATION,),
)


FORENSIC_INVESTIGATOR_HEALING_SETUP = EncounterSetup(
    setup_id="investigator_forensic_healing_vs_ally",
    name="Forensic Investigator's Battle Medicine",
    width=5,
    height=3,
    placements=(
        CreaturePlacement(
            "forensic_investigator",
            FORENSIC_INVESTIGATOR.definition_id,
            "Forensic Investigator",
            "blue",
            Position(1, 1),
        ),
        CreaturePlacement(
            "healing_ally",
            "fighter_m_level_1",
            "Healing Ally",
            "blue",
            Position(2, 1),
        ),
        CreaturePlacement(
            "healing_dog",
            "guard_dog_mc2924",
            "Guard Dog",
            "red",
            Position(4, 2),
        ),
    ),
    knowledge=(GUARD_DOG_KNOWLEDGE,),
    examinations=(FORENSIC_HEALING_DOG_EXAMINATION,),
)


INVESTIGATOR_DEFINITIONS: Mapping[str, CreatureDefinition] = MappingProxyType(
    {FORENSIC_INVESTIGATOR.definition_id: FORENSIC_INVESTIGATOR}
)
INVESTIGATOR_SETUPS: Mapping[str, EncounterSetup] = MappingProxyType(
    {
        FORENSIC_INVESTIGATOR_VS_TWO_DOGS.setup_id: FORENSIC_INVESTIGATOR_VS_TWO_DOGS,
        FORENSIC_INVESTIGATOR_HEALING_SETUP.setup_id: FORENSIC_INVESTIGATOR_HEALING_SETUP,
    }
)
