import { Card, Form, Input, Switch, Button, message } from 'antd'

export default function Settings() {
  return (
    <div>
      <h1>Настройки</h1>
      <Card title="Настройки системы" style={{ maxWidth: 600 }}>
        <Form
          layout="vertical"
          initialValues={{
            sender: '',
            receiver: '',
            autoSend: true,
            background: true,
          }}
        >
          <Form.Item label="Email отправителя" name="sender">
            <Input placeholder="noreply@company.ru" />
          </Form.Item>
          <Form.Item label="Email ответственного" name="receiver">
            <Input placeholder="lawyer@company.ru" />
          </Form.Item>
          <Form.Item
            label="Автоматическая отправка писем"
            name="autoSend"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            label="Фоновая обработка документов"
            name="background"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Button
            type="primary"
            onClick={() => message.success('Настройки сохранены')}
          >
            Сохранить
          </Button>
        </Form>
      </Card>
    </div>
  )
}