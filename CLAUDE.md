# spy-qqq-bot

Automated SPY/QQQ paper-trading bot at $0 incremental cost: deterministic Python
rules trade, a headless Claude Pro session gates daily risk exposure, and a
Next.js site (deployed to Vercel) gives a hosted view of it. Full narrative
history (design decisions, backtest numbers, the adversarial review findings)
is in `BUILD_LOG.md` — read that before re-deriving *why* something is built
the way it is. `README.md` is the operator runbook.

## Architecture

- `bot/` — pure strategy logic (`strategy.py`), broker wrapper (`broker.py`,
  Alpaca paper API), risk/kill-switches (`risk.py`), posture loader
  (`posture.py`), NYSE calendar guard, CSV/JSONL journaling (`journal.py`).
- `backtest/` — `get_history.py` (download), `backtest.py --sweep` (replay +
  parameter sweep). Re-run the backtest gate before trading on any strategy
  parameter change.
- `posture/` — the Claude posture layer. `posture_prompt.md` is the actual
  prompt (mapping guidance for RISK_ON/NEUTRAL/RISK_OFF); `make_posture.py`
  runs `claude -p` headlessly and **grounds** the LLM's claimed posture
  against the real market-breadth-analyzer / ibd-distribution-day-monitor
  skill output from that same run before accepting it (`common.py` has the
  deterministic ceiling logic) — never trust the LLM's self-reported numbers
  without checking them against what the skills actually returned.
  `posture/eval/` is a 13-fixture live-Claude regression benchmark
  (`run_eval.py`) — run it after any `posture_prompt.md` edit, not on a
  schedule (costs Pro-subscription turns).
- `reports/` — `data_sources.py` (shared log readers, single source of truth),
  `build_dashboard.py` (local self-contained HTML dashboard, no CDN),
  `export_snapshot.py` (writes `web/public/data/snapshot.json` for the
  Next.js site). Both dashboard builders are called from the end of
  `run_bot.py`'s `main()`, best-effort — a reporting failure must never fail
  the trading run.
- `web/` — the Next.js 16 / Tailwind / recharts site. Reads
  `web/public/data/snapshot.json` via a server-side `fs.readFileSync` in
  `src/lib/data.ts` — **no client-side fetch, no API routes, no database.**
  Pages: Overview (`/`), Signals, Posture history, Trades, Strategy.
- `ops/` — Task Scheduler registration + hidden launchers (`run_hidden.vbs`
  wraps the `.cmd` jobs so a stray console close can't kill the job).

## The two scheduled jobs (Windows Task Scheduler, weekdays)

- `SpyQqqBot-Posture` ~8:15 local (9:15 ET) → `posture/run_posture.cmd` →
  `make_posture.py`.
- `SpyQqqBot-Trade` ~2:45 local (3:45 ET) → `ops/run_bot.cmd` → `run_bot.py`
  (fetches bars, computes signals, places orders, then regenerates both
  dashboards and — see below — pushes the snapshot to GitHub).

Venv lives outside iCloud sync at `C:\Users\abbas\.venvs\spy-qqq-bot` — always
use that interpreter (`Scripts\python.exe`), not a bare `python` on PATH,
which may resolve to a different environment without `exchange_calendars` /
`alpaca-py` installed.

## Hosted dashboard deploy model (git-push sync, decided 2026-07-16)

There is deliberately **no live API and no hosted database.** The flow is:
`run_bot.py` → `export_snapshot.py` writes `web/public/data/snapshot.json` →
(intended, not yet wired as of this writing — see below) the bot commits and
pushes that file to GitHub → Vercel's git integration redeploys → the site is
current as of the last trading run, not live. This was an explicit choice
over a hosted DB + API route (simpler, stays free, no secrets to manage) —
don't "upgrade" to a live API without discussing it first.

- GitHub: `abbask-08/spyqqq` (this repo, remote `origin`). Push auth is
  whatever GitHub account is cached in Windows Credential Manager under
  `git:https://github.com` — must be `abbask-08`, not any other account on
  this machine.
- Vercel: project `akspyqqq` under scope `abbasstayshidden-6893s-projects`,
  git-connected to `abbask-08/spyqqq`. **Root Directory must be set to `web`**
  in Project Settings → General — this is a server-side project setting, not
  something a local `.vercel/repo.json` edit or `--cwd web` flag can fix; if
  deploys start failing with "No Next.js version detected," this setting is
  the first thing to check (it silently reset or was never set once already
  this project's history). SSO/Vercel-Authentication deployment protection is
  **deliberately disabled** (`vercel project protection disable ... --sso`)
  — the site is meant to be publicly viewable, per explicit user choice.
- Live URL: `https://akspyqqq-abbasstayshidden-6893s-projects.vercel.app`

**Still open / not yet done:** wiring the actual `git add/commit/push` step
into `run_bot.py`'s post-run hook so future trading runs auto-publish. Right
now `export_snapshot.py` only writes the local file — nothing pushes it
automatically yet. Don't assume the live site is current without checking.

## Conventions

- Config is one source of truth: `config.yaml`, read by both the backtest and
  the live bot (`bot/config.py`). Don't hardcode a strategy parameter that
  already has a config entry.
- Fail-safe direction is always "less risk, not more": posture defaults to
  NEUTRAL on any failure, grounding rejects a posture riskier than the data
  supports, kill switches only halt new entries (never block exit/stop
  processing).
- Tests: `python tests/test_strategy.py` and
  `python tests/test_posture_grounding.py` (both fast, no network/Claude
  calls). `posture/eval/run_eval.py` is the slow, costs-real-turns one.
- Runtime artifacts are gitignored (`logs/`, `posture/posture.json`,
  `posture/posture_history.jsonl`, `reports/dashboard.html`) — except
  `web/public/data/snapshot.json`, which is deliberately tracked since it's
  the git-push sync payload for the hosted site.
