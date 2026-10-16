"""
Market data module — fetches OHLCV data from Yahoo Finance via yfinance.

Handles downloading, caching (per-session), and error recovery for all
ETFs in the configured universe.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from config import AnalysisConfig, ETF_UNIVERSE

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Downloads and caches daily OHLCV data for a set of ETF tickers."""

    def __init__(self, config: Optional[AnalysisConfig] = None) -> None:
        self.config = config or AnalysisConfig()
        self._cache: Dict[str, pd.DataFrame] = {}

    # ── public API ───────────────────────────────────────────────────────

    def fetch_all(self, tickers: Optional[list] = None) -> Dict[str, pd.DataFrame]:
        """
        Download 1-year daily OHLCV data for every ticker in the universe.

        Returns a dict mapping ticker → DataFrame.  Tickers that fail to
        download are logged and skipped (the dict simply won't contain them).
        """
        tickers = tickers or ETF_UNIVERSE
        end_date = datetime.today()
        start_date = end_date - timedelta(days=self.config.data_lookback_days)

        logger.info(
            "Fetching market data for %d tickers (%s -> %s) ...",
            len(tickers),
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        for ticker in tickers:
            if ticker in self._cache:
                logger.debug("Cache hit for %s — skipping download.", ticker)
                continue
            df = self._download_ticker(ticker, start_date, end_date)
            if df is not None and not df.empty:
                self._cache[ticker] = df
            else:
                logger.warning("No data returned for %s — skipped.", ticker)

        logger.info(
            "Market data ready: %d / %d tickers loaded.",
            len(self._cache),
            len(tickers),
        )
        return dict(self._cache)

    def fetch_single(self, ticker: str) -> Optional[pd.DataFrame]:
        """Fetch data for a single ticker (uses cache if available)."""
        if ticker in self._cache:
            return self._cache[ticker]
        end_date = datetime.today()
        start_date = end_date - timedelta(days=self.config.data_lookback_days)
        df = self._download_ticker(ticker, start_date, end_date)
        if df is not None and not df.empty:
            self._cache[ticker] = df
            return df
        return None

    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Return the most recent closing price for *ticker*."""
        df = self.fetch_single(ticker)
        if df is not None and not df.empty:
            return float(df["Close"].iloc[-1])
        return None

    def clear_cache(self) -> None:
        """Wipe the in-memory cache so the next fetch re-downloads."""
        self._cache.clear()
        logger.info("Market data cache cleared.")

    # ── internals ────────────────────────────────────────────────────────

    def _download_ticker(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
    ) -> Optional[pd.DataFrame]:
        """Download OHLCV data for a single ticker with error handling."""
        try:
            logger.debug("Downloading %s …", ticker)
            df: pd.DataFrame = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                return None

            # yfinance may return MultiIndex columns when downloading a
            # single ticker; flatten if needed.
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Ensure expected columns exist
            required = {"Open", "High", "Low", "Close", "Volume"}
            if not required.issubset(set(df.columns)):
                logger.warning(
                    "%s — missing columns: %s",
                    ticker,
                    required - set(df.columns),
                )
                return None

            return df

        except Exception as exc:
            logger.error("Failed to download %s: %s", ticker, exc, exc_info=True)
            return None
