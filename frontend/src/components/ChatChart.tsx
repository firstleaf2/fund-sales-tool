import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

interface ChatChartProps {
  option: Record<string, unknown>
  height?: number
}

export default function ChatChart({ option, height = 320 }: ChatChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current) return
    const chart = echarts.init(chartRef.current)
    try {
      chart.setOption(option)
    } catch {
      chart.dispose()
      return
    }
    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)
    return () => {
      chart.dispose()
      window.removeEventListener('resize', handleResize)
    }
  }, [option])

  return (
    <div style={{ marginTop: 12, background: '#fff', borderRadius: 8, padding: 12, border: '1px solid #f0f0f0' }}>
      <div ref={chartRef} style={{ width: '100%', height }} />
    </div>
  )
}
