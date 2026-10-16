# ETF Analyzer 📊

Automated daily ETF market analysis with email notifications. Scores 27 major ETFs using a multi-factor system and sends you buy/sell recommendations every morning.

## Features

- **Multi-factor scoring** — momentum, moving averages, RSI, and volume/volatility combined into a 0–100 composite score
- **Buy/sell signals** — actionable recommendations with human-readable reasoning
- **Portfolio tracking** — tracks positions, P&L, and days held in a local JSON file
- **Email reports** — beautiful HTML emails with color-coded scorecard
- **Daily scheduler** — runs automatically on weekday mornings
- **Backtesting** — simple 6-month historical backtest to validate the strategy

## Quick Start

### 1. Install dependencies

```bash
cd etf-analyzer
pip install -r requirements.txt
```

### 2. Configure email

Copy the example env file and fill in your Gmail credentials:

```bash
cp .env.example .env
```

Edit `.env` with your details:

```env
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=your.email@gmail.com
```

### 3. Get a Gmail App Password

> **Important:** You need a Gmail **App Password**, not your regular password.

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** and generate a password
5. Copy the 16-character password into your `.env` file

### 4. Run the analyzer

```bash
# Run analysis once and send email
python main.py run

# Start the daily scheduler (runs Mon-Fri at 7:00 AM)
python main.py schedule

# View your current portfolio
python main.py portfolio

# Run a 6-month backtest
python main.py backtest
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py run` | Run analysis now, send email report |
| `python main.py schedule` | Start daily scheduler (weekdays at 7:00 AM) |
| `python main.py portfolio` | Display current portfolio |
| `python main.py backtest` | 6-month historical backtest |

Add `-v` or `--verbose` for debug logging.

## Configuration

Edit `config.py` to customize:

- **ETF universe** — add/remove tickers from `ETF_UNIVERSE`
- **Analysis weights** — adjust factor weights in `AnalysisConfig`
- **Signal thresholds** — tune buy/sell score thresholds in `SignalConfig`
- **Portfolio limits** — max positions, initial capital in `PortfolioConfig`
- **Schedule time** — change run hour/minute in `SchedulerConfig`
- **Timezone** — set your local timezone in `SchedulerConfig`

## Scoring System

Each ETF receives a composite score (0–100) from four equally-weighted factors:

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| **Momentum** | 25% | 1/3/6-month returns, percentile-ranked across universe |
| **Moving Averages** | 25% | Price vs SMA50/200, golden/death cross, trend slope |
| **RSI** | 25% | 14-day RSI — rewards neutral zone, penalizes extremes |
| **Volume & Volatility** | 25% | Volume trend confirmation, ATR stability |

## Project Structure

```
etf-analyzer/
├── main.py             # CLI entry point
├── config.py           # All configuration
├── market_data.py      # Yahoo Finance data fetching
├── analysis.py         # Multi-factor scoring engine
├── signals.py          # Buy/sell signal generation
├── portfolio.py        # Position tracking & P&L
├── report.py           # HTML email report builder
├── email_notifier.py   # Gmail SMTP sender
├── scheduler.py        # APScheduler daily daemon
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── portfolio.json      # Auto-generated position storage
```

## ⚠️ Disclaimer

This tool is for **educational and informational purposes only**. It is **not financial advice**. Always do your own research and consult a qualified financial advisor before making investment decisions. Past performance does not guarantee future results. The authors are not responsible for any financial losses.
