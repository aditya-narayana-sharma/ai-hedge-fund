import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { RiskSignal } from '@/services/types';

interface PortfolioExposureProps {
  /** The risk manager's per-ticker output from analyst_signals. */
  riskSignals: Record<string, RiskSignal> | undefined;
}

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

/**
 * Allocation and remaining headroom per ticker.
 *
 * The risk manager already reports current_price, position_limit and
 * remaining_limit for every ticker; nothing rendered them.
 */
export function PortfolioExposure({ riskSignals }: PortfolioExposureProps) {
  const tickers = Object.keys(riskSignals ?? {});
  if (!riskSignals || tickers.length === 0) return null;

  const rows = tickers.map(ticker => {
    const reasoning = riskSignals[ticker].reasoning ?? {};
    const positionValue = Number(reasoning.current_position_value ?? 0);
    const positionLimit = Number(reasoning.position_limit ?? 0);
    const remaining = Number(reasoning.remaining_limit ?? 0);
    const used = positionLimit > 0 ? Math.min(100, (positionValue / positionLimit) * 100) : 0;
    return { ticker, positionValue, positionLimit, remaining, used };
  });

  const totalExposure = rows.reduce((sum, row) => sum + row.positionValue, 0);

  return (
    <section>
      <h2 className="text-lg font-semibold mb-4">Portfolio Exposure</h2>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>
            Allocation against the risk manager's per-ticker limit. Total exposure {currency.format(totalExposure)}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Position value</TableHead>
                <TableHead>Limit</TableHead>
                <TableHead>Remaining</TableHead>
                <TableHead className="w-48">Limit used</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(row => (
                <TableRow key={row.ticker}>
                  <TableCell className="font-medium">{row.ticker}</TableCell>
                  <TableCell>
                    {typeof riskSignals[row.ticker].current_price === 'number'
                      ? currency.format(riskSignals[row.ticker].current_price as number)
                      : 'N/A'}
                  </TableCell>
                  <TableCell>{currency.format(row.positionValue)}</TableCell>
                  <TableCell>{currency.format(row.positionLimit)}</TableCell>
                  <TableCell>{currency.format(row.remaining)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded bg-muted">
                        <div
                          className="h-2 rounded bg-blue-500"
                          style={{ width: `${row.used.toFixed(1)}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground w-10 text-right">
                        {row.used.toFixed(0)}%
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
