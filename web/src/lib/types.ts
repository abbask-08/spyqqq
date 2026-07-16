export type Posture = "RISK_ON" | "NEUTRAL" | "RISK_OFF" | "unknown";

export interface EquityRow {
  date: string;
  equity: number;
  posture: Posture;
  exposure_cap: number;
  note: string;
}

export interface SignalRow {
  date: string;
  symbol: string;
  close: number;
  sma: number | null;
  rsi: number | null;
  atr: number | null;
  in_regime: boolean | null;
  entry_signal: boolean;
}

export interface PostureHistoryEntry {
  posture: Posture;
  max_exposure: number;
  reasons: string[];
  generated_at: string;
  grounding?: {
    breadth_score: number | null;
    distribution_risk: string | null;
    ceiling: Posture;
  };
}

export interface TradeRow {
  timestamp: string;
  symbol: string;
  side: "BUY" | "SELL";
  qty: number;
  price: number;
  reason: string;
  posture: Posture;
  exposure_cap: number;
  pnl: number | null;
  dry_run: boolean;
}

export interface CurrentStatus {
  equity: number | null;
  posture: Posture;
  max_exposure: number | null;
  grounding: {
    breadth_score?: number | null;
    distribution_risk?: string | null;
    ceiling?: Posture;
  };
  positions: Record<string, { qty: number; entry_price: number; entry_date: string; stop: number | null }>;
  halted: boolean;
  halt_reason: string;
  first_trading_day: string | null;
  days_elapsed: number | null;
  real_money_gate_date: string | null;
}

export interface StrategyConfig {
  symbols: string[];
  rsi_buy_below: number;
  rsi_exit_above: number;
  sma_period: number;
  max_hold_days: number;
}

export interface Snapshot {
  generated_at: string;
  current: CurrentStatus;
  equity_curve: EquityRow[];
  signals: Record<string, SignalRow[]>;
  posture_history: PostureHistoryEntry[];
  trades: TradeRow[];
  config: StrategyConfig;
}
