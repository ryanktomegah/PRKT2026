'use client'

import { motion } from 'framer-motion'
import type { ExecuteResponse } from '@/lib/api'
import { ClaimBadge } from '@/components/shared/ClaimBadge'
import { formatCurrency, formatBps, cn } from '@/lib/utils'

interface ExecuteResultProps {
  data: ExecuteResponse
}

const LIFECYCLE_STAGES = [
  'Offer',
  'Acceptance',
  'Disbursement',
  'Monitoring',
  'Settlement',
  'Repayment',
  'Audit',
]

export function ExecuteResult({ data }: ExecuteResultProps) {
  const statusColor =
    data.offer_status === 'ACCEPTED'
      ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50'
      : data.offer_status === 'REJECTED'
      ? 'bg-red-950/40 text-red-400 border-red-800/50'
      : 'bg-yellow-950/40 text-yellow-400 border-yellow-800/50'

  // How far through the lifecycle?
  const activeStages =
    data.offer_status === 'ACCEPTED'
      ? data.settlement_status === 'SETTLED'
        ? LIFECYCLE_STAGES.length
        : 3
      : 1

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.6 }}
      className="rounded-lg border border-border bg-card p-5 space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Component 3 — Bridge Loan Execution</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Loan ID: <span className="font-mono">{data.loan_id}</span>
          </p>
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {['Claim 1(f-h)', '3(m)', '5(t-x)', 'D7', 'D11'].map((c) => (
            <ClaimBadge key={c} claim={c} />
          ))}
        </div>
      </div>

      {/* Offer status badge */}
      <div className={cn('rounded px-3 py-2 text-sm font-bold text-center border', statusColor)}>
        {data.offer_status}
      </div>

      {/* Lifecycle timeline */}
      <div>
        <p className="text-xs text-muted-foreground mb-3">Loan Lifecycle</p>
        <div className="flex items-center overflow-x-auto gap-0">
          {LIFECYCLE_STAGES.map((stage, idx) => {
            const isActive = idx < activeStages
            const isLast = idx === LIFECYCLE_STAGES.length - 1
            return (
              <div key={stage} className="flex items-center flex-shrink-0">
                <div className="flex flex-col items-center gap-1">
                  <motion.div
                    className={cn(
                      'w-6 h-6 rounded-full border-2 flex items-center justify-center text-[10px] font-bold',
                      isActive
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'bg-muted border-border text-muted-foreground'
                    )}
                    initial={{ scale: 0.5 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.6 + idx * 0.1 }}
                  >
                    {idx + 1}
                  </motion.div>
                  <span className={cn('text-[10px] text-center', isActive ? 'text-foreground' : 'text-muted-foreground')}>
                    {stage}
                  </span>
                </div>
                {!isLast && (
                  <div
                    className={cn(
                      'h-0.5 w-8 mx-1 mt-[-10px]',
                      idx < activeStages - 1 ? 'bg-blue-600' : 'bg-border'
                    )}
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Term sheet */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        {[
          { label: 'Advance Amount', value: formatCurrency(data.advance_amount_usd), accent: 'text-emerald-400' },
          { label: 'APR', value: formatBps(data.apr_bps), accent: 'text-blue-400' },
          { label: 'Total Cost', value: formatCurrency(data.total_cost_usd), accent: 'text-red-400' },
          { label: 'Horizon', value: `${data.offer_horizon_days}d`, accent: 'text-yellow-400' },
          { label: 'Collateral', value: data.collateral_type, accent: 'text-foreground' },
          { label: 'Repayment Trigger', value: data.repayment_trigger, accent: 'text-foreground' },
          { label: 'Settlement Source', value: data.settlement_source, accent: 'text-foreground' },
          { label: 'Settlement Status', value: data.settlement_status, accent: data.settlement_status === 'SETTLED' ? 'text-emerald-400' : 'text-yellow-400' },
        ].map(({ label, value, accent }) => (
          <div key={label}>
            <p className="text-muted-foreground">{label}</p>
            <p className={cn('font-mono font-medium mt-0.5', accent)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Security assignment */}
      <div className="rounded border border-border bg-muted/20 p-3">
        <p className="text-[11px] text-muted-foreground mb-1">Security Assignment</p>
        <p className="text-xs font-mono text-foreground">{data.security_assignment}</p>
      </div>

      {/* Disbursement ref */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-muted-foreground">Disbursement Ref:</span>
        <span className="font-mono text-blue-300">{data.disbursement_ref}</span>
      </div>

      {/* Claim 5 compliance */}
      <div className="rounded border border-emerald-800/40 bg-emerald-950/20 px-3 py-2 flex items-center justify-between">
        <span className="text-xs text-emerald-400">✓ Claim 5(x) Audit Record Captured</span>
        <ClaimBadge claim="Claim 5(x)" />
      </div>
    </motion.div>
  )
}
