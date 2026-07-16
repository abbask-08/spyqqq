import fs from "fs";
import path from "path";
import type { Snapshot } from "./types";

const SNAPSHOT_PATH = path.join(process.cwd(), "public", "data", "snapshot.json");

const EMPTY_SNAPSHOT: Snapshot = {
  generated_at: "",
  current: {
    equity: null,
    posture: "unknown",
    max_exposure: null,
    grounding: {},
    positions: {},
    halted: false,
    halt_reason: "",
    first_trading_day: null,
    days_elapsed: null,
    real_money_gate_date: null,
  },
  equity_curve: [],
  signals: {},
  posture_history: [],
  trades: [],
  config: { symbols: [], rsi_buy_below: 10, rsi_exit_above: 65, sma_period: 200, max_hold_days: 10 },
};

// Reads the exported snapshot fresh on every call (no in-memory caching) --
// the file only changes once per deploy (the local bot commits + pushes a
// new snapshot, which triggers a fresh Vercel build), so staleness within a
// single running instance isn't a real concern, and a hot-reloadable file
// read makes local `npm run dev` reflect a freshly exported snapshot too.
export function getSnapshot(): Snapshot {
  try {
    const raw = fs.readFileSync(SNAPSHOT_PATH, "utf-8");
    return JSON.parse(raw) as Snapshot;
  } catch {
    return EMPTY_SNAPSHOT;
  }
}
