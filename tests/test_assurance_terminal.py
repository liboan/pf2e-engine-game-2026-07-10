"""Numbered terminal coverage for the engine-owned Assurance intents."""

from pf2e.content import get_setup
from pf2e.terminal import run_terminal


def _run_assurance_trip_terminal(*, rolls: tuple[int, ...], inputs: list[str], save_path=None):
    transcript: list[str] = []
    remaining = iter(inputs)
    result = run_terminal(
        setup=get_setup("s2_pc_duel_fixture"),
        rolls=rolls,
        save_path=save_path or "assurance-terminal-save.json",
        input_fn=lambda: next(remaining),
        output_fn=transcript.append,
    )
    return result, "\n".join(transcript)


def test_terminal_dispatches_numbered_assurance_trip_without_a_second_choice() -> None:
    result, transcript = _run_assurance_trip_terminal(
        rolls=(20, 1),
        inputs=[
            "2", "1",  # keep Fighter A's initiative
            "2", "1",  # keep Fighter B's initiative
            "14",      # Trip (Assurance)
            "1", "1",  # Fighter B; free hand
            "20",      # quit from the ordinary action menu
        ],
    )

    assert result == 0
    assert "14. Trip (Assurance)" in transcript
    assert "Fighter A uses Assurance (Athletics) for Trip against Fighter B: Failure (13 vs DC 16)." in transcript
    assert transcript.count("Choice prompt action:") == 2
    assert "may use Guidance for this check" not in transcript


def test_terminal_assurance_save_load_can_finish_a_real_encounter(tmp_path) -> None:
    save_path = tmp_path / "assurance-terminal-save.json"
    result, transcript = _run_assurance_trip_terminal(
        rolls=(20, 1, 20, 8, 8),
        save_path=save_path,
        inputs=[
            "2", "1",  # keep Fighter A's initiative
            "2", "1",  # keep Fighter B's initiative
            "14", "1", "1",  # Trip (Assurance), Fighter B, free hand
            "17", "",  # save at the post-Assurance action boundary
            "18", "",  # load the saved action boundary
            "4", "1", "1", "1", "1",  # longsword, Fighter B, slashing, default damage
            "2", "1",  # keep the ordinary Strike check
            "2", "1",  # apply the normal health outcome
            "6",  # quit after the blue team wins
        ],
    )

    assert result == 0
    assert save_path.exists()
    assert "Saved encounter to" in transcript
    assert "Loaded encounter from" in transcript
    assert "Fighter A uses Assurance (Athletics) for Trip against Fighter B" in transcript
    assert "Fighter B (red) — HP 0/21" in transcript
    assert "Fighter A (blue) — HP 21/21" in transcript
    assert "Encounter finished." in transcript
