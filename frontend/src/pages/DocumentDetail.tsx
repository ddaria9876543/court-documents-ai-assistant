import { Card, Descriptions, Tag, Button, Space, message, Row, Col, Typography } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { mockDocuments } from '../mocks/documents'

const { Title, Text } = Typography

const statusConfig: Record<string, { label: string; color: string }> = {
  processed: { label: 'Обработан', color: 'green' },
  needs_review: { label: 'На проверке', color: 'orange' },
  error: { label: 'Ошибка', color: 'red' },
  sent: { label: 'Отправлен', color: 'blue' },
  processing: { label: 'В обработке', color: 'default' },
  new: { label: 'Новый', color: 'default' },
}

const formatAmount = (n?: number) => {
  if (n === undefined) return '—'
  return new Intl.NumberFormat('ru-RU').format(n) + ' руб.'
}

export default function DocumentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const doc = mockDocuments.find((d) => d.id === Number(id))

  if (!doc) return <div>Документ не найден</div>

  const cfg = statusConfig[doc.status]

  return (
    <div>
      <Row gutter={16}>
        <Col span={12}>
          <Card title="Оригинал документа">
            <div
              style={{
                height: 500,
                background: '#fafafa',
                border: '1px dashed #d9d9d9',
                borderRadius: 16,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text type="secondary">PDF preview будет здесь</Text>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Тип документа">{doc.documentType}</Descriptions.Item>
              <Descriptions.Item label="Номер дела">{doc.caseNumber || '—'}</Descriptions.Item>
              <Descriptions.Item label="Номер ИП">{doc.enforcementNumber || '—'}</Descriptions.Item>
              <Descriptions.Item label="Должник">{doc.debtor || '—'}</Descriptions.Item>
              <Descriptions.Item label="Сумма">{formatAmount(doc.amount)}</Descriptions.Item>
              <Descriptions.Item label="Файл">{doc.filename}</Descriptions.Item>
              <Descriptions.Item label="Дата">
                {new Date(doc.createdAt).toLocaleString('ru-RU')}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                <Tag color={cfg.color}>{cfg.label}</Tag>
              </Descriptions.Item>
              {doc.reviewReason && (
                <Descriptions.Item label="Причина проверки">
                  {doc.reviewReason}
                </Descriptions.Item>
              )}
            </Descriptions>

            <Title level={5} style={{ marginTop: 16 }}>
              Кратко о документе
            </Title>
            <Text>{doc.summary}</Text>

            {doc.status === 'needs_review' && (
              <Space style={{ marginTop: 16 }} wrap>
                <Button type="primary" onClick={() => message.success('Подтверждено')}>
                  Подтвердить
                </Button>
                <Button onClick={() => message.info('Открыт режим исправления')}>
                  Исправить
                </Button>
                <Button onClick={() => message.info('Не требует отправки')}>
                  Не требует отправки
                </Button>
                <Button onClick={() => message.success('Отправлено ответственному')}>
                  Отправить ответственному
                </Button>
              </Space>
            )}

            <Button style={{ marginTop: 16 }} onClick={() => navigate(-1)}>
              Назад
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  )
}