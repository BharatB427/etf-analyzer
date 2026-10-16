"""
Configuration module for the ETF Analyzer application.

Centralizes all configurable parameters including the ETF universe,
analysis thresholds, email settings, scheduling, and portfolio limits.
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


# ── ETF Universe ─────────────────────────────────────────────────────────────

ETF_UNIVERSE: List[str] = [
    # Broad Market
    "SPY",   # S&P 500
    "QQQ",   # Nasdaq 100
    "IWM",   # Russell 2000 (small-cap)
    "DIA",   # Dow Jones Industrial Average
    "VTI",   # Total US Stock Market
    "VOO",   # Vanguard S&P 500

    # International
    "EFA",   # Developed Markets ex-US
    "EEM",   # Emerging Markets
    "VWO",   # Vanguard Emerging Markets

    # Sectors
    "XLK",   # Technology
    "XLF",   # Financials
    "XLE",   # Energy
    "XLV",   # Healthcare
    "XLI",   # Industrials
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLRE",  # Real Estate
    "XLB",   # Materials
    "XLC",   # Communication Services
    "XLY",   # Consumer Discretionary

    # Commodities & Alternatives
    "GLD",   # Gold
    "SLV",   # Silver
    "VNQ",   # REITs

    # Fixed Income
    "TLT",   # 20+ Year Treasury
    "HYG",   # High Yield Corporate Bonds
    "LQD",   # Investment Grade Corporate Bonds

    # Thematic
    "ARKK",  # ARK Innovation
]


# ── Analysis Parameters ──────────────────────────────────────────────────────

@dataclass
class AnalysisConfig:
    """Parameters controlling the technical analysis scoring engine."""

    # Momentum lookback periods (trading days)
    momentum_1m_period: int = 21
    momentum_3m_period: int = 63
    momentum_6m_period: int = 126

    # Moving average periods
    sma_short_period: int = 50
    sma_long_period: int = 200
    sma_slope_period: int = 10  # days to measure SMA slope

    # RSI
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # Volume & Volatility
    volume_short_period: int = 20
    volume_long_period: int = 50
    atr_period: int = 14

    # Factor weights (must sum to 1.0)
    weight_momentum: float = 0.25
    weight_moving_avg: float = 0.25
    weight_rsi: float = 0.25
    weight_volume_volatility: float = 0.25

    # Data lookback for yfinance download
    data_lookback_days: int = 365


# ── Signal Thresholds ────────────────────────────────────────────────────────

@dataclass
class SignalConfig:
    """Thresholds that drive buy/sell/hold signal generation."""

    strong_buy_threshold: float = 75.0
    buy_threshold: float = 65.0
    hold_threshold: float = 40.0
    sell_threshold: float = 40.0    # score below this → SELL
    strong_sell_threshold: float = 25.0

    top_n_recommendations: int = 5  # how many BUY picks to show


# ── Portfolio ────────────────────────────────────────────────────────────────

@dataclass
class PortfolioConfig:
    """Portfolio management settings."""

    max_positions: int = 5
    portfolio_file: str = "portfolio.json"
    initial_capital: float = 100_000.0


# ── Email ────────────────────────────────────────────────────────────────────

@dataclass
class EmailConfig:
    """Gmail SMTP email settings. Credentials come from environment variables."""

    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = field(default_factory=lambda: os.getenv("EMAIL_ADDRESS", ""))
    sender_password: str = field(default_factory=lambda: os.getenv("EMAIL_PASSWORD", ""))
    recipient_email: str = field(default_factory=lambda: os.getenv("RECIPIENT_EMAIL", ""))
    max_retries: int = 3
    retry_delay_seconds: int = 5

    def is_configured(self) -> bool:
        """Return True if all required email fields are set."""
        return bool(self.sender_email and self.sender_password and self.recipient_email)


# ── Scheduler ────────────────────────────────────────────────────────────────

@dataclass
class SchedulerConfig:
    """Daily scheduler settings."""

    run_hour: int = 7
    run_minute: int = 0
    timezone: str = "Europe/Berlin"  # adjust to your local timezone


# ── Logging ──────────────────────────────────────────────────────────────────

LOG_FILE: str = "etf_analyzer.log"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
