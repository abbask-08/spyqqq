import { getSnapshot } from "@/lib/data";
import { Card, EmptyState } from "@/components/StatTile";
import { PostureBadge } from "@/components/Badge";

export default function PosturePage() {
  const snap = getSnapshot();
  const history = [...snap.posture_history].reverse();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Posture history</h1>
        <p className="text-sm text-ink-muted mt-1">
          Every daily decision from the headless Claude posture run (~9:15 AM ET), grounded against
          the actual market-breadth-analyzer and ibd-distribution-day-monitor skill output before
          being accepted -- see <code className="text-xs">posture/make_posture.py</code>.
        </p>
      </div>

      <Card title="Decisions">
        {history.length === 0 ? (
          <EmptyState>No posture history recorded yet -- this fills in after tomorrow&apos;s posture run.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-ink-muted border-b border-gridline">
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3">Posture</th>
                  <th className="py-2 pr-3">Cap</th>
                  <th className="py-2 pr-3">Breadth</th>
                  <th className="py-2 pr-3">Distribution</th>
                  <th className="py-2 pr-3">Ceiling</th>
                  <th className="py-2 pr-3">Reasons</th>
                </tr>
              </thead>
              <tbody>
                {history.map((entry, i) => (
                  <tr key={i} className="border-b border-gridline align-top">
                    <td className="py-2 pr-3 tabular-nums whitespace-nowrap">
                      {entry.generated_at?.slice(0, 10)}
                    </td>
                    <td className="py-2 pr-3">
                      <PostureBadge posture={entry.posture} />
                    </td>
                    <td className="py-2 pr-3 tabular-nums">{(entry.max_exposure * 100).toFixed(0)}%</td>
                    <td className="py-2 pr-3 tabular-nums">{entry.grounding?.breadth_score ?? "-"}</td>
                    <td className="py-2 pr-3">{entry.grounding?.distribution_risk ?? "-"}</td>
                    <td className="py-2 pr-3">
                      {entry.grounding?.ceiling ? <PostureBadge posture={entry.grounding.ceiling} /> : "-"}
                    </td>
                    <td className="py-2 pr-3 text-ink-secondary text-xs max-w-md">
                      {entry.reasons?.join("; ")}
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
