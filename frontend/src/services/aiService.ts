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

export interface StreamCallbacks {
  onMeta: (sources: { type: string; id: number; name: string }[], conversationId: string) => void
  onContent: (chunk: string) => void
  onDone: () => void
  onError: (error: string) => void
}

export async function sendMessageStream(
  message: string,
  conversationId: string | undefined,
  callbacks: StreamCallbacks,
) {
  try {
    const response = await fetch('/api/ai/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-Id': getUserId() },
      body: JSON.stringify({ message, conversation_id: conversationId, user_id: getUserId() }),
    })

    if (!response.ok || !response.body) {
      callbacks.onError('请求失败')
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        try {
          const event = JSON.parse(jsonStr)
          if (event.type === 'meta') {
            callbacks.onMeta(event.sources || [], event.conversation_id || '')
          } else if (event.type === 'content') {
            callbacks.onContent(event.data)
          } else if (event.type === 'done') {
            callbacks.onDone()
          }
        } catch {
          // ignore parse errors
        }
      }
    }
  } catch {
    callbacks.onError('网络错误')
  }
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
