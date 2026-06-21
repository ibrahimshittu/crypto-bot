"""Self-improvement: turn journaled trades into lessons + strategy weights."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from agents.schemas import Lesson
from memory.journal import JournalEntry


@dataclass
class StrategyWeights:
    """Per-strategy multiplier in [0, 1.5]; 1.0 = neutral. Biases scanner/selection."""

    weights: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1.0))

    def get(self, strategy_id: str) -> float:
        return self.weights.get(strategy_id, 1.0)

    def nudge(self, strategy_id: str, delta: float) -> None:
        new = max(0.0, min(1.5, self.get(strategy_id) + delta))
        self.weights[strategy_id] = new


class DeterministicReflector:
    """Rule-based lessons from journal statistics — the no-LLM self-improvement path."""

    def __init__(self, min_trades: int = 10, weak_win_rate: float = 0.4):
        self.min_trades = min_trades
        self.weak_win_rate = weak_win_rate

    def reflect(self, trades: list[JournalEntry], weights: StrategyWeights) -> list[Lesson]:
        lessons: list[Lesson] = []

        buckets: dict[tuple[str, str], list[JournalEntry]] = defaultdict(list)
        for t in trades:
            buckets[(t.strategy_id, t.session_label)].append(t)

        for (strat, session), group in buckets.items():
            if len(group) < self.min_trades:
                continue
            wins = sum(1 for t in group if t.pnl > 0)
            wr = wins / len(group)
            avg = sum(t.pnl_pct for t in group) / len(group)
            if wr < self.weak_win_rate or avg < 0:
                weights.nudge(strat, -0.15)
                lessons.append(
                    Lesson(
                        scope=f"{strat}/{session}",
                        lesson=(
                            f"{strat} underperforms in {session} "
                            f"(win rate {wr:.0%}, avg {avg:+.2f}%) → down-weight / avoid."
                        ),
                        weight=2.0,
                    )
                )
            elif wr > 0.6 and avg > 0:
                weights.nudge(strat, +0.1)
                lessons.append(
                    Lesson(
                        scope=f"{strat}/{session}",
                        lesson=(
                            f"{strat} works well in {session} "
                            f"(win rate {wr:.0%}, avg {avg:+.2f}%) → keep / up-weight."
                        ),
                        weight=1.5,
                    )
                )

        slipped = [t for t in trades if t.realized_slippage > t.expected_slippage * 2 > 0]
        if len(slipped) >= self.min_trades:
            lessons.append(
                Lesson(
                    scope="execution",
                    lesson=(
                        f"{len(slipped)} trades had realized slippage >2x expected → "
                        "tighten depth gate / prefer TWAP on thin pairs."
                    ),
                    weight=2.5,
                )
            )
        return lessons
