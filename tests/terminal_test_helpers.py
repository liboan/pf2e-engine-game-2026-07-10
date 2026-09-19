"""Small bounded helpers shared by terminal integration tests."""

from collections.abc import Callable


class BoundedInput:
    """Stop a scripted terminal run whose policy never reaches a terminal state."""

    def __init__(
        self,
        input_fn: Callable[[], str],
        *,
        max_calls: int = 4096,
        describe: Callable[[], str] | None = None,
    ) -> None:
        if max_calls < 1:
            raise ValueError("input call limit must be positive")
        self._input_fn = input_fn
        self._max_calls = max_calls
        self._describe = describe
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def __call__(self) -> str:
        if self._calls >= self._max_calls:
            detail = ""
            if self._describe is not None:
                detail = f"; {self._describe()}"
            raise AssertionError(
                f"terminal test input script exceeded its call limit "
                f"({self._max_calls}){detail}"
            )
        self._calls += 1
        return self._input_fn()


class BoundedTranscript(list[str]):
    """Keep a runaway scripted terminal test from retaining unlimited output."""

    def __init__(self, *, max_lines: int = 4096, max_chars: int = 1_048_576) -> None:
        super().__init__()
        self._max_lines = max_lines
        self._max_chars = max_chars
        self._captured_chars = 0

    def append(self, line: str) -> None:
        if len(self) >= self._max_lines or self._captured_chars + len(line) > self._max_chars:
            last = f"; last_output={self[-1]!r}" if self else ""
            raise AssertionError(
                f"terminal test transcript exceeded its capture limit{last}"
            )
        super().append(line)
        self._captured_chars += len(line)
