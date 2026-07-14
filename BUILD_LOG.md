# Build Log — 2026-07-13/14

Complete record of how this bot was built, tested, and deployed.

## Goal & ground rules

Automated agentic trading bot for SPY/QQQ at zero additional cost, using a
Claude Pro subscription (no API credits). Original ask was a bot that "strictly
triggers winning trades" — re-framed to the achievable goal: positive
expectancy with capped losses, validated on paper before any real money.

## Decisions (user-approved)

| Decision | Choice | Why |
|---|---|---|
| Platform | Alpaca paper trading | Free official API + unlimited fake money. Robinhood's official Agentic Trading MCP (beta 5/2026) is real-money-only, no paper mode — kept as future upgrade path |
| Cadence | Daily swing | Best-documented edges, fits Pro limits, PC only needed briefly |
| Agentic design | Rules trade, Claude gates | Deterministic Python is backtestable; Claude posture can only reduce risk |
| Runtime | This PC, Task Scheduler | Free; Claude login already here |

## Verified platform facts (5-agent research workflow, July 2026 sources)

- Alpaca paper: free email-only signup, `paper-api.alpaca.markets`, alpaca-py SDK, free IEX data (200 req/min). Bracket/OTO orders require whole shares.
- Claude Pro headless: `claude -p` on subscription auth is officially supported; `claude setup-token` for unattended runs; never `--bare`; never set ANTHROPIC_API_KEY in the job environment.
- This PC is Modern Standby (S0): Task Scheduler wake timers unreliable → keep PC awake/plugged in during market hours.
- Strategy class (RSI(2) + 200-SMA filter): published 65-76% win rates, PF 1.4-2.1, no stop in the classic rules (fat left tail).

## Strategy v1

Long-only, no leverage, whole shares. Entry: close > 200-SMA and RSI(2) < 10.
Exit: RSI(2) > 65, or 10 trading days, or regime break. 3×ATR(14) GTC
catastrophe stop. Posture caps total exposure: RISK_ON 90% / NEUTRAL 50% /
RISK_OFF 0%. Kill switches: 15% drawdown from peak or 3 consecutive losses.

## Backtest results (2000-01-03 → 2026-07-13, 7.5bp slippage + 1¢ spread)

| Period | Trades | Win rate | PF | CAGR | Max DD |
|---|---|---|---|---|---|
| Full | 424 | 71.0% | 1.58 | 2.55% | -15.6% |
| In-sample (→2015) | 241 | 71.0% | 1.70 | 2.78% | -11.8% |
| Out-of-sample (2016→) | 183 | 71.0% | 1.47 | 2.21% | -15.6% |
| Buy & hold SPY (full) | — | — | — | 8.27% | -55.2% |

Gate (OOS PF > 1.3, DD far below B&H): **passed**. 25-config in-sample sweep
(RSI 5-15 × SMA 150-250): PF 1.47-1.92 plateau, no spike. Honest read: this is
a drawdown-reduction system that is mostly in cash, not a return-maximizer.

## Adversarial review (3 finders → 12 findings, all fixed)

Most serious: OTO stop leg was DAY (expired at the close — swing positions
would have been unprotected overnight) → GTC. Also fixed: transient APIError
treated as flat (fabricated closed trades); posture cap breach when stacking
positions (now sized against remaining headroom); unadjusted live bars vs
adjusted backtest (now adjustment=ALL); cancel-then-close race on exits;
prompt-echo hazard (example JSON was max-risk, now the safe NEUTRAL); stale
RISK_OFF easing to NEUTRAL (now preserved); entries outside the tested
near-close window (now last-75-min gate); fabricated PnL on adopted positions;
sweep contaminating OOS (now in-sample only); partial daily bar in history
downloads; cp1252 crashes in unattended error paths.
Note: the verify agents hit the Pro session limit, so findings were verified
by hand rather than adversarially.

## Deployment & live verification

- venv: `C:\Users\abbas\.venvs\spy-qqq-bot` (outside iCloud). Repo: this folder, git.
- Task Scheduler: `SpyQqqBot-Posture` weekdays 8:15 local (9:15 ET; user
  preference, moved from 7:45) and `SpyQqqBot-Trade` weekdays 2:45 local
  (3:45 ET). Both run hidden via `ops/run_hidden.vbs` after a visible console
  got closed mid-run (killed the job, 0xC000013A).
- End-to-end verified: scheduler → hidden launcher → cmd → venv python →
  headless claude → skills → validated posture.json (three successful runs).
- Live bot run with real keys: authenticated to the new $5,000 paper account,
  pulled Alpaca IEX data, read posture, correctly no-op'd (no signal).
- FMP_API_KEY set as a user environment variable; SPY distribution data loads
  (2026-07-14: 8 distribution days in 25 sessions = SEVERE → RISK_OFF, a real
  data-driven call). Known limitation: FMP free tier 402s on QQQ; posture
  prompt now treats SPY-only distribution data as valid instead of degrading.

## Operating state at session close (2026-07-14)

- Posture: RISK_OFF (SEVERE SPY distribution + neutral breadth) — bot in cash.
- Positions: none. Equity: $5,000 paper.
- User's standing duties: keep the PC plugged in on weekdays; weekly glance at
  `logs/trades.csv` / `logs/bot.log`; `run_bot.py --resume` after a kill-switch
  halt; paper trade ≥1 month before any real-money discussion.
- Future path: compare a month of paper results against the backtest; only
  then consider Alpaca live or Robinhood Agentic Trading (official MCP,
  requires beta access, real money, no paper mode).
