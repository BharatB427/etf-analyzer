"""
HTML report generator for email notifications.

Produces a styled, colour-coded report containing market overview,
buy/sell recommendations, portfolio summary, and a full ETF scorecard.
"""

import logging
from datetime import datetime
from typing import Dict, List

from analysis import ETFAnalysis
from portfolio import PortfolioSummary
from signals import Signal, SignalType

logger = logging.getLogger(__name__)


def _score_color(score: float) -> str:
    """Return an inline CSS color for a composite score."""
    if score >= 75:
        return "#16a34a"   # green
    elif score >= 65:
        return "#65a30d"   # lime
    elif score >= 50:
        return "#ca8a04"   # amber
    elif score >= 40:
        return "#ea580c"   # orange
    else:
        return "#dc2626"   # red


def _pnl_color(value: float) -> str:
    return "#16a34a" if value >= 0 else "#dc2626"


def _signal_badge(sig: SignalType) -> str:
    """Return an HTML badge for a signal type."""
    colors = {
        SignalType.STRONG_BUY: ("#dcfce7", "#166534"),
        SignalType.BUY: ("#ecfdf5", "#065f46"),
        SignalType.HOLD: ("#fefce8", "#854d0e"),
        SignalType.SELL: ("#fff7ed", "#9a3412"),
        SignalType.STRONG_SELL: ("#fef2f2", "#991b1b"),
    }
    bg, fg = colors.get(sig, ("#f3f4f6", "#374151"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:12px;font-weight:600;font-size:13px;">'
        f"{sig.value}</span>"
    )


class ReportGenerator:
    """Build rich HTML email reports."""

    def generate(
        self,
        analyses: List[ETFAnalysis],
        signals: Dict[str, List[Signal]],
        portfolio: PortfolioSummary,
        run_timestamp: datetime | None = None,
    ) -> str:
        """Return a complete HTML email string."""
        ts = run_timestamp or datetime.now()
        date_str = ts.strftime("%A, %B %d, %Y at %H:%M")

        html_parts = [
            self._header(date_str),
            self._market_overview(analyses),
            self._buy_section(signals.get("buy", [])),
            self._sell_section(signals.get("sell", [])),
            self._portfolio_section(portfolio),
            self._scorecard(analyses),
            self._disclaimer(),
            self._footer(),
        ]
        return "\n".join(html_parts)

    # ── sections ─────────────────────────────────────────────────────────

    def _header(self, date_str: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:
  -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:700px;margin:20px auto;background:#fff;
  border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,.07);">

  <!-- Banner -->
  <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);
    padding:30px 32px;color:#fff;">
    <h1 style="margin:0;font-size:26px;">📊 ETF Market Analysis</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:14px;">{date_str}</p>
  </div>
  <div style="padding:24px 32px;">
"""

    def _market_overview(self, analyses: List[ETFAnalysis]) -> str:
        spy = next((a for a in analyses if a.ticker == "SPY"), None)
        qqq = next((a for a in analyses if a.ticker == "QQQ"), None)

        avg_score = sum(a.composite_score for a in analyses) / len(analyses) if analyses else 0
        bullish = sum(1 for a in analyses if a.golden_cross)
        total = len(analyses)

        html = '<h2 style="color:#1e3a5f;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">Market Overview</h2>'
        html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;">'

        if spy:
            color = _pnl_color(spy.momentum_1m)
            html += f"""<tr>
              <td style="padding:6px 0;color:#64748b;">S&P 500 (SPY)</td>
              <td style="padding:6px 0;font-weight:600;">${spy.close_price:.2f}</td>
              <td style="padding:6px 0;color:{color};font-weight:600;">{spy.momentum_1m:+.1f}% (1M)</td>
            </tr>"""
        if qqq:
            color = _pnl_color(qqq.momentum_1m)
            html += f"""<tr>
              <td style="padding:6px 0;color:#64748b;">Nasdaq 100 (QQQ)</td>
              <td style="padding:6px 0;font-weight:600;">${qqq.close_price:.2f}</td>
              <td style="padding:6px 0;color:{color};font-weight:600;">{qqq.momentum_1m:+.1f}% (1M)</td>
            </tr>"""

        html += f"""<tr>
          <td style="padding:6px 0;color:#64748b;">Universe Avg Score</td>
          <td style="padding:6px 0;font-weight:600;color:{_score_color(avg_score)};">{avg_score:.1f} / 100</td>
          <td style="padding:6px 0;color:#64748b;">Breadth: {bullish}/{total} bullish</td>
        </tr></table>"""
        return html

    def _buy_section(self, buys: List[Signal]) -> str:
        if not buys:
            return '<h2 style="color:#16a34a;">🟢 Buy Recommendations</h2><p style="color:#64748b;">No strong buy signals today.</p>'

        html = '<h2 style="color:#16a34a;">🟢 Buy Recommendations</h2>'
        for s in buys:
            html += f"""
            <div style="background:#f0fdf4;border-left:4px solid #16a34a;
              padding:14px 18px;margin-bottom:12px;border-radius:0 8px 8px 0;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:18px;font-weight:700;">{s.ticker}</span>
                {_signal_badge(s.signal_type)}
              </div>
              <div style="margin-top:6px;font-size:14px;color:#374151;">
                Score: <strong style="color:{_score_color(s.composite_score)};">{s.composite_score:.1f}</strong>
                &nbsp;|&nbsp; Price: <strong>${s.close_price:.2f}</strong>
              </div>
              <div style="margin-top:6px;font-size:13px;color:#64748b;">{s.reasoning}</div>
            </div>"""
        return html

    def _sell_section(self, sells: List[Signal]) -> str:
        if not sells:
            return '<h2 style="color:#dc2626;">🔴 Sell Alerts</h2><p style="color:#64748b;">No sell signals for current holdings.</p>'

        html = '<h2 style="color:#dc2626;">🔴 Sell Alerts</h2>'
        for s in sells:
            html += f"""
            <div style="background:#fef2f2;border-left:4px solid #dc2626;
              padding:14px 18px;margin-bottom:12px;border-radius:0 8px 8px 0;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:18px;font-weight:700;">{s.ticker}</span>
                {_signal_badge(s.signal_type)}
              </div>
              <div style="margin-top:6px;font-size:14px;color:#374151;">
                Score: <strong style="color:{_score_color(s.composite_score)};">{s.composite_score:.1f}</strong>
                &nbsp;|&nbsp; Price: <strong>${s.close_price:.2f}</strong>
              </div>
              <div style="margin-top:6px;font-size:13px;color:#64748b;">{s.reasoning}</div>
            </div>"""
        return html

    def _portfolio_section(self, pf: PortfolioSummary) -> str:
        html = '<h2 style="color:#1e3a5f;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">💼 Portfolio Summary</h2>'

        if pf.position_count == 0:
            html += '<p style="color:#64748b;">No positions held. Follow buy signals above to get started.</p>'
            return html

        color = _pnl_color(pf.total_pnl_dollar)
        html += f"""
        <div style="display:flex;gap:20px;margin-bottom:16px;flex-wrap:wrap;">
          <div style="background:#f1f5f9;padding:12px 20px;border-radius:8px;flex:1;min-width:140px;">
            <div style="font-size:12px;color:#64748b;">Total Value</div>
            <div style="font-size:22px;font-weight:700;">${pf.total_value:,.2f}</div>
          </div>
          <div style="background:#f1f5f9;padding:12px 20px;border-radius:8px;flex:1;min-width:140px;">
            <div style="font-size:12px;color:#64748b;">Total P&L</div>
            <div style="font-size:22px;font-weight:700;color:{color};">
              ${pf.total_pnl_dollar:+,.2f} ({pf.total_pnl_pct:+.1f}%)
            </div>
          </div>
          <div style="background:#f1f5f9;padding:12px 20px;border-radius:8px;flex:1;min-width:140px;">
            <div style="font-size:12px;color:#64748b;">Positions</div>
            <div style="font-size:22px;font-weight:700;">{pf.position_count}</div>
          </div>
        </div>"""

        # Positions table
        html += """<table style="width:100%;border-collapse:collapse;font-size:13px;">
          <tr style="background:#f1f5f9;">
            <th style="padding:8px;text-align:left;">Ticker</th>
            <th style="padding:8px;text-align:right;">Entry</th>
            <th style="padding:8px;text-align:right;">Current</th>
            <th style="padding:8px;text-align:right;">P&L</th>
            <th style="padding:8px;text-align:right;">Days</th>
          </tr>"""
        for p in pf.positions:
            c = _pnl_color(p.pnl_pct)
            html += f"""<tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:8px;font-weight:600;">{p.ticker}</td>
              <td style="padding:8px;text-align:right;">${p.entry_price:.2f}</td>
              <td style="padding:8px;text-align:right;">${p.current_price:.2f}</td>
              <td style="padding:8px;text-align:right;color:{c};font-weight:600;">
                {p.pnl_pct:+.1f}% (${p.pnl_dollar:+,.0f})
              </td>
              <td style="padding:8px;text-align:right;">{p.days_held}d</td>
            </tr>"""
        html += "</table>"
        return html

    def _scorecard(self, analyses: List[ETFAnalysis]) -> str:
        html = """
        <h2 style="color:#1e3a5f;border-bottom:2px solid #e2e8f0;
          padding-bottom:8px;margin-top:28px;">📋 Full ETF Scorecard</h2>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <tr style="background:#1e3a5f;color:#fff;">
            <th style="padding:8px;text-align:left;">Rank</th>
            <th style="padding:8px;text-align:left;">Ticker</th>
            <th style="padding:8px;text-align:right;">Price</th>
            <th style="padding:8px;text-align:right;">Score</th>
            <th style="padding:8px;text-align:right;">Mom</th>
            <th style="padding:8px;text-align:right;">MA</th>
            <th style="padding:8px;text-align:right;">RSI</th>
            <th style="padding:8px;text-align:right;">Vol</th>
            <th style="padding:8px;text-align:center;">Trend</th>
          </tr>"""

        for i, a in enumerate(analyses, 1):
            bg = "#fff" if i % 2 else "#f8fafc"
            sc = _score_color(a.composite_score)
            trend = "🟢" if a.golden_cross and a.above_sma_50 else ("🟡" if a.golden_cross else "🔴")
            html += f"""<tr style="background:{bg};border-bottom:1px solid #e2e8f0;">
              <td style="padding:6px 8px;">{i}</td>
              <td style="padding:6px 8px;font-weight:600;">{a.ticker}</td>
              <td style="padding:6px 8px;text-align:right;">${a.close_price:.2f}</td>
              <td style="padding:6px 8px;text-align:right;font-weight:700;color:{sc};">{a.composite_score:.1f}</td>
              <td style="padding:6px 8px;text-align:right;">{a.factor_scores.momentum:.0f}</td>
              <td style="padding:6px 8px;text-align:right;">{a.factor_scores.moving_avg:.0f}</td>
              <td style="padding:6px 8px;text-align:right;">{a.factor_scores.rsi:.0f}</td>
              <td style="padding:6px 8px;text-align:right;">{a.factor_scores.volume_volatility:.0f}</td>
              <td style="padding:6px 8px;text-align:center;">{trend}</td>
            </tr>"""
        html += "</table>"
        return html

    def _disclaimer(self) -> str:
        return """
        <div style="margin-top:28px;padding:16px;background:#fffbeb;
          border:1px solid #fde68a;border-radius:8px;font-size:12px;color:#92400e;">
          <strong>⚠️ Disclaimer:</strong> This is algorithmic analysis for
          <strong>educational purposes only</strong>. It is <strong>not financial
          advice</strong>. Always do your own research and consult a qualified
          financial advisor before making investment decisions. Past performance
          does not guarantee future results.
        </div>"""

    def _footer(self) -> str:
        return """
  </div>
  <div style="padding:16px 32px;background:#f1f5f9;text-align:center;
    font-size:11px;color:#94a3b8;">
    ETF Analyzer • Automated Market Intelligence<br>
    Generated by your personal trading analysis system
  </div>
</div></body></html>"""
