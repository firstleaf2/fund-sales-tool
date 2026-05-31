import api from './api'
import type { Customer, CustomerCreate, HoldingsResponse } from '../types'

export async function getCustomers() {
  const res = await api.get<{ data: Customer[]; total: number }>('/customers')
  return res.data
}

export async function createCustomer(data: CustomerCreate) {
  const res = await api.post<Customer>('/customers', data)
  return res.data
}

export async function updateCustomer(id: number, data: Partial<CustomerCreate>) {
  const res = await api.put<Customer>(`/customers/${id}`, data)
  return res.data
}

export async function getCustomerHoldings(id: number) {
  const res = await api.get<HoldingsResponse>(`/customers/${id}/holdings`)
  return res.data
}
