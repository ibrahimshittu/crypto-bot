"""Tests for order qty/price rounding (Bybit lot step + tick size)."""

from core.execution.rounding import floor_to_step, round_to_tick


def test_floor_to_step_whole_lots():
    # The exact bug: 147977.84 with step 1 → 147977 (valid lot)
    assert floor_to_step(147977.8400908, 1.0) == 147977.0


def test_floor_to_step_fractional():
    assert floor_to_step(147977.8400908, 0.1) == 147977.8
    assert floor_to_step(0.123456, 0.001) == 0.123


def test_floor_to_step_never_rounds_up():
    assert floor_to_step(9.99, 1.0) == 9.0  # down, not up to 10


def test_floor_to_step_no_step_passthrough():
    assert floor_to_step(123.456, 0) == 123.456


def test_round_to_tick():
    assert round_to_tick(0.07441357, 0.0001) == 0.0744
    assert round_to_tick(100.0, 0.5) == 100.0
    assert round_to_tick(100.3, 0.5) == 100.5


def test_round_to_tick_no_tick_passthrough():
    assert round_to_tick(1.2345, 0) == 1.2345
