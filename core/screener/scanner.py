"""UniverseScanner — apply gates, rank survivors, suggest a strategy per candidate."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.screener.gates import GateConfig, liquidity_gate, manipulation_gate


@dataclass(frozen=True)
class InstrumentSnapshot:
    """A point-in-time market snapshot for one tradable symbol."""

    symbol: str
    category: str                       # spot | linear
    last_price: float
    turnover_24h_usd: float
    spread_bps: float
    depth_usd_1pct: float
    move_1h_pct: float
    move_24h_pct: float
    volume_spike_ratio: float           # 1h volume / trailing avg
    realized_vol_pct: float             # recent realized volatility (annualized %)
    trend_score: float                  # -1..1 (e.g. fast/slow MA alignment)
    zscore: float                       # mean-reversion z-score of price vs rolling mean
    annualized_funding_pct: float = 0.0
    age_hours: float = 10_000.0         # hours since listing
    regime: str = "neutral"             # trending | ranging | neutral
    preferred_family: str = ""          # directional | market_neutral
    mtf_confluence: int = 0             # 0–3 timeframes agreeing with the 1h trend
    ob_imbalance: float = 0.0           # -1 ask-heavy … +1 bid-heavy
    frac_diff: float = 0.0              # fractionally-differentiated last close (stationary)
    funding_trend: float = 0.0          # slope of recent annualized funding
    oi_change_pct: float = 0.0          # % change in open interest


@dataclass(frozen=True)
class Candidate:
    symbol: str
    category: str
    score: float
    suggested_strategy: str
    rationale: str
    snapshot: InstrumentSnapshot
    rejected: bool = False
    reject_reasons: tuple[str, ...] = field(default_factory=tuple)


class UniverseScanner:
    def __init__(self, cfg: GateConfig | None = None):
        self.cfg = cfg or GateConfig()

    def _suggest_strategy(self, snap: InstrumentSnapshot) -> tuple[str, float, str]:
        """Pick the best-fit strategy family + an opportunity score for ranking."""
        liq_quality = min(1.0, snap.turnover_24h_usd / (self.cfg.min_24h_turnover_usd * 10))

        carry = abs(snap.annualized_funding_pct) if snap.category == "linear" else 0.0
        trend = abs(snap.trend_score)
        revert = max(0.0, abs(snap.zscore) - 1.5)

        # Regime boosts the strategy family that fits the current market.
        family = {"momentum_trend": "directional", "mean_reversion_statarb": "market_neutral"}
        def boost(strat_id: str) -> float:
            return 1.5 if snap.preferred_family and family.get(strat_id) == snap.preferred_family else 1.0

        options = [
            ("funding_carry_basis", carry / 10.0, f"funding {snap.annualized_funding_pct:+.1f}% annualized"),
            ("momentum_trend", trend * boost("momentum_trend"), f"trend score {snap.trend_score:+.2f}"),
            ("mean_reversion_statarb", revert * 0.5 * boost("mean_reversion_statarb"), f"z-score {snap.zscore:+.2f}"),
        ]
        strat, raw, why = max(options, key=lambda o: o[1])
        score = raw * (0.5 + 0.5 * liq_quality)
        return strat, score, f"{why} [{snap.regime}]"

    def scan(self, snapshots: list[InstrumentSnapshot]) -> list[Candidate]:
        """Return ranked candidates (survivors first by score desc; rejected flagged at end)."""
        survivors: list[Candidate] = []
        rejected: list[Candidate] = []

        for snap in snapshots:
            lg = liquidity_gate(snap, self.cfg)
            mg = manipulation_gate(snap, self.cfg)
            if not (lg.passed and mg.passed):
                rejected.append(
                    Candidate(
                        symbol=snap.symbol, category=snap.category, score=0.0,
                        suggested_strategy="none", rationale="gated out",
                        snapshot=snap, rejected=True,
                        reject_reasons=lg.reasons + mg.reasons,
                    )
                )
                continue

            strat, score, why = self._suggest_strategy(snap)
            survivors.append(
                Candidate(
                    symbol=snap.symbol, category=snap.category, score=score,
                    suggested_strategy=strat, rationale=why, snapshot=snap,
                )
            )

        survivors.sort(key=lambda c: c.score, reverse=True)
        return survivors + rejected

    def top(self, snapshots: list[InstrumentSnapshot], n: int = 20) -> list[Candidate]:
        return [c for c in self.scan(snapshots) if not c.rejected][:n]
