import api from './api'
import type { DashboardSummary, SalesTrendItem, ProductDistributionItem } from '../types'

export async function getDashboardSummary() {
  const res = await api.get<DashboardSummary>('/dashboard/summary')
  return res.data
}

export async function getSalesTrend(period = 'day', days = 30) {
  const res = await api.get<{ period: string; data: SalesTrendItem[] }>(
    '/dashboard/sales-trend',
    { params: { period, days } }
  )
  return res.data
}

export async function getProductDistribution() {
  const res = await api.get<{ data: ProductDistributionItem[] }>('/dashboard/product-distribution')
  return res.data
}
