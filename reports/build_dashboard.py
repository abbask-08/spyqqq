"""Build reports/dashboard.html from the accumulated logs: equity, signals,
posture history, and trades. Self-contained (no CDN, no JS build step) so it
opens locally with no internet. Run standalone:
    python reports/build_dashboard.py
Also called automatically at the end of every run_bot.py run (best-effort --
a dashboard failure must never affect trading).
"""
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.config import load_config, repo_path  # noqa: E402
from reports.data_sources import (  # noqa: E402
    POSTURE_JSON, STATE_JSON, compute_current_status, read_csv_rows,
    read_equity_curve, read_json, read_posture_history, read_signals,
)

OUT_FILE = repo_path("reports/dashboard.html")

STATUS_COLOR = {"RISK_ON": "good", "NEUTRAL": "warning", "RISK_OFF": "critical"}
SYMBOL_SLOT = {"SPY": 1, "QQQ": 2}  # fixed categorical order, per palette.md


# ---------------------------------------------------------------- SVG helpers

def scale(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
    if hi <= lo:
        return (out_lo + out_hi) / 2
    return out_lo + (value - lo) / (hi - lo) * (out_hi - out_lo)


def equity_chart(rows: list[dict]) -> str:
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 760, 260, 56, 16, 16, 28
    if len(rows) < 1:
        return '<p class="empty-state">No live equity data yet -- this fills in after the first trading run.</p>'

    dates = [r["date"] for r in rows]
    equities = [float(r["equity"]) for r in rows]
    lo, hi = min(equities), max(equities)
    pad = max((hi - lo) * 0.1, 50)
    lo, hi = lo - pad, hi + pad

    def x_of(i):
        return scale(i, 0, max(len(rows) - 1, 1), PAD_L, W - PAD_R)

    def y_of(v):
        return scale(v, lo, hi, H - PAD_B, PAD_T)

    # Non-overlapping day bands: each spans the midpoint to its neighbors,
    # with the first/last band's outer edge clamped to the plot area rather
    # than reusing the (pre-clamp) interval width -- otherwise the first and
    # last bands render oversized and overlap their neighbors.
    half_step = (x_of(1) - x_of(0)) / 2 if len(rows) > 1 else (W - PAD_L - PAD_R) / 2
    bands = []
    for i, r in enumerate(rows):
        x0 = PAD_L if i == 0 else x_of(i) - half_step
        x1 = (W - PAD_R) if i == len(rows) - 1 else x_of(i) + half_step
        status = STATUS_COLOR.get(r.get("posture"), "warning")
        bands.append(
            f'<rect x="{x0:.1f}" y="{PAD_T}" width="{max(x1 - x0, 1):.1f}" '
            f'height="{H - PAD_T - PAD_B}" fill="var(--status-{status})" opacity="0.12"/>'
        )

    points = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in enumerate(equities))
    dots = []
    for i, (d, v) in enumerate(zip(dates, equities)):
        dots.append(
            f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="7" fill="transparent" stroke="none">'
            f'<title>{d}: ${v:,.2f}</title></circle>'
            f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="3" fill="var(--ink-primary)"/>'
        )

    y_ticks = []
    for frac in (0, 0.5, 1):
        v = lo + frac * (hi - lo)
        y = y_of(v)
        y_ticks.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" stroke="var(--gridline)" stroke-width="1"/>'
            f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis-label">${v:,.0f}</text>'
        )

    x_labels = []
    step = max(1, len(rows) // 6)
    for i in range(0, len(rows), step):
        x_labels.append(
            f'<text x="{x_of(i):.1f}" y="{H - 8}" text-anchor="middle" class="axis-label">{dates[i][5:]}</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" aria-label="Equity curve">
{''.join(bands)}
{''.join(y_ticks)}
<polyline points="{points}" fill="none" stroke="var(--ink-primary)" stroke-width="2"/>
{''.join(dots)}
{''.join(x_labels)}
</svg>"""


def rsi_chart(by_symbol: dict, threshold: float) -> str:
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 760, 220, 44, 16, 16, 28
    if not by_symbol:
        return '<p class="empty-state">No signal history yet -- this fills in after the first trading run.</p>'

    all_dates = sorted({r["date"] for rows in by_symbol.values() for r in rows})
    if not all_dates:
        return '<p class="empty-state">No signal history yet -- this fills in after the first trading run.</p>'
    date_idx = {d: i for i, d in enumerate(all_dates)}

    def x_of(i):
        return scale(i, 0, max(len(all_dates) - 1, 1), PAD_L, W - PAD_R)

    def y_of(v):
        return scale(v, 0, 100, H - PAD_B, PAD_T)

    y_ticks = []
    for v in (0, 50, 100):
        y = y_of(v)
        y_ticks.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" stroke="var(--gridline)" stroke-width="1"/>'
            f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis-label">{v}</text>'
        )
    thresh_y = y_of(threshold)
    y_ticks.append(
        f'<line x1="{PAD_L}" y1="{thresh_y:.1f}" x2="{W - PAD_R}" y2="{thresh_y:.1f}" '
        f'stroke="var(--ink-secondary)" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="{W - PAD_R}" y="{thresh_y - 4:.1f}" text-anchor="end" class="axis-label">entry &lt; {threshold:g}</text>'
    )

    series_svg, legend = [], []
    for symbol, rows in sorted(by_symbol.items(), key=lambda kv: SYMBOL_SLOT.get(kv[0], 99)):
        slot = SYMBOL_SLOT.get(symbol, 1)
        idxs = [date_idx[r["date"]] for r in rows]
        vals = [float(r["rsi"]) for r in rows]
        pts = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in zip(idxs, vals))
        dots = "".join(
            f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="7" fill="transparent"><title>{symbol} {r["date"]}: RSI(2)={v:.1f}</title></circle>'
            f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="3" fill="var(--series-{slot})"/>'
            for i, v, r in zip(idxs, vals, rows)
        )
        series_svg.append(
            f'<polyline points="{pts}" fill="none" stroke="var(--series-{slot})" stroke-width="2"/>{dots}'
        )
        legend.append(
            f'<span class="legend-item"><span class="swatch" style="background:var(--series-{slot})"></span>{symbol}</span>'
        )

    x_labels = []
    step = max(1, len(all_dates) // 6)
    for i in range(0, len(all_dates), step):
        x_labels.append(
            f'<text x="{x_of(i):.1f}" y="{H - 8}" text-anchor="middle" class="axis-label">{all_dates[i][5:]}</text>'
        )

    legend_html = f'<div class="legend">{"".join(legend)}</div>'
    return f"""{legend_html}
<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" aria-label="RSI(2) history">
{''.join(y_ticks)}
{''.join(series_svg)}
{''.join(x_labels)}
</svg>"""


def posture_table(history: list[dict]) -> str:
    if not history:
        return '<p class="empty-state">No posture history recorded yet -- this fills in after tomorrow\'s posture run.</p>'
    rows_html = []
    for entry in reversed(history[-30:]):
        posture = entry.get("posture", "?")
        status = STATUS_COLOR.get(posture, "warning")
        grounding = entry.get("grounding", {})
        gen = entry.get("generated_at", "")[:10]
        reasons = "; ".join(entry.get("reasons", []))
        rows_html.append(f"""<tr>
<td>{gen}</td>
<td><span class="badge badge-{status}">{posture}</span></td>
<td>{entry.get('max_exposure', ''):.0%}</td>
<td>{grounding.get('breadth_score', '-')}</td>
<td>{grounding.get('distribution_risk', '-')}</td>
<td class="reasons">{reasons}</td>
</tr>""")
    return f"""<table class="data-table">
<thead><tr><th>Date</th><th>Posture</th><th>Cap</th><th>Breadth</th><th>Distribution</th><th>Reasons</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody>
</table>"""


def trades_table(trades: list[dict]) -> str:
    if not trades:
        return '<p class="empty-state">No trades yet -- the strategy has not fired an entry signal since deployment.</p>'
    rows_html = []
    for t in reversed(trades[-50:]):
        pnl = t.get("pnl", "")
        pnl_class = "pnl-pos" if pnl not in ("", None) and float(pnl) > 0 else (
            "pnl-neg" if pnl not in ("", None) and float(pnl) < 0 else ""
        )
        rows_html.append(f"""<tr>
<td>{t.get('timestamp', '')[:16].replace('T', ' ')}</td>
<td>{t.get('symbol', '')}</td>
<td>{t.get('side', '')}</td>
<td>{t.get('qty', '')}</td>
<td>{t.get('price', '')}</td>
<td>{t.get('reason', '')}</td>
<td class="{pnl_class}">{pnl}</td>
</tr>""")
    return f"""<table class="data-table">
<thead><tr><th>Time (UTC)</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Reason</th><th>PnL</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody>
</table>"""


def stat_tiles(equity_rows: list[dict], current_posture: dict, state: dict) -> str:
    status_data = compute_current_status(equity_rows, current_posture, state)
    equity = status_data["equity"]
    posture = status_data["posture"]
    status = STATUS_COLOR.get(posture, "warning")
    cap = status_data["max_exposure"]
    positions = status_data["positions"]
    halted = status_data["halted"]
    days_elapsed = status_data["days_elapsed"]
    gate_date = status_data["real_money_gate_date"]

    def tile(label, value, extra_class=""):
        return f'<div class="stat-tile"><div class="stat-label">{label}</div><div class="stat-value {extra_class}">{value}</div></div>'

    tiles = [
        tile("Equity", f"${equity:,.2f}" if equity is not None else "-"),
        tile("Posture", f'<span class="badge badge-{status}">{posture}</span> ({cap:.0%})' if cap is not None else posture),
        tile("Open positions", len(positions) or "flat"),
        tile("Kill switch", "HALTED" if halted else "clear", "pnl-neg" if halted else "pnl-pos"),
        tile("Days paper trading", days_elapsed if days_elapsed is not None else "-"),
        tile("Real-money gate (30d)", gate_date or "-"),
    ]
    return f'<div class="stat-grid">{"".join(tiles)}</div>'


PALETTE_CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb;
  --ink-primary: #0b0b0b; --ink-secondary: #52514e; --ink-muted: #898781;
  --gridline: #e1e0d9; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --series-2: #008300;
  --status-good: #0ca30c; --status-warning: #fab219; --status-critical: #d03b3b;
  --pnl-pos: #006300; --pnl-neg: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink-primary: #ffffff; --ink-secondary: #c3c2b7; --ink-muted: #898781;
    --gridline: #2c2c2a; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #008300;
    --status-good: #0ca30c; --status-warning: #fab219; --status-critical: #d03b3b;
    --pnl-pos: #0ca30c; --pnl-neg: #e66767;
  }
}
"""


def render(equity_rows, signals_by_symbol, posture_history, trades, current_posture, state, rsi_threshold) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SPY/QQQ Bot Dashboard</title>
<style>
{PALETTE_CSS}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px; background: var(--page); color: var(--ink-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}}
h1 {{ font-size: 1.4rem; margin: 0 0 4px; }}
.subtitle {{ color: var(--ink-muted); font-size: 0.85rem; margin-bottom: 20px; }}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px 20px; margin-bottom: 20px;
}}
.card h2 {{ font-size: 1rem; margin: 0 0 12px; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
.stat-tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }}
.stat-label {{ font-size: 0.72rem; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.04em; }}
.stat-value {{ font-size: 1.15rem; font-weight: 600; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.chart-svg {{ width: 100%; height: auto; }}
.axis-label {{ font-size: 10px; fill: var(--ink-muted); }}
.legend {{ display: flex; gap: 16px; margin-bottom: 8px; font-size: 0.82rem; color: var(--ink-secondary); }}
.legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
.swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
.badge {{
  display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
  color: white;
}}
.badge-good {{ background: var(--status-good); }}
.badge-warning {{ background: var(--status-warning); color: #3a2a00; }}
.badge-critical {{ background: var(--status-critical); }}
.data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
.data-table th {{
  text-align: left; padding: 8px 10px; color: var(--ink-muted); font-weight: 600;
  border-bottom: 1px solid var(--gridline); font-size: 0.75rem; text-transform: uppercase;
}}
.data-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--gridline); font-variant-numeric: tabular-nums; }}
.data-table td.reasons {{ font-variant-numeric: normal; color: var(--ink-secondary); font-size: 0.8rem; }}
.pnl-pos {{ color: var(--pnl-pos); }}
.pnl-neg {{ color: var(--pnl-neg); }}
.empty-state {{ color: var(--ink-muted); font-size: 0.85rem; font-style: italic; }}
.table-wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>SPY/QQQ Paper-Trading Bot</h1>
<div class="subtitle">Generated {generated} local time -- regenerates automatically after each trading run (~2:45 PM local weekdays)</div>

<div class="card">{stat_tiles(equity_rows, current_posture, state)}</div>

<div class="card">
<h2>Equity curve</h2>
{equity_chart(equity_rows)}
</div>

<div class="card">
<h2>RSI(2) history -- distance from entry threshold</h2>
{rsi_chart(signals_by_symbol, rsi_threshold)}
</div>

<div class="card">
<h2>Posture history</h2>
<div class="table-wrap">{posture_table(posture_history)}</div>
</div>

<div class="card">
<h2>Trade log</h2>
<div class="table-wrap">{trades_table(trades)}</div>
</div>

</body>
</html>"""


def main() -> int:
    cfg = load_config()
    equity_rows = read_equity_curve()
    signals_by_symbol = read_signals()
    posture_history = read_posture_history()
    trades = read_csv_rows(repo_path(cfg["paths"]["trades_csv"]))
    current_posture = read_json(POSTURE_JSON)
    state = read_json(STATE_JSON)
    rsi_threshold = float(cfg["strategy"]["rsi_buy_below"])

    html = render(equity_rows, signals_by_symbol, posture_history, trades, current_posture, state, rsi_threshold)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
