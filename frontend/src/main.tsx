import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import { router } from './router'

const interRAOTheme = {
  token: {
    colorPrimary: '#0054A6',
    colorSuccess: '#2B7A3D',
    colorWarning: '#F58220',
    colorError: '#D32F2F',
    colorInfo: '#0054A6',
    borderRadius: 16,
  },
  algorithm: theme.defaultAlgorithm,
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={ruRU} theme={interRAOTheme}>
      <RouterProvider router={router} />
    </ConfigProvider>
  </React.StrictMode>,
)