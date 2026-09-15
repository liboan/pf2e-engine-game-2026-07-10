"""Small, scrolling terminal presentation helpers for the local PF2e engine.

Rules decisions belong to :mod:`pf2e.encounter`; this module only formats
state and turns text into simple menu or coordinate inputs.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pf2e.encounter import Encounter


MAIN_MENU = (
    "Inspect",
    "Stride",
    "Step",
    "Strike",
    "End Turn",
    "Save",
    "Load",
    "Restart",
    "Quit",
)
_S1_MENU_ACTIONS = (
    "inspect",
    "stride",
    "step",
    "strike",
    "end_turn",
    "save",
    "load",
    "restart",
    "quit",
)
_ACTION_LABELS = {
    "stride": "Stride",
    "step": "Step",
    "strike": "Strike",
    "vicious_swing": "Vicious Swing",
    "interact": "Interact",
    "release": "Release",
    "stand": "Stand",
    "crawl": "Crawl",
    "take_cover": "Take Cover",
    "cast": "Cast",
    "end_turn": "End Turn",
}

PROTOTYPE_NOTICE = (
    "S1 prototype: synthetic NPC-style test actors on an open grid. "
    "This is not published-creature or PC support. Reactions, spellcasting, "
    "conditions, terrain, and PC dying/recovery are outside this prototype. "
    "At 0 HP, a test actor is defeated; the fight ends when one team has no "
    "active actor."
)
S2_SCOPE_NOTICE = (
    "S2 roster fixture: level-1 Fighter M sheets and Guard Dog source statistics are admitted. "
    "Normal S2 play remains gated until the required actions, reactions, and health choices "
    "are implemented. This is not full Fighter, creature, or PF2e support."
)
S2_ADMITTED_SCOPE_NOTICE = (
    "S2 fixed encounter catalog uses level-1 Fighter M and Fleet shortsword Fighter builds "
    "against Guard Dogs, including the elite adjustment. The selected actions and health "
    "procedures admitted for this scope include reactions, positioning, equipment, and Hero Points. "
    "All sides remain manually controlled; broader Fighter and creature options are outside scope. "
    "A team loses when it has no conscious, living combat-capable actor; downed actors remain "
    "rescuable while an ally keeps the team active."
)
S3_SCOPE_NOTICE = (
    "S3 catalogued encounters use selected level-1 melee, shortbow Fighter, rapier Fighter, "
    "and Iomedaean Warpriest builds with Guard Dogs and elite Guard Dogs. S3 play "
    "remains gated until its ranged, spell, effect, and continuation rules are verified. "
    "This is not full class, creature, or PF2e support."
)
S3_ADMITTED_SCOPE_NOTICE = (
    "S3 fixed encounter catalog uses level-1 melee, shortbow, and rapier Fighters plus an "
    "Iomedaean Warpriest against Guard Dogs. The selected actions and rank-1 spells include "
    "ranged, reaction, casting, healing, resource, and effect interactions. All sides remain "
    "manually controlled. Other class, creature, and PF2e actions remain outside this scope. "
    "A team loses when it has no conscious, living combat-capable actor; downed actors remain "
    "rescuable while an ally keeps the team active."
)

_COORDINATE = re.compile(r"^([A-Za-z])([1-9][0-9]*)$")


def parse_menu_choice(text: str, choice_count: int = len(MAIN_MENU)) -> int:
    """Return a one-based menu choice or raise ``ValueError`` for bad input."""
    raw = text.strip()
    try:
        choice = int(raw)
    except ValueError as exc:
        raise ValueError(f"Enter a number from 1 to {choice_count}.") from exc
    if not 1 <= choice <= choice_count:
        raise ValueError(f"Enter a number from 1 to {choice_count}.")
    return choice


def parse_coordinate(text: str, width: int = 7, height: int = 5) -> tuple[int, int]:
    """Parse a board coordinate such as ``C2`` into zero-based ``(x, y)``.

    This validates only coordinate spelling and board bounds. The encounter
    engine decides whether a requested route or destination is legal.
    """
    match = _COORDINATE.fullmatch(text.strip())
    if match is None:
        raise ValueError("Use a coordinate such as C2.")
    column = ord(match.group(1).upper()) - ord("A")
    row = int(match.group(2)) - 1
    if column >= width or row >= height:
        last_column = chr(ord("A") + width - 1)
        raise ValueError(f"Choose a square from A1 to {last_column}{height}.")
    return column, row


def format_coordinate(position: tuple[int, int]) -> str:
    """Format zero-based ``(x, y)`` as a board coordinate."""
    x, y = position
    if x < 0 or x >= 26 or y < 0:
        raise ValueError("Position is outside the supported coordinate range.")
    return f"{chr(ord('A') + x)}{y + 1}"


def parse_path(text: str, width: int = 7, height: int = 5) -> list[tuple[int, int]]:
    """Parse a sequence of explicit squares separated by spaces or commas.

    No routes are inferred or enumerated; the supplied path is passed to the
    engine, which checks movement costs and legality.
    """
    parts = [part for part in re.split(r"[\s,]+", text.strip()) if part]
    if not parts:
        raise ValueError("Enter one or more squares, for example B2 C2 D3.")
    return [parse_coordinate(part, width=width, height=height) for part in parts]


def render_menu(items: Sequence[str] = MAIN_MENU) -> str:
    """Format numbered choices for an ordinary scrolling terminal."""
    return "\n".join(f"{number}. {label}" for number, label in enumerate(items, 1))


def build_action_menu(
    available_actions: Sequence[str],
    *,
    preserve_s1: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Pair command IDs with labels; legality and availability come from engine options."""
    if preserve_s1:
        return tuple(zip(_S1_MENU_ACTIONS, MAIN_MENU))
    entries = [("inspect", "Inspect")]
    entries.extend(
        (action_id, _ACTION_LABELS.get(action_id, action_id.replace("_", " ").title()))
        for action_id in available_actions
    )
    entries.extend(
        (
            ("save", "Save"),
            ("load", "Load"),
            ("restart", "Restart"),
            ("quit", "Quit"),
        )
    )
    return tuple(entries)


def render_grid(
    width: int,
    height: int,
    positions: Mapping[str, tuple[int, int]],
    markers: Mapping[str, str] | None = None,
) -> str:
    """Render actor positions without applying any map or movement rules.

    ``positions`` maps actor ids to zero-based squares. ``markers`` supplies
    the single-character symbol used for each actor. Overlapping entries are
    displayed as ``*`` so the formatter never silently hides an actor.
    """
    if not 1 <= width <= 26 or height < 1:
        raise ValueError("Grid dimensions must be 1–26 columns and at least 1 row.")
    cells: dict[tuple[int, int], str] = {}
    for actor_id, (x, y) in positions.items():
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"{actor_id} is outside the displayed grid.")
        marker = (markers or {}).get(actor_id, actor_id[:1] or "?")[:1].upper()
        if (x, y) in cells:
            cells[(x, y)] = "*"
        else:
            cells[(x, y)] = marker

    columns = " ".join(chr(ord("A") + x) for x in range(width))
    row_width = len(str(height))
    rows = [f"   {columns}"]
    for y in range(height):
        contents = " ".join(cells.get((x, y), ".") for x in range(width))
        rows.append(f"{y + 1:>{row_width}}  {contents}")
    return "\n".join(rows)


def render_actor_lines(actors: Sequence[Mapping[str, object]]) -> str:
    """Render a concise roster from already-inspected actor data."""
    lines: list[str] = []
    for actor in actors:
        name = str(actor["name"])
        team = str(actor["team"])
        hp = actor["hp"]
        max_hp = actor["max_hp"]
        conditions = actor.get("conditions")
        condition_text = (
            ", ".join(str(value) for value in conditions)
            if conditions is not None
            else "not modeled in S1"
        ) or "none"
        lines.append(f"{name} ({team}) — HP {hp}/{max_hp}; conditions: {condition_text}")
    return "\n".join(lines)


def render_support_summary(setup_id: str = "s1_duel") -> str:
    """Explain the admitted boundary for a known setup."""
    if setup_id.startswith("s3_"):
        from pf2e.content import S3_READY

        return S3_ADMITTED_SCOPE_NOTICE if S3_READY else S3_SCOPE_NOTICE
    if setup_id.startswith("s2_"):
        from pf2e.content import S2_READY

        return S2_ADMITTED_SCOPE_NOTICE if S2_READY else S2_SCOPE_NOTICE
    return PROTOTYPE_NOTICE


def _actor_conditions(actor: object) -> tuple[str, ...]:
    """Format explicit condition fields without deriving their rule effects."""
    conditions: list[str] = []
    dying = getattr(actor, "dying", 0)
    wounded = getattr(actor, "wounded", 0)
    if dying:
        conditions.append(f"dying {dying}")
    if wounded:
        conditions.append(f"wounded {wounded}")
    for name in ("unconscious", "dead", "prone"):
        if getattr(actor, name, False):
            conditions.append(name)
    if getattr(actor, "defeated", False) and "dead" not in conditions:
        conditions.append("defeated")
    return tuple(conditions)


def _has_extended_health(actor: object) -> bool:
    mode = getattr(actor, "health_mode", None)
    mode = getattr(mode, "value", mode)
    return mode in {"ordinary", "pc"}


def render_actor_sheet(actor: object) -> str:
    """Render immutable sheet fields surfaced by the engine's inspection."""
    lines = [f"{actor.label} ({actor.actor_id})"]
    identity = [
        value
        for value in (
            getattr(actor, "ancestry", None),
            getattr(actor, "heritage", None),
            getattr(actor, "background", None),
            getattr(actor, "class_name", None),
            getattr(actor, "deity", None),
        )
        if value
    ]
    if identity:
        lines.append("Identity: " + " · ".join(identity))
    lines.append(
        f"Level {getattr(actor, 'level', '?')} · {getattr(actor, 'size', 'unknown')} · "
        f"HP {actor.hp}/{actor.max_hp} · AC {getattr(actor, 'ac', '?')} · "
        f"Perception {getattr(actor, 'perception', '?')}"
    )

    abilities = getattr(actor, "ability_modifiers", ())
    if abilities:
        lines.append("Abilities: " + ", ".join(f"{name.title()} {value:+d}" for name, value in abilities))
    for label, key in (("Saves", "saves"), ("Skills", "skills")):
        entries = getattr(actor, key, ())
        if entries:
            rendered = []
            for entry in entries:
                name, rank, modifier = entry
                rank_text = f"{rank} " if rank else "printed "
                rendered.append(f"{name.replace('_', ' ').title()} {rank_text}{modifier:+d}")
            lines.append(f"{label}: " + ", ".join(rendered))
    proficiencies = getattr(actor, "proficiencies", ())
    if proficiencies:
        lines.append(
            "Proficiencies: "
            + ", ".join(f"{name.replace('_', ' ').title()} {rank}" for name, rank in proficiencies)
        )
    class_dc = getattr(actor, "class_dc", None)
    if class_dc is not None:
        lines.append(f"Class DC {class_dc}")
    for label, key in (
        ("Feats", "feats"),
        ("Abilities", "abilities"),
        ("Languages", "languages"),
        ("Senses", "senses"),
        ("Held", "held_items"),
        ("Worn", "worn_items"),
        ("Carried", "stowed_items"),
    ):
        values = getattr(actor, key, ())
        if values:
            lines.append(f"{label}: " + ", ".join(str(value) for value in values))
    ammunition = getattr(actor, "ammunition", ())
    if ammunition:
        lines.append(
            "Ammunition: "
            + ", ".join(f"{ammo_id.replace('_', ' ').title()} {count}" for ammo_id, count in ammunition)
        )
    prepared_slots = getattr(actor, "prepared_slots", ())
    if prepared_slots:
        lines.append("Prepared spells:")
        for slot in prepared_slots:
            spell_name = str(slot.spell_id).replace("_", " ").title()
            source = str(slot.source).replace("_", " ").title()
            kind = "cantrip" if slot.cantrip else f"rank {slot.rank}"
            status = "spent" if slot.spent else "ready"
            slot_label = str(slot.slot_id).replace("_", " ").title()
            lines.append(f"  {slot_label}: {spell_name} ({source}, {kind}, {status})")
    notes = getattr(actor, "sheet_notes", ())
    lines.extend(f"Note: {note}" for note in notes)
    return "\n".join(lines)


def render_inspection(inspection: object, *, include_sheets: bool = False) -> str:
    """Format an engine inspection without deriving rules state."""
    actors = inspection.actors
    current_id = inspection.turn_actor_id
    current = next((actor for actor in actors if actor.actor_id == current_id), None)
    if current is None:
        headline = f"Round {inspection.round_number} · no active actor"
    else:
        headline = (
            f"Round {inspection.round_number} · {current.label} ({current.team}) · "
            f"{current.actions_remaining} actions · HP {current.hp}/{current.max_hp}"
        )

    markers = {actor.actor_id: chr(ord("A") + index) for index, actor in enumerate(actors)}
    positions = {actor.actor_id: (actor.position.x, actor.position.y) for actor in actors}
    lines = [headline, "", "Map:"]
    lines.extend(
        render_grid(
            inspection.map_width,
            inspection.map_height,
            positions,
            markers,
        ).splitlines()
    )
    legend = "; ".join(
        f"{markers[actor.actor_id]} = {actor.label} ({actor.team})" for actor in actors
    )
    lines.append(f"Legend: {legend}")
    has_condition_data = any(_has_extended_health(actor) for actor in actors)
    if not has_condition_data:
        lines.append("Conditions: not modeled in S1.")
    lines.append("Actors:")
    for actor in actors:
        active = " · active turn" if actor.actor_id == current_id else ""
        defeated = " · defeated" if actor.defeated else ""
        extended = _has_extended_health(actor)
        condition_text = ""
        resources = ""
        if extended:
            conditions = _actor_conditions(actor)
            condition_text = f"; conditions: {', '.join(conditions) if conditions else 'none'}"
            hero_points = getattr(actor, "hero_points", None)
            health_mode = getattr(actor, "health_mode", None)
            health_mode = getattr(health_mode, "value", health_mode)
            if hero_points is not None and (hero_points or health_mode == "pc"):
                resources += f" · Hero Points {hero_points}"
            reaction = getattr(actor, "reaction_available", None)
            if reaction is not None:
                resources += f" · reaction {'ready' if reaction else 'spent'}"
        lines.append(
            f"{actor.label} ({actor.team}) — HP {actor.hp}/{actor.max_hp}; "
            f"{actor.actions_remaining} actions; initiative {actor.initiative}"
            f"{condition_text}{resources}"
            f"{active}{defeated}"
        )
    if has_condition_data:
        for actor in actors:
            held = getattr(actor, "held_items", ())
            worn = getattr(actor, "worn_items", ())
            equipment = []
            if held:
                equipment.append("held " + ", ".join(held))
            if worn:
                equipment.append("worn " + ", ".join(worn))
            stowed = getattr(actor, "stowed_items", ())
            if stowed:
                equipment.append("carried " + ", ".join(stowed))
            if equipment:
                lines.append(f"{actor.label} equipment: " + " · ".join(equipment))
            ammunition = getattr(actor, "ammunition", ())
            if ammunition:
                lines.append(
                    f"{actor.label} ammunition: "
                    + ", ".join(f"{ammo_id} {count}" for ammo_id, count in ammunition)
                )
            prepared_slots = getattr(actor, "prepared_slots", ())
            if prepared_slots:
                ready = sum(not slot.spent for slot in prepared_slots if not slot.cantrip)
                spent = sum(slot.spent for slot in prepared_slots if not slot.cantrip)
                lines.append(
                    f"{actor.label} prepared slots: {ready} ready, {spent} spent; "
                    f"{sum(slot.cantrip for slot in prepared_slots)} cantrips"
                )
                lines.append(
                    f"{actor.label} prepared: "
                    + "; ".join(
                        f"{slot.slot_id} = {str(slot.spell_id).replace('_', ' ').title()} "
                        f"({slot.source}, {'cantrip' if slot.cantrip else f'rank {slot.rank}'}, "
                        f"{'spent' if slot.spent else 'ready'})"
                        for slot in prepared_slots
                    )
                )
            for effect in getattr(actor, "effects", ()):
                source = _actor_label(inspection, effect.source_actor_id)
                target = _actor_label(inspection, effect.target_actor_id)
                name = str(effect.kind).replace("_", " ").title()
                lines.append(
                    f"Active effect: {name} {effect.value:+d} on {target}, from {source}; "
                    f"expires at source start round {effect.expires_at_source_start}."
                )
            immune_until = getattr(actor, "guidance_immune_until_round", None)
            if immune_until is not None:
                lines.append(
                    f"{actor.label} Guidance immunity through round {immune_until}."
                )
        ground_items = getattr(inspection, "ground_items", ())
        if ground_items:
            lines.append("Ground items:")
            lines.extend(
                f"ground {format_coordinate((position.x, position.y))}: {', '.join(items)}"
                for position, items in ground_items
            )
    if include_sheets and has_condition_data:
        lines.extend(("", "Character sheets:"))
        lines.extend(render_actor_sheet(actor) for actor in actors)
    return "\n".join(lines)


def render_pending_choice(choice: object, inspection: object) -> str:
    """Display a real engine choice exactly as exposed, without preselecting."""
    owner_id = getattr(choice, "owner_actor_id", None)
    owner = _actor_label(inspection, owner_id) if owner_id else "GM / encounter"
    lines = [f"{choice.prompt} (choice owner: {owner})"]
    lines.extend(str(detail) for detail in getattr(choice, "details", ()))
    lines.append(render_menu([option.label for option in choice.options]))
    return "\n".join(lines)


def format_action_result(result: object) -> tuple[str, ...]:
    """Return engine-supplied result text in causal order, without rule logic."""
    raw_status = result.status
    status = str(getattr(raw_status, "value", raw_status)).lower()
    message = str(result.message).strip()
    lines: list[str] = []
    if status in {"rejected", "unsupported"} and message:
        lines.append(f"{status.title()}: {message}")

    for event in result.events:
        text = str(event.text).strip()
        if text and text not in lines:
            lines.append(text)
        for detail in getattr(event, "details", ()):
            detail_text = str(detail).strip()
            if detail_text and detail_text not in lines:
                lines.append(detail_text)
    if status not in {"rejected", "unsupported"} and message and message not in lines:
        lines.append(message)
    if not lines:
        lines.append(f"Action {status}.")
    return tuple(lines)


def _read_line(
    prompt: str,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str:
    output_fn(prompt)
    try:
        return input_fn()
    except StopIteration as exc:
        raise EOFError from exc


def _actor_label(inspection: object, actor_id: str) -> str:
    actor = next((item for item in inspection.actors if item.actor_id == actor_id), None)
    return actor.label if actor is not None else actor_id


def _choose_target(
    targets: Sequence[str],
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
    prompt: str = "Strike target:",
) -> str | None:
    if not targets:
        output_fn("No legal Strike targets are available now.")
        return None
    labels = [f"{_actor_label(inspection, target_id)} ({target_id})" for target_id in targets]
    output_fn(prompt)
    output_fn(render_menu(labels))
    while True:
        try:
            choice = parse_menu_choice(
                _read_line("Target number:", input_fn, output_fn),
                len(targets),
            )
            return targets[choice - 1]
        except ValueError as exc:
            output_fn(str(exc))


def _choose_index(
    prompt: str,
    labels: Sequence[str],
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> int | None:
    if not labels:
        output_fn("The engine did not provide any selectable options.")
        return None
    output_fn(render_menu(labels))
    while True:
        try:
            return parse_menu_choice(
                _read_line(prompt, input_fn, output_fn),
                len(labels),
            ) - 1
        except ValueError as exc:
            output_fn(str(exc))


def _choose_strike_inputs(
    strikes: Sequence[object],
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, str, str | None, bool | None] | None:
    """Ask only for attack data exposed by current engine options."""
    strike_index = _choose_index(
        "Weapon / attack number:",
        [f"{option.name} ({option.attack_id})" for option in strikes],
        input_fn,
        output_fn,
    )
    if strike_index is None:
        return None
    attack = strikes[strike_index]
    target_id = _choose_target(
        attack.targets,
        inspection,
        input_fn,
        output_fn,
        prompt=f"{attack.name} target:",
    )
    if target_id is None:
        return None

    damage_type: str | None = None
    damage_types = tuple(attack.damage_types)
    if len(damage_types) > 1:
        damage_index = _choose_index(
            "Damage type:",
            [damage_type.title() for damage_type in damage_types],
            input_fn,
            output_fn,
        )
        if damage_index is None:
            return None
        damage_type = damage_types[damage_index]

    default_intent = "nonlethal" if attack.default_nonlethal else "lethal"
    intent_index = _choose_index(
        "Damage intent:",
        (
            f"Use attack default ({default_intent})",
            "Lethal damage",
            "Nonlethal damage",
        ),
        input_fn,
        output_fn,
    )
    if intent_index is None:
        return None
    nonlethal = (None, False, True)[intent_index]
    return attack.attack_id, target_id, damage_type, nonlethal


def _choose_cast_inputs(
    spells: Sequence[object],
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, str | None, int, str | None, bool | None] | None:
    """Collect only spell choices and legal targets surfaced by engine options."""
    available = []
    for spell in spells:
        unavailable_reason = getattr(spell, "unavailable_reason", None)
        if unavailable_reason:
            output_fn(f"Unavailable: {spell.name} — {unavailable_reason}")
        else:
            available.append(spell)
    spell_index = _choose_index(
        "Spell number:",
        [
            f"{spell.name} ({', '.join(spell.traits)})"
            if spell.traits
            else spell.name
            for spell in available
        ],
        input_fn,
        output_fn,
    )
    if spell_index is None:
        return None
    spell = available[spell_index]

    target_modes = tuple(spell.target_options)
    if not target_modes:
        output_fn("The engine did not provide a selectable target or casting mode for this spell.")
        return None
    mode_index = _choose_index(
        "Casting mode:",
        [f"{option.actions} action" + ("s" if option.actions != 1 else "") for option in target_modes],
        input_fn,
        output_fn,
    )
    if mode_index is None:
        return None
    target_mode = target_modes[mode_index]

    slot_id = None
    if spell.slots:
        slot_index = _choose_index(
            "Prepared slot:",
            [f"{slot_id} ({source})" for slot_id, source in spell.slots],
            input_fn,
            output_fn,
        )
        if slot_index is None:
            return None
        slot_id = spell.slots[slot_index][0]

    target_id: str | None = None
    include_self: bool | None = None
    if target_mode.include_self_available:
        affected = [
            _actor_label(inspection, actor_id)
            for actor_id in target_mode.targets
        ]
        output_fn(
            "Other engine-listed recipients: "
            + (", ".join(affected) if affected else "none")
        )
        output_fn("The engine will ask whether to include the caster.")
    else:
        target_id = _choose_target(
            target_mode.targets,
            inspection,
            input_fn,
            output_fn,
            prompt=f"{spell.name} target:",
        )
        if target_id is None:
            return None
    return spell.spell_id, target_id, target_mode.actions, slot_id, include_self


def _interact_label(mode: str, item_id: str) -> str:
    verb = {
        "draw": "Draw",
        "stow": "Stow",
        "retrieve": "Retrieve",
    }.get(mode, mode.replace("_", " ").title())
    return f"{verb}: {item_id}"


def _run_command(game: Encounter, command: object, output_fn: Callable[[str], object]) -> None:
    result = game.execute(command)
    for line in format_action_result(result):
        output_fn(line)


def run_terminal(
    *,
    setup: object | None = None,
    seed: int = 0,
    rolls: Sequence[int] | None = None,
    save_path: str | Path = "s1-save.json",
    input_fn: Callable[[], str] | None = None,
    output_fn: Callable[[str], object] = print,
) -> int:
    """Play the S1 fixture through numbered prompts and the public engine API."""
    from pf2e.content import S1_SETUP
    from pf2e.encounter import Encounter
    from pf2e.model import (
        Cast,
        Choose,
        Crawl,
        EndTurn,
        Interact,
        Position,
        Release,
        Stand,
        Step,
        Stride,
        Strike,
        TakeCover,
        ViciousSwing,
    )

    if input_fn is None:
        input_fn = input
    if setup is None:
        setup = S1_SETUP
    scripted_rolls = tuple(rolls) if rolls is not None else None
    game = Encounter.start(setup=setup, seed=seed, rolls=scripted_rolls)
    output_fn(render_support_summary(getattr(setup, "setup_id", "s1_duel")))

    try:
        while True:
            inspection = game.inspect()
            output_fn("")
            output_fn(render_inspection(inspection))
            if not inspection.in_progress:
                output_fn("Encounter finished. Restart, load a save, save this result, or quit.")

            pending_choice = getattr(inspection, "choice", None)
            if pending_choice is not None:
                output_fn(render_pending_choice(pending_choice, inspection))
                choice_menu = ("Inspect sheet and encounter", "Resolve this choice", "Save", "Load", "Restart", "Quit")
                output_fn(render_menu(choice_menu))
                try:
                    choice = parse_menu_choice(
                        _read_line("Choice prompt action:", input_fn, output_fn),
                        len(choice_menu),
                    )
                except ValueError as exc:
                    output_fn(str(exc))
                    continue
                if choice == 1:
                    output_fn(render_inspection(inspection, include_sheets=True))
                elif choice == 2:
                    options = pending_choice.options
                    if not options:
                        output_fn("This engine choice has no available options.")
                        continue
                    output_fn(render_menu([option.label for option in options]))
                    try:
                        option_number = parse_menu_choice(
                            _read_line("Choice option number:", input_fn, output_fn),
                            len(options),
                        )
                    except ValueError as exc:
                        output_fn(str(exc))
                        continue
                    option = options[option_number - 1]
                    _run_command(
                        game,
                        Choose(
                            choice_id=pending_choice.choice_id,
                            option_id=option.option_id,
                            actor_id=pending_choice.owner_actor_id,
                        ),
                        output_fn,
                    )
                elif choice == 3:
                    raw_path = _read_line(
                        f"Save file [{save_path}]; press Enter to use it:", input_fn, output_fn
                    )
                    selected_path = raw_path.strip() or str(save_path)
                    try:
                        game.save(selected_path)
                        output_fn(f"Saved encounter to {selected_path}.")
                    except (OSError, ValueError, TypeError) as exc:
                        output_fn(f"Could not save encounter: {exc}")
                elif choice == 4:
                    raw_path = _read_line(
                        f"Load file [{save_path}]; press Enter to use it:", input_fn, output_fn
                    )
                    selected_path = raw_path.strip() or str(save_path)
                    try:
                        game = Encounter.load(selected_path)
                        output_fn(f"Loaded encounter from {selected_path}.")
                    except (OSError, ValueError, TypeError, KeyError) as exc:
                        output_fn(f"Could not load encounter: {exc}")
                elif choice == 5:
                    game = Encounter.start(setup=setup, seed=seed, rolls=scripted_rolls)
                    output_fn("Encounter restarted.")
                else:
                    output_fn("Goodbye.")
                    return 0
                continue

            engine_options = game.options()
            is_s1 = getattr(setup, "setup_id", None) == "s1_duel"
            menu_entries = build_action_menu(
                engine_options.available_actions,
                preserve_s1=is_s1,
            )
            output_fn(render_menu([label for _, label in menu_entries]))
            choice_text = _read_line("Choice:", input_fn, output_fn)
            try:
                choice = parse_menu_choice(choice_text, len(menu_entries))
            except ValueError as exc:
                output_fn(str(exc))
                continue
            action_id = menu_entries[choice - 1][0]

            if not inspection.in_progress and action_id not in {"save", "load", "restart", "quit"}:
                output_fn("The encounter is finished; choose Save, Load, Restart, or Quit.")
                continue

            if action_id == "inspect":
                output_fn(render_inspection(inspection, include_sheets=True))
                continue
            elif action_id == "stride":
                try:
                    raw_path = _read_line(
                        "Stride path, in order (for example B2 C2 D3):",
                        input_fn,
                        output_fn,
                    )
                    points = parse_path(
                        raw_path,
                        width=inspection.map_width,
                        height=inspection.map_height,
                    )
                    _run_command(
                        game,
                        Stride(path=tuple(Position(x=x, y=y) for x, y in points)),
                        output_fn,
                    )
                except ValueError as exc:
                    output_fn(str(exc))
            elif action_id == "step":
                destinations = ", ".join(
                    format_coordinate((position.x, position.y))
                    for position in engine_options.step_destinations
                )
                if destinations:
                    output_fn(f"Step destinations from engine: {destinations}")
                try:
                    raw_destination = _read_line(
                        "Step destination:",
                        input_fn,
                        output_fn,
                    )
                    x, y = parse_coordinate(
                        raw_destination,
                        width=inspection.map_width,
                        height=inspection.map_height,
                    )
                    _run_command(game, Step(destination=Position(x=x, y=y)), output_fn)
                except ValueError as exc:
                    output_fn(str(exc))
            elif action_id == "strike":
                if is_s1:
                    target_id = _choose_target(
                        engine_options.strike_targets,
                        inspection,
                        input_fn,
                        output_fn,
                    )
                    if target_id is not None:
                        _run_command(game, Strike(target_id=target_id), output_fn)
                else:
                    strike_inputs = _choose_strike_inputs(
                        engine_options.strikes,
                        inspection,
                        input_fn,
                        output_fn,
                    )
                    if strike_inputs is not None:
                        attack_id, target_id, damage_type, nonlethal = strike_inputs
                        _run_command(
                            game,
                            Strike(
                                target_id=target_id,
                                attack_id=attack_id,
                                damage_type=damage_type,
                                nonlethal=nonlethal,
                            ),
                            output_fn,
                        )
            elif action_id == "vicious_swing":
                strike_inputs = _choose_strike_inputs(
                    engine_options.strikes,
                    inspection,
                    input_fn,
                    output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    _run_command(
                        game,
                        ViciousSwing(
                            target_id=target_id,
                            attack_id=attack_id,
                            damage_type=damage_type,
                            nonlethal=nonlethal,
                        ),
                        output_fn,
                    )
            elif action_id == "interact":
                interact_index = _choose_index(
                    "Interact option:",
                    [_interact_label(mode, item_id) for mode, item_id in engine_options.interact_options],
                    input_fn,
                    output_fn,
                )
                if interact_index is not None:
                    mode, item_id = engine_options.interact_options[interact_index]
                    _run_command(game, Interact(mode=mode, item_id=item_id), output_fn)
            elif action_id == "release":
                actor = next(
                    (item for item in inspection.actors if item.actor_id == engine_options.actor_id),
                    None,
                )
                held_items = tuple(actor.held_items) if actor is not None else ()
                release_index = _choose_index(
                    "Item to Release:",
                    held_items,
                    input_fn,
                    output_fn,
                )
                if release_index is not None:
                    _run_command(game, Release(item_id=held_items[release_index]), output_fn)
            elif action_id == "stand":
                _run_command(game, Stand(), output_fn)
            elif action_id == "crawl":
                try:
                    raw_path = _read_line(
                        "Crawl path, in order (for example B2 C2):",
                        input_fn,
                        output_fn,
                    )
                    points = parse_path(
                        raw_path,
                        width=inspection.map_width,
                        height=inspection.map_height,
                    )
                    _run_command(
                        game,
                        Crawl(path=tuple(Position(x=x, y=y) for x, y in points)),
                        output_fn,
                    )
                except ValueError as exc:
                    output_fn(str(exc))
            elif action_id == "take_cover":
                _run_command(game, TakeCover(), output_fn)
            elif action_id == "cast":
                cast_inputs = _choose_cast_inputs(
                    engine_options.spells,
                    inspection,
                    input_fn,
                    output_fn,
                )
                if cast_inputs is not None:
                    spell_id, target_id, actions, slot_id, include_self = cast_inputs
                    _run_command(
                        game,
                        Cast(
                            spell_id=spell_id,
                            target_id=target_id,
                            actions=actions,
                            slot_id=slot_id,
                            include_self=include_self,
                        ),
                        output_fn,
                    )
            elif action_id == "end_turn":
                _run_command(game, EndTurn(), output_fn)
            elif action_id == "save":
                raw_path = _read_line(
                    f"Save file [{save_path}]; press Enter to use it:",
                    input_fn,
                    output_fn,
                )
                selected_path = raw_path.strip() or str(save_path)
                try:
                    game.save(selected_path)
                    output_fn(f"Saved encounter to {selected_path}.")
                except (OSError, ValueError, TypeError) as exc:
                    output_fn(f"Could not save encounter: {exc}")
            elif action_id == "load":
                raw_path = _read_line(
                    f"Load file [{save_path}]; press Enter to use it:",
                    input_fn,
                    output_fn,
                )
                selected_path = raw_path.strip() or str(save_path)
                try:
                    game = Encounter.load(selected_path)
                    output_fn(f"Loaded encounter from {selected_path}.")
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    output_fn(f"Could not load encounter: {exc}")
            elif action_id == "restart":
                game = Encounter.start(setup=setup, seed=seed, rolls=scripted_rolls)
                output_fn("Encounter restarted.")
            elif action_id == "quit":
                output_fn("Goodbye.")
                return 0
            else:
                output_fn(f"The terminal does not yet provide input controls for {action_id}.")
    except EOFError:
        output_fn("End of input; quitting.")
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play a local PF2e encounter.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    play_parser = subparsers.add_parser("play", help="play a numbered terminal encounter")
    from pf2e.content import SETUPS

    play_parser.add_argument(
        "encounter",
        choices=("s1", "s2", "s3", *SETUPS),
        help="encounter preset or catalogued setup name",
    )
    play_parser.add_argument("--seed", type=int, default=0, help="seed for automatic dice")
    play_parser.add_argument(
        "--save-path",
        default="s1-save.json",
        help="default file used by the Save and Load choices",
    )
    args = parser.parse_args(argv)
    if args.command == "play":
        setup_id = {
            "s1": "s1_duel",
            "s2": "s2_fighters_vs_guard_dogs",
            "s3": "s3_mixed_party_vs_three_guard_dogs",
        }.get(args.encounter, args.encounter)
        if setup_id.startswith("s2_"):
            from pf2e.content import S2_READY

            if not S2_READY:
                print(S2_SCOPE_NOTICE)
                return 2
        if setup_id.startswith("s3_"):
            from pf2e.content import S3_READY

            if not S3_READY:
                print(S3_SCOPE_NOTICE)
                return 2
        from pf2e.content import get_setup

        return run_terminal(setup=get_setup(setup_id), seed=args.seed, save_path=args.save_path)
    return 2
