import { cn } from '@/lib/utils'

interface ClaimBadgeProps {
  claim: string
  className?: string
}

export function ClaimBadge({ claim, className }: ClaimBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium',
        'bg-blue-950/60 text-blue-300 border border-blue-800/50',
        className
      )}
    >
      {claim}
    </span>
  )
}
