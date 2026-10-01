import { Modal, Upload, List, Typography, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { useState } from 'react'

const { Dragger } = Upload
const { Text } = Typography

interface Props {
  open: boolean
  onClose: () => void
}

const BACKEND_URL = 'http://localhost:8000'

export default function UploadModal({ open, onClose }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)

  const totalSize = files.reduce((acc, f) => acc + f.size, 0)
  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
  }

  const handleOk = async () => {
    if (files.length === 0) return

    setUploading(true)
    let successCount = 0
    let errorCount = 0

    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)

      try {
        const response = await fetch(`${BACKEND_URL}/documents/upload`, {
          method: 'POST',
          body: formData,
        })

        if (response.ok) {
          successCount++
        } else {
          errorCount++
          console.error(`Ошибка загрузки ${file.name}:`, await response.text())
        }
      } catch (error) {
        errorCount++
        console.error(`Сетевая ошибка при загрузке ${file.name}:`, error)
      }
    }

    setUploading(false)

    if (errorCount === 0) {
      message.success(`Успешно загружено файлов: ${successCount}`)
    } else {
      message.warning(`Загружено: ${successCount}, Ошибок: ${errorCount}`)
    }

    setFiles([])
    onClose()
  }

  return (
    <Modal
      title="Загрузка документов"
      open={open}
      onCancel={() => !uploading && onClose()}
      onOk={handleOk}
      okText="Загрузить"
      cancelText="Отмена"
      confirmLoading={uploading}
      width={600}
    >
      <Dragger
        multiple
        accept=".pdf,.xml"
        beforeUpload={(file) => {
          setFiles((prev) => [...prev, file])
          return false
        }}
        onRemove={(file) => {
          setFiles((prev) => prev.filter((f) => f.name !== file.name))
        }}
        showUploadList={{
          showRemoveIcon: !uploading,
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p>
          Перетащите файлы сюда или <Text type="secondary">выберите</Text>
        </p>
        <p className="ant-upload-hint">Поддерживаются PDF и XML</p>
      </Dragger>

      {files.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text strong>
            Выбрано: {files.length} файлов • Общий размер: {formatSize(totalSize)}
          </Text>
          <List
            size="small"
            dataSource={files}
            renderItem={(f) => (
              <List.Item>
                {f.name} <Text type="secondary">({formatSize(f.size)})</Text>
              </List.Item>
            )}
            style={{ marginTop: 8, maxHeight: 200, overflowY: 'auto' }}
          />
        </div>
      )}
    </Modal>
  )
}