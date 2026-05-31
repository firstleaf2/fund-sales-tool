import api from './api'
import type { Fund, FundDetail, NAVHistoryItem } from '../types'

export async function getFunds(params?: { type?: string; keyword?: string; status?: string }) {
  const res = await api.get<{ data: Fund[]; total: number }>('/funds', { params })
  return res.data
}

export async function getFundDetail(id: number) {
  const res = await api.get<FundDetail>(`/funds/${id}`)
  return res.data
}

export async function getNAVHistory(id: number, days = 180) {
  const res = await api.get<{ fund_id: number; data: NAVHistoryItem[] }>(
    `/funds/${id}/nav-history`,
    { params: { days } }
  )
  return res.data
}
