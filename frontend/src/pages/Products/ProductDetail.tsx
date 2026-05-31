import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Spin, Empty } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { getFundDetail, getNAVHistory } from '../../services/fundService'
import type { FundDetail as FundDetailType, NAVHistoryItem } from '../../types'

const riskColors: Record<string, string> = { low: 'green', medium: 'orange', high: 'red' }
const riskLabels: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const typeLabels: Record<string, string> = { stock: '股票型', bond: '债券型', mixed: '混合型', money: '货币型' }

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [fund, setFund] = useState<FundDetailType | null>(null)
  const [navHistory, setNavHistory] = useState<NAVHistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    const fetchData = async () => {
      setLoading(true)
      try {
        const [detail, history] = await Promise.all([
          getFundDetail(Number(id)),
          getNAVHistory(Number(id)),
        ])
        setFund(detail)
        setNavHistory(history.data)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current || navHistory.length === 0) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: navHistory.map((item) => item.date),
        axisLabel: { rotate: 45 },
      },
      yAxis: { type: 'value', scale: true },
      series: [{
        name: '净值',
        type: 'line',
        data: navHistory.map((item) => item.nav),
        smooth: true,
        areaStyle: { opacity: 0.1 },
      }],
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    })
    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)
    return () => { chart.dispose(); window.removeEventListener('resize', handleResize) }
  }, [navHistory])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!fund) return <Empty description="基金不存在" />

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/products')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <Card title={fund.name} extra={<Tag color={riskColors[fund.risk_level]}>{riskLabels[fund.risk_level]}</Tag>}>
        <Descriptions column={2}>
          <Descriptions.Item label="基金代码">{fund.code}</Descriptions.Item>
          <Descriptions.Item label="基金类型">{typeLabels[fund.type]}</Descriptions.Item>
          <Descriptions.Item label="最新净值">{fund.nav.toFixed(4)}</Descriptions.Item>
          <Descriptions.Item label="日涨跌幅">
            {fund.daily_change !== null ? `${(fund.daily_change * 100).toFixed(2)}%` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="基金经理">{fund.manager || '-'}</Descriptions.Item>
          <Descriptions.Item label="成立日期">{fund.established_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="管理费率">
            {fund.management_fee !== null ? `${(fund.management_fee * 100).toFixed(2)}%` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="状态">{fund.status === 'active' ? '在售' : '暂停'}</Descriptions.Item>
        </Descriptions>
        {fund.description && (
          <p style={{ marginTop: 16, color: '#666' }}>{fund.description}</p>
        )}
      </Card>

      <Card title="历史净值走势" style={{ marginTop: 16 }}>
        {navHistory.length > 0 ? (
          <div ref={chartRef} style={{ height: 350 }} />
        ) : (
          <Empty description="暂无净值数据" />
        )}
      </Card>
    </div>
  )
}
