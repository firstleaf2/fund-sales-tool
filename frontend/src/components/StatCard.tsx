import { Card, Statistic } from 'antd'
import {
  DollarOutlined,
  TeamOutlined,
  FundOutlined,
  RiseOutlined,
} from '@ant-design/icons'

interface StatCardProps {
  title: string
  value: number
  prefix?: string
  type: 'sales' | 'customers' | 'aum' | 'monthly'
}

const icons = {
  sales: <DollarOutlined />,
  customers: <TeamOutlined />,
  aum: <FundOutlined />,
  monthly: <RiseOutlined />,
}

export default function StatCard({ title, value, prefix = '¥', type }: StatCardProps) {
  const isCount = type === 'customers'

  return (
    <Card>
      <Statistic
        title={title}
        value={value}
        prefix={isCount ? undefined : prefix}
        precision={isCount ? 0 : 2}
        valueStyle={{ color: '#1677ff' }}
        suffix={isCount ? '人' : undefined}
      />
      <div style={{ marginTop: 8, color: '#999', fontSize: 20 }}>
        {icons[type]}
      </div>
    </Card>
  )
}
