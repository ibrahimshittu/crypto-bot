"""Liquidity + manipulation gates for the universe scanner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateConfig:
    # Liquidity
    min_24h_turnover_usd: float = 5_000_000.0   # min daily USD volume
    max_spread_bps: float = 25.0                # max bid/ask spread (basis points)
    min_depth_usd_1pct: float = 50_000.0        # min book notional within ±1% of mid
    # Manipulation / anomaly
    max_1h_abs_move_pct: float = 25.0           # reject parabolic 1h moves (pump signature)
    max_volume_spike_ratio: float = 12.0        # 1h vol vs trailing avg
    max_funding_abs_pct: float = 100.0          # |annualized funding| squeeze cap (normal ~11%)
    quarantine_age_hours: float = 72.0          # newly-listed pairs sit out this long


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]


def liquidity_gate(snap, cfg: GateConfig) -> GateResult:
    """Hard liquidity requirements. `snap` is an InstrumentSnapshot."""
    reasons: list[str] = []
    if snap.turnover_24h_usd < cfg.min_24h_turnover_usd:
        reasons.append(
            f"24h turnover ${snap.turnover_24h_usd:,.0f} < ${cfg.min_24h_turnover_usd:,.0f}"
        )
    if snap.spread_bps > cfg.max_spread_bps:
        reasons.append(f"spread {snap.spread_bps:.1f}bps > {cfg.max_spread_bps}bps")
    if snap.depth_usd_1pct < cfg.min_depth_usd_1pct:
        reasons.append(
            f"±1% depth ${snap.depth_usd_1pct:,.0f} < ${cfg.min_depth_usd_1pct:,.0f}"
        )
    return GateResult(passed=not reasons, reasons=tuple(reasons))


def manipulation_gate(snap, cfg: GateConfig) -> GateResult:
    """Reject pump-and-dump / manipulation signatures and stale-new listings."""
    reasons: list[str] = []
    if abs(snap.move_1h_pct) > cfg.max_1h_abs_move_pct:
        reasons.append(f"1h move {snap.move_1h_pct:+.1f}% looks parabolic")
    if snap.volume_spike_ratio > cfg.max_volume_spike_ratio:
        reasons.append(f"volume spike {snap.volume_spike_ratio:.1f}x trailing avg")
    if abs(snap.annualized_funding_pct) > cfg.max_funding_abs_pct:
        reasons.append(f"funding {snap.annualized_funding_pct:+.1f}% is an outlier")
    if snap.age_hours < cfg.quarantine_age_hours:
        reasons.append(f"listed {snap.age_hours:.0f}h ago < {cfg.quarantine_age_hours}h quarantine")
    return GateResult(passed=not reasons, reasons=tuple(reasons))
