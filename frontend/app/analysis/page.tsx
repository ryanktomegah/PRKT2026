'use client'

import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { PaymentForm } from '@/components/analysis/PaymentForm'
import { ScoreResult } from '@/components/analysis/ScoreResult'
import { PriceResult } from '@/components/analysis/PriceResult'
import { ExecuteResult } from '@/components/analysis/ExecuteResult'
import { useALBSStore } from '@/lib/store'
import {
  scorePayment,
  pricePayment,
  executePayment,
  type ScoreRequest,
  type ScoreResponse,
  type PriceResponse,
  type ExecuteResponse,
} from '@/lib/api'

export default function AnalysisPage() {
  const addPortfolioItem = useALBSStore((s) => s.addPortfolioItem)

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [scoreResult, setScoreResult] = useState<ScoreResponse | null>(null)
  const [priceResult, setPriceResult] = useState<PriceResponse | null>(null)
  const [executeResult, setExecuteResult] = useState<ExecuteResponse | null>(null)

  async function handleAnalyse(req: ScoreRequest) {
    setIsLoading(true)
    setError(null)
    setScoreResult(null)
    setPriceResult(null)
    setExecuteResult(null)

    try {
      // Step 1: Score
      const score = await scorePayment(req)
      setScoreResult(score)

      if (!score.threshold_exceeded) {
        addPortfolioItem({ id: score.uetr, timestamp: new Date(), scoreResult: score })
        return
      }

      // Step 2: Price (with intentional 300ms delay for cascade effect)
      await new Promise((r) => setTimeout(r, 300))
      const price = await pricePayment(score)
      setPriceResult(price)

      // Step 3: Execute (with intentional 300ms delay)
      await new Promise((r) => setTimeout(r, 300))
      const execute = await executePayment(price)
      setExecuteResult(execute)

      addPortfolioItem({
        id: score.uetr,
        timestamp: new Date(),
        scoreResult: score,
        priceResult: price,
        executeResult: execute,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred. Is the backend running?')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div>
      <Header title="Analysis" subtitle="Payment Failure Prediction & Bridge Loan Orchestration" />
      <main className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left panel — form */}
          <div className="rounded-lg border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Payment Configuration</h2>
            <PaymentForm onSubmit={handleAnalyse} isLoading={isLoading} />
          </div>

          {/* Right panel — results cascade */}
          <div className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-800/50 bg-red-950/30 p-4 text-sm text-red-400">
                <strong>Error:</strong> {error}
              </div>
            )}

            {!scoreResult && !isLoading && !error && (
              <div className="rounded-lg border border-border bg-card/50 p-10 text-center">
                <p className="text-muted-foreground text-sm">
                  Configure a payment and click <strong className="text-foreground">Analyse Payment</strong> to run the pipeline.
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Results will cascade: Prediction → CVA Pricing → Execution
                </p>
              </div>
            )}

            {isLoading && !scoreResult && (
              <div className="rounded-lg border border-border bg-card p-6 animate-pulse">
                <div className="h-4 bg-muted rounded w-1/2 mb-3" />
                <div className="h-20 bg-muted rounded mb-3" />
                <div className="h-4 bg-muted rounded w-2/3" />
              </div>
            )}

            {scoreResult && <ScoreResult data={scoreResult} />}
            {priceResult && <PriceResult data={priceResult} />}
            {executeResult && <ExecuteResult data={executeResult} />}
          </div>
        </div>
      </main>
    </div>
  )
}
