"""
Portfolio tracking module.

Persists positions in a local JSON file and calculates P&L metrics.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import PortfolioConfig

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """A single portfolio position."""
    ticker: str
    entry_date: str            # ISO format "YYYY-MM-DD"
    entry_price: float
    shares: float
    current_price: float = 0.0
    pnl_pct: float = 0.0
    pnl_dollar: float = 0.0
    days_held: int = 0


@dataclass
class PortfolioSummary:
    """Aggregate portfolio stats."""
    total_value: float = 0.0
    total_cost: float = 0.0
    total_pnl_dollar: float = 0.0
    total_pnl_pct: float = 0.0
    position_count: int = 0
    positions: List[Position] = field(default_factory=list)


class PortfolioManager:
    """Manage positions stored in a local JSON file."""

    def __init__(self, config: Optional[PortfolioConfig] = None) -> None:
        self.cfg = config or PortfolioConfig()
        self.filepath = Path(self.cfg.portfolio_file)
        self._positions: Dict[str, dict] = {}
        self._load()

    # ── public API ───────────────────────────────────────────────────────

    def add_position(
        self,
        ticker: str,
        price: float,
        shares: Optional[float] = None,
        allocation: Optional[float] = None,
    ) -> bool:
        """
        Add a new position.  Supply either *shares* or *allocation* (fraction
        of initial capital to invest).  Returns True on success.
        """
        if ticker in self._positions:
            logger.warning("%s already in portfolio — skipping add.", ticker)
            return False
        if len(self._positions) >= self.cfg.max_positions:
            logger.warning(
                "Portfolio full (%d/%d) — cannot add %s.",
                len(self._positions),
                self.cfg.max_positions,
                ticker,
            )
            return False

        if shares is None:
            alloc = allocation or (1.0 / self.cfg.max_positions)
            invest_amount = self.cfg.initial_capital * alloc
            shares = invest_amount / price if price > 0 else 0.0

        self._positions[ticker] = {
            "ticker": ticker,
            "entry_date": date.today().isoformat(),
            "entry_price": price,
            "shares": shares,
            "current_price": price,
        }
        self._save()
        logger.info("Added %s: %.2f shares @ $%.2f", ticker, shares, price)
        return True

    def remove_position(self, ticker: str) -> Optional[Position]:
        """Remove a position and return its final state."""
        if ticker not in self._positions:
            logger.warning("Cannot remove %s — not in portfolio.", ticker)
            return None

        pos = self._to_position(self._positions.pop(ticker))
        self._save()
        logger.info(
            "Removed %s — P&L: $%.2f (%.1f%%)",
            ticker, pos.pnl_dollar, pos.pnl_pct,
        )
        return pos

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Refresh current prices for held positions."""
        for ticker, data in self._positions.items():
            if ticker in prices:
                data["current_price"] = prices[ticker]
        self._save()

    def get_summary(self) -> PortfolioSummary:
        """Return an aggregate portfolio summary."""
        positions = [self._to_position(d) for d in self._positions.values()]
        total_cost = sum(p.entry_price * p.shares for p in positions)
        total_value = sum(p.current_price * p.shares for p in positions)
        total_pnl = total_value - total_cost

        return PortfolioSummary(
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            total_pnl_dollar=round(total_pnl, 2),
            total_pnl_pct=round((total_pnl / total_cost * 100) if total_cost else 0, 2),
            position_count=len(positions),
            positions=positions,
        )

    def get_held_tickers(self) -> set:
        """Return the set of currently held ticker symbols."""
        return set(self._positions.keys())

    def is_full(self) -> bool:
        return len(self._positions) >= self.cfg.max_positions

    # ── persistence ──────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r") as f:
                    self._positions = json.load(f)
                logger.info("Loaded %d positions from %s", len(self._positions), self.filepath)
            except (json.JSONDecodeError, IOError) as exc:
                logger.error("Failed to load portfolio file: %s", exc)
                self._positions = {}
        else:
            self._positions = {}

    def _save(self) -> None:
        try:
            with open(self.filepath, "w") as f:
                json.dump(self._positions, f, indent=2)
        except IOError as exc:
            logger.error("Failed to save portfolio: %s", exc)

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_position(data: dict) -> Position:
        entry_price = data["entry_price"]
        current_price = data.get("current_price", entry_price)
        shares = data["shares"]
        pnl_dollar = (current_price - entry_price) * shares
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0

        entry_date_str = data["entry_date"]
        try:
            days_held = (date.today() - date.fromisoformat(entry_date_str)).days
        except ValueError:
            days_held = 0

        return Position(
            ticker=data["ticker"],
            entry_date=entry_date_str,
            entry_price=entry_price,
            shares=shares,
            current_price=current_price,
            pnl_pct=round(pnl_pct, 2),
            pnl_dollar=round(pnl_dollar, 2),
            days_held=days_held,
        )
