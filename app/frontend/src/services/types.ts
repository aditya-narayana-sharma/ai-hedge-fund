/** One analyst, as served by GET /agents. */
export interface AgentItem {
  key: string;
  display_name: string;
  description?: string | null;
  order: number;
}

/** One selectable LLM, as served by GET /models. */
export interface ModelItem {
  display_name: string;
  model_name: string;
  /** Free-form so a provider added on the Python side reaches the UI. */
  provider: string;
  supports_json_mode?: boolean;
}

export interface HedgeFundRequest {
  tickers: string[];
  selected_agents: string[];
  end_date?: string;
  start_date?: string;
  model_name?: string;
  model_provider?: string;
  initial_cash?: number;
  margin_requirement?: number;
  position_limit_pct?: number;
  run_id?: string;
}

export interface BacktestRequest extends Omit<HedgeFundRequest, 'end_date' | 'start_date'> {
  start_date?: string;
  end_date?: string;
}

/** One agent's verdict on one ticker. */
export interface AnalystSignal {
  signal?: string;
  confidence?: number;
  reasoning?: string;
}

/** The risk manager's per-ticker sizing output. */
export interface RiskSignal {
  current_price?: number;
  remaining_position_limit?: number;
  reasoning?: Record<string, number | string>;
}

export interface TradingDecision {
  action: 'buy' | 'sell' | 'short' | 'cover' | 'hold' | string;
  quantity: number;
  confidence: number;
  reasoning: string;
}

export interface OutputNodeData {
  run_id?: string;
  decisions: Record<string, TradingDecision>;
  analyst_signals: Record<string, Record<string, AnalystSignal & RiskSignal>>;
}

export interface EquityPoint {
  date: string;
  portfolio_value: number;
  long_exposure?: number | null;
  short_exposure?: number | null;
  gross_exposure?: number | null;
  net_exposure?: number | null;
}

export interface BacktestMetrics {
  total_return_pct: number;
  sharpe_ratio?: number | null;
  sortino_ratio?: number | null;
  max_drawdown_pct?: number | null;
  max_drawdown_date?: string | null;
  win_rate_pct?: number | null;
  win_loss_ratio?: number | null;
  max_consecutive_wins?: number | null;
  max_consecutive_losses?: number | null;
}

export interface BacktestResult {
  run_id: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  final_portfolio: Record<string, unknown>;
}

/** Server-Sent Event payloads, discriminated by the SSE event name. */
export interface StartEventData {
  run_id?: string;
  timestamp?: string | null;
}

export interface ProgressEventData {
  run_id?: string;
  agent: string;
  ticker?: string | null;
  status: string;
  timestamp?: string | null;
}

export interface ErrorEventData {
  run_id?: string;
  message: string;
  timestamp?: string | null;
}

export interface CompleteEventData {
  run_id?: string;
  data: OutputNodeData;
  timestamp?: string | null;
}

export interface BacktestDayEventData {
  run_id?: string;
  date: string;
  portfolio_value: number;
  return_pct: number;
}
