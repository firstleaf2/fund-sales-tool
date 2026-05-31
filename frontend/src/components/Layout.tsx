import React from 'react'
import { Layout as AntLayout, Menu } from 'antd'
import {
  DashboardOutlined,
  ShopOutlined,
  TeamOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

const { Sider, Content } = AntLayout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '数据概览' },
  { key: '/products', icon: <ShopOutlined />, label: '产品货架' },
  { key: '/customers', icon: <TeamOutlined />, label: '客户管理' },
  { key: '/ai-assistant', icon: <RobotOutlined />, label: 'AI 助手' },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const selectedKey = menuItems.find(
    (item) => item.key !== '/' && location.pathname.startsWith(item.key)
  )?.key || '/'

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={200}>
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 16 }}>
          基金销售管理
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Content style={{ margin: 24 }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
