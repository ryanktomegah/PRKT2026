const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface HealthResponse {
  status: string
  model_ready: boolean
  threshold: number
  model_auc: number
  model_recall: number
  timestamp: string
}

export interface ScoreRequest {
  sending_bic: string
  receiving_bic: string
  currency_pair: string
  amount_usd: number
  payment_status: string
  rejection_code: string
  hour_of_day: number
  settlement_lag_days: number
  message_priority: string
  prior_rejections_30d: number
  correspondent_depth: number
  data_quality_score: number
}

export interface RiskFactor {
  feature: string
  shap_value: number
  direction: string
}

export interface ScoreResponse {
  uetr: string
  failure_probability: number
  threshold_exceeded: boolean
  decision_threshold: number
  bridge_recommendation: string
  top_risk_factors: RiskFactor[]
  amount_usd: number
  currency_pair: string
  sending_bic: string
  receiving_bic: string
  settlement_lag_days: number
  payment_status: string
  is_high_confidence: boolean
  distance_from_threshold: number
  inference_latency_ms: number
  claim_coverage: Record<string, string>
}

export interface PriceResponse {
  uetr: string
  currency_pair: string
  sending_bic: string
  receiving_bic: string
  counterparty_name: string
  counterparty_tier: number
  pd_structural: number
  pd_ml_signal: number
  pd_blended: number
  lgd_estimate: number
  ead_usd: number
  expected_loss_usd: number
  discount_factor: number
  risk_free_rate: number
  cva_cost_rate_annual: number
  funding_spread_bps: number
  net_margin_bps: number
  annualized_rate_bps: number
  apr_decimal: number
  bridge_loan_amount: number
  bridge_horizon_days: number
  expected_profit_usd: number
  offer_valid_seconds: number
  pd_tier_used: string
  pd_model_diagnostics: Record<string, unknown>
  lgd_model_diagnostics: Record<string, unknown>
  top_risk_factors: RiskFactor[]
  threshold_exceeded: boolean
  claim_coverage: Record<string, string>
}

export interface ExecuteResponse {
  loan_id: string
  uetr: string
  offer_status: 'ACCEPTED' | 'REJECTED' | 'EXPIRED'
  advance_amount_usd: number
  apr_bps: number
  total_cost_usd: number
  offer_horizon_days: number
  valid_until: string
  collateral_type: string
  repayment_trigger: string
  settlement_source: string
  security_assignment: string
  disbursement_ref: string
  settlement_status: string
  claim_coverage: Record<string, string>
}

export interface BicInfo {
  bic: string
  name: string
  region: string
  tier: number
}

export const KNOWN_BICS: BicInfo[] = [
  { bic: 'DEUTDEDB', name: 'Deutsche Bank', region: 'EU', tier: 1 },
  { bic: 'BNPAFRPP', name: 'BNP Paribas', region: 'EU', tier: 1 },
  { bic: 'HSBCGB2L', name: 'HSBC', region: 'GB', tier: 1 },
  { bic: 'CHASUS33', name: 'JPMorgan Chase', region: 'US', tier: 1 },
  { bic: 'CITIUS33', name: 'Citibank', region: 'US', tier: 1 },
  { bic: 'SBINMUMU', name: 'State Bank of India', region: 'IN', tier: 2 },
  { bic: 'BRADBRSP', name: 'Bradesco', region: 'BR', tier: 2 },
  { bic: 'ABORKEN1', name: 'Abor Bank', region: 'KE', tier: 3 },
  { bic: 'LOYDGB2L', name: 'Lloyds', region: 'GB', tier: 1 },
  { bic: 'MABOROBU', name: 'Maborou Bank', region: 'BU', tier: 3 },
]

// Currency mapping by BIC region
const REGION_CURRENCY: Record<string, string> = {
  EU: 'EUR', GB: 'GBP', US: 'USD', IN: 'INR', BR: 'BRL', KE: 'KES', BU: 'MMK',
}

export function getCurrencyPair(sendingBic: string, receivingBic: string): string {
  const sender = KNOWN_BICS.find(b => b.bic === sendingBic)
  const receiver = KNOWN_BICS.find(b => b.bic === receivingBic)
  if (!sender || !receiver) return 'USD/USD'
  const sc = REGION_CURRENCY[sender.region] || 'USD'
  const rc = REGION_CURRENCY[receiver.region] || 'USD'
  return `${sc}/${rc}`
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`)
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function scorePayment(req: ScoreRequest): Promise<ScoreResponse> {
  const res = await fetch(`${API_URL}/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Score request failed: ${res.statusText}`)
  return res.json()
}

export async function pricePayment(scoreData: ScoreResponse): Promise<PriceResponse> {
  const res = await fetch(`${API_URL}/price`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scoreData),
  })
  if (!res.ok) throw new Error(`Price request failed: ${res.statusText}`)
  return res.json()
}

export async function executePayment(priceData: PriceResponse): Promise<ExecuteResponse> {
  const res = await fetch(`${API_URL}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(priceData),
  })
  if (!res.ok) throw new Error(`Execute request failed: ${res.statusText}`)
  return res.json()
}
