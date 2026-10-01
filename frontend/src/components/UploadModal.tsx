import { Modal, Upload, List, Typography } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { message } from 'antd';

const { Dragger } = Upload;
const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function UploadModal({ open, onClose }: Props) {
  const [files, setFiles] = useState<File[]>([]);

  const totalSize = files.reduce((acc, f) => acc + f.size, 0);
  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  };

  const handleOk = () => {
    message.success('Документы добавлены в очередь');
    setFiles([]);
    onClose();
  };

  return (
    <Modal
      title="Загрузка документов"
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      okText="Загрузить"
      cancelText="Отмена"
      width={600}
    >
      <Dragger
        multiple
        accept=".pdf,.xml"
        beforeUpload={(file) => {
          setFiles((prev) => [...prev, file]);
          return false;
        }}
        showUploadList={false}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p>Перетащите файлы сюда или <Text type="secondary">выберите</Text></p>
        <p className="ant-upload-hint">PDF, XML</p>
      </Dragger>

      {files.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text strong>
            Выбрано: {files.length} файлов • Общий размер: {formatSize(totalSize)}
          </Text>
          <List
            size="small"
            dataSource={files}
            renderItem={(f) => <List.Item>{f.name}</List.Item>}
            style={{ marginTop: 8 }}
          />
        </div>
      )}
    </Modal>
  );
}