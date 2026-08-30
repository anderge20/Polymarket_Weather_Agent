"""weather_agent.strategy — Phase 2D Strategy A (weather-vs-market signal generator).

Scope: signal generation ONLY (predictions + signals). No sizing, no net/fees, no
P&L, no execution, no backtest. See PHASE_2D_STRATEGY_A_DESIGN.md.
"""
from .strategy_a import generate_event_signals

__all__ = ["generate_event_signals"]
