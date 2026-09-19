"""Public catalog and terminal evidence for the admitted Angelic slice."""

from pathlib import Path

import pf2e.content as content
import pf2e.terminal as terminal


def test_curated_angelic_first_cast_and_item_ally_are_admitted() -> None:
    setup = content.get_setup("sorcerer_angelic_first_cast")

    assert setup is content.ANGELIC_FIRST_CAST_SETUP
    assert setup.setup_id in content.SETUPS
    assert content.ANGELIC_SORCERER_STAGED.definition_id in content.CREATURES
    assert content.WEAPON_IDENTITY_FIGHTER_M.definition_id in content.CREATURES
    assert setup.setup_id not in content._STAGED_SETUPS
    assert content.ANGELIC_SORCERER_STAGED.definition_id not in content._STAGED_CREATURES
    assert content.WEAPON_IDENTITY_FIGHTER_M.definition_id not in content._STAGED_CREATURES
    assert all(placement.definition_id in content.CREATURES for placement in setup.placements)
    assert terminal.render_support_summary(setup.setup_id).startswith(
        "Curated Angelic level-1 Sorcerer first-cast setup:"
    )


class _MainPlayScript:
    """Drive the real ``main`` path through a Heal choice save/load."""

    def __init__(self, save_path: Path) -> None:
        self.save_path = str(save_path)
        self.answers = iter(
            (
                "2",  # Initial initiative choice: resolve.
                "1",  # Keep initiative.
                "8",  # Ally: End Turn (Release is also exposed for the held item).
                "4",  # Guard Dog: End Turn.
                "5",  # Sorcerer: Cast.
                "6",  # Spell: Heal.
                "2",  # Two-action mode.
                "1",  # Rank-1 spontaneous slot.
                "2",  # Heal the ally.
                "3",  # Save the pending Blood Magic recipient choice.
                self.save_path,
                "4",  # Load the same pending choice.
                self.save_path,
                "2",  # Resolve the restored Blood Magic choice.
                "1",  # Choose the caster as Blood Magic recipient.
                "2",  # Resolve the restored willingness choice.
                "1",  # The ally is willing.
                "19",  # Quit after the supported cast.
            )
        )

    def __call__(self) -> str:
        try:
            return next(self.answers)
        except StopIteration as exc:
            raise AssertionError("real main path requested more input than expected") from exc


def test_real_main_admitted_angelic_heal_choice_save_load_smoke(tmp_path, monkeypatch, capsys) -> None:
    save_path = tmp_path / "angelic-cli-save.json"
    monkeypatch.setattr("builtins.input", _MainPlayScript(save_path))

    exit_code = terminal.main(
        [
            "play",
            "sorcerer_angelic_first_cast",
            "--seed",
            "13",
            "--save-path",
            str(save_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert save_path.exists()
    assert "Curated Angelic level-1 Sorcerer first-cast setup:" in output
    assert "Heal" in output
    assert "Saved encounter to" in output
    assert "Loaded encounter from" in output
    assert "Goodbye." in output
