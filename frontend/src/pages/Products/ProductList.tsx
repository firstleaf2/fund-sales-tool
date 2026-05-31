import { useEffect, useState } from 'react'
import { Table, Input, Select, Tag, Space, Typography, Button, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { CopyOutlined } from '@ant-design/icons'
import { getFunds } from '../../services/fundService'
import type { Fund } from '../../types'

const { Search } = Input
const { Title } = Typography

const typeOptions = [
  { value: '', label: '全部类型' },
  { value: 'stock', label: '股票型' },
  { value: 'bond', label: '债券型' },
  { value: 'mixed', label: '混合型' },
  { value: 'money', label: '货币型' },
]

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'raising', label: '募集中' },
  { value: 'active', label: '运作中' },
  { value: 'liquidated', label: '已清盘' },
]

const typeLabels: Record<string, string> = {
  stock: '股票型',
  bond: '债券型',
  mixed: '混合型',
  money: '货币型',
}

const riskColors: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
}

const riskLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

export default function ProductList() {
  const [funds, setFunds] = useState<Fund[]>([])
  const [loading, setLoading] = useState(false)
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()

  const fetchFunds = async () => {
    setLoading(true)
    try {
      const res = await getFunds({ type: type || undefined, keyword: keyword || undefined, status: status || undefined })
      setFunds(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFunds()
  }, [type, status])

  const columns = [
    { title: '基金代码', dataIndex: 'code', key: 'code', width: 100 },
    {
      title: '基金名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Space>
          <span>{name}</span>
          <Button
            type="text"
            size="small"
            icon={<CopyOutlined />}
            onClick={(e) => {
              e.stopPropagation()
              navigator.clipboard.writeText(name)
              message.success('已复制')
            }}
          />
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (t: string) => typeLabels[t] || t,
    },
    {
      title: '最新净值',
      dataIndex: 'nav',
      key: 'nav',
      width: 100,
      render: (v: number) => v.toFixed(4),
    },
    {
      title: '日涨跌幅',
      dataIndex: 'daily_change',
      key: 'daily_change',
      width: 100,
      render: (v: number | null) => {
        if (v === null) return '-'
        const pct = (v * 100).toFixed(2)
        const color = v >= 0 ? '#cf1322' : '#3f8600'
        return <span style={{ color }}>{v >= 0 ? '+' : ''}{pct}%</span>
      },
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 90,
      render: (r: string) => <Tag color={riskColors[r]}>{riskLabels[r]}</Tag>,
    },
  ]

  return (
    <div>
      <Title level={4}>产品货架</Title>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={type}
          onChange={setType}
          options={typeOptions}
          style={{ width: 120 }}
        />
        <Select
          value={status}
          onChange={setStatus}
          options={statusOptions}
          style={{ width: 120 }}
        />
        <Search
          placeholder="搜索基金名称或代码"
          onSearch={(v) => { setKeyword(v); fetchFunds() }}
          onChange={(e) => setKeyword(e.target.value)}
          allowClear
          style={{ width: 250 }}
        />
      </Space>
      <Table
        columns={columns}
        dataSource={funds}
        rowKey="id"
        loading={loading}
        onRow={(record) => ({
          onClick: () => navigate(`/products/${record.id}`),
          style: { cursor: 'pointer' },
        })}
        pagination={{ pageSize: 10 }}
      />
    </div>
  )
}
