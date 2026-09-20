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

from pf2e.model import Cackle, EnergyAblation, Position

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
    "quick_bomber": "Quick Bomber",
    "quick_alchemy": "Quick Alchemy",
    "activate_alchemy": "Activate Alchemy Item",
    "confident_finisher": "Confident Finisher",
    "devise_stratagem": "Devise a Stratagem",
    "known_weaknesses": "Known Weaknesses + Devise",
    "vicious_swing": "Vicious Swing",
    "exacting_strike": "Exacting Strike",
    "double_slice": "Double Slice",
    "twin_takedown": "Twin Takedown",
    "twin_feint": "Twin Feint",
    "intimidating_strike": "Intimidating Strike",
    "snagging_strike": "Snagging Strike",
    "combat_grab": "Combat Grab",
    "brutish_shove": "Brutish Shove",
    "sudden_charge": "Sudden Charge",
    "dueling_parry": "Dueling Parry",
    "crane_stance": "Crane Stance",
    "dismiss_crane_stance": "Dismiss Crane Stance",
    "point_blank_stance": "Point Blank Stance",
    "flurry_of_blows": "Flurry of Blows",
    "hunt_prey": "Hunt Prey",
    "hunted_shot": "Hunted Shot",
    "hunter_aim": "Hunter's Aim",
    "interact": "Interact",
    "release": "Release",
    "stand": "Stand",
    "crawl": "Crawl",
    "take_cover": "Take Cover",
    "raise_shield": "Raise a Shield",
    "lay_on_hands": "Lay on Hands",
    "battle_medicine": "Battle Medicine",
    "person_of_interest": "Person of Interest",
    "suppress_aura": "Suppress Aura",
    "resume_aura": "Resume Aura",
    "trip": "Trip",
    "trip_assurance": "Trip (Assurance)",
    "quick_jump": "Quick Jump",
    "grapple": "Grapple",
    "grapple_assurance": "Grapple (Assurance)",
    "escape": "Escape",
    "escape_assurance": "Escape (Assurance)",
    "flee": "Flee",
    "demoralize": "Demoralize",
    "tumble_through": "Tumble Through",
    "feint": "Feint",
    "recall_knowledge": "Recall Knowledge",
    "forensic_examine": "Forensic Acumen Examination",
    "pursue_lead": "Pursue a Lead",
    "streetwise": "Streetwise",
    "animal_empathy": "Animal Empathy",
    "nudge_the_scales": "Nudge the Scales",
    "oracle_life_mode": "Choose Oracle Life/Death Mode",
    "rage": "Rage",
    "drain_bonded_item": "Drain Bonded Item",
    "cast": "Cast",
    "lingering_composition": "Lingering Composition",
    "reach_spell": "Reach Spell",
    "widen_spell": "Widen Spell",
    "energy_ablation": "Energy Ablation",
    "cackle": "Cackle",
    "sustain_light": "Sustain Light",
    "dismiss_light": "Dismiss Light",
    "dismiss_life_link": "Dismiss Life Link",
    "end_turn": "End Turn",
    "refocus": "Refocus (10 minutes)",
    "next_encounter": "Next Encounter",
    "record_rested": "Record Rested Eligibility",
    "daily_prepare": "Daily Preparation",
    "spell_substitution": "Spell Substitution (10 minutes)",
    "interrupt_spell_substitution": "Interrupt Spell Substitution",
}

PROTOTYPE_NOTICE = (
    "S1 prototype: synthetic NPC-style test actors on an open grid. "
    "This is not published-creature or PC support. Reactions, spellcasting, "
    "conditions, terrain, and PC dying/recovery are outside this prototype. "
    "At 0 HP, a test actor is defeated; the fight ends when one team has no "
    "active actor."
)
FIXED_ENCOUNTER_NOTICE = (
    "Fixed local encounter: the displayed actors and available actions define this setup's "
    "admitted play boundary. All sides remain manually controlled; broader class, creature, "
    "and PF2e options are outside scope. A team loses when it has no conscious, living "
    "combat-capable actor."
)
SWASHBUCKLER_ADMITTED_SCOPE_NOTICE = (
    "Curated Braggart Swashbuckler setup: this local encounter exposes Braggart "
    "Demoralize, Panache, dagger Precise Strike, Confident Finisher, Tumble "
    "Through, and Flying Blade thrown dagger attacks in the first 10-foot range increment."
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
ANGELIC_ADMITTED_SCOPE_NOTICE = (
    "Curated Angelic level-1 Sorcerer first-cast setup: the selected Human sheet, "
    "Angelic Halo/Blood Magic, Light, Divine Lance, Heal, Fear, and Runic Weapon "
    "paths have bounded public support, including resource use and saved choices. "
    "The ally's mundane longsword is an item identity that survives transfer and "
    "save/load. This admits one authored setup; broader Sorcerer and Angelic "
    "options, including offensive Heal against undead, remain outside scope."
)
JUSTICE_ADMITTED_SCOPE_NOTICE = (
    "Curated Justice level-1 Champion of Iomedae setup: the selected Human sheet, "
    "15-foot divine aura, Retributive Strike protection, Lay on Hands, and Desperate "
    "Prayer have bounded public support, including deterministic encounter choices and "
    "save/load. This admits one authored setup; undead Lay on Hands, broader Champion "
    "causes, and other subclass options remain outside scope."
)
INVESTIGATOR_ADMITTED_SCOPE_NOTICE = (
    "Curated level-1 Forensic Investigator setup: the authored Human sheet, "
    "attack Devise a Stratagem, Intelligence substitution for the agile/finesse "
    "shortsword, and Strategic Strike precision damage have bounded public support, "
    "Battle Medicine with Forensic Medicine's level healing bonus and one-hour "
    "medic/recipient immunity also have bounded public support, including deterministic "
    "save/load. Normal Recall Knowledge and Known Weaknesses use the authored "
    "question/answer packet in these scenes. The authored Forensic Acumen body "
    "examination and immediate relevant follow-up are also supported outside combat. "
    "The authored Pursue a Lead, Clue In, lead-aware free Devise, and Skill "
    "Stratagem paths are supported for the selected case."
)
LIFE_ORACLE_ADMITTED_SCOPE_NOTICE = (
    "Curated level-1 Life Oracle setup: the selected Human Scholar sheet, "
    "Nudge the Scales, Life Link, Vitality Lash, finite divine repertoire, "
    "daily life/death choice, Refocus, and saved encounter choices have "
    "bounded public support. This admits one authored Life mystery build; "
    "other mysteries, anathema adjudication, persistent damage, and positive "
    "damage against stabilized 0-HP PCs remain outside this scope."
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
    include_refocus: bool = False,
    include_next_encounter: bool = False,
    include_downtime: bool = False,
    include_examination: bool = False,
    include_lead: bool = False,
    include_streetwise: bool = False,
    include_animal_empathy: bool = False,
    include_spell_substitution: bool = False,
    include_oracle_life_mode: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Pair command IDs with labels; legality and availability come from engine options."""
    if preserve_s1:
        entries = list(zip(_S1_MENU_ACTIONS, MAIN_MENU))
    else:
        entries = [("inspect", "Inspect")]
        # Keep the trailing Save/Load/Restart/Quit positions stable for the
        # existing bounded scripts as new Investigator actions are added.
        appended_actions = {"recall_knowledge", "known_weaknesses"}
        entries.extend(
            (action_id, _ACTION_LABELS.get(action_id, action_id.replace("_", " ").title()))
            for action_id in available_actions
            if action_id not in appended_actions
        )
        entries.extend(
            (
                ("save", "Save"),
                ("load", "Load"),
                ("restart", "Restart"),
                ("quit", "Quit"),
            )
        )
        entries.extend(
            (action_id, _ACTION_LABELS.get(action_id, action_id.replace("_", " ").title()))
            for action_id in available_actions
            if action_id in appended_actions
        )
    if include_refocus:
        # Keep this separate from engine combat options.  Encounter owns
        # eligibility; the terminal only makes the public post-combat
        # activity reachable and collects the actor identity.
        entries.insert(1, ("refocus", _ACTION_LABELS["refocus"]))
    if include_next_encounter:
        # The curated Angelic and Bomber carry routes are the authored scene
        # transitions exposed by this small terminal adapter. The encounter
        # engine still owns all eligibility and atomic validation.
        # Keep the existing Save/Load/Restart/Quit positions stable for
        # scripts that already drive the post-combat Refocus menu.
        entries.append(("next_encounter", _ACTION_LABELS["next_encounter"]))
    if include_downtime:
        # Append downtime controls so established post-combat menu positions
        # for Save/Load/Restart/Quit and the staged Next Encounter remain
        # stable for existing terminal scripts.
        entries.extend(
            (
                ("record_rested", _ACTION_LABELS["record_rested"]),
                ("daily_prepare", _ACTION_LABELS["daily_prepare"]),
            )
        )
    if include_oracle_life_mode:
        entries.append(("oracle_life_mode", _ACTION_LABELS["oracle_life_mode"]))
    if include_spell_substitution:
        entries.extend(
            (
                ("spell_substitution", _ACTION_LABELS["spell_substitution"]),
                ("interrupt_spell_substitution", _ACTION_LABELS["interrupt_spell_substitution"]),
            )
        )
    if include_examination:
        # Body examinations are authored outside-combat activities.  Append
        # this control after the established recovery controls so existing
        # bounded terminal scripts retain their menu positions.
        entries.append(("forensic_examine", _ACTION_LABELS["forensic_examine"]))
    if include_lead:
        entries.append(("pursue_lead", _ACTION_LABELS["pursue_lead"]))
    if include_streetwise:
        entries.append(("streetwise", _ACTION_LABELS["streetwise"]))
    if include_animal_empathy:
        entries.append(("animal_empathy", _ACTION_LABELS["animal_empathy"]))
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
    if setup_id == "sorcerer_angelic_first_cast":
        return ANGELIC_ADMITTED_SCOPE_NOTICE
    if setup_id == "justice_champion_iomedae_vs_guard_dog":
        return JUSTICE_ADMITTED_SCOPE_NOTICE
    if setup_id in {
        "investigator_forensic_vs_two_guard_dogs",
        "investigator_forensic_healing_vs_ally",
    }:
        return INVESTIGATOR_ADMITTED_SCOPE_NOTICE
    if setup_id == "staged_life_oracle_nudge":
        return LIFE_ORACLE_ADMITTED_SCOPE_NOTICE
    if setup_id == "staged_braggart_swashbuckler_vs_guard_dog":
        return SWASHBUCKLER_ADMITTED_SCOPE_NOTICE
    if setup_id == "s1_duel":
        return PROTOTYPE_NOTICE
    return FIXED_ENCOUNTER_NOTICE


def _actor_conditions(actor: object, inspection: object | None = None) -> tuple[str, ...]:
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
    valued_conditions = {"clumsy", "drained", "enfeebled", "frightened", "sickened", "stupefied"}
    for effect in getattr(actor, "condition_effects", ()):
        kind = str(effect.kind).replace("_", " ")
        value = getattr(effect, "value", None)
        if value is not None and (value != 1 or effect.kind in valued_conditions):
            kind += f" {value}"
        source_id = getattr(effect, "source_actor_id", None)
        if source_id:
            source = (
                _actor_label(inspection, source_id)
                if inspection is not None
                else source_id
            )
            kind += f" (from {source})"
        conditions.append(kind)
    return tuple(conditions)


def _has_extended_health(actor: object) -> bool:
    mode = getattr(actor, "health_mode", None)
    mode = getattr(mode, "value", mode)
    return mode in {"ordinary", "pc"}


def _display_inventory_item(actor: object, item_id: str) -> str:
    """Use the inspected shield name instead of its internal instance key."""
    for shield in getattr(actor, "shields", ()):
        if shield.instance_id == item_id:
            return str(shield.definition_id).replace("_", " ").title()
    return item_id


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
        f"Perception {getattr(actor, 'perception', '?')} · Speed {getattr(actor, 'speed_ft', '?')} ft"
    )
    if getattr(actor, "class_name", None) == "Swashbuckler":
        panache = "active" if getattr(actor, "panache", False) else "inactive"
        lines.append(f"Panache: {panache}")

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
        if key in {"held_items", "worn_items", "stowed_items"}:
            values = tuple(_display_inventory_item(actor, str(value)) for value in values)
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


def _render_shields(actor: object) -> str:
    """Summarize the inspected shield state without exposing instance IDs."""
    summaries: list[str] = []
    for shield in getattr(actor, "shields", ()):
        name = str(shield.definition_id).replace("_", " ").title()
        status = [f"HP {shield.hp}/{shield.max_hp}"]
        if shield.raised:
            status.append("raised")
        else:
            status.append("not raised")
        status.append("broken" if shield.broken else "intact")
        if shield.ac_bonus_active:
            status.append(f"AC +{shield.ac_bonus}")
        else:
            status.append("AC bonus inactive")
        summaries.append(f"{name} (" + "; ".join(status) + ")")
    return ", ".join(summaries)


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
    preparation_day = getattr(inspection, "preparation_day", None)
    rested_actor_ids = tuple(getattr(inspection, "rested_actor_ids", ()))
    if preparation_day is not None:
        rested = ", ".join(_actor_label(inspection, actor_id) for actor_id in rested_actor_ids) or "none"
        lines.append(f"Declared preparation day: {preparation_day}; rested eligibility: {rested}.")
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
            conditions = _actor_conditions(actor, inspection)
            condition_text = f"; conditions: {', '.join(conditions) if conditions else 'none'}"
            hero_points = getattr(actor, "hero_points", None)
            health_mode = getattr(actor, "health_mode", None)
            health_mode = getattr(health_mode, "value", health_mode)
            if hero_points is not None and (hero_points or health_mode == "pc"):
                resources += f" · Hero Points {hero_points}"
            reaction = getattr(actor, "reaction_available", None)
            if reaction is not None:
                resources += f" · reaction {'ready' if reaction else 'spent'}"
        if getattr(actor, "class_name", None) == "Swashbuckler":
            resources += f" · Speed {getattr(actor, 'speed_ft', '?')} ft"
            resources += " · Panache active" if getattr(actor, "panache", False) else " · Panache inactive"
        barbarian_state = getattr(actor, "barbarian_state", None)
        if barbarian_state is not None:
            rage = getattr(barbarian_state, "rage", None)
            if rage is None:
                resources += " · Rage inactive"
            else:
                mode_id = str(getattr(rage, "mode_id", "base"))
                mode_label = {
                    "base": "normal damage",
                    "dragon_damage": "dragon damage",
                    "spirit_damage": "spirit damage",
                }.get(mode_id, "special damage")
                damage_type = getattr(rage, "damage_type", None)
                if damage_type and damage_type not in mode_label:
                    mode_label += f" ({damage_type})"
                if getattr(rage, "ghost_touch", False):
                    mode_label += ", ghost touch"
                resources += f" · Rage active ({mode_label})"
            temporary_hp = getattr(actor, "temporary_hp", None)
            if temporary_hp is not None:
                resources += f" · temporary HP {temporary_hp}"
                source_id = getattr(actor, "temporary_hp_source_id", None)
                if source_id and str(source_id).startswith("rage:"):
                    resources += " (from Rage)"
        shield_summary = _render_shields(actor)
        if shield_summary:
            resources += f" · shield: {shield_summary}"
        lines.append(
            f"{actor.label} ({actor.team}) — HP {actor.hp}/{actor.max_hp}; "
            f"{actor.actions_remaining} actions; initiative {actor.initiative}"
            f"{condition_text}{resources}"
            f"{active}{defeated}"
        )
    if has_condition_data:
        for actor in actors:
            held = getattr(actor, "held_items", ())
            held = tuple(_display_inventory_item(actor, item_id) for item_id in held)
            worn = getattr(actor, "worn_items", ())
            worn = tuple(_display_inventory_item(actor, item_id) for item_id in worn)
            equipment = []
            if held:
                equipment.append("held " + ", ".join(held))
            if worn:
                equipment.append("worn " + ", ".join(worn))
            stowed = getattr(actor, "stowed_items", ())
            stowed = tuple(_display_inventory_item(actor, item_id) for item_id in stowed)
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
            sure_until = getattr(actor, "sure_strike_immune_until_seconds", None)
            if sure_until is not None:
                lines.append(
                    f"{actor.label} Sure Strike immunity until world time {sure_until} seconds."
                )
        ground_items = getattr(inspection, "ground_items", ())
        if ground_items:
            lines.append("Ground items:")
            lines.extend(
                f"ground {format_coordinate((position.x, position.y))}: {', '.join(items)}"
                for position, items in ground_items
            )
    light_orbs = tuple(getattr(inspection, "light_orbs", ()))
    if light_orbs:
        lines.append("Light orbs:")
        actors_by_id = {actor.actor_id: actor for actor in actors}
        for orb in light_orbs:
            attached_id = getattr(orb, "attached_actor_id", None)
            if attached_id is not None:
                carrier = actors_by_id.get(attached_id)
                if carrier is None:
                    location = f"attached to {attached_id} (carrier unavailable)"
                else:
                    location = (
                        f"attached to {carrier.label} ({attached_id}) at "
                        f"{format_coordinate((carrier.position.x, carrier.position.y))}"
                    )
            else:
                point = getattr(orb, "point", None)
                location = (
                    f"at {format_coordinate((point.x, point.y))}"
                    if point is not None
                    else "at an unavailable location"
                )
            lines.append(
                f"  {getattr(orb, 'stable_id', getattr(orb, 'orb_id', 'light-orb'))}: "
                f"rank {getattr(orb, 'rank', '?')} {getattr(orb, 'color', 'white')}; {location}"
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


def _choose_devise_target(
    inspection: object,
    actor_id: str | None,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select a conscious active creature for the Investigator's Devise."""
    targets = tuple(
        actor.actor_id
        for actor in inspection.actors
        if actor.actor_id != actor_id
        and not getattr(actor, "defeated", False)
        and not getattr(actor, "unconscious", False)
        and not getattr(actor, "dead", False)
    )
    return _choose_target(
        targets,
        inspection,
        input_fn,
        output_fn,
        prompt="Devise a Stratagem target:",
    )


def _devise_is_free(game: "Encounter", actor_id: str, target_id: str) -> bool:
    """Keep terminal Devise cost aligned with the engine's saved grants."""
    from pf2e.investigator import person_of_interest_grant_allows_free_devise

    actor = game._state.creatures[actor_id]
    return (
        (
            bool(actor.investigator_active_cases)
            and target_id in actor.investigator_awareness
        )
        or person_of_interest_grant_allows_free_devise(
            actor.investigator_person_of_interest,
            target_id=target_id,
            now_seconds=game._state.world_time_seconds,
        )
    )


def _choose_recall_target(
    inspection: object,
    targets: Sequence[str],
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select an authored Recall Knowledge subject target."""
    return _choose_target(
        targets,
        inspection,
        input_fn,
        output_fn,
        prompt="Recall Knowledge subject:",
    )


def _choose_recall_skill(
    record: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select one skill from the authored Recall Knowledge skill menu."""
    pairs = tuple(getattr(record, "allowed_skills", ()))
    labels = tuple(str(skill).replace("_", " ").title() for skill, _dc in pairs)
    index = _choose_index("Recall Knowledge skill:", labels, input_fn, output_fn)
    return pairs[index][0] if index is not None else None


def _choose_forensic_examination(
    setup: object,
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, str] | None:
    """Select an authored body and the eligible Investigator who examines it."""
    records = tuple(getattr(setup, "examinations", ()))
    if not records:
        output_fn("No authored Forensic Acumen examinations are available in this scene.")
        return None
    def eligible(actor: object) -> bool:
        mode = getattr(actor, "health_mode", None)
        mode = getattr(mode, "value", mode)
        return (
            "investigator_forensic_acumen" in getattr(actor, "abilities", ())
            and mode == "pc"
            and not getattr(actor, "unconscious", False)
            and not getattr(actor, "dead", False)
        )

    actor = next((item for item in getattr(inspection, "actors", ()) if eligible(item)), None)
    if actor is None:
        output_fn("No conscious Investigator with Forensic Acumen can examine a body now.")
        return None
    labels = [
        f"{getattr(record, 'body_label', getattr(record, 'body_key', 'body'))} "
        f"({getattr(record, 'key', getattr(record, 'body_key', ''))})"
        for record in records
    ]
    index = _choose_index("Examination body number:", labels, input_fn, output_fn)
    if index is None:
        return None
    record = records[index]
    key = getattr(record, "key", getattr(record, "body_key", None))
    if not isinstance(key, str) or not key:
        output_fn("The selected examination has no usable authored key.")
        return None
    return actor.actor_id, key


def _choose_pursue_lead(
    setup: object,
    game: object,
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, str, str] | None:
    """Select one authored case/clue for the public downtime activity."""
    records = tuple(getattr(setup, "investigations", ()))
    if not records:
        output_fn("No authored investigations are available in this scene.")
        return None
    actor = next(
        (
            item for item in getattr(inspection, "actors", ())
            if "investigator_on_the_case" in getattr(item, "abilities", ())
            and getattr(getattr(item, "health_mode", None), "value", None) == "pc"
            and not getattr(item, "unconscious", False)
            and not getattr(item, "dead", False)
        ),
        None,
    )
    if actor is None:
        output_fn("No conscious Investigator can pursue a lead now.")
        return None
    case_index = _choose_index(
        "Investigation case number:",
        tuple(f"{record.name} ({record.case_id})" for record in records),
        input_fn,
        output_fn,
    )
    if case_index is None:
        return None
    record = records[case_index]
    clues = tuple(getattr(record, "clues", ()))
    clue_index = _choose_index(
        "Clue number:",
        tuple(f"{clue.label} ({clue.clue_key})" for clue in clues),
        input_fn,
        output_fn,
    )
    if clue_index is None:
        return None
    return actor.actor_id, record.case_id, clues[clue_index].clue_key


def _choose_streetwise(setup: object, inspection: object, input_fn, output_fn):
    """Select one finite Streetwise question and one sourced method."""
    records = tuple(getattr(setup, "streetwise", ()))
    actor = next((item for item in getattr(inspection, "actors", ()) if (
        "Streetwise" in getattr(item, "feats", ())
        and getattr(getattr(item, "health_mode", None), "value", None) == "pc"
        and not getattr(item, "unconscious", False) and not getattr(item, "dead", False)
    )), None)
    if actor is None or not records:
        output_fn("No conscious Investigator with an authored Streetwise question is available.")
        return None
    index = _choose_index(
        "Streetwise question number:",
        tuple(f"{record.question} ({record.settlement_label})" for record in records), input_fn, output_fn,
    )
    if index is None:
        return None
    mode_index = _choose_index(
        "Streetwise method:",
        ("Recall Knowledge (Society, no time)", "Gather Information (Society, 2 hours)"),
        input_fn, output_fn,
    )
    if mode_index is None:
        return None
    record = records[index]
    return actor.actor_id, record.question_key, ("recall", "gather")[mode_index], record.settlement_key


def _choose_animal_empathy(setup: object, inspection: object, input_fn, output_fn):
    records = tuple(getattr(setup, "animal_empathy", ()))
    actor = next((item for item in getattr(inspection, "actors", ()) if "animal_empathy" in getattr(item, "abilities", ()) and not getattr(item, "unconscious", False) and not getattr(item, "dead", False)), None)
    if actor is None or not records:
        output_fn("No conscious Druid with an authored Animal Empathy question is available.")
        return None
    index = _choose_index("Animal Empathy question number:", tuple(f"{record.question} ({record.attitude}; Will DC {record.will_dc}; Request DC {record.request_dc})" for record in records), input_fn, output_fn)
    if index is None:
        return None
    action = _choose_index("Diplomacy action:", ("Make an Impression", "Request"), input_fn, output_fn)
    if action is None:
        return None
    return actor.actor_id, records[index].question_key, ("make_impression", "request")[action]


def _choose_encounter_actor(
    prompt: str,
    inspection: object,
    actor_id: str | None,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
    *,
    include_actor: bool = False,
) -> str | None:
    """Offer other inspected actors; the engine validates action targeting."""
    targets = tuple(actor for actor in inspection.actors if include_actor or actor.actor_id != actor_id)
    if not targets:
        output_fn("No other encounter actors are available to select.")
        return None
    output_fn(prompt)
    output_fn("The engine checks whether the selected actor is a valid target.")
    index = _choose_index(
        "Target number:",
        [f"{actor.label} ({actor.actor_id})" for actor in targets],
        input_fn,
        output_fn,
    )
    return targets[index].actor_id if index is not None else None


def _choose_refocus_actor(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select an actor for the public Refocus activity.

    The terminal lists the inspected roster and leaves all eligibility checks
    (PC identity, consciousness, focus pool and unresolved recovery state) to
    :meth:`Encounter.refocus`.
    """
    actors = tuple(getattr(inspection, "actors", ()))
    if not actors:
        output_fn("No encounter actors are available to select for Refocus.")
        return None
    output_fn("The engine checks whether the selected actor can Refocus.")
    index = _choose_index(
        "Refocus actor number:",
        [f"{actor.label} ({actor.actor_id})" for actor in actors],
        input_fn,
        output_fn,
    )
    return actors[index].actor_id if index is not None else None


def _choose_downtime_actor_group(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, ...] | None:
    """Collect a unique explicit actor group for a downtime activity."""
    actors = tuple(getattr(inspection, "actors", ()))
    if not actors:
        output_fn("No encounter actors are available for downtime.")
        return None
    output_fn("Select one or more actors by number, separated by commas.")
    output_fn(render_menu([f"{actor.label} ({actor.actor_id})" for actor in actors]))
    raw = _read_line("Actor numbers:", input_fn, output_fn)
    pieces = [piece.strip() for piece in raw.split(",") if piece.strip()]
    if not pieces:
        output_fn("Choose at least one actor.")
        return None
    try:
        numbers = [int(piece) for piece in pieces]
    except ValueError:
        output_fn("Enter actor numbers separated by commas.")
        return None
    if any(number < 1 or number > len(actors) for number in numbers):
        output_fn(f"Choose actor numbers from 1 to {len(actors)}.")
        return None
    if len(set(numbers)) != len(numbers):
        output_fn("Choose each actor only once.")
        return None
    return tuple(actors[number - 1].actor_id for number in numbers)


def _choose_daily_preparations(
    game: "Encounter",
    actor_ids: tuple[str, ...],
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> dict[str, dict[str, str]] | None:
    """Choose each live prepared slot from its finite authored menu."""
    from pf2e.content import get_definition
    from pf2e.preparation import preparation_choices

    selections: dict[str, dict[str, str]] = {}
    for actor_id in actor_ids:
        actor = game._state.creatures[actor_id]
        definition = get_definition(actor.definition_id)
        selected: dict[str, str] = {}
        for slot in actor.prepared_slots:
            choices = preparation_choices(actor, definition, slot)
            if choices == (slot.spell_id,):
                selected[slot.slot_id] = slot.spell_id
                continue
            index = _choose_index(
                f"Daily preparation {slot.slot_id} spell:",
                tuple(spell.replace("_", " ").title() for spell in choices),
                input_fn,
                output_fn,
            )
            if index is None:
                return None
            selected[slot.slot_id] = choices[index]
        selections[actor_id] = selected
    return selections


def _read_integer(
    prompt: str,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> int | None:
    """Read one integer for an explicit downtime fact."""
    raw = _read_line(prompt, input_fn, output_fn).strip()
    try:
        return int(raw)
    except ValueError:
        output_fn("Enter a whole number.")
        return None


def _choose_maneuver_item(
    actor: object | None,
    action_name: str,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    held_items = tuple(getattr(actor, "held_items", ())) if actor is not None else ()
    if not held_items:
        return None
    output_fn(
        f"{action_name} may use a free hand or a held item; the engine checks item traits and hands."
    )
    index = _choose_index(
        "Maneuver option:",
        ("Use a free hand / no weapon", *(f"Held item: {item_id}" for item_id in held_items)),
        input_fn,
        output_fn,
    )
    if index is None or index == 0:
        return None
    return held_items[index - 1]


def _physical_item_name(item_id: str) -> str:
    """Give a runtime item identity a readable name without inspecting rules."""
    definition_name = item_id.rsplit(":", 1)[-1]
    return definition_name.replace("_", " ").title()


def _physical_item_choices(inspection: object) -> tuple[tuple[str, str], ...]:
    """Collect held and ground item identities exposed by inspection.

    The terminal deliberately lists the physical locations verbatim.  The
    encounter engine decides whether a listed item is a compatible weapon,
    within touch range, and otherwise eligible for Runic Weapon.
    """
    choices: list[tuple[str, str]] = []
    seen: set[str] = set()
    for actor in getattr(inspection, "actors", ()):
        actor_label = str(getattr(actor, "label", getattr(actor, "actor_id", "actor")))
        for location, item_ids in (
            ("Held by", getattr(actor, "held_items", ())),
            ("Worn by", getattr(actor, "worn_items", ())),
            ("Carried by", getattr(actor, "stowed_items", ())),
        ):
            for raw_item_id in item_ids:
                item_id = str(raw_item_id)
                if item_id in seen:
                    continue
                seen.add(item_id)
                choices.append(
                    (
                        item_id,
                        f"{location} {actor_label}: {_physical_item_name(item_id)} ({item_id})",
                    )
                )
    for position, item_ids in getattr(inspection, "ground_items", ()):
        coordinate = format_coordinate((position.x, position.y))
        for raw_item_id in item_ids:
            item_id = str(raw_item_id)
            if item_id in seen:
                continue
            seen.add(item_id)
            choices.append(
                (
                    item_id,
                    f"On ground at {coordinate}: {_physical_item_name(item_id)} ({item_id})",
                )
            )
    return tuple(choices)


def _choose_runic_weapon_item(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select an inspected held or ground item for the item-targeted cast."""
    choices = _physical_item_choices(inspection)
    if not choices:
        output_fn("No held or ground physical items are visible for Runic Weapon.")
        return None
    output_fn(
        "Runic Weapon target item (the engine checks weapon eligibility, touch range, and willingness):"
    )
    index = _choose_index(
        "Item number:",
        [label for _item_id, label in choices],
        input_fn,
        output_fn,
    )
    return choices[index][0] if index is not None else None


def _choose_sigil_item(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select a concrete object for Sigil; range remains engine-owned."""
    choices = _physical_item_choices(inspection)
    if not choices:
        output_fn("No carried, worn, or ground physical items are visible for Sigil.")
        return None
    index = _choose_index(
        "Sigil item number:", [label for _item_id, label in choices], input_fn, output_fn,
    )
    return choices[index][0] if index is not None else None


def _choose_ground_item(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select a literal loose item; the engine verifies range and eligibility."""
    choices = tuple(
        (item_id, label) for item_id, label in _physical_item_choices(inspection)
        if label.startswith("On ground at ")
    )
    if not choices:
        output_fn("No loose unattended ground item is visible for Telekinetic Projectile.")
        return None
    index = _choose_index("Ground item number:", [label for _item_id, label in choices], input_fn, output_fn)
    return choices[index][0] if index is not None else None


def _choose_held_item(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select an item held by the active actor for a literal self procedure."""
    active_id = getattr(inspection, "turn_actor_id", None)
    actor = next(
        (entry for entry in getattr(inspection, "actors", ()) if entry.actor_id == active_id),
        None,
    )
    held = tuple(getattr(actor, "held_items", ())) if actor is not None else ()
    if not held:
        output_fn("The active actor holds no item.")
        return None
    index = _choose_index(
        "Held item:", [_physical_item_name(str(item_id)) + f" ({item_id})" for item_id in held],
        input_fn, output_fn,
    )
    return str(held[index]) if index is not None else None


def _choose_escape_inputs(
    inspection: object,
    engine_options: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, str, str | None] | None:
    """Collect an inspected impediment and a check method for engine validation."""
    actor = next(
        (item for item in inspection.actors if item.actor_id == engine_options.actor_id),
        None,
    )
    effects = tuple(getattr(actor, "condition_effects", ())) if actor is not None else ()
    if not effects:
        output_fn("No condition effects are visible on the acting creature for Escape.")
        return None
    effect_labels = []
    for effect in effects:
        kind = str(effect.kind).replace("_", " ")
        if effect.kind in {"clumsy", "drained", "enfeebled", "frightened", "sickened", "stupefied"} or effect.value != 1:
            kind += f" {effect.value}"
        source = _actor_label(inspection, effect.source_actor_id)
        effect_labels.append(f"{kind} from {source} ({effect.effect_id})")
    output_fn("The engine checks whether the selected effect can be escaped from.")
    effect_index = _choose_index("Condition effect number:", effect_labels, input_fn, output_fn)
    if effect_index is None:
        return None

    methods = (("athletics", "Athletics"), ("acrobatics", "Acrobatics"), ("unarmed_attack", "Unarmed attack"))
    method_index = _choose_index(
        "Escape check method:",
        [label for _, label in methods],
        input_fn,
        output_fn,
    )
    if method_index is None:
        return None
    method, _ = methods[method_index]
    attack_id = None
    if method == "unarmed_attack":
        strikes = tuple(getattr(engine_options, "strikes", ()))
        if strikes:
            output_fn("Select an attack profile; the engine verifies that it is an available unarmed attack.")
            attack_index = _choose_index(
                "Unarmed profile number:",
                [f"{strike.name} ({strike.attack_id})" for strike in strikes],
                input_fn,
                output_fn,
            )
            if attack_index is None:
                return None
            attack_id = strikes[attack_index].attack_id
    return effects[effect_index].effect_id, method, attack_id


def _choose_assurance_escape_input(
    inspection: object,
    engine_options: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> str | None:
    """Select an inspected impediment for the fixed Athletics Escape intent."""
    actor = next(
        (item for item in inspection.actors if item.actor_id == engine_options.actor_id),
        None,
    )
    effects = tuple(getattr(actor, "condition_effects", ())) if actor is not None else ()
    if not effects:
        output_fn("No condition effects are visible on the acting creature for Escape.")
        return None
    effect_labels = []
    for effect in effects:
        kind = str(effect.kind).replace("_", " ")
        if effect.kind in {"clumsy", "drained", "enfeebled", "frightened", "sickened", "stupefied"} or effect.value != 1:
            kind += f" {effect.value}"
        source = _actor_label(inspection, effect.source_actor_id)
        effect_labels.append(f"{kind} from {source} ({effect.effect_id})")
    output_fn("The engine checks whether the selected effect can be escaped from with Athletics.")
    effect_index = _choose_index("Condition effect number:", effect_labels, input_fn, output_fn)
    return effects[effect_index].effect_id if effect_index is not None else None


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
) -> (
    tuple[str, str | None, int, str | None, bool | None]
    | tuple[str, None, int, str | None, None, str]
    | tuple[str, None, int, None, None, None, Position, str, str | None]
    | tuple[str, None, int, None, None, None, Position, str, str | None, str]
    | None
):
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
    is_runic_weapon = spell.spell_id == "runic_weapon"

    if spell.spell_id == "light":
        return _choose_light_inputs(spell, inspection, input_fn, output_fn)

    target_modes = tuple(spell.target_options)
    if not target_modes:
        output_fn("The engine did not provide a selectable target or casting mode for this spell.")
        return None
    mode_index = _choose_index(
        "Casting mode:",
        [
            f"{option.actions} action" + ("s" if option.actions != 1 else "")
            for option in target_modes
        ],
        input_fn,
        output_fn,
    )
    if mode_index is None:
        return None
    target_mode = target_modes[mode_index]

    slot_id = None
    use_arcane_bond = False
    # Focus spells use their actor-level pool; there is no rank-slot choice.
    # A pool resource carries rank 0 internally, while the spell's source
    # access carries its real rank, so forwarding it as ``slot_id`` would
    # incorrectly ask the normal prepared-slot validator for rank 0.
    if spell.slots and any(candidate_id != "actor_focus_pool" for candidate_id, _source in spell.slots):
        slot_index = _choose_index(
            "Prepared slot:",
            [f"{slot_id} ({source})" for slot_id, source in spell.slots],
            input_fn,
            output_fn,
        )
        if slot_index is None:
            return None
        slot_id, slot_source = spell.slots[slot_index]
        use_arcane_bond = slot_source.endswith("; Arcane Bond")

    if is_runic_weapon:
        item_id = _choose_runic_weapon_item(inspection, input_fn, output_fn)
        if item_id is None:
            return None
        # The item selector supplies the target identity; the engine owns all
        # eligibility, range, commitment, and willingness checks.
        return spell.spell_id, None, target_mode.actions, slot_id, None, item_id

    if spell.spell_id == "sigil":
        kind = _choose_index(
            "Sigil target:", ("Creature", "Carried or worn item"), input_fn, output_fn,
        )
        if kind is None:
            return None
        visibility = _choose_index(
            "Sigil visibility:", ("Visible", "Invisible"), input_fn, output_fn,
        )
        if visibility is None:
            return None
        mode = ("visible", "invisible")[visibility]
        if kind == 0:
            target_id = _choose_target(
                target_mode.targets, inspection, input_fn, output_fn,
                prompt="Sigil creature target:",
            )
            return (spell.spell_id, target_id, target_mode.actions, slot_id, None, {"spell_mode": mode}) if target_id is not None else None
        item_id = _choose_sigil_item(inspection, input_fn, output_fn)
        return (spell.spell_id, None, target_mode.actions, slot_id, None, {"spell_mode": mode, "item_id": item_id}) if item_id is not None else None

    if spell.spell_id == "telekinetic_projectile":
        target_id = _choose_target(
            target_mode.targets, inspection, input_fn, output_fn,
            prompt="Telekinetic Projectile target:",
        )
        if target_id is None:
            return None
        item_id = _choose_ground_item(inspection, input_fn, output_fn)
        if item_id is None:
            return None
        return spell.spell_id, target_id, target_mode.actions, slot_id, None, item_id

    if spell.spell_id == "force_barrage":
        shard_targets: list[str] = []
        for shard_number in range(1, target_mode.actions + 1):
            target_id = _choose_target(
                target_mode.targets, inspection, input_fn, output_fn,
                prompt=f"Force Barrage shard {shard_number} target:",
            )
            if target_id is None:
                return None
            shard_targets.append(target_id)
        if use_arcane_bond:
            return spell.spell_id, None, target_mode.actions, slot_id, None, tuple(shard_targets), {"use_arcane_bond": True}
        return spell.spell_id, None, target_mode.actions, slot_id, None, tuple(shard_targets)

    if spell.spell_id == "electric_arc":
        target_ids: list[str] = []
        for target_number in range(1, 3):
            target_id = _choose_target(
                tuple(target for target in target_mode.targets if target not in target_ids),
                inspection, input_fn, output_fn,
                prompt=f"Electric Arc target {target_number} (or cancel after the first):",
            )
            if target_id is None:
                break
            target_ids.append(target_id)
        if not target_ids:
            return None
        return spell.spell_id, None, target_mode.actions, slot_id, None, tuple(target_ids)

    if spell.spell_id == "breathe_fire":
        direction_index = _choose_index(
            "Breathe Fire direction:",
            ("North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"),
            input_fn, output_fn,
        )
        if direction_index is None:
            return None
        direction = (
            Position(0, 1), Position(1, 1), Position(1, 0), Position(1, -1),
            Position(0, -1), Position(-1, -1), Position(-1, 0), Position(-1, 1),
        )[direction_index]
        if use_arcane_bond:
            return spell.spell_id, None, target_mode.actions, slot_id, None, direction, {"use_arcane_bond": True}
        return spell.spell_id, None, target_mode.actions, slot_id, None, direction

    spell_mode = None
    if spell.spell_id == "ignition":
        mode_index = _choose_index(
            "Ignition form:", ("Ranged (2d4 fire)", "Melee (2d6 fire)"), input_fn, output_fn,
        )
        if mode_index is None:
            return None
        spell_mode = ("ranged", "melee")[mode_index]
    elif spell.spell_id == "gouging_claw":
        mode_index = _choose_index(
            "Gouging Claw damage type:", ("Piercing", "Slashing"), input_fn, output_fn,
        )
        if mode_index is None:
            return None
        spell_mode = ("piercing", "slashing")[mode_index]
    elif spell.spell_id == "sigil":
        mode_index = _choose_index(
            "Sigil visibility:", ("Visible", "Invisible"), input_fn, output_fn,
        )
        if mode_index is None:
            return None
        spell_mode = ("visible", "invisible")[mode_index]

    if spell.spell_id in {"shield", "sure_strike", "angelic_halo", "courageous_anthem", "detect_magic"}:
        return spell.spell_id, None, target_mode.actions, slot_id, None

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
    if spell_mode is not None:
        return spell.spell_id, target_id, target_mode.actions, slot_id, include_self, {"spell_mode": spell_mode}
    if use_arcane_bond:
        return spell.spell_id, target_id, target_mode.actions, slot_id, include_self, {"use_arcane_bond": True}
    return spell.spell_id, target_id, target_mode.actions, slot_id, include_self


def _light_orb_choices(
    inspection: object,
    caster_actor_id: str | None,
) -> tuple[tuple[str, str], ...]:
    """Return inspected Light orbs owned by the active caster."""
    choices: list[tuple[str, str]] = []
    actors_by_id = {
        str(actor.actor_id): actor for actor in getattr(inspection, "actors", ())
    }
    for orb in getattr(inspection, "light_orbs", ()):
        if caster_actor_id is not None and getattr(orb, "caster_actor_id", None) != caster_actor_id:
            continue
        stable_id = str(getattr(orb, "stable_id", getattr(orb, "orb_id", "")))
        if not stable_id:
            continue
        attached_id = getattr(orb, "attached_actor_id", None)
        if attached_id is not None:
            carrier = actors_by_id.get(str(attached_id))
            location = (
                f"attached to {carrier.label}"
                if carrier is not None
                else f"attached to {attached_id}"
            )
        else:
            point = getattr(orb, "point", None)
            location = (
                f"at {format_coordinate((point.x, point.y))}"
                if point is not None
                else "at an unavailable location"
            )
        choices.append(
            (
                stable_id,
                f"{stable_id} ({getattr(orb, 'color', 'white')}; {location})",
            )
        )
    return tuple(choices)


def _choose_light_orb(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
    *,
    prompt: str,
) -> str | None:
    """Select one active orb for a Sustain or Dismiss command."""
    choices = _light_orb_choices(inspection, getattr(inspection, "turn_actor_id", None))
    if not choices:
        output_fn("The engine did not provide an active Light orb owned by this actor.")
        return None
    index = _choose_index(prompt, [label for _orb_id, label in choices], input_fn, output_fn)
    return choices[index][0] if index is not None else None


def _choose_light_sustain_inputs(
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> tuple[str, Position | None, str | None] | None:
    """Collect one orb and optional Sustain point/carrier intent."""
    orb_id = _choose_light_orb(
        inspection,
        input_fn,
        output_fn,
        prompt="Light orb to Sustain:",
    )
    if orb_id is None:
        return None
    raw_point = _read_line(
        "Sustain point (press Enter to keep current point or detach carrier):",
        input_fn,
        output_fn,
    ).strip()
    point: Position | None = None
    attachment_actor_id: str | None = None
    if raw_point:
        try:
            x, y = parse_coordinate(
                raw_point,
                width=getattr(inspection, "map_width", 7),
                height=getattr(inspection, "map_height", 5),
            )
        except ValueError as exc:
            output_fn(str(exc))
            return None
        point = Position(x=x, y=y)
        carriers = tuple(
            actor
            for actor in getattr(inspection, "actors", ())
            if getattr(actor, "position", None) == point
        )
        if carriers:
            output_fn("Optional Light carrier at this point (the engine asks for willingness):")
            carrier_index = _choose_index(
                "Carrier number:",
                (
                    "Leave the orb at this point",
                    *(f"Attach to {actor.label} ({actor.actor_id})" for actor in carriers),
                ),
                input_fn,
                output_fn,
            )
            if carrier_index is None:
                return None
            if carrier_index > 0:
                attachment_actor_id = carriers[carrier_index - 1].actor_id
    return orb_id, point, attachment_actor_id


def _choose_light_inputs(
    spell: object,
    inspection: object,
    input_fn: Callable[[], str],
    output_fn: Callable[[str], object],
) -> (
    tuple[str, None, int, None, None, None, Position, str, str | None]
    | tuple[str, None, int, None, None, None, Position, str, str | None, str]
    | None
):
    """Collect Light's point, color, and optional carrier intent.

    The terminal validates coordinate spelling and presents actors occupying
    the selected square. The encounter engine remains responsible for range,
    action, target, and willingness legality.
    """
    action_costs = tuple(getattr(spell, "action_costs", ()))
    if not action_costs:
        output_fn("The engine did not provide a supported action mode for Light.")
        return None
    if len(action_costs) == 1:
        actions = action_costs[0]
    else:
        mode_index = _choose_index(
            "Casting mode:",
            [f"{actions} action" + ("s" if actions != 1 else "") for actions in action_costs],
            input_fn,
            output_fn,
        )
        if mode_index is None:
            return None
        actions = action_costs[mode_index]

    replacement_orb_id: str | None = None
    owned_orbs = _light_orb_choices(
        inspection,
        getattr(inspection, "turn_actor_id", None),
    )
    if len(owned_orbs) >= 4:
        output_fn(
            "Four active Light orbs are present; choose the owned orb to replace "
            "(the engine validates the replacement)."
        )
        replacement_index = _choose_index(
            "Light orb to replace:",
            [label for _orb_id, label in owned_orbs],
            input_fn,
            output_fn,
        )
        if replacement_index is None:
            return None
        replacement_orb_id = owned_orbs[replacement_index][0]

    raw_point = _read_line("Light point (for example C3):", input_fn, output_fn)
    try:
        x, y = parse_coordinate(
            raw_point,
            width=getattr(inspection, "map_width", 7),
            height=getattr(inspection, "map_height", 5),
        )
    except ValueError as exc:
        output_fn(str(exc))
        return None
    point = Position(x=x, y=y)

    raw_color = _read_line("Light color [white]:", input_fn, output_fn).strip()
    color = raw_color or "white"

    carriers = tuple(
        actor
        for actor in getattr(inspection, "actors", ())
        if getattr(actor, "position", None) == point
    )
    attachment_actor_id: str | None = None
    if carriers:
        output_fn("Optional Light carrier at this point (the engine asks for willingness):")
        carrier_index = _choose_index(
            "Carrier number:",
            (
                "Leave the orb at this point",
                *(f"Attach to {actor.label} ({actor.actor_id})" for actor in carriers),
            ),
            input_fn,
            output_fn,
        )
        if carrier_index is None:
            return None
        if carrier_index > 0:
            attachment_actor_id = carriers[carrier_index - 1].actor_id

    result = (
        spell.spell_id,
        None,
        actions,
        None,
        None,
        None,
        point,
        color,
        attachment_actor_id,
    )
    if replacement_orb_id is None:
        return result
    return (*result, replacement_orb_id)


def _interact_label(mode: str, item_id: str) -> str:
    verb = {
        "draw": "Draw",
        "stow": "Stow",
        "retrieve": "Retrieve",
    }.get(mode, mode.replace("_", " ").title())
    return f"{verb}: {item_id}"


def _run_command(game: Encounter, command: object, output_fn: Callable[[str], object]) -> None:
    _run_result(game.execute(command), output_fn)


def _run_result(result: object, output_fn: Callable[[str], object]) -> None:
    """Render an already-resolved public activity result."""
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
    from pf2e.content import (
        ANGELIC_FIRST_CAST_SETUP,
        ANGELIC_NEXT_ENCOUNTER_SETUP,
        BOMBER_ALCHEMIST_NEXT_SETUP,
        BOMBER_ALCHEMIST_SETUP,
        S1_SETUP,
        get_setup,
    )
    from pf2e.encounter import Encounter
    from pf2e.model import (
        Cast,
        LingeringComposition,
        Choose,
        Crawl,
        EndTurn,
        Flee,
        Interact,
        Position,
        Release,
        ResultStatus,
        Stand,
        Step,
        Stride,
        Strike,
        QuickBomber,
        QuickAlchemy,
        ActivateAlchemy,
        TakeCover,
        RaiseShield,
        Sustain,
        Dismiss,
        ViciousSwing,
        LayOnHands,
        SuppressAura,
        ResumeAura,
    )
    from pf2e.skill_actions import Demoralize, Escape, Feint, Grapple, Trip, TumbleThrough
    from pf2e.barbarian import Rage
    from pf2e.investigator import BattleMedicine, DeviseStratagem, PersonOfInterest, RecallKnowledge
    from pf2e.swashbuckler import ConfidentFinisher
    from pf2e.ranger import HuntPrey, HuntedShot, HunterAim
    from pf2e.fighter import BrutishShove, CombatGrab, IntimidatingStrike, SnaggingStrike, SuddenCharge
    from pf2e.w4_offensive import DoubleSlice, ExactingStrike, TwinFeint, TwinTakedown
    from pf2e.martial_defense import CraneStance, DismissCraneStance, DuelingParry, PointBlankStance

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
                if getattr(setup, "setup_id", None) == ANGELIC_FIRST_CAST_SETUP.setup_id:
                    output_fn(
                        "Encounter finished. Next Encounter, Refocus, Record Rested Eligibility, "
                        "Daily Preparation, Restart, load, save, or quit."
                    )
                else:
                    output_fn(
                        "Encounter finished. Refocus, Record Rested Eligibility, Daily Preparation, "
                        "Restart, load a save, save this result, or quit."
                    )

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
                        loaded_setup_id = getattr(getattr(game, "_state", None), "setup_id", None)
                        if loaded_setup_id is not None:
                            setup = get_setup(loaded_setup_id)
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
                include_refocus=not inspection.in_progress and not is_s1,
                include_next_encounter=(
                    not inspection.in_progress
                    and getattr(setup, "setup_id", None) in {
                        ANGELIC_FIRST_CAST_SETUP.setup_id,
                        BOMBER_ALCHEMIST_SETUP.setup_id,
                    }
                ),
                include_downtime=not inspection.in_progress and not is_s1,
                include_examination=(
                    not inspection.in_progress
                    and not is_s1
                    and bool(getattr(setup, "examinations", ()))
                    and any(
                        "investigator_forensic_acumen" in getattr(actor, "abilities", ())
                        and getattr(getattr(actor, "health_mode", None), "value", None) == "pc"
                        and not getattr(actor, "unconscious", False)
                        and not getattr(actor, "dead", False)
                        for actor in inspection.actors
                    )
                ),
                include_lead=(
                    not inspection.in_progress
                    and not is_s1
                    and bool(getattr(setup, "investigations", ()))
                    and any(
                        "investigator_on_the_case" in getattr(actor, "abilities", ())
                        and getattr(getattr(actor, "health_mode", None), "value", None) == "pc"
                        and not getattr(actor, "unconscious", False)
                        and not getattr(actor, "dead", False)
                        for actor in inspection.actors
                    )
                ),
                include_streetwise=(
                    not inspection.in_progress and not is_s1
                    and bool(getattr(setup, "streetwise", ()))
                    and any(
                        "Streetwise" in getattr(actor, "feats", ())
                        and getattr(getattr(actor, "health_mode", None), "value", None) == "pc"
                        and not getattr(actor, "unconscious", False) and not getattr(actor, "dead", False)
                        for actor in inspection.actors
                    )
                ),
                include_animal_empathy=(
                    not inspection.in_progress and not is_s1
                    and bool(getattr(setup, "animal_empathy", ()))
                    and any("animal_empathy" in getattr(actor, "abilities", ()) and not getattr(actor, "unconscious", False) and not getattr(actor, "dead", False) for actor in inspection.actors)
                ),
                include_spell_substitution=(
                    not inspection.in_progress and not is_s1
                    and any("spell_substitution" in getattr(actor, "abilities", ()) for actor in inspection.actors)
                ),
                include_oracle_life_mode=(
                    not inspection.in_progress and not is_s1
                    and any("life_oracle" in getattr(actor, "abilities", ()) for actor in inspection.actors)
                ),
            )
            output_fn(render_menu([label for _, label in menu_entries]))
            choice_text = _read_line("Choice:", input_fn, output_fn)
            try:
                choice = parse_menu_choice(choice_text, len(menu_entries))
            except ValueError as exc:
                output_fn(str(exc))
                continue
            action_id = menu_entries[choice - 1][0]

            if not inspection.in_progress and action_id not in {
                "save", "load", "restart", "quit", "refocus", "next_encounter",
                "record_rested", "daily_prepare", "forensic_examine",
                "pursue_lead", "streetwise", "animal_empathy", "spell_substitution", "interrupt_spell_substitution", "oracle_life_mode",
            }:
                output_fn("The encounter is finished; choose an available recovery or encounter action, Save, Load, Restart, or Quit.")
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
            elif action_id == "quick_jump":
                try:
                    from pf2e.skill_actions import QuickJump

                    raw_path = _read_line(
                        "Quick Jump path, in order (for example B2 C2 D2):",
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
                        QuickJump(path=tuple(Position(x=x, y=y) for x, y in points)),
                        output_fn,
                    )
                except ValueError as exc:
                    output_fn(str(exc))
            elif action_id == "tumble_through":
                try:
                    raw_path = _read_line(
                        "Tumble Through path, in order (for example B2 C2 D2):",
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
                        TumbleThrough(path=tuple(Position(x=x, y=y) for x, y in points)),
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
                        use_intelligence = None
                        if (
                            target_id == getattr(engine_options, "investigator_stratagem_target_id", None)
                            and getattr(
                                next(
                                    (option for option in engine_options.strikes if option.attack_id == attack_id),
                                    None,
                                ),
                                "intelligence_substitution_available",
                                False,
                            )
                        ):
                            intelligence_choice = _choose_index(
                                "Devise attack ability:",
                                (
                                    "Use Intelligence (Strategic Strike +1d6 precision)",
                                    "Use the weapon's printed ability",
                                ),
                                input_fn,
                                output_fn,
                            )
                            if intelligence_choice is not None:
                                use_intelligence = intelligence_choice == 0
                        _run_command(
                            game,
                            Strike(
                                target_id=target_id,
                                attack_id=attack_id,
                                damage_type=damage_type,
                                nonlethal=nonlethal,
                                use_intelligence=use_intelligence,
                            ),
                            output_fn,
                        )
            elif action_id in {"exacting_strike", "double_slice", "twin_takedown", "twin_feint"}:
                from pf2e.content import get_definition
                from pf2e.model import PairedStrikeSelection

                actor = game._state.creatures.get(engine_options.actor_id or "")
                definition = get_definition(actor.definition_id) if actor is not None else None
                choices = tuple(
                    option for option in engine_options.strikes
                    if definition is not None and any(
                        attack.attack_id == option.attack_id
                        and "melee" in attack.traits
                        and (
                            action_id == "exacting_strike"
                            or (
                                attack.item_id is not None
                                and attack.item_id in actor.held_items
                                and attack.hands_required == 1
                            )
                        )
                        for attack in definition.attacks
                    )
                )
                strike_inputs = _choose_strike_inputs(choices, inspection, input_fn, output_fn)
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    selection = PairedStrikeSelection(target_id, attack_id, damage_type, nonlethal)
                    if action_id == "exacting_strike":
                        _run_command(game, ExactingStrike(target_id, attack_id, damage_type, nonlethal), output_fn)
                    elif action_id == "double_slice":
                        _run_command(game, DoubleSlice(selection), output_fn)
                    elif action_id == "twin_takedown":
                        _run_command(game, TwinTakedown(selection), output_fn)
                    else:
                        _run_command(game, TwinFeint(selection), output_fn)
            elif action_id == "sudden_charge":
                try:
                    first_raw = _read_line(
                        "Sudden Charge first Stride path (for example B2 C2):",
                        input_fn, output_fn,
                    )
                    second_raw = _read_line(
                        "Sudden Charge second Stride path (for example D2 E2):",
                        input_fn, output_fn,
                    )
                    first = tuple(Position(x=x, y=y) for x, y in parse_path(
                        first_raw, width=inspection.map_width, height=inspection.map_height,
                    ))
                    second = tuple(Position(x=x, y=y) for x, y in parse_path(
                        second_raw, width=inspection.map_width, height=inspection.map_height,
                    ))
                    # The optional subordinate Strike is made after both
                    # paths, so the ordinary pre-move strike menu may not yet
                    # show a target reached by the second Stride.  Offer only
                    # the acting creature's ordinary melee attacks and all
                    # opposing living actors; Encounter remains authoritative
                    # for the final range/equipment validation.
                    from pf2e.content import get_definition

                    actor = next(item for item in inspection.actors if item.actor_id == inspection.turn_actor_id)
                    attacks = [
                        attack for attack in get_definition(
                            game._state.creatures[actor.actor_id].definition_id
                        ).attacks
                        if "melee" in attack.traits
                    ]
                    attack_index = _choose_index(
                        "Weapon / attack number:",
                        [f"{attack.name} ({attack.attack_id})" for attack in attacks],
                        input_fn, output_fn,
                    )
                    if attack_index is None:
                        _run_command(game, SuddenCharge(first, second), output_fn)
                    else:
                        attack = attacks[attack_index]
                        targets = tuple(
                            item.actor_id for item in inspection.actors
                            if item.team != actor.team and not item.defeated and not item.dead
                        )
                        target_index = _choose_index(
                            f"{attack.name} target:",
                            [f"{_actor_label(inspection, target_id)} ({target_id})" for target_id in targets],
                            input_fn, output_fn,
                        )
                        if target_index is None:
                            _run_command(game, SuddenCharge(first, second), output_fn)
                        else:
                            target_id = targets[target_index]
                            intent_index = _choose_index(
                                "Damage intent:",
                                ("Use attack default (lethal)", "Lethal damage", "Nonlethal damage"),
                                input_fn, output_fn,
                            )
                            if intent_index is None:
                                _run_command(game, SuddenCharge(first, second), output_fn)
                            else:
                                _run_command(game, SuddenCharge(first, second, target_id, attack.attack_id), output_fn)
                except ValueError as exc:
                    output_fn(str(exc))
            elif action_id == "quick_alchemy":
                from pf2e.alchemy_content import FORMULAS_BY_ID

                known_formula_ids = game._state.alchemy_states[engine_options.actor_id].known_formula_ids
                formula_index = _choose_index(
                    "Quick Alchemy formula:",
                    tuple(FORMULAS_BY_ID[formula_id].name for formula_id in known_formula_ids),
                    input_fn, output_fn,
                )
                if formula_index is not None:
                    _run_command(game, QuickAlchemy("create_consumable", known_formula_ids[formula_index]), output_fn)
            elif action_id == "activate_alchemy":
                from pf2e.alchemy_content import FORMULAS_BY_ID

                actor = game._state.creatures[engine_options.actor_id]
                held = tuple(
                    item_id for item_id in actor.held_items
                    if item_id in game._state.infused_alchemy_items
                    and game._state.infused_alchemy_items[item_id].formula_id in FORMULAS_BY_ID
                    and FORMULAS_BY_ID[game._state.infused_alchemy_items[item_id].formula_id].category != "bomb"
                )
                item_index = _choose_index(
                    "Held alchemy item:",
                    tuple(
                        game._state.infused_alchemy_items[item_id].formula_id.replace("_", " ")
                        for item_id in held
                    ),
                    input_fn, output_fn,
                )
                if item_index is not None:
                    item_id = held[item_index]
                    formula_id = game._state.infused_alchemy_items[item_id].formula_id
                    if formula_id in {"bestial_mutagen_lesser", "cognitive_mutagen_lesser", "juggernaut_mutagen_lesser", "giant_centipede_venom"}:
                        temporary_hp_choice = None
                        if formula_id == "juggernaut_mutagen_lesser" and actor.temporary_hp > 0:
                            choice_index = _choose_index(
                                "Juggernaut temporary-HP pool:",
                                ("Keep existing temporary HP", "Gain Juggernaut's temporary HP"),
                                input_fn, output_fn,
                            )
                            if choice_index is not None:
                                temporary_hp_choice = ("keep_existing", "gain_new")[choice_index]
                        if formula_id != "juggernaut_mutagen_lesser" or actor.temporary_hp == 0 or temporary_hp_choice is not None:
                            _run_command(game, ActivateAlchemy(item_id, temporary_hp_choice=temporary_hp_choice), output_fn)
                    else:
                        recipient_id = _choose_target(
                            tuple(
                                candidate.actor_id for candidate in inspection.actors
                                if not candidate.dead and not candidate.unconscious
                            ),
                            inspection, input_fn, output_fn, prompt="Alchemy recipient:",
                        )
                        if recipient_id is not None:
                            _run_command(game, ActivateAlchemy(item_id, recipient_id), output_fn)
            elif action_id == "quick_bomber":
                from pf2e.alchemy import bomber_bomb_range_increment
                from pf2e.alchemist_content import admitted_bomber_bomb_facts
                from pf2e.alchemy_content import FORMULAS_BY_ID
                from pf2e.content import get_definition
                from pf2e.space import grid_distance_feet

                actor = game._state.creatures[engine_options.actor_id]
                available_formula_ids = tuple(dict.fromkeys(
                    game._state.item_instances[item_id].definition_id
                    for item_id in actor.held_items + actor.stowed_items
                    if item_id in game._state.item_instances
                    and admitted_bomber_bomb_facts(
                        game._state.item_instances[item_id].definition_id,
                        character_level=game._state.alchemy_states[actor.actor_id].character_level,
                    ) is not None
                ))
                formula_index = _choose_index(
                    "Prepared bomb:", tuple(
                        FORMULAS_BY_ID[formula_id].name for formula_id in available_formula_ids
                    ), input_fn, output_fn,
                )
                if formula_index is not None:
                    formula_id = available_formula_ids[formula_index]
                    attack = next(
                        candidate for candidate in get_definition(actor.definition_id).attacks
                        if candidate.item_id == formula_id
                    )
                    alchemy_state = game._state.alchemy_states.get(actor.actor_id)
                    ordinary_increment = attack.range_increment_ft or attack.range_ft
                    max_range_ft = (
                        bomber_bomb_range_increment(alchemy_state, ordinary_increment) * 6
                        if alchemy_state is not None
                        else (attack.max_range_ft or 0)
                    )
                    target_ids = tuple(
                        candidate.actor_id for candidate in inspection.actors
                        if candidate.actor_id != actor.actor_id
                        and not candidate.defeated
                        and grid_distance_feet(
                            actor.position,
                            game._state.creatures[candidate.actor_id].position,
                        ) <= max_range_ft
                    )
                    target_id = _choose_target(target_ids, inspection, input_fn, output_fn)
                    if target_id is not None:
                        _run_command(game, QuickBomber(target_id, formula_id), output_fn)
            elif action_id == "devise_stratagem":
                target_id = _choose_devise_target(
                    inspection,
                    engine_options.actor_id,
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    _run_command(
                        game,
                        DeviseStratagem(
                            target_id=target_id,
                            free_action=_devise_is_free(
                                game, engine_options.actor_id, target_id,
                            ),
                        ),
                        output_fn,
                    )
            elif action_id == "known_weaknesses":
                target_id = _choose_recall_target(
                    inspection,
                    getattr(engine_options, "recall_knowledge_targets", ()),
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    _run_command(
                        game,
                        DeviseStratagem(
                            target_id=target_id,
                            known_weaknesses=True,
                            free_action=_devise_is_free(
                                game, engine_options.actor_id, target_id,
                            ),
                        ),
                        output_fn,
                    )
            elif action_id == "recall_knowledge":
                target_id = _choose_recall_target(
                    inspection,
                    getattr(engine_options, "recall_knowledge_targets", ()),
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    from pf2e.content import get_setup

                    records = tuple(getattr(get_setup(game._state.setup_id), "knowledge", ()))
                    record = next(
                        (
                            item for item in records
                            if getattr(item, "subject_actor_id", None) in {None, target_id}
                            and (
                                getattr(item, "subject_definition_id", None) is None
                                or item.subject_definition_id == game._state.creatures[target_id].definition_id
                            )
                        ),
                        None,
                    )
                    if record is None:
                        output_fn("No authored Recall Knowledge question is available for that subject.")
                    else:
                        output_fn(f"Question: {record.question}")
                        skill = _choose_recall_skill(record, input_fn, output_fn)
                        if skill is not None:
                            from pf2e.content import get_definition
                            actor = game._state.creatures.get(inspection.turn_actor_id or "")
                            definition = get_definition(actor.definition_id) if actor is not None else None
                            use_assurance = False
                            if definition is not None and f"assurance_{skill}" in definition.abilities:
                                method = _choose_index(
                                    "Recall Knowledge method:",
                                    ("Roll check", f"Use Assurance ({skill.title()})"),
                                    input_fn, output_fn,
                                )
                                if method is None:
                                    continue
                                use_assurance = method == 1
                            _run_command(
                                game,
                                RecallKnowledge(
                                    subject_key=record.subject_key,
                                    question=record.question,
                                    skill=skill,
                                    target_id=target_id,
                                    use_assurance=use_assurance,
                                ),
                                output_fn,
                            )
            elif action_id == "forensic_examine":
                selected = _choose_forensic_examination(
                    setup,
                    inspection,
                    input_fn,
                    output_fn,
                )
                if selected is not None:
                    actor_id, examination_key = selected
                    _run_result(
                        game.forensic_examine(actor_id, examination_key),
                        output_fn,
                    )
            elif action_id == "pursue_lead":
                selected = _choose_pursue_lead(
                    setup,
                    game,
                    inspection,
                    input_fn,
                    output_fn,
                )
                if selected is not None:
                    actor_id, case_id, clue_key = selected
                    _run_result(
                        game.pursue_lead(actor_id, case_id, clue_key),
                        output_fn,
                    )
            elif action_id == "streetwise":
                selected = _choose_streetwise(setup, inspection, input_fn, output_fn)
                if selected is not None:
                    actor_id, question_key, mode, settlement_key = selected
                    _run_result(
                        game.streetwise(actor_id, question_key, mode=mode, settlement_key=settlement_key),
                        output_fn,
                    )
            elif action_id == "animal_empathy":
                selected = _choose_animal_empathy(setup, inspection, input_fn, output_fn)
                if selected is not None:
                    actor_id, question_key, action = selected
                    _run_result(game.animal_empathy(actor_id, question_key, action=action), output_fn)
            elif action_id == "battle_medicine":
                target_id = _choose_target(
                    getattr(engine_options, "battle_medicine_targets", ()),
                    inspection,
                    input_fn,
                    output_fn,
                    prompt="Battle Medicine target:",
                )
                if target_id is not None:
                    from pf2e.content import get_definition

                    actor = game._state.creatures.get(inspection.turn_actor_id or "")
                    definition = get_definition(actor.definition_id) if actor is not None else None
                    use_assurance = False
                    if definition is not None and "assurance_medicine" in definition.abilities:
                        method = _choose_index(
                            "Battle Medicine method:",
                            ("Roll check", "Use Assurance (Medicine)"),
                            input_fn,
                            output_fn,
                        )
                        if method is None:
                            continue
                        use_assurance = method == 1
                    _run_command(
                        game,
                        BattleMedicine(target_id=target_id, use_assurance=use_assurance),
                        output_fn,
                    )
            elif action_id == "person_of_interest":
                target_id = _choose_target(
                    getattr(engine_options, "person_of_interest_targets", ()),
                    inspection,
                    input_fn,
                    output_fn,
                    prompt="Person of Interest target:",
                )
                if target_id is not None:
                    _run_command(game, PersonOfInterest(target_id), output_fn)
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
            elif action_id == "intimidating_strike":
                from pf2e.content import get_definition

                acting_actor = game._state.creatures.get(engine_options.actor_id or "")
                melee_attack_ids = {
                    attack.attack_id
                    for attack in get_definition(acting_actor.definition_id).attacks
                    if "melee" in attack.traits
                } if acting_actor is not None else set()
                strike_inputs = _choose_strike_inputs(
                    tuple(
                        option for option in engine_options.strikes
                        if option.attack_id in melee_attack_ids
                    ),
                    inspection,
                    input_fn,
                    output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    _run_command(
                        game,
                        IntimidatingStrike(
                            target_id=target_id,
                            attack_id=attack_id,
                            damage_type=damage_type,
                            nonlethal=nonlethal,
                        ),
                        output_fn,
                    )
            elif action_id in {"snagging_strike", "combat_grab"}:
                from pf2e.content import get_definition

                acting_actor = game._state.creatures.get(engine_options.actor_id or "")
                melee_attack_ids = {
                    attack.attack_id for attack in get_definition(acting_actor.definition_id).attacks
                    if "melee" in attack.traits
                } if acting_actor is not None else set()
                strike_inputs = _choose_strike_inputs(
                    tuple(option for option in engine_options.strikes if option.attack_id in melee_attack_ids),
                    inspection, input_fn, output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    command_type = SnaggingStrike if action_id == "snagging_strike" else CombatGrab
                    _run_command(game, command_type(target_id, attack_id, damage_type, nonlethal), output_fn)
            elif action_id == "brutish_shove":
                from pf2e.content import get_definition

                acting_actor = game._state.creatures.get(engine_options.actor_id or "")
                two_handed = {
                    attack.attack_id for attack in get_definition(acting_actor.definition_id).attacks
                    if "melee" in attack.traits and attack.hands_required >= 2
                } if acting_actor is not None else set()
                strike_inputs = _choose_strike_inputs(
                    tuple(option for option in engine_options.strikes if option.attack_id in two_handed),
                    inspection, input_fn, output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    target = game._state.creatures.get(target_id)
                    actor = game._state.creatures.get(engine_options.actor_id or "")
                    if target is None or actor is None:
                        continue
                    failure_effect = _choose_index("On a hit, use failure effect?", ("Automatic Shove", "Failure effect: off-guard"), input_fn, output_fn)
                    if failure_effect is None:
                        continue
                    destination = None
                    follow = False
                    if failure_effect == 0:
                        dx = (target.position.x > actor.position.x) - (target.position.x < actor.position.x)
                        dy = (target.position.y > actor.position.y) - (target.position.y < actor.position.y)
                        candidate = Position(target.position.x + dx, target.position.y + dy)
                        if (
                            0 <= candidate.x < game._state.map_width
                            and 0 <= candidate.y < game._state.map_height
                            and not any(other.actor_id != target_id and other.position == candidate and not other.defeated for other in game._state.creatures.values())
                        ):
                            destination = candidate
                        else:
                            output_fn("No open away destination is available; the Strike remains legal but cannot Shove.")
                        follow_choice = _choose_index("Follow the target?", ("Do not follow", "Follow without reactions"), input_fn, output_fn)
                        if follow_choice is None:
                            continue
                        follow = follow_choice == 1 and destination is not None
                    _run_command(game, BrutishShove(target_id, attack_id, destination, follow, failure_effect == 1, damage_type, nonlethal), output_fn)
            elif action_id == "dueling_parry":
                from pf2e.content import get_definition

                acting_actor = game._state.creatures.get(engine_options.actor_id or "")
                definition = get_definition(acting_actor.definition_id) if acting_actor is not None else None
                choices = tuple(
                    option for option in engine_options.strikes
                    if definition is not None and any(
                        attack.attack_id == option.attack_id
                        and attack.item_id is not None
                        and attack.hands_required == 1
                        and "melee" in attack.traits
                        for attack in definition.attacks
                    )
                )
                index = _choose_index(
                    "Dueling weapon:",
                    tuple(f"{option.name} ({option.attack_id})" for option in choices),
                    input_fn, output_fn,
                )
                if index is not None:
                    _run_command(game, DuelingParry(choices[index].attack_id), output_fn)
            elif action_id == "crane_stance":
                _run_command(game, CraneStance(), output_fn)
            elif action_id == "dismiss_crane_stance":
                _run_command(game, DismissCraneStance(), output_fn)
            elif action_id == "point_blank_stance":
                _run_command(game, PointBlankStance(), output_fn)
            elif action_id == "flurry_of_blows":
                strike_inputs = _choose_strike_inputs(
                    tuple(
                        option for option in engine_options.strikes
                        if option.attack_id in {"fist", "kama", "crane_wing"}
                    ),
                    inspection,
                    input_fn,
                    output_fn,
                )
                if strike_inputs is not None:
                    from pf2e.monk import FlurryOfBlows
                    from pf2e.model import PairedStrikeSelection

                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    _run_command(
                        game,
                        FlurryOfBlows(PairedStrikeSelection(target_id, attack_id, damage_type, nonlethal)),
                        output_fn,
                    )
            elif action_id == "hunt_prey":
                target_id = _choose_target(
                    tuple(
                        actor.actor_id for actor in inspection.actors
                        if actor.actor_id != engine_options.actor_id and not actor.defeated
                    ),
                    inspection,
                    input_fn,
                    output_fn,
                    prompt="Hunt Prey target:",
                )
                if target_id is not None:
                    _run_command(game, HuntPrey(target_id), output_fn)
            elif action_id == "hunted_shot":
                strike_inputs = _choose_strike_inputs(
                    tuple(
                        option for option in engine_options.strikes
                        if option.attack_id == "shortbow"
                    ),
                    inspection,
                    input_fn,
                    output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, damage_type, nonlethal = strike_inputs
                    from pf2e.model import PairedStrikeSelection

                    _run_command(
                        game,
                        HuntedShot(PairedStrikeSelection(target_id, attack_id, damage_type, nonlethal)),
                        output_fn,
                    )
            elif action_id == "hunter_aim":
                strike_inputs = _choose_strike_inputs(
                    tuple(
                        option for option in engine_options.strikes
                        if option.attack_id == "shortbow"
                    ),
                    inspection,
                    input_fn,
                    output_fn,
                )
                if strike_inputs is not None:
                    attack_id, target_id, _damage_type, _nonlethal = strike_inputs
                    _run_command(game, HunterAim(target_id, attack_id), output_fn)
            elif action_id == "confident_finisher":
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
                        ConfidentFinisher(
                            target_id=target_id,
                            attack_id=attack_id,
                            damage_type=damage_type,
                            nonlethal=nonlethal,
                        ),
                        output_fn,
                    )
            elif action_id in {"trip", "trip_assurance", "grapple", "grapple_assurance"}:
                base_action_id = action_id.removesuffix("_assurance")
                use_assurance = action_id.endswith("_assurance")
                target_id = _choose_encounter_actor(
                    f"{_ACTION_LABELS[base_action_id]} target:",
                    inspection,
                    engine_options.actor_id,
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    actor = next(
                        (item for item in inspection.actors if item.actor_id == engine_options.actor_id),
                        None,
                    )
                    maneuver_item_id = _choose_maneuver_item(
                        actor,
                        _ACTION_LABELS[base_action_id],
                        input_fn,
                        output_fn,
                    )
                    command_type = Trip if base_action_id == "trip" else Grapple
                    _run_command(
                        game,
                        command_type(
                            target_id=target_id,
                            maneuver_item_id=maneuver_item_id,
                            use_assurance=use_assurance,
                        ),
                        output_fn,
                    )
            elif action_id == "escape_assurance":
                impediment_id = _choose_assurance_escape_input(
                    inspection,
                    engine_options,
                    input_fn,
                    output_fn,
                )
                if impediment_id is not None:
                    _run_command(
                        game,
                        Escape(
                            impediment_id=impediment_id,
                            check_method="athletics",
                            use_assurance=True,
                        ),
                        output_fn,
                    )
            elif action_id == "escape":
                escape_inputs = _choose_escape_inputs(
                    inspection,
                    engine_options,
                    input_fn,
                    output_fn,
                )
                if escape_inputs is not None:
                    impediment_id, check_method, attack_id = escape_inputs
                    _run_command(
                        game,
                        Escape(
                            impediment_id=impediment_id,
                            check_method=check_method,
                            attack_id=attack_id,
                        ),
                        output_fn,
                    )
            elif action_id == "demoralize":
                target_id = _choose_encounter_actor(
                    "Demoralize target:",
                    inspection,
                    engine_options.actor_id,
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    acting_actor = next(
                        (
                            actor
                            for actor in inspection.actors
                            if actor.actor_id == engine_options.actor_id
                        ),
                        None,
                    )
                    use_intimidating_glare = False
                    if (
                        acting_actor is not None
                        and getattr(acting_actor, "class_name", None) == "Swashbuckler"
                        and "Intimidating Glare" in getattr(acting_actor, "feats", ())
                    ):
                        answer = _read_line(
                            "Use Intimidating Glare (visual, no language penalty)? [y/N]:",
                            input_fn,
                            output_fn,
                        ).strip().casefold()
                        use_intimidating_glare = answer in {"y", "yes"}
                    _run_command(
                        game,
                        Demoralize(
                            target_id=target_id,
                            use_intimidating_glare=use_intimidating_glare,
                        ),
                        output_fn,
                    )
            elif action_id == "feint":
                target_id = _choose_encounter_actor(
                    "Feint target:",
                    inspection,
                    engine_options.actor_id,
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    _run_command(
                        game,
                        Feint(target_id=target_id),
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
            elif action_id == "flee":
                # The engine owns route selection and any necessary Stand,
                # Escape, reaction, or saved-choice continuation.  The
                # terminal only dispatches the public action it exposed.
                _run_command(game, Flee(), output_fn)
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
            elif action_id == "raise_shield":
                _run_command(game, RaiseShield(), output_fn)
            elif action_id == "lay_on_hands":
                target_id = _choose_encounter_actor(
                    "Lay on Hands target:",
                    inspection,
                    engine_options.actor_id,
                    input_fn,
                    output_fn,
                )
                if target_id is not None:
                    _run_command(game, LayOnHands(target_id=target_id), output_fn)
            elif action_id == "nudge_the_scales":
                target_id = _choose_encounter_actor("Nudge the Scales target:", inspection, engine_options.actor_id, input_fn, output_fn, include_actor=True)
                if target_id is not None and engine_options.actor_id is not None:
                    _run_result(game.nudge_the_scales(engine_options.actor_id, target_id), output_fn)
            elif action_id == "suppress_aura":
                _run_command(game, SuppressAura(), output_fn)
            elif action_id == "resume_aura":
                _run_command(game, ResumeAura(), output_fn)
            elif action_id == "rage":
                _run_command(game, Rage(), output_fn)
            elif action_id == "sustain_light":
                sustain_inputs = _choose_light_sustain_inputs(
                    inspection,
                    input_fn,
                    output_fn,
                )
                if sustain_inputs is not None:
                    orb_id, point, attachment_actor_id = sustain_inputs
                    _run_command(
                        game,
                        Sustain(
                            orb_id=orb_id,
                            point=point,
                            attachment_actor_id=attachment_actor_id,
                        ),
                        output_fn,
                    )
            elif action_id == "dismiss_light":
                orb_id = _choose_light_orb(
                    inspection,
                    input_fn,
                    output_fn,
                    prompt="Light orb to Dismiss:",
                )
                if orb_id is not None:
                    _run_command(game, Dismiss(orb_id=orb_id), output_fn)
            elif action_id == "dismiss_life_link":
                actor_id = engine_options.actor_id
                effect = next(
                    (
                        item for item in game._state.active_effects
                        if item.kind == "life_link" and item.source_actor_id == actor_id
                    ),
                    None,
                )
                if effect is None:
                    output_fn("No active Life Link is available to dismiss.")
                else:
                    _run_command(game, Dismiss(effect_id=effect.effect_id), output_fn)
            elif action_id == "drain_bonded_item":
                from pf2e.wizard import DrainBondedItem

                item_id = _choose_held_item(inspection, input_fn, output_fn)
                if item_id is not None:
                    _run_command(game, DrainBondedItem(item_id), output_fn)
            elif action_id == "cast":
                cast_inputs = _choose_cast_inputs(
                    engine_options.spells,
                    inspection,
                    input_fn,
                    output_fn,
                )
                if cast_inputs is not None:
                    item_id = None
                    point = None
                    color = None
                    attachment_actor_id = None
                    replacement_orb_id = None
                    target_ids = None
                    area_direction = None
                    use_arcane_bond = False
                    spell_mode = None
                    if len(cast_inputs) == 10:
                        (
                            spell_id,
                            target_id,
                            actions,
                            slot_id,
                            include_self,
                            item_id,
                            point,
                            color,
                            attachment_actor_id,
                            replacement_orb_id,
                        ) = cast_inputs
                    elif len(cast_inputs) == 9:
                        (
                            spell_id,
                            target_id,
                            actions,
                            slot_id,
                            include_self,
                            item_id,
                            point,
                            color,
                            attachment_actor_id,
                        ) = cast_inputs
                    elif len(cast_inputs) == 7:
                        spell_id, target_id, actions, slot_id, include_self, special_input, bond_input = cast_inputs
                        use_arcane_bond = bond_input == {"use_arcane_bond": True}
                        if spell_id == "force_barrage":
                            target_ids, item_id, area_direction = special_input, None, None
                        elif spell_id == "electric_arc":
                            target_ids, item_id, area_direction = special_input, None, None
                        elif spell_id == "breathe_fire":
                            area_direction, item_id, target_ids = special_input, None, None
                        else:
                            raise ValueError("unsupported bonded spell input")
                    elif len(cast_inputs) == 6:
                        spell_id, target_id, actions, slot_id, include_self, special_input = cast_inputs
                        if spell_id == "force_barrage":
                            target_ids, item_id, area_direction = special_input, None, None
                        elif spell_id == "electric_arc":
                            target_ids, item_id, area_direction = special_input, None, None
                        elif spell_id == "breathe_fire":
                            area_direction, item_id, target_ids = special_input, None, None
                        elif isinstance(special_input, dict) and special_input.get("spell_mode") in {"ranged", "melee", "piercing", "slashing", "visible", "invisible"}:
                            spell_mode = special_input["spell_mode"]
                            item_id = special_input.get("item_id")
                        elif special_input == {"use_arcane_bond": True}:
                            use_arcane_bond = True
                        else:
                            item_id, target_ids, area_direction = special_input, None, None
                    else:
                        spell_id, target_id, actions, slot_id, include_self = cast_inputs
                    _run_command(
                        game,
                        Cast(
                            spell_id=spell_id,
                            target_id=target_id,
                            actions=actions,
                            slot_id=slot_id,
                            include_self=include_self,
                            item_id=item_id,
                            point=point,
                            color=color,
                            attachment_actor_id=attachment_actor_id,
                            replacement_orb_id=replacement_orb_id,
                            target_ids=target_ids,
                            area_direction=area_direction,
                            use_arcane_bond=use_arcane_bond,
                            spell_mode=spell_mode,
                        ),
                        output_fn,
                    )
            elif action_id == "lingering_composition":
                _run_command(game, LingeringComposition(), output_fn)
            elif action_id == "reach_spell":
                from pf2e.reach_spell_terminal import command as reach_spell_command

                _run_command(game, reach_spell_command(), output_fn)
            elif action_id == "widen_spell":
                from pf2e.widen_spell_terminal import command as widen_spell_command

                _run_command(game, widen_spell_command(), output_fn)
            elif action_id == "energy_ablation":
                energy_types = ("acid", "cold", "electricity", "fire", "force", "sonic", "vitality", "void")
                selected = _choose_index("Energy type number:", energy_types, input_fn, output_fn)
                if selected is not None:
                    _run_command(game, EnergyAblation(energy_types[selected]), output_fn)
            elif action_id == "cackle":
                _run_command(game, Cackle(), output_fn)
            elif action_id == "end_turn":
                _run_command(game, EndTurn(), output_fn)
            elif action_id == "refocus":
                actor_id = _choose_refocus_actor(inspection, input_fn, output_fn)
                if actor_id is not None:
                    output_fn(
                        "Refocus takes 10 minutes and restores only 1 Focus Point; "
                        "HP, spell slots, and other resources are unchanged."
                    )
                    _run_result(game.refocus(actor_id), output_fn)
            elif action_id == "next_encounter":
                next_setup = (
                    BOMBER_ALCHEMIST_NEXT_SETUP
                    if getattr(setup, "setup_id", None) == BOMBER_ALCHEMIST_SETUP.setup_id
                    else ANGELIC_NEXT_ENCOUNTER_SETUP
                )
                result = game.next_encounter(next_setup)
                _run_result(result, output_fn)
                if result.status is not ResultStatus.REJECTED:
                    setup = next_setup
            elif action_id == "record_rested":
                actor_ids = _choose_downtime_actor_group(inspection, input_fn, output_fn)
                if actor_ids is not None:
                    day_number = _read_integer("Declared preparation day:", input_fn, output_fn)
                    elapsed_seconds = _read_integer(
                        "Externally adjudicated elapsed seconds:", input_fn, output_fn
                    )
                    if day_number is not None and elapsed_seconds is not None:
                        output_fn(
                            "Record Rested Eligibility declares external rest facts; "
                            "it does not simulate sleep, healing, or fatigue recovery."
                        )
                        _run_result(
                            game.record_rested(
                                actor_ids,
                                day_number=day_number,
                                elapsed_seconds=elapsed_seconds,
                            ),
                            output_fn,
                        )
            elif action_id == "daily_prepare":
                actor_ids = _choose_downtime_actor_group(inspection, input_fn, output_fn)
                if actor_ids is not None:
                    output_fn(
                        "Daily Preparation advances one hour once, restores the selected "
                        "casters' actual spell and Focus resources, and ends only their Light."
                    )
                    preparations = _choose_daily_preparations(game, actor_ids, input_fn, output_fn)
                    if preparations is not None:
                        _run_result(game.daily_prepare(actor_ids, preparations), output_fn)
            elif action_id == "oracle_life_mode":
                actor_id = _choose_refocus_actor(inspection, input_fn, output_fn)
                if actor_id is not None:
                    mode = _read_line("Oracle mode (life/death):", input_fn, output_fn).strip().lower()
                    _run_result(game.set_oracle_life_mode(actor_id, mode), output_fn)
            elif action_id == "spell_substitution":
                actor_ids = _choose_downtime_actor_group(inspection, input_fn, output_fn)
                if actor_ids is not None and len(actor_ids) == 1:
                    slot_id = _read_line("Prepared rank-1 slot id:", input_fn, output_fn).strip()
                    spell_id = _read_line("Replacement spell id:", input_fn, output_fn).strip()
                    result = game.start_spell_substitution(actor_ids[0], slot_id, spell_id)
                    _run_result(result, output_fn)
                    if result.status is ResultStatus.COMPLETED:
                        elapsed = _read_integer("Uninterrupted elapsed seconds to advance (max 600):", input_fn, output_fn)
                        if elapsed is not None:
                            _run_result(game.advance_spell_substitution(actor_ids[0], elapsed), output_fn)
            elif action_id == "interrupt_spell_substitution":
                actor_ids = _choose_downtime_actor_group(inspection, input_fn, output_fn)
                if actor_ids is not None and len(actor_ids) == 1:
                    _run_result(game.interrupt_spell_substitution(actor_ids[0]), output_fn)
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
                    loaded_setup_id = getattr(getattr(game, "_state", None), "setup_id", None)
                    if loaded_setup_id is not None:
                        setup = get_setup(loaded_setup_id)
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
