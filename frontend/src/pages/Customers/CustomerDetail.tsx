import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Descriptions, Table, Tag, Button, Form, Input, Select, Spin, Empty, message, Timeline, Modal, DatePicker } from 'antd'
import { ArrowLeftOutlined, EditOutlined, SaveOutlined, PlusOutlined, PhoneOutlined, MessageOutlined, TeamOutlined, MailOutlined, DeleteOutlined } from '@ant-design/icons'
import { getCustomers, updateCustomer, getCustomerHoldings } from '../../services/customerService'
import { getFollowUps, createFollowUp, deleteFollowUp, type FollowUp } from '../../services/followUpService'
import type { Customer, HoldingItem } from '../../types'
import dayjs from 'dayjs'

const riskOptions = [
  { value: 'conservative', label: '保守型' },
  { value: 'moderate', label: '稳健型' },
  { value: 'aggressive', label: '激进型' },
]
const riskLabels: Record<string, string> = { conservative: '保守型', moderate: '稳健型', aggressive: '激进型' }
const riskColors: Record<string, string> = { conservative: 'green', moderate: 'blue', aggressive: 'red' }

const methodOptions = [
  { value: 'phone', label: '电话' },
  { value: 'wechat', label: '微信' },
  { value: 'meeting', label: '面谈' },
  { value: 'email', label: '邮件' },
]
const methodIcons: Record<string, React.ReactNode> = {
  phone: <PhoneOutlined />,
  wechat: <MessageOutlined />,
  meeting: <TeamOutlined />,
  email: <MailOutlined />,
}
const methodLabels: Record<string, string> = { phone: '电话', wechat: '微信', meeting: '面谈', email: '邮件' }

export default function CustomerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [holdings, setHoldings] = useState<HoldingItem[]>([])
  const [totalMarketValue, setTotalMarketValue] = useState(0)
  const [totalProfitLoss, setTotalProfitLoss] = useState(0)
  const [followUps, setFollowUps] = useState<FollowUp[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [followUpModalOpen, setFollowUpModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [followUpForm] = Form.useForm()

  const fetchData = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [custRes, holdRes, fuRes] = await Promise.all([
        getCustomers(),
        getCustomerHoldings(Number(id)),
        getFollowUps(Number(id)),
      ])
      const cust = custRes.data.find((c: Customer) => c.id === Number(id))
      setCustomer(cust || null)
      setHoldings(holdRes.holdings)
      setTotalMarketValue(holdRes.total_market_value)
      setTotalProfitLoss(holdRes.total_profit_loss)
      setFollowUps(fuRes.data)
      if (cust) form.setFieldsValue(cust)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [id])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      await updateCustomer(Number(id), values)
      message.success('更新成功')
      setEditing(false)
      setCustomer({ ...customer!, ...values })
    } catch { /* validation error */ }
  }

  const handleAddFollowUp = async () => {
    try {
      const values = await followUpForm.validateFields()
      await createFollowUp({
        customer_id: Number(id),
        contact_method: values.contact_method,
        content: values.content,
        follow_date: values.follow_date?.toISOString(),
      })
      message.success('跟进记录已添加')
      setFollowUpModalOpen(false)
      followUpForm.resetFields()
      const fuRes = await getFollowUps(Number(id))
      setFollowUps(fuRes.data)
    } catch { /* validation error */ }
  }

  const handleDeleteFollowUp = async (fuId: number) => {
    await deleteFollowUp(fuId)
    message.success('已删除')
    const fuRes = await getFollowUps(Number(id))
    setFollowUps(fuRes.data)
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!customer) return <Empty description="客户不存在" />

  const holdingColumns = [
    { title: '基金名称', dataIndex: 'fund_name', key: 'fund_name' },
    { title: '基金代码', dataIndex: 'fund_code', key: 'fund_code', width: 90 },
    { title: '持有份额', dataIndex: 'shares', key: 'shares', render: (v: number) => v.toLocaleString() },
    { title: '成本价', dataIndex: 'cost_price', key: 'cost_price', render: (v: number) => v.toFixed(4) },
    { title: '当前净值', dataIndex: 'current_nav', key: 'current_nav', render: (v: number) => v.toFixed(4) },
    {
      title: '市值',
      dataIndex: 'market_value',
      key: 'market_value',
      render: (v: number) => `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`,
    },
    {
      title: '盈亏',
      dataIndex: 'profit_loss',
      key: 'profit_loss',
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#cf1322' : '#3f8600' }}>
          {v >= 0 ? '+' : ''}¥{v.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
        </span>
      ),
    },
    {
      title: '收益率',
      dataIndex: 'profit_rate',
      key: 'profit_rate',
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#cf1322' : '#3f8600' }}>
          {v >= 0 ? '+' : ''}{(v * 100).toFixed(2)}%
        </span>
      ),
    },
  ]

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <Card
        title={customer.name}
        extra={
          editing ? (
            <Button icon={<SaveOutlined />} type="primary" onClick={handleSave}>保存</Button>
          ) : (
            <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑</Button>
          )
        }
      >
        {editing ? (
          <Form form={form} layout="vertical">
            <Form.Item name="name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="phone" label="电话"><Input /></Form.Item>
            <Form.Item name="email" label="邮箱"><Input /></Form.Item>
            <Form.Item name="risk_preference" label="风险偏好" rules={[{ required: true }]}><Select options={riskOptions} /></Form.Item>
            <Form.Item name="notes" label="备注"><Input.TextArea rows={2} /></Form.Item>
          </Form>
        ) : (
          <Descriptions column={2}>
            <Descriptions.Item label="联系电话">{customer.phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="邮箱">{customer.email || '-'}</Descriptions.Item>
            <Descriptions.Item label="风险偏好">
              <Tag color={riskColors[customer.risk_preference]}>{riskLabels[customer.risk_preference]}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="总资产">
              ¥{customer.total_assets.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </Descriptions.Item>
            <Descriptions.Item label="备注">{customer.notes || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card title="持仓明细" style={{ marginTop: 16 }}
        extra={
          <span>
            总市值: ¥{totalMarketValue.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} |
            总盈亏: <span style={{ color: totalProfitLoss >= 0 ? '#cf1322' : '#3f8600' }}>
              {totalProfitLoss >= 0 ? '+' : ''}¥{totalProfitLoss.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </span>
          </span>
        }
      >
        {holdings.length > 0 ? (
          <Table columns={holdingColumns} dataSource={holdings} rowKey="id" pagination={false} />
        ) : (
          <Empty description="暂无持仓" />
        )}
      </Card>

      <Card
        title="跟进记录"
        style={{ marginTop: 16 }}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setFollowUpModalOpen(true)}>新增跟进</Button>}
      >
        {followUps.length > 0 ? (
          <Timeline
            items={followUps.map((fu) => ({
              dot: methodIcons[fu.contact_method],
              children: (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>
                      <Tag>{methodLabels[fu.contact_method] || fu.contact_method}</Tag>
                      <span style={{ color: '#999', fontSize: 12 }}>{dayjs(fu.follow_date).format('YYYY-MM-DD HH:mm')}</span>
                    </span>
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteFollowUp(fu.id)} />
                  </div>
                  <p style={{ margin: '4px 0 0' }}>{fu.content}</p>
                </div>
              ),
            }))}
          />
        ) : (
          <Empty description="暂无跟进记录" />
        )}
      </Card>

      <Modal
        title="新增跟进记录"
        open={followUpModalOpen}
        onOk={handleAddFollowUp}
        onCancel={() => { setFollowUpModalOpen(false); followUpForm.resetFields() }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={followUpForm} layout="vertical">
          <Form.Item name="contact_method" label="沟通方式" rules={[{ required: true, message: '请选择沟通方式' }]}>
            <Select options={methodOptions} />
          </Form.Item>
          <Form.Item name="follow_date" label="跟进时间">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="content" label="跟进内容" rules={[{ required: true, message: '请输入跟进内容' }]}>
            <Input.TextArea rows={4} placeholder="如：电话沟通，讨论了XX产品认购意向" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
