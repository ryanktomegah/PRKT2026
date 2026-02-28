'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: 'default' | 'green' | 'red' | 'yellow' | 'blue'
}

export function MetricCard({ label, value, sub, accent = 'default' }: MetricCardProps) {
  const [displayed, setDisplayed] = useState(0)
  const numericValue = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.]/g, ''))
  const isNumeric = !isNaN(numericValue) && typeof value === 'number'

  useEffect(() => {
    if (!isNumeric) return
    let start = 0
    const end = numericValue
    const duration = 800
    const step = end / (duration / 16)
    const timer = setInterval(() => {
      start += step
      if (start >= end) {
        setDisplayed(end)
        clearInterval(timer)
      } else {
        setDisplayed(start)
      }
    }, 16)
    return () => clearInterval(timer)
  }, [numericValue, isNumeric])

  const accentClasses = {
    default: 'text-foreground',
    green: 'text-emerald-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    blue: 'text-blue-400',
  }

  const displayValue = isNumeric ? displayed : value

  return (
    <div className="rounded-lg border border-border bg-card p-4 flex flex-col gap-1">
      <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className={cn('text-2xl font-bold font-mono-nums', accentClasses[accent])} aria-live="off" aria-atomic="true">
        {isNumeric
          ? typeof value === 'number' && Number.isInteger(value)
            ? Math.round(displayed as number).toLocaleString()
            : (displayed as number).toFixed(2)
          : displayValue}
      </p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}
