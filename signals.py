"""
Signal generation module.

Translates composite scores from the analysis engine into actionable
BUY / SELL / HOLD signals with human-readable reasoning.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

from analysis import ETFAnalysis
from config import SignalConfig

logger = logging.getLogger(__name__)


class SignalType(Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


@dataclass
class Signal:
    """A trading signal for one ETF."""
    ticker: str
    signal_type: SignalType
    composite_score: float
    reasoning: str
    close_price: float


class SignalGenerator:
    """Produces buy/sell signals from scored ETF analyses."""

    def __init__(self, config: Optional[SignalConfig] = None) -> None:
        self.cfg = config or SignalConfig()

    def generate(
        self,
        analyses: List[ETFAnalysis],
        held_tickers: Optional[Set[str]] = None,
    ) -> Dict[str, List[Signal]]:
        """
        Generate signals for the full ETF universe.

        Parameters
        ----------
        analyses : list of ETFAnalysis
            Scored and sorted (best-first) analyses.
        held_tickers : set of str, optional
            Tickers currently in the portfolio. Used to mark SELL signals.

        Returns
        -------
        dict with keys ``"buy"``, ``"sell"``, ``"hold"`` each containing a
        list of Signal objects.
        """
        held = held_tickers or set()
        buy_signals: List[Signal] = []
        sell_signals: List[Signal] = []
        hold_signals: List[Signal] = []

        for a in analyses:
            sig_type = self._classify(a.composite_score)
            reasoning = self._build_reasoning(a, sig_type, a.ticker in held)

            signal = Signal(
                ticker=a.ticker,
                signal_type=sig_type,
                composite_score=a.composite_score,
                reasoning=reasoning,
                close_price=a.close_price,
            )

            if sig_type in (SignalType.STRONG_BUY, SignalType.BUY):
                buy_signals.append(signal)
            elif sig_type in (SignalType.SELL, SignalType.STRONG_SELL):
                if a.ticker in held:
                    sell_signals.append(signal)
                else:
                    hold_signals.append(signal)  # not held → just note it
            else:
                hold_signals.append(signal)

        # Also flag held tickers that have death-cross (SMA50 < SMA200)
        for a in analyses:
            if a.ticker in held and not a.golden_cross:
                already = any(s.ticker == a.ticker for s in sell_signals)
                if not already:
                    sell_signals.append(
                        Signal(
                            ticker=a.ticker,
                            signal_type=SignalType.SELL,
                            composite_score=a.composite_score,
                            reasoning=(
                                f"Death cross detected (SMA50 {a.sma_50:.2f} < "
                                f"SMA200 {a.sma_200:.2f}). Consider exiting."
                            ),
                            close_price=a.close_price,
                        )
                    )

        # Limit buy recommendations
        buy_signals = buy_signals[: self.cfg.top_n_recommendations]

        logger.info(
            "Signals generated — BUY: %d, SELL: %d, HOLD: %d",
            len(buy_signals),
            len(sell_signals),
            len(hold_signals),
        )
        return {"buy": buy_signals, "sell": sell_signals, "hold": hold_signals}

    # ── helpers ──────────────────────────────────────────────────────────

    def _classify(self, score: float) -> SignalType:
        if score >= self.cfg.strong_buy_threshold:
            return SignalType.STRONG_BUY
        elif score >= self.cfg.buy_threshold:
            return SignalType.BUY
        elif score >= self.cfg.hold_threshold:
            return SignalType.HOLD
        elif score >= self.cfg.strong_sell_threshold:
            return SignalType.SELL
        else:
            return SignalType.STRONG_SELL

    @staticmethod
    def _build_reasoning(a: ETFAnalysis, sig: SignalType, is_held: bool) -> str:
        """Compose a short human-readable reasoning string."""
        parts: List[str] = []

        # Momentum
        if a.momentum_3m > 5:
            parts.append(f"Strong 3-month momentum (+{a.momentum_3m:.1f}%)")
        elif a.momentum_3m < -5:
            parts.append(f"Weak 3-month momentum ({a.momentum_3m:.1f}%)")

        # Trend
        if a.above_sma_50 and a.above_sma_200 and a.golden_cross:
            parts.append("Full bullish alignment (price > SMA50 > SMA200)")
        elif not a.above_sma_50 and not a.above_sma_200:
            parts.append("Below both key moving averages — bearish trend")
        elif a.golden_cross:
            parts.append("Golden cross in effect")
        elif not a.golden_cross:
            parts.append("Death cross — caution")

        # RSI
        if a.rsi_value > 70:
            parts.append(f"RSI overbought ({a.rsi_value:.0f})")
        elif a.rsi_value < 30:
            parts.append(f"RSI oversold ({a.rsi_value:.0f}) — potential reversal")
        else:
            parts.append(f"RSI neutral ({a.rsi_value:.0f})")

        # Volume
        if a.volume_trend > 1.2:
            parts.append("Rising volume confirms price action")
        elif a.volume_trend < 0.8:
            parts.append("Declining volume — conviction is weak")

        # Volatility
        if a.atr_pct > 2.5:
            parts.append(f"High volatility (ATR {a.atr_pct:.1f}%)")

        # Held context
        if is_held and sig in (SignalType.SELL, SignalType.STRONG_SELL):
            parts.append("⚠️  Currently held — review for exit")

        return ". ".join(parts) + "." if parts else "No notable signals."
