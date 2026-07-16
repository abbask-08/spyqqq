import { getSnapshot } from "@/lib/data";
import { Card, EmptyState, StatGrid, StatTile } from "@/components/StatTile";
import { PostureBadge } from "@/components/Badge";

export default function TradesPage() {
  const snap = getSnapshot();
  const trades = [...snap.trades].reverse();

  const closed = snap.trades.filter((t) => t.side === "SELL" && t.pnl != null);
  const wins = closed.filter((t) => (t.pnl ?? 0) > 0);
  const winRate = closed.length > 0 ? (wins.length / closed.length) * 100 : null;
  const totalPnl = closed.reduce((sum, t) => sum + (t.pnl ?? 0), 0);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Trade log</h1>
        <p className="text-sm text-ink-muted mt-1">Every order the bot has placed, with the posture and reason behind it.</p>
      </div>

      <StatGrid>
        <StatTile label="Total trades" value={snap.trades.length} />
        <StatTile label="Closed trades" value={closed.length} />
        <StatTile label="Win rate" value={winRate != null ? `${winRate.toFixed(0)}%` : "-"} />
        <StatTile
          label="Total realized PnL"
          value={closed.length > 0 ? `$${totalPnl.toFixed(2)}` : "-"}
          tone={closed.length > 0 ? (totalPnl >= 0 ? "pos" : "neg") : undefined}
        />
      </StatGrid>

      <Card title="History">
        {trades.length === 0 ? (
          <EmptyState>No trades yet -- the strategy has not fired an entry signal since deployment.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-ink-muted border-b border-gridline">
                  <th className="py-2 pr-3">Time (UTC)</th>
                  <th className="py-2 pr-3">Symbol</th>
                  <th className="py-2 pr-3">Side</th>
                  <th className="py-2 pr-3">Qty</th>
                  <th className="py-2 pr-3">Price</th>
                  <th className="py-2 pr-3">Reason</th>
                  <th className="py-2 pr-3">Posture</th>
                  <th className="py-2 pr-3">PnL</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="border-b border-gridline tabular-nums">
                    <td className="py-2 pr-3 whitespace-nowrap">{t.timestamp?.slice(0, 16).replace("T", " ")}</td>
                    <td className="py-2 pr-3">{t.symbol}</td>
                    <td className="py-2 pr-3">{t.side}</td>
                    <td className="py-2 pr-3">{t.qty}</td>
                    <td className="py-2 pr-3">{t.price}</td>
                    <td className="py-2 pr-3 text-ink-secondary">{t.reason}</td>
                    <td className="py-2 pr-3">
                      <PostureBadge posture={t.posture} />
                    </td>
                    <td
                      className={`py-2 pr-3 ${t.pnl != null ? (t.pnl > 0 ? "text-[var(--pnl-pos)]" : t.pnl < 0 ? "text-[var(--pnl-neg)]" : "") : ""}`}
                    >
                      {t.pnl != null ? t.pnl.toFixed(2) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
