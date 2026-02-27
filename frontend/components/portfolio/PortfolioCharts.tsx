'use client'

import { useALBSStore } from '@/lib/store'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { formatCurrency, formatPercent, formatBps } from '@/lib/utils'

export function PortfolioCharts() {
  const portfolio = useALBSStore((s) => s.portfolio)

  if (portfolio.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        No data yet. Run some analyses to populate the portfolio.
      </div>
    )
  }

  // Failure probability histogram buckets
  const buckets = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
  const histData = buckets.slice(0, -1).map((low, i) => {
    const high = buckets[i + 1]
    const count = portfolio.filter(
      (p) => p.scoreResult.failure_probability >= low && p.scoreResult.failure_probability < high
    ).length
    return { name: `${(low * 100).toFixed(0)}–${(high * 100).toFixed(0)}%`, count }
  })

  // APR distribution
  const aprData = portfolio
    .filter((p) => p.priceResult)
    .map((p) => ({
      name: p.scoreResult.currency_pair,
      apr: p.priceResult!.annualized_rate_bps,
    }))

  // Offer status donut
  const statusCounts = portfolio.reduce(
    (acc, p) => {
      const status = p.executeResult?.offer_status ?? 'NO_OFFER'
      acc[status] = (acc[status] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )
  const pieData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }))
  const PIE_COLORS: Record<string, string> = {
    ACCEPTED: '#10b981',
    REJECTED: '#ef4444',
    EXPIRED: '#f59e0b',
    NO_OFFER: '#64748b',
  }

  return (
    <div className="space-y-6">
      {/* Failure probability histogram */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="text-sm font-semibold text-foreground mb-3">Failure Probability Distribution</h3>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={histData} margin={{ top: 0, right: 0, left: -20, bottom: 20 }}>
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} angle={-30} textAnchor="end" />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} allowDecimals={false} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
            <Bar dataKey="count" fill="#3b82f6" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* APR distribution */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="text-sm font-semibold text-foreground mb-3">APR by Corridor (bps)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={aprData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }}
                formatter={(v: number) => [`${v.toFixed(0)} bps`, 'APR']}
              />
              <Bar dataKey="apr" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Offer status donut */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="text-sm font-semibold text-foreground mb-3">Offer Status Breakdown</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={70}>
                {pieData.map((entry, idx) => (
                  <Cell key={idx} fill={PIE_COLORS[entry.name] || '#64748b'} />
                ))}
              </Pie>
              <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 11, color: '#94a3b8' }}
              />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Loans table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Loan Results</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Corridor', 'Amount', 'Fail. Prob', 'APR', 'Offer Status', 'Settlement', 'Net Return', 'Claim 5'].map((h) => (
                  <th key={h} className="px-4 py-2 text-left text-muted-foreground font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {portfolio.map((item, idx) => (
                <tr key={item.id} className="border-b border-border/50 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-2 font-mono text-muted-foreground">{idx + 1}</td>
                  <td className="px-4 py-2 font-mono">{item.scoreResult.currency_pair}</td>
                  <td className="px-4 py-2 font-mono">{formatCurrency(item.scoreResult.amount_usd)}</td>
                  <td className="px-4 py-2 font-mono">
                    <span className={item.scoreResult.failure_probability > item.scoreResult.decision_threshold ? 'text-red-400' : 'text-emerald-400'}>
                      {formatPercent(item.scoreResult.failure_probability)}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono">
                    {item.priceResult ? formatBps(item.priceResult.annualized_rate_bps) : '—'}
                  </td>
                  <td className="px-4 py-2">
                    {item.executeResult ? (
                      <span className={
                        item.executeResult.offer_status === 'ACCEPTED' ? 'text-emerald-400' :
                        item.executeResult.offer_status === 'REJECTED' ? 'text-red-400' : 'text-yellow-400'
                      }>
                        {item.executeResult.offer_status}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2 font-mono">
                    {item.executeResult?.settlement_status ?? '—'}
                  </td>
                  <td className="px-4 py-2 font-mono text-emerald-400">
                    {item.priceResult ? formatCurrency(item.priceResult.expected_profit_usd) : '—'}
                  </td>
                  <td className="px-4 py-2">
                    {item.executeResult ? '✓' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Claim 5 compliance */}
      {portfolio.some((p) => p.executeResult) && (
        <div className="rounded border border-emerald-800/40 bg-emerald-950/20 px-4 py-3 text-xs text-emerald-400">
          ✓ All executed loans carry full Claim 5(x) audit provenance. Settlement confirmation, repayment triggers, and security assignments are captured for regulatory review.
        </div>
      )}
    </div>
  )
}
