import { useEffect, useState, useRef } from 'react'
import { Row, Col, Card, Radio, Spin } from 'antd'
import * as echarts from 'echarts'
import StatCard from '../../components/StatCard'
import { getDashboardSummary, getSalesTrend, getProductDistribution } from '../../services/dashboardService'
import type { DashboardSummary, SalesTrendItem, ProductDistributionItem } from '../../types'

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [trend, setTrend] = useState<SalesTrendItem[]>([])
  const [distribution, setDistribution] = useState<ProductDistributionItem[]>([])
  const [period, setPeriod] = useState('day')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true)
      try {
        const [s, t, d] = await Promise.all([
          getDashboardSummary(),
          getSalesTrend(period),
          getProductDistribution(),
        ])
        setSummary(s)
        setTrend(t.data)
        setDistribution(d.data)
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [period])

  const trendRef = useRef<HTMLDivElement>(null)
  const pieRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!trendRef.current || trend.length === 0) return
    const chart = echarts.init(trendRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: trend.map((i) => i.date), axisLabel: { rotate: 30 } },
      yAxis: { type: 'value' },
      series: [{ name: '销售额', type: 'line', data: trend.map((i) => i.amount), smooth: true, areaStyle: { opacity: 0.15 } }],
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    })
    const h = () => chart.resize()
    window.addEventListener('resize', h)
    return () => { chart.dispose(); window.removeEventListener('resize', h) }
  }, [trend])

  useEffect(() => {
    if (!pieRef.current || distribution.length === 0) return
    const chart = echarts.init(pieRef.current)
    chart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: distribution.map((d) => ({ name: d.label, value: d.amount })),
        label: { formatter: '{b}: {d}%' },
      }],
    })
    const h = () => chart.resize()
    window.addEventListener('resize', h)
    return () => { chart.dispose(); window.removeEventListener('resize', h) }
  }, [distribution])

  if (loading || !summary) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}><StatCard title="销售总额" value={summary.total_sales} type="sales" /></Col>
        <Col span={6}><StatCard title="客户总数" value={summary.total_customers} type="customers" /></Col>
        <Col span={6}><StatCard title="持仓总规模" value={summary.total_aum} type="aum" /></Col>
        <Col span={6}><StatCard title="本月销售" value={summary.monthly_sales} type="monthly" /></Col>
      </Row>

      <Row gutter={16}>
        <Col span={14}>
          <Card
            title="销售趋势"
            extra={
              <Radio.Group value={period} onChange={(e) => setPeriod(e.target.value)} size="small">
                <Radio.Button value="day">日</Radio.Button>
                <Radio.Button value="week">周</Radio.Button>
                <Radio.Button value="month">月</Radio.Button>
              </Radio.Group>
            }
          >
            <div ref={trendRef} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="产品销售占比">
            <div ref={pieRef} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
