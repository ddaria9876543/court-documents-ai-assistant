import { Card, Statistic, Row, Col, Table, Tag, Alert, Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { mockDocuments } from '../mocks/documents'
import { useState } from 'react'
import UploadModal from '../components/UploadModal'

const statusConfig: Record<string, { label: string; color: string }> = {
  processed: { label: 'Обработан', color: 'green' },
  needs_review: { label: 'На проверке', color: 'orange' },
  error: { label: 'Ошибка', color: 'red' },
  sent: { label: 'Отправлен', color: 'blue' },
  processing: { label: 'В обработке', color: 'default' },
  new: { label: 'Новый', color: 'default' },
}

export default function Home() {
  const navigate = useNavigate()
  const [uploadOpen, setUploadOpen] = useState(false)

  const today = mockDocuments.filter((d) => d.createdAt.startsWith('2026-09-30'))
  const processed = mockDocuments.filter((d) => d.status === 'processed')
  const sent = mockDocuments.filter((d) => d.status === 'sent')
  const needsReview = mockDocuments.filter((d) => d.status === 'needs_review')
  const errors = mockDocuments.filter((d) => d.status === 'error')

  const columns = [
    {
      title: 'Дата',
      dataIndex: 'createdAt',
      width: 160,
      render: (v: string) => new Date(v).toLocaleString('ru-RU'),
    },
    { title: 'Файл', dataIndex: 'filename' },
    { title: 'Тип', dataIndex: 'documentType' },
    {
      title: '№ дела / ИП',
      key: 'num',
      render: (_: any, r: any) => r.caseNumber || r.enforcementNumber || '—',
    },
    { title: 'Результат', dataIndex: 'summary', ellipsis: true },
    {
      title: 'Статус',
      dataIndex: 'status',
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
      {/* Индикатор фоновой обработки */}
      <Alert
        message="Фоновая обработка активна"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h1 style={{ margin: 0 }}>Главная страница</h1>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setUploadOpen(true)}
        >
          Загрузить документы
        </Button>
      </div>

      {errors.length > 0 && (
        <Alert
          message={`Ошибки обработки: ${errors.length}`}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="Получено сегодня" value={today.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Обработано автоматически" value={processed.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Отправлено ответственным" value={sent.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="На проверке"
              value={needsReview.length}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {needsReview.length > 0 && (
        <Card title="Требует вашего внимания" style={{ marginBottom: 16 }}>
          {needsReview.map((doc) => (
            <div
              key={doc.id}
              onClick={() => navigate(`/documents/${doc.id}`)}
              style={{
                padding: '12px 0',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{doc.documentType}</div>
                <div style={{ color: '#666', fontSize: 13 }}>
                  Дело № {doc.caseNumber || doc.enforcementNumber}
                </div>
                <div style={{ color: '#faad14', fontSize: 13 }}>
                  Причина: {doc.reviewReason}
                </div>
                <div style={{ color: '#999', fontSize: 13 }}>{doc.summary}</div>
              </div>
              <Button type="link">Проверить</Button>
            </div>
          ))}
        </Card>
      )}

      <Card title="Последние документы">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={mockDocuments}
          pagination={false}
          onRow={(r) => ({
            onClick: () => navigate(`/documents/${r.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </div>
  )
}