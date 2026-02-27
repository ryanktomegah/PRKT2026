'use client'

import { motion } from 'framer-motion'
import type { PriceResponse } from '@/lib/api'
import { ClaimBadge } from '@/components/shared/ClaimBadge'
import { formatCurrency, formatPercent, formatBps } from '@/lib/utils'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface PriceResultProps {
  data: PriceResponse
}

export function PriceResult({ data }: PriceResultProps) {
  const chartData = [
    { name: 'PD Structural', value: data.pd_structural * 100, color: '#3b82f6' },
    { name: 'PD ML Signal', value: data.pd_ml_signal * 100, color: '#8b5cf6' },
    { name: 'PD Blended', value: data.pd_blended * 100, color: '#06b6d4' },
    { name: 'LGD Estimate', value: data.lgd_estimate * 100, color: '#f59e0b' },
    { name: 'CVA Rate (ann.)', value: data.cva_cost_rate_annual * 100, color: '#ef4444' },
  ]

  const tierColor = data.counterparty_tier === 1
    ? 'text-emerald-400'
    : data.counterparty_tier === 2
    ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className="rounded-lg border border-border bg-card p-5 space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Component 2 — CVA Pricing</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data.counterparty_name} ·{' '}
            <span className={tierColor}>Tier {data.counterparty_tier}</span>
            {' · '}<span className="font-mono">{data.pd_tier_used}</span>
          </p>
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {['Claim 1(e)', 'D4', 'D5', 'D6', 'D7'].map((c) => (
            <ClaimBadge key={c} claim={c} />
          ))}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'APR', value: formatBps(data.annualized_rate_bps), accent: 'text-blue-400' },
          { label: 'Expected Loss', value: formatCurrency(data.expected_loss_usd), accent: 'text-red-400' },
          { label: 'Bridge Amount', value: formatCurrency(data.bridge_loan_amount), accent: 'text-emerald-400' },
          { label: 'Horizon', value: `${data.bridge_horizon_days}d`, accent: 'text-yellow-400' },
        ].map(({ label, value, accent }) => (
          <div key={label} className="rounded border border-border bg-muted/30 p-3">
            <p className="text-[11px] text-muted-foreground">{label}</p>
            <p className={`font-mono font-bold text-sm mt-0.5 ${accent}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div>
        <p className="text-xs text-muted-foreground mb-2">Credit Model Components (%)</p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} />
            <YAxis tick={{ fontSize: 9, fill: '#64748b' }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }}
              formatter={(v: number) => [`${v.toFixed(3)}%`, '']}
            />
            <Bar dataKey="value" radius={[2, 2, 0, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* PD breakdown */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <p className="text-muted-foreground">PD Structural</p>
          <p className="font-mono text-blue-400">{formatPercent(data.pd_structural)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">PD ML Signal</p>
          <p className="font-mono text-purple-400">{formatPercent(data.pd_ml_signal)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">PD Blended</p>
          <p className="font-mono text-cyan-400">{formatPercent(data.pd_blended)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">LGD Estimate</p>
          <p className="font-mono text-yellow-400">{formatPercent(data.lgd_estimate)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">EAD</p>
          <p className="font-mono">{formatCurrency(data.ead_usd)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Expected Profit</p>
          <p className="font-mono text-emerald-400">{formatCurrency(data.expected_profit_usd)}</p>
        </div>
      </div>
    </motion.div>
  )
}
