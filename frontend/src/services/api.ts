import axios from 'axios'
import { message } from 'antd'

function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

function getUserId(): string {
  let id = localStorage.getItem('fund_sales_user_id')
  if (!id) {
    id = generateUUID()
    localStorage.setItem('fund_sales_user_id', id)
  }
  return id
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  config.headers['X-User-Id'] = getUserId()
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.error?.message || '请求失败，请稍后重试'
    message.error(msg)
    return Promise.reject(error)
  }
)

export { getUserId }
export default api
