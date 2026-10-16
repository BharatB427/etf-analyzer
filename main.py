"""
ETF Analyzer — main entry point.

Commands
--------
  python main.py run        Run analysis once and send an email report.
  python main.py schedule   Start the daily scheduler daemon.
  python main.py portfolio  Show current portfolio holdings.
  python main.py backtest   Simple back-test over the last 6 months.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Force UTF-8 console output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import (
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    AnalysisConfig,
    EmailConfig,
    ETF_UNIVERSE,
    PortfolioConfig,
    SchedulerConfig,
    SignalConfig,
)
from analysis import AnalysisEngine, ETFAnalysis
from email_notifier import EmailNotifier
from market_data import MarketDataFetcher
from portfolio import PortfolioManager
from report import ReportGenerator
from scheduler import DailyScheduler
from signals import SignalGenerator

logger = logging.getLogger("etf_analyzer")


# ── Logging setup ────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


# ── Core pipeline ────────────────────────────────────────────────────────────

def run_analysis() -> None:
    """Execute the full analysis pipeline: fetch → analyze → signal → report → email."""
    logger.info("=" * 60)
    logger.info("ETF Analyzer — starting analysis run")
    logger.info("=" * 60)

    # 1. Fetch market data
    fetcher = MarketDataFetcher()
    data = fetcher.fetch_all()
    if not data:
        logger.error("No market data available — aborting.")
        return

    # 2. Run multi-factor analysis
    engine = AnalysisEngine()
    analyses = engine.analyze_universe(data)
    if not analyses:
        logger.error("Analysis produced no results — aborting.")
        return

    # 3. Portfolio — update prices
    pm = PortfolioManager()
    prices = {a.ticker: a.close_price for a in analyses}
    pm.update_prices(prices)

    # 4. Generate signals
    sig_gen = SignalGenerator()
    signals = sig_gen.generate(analyses, pm.get_held_tickers())

    # 5. Build report
    portfolio_summary = pm.get_summary()
    rg = ReportGenerator()
    html = rg.generate(analyses, signals, portfolio_summary)

    # 6. Send email
    notifier = EmailNotifier()
    today = datetime.now().strftime("%Y-%m-%d")
    buy_count = len(signals.get("buy", []))
    sell_count = len(signals.get("sell", []))
    subject = f"📊 ETF Analysis — {today} | {buy_count} Buy, {sell_count} Sell signals"
    sent = notifier.send(subject, html)

    if not sent:
        # Save report locally as fallback
        report_path = Path(f"report_{today}.html")
        report_path.write_text(html, encoding="utf-8")
        logger.info("Email failed — report saved to %s", report_path)

    # 7. Print summary to console
    _print_summary(analyses, signals)
    logger.info("Analysis run complete.")


def _print_summary(
    analyses: List[ETFAnalysis],
    signals: Dict[str, list],
) -> None:
    """Print a concise console summary."""
    print("\n" + "=" * 60)
    print("  TOP 5 ETFs BY COMPOSITE SCORE")
    print("=" * 60)
    for a in analyses[:5]:
        trend = "[+]" if a.golden_cross and a.above_sma_50 else "[-]"
        print(
            f"  {trend} {a.ticker:<6} Score: {a.composite_score:5.1f}  "
            f"Price: ${a.close_price:8.2f}  RSI: {a.rsi_value:5.1f}"
        )

    if signals.get("buy"):
        print("\n  >> BUY SIGNALS:")
        for s in signals["buy"]:
            print(f"     {s.signal_type.value:12} {s.ticker:<6} (Score: {s.composite_score:.1f})")

    if signals.get("sell"):
        print("\n  << SELL SIGNALS:")
        for s in signals["sell"]:
            print(f"     {s.signal_type.value:12} {s.ticker:<6} (Score: {s.composite_score:.1f})")

    print("=" * 60 + "\n")


# ── Backtest ─────────────────────────────────────────────────────────────────

def run_backtest() -> None:
    """
    Simple historical backtest: replay the scoring strategy over the last
    6 months, rebalancing monthly into the top-5 ETFs.
    """
    import numpy as np
    import pandas as pd

    logger.info("Starting 6-month backtest …")

    fetcher = MarketDataFetcher()
    data = fetcher.fetch_all()
    if not data:
        logger.error("No data for backtest.")
        return

    # Use SPY as benchmark
    spy_data = data.get("SPY")
    if spy_data is None:
        logger.error("SPY data missing — cannot benchmark.")
        return

    # Monthly rebalance dates (last ~6 months, every ~21 trading days)
    reference_df = spy_data
    total_days = len(reference_df)
    rebalance_interval = 21
    start_idx = max(0, total_days - 126)  # ~6 months

    portfolio_value = 100_000.0
    benchmark_start = float(reference_df["Close"].iloc[start_idx])
    holdings: Dict[str, float] = {}  # ticker → shares

    print("\n" + "=" * 60)
    print("  6-MONTH BACKTEST (monthly rebalance, top 5)")
    print("=" * 60)

    engine = AnalysisEngine()

    for step_idx in range(start_idx, total_days, rebalance_interval):
        # Slice data up to this point
        sliced = {t: df.iloc[: step_idx + 1] for t, df in data.items() if len(df) > step_idx}
        if len(sliced) < 10:
            continue

        analyses = engine.analyze_universe(sliced)
        top5 = [a.ticker for a in analyses[:5]]

        # Calculate current portfolio value
        if holdings:
            portfolio_value = sum(
                shares * float(data[t]["Close"].iloc[step_idx])
                for t, shares in holdings.items()
                if t in data and len(data[t]) > step_idx
            )

        # Rebalance: equal-weight into top 5
        per_position = portfolio_value / 5
        holdings = {}
        for ticker in top5:
            if ticker in data and len(data[ticker]) > step_idx:
                price = float(data[ticker]["Close"].iloc[step_idx])
                if price > 0:
                    holdings[ticker] = per_position / price

        date_label = reference_df.index[step_idx].strftime("%Y-%m-%d")
        print(f"  {date_label}  Value: ${portfolio_value:>12,.2f}  Holdings: {', '.join(top5)}")

    # Final value
    if holdings:
        portfolio_value = sum(
            shares * float(data[t]["Close"].iloc[-1])
            for t, shares in holdings.items()
            if t in data
        )

    benchmark_end = float(reference_df["Close"].iloc[-1])
    benchmark_return = (benchmark_end - benchmark_start) / benchmark_start * 100
    strategy_return = (portfolio_value - 100_000) / 100_000 * 100

    print(f"\n  Final Value:       ${portfolio_value:>12,.2f}")
    print(f"  Strategy Return:   {strategy_return:>+.2f}%")
    print(f"  SPY Benchmark:     {benchmark_return:>+.2f}%")
    print(f"  Alpha:             {strategy_return - benchmark_return:>+.2f}%")
    print("=" * 60 + "\n")


# ── Portfolio display ────────────────────────────────────────────────────────

def show_portfolio() -> None:
    """Print current portfolio to console."""
    pm = PortfolioManager()

    # Update prices
    fetcher = MarketDataFetcher()
    prices = {}
    for ticker in pm.get_held_tickers():
        price = fetcher.get_latest_price(ticker)
        if price is not None:
            prices[ticker] = price
    pm.update_prices(prices)

    summary = pm.get_summary()
    if summary.position_count == 0:
        print("\n  Portfolio is empty. Run 'python main.py run' to get started.\n")
        return

    print("\n" + "=" * 60)
    print("  CURRENT PORTFOLIO")
    print("=" * 60)
    print(f"  Total Value:  ${summary.total_value:>12,.2f}")
    print(f"  Total Cost:   ${summary.total_cost:>12,.2f}")
    pnl_sign = "+" if summary.total_pnl_dollar >= 0 else ""
    print(
        f"  Total P&L:    {pnl_sign}${summary.total_pnl_dollar:>11,.2f} "
        f"({pnl_sign}{summary.total_pnl_pct:.1f}%)"
    )
    print("-" * 60)
    print(f"  {'Ticker':<8} {'Entry':>8} {'Current':>8} {'P&L%':>8} {'Days':>6}")
    print("-" * 60)
    for p in summary.positions:
        sign = "+" if p.pnl_pct >= 0 else ""
        print(
            f"  {p.ticker:<8} ${p.entry_price:>7.2f} ${p.current_price:>7.2f} "
            f"{sign}{p.pnl_pct:>6.1f}% {p.days_held:>5}d"
        )
    print("=" * 60 + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ETF Analyzer",
        description="Daily ETF market analysis with email notifications.",
    )
    parser.add_argument(
        "command",
        choices=["run", "schedule", "backtest", "portfolio"],
        help="Action to perform.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.command == "run":
        run_analysis()

    elif args.command == "schedule":
        logger.info("Starting daily scheduler …")
        sched = DailyScheduler(job_func=run_analysis)
        sched.start()

    elif args.command == "backtest":
        run_backtest()

    elif args.command == "portfolio":
        show_portfolio()


if __name__ == "__main__":
    main()
