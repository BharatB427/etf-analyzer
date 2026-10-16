"""
Technical analysis & scoring engine.

Computes a composite 0–100 score for each ETF based on four equally-weighted
factors: Momentum, Moving-Average signals, RSI, and Volume/Volatility.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import AnalysisConfig

logger = logging.getLogger(__name__)


# ── Data containers ──────────────────────────────────────────────────────────

@dataclass
class FactorScores:
    """Individual factor scores for one ETF (each 0–100)."""
    momentum: float = 0.0
    moving_avg: float = 0.0
    rsi: float = 0.0
    volume_volatility: float = 0.0


@dataclass
class ETFAnalysis:
    """Complete analysis result for a single ETF."""
    ticker: str
    close_price: float
    factor_scores: FactorScores
    composite_score: float
    momentum_1m: float  # 1-month return %
    momentum_3m: float  # 3-month return %
    momentum_6m: float  # 6-month return %
    rsi_value: float
    sma_50: float
    sma_200: float
    above_sma_50: bool
    above_sma_200: bool
    golden_cross: bool  # SMA50 > SMA200
    volume_trend: float  # ratio of short/long avg volume
    atr_pct: float  # ATR as % of price


# ── Scoring engine ───────────────────────────────────────────────────────────

class AnalysisEngine:
    """Multi-factor scoring engine for ETF ranking."""

    def __init__(self, config: Optional[AnalysisConfig] = None) -> None:
        self.cfg = config or AnalysisConfig()

    # ── public API ───────────────────────────────────────────────────────

    def analyze_universe(
        self, data: Dict[str, pd.DataFrame]
    ) -> List[ETFAnalysis]:
        """
        Score every ETF in *data* and return a list of ETFAnalysis objects
        sorted by composite score (descending).
        """
        raw_results: List[dict] = []

        for ticker, df in data.items():
            try:
                result = self._analyze_single(ticker, df)
                if result is not None:
                    raw_results.append(result)
            except Exception as exc:
                logger.error("Analysis failed for %s: %s", ticker, exc, exc_info=True)

        if not raw_results:
            logger.warning("No ETFs could be analyzed — returning empty list.")
            return []

        # Percentile-rank momentum scores across the universe
        self._rank_momentum(raw_results)

        # Build final ETFAnalysis objects with composite score
        analyses: List[ETFAnalysis] = []
        for r in raw_results:
            fs = FactorScores(
                momentum=r["momentum_score"],
                moving_avg=r["ma_score"],
                rsi=r["rsi_score"],
                volume_volatility=r["vol_score"],
            )
            composite = (
                fs.momentum * self.cfg.weight_momentum
                + fs.moving_avg * self.cfg.weight_moving_avg
                + fs.rsi * self.cfg.weight_rsi
                + fs.volume_volatility * self.cfg.weight_volume_volatility
            )
            analyses.append(
                ETFAnalysis(
                    ticker=r["ticker"],
                    close_price=r["close"],
                    factor_scores=fs,
                    composite_score=round(composite, 2),
                    momentum_1m=r["mom_1m"],
                    momentum_3m=r["mom_3m"],
                    momentum_6m=r["mom_6m"],
                    rsi_value=r["rsi_val"],
                    sma_50=r["sma50"],
                    sma_200=r["sma200"],
                    above_sma_50=r["above_sma50"],
                    above_sma_200=r["above_sma200"],
                    golden_cross=r["golden_cross"],
                    volume_trend=r["vol_trend"],
                    atr_pct=r["atr_pct"],
                )
            )

        analyses.sort(key=lambda a: a.composite_score, reverse=True)
        logger.info(
            "Analysis complete — top ETF: %s (%.1f), bottom: %s (%.1f)",
            analyses[0].ticker,
            analyses[0].composite_score,
            analyses[-1].ticker,
            analyses[-1].composite_score,
        )
        return analyses

    # ── per-ticker analysis ──────────────────────────────────────────────

    def _analyze_single(self, ticker: str, df: pd.DataFrame) -> Optional[dict]:
        """Compute raw metrics for one ETF.  Returns a dict or None."""
        if len(df) < self.cfg.sma_long_period:
            logger.warning(
                "%s has only %d rows — need at least %d. Skipping.",
                ticker, len(df), self.cfg.sma_long_period,
            )
            return None

        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        volume = df["Volume"].astype(float)

        latest_close = float(close.iloc[-1])

        # ── Momentum returns ─────────────────────────────────────────
        mom_1m = self._pct_return(close, self.cfg.momentum_1m_period)
        mom_3m = self._pct_return(close, self.cfg.momentum_3m_period)
        mom_6m = self._pct_return(close, self.cfg.momentum_6m_period)

        # ── Moving Averages ──────────────────────────────────────────
        sma50 = float(close.rolling(self.cfg.sma_short_period).mean().iloc[-1])
        sma200 = float(close.rolling(self.cfg.sma_long_period).mean().iloc[-1])
        above_sma50 = latest_close > sma50
        above_sma200 = latest_close > sma200
        golden_cross = sma50 > sma200

        # SMA-50 slope (normalized)
        sma50_series = close.rolling(self.cfg.sma_short_period).mean()
        sma50_slope = (
            (sma50_series.iloc[-1] - sma50_series.iloc[-self.cfg.sma_slope_period])
            / sma50_series.iloc[-self.cfg.sma_slope_period]
            * 100
        ) if sma50_series.iloc[-self.cfg.sma_slope_period] != 0 else 0.0

        ma_score = self._score_moving_avg(
            above_sma50, above_sma200, golden_cross, sma50_slope
        )

        # ── RSI ──────────────────────────────────────────────────────
        rsi_val = self._compute_rsi(close, self.cfg.rsi_period)
        rsi_score = self._score_rsi(rsi_val)

        # ── Volume & Volatility ──────────────────────────────────────
        vol_short = float(volume.rolling(self.cfg.volume_short_period).mean().iloc[-1])
        vol_long = float(volume.rolling(self.cfg.volume_long_period).mean().iloc[-1])
        vol_trend = vol_short / vol_long if vol_long > 0 else 1.0

        atr = self._compute_atr(high, low, close, self.cfg.atr_period)
        atr_pct = (atr / latest_close * 100) if latest_close > 0 else 0.0

        vol_score = self._score_volume_volatility(vol_trend, atr_pct, above_sma50)

        return {
            "ticker": ticker,
            "close": latest_close,
            "mom_1m": mom_1m,
            "mom_3m": mom_3m,
            "mom_6m": mom_6m,
            "sma50": sma50,
            "sma200": sma200,
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
            "golden_cross": golden_cross,
            "ma_score": ma_score,
            "rsi_val": rsi_val,
            "rsi_score": rsi_score,
            "vol_trend": vol_trend,
            "atr_pct": atr_pct,
            "vol_score": vol_score,
            # momentum_score will be set after universe ranking
            "momentum_score": 0.0,
        }

    # ── momentum ranking (cross-sectional) ───────────────────────────────

    def _rank_momentum(self, results: List[dict]) -> None:
        """Assign percentile-rank momentum scores across the universe in place."""
        combined = []
        for r in results:
            avg_mom = (r["mom_1m"] + r["mom_3m"] + r["mom_6m"]) / 3.0
            combined.append(avg_mom)

        arr = np.array(combined)
        # Percentile rank: 0-100
        ranks = np.argsort(np.argsort(arr)).astype(float)
        if len(ranks) > 1:
            ranks = ranks / (len(ranks) - 1) * 100
        else:
            ranks = np.array([50.0])

        for r, score in zip(results, ranks):
            r["momentum_score"] = float(score)

    # ── factor scoring helpers ───────────────────────────────────────────

    @staticmethod
    def _score_moving_avg(
        above_50: bool,
        above_200: bool,
        golden_cross: bool,
        sma50_slope: float,
    ) -> float:
        """Score 0–100 based on moving-average alignment."""
        score = 0.0
        if above_50:
            score += 25
        if above_200:
            score += 25
        if golden_cross:
            score += 25
        # Slope contribution (clamped -25..+25)
        slope_score = max(-25, min(25, sma50_slope * 10))
        score += slope_score
        return max(0.0, min(100.0, score))

    def _score_rsi(self, rsi: float) -> float:
        """
        Score RSI for a trend-following + mean-reversion hybrid.

        - Sweet spot (40–60) → highest scores
        - Moderately overbought (60-70) → still good in uptrend
        - Extreme overbought (>70) → penalized
        - Oversold (<30) → moderate score (potential reversal buy)
        """
        if 45 <= rsi <= 55:
            return 90.0
        elif 40 <= rsi <= 60:
            return 80.0
        elif 55 < rsi <= 65:
            return 70.0
        elif 35 <= rsi < 40:
            return 65.0
        elif 65 < rsi <= 70:
            return 55.0
        elif 30 <= rsi < 35:
            return 50.0  # mildly oversold — possible reversal
        elif rsi < 30:
            return 40.0  # deeply oversold — risky but contrarian opportunity
        elif 70 < rsi <= 80:
            return 35.0
        else:  # RSI > 80
            return 15.0

    @staticmethod
    def _score_volume_volatility(
        vol_trend: float, atr_pct: float, uptrend: bool
    ) -> float:
        """
        Score 0–100 combining volume trend and volatility.

        High volume confirming an uptrend is positive.
        Low volatility (low ATR%) preferred for stability.
        """
        score = 50.0  # neutral baseline

        # Volume trend component (-20 .. +25)
        if uptrend:
            # Rising volume in uptrend = bullish confirmation
            if vol_trend > 1.2:
                score += 25
            elif vol_trend > 1.0:
                score += 15
            else:
                score += 5
        else:
            # Rising volume in downtrend = bearish confirmation
            if vol_trend > 1.2:
                score -= 20
            elif vol_trend > 1.0:
                score -= 10

        # Volatility component (-25 .. +25)
        if atr_pct < 0.8:
            score += 25  # very low vol — stable
        elif atr_pct < 1.2:
            score += 15
        elif atr_pct < 2.0:
            score += 0
        elif atr_pct < 3.0:
            score -= 15
        else:
            score -= 25  # very volatile

        return max(0.0, min(100.0, score))

    # ── technical indicator helpers ──────────────────────────────────────

    @staticmethod
    def _pct_return(close: pd.Series, periods: int) -> float:
        """Percentage return over the last *periods* trading days."""
        if len(close) <= periods:
            return 0.0
        old = float(close.iloc[-periods - 1])
        new = float(close.iloc[-1])
        return ((new - old) / old * 100) if old != 0 else 0.0

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int = 14) -> float:
        """Compute the latest RSI value using exponential moving averages."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        val = float(rsi.iloc[-1])
        return val if not np.isnan(val) else 50.0

    @staticmethod
    def _compute_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> float:
        """Compute the latest Average True Range."""
        prev_close = close.shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean()
        val = float(atr.iloc[-1])
        return val if not np.isnan(val) else 0.0
