import { Card, Statistic, Row, Col, Table, Tag, Alert, Button, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import UploadModal from '../components/UploadModal'
import type { Document } from '../types/document'

const BACKEND_URL = 'http://127.0.0.1:8000'

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

  const [documents, setDocuments] = useState<Document[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadDocuments = async () => {
    setLoading(true)

    try {
      const response = await fetch(`${BACKEND_URL}/documents`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data: Document[] = await response.json()
      setDocuments(data)
    } catch (error) {
      console.error('Ошибка загрузки документов:', error)
      message.error('Не удалось получить документы с backend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [])

  const todayString = new Date().toISOString().slice(0, 10)

  const today = documents.filter((d) =>
    d.createdAt.startsWith(todayString)
  )

  const processed = documents.filter(
    (d) => d.status === 'processed'
  )

  const sent = documents.filter(
    (d) => d.status === 'sent'
  )

  const needsReview = documents.filter(
    (d) => d.status === 'needs_review'
  )

  const errors = documents.filter(
    (d) => d.status === 'error'
  )

  const columns = [
    {
      title: 'Дата',
      dataIndex: 'createdAt',
      width: 160,
      render: (v: string) =>
        new Date(v).toLocaleString('ru-RU'),
    },
    {
      title: 'Файл',
      dataIndex: 'filename',
    },
    {
      title: 'Тип',
      dataIndex: 'documentType',
    },
    {
      title: '№ дела / ИП',
      key: 'num',
      render: (_: unknown, r: Document) =>
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
      render: (status: string) => {
        const cfg =
          statusConfig[status] ?? {
            label: status,
            color: 'default',
          }

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
        <h1 style={{ margin: 0 }}>
          Главная страница
        </h1>

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

      <Row
        gutter={16}
        style={{ marginBottom: 24 }}
      >
        <Col span={6}>
          <Card>
            <Statistic
              title="Получено сегодня"
              value={today.length}
            />
          </Card>
        </Col>

        <Col span={6}>
          <Card>
            <Statistic
              title="Обработано автоматически"
              value={processed.length}
            />
          </Card>
        </Col>

        <Col span={6}>
          <Card>
            <Statistic
              title="Отправлено ответственным"
              value={sent.length}
            />
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
        <Card
          title="Требует вашего внимания"
          style={{ marginBottom: 16 }}
        >
          {needsReview.map((doc) => (
            <div
              key={doc.id}
              onClick={() =>
                navigate(`/documents/${doc.id}`)
              }
              style={{
                padding: '12px 0',
                borderBottom:
                  '1px solid #f0f0f0',
                cursor: 'pointer',
                display: 'flex',
                justifyContent:
                  'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div
                  style={{
                    fontWeight: 600,
                  }}
                >
                  {doc.documentType}
                </div>

                <div
                  style={{
                    color: '#666',
                    fontSize: 13,
                  }}
                >
                  Дело №{' '}
                  {doc.caseNumber ||
                    doc.enforcementNumber ||
                    '—'}
                </div>

                <div
                  style={{
                    color: '#faad14',
                    fontSize: 13,
                  }}
                >
                  Причина:{' '}
                  {doc.reviewReason ||
                    'Требуется проверка'}
                </div>

                <div
                  style={{
                    color: '#999',
                    fontSize: 13,
                  }}
                >
                  {doc.summary}
                </div>
              </div>

              <Button type="link">
                Проверить
              </Button>
            </div>
          ))}
        </Card>
      )}

      <Card title="Последние документы">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={documents}
          loading={loading}
          pagination={false}
          onRow={(record) => ({
            onClick: () =>
              navigate(
                `/documents/${record.id}`
              ),
            style: {
              cursor: 'pointer',
            },
          })}
        />
      </Card>

      <UploadModal
        open={uploadOpen}
        onClose={() => {
          setUploadOpen(false)

          // После закрытия окна перечитываем
          // документы из backend.
          setTimeout(() => {
            loadDocuments()
          }, 300)
        }}
      />
    </div>
  )
}