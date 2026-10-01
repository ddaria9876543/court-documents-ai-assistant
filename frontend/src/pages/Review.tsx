import { Card, List, Tag, Select, DatePicker, Input } from 'antd'
import { useNavigate } from 'react-router-dom'
import { mockDocuments } from '../mocks/documents'
import { useState } from 'react'
import dayjs from 'dayjs'

export default function Review() {
  const navigate = useNavigate()
  const [typeFilter, setTypeFilter] = useState<string>()
  const [dateFilter, setDateFilter] = useState<string>()
  const [reasonFilter, setReasonFilter] = useState('')

  const docs = mockDocuments
    .filter((d) => d.status === 'needs_review')
    .filter((d) => !typeFilter || d.documentType === typeFilter)
    .filter((d) => !dateFilter || d.createdAt.startsWith(dateFilter))
    .filter((d) =>
      !reasonFilter ||
      (d.reviewReason || '').toLowerCase().includes(reasonFilter.toLowerCase())
    )

  const types = Array.from(new Set(mockDocuments.map((d) => d.documentType)))

  return (
    <div>
      <h1>Документы на проверке</h1>
      <Card
        title="Требуют проверки"
        extra={
          <div style={{ display: 'flex', gap: 8 }}>
            <Select
              allowClear
              placeholder="Тип"
              style={{ width: 200 }}
              onChange={setTypeFilter}
              options={types.map((t) => ({ value: t, label: t }))}
            />
            <DatePicker
              placeholder="Дата"
              onChange={(date) =>
                setDateFilter(date ? dayjs(date).format('YYYY-MM-DD') : undefined)
              }
              style={{ width: 160 }}
            />
            <Input.Search
              placeholder="Причина"
              allowClear
              style={{ width: 200 }}
              onSearch={setReasonFilter}
              onChange={(e) => !e.target.value && setReasonFilter('')}
            />
          </div>
        }
      >
        <List
          dataSource={docs}
          renderItem={(d) => (
            <List.Item
              onClick={() => navigate(`/documents/${d.id}`)}
              style={{ cursor: 'pointer' }}
            >
              <List.Item.Meta
                title={
                  <>
                    {d.documentType} <Tag>{d.caseNumber || d.enforcementNumber}</Tag>
                  </>
                }
                description={
                  <>
                    <div>Дата: {new Date(d.createdAt).toLocaleString('ru-RU')}</div>
                    <div style={{ color: '#faad14' }}>Причина: {d.reviewReason}</div>
                    <div>{d.summary}</div>
                  </>
                }
              />
              <Tag color="orange">На проверке</Tag>
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}