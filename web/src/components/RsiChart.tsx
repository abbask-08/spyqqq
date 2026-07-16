"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SignalRow } from "@/lib/types";
import { EmptyState } from "./StatTile";

const SYMBOL_VAR: Record<string, string> = {
  SPY: "var(--series-1)",
  QQQ: "var(--series-2)",
};

interface MergedPoint {
  date: string;
  [symbol: string]: string | number | null;
}

function mergeBySymbol(signals: Record<string, SignalRow[]>): MergedPoint[] {
  const byDate = new Map<string, MergedPoint>();
  for (const [symbol, rows] of Object.entries(signals)) {
    for (const row of rows) {
      const point = byDate.get(row.date) ?? { date: row.date };
      point[symbol] = row.rsi;
      byDate.set(row.date, point);
    }
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function RsiChart({
  signals,
  threshold,
}: {
  signals: Record<string, SignalRow[]>;
  threshold: number;
}) {
  const symbols = Object.keys(signals);
  const data = mergeBySymbol(signals);

  if (data.length === 0) {
    return <EmptyState>No signal history yet -- this fills in after the first trading run.</EmptyState>;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
          tickFormatter={(d: string) => d.slice(5)}
          axisLine={{ stroke: "var(--gridline)" }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "var(--ink-muted)" }}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <ReferenceLine
          y={threshold}
          stroke="var(--ink-secondary)"
          strokeDasharray="4 3"
          label={{ value: `entry < ${threshold}`, position: "right", fontSize: 11, fill: "var(--ink-secondary)" }}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {symbols.map((symbol) => (
          <Line
            key={symbol}
            type="monotone"
            dataKey={symbol}
            name={symbol}
            stroke={SYMBOL_VAR[symbol] ?? "var(--ink-secondary)"}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
