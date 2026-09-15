"""Small bounded-output helpers shared by terminal integration tests."""


class BoundedTranscript(list[str]):
    """Keep a runaway scripted terminal test from retaining unlimited output."""

    def __init__(self, *, max_lines: int = 4096, max_chars: int = 1_048_576) -> None:
        super().__init__()
        self._max_lines = max_lines
        self._max_chars = max_chars
        self._captured_chars = 0

    def append(self, line: str) -> None:
        if len(self) >= self._max_lines or self._captured_chars + len(line) > self._max_chars:
            raise AssertionError("terminal test transcript exceeded its capture limit")
        super().append(line)
        self._captured_chars += len(line)
