import { Table, Input, Select, Space, Tag, DatePicker } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { mockDocuments } from '../mocks/documents'
import dayjs from 'dayjs'

const statusConfig: Record<string, { label: string; color: string }> = {
  processed: { label: 'Обработан', color: 'green' },
  needs_review: { label: 'На проверке', color: 'orange' },
  error: { label: 'Ошибка', color: 'red' },
  sent: { label: 'Отправлен', color: 'blue' },
  processing: { label: 'В обработке', color: 'default' },
  new: { label: 'Новый', color: 'default' },
}

export default function Documents() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [typeFilter, setTypeFilter] = useState<string | undefined>()
  const [formatFilter, setFormatFilter] = useState<string | undefined>()
  const [dateFilter, setDateFilter] = useState<string | undefined>()

  const filtered = mockDocuments.filter((d) => {
    const matchSearch =
      d.filename.toLowerCase().includes(search.toLowerCase()) ||
      (d.caseNumber || '').toLowerCase().includes(search.toLowerCase()) ||
      (d.enforcementNumber || '').toLowerCase().includes(search.toLowerCase())

    const matchStatus = !statusFilter || d.status === statusFilter
    const matchType = !typeFilter || d.documentType === typeFilter
    const matchFormat = !formatFilter || d.fileFormat === formatFilter
    const matchDate = !dateFilter || d.createdAt.startsWith(dateFilter)

    return matchSearch && matchStatus && matchType && matchFormat && matchDate
  })

  const types = Array.from(new Set(mockDocuments.map((d) => d.documentType)))

  const columns = [
    {
      title: 'Дата',
      dataIndex: 'createdAt',
      width: 160,
      sorter: (a: any, b: any) =>
        new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
      defaultSortOrder: 'descend' as const,
      render: (v: string) => new Date(v).toLocaleString('ru-RU'),
    },
    {
      title: 'Файл',
      dataIndex: 'filename',
    },
    {
      title: 'Тип',
      dataIndex: 'documentType',
      sorter: (a: any, b: any) =>
        a.documentType.localeCompare(b.documentType),
    },
    {
      title: '№ дела / ИП',
      key: 'num',
      render: (_: any, r: any) =>
        r.caseNumber || r.enforcementNumber || '—',
    },
    {
      title: 'Результат',
      dataIndex: 'summary',
      ellipsis: true,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      sorter: (a: any, b: any) =>
        a.status.localeCompare(b.status),
      render: (s: string) => {
        const cfg = statusConfig[s]

        return (
          <Tag color={cfg.color}>
            {cfg.label}
          </Tag>
        )
      },
    },
  ]

  return (
    <div>
      <h1>Документы</h1>

      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Поиск по файлу, делу, ИП"
          allowClear
          style={{ width: 300 }}
          onSearch={setSearch}
          onChange={(e) => !e.target.value && setSearch('')}
        />

        <Select
          allowClear
          placeholder="Статус"
          style={{ width: 180 }}
          onChange={setStatusFilter}
          options={[
            { value: 'processed', label: 'Обработан' },
            { value: 'needs_review', label: 'На проверке' },
            { value: 'error', label: 'Ошибка' },
            { value: 'sent', label: 'Отправлен' },
            { value: 'processing', label: 'В обработке' },
            { value: 'new', label: 'Новый' },
          ]}
        />

        <Select
          allowClear
          placeholder="Тип документа"
          style={{ width: 200 }}
          onChange={setTypeFilter}
          options={types.map((t) => ({
            value: t,
            label: t,
          }))}
        />

        <Select
          allowClear
          placeholder="Формат"
          style={{ width: 120 }}
          onChange={setFormatFilter}
          options={[
            { value: 'pdf', label: 'PDF' },
            { value: 'xml', label: 'XML' },
          ]}
        />

        <DatePicker
          placeholder="Дата"
          onChange={(date) =>
            setDateFilter(
              date
                ? dayjs(date).format('YYYY-MM-DD')
                : undefined
            )
          }
          style={{ width: 160 }}
        />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={filtered}
        onRow={(r) => ({
          onClick: () => navigate(`/documents/${r.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  )
}