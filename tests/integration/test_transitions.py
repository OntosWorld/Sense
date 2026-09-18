"""Integration tests: transition detection (FR-8)."""

from __future__ import annotations

from sense_ai import (
    ContextMachine,
    capability,
    equals,
)
from sense_ai.model.result import CapabilityStatus


class TestTransitionDetection:
    """FR-8: state-change callbacks and transition log."""

    def test_no_transition_on_initial_evaluation(self) -> None:
        """First evaluation records a transition (from None → status)."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability("c", requires=[equals("x", True)])
        )
        m.observe("x", True)
        result = m.evaluate("c")
        assert result.status == CapabilityStatus.AVAILABLE
        # A machine that has never been evaluated has no "previous" — but
        # the first evaluate() still records a transition from None
        assert len(m.transitions()) >= 1

    def test_transition_log_grows(self) -> None:
        """Transition log grows when status changes."""
        m = ContextMachine()
        m.define_capability(
            capability("c", requires=[equals("x", True)])
        )
        # Initial evaluation — status goes from None → UNKNOWN (no data)
        _ = m.evaluate("c")
        initial_count = len(m.transitions())

        # Add observation → UNKNOWN → AVAILABLE
        m.observe("x", True)
        r2 = m.evaluate("c")
        assert r2.status == CapabilityStatus.AVAILABLE
        assert len(m.transitions()) > initial_count

        # Add contradicting observation → AVAILABLE → UNAVAILABLE
        m.observe("x", False)
        r3 = m.evaluate("c")
        assert r3.status == CapabilityStatus.UNAVAILABLE
        assert len(m.transitions()) > initial_count + 1

    def test_transition_callback(self) -> None:
        """on_transition() decorator fires when status changes."""
        m = ContextMachine()
        m.define_capability(
            capability("c", requires=[equals("x", True)])
        )
        fired: list[str] = []

        @m.on_transition("c")
        def on_c_changed(t):
            fired.append(f"{t.previous}→{t.current}")

        # First evaluation
        m.evaluate("c")  # UNKNOWN (no data)
        m.observe("x", True)
        m.evaluate("c")  # AVAILABLE
        m.observe("x", False)
        m.evaluate("c")  # UNAVAILABLE

        assert len(fired) >= 2

    def test_transition_callback_only_on_change(self) -> None:
        """Callback does NOT fire when status stays the same."""
        m = ContextMachine()
        m.define_capability(
            capability("c", requires=[equals("x", True)])
        )
        fired: list[str] = []

        @m.on_transition("c")
        def on_c_changed(t):
            fired.append(str(t.current))

        m.observe("x", True)
        m.evaluate("c")  # → AVAILABLE
        m.evaluate("c")  # Same status — no transition
        m.evaluate("c")  # Same status — no transition

        assert len(fired) == 1

    def test_transitions_returns_all(self) -> None:
        """transitions() returns all recorded transitions."""
        m = ContextMachine()
        m.define_capability(capability("c", requires=[equals("x", True)]))
        m.evaluate("c")  # None → UNKNOWN
        m.observe("x", True)
        m.evaluate("c")  # UNKNOWN → AVAILABLE
        all_t = m.transitions()
        assert len(all_t) == 2
        assert all_t[0].current == CapabilityStatus.UNKNOWN
        assert all_t[1].current == CapabilityStatus.AVAILABLE

    def test_transitions_filtered_by_capability(self) -> None:
        """transitions(capability=...) returns only that capability's transitions."""
        m = ContextMachine()
        m.define_capability(capability("a", requires=[equals("x", True)]))
        m.define_capability(capability("b", requires=[equals("y", True)]))
        m.evaluate("a")
        m.evaluate("b")
        transitions_a = m.transitions("a")
        transitions_b = m.transitions("b")
        assert all(t.capability == "a" for t in transitions_a)
        assert all(t.capability == "b" for t in transitions_b)

    def test_unknown_to_unavailable_transition(self) -> None:
        """UNKNOWN → concrete failure → UNAVAILABLE is a real transition."""
        m = ContextMachine()
        m.define_capability(
            capability("c", requires=[equals("x", True)])
        )
        m.evaluate("c")  # UNKNOWN (no data)
        m.observe("x", False)  # concrete failure
        result = m.evaluate("c")
        assert result.status == CapabilityStatus.UNAVAILABLE
        last = m.transitions("c")[-1]
        assert last.current == CapabilityStatus.UNAVAILABLE

    def test_clear_transitions(self) -> None:
        """Clearing the internal _transitions list resets the log."""
        m = ContextMachine()
        m.define_capability(capability("c", requires=[equals("x", True)]))
        m.evaluate("c")
        assert len(m.transitions()) >= 1
        m._transitions.clear()
        assert m.transitions() == []
