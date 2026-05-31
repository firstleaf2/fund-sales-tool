import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, Select, Typography, Tag, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getCustomers, createCustomer } from '../../services/customerService'
import type { Customer } from '../../types'

const { Title } = Typography

const riskOptions = [
  { value: 'conservative', label: '保守型' },
  { value: 'moderate', label: '稳健型' },
  { value: 'aggressive', label: '激进型' },
]

const riskLabels: Record<string, string> = {
  conservative: '保守型',
  moderate: '稳健型',
  aggressive: '激进型',
}

const riskColors: Record<string, string> = {
  conservative: 'green',
  moderate: 'blue',
  aggressive: 'red',
}

export default function CustomerList() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const navigate = useNavigate()

  const fetchCustomers = async () => {
    setLoading(true)
    try {
      const res = await getCustomers()
      setCustomers(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCustomers()
  }, [])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await createCustomer(values)
      message.success('客户创建成功')
      setModalOpen(false)
      form.resetFields()
      fetchCustomers()
    } catch {
      // validation error
    }
  }

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    {
      title: '风险偏好',
      dataIndex: 'risk_preference',
      key: 'risk_preference',
      render: (r: string) => <Tag color={riskColors[r]}>{riskLabels[r]}</Tag>,
    },
    {
      title: '总资产',
      dataIndex: 'total_assets',
      key: 'total_assets',
      render: (v: number) => `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`,
    },
    { title: '联系电话', dataIndex: 'phone', key: 'phone' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>客户管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新增客户
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={customers}
        rowKey="id"
        loading={loading}
        onRow={(record) => ({
          onClick: () => navigate(`/customers/${record.id}`),
          style: { cursor: 'pointer' },
        })}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="新增客户"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="phone" label="联系电话">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input />
          </Form.Item>
          <Form.Item name="risk_preference" label="风险偏好" rules={[{ required: true, message: '请选择风险偏好' }]}>
            <Select options={riskOptions} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
