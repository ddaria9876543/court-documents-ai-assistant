import {
  Card,
  Form,
  DatePicker,
  Select,
  Button,
  Table,
  message,
  Space,
} from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useState } from 'react'

const BACKEND_URL = 'http://127.0.0.1:8000'

type ExportFormat = 'XLSX' | 'CSV'

export default function Exports() {
  const [format, setFormat] = useState<ExportFormat>('XLSX')
  const [loading, setLoading] = useState(false)

  const history = [
    {
      id: 1,
      date: '2026-10-03',
      name: 'documents.xlsx',
      count: 'Все документы',
      format: 'XLSX',
    },
    {
      id: 2,
      date: '2026-10-03',
      name: 'documents.csv',
      count: 'Все документы',
      format: 'CSV',
    },
  ]

  const downloadExport = async (
    selectedFormat: ExportFormat,
  ) => {
    setLoading(true)

    try {
      const exportFormat =
        selectedFormat.toLowerCase()

      const response = await fetch(
        `${BACKEND_URL}/documents/exports/download?format=${exportFormat}`,
      )

      if (!response.ok) {
        const errorText =
          await response.text()

        throw new Error(
          errorText ||
            'Не удалось сформировать выгрузку',
        )
      }

      const blob = await response.blob()

      const url =
        window.URL.createObjectURL(blob)

      const link =
        document.createElement('a')

      link.href = url

      link.download =
        selectedFormat === 'XLSX'
          ? 'documents.xlsx'
          : 'documents.csv'

      document.body.appendChild(link)

      link.click()

      link.remove()

      window.URL.revokeObjectURL(url)

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

  return (
    <div>
      <h1>Выгрузки</h1>

      <Space
        direction="vertical"
        size="large"
        style={{ width: '100%' }}
      >
        <Card title="Сформировать выгрузку">
          <Form layout="inline">
            <Form.Item label="Период">
              <DatePicker.RangePicker disabled />
            </Form.Item>

            <Form.Item label="Тип">
              <Select
                style={{ width: 200 }}
                placeholder="Любой"
                disabled
                options={[
                  {
                    value: 'order',
                    label: 'Судебный приказ',
                  },
                  {
                    value: 'il',
                    label: 'Исполнительный лист',
                  },
                  {
                    value: 'fssp',
                    label: 'Постановление ФССП',
                  },
                ]}
              />
            </Form.Item>

            <Form.Item label="Статус">
              <Select
                style={{ width: 180 }}
                placeholder="Любой"
                disabled
                options={[
                  {
                    value: 'processed',
                    label: 'Обработан',
                  },
                  {
                    value: 'sent',
                    label: 'Отправлен',
                  },
                  {
                    value: 'needs_review',
                    label: 'На проверке',
                  },
                ]}
              />
            </Form.Item>

            <Form.Item label="Формат">
              <Select
                style={{ width: 120 }}
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
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                loading={loading}
                onClick={() =>
                  downloadExport(format)
                }
              >
                Сформировать
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="Доступные выгрузки">
          <Table
            rowKey="id"
            pagination={false}
            dataSource={history}
            columns={[
              {
                title: 'Дата',
                dataIndex: 'date',
              },
              {
                title: 'Файл',
                dataIndex: 'name',
              },
              {
                title: 'Документы',
                dataIndex: 'count',
              },
              {
                title: 'Формат',
                dataIndex: 'format',
              },
              {
                title: '',
                key: 'action',
                render: (_, record) => (
                  <Button
                    icon={
                      <DownloadOutlined />
                    }
                    onClick={() =>
                      downloadExport(
                        record.format as ExportFormat,
                      )
                    }
                  >
                    Скачать
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Space>
    </div>
  )
}