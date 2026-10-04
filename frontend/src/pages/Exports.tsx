import {
  Card,
  Form,
  DatePicker,
  Select,
  Button,
  message,
  Space,
  Alert,
  Statistic,
  Table,
  Tag,
} from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useEffect, useMemo, useState } from 'react'
import dayjs, { Dayjs } from 'dayjs'

const BACKEND_URL = 'http://127.0.0.1:8000'

type ExportFormat = 'XLSX' | 'CSV'

type DocumentItem = {
  id: number
  filename: string
  status: string
  documentType?: string | null
  caseNumber?: string | null
  createdAt?: string | null
}

type DateRange =
  [Dayjs | null, Dayjs | null] | null

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
  sent: {
    label: 'Отправлен',
    color: 'blue',
  },
}

export default function Exports() {
  const [format, setFormat] =
    useState<ExportFormat>('XLSX')

  const [loading, setLoading] =
    useState(false)

  const [documents, setDocuments] =
    useState<DocumentItem[]>([])

  const [dateRange, setDateRange] =
    useState<DateRange>(null)

  const [
    documentType,
    setDocumentType,
  ] = useState<string | undefined>(
    undefined,
  )

  const [status, setStatus] =
    useState<string | undefined>(
      undefined,
    )

  const [
    selectedRowKeys,
    setSelectedRowKeys,
  ] = useState<React.Key[]>([])

  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const response = await fetch(
          `${BACKEND_URL}/documents`,
        )

        if (!response.ok) {
          throw new Error(
            'Не удалось получить документы',
          )
        }

        const data =
          await response.json()

        setDocuments(data)
      } catch (error) {
        console.error(error)

        message.error(
          'Не удалось получить список документов',
        )
      }
    }

    loadDocuments()
  }, [])

  const exportableDocuments =
    useMemo(() => {
      const allowedStatuses = [
        'processed',
        'needs_review',
        'sent',
      ]

      const allowedTypes = [
        'судебный приказ',
        'исполнительный лист',
        'постановление фссп',
      ]

      return documents.filter(
        (document) => {
          const normalizedType =
            (
              document.documentType || ''
            )
              .trim()
              .toLowerCase()

          const correctStatus =
            allowedStatuses.includes(
              document.status,
            )

          const correctType =
            allowedTypes.includes(
              normalizedType,
            )

          if (
            !correctStatus ||
            !correctType
          ) {
            return false
          }

          if (
            status &&
            document.status !== status
          ) {
            return false
          }

          if (
            documentType &&
            normalizedType !==
              documentType
          ) {
            return false
          }

          if (
            dateRange &&
            document.createdAt
          ) {
            const createdAt =
              dayjs(
                document.createdAt,
              )

            const [start, end] =
              dateRange

            if (
              start &&
              createdAt.isBefore(
                start.startOf('day'),
              )
            ) {
              return false
            }

            if (
              end &&
              createdAt.isAfter(
                end.endOf('day'),
              )
            ) {
              return false
            }
          }

          return true
        },
      )
    }, [
      documents,
      status,
      documentType,
      dateRange,
    ])

  const downloadExport = async (
    selectedFormat: ExportFormat,
  ) => {
    setLoading(true)

    try {
      const params =
        new URLSearchParams()

      params.set(
        'format',
        selectedFormat.toLowerCase(),
      )

      if (status) {
        params.set(
          'status',
          status,
        )
      }

      if (documentType) {
        params.set(
          'document_type',
          documentType,
        )
      }

      if (dateRange?.[0]) {
        params.set(
          'date_from',
          dateRange[0].format(
            'YYYY-MM-DD',
          ),
        )
      }

      if (dateRange?.[1]) {
        params.set(
          'date_to',
          dateRange[1].format(
            'YYYY-MM-DD',
          ),
        )
      }

      // Если пользователь выбрал
      // конкретные документы —
      // выгружаем только их.
      selectedRowKeys.forEach(
        (id) => {
          params.append(
            'document_ids',
            String(id),
          )
        },
      )

      const response = await fetch(
        `${BACKEND_URL}/documents/exports/download?${params.toString()}`,
      )

      if (!response.ok) {
        const errorText =
          await response.text()

        throw new Error(
          errorText ||
            'Не удалось сформировать выгрузку',
        )
      }

      const blob =
        await response.blob()

      const url =
        window.URL.createObjectURL(
          blob,
        )

      const link =
        document.createElement('a')

      link.href = url

      link.download =
        selectedFormat === 'XLSX'
          ? 'documents.xlsx'
          : 'documents.csv'

      document.body.appendChild(
        link,
      )

      link.click()

      link.remove()

      window.URL.revokeObjectURL(
        url,
      )

      message.success(
        `Выгрузка ${selectedFormat} сформирована`,
      )
    } catch (error) {
      console.error(error)

      message.error(
        'Не удалось сформировать выгрузку',
      )
    } finally {
      setLoading(false)
    }
  }

  const resetFilters = () => {
    setDateRange(null)
    setDocumentType(undefined)
    setStatus(undefined)
    setSelectedRowKeys([])
  }

  const selectedCount =
    selectedRowKeys.length

  const documentsToExport =
    selectedCount > 0
      ? selectedCount
      : exportableDocuments.length

  return (
    <div>
      <h1>Выгрузки</h1>

      <Space
        direction="vertical"
        size="large"
        style={{
          width: '100%',
        }}
      >
        <Card title="Сформировать выгрузку">
          <Space
            direction="vertical"
            size="middle"
            style={{
              width: '100%',
            }}
          >
            <Statistic
              title="Документов для выгрузки"
              value={
                documentsToExport
              }
            />

            <Alert
              type="info"
              showIcon
              message={
                selectedCount > 0
                  ? `Выбрано документов: ${selectedCount}`
                  : 'Документы вручную не выбраны'
              }
              description={
                selectedCount > 0
                  ? 'В выгрузку попадут только отмеченные документы.'
                  : 'Если документы не отмечать галочками, в выгрузку попадут все документы, соответствующие фильтрам.'
              }
            />

            <Form layout="inline">
              <Form.Item label="Период">
                <DatePicker.RangePicker
                  value={dateRange}
                  onChange={(value) => {
                    setDateRange(
                      value as DateRange,
                    )

                    setSelectedRowKeys(
                      [],
                    )
                  }}
                  format="DD.MM.YYYY"
                  allowClear
                />
              </Form.Item>

              <Form.Item label="Тип">
                <Select
                  allowClear
                  style={{
                    width: 210,
                  }}
                  placeholder="Любой"
                  value={documentType}
                  onChange={(value) => {
                    setDocumentType(
                      value,
                    )

                    setSelectedRowKeys(
                      [],
                    )
                  }}
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
                        'постановление фссп',
                      label:
                        'Постановление ФССП',
                    },
                  ]}
                />
              </Form.Item>

              <Form.Item label="Статус">
                <Select
                  allowClear
                  style={{
                    width: 180,
                  }}
                  placeholder="Любой"
                  value={status}
                  onChange={(value) => {
                    setStatus(value)

                    setSelectedRowKeys(
                      [],
                    )
                  }}
                  options={[
                    {
                      value:
                        'processed',
                      label:
                        'Обработан',
                    },
                    {
                      value:
                        'needs_review',
                      label:
                        'На проверке',
                    },
                    {
                      value: 'sent',
                      label:
                        'Отправлен',
                    },
                  ]}
                />
              </Form.Item>

              <Form.Item label="Формат">
                <Select
                  style={{
                    width: 120,
                  }}
                  value={format}
                  onChange={setFormat}
                  options={[
                    {
                      value: 'XLSX',
                      label: 'XLSX',
                    },
                    {
                      value: 'CSV',
                      label: 'CSV',
                    },
                  ]}
                />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    icon={
                      <DownloadOutlined />
                    }
                    loading={loading}
                    disabled={
                      documentsToExport ===
                      0
                    }
                    onClick={() =>
                      downloadExport(
                        format,
                      )
                    }
                  >
                    Сформировать
                  </Button>

                  <Button
                    onClick={
                      resetFilters
                    }
                  >
                    Сбросить
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Space>
        </Card>

        <Card
          title="Документы для выгрузки"
          extra={
            selectedCount > 0
              ? `Выбрано: ${selectedCount}`
              : `Всего: ${exportableDocuments.length}`
          }
        >
          <Table
            rowKey="id"
            dataSource={
              exportableDocuments
            }
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              pageSizeOptions: [
                '10',
                '20',
                '50',
              ],
            }}
            rowSelection={{
              selectedRowKeys,
              onChange: (
                keys,
              ) => {
                setSelectedRowKeys(
                  keys,
                )
              },
            }}
            columns={[
              {
                title: 'Дата',
                dataIndex:
                  'createdAt',
                width: 180,
                render: (
                  value:
                    | string
                    | null,
                ) =>
                  value
                    ? dayjs(
                        value,
                      ).format(
                        'DD.MM.YYYY, HH:mm:ss',
                      )
                    : '—',
              },
              {
                title: 'Файл',
                dataIndex:
                  'filename',
              },
              {
                title: 'Тип',
                dataIndex:
                  'documentType',
                render: (
                  value:
                    | string
                    | null,
                ) =>
                  value || '—',
              },
              {
                title:
                  '№ дела / ИП',
                dataIndex:
                  'caseNumber',
                render: (
                  value:
                    | string
                    | null,
                ) =>
                  value || '—',
              },
              {
                title: 'Статус',
                dataIndex:
                  'status',
                width: 150,
                render: (
                  value: string,
                ) => {
                  const config =
                    statusConfig[
                      value
                    ]

                  if (!config) {
                    return value
                  }

                  return (
                    <Tag
                      color={
                        config.color
                      }
                    >
                      {
                        config.label
                      }
                    </Tag>
                  )
                },
              },
            ]}
          />
        </Card>
      </Space>
    </div>
  )
}