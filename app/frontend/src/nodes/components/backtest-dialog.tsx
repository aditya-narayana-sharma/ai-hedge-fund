import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { BacktestDayEventData, BacktestResult } from '@/services/types';

interface BacktestDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  result: BacktestResult | null;
  /** Days streamed so far, used while the run is still in flight. */
  streamedDays: BacktestDayEventData[];
}

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

function formatMetric(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}${suffix}`;
}

/** Recharts hands tooltips a loosely typed value; narrow before formatting. */
function formatCurrencyTooltip(value: unknown): string {
  return typeof value === 'number' ? currency.format(value) : '—';
}

function formatPercentTooltip(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(2)}%` : '—';
}

export function BacktestDialog({ isOpen, onOpenChange, result, streamedDays }: BacktestDialogProps) {
  const equityCurve = useMemo(() => {
    if (result?.equity_curve?.length) {
      return result.equity_curve.map(point => ({ date: point.date, value: point.portfolio_value }));
    }
    return streamedDays.map(day => ({ date: day.date, value: day.portfolio_value }));
  }, [result, streamedDays]);

  // Drawdown from the running peak, the same series the CLI reports a minimum of.
  const drawdownCurve = useMemo(() => {
    let peak = -Infinity;
    return equityCurve.map(point => {
      peak = Math.max(peak, point.value);
      return { date: point.date, drawdown: peak > 0 ? ((point.value - peak) / peak) * 100 : 0 };
    });
  }, [equityCurve]);

  if (!result && equityCurve.length === 0) return null;

  const metrics = result?.metrics;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Backtest Report</DialogTitle>
        </DialogHeader>

        <div className="space-y-8 my-4">
          {metrics && (
            <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard label="Total return" value={formatMetric(metrics.total_return_pct, '%')} />
              <MetricCard label="Sharpe" value={formatMetric(metrics.sharpe_ratio)} />
              <MetricCard label="Sortino" value={formatMetric(metrics.sortino_ratio)} />
              <MetricCard
                label="Max drawdown"
                value={formatMetric(metrics.max_drawdown_pct, '%')}
                caption={metrics.max_drawdown_date ?? undefined}
              />
              <MetricCard label="Win rate" value={formatMetric(metrics.win_rate_pct, '%')} />
              <MetricCard label="Win/loss ratio" value={formatMetric(metrics.win_loss_ratio)} />
              <MetricCard label="Longest win streak" value={String(metrics.max_consecutive_wins ?? '—')} />
              <MetricCard label="Longest loss streak" value={String(metrics.max_consecutive_losses ?? '—')} />
            </section>
          )}

          <section>
            <h2 className="text-lg font-semibold mb-4">Equity Curve</h2>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>
                  {result ? 'Portfolio value over the backtest period' : 'Running — value so far'}
                </CardDescription>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={equityCurve}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={32} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={value => currency.format(value)} width={80} />
                    <Tooltip formatter={formatCurrencyTooltip} />
                    <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-4">Drawdown</h2>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Decline from the running peak, in percent</CardDescription>
              </CardHeader>
              <CardContent className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={drawdownCurve}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={32} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={value => `${value.toFixed(0)}%`} width={56} />
                    <Tooltip formatter={formatPercentTooltip} />
                    <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MetricCard({ label, value, caption }: { label: string; value: string; caption?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-xl">{value}</CardTitle>
      </CardHeader>
      {caption && <CardContent className="pt-0 text-xs text-muted-foreground">{caption}</CardContent>}
    </Card>
  );
}
