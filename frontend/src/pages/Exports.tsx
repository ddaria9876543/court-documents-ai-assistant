import { Card, Form, DatePicker, Select, Button, Table, message, Space } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'

export default function Exports() {
  const history = [
    { id: 1, date: '2026-09-29', name: 'docs_2026-09-29.xlsx', count: 12, format: 'XLSX' },
    { id: 2, date: '2026-09-28', name: 'docs_2026-09-28.csv', count: 8, format: 'CSV' },
  ]

  return (
    <div>
      <h1>Выгрузки</h1>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card title="Сформировать выгрузку">
          <Form layout="inline">
            <Form.Item label="Период">
              <DatePicker.RangePicker />
            </Form.Item>
            <Form.Item label="Тип">
              <Select
                style={{ width: 200 }}
                placeholder="Любой"
                options={[
                  { value: 'order', label: 'Судебный приказ' },
                  { value: 'il', label: 'Исполнительный лист' },
                  { value: 'fssp', label: 'Постановление ФССП' },
                ]}
              />
            </Form.Item>
            <Form.Item label="Статус">
              <Select
                style={{ width: 180 }}
                placeholder="Любой"
                options={[
                  { value: 'processed', label: 'Обработан' },
                  { value: 'sent', label: 'Отправлен' },
                  { value: 'needs_review', label: 'На проверке' },
                ]}
              />
            </Form.Item>
            <Form.Item label="Формат">
              <Select
                style={{ width: 120 }}
                defaultValue="XLSX"
                options={[
                  { value: 'XLSX', label: 'XLSX' },
                  { value: 'CSV', label: 'CSV' },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                onClick={() => message.success('Выгрузка сформирована')}
              >
                Сформировать
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="История выгрузок">
          <Table
            rowKey="id"
            dataSource={history}
            columns={[
              { title: 'Дата', dataIndex: 'date' },
              { title: 'Файл', dataIndex: 'name' },
              { title: 'Кол-во документов', dataIndex: 'count' },
              { title: 'Формат', dataIndex: 'format' },
              {
                title: '',
                key: 'action',
                render: () => (
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={() => message.info('Скачивание (мок)')}
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