/**
 * Wire types shared between the SSE client, the node context and the report UI.
 * These mirror the backend payloads in app/backend/models.
 */

/** Provider identifiers as spelled by src/llm/models.py ModelProvider. */
export type ModelProvider =
  | 'Anthropic'
  | 'DeepSeek'
  | 'Gemini'
  | 'Groq'
  | 'OpenAI'
  | 'Ollama';

/** One entry of GET /models. */
export interface ModelItem {
  display_name: string;
  model_name: string;
  provider: ModelProvider;
}

/** One entry of GET /agents. */
export interface AgentItem {
  key: string;
  display_name: string;
  description: string;
  order: number;
}

/** A portfolio-manager order for a single ticker. */
export interface TradingDecision {
  action: string;
  quantity: number;
  confidence: number;
  reasoning: string;
}

/**
 * One analyst's verdict for one ticker. Analysts agree on signal/confidence/
 * reasoning; the risk manager instead reports sizing fields.
 */
export interface AnalystSignal {
  signal?: string;
  confidence?: number;
  reasoning?: string | Record<string, unknown>;
  current_price?: number;
  remaining_position_limit?: number;
}

/** analyst_signals[agentKey][ticker] */
export type AnalystSignalsByAgent = Record<string, Record<string, AnalystSignal>>;

/** Payload of the SSE `complete` event. */
export interface HedgeFundResult {
  decisions: Record<string, TradingDecision>;
  analyst_signals: AnalystSignalsByAgent;
}

/** Per-day row of a backtest run. */
export interface BacktestDay {
  date: string;
  portfolio_value: number;
  cash: number;
  long_exposure: number;
  short_exposure: number;
  gross_exposure: number;
  net_exposure: number;
  long_short_ratio: number | null;
}

/** Summary metrics of a completed backtest. */
export interface BacktestMetrics {
  total_return_pct: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number | null;
  max_drawdown_date: string | null;
  win_rate_pct: number | null;
  win_loss_ratio: number | null;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
}

/** Payload of the backtest SSE `complete` event. */
export interface BacktestResult {
  initial_capital: number;
  final_portfolio_value: number;
  metrics: BacktestMetrics;
  portfolio_values: BacktestDay[];
}
