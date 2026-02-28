'use client'

import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '@/lib/api'
import { useALBSStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function HealthIndicator() {
  const setHealth = useALBSStore((s) => s.setHealth)

  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const h = await fetchHealth()
      setHealth(h)
      return h
    },
    refetchInterval: 15_000,
    retry: false,
  })

  const isHealthy = !isError && data?.status === 'ok' && data?.model_ready

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          'relative flex h-2 w-2',
        )}
      >
        <span
          className={cn(
            'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
            isHealthy ? 'bg-emerald-400' : 'bg-red-400'
          )}
        />
        <span
          className={cn(
            'relative inline-flex rounded-full h-2 w-2',
            isHealthy ? 'bg-emerald-500' : 'bg-red-500'
          )}
        />
      </span>
      <span className="text-xs text-muted-foreground">
        {isError ? 'API Offline' : data ? (data.model_ready ? 'Model Ready' : 'Loading…') : 'Connecting…'}
      </span>
    </div>
  )
}
