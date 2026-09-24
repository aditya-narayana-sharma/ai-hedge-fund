import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';

import { RISK_MANAGER_KEY } from '@/data/node-ids';
import { OutputNodeData } from '@/services/types';
import { PortfolioExposure } from './portfolio-exposure';

interface TextOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  outputNodeData: OutputNodeData | null;
}

type BadgeVariant = React.ComponentProps<typeof Badge>['variant'];

const BUY_ACTIONS = new Set(['buy', 'long', 'cover']);
const SELL_ACTIONS = new Set(['sell', 'short']);

export function TextOutputDialog({ 
  isOpen, 
  onOpenChange, 
  outputNodeData 
}: TextOutputDialogProps) {
  if (!outputNodeData) return null;

  const getActionIcon = (action: string) => {
    if (BUY_ACTIONS.has(action)) return <ArrowUp className="h-4 w-4 text-green-500" />;
    if (SELL_ACTIONS.has(action)) return <ArrowDown className="h-4 w-4 text-red-500" />;
    if (action === 'hold') return <Minus className="h-4 w-4 text-yellow-500" />;
    return null;
  };

  const getSignalBadge = (signal: string | undefined) => {
    if (!signal) return null;
    const variant: BadgeVariant = signal === 'bullish' ? 'success' :
                   signal === 'bearish' ? 'destructive' : 'outline';
    
    return (
      <Badge variant={variant}>
        {signal}
      </Badge>
    );
  };

  const getConfidenceBadge = (confidence: number | undefined) => {
    if (confidence === undefined || confidence === null) return null;
    const variant: BadgeVariant = confidence >= 50 ? 'success' : confidence >= 0 ? 'warning' : 'outline';
    const rounded = Number(confidence.toFixed(1));
    return (
      <Badge variant={variant}>
        {rounded}%
      </Badge>
    );
  };

  // Extract unique tickers from the data
  const tickers = Object.keys(outputNodeData.decisions || {});
  
  // Extract unique agents from analyst signals, excluding risk_management_agent
  const agents = Object.keys(outputNodeData.analyst_signals || {})
    .filter(agent => agent !== RISK_MANAGER_KEY);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Investment Analysis Report</DialogTitle>
        </DialogHeader>
        
        <div className="space-y-8 my-4">
          {/* Summary Section */}
          <section>
            <h2 className="text-lg font-semibold mb-4">Summary</h2>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>
                  Recommended trading actions based on analyst signals
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Quantity</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Reasoning</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tickers.map(ticker => {
                      const decision = outputNodeData.decisions[ticker];
                      const currentPrice = outputNodeData.analyst_signals[RISK_MANAGER_KEY]?.[ticker]?.current_price;
                      return (
                        <TableRow key={ticker}>
                          <TableCell className="font-medium">{ticker}</TableCell>
                          <TableCell>{typeof currentPrice === 'number' ? `$${currentPrice.toFixed(2)}` : 'N/A'}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getActionIcon(decision.action)}
                              <span className="capitalize">{decision.action}</span>
                            </div>
                          </TableCell>
                          <TableCell>{decision.quantity}</TableCell>
                          <TableCell>{getConfidenceBadge(decision.confidence)}</TableCell>
                          <TableCell className="max-w-sm">
                            <p className="text-xs text-muted-foreground line-clamp-2 hover:line-clamp-none">
                              {decision.reasoning}
                            </p>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </section>

          <PortfolioExposure riskSignals={outputNodeData.analyst_signals[RISK_MANAGER_KEY]} />

          {/* Analyst Signals Section */}
          <section>
            <h2 className="text-lg font-semibold mb-4">Analyst Signals</h2>
            <Accordion type="multiple" className="w-full">
              {tickers.map(ticker => (
                <AccordionItem key={ticker} value={ticker}>
                  <AccordionTrigger className="text-base font-medium px-4 py-3 bg-muted/30 rounded-md hover:bg-muted/50">
                    <div className="flex items-center gap-2">
                      {ticker}
                      <div className="flex items-center gap-1">
                        {getActionIcon(outputNodeData.decisions[ticker].action)}
                        <span className="text-sm font-normal text-muted-foreground">
                          {outputNodeData.decisions[ticker].action} {outputNodeData.decisions[ticker].quantity} shares
                        </span>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pt-4 px-1">
                    <div className="space-y-4">
                      {/* Agent Signals */}
                      <div className="grid grid-cols-1 gap-4">
                        {agents.map(agent => {
                          const signal = outputNodeData.analyst_signals[agent]?.[ticker];
                          if (!signal) return null;
                          
                          return (
                            <Card key={agent} className="overflow-hidden">
                              <CardHeader className="bg-muted/50 pb-3">
                                <div className="flex items-center justify-between">
                                  <CardTitle className="text-base capitalize">
                                    {agent.replace(/_/g, ' ')}
                                  </CardTitle>
                                  <div className="flex items-center gap-2">
                                    {getSignalBadge(signal.signal)}
                                    {getConfidenceBadge(signal.confidence)}
                                  </div>
                                </div>
                              </CardHeader>
                              <CardContent className="pt-3">
                                <p className="text-sm whitespace-pre-line">{signal.reasoning}</p>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}