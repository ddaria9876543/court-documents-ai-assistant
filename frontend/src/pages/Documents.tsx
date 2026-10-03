import {
  Table,
  Input,
  Select,
  Space,
  Tag,
  DatePicker,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Document } from '../types/document'
import dayjs from 'dayjs'

const BACKEND_URL = 'http://127.0.0.1:8000'

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

const normalizeDocumentType = (
  value?: string | null,
) => {
  if (!value) {
    return ''
  }

  return value
    .replace(/\u0301/g, '')
    .trim()
    .toLowerCase()
}

const formatDocumentType = (
  value?: string | null,
) => {
  if (!value) {
    return '—'
  }

  const cleaned =
    normalizeDocumentType(value)

  const typeMap: Record<string, string> = {
    'судебный приказ':
      'Судебный приказ',

    'исполнительный лист':
      'Исполнительный лист',

    'постановление фссп':
      'Постановление ФССП',

    'определение':
      'Определение',

    'исполнительное производство':
      'Исполнительное производство',

    'исполнительное постановление':
      'Исполнительное постановление',
  }

  if (typeMap[cleaned]) {
    return typeMap[cleaned]
  }

  return (
    cleaned.charAt(0).toUpperCase() +
    cleaned.slice(1)
  )
}

export default function Documents() {
  const navigate = useNavigate()

  const [documents, setDocuments] =
    useState<Document[]>([])

  const [loading, setLoading] =
    useState(false)

  const [search, setSearch] =
    useState('')

  const [
    statusFilter,
    setStatusFilter,
  ] = useState<string | undefined>()

  const [
    typeFilter,
    setTypeFilter,
  ] = useState<string | undefined>()

  const [
    formatFilter,
    setFormatFilter,
  ] = useState<string | undefined>()

  const [
    dateFilter,
    setDateFilter,
  ] = useState<string | undefined>()

  const loadDocuments = async () => {
    setLoading(true)

    try {
      const response = await fetch(
        `${BACKEND_URL}/documents`,
      )

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}`,
        )
      }

      const data: Document[] =
        await response.json()

      setDocuments(data)
    } catch (error) {
      console.error(
        'Ошибка загрузки документов:',
        error,
      )

      message.error(
        'Не удалось получить документы с backend',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [])

  const filtered = documents.filter(
    (d) => {
      const searchValue =
        search.toLowerCase()

      const matchSearch =
        d.filename
          .toLowerCase()
          .includes(searchValue) ||
        (d.caseNumber || '')
          .toLowerCase()
          .includes(searchValue) ||
        (d.enforcementNumber || '')
          .toLowerCase()
          .includes(searchValue)

      const matchStatus =
        !statusFilter ||
        d.status === statusFilter

      const matchType =
        !typeFilter ||
        normalizeDocumentType(
          d.documentType,
        ) === typeFilter

      const matchFormat =
        !formatFilter ||
        d.fileFormat?.toLowerCase() ===
          formatFilter

      const matchDate =
        !dateFilter ||
        d.createdAt.startsWith(
          dateFilter,
        )

      return (
        matchSearch &&
        matchStatus &&
        matchType &&
        matchFormat &&
        matchDate
      )
    },
  )

  const typeOptions =
    Array.from(
      new Set(
        documents
          .map((d) =>
            normalizeDocumentType(
              d.documentType,
            ),
          )
          .filter(Boolean),
      ),
    )
      .map((type) => ({
        value: type,
        label:
          formatDocumentType(type),
      }))
      .sort((a, b) =>
        a.label.localeCompare(
          b.label,
          'ru',
        ),
      )

  const columns = [
    {
      title: 'Дата',
      dataIndex: 'createdAt',
      width: 160,

      sorter: (
        a: Document,
        b: Document,
      ) =>
        new Date(
          a.createdAt,
        ).getTime() -
        new Date(
          b.createdAt,
        ).getTime(),

      defaultSortOrder:
        'descend' as const,

      render: (value: string) =>
        new Date(
          value,
        ).toLocaleString(
          'ru-RU',
        ),
    },

    {
      title: 'Файл',
      dataIndex: 'filename',
    },

    {
      title: 'Тип',
      dataIndex: 'documentType',

      sorter: (
        a: Document,
        b: Document,
      ) =>
        formatDocumentType(
          a.documentType,
        ).localeCompare(
          formatDocumentType(
            b.documentType,
          ),
          'ru',
        ),

      render: (
        value?: string | null,
      ) =>
        formatDocumentType(value),
    },

    {
      title: '№ дела / ИП',
      key: 'num',

      render: (
        _: unknown,
        record: Document,
      ) =>
        record.caseNumber ||
        record.enforcementNumber ||
        '—',
    },

    {
      title: 'Результат',
      dataIndex: 'summary',
      ellipsis: true,
    },

    {
      title: 'Работа юриста',
      key: 'legalAction',
      width: 150,

      render: (
        _: unknown,
        record: Document,
      ) =>
        record.requiresLegalAction ? (
          <Tag color="orange">
            Требуется
          </Tag>
        ) : (
          <Tag color="green">
            Не требуется
          </Tag>
        ),
    },

    {
      title: 'Статус',
      dataIndex: 'status',

      sorter: (
        a: Document,
        b: Document,
      ) =>
        a.status.localeCompare(
          b.status,
        ),

      render: (
        status: string,
      ) => {
        const cfg =
          statusConfig[
            status
          ] ?? {
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
      <h1>Документы</h1>

      <Space
        wrap
        style={{
          marginBottom: 16,
        }}
      >
        <Input.Search
          placeholder="Поиск по файлу, делу, ИП"
          allowClear
          style={{
            width: 300,
          }}
          onSearch={setSearch}
          onChange={(e) => {
            setSearch(
              e.target.value,
            )
          }}
        />

        <Select
          allowClear
          placeholder="Статус"
          style={{
            width: 180,
          }}
          onChange={
            setStatusFilter
          }
          options={[
            {
              value: 'processed',
              label: 'Обработан',
            },
            {
              value:
                'needs_review',
              label: 'На проверке',
            },
            {
              value: 'error',
              label: 'Ошибка',
            },
            {
              value: 'sent',
              label: 'Отправлен',
            },
            {
              value:
                'processing',
              label: 'В обработке',
            },
            {
              value: 'new',
              label: 'Новый',
            },
          ]}
        />

        <Select
          allowClear
          placeholder="Тип документа"
          style={{
            width: 220,
          }}
          onChange={
            setTypeFilter
          }
          options={
            typeOptions
          }
        />

        <Select
          allowClear
          placeholder="Формат"
          style={{
            width: 120,
          }}
          onChange={
            setFormatFilter
          }
          options={[
            {
              value: 'pdf',
              label: 'PDF',
            },
            {
              value: 'xml',
              label: 'XML',
            },
          ]}
        />

        <DatePicker
          placeholder="Дата"
          onChange={(date) =>
            setDateFilter(
              date
                ? dayjs(
                    date,
                  ).format(
                    'YYYY-MM-DD',
                  )
                : undefined,
            )
          }
          style={{
            width: 160,
          }}
        />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={filtered}
        loading={loading}
        onRow={(record) => ({
          onClick: () =>
            navigate(
              `/documents/${record.id}`,
            ),

          style: {
            cursor: 'pointer',
          },
        })}
      />
    </div>
  )
}