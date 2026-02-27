'use client'

import { motion } from 'framer-motion'
import type { ScoreResponse } from '@/lib/api'
import { ClaimBadge } from '@/components/shared/ClaimBadge'
import { formatPercent, formatMs } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface ScoreResultProps {
  data: ScoreResponse
}

export function ScoreResult({ data }: ScoreResultProps) {
  const prob = data.failure_probability
  const probPct = prob * 100

  // Gauge color
  const gaugeColor =
    probPct < 30 ? '#10b981' : probPct < 60 ? '#f59e0b' : '#ef4444'

  const maxShap = Math.max(...data.top_risk_factors.map((f) => Math.abs(f.shap_value)))

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-lg border border-border bg-card p-5 space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Component 1 — Failure Prediction</h3>
          <p className="text-xs text-muted-foreground mt-0.5">UETR: <span className="font-mono">{data.uetr}</span></p>
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {['Claim 1(a)', 'Claim 1(b)', 'Claim 1(c)', 'Claim 1(d)', 'D1', 'D3'].map((c) => (
            <ClaimBadge key={c} claim={c} />
          ))}
        </div>
      </div>

      {/* Probability gauge */}
      <div className="flex items-center gap-6">
        <div className="relative flex-shrink-0">
          <svg width="100" height="60" viewBox="0 0 100 60">
            {/* Background arc */}
            <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="#1e293b" strokeWidth="8" strokeLinecap="round" />
            {/* Foreground arc */}
            <motion.path
              d="M 10 55 A 40 40 0 0 1 90 55"
              fill="none"
              stroke={gaugeColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray="126"
              initial={{ strokeDashoffset: 126 }}
              animate={{ strokeDashoffset: 126 - (prob * 126) }}
              transition={{ duration: 1, ease: 'easeOut' }}
            />
            <text x="50" y="52" textAnchor="middle" fontSize="14" fontWeight="bold" fill={gaugeColor} fontFamily="monospace">
              {probPct.toFixed(1)}%
            </text>
          </svg>
          <p className="text-[10px] text-muted-foreground text-center -mt-1">Failure Prob.</p>
        </div>

        <div className="flex-1 space-y-2">
          {/* Bridge recommendation */}
          <div
            className={cn(
              'rounded px-3 py-2 text-sm font-bold text-center border',
              data.threshold_exceeded
                ? 'bg-red-950/40 text-red-400 border-red-800/50'
                : 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50'
            )}
          >
            {data.bridge_recommendation}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">Threshold: </span>
              <span className="font-mono">{formatPercent(data.decision_threshold)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Distance: </span>
              <span className={cn('font-mono', data.threshold_exceeded ? 'text-red-400' : 'text-emerald-400')}>
                {data.distance_from_threshold > 0 ? '+' : ''}{formatPercent(data.distance_from_threshold)}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Confidence: </span>
              <span className={cn('font-mono', data.is_high_confidence ? 'text-emerald-400' : 'text-yellow-400')}>
                {data.is_high_confidence ? 'High' : 'Low'}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-muted-foreground">Latency: </span>
              <span className="font-mono">{formatMs(data.inference_latency_ms)}</span>
              {data.inference_latency_ms < 100 && <ClaimBadge claim="D9" />}
            </div>
          </div>
        </div>
      </div>

      {/* SHAP risk factors */}
      <div>
        <p className="text-xs text-muted-foreground mb-2 font-medium">Top Risk Factors (SHAP)</p>
        <div className="space-y-2">
          {data.top_risk_factors.map((factor, idx) => {
            const pct = (Math.abs(factor.shap_value) / maxShap) * 100
            const isPositive = factor.direction === 'increases_risk' || factor.shap_value > 0
            return (
              <div key={idx} className="space-y-0.5">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground font-mono">{factor.feature}</span>
                  <span className={cn('font-mono', isPositive ? 'text-red-400' : 'text-emerald-400')}>
                    {isPositive ? '+' : ''}{factor.shap_value.toFixed(4)}
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <motion.div
                    className={cn('h-full rounded-full', isPositive ? 'bg-red-500' : 'bg-emerald-500')}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.6, delay: idx * 0.1 }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}
