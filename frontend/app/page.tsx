'use client'

import { useALBSStore } from '@/lib/store'
import { Header } from '@/components/layout/Header'
import { MetricCard } from '@/components/shared/MetricCard'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { ArrowRight, Cpu, DollarSign, ShieldCheck } from 'lucide-react'

export default function DashboardPage() {
  const portfolio = useALBSStore((s) => s.portfolio)
  const health = useALBSStore((s) => s.health)

  const total = portfolio.length
  const flagged = portfolio.filter((p) => p.scoreResult.threshold_exceeded).length
  const accepted = portfolio.filter((p) => p.executeResult?.offer_status === 'ACCEPTED').length
  const acceptanceRate = total > 0 ? accepted / total : 0
  const netReturn = portfolio.reduce((sum, p) => {
    return sum + (p.priceResult?.expected_profit_usd ?? 0)
  }, 0)

  const pipelineSteps = [
    {
      id: 1,
      label: 'Failure Prediction',
      sub: 'ML scoring with SHAP',
      icon: Cpu,
      claim: 'Claim 1(a-d)',
      color: 'blue',
    },
    {
      id: 2,
      label: 'CVA Pricing',
      sub: 'Structural + ML PD blend',
      icon: DollarSign,
      claim: 'Claim 1(e)',
      color: 'yellow',
    },
    {
      id: 3,
      label: 'Bridge Execution',
      sub: 'Offer → Disburse → Settle',
      icon: ShieldCheck,
      claim: 'Claim 1(f-h)',
      color: 'emerald',
    },
  ]

  const colorMap: Record<string, string> = {
    blue: 'text-blue-400 bg-blue-950/40 border-blue-800/50',
    yellow: 'text-yellow-400 bg-yellow-950/40 border-yellow-800/50',
    emerald: 'text-emerald-400 bg-emerald-950/40 border-emerald-800/50',
  }

  return (
    <div>
      <Header title="Dashboard" subtitle="System Overview" />
      <main className="p-6 space-y-6">
        {/* Metric cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Total Analysed"
            value={total}
            sub="payments in session"
          />
          <MetricCard
            label="Total Flagged"
            value={flagged}
            sub="threshold exceeded"
            accent="yellow"
          />
          <MetricCard
            label="Acceptance Rate"
            value={total > 0 ? formatPercent(acceptanceRate) : '—'}
            sub="bridge loans offered"
            accent="green"
          />
          <MetricCard
            label="Net Return"
            value={total > 0 ? formatCurrency(netReturn) : '—'}
            sub="expected profit pool"
            accent="blue"
          />
        </div>

        {/* Pipeline diagram */}
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-sm font-semibold text-foreground mb-4">
            Pipeline Architecture
          </h2>
          <div className="flex items-center gap-0 overflow-x-auto">
            {pipelineSteps.map((step, idx) => {
              const Icon = step.icon
              return (
                <div key={step.id} className="flex items-center">
                  <div
                    className={`rounded-lg border p-4 min-w-[160px] flex flex-col gap-2 ${colorMap[step.color]}`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      <span className="text-xs font-semibold">{step.label}</span>
                    </div>
                    <p className="text-[11px] opacity-70">{step.sub}</p>
                    <span className="text-[10px] font-mono bg-black/20 px-1.5 py-0.5 rounded w-fit">
                      {step.claim}
                    </span>
                  </div>
                  {idx < pipelineSteps.length - 1 && (
                    <ArrowRight className="h-5 w-5 mx-3 text-muted-foreground flex-shrink-0" />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* System status */}
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-sm font-semibold text-foreground mb-4">System Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground text-xs mb-1">API Health</p>
              <p className={`font-medium ${health?.status === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
                {health?.status === 'ok' ? '✓ Online' : '✗ Offline'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Model Ready</p>
              <p className={`font-medium ${health?.model_ready ? 'text-emerald-400' : 'text-yellow-400'}`}>
                {health?.model_ready ? '✓ Ready' : '○ Loading'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Decision Threshold</p>
              <p className="font-mono text-yellow-400">
                {health?.threshold?.toFixed(2) ?? '—'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Model AUC</p>
              <p className="font-mono text-blue-400">
                {health?.model_auc?.toFixed(3) ?? '—'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Model Recall</p>
              <p className="font-mono text-blue-400">
                {health?.model_recall !== undefined
                  ? formatPercent(health.model_recall)
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-1">Last Checked</p>
              <p className="font-mono text-muted-foreground text-xs">
                {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : '—'}
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
