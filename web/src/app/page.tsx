import { getSnapshot } from "@/lib/data";
import { PostureBadge } from "@/components/Badge";
import { Card, StatGrid, StatTile } from "@/components/StatTile";
import { EquityChart } from "@/components/EquityChart";
import { RsiChart } from "@/components/RsiChart";

export default function OverviewPage() {
  const snap = getSnapshot();
  const { current } = snap;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">SPY/QQQ Paper-Trading Bot</h1>
        <p className="text-sm text-ink-muted mt-1">
          Daily RSI(2) mean-reversion swing bot, gated by a Claude-generated risk posture.
          {snap.generated_at && (
            <> Last updated {new Date(snap.generated_at).toLocaleString()}.</>
          )}
        </p>
      </div>

      <StatGrid>
        <StatTile label="Equity" value={current.equity != null ? `$${current.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "-"} />
        <StatTile
          label="Posture"
          value={
            <span className="flex items-center gap-1.5">
              <PostureBadge posture={current.posture} />
              {current.max_exposure != null && (
                <span className="text-xs text-ink-muted font-normal">{(current.max_exposure * 100).toFixed(0)}%</span>
              )}
            </span>
          }
        />
        <StatTile label="Open positions" value={Object.keys(current.positions).length || "flat"} />
        <StatTile
          label="Kill switch"
          value={current.halted ? "HALTED" : "clear"}
          tone={current.halted ? "neg" : "pos"}
        />
        <StatTile label="Days paper trading" value={current.days_elapsed ?? "-"} />
        <StatTile label="Real-money gate" value={current.real_money_gate_date ?? "-"} />
      </StatGrid>

      {current.halted && (
        <div className="rounded-lg border border-status-critical bg-status-critical/10 px-4 py-3 text-sm">
          <strong>Kill switch active:</strong> {current.halt_reason}
        </div>
      )}

      <Card title="Equity curve">
        <EquityChart rows={snap.equity_curve} />
      </Card>

      <Card title="RSI(2) history -- distance from entry threshold">
        <RsiChart signals={snap.signals} threshold={snap.config.rsi_buy_below} />
      </Card>

      {snap.posture_history.length > 0 && (
        <Card title="Today's posture reasoning">
          <ul className="text-sm text-ink-secondary list-disc pl-5 space-y-1">
            {snap.posture_history[snap.posture_history.length - 1].reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
