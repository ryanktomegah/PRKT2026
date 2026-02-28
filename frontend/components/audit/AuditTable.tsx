'use client'

import { useState } from 'react'
import { useALBSStore, type PortfolioItem } from '@/lib/store'
import { formatCurrency, formatBps } from '@/lib/utils'
import { ChevronDown, ChevronRight, Download } from 'lucide-react'
import { ClaimBadge } from '@/components/shared/ClaimBadge'

function AuditRow({ item, index }: { item: PortfolioItem; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const exec = item.executeResult

  const auditRecord = {
    loan_id: exec?.loan_id,
    uetr: item.scoreResult.uetr,
    timestamp: item.timestamp.toISOString(),
    advance_details: exec
      ? {
          advance_amount_usd: exec.advance_amount_usd,
          apr_bps: exec.apr_bps,
          total_cost_usd: exec.total_cost_usd,
          offer_horizon_days: exec.offer_horizon_days,
          collateral_type: exec.collateral_type,
        }
      : null,
    settlement_confirmation: exec
      ? {
          settlement_status: exec.settlement_status,
          settlement_source: exec.settlement_source,
          disbursement_ref: exec.disbursement_ref,
        }
      : null,
    repayment_details: exec
      ? {
          repayment_trigger: exec.repayment_trigger,
          security_assignment: exec.security_assignment,
        }
      : null,
    net_return: item.priceResult?.expected_profit_usd,
    failure_probability: item.scoreResult.failure_probability,
    bridge_recommendation: item.scoreResult.bridge_recommendation,
    claim_provenance: exec?.claim_coverage ?? item.scoreResult.claim_coverage,
  }

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-5 py-3 hover:bg-muted/20 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        <span className="font-mono text-xs text-muted-foreground w-6">{index + 1}</span>
        <span className="font-mono text-xs text-blue-300 flex-1 truncate">{item.scoreResult.uetr}</span>
        <span className="font-mono text-xs">{item.scoreResult.currency_pair}</span>
        <span className="font-mono text-xs">{formatCurrency(item.scoreResult.amount_usd)}</span>
        {exec && (
          <span className={`font-mono text-xs ${exec.offer_status === 'ACCEPTED' ? 'text-emerald-400' : exec.offer_status === 'REJECTED' ? 'text-red-400' : 'text-yellow-400'}`}>
            {exec.offer_status}
          </span>
        )}
        {item.priceResult && (
          <span className="font-mono text-xs text-emerald-400">
            {formatCurrency(item.priceResult.expected_profit_usd)}
          </span>
        )}
        {exec && <ClaimBadge claim="Claim 5(x)" />}
      </button>

      {expanded && (
        <div className="px-5 pb-4 bg-black/20">
          <pre className="text-[11px] font-mono text-slate-300 overflow-x-auto bg-slate-950/50 rounded border border-border p-4 leading-relaxed">
            {JSON.stringify(auditRecord, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export function AuditTable() {
  const portfolio = useALBSStore((s) => s.portfolio)
  const executed = portfolio.filter((p) => p.executeResult)

  function downloadJSON() {
    const records = executed.map((item) => ({
      loan_id: item.executeResult!.loan_id,
      uetr: item.scoreResult.uetr,
      timestamp: item.timestamp.toISOString(),
      corridor: item.scoreResult.currency_pair,
      amount_usd: item.scoreResult.amount_usd,
      failure_probability: item.scoreResult.failure_probability,
      offer_status: item.executeResult!.offer_status,
      advance_amount_usd: item.executeResult!.advance_amount_usd,
      apr_bps: item.executeResult!.apr_bps,
      settlement_status: item.executeResult!.settlement_status,
      net_return: item.priceResult?.expected_profit_usd,
      claim_provenance: item.executeResult!.claim_coverage,
    }))
    const blob = new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'albs-audit-trail.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  function downloadCSV() {
    const headers = ['loan_id', 'uetr', 'timestamp', 'corridor', 'amount_usd', 'failure_probability', 'offer_status', 'advance_amount_usd', 'apr_bps', 'settlement_status', 'net_return']
    const rows = executed.map((item) => [
      item.executeResult!.loan_id,
      item.scoreResult.uetr,
      item.timestamp.toISOString(),
      item.scoreResult.currency_pair,
      item.scoreResult.amount_usd,
      item.scoreResult.failure_probability.toFixed(4),
      item.executeResult!.offer_status,
      item.executeResult!.advance_amount_usd,
      item.executeResult!.apr_bps,
      item.executeResult!.settlement_status,
      item.priceResult?.expected_profit_usd ?? '',
    ])
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'albs-audit-trail.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (portfolio.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
        No audit records yet. Execute bridge loans on the Analysis page to generate records.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {executed.length} executed loan{executed.length !== 1 ? 's' : ''} · {portfolio.length} total analyses
        </p>
        {executed.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={downloadJSON}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-border bg-muted hover:bg-muted/70 text-foreground transition-colors"
            >
              <Download className="h-3 w-3" />
              JSON
            </button>
            <button
              onClick={downloadCSV}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-border bg-muted hover:bg-muted/70 text-foreground transition-colors"
            >
              <Download className="h-3 w-3" />
              CSV
            </button>
          </div>
        )}
      </div>

      {/* Table header */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-2 border-b border-border bg-muted/20 text-[11px] text-muted-foreground font-medium">
          <span className="w-4" />
          <span className="w-6">#</span>
          <span className="flex-1">UETR</span>
          <span>Corridor</span>
          <span>Amount</span>
          <span>Status</span>
          <span>Net Return</span>
          <span>Claim</span>
        </div>

        {portfolio.map((item, idx) => (
          <AuditRow key={item.id} item={item} index={idx} />
        ))}
      </div>

      {/* Regulatory note */}
      <div className="rounded border border-blue-800/40 bg-blue-950/20 px-4 py-3 text-xs text-blue-300">
        All records include full Claim 5(x) provenance: loan_id, UETR, advance details, settlement confirmation, repayment details, net return, and claim coverage mapping.
      </div>
    </div>
  )
}
