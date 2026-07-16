import { getSnapshot } from "@/lib/data";
import { Card } from "@/components/StatTile";

const BACKTEST_ROWS = [
  { period: "Full (2000-01-03 -> 2026-07-13)", trades: 424, winRate: "71.0%", pf: "1.58", cagr: "2.55%", maxDd: "-15.6%" },
  { period: "In-sample (-> 2015)", trades: 241, winRate: "71.0%", pf: "1.70", cagr: "2.78%", maxDd: "-11.8%" },
  { period: "Out-of-sample (2016 ->)", trades: 183, winRate: "71.0%", pf: "1.47", cagr: "2.21%", maxDd: "-15.6%" },
  { period: "Buy & hold SPY (full)", trades: undefined, winRate: undefined, pf: undefined, cagr: "8.27%", maxDd: "-55.2%" },
];

export default function StrategyPage() {
  const snap = getSnapshot();
  const { config } = snap;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Strategy &amp; risk framework</h1>
        <p className="text-sm text-ink-muted mt-1">
          Rules trade, Claude only gates. The Python layer is deterministic and backtestable; the
          daily posture can only reduce exposure below what the rules would otherwise take, never
          raise it.
        </p>
      </div>

      <Card title="Entry / exit rules">
        <ul className="text-sm space-y-2 text-ink-secondary">
          <li>
            <strong className="text-ink-primary">Entry:</strong> close &gt; {config.sma_period}-day SMA (uptrend
            regime) and RSI(2) &lt; {config.rsi_buy_below} (washed-out pullback).
          </li>
          <li>
            <strong className="text-ink-primary">Exit:</strong> RSI(2) &gt; {config.rsi_exit_above}, or{" "}
            {config.max_hold_days} trading days held, or the regime breaks (close falls back below the
            SMA).
          </li>
          <li>
            <strong className="text-ink-primary">Catastrophe stop:</strong> 3&times;ATR(14) below entry, GTC
            (good-till-canceled, not day -- protects multi-day swing positions overnight).
          </li>
          <li>
            <strong className="text-ink-primary">Symbols:</strong> {config.symbols.join(", ")}, long-only, no
            leverage, whole shares.
          </li>
        </ul>
      </Card>

      <Card title="Posture gate">
        <ul className="text-sm space-y-2 text-ink-secondary">
          <li>
            <strong className="text-ink-primary">RISK_ON</strong> (max 90% gross exposure) -- healthy breadth
            (composite &ge; 60) and normal distribution-day risk.
          </li>
          <li>
            <strong className="text-ink-primary">NEUTRAL</strong> (max 50%) -- mixed signals, the fail-safe
            default when posture.json is missing, stale, or invalid.
          </li>
          <li>
            <strong className="text-ink-primary">RISK_OFF</strong> (0%) -- weak breadth, elevated distribution
            risk, or a data blackout on either signal.
          </li>
          <li>
            Every posture decision is cross-checked against the actual skill output it was supposedly
            based on before being accepted -- see the <a href="/posture" className="underline">posture history</a> page.
          </li>
        </ul>
      </Card>

      <Card title="Kill switches">
        <ul className="text-sm space-y-2 text-ink-secondary">
          <li>15% drawdown from peak equity halts new entries (existing positions still managed).</li>
          <li>3 consecutive losing trades halts new entries until a manual <code className="text-xs">--resume</code>.</li>
        </ul>
      </Card>

      <Card title="Backtest results (7.5bp slippage + 1&cent; spread)">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-ink-muted border-b border-gridline">
                <th className="py-2 pr-3">Period</th>
                <th className="py-2 pr-3">Trades</th>
                <th className="py-2 pr-3">Win rate</th>
                <th className="py-2 pr-3">Profit factor</th>
                <th className="py-2 pr-3">CAGR</th>
                <th className="py-2 pr-3">Max DD</th>
              </tr>
            </thead>
            <tbody>
              {BACKTEST_ROWS.map((r) => (
                <tr key={r.period} className="border-b border-gridline tabular-nums">
                  <td className="py-2 pr-3 whitespace-nowrap">{r.period}</td>
                  <td className="py-2 pr-3">{r.trades ?? "-"}</td>
                  <td className="py-2 pr-3">{r.winRate ?? "-"}</td>
                  <td className="py-2 pr-3">{r.pf ?? "-"}</td>
                  <td className="py-2 pr-3">{r.cagr}</td>
                  <td className="py-2 pr-3">{r.maxDd}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-ink-muted mt-3">
          Out-of-sample gate (PF &gt; 1.3, max drawdown well below buy-and-hold) passed. Honest read: this
          is a drawdown-reduction system that spends most of its time in cash, not a return-maximizer.
        </p>
      </Card>

      <Card title="What this is not">
        <p className="text-sm text-ink-secondary">
          This bot trades on Alpaca&apos;s paper-trading API with simulated money. Nothing on this site is
          investment advice, and no real capital is at risk. Paper fills are optimistic (no slippage, no
          dividends) -- live results would run below what&apos;s shown here. Real money is only under
          consideration after at least a month of paper results matching the backtest.
        </p>
      </Card>
    </div>
  );
}
