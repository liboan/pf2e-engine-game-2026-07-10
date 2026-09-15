"""Small bounded harness for public-API encounter interaction tests."""

from pathlib import Path
from pf2e.encounter import Encounter
from pf2e.model import (
    ActionResult,
    ActorView,
    ChoiceView,
    Command,
    EndTurn,
    Inspection,
    ResultStatus,
)


class EncounterHarness:
    """Apply checked, bounded commands to one public Encounter instance."""

    def __init__(
        self,
        game: Encounter,
        scenario: str,
        *,
        max_commands: int = 160,
        max_choices: int = 40,
        max_rounds: int = 12,
        max_events: int = 2000,
    ) -> None:
        if min(max_commands, max_choices, max_rounds, max_events) < 1:
            raise ValueError("encounter harness limits must be positive")
        self.game = game
        self.scenario = scenario
        self.max_commands = max_commands
        self.max_choices = max_choices
        self.max_rounds = max_rounds
        self.max_events = max_events
        self.commands = 0
        self.choices = 0
        self.events_seen = 0
        self.last_result = "not started"
        self._guard_state()

    @property
    def inspection(self) -> Inspection:
        self._guard_state()
        return self.game.inspect()

    def actor(self, actor_id: str) -> ActorView:
        actor = next((item for item in self.inspection.actors if item.actor_id == actor_id), None)
        if actor is None:
            self._fail(f"actor {actor_id!r} is absent")
        return actor

    def pending_choice(
        self,
        *,
        kind: str,
        owner_actor_id: str | None,
        options: tuple[str, ...] = (),
    ) -> ChoiceView:
        choice = self.inspection.choice
        if choice is None:
            self._fail(f"expected pending choice {kind!r}; no choice is pending")
        if choice.kind != kind or choice.owner_actor_id != owner_actor_id:
            self._fail(
                f"expected choice {kind!r} owned by {owner_actor_id!r}; "
                f"found {choice.kind!r} owned by {choice.owner_actor_id!r}"
            )
        available = {option.option_id for option in choice.options}
        missing = set(options) - available
        if missing:
            self._fail(f"choice {kind!r} lacks expected option(s) {sorted(missing)!r}")
        return choice

    def command(
        self,
        action: Command,
        *,
        expected_status: ResultStatus | None = ResultStatus.COMPLETED,
    ) -> ActionResult:
        self._begin_step()
        result = self.game.execute(action)
        self._check_result(result, expected_status)
        return result

    def choose(
        self,
        *,
        kind: str,
        owner_actor_id: str | None,
        option_id: str,
        expected_status: ResultStatus | None = ResultStatus.COMPLETED,
    ) -> ActionResult:
        choice = self.pending_choice(
            kind=kind, owner_actor_id=owner_actor_id, options=(option_id,)
        )
        self._begin_step(choice=True)
        result = self.game.choose(choice.choice_id, option_id, owner_actor_id)
        self._check_result(result, expected_status)
        return result

    def checkpoint(self, path: str | Path) -> None:
        """Save and restore through the public persistence API, preserving budgets."""
        before = self.inspection
        self.game.save(path)
        restored = Encounter.load(path)
        if restored.inspect() != before:
            self._fail("save/load checkpoint changed encounter inspection")
        self.game = restored
        self._guard_state()

    def keep_initiative(self) -> None:
        """Keep each offered PC initiative result; leave a tie for explicit selection."""
        while (choice := self.inspection.choice) is not None:
            if choice.kind == "initiative_tie":
                return
            if choice.kind != "initiative_hero_reroll":
                self._fail(f"unexpected choice during initiative setup: {choice.kind!r}")
            self.choose(
                kind="initiative_hero_reroll",
                owner_actor_id=choice.owner_actor_id,
                option_id="keep",
                expected_status=None,
            )

    def advance_initiative(self, actor_id: str) -> ActionResult:
        """Select one actor in a displayed initiative tie, never infer the winner."""
        return self.choose(
            kind="initiative_tie",
            owner_actor_id=None,
            option_id=actor_id,
            expected_status=None,
        )

    def end_turn(self, *, expected_actor_id: str | None = None) -> ActionResult:
        result = self.command(EndTurn())
        inspection = self.inspection
        if expected_actor_id is not None and inspection.turn_actor_id != expected_actor_id:
            self._fail(
                f"EndTurn expected {expected_actor_id!r}, got {inspection.turn_actor_id!r}"
            )
        return result

    def assert_ended(self) -> None:
        inspection = self.inspection
        if inspection.in_progress or inspection.choice is not None:
            self._fail("expected encounter to have ended with no pending choice")

    def _begin_step(self, *, choice: bool = False) -> None:
        if self.commands >= self.max_commands:
            self._fail(f"command bound exceeded ({self.max_commands})")
        if choice and self.choices >= self.max_choices:
            self._fail(f"choice bound exceeded ({self.max_choices})")
        self.commands += 1
        if choice:
            self.choices += 1

    def _check_result(
        self, result: ActionResult, expected_status: ResultStatus | None
    ) -> None:
        self.events_seen += len(result.events)
        self.last_result = f"{result.status.value}: {result.message[:100]}"
        self._guard_state()
        if result.status in (ResultStatus.REJECTED, ResultStatus.UNSUPPORTED):
            self._fail(f"command was {result.status.value}: {result.message[:120]}")
        if expected_status is not None and result.status is not expected_status:
            self._fail(
                f"expected command status {expected_status.value!r}, got {result.status.value!r}"
            )
        if result.status is ResultStatus.PAUSED and result.inspection.choice is None:
            self._fail("command paused without a visible pending choice")
        if result.status is ResultStatus.COMPLETED and result.inspection.choice is not None:
            self._fail("command completed while an unhandled choice is pending")

    def _guard_state(self) -> None:
        inspection = self.game.inspect()
        if inspection.round_number > self.max_rounds:
            self._fail(f"round bound exceeded ({self.max_rounds})")
        if self.events_seen > self.max_events:
            self._fail(f"event bound exceeded ({self.max_events})")

    def _fail(self, reason: str) -> None:
        inspection = self.game.inspect()
        choice = inspection.choice
        pending = None if choice is None else f"{choice.kind}/{choice.owner_actor_id}"
        raise AssertionError(
            f"[{self.scenario}] {reason}; "
            f"round={inspection.round_number} turn={inspection.turn_actor_id!r} "
            f"choice={pending!r} commands={self.commands}/{self.max_commands} "
            f"choices={self.choices}/{self.max_choices} events={self.events_seen}/{self.max_events}; "
            f"last={self.last_result}"
        )
