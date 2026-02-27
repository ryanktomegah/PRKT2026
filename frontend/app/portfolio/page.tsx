'use client'

import { useALBSStore } from '@/lib/store'
import { Header } from '@/components/layout/Header'
import { MetricCard } from '@/components/shared/MetricCard'
import { PortfolioCharts } from '@/components/portfolio/PortfolioCharts'
import { formatCurrency, formatPercent } from '@/lib/utils'

export default function PortfolioPage() {
  const portfolio = useALBSStore((s) => s.portfolio)
  const clearPortfolio = useALBSStore((s) => s.clearPortfolio)

  const total = portfolio.length
  const flagged = portfolio.filter((p) => p.scoreResult.threshold_exceeded).length
  const flaggedPct = total > 0 ? flagged / total : 0
  const avgProb =
    total > 0
      ? portfolio.reduce((s, p) => s + p.scoreResult.failure_probability, 0) / total
      : 0
  const totalPool = portfolio.reduce(
    (s, p) => s + (p.priceResult?.bridge_loan_amount ?? 0),
    0
  )
  const netReturn = portfolio.reduce(
    (s, p) => s + (p.priceResult?.expected_profit_usd ?? 0),
    0
  )

  return (
    <div>
      <Header title="Portfolio" subtitle="Session Analytics" />
      <main className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">{total} analyses in this session</p>
          {total > 0 && (
            <button
              onClick={clearPortfolio}
              className="text-xs text-muted-foreground hover:text-red-400 transition-colors"
            >
              Clear session
            </button>
          )}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard label="Total Analysed" value={total} />
          <MetricCard
            label="Total Flagged"
            value={flagged}
            sub={total > 0 ? formatPercent(flaggedPct) + ' of total' : undefined}
            accent="yellow"
          />
          <MetricCard
            label="Avg Failure Prob"
            value={total > 0 ? formatPercent(avgProb) : '—'}
            accent={avgProb > 0.5 ? 'red' : avgProb > 0.3 ? 'yellow' : 'green'}
          />
          <MetricCard
            label="Total Advance Pool"
            value={total > 0 ? formatCurrency(totalPool) : '—'}
            accent="blue"
          />
          <MetricCard
            label="Net Return"
            value={total > 0 ? formatCurrency(netReturn) : '—'}
            accent="green"
          />
        </div>

        <PortfolioCharts />
      </main>
    </div>
  )
}
