'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useALBSStore } from '@/lib/store'
import {
  LayoutDashboard,
  Search,
  BarChart3,
  ClipboardList,
  Activity,
} from 'lucide-react'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/analysis', label: 'Analysis', icon: Search },
  { href: '/portfolio', label: 'Portfolio', icon: BarChart3 },
  { href: '/audit', label: 'Audit Trail', icon: ClipboardList },
]

export function Sidebar() {
  const pathname = usePathname()
  const health = useALBSStore((s) => s.health)

  return (
    <aside className="fixed left-0 top-0 h-full w-56 border-r border-border bg-card flex flex-col z-20">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <Activity className="h-5 w-5 text-blue-400" />
          <span className="font-semibold text-sm text-foreground leading-tight">ALBS</span>
        </div>
        <p className="text-[10px] text-muted-foreground leading-snug">
          Automated Liquidity Bridging System
        </p>
        <p className="text-[10px] text-blue-400/70 mt-0.5">Patent Spec v4.0</p>
      </div>

      {/* Model stats */}
      {health && (
        <div className="px-4 py-3 border-b border-border space-y-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-muted-foreground">AUC</span>
            <span className="font-mono text-emerald-400">{health.model_auc.toFixed(3)}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-muted-foreground">Threshold</span>
            <span className="font-mono text-yellow-400">{health.threshold.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-muted-foreground">Recall</span>
            <span className="font-mono text-blue-400">{(health.model_recall * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              pathname === href
                ? 'bg-blue-600/20 text-blue-300 border border-blue-600/30'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-border">
        <p className="text-[10px] text-muted-foreground">© 2026 Patent Spec v4.0</p>
      </div>
    </aside>
  )
}
