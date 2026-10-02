import { Layout, Menu } from 'antd'
import {
  HomeOutlined,
  FileTextOutlined,
  EyeOutlined,
  ExportOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import {
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useEffect, useState } from 'react'

const { Sider, Content, Header } = Layout

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  const [activeMenuKey, setActiveMenuKey] = useState(() => {
    const path = location.pathname

    if (path === '/') return '/'
    if (path === '/review') return '/review'
    if (path === '/documents') return '/documents'
    if (path === '/exports') return '/exports'
    if (path === '/settings') return '/settings'

    if (path.startsWith('/documents/')) {
      return '/documents'
    }

    return '/'
  })

  useEffect(() => {
    const path = location.pathname

    if (path === '/') {
      setActiveMenuKey('/')
      return
    }

    if (path === '/review') {
      setActiveMenuKey('/review')
      return
    }

    if (path === '/documents') {
      setActiveMenuKey('/documents')
      return
    }

    if (path === '/exports') {
      setActiveMenuKey('/exports')
      return
    }

    if (path === '/settings') {
      setActiveMenuKey('/settings')
      return
    }

    if (path.startsWith('/documents/')) {
      setActiveMenuKey((current) => {
        if (current === '/review') {
          return '/review'
        }

        return '/documents'
      })
    }
  }, [location.pathname])

  const handleMenuClick = (key: string) => {
    setActiveMenuKey(key)
    navigate(key)
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        theme="light"
        width={220}
        style={{
          borderRight: '1px solid #e8e8e8',
          background: '#F5F7FA',
        }}
      >
        <div
          style={{
            padding: '16px',
            fontWeight: 700,
            fontSize: 18,
            color: '#0054A6',
            borderBottom: '2px solid #F58220',
            marginBottom: 8,
          }}
        >
          ⚡ Doc AI Assistant
        </div>

        <Menu
          mode="inline"
          selectedKeys={[activeMenuKey]}
          items={[
            {
              key: '/',
              icon: <HomeOutlined />,
              label: 'Главная',
            },
            {
              key: '/documents',
              icon: <FileTextOutlined />,
              label: 'Документы',
            },
            {
              key: '/review',
              icon: <EyeOutlined />,
              label: 'На проверке',
            },
            {
              key: '/exports',
              icon: <ExportOutlined />,
              label: 'Выгрузки',
            },
            {
              type: 'divider' as const,
            },
            {
              key: '/settings',
              icon: <SettingOutlined />,
              label: 'Настройки',
            },
          ]}
          onClick={({ key }) =>
            handleMenuClick(key)
          }
          style={{ borderRight: 0 }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: '#f5f5f5',
            padding: '16px 24px',
            display: 'flex',
            alignItems: 'center',
            height: 'auto',
            lineHeight: 'normal',
          }}
        >
          <div
            style={{
              background:
                'linear-gradient(90deg, #0054A6 0%, #1a6fc4 100%)',
              borderRadius: 16,
              padding: '16px 24px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              boxShadow:
                '0 4px 12px rgba(0, 84, 166, 0.2)',
              width: '100%',
            }}
          >
            <div
              style={{
                width: 6,
                height: 28,
                background: '#F58220',
                borderRadius: 3,
              }}
            />

            <h3
              style={{
                margin: 0,
                color: 'white',
                fontSize: 20,
                fontWeight: 600,
              }}
            >
              Судебные документы
            </h3>
          </div>
        </Header>

        <Content
          style={{
            padding: 24,
            background: '#f5f5f5',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}