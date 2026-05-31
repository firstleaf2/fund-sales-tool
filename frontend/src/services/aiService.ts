import api, { getUserId } from './api'
import type { ChartData } from '../types'

interface ChatResponse {
  reply: string
  sources: { type: string; id: number; name: string }[]
  conversation_id: string
  chart?: ChartData | null
}

export async function sendMessage(message: string, conversationId?: string) {
  const res = await api.post<ChatResponse>('/ai/chat', {
    message,
    conversation_id: conversationId,
    user_id: getUserId(),
  })
  return res.data
}

export async function getMessages(conversationId: string) {
  const res = await api.get<{ data: { role: string; content: string; created_at: string }[] }>(
    '/ai/messages',
    { params: { conversation_id: conversationId } }
  )
  return res.data.data
}

export async function getConversations() {
  const res = await api.get<{ data: { conversation_id: string; title: string; last_time: string }[] }>(
    '/ai/conversations',
    { params: { user_id: getUserId() } }
  )
  return res.data.data
}
