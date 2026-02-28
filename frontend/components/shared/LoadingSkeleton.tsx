export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-muted rounded"
          style={{ width: `${85 - i * 10}%` }}
        />
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-card p-4 animate-pulse">
      <div className="h-3 bg-muted rounded w-1/3 mb-3" />
      <div className="h-7 bg-muted rounded w-2/3 mb-2" />
      <div className="h-3 bg-muted rounded w-1/2" />
    </div>
  )
}
