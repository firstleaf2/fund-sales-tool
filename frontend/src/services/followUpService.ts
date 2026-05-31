import api from './api'

export interface FollowUp {
  id: number
  customer_id: number
  contact_method: string
  content: string
  follow_date: string
  created_at: string
}

export interface FollowUpCreate {
  customer_id: number
  contact_method: string
  content: string
  follow_date?: string
}

export async function getFollowUps(customerId: number) {
  const res = await api.get<{ data: FollowUp[]; total: number }>(`/follow-ups/${customerId}`)
  return res.data
}

export async function createFollowUp(data: FollowUpCreate) {
  const res = await api.post<FollowUp>('/follow-ups', data)
  return res.data
}

export async function deleteFollowUp(id: number) {
  await api.delete(`/follow-ups/${id}`)
}
