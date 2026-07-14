# SPY/QQQ Paper-Trading Bot

An automated daily swing bot that paper-trades SPY and QQQ on Alpaca, gated by a
daily risk posture produced by a headless Claude Code run on a Claude Pro
subscription. Total running cost: **$0**.

## Read this first: what this bot will and won't do

**No bot only wins.** Win rate is a manipulable number — martingale-style systems
post 90%+ win rates right up until one losing streak ends the account. This bot
targets **positive expectancy**: many small wins, small capped losses, judged on
profit factor, expectancy, and max drawdown. Published long-run results for this
strategy class (RSI(2) mean reversion + 200-day trend filter on SPY):

- win rate ~55–75%
- profit factor ~1.3–2.0
- returns roughly market-like, with **about half the drawdown** of buy-and-hold
- some trades and some whole months **will lose** — by design, losses stay small

Alpaca's paper fills are optimistic (no slippage, no dividends), so live results
would run below paper results. The backtest models costs explicitly; the paper
account is the out-of-sample proving ground. Paper trade **at least a month**
before even discussing real money.

## How it works

```
Job A (weekdays ~8:45 AM ET)          Job B (weekdays ~3:45 PM ET)
claude -p (Pro plan, headless)        python run_bot.py
  market-breadth-analyzer               1. NYSE calendar guard
  ibd-distribution-day-monitor          2. fetch daily bars (Alpaca IEX, free)
        │                               3. signals: 200-SMA regime + RSI(2)<10
        ▼                               4. clamp by posture.json + kill switches
  posture/posture.json  ──────────────► 5. whole-share OTO orders (market+stop)
  {"posture": "...", "max_exposure":…}  6. journal to logs/*.csv
```

- **Rules trade, Claude gates.** The Python layer is deterministic and
  backtestable. Claude's posture can only *reduce* exposure (RISK_ON 90% /
  NEUTRAL 50% / RISK_OFF 0%), never add risk. If posture.json is missing,
  stale (>24h), or invalid, the bot silently degrades to NEUTRAL.
- **Kill switches:** 15% drawdown from peak or 3 consecutive losses halts new
  entries until you run `python run_bot.py --resume`.
- **Idempotent:** re-running the same day cannot double-enter
  (`client_order_id` is derived from symbol+date).

## Setup (one time, ~15 minutes)

1. **Alpaca keys (free):** sign up at <https://alpaca.markets>, switch the
   dashboard (upper-left selector) to **Paper Trading**, generate an API key.
   The secret is shown once — copy it immediately.
   `copy .env.example .env` and fill both values in.
2. **Python env** (lives outside iCloud so sync never touches it):
   ```
   py -3.12 -m venv C:\Users\abbas\.venvs\spy-qqq-bot
   C:\Users\abbas\.venvs\spy-qqq-bot\Scripts\pip install -r requirements.txt
   ```
3. **Backtest gate** (do not skip — if this fails, don't run the bot):
   ```
   C:\Users\abbas\.venvs\spy-qqq-bot\Scripts\python backtest\get_history.py
   C:\Users\abbas\.venvs\spy-qqq-bot\Scripts\python backtest\backtest.py --sweep
   ```
   Ship only if out-of-sample profit factor > 1.3 and max drawdown is well
   below buy-and-hold, across a *plateau* of nearby parameters (not one spike).
4. **Dry run:** `...\python run_bot.py --paper-dry` — logs intended orders,
   submits nothing, works before keys exist.
5. **Schedule:** `powershell -ExecutionPolicy Bypass -File ops\register_tasks.ps1`
   registers both weekday jobs and prints your machine's sleep capabilities.
   If it reports Modern Standby (S0 Low Power Idle), keep the PC awake during
   market hours — wake timers won't fire reliably.
6. **(Optional but recommended) durable Claude auth for Job A:**
   `claude setup-token` mints a 1-year token; cached browser logins can fail to
   refresh in unattended runs. Never set `ANTHROPIC_API_KEY` in this
   environment (it would silently override subscription auth), and never pass
   `--bare` to claude (it skips subscription auth entirely).

## Daily operation

Nothing. Job A writes the posture, Job B trades, both append to `logs/`.
Check in weekly:

- `logs/trades.csv` — every action with reason and posture
- `logs/equity_curve.csv` — daily equity
- `logs/bot.log`, `logs/posture.log` — full run output
- Alpaca paper dashboard — positions and orders
- run the `signal-postmortem` skill on the trade log for a weekly review

## Runbook

| Situation | What to do |
|---|---|
| Kill switch tripped | Read the reason in `logs/bot.log`, review trades, then `python run_bot.py --resume` |
| Posture missing/stale | Bot already degraded to NEUTRAL; check `logs/posture.log` |
| Missed a day (PC off) | Task fires on wake ("run ASAP after missed start"); a delayed run still manages exits but won't enter outside the last 75 min before the close |
| Emergency stop | Disable both tasks in Task Scheduler; positions still have resting stop orders |
| Change parameters | Edit `config.yaml`, re-run the backtest gate before trading on |

## Future: real money (not now)

Only after ≥1 month of paper results that match the backtest. Options, in order:
1. Alpaca live account — same code, live keys, `paper=False` (deliberate change).
2. Robinhood Agentic Trading (official MCP beta, real money, no paper mode):
   `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`
   — requires beta access from Robinhood; keep the same posture+rules design.

## Layout

```
bot/            strategy (pure logic), data, broker, risk, posture, calendar, journal
backtest/       get_history.py (download), backtest.py (replay + --sweep)
posture/        Claude posture prompt, runner, output JSON
ops/            run_bot.cmd, register_tasks.ps1
tests/          test_strategy.py (python tests/test_strategy.py)
logs/, data/    runtime artifacts (gitignored)
```
