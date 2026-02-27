import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatPercent(value: number, decimals = 2): string {
  return `${(value * 100).toFixed(decimals)}%`
}

export function formatBps(value: number): string {
  return `${value.toFixed(0)} bps`
}

export function formatMs(value: number): string {
  return `${value.toFixed(1)} ms`
}
