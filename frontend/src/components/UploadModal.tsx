import {
  List,
  Modal,
  Typography,
  Upload,
  message,
} from 'antd'

import { InboxOutlined } from '@ant-design/icons'
import { useMemo, useState } from 'react'

const { Dragger } = Upload
const { Text } = Typography

interface Props {
  open: boolean
  onClose: () => void
}

interface FileGroup {
  key: string
  pdf?: File
  xml?: File
}

const BACKEND_URL = 'http://127.0.0.1:8000'

const getBaseName = (filename: string) =>
  filename
    .replace(/\.(pdf|xml)$/i, '')
    .toLowerCase()

const formatSize = (bytes: number) => {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} КБ`
  }

  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

export default function UploadModal({
  open,
  onClose,
}: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] =
    useState(false)

  const totalSize = files.reduce(
    (sum, file) => sum + file.size,
    0,
  )

  const groups = useMemo<FileGroup[]>(() => {
    const map = new Map<string, FileGroup>()

    for (const file of files) {
      const key = getBaseName(file.name)

      const group =
        map.get(key) || {
          key,
        }

      const name = file.name.toLowerCase()

      if (name.endsWith('.pdf')) {
        group.pdf = file
      }

      if (name.endsWith('.xml')) {
        group.xml = file
      }

      map.set(key, group)
    }

    return Array.from(map.values())
  }, [files])

  const uploadSingleFile = async (
    file: File,
  ) => {
    const formData = new FormData()

    formData.append('files', file)

    return fetch(
      `${BACKEND_URL}/documents/upload`,
      {
        method: 'POST',
        body: formData,
      },
    )
  }

  const uploadPair = async (
    xml: File,
    pdf: File,
  ) => {
    const formData = new FormData()

    formData.append('source_file', xml)
    formData.append('original_file', pdf)

    return fetch(
      `${BACKEND_URL}/documents/upload-pair`,
      {
        method: 'POST',
        body: formData,
      },
    )
  }

  const handleOk = async () => {
    if (files.length === 0) {
      return
    }

    setUploading(true)

    let successCount = 0
    let duplicateCount = 0
    let errorCount = 0

    try {
      for (const group of groups) {
        let response: Response

        // XML + PDF:
        // XML используется как источник данных,
        // PDF сохраняется как оригинал.
        if (group.xml && group.pdf) {
          response = await uploadPair(
            group.xml,
            group.pdf,
          )
        }

        // Только XML:
        // XML разрешено обрабатывать самостоятельно.
        else if (group.xml) {
          response = await uploadSingleFile(
            group.xml,
          )
        }

        // Только PDF:
        // обычный судебный документ.
        else if (group.pdf) {
          response = await uploadSingleFile(
            group.pdf,
          )
        } else {
          continue
        }

        if (!response.ok) {
          errorCount++

          console.error(
            await response.text(),
          )

          continue
        }

        const result = await response.json()

        if (result.uploaded?.length) {
          successCount +=
            result.uploaded.length
        }

        if (result.duplicates?.length) {
          duplicateCount +=
            result.duplicates.length
        }

        if (result.errors?.length) {
          errorCount +=
            result.errors.length

          console.error(result.errors)
        }
      }
    } catch (error) {
      console.error(error)
      errorCount++
    } finally {
      setUploading(false)
    }

    if (
      successCount > 0 &&
      errorCount === 0
    ) {
      message.success(
        `Загружено документов: ${successCount}`,
      )
    } else if (successCount > 0) {
      message.warning(
        `Загружено: ${successCount}, ошибок: ${errorCount}`,
      )
    } else if (
      duplicateCount > 0 &&
      errorCount === 0
    ) {
      message.info(
        `Дубликатов: ${duplicateCount}`,
      )
    } else {
      message.error(
        'Не удалось загрузить документы',
      )

      return
    }

    setFiles([])
    onClose()

    window.location.reload()
  }

  const handleCancel = () => {
    if (uploading) {
      return
    }

    setFiles([])
    onClose()
  }

  return (
    <Modal
      title="Загрузка документов"
      open={open}
      onCancel={handleCancel}
      onOk={handleOk}
      okText="Загрузить"
      cancelText="Отмена"
      confirmLoading={uploading}
      okButtonProps={{
        disabled: files.length === 0,
      }}
      width={650}
    >
      <Dragger
        multiple
        accept=".pdf,.xml"
        disabled={uploading}
        beforeUpload={(file) => {
          setFiles((previous) => {
            const duplicate =
              previous.some(
                (existing) =>
                  existing.name === file.name,
              )

            if (duplicate) {
              return previous
            }

            return [
              ...previous,
              file,
            ]
          })

          return false
        }}
        onRemove={(file) => {
          setFiles((previous) =>
            previous.filter(
              (existing) =>
                existing.name !== file.name,
            ),
          )
        }}
        showUploadList={{
          showRemoveIcon: !uploading,
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>

        <p>
          Перетащите документы сюда или{' '}
          <Text type="secondary">
            выберите файлы
          </Text>
        </p>

        <p className="ant-upload-hint">
          PDF и XML можно загружать отдельно.
          Для XML ФССП при наличии PDF
          с таким же именем можно загрузить
          оба файла вместе.
        </p>
      </Dragger>

      {files.length > 0 && (
        <div
          style={{
            marginTop: 16,
          }}
        >
          <Text strong>
            Выбрано: {files.length} файлов
            {' • '}
            {formatSize(totalSize)}
          </Text>

          <List
            size="small"
            dataSource={groups}
            style={{
              marginTop: 12,
              maxHeight: 260,
              overflowY: 'auto',
            }}
            renderItem={(group) => (
              <List.Item>
                <div>
                  <Text strong>
                    {group.key}
                  </Text>

                  {group.xml && (
                    <div>
                      XML: {group.xml.name}
                    </div>
                  )}

                  {group.pdf && (
                    <div>
                      PDF: {group.pdf.name}
                    </div>
                  )}

                  {group.xml &&
                    !group.pdf && (
                      <Text type="secondary">
                        XML будет обработан
                        самостоятельно
                      </Text>
                    )}

                  {!group.xml &&
                    group.pdf && (
                      <Text type="secondary">
                        PDF-документ
                      </Text>
                    )}

                  {group.xml &&
                    group.pdf && (
                      <Text type="success">
                        XML + PDF-оригинал
                      </Text>
                    )}
                </div>
              </List.Item>
            )}
          />
        </div>
      )}
    </Modal>
  )
}