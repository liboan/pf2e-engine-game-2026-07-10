"""The bounded level-1 Investigator stratagem procedure.

This module owns the rule facts that are specific to the first admitted
Investigator play slice.  The encounter core owns the actual Strike check,
damage transaction, and persistence representation.  The module deliberately
keeps a stratagem's preliminary d20 separate from :class:`CheckResult`: the
face is a stored input for a later attack and is never itself a check.

Sources checked 2026-09-16:

* https://2e.aonprd.com/Classes.aspx?ID=59
* https://2e.aonprd.com/Actions.aspx?ID=2813
* https://2e.aonprd.com/Methodologies.aspx?ID=7
* https://2e.aonprd.com/Feats.aspx?ID=5125
* https://2e.aonprd.com/Actions.aspx?ID=2399
* https://2e.aonprd.com/Equipment.aspx?ID=2727
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, ClassVar, Protocol

from .checks import CheckResult, DegreeOfSuccess, Modifier, resolve_check
from .damage import DamageTerm, roll_damage_terms
from .health import healing as pc_healing
from .model import (
    AttackDefinition,
    ActionContinuation,
    ChoiceOption,
    Event,
    FamilyCommand,
    FamilyProcedureContext,
    FamilyProcedureResult,
    HealthMode,
)
from .space import grid_distance_feet


DEVISE_ABILITY = "investigator_devise_stratagem"
FORENSIC_MEDICINE_ABILITY = "investigator_forensic_medicine"
FORENSIC_ACUMEN_ABILITY = "investigator_forensic_acumen"
BATTLE_MEDICINE_ABILITY = "investigator_battle_medicine"
KNOWN_WEAKNESSES_ABILITY = "investigator_known_weaknesses"
ATTACK_STRATAGEM = "attack"
SKILL_STRATAGEM = "skill"
_BATTLE_MEDICINE_FEAT = "Battle Medicine"
_HEALER_TOOLKIT_DEFINITION = "healers_toolkit"
_BATTLE_MEDICINE_TRAITS = frozenset({"healing", "manipulate", "skill"})
_BATTLE_MEDICINE_DC = 15
_FORENSIC_IMMUNITY_SECONDS = 60 * 60


class _ActorWithStratagem(Protocol):
    """The small actor surface needed by the independent rule helpers."""

    investigator_stratagem: "InvestigatorStratagemState | None"


@dataclass(frozen=True)
class DeviseStratagem(FamilyCommand):
    """Use Devise a Stratagem against one visible creature.

    ``free_action`` is intentionally explicit.  Lead-aware free use belongs
    to the later investigation slice; this first public action accepts only
    the ordinary one-action form and rejects an attempted free use rather
    than silently ignoring that field.
    """

    family_id: ClassVar[str] = "martial"
    target_id: str
    mode: str = ATTACK_STRATAGEM
    free_action: bool = False
    known_weaknesses: bool = False


@dataclass(frozen=True)
class RecallKnowledge(FamilyCommand):
    """Use one action to resolve an authored Recall Knowledge question."""

    family_id: ClassVar[str] = "martial"
    subject_key: str
    question: str | None = None
    skill: str | None = None
    target_id: str | None = None
    # Forensic Acumen follow-ups carry their one authored circumstance bonus
    # through a saved command; ordinary Recall Knowledge leaves this at zero.
    circumstance_bonus: int = 0
    forensic_follow_up: bool = False


# Alias retained for callers that use the full action name.
RecallKnowledgeAction = RecallKnowledge


@dataclass(frozen=True)
class ForensicExamination(FamilyCommand):
    """Persist one outside-combat Forensic Acumen examination continuation."""

    family_id: ClassVar[str] = "martial"
    examination_key: str


ForensicExamine = ForensicExamination
ExamineBody = ForensicExamination


@dataclass(frozen=True)
class AuthoredKnowledgeSubject:
    """A labeled non-creature subject used without fabricating a live actor."""

    subject_key: str
    label: str
    actor_id: str | None = None
    definition_id: str | None = None
    defeated: bool = False
    unconscious: bool = False


@dataclass(frozen=True)
class InvestigatorWeaknessBonus:
    """A Known Weakness +1 circumstance bonus awaiting one attack."""

    source_actor_id: str
    target_actor_id: str
    recipient_actor_id: str
    expires_at_actor_start: int


@dataclass(frozen=True)
class BattleMedicine(FamilyCommand):
    """Attempt the selected Investigator's one-action Battle Medicine."""

    family_id: ClassVar[str] = "martial"
    target_id: str
    dc: int = _BATTLE_MEDICINE_DC


@dataclass(frozen=True)
class InvestigatorStratagemState:
    """One stored stratagem, valid only for the current owner turn.

    ``turn_start`` is the owner's monotonically increasing turn-start count,
    so an unused die expires when the next turn begins even if other actors'
    turns do not advance the round number.
    """

    target_id: str
    die: int
    mode: str
    round_number: int
    turn_start: int
    consumed: bool = False


def validate_stratagem_state(state: InvestigatorStratagemState) -> None:
    """Validate a persisted stratagem before it can re-enter encounter play."""

    if not isinstance(state, InvestigatorStratagemState):
        raise ValueError("saved Investigator stratagem has the wrong type")
    if not isinstance(state.target_id, str) or not state.target_id:
        raise ValueError("saved Investigator stratagem requires a target")
    if type(state.die) is not int or not 1 <= state.die <= 20:
        raise ValueError("saved Investigator stratagem die must be from 1 through 20")
    if state.mode not in {ATTACK_STRATAGEM, SKILL_STRATAGEM}:
        raise ValueError("saved Investigator stratagem has an unknown mode")
    if type(state.round_number) is not int or state.round_number < 1:
        raise ValueError("saved Investigator stratagem round must be positive")
    if type(state.turn_start) is not int or state.turn_start < 1:
        raise ValueError("saved Investigator stratagem turn start must be positive")
    if type(state.consumed) is not bool:
        raise ValueError("saved Investigator stratagem consumed flag must be boolean")


def stratagem_to_data(state: InvestigatorStratagemState | None) -> dict[str, Any] | None:
    """Encode the exact state shape used by the versioned JSON save."""

    if state is None:
        return None
    validate_stratagem_state(state)
    return {
        "target_id": state.target_id,
        "die": state.die,
        "mode": state.mode,
        "round_number": state.round_number,
        "turn_start": state.turn_start,
        "consumed": state.consumed,
    }


def stratagem_from_data(data: Any) -> InvestigatorStratagemState | None:
    """Decode and validate one saved stratagem or an empty slot."""

    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("save has invalid Investigator stratagem")
    state = InvestigatorStratagemState(
        target_id=data.get("target_id"),
        die=data.get("die"),
        mode=data.get("mode"),
        round_number=data.get("round_number"),
        turn_start=data.get("turn_start"),
        consumed=data.get("consumed"),
    )
    try:
        validate_stratagem_state(state)
    except ValueError as error:
        raise ValueError("save has invalid Investigator stratagem") from error
    return state


def intelligence_substitution_eligible(attack: AttackDefinition) -> bool:
    """Whether Devise may substitute Intelligence for this Strike.

    Ranged weapon attacks are eligible.  A melee weapon, melee unarmed
    attack, or thrown weapon must have Agile or Finesse, as printed by
    Devise a Stratagem.  This function only answers the weapon gate; it does
    not decide whether the actor actually chose Intelligence.
    """

    if not isinstance(attack, AttackDefinition):
        raise ValueError("attack must be an AttackDefinition")
    traits = attack.traits
    if "melee" in traits or "thrown" in traits:
        return bool({"agile", "finesse"} & traits)
    if "ranged" in traits:
        return True
    return False


def strategic_strike_damage_term(
    attack: AttackDefinition,
    *,
    used_intelligence: bool,
    investigator_level: int,
) -> DamageTerm | None:
    """Return Strategic Strike's separate precision term when it applies."""

    if not isinstance(attack, AttackDefinition):
        raise ValueError("attack must be an AttackDefinition")
    if type(used_intelligence) is not bool:
        raise ValueError("used_intelligence must be a boolean")
    if type(investigator_level) is not int or investigator_level < 1:
        raise ValueError("investigator_level must be a positive integer")
    if not used_intelligence:
        return None
    if not intelligence_substitution_eligible(attack):
        return None
    dice_count = 1 + max(0, (investigator_level - 1) // 4)
    return DamageTerm(
        source="investigator_strategic_strike",
        damage_type=attack.damage_type,
        dice=(6,) * dice_count,
        tags=frozenset({"precision"}),
        critical_mode="double",
    )


def stratagem_for_attack(
    actor: _ActorWithStratagem,
    *,
    target_id: str,
    round_number: int,
    turn_start: int,
) -> InvestigatorStratagemState | None:
    """Return a still-valid attack stratagem for ``target_id``."""

    state = getattr(actor, "investigator_stratagem", None)
    if state is None:
        return None
    validate_stratagem_state(state)
    if state.mode != ATTACK_STRATAGEM or state.consumed:
        return None
    if state.target_id != target_id:
        return None
    if state.round_number != round_number or state.turn_start != turn_start:
        return None
    return state


def consume_stratagem(
    actor: _ActorWithStratagem,
    *,
    target_id: str,
    round_number: int,
    turn_start: int,
) -> tuple[int, InvestigatorStratagemState] | None:
    """Mark the first qualifying Strike as the stratagem consumer.

    The caller should invoke this exactly when the actual attack roll is
    about to be made, after target and reaction windows have resolved.  It
    returns the stored face and the consumed state; no new die is drawn.
    """

    state = stratagem_for_attack(
        actor,
        target_id=target_id,
        round_number=round_number,
        turn_start=turn_start,
    )
    if state is None:
        return None
    consumed = replace(state, consumed=True)
    actor.investigator_stratagem = consumed
    return state.die, consumed


def resolve_stratagem_check(
    state: InvestigatorStratagemState,
    *,
    modifier: int,
    dc: int,
    attack_id: str,
    attack_count: int,
    map_penalty: int,
    traits: frozenset[str],
) -> CheckResult:
    """Resolve a consumed attack stratagem without drawing another d20.

    The caller supplies the current Strike modifiers and MAP after all target
    and reaction decisions.  Adding ``fortune`` to the resolved attack record
    makes the source trait visible while leaving Hero Point eligibility to the
    encounter's explicit saved-check gate.
    """

    validate_stratagem_state(state)
    if state.mode != ATTACK_STRATAGEM or not state.consumed:
        raise ValueError("the stratagem must be an already-consumed attack stratagem")
    if type(modifier) is not int or type(dc) is not int:
        raise ValueError("stratagem check modifier and DC must be integers")
    if not isinstance(attack_id, str) or not attack_id:
        raise ValueError("stratagem check requires an attack id")
    if type(attack_count) is not int or attack_count < 1:
        raise ValueError("stratagem check attack count must be positive")
    if type(map_penalty) is not int:
        raise ValueError("stratagem check MAP must be an integer")
    if not isinstance(traits, frozenset):
        raise ValueError("stratagem check traits must be a frozenset")
    return resolve_check(
        state.die,
        modifier,
        dc,
        attack_id=attack_id,
        attack_count=attack_count,
        map_penalty=map_penalty,
        traits=(*traits, "fortune"),
    )


def _active_target(context: FamilyProcedureContext, target_id: str):
    if not isinstance(target_id, str) or not target_id:
        return None
    target = context.state.creatures.get(target_id)
    if target is None or target.actor_id == context.actor.actor_id or target.defeated:
        return None
    return target


def _knowledge_records(context: FamilyProcedureContext) -> tuple[Any, ...]:
    """Return the scene's explicitly authored knowledge records."""
    # ``FamilyProcedureContext`` is also used by focused unit tests with a
    # small fake encounter, so resolve the setup through the real state only
    # when it exists and otherwise report no authored records.
    setup_id = getattr(context.state, "setup_id", None)
    if not isinstance(setup_id, str):
        return ()
    from .content import get_setup

    return tuple(getattr(get_setup(setup_id), "knowledge", ()))


def _knowledge_content(
    context: FamilyProcedureContext,
    subject_key: str,
    target_id: str | None = None,
    additional_records: tuple[Any, ...] = (),
):
    if not isinstance(subject_key, str) or not subject_key:
        return None
    target = context.state.creatures.get(target_id) if target_id else None
    matches = []
    for record in (*_knowledge_records(context), *additional_records):
        if getattr(record, "subject_key", None) != subject_key:
            continue
        record_actor = getattr(record, "subject_actor_id", None)
        record_definition = getattr(record, "subject_definition_id", None)
        if target_id is not None:
            if record_actor is not None and record_actor != target_id:
                continue
            if target is None:
                continue
            if record_definition is not None and record_definition != target.definition_id:
                continue
        matches.append(record)
    return matches[0] if len(matches) == 1 else None


def _knowledge_target(
    context: FamilyProcedureContext,
    record: Any,
    target_id: str | None,
):
    actor_id = getattr(record, "subject_actor_id", None)
    resolved_id = target_id or actor_id
    if resolved_id is None:
        label = getattr(record, "subject_label", None)
        if isinstance(label, str) and label:
            return AuthoredKnowledgeSubject(
                subject_key=record.subject_key,
                label=label,
                definition_id=getattr(record, "subject_definition_id", None),
            )
        return None
    target = context.state.creatures.get(resolved_id)
    if target is None or target.actor_id == context.actor.actor_id:
        return None
    label = getattr(record, "subject_label", None)
    if target.defeated:
        if not isinstance(label, str) or not label:
            return None
        return AuthoredKnowledgeSubject(
            subject_key=record.subject_key,
            label=label,
            actor_id=target.actor_id,
            definition_id=target.definition_id,
            defeated=True,
            unconscious=target.unconscious,
        )
    if getattr(record, "subject_actor_id", None) not in {None, target.actor_id}:
        return None
    definition_id = getattr(record, "subject_definition_id", None)
    if definition_id is not None and target.definition_id != definition_id:
        return None
    return target


def _knowledge_dc(record: Any, attempts: int, skill: str | None = None) -> int:
    progression = tuple(getattr(record, "dc_progression", ()))
    if not progression:
        raise ValueError("Recall Knowledge has no authored DC progression")
    stage = progression[min(attempts, len(progression) - 1)]
    # The authored progression describes the successive DCs for the record's
    # first listed skill. Other eligible skills retain their authored initial
    # DC and follow the same successive increase, so a skill/DC pair is never
    # silently ignored.
    if skill is None:
        return stage
    allowed = dict(getattr(record, "allowed_skills", ()))
    base = allowed.get(skill)
    if base is None:
        return stage
    return base + stage - progression[0]


def _knowledge_check_event(actor, target, record, check: CheckResult, answer: str | None, *, critical: bool = False) -> Event:
    result_text = answer or "No useful information is available."
    suffix = " Critical success adds: " + getattr(record, "critical_context", "") if critical and getattr(record, "critical_context", "") else ""
    return Event(
        "recall_knowledge",
        actor.actor_id,
        getattr(target, "actor_id", None),
        f"{actor.label} recalls knowledge about {target.label}: {check.degree.label()} "
        f"({check.total} vs DC {check.dc}). {result_text}{suffix}",
        check=check,
        details=(
            f"Question: {record.question}",
            f"Subject: {record.subject_key}",
        ),
    )


def _knowledge_answer(record: Any, degree: DegreeOfSuccess) -> tuple[str | None, bool]:
    if degree is DegreeOfSuccess.CRITICAL_SUCCESS:
        return record.answer, True
    if degree is DegreeOfSuccess.SUCCESS:
        return record.answer, False
    if degree is DegreeOfSuccess.FAILURE:
        return getattr(record, "failure_answer", None) or getattr(record, "false_answer", None), False
    return getattr(record, "critical_failure_answer", None) or getattr(record, "false_answer", None), False


def _finalize_knowledge(
    context: FamilyProcedureContext,
    record: Any,
    target,
    command: RecallKnowledge,
    saved,
    *,
    known_weaknesses: bool = False,
) -> FamilyProcedureResult:
    if saved.result is None:
        return FamilyProcedureResult(rejection="The saved Recall Knowledge check has not been resolved.")
    check = saved.result
    actor = context.actor
    attempts = actor.investigator_knowledge_attempts.get(record.subject_key, 0)
    answer, critical = _knowledge_answer(record, check.degree)
    actor.investigator_knowledge_attempts[record.subject_key] = attempts + 1
    # The authored terminal stage ends the subject even on a success. Any
    # failure/critical failure also exhausts the subject per this GM packet.
    if check.degree in {DegreeOfSuccess.FAILURE, DegreeOfSuccess.CRITICAL_FAILURE} or attempts + 1 >= len(record.dc_progression):
        actor.investigator_knowledge_exhausted.add(record.subject_key)
    events = [_knowledge_check_event(actor, target, record, check, answer, critical=critical)]
    if answer is None:
        events.append(Event(
            "recall_knowledge_no_information",
            actor.actor_id,
            getattr(target, "actor_id", None),
            f"{actor.label} receives no useful information about {target.label}.",
        ))
    if (
        known_weaknesses
        and check.degree is DegreeOfSuccess.CRITICAL_SUCCESS
        and getattr(target, "actor_id", None) is not None
    ):
        # The investigator's own +1 is consumed only by the chosen attack
        # stratagem; explicitly informed allies each receive their own grant.
        recipients = tuple(getattr(record, "communication_recipients", ()))
        recipients = tuple(
            recipient for recipient in recipients
            if recipient in context.state.creatures
            and context.state.creatures[recipient].team == actor.team
            and recipient != actor.actor_id
            and not context.state.creatures[recipient].defeated
            and not context.state.creatures[recipient].unconscious
        )
        expiry = context.state.actor_start_counts.get(actor.actor_id, 0) + 1
        for recipient in (actor.actor_id, *recipients):
            context.state.investigator_weakness_bonuses.append(
                InvestigatorWeaknessBonus(
                    source_actor_id=actor.actor_id,
                    target_actor_id=target.actor_id,
                    recipient_actor_id=recipient,
                    expires_at_actor_start=expiry,
                )
            )
        events.append(Event(
            "known_weaknesses",
            actor.actor_id,
            target.actor_id,
            f"Known Weaknesses informs {len(recipients)} ally/ies; each receives +1 circumstance to the next attack against {target.label}.",
            details=(
                "The investigator's +1 applies only to the chosen attack stratagem.",
                f"Informed allies: {', '.join(recipients) if recipients else 'none'}.",
            ),
        ))
    return FamilyProcedureResult(events=tuple(events))


def _resolve_recall_knowledge(
    context: FamilyProcedureContext,
    command: RecallKnowledge,
    *,
    known_weaknesses: bool = False,
    record_override: Any | None = None,
    additional_modifiers: tuple[Modifier, ...] = (),
) -> FamilyProcedureResult:
    record = record_override or _knowledge_content(
        context, command.subject_key, command.target_id
    )
    if record is None:
        return FamilyProcedureResult(rejection="No authored Recall Knowledge subject matches that selection.")
    target = _knowledge_target(context, record, command.target_id)
    if target is None:
        return FamilyProcedureResult(rejection="Recall Knowledge requires an active authored subject target.")
    if command.question is not None and command.question != record.question:
        return FamilyProcedureResult(rejection="That Recall Knowledge question is not available for this subject.")
    if command.forensic_follow_up and command.circumstance_bonus != 2:
        return FamilyProcedureResult(rejection="Forensic Acumen follow-ups require their authored +2 circumstance bonus.")
    if not command.forensic_follow_up and command.circumstance_bonus != 0:
        return FamilyProcedureResult(rejection="Ordinary Recall Knowledge cannot carry a Forensic Acumen bonus.")
    allowed = dict(record.allowed_skills)
    skill = command.skill or next(iter(allowed), None)
    if skill not in allowed:
        return FamilyProcedureResult(rejection="That skill is not eligible for this Recall Knowledge question.")
    if record.subject_key in context.actor.investigator_knowledge_exhausted:
        return FamilyProcedureResult(rejection="This Recall Knowledge subject is exhausted.")
    attempts = context.actor.investigator_knowledge_attempts.get(record.subject_key, 0)
    dc = _knowledge_dc(record, attempts, skill)
    try:
        saved = context.prepare_skill_check(
            skill,
            dc,
            traits=frozenset({"secret", "skill"}),
            extra_modifiers=additional_modifiers,
        )
        saved = context.resolve_saved_check(saved)
    except (NotImplementedError, ValueError) as error:
        return FamilyProcedureResult(unsupported=str(error))
    if context.actor.health_mode is HealthMode.PC and context.actor.hero_points > 0:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=getattr(target, "actor_id", None),
            stage=(
                "forensic_examination_follow_up_hero_point"
                if command.forensic_follow_up
                else "known_weaknesses_knowledge_hero_point"
                if known_weaknesses
                else "recall_knowledge_hero_point"
            ),
        )
        procedure_id = (
            "investigator:forensic_examination:follow_up:hero_point"
            if command.forensic_follow_up
            else "investigator:known_weaknesses:hero_point"
            if known_weaknesses
            else "investigator:recall_knowledge:hero_point"
        )
        context.present_choice(
            procedure_id,
            context.actor.actor_id,
            f"{context.actor.label} may spend a Hero Point to reroll the Recall Knowledge check.",
            (
                ChoiceOption("reroll", "Spend a Hero Point to reroll"),
                ChoiceOption("keep", "Keep the current result"),
            ),
            continuation,
            target_id=getattr(target, "actor_id", None),
            saved_check=saved,
            family_command=command,
        )
        return FamilyProcedureResult(events=(Event(
            "choice_offered",
            context.actor.actor_id,
            getattr(target, "actor_id", None),
            "Choose whether to reroll the Recall Knowledge check.",
        ),))
    return _finalize_knowledge(context, record, target, command, saved, known_weaknesses=known_weaknesses)


def _examination_records(context: FamilyProcedureContext) -> tuple[Any, ...]:
    """Return the scene's finite authored outside-combat examinations."""
    setup_id = getattr(context.state, "setup_id", None)
    if not isinstance(setup_id, str):
        return ()
    from .content import get_setup

    return tuple(getattr(get_setup(setup_id), "examinations", ()))


def _examination_content(
    context: FamilyProcedureContext,
    examination_key: str,
) -> Any | None:
    if not isinstance(examination_key, str) or not examination_key:
        return None
    matches = tuple(
        item for item in _examination_records(context)
        if getattr(item, "key", None) == examination_key
        or getattr(item, "body_key", None) == examination_key
        or getattr(item, "examination_key", None) == examination_key
    )
    return matches[0] if len(matches) == 1 else None


def _examination_follow_up_record(
    context: FamilyProcedureContext,
    subject_key: str,
) -> Any | None:
    """Find one selected follow-up in the authored examination packet."""
    matches = tuple(
        item
        for examination in _examination_records(context)
        for item in getattr(examination, "follow_up_records", ())
        if item.subject_key == subject_key
    )
    return matches[0] if len(matches) == 1 else None


def _examination_body(
    context: FamilyProcedureContext,
    record: Any,
) -> AuthoredKnowledgeSubject | None:
    if not getattr(record, "accessible", False):
        return None
    body_actor_id = getattr(record, "body_actor_id", None)
    if body_actor_id is None:
        return AuthoredKnowledgeSubject(
            subject_key=record.body_key,
            label=record.body_label,
        )
    body_actor = context.state.creatures.get(body_actor_id)
    if (
        body_actor is None
        or body_actor.actor_id == context.actor.actor_id
        or not body_actor.defeated
    ):
        return None
    return AuthoredKnowledgeSubject(
        subject_key=record.body_key,
        label=record.body_label,
        actor_id=body_actor.actor_id,
        definition_id=body_actor.definition_id,
        defeated=body_actor.defeated,
        unconscious=body_actor.unconscious,
    )


def _examination_answer(record: Any, degree: DegreeOfSuccess) -> str | None:
    if degree is DegreeOfSuccess.CRITICAL_SUCCESS:
        return getattr(record, "critical_success_answer", None) or record.success_answer
    if degree is DegreeOfSuccess.SUCCESS:
        return record.success_answer
    if degree is DegreeOfSuccess.FAILURE:
        return getattr(record, "failure_answer", None)
    return getattr(record, "critical_failure_answer", None)


def _examination_duration(record: Any) -> int:
    """Apply Forensic Acumen's half-time rule with its five-minute floor."""
    ordinary = getattr(record, "ordinary_duration_seconds", None)
    if type(ordinary) is not int or ordinary < 600:
        raise ValueError("Forensic examination duration must be at least ten minutes")
    return max(300, ordinary // 2)


def _examination_event(
    actor,
    body: AuthoredKnowledgeSubject,
    record: Any,
    check: CheckResult,
    answer: str | None,
    elapsed_seconds: int,
    world_time_seconds: int,
) -> Event:
    result_text = answer or "No reliable information is available."
    return Event(
        "forensic_examination",
        actor.actor_id,
        body.actor_id,
        f"{actor.label} examines {body.label}: {check.degree.label()} "
        f"({check.total} vs DC {check.dc}). {result_text}",
        check=check,
        details=(
            f"Question: {record.medicine_question}",
            f"Body: {body.label}",
            f"Forensic Acumen elapsed time: {elapsed_seconds} seconds",
            f"world time advanced to {world_time_seconds} seconds",
        ),
    )


def _finalize_examination(
    context: FamilyProcedureContext,
    record: Any,
    body: AuthoredKnowledgeSubject,
    command: ForensicExamination,
    saved,
    *,
    elapsed_already_charged: bool = False,
) -> FamilyProcedureResult:
    if saved.result is None:
        return FamilyProcedureResult(rejection="The saved Forensic examination check has not been resolved.")
    check = saved.result
    actor = context.actor
    subject_key = record.body_key
    attempts = actor.investigator_knowledge_attempts.get(subject_key, 0)
    actor.investigator_knowledge_attempts[subject_key] = attempts + 1
    actor.investigator_examinations_completed.add(record.key)
    if check.degree in {DegreeOfSuccess.FAILURE, DegreeOfSuccess.CRITICAL_FAILURE}:
        actor.investigator_knowledge_exhausted.add(subject_key)
    answer = _examination_answer(record, check.degree)
    elapsed_seconds = _examination_duration(record)
    if not elapsed_already_charged:
        context.encounter._advance_elapsed_time(context.state, elapsed_seconds)
    event = _examination_event(
        actor,
        body,
        record,
        check,
        answer,
        elapsed_seconds,
        context.state.world_time_seconds,
    )
    events: list[Event] = [event]
    if answer is None or check.degree in {DegreeOfSuccess.FAILURE, DegreeOfSuccess.CRITICAL_FAILURE}:
        events.append(Event(
            "forensic_examination_no_information",
            actor.actor_id,
            body.actor_id,
            f"{actor.label} finds no reliable information in {body.label}.",
        ))
    followups = tuple(
        item for item in getattr(record, "follow_up_records", ())
        if item.subject_key not in actor.investigator_knowledge_exhausted
    )
    if check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS} and followups:
        options = (
            ChoiceOption("decline", "Decline immediate Recall Knowledge"),
            *(ChoiceOption(f"follow_up:{item.subject_key}", item.question) for item in followups),
        )
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=actor.actor_id,
            target_id=body.actor_id,
            stage="forensic_examination_follow_up",
        )
        context.present_choice(
            "investigator:forensic_examination:follow_up",
            actor.actor_id,
            f"{actor.label} may ask one immediate relevant Recall Knowledge question.",
            options,
            continuation,
            details=(
                f"The examination took {elapsed_seconds} seconds.",
                "The selected follow-up receives a +2 circumstance bonus from Forensic Acumen.",
            ),
            target_id=body.actor_id,
            family_command=command,
        )
        events.append(Event(
            "forensic_examination_follow_up_offered",
            actor.actor_id,
            body.actor_id,
            "Choose an immediate relevant Recall Knowledge question or decline.",
        ))
    return FamilyProcedureResult(events=tuple(events))


def _resolve_forensic_examination(
    context: FamilyProcedureContext,
    command: ForensicExamination,
) -> FamilyProcedureResult:
    record = _examination_content(context, command.examination_key)
    if record is None:
        return FamilyProcedureResult(rejection="No authored Forensic examination matches that selection.")
    if context.state.in_progress:
        return FamilyProcedureResult(rejection="Forensic examination is only available outside combat.")
    if context.state.pending_choice is not None:
        return FamilyProcedureResult(rejection="A pending choice must be resolved before examination.")
    if (
        context.actor.health_mode is not HealthMode.PC
        or context.actor.unconscious
        or context.actor.dead
    ):
        return FamilyProcedureResult(rejection="Forensic examination requires a conscious living PC.")
    if FORENSIC_ACUMEN_ABILITY not in context.definition.abilities:
        return FamilyProcedureResult(unsupported="Forensic examination requires Forensic Acumen.")
    if record.key in context.actor.investigator_examinations_completed:
        return FamilyProcedureResult(rejection="This authored body has already been examined.")
    body = _examination_body(context, record)
    if body is None:
        return FamilyProcedureResult(rejection="The authored body is not accessible in this scene.")
    subject_key = record.body_key
    if subject_key in context.actor.investigator_knowledge_exhausted:
        return FamilyProcedureResult(rejection="This examination subject is exhausted.")
    try:
        saved = context.prepare_skill_check(
            "medicine",
            record.medicine_dc,
            traits=frozenset({"secret", "skill"}),
        )
        saved = context.resolve_saved_check(saved)
        elapsed_seconds = _examination_duration(record)
    except (NotImplementedError, ValueError) as error:
        return FamilyProcedureResult(unsupported=str(error))
    if context.actor.hero_points > 0:
        # Charge the authored elapsed time before persisting the Hero choice;
        # a later reroll therefore cannot charge another five/ten minutes.
        context.encounter._advance_elapsed_time(context.state, elapsed_seconds)
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=body.actor_id,
            stage="forensic_examination_medicine_hero_point",
        )
        context.present_choice(
            "investigator:forensic_examination:medicine_hero_point",
            context.actor.actor_id,
            f"{context.actor.label} may spend a Hero Point to reroll the Medicine examination check.",
            (
                ChoiceOption("reroll", "Spend a Hero Point to reroll"),
                ChoiceOption("keep", "Keep the current result"),
            ),
            continuation,
            details=(
                f"Body: {body.label}",
                f"Forensic Acumen elapsed time: {elapsed_seconds} seconds",
            ),
            target_id=body.actor_id,
            saved_check=saved,
            family_command=command,
        )
        return FamilyProcedureResult(events=(Event(
            "forensic_examination_started",
            context.actor.actor_id,
            body.actor_id,
            f"{context.actor.label} begins examining {body.label}; choose whether to reroll the Medicine check.",
            check=saved.result,
        ),))
    return _finalize_examination(context, record, body, command, saved)


def recall_knowledge_target_ids(encounter, state, actor, definition) -> tuple[str, ...]:
    """Project the legal authored Recall Knowledge targets for the action menu."""
    context = FamilyProcedureContext(
        encounter, state, encounter._dice.clone(), actor, definition, "martial"
    )
    targets: list[str] = []
    for record in _knowledge_records(context):
        subject_key = getattr(record, "subject_key", None)
        if not isinstance(subject_key, str) or subject_key in actor.investigator_knowledge_exhausted:
            continue
        record_actor = getattr(record, "subject_actor_id", None)
        record_definition = getattr(record, "subject_definition_id", None)
        for candidate in state.creatures.values():
            if (
                candidate.actor_id != actor.actor_id
                and not candidate.defeated
                and (record_actor is None or record_actor == candidate.actor_id)
                and (record_definition is None or record_definition == candidate.definition_id)
                and candidate.actor_id not in targets
            ):
                targets.append(candidate.actor_id)
    return tuple(targets)


def _handle_devise(
    context: FamilyProcedureContext,
    command: DeviseStratagem,
) -> FamilyProcedureResult:
    if DEVISE_ABILITY not in context.definition.abilities and "devise_stratagem" not in context.definition.abilities:
        return FamilyProcedureResult(
            unsupported="Devise a Stratagem is not admitted for this creature."
        )
    if command.mode not in {ATTACK_STRATAGEM, SKILL_STRATAGEM}:
        return FamilyProcedureResult(
            rejection="Devise a Stratagem mode must be 'attack' or 'skill'."
        )
    if command.mode == SKILL_STRATAGEM:
        return FamilyProcedureResult(
            unsupported="Skill Stratagem is outside the first Investigator play slice."
        )
    if command.free_action:
        return FamilyProcedureResult(
            unsupported="Free Devise a Stratagem requires an active investigation subject; lead support is not yet admitted."
        )
    if context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Devise a Stratagem requires one action.")
    target = _active_target(context, command.target_id)
    if target is None:
        return FamilyProcedureResult(
            rejection="Devise a Stratagem requires a visible active creature other than the investigator."
        )
    turn_start = context.state.actor_start_counts.get(context.actor.actor_id, 0)
    existing = getattr(context.actor, "investigator_stratagem", None)
    if isinstance(existing, InvestigatorStratagemState) and existing.round_number == context.state.round_number:
        return FamilyProcedureResult(
            rejection="Devise a Stratagem is limited to once per round."
        )
    context.require_action_permitted(
        "devise_stratagem", frozenset({"concentrate", "investigator"})
    )
    if command.known_weaknesses:
        # Known Weaknesses is an optional Recall Knowledge embedded in Devise.
        # Validate the authored record and the skill menu before paying Devise;
        # once paid, a Hero decision can pause before the stratagem d20.
        matching = tuple(
            item for item in _knowledge_records(context)
            if (
                getattr(item, "subject_actor_id", None) in {None, target.actor_id}
                and getattr(item, "subject_definition_id", None) in {None, target.definition_id}
            )
        )
        record = matching[0] if len(matching) == 1 else None
        if record is None:
            return FamilyProcedureResult(
                unsupported="Known Weaknesses requires an authored Recall Knowledge question for this target."
            )
        skill = next(iter(dict(record.allowed_skills)), None)
        if skill is None:
            return FamilyProcedureResult(rejection="Known Weaknesses has no eligible Recall Knowledge skill.")
        context.commit_family_action(actions=1)
        knowledge = _resolve_recall_knowledge(
            context,
            RecallKnowledge(record.subject_key, record.question, skill, target.actor_id),
            known_weaknesses=True,
        )
        if knowledge.rejection or knowledge.unsupported:
            return knowledge
        if context.state.pending_choice is not None:
            return knowledge
        events = list(knowledge.events)
        return _draw_devise_after_knowledge(context, command, target, events)
    die = context.dice.draw(20)
    context.commit_family_action(actions=1)
    state = InvestigatorStratagemState(
        target_id=target.actor_id,
        die=die,
        mode=command.mode,
        round_number=context.state.round_number,
        turn_start=turn_start,
    )
    context.actor.investigator_stratagem = state
    if command.mode == ATTACK_STRATAGEM:
        text = (
            f"{context.actor.label} devises an attack stratagem against {target.label}; "
            f"the stored preliminary d20 is {die}."
        )
    else:
        text = (
            f"{context.actor.label} devises a skill stratagem against {target.label}; "
            f"the stored preliminary d20 is {die}."
        )
    events = [Event("devise_stratagem", context.actor.actor_id, target.actor_id, text)]
    return FamilyProcedureResult(
        events=tuple(context.encounter._complete_action(
            context.state, context.actor, events, dice=context.dice
        ))
    )


def _draw_devise_after_knowledge(
    context: FamilyProcedureContext,
    command: DeviseStratagem,
    target,
    events: list[Event],
) -> FamilyProcedureResult:
    """Finalize Known Weaknesses then draw Devise's single stored d20."""
    die = context.dice.draw(20)
    turn_start = context.state.actor_start_counts.get(context.actor.actor_id, 0)
    context.actor.investigator_stratagem = InvestigatorStratagemState(
        target_id=target.actor_id,
        die=die,
        mode=command.mode,
        round_number=context.state.round_number,
        turn_start=turn_start,
    )
    events.append(Event(
        "devise_stratagem",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} devises an attack stratagem against {target.label} after Known Weaknesses; "
        f"the stored preliminary d20 is {die}.",
    ))
    return FamilyProcedureResult(events=tuple(context.encounter._complete_action(
        context.state, context.actor, events, dice=context.dice
    )))


def _has_healer_toolkit(context: FamilyProcedureContext) -> bool:
    """Return whether the actor can legally use a healer's toolkit now."""

    state = context.state
    actor = context.actor
    for item_id in actor.worn_items:
        instance = state.item_instances.get(item_id)
        if item_id == _HEALER_TOOLKIT_DEFINITION or (
            instance is not None and instance.definition_id == _HEALER_TOOLKIT_DEFINITION
        ):
            return True
    for item_id in actor.held_items:
        instance = state.item_instances.get(item_id)
        # The held toolkit occupies one hand; the action needs one additional
        # free hand to use it as a two-handed held item.
        if (
            item_id == _HEALER_TOOLKIT_DEFINITION
            or (instance is not None and instance.definition_id == _HEALER_TOOLKIT_DEFINITION)
        ) and context.free_hands >= 1:
            return True
    return False


def _battle_medicine_target(context: FamilyProcedureContext, target_id: str):
    if not isinstance(target_id, str) or not target_id:
        return None, "Battle Medicine requires a target."
    target = context.state.creatures.get(target_id)
    if target is None or target.dead or not context.encounter._is_living_target(target):
        return None, "Battle Medicine requires a living target."
    if target.team != context.actor.team:
        return None, "Battle Medicine can target only an ally."
    if grid_distance_feet(context.actor.position, target.position) > 5:
        return None, "Battle Medicine requires a target within 5 feet."
    from .content import get_definition

    target_definition = get_definition(target.definition_id)
    if target.health_mode is not HealthMode.PC and target.hp >= target_definition.hp:
        return None, "Battle Medicine requires an injured target."
    if target.health_mode is HealthMode.PC and target.hp >= target_definition.hp and not target.dying:
        return None, "Battle Medicine requires an injured target."
    if context.condition_immunity_active(
        "battle_medicine", context.actor.actor_id, target.actor_id
    ):
        return None, "This target is temporarily immune to this medic's Battle Medicine."
    return target, None


def battle_medicine_target_ids(encounter, state, actor, definition) -> tuple[str, ...]:
    """Project the target IDs currently legal for the public action menu."""

    if (
        "Battle Medicine" not in definition.feats
        and FORENSIC_MEDICINE_ABILITY not in definition.abilities
    ):
        return ()
    context = FamilyProcedureContext(encounter, state, encounter._dice.clone(), actor, definition, "martial")
    if not _has_healer_toolkit(context):
        return ()
    return tuple(
        target.actor_id
        for target in state.creatures.values()
        if _battle_medicine_target(context, target.actor_id)[0] is not None
    )


def _check_event(actor, target, check: CheckResult) -> Event:
    return Event(
        "battle_medicine_check",
        actor.actor_id,
        target.actor_id,
        f"{actor.label} attempts Battle Medicine on {target.label}: "
        f"{check.degree.label()} ({check.total} vs DC {check.dc}).",
        check=check,
    )


def _finish_battle_medicine(
    context: FamilyProcedureContext,
    command: BattleMedicine,
    saved_check,
) -> FamilyProcedureResult:
    if saved_check.result is None:
        return FamilyProcedureResult(rejection="The saved Battle Medicine check has not been resolved.")
    target, error = _battle_medicine_target(context, command.target_id)
    if error:
        return FamilyProcedureResult(rejection=error)
    check = saved_check.result
    events = [_check_event(context.actor, target, check)]
    # The methodology changes the normal Battle Medicine cooldown and adds
    # the Investigator's level on a success. The immunity applies to every
    # attempted check, including a failure or critical failure.
    context.grant_condition_immunity(
        "battle_medicine",
        context.actor.actor_id,
        target.actor_id,
        duration_seconds=_FORENSIC_IMMUNITY_SECONDS,
    )
    if check.degree is DegreeOfSuccess.CRITICAL_FAILURE:
        damage = roll_damage_terms(
            (DamageTerm(
                source="battle_medicine_critical_failure",
                damage_type="untyped",
                dice=(8,),
                critical_mode="unchanged",
            ),),
            context.dice.draw,
        )
        if target.actor_id == context.actor.actor_id:
            # The shared family damage API intentionally rejects self-targets;
            # retain its PC health transition for this legal self-target case.
            from .health import damage as pc_damage

            transition = pc_damage(context.encounter._health_state(target), damage.total)
            context.encounter._apply_health_transition(context.state, target, transition)
            events.append(Event(
                "battle_medicine_critical_failure",
                context.actor.actor_id,
                target.actor_id,
                f"Battle Medicine critically fails; {target.label} takes {damage.total} damage "
                f"(1d8 {damage.components[0].rolls[0]}).",
                check=check,
                damage=damage,
            ))
        else:
            events.extend(context.apply_family_damage(
                target.actor_id,
                damage,
                source="Battle Medicine critical failure",
                damage_type="untyped",
                check=check,
            ))
        events.append(Event(
            "immunity_applied",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} is immune to this medic's Battle Medicine for 1 hour.",
        ))
    elif check.degree in {DegreeOfSuccess.SUCCESS, DegreeOfSuccess.CRITICAL_SUCCESS}:
        dice_count = 4 if check.degree is DegreeOfSuccess.CRITICAL_SUCCESS else 2
        healing = roll_damage_terms(
            (DamageTerm(
                source="battle_medicine",
                damage_type="vitality",
                dice=(8,) * dice_count,
                critical_mode="unchanged",
            ),),
            context.dice.draw,
        )
        forensic_bonus = context.definition.level if check.degree is DegreeOfSuccess.SUCCESS else 0
        amount = healing.total + forensic_bonus
        if target.health_mode is HealthMode.PC:
            # Battle Medicine restores HP without changing Wounded. The
            # shared PC healing transition handles dying/unconscious recovery;
            # restore the pre-action Wounded value after proposing it.
            transition = pc_healing(context.encounter._health_state(target), amount)
            transition = replace(
                transition,
                state=replace(transition.state, wounded=target.wounded),
            )
            context.encounter._apply_health_transition(context.state, target, transition)
        else:
            target.hp = min(get_definition(target.definition_id).hp, target.hp + amount)
            if target.hp > 0:
                target.unconscious = False
        bonus_text = f" + {forensic_bonus} Forensic Medicine" if forensic_bonus else ""
        events.append(Event(
            "battle_medicine",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} heals {amount} HP from Battle Medicine "
            f"({dice_count}d8 {', '.join(map(str, healing.components[0].rolls))}{bonus_text}); "
            f"now at {target.hp} HP with wounded {target.wounded}.",
            check=check,
        ))
        events.append(Event(
            "immunity_applied",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} is immune to this medic's Battle Medicine for 1 hour.",
        ))
    else:
        events.append(Event(
            "battle_medicine_failed",
            context.actor.actor_id,
            target.actor_id,
            f"Battle Medicine fails; {target.label} regains no HP.",
            check=check,
        ))
        events.append(Event(
            "immunity_applied",
            context.actor.actor_id,
            target.actor_id,
            f"{target.label} is immune to this medic's Battle Medicine for 1 hour.",
        ))
    if context.state.pending_choice is None:
        events = context.encounter._complete_action(
            context.state, context.actor, events, dice=context.dice
        )
    return FamilyProcedureResult(events=tuple(events))


def resolve_battle_medicine_continuation(encounter, state, dice, continuation):
    actor = state.creatures.get(continuation.actor_id or "")
    target = state.creatures.get(continuation.target_id or "")
    if actor is None or target is None or continuation.stage != "battle_medicine_check":
        raise ValueError("The saved Battle Medicine continuation is incomplete.")
    from .content import get_definition

    context = FamilyProcedureContext(
        encounter, state, dice, actor, get_definition(actor.definition_id), "martial"
    )
    result = _resolve_battle_medicine_check(context, BattleMedicine(target.actor_id))
    if result.rejection:
        raise ValueError(result.rejection)
    if result.unsupported:
        raise NotImplementedError(result.unsupported)
    return list(result.events)


def _resolve_battle_medicine_check(
    context: FamilyProcedureContext, command: BattleMedicine
) -> FamilyProcedureResult:
    try:
        saved = context.prepare_skill_check(
            "medicine", command.dc, traits=_BATTLE_MEDICINE_TRAITS
        )
        saved = context.resolve_saved_check(saved)
    except (NotImplementedError, ValueError) as error:
        return FamilyProcedureResult(unsupported=str(error))
    if context.actor.health_mode is HealthMode.PC and context.actor.hero_points > 0:
        continuation = ActionContinuation(
            kind="family_action",
            actor_id=context.actor.actor_id,
            target_id=command.target_id,
            stage="battle_medicine_hero_point",
        )
        context.present_choice(
            "investigator:battle_medicine:hero_point",
            context.actor.actor_id,
            f"{context.actor.label} may spend a Hero Point to reroll the Battle Medicine check.",
            (
                ChoiceOption("reroll", "Spend a Hero Point to reroll"),
                ChoiceOption("keep", "Keep the current result"),
            ),
            continuation,
            target_id=command.target_id,
            saved_check=saved,
            family_command=command,
        )
        return FamilyProcedureResult(events=(Event(
            "choice_offered",
            context.actor.actor_id,
            command.target_id,
            "Choose whether to spend a Hero Point to reroll the Battle Medicine check.",
        ),))
    return _finish_battle_medicine(context, command, saved)


def _handle_battle_medicine(
    context: FamilyProcedureContext, command: BattleMedicine
) -> FamilyProcedureResult:
    if (
        BATTLE_MEDICINE_ABILITY not in context.definition.abilities
        and _BATTLE_MEDICINE_FEAT not in context.definition.feats
        and FORENSIC_MEDICINE_ABILITY not in context.definition.abilities
    ):
        return FamilyProcedureResult(unsupported="Battle Medicine is not admitted for this creature.")
    if command.dc != _BATTLE_MEDICINE_DC:
        return FamilyProcedureResult(
            unsupported="Only the level-1 trained Battle Medicine DC 15 is admitted in this slice."
        )
    if context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Battle Medicine requires one action.")
    target, error = _battle_medicine_target(context, command.target_id)
    if error:
        return FamilyProcedureResult(rejection=error)
    if not _has_healer_toolkit(context):
        return FamilyProcedureResult(
            rejection="Battle Medicine requires holding or wearing a healer's toolkit."
        )
    context.require_action_permitted("battle_medicine", _BATTLE_MEDICINE_TRAITS)
    context.commit_family_action(actions=1)
    continuation = ActionContinuation(
        kind="family_action",
        actor_id=context.actor.actor_id,
        target_id=target.actor_id,
        movement_kind="manipulate",
        reaction_trigger="manipulate",
        must_disrupt_on_critical=True,
        stage="battle_medicine_check",
    )
    events = [Event(
        "battle_medicine_started",
        context.actor.actor_id,
        target.actor_id,
        f"{context.actor.label} commits Battle Medicine on {target.label}.",
    )]
    events.extend(context.encounter._advance_continuation(
        context.state, context.dice, continuation
    ))
    return FamilyProcedureResult(events=tuple(events))


def _handle_recall_knowledge(
    context: FamilyProcedureContext, command: RecallKnowledge
) -> FamilyProcedureResult:
    if context.actor.actions_remaining < 1:
        return FamilyProcedureResult(rejection="Recall Knowledge requires one action.")
    # Resolve the authored record before committing the one action. This keeps
    # malformed subject/question/skill requests atomic and avoids paying for a
    # missing GM context.
    record = _knowledge_content(context, command.subject_key, command.target_id)
    if record is None:
        return FamilyProcedureResult(rejection="No authored Recall Knowledge subject matches that selection.")
    target = _knowledge_target(context, record, command.target_id)
    if target is None:
        return FamilyProcedureResult(rejection="Recall Knowledge requires an active authored subject target.")
    skill = command.skill or next(iter(dict(record.allowed_skills)), None)
    if command.question is not None and command.question != record.question:
        return FamilyProcedureResult(rejection="That Recall Knowledge question is not available for this subject.")
    if skill not in dict(record.allowed_skills):
        return FamilyProcedureResult(rejection="That skill is not eligible for this Recall Knowledge question.")
    if record.subject_key in context.actor.investigator_knowledge_exhausted:
        return FamilyProcedureResult(rejection="This Recall Knowledge subject is exhausted.")
    context.require_action_permitted("recall_knowledge", frozenset({"concentrate", "secret", "skill"}))
    context.commit_family_action(actions=1)
    return _resolve_recall_knowledge(
        context,
        RecallKnowledge(record.subject_key, record.question, skill, target.actor_id),
    )


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    if isinstance(context.command, DeviseStratagem):
        return _handle_devise(context, context.command)
    if isinstance(context.command, ForensicExamination):
        return _resolve_forensic_examination(context, context.command)
    if isinstance(context.command, RecallKnowledge):
        return _handle_recall_knowledge(context, context.command)
    if isinstance(context.command, BattleMedicine):
        return _handle_battle_medicine(context, context.command)
    return None


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult | None:
    pending, choice = context.pending, context.choice
    if pending is None or choice is None:
        return None
    if pending.procedure_id == "investigator:forensic_examination:follow_up":
        command = pending.family_command
        continuation = pending.continuation
        if not isinstance(command, ForensicExamination) or continuation is None:
            return FamilyProcedureResult(rejection="The saved Forensic examination follow-up choice is incomplete.")
        if continuation.stage != "forensic_examination_follow_up":
            return FamilyProcedureResult(rejection="The saved Forensic examination follow-up choice is stale.")
        record = _examination_content(context, command.examination_key)
        body = _examination_body(context, record) if record is not None else None
        if record is None or body is None:
            return FamilyProcedureResult(rejection="The authored examination body is no longer available.")
        followups = tuple(
            item for item in getattr(record, "follow_up_records", ())
            if item.subject_key not in context.actor.investigator_knowledge_exhausted
        )
        expected_options = (
            ChoiceOption("decline", "Decline immediate Recall Knowledge"),
            *(ChoiceOption(f"follow_up:{item.subject_key}", item.question) for item in followups),
        )
        if pending.options != expected_options:
            return FamilyProcedureResult(rejection="The saved Forensic examination follow-up choices are stale.")
        if choice.option_id == "decline":
            return FamilyProcedureResult(events=(Event(
                "forensic_examination_follow_up_declined",
                context.actor.actor_id,
                body.actor_id,
                f"{context.actor.label} declines immediate Recall Knowledge after examining {body.label}.",
            ),))
        selected_key = choice.option_id.removeprefix("follow_up:")
        followup = next((item for item in followups if item.subject_key == selected_key), None)
        if followup is None:
            return FamilyProcedureResult(rejection="That immediate Recall Knowledge follow-up is not available.")
        followup_command = RecallKnowledge(
            subject_key=followup.subject_key,
            question=followup.question,
            skill=next(iter(dict(followup.allowed_skills))),
            target_id=followup.subject_actor_id,
            circumstance_bonus=2,
            forensic_follow_up=True,
        )
        return _resolve_recall_knowledge(
            context,
            followup_command,
            record_override=followup,
            additional_modifiers=(Modifier(2, "circumstance", "Forensic Acumen"),),
        )
    if pending.procedure_id == "investigator:forensic_examination:medicine_hero_point":
        command = pending.family_command
        saved = pending.saved_check
        continuation = pending.continuation
        if not isinstance(command, ForensicExamination) or saved is None or continuation is None:
            return FamilyProcedureResult(rejection="The saved Forensic examination Hero Point choice is incomplete.")
        if choice.option_id == "reroll":
            try:
                saved = context.reroll_skill_check(saved)
            except (NotImplementedError, ValueError) as error:
                return FamilyProcedureResult(rejection=str(error))
        elif choice.option_id != "keep":
            return FamilyProcedureResult(rejection="Choose whether to reroll the Medicine examination check.")
        if continuation.stage != "forensic_examination_medicine_hero_point":
            return FamilyProcedureResult(rejection="The saved Forensic examination Hero Point choice is stale.")
        record = _examination_content(context, command.examination_key)
        body = _examination_body(context, record) if record is not None else None
        if record is None or body is None:
            return FamilyProcedureResult(rejection="The authored examination body is no longer available.")
        return _finalize_examination(
            context,
            record,
            body,
            command,
            saved,
            elapsed_already_charged=True,
        )
    if pending.procedure_id in {
        "investigator:recall_knowledge:hero_point",
        "investigator:known_weaknesses:hero_point",
        "investigator:forensic_examination:follow_up:hero_point",
    }:
        command = pending.family_command
        saved = pending.saved_check
        continuation = pending.continuation
        if not isinstance(command, RecallKnowledge) or saved is None or continuation is None:
            return FamilyProcedureResult(rejection="The saved Recall Knowledge Hero Point choice is incomplete.")
        if choice.option_id == "reroll":
            try:
                saved = context.reroll_skill_check(saved)
            except (NotImplementedError, ValueError) as error:
                return FamilyProcedureResult(rejection=str(error))
        elif choice.option_id != "keep":
            return FamilyProcedureResult(rejection="Choose whether to reroll the Recall Knowledge check.")
        expected_stage = (
            "forensic_examination_follow_up_hero_point"
            if pending.procedure_id == "investigator:forensic_examination:follow_up:hero_point"
            else "known_weaknesses_knowledge_hero_point"
            if pending.procedure_id == "investigator:known_weaknesses:hero_point"
            else "recall_knowledge_hero_point"
        )
        if continuation.stage != expected_stage:
            return FamilyProcedureResult(rejection="The saved Recall Knowledge Hero Point choice is stale.")
        record = (
            _examination_follow_up_record(context, command.subject_key)
            if command.forensic_follow_up
            else _knowledge_content(context, command.subject_key, command.target_id)
        )
        target = _knowledge_target(context, record, command.target_id) if record is not None else None
        if record is None or target is None:
            return FamilyProcedureResult(rejection="The authored Recall Knowledge subject is no longer available.")
        result = _finalize_knowledge(
            context, record, target, command, saved,
            known_weaknesses=pending.procedure_id == "investigator:known_weaknesses:hero_point",
        )
        if result.rejection or result.unsupported:
            return result
        events = list(result.events)
        if pending.procedure_id == "investigator:known_weaknesses:hero_point":
            # The one action was committed before the saved Hero decision.
            # Draw Devise's d20 only after information/history/benefits are
            # finalized, exactly once.
            devise = DeviseStratagem(
                target_id=target.actor_id,
                mode=ATTACK_STRATAGEM,
                known_weaknesses=True,
            )
            return _draw_devise_after_knowledge(context, devise, target, events)
        if command.forensic_follow_up:
            return FamilyProcedureResult(events=tuple(result.events))
        return FamilyProcedureResult(events=tuple(context.encounter._complete_action(
            context.state, context.actor, events, dice=context.dice
        )))
    if pending.procedure_id != "investigator:battle_medicine:hero_point":
        return None
    command = pending.family_command
    saved = pending.saved_check
    continuation = pending.continuation
    if not isinstance(command, BattleMedicine) or saved is None or continuation is None:
        return FamilyProcedureResult(rejection="The saved Battle Medicine Hero Point choice is incomplete.")
    if choice.option_id == "reroll":
        try:
            saved = context.reroll_skill_check(saved)
        except (NotImplementedError, ValueError) as error:
            return FamilyProcedureResult(rejection=str(error))
    elif choice.option_id != "keep":
        return FamilyProcedureResult(rejection="Choose whether to reroll the Battle Medicine check.")
    if continuation.stage != "battle_medicine_hero_point":
        return FamilyProcedureResult(rejection="The saved Battle Medicine Hero Point choice is stale.")
    return _finish_battle_medicine(context, command, saved)


def validate_pending(context: FamilyProcedureContext) -> None:
    pending = context.pending
    if pending is not None and pending.procedure_id == "investigator:forensic_examination:medicine_hero_point":
        command = pending.family_command
        continuation = pending.continuation
        record = (
            _examination_content(context, command.examination_key)
            if isinstance(command, ForensicExamination)
            else None
        )
        body = _examination_body(context, record) if record is not None else None
        if (
            context.state.in_progress
            or pending.family_id != "martial"
            or pending.owner_actor_id != context.actor.actor_id
            or pending.actor_id != context.actor.actor_id
            or continuation is None
            or continuation.kind != "family_action"
            or continuation.stage != "forensic_examination_medicine_hero_point"
            or not isinstance(command, ForensicExamination)
            or record is None
            or body is None
            or record.key in context.actor.investigator_examinations_completed
            or pending.saved_check is None
            or pending.saved_check.result is None
            or pending.saved_check.check_owner_actor_id != context.actor.actor_id
            or pending.saved_check.context.statistic != "medicine"
            or pending.saved_check.dc != record.medicine_dc
            or context.actor.health_mode is not HealthMode.PC
            or context.actor.hero_points < 1
            or pending.options != (
                ChoiceOption("reroll", "Spend a Hero Point to reroll"),
                ChoiceOption("keep", "Keep the current result"),
            )
        ):
            raise ValueError("save has an invalid Forensic examination Hero Point choice")
        return
    if pending is not None and pending.procedure_id == "investigator:forensic_examination:follow_up":
        command = pending.family_command
        continuation = pending.continuation
        record = (
            _examination_content(context, command.examination_key)
            if isinstance(command, ForensicExamination)
            else None
        )
        body = _examination_body(context, record) if record is not None else None
        followups = tuple(
            item for item in getattr(record, "follow_up_records", ())
            if item.subject_key not in context.actor.investigator_knowledge_exhausted
        ) if record is not None else ()
        expected_options = (
            ChoiceOption("decline", "Decline immediate Recall Knowledge"),
            *(ChoiceOption(f"follow_up:{item.subject_key}", item.question) for item in followups),
        )
        if (
            context.state.in_progress
            or pending.family_id != "martial"
            or pending.owner_actor_id != context.actor.actor_id
            or pending.actor_id != context.actor.actor_id
            or continuation is None
            or continuation.kind != "family_action"
            or continuation.stage != "forensic_examination_follow_up"
            or not isinstance(command, ForensicExamination)
            or record is None
            or body is None
            or pending.options != expected_options
        ):
            raise ValueError("save has an invalid Forensic examination follow-up choice")
        return
    if pending is not None and pending.procedure_id in {
        "investigator:recall_knowledge:hero_point",
        "investigator:known_weaknesses:hero_point",
        "investigator:forensic_examination:follow_up:hero_point",
    }:
        command = pending.family_command
        continuation = pending.continuation
        if (
            pending.family_id != "martial"
            or pending.owner_actor_id != context.actor.actor_id
            or pending.actor_id != context.actor.actor_id
            or continuation is None
            or continuation.kind != "family_action"
            or not isinstance(command, RecallKnowledge)
            or pending.saved_check is None
            or pending.saved_check.result is None
            or pending.saved_check.check_owner_actor_id != context.actor.actor_id
            or context.actor.health_mode is not HealthMode.PC
            or context.actor.hero_points < 1
            or pending.options != (
                ChoiceOption("reroll", "Spend a Hero Point to reroll"),
                ChoiceOption("keep", "Keep the current result"),
            )
        ):
            raise ValueError("save has an invalid Recall Knowledge Hero Point choice")
        expected_stage = (
            "forensic_examination_follow_up_hero_point"
            if pending.procedure_id == "investigator:forensic_examination:follow_up:hero_point"
            else "known_weaknesses_knowledge_hero_point"
            if pending.procedure_id == "investigator:known_weaknesses:hero_point"
            else "recall_knowledge_hero_point"
        )
        if continuation.stage != expected_stage:
            raise ValueError("save has an invalid Recall Knowledge Hero Point stage")
        record = (
            _examination_follow_up_record(context, command.subject_key)
            if command.forensic_follow_up
            else _knowledge_content(context, command.subject_key, command.target_id)
        )
        target = _knowledge_target(context, record, command.target_id) if record is not None else None
        if record is None or target is None:
            raise ValueError("save has an unavailable Recall Knowledge subject")
        skill = command.skill or next(iter(dict(record.allowed_skills)), None)
        if skill not in dict(record.allowed_skills):
            raise ValueError("save has an ineligible Recall Knowledge skill")
        if pending.saved_check.context.statistic != skill:
            raise ValueError("save has a Recall Knowledge check for a different skill")
        if command.forensic_follow_up:
            if command.circumstance_bonus != 2 or not any(
                item == Modifier(2, "circumstance", "Forensic Acumen")
                for item in pending.saved_check.modifiers
            ):
                raise ValueError("save has a Recall Knowledge follow-up without Forensic Acumen's +2")
        elif command.circumstance_bonus != 0 or command.forensic_follow_up:
            raise ValueError("save has an invalid ordinary Recall Knowledge bonus")
        if pending.saved_check.dc != _knowledge_dc(
            record,
            context.actor.investigator_knowledge_attempts.get(record.subject_key, 0),
            skill,
        ):
            raise ValueError("save has a Recall Knowledge check for an outdated DC")
        return
    if (
        pending is None
        or pending.procedure_id != "investigator:battle_medicine:hero_point"
        or pending.family_id != "martial"
        or pending.owner_actor_id != context.actor.actor_id
        or pending.actor_id != context.actor.actor_id
        or pending.continuation is None
        or pending.continuation.stage != "battle_medicine_hero_point"
        or not isinstance(pending.family_command, BattleMedicine)
        or pending.saved_check is None
        or pending.saved_check.result is None
        or pending.saved_check.check_owner_actor_id != context.actor.actor_id
        or context.actor.health_mode is not HealthMode.PC
        or context.actor.hero_points < 1
        or pending.options != (
            ChoiceOption("reroll", "Spend a Hero Point to reroll"),
            ChoiceOption("keep", "Keep the current result"),
        )
    ):
        raise ValueError("save has an invalid Battle Medicine Hero Point choice")
    target, error = _battle_medicine_target(context, pending.family_command.target_id)
    if error:
        raise ValueError(f"save has an unavailable Battle Medicine target: {error}")
    return None
