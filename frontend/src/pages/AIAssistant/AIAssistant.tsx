import { useState, useRef, useEffect } from 'react'
import { Input, Button, Card, Typography, Tag, Spin, List } from 'antd'
import { SendOutlined, RobotOutlined, UserOutlined, PlusOutlined } from '@ant-design/icons'
import { sendMessageStream, getMessages, getConversations } from '../../services/aiService'
import ChatChart from '../../components/ChatChart'
import type { ChatMessage } from '../../types'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const CONV_STORAGE_KEY = 'fund_sales_conversation_id'

export default function AIAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | undefined>(
    () => localStorage.getItem(CONV_STORAGE_KEY) || undefined
  )
  const [conversations, setConversations] = useState<{ conversation_id: string; title: string; last_time: string }[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 加载会话列表
  useEffect(() => {
    getConversations().then(setConversations).catch(() => {})
  }, [])

  // 加载当前会话的历史消息
  useEffect(() => {
    if (!conversationId) return
    getMessages(conversationId).then((data) => {
      setMessages(data.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })))
    }).catch(() => {})
  }, [conversationId])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: ChatMessage = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMessage])
    const currentInput = input.trim()
    setInput('')
    setLoading(true)

    // 先添加一个空的 assistant 消息，后续逐字填充
    const assistantIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    await sendMessageStream(currentInput, conversationId, {
      onMeta: (sources, convId) => {
        setConversationId(convId)
        localStorage.setItem(CONV_STORAGE_KEY, convId)
        setMessages((prev) => {
          const updated = [...prev]
          updated[assistantIdx] = { ...updated[assistantIdx], sources }
          return updated
        })
      },
      onContent: (chunk) => {
        setMessages((prev) => {
          const updated = [...prev]
          updated[assistantIdx] = {
            ...updated[assistantIdx],
            content: updated[assistantIdx].content + chunk,
          }
          return updated
        })
      },
      onDone: () => {
        setLoading(false)
        getConversations().then(setConversations).catch(() => {})
      },
      onError: (error) => {
        setMessages((prev) => {
          const updated = [...prev]
          updated[assistantIdx] = { role: 'assistant', content: error || '抱歉，服务暂时不可用。' }
          return updated
        })
        setLoading(false)
      },
    })
  }

  const handleNewConversation = () => {
    setMessages([])
    setConversationId(undefined)
    localStorage.removeItem(CONV_STORAGE_KEY)
  }

  const handleSelectConversation = (cid: string) => {
    setConversationId(cid)
    localStorage.setItem(CONV_STORAGE_KEY, cid)
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 112px)', gap: 16 }}>
      {/* 左侧会话列表 */}
      <Card
        style={{ width: 240, overflow: 'auto' }}
        bodyStyle={{ padding: 8 }}
        title={<Text style={{ fontSize: 14 }}>历史会话</Text>}
        extra={<Button size="small" icon={<PlusOutlined />} onClick={handleNewConversation} />}
      >
        <List
          size="small"
          dataSource={conversations}
          renderItem={(item) => (
            <List.Item
              onClick={() => handleSelectConversation(item.conversation_id)}
              style={{
                cursor: 'pointer',
                padding: '8px',
                borderRadius: 4,
                background: item.conversation_id === conversationId ? '#e6f4ff' : undefined,
              }}
            >
              <Text ellipsis style={{ fontSize: 12 }}>{item.title}</Text>
            </List.Item>
          )}
        />
      </Card>

      {/* 右侧对话区 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Title level={4}>AI 智能助手</Title>

        <Card style={{ flex: 1, overflow: 'auto', marginBottom: 16 }} bodyStyle={{ padding: 16 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', color: '#999', marginTop: 60 }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <Paragraph>你好，我是 AI 销售助手。可以帮你：</Paragraph>
              <Paragraph type="secondary">- 根据客户风险偏好推荐基金</Paragraph>
              <Paragraph type="secondary">- 分析市场行情</Paragraph>
              <Paragraph type="secondary">- 提供销售话术建议</Paragraph>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} style={{ marginBottom: 16, display: 'flex', gap: 8, flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: msg.role === 'user' ? '#1677ff' : '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                {msg.role === 'user' ? <UserOutlined style={{ color: '#fff' }} /> : <RobotOutlined />}
              </div>
              <div style={{ maxWidth: '70%' }}>
                <div style={{ background: msg.role === 'user' ? '#1677ff' : '#f5f5f5', color: msg.role === 'user' ? '#fff' : '#333', padding: '8px 12px', borderRadius: 8, whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </div>
                {msg.chart && msg.chart.option && (
                  <ChatChart option={msg.chart.option} />
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    {msg.sources.map((s, i) => (
                      <Tag key={i} color={s.type === 'fund' ? 'blue' : 'green'} style={{ fontSize: 11 }}>
                        {s.type === 'fund' ? '基金' : '客户'}: {s.name}
                      </Tag>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <RobotOutlined />
              </div>
              <Spin size="small" />
            </div>
          )}
          <div ref={messagesEndRef} />
        </Card>

        <div style={{ display: 'flex', gap: 8 }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleSend() } }}
            placeholder="输入问题，如：给客户李明推荐什么基金？"
            autoSize={{ minRows: 1, maxRows: 3 }}
            style={{ flex: 1 }}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={loading}>
            发送
          </Button>
        </div>
      </div>
    </div>
  )
}
