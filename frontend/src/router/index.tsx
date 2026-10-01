import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '../components/Layout/AppLayout'
import Home from '../pages/Home'
import Documents from '../pages/Documents'
import DocumentDetail from '../pages/DocumentDetail'
import Review from '../pages/Review'
import Exports from '../pages/Exports'
import Settings from '../pages/Settings'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'documents', element: <Documents /> },
      { path: 'documents/:id', element: <DocumentDetail /> },
      { path: 'review', element: <Review /> },
      { path: 'exports', element: <Exports /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
])