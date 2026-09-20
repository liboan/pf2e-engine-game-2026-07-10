"""Fixed dispatcher for explicit martial class procedures.

Class feature modules own their commands and rule procedures. This module only
routes those explicit command records and saved family choices; it is not a
feature registry or an effect interpreter.

Each admitted module exposes ``handle_action(context)``,
``handle_choice(context)``, and ``validate_pending(context)``. The context is
the current Encounter transaction draft, never a second call to public
``Encounter.execute``. Pauses use ``context.present_choice`` and the existing
typed ``ActionContinuation`` record.
"""

from __future__ import annotations

from .model import FamilyProcedureContext, FamilyProcedureResult


def _owner_module(context: FamilyProcedureContext):
    """Resolve the owning code module through a short, fixed family list."""
    if context.command is not None:
        module_name = type(context.command).__module__.rsplit(".", 1)[-1]
    elif context.pending is not None and context.pending.procedure_id is not None:
        module_name = context.pending.procedure_id.split(":", 1)[0]
    else:
        return None

    if module_name == "barbarian":
        try:
            from . import barbarian
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.barbarian":
                raise
            return None
        return barbarian
    if module_name == "fighter":
        try:
            from . import fighter
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.fighter":
                raise
            return None
        return fighter
    if module_name == "ranger":
        try:
            from . import ranger
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.ranger":
                raise
            return None
        return ranger
    if module_name == "monk":
        try:
            from . import monk
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.monk":
                raise
            return None
        return monk
    if module_name == "martial_defense":
        try:
            from . import martial_defense
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.martial_defense":
                raise
            return None
        return martial_defense
    if module_name == "skill_actions":
        try:
            from . import skill_actions
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.skill_actions":
                raise
            return None
        return skill_actions
    if module_name == "justice":
        try:
            from . import justice
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.justice":
                raise
            return None
        return justice
    if module_name == "investigator":
        try:
            from . import investigator
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.investigator":
                raise
            return None
        return investigator
    if module_name == "swashbuckler":
        try:
            from . import swashbuckler
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.swashbuckler":
                raise
            return None
        return swashbuckler
    if module_name == "model" and type(context.command).__name__ in {
        "LayOnHands", "SuppressAura", "ResumeAura", "ToggleAura",
    }:
        try:
            from . import justice
        except ModuleNotFoundError as error:
            if error.name != f"{__package__}.justice":
                raise
            return None
        return justice
    return None


def handle_action(context: FamilyProcedureContext) -> FamilyProcedureResult:
    if context.command is None or context.command.family_id != "martial":
        return FamilyProcedureResult(unsupported="The martial procedure has no explicit command.")
    owner = _owner_module(context)
    handler = getattr(owner, "handle_action", None) if owner is not None else None
    if not callable(handler):
        return FamilyProcedureResult(
            unsupported=f"No admitted martial procedure handles {type(context.command).__name__}."
        )
    result = handler(context)
    if result is None:
        return FamilyProcedureResult(
            unsupported=f"No admitted martial procedure handles {type(context.command).__name__}."
        )
    return result


def handle_choice(context: FamilyProcedureContext) -> FamilyProcedureResult:
    if context.pending is None or context.pending.family_id != "martial":
        return FamilyProcedureResult(unsupported="The saved choice is not a martial procedure.")
    owner = _owner_module(context)
    handler = getattr(owner, "handle_choice", None) if owner is not None else None
    if not callable(handler):
        return FamilyProcedureResult(unsupported="The owning martial procedure cannot resume this choice.")
    result = handler(context)
    if result is None:
        return FamilyProcedureResult(unsupported="The owning martial procedure rejected this saved choice.")
    return result


def validate_pending(context: FamilyProcedureContext) -> None:
    if context.pending is None or context.pending.family_id != "martial":
        raise ValueError("save has a pending choice outside the martial family")
    owner = _owner_module(context)
    validator = getattr(owner, "validate_pending", None) if owner is not None else None
    if not callable(validator):
        raise ValueError("save has a pending choice for an unsupported martial procedure")
    validator(context)
