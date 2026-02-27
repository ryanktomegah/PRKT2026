'use client'

import { Header } from '@/components/layout/Header'
import { AuditTable } from '@/components/audit/AuditTable'

export default function AuditPage() {
  return (
    <div>
      <Header title="Audit Trail" subtitle="Claim 5(x) — Regulatory-Grade Loan Records" />
      <main className="p-6">
        <AuditTable />
      </main>
    </div>
  )
}
