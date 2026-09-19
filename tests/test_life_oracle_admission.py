"""Public catalog and terminal evidence for the admitted Life Oracle slice."""

import pf2e.content as content
import pf2e.terminal as terminal


def test_selected_life_oracle_is_in_the_ordinary_catalog_and_terminal() -> None:
    setup = content.get_setup("staged_life_oracle_nudge")

    assert setup is content.LIFE_ORACLE_NUDGE_SETUP
    assert setup.setup_id in content.SETUPS
    assert content.LIFE_ORACLE.definition_id in content.CREATURES
    assert setup.setup_id not in content._STAGED_SETUPS
    assert content.LIFE_ORACLE.definition_id not in content._STAGED_CREATURES
    assert all(placement.definition_id in content.CREATURES for placement in setup.placements)
    assert terminal.render_support_summary(setup.setup_id).startswith(
        "Curated level-1 Life Oracle setup:"
    )


def test_terminal_main_starts_the_catalogued_life_oracle_setup(monkeypatch) -> None:
    seen = {}

    def capture_run(*, setup, seed, save_path):
        seen.update(setup=setup, seed=seed, save_path=save_path)
        return 0

    monkeypatch.setattr(terminal, "run_terminal", capture_run)

    assert terminal.main([
        "play", "staged_life_oracle_nudge", "--seed", "29", "--save-path", "oracle.json",
    ]) == 0
    assert seen == {
        "setup": content.LIFE_ORACLE_NUDGE_SETUP,
        "seed": 29,
        "save_path": "oracle.json",
    }
