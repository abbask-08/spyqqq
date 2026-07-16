"use client";

import {
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import type { EquityRow, Posture } from "@/lib/types";
import { EmptyState } from "./StatTile";

const STATUS_VAR: Record<Posture, string> = {
  RISK_ON: "var(--status-good)",
  NEUTRAL: "var(--status-warning)",
  RISK_OFF: "var(--status-critical)",
  unknown: "var(--ink-muted)",
};

function postureSegments(rows: EquityRow[]) {
  // Group consecutive same-posture days into one shaded band each, rather
  // than one ReferenceArea per day -- fewer overlapping elements, and reads
  // cleaner once the history spans weeks with long same-posture stretches.
  const segments: { start: string; end: string; posture: Posture }[] = [];
  for (const row of rows) {
    const last = segments[segments.length - 1];
    if (last && last.posture === row.posture) {
      last.end = row.date;
    } else {
      segments.push({ start: row.date, end: row.date, posture: row.posture });
    }
  }
  return segments;
}

export function EquityChart({ rows }: { rows: EquityRow[] }) {
  if (rows.length === 0) {
    return <EmptyState>No live equity data yet -- this fills in after the first trading run.</EmptyState>;
  }

  const segments = postureSegments(rows);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        {segments.map((seg, i) => (
          <ReferenceArea
            key={i}
            x1={seg.start}
            x2={seg.end}
            fill={STATUS_VAR[seg.posture]}
            fillOpacity={0.12}
            stroke="none"
          />
        ))}
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
          tickFormatter={(d: string) => d.slice(5)}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
          tickFormatter={(v: number) => `$${v.toLocaleString()}`}
          axisLine={false}
          tickLine={false}
          domain={["auto", "auto"]}
          width={64}
        />
        <Tooltip
          formatter={(value) => [
            `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
            "Equity",
          ]}
          labelFormatter={(label, payload) => {
            const posture = payload?.[0]?.payload?.posture;
            return posture ? `${label} -- ${posture}` : label;
          }}
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey="equity"
          stroke="var(--ink-primary)"
          strokeWidth={2}
          dot={{ r: 3, fill: "var(--ink-primary)" }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
