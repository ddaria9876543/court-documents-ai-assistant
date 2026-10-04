import {
  Card,
  List,
  Tag,
  Select,
  DatePicker,
  Input,
  Spin,
  Empty,
  message,
} from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import dayjs from 'dayjs'

import type { Document } from '../types/document'

const BACKEND_URL = 'http://127.0.0.1:8000'

export default function Review() {
  const navigate = useNavigate()
  const location = useLocation()

  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)

  const [typeFilter, setTypeFilter] = useState<string>()
  const [dateFilter, setDateFilter] = useState<string>()
  const [reasonFilter, setReasonFilter] = useState('')

  const loadDocuments = async () => {
    try {
      setLoading(true)

      const response = await fetch(`${BACKEND_URL}/documents`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data: Document[] = await response.json()
      setDocuments(data)
    } catch (error) {
      console.error('Ошибка загрузки документов:', error)
      message.error('Не удалось загрузить документы')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocuments()
  }, [location.key])

  const docs = useMemo(() => {
    return documents
      .filter((d) => d.status === 'needs_review')
      .filter(
        (d) =>
          !typeFilter ||
          d.documentType === typeFilter
      )
      .filter(
        (d) =>
          !dateFilter ||
          d.createdAt.startsWith(dateFilter)
      )
      .filter((d) => {
        if (!reasonFilter) {
          return true
        }

        return (d.reviewReason || '')
          .toLowerCase()
          .includes(
            reasonFilter.toLowerCase()
          )
      })
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() -
          new Date(a.createdAt).getTime()
      )
  }, [
    documents,
    typeFilter,
    dateFilter,
    reasonFilter,
  ])

  const types = useMemo(() => {
    return Array.from(
      new Set(
        documents
          .filter(
            (d) =>
              d.status === 'needs_review'
          )
          .map((d) => d.documentType)
          .filter(
            (type): type is string =>
              Boolean(type)
          )
      )
    )
  }, [documents])

  return (
    <div>
      <h1>Документы на проверке</h1>

      <Card
        title="Требуют проверки"
        extra={
          <div
            style={{
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <Select
              allowClear
              placeholder="Тип"
              style={{ width: 200 }}
              value={typeFilter}
              onChange={setTypeFilter}
              options={types.map((type) => ({
                value: type,
                label: type,
              }))}
            />

            <DatePicker
              placeholder="Дата"
              onChange={(date) =>
                setDateFilter(
                  date
                    ? dayjs(date).format(
                        'YYYY-MM-DD'
                      )
                    : undefined
                )
              }
              style={{ width: 160 }}
            />

            <Input.Search
              placeholder="Причина"
              allowClear
              style={{ width: 200 }}
              onSearch={setReasonFilter}
              onChange={(event) => {
                const value =
                  event.target.value

                if (!value) {
                  setReasonFilter('')
                }
              }}
            />
          </div>
        }
      >
        {loading ? (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              padding: 40,
            }}
          >
            <Spin size="large" />
          </div>
        ) : docs.length === 0 ? (
          <Empty
            description="Документов на проверке нет"
          />
        ) : (
          <List
            dataSource={docs}
            renderItem={(doc) => (
              <List.Item
                onClick={() =>
                  navigate(
                    `/documents/${doc.id}`
                  )
                }
                style={{
                  cursor: 'pointer',
                }}
              >
                <List.Item.Meta
                  title={
                    <>
                      {doc.documentType ||
                        'Тип не определён'}{' '}
                      <Tag>
                        {doc.caseNumber ||
                          doc.enforcementNumber ||
                          '—'}
                      </Tag>
                    </>
                  }
                  description={
                    <>
                      <div>
                        Дата:{' '}
                        {new Date(
                          doc.createdAt
                        ).toLocaleString(
                          'ru-RU'
                        )}
                      </div>

                      <div
                        style={{
                          color: '#faad14',
                        }}
                      >
                        Причина:{' '}
                        {doc.reviewReason ||
                          'Требуется проверка'}
                      </div>

                      {doc.summary && (
                        <div>
                          {doc.summary}
                        </div>
                      )}
                    </>
                  }
                />

                <Tag color="orange">
                  На проверке
                </Tag>
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}