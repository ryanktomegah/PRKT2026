'use client'

import { useState } from 'react'
import { KNOWN_BICS, getCurrencyPair } from '@/lib/api'
import type { ScoreRequest } from '@/lib/api'
import { cn } from '@/lib/utils'

interface PaymentFormProps {
  onSubmit: (req: ScoreRequest) => void
  isLoading: boolean
}

const PAYMENT_STATUSES = ['ACSP', 'RJCT', 'ACCC', 'PDNG']
const REJECTION_CODES = ['NONE', 'AC01', 'AC04', 'AG01', 'AM04', 'CUST', 'FF01', 'MD07', 'MS02', 'MS03', 'RR01', 'RR02', 'RR03', 'RR04', 'SL01']
const MESSAGE_PRIORITIES = ['NORM', 'HIGH', 'URGP']

export function PaymentForm({ onSubmit, isLoading }: PaymentFormProps) {
  const [sendingBic, setSendingBic] = useState('CHASUS33')
  const [receivingBic, setReceivingBic] = useState('SBINMUMU')
  const [amountUsd, setAmountUsd] = useState(5_000_000)
  const [paymentStatus, setPaymentStatus] = useState('RJCT')
  const [rejectionCode, setRejectionCode] = useState('AC01')
  const [hourOfDay, setHourOfDay] = useState(14)
  const [settlementLag, setSettlementLag] = useState(3)
  const [messagePriority, setMessagePriority] = useState('NORM')
  const [priorRejections, setPriorRejections] = useState(2)
  const [correspondentDepth, setCorrespondentDepth] = useState(3)
  const [dataQuality, setDataQuality] = useState(0.85)

  const currencyPair = getCurrencyPair(sendingBic, receivingBic)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({
      sending_bic: sendingBic,
      receiving_bic: receivingBic,
      currency_pair: currencyPair,
      amount_usd: amountUsd,
      payment_status: paymentStatus,
      rejection_code: rejectionCode,
      hour_of_day: hourOfDay,
      settlement_lag_days: settlementLag,
      message_priority: messagePriority,
      prior_rejections_30d: priorRejections,
      correspondent_depth: correspondentDepth,
      data_quality_score: dataQuality,
    })
  }

  const getBicInfo = (bic: string) => KNOWN_BICS.find((b) => b.bic === bic)
  const tierColor = (tier: number) =>
    tier === 1 ? 'text-emerald-400' : tier === 2 ? 'text-yellow-400' : 'text-red-400'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* BIC selectors */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Sending BIC</label>
          <select
            value={sendingBic}
            onChange={(e) => setSendingBic(e.target.value)}
            className="w-full bg-muted border border-border rounded px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {KNOWN_BICS.map((b) => (
              <option key={b.bic} value={b.bic}>
                {b.bic} — {b.name}
              </option>
            ))}
          </select>
          {getBicInfo(sendingBic) && (
            <p className="text-[11px] mt-0.5 text-muted-foreground">
              {getBicInfo(sendingBic)!.name} ·{' '}
              <span className={tierColor(getBicInfo(sendingBic)!.tier)}>
                Tier {getBicInfo(sendingBic)!.tier}
              </span>
            </p>
          )}
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Receiving BIC</label>
          <select
            value={receivingBic}
            onChange={(e) => setReceivingBic(e.target.value)}
            className="w-full bg-muted border border-border rounded px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {KNOWN_BICS.map((b) => (
              <option key={b.bic} value={b.bic}>
                {b.bic} — {b.name}
              </option>
            ))}
          </select>
          {getBicInfo(receivingBic) && (
            <p className="text-[11px] mt-0.5 text-muted-foreground">
              {getBicInfo(receivingBic)!.name} ·{' '}
              <span className={tierColor(getBicInfo(receivingBic)!.tier)}>
                Tier {getBicInfo(receivingBic)!.tier}
              </span>
            </p>
          )}
        </div>
      </div>

      {/* Currency corridor */}
      <div className="rounded border border-border bg-muted/30 px-3 py-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Currency Corridor</span>
        <span className="font-mono text-sm font-semibold text-blue-300">{currencyPair}</span>
      </div>

      {/* Amount */}
      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          Amount USD — <span className="font-mono text-foreground">${amountUsd.toLocaleString()}</span>
        </label>
        <input
          type="range"
          min={100_000}
          max={50_000_000}
          step={100_000}
          value={amountUsd}
          onChange={(e) => setAmountUsd(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
      </div>

      {/* Payment Status + Rejection Code */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Payment Status</label>
          <select
            value={paymentStatus}
            onChange={(e) => setPaymentStatus(e.target.value)}
            className="w-full bg-muted border border-border rounded px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {PAYMENT_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Rejection Code</label>
          <select
            value={rejectionCode}
            onChange={(e) => setRejectionCode(e.target.value)}
            className="w-full bg-muted border border-border rounded px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {REJECTION_CODES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Message Priority */}
      <div>
        <label className="block text-xs text-muted-foreground mb-1">Message Priority</label>
        <div className="flex gap-2">
          {MESSAGE_PRIORITIES.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setMessagePriority(p)}
              className={cn(
                'flex-1 py-1.5 rounded text-xs font-medium border transition-colors',
                messagePriority === p
                  ? 'bg-blue-600/30 text-blue-300 border-blue-600/50'
                  : 'bg-muted text-muted-foreground border-border hover:border-muted-foreground'
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Sliders */}
      {[
        { label: 'Hour of Day', value: hourOfDay, set: setHourOfDay, min: 0, max: 23, step: 1, fmt: (v: number) => `${v}:00` },
        { label: 'Settlement Lag Days', value: settlementLag, set: setSettlementLag, min: 0, max: 30, step: 1, fmt: (v: number) => `${v}d` },
        { label: 'Prior Rejections (30d)', value: priorRejections, set: setPriorRejections, min: 0, max: 10, step: 1, fmt: (v: number) => String(v) },
        { label: 'Correspondent Depth', value: correspondentDepth, set: setCorrespondentDepth, min: 1, max: 5, step: 1, fmt: (v: number) => String(v) },
        { label: 'Data Quality Score', value: dataQuality, set: setDataQuality, min: 0, max: 1, step: 0.05, fmt: (v: number) => v.toFixed(2) },
      ].map(({ label, value, set, min, max, step, fmt }) => (
        <div key={label}>
          <label className="block text-xs text-muted-foreground mb-1">
            {label} — <span className="font-mono text-foreground">{fmt(value)}</span>
          </label>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => set(Number(e.target.value))}
            className="w-full accent-blue-500"
          />
        </div>
      ))}

      {/* Submit */}
      <button
        type="submit"
        disabled={isLoading}
        className={cn(
          'w-full py-3 rounded-lg font-semibold text-sm transition-all',
          isLoading
            ? 'bg-blue-800/50 text-blue-400 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20'
        )}
      >
        {isLoading ? 'Analysing…' : 'Analyse Payment'}
      </button>
    </form>
  )
}
