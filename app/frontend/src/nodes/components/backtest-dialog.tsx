import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useMemo } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { BacktestResult } from '@/services/types';

interface BacktestDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  result: BacktestResult | null;
}

const AXIS_STYLE = { fill: 'hsl(var(--muted-foreground))', fontSize: 11 };
const GRID_COLOR = 'hsl(var(--border))';

function formatCurrency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatMetric(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toFixed(2)}${suffix}`;
}

// Recharts hands formatters a loosely typed value, so narrow before formatting.
const currencyTooltip = (value: unknown) => (typeof value === 'number' ? formatCurrency(value) : String(value ?? ''));
const absCurrencyTooltip = (value: unknown) => (typeof value === 'number' ? formatCurrency(Math.abs(value)) : String(value ?? ''));
const percentTooltip = (value: unknown) => (typeof value === 'number' ? `${value.toFixed(2)}%` : String(value ?? ''));

export function BacktestDialog({ isOpen, onOpenChange, result }: BacktestDialogProps) {
  // Drawdown is derived here rather than sent over the wire: it is a pure
  // function of the equity curve the response already carries.
  const equityCurve = useMemo(() => {
    if (!result) return [];
    let peak = Number.NEGATIVE_INFINITY;
    return result.portfolio_values.map((day) => {
      peak = Math.max(peak, day.portfolio_value);
      return {
        date: day.date,
        value: day.portfolio_value,
        drawdown: peak > 0 ? ((day.portfolio_value - peak) / peak) * 100 : 0,
      };
    });
  }, [result]);

  const exposure = useMemo(() => {
    if (!result) return [];
    return result.portfolio_values.map((day) => ({
      date: day.date,
      long: day.long_exposure,
      short: -day.short_exposure,
      net: day.net_exposure,
    }));
  }, [result]);

  if (!result) return null;

  const { metrics } = result;
  const totalReturn = metrics.total_return_pct;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Backtest Report</DialogTitle>
        </DialogHeader>

        <div className="my-4 space-y-8">
          <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard
              label="Total Return"
              value={formatMetric(totalReturn, '%')}
              tone={totalReturn >= 0 ? 'positive' : 'negative'}
            />
            <MetricCard label="Final Value" value={formatCurrency(result.final_portfolio_value)} />
            <MetricCard label="Sharpe" value={formatMetric(metrics.sharpe_ratio)} />
            <MetricCard label="Sortino" value={formatMetric(metrics.sortino_ratio)} />
            <MetricCard
              label="Max Drawdown"
              value={formatMetric(metrics.max_drawdown_pct, '%')}
              hint={metrics.max_drawdown_date ?? undefined}
              tone="negative"
            />
            <MetricCard label="Win Rate" value={formatMetric(metrics.win_rate_pct, '%')} />
            <MetricCard label="Win/Loss" value={formatMetric(metrics.win_loss_ratio)} />
            <MetricCard
              label="Days"
              value={`${metrics.winning_trades}W / ${metrics.losing_trades}L`}
              hint={`${metrics.total_trades} total`}
            />
          </section>

          <ChartSection title="Equity curve" description="Net liquidation value per simulated trading day">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={equityCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={AXIS_STYLE} minTickGap={40} />
                <YAxis tick={AXIS_STYLE} tickFormatter={formatCurrency} width={80} />
                <ChartTooltip formatter={currencyTooltip} />
                <Line type="monotone" dataKey="value" name="Portfolio value" stroke="#3fb950" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </ChartSection>

          <ChartSection title="Drawdown" description="Percentage below the running peak">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={equityCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={AXIS_STYLE} minTickGap={40} />
                <YAxis tick={AXIS_STYLE} tickFormatter={(value: number) => `${value.toFixed(0)}%`} width={60} />
                <ChartTooltip formatter={percentTooltip} />
                <Area type="monotone" dataKey="drawdown" name="Drawdown" stroke="#f85149" fill="#f8514933" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartSection>

          <ChartSection
            title="Exposure"
            description="Long above the axis, short below, from the risk manager's position data"
          >
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={exposure} stackOffset="sign">
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
                <XAxis dataKey="date" tick={AXIS_STYLE} minTickGap={40} />
                <YAxis tick={AXIS_STYLE} tickFormatter={formatCurrency} width={80} />
                <ChartTooltip formatter={absCurrencyTooltip} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="long" name="Long" stackId="exposure" fill="#3fb950" />
                <Bar dataKey="short" name="Short" stackId="exposure" fill="#f85149" />
              </BarChart>
            </ResponsiveContainer>
          </ChartSection>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MetricCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: 'positive' | 'negative';
}) {
  const toneClass = tone === 'positive' ? 'text-green-500' : tone === 'negative' ? 'text-red-500' : '';
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={`text-xl font-semibold ${toneClass}`}>{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}

function ChartSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
