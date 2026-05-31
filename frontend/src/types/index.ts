export interface Fund {
  id: number
  code: string
  name: string
  type: string
  nav: number
  daily_change: number | null
  risk_level: string
  manager: string | null
  status: string
}

export interface FundDetail extends Fund {
  established_date: string | null
  management_fee: number | null
  description: string | null
}

export interface NAVHistoryItem {
  date: string
  nav: number
  daily_change: number | null
}

export interface Customer {
  id: number
  name: string
  phone: string | null
  email: string | null
  risk_preference: string
  total_assets: number
  created_at: string | null
  notes: string | null
}

export interface CustomerCreate {
  name: string
  phone?: string
  email?: string
  risk_preference: string
  notes?: string
}

export interface HoldingItem {
  id: number
  fund_id: number
  fund_name: string
  fund_code: string
  shares: number
  cost_price: number
  current_nav: number
  market_value: number
  profit_loss: number
  profit_rate: number
  purchase_date: string
}

export interface HoldingsResponse {
  customer_id: number
  customer_name: string
  holdings: HoldingItem[]
  total_market_value: number
  total_profit_loss: number
}

export interface DashboardSummary {
  total_sales: number
  total_customers: number
  total_aum: number
  monthly_sales: number
}

export interface SalesTrendItem {
  date: string
  amount: number
}

export interface ProductDistributionItem {
  type: string
  label: string
  amount: number
  percentage: number
}

export interface ChartData {
  title: string
  option: Record<string, unknown>
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: { type: string; id: number; name: string }[]
  chart?: ChartData | null
}
