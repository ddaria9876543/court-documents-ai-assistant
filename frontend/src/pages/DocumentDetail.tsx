import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'

import { CheckCircleOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

const { Title, Text } = Typography

const BACKEND_URL = 'http://127.0.0.1:8000'

interface DocumentData {
  id: number
  filename: string
  documentType?: string | null
  caseNumber?: string | null
  enforcementNumber?: string | null
  status: string
  createdAt: string
  summary?: string | null

  needsReview?: boolean
  reviewReason?: string | null

  requiresLegalAction?: boolean
  legalActionReason?: string | null
  evidenceFragment?: string | null

  dataVerified?: boolean
  debtor?: string | null
  amount?: number | null
  fileFormat?: string | null
}

interface EditFormValues {
  documentType?: string | null
  caseNumber?: string | null
  enforcementNumber?: string | null
  debtor?: string | null
  amount?: number | null
}

const statusConfig: Record<
  string,
  { label: string; color: string }
> = {
  processed: {
    label: 'Обработан',
    color: 'green',
  },
  needs_review: {
    label: 'На проверке',
    color: 'orange',
  },
  error: {
    label: 'Ошибка',
    color: 'red',
  },
  sent: {
    label: 'Отправлен',
    color: 'blue',
  },
  processing: {
    label: 'В обработке',
    color: 'default',
  },
  new: {
    label: 'Новый',
    color: 'default',
  },
}

const formatAmount = (
  value?: number | null
) => {
  if (
    value === undefined ||
    value === null
  ) {
    return '—'
  }

  return (
    new Intl.NumberFormat('ru-RU').format(value) +
    ' руб.'
  )
}

export default function DocumentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [form] =
    Form.useForm<EditFormValues>()

  const [doc, setDoc] =
    useState<DocumentData | null>(null)

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [editing, setEditing] =
    useState(false)

  const [saving, setSaving] =
    useState(false)

  const [
    actionLoading,
    setActionLoading,
  ] = useState(false)

  useEffect(() => {
    if (!id) {
      setError('Не указан ID документа')
      setLoading(false)
      return
    }

    const loadDocument = async () => {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(
          `${BACKEND_URL}/documents/${id}`
        )

        if (!response.ok) {
          throw new Error(
            `Ошибка загрузки: ${response.status}`
          )
        }

        const data: DocumentData =
          await response.json()

        setDoc(data)
      } catch (err) {
        console.error(err)

        setError(
          'Не удалось загрузить документ'
        )
      } finally {
        setLoading(false)
      }
    }

    loadDocument()
  }, [id])

  const startEditing = () => {
    if (!doc) return

    form.setFieldsValue({
      documentType:
        doc.documentType ?? undefined,
      caseNumber:
        doc.caseNumber ?? undefined,
      enforcementNumber:
        doc.enforcementNumber ?? undefined,
      debtor:
        doc.debtor ?? undefined,
      amount:
        doc.amount ?? undefined,
    })

    setEditing(true)
  }

  const cancelEditing = () => {
    setEditing(false)
    form.resetFields()
  }

  const saveChanges = async (
    values: EditFormValues
  ) => {
    if (!doc) return

    try {
      setSaving(true)

      const response = await fetch(
        `${BACKEND_URL}/documents/${doc.id}/data`,
        {
          method: 'PUT',
          headers: {
            'Content-Type':
              'application/json',
          },
          body: JSON.stringify({
            documentType:
              values.documentType || null,
            caseNumber:
              values.caseNumber || null,
            enforcementNumber:
              values.enforcementNumber ||
              null,
            debtor:
              values.debtor || null,
            amount:
              values.amount ?? null,
          }),
        }
      )

      if (!response.ok) {
        throw new Error(
          `Ошибка сохранения: ${response.status}`
        )
      }

      const updatedDocument: DocumentData =
        await response.json()

      setDoc(updatedDocument)
      setEditing(false)
      form.resetFields()

      message.success(
        'Исправления сохранены. Данные считаются проверенными.'
      )
    } catch (err) {
      console.error(err)

      message.error(
        'Не удалось сохранить исправления'
      )
    } finally {
      setSaving(false)
    }
  }

  const confirmData = async () => {
    if (!doc) return

    try {
      setActionLoading(true)

      const response = await fetch(
        `${BACKEND_URL}/documents/${doc.id}/verify`,
        {
          method: 'PUT',
        }
      )

      if (!response.ok) {
        throw new Error(
          `Ошибка подтверждения: ${response.status}`
        )
      }

      const updatedDocument: DocumentData =
        await response.json()

      setDoc(updatedDocument)

      message.success(
        'Извлечённые данные подтверждены'
      )
    } catch (err) {
      console.error(err)

      message.error(
        'Не удалось подтвердить данные'
      )
    } finally {
      setActionLoading(false)
    }
  }

  const updateStatus = async (
    status: 'processed' | 'sent',
    successMessage: string
  ) => {
    if (!doc) return

    try {
      setActionLoading(true)

      const response = await fetch(
        `${BACKEND_URL}/documents/${doc.id}/status`,
        {
          method: 'PUT',
          headers: {
            'Content-Type':
              'application/json',
          },
          body: JSON.stringify({
            status,
          }),
        }
      )

      if (!response.ok) {
        throw new Error(
          `Ошибка изменения статуса: ${response.status}`
        )
      }

      const updatedDocument: DocumentData =
        await response.json()

      setDoc(updatedDocument)

      message.success(successMessage)
    } catch (err) {
      console.error(err)

      message.error(
        'Не удалось изменить статус документа'
      )
    } finally {
      setActionLoading(false)
    }
  }

  const markNoSendingRequired =
    async () => {
      await updateStatus(
        'processed',
        'Документ обработан и не требует отправки'
      )
    }

  const sendToResponsible = async () => {
    await updateStatus(
      'sent',
      'Письмо ответственному сформировано (демо)'
    )
  }

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          padding: 80,
        }}
      >
        <Spin size="large" />
      </div>
    )
  }

  if (error || !doc) {
    return (
      <Alert
        type="error"
        showIcon
        message="Ошибка"
        description={
          error || 'Документ не найден'
        }
      />
    )
  }

  const cfg =
    statusConfig[doc.status] || {
      label: doc.status,
      color: 'default',
    }

  const fileUrl =
    `${BACKEND_URL}/documents/${doc.id}/file`

  const fileFormat =
    doc.fileFormat?.toLowerCase()

  return (
    <div>
      <Row gutter={16}>
        <Col span={12}>
          <Card title="Оригинал документа">
            {fileFormat === 'pdf' ? (
              <iframe
                src={fileUrl}
                title={doc.filename}
                style={{
                  width: '100%',
                  height: 650,
                  border:
                    '1px solid #d9d9d9',
                  borderRadius: 8,
                  background: '#fafafa',
                }}
              />
            ) : fileFormat === 'xml' ? (
              <iframe
                src={fileUrl}
                title={doc.filename}
                style={{
                  width: '100%',
                  height: 650,
                  border:
                    '1px solid #d9d9d9',
                  borderRadius: 8,
                  background: '#fff',
                }}
              />
            ) : (
              <div
                style={{
                  height: 500,
                  background: '#fafafa',
                  border:
                    '1px dashed #d9d9d9',
                  borderRadius: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                }}
              >
                <Text type="secondary">
                  Предпросмотр этого формата
                  недоступен
                </Text>

                <Button
                  onClick={() =>
                    window.open(
                      fileUrl,
                      '_blank'
                    )
                  }
                >
                  Открыть оригинал
                </Button>
              </div>
            )}
          </Card>
        </Col>

        <Col span={12}>
          <Card title="Извлечённые данные">
            {editing ? (
              <Form
                form={form}
                layout="vertical"
                onFinish={saveChanges}
              >
                <Form.Item
                  label="Тип документа"
                  name="documentType"
                >
                  <Select
                    allowClear
                    options={[
                      {
                        value:
                          'судебный приказ',
                        label:
                          'Судебный приказ',
                      },
                      {
                        value:
                          'исполнительный лист',
                        label:
                          'Исполнительный лист',
                      },
                      {
                        value:
                          'постановление ФССП',
                        label:
                          'Постановление ФССП',
                      },
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  label="Номер дела"
                  name="caseNumber"
                >
                  <Input />
                </Form.Item>

                <Form.Item
                  label="Номер ИП"
                  name="enforcementNumber"
                >
                  <Input />
                </Form.Item>

                <Form.Item
                  label="Должник"
                  name="debtor"
                >
                  <Input />
                </Form.Item>

                <Form.Item
                  label="Сумма"
                  name="amount"
                >
                  <InputNumber
                    min={0}
                    precision={2}
                    style={{
                      width: '100%',
                    }}
                    addonAfter="руб."
                  />
                </Form.Item>

                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={saving}
                  >
                    Сохранить
                  </Button>

                  <Button
                    onClick={cancelEditing}
                    disabled={saving}
                  >
                    Отмена
                  </Button>
                </Space>
              </Form>
            ) : (
              <>
                <Descriptions
                  column={1}
                  bordered
                  size="small"
                >
                  <Descriptions.Item label="Тип документа">
                    {doc.documentType || '—'}
                  </Descriptions.Item>

                  <Descriptions.Item label="Номер дела">
                    {doc.caseNumber || '—'}
                  </Descriptions.Item>

                  <Descriptions.Item label="Номер ИП">
                    {doc.enforcementNumber ||
                      '—'}
                  </Descriptions.Item>

                  <Descriptions.Item label="Должник">
                    {doc.debtor || '—'}
                  </Descriptions.Item>

                  <Descriptions.Item label="Сумма">
                    {formatAmount(doc.amount)}
                  </Descriptions.Item>

                  <Descriptions.Item label="Файл">
                    {doc.filename}
                  </Descriptions.Item>

                  <Descriptions.Item label="Дата">
                    {new Date(
                      doc.createdAt
                    ).toLocaleString(
                      'ru-RU'
                    )}
                  </Descriptions.Item>

                  <Descriptions.Item label="Статус">
                    <Tag color={cfg.color}>
                      {cfg.label}
                    </Tag>
                  </Descriptions.Item>

                  {doc.reviewReason && (
                    <Descriptions.Item label="Причина проверки">
                      {doc.reviewReason}
                    </Descriptions.Item>
                  )}

                  <Descriptions.Item label="Работа юриста">
                    {doc.requiresLegalAction ? (
                      <Tag color="orange">
                        Требуется
                      </Tag>
                    ) : (
                      <Tag color="green">
                        Не требуется
                      </Tag>
                    )}
                  </Descriptions.Item>
                </Descriptions>

                <Title
                  level={5}
                  style={{
                    marginTop: 16,
                  }}
                >
                  Кратко о документе
                </Title>

                <Text>
                  {doc.summary ||
                    'Краткое описание отсутствует'}
                </Text>

                {doc.requiresLegalAction && (
                  <Alert
                    type="warning"
                    showIcon
                    message="Требуется действие юриста"
                    description={
                      <div>
                        <div>
                          <strong>
                            Причина:
                          </strong>{' '}
                          {doc.legalActionReason ||
                            'Документ требует дополнительной юридической обработки.'}
                        </div>

                        {doc.evidenceFragment && (
                          <div
                            style={{
                              marginTop: 8,
                            }}
                          >
                            <strong>
                              Подтверждающий фрагмент:
                            </strong>

                            <div
                              style={{
                                marginTop: 4,
                              }}
                            >
                              {doc.evidenceFragment}
                            </div>
                          </div>
                        )}

                        <div
                          style={{
                            marginTop: 12,
                          }}
                        >
                          Решение о дальнейших
                          юридических действиях
                          принимает сотрудник.
                        </div>
                      </div>
                    }
                    style={{
                      marginTop: 20,
                    }}
                  />
                )}

                {doc.status ===
                  'needs_review' && (
                  <div
                    style={{
                      marginTop: 24,
                    }}
                  >
                    {!doc.dataVerified ? (
                      <>
                        <Text
                          strong
                          style={{
                            display: 'block',
                            marginBottom: 4,
                          }}
                        >
                          Проверка извлечённых данных
                        </Text>

                        <Text
                          type="secondary"
                          style={{
                            display: 'block',
                            marginBottom: 12,
                          }}
                        >
                          Сравните данные с
                          оригиналом документа.
                        </Text>

                        <Space wrap>
                          <Button
                            type="primary"
                            loading={
                              actionLoading
                            }
                            onClick={
                              confirmData
                            }
                          >
                            Подтвердить данные
                          </Button>

                          <Button
                            onClick={
                              startEditing
                            }
                            disabled={
                              actionLoading
                            }
                          >
                            Исправить данные
                          </Button>
                        </Space>
                      </>
                    ) : (
                      <>
                        <Alert
                          type="success"
                          showIcon
                          icon={
                            <CheckCircleOutlined />
                          }
                          message="Извлечённые данные проверены"
                          style={{
                            marginBottom: 16,
                          }}
                        />

                        <Text
                          strong
                          style={{
                            display: 'block',
                            marginBottom: 4,
                          }}
                        >
                          Решение по документу
                        </Text>

                        <Text
                          type="secondary"
                          style={{
                            display: 'block',
                            marginBottom: 12,
                          }}
                        >
                          Определите, требуется
                          ли передавать документ
                          ответственному.
                        </Text>

                        <Space wrap>
                          <Button
                            type="primary"
                            onClick={
                              markNoSendingRequired
                            }
                            loading={
                              actionLoading
                            }
                          >
                            Не требует отправки
                          </Button>

                          <Button
                            onClick={
                              sendToResponsible
                            }
                            loading={
                              actionLoading
                            }
                          >
                            Сформировать письмо ответственному
                          </Button>

                          <Button
                            onClick={
                              startEditing
                            }
                            disabled={
                              actionLoading
                            }
                          >
                            Изменить данные
                          </Button>
                        </Space>
                      </>
                    )}
                  </div>
                )}

                {doc.status ===
                  'processed' &&
                  !doc.requiresLegalAction && (
                    <Alert
                      type="success"
                      showIcon
                      message="Документ обработан"
                      description="Дополнительных действий юриста не требуется."
                      style={{
                        marginTop: 20,
                      }}
                    />
                  )}

                {doc.status ===
                  'processed' &&
                  doc.requiresLegalAction && (
                    <div
                      style={{
                        marginTop: 20,
                      }}
                    >
                      <Space wrap>
                        <Button
                          type="primary"
                          onClick={
                            sendToResponsible
                          }
                          loading={
                            actionLoading
                          }
                        >
                          Сформировать письмо ответственному
                        </Button>

                        <Button
                          onClick={
                            markNoSendingRequired
                          }
                          loading={
                            actionLoading
                          }
                        >
                          Не требует отправки
                        </Button>

                        <Button
                          onClick={
                            startEditing
                          }
                          disabled={
                            actionLoading
                          }
                        >
                          Изменить данные
                        </Button>
                      </Space>
                    </div>
                  )}

                {doc.status === 'sent' && (
                  <Alert
                    type="info"
                    showIcon
                    message="Письмо ответственному сформировано"
                    description="Демо-режим: в MVP фактическая отправка e-mail не выполняется. Система имитирует отправку сменой статуса документа."
                    style={{
                      marginTop: 20,
                    }}
                  />
                )}
              </>
            )}
          </Card>

          <Button
            style={{
              marginTop: 16,
            }}
            onClick={() =>
              navigate(-1)
            }
          >
            ← Назад
          </Button>
        </Col>
      </Row>
    </div>
  )
}