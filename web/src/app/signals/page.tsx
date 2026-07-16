import { getSnapshot } from "@/lib/data";
import { Card, EmptyState } from "@/components/StatTile";
import { RsiChart } from "@/components/RsiChart";

function regimeLabel(inRegime: boolean | null) {
  if (inRegime == null) return "-";
  return inRegime ? "above SMA" : "below SMA";
}

export default function SignalsPage() {
  const snap = getSnapshot();
  const { signals, config } = snap;
  const symbols = Object.keys(signals);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Signals</h1>
        <p className="text-sm text-ink-muted mt-1">
          Entry rule: close &gt; {config.sma_period}-day SMA (regime filter) and RSI({2}) &lt;{" "}
          {config.rsi_buy_below}. Exit: RSI &gt; {config.rsi_exit_above}, {config.max_hold_days} trading
          days, or a regime break.
        </p>
      </div>

      <Card title="RSI(2) history">
        <RsiChart signals={signals} threshold={config.rsi_buy_below} />
      </Card>

      {symbols.length === 0 && (
        <Card title="Signal detail">
          <EmptyState>No signal history yet -- this fills in after the first trading run.</EmptyState>
        </Card>
      )}

      {symbols.map((symbol) => {
        const rows = [...signals[symbol]].sort((a, b) => b.date.localeCompare(a.date));
        return (
          <Card key={symbol} title={`${symbol} -- indicator history`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-ink-muted border-b border-gridline">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Close</th>
                    <th className="py-2 pr-3">SMA</th>
                    <th className="py-2 pr-3">RSI(2)</th>
                    <th className="py-2 pr-3">ATR</th>
                    <th className="py-2 pr-3">Regime</th>
                    <th className="py-2 pr-3">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-b border-gridline tabular-nums">
                      <td className="py-2 pr-3">{r.date}</td>
                      <td className="py-2 pr-3">{r.close?.toFixed(2) ?? "-"}</td>
                      <td className="py-2 pr-3">{r.sma?.toFixed(2) ?? "-"}</td>
                      <td className="py-2 pr-3">
                        {r.rsi != null ? (
                          <span className={r.rsi < config.rsi_buy_below ? "text-status-critical font-semibold" : ""}>
                            {r.rsi.toFixed(1)}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-2 pr-3">{r.atr?.toFixed(2) ?? "-"}</td>
                      <td className="py-2 pr-3 text-ink-secondary">{regimeLabel(r.in_regime)}</td>
                      <td className="py-2 pr-3">{r.entry_signal ? "ENTRY" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
